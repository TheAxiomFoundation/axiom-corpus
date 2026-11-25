from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

import scripts.deduplicate_release_selector as dedup_module
from scripts.deduplicate_release_selector import deduplicate
from tests.conftest import fixture_git

ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_scope(corpus: Path, version: str, paths: list[str]) -> None:
    scope_root = ("us-example", "statute")
    provisions = corpus.joinpath("provisions", *scope_root, f"{version}.jsonl")
    inventory = corpus.joinpath("inventory", *scope_root, f"{version}.json")
    coverage = corpus.joinpath("coverage", *scope_root, f"{version}.json")
    provisions.parent.mkdir(parents=True, exist_ok=True)
    provisions.write_text(
        "".join(
            json.dumps(
                {
                    "citation_path": path,
                    "document_class": "statute",
                    "jurisdiction": "us-example",
                    "version": version,
                },
                sort_keys=True,
            )
            + "\n"
            for path in paths
        )
    )
    _write_json(inventory, {"items": [{"citation_path": path} for path in paths]})
    _write_json(
        coverage,
        {
            "complete": True,
            "document_class": "statute",
            "duplicate_provision_citations": [],
            "duplicate_source_citations": [],
            "extra_provisions": [],
            "jurisdiction": "us-example",
            "matched_count": len(paths),
            "missing_from_provisions": [],
            "provision_count": len(paths),
            "source_count": len(paths),
            "version": version,
        },
    )


def _write_selector(path: Path, versions: list[str], *, bases: tuple[str, ...] = ()) -> None:
    _write_json(
        path,
        {
            "scopes": [
                {
                    "document_class": "statute",
                    "jurisdiction": "us-example",
                    "version": version,
                    **({"layer": "base"} if version in bases else {}),
                }
                for version in versions
            ]
        },
    )


def _scope_files(corpus: Path, version: str) -> list[Path]:
    return [
        corpus.joinpath("provisions", "us-example", "statute", f"{version}.jsonl"),
        corpus.joinpath("inventory", "us-example", "statute", f"{version}.json"),
        corpus.joinpath("coverage", "us-example", "statute", f"{version}.json"),
    ]


def _digests(paths: list[Path]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def _provision_paths(corpus: Path, version: str) -> list[str]:
    provisions = corpus.joinpath("provisions", "us-example", "statute", f"{version}.jsonl")
    return [json.loads(line)["citation_path"] for line in provisions.read_text().splitlines()]


def _base_mapping(version: str) -> dict[str, str]:
    return {
        "document_class": "statute",
        "jurisdiction": "us-example",
        "layer": "base",
        "version": version,
    }


def test_deduplicate_retains_canonical_carrier_and_refreshes_added_scope(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/1"])
    _write_scope(corpus, "added", ["us-example/statute/1", "us-example/statute/2"])
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "added"])

    dry_run = deduplicate(corpus, canonical, target, apply=False)
    assert dry_run["collision_count"] == 1
    assert "us-example/statute/1" in (
        corpus / "provisions/us-example/statute/added.jsonl"
    ).read_text()

    applied = deduplicate(corpus, canonical, target, apply=True)
    assert applied["collision_count"] == 1
    assert [
        json.loads(line)["citation_path"]
        for line in (corpus / "provisions/us-example/statute/added.jsonl").read_text().splitlines()
    ] == ["us-example/statute/2"]
    inventory = json.loads((corpus / "inventory/us-example/statute/added.json").read_text())
    coverage = json.loads((corpus / "coverage/us-example/statute/added.json").read_text())
    assert inventory["items"] == [{"citation_path": "us-example/statute/2"}]
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["provision_count"] == 1


def test_deduplicate_rejects_ambiguous_added_carriers(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    for version in ("canonical", "added-one", "added-two"):
        _write_scope(corpus, version, ["us-example/statute/1"])
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "added-one", "added-two"])

    with pytest.raises(ValueError, match="ambiguous citation carrier"):
        deduplicate(corpus, canonical, target, apply=False)


