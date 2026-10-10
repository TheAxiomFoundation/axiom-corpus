#!/usr/bin/env python3
"""Reproduce the exact-source 26 USC 63 repair and 26 USC 165 ingest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from axiom_corpus.corpus.cli import main as corpus_cli

REPO_ROOT = Path(__file__).resolve().parents[2]
RETAINED_BASE = REPO_ROOT / "data/corpus"

VERSION = "2026-07-27-usc-63-repair-165"
STATUTE_VERSION = f"{VERSION}-title-26"
OLRC_URL = (
    "https://uscode.house.gov/download/releasepoints/us/pl/119/102not101/"
    "xml_usc26@119-102not101.zip"
)

SEED_VERSION = "2026-07-24-1401-coordination-repair-title-26"
SEED_ZIP = (
    Path("sources/us/statute")
    / SEED_VERSION
    / "olrc/xml_usc26@119-102not101.zip"
)
SEED_XML = Path("sources/us/statute") / SEED_VERSION / "uslm/usc26.xml"

TARGET_ZIP = (
    Path("sources/us/statute")
    / STATUTE_VERSION
    / "olrc/xml_usc26@119-102not101.zip"
)
TARGET_XML = Path("sources/us/statute") / STATUTE_VERSION / "uslm/usc26.xml"

EXPECTED_ZIP_SHA256 = (
    "d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0"
)
EXPECTED_XML_SHA256 = (
    "d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621"
)
EXPECTED_PROVISION_COUNT = 163
EXPECTED_SECTION_COUNTS = {"63": 62, "165": 100}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_seed_sources() -> None:
    retained_zip = RETAINED_BASE / SEED_ZIP
    retained_xml = RETAINED_BASE / SEED_XML
    actual_zip_sha256 = _sha256(retained_zip)
    actual_xml_sha256 = _sha256(retained_xml)
    if actual_zip_sha256 != EXPECTED_ZIP_SHA256:
        raise ValueError(
            "retained OLRC ZIP hash mismatch: "
            f"expected {EXPECTED_ZIP_SHA256}, got {actual_zip_sha256}"
        )
    if actual_xml_sha256 != EXPECTED_XML_SHA256:
        raise ValueError(
            "retained USLM XML hash mismatch: "
            f"expected {EXPECTED_XML_SHA256}, got {actual_xml_sha256}"
        )

    with zipfile.ZipFile(retained_zip) as archive:
        if archive.namelist() != ["usc26.xml"]:
            raise ValueError(
                f"expected sole OLRC member usc26.xml, got {archive.namelist()}"
            )
        member_bytes = archive.read("usc26.xml")
    if hashlib.sha256(member_bytes).hexdigest() != EXPECTED_XML_SHA256:
        raise ValueError("OLRC ZIP member hash does not match retained USC XML")
    if member_bytes != retained_xml.read_bytes():
        raise ValueError("OLRC ZIP member is not byte-equal to retained USC XML")


def _copy_exact_source(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _run_cli(argv: list[str]) -> None:
    exit_code = corpus_cli(argv)
    if exit_code:
        raise SystemExit(exit_code)


def _verify_generated_scope(base: Path) -> None:
    target_zip = base / TARGET_ZIP
    target_xml = base / TARGET_XML
    if _sha256(target_zip) != EXPECTED_ZIP_SHA256:
        raise ValueError("reproduced OLRC ZIP does not match the official bytes")
    if _sha256(target_xml) != EXPECTED_XML_SHA256:
        raise ValueError("reproduced USLM XML does not match the official bytes")

    provisions_path = (
        base / "provisions/us/statute" / f"{STATUTE_VERSION}.jsonl"
    )
    records = tuple(
        json.loads(line)
        for line in provisions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if len(records) != EXPECTED_PROVISION_COUNT:
        raise ValueError(
            f"expected {EXPECTED_PROVISION_COUNT} provisions, got {len(records)}"
        )

    source_path = TARGET_XML.as_posix()
    for section, expected_count in EXPECTED_SECTION_COUNTS.items():
        citation_path = f"us/statute/26/{section}"
        section_records = tuple(
            record
            for record in records
            if record["citation_path"] == citation_path
            or record["citation_path"].startswith(f"{citation_path}/")
        )
        if len(section_records) != expected_count:
            raise ValueError(
                f"expected {expected_count} section {section} records, "
                f"got {len(section_records)}"
            )
        expected_url = (
            "https://uscode.house.gov/view.xhtml?"
            f"req=granuleid:USC-prelim-title26-section{section}"
            "&num=0&edition=prelim"
        )
        if any(record["source_url"] != expected_url for record in section_records):
            raise ValueError(f"section {section} source URL is not exact")
        if any(record["source_path"] != source_path for record in section_records):
            raise ValueError(f"section {section} source path is not exact")


def reproduce(base: Path) -> None:
    target_base = base.resolve()
    _verify_seed_sources()
    _copy_exact_source(RETAINED_BASE / SEED_ZIP, target_base / TARGET_ZIP)
    _copy_exact_source(RETAINED_BASE / SEED_XML, target_base / TARGET_XML)

    _run_cli(
        [
            "extract-usc",
            "--base",
            str(target_base),
            "--version",
            VERSION,
            "--source-xml",
            str(target_base / TARGET_XML),
            "--title",
            "26",
            "--source-as-of",
            "2026-07-12",
            "--expression-date",
            "2026-07-12",
            "--source-url",
            OLRC_URL,
            "--section",
            "63",
            "--section",
            "165",
            "--include-title",
        ]
    )
    _verify_generated_scope(target_base)

    print(
        json.dumps(
            {
                "base": str(target_base),
                "command": "reproduce-us-63-repair-165",
                "source_sha256": {
                    TARGET_ZIP.as_posix(): EXPECTED_ZIP_SHA256,
                    TARGET_XML.as_posix(): EXPECTED_XML_SHA256,
                },
                "version": STATUTE_VERSION,
            },
            indent=2,
            sort_keys=True,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        type=Path,
        required=True,
        help="Corpus output base; retained official inputs are copied here.",
    )
    args = parser.parse_args()
    reproduce(args.base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
