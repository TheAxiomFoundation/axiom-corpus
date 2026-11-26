from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import sys
import threading
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

import scripts.repair_plan_cascade_self_containment as repair_module
from scripts.repair_plan_cascade_self_containment import _refuse_base_repairs
from tests.conftest import fixture_git

SUFFIX = "r2026-11-17-repaired"
BASE = ("us-example", "statute", "base-v")
PRIMARY = ("us-example", "statute", "primary-v")
OTHER_PRIMARY = ("us-example", "regulation", "primary-w")
REPAIRED_PRIMARY = ("us-example", "statute", f"primary-v-{SUFFIX}")


def _row(scope: tuple[str, str, str], *, layer: str | None = None) -> dict[str, str]:
    row = {"jurisdiction": scope[0], "document_class": scope[1], "version": scope[2]}
    if layer is not None:
        row["layer"] = layer
    return row


def _payload(*rows: dict[str, str]) -> dict[str, object]:
    return {"name": "us-example-repair", "scopes": list(rows)}


def _mapped(*scopes: tuple[str, str, str]) -> dict[tuple[str, str, str], tuple[str, str, str]]:
    return {scope: (scope[0], scope[1], f"{scope[2]}-{SUFFIX}") for scope in scopes}


def test_allows_a_repair_of_primary_scopes_beside_bases():
    # The payload's base and the tracked base are both left out of the repair.
    _refuse_base_repairs(
        _payload(_row(BASE, layer="base"), _row(PRIMARY), _row(OTHER_PRIMARY)),
        _mapped(PRIMARY, OTHER_PRIMARY),
        frozenset({BASE, ("us-example", "regulation", "base-w")}),
    )


def test_refuses_a_scope_the_release_payload_marks_as_base():
    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be repaired: "
        r"us-example/statute/base-v$",
    ):
        _refuse_base_repairs(
            _payload(_row(BASE, layer="base"), _row(PRIMARY)),
            _mapped(BASE, PRIMARY),
            frozenset(),
        )


def test_refuses_a_scope_a_tracked_selector_marks_as_base():
    # The release payload carries the scope as primary.
    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be repaired: "
        r"us-example/statute/primary-v$",
    ):
        _refuse_base_repairs(
            _payload(_row(PRIMARY), _row(OTHER_PRIMARY)),
            _mapped(PRIMARY, OTHER_PRIMARY),
            frozenset({PRIMARY}),
        )


def test_refuses_a_repair_whose_new_scope_is_a_tracked_base():
    new_scope = ("us-example", "statute", f"primary-v-{SUFFIX}")
    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be repaired: "
        rf"us-example/statute/primary-v-{SUFFIX}$",
    ):
        _refuse_base_repairs(
            _payload(_row(PRIMARY)),
            _mapped(PRIMARY),
            frozenset({new_scope}),
        )


@pytest.mark.parametrize(
    ("rows", "repaired", "tracked", "refused"),
    [
        pytest.param(
            (_row(PRIMARY), _row(REPAIRED_PRIMARY, layer="base")),
            (PRIMARY,),
            frozenset(),
            f"us-example/statute/primary-v-{SUFFIX}",
            id="payload-base-is-the-new-scope",
        ),
        pytest.param(
            (_row(PRIMARY), _row(REPAIRED_PRIMARY, layer="base"), _row(OTHER_PRIMARY)),
            (PRIMARY, OTHER_PRIMARY),
            frozenset({OTHER_PRIMARY}),
            f"us-example/regulation/primary-w, us-example/statute/primary-v-{SUFFIX}",
            id="beside-a-tracked-base-key",
        ),
    ],
)
def test_refuses_a_repair_whose_new_scope_the_release_payload_marks_as_base(
    rows, repaired, tracked, refused
):
    # The release's own payload declares the new scope a base, so the repair
    # would write over a base's files. No tracked selector needs to say so.
    with pytest.raises(
        ValueError,
        match="^"
        + re.escape(f"base scopes are carried unchanged and cannot be repaired: {refused}")
        + "$",
    ):
        _refuse_base_repairs(_payload(*rows), _mapped(*repaired), tracked)


def test_names_every_refused_scope_in_order():
    with pytest.raises(
        ValueError,
        match=r"cannot be repaired: us-example/regulation/primary-w, us-example/statute/base-v$",
    ):
        _refuse_base_repairs(
            _payload(_row(BASE, layer="base"), _row(OTHER_PRIMARY)),
            _mapped(BASE, OTHER_PRIMARY),
            frozenset({OTHER_PRIMARY}),
        )


@pytest.mark.parametrize("layer", ["primary", "Base", ""])
def test_refuses_a_release_payload_with_an_invalid_layer(layer):
    with pytest.raises(
        ValueError, match=r"^release scope us-example/statute/base-v has an invalid layer"
    ):
        _refuse_base_repairs(
            _payload(_row(BASE, layer=layer), _row(PRIMARY)),
            _mapped(PRIMARY),
            frozenset(),
        )


