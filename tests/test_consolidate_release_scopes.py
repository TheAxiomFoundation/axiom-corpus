from __future__ import annotations

import json
import os
import re
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path

import pytest

import scripts.consolidate_release_scopes as consolidate_module
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.consolidate_release_scopes import consolidate_release_scopes
from tests.conftest import fixture_git


def _write_scope(
    store: CorpusArtifactStore,
    *,
    version: str,
    records: tuple[ProvisionRecord, ...],
    jurisdiction: str = "us",
) -> None:
    source = store.source_path(jurisdiction, "statute", version, "source.xml")
    source_sha256 = store.write_text(source, f"<source version='{version}' />")
    source_path = source.relative_to(store.root).as_posix()
    normalized = tuple(
        replace(
            record,
            version=version,
            source_path=source_path,
            source_as_of="2026-07-19",
            expression_date="2026-07-19",
        )
        for record in records
    )
    store.write_inventory(
        store.inventory_path(jurisdiction, "statute", version),
        [
            SourceInventoryItem(
                citation_path=record.citation_path,
                source_path=source_path,
                sha256=source_sha256,
                metadata=record.metadata,
            )
            for record in normalized
        ],
    )
    store.write_provisions(
        store.provisions_path(jurisdiction, "statute", version),
        normalized,
    )


def test_consolidates_structural_duplicates_without_mutating_sources(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    root = ProvisionRecord(
        jurisdiction="us",
        document_class="statute",
        citation_path="us/statute/26",
        heading="Title 26",
        body=None,
    )
    _write_scope(
        store,
        version="published-one",
        records=(
            root,
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/26/1",
                body="First.",
                parent_citation_path="us/statute/26",
            ),
        ),
    )
    _write_scope(
        store,
        version="published-two",
        records=(
            root,
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/26/2",
                body="Second.",
                parent_citation_path="us/statute/26",
            ),
        ),
    )
    before = store.provisions_path("us", "statute", "published-one").read_bytes()

    generated = consolidate_release_scopes(
        base=store.root,
        jurisdiction="us",
        document_class="statute",
        source_versions=("published-one", "published-two"),
        target_version="published-three",
    )

    assert len(generated) == 4
    assert store.provisions_path("us", "statute", "published-one").read_bytes() == before
    records = load_provisions(store.provisions_path("us", "statute", "published-three"))
    assert [record.citation_path for record in records] == [
        "us/statute/26",
        "us/statute/26/1",
        "us/statute/26/2",
    ]
    assert all(record.version == "published-three" for record in records)
    assert records[1].parent_id == deterministic_provision_id("us/statute/26", "published-three")
    inventory = load_source_inventory(store.inventory_path("us", "statute", "published-three"))
    assert len(inventory) == 3
    assert all("published-three/published-" in item.source_path for item in inventory)
    coverage = json.loads(store.coverage_path("us", "statute", "published-three").read_text())
    assert coverage["complete"] is True
    assert coverage["provision_count"] == 3


