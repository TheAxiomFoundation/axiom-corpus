from __future__ import annotations

import json
import os
import re
import shutil
import sys
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
    ],
)
def test_main_refuses_a_repair_through_a_link_or_of_a_base_another_checkout_marks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_checkout: MakeCheckout, case: str
) -> None:
    monkeypatch.chdir(tmp_path)
    release = PLAIN_RELEASE
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
