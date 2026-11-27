"""Render the USLM quotation inserting 42 U.S.C. 1396a(xx), one element per line.

Verification covers only this quotation from Pub. L. 119-21, section 71119(a),
and only the 12 renders checked on it: subsection (xx) and its paragraphs (1) to
(11), each with its own label path, the quotation's closing quote and punctuation
normalization. :func:`render_structural_element` enforces that scope. It
accepts the quotation by the fingerprint of its canonical XML and each render
by its arguments, and it renders from a copy of the fingerprinted quotation.

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
anchors markers inside a row's own heading at body offset zero. The only
unspaced marker removal it permits is a ``<sidenote>`` within a heading between
a period and an em dash. It strips the leading open quote from each rendered
``<num>`` and, when told which text node ends the quotation, the closing quote.
Every other character in the body is kept as printed, inner quotes included.
Text nodes are concatenated as the source has them, and
whitespace runs collapse to one space. The parts of a line (the number, the
heading and the text) are joined with one space. With
``drop_space_before_punctuation`` a space the source puts before ``,``, ``.``,
``;`` or ``:`` is dropped as well (GPO's USLM prints ``Code of 1986 .`` where
the printed law reads ``Code of 1986.``).

The renderer validates the row's own number and heading before omitting them.
Unsupported elements and continuations, text outside text blocks or outside a
margin note's paragraphs, ambiguous marker boundaries, and missing closing
quotes raise :class:`UslmRenderError`.

Outside the verified quotation, punctuation normalization can fuse a leading
decimal with a structural label. A sidenote between a period and an em dash
can join them mid-heading. Foreign-namespace markers can divert body text into
metadata, a ``<br/>`` can fuse margin-note lines, and a page marker nested in a
margin note can affect :func:`page_in_effect` for the next row. The marker guard
refuses ``Shall pay<page/>.`` even with punctuation normalization. A ``<num>``
with an inline child also raises.

:func:`page_in_effect` is not a render and has no scope guard. A row that
starts before the quotation's first page marker takes its starting page from a
marker outside the quotation, which the fingerprint does not cover; the build
pins it by the SHA-256 of the whole law.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Mapping
from copy import copy, deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from types import MappingProxyType

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
_INLINE_TAGS = frozenset({"inline", "term", "ref", "date", "i", "b", "span"})
_MARKER_TAGS = frozenset({"page", "sidenote"})
_STAT_PAGE = re.compile(r"/us/stat/(?P<volume>\d+)/(?P<page>\d+)")
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:])")


@dataclass(frozen=True)
class VerifiedQuotation:
    """A quotation the renderer was checked on, and the renders checked on it.

    ``rows`` holds the label path of each checked element, which is also the
    ``label_path`` it must be rendered with. Every checked render passes the
    quotation's last text slot as ``closing_slot`` and the recorded
    ``drop_space_before_punctuation``.
    """

    description: str
    rows: frozenset[tuple[str, ...]]
    drop_space_before_punctuation: bool


VERIFIED_QUOTATIONS: Mapping[str, VerifiedQuotation] = MappingProxyType(
    {
        "fa7258db3763d6491cd5c07808d7ef0e3026d55fe7fab52ad84c070d6ddb6217": VerifiedQuotation(
            description="Pub. L. 119-21 sec. 71119(a), inserting 42 U.S.C. 1396a(xx)",
            rows=frozenset({("xx",), *(("xx", str(number)) for number in range(1, 12))}),
            drop_space_before_punctuation=True,
        ),
    }
)


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
    """The tag without its namespace.

    A comment or processing instruction kept in the tree has a non-string tag and raises.
    """
    if not isinstance(tag, str):
        raise UslmRenderError(f"a node with a non-string tag ({tag!r}), such as a comment")
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
    return [path for _node, path in _structural_nodes(element, prefix)]


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


def _quotation_fingerprint(quotation: ET.Element) -> str:
    """Hash the canonical XML of the quotation alone."""
    standalone = copy(quotation)
    standalone.tail = None
    canonical = ET.canonicalize(
        ET.tostring(standalone, encoding="unicode"), rewrite_prefixes=True, with_comments=True
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def render_structural_element(
    element: ET.Element,
    *,
    quotation: ET.Element,
    label_path: tuple[str, ...],
    closing_slot: TextSlot | None = None,
    drop_space_before_punctuation: bool = False,
) -> RenderedElement:
    """Render one checked row of a verified ``quotation``, one line per structural element.

    ``label_path`` is the element's own label path, the start of every
    reported label path. ``closing_slot`` (see :func:`last_text_slot`) names
    the text node that ends the quotation; if it is inside ``element``, the
    closing quote must end it and is removed. ``drop_space_before_punctuation``
    removes whitespace before ``,``, ``.``, ``;`` and ``:``.

    The call raises :class:`UslmRenderError` unless it is one of the checked
    renders in :data:`VERIFIED_QUOTATIONS`: the quotation's canonical XML has a
    listed fingerprint, ``element`` is one of its listed rows, ``label_path``
    is that row's own label path, ``closing_slot`` is
    ``last_text_slot(quotation)`` and ``drop_space_before_punctuation`` is the
    recorded value. It renders the matching row of a deep copy of the
    quotation, the copy it fingerprinted.
    """
    snapshot_element, snapshot_slot, verified = _checked_render(
        element,
        quotation=quotation,
        label_path=label_path,
        closing_slot=closing_slot,
        drop_space_before_punctuation=drop_space_before_punctuation,
    )
    return _render_structural_element(
        snapshot_element,
        label_path=tuple(label_path),
        closing_slot=snapshot_slot,
        drop_space_before_punctuation=verified.drop_space_before_punctuation,
    )


def _scope_error(reason: str) -> UslmRenderError:
    listed = "; ".join(
        f"{quotation.description}: {len(quotation.rows)} rows, "
        f"drop_space_before_punctuation={quotation.drop_space_before_punctuation}"
        for quotation in VERIFIED_QUOTATIONS.values()
    )
    return UslmRenderError(
        f"The renderer is verified only for the listed quotation(s) ({listed}) and the renders "
        f"checked on them, and this call is not one: {reason}. Pass a verified <quotedContent>, "
        "one of its listed rows with that row's own label path, "
        "closing_slot=last_text_slot(quotation) and the recorded "
        "drop_space_before_punctuation. For other quotations, "
        "drop_space_before_punctuation can fuse a decimal such as .25 with the preceding "
        "label into (A).25. A margin note between a period and an em dash can join them "
        "mid-heading (5 p.m.— filing). A foreign-namespace <page> or <sidenote> can divert "
        "body text into metadata. A <br/> in a margin-note paragraph can fuse its lines. "
        "A page marker nested in a margin note can set the next row's starting page "
        "through page_in_effect."
    )


def _structural_nodes(
    element: ET.Element, prefix: tuple[str, ...] = ()
) -> Iterator[tuple[ET.Element, tuple[str, ...]]]:
    """Each descendant structural element with its label path, as :func:`structural_label_paths`."""
    for child in element:
        tag = local_name(child.tag)
        if tag in _STRUCTURAL:
            value = num_value(child)
            if not value:
                raise UslmRenderError(f"structural <{tag}> under {prefix} has no num value")
            path = (*prefix, value)
            yield child, path
            yield from _structural_nodes(child, path)
        elif tag not in {"num", "heading"}:
            yield from _structural_nodes(child, prefix)


def _checked_render(
    element: ET.Element,
    *,
    quotation: ET.Element,
    label_path: tuple[str, ...],
    closing_slot: TextSlot | None,
    drop_space_before_punctuation: bool,
) -> tuple[ET.Element, TextSlot, VerifiedQuotation]:
    """Check one render against :data:`VERIFIED_QUOTATIONS`; return what to render.

    The returned element and closing slot belong to a deep copy of
    ``quotation``, whose fingerprint was checked, so later changes to the
    caller's tree cannot reach the render.
    """
    if not isinstance(quotation, ET.Element) or not isinstance(element, ET.Element):
        raise _scope_error("the quotation and the element must be ElementTree elements")
    if not isinstance(quotation.tag, str) or local_name(quotation.tag) != "quotedContent":
        raise _scope_error("the quotation is not a <quotedContent>")
    snapshot = deepcopy(quotation)
    try:
        fingerprint = _quotation_fingerprint(snapshot)
    except (SyntaxError, ValueError, TypeError, AttributeError, UnicodeError) as error:
        raise _scope_error(f"the quotation has no canonical XML ({error})") from error
    verified = VERIFIED_QUOTATIONS.get(fingerprint)
    if verified is None:
        raise _scope_error("the quotation's fingerprint is not listed")
    if drop_space_before_punctuation is not verified.drop_space_before_punctuation:
        raise _scope_error(
            f"drop_space_before_punctuation must be {verified.drop_space_before_punctuation}"
        )
    own_path = next((path for node, path in _structural_nodes(quotation) if node is element), None)
    if own_path is None:
        raise _scope_error("the element is not a structural element of the quotation")
    if own_path not in verified.rows:
        raise _scope_error(f"{own_path} is not a checked row")
    if not isinstance(label_path, tuple) or label_path != own_path:
        raise _scope_error(f"label_path {label_path!r} is not the row's own {own_path!r}")
    quotation_slot = last_text_slot(quotation)
    if (
        not isinstance(closing_slot, tuple)
        or len(closing_slot) != 2
        or closing_slot[0] is not quotation_slot[0]
        or closing_slot[1] != quotation_slot[1]
    ):
        raise _scope_error("closing_slot must be last_text_slot(quotation)")
    matches = [node for node, path in _structural_nodes(snapshot) if path == own_path]
    if len(matches) != 1:
        raise _scope_error(f"{own_path} does not name exactly one element of the quotation")
    return matches[0], last_text_slot(snapshot), verified


def _render_structural_element(
    element: ET.Element,
    *,
    label_path: tuple[str, ...],
    closing_slot: TextSlot | None = None,
    drop_space_before_punctuation: bool = False,
) -> RenderedElement:
    """Render without the scope guard, for direct use in tests only."""
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
    own_fields: set[str] = set()
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
        if own and tag in {"num", "heading"}:
            if tag in own_fields:
                raise UslmRenderError(f"multiple own <{tag}> elements")
            own_fields.add(tag)
        if tag == "num":
            parts.append(_num_text(child, state, include_text=not own))
        elif tag == "heading":
            parts.append(_inline_text(child, state, include_text=not own))
        elif tag in _MARKER_TAGS:
            _mark(child, state, count=state.non_space)
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


def _num_text(num: ET.Element, state: _State, *, include_text: bool) -> str:
    if len(num):
        raise UslmRenderError("<num> with child elements")
    text = _strip_closing_quote(num.text or "", (num, "text"), state)
    if not include_text:
        return ""
    text = " ".join(text.split())
    if text.startswith(OPEN_QUOTE):
        text = text[len(OPEN_QUOTE) :].lstrip()
        state.open_quotes += 1
    state.non_space += _non_space(text)
    return text


def _inline_text(element: ET.Element, state: _State, *, include_text: bool = True) -> str:
    pieces: list[str] = []
    markers: list[tuple[str, int]] = []

    def emit(text: str | None, slot: TextSlot) -> None:
        text = _strip_closing_quote(text or "", slot, state)
        if text:
            pieces.append(text)
            if include_text:
                state.non_space += _non_space(text)

    def visit(node: ET.Element) -> None:
        emit(node.text, (node, "text"))
        for child in node:
            tag = local_name(child.tag)
            if tag in _MARKER_TAGS:
                _mark(child, state, count=state.non_space if include_text else 0)
                markers.append((tag, len(pieces)))
            elif tag in _INLINE_TAGS:
                visit(child)
            else:
                raise UslmRenderError(f"unexpected <{tag}> in <{local_name(node.tag)}>")
            emit(child.tail, (child, "tail"))

    visit(element)
    in_heading = local_name(element.tag) == "heading"
    # A marker's next text may come from a sibling or an enclosing inline element.
    for tag, index in markers:
        if not 0 < index < len(pieces):
            continue
        before, after = pieces[index - 1][-1], pieces[index][0]
        if before.isspace() or after.isspace():
            continue
        if in_heading and tag == "sidenote" and (before, after) == (".", "—"):
            continue
        raise UslmRenderError(f"<{tag}> would join text without whitespace")
    return " ".join("".join(pieces).split()) if include_text else ""


def _strip_closing_quote(text: str, slot: TextSlot, state: _State) -> str:
    closing = state.closing_slot
    if closing is not None and slot[0] is closing[0] and slot[1] == closing[1]:
        stripped = text.rstrip()
        if not stripped.endswith(CLOSE_QUOTE):
            raise UslmRenderError("the quotation's last text does not end with its closing quote")
        state.closing_stripped = True
        return stripped[: -len(CLOSE_QUOTE)]
    return text


def _mark(marker: ET.Element, state: _State, *, count: int) -> None:
    """Record a page marker or margin note at a non-whitespace character count."""
    tag = local_name(marker.tag)
    if any(local_name(node.tag) in _MARKER_TAGS for child in marker for node in child.iter()):
        raise UslmRenderError(f"nested marker in <{tag}>")
    if tag == "page":
        printed = " ".join("".join(marker.itertext()).split())
        state.page_marks.append(
            (StatutesPage.from_identifier(marker.get("identifier")), printed, count)
        )
        return
    if (marker.text or "").strip():
        raise UslmRenderError("margin note text outside <p>")
    notes: list[str] = []
    for child in marker:
        if local_name(child.tag) != "p":
            raise UslmRenderError(f"unexpected <{local_name(child.tag)}> in <sidenote>")
        if (child.tail or "").strip():
            raise UslmRenderError("margin note text outside <p>")
        note = " ".join("".join(child.itertext()).split())
        if note:
            notes.append(note)
    if not notes:
        raise UslmRenderError("empty margin note")
    state.note_marks.append((tuple(notes), state.label, count))


def _non_space(text: str) -> int:
    return sum(1 for char in text if not char.isspace())
