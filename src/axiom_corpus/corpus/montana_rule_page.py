"""Read one ARM rule from a retained rules.mt.gov rule page.

The rules.mt.gov browser page renders the rule's PDF with react-pdf. Its
text layer (``div.react-pdf__Page__textContent``) holds one absolutely
positioned ``span`` per run of text, with ``left``/``top`` given as page
percentages. Around the PDF the page carries its own chrome: menus, the
version list and the accordions (rule version, contact, history, MAR notices,
references, referenced-by).

This module rebuilds the rule document from the text layer alone:

* spans with the same ``top`` on a page form a line;
* the lines before the first numbered paragraph are the heading;
* ``Authorizing statute(s):``, ``Implementing statute(s):`` and ``History:``
  open the trailer, which is returned as fields, not body;
* a line that opens with a paragraph marker such as ``(1)`` or ``(a)`` starts
  a paragraph; a one-span line at that paragraph's text indent continues it;
* every other run of lines is a table. A line that opens with a row label
  (``1``, ``20``, ``1st``) starts a data row; unlabelled lines continue the
  row, cell by cell. Lines above the first data row are grouped into title
  rows and a column-header row: a gap wider than the text's line height (the
  smallest gap between two lines of a page) starts a new group.

Wrapped lines are joined with a space, except that a line ending in a hyphen
attached to a letter or digit joins the next word directly (``Post-`` +
``Employment``),
and inside a table cell a break inside a numeral joins directly (``$ 37`` +
``5``): a word processor breaks a numeral only when it does not fit the cell.

The chrome is read separately, for metadata only. Every rule the parser
cannot read (overlapping columns, a table without labelled rows, a heading
without an ARM number) raises ``MontanaRulePageError`` instead of guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from bs4.element import Tag

from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord
from axiom_corpus.corpus.montana_admin_rules import (
    _ARM_REF_RE,
    _MCA_REF_RE,
    _normalize_mca_citation,
    _path_token,
)
from axiom_corpus.corpus.supabase import deterministic_provision_id

_POSITION_RE = re.compile(r"left:\s*(?P<left>-?\d+(?:\.\d+)?)%;\s*top:\s*(?P<top>-?\d+(?:\.\d+)?)%")
_PARAGRAPH_MARKER_RE = re.compile(r"^\((?:\d+|[a-z]{1,4})\)$")
_ROW_LABEL_RE = re.compile(r"^\d+(?:st|nd|rd|th)?$")
_HEADING_RE = re.compile(r"^(?P<citation>\d{1,2}\.\d{1,3}\.\d{1,4})\s+(?P<name>\S.*)$")
_TRAILER_LABELS = (
    ("authorizing_statutes", "Authorizing statute(s):"),
    ("implementing_statutes", "Implementing statute(s):"),
    ("history", "History:"),
)
_EFFECTIVE_RANGE_RE = re.compile(
    r"^(?P<start>\d{2}/\d{2}/\d{4})\s*-\s*(?:(?P<end>\d{2}/\d{2}/\d{4})|Present)$"
)
_POLICY_HREF_RE = re.compile(
    r"/browse/collections/(?P<collection>[0-9a-f-]{36})/policies/(?P<policy>[0-9a-f-]{36})"
)
_SECTION_HREF_RE = re.compile(
    r"/browse/collections/(?P<collection>[0-9a-f-]{36})/sections/(?P<section>[0-9a-f-]{36})"
)
_HYPHEN_WRAP_RE = re.compile(r"[^\W_]-$")
_NUMERAL_WRAP_RE = re.compile(r"\d[,.]?$")
_ARIA_REFERENCE_RE = re.compile(r"^View reference: (?P<label>.+) \(opens in new tab\)$")
MONTANA_RULES_PAGE_ORIGIN = "https://rules.mt.gov"
_INDENT_TOLERANCE = 0.3
_PITCH_TOLERANCE = 0.05


class MontanaRulePageError(ValueError):
    """The retained page does not have the structure this reader expects."""


@dataclass(frozen=True)
class TextLayerSegment:
    left: float
    text: str


@dataclass(frozen=True)
class TextLayerLine:
    page: int
    top: float
    segments: tuple[TextLayerSegment, ...]

    @property
    def words(self) -> tuple[TextLayerSegment, ...]:
        return tuple(segment for segment in self.segments if segment.text.strip())

    @property
    def left(self) -> float:
        return self.words[0].left

    @property
    def text(self) -> str:
        return squash_text("".join(segment.text for segment in self.segments))


@dataclass(frozen=True)
class MontanaRuleVersion:
    number: str
    version_uuid: str | None
    effective_start_date: str
    effective_end_date: str | None
    active: bool


@dataclass(frozen=True)
class MontanaRuleReference:
    label: str
    url: str | None


@dataclass(frozen=True)
class MontanaRulePageChrome:
    """Facts the page states outside the rule document."""

    collection_uuid: str
    policy_uuid: str
    parent_section_uuid: str | None
    parent_section_label: str | None
    active_version: MontanaRuleVersion
    versions: tuple[MontanaRuleVersion, ...]
    contact_information: str | None
    history: str | None
    mar_notices: tuple[MontanaRuleReference, ...]
    references: tuple[MontanaRuleReference, ...]
    referenced_by: tuple[MontanaRuleReference, ...]


@dataclass(frozen=True)
class MontanaRuleDocument:
    """The rule document the text layer carries."""

    citation_id: str
    heading: str
    body_lines: tuple[str, ...]
    authorizing_statutes: str | None
    implementing_statutes: str | None
    history: str | None
    page_count: int

    @property
    def heading_line(self) -> str:
        return f"{self.citation_id} {self.heading}"

    @property
    def body(self) -> str:
        return "\n".join(self.body_lines)

    def document_lines(self) -> tuple[str, ...]:
        """Heading, body and trailer, one rendered line each."""

        trailer = tuple(
            f"{label} {value}"
            for key, label in _TRAILER_LABELS
            for value in (getattr(self, key),)
            if value
        )
        return (self.heading_line, *self.body_lines, *trailer)


def squash_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def join_wrapped(parts: list[str] | tuple[str, ...], *, numeral_wrap: bool = False) -> str:
    """Join wrapped lines of one paragraph or table cell.

    A line that ends in a hyphen attached to a letter or digit (``Post-``,
    ``53-4-``) joins a next line that opens with a letter or digit directly: a
    word processor wraps a hyphenated word after its hyphen. A spaced dash
    (``income -``) keeps its space. With ``numeral_wrap`` (table cells), a line that ends inside
    a numeral (a digit, or a digit and a thousands or decimal separator) joins
    a next line that opens with a digit directly: ``$ 37`` + ``5`` is ``$ 375``.
    Every other break was a space.
    """

    out = ""
    for raw in parts:
        part = squash_text(raw)
        if not part:
            continue
        if not out:
            out = part
        elif (_HYPHEN_WRAP_RE.search(out) and part[:1].isalnum()) or (
            numeral_wrap and _NUMERAL_WRAP_RE.search(out) and part[:1].isdigit()
        ):
            out += part
        else:
            out += " " + part
    return out


def text_layer_lines(html: bytes) -> tuple[TextLayerLine, ...]:
    """Return the text layer's lines in reading order: page, then top."""

    soup = BeautifulSoup(html, "html.parser")
    pages = soup.select("div.react-pdf__Page")
    if not pages:
        raise MontanaRulePageError("page has no react-pdf pages")
    numbers = [int(str(page.get("data-page-number"))) for page in pages]
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
        raise MontanaRulePageError(f"react-pdf page numbers are not 1..n: {numbers}")
    lines: list[TextLayerLine] = []
    for number, page in sorted(zip(numbers, pages, strict=True), key=lambda item: item[0]):
        layer = page.select_one("div.react-pdf__Page__textContent")
        if layer is None:
            raise MontanaRulePageError(f"page {number} has no text layer")
        by_top: dict[float, list[TextLayerSegment]] = {}
        for span in layer.find_all("span"):
            if not isinstance(span, Tag) or span.find("span") is not None:
                continue
            text = span.get_text()
            if not text:
                continue
            match = _POSITION_RE.search(str(span.get("style") or ""))
            if match is None:
                raise MontanaRulePageError(f"page {number}: text span without a position: {text!r}")
            by_top.setdefault(float(match["top"]), []).append(
                TextLayerSegment(left=float(match["left"]), text=text)
            )
        for top in sorted(by_top):
            segments = tuple(sorted(by_top[top], key=lambda segment: segment.left))
            if any(segment.text.strip() for segment in segments):
                lines.append(TextLayerLine(page=number, top=top, segments=segments))
    if not lines:
        raise MontanaRulePageError("text layer is empty")
    return tuple(lines)


