from __future__ import annotations

import json
import shutil
from dataclasses import replace

import pytest

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
) -> None:
    source = store.source_path("us", "statute", version, "source.xml")
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
        store.inventory_path("us", "statute", version),
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
        store.provisions_path("us", "statute", version),
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
