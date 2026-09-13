"""Federal US Code source adapter for source-first corpus ingestion."""

from __future__ import annotations

import re
import zlib
from collections.abc import Iterable, Iterator
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date
from io import BytesIO
from pathlib import Path, PurePosixPath
from stat import S_ISLNK
from typing import Any, cast
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, LargeZipFile, ZipFile, ZipInfo

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import ProvisionCoverageReport, compare_provision_coverage
from axiom_corpus.corpus.models import DocumentClass, ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

USC_READER_BASE = "https://uscode.house.gov/view.xhtml"
USLM_SOURCE_FORMAT = "uslm-xml"
USLM_ZIP_SOURCE_FORMAT = "uslm-xml+zip"
USLM_XML_NAMESPACE = "http://xml.house.gov/schemas/uslm/1.0"
MAX_USLM_ARCHIVE_MEMBER_BYTES = 512 * 1024 * 1024

US_CODE_TITLE_NAMES: dict[str, str] = {
    "1": "General Provisions",
    "2": "The Congress",
    "3": "The President",
    "4": "Flag and Seal, Seat of Government, and the States",
    "5": "Government Organization and Employees",
    "6": "Domestic Security",
    "7": "Agriculture",
    "8": "Aliens and Nationality",
    "9": "Arbitration",
    "10": "Armed Forces",
    "11": "Bankruptcy",
    "12": "Banks and Banking",
    "13": "Census",
    "14": "Coast Guard",
    "15": "Commerce and Trade",
    "16": "Conservation",
    "17": "Copyrights",
    "18": "Crimes and Criminal Procedure",
    "19": "Customs Duties",
    "20": "Education",
    "21": "Food and Drugs",
    "22": "Foreign Relations and Intercourse",
    "23": "Highways",
    "24": "Hospitals and Asylums",
    "25": "Indians",
    "26": "Internal Revenue Code",
    "27": "Intoxicating Liquors",
    "28": "Judiciary and Judicial Procedure",
    "29": "Labor",
    "30": "Mineral Lands and Mining",
    "31": "Money and Finance",
    "32": "National Guard",
    "33": "Navigation and Navigable Waters",
    "34": "Crime Control and Law Enforcement",
    "35": "Patents",
    "36": "Patriotic and National Observances",
    "37": "Pay and Allowances of the Uniformed Services",
    "38": "Veterans' Benefits",
    "39": "Postal Service",
    "40": "Public Buildings, Property, and Works",
    "41": "Public Contracts",
    "42": "The Public Health and Welfare",
    "43": "Public Lands",
    "44": "Public Printing and Documents",
    "45": "Railroads",
    "46": "Shipping",
    "47": "Telecommunications",
    "48": "Territories and Insular Possessions",
    "49": "Transportation",
    "50": "War and National Defense",
    "51": "National and Commercial Space Programs",
    "52": "Voting and Elections",
    "54": "National Park Service and Related Programs",
}

_TITLE_IDENTIFIER_RE = re.compile(r"/us/usc/t(?P<title>[^/]+)")
_SECTION_IDENTIFIER_RE = re.compile(r"/us/usc/t(?P<title>[^/]+)/s(?P<section>[^/]+)")
_SECTION_DESCENDANT_IDENTIFIER_RE = re.compile(
    r"/us/usc/t(?P<title>[^/]+)/s(?P<section>[^/]+)/(?P<label>[^/]+)"
)
_SECTION_NUM_RE = re.compile(r"(?:§+\s*|section\s+)?(?P<section>[0-9A-Za-z][0-9A-Za-z.-]*)", re.I)
_BODY_SKIP_TAGS = {"num", "heading", "sourceCredit", "notes", "annotations"}
_BODY_BLOCK_TAGS = {
    "p",
    "subsection",
    "paragraph",
    "subparagraph",
    "clause",
    "subclause",
    "item",
    "subitem",
    "continuation",
    "chapeau",
    "table",
}
_NESTED_PROVISION_KINDS = {
    "subsection": "subsection",
    "paragraph": "paragraph",
    "subparagraph": "subparagraph",
    "clause": "clause",
    "subclause": "subclause",
    "item": "item",
    "subitem": "subitem",
}


@dataclass(frozen=True)
class UscSection:
    title: str
    section: str
    identifier: str | None
    heading: str | None
    body: str
    references_to: tuple[str, ...]
    status: str | None = None
    subsections: tuple[UscSubsection, ...] = ()
    descendants: tuple[UscSubsection | UscNestedProvision, ...] = ()

    @property
    def citation_path(self) -> str:
        return f"us/statute/{self.title}/{self.section}"


@dataclass(frozen=True)
class UscSubsection:
    title: str
    section: str
    label: str
    identifier: str | None
    heading: str | None
    body: str
    references_to: tuple[str, ...]
    paragraphs: tuple[UscParagraph, ...] = ()
    descendants: tuple[UscParagraph | UscNestedProvision, ...] = ()

    @property
    def citation_path(self) -> str:
        return f"us/statute/{self.title}/{self.section}/{self.label}"


@dataclass(frozen=True)
class UscParagraph:
    title: str
    section: str
    subsection: str
    label: str
    identifier: str | None
    heading: str | None
    body: str
    references_to: tuple[str, ...]
    children: tuple[UscNestedProvision, ...] = ()

    @property
    def citation_path(self) -> str:
        return (
            f"us/statute/{self.title}/{self.section}/"
            f"{self.subsection}/{self.label}"
        )


@dataclass(frozen=True)
class UscNestedProvision:
    title: str
    section: str
    labels: tuple[str, ...]
    kinds: tuple[str, ...]
    kind: str
    identifier: str | None
    heading: str | None
    body: str
    references_to: tuple[str, ...]
    children: tuple[UscNestedProvision, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.kinds
            or len(self.kinds) != len(self.labels)
            or self.kind != self.kinds[-1]
        ):
            raise ValueError("USC descendant kinds must align with labels")

    @property
    def citation_path(self) -> str:
        return f"us/statute/{self.title}/{self.section}/{'/'.join(self.labels)}"

    @property
    def parent_citation_path(self) -> str:
        section_path = f"us/statute/{self.title}/{self.section}"
        if len(self.labels) == 1:
            return section_path
        return f"{section_path}/{'/'.join(self.labels[:-1])}"


@dataclass(frozen=True)
class UscTitleDocument:
    title: str
    heading: str | None
    sections: tuple[UscSection, ...]
    created_date: str | None = None
    publication_name: str | None = None

    @property
    def citation_path(self) -> str:
        return f"us/statute/{self.title}"


@dataclass(frozen=True)
class UscInventory:
    items: tuple[SourceInventoryItem, ...]
    title_count: int
    section_count: int

    @property
    def unique_citation_count(self) -> int:
        return len({item.citation_path for item in self.items})


@dataclass(frozen=True)
class UscExtractReport:
    title: str | None
    title_count: int
    section_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]


@dataclass(frozen=True)
class UscSourcePayload:
    """One local USLM input and the exact bytes retained for provenance."""

    source_path: Path
    retained_bytes: bytes
    xml_bytes: bytes
    source_format: str
    archive_member: str | None = None
    archive_member_sha256: str | None = None
    declared_title: str | None = None

    @property
    def xml_content(self) -> str:
        return decode_uslm_bytes(self.xml_bytes)


def usc_run_id(version: str, title: str | int | None = None, limit: int | None = None) -> str:
    parts = [version]
    if title is not None:
        parts.append(f"title-{_clean_title_token(title)}")
    if limit is not None:
        parts.append(f"limit-{limit}")
    return "-".join(parts)


def decode_uslm_bytes(data: bytes) -> str:
    """Decode a USLM XML payload while tolerating a UTF-8 BOM."""
    return data.decode("utf-8-sig")


def load_usc_source(
    *,
    source_xml: str | Path | None = None,
    source_archive: str | Path | None = None,
    archive_member: str | None = None,
    title: str | int | None = None,
) -> UscSourcePayload:
    """Load exactly one retained XML or official OLRC USLM ZIP input.

    Archive selection is exact when ``archive_member`` is supplied. Otherwise,
    a requested title selects a unique ``usc{title}.xml`` basename, or the
    archive must contain exactly one XML member. Archives fail closed on unsafe
    or duplicate member names, ambiguous selection, encrypted/symlink members,
    oversized members, corrupt ZIP data, and non-OLRC USLM XML content.
    """
    if (source_xml is None) == (source_archive is None):
        raise ValueError("provide exactly one of source_xml or source_archive")
    if source_xml is not None:
        if archive_member is not None:
            raise ValueError("archive_member requires source_archive")
        source_path = Path(source_xml)
        source_bytes = source_path.read_bytes()
        return UscSourcePayload(
            source_path=source_path,
            retained_bytes=source_bytes,
            xml_bytes=source_bytes,
            source_format=USLM_SOURCE_FORMAT,
        )
    return _load_usc_archive(
        Path(cast(str | Path, source_archive)),
        archive_member=archive_member,
        title=title,
    )