def parse_montana_rule_document(html: bytes) -> MontanaRuleDocument:
    """Rebuild the rule document from the page's react-pdf text layer."""

    lines = text_layer_lines(html)
    first_paragraph = next(
        (index for index, line in enumerate(lines) if _is_paragraph_start(line)), None
    )
    if first_paragraph is None or first_paragraph == 0:
        raise MontanaRulePageError("text layer has no heading before its first paragraph")
    trailer_start = next(
        (
            index
            for index, line in enumerate(lines)
            if line.words[0].text.strip() == _TRAILER_LABELS[0][1]
        ),
        len(lines),
    )
    if trailer_start <= first_paragraph:
        raise MontanaRulePageError("trailer starts before the first paragraph")

    heading_line = join_wrapped([line.text for line in lines[:first_paragraph]])
    heading_match = _HEADING_RE.match(heading_line)
    if heading_match is None:
        raise MontanaRulePageError(f"heading does not open with an ARM number: {heading_line!r}")

    body_lines = _body_lines(lines[first_paragraph:trailer_start], pitch=_line_pitch(lines))
    trailer = _trailer_fields(lines[trailer_start:])
    return MontanaRuleDocument(
        citation_id=heading_match["citation"],
        heading=heading_match["name"],
        body_lines=body_lines,
        authorizing_statutes=trailer.get("authorizing_statutes"),
        implementing_statutes=trailer.get("implementing_statutes"),
        history=trailer.get("history"),
        page_count=len({line.page for line in lines}),
    )


