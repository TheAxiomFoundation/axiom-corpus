import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-nd-snap-manual.yaml"
VERSION = "2026-07-21-nd-snap-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources/us-nd/manual" / VERSION / "official-documents"
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-nd/manual" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-nd/manual" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-nd/manual" / f"{VERSION}.json"

EXPECTED_TOPIC_COUNT = 64
EXPECTED_SOURCE_COUNT = 67
EXPECTED_ROW_COUNT = 167
EXPECTED_SOURCE_SET_SHA256 = "2f9676805b6c62545c0f24f6ad3a7b1a4f1ce45c4060c1db0f5ac7bb7b99cddc"
EXPECTED_RELEASE_PDF_SHA256 = "c22c1ba7ed16158f891035792b88895aa588731cc14254510e910529eee97ead"


def _documents() -> list[dict]:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_north_dakota_manifest_matches_the_live_release_boundary() -> None:
    documents = _documents()
    topics = [
        document
        for document in documents
        if document["metadata"]["document_subtype"] == "policy_manual_section"
    ]
    toc = (SOURCE_ROOT / "nd-hhs-snap-manual-toc.js").read_text()
    toc_paths = set(re.findall(r"'(/Content/[^']+\.htm)'", toc))
    manifest_paths = {
        unquote(urlparse(document["source_url"]).path).split("/SNAP", 1)[1]
        for document in topics
    }

    assert len(documents) == EXPECTED_SOURCE_COUNT
    assert len(topics) == EXPECTED_TOPIC_COUNT
    assert len({document["source_id"] for document in documents}) == len(documents)
    assert len({document["citation_path"] for document in documents}) == len(documents)
    assert {document["source_as_of"] for document in documents} == {"2026-07-21"}
    assert {document["expression_date"] for document in documents} == {"2026-06-15"}
    assert all(document["metadata"]["primary_source"] is True for document in documents)
    assert toc_paths == manifest_paths


def test_north_dakota_retains_release_evidence_and_current_policy_text() -> None:
    landing = (SOURCE_ROOT / "nd-hhs-snap-manual-landing.html").read_text()
    release_log = next(SOURCE_ROOT.glob("*release-log*.html")).read_text()
    work_registration = next(
        SOURCE_ROOT.glob("*301-work-registration-overview*.html")
    ).read_text()
    reporting = next(SOURCE_ROOT.glob("*1002-reporting-requirements*.html")).read_text()
    release_pdf = SOURCE_ROOT / "nd-hhs-snap-release-26-5.pdf"

    assert "Last published" in landing and "Jun 15, 2026" in landing
    assert "Current Release: 26.5" in landing
    assert "SNAP Release 26.5 Effective 6.15.2026.pdf" in release_log
    qualifying = work_registration.index("<p>Qualifying Components</p>")
    nonqualifying = work_registration.index("<p>Non-Qualifying Components</p>")
    assert "Job Retention" not in work_registration[qualifying:nonqualifying]
    assert "Job Retention" in work_registration[nonqualifying:]
    assert "eligibleClosed" in reporting
    assert "Able-bodiedClosed" in reporting
    assert hashlib.sha256(release_pdf.read_bytes()).hexdigest() == (
        EXPECTED_RELEASE_PDF_SHA256
    )


def test_north_dakota_source_set_and_generated_scope_are_complete() -> None:
    source_files = sorted(path for path in SOURCE_ROOT.iterdir() if path.is_file())
    digest_lines = [
        f"{path.name}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        for path in source_files
    ]
    rows = _provisions()
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    page_rows = [row for row in rows if row["kind"] == "page"]

    assert len(source_files) == EXPECTED_SOURCE_COUNT
    assert hashlib.sha256("\n".join(digest_lines).encode()).hexdigest() == (
        EXPECTED_SOURCE_SET_SHA256
    )
    assert len(rows) == len(inventory) == EXPECTED_ROW_COUNT
    assert len({row["citation_path"] for row in rows}) == EXPECTED_ROW_COUNT
    assert sum(row["kind"] == "document" for row in rows) == EXPECTED_SOURCE_COUNT
    assert sum(row["kind"] == "block" for row in rows) == 96
    assert [row["metadata"]["page_number"] for row in page_rows] == [1, 2, 3, 4]
    assert all(row["body"] for row in rows if row["kind"] != "document")
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []
    assert coverage["matched_count"] == coverage["source_count"] == EXPECTED_ROW_COUNT
    assert coverage["provision_count"] == EXPECTED_ROW_COUNT
