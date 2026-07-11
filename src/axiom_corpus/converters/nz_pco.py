"""New Zealand Parliamentary Counsel Office (PCO) legislation parser.

This module parses New Zealand legislation XML from legislation.govt.nz
and converts it to our internal models.

NZ legislation XML uses a custom DTD with these key elements:
- <act> / <bill> / <regulation> - Root elements for different legislation types
- <prov> - A provision (section) with id, label, heading
- <subprov> - Subsection within a provision
- <label-para> - Labeled paragraph (a, b, i, ii, etc.)
- <text> - Actual legislative text content
- <citation> - Cross-references to other legislation

Data sources:
- RSS feed: http://www.legislation.govt.nz/subscribe/nzpco-rss.xml
- Bulk XML: https://catalogue.data.govt.nz/dataset/new-zealand-legislation
- Web: https://www.legislation.govt.nz/

Usage:
    from axiom_corpus.converters.nz_pco import NZPCOConverter

    converter = NZPCOConverter()

    # Parse XML file
    act = converter.parse_file("path/to/act.xml")

    # Fetch from RSS feed
    items = converter.fetch_rss_feed()

    # Download a specific act
    xml_content = converter.download_legislation("act", "public", 2007, 97)
"""

import contextlib
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Literal, cast
from xml.etree import ElementTree as ET

import httpx
from pydantic import BaseModel, Field

# NZ legislation types
NZLegislationType = Literal["act", "bill", "regulation", "sop"]
NZLegislationSubtype = Literal["public", "private", "local", "government", "members", "imperial"]
NZ_LEGISLATION_SUBTYPES: tuple[NZLegislationSubtype, ...] = (
    "public",
    "private",
    "local",
    "government",
    "members",
    "imperial",
)


def _coerce_subtype(value: str | None) -> NZLegislationSubtype:
    if value in NZ_LEGISLATION_SUBTYPES:
        return cast(NZLegislationSubtype, value)
    return "public"


def _number_value(value: str | None) -> int:
    if not value:
        return 0
    match = re.match(r"\d+", value)
    return int(match.group(0)) if match else 0


def _provision_path_component(value: str) -> str:
    token = value.strip().strip("()")
    token = re.sub(r"[^0-9A-Za-z]+", "-", token).strip("-")
    return token or "unnumbered"


def render_nz_pco_legal_text(
    element: ET.Element,
    *,
    excluded: set[ET.Element] | None = None,
) -> str:
    """Render substantive PCO text once in document order.

    Labels, definitions, provisos, equations, examples, amendment text, and
    later text/tail siblings are retained. Tables use stable row/cell
    formatting. Editorial, accessibility, and amendment-history metadata are
    excluded from every caller, including schedule hierarchy bodies.
    """
    excluded_elements = excluded or set()
    skipped_tags = {
        "amends-note",
        "editorial-note",
        "history",
        "history-note",
        "ird.aids",
        "notes",
        "struckoutwords",
        "summary",
    }
    block_tags = {
        "amend",
        "def-para",
        "eqn",
        "eqn-line",
        "example",
        "heading",
        "item",
        "label-para",
        "label-para.crosshead",
        "legtable",
        "list",
        "para",
        "proviso",
        "quote",
        "row",
        "subheading",
        "subprov",
        "subprov.crosshead",
        "table",
        "tbody",
        "tgroup",
        "thead",
        "variable-def",
    }

    def clean(value: str | None) -> str:
        return " ".join((value or "").split())

    def join(parts: list[tuple[str, bool]]) -> str:
        output = ""
        prior_block = False
        for value, is_block in parts:
            value = value.strip()
            if not value:
                continue
            if output:
                separator = "\n" if prior_block or is_block else " "
                if output.rsplit("\n", 1)[-1].strip().startswith("(") and is_block:
                    separator = " "
                output += separator
            output += value
            prior_block = is_block
        return "\n".join(
            line for line in (" ".join(line.split()) for line in output.splitlines()) if line
        )

    def render(node: ET.Element) -> str:
        if node in excluded_elements or node.tag in skipped_tags:
            return ""
        if node.tag == "brk":
            return "\n"
        if node.tag == "row":
            cells = [child for child in node if child.tag == "entry"] or list(node)
            rendered_cells: list[str] = []
            for cell in cells:
                rendered_cell = " ".join(render(cell).split())
                if rendered_cell:
                    rendered_cells.append(rendered_cell)
            return " | ".join(rendered_cells)

        parts: list[tuple[str, bool]] = []
        if value := clean(node.text):
            parts.append((value, False))
        for child in node:
            child_text = render(child)
            if child_text.strip():
                parts.append((child_text, child.tag in block_tags))
            if tail := clean(child.tail):
                parts.append((tail, False))
        return join(parts)

    return render(element).strip()