def _tree(root: Path) -> dict[str, bytes | None]:
    """Every path under ``root``, with a file's bytes and None for a directory."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in sorted(root.rglob("*"))
    }


def _write_repo(
    repo: Path, *, release: Path, release_layer: str | None, tracked_base: bool
) -> None:
    """Write one scope whose rows name a parent it lacks, so an audit repairs it."""
    corpus = repo / "data" / "corpus"
    jurisdiction, document_class, version = BASE
    rows = [
        {
            "citation_path": "us-example/statute/1/a",
            "document_class": document_class,
            "jurisdiction": jurisdiction,
            "parent_citation_path": "us-example/statute/1",
            "version": version,
        }
    ]
    provisions = corpus / "provisions" / jurisdiction / document_class / f"{version}.jsonl"
    provisions.parent.mkdir(parents=True)
    provisions.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    inventory = corpus / "inventory" / jurisdiction / document_class / f"{version}.json"
    inventory.parent.mkdir(parents=True)
    inventory.write_text(json.dumps({"items": []}) + "\n")
    coverage = corpus / "coverage" / jurisdiction / document_class / f"{version}.json"
    coverage.parent.mkdir(parents=True)
    coverage.write_text(json.dumps({"complete": True}) + "\n")
    source = corpus / "sources" / jurisdiction / document_class / version / "source.html"
    source.parent.mkdir(parents=True)
    source.write_text(f"<p>{version}</p>\n")

    releases = repo / "manifests" / "releases"
    releases.mkdir(parents=True)
    (repo / "SIGNING-COMMANDS.md").write_text(
        f"sign_scope {jurisdiction} {document_class} {version}\n"
    )
    release_path = repo / release
    release_path.parent.mkdir(parents=True, exist_ok=True)
    release_path.write_text(
        json.dumps(_payload(_row(BASE, layer=release_layer)), indent=2, sort_keys=True) + "\n"
    )
    if tracked_base:
        (releases / "us-example-layered.json").write_text(
            json.dumps(
                {"name": "us-example-layered", "scopes": [_row(BASE, layer="base")]},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    else:
        # A tracked selector that marks no base: an inventory with no selector is refused.
        (releases / "us-example-plain.json").write_text(
            json.dumps({"name": "us-example-plain", "scopes": [_row(PRIMARY)]}) + "\n"
        )


@pytest.mark.parametrize(
    ("release", "release_layer", "tracked_base"),
    [
        # The release payload alone marks the scope: no tracked selector does.
        pytest.param(Path("repair") / "release.json", "base", False, id="payload-base"),
        # A tracked selector alone marks the scope: the release carries it as primary.
        pytest.param(
            Path("manifests") / "releases" / "release.json", None, True, id="tracked-base"
        ),
    ],
)
def test_main_refuses_a_base_repair_before_moving_anything(
    tmp_path, monkeypatch, release, release_layer, tracked_base
):
    repo = tmp_path / "repo"
    _write_repo(repo, release=release, release_layer=release_layer, tracked_base=tracked_base)
    report = tmp_path / "report.json"
    before = _tree(repo)
    fetched: list[list[tuple[str, str, str]]] = []
    monkeypatch.setattr(
        repair_module,
        "ensure_corpus_scopes",
        lambda scopes, *, repo: fetched.append(list(scopes)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repair_plan_cascade_self_containment.py",
            "--audit-residuals",
            "--repo",
            str(repo),
            "--release",
            str(release),
            "--suffix",
            SUFFIX,
            "--report",
            str(report),
        ],
    )

    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be repaired: "
        r"us-example/statute/base-v$",
    ):
        repair_module.main()

    # The audit reached the repair plan, and nothing was moved, written or unlinked.
    assert fetched == [[BASE]]
    assert _tree(repo) == before
    assert not report.exists()


@pytest.mark.parametrize(
    ("opening", "closing", "says", "never_says"),
    [
        pytest.param(
            "**Consolidation, composition and repair.**",
            "- `scripts/consolidate_release_scopes.py`",
            (),
            ("before it changes anything",),
            id="lead",
        ),
        pytest.param(
            "- `scripts/repair_plan_cascade_self_containment.py`",
            "**Signing.**",
            ("after it fetches", "before its first move, rewrite or unlink"),
            (),
            id="repair",
        ),
    ],
)
def test_the_docs_time_the_base_refusal_as_main_runs_it(
    tmp_path, monkeypatch, opening, closing, says, never_says
):
    # main() fetches and reads the release's scopes to plan the repair, then
    # refuses a base before it moves anything; the docs must say so.
    repo = tmp_path / "repo"
    _write_repo(
        repo, release=Path("repair") / "release.json", release_layer="base", tracked_base=False
    )
    report = tmp_path / "report.json"
    before = _tree(repo)
    events: list[str] = []
    monkeypatch.setattr(
        repair_module,
        "ensure_corpus_scopes",
        lambda scopes, *, repo: events.append("fetch"),
    )
    refuse = repair_module._refuse_base_repairs

    def recording_refusal(*args, **kwargs):
        events.append("refuse")
        return refuse(*args, **kwargs)

    monkeypatch.setattr(repair_module, "_refuse_base_repairs", recording_refusal)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repair_plan_cascade_self_containment.py",
            "--audit-residuals",
            "--repo",
            str(repo),
            "--release",
            str(Path("repair") / "release.json"),
            "--suffix",
            SUFFIX,
            "--report",
            str(report),
        ],
    )

    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be repaired: "
        r"us-example/statute/base-v$",
    ):
        repair_module.main()

    assert events == ["fetch", "refuse"]
    assert _tree(repo) == before

    docs = " ".join(
        (Path(__file__).parents[1] / "docs" / "named-release-publication.md")
        .read_text(encoding="utf-8")
        .split()
    )
    start = docs.index(opening)
    section = docs[start : docs.index(closing, start + len(opening))]
    for phrase in says:
        assert phrase in section, phrase
    for phrase in never_says:
        assert phrase not in section, phrase


def _write_scope_files(
    corpus: Path, scope: tuple[str, str, str], rows: list[dict[str, str]], *, sources: bool
) -> None:
    jurisdiction, document_class, version = scope
    provisions = corpus / "provisions" / jurisdiction / document_class / f"{version}.jsonl"
    provisions.parent.mkdir(parents=True, exist_ok=True)
    provisions.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    inventory = corpus / "inventory" / jurisdiction / document_class / f"{version}.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    items = [{"citation_path": row["citation_path"]} for row in rows]
    inventory.write_text(json.dumps({"items": items}) + "\n")
    coverage = corpus / "coverage" / jurisdiction / document_class / f"{version}.json"
    coverage.parent.mkdir(parents=True, exist_ok=True)
    coverage.write_text(json.dumps({"complete": True, "version": version}) + "\n")
    if sources:
        source = corpus / "sources" / jurisdiction / document_class / version / "source.html"
        source.parent.mkdir(parents=True)
        source.write_text(f"<p>{version}</p>\n")


def _write_payload_base_repo(repo: Path) -> None:
    """Write a primary scope to repair and the base its release payload names as the repair."""
    corpus = repo / "data" / "corpus"
    # The primary scope's row names a parent it lacks, so an audit repairs it.
    _write_scope_files(
        corpus,
        PRIMARY,
        [
            {
                "citation_path": "us-example/statute/1/a",
                "document_class": PRIMARY[1],
                "jurisdiction": PRIMARY[0],
                "parent_citation_path": "us-example/statute/1",
                "version": PRIMARY[2],
            }
        ],
        sources=True,
    )
    manifest = repo / ".axiom" / "ingest-manifests" / PRIMARY[0] / PRIMARY[1] / f"{PRIMARY[2]}.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"applied_files": [], "version": PRIMARY[2]}) + "\n")
    # The base whose name the suffix spells: self-contained, so the audit leaves it alone.
    _write_scope_files(
        corpus,
        REPAIRED_PRIMARY,
        [
            {
                "citation_path": "us-example/statute/2",
                "document_class": REPAIRED_PRIMARY[1],
                "jurisdiction": REPAIRED_PRIMARY[0],
                "version": REPAIRED_PRIMARY[2],
            }
        ],
        sources=False,
    )
    release = repo / "repair" / "release.json"
    release.parent.mkdir(parents=True)
    release.write_text(
        json.dumps(
            _payload(_row(PRIMARY), _row(REPAIRED_PRIMARY, layer="base")), indent=2, sort_keys=True
        )
        + "\n"
    )
    releases = repo / "manifests" / "releases"
    releases.mkdir(parents=True)
    # A tracked selector that marks no base, so only the release payload names one.
    (releases / "us-example-plain.json").write_text(
        json.dumps({"name": "us-example-plain", "scopes": [_row(PRIMARY)]}) + "\n"
    )
    (repo / "SIGNING-COMMANDS.md").write_text(
        f"sign_scope {PRIMARY[0]} {PRIMARY[1]} {PRIMARY[2]}\n"
    )


def test_main_refuses_a_repair_onto_a_payload_base_before_moving_anything(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _write_payload_base_repo(repo)
    report = tmp_path / "report.json"
    before = _tree(repo)
    fetched: list[list[tuple[str, str, str]]] = []
    monkeypatch.setattr(
        repair_module,
        "ensure_corpus_scopes",
        lambda scopes, *, repo: fetched.append(list(scopes)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repair_plan_cascade_self_containment.py",
            "--audit-residuals",
            "--repo",
            str(repo),
            "--release",
            str(Path("repair") / "release.json"),
            "--suffix",
            SUFFIX,
            "--report",
            str(report),
        ],
    )

    with pytest.raises(
        ValueError,
        match=rf"^base scopes are carried unchanged and cannot be repaired: "
        rf"us-example/statute/primary-v-{SUFFIX}$",
    ):
        repair_module.main()

    # The audit reached the repair plan, and the base's files are as they were.
    assert fetched == [[PRIMARY, REPAIRED_PRIMARY]]
    assert _tree(repo) == before
    assert not report.exists()


@pytest.mark.parametrize(
    ("rows", "mapping", "tracked"),
    [
        pytest.param(
            (_row(PRIMARY),),
            {PRIMARY: ("us-example", "statute", "primary-v-FIX")},
            frozenset({("us-example", "statute", "primary-v-fix")}),
            id="suffix-case",
        ),
        pytest.param(
            (_row(PRIMARY),),
            {PRIMARY: ("us-example", "statute", "primary-v-fix/")},
            frozenset({("us-example", "statute", "primary-v-fix")}),
            id="suffix-slash",
        ),
        pytest.param(
            (_row(PRIMARY), _row(("us-example", "statute", "primary-v-FIX"), layer="base")),
            {PRIMARY: ("us-example", "statute", "primary-v-fix")},
            frozenset(),
            id="payload-base-case",
        ),
    ],
)
def test_refuses_a_scope_name_a_selector_cannot_spell(rows, mapping, tracked):
    # On case-insensitive APFS, or through safe_segment, each spelling names
    # the files of another scope while comparing unequal to it.
    with pytest.raises(ValueError, match=r"^not a canonical scope: "):
        _refuse_base_repairs(_payload(*rows), mapping, tracked)


@pytest.mark.parametrize(
    ("rows", "mapping", "refusal"),
    [
        pytest.param(
            (_row(("us-example", "statute", "Base-V"), layer="primary"), _row(PRIMARY)),
            _mapped(PRIMARY),
            "release scope us-example/statute/Base-V has an invalid layer: 'primary'",
            id="same-row",
        ),
        pytest.param(
            (_row(BASE, layer="primary"), _row(PRIMARY)),
            {PRIMARY: ("us-example", "statute", "primary-v-FIX")},
            "release scope us-example/statute/base-v has an invalid layer: 'primary'",
            id="new-scope",
        ),
    ],
)
def test_refuses_an_invalid_layer_before_a_spelling(rows, mapping, refusal):
    # The layer loop runs before the spelling check, so a payload with a
    # layer other than "base" gets the layer refusal whatever else it misspells.
    with pytest.raises(ValueError, match=rf"^{re.escape(refusal)}$"):
        _refuse_base_repairs(_payload(*rows), mapping, frozenset())


# Finding 1 of round 2, repair half: links on the paths repair touches, and the
# checkouts that hold them. Primary ``pv1`` needs repair and ``us-layered``
# marks ``bv1`` as a base; every checkout is built with ``make_checkout`` and
# commits its selectors. Each case runs ``main()`` with the fetch stubbed.
MakeCheckout = Callable[[str, Mapping[str, Mapping[str, object]]], Path]
PV1 = ("us", "statute", "pv1")
PV1_FIX = ("us", "statute", "pv1-fix")
QV1 = ("us", "statute", "qv1")
BV1 = ("us", "statute", "bv1")
BV2 = ("us", "statute", "bv2")
PLAIN_RELEASE = Path("manifests") / "releases" / "us-plain.json"
NEEDS_REPAIR = [
    {
        "citation_path": "us/statute/1/a",
        "level": 2,
        "ordinal": 1,
        "parent_citation_path": "us/statute/1",
    }
]
SELF_CONTAINED = [{"citation_path": "us/statute/9", "level": 1, "ordinal": 1}]


def _exactly(text: str) -> str:
    return "^" + re.escape(text) + "$"


def _snapshot(root: Path) -> dict[str, object]:
    """Every entry below ``root`` outside ``.git``: a file's bytes, a link's target, or None."""
    found: dict[str, object] = {}
    for directory, directories, filenames in os.walk(root):
        directories[:] = sorted(name for name in directories if name != ".git")
        for name in (*directories, *filenames):
            if name == ".git":
                continue
            path = Path(directory, name)
            key = path.relative_to(root).as_posix()
            if path.is_symlink():
                found[key] = ("link", os.readlink(path))
            elif path.is_file():
                found[key] = path.read_bytes()
            else:
                found[key] = None
    return found


def _manifest_path(repo: Path, scope: tuple[str, str, str]) -> Path:
    return repo / ".axiom" / "ingest-manifests" / scope[0] / scope[1] / f"{scope[2]}.json"


def _repair_checkout(
    make_checkout: MakeCheckout, name: str, *, bases: tuple[tuple[str, str, str], ...] = (BV1,)
) -> Path:
    """Build checkout ``name``: ``us-plain`` lists pv1 and ``us-layered`` marks ``bases``."""
    selectors: dict[str, Mapping[str, object]] = {
        "us-plain": {"name": "us-plain", "scopes": [_row(PV1)]}
    }
    if bases:
        selectors["us-layered"] = {
            "name": "us-layered",
            "scopes": [_row(QV1), *(_row(scope, layer="base") for scope in bases)],
        }
    checkout = make_checkout(name, selectors)
    (checkout / "SIGNING-COMMANDS.md").write_text("sign_scope us statute pv1\n")
    return checkout


def _write_repair_scopes(corpus: Path, repo: Path) -> None:
    """Write pv1, which an audit repairs, and bv1, with their ingest manifests in ``repo``."""
    _write_scope_files(
        corpus, PV1, [{**row, "version": "pv1"} for row in NEEDS_REPAIR], sources=True
    )
    _write_scope_files(
        corpus, BV1, [{**row, "version": "bv1"} for row in SELF_CONTAINED], sources=True
    )
    for scope in (PV1, BV1):
        manifest = _manifest_path(repo, scope)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"applied_files": [], "version": scope[2]}) + "\n")


def _repair_argv(
    monkeypatch: pytest.MonkeyPatch, repo: Path, release: Path, report: Path
) -> list[str]:
    """Point ``main()`` at ``repo`` and stub the fetch, which records ``"fetch"``."""
    events: list[str] = []
    monkeypatch.setattr(
        repair_module,
        "ensure_corpus_scopes",
        lambda scopes, *, repo: events.append("fetch"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repair_plan_cascade_self_containment.py",
            "--audit-residuals",
            "--repo",
            str(repo),
            "--release",
            str(release),
            "--suffix",
            "fix",
            "--report",
            str(report),
        ],
    )
    return events


def _swap_for_link(path: Path, target: Path) -> None:
    """Replace the directory ``path`` with a symlink to ``target``, then forget cached roots."""
    from axiom_corpus.corpus import resolver

    shutil.rmtree(path)
    path.symlink_to(target, target_is_directory=True)
    resolver._repo_root_for_dir.cache_clear()


def _relink(path: Path, target: Path, *, hard: bool = False) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    if hard:
        os.link(target, path)
    else:
        path.symlink_to(target)


@pytest.mark.parametrize(
    "case",
    [
        "destination-provisions-link",
        "destination-inventory-link",
        "destination-coverage-link",
        "destination-ingest-manifest-link",
        "linked-corpus",
        "working-directory-checkout",
        "existing-destination",
        "source-symlink",
        "source-hard-link",
        "tracked-base-file-links-to-repaired",
        "tracked-base-sources-link",
        "tracked-base-ingest-manifest-link",
        "release-base-links-to-repaired",
        "existing-destination-ingest-manifest",
        "dangling-destination-link",
        "nested-source-symlink",
        "holder-base-links-to-repaired",
        "release-held-by-another-checkout",
        "repo-releases-link",
        "repo-manifests-link",
        "file-chain-holder-marks-repaired",
        "tracked-base-sources-entry-to-moved-parent",
    ],
)
def test_main_refuses_a_repair_through_a_link_or_of_a_base_another_checkout_marks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_checkout: MakeCheckout, case: str
) -> None:
    monkeypatch.chdir(tmp_path)
    release = PLAIN_RELEASE
    never_created: Path | None = None
    if case == "linked-corpus":
        # A's corpus is B's, and only B marks pv1 as a base.
        repo = _repair_checkout(make_checkout, "a", bases=())
        b = _repair_checkout(make_checkout, "b", bases=(PV1,))
        _write_repair_scopes(b / "data" / "corpus", repo)
        (repo / "data").mkdir()
        (repo / "data" / "corpus").symlink_to(b / "data" / "corpus")
        expected = _exactly(
            "base scopes are carried unchanged and cannot be repaired: us/statute/pv1"
        )
    elif case == "working-directory-checkout":
        # The working directory is a worktree whose branch marks pv1 as a base;
        # --repo is the main checkout and --release lies outside every checkout.
        repo = _repair_checkout(make_checkout, "m", bases=())
        _write_repair_scopes(repo / "data" / "corpus", repo)
        worktree = tmp_path / "wt"
        fixture_git(repo, "worktree", "add", "-q", "-b", "feat", str(worktree))
        (worktree / "manifests" / "releases" / "us-layered.json").write_text(
            json.dumps(
                {"name": "us-layered", "scopes": [_row(QV1), _row(PV1, layer="base")]},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        fixture_git(worktree, "add", "--", "manifests")
        fixture_git(worktree, "commit", "-q", "-m", "Mark pv1 as a base")
        release = tmp_path / "release.json"
        release.write_text(json.dumps(_payload(_row(PV1))) + "\n")
        monkeypatch.chdir(worktree)
        expected = _exactly(
            "base scopes are carried unchanged and cannot be repaired: us/statute/pv1"
        )
    elif case == "dangling-destination-link":
        # pv1-fix's provisions in A is a dangling link to the same path in B;
        # the guard refuses a symlinked file at a guarded place before repair
        # checks for an existing destination.
        repo = _repair_checkout(make_checkout, "a", bases=())
        b = _repair_checkout(make_checkout, "b", bases=())
        _write_repair_scopes(repo / "data" / "corpus", repo)
        never_created = repair_module._scope_paths(b / "data" / "corpus", PV1_FIX)["provisions"]
        never_created.parent.mkdir(parents=True)
        link = repair_module._scope_paths(repo / "data" / "corpus", PV1_FIX)["provisions"]
        link.symlink_to(never_created)
        expected = _exactly(
            "path leads through a symlinked file at or below a checkout's guarded place: "
            f"{link} (the link is {link}); corpus files are placed as regular files, "
            "never symlinks"
        )
    elif case == "file-chain-holder-marks-repaired":
        # Only B marks pv1 as a base. A's pv1 files link to B's, and B's to
        # C's, which C holds as regular files.
        repo = _repair_checkout(make_checkout, "a", bases=())
        b = _repair_checkout(make_checkout, "b", bases=(PV1,))
        c = _repair_checkout(make_checkout, "c", bases=())
        corpora = [x / "data" / "corpus" for x in (repo, b, c)]
        for corpus in corpora:
            _write_repair_scopes(corpus, repo)
        for here, there in ((corpora[0], corpora[1]), (corpora[1], corpora[2])):
            for kind in ("coverage", "inventory", "provisions"):
                _relink(
                    repair_module._scope_paths(here, PV1)[kind],
                    repair_module._scope_paths(there, PV1)[kind],
                )
        from axiom_corpus.corpus import resolver

        resolver._repo_root_for_dir.cache_clear()
        link = repair_module._scope_paths(corpora[0], PV1)["coverage"]
        expected = _exactly(
            "path leads through a symlinked file at or below a checkout's guarded place: "
            f"{link} (the link is {link}); corpus files are placed as regular files, "
            "never symlinks"
        )
    elif case == "holder-base-links-to-repaired":
        # A's corpus is B's; only B marks bv1, whose provisions lead to pv1's,
        # which repair unlinks.
        repo = _repair_checkout(make_checkout, "a", bases=())
        b = _repair_checkout(make_checkout, "b", bases=(BV1,))
        _write_repair_scopes(b / "data" / "corpus", repo)
        (repo / "data").mkdir()
        (repo / "data" / "corpus").symlink_to(b / "data" / "corpus")
        _relink(
            repair_module._scope_paths(b / "data" / "corpus", BV1)["provisions"],
            repair_module._scope_paths(b / "data" / "corpus", PV1)["provisions"],
        )
        old_provisions = repair_module._scope_paths(repo / "data" / "corpus", PV1)["provisions"]
        expected = _exactly(f"{old_provisions} is also us/statute/bv1's provisions through a link")
    elif case == "release-held-by-another-checkout":
        # --release lies in B, which marks pv1 as a base; --repo is A, and the
        # working directory lies outside every checkout.
        repo = _repair_checkout(make_checkout, "a", bases=())
        b = _repair_checkout(make_checkout, "b", bases=(PV1,))
        _write_repair_scopes(repo / "data" / "corpus", repo)
        release = b / PLAIN_RELEASE
        expected = _exactly(
            "base scopes are carried unchanged and cannot be repaired: us/statute/pv1"
        )
    elif case in ("repo-releases-link", "repo-manifests-link"):
        # --repo A commits a selector marking pv1 as a base; on disk A's selector
        # directory leads to B's, which marks nothing, and --release lies outside.
        repo = _repair_checkout(make_checkout, "a", bases=(PV1,))
        b = _repair_checkout(make_checkout, "b", bases=())
        _write_repair_scopes(repo / "data" / "corpus", repo)
        link = repo / "manifests"
        if case == "repo-releases-link":
            link = link / "releases"
        _swap_for_link(link, b / link.relative_to(repo))
        release = tmp_path / "release.json"
        release.write_text(json.dumps(_payload(_row(PV1))) + "\n")
        expected = "^" + re.escape(f"selector directory leads through a link: {link} -> ")
    else:
        repo = _repair_checkout(make_checkout, "c")
        corpus = repo / "data" / "corpus"
        _write_repair_scopes(corpus, repo)
        old = repair_module._scope_paths(corpus, PV1)
        new = repair_module._scope_paths(corpus, PV1_FIX)
        base = repair_module._scope_paths(corpus, BV1)
        if case in (
            "destination-provisions-link",
            "destination-inventory-link",
            "destination-coverage-link",
        ):
            # pv1-fix's file is already a link to bv1's.
            kind = case.removeprefix("destination-").removesuffix("-link")
            new[kind].parent.mkdir(parents=True, exist_ok=True)
            new[kind].symlink_to(base[kind])
            expected = "^scope artifact resolves to another path: " + re.escape(f"{new[kind]} -> ")
        elif case == "destination-ingest-manifest-link":
            link = _manifest_path(repo, PV1_FIX)
            link.symlink_to(_manifest_path(repo, BV1))
            expected = "^scope artifact resolves to another path: " + re.escape(f"{link} -> ")
        elif case == "existing-destination":
            new["coverage"].write_text(json.dumps({"complete": True}) + "\n")
            expected = _exactly(f"repaired scope artifact already exists: {new['coverage']}")
        elif case == "source-symlink":
            _relink(old["sources"] / "source.html", base["sources"] / "source.html")
            expected = _exactly(f"source directory contains a symlink: {old['sources']}")
        elif case == "source-hard-link":
            _relink(old["sources"] / "source.html", base["sources"] / "source.html", hard=True)
            expected = _exactly(
                "scope artifact shares its file with another path: "
                f"{old['sources'] / 'source.html'} (2 links)"
            )
        elif case == "tracked-base-file-links-to-repaired":
            # Repair unlinks pv1's provisions, where bv1's provisions lead.
            _relink(base["provisions"], old["provisions"])
            expected = _exactly(
                f"{old['provisions']} is also us/statute/bv1's provisions through a link"
            )
        elif case == "tracked-base-sources-link":
            # Repair moves pv1's sources, where bv1's sources lead.
            _relink(base["sources"], old["sources"])
            expected = _exactly(f"{old['sources']} is also us/statute/bv1's sources through a link")
        elif case == "tracked-base-sources-entry-to-moved-parent":
            # A link below bv1's sources leads to the directory that holds
            # pv1's sources, which repair moves.
            (base["sources"] / "alias").symlink_to(corpus / "sources" / "us" / "statute")
            expected = _exactly(f"{old['sources']} is also us/statute/bv1's sources through a link")
        elif case == "tracked-base-ingest-manifest-link":
            _relink(_manifest_path(repo, BV1), _manifest_path(repo, PV1))
            expected = _exactly(
                f"{_manifest_path(repo, PV1)} is also us/statute/bv1's ingest manifest "
                "through a link"
            )
        elif case == "release-base-links-to-repaired":
            # No tracked selector marks bv2; the release marks it, and its
            # coverage leads to pv1's, which repair unlinks.
            _write_scope_files(
                corpus, BV2, [{**row, "version": "bv2"} for row in SELF_CONTAINED], sources=True
            )
            _relink(repair_module._scope_paths(corpus, BV2)["coverage"], old["coverage"])
            release = Path("repair") / "release.json"
            (repo / release).parent.mkdir()
            (repo / release).write_text(
                json.dumps(_payload(_row(PV1), _row(BV2, layer="base"))) + "\n"
            )
            expected = _exactly(
                f"{old['coverage']} is also us/statute/bv2's coverage through a link"
            )
        elif case == "existing-destination-ingest-manifest":
            # pv1-fix's ingest manifest exists as a plain file.
            manifest = _manifest_path(repo, PV1_FIX)
            manifest.write_text(json.dumps({"applied_files": [], "version": "pv1-fix"}) + "\n")
            expected = _exactly(f"repaired scope artifact already exists: {manifest}")
        elif case == "nested-source-symlink":
            # A link below a subdirectory of pv1's sources leads to bv1's source,
            # which quotes pv1 and so would be rewritten after the move.
            base_source = base["sources"] / "source.html"
            base_source.write_text("<p>bv1 quotes pv1</p>\n")
            nested = old["sources"] / "sub" / "inner.html"
            nested.parent.mkdir()
            nested.symlink_to(base_source)
            expected = _exactly(f"source directory contains a symlink: {old['sources']}")
        else:
            raise AssertionError(case)
    report = tmp_path / "report.json"
    events = _repair_argv(monkeypatch, repo, release, report)
    before = _snapshot(tmp_path)

    with pytest.raises(ValueError, match=expected):
        repair_module.main()

    # The repair was planned, and nothing in any checkout was moved, written or unlinked.
    assert events == ["fetch"]
    assert _snapshot(tmp_path) == before
    assert not report.exists()
    if never_created is not None:
        assert not os.path.lexists(never_created)


@pytest.mark.parametrize("case", ["plain", "linked-corpus-without-a-base"])
def test_main_repairs_beside_a_base_no_link_reaches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_checkout: MakeCheckout, case: str
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = _repair_checkout(make_checkout, "c")
    corpus = repo / "data" / "corpus"
    if case == "plain":
        _write_repair_scopes(corpus, repo)
    else:
        # A shared corpus in a checkout that marks no base of the repair.
        b = _repair_checkout(make_checkout, "b", bases=())
        _write_repair_scopes(b / "data" / "corpus", repo)
        (repo / "data").mkdir()
        corpus.symlink_to(b / "data" / "corpus")
    base_files = {
        kind: path.read_bytes()
        for kind, path in repair_module._scope_paths(corpus, BV1).items()
        if kind != "sources"
    }
    report = tmp_path / "report.json"
    events = _repair_argv(monkeypatch, repo, PLAIN_RELEASE, report)

    assert repair_module.main() == 0

    assert events == ["fetch"]
    new = repair_module._scope_paths(corpus, PV1_FIX)
    assert all(path.exists() for path in new.values())
    assert _manifest_path(repo, PV1_FIX).is_file()
    assert not any(path.exists() for path in repair_module._scope_paths(corpus, PV1).values())
    assert {
        kind: path.read_bytes()
        for kind, path in repair_module._scope_paths(corpus, BV1).items()
        if kind != "sources"
    } == base_files
    assert json.loads(report.read_text())["scopes_repaired"] == [list(PV1_FIX)]


# Finding 5 of round 2: repair's --report path. The repository holds a
# self-contained primary scope, so the audit repairs nothing and reaches the
# report write, and ``us-example-layered`` marks ``REPORT_BASE`` as a base.
REPORT_BASE = ("us-example", "regulation", "base-v")
LAYERED_RELEASE = Path("manifests") / "releases" / "us-example-layered.json"


def _layered_selector() -> dict[str, object]:
    return {
        "name": "us-example-layered",
        "scopes": [_row(PRIMARY), _row(REPORT_BASE, layer="base")],
    }


def _write_report_repo(repo: Path) -> None:
    corpus = repo / "data" / "corpus"
    _write_scope_files(corpus, PRIMARY, [{"citation_path": "us-example/statute/1"}], sources=True)
    _write_scope_files(
        corpus, REPORT_BASE, [{"citation_path": "us-example/regulation/1"}], sources=True
    )
    selector = repo / LAYERED_RELEASE
    selector.parent.mkdir(parents=True)
    selector.write_text(json.dumps(_layered_selector(), indent=2, sort_keys=True) + "\n")
    lock = repo / ".axiom" / "corpus-locks" / "us-example" / "regulation" / "base-v.json"
    lock.parent.mkdir(parents=True)
    lock.write_text(json.dumps({"files": []}) + "\n")
    (repo / "SIGNING-COMMANDS.md").write_text("sign_scope us-example statute primary-v\n")


def _base_coverage(corpus: Path, version: str = "base-v") -> Path:
    return corpus / "coverage" / "us-example" / "regulation" / f"{version}.json"


def _report_argv(
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
    report: Path | str,
    *,
    release: Path = LAYERED_RELEASE,
    conflicts: Path | None = None,
    fetch: Callable[[], None] | None = None,
) -> list[str]:
    """Point ``main()`` at ``repo``; the fetch stub records ``"fetch"``, then runs ``fetch``."""
    events: list[str] = []

    def fetched(scopes: object, *, repo: Path) -> None:
        events.append("fetch")
        if fetch is not None:
            fetch()

    monkeypatch.setattr(repair_module, "ensure_corpus_scopes", fetched)
    source = ["--conflicts", str(conflicts)] if conflicts is not None else ["--audit-residuals"]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repair_plan_cascade_self_containment.py",
            *source,
            "--repo",
            str(repo),
            "--release",
            str(release),
            "--report",
            str(report),
        ],
    )
    return events


def _case_insensitive(directory: Path) -> bool:
    probe = directory / "Case-Probe"
    probe.mkdir()
    try:
        return (directory / "case-probe").exists()
    finally:
        probe.rmdir()


# A name in NFC and in NFD, built from code points so the source stays ASCII.
NFC_NAME = "out-caf" + chr(0xE9)
NFD_NAME = "out-cafe" + chr(0x301)
FIRMLINK_ROOT = Path("/System/Volumes/Data")
# The report rule's places, spelled out here so that a place dropped from
# ``PLACES`` turns its rows red instead of removing them.
REPORT_PLACES = (
    "data",
    "data/corpus",
    "data/corpus/coverage",
    "data/corpus/inventory",
    "data/corpus/provisions",
    "data/corpus/sources",
    ".axiom",
    ".axiom/ingest-manifests",
    ".axiom/corpus-locks",
    "manifests",
    "manifests/releases",
)
PLACE_BY_LABEL = {place.replace("/", "-").lstrip("."): place for place in REPORT_PLACES}


def _normalization_insensitive(directory: Path) -> bool:
    probe = directory / NFC_NAME
    probe.mkdir()
    try:
        return (directory / NFD_NAME).exists()
    finally:
        probe.rmdir()


def _firmlink_spelling(path: Path) -> Path | None:
    """``path`` spelled through ``/System/Volumes/Data``, when that names the same entry."""
    real = Path(os.path.realpath(path))
    spelled = FIRMLINK_ROOT / real.relative_to(real.anchor)
    try:
        return spelled if os.path.samefile(spelled, path) else None
    except OSError:
        return None


def _link_place(path: Path, target: Path) -> None:
    """Make ``path`` a symlink to ``target``, removing whatever stood there."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif os.path.lexists(path):
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target)


