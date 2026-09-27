import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest
import yaml
from bs4 import BeautifulSoup
from bs4.element import CData, NavigableString, Tag
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.cli as cli
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.coverage import ProvisionCoverageReport
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.maine import (
    MAINE_REVISED_STATUTES_INDEX,
    MAINE_REVISED_STATUTES_SOURCE_FORMAT,
    MaineSectionTarget,
    MaineTitle,
    extract_maine_revised_statutes,
    parse_maine_chapter_page,
    parse_maine_section,
    parse_maine_title_index,
    parse_maine_title_page,
)
from axiom_corpus.corpus.states import StateStatuteExtractReport

ROOT = Path(__file__).resolve().parents[1]
RETAINED_VERSION = "2026-09-14-income-tax-chapter-us-me-title-36"
SUBUNITS_VERSION = "2026-09-26-income-tax-subunits-us-me-title-36"
SUBUNITS_MANIFEST_PATH = ROOT / "manifests/us-me-statutes-title-36-subunits.yaml"
RETAINED_HTML = (
    ROOT / "data/corpus/sources/us-me/statute" / RETAINED_VERSION / "maine-revised-statutes-html"
)
AS_OF = date(2026, 9, 14)
NON_BODY_CLASSES = {"heading_section", "headnote_blip", "qhistory", "bhistory", "note"}

SAMPLE_TITLE_INDEX_HTML = """
<html>
<body>
<ul class="title_list">
  <li class="right_nav"><a href="1/title1ch0sec0.html">TITLE 1: GENERAL PROVISIONS</a></li>
  <li class="right_nav"><a href="36/title36ch0sec0.html">TITLE 36: TAXATION</a></li>
</ul>
</body>
</html>
"""

SAMPLE_TITLE_HTML = """
<html>
<body>
<div class="title_toc MRSTitle_toclist col-sm-10">
  <div class="title_heading"><div>Title 36: TAXATION</div></div>
  <div class="MRSPart_toclist">
    <h2 class="heading_part">Part 8: INCOME TAXES</h2>
    <div class="MRSChapter_toclist">
      <a href="./title36ch822sec0.html">Chapter 822: TAX CREDITS</a> \u00a75213 - \u00a75219-BBB
    </div>
  </div>
</div>
</body>
</html>
"""

SAMPLE_CHAPTER_HTML = """
<html>
<body>
<div class="chapter_toclist col-sm-10">
  <div class="ch_heading"><div>Title 36, Chapter 822: TAX CREDITS</div></div>
  <div class="MRSSection_toclist">
    <a href="./title36sec5219-S.html">36 \u00a75219-S. Earned income credit</a>
  </div>
  <div class="MRSSection_toclist right_nav_repealed">
    <a href="./title36sec5219-T.html">36 \u00a75219-T. Old credit (REPEALED)</a>
  </div>
</div>
</body>
</html>
"""

SAMPLE_SECTION_HTML = """
<html>
<body>
<div class="col-sm-12 MRSSection status_current">
  <h3 class="heading_section">\u00a75219-S. Earned income credit</h3>
  <div class="MRSSubSection">
    <div class="mrs-text indpara">
      <span class="headnote">1. Resident taxpayer.</span>
      A resident is allowed a credit under <a href="../36/title36sec5102.html">section 5102</a>.
    </div>
    <span class="bhistory">[PL 2021, c. 635, Pt. E, \u00a71 (AMD).]</span>
  </div>
  <div class="note"><span>Revisor's Note:</span> This is a note.</div>
  <div class="qhistory">
    SECTION HISTORY
    <div class="qhistory_list"><span class="hist_chapter">PL 1999, c. 731, \u00a7V1 (NEW).</span></div>
  </div>
</div>
</body>
</html>
"""

SAMPLE_UNSUBDIVIDED_SECTION_HTML = """
<html>
<body>
<div class="col-sm-12 MRSSection status_current">
  <h3 class="heading_section">\u00a7115. Payment by credit card</h3>
  <div class="mrs-text indpara MRSIndentedPara status_current IP">
    The State Tax Assessor may establish procedures permitting payment of taxes by the use of credit cards.
    <span class="bhistory">[PL 2005, c. 622, \u00a73 (NEW).]</span>
  </div>
  <div class="qhistory">
    SECTION HISTORY
    <div class="qhistory_list"><span class="hist_chapter">PL 2005, c. 622, \u00a73 (NEW).</span></div>
  </div>
</div>
</body>
</html>
"""

SAMPLE_TITLE = MaineTitle(
    number="36",
    heading="Taxation",
    relative_path="36/title36ch0sec0.html",
    ordinal=1,
)


def test_parse_maine_title_index_extracts_titles():
    titles = parse_maine_title_index(SAMPLE_TITLE_INDEX_HTML)

    assert [title.number for title in titles] == ["1", "36"]
    assert titles[1].heading == "TAXATION"
    assert titles[1].relative_path == "36/title36ch0sec0.html"
    assert titles[1].citation_path == "us-me/statute/title-36"


def test_parse_maine_title_chapter_and_section_pages():
    document = parse_maine_title_page(SAMPLE_TITLE_HTML, title=SAMPLE_TITLE)

    assert document.title_heading == "TAXATION"
    assert [part.part for part in document.parts] == ["8"]
    assert document.parts[0].citation_path == "us-me/statute/title-36/part-8"
    assert [chapter.display_chapter for chapter in document.chapters] == ["822"]
    assert document.chapters[0].section_range == "\u00a75213 - \u00a75219-BBB"

    targets = parse_maine_chapter_page(SAMPLE_CHAPTER_HTML, chapter=document.chapters[0])

    assert [target.section_id for target in targets] == ["5219-S", "5219-T"]
    assert targets[0].citation_path == "us-me/statute/36/5219-S"
    assert targets[1].status == "repealed"

    parsed = parse_maine_section(SAMPLE_SECTION_HTML, target=targets[0])

    assert parsed.heading == "Earned income credit"
    assert parsed.body is not None
    assert "resident is allowed a credit" in parsed.body
    assert parsed.references_to == ("us-me/statute/36/5102",)
    assert parsed.source_history == (
        "[PL 2021, c. 635, Pt. E, \u00a71 (AMD).]",
        "PL 1999, c. 731, \u00a7V1 (NEW).",
    )
    assert parsed.notes == ("Revisor's Note: This is a note.",)


