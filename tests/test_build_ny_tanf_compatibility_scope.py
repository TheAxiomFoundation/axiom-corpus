from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from axiom_corpus.corpus.ingest_manifests import sha256_file
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.build_ny_tanf_compatibility_scope import (
    ALIAS_PAGE_NUMBERS,
    ALIASES,
    CURRENT_VERSION,
    DOCUMENT_CLASS,
    JURISDICTION,
    LEGACY_VERSION,
    PAGE_CITATION_PREFIX,
    SOURCE_DOCUMENT_NAME,
    build_ny_tanf_compatibility_scope,
)

REPO = Path(__file__).resolve().parents[1]
TARGET_VERSION = "target-ny-tanf-official-source-recovery-with-aliases"
CURRENT_SOURCE = Path(
    f"data/corpus/sources/{JURISDICTION}/{DOCUMENT_CLASS}/{CURRENT_VERSION}/"
    f"official-documents/{SOURCE_DOCUMENT_NAME}"
)
INPUT_PATHS = (
    Path(f".axiom/ingest-manifests/{JURISDICTION}/{DOCUMENT_CLASS}/{LEGACY_VERSION}.json"),
    Path(f".axiom/ingest-manifests/{JURISDICTION}/{DOCUMENT_CLASS}/{CURRENT_VERSION}.json"),
    Path(f"data/corpus/inventory/{JURISDICTION}/{DOCUMENT_CLASS}/{CURRENT_VERSION}.json"),
    Path(f"data/corpus/provisions/{JURISDICTION}/{DOCUMENT_CLASS}/{CURRENT_VERSION}.jsonl"),
    Path(f"data/corpus/provisions/{JURISDICTION}/{DOCUMENT_CLASS}/{LEGACY_VERSION}.jsonl"),
    CURRENT_SOURCE,
)
EXPECTED_OUTPUT_SHA256 = {
    "inventory": "883570c64c4caab0dae9d5c9e7853f08adb5923ef08b4b747e0886ca8a63ff95",
    "provisions": "e2f21bd863508d39521be0f9e18f2166050f30f5cf261fd468f4b58568f9e1e5",
    "coverage": "8fb0d58d63c59f7b34bfce42feecf23853960eb2ff7755f852943b85c0a3e9cf",
}


def _copy_inputs(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    for relative in INPUT_PATHS:
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / relative, destination)
    return repo


def _target_paths(repo: Path) -> tuple[Path, ...]:
    base = repo / "data/corpus"
    return (
        base / f"sources/{JURISDICTION}/{DOCUMENT_CLASS}/{TARGET_VERSION}",
        base / f"inventory/{JURISDICTION}/{DOCUMENT_CLASS}/{TARGET_VERSION}.json",
        base / f"provisions/{JURISDICTION}/{DOCUMENT_CLASS}/{TARGET_VERSION}.jsonl",
        base / f"coverage/{JURISDICTION}/{DOCUMENT_CLASS}/{TARGET_VERSION}.json",
    )


def _rewrite_legacy_provisions(repo: Path, rows: list[dict[str, object]]) -> None:
    path = (
        repo
        / f"data/corpus/provisions/{JURISDICTION}/{DOCUMENT_CLASS}/{LEGACY_VERSION}.jsonl"
    )
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    manifest_path = (
        repo
        / f".axiom/ingest-manifests/{JURISDICTION}/{DOCUMENT_CLASS}/{LEGACY_VERSION}.json"
    )
    manifest = json.loads(manifest_path.read_text())
    relative_text = path.relative_to(repo).as_posix()
    for entry in manifest["applied_files"]:
        if entry["path"] == relative_text:
            entry["sha256"] = sha256_file(path)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def test_real_data_rebuild_is_byte_identical_and_auditable(tmp_path: Path) -> None:
    repo = _copy_inputs(tmp_path)
    before = {relative: sha256_file(repo / relative) for relative in INPUT_PATHS}

    generated = build_ny_tanf_compatibility_scope(
        repo=repo,
        target_version=TARGET_VERSION,
    )

    assert generated == _target_paths(repo)
    assert {relative: sha256_file(repo / relative) for relative in INPUT_PATHS} == before
    _source_dir, inventory_path, provisions_path, coverage_path = generated
    assert sha256_file(inventory_path) == EXPECTED_OUTPUT_SHA256["inventory"]
    assert sha256_file(provisions_path) == EXPECTED_OUTPUT_SHA256["provisions"]
    assert sha256_file(coverage_path) == EXPECTED_OUTPUT_SHA256["coverage"]

    records = load_provisions(provisions_path)
    assert len(records) == len({record.citation_path for record in records}) == 119
    records_by_citation = {record.citation_path: record for record in records}
    for alias, page_numbers in ALIAS_PAGE_NUMBERS.items():
        alias_record = records_by_citation[alias]
        assert alias_record.body == "\n\n".join(
            records_by_citation[f"{PAGE_CITATION_PREFIX}{page}"].body
            for page in page_numbers
        )
        assert alias_record.id == deterministic_provision_id(alias, TARGET_VERSION)
        if alias_record.parent_citation_path:
            assert alias_record.parent_id == deterministic_provision_id(
                alias_record.parent_citation_path,
                TARGET_VERSION,
            )
        metadata = alias_record.metadata or {}
        assert metadata["compatibility_alias"] is True
        assert metadata["compatibility_alias_from_signed_scope"] == LEGACY_VERSION
        assert metadata["compatibility_source_scope"] == CURRENT_VERSION
        assert not str(metadata.get("download_url", "")).startswith("file://")

    inventory = load_source_inventory(inventory_path)
    inventory_by_citation = {item.citation_path: item for item in inventory}
    source_sha256 = sha256_file(repo / CURRENT_SOURCE)
    for alias in ALIASES:
        item = inventory_by_citation[alias]
        assert item.sha256 == source_sha256
        assert item.source_path == (
            f"sources/{JURISDICTION}/{DOCUMENT_CLASS}/{TARGET_VERSION}/"
            f"{CURRENT_VERSION}/official-documents/{SOURCE_DOCUMENT_NAME}"
        )
    copied_source = generated[0] / CURRENT_VERSION / "official-documents" / SOURCE_DOCUMENT_NAME
    assert sha256_file(copied_source) == source_sha256

    coverage = json.loads(coverage_path.read_text())
    assert coverage["complete"] is True
    assert coverage["source_count"] == coverage["provision_count"] == 119
    assert coverage["matched_count"] == 119


