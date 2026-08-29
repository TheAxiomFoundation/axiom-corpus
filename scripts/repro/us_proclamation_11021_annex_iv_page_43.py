#!/usr/bin/env python3
"""Reproduce the focused Annex IV page-43 witness for Proclamation 11021.

The Federal Register rendition of the proclamation's annexes is graphics-only.
The White House publishes the same 58 annex pages as an official text-layer
PDF.  Page 43 contains the complete operative text needed to ground the April
6 effective date, the U.S. note 16(c) 15-percent metal-weight proviso, and the
page-43 portion of subdivision (c)(ii), including HTS 7612.10.00.

This additive scope retains the full byte-pinned White House PDF but emits only
that one complete page as a normalized provision.  It uses the corpus's
standard PyMuPDF page extraction without OCR, sorting, substitutions, or hand
edits.
"""

from __future__ import annotations

import argparse
import json
import shlex
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from axiom_corpus.corpus import documents
from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import OfficialDocumentSource, _DocumentBlock
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord

REPO_ROOT = Path(__file__).resolve().parents[2]
RETAINED_BASE = REPO_ROOT / "data/corpus"

JURISDICTION = "us"
DOCUMENT_CLASS = DocumentClass.RULEMAKING.value
VERSION = "2026-08-29-tariff-232-proclamation-11021-annex-iv-page-43"
FR_ROOT_CITATION = "us/rulemaking/federal-register/2026-04-09/2026-06960"
ANNEX_ROOT_CITATION = f"{FR_ROOT_CITATION}/annex-iv"
WITNESS_CITATION = f"{ANNEX_ROOT_CITATION}/page-43"
SOURCE_AS_OF = "2026-08-29"
EXPRESSION_DATE = "2026-04-09"
EFFECTIVE_DATE = "2026-04-06"
SOURCE_FILENAME = "Metals-ANNEXES-I-A-I-B-II-III-IV.pdf"
SOURCE_SHA256 = "9657a6c4589e1013ecebbc9eaf04db0ab865efde25ddfe81c463b29e5f0180f7"
SOURCE_SIZE_BYTES = 633_053
SOURCE_PAGE_COUNT = 58
WITNESS_PAGE_NUMBER = 43
WITNESS_BODY_SHA256 = "8bb8ff988becea34d3e4331b35350f023e68750419a62c724b36311870218d57"
OFFICIAL_URL = (
    "https://www.whitehouse.gov/wp-content/uploads/2026/04/Metals-ANNEXES-I-A-I-B-II-III-IV.pdf"
)
LANDING_PAGE_URL = (
    "https://www.whitehouse.gov/presidential-actions/2026/04/"
    "strengthening-actions-taken-to-adjust-imports-of-aluminum-steel-and-"
    "copper-into-the-united-states/"
)
WAYBACK_TIMESTAMP = "20260404165018"
WAYBACK_URL = f"https://web.archive.org/web/{WAYBACK_TIMESTAMP}id_/{OFFICIAL_URL}"
CONTENT_TYPE = "application/pdf"
TITLE = "Annex IV to Proclamation 11021—Official White House Text Rendition"
REPRO_ARGV = (
    "uv",
    "run",
    "--extra",
    "dev",
    "python",
    "scripts/repro/us_proclamation_11021_annex_iv_page_43.py",
    "--base",
    "data/corpus",
)
REPRO_COMMAND = shlex.join(REPRO_ARGV)
if shlex.join(shlex.split(REPRO_COMMAND)) != REPRO_COMMAND:
    raise AssertionError("Proclamation 11021 Annex IV repro command is not canonical")

SOURCE_RELATIVE_PATH = (
    Path("sources")
    / JURISDICTION
    / DOCUMENT_CLASS
    / VERSION
    / "official-documents"
    / SOURCE_FILENAME
)
INVENTORY_RELATIVE_PATH = Path("inventory") / JURISDICTION / DOCUMENT_CLASS / f"{VERSION}.json"
PROVISIONS_RELATIVE_PATH = Path("provisions") / JURISDICTION / DOCUMENT_CLASS / f"{VERSION}.jsonl"
COVERAGE_RELATIVE_PATH = Path("coverage") / JURISDICTION / DOCUMENT_CLASS / f"{VERSION}.json"
GENERATED_RELATIVE_PATHS = (
    SOURCE_RELATIVE_PATH,
    INVENTORY_RELATIVE_PATH,
    PROVISIONS_RELATIVE_PATH,
    COVERAGE_RELATIVE_PATH,
)