@pytest.mark.parametrize(
    "case",
    [
        "coverage",
        "selector",
        "symlink-alias",
        "case-variant",
        "dotdot",
        "relative-cwd",
        "absent-base",
        "dir-link",
        "other-checkout",
        "other-sparse-checkout",
        "linked-corpus-target",
        "other-checkout-linked-corpus",
        "dangling-link-into-repo",
        "new-file-in-releases",
        "lock-file",
        "class-place-linked-out",
        "lock-place-linked-out",
        "case-variant-absent-place",
        "report-through-guarded-file-link",
        *(f"dangling-{label}" for label in PLACE_BY_LABEL),
        "dangling-spelled-through-link",
        "dangling-relative-target",
        "dangling-chain",
        "dangling-target-parents-absent",
        "dangling-target-case-variant",
        "dangling-target-nfd",
        "dangling-target-firmlink",
        "dangling-place-of-physical-holder",
        "dangling-class-place-other-checkout",
        "firmlink-absent-data",
        "firmlink-absent-axiom",
        "firmlink-case-absent-data",
        "upper-root-exact-absent-data",
        "upper-root-exact-absent-axiom",
        "upper-root-exact-absent-manifests",
        *(
            f"linked-out-{label}"
            for label in PLACE_BY_LABEL
            if label not in ("data-corpus-coverage", "axiom-corpus-locks")
        ),
    ],
)
def test_main_refuses_a_report_path_in_a_protected_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_checkout: MakeCheckout, case: str
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    _write_report_repo(repo)
    coverage = _base_coverage(repo / "data" / "corpus")
    root, place = repo, "data"
    report: Path
    fetch: Callable[[], None] | None = None
    expected: str | None = None
    if case == "coverage":
        report = coverage
    elif case == "selector":
        report, place = repo / LAYERED_RELEASE, "manifests"
    elif case == "symlink-alias":
        report = tmp_path / "alias.json"
        report.symlink_to(coverage)
    elif case == "case-variant":
        if not _case_insensitive(tmp_path):
            pytest.skip("the filesystem tells letter case apart")
        report = repo / "DATA" / "corpus" / "coverage" / "us-example" / "regulation" / "BASE-V.json"
    elif case == "dotdot":
        (tmp_path / "x").mkdir()
        report = tmp_path / "x" / ".." / "repo" / coverage.relative_to(repo)
    elif case == "relative-cwd":
        monkeypatch.chdir(repo)
        report = coverage.relative_to(repo)
    elif case == "absent-base":
        coverage.unlink()
        report = coverage
    elif case == "dir-link":
        (tmp_path / "covdir").symlink_to(coverage.parent)
        report = tmp_path / "covdir" / "base-v.json"
    elif case in ("other-checkout", "other-sparse-checkout"):
        root = make_checkout("b", {"us-example-layered": _layered_selector()})
        if case == "other-sparse-checkout":
            fixture_git(root, "sparse-checkout", "set", "--no-cone", "/*", "!/src/", "!/.axiom/")
            from axiom_corpus.corpus import resolver

            resolver._repo_root_for_dir.cache_clear()
            assert not (root / "src").exists()
        report = _base_coverage(root / "data" / "corpus")
        report.parent.mkdir(parents=True)
        report.write_text(json.dumps({"complete": True, "version": "base-v"}) + "\n")
    elif case == "linked-corpus-target":
        # --repo's data/corpus leads to a directory outside every checkout.
        shared = tmp_path / "shared-corpus"
        (repo / "data" / "corpus").rename(shared)
        (repo / "data" / "corpus").symlink_to(shared)
        report, place = _base_coverage(shared), "data/corpus"
    elif case == "other-checkout-linked-corpus":
        # B marks the base and its data/corpus leads to a directory where the
        # base was never fetched.
        root = make_checkout("b", {"us-example-layered": _layered_selector()})
        shared = tmp_path / "shared"
        (shared / "coverage" / "us-example" / "regulation").mkdir(parents=True)
        (root / "data").mkdir()
        (root / "data" / "corpus").symlink_to(shared)
        report, place = _base_coverage(root / "data" / "corpus"), "data/corpus"
    elif case == "dangling-link-into-repo":
        report, place = tmp_path / "dangle.json", "manifests"
        report.symlink_to(repo / "manifests" / "releases" / "new.json")
    elif case == "new-file-in-releases":
        report, place = repo / "manifests" / "releases" / "report.json", "manifests"
    elif case == "lock-file":
        report = repo / ".axiom" / "corpus-locks" / "us-example" / "regulation" / "base-v.json"
        place = ".axiom"
    elif case in ("class-place-linked-out", "lock-place-linked-out"):
        # The place itself links to a directory outside every checkout, and the
        # report is spelled there: a new file the checkout reads in that place.
        if case == "class-place-linked-out":
            place, out = "data/corpus/coverage", tmp_path / "out-cov"
        else:
            place, out = ".axiom/corpus-locks", tmp_path / "out-locks"
        (repo / place).rename(out)
        (repo / place).symlink_to(out)
        report = out / "us-example" / "regulation" / "new-v.json"
    elif case == "case-variant-absent-place":
        if not _case_insensitive(tmp_path):
            pytest.skip("the filesystem tells letter case apart")
        # Nothing is fetched yet, so no place exists to compare by identity;
        # the fetch would create data/, where the report spelled Data/ lands.
        shutil.rmtree(repo / "data")

        def fetch_scopes() -> None:
            corpus = repo / "data" / "corpus"
            _write_scope_files(
                corpus, PRIMARY, [{"citation_path": "us-example/statute/1"}], sources=True
            )
            _write_scope_files(
                corpus, REPORT_BASE, [{"citation_path": "us-example/regulation/1"}], sources=True
            )

        fetch = fetch_scopes
        report = _base_coverage(repo / "Data" / "corpus", "never-fetched")
    elif case == "report-through-guarded-file-link":
        # The base's coverage is a link out of the checkout, which the resolver
        # recognises by its corpus locks at a git toplevel; the report is
        # spelled through it.
        fixture_git(repo, "init", "-q", "-b", "main")
        from axiom_corpus.corpus import resolver

        resolver._repo_root_for_dir.cache_clear()
        target = tmp_path / "out" / "target.json"
        target.parent.mkdir()
        target.write_text(json.dumps({"complete": True, "version": "base-v"}) + "\n")
        coverage.unlink()
        coverage.symlink_to(target)
        report = coverage
        expected = (
            "path leads through a symlinked file at or below a checkout's guarded place: "
            f"{coverage} (the link is {coverage}); corpus files are placed as regular files, "
            "never symlinks"
        )
    elif case.startswith("dangling-") and case.removeprefix("dangling-") in PLACE_BY_LABEL:
        # The place is a dangling link out of every checkout, and the report
        # is spelled where it leads: a file the checkout would read there.
        place = PLACE_BY_LABEL[case.removeprefix("dangling-")]
        out = tmp_path / f"out-{REPORT_PLACES.index(place)}"
        _link_place(repo / place, out)
        report = out / "us-example" / "regulation" / "base-v.json"
    elif case in (
        "dangling-spelled-through-link",
        "dangling-relative-target",
        "dangling-chain",
        "dangling-target-parents-absent",
        "dangling-target-case-variant",
        "dangling-target-nfd",
        "dangling-target-firmlink",
    ):
        place = "data/corpus/coverage"
        outside = tmp_path / "outside-cov"
        target: Path = outside
        if case == "dangling-relative-target":
            target = Path("..", "..", "..", "outside-cov")
        elif case == "dangling-chain":
            (tmp_path / "hop").symlink_to(outside)
            target = tmp_path / "hop"
        elif case == "dangling-target-parents-absent":
            outside = target = tmp_path / "a" / "b" / "c"
        elif case == "dangling-target-case-variant":
            if not _case_insensitive(tmp_path):
                pytest.skip("the filesystem tells letter case apart")
            target = tmp_path / "OUTSIDE-COV"
        elif case == "dangling-target-nfd":
            if not _normalization_insensitive(tmp_path):
                pytest.skip("the filesystem tells NFC and NFD apart")
            target, outside = tmp_path / NFC_NAME, tmp_path / NFD_NAME
        elif case == "dangling-target-firmlink":
            firm = _firmlink_spelling(tmp_path)
            if firm is None:
                pytest.skip("no /System/Volumes/Data spelling of the test directory")
            target = firm / "outside-cov"
        _link_place(repo / place, target)
        top = repo / place if case == "dangling-spelled-through-link" else outside
        report = top / "us-example" / "regulation" / "base-v.json"
    elif case == "dangling-place-of-physical-holder":
        # B physically holds the report, and B's .axiom dangles to it.
        root = make_checkout("b", {"us-example-layered": _layered_selector()})
        (root / ".axiom").symlink_to(root / "ax-out")
        report, place = root / "ax-out" / "x.json", ".axiom"
    elif case == "dangling-class-place-other-checkout":
        # B holds a link on the report as spelled: B's coverage dangles.
        root = make_checkout("b", {"us-example-layered": _layered_selector()})
        (root / "data" / "corpus").mkdir(parents=True)
        (root / "data" / "corpus" / "coverage").symlink_to(tmp_path / "outside-cov")
        report, place = _base_coverage(root / "data" / "corpus"), "data/corpus/coverage"
    elif case in ("firmlink-absent-data", "firmlink-absent-axiom", "firmlink-case-absent-data"):
        firm = _firmlink_spelling(repo)
        if firm is None:
            pytest.skip("no /System/Volumes/Data spelling of the test directory")
        if case == "firmlink-case-absent-data" and not _case_insensitive(tmp_path):
            pytest.skip("the filesystem tells letter case apart")
        place = ".axiom" if case == "firmlink-absent-axiom" else "data"
        shutil.rmtree(repo / place)
        if case == "firmlink-absent-axiom":
            report = firm / ".axiom" / "corpus-locks" / "us-example" / "regulation" / "never.json"
        else:
            spelled_data = "DATA" if case == "firmlink-case-absent-data" else "data"
            report = _base_coverage(firm / spelled_data / "corpus", "never-fetched")
    elif case.startswith("upper-root-exact-absent-"):
        # The checkout's path holds capitals, and the place does not exist yet.
        repo = root = tmp_path / "Upper" / "repo"
        _write_report_repo(repo)
        place = {"data": "data", "axiom": ".axiom", "manifests": "manifests"}[
            case.removeprefix("upper-root-exact-absent-")
        ]
        shutil.rmtree(repo / place)
        if place == "data":
            report = _base_coverage(repo / "data" / "corpus", "never-fetched")
        elif place == ".axiom":
            report = repo / ".axiom" / "corpus-locks" / "us-example" / "regulation" / "never.json"
        else:
            report = repo / "manifests" / "releases" / "new-selector.json"
    elif case.startswith("linked-out-"):
        # The place links to a directory outside every checkout, and the report
        # is a new file there.
        place = PLACE_BY_LABEL[case.removeprefix("linked-out-")]
        out = tmp_path / f"out-{REPORT_PLACES.index(place)}"
        if (repo / place).exists():
            (repo / place).rename(out)
        else:
            out.mkdir()
        (repo / place).symlink_to(out)
        report = out / "us-example" / "regulation" / "new-v.json"
    else:
        raise AssertionError(case)
    spelled = report if report.is_absolute() else Path.cwd() / report
    events = _report_argv(monkeypatch, repo, report, fetch=fetch)
    before = _snapshot(tmp_path)

    with pytest.raises(ValueError) as raised:
        repair_module.main()

    assert str(raised.value) == (
        expected or f"report path resolves into {place} of the checkout {root}: {spelled}"
    )
    assert events == []
    assert _snapshot(tmp_path) == before