def test_parse_maine_section_without_subsections_keeps_body():
    parsed = parse_maine_section(SAMPLE_UNSUBDIVIDED_SECTION_HTML)

    assert parsed.heading == "Payment by credit card"
    assert parsed.body == (
        "The State Tax Assessor may establish procedures permitting payment of taxes "
        "by the use of credit cards."
    )
    assert parsed.source_history == (
        "[PL 2005, c. 622, \u00a73 (NEW).]",
        "PL 2005, c. 622, \u00a73 (NEW).",
    )


def test_extract_maine_revised_statutes_from_source_dir_writes_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    (source_dir / "36").mkdir(parents=True)
    (source_dir / MAINE_REVISED_STATUTES_INDEX).write_text(
        SAMPLE_TITLE_INDEX_HTML,
        encoding="utf-8",
    )
    (source_dir / "36" / "title36ch0sec0.html").write_text(
        SAMPLE_TITLE_HTML,
        encoding="utf-8",
    )
    (source_dir / "36" / "title36ch822sec0.html").write_text(
        SAMPLE_CHAPTER_HTML,
        encoding="utf-8",
    )
    (source_dir / "36" / "title36sec5219-S.html").write_text(
        SAMPLE_SECTION_HTML,
        encoding="utf-8",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_maine_revised_statutes(
        store,
        version="2026-05-09",
        source_dir=source_dir,
        source_as_of="2025-10-01",
        expression_date="2025-10-01",
        only_title="36",
        limit=1,
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 2
    assert report.section_count == 1
    assert report.provisions_written == 4
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    assert inventory[0].source_format == MAINE_REVISED_STATUTES_SOURCE_FORMAT
    assert [record.citation_path for record in records] == [
        "us-me/statute/title-36",
        "us-me/statute/title-36/part-8",
        "us-me/statute/title-36/chapter-822",
        "us-me/statute/36/5219-S",
    ]
    assert records[3].metadata is not None
    assert records[3].metadata["references_to"] == ["us-me/statute/36/5102"]


# --- Numbered units below the section ---------------------------------------------------------

SECTION_5122_TARGET = MaineSectionTarget(
    title="36",
    section_id="5122",
    display_section="5122",
    heading="Modifications",
    relative_path="36/title36sec5122.html",
    parent_citation_path="us-me/statute/title-36/chapter-805",
    ordinal=2,
)


def _words(text: str | None) -> list[str]:
    return (text or "").split()


def _body_text_nodes(section: Tag) -> list[str]:
    """Independent re-derivation of the body text: every string under the section node
    outside the editorial apparatus (heading, blips, history, notes), in document order."""
    texts: list[str] = []
    for string in section.descendants:
        if type(string) not in (NavigableString, CData):
            continue
        for parent in string.parents:
            if parent is section:
                texts.append(str(string))
                break
            if NON_BODY_CLASSES.intersection(parent.get("class") or ()) or parent.name in {
                "script",
                "style",
                "template",
            }:
                break
    return texts


def _body_words_from_html(html: bytes | Tag) -> list[str]:
    section = html if isinstance(html, Tag) else BeautifulSoup(html, "lxml").select_one(".MRSSection")
    assert section is not None
    text = " ".join(_body_text_nodes(section))
    text = text.replace("\xa0", " ").replace("\u2011", "-").replace("\u2013", "-")
    return text.replace("\u2014", "--").split()


def _assert_subunit_invariants(parsed, *, section_path: str) -> None:
    """Invariants every parsed section satisfies, whatever its structure."""
    lines = (parsed.body or "").split("\n")
    paths = [f"{section_path}/{'/'.join(unit.segments)}" for unit in parsed.subunits]
    assert len(paths) == len(set(paths)), "citation paths are unique within the section"
    known = {section_path, *paths}
    siblings: dict[tuple[str, ...], list[int]] = {}
    for unit in parsed.subunits:
        parent = f"{section_path}/{'/'.join(unit.parent_segments)}" if unit.parent_segments else section_path
        assert parent in known, "every parent is the section or an emitted unit"
        assert len(unit.segments) == len(unit.numbers)
        for segment, number in zip(unit.segments, unit.numbers, strict=True):
            assert segment == number or segment.startswith(f"{number}--")
        assert (unit.variant is None) == (unit.segments[-1] == unit.numbers[-1])
        siblings.setdefault(unit.parent_segments, []).append(unit.ordinal)
        if unit.body is None:
            continue
        body_lines = unit.body.split("\n")
        # The first body line is the tail of a section line (its printed number, and a
        # subsection's headnote, removed); the rest is a contiguous run of section lines.
        starts = [
            index
            for index, line in enumerate(lines)
            if line.endswith(body_lines[0]) and lines[index + 1 : index + len(body_lines)] == body_lines[1:]
        ]
        assert starts, f"{'/'.join(unit.segments)} body is not a contiguous run of the section body"
    for ordinals in siblings.values():
        assert ordinals == list(range(1, len(ordinals) + 1)), "ordinals number siblings 1..n"
    # A parent's body contains every line of each child's body except the child's first
    # (the parent prints the child's number there).
    by_segments = {unit.segments: unit for unit in parsed.subunits}
    for unit in parsed.subunits:
        parent = by_segments.get(unit.parent_segments)
        if parent is not None and unit.body is not None:
            assert parent.body is not None
            for line in unit.body.split("\n")[1:]:
                assert line in parent.body.split("\n")


def test_parse_maine_section_keeps_lettered_paragraphs_and_deeper_levels():
    html = (RETAINED_HTML / "36/title36sec5122.html").read_bytes()
    assert hashlib.sha256(html).hexdigest() == (
        "05d1f7f89a8c0ef06659c6b8137e5168899070cf3b8404aeb4271a403ed6fdca"
    )

    parsed = parse_maine_section(html, target=SECTION_5122_TARGET, as_of=AS_OF)

    assert parsed.body is not None
    lines = parsed.body.split("\n")
    assert len(lines) == 225
    assert len(parsed.body) == 54705
    # Before the fix the body was the four subsection lead-ins (495 characters).
    subtractions = lines.index("2. Subtractions. Federal adjusted gross income shall be reduced by:")
    assert lines[subtractions + 1].startswith("A. Interest or dividends on obligations of the United States")
    assert (
        "(i) The aggregate of retirement plan benefits under employee retirement plans or "
        "individual retirement accounts included in the individual\u2019s federal adjusted "
        "gross income; and"
    ) in lines
    assert "M-2. For tax years beginning on or after January 1, 2016:" in lines
    assert 'For purposes of this paragraph, "applicable amount" means:' in lines
    assert "(4) For married individuals filing separate returns, 1/2 of the applicable amount under subparagraph (3);" in lines
    assert not any(line.startswith("[PL ") or line.startswith("[RR ") for line in lines)
    assert "[PL 2025, c. 271, Pt. C, \u00a72 (AMD); PL 2025, c. 452, \u00a71 (AMD).]" in parsed.source_history
    assert _words(parsed.body) == _body_words_from_html(html)

    units = {"/".join(unit.segments): unit for unit in parsed.subunits}
    assert len(units) == 205
    m2 = units["2/M-2"]
    assert (m2.kind, m2.label, m2.numbers, m2.ordinal) == ("paragraph", "M-2.", ("2", "M-2"), 15)
    assert m2.body is not None
    assert m2.body.startswith(
        "For tax years beginning on or after January 1, 2016:\n"
        "(1) For each individual who is a primary recipient of retirement plan benefits, "
        "the reduction is the sum of:\n(a) Excluding military retirement plan benefits"
    )
    assert m2.body.endswith(
        '"Retirement plan benefits" does not include distributions that are subject to '
        "the tax imposed by the Code, Section 72(t);"
    )
    assert m2.source_history == (
        "[PL 2025, c. 271, Pt. C, \u00a72 (AMD); PL 2025, c. 452, \u00a71 (AMD).]",
    )
    m3 = units["2/M-3"]
    assert m3.body is not None
    assert m3.body.split("\n")[1:] == [
        'For purposes of this paragraph, "applicable amount" means:',
        "(1) For individuals filing as single individuals, $125,000;",
        "(2) For individuals filing as heads of households, $187,500;",
        "(3) For individuals filing married joint returns or as surviving spouses, $250,000; or",
        "(4) For married individuals filing separate returns, 1/2 of the applicable amount "
        "under subparagraph (3);",
    ]
    expected_kinds = {
        "2": ("subsection", "Subtractions", "Federal adjusted gross income shall be reduced by:"),
        "2/M-2/1": ("subparagraph", None, "For each individual who is a primary recipient"),
        "2/M-2/1/a": ("division", None, "Excluding military retirement plan benefits"),
        "2/M-2/1/a/i": ("subdivision", None, "The aggregate of retirement plan benefits"),
        "2/M-2/2/d/iv": ("subdivision", None, "For tax years beginning on or after January 1, 2024,"),
    }
    for segments, (kind, heading, body_start) in expected_kinds.items():
        assert units[segments].kind == kind
        assert units[segments].heading == heading
        assert (units[segments].body or "").startswith(body_start)
    assert units["2/M-2/2/d/iv"].body == (
        "For tax years beginning on or after January 1, 2024, the maximum annual benefit "
        "that an individual eligible to retire at the retirement age, as defined in 42 United "
        "States Code, Section 416(l), as of January 1st of the tax year may receive under the "
        "federal Social Security Act and amendments to that Act as of June 28, 2023."
    )
    _assert_subunit_invariants(parsed, section_path="us-me/statute/36/5122")


def test_parse_maine_section_gives_repealed_and_reallocated_duplicates_variant_paths():
    html = (RETAINED_HTML / "36/title36sec5122.html").read_bytes()
    parsed = parse_maine_section(html, target=SECTION_5122_TARGET, as_of=AS_OF)
    units = {"/".join(unit.segments): unit for unit in parsed.subunits}

    # Subsection 1 prints the live paragraph KK and, after it, the placeholder of a
    # second KK repealed by PL 2017, c. 211; subsection 2 prints the live P and the
    # placeholder of a P reallocated to paragraph T.
    live_kk, repealed_kk = units["1/KK"], units["1/KK--repealed"]
    assert (live_kk.variant, live_kk.variants, live_kk.status) == (None, (("1", "KK--repealed"),), None)
    assert (live_kk.body or "").startswith("For taxable years beginning on or after January 1, 2015:")
    assert (repealed_kk.variant, repealed_kk.variant_of, repealed_kk.status) == (
        "repealed",
        ("1", "KK"),
        "repealed",
    )
    assert repealed_kk.body is None
    assert repealed_kk.source_history == ("[PL 2017, c. 211, Pt. D, \u00a71 (RP).]",)
    reallocated_p = units["2/P--reallocated"]
    assert reallocated_p.status == "reallocated"
    assert reallocated_p.markers == ("REALLOCATED TO T. 36, \u00a75122, sub-\u00a72, \u00b6T",)
    assert reallocated_p.body is None
    assert (units["2/P"].body or "").startswith("An amount equal to the absolute value of any net operating loss")


DATED_VERSIONS_HTML = """
<html><body>
<div class="col-sm-12 MRSSection status_current">
  <h3 class="heading_section">\u00a74401. Definitions</h3>
  <div class="MRSSubSection">
    <div class="mrs-text indpara"><span class="headnote">2-A. (TEXT EFFECTIVE UNTIL 1/05/26) Electronic smoking device. </span>"Electronic smoking device" means an old device.</div>
    <span class="bhistory">[PL 2011, c. 1, \u00a71 (NEW).]</span>
  </div>
  <div class="MRSSubSection">
    <div class="mrs-text indpara"><span class="headnote">2-A. (TEXT EFFECTIVE 1/05/26) Electronic smoking device. </span>"Electronic smoking device" means a new device.</div>
    <div class="mrs-text paragraph MRSLetteredPara status_current LP"><span class="letpara_id">A. </span>(TEXT EFFECTIVE UNTIL 1/05/26) Old rule.<span class="bhistory"></span></div>
    <div class="mrs-text paragraph MRSLetteredPara status_current LP"><span class="letpara_id">A. </span>(TEXT EFFECTIVE 1/05/26) New rule.<span class="bhistory"></span></div>
    <span class="bhistory">[PL 2025, c. 1, \u00a71 (AMD).]</span>
  </div>
  <div class="MRSSubSection">
    <div class="mrs-text indpara"><span class="headnote">3. (TEXT EFFECTIVE UNTIL 1/05/26) Vending machines. </span>Machines are presumed full.</div>
    <span class="bhistory"></span>
  </div>
  <div class="MRSSubSection">
    <div class="mrs-text indpara"><span class="headnote">3. (FUTURE CONFLICT: Text as repealed by PL 2025, c. 367, \u00a717) (TEXT REPEALED 1/05/26) Vending machines. </span></div>
    <span class="bhistory">[PL 2025, c. 367, \u00a717 (RP).]</span>
  </div>
  <div class="MRSSubSection">
    <div class="mrs-text indpara"><span class="headnote">4. Plain. </span>Text.</div>
    <div class="mrs-text paragraph MRSLetteredPara status_current LP"><span class="letpara_id">DD. </span>Live paragraph.<span class="bhistory"></span></div>
    <div class="mrs-text paragraph MRSLetteredPara status_current LP"><span class="letpara_id">DD. </span>(REALLOCATED TO T. 36, \u00a7191, sub-\u00a72, \u00b6HH)<span class="bhistory">[RR 2005, c. 1, \u00a718 (RAL).]</span></div>
    <div class="mrs-text paragraph MRSLetteredPara status_current LP"><span class="letpara_id">DD. </span>(REALLOCATED TO T. 36, \u00a7191, sub-\u00a72, \u00b6II)<span class="bhistory">[RR 2005, c. 1, \u00a719 (RAL).]</span></div>
  </div>
</div>
</body></html>
"""


@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        (
            date(2026, 9, 14),
            {
                "2-A--effective-until-2026-01-05": "\"Electronic smoking device\" means an old device.",
                "2-A": "\"Electronic smoking device\" means a new device.\nA. (TEXT EFFECTIVE UNTIL 1/05/26) Old rule.\nA. (TEXT EFFECTIVE 1/05/26) New rule.",
                "2-A/A--effective-until-2026-01-05": "Old rule.",
                "2-A/A": "New rule.",
                "3--effective-until-2026-01-05": "Machines are presumed full.",
                "3": None,
            },
        ),
        (
            date(2025, 12, 31),
            {
                "2-A": "\"Electronic smoking device\" means an old device.",
                "2-A--effective-2026-01-05": "\"Electronic smoking device\" means a new device.\nA. (TEXT EFFECTIVE UNTIL 1/05/26) Old rule.\nA. (TEXT EFFECTIVE 1/05/26) New rule.",
                "2-A--effective-2026-01-05/A": "Old rule.",
                "2-A--effective-2026-01-05/A--effective-2026-01-05": "New rule.",
                "3": "Machines are presumed full.",
                "3--repealed-2026-01-05": None,
            },
        ),
    ],
)
def test_parse_maine_section_keeps_the_version_in_force_on_the_plain_path(as_of, expected):
    parsed = parse_maine_section(DATED_VERSIONS_HTML, as_of=as_of)
    units = {"/".join(unit.segments): unit for unit in parsed.subunits}

    for segments, body in expected.items():
        assert units[segments].body == body, segments
    assert units["2-A"].heading == units["2-A--effective-until-2026-01-05" if as_of > date(2026, 1, 5) else "2-A--effective-2026-01-05"].heading == "Electronic smoking device"
    repealed = units["3"] if as_of > date(2026, 1, 5) else units["3--repealed-2026-01-05"]
    assert repealed.status == ("repealed" if as_of > date(2026, 1, 5) else None)
    assert repealed.markers == (
        "FUTURE CONFLICT: Text as repealed by PL 2025, c. 367, \u00a717",
        "TEXT REPEALED 1/05/26",
    )
    # Two reallocated placeholders of one number are told apart by printed position.
    assert units["4/DD"].body == "Live paragraph."
    assert units["4/DD--reallocated-2"].markers == ("REALLOCATED TO T. 36, \u00a7191, sub-\u00a72, \u00b6HH",)
    assert units["4/DD--reallocated-3"].markers == ("REALLOCATED TO T. 36, \u00a7191, sub-\u00a72, \u00b6II",)
    assert units["4/DD--reallocated-2"].variant_of == ("4", "DD")
    _assert_subunit_invariants(parsed, section_path="us-me/statute/36/4401")