def _is_paragraph_start(line: TextLayerLine) -> bool:
    words = line.words
    return len(words) >= 2 and _PARAGRAPH_MARKER_RE.match(words[0].text.strip()) is not None


def _body_lines(lines: tuple[TextLayerLine, ...], *, pitch: float) -> tuple[str, ...]:
    out: list[str] = []
    paragraph: list[str] = []
    paragraph_indent: float | None = None
    table: list[TextLayerLine] = []

    def close_paragraph() -> None:
        nonlocal paragraph, paragraph_indent
        if paragraph:
            out.append(join_wrapped(paragraph))
        paragraph, paragraph_indent = [], None

    def close_table() -> None:
        nonlocal table
        if table:
            out.extend(
                " | ".join(cell for cell in row if cell) for row in _table_rows(table, pitch=pitch)
            )
        table = []

    for line in lines:
        if _is_paragraph_start(line):
            close_paragraph()
            close_table()
            marker, first_word = line.words[0], line.words[1]
            rest = line.segments[line.segments.index(first_word) :]
            paragraph = [marker.text.strip(), "".join(segment.text for segment in rest)]
            paragraph_indent = first_word.left
            continue
        if (
            paragraph
            and paragraph_indent is not None
            and len(line.words) == 1
            and abs(line.left - paragraph_indent) <= _INDENT_TOLERANCE
        ):
            paragraph.append(line.text)
            continue
        close_paragraph()
        table.append(line)
    close_paragraph()
    close_table()
    return tuple(out)


def _is_row_start(line: TextLayerLine) -> bool:
    words = line.words
    return len(words) >= 2 and _ROW_LABEL_RE.match(words[0].text.strip()) is not None


def _table_rows(lines: list[TextLayerLine], *, pitch: float) -> list[list[str]]:
    labelled = [line for line in lines if _is_row_start(line)]
    if not labelled:
        raise MontanaRulePageError(
            f"table on page {lines[0].page} has no labelled rows: {lines[0].text!r}"
        )
    if any(len(line.words) != 2 for line in labelled):
        raise MontanaRulePageError("table rows with more than two cells are not supported")
    first_row = lines.index(labelled[0])
    header, data = lines[:first_row], lines[first_row:]
    rows = _header_rows(header, pitch=pitch)

    boundary = _column_boundary(labelled)
    cells: list[list[str]] | None = None
    for line in data:
        if _is_row_start(line):
            if cells is not None:
                rows.append([join_wrapped(cell, numeral_wrap=True) for cell in cells])
            cells = [[], []]
        if cells is None:  # pragma: no cover - data starts at a labelled line
            raise MontanaRulePageError("table data before its first row")
        for word in line.words:
            cells[0 if word.left < boundary else 1].append(word.text)
    if cells is not None:
        rows.append([join_wrapped(cell, numeral_wrap=True) for cell in cells])
    return rows


