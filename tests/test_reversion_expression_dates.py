from __future__ import annotations

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.reversion_expression_dates import reversion_expression_dates


def test_reversion_repairs_dates_and_preserves_immutable_source_scope(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    source_version = "published-v1"
    target_version = "published-v2"
    source = store.source_path("us", "statute", source_version, "source.xml")
    source_sha256 = store.write_text(source, "<section>Official source.</section>")
    source_path = source.relative_to(store.root).as_posix()
    inventory = (
        SourceInventoryItem(
            citation_path="us/statute/1",
            source_path=source_path,
            sha256=source_sha256,
            metadata={
                "index_source_path": source_path,
                "unrelated": "published-v1",
            },
        ),
        SourceInventoryItem(
            citation_path="us/statute/1/a",
            source_path=source_path,
            sha256=source_sha256,
        ),
    )
    records = (
        ProvisionRecord(
            jurisdiction="us",
            document_class="statute",
            citation_path="us/statute/1",
            body="Parent.",
            id=deterministic_provision_id("us/statute/1", source_version),
            version=source_version,
            source_path=source_path,
            source_as_of="2026-07-18",
            expression_date=None,
            metadata={
                "index_source_path": source_path,
                "nested": {"source_paths": [source_path]},
                "unrelated": "published-v1",
            },
        ),
        ProvisionRecord(
            jurisdiction="us",
            document_class="statute",
            citation_path="us/statute/1/a",
            body="Child.",
            id=deterministic_provision_id("us/statute/1/a", source_version),
            version=source_version,
            source_path=source_path,
            source_as_of="2026-07-18",
            expression_date="not-a-date",
            parent_citation_path="us/statute/1",
            parent_id=deterministic_provision_id("us/statute/1", source_version),
        ),
    )
    store.write_inventory(
        store.inventory_path("us", "statute", source_version), inventory
    )
    store.write_provisions(
        store.provisions_path("us", "statute", source_version), records
    )

    generated = reversion_expression_dates(
        base=store.root,
        jurisdiction="us",
        document_class="statute",
        source_version=source_version,
        target_version=target_version,
    )

    assert len(generated) == 4
    assert load_provisions(
        store.provisions_path("us", "statute", source_version)
    ) == records
    target_inventory = load_source_inventory(
        store.inventory_path("us", "statute", target_version)
    )
    target_records = load_provisions(
        store.provisions_path("us", "statute", target_version)
    )
    assert all(target_version in item.source_path for item in target_inventory)
    assert target_inventory[0].metadata == {
        "index_source_path": (
            f"sources/us/statute/{target_version}/source.xml"
        ),
        "unrelated": "published-v1",
    }
    assert [record.expression_date for record in target_records] == [
        "2026-07-18",
        "2026-07-18",
    ]
    assert target_records[0].id == deterministic_provision_id(
        "us/statute/1", target_version
    )
    assert target_records[1].parent_id == target_records[0].id
    assert target_records[0].metadata == {
        "index_source_path": f"sources/us/statute/{target_version}/source.xml",
        "nested": {
            "source_paths": [f"sources/us/statute/{target_version}/source.xml"]
        },
        "unrelated": "published-v1",
    }
    assert (store.root / target_records[0].source_path).read_bytes() == source.read_bytes()


def test_reversion_rejects_record_without_valid_date_fallback(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    source_version = "published-v1"
    source = store.source_path("us", "statute", source_version, "source.xml")
    source_sha256 = store.write_text(source, "<section>Official source.</section>")
    source_path = source.relative_to(store.root).as_posix()
    store.write_inventory(
        store.inventory_path("us", "statute", source_version),
        [
            SourceInventoryItem(
                citation_path="us/statute/1",
                source_path=source_path,
                sha256=source_sha256,
            )
        ],
    )
    store.write_provisions(
        store.provisions_path("us", "statute", source_version),
        [
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/1",
                body="Official source.",
                version=source_version,
                source_path=source_path,
                source_as_of="not-a-date",
            )
        ],
    )

    with pytest.raises(ValueError, match="no valid source_as_of fallback"):
        reversion_expression_dates(
            base=store.root,
            jurisdiction="us",
            document_class="statute",
            source_version=source_version,
            target_version="published-v2",
        )