@dataclass
class NZProvision:
    """A provision (section) in NZ legislation."""

    id: str  # DLM identifier, e.g., "DLM407936"
    label: str  # Section number, e.g., "1", "37A"
    heading: str  # Section title
    text: str = ""  # Direct text content
    subprovisions: list[NZProvision] = field(default_factory=list)
    paragraphs: list[NZLabeledParagraph] = field(default_factory=list)
    path_token: str | None = None  # Collision-safe token for corpus citation paths
    citation_path_suffix: str | None = None
    parent_citation_path_suffix: str | None = None
    corpus_level: int = 2
    corpus_kind: str | None = None


@dataclass
class NZLabeledParagraph:
    """A labeled paragraph (a), (b), (i), (ii), etc."""

    label: str  # e.g., "a", "i"
    text: str
    children: list[NZLabeledParagraph] = field(default_factory=list)


@dataclass
class NZLegislation:
    """Parsed NZ legislation document."""

    # Identification
    id: str  # DLM identifier
    legislation_type: NZLegislationType  # act, bill, regulation, sop
    subtype: NZLegislationSubtype  # public, private, etc.
    year: int
    number: int

    # Metadata
    title: str
    short_title: str | None = None
    assent_date: date | None = None
    commencement_date: date | None = None
    stage: str = "in-force"  # in-force, repealed, etc.

    # Content
    long_title: str = ""
    provisions: list[NZProvision] = field(default_factory=list)

    # Administrative
    administering_ministry: str | None = None
    version_date: date | None = None
    document_number_token: str | None = None
    source_document_path: str | None = None

    @property
    def citation(self) -> str:
        """Return standard NZ citation format."""
        self.legislation_type.title()
        if self.legislation_type == "sop":
            pass
        return f"{self.title} {self.year} No {self.number}"

    @property
    def url(self) -> str:
        """Return legislation.govt.nz URL."""
        document_path = self.source_document_path or (
            f"{self.legislation_type}/{self.subtype}/"
            f"{self.year}/{self.document_number_token or f'{self.number:04d}'}"
        )
        return f"https://www.legislation.govt.nz/{document_path}/latest/contents.html"


class NZRSSItem(BaseModel):
    """An item from the NZ legislation RSS feed."""

    id: str = Field(..., description="URL to the legislation")
    title: str
    published: datetime
    updated: datetime
    legislation_type: NZLegislationType
    subtype: NZLegislationSubtype
    year: int
    number: int
    status: str = Field(default="", description="New, Modified, repealed, etc.")

    model_config = {"extra": "forbid"}


