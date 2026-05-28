"""New Jersey SNAP rule reconstruction from primary official sources."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TextIO

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

NEW_JERSEY_SNAP_JURISDICTION = "us-nj"
NEW_JERSEY_SNAP_DOCUMENT_CLASS = DocumentClass.REGULATION.value
NEW_JERSEY_SNAP_ROOT = "us-nj/regulation/njac-10-87"
NEW_JERSEY_SNAP_RECONSTRUCTION_SOURCE_ID = "njac-10-87-reconstructed-current"


@dataclass(frozen=True)
class NewJerseySnapReconstructionReport:
    """Result from reconstructing the current N.J.A.C. 10:87 SNAP scope."""

    jurisdiction: str
    document_class: str
    version: str
    base_provisions_path: Path
    rulemaking_provisions_path: Path
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    modified_citation_paths: tuple[str, ...]
    added_citation_paths: tuple[str, ...]


def reconstruct_new_jersey_snap_rules(
    store: CorpusArtifactStore,
    *,
    version: str,
    base_provisions_path: str | Path,
    rulemaking_provisions_path: str | Path,
    source_as_of: str,
    expression_date: str,
    progress_stream: TextIO | None = None,
) -> NewJerseySnapReconstructionReport:
    """Build a current N.J.A.C. 10:87 scope from official base and notices."""
    base_path = Path(base_provisions_path)
    rulemaking_path = Path(rulemaking_provisions_path)
    base_records = load_provisions(base_path)
    rulemaking_records = load_provisions(rulemaking_path)
    if not base_records:
        raise ValueError(f"New Jersey SNAP base provisions not found: {base_path}")
    if not rulemaking_records:
        raise ValueError(f"New Jersey SNAP rulemaking provisions not found: {rulemaking_path}")

    _progress(progress_stream, "loading New Jersey SNAP base sections")
    section_by_suffix = {
        record.citation_path.rsplit("/", 1)[-1]: record
        for record in base_records
        if record.citation_path.startswith(NEW_JERSEY_SNAP_ROOT)
    }
    root = section_by_suffix.get("njac-10-87") or next(
        (record for record in base_records if record.citation_path == NEW_JERSEY_SNAP_ROOT),
        None,
    )
    if root is None:
        raise ValueError("New Jersey SNAP base is missing the N.J.A.C. 10:87 root record")

    records = {
        record.citation_path: _current_record(
            record,
            version=version,
            source_as_of=source_as_of,
            expression_date=expression_date,
            modified_by=(),
        )
        for record in base_records
    }

    modified: set[str] = set()

    def update_section(
        suffix: str,
        body: str,
        *,
        modified_by: tuple[str, ...],
        heading: str | None = None,
    ) -> None:
        citation_path = f"{NEW_JERSEY_SNAP_ROOT}/{suffix}"
        if citation_path not in records:
            raise ValueError(f"New Jersey SNAP section not found: {citation_path}")
        records[citation_path] = replace(
            records[citation_path],
            body=_apply_terminology_changes(_normalize_reconstructed_text(body)),
            heading=heading or records[citation_path].heading,
            metadata=_record_metadata(
                records[citation_path],
                modified_by=modified_by,
                reconstruction_note="current section reconstructed from official base and modifying notices",
            ),
        )
        modified.add(citation_path)

    _progress(progress_stream, "applying New Jersey SNAP rulemaking notices")
    update_section(
        "10-87-2.2",
        _apply_2024_spouse_definition(_body(section_by_suffix, "10-87-2.2")),
        modified_by=("r-2024-d-059-56-njr-1105b",),
    )
    update_section(
        "10-87-2.26",
        _apply_2023_normal_processing(_body(section_by_suffix, "10-87-2.26")),
        modified_by=("r-2023-d-083-55-njr-1335a",),
    )
    update_section(
        "10-87-2.32",
        _apply_2025_categorical_eligibility(_body(section_by_suffix, "10-87-2.32")),
        modified_by=("r-2025-d-108-57-njr-2267a",),
    )
    update_section(
        "10-87-3.14",
        _apply_2024_student_procedures(
            _body(section_by_suffix, "10-87-3.14"),
            _notice_section(
                rulemaking_records,
                source_id="r-2024-d-103-56-njr-2081a",
                label="10:87-3.14",
                heading="Procedures for students in an institution of higher education",
            ),
        ),
        modified_by=("r-2024-d-103-56-njr-2081a",),
    )
    update_section(
        "10-87-3.17",
        _notice_section(
            rulemaking_records,
            source_id="r-2025-d-110-57-njr-2267b",
            label="10:87-3.17",
            heading="Fleeing felons and probation or parole violators",
        ),
        modified_by=("r-2025-d-110-57-njr-2267b",),
        heading="10:87-3.17 Fleeing felons and probation or parole violators",
    )
    update_section(
        "10-87-5.4",
        _apply_2018_earned_income_correction(_body(section_by_suffix, "10-87-5.4")),
        modified_by=("noac-2018-10-87-5-4-50-njr-1814c",),
    )
    update_section(
        "10-87-5.7",
        _apply_2025_special_income(_body(section_by_suffix, "10-87-5.7")),
        modified_by=("r-2025-d-108-57-njr-2267a",),
    )
    update_section(
        "10-87-5.10",
        _apply_2024_income_deductions(_body(section_by_suffix, "10-87-5.10")),
        modified_by=("r-2024-d-045-56-njr-905a",),
    )
    update_section(
        "10-87-9.11",
        "Unused NJ SNAP benefits will remain accessible to the household until they "
        "are expunged from the EBT account pursuant to N.J.A.C. 10:88-4.2.",
        modified_by=("r-2023-d-083-55-njr-1335a",),
        heading="10:87-9.11 Procedures for expungement of electronic NJ SNAP benefits",
    )
    update_section(
        "10-87-11.20",
        _apply_2023_claims_collection(_body(section_by_suffix, "10-87-11.20")),
        modified_by=("r-2023-d-083-55-njr-1335a",),
    )

    added = _append_2023_minimum_benefit_sections(
        records,
        rulemaking_records=rulemaking_records,
        version=version,
        source_as_of=source_as_of,
        expression_date=expression_date,
    )

    reconstructed = _ordered_records(records.values())
    inventory = tuple(_inventory_item(record) for record in reconstructed)
    inventory_path = store.inventory_path(
        NEW_JERSEY_SNAP_JURISDICTION,
        NEW_JERSEY_SNAP_DOCUMENT_CLASS,
        version,
    )
    provisions_path = store.provisions_path(
        NEW_JERSEY_SNAP_JURISDICTION,
        NEW_JERSEY_SNAP_DOCUMENT_CLASS,
        version,
    )
    coverage_path = store.coverage_path(
        NEW_JERSEY_SNAP_JURISDICTION,
        NEW_JERSEY_SNAP_DOCUMENT_CLASS,
        version,
    )
    store.write_inventory(inventory_path, inventory)
    store.write_provisions(provisions_path, reconstructed)
    coverage = compare_provision_coverage(
        inventory,
        reconstructed,
        jurisdiction=NEW_JERSEY_SNAP_JURISDICTION,
        document_class=NEW_JERSEY_SNAP_DOCUMENT_CLASS,
        version=version,
    )
    store.write_json(coverage_path, coverage.to_mapping())

    return NewJerseySnapReconstructionReport(
        jurisdiction=NEW_JERSEY_SNAP_JURISDICTION,
        document_class=NEW_JERSEY_SNAP_DOCUMENT_CLASS,
        version=version,
        base_provisions_path=base_path,
        rulemaking_provisions_path=rulemaking_path,
        provisions_written=len(reconstructed),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        modified_citation_paths=tuple(sorted(modified)),
        added_citation_paths=tuple(sorted(added)),
    )


def _current_record(
    record: ProvisionRecord,
    *,
    version: str,
    source_as_of: str,
    expression_date: str,
    modified_by: tuple[str, ...],
) -> ProvisionRecord:
    heading = record.heading
    citation_label = record.citation_label
    if record.citation_path == NEW_JERSEY_SNAP_ROOT:
        heading = "N.J.A.C. 10:87 New Jersey Supplemental Nutrition Assistance Program (NJ SNAP) Manual"
        citation_label = "N.J.A.C. 10:87"
    return replace(
        record,
        version=version,
        source_id=NEW_JERSEY_SNAP_RECONSTRUCTION_SOURCE_ID,
        source_as_of=source_as_of,
        expression_date=expression_date,
        heading=heading,
        citation_label=citation_label,
        body=(
            _apply_terminology_changes(_normalize_reconstructed_text(record.body))
            if record.body is not None
            else None
        ),
        metadata=_record_metadata(
            record,
            modified_by=modified_by,
            reconstruction_note=(
                "current section carried forward from official base with global "
                "DFD terminology administrative change"
            ),
        ),
    )


def _record_metadata(
    record: ProvisionRecord,
    *,
    modified_by: tuple[str, ...],
    reconstruction_note: str,
) -> dict[str, object]:
    metadata = dict(record.metadata or {})
    metadata.update(
        {
            "reconstruction_status": "compiled_from_primary_sources",
            "reconstruction_note": reconstruction_note,
            "base_source_version": "2017-02-06-nj-snap-rules-base",
            "global_modifying_source": "noac-2024-dfd-terminology-56-njr-1244a",
        }
    )
    if modified_by:
        metadata["modified_by_rulemaking_source_ids"] = list(modified_by)
    return metadata


def _inventory_item(record: ProvisionRecord) -> SourceInventoryItem:
    return SourceInventoryItem(
        citation_path=record.citation_path,
        source_url=record.source_url,
        source_path=record.source_path,
        source_format=record.source_format,
        metadata={
            "kind": record.kind,
            "source_as_of": record.source_as_of,
            "expression_date": record.expression_date,
            "reconstruction_status": "compiled_from_primary_sources",
        },
    )


def _append_2023_minimum_benefit_sections(
    records: dict[str, ProvisionRecord],
    *,
    rulemaking_records: tuple[ProvisionRecord, ...],
    version: str,
    source_as_of: str,
    expression_date: str,
) -> tuple[str, ...]:
    source_id = "r-2023-d-140-55-njr-2550a"
    sections = _notice_sections(
        rulemaking_records,
        source_id=source_id,
        labels=(
            ("10:87-13.1", "Authority and purpose"),
            ("10:87-13.2", "Eligibility and benefit amount"),
            ("10:87-13.3", "Benefit distribution and use"),
            ("10:87-13.4", "Applicability of Federal SNAP rules"),
        ),
    )
    source_record = next(
        record
        for record in rulemaking_records
        if record.source_id == source_id and record.kind == "document"
    )
    added: list[str] = []
    for label, heading, body in sections:
        suffix = label.replace(":", "-")
        citation_path = f"{NEW_JERSEY_SNAP_ROOT}/{suffix}"
        record = ProvisionRecord(
            id=deterministic_provision_id(citation_path),
            jurisdiction=NEW_JERSEY_SNAP_JURISDICTION,
            document_class=NEW_JERSEY_SNAP_DOCUMENT_CLASS,
            citation_path=citation_path,
            body=_apply_terminology_changes(_normalize_reconstructed_text(body)),
            heading=f"{label} {heading}",
            citation_label=f"N.J.A.C. {label}",
            version=version,
            source_url=source_record.source_url,
            source_path=source_record.source_path,
            source_id=NEW_JERSEY_SNAP_RECONSTRUCTION_SOURCE_ID,
            source_format=source_record.source_format,
            source_as_of=source_as_of,
            expression_date=expression_date,
            parent_citation_path=NEW_JERSEY_SNAP_ROOT,
            parent_id=deterministic_provision_id(NEW_JERSEY_SNAP_ROOT),
            level=2,
            kind="section",
            legal_identifier=f"N.J.A.C. {label}",
            metadata={
                "kind": "section",
                "reconstruction_status": "compiled_from_primary_sources",
                "reconstruction_note": "current section added by official rule adoption",
                "base_source_version": "2017-02-06-nj-snap-rules-base",
                "modified_by_rulemaking_source_ids": [source_id],
            },
        )
        records[citation_path] = record
        added.append(citation_path)
    return tuple(added)


def _notice_sections(
    records: tuple[ProvisionRecord, ...],
    *,
    source_id: str,
    labels: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str, str], ...]:
    text = _notice_text(records, source_id=source_id)
    out: list[tuple[str, str, str]] = []
    for index, (label, heading) in enumerate(labels):
        start_marker = f"{label} {heading}"
        start = text.find(start_marker)
        if start < 0:
            raise ValueError(f"notice {source_id} missing section {label}")
        body_start = start + len(start_marker)
        if index + 1 < len(labels):
            end_marker = f"{labels[index + 1][0]} {labels[index + 1][1]}"
            end = text.find(end_marker, body_start)
        else:
            end = text.find("__________", body_start)
        if end < 0:
            raise ValueError(f"notice {source_id} missing end marker for {label}")
        out.append((label, heading, _strip_register_noise(text[body_start:end])))
    return tuple(out)


def _notice_section(
    records: tuple[ProvisionRecord, ...],
    *,
    source_id: str,
    label: str,
    heading: str,
) -> str:
    text = _notice_text(records, source_id=source_id)
    marker = f"{label} {heading}"
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"notice {source_id} missing section {label}")
    body_start = start + len(marker)
    end = text.find("__________", body_start)
    if end < 0:
        raise ValueError(f"notice {source_id} missing end marker for {label}")
    return _strip_register_noise(text[body_start:end])


def _notice_text(records: tuple[ProvisionRecord, ...], *, source_id: str) -> str:
    text = "\n".join(
        record.body or ""
        for record in records
        if record.source_id == source_id and record.kind == "page"
    )
    if not text:
        raise ValueError(f"notice source not found: {source_id}")
    return text


def _apply_2018_earned_income_correction(body: str) -> str:
    return _require_replace(
        body,
        "N.J.A.C. 10:87-5.9(a)10ii",
        "N.J.A.C. 10:87-5.9(a)11ii",
    )


def _apply_2023_normal_processing(body: str) -> str:
    return _require_replace(
        body,
        "staggered issuance procedure which has been established by a CWA",
        "staggered issuance procedure that has been established by a CWA",
    )


def _apply_2023_claims_collection(body: str) -> str:
    old = (
        "(1) For collecting from active (or reactivated) EBT benefits the CWA needs written "
        "permission, which may be ob- tained in advance and done in accordance with (p)2iii "
        "below; or oral permission for one time reductions with the CWA sending the household "
        "a receipt of the transaction within 10 days. The retention rates described at (v) "
        "below apply to this collection. (2) For collecting from stale EBT benefits the CWA "
        "shall mail or otherwise deliver to the household, written noti- fication that the "
        "CWA intends to apply the benefits to the outstanding claim, and give the household "
        "at least 10 days to notify the CWA that it does not want to use these benefits to "
        "pay the claim. The retention rates described at (v) below apply to this collection. "
        "(3) For making an adjustment with expunged EBT benefits the CWA shall adjust the "
        "amount of any claim by sub- tracting any expunged amount from the EBT benefit "
        "account which the CWA becomes aware of. This adjustment can be done at any time. "
        "The retention rates described at (v) below do not apply to this balance adjustment."
    )
    new = (
        "(1) For collecting from active EBT benefits, the CWA needs written permission, "
        "which may be obtained in advance and done in accordance with (p)2iii below; or "
        "oral permission for one time reductions with the CWA sending the household a "
        "receipt of the transaction within 10 days. The retention rates described at (v) "
        "below apply to this collection. (2) For collecting from expunged EBT benefits, "
        "the CWA shall mail or otherwise deliver to the household, written notification "
        "that expunged benefits will be applied to any outstanding claim. The retention "
        "rates described at (v) below apply to this collection. (3) (No change.)"
    )
    return _require_replace(body, old, new)


def _apply_2024_spouse_definition(body: str) -> str:
    old = (
        '3. A spouse of a member of the household. For the purposes of this Program, the term '
        '"spouse" shall include per- sons recognized by applicable State law as such and '
        "persons representing themselves as husband and wife to the com- munity, relatives, "
        "friends, neighbors or trades people; or"
    )
    new = (
        '3. A spouse of a member of the household. For the purposes of this Program, the term '
        '"spouse" shall include persons who are legally married pursuant to New Jersey law, '
        "as well as individuals in a domestic partnership, pursuant to N.J.S.A. 26:8A-1 et "
        "seq., and civil union partners, pursuant to N.J.S.A. 37:1-28 et seq.; or"
    )
    return _require_replace(body, old, new)


def _apply_2024_student_procedures(old_body: str, notice_body: str) -> str:
    body = notice_body
    work_study = _between(
        old_body,
        "2. Participate in a Federally financed work study program",
        "3. Be responsible for the care of a dependent household member under the age of six;",
        include_start=True,
    )
    child_care_i = _between(
        old_body,
        "i. The availability and adequacy of child care shall be determined by the CWA",
        "ii. Only one person per dependent may qualify under this provision;",
        include_start=True,
    )
    trade_act = _between(
        old_body,
        "iii. A program under Section 236 of the Trade Act of 1974",
        "iv. An employment and training program for low-income households",
        include_start=True,
    )
    body = _require_replace(body, "2. (No change.)", work_study)
    body = _require_replace(body, "i. (No change.)", child_care_i, count=1)
    body = _require_replace(body, "iii. (No change.)", trade_act, count=1)
    return body


def _apply_2024_income_deductions(body: str) -> str:
    old = "(9) Reasonable cost of transportation and lodging to obtain medical treatment or services;"
    new = (
        "(9) Reasonable cost of transportation and lodging to obtain medical treatment or "
        "services. (A) When a privately owned vehicle is used for transportation to obtain "
        "medical treatment or services, the reasonable cost of transportation shall be "
        "calculated by using the State of New Jersey mileage reimbursement rate for use of "
        "a personal vehicle, as determined by the applicable circular published by the New "
        "Jersey Department of the Treasury, Office of Management and Budget. The State "
        "mileage reimbursement rate must be used in lieu of the actual expenses of "
        "transportation; and"
    )
    return _require_replace(body, old, new)


def _apply_2025_categorical_eligibility(body: str) -> str:
    body = _require_replace(body, "listed in (c) below", "listed at (c) below", count=1)
    return _require_replace(
        body,
        "Federal money under Title IV-A designed to forward purposes one and two",
        "Federal money pursuant to Title IV-A designed to forward purposes one and two",
        count=1,
    )


def _apply_2025_special_income(body: str) -> str:
    body = _require_replace(
        body,
        " If the new member is a capped child the WFNJ/TANF grant will not increase, how- ever, "
        "the child will be included in the NJ SNAP household and the NJ SNAP allotment shall "
        "increase accordingly.",
        "",
    )
    old = (
        "(d) The following are good cause reasons for not applying the Riverside Rule. The ban "
        "on increasing benefits does not apply under these circumstances. 1. Clients whose "
        "WFNJ/TANF or WFNJ/GA benefits are terminated; 2. Clients have a child subject to "
        "the TANF family cap; 3. Clients fail to reapply or to complete the reapplication "
        "process for continued WFNJ cash assistance; 4. Clients fail to perform a purely "
        "procedural requirement, such as failing to sign an application; or 5. Clients fail "
        "to perform a required action because they are unable to complete the action through "
        "no fault of their own."
    )
    new = (
        "(d) The following are good cause reasons for not applying the Riverside Rule. The ban "
        "on increasing benefits does not apply under these circumstances. 1. Clients whose "
        "WFNJ/TANF or WFNJ/GA benefits are terminated; 2. Clients fail to reapply or to "
        "complete the reapplication process for continued WFNJ cash assistance; 3. Clients "
        "fail to perform a purely procedural requirement, such as failing to sign an "
        "application; or 4. Clients fail to perform a required action because they are unable "
        "to complete the action through no fault of their own."
    )
    return _require_replace(body, old, new)


def _body(section_by_suffix: dict[str, ProvisionRecord], suffix: str) -> str:
    try:
        body = section_by_suffix[suffix].body
    except KeyError as exc:
        raise ValueError(f"New Jersey SNAP base missing section {suffix}") from exc
    if not body:
        raise ValueError(f"New Jersey SNAP base section has no body: {suffix}")
    return body


def _between(text: str, start: str, end: str, *, include_start: bool = False) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise ValueError(f"start marker not found: {start}")
    end_index = text.find(end, start_index + len(start))
    if end_index < 0:
        raise ValueError(f"end marker not found: {end}")
    return text[start_index if include_start else start_index + len(start) : end_index].strip()


def _require_replace(text: str, old: str, new: str, *, count: int = -1) -> str:
    if old not in text:
        raise ValueError(f"required New Jersey SNAP text not found: {old[:120]}")
    if count == -1:
        return text.replace(old, new)
    return text.replace(old, new, count)


def _apply_terminology_changes(text: str | None) -> str | None:
    if text is None:
        return None
    replacements = (
        (r"\bCWAs\b", "CSSAs"),
        (r"\bCWA\b", "CSSA"),
        (r"\bcounty welfare agencies\b", "county social service agencies"),
        (r"\bCounty welfare agencies\b", "County social service agencies"),
        (r"\bcounty welfare agency\b", "county social service agency"),
        (r"\bCounty Welfare Agency\b", "County Social Service Agency"),
        (r"\bcounty welfare board\b", "county social services board"),
        (r"\bcounty welfare boards\b", "county social services boards"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def _strip_register_noise(text: str) -> str:
    text = re.sub(
        r"\s*HUMAN SERVICES\s+ADOPTIONS\s+\(CITE [^)]+\)\s+NEW JERSEY REGISTER,"
        r"\s+[A-Z]+,\s+[A-Z]+\s+\d{1,2},\s+\d{4}\s*",
        " ",
        text,
    )
    text = re.sub(
        r"\s*ADOPTIONS\s+HUMAN SERVICES\s+NEW JERSEY REGISTER,"
        r"\s+[A-Z]+,\s+[A-Z]+\s+\d{1,2},\s+\d{4}\s+\(CITE [^)]+\)\s*",
        " ",
        text,
    )
    normalized = _normalize_reconstructed_text(text)
    if normalized is None:
        raise ValueError("New Jersey SNAP notice text unexpectedly normalized to empty")
    return normalized


def _normalize_reconstructed_text(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.replace("\x00", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _ordered_records(records: Iterable[ProvisionRecord]) -> tuple[ProvisionRecord, ...]:
    sorted_records = sorted(records, key=_record_sort_key)
    root_id = deterministic_provision_id(NEW_JERSEY_SNAP_ROOT)
    out: list[ProvisionRecord] = []
    section_ordinal = 0
    for record in sorted_records:
        if record.citation_path == NEW_JERSEY_SNAP_ROOT:
            out.append(
                replace(
                    record,
                    id=root_id,
                    citation_label="N.J.A.C. 10:87",
                    legal_identifier="N.J.A.C. 10:87",
                    level=1,
                    ordinal=1,
                    parent_id=None,
                )
            )
            continue
        section_ordinal += 1
        legal_identifier = _legal_identifier(record.citation_path)
        out.append(
            replace(
                record,
                id=deterministic_provision_id(record.citation_path),
                citation_label=legal_identifier,
                legal_identifier=legal_identifier,
                parent_citation_path=NEW_JERSEY_SNAP_ROOT,
                parent_id=root_id,
                level=2,
                ordinal=section_ordinal,
            )
        )
    return tuple(out)


def _legal_identifier(citation_path: str) -> str:
    suffix = citation_path.rsplit("/", 1)[-1]
    return f"N.J.A.C. {suffix.replace('10-87-', '10:87-')}"


def _record_sort_key(record: ProvisionRecord) -> tuple[int, tuple[int, ...], str]:
    if record.citation_path == NEW_JERSEY_SNAP_ROOT:
        return (0, (), record.citation_path)
    suffix = record.citation_path.rsplit("/", 1)[-1]
    match = re.match(r"10-87-(?P<label>[0-9A-Za-z.]+)$", suffix)
    if not match:
        return (2, (), record.citation_path)
    parts: list[int] = []
    for part in re.split(r"[.A-Za-z]+", match.group("label")):
        if part.isdigit():
            parts.append(int(part))
    return (1, tuple(parts), suffix)


def _progress(stream: TextIO | None, message: str) -> None:
    if stream is not None:
        print(message, file=stream)
