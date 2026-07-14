"""Parser for CLML (Crown Legislation Markup Language) XML.

CLML is the XML format used by legislation.gov.uk for UK legislation.
Structure:
- <Legislation> root with namespaces
- <ukm:Metadata> contains Dublin Core and legislative metadata
- <Primary><Body> contains the legislation content
- <P1> = primary sections, <P2> = subsections, <P3> = paragraphs

Source: https://legislation.github.io/data-documentation/
"""

import contextlib
import re
from datetime import date
from xml.etree import ElementTree as ET

from axiom_corpus.models_uk import (
    UKAct,
    UKAmendment,
    UKCitation,
    UKPart,
    UKSection,
    UKSubsection,
)

# CLML namespaces
NAMESPACES = {
    "leg": "http://www.legislation.gov.uk/namespaces/legislation",
    "ukm": "http://www.legislation.gov.uk/namespaces/metadata",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
    "xhtml": "http://www.w3.org/1999/xhtml",
}

# CLML writes a vulgar fraction as a <Superior> (numerator) element followed by
# an <Inferior> (denominator) element, e.g. the mixed number "2 6/7 per cent" is
# ``2<Superior>6</Superior>/<Inferior>7</Inferior> per cent``. Flattening that
# subtree with ``ElementTree.itertext`` concatenates the integer part directly
# onto the numerator ("2" + "6" + "/" + "7" -> "26/7"), silently turning the
# mixed number 2 6/7 (2.857...) into the improper fraction 26/7 (3.714...). The
# encoder grounds numeric literals against the provision body, so that corruption
# can pass grounding as a wrong value -- a silent-wrong-value failure (issue #321).
#
# Audit of the other CLML uses of these tags dictates a deliberately narrow rule:
#   * <Superior> alone marks exponents (``m<Superior>2</Superior>`` for m^2) and
#     footnote / reference markers. Those MUST NOT gain a separating space, or
#     "m2" would become "m 2".
#   * legislation.gov.uk encodes a vulgar fraction as <Superior> (numerator)
#     immediately followed by <Inferior> (denominator) -- the adjacency, not the
#     tag in isolation, is the fraction signal.
# So the fraction rendering fires only for a <Superior> whose next sibling is an
# <Inferior> AND whose intervening tail is nothing but a bare solidus or U+2044
# fraction slash; any other intervening text (a footnote <Superior> followed later
# by an unrelated <Inferior>) is left alone. A lone <Superior> is emitted exactly
# as ``itertext`` would, leaving exponents and footnote markers untouched. When
# the pair does fire, a single separating space is inserted only when the numerator
# directly follows an alphanumeric (the integer part of a mixed number), and the
# numerator and denominator are always joined by one "/". For any element whose
# subtree contains no such pair, the output is byte-identical to
# ``"".join(elem.itertext())``.
_SUPERIOR_TAG = f"{{{NAMESPACES['leg']}}}Superior"
_INFERIOR_TAG = f"{{{NAMESPACES['leg']}}}Inferior"
# Literal text tolerated between the <Superior> and <Inferior> of one fraction:
# nothing, an ASCII solidus, or U+2044 FRACTION SLASH. Any other tail means the
# two elements are unrelated (e.g. a footnote <Superior> and a later <Inferior>).
_FRACTION_SEPARATORS = frozenset({"", "/", "⁄"})


def extract_text(xml_str: str) -> str:
    """Extract plain text from XML string, removing tags.

    Args:
        xml_str: XML string with potential tags

    Returns:
        Plain text with normalized whitespace
    """
    # Remove XML tags
    text = re.sub(r"<[^>]+>", " ", xml_str)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_extent(extent_str: str) -> list[str]:
    """Parse territorial extent string.

    Args:
        extent_str: String like "E+W+S+N.I."

    Returns:
        List of territory codes
    """
    if not extent_str:
        return []
    return [e.strip() for e in extent_str.split("+")]


def extract_citations(xml_str: str) -> list[str]:
    """Extract citation URIs from XML.

    Args:
        xml_str: XML string containing Citation elements

    Returns:
        List of citation URIs
    """
    # Find Citation URI attributes
    pattern = r'URI="([^"]+)"'
    matches = re.findall(pattern, xml_str)

    # Filter to legislation.gov.uk URIs
    citations = []
    seen = set()
    for uri in matches:
        if "legislation.gov.uk" in uri:
            # Extract the citation part (e.g., ukpga/2017/32)
            match = re.search(r"legislation\.gov\.uk/([a-z]+/\d+/\d+)", uri)
            if match and match.group(1) not in seen:
                seen.add(match.group(1))
                citations.append(match.group(1))

    return citations


