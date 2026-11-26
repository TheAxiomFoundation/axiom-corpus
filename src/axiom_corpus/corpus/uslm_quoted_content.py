"""Render USLM structured text, such as a public law's quoted amendment, one element per line.

An enrolled public law in USLM prints an amendment it inserts into another law
as ``<quotedContent>``: the inserted subsection with its paragraphs,
subparagraphs, clauses and so on, each with a ``<num>`` and optional
``<heading>``, ``<chapeau>`` and ``<content>``. The Statutes at Large print
three things in that text that are not part of the inserted law:

* ``<page>`` markers (``139 STAT. 307``) where a printed page ends, often
  mid-sentence;
* ``<sidenote>`` margin notes (``Deadline.``);
* the amendatory open quote that starts every quoted paragraph, which USLM
  keeps inside each ``<num>`` (``“(1)``), and the closing quote that ends the
  quotation.

:func:`render_structural_element` renders one structural element the way
``extract-usc`` treats a row (the row's own ``<num>`` and ``<heading>`` are
not in its body) with one line per descendant structural element. It drops
page markers and margin notes from the text and reports where they stood, as
character offsets into the body, so a caller can keep them as metadata. It
strips the leading open quote from each ``<num>`` and, when told which text
node ends the quotation, the closing quote. Every other character is kept as
printed, inner quotes included. Text nodes are concatenated as the source has
them, and whitespace runs collapse to one space; the parts of a line (the
number, the heading and the text) are joined with one space. With
``drop_space_before_punctuation`` a space the source puts before ``,``, ``.``,
``;`` or ``:`` is dropped as well (GPO's USLM prints ``Code of 1986 .`` where
the printed law reads ``Code of 1986.``).

Anything the renderer cannot place raises :class:`UslmRenderError`: an element
it does not know, text between structural elements, a continuation, a marker
glued to text on both sides, or a closing quote that is not there.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

STRUCTURAL_TAGS: tuple[str, ...] = (
    "subsection",
    "paragraph",
    "subparagraph",
    "clause",
    "subclause",
    "item",
    "subitem",
)
OPEN_QUOTE = "“"
CLOSE_QUOTE = "”"

_STRUCTURAL = frozenset(STRUCTURAL_TAGS)
_TEXT_BLOCK_TAGS = frozenset({"chapeau", "content"})
_INLINE_TAGS = frozenset({"inline", "term", "ref", "date", "i", "b", "sup", "sub", "span"})
_MARKER_TAGS = frozenset({"page", "sidenote"})
_STAT_PAGE = re.compile(r"/us/stat/(?P<volume>\d+)/(?P<page>\d+)")
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:])")


class UslmRenderError(ValueError):
    """The USLM element holds something this renderer cannot place."""


@dataclass(frozen=True)
class StatutesPage:
    """A Statutes at Large page, from a ``<page identifier="/us/stat/V/P">`` marker."""

    identifier: str
    volume: int
    page: int

    @classmethod
    def from_identifier(cls, identifier: str | None) -> StatutesPage:
        match = _STAT_PAGE.fullmatch(identifier or "")
        if match is None:
            raise UslmRenderError(f"page identifier {identifier!r} is not /us/stat/<volume>/<page>")
        return cls(identifier=str(identifier), volume=int(match["volume"]), page=int(match["page"]))


@dataclass(frozen=True)
class PageBreak:
    """A page marker dropped from the text; ``offset`` is where the new page's text starts."""

    page: StatutesPage
    printed: str
    offset: int


@dataclass(frozen=True)
class MarginNote:
    """A margin note dropped from the text.

    ``notes`` holds the note's printed lines (one per ``<p>``), ``label_path``
    the labels of the structural element it sits in, from the rendered
    element's own label down, and ``offset`` the body position of the first
    character printed after it.
    """

    notes: tuple[str, ...]
    label_path: tuple[str, ...]
    offset: int


@dataclass(frozen=True)
class RenderedElement:
    """One structural element rendered as a corpus body."""

    body: str
    label_paths: tuple[tuple[str, ...], ...]
    page_breaks: tuple[PageBreak, ...]
    margin_notes: tuple[MarginNote, ...]
    stripped_open_quotes: int
    stripped_closing_quote: bool


TextSlot = tuple[ET.Element, str]