def _resolve_input_path(source_dir: Path) -> Path:
    candidates = (
        source_dir / SOURCE_FILENAME,
        source_dir / SOURCE_RELATIVE_PATH,
    )
    for candidate in candidates:
        if candidate.is_symlink():
            raise ValueError(f"official source must not be a symlink: {candidate}")
        if candidate.is_file():
            return candidate
    choices = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"official source not found; checked {choices}")


def _read_verified_source(source_dir: Path) -> bytes:
    content = _resolve_input_path(source_dir).read_bytes()
    actual_sha256 = sha256_bytes(content)
    if actual_sha256 != SOURCE_SHA256:
        raise ValueError(
            "Proclamation 11021 annex source hash mismatch: "
            f"expected {SOURCE_SHA256}, got {actual_sha256}"
        )
    if len(content) != SOURCE_SIZE_BYTES:
        raise ValueError(
            "Proclamation 11021 annex source size mismatch: "
            f"expected {SOURCE_SIZE_BYTES}, got {len(content)}"
        )
    return content


def _source_metadata() -> dict[str, Any]:
    return {
        "primary_source": True,
        "source_authority": "The White House",
        "document_subtype": "annex_text_rendition_page_witness",
        "proclamation_number": "11021",
        "proclamation_date": "2026-04-02",
        "publication_date": EXPRESSION_DATE,
        "effective_date": EFFECTIVE_DATE,
        "federal_register_citation": "91 FR 18201–18266",
        "federal_register_document_number": "2026-06960",
        "federal_register_annex_pages": "18209–18266",
        "federal_register_equivalent_page": 18251,
        "federal_register_annex_graphics_only": True,
        "whitehouse_source_url": OFFICIAL_URL,
        "whitehouse_landing_page_url": LANDING_PAGE_URL,
        "source_pdf_sha256": SOURCE_SHA256,
        "source_pdf_size_bytes": SOURCE_SIZE_BYTES,
        "source_pdf_page_count": SOURCE_PAGE_COUNT,
        "annex_iv_pdf_pages": "43–58",
        "selected_pdf_pages": [WITNESS_PAGE_NUMBER],
        "selection_scope": (
            "single complete PDF page containing the Annex IV effective date, "
            "U.S. note 16(c) 15-percent proviso, and the page-43 portion of "
            "subdivision (c)(ii), including HTS 7612.10.00"
        ),
        "wayback_timestamp": WAYBACK_TIMESTAMP,
        "wayback_url": WAYBACK_URL,
        "wayback_byte_identical_to_official": True,
        "source_cross_verified_on": SOURCE_AS_OF,
        "logical_parent_citation_path": ANNEX_ROOT_CITATION,
        "existing_body_version": (
            "2026-08-01-tariff-232-annex-restructure-types-presdocu-term-strengthening-actions"
        ),
        "rendition_role": ("focused page-level text for the graphics-only Federal Register annex"),
        "operator_visual_verification": (
            "White House PDF page 43 visually verified against its rendered "
            "page; verified 2026-08-29"
        ),
        "extraction_method": (
            "PyMuPDF page.get_text('text', sort=False) through the standard "
            "corpus PDF page extractor; no OCR or text replacements"
        ),
        "repro_command": REPRO_COMMAND,
    }


def _source() -> OfficialDocumentSource:
    return OfficialDocumentSource(
        source_id="whitehouse-proclamation-11021-annex-iv",
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS,
        title=TITLE,
        source_url=OFFICIAL_URL,
        citation_path=ANNEX_ROOT_CITATION,
        download_url=WAYBACK_URL,
        source_format="pdf",
        source_as_of=SOURCE_AS_OF,
        expression_date=EXPRESSION_DATE,
        extraction={"page_citation_prefix": "page"},
        metadata=_source_metadata(),
    )


