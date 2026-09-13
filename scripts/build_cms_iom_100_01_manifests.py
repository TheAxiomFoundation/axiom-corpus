"""Build the corpus manifest for one CMS Internet-Only Manual (IOM) publication
(every chapter PDF), inventory the CMS IOM index, and update the Medicare agent
queue. Publications: Pub 100-01 Medicare General Information, Eligibility, and
Entitlement Manual (the default, the first family ingested), Pub 100-24 State
Payment of Medicare Premiums (the Part A/Part B buy-in manual), Pub 100-02
Medicare Benefit Policy Manual, Pub 100-04 Medicare Claims Processing Manual,
Pub 100-16 Medicare Managed Care Manual and Pub 100-18 Medicare Prescription
Drug Benefit Manual (2026-09-13 closure run, needs-closure-2026-09-11
MED-F-IOM-100-16 / MED-F-IOM-100-18).

Pub 100-16 numbers its cost-plan and special-plan chapters with letters
("Chapter 16a - Subchapter A - Private Fee-for-Service (PFFS) Plans"); the
chapter key keeps the letter (``chapter-16a``). Pub 100-18's IOM publication
page links only a two-page table of contents (``pub100_18.pdf``); the chapter
PDFs are posted on the publisher's Prescription Drug Benefit Manual page
(``Publication.chapter_page``), some without a ``.pdf`` extension
(``chapter7pdf``, ``r6pdbpdfpdf``), so a chapter-labelled link under
``/downloads/`` or ``/files/document/`` is a chapter when its bytes are a PDF.
Its chapter 9 is one document with Pub 100-16 chapter 21 and prints
"(Chapter 9 - Rev. 16, 01-11-13)" / "(Chapter 21 - Rev. 110, 01-11-13)"; the
transmittal regex accepts the chapter prefix and only lines naming the chapter
being built (or no chapter) count. Chapter 12 is a CMS Manual System
transmittal wrapping the chapter and prints no "Transmittals for Chapter" line;
the "Table of Contents" line is the header end then.

Primary official source: the CMS IOM index,
https://www.cms.gov/medicare/regulations-guidance/manuals/internet-only-manuals-ioms
(Centers for Medicare & Medicaid Services). The index lists one page per
publication; each publication page lists one PDF per chapter. Each chapter PDF
opens with a table of contents whose header prints the chapter's latest
transmittal ("(Rev. 12425; Issued: 12-21-23)", "(Rev. 7; Issued: 01-16-2025)");
that issued date becomes the chapter's expression_date. The body repeats every
section heading in bold, so extraction uses labeled_sections with
section_heading_requires_bold and a per-chapter start_after_pattern anchored on
the last table-of-contents line. The heading shape differs per publication:

* Pub 100-01 prints "10.1 - Inpatient Hospital Deductible" (label, spaced dash).
* Pub 100-24 prints "1.1 Definitions" (label, space) in chapter 1 and
  "2.2 - Frequency of ...", "2.2.1- State Input Files" (optional dash, optional
  spaces) in chapters 2-6; its appendices ("Appendix 5.A - Medicare Part A
  Premium Amount") are bold sections with their own transmittal lines and are
  labeled by the printed appendix code ("5.A"). Requiring the heading text to
  start with an upper-case letter or "(" keeps bold wrapped cross-references
  ("1.7 and 1.11 for more information ...", "00805.385 at https://...") out.
* Pub 100-02 and Pub 100-04 print "10.1 - Title" like Pub 100-01 in most
  sections, but individual chapters also print "100.1 Definition of AKI" (no
  dash), "40.7- Individuals ..." and "230.2.1– Chronic ..." (dash attached to
  the label), "20.3 -End Stage ..." (dash attached to the heading) and
  "20.4.3 -- TPNIES ..." (double dash), all bold and all followed by their
  transmittal line, so their pattern accepts every dash form and no dash. Top
  labels are one to three digits (Pub 100-04 chapter 1 opens with "01 -
  Foreword"), which keeps bold years ("2014 - ...") and HCPCS codes in tables
  out; a chapter whose table of contents lists no single-digit section gets a
  two-to-three-digit top label so bold table cells such as "1 - Community
  Early" (Pub 100-04 chapter 10) are not sections. Chapters whose bold tables
  still collide with the pattern carry an explicit override (Pub 100-04
  chapter 26 place-of-service codes, chapter 27 CWF response codes, chapter 32
  MSN message 23.17) and three chapters carry text replacements for labels the
  PDF prints with a stray space or dot ("30.2. 8 -", "100.6.1.", "40.8. -").
  The body may start before the first repeated label (Pub 100-02 chapter 17's
  TOC omits section 10; Pub 100-04 chapter 1's TOC ends with 130.7 while the
  body opens with 01 - Foreword), so the body also starts at the first bold
  heading followed by its transmittal line, whichever comes first.

cms.gov serves both HTML and PDF to the corpus user agent over a complete TLS
chain; no certificate bundle or browser impersonation is needed.

    uv run python scripts/build_cms_iom_100_01_manifests.py \
        [--publication 100-01|100-24|100-02|100-04] \
        [--download-dir ~/.axiom/cache/cms-iom-<pub>]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF, an axiom-corpus dependency
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://www.cms.gov"
INDEX = f"{BASE}/medicare/regulations-guidance/manuals/internet-only-manuals-ioms"
PAPER_INDEX = f"{BASE}/medicare/regulations-guidance/manuals/paper-based-manuals"
SOURCE_AS_OF = "2026-09-10"
USER_AGENT = "axiom-corpus/0.1 (source discovery)"
# site-wide footer link present on every cms.gov page; not a manual document
SITE_WIDE_LINKS = ("/files/document/agent/broker-help-desks.pdf",)
# IOM publications the Pub 100-01 run named as later families (not taken)
CANDIDATE_LATER_PUBLICATIONS = ("100-02", "100-04")

# Pub 100-01: "10 - Title", "10.1 - Title", "30.30.1.1 - Title"; a spaced dash
# keeps "10-foot", "1-800-MEDICARE", "100-01 - General Information" and
# "1966 - 1972" out. The bold requirement in the extraction config removes the
# remaining in-text references such as "40.2 - Shared System Maintainer" in an
# exhibit.
DASHED_HEADING_PATTERN = r"^(?P<label>\d+(?:\.\d+)*)\s+[-–—]\s*(?P<heading>[A-Za-z(].*)$"
# Pub 100-24: "1.0 Introduction", "2.2 - Frequency of ...", "2.2.1- State Input
# Files", "Appendix 5.A - Medicare Part A Premium Amount". Labels always carry
# a dot (chapter.section), so "1-800" style text never matches; the heading
# must start with an upper-case letter or "(" so bold wrapped cross-references
# ("1.7 and 1.11 for ...", "00805.385 at https://...") are not headings.
DOTTED_HEADING_PATTERN = (
    r"^(?:Appendix\s+)?(?P<label>\d+\.(?:\d+(?:\.\d+)*|[A-Z]))(?:\s+|\s*[-–—]\s*)(?P<heading>[A-Z(].*)$"
)
# Pub 100-02 / 100-04: "10.1 - Title", "100.1 Title", "40.7- Title",
# "20.3 -Title", "20.4.3 -- Title". The heading must start with an upper-case
# letter or "(" so "10-foot", "1-800-MEDICARE", "100-01 - General Information"
# and bold enumerations ("1. Content: ...") never match.
IOM_SEPARATORS = {
    "any": r"(?:\s*[-–—]+\s*|\s+)",
    "dash": r"\s*[-–—]+\s*",
    "spaced_dash": r"\s+[-–—]+\s+",
}
TOP_LABEL_ANY = r"\d{1,3}"
TOP_LABEL_TWO_PLUS = r"\d{2,3}"


def iom_heading_pattern(
    *,
    top_label: str = TOP_LABEL_ANY,
    form: str = "any",
    exclude_labels: tuple[str, ...] = (),
    heading_optional: bool = False,
) -> str:
    """Section-heading regex for the Pub 100-02 / 100-04 label shapes."""
    guard = "".join(rf"(?!{re.escape(label)}\b)" for label in exclude_labels)
    label = rf"(?P<label>{top_label}(?:\.\d+)*)"
    # Pub 100-16 and 100-18 print bold regulatory citations under some headings
    # ("42 CFR §422.158(e)", "42 C.F.R. §§ 422.503(b)(4)(vi)(G), ..."); a heading
    # never starts with "CFR" / "C.F.R.", so those lines stay in the body.
    tail = rf"{IOM_SEPARATORS[form]}(?P<heading>(?!C\.?\s?F\.?\s?R\.?\b)[A-Z(].*)"
    if heading_optional:
        tail = f"(?:{tail})?"
    return rf"^{guard}{label}{tail}$"


IOM_HEADING_PATTERN = iom_heading_pattern()
# A wrapped heading continues on the next line in Title Case ("Payer (D-SEP)",
# "or After October 1, 1983 Under PPS", "(Contractors)", "Services - General",
# "... Services - A Brief Description", "Columbia - General", "(MARx UI)"). The
# transmittal line that follows every heading ("(Rev. 1, 09-11-02)",
# "(Rev .11764; ...)", "(Rev.: 128, ...)", "(Rev. 6; Issued:04-26-24; ...)")
# and bold sub-captions ("A. General", "NOTE:", "POLICY") are excluded so they
# stay in the section body, and a line shaped like the next section heading
# ("10.1 - Inpatient Hospital Deductible" after a bare container heading with
# no transmittal line) is never absorbed.
_JOIN = (
    "(?:a|an|and|as|at|by|for|from|in|of|on|or|the|to|under|with|is|are|now|than|that|"
    "who|whom|which|when|where|not|yet|available)"
)
_WORD = rf"(?:\(?[A-Z0-9][^\s]*|[-–—]|{_JOIN}\b[^\s]*)"


DASHED_NEXT_HEADING_GUARD = r"(?!\d+(?:\.\d+)*\s+[-–—])"
# Pub 100-02 / 100-04 headings may follow the label with no dash, so a line
# shaped like "120- Title", "100.1 Title" or "20.3 -Title" is a heading too.
IOM_NEXT_HEADING_GUARD = r"(?!\d{1,3}(?:\.\d+)*(?:\s*[-–—]|\s+[A-Z]))"


def continuation_pattern(
    *, allow_single_letter_line: bool, next_heading_guard: str = DASHED_NEXT_HEADING_GUARD
) -> str:
    """Heading-continuation regex; the all-caps guard rejects bold captions
    ("POLICY", "NOTE"). Pub 100-24 chapter 2 wraps one heading onto a bare
    "A" line ("... Premium-Free Part" / "A"), so its variant lets a single
    capital letter through while still rejecting two or more."""
    caps_guard = r"(?![A-Z]{2,}:?$)" if allow_single_letter_line else r"(?![A-Z]+:?$)"
    # "(Chapter 21, Rev. 110, ...)" is the joint compliance chapter's transmittal line
    # (Pub 100-16 chapter 21 / Pub 100-18 chapter 9), excluded like "(Rev. ...)".
    return (
        rf"^(?P<heading>(?!\(Rev\b)(?!\(Chapter\b){next_heading_guard}(?![A-Z][.)\-–]\s)(?!NOTE\b){caps_guard}(?![A-Z][A-Z ]+$)"
        rf"{_WORD}(?:\s+{_WORD})*)$"
    )


HEADING_CONTINUATION_PATTERN = continuation_pattern(allow_single_letter_line=False)
SINGLE_LETTER_HEADING_CONTINUATION_PATTERN = continuation_pattern(allow_single_letter_line=True)
IOM_HEADING_CONTINUATION_PATTERN = continuation_pattern(
    allow_single_letter_line=False, next_heading_guard=IOM_NEXT_HEADING_GUARD
)
# TOC header transmittals: "(Rev. 12425; Issued: 12-21-23)", "(Rev. 4, 08-21-20)",
# "(Rev. 12421; Issued; 12-21-23)" (Pub 100-02 ch. 6), "(Rev. 12425 Issued:
# 12-21-23)" (ch. 7, no separator), "(Rev. 198, 11- 06-14)" (ch. 14, space in
# the date).
# Pub 100-18 chapter 9 / Pub 100-16 chapter 21 share one PDF and prefix each
# transmittal with its chapter: "(Chapter 9 - Rev. 16, 01-11-13)".
# Pub 100-16 prints "(Rev. 73, 09 30 05)" (spaces for dashes, chapter 15) and
# "Last Updated - Rev. 52, 05-07-04" (no parentheses, chapters 17a and 17c).
REV_RE = re.compile(
    r"(?:\(|Last Updated\s*[-–—]\s*)(?:Chapter\s+(?P<chapter>\d+[a-z]?)\s*[-–—]\s*)?Rev\.?\s*:?\s*(?P<rev>\d+)\s*[;,:]?\s*"
    r"(?:Issued\s*[:;]?\s*)?(?P<date>\d{1,2}\s?[-\s]\s?\d{1,2}\s?[-\s]\s?\d{2,4})"
)
# "Transmittals for Chapter N"; Pub 100-02 chapter 8 prints "Transmittals
# Issued for this Chapter".
TRANSMITTALS_RE = re.compile(r"^Transmittals (?:Issued )?for (?:this )?Chapter")
# "Chapter 16a - Subchapter A - ..." (Pub 100-16) keeps its letter; the Pub
# 100-18 page prints "Chapter 5-Benefits and Beneficiary Protection (v9.20.11) (PDF)".
CHAPTER_LINK_RE = re.compile(r"^Chapter\s*(?P<number>\d+[a-z]?)\s*[-–—]+\s*(?P<title>\S.*)$", re.I)
# trailing "(PDF)" and version tags "(v9.20.11)", "(v09 14 2018)" on the Pub 100-18 page
TITLE_TAG_RE = re.compile(r"\s*\((?:PDF|v\.?\s*[\d. ]+)\)\s*$", re.I)


def chapter_key(number: str) -> str:
    """'16a' -> '16a', '05' -> '5'."""
    match = re.match(r"^(\d+)([a-z]?)$", number.lower())
    assert match is not None, number
    return f"{int(match.group(1))}{match.group(2)}"


def chapter_sort_key(key: str) -> tuple[int, str]:
    match = re.match(r"^(\d+)([a-z]?)$", key)
    assert match is not None, key
    return int(match.group(1)), match.group(2)


def clean_chapter_title(title: str) -> tuple[str, str | None]:
    """Strip "(PDF)" and a version tag from a chapter link text; return (title, tag)."""
    tag = None
    while (match := TITLE_TAG_RE.search(title)) is not None:
        text = match.group(0).strip()
        if text.upper() != "(PDF)":
            tag = text.strip("()")
        title = title[: match.start()]
    return title.strip(), tag


@dataclass(frozen=True)
class ChapterOverride:
    """Per-chapter extraction settings a publication needs beyond the computed
    defaults; `reason` is recorded in the document metadata."""

    reason: str
    heading_form: str = "any"
    exclude_labels: tuple[str, ...] = ()
    heading_optional: bool = False
    extraction: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Publication:
    number: str
    version: str
    section_heading_pattern: str
    heading_continuation_pattern: str
    heading_style: str
    queue_note: str
    source_as_of: str = SOURCE_AS_OF
    run_note: str | None = None
    # Build each chapter's heading pattern from its TOC (two-to-three-digit top
    # labels when the TOC lists no single-digit section) and the overrides
    # below; False keeps section_heading_pattern verbatim (Pub 100-01, 100-24).
    adaptive_heading_pattern: bool = False
    chapter_overrides: dict[str, ChapterOverride] = field(default_factory=dict)
    # Pub 100-18: the IOM publication page links only a table of contents; the
    # chapter PDFs are on this publisher page instead.
    chapter_page: str | None = None
    chapter_page_note: str | None = None
    # chapter key -> reason: chapter PDFs that are one-page pointers to a document
    # published elsewhere (Pub 100-16 chapter 3), recorded as not taken.
    pointer_chapters: dict[str, str] = field(default_factory=dict)


IOM_100_02_QUEUE_NOTE = (
    "Pub 100-02 (Medicare Benefit Policy Manual, the benefit coverage rules) taken in full: 17 chapter PDFs "
    "from its publication page; the 16 per-chapter crosswalk PDFs on the same page are finding aids and are "
    "not taken. Chapter 7's TOC lists 30.2.8 Facsimile Signatures and chapter 11's TOC lists 100.6.1 Dialysis "
    "Modality; both are printed in the body with a stray space or dot in the label and are recovered with text "
    "replacements."
)
IOM_100_04_QUEUE_NOTE = (
    "Pub 100-04 (Medicare Claims Processing Manual) taken: 39 chapter PDFs (chapters 1-39) from its publication "
    "page; the two 'Chapter 21 - Medicare Summary Notices - English/Spanish Exhibits' links are ZIP bundles of "
    "MSN exhibit images, not chapter text, and the 29 per-chapter crosswalk PDFs are finding aids; none of those "
    "are taken. Several chapter TOCs list sections the body no longer prints (for example chapter 8's 50.1.5 to "
    "100.3 and chapter 18's 1 and 1.1); the body governs."
)

PUBLICATIONS = {
    "100-01": Publication(
        number="100-01",
        version="2026-09-10-medicare-cms-iom-100-01",
        section_heading_pattern=DASHED_HEADING_PATTERN,
        heading_continuation_pattern=HEADING_CONTINUATION_PATTERN,
        heading_style="bold 'N - Title' headings; the body starts after the table of contents",
        queue_note=(
            "Family: CMS Internet-Only Manuals. Pub 100-01 (Medicare General Information, Eligibility and "
            "Entitlement Manual) taken in full: 7 chapter PDFs from the publication page listed on the IOM index; "
            "the Crosswalks PDF on the same page is a finding aid, not a chapter, and is not taken. The existing "
            "us/guidance/cms/original-medicare-part-a-b scope is not re-ingested. Pub 100-02 (Benefit Policy), "
            "Pub 100-04 (Claims Processing) and Pub 45 (State Medicaid Manual) are candidate later families; "
            "cms.gov fact sheets, medicare.gov pages, SSA POMS and state pages on the lead list are not CMS "
            "manuals and stay out of this family."
        ),
    ),
    "100-24": Publication(
        number="100-24",
        version="2026-09-10-medicare-cms-iom-100-24",
        section_heading_pattern=DOTTED_HEADING_PATTERN,
        heading_continuation_pattern=SINGLE_LETTER_HEADING_CONTINUATION_PATTERN,
        heading_style=(
            "bold 'N.N Title' / 'N.N - Title' headings and bold 'Appendix N.X - Title' appendices; "
            "the body starts after the table of contents"
        ),
        queue_note=(
            "Pub 100-24 (State Payment of Medicare Premiums, the Part A/Part B buy-in manual) taken in full: "
            "6 chapter PDFs from its publication page; the '100-24 Table of Contents' PDF on the same page is a "
            "finding aid, not a chapter, and is not taken. Its appendices (1.A-1.D, 5.A-5.D, 6.A-6.B) are bold "
            "sections with their own transmittal lines and are emitted as sections labeled by appendix code."
        ),
    ),
    "100-02": Publication(
        number="100-02",
        version="2026-09-11-medicare-cms-iom-100-02",
        section_heading_pattern=IOM_HEADING_PATTERN,
        heading_continuation_pattern=IOM_HEADING_CONTINUATION_PATTERN,
        heading_style=(
            "bold 'N - Title' headings (a few chapters print 'N Title', 'N- Title' or 'N -- Title'); "
            "the body starts after the table of contents"
        ),
        queue_note=IOM_100_02_QUEUE_NOTE,
        source_as_of="2026-09-11",
        run_note="docs/ingest-runs/2026-09-11-medicare-cms-iom-100-02-100-04.md",
        adaptive_heading_pattern=True,
        chapter_overrides={
            "7": ChapterOverride(
                reason="the body prints section 30.2.8 as '30.2. 8 - Facsimile Signatures' (space inside the label)",
                extraction={"text_replacements": {"30.2. 8 - Facsimile Signatures": "30.2.8 - Facsimile Signatures"}},
            ),
            "11": ChapterOverride(
                reason="the body prints section 100.6.1 as '100.6.1. Dialysis Modality' (trailing dot on the label)",
                extraction={"text_replacements": {"100.6.1. Dialysis Modality": "100.6.1 - Dialysis Modality"}},
            ),
            "15": ChapterOverride(
                reason=(
                    "section 320.7.1 prints its bold label alone with '- Determining Qualifying Home Infusion "
                    "Drugs' on the next line; a bare label is a heading only when the next line starts with a dash"
                ),
                heading_optional=True,
                extraction={
                    "label_only_heading_pattern": r"^[-–—]\s*[A-Z(].*$",
                    "label_only_requires_heading": True,
                },
            ),
        },
    ),
    "100-16": Publication(
        number="100-16",
        version="2026-09-13-medicare-cms-iom-100-16",
        section_heading_pattern=IOM_HEADING_PATTERN,
        heading_continuation_pattern=IOM_HEADING_CONTINUATION_PATTERN,
        heading_style=(
            "bold 'N – Title' headings (some sections print 'N– Title' or 'N Title'); lettered chapters "
            "(16a, 16b, 17a-17f, 18a-18c) keep their letter in the chapter key; the body starts after the table "
            "of contents"
        ),
        queue_note=(
            "Pub 100-16 (Medicare Managed Care Manual, the Part C eligibility, enrollment, benefits and beneficiary "
            "protection rules) taken as posted: 25 chapter PDFs on its publication page (chapters 1, 3-15, 16a, 16b, "
            "17a-17d, 17f, 18a-18c, 21; chapters 2, 17e, 19 and 20 are not posted), of which 23 carry text; chapters 3 "
            "(marketing) and 13 (grievances and appeals) are one-page pointers to standalone cms.gov guidance and are "
            "recorded, not taken. Chapter 21 is the joint compliance program chapter also posted as Pub 100-18 "
            "chapter 9. 2026-09-13 closure run (needs-closure-2026-09-11 MED-F-IOM-100-16)."
        ),
        source_as_of="2026-09-13",
        run_note="docs/ingest-runs/2026-09-13-federal-guidance-layer.md",
        adaptive_heading_pattern=True,
        pointer_chapters={
            "3": (
                "one-page pointer: the chapter text (Medicare Marketing Guidelines) is published as the standalone "
                "Medicare Communications and Marketing Guidelines on cms.gov, not in the PDF"
            ),
            "13": (
                "one-page pointer: the chapter text is published as the standalone Parts C & D Enrollee Grievances, "
                "Organization/Coverage Determinations, and Appeals Guidance on cms.gov, not in the PDF"
            ),
        },
    ),
    "100-18": Publication(
        number="100-18",
        version="2026-09-13-medicare-cms-iom-100-18",
        section_heading_pattern=IOM_HEADING_PATTERN,
        heading_continuation_pattern=IOM_HEADING_CONTINUATION_PATTERN,
        heading_style=(
            "bold 'N - Title' / 'N – Title' headings (chapter 13 prints 'N- Title'); chapters 5 and 12 open with "
            "a transmittal cover letter before the table of contents; the body starts after the table of contents"
        ),
        queue_note=(
            "Pub 100-18 (Medicare Prescription Drug Benefit Manual: Part D benefits, formulary, LIS, coordination "
            "of benefits) taken as posted: the IOM publication page links only the two-page table of contents "
            "(pub100_18.pdf, not a chapter and not taken); the chapter PDFs (5, 6, 7, 9, 12, 13, 14) are on the "
            "publisher's Prescription Drug Benefit Manual page. Chapters 1, 8, 16 and 17 are reserved; 10, 11 and "
            "15 have not been disseminated via Pub 100-18; chapter 2 (communications and marketing), chapter 3 "
            "(eligibility and enrollment) and chapter 4 (creditable coverage) are published as standalone CMS "
            "guidance documents (Medicare Communications and Marketing Guidelines, the CY C/D Enrollment and "
            "Disenrollment Guidance, the creditable-coverage guidance pages), not as manual chapters; chapter 18 "
            "is the Parts C & D Enrollee Grievances, Organization/Coverage Determinations, and Appeals Guidance "
            "linked on the same page and is recorded, not taken as a chapter. 2026-09-13 closure run "
            "(needs-closure-2026-09-11 MED-F-IOM-100-18)."
        ),
        source_as_of="2026-09-13",
        run_note="docs/ingest-runs/2026-09-13-federal-guidance-layer.md",
        adaptive_heading_pattern=True,
        chapter_overrides={
            "13": ChapterOverride(
                reason=(
                    "the body prints section 30.2 as '30.1- Partial Subsidy Eligible Individuals' (the label of the "
                    "preceding section repeated; the TOC and the section text are 30.2)"
                ),
                extraction={
                    "text_replacements": {
                        "30.1- Partial Subsidy Eligible Individuals": "30.2 - Partial Subsidy Eligible Individuals"
                    }
                },
            ),
        },
        chapter_page=f"{BASE}/medicare/coverage/prescription-drug-coverage-contracting/prescription-drug-benefit-manual",
        chapter_page_note=(
            "CMS Prescription Drug Benefit Manual page (the publisher's chapter listing; the IOM publication page "
            "cms050485 links only the table of contents PDF)"
        ),
    ),
    "100-04": Publication(
        number="100-04",
        version="2026-09-11-medicare-cms-iom-100-04",
        section_heading_pattern=IOM_HEADING_PATTERN,
        heading_continuation_pattern=IOM_HEADING_CONTINUATION_PATTERN,
        heading_style=(
            "bold 'N - Title' headings (some chapters print 'N Title', 'N- Title' or 'N -Title'; chapter 1 "
            "opens with '01 - Foreword'); the body starts after the table of contents"
        ),
        queue_note=IOM_100_04_QUEUE_NOTE,
        source_as_of="2026-09-11",
        run_note="docs/ingest-runs/2026-09-11-medicare-cms-iom-100-02-100-04.md",
        adaptive_heading_pattern=True,
        chapter_overrides={
            "12": ChapterOverride(
                reason="the body prints section 40.8 as '40.8. - Claims for Co-Surgeons ...' (trailing dot on the label)",
                extraction={
                    "text_replacements": {
                        "40.8. - Claims for Co-Surgeons and Team Surgeons": "40.8 - Claims for Co-Surgeons and Team Surgeons"
                    }
                },
            ),
            "26": ChapterOverride(
                reason=(
                    "the place-of-service code table prints bold 'NN Name (date)' rows; every section heading in "
                    "this chapter uses a dash, so the dash is required"
                ),
                heading_form="dash",
            ),
            "27": ChapterOverride(
                reason=(
                    "the CWF response-code table prints bold 'NN -Description' rows and a bold '837 Professional "
                    "Claims' caption; every section heading in this chapter uses a spaced dash, so it is required"
                ),
                heading_form="spaced_dash",
            ),
            "32": ChapterOverride(
                reason=(
                    "MSN message 23.17 is printed bold in English and Spanish under the surgical-error denial "
                    "instructions; it is a message number, not a section"
                ),
                exclude_labels=("23.17",),
            ),
        },
    ),
}


def fetch(session: requests.Session, url: str) -> requests.Response:
    resp = session.get(url, timeout=120)
    resp.raise_for_status()
    return resp


def links(page: str) -> list[tuple[str, str]]:
    out = []
    for href, text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text))).strip()
        out.append((href if href.startswith("http") else BASE + href, text))
    return out


def index_rows(page: str) -> list[dict[str, str]]:
    """Publication rows of a CMS manuals index table: number, title, page URL."""
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [
            re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(cell))).strip()
            for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        ]
        hrefs = re.findall(r'href="([^"]+)"', row)
        if len(cells) < 2 or not hrefs:
            continue
        number = re.sub(r"^Publication #\s*", "", cells[0]).strip()
        title = re.sub(r"^Title\s*", "", cells[1]).strip()
        if not re.match(r"^\d", number):
            continue
        href = hrefs[0]
        rows.append({"publication": number, "title": title, "url": href if href.startswith("http") else BASE + href})
    return rows


def publication_documents(page: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (chapter links, other download links) on one publication page."""
    chapters, other = [], []
    for href, text in links(page):
        path = href.removeprefix(BASE)
        is_chapter = CHAPTER_LINK_RE.match(text) is not None
        is_download = "/manuals/downloads/" in path.lower() or path.lower().endswith((".pdf", ".zip"))
        # Pub 100-18 chapter links without a file extension: /downloads/dwnlds/chapter7pdf
        if is_chapter and ("/downloads/" in path.lower() or "/files/document/" in path.lower()):
            is_download = True
        if not is_download or path in SITE_WIDE_LINKS:
            continue
        (chapters if is_chapter else other).append((href, text))
    return chapters, other