def _header_rows(lines: list[TextLayerLine], *, pitch: float) -> list[list[str]]:
    groups: list[list[TextLayerLine]] = []
    for line in lines:
        previous = groups[-1][-1] if groups else None
        if (
            previous is not None
            and previous.page == line.page
            and line.top - previous.top <= pitch + _PITCH_TOLERANCE
        ):
            groups[-1].append(line)
        else:
            groups.append([line])
    rows: list[list[str]] = []
    for group in groups:
        split = [line for line in group if len(line.words) >= 2]
        if not split:
            rows.append([join_wrapped([line.text for line in group])])
            continue
        if any(len(line.words) != 2 for line in split):
            raise MontanaRulePageError(
                "table header rows with more than two cells are not supported"
            )
        boundary = _column_boundary(split)
        rows.append(
            [
                join_wrapped(
                    [word.text for line in group for word in line.words if word.left < boundary]
                ),
                join_wrapped(
                    [word.text for line in group for word in line.words if word.left >= boundary]
                ),
            ]
        )
    return rows


def _column_boundary(lines: list[TextLayerLine]) -> float:
    first_column = max(line.words[0].left for line in lines)
    second_column = min(line.words[1].left for line in lines)
    if first_column >= second_column:
        raise MontanaRulePageError("table columns overlap")
    return (first_column + second_column) / 2


def _line_pitch(lines: tuple[TextLayerLine, ...]) -> float:
    """The text's line height: the smallest gap between two lines of one page."""

    gaps = [
        later.top - earlier.top
        for earlier, later in zip(lines, lines[1:], strict=False)
        if earlier.page == later.page and later.top > earlier.top
    ]
    if not gaps:
        raise MontanaRulePageError("text layer has no two lines on one page")
    return min(gaps)


def _trailer_fields(lines: tuple[TextLayerLine, ...]) -> dict[str, str]:
    labels = {label: key for key, label in _TRAILER_LABELS}
    fields: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        first = line.words[0].text.strip()
        if first in labels:
            current = labels[first]
            if current in fields:
                raise MontanaRulePageError(f"trailer repeats {first!r}")
            fields[current] = [line.text[len(first) :]]
        elif current is None:  # pragma: no cover - the trailer opens with a label
            raise MontanaRulePageError(f"trailer line before any label: {line.text!r}")
        else:
            fields[current].append(line.text)
    return {key: join_wrapped(parts) for key, parts in fields.items()}


def parse_montana_rule_page_chrome(html: bytes) -> MontanaRulePageChrome:
    """Read the facts the page states around the PDF: version, history, links."""

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    document = soup.select_one("div.react-pdf__Document")
    if document is not None:
        document.decompose()

    accordions: dict[str, Tag] = {}
    for accordion in soup.select(".MuiAccordion-root"):
        summary = accordion.select_one(".MuiAccordionSummary-content")
        details = accordion.select_one(".MuiAccordionDetails-root")
        if summary is not None and details is not None:
            accordions[squash_text(summary.get_text(" "))] = details

    versions: list[MontanaRuleVersion] = []
    policy_ids: set[tuple[str, str]] = set()
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        match = _POLICY_HREF_RE.search(href)
        if match is None or "versionNumber" not in href:
            continue
        policy_ids.add((match["collection"], match["policy"]))
        texts = [squash_text(text) for text in link.stripped_strings]
        version_uuid = parse_qs(urlparse(href).query).get("versionNumber", [None])[0]
        versions.append(_version_from_texts(texts, version_uuid=version_uuid))
    if len(policy_ids) != 1:
        raise MontanaRulePageError(
            f"expected one policy in the version list, found {sorted(policy_ids)}"
        )
    collection_uuid, policy_uuid = next(iter(policy_ids))
    active = [version for version in versions if version.active]
    if len(active) != 1:
        raise MontanaRulePageError(f"expected one active version, found {len(active)}")

    panel = accordions.get("Rule Version")
    if panel is not None:
        stated = _version_from_texts(
            [squash_text(text) for text in panel.stripped_strings],
            version_uuid=active[0].version_uuid,
        )
        if stated != active[0]:
            raise MontanaRulePageError(
                f"rule version panel {stated} disagrees with the version list {active[0]}"
            )

    parent_section_uuid: str | None = None
    parent_section_label: str | None = None
    for link in soup.find_all("a", href=True):
        match = _SECTION_HREF_RE.search(str(link["href"]))
        label = squash_text(link.get_text(" "))
        if (
            match is not None
            and match["collection"] == collection_uuid
            and label.startswith("Subchapter")
        ):
            parent_section_uuid, parent_section_label = match["section"], label

    return MontanaRulePageChrome(
        collection_uuid=collection_uuid,
        policy_uuid=policy_uuid,
        parent_section_uuid=parent_section_uuid,
        parent_section_label=parent_section_label,
        active_version=active[0],
        versions=tuple(versions),
        contact_information=_accordion_text(accordions.get("Contact Information")),
        history=_accordion_text(accordions.get("Rule History")),
        mar_notices=_accordion_links(accordions.get("Relevant MAR Notices")),
        references=_accordion_links(accordions.get("References")),
        referenced_by=_accordion_links(accordions.get("Referenced by")),
    )