# The keys main() writes, spelled out here rather than read from REPORT_KEYS.
WRITTEN_KEYS = (
    "assertion",
    "cascade_parent_paths",
    "conflict_rows",
    "rows_added",
    "scopes_repaired",
    "scopes_repaired_count",
)


def _main_within(seconds: float, *, fifo: Path | None = None) -> object:
    """Run ``main()`` in a daemon thread: its return value, its exception, or "timeout".

    On a timeout, both ends of ``fifo`` are opened without blocking, so a thread
    stuck opening it returns.
    """
    outcome: list[object] = []

    def run() -> None:
        try:
            outcome.append(repair_module.main())
        except BaseException as exc:  # noqa: BLE001 - the test inspects it
            outcome.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(seconds)
    if not thread.is_alive():
        return outcome[0]
    if fifo is not None:
        for flags in (os.O_RDONLY | os.O_NONBLOCK, os.O_WRONLY | os.O_NONBLOCK):
            with contextlib.suppress(OSError):
                os.close(os.open(fifo, flags))
        thread.join(5)
    return "timeout"


@pytest.mark.parametrize(
    "case",
    [
        "conflicts-is-report",
        "outside-release-is-report",
        "hardlink",
        "outside-symlink",
        "dangling-final-symlink",
        "directory",
        "dev-null",
        "fifo",
    ],
)
def test_main_refuses_a_report_path_that_is_an_input_or_not_a_plain_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    _write_report_repo(repo)
    coverage = _base_coverage(repo / "data" / "corpus")
    release = LAYERED_RELEASE
    conflicts: Path | None = None
    fifo: Path | None = None
    report = tmp_path / "out" / "report.json"
    report.parent.mkdir()
    if case == "conflicts-is-report":
        conflicts = report
        conflicts.write_text("[]\n")
        expected = f"report path is the --conflicts file this run reads: {report}"
    elif case == "outside-release-is-report":
        release = report
        release.write_bytes((repo / LAYERED_RELEASE).read_bytes())
        expected = f"report path is the --release file this run reads: {report}"
    elif case == "hardlink":
        os.link(coverage, report)
        expected = f"report path is a file with another hard link: {report}"
    elif case == "outside-symlink":
        (tmp_path / "out" / "target.json").write_text("{}\n")
        report.symlink_to(tmp_path / "out" / "target.json")
        expected = f"report path is a symlink: {report}"
    elif case == "dangling-final-symlink":
        report.symlink_to(tmp_path / "out" / "missing.json")
        expected = f"report path is a symlink: {report}"
    elif case == "directory":
        report.mkdir()
        expected = f"report path is a directory: {report}"
    elif case == "dev-null":
        report = Path("/dev/null")
        expected = "report path is not a regular file: /dev/null"
    elif case == "fifo":
        fifo = report
        os.mkfifo(fifo)
        expected = f"report path is not a regular file: {report}"
    else:
        raise AssertionError(case)
    events = _report_argv(monkeypatch, repo, report, release=release, conflicts=conflicts)
    before = _snapshot(tmp_path)

    result = _main_within(10, fifo=fifo)

    assert isinstance(result, ValueError), result
    assert str(result) == expected
    assert events == []
    assert _snapshot(tmp_path) == before
    assert not (tmp_path / "out" / "missing.json").exists()