def normalized_lines(document: fitz.Document) -> list[tuple[str, int, bool]]:
    """Text lines the same way the official-documents extractor sees them, with
    the bold flag of each line's first span (paired by occurrence, as the
    extractor does for section_heading_requires_bold)."""
    out = []
    for page_index, page in enumerate(document, start=1):
        styles: dict[str, list[bool]] = {}
        for block in page.get_text("dict").get("blocks", ()):
            for span_line in block.get("lines", ()):
                spans = span_line.get("spans", ())
                first_span = next((span for span in spans if str(span.get("text", "")).strip()), None)
                if first_span is None:
                    continue
                text = " ".join("".join(str(span.get("text", "")) for span in spans).split())
                if text:
                    styles.setdefault(text, []).append(bool(int(first_span.get("flags", 0)) & fitz.TEXT_FONT_BOLD))
        occurrences: dict[str, int] = {}
        for raw in page.get_text("text").splitlines():
            line = " ".join(raw.split())
            if not line:
                continue
            occurrence = occurrences.get(line, 0)
            occurrences[line] = occurrence + 1
            if re.match(r"^Page \d+$", line):
                continue
            line_styles = styles.get(line, ())
            out.append((line, page_index, line_styles[occurrence] if occurrence < len(line_styles) else False))
    return out


