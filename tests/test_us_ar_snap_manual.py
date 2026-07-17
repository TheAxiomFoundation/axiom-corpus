import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-ar-snap-manual.yaml"
VERSION = "2026-07-16-ar-snap-manual"
SOURCE_ROOT = CORPUS_ROOT / "sources" / "us-ar" / "manual" / VERSION
INVENTORY_PATH = CORPUS_ROOT / "inventory" / "us-ar" / "manual" / f"{VERSION}.json"
COVERAGE_PATH = CORPUS_ROOT / "coverage" / "us-ar" / "manual" / f"{VERSION}.json"
EXPECTED_SOURCES = {
    "ar-dhs-snap-policy-manual": (
        "us-ar/manual/dhs/snap-policy-manual",
        "https://humanservices.arkansas.gov/wp-content/uploads/"
        "SNAP-Policy-Manual-04.02.2026.pdf",
        "https://humanservices.arkansas.gov/wp-content/uploads/"
        "SNAP-Policy-Manual-04.02.2026.pdf?download=1",
        "pdf",
        "2026-07-16",
        "2026-04-02",
        None,
        589,
    ),
    "ar-dhs-snap-manual-appendices": (
        "us-ar/manual/dhs/snap-manual-appendices",
        "https://humanservices.arkansas.gov/wp-content/uploads/"
        "SNAP-Appendices-05.15.2026.pdf",
        "https://humanservices.arkansas.gov/wp-content/uploads/"
        "SNAP-Appendices-05.15.2026.pdf?download=1",
        "pdf",
        "2026-07-16",
        "2026-05-15",
        None,
        85,
    ),
    "ar-dhs-snap-july-2026-final-filing": (
        "us-ar/manual/dhs/snap-july-2026-final-filing",
        "https://humanservices.arkansas.gov/wp-content/uploads/"
        "SNAP-TEA-and-Work-Pays-Program-Updates-A.pdf",
        None,
        "pdf",
        "2026-07-16",
        "2026-07-01",
        None,
        117,
    ),
    "ar-dhs-snap-quick-reference-fy2026": (
        "us-ar/manual/dhs/snap-quick-reference-fy2026",
        "https://humanservices.arkansas.gov/wp-content/uploads/"
        "Quick-Reference-SNAP-Eligibility-Chart-FY2026.pdf",
        None,
        "pdf",
        "2026-07-16",
        "2025-10-01",
        None,
        2,
    ),
    "ar-dhs-snap-basis-of-issuance-ffy2026": (
        "us-ar/manual/dhs/snap-basis-of-issuance-ffy2026",
        "https://humanservices.arkansas.gov/wp-content/uploads/"
        "FFY26-NBI-Chart-Oct-2025-September-2026-05.21.2026.pdf",
        "https://humanservices.arkansas.gov/wp-content/uploads/"
        "FFY26-NBI-Chart-Oct-2025-September-2026-05.21.2026.pdf?download=1",
        "pdf",
        "2026-07-16",
        "2026-05-15",
        None,
        3,
    ),
    "ar-dhs-snap-nutrition-waiver": (
        "us-ar/manual/dhs/snap-nutrition-waiver",
        "https://humanservices.arkansas.gov/divisions-shared-services/county-operations/"
        "supplemental-nutrition-assistance-snap/snap-nutrition-waiver/",
        None,
        "html",
        "2026-07-16",
        "2026-07-01",
        ".elementor-widget-theme-post-content",
        3,
    ),
    "ar-dhs-snap-nutrition-waiver-faq": (
        "us-ar/manual/dhs/snap-nutrition-waiver-faq",
        "https://humanservices.arkansas.gov/divisions-shared-services/county-operations/"
        "supplemental-nutrition-assistance-snap/snap-nutrition-waiver/"
        "snap-nutrition-waiver-faq/",
        None,
        "html",
        "2026-07-16",
        "2026-07-01",
        ".elementor-widget-theme-post-content",
        1,
    ),
    "ar-dhs-snap-time-limit-rules": (
        "us-ar/manual/dhs/snap-time-limit-rules",
        "https://humanservices.arkansas.gov/divisions-shared-services/county-operations/"
        "supplemental-nutrition-assistance-snap/snap-time-limit-rules/",
        None,
        "html",
        "2026-07-16",
        "2026-07-01",
        ".elementor-widget-theme-post-content",
        2,
    ),
}


def test_arkansas_snap_scope_retains_complete_current_policy_set() -> None:
    documents = yaml.safe_load(MANIFEST_PATH.read_text())["documents"]
    inventory = json.loads(INVENTORY_PATH.read_text())["items"]
    coverage = json.loads(COVERAGE_PATH.read_text())
    document_items = [item for item in inventory if item["metadata"]["kind"] == "document"]
    documents_by_id = {document["source_id"]: document for document in documents}
    document_items_by_url = {item["source_url"]: item for item in document_items}

    assert len(documents) == len(documents_by_id) == len(EXPECTED_SOURCES)
    assert len(document_items) == len(document_items_by_url) == len(EXPECTED_SOURCES)
    assert set(documents_by_id) == set(EXPECTED_SOURCES)
    for source_id, expected in EXPECTED_SOURCES.items():
        (
            citation_path,
            source_url,
            download_url,
            source_format,
            source_as_of,
            expression_date,
            selector,
            count,
        ) = expected
        document = documents_by_id[source_id]
        assert (
            document["citation_path"],
            document["source_url"],
            document.get("download_url"),
            document["source_format"],
            document["source_as_of"],
            document["expression_date"],
            (document.get("extraction") or {}).get("html_content_selector"),
        ) == (
            citation_path,
            source_url,
            download_url,
            source_format,
            source_as_of,
            expression_date,
            selector,
        )

        item = document_items_by_url[source_url]
        assert item["citation_path"] == citation_path
        assert item["source_format"] == source_format
        assert item["metadata"]["block_count"] == count
        assert (CORPUS_ROOT / item["source_path"]).is_relative_to(SOURCE_ROOT)

    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == []
    assert coverage["extra_provisions"] == []
    assert coverage["source_count"] == coverage["provision_count"] == len(inventory)