class NZPCOConverter:
    """Parser for New Zealand PCO legislation XML."""

    RSS_URL = "http://www.legislation.govt.nz/subscribe/nzpco-rss.xml"
    BASE_URL = "https://www.legislation.govt.nz"
    _SCHEDULE_HIERARCHY_TAGS = frozenset({"head1", "head2", "part", "subpart"})

    def __init__(self, timeout: int = 30):
        """Initialize the converter.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Lazy-initialize HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={"User-Agent": "Axiom/1.0 (contact@axiom-foundation.org)"},
                follow_redirects=True,
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()  # pragma: no cover
            self._client = None  # pragma: no cover

    def __enter__(self) -> NZPCOConverter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # =========================================================================
    # Parsing methods
    # =========================================================================

    def parse_file(self, path: Path | str) -> NZLegislation:
        """Parse a local NZ legislation XML file.

        Args:
            path: Path to the XML file

        Returns:
            Parsed NZLegislation object
        """
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        return self.parse_xml(content)

    def parse_xml(self, xml_content: str) -> NZLegislation:
        """Parse NZ legislation XML content.

        Args:
            xml_content: Raw XML string

        Returns:
            Parsed NZLegislation object
        """
        # Parse XML
        root = ET.fromstring(xml_content)

        # Determine legislation type from root element
        root_tag = root.tag.lower()
        if root_tag == "act":
            leg_type: NZLegislationType = "act"
        elif root_tag == "bill":
            leg_type = "bill"
        elif root_tag in ("regulation", "regulation-order"):
            leg_type = "regulation"
        elif root_tag == "sop":
            leg_type = "sop"  # pragma: no cover
        else:
            # Default to act for unknown types
            leg_type = "act"

        # Extract attributes
        leg_id = root.get("id", "")
        year = int(root.get("year", "0"))
        number_text = (
            root.get("act.no")
            or root.get("bill.no")
            or root.get("regulation.no")
            or root.get("sr.no")
            or root.get("sop.no")
            or "0"
        )
        number = _number_value(number_text)
        split_letter = root.get("split.letter")
        document_number_token = f"{number_text}-{split_letter}" if split_letter else None
        subtype_raw = root.get(
            "act.type",
            root.get(
                "bill.type",
                root.get("sop.type", root.get("regulation.type", root.get("sr.type", "public"))),
            ),
        )
        subtype = _coerce_subtype(subtype_raw)
        stage = root.get("stage", "in-force")

        # Parse dates
        assent_date = self._parse_date(root.get("date.assent"))
        version_date = self._parse_date(root.get("date.as.at"))

        # Extract title from cover
        title = ""
        cover = root.find("cover")
        if cover is not None:
            title_elem = cover.find("title")
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()

            # Extract assent date if not in attributes
            if assent_date is None:
                assent_elem = cover.find("assent")
                if assent_elem is not None and assent_elem.text:
                    assent_date = self._parse_date(assent_elem.text)  # pragma: no cover

        # Extract administering ministry
        ministry = None
        ministry_elem = root.find(".//ministry")
        if ministry_elem is not None and ministry_elem.text:
            ministry = ministry_elem.text.strip()

        # Extract long title
        long_title = ""
        long_title_elem = root.find(".//long-title")
        if long_title_elem is not None:
            long_title = self._extract_text_recursive(long_title_elem)

        # Route provisions before assigning path tokens. Only the enacted body
        # and schedules are legal regions; ``end`` contains amendment skeletons
        # whose labels deliberately mirror live provisions but are not law.
        routed_provisions: list[tuple[NZProvision, ET.Element]] = []
        seen_provision_ids: set[str] = set()
        parent_map = {child: parent for parent in root.iter() for child in parent}
        legal_regions: list[tuple[ET.Element, Literal["body", "schedule"]]] = []
        body = root.find("./body")
        if body is not None:
            legal_regions.append((body, "body"))
        legal_regions.extend(
            (schedule, "schedule") for schedule in root.findall("./schedule.group/schedule")
        )
        for region, region_kind in legal_regions:
            for prov in region.iter("prov"):
                if self._is_nonoperative_or_nested_provision(
                    prov,
                    region=region,
                    parent_map=parent_map,
                ):
                    continue
                prov_id = prov.get("id", "")
                if prov_id and prov_id in seen_provision_ids:
                    continue
                parsed = self._parse_provision(prov)
                if parsed:
                    namespace = (
                        region
                        if region_kind == "body"
                        else self._schedule_provision_namespace(
                            prov,
                            schedule=region,
                            parent_map=parent_map,
                        )
                    )
                    routed_provisions.append((parsed, namespace))
                if prov_id:
                    seen_provision_ids.add(prov_id)
        self._assign_path_tokens(routed_provisions)
        provisions = [provision for provision, _ in routed_provisions]

        return NZLegislation(
            id=leg_id,
            legislation_type=leg_type,
            subtype=subtype,
            year=year,
            number=number,
            title=title,
            assent_date=assent_date,
            stage=stage,
            long_title=long_title,
            provisions=provisions,
            administering_ministry=ministry,
            version_date=version_date,
            document_number_token=document_number_token,
        )

    def _parse_provision(self, elem: ET.Element) -> NZProvision | None:
        """Parse a <prov> element."""
        prov_id = elem.get("id", "")

        # Get label
        label_elem = elem.find("label")
        label = ""
        if label_elem is not None and label_elem.text:
            label = label_elem.text.strip()

        # Get heading
        heading_elem = elem.find("heading")
        heading = ""
        if heading_elem is not None:
            heading = self._extract_text_recursive(heading_elem)

        # Render the complete body once, in source order. The structured
        # subprovision and paragraph models below are metadata views only; the
        # corpus body is never rebuilt from them.
        text = ""
        subprovisions = []
        paragraphs = []

        prov_body = elem.find("prov.body")
        if prov_body is not None:
            text = self._render_legal_text(prov_body)

            for subprov in self._immediate_structural_descendants(
                prov_body,
                "subprov",
            ):
                sub = self._parse_subprovision(subprov)
                if sub:
                    subprovisions.append(sub)

            for lp in self._immediate_structural_descendants(
                prov_body,
                "label-para",
                boundaries={"subprov"},
            ):
                parsed = self._parse_label_para(lp)
                if parsed:
                    paragraphs.append(parsed)

        if not label and not heading and not text.strip() and not subprovisions:
            return None  # pragma: no cover

        return NZProvision(
            id=prov_id,
            label=label,
            heading=heading,
            text=text.strip(),
            subprovisions=subprovisions,
            paragraphs=paragraphs,
        )

    def _is_nonoperative_or_nested_provision(
        self,
        provision: ET.Element,
        *,
        region: ET.Element,
        parent_map: dict[ET.Element, ET.Element],
    ) -> bool:
        """Reject amendment templates and provisions embedded in provisions."""
        ancestor = parent_map.get(provision)
        while ancestor is not None and ancestor is not region:
            if (
                ancestor.tag == "prov"
                or ancestor.tag == "end"
                or ancestor.tag == "skeletons"
                or ancestor.tag.startswith("skeleton.")
            ):
                return True
            ancestor = parent_map.get(ancestor)
        return ancestor is not region

    def _schedule_provision_namespace(
        self,
        provision: ET.Element,
        *,
        schedule: ET.Element,
        parent_map: dict[ET.Element, ET.Element],
    ) -> ET.Element:
        """Return the final schedule parent used as the token namespace."""
        ancestor = parent_map.get(provision)
        while ancestor is not None and ancestor is not schedule:
            if ancestor.tag in self._SCHEDULE_HIERARCHY_TAGS:
                label = ancestor.find("label")
                if (
                    (ancestor.get("id") or "").strip()
                    and label is not None
                    and any((text or "").strip() for text in label.itertext())
                ):
                    return ancestor
                # The corpus router sends children of an incomplete hierarchy
                # node to the schedule rather than inventing a container path.
                return schedule
            ancestor = parent_map.get(ancestor)
        return schedule

    def _assign_path_tokens(
        self,
        routed_provisions: list[tuple[NZProvision, ET.Element]],
    ) -> None:
        """Assign unique tokens within each final citation-path namespace."""
        routed_tokens = [
            (provision, namespace, _provision_path_component(provision.label))
            for provision, namespace in routed_provisions
        ]
        token_counts = Counter((namespace, token.lower()) for _, namespace, token in routed_tokens)
        candidates: list[tuple[NZProvision, ET.Element, str]] = []
        for provision, namespace, token in routed_tokens:
            candidate = token
            if token_counts[(namespace, token.lower())] > 1:
                candidate = f"{token}-{_provision_path_component(provision.id)}"
            candidates.append((provision, namespace, candidate))

        reserved = {(namespace, candidate.lower()) for _, namespace, candidate in candidates}
        assigned: set[tuple[ET.Element, str]] = set()
        candidate_occurrences: Counter[tuple[ET.Element, str]] = Counter()
        for provision, namespace, candidate in candidates:
            candidate_key = (namespace, candidate.lower())
            candidate_occurrences[candidate_key] += 1
            path_token = candidate
            if candidate_key in assigned:
                occurrence = candidate_occurrences[candidate_key]
                while (
                    namespace,
                    f"{candidate}-{occurrence}".lower(),
                ) in assigned | reserved:
                    occurrence += 1
                path_token = f"{candidate}-{occurrence}"
            provision.path_token = path_token
            assigned.add((namespace, path_token.lower()))

    def _parse_subprovision(self, elem: ET.Element) -> NZProvision | None:
        """Parse a <subprov> element."""
        # Get label
        label_elem = elem.find("label")
        label = ""
        if label_elem is not None and label_elem.text:
            label = label_elem.text.strip()

        label_elements = {child for child in elem if child.tag == "label"}
        text = self._render_legal_text(elem, excluded=label_elements)
        paragraphs = []

        for lp in self._immediate_structural_descendants(elem, "label-para"):
            parsed = self._parse_label_para(lp)
            if parsed:
                paragraphs.append(parsed)

        if not label and not text.strip() and not paragraphs:
            return None  # pragma: no cover

        return NZProvision(
            id=elem.get("id", ""),
            label=label,
            heading="",
            text=text.strip(),
            subprovisions=[],
            paragraphs=paragraphs,
        )

    def _parse_label_para(self, elem: ET.Element) -> NZLabeledParagraph | None:
        """Parse a <label-para> element."""
        # Get label
        label_elem = elem.find("label")
        label = ""
        if label_elem is not None and label_elem.text:
            label = label_elem.text.strip()

        child_elements = self._immediate_structural_descendants(elem, "label-para")
        excluded = set(child_elements)
        excluded.update(child for child in elem if child.tag == "label")
        text = self._render_legal_text(elem, excluded=excluded)

        children = []
        for child_lp in child_elements:
            parsed = self._parse_label_para(child_lp)
            if parsed:
                children.append(parsed)

        if not label and not text.strip():
            return None  # pragma: no cover

        return NZLabeledParagraph(
            label=label,
            text=text.strip(),
            children=children,
        )

    def _immediate_structural_descendants(
        self,
        root: ET.Element,
        tag: str,
        *,
        boundaries: set[str] | None = None,
    ) -> list[ET.Element]:
        """Return nearest structural descendants without promoting grandchildren."""
        found: list[ET.Element] = []
        boundary_tags = boundaries or set()

        def visit(node: ET.Element) -> None:
            for child in node:
                if child.tag == tag:
                    found.append(child)
                    continue
                if child.tag in boundary_tags:
                    continue
                visit(child)

        visit(root)
        return found

    def _render_legal_text(
        self,
        elem: ET.Element,
        *,
        excluded: set[ET.Element] | None = None,
    ) -> str:
        return render_nz_pco_legal_text(elem, excluded=excluded)

    def _extract_text_recursive(self, elem: ET.Element) -> str:
        """Extract all text content from an element, including nested elements."""
        return " ".join(self._render_legal_text(elem).split())

    def _extract_table_texts(self, elem: ET.Element) -> list[str]:
        """Extract table rows from a subtree as compact source text."""
        return [
            table_text
            for table in elem.findall(".//table")
            if (table_text := self._extract_table_text(table))
        ]

    def _extract_table_text(self, table: ET.Element) -> str:
        rows: list[str] = []
        for row in table.iter("row"):
            cells: list[str] = []
            for cell in row:
                cell_text = self._extract_text_recursive(cell)
                if cell_text:
                    cells.append(cell_text)
            if cells:
                rows.append(" | ".join(cells))
                continue
            row_text = self._extract_text_recursive(row)
            if row_text:
                rows.append(row_text)
        if rows:
            return "\n".join(rows)
        return self._extract_text_recursive(table)

    def _parse_date(self, date_str: str | None) -> date | None:
        """Parse a date string in YYYY-MM-DD format."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

    # =========================================================================
    # RSS feed methods
    # =========================================================================

    def fetch_rss_feed(self) -> list[NZRSSItem]:
        """Fetch and parse the NZ legislation RSS feed.

        Returns:
            List of RSS items representing recent legislation updates
        """
        response = self.client.get(self.RSS_URL)  # pragma: no cover
        response.raise_for_status()
        return self.parse_rss(response.text)  # pragma: no cover

    def parse_rss(self, xml_content: str) -> list[NZRSSItem]:
        """Parse NZ legislation RSS/Atom feed.

        Args:
            xml_content: Raw RSS XML string

        Returns:
            List of parsed RSS items
        """
        # Define namespaces
        namespaces = {
            "atom": "http://www.w3.org/2005/Atom",
        }

        root = ET.fromstring(xml_content)
        items = []

        # Try Atom format first
        for entry in root.findall(".//atom:entry", namespaces):
            try:
                item = self._parse_atom_entry(entry, namespaces)
                if item:
                    items.append(item)
            except Exception:  # pragma: no cover
                continue  # pragma: no cover

        # If no Atom entries, try RSS 2.0 format
        if not items:
            for item_elem in root.findall(".//item"):
                try:
                    item = self._parse_rss_item(item_elem)
                    if item:
                        items.append(item)
                except Exception:  # pragma: no cover
                    continue  # pragma: no cover

        return items

    def _parse_atom_entry(self, entry: ET.Element, ns: dict[str, str]) -> NZRSSItem | None:
        """Parse an Atom <entry> element."""
        # Get ID (usually the URL)
        id_elem = entry.find("atom:id", ns)
        item_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""

        # Get title
        title_elem = entry.find("atom:title", ns)
        title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

        # Get dates
        published_elem = entry.find("atom:published", ns)
        published = self._parse_iso_datetime(
            published_elem.text if published_elem is not None else None
        )

        updated_elem = entry.find("atom:updated", ns)
        updated = self._parse_iso_datetime(updated_elem.text if updated_elem is not None else None)

        if not published:
            published = updated or datetime.now()  # pragma: no cover
        if not updated:
            updated = published  # pragma: no cover

        # Parse URL to extract legislation type, subtype, year, number
        leg_type, subtype, year, number = self._parse_legislation_url(item_id)

        # Get status from content if available
        status = ""
        content_elem = entry.find("atom:content", ns)
        if content_elem is not None and content_elem.text:
            # Look for status in HTML content
            match = re.search(r"<b>Status:</b>\s*([^<]+)", content_elem.text)
            if match:
                status = match.group(1).strip()

        return NZRSSItem(
            id=item_id,
            title=title,
            published=published,
            updated=updated,
            legislation_type=leg_type,
            subtype=subtype,
            year=year,
            number=number,
            status=status,
        )

    def _parse_rss_item(self, item: ET.Element) -> NZRSSItem | None:
        """Parse an RSS 2.0 <item> element."""
        # Get link/guid
        link_elem = item.find("link")
        guid_elem = item.find("guid")
        item_id = ""
        if link_elem is not None and link_elem.text:
            item_id = link_elem.text.strip()
        elif guid_elem is not None and guid_elem.text:  # pragma: no cover
            item_id = guid_elem.text.strip()  # pragma: no cover

        # Get title
        title_elem = item.find("title")
        title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

        # Get pubDate
        pub_date_elem = item.find("pubDate")
        published = datetime.now()
        if pub_date_elem is not None and pub_date_elem.text:
            with contextlib.suppress(ValueError):
                # RFC 822 format
                published = datetime.strptime(
                    pub_date_elem.text.strip(), "%a, %d %b %Y %H:%M:%S %z"
                )

        # Parse URL
        leg_type, subtype, year, number = self._parse_legislation_url(item_id)

        return NZRSSItem(
            id=item_id,
            title=title,
            published=published,
            updated=published,
            legislation_type=leg_type,
            subtype=subtype,
            year=year,
            number=number,
        )

    def _parse_iso_datetime(self, dt_str: str | None) -> datetime | None:
        """Parse an ISO 8601 datetime string."""
        if not dt_str:
            return None  # pragma: no cover
        try:
            # Handle various ISO formats
            dt_str = dt_str.strip()
            if "T" in dt_str:
                # Try with timezone
                try:
                    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                except ValueError:  # pragma: no cover
                    pass
                # Try without timezone
                if "+" in dt_str or dt_str.endswith("Z"):  # pragma: no cover
                    dt_str = dt_str.split("+")[0].rstrip("Z")  # pragma: no cover
                return datetime.fromisoformat(dt_str)  # pragma: no cover
            else:
                return datetime.strptime(dt_str, "%Y-%m-%d")  # pragma: no cover
        except ValueError:  # pragma: no cover
            return None  # pragma: no cover

    def _parse_legislation_url(
        self, url: str
    ) -> tuple[NZLegislationType, NZLegislationSubtype, int, int]:
        """Parse legislation type, subtype, year, and number from URL.

        Args:
            url: A legislation.govt.nz URL

        Returns:
            Tuple of (type, subtype, year, number)
        """
        # Pattern: /act/public/2007/0097/...
        pattern = r"/(act|bill|regulation|sop)/(public|private|local|government|members|imperial)/(\d{4})/(\d+)"
        match = re.search(pattern, url)

        if match:
            leg_type = match.group(1)
            subtype = match.group(2)
            year = int(match.group(3))
            number = int(match.group(4))
            return (leg_type, subtype, year, number)  # type: ignore

        return ("act", "public", 0, 0)  # pragma: no cover

    # =========================================================================
    # Download methods
    # =========================================================================

    def download_legislation(
        self,
        leg_type: NZLegislationType,
        subtype: NZLegislationSubtype,
        year: int,
        number: int,
        version: str = "latest",
    ) -> str | None:
        """Download legislation XML from legislation.govt.nz.

        Note: The website uses WAF protection which may block automated access.
        For bulk downloads, use the data.govt.nz dataset instead.

        Args:
            leg_type: Type of legislation (act, bill, regulation, sop)
            subtype: Subtype (public, private, etc.)
            year: Year of legislation
            number: Legislation number
            version: Version identifier (default: "latest")

        Returns:
            XML content as string, or None if not available
        """
        # Build URL
        # Note: The Subscribe endpoint requires authentication
        url = (  # pragma: no cover
            f"{self.BASE_URL}/Subscribe/{leg_type}/{subtype}/"
            f"{year}/{number:04d}/{version}/wholeof.xml"
        )

        try:  # pragma: no cover
            response = self.client.get(url)  # pragma: no cover
            response.raise_for_status()

            # Check if we got XML (not a WAF challenge page)
            content_type = response.headers.get("content-type", "")  # pragma: no cover
            if "xml" not in content_type.lower():  # pragma: no cover
                return None  # pragma: no cover

            return response.text  # pragma: no cover
        except httpx.HTTPError:  # pragma: no cover
            return None  # pragma: no cover

    def iter_legislation_from_directory(
        self,
        directory: Path | str,
        pattern: str = "*.xml*",
    ) -> Iterator[NZLegislation]:
        """Iterate over legislation files in a local directory.

        Use this with the bulk download from data.govt.nz.

        Args:
            directory: Path to directory containing XML files
            pattern: Glob pattern for files (default: "*.xml*")

        Yields:
            Parsed NZLegislation objects
        """
        directory = Path(directory)  # pragma: no cover
        for xml_file in directory.rglob(pattern):  # pragma: no cover
            try:  # pragma: no cover
                yield self.parse_file(xml_file)  # pragma: no cover
            except Exception:  # pragma: no cover
                continue  # pragma: no cover