def test_deduplicate_reports_inherited_canonical_collisions(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical-one", ["us-example/statute/1"])
    _write_scope(corpus, "canonical-two", ["us-example/statute/1"])
    _write_scope(corpus, "added", ["us-example/statute/2"])
    _write_selector(canonical, ["canonical-one", "canonical-two"])
    _write_selector(target, ["canonical-one", "canonical-two", "added"])

    report = deduplicate(corpus, canonical, target, apply=False)
    assert report["collision_count"] == 0
    assert report["inherited_collision_count"] == 1
    assert report["inherited_collision_paths"] == ["us-example/statute/1"]


def test_deduplicate_preflights_every_scope_before_writing(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(
        corpus,
        "canonical",
        ["us-example/statute/1", "us-example/statute/2"],
    )
    _write_scope(
        corpus,
        "added-a-good",
        ["us-example/statute/1", "us-example/statute/3"],
    )
    _write_scope(
        corpus,
        "added-z-bad",
        ["us-example/statute/2", "us-example/statute/4"],
    )
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "added-a-good", "added-z-bad"])
    bad_inventory = corpus / "inventory/us-example/statute/added-z-bad.json"
    _write_json(bad_inventory, {"items": [{"citation_path": "us-example/statute/4"}]})
    good_provisions = corpus / "provisions/us-example/statute/added-a-good.jsonl"
    before = good_provisions.read_text()

    with pytest.raises(ValueError, match="expected one inventory item"):
        deduplicate(corpus, canonical, target, apply=True)

    assert good_provisions.read_text() == before


def test_deduplicate_never_opens_or_cuts_an_added_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(
        corpus,
        "canonical",
        ["us-example/statute/1", "us-example/statute/2", "us-example/statute/5"],
    )
    _write_scope(
        corpus,
        "base",
        ["us-example/statute/1", "us-example/statute/2", "us-example/statute/3"],
    )
    _write_scope(corpus, "added", ["us-example/statute/4", "us-example/statute/5"])
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "base", "added"], bases=("base",))
    base_files = _scope_files(corpus, "base")
    before = _digests(base_files)
    opened: list[Path] = []
    read_text = Path.read_text

    def recording_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        opened.append(self)
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", recording_read_text)
    report = deduplicate(corpus, canonical, target, apply=True)
    monkeypatch.undo()

    assert set(_scope_files(corpus, "added")) <= set(opened)
    assert set(opened).isdisjoint(base_files)
    assert _digests(base_files) == before
    assert _provision_paths(corpus, "base") == [
        "us-example/statute/1",
        "us-example/statute/2",
        "us-example/statute/3",
    ]
    assert _provision_paths(corpus, "added") == ["us-example/statute/4"]
    assert report["collision_count"] == 1
    assert report["untouched_base_scopes"] == [_base_mapping("base")]


