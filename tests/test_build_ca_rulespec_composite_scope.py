from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import scripts.build_ca_rulespec_composite_scope as ca_module
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


def test_normalizes_empty_composite_root_and_removes_empty_primary_document(
    tmp_path,
) -> None:
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
        body="",
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
    empty_primary = replace(
        root,
        citation_path=f"{root_path}/primary-document",
        id=deterministic_provision_id(f"{root_path}/primary-document", version),
        parent_citation_path=root_path,
        parent_id=root.id,
    )
    inventory = tuple(
        SourceInventoryItem(
            citation_path=record.citation_path,
            source_path=relative_source_path,
            sha256=source_sha256,
        )
        for record in (root, document, empty_primary)
    )
    store.write_inventory(store.inventory_path("ca", "policy", version), inventory)
    store.write_provisions(
        store.provisions_path("ca", "policy", version),
        (root, document, empty_primary),
    )

    promote_program_roots(base=store.root, version=version, citation_paths=(root_path,))

    records = load_provisions(store.provisions_path("ca", "policy", version))
    assert records == (replace(root, body=None), document)
    assert all(not record.citation_path.endswith("/primary-document") for record in records)


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


def test_rejects_additional_citation_already_in_contract(tmp_path) -> None:
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

    with pytest.raises(ValueError, match="citation paths must be unique"):
        build_ca_rulespec_composite_scope(
            base=tmp_path / "corpus",
            selector_path=selector_path,
            citation_contract_path=contract_path,
            target_version="combined",
            additional_citation_paths=("ca/policy/example",),
        )


class _ConsolidateCalledError(Exception):
    def __init__(self, kwargs: dict[str, object]) -> None:
        super().__init__("consolidate_release_scopes called")
        self.kwargs = kwargs


@pytest.mark.parametrize(
    "owner",
    [pytest.param("owner", id="base-checkout"), pytest.param(None, id="no-checkout")],
)
def test_cli_reads_the_selectors_of_the_checkout_holding_base(tmp_path, monkeypatch, owner) -> None:
    selector_path = tmp_path / "selector.json"
    selector_path.write_text(
        json.dumps(
            {
                "name": "ca-test",
                "scopes": [
                    {"jurisdiction": "ca", "document_class": "policy", "version": "source-v1"}
                ],
            }
        )
    )
    contract_path = tmp_path / "citations.json"
    contract_path.write_text(json.dumps({"citation_paths": ["ca/policy/example"]}))

    def stop_at_consolidate(**kwargs: object) -> tuple[()]:
        raise _ConsolidateCalledError(kwargs)

    monkeypatch.setattr(
        ca_module,
        "cli_repo",
        lambda args: None if owner is None else tmp_path / owner,
        raising=False,
    )
    monkeypatch.setattr(ca_module, "consolidate_release_scopes", stop_at_consolidate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_ca_rulespec_composite_scope.py",
            "--base",
            str(tmp_path / "corpus"),
            "--selector",
            str(selector_path),
            "--citation-contract",
            str(contract_path),
            "--target-version",
            "combined",
        ],
    )

    if owner is None:
        with pytest.raises(SystemExit) as exited:
            ca_module.main()
        assert exited.value.code == 2
        return
    with pytest.raises(_ConsolidateCalledError) as called:
        ca_module.main()
    assert called.value.kwargs.get("releases_dir") == tmp_path / "owner" / "manifests" / "releases"
    # The working directory's checkout is read too, as composition and dedup read it.
    assert called.value.kwargs.get("holders_of") == (Path.cwd(),)