# Convenience function for quick parsing
def parse_nz_legislation(path_or_content: Path | str) -> NZLegislation:
    """Parse NZ legislation from a file path or XML content.

    Args:
        path_or_content: Either a path to an XML file or raw XML content

    Returns:
        Parsed NZLegislation object
    """
    converter = NZPCOConverter()  # pragma: no cover

    if isinstance(path_or_content, Path):  # pragma: no cover
        return converter.parse_file(path_or_content)  # pragma: no cover

    # Check if it looks like a file path
    if not path_or_content.strip().startswith("<?xml") and not path_or_content.strip().startswith(
        "<"
    ):  # pragma: no cover
        path = Path(path_or_content)  # pragma: no cover
        if path.exists():  # pragma: no cover
            return converter.parse_file(path)  # pragma: no cover

    return converter.parse_xml(path_or_content)  # pragma: no cover


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Parse a local file
        legislation = parse_nz_legislation(sys.argv[1])
        print(f"Title: {legislation.title}")
        print(f"Citation: {legislation.citation}")
        print(f"Type: {legislation.legislation_type}")
        print(f"Assent: {legislation.assent_date}")
        print(f"Stage: {legislation.stage}")
        print(f"Provisions: {len(legislation.provisions)}")

        if legislation.provisions:
            prov = legislation.provisions[0]
            print("\nFirst provision:")
            print(f"  Section {prov.label}: {prov.heading}")
            if prov.text:
                print(f"  Text: {prov.text[:200]}...")
    else:
        # Try to fetch RSS feed
        print("Fetching NZ legislation RSS feed...")
        with NZPCOConverter() as converter:
            try:
                items = converter.fetch_rss_feed()
                print(f"Found {len(items)} items")
                for item in items[:5]:
                    print(f"  - {item.title} ({item.legislation_type})")
            except Exception as e:
                print(f"Error fetching RSS: {e}")