def test_deduplicate_lets_an_added_primary_shadow_a_canonical_base(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/5"])
    _write_scope(corpus, "base", ["us-example/statute/1", "us-example/statute/2"])
    _write_scope(corpus, "added", ["us-example/statute/1", "us-example/statute/3"])
    _write_selector(canonical, ["canonical", "base"], bases=("base",))
    _write_selector(target, ["canonical", "base", "added"], bases=("base",))
    before = _digests(_scope_files(corpus, "base") + _scope_files(corpus, "added"))

    report = deduplicate(corpus, canonical, target, apply=True)

    assert report["collision_count"] == 0
    assert report["scopes"] == []
    assert report["untouched_base_scopes"] == [_base_mapping("base")]
    assert _provision_paths(corpus, "added") == ["us-example/statute/1", "us-example/statute/3"]
    assert _digests(_scope_files(corpus, "base") + _scope_files(corpus, "added")) == before


def test_deduplicate_resolves_a_primary_collision_over_a_canonical_base(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/1"])
    _write_scope(corpus, "base", ["us-example/statute/1", "us-example/statute/2"])
    _write_scope(corpus, "added", ["us-example/statute/1", "us-example/statute/3"])
    _write_selector(canonical, ["canonical", "base"], bases=("base",))
    _write_selector(target, ["canonical", "base", "added"], bases=("base",))
    base_files = _scope_files(corpus, "base")
    before = _digests(base_files)

    report = deduplicate(corpus, canonical, target, apply=True)

    assert report["collision_count"] == 1
    assert report["inherited_collision_count"] == 0
    assert [(scope["version"], scope["removed_paths"]) for scope in report["scopes"]] == [
        ("added", ["us-example/statute/1"])
    ]
    assert _provision_paths(corpus, "added") == ["us-example/statute/3"]
    assert _provision_paths(corpus, "canonical") == ["us-example/statute/1"]
    assert _digests(base_files) == before
    assert report["untouched_base_scopes"] == [_base_mapping("base")]


@pytest.mark.parametrize(
    ("canonical_bases", "target_bases", "omitted"),
    [
        (("base",), (), "us-example/statute/base (base)"),
        ((), ("canonical",), "us-example/statute/canonical"),
    ],
    ids=["canonical-base-carried-as-primary", "canonical-primary-carried-as-base"],
)
def test_deduplicate_refuses_a_canonical_scope_carried_in_the_other_layer(
    tmp_path: Path,
    canonical_bases: tuple[str, ...],
    target_bases: tuple[str, ...],
    omitted: str,
) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/1"])
    _write_scope(corpus, "base", ["us-example/statute/1", "us-example/statute/2"])
    _write_scope(corpus, "added", ["us-example/statute/3"])
    _write_selector(canonical, ["canonical", "base"], bases=canonical_bases)
    _write_selector(target, ["canonical", "base", "added"], bases=target_bases)

    with pytest.raises(ValueError) as excinfo:
        deduplicate(corpus, canonical, target, apply=False)

    assert str(excinfo.value) == f"target selector omits canonical scopes: {omitted}"


def test_deduplicate_refuses_a_scope_selected_in_both_layers(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_selector(canonical, ["canonical"])
    _write_json(
        target,
        {
            "scopes": [
                {"document_class": "statute", "jurisdiction": "us-example", "version": "canonical"},
                {
                    "document_class": "statute",
                    "jurisdiction": "us-example",
                    "layer": "base",
                    "version": "canonical",
                },
            ]
        },
    )

    with pytest.raises(ValueError, match="selector contains duplicate scopes"):
        deduplicate(tmp_path / "corpus", canonical, target, apply=False)


# A tracked selector marks us-example/statute/base as a base, and canonical as a primary scope.
LAYERED_SELECTOR = "us-example-layered"
TRACKED_BASE_REFUSAL = (
    "target selector {target} selects a tracked base scope as a primary scope: "
    'us-example/statute/base; a scope that a tracked selector marks "layer": "base" '
    "is selected only as a base"
)


def _write_tracked_releases(directory: Path) -> Path:
    releases = directory / "releases"
    _write_json(
        releases / f"{LAYERED_SELECTOR}.json",
        {
            "name": LAYERED_SELECTOR,
            "scopes": [
                {"document_class": "statute", "jurisdiction": "us-example", "version": "canonical"},
                _base_mapping("base"),
            ],
        },
    )
    return releases


@pytest.mark.parametrize(
    ("canonical_versions", "target_versions"),
    [
        pytest.param(["canonical"], ["canonical", "base"], id="reviewer-draft-drops-the-layer"),
        pytest.param(["canonical"], ["canonical", "base", "added"], id="beside-an-added-primary"),
        pytest.param(
            ["canonical", "base"], ["canonical", "base"], id="canonical-carries-it-as-primary"
        ),
    ],
)
def test_deduplicate_refuses_a_tracked_base_selected_as_primary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    canonical_versions: list[str],
    target_versions: list[str],
) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/1"])
    _write_scope(corpus, "base", ["us-example/statute/1", "us-example/statute/2"])
    _write_scope(corpus, "added", ["us-example/statute/3"])
    _write_selector(canonical, canonical_versions)
    _write_selector(target, target_versions)
    releases = _write_tracked_releases(tmp_path)
    base_files = _scope_files(corpus, "base")
    before = _digests(base_files + _scope_files(corpus, "canonical"))
    opened: list[Path] = []
    read_text = Path.read_text

    def recording_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        opened.append(self)
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", recording_read_text)
    with pytest.raises(ValueError) as raised:
        deduplicate(corpus, canonical, target, apply=True, releases_dir=releases)
    monkeypatch.undo()

    assert str(raised.value) == TRACKED_BASE_REFUSAL.format(target=target)
    assert set(opened).isdisjoint(base_files)
    assert _digests(base_files + _scope_files(corpus, "canonical")) == before


def test_deduplicate_leaves_a_tracked_base_declared_as_base_alone(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/1"])
    _write_scope(corpus, "base", ["us-example/statute/1", "us-example/statute/2"])
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "base"], bases=("base",))
    releases = _write_tracked_releases(tmp_path)
    files = _scope_files(corpus, "base") + _scope_files(corpus, "canonical")
    before = _digests(files)

    report = deduplicate(corpus, canonical, target, apply=True, releases_dir=releases)

    assert report["collision_count"] == 0
    assert report["untouched_base_scopes"] == [_base_mapping("base")]
    assert _digests(files) == before


def test_deduplicate_reads_the_repository_selectors_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/1"])
    _write_scope(corpus, "base", ["us-example/statute/1", "us-example/statute/2"])
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "base"])
    seen: list[Path] = []

    def recording_tracked_base_scopes(releases_dir: Path) -> frozenset[tuple[str, str, str]]:
        seen.append(releases_dir)
        return frozenset({("us-example", "statute", "base")})

    monkeypatch.setattr(
        dedup_module, "tracked_base_scopes", recording_tracked_base_scopes, raising=False
    )

    with pytest.raises(ValueError) as raised:
        deduplicate(corpus, canonical, target, apply=True)

    assert str(raised.value) == TRACKED_BASE_REFUSAL.format(target=target)
    repository_releases = ROOT / "manifests" / "releases"
    assert seen == [repository_releases]
    assert getattr(dedup_module, "DEFAULT_RELEASES_DIR", None) == repository_releases


