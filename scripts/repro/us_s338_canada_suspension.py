#!/usr/bin/env python3
"""Reproduce the White House Canada section 338 suspension proclamation."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from bs4 import BeautifulSoup

from axiom_corpus.corpus import documents
from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import OfficialDocumentSource, _DocumentBlock
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord

VERSION = "2026-08-18-canada-338-suspension"
JURISDICTION = "us"
DOCUMENT_CLASS = DocumentClass.RULEMAKING.value
SOURCE_ID = "wh-2026-08-18-canada-338-suspension"
SOURCE_FILENAME = f"{SOURCE_ID}.html"
SOURCE_SHA256 = "252d6873bd938e3e8e571d5f2d10df3f09eef482d0911080eb432a77a192d1ac"
SOURCE_SIZE_BYTES = 305_024
SOURCE_URL = (
    "https://www.whitehouse.gov/presidential-actions/2026/08/"
    "temporary-suspension-of-additional-duties-to-offset-canadian-"
    "discrimination-against-the-commerce-of-the-united-states-with-respect-"
    "to-alcoholic-beverages-dairy-and-motor-vehicles/"
)
TITLE = (
    "Temporary Suspension of Additional Duties to Offset Canadian "
    "Discrimination Against the Commerce of the United States with Respect "
    "to Alcoholic Beverages, Dairy, and Motor Vehicles"
)
CITATION_ROOT = "us/rulemaking/white-house/2026-08-18/canada-338-suspension"
SOURCE_RELATIVE_PATH = (
    Path("sources/us/rulemaking") / VERSION / "official-documents" / SOURCE_FILENAME
)
INVENTORY_RELATIVE_PATH = Path("inventory/us/rulemaking") / f"{VERSION}.json"
PROVISIONS_RELATIVE_PATH = Path("provisions/us/rulemaking") / f"{VERSION}.jsonl"
COVERAGE_RELATIVE_PATH = Path("coverage/us/rulemaking") / f"{VERSION}.json"
GENERATED_RELATIVE_PATHS = (
    SOURCE_RELATIVE_PATH,
    INVENTORY_RELATIVE_PATH,
    PROVISIONS_RELATIVE_PATH,
    COVERAGE_RELATIVE_PATH,
)


def _source() -> OfficialDocumentSource:
    return OfficialDocumentSource(
        source_id=SOURCE_ID,
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS,
        title=TITLE,
        source_url=SOURCE_URL,
        citation_path=CITATION_ROOT,
        source_format="html",
        source_as_of="2026-08-19",
        expression_date="2026-08-18",
        metadata={
            "primary_source": True,
            "source_authority": "The White House",
            "document_subtype": "presidential_proclamation",
            "proclamation_date": "2026-08-18",
            "white_house_publication_date": "2026-08-19",
            "fetcher": "tariff parity coordinator",
            "fetched_at": "2026-08-19 15:23 ET",
            "staged_source_sha256": SOURCE_SHA256,
            "staged_source_size_bytes": SOURCE_SIZE_BYTES,
            "extraction_method": (
                "BeautifulSoup HTML parsing of the White House entry-content "
                "paragraphs; paragraph text normalized by the corpus extractor"
            ),
            "federal_register_rendition_status": "pending later upgrade",
        },
    )


def _paragraph_blocks(content: bytes) -> tuple[_DocumentBlock, ...]:
    soup = BeautifulSoup(content, "html.parser")
    root = soup.select_one("div.entry-content.wp-block-post-content")
    if root is None:
        raise ValueError("White House entry-content container not found")
    texts = [
        documents._normalize_text(node.get_text(" ", strip=True))
        for node in root.find_all("p", recursive=False)
    ]
    texts = [text for text in texts if text]
    if len(texts) != 17:
        raise ValueError(f"expected 17 proclamation paragraphs, got {len(texts)}")
    suffixes = (
        "preamble-1",
        "preamble-2",
        *(f"recital-{number}" for number in range(1, 8)),
        "proclamation-chapeau",
        *(f"clause-{number}" for number in range(1, 6)),
        "attestation",
        "signature",
    )
    headings = (
        "President of the United States",
        "A Proclamation",
        *(f"Recital {number}" for number in range(1, 8)),
        "Proclamation Chapeau",
        *(f"Clause {number}" for number in range(1, 6)),
        "Attestation",
        "Signature",
    )
    return tuple(
        _DocumentBlock(
            kind="paragraph",
            ordinal=index,
            heading=heading,
            body=text,
            metadata={"citation_suffix": suffix},
        )
        for index, (suffix, heading, text) in enumerate(
            zip(suffixes, headings, texts, strict=True), start=1
        )
    )


def _leveled(records: tuple[ProvisionRecord, ...]) -> tuple[ProvisionRecord, ...]:
    return tuple(replace(record, level=4 if index == 0 else 5) for index, record in enumerate(records))


def _build(staging_base: Path, content: bytes) -> dict[str, int]:
    store = CorpusArtifactStore(staging_base)
    source = _source()
    source_sha = store.write_bytes(staging_base / SOURCE_RELATIVE_PATH, content)
    blocks = _paragraph_blocks(content)
    source_key = SOURCE_RELATIVE_PATH.as_posix()
    inventory = documents._inventory_items(
        source,
        blocks=blocks,
        source_key=source_key,
        source_format="html",
        source_sha=source_sha,
        content_type="text/html; charset=UTF-8",
        final_url=SOURCE_URL,
    )
    records = _leveled(documents._provision_records(
        source,
        blocks=blocks,
        version=VERSION,
        source_key=source_key,
        source_format="html",
        source_as_of="2026-08-19",
        expression_date="2026-08-18",
        content_type="text/html; charset=UTF-8",
        final_url=SOURCE_URL,
    ))
    store.write_inventory(staging_base / INVENTORY_RELATIVE_PATH, inventory)
    store.write_provisions(staging_base / PROVISIONS_RELATIVE_PATH, records)
    coverage = compare_provision_coverage(
        inventory, records, jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS, version=VERSION,
    )
    if not coverage.complete:
        raise ValueError(f"incomplete coverage: {coverage.to_mapping()}")
    store.write_json(staging_base / COVERAGE_RELATIVE_PATH, coverage.to_mapping())
    return {"paragraph_count": len(blocks), "provision_count": len(records)}


def _verify(staging_base: Path, content: bytes) -> None:
    if (staging_base / SOURCE_RELATIVE_PATH).read_bytes() != content:
        raise ValueError("retained source is not byte-identical to staged source")
    rows = [
        json.loads(line)
        for line in (staging_base / PROVISIONS_RELATIVE_PATH).read_text().splitlines()
        if line
    ]
    by_path = {row["citation_path"]: row for row in rows}
    clause_one = by_path[f"{CITATION_ROOT}/clause-1"]["body"]
    required = (
        "shall be 12:01 a.m. eastern time on August 22, 2026",
        "the chapeau of Annex II of each of Proclamations 11046, 11047, and 11048",
        "deleting the effective date \u201cAugust 19, 2026\u201d",
        "inserting \u201cAugust 22, 2026\u201d in lieu thereof",
    )
    for text in required:
        if text not in clause_one:
            raise ValueError(f"operative clause text missing: {text}")
    if "suspend the collection" not in by_path[f"{CITATION_ROOT}/clause-2"]["body"]:
        raise ValueError("implementation suspension clause text missing")


def reproduce(base: Path, source_path: Path | None = None) -> dict[str, Any]:
    input_path = source_path or (base / SOURCE_RELATIVE_PATH)
    if input_path.is_symlink() or not input_path.is_file():
        raise ValueError(f"source must be a regular non-symlink file: {input_path}")
    content = input_path.read_bytes()
    if len(content) != SOURCE_SIZE_BYTES or sha256_bytes(content) != SOURCE_SHA256:
        raise ValueError("staged White House source size or SHA-256 mismatch")
    with TemporaryDirectory(prefix="repro-us-s338-canada-suspension-") as name:
        staging_base = Path(name) / "corpus"
        scope = _build(staging_base, content)
        _verify(staging_base, content)
        store = CorpusArtifactStore(base)
        hashes: dict[str, str] = {}
        for relative_path in GENERATED_RELATIVE_PATHS:
            generated = (staging_base / relative_path).read_bytes()
            store.write_bytes(base / relative_path, generated)
            hashes[relative_path.as_posix()] = sha256_bytes(generated)
    return {"files": hashes, "scope": scope, "version": VERSION}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--source-path", type=Path)
    args = parser.parse_args()
    print(json.dumps(reproduce(args.base, args.source_path), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
