#!/usr/bin/env python3
"""Rebuild 42 CFR 435.550-435.563 (CMS-2454) without Federal Register page breaks.

``us/regulation/2026-06-29-cms-2454-ifc-42-cfr-435-community-engagement-corrected-r2026-07-24-self-contained``
holds the 14 sections of the CMS-2454 interim final rule as Federal Register raw
text slices (``federal-register-raw-text-slice``): 12 from 2026-11094 (91 FR
33348) and 435.557 and 435.558 from the correction C1-2026-11094 (91 FR 39028).
Each body is the raw text as printed: "[[Page N]]" page breaks, nine of them in
eight rows, one in the middle of a sentence, and every paragraph hard-wrapped
with its continuation lines at column 0. A continuation such as
"(c)(1)(i)(A) through (C) of this section." then begins a line, and a reader
that takes a line-initial label for a paragraph start invents paragraphs.

This successor keeps every row and changes only the body: it drops the page
markers and joins each continuation line onto its paragraph, with
:func:`normalize_federal_register_cfr_section_body`. Rows are derived from the
locked rows of the base scope, as ``scripts/compose_scope_versions.py`` derives a
composed scope: the base scope's retained source files are copied byte for byte
and each row keeps its citation path, heading, labels, identifiers, metadata,
dates and source document. Twelve of the rows have no retained raw text in the
base scope (it keeps 2026-11094 as the federalregister.gov HTML page), so the
locked rows are the input; the two corrected rows are also checked against a
fresh slice of the retained C1-2026-11094 raw text.

Two steps:

``fetch`` (network, run once): downloads the eCFR XML of each of the 14
sections as in force on 2026-07-31, the rows' expression date and the date of
each section's one eCFR version, with a provenance record. They are checks only.

``build`` (offline): copies the base scope's sources and the eCFR checks,
normalises the 14 bodies, and fails unless every body keeps the base's
non-space characters (less the page markers) and reads, line for paragraph,
as the eCFR section does. Then it writes the inventory, provisions and coverage.

    uv run --extra dev python scripts/repro/us_cms_2454_435_fr_page_markers.py fetch --base data/corpus
    uv run --extra dev python scripts/repro/us_cms_2454_435_fr_page_markers.py build --base data/corpus
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import urllib.request
import zlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.ecfr import USER_AGENT as ECFR_USER_AGENT
from axiom_corpus.corpus.federal_register import (
    FEDERAL_REGISTER_PAGE_MARKER,
    _federal_register_cfr_section_body,
    normalize_federal_register_cfr_section_body,
)
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.resolver import ensure_corpus_paths
from axiom_corpus.corpus.supabase import deterministic_provision_id

REPO_ROOT = Path(__file__).resolve().parents[2]
JURISDICTION = "us"
DOCUMENT_CLASS = DocumentClass.REGULATION
SOURCE_VERSION = (
    "2026-06-29-cms-2454-ifc-42-cfr-435-community-engagement-corrected-r2026-07-24-self-contained"
)
VERSION = f"{SOURCE_VERSION}-r2026-11-26-fr-page-markers"
# The locked bytes of the base scope's inventory and provisions
# (.axiom/corpus-locks/us/regulation/<SOURCE_VERSION>.json).
SOURCE_INVENTORY_SHA256 = "93c35a635b1a60034ac211f0d6b43f1bd2ca8397558cf2f77345898d71556c6b"
SOURCE_PROVISIONS_SHA256 = "ef36b03266e212fa35f0b3bca33beb09774d083bd17988156e12192fdf720bea"
_PREDECESSOR = (
    "release-scope-us-regulation-2026-06-03-cms-2454-ifc-42-cfr-435-community-engagement-"
    "r2026-07-15-self-contained-r2026-07-15-cascade-contained-r2026-07-15-self-contained-"
    "r2026-07-17-dedup"
)
CORRECTION_LEAF = "federal-register/documents/C1-2026-11094.txt"
# The base scope's retained sources, copied unchanged, with their locked sha256.
RETAINED_SOURCES = {
    CORRECTION_LEAF: "5f063fd2316efc64d600be6c2e29ec50a616d33fac6d59341533fac0ecdeab20",
    f"official-documents/{_PREDECESSOR}": (
        "2ef8bfb3eb99b5f5d93eb5c9b6d932e7c8adc4af3d4484f6583368920720eab9"
    ),
    f"provenance/{_PREDECESSOR}.json": (
        "02f1dda07551eef9ff7f07aac3a9d14cd5b215563d81b6acbb80600e70eb014d"
    ),
}
# Row order of the base scope (the 2026-07-24 composition put 435.557-558 last).
SECTIONS = (
    "435.550",
    "435.551",
    "435.552",
    "435.553",
    "435.554",
    "435.555",
    "435.556",
    "435.559",
    "435.560",
    "435.561",
    "435.562",
    "435.563",
    "435.557",
    "435.558",
)
CORRECTED_SECTIONS = frozenset({"435.557", "435.558"})
ECFR_DATE = "2026-07-31"
ECFR_URL = (
    "https://www.ecfr.gov/api/versioner/v1/full/{date}/title-42.xml?part=435&section={section}"
)


def citation_path(section: str) -> str:
    part, number = section.split(".")
    return f"us/regulation/42/{part}/{number}"


def ecfr_leaf(section: str) -> str:
    return f"ecfr/title-42-section-{section}.xml"


def ecfr_provenance_leaf(section: str) -> str:
    return f"provenance/ecfr-title-42-section-{section}.json"


VERIFICATION_LEAVES = tuple(
    leaf for section in SECTIONS for leaf in (ecfr_leaf(section), ecfr_provenance_leaf(section))
)


@dataclass(frozen=True)
class SuccessorScope:
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    source_root: Path
    section_count: int


def _scope_root(base: Path, version: str) -> Path:
    return Path(base, "sources", JURISDICTION, DOCUMENT_CLASS.value, version)


def _source_key(version: str, leaf: str) -> str:
    return f"sources/{JURISDICTION}/{DOCUMENT_CLASS.value}/{version}/{leaf}"


def _artifact(base: Path, kind: str, version: str) -> Path:
    suffix = "jsonl" if kind == "provisions" else "json"
    return Path(base, kind, JURISDICTION, DOCUMENT_CLASS.value, f"{version}.{suffix}")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _decode(data: bytes, encoding: str) -> bytes:
    normalized = encoding.strip().lower()
    if normalized in ("gzip", "x-gzip"):
        return gzip.decompress(data)
    if normalized == "deflate":
        try:
            return zlib.decompress(data)
        except zlib.error:
            return zlib.decompress(data, -zlib.MAX_WBITS)
    if normalized in ("", "identity"):
        return data
    raise ValueError(f"unsupported content encoding: {encoding!r}")


def fetch_verification_sources(*, base: Path) -> tuple[Path, ...]:
    """Download the eCFR XML of the 14 sections as of 2026-07-31, with provenance.

    The eCFR ``full`` endpoint refuses uncompressed responses, so the request
    offers gzip and deflate (as ``axiom_corpus.corpus.ecfr`` does); the stored
    bytes and their sha256 are the decoded XML.
    """

    store = CorpusArtifactStore(base)
    root = _scope_root(base, VERSION)
    written: list[Path] = []
    for section in SECTIONS:
        url = ECFR_URL.format(date=ECFR_DATE, section=section)
        request = urllib.request.Request(
            url, headers={"User-Agent": ECFR_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
        )
        fetched_at = _now()
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = bytes(response.read())
            status = response.status
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type")
            encoding = response.headers.get("Content-Encoding") or ""
        content = _decode(raw, encoding)
        ecfr_paragraphs(content, section)  # refuse anything that is not the section's XML
        provenance = {
            "document_id": f"ecfr-title-42-section-{section}-{ECFR_DATE}",
            "url": url,
            "final_url": final_url,
            "fetched_at": fetched_at,
            "sha256": sha256_bytes(content),
            "http": status,
            "content_type": content_type,
            "content_encoding": encoding or None,
            "fetch_method": "http-get",
            "confidence": "high",
            "purpose": (
                f"verification: the eCFR text of 42 CFR {section} in force on {ECFR_DATE}, "
                "checked paragraph for line against the normalised Federal Register body"
            ),
        }
        store.write_bytes(root / ecfr_leaf(section), content)
        store.write_bytes(
            root / ecfr_provenance_leaf(section),
            (json.dumps(provenance, indent=2) + "\n").encode("utf-8"),
        )
        written.extend((root / ecfr_leaf(section), root / ecfr_provenance_leaf(section)))
    return tuple(written)


def ecfr_paragraphs(content: bytes, section: str) -> list[str]:
    """The heading and paragraphs of one eCFR section, in document order.

    The citation note (``CITA``) is left out: the Federal Register body has none.
    """

    root = ET.fromstring(content)
    if root.tag != "DIV8" or root.get("N") != section or root.get("TYPE") != "SECTION":
        raise ValueError(f"eCFR XML is not section {section}: {root.tag} {root.attrib}")
    unexpected = sorted({child.tag for child in root} - {"HEAD", "P", "CITA"})
    if unexpected:
        raise ValueError(f"eCFR section {section} has elements this check skips: {unexpected}")
    return ["".join(child.itertext()) for child in root if child.tag in ("HEAD", "P")]


def non_space_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _lineage(record: ProvisionRecord, section: str) -> dict[str, Any]:
    return {
        "successor_of_version": SOURCE_VERSION,
        "successor_of_source_path": record.source_path,
        "verification_source_paths": [_source_key(VERSION, ecfr_leaf(section))],
    }


def _retained_leaf(source_path: str | None) -> str:
    prefix = _source_key(SOURCE_VERSION, "")
    if source_path is None or not source_path.startswith(prefix):
        raise ValueError(f"source_path is outside the base scope: {source_path}")
    leaf = source_path[len(prefix) :]
    if leaf not in RETAINED_SOURCES:
        raise ValueError(f"source_path is not a retained source: {source_path}")
    return leaf


def build_scope(*, base: Path, source_base: Path) -> SuccessorScope:
    """Build the successor from the base scope's locked rows and the eCFR checks."""

    store = CorpusArtifactStore(base)
    old_root = _scope_root(source_base, SOURCE_VERSION)
    verification_root = _scope_root(source_base, VERSION)
    new_root = _scope_root(base, VERSION)

    old_inventory_path = _artifact(source_base, "inventory", SOURCE_VERSION)
    old_provisions_path = _artifact(source_base, "provisions", SOURCE_VERSION)
    for path, expected in (
        (old_inventory_path, SOURCE_INVENTORY_SHA256),
        (old_provisions_path, SOURCE_PROVISIONS_SHA256),
    ):
        if sha256_bytes(path.read_bytes()) != expected:
            raise ValueError(f"{path} is not the locked base artifact")
    old_items = load_source_inventory(old_inventory_path)
    old_records = load_provisions(old_provisions_path)
    expected_paths = [citation_path(section) for section in SECTIONS]
    if [item.citation_path for item in old_items] != expected_paths:
        raise ValueError("base inventory no longer lists the 14 sections in order")
    if [record.citation_path for record in old_records] != expected_paths:
        raise ValueError("base provisions no longer hold the 14 sections in order")

    retained: dict[str, bytes] = {}
    for leaf, expected in RETAINED_SOURCES.items():
        content = (old_root / leaf).read_bytes()
        if sha256_bytes(content) != expected:
            raise ValueError(f"retained source {leaf} changed")
        retained[leaf] = content
    verification: dict[str, bytes] = {}
    for section in SECTIONS:
        content = (verification_root / ecfr_leaf(section)).read_bytes()
        provenance_bytes = (verification_root / ecfr_provenance_leaf(section)).read_bytes()
        if sha256_bytes(content) != json.loads(provenance_bytes)["sha256"]:
            raise ValueError(f"{ecfr_leaf(section)} does not match its provenance")
        verification[ecfr_leaf(section)] = content
        verification[ecfr_provenance_leaf(section)] = provenance_bytes
    correction_text = retained[CORRECTION_LEAF].decode("utf-8")

    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    for section, item, record in zip(SECTIONS, old_items, old_records, strict=True):
        body = record.body or ""
        if section in CORRECTED_SECTIONS:
            if record.source_path != _source_key(SOURCE_VERSION, CORRECTION_LEAF):
                raise ValueError(f"{section}: not sliced from C1-2026-11094")
            if _federal_register_cfr_section_body(correction_text, section) != body:
                raise ValueError(f"{section}: base body is not the retained C1-2026-11094 slice")
        if item.source_path != record.source_path:
            raise ValueError(f"{section}: inventory and row name different sources")
        leaf = _retained_leaf(record.source_path)
        if item.sha256 != RETAINED_SOURCES[leaf]:
            raise ValueError(f"{section}: inventory hash is not its retained source's")
        paragraphs = ecfr_paragraphs(verification[ecfr_leaf(section)], section)
        try:
            normalised = normalize_federal_register_cfr_section_body(body, paragraphs)
        except ValueError as exc:
            raise ValueError(f"{section}: {exc}") from exc
        if "[[Page" in normalised:
            raise ValueError(f"{section}: a page marker survived")
        if non_space_text(normalised) != non_space_text(FEDERAL_REGISTER_PAGE_MARKER.sub("", body)):
            raise ValueError(f"{section}: normalisation changed a non-space character")

        lineage = _lineage(record, section)
        source_path = _source_key(VERSION, leaf)
        items.append(
            replace(item, source_path=source_path, metadata={**(item.metadata or {}), **lineage})
        )
        records.append(
            replace(
                record,
                version=VERSION,
                id=deterministic_provision_id(record.citation_path, VERSION),
                body=normalised,
                source_path=source_path,
                metadata={**(record.metadata or {}), **lineage},
            )
        )

    for leaf, content in {**retained, **verification}.items():
        store.write_bytes(new_root / leaf, content)
    inventory_path = store.inventory_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    provisions_path = store.provisions_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    coverage_path = store.coverage_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    store.write_inventory(inventory_path, items)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(items),
        tuple(records),
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS.value,
        version=VERSION,
    )
    if not coverage.complete:
        raise ValueError("42 CFR 435.550-435.563 successor coverage is incomplete")
    store.write_json(coverage_path, coverage.to_mapping())
    return SuccessorScope(
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        source_root=new_root,
        section_count=len(records),
    )