@pytest.mark.parametrize(
    "checkout",
    [
        pytest.param("other-checkout", id="base-checkout"),
        pytest.param(None, id="no-checkout"),
    ],
)
def test_deduplicate_cli_reads_the_selectors_of_the_checkout_holding_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, checkout: str | None
) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/1"])
    _write_scope(corpus, "base", ["us-example/statute/1", "us-example/statute/2"])
    _write_selector(canonical, ["canonical"])
    # The draft drops the layer of a scope that a tracked selector marks as a base.
    _write_selector(target, ["canonical", "base"])
    base_files = _scope_files(corpus, "base")
    before = _digests(base_files)
    asked: list[Path] = []
    seen: list[Path] = []

    def fake_cli_repo(args: Any) -> Path | None:
        asked.append(Path(args.base))
        return None if checkout is None else tmp_path / checkout

    def recording_tracked_base_scopes(releases_dir: Path) -> frozenset[tuple[str, str, str]]:
        seen.append(releases_dir)
        return frozenset({("us-example", "statute", "base")})

    monkeypatch.setattr(dedup_module, "cli_repo", fake_cli_repo, raising=False)
    monkeypatch.setattr(
        dedup_module, "tracked_base_scopes", recording_tracked_base_scopes, raising=False
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deduplicate_release_selector.py",
            "--corpus",
            str(corpus),
            "--canonical-selector",
            str(canonical),
            "--target-selector",
            str(target),
            "--apply",
        ],
    )

    if checkout is None:
        # No checkout holds --corpus or the working directory, so no selector
        # says which scopes are bases: the command line refuses to guess.
        with pytest.raises(SystemExit) as exited:
            dedup_module.main()
        assert exited.value.code == 2
        assert seen == []
    else:
        with pytest.raises(ValueError) as raised:
            dedup_module.main()
        assert str(raised.value) == TRACKED_BASE_REFUSAL.format(target=target)
        assert seen == [tmp_path / "other-checkout" / "manifests" / "releases"]
    assert asked == [corpus]
    assert _digests(base_files) == before


# Finding 1 of round 2: the checkouts that hold dedup's paths. Each checkout is
# built with ``make_checkout`` and commits its selectors; ``canonical`` carries
# X, and ``base`` and ``added`` carry X and Y.
MakeCheckout = Callable[[str, Mapping[str, Mapping[str, object]]], Path]
X = "us-example/statute/1"
Y = "us-example/statute/2"


def _selector_payload(name: str, *, marks_base: bool) -> dict[str, object]:
    scopes: list[dict[str, str]] = [
        {"document_class": "statute", "jurisdiction": "us-example", "version": "canonical"}
    ]
    if marks_base:
        scopes.append(_base_mapping("base"))
    return {"name": name, "scopes": scopes}


def _checkout(make_checkout: MakeCheckout, name: str, *, marks_base: bool = False) -> Path:
    selector = f"{name}-selector"
    return make_checkout(name, {selector: _selector_payload(selector, marks_base=marks_base)})


def _releases(checkout: Path) -> Path:
    return checkout / "manifests" / "releases"


def _clear_resolver_cache() -> None:
    from axiom_corpus.corpus import resolver

    resolver._repo_root_for_dir.cache_clear()


def _write_scopes(corpus: Path) -> None:
    _write_scope(corpus, "canonical", [X])
    _write_scope(corpus, "base", [X, Y])
    _write_scope(corpus, "added", [X, Y])


def _link(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)


def _relink(path: Path, target: Path, *, hard: bool = False) -> None:
    path.unlink()
    if hard:
        os.link(target, path)
    else:
        path.symlink_to(target)


def _bytes_under(root: Path) -> dict[str, bytes]:
    """Every file below ``root`` outside ``.git``, read through its own path."""
    found: dict[str, bytes] = {}
    for directory, directories, filenames in os.walk(root):
        directories[:] = [name for name in directories if name != ".git"]
        for name in filenames:
            path = Path(directory, name)
            if name != ".git" and path.is_file():
                found[str(path.relative_to(root))] = path.read_bytes()
    return found