def _get_text_content(elem: ET.Element) -> str:
    """Get all text content from an element, including nested elements.

    Equivalent to ``"".join(elem.itertext())`` except that a CLML
    <Superior>/<Inferior> vulgar-fraction pair is rendered as a spaced mixed
    number (``2 6/7``) instead of being flattened into an improper fraction
    (``26/7``). See the module-level note and issue #321. Elements whose subtree
    holds no such pair render byte-identically to ``itertext``.
    """
    parts: list[str] = []
    _append_text_content(elem, parts)
    return "".join(parts)


def _append_text_content(elem: ET.Element, parts: list[str]) -> None:
    """Depth-first ``itertext`` walk that renders Superior/Inferior fractions.

    Mirrors ``ElementTree.itertext``: emit ``elem.text``, then for each child
    emit its rendered text followed by the child's ``tail``. (``parse_section``
    always builds the tree with ``ET.fromstring``, which discards comment and
    processing-instruction nodes, so only string-tagged elements are reached.)
    """
    if elem.text:
        parts.append(elem.text)
    children = list(elem)
    index = 0
    while index < len(children):
        child = children[index]
        following = children[index + 1] if index + 1 < len(children) else None
        if _is_fraction_pair(child, following):
            _append_fraction(child, following, parts)
            if following.tail:
                parts.append(following.tail)
            index += 2
            continue
        _append_text_content(child, parts)
        if child.tail:
            parts.append(child.tail)
        index += 1


def _is_fraction_pair(numerator: ET.Element, denominator: ET.Element | None) -> bool:
    """True when the two elements are an adjacent Superior/Inferior fraction pair.

    Only a bare solidus or fraction slash may sit between them; any other tail
    (e.g. a footnote <Superior> followed later by an unrelated <Inferior>) is
    rejected so the two are not joined into a spurious fraction.
    """
    return (
        denominator is not None
        and numerator.tag == _SUPERIOR_TAG
        and denominator.tag == _INFERIOR_TAG
        and (numerator.tail is None or numerator.tail.strip() in _FRACTION_SEPARATORS)
    )


def _append_fraction(
    numerator: ET.Element, denominator: ET.Element, parts: list[str]
) -> None:
    """Render one Superior/Inferior pair as ``a/b``, space-separated from any
    preceding integer so a mixed number keeps its value (``2 6/7``, not ``26/7``).

    The numerator and denominator are read with the full text walker rather than
    ``.text`` so nested markup inside them (e.g. an ``<Emphasis>`` wrapper) is not
    silently dropped.
    """
    if _last_emitted_char(parts).isalnum():
        parts.append(" ")
    parts.append(f"{_get_text_content(numerator).strip()}/{_get_text_content(denominator).strip()}")


def _last_emitted_char(parts: list[str]) -> str:
    """Return the last non-empty character emitted so far, or ``""``."""
    for chunk in reversed(parts):
        if chunk:
            return chunk[-1]
    return ""


def _clean_text(text: str) -> str:
    """Normalize XML text content without flattening meaningful line breaks."""
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def _operative_text_parts(parent: ET.Element, ns: dict) -> list[str]:
    """Extract operative provision text, including embedded XHTML tables."""
    parts = [
        _clean_text(_get_text_content(text_elem)) for text_elem in parent.findall(".//leg:Text", ns)
    ]
    parts.extend(_extract_xhtml_tables(parent, ns))
    return [part for part in parts if part]


def _extract_xhtml_tables(parent: ET.Element, ns: dict) -> list[str]:
    tables: list[str] = []
    for table in parent.findall(".//xhtml:table", ns):
        rows: list[list[str]] = []
        for row in table.findall(".//xhtml:tr", ns):
            cells = [
                _clean_text(_get_text_content(cell))
                for cell in row.findall("./xhtml:th", ns) + row.findall("./xhtml:td", ns)
            ]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(_format_table_rows(rows))
    return tables


def _format_table_rows(rows: list[list[str]]) -> str:
    column_count = max(len(row) for row in rows)
    padded_rows = [row + [""] * (column_count - len(row)) for row in rows]

    def format_row(row: list[str]) -> str:
        return "| " + " | ".join(row) + " |"

    if len(padded_rows) == 1:
        return format_row(padded_rows[0])
    separator = "| " + " | ".join("---" for _ in range(column_count)) + " |"
    return "\n".join(
        [format_row(padded_rows[0]), separator, *(format_row(row) for row in padded_rows[1:])]
    )


