#!/usr/bin/env python3
"""Rebuild 42 U.S.C. 1396a(xx) as quoted in Public Law 119-21 with one element per line.

``us/statute/2026-06-29-pl-119-21-medicaid-community-engagement-r2026-07-15-self-contained``
holds 12 rows, the subsection 1396a(xx) that Public Law 119-21 section 71119(a)
adds and its paragraphs (1) to (11). Its builder
(``scripts/extract_pl119_21_medicaid_community_engagement.py``) read the USLM
``quotedContent`` with ``itertext()``, so every body is one line that carries
the Statutes at Large page markers (``139 STAT. 307`` to ``314``) mid-sentence,
the margin notes (``Deadline.``), the amendatory open quote of every quoted
paragraph (``“(1)``), the row's own number and heading, and the closing quote.

This successor re-reads the same retained USLM bytes with
:mod:`axiom_corpus.corpus.uslm_quoted_content`: each row's body leaves out its
own number and heading, each descendant paragraph, subparagraph, clause,
subclause, item and subitem starts its own line, and page markers and margin
notes move from the text to metadata (``statutes_at_large``,
``margin_notes``). No publisher traffic: the source bytes are copied byte for
byte after their SHA-256 is checked against the released inventory. The build
fails unless every body keeps exactly the released word tokens, in
order, apart from the page markers, margin notes, quotes and own number and
heading it drops, and unless the label sequence of the quoted subsection equals
the codified 42 U.S.C. 1396a(xx) of the Office of the Law Revision Counsel's
release point 119-103, already locked in
``us/statute/2026-10-06-w6-federal-usc-closure-title-42``. The released scope
is left untouched.

    uv run --extra dev python scripts/repro/us_pl_119_21_1396a_xx_line_structure.py build \\
        --base data/corpus
"""

from __future__ import annotations