def _exactly(text: str) -> str:
    return "^" + re.escape(text) + "$"


def _swap_for_link(path: Path, target: Path) -> None:
    """Replace the directory ``path`` with a symlink to ``target``."""
    shutil.rmtree(path)
    path.symlink_to(target, target_is_directory=True)


def _toplevel_refusal(top: Path, checkout: Path) -> str:
    return (
        r"^selector directory is not the manifests/releases of the toplevel git names \("
        + re.escape(str(top))
        + r"\), while a \.git entry sits two levels up at "
        + re.escape(str(checkout / ".git"))
    )


@pytest.mark.parametrize(
    "case",
    [
        "corpus-link",
        "provisions-link",
        "inventory-link",
        "coverage-link",
        "link-outside-checkouts",
        "link-holder-marks-base",
        "selector-holder",
        "canonical-holder",
        "sparse-holder-without-markers",
        "file-symlinks",
        "directory-alias",
        "base-path-links-to-primary",
        "hard-link",
        "coverage-only-hard-link",
        "tracked-base-links-to-cut-primary",
        "linked-holders-base-links-to-cut-primary",
        "holder-releases-link",
        "holder-manifests-link",
        "holder-nested-repo-at-manifests",
        "holder-nested-repo-at-releases",
        "holder-gitfile-at-manifests",
        "releases-dir-core-worktree-redirect",
    ],
)
def test_deduplicate_refuses_a_base_or_an_alias_another_path_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_checkout: MakeCheckout, case: str
) -> None:
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_selector(canonical, ["canonical"])
    # The draft selects base as a primary scope unless the case says otherwise.
    target_versions = ["canonical", "base"]
    target_bases: tuple[str, ...] = ()
    error: type[Exception] = ValueError
    if case == "corpus-link":
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", marks_base=True)
        _write_scopes(b / "data" / "corpus")
        _link(a / "data" / "corpus", b / "data" / "corpus")
        corpus, releases = a / "data" / "corpus", _releases(a)
        expected = _exactly(TRACKED_BASE_REFUSAL.format(target=target))
    elif case in ("provisions-link", "inventory-link", "coverage-link"):
        # Only A's directory of one artifact kind leads into B, which marks base.
        kind = case.removesuffix("-link")
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", marks_base=True)
        _write_scopes(a / "data" / "corpus")
        _write_scopes(b / "data" / "corpus")
        shutil.rmtree(a / "data" / "corpus" / kind)
        _link(a / "data" / "corpus" / kind, b / "data" / "corpus" / kind)
        corpus, releases = a / "data" / "corpus", _releases(a)
        expected = _exactly(TRACKED_BASE_REFUSAL.format(target=target))
    elif case == "link-outside-checkouts":
        a = _checkout(make_checkout, "a")
        _write_scopes(tmp_path / "shared")
        _link(a / "data" / "corpus", tmp_path / "shared")
        corpus, releases = a / "data" / "corpus", _releases(a)
        target_versions = ["canonical", "added"]
        expected = (
            "^scope artifact leads through a link outside every axiom-corpus checkout: "
            + re.escape(str(_scope_files(corpus, "canonical")[0]))
        )
    elif case == "link-holder-marks-base":
        a = _checkout(make_checkout, "a", marks_base=True)
        b = _checkout(make_checkout, "b")
        c = _checkout(make_checkout, "c")
        _write_scopes(b / "data" / "corpus")
        _link(a / "data" / "corpus", b / "data" / "corpus")
        corpus, releases = a / "data" / "corpus", _releases(c)
        expected = _exactly(TRACKED_BASE_REFUSAL.format(target=target))
    elif case == "selector-holder":
        m = _checkout(make_checkout, "m")
        wt = _checkout(make_checkout, "wt", marks_base=True)
        _write_scopes(m / "data" / "corpus")
        corpus, releases = m / "data" / "corpus", _releases(m)
        # The draft lies in a checkout whose HEAD marks base as a base.
        target = wt / "draft.json"
        expected = _exactly(TRACKED_BASE_REFUSAL.format(target=target))
    elif case == "canonical-holder":
        m = _checkout(make_checkout, "m")
        wt = _checkout(make_checkout, "wt", marks_base=True)
        _write_scopes(m / "data" / "corpus")
        corpus, releases = m / "data" / "corpus", _releases(m)
        # The canonical selector lies in a checkout whose HEAD marks base as a base.
        canonical = wt / "canonical.json"
        _write_selector(canonical, ["canonical"])
        expected = _exactly(TRACKED_BASE_REFUSAL.format(target=target))
    elif case == "sparse-holder-without-markers":
        b = _checkout(make_checkout, "b", marks_base=True)
        c = _checkout(make_checkout, "c")
        fixture_git(b, "sparse-checkout", "set", "--no-cone", "/*", "!/src/", "!/.axiom/")
        _clear_resolver_cache()
        assert not (b / "src").exists() and not (b / ".axiom").exists()
        _write_scopes(b / "data" / "corpus")
        corpus, releases = b / "data" / "corpus", _releases(c)
        expected = _exactly(TRACKED_BASE_REFUSAL.format(target=target))
    elif case == "file-symlinks":
        a = _checkout(make_checkout, "a", marks_base=True)
        corpus, releases = a / "data" / "corpus", _releases(a)
        _write_scopes(corpus)
        for added, base in zip(
            _scope_files(corpus, "added"), _scope_files(corpus, "base"), strict=True
        ):
            _relink(added, base)
        target_versions = ["canonical", "added"]
        expected = "^scope artifact resolves to another path: " + re.escape(
            str(_scope_files(corpus, "added")[0]) + " -> "
        )
    elif case == "directory-alias":
        a = _checkout(make_checkout, "a", marks_base=True)
        corpus, releases = a / "data" / "corpus", _releases(a)
        _write_scopes(corpus)
        for kind in ("provisions", "inventory", "coverage"):
            _link(
                corpus / kind / "us-example" / "regulation",
                corpus / kind / "us-example" / "statute",
            )
        _write_json(
            target,
            {
                "scopes": [
                    {
                        "document_class": "statute",
                        "jurisdiction": "us-example",
                        "version": "canonical",
                    },
                    {
                        "document_class": "regulation",
                        "jurisdiction": "us-example",
                        "version": "base",
                    },
                ]
            },
        )
        target_versions = []
        alias = corpus / "provisions" / "us-example" / "regulation" / "base.jsonl"
        expected = "^scope artifact resolves to another path: " + re.escape(f"{alias} -> ")
    elif case == "base-path-links-to-primary":
        a = _checkout(make_checkout, "a", marks_base=True)
        corpus, releases = a / "data" / "corpus", _releases(a)
        _write_scopes(corpus)
        for base, added in zip(
            _scope_files(corpus, "base"), _scope_files(corpus, "added"), strict=True
        ):
            _relink(base, added)
        target_versions, target_bases = ["canonical", "added", "base"], ("base",)
        expected = "^scope artifact resolves to another path: " + re.escape(
            str(_scope_files(corpus, "base")[0]) + " -> "
        )
    elif case in ("hard-link", "coverage-only-hard-link"):
        a = _checkout(make_checkout, "a", marks_base=True)
        corpus, releases = a / "data" / "corpus", _releases(a)
        _write_scopes(corpus)
        pairs = list(zip(_scope_files(corpus, "added"), _scope_files(corpus, "base"), strict=True))
        if case == "coverage-only-hard-link":
            pairs = pairs[2:]
        for added, base in pairs:
            _relink(added, base, hard=True)
        target_versions = ["canonical", "added"]
        expected = _exactly(
            f"scope artifact shares its file with another path: {pairs[0][0]} (2 links)"
        )
    elif case == "tracked-base-links-to-cut-primary":
        a = _checkout(make_checkout, "a", marks_base=True)
        corpus, releases = a / "data" / "corpus", _releases(a)
        _write_scopes(corpus)
        added_provisions = _scope_files(corpus, "added")[0]
        _relink(_scope_files(corpus, "base")[0], added_provisions)
        target_versions = ["canonical", "added"]
        expected = _exactly(
            f"{added_provisions} is also us-example/statute/base's provisions through a link"
        )
    elif case == "linked-holders-base-links-to-cut-primary":
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", marks_base=True)
        shared = b / "data" / "corpus"
        _write_scopes(shared)
        _relink(_scope_files(shared, "base")[2], _scope_files(shared, "added")[2])
        _link(a / "data" / "corpus", shared)
        corpus, releases = a / "data" / "corpus", _releases(a)
        target_versions = ["canonical", "added"]
        expected = _exactly(
            f"{_scope_files(corpus, 'added')[2]} is also us-example/statute/base's coverage "
            "through a link"
        )
    elif case in ("holder-releases-link", "holder-manifests-link"):
        # B physically holds the corpus, spelled through A's link, and marks base;
        # B's selector directory leads to the one releases_dir names.
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", marks_base=True)
        _write_scopes(b / "data" / "corpus")
        _link(a / "data" / "corpus", b / "data" / "corpus")
        if case == "holder-releases-link":
            link = _releases(b)
            _swap_for_link(link, _releases(a))
            releases = _releases(a)
        else:
            third = _checkout(make_checkout, "third")
            link = b / "manifests"
            _swap_for_link(link, third / "manifests")
            releases = _releases(third)
        _clear_resolver_cache()
        corpus = a / "data" / "corpus"
        expected = "^" + re.escape(f"selector directory leads through a link: {link} -> ")
    elif case in (
        "holder-nested-repo-at-manifests",
        "holder-nested-repo-at-releases",
        "holder-gitfile-at-manifests",
    ):
        # B physically holds the corpus and commits a selector marking base; on
        # disk its selector is hidden beside a plain one, and another git
        # repository's entry sits at its manifests or manifests/releases.
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", marks_base=True)
        other = _checkout(make_checkout, "other")
        _write_scopes(b / "data" / "corpus")
        _link(a / "data" / "corpus", b / "data" / "corpus")
        if case == "holder-nested-repo-at-releases":
            fixture_git(b, "update-index", "--skip-worktree", "manifests/releases/b-selector.json")
            (_releases(b) / "b-selector.json").unlink()
            fixture_git(_releases(b), "init", "-q")
            entry = _releases(b) / ".git"
        else:
            fixture_git(b, "sparse-checkout", "set", "--no-cone", "/*", "!/manifests/")
            _releases(b).mkdir(parents=True)
            entry = b / "manifests" / ".git"
            if case == "holder-nested-repo-at-manifests":
                fixture_git(b / "manifests", "init", "-q")
            else:
                entry.write_text(f"gitdir: {other / '.git'}\n")
        _write_json(_releases(b) / "plain.json", _selector_payload("plain", marks_base=False))
        _clear_resolver_cache()
        corpus, releases = a / "data" / "corpus", _releases(a)
        expected = "^" + re.escape(f"selector directory sits at a git entry: {entry};")
    elif case == "releases-dir-core-worktree-redirect":
        # B commits a selector marking base, hidden beside a plain one, and its
        # core.worktree names another repository.
        b = _checkout(make_checkout, "b", marks_base=True)
        other = _checkout(make_checkout, "other")
        _write_scopes(b / "data" / "corpus")
        fixture_git(b, "update-index", "--skip-worktree", "manifests/releases/b-selector.json")
        (_releases(b) / "b-selector.json").unlink()
        _write_json(_releases(b) / "plain.json", _selector_payload("plain", marks_base=False))
        fixture_git(b, "config", "core.worktree", str(other))
        _clear_resolver_cache()
        corpus, releases = b / "data" / "corpus", _releases(b)
        error = FileNotFoundError
        expected = _toplevel_refusal(other, b)
    if target_versions:
        _write_selector(target, target_versions, bases=target_bases)
    before = _bytes_under(tmp_path)
    opened: list[Path] = []
    read_text = Path.read_text

    def recording_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        opened.append(self)
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", recording_read_text)
    with pytest.raises(error, match=expected):
        deduplicate(corpus, canonical, target, apply=True, releases_dir=releases)
    monkeypatch.undo()

    # Refused before any provisions file is read, and nothing changed anywhere.
    assert [path for path in opened if path.suffix == ".jsonl"] == []
    assert _bytes_under(tmp_path) == before