def _load_usc_archive(
    source_archive: Path,
    *,
    archive_member: str | None,
    title: str | int | None,
) -> UscSourcePayload:
    if source_archive.suffix.lower() != ".zip":
        raise ValueError(f"USLM source archive must be a ZIP file: {source_archive}")
    archive_bytes = source_archive.read_bytes()
    try:
        with ZipFile(BytesIO(archive_bytes)) as archive:
            members = archive.infolist()
            _validate_usc_archive_members(members)
            selected = _select_usc_archive_member(
                members,
                archive_member=archive_member,
                title=title,
            )
            if selected.file_size > MAX_USLM_ARCHIVE_MEMBER_BYTES:
                raise ValueError(
                    f"USLM archive member exceeds {MAX_USLM_ARCHIVE_MEMBER_BYTES} "
                    f"bytes: {selected.filename}"
                )
            try:
                xml_bytes = archive.read(selected)
            except (BadZipFile, RuntimeError, OSError, zlib.error) as exc:
                raise ValueError(f"cannot read USLM archive member {selected.filename!r}") from exc
    except (BadZipFile, LargeZipFile) as exc:
        raise ValueError(f"invalid USLM ZIP archive: {source_archive}") from exc

    declared_title = _validate_archived_uslm_xml(
        xml_bytes,
        member_name=selected.filename,
        requested_title=title,
    )
    return UscSourcePayload(
        source_path=source_archive,
        retained_bytes=archive_bytes,
        xml_bytes=xml_bytes,
        source_format=USLM_ZIP_SOURCE_FORMAT,
        archive_member=selected.filename,
        archive_member_sha256=sha256_bytes(xml_bytes),
        declared_title=declared_title,
    )


def _validate_usc_archive_members(members: list[ZipInfo]) -> None:
    if not members:
        raise ValueError("USLM ZIP archive is empty")
    seen: set[str] = set()
    for member in members:
        name = member.filename
        if name in seen:
            raise ValueError(f"USLM ZIP archive contains duplicate member {name!r}")
        seen.add(name)
        if not _safe_usc_archive_member_name(member.orig_filename):
            raise ValueError(f"USLM ZIP archive contains unsafe member {member.orig_filename!r}")
        if S_ISLNK(member.external_attr >> 16):
            raise ValueError(f"USLM ZIP archive contains symlink member {name!r}")
        if member.flag_bits & 0x1:
            raise ValueError(f"USLM ZIP archive contains encrypted member {name!r}")


def _safe_usc_archive_member_name(name: str) -> bool:
    if not name or "\x00" in name or "\\" in name or name.startswith("/"):
        return False
    trimmed = name[:-1] if name.endswith("/") else name
    if not trimmed or re.match(r"^[A-Za-z]:", trimmed):
        return False
    parts = trimmed.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _select_usc_archive_member(
    members: list[ZipInfo],
    *,
    archive_member: str | None,
    title: str | int | None,
) -> ZipInfo:
    files = [member for member in members if not member.is_dir()]
    if archive_member is not None:
        if not _safe_usc_archive_member_name(archive_member):
            raise ValueError(f"unsafe USLM archive member request: {archive_member!r}")
        matches = [member for member in files if member.filename == archive_member]
        if not matches:
            raise ValueError(f"USLM archive member not found: {archive_member!r}")
        selected = matches[0]
        if PurePosixPath(selected.filename).suffix.lower() != ".xml":
            raise ValueError(f"USLM archive member must be an XML file: {selected.filename!r}")
        return selected

    xml_members = [
        member for member in files if PurePosixPath(member.filename).suffix.lower() == ".xml"
    ]
    if title is not None:
        expected_name = f"usc{_clean_title_token(title)}.xml".casefold()
        title_matches = [
            member
            for member in xml_members
            if PurePosixPath(member.filename).name.casefold() == expected_name
        ]
        if len(title_matches) == 1:
            return title_matches[0]
        if len(title_matches) > 1:
            raise ValueError(
                f"USLM ZIP archive has ambiguous members for title {title}: "
                + ", ".join(sorted(member.filename for member in title_matches))
            )
    if len(xml_members) == 1:
        return xml_members[0]
    if not xml_members:
        raise ValueError("USLM ZIP archive contains no XML member")
    raise ValueError(
        "USLM ZIP archive has ambiguous XML members; specify archive_member: "
        + ", ".join(sorted(member.filename for member in xml_members))
    )


def _validate_archived_uslm_xml(
    xml_bytes: bytes,
    *,
    member_name: str,
    requested_title: str | int | None,
) -> str:
    try:
        root = ET.fromstring(decode_uslm_bytes(xml_bytes))
    except (UnicodeDecodeError, ET.ParseError) as exc:
        raise ValueError(f"USLM archive member is not valid UTF-8 XML: {member_name!r}") from exc
    if root.tag != f"{{{USLM_XML_NAMESPACE}}}uscDoc":
        raise ValueError(
            f"USLM archive member is not official OLRC USLM title XML: {member_name!r}"
        )
    try:
        declared_title = _title_from_xml(root)
    except ValueError as exc:
        raise ValueError(
            f"USLM archive member does not declare a US Code title: {member_name!r}"
        ) from exc
    if requested_title is not None:
        expected_title = _clean_title_token(requested_title)
        if declared_title != expected_title:
            raise ValueError(
                f"USLM archive member declares title {declared_title}, "
                f"not requested title {expected_title}"
            )
    return declared_title


def infer_uslm_title(xml_content: str) -> str:
    """Return the US Code title token declared by a USLM document."""
    return parse_uslm_title(xml_content).title


def parse_uslm_title(xml_content: str, title: str | int | None = None) -> UscTitleDocument:
    root = ET.fromstring(xml_content)
    title_token = _clean_title_token(title) if title is not None else _title_from_xml(root)
    title_heading = _title_heading(root, title_token)
    sections = tuple(_iter_sections(root, title_token))
    return UscTitleDocument(
        title=title_token,
        heading=title_heading,
        sections=sections,
        created_date=_created_date(root),
        publication_name=_first_local_text(root, "docPublicationName"),
    )


def _source_artifact_bytes(
    xml_content: str,
    *,
    title: str,
    allowed_citation_paths: set[str] | None,
) -> bytes:
    """Build a legacy derived excerpt; canonical extraction must retain raw bytes."""
    if allowed_citation_paths is None:
        return xml_content.encode("utf-8")

    root = ET.fromstring(xml_content)
    title_elem = _matching_title_element(root, title)
    selected_sections: list[ET.Element] = []
    for section_elem in _iter_by_local(root, "section"):
        section = _section_from_identifier(
            section_elem.get("identifier"), title
        ) or _section_from_num(section_elem)
        if not section:
            continue
        section_path = f"us/statute/{title}/{section.strip()}"
        descendant_paths = {
            path
            for path in allowed_citation_paths
            if path.startswith(f"{section_path}/")
        }
        if section_path in allowed_citation_paths:
            selected_sections.append(deepcopy(section_elem))
            continue
        if descendant_paths:
            selected_sections.append(
                _section_element_with_selected_subsections(
                    section_elem,
                    title=title,
                    section=section.strip(),
                    allowed_citation_paths=descendant_paths,
                )
            )

    if not selected_sections:
        raise ValueError(f"no US Code sections matched scoped source for title {title}")

    scoped_root = ET.Element(root.tag, root.attrib)
    for child in root:
        if _local_name(child.tag) == "meta":
            scoped_root.append(deepcopy(child))

    scoped_title = ET.Element(title_elem.tag, title_elem.attrib)
    for child in title_elem:
        if _local_name(child.tag) in {"num", "heading"}:
            scoped_title.append(deepcopy(child))
    for section_elem in selected_sections:
        scoped_title.append(section_elem)
    scoped_root.append(scoped_title)
    ET.indent(scoped_root)
    return cast(bytes, ET.tostring(scoped_root, encoding="utf-8", xml_declaration=True))


def _section_element_with_selected_subsections(
    section_elem: ET.Element,
    *,
    title: str,
    section: str,
    allowed_citation_paths: set[str],
) -> ET.Element:
    scoped_section = ET.Element(section_elem.tag, section_elem.attrib)
    section_path = f"us/statute/{title}/{section}"
    for child in section_elem:
        tag = _local_name(child.tag)
        if tag in {"num", "heading"}:
            scoped_section.append(deepcopy(child))
            continue
        if tag != "subsection":
            continue
        label = _subsection_label_from_identifier(
            child.get("identifier"), title, section
        ) or _label_from_num(child)
        if not label:
            continue
        subsection_path = f"{section_path}/{label}"
        paragraph_paths = {
            path
            for path in allowed_citation_paths
            if path.startswith(f"{subsection_path}/")
        }
        if subsection_path in allowed_citation_paths:
            scoped_section.append(deepcopy(child))
            continue
        if paragraph_paths:
            scoped_section.append(
                _subsection_element_with_selected_paragraphs(
                    child,
                    title=title,
                    section=section,
                    subsection=label,
                    allowed_citation_paths=paragraph_paths,
                )
            )
    return scoped_section


