#!/usr/bin/env python3
"""Reproduce the source-complete 26 USC 469 ingest from retained OLRC bytes."""

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

VERSION = "2026-08-29-usc-469"
STATUTE_VERSION = f"{VERSION}-title-26"
SOURCE_AS_OF = "2026-07-12"
OLRC_URL = (
    "https://uscode.house.gov/download/releasepoints/us/pl/119/102/"
    "xml_usc26@119-102.zip"
)
REPRO_COMMAND = (
    "uv run --extra dev python scripts/repro/us_usc_469.py --base data/corpus"
)

SOURCE_SCOPE = "2026-07-27-usc-63-repair-165-title-26"
RETAINED_ZIP = (
    Path("sources/us/statute")
    / SOURCE_SCOPE
    / "olrc/xml_usc26@119-102not101.zip"
)
RETAINED_XML = Path("sources/us/statute") / SOURCE_SCOPE / "uslm/usc26.xml"
TARGET_ZIP = (
    Path("sources/us/statute")
    / STATUTE_VERSION
    / "olrc/xml_usc26@119-102.zip"
)
TARGET_XML = Path("sources/us/statute") / STATUTE_VERSION / "uslm/usc26.xml"

EXPECTED_ZIP_SHA256 = (
    "d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0"
)
EXPECTED_XML_SHA256 = (
    "d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621"
)
EXPECTED_KIND_COUNTS = {
    "title": 1,
    "section": 1,
    "subsection": 12,
    "paragraph": 53,
    "subparagraph": 59,
    "clause": 33,
    "subclause": 5,
}
EXPECTED_PROVISION_COUNT = sum(EXPECTED_KIND_COUNTS.values())
SECTION_URL = (
    "https://uscode.house.gov/view.xhtml?"
    "req=granuleid:USC-prelim-title26-section469&num=0&edition=prelim"
)
TITLE_URL = (
    "https://uscode.house.gov/view.xhtml?"
    "req=granuleid:USC-prelim-title26&num=0&edition=prelim"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_retained_sources() -> None:
    retained_zip = RETAINED_BASE / RETAINED_ZIP
    retained_xml = RETAINED_BASE / RETAINED_XML
    if _sha256(retained_zip) != EXPECTED_ZIP_SHA256:
        raise ValueError("retained OLRC ZIP hash does not match the reviewed source")
    if _sha256(retained_xml) != EXPECTED_XML_SHA256:
        raise ValueError("retained USLM XML hash does not match the reviewed source")

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
    if source.resolve() == target.resolve():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _run_cli(argv: list[str]) -> None:
    exit_code = corpus_cli(argv)
    if exit_code:
        raise SystemExit(exit_code)


def _load_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    return tuple(
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _verify_generated_scope(base: Path) -> None:
    target_zip = base / TARGET_ZIP
    target_xml = base / TARGET_XML
    if _sha256(target_zip) != EXPECTED_ZIP_SHA256:
        raise ValueError("reproduced OLRC ZIP does not match the official bytes")
    if _sha256(target_xml) != EXPECTED_XML_SHA256:
        raise ValueError("reproduced USLM XML does not match the official bytes")

    provisions = (
        base / "provisions/us/statute" / f"{STATUTE_VERSION}.jsonl"
    )
    records = _load_jsonl(provisions)
    if len(records) != EXPECTED_PROVISION_COUNT:
        raise ValueError(
            f"expected {EXPECTED_PROVISION_COUNT} provisions, got {len(records)}"
        )
    kind_counts = Counter(str(record["kind"]) for record in records)
    if dict(kind_counts) != EXPECTED_KIND_COUNTS:
        raise ValueError(
            f"unexpected provision kinds: expected {EXPECTED_KIND_COUNTS}, "
            f"got {dict(kind_counts)}"
        )

    records_by_path = {str(record["citation_path"]): record for record in records}
    required = {
        "us/statute/26",
        "us/statute/26/469",
        "us/statute/26/469/c",
        "us/statute/26/469/c/1",
        "us/statute/26/469/c/1/A",
        "us/statute/26/469/c/1/B",
        "us/statute/26/469/h",
        "us/statute/26/469/h/1",
        "us/statute/26/469/h/2",
        "us/statute/26/469/h/5",
    }
    if not required <= records_by_path.keys():
        raise ValueError("section 469 material-participation hierarchy is incomplete")

    source_path = TARGET_XML.as_posix()
    if records_by_path["us/statute/26"]["source_url"] != TITLE_URL:
        raise ValueError("Title 26 source URL is not exact")
    if any(
        record["source_url"] != SECTION_URL
        for path, record in records_by_path.items()
        if path != "us/statute/26"
    ):
        raise ValueError("section 469 source URLs are not exact")
    if any(record["source_path"] != source_path for record in records):
        raise ValueError("section 469 source path is not exact")
    if any(record["source_as_of"] != SOURCE_AS_OF for record in records):
        raise ValueError("section 469 source-as-of date is not exact")
    if any(record["expression_date"] != SOURCE_AS_OF for record in records):
        raise ValueError("section 469 expression date is not exact")


def reproduce(base: Path) -> None:
    target_base = base.resolve()
    _verify_retained_sources()
    _copy_exact_source(RETAINED_BASE / RETAINED_ZIP, target_base / TARGET_ZIP)
    _copy_exact_source(RETAINED_BASE / RETAINED_XML, target_base / TARGET_XML)

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
            SOURCE_AS_OF,
            "--expression-date",
            SOURCE_AS_OF,
            "--source-url",
            OLRC_URL,
            "--section",
            "469",
            "--include-title",
        ]
    )
    _verify_generated_scope(target_base)

    print(
        json.dumps(
            {
                "base": str(target_base),
                "command": REPRO_COMMAND,
                "source_sha256": {
                    TARGET_ZIP.as_posix(): EXPECTED_ZIP_SHA256,
                    TARGET_XML.as_posix(): EXPECTED_XML_SHA256,
                },
                "total_rows": EXPECTED_PROVISION_COUNT,
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