@pytest.mark.parametrize(
    "case",
    ["shared-corpus-control", "canonical-hard-link-control", "untracked-base-link-control"],
)
def test_deduplicate_runs_beside_links_that_reach_no_base_it_knows(
    tmp_path: Path, make_checkout: MakeCheckout, case: str
) -> None:
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "added"])
    a = _checkout(make_checkout, "a")
    corpus = a / "data" / "corpus"
    if case == "shared-corpus-control":
        b = _checkout(make_checkout, "b")
        _write_scopes(b / "data" / "corpus")
        _link(corpus, b / "data" / "corpus")
    elif case == "canonical-hard-link-control":
        _write_scopes(corpus)
        # Only rewritten files must have one link; dedup only reads canonical's.
        os.link(_scope_files(corpus, "canonical")[0], tmp_path / "outside.jsonl")
    else:
        # No selector marks base, so dedup does not know it (stated limit 3).
        _write_scopes(corpus)
        _relink(_scope_files(corpus, "base")[0], _scope_files(corpus, "added")[0])

    report = deduplicate(corpus, canonical, target, apply=True, releases_dir=_releases(a))

    assert report["collision_count"] == 1
    assert _provision_paths(corpus, "added") == [Y]
    assert _provision_paths(corpus, "canonical") == [X]


