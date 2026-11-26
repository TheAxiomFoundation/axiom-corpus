"""The line-structure successor of the Pub. L. 119-21 42 U.S.C. 1396a(xx) scope."""

from __future__ import annotations

import hashlib
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import fields, replace
from functools import cache
from pathlib import Path

import pytest

from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.uslm_quoted_content import local_name, num_value, structural_label_paths
from scripts.repro.us_pl_119_21_1396a_xx_line_structure import (
    CITATION_PATHS,
    OLRC_SOURCE_PATH,
    ROOT_CITATION_PATH,
    SECTION_IDENTIFIER,
    SOURCE_LEAF,
    SOURCE_SHA256,
    SOURCE_VERSION,
    VERSION,
    build_scope,
    check_conservation,
    olrc_label_paths,
    render_rows,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus"
SCOPE = ("us", "statute")
OLRC_ZIP = CORPUS / OLRC_SOURCE_PATH
OPEN, CLOSE = "“", "”"
PAGE_STRINGS = tuple(f"139 STAT. {page}" for page in range(307, 315))
MARGIN_NOTE_LINES = (
    "Deadline.",
    "Determination.",
    "Criteria.",
    "Regulations.",
    "Procedures.",
    "Standards.",
    "Processes.",
    "Notices.",
    "Deadline.",
    "Determination.",
    "Effective date.",
    "Notification.",
    "Electronic formats.",
    "Mail.",
    "Determinations.",
    "Expiration date.",
)
NEW_METADATA_KEYS = {
    "successor_of_version",
    "successor_of_source_path",
    "verification_source_paths",
    "statutes_at_large",
    "margin_notes",
}


def _artifact(kind: str, version: str = VERSION) -> Path:
    suffix = "jsonl" if kind == "provisions" else "json"
    return CORPUS / kind / "us/statute" / f"{version}.{suffix}"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@cache
def _rows(version: str = VERSION) -> tuple[ProvisionRecord, ...]:
    return tuple(load_provisions(_artifact("provisions", version)))


@cache
def _quoted_subsection() -> ET.Element:
    raw = (CORPUS / "sources/us/statute" / VERSION / SOURCE_LEAF).read_bytes()
    document = ET.fromstring(raw)
    section = next(
        node
        for node in document.iter()
        if local_name(node.tag) == "section" and node.get("identifier") == SECTION_IDENTIFIER
    )
    return next(
        node
        for node in section.iter()
        if local_name(node.tag) == "subsection" and num_value(node) == "xx"
    )


def _row_element(citation_path: str) -> ET.Element:
    subsection = _quoted_subsection()
    if citation_path == ROOT_CITATION_PATH:
        return subsection
    label = citation_path.rsplit("/", 1)[-1]
    return next(
        child
        for child in subsection
        if local_name(child.tag) == "paragraph" and num_value(child) == label
    )


def _text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _removals(element: ET.Element) -> list[tuple[str, str]]:
    """What the successor drops from a released body, in document order.

    An independent walk of the USLM element: the own number and heading
    ("own"), then page markers ("page"), margin notes ("note") and the open
    quote of each descendant number ("quote").
    """
    out: list[tuple[str, str]] = []

    def visit(node: ET.Element, *, top: bool) -> None:
        for child in node:
            tag = local_name(child.tag)
            if tag in {"num", "heading"} and top:
                out.append(("own", _text(child)))
            elif tag == "num":
                if _text(child).startswith(OPEN):
                    out.append(("quote", OPEN))
            elif tag == "page":
                out.append(("page", _text(child)))
            elif tag == "sidenote":
                out.append(("note", " ".join(_text(p) for p in child)))
            else:
                visit(child, top=False)

    visit(element, top=True)
    return out


def test_build_reproduces_the_scope_byte_for_byte(tmp_path: Path) -> None:
    first = build_scope(base=tmp_path / "first", source_base=CORPUS, olrc_zip=None)
    second = build_scope(base=tmp_path / "second", source_base=CORPUS, olrc_zip=None)
    built = (first.inventory_path, first.provisions_path, first.coverage_path, first.source_path)
    again = (
        second.inventory_path,
        second.provisions_path,
        second.coverage_path,
        second.source_path,
    )
    assert [_digest(path) for path in built] == [_digest(path) for path in again]
    for path, kind in zip(built[:3], ("inventory", "provisions", "coverage"), strict=True):
        assert path.read_bytes() == _artifact(kind).read_bytes(), kind
    sources = tmp_path / "first/sources/us/statute" / VERSION
    assert sorted(p.relative_to(sources).as_posix() for p in sources.rglob("*") if p.is_file()) == [
        SOURCE_LEAF
    ]
    assert _digest(first.source_path) == SOURCE_SHA256
    assert first.row_count == 12


def test_rows_keep_every_released_field_but_body_version_source_and_new_metadata() -> None:
    released = _rows(SOURCE_VERSION)
    successor = _rows()
    assert tuple(row.citation_path for row in successor) == CITATION_PATHS
    assert tuple(row.citation_path for row in released) == CITATION_PATHS
    changed = {"body", "version", "source_path", "metadata"}
    for old, new in zip(released, successor, strict=True):
        for item in fields(ProvisionRecord):
            if item.name not in changed:
                assert getattr(new, item.name) == getattr(old, item.name), (
                    new.citation_path,
                    item.name,
                )
        assert new.version == VERSION
        assert new.source_path == f"sources/us/statute/{VERSION}/{SOURCE_LEAF}"
        assert new.metadata is not None and old.metadata is not None
        assert set(new.metadata) - set(old.metadata) == NEW_METADATA_KEYS
        assert {key: new.metadata[key] for key in old.metadata} == old.metadata
        assert new.metadata["successor_of_version"] == SOURCE_VERSION
        assert new.metadata["successor_of_source_path"] == old.source_path
        assert new.metadata["verification_source_paths"] == [OLRC_SOURCE_PATH]
    root = successor[0]
    assert root.parent_citation_path is None and root.parent_id is None
    assert (root.expression_date, root.source_as_of) == ("2025-07-04", "2025-08-14")
    assert (root.kind, root.level) == ("subsection", 2)


def test_inventory_names_the_retained_bytes_and_matches_row_metadata() -> None:
    released = load_source_inventory(_artifact("inventory", SOURCE_VERSION))
    inventory = load_source_inventory(_artifact("inventory"))
    assert tuple(item.citation_path for item in inventory) == CITATION_PATHS
    for old, item, row in zip(released, inventory, _rows(), strict=True):
        assert item.sha256 == old.sha256 == SOURCE_SHA256
        assert item.source_path == row.source_path
        assert item.metadata == row.metadata
        assert (item.source_url, item.source_format) == (old.source_url, old.source_format)
    assert _digest(CORPUS / inventory[0].source_path) == SOURCE_SHA256


def _conserve(released: str, successor: str, removals: list[tuple[str, str]], *, ends: bool):
    """Walk the released words, dropping the removals in order; return what was dropped.

    Fails unless what is left is the successor's word sequence.
    """
    # The released builder joined text nodes with spaces, so it printed
    # "\u2018 applicable individual \u2019"; the source has no such spaces.
    words = released.replace("\u2018 ", "\u2018").replace(" \u2019", "\u2019").split()
    kept = successor.split()
    pending = [(kind, text.split()) for kind, text in removals if kind != "quote"]
    dropped: Counter[str] = Counter()
    out: list[str] = []
    index = 0
    while index < len(words):
        if pending and words[index : index + len(pending[0][1])] == pending[0][1]:
            kind, run = pending.pop(0)
            dropped[kind] += 1
            index += len(run)
            continue
        word = words[index]
        if word.startswith(OPEN + "(") and len(out) < len(kept) and kept[len(out)] == word[1:]:
            word = word[1:]
            dropped["quote"] += 1
        out.append(word)
        index += 1
    assert not pending, pending
    if ends:
        assert out[-1].endswith(CLOSE)
        out[-1] = out[-1][: -len(CLOSE)]
        dropped["close"] += 1
    assert out == kept
    return dropped


def test_bodies_keep_the_released_words_minus_markers_quotes_and_own_labels() -> None:
    for old, new in zip(_rows(SOURCE_VERSION), _rows(), strict=True):
        removals = _removals(_row_element(new.citation_path))
        ends = new.citation_path in {ROOT_CITATION_PATH, CITATION_PATHS[-1]}
        dropped = _conserve(old.body or "", new.body or "", removals, ends=ends)
        expected = Counter(kind for kind, _text in removals)
        if ends:
            expected["close"] += 1
        assert dropped == expected, new.citation_path
    root_removals = _removals(_quoted_subsection())
    assert [text for kind, text in root_removals if kind == "own"] == [
        OPEN + "(xx)",
        "Community Engagement Requirement for Applicable Individuals.\u2014",
    ]
    assert [text for kind, text in root_removals if kind == "page"] == list(PAGE_STRINGS)
    notes = [text for kind, text in root_removals if kind == "note"]
    assert len(notes) == 11 and " ".join(notes) == " ".join(MARGIN_NOTE_LINES)
    root = _conserve(
        _rows(SOURCE_VERSION)[0].body or "", _rows()[0].body or "", root_removals, ends=True
    )
    # 8 pages, 11 margin notes, 110 descendant open quotes (the own "(xx)"
    # carries the 111th), the own number and heading, and the closing quote.
    assert root == {"page": 8, "note": 11, "quote": 110, "own": 2, "close": 1}
    released_root = _rows(SOURCE_VERSION)[0].body or ""
    assert released_root.count(OPEN) == 111 and (_rows()[0].body or "").count(OPEN) == 0


def test_no_page_marker_text_and_no_line_opens_with_a_quote() -> None:
    for row in _rows():
        body = row.body or ""
        assert not re.search(r"\d+ STAT\. \d+", body), row.citation_path
        assert not re.search(r"\d+ STAT\. \d+", row.heading or "")
        for line in body.split("\n"):
            assert line and line == line.strip(), row.citation_path
            assert not line.startswith((OPEN, CLOSE)), (row.citation_path, line[:40])
            assert "  " not in line
    released = _rows(SOURCE_VERSION)
    assert all((row.body or "").count("\n") == 0 for row in released)
    assert sum(len(re.findall(r"\d+ STAT\. \d+", row.body or "")) for row in released[:1]) == 8


def test_each_descendant_element_starts_its_own_line_in_document_order() -> None:
    for row in _rows():
        element = _row_element(row.citation_path)
        labels = structural_label_paths(element)
        lines = (row.body or "").split("\n")
        has_text = any(local_name(child.tag) in {"chapeau", "content"} for child in element)
        structural_lines = lines[1:] if has_text else lines
        assert len(structural_lines) == len(labels), row.citation_path
        for line, label in zip(structural_lines, labels, strict=True):
            assert re.match(rf"\({re.escape(label[-1])}\)( |$)", line), (row.citation_path, line)
    root_lines = (_rows()[0].body or "").split("\n")
    assert len(root_lines) == 111
    assert Counter(len(path) for path in structural_label_paths(_quoted_subsection())) == {
        1: 11,
        2: 25,
        3: 30,
        4: 24,
        5: 19,
        6: 2,
    }


def test_each_paragraph_row_is_its_block_of_the_root_body() -> None:
    rows = _rows()
    blocks: list[list[str]] = []
    for line in (rows[0].body or "").split("\n"):
        if re.match(r"\(\d+\) ", line):
            blocks.append([line])
        else:
            blocks[-1].append(line)
    assert len(blocks) == 11
    for row, block in zip(rows[1:], blocks, strict=True):
        own = f"({row.citation_path.rsplit('/', 1)[-1]}) {row.heading}"
        assert block[0].startswith(own), row.citation_path
        rest = block[0][len(own) :].strip()
        assert (row.body or "").split("\n") == ([rest] if rest else []) + block[1:]


def test_structure_matches_the_codified_subsection_at_release_point_119_103() -> None:
    codified = olrc_label_paths(OLRC_ZIP.read_bytes())
    quoted = structural_label_paths(_quoted_subsection(), ("xx",))
    assert len(codified) == 111
    assert codified == quoted


def test_metadata_records_statutes_pages_and_margin_notes() -> None:
    rows = _rows()
    root = rows[0]
    assert root.metadata is not None
    pages = root.metadata["statutes_at_large"]
    assert (pages["volume"], pages["page_start"], pages["page_end"]) == (139, 306, 314)
    assert [item["page"] for item in pages["page_breaks"]] == list(range(307, 315))
    body = root.body or ""
    assert body[pages["page_breaks"][0]["offset"] :].startswith("a State shall provide")
    for item in pages["page_breaks"]:
        assert item["identifier"] == f"/us/stat/139/{item['page']}"
        assert not body[item["offset"]].isspace()
    notes = root.metadata["margin_notes"]
    assert [line for note in notes for line in note["notes"]] == list(MARGIN_NOTE_LINES)
    assert notes[0] == {"notes": ["Deadline."], "label_path": "xx/1", "offset": 4}
    assert body[notes[0]["offset"] :].startswith("In general.— Except as provided")
    by_paragraph: Counter[str] = Counter(note["label_path"].split("/")[1] for note in notes)
    root_break_offsets = {item["identifier"]: item["offset"] for item in pages["page_breaks"]}
    seen_breaks: set[str] = set()
    for row in rows[1:]:
        assert row.metadata is not None
        label = row.citation_path.rsplit("/", 1)[-1]
        assert len(row.metadata["margin_notes"]) == by_paragraph[label], row.citation_path
        assert all(
            note["label_path"].split("/")[1] == label for note in row.metadata["margin_notes"]
        )
        stat = row.metadata["statutes_at_large"]
        assert stat["volume"] == 139 and stat["page_start"] <= stat["page_end"]
        row_body = row.body or ""
        for item in stat["page_breaks"]:
            identifier = item["identifier"]
            assert identifier == f"/us/stat/139/{item['page']}"
            assert 0 <= item["offset"] < len(row_body), row.citation_path
            assert body.index(row_body) + item["offset"] == root_break_offsets[identifier]
            seen_breaks.add(identifier)
    assert seen_breaks == root_break_offsets.keys()
    assert rows[1].metadata is not None
    assert rows[1].metadata["margin_notes"][0]["offset"] == 0


def test_the_swap_keeps_the_release_citation_set() -> None:
    old = {row.citation_path for row in _rows(SOURCE_VERSION)}
    new = {row.citation_path for row in _rows()}
    assert new == old == set(CITATION_PATHS)


def test_the_successor_validates_alone() -> None:
    release = ReleaseManifest(
        name="us-pl-119-21-xx-line-structure",
        quality_profile="complete-expression-dates-v1",
        scopes=(ReleaseScope(*SCOPE, VERSION),),
    )
    report = validate_release(CORPUS, release, strict_warnings=True).to_mapping()
    assert report["ok"], report["issues"][:3]


def test_selecting_the_base_with_its_successor_is_rejected() -> None:
    release = ReleaseManifest(
        name="us-pl-119-21-xx-both",
        quality_profile="complete-expression-dates-v1",
        scopes=(ReleaseScope(*SCOPE, SOURCE_VERSION), ReleaseScope(*SCOPE, VERSION)),
    )
    report = validate_release(CORPUS, release, strict_warnings=True).to_mapping()
    assert not report["ok"]
    assert {issue["code"] for issue in report["issues"]} == {"duplicate_release_citation"}


def _copy_base_scope(target: Path) -> Path:
    for kind in ("inventory", "provisions"):
        destination = target / kind / "us/statute" / _artifact(kind, SOURCE_VERSION).name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_artifact(kind, SOURCE_VERSION), destination)
    sources = target / "sources/us/statute" / SOURCE_VERSION
    shutil.copytree(CORPUS / "sources/us/statute" / SOURCE_VERSION, sources)
    return target


