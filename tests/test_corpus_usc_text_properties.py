"""Property tests for the US Code text helpers in ``axiom_corpus.corpus.usc``.

``_element_text`` collects an element's raw text and collapses whitespace once,
``_clean_text`` splits on whitespace instead of running a regex, and
``_iter_by_local`` walks ``Element.iter()`` instead of recursing. The ``_reference_*``
functions below are the earlier implementations, kept as the oracle: they collapse
whitespace at every nesting level, so every US Code body depends on the two agreeing.

Invariants, for every input:

* ``_clean_text(s)`` equals ``re.sub(r"\\s+", " ", s or "").strip()``, and that rests on
  ``\\s`` and ``str.isspace()`` naming the same code points, checked for all of them.
* ``_element_text(e)`` equals the reference for every element of every tree of
  USLM-like elements, namespaced or not, including tables nested at any depth.
* A non-table element's text is already clean: ``_clean_text`` leaves it unchanged.
* ``_iter_by_local(e, name)`` yields the same elements in the same order as the
  recursive pre-order reference, and ``_local_name`` agrees with the ``rsplit`` one.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from xml.etree import ElementTree as ET

from hypothesis import given, note, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.usc import (
    _clean_text,
    _element_text,
    _iter_by_local,
    _local_name,
)

USLM_NAMESPACE = "{http://xml.house.gov/schemas/uslm/1.0}"
LOCAL_TAGS = (
    "p",
    "content",
    "chapeau",
    "paragraph",
    "ref",
    "i",
    "num",
    "heading",
    "table",
    "tr",
    "td",
    "th",
)
WHITESPACE = tuple(
    character for character in map(chr, range(sys.maxunicode + 1)) if re.fullmatch(r"\s", character)
)
TEXT = st.text(
    alphabet=st.sampled_from(("a", "b", "§", "(", "1", ")", "|", "-", *WHITESPACE)),
    max_size=8,
)
TAGS = st.builds(
    lambda namespace, local: namespace + local,
    st.sampled_from(("", USLM_NAMESPACE)),
    st.sampled_from(LOCAL_TAGS),
)


def _reference_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _reference_iter_by_local(elem: ET.Element, name: str) -> Iterator[ET.Element]:
    if _reference_local_name(elem.tag) == name:
        yield elem
    for child in elem:
        yield from _reference_iter_by_local(child, name)


def _reference_clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _reference_table_to_markdown(table: ET.Element) -> str:
    rows: list[list[str]] = []
    for row_elem in table.iter():
        if _reference_local_name(row_elem.tag) != "tr":
            continue
        cells = [
            _reference_clean_text(" ".join(cell.itertext()))
            for cell in row_elem
            if _reference_local_name(cell.tag) in {"td", "th"}
        ]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    column_count = max(len(row) for row in rows)
    padded_rows = [row + [""] * (column_count - len(row)) for row in rows]
    widths = [max(3, max(len(row[index]) for row in padded_rows)) for index in range(column_count)]

    def format_row(row: list[str]) -> str:
        return (
            "| "
            + " | ".join(row[index].ljust(widths[index]) for index in range(column_count))
            + " |"
        )

    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    return "\n".join(
        [format_row(padded_rows[0]), separator, *(format_row(row) for row in padded_rows[1:])]
    )


def _reference_element_text(elem: ET.Element) -> str:
    if _reference_local_name(elem.tag) == "table":
        return _reference_table_to_markdown(elem)
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        child_text = _reference_element_text(child)
        if child_text:
            parts.append(child_text)
        if child.tail:
            parts.append(child.tail)
    return _reference_clean_text(" ".join(parts))


def _build(spec: tuple) -> ET.Element:
    tag, text, tail, children = spec
    elem = ET.Element(tag)
    elem.text = text
    elem.tail = tail
    elem.extend(_build(child) for child in children)
    return elem


OPTIONAL_TEXT = st.none() | TEXT
TREES = st.recursive(
    st.tuples(TAGS, OPTIONAL_TEXT, OPTIONAL_TEXT, st.just(())),
    lambda children: st.tuples(
        TAGS, OPTIONAL_TEXT, OPTIONAL_TEXT, st.lists(children, max_size=4).map(tuple)
    ),
    max_leaves=30,
).map(_build)


def test_regex_whitespace_is_exactly_str_whitespace():
    # _clean_text's str.split() and the regex collapse the same runs only because
    # \s and str.isspace() agree on every code point; this pins that premise.
    disagreements = [
        hex(code_point)
        for code_point in range(sys.maxunicode + 1)
        if bool(re.fullmatch(r"\s", chr(code_point))) != chr(code_point).isspace()
    ]

    assert disagreements == []
    assert len(WHITESPACE) > 20


@settings(max_examples=500, deadline=None)
@given(st.none() | TEXT | st.text(max_size=40))
def test_clean_text_matches_the_regex_definition(value):
    cleaned = _clean_text(value)

    assert cleaned == _reference_clean_text(value)
    assert _clean_text(cleaned) == cleaned


@settings(max_examples=400, deadline=None)
@given(TREES)
def test_element_text_matches_the_level_by_level_reference(tree):
    note(ET.tostring(tree, encoding="unicode"))
    for elem in tree.iter():
        text = _element_text(elem)

        assert text == _reference_element_text(elem)
        if _local_name(elem.tag) != "table":
            assert _clean_text(text) == text


@settings(max_examples=300, deadline=None)
@given(TREES, st.sampled_from(LOCAL_TAGS))
def test_iter_by_local_matches_the_recursive_preorder_reference(tree, name):
    note(ET.tostring(tree, encoding="unicode"))
    for elem in tree.iter():
        assert _local_name(elem.tag) == _reference_local_name(elem.tag)
        assert list(_iter_by_local(elem, name)) == list(_reference_iter_by_local(elem, name))
