#!/usr/bin/env python3
"""Reproduce the 26 USC/26 CFR 1401 coordination repair from retained sources."""

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
VERSION = "2026-07-24-1401-coordination-repair"
STATUTE_VERSION = f"{VERSION}-title-26"
REGULATION_VERSION = f"{VERSION}-title-26-part-1"
OLRC_URL = (
    "https://uscode.house.gov/download/releasepoints/us/pl/119/102not101/"
    "xml_usc26@119-102not101.zip"
)

STATUTE_ZIP = (
    Path("sources/us/statute")
    / STATUTE_VERSION
    / "olrc/xml_usc26@119-102not101.zip"
)
STATUTE_XML = (
    Path("sources/us/statute") / STATUTE_VERSION / "uslm/usc26.xml"
)
REGULATION_XML = (
    Path("sources/us/regulation")
    / REGULATION_VERSION
    / "ecfr/title-26-part-1.xml"
)

EXPECTED_SHA256 = {
    STATUTE_ZIP: "d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0",
    STATUTE_XML: "d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621",
    REGULATION_XML: "1e5ca5d86df2ebf303d2df1eb9d162412e549896118779621d41139c9662001a",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_retained_sources() -> None:
    for relative_path, expected in EXPECTED_SHA256.items():
        retained_path = RETAINED_BASE / relative_path
        actual = _sha256(retained_path)
        if actual != expected:
            raise ValueError(
                f"retained source hash mismatch for {relative_path}: "
                f"expected {expected}, got {actual}"
            )

    retained_zip = RETAINED_BASE / STATUTE_ZIP
    retained_xml = RETAINED_BASE / STATUTE_XML
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


def _seed_source(target_base: Path, relative_path: Path) -> None:
    retained_path = RETAINED_BASE / relative_path
    target_path = target_base / relative_path
    if retained_path.resolve() == target_path.resolve():
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(retained_path, target_path)


def _run_cli(argv: list[str]) -> None:
    exit_code = corpus_cli(argv)
    if exit_code:
        raise SystemExit(exit_code)


def reproduce(base: Path) -> None:
    target_base = base.resolve()
    _verify_retained_sources()
    for relative_path in EXPECTED_SHA256:
        _seed_source(target_base, relative_path)

    statute_xml = target_base / STATUTE_XML
    statute_provisions = (
        target_base / "provisions/us/statute" / f"{STATUTE_VERSION}.jsonl"
    )
    statute_anchors = (
        target_base / "anchors/us/statute" / f"{STATUTE_VERSION}.jsonl"
    )
    _run_cli(
        [
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
            "2026-07-12",
            "--expression-date",
            "2026-07-12",
            "--source-url",
            OLRC_URL,
            "--section",
            "1401",
            "--section",
            "3101",
            "--include-title",
        ]
    )
    _run_cli(
        [
            "generate-anchors",
            "--provisions",
            str(statute_provisions),
            "--asserted-parent",
            "us/statute/26/1401",
            "--asserted-parent",
            "us/statute/26/3101",
            "--output",
            str(statute_anchors),
        ]
    )

    regulation_xml = target_base / REGULATION_XML
    regulation_provisions = (
        target_base
        / "provisions/us/regulation"
        / f"{REGULATION_VERSION}.jsonl"
    )
    regulation_anchors = (
        target_base / "anchors/us/regulation" / f"{REGULATION_VERSION}.jsonl"
    )
    _run_cli(
        [
            "extract-ecfr",
            "--base",
            str(target_base),
            "--version",
            VERSION,
            "--as-of",
            "2026-07-22",
            "--expression-date",
            "2026-07-22",
            "--source-xml",
            str(regulation_xml),
            "--only-title",
            "26",
            "--only-part",
            "1",
            "--section",
            "1.1401-1",
            "--workers",
            "1",
        ]
    )
    _run_cli(
        [
            "generate-anchors",
            "--provisions",
            str(regulation_provisions),
            "--target",
            "us/regulation/26/1/1401-1",
            "--output",
            str(regulation_anchors),
        ]
    )

    print(
        json.dumps(
            {
                "base": str(target_base),
                "command": "reproduce-us-1401-coordination-repair",
                "source_sha256": {
                    path.as_posix(): expected
                    for path, expected in EXPECTED_SHA256.items()
                },
                "versions": [STATUTE_VERSION, REGULATION_VERSION],
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