@dataclass
class _State:
    label: tuple[str, ...]
    closing_slot: TextSlot | None
    drop_space_before_punctuation: bool = False
    non_space: int = 0
    lines: list[str] = field(default_factory=list)
    page_marks: list[tuple[StatutesPage, str, int]] = field(default_factory=list)
    note_marks: list[tuple[tuple[str, ...], tuple[str, ...], int]] = field(default_factory=list)
    label_paths: list[tuple[str, ...]] = field(default_factory=list)
    open_quotes: int = 0
    closing_stripped: bool = False


def local_name(tag: str) -> str:
    """The tag without its namespace."""
    return tag.rsplit("}", 1)[-1]


def num_value(element: ET.Element) -> str | None:
    """The ``value`` of the element's own ``<num>``."""
    for child in element:
        if local_name(child.tag) == "num":
            return child.get("value")
    return None


def structural_label_paths(
    element: ET.Element, prefix: tuple[str, ...] = ()
) -> list[tuple[str, ...]]:
    """Label paths of the element's descendant structural elements, in document order.

    Labels come from each ``<num value>``, so a public law's quotation and the
    U.S. Code's codified text of the same subsection compare directly.
    """
    paths: list[tuple[str, ...]] = []
    for child in element:
        tag = local_name(child.tag)
        if tag in _STRUCTURAL:
            value = num_value(child)
            if not value:
                raise UslmRenderError(f"structural <{tag}> under {prefix} has no num value")
            path = (*prefix, value)
            paths.append(path)
            paths.extend(structural_label_paths(child, path))
        elif tag not in {"num", "heading"}:
            paths.extend(structural_label_paths(child, prefix))
    return paths


def last_text_slot(element: ET.Element) -> TextSlot:
    """The last non-blank text node inside ``element`` (its own tail excluded).

    A page marker's or margin note's own text is skipped; their tails count.
    """
    found: TextSlot | None = None

    def visit(node: ET.Element) -> None:
        nonlocal found
        if local_name(node.tag) in _MARKER_TAGS:
            return
        if node.text and node.text.strip():
            found = (node, "text")
        for child in node:
            visit(child)
            if child.tail and child.tail.strip():
                found = (child, "tail")

    visit(element)
    if found is None:
        raise UslmRenderError("element holds no text")
    return found


def page_in_effect(document: ET.Element, element: ET.Element) -> StatutesPage | None:
    """The last page marker before ``element`` in document order (the page it starts on)."""
    last: str | None = None
    for node in document.iter():
        if node is element:
            return StatutesPage.from_identifier(last) if last is not None else None
        if local_name(node.tag) == "page":
            last = node.get("identifier")
    raise UslmRenderError("element is not inside the document")


def render_structural_element(
    element: ET.Element,
    *,
    label_path: tuple[str, ...],
    closing_slot: TextSlot | None = None,
    drop_space_before_punctuation: bool = False,
) -> RenderedElement:
    """Render ``element`` as a row body: its text, then one line per descendant element.

    ``label_path`` is the element's own label path, the start of every
    reported label path. ``closing_slot`` (see :func:`last_text_slot`) names
    the text node that ends the quotation; if it is inside ``element``, the
    closing quote must end it and is removed. ``drop_space_before_punctuation``
    removes whitespace before ``,``, ``.``, ``;`` and ``:``.
    """
    tag = local_name(element.tag)
    if tag not in _STRUCTURAL:
        raise UslmRenderError(f"<{tag}> is not a structural element")
    if any(local_name(node.tag) == "continuation" for node in element.iter()):
        raise UslmRenderError("cannot place <continuation> in a one-element-per-line body")
    state = _State(
        label=label_path,
        closing_slot=closing_slot,
        drop_space_before_punctuation=drop_space_before_punctuation,
    )
    _render_children(element, state, own=True)
    body = "\n".join(state.lines)
    positions = [index for index, char in enumerate(body) if not char.isspace()]
    if len(positions) != state.non_space:
        raise UslmRenderError("rendered text lost or gained characters")

    def offset(count: int) -> int:
        return positions[count] if count < len(positions) else len(body)

    return RenderedElement(
        body=body,
        label_paths=tuple(state.label_paths),
        page_breaks=tuple(
            PageBreak(page=page, printed=printed, offset=offset(count))
            for page, printed, count in state.page_marks
        ),
        margin_notes=tuple(
            MarginNote(notes=notes, label_path=path, offset=offset(count))
            for notes, path, count in state.note_marks
        ),
        stripped_open_quotes=state.open_quotes,
        stripped_closing_quote=state.closing_stripped,
    )


