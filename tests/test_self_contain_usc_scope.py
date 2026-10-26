from __future__ import annotations

import json

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.self_contain_usc_scope import self_contain_scope

VERSION = "2026-09-13-test-statute-title-42"


def _record(path: str, parent: str | None, **fields) -> ProvisionRecord:
    return ProvisionRecord(
        jurisdiction="us",
        document_class="statute",
        version=VERSION,
        citation_path=path,
        body=fields.pop("body", f"Body of {path}."),
        parent_citation_path=parent,
        parent_id=deterministic_provision_id(parent) if parent else None,
        metadata={"kind": "section"},
        **fields,
    )


def _write_scope(store: CorpusArtifactStore, records: tuple[ProvisionRecord, ...]) -> None:
    source = store.source_path("us", "statute", VERSION, "uslm/usc42.xml")
    sha256 = store.write_text(source, "<uscDoc />")
    source_path = source.relative_to(store.root).as_posix()
    store.write_inventory(
        store.inventory_path("us", "statute", VERSION),
        [
            SourceInventoryItem(
                citation_path=r.citation_path, source_path=source_path, sha256=sha256
            )
            for r in records
        ],
    )
    store.write_provisions(store.provisions_path("us", "statute", VERSION), records)


def test_detaches_only_parents_missing_from_the_scope(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    section = _record("us/statute/42/1786", "us/statute/42", kind="section")
    subsection = _record("us/statute/42/1786/a", "us/statute/42/1786", kind="subsection")
    orphan_paragraph = _record(
        "us/statute/42/1396a/a/17", "us/statute/42/1396a/a", kind="paragraph"
    )
    _write_scope(store, (section, subsection, orphan_paragraph))

    report = self_contain_scope(
        store.root, jurisdiction="us", document_class="statute", version=VERSION
    )

    assert report["detached_rows"] == 2
    assert report["detached_parents"] == {"us/statute/42": 1, "us/statute/42/1396a/a": 1}
    assert report["coverage_complete"] is True
    by_path = {
        r.citation_path: r for r in load_provisions(store.provisions_path("us", "statute", VERSION))
    }
    root = by_path["us/statute/42/1786"]
    assert root.parent_citation_path is None and root.parent_id is None
    assert root.metadata["self_contained_root"] is True
    assert root.metadata["detached_parent_citation_path"] == "us/statute/42"
    kept = by_path["us/statute/42/1786/a"]
    assert kept.parent_citation_path == "us/statute/42/1786"
    assert kept.parent_id == deterministic_provision_id("us/statute/42/1786")
    assert "self_contained_root" not in (kept.metadata or {})
    coverage = json.loads(store.coverage_path("us", "statute", VERSION).read_text())
    assert coverage["complete"] is True and coverage["provision_count"] == 3


def test_refuses_incomplete_coverage(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    section = _record("us/statute/42/1786", "us/statute/42", kind="section")
    _write_scope(store, (section,))
    store.write_inventory(
        store.inventory_path("us", "statute", VERSION),
        [
            SourceInventoryItem(citation_path="us/statute/42/1786", source_path="x", sha256="0"),
            SourceInventoryItem(citation_path="us/statute/42/1787", source_path="x", sha256="0"),
        ],
    )
    with pytest.raises(ValueError, match="incomplete"):
        self_contain_scope(store.root, jurisdiction="us", document_class="statute", version=VERSION)
