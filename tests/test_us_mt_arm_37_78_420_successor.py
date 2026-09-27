"""The ARM 37.78.420 successor of us-mt/regulation/2026-07-13-recovery."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from functools import cache
from pathlib import Path

import pytest

from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.montana_admin_rules import _html_body_text, _references_to
from axiom_corpus.corpus.montana_rule_page import (
    MontanaRuleDocument,
    montana_accessible_html_lines,
    parse_montana_rule_document,
    parse_montana_rule_page_chrome,
    text_layer_lines,
)
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.repro.us_mt_arm_37_78_420_successor import (
    CITATION_PATH,
    POLICY_LEAF,
    POLICY_PROVENANCE_LEAF,
    RETAINED_LEAF,
    RETAINED_PROVENANCE_LEAF,
    SOURCE_VERSION,
    VERSION,
    VERSION_HTML_LEAF,
    VERSION_HTML_PROVENANCE_LEAF,
    VERSION_PDF_LEAF,
    VERSION_PDF_PROVENANCE_LEAF,
    VERSION_RENDITIONS,
    VERSION_UUID,
    build_scope,
    non_space_characters,
    pdf_text,
    policy_version,
    version_field,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus"
SCOPE = ("us-mt", "regulation")
OLD_SOURCES = CORPUS / "sources/us-mt/regulation" / SOURCE_VERSION
NEW_SOURCES = CORPUS / "sources/us-mt/regulation" / VERSION
KEY_LINES = (
    "us-rulespec-2026-08-08-obbb-alien-snap",
    "us-rulespec-2026-09-24-snap-fy2027-cola",
    "us-rulespec-2026-08-23-canada-338-suspension-union",
    "us-rulespec-2026-09-14-wave4-union",
    "us-rulespec-2026-09-14-wave4-r2-union",
)
OUTSIDE_THE_RULE_TEXT = (
    "Montana SOS",
    "Skip to main content",
    "View in PDF",
    "Collapse All",
    "Rule Version",
    "Contact Information",
    "Relevant MAR Notices",
    "Referenced by",
    "Active Version",
    "hhsadminrules@mt.gov",
    "Authorizing statute(s)",
    "History:",
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(kind: str, version: str = VERSION) -> Path:
    suffix = "jsonl" if kind == "provisions" else "json"
    return CORPUS / kind / "us-mt/regulation" / f"{version}.{suffix}"


@cache
def _retained() -> bytes:
    return (NEW_SOURCES / RETAINED_LEAF).read_bytes()


@cache
def _document() -> MontanaRuleDocument:
    return parse_montana_rule_document(_retained())


@cache
def _record() -> ProvisionRecord:
    (record,) = load_provisions(_artifact("provisions"))
    return record


def test_build_reproduces_the_committed_scope_byte_for_byte(tmp_path: Path) -> None:
    first = build_scope(base=tmp_path / "first", source_base=CORPUS)
    second = build_scope(base=tmp_path / "second", source_base=CORPUS)
    assert [_digest(path) for path in first] == [_digest(path) for path in second]
    for built, kind in zip(first, ("inventory", "provisions", "coverage"), strict=True):
        assert built.read_bytes() == _artifact(kind).read_bytes(), kind
    built_sources = tmp_path / "first/sources/us-mt/regulation" / VERSION
    committed = sorted(p.relative_to(NEW_SOURCES) for p in NEW_SOURCES.rglob("*") if p.is_file())
    assert (
        sorted(p.relative_to(built_sources) for p in built_sources.rglob("*") if p.is_file())
        == committed
    )
    for leaf in committed:
        assert (built_sources / leaf).read_bytes() == (NEW_SOURCES / leaf).read_bytes(), leaf


def test_retained_page_and_its_provenance_are_copied_unchanged() -> None:
    for leaf in (RETAINED_LEAF, RETAINED_PROVENANCE_LEAF):
        assert (NEW_SOURCES / leaf).read_bytes() == (OLD_SOURCES / leaf).read_bytes()
    (old_item,) = load_source_inventory(_artifact("inventory", SOURCE_VERSION))
    (new_item,) = load_source_inventory(_artifact("inventory"))
    assert new_item.sha256 == old_item.sha256 == _digest(NEW_SOURCES / RETAINED_LEAF)
    assert new_item.citation_path == old_item.citation_path == CITATION_PATH
    assert new_item.source_url == old_item.source_url
    assert new_item.metadata is not None
    assert new_item.metadata["successor_of_source_path"] == old_item.source_path


def test_successor_row_is_the_rule_without_page_chrome() -> None:
    record = _record()
    (old,) = load_provisions(_artifact("provisions", SOURCE_VERSION))
    body = record.body or ""

    assert record.citation_path == old.citation_path == CITATION_PATH
    assert record.id == deterministic_provision_id(CITATION_PATH, VERSION)
    assert record.parent_citation_path is None and record.parent_id is None
    assert (record.kind, record.level, record.ordinal) == ("rule", 4, 1)
    assert record.citation_label == record.legal_identifier == "ARM 37.78.420"
    assert record.heading == (
        "TANF: ASSISTANCE STANDARDS; TABLES; METHODS OF COMPUTING AMOUNT OF MONTHLY BENEFIT PAYMENT"
    )
    assert (record.source_as_of, record.expression_date) == (old.source_as_of, old.expression_date)
    assert record.source_path == f"sources/us-mt/regulation/{VERSION}/{RETAINED_LEAF}"

    assert body.startswith("(1) Income standards as set forth in this rule")
    assert body.endswith("income anticipated to be received in the benefit month is used.")
    for text in OUTSIDE_THE_RULE_TEXT:
        assert text not in body, text
        assert text in (old.body or ""), text
    assert "37.78.420" not in body
    assert len(body) < len(old.body or "") - 1800


def test_body_carries_what_the_rulespec_module_cites() -> None:
    """rulespec-us us-mt/regulations/.../rule-37-78-420.yaml at 54d90a725."""

    body = _record().body or ""
    lines = body.split("\n")
    excerpt = (
        "Payment standards in the Post-Employment Program are a set amount as defined in "
        "(4)(e). This amount is not based on household size."
    )
    assert excerpt in body
    for header in (
        "GROSS MONTHLY INCOME STANDARDS (GMI)",
        "NET MONTHLY INCOME STANDARDS (NMI)",
        "BENEFITS STANDARDS",
        "PAYMENT STANDARDS (33% of the FY 2007 Federal Poverty Level)",
        "POST-EMPLOYMENT PAYMENT STANDARDS",
    ):
        assert header in lines, header
    assert "Number of Persons in Household | Gross Monthly Income (GMI)" in lines

    tables: dict[str, dict[str, str]] = {}
    current = ""
    for line in lines:
        if " | " not in line and not line.startswith("("):
            current = line
            tables[current] = {}
        elif current and " | " in line:
            label, value = line.split(" | ")
            tables[current][label] = value
    assert tables["POST-EMPLOYMENT PAYMENT STANDARDS"] == {
        "1st Month": "$ 375",
        "2nd Month": "275",
        "3rd Month": "175",
    }
    gmi = tables["GROSS MONTHLY INCOME STANDARDS (GMI)"]
    assert (gmi["1"], gmi["3"], gmi["20"]) == ("$ 557", "979", "4,383")
    payment = tables["PAYMENT STANDARDS (33% of the FY 2007 Federal Poverty Level)"]
    assert (payment["1"], payment["3"], payment["20"]) == ("$ 298", "504", "2,252")
    for name in (
        "NET MONTHLY INCOME STANDARDS (NMI)",
        "BENEFITS STANDARDS",
        "PAYMENT STANDARDS (33% of the FY 2007 Federal Poverty Level)",
    ):
        assert list(tables[name]) == [str(size) for size in range(1, 21)], name


def test_text_layer_matches_the_versions_accessible_html_line_for_line() -> None:
    """The differential check: two renditions of rule version 33678 agree exactly."""

    official = montana_accessible_html_lines((NEW_SOURCES / VERSION_HTML_LEAF).read_bytes())
    assert _document().document_lines() == official
    assert len(official) == 109


def test_text_layer_carries_the_characters_of_the_versions_pdf() -> None:
    layer = "".join(
        segment.text for line in text_layer_lines(_retained()) for segment in line.segments
    )
    pdf = pdf_text((NEW_SOURCES / VERSION_PDF_LEAF).read_bytes())
    assert non_space_characters(pdf) == non_space_characters(layer)
    assert sum(non_space_characters(layer).values()) == 4330


def test_every_text_layer_character_is_kept() -> None:
    layer = "".join(
        segment.text for line in text_layer_lines(_retained()) for segment in line.segments
    )
    rendered = "".join(_document().document_lines()).replace("|", "")
    assert Counter(re.sub(r"\s+", "", rendered)) == Counter(re.sub(r"\s+", "", layer))


def test_metadata_agrees_with_the_page_and_the_policy_record() -> None:
    record = _record()
    metadata = record.metadata or {}
    chrome = parse_montana_rule_page_chrome(_retained())
    version = policy_version(json.loads((NEW_SOURCES / POLICY_LEAF).read_bytes()), VERSION_UUID)
    html = (NEW_SOURCES / VERSION_HTML_LEAF).read_bytes()

    history = version_field(version, "history")
    assert metadata["history"] == _document().history == chrome.history == history
    assert metadata["source_history"] == [history]
    assert metadata["version_number"] == version_field(version, "version_number") == "33678"
    assert metadata["effective_start_date"] == version_field(version, "effective_start_date")
    assert metadata["policy_version_uuid"] == VERSION_UUID
    assert "effective_end_date" not in metadata
    assert metadata["authorizing_statutes"] == "53-4-212, MCA"
    assert metadata["implementing_statutes"] == "53-4-211, 53-4-241, 53-4-601, MCA"
    assert metadata["referenced_by"] == [
        {
            "label": "2026-529.1 TANF Benefit and Payment Standards",
            "url": (
                "https://rules.mt.gov/browse/collections/5e1173a6-33c7-4df8-b426-5e0077cfc430/"
                "policies/a53a35af-d5ed-4c46-956e-a16cf534ecc1"
            ),
        }
    ]
    adapter_refs = [
        ref
        for ref in _references_to(html, _html_body_text(html) or "")
        if ref != "us-mt/regulation/rule-37-78-420"
    ]
    assert metadata["references_to"] == adapter_refs
    assert record.identifiers == {
        "montana:arm_rule": "37.78.420",
        "montana:policy_uuid": chrome.policy_uuid,
        "montana:policy_version_uuid": VERSION_UUID,
    }


def test_verification_sources_are_what_the_policy_record_declares() -> None:
    policy_bytes = (NEW_SOURCES / POLICY_LEAF).read_bytes()
    policy_provenance = json.loads((NEW_SOURCES / POLICY_PROVENANCE_LEAF).read_bytes())
    version = policy_version(json.loads(policy_bytes), VERSION_UUID)
    assert policy_provenance["sha256"] == hashlib.sha256(policy_bytes).hexdigest()
    assert policy_provenance["http"] == 200
    assert {rendition.leaf for rendition in VERSION_RENDITIONS} == {
        VERSION_HTML_LEAF,
        VERSION_PDF_LEAF,
    }
    assert {rendition.provenance_leaf for rendition in VERSION_RENDITIONS} == {
        VERSION_HTML_PROVENANCE_LEAF,
        VERSION_PDF_PROVENANCE_LEAF,
    }
    for rendition in VERSION_RENDITIONS:
        content = (NEW_SOURCES / rendition.leaf).read_bytes()
        provenance = json.loads((NEW_SOURCES / rendition.provenance_leaf).read_bytes())
        declared = version[rendition.key]
        assert (
            provenance["sha256"] == provenance["declared_sha256"] == declared["contentHashSha256"]
        )
        assert provenance["sha256"] == hashlib.sha256(content).hexdigest()
        assert provenance["url"].endswith(declared["contentUrl"])
        assert provenance["final_url"].endswith(provenance["sha256"])
        assert provenance["http"] == 200
    assert version_field(version, "effective_end_date") == "2026-09-25"
    metadata = _record().metadata or {}
    assert metadata["verification_source_paths"] == [
        f"sources/us-mt/regulation/{VERSION}/{leaf}"
        for leaf in (VERSION_HTML_LEAF, VERSION_PDF_LEAF, POLICY_LEAF)
    ]


@pytest.mark.parametrize("line", KEY_LINES)
def test_the_swap_validates_on_every_key_line(line: str) -> None:
    selector = json.loads((ROOT / "manifests/releases" / f"{line}.json").read_text("utf-8"))
    selected = [
        scope["version"]
        for scope in selector["scopes"]
        if (scope["jurisdiction"], scope["document_class"]) == SCOPE
    ]
    assert SOURCE_VERSION in selected and VERSION not in selected
    swapped = [VERSION if version == SOURCE_VERSION else version for version in selected]
    release = ReleaseManifest(
        name=f"{line}-mt-arm-37-78-420-swap",
        quality_profile=selector["quality_profile"],
        scopes=tuple(ReleaseScope(*SCOPE, version) for version in swapped),
    )
    report = validate_release(CORPUS, release, strict_warnings=True).to_mapping()
    assert (report["ok"], report["issue_count"]) == (True, 0), report["issues"][:3]


def test_the_swap_keeps_the_release_citation_set() -> None:
    old = {
        record.citation_path for record in load_provisions(_artifact("provisions", SOURCE_VERSION))
    }
    new = {record.citation_path for record in load_provisions(_artifact("provisions"))}
    assert new == old == {CITATION_PATH}


def test_selecting_the_original_with_its_successor_is_rejected() -> None:
    release = ReleaseManifest(
        name="mt-arm-37-78-420-both",
        quality_profile="complete-expression-dates-v1",
        scopes=(ReleaseScope(*SCOPE, SOURCE_VERSION), ReleaseScope(*SCOPE, VERSION)),
    )
    report = validate_release(CORPUS, release, strict_warnings=True).to_mapping()
    assert not report["ok"]
    assert {issue["code"] for issue in report["issues"]} == {"duplicate_release_citation"}