def chapter_facts(pdf_path: Path, heading_re: re.Pattern[str], chapter: str | None = None) -> dict[str, Any]:
    """Latest TOC transmittal, last TOC line, TOC labels and page count of one
    chapter PDF."""
    with fitz.open(pdf_path) as document:
        page_count = len(document)
        lines = normalized_lines(document)
    # The TOC header (before "Transmittals for Chapter N") prints the chapter's
    # latest transmittal; Pub 100-01 chapter 6 prints two, so take the latest
    # issued date. Pub 100-18 chapter 12 (a CMS Manual System transmittal
    # wrapping the chapter) prints no "Transmittals for Chapter" line; its
    # "Table of Contents" line ends the header instead.
    header_end = next((i for i, (line, _, _) in enumerate(lines) if TRANSMITTALS_RE.match(line)), None)
    header_rule = "Transmittals for Chapter line"
    if header_end is None:
        header_end = next((i for i, (line, _, _) in enumerate(lines) if line == "Table of Contents"), None)
        header_rule = "Table of Contents line (no Transmittals for Chapter line)"
    if header_end is None:
        raise RuntimeError(f"{pdf_path.name}: no 'Transmittals for Chapter' or 'Table of Contents' line in the TOC header")
    transmittals = []
    # With the "Table of Contents" fallback the transmittal line follows the anchor
    # ("Table of Contents" / "(Rev.6, 11-07-08)" in Pub 100-18 chapter 12), so the
    # header window extends to the first heading-shaped TOC line.
    header_scan = header_end
    if header_rule != "Transmittals for Chapter line":
        header_scan = next(
            (i for i in range(header_end, len(lines)) if heading_re.match(lines[i][0])), header_end
        )
    def read_transmittals(window: list[tuple[str, int, bool]]) -> list[tuple[dt.date, int, str]]:
        found = []
        for line, _, _ in window:
            for match in REV_RE.finditer(line):
                if match.group("chapter") and chapter is not None and chapter_key(match.group("chapter")) != chapter:
                    continue  # the joint compliance chapter names the other manual's chapter too
                month, day, year = re.split(r"[-\s]+", match.group("date").strip())
                year_full = int(year) if len(year) == 4 else 2000 + int(year)
                found.append((dt.date(year_full, int(month), int(day)), int(match.group("rev")), line))
        return found

    transmittals = read_transmittals(lines[:header_scan])
    transmittal_source = "TOC header"
    if not transmittals:
        # Pub 100-16 chapters 18a and 18c print no transmittal in the TOC header;
        # every section carries one, so the latest section transmittal dates the chapter.
        transmittals = read_transmittals(lines[header_scan:])
        transmittal_source = "latest section transmittal line (no transmittal in the TOC header)"
    # The TOC repeats every heading, so the body starts where the first TOC
    # heading label reappears. When the TOC omits the chapter's first sections
    # (Pub 100-02 chapter 17 lists nothing before section 20) or its order
    # differs from the body (Pub 100-04 chapter 1's TOC ends with 130.7 while
    # the body opens with "01 - Foreword"), the body starts at the first bold
    # heading followed by its "(Rev. ...)" transmittal line, allowing up to
    # two wrapped heading lines in between but no further heading-shaped line
    # (recently added TOC entries are bold too, and the last one sits right
    # above the first body heading and its transmittal line); the earlier of
    # the two wins. The line before is the last TOC line, the start_after
    # anchor.
    seen: dict[str, int] = {}
    first_repeat = None
    for i, (line, _, _) in enumerate(lines):
        match = heading_re.match(line)
        if match is None:
            continue
        if match.group("label") in seen:
            first_repeat = i
            break
        seen[match.group("label")] = i
    def followed_by_transmittal(index: int) -> bool:
        for j in range(index + 1, min(index + 4, len(lines))):
            if lines[j][0].startswith("(Rev"):
                return True
            if heading_re.match(lines[j][0]):
                return False
        return False

    first_bold_with_transmittal = next(
        (
            i
            for i in range(header_end + 1, len(lines))
            if lines[i][2] and heading_re.match(lines[i][0]) and followed_by_transmittal(i)
        ),
        None,
    )
    candidates = [i for i in (first_repeat, first_bold_with_transmittal) if i is not None]
    if not candidates:
        raise RuntimeError(f"{pdf_path.name}: could not find where the body restarts after the TOC")
    body_start = min(candidates)
    last_toc_line = lines[body_start - 1][0]
    anchor_note = None
    earlier = sum(1 for line, _, _ in lines[:body_start - 1] if line == last_toc_line)
    if earlier:
        # Pub 100-16 chapter 16a ends its TOC with the wrapped fragment "Network PFFS
        # Plan", which three TOC entries share; the extractor starts after the first
        # line matching the anchor, so the anchor walks back to the nearest unique TOC
        # line and the fragments that follow it sit before the first bold heading.
        for back in range(2, 5):
            candidate = lines[body_start - back][0]
            if not any(line == candidate for line, _, _ in lines[:body_start - back]):
                anchor_note = (
                    f"last TOC line {last_toc_line!r} also appears earlier in the TOC; the anchor is the "
                    f"unique TOC line {back - 1} line(s) before it, so {back - 1} wrapped TOC fragment(s) precede "
                    "the first bold heading"
                )
                last_toc_line = candidate
                break
        else:
            raise RuntimeError(f"{pdf_path.name}: last TOC line {last_toc_line!r} also appears earlier")
    toc_labels = [label for label, index in seen.items() if index < body_start]
    return {
        "page_count": page_count,
        "toc_section_count": len(toc_labels),
        "toc_labels": toc_labels,
        "body_start_page": lines[body_start][1],
        "body_start_rule": (
            "first repeated label"
            if body_start == first_repeat
            else "first bold heading followed by its transmittal line"
        ),
        "last_toc_line": last_toc_line,
        "header_rule": header_rule,
        "anchor_note": anchor_note,
        "transmittal_source": transmittal_source,
        "transmittals": sorted(transmittals),
    }