@pytest.mark.parametrize(
    "case",
    [
        "deep-dir-link",
        "deep-file-link",
        "foreign-json",
        "report-keys-plus-one",
        "not-json",
        "empty-object",
        "report-minus-one",
        "renamed-key",
    ],
)
def test_main_refuses_a_report_path_that_holds_another_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    _write_report_repo(repo)
    corpus = repo / "data" / "corpus"
    out = tmp_path / "out"
    out.mkdir()
    if case == "deep-dir-link":
        # The base's coverage as the checkout reads it lies outside every checkout.
        (corpus / "coverage" / "us-example").rename(out / "us-example")
        (corpus / "coverage" / "us-example").symlink_to(out / "us-example")
        report = out / "us-example" / "regulation" / "base-v.json"
    elif case == "deep-file-link":
        inventory = corpus / "inventory" / "us-example" / "regulation" / "base-v.json"
        inventory.rename(out / "base-v.json")
        inventory.symlink_to(out / "base-v.json")
        report = out / "base-v.json"
    elif case == "foreign-json":
        report = out / "notes.json"
        report.write_text(json.dumps({"a": 1}) + "\n")
    elif case == "report-keys-plus-one":
        report = out / "report.json"
        keys = (
            "assertion",
            "cascade_parent_paths",
            "conflict_rows",
            "rows_added",
            "scopes_repaired",
            "scopes_repaired_count",
            "extra",
        )
        report.write_text(json.dumps(dict.fromkeys(keys, 0)) + "\n")
    elif case == "not-json":
        report = out / "notes.txt"
        report.write_text("not a report\n")
    elif case == "empty-object":
        report = out / "notes.json"
        report.write_text("{}\n")
    elif case in ("report-minus-one", "renamed-key"):
        # Five of the report's six keys, or all six with one renamed.
        report = out / "report.json"
        keys = [key for key in WRITTEN_KEYS if key != "rows_added"]
        if case == "renamed-key":
            keys.append("rows_removed")
        report.write_text(json.dumps(dict.fromkeys(keys, 0)) + "\n")
    else:
        raise AssertionError(case)
    events = _report_argv(monkeypatch, repo, report)
    before = _snapshot(tmp_path)

    with pytest.raises(ValueError) as raised:
        repair_module.main()

    assert str(raised.value) == f"report path holds a file this script did not write: {report}"
    assert events == []
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "case",
    [
        "fetched-through-deep-link",
        "link-planted-during-fetch",
        "write-time-place-relinked",
        "write-time-dangling-axiom",
        "write-time-directory-relinked",
        "write-time-holder-place-relinked",
        "write-time-holder-appears",
    ],
)
def test_the_report_write_refuses_what_appeared_during_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_checkout: MakeCheckout, case: str
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    _write_report_repo(repo)
    corpus = repo / "data" / "corpus"
    base_bytes = json.dumps({"complete": True, "version": "base-w"}).encode() + b"\n"
    # Paths that must not exist after the refusal: the report and what its write would make.
    absent: list[Path] = []
    if case == "fetched-through-deep-link":
        # base-w is unfetched at the check; the fetch writes its coverage
        # through the checkout's link, at the report path.
        out = tmp_path / "out"
        out.mkdir()
        (corpus / "coverage" / "us-example").rename(out / "us-example")
        (corpus / "coverage" / "us-example").symlink_to(out / "us-example")
        base = _base_coverage(corpus, "base-w")
        report = out / "us-example" / "regulation" / "base-w.json"

        def fetch() -> None:
            base.write_bytes(base_bytes)

        expected = f"report path holds a file this script did not write: {report}"
    elif case == "link-planted-during-fetch":
        base = _base_coverage(corpus)
        base_bytes = base.read_bytes()
        report = tmp_path / "out-e" / "report.json"
        report.parent.mkdir()

        def fetch() -> None:
            report.symlink_to(base)

        expected = f"report path is a symlink: {report}"
    elif case == "write-time-place-relinked":
        # The fetch turns repo's coverage into a link to the report's directory.
        base = _base_coverage(corpus)
        base_bytes = base.read_bytes()
        report = tmp_path / "out-w" / "r.json"

        def fetch() -> None:
            (corpus / "coverage").rename(report.parent)
            (corpus / "coverage").symlink_to(report.parent)

        expected = (
            f"report path resolves into data/corpus/coverage of the checkout {repo}: {report}"
        )
        absent = [report]
    elif case == "write-time-dangling-axiom":
        # The fetch replaces repo's .axiom with a link to where the report would go.
        base = _base_coverage(corpus)
        base_bytes = base.read_bytes()
        report = tmp_path / "ax-out" / "corpus-locks" / "us-example" / "regulation" / "base-v.json"

        def fetch() -> None:
            shutil.rmtree(repo / ".axiom")
            (repo / ".axiom").symlink_to(tmp_path / "ax-out")

        expected = f"report path resolves into .axiom of the checkout {repo}: {report}"
        absent = [report, tmp_path / "ax-out"]
    elif case == "write-time-directory-relinked":
        # The report's directory is a directory at the check; the fetch turns
        # it into a dangling link.
        base = _base_coverage(corpus)
        base_bytes = base.read_bytes()
        report = tmp_path / "out-d" / "r.json"
        report.parent.mkdir()

        def fetch() -> None:
            report.parent.rmdir()
            report.parent.symlink_to(tmp_path / "gone" / "x")

        expected = f"report path passes through {report.parent}, which is not a directory: {report}"
        absent = [report, tmp_path / "gone"]
    elif case == "write-time-holder-place-relinked":
        # B physically holds the report; the fetch turns B's .axiom into a
        # link to the report's directory. --repo is repo, not B.
        holder = make_checkout("b", {"us-example-layered": _layered_selector()})
        (holder / "notes").mkdir()
        (holder / ".axiom").mkdir()
        base = _base_coverage(corpus)
        base_bytes = base.read_bytes()
        report = holder / "notes" / "r.json"

        def fetch() -> None:
            (holder / ".axiom").rmdir()
            (holder / ".axiom").symlink_to(holder / "notes")

        expected = f"report path resolves into .axiom of the checkout {holder}: {report}"
        absent = [report]
    elif case == "write-time-holder-appears":
        # The report's directory lies in no checkout at the check; the fetch
        # turns it into a link to B's .axiom, so B holds the path only at
        # write time.
        holder = make_checkout("b", {"us-example-layered": _layered_selector()})
        (holder / ".axiom" / "notes").mkdir(parents=True)
        base = _base_coverage(corpus)
        base_bytes = base.read_bytes()
        out = tmp_path / "out-z"
        (out / "notes").mkdir(parents=True)
        report = out / "notes" / "r.json"

        def fetch() -> None:
            shutil.rmtree(out)
            out.symlink_to(holder / ".axiom")

        expected = f"report path resolves into .axiom of the checkout {holder}: {report}"
        absent = [report, holder / ".axiom" / "notes" / "r.json"]
    else:
        raise AssertionError(case)
    events = _report_argv(monkeypatch, repo, report, fetch=fetch)

    with pytest.raises(ValueError) as raised:
        repair_module.main()

    assert str(raised.value) == expected
    assert events == ["fetch"]
    assert base.read_bytes() == base_bytes
    for path in absent:
        assert not os.path.lexists(path), path


