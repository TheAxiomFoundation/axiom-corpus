from __future__ import annotations

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.compose_scope_versions import compose_scope_versions


def _write_scope(
    store: CorpusArtifactStore,
    version: str,
    citation_paths: list[str],
    *,
    parent: dict[str, str] | None = None,
) -> tuple[tuple[SourceInventoryItem, ...], tuple[ProvisionRecord, ...]]:
    source = store.source_path("de", "statute", version, f"{version}-source.xml")
    source_sha256 = store.write_text(source, f"<doc>{version}</doc>")
    source_path = source.relative_to(store.root).as_posix()
    parent = parent or {}
    inventory = tuple(
        SourceInventoryItem(
            citation_path=citation_path,
            source_path=source_path,
            sha256=source_sha256,
        )
        for citation_path in citation_paths
    )
    records = tuple(
        ProvisionRecord(
            jurisdiction="de",
            document_class="statute",
            citation_path=citation_path,
            body=f"Body of {citation_path}.",
            id=deterministic_provision_id(citation_path, version),
            version=version,
            source_path=source_path,
            source_as_of="2026-07-21",
            expression_date="2026-07-21",
            parent_citation_path=parent.get(citation_path),
            parent_id=(
                deterministic_provision_id(parent[citation_path], version)
                if citation_path in parent
                else None
            ),
        )
        for citation_path in citation_paths
    )
    store.write_inventory(store.inventory_path("de", "statute", version), inventory)
    store.write_provisions(store.provisions_path("de", "statute", version), records)
    return inventory, records


def test_compose_concatenates_and_rewrites_versions(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _, base_records = _write_scope(
        store,
        "wave-1",
        ["de/statute/estg", "de/statute/estg/66"],
        parent={"de/statute/estg/66": "de/statute/estg"},
    )
    _write_scope(store, "wave-2", ["de/statute/act-449/stefeg"])

    generated = compose_scope_versions(
        base=store.root,
        jurisdiction="de",
        document_class="statute",
        source_versions=["wave-1", "wave-2"],
        target_version="composed",
    )

    assert len(generated) == 4
    # Constituent artifacts stay untouched.
    assert (
        load_provisions(store.provisions_path("de", "statute", "wave-1"))
        == base_records
    )
    target_inventory = load_source_inventory(
        store.inventory_path("de", "statute", "composed")
    )
    target_records = load_provisions(store.provisions_path("de", "statute", "composed"))
    assert [item.citation_path for item in target_inventory] == [
        "de/statute/estg",
        "de/statute/estg/66",
        "de/statute/act-449/stefeg",
    ]
    assert all(item.source_path.startswith("sources/de/statute/composed/") for item in target_inventory)
    assert {record.version for record in target_records} == {"composed"}
    assert target_records[0].id == deterministic_provision_id(
        "de/statute/estg", "composed"
    )
    assert target_records[1].parent_id == target_records[0].id
    assert target_records[2].id == deterministic_provision_id(
        "de/statute/act-449/stefeg", "composed"
    )
    # Source files from every constituent are present under the composed tree.
    composed_sources = sorted(
        path.name
        for path in (store.root / "sources" / "de" / "statute" / "composed").rglob("*")
        if path.is_file()
    )
    assert composed_sources == ["wave-1-source.xml", "wave-2-source.xml"]


def test_compose_rejects_duplicate_citation_paths(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_scope(store, "wave-1", ["de/statute/estg"])
    _write_scope(store, "wave-2", ["de/statute/estg"])

    with pytest.raises(ValueError, match="duplicate inventory citation_path"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="composed",
        )


def test_compose_rejects_existing_target_and_reused_version(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_scope(store, "wave-1", ["de/statute/estg"])
    _write_scope(store, "wave-2", ["de/statute/solzg-1995"])

    with pytest.raises(ValueError, match="target version must differ"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="wave-2",
        )
    with pytest.raises(ValueError, match="at least two source versions"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1"],
            target_version="composed",
        )
    compose_scope_versions(
        base=store.root,
        jurisdiction="de",
        document_class="statute",
        source_versions=["wave-1", "wave-2"],
        target_version="composed",
    )
    with pytest.raises(ValueError, match="target artifact already exists"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="composed",
        )


def test_compose_rejects_colliding_source_files(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    for version, citation_path in (
        ("wave-1", "de/statute/estg"),
        ("wave-2", "de/statute/solzg-1995"),
    ):
        source = store.source_path("de", "statute", version, "same-name.xml")
        source_sha256 = store.write_text(source, f"<doc>{version}</doc>")
        source_path = source.relative_to(store.root).as_posix()
        store.write_inventory(
            store.inventory_path("de", "statute", version),
            [
                SourceInventoryItem(
                    citation_path=citation_path,
                    source_path=source_path,
                    sha256=source_sha256,
                )
            ],
        )
        store.write_provisions(
            store.provisions_path("de", "statute", version),
            [
                ProvisionRecord(
                    jurisdiction="de",
                    document_class="statute",
                    citation_path=citation_path,
                    body="Body.",
                    id=deterministic_provision_id(citation_path, version),
                    version=version,
                    source_path=source_path,
                    source_as_of="2026-07-21",
                    expression_date="2026-07-21",
                )
            ],
        )

    with pytest.raises(ValueError, match="source file collides"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="composed",
        )