import argparse
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.resolver import ensure_corpus_paths
from axiom_corpus.corpus.uslm_quoted_content import (
    CLOSE_QUOTE,
    OPEN_QUOTE,
    RenderedElement,
    last_text_slot,
    local_name,
    num_value,
    page_in_effect,
    render_structural_element,
    structural_label_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
JURISDICTION = "us"
DOCUMENT_CLASS = DocumentClass.STATUTE
SOURCE_VERSION = "2026-06-29-pl-119-21-medicaid-community-engagement-r2026-07-15-self-contained"
VERSION = f"{SOURCE_VERSION}-r2026-11-26-line-structure"
SOURCE_LEAF = "uslm/PLAW-119publ21.xml"
SOURCE_SHA256 = "762ae9af06640f023ddb9eb6f474ff7cfa275691de338d4fd985cfb04a7b6dea"
SECTION_IDENTIFIER = "/us/pl/119/21/tVII/stB/ch1/schD/s71119"
ROOT_CITATION_PATH = "us/statute/42/1396a/xx"
CITATION_PATHS = (ROOT_CITATION_PATH, *(f"{ROOT_CITATION_PATH}/{n}" for n in range(1, 12)))

# The codified text of the same subsection, used only as a structure check.
OLRC_VERSION = "2026-10-06-w6-federal-usc-closure-title-42"
OLRC_SOURCE_PATH = f"sources/us/statute/{OLRC_VERSION}/olrc/xml_usc42@119-103.zip"
OLRC_SHA256 = "28eaf3479573ea9342c208a3cd28a48aedb57dd87a30c2f978b59d1cf4757388"
OLRC_MEMBER = "usc42.xml"
OLRC_IDENTIFIER = "/us/usc/t42/s1396a/xx"


@dataclass(frozen=True)
class SuccessorScope:
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    source_path: Path
    row_count: int


@dataclass(frozen=True)
class RowRendering:
    citation_path: str
    element: ET.Element
    rendered: RenderedElement
    own_num: str
    own_heading: str


def _scope_file(base: Path, kind: str, version: str) -> Path:
    suffix = ".jsonl" if kind == "provisions" else ".json"
    return base / kind / JURISDICTION / DOCUMENT_CLASS.value / f"{version}{suffix}"


def _quoted_subsection(document: ET.Element) -> tuple[ET.Element, ET.Element]:
    """Section 71119's quotedContent and the quoted subsection (xx) inside it."""
    sections = [
        node
        for node in document.iter()
        if local_name(node.tag) == "section" and node.get("identifier") == SECTION_IDENTIFIER
    ]
    if len(sections) != 1:
        raise ValueError(f"{SECTION_IDENTIFIER}: found {len(sections)} sections")
    found = [
        (quoted, child)
        for quoted in sections[0].iter()
        if local_name(quoted.tag) == "quotedContent"
        for child in quoted
        if local_name(child.tag) == "subsection" and num_value(child) == "xx"
    ]
    if len(found) != 1:
        raise ValueError(f"section 71119 quotes subsection (xx) {len(found)} times")
    quoted, subsection = found[0]
    if [local_name(child.tag) for child in quoted] != ["subsection"]:
        raise ValueError("section 71119's quotation holds more than subsection (xx)")
    return quoted, subsection


def _plain_text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _own(element: ET.Element, tag: str) -> str:
    children = [child for child in element if local_name(child.tag) == tag]
    if len(children) != 1:
        raise ValueError(f"<{local_name(element.tag)}> has {len(children)} <{tag}>")
    return _plain_text(children[0])


def render_rows(raw: bytes) -> tuple[ET.Element, list[RowRendering]]:
    """Render the 12 rows from the Public Law 119-21 USLM bytes."""
    document = ET.fromstring(raw)
    quoted, subsection = _quoted_subsection(document)
    closing_slot = last_text_slot(quoted)
    elements: list[tuple[str, ET.Element, tuple[str, ...]]] = [
        (ROOT_CITATION_PATH, subsection, ("xx",))
    ]
    for child in subsection:
        if local_name(child.tag) == "paragraph":
            value = num_value(child)
            elements.append((f"{ROOT_CITATION_PATH}/{value}", child, ("xx", str(value))))
    if tuple(path for path, _element, _label in elements) != CITATION_PATHS:
        raise ValueError("quoted subsection (xx) no longer has paragraphs (1) to (11)")
    rows = [
        RowRendering(
            citation_path=path,
            element=element,
            rendered=render_structural_element(
                element,
                label_path=label,
                closing_slot=closing_slot,
                # As the released builder did: the USLM has "Code of 1986 ." once.
                drop_space_before_punctuation=True,
            ),
            own_num=_own(element, "num"),
            own_heading=_own(element, "heading"),
        )
        for path, element, label in elements
    ]
    return document, rows


def _retained_text_parts(element: ET.Element, *, own: bool = True) -> Iterator[str]:
    """Yield the released text slots with the edits applied at their XML positions."""
    if element.text:
        yield element.text
    dropped = {"page", "sidenote", "num", "heading"} if own else {"page", "sidenote"}
    for child in element:
        tag = local_name(child.tag)
        if tag not in dropped:
            if tag == "num":
                yield (child.text or "").lstrip().removeprefix(OPEN_QUOTE)
            else:
                yield from _retained_text_parts(child, own=False)
        if child.tail:
            yield child.tail


def _released_text(parts: Iterable[str]) -> str:
    """Apply the released builder's text-node spacing and punctuation rules."""
    return re.sub(r"\s+([,.;:])", r"\1", " ".join(" ".join(parts).split()))


def check_conservation(row: RowRendering, released_body: str, *, ends_quotation: bool) -> None:
    """Require the released word sequence after the specified source edits."""
    released = _released_text(row.element.itertext())
    expected = _released_text(_retained_text_parts(row.element))
    # The released builder added spaces inside single quotation marks around terms.
    expected = expected.replace("‘ ", "‘").replace(" ’", "’")
    if ends_quotation:
        if not released_body.rstrip().endswith(CLOSE_QUOTE):
            raise ValueError(f"{row.citation_path}: released body lacks its closing quote")
        expected = expected.removesuffix(CLOSE_QUOTE)

    if released.split() != released_body.split() or expected.split() != row.rendered.body.split():
        raise ValueError(
            f"{row.citation_path}: successor word tokens are not drawn from the released body "
            "after the expected removals"
        )


def olrc_label_paths(zip_bytes: bytes) -> list[tuple[str, ...]]:
    """Label paths under codified 42 U.S.C. 1396a(xx) in the OLRC title 42 zip."""
    if sha256_bytes(zip_bytes) != OLRC_SHA256:
        raise ValueError("OLRC title 42 zip is not the locked release point 119-103 file")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        xml_bytes = archive.read(OLRC_MEMBER)
    for _event, node in ET.iterparse(io.BytesIO(xml_bytes), events=("end",)):
        if local_name(node.tag) == "subsection" and node.get("identifier") == OLRC_IDENTIFIER:
            return structural_label_paths(node, ("xx",))
    raise ValueError(f"{OLRC_IDENTIFIER} not in the OLRC title 42 XML")


def check_structure_against_olrc(rows: list[RowRendering], zip_bytes: bytes) -> None:
    """Fail unless the quoted subsection has the codified subsection's label sequence."""
    ours = list(rows[0].rendered.label_paths)
    codified = olrc_label_paths(zip_bytes)
    if ours != codified:
        raise ValueError(
            f"quoted (xx) has {len(ours)} labelled elements, codified (xx) {len(codified)}; "
            "the label sequences differ"
        )


def _row_metadata(
    base_metadata: dict[str, Any],
    row: RowRendering,
    document: ET.Element,
    successor_of_source_path: str,
) -> dict[str, Any]:
    start = page_in_effect(document, row.element)
    if start is None:
        raise ValueError(f"{row.citation_path}: no Statutes at Large page before it")
    breaks = row.rendered.page_breaks
    if any(item.page.volume != start.volume for item in breaks):
        raise ValueError(f"{row.citation_path}: page markers span Statutes at Large volumes")
    return {
        **base_metadata,
        "successor_of_version": SOURCE_VERSION,
        "successor_of_source_path": successor_of_source_path,
        "verification_source_paths": [OLRC_SOURCE_PATH],
        "statutes_at_large": {
            "volume": start.volume,
            "page_start": start.page,
            "page_end": breaks[-1].page.page if breaks else start.page,
            "page_breaks": [
                {"page": item.page.page, "identifier": item.page.identifier, "offset": item.offset}
                for item in breaks
            ],
        },
        "margin_notes": [
            {
                "notes": list(note.notes),
                "label_path": "/".join(note.label_path),
                "offset": note.offset,
            }
            for note in row.rendered.margin_notes
        ],
    }


def build_scope(
    *,
    base: Path,
    source_base: Path,
    olrc_zip: Path | None,
) -> SuccessorScope:
    """Build the successor scope from the retained Public Law 119-21 USLM bytes.

    ``olrc_zip`` is the locked OLRC title 42 zip for the structure check; the
    ``build`` command always passes it. ``None`` skips that check only, for
    tests of the other invariants; the written files do not depend on it.
    """
    inventory = load_source_inventory(_scope_file(source_base, "inventory", SOURCE_VERSION))
    released = load_provisions(_scope_file(source_base, "provisions", SOURCE_VERSION))
    if tuple(item.citation_path for item in inventory) != CITATION_PATHS:
        raise ValueError(f"{SOURCE_VERSION} inventory no longer lists the 12 (xx) paths")
    if tuple(record.citation_path for record in released) != CITATION_PATHS:
        raise ValueError(f"{SOURCE_VERSION} provisions no longer hold the 12 (xx) paths")
    source_paths = {item.source_path for item in inventory}
    if len(source_paths) != 1 or {item.sha256 for item in inventory} != {SOURCE_SHA256}:
        raise ValueError(f"{SOURCE_VERSION} inventory does not name the one retained USLM file")
    old_source_path = str(next(iter(source_paths)))
    raw = (source_base / old_source_path).read_bytes()
    if sha256_bytes(raw) != SOURCE_SHA256:
        raise ValueError("retained Public Law 119-21 USLM hash changed")

    document, rows = render_rows(raw)
    if olrc_zip is not None:
        check_structure_against_olrc(rows, olrc_zip.read_bytes())

    store = CorpusArtifactStore(base)
    source_file = store.source_path(JURISDICTION, DOCUMENT_CLASS, VERSION, SOURCE_LEAF)
    source_key = source_file.relative_to(base).as_posix()
    records: list[ProvisionRecord] = []
    items: list[SourceInventoryItem] = []
    for row, record, item in zip(rows, released, inventory, strict=True):
        # The released root heading leaves out the heading's own ".—"; the
        # paragraph headings keep it.
        released_heading = record.heading or ""
        if row.citation_path == ROOT_CITATION_PATH:
            released_heading += ".\u2014"
        if row.own_heading != released_heading:
            raise ValueError(f"{row.citation_path}: heading differs from the released row")
        if row.own_num != f"{OPEN_QUOTE}({row.citation_path.rsplit('/', 1)[-1]})":
            raise ValueError(f"{row.citation_path}: unexpected number {row.own_num!r}")
        if item.metadata != record.metadata:
            raise ValueError(f"{row.citation_path}: released inventory and row metadata differ")
        ends_quotation = row.rendered.stripped_closing_quote
        if ends_quotation != (row.citation_path in {ROOT_CITATION_PATH, CITATION_PATHS[-1]}):
            raise ValueError(f"{row.citation_path}: closing quote in the wrong row")
        check_conservation(row, record.body or "", ends_quotation=ends_quotation)
        metadata = _row_metadata(record.metadata or {}, row, document, old_source_path)
        records.append(
            replace(
                record,
                body=row.rendered.body,
                version=VERSION,
                source_path=source_key,
                metadata=metadata,
            )
        )
        items.append(replace(item, source_path=source_key, metadata=metadata))

    store.write_bytes(source_file, raw)
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
        raise ValueError("1396a(xx) line-structure successor coverage is incomplete")
    store.write_json(coverage_path, coverage.to_mapping())
    return SuccessorScope(
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        source_path=source_file,
        row_count=len(records),
    )


def ensure_corpus_inputs(*, source_base: Path, olrc_zip: Path | None) -> None:
    """Fetch the locked files this build reads; a no-op without lock files."""
    root = source_base.resolve()
    scope_path = Path(JURISDICTION) / DOCUMENT_CLASS.value
    paths = [
        root / "sources" / scope_path / SOURCE_VERSION,
        root / "inventory" / scope_path / f"{SOURCE_VERSION}.json",
        root / "provisions" / scope_path / f"{SOURCE_VERSION}.jsonl",
    ]
    if olrc_zip is not None and olrc_zip.resolve() == (root / OLRC_SOURCE_PATH).resolve():
        paths.append(root / OLRC_SOURCE_PATH)
    ensure_corpus_paths(paths, repo=REPO_ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build the successor scope (offline)")
    build.add_argument("--base", type=Path, default=Path("data/corpus"))
    build.add_argument("--source-base", type=Path)
    build.add_argument(
        "--olrc-zip",
        type=Path,
        help=(
            "the locked OLRC title 42 zip (default: <source-base>/"
            f"{OLRC_SOURCE_PATH}); its SHA-256 must be {OLRC_SHA256[:12]}..."
        ),
    )
    args = parser.parse_args(argv)
    source_base = args.source_base or args.base
    olrc_zip = args.olrc_zip or (source_base / OLRC_SOURCE_PATH)
    ensure_corpus_inputs(source_base=source_base, olrc_zip=olrc_zip)
    scope = build_scope(base=args.base, source_base=source_base, olrc_zip=olrc_zip)
    print(
        json.dumps(
            {
                "version": VERSION,
                "rows": scope.row_count,
                "source": str(scope.source_path),
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
