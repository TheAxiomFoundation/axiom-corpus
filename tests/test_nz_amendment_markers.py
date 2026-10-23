"""Reviewed amendment markers must remain grounded in retained official sources."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pytest
import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.nz_amendment_markers import enrich_amendment_rows, reproduce_scope
from axiom_corpus.corpus.nz_legislation import extract_nz_legislation
from axiom_corpus.corpus.release_policy import ReleaseGatePolicy
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    ReleaseManifest,
    ReleaseScope,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/corpus"
OLD_VERSION = "2026-10-20-rulespec-nz-pco"
NEW_VERSION = "2026-10-23-rulespec-nz-pco"
DOCUMENT = "nz/statute/act/public/2026/0054"
PRINCIPAL = "nz/statute/act/public/2018/0032"
SOURCE_NAME = "act/public/2026/54/act_public_2026_54_en_2026-09-03.xml"
SOURCE = BASE / "sources/nz/statute" / OLD_VERSION / SOURCE_NAME
OVERLAY = ROOT / "manifests/nz-amendment-markers/act-2026-0054.yaml"
TABLE_TARGET = f"{PRINCIPAL}/schedule/4/part/7/clause/lms118453"
TARGETS = {
    "section/4": "section/20",
    "section/6": "section/63",
    "section/7": "section/113",
    "section/10": "schedule/1",
    "section/11": "schedule/2",
    "section/12": "schedule/3",
    "section/13": "schedule/1",
    "section/14": "schedule/2",
    "section/15": "schedule/4/part/7/clause/lms118453",
}


def _read_rows(path: Path) -> list[ProvisionRecord]:
    if not path.is_file():
        pytest.skip(f"retained NZ scope is not fetched: {path}")
    return [ProvisionRecord.from_mapping(json.loads(line)) for line in path.read_text().splitlines()]


@pytest.fixture(scope="module")
def official_xml() -> bytes:
    if not SOURCE.is_file():
        pytest.skip(f"retained NZ source is not fetched: {SOURCE}")
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "aa6b16470e1302a80503a5a8fb44ea40159081cd234c731cad672652b5545f52"
    )
    return raw


@pytest.fixture(scope="module")
def original_rows() -> list[ProvisionRecord]:
    return _read_rows(BASE / "provisions/nz/statute" / f"{OLD_VERSION}.jsonl")


@pytest.fixture(scope="module")
def principal_rows() -> list[ProvisionRecord]:
    rows = _read_rows(BASE / "provisions/nz/statute/2026-06-16-rulespec-nz-pco.jsonl")
    return [row for row in rows if row.citation_path == PRINCIPAL or row.citation_path.startswith(f"{PRINCIPAL}/")]


@pytest.fixture
def overlay() -> dict[str, Any]:
    return yaml.safe_load(OVERLAY.read_text())


def _by_path(rows: list[ProvisionRecord]) -> dict[str, ProvisionRecord]:
    return {row.citation_path: row for row in rows}


def _replace_row(rows: list[ProvisionRecord], suffix: str, **changes: Any) -> list[ProvisionRecord]:
    path = f"{DOCUMENT}/{suffix}"
    assert any(row.citation_path == path for row in rows)
    return [replace(row, **changes) if row.citation_path == path else row for row in rows]


def test_enrichment_changes_only_metadata_and_does_not_mutate_inputs(
    official_xml, original_rows, principal_rows, overlay
):
    before = copy.deepcopy([row.to_mapping() for row in original_rows])
    result = enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay)
    assert len(result) == len(original_rows) == 26
    assert [row.to_mapping() for row in original_rows] == before
    changed = []
    for old, new in zip(original_rows, result, strict=True):
        old_mapping, new_mapping = old.to_mapping(), new.to_mapping()
        assert old_mapping.pop("metadata") != {}  # Preserve all inherited provenance.
        new_mapping.pop("metadata")
        assert old_mapping == new_mapping
        assert old.body == new.body
        assert set(old.metadata or {}).issubset(new.metadata or {})
        assert all((new.metadata or {})[key] == value for key, value in (old.metadata or {}).items())
        if new.citation_path == DOCUMENT:
            added_keys = {"document_type", "amends"}
        elif new.citation_path in {f"{DOCUMENT}/section/{number}" for number in (1, 2, 3)}:
            added_keys = set()
        else:
            added_keys = {"part", "commencement_date", "commencement_citation_path"}
            if new.citation_path not in {f"{DOCUMENT}/section/{number}" for number in (5, 8, 9)}:
                added_keys.add("amendment_target")
        assert set(new.metadata or {}) - set(old.metadata or {}) == added_keys
        if old.metadata != new.metadata:
            changed.append(old.citation_path)
    assert len(changed) == 23
    assert DOCUMENT in changed
    assert all(f"{DOCUMENT}/section/{number}" not in changed for number in (1, 2, 3))


def test_document_marker_resolves_xml_principal_id_to_existing_document(
    official_xml, original_rows, principal_rows, overlay
):
    rows = _by_path(enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay))
    metadata = rows[DOCUMENT].metadata or {}
    assert metadata["document_type"] == "amendment_act"
    assert metadata["amends"] == [PRINCIPAL]
    source = ET.fromstring(official_xml)
    assert "Amendment Act 2026" in source.findtext("./cover/title", "")
    assert source.findall(".//amend")
    assert source.find("./body/prov[label='3']//leg-title").attrib["href"] == "DLM6783102"
    assert "Social Security Act 2018" in (rows[f"{DOCUMENT}/section/3"].body or "")


def test_each_amending_row_binds_date_to_its_xml_part(
    official_xml, original_rows, principal_rows, overlay
):
    rows = _by_path(enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay))
    amendments = [row for row in rows.values() if (row.metadata or {}).get("commencement_date")]
    assert len(amendments) == 22
    for row in amendments:
        suffix = row.citation_path.removeprefix(f"{DOCUMENT}/")
        in_part_2 = suffix.startswith("schedule/2") or suffix in {
            "section/13", "section/14", "section/15"
        }
        metadata = row.metadata or {}
        assert metadata["part"] == ("2" if in_part_2 else "1")
        assert metadata["commencement_date"] == ("2027-04-01" if in_part_2 else "2026-11-02")
        assert metadata["commencement_citation_path"] == f"{DOCUMENT}/section/2"
        assert "amendment_targets" not in metadata
        if suffix in {"section/5", "section/8", "section/9"}:
            assert "amendment_target" not in metadata
        else:
            expected = TARGETS.get(suffix, "schedule/1")
            assert metadata["amendment_target"] == f"{PRINCIPAL}/{expected}"


def test_xml_parts_override_misleading_date_attributes(
    official_xml, original_rows, principal_rows, overlay
):
    source = ET.fromstring(official_xml)
    part_2 = source.find("./body/part[label='2']")
    assert part_2 is not None
    assert part_2.attrib["date.first.valid"] == "2026-11-02"
    part_2.set("date.first.valid", "2099-12-31")
    rows = _by_path(enrich_amendment_rows(ET.tostring(source), original_rows, principal_rows, overlay))
    assert (rows[f"{DOCUMENT}/section/15"].metadata or {})["commencement_date"] == "2027-04-01"
    assert (rows[f"{DOCUMENT}/schedule/2/part/18"].metadata or {})["part"] == "2"


def test_part_membership_is_taken_from_xml_structure(
    official_xml, original_rows, principal_rows, overlay
):
    source = ET.fromstring(official_xml)
    part_1 = source.find("./body/part[label='1']")
    part_2 = source.find("./body/part[label='2']")
    assert part_1 is not None and part_2 is not None
    section_13 = part_2.find("prov[label='13']")
    assert section_13 is not None
    part_2.remove(section_13)
    part_1.append(section_13)
    rows = _by_path(enrich_amendment_rows(ET.tostring(source), original_rows, principal_rows, overlay))
    for suffix in ("section/13", "schedule/2", "schedule/2/part/18/clause/132"):
        metadata = rows[f"{DOCUMENT}/{suffix}"].metadata or {}
        assert metadata["part"] == "1"
        assert metadata["commencement_date"] == "2026-11-02"


def test_s15_target_is_the_single_table_containing_replaced_clauses(
    official_xml, original_rows, principal_rows, overlay
):
    rows = _by_path(enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay))
    assert (rows[f"{DOCUMENT}/section/15"].metadata or {})["amendment_target"] == TABLE_TARGET
    table = _by_path(principal_rows)[TABLE_TARGET]
    assert (table.identifiers or {})["legislation.govt.nz:label"] == ""
    for clause in ("4", "5", "6", "6A"):
        assert re.search(rf"(?m)^{clause} \|", table.body or "")
    assert not any(f"{PRINCIPAL}/schedule/4/part/7/clause/{clause}" in _by_path(principal_rows) for clause in ("4", "5", "6", "6a"))


def test_application_clauses_add_no_special_encoding_metadata(
    official_xml, original_rows, principal_rows, overlay
):
    before = _by_path(original_rows)
    after = _by_path(enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay))
    additions = {"amendment_target", "commencement_date", "commencement_citation_path", "part"}
    for suffix in ("schedule/1/part/16/clause/125", "schedule/2/part/18/clause/132"):
        path = f"{DOCUMENT}/{suffix}"
        assert set(after[path].metadata or {}) - set(before[path].metadata or {}) == additions


def test_legacy_opt_out_reproduces_all_four_locked_files(official_xml, tmp_path):
    store = CorpusArtifactStore(tmp_path / "data/corpus")
    report = extract_nz_legislation(
        store,
        version=OLD_VERSION,
        source_dir=SOURCE.parents[4],
        source_pattern=Path(SOURCE_NAME).name,
        source_as_of="2026-10-20",
        expression_date="2026-10-20",
    )
    assert report.provisions_written == 26
    lock = json.loads((ROOT / ".axiom/corpus-locks/nz/statute" / f"{OLD_VERSION}.json").read_text())
    assert len(lock["files"]) == 4
    for entry in lock["files"]:
        artifact = tmp_path / entry["path"]
        assert artifact.read_bytes() == (ROOT / entry["path"]).read_bytes()
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == entry["sha256"]
    assert official_xml == (tmp_path / "data/corpus/sources/nz/statute" / OLD_VERSION / SOURCE_NAME).read_bytes()


def test_wrong_but_existing_target_fails_with_amending_row(
    official_xml, original_rows, principal_rows, overlay
):
    overlay["targets"]["section/4"] = "section/63"
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/4")):
        enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay)


def test_nonexistent_principal_target_fails_with_amending_row(
    official_xml, original_rows, principal_rows, overlay
):
    principal_rows = [row for row in principal_rows if row.citation_path != f"{PRINCIPAL}/section/20"]
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/4")):
        enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay)


@pytest.mark.parametrize("inactive", ["repealed", "revoked", "not-in-force", "expired"])
def test_inactive_principal_target_fails_with_amending_row(
    official_xml, original_rows, principal_rows, overlay, inactive
):
    principal_rows = [
        replace(row, metadata={**(row.metadata or {}), "stage": inactive})
        if row.citation_path == f"{PRINCIPAL}/section/20" else row
        for row in principal_rows
    ]
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/4")):
        enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay)


@pytest.mark.parametrize("date", ["2 November 2026", "1 April 2027"])
def test_missing_commencement_date_in_row_fails_with_s2(
    official_xml, original_rows, principal_rows, overlay, date
):
    row = _by_path(original_rows)[f"{DOCUMENT}/section/2"]
    mutated = _replace_row(original_rows, "section/2", body=(row.body or "").replace(date, "a later date"))
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/2")):
        enrich_amendment_rows(official_xml, mutated, principal_rows, overlay)


def test_wrong_principal_name_in_s3_fails_with_s3(
    official_xml, original_rows, principal_rows, overlay
):
    mutated = _replace_row(original_rows, "section/3", body="This Act amends the Income Tax Act 2007.")
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/3")):
        enrich_amendment_rows(official_xml, mutated, principal_rows, overlay)


def test_unresolvable_xml_principal_id_fails_with_s3(
    official_xml, original_rows, principal_rows, overlay
):
    source = ET.fromstring(official_xml)
    reference = source.find("./body/prov[label='3']//leg-title")
    assert reference is not None
    reference.set("href", "UNKNOWN-PRINCIPAL")
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/3")):
        enrich_amendment_rows(ET.tostring(source), original_rows, principal_rows, overlay)


def test_missing_overlay_section_fails_with_omitted_row(
    official_xml, original_rows, principal_rows, overlay
):
    del overlay["targets"]["section/4"]
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/4")):
        enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay)


def test_missing_xml_schedule_empowering_reference_fails_with_schedule_row(
    official_xml, original_rows, principal_rows, overlay
):
    source = ET.fromstring(official_xml)
    schedule = source.find("./schedule.group/schedule[label='2']")
    assert schedule is not None
    empowering = schedule.find("empowering-prov")
    assert empowering is not None
    schedule.remove(empowering)
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/schedule/2")):
        enrich_amendment_rows(ET.tostring(source), original_rows, principal_rows, overlay)


def test_wrong_xml_commencement_part_reference_fails_with_s2(
    official_xml, original_rows, principal_rows, overlay
):
    source = ET.fromstring(official_xml)
    reference = source.find("./body/prov[label='2']//intref")
    assert reference is not None
    reference.set("href", "LMS1607692")  # Part 1, while the operative words say Part 2.
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/2")):
        enrich_amendment_rows(ET.tostring(source), original_rows, principal_rows, overlay)


def test_wrong_xml_principal_operative_words_fail_with_s3(
    official_xml, original_rows, principal_rows, overlay
):
    source = ET.fromstring(official_xml)
    text = source.find("./body/prov[label='3']/prov.body/subprov/para/text")
    assert text is not None
    text.text = "This Act repeals the "
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/3")):
        enrich_amendment_rows(ET.tostring(source), original_rows, principal_rows, overlay)


def test_missing_xml_amend_wrappers_fail_with_s3(
    official_xml, original_rows, principal_rows, overlay
):
    source = ET.fromstring(official_xml)
    for parent in list(source.iter()):
        for index, child in reversed(list(enumerate(parent))):
            if child.tag == "amend":
                parent.remove(child)
                for offset, grandchild in enumerate(list(child)):
                    parent.insert(index + offset, grandchild)
    assert not source.findall(".//amend")
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/3")):
        enrich_amendment_rows(ET.tostring(source), original_rows, principal_rows, overlay)


def test_table_target_without_replaced_clause_fails_with_s15(
    official_xml, original_rows, principal_rows, overlay
):
    principal_rows = [
        replace(row, body=re.sub(r"(?m)^4 \|.*(?:\n|$)", "", row.body or ""))
        if row.citation_path == TABLE_TARGET else row
        for row in principal_rows
    ]
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/15")):
        enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay)


def test_wrong_existing_xml_schedule_reference_fails_with_schedule_row(
    official_xml, original_rows, principal_rows, overlay
):
    source = ET.fromstring(official_xml)
    reference = source.find("./schedule.group/schedule[label='2']/empowering-prov//intref")
    section_11 = source.find("./body/part/prov[label='11']")
    assert reference is not None and section_11 is not None
    reference.set("href", section_11.attrib["id"])
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/schedule/2")):
        enrich_amendment_rows(ET.tostring(source), original_rows, principal_rows, overlay)


def test_misclassified_insertion_fails_with_amending_row(
    official_xml, original_rows, principal_rows, overlay
):
    del overlay["targets"]["section/4"]
    overlay["insertions"].append("section/4")
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/4")):
        enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay)


def test_reproduce_scope_copies_source_and_changes_only_metadata(
    official_xml, original_rows, tmp_path
):
    """Persist only added metadata and the explicitly allowed scope identity delta."""
    output = tmp_path / "output"
    report = reproduce_scope(
        base=BASE,
        output=output,
        overlay_path=OVERLAY,
        base_release=ROOT / "manifests/releases/nz-rulespec-2026-10-20.json",
        temp_root=tmp_path / "reextract",
    )
    assert report["rows"] == 26
    assert report["coverage"]["complete"]
    assert len([path for path in output.rglob("*") if path.is_file()]) == 4
    assert (output / "sources/nz/statute" / NEW_VERSION / SOURCE_NAME).read_bytes() == official_xml
    new_rows = _read_rows(output / "provisions/nz/statute" / f"{NEW_VERSION}.jsonl")
    assert len(new_rows) == 26
    assert [row.citation_path for row in new_rows] == [row.citation_path for row in original_rows]
    original_by_path = _by_path(original_rows)
    for new in new_rows:
        old = original_by_path[new.citation_path]
        assert {
            k: v for k, v in old.to_mapping().items()
            if k not in {"metadata", "version", "source_path"}
        } == {
            k: v for k, v in new.to_mapping().items()
            if k not in {"metadata", "version", "source_path"}
        }
        assert old.body == new.body
        assert all((new.metadata or {})[key] == value for key, value in (old.metadata or {}).items())
    old_inventory = json.loads((BASE / "inventory/nz/statute" / f"{OLD_VERSION}.json").read_text())
    new_inventory = json.loads((output / "inventory/nz/statute" / f"{NEW_VERSION}.json").read_text())
    assert old_inventory.keys() == new_inventory.keys()
    for old, new in zip(old_inventory["items"], new_inventory["items"], strict=True):
        assert {k: v for k, v in old.items() if k not in {"version", "source_path"}} == {
            k: v for k, v in new.items() if k not in {"version", "source_path"}
        }
    _assert_scope_identity(output)
    coverage = json.loads((output / "coverage/nz/statute" / f"{NEW_VERSION}.json").read_text())
    assert coverage["version"] == NEW_VERSION
    assert coverage["matched_count"] == coverage["provision_count"] == coverage["source_count"] == 26
    assert list((tmp_path / "reextract").iterdir()) == []


def _assert_scope_identity(output: Path) -> None:
    source_key = f"sources/nz/statute/{NEW_VERSION}/{SOURCE_NAME}"
    rows = _read_rows(output / "provisions/nz/statute" / f"{NEW_VERSION}.jsonl")
    inventory = json.loads((output / "inventory/nz/statute" / f"{NEW_VERSION}.json").read_text())
    assert len(rows) == len(inventory["items"]) == 26
    for row in rows:
        assert row.jurisdiction == "nz", row.citation_path
        assert row.document_class == "statute", row.citation_path
        assert row.version == NEW_VERSION, row.citation_path
        assert row.source_path == source_key, row.citation_path
    for item in inventory["items"]:
        assert item["version"] == NEW_VERSION, item["citation_path"]
        assert item["source_path"] == source_key, item["citation_path"]


def _isolated_release() -> ReleaseManifest:
    return ReleaseManifest(
        name="nz-amendment-marker-isolated-validation",
        scopes=(ReleaseScope("nz", "statute", NEW_VERSION),),
        quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
    )


@pytest.fixture(scope="module")
def successor_scope(tmp_path_factory) -> Path:
    temporary = tmp_path_factory.mktemp("successor")
    output = temporary / "output"
    reproduce_scope(
        base=BASE,
        output=output,
        overlay_path=OVERLAY,
        base_release=ROOT / "manifests/releases/nz-rulespec-2026-10-20.json",
        temp_root=temporary / "reextract",
    )
    return output


def test_successor_identity_passes_existing_release_gates(successor_scope):
    _assert_scope_identity(successor_scope)
    report = validate_release(
        successor_scope, _isolated_release(), policy=ReleaseGatePolicy.empty()
    )
    assert report.ok, report.to_mapping()
    assert report.error_count == report.warning_count == 0


@pytest.mark.parametrize("artifact,field,code", [
    ("provisions", "version", "provision_version_mismatch"),
    ("provisions", "source_path", "noncanonical_provision_source_path"),
    ("inventory", "source_path", "noncanonical_inventory_source_path"),
])
def test_old_scope_identity_fails_identity_assertion_and_release_gate(
    successor_scope, tmp_path, artifact, field, code
):
    output = tmp_path / "mutated"
    shutil.copytree(successor_scope, output)
    suffix = "jsonl" if artifact == "provisions" else "json"
    path = output / artifact / "nz/statute" / f"{NEW_VERSION}.{suffix}"
    if artifact == "provisions":
        rows = _read_rows(path)
        old_value = OLD_VERSION if field == "version" else f"sources/nz/statute/{OLD_VERSION}/{SOURCE_NAME}"
        rows[0] = replace(rows[0], **{field: old_value})
        CorpusArtifactStore(output).write_provisions(path, rows)
    else:
        inventory = json.loads(path.read_text())
        inventory["items"][0][field] = f"sources/nz/statute/{OLD_VERSION}/{SOURCE_NAME}"
        CorpusArtifactStore(output).write_json(path, inventory)
    with pytest.raises(AssertionError, match=re.escape(DOCUMENT)):
        _assert_scope_identity(output)
    report = validate_release(output, _isolated_release(), policy=ReleaseGatePolicy.empty())
    assert not report.ok
    assert report.error_count == 1, report.to_mapping()
    assert [issue.code for issue in report.issues] == [code]


def test_old_inventory_version_fails_identity_assertion(successor_scope, tmp_path):
    """The opt-in inventory version is checked even though the shared model omits it."""
    output = tmp_path / "mutated"
    shutil.copytree(successor_scope, output)
    path = output / "inventory/nz/statute" / f"{NEW_VERSION}.json"
    inventory = json.loads(path.read_text())
    inventory["items"][0]["version"] = OLD_VERSION
    CorpusArtifactStore(output).write_json(path, inventory)
    with pytest.raises(AssertionError, match=re.escape(DOCUMENT)):
        _assert_scope_identity(output)


@pytest.mark.parametrize("malformed", [None, "not an overlay", [], ["targets", "insertions"], {}])
def test_malformed_overlay_fails_with_document(
    official_xml, original_rows, principal_rows, malformed
):
    with pytest.raises(ValueError, match=re.escape(DOCUMENT)):
        enrich_amendment_rows(official_xml, original_rows, principal_rows, malformed)


def test_numeric_overlay_target_key_fails_with_document(
    official_xml, original_rows, principal_rows, overlay
):
    overlay["targets"][4] = overlay["targets"].pop("section/4")
    with pytest.raises(ValueError, match=re.escape(DOCUMENT)):
        enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay)


def test_duplicate_row_fails_with_duplicated_row(
    official_xml, original_rows, principal_rows, overlay
):
    duplicate = _by_path(original_rows)[f"{DOCUMENT}/section/4"]
    with pytest.raises(ValueError, match=re.escape(duplicate.citation_path)):
        enrich_amendment_rows(official_xml, [*original_rows, duplicate], principal_rows, overlay)


def test_document_xml_identifier_mismatch_fails_with_document(
    official_xml, original_rows, principal_rows, overlay
):
    rows = [
        replace(row, identifiers={**(row.identifiers or {}), "legislation.govt.nz:id": "WRONG-ID"})
        if row.citation_path == DOCUMENT else row
        for row in original_rows
    ]
    with pytest.raises(ValueError, match=re.escape(DOCUMENT)):
        enrich_amendment_rows(official_xml, rows, principal_rows, overlay)


@pytest.mark.parametrize("malformed", [None, 20, {}, [], [20], ["section/20", "section/20"]])
def test_malformed_or_duplicate_target_list_fails_with_amending_row(
    official_xml, original_rows, principal_rows, overlay, malformed
):
    overlay["targets"]["section/4"] = malformed
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/4")):
        enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay)


@pytest.mark.parametrize("malformed", [None, "section/5", [5], ["section/5", "section/5"]])
def test_malformed_or_duplicate_insertions_fail_with_document(
    official_xml, original_rows, principal_rows, overlay, malformed
):
    overlay["insertions"] = malformed
    with pytest.raises(ValueError, match=re.escape(DOCUMENT)):
        enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay)


def test_target_and_insertion_overlap_fails_with_document(
    official_xml, original_rows, principal_rows, overlay
):
    overlay["insertions"].append("section/4")
    with pytest.raises(ValueError, match=re.escape(DOCUMENT)):
        enrich_amendment_rows(official_xml, original_rows, principal_rows, overlay)


@pytest.mark.parametrize("mutation", ["invalid_date", "missing_act", "unsupported", "duplicate", "missing_xml", "missing_row"])
def test_invalid_or_missing_act_commencement_fails_with_s2(
    official_xml, original_rows, principal_rows, overlay, mutation
):
    source = ET.fromstring(official_xml)
    section = source.find("./body/prov[label='2']")
    assert section is not None
    body = section.find("prov.body")
    assert body is not None
    general = body.find("subprov[label='1']")
    assert general is not None
    text = general.find("para/text")
    assert text is not None
    rows = original_rows
    if mutation == "invalid_date":
        text.text = "This Act comes into force on 32 November 2026."
        old_body = _by_path(rows)[f"{DOCUMENT}/section/2"].body or ""
        rows = _replace_row(rows, "section/2", body=old_body.replace("2 November 2026", "32 November 2026"))
    elif mutation == "missing_act":
        body.remove(general)
    elif mutation == "unsupported":
        text.text = "This Act commences at a time set by Order in Council."
    elif mutation == "duplicate":
        body.append(copy.deepcopy(general))
    elif mutation == "missing_xml":
        source.find("body").remove(section)
    else:
        rows = [row for row in rows if row.citation_path != f"{DOCUMENT}/section/2"]
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/2")):
        enrich_amendment_rows(ET.tostring(source), rows, principal_rows, overlay)


def test_missing_xml_amending_section_fails_with_omitted_row(
    official_xml, original_rows, principal_rows, overlay
):
    source = ET.fromstring(official_xml)
    part = source.find("./body/part[label='1']")
    assert part is not None
    section = part.find("prov[label='4']")
    assert section is not None
    part.remove(section)
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/4")):
        enrich_amendment_rows(ET.tostring(source), original_rows, principal_rows, overlay)


def test_unbound_extra_row_fails_with_extra_row(
    official_xml, original_rows, principal_rows, overlay
):
    unknown = replace(
        _by_path(original_rows)[f"{DOCUMENT}/section/4"],
        citation_path=f"{DOCUMENT}/section/999",
    )
    with pytest.raises(ValueError, match=re.escape(unknown.citation_path)):
        enrich_amendment_rows(official_xml, [*original_rows, unknown], principal_rows, overlay)


def test_corrupted_retained_source_fails_before_writing_scope(official_xml, tmp_path):
    base = tmp_path / "input"
    source = base / "sources/nz/statute" / OLD_VERSION / SOURCE_NAME
    source.parent.mkdir(parents=True)
    source.write_bytes(official_xml + b"\n")
    output = tmp_path / "output"
    with pytest.raises(ValueError, match=re.escape(DOCUMENT)):
        reproduce_scope(
            base=base,
            output=output,
            overlay_path=OVERLAY,
            base_release=ROOT / "manifests/releases/nz-rulespec-2026-10-20.json",
            temp_root=tmp_path / "reextract",
        )
    assert not output.exists()
    assert not (tmp_path / "reextract").exists()


@pytest.mark.parametrize("artifact", ["inventory", "coverage", "provisions"])
def test_reproducer_rejects_byte_drift_in_predecessor_artifact(
    official_xml, tmp_path, artifact
):
    base = tmp_path / "input"
    lock = json.loads((ROOT / ".axiom/corpus-locks/nz/statute" / f"{OLD_VERSION}.json").read_text())
    for entry in lock["files"]:
        relative = Path(entry["path"]).relative_to("data/corpus")
        destination = base / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / entry["path"]).read_bytes())
    extension = "jsonl" if artifact == "provisions" else "json"
    relative = Path(artifact) / "nz/statute" / f"{OLD_VERSION}.{extension}"
    predecessor = base / relative
    payload = predecessor.read_bytes()
    predecessor.write_bytes(payload.replace(b"{", b"{ ", 1) if artifact == "provisions" else payload + b"\n")
    output = tmp_path / "output"
    with pytest.raises(ValueError, match=re.escape(f"{relative.as_posix()}: legacy extraction is not byte-identical")):
        reproduce_scope(
            base=base,
            output=output,
            overlay_path=OVERLAY,
            base_release=ROOT / "manifests/releases/nz-rulespec-2026-10-20.json",
            temp_root=tmp_path / "reextract",
        )
    assert not output.exists()
    assert list((tmp_path / "reextract").iterdir()) == []


@pytest.mark.parametrize("field,value", [
    ("body", "mutated"),
    ("heading", "mutated"),
    ("ordinal", 999),
    ("id", "mutated"),
    ("source_as_of", "2099-01-01"),
])
def test_reproducer_rejects_enrichment_that_changes_provision_body(
    official_xml, tmp_path, monkeypatch, field, value
):
    from axiom_corpus.corpus import nz_amendment_markers

    original = nz_amendment_markers.enrich_amendment_rows

    def mutate_body(*args, **kwargs):
        rows = original(*args, **kwargs)
        return _replace_row(rows, "section/4", **{field: value})

    monkeypatch.setattr(nz_amendment_markers, "enrich_amendment_rows", mutate_body)
    output = tmp_path / "output"
    with pytest.raises(ValueError, match=re.escape(f"{DOCUMENT}/section/4: enrichment changed a field other than metadata")):
        reproduce_scope(
            base=BASE,
            output=output,
            overlay_path=OVERLAY,
            base_release=ROOT / "manifests/releases/nz-rulespec-2026-10-20.json",
            temp_root=tmp_path / "reextract",
        )
    assert not output.exists()
    assert list((tmp_path / "reextract").iterdir()) == []
