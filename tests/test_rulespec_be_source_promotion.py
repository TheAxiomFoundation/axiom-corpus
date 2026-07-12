"""Fail-closed checks for the RuleSpec Belgium corpus promotion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/corpus"
MIGRATION_PATH = ROOT / "manifests/migrations/rulespec-be-source-promotion.json"
NAMED_RELEASE_PATH = ROOT / "manifests/releases/be-rulespec-current.json"
CURRENT_RELEASE_PATH = ROOT / "manifests/releases/current.json"
VERSION = "2026-07-10-be-rulespec-source-promotion"
REQUIRED_ROW_FIELDS = {
    "id",
    "jurisdiction",
    "document_class",
    "version",
    "citation_path",
    "source_path",
    "source_url",
    "source_as_of",
    "expression_date",
}
ALLOWED_CHANGED_FIELDS = {
    "citation_label",
    "citation_path",
    "document_class",
    "expression_date",
    "id",
    "jurisdiction",
    "kind",
    "language",
    "parent_id",
    "parent_citation_path",
    "source_document_id",
    "source_id",
    "source_path",
    "source_as_of",
    "version",
}
LOCAL_CHANGED_FIELDS = {
    "citation_path",
    "expression_date",
    "id",
    "parent_id",
    "parent_citation_path",
    "source_as_of",
    "source_path",
    "version",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _body_sha256(body: object) -> str | None:
    return _sha256(body.encode("utf-8")) if isinstance(body, str) else None


def _canonical_row_sha256(row: dict[str, object]) -> str:
    encoded = json.dumps(
        row,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return _sha256(encoded)


def _release_rows(
    release: ReleaseManifest,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    rows: list[dict[str, object]] = []
    for scope in release.scopes:
        path = (
            BASE
            / "provisions"
            / scope.jurisdiction
            / scope.document_class
            / f"{scope.version}.jsonl"
        )
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    by_citation = {str(row["citation_path"]): row for row in rows}
    assert len(by_citation) == len(rows)
    return rows, by_citation


def test_rulespec_be_named_release_is_exact_current_subset() -> None:
    named = ReleaseManifest.load(NAMED_RELEASE_PATH)
    current = ReleaseManifest.load(CURRENT_RELEASE_PATH)

    assert named.name == "be-rulespec-current"
    assert len(named.scopes) == 13
    assert {scope.version for scope in named.scopes} == {VERSION}
    assert set(named.scope_keys) == {
        scope.key
        for scope in current.scopes
        if scope.jurisdiction == "be" or scope.jurisdiction.startswith("be-")
    }


def test_rulespec_be_named_release_passes_strict_quality_gate() -> None:
    release = ReleaseManifest.load(NAMED_RELEASE_PATH)
    report = validate_release(BASE, release, strict_warnings=True)

    assert report.ok, report.to_mapping()
    assert report.error_count == 0
    assert report.warning_count == 0


def test_rulespec_be_promotion_is_lossless_and_unambiguous() -> None:
    migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
    release = ReleaseManifest.load(NAMED_RELEASE_PATH)
    rows, by_citation = _release_rows(release)
    mappings = migration["row_mappings"]
    parents = migration["derived_parent_rows"]

    assert migration["schema_version"] == "axiom-corpus/source-promotion/v1"
    assert migration["source"] == {
        "corpus_commit": "06f4d429fd5d3bbc1426217c4b9396abbcccfed3",
        "corpus_repository": "https://github.com/TheAxiomFoundation/axiom-corpus",
        "rulespec_commit": "87154df73fe11aabb4ab9c6c605272d73b391a39",
        "rulespec_repository": "https://github.com/TheAxiomFoundation/rulespec-be",
    }
    assert migration["counts"] == {
        "current_external_files_divergent": 1,
        "current_external_files_identical": 9,
        "current_external_files_missing": 2,
        "derived_parent_rows": 48,
        "rulespec_citation_references": 2147,
        "rulespec_local_body_rows": 116,
        "rulespec_local_source_files": 12,
        "rulespec_local_source_rows": 125,
        "rulespec_unique_citations": 453,
        "selected_source_rows": 578,
        "source_snapshots": 55,
        "target_body_rows": 520,
        "target_rows": 626,
        "target_scopes": 13,
    }
    assert len(rows) == 626
    assert len({row["id"] for row in rows}) == len(rows)
    assert len(
        {
            (
                mapping["source_repository"],
                mapping["source_file"],
                mapping["source_line"],
            )
            for mapping in mappings
        }
    ) == 578
    assert {mapping["target_citation_path"] for mapping in mappings}.isdisjoint(
        {parent["target_citation_path"] for parent in parents}
    )

    for row in rows:
        assert row.keys() >= REQUIRED_ROW_FIELDS
        assert row["version"] == VERSION
        assert all(isinstance(row[field], str) and row[field] for field in REQUIRED_ROW_FIELDS)

    for mapping in mappings:
        target = by_citation[mapping["target_citation_path"]]
        assert set(mapping["changed_fields"]) <= ALLOWED_CHANGED_FIELDS
        assert _canonical_row_sha256(target) == mapping["target_row_sha256"]
        assert _body_sha256(target.get("body")) == mapping["target_body_sha256"]
        assert mapping["source_body_sha256"] == mapping["target_body_sha256"]
        assert mapping["target_source_url"] == target["source_url"]
        assert mapping["target_source_path"] == target["source_path"]
        if mapping["source_url"]:
            assert mapping["source_url"] == mapping["target_source_url"]
        if mapping["source_path"] and "source_path" not in mapping["changed_fields"]:
            assert mapping["source_path"] == mapping["target_source_path"]

    local_mappings = [
        mapping
        for mapping in mappings
        if mapping["source_repository"]
        == "https://github.com/TheAxiomFoundation/rulespec-be"
    ]
    assert len(local_mappings) == 125
    assert all(
        set(mapping["changed_fields"]) <= LOCAL_CHANGED_FIELDS
        and mapping["source_body_sha256"] == mapping["target_body_sha256"]
        and mapping["source_url"] == mapping["target_source_url"]
        and (
            mapping["source_path"] == mapping["target_source_path"]
            or "source_path" in mapping["changed_fields"]
        )
        for mapping in local_mappings
    )

    for parent in parents:
        target = by_citation[parent["target_citation_path"]]
        assert _canonical_row_sha256(target) == parent["target_row_sha256"]
        assert target["body"] is None
        assert target["source_url"] == parent["source_url"]
        assert target["source_path"] == parent["source_path"]
        assert set(parent["component_citations"]) <= by_citation.keys()


def test_rulespec_be_release_covers_every_declared_reference() -> None:
    migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
    release = ReleaseManifest.load(NAMED_RELEASE_PATH)
    _rows, by_citation = _release_rows(release)
    inventory = migration["rulespec_reference_inventory"]

    assert len(inventory) == 453
    assert len({item["rulespec_citation_path"] for item in inventory}) == 453
    assert sum(item["reference_count"] for item in inventory) == 2147
    for item in inventory:
        target = by_citation[item["target_citation_path"]]
        assert _canonical_row_sha256(target) == item["target_row_sha256"]


def test_rulespec_be_source_snapshots_and_signed_manifests_are_complete() -> None:
    migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
    release = ReleaseManifest.load(NAMED_RELEASE_PATH)
    snapshots = migration["source_snapshots"]

    assert len(snapshots) == 55
    assert sum(item["snapshot_mode"] == "full_file" for item in snapshots) == 13
    assert sum(item["snapshot_mode"] == "selected_raw_lines" for item in snapshots) == 42
    snapshot_paths = {item["snapshot_path"] for item in snapshots}
    assert {
        mapping["promotion_input_snapshot"]
        for mapping in migration["row_mappings"]
    } == snapshot_paths
    for item in snapshots:
        path = ROOT / item["snapshot_path"]
        assert path.is_file()
        assert path.stat().st_size == item["snapshot_bytes"]
        assert _sha256(path.read_bytes()) == item["snapshot_sha256"]

    for scope in release.scopes:
        manifest_path = (
            ROOT
            / ".axiom/ingest-manifests"
            / scope.jurisdiction
            / scope.document_class
            / f"{VERSION}.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = {
            (
                BASE
                / artifact_class
                / scope.jurisdiction
                / scope.document_class
                / f"{VERSION}{'.jsonl' if artifact_class == 'provisions' else '.json'}"
            ).relative_to(ROOT).as_posix()
            for artifact_class in ("coverage", "inventory", "provisions")
        }
        expected.update(
            path.relative_to(ROOT).as_posix()
            for path in (
                BASE
                / "sources"
                / scope.jurisdiction
                / scope.document_class
                / VERSION
            ).rglob("*")
            if path.is_file()
        )
        applied = {item["path"]: item["sha256"] for item in manifest["applied_files"]}
        assert applied.keys() == expected
        assert all(_sha256((ROOT / path).read_bytes()) == sha for path, sha in applied.items())


def test_rulespec_be_aviq_collision_is_explicitly_disambiguated() -> None:
    migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
    collision = migration["canonicalization"]["citation_collision"]
    renamed = [
        mapping
        for mapping in migration["row_mappings"]
        if "citation_path" in mapping["changed_fields"]
    ]

    assert collision["old_parent"] == (
        "be-wal/guidance/aviq/family-benefits/amount-scale-2025-02"
    )
    assert collision["new_parent"] == (
        "be-wal/guidance/aviq/family-benefits/consolidated-amount-scale-2025-02"
    )
    assert len(renamed) == 3
    assert {mapping["source_citation_path"].rsplit("/", 1)[-1] for mapping in renamed} == {
        "page-1",
        "page-4",
        "page-6",
    }
    assert all(
        mapping["source_citation_path"].startswith(collision["old_parent"] + "/")
        and mapping["target_citation_path"].startswith(collision["new_parent"] + "/")
        and {"id", "parent_id"} <= set(mapping["changed_fields"])
        for mapping in renamed
    )