def _verify_critical_text(body: str) -> None:
    required = (
        (
            "Effective with respect to goods entered for consumption, or "
            "withdrawn from warehouse for consumption, on or after 12:01 a.m. "
            "eastern time on April 6, 2026"
        ),
        (
            "For articles classified in the listed provisions that are not in "
            "chapters 72, 73, 74 or 76 of the HTSUS"
        ),
        (
            "only apply where the weight of the applicable metal is at least "
            "15 percent of the weight of the imported article"
        ),
        (
            "If an article is classified in a provision that is present on "
            "multiple lists, use the aggregate weight of the listed metals."
        ),
        "(ii) Derivative aluminum articles:",
        "7308.20.0035 7610.10.00 7610.90.00 7612.10.00",
    )
    for text in required:
        if text not in body:
            raise ValueError(f"critical Annex IV page-43 text is missing: {text!r}")
    if "7612.10.10" in body:
        raise ValueError("incorrect HTS 7612.10.10 appeared in Annex IV page 43")


def _extract_witness(content: bytes) -> tuple[_DocumentBlock, ...]:
    blocks = documents._extract_blocks(
        content,
        "pdf",
        source_url=OFFICIAL_URL,
        title=TITLE,
        extraction={"page_citation_prefix": "page"},
    )
    if len(blocks) != SOURCE_PAGE_COUNT:
        raise ValueError(f"expected {SOURCE_PAGE_COUNT} annex pages, got {len(blocks)}")
    witness = blocks[WITNESS_PAGE_NUMBER - 1]
    if witness.kind != "page" or witness.ordinal != WITNESS_PAGE_NUMBER:
        raise ValueError("unexpected Annex IV witness block")
    if witness.metadata != {
        "page_number": WITNESS_PAGE_NUMBER,
        "citation_suffix": f"page-{WITNESS_PAGE_NUMBER}",
    }:
        raise ValueError("unexpected Annex IV witness page metadata")
    body_sha256 = sha256_bytes(witness.body.encode("utf-8"))
    if body_sha256 != WITNESS_BODY_SHA256:
        raise ValueError(
            "Annex IV page-43 extracted-text hash mismatch: "
            f"expected {WITNESS_BODY_SHA256}, got {body_sha256}"
        )
    _verify_critical_text(witness.body)
    return (witness,)


def _page_records(records: tuple[ProvisionRecord, ...]) -> tuple[ProvisionRecord, ...]:
    return tuple(
        replace(
            record,
            parent_citation_path=None,
            parent_id=None,
            level=4,
        )
        for record in records[1:]
    )