def test_rejects_conflicting_substantive_duplicates(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    for version, body in (("published-one", "First."), ("published-two", "Second.")):
        _write_scope(
            store,
            version=version,
            records=(
                ProvisionRecord(
                    jurisdiction="us",
                    document_class="statute",
                    citation_path="us/statute/26/1",
                    body=body,
                ),
            ),
        )

    with pytest.raises(ValueError, match="explicit preferred source version"):
        consolidate_release_scopes(
            base=store.root,
            jurisdiction="us",
            document_class="statute",
            source_versions=("published-one", "published-two"),
            target_version="published-three",
        )


def test_requires_explicit_carrier_for_semantically_different_containers(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    for version, heading in (("published-one", "Section 85"), ("published-two", "Title 26")):
        _write_scope(
            store,
            version=version,
            records=(
                ProvisionRecord(
                    jurisdiction="us",
                    document_class="statute",
                    citation_path="us/statute/26",
                    heading=heading,
                    body=None,
                ),
            ),
        )

    with pytest.raises(ValueError, match="explicit preferred source version"):
        consolidate_release_scopes(
            base=store.root,
            jurisdiction="us",
            document_class="statute",
            source_versions=("published-one", "published-two"),
            target_version="published-three",
        )

    consolidate_release_scopes(
        base=store.root,
        jurisdiction="us",
        document_class="statute",
        source_versions=("published-one", "published-two"),
        target_version="published-three",
        preferred_duplicate_versions={"us/statute/26": "published-two"},
    )

    records = load_provisions(store.provisions_path("us", "statute", "published-three"))
    assert records[0].heading == "Title 26"
    inventory = load_source_inventory(
        store.inventory_path("us", "statute", "published-three")
    )
    assert "/published-two/" in inventory[0].source_path


def test_drops_legacy_children_shadowed_by_successor_parents(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    local_metadata = {"download_url": "file:///Users/example/recovery/source.pdf"}
    _write_scope(
        store,
        version="published-legacy",
        records=(
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/26/1",
                body=None,
            ),
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/26/1/block-1",
                body="Stale text.",
                parent_citation_path="us/statute/26/1",
                kind="block",
                metadata=local_metadata,
            ),
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/26/2",
                body=None,
                metadata=local_metadata,
            ),
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/26/2/block-1",
                body="Unique legacy text.",
                parent_citation_path="us/statute/26/2",
                kind="block",
                metadata=local_metadata,
            ),
        ),
    )
    _write_scope(
        store,
        version="published-current",
        records=(
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/26/1",
                body="Current text.",
            ),
        ),
    )

    consolidate_release_scopes(
        base=store.root,
        jurisdiction="us",
        document_class="statute",
        source_versions=("published-legacy", "published-current"),
        target_version="published-consolidated",
        preferred_duplicate_version="published-current",
        shadowed_block_versions={"published-legacy": "published-current"},
    )

    records = load_provisions(
        store.provisions_path("us", "statute", "published-consolidated")
    )
    records_by_citation = {record.citation_path: record for record in records}
    assert set(records_by_citation) == {
        "us/statute/26/1",
        "us/statute/26/2",
        "us/statute/26/2/block-1",
    }
    assert records_by_citation["us/statute/26/1"].body == "Current text."
    assert records_by_citation["us/statute/26/2/block-1"].body == "Unique legacy text."
    assert all(
        not (record.metadata or {}).get("download_url", "").startswith("file://")
        for record in records
    )
    inventory = load_source_inventory(
        store.inventory_path("us", "statute", "published-consolidated")
    )
    assert all(
        not (item.metadata or {}).get("download_url", "").startswith("file://")
        for item in inventory
    )


def test_restricts_one_source_to_explicit_successor_citations(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    root = ProvisionRecord(
        jurisdiction="us",
        document_class="statute",
        citation_path="us/statute/hts",
        body=None,
    )
    _write_scope(
        store,
        version="current-schedule",
        records=(
            root,
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/hts/9903.85.67",
                body="Current heading.",
                parent_citation_path="us/statute/hts",
            ),
        ),
    )
    _write_scope(
        store,
        version="legacy-schedule",
        records=(
            root,
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/hts/9903.85.02",
                body="Legacy heading still cited by RuleSpec.",
                parent_citation_path="us/statute/hts",
            ),
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/hts/obsolete",
                body="Unrelated legacy heading.",
                parent_citation_path="us/statute/hts",
            ),
        ),
    )

    consolidate_release_scopes(
        base=store.root,
        jurisdiction="us",
        document_class="statute",
        source_versions=("current-schedule", "legacy-schedule"),
        target_version="rulespec-schedule",
        included_citations_by_version={
            "legacy-schedule": frozenset({"us/statute/hts/9903.85.02"})
        },
    )

    records = load_provisions(store.provisions_path("us", "statute", "rulespec-schedule"))
    assert [record.citation_path for record in records] == [
        "us/statute/hts",
        "us/statute/hts/9903.85.67",
        "us/statute/hts/9903.85.02",
    ]
    assert "/legacy-schedule/" in records[-1].source_path


def test_rejects_missing_explicit_successor_citation(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_scope(
        store,
        version="published-one",
        records=(
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/26/1",
                body="Text.",
            ),
        ),
    )

    with pytest.raises(ValueError, match="included citations are absent"):
        consolidate_release_scopes(
            base=store.root,
            jurisdiction="us",
            document_class="statute",
            source_versions=("published-one",),
            target_version="published-two",
            included_citations_by_version={
                "published-one": frozenset({"us/statute/26/2"})
            },
        )