def _parse_subsections(parent: ET.Element, ns: dict) -> list[UKSubsection]:
    """Parse P2/P3 elements into UKSubsection objects."""
    subsections = []

    # Find P2 elements (subsections like (a), (b))
    for p2 in parent.findall(".//leg:P2", ns):
        p2_id = p2.get("id", "")
        pnum = p2.find("leg:Pnumber", ns)
        pnum_text = pnum.text if pnum is not None else ""

        # Get text from P2para
        p2_text_parts = _operative_text_parts(p2, ns)

        # Parse nested P3 elements
        children = []
        for p3 in p2.findall(".//leg:P3", ns):
            p3_pnum = p3.find("leg:Pnumber", ns)
            p3_id = p3_pnum.text if p3_pnum is not None else ""
            p3_text_parts = _operative_text_parts(p3, ns)

            if p3_text_parts:
                children.append(
                    UKSubsection(
                        id=p3_id,
                        text=" ".join(p3_text_parts),
                    )
                )

        if p2_text_parts or children:
            subsections.append(
                UKSubsection(
                    id=pnum_text or p2_id.split("-")[-1] if p2_id else "",
                    text=" ".join(p2_text_parts),
                    children=children,
                )
            )

    return subsections


def _parse_citation_from_uri(uri: str) -> UKCitation | None:
    """Parse a UKCitation from a DocumentURI."""
    if not uri:
        return None

    schedule_paragraph_match = re.search(
        r"legislation\.gov\.uk/(?:id/)?([a-z]+)/(\d+)/(\d+)/schedule/(\d+[A-Za-z]*)/paragraph/(\d+[A-Za-z]*)",
        uri,
    )
    if schedule_paragraph_match:
        return UKCitation(
            type=schedule_paragraph_match.group(1),
            year=int(schedule_paragraph_match.group(2)),
            number=int(schedule_paragraph_match.group(3)),
            provision_kind="schedule",
            section=schedule_paragraph_match.group(4),
            paragraph=schedule_paragraph_match.group(5),
            subsection=None,
        )

    # Extract type/year/number/provision from URI
    # e.g., http://www.legislation.gov.uk/ukpga/2003/1/section/62
    #       http://www.legislation.gov.uk/uksi/2013/376/regulation/36
    #       http://www.legislation.gov.uk/uksi/2026/148/article/14
    #       http://www.legislation.gov.uk/uksi/2002/2005/schedule/2
    match = re.search(
        r"legislation\.gov\.uk/(?:id/)?([a-z]+)/(\d+)/(\d+)(?:/(section|regulation|article|schedule)/(\d+[A-Za-z]*))?",
        uri,
    )
    if match:
        return UKCitation(
            type=match.group(1),
            year=int(match.group(2)),
            number=int(match.group(3)),
            provision_kind=match.group(4),
            section=match.group(5),
            paragraph=None,
            subsection=None,
        )
    return None  # pragma: no cover


def _find_provision_root(root: ET.Element, ns: dict) -> ET.Element | None:
    """Find the provision element for section/regulation/article/schedule snippets."""
    target_paragraph = _document_target_schedule_paragraph(root, ns)
    if target_paragraph is not None:
        schedule_number, paragraph_number = target_paragraph
        for p1 in root.findall(".//leg:P1", ns):
            if _element_matches_schedule_paragraph(p1, schedule_number, paragraph_number):
                return p1

    schedule = root.find(".//leg:Schedule", ns)
    if schedule is not None and _document_targets_schedule(root, ns):
        return schedule
    p1 = root.find(".//leg:P1", ns)
    if p1 is not None:
        return p1
    return schedule


def _document_uri_candidates(root: ET.Element, ns: dict) -> list[str]:
    """Return URI values that identify the requested CLML document."""
    candidates = [root.get("DocumentURI", ""), root.get("IdURI", "")]
    identifier = root.find(".//dc:identifier", ns)
    if identifier is not None and identifier.text:
        candidates.append(identifier.text)
    return [candidate for candidate in candidates if candidate]


def _document_target_schedule_paragraph(
    root: ET.Element,
    ns: dict,
) -> tuple[str, str] | None:
    """Return the requested schedule and paragraph when the document targets one."""
    for value in _document_uri_candidates(root, ns):
        match = re.search(r"/schedule/(\d+[A-Za-z]*)/paragraph/(\d+[A-Za-z]*)", value)
        if match:
            return match.group(1), match.group(2)
    return None


