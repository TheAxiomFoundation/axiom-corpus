import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST_PATH = REPO_ROOT / "manifests" / "us-co-snap-primary-policy.yaml"
QUEUE_PATH = REPO_ROOT / "manifests" / "state-snap-manual-agent-queue.yaml"
VERSION = "2026-07-21-co-snap-policy"
SOURCE_DIR = CORPUS_ROOT / "sources/us-co/policy" / VERSION / "official-documents"
INVENTORY_PATH = CORPUS_ROOT / "inventory/us-co/policy" / f"{VERSION}.json"
PROVISIONS_PATH = CORPUS_ROOT / "provisions/us-co/policy" / f"{VERSION}.jsonl"
COVERAGE_PATH = CORPUS_ROOT / "coverage/us-co/policy" / f"{VERSION}.json"

EXPECTED_SOURCES = {
    "co-cdhs-snap-page": (
        "co-cdhs-snap-page.html",
        157_228,
        "e1580d1dac142adda55dac7a733c4b4841c79e3c7f4401ac40a029dac7cc80c3",
        22,
    ),
    "co-cdhs-abawd-page": (
        "co-cdhs-abawd-page.html",
        108_068,
        "a464f6ed76fd3671466dd5eceb7016cfb2d465b3ec309feee87b56103256f546",
        4,
    ),
    "co-cdhs-healthy-choice-waiver-page": (
        "co-cdhs-healthy-choice-waiver-page.html",
        103_358,
        "bde90d32e5582c08caabb8f8f1057fc6df4abf38d3937a922e035d4c97f96f27",
        4,
    ),
    "co-cdhs-employment-first-page": (
        "co-cdhs-employment-first-page.html",
        122_688,
        "26e83d7ac14684d994ae4d57e96c17f748b8e3bfe602f44c28235fec6f78241a",
        15,
    ),
    "co-cdhs-energy-ebt-page": (
        "co-cdhs-energy-ebt-page.html",
        121_539,
        "81aff4dc43fc29524528406f105233a6d341fe438c955ab13da0bbe2fb9bebfe",
        10,
    ),
    "co-cdhs-snap-outreach-page": (
        "co-cdhs-snap-outreach-page.html",
        115_608,
        "45acbecaff7d131cae92e9a55382b3de2efa469fefbcba9b30e03c30ca6efc49",
        11,
    ),
    "co-cdhs-snap-et-state-plan-ffy2026": (
        "co-cdhs-snap-et-state-plan-ffy2026.pdf",
        2_749_753,
        "1ff9517c2ec2105936fdfdda5d202ac95debc11854b34e9752d32c8ea947f40a",
        426,
    ),
    "co-cdhs-workfare-state-plan-ffy2026": (
        "co-cdhs-workfare-state-plan-ffy2026.pdf",
        157_934,
        "4cc864a58756d103ec19e4da3a6e33c7af7ad623c956f4205b58cbb70f91910d",
        8,
    ),
    "co-cdhs-employment-first-operator-handbook-ffy2026": (
        "co-cdhs-employment-first-operator-handbook-ffy2026.pdf",
        898_739,
        "f12794cd143b49b1f3d63b829edce7eee3ce134c222c885611da580dd3376caa",
        42,
    ),
    "co-cdhs-snap-outreach-plan-fy2026": (
        "co-cdhs-snap-outreach-plan-fy2026.pdf",
        770_640,
        "975872a3ea9706f9f07073ec3ce4b85bfd004c9912851de738fd6061fa90affa",
        41,
    ),
    "co-fns-food-restriction-waiver-approval-2025": (
        "co-fns-food-restriction-waiver-approval-2025.pdf",
        730_184,
        "bbf77f7011532d2cd0604de35d307c99003f025e75325e43f31873b0c3360727",
        9,
    ),
    "co-fns-food-restriction-waiver-modification-2026-01-23": (
        "co-fns-food-restriction-waiver-modification-2026-01-23.pdf",
        135_484,
        "ac213418b3bb4d8aaacc18e9d448072dd0532d320ef2f021adde8b6566e1af4c",
        3,
    ),
    "co-fns-food-restriction-waiver-modification-2026-05-11": (
        "co-fns-food-restriction-waiver-modification-2026-05-11.pdf",
        146_352,
        "c311d5aade08ef7c15a404d06b6fa37c0a9ae4f825c54a5185441067fc86da56",
        3,
    ),
}
EXPECTED_SOURCE_BYTES = 6_317_575
EXPECTED_SOURCE_AGGREGATE = "8bdcc4bcf74e2f1eefb496e98eff77588232351a939e08a24d910aba284848e0"
EXPIRED_SOURCE_IDS = {
    "co-fns-abawd-waiver-fy2025",
    "co-cdhs-energy-ebt-implementation-2025",
    "co-cdhs-work-requirements-oral-explanation-waiver-2025",
}


def _documents() -> list[dict]:
    return yaml.safe_load(MANIFEST_PATH.read_text())["documents"]


def _inventory() -> list[dict]:
    return json.loads(INVENTORY_PATH.read_text())["items"]


def _provisions() -> list[dict]:
    return [json.loads(line) for line in PROVISIONS_PATH.read_text().splitlines()]