def _version_from_texts(texts: list[str], *, version_uuid: str | None) -> MontanaRuleVersion:
    words = [text for text in texts if text]
    active = "Active Version" in words
    words = [text for text in words if text not in {"Active Version", "Effective"}]
    if len(words) != 2:
        raise MontanaRulePageError(f"unexpected version entry: {texts}")
    number, span = words
    match = _EFFECTIVE_RANGE_RE.match(span)
    if match is None:
        raise MontanaRulePageError(f"unexpected effective range: {span!r}")
    return MontanaRuleVersion(
        number=number,
        version_uuid=version_uuid,
        effective_start_date=_iso_date(match["start"]),
        effective_end_date=_iso_date(match["end"]) if match["end"] else None,
        active=active,
    )


def _iso_date(value: str) -> str:
    return datetime.strptime(value, "%m/%d/%Y").date().isoformat()


def _accordion_text(details: Tag | None) -> str | None:
    if details is None:
        return None
    text = squash_text(details.get_text(" "))
    return text or None


def _accordion_links(details: Tag | None) -> tuple[MontanaRuleReference, ...]:
    """Each entry is a ``p`` label beside an icon link whose aria-label repeats it."""

    if details is None:
        return ()
    references: list[MontanaRuleReference] = []
    for link in details.find_all("a", href=True):
        label_node = link.find_previous_sibling()
        label = squash_text(label_node.get_text(" ")) if isinstance(label_node, Tag) else ""
        aria = _ARIA_REFERENCE_RE.match(squash_text(str(link.get("aria-label") or "")))
        if not label or aria is None or aria["label"] != label:
            raise MontanaRulePageError(f"reference link without a matching label: {link!r}")
        references.append(MontanaRuleReference(label=label, url=_absolute_url(str(link["href"]))))
    return tuple(references)


def _absolute_url(href: str) -> str:
    if href.startswith(("http://", "https://")):
        return href
    return f"{MONTANA_RULES_PAGE_ORIGIN}/{href.lstrip('/')}"


def montana_rule_references(document: MontanaRuleDocument) -> tuple[str, ...]:
    """Cross-references in the Montana adapter's ``references_to`` form.

    ARM rules cited in the body come first, then MCA sections named by the
    authorizing and implementing statute notes, each once, the rule itself
    excluded.
    """

    self_ref = f"us-mt/regulation/rule-{_path_token(document.citation_id)}"
    refs = [
        f"us-mt/regulation/rule-{_path_token(match.group('cite'))}"
        for match in _ARM_REF_RE.finditer(document.body)
    ]
    for note in (document.authorizing_statutes, document.implementing_statutes):
        refs.extend(
            f"us-mt/statute/{_normalize_mca_citation(match.group('cite'))}"
            for match in _MCA_REF_RE.finditer(note or "")
        )
    return tuple(ref for ref in dict.fromkeys(refs) if ref != self_ref)


