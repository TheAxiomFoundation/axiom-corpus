#!/usr/bin/env python3
"""Reproduce the California CalFresh BBCE authority ingest from exact sources."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import fitz

from axiom_corpus.corpus import documents
from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import OfficialDocumentManifest
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.states import extract_california_code_sections

REPO_ROOT = Path(__file__).resolve().parents[2]
RETAINED_BASE = REPO_ROOT / "data/corpus"
MANIFEST_PATH = REPO_ROOT / "manifests/us-ca-cdss-calfresh-bbce-authority.yaml"

VERSION = "2026-07-28-ca-cdss-calfresh-bbce-authority"
GUIDANCE_VERSION = VERSION
STATUTE_SECTIONS = ("WIC:18901.3", "WIC:18901.5")
STATUTE_INPUTS = ("WIC-18901.3.html", "WIC-18901.5.html")
STATUTE_VERSION = f"{VERSION}-us-ca-sections-wic-18901.3-wic-18901.5"
SOURCE_AS_OF = "2026-07-28"
REPRO_COMMAND = (
    "uv run --extra dev python "
    "scripts/repro/us_ca_calfresh_bbce_authority.py --base data/corpus"
)

GUIDANCE_INPUT_BY_SOURCE_ID = {
    "ca-cdss-acl-2014-14-56": "14-56.pdf",
    "ca-cdss-acl-2014-14-56e": "14-56e.pdf",
    "ca-cdss-acl-2014-14-63": "14-63.pdf",
    "ca-cdss-acl-2015-15-42": "15-42.pdf",
    "ca-cdss-acl-2014-14-100": "14-100.pdf",
    "ca-cdss-acl-2013-13-32": "13-32.pdf",
}
ROOT_CITATION_BY_SOURCE_ID = {
    "ca-cdss-acl-2014-14-56": "us-ca/guidance/cdss/acl-2014-14-56",
    "ca-cdss-acl-2014-14-56e": "us-ca/guidance/cdss/acl-2014-14-56e",
    "ca-cdss-acl-2014-14-63": "us-ca/guidance/cdss/acl-2014-14-63",
    "ca-cdss-acl-2015-15-42": "us-ca/guidance/cdss/acl-2015-15-42",
    "ca-cdss-acl-2014-14-100": "us-ca/guidance/cdss/acl-2014-14-100",
    "ca-cdss-acl-2013-13-32": "us-ca/guidance/cdss/acl-2013-13-32",
}
EXPECTED_SHA256 = {
    "WIC-18901.3.html": (
        "793afbd116aa7664fde4137f55d34ad659e80c10f37849d59bb4ea07b43fffdc"
    ),
    "WIC-18901.5.html": (
        "97cae778729e0dd5d3c15797934690467876a14057e7d856d1500326e72d004e"
    ),
    "14-56.pdf": "8677c1d3e5c2ec9ecef23206b24061999817a46fa469ccb68a000b8f2f570d5e",
    "14-56e.pdf": "67e33a2613009abaef3759ebc2a583417fb852120f009848e3b1a1e3c3c11cbd",
    "14-63.pdf": "4392ab0dedfcfb6f247bb7d3d913e90ff2a97a673ea01efac02ec9f3d6ee2841",
    "15-42.pdf": "6aab92e4e2a2c9e0f234eba2b1c0eeb68d4d9d5dbc7ba752465a2358d9f2db33",
    "14-100.pdf": "c981081163b361eea20aeeccec7934509dc5bf23d8d66c8035895586db60131e",
    "13-32.pdf": "1a0bbfc2d6d69fd378aff3f1285d03d20b8b6abf2ff64c749b9897fd1cc55506",
}
EXPECTED_SIZE_BYTES = {
    "WIC-18901.3.html": 163_929,
    "WIC-18901.5.html": 164_166,
    "14-56.pdf": 278_260,
    "14-56e.pdf": 189_729,
    "14-63.pdf": 120_344,
    "15-42.pdf": 249_307,
    "14-100.pdf": 209_290,
    "13-32.pdf": 204_909,
}
EXPECTED_PAGE_COUNTS = {
    "14-56.pdf": 7,
    "14-56e.pdf": 4,
    "14-63.pdf": 2,
    "15-42.pdf": 13,
    "14-100.pdf": 12,
    "13-32.pdf": 3,
}
EXPECTED_ROWS_BY_SOURCE_ID = {
    source_id: EXPECTED_PAGE_COUNTS[input_name] + 1
    for source_id, input_name in GUIDANCE_INPUT_BY_SOURCE_ID.items()
}
EXPECTED_ROWS_BY_INPUT = {
    "WIC-18901.3.html": 1,
    "WIC-18901.5.html": 1,
    **{
        input_name: EXPECTED_ROWS_BY_SOURCE_ID[source_id]
        for source_id, input_name in GUIDANCE_INPUT_BY_SOURCE_ID.items()
    },
}
EXPECTED_GUIDANCE_ROW_COUNT = sum(EXPECTED_ROWS_BY_SOURCE_ID.values())
EXPECTED_STATUTE_CITATION_PATHS = {
    "us-ca/statute/wic/18901.3",
    "us-ca/statute/wic/18901.5",
}
EXPECTED_STATUTE_ROW_COUNT = len(EXPECTED_STATUTE_CITATION_PATHS)

GUIDANCE_SOURCE_BASE = (
    Path("sources/us-ca/guidance") / GUIDANCE_VERSION / "official-documents"
)
STATUTE_SOURCE_BASE = (
    Path("sources/us-ca/statute")
    / STATUTE_VERSION
    / "california-leginfo-sections"
)
CANONICAL_SOURCE_BY_INPUT = {
    **{
        input_name: STATUTE_SOURCE_BASE / input_name
        for input_name in STATUTE_INPUTS
    },
    **{
        input_name: GUIDANCE_SOURCE_BASE / f"{safe_segment(source_id)}.pdf"
        for source_id, input_name in GUIDANCE_INPUT_BY_SOURCE_ID.items()
    },
}
GUIDANCE_INVENTORY = (
    Path("inventory/us-ca/guidance") / f"{GUIDANCE_VERSION}.json"
)
GUIDANCE_PROVISIONS = (
    Path("provisions/us-ca/guidance") / f"{GUIDANCE_VERSION}.jsonl"
)
GUIDANCE_COVERAGE = Path("coverage/us-ca/guidance") / f"{GUIDANCE_VERSION}.json"
STATUTE_INVENTORY = Path("inventory/us-ca/statute") / f"{STATUTE_VERSION}.json"
STATUTE_PROVISIONS = Path("provisions/us-ca/statute") / f"{STATUTE_VERSION}.jsonl"
STATUTE_COVERAGE = Path("coverage/us-ca/statute") / f"{STATUTE_VERSION}.json"
GENERATED_RELATIVE_PATHS = (
    *CANONICAL_SOURCE_BY_INPUT.values(),
    GUIDANCE_INVENTORY,
    GUIDANCE_PROVISIONS,
    GUIDANCE_COVERAGE,
    STATUTE_INVENTORY,
    STATUTE_PROVISIONS,
    STATUTE_COVERAGE,
)

EXPECTED_EXCERPTS = {
    "us-ca/statute/wic/18901.3": (
        "California opts out of the provisions of Section 115(a)(2)",
        "shall be eligible to receive CalFresh benefits as provided for under "
        "this section",
        "who is on probation or parole shall comply with the terms of the "
        "probation or parole",
        "or that the individual is a fleeing felon pursuant to federal law",
    ),
    "us-ca/statute/wic/18901.5": (
        "The department shall establish a program of categorical eligibility "
        "for CalFresh",
    ),
    "us-ca/guidance/cdss/acl-2014-14-56/page-1": (
        "all households (with certain exceptions as cited in this letter) with "
        "gross income at or below 200 percent of the Federal Poverty Level "
        "(FPL), must be conferred MCE status",
    ),
    "us-ca/guidance/cdss/acl-2014-14-56e/page-2": (
        "gross income at or less than 200 percent of the FPL",
    ),
    "us-ca/guidance/cdss/acl-2014-14-56/page-3": (
        "receipt of the PUB 275 exempts all resources in the determination of "
        "eligibility",
        "Receipt of the PUB 275, in and of itself, does not confer MCE status.",
    ),
    "us-ca/guidance/cdss/acl-2015-15-42/page-2": (
        "must be conferred MCE status if they are issued or have online access "
        "to the TANF-funded “Family Planning – PUB 275” brochure",
    ),
    "us-ca/guidance/cdss/acl-2015-15-42/page-3": (
        "Any household member who is disqualified for an Intentional Program "
        "Violation (IPV).",
        "The head of household who does not comply with work requirements.",
    ),
    "us-ca/guidance/cdss/acl-2015-15-42/page-4": (
        "entitled to the minimum CalFresh benefit even though the household’s "
        "net income exceeds the maximum allowable for the household size",
        "entitled to the allotment amount indicated in the tables of benefit "
        "issuance by household size even if the household’s net income exceeds "
        "the maximum amount allowable",
    ),
    "us-ca/guidance/cdss/acl-2014-14-100/page-2": (
        "Effective April 1, 2015, no person will be denied aid because they "
        "have a prior felony drug conviction",
    ),
    "us-ca/guidance/cdss/acl-2014-14-56/page-6": (
        "California has opted to deny these household who are otherwise CE or "
        "MCE and entitled to no benefits.",
    ),
    "us-ca/guidance/cdss/acl-2014-14-63/page-1": (
        "Except during an initial month, those CE households with one or two "
        "members would receive no less than the current minimum allotment "
        "regardless of their net income.",
        "households of three or more would only receive the benefit allotment "
        "that corresponds to the amount indicated on the tables of benefit "
        "issuance",
    ),
    "us-ca/guidance/cdss/acl-2014-14-63/page-2": (
        "California has opted to deny zero benefit cases.",
        "the county will deny the application.",
        "the county will discontinue the household’s participation",
        "the county will deny the recertification application",
    ),
    "us-ca/guidance/cdss/acl-2013-13-32/page-1": (
        "E/D households are not subject to a gross income test for actual "
        "program eligibility",
    ),
}

FEDERAL_AUTHORITY_PROVISIONS = Path(
    "provisions/us/regulation/2026-07-15-title-7-part-273.jsonl"
)
FEDERAL_AUTHORITY_VERSION = "2026-07-15-title-7-part-273"
FEDERAL_AUTHORITY_SOURCE_AS_OF = "2026-07-09"
FEDERAL_MCE_CITATION_PATH = "us/regulation/7/273/2"
FEDERAL_MEMBER_RULE_CITATION_PATH = "us/regulation/7/273/11"
FEDERAL_MCE_EXCLUSIONS_START = (
    "(vii) Under no circumstances shall any household be considered "
    "categorically eligible if:"
)
FEDERAL_MCE_EXCLUSIONS_END = "\n\n(viii)"
FEDERAL_MCE_EXCLUSIONS_SHA256 = (
    "6f0365e2f9ead0833adcef7a3d5a9bd2859db43517811864a0715ff37b2c42ab"
)
FEDERAL_MEMBER_EXCLUSIONS_START = (
    "(ix) No person shall be included as a member in any household which is "
    "otherwise categorically eligible if that person is:"
)
FEDERAL_MEMBER_EXCLUSIONS_END = "\n\n(x)"
FEDERAL_MEMBER_EXCLUSIONS_SHA256 = (
    "641740f072ea889906798769de510a6013d97d6b5c96293b34c9fe100cd44d25"
)
EXPECTED_MEMBER_EXCLUSIONS = {
    "ineligible_alien": "(A) An ineligible alien as defined in § 273.4;",
    "ineligible_student": (
        "(B) Ineligible under the student provisions in § 273.5;"
    ),
    "cash_out_state_ssi_recipient": (
        "(C) An SSI recipient in a cash-out State as defined in § 273.20; or"
    ),
    "nonexempt_facility_institutionalization": (
        "(D) Institutionalized in a nonexempt facility as defined in "
        "§ 273.1(e)."
    ),
    "individual_work_requirement_noncompliance": (
        "(E) Ineligible because of failure to comply with a work requirement "
        "of § 273.7."
    ),
}

MCE_EXCLUSION_GATES: dict[str, dict[str, Any]] = {
    "intentional_program_violation": {
        "federal_clause": "A",
        "federal_citation_path": FEDERAL_MCE_CITATION_PATH,
        "federal_excerpt": (
            "Any member of that household is disqualified for an intentional "
            "Program violation in accordance with § 273.16"
        ),
        "supporting_federal_citation_path": None,
        "supporting_federal_excerpt": None,
        "state_overlay_citation_path": None,
        "state_overlay_excerpts": (),
        "california_result": "federal_household_gate_controls",
        "guidance_context_citation_paths": (
            "us-ca/guidance/cdss/acl-2015-15-42/page-3",
        ),
    },
    "monthly_reporting_disqualification": {
        "federal_clause": "A",
        "federal_citation_path": FEDERAL_MCE_CITATION_PATH,
        "federal_excerpt": (
            "failure to comply with monthly reporting requirements in "
            "accordance with § 273.21"
        ),
        "supporting_federal_citation_path": None,
        "supporting_federal_excerpt": None,
        "state_overlay_citation_path": None,
        "state_overlay_excerpts": (),
        "california_result": "federal_household_gate_controls",
        "guidance_context_citation_paths": (),
    },
    "entire_household_workfare_disqualification": {
        "federal_clause": "B",
        "federal_citation_path": FEDERAL_MCE_CITATION_PATH,
        "federal_excerpt": (
            "The entire household is disqualified because one or more of its "
            "members failed to comply with workfare in accordance with § 273.22"
        ),
        "supporting_federal_citation_path": None,
        "supporting_federal_excerpt": None,
        "state_overlay_citation_path": None,
        "state_overlay_excerpts": (),
        "california_result": "federal_household_gate_controls",
        "guidance_context_citation_paths": (),
    },
    "head_of_household_work_disqualification": {
        "federal_clause": "C",
        "federal_citation_path": FEDERAL_MCE_CITATION_PATH,
        "federal_excerpt": (
            "The head of the household is disqualified for failure to comply "
            "with the work requirements in accordance with § 273.7"
        ),
        "supporting_federal_citation_path": None,
        "supporting_federal_excerpt": None,
        "state_overlay_citation_path": None,
        "state_overlay_excerpts": (),
        "california_result": "federal_household_gate_controls",
        "guidance_context_citation_paths": (
            "us-ca/guidance/cdss/acl-2015-15-42/page-3",
        ),
    },
    "drug_felony_member_ineligibility": {
        "federal_clause": "D",
        "federal_citation_path": FEDERAL_MCE_CITATION_PATH,
        "federal_excerpt": (
            "Any member of that household is ineligible under § 273.11(m) by "
            "virtue of a conviction for a drug-related felony"
        ),
        "supporting_federal_citation_path": FEDERAL_MEMBER_RULE_CITATION_PATH,
        "supporting_federal_excerpt": (
            "unless the State legislature of the State where the individual "
            "is domiciled has enacted legislation exempting individuals "
            "domiciled in the State from the above exclusion"
        ),
        "state_overlay_citation_path": "us-ca/statute/wic/18901.3",
        "state_overlay_excerpts": (
            "California opts out of the provisions of Section 115(a)(2)",
            "shall be eligible to receive CalFresh benefits as provided for "
            "under this section",
        ),
        "california_result": (
            "conviction_alone_does_not_trigger_the_gate_after_state_opt_out"
        ),
        "guidance_context_citation_paths": (
            "us-ca/guidance/cdss/acl-2014-14-100/page-2",
        ),
    },
    "fleeing_felon_or_probation_parole_violator": {
        "federal_clause": "D",
        "federal_citation_path": FEDERAL_MCE_CITATION_PATH,
        "federal_excerpt": (
            "under § 273.11(n) for being a fleeing felon or a probation or "
            "parole violator"
        ),
        "supporting_federal_citation_path": FEDERAL_MEMBER_RULE_CITATION_PATH,
        "supporting_federal_excerpt": (
            "who are violating a condition of probation or parole under a "
            "Federal or State law shall not be considered eligible household "
            "members"
        ),
        "state_overlay_citation_path": "us-ca/statute/wic/18901.3",
        "state_overlay_excerpts": (
            "who is on probation or parole shall comply with the terms of the "
            "probation or parole",
            "or that the individual is a fleeing felon pursuant to federal law",
        ),
        "california_result": (
            "federal_gate_controls_universally_and_state_text_confirms_it_for_"
            "the_drug_felony_cohort"
        ),
        "guidance_context_citation_paths": (
            "us-ca/guidance/cdss/acl-2014-14-100/page-4",
            "us-ca/guidance/cdss/acl-2014-14-100/page-5",
        ),
    },
    "serious_crime_sentence_noncompliance": {
        "federal_clause": "D",
        "federal_citation_path": FEDERAL_MCE_CITATION_PATH,
        "federal_excerpt": (
            "under § 273.11(s) for having a conviction of certain crimes and "
            "not being in compliance with the sentence"
        ),
        "supporting_federal_citation_path": FEDERAL_MEMBER_RULE_CITATION_PATH,
        "supporting_federal_excerpt": (
            "The individual is not in compliance with the terms of the "
            "sentence of the individual or the restrictions under § 273.11(n)"
        ),
        "state_overlay_citation_path": None,
        "state_overlay_excerpts": (),
        "california_result": "federal_household_gate_controls",
        "guidance_context_citation_paths": (),
    },
}
EXPECTED_MCE_GATE_IDS = frozenset(
    {
        "intentional_program_violation",
        "monthly_reporting_disqualification",
        "entire_household_workfare_disqualification",
        "head_of_household_work_disqualification",
        "drug_felony_member_ineligibility",
        "fleeing_felon_or_probation_parole_violator",
        "serious_crime_sentence_noncompliance",
    }
)
EXPECTED_STATE_OVERLAY_BY_GATE = {
    "drug_felony_member_ineligibility": "us-ca/statute/wic/18901.3",
    "fleeing_felon_or_probation_parole_violator": (
        "us-ca/statute/wic/18901.3"
    ),
}


def _resolve_input_path(source_dir: Path, input_name: str) -> Path:
    candidates = (
        source_dir / input_name,
        source_dir / CANONICAL_SOURCE_BY_INPUT[input_name],
    )
    for candidate in candidates:
        if candidate.is_symlink():
            raise ValueError(f"official source must not be a symlink: {candidate}")
        if candidate.is_file():
            return candidate
    choices = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"official source {input_name} not found; checked {choices}")


def _read_verified_sources(source_dir: Path) -> dict[str, bytes]:
    source_bytes: dict[str, bytes] = {}
    for input_name, expected_hash in EXPECTED_SHA256.items():
        source_path = _resolve_input_path(source_dir, input_name)
        content = source_path.read_bytes()
        actual_hash = sha256_bytes(content)
        if actual_hash != expected_hash:
            raise ValueError(
                f"official source hash mismatch for {input_name}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        expected_size = EXPECTED_SIZE_BYTES[input_name]
        if len(content) != expected_size:
            raise ValueError(
                f"official source size mismatch for {input_name}: "
                f"expected {expected_size}, got {len(content)}"
            )
        source_bytes[input_name] = content

    for input_name, expected_pages in EXPECTED_PAGE_COUNTS.items():
        with fitz.open(stream=source_bytes[input_name], filetype="pdf") as pdf:
            if pdf.page_count != expected_pages:
                raise ValueError(
                    f"official PDF page-count mismatch for {input_name}: "
                    f"expected {expected_pages}, got {pdf.page_count}"
                )
            empty_pages = [
                page.number + 1 for page in pdf if not page.get_text().strip()
            ]
        if empty_pages:
            raise ValueError(
                f"official PDF contains empty extracted pages for {input_name}: "
                f"{empty_pages}"
            )
    return source_bytes


def _guidance_manifest() -> OfficialDocumentManifest:
    manifest = OfficialDocumentManifest.load(MANIFEST_PATH)
    manifest.require_unique_sources()
    expected_ids = set(GUIDANCE_INPUT_BY_SOURCE_ID)
    actual_ids = {source.source_id for source in manifest.documents}
    if actual_ids != expected_ids:
        raise ValueError(
            f"guidance manifest source IDs changed: expected {expected_ids}, got {actual_ids}"
        )
    for source in manifest.documents:
        if source.document_class != DocumentClass.GUIDANCE.value:
            raise ValueError(f"unexpected document class for {source.source_id}")
        if source.source_format != "pdf":
            raise ValueError(f"unexpected source format for {source.source_id}")
        if source.local_path is not None:
            raise ValueError(f"manifest must not use local_path for {source.source_id}")
        if source.citation_path != ROOT_CITATION_BY_SOURCE_ID[source.source_id]:
            raise ValueError(f"unexpected citation path for {source.source_id}")
    return manifest


def _build_guidance_scope(
    staging_base: Path,
    source_bytes: dict[str, bytes],
) -> dict[str, Any]:
    store = CorpusArtifactStore(staging_base)
    inventory: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    block_count = 0
    manifest = _guidance_manifest()

    for source in manifest.documents:
        input_name = GUIDANCE_INPUT_BY_SOURCE_ID[source.source_id]
        content = source_bytes[input_name]
        relative_source = (
            f"official-documents/{safe_segment(source.source_id)}.pdf"
        )
        artifact_path = store.source_path(
            source.jurisdiction,
            source.document_class,
            GUIDANCE_VERSION,
            relative_source,
        )
        source_sha = store.write_bytes(artifact_path, content)
        source_key = (
            f"sources/{source.jurisdiction}/{source.document_class}/"
            f"{GUIDANCE_VERSION}/{relative_source}"
        )
        blocks = documents._extract_blocks(
            content,
            "pdf",
            source_url=source.source_url,
            title=source.title,
            extraction=source.extraction,
        )
        expected_pages = EXPECTED_PAGE_COUNTS[input_name]
        if len(blocks) != expected_pages:
            raise ValueError(
                f"unexpected PDF block count for {input_name}: "
                f"expected {expected_pages}, got {len(blocks)}"
            )
        block_count += len(blocks)
        inventory.extend(
            documents._inventory_items(
                source,
                blocks=blocks,
                source_key=source_key,
                source_format="pdf",
                source_sha=source_sha,
                content_type="application/pdf",
                final_url=source.source_url,
            )
        )
        source_as_of = source.source_as_of or GUIDANCE_VERSION
        expression_date = source.expression_date or source_as_of
        records.extend(
            documents._provision_records(
                source,
                blocks=blocks,
                version=GUIDANCE_VERSION,
                source_key=source_key,
                source_format="pdf",
                source_as_of=source_as_of,
                expression_date=expression_date,
                content_type="application/pdf",
                final_url=source.source_url,
            )
        )

    store.write_inventory(staging_base / GUIDANCE_INVENTORY, inventory)
    store.write_provisions(staging_base / GUIDANCE_PROVISIONS, records)
    coverage = compare_provision_coverage(
        tuple(inventory),
        tuple(records),
        jurisdiction="us-ca",
        document_class=DocumentClass.GUIDANCE.value,
        version=GUIDANCE_VERSION,
    )
    if not coverage.complete:
        raise ValueError(f"incomplete guidance coverage: {coverage.to_mapping()}")
    store.write_json(staging_base / GUIDANCE_COVERAGE, coverage.to_mapping())
    return {
        "block_count": block_count,
        "document_count": len(manifest.documents),
        "row_count": len(records),
    }


def _build_statute_scope(
    staging_base: Path,
    source_bytes: dict[str, bytes],
) -> dict[str, Any]:
    with TemporaryDirectory(prefix="ca-bbce-leginfo-cache-") as cache_name:
        cache_root = Path(cache_name)
        cache_store = CorpusArtifactStore(cache_root)
        for input_name in STATUTE_INPUTS:
            cache_path = (
                cache_root / "california-leginfo-sections" / input_name
            )
            cache_store.write_bytes(cache_path, source_bytes[input_name])
        store = CorpusArtifactStore(staging_base)
        report = extract_california_code_sections(
            store,
            version=VERSION,
            sections=STATUTE_SECTIONS,
            source_as_of=SOURCE_AS_OF,
            expression_date=SOURCE_AS_OF,
            download_dir=cache_root,
            request_delay_seconds=0,
        )
        statute_path = staging_base / STATUTE_PROVISIONS
        statute_records = [
            replace(record, parent_citation_path=None, parent_id=None)
            for record in load_provisions(statute_path)
        ]
        store.write_provisions(statute_path, statute_records)
    if report.errors:
        raise ValueError(f"California section extractor errors: {report.errors}")
    if (
        not report.coverage.complete
        or report.provisions_written != EXPECTED_STATUTE_ROW_COUNT
    ):
        raise ValueError(
            f"unexpected California statute report: {report.coverage.to_mapping()}"
        )
    return {
        "row_count": report.provisions_written,
        "section_count": report.section_count,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _bounded_clause(body: str, *, start_marker: str, end_marker: str) -> str:
    start = body.index(start_marker)
    end = body.index(end_marker, start)
    return body[start:end]


def _verify_current_mce_authority(
    guidance_by_path: dict[str, dict[str, Any]],
    statute_by_path: dict[str, dict[str, Any]],
) -> None:
    federal_rows = _load_jsonl(RETAINED_BASE / FEDERAL_AUTHORITY_PROVISIONS)
    federal_by_path = {row["citation_path"]: row for row in federal_rows}
    if len(federal_rows) != len(federal_by_path):
        raise ValueError("current retained 7 CFR part 273 scope has duplicate paths")

    mce_row = federal_by_path.get(FEDERAL_MCE_CITATION_PATH)
    member_rule_row = federal_by_path.get(FEDERAL_MEMBER_RULE_CITATION_PATH)
    if mce_row is None or member_rule_row is None:
        raise ValueError("required current 7 CFR 273.2/273.11 rows are not retained")
    for row in (mce_row, member_rule_row):
        if row.get("version") != FEDERAL_AUTHORITY_VERSION:
            raise ValueError(
                f"unexpected retained federal version for {row['citation_path']}"
            )
        if row.get("source_as_of") != FEDERAL_AUTHORITY_SOURCE_AS_OF:
            raise ValueError(
                f"unexpected federal source_as_of for {row['citation_path']}"
            )

    mce_body = str(mce_row.get("body") or "")
    member_rule_body = str(member_rule_row.get("body") or "")
    exclusion_clause = _bounded_clause(
        mce_body,
        start_marker=FEDERAL_MCE_EXCLUSIONS_START,
        end_marker=FEDERAL_MCE_EXCLUSIONS_END,
    )
    if (
        sha256_bytes(exclusion_clause.encode("utf-8"))
        != FEDERAL_MCE_EXCLUSIONS_SHA256
    ):
        raise ValueError("retained current 7 CFR 273.2(j)(2)(vii) text changed")

    member_clause = _bounded_clause(
        mce_body,
        start_marker=FEDERAL_MEMBER_EXCLUSIONS_START,
        end_marker=FEDERAL_MEMBER_EXCLUSIONS_END,
    )
    if (
        sha256_bytes(member_clause.encode("utf-8"))
        != FEDERAL_MEMBER_EXCLUSIONS_SHA256
    ):
        raise ValueError("retained current 7 CFR 273.2(j)(2)(ix) text changed")
    for exclusion_id, excerpt in EXPECTED_MEMBER_EXCLUSIONS.items():
        if excerpt not in member_clause:
            raise ValueError(
                f"missing 7 CFR 273.2(j)(2)(ix) member exclusion {exclusion_id}"
            )

    if set(MCE_EXCLUSION_GATES) != EXPECTED_MCE_GATE_IDS:
        raise ValueError("MCE exclusion gate map is not exhaustive")
    actual_state_overlays = {
        gate_id: gate["state_overlay_citation_path"]
        for gate_id, gate in MCE_EXCLUSION_GATES.items()
        if gate["state_overlay_citation_path"] is not None
    }
    if actual_state_overlays != EXPECTED_STATE_OVERLAY_BY_GATE:
        raise ValueError("MCE state-overlay map changed")

    for gate_id, gate in MCE_EXCLUSION_GATES.items():
        if gate["federal_citation_path"] != FEDERAL_MCE_CITATION_PATH:
            raise ValueError(
                f"{gate_id} must map to the retained current 7 CFR 273.2 row"
            )
        federal_excerpt = str(gate["federal_excerpt"])
        if federal_excerpt not in exclusion_clause:
            raise ValueError(f"missing controlling federal text for {gate_id}")

        supporting_path = gate["supporting_federal_citation_path"]
        supporting_excerpt = gate["supporting_federal_excerpt"]
        if supporting_path is not None:
            if supporting_path != FEDERAL_MEMBER_RULE_CITATION_PATH:
                raise ValueError(f"unexpected federal supporting row for {gate_id}")
            if str(supporting_excerpt) not in member_rule_body:
                raise ValueError(f"missing federal supporting text for {gate_id}")
        elif supporting_excerpt is not None:
            raise ValueError(f"unmapped federal supporting text for {gate_id}")

        state_path = gate["state_overlay_citation_path"]
        state_excerpts = tuple(gate["state_overlay_excerpts"])
        if state_path is None:
            if state_excerpts:
                raise ValueError(f"unmapped state overlay text for {gate_id}")
        else:
            state_row = statute_by_path.get(str(state_path))
            if state_row is None:
                raise ValueError(f"missing state overlay row for {gate_id}")
            state_body = str(state_row.get("body") or "")
            for state_excerpt in state_excerpts:
                if str(state_excerpt) not in state_body:
                    raise ValueError(f"missing state overlay text for {gate_id}")

        for context_path in gate["guidance_context_citation_paths"]:
            if str(context_path) not in guidance_by_path:
                raise ValueError(f"missing noncontrolling guidance for {gate_id}")


def _verify_coverage(
    path: Path,
    *,
    document_class: str,
    version: str,
    expected_count: int,
) -> None:
    coverage = json.loads(path.read_text(encoding="utf-8"))
    expected_fields = {
        "complete": True,
        "document_class": document_class,
        "jurisdiction": "us-ca",
        "matched_count": expected_count,
        "provision_count": expected_count,
        "source_count": expected_count,
        "version": version,
    }
    for key, expected in expected_fields.items():
        if coverage.get(key) != expected:
            raise ValueError(
                f"unexpected coverage field {key} in {path}: "
                f"expected {expected!r}, got {coverage.get(key)!r}"
            )
    for key in (
        "duplicate_provision_citations",
        "duplicate_source_citations",
        "extra_provisions",
        "missing_from_provisions",
    ):
        if coverage.get(key) != []:
            raise ValueError(f"non-empty coverage issue list {key} in {path}")


def _verify_generated_scope(
    staging_base: Path,
    source_bytes: dict[str, bytes],
) -> None:
    for input_name, relative_path in CANONICAL_SOURCE_BY_INPUT.items():
        generated = (staging_base / relative_path).read_bytes()
        if generated != source_bytes[input_name]:
            raise ValueError(f"generated source is not byte-equal for {input_name}")
        actual_hash = sha256_bytes(generated)
        if actual_hash != EXPECTED_SHA256[input_name]:
            raise ValueError(f"generated source hash mismatch for {input_name}")

    guidance_rows = _load_jsonl(staging_base / GUIDANCE_PROVISIONS)
    statute_rows = _load_jsonl(staging_base / STATUTE_PROVISIONS)
    guidance_by_path = {row["citation_path"]: row for row in guidance_rows}
    statute_by_path = {row["citation_path"]: row for row in statute_rows}
    if (
        len(guidance_rows) != len(guidance_by_path)
        or len(guidance_rows) != EXPECTED_GUIDANCE_ROW_COUNT
    ):
        raise ValueError(
            f"guidance scope must contain {EXPECTED_GUIDANCE_ROW_COUNT} unique rows"
        )
    if set(statute_by_path) != EXPECTED_STATUTE_CITATION_PATHS:
        raise ValueError("statute scope must contain only WIC 18901.3 and 18901.5")
    for statute_row in statute_rows:
        if statute_row.get("parent_citation_path") or statute_row.get("parent_id"):
            raise ValueError("section statute slice has a dangling parent link")
        if statute_row.get("metadata", {}).get("parent_citation_path") != (
            "us-ca/statute/wic"
        ):
            raise ValueError("California source hierarchy metadata changed")

    actual_rows_by_source = Counter(row["source_id"] for row in guidance_rows)
    if actual_rows_by_source != Counter(EXPECTED_ROWS_BY_SOURCE_ID):
        raise ValueError(
            "unexpected per-source guidance rows: "
            f"expected {EXPECTED_ROWS_BY_SOURCE_ID}, got {dict(actual_rows_by_source)}"
        )

    expected_guidance_paths: set[str] = set()
    for source_id, root_citation in ROOT_CITATION_BY_SOURCE_ID.items():
        expected_guidance_paths.add(root_citation)
        input_name = GUIDANCE_INPUT_BY_SOURCE_ID[source_id]
        expected_guidance_paths.update(
            f"{root_citation}/page-{page_number}"
            for page_number in range(1, EXPECTED_PAGE_COUNTS[input_name] + 1)
        )
    if set(guidance_by_path) != expected_guidance_paths:
        raise ValueError("guidance citation paths changed")

    manifest_by_id = {
        source.source_id: source for source in _guidance_manifest().documents
    }
    for row in guidance_rows:
        source = manifest_by_id[row["source_id"]]
        if row["source_url"] != source.source_url:
            raise ValueError(f"official source URL changed for {row['citation_path']}")
        download_url = row.get("metadata", {}).get("download_url")
        if download_url != source.source_url or str(download_url).startswith("file:"):
            raise ValueError(
                f"non-official download URL for {row['citation_path']}: {download_url}"
            )

    guidance_inventory = json.loads(
        (staging_base / GUIDANCE_INVENTORY).read_text(encoding="utf-8")
    )["items"]
    statute_inventory = json.loads(
        (staging_base / STATUTE_INVENTORY).read_text(encoding="utf-8")
    )["items"]
    if {item["citation_path"] for item in guidance_inventory} != set(
        guidance_by_path
    ):
        raise ValueError("guidance inventory/provision paths differ")
    if {item["citation_path"] for item in statute_inventory} != set(
        statute_by_path
    ):
        raise ValueError("statute inventory/provision paths differ")

    all_rows_by_path = guidance_by_path | statute_by_path
    for citation_path, excerpts in EXPECTED_EXCERPTS.items():
        body = str(all_rows_by_path[citation_path].get("body") or "")
        for excerpt in excerpts:
            if excerpt not in body:
                raise ValueError(
                    f"required authority excerpt missing from {citation_path}: {excerpt}"
                )

    _verify_current_mce_authority(guidance_by_path, statute_by_path)

    _verify_coverage(
        staging_base / GUIDANCE_COVERAGE,
        document_class=DocumentClass.GUIDANCE.value,
        version=GUIDANCE_VERSION,
        expected_count=EXPECTED_GUIDANCE_ROW_COUNT,
    )
    _verify_coverage(
        staging_base / STATUTE_COVERAGE,
        document_class=DocumentClass.STATUTE.value,
        version=STATUTE_VERSION,
        expected_count=EXPECTED_STATUTE_ROW_COUNT,
    )


def reproduce(base: Path, source_dir: Path | None = None) -> dict[str, Any]:
    target_base = base.resolve()
    input_root = (source_dir or RETAINED_BASE).resolve()
    source_bytes = _read_verified_sources(input_root)

    with TemporaryDirectory(prefix="repro-us-ca-calfresh-bbce-") as staging_name:
        staging_base = Path(staging_name) / "corpus"
        guidance = _build_guidance_scope(staging_base, source_bytes)
        statute = _build_statute_scope(staging_base, source_bytes)
        _verify_generated_scope(staging_base, source_bytes)

        target_store = CorpusArtifactStore(target_base)
        generated_hashes: dict[str, str] = {}
        for relative_path in GENERATED_RELATIVE_PATHS:
            content = (staging_base / relative_path).read_bytes()
            target_store.write_bytes(target_base / relative_path, content)
            generated_hashes[relative_path.as_posix()] = sha256_bytes(content)

    return {
        "base": str(target_base),
        "command": REPRO_COMMAND,
        "files": generated_hashes,
        "guidance": guidance,
        "mce_exclusion_gate_count": len(MCE_EXCLUSION_GATES),
        "per_source_rows": EXPECTED_ROWS_BY_INPUT,
        "source_sha256": EXPECTED_SHA256,
        "statute": statute,
        "versions": {
            "guidance": GUIDANCE_VERSION,
            "statute": STATUTE_VERSION,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        type=Path,
        required=True,
        help="Destination corpus base.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help=(
            "Optional local input root. Accepts the eight flat original filenames "
            "or the retained canonical paths; defaults to repository data/corpus."
        ),
    )
    args = parser.parse_args()
    print(json.dumps(reproduce(args.base, args.source_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