def chapter_heading_settings(
    publication: Publication, number: str, facts: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The chapter's section-heading extraction keys and the metadata that
    explains them."""
    override = publication.chapter_overrides.get(number)
    if not publication.adaptive_heading_pattern:
        if override is not None:
            raise ValueError(f"chapter overrides need adaptive_heading_pattern (Pub {publication.number})")
        return {"section_heading_pattern": publication.section_heading_pattern}, {}
    single_digit_toc = any(re.match(r"^\d(?:\.|$)", label) for label in facts["toc_labels"])
    top_label = TOP_LABEL_ANY if single_digit_toc else TOP_LABEL_TWO_PLUS
    extraction: dict[str, Any] = {
        "section_heading_pattern": iom_heading_pattern(
            top_label=top_label,
            form=override.heading_form if override else "any",
            exclude_labels=override.exclude_labels if override else (),
            heading_optional=override.heading_optional if override else False,
        )
    }
    metadata: dict[str, Any] = {
        "toc_lists_single_digit_sections": single_digit_toc,
        "heading_label_form": "one to three digit top label" if single_digit_toc else "two to three digit top label",
    }
    if override is not None:
        extraction.update(override.extraction)
        metadata["extraction_override"] = override.reason
    return extraction, metadata


def build_documents(
    session: requests.Session,
    publication: Publication,
    pub_row: dict[str, str],
    chapter_links: list[tuple[str, str]],
    download_dir: Path,
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """One manifest document per chapter PDF of the publication page, plus the
    chapter-labelled links that are not chapter PDFs (with the reason)."""
    heading_re = re.compile(publication.section_heading_pattern)
    download_dir.mkdir(parents=True, exist_ok=True)
    documents = []
    skipped: list[tuple[str, str]] = []
    for href, text in chapter_links:
        match = CHAPTER_LINK_RE.match(text)
        assert match is not None
        key = chapter_key(match.group("number"))
        chapter_title, version_tag = clean_chapter_title(match.group("title"))
        if key in publication.pointer_chapters:
            skipped.append((text, publication.pointer_chapters[key]))
            continue
        if href.lower().endswith(".zip"):
            # Pub 100-04 lists "Chapter 21 - ... English/Spanish Exhibits" ZIP
            # bundles beside the chapter PDFs; the extractor reads PDF only and
            # the exhibits are MSN images, not chapter text.
            skipped.append((text, "ZIP bundle, not a chapter PDF"))
            continue
        file_name = href.rsplit("/", 1)[-1]
        pdf_path = download_dir / (file_name if file_name.lower().endswith(".pdf") else f"{file_name}.pdf")
        last_modified = None
        if not pdf_path.exists():
            resp = fetch(session, href)
            if not resp.content.startswith(b"%PDF"):
                skipped.append((text, f"not a PDF ({resp.headers.get('Content-Type', 'unknown type')})"))
                continue
            pdf_path.write_bytes(resp.content)
            last_modified = resp.headers.get("Last-Modified")
        else:
            # cms.gov does not answer HEAD with Last-Modified; open a streamed GET
            # and close it without reading the body.
            with session.get(href, timeout=60, stream=True) as resp:
                last_modified = resp.headers.get("Last-Modified") if resp.ok else None
        facts = chapter_facts(pdf_path, heading_re, key)
        if facts["transmittals"]:
            issued, rev, rev_line = facts["transmittals"][-1]
            expression_date = issued.isoformat()
            expression_source = f"{facts['transmittal_source']} {rev_line!r}"
            latest_transmittal = f"Rev. {rev}, issued {issued.isoformat()}"
        else:
            expression_date = publication.source_as_of
            expression_source = "no transmittal date printed in the TOC header; source_as_of used"
            latest_transmittal = None
        heading_extraction, heading_metadata = chapter_heading_settings(publication, key, facts)
        metadata = {
            "primary_source": True,
            "source_authority": "Centers for Medicare & Medicaid Services",
            "document_subtype": "internet_only_manual_chapter",
            "program": "MEDICARE",
            "publication": publication.number,
            "publication_title": pub_row["title"],
            "publication_page": pub_row["url"],
            "chapter": int(key) if key.isdigit() else key,
            "chapter_title": chapter_title,
            "latest_transmittal": latest_transmittal,
            "expression_date_source": expression_source,
            "pdf_page_count": facts["page_count"],
            "body_start_page": facts["body_start_page"],
            "toc_section_count": facts["toc_section_count"],
            "body_start_rule": facts["body_start_rule"],
            **heading_metadata,
            "extraction_granularity": "numbered_section",
            "source_discovery_group": f"us/manual/cms-iom-{publication.number}",
            "discovered_via": f"manual-review:medicare-agent-queue; index {INDEX}; publication page {pub_row['url']}",
        }
        if last_modified:
            metadata["http_last_modified"] = last_modified
        if version_tag:
            metadata["chapter_page_version_tag"] = version_tag
        if publication.chapter_page:
            metadata["chapter_page"] = publication.chapter_page
            metadata["chapter_page_note"] = publication.chapter_page_note
        if facts["header_rule"] != "Transmittals for Chapter line":
            metadata["toc_header_rule"] = facts["header_rule"]
        if facts["anchor_note"]:
            metadata["toc_anchor_note"] = facts["anchor_note"]
        documents.append(
            {
                "source_id": f"us-cms-iom-{publication.number}-chapter-{key}",
                "jurisdiction": "us",
                "document_class": "manual",
                "title": f"CMS Pub {publication.number} {pub_row['title']}, Chapter {key} - {chapter_title}",
                "source_url": href,
                "source_format": "pdf",
                "source_as_of": publication.source_as_of,
                "expression_date": expression_date,
                "citation_path": f"us/manual/cms/iom/{publication.number}/chapter-{key}",
                "extraction": {
                    "segmentation": "labeled_sections",
                    **heading_extraction,
                    "section_heading_requires_bold": True,
                    "heading_continuation_pattern": publication.heading_continuation_pattern,
                    # skip the table of contents, which repeats every heading
                    "start_after_pattern": "^" + re.escape(facts["last_toc_line"]) + "$",
                },
                "metadata": metadata,
            }
        )
    documents.sort(key=lambda doc: chapter_sort_key(str(doc["metadata"]["chapter"])))
    return documents, skipped


def family_status(entry: dict[str, Any], taken: set[str]) -> str:
    if entry["publication"] in taken:
        return "taken"
    if entry["chapter_count"] == 0 and entry["other_document_count"] == 0:
        return "no_documents"
    if entry["chapter_count"] == 0:
        return "whole_manual_download_only"
    if entry["publication"] in CANDIDATE_LATER_PUBLICATIONS:
        return "candidate_later_family"
    return "not_taken"


def update_queue(
    queue_path: Path,
    publication: Publication,
    pub_row: dict[str, str],
    chapter_links: list[tuple[str, str]],
    other_links: list[tuple[str, str]],
    skipped_chapters: list[tuple[str, str]],
    documents: list[dict[str, Any]],
    manifest_name: str,
    publications_on_index: int,
    inventory: list[dict[str, Any]],
    paper_inventory: list[dict[str, Any]],
) -> dict[str, int]:
    """Extend the single federal row: one entry per taken publication."""
    queue = yaml.safe_load(queue_path.read_text())
    rows = {s["jurisdiction"]: s for s in queue["states"]}
    row = rows["us"]
    taken = {e["publication"] for e in row.get("index_inventory", []) if e.get("taken")}
    taken |= {p["publication"] for p in row.get("publications", [])}
    taken.add(publication.number)
    for entry in inventory:
        entry["taken"] = entry["publication"] in taken
    publication_record = {
        "publication": publication.number,
        "title": pub_row["title"],
        "url": pub_row["url"],
        "target_manifest": f"manifests/{manifest_name}",
        "target_scope": {"jurisdiction": "us", "document_class": "manual", "version": publication.version},
        "document_count": len(chapter_links) + len(other_links),
        "chapter_count": len(chapter_links),
        "chapters_taken": len(documents),
        "not_taken": [text for _href, text in other_links]
        + [f"{text} ({reason})" for text, reason in skipped_chapters],
        "heading_style": publication.heading_style,
        "run_note": publication.run_note or f"docs/ingest-runs/{publication.version}.md",
    }
    if publication.chapter_page:
        publication_record["chapter_page"] = publication.chapter_page
        publication_record["chapter_page_note"] = publication.chapter_page_note
    publications = [p for p in row.get("publications", []) if p["publication"] != publication.number]
    publications.append(publication_record)
    publications.sort(key=lambda p: p["publication"])
    if publication.number == "100-01" or "target_manifest" not in row:
        # first family: the row's singular keys describe it
        row.update(
            {
                "source_kind": "official_pdf_manual_chapters",
                "primary_source_url": pub_row["url"],
                "target_manifest": f"manifests/{manifest_name}",
                "target_scope": publication_record["target_scope"],
                "publication_page": {
                    key: publication_record[key]
                    for key in ("url", "document_count", "chapter_count", "chapters_taken", "not_taken")
                },
            }
        )
    notes = str(row.get("notes") or "")
    if publication.queue_note not in notes:
        notes = f"{notes} {publication.queue_note}".strip()
    row.update(
        {
            "queue_status": "agent_ready",
            "index_url": INDEX,
            "index_document_count": publications_on_index,
            "taken_count": len(taken),
            "publications": publications,
            "index_families": [
                {
                    "publication": entry["publication"],
                    "title": entry["title"],
                    "chapter_count": entry["chapter_count"],
                    "status": family_status(entry, taken),
                    **(
                        {
                            "target_manifest": p["target_manifest"],
                            "version": p["target_scope"]["version"],
                        }
                        if (p := next((p for p in publications if p["publication"] == entry["publication"]), None))
                        else {}
                    ),
                }
                for entry in inventory
            ],
            "index_inventory": inventory,
            "paper_based_manuals": {"index_url": PAPER_INDEX, "publications": paper_inventory},
            "notes": notes,
        }
    )
    queue["states"] = [rows[j] for j in sorted(rows, key=lambda j: (j != "us", j))]
    queue["status_counts"] = {}
    for s in queue["states"]:
        queue["status_counts"][s["queue_status"]] = queue["status_counts"].get(s["queue_status"], 0) + 1
    queue["queue_status"] = "in_progress"
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]



# ---------------------------------------------------------------- territories (2026-09-11 pass)
# Medicare is federally administered in every territory (42 U.S.C. 1395x(x) includes Puerto Rico, the
# Virgin Islands, Guam, American Samoa and the Northern Mariana Islands in "United States" for title
# XVIII); no territory agency publishes a Medicare eligibility document, and the governing manual is the
# Pub 100-01 scope already in the corpus. One done-by-pointer row per territory, applied with
# --territory-rows (no cms.gov fetch, no manifest change).
IOM_100_01_PAGE = f"{BASE}/regulations-and-guidance/guidance/manuals/internet-only-manuals-ioms-items/cms050111"
IOM_100_01_SCOPE = {"jurisdiction": "us", "document_class": "manual", "version": "2026-09-10-medicare-cms-iom-100-01"}
TERRITORY_POINTERS = {
    "us-pr": ("Puerto Rico", "us/manual/cms/iom/100-01/chapter-2/40.2 (automatic SMI enrollment does not apply to residents of Puerto Rico) and chapter-1 (entitlement)"),
    "us-gu": ("Guam", "us/manual/cms/iom/100-01/chapter-1 and chapter-2 (entitlement and enrollment; no Guam-specific section)"),
    "us-vi": ("Virgin Islands", "us/manual/cms/iom/100-01/chapter-1 and chapter-2 (entitlement and enrollment; no Virgin Islands-specific section)"),
    "us-as": ("American Samoa", "us/manual/cms/iom/100-01/chapter-1 and chapter-2 (entitlement and enrollment; no American Samoa-specific section)"),
    "us-mp": ("Northern Mariana Islands", "us/manual/cms/iom/100-01/chapter-1 and chapter-2 (entitlement and enrollment; no Northern Mariana Islands-specific section)"),
}


def apply_territory_rows(queue_path: Path, only: set[str] | None = None) -> dict[str, int]:
    queue = yaml.safe_load(queue_path.read_text())
    rows = {s["jurisdiction"]: s for s in queue["states"]}
    for jur, (name, pointer) in TERRITORY_POINTERS.items():
        if only and jur not in only:
            continue
        row = rows.get(jur) or {"jurisdiction": jur, "name": name, "lead_counts": {}, "candidate_sources": []}
        row.update(
            {
                "queue_status": "done",
                "source_kind": "federal_manual_pointer",
                "primary_source_url": IOM_100_01_PAGE,
                "target_manifest": "manifests/us-cms-iom-100-01.yaml",
                "target_scope": dict(IOM_100_01_SCOPE),
                "index_url": INDEX,
                "index_document_count": 0,
                "taken_count": 0,
                "pointer": pointer,
                "index_families": (
                    "no territory Medicare document family: Medicare is federally administered and the territory "
                    "publishes no eligibility document; the CMS Pub 100-01 family is already in the corpus"
                ),
                "notes": (
                    f"Done by pointer (2026-09-11 territories pass): Medicare operates in {name} as federal law "
                    "(42 U.S.C. 1395x(x) counts the territories as part of the United States for title XVIII; the "
                    "section is not in the corpus). No territory agency publishes a Medicare eligibility or entitlement "
                    "document (reviewed 2026-09-11: the territory health, human-services and Medicaid publishers list "
                    "only SHIP counseling notices and Part D information sheets), so the governing text is CMS Pub "
                    "100-01 (Medicare General Information, Eligibility and Entitlement Manual), extracted in full on "
                    "2026-09-10 (7 chapters, 341 provisions). Nothing was fetched."
                ),
            }
        )
        rows[jur] = row
    queue["states"] = [rows[j] for j in sorted(rows, key=lambda j: (j != "us", j))]
    queue["status_counts"] = {}
    for s in queue["states"]:
        queue["status_counts"][s["queue_status"]] = queue["status_counts"].get(s["queue_status"], 0) + 1
    queue["queue_status"] = "in_progress"
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--publication",
        choices=sorted(PUBLICATIONS),
        default="100-01",
        help="IOM publication number to build the manifest for",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=None,
        help="where chapter PDFs are cached while computing per-chapter extraction settings "
        "(default ~/.axiom/cache/cms-iom-<publication>)",
    )
    parser.add_argument("--territory-rows", action="store_true",
                        help="apply only the five territory done-by-pointer rows to the queue (no cms.gov fetch)")
    parser.add_argument("--only", help="comma-separated jurisdictions to apply with --territory-rows")
    args = parser.parse_args()
    if args.territory_rows:
        only = set(args.only.split(",")) if args.only else None
        counts = apply_territory_rows(ROOT / "manifests" / "medicare-agent-queue.yaml", only)
        print(f"territory rows applied; queue {counts}")
        return 0
    publication = PUBLICATIONS[args.publication]
    download_dir = args.download_dir or Path.home() / ".axiom" / "cache" / f"cms-iom-{publication.number}"
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    # 1. The publisher's own index: every publication, with chapter counts.
    publications = index_rows(fetch(session, INDEX).text)
    if len(publications) < 20:
        print(f"only {len(publications)} publications on the IOM index; layout changed?", file=sys.stderr)
        return 1
    inventory = []
    taken_row = None
    for row in publications:
        chapters, other = publication_documents(fetch(session, row["url"]).text)
        crosswalks = [text for _href, text in other if re.match(r"^Chapter \d+ Crosswalk$", text)]
        other_documents = [text for _href, text in other if text not in crosswalks]
        if crosswalks:
            other_documents.append(f"{len(crosswalks)} per-chapter crosswalks")
        entry = {
            **row,
            "chapter_count": len(chapters),
            "other_document_count": len(other),
            "other_documents": other_documents,
            "taken": row["publication"] == publication.number,
        }
        inventory.append(entry)
        if entry["taken"]:
            taken_row = (row, chapters, other)
    if taken_row is None:
        print(f"Pub {publication.number} is not on the IOM index", file=sys.stderr)
        return 1
    paper_rows = index_rows(fetch(session, PAPER_INDEX).text)
    paper_inventory = []
    for row in paper_rows:
        chapters, other = publication_documents(fetch(session, row["url"]).text)
        paper_inventory.append(
            {**row, "chapter_count": len(chapters), "other_document_count": len(other), "taken": False}
        )

    # 2. The publication: one document per chapter PDF (Pub 100-18: from the
    # publisher's chapter page; the IOM page's table-of-contents PDF is recorded
    # as not taken).
    pub_row, chapter_links, other_links = taken_row
    if publication.chapter_page:
        page_chapters, page_other = publication_documents(fetch(session, publication.chapter_page).text)
        other_links = other_links + page_other
        chapter_links = page_chapters
    documents, skipped_chapters = build_documents(session, publication, pub_row, chapter_links, download_dir)
    manifest_path = ROOT / "manifests" / f"us-cms-iom-{publication.number}.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {"version": publication.version, "documents": documents}, sort_keys=False, allow_unicode=True, width=120
        )
    )

    # 3. Queue: the single federal row, one entry per taken publication.
    status_counts = update_queue(
        ROOT / "manifests" / "medicare-agent-queue.yaml",
        publication,
        pub_row,
        chapter_links,
        other_links,
        skipped_chapters,
        documents,
        manifest_path.name,
        len(publications),
        inventory,
        paper_inventory,
    )
    print(
        f"wrote {manifest_path.relative_to(ROOT)} with {len(documents)} chapters; "
        f"IOM index publications {len(publications)}, paper-based {len(paper_inventory)}; "
        f"queue {status_counts}"
    )
    for doc in documents:
        meta = doc["metadata"]
        extra = f"; {meta['heading_label_form']}" if "heading_label_form" in meta else ""
        extra += f"; override: {meta['extraction_override']}" if "extraction_override" in meta else ""
        print(
            f"  chapter {meta['chapter']}: {meta['toc_section_count']} TOC sections, "
            f"{meta['pdf_page_count']} pages, expression {doc['expression_date']} ({meta['latest_transmittal']}); "
            f"body start p{meta['body_start_page']} by {meta['body_start_rule']}{extra}"
        )
    for text, reason in skipped_chapters:
        print(f"  not taken: {text} ({reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