def test_copy_failure_leaves_target_retryable(tmp_path, monkeypatch):
    store = CorpusArtifactStore(tmp_path / "corpus")
    for version, citation in (
        ("published-one", "us/statute/26/1"),
        ("published-two", "us/statute/26/2"),
    ):
        _write_scope(
            store,
            version=version,
            records=(
                ProvisionRecord(
                    jurisdiction="us",
                    document_class="statute",
                    citation_path=citation,
                    body="Text.",
                ),
            ),
        )
    original_copytree = shutil.copytree
    calls = 0

    def fail_second_copy(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected copy failure")
        return original_copytree(*args, **kwargs)

    monkeypatch.setattr(shutil, "copytree", fail_second_copy)
    with pytest.raises(OSError, match="injected copy failure"):
        consolidate_release_scopes(
            base=store.root,
            jurisdiction="us",
            document_class="statute",
            source_versions=("published-one", "published-two"),
            target_version="published-three",
        )

    targets = (
        store.root / "sources/us/statute/published-three",
        store.inventory_path("us", "statute", "published-three"),
        store.provisions_path("us", "statute", "published-three"),
        store.coverage_path("us", "statute", "published-three"),
    )
    assert not any(path.exists() for path in targets)
    monkeypatch.setattr(shutil, "copytree", original_copytree)
    consolidate_release_scopes(
        base=store.root,
        jurisdiction="us",
        document_class="statute",
        source_versions=("published-one", "published-two"),
        target_version="published-three",
    )
    assert all(path.exists() for path in targets)


def _write_layered_selector(releases_dir: Path) -> Path:
    """Write a tracked selector that marks us-example/statute/tracked-base as a base."""
    releases_dir.mkdir(parents=True)
    selector = {
        "name": "us-example-layered",
        "scopes": [
            {
                "document_class": "statute",
                "jurisdiction": "us-example",
                "layer": "base",
                "version": "tracked-base",
            },
            {
                "document_class": "statute",
                "jurisdiction": "us-example",
                "version": "primary-one",
            },
        ],
    }
    (releases_dir / "us-example-layered.json").write_text(
        json.dumps(selector, indent=2, sort_keys=True) + "\n"
    )
    return releases_dir


def _write_example_scope(
    store: CorpusArtifactStore, version: str, *, jurisdiction: str = "us-example"
) -> None:
    _write_scope(
        store,
        version=version,
        jurisdiction=jurisdiction,
        records=(
            ProvisionRecord(
                jurisdiction=jurisdiction,
                document_class="statute",
                citation_path=f"{jurisdiction}/statute/{version}",
                body=f"Text of {version}.",
            ),
        ),
    )


def _tree(root: Path) -> dict[str, bytes | None]:
    """Every path under ``root``, with a file's bytes and None for a directory."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in sorted(root.rglob("*"))
    }


def _refuse_fetch(*_args, **_kwargs):
    raise AssertionError("require_materialized ran for a refused base scope")


@pytest.mark.parametrize(
    ("source_versions", "target_version"),
    [
        pytest.param(("tracked-base", "primary-one"), "consolidated", id="base-source"),
        pytest.param(("primary-one", "primary-two"), "tracked-base", id="base-target"),
    ],
)
def test_refuses_a_tracked_base_scope_before_fetching(
    tmp_path, monkeypatch, source_versions, target_version
):
    store = CorpusArtifactStore(tmp_path / "corpus")
    for version in source_versions:
        _write_example_scope(store, version)
    releases_dir = _write_layered_selector(tmp_path / "releases")
    before = _tree(store.root)
    monkeypatch.setattr(consolidate_module, "require_materialized", _refuse_fetch)

    with pytest.raises(
        ValueError,
        match=(
            r"^base scopes are carried unchanged and cannot be consolidated: "
            r"us-example/statute/tracked-base$"
        ),
    ):
        consolidate_release_scopes(
            base=store.root,
            jurisdiction="us-example",
            document_class="statute",
            source_versions=source_versions,
            target_version=target_version,
            releases_dir=releases_dir,
        )

    # Nothing was created, moved or rewritten, and no staging directory is left.
    assert _tree(store.root) == before
    assert not (store.root / "sources/us-example/statute" / target_version).exists()
    assert not store.inventory_path("us-example", "statute", target_version).exists()
    assert not store.provisions_path("us-example", "statute", target_version).exists()
    assert not store.coverage_path("us-example", "statute", target_version).exists()


def test_consolidates_primary_scopes_beside_a_tracked_base(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    releases_dir = _write_layered_selector(tmp_path / "releases")
    # Primary scopes of the pair whose base the selector marks.
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    # The base's version string under another pair names a primary scope.
    _write_example_scope(store, "tracked-base", jurisdiction="us")
    _write_example_scope(store, "primary-one", jurisdiction="us")

    consolidate_release_scopes(
        base=store.root,
        jurisdiction="us-example",
        document_class="statute",
        source_versions=("primary-one", "primary-two"),
        target_version="consolidated",
        releases_dir=releases_dir,
    )
    consolidate_release_scopes(
        base=store.root,
        jurisdiction="us",
        document_class="statute",
        source_versions=("tracked-base", "primary-one"),
        target_version="consolidated",
        releases_dir=releases_dir,
    )

    assert [
        record.citation_path
        for record in load_provisions(
            store.provisions_path("us-example", "statute", "consolidated")
        )
    ] == ["us-example/statute/primary-one", "us-example/statute/primary-two"]
    assert [
        record.citation_path
        for record in load_provisions(store.provisions_path("us", "statute", "consolidated"))
    ] == ["us/statute/tracked-base", "us/statute/primary-one"]


def test_reads_the_repository_selectors_by_default(tmp_path, monkeypatch):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    seen: list[Path] = []

    def recording_tracked_base_scopes(releases_dir: Path) -> frozenset[tuple[str, str, str]]:
        seen.append(releases_dir)
        return frozenset({("us-example", "statute", "primary-two")})

    monkeypatch.setattr(consolidate_module, "tracked_base_scopes", recording_tracked_base_scopes)
    monkeypatch.setattr(consolidate_module, "require_materialized", _refuse_fetch)

    with pytest.raises(
        ValueError, match=r"cannot be consolidated: us-example/statute/primary-two$"
    ):
        consolidate_release_scopes(
            base=store.root,
            jurisdiction="us-example",
            document_class="statute",
            source_versions=("primary-one", "primary-two"),
            target_version="consolidated",
        )

    repository_releases = Path(__file__).resolve().parents[1] / "manifests" / "releases"
    assert seen == [repository_releases]
    assert repository_releases.is_dir()


@pytest.mark.parametrize(
    "checkout",
    [
        pytest.param("other-checkout", id="base-checkout"),
        pytest.param(None, id="no-checkout"),
    ],
)
def test_cli_reads_the_selectors_of_the_checkout_holding_base(tmp_path, monkeypatch, checkout):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    asked: list[Path] = []
    seen: list[Path] = []

    def fake_cli_repo(args) -> Path | None:
        asked.append(Path(args.base))
        return None if checkout is None else tmp_path / checkout

    def recording_tracked_base_scopes(releases_dir: Path) -> frozenset[tuple[str, str, str]]:
        seen.append(releases_dir)
        return frozenset({("us-example", "statute", "primary-two")})

    monkeypatch.setattr(consolidate_module, "cli_repo", fake_cli_repo, raising=False)
    monkeypatch.setattr(consolidate_module, "tracked_base_scopes", recording_tracked_base_scopes)
    monkeypatch.setattr(consolidate_module, "require_materialized", _refuse_fetch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "consolidate_release_scopes.py",
            "--base",
            str(store.root),
            "--jurisdiction",
            "us-example",
            "--document-class",
            "statute",
            "--source-version",
            "primary-one",
            "--source-version",
            "primary-two",
            "--target-version",
            "consolidated",
        ],
    )

    if checkout is None:
        # No checkout holds --base or the working directory, so no selector
        # says which scopes are bases: the command line refuses to guess.
        with pytest.raises(SystemExit) as exited:
            consolidate_module.main()
        assert exited.value.code == 2
        assert seen == []
        return
    with pytest.raises(
        ValueError, match=r"cannot be consolidated: us-example/statute/primary-two$"
    ):
        consolidate_module.main()
    assert seen == [tmp_path / "other-checkout" / "manifests" / "releases"]
    assert asked == [store.root]


# Spellings a selector cannot hold that name the files of us-example/statute/tracked-base:
# artifacts.safe_segment strips whitespace and "/" and rewrites "\\" and ":",
# and APFS folds case.
BASE_ALIASES = [
    pytest.param(("us-example", "statute", "tracked-base "), id="trailing-space"),
    pytest.param(("us-example", "statute", " tracked-base"), id="leading-space"),
    pytest.param(("us-example", "statute", "tracked-base\t"), id="trailing-tab"),
    pytest.param(("us-example", "statute", "tracked-base\n"), id="trailing-newline"),
    pytest.param(("us-example", "statute", "tracked-base/"), id="trailing-slash"),
    pytest.param(("us-example", "statute", "tracked:base"), id="colon"),
    pytest.param(("us-example", "statute", "tracked\\base"), id="backslash"),
    pytest.param(("us-example", "statute", "Tracked-Base"), id="upper-case"),
    pytest.param(("us-example ", "statute", "tracked-base"), id="jurisdiction-alias"),
    pytest.param(("us-example", "statute/", "tracked-base"), id="document-class-alias"),
]


@pytest.mark.parametrize("role", ["source", "target"])
@pytest.mark.parametrize("alias", BASE_ALIASES)
def test_refuses_a_spelling_that_names_a_tracked_base(tmp_path, monkeypatch, alias, role):
    jurisdiction, document_class, version = alias
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    releases_dir = _write_layered_selector(tmp_path / "releases")
    before = _tree(store.root)
    monkeypatch.setattr(consolidate_module, "require_materialized", _refuse_fetch)
    if role == "source":
        source_versions = (version, "primary-one")
        target_version = "consolidated"
    else:
        source_versions = ("primary-one", "primary-two")
        target_version = version

    # The name is refused before any path is built or anything is fetched.
    with pytest.raises(ValueError, match=r"^not a canonical scope: "):
        consolidate_release_scopes(
            base=store.root,
            jurisdiction=jurisdiction,
            document_class=document_class,
            source_versions=source_versions,
            target_version=target_version,
            releases_dir=releases_dir,
        )

    assert _tree(store.root) == before
    assert not (store.root / "sources/us-example/statute/tracked-base").exists()
    assert not store.inventory_path("us-example", "statute", "tracked-base").exists()
    assert not store.provisions_path("us-example", "statute", "tracked-base").exists()
    assert not store.coverage_path("us-example", "statute", "tracked-base").exists()


@pytest.mark.parametrize("target_version", ["tracked-base ", "tracked-base/"])
def test_writes_nothing_at_a_tracked_base_path_through_an_alias(tmp_path, target_version):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    releases_dir = _write_layered_selector(tmp_path / "releases")

    # With the real fetch step: the alias would otherwise write the base's files.
    with pytest.raises(ValueError, match=r"^not a canonical scope: "):
        consolidate_release_scopes(
            base=store.root,
            jurisdiction="us-example",
            document_class="statute",
            source_versions=("primary-one", "primary-two"),
            target_version=target_version,
            releases_dir=releases_dir,
        )

    assert not store.provisions_path("us-example", "statute", "tracked-base").exists()
    assert not store.inventory_path("us-example", "statute", "tracked-base").exists()
    assert not store.coverage_path("us-example", "statute", "tracked-base").exists()
    assert not (store.root / "sources/us-example/statute/tracked-base").exists()


@pytest.mark.parametrize("role", ["source", "target"])
def test_refuses_a_spelling_before_reading_the_tracked_selectors(tmp_path, monkeypatch, role):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    monkeypatch.setattr(consolidate_module, "require_materialized", _refuse_fetch)
    if role == "source":
        source_versions = ("tracked-base ", "primary-one")
        target_version = "consolidated"
    else:
        source_versions = ("primary-one", "primary-two")
        target_version = "tracked-base "

    # No selector directory exists, so the spelling refusal can win only if
    # the check runs before tracked_base_scopes reads the directory.
    with pytest.raises(
        ValueError, match=r"^not a canonical scope: 'us-example'/'statute'/'tracked-base ' "
    ):
        consolidate_release_scopes(
            base=store.root,
            jurisdiction="us-example",
            document_class="statute",
            source_versions=source_versions,
            target_version=target_version,
            releases_dir=tmp_path / "missing",
        )


# Finding 1 of round 2: the checkouts that hold the paths consolidation uses. Each
# checkout is built with ``make_checkout`` and commits one selector.
MakeCheckout = Callable[[str, Mapping[str, Mapping[str, object]]], Path]
VERSIONS = ("primary-one", "primary-two")


def _checkout(make_checkout: MakeCheckout, name: str, *, base: str | None = None) -> Path:
    """A checkout whose committed selector marks ``us-example/statute/<base>`` as a base."""
    selector = f"{name}-selector"
    scopes: list[dict[str, str]] = [
        {"document_class": "statute", "jurisdiction": "us-example", "version": "primary-one"}
    ]
    if base is not None:
        scopes.append(
            {
                "document_class": "statute",
                "jurisdiction": "us-example",
                "layer": "base",
                "version": base,
            }
        )
    return make_checkout(name, {selector: {"name": selector, "scopes": scopes}})


def _releases(checkout: Path) -> Path:
    return checkout / "manifests" / "releases"


def _link(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)


def _bytes_under(root: Path) -> dict[str, bytes | None]:
    """Every entry below ``root`` outside ``.git``: a file's bytes, else None."""
    found: dict[str, bytes | None] = {}
    for directory, directories, filenames in os.walk(root):
        directories[:] = [name for name in directories if name != ".git"]
        for name in (*directories, *filenames):
            path = Path(directory, name)
            if name != ".git":
                found[str(path.relative_to(root))] = path.read_bytes() if path.is_file() else None
    return found


def _sources(checkout: Path) -> CorpusArtifactStore:
    store = CorpusArtifactStore(checkout / "data" / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    return store


def _swap_for_link(path: Path, target: Path) -> None:
    """Replace the directory ``path`` with a symlink to ``target``, then forget cached roots."""
    from axiom_corpus.corpus import resolver

    shutil.rmtree(path)
    path.symlink_to(target, target_is_directory=True)
    resolver._repo_root_for_dir.cache_clear()


@pytest.mark.parametrize(
    "case",
    [
        "target-named-after-another-checkouts-base",
        "source-is-another-checkouts-base",
        "coverage-link-target",
        "sources-link-target",
        "link-outside-checkouts",
        "directory-alias",
        "holder-selector-link",
        "source-file-chain",
    ],
)
def test_refuses_a_base_or_an_alias_another_path_holds(tmp_path, monkeypatch, make_checkout, case):
    document_class = "statute"
    target_version = "consolidated"
    if case == "target-named-after-another-checkouts-base":
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", base="consolidated-base")
        _link(a / "data" / "corpus", _sources(b).root)
        target_version = "consolidated-base"
        refused = "us-example/statute/consolidated-base"
    elif case == "source-is-another-checkouts-base":
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", base="primary-two")
        _link(a / "data" / "corpus", _sources(b).root)
        refused = "us-example/statute/primary-two"
    elif case == "coverage-link-target":
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", base="consolidated")
        _sources(a)
        (b / "data" / "corpus" / "coverage").mkdir(parents=True)
        _link(a / "data" / "corpus" / "coverage", b / "data" / "corpus" / "coverage")
        refused = "us-example/statute/consolidated"
    elif case == "sources-link-target":
        # Only A's sources directory leads into B, which marks the target as a base.
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", base="consolidated")
        _sources(a)
        (b / "data" / "corpus").mkdir(parents=True)
        (a / "data" / "corpus" / "sources").rename(b / "data" / "corpus" / "sources")
        _link(a / "data" / "corpus" / "sources", b / "data" / "corpus" / "sources")
        refused = "us-example/statute/consolidated"
    elif case == "link-outside-checkouts":
        a = _checkout(make_checkout, "a")
        shared = CorpusArtifactStore(tmp_path / "shared")
        _write_example_scope(shared, "primary-one")
        _write_example_scope(shared, "primary-two")
        _link(a / "data" / "corpus", shared.root)
        refused = ""
        expected = r"^scope artifact leads through a link outside every axiom-corpus checkout: "
    elif case == "holder-selector-link":
        # The target is named after B's committed base, and B's manifests leads to
        # the manifests of A, whose selectors releases_dir names.
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", base="consolidated-base")
        _link(a / "data" / "corpus", _sources(b).root)
        _swap_for_link(b / "manifests", a / "manifests")
        target_version = "consolidated-base"
        refused = ""
        expected = "^" + re.escape(
            f"selector directory leads through a link: {b / 'manifests'} -> "
        )
    elif case == "source-file-chain":
        # A source version's provisions in A link to B's, and B's to C's.
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b")
        c = _checkout(make_checkout, "c")
        stores = [_sources(x) for x in (a, b, c)]
        for here, there in ((stores[0], stores[1]), (stores[1], stores[2])):
            link = here.provisions_path("us-example", "statute", "primary-one")
            link.unlink()
            link.symlink_to(there.provisions_path("us-example", "statute", "primary-one"))
        link = stores[0].provisions_path("us-example", "statute", "primary-one")
        refused = ""
        expected = (
            "^"
            + re.escape(
                "path leads through a symlinked file at or below a checkout's guarded place: "
                f"{link} (the link is {link}); corpus files are placed as regular files, "
                "never symlinks"
            )
            + "$"
        )
    else:
        a = _checkout(make_checkout, "a", base="primary-two")
        store = _sources(a)
        for kind in ("inventory", "provisions", "sources"):
            _link(
                store.root / kind / "us-example" / "regulation",
                store.root / kind / "us-example" / "statute",
            )
        document_class = "regulation"
        refused = ""
        expected = r"^scope artifact resolves to another path: "
    if refused:
        expected = rf"^base scopes are carried unchanged and cannot be consolidated: {refused}$"
    before = _bytes_under(tmp_path)
    monkeypatch.setattr(consolidate_module, "require_materialized", _refuse_fetch)

    with pytest.raises(ValueError, match=expected):
        consolidate_release_scopes(
            base=a / "data" / "corpus",
            jurisdiction="us-example",
            document_class=document_class,
            source_versions=VERSIONS,
            target_version=target_version,
            releases_dir=_releases(a),
        )

    # Refused before the fetch, and nothing was written in any checkout.
    assert _bytes_under(tmp_path) == before


def test_cli_reads_the_working_directorys_checkout(tmp_path, monkeypatch, make_checkout):
    m = _checkout(make_checkout, "m")
    wt = tmp_path / "wt"
    fixture_git(m, "worktree", "add", "-q", "-b", "feat", str(wt))
    # The worktree's branch commits a selector that marks primary-two as a base.
    payload = {
        "name": "wt-layered",
        "scopes": [
            {
                "document_class": "statute",
                "jurisdiction": "us-example",
                "layer": "base",
                "version": "primary-two",
            }
        ],
    }
    (_releases(wt) / "wt-layered.json").write_text(json.dumps(payload, indent=2) + "\n")
    fixture_git(wt, "add", "--", "manifests")
    fixture_git(wt, "commit", "-q", "-m", "Mark primary-two as a base")
    store = _sources(m)
    before = _bytes_under(tmp_path)
    monkeypatch.setattr(consolidate_module, "require_materialized", _refuse_fetch)
    monkeypatch.chdir(wt)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "consolidate_release_scopes.py",
            "--base",
            str(store.root),
            "--jurisdiction",
            "us-example",
            "--document-class",
            "statute",
            "--source-version",
            "primary-one",
            "--source-version",
            "primary-two",
            "--target-version",
            "consolidated",
        ],
    )

    # --base binds to m, whose HEAD marks nothing; the working directory's does.
    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be consolidated: "
        r"us-example/statute/primary-two$",
    ):
        consolidate_module.main()

    assert _bytes_under(tmp_path) == before


def test_runs_through_a_link_into_a_checkout_that_marks_no_base(tmp_path, make_checkout):
    a = _checkout(make_checkout, "a")
    b = _checkout(make_checkout, "b")
    shared = _sources(b)
    _link(a / "data" / "corpus", shared.root)

    consolidate_release_scopes(
        base=a / "data" / "corpus",
        jurisdiction="us-example",
        document_class="statute",
        source_versions=VERSIONS,
        target_version="consolidated",
        releases_dir=_releases(a),
    )

    assert [
        record.citation_path
        for record in load_provisions(
            shared.provisions_path("us-example", "statute", "consolidated")
        )
    ] == ["us-example/statute/primary-one", "us-example/statute/primary-two"]