def test_parse_maine_section_without_as_of_prefers_the_first_live_unit():
    parsed = parse_maine_section(DATED_VERSIONS_HTML)
    units = {"/".join(unit.segments): unit for unit in parsed.subunits}

    assert units["2-A"].body == "\"Electronic smoking device\" means an old device."
    assert units["3"].body == "Machines are presumed full."
    assert units["3--repealed-2026-01-05"].body is None


# --- Property tests on generated section pages ------------------------------------------------

_KINDS = ("subsection", "paragraph", "subparagraph", "division", "subdivision")
_ROMAN = ("i", "ii", "iii", "iv", "v", "vi")
_WORD = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=7)
_SENTENCE = st.lists(_WORD, min_size=1, max_size=5).map(" ".join)


@dataclass
class _GenUnit:
    kind: str
    number: str
    heading: str | None
    lead: str
    continuation: str | None
    wrap_children: bool
    history: str
    note: bool = False
    children: list[_GenUnit] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.kind == "subsection":
            return f"{self.number}. {self.heading}."
        if self.kind == "paragraph":
            return f"{self.number}."
        return f"({self.number})"

    def full_text(self) -> str:
        return " ".join([self.label, self.own_text()])

    def own_text(self) -> str:
        parts = [self.lead]
        if self.continuation:
            parts.append(self.continuation)
        parts.extend(child.full_text() for child in self.children)
        return " ".join(parts)

    def html(self) -> str:
        children = "\n".join(child.html() for child in self.children)
        cont = self.continuation or ""
        history = f'<span class="bhistory">{self.history}</span>'
        if self.note:
            # Editorial apparatus inside the unit, carrying number-like labels.
            history += (
                '<div class="note"><span class="headnote">99. Quoted.</span>'
                '<span class="letpara_id">ZZ.</span><span class="mrs-text paragraph">(9)</span> note</div>'
            )
        if self.kind == "subsection":
            block = f'<div class="mrs-text paragraph B">{cont}</div>' if cont else ""
            return (
                '<div class="MRSSubSection">\n<div class="mrs-text indpara">'
                f'<span class="headnote">{self.label}\n </span>{self.lead}\n</div>'
                f"{block}\n{children}\n{history}</div>"
            )
        if cont and self.wrap_children:
            inner = f'<div class="mrs-text paragraph B">{cont}\n{children}</div>'
        elif cont:
            inner = f'<div class="mrs-text paragraph B">{cont}</div>\n{children}'
        else:
            inner = children
        if self.kind == "paragraph":
            return (
                '<div class="mrs-text paragraph MRSLetteredPara status_current LP">'
                f'<span class="letpara_id">{self.label}\n  </span>{self.lead}\n{inner}{history}</div>'
            )
        css = {"subparagraph": "MRSSubPara", "division": "MRSDivision", "subdivision": "MRSSubDivision"}
        return (
            f'<div class="mrs-text {css[self.kind]} paragraph"><span class="mrs-text paragraph">'
            f"\n  {self.label}\n</span>{self.lead}\n{inner}{history}</div>"
        )