def ensure_corpus_inputs(*, repo: Path = REPO_ROOT, source_base: Path | None = None) -> None:
    """Fetch the locked files this build reads; a no-op without lock files.

    Those are the base scope's sources, inventory and provisions, and the eCFR
    checks under the successor's own source directory (once it is locked),
    never the successor's inventory, provisions or coverage, which it writes.
    """

    input_root = source_base.resolve() if source_base is not None else Path("data/corpus")
    verification_root = _scope_root(input_root, VERSION)
    ensure_corpus_paths(
        [
            _scope_root(input_root, SOURCE_VERSION),
            _artifact(input_root, "inventory", SOURCE_VERSION),
            _artifact(input_root, "provisions", SOURCE_VERSION),
            *(verification_root / leaf for leaf in VERIFICATION_LEAVES),
        ],
        repo=repo,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)
    fetch = subparsers.add_parser("fetch", help="download the eCFR verification sources (network)")
    fetch.add_argument("--base", type=Path, default=Path("data/corpus"))
    build = subparsers.add_parser("build", help="build the successor scope (offline)")
    build.add_argument("--base", type=Path, default=Path("data/corpus"))
    build.add_argument("--source-base", type=Path)
    args = parser.parse_args(argv)
    if args.command == "fetch":
        for path in fetch_verification_sources(base=args.base):
            print(path)
        return 0
    source_base = args.source_base or args.base
    ensure_corpus_inputs(source_base=source_base)
    scope = build_scope(base=args.base, source_base=source_base)
    print(
        json.dumps(
            {
                "version": VERSION,
                "sections": scope.section_count,
                "inventory": str(scope.inventory_path),
                "provisions": str(scope.provisions_path),
                "coverage": str(scope.coverage_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