def _subsection_element_with_selected_paragraphs(
    subsection_elem: ET.Element,
    *,
    title: str,
    section: str,
    subsection: str,
    allowed_citation_paths: set[str],
) -> ET.Element:
    scoped_subsection = ET.Element(subsection_elem.tag, subsection_elem.attrib)
    subsection_path = f"us/statute/{title}/{section}/{subsection}"
    for child in subsection_elem:
        tag = _local_name(child.tag)
        if tag in {"num", "heading", "chapeau"}:
            scoped_subsection.append(deepcopy(child))
            continue
        if tag != "paragraph":
            continue
        label = _paragraph_label_from_identifier(
            child.get("identifier"), title, section, subsection
        ) or _label_from_num(child)
        if label and f"{subsection_path}/{label}" in allowed_citation_paths:
            scoped_subsection.append(deepcopy(child))
    return scoped_subsection


def _matching_title_element(root: ET.Element, title: str) -> ET.Element:
    fallback: ET.Element | None = None
    for elem in _iter_by_local(root, "title"):
        if fallback is None:
            fallback = elem
        if _title_from_identifier(elem.get("identifier")) == title:
            return elem
    if fallback is not None:
        return fallback
    raise ValueError(f"USLM XML does not contain title {title}")


def build_usc_inventory_from_xml(
    xml_content: str,
    *,
    title: str | int | None = None,
    run_id: str | None = None,
    source_sha256: str | None = None,
    source_download_url: str | None = None,
    limit: int | None = None,
    allowed_citation_paths: set[str] | None = None,
) -> UscInventory:
    document = parse_uslm_title(xml_content, title=title)
    source_path = (
        _usc_source_key(run_id, document.title)
        if run_id is not None
        else _usc_source_relative_name(document.title)
    )
    title_item = SourceInventoryItem(
        citation_path=document.citation_path,
        source_url=_usc_title_url(document.title),
        source_path=source_path,
        source_format=USLM_SOURCE_FORMAT,
        sha256=source_sha256,
        metadata=_title_metadata(document, source_download_url),
    )
    items: list[SourceInventoryItem] = []
    seen_citation_paths: set[str] = set()

    def extend_unique(candidates: Iterable[SourceInventoryItem]) -> None:
        for item in candidates:
            if item.citation_path in seen_citation_paths:
                continue
            seen_citation_paths.add(item.citation_path)
            items.append(item)

    if allowed_citation_paths is None or document.citation_path in allowed_citation_paths:
        extend_unique((title_item,))
    for section in document.sections:
        section_allowed = (
            allowed_citation_paths is None
            or section.citation_path in allowed_citation_paths
        )
        if (
            allowed_citation_paths is not None
            and not section_allowed
            and not any(
                _section_descendant_allowed(
                    descendant,
                    allowed_citation_paths=allowed_citation_paths,
                )
                for descendant in section.descendants
            )
        ):
            continue
        if section_allowed:
            extend_unique(
                (
                    SourceInventoryItem(
                        citation_path=section.citation_path,
                        source_url=_usc_section_url(section.title, section.section),
                        source_path=source_path,
                        source_format=USLM_SOURCE_FORMAT,
                        sha256=source_sha256,
                        metadata=_section_metadata(
                            section, document, source_download_url
                        ),
                    ),
                )
            )
        for descendant in section.descendants:
            if isinstance(descendant, UscSubsection):
                extend_unique(
                    _subsection_inventory_items(
                        descendant,
                        document=document,
                        section=section,
                        source_path=source_path,
                        source_sha256=source_sha256,
                        source_download_url=source_download_url,
                        allowed_citation_paths=allowed_citation_paths,
                        ancestor_allowed=section_allowed,
                    )
                )
                continue
            extend_unique(
                _nested_inventory_items(
                    descendant,
                    document=document,
                    section=section,
                    source_path=source_path,
                    source_sha256=source_sha256,
                    source_download_url=source_download_url,
                    allowed_citation_paths=allowed_citation_paths,
                    ancestor_allowed=section_allowed,
                )
            )
        if limit is not None and len(items) >= limit:
            break
    return UscInventory(
        items=tuple(items[:limit] if limit is not None else items),
        title_count=1,
        section_count=len(document.sections),
    )


def _subsection_inventory_items(
    subsection: UscSubsection,
    *,
    document: UscTitleDocument,
    section: UscSection,
    source_path: str,
    source_sha256: str | None,
    source_download_url: str | None,
    allowed_citation_paths: set[str] | None,
    ancestor_allowed: bool,
) -> list[SourceInventoryItem]:
    subsection_allowed = (
        allowed_citation_paths is None
        or ancestor_allowed
        or subsection.citation_path in allowed_citation_paths
    )
    if (
        allowed_citation_paths is not None
        and not subsection_allowed
        and not any(
            _subsection_descendant_allowed(
                descendant,
                allowed_citation_paths=allowed_citation_paths,
            )
            for descendant in subsection.descendants
        )
    ):
        return []

    items: list[SourceInventoryItem] = []
    if subsection_allowed:
        items.append(
            SourceInventoryItem(
                citation_path=subsection.citation_path,
                source_url=_usc_section_url(section.title, section.section),
                source_path=source_path,
                source_format=USLM_SOURCE_FORMAT,
                sha256=source_sha256,
                metadata=_subsection_metadata(
                    subsection,
                    section,
                    document,
                    source_download_url,
                ),
            )
        )
    for descendant in subsection.descendants:
        if isinstance(descendant, UscParagraph):
            items.extend(
                _paragraph_inventory_items(
                    descendant,
                    subsection=subsection,
                    document=document,
                    section=section,
                    source_path=source_path,
                    source_sha256=source_sha256,
                    source_download_url=source_download_url,
                    allowed_citation_paths=allowed_citation_paths,
                    ancestor_allowed=subsection_allowed,
                )
            )
            continue
        items.extend(
            _nested_inventory_items(
                descendant,
                document=document,
                section=section,
                source_path=source_path,
                source_sha256=source_sha256,
                source_download_url=source_download_url,
                allowed_citation_paths=allowed_citation_paths,
                ancestor_allowed=subsection_allowed,
            )
        )
    return items


def _paragraph_inventory_items(
    paragraph: UscParagraph,
    *,
    subsection: UscSubsection,
    document: UscTitleDocument,
    section: UscSection,
    source_path: str,
    source_sha256: str | None,
    source_download_url: str | None,
    allowed_citation_paths: set[str] | None,
    ancestor_allowed: bool,
) -> list[SourceInventoryItem]:
    paragraph_allowed = (
        allowed_citation_paths is None
        or ancestor_allowed
        or paragraph.citation_path in allowed_citation_paths
    )
    if (
        allowed_citation_paths is not None
        and not paragraph_allowed
        and not any(
            _nested_or_descendant_allowed(
                child,
                allowed_citation_paths=allowed_citation_paths,
            )
            for child in paragraph.children
        )
    ):
        return []

    items: list[SourceInventoryItem] = []
    if paragraph_allowed:
        items.append(
            SourceInventoryItem(
                citation_path=paragraph.citation_path,
                source_url=_usc_section_url(section.title, section.section),
                source_path=source_path,
                source_format=USLM_SOURCE_FORMAT,
                sha256=source_sha256,
                metadata=_paragraph_metadata(
                    paragraph,
                    subsection,
                    section,
                    document,
                    source_download_url,
                ),
            )
        )
    for child in paragraph.children:
        items.extend(
            _nested_inventory_items(
                child,
                document=document,
                section=section,
                source_path=source_path,
                source_sha256=source_sha256,
                source_download_url=source_download_url,
                allowed_citation_paths=allowed_citation_paths,
                ancestor_allowed=paragraph_allowed,
            )
        )
    return items


def _nested_inventory_items(
    provision: UscNestedProvision,
    *,
    document: UscTitleDocument,
    section: UscSection,
    source_path: str,
    source_sha256: str | None,
    source_download_url: str | None,
    allowed_citation_paths: set[str] | None,
    ancestor_allowed: bool,
) -> list[SourceInventoryItem]:
    provision_allowed = (
        allowed_citation_paths is None
        or ancestor_allowed
        or provision.citation_path in allowed_citation_paths
    )
    if (
        allowed_citation_paths is not None
        and not provision_allowed
        and not any(
            _nested_or_descendant_allowed(
                child,
                allowed_citation_paths=allowed_citation_paths,
            )
            for child in provision.children
        )
    ):
        return []

    items: list[SourceInventoryItem] = []
    if provision_allowed:
        items.append(
            SourceInventoryItem(
                citation_path=provision.citation_path,
                source_url=_usc_section_url(provision.title, provision.section),
                source_path=source_path,
                source_format=USLM_SOURCE_FORMAT,
                sha256=source_sha256,
                metadata=_nested_metadata(
                    provision,
                    section,
                    document,
                    source_download_url,
                ),
            )
        )
    for child in provision.children:
        items.extend(
            _nested_inventory_items(
                child,
                document=document,
                section=section,
                source_path=source_path,
                source_sha256=source_sha256,
                source_download_url=source_download_url,
                allowed_citation_paths=allowed_citation_paths,
                ancestor_allowed=provision_allowed,
            )
        )
    return items