def _element_matches_schedule_paragraph(
    elem: ET.Element,
    schedule_number: str,
    paragraph_number: str,
) -> bool:
    target = (
        rf"/schedule/{re.escape(schedule_number)}"
        rf"/paragraph/{re.escape(paragraph_number)}(?:/|$)"
    )
    candidates = [elem.get("DocumentURI", ""), elem.get("IdURI", "")]
    return any(re.search(target, candidate) for candidate in candidates)


def _document_targets_schedule(root: ET.Element, ns: dict) -> bool:
    """Return true when a CLML document is a schedule-level snippet."""
    return any("/schedule/" in value for value in _document_uri_candidates(root, ns))


def _p1group_title(root: ET.Element, ns: dict, provision_root: ET.Element | None) -> str | None:
    """Return the enclosing P1group title for a paragraph provision."""
    if provision_root is None:
        return None
    for group in root.findall(".//leg:P1group", ns):
        if any(p1 is provision_root for p1 in group.findall(".//leg:P1", ns)):
            title_elem = group.find("leg:Title", ns)
            if title_elem is not None:
                title = _clean_text(_get_text_content(title_elem))
                if title:
                    return title
    return None


def _parse_amendments(root: ET.Element, ns: dict) -> list[UKAmendment]:
    """Parse amendment information from Commentaries and Substitution elements."""
    amendments = []

    # Find Substitution/Addition/Repeal elements
    for sub in root.findall(".//leg:Substitution", ns):
        change_id = sub.get("ChangeId", "")
        commentary_ref = sub.get("CommentaryRef", "")

        # Try to find the referenced commentary
        if commentary_ref:
            commentary = root.find(f".//leg:Commentary[@id='{commentary_ref}']", ns)
            if commentary is not None:
                # Extract amending act from Citation
                citation_elem = commentary.find(".//leg:Citation", ns)
                amending_uri = citation_elem.get("URI", "") if citation_elem is not None else ""

                # Extract date from commentary text
                text = _get_text_content(commentary)
                date_match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
                eff_date = date.today()
                if date_match:
                    with contextlib.suppress(ValueError):
                        eff_date = date(
                            int(date_match.group(3)),
                            int(date_match.group(2)),
                            int(date_match.group(1)),
                        )

                # Extract citation path from URI
                amending_act = ""
                if amending_uri:
                    match = re.search(r"legislation\.gov\.uk/([a-z]+/\d+/\d+)", amending_uri)
                    if match:
                        amending_act = match.group(1)

                amendments.append(
                    UKAmendment(
                        type="substitution",
                        amending_act=amending_act,
                        description=text[:200] if text else None,
                        effective_date=eff_date,
                        change_id=change_id,
                    )
                )

    return amendments


def parse_section(xml_str: str) -> UKSection:
    """Parse a UK legislation section from CLML XML.

    Args:
        xml_str: XML string containing a section

    Returns:
        UKSection object
    """
    root = ET.fromstring(xml_str)

    # Use namespaces
    ns = NAMESPACES

    # Get DocumentURI - prefer the provision URI over root-level document URI.
    # Schedule snippets have a Schedule DocumentURI while the root can point to
    # the instrument/version instead of the schedule.
    provision_root = _find_provision_root(root, ns)
    doc_uri = ""
    if provision_root is not None:
        doc_uri = provision_root.get("DocumentURI", "")
    if not doc_uri:
        doc_uri = root.get("DocumentURI", "")

    # Parse citation from URI
    citation = _parse_citation_from_uri(doc_uri)
    if citation is None:
        # Try to extract from metadata
        year_elem = root.find(".//ukm:Year", ns)
        number_elem = root.find(".//ukm:Number", ns)
        year = int(year_elem.get("Value", "0")) if year_elem is not None else 0
        number = int(number_elem.get("Value", "0")) if number_elem is not None else 0

        # Try to find provision number from the provision element.
        section = None
        if provision_root is not None:
            pnum = provision_root.find("leg:Pnumber", ns)
            if pnum is None:
                pnum = provision_root.find("leg:Number", ns)
            if pnum is not None:
                section = pnum.text

        citation = UKCitation(
            type="ukpga",
            year=year,
            number=number,
            section=section,
            provision_kind="section",
            paragraph=None,
            subsection=None,
        )

    # Extract title from dc:title or section heading
    title_elem = root.find(".//dc:title", ns)
    title = title_elem.text if title_elem is not None else ""

    # If this is a section-level doc, use section number as title
    if citation.section:
        if citation.provision_segment == "schedule" and citation.paragraph:
            title = f"Schedule {citation.section} paragraph {citation.paragraph}"
            paragraph_heading = _p1group_title(root, ns, provision_root)
            if paragraph_heading:
                title += f" - {paragraph_heading}"
        else:
            title_prefix = {
                "article": "Article",
                "regulation": "Regulation",
                "schedule": "Schedule",
            }.get(citation.provision_segment, "Section")
            title = f"{title_prefix} {citation.section}"

    # Extract full text
    content_root = provision_root if provision_root is not None else root
    text_parts = _operative_text_parts(content_root, ns)
    full_text = "\n".join(text_parts)

    # Parse subsections
    body = root.find(".//leg:Body", ns)
    subsections = []
    if body is not None:
        for p1 in body.findall(".//leg:P1", ns):
            subsections.extend(_parse_subsections(p1, ns))

    # Get enactment date
    enacted_elem = root.find(".//ukm:EnactmentDate", ns)
    enacted_date = date.today()
    if enacted_elem is not None:
        date_str = enacted_elem.get("Date", "")
        if date_str:
            with contextlib.suppress(ValueError):
                enacted_date = date.fromisoformat(date_str)

    # Parse extent
    extent_str = root.get("RestrictExtent", "")
    extent = parse_extent(extent_str)

    # Parse amendments
    amendments = _parse_amendments(root, ns)

    # Extract cross-references
    references = extract_citations(xml_str)

    return UKSection(
        citation=citation,
        title=title,
        text=full_text,
        subsections=subsections,
        enacted_date=enacted_date,
        extent=extent,
        amendments=amendments,
        references_to=references,
        source_url=doc_uri,
    )