def _render_children(element: ET.Element, state: _State, *, own: bool) -> None:
    """Render one structural element's lines; ``own`` leaves out its num and heading."""
    if (element.text or "").strip():
        raise UslmRenderError(f"text outside a text block in <{local_name(element.tag)}>")
    parts: list[str] = []
    seen_structural = False

    def flush() -> None:
        line = " ".join(part for part in parts if part)
        if state.drop_space_before_punctuation:
            line = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", line)
        if line:
            state.lines.append(line)
        parts.clear()

    for child in element:
        tag = local_name(child.tag)
        if tag == "num":
            if not own:
                parts.append(_num_text(child, state))
        elif tag == "heading":
            if own:
                for note in child.iter():
                    if local_name(note.tag) == "sidenote":
                        _mark(note, state)
            else:
                parts.append(_inline_text(child, state))
        elif tag in _MARKER_TAGS:
            _mark(child, state)
            if (child.tail or "").strip():
                raise UslmRenderError(f"text after <{tag}> outside a text block")
            continue
        elif tag in _TEXT_BLOCK_TAGS:
            if seen_structural:
                flush()
            parts.append(_inline_text(child, state))
        elif tag in _STRUCTURAL:
            flush()
            seen_structural = True
            value = num_value(child)
            if not value:
                raise UslmRenderError(f"structural <{tag}> under {state.label} has no num value")
            parent_label = state.label
            state.label = (*parent_label, value)
            state.label_paths.append(state.label)
            _render_children(child, state, own=False)
            state.label = parent_label
        else:
            raise UslmRenderError(f"unexpected <{tag}> in <{local_name(element.tag)}>")
        if (child.tail or "").strip():
            raise UslmRenderError(f"text after <{tag}> in <{local_name(element.tag)}>")
    flush()


def _num_text(num: ET.Element, state: _State) -> str:
    if len(num):
        raise UslmRenderError("<num> with child elements")
    text = " ".join((num.text or "").split())
    if text.startswith(OPEN_QUOTE):
        text = text[len(OPEN_QUOTE) :].lstrip()
        state.open_quotes += 1
    state.non_space += _non_space(text)
    return text


def _inline_text(element: ET.Element, state: _State) -> str:
    pieces: list[str] = []
    markers: list[tuple[str, int]] = []
    _append_inline(element, state, pieces, markers)
    # A marker's next text may come from a sibling or an enclosing inline element.
    for tag, index in markers:
        if (
            0 < index < len(pieces)
            and not pieces[index - 1][-1].isspace()
            and not pieces[index][0].isspace()
        ):
            raise UslmRenderError(f"<{tag}> splits a word")
    return " ".join("".join(pieces).split())


def _append_inline(
    element: ET.Element, state: _State, pieces: list[str], markers: list[tuple[str, int]]
) -> None:
    _emit(element.text, (element, "text"), state, pieces)
    for child in element:
        tag = local_name(child.tag)
        if tag in _MARKER_TAGS:
            _mark(child, state)
            markers.append((tag, len(pieces)))
        elif tag in _INLINE_TAGS:
            _append_inline(child, state, pieces, markers)
        else:
            raise UslmRenderError(f"unexpected <{tag}> in <{local_name(element.tag)}>")
        _emit(child.tail, (child, "tail"), state, pieces)


def _emit(text: str | None, slot: TextSlot, state: _State, pieces: list[str]) -> None:
    if not text:
        return
    closing = state.closing_slot
    if closing is not None and slot[0] is closing[0] and slot[1] == closing[1]:
        stripped = text.rstrip()
        if not stripped.endswith(CLOSE_QUOTE):
            raise UslmRenderError("the quotation's last text does not end with its closing quote")
        text = stripped[: -len(CLOSE_QUOTE)]
        state.closing_stripped = True
    if text:
        pieces.append(text)
        state.non_space += _non_space(text)


def _mark(marker: ET.Element, state: _State) -> None:
    """Record a page marker or margin note at the current position."""
    if local_name(marker.tag) == "page":
        printed = " ".join("".join(marker.itertext()).split())
        state.page_marks.append(
            (StatutesPage.from_identifier(marker.get("identifier")), printed, state.non_space)
        )
        return
    notes: list[str] = []
    for child in marker:
        if local_name(child.tag) != "p":
            raise UslmRenderError(f"unexpected <{local_name(child.tag)}> in <sidenote>")
        note = " ".join("".join(child.itertext()).split())
        if note:
            notes.append(note)
    if (marker.text or "").strip() or not notes:
        raise UslmRenderError("margin note text outside <p>, or an empty margin note")
    state.note_marks.append((tuple(notes), state.label, state.non_space))


def _non_space(text: str) -> int:
    return sum(1 for char in text if not char.isspace())