def _numbers(kind: str, count: int) -> list[str]:
    if kind == "subsection":
        return [str(index) if index % 3 else f"{index}-A" for index in range(1, count + 1)]
    if kind == "paragraph":
        return [chr(ord("A") + index) if index < 26 else f"A-{index}" for index in range(count)]
    if kind == "subparagraph":
        return [str(index) for index in range(1, count + 1)]
    if kind == "division":
        return [chr(ord("a") + index) for index in range(count)]
    return list(_ROMAN[:count])


@st.composite
def _units(draw, depth: int, max_depth: int) -> list[_GenUnit]:
    kind = _KINDS[depth]
    count = draw(st.integers(min_value=0 if depth else 1, max_value=4))
    units = []
    for number in _numbers(kind, count):
        children = draw(_units(depth + 1, max_depth)) if depth + 1 <= max_depth else []
        units.append(
            _GenUnit(
                kind=kind,
                number=number,
                heading=draw(_SENTENCE).capitalize() if kind == "subsection" else None,
                lead=draw(st.sampled_from(["", "(WHOLE milk only) ", "(TEXT of it) ", "(including x) "]))
                + draw(_SENTENCE),
                note=draw(st.booleans()),
                continuation=draw(st.none() | _SENTENCE),
                wrap_children=draw(st.booleans()),
                history=draw(st.sampled_from(["", "[PL 2001, c. 1, \u00a71 (NEW).]", "[PL 2019, c. 9, \u00a72 (AMD).]"])),
                children=children,
            )
        )
    return units