def iter_usc_title_provisions(
    xml_content: str,
    *,
    version: str,
    source_path: str,
    title: str | int | None = None,
    source_as_of: str | None = None,
    expression_date: str | None = None,
    source_download_url: str | None = None,
    allowed_citation_paths: set[str] | None = None,
) -> Iterator[ProvisionRecord]:
    document = parse_uslm_title(xml_content, title=title)
    source_as_of_text = source_as_of or document.created_date or version
    expression_date_text = expression_date or source_as_of_text
    emitted_citation_paths: set[str] = set()

    def unseen(record: ProvisionRecord) -> bool:
        if record.citation_path in emitted_citation_paths:
            return False
        emitted_citation_paths.add(record.citation_path)
        return True

    title_record = _title_provision(
        document,
        version=version,
        source_path=source_path,
        source_as_of=source_as_of_text,
        expression_date=expression_date_text,
        source_download_url=source_download_url,
    )
    if (
        allowed_citation_paths is None
        or title_record.citation_path in allowed_citation_paths
    ) and unseen(title_record):
        yield title_record

    for section in document.sections:
        section_allowed = (
            allowed_citation_paths is None
            or section.citation_path in allowed_citation_paths
        )
        if (
            allowed_citation_paths is not None
            and not section_allowed
            and not any(
                _section_descendant_allowed(
                    descendant,
                    allowed_citation_paths=allowed_citation_paths,
                )
                for descendant in section.descendants
            )
        ):
            continue
        if section_allowed:
            section_record = _section_provision(
                section,
                document,
                version=version,
                source_path=source_path,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                source_download_url=source_download_url,
            )
            if unseen(section_record):
                yield section_record
        for descendant in section.descendants:
            if isinstance(descendant, UscSubsection):
                records = _iter_subsection_provisions(
                    descendant,
                    document=document,
                    section=section,
                    version=version,
                    source_path=source_path,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                    source_download_url=source_download_url,
                    allowed_citation_paths=allowed_citation_paths,
                    ancestor_allowed=section_allowed,
                )
            else:
                records = _iter_nested_provisions_as_records(
                    descendant,
                    document=document,
                    section=section,
                    version=version,
                    source_path=source_path,
                    source_as_of=source_as_of_text,
                    expression_date=expression_date_text,
                    source_download_url=source_download_url,
                    allowed_citation_paths=allowed_citation_paths,
                    ancestor_allowed=section_allowed,
                )
            for record in records:
                if unseen(record):
                    yield record


def _iter_subsection_provisions(
    subsection: UscSubsection,
    *,
    document: UscTitleDocument,
    section: UscSection,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    source_download_url: str | None,
    allowed_citation_paths: set[str] | None,
    ancestor_allowed: bool,
) -> Iterator[ProvisionRecord]:
    subsection_allowed = (
        allowed_citation_paths is None
        or ancestor_allowed
        or subsection.citation_path in allowed_citation_paths
    )
    if (
        allowed_citation_paths is not None
        and not subsection_allowed
        and not any(
            _subsection_descendant_allowed(
                descendant,
                allowed_citation_paths=allowed_citation_paths,
            )
            for descendant in subsection.descendants
        )
    ):
        return

    if subsection_allowed:
        yield _subsection_provision(
            subsection,
            section,
            document,
            version=version,
            source_path=source_path,
            source_as_of=source_as_of,
            expression_date=expression_date,
            source_download_url=source_download_url,
        )
    for descendant in subsection.descendants:
        if isinstance(descendant, UscParagraph):
            yield from _iter_paragraph_provisions(
                descendant,
                subsection=subsection,
                document=document,
                section=section,
                version=version,
                source_path=source_path,
                source_as_of=source_as_of,
                expression_date=expression_date,
                source_download_url=source_download_url,
                allowed_citation_paths=allowed_citation_paths,
                ancestor_allowed=subsection_allowed,
            )
            continue
        yield from _iter_nested_provisions_as_records(
            descendant,
            document=document,
            section=section,
            version=version,
            source_path=source_path,
            source_as_of=source_as_of,
            expression_date=expression_date,
            source_download_url=source_download_url,
            allowed_citation_paths=allowed_citation_paths,
            ancestor_allowed=subsection_allowed,
        )


def _iter_paragraph_provisions(
    paragraph: UscParagraph,
    *,
    subsection: UscSubsection,
    document: UscTitleDocument,
    section: UscSection,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    source_download_url: str | None,
    allowed_citation_paths: set[str] | None,
    ancestor_allowed: bool,
) -> Iterator[ProvisionRecord]:
    paragraph_allowed = (
        allowed_citation_paths is None
        or ancestor_allowed
        or paragraph.citation_path in allowed_citation_paths
    )
    if (
        allowed_citation_paths is not None
        and not paragraph_allowed
        and not any(
            _nested_or_descendant_allowed(
                child,
                allowed_citation_paths=allowed_citation_paths,
            )
            for child in paragraph.children
        )
    ):
        return

    if paragraph_allowed:
        yield _paragraph_provision(
            paragraph,
            subsection,
            section,
            document,
            version=version,
            source_path=source_path,
            source_as_of=source_as_of,
            expression_date=expression_date,
            source_download_url=source_download_url,
        )
    for child in paragraph.children:
        yield from _iter_nested_provisions_as_records(
            child,
            document=document,
            section=section,
            version=version,
            source_path=source_path,
            source_as_of=source_as_of,
            expression_date=expression_date,
            source_download_url=source_download_url,
            allowed_citation_paths=allowed_citation_paths,
            ancestor_allowed=paragraph_allowed,
        )


def _iter_nested_provisions_as_records(
    provision: UscNestedProvision,
    *,
    document: UscTitleDocument,
    section: UscSection,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    source_download_url: str | None,
    allowed_citation_paths: set[str] | None,
    ancestor_allowed: bool,
) -> Iterator[ProvisionRecord]:
    provision_allowed = (
        allowed_citation_paths is None
        or ancestor_allowed
        or provision.citation_path in allowed_citation_paths
    )
    if (
        allowed_citation_paths is not None
        and not provision_allowed
        and not any(
            _nested_or_descendant_allowed(
                child,
                allowed_citation_paths=allowed_citation_paths,
            )
            for child in provision.children
        )
    ):
        return

    if provision_allowed:
        yield _nested_provision_record(
            provision,
            section,
            document,
            version=version,
            source_path=source_path,
            source_as_of=source_as_of,
            expression_date=expression_date,
            source_download_url=source_download_url,
        )
    for child in provision.children:
        yield from _iter_nested_provisions_as_records(
            child,
            document=document,
            section=section,
            version=version,
            source_path=source_path,
            source_as_of=source_as_of,
            expression_date=expression_date,
            source_download_url=source_download_url,
            allowed_citation_paths=allowed_citation_paths,
            ancestor_allowed=provision_allowed,
        )


