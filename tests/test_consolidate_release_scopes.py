from __future__ import annotations

import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import scripts.consolidate_release_scopes as consolidate_module
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.consolidate_release_scopes import consolidate_release_scopes


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
