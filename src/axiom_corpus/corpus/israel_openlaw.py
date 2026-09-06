"""Israeli consolidated-statute extraction from the ספר החוקים הפתוח (OpenLaw) HTML.

The Knesset National Legislation Database renders client-side and its
``לחוק המלא`` link points at the he.wikisource.org ספר החוקים הפתוח project, so
that project's server-rendered HTML is the reachable consolidation for this
pilot.  It is a *secondary* consolidation: statutes themselves carry no
copyright (Copyright Act 5768-2007 §6), but the editorial apparatus — amendment
history brackets, cross-reference notes, historical rate tables — belongs to the
project and is not statutory text.  This adapter keeps that apparatus out of
provision bodies and records it in provision metadata instead.

Like the Armenian ARLIS adapter, extraction is local-file first: a manifest binds
every input to its official URL, an immutable SHA-256, an expression date with a
declared basis, and the expected structural counts, and every source is fully
parsed before the first artifact is written.

Structure of the source markup (``div#law-content``):

* ``div.law-number.tc_.selflink`` with ``id="סעיף_<ident>"`` opens a section;
  the same class with a dotted id (``סעיף_2.1``) is a *sub-item* anchor whose
  text belongs to the enclosing section, not to a new one.  Treating those as
  section starts is the false-split failure this adapter is built to avoid.
* ``id="לוח_<schedule>_פרט_<item>"`` opens a schedule item.
* ``div.law-desc`` carries the section heading, ``div.law-main`` the body.
* ``h1.law-part`` / ``h2.law-section`` / ``h3.law-subsection`` are the
  חלק / פרק (or לוח) / סימן navigation levels.
* ``h4.law-subsubsection`` is a subheading under one of those: the enabling
  section caption a schedule prints under its own name, and the applicability
  labels that tell two identically-headed tables apart.  Both are statutory and
  both stay in the body at their printed position.
* ``span.law-note`` is OpenLaw's apparatus nearly everywhere it appears — amendment
  history in square brackets, the project's own indexed-amount glosses, its footnote
  letters — and is kept out of provision bodies.  Four parenthesised shapes are not
  apparatus and do reach a body, because deleting them changes what the row says: a
  repeal, deletion or expiry marker on a subsection; a colon-terminated qualifier
  saying which version a text is or when it applies; a note inside a table cell (a
  temporary-order substitution for that cell's value); and a substitution printed
  inline in running text (``(בשנים 2025–2026: 7.85%)`` against NII §340א's 6.25%),
  which states the rate in force for the window it names.  Each is also reported in
  ``metadata.statutory_notes``.  See :func:`_statutory_label_positions`.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Self, cast
from urllib.parse import unquote, urlparse

import yaml
from bs4 import BeautifulSoup
from bs4.element import NavigableString, PageElement, Tag

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import (
    ProvisionCoverageReport,
    compare_provision_coverage,
)
from axiom_corpus.corpus.models import (
    DocumentClass,
    ProvisionRecord,
    SourceInventoryItem,
)
from axiom_corpus.corpus.supabase import deterministic_provision_id

ISRAEL_OPENLAW_SOURCE_FORMAT = "he.wikisource.org-openlaw-consolidated-html"
ISRAEL_OPENLAW_JURISDICTION = "il"
ISRAEL_OPENLAW_DOCUMENT_CLASS = DocumentClass.STATUTE.value
ISRAEL_OPENLAW_LANGUAGE = "he"
ISRAEL_OPENLAW_SOURCE_AUTHORITY = "ספר החוקים הפתוח (he.wikisource.org OpenLaw project)"
# Two tiers, because the evidence differs per act.  The Knesset National
# Legislation Database's "לחוק המלא" link was followed to the Wikisource page for
# the Income Tax Ordinance; the same check is still pending for the National
# Insurance Law, so that act may not claim the stronger tier.
ISRAEL_OPENLAW_SOURCE_TIERS = frozenset(
    {"consolidation-knesset-linked", "consolidation-wikisource"}
)
ISRAEL_OPENLAW_HOST = "he.wikisource.org"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ASCII_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")
# Removing an inline editorial note leaves the space that preceded it stranded
# in front of the punctuation that followed it.  HTML whitespace is not
# semantic, so collapse it the same way runs of spaces are collapsed.
_SPACE_BEFORE_PUNCTUATION_RE = re.compile(r" +(?=[.,;:])")

_SECTION_ANCHOR_PREFIX = "סעיף_"
# The National Insurance Law calls its schedules לוח, the Ordinance תוספת.
_SCHEDULE_ANCHOR_PREFIXES = ("לוח_", "תוספת_")
_SCHEDULE_ITEM_INFIX = "_פרט_"
_TABLE_OF_CONTENTS_HEADING = "תוכן עניינים"
_SCHEDULE_HEADING_RE = re.compile(r"^(?:לוח|תוספת)\s+(?P<rest>.+)$")
_PARENTHETICAL_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")
# Ordinance schedules are named by feminine ordinal word — "תוספת ראשונה א׳"
# is the anchor space's תוספת_1א — so the word carries the number.
_HEBREW_ORDINAL_WORDS = {
    "ראשונה": 1,
    "שניה": 2,
    "שנייה": 2,
    "שלישית": 3,
    "רביעית": 4,
    "חמישית": 5,
    "ששית": 6,
    "שישית": 6,
    "שביעית": 7,
    "שמינית": 8,
    "תשיעית": 9,
    "עשירית": 10,
}
# MediaWiki stops expanding templates once a page exceeds its 2 MiB
# post-expand include budget, and says so in an HTML comment.  The Ordinance
# page hits that ceiling exactly, so its full-page render silently loses the
# tail of the law.  Ingesting past this marker would land truncated text.
_TRUNCATION_MARKER = "WARNING: template omitted, post-expand include size too large"
# The Wikitext disclaimer block the project appends to every law page.
_DISCLAIMER_CLASS = "graytext"
# Opening markup of a section anchor, used to find the last whole section
# before a truncated render stops expanding templates.
# The trailing space matters: it distinguishes a section anchor
# (class "law-number tc_ selflink") from the subsection markers
# "law-number2".."law-number6" that appear inside a section body.
_SECTION_ANCHOR_OPEN = '<div class="law-number '
_HEBREW_PUNCTUATION = "״׳\"'"
_ORIGIN_MARKER_RE = re.compile(r"\[(?P<marker>\d+[א-ת]*)\]\s*$")
# OpenLaw styles a repealed/expired/deleted section's own status line as a note.
# That line is how the consolidated text reads for that section, not commentary,
# so it becomes the provision body with the status recorded in metadata.
_STATUS_MARKER_RE = re.compile(r"^\(\s*(?P<status>בוטל|פקע|נמחק)\b")

# The same statements of legal effect, in every printed form — masculine, feminine and
# plural.  A note-only block matching _STATUS_MARKER_RE becomes a whole section's body
# and sets ``operative: false``; this wider pattern keeps the identical marker in the
# body when it sits on a subsection or paragraph of a section that is still in force.
_STATUTORY_STATUS_RE = re.compile(r"^\(\s*(?:בוטל|בוטלה|בוטלו|פקע|פקעה|פקעו|נמחק|נמחקה|נמחקו)\b")

# A note that names a temporary order (הוראת שעה) or instructs one wording to be read
# in place of another (במקום) states legal effect wherever it is printed, so neither
# needs to sit in a table or end with a colon to reach a body.
_TEMPORARY_ORDER_RE = re.compile(r"הוראת שעה")
_SUBSTITUTED_WORDING_RE = re.compile(r"במקום")
# OpenLaw's own value glosses, which are never body text: the base year of an indexed
# amount and the figures the project has indexed it to since
# (``(נקוב לשנת 2015; בשנת 2023, 141,840 ש״ח)``, ``(נכון לשנת 2016)``), and the average
# wage it supplies for a definition.  The citation scheme takes current-year regulated
# amounts only from official publications captured under ``il/policies/`` — never from
# this secondary consolidation — so a gloss that replaces a shekel figure stays out.
_INDEXATION_GLOSS_RE = re.compile(r"^\(\s*(?:נקוב|נכון)\b")
_SHEKEL_UNIT_RE = re.compile(r"ש[״\"]ח")

# Hebrew numeral values, as used for section suffixes (gematria).  Section
# suffixes are written without final forms, so only the base letters appear.
_HEBREW_NUMERALS: dict[str, int] = {
    "א": 1,
    "ב": 2,
    "ג": 3,
    "ד": 4,
    "ה": 5,
    "ו": 6,
    "ז": 7,
    "ח": 8,
    "ט": 9,
    "י": 10,
    "כ": 20,
    "ל": 30,
    "מ": 40,
    "נ": 50,
    "ס": 60,
    "ע": 70,
    "פ": 80,
    "צ": 90,
    "ק": 100,
    "ר": 200,
    "ש": 300,
    "ת": 400,
}
_HEBREW_FINAL_FORMS = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}
_HEBREW_LETTER_RE = re.compile(r"[א-ת]+")
_DIGIT_RUN_RE = re.compile(r"\d+")
_IDENT_TOKEN_RE = re.compile(r"\d+|[א-ת]+")

_NAV_LEVELS = {"part": 1, "chapter": 2, "schedule": 2, "sign": 3}


def hebrew_numeral_value(letters: str) -> int:
    """Return the gematria value of a Hebrew numeral run such as ``יא``."""
    if not letters:
        raise ValueError("empty Hebrew numeral")
    total = 0
    for char in letters:
        base = _HEBREW_FINAL_FORMS.get(char, char)
        value = _HEBREW_NUMERALS.get(base)
        if value is None:
            raise ValueError(f"not a Hebrew numeral letter: {char!r} in {letters!r}")
        total += value
    return total


def latin_ordinal_slug(value: int) -> str:
    """Return the ordinal-position slug for ``value``: 1->a, 26->z, 27->aa.

    ``ops/il-lane/CITATION-SCHEME.md`` fixes 1..12 (א->a … יב->l) and elides the
    rest.  Bijective base-26 is the total, collision-free continuation of that
    sequence; the National Insurance Law needs it, reaching לד (34) -> ``ah``.
    """
    if value < 1:
        raise ValueError(f"ordinal slug requires a positive value, got {value}")
    out = ""
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        out = chr(ord("a") + remainder) + out
    return out


def hebrew_suffix_slug(letters: str) -> str:
    """Transliterate one Hebrew suffix run by ordinal: ב->b, י->j, יא->k."""
    return latin_ordinal_slug(hebrew_numeral_value(letters))


def schedule_heading_ident(rest: str) -> str:
    """Return the anchor-space identifier for a schedule heading's remainder.

    ``לוח ט״ז1`` -> ``טז1``; ``תוספת ראשונה א׳`` -> ``1א``; ``תוספת שניה`` -> ``2``.
    The Ordinance names schedules by ordinal word and anchors them by number, so
    the word has to be resolved for the heading and its items to agree.
    """
    cleaned = _PARENTHETICAL_SUFFIX_RE.sub("", unicodedata.normalize("NFC", rest)).strip()
    if not cleaned:
        raise ValueError("empty schedule heading")
    tokens = cleaned.split()
    ordinal = _HEBREW_ORDINAL_WORDS.get(_strip_hebrew_punctuation(tokens[0]))
    if ordinal is None:
        return _strip_hebrew_punctuation(cleaned).replace(" ", "")
    suffix = _strip_hebrew_punctuation("".join(tokens[1:]))
    return f"{ordinal}{suffix}"


def israeli_ident_slug(ident: str) -> str:
    """Transliterate a printed section identifier such as ``121ב`` or ``64א7א``.

    Digit runs pass through; Hebrew-letter runs become their ordinal slug.  Runs
    alternate, so the transformation stays injective across identifiers.
    """
    normalized = unicodedata.normalize("NFC", ident).strip()
    for char in _HEBREW_PUNCTUATION:
        normalized = normalized.replace(char, "")
    if not normalized:
        raise ValueError("empty section identifier")
    tokens = _IDENT_TOKEN_RE.findall(normalized)
    if "".join(tokens) != normalized:
        raise ValueError(f"unsupported characters in section identifier: {ident!r}")
    return "".join(token if token.isdigit() else hebrew_suffix_slug(token) for token in tokens)


@dataclass(frozen=True)
class IsraelOpenLawSupplement:
    """One extra rendered fragment that completes a truncated primary render."""

    source_file: str
    sha256: str
    note: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], *, source_id: str) -> Self:
        source_file = _required_text(data, "source_file")
        if Path(source_file).name != source_file or Path(source_file).is_absolute():
            raise ValueError(
                f"Israel supplement source_file must be a plain file name: {source_file!r}"
            )
        if not source_file.lower().endswith((".html", ".htm")):
            raise ValueError(f"Israel supplement source_file must be HTML: {source_file!r}")
        sha256 = _required_text(data, "sha256")
        if not _SHA256_RE.fullmatch(sha256):
            raise ValueError(f"invalid lowercase SHA-256 for {source_id} supplement: {sha256!r}")
        return cls(source_file=source_file, sha256=sha256, note=_required_text(data, "note"))


@dataclass(frozen=True)
class IsraelOpenLawSource:
    """One hash-pinned Israeli consolidated statute snapshot."""

    source_id: str
    instrument_slug: str
    israel_law_id: str
    title: str
    title_en: str
    source_url: str
    source_file: str
    sha256: str
    source_as_of: str
    expression_date: str
    expression_date_basis: str
    source_tier: str
    language: str
    expected_section_count: int
    expected_schedule_item_count: int
    expected_part_count: int
    expected_chapter_count: int
    expected_sign_count: int
    expected_schedule_count: int = 0
    alternate_version_sections: tuple[str, ...] = ()
    supplement_files: tuple[IsraelOpenLawSupplement, ...] = ()
    render_truncated_after_section: str | None = None
    excluded_headings: tuple[str, ...] = (_TABLE_OF_CONTENTS_HEADING,)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Self:
        """Validate and construct one manifest source."""
        jurisdiction = str(data.get("jurisdiction", ISRAEL_OPENLAW_JURISDICTION))
        if jurisdiction != ISRAEL_OPENLAW_JURISDICTION:
            raise ValueError(f"Israel source jurisdiction must be il, got {jurisdiction!r}")
        document_class = str(data.get("document_class", ISRAEL_OPENLAW_DOCUMENT_CLASS))
        if document_class != ISRAEL_OPENLAW_DOCUMENT_CLASS:
            raise ValueError(
                f"Israel source document_class must be statute, got {document_class!r}"
            )

        source_id = _required_text(data, "source_id")
        if not _SLUG_RE.fullmatch(source_id):
            raise ValueError(f"invalid Israel source_id: {source_id!r}")
        instrument_slug = _required_text(data, "instrument_slug")
        if not _SLUG_RE.fullmatch(instrument_slug):
            raise ValueError(f"invalid Israel instrument_slug: {instrument_slug!r}")

        israel_law_id = _required_text(data, "israel_law_id")
        if not israel_law_id.isdigit():
            raise ValueError(f"israel_law_id must contain only digits: {israel_law_id!r}")

        language_value = data.get("language")
        if isinstance(language_value, bool):
            raise ValueError("Israel language must be the string 'he', not a YAML boolean")
        language = _required_text(data, "language")
        if language != ISRAEL_OPENLAW_LANGUAGE:
            raise ValueError(f"Israel source language must be he, got {language!r}")

        source_file = _required_text(data, "source_file")
        if Path(source_file).name != source_file or Path(source_file).is_absolute():
            raise ValueError(f"Israel source_file must be a plain file name: {source_file!r}")
        if not source_file.lower().endswith((".html", ".htm")):
            raise ValueError(f"Israel source_file must be HTML: {source_file!r}")

        source_url = _required_text(data, "source_url")
        parsed_url = urlparse(source_url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.netloc != ISRAEL_OPENLAW_HOST
            or not parsed_url.path.startswith("/wiki/")
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError(
                f"Israel source_url must be an he.wikisource.org /wiki/ page: {source_url!r}"
            )

        sha256 = _required_text(data, "sha256")
        if not _SHA256_RE.fullmatch(sha256):
            raise ValueError(f"invalid lowercase SHA-256 for {source_id}: {sha256!r}")

        counts = {
            name: _required_count(data, name)
            for name in (
                "expected_section_count",
                "expected_part_count",
                "expected_chapter_count",
                "expected_sign_count",
            )
        }
        schedule_count = data.get("expected_schedule_count", 0)
        if (
            isinstance(schedule_count, bool)
            or not isinstance(schedule_count, int)
            or schedule_count < 0
        ):
            raise ValueError(
                f"Israel source {source_id} requires a non-negative expected_schedule_count"
            )
        schedule_items = data.get("expected_schedule_item_count", 0)
        if (
            isinstance(schedule_items, bool)
            or not isinstance(schedule_items, int)
            or schedule_items < 0
        ):
            raise ValueError(
                f"Israel source {source_id} requires a non-negative expected_schedule_item_count"
            )

        source_tier = _required_text(data, "source_tier")
        if source_tier not in ISRAEL_OPENLAW_SOURCE_TIERS:
            raise ValueError(
                f"Israel source {source_id} has unsupported source_tier: {source_tier!r}"
            )

        alternates = data.get("alternate_version_sections", [])
        if not isinstance(alternates, list) or not all(
            isinstance(item, str) and item.strip() for item in alternates
        ):
            raise ValueError(
                f"Israel source {source_id} alternate_version_sections must be a list of strings"
            )

        supplements_raw = data.get("supplement_files", [])
        if not isinstance(supplements_raw, list) or not all(
            isinstance(item, dict) for item in supplements_raw
        ):
            raise ValueError(
                f"Israel source {source_id} supplement_files must be a list of mappings"
            )
        supplements = tuple(
            IsraelOpenLawSupplement.from_mapping(cast(dict[str, Any], item), source_id=source_id)
            for item in supplements_raw
        )
        supplement_names = [item.source_file for item in supplements]
        if len(set(supplement_names)) != len(supplement_names) or source_file in supplement_names:
            raise ValueError(f"Israel source {source_id} has duplicate supplement source_file")

        truncated_after = data.get("render_truncated_after_section")
        if truncated_after is not None and (
            not isinstance(truncated_after, str) or not truncated_after.strip()
        ):
            raise ValueError(
                f"Israel source {source_id} render_truncated_after_section must be a section "
                "identifier string"
            )
        if truncated_after is not None and not supplements:
            raise ValueError(
                f"Israel source {source_id} declares a truncated render but no supplement_files"
            )

        excluded = data.get("excluded_headings", [_TABLE_OF_CONTENTS_HEADING])
        if not isinstance(excluded, list) or not all(
            isinstance(item, str) and item.strip() for item in excluded
        ):
            raise ValueError(
                f"Israel source {source_id} excluded_headings must be a list of strings"
            )

        return cls(
            source_id=source_id,
            instrument_slug=instrument_slug,
            israel_law_id=israel_law_id,
            title=_required_text(data, "title"),
            title_en=_required_text(data, "title_en"),
            source_url=source_url,
            source_file=source_file,
            sha256=sha256,
            source_as_of=_required_iso_date(data, "source_as_of"),
            expression_date=_required_iso_date(data, "expression_date"),
            expression_date_basis=_required_text(data, "expression_date_basis"),
            source_tier=source_tier,
            language=language,
            expected_section_count=counts["expected_section_count"],
            expected_schedule_item_count=schedule_items,
            expected_part_count=counts["expected_part_count"],
            expected_chapter_count=counts["expected_chapter_count"],
            expected_sign_count=counts["expected_sign_count"],
            expected_schedule_count=schedule_count,
            alternate_version_sections=tuple(
                unicodedata.normalize("NFC", item) for item in alternates
            ),
            supplement_files=supplements,
            render_truncated_after_section=(
                unicodedata.normalize("NFC", truncated_after.strip())
                if truncated_after is not None
                else None
            ),
            excluded_headings=tuple(
                unicodedata.normalize("NFC", item.strip()) for item in excluded
            ),
        )

    @property
    def document_citation_path(self) -> str:
        return (
            f"{ISRAEL_OPENLAW_JURISDICTION}/{ISRAEL_OPENLAW_DOCUMENT_CLASS}/{self.instrument_slug}"
        )

    @property
    def page_title(self) -> str:
        """The decoded he.wikisource page title from ``source_url``."""
        return unquote(urlparse(self.source_url).path[len("/wiki/") :])


@dataclass(frozen=True)
class IsraelOpenLawManifest:
    """Manifest binding local snapshots to official Israeli statute identities."""

    documents: tuple[IsraelOpenLawSource, ...]

    @classmethod
    def load(cls, path: str | Path) -> Self:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Israel manifest must be a YAML mapping")
        rows = data.get("documents")
        if not isinstance(rows, list) or not rows:
            raise ValueError("Israel manifest must contain a non-empty documents list")
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError("every Israel manifest document must be a mapping")
        manifest = cls(
            documents=tuple(
                IsraelOpenLawSource.from_mapping(cast(dict[str, Any], row)) for row in rows
            )
        )
        manifest.require_unique_sources()
        return manifest

    def require_unique_sources(self) -> None:
        for field_name in ("source_id", "instrument_slug", "israel_law_id", "source_file"):
            values = [str(getattr(source, field_name)) for source in self.documents]
            duplicates = sorted(value for value in set(values) if values.count(value) > 1)
            if duplicates:
                raise ValueError(f"duplicate Israel {field_name}: {', '.join(duplicates)}")


@dataclass(frozen=True)
class IsraelOpenLawProvision:
    """One document, navigation node, section, or schedule item."""

    citation_path: str
    parent_citation_path: str | None
    kind: str
    label: str
    heading: str | None
    body: str | None
    level: int
    ordinal: int
    source_file: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class IsraelOpenLawDocumentExtractReport:
    """Extraction result for one Israeli statute."""

    source_id: str
    instrument_slug: str
    israel_law_id: str
    section_count: int
    schedule_item_count: int
    navigation_count: int
    provisions_written: int
    source_path: Path
    sha256: str


@dataclass(frozen=True)
class IsraelOpenLawExtractReport:
    """Artifact report for one Israeli OpenLaw extraction run."""

    jurisdiction: str
    document_class: str
    version: str
    document_count: int
    section_count: int
    schedule_item_count: int
    navigation_count: int
    provisions_written: int
    inventory_path: Path
    provisions_path: Path
    coverage_path: Path
    coverage: ProvisionCoverageReport
    source_paths: tuple[Path, ...]
    document_reports: tuple[IsraelOpenLawDocumentExtractReport, ...]


@dataclass
class _PendingProvision:
    citation_path: str
    parent_citation_path: str | None
    kind: str
    label: str
    level: int
    ordinal: int
    source_file: str
    heading: str | None = None
    blocks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    editorial_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _PreparedSource:
    source: IsraelOpenLawSource
    content: bytes
    supplements: tuple[tuple[IsraelOpenLawSupplement, bytes], ...]
    provisions: tuple[IsraelOpenLawProvision, ...]
    section_count: int
    schedule_item_count: int
    navigation_count: int


def extract_israel_openlaw(
    store: CorpusArtifactStore,
    *,
    version: str,
    manifest_path: str | Path,
    source_dir: str | Path,
) -> IsraelOpenLawExtractReport:
    """Verify and extract hash-pinned Israeli consolidated statutes.

    Every manifest row, input hash, and structural count is validated before the
    first artifact is written, so a drifted snapshot fails loudly instead of
    landing a plausible-looking partial scope.
    """
    if not str(version).strip():
        raise ValueError("Israel extraction version must not be empty")
    manifest = IsraelOpenLawManifest.load(manifest_path)
    source_root = Path(source_dir).resolve()
    if not source_root.is_dir():
        raise ValueError(f"Israel source directory does not exist: {source_root}")

    prepared: list[_PreparedSource] = []
    for source in manifest.documents:
        source_path = _resolved_source_path(source_root, source.source_file, source)
        content = _verified_bytes(source_path, source.sha256, source.source_id)
        supplements: list[tuple[IsraelOpenLawSupplement, bytes]] = []
        for supplement in source.supplement_files:
            supplement_path = _resolved_source_path(source_root, supplement.source_file, source)
            supplements.append(
                (supplement, _verified_bytes(supplement_path, supplement.sha256, source.source_id))
            )
        provisions = parse_israel_openlaw_document(
            source=source,
            primary_html=content,
            supplements=tuple(supplements),
        )
        counts = _kind_counts(provisions)
        _require_expected_counts(source, counts)
        prepared.append(
            _PreparedSource(
                source=source,
                content=content,
                supplements=tuple(supplements),
                provisions=provisions,
                section_count=counts["section"],
                schedule_item_count=counts["schedule-item"],
                navigation_count=(
                    counts["part"] + counts["chapter"] + counts["sign"] + counts["schedule"]
                ),
            )
        )

    records: list[ProvisionRecord] = []
    inventory: list[SourceInventoryItem] = []
    source_paths: list[Path] = []
    document_reports: list[IsraelOpenLawDocumentExtractReport] = []
    for item in prepared:
        source = item.source
        # Every rendered fragment of the instrument is stored, and each provision
        # keeps the key of the fragment it was actually read from.
        source_keys: dict[str, str] = {}
        for file_name, payload, expected in (
            (source.source_file, item.content, source.sha256),
            *(
                (supplement.source_file, payload, supplement.sha256)
                for supplement, payload in item.supplements
            ),
        ):
            relative_name = f"openlaw/{file_name}"
            artifact_path = store.source_path(
                ISRAEL_OPENLAW_JURISDICTION,
                ISRAEL_OPENLAW_DOCUMENT_CLASS,
                version,
                relative_name,
            )
            written_sha256 = store.write_bytes(artifact_path, payload)
            if written_sha256 != expected:
                raise RuntimeError(
                    f"written Israel source hash changed for {source.source_id}: {written_sha256}"
                )
            source_paths.append(artifact_path)
            source_keys[file_name] = (
                f"sources/{ISRAEL_OPENLAW_JURISDICTION}/{ISRAEL_OPENLAW_DOCUMENT_CLASS}/"
                f"{version}/{relative_name}"
            )
        sha_by_file = {
            source.source_file: source.sha256,
            **{s.source_file: s.sha256 for s in source.supplement_files},
        }
        document_id = deterministic_provision_id(source.document_citation_path, version)
        for provision in item.provisions:
            source_key = source_keys[provision.source_file]
            metadata = {**_source_metadata(source), **provision.metadata}
            inventory.append(
                SourceInventoryItem(
                    citation_path=provision.citation_path,
                    source_url=source.source_url,
                    source_path=source_key,
                    source_format=ISRAEL_OPENLAW_SOURCE_FORMAT,
                    sha256=sha_by_file[provision.source_file],
                    metadata=metadata,
                )
            )
            citation_label = _citation_label(source, provision)
            records.append(
                ProvisionRecord(
                    id=deterministic_provision_id(provision.citation_path, version),
                    jurisdiction=ISRAEL_OPENLAW_JURISDICTION,
                    document_class=ISRAEL_OPENLAW_DOCUMENT_CLASS,
                    citation_path=provision.citation_path,
                    body=provision.body,
                    heading=provision.heading,
                    citation_label=citation_label,
                    version=version,
                    source_url=source.source_url,
                    source_path=source_key,
                    source_id=f"he.wikisource.org:openlaw:{source.instrument_slug}",
                    source_format=ISRAEL_OPENLAW_SOURCE_FORMAT,
                    source_document_id=document_id,
                    source_as_of=source.source_as_of,
                    expression_date=source.expression_date,
                    parent_citation_path=provision.parent_citation_path,
                    parent_id=(
                        deterministic_provision_id(provision.parent_citation_path, version)
                        if provision.parent_citation_path
                        else None
                    ),
                    level=provision.level,
                    ordinal=provision.ordinal,
                    kind=provision.kind,
                    language=source.language,
                    legal_identifier=citation_label,
                    identifiers={
                        "knesset.gov.il:israel_law_id": source.israel_law_id,
                        "he.wikisource.org:page": source.page_title,
                        "openlaw:instrument": source.instrument_slug,
                        "openlaw:source_id": source.source_id,
                        f"openlaw:{provision.kind}": provision.label,
                    },
                    metadata=metadata,
                )
            )
        document_reports.append(
            IsraelOpenLawDocumentExtractReport(
                source_id=source.source_id,
                instrument_slug=source.instrument_slug,
                israel_law_id=source.israel_law_id,
                section_count=item.section_count,
                schedule_item_count=item.schedule_item_count,
                navigation_count=item.navigation_count,
                provisions_written=len(item.provisions),
                source_path=artifact_path,
                sha256=written_sha256,
            )
        )

    _require_unique_citations(records)
    inventory_path = store.inventory_path(
        ISRAEL_OPENLAW_JURISDICTION, ISRAEL_OPENLAW_DOCUMENT_CLASS, version
    )
    provisions_path = store.provisions_path(
        ISRAEL_OPENLAW_JURISDICTION, ISRAEL_OPENLAW_DOCUMENT_CLASS, version
    )
    coverage_path = store.coverage_path(
        ISRAEL_OPENLAW_JURISDICTION, ISRAEL_OPENLAW_DOCUMENT_CLASS, version
    )
    store.write_inventory(inventory_path, inventory)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        tuple(inventory),
        tuple(records),
        jurisdiction=ISRAEL_OPENLAW_JURISDICTION,
        document_class=ISRAEL_OPENLAW_DOCUMENT_CLASS,
        version=version,
    )
    if not coverage.complete:
        raise RuntimeError("Israel extraction produced incomplete provision coverage")
    store.write_json(coverage_path, coverage.to_mapping())

    return IsraelOpenLawExtractReport(
        jurisdiction=ISRAEL_OPENLAW_JURISDICTION,
        document_class=ISRAEL_OPENLAW_DOCUMENT_CLASS,
        version=version,
        document_count=len(document_reports),
        section_count=sum(report.section_count for report in document_reports),
        schedule_item_count=sum(report.schedule_item_count for report in document_reports),
        navigation_count=sum(report.navigation_count for report in document_reports),
        provisions_written=len(records),
        inventory_path=inventory_path,
        provisions_path=provisions_path,
        coverage_path=coverage_path,
        coverage=coverage,
        source_paths=tuple(source_paths),
        document_reports=tuple(document_reports),
    )


@dataclass
class _ParseState:
    """Structure carried across the fragments that make up one document."""

    context: dict[str, tuple[str, int]] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=lambda: {"part": 0, "chapter": 0, "sign": 0})
    section_ordinal: int = 0
    schedule_item_ordinal: int = 0
    seen_section_idents: dict[str, int] = field(default_factory=dict)
    excluded_blocks: int = 0
    last_section_ident: str | None = None


def parse_israel_openlaw_document(
    *,
    source: IsraelOpenLawSource,
    primary_html: bytes,
    supplements: Sequence[tuple[IsraelOpenLawSupplement, bytes]] = (),
) -> tuple[IsraelOpenLawProvision, ...]:
    """Parse one instrument from its primary render plus any repair fragments.

    The Ordinance's full-page render exceeds MediaWiki's post-expand include
    budget and silently loses its tail, so a document may need more than one
    rendered fragment to be whole.  Fragments are parsed in order and share one
    navigation context, so a section in a supplement still hangs off the חלק it
    belongs to.
    """
    state = _ParseState()
    provisions: list[IsraelOpenLawProvision] = []

    primary_text = primary_html.decode("utf-8", "replace")
    truncated_at = primary_text.find(_TRUNCATION_MARKER)
    if truncated_at >= 0:
        if source.render_truncated_after_section is None:
            raise ValueError(
                f"Israel source {source.source_id} render is truncated by MediaWiki's "
                "post-expand include limit but the manifest does not declare "
                "render_truncated_after_section"
            )
        # Everything from the first omitted template on is partial, including the
        # section it lands inside, so the cut is made at the start of that
        # section rather than at the marker: a half-rendered provision is worse
        # than an absent one, and the supplement supplies it whole.
        anchor_start = primary_text.rfind(_SECTION_ANCHOR_OPEN, 0, truncated_at)
        if anchor_start < 0:
            raise ValueError(
                f"Israel source {source.source_id} is truncated before its first section"
            )
        primary_text = primary_text[:anchor_start]
    elif source.render_truncated_after_section is not None:
        raise ValueError(
            f"Israel source {source.source_id} declares render_truncated_after_section "
            "but its render carries no truncation marker"
        )

    provisions.extend(
        _parse_fragment(
            primary_text,
            source=source,
            state=state,
            source_file=source.source_file,
            primary=True,
        )
    )

    if source.render_truncated_after_section is not None:
        if state.last_section_ident != source.render_truncated_after_section:
            raise ValueError(
                f"Israel source {source.source_id} truncates after section "
                f"{state.last_section_ident!r}, not the declared "
                f"{source.render_truncated_after_section!r}"
            )
        if not supplements:
            raise ValueError(
                f"Israel source {source.source_id} is truncated and supplies no "
                "supplement to complete it"
            )

    for supplement, payload in supplements:
        provisions.extend(
            _parse_fragment(
                payload.decode("utf-8", "replace"),
                source=source,
                state=state,
                source_file=supplement.source_file,
                primary=False,
            )
        )

    provisions = _mark_alternate_bases(provisions)
    _require_unique_parsed_citations(provisions, source.source_id)
    return tuple(provisions)


def parse_israel_openlaw_html(
    html: str | bytes,
    *,
    source: IsraelOpenLawSource,
) -> tuple[IsraelOpenLawProvision, ...]:
    """Parse a single complete ספר החוקים הפתוח render."""
    payload = html.encode("utf-8") if isinstance(html, str) else html
    return parse_israel_openlaw_document(source=source, primary_html=payload)


def _fragment_root(soup: BeautifulSoup, source: IsraelOpenLawSource, primary: bool) -> Tag:
    """Return the element whose children are the law's blocks.

    A full page nests everything in ``div#law-content``.  An API-rendered
    fragment closes that wrapper early, leaving the blocks as siblings under the
    parser output, so the fragment's root is that container instead.
    """
    roots = soup.select("div#law-content")
    if primary:
        if len(roots) != 1:
            raise ValueError(
                f"Israel source {source.source_id} must contain exactly one "
                f"div#law-content, got {len(roots)}"
            )
        return roots[0]
    if len(roots) != 1:
        raise ValueError(
            f"Israel supplement for {source.source_id} must contain exactly one "
            f"div#law-content, got {len(roots)}"
        )
    parent = roots[0].parent
    if not isinstance(parent, Tag):
        raise ValueError(f"Israel supplement for {source.source_id} has no fragment container")
    return parent


def _parse_fragment(
    html: str,
    *,
    source: IsraelOpenLawSource,
    state: _ParseState,
    source_file: str,
    primary: bool,
) -> list[IsraelOpenLawProvision]:
    """Parse one rendered fragment into document-order provisions."""
    soup = BeautifulSoup(html, "lxml")
    root = _fragment_root(soup, source, primary)

    document_path = source.document_citation_path
    parsed: list[IsraelOpenLawProvision] = []

    if primary:
        publication_history = _require_source_identity(root, source)
        parsed.append(
            IsraelOpenLawProvision(
                citation_path=document_path,
                parent_citation_path=None,
                kind="document",
                label=source.israel_law_id,
                heading=source.title,
                body=publication_history or source.title,
                level=0,
                ordinal=0,
                source_file=source_file,
                metadata=_document_metadata(soup, source, publication_history),
            )
        )

    context = state.context
    counters = state.counters
    pending: _PendingProvision | None = None
    pending_sub_item: str | None = None
    last_anchor_was_provision = False
    skipping = False

    def deepest() -> tuple[str, int]:
        for kind in ("sign", "chapter", "schedule", "part"):
            if kind in context:
                return context[kind]
        return document_path, 0

    def clear_deeper(level: int) -> None:
        for kind in [k for k, (_, node_level) in context.items() if node_level >= level]:
            del context[kind]

    def flush() -> None:
        nonlocal pending, pending_sub_item, last_anchor_was_provision
        pending_sub_item = None
        last_anchor_was_provision = False
        if pending is None:
            return
        metadata = dict(pending.metadata)
        if pending.editorial_notes:
            metadata["editorial_notes"] = list(pending.editorial_notes)
        if pending.kind in _NAV_LEVELS and pending.heading:
            # A navigation node prints its own name above whatever it carries —
            # a schedule's caption, its subheadings and its tables.  Leading with
            # the name keeps a content-bearing לוח from reading as a bare table
            # and keeps the empty-node fallback (name only) exactly as it was.
            body = _joined_body([pending.heading, *pending.blocks])
        else:
            body = _joined_body(pending.blocks)
        parsed.append(
            IsraelOpenLawProvision(
                citation_path=pending.citation_path,
                parent_citation_path=pending.parent_citation_path,
                kind=pending.kind,
                label=pending.label,
                heading=pending.heading,
                body=body,
                level=pending.level,
                ordinal=pending.ordinal,
                source_file=pending.source_file,
                metadata=metadata,
            )
        )
        pending = None

    for node in root.children:
        if not isinstance(node, Tag):
            continue
        classes = _classes(node)

        if _DISCLAIMER_CLASS in classes:
            # The project's "not legal advice" block. Never law.
            state.excluded_blocks += 1
            continue

        if node.name in {"h1", "h2", "h3", "h4"}:
            if "law-title" in classes:
                continue
            heading = _inline_text(node)
            if node.name == "h4":
                # A subheading printed under a schedule or part heading: the
                # enabling-section caption ("( סעיף 75ג )") and the applicability
                # labels that distinguish otherwise identical tables
                # ("גיל הפרישה לגבר" / "גיל הפרישה לאישה" over NII לוח א׳1) alike.
                # Keep it in the body at its printed position, so each table
                # keeps its own label, and keep every one of them in metadata in
                # printed order rather than overwriting.
                if pending is not None:
                    captions = cast(list[str], pending.metadata.setdefault("captions", []))
                    captions.append(heading)
                    pending.metadata.setdefault("caption", heading)
                    pending.blocks.append(heading)
                continue
            flush()
            skipping = heading in source.excluded_headings
            if skipping:
                state.excluded_blocks += 1
                if node.name == "h1":
                    clear_deeper(_NAV_LEVELS["part"])
                elif node.name == "h2":
                    clear_deeper(_NAV_LEVELS["chapter"])
                else:
                    clear_deeper(_NAV_LEVELS["sign"])
                continue
            if node.name == "h1":
                clear_deeper(_NAV_LEVELS["part"])
                counters["part"] += 1
                counters["chapter"] = 0
                counters["sign"] = 0
                path = f"{document_path}/part-{counters['part']}"
                pending = _PendingProvision(
                    citation_path=path,
                    parent_citation_path=document_path,
                    kind="part",
                    label=str(counters["part"]),
                    level=_NAV_LEVELS["part"],
                    ordinal=counters["part"],
                    source_file=source_file,
                    heading=heading,
                    metadata={"raw_marker": heading},
                )
                context["part"] = (path, _NAV_LEVELS["part"])
                continue
            if node.name == "h2":
                clear_deeper(_NAV_LEVELS["chapter"])
                counters["sign"] = 0
                schedule = _SCHEDULE_HEADING_RE.match(heading)
                if schedule is not None:
                    ident = schedule_heading_ident(schedule.group("rest"))
                    path = f"{document_path}/schedule-{israeli_ident_slug(ident)}"
                    pending = _PendingProvision(
                        citation_path=path,
                        parent_citation_path=document_path,
                        kind="schedule",
                        label=ident,
                        level=_NAV_LEVELS["schedule"],
                        ordinal=0,
                        source_file=source_file,
                        heading=heading,
                        metadata={"raw_marker": heading, "printed_identifier": ident},
                    )
                    context["schedule"] = (path, _NAV_LEVELS["schedule"])
                    continue
                counters["chapter"] += 1
                parent_path = context["part"][0] if "part" in context else document_path
                path = f"{parent_path}/chapter-{counters['chapter']}"
                pending = _PendingProvision(
                    citation_path=path,
                    parent_citation_path=parent_path,
                    kind="chapter",
                    label=str(counters["chapter"]),
                    level=_NAV_LEVELS["chapter"],
                    ordinal=counters["chapter"],
                    source_file=source_file,
                    heading=heading,
                    metadata={"raw_marker": heading},
                )
                context["chapter"] = (path, _NAV_LEVELS["chapter"])
                continue
            clear_deeper(_NAV_LEVELS["sign"])
            counters["sign"] += 1
            parent_path, _ = deepest()
            path = f"{parent_path}/sign-{counters['sign']}"
            pending = _PendingProvision(
                citation_path=path,
                parent_citation_path=parent_path,
                kind="sign",
                label=str(counters["sign"]),
                level=_NAV_LEVELS["sign"],
                ordinal=counters["sign"],
                source_file=source_file,
                heading=heading,
                metadata={"raw_marker": heading},
            )
            context["sign"] = (path, _NAV_LEVELS["sign"])
            continue

        if node.name != "div":
            continue

        if skipping:
            if any(name in classes for name in ("law-main", "law-desc")) or "law-number" in classes:
                state.excluded_blocks += 1
            continue

        if any(name.startswith("law-number") for name in classes) and node.get("id"):
            anchor_id = unicodedata.normalize("NFC", str(node["id"]))
            label = _inline_text(node).rstrip(".").strip()
            if anchor_id.startswith(_SECTION_ANCHOR_PREFIX):
                ident = anchor_id[len(_SECTION_ANCHOR_PREFIX) :]
                if "." in ident:
                    # Sub-item anchor (סעיף_2.1): its text belongs to the open
                    # section.  Splitting here is the false-split failure mode.
                    if pending is None or pending.kind != "section":
                        raise ValueError(
                            f"Israel source {source.source_id} has sub-item anchor "
                            f"{anchor_id!r} outside a section"
                        )
                    if label:
                        raise ValueError(
                            f"Israel source {source.source_id} sub-item anchor "
                            f"{anchor_id!r} carries a printed label {label!r}"
                        )
                    pending_sub_item = ident
                    last_anchor_was_provision = False
                    continue
                if not label:
                    raise ValueError(
                        f"Israel source {source.source_id} section anchor "
                        f"{anchor_id!r} has no printed label"
                    )
                flush()
                occurrence = state.seen_section_idents.get(ident, 0) + 1
                state.seen_section_idents[ident] = occurrence
                slug = israeli_ident_slug(ident)
                if occurrence == 1:
                    path = f"{document_path}/section-{slug}"
                else:
                    if ident not in source.alternate_version_sections:
                        raise ValueError(
                            f"Israel source {source.source_id} repeats section {ident!r} "
                            "without declaring it in alternate_version_sections"
                        )
                    path = f"{document_path}/section-{slug}-alt{occurrence}"
                state.section_ordinal += 1
                state.last_section_ident = ident
                parent_path, parent_level = deepest()
                metadata: dict[str, Any] = {
                    "printed_identifier": ident,
                    "printed_label": label,
                    "anchor_id": anchor_id,
                }
                if _strip_hebrew_punctuation(label) != ident:
                    # OpenLaw prints "57א" against id סעיף_57ג; the anchor wins.
                    metadata["printed_label_mismatch"] = True
                if occurrence > 1:
                    metadata["alternate_version"] = True
                    metadata["alternate_version_index"] = occurrence
                    metadata["alternate_of"] = f"{document_path}/section-{slug}"
                pending = _PendingProvision(
                    citation_path=path,
                    parent_citation_path=parent_path,
                    kind="section",
                    label=ident,
                    level=parent_level + 1,
                    ordinal=state.section_ordinal,
                    source_file=source_file,
                    metadata=metadata,
                )
                last_anchor_was_provision = True
                continue

            prefix = next(
                (p for p in _SCHEDULE_ANCHOR_PREFIXES if anchor_id.startswith(p)),
                None,
            )
            if prefix is not None:
                if _SCHEDULE_ITEM_INFIX not in anchor_id:
                    raise ValueError(
                        f"Israel source {source.source_id} has unrecognized schedule anchor "
                        f"{anchor_id!r}"
                    )
                schedule_ident, item_ident = anchor_id[len(prefix) :].split(_SCHEDULE_ITEM_INFIX, 1)
                if "schedule" not in context:
                    raise ValueError(
                        f"Israel source {source.source_id} has schedule item {anchor_id!r} "
                        "outside a schedule heading"
                    )
                schedule_path = context["schedule"][0]
                expected_path = f"{document_path}/schedule-{israeli_ident_slug(schedule_ident)}"
                if schedule_path != expected_path:
                    raise ValueError(
                        f"Israel source {source.source_id} schedule item {anchor_id!r} "
                        f"does not belong to the open schedule {schedule_path!r}"
                    )
                flush()
                state.schedule_item_ordinal += 1
                path = f"{schedule_path}/item-{israeli_ident_slug(item_ident)}"
                pending = _PendingProvision(
                    citation_path=path,
                    parent_citation_path=schedule_path,
                    kind="schedule-item",
                    label=item_ident,
                    level=_NAV_LEVELS["schedule"] + 1,
                    ordinal=state.schedule_item_ordinal,
                    source_file=source_file,
                    metadata={
                        "printed_identifier": item_ident,
                        "printed_label": label,
                        "anchor_id": anchor_id,
                        "schedule_identifier": schedule_ident,
                    },
                )
                last_anchor_was_provision = True
                continue

            raise ValueError(
                f"Israel source {source.source_id} has unrecognized anchor id {anchor_id!r}"
            )

        if "law-desc" in classes:
            heading, amendment_history = _split_description(node)
            if pending_sub_item is not None:
                if pending is None:
                    raise ValueError(
                        f"Israel source {source.source_id} has a sub-item description "
                        "outside a section"
                    )
                sub_items = cast(
                    list[dict[str, str]], pending.metadata.setdefault("sub_item_headings", [])
                )
                entry = {"identifier": pending_sub_item}
                if heading:
                    entry["heading"] = heading
                if amendment_history:
                    entry["amendment_history"] = amendment_history
                sub_items.append(entry)
                continue
            if pending is None or not last_anchor_was_provision:
                continue
            pending.heading = heading or None
            if amendment_history:
                pending.metadata["amendment_history"] = amendment_history
            if heading:
                origin = _ORIGIN_MARKER_RE.search(heading)
                if origin is not None:
                    pending.metadata["consolidation_origin_marker"] = origin.group("marker")
            last_anchor_was_provision = False
            continue

        if "law-main" in classes:
            statutory, notes, labels = _render_law_main(node)
            if pending is None:
                if statutory:
                    raise ValueError(
                        f"Israel source {source.source_id} has statutory text before the "
                        "first structural marker"
                    )
                continue
            if statutory is None:
                status = _status_marker(notes)
                if status is not None and not pending.blocks:
                    statutory, status_word = status
                    pending.metadata["status_marker"] = status_word
                    pending.metadata["operative"] = False
            if statutory:
                pending.blocks.append(statutory)
            pending.editorial_notes.extend(notes)
            if labels:
                # Kept in the body at their printed position; recorded here too so a
                # consumer can find them without re-parsing the table they label.
                recorded = cast(list[str], pending.metadata.setdefault("statutory_notes", []))
                recorded.extend(labels)
            last_anchor_was_provision = False
            continue

    flush()
    return parsed


def _resolved_source_path(source_root: Path, file_name: str, source: IsraelOpenLawSource) -> Path:
    path = (source_root / file_name).resolve()
    try:
        path.relative_to(source_root)
    except ValueError as exc:
        raise ValueError(f"Israel source path escapes source directory: {file_name!r}") from exc
    if not path.is_file():
        raise ValueError(f"Israel source file does not exist: {path}")
    return path


def _verified_bytes(path: Path, expected_sha256: str, source_id: str) -> bytes:
    content = path.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected_sha256:
        raise ValueError(
            f"Israel SHA-256 mismatch for {source_id} ({path.name}): "
            f"expected {expected_sha256}, got {actual}"
        )
    return content


def _required_text(data: Mapping[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Israel manifest requires a non-empty {field_name}")
    return unicodedata.normalize("NFC", value.strip())


def _required_iso_date(data: Mapping[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Israel manifest requires a quoted ISO date for {field_name}")
    return date.fromisoformat(value.strip()).isoformat()


def _required_count(data: Mapping[str, Any], field_name: str) -> int:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Israel manifest requires a non-negative integer {field_name}")
    return value


def _classes(tag: Tag) -> list[str]:
    """Return a tag's CSS classes as a list, whatever bs4 hands back."""
    value = tag.get("class")
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _strip_hebrew_punctuation(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    for char in _HEBREW_PUNCTUATION:
        normalized = normalized.replace(char, "")
    return normalized.strip()


def _require_source_identity(root: Tag, source: IsraelOpenLawSource) -> str | None:
    """Check the page's own title and Knesset law id, and return its header line."""
    title_node = root.select_one("h1.law-title")
    if title_node is None:
        raise ValueError(f"Israel source {source.source_id} has no h1.law-title")
    title = _inline_text(title_node)
    if title != source.title:
        raise ValueError(
            f"Israel source {source.source_id} title mismatch: "
            f"manifest {source.title!r}, page {title!r}"
        )
    header = _publication_history(root)
    if header is None or not header.startswith(source.israel_law_id):
        raise ValueError(
            f"Israel source {source.source_id} does not open with IsraelLawID "
            f"{source.israel_law_id}"
        )
    return header


def _publication_history(root: Tag) -> str | None:
    """Return the publication-history line OpenLaw prints under the title rule."""
    separator = root.select_one("hr.law-separator")
    if separator is None:
        return None
    for sibling in separator.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.name in {"h1", "h2", "h3"}:
            return None
        if sibling.name != "div" or sibling.get("class"):
            continue
        text = _inline_text(sibling)
        if text:
            return text
    return None


def _document_metadata(
    soup: BeautifulSoup,
    source: IsraelOpenLawSource,
    publication_history: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"wikisource_page": source.page_title}
    if source.render_truncated_after_section is not None:
        metadata["render_truncated_after_section"] = source.render_truncated_after_section
        metadata["render_supplements"] = [
            {"source_file": item.source_file, "note": item.note} for item in source.supplement_files
        ]
    if publication_history:
        metadata["publication_history"] = publication_history
    revision = soup.find(id="footer-info-lastmod")
    if isinstance(revision, Tag):
        metadata["wikisource_last_edited_note"] = _inline_text(revision)
    return metadata


def _split_description(node: Tag) -> tuple[str, str | None]:
    """Split a ``div.law-desc`` into its heading and its amendment-history note."""
    notes = [_inline_text(note) for note in node.find_all("span", class_="law-note")]
    working = _without(node, lambda tag: "law-note" in _classes(tag))
    heading = _inline_text(working)
    amendment_history = " ".join(note for note in notes if note) or None
    return heading, amendment_history


def _is_editorial_lead_in(text: str) -> bool:
    """Does this note read as OpenLaw introducing apparatus of its own?

    The project prints its comparison apparatus behind an unparenthesised,
    colon-terminated lead-in sentence — ``להלן מדרגות המס לשנים 2019 עד 2027:``
    under ITO §121.  Everything the *statute* prints as a note is delimited
    instead: amendment history in square brackets (``[תיקון: תשס״ט־4]``) and
    statutory version labels in parentheses (``(הנוסח הקבוע):``,
    ``(הוראת שעה לשנים 2025–2026):`` over NII לוח י׳).  A parenthesised or
    bracketed note therefore never introduces editorial apparatus.
    """
    return bool(text) and text.endswith(":") and text[0] not in "([\u200f\u200e"


def _introduces_a_replacement(text: str) -> bool:
    """Is this note shaped ``(<qualifier>: <replacement>)``?

    A colon *inside* the parentheses, with a qualifier before it and a value after,
    is how this consolidation prints a substitution: the printed text holds for the
    general case and the note gives what to read instead in the case it names —
    ``(בשנים 2025–2026: 7.85%)`` beside NII §340א's 6.25%,
    ``(עבור מי שעלה לפני שנת 2022: 42 החדשים)`` beside ITO §35's 54 months.  A note
    that *ends* with its colon is a label on what follows, handled separately.
    """
    inner = text[1:].rstrip()
    if inner.endswith(")"):
        inner = inner[:-1]
    qualifier, separator, replacement = inner.partition(":")
    return bool(separator) and bool(qualifier.strip()) and bool(replacement.strip())


def _is_temporary_substitution(text: str) -> bool:
    """Does this note print a replacement for the text it is printed beside?

    Naming a temporary order or instructing a re-reading is a statement of legal
    effect in any position, so those two markers decide on their own.  Otherwise the
    shape does: ``(<qualifier>: <replacement>)`` is a substitution unless it is one of
    the project's own value glosses, which supply a figure the statute leaves to
    indexation rather than a wording the statute replaces.
    """
    if _TEMPORARY_ORDER_RE.search(text) or _SUBSTITUTED_WORDING_RE.search(text):
        return True
    if _INDEXATION_GLOSS_RE.match(text) or _SHEKEL_UNIT_RE.search(text):
        return False
    return _introduces_a_replacement(text)


def _editorial_table_positions(block: Tag) -> set[int]:
    """Positions (in document order) of the tables OpenLaw prints as apparatus.

    A table is the project's own only when a lead-in note introduces it *and* it
    carries no note of its own: a note printed in a cell qualifies the value in
    that cell (NII לוח ח׳2, לוח י׳, לוח י״ז), which is the signal that the table
    belongs to the law.  Every other table in the block is statutory and must
    survive note removal — deleting the whole block because nothing but a table
    remained is what dropped those three schedules.

    Once a lead-in is seen, every later table in its container with no note of its
    own is marked, with no bound on what lies between.  That is right for the one
    block where it fires and is recorded as a limit in the PR body: a re-capture
    that interleaves statutory text under a lead-in is a new review, and the
    snapshots are hash-pinned, so it cannot happen silently.
    """
    positions = {id(table): index for index, table in enumerate(block.find_all("table"))}
    editorial: set[int] = set()
    for note in block.find_all("span", class_="law-note"):
        if note.find_parent("table") is not None:
            # A marker on a cell of the table: the table is statutory text.
            continue
        if not _is_editorial_lead_in(_inline_text(note)):
            continue
        container = note.parent
        if container is None:
            continue
        introduced = False
        for descendant in container.descendants:
            if descendant is note:
                introduced = True
                continue
            if not introduced or not isinstance(descendant, Tag) or descendant.name != "table":
                continue
            if descendant.find("span", class_="law-note") is not None:
                continue
            editorial.add(positions[id(descendant)])
    return editorial


def _without_tables_at(node: Tag, positions: set[int]) -> Tag:
    """Return a detached copy of ``node`` without the tables at ``positions``."""
    working = node.__copy__()
    for index, table in enumerate(working.find_all("table")):
        if index in positions:
            table.decompose()
    return working


def _statutory_label_positions(block: Tag) -> set[int]:
    """Positions (in document order) of the ``law-note`` spans a body must keep.

    ``span.law-note`` is OpenLaw's apparatus nearly everywhere it appears, and the
    citation scheme strips it: amendment history in square brackets
    (``[תיקון: תשס״ט־4]``), the project's own indexed-amount glosses
    (``(נקוב לשנת 2015; בשנת 2023, 141,840 ש״ח)``), its footnote letters, its
    editorial asides.  Three shapes are not apparatus, because deleting them changes
    what the row *says* rather than how it reads:

    * a **repeal, deletion or expiry marker** — ``(בוטל).``, ``(נמחקה);``,
      ``(פקע).`` — printed against a subsection or a paragraph.  The adapter already
      treats the identical marker as body text when it is a whole section's only
      content (:func:`_status_marker`, which also sets ``operative: false``); deleting
      it on a limb of a live section is the same statement of legal effect thrown
      away, and it leaves a bare enumerator behind.  ITO §5 read
      ``(1) (2) (3) (4) (א) (ב) שר האוצר…`` — five repealed limbs collapsed into a run
      of empty labels flowing into the text of the one that survives.
    * a **parenthesised, colon-terminated qualifier** — ``(הנוסח הקבוע):``,
      ``(הוראת שעה לשנים 2025–2026):``, ``(החל מיום 1.1.2030):``,
      ``(חל על עולה שעלה בשנת 2022 ולאחריה):``.  These say which of two competing
      versions a text is, or the window in which it applies.  Without them NII §348(ה)
      prints its permanent version and its temporary-order replacement consecutively
      with nothing between, ITO §11's confrontation-line credits read as permanent,
      and NII לוח י׳ prints two identical-header contribution-rate tables back to
      back — the same defect the h4 repair fixed for the two ladders of לוח א׳1.
    * a **parenthesised note printed inside a table cell** — the statute's own
      temporary-order substitution for that cell's value,
      ``(הוראת שעה בשנים 2024 עד 2027: 2.06)``.  It is not colon-terminated, so it
      needs its own limb.
    * a **substitution printed inline in running text** — the same statement of legal
      effect as the one in the cell, in a sentence rather than a table:
      ``(בשנים 2025–2026: 7.85%)`` beside the 6.25% of NII §340א(א)(1),
      ``(עבור מי שעלה לפני שנת 2022: 42 החדשים)`` beside the 54 months of ITO §35,
      ``(לגבי מי שהיה לתושב ישראל בשנות המס 2007–2009, יקראו כאילו נאמר ”חמש שנים
      רצופות“ במקום ”עשר שנים רצופות“)`` in ITO §14's definition.  Dropping these
      leaves the permanent figure reading as the one in force for the pilot year.
      See :func:`_is_temporary_substitution` for the line between a substitution and
      one of the project's indexed-value glosses.

    An unparenthesised colon lead-in is the project introducing itself and is never
    kept — see :func:`_is_editorial_lead_in`.  Every note that is kept is also
    reported for ``metadata.statutory_notes``.
    """
    keep: set[int] = set()
    for index, note in enumerate(block.find_all("span", class_="law-note")):
        text = _inline_text(note)
        if not text.startswith("("):
            continue
        in_a_cell = note.find_parent("table") is not None
        qualifies = (
            text.endswith(":")
            or _STATUTORY_STATUS_RE.match(text) is not None
            or _is_temporary_substitution(text)
        )
        if in_a_cell or qualifies:
            keep.add(index)
    return keep


def _without_notes_except(node: Tag, keep: set[int]) -> Tag:
    """Detached copy of ``node`` with every ``law-note`` gone but those at ``keep``."""
    working = node.__copy__()
    for index, note in enumerate(working.find_all("span", class_="law-note")):
        if index in keep or note.decomposed or note.attrs is None:
            continue
        note.decompose()
    return working


def _render_law_main(block: Tag) -> tuple[str | None, list[str], list[str]]:
    """Return (statutory text, editorial notes, statutory labels) for one ``div.law-main``.

    ``span.law-note`` reaches a body only in the statutory shapes
    :func:`_statutory_label_positions` names; every other note is apparatus, is kept
    out of the body and is reported for ``metadata.editorial_notes``.  Tables are
    kept unless OpenLaw introduces them as apparatus of its own (see
    :func:`_editorial_table_positions`), and a block is discarded entirely only when
    nothing but that apparatus was in it.
    """
    found = block.find_all("span", class_="law-note")
    keep = _statutory_label_positions(block)
    # A block holding nothing but its own status line goes to :func:`_status_marker` in
    # the caller, which makes it the body and pairs it with ``operative: false``; keeping
    # the marker here would render the same text and silently skip that path.  Every
    # *other* note-only block is a standalone label — NII סימן ט׳ of chapter ז׳ is headed
    # by nothing but ``(הוראת שעה מיום 31.3.2026 עד יום 31.3.2027):``, the window in which
    # its wartime unemployment provisions apply — and is body text in printed position.
    # Assuming every note-only block was a status line dropped that window into
    # ``editorial_notes`` and left the sign reading as though it applied indefinitely.
    if (
        keep
        and _status_marker([text for note in found if (text := _inline_text(note))]) is not None
        and _render_law_main_text(_without_notes_except(block, set())) is None
    ):
        keep = set()
    notes = [
        text
        for index, note in enumerate(found)
        if index not in keep and (text := _inline_text(note))
    ]
    labels = [text for index in sorted(keep) if (text := _inline_text(found[index]))]
    working = _without_notes_except(block, keep)
    statutory = _render_law_main_text(working)
    if statutory is None:
        return None, notes, labels
    editorial = _editorial_table_positions(block)
    if not editorial:
        return statutory, notes, labels
    return _render_law_main_text(_without_tables_at(working, editorial)), notes, labels


def _status_marker(notes: Sequence[str]) -> tuple[str, str] | None:
    """Return (line, status) when a note-only block is a section status line."""
    if len(notes) != 1:
        return None
    match = _STATUS_MARKER_RE.match(notes[0])
    if match is None:
        return None
    return notes[0], match.group("status")


def _without(node: Tag, predicate: Any) -> Tag:
    """Return a detached copy of ``node`` with matching descendants removed."""
    working = node.__copy__()
    for tag in list(working.find_all(True)):
        if tag.decomposed or tag.attrs is None:
            # Already destroyed together with a matching ancestor.
            continue
        if predicate(tag):
            tag.decompose()
    return working


def _render_law_main_text(block: Tag) -> str | None:
    """Render one law-main body, pairing ``law-numberN`` markers with their text."""
    lines: list[str] = []
    markers: list[str] = []
    for child in block.children:
        if isinstance(child, NavigableString):
            text = _render_text(str(child))
            if text:
                lines.append(text)
            continue
        if not isinstance(child, Tag):
            continue
        classes = _classes(child)
        if any(name.startswith("law-number") for name in classes):
            marker = _inline_text(child)
            if marker:
                markers.append(marker)
            continue
        text = _render_block(child)
        if not text:
            continue
        if markers:
            text = f"{' '.join(markers)} {text}"
            markers = []
        lines.append(text)
    if markers:
        lines.append(" ".join(markers))
    return _joined_body(lines)


def _collapse_spaces(value: str) -> str:
    return _SPACE_BEFORE_PUNCTUATION_RE.sub("", value)


def _inline_text(tag: Tag) -> str:
    raw = (
        tag.get_text("", strip=False).replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    )
    return _collapse_spaces(
        unicodedata.normalize("NFC", _ASCII_WHITESPACE_RE.sub(" ", raw.replace("\n", " ")).strip())
    )


def _render_block(block: Tag) -> str:
    if block.name == "table":
        return _render_table(block)
    raw = "".join(_render_element(child) for child in block.children)
    return _render_text(raw)


def _render_element(node: PageElement) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    if node.name == "br":
        return "\n"
    if node.name == "table":
        return _render_table(node)
    if node.name in {"div", "p"}:
        inner = "".join(_render_element(child) for child in node.children)
        return f"\n{inner}\n"
    return "".join(_render_element(child) for child in node.children)


def _render_table(table: Tag) -> str:
    rendered_rows: list[str] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        rendered_cells = [
            _render_text("".join(_render_element(child) for child in cell.children))
            for cell in cells
        ]
        rendered_rows.append(" | ".join(cell for cell in rendered_cells if cell))
    return _joined_body(rendered_rows) or ""


def _render_text(raw: str) -> str:
    raw = unicodedata.normalize("NFC", raw)
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    lines = [
        _collapse_spaces(_ASCII_WHITESPACE_RE.sub(" ", line).strip()) for line in raw.split("\n")
    ]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    compacted: list[str] = []
    for line in lines:
        if line or not compacted or compacted[-1]:
            compacted.append(line)
    return "\n".join(compacted)


def _joined_body(blocks: Sequence[str]) -> str | None:
    values = [value for value in blocks if value.strip()]
    return "\n".join(values) if values else None


def _kind_counts(provisions: Sequence[IsraelOpenLawProvision]) -> dict[str, int]:
    counts = {
        "document": 0,
        "part": 0,
        "chapter": 0,
        "sign": 0,
        "schedule": 0,
        "section": 0,
        "schedule-item": 0,
    }
    for provision in provisions:
        if provision.kind not in counts:
            raise ValueError(f"unexpected Israel provision kind: {provision.kind!r}")
        counts[provision.kind] += 1
    return counts


def _require_expected_counts(source: IsraelOpenLawSource, counts: Mapping[str, int]) -> None:
    expectations = (
        ("section", source.expected_section_count, "expected_section_count"),
        ("schedule-item", source.expected_schedule_item_count, "expected_schedule_item_count"),
        ("part", source.expected_part_count, "expected_part_count"),
        ("chapter", source.expected_chapter_count, "expected_chapter_count"),
        ("sign", source.expected_sign_count, "expected_sign_count"),
        ("schedule", source.expected_schedule_count, "expected_schedule_count"),
    )
    for kind, expected, field_name in expectations:
        if counts[kind] != expected:
            raise ValueError(
                f"Israel {field_name} mismatch for {source.source_id}: "
                f"expected {expected}, got {counts[kind]}"
            )


def _mark_alternate_bases(
    provisions: Sequence[IsraelOpenLawProvision],
) -> list[IsraelOpenLawProvision]:
    """Flag the base section of every alternate-version pair."""
    bases = {
        str(provision.metadata["alternate_of"])
        for provision in provisions
        if provision.metadata.get("alternate_version")
    }
    if not bases:
        return list(provisions)
    marked: list[IsraelOpenLawProvision] = []
    for provision in provisions:
        if provision.citation_path in bases:
            metadata = {**provision.metadata, "has_alternate_versions": True}
            marked.append(
                IsraelOpenLawProvision(
                    citation_path=provision.citation_path,
                    parent_citation_path=provision.parent_citation_path,
                    kind=provision.kind,
                    label=provision.label,
                    heading=provision.heading,
                    body=provision.body,
                    level=provision.level,
                    ordinal=provision.ordinal,
                    source_file=provision.source_file,
                    metadata=metadata,
                )
            )
            continue
        marked.append(provision)
    return marked


def _citation_label(source: IsraelOpenLawSource, provision: IsraelOpenLawProvision) -> str:
    if provision.kind == "document":
        return source.title
    if provision.kind == "section":
        suffix = ""
        if provision.metadata.get("alternate_version"):
            suffix = f" (נוסח חלופי {provision.metadata['alternate_version_index']})"
        return f"{source.title}, סעיף {provision.label}{suffix}"
    if provision.kind == "schedule-item":
        schedule = provision.metadata.get("schedule_identifier", "")
        return f"{source.title}, לוח {schedule} פרט {provision.label}"
    if provision.heading:
        return f"{source.title}, {provision.heading}"
    return f"{source.title}, {provision.kind} {provision.label}"


def _source_metadata(source: IsraelOpenLawSource) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "instrument_slug": source.instrument_slug,
        "israel_law_id": source.israel_law_id,
        "title": source.title,
        "title_en": source.title_en,
        "source_authority": ISRAEL_OPENLAW_SOURCE_AUTHORITY,
        "source_tier": source.source_tier,
        "knesset_full_text_link_verified": (source.source_tier == "consolidation-knesset-linked"),
        "source_language": source.language,
        "consolidated_expression": True,
        "expression_date_basis": source.expression_date_basis,
        "expected_section_count": source.expected_section_count,
        "verified_source_sha256": source.sha256,
        "editorial_apparatus_removed": True,
    }


def _require_unique_parsed_citations(
    provisions: Sequence[IsraelOpenLawProvision],
    source_id: str,
) -> None:
    paths = [provision.citation_path for provision in provisions]
    duplicates = sorted(path for path in set(paths) if paths.count(path) > 1)
    if duplicates:
        raise ValueError(
            f"Israel source {source_id} produced duplicate citation paths: "
            f"{', '.join(duplicates[:5])}"
        )


def _require_unique_citations(records: Sequence[ProvisionRecord]) -> None:
    paths = [record.citation_path for record in records]
    duplicates = sorted(path for path in set(paths) if paths.count(path) > 1)
    if duplicates:
        raise ValueError(
            f"Israel extraction produced duplicate citation paths: {', '.join(duplicates[:5])}"
        )