def montana_rule_record(
    document: MontanaRuleDocument,
    chrome: MontanaRulePageChrome,
    *,
    citation_path: str,
    version: str,
    source_url: str,
    source_path: str,
    source_format: str,
    source_as_of: str,
    expression_date: str,
    ordinal: int = 1,
    extra_metadata: dict[str, object] | None = None,
) -> ProvisionRecord:
    """One ``rule`` row in the Montana adapter's shape, with no parent row.

    The body is the rule text: paragraphs and table rows, one per line. The
    heading is the rule name. The source notes (authorizing and implementing
    statutes, history) and the page's version facts go to metadata.
    """

    expected_leaf = f"rule-{_path_token(document.citation_id)}"
    if citation_path.rsplit("/", 1)[-1] != expected_leaf:
        raise MontanaRulePageError(
            f"citation path {citation_path!r} does not end in {expected_leaf!r}"
        )
    active = chrome.active_version
    if (
        document.history is not None
        and chrome.history is not None
        and document.history != chrome.history
    ):
        raise MontanaRulePageError("the PDF history note and the page's rule history differ")
    history = document.history or chrome.history
    metadata: dict[str, object] = {
        "kind": "rule",
        "collection_uuid": chrome.collection_uuid,
        "policy_uuid": chrome.policy_uuid,
        "policy_version_uuid": active.version_uuid,
        "version_number": active.number,
        "effective_start_date": active.effective_start_date,
        "effective_end_date": active.effective_end_date,
        "history": history,
        "source_history": [history] if history else [],
        "authorizing_statutes": document.authorizing_statutes,
        "implementing_statutes": document.implementing_statutes,
        "contact_information": chrome.contact_information,
        "references_to": list(montana_rule_references(document)),
        "mar_notices": [
            {"label": reference.label, "url": reference.url} for reference in chrome.mar_notices
        ],
        "referenced_by": [
            {"label": reference.label, "url": reference.url} for reference in chrome.referenced_by
        ],
        "rule_versions": [
            {
                "number": item.number,
                "policy_version_uuid": item.version_uuid,
                "effective_start_date": item.effective_start_date,
                "effective_end_date": item.effective_end_date,
                "active": item.active,
            }
            for item in chrome.versions
        ],
        "parent_section_uuid": chrome.parent_section_uuid,
        "parent_section_label": chrome.parent_section_label,
        "pdf_page_count": document.page_count,
        **(extra_metadata or {}),
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "", [])}
    identifiers = {
        "montana:arm_rule": document.citation_id,
        "montana:policy_uuid": chrome.policy_uuid,
    }
    if active.version_uuid:
        identifiers["montana:policy_version_uuid"] = active.version_uuid
    label = f"ARM {document.citation_id}"
    return ProvisionRecord(
        id=deterministic_provision_id(citation_path, version),
        jurisdiction="us-mt",
        document_class=DocumentClass.REGULATION.value,
        citation_path=citation_path,
        citation_label=label,
        heading=document.heading,
        body=document.body,
        version=version,
        source_url=source_url,
        source_path=source_path,
        source_id=chrome.policy_uuid,
        source_format=source_format,
        source_as_of=source_as_of,
        expression_date=expression_date,
        level=4,
        ordinal=ordinal,
        kind="rule",
        legal_identifier=label,
        identifiers=identifiers,
        metadata=metadata,
    )


def montana_accessible_html_lines(html: bytes) -> tuple[str, ...]:
    """Render an ARM accessible-HTML document in ``document_lines`` form.

    Each ``p`` of ``#documentBody`` outside a table is one line; each table row
    is its cells joined by `` | ``. Inline spans concatenate as the browser
    shows them. This is the official structured rendition of the same rule
    version, so it checks the text-layer reconstruction line for line.
    """

    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("#documentBody")
    if body is None:
        raise MontanaRulePageError("accessible HTML has no #documentBody")
    lines: list[str] = []
    for element in body.find_all(["p", "table"]):
        if element.name == "p" and element.find_parent("table") is not None:
            continue
        if element.name == "table":
            for row in element.find_all("tr"):
                cells = [
                    squash_text(cell.get_text(""))
                    for cell in row.find_all(["td", "th"], recursive=False)
                ]
                cells = [cell for cell in cells if cell]
                if cells:
                    lines.append(" | ".join(cells))
            continue
        text = squash_text(element.get_text(""))
        if text:
            lines.append(text)
    return tuple(lines)
