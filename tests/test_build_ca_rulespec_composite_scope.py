from __future__ import annotations

import json
from dataclasses import replace

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.build_ca_rulespec_composite_scope import (
    build_ca_rulespec_composite_scope,
    promote_program_roots,
)


def test_promotes_program_body_to_attested_primary_document(tmp_path) -> None:
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "ca-composite"
    root_path = "ca/policy/cra/example"
    source_path = store.source_path("ca", "policy", version, "example.txt")
    source_sha256 = store.write_text(source_path, "Primary text")
    relative_source_path = source_path.relative_to(store.root).as_posix()
    root = ProvisionRecord(
        jurisdiction="ca",
        document_class="policy",
        citation_path=root_path,
        body="Primary text",
        id=deterministic_provision_id(root_path, version),
        version=version,
        source_path=relative_source_path,
        level=1,
        ordinal=1,
        kind="document",
    )
    values = ProvisionRecord(
        jurisdiction="ca",
        document_class="policy",
        citation_path=f"{root_path}/values",
        body="Worksheet text",
        id=deterministic_provision_id(f"{root_path}/values", version),
        version=version,
        source_path=relative_source_path,
        parent_citation_path=root_path,
        parent_id=root.id,
        level=2,
        ordinal=2,
        kind="section",
    )
    inventory = (
        SourceInventoryItem(
            citation_path=root_path,
            source_path=relative_source_path,
            sha256=source_sha256,
        ),
        SourceInventoryItem(
            citation_path=values.citation_path,
            source_path=relative_source_path,
            sha256=source_sha256,
        ),
    )
    store.write_inventory(store.inventory_path("ca", "policy", version), inventory)
    store.write_provisions(store.provisions_path("ca", "policy", version), (root, values))

    promote_program_roots(base=store.root, version=version, citation_paths=(root_path,))

    records = {
        record.citation_path: record
        for record in load_provisions(store.provisions_path("ca", "policy", version))
    }
    primary_path = f"{root_path}/primary-document"
    assert records[root_path].body is None
    assert records[primary_path].body == "Primary text"
    assert records[primary_path].parent_citation_path == root_path
    assert records[primary_path].parent_id == deterministic_provision_id(root_path, version)
    assert records[f"{root_path}/values"] == values
    inventory_paths = {
        item.citation_path
        for item in load_source_inventory(store.inventory_path("ca", "policy", version))
    }
    assert inventory_paths == {root_path, primary_path, f"{root_path}/values"}


def test_preserves_existing_bodyless_composite_root(tmp_path) -> None:
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "ca-composite"
    root_path = "ca/policy/cra/example"
    source_path = store.source_path("ca", "policy", version, "example.txt")
    source_sha256 = store.write_text(source_path, "Document text")
    relative_source_path = source_path.relative_to(store.root).as_posix()
    root = ProvisionRecord(
        jurisdiction="ca",
        document_class="policy",
        citation_path=root_path,
        body=None,
        id=deterministic_provision_id(root_path, version),
        version=version,
        source_path=relative_source_path,
    )
    document = replace(
        root,
        citation_path=f"{root_path}/document-1",
        body="Document text",
        id=deterministic_provision_id(f"{root_path}/document-1", version),
        parent_citation_path=root_path,
        parent_id=root.id,
    )
    inventory = tuple(
        SourceInventoryItem(
            citation_path=record.citation_path,
            source_path=relative_source_path,
            sha256=source_sha256,
        )
        for record in (root, document)
    )
    store.write_inventory(store.inventory_path("ca", "policy", version), inventory)
    store.write_provisions(store.provisions_path("ca", "policy", version), (root, document))

    promote_program_roots(base=store.root, version=version, citation_paths=(root_path,))

    records = load_provisions(store.provisions_path("ca", "policy", version))
    assert records == (root, document)


def test_rejects_duplicate_supplemental_source_version(tmp_path) -> None:
    selector_path = tmp_path / "selector.json"
    selector_path.write_text(
        json.dumps(
            {
                "name": "ca-test",
                "scopes": [
                    {
                        "jurisdiction": "ca",
                        "document_class": "policy",
                        "version": "source-v1",
                    }
                ],
            }
        )
    )
    contract_path = tmp_path / "citations.json"
    contract_path.write_text(json.dumps({"citation_paths": ["ca/policy/example"]}))

    with pytest.raises(ValueError, match="source versions must be unique"):
        build_ca_rulespec_composite_scope(
            base=tmp_path / "corpus",
            selector_path=selector_path,
            citation_contract_path=contract_path,
            target_version="combined",
            supplemental_versions=("source-v1",),
        )