@st.composite
def _generated_sections(draw):
    max_depth = draw(st.integers(min_value=0, max_value=4))
    intro = draw(st.none() | _SENTENCE)
    units = draw(_units(0, max_depth))
    note = draw(st.booleans())
    parts = ['<html><body><div class="col-sm-12 MRSSection status_current">']
    parts.append('<h3 class="heading_section">\u00a7900. Generated</h3>')
    if intro:
        parts.append(f'<div class="mrs-text indpara MRSIndentedPara status_current IP">{intro}</div>')
    parts.extend(unit.html() for unit in units)
    if note:
        parts.append("<div class=\"note\"><span>Revisor's Note:</span> not statute text</div>")
    parts.append('<div class="qhistory">SECTION HISTORY <div class="qhistory_list">PL 2001, c. 1 (NEW).</div></div>')
    parts.append("</div></body></html>")
    return "\n".join(parts), intro, units


def _flatten(units: list[_GenUnit], prefix: tuple[str, ...] = ()):
    for unit in units:
        segments = (*prefix, unit.number)
        yield segments, unit
        yield from _flatten(unit.children, segments)


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_generated_sections())
def test_generated_sections_keep_every_word_and_every_unit(generated):
    html, intro, units = generated
    parsed = parse_maine_section(html, as_of=AS_OF)

    # Conservation: the body holds every statute word of the page, in order, and nothing else.
    expected_text = " ".join([intro or "", *(unit.full_text() for unit in units)])
    assert _words(parsed.body) == _words(expected_text)
    assert _words(parsed.body) == _body_words_from_html(html.encode())
    # Every generated unit is a subunit with the generator's path, kind and own text.
    expected = dict(_flatten(units))
    got = {unit.segments: unit for unit in parsed.subunits}
    assert list(got) == list(expected)
    for segments, unit in expected.items():
        assert got[segments].kind == unit.kind
        assert got[segments].heading == unit.heading
        assert _words(got[segments].body) == _words(unit.own_text())
        assert got[segments].variant is None
    _assert_subunit_invariants(parsed, section_path="us-me/statute/36/900")
    # Determinism.
    assert parse_maine_section(html, as_of=AS_OF) == parsed


@settings(max_examples=200, deadline=None)
@given(
    st.lists(
        st.tuples(st.booleans(), st.sampled_from(["", "[PL 2017, c. 211, \u00a71 (RP).]"])),
        min_size=2,
        max_size=5,
    )
)
def test_same_number_paragraphs_get_one_plain_path_and_unique_variants(occurrences):
    paragraphs = "".join(
        '<div class="mrs-text paragraph MRSLetteredPara status_current LP"><span class="letpara_id">KK. </span>'
        f"{'Operative text ' + str(index) + '.' if live else ''}<span class=\"bhistory\">{history}</span></div>"
        for index, (live, history) in enumerate(occurrences)
    )
    html = (
        '<html><body><div class="MRSSection"><div class="MRSSubSection"><div class="mrs-text indpara">'
        f'<span class="headnote">1. Additions. </span>Add:</div>{paragraphs}</div></div></body></html>'
    )
    parsed = parse_maine_section(html, as_of=AS_OF)
    group = [unit for unit in parsed.subunits if unit.numbers == ("1", "KK")]

    assert len(group) == len(occurrences)
    segments = [unit.segments[-1] for unit in group]
    assert len(set(segments)) == len(segments)
    plain = [unit for unit in group if unit.segments[-1] == "KK"]
    assert len(plain) == 1
    first_live = next((index for index, (live, _) in enumerate(occurrences) if live), 0)
    assert plain[0] is group[first_live]
    assert all(unit.variant_of == ("1", "KK") for unit in group if unit is not plain[0])
    assert sorted(plain[0].variants) == sorted(unit.segments for unit in group if unit is not plain[0])
    _assert_subunit_invariants(parsed, section_path="us-me/statute/36/9")