def _build_scope(staging_base: Path, content: bytes) -> dict[str, Any]:
    source = _source()
    blocks = _extract_witness(content)
    store = CorpusArtifactStore(staging_base)
    source_sha = store.write_bytes(staging_base / SOURCE_RELATIVE_PATH, content)
    source_key = SOURCE_RELATIVE_PATH.as_posix()

    inventory = documents._inventory_items(
        source,
        blocks=blocks,
        source_key=source_key,
        source_format="pdf",
        source_sha=source_sha,
        content_type=CONTENT_TYPE,
        final_url=WAYBACK_URL,
    )[1:]
    all_records = documents._provision_records(
        source,
        blocks=blocks,
        version=VERSION,
        source_key=source_key,
        source_format="pdf",
        source_as_of=SOURCE_AS_OF,
        expression_date=EXPRESSION_DATE,
        content_type=CONTENT_TYPE,
        final_url=WAYBACK_URL,
    )
    records = _page_records(all_records)

    store.write_inventory(staging_base / INVENTORY_RELATIVE_PATH, inventory)
    store.write_provisions(staging_base / PROVISIONS_RELATIVE_PATH, records)
    coverage = compare_provision_coverage(
        tuple(inventory),
        records,
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS,
        version=VERSION,
    )
    if not coverage.complete:
        raise ValueError(f"incomplete Annex IV witness coverage: {coverage.to_mapping()}")
    store.write_json(staging_base / COVERAGE_RELATIVE_PATH, coverage.to_mapping())
    return {"page_count": len(blocks), "row_count": len(records)}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _verify_generated_scope(staging_base: Path, content: bytes) -> None:
    if (staging_base / SOURCE_RELATIVE_PATH).read_bytes() != content:
        raise ValueError("retained Proclamation 11021 annex PDF is not byte-identical")

    records = _load_jsonl(staging_base / PROVISIONS_RELATIVE_PATH)
    if len(records) != 1 or records[0].get("citation_path") != WITNESS_CITATION:
        raise ValueError("unexpected Annex IV witness citation path")
    record = records[0]
    witness = _extract_witness(content)[0]
    if record.get("body") != witness.body:
        raise ValueError("witness body differs from standard PDF extraction")
    if record.get("kind") != "page" or record.get("level") != 4:
        raise ValueError("unexpected Annex IV witness kind or level")
    if "parent_citation_path" in record or "parent_id" in record:
        raise ValueError("Annex IV witness has a cross-version structural parent")
    if record.get("version") != VERSION or record.get("source_url") != OFFICIAL_URL:
        raise ValueError("Annex IV witness provenance drifted")
    metadata = record.get("metadata", {})
    for key, expected in _source_metadata().items():
        if metadata.get(key) != expected:
            raise ValueError(
                f"metadata {key} drifted: expected {expected!r}, got {metadata.get(key)!r}"
            )
    if metadata.get("download_url") != WAYBACK_URL:
        raise ValueError("Annex IV witness download URL drifted")

    inventory = json.loads((staging_base / INVENTORY_RELATIVE_PATH).read_text(encoding="utf-8"))[
        "items"
    ]
    if len(inventory) != 1 or inventory[0].get("citation_path") != WITNESS_CITATION:
        raise ValueError("inventory and witness citation paths differ")
    if inventory[0].get("sha256") != SOURCE_SHA256:
        raise ValueError("inventory source hash drifted")

    coverage = json.loads((staging_base / COVERAGE_RELATIVE_PATH).read_text(encoding="utf-8"))
    expected_coverage = {
        "complete": True,
        "document_class": DOCUMENT_CLASS,
        "jurisdiction": JURISDICTION,
        "matched_count": 1,
        "provision_count": 1,
        "source_count": 1,
        "version": VERSION,
    }
    for key, expected in expected_coverage.items():
        if coverage.get(key) != expected:
            raise ValueError(
                f"unexpected coverage field {key}: expected {expected!r}, got {coverage.get(key)!r}"
            )


def reproduce(base: Path, source_dir: Path | None = None) -> dict[str, Any]:
    """Verify the pinned PDF and atomically reproduce its page-43 scope."""

    target_base = base.resolve()
    input_root = (source_dir or RETAINED_BASE).resolve()
    content = _read_verified_source(input_root)
    with TemporaryDirectory(prefix="repro-us-proclamation-11021-") as staging_name:
        staging_base = Path(staging_name) / "corpus"
        scope = _build_scope(staging_base, content)
        _verify_generated_scope(staging_base, content)

        target_store = CorpusArtifactStore(target_base)
        generated_hashes: dict[str, str] = {}
        for relative_path in GENERATED_RELATIVE_PATHS:
            generated = (staging_base / relative_path).read_bytes()
            target_store.write_bytes(target_base / relative_path, generated)
            generated_hashes[relative_path.as_posix()] = sha256_bytes(generated)

    return {
        "base": str(target_base),
        "command": REPRO_COMMAND,
        "files": generated_hashes,
        "scope": scope,
        "source_sha256": SOURCE_SHA256,
        "version": VERSION,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True, help="Destination corpus base.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        help=(
            "Optional local input root containing the flat staged PDF or its "
            "retained corpus path; defaults to data/corpus."
        ),
    )
    args = parser.parse_args()
    print(json.dumps(reproduce(args.base, args.source_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