def test_colorado_policy_manifest_uses_exact_current_source_boundary() -> None:
    documents = _documents()
    source_ids = {document["source_id"] for document in documents}
    html_documents = [document for document in documents if document["source_format"] == "html"]

    assert len(documents) == len(source_ids) == 13
    assert source_ids == EXPECTED_SOURCES.keys()
    assert source_ids.isdisjoint(EXPIRED_SOURCE_IDS)
    assert len(html_documents) == 6
    assert all(
        document["request"]
        == {
            "browser_impersonation_direct": True,
            "browser_impersonation": "chrome120",
        }
        for document in html_documents
    )
    assert all(document["metadata"]["primary_source"] is True for document in documents)


def test_colorado_policy_retained_sources_match_live_hash_ratcheting() -> None:
    actual_files = {path.name: path for path in SOURCE_DIR.iterdir() if path.is_file()}
    expected_files = {values[0] for values in EXPECTED_SOURCES.values()}

    assert actual_files.keys() == expected_files
    assert sum(path.stat().st_size for path in actual_files.values()) == EXPECTED_SOURCE_BYTES
    for filename, expected_bytes, expected_hash, _row_count in EXPECTED_SOURCES.values():
        source_path = actual_files[filename]
        assert source_path.stat().st_size == expected_bytes
        assert sha256_file(source_path) == expected_hash

    document_items = [item for item in _inventory() if item["metadata"]["kind"] == "document"]
    ordered_hashes = "".join(item["sha256"] for item in document_items)
    assert hashlib.sha256(ordered_hashes.encode()).hexdigest() == EXPECTED_SOURCE_AGGREGATE


def test_colorado_policy_generated_scope_is_complete() -> None:
    inventory = _inventory()
    rows = _provisions()
    coverage = json.loads(COVERAGE_PATH.read_text())

    assert Counter(row["source_id"] for row in rows) == {
        source_id: values[3] for source_id, values in EXPECTED_SOURCES.items()
    }
    assert len(inventory) == len(rows) == 598
    assert sum(row["kind"] == "document" for row in rows) == 13
    assert sum(row["kind"] in {"block", "page"} for row in rows) == 585
    assert len({row["citation_path"] for row in rows}) == 598
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == coverage["extra_provisions"] == []
    assert coverage["duplicate_source_citations"] == []
    assert coverage["duplicate_provision_citations"] == []
    assert coverage["matched_count"] == coverage["source_count"] == 598
    assert coverage["provision_count"] == 598


def test_colorado_policy_marks_discontinued_decision_chain_non_operative() -> None:
    documents = {document["source_id"]: document for document in _documents()}

    assert documents["co-cdhs-healthy-choice-waiver-page"]["metadata"] == {
        "primary_source": True,
        "source_authority": "Colorado Department of Human Services",
        "document_subtype": "agency_page",
        "program": "SNAP",
        "topic": "food_restriction_waiver",
        "source_status": "current",
        "policy_status": "discontinued",
    }
    fns_documents = [
        document
        for source_id, document in documents.items()
        if source_id.startswith("co-fns-food-restriction-waiver-")
    ]
    assert [document["metadata"]["decision_order"] for document in fns_documents] == [1, 2, 3]
    assert all(
        document["metadata"]["source_status"] == "historical_decision_chain"
        and document["metadata"]["policy_status"] == "non_operative"
        for document in fns_documents
    )
    healthy_choice_html = (
        SOURCE_DIR / EXPECTED_SOURCES["co-cdhs-healthy-choice-waiver-page"][0]
    ).read_text()
    assert (
        "discontinuing its efforts to implement the SNAP Healthy Choice Waiver"
        in healthy_choice_html
    )


def test_colorado_policy_preserves_explicit_current_source_gaps() -> None:
    rows = _provisions()
    bodies_by_source = {
        source_id: "\n".join(row["body"] or "" for row in rows if row["source_id"] == source_id)
        for source_id in EXPECTED_SOURCES
    }

    assert "FORM STATUS: Unsubmitted" in bodies_by_source["co-cdhs-snap-et-state-plan-ffy2026"]
    snap_body = bodies_by_source["co-cdhs-snap-page"]
    assert "values were last updated on Oct. 1, 2024" in snap_body
    assert "adult between 18 and 56" in snap_body
    assert "Between the ages of 18 and 64" in snap_body
    fy2026_documents = [
        document for document in _documents() if document["metadata"].get("fiscal_year") == "2026"
    ]
    assert len(fy2026_documents) == 4
    assert all(
        document["metadata"]["effective_end"] == "2026-09-30" for document in fy2026_documents
    )


def test_colorado_queue_publishes_current_supporting_scope() -> None:
    states = yaml.safe_load(QUEUE_PATH.read_text())["states"]
    state = next(item for item in states if item["jurisdiction"] == "us-co")

    assert state["supporting_queue_status"] == "published_current"
    assert state["supporting_scope"] == {
        "jurisdiction": "us-co",
        "document_class": "policy",
        "version": VERSION,
    }
    assert "FORM STATUS Unsubmitted" in state["notes"]
    assert "stale October 2024 amounts" in state["notes"]
    assert "conflicting ABAWD ages" in state["notes"]
    assert "Federal law" in state["notes"]
    assert "broader active CDHS memo catalog" in state["notes"]