# --- The retained Title 36 pages --------------------------------------------------------------


def test_every_retained_title_36_section_page_keeps_every_word():
    pages = sorted((RETAINED_HTML / "36").glob("title36sec*.html"))
    assert len(pages) == 1776
    unit_count = 0
    for page in pages:
        html = page.read_bytes()
        parsed = parse_maine_section(html, as_of=AS_OF)
        section = BeautifulSoup(html, "lxml").select_one(".MRSSection")
        assert section is not None
        expected_words = _body_words_from_html(section)
        if not expected_words:
            # A section with no text prints only its status blip ("(REPEALED)",
            # "(REALLOCATED TO TITLE 36, SECTION 6142)"), which is then the body.
            expected_words = _words(" ".join(blip.get_text(" ") for blip in section.select(".headnote_blip")))
        assert _words(parsed.body) == expected_words, page.name
        _assert_subunit_invariants(parsed, section_path=f"us-me/statute/36/{page.stem[len('title36sec'):]}")
        units = [
            tag
            for tag in section.find_all(True)
            if {"MRSSubSection", "MRSLetteredPara", "MRSSubPara", "MRSDivision", "MRSSubDivision"}
            & set(tag.get("class") or ())
        ]
        assert len(parsed.subunits) == len(units), page.name
        # Each child is its own element's statute words, in order, minus only its printed
        # number (a subsection's whole headnote) and leading status markers: a body taken
        # from the wrong element (for example two siblings swapped) fails here.
        for unit, element in zip(parsed.subunits, units, strict=True):
            element_words = _body_words_from_html(element)
            body_words = _words(unit.body)
            prefix = element_words[: len(element_words) - len(body_words)]
            assert element_words[len(prefix) :] == body_words, (page.name, unit.segments)
            markers = [] if unit.kind == "subsection" else [f"({marker})" for marker in unit.markers]
            assert prefix == _words(" ".join([unit.label, *markers])), (page.name, unit.segments)
        unit_count += len(units)
    assert unit_count == 5812


def _superseded_rows() -> dict[str, dict]:
    path = ROOT / "data/corpus/provisions/us-me/statute" / f"{RETAINED_VERSION}.jsonl"
    return {row["citation_path"]: row for row in map(json.loads, path.read_text().splitlines())}