def _cli_argv(corpus: Path, canonical: Path, target: Path) -> list[str]:
    return [
        "deduplicate_release_selector.py",
        "--corpus",
        str(corpus),
        "--canonical-selector",
        str(canonical),
        "--target-selector",
        str(target),
        "--apply",
    ]


def test_deduplicate_cli_reads_the_working_directorys_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_checkout: MakeCheckout
) -> None:
    m = _checkout(make_checkout, "m")
    wt = tmp_path / "wt"
    fixture_git(m, "worktree", "add", "-q", "-b", "feat", str(wt))
    # The worktree's branch commits a selector that marks base as a base.
    _write_json(_releases(wt) / "wt-layered.json", _selector_payload("wt-layered", marks_base=True))
    fixture_git(wt, "add", "--", "manifests")
    fixture_git(wt, "commit", "-q", "-m", "Mark base as a base")
    _clear_resolver_cache()
    corpus = m / "data" / "corpus"
    _write_scopes(corpus)
    target = tmp_path / "draft.json"
    _write_selector(target, ["canonical", "base"])
    before = _bytes_under(tmp_path)
    monkeypatch.chdir(wt)
    monkeypatch.setattr(sys, "argv", _cli_argv(corpus, _releases(m) / "m-selector.json", target))

    # --corpus binds to m, whose HEAD marks nothing; the working directory's does.
    with pytest.raises(ValueError) as raised:
        dedup_module.main()

    assert str(raised.value) == TRACKED_BASE_REFUSAL.format(target=target)
    assert _bytes_under(tmp_path) == before