def test_build_rejects_changed_source_bytes(tmp_path: Path) -> None:
    source_base = _copy_base_scope(tmp_path / "source")
    xml = source_base / "sources/us/statute" / SOURCE_VERSION / SOURCE_LEAF
    xml.write_bytes(xml.read_bytes().replace(b"8 percent", b"9 percent", 1))
    with pytest.raises(ValueError, match="hash changed"):
        build_scope(base=tmp_path / "out", source_base=source_base, olrc_zip=None)


def test_build_rejects_a_released_body_it_does_not_conserve(tmp_path: Path) -> None:
    source_base = _copy_base_scope(tmp_path / "source")
    provisions = source_base / "provisions/us/statute" / f"{SOURCE_VERSION}.jsonl"
    text = provisions.read_text(encoding="utf-8")
    assert text.count("1 or more but not more than 3") == 2
    provisions.write_text(text.replace("1 or more but not more than 3", "1 or more", 1), "utf-8")
    with pytest.raises(ValueError, match="not drawn from the released body"):
        build_scope(base=tmp_path / "out", source_base=source_base, olrc_zip=None)


def test_conservation_rejects_fused_words_in_the_rendered_body() -> None:
    raw = (CORPUS / "sources/us/statute" / SOURCE_VERSION / SOURCE_LEAF).read_bytes()
    _document, rows = render_rows(raw)
    root = rows[0]
    assert "shall provide" in root.rendered.body
    fused_body = root.rendered.body.replace("shall provide", "shallprovide", 1)
    fused = replace(root, rendered=replace(root.rendered, body=fused_body))

    with pytest.raises(ValueError, match="word tokens"):
        check_conservation(fused, _rows(SOURCE_VERSION)[0].body or "", ends_quotation=True)
