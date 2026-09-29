import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile

import pytest

from axiom_corpus.corpus.documents import OfficialDocumentManifest
from axiom_corpus.corpus.ingest_manifests import (
    INGEST_MANIFEST_KEY_ID,
    INGEST_MANIFEST_SCHEMA_VERSION,
    INGEST_MANIFEST_SIGNATURE_ALGORITHM,
    default_ingest_manifest_path,
    sha256_file,
    verify_ingest_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST = REPO_ROOT / "manifests/us-federal-proposal-security-2026.yaml"
RUN_NOTE = "docs/ingest-runs/2026-08-30-federal-proposal-security.md"

MATERIALIZED_SCOPES = {
    ("guidance", "2026-08-30-federal-proposal-security-guidance"): 25,
    ("regulation", "2026-08-30-proposal-security-title-2-part-25"): 16,
    ("regulation", "2026-08-30-proposal-security-title-45-part-604"): 22,
    ("statute", "2026-08-30-proposal-security-title-31"): 72,
    ("statute", "2026-08-30-proposal-security-title-42"): 132,
}

# Official OLRC release point Online@119-102 downloads retained byte-for-byte.
USC_ARCHIVES = {
    "2026-08-30-proposal-security-title-31": {
        "title": "31",
        "archive": "olrc/xml_usc31@119-102.zip",
        "archive_sha256": "1cccbcc7e0fe4bc548b970e866dced83a728bca2f3d305f477405f0426735b78",
        "member": "usc31.xml",
        "member_sha256": "254572a738146d41174b64232c98f630e892b8d368d7a1841d3750d8cb102185",
        "sections": {"1352"},
    },
    "2026-08-30-proposal-security-title-42": {
        "title": "42",
        "archive": "olrc/xml_usc42@119-102.zip",
        "archive_sha256": "31929c28f117362ac8788607242795769b05ed7726f07e4ed3b1786f39655ce7",
        "member": "usc42.xml",
        "member_sha256": "b72955590abe55bdbd1ce5d13c5293955a82add9c84fad92c1674ec469e86624",
        "sections": {
            "1862o",
            "6605",
            "19231",
            "19232",
            "19233",
            "19234",
            "19235",
            "19237",
        },
    },
}

# The rebuild command each signed manifest must record, by document class.
EXPECTED_COMMAND_FRAGMENTS = {
    "guidance": (
        "axiom-corpus-ingest extract-official-documents",
        "--manifest manifests/us-federal-proposal-security-2026.yaml",
        RUN_NOTE,
    ),
    "regulation": (
        "axiom-corpus-ingest extract-ecfr",
        "--as-of 2026-08-27",
        "--include-appendices",
        RUN_NOTE,
    ),
    "statute": (
        "axiom-corpus-ingest extract-usc",
        "--source-zip",
        "scripts/self_contain_usc_scope.py",
        RUN_NOTE,
    ),
}


def _scope_artifacts(document_class: str, version: str) -> set[str]:
    source_root = CORPUS_ROOT / "sources" / "us" / document_class / version
    paths = {path for path in source_root.rglob("*") if path.is_file()}
    paths |= {
        CORPUS_ROOT / "inventory" / "us" / document_class / f"{version}.json",
        CORPUS_ROOT / "provisions" / "us" / document_class / f"{version}.jsonl",
        CORPUS_ROOT / "coverage" / "us" / document_class / f"{version}.json",
    }
    return {path.relative_to(REPO_ROOT).as_posix() for path in paths}


def _ingest_manifest(document_class: str, version: str) -> dict:
    path = REPO_ROOT / default_ingest_manifest_path(
        jurisdiction="us",
        document_class=document_class,
        version=version,
    )
    return json.loads(path.read_text())


def test_federal_proposal_security_manifest_has_stable_scoped_sources():
    manifest = OfficialDocumentManifest.load(MANIFEST)
    manifest.require_unique_sources()

    assert len(manifest.documents) == 6
    by_id = {document.source_id: document for document in manifest.documents}

    chapter_i = by_id["nsf-pappg-24-1-chapter-i-submission-security"]
    assert chapter_i.extraction is not None
    assert [
        row["section_label"] for row in chapter_i.extraction["anchor_ranges"]
    ] == ["submission-instructions", "uei-and-sam"]

    supplement_2 = by_id["nsf-pappg-24-1-supplement-2-dmsp"]
    assert supplement_2.extraction is not None
    assert "s" in supplement_2.extraction["html_drop_selectors"]
    assert supplement_2.extraction["section_label"] == "dmsp"

    notice = by_id["nsf-important-notice-149-proposal-security"]
    assert notice.extraction is not None
    assert notice.extraction["stop_text_pattern"] == r"^5\."

    faq = by_id["nsf-important-notice-149-implementation-faq"]
    assert faq.extraction is not None
    assert len(faq.extraction["anchor_ranges"]) == 9

    tip = by_id["nsf-tip-person-entity-of-concern-prohibition"]
    assert tip.extraction is not None
    assert tip.extraction["section_label"] == "implementation"
    assert tip.metadata is not None
    assert tip.metadata["dynamic_external_lists"] is True
    assert tip.metadata["prohibited_entity_names_must_not_be_encoded"] is True


def test_materialized_federal_proposal_security_scopes_are_self_contained():
    for (document_class, version), expected_count in MATERIALIZED_SCOPES.items():
        inventory_path = CORPUS_ROOT / f"inventory/us/{document_class}/{version}.json"
        provisions_path = CORPUS_ROOT / f"provisions/us/{document_class}/{version}.jsonl"
        coverage_path = CORPUS_ROOT / f"coverage/us/{document_class}/{version}.json"

        inventory = json.loads(inventory_path.read_text())["items"]
        provisions = [json.loads(line) for line in provisions_path.read_text().splitlines()]
        coverage = json.loads(coverage_path.read_text())

        inventory_paths = {item["citation_path"] for item in inventory}
        provision_paths = {item["citation_path"] for item in provisions}
        assert len(inventory) == expected_count
        assert len(inventory_paths) == expected_count
        assert len(provisions) == expected_count
        assert provision_paths == inventory_paths
        assert coverage["complete"] is True
        assert coverage["missing_from_provisions"] == []
        assert coverage["extra_provisions"] == []

        # Every parent link resolves inside the scope.
        for row in provisions:
            parent = row.get("parent_citation_path")
            assert parent is None or parent in provision_paths, row["citation_path"]

        for item in inventory:
            source_path = CORPUS_ROOT / item["source_path"]
            assert source_path.is_file(), source_path
            assert hashlib.sha256(source_path.read_bytes()).hexdigest() == item["sha256"]


def test_us_code_scopes_retain_the_official_release_point_zip():
    for version, expected in USC_ARCHIVES.items():
        title = expected["title"]
        source_root = CORPUS_ROOT / "sources/us/statute" / version
        assert sorted(
            path.relative_to(source_root).as_posix()
            for path in source_root.rglob("*")
            if path.is_file()
        ) == [expected["archive"]]
        archive = source_root / expected["archive"]
        assert sha256_file(archive) == expected["archive_sha256"]
        with ZipFile(archive) as zipped:
            assert [info.filename for info in zipped.infolist()] == [expected["member"]]
            member_digest = hashlib.sha256()
            with zipped.open(expected["member"]) as member:
                while chunk := member.read(1024 * 1024):
                    member_digest.update(chunk)
        assert member_digest.hexdigest() == expected["member_sha256"]

        inventory = json.loads(
            (CORPUS_ROOT / f"inventory/us/statute/{version}.json").read_text()
        )["items"]
        provisions = [
            json.loads(line)
            for line in (CORPUS_ROOT / f"provisions/us/statute/{version}.jsonl")
            .read_text()
            .splitlines()
        ]
        source_key = f"sources/us/statute/{version}/{expected['archive']}"
        for record in [*inventory, *provisions]:
            assert record["source_path"] == source_key
            assert record["source_format"] == "uslm-xml"
            assert record["metadata"]["source_archive_member"] == expected["member"]
            assert record["metadata"]["publication_name"] == "Online@119-102"
        for item in inventory:
            assert item["sha256"] == expected["archive_sha256"]

        # Section rows are detached roots; the released title row is not duplicated.
        paths = {row["citation_path"] for row in provisions}
        assert f"us/statute/{title}" not in paths
        roots = [row for row in provisions if row.get("parent_citation_path") is None]
        assert {row["citation_path"] for row in roots} == {
            f"us/statute/{title}/{section}" for section in expected["sections"]
        }
        for row in roots:
            assert row["kind"] == "section"
            assert row["metadata"]["self_contained_root"] is True
            assert row["metadata"]["detached_parent_citation_path"] == f"us/statute/{title}"


def test_federal_proposal_security_scopes_carry_signed_ingest_manifests():
    for (document_class, version), expected_count in MATERIALIZED_SCOPES.items():
        manifest = _ingest_manifest(document_class, version)

        assert manifest["schema_version"] == INGEST_MANIFEST_SCHEMA_VERSION
        assert manifest["jurisdiction"] == "us"
        assert manifest["document_class"] == document_class
        assert manifest["version"] == version
        assert manifest["reasoning_logs"] == []
        assert manifest["coverage"] == {
            "complete": True,
            "source_count": expected_count,
            "provision_count": expected_count,
            "matched_count": expected_count,
            "missing_count": 0,
            "extra_count": 0,
        }
        command = manifest["command"]["text"]
        for fragment in EXPECTED_COMMAND_FRAGMENTS[document_class]:
            assert fragment in command, (version, fragment)

        git = manifest["axiom_corpus_git"]
        assert git["root"] == "."
        assert git["dirty_tracked"] is False
        assert len(git["commit"]) == 40

        signature = manifest["signature"]
        assert signature["algorithm"] == INGEST_MANIFEST_SIGNATURE_ALGORITHM
        assert signature["key_id"] == INGEST_MANIFEST_KEY_ID
        assert signature["value"]

        # The manifest attests exactly the scope's artifacts, at their committed bytes.
        applied = {entry["path"]: entry for entry in manifest["applied_files"]}
        assert set(applied) == _scope_artifacts(document_class, version)
        for path, entry in applied.items():
            assert "deleted" not in entry, path
            assert entry["sha256"] == sha256_file(REPO_ROOT / path), path


def test_federal_proposal_security_ingest_manifests_are_authenticated():
    public_key = os.environ.get("AXIOM_CORPUS_INGEST_PUBLIC_KEY")
    if not public_key:
        if os.environ.get("CI"):
            pytest.fail("AXIOM_CORPUS_INGEST_PUBLIC_KEY is required in CI")
        pytest.skip("AXIOM_CORPUS_INGEST_PUBLIC_KEY is required for signature verification")

    issues = {
        version: verify_ingest_manifest(
            _ingest_manifest(document_class, version),
            public_key=public_key,
            repo=REPO_ROOT,
            head_ref="HEAD",
        )
        for document_class, version in MATERIALIZED_SCOPES
    }
    assert issues == {version: [] for _document_class, version in MATERIALIZED_SCOPES}
