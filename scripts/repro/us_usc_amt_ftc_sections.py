#!/usr/bin/env python3
"""Reproduce the 26 USC AMT and foreign-tax-credit section ingest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.cli import main as corpus_cli

REPO_ROOT = Path(__file__).resolve().parents[2]
RETAINED_BASE = REPO_ROOT / "data/corpus"
VERSION = "2026-07-27-usc-amt-ftc-sections"
STATUTE_VERSION = f"{VERSION}-title-26"
SOURCE_AS_OF = "2026-07-12"
OLRC_URL = (
    "https://uscode.house.gov/download/releasepoints/us/pl/119/102not101/"
    "xml_usc26@119-102not101.zip"
)
REPRO_COMMAND = (
    "uv run --extra dev python "
    "scripts/repro/us_usc_amt_ftc_sections.py --base data/corpus"
)

SECTIONS = ("27", "57", "58", "59", "901", "902", "903", "904")
EXPECTED_SECTION_COUNTS = {
    "27": 1,
    "57": 43,
    "58": 17,
    "59": 98,
    "901": 131,
    "902": 1,
    "903": 1,
    "904": 259,
}

SOURCE_SCOPE = "2026-07-24-1401-coordination-repair-title-26"
RETAINED_STATUTE_ZIP = (
    Path("sources/us/statute")
    / SOURCE_SCOPE
    / "olrc/xml_usc26@119-102not101.zip"
)
RETAINED_STATUTE_XML = (
    Path("sources/us/statute") / SOURCE_SCOPE / "uslm/usc26.xml"
)
STATUTE_ZIP = (
    Path("sources/us/statute")
    / STATUTE_VERSION
    / "olrc/xml_usc26@119-102not101.zip"
)
STATUTE_XML = (
    Path("sources/us/statute") / STATUTE_VERSION / "uslm/usc26.xml"
)

EXPECTED_SHA256 = {
    STATUTE_ZIP: "d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0",
    STATUTE_XML: "d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_retained_sources() -> None:
    retained_paths = {
        RETAINED_STATUTE_ZIP: EXPECTED_SHA256[STATUTE_ZIP],
        RETAINED_STATUTE_XML: EXPECTED_SHA256[STATUTE_XML],
    }
    for relative_path, expected in retained_paths.items():
        retained_path = RETAINED_BASE / relative_path
        actual = _sha256(retained_path)
        if actual != expected:
            raise ValueError(
                f"retained source hash mismatch for {relative_path}: "
                f"expected {expected}, got {actual}"
            )

    retained_zip = RETAINED_BASE / RETAINED_STATUTE_ZIP
    retained_xml = RETAINED_BASE / RETAINED_STATUTE_XML
    with zipfile.ZipFile(retained_zip) as archive:
        if archive.namelist() != ["usc26.xml"]:
            raise ValueError(
                f"expected sole OLRC member usc26.xml, got {archive.namelist()}"
            )
        member_bytes = archive.read("usc26.xml")
    if hashlib.sha256(member_bytes).hexdigest() != EXPECTED_SHA256[STATUTE_XML]:
        raise ValueError("OLRC ZIP member hash does not match retained USC XML")
    if member_bytes != retained_xml.read_bytes():
        raise ValueError("OLRC ZIP member is not byte-equal to retained USC XML")


def _seed_source(target_base: Path, retained: Path, target: Path) -> None:
    retained_path = RETAINED_BASE / retained
    target_path = target_base / target
    if retained_path.resolve() == target_path.resolve():
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(retained_path, target_path)


def _run_cli(argv: list[str]) -> None:
    exit_code = corpus_cli(argv)
    if exit_code:
        raise SystemExit(exit_code)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _verify_generated_scope(target_base: Path) -> None:
    provisions_path = (
        target_base
        / "provisions/us/statute"
        / f"{STATUTE_VERSION}.jsonl"
    )
    rows = _load_jsonl(provisions_path)
    title_rows = [row for row in rows if row["citation_path"] == "us/statute/26"]
    if len(title_rows) != 1:
        raise ValueError(f"expected one Title 26 row, got {len(title_rows)}")

    section_counts: Counter[str] = Counter()
    for row in rows:
        parts = row["citation_path"].split("/")
        if len(parts) >= 4:
            section_counts[parts[3]] += 1
    if dict(section_counts) != EXPECTED_SECTION_COUNTS:
        raise ValueError(
            "unexpected per-section counts: "
            f"expected {EXPECTED_SECTION_COUNTS}, got {dict(section_counts)}"
        )

    rows_by_path = {row["citation_path"]: row for row in rows}
    repeal = rows_by_path["us/statute/26/902"]
    if repeal.get("body") not in {None, ""}:
        raise ValueError("26 USC 902 repeal-status atom has operative body text")
    if repeal.get("metadata", {}).get("status") != "repealed":
        raise ValueError("26 USC 902 is not marked repealed in normalized metadata")
    if not str(repeal.get("heading", "")).startswith("Repealed."):
        raise ValueError("26 USC 902 does not retain the official repeal heading")
    if any(
        path.startswith("us/statute/26/902/")
        for path in rows_by_path
    ):
        raise ValueError("26 USC 902 unexpectedly emitted operative descendants")

    for section in SECTIONS:
        root_path = f"us/statute/26/{section}"
        source_url = rows_by_path[root_path].get("source_url")
        expected_url = (
            "https://uscode.house.gov/view.xhtml?"
            f"req=granuleid:USC-prelim-title26-section{section}"
            "&num=0&edition=prelim"
        )
        if source_url != expected_url:
            raise ValueError(
                f"unexpected source URL for {root_path}: {source_url!r}"
            )

    for section in ("901", "904"):
        references = rows_by_path[f"us/statute/26/{section}"][
            "metadata"
        ].get("references_to", [])
        if "us/statute/26/902" not in references:
            raise ValueError(f"26 USC {section} no longer references repealed 902")


def reproduce(base: Path) -> None:
    target_base = base.resolve()
    _verify_retained_sources()
    _seed_source(
        target_base,
        RETAINED_STATUTE_ZIP,
        STATUTE_ZIP,
    )
    _seed_source(
        target_base,
        RETAINED_STATUTE_XML,
        STATUTE_XML,
    )

    statute_xml = target_base / STATUTE_XML
    extract_args = [
        "extract-usc",
        "--base",
        str(target_base),
        "--version",
        VERSION,
        "--source-xml",
        str(statute_xml),
        "--title",
        "26",
        "--source-as-of",
        SOURCE_AS_OF,
        "--expression-date",
        SOURCE_AS_OF,
        "--source-url",
        OLRC_URL,
    ]
    for section in SECTIONS:
        extract_args.extend(("--section", section))
    extract_args.append("--include-title")
    _run_cli(extract_args)
    _verify_generated_scope(target_base)

    print(
        json.dumps(
            {
                "base": str(target_base),
                "command": REPRO_COMMAND,
                "section_counts": EXPECTED_SECTION_COUNTS,
                "source_sha256": {
                    path.as_posix(): expected
                    for path, expected in EXPECTED_SHA256.items()
                },
                "total_rows": 1 + sum(EXPECTED_SECTION_COUNTS.values()),
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