def parse_act_metadata(xml_str: str) -> UKAct:
    """Parse Act-level metadata from CLML XML.

    Args:
        xml_str: XML string containing Act metadata

    Returns:
        UKAct object
    """
    root = ET.fromstring(xml_str)
    ns = NAMESPACES

    # Get DocumentURI
    doc_uri = root.get("DocumentURI", "")

    # Parse citation from URI
    citation = _parse_citation_from_uri(doc_uri)
    if citation is None:
        year_elem = root.find(".//ukm:Year", ns)  # pragma: no cover
        number_elem = root.find(".//ukm:Number", ns)  # pragma: no cover
        year = int(year_elem.get("Value", "0")) if year_elem is not None else 0  # pragma: no cover
        number = (
            int(number_elem.get("Value", "0")) if number_elem is not None else 0
        )  # pragma: no cover
        citation = UKCitation(  # pragma: no cover
            type="ukpga",
            year=year,
            number=number,
            section=None,
            provision_kind=None,
            paragraph=None,
            subsection=None,
        )

    # Extract title
    title_elem = root.find(".//dc:title", ns)
    title = title_elem.text if title_elem is not None else ""

    # Get enactment date
    enacted_elem = root.find(".//ukm:EnactmentDate", ns)
    enacted_date = date.today()
    if enacted_elem is not None:
        date_str = enacted_elem.get("Date", "")
        if date_str:
            with contextlib.suppress(ValueError):
                enacted_date = date.fromisoformat(date_str)

    # Get commencement date
    commencement_elem = root.find(".//ukm:ComingIntoForce/ukm:DateTime", ns)
    commencement_date = None
    if commencement_elem is not None:
        date_str = commencement_elem.get("Date", "")
        if date_str:
            with contextlib.suppress(ValueError):
                commencement_date = date.fromisoformat(date_str)

    # Get section count from NumberOfProvisions
    section_count = None
    provisions = root.get("NumberOfProvisions")
    if provisions:
        with contextlib.suppress(ValueError):
            section_count = int(provisions)

    # Parse parts
    parts = []
    for part_elem in root.findall(".//leg:Part", ns):
        number_elem = part_elem.find("leg:Number", ns)
        title_elem = part_elem.find("leg:Title", ns)
        if number_elem is not None or title_elem is not None:
            parts.append(
                UKPart(
                    number=number_elem.text if number_elem is not None else "",
                    title=title_elem.text if title_elem is not None else "",
                )
            )

    # Parse extent
    extent_str = root.get("RestrictExtent", "")
    extent = parse_extent(extent_str)

    return UKAct(
        citation=citation,
        title=title,
        enacted_date=enacted_date,
        commencement_date=commencement_date,
        parts=parts,
        section_count=section_count,
        extent=extent,
        source_url=doc_uri,
    )