def test_the_cli_refuses_a_base_the_main_checkout_tracks_through_a_linked_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_checkout: MakeCheckout
) -> None:
    m = _checkout(make_checkout, "m")
    wt = tmp_path / "wt"
    fixture_git(m, "worktree", "add", "-q", "-b", "feat", str(wt))
    # After the worktree branched, main commits a selector that marks base as a base.
    _write_json(_releases(m) / "m-layered.json", _selector_payload("m-layered", marks_base=True))
    fixture_git(m, "add", "--", "manifests")
    fixture_git(m, "commit", "-q", "-m", "Mark base as a base")
    _clear_resolver_cache()
    _write_scopes(m / "data" / "corpus")
    _link(wt / "data" / "corpus", m / "data" / "corpus")
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "base"])
    before = _bytes_under(tmp_path)
    monkeypatch.chdir(wt)
    monkeypatch.setattr(sys, "argv", _cli_argv(Path("data/corpus"), canonical, target))

    # cli_repo binds to the worktree, which holds the link and predates the
    # base; the main checkout physically holds the corpus.
    with pytest.raises(ValueError) as raised:
        dedup_module.main()

    assert str(raised.value) == TRACKED_BASE_REFUSAL.format(target=target)
    assert _bytes_under(tmp_path) == before
    assert _provision_paths(m / "data" / "corpus", "base") == [X, Y]


def test_the_cli_refuses_a_corpus_checkout_whose_manifests_is_a_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_checkout: MakeCheckout
) -> None:
    a = _checkout(make_checkout, "a", marks_base=True)
    b = _checkout(make_checkout, "b")
    corpus = a / "data" / "corpus"
    _write_scopes(corpus)
    # A's HEAD marks base; on disk its manifests leads to B's, which marks nothing.
    fixture_git(a, "sparse-checkout", "set", "--no-cone", "/*", "!/manifests/")
    _link(a / "manifests", b / "manifests")
    _clear_resolver_cache()
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "base"])
    before = _bytes_under(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", _cli_argv(corpus, canonical, target))

    with pytest.raises(ValueError) as raised:
        dedup_module.main()

    assert str(raised.value).startswith(
        f"selector directory leads through a link: {a / 'manifests'} -> "
    )
    assert _bytes_under(tmp_path) == before
    assert _provision_paths(corpus, "base") == [X, Y]


def test_the_cli_reads_head_under_a_ceiling_at_manifests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_checkout: MakeCheckout
) -> None:
    a = _checkout(make_checkout, "a", marks_base=True)
    corpus = a / "data" / "corpus"
    _write_scopes(corpus)
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "base"])
    before = _bytes_under(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", _cli_argv(corpus, canonical, target))
    # Exported after every fixture git command; git would stop its search at A's manifests.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(a / "manifests"))

    with pytest.raises(ValueError) as raised:
        dedup_module.main()

    assert str(raised.value) == TRACKED_BASE_REFUSAL.format(target=target)
    assert _bytes_under(tmp_path) == before
    assert _provision_paths(corpus, "base") == [X, Y]