def test_main_accepts_a_plain_report_outside_protected_places(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    _write_report_repo(repo)
    coverage = _base_coverage(repo / "data" / "corpus")
    base_bytes = coverage.read_bytes()
    # A new file, a rerun onto the report the first run wrote, and the repository root.
    for report in (tmp_path / "report.json", tmp_path / "report.json", repo / "report.json"):
        events = _report_argv(monkeypatch, repo, report)

        assert repair_module.main() == 0

        assert events == ["fetch"]
        assert report.is_file() and not report.is_symlink()
        assert set(json.loads(report.read_text())) == repair_module.REPORT_KEYS
    assert coverage.read_bytes() == base_bytes


@pytest.mark.parametrize(
    "case",
    [
        "report-through-dangling-link-outside",
        "report-through-file-outside",
        "report-through-dangling-dotdot",
        "report-through-dangling-link-two-up",
    ],
)
def test_main_refuses_a_report_path_below_something_that_is_not_a_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    _write_report_repo(repo)
    entry = tmp_path / "x"
    if case == "report-through-dangling-link-outside":
        entry.symlink_to(tmp_path / "nowhere")
        report = entry / "r.json"
    elif case == "report-through-file-outside":
        entry = tmp_path / "plainfile"
        entry.write_text("x\n")
        report = entry / "r.json"
    elif case == "report-through-dangling-dotdot":
        entry.symlink_to(tmp_path / "nowhere")
        (tmp_path / "out").mkdir()
        report = entry / ".." / "out" / "r.json"
    elif case == "report-through-dangling-link-two-up":
        entry.symlink_to(tmp_path / "nowhere")
        report = entry / "y" / "r.json"
    else:
        raise AssertionError(case)
    events = _report_argv(monkeypatch, repo, report)
    before = _snapshot(tmp_path)

    with pytest.raises(ValueError) as raised:
        repair_module.main()

    assert str(raised.value) == (
        f"report path passes through {entry}, which is not a directory: {report}"
    )
    assert events == []
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "case",
    [
        "control-ancestor-of-dangling-target",
        "control-sibling-of-place",
        "control-sibling-of-dangling-target",
        "control-place-name-elsewhere",
        "cwd-checkout-link",
        "deeper-lock-link",
        "dangling-file-link-in-releases",
    ],
)
def test_main_writes_a_report_beside_a_place_or_where_limit_14_lets_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_checkout: MakeCheckout, case: str
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    _write_report_repo(repo)
    base = _base_coverage(repo / "data" / "corpus")
    coverage_place = repo / "data" / "corpus" / "coverage"
    if case in ("control-ancestor-of-dangling-target", "control-sibling-of-dangling-target"):
        # The coverage place dangles; its files move aside so the base stays readable.
        coverage_place.rename(tmp_path / "unused-cov")
        base = tmp_path / "unused-cov" / "us-example" / "regulation" / "base-v.json"
    base_bytes = base.read_bytes()
    if case == "control-ancestor-of-dangling-target":
        # The report is the dangling target's parent, not below the target.
        coverage_place.symlink_to(tmp_path / "x" / "y")
        report = tmp_path / "x"
    elif case == "control-sibling-of-place":
        report = repo / "data-old" / "r.json"
    elif case == "control-sibling-of-dangling-target":
        coverage_place.symlink_to(tmp_path / "outside-cov")
        report = tmp_path / "outside-cov-2" / "r.json"
    elif case == "control-place-name-elsewhere":
        report = tmp_path / "plain" / "data" / "corpus" / "coverage" / "r.json"
        report.parent.mkdir(parents=True)
    elif case == "cwd-checkout-link":
        # Limit 14: the working directory's checkout C is no root, and C's
        # data/corpus leads to where the report goes.
        checkout = make_checkout("C", {"us-example-layered": _layered_selector()})
        shared = tmp_path / "shared"
        (shared / "coverage" / "us-example" / "regulation").mkdir(parents=True)
        (checkout / "data").mkdir()
        (checkout / "data" / "corpus").symlink_to(shared)
        monkeypatch.chdir(checkout)
        report = _base_coverage(shared)
    elif case == "deeper-lock-link":
        # Limit 14: a link below the lock place is not followed.
        locks = repo / ".axiom" / "corpus-locks" / "us-example"
        shutil.rmtree(locks)
        locks.symlink_to(tmp_path / "out-lk")
        report = tmp_path / "out-lk" / "regulation" / "base-v.json"
    elif case == "dangling-file-link-in-releases":
        # Limit 14: a file link below the selector place is not followed. The
        # selectors are committed, so the dangling link is read as untracked.
        fixture_git(repo, "init", "-q", "-b", "main")
        fixture_git(repo, "add", "--", "manifests")
        fixture_git(repo, "commit", "-q", "-m", "Fixture checkout")
        from axiom_corpus.corpus import resolver

        resolver._repo_root_for_dir.cache_clear()
        (tmp_path / "out").mkdir()
        (repo / "manifests" / "releases" / "x.json").symlink_to(tmp_path / "out" / "x.json")
        report = tmp_path / "out" / "x.json"
    else:
        raise AssertionError(case)
    events = _report_argv(monkeypatch, repo, report)

    assert repair_module.main() == 0

    assert events == ["fetch"]
    assert report.is_file() and not report.is_symlink()
    assert set(json.loads(report.read_text())) == set(WRITTEN_KEYS)
    assert base.read_bytes() == base_bytes
