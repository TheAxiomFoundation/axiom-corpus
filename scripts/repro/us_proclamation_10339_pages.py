#!/usr/bin/env python3
"""Reproduce page-level text for Proclamation 10339 and its solar annexes.

The retained source is the six-page Federal Register PDF for 87 FR 7357–7362.
It has a complete text layer, so this reproducer uses the corpus's standard
PyMuPDF page extraction without OCR, sorting, substitutions, or hand edits.
The document-level body already exists in a signed version; this additive
scope therefore emits only the six page records and inventories them against
the byte-pinned PDF retained beneath this new version.
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
VERSION = "2026-08-02-tariff-201-solar-proclamation-10339-pages"
ROOT_CITATION = "us/rulemaking/federal-register/2022-02-09/2022-02906"
SOURCE_AS_OF = "2026-08-02"
EXPRESSION_DATE = "2022-02-09"
SOURCE_FILENAME = "fr-2022-02906-proc-10339.pdf"
SOURCE_SHA256 = "fe4d4a4ea60e2affd41714b78cd9c400fdb3aff8d4ebd446044de9db14bccce8"
SOURCE_SIZE_BYTES = 424_072
PAGE_COUNT = 6
OFFICIAL_URL = (
    "https://www.govinfo.gov/content/pkg/FR-2022-02-09/pdf/2022-02906.pdf"
)
WAYBACK_TIMESTAMP = "20260722175202"
WAYBACK_URL = (
    f"https://web.archive.org/web/{WAYBACK_TIMESTAMP}id_/{OFFICIAL_URL}"
)
CONTENT_TYPE = "application/pdf"
TITLE = (
    "Proclamation 10339 of February 4, 2022—To Continue Facilitating "
    "Positive Adjustment to Competition From Imports of Certain Crystalline "
    "Silicon Photovoltaic Cells (Whether or Not Partially or Fully Assembled "
    "Into Other Products)"
)
REPRO_ARGV = (
    "uv",
    "run",
    "--extra",
    "dev",
    "python",
    "scripts/repro/us_proclamation_10339_pages.py",
    "--base",
    "data/corpus",
)
REPRO_COMMAND = shlex.join(REPRO_ARGV)
if shlex.join(shlex.split(REPRO_COMMAND)) != REPRO_COMMAND:
    raise AssertionError("Proclamation 10339 repro command is not shlex-canonical")

EXPECTED_BODY_SHA256 = (
    "8bbe9b28ebb0781f15a8b01908d1f89461529a61e2dc53e5e891a3a59b832589",
    "d2c24c5f0277cd676484abe2927a8f14c96abc2672ee9cc8c473b82a3af20215",
    "d132c6a1c422f43f790b95653974b148fe67f02dd607e2f8d78f6d8611a346b9",
    "6d7bf5a589505bb21e159f348adef4fb29de4b0534e901336cfdb6cb541b3fba",
    "01e0baece80edc46f9509457da8224ec4db2b29dd7d3dc252f70a3ce24172154",
    "5b135f57b65aad2aa15124dbae40c6d47a7e21dc329bc2a070a0b4cf53df4b5d",
)

SOURCE_RELATIVE_PATH = (
    Path("sources")
    / JURISDICTION
    / DOCUMENT_CLASS
    / VERSION
    / "official-documents"
    / SOURCE_FILENAME
)
INVENTORY_RELATIVE_PATH = (
    Path("inventory") / JURISDICTION / DOCUMENT_CLASS / f"{VERSION}.json"
)
PROVISIONS_RELATIVE_PATH = (
    Path("provisions") / JURISDICTION / DOCUMENT_CLASS / f"{VERSION}.jsonl"
)
COVERAGE_RELATIVE_PATH = (
    Path("coverage") / JURISDICTION / DOCUMENT_CLASS / f"{VERSION}.json"
)
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
    source_path = _resolve_input_path(source_dir)
    content = source_path.read_bytes()
    actual_sha256 = sha256_bytes(content)
    if actual_sha256 != SOURCE_SHA256:
        raise ValueError(
            "Proclamation 10339 source hash mismatch: "
            f"expected {SOURCE_SHA256}, got {actual_sha256}"
        )
    if len(content) != SOURCE_SIZE_BYTES:
        raise ValueError(
            "Proclamation 10339 source size mismatch: "
            f"expected {SOURCE_SIZE_BYTES}, got {len(content)}"
        )
    return content


def _source_metadata() -> dict[str, Any]:
    return {
        "primary_source": True,
        "source_authority": (
            "U.S. Government Publishing Office / Office of the Federal Register"
        ),
        "document_subtype": "federal_register_proclamation_page_rendition",
        "federal_register_citation": "87 FR 7357–7362",
        "federal_register_document_number": "2022-02906",
        "proclamation_number": "10339",
        "proclamation_date": "2022-02-04",
        "publication_date": EXPRESSION_DATE,
        "wayback_timestamp": WAYBACK_TIMESTAMP,
        "wayback_url": WAYBACK_URL,
        "wayback_byte_identical_to_official": True,
        "source_cross_verified_on": SOURCE_AS_OF,
        "logical_parent_citation_path": ROOT_CITATION,
        "existing_body_version": (
            "2026-08-01-tariff-201-solar-extension-types-presdocu-term-photovoltaic"
        ),
        "rendition_role": "page-level text for the existing Federal Register instrument",
        "extraction_method": (
            "PyMuPDF page.get_text('text', sort=False) through the standard "
            "corpus PDF page extractor; no OCR or text replacements"
        ),
        "repro_command": REPRO_COMMAND,
    }


def _source() -> OfficialDocumentSource:
    return OfficialDocumentSource(
        source_id="fr-2022-02906-proclamation-10339",
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS,
        title=TITLE,
        source_url=OFFICIAL_URL,
        citation_path=ROOT_CITATION,
        download_url=WAYBACK_URL,
        source_format="pdf",
        source_as_of=SOURCE_AS_OF,
        expression_date=EXPRESSION_DATE,
        extraction={"page_citation_prefix": "page"},
        metadata=_source_metadata(),
    )


def _extract_pages(content: bytes) -> tuple[_DocumentBlock, ...]:
    blocks = documents._extract_blocks(
        content,
        "pdf",
        source_url=OFFICIAL_URL,
        title=TITLE,
        extraction={"page_citation_prefix": "page"},
    )
    if len(blocks) != PAGE_COUNT:
        raise ValueError(
            f"expected {PAGE_COUNT} Proclamation 10339 pages, got {len(blocks)}"
        )
    for page_number, block in enumerate(blocks, start=1):
        if block.kind != "page" or block.ordinal != page_number:
            raise ValueError(f"unexpected page block at ordinal {page_number}")
        if block.metadata != {
            "page_number": page_number,
            "citation_suffix": f"page-{page_number}",
        }:
            raise ValueError(f"unexpected page metadata at ordinal {page_number}")
        body_sha256 = sha256_bytes(block.body.encode("utf-8"))
        if body_sha256 != EXPECTED_BODY_SHA256[page_number - 1]:
            raise ValueError(
                f"page {page_number} extracted-text hash mismatch: {body_sha256}"
            )
    return blocks


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
    blocks = _extract_pages(content)
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
        raise ValueError(f"incomplete page coverage: {coverage.to_mapping()}")
    store.write_json(staging_base / COVERAGE_RELATIVE_PATH, coverage.to_mapping())
    return {"page_count": len(blocks), "row_count": len(records)}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _verify_critical_text(records: list[dict[str, Any]]) -> None:
    page_five = records[4]["body"]
    page_six = records[5]["body"]
    required_page_five = (
        'by inserting in lieu thereof"8541.42.00"',
        "Subdivision (f) of U.S. note 18",
        'by inserting in lieu thereof"8541.43.00"',
        "Subdivision (h) of U.S. note 18",
        'by inserting in lieu thereof "8541.4 3. 00"',
        (
            "If entered during the period from February 7, 2025 through "
            "February 6, 2026 ........................................... 14%"
        ),
    )
    for text in required_page_five:
        if text not in page_five:
            raise ValueError(f"critical Annex I text missing from page 5: {text!r}")
    quota_change = (
        'The article description of subheading 9903.45.21 is modified by deleting '
        '"2.5" and by inserting in lieu thereof "5".'
    )
    if quota_change not in page_six:
        raise ValueError("critical 9903.45.21 quota change missing from page 6")


def _verify_generated_scope(staging_base: Path, content: bytes) -> None:
    if (staging_base / SOURCE_RELATIVE_PATH).read_bytes() != content:
        raise ValueError("retained Proclamation 10339 PDF is not byte-identical")
    records = _load_jsonl(staging_base / PROVISIONS_RELATIVE_PATH)
    expected_paths = [f"{ROOT_CITATION}/page-{number}" for number in range(1, 7)]
    if [record["citation_path"] for record in records] != expected_paths:
        raise ValueError("unexpected Proclamation 10339 citation paths")
    blocks = _extract_pages(content)
    for index, (record, block) in enumerate(zip(records, blocks, strict=True), start=1):
        if record.get("body") != block.body:
            raise ValueError(f"page {index} body differs from standard PDF extraction")
        if record.get("kind") != "page" or record.get("level") != 4:
            raise ValueError(f"unexpected page {index} kind or level")
        if "parent_citation_path" in record or "parent_id" in record:
            raise ValueError(f"page {index} has a cross-version structural parent")
        if record.get("version") != VERSION:
            raise ValueError(f"page {index} has an unexpected version")
        if record.get("source_url") != OFFICIAL_URL:
            raise ValueError(f"page {index} has an unexpected source URL")
        metadata = record.get("metadata", {})
        if metadata.get("download_url") != WAYBACK_URL:
            raise ValueError(f"page {index} has an unexpected download URL")
        if metadata.get("repro_command") != REPRO_COMMAND:
            raise ValueError(f"page {index} has an unexpected repro command")

    inventory = json.loads(
        (staging_base / INVENTORY_RELATIVE_PATH).read_text(encoding="utf-8")
    )["items"]
    if [item["citation_path"] for item in inventory] != expected_paths:
        raise ValueError("inventory and provision citation paths differ")
    if any(item.get("sha256") != SOURCE_SHA256 for item in inventory):
        raise ValueError("inventory source hash drifted")

    coverage = json.loads(
        (staging_base / COVERAGE_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    expected_coverage = {
        "complete": True,
        "document_class": DOCUMENT_CLASS,
        "jurisdiction": JURISDICTION,
        "matched_count": PAGE_COUNT,
        "provision_count": PAGE_COUNT,
        "source_count": PAGE_COUNT,
        "version": VERSION,
    }
    for key, expected in expected_coverage.items():
        if coverage.get(key) != expected:
            raise ValueError(
                f"unexpected coverage field {key}: expected {expected!r}, "
                f"got {coverage.get(key)!r}"
            )
    _verify_critical_text(records)


def reproduce(base: Path, source_dir: Path | None = None) -> dict[str, Any]:
    """Verify the pinned PDF and atomically reproduce its page scope."""

    target_base = base.resolve()
    input_root = (source_dir or RETAINED_BASE).resolve()
    content = _read_verified_source(input_root)
    with TemporaryDirectory(prefix="repro-us-proclamation-10339-") as staging_name:
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