def test_rejects_one_byte_alias_drift_before_writing_target(tmp_path: Path) -> None:
    repo = _copy_inputs(tmp_path)
    legacy_path = (
        repo
        / f"data/corpus/provisions/{JURISDICTION}/{DOCUMENT_CLASS}/{LEGACY_VERSION}.jsonl"
    )
    rows = [json.loads(line) for line in legacy_path.read_text().splitlines()]
    alias_row = next(row for row in rows if row["citation_path"] == ALIASES[0])
    alias_row["body"] = str(alias_row["body"]) + "x"
    _rewrite_legacy_provisions(repo, rows)

    with pytest.raises(ValueError, match="exact current-page concatenation"):
        build_ny_tanf_compatibility_scope(repo=repo, target_version=TARGET_VERSION)

    assert not any(path.exists() for path in _target_paths(repo))


def test_rejects_duplicate_manifest_attestation(tmp_path: Path) -> None:
    repo = _copy_inputs(tmp_path)
    manifest_path = (
        repo
        / f".axiom/ingest-manifests/{JURISDICTION}/{DOCUMENT_CLASS}/{CURRENT_VERSION}.json"
    )
    manifest = json.loads(manifest_path.read_text())
    provisions_path = (
        f"data/corpus/provisions/{JURISDICTION}/{DOCUMENT_CLASS}/{CURRENT_VERSION}.jsonl"
    )
    entry = next(row for row in manifest["applied_files"] if row["path"] == provisions_path)
    manifest["applied_files"].append(dict(entry))
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="repeats applied file"):
        build_ny_tanf_compatibility_scope(repo=repo, target_version=TARGET_VERSION)


def test_rejects_manifested_artifact_hash_mismatch(tmp_path: Path) -> None:
    repo = _copy_inputs(tmp_path)
    with (repo / CURRENT_SOURCE).open("ab") as source:
        source.write(b"tamper")

    with pytest.raises(ValueError, match="signed artifact hash mismatch"):
        build_ny_tanf_compatibility_scope(repo=repo, target_version=TARGET_VERSION)


def test_verify_only_accepts_divergent_input_commit_and_writes_nothing(
    tmp_path: Path,
) -> None:
    repo = _copy_inputs(tmp_path)
    manifest_path = (
        repo
        / f".axiom/ingest-manifests/{JURISDICTION}/{DOCUMENT_CLASS}/{CURRENT_VERSION}.json"
    )
    manifest = json.loads(manifest_path.read_text())
    assert manifest["axiom_corpus_git"]["commit"] == (
        "961e980dd5e72617977a80a625d6b414eb386ad2"
    )

    assert (
        build_ny_tanf_compatibility_scope(
            repo=repo,
            target_version=TARGET_VERSION,
            verify_only=True,
        )
        == ()
    )
    assert not any(path.exists() for path in _target_paths(repo))

    build_ny_tanf_compatibility_scope(repo=repo, target_version=TARGET_VERSION)
    assert (
        build_ny_tanf_compatibility_scope(
            repo=repo,
            target_version=TARGET_VERSION,
            verify_only=True,
        )
        == ()
    )


def test_existing_target_is_rejected_without_mutating_inputs(tmp_path: Path) -> None:
    repo = _copy_inputs(tmp_path)
    build_ny_tanf_compatibility_scope(repo=repo, target_version=TARGET_VERSION)
    before = {relative: sha256_file(repo / relative) for relative in INPUT_PATHS}

    with pytest.raises(ValueError, match="target artifact already exists"):
        build_ny_tanf_compatibility_scope(repo=repo, target_version=TARGET_VERSION)

    assert {relative: sha256_file(repo / relative) for relative in INPUT_PATHS} == before