def extract_usc(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_payload: UscSourcePayload | None = None,
    source_xml: str | Path | None = None,
    source_archive: str | Path | None = None,
    archive_member: str | None = None,
    title: str | int | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    source_download_url: str | None = None,
    limit: int | None = None,
    allowed_citation_paths: set[str] | None = None,
) -> UscExtractReport:
    if source_payload is not None:
        if source_xml is not None or source_archive is not None or archive_member is not None:
            raise ValueError(
                "source_payload cannot be combined with source_xml, "
                "source_archive, or archive_member"
            )
        source = source_payload
    else:
        source = load_usc_source(
            source_xml=source_xml,
            source_archive=source_archive,
            archive_member=archive_member,
            title=title,
        )
    if title is not None and source.declared_title is not None:
        expected_title = _clean_title_token(title)
        if source.declared_title != expected_title:
            raise ValueError(
                f"USLM source payload declares title {source.declared_title}, "
                f"not requested title {expected_title}"
            )
    xml_content = source.xml_content
    document = parse_uslm_title(xml_content, title=title)
    run_id = usc_run_id(version, document.title, limit)
    source_relative_name = (
        _usc_archive_source_relative_name(source.source_path)
        if source.archive_member is not None
        else _usc_source_relative_name(document.title)
    )
    source_artifact_path = store.source_path(
        "us",
        DocumentClass.STATUTE,
        run_id,
        source_relative_name,
    )
    source_sha256 = store.write_bytes(source_artifact_path, source.retained_bytes)
    source_key = _usc_source_key_for_relative_name(run_id, source_relative_name)
    inventory = build_usc_inventory_from_xml(
        xml_content,
        title=document.title,
        run_id=run_id,
        source_sha256=source_sha256,
        source_download_url=source_download_url,
        limit=limit,
        allowed_citation_paths=allowed_citation_paths,
    )
    archive_metadata = _usc_archive_metadata(source, source_sha256)
    if archive_metadata is not None:
        inventory = replace(
            inventory,
            items=tuple(
                replace(
                    item,
                    source_path=source_key,
                    source_format=source.source_format,
                    sha256=source_sha256,
                    metadata=_merge_source_metadata(item.metadata, archive_metadata),
                )
                for item in inventory.items
            ),
        )
    inventory_citation_paths = {item.citation_path for item in inventory.items}
    records = tuple(
        record
        for record in iter_usc_title_provisions(
            xml_content,
            version=run_id,
            source_path=source_key,
            title=document.title,
            source_as_of=source_as_of,
            expression_date=(
                _date_text(expression_date, source_as_of or version)
                if expression_date is not None
                else None
            ),
            source_download_url=source_download_url,
            allowed_citation_paths=inventory_citation_paths,
        )
        if record.citation_path in inventory_citation_paths
    )
    if archive_metadata is not None:
        records = tuple(
            replace(
                record,
                source_path=source_key,
                source_format=source.source_format,
                metadata=_merge_source_metadata(record.metadata, archive_metadata),
            )
            for record in records
        )
    inventory_path = store.inventory_path("us", DocumentClass.STATUTE, run_id)
    store.write_inventory(inventory_path, inventory.items)
    provisions_path = store.provisions_path("us", DocumentClass.STATUTE, run_id)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        inventory.items,
        records,
        jurisdiction="us",
        document_class=DocumentClass.STATUTE.value,
        version=run_id,
    )
    coverage_path = store.coverage_path("us", DocumentClass.STATUTE, run_id)
    store.write_json(coverage_path, coverage.to_mapping())
    return UscExtractReport(
        title=document.title,
        title_count=1,
        section_count=inventory.section_count,
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=(source_artifact_path,),
    )