def test_title_36_subunit_scope_replays_and_resolves_the_pension_deduction(tmp_path, capsys, monkeypatch):
    # The committed us-me/statute/2026-09-26-income-tax-subunits-us-me-title-36 scope must be
    # exactly what this adapter produces from the retained, git-tracked official bytes of the
    # 2026-09-14 scope, with no network access.
    def no_network(self, source_url):
        raise AssertionError(f"unexpected download: {source_url}")

    monkeypatch.setattr(cli.extract_maine_revised_statutes.__globals__["_MaineFetcher"], "_download", no_network)
    manifest = yaml.safe_load(SUBUNITS_MANIFEST_PATH.read_text(encoding="utf-8"))
    (source,) = manifest["sources"]
    source["options"]["source_dir"] = str(ROOT / "data/corpus/sources/us-me/statute" / RETAINED_VERSION)
    manifest_path = tmp_path / "replay.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    base = tmp_path / "corpus"

    exit_code = main(["extract-state-statutes", "--base", str(base), "--manifest", str(manifest_path)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0, payload
    assert payload["provisions_written"] == 7745
    assert payload["coverage_complete"] is True
    committed = ROOT / "data/corpus"
    written = sorted(path for path in base.rglob("*") if path.is_file())
    assert len(written) == 3 + 1923
    for path in written:
        relative = path.relative_to(base).as_posix()
        assert hashlib.sha256((committed / relative).read_bytes()).hexdigest() == hashlib.sha256(
            path.read_bytes()
        ).hexdigest(), relative
    for path in (RETAINED_HTML).rglob("*.html"):
        relative = path.relative_to(RETAINED_HTML).as_posix()
        replayed = base / "sources/us-me/statute" / SUBUNITS_VERSION / "maine-revised-statutes-html" / relative
        assert replayed.read_bytes() == path.read_bytes(), relative

    by_path = {
        record.citation_path: record
        for record in load_provisions(committed / "provisions/us-me/statute" / f"{SUBUNITS_VERSION}.jsonl")
    }
    section = by_path["us-me/statute/36/5122"]
    assert section.id == "88f3606d-528a-5355-a8eb-3de153e6bc40"
    assert section.body is not None and len(section.body) == 54705
    expected = {
        "us-me/statute/36/5122/2": ("subsection", "36 M.R.S. \u00a7 5122(2)", "us-me/statute/36/5122"),
        "us-me/statute/36/5122/2/M-2": ("paragraph", "36 M.R.S. \u00a7 5122(2)(M-2)", "us-me/statute/36/5122/2"),
        "us-me/statute/36/5122/2/M-3": ("paragraph", "36 M.R.S. \u00a7 5122(2)(M-3)", "us-me/statute/36/5122/2"),
        "us-me/statute/36/5122/2/M-2/2/d/iv": (
            "subdivision",
            "36 M.R.S. \u00a7 5122(2)(M-2)(2)(d)(iv)",
            "us-me/statute/36/5122/2/M-2/2/d",
        ),
    }
    for citation_path, (kind, label, parent) in expected.items():
        record = by_path[citation_path]
        assert (record.kind, record.citation_label, record.parent_citation_path) == (kind, label, parent)
        assert record.parent_id == by_path[parent].id
        assert record.source_path == section.source_path
        assert record.body is not None
        assert all(line in section.body.split("\n") for line in record.body.split("\n")[1:])
    m2 = by_path["us-me/statute/36/5122/2/M-2"]
    assert m2.identifiers == {
        "maine:title": "36",
        "maine:section": "5122",
        "maine:subsection": "2",
        "maine:paragraph": "M-2",
        "maine:source_id": "36-5122/2/M-2",
    }
    assert m2.metadata is not None and m2.metadata["publisher_label"] == "M-2."
    assert m2.level == 5

    # Differential check against the superseded scope: every citation path it has is here
    # with the same id, heading, parent and metadata apart from amendment history, and
    # every word of its section bodies is still in the new body once the amendment history
    # and Revisor's notes that bodies of sections without subsections used to print inline
    # are set aside.
    superseded = _superseded_rows()
    assert set(superseded) <= set(by_path)
    for citation_path, old in superseded.items():
        new = by_path[citation_path]
        assert new.id == old["id"]
        assert (new.heading, new.parent_citation_path, new.kind, new.level) == (
            old.get("heading"), old.get("parent_citation_path"), old["kind"], old.get("level")
        )
        if old["kind"] != "section":
            assert new.body == old.get("body")
            continue
        assert new.metadata is not None
        old_metadata = dict(old["metadata"])
        new_metadata = dict(new.metadata)
        assert set(old_metadata.pop("source_history", ())) <= set(new_metadata.pop("source_history", ()))
        assert old_metadata == new_metadata, citation_path
        new_text = " ".join(_words(new.body))
        removable = [*old["metadata"].get("source_history", ()), *old["metadata"].get("notes", ())]
        for line in (old.get("body") or "").split("\n"):
            for text in sorted(removable, key=len, reverse=True):
                line = line.replace(text, " ")
            assert " ".join(_words(line)) in new_text, citation_path


def test_include_subunits_defaults_to_section_grain(tmp_path):
    source_dir = tmp_path / "source"
    (source_dir / "36").mkdir(parents=True)
    for name, html in (
        (MAINE_REVISED_STATUTES_INDEX, SAMPLE_TITLE_INDEX_HTML),
        ("36/title36ch0sec0.html", SAMPLE_TITLE_HTML),
        ("36/title36ch822sec0.html", SAMPLE_CHAPTER_HTML),
        ("36/title36sec5219-S.html", SAMPLE_SECTION_HTML),
    ):
        (source_dir / name).write_text(html, encoding="utf-8")

    reports = {
        flag: extract_maine_revised_statutes(
            CorpusArtifactStore(tmp_path / f"corpus-{flag}"),
            version="2026-05-09",
            source_dir=source_dir,
            source_as_of="2025-10-01",
            only_title="36",
            limit=1,
            include_subunits=flag,
        )
        for flag in (False, True)
    }

    assert [record.citation_path for record in load_provisions(reports[False].provisions_path)] == [
        "us-me/statute/title-36",
        "us-me/statute/title-36/part-8",
        "us-me/statute/title-36/chapter-822",
        "us-me/statute/36/5219-S",
    ]
    records = load_provisions(reports[True].provisions_path)
    assert [record.citation_path for record in records][3:] == [
        "us-me/statute/36/5219-S",
        "us-me/statute/36/5219-S/1",
    ]
    child = records[4]
    assert (child.kind, child.heading, child.body, child.level, child.ordinal) == (
        "subsection",
        "Resident taxpayer",
        "A resident is allowed a credit under section 5102 .",
        4,
        1,
    )
    assert child.parent_id == records[3].id
    assert child.metadata is not None
    assert child.metadata["references_to"] == ["us-me/statute/36/5102"]
    assert child.metadata["source_history"] == ["[PL 2021, c. 635, Pt. E, \u00a71 (AMD).]"]
    assert reports[True].coverage.complete is True
    inventory = load_source_inventory(reports[True].inventory_path)
    assert [item.citation_path for item in inventory] == [record.citation_path for record in records]


@pytest.mark.parametrize(
    ("manifest", "source_id", "expected"),
    [
        (SUBUNITS_MANIFEST_PATH, "us-me-mrs-title-36", True),
        (ROOT / "manifests/state-statutes.current.yaml", "us-me-statutes", False),
        (ROOT / "manifests/state-income-tax-chapters-2026-09-14.yaml", "us-me-mrs-title-36", False),
    ],
)
def test_extract_state_statutes_passes_include_subunits(tmp_path, capsys, monkeypatch, manifest, source_id, expected):
    base = tmp_path / "corpus"
    seen: dict[str, object] = {}

    def fake_maine(*args, **kwargs):
        seen.update(kwargs)
        return StateStatuteExtractReport(
            jurisdiction="us-me",
            title_count=1,
            container_count=0,
            section_count=1,
            provisions_written=1,
            inventory_path=base / "inventory.json",
            provisions_path=base / "provisions.jsonl",
            coverage_path=base / "coverage.json",
            coverage=ProvisionCoverageReport(
                jurisdiction="us-me",
                document_class="statute",
                version="v",
                source_count=1,
                provision_count=1,
                matched_count=1,
                missing_from_provisions=(),
                extra_provisions=(),
            ),
            source_paths=(),
        )

    monkeypatch.setattr(cli, "extract_maine_revised_statutes", fake_maine)
    main(["extract-state-statutes", "--base", str(base), "--manifest", str(manifest), "--only-source-id", source_id])
    capsys.readouterr()

    assert seen["include_subunits"] is expected


@pytest.mark.parametrize("include_subunits", [False, True])
def test_an_impossible_marker_date_keeps_the_section(tmp_path, include_subunits):
    html = (
        '<div class="MRSSection"><h3 class="heading_section">\u00a79. Test</h3>'
        '<div class="mrs-text MRSLetteredPara"><span class="letpara_id">A.</span>'
        "(TEXT EFFECTIVE 2/29/25) Operative text.</div></div>"
    )
    parsed = parse_maine_section(html, as_of=AS_OF)

    assert parsed.body == "A. (TEXT EFFECTIVE 2/29/25) Operative text."
    (unit,) = parsed.subunits
    assert (unit.segments, unit.body, unit.markers, unit.status) == (
        ("A",),
        "Operative text.",
        ("TEXT EFFECTIVE 2/29/25",),
        None,
    )


def test_a_page_without_section_content_is_rejected_not_read_as_statute_text():
    error_page = (
        "<html><head><title>Error</title></head><body><h1>Temporarily unavailable</h1>"
        "<p>Please try again later.</p></body></html>"
    )
    with pytest.raises(ValueError, match="no Maine section content"):
        parse_maine_section(error_page)
    # Without the section container only the Revisor's statute-text elements count.
    bare = (
        "<html><body><nav>Home | Statutes</nav>"
        '<div class="mrs-text indpara">The assessor may act.<span class="bhistory">[PL 1, c. 1 (NEW).]</span></div>'
        "<footer>Contact the Revisor</footer></body></html>"
    )
    assert parse_maine_section(bare).body == "The assessor may act."


def test_a_headnote_inside_a_note_never_numbers_a_unit():
    html = (
        '<div class="MRSSection"><div class="MRSSubSection"><div class="note">'
        '<span class="headnote">9. Quoted note.</span><span class="bhistory">[PL 9 (RP).]</span></div>'
        '<span class="headnote">1. Actual heading.</span>Operative text.'
        '<span class="bhistory">[PL 1 (NEW).]</span></div></div>'
    )
    parsed = parse_maine_section(html)

    assert parsed.body == "1. Actual heading. Operative text."
    (unit,) = parsed.subunits
    assert (unit.segments, unit.heading, unit.body, unit.source_history) == (
        ("1",),
        "Actual heading",
        "Operative text.",
        ("[PL 1 (NEW).]",),
    )


@pytest.mark.parametrize(
    ("lead", "markers", "body"),
    [
        ("(WHOLE milk only) must be supplied.", (), "(WHOLE milk only) must be supplied."),
        ("(TEXT of the note) applies.", (), "(TEXT of the note) applies."),
        ("(including benefits) is income.", (), "(including benefits) is income."),
        ("(REPEALED)", ("REPEALED",), None),
        ("(TEXT WITH CONFLICT) Rule.", ("TEXT WITH CONFLICT",), "Rule."),
        ("(CONFLICT: Text as amended by PL 2025, c. 1) Rule.", ("CONFLICT: Text as amended by PL 2025, c. 1",), "Rule."),
        ("(REALLOCATED FROM T. 36, \u00a75122, sub-\u00a72, \u00b6HH) Rule.", ("REALLOCATED FROM T. 36, \u00a75122, sub-\u00a72, \u00b6HH",), "Rule."),
    ],
)
def test_only_the_revisors_status_forms_are_markers(lead, markers, body):
    html = (
        '<div class="MRSSection"><div class="mrs-text MRSLetteredPara"><span class="letpara_id">A.</span>'
        f"{lead}</div></div>"
    )
    (unit,) = parse_maine_section(html).subunits
    assert (unit.markers, unit.body) == (markers, body)


@pytest.mark.parametrize(
    ("html", "body", "units"),
    [
        (
            '<div class="mrs-text">Statute.</div><div class="mrs-text note">Editorial note.</div>',
            "Statute.",
            [],
        ),
        (
            '<div class="MRSSection"><div class="MRSSubSection"><span class="headnote note">9. Quoted.</span>'
            '<span class="headnote">1. Actual.</span>Statute.</div></div>',
            "1. Actual. Statute.",
            [(("1",), "Actual", "Statute.")],
        ),
        (
            '<div class="MRSSection"><div class="mrs-text MRSSubPara"><span class="note">(9)</span>'
            "<span>(1)</span>Statute.</div></div>",
            "(1) Statute.",
            [(("1",), None, "Statute.")],
        ),
        (
            '<div class="MRSSection"><div class="mrs-text MRSSubPara"><div class="note">Editorial note.</div>'
            "<span>(1)</span>Statute.</div></div>",
            "(1) Statute.",
            [(("1",), None, "Statute.")],
        ),
    ],
)
def test_an_element_that_is_itself_a_note_is_never_text_or_a_label(html, body, units):
    parsed = parse_maine_section(html)
    assert parsed.body == body
    assert [(unit.segments, unit.heading, unit.body) for unit in parsed.subunits] == units


_APPARATUS = ["note", "bhistory", "qhistory", "headnote_blip", "heading_section"]


@pytest.mark.parametrize("apparatus", _APPARATUS)
def test_editorial_apparatus_never_becomes_a_unit_label_heading_or_history(apparatus):
    # A real ``.bhistory`` span inside a label is history, so labels nest a note then.
    inner = apparatus if apparatus not in {"bhistory", "heading_section"} else "note"
    section = (
        '<div class="MRSSection"><h3 class="heading_section">\u00a71. Actual heading'
        f'<span class="{inner}"> Editorial</span></h3>'
        f'<div class="MRSSubSection {apparatus}"><span class="headnote">9. Editorial heading.</span>Editorial text.'
        '<span class="bhistory">[PL 9 (RP).]</span></div>'
        '<div class="MRSSubSection"><span class="headnote">'
        f'<span class="{inner}">8. Editorial.</span>1. Actual.</span>Statute.'
        f'<span class="bhistory {apparatus if apparatus != "bhistory" else "note"}">[EDITORIAL (RP).]</span>'
        f'<span class="bhistory"><span class="{inner}">[EDITORIAL (RP).]</span></span>'
        '<div class="mrs-text MRSLetteredPara"><span class="letpara_id">'
        f'<span class="{inner}">Z.</span>A.</span>Paragraph.</div>'
        '<div class="mrs-text MRSSubPara"><span>'
        f'<span class="{inner}">(9)</span>(1)</span>Subparagraph.</div>'
        "</div></div>"
    )
    parsed = parse_maine_section(section)

    assert (parsed.display_section, parsed.heading) == ("1", "Actual heading")
    assert parsed.body == "1. Actual. Statute.\nA. Paragraph.\n(1) Subparagraph."
    assert [(unit.segments, unit.heading, unit.body, unit.source_history, unit.status) for unit in parsed.subunits] == [
        (("1",), "Actual", "Statute.\nA. Paragraph.\n(1) Subparagraph.", (), None),
        (("1", "A"), None, "Paragraph.", (), None),
        (("1", "1"), None, "Subparagraph.", (), None),
    ]
    assert "[EDITORIAL (RP).]" not in parsed.source_history


def test_a_section_container_inside_or_marked_as_a_note_is_skipped():
    for wrapper in (
        '<div class="MRSSection note"><div class="mrs-text">Editorial text.</div></div>',
        '<div class="note"><div class="MRSSection"><div class="mrs-text">Editorial text.</div></div></div>',
    ):
        html = (
            f"{wrapper}"
            '<div class="MRSSection"><div class="note"><h3 class="heading_section">\u00a79. Editorial</h3>'
            '<div class="headnote_blip">(REPEALED)</div></div>'
            '<h3 class="heading_section">\u00a71. Actual heading</h3><div class="mrs-text">Statute.</div></div>'
        )
        parsed = parse_maine_section(html)
        assert (parsed.display_section, parsed.heading, parsed.body, parsed.status) == (
            "1",
            "Actual heading",
            "Statute.",
            None,
        )