def extract_usc_directory(
    store: CorpusArtifactStore,
    *,
    version: str,
    source_dir: str | Path,
    only_title: str | int | None = None,
    source_as_of: str | None = None,
    expression_date: date | str | None = None,
    source_download_url: str | None = None,
    limit: int | None = None,
) -> UscExtractReport:
    only_title_token = _clean_title_token(only_title) if only_title is not None else None
    run_id = usc_run_id(version, only_title_token, limit) if only_title_token or limit else version
    source_files = tuple(_iter_uslm_source_files(Path(source_dir), only_title_token))
    if not source_files:
        raise ValueError(f"no USLM XML files found in {source_dir}")

    all_items: list[SourceInventoryItem] = []
    all_records: list[ProvisionRecord] = []
    source_paths: list[Path] = []
    title_count = 0
    section_count = 0
    remaining = limit

    for source_xml_path in source_files:
        source_bytes = source_xml_path.read_bytes()
        xml_content = decode_uslm_bytes(source_bytes)
        document = parse_uslm_title(xml_content)
        if only_title_token and document.title != only_title_token:
            continue
        source_artifact_path = store.source_path(
            "us",
            DocumentClass.STATUTE,
            run_id,
            _usc_source_relative_name(document.title),
        )
        source_sha256 = store.write_bytes(source_artifact_path, source_bytes)
        source_key = _usc_source_key(run_id, document.title)
        source_as_of_text = source_as_of or document.created_date or version
        expression_date_text = _date_text(expression_date, source_as_of_text)
        inventory = build_usc_inventory_from_xml(
            xml_content,
            title=document.title,
            run_id=run_id,
            source_sha256=source_sha256,
            source_download_url=source_download_url,
            limit=remaining,
        )
        allowed_citation_paths = {item.citation_path for item in inventory.items}
        records = tuple(
            record
            for record in iter_usc_title_provisions(
                xml_content,
                version=run_id,
                source_path=source_key,
                title=document.title,
                source_as_of=source_as_of_text,
                expression_date=expression_date_text,
                source_download_url=source_download_url,
                allowed_citation_paths=allowed_citation_paths,
            )
            if record.citation_path in allowed_citation_paths
        )
        all_items.extend(inventory.items)
        all_records.extend(records)
        source_paths.append(source_artifact_path)
        title_count += 1
        section_count += inventory.section_count
        if remaining is not None:
            remaining -= len(inventory.items)
            if remaining <= 0:
                break

    if not all_items:
        raise ValueError(f"no matching USLM XML files found in {source_dir}")

    inventory_path = store.inventory_path("us", DocumentClass.STATUTE, run_id)
    store.write_inventory(inventory_path, all_items)
    provisions_path = store.provisions_path("us", DocumentClass.STATUTE, run_id)
    store.write_provisions(provisions_path, all_records)
    coverage = compare_provision_coverage(
        tuple(all_items),
        tuple(all_records),
        jurisdiction="us",
        document_class=DocumentClass.STATUTE.value,
        version=run_id,
    )
    coverage_path = store.coverage_path("us", DocumentClass.STATUTE, run_id)
    store.write_json(coverage_path, coverage.to_mapping())
    return UscExtractReport(
        title=only_title_token,
        title_count=title_count,
        section_count=section_count,
        provisions_written=len(all_records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
    )


def _date_text(value: date | str | None, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value.isoformat()
    return value


def _iter_uslm_source_files(source_dir: Path, only_title: str | None) -> Iterator[Path]:
    candidates: list[tuple[tuple[int, str], Path]] = []
    for path in source_dir.glob("usc*.xml"):
        match = re.fullmatch(r"usc(?P<title>[0-9]+[a-z]?)\.xml", path.name.lower())
        if not match:
            continue
        title = _clean_title_token(match.group("title"))
        if only_title is not None and title != only_title:
            continue
        candidates.append((_title_sort_key(title), path))
    for _key, path in sorted(candidates):
        yield path


def _title_sort_key(title: str) -> tuple[int, str]:
    match = re.fullmatch(r"(?P<number>\d+)(?P<suffix>[a-z]?)", title)
    if not match:
        return (10_000, title)
    return (int(match.group("number")), match.group("suffix"))


def _clean_title_token(value: str | int) -> str:
    text = str(value).strip().lower()
    if not re.fullmatch(r"[0-9]+[a-z]?", text):
        raise ValueError(f"invalid US Code title token: {value!r}")
    return text


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _iter_by_local(elem: ET.Element, name: str) -> Iterator[ET.Element]:
    if _local_name(elem.tag) == name:
        yield elem
    for child in elem:
        yield from _iter_by_local(child, name)


def _iter_structural_sections(elem: ET.Element) -> Iterator[ET.Element]:
    """Yield corpus sections without descending into quoted amendatory sections."""
    if _local_name(elem.tag) == "section":
        yield elem
        return
    for child in elem:
        yield from _iter_structural_sections(child)


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _element_text(elem: ET.Element) -> str:
    if _local_name(elem.tag) == "table":
        return _table_to_markdown(elem)
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        child_text = _element_text(child)
        if child_text:
            parts.append(child_text)
        if child.tail:
            parts.append(child.tail)
    return _clean_text(" ".join(parts))


def _table_to_markdown(table: ET.Element) -> str:
    rows: list[list[str]] = []
    for row_elem in table.iter():
        if _local_name(row_elem.tag) != "tr":
            continue
        cells = [
            _clean_text(" ".join(cell.itertext()))
            for cell in row_elem
            if _local_name(cell.tag) in {"td", "th"}
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


def _direct_child_text(elem: ET.Element, name: str) -> str | None:
    for child in elem:
        if _local_name(child.tag) == name:
            text = _element_text(child)
            return text or None
    return None


def _title_from_xml(root: ET.Element) -> str:
    for doc_number in _iter_by_local(root, "docNumber"):
        text = _clean_text(doc_number.text)
        if text:
            return _clean_title_token(text)
    for elem in _iter_by_local(root, "title"):
        title = _title_from_identifier(elem.get("identifier"))
        if title:
            return title
    title = _title_from_identifier(root.get("identifier"))
    if title:
        return title
    raise ValueError("cannot determine US Code title from USLM XML")


def _title_from_identifier(identifier: str | None) -> str | None:
    match = _TITLE_IDENTIFIER_RE.search(identifier or "")
    if not match:
        return None
    return _clean_title_token(match.group("title"))


def _first_local_text(root: ET.Element, name: str) -> str | None:
    for elem in _iter_by_local(root, name):
        text = _element_text(elem)
        if text:
            return text
    return None


def _created_date(root: ET.Element) -> str | None:
    text = _first_local_text(root, "created")
    if not text:
        return None
    return text.split("T", 1)[0]


def _section_from_identifier(identifier: str | None, title: str) -> str | None:
    match = _SECTION_IDENTIFIER_RE.search(identifier or "")
    if not match or _clean_title_token(match.group("title")) != title:
        return None
    return match.group("section")


def _subsection_label_from_identifier(
    identifier: str | None,
    title: str,
    section: str,
) -> str | None:
    match = _SECTION_DESCENDANT_IDENTIFIER_RE.search(identifier or "")
    if (
        not match
        or _clean_title_token(match.group("title")) != title
        or match.group("section") != section
    ):
        return None
    return match.group("label")


def _paragraph_label_from_identifier(
    identifier: str | None,
    title: str,
    section: str,
    subsection: str,
) -> str | None:
    match = _SECTION_DESCENDANT_IDENTIFIER_RE.search(identifier or "")
    if (
        not match
        or _clean_title_token(match.group("title")) != title
        or match.group("section") != section
    ):
        return None
    parts = (identifier or "").split(f"/s{section}/", 1)[-1].split("/")
    if len(parts) < 2 or parts[0] != subsection:
        return None
    return parts[1]


def _nested_label_from_identifier(
    identifier: str | None,
    title: str,
    section: str,
    parent_labels: tuple[str, ...],
) -> str | None:
    prefix = f"/us/usc/t{title}/s{section}/"
    if not identifier or not identifier.startswith(prefix):
        return None
    labels = tuple(part for part in identifier.removeprefix(prefix).split("/") if part)
    if len(labels) != len(parent_labels) + 1 or labels[:-1] != parent_labels:
        return None
    return labels[-1]


def _section_from_num(elem: ET.Element) -> str | None:
    num_text = _direct_child_text(elem, "num")
    match = _SECTION_NUM_RE.search(num_text or "")
    return match.group("section").rstrip(".") if match else None


def _label_from_num(elem: ET.Element) -> str | None:
    num_text = (_direct_child_text(elem, "num") or "").strip()
    if not num_text:
        return None
    return num_text.strip("()[]{} .\u202f")


def _title_heading(root: ET.Element, title: str) -> str | None:
    fallback: str | None = None
    for elem in _iter_by_local(root, "title"):
        heading = _direct_child_text(elem, "heading")
        if not heading:
            continue
        if fallback is None:
            fallback = heading
        identifier_title = _title_from_identifier(elem.get("identifier"))
        if identifier_title == title:
            return heading
    return fallback or US_CODE_TITLE_NAMES.get(title) or f"Title {title}"


def _iter_sections(root: ET.Element, title: str) -> Iterator[UscSection]:
    seen: set[tuple[str, str | int]] = set()
    for position, elem in enumerate(_iter_structural_sections(root)):
        identifier = elem.get("identifier")
        # Quoted amendatory text can contain nested ``section`` elements whose
        # printed number is prose such as ``Sec. “(a)``. Only fall back to the
        # printed number for legacy elements that genuinely lack an identifier.
        section = (
            _section_from_identifier(identifier, title)
            if identifier
            else _section_from_num(elem)
        )
        if not section:
            continue
        section = section.strip()
        traversal_key = _source_traversal_key(elem, position)
        if traversal_key in seen:
            continue
        seen.add(traversal_key)
        descendants = tuple(_iter_section_descendants(elem, title, section))
        yield UscSection(
            title=title,
            section=section,
            identifier=identifier,
            heading=_direct_child_text(elem, "heading"),
            body=_section_body(elem),
            references_to=_extract_usc_references(elem),
            status=elem.get("status"),
            subsections=tuple(
                descendant
                for descendant in descendants
                if isinstance(descendant, UscSubsection)
            ),
            descendants=descendants,
        )


def _section_descendant_allowed(
    descendant: UscSubsection | UscNestedProvision,
    *,
    allowed_citation_paths: set[str],
) -> bool:
    if isinstance(descendant, UscSubsection):
        return _subsection_or_descendant_allowed(
            descendant,
            allowed_citation_paths=allowed_citation_paths,
        )
    return _nested_or_descendant_allowed(
        descendant,
        allowed_citation_paths=allowed_citation_paths,
    )


def _subsection_or_descendant_allowed(
    subsection: UscSubsection,
    *,
    allowed_citation_paths: set[str],
) -> bool:
    if subsection.citation_path in allowed_citation_paths:
        return True
    return any(
        _subsection_descendant_allowed(
            descendant,
            allowed_citation_paths=allowed_citation_paths,
        )
        for descendant in subsection.descendants
    )


def _subsection_descendant_allowed(
    descendant: UscParagraph | UscNestedProvision,
    *,
    allowed_citation_paths: set[str],
) -> bool:
    if isinstance(descendant, UscParagraph):
        return _paragraph_or_descendant_allowed(
            descendant,
            allowed_citation_paths=allowed_citation_paths,
        )
    return _nested_or_descendant_allowed(
        descendant,
        allowed_citation_paths=allowed_citation_paths,
    )


def _paragraph_or_descendant_allowed(
    paragraph: UscParagraph,
    *,
    allowed_citation_paths: set[str],
) -> bool:
    if paragraph.citation_path in allowed_citation_paths:
        return True
    return any(
        _nested_or_descendant_allowed(
            child,
            allowed_citation_paths=allowed_citation_paths,
        )
        for child in paragraph.children
    )


def _nested_or_descendant_allowed(
    provision: UscNestedProvision,
    *,
    allowed_citation_paths: set[str],
) -> bool:
    if provision.citation_path in allowed_citation_paths:
        return True
    return any(
        _nested_or_descendant_allowed(
            child,
            allowed_citation_paths=allowed_citation_paths,
        )
        for child in provision.children
    )


def _iter_subsections(
    section_elem: ET.Element,
    title: str,
    section: str,
) -> Iterator[UscSubsection]:
    for descendant in _iter_section_descendants(section_elem, title, section):
        if isinstance(descendant, UscSubsection):
            yield descendant


def _iter_section_descendants(
    section_elem: ET.Element,
    title: str,
    section: str,
) -> Iterator[UscSubsection | UscNestedProvision]:
    seen: set[tuple[str, str | int]] = set()
    for position, elem in enumerate(section_elem):
        tag = _local_name(elem.tag)
        if tag == "subsection":
            descendant: UscSubsection | UscNestedProvision | None = (
                _subsection_from_element(elem, title, section)
            )
        elif tag in _NESTED_PROVISION_KINDS:
            descendant = _nested_provision_from_element(
                elem,
                title=title,
                section=section,
                parent_labels=(),
                parent_kinds=(),
            )
        else:
            continue
        traversal_key = _source_traversal_key(elem, position)
        if descendant is None or traversal_key in seen:
            continue
        seen.add(traversal_key)
        yield descendant


def _subsection_from_element(
    elem: ET.Element,
    title: str,
    section: str,
) -> UscSubsection | None:
    identifier = elem.get("identifier")
    if identifier is not None:
        label = _subsection_label_from_identifier(identifier, title, section)
        if label is None:
            raise ValueError(
                f"USLM subsection identifier {identifier!r} contradicts "
                f"title {title} section {section}"
            )
    else:
        label = _label_from_num(elem)
    if not label:
        return None
    descendants = tuple(
        _iter_subsection_descendants(
            elem,
            title=title,
            section=section,
            subsection=label,
        )
    )
    return UscSubsection(
        title=title,
        section=section,
        label=label,
        identifier=identifier,
        heading=_direct_child_text(elem, "heading"),
        body=_section_body(elem),
        references_to=_extract_usc_references(elem),
        paragraphs=tuple(
            descendant
            for descendant in descendants
            if isinstance(descendant, UscParagraph)
        ),
        descendants=descendants,
    )


def _iter_paragraphs(
    subsection_elem: ET.Element,
    title: str,
    section: str,
    subsection: str,
) -> Iterator[UscParagraph]:
    for descendant in _iter_subsection_descendants(
        subsection_elem,
        title=title,
        section=section,
        subsection=subsection,
    ):
        if isinstance(descendant, UscParagraph):
            yield descendant


def _iter_subsection_descendants(
    subsection_elem: ET.Element,
    *,
    title: str,
    section: str,
    subsection: str,
) -> Iterator[UscParagraph | UscNestedProvision]:
    seen: set[tuple[str, str | int]] = set()
    for position, elem in enumerate(subsection_elem):
        tag = _local_name(elem.tag)
        if tag == "paragraph":
            descendant: UscParagraph | UscNestedProvision | None = (
                _paragraph_from_element(
                    elem,
                    title=title,
                    section=section,
                    subsection=subsection,
                )
            )
        elif tag in _NESTED_PROVISION_KINDS:
            descendant = _nested_provision_from_element(
                elem,
                title=title,
                section=section,
                parent_labels=(subsection,),
                parent_kinds=("subsection",),
            )
        else:
            continue
        traversal_key = _source_traversal_key(elem, position)
        if descendant is None or traversal_key in seen:
            continue
        seen.add(traversal_key)
        yield descendant


def _paragraph_from_element(
    elem: ET.Element,
    *,
    title: str,
    section: str,
    subsection: str,
) -> UscParagraph | None:
    identifier = elem.get("identifier")
    if identifier is not None:
        label = _paragraph_label_from_identifier(
            identifier,
            title,
            section,
            subsection,
        )
        if label is None:
            raise ValueError(
                f"USLM paragraph identifier {identifier!r} contradicts "
                f"title {title} section {section} subsection {subsection}"
            )
    else:
        label = _label_from_num(elem)
    if not label:
        return None
    return UscParagraph(
        title=title,
        section=section,
        subsection=subsection,
        label=label,
        identifier=identifier,
        heading=_direct_child_text(elem, "heading"),
        body=_section_body(elem),
        references_to=_extract_usc_references(elem),
        children=tuple(
            _iter_nested_provisions(
                elem,
                title=title,
                section=section,
                parent_labels=(subsection, label),
                parent_kinds=("subsection", "paragraph"),
            )
        ),
    )


def _iter_nested_provisions(
    parent_elem: ET.Element,
    *,
    title: str,
    section: str,
    parent_labels: tuple[str, ...],
    parent_kinds: tuple[str, ...],
) -> Iterator[UscNestedProvision]:
    seen: set[tuple[str, str | int]] = set()
    for position, elem in enumerate(parent_elem):
        provision = _nested_provision_from_element(
            elem,
            title=title,
            section=section,
            parent_labels=parent_labels,
            parent_kinds=parent_kinds,
        )
        traversal_key = _source_traversal_key(elem, position)
        if provision is None or traversal_key in seen:
            continue
        seen.add(traversal_key)
        yield provision


def _source_traversal_key(
    elem: ET.Element,
    position: int,
) -> tuple[str, str | int]:
    source_id = elem.get("id")
    if source_id:
        return ("id", source_id)
    return ("position", position)


def _nested_provision_from_element(
    elem: ET.Element,
    *,
    title: str,
    section: str,
    parent_labels: tuple[str, ...],
    parent_kinds: tuple[str, ...],
) -> UscNestedProvision | None:
    kind = _NESTED_PROVISION_KINDS.get(_local_name(elem.tag))
    if kind is None:
        return None
    identifier = elem.get("identifier")
    if identifier is not None:
        label = _nested_label_from_identifier(
            identifier,
            title,
            section,
            parent_labels,
        )
        if label is None:
            raise ValueError(
                f"USLM {kind} identifier {identifier!r} contradicts "
                f"parent {'/'.join(parent_labels)}"
            )
    else:
        label = _label_from_num(elem)
    if not label:
        return None
    labels = (*parent_labels, label)
    kinds = (*parent_kinds, kind)
    return UscNestedProvision(
        title=title,
        section=section,
        labels=labels,
        kinds=kinds,
        kind=kind,
        identifier=identifier,
        heading=_direct_child_text(elem, "heading"),
        body=_section_body(elem),
        references_to=_extract_usc_references(elem),
        children=tuple(
            _iter_nested_provisions(
                elem,
                title=title,
                section=section,
                parent_labels=labels,
                parent_kinds=kinds,
            )
        ),
    )


def _section_body(elem: ET.Element) -> str:
    parts: list[str] = []
    for child in elem:
        tag = _local_name(child.tag)
        if tag in _BODY_SKIP_TAGS:
            continue
        if tag == "content":
            parts.extend(_content_blocks(child))
            continue
        text = _element_text(child)
        if text:
            parts.append(text)
    return "\n\n".join(part for part in parts if part)


def _content_blocks(elem: ET.Element) -> list[str]:
    blocks: list[str] = []
    for child in elem:
        tag = _local_name(child.tag)
        if tag in _BODY_BLOCK_TAGS:
            text = _element_text(child)
            if text:
                blocks.append(text)
        elif tag == "content":
            blocks.extend(_content_blocks(child))
    if not blocks:
        text = _element_text(elem)
        if text:
            blocks.append(text)
    return blocks


def _extract_usc_references(elem: ET.Element) -> tuple[str, ...]:
    references: set[str] = set()
    for ref in _iter_by_local(elem, "ref"):
        href = ref.get("href")
        match = _SECTION_IDENTIFIER_RE.match(href or "")
        if match:
            references.add(
                f"us/statute/{_clean_title_token(match.group('title'))}/{match.group('section')}"
            )
    return tuple(sorted(references))


def _section_ordinal(section: str) -> int | None:
    match = re.match(r"(?P<number>\d+)(?P<suffix>.*)", section)
    if not match:
        return None
    suffix = match.group("suffix")
    suffix_offset = 0 if not suffix else 1
    return int(match.group("number")) * 10 + suffix_offset


def _subsection_ordinal(section: str, label: str) -> int | None:
    section_ordinal = _section_ordinal(section)
    label_ordinal = _label_ordinal(label)
    if section_ordinal is None or label_ordinal is None:
        return None
    return section_ordinal * 1000 + label_ordinal


def _paragraph_ordinal(section: str, subsection: str, label: str) -> int | None:
    subsection_ordinal = _subsection_ordinal(section, subsection)
    label_ordinal = _label_ordinal(label)
    if subsection_ordinal is None or label_ordinal is None:
        return None
    return subsection_ordinal * 1000 + label_ordinal


def _nested_ordinal(section: str, labels: tuple[str, ...]) -> int | None:
    ordinal = _section_ordinal(section)
    if ordinal is None:
        return None
    for label in labels:
        label_ordinal = _label_ordinal(label)
        if label_ordinal is None:
            return None
        ordinal = ordinal * 1000 + label_ordinal
    return ordinal


def _label_ordinal(label: str) -> int | None:
    if label.isdigit():
        return int(label)
    if label.isalpha():
        ordinal = 0
        for char in label.lower():
            ordinal = ordinal * 26 + (ord(char) - ord("a") + 1)
        return ordinal
    return None


def _title_ordinal(title: str) -> int | None:
    return int(title) if title.isdigit() else None


def _usc_title_url(title: str) -> str:
    return f"{USC_READER_BASE}?req=granuleid:USC-prelim-title{title}&num=0&edition=prelim"


def _usc_section_url(title: str, section: str) -> str:
    return (
        f"{USC_READER_BASE}?req=granuleid:USC-prelim-title{title}-section{section}"
        "&num=0&edition=prelim"
    )


def _usc_source_relative_name(title: str) -> str:
    return f"uslm/usc{title}.xml"


def _usc_archive_source_relative_name(source_archive: Path) -> str:
    return f"olrc/{source_archive.name}"


def _usc_source_key(run_id: str, title: str) -> str:
    return f"sources/us/{DocumentClass.STATUTE.value}/{run_id}/{_usc_source_relative_name(title)}"


def _usc_source_key_for_relative_name(run_id: str, relative_name: str) -> str:
    return f"sources/us/{DocumentClass.STATUTE.value}/{run_id}/{relative_name}"


def _usc_archive_metadata(
    source: UscSourcePayload,
    archive_sha256: str,
) -> dict[str, str] | None:
    if source.archive_member is None or source.archive_member_sha256 is None:
        return None
    return {
        "archive_sha256": archive_sha256,
        "archive_member": source.archive_member,
        "archive_member_sha256": source.archive_member_sha256,
    }


def _merge_source_metadata(
    metadata: dict[str, Any] | None,
    source_metadata: dict[str, str],
) -> dict[str, Any]:
    return {**(metadata or {}), **source_metadata}


def _usc_identifiers(
    title: str,
    section: str | None = None,
    subsection: str | None = None,
    paragraph: str | None = None,
    source_id: str | None = None,
) -> dict[str, str]:
    identifiers = {"usc:title": title}
    if section is not None:
        identifiers["usc:section"] = section
    if subsection is not None:
        identifiers["usc:subsection"] = subsection
    if paragraph is not None:
        identifiers["usc:paragraph"] = paragraph
    if source_id is not None:
        identifiers["uslm:identifier"] = source_id
    return identifiers


def _nested_identifiers(provision: UscNestedProvision) -> dict[str, str]:
    identifiers = {
        "usc:title": provision.title,
        "usc:section": provision.section,
    }
    for kind, label in zip(provision.kinds, provision.labels, strict=True):
        identifiers[f"usc:{kind}"] = label
    if provision.identifier:
        identifiers["uslm:identifier"] = provision.identifier
    return identifiers


def _title_metadata(
    document: UscTitleDocument,
    source_download_url: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "kind": "title",
        "title": document.title,
        "heading": document.heading,
        "section_count": len(document.sections),
    }
    if document.created_date:
        metadata["created_date"] = document.created_date
    if document.publication_name:
        metadata["publication_name"] = document.publication_name
    if source_download_url:
        metadata["source_download_url"] = source_download_url
    return metadata


def _section_metadata(
    section: UscSection,
    document: UscTitleDocument,
    source_download_url: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "kind": "section",
        "title": section.title,
        "section": section.section,
        "title_heading": document.heading,
        "heading": section.heading,
        "parent_citation_path": document.citation_path,
        "references_to": list(section.references_to),
    }
    if document.created_date:
        metadata["created_date"] = document.created_date
    if document.publication_name:
        metadata["publication_name"] = document.publication_name
    if section.identifier:
        metadata["identifier"] = section.identifier
    if section.status:
        metadata["status"] = section.status
    if source_download_url:
        metadata["source_download_url"] = source_download_url
    return metadata


def _subsection_metadata(
    subsection: UscSubsection,
    section: UscSection,
    document: UscTitleDocument,
    source_download_url: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "kind": "subsection",
        "title": subsection.title,
        "section": subsection.section,
        "subsection": subsection.label,
        "title_heading": document.heading,
        "section_heading": section.heading,
        "heading": subsection.heading,
        "parent_citation_path": section.citation_path,
        "references_to": list(subsection.references_to),
    }
    if document.created_date:
        metadata["created_date"] = document.created_date
    if document.publication_name:
        metadata["publication_name"] = document.publication_name
    if subsection.identifier:
        metadata["identifier"] = subsection.identifier
    if source_download_url:
        metadata["source_download_url"] = source_download_url
    return metadata


def _paragraph_metadata(
    paragraph: UscParagraph,
    subsection: UscSubsection,
    section: UscSection,
    document: UscTitleDocument,
    source_download_url: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "kind": "paragraph",
        "title": paragraph.title,
        "section": paragraph.section,
        "subsection": paragraph.subsection,
        "paragraph": paragraph.label,
        "title_heading": document.heading,
        "section_heading": section.heading,
        "subsection_heading": subsection.heading,
        "heading": paragraph.heading,
        "parent_citation_path": subsection.citation_path,
        "references_to": list(paragraph.references_to),
    }
    if document.created_date:
        metadata["created_date"] = document.created_date
    if document.publication_name:
        metadata["publication_name"] = document.publication_name
    if paragraph.identifier:
        metadata["identifier"] = paragraph.identifier
    if source_download_url:
        metadata["source_download_url"] = source_download_url
    return metadata


def _nested_metadata(
    provision: UscNestedProvision,
    section: UscSection,
    document: UscTitleDocument,
    source_download_url: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "kind": provision.kind,
        "title": provision.title,
        "section": provision.section,
        "title_heading": document.heading,
        "section_heading": section.heading,
        "heading": provision.heading,
        "parent_citation_path": provision.parent_citation_path,
        "references_to": list(provision.references_to),
    }
    for kind, label in zip(provision.kinds, provision.labels, strict=True):
        metadata[kind] = label
    if document.created_date:
        metadata["created_date"] = document.created_date
    if document.publication_name:
        metadata["publication_name"] = document.publication_name
    if provision.identifier:
        metadata["identifier"] = provision.identifier
    if source_download_url:
        metadata["source_download_url"] = source_download_url
    return metadata


def _title_provision(
    document: UscTitleDocument,
    *,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    source_download_url: str | None,
) -> ProvisionRecord:
    return ProvisionRecord(
        id=deterministic_provision_id(document.citation_path),
        jurisdiction="us",
        document_class=DocumentClass.STATUTE.value,
        citation_path=document.citation_path,
        citation_label=f"Title {document.title}, U.S. Code",
        heading=document.heading,
        body=None,
        version=version,
        source_url=_usc_title_url(document.title),
        source_path=source_path,
        source_id=f"/us/usc/t{document.title}",
        source_format=USLM_SOURCE_FORMAT,
        source_as_of=source_as_of,
        expression_date=expression_date,
        level=0,
        ordinal=_title_ordinal(document.title),
        kind="title",
        legal_identifier=f"Title {document.title}, U.S. Code",
        identifiers=_usc_identifiers(document.title),
        metadata=_title_metadata(document, source_download_url),
    )


def _section_provision(
    section: UscSection,
    document: UscTitleDocument,
    *,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    source_download_url: str | None,
) -> ProvisionRecord:
    return ProvisionRecord(
        id=deterministic_provision_id(section.citation_path),
        jurisdiction="us",
        document_class=DocumentClass.STATUTE.value,
        citation_path=section.citation_path,
        citation_label=f"{section.title} U.S.C. § {section.section}",
        heading=section.heading,
        body=section.body,
        version=version,
        source_url=_usc_section_url(section.title, section.section),
        source_path=source_path,
        source_id=section.identifier,
        source_format=USLM_SOURCE_FORMAT,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=document.citation_path,
        parent_id=deterministic_provision_id(document.citation_path),
        level=1,
        ordinal=_section_ordinal(section.section),
        kind="section",
        legal_identifier=f"{section.title} U.S.C. § {section.section}",
        identifiers=_usc_identifiers(
            section.title,
            section.section,
            source_id=section.identifier,
        ),
        metadata=_section_metadata(section, document, source_download_url),
    )


def _subsection_provision(
    subsection: UscSubsection,
    section: UscSection,
    document: UscTitleDocument,
    *,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    source_download_url: str | None,
) -> ProvisionRecord:
    legal_identifier = (
        f"{subsection.title} U.S.C. § {subsection.section}({subsection.label})"
    )
    return ProvisionRecord(
        id=deterministic_provision_id(subsection.citation_path),
        jurisdiction="us",
        document_class=DocumentClass.STATUTE.value,
        citation_path=subsection.citation_path,
        citation_label=legal_identifier,
        heading=subsection.heading,
        body=subsection.body,
        version=version,
        source_url=_usc_section_url(subsection.title, subsection.section),
        source_path=source_path,
        source_id=subsection.identifier,
        source_format=USLM_SOURCE_FORMAT,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=section.citation_path,
        parent_id=deterministic_provision_id(section.citation_path),
        level=2,
        ordinal=_subsection_ordinal(subsection.section, subsection.label),
        kind="subsection",
        legal_identifier=legal_identifier,
        identifiers=_usc_identifiers(
            subsection.title,
            subsection.section,
            subsection=subsection.label,
            source_id=subsection.identifier,
        ),
        metadata=_subsection_metadata(
            subsection, section, document, source_download_url
        ),
    )


def _paragraph_provision(
    paragraph: UscParagraph,
    subsection: UscSubsection,
    section: UscSection,
    document: UscTitleDocument,
    *,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    source_download_url: str | None,
) -> ProvisionRecord:
    legal_identifier = (
        f"{paragraph.title} U.S.C. § "
        f"{paragraph.section}({paragraph.subsection})({paragraph.label})"
    )
    return ProvisionRecord(
        id=deterministic_provision_id(paragraph.citation_path),
        jurisdiction="us",
        document_class=DocumentClass.STATUTE.value,
        citation_path=paragraph.citation_path,
        citation_label=legal_identifier,
        heading=paragraph.heading,
        body=paragraph.body,
        version=version,
        source_url=_usc_section_url(paragraph.title, paragraph.section),
        source_path=source_path,
        source_id=paragraph.identifier,
        source_format=USLM_SOURCE_FORMAT,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=subsection.citation_path,
        parent_id=deterministic_provision_id(subsection.citation_path),
        level=3,
        ordinal=_paragraph_ordinal(
            paragraph.section, paragraph.subsection, paragraph.label
        ),
        kind="paragraph",
        legal_identifier=legal_identifier,
        identifiers=_usc_identifiers(
            paragraph.title,
            paragraph.section,
            subsection=paragraph.subsection,
            paragraph=paragraph.label,
            source_id=paragraph.identifier,
        ),
        metadata=_paragraph_metadata(
            paragraph,
            subsection,
            section,
            document,
            source_download_url,
        ),
    )


def _nested_provision_record(
    provision: UscNestedProvision,
    section: UscSection,
    document: UscTitleDocument,
    *,
    version: str,
    source_path: str,
    source_as_of: str,
    expression_date: str,
    source_download_url: str | None,
) -> ProvisionRecord:
    legal_identifier = (
        f"{provision.title} U.S.C. § {provision.section}"
        + "".join(f"({label})" for label in provision.labels)
    )
    return ProvisionRecord(
        id=deterministic_provision_id(provision.citation_path),
        jurisdiction="us",
        document_class=DocumentClass.STATUTE.value,
        citation_path=provision.citation_path,
        citation_label=legal_identifier,
        heading=provision.heading,
        body=provision.body,
        version=version,
        source_url=_usc_section_url(provision.title, provision.section),
        source_path=source_path,
        source_id=provision.identifier,
        source_format=USLM_SOURCE_FORMAT,
        source_as_of=source_as_of,
        expression_date=expression_date,
        parent_citation_path=provision.parent_citation_path,
        parent_id=deterministic_provision_id(provision.parent_citation_path),
        level=1 + len(provision.labels),
        ordinal=_nested_ordinal(provision.section, provision.labels),
        kind=provision.kind,
        legal_identifier=legal_identifier,
        identifiers=_nested_identifiers(provision),
        metadata=_nested_metadata(
            provision,
            section,
            document,
            source_download_url,
        ),
    )
