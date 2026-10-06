import json
import re
from datetime import date, datetime
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.idaho import (
    IDAHO_CHAPTER_SOURCE_FORMAT,
    IDAHO_SECTION_SOURCE_FORMAT,
    IDAHO_TITLE_INDEX_SOURCE_FORMAT,
    IDAHO_TITLE_SOURCE_FORMAT,
    IdahoSectionListing,
    _clean_text,
    _coerce_expression_date,
    _is_history_marker,
    _parse_section_divs,
    _RecordedSource,
    _section_content_divs,
    _strip_section_heading,
    extract_idaho_statutes,
    parse_idaho_chapter_page,
    parse_idaho_section_page,
    parse_idaho_section_versions,
    parse_idaho_title_index,
    parse_idaho_title_page,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "citation-path.v1.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
SEGMENT_RE = re.compile(_SCHEMA["$defs"]["hierarchy_segment"]["well_formed_pattern"])
CITATION_PATH_RE = re.compile(_SCHEMA["$defs"]["citation_path"]["pattern"])

SAMPLE_TITLE_INDEX_HTML = """
<html><body>
  <table>
    <tr>
      <td><a href="/statutesrules/idstat/Title63">TITLE 63</a></td>
      <td>&#160;&#160;</td>
      <td> REVENUE AND TAXATION </td>
    </tr>
  </table>
</body></html>
"""

SAMPLE_TITLE_HTML = """
<html><body>
  <h1 class="lso-toc"><center>TITLE 63 REVENUE AND TAXATION</center></h1>
  <table>
    <tr>
      <td><a href="/statutesrules/idstat/Title63/T63CH30">CHAPTER 30</a></td>
      <td>&#160;&#160;</td>
      <td> INCOME TAX </td>
      <td>&#160;&#160;</td>
      <td><a href="/wp-content/uploads/statutesrules/idstat/Title63/T63CH30.pdf">Download Entire Chapter (PDF)</a></td>
    </tr>
    <tr>
      <td>CHAPTER 31</td>
      <td>&#160;&#160;</td>
      <td> OLD TAX ACT [REPEALED] </td>
      <td>&#160;&#160;</td>
      <td>&#160;&#160;</td>
    </tr>
  </table>
</body></html>
"""

SAMPLE_CHAPTER_HTML = """
<html><body>
  <h1 class="lso-toc"><center>TITLE 63 REVENUE AND TAXATION</center></h1>
  <h2 class="lso-toc"><center>CHAPTER 30 INCOME TAX</center></h2>
  <table>
    <tr>
      <td><a href="/statutesrules/idstat/Title63/T63CH30/SECT63-3002">63-3002</a></td>
      <td>&#160;&#160;</td>
      <td> DECLARATION OF INTENT. </td>
    </tr>
  </table>
</body></html>
"""

SAMPLE_SECTION_HTML = """
<html><body>
  <div class="pgbrk">
    <div style="line-height: 12pt; text-align: center"><span style="font-family: Courier New;">TITLE 63</span></div>
    <div style="line-height: 12pt; text-align: center"><span style="font-family: Courier New;">REVENUE AND TAXATION</span></div>
    <div style="line-height: 12pt; text-align: center"><span style="font-family: Courier New;">CHAPTER 30</span></div>
    <div style="line-height: 12pt; text-align: center"><span style="font-family: Courier New;">INCOME TAX</span></div>
    <div style="line-height: 12pt; text-align: justify"><span style="font-family: Courier New;">63-3002. <span style="text-transform: uppercase">Declaration of intent.</span> The income tax act applies with section 63-3003.</span></div>
    <div style="line-height: 12pt; text-align: justify"><span style="font-family: Courier New;">History:</span></div>
    <div style="line-height: 12pt; text-align: justify"><span style="font-family: Courier New;">[63-3002, added 1959, ch. 299, sec. 2, p. 613.]</span></div>
  </div>
</body></html>
"""

SAMPLE_RENDITIONED_SECTION_HTML = """
<html><body>
  <div class="pgbrk">
    <div style="font-family: Courier New; text-align: center">TITLE 63</div>
    <div style="font-family: Courier New; text-align: justify">63-3022E. Current text. [effective until January 1, 2027] Uses section <a href="/statutesrules/idstat/Title66/T66CH4/SECT66-402">66-402</a>(5).</div>
    <div style="font-family: Courier New; text-align: justify">63-3022E. Future text. [effective January 1, 2027] Uses section <a href="/statutesrules/idstat/Title66/T66CH4/SECT66-403">66-403</a>(4).</div>
    <div style="font-family: Courier New; text-align: justify">History:</div>
    <div style="font-family: Courier New; text-align: justify">[Added 2026.]</div>
  </div>
</body></html>
"""

SAMPLE_RECORDED = _RecordedSource(
    source_url="https://legislature.idaho.gov/statutesrules/idstat/",
    source_path="sources/us-id/statute/test/index.html",
    source_format=IDAHO_TITLE_INDEX_SOURCE_FORMAT,
    sha256="abc",
)


def test_parse_idaho_indexes_and_section_page():
    titles = parse_idaho_title_index(SAMPLE_TITLE_INDEX_HTML, source=SAMPLE_RECORDED)

    assert [title.number for title in titles] == ["63"]
    assert titles[0].heading == "REVENUE AND TAXATION"
    title_source = _RecordedSource(
        source_url=titles[0].source_url,
        source_path="sources/us-id/statute/test/title.html",
        source_format=IDAHO_TITLE_SOURCE_FORMAT,
        sha256="def",
    )
    chapters = parse_idaho_title_page(SAMPLE_TITLE_HTML, title=titles[0], source=title_source)

    assert [chapter.chapter for chapter in chapters] == ["30", "31"]
    assert chapters[0].pdf_url == (
        "https://legislature.idaho.gov/wp-content/uploads/statutesrules/idstat/Title63/T63CH30.pdf"
    )
    assert chapters[1].active is False
    assert chapters[1].status == "repealed"

    sections = parse_idaho_chapter_page(SAMPLE_CHAPTER_HTML, chapter=chapters[0])
    assert [section.section for section in sections] == ["63-3002"]
    section_source = _RecordedSource(
        source_url=sections[0].source_url,
        source_path="sources/us-id/statute/test/63-3002.html",
        source_format=IDAHO_SECTION_SOURCE_FORMAT,
        sha256="ghi",
    )
    parsed = parse_idaho_section_page(
        SAMPLE_SECTION_HTML,
        listing=sections[0],
        source=section_source,
    )

    assert parsed.heading == "Declaration of intent"
    assert parsed.body == "The income tax act applies with section 63-3003."
    assert parsed.source_history == ("[63-3002, added 1959, ch. 299, sec. 2, p. 613.]",)
    assert parsed.references_to == ("us-id/statute/63-3003",)


def test_parse_idaho_section_page_selects_expression_date_rendition():
    listing = IdahoSectionListing(
        title_number="63",
        chapter="30",
        section="63-3022E",
        heading="Household deduction",
        source_url=SAMPLE_RECORDED.source_url,
        ordinal=1,
    )

    current = parse_idaho_section_page(
        SAMPLE_RENDITIONED_SECTION_HTML,
        listing=listing,
        source=SAMPLE_RECORDED,
        expression_date="2026-07-13",
    )
    future = parse_idaho_section_page(
        SAMPLE_RENDITIONED_SECTION_HTML,
        listing=listing,
        source=SAMPLE_RECORDED,
        expression_date="2027-01-01",
    )

    assert current.heading == "Current text"
    assert "effective until January 1, 2027" in (current.body or "")
    assert "Future text" not in (current.body or "")
    assert current.references_to == ("us-id/statute/66-402",)
    assert current.source_history == ("[Added 2026.]",)
    assert future.heading == "Future text"
    assert "effective January 1, 2027" in (future.body or "")
    assert "Current text" not in (future.body or "")
    assert future.references_to == ("us-id/statute/66-403",)


def test_parse_idaho_section_page_requires_date_for_multiple_renditions():
    listing = IdahoSectionListing(
        title_number="63",
        chapter="30",
        section="63-3022E",
        heading="Household deduction",
        source_url=SAMPLE_RECORDED.source_url,
        ordinal=1,
    )

    with pytest.raises(ValueError, match="expression_date is required"):
        parse_idaho_section_page(
            SAMPLE_RENDITIONED_SECTION_HTML,
            listing=listing,
            source=SAMPLE_RECORDED,
        )


def test_extract_idaho_statutes_from_source_dir_writes_complete_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    (source_dir / IDAHO_TITLE_INDEX_SOURCE_FORMAT).mkdir(parents=True)
    (source_dir / IDAHO_TITLE_SOURCE_FORMAT).mkdir(parents=True)
    (source_dir / IDAHO_CHAPTER_SOURCE_FORMAT / "title-63").mkdir(parents=True)
    (source_dir / IDAHO_SECTION_SOURCE_FORMAT / "title-63" / "chapter-30").mkdir(parents=True)
    (source_dir / IDAHO_TITLE_INDEX_SOURCE_FORMAT / "index.html").write_text(
        SAMPLE_TITLE_INDEX_HTML,
        encoding="utf-8",
    )
    (source_dir / IDAHO_TITLE_SOURCE_FORMAT / "title-63.html").write_text(
        SAMPLE_TITLE_HTML,
        encoding="utf-8",
    )
    (source_dir / IDAHO_CHAPTER_SOURCE_FORMAT / "title-63" / "chapter-30.html").write_text(
        SAMPLE_CHAPTER_HTML,
        encoding="utf-8",
    )
    (
        source_dir / IDAHO_SECTION_SOURCE_FORMAT / "title-63" / "chapter-30" / "63-3002.html"
    ).write_text(SAMPLE_SECTION_HTML, encoding="utf-8")
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_idaho_statutes(
        store,
        version="2026-05-09",
        source_dir=source_dir,
        source_as_of="2025-07-01",
        expression_date="2025-07-01",
        only_title="63",
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 3
    assert report.section_count == 1
    assert report.provisions_written == 4
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    assert len(inventory) == 4
    assert [record.citation_path for record in records] == [
        "us-id/statute/title-63",
        "us-id/statute/title-63/chapter-30",
        "us-id/statute/63-3002",
        "us-id/statute/title-63/chapter-31",
    ]
    assert records[2].metadata is not None
    assert records[2].metadata["references_to"] == ["us-id/statute/63-3003"]
    assert records[3].metadata is not None
    assert records[3].metadata["status"] == "repealed"


RENDITIONED_LISTING = IdahoSectionListing(
    title_number="63",
    chapter="30",
    section="63-3022E",
    heading="Household deduction",
    source_url=SAMPLE_RECORDED.source_url,
    ordinal=34,
)


def test_parse_idaho_section_versions_keeps_later_rendition_as_variant():
    current, future = parse_idaho_section_versions(
        SAMPLE_RENDITIONED_SECTION_HTML,
        listing=RENDITIONED_LISTING,
        source=SAMPLE_RECORDED,
        expression_date="2026-09-14",
    )

    assert current == parse_idaho_section_page(
        SAMPLE_RENDITIONED_SECTION_HTML,
        listing=RENDITIONED_LISTING,
        source=SAMPLE_RECORDED,
        expression_date="2026-09-14",
    )
    assert current.variant is None
    assert current.citation_path == "us-id/statute/63-3022E"
    assert current.status is None
    assert current.effective_note is None

    assert future.variant == "effective-2027-01-01"
    assert future.citation_path == "us-id/statute/63-3022E--effective-2027-01-01"
    assert future.source_id == "63-3022E--effective-2027-01-01"
    assert future.canonical_citation_path == "us-id/statute/63-3022E"
    assert future.legal_identifier == current.legal_identifier == "Idaho Code § 63-3022E"
    assert future.heading == "Future text"
    assert future.body == "[effective January 1, 2027] Uses section 66-403 (4)."
    assert future.references_to == ("us-id/statute/66-403",)
    assert future.source_history == current.source_history == ("[Added 2026.]",)
    assert future.status == "future_or_conditional"
    assert future.effective_note == "effective January 1, 2027"


def test_parse_idaho_section_versions_after_the_switch_date():
    current, earlier = parse_idaho_section_versions(
        SAMPLE_RENDITIONED_SECTION_HTML,
        listing=RENDITIONED_LISTING,
        source=SAMPLE_RECORDED,
        expression_date="2027-01-01",
    )

    assert current.citation_path == "us-id/statute/63-3022E"
    assert current.heading == "Future text"
    assert earlier.citation_path == "us-id/statute/63-3022E--effective-until-2027-01-01"
    assert earlier.heading == "Current text"
    assert earlier.status == "effective_until"
    assert earlier.effective_note == "effective until January 1, 2027"


def test_parse_idaho_section_versions_single_rendition_is_one_plain_section():
    listing = IdahoSectionListing(
        title_number="63",
        chapter="30",
        section="63-3002",
        heading="Declaration of intent",
        source_url=SAMPLE_RECORDED.source_url,
        ordinal=1,
    )

    (only,) = parse_idaho_section_versions(
        SAMPLE_SECTION_HTML, listing=listing, source=SAMPLE_RECORDED
    )

    assert only.variant is None
    assert only.citation_path == "us-id/statute/63-3002"
    assert only == parse_idaho_section_page(
        SAMPLE_SECTION_HTML, listing=listing, source=SAMPLE_RECORDED
    )


def _rendition_div(text: str) -> str:
    return (
        '<div style="line-height: 12pt; text-align: justify">'
        f'<span style="font-family: Courier New;">{text}</span></div>'
    )


def _section_page(section: str, renditions: list[tuple[str, list[str]]], history: str) -> str:
    """An Idaho section page printing ``renditions`` as (first line, later lines)."""
    divs = [
        '<div style="line-height: 12pt; text-align: center">'
        f'<span style="font-family: Courier New;">{text}</span></div>'
        for text in ("TITLE 63", "REVENUE AND TAXATION", "CHAPTER 30", "INCOME TAX")
    ]
    for first, rest in renditions:
        divs.append(_rendition_div(f"{section}. {first}"))
        divs.extend(_rendition_div(line) for line in rest)
    if history:
        divs.extend((_rendition_div("History:"), _rendition_div(history)))
    return f'<html><body><div class="pgbrk">{"".join(divs)}</div></body></html>'


def test_parse_idaho_section_versions_names_an_unmarked_rendition_by_position():
    html = _section_page(
        "63-3022E",
        [
            ("Current text. [effective until January 1, 2027] (1) Old.", []),
            ("Unmarked text. (1) Undated.", []),
        ],
        "[Added 2026.]",
    )

    current, unmarked = parse_idaho_section_versions(
        html, listing=RENDITIONED_LISTING, source=SAMPLE_RECORDED, expression_date="2026-09-14"
    )

    assert current.heading == "Current text"
    assert unmarked.variant == "variant-2"
    assert unmarked.citation_path == "us-id/statute/63-3022E--variant-2"
    assert unmarked.status is None
    assert unmarked.effective_note is None


def test_parse_idaho_section_versions_rejects_two_renditions_with_one_name():
    html = _section_page(
        "63-3022E",
        [
            ("Current text. [effective until January 1, 2027] (1) Old.", []),
            ("Future text. [effective January 1, 2027] (1) New.", []),
            ("Future text. [effective January 1, 2027] (1) Newer.", []),
        ],
        "[Added 2026.]",
    )

    with pytest.raises(ValueError, match="two renditions named 'effective-2027-01-01'"):
        parse_idaho_section_versions(
            html, listing=RENDITIONED_LISTING, source=SAMPLE_RECORDED, expression_date="2026-09-14"
        )


def test_extract_idaho_statutes_writes_variant_rows_after_their_section(tmp_path):
    source_dir = tmp_path / "source"
    section_dir = source_dir / IDAHO_SECTION_SOURCE_FORMAT / "title-63" / "chapter-30"
    section_dir.mkdir(parents=True)
    (source_dir / IDAHO_TITLE_INDEX_SOURCE_FORMAT).mkdir(parents=True)
    (source_dir / IDAHO_TITLE_SOURCE_FORMAT).mkdir(parents=True)
    (source_dir / IDAHO_CHAPTER_SOURCE_FORMAT / "title-63").mkdir(parents=True)
    (source_dir / IDAHO_TITLE_INDEX_SOURCE_FORMAT / "index.html").write_text(
        SAMPLE_TITLE_INDEX_HTML, encoding="utf-8"
    )
    (source_dir / IDAHO_TITLE_SOURCE_FORMAT / "title-63.html").write_text(
        SAMPLE_TITLE_HTML, encoding="utf-8"
    )
    chapter_html = SAMPLE_CHAPTER_HTML.replace(
        "</table>",
        '<tr><td><a href="/statutesrules/idstat/Title63/T63CH30/SECT63-3022E">63-3022E</a>'
        "</td><td>&#160;</td><td> HOUSEHOLD DEDUCTION. </td></tr></table>",
    )
    (source_dir / IDAHO_CHAPTER_SOURCE_FORMAT / "title-63" / "chapter-30.html").write_text(
        chapter_html, encoding="utf-8"
    )
    (section_dir / "63-3002.html").write_text(SAMPLE_SECTION_HTML, encoding="utf-8")
    (section_dir / "63-3022E.html").write_text(SAMPLE_RENDITIONED_SECTION_HTML, encoding="utf-8")
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_idaho_statutes(
        store,
        version="2026-09-27",
        source_dir=source_dir,
        source_as_of="2026-09-14",
        expression_date="2026-09-14",
        only_title="63",
        only_chapter="30",
        limit=2,
    )

    assert report.errors == ()
    assert report.coverage.complete is True
    assert report.section_count == 3
    records = load_provisions(report.provisions_path)
    inventory = load_source_inventory(report.inventory_path)
    assert (
        [record.citation_path for record in records]
        == [item.citation_path for item in inventory]
        == [
            "us-id/statute/title-63",
            "us-id/statute/title-63/chapter-30",
            "us-id/statute/63-3002",
            "us-id/statute/63-3022E",
            "us-id/statute/63-3022E--effective-2027-01-01",
        ]
    )
    plain, variant = records[3], records[4]
    assert plain.metadata is not None and variant.metadata is not None
    assert "variant" not in plain.metadata
    assert variant.metadata["variant"] == "effective-2027-01-01"
    assert variant.metadata["canonical_citation_path"] == plain.citation_path
    assert variant.metadata["effective_note"] == "effective January 1, 2027"
    assert variant.metadata["status"] == "future_or_conditional"
    assert variant.id != plain.id
    assert (variant.parent_citation_path, variant.level, variant.ordinal, variant.kind) == (
        plain.parent_citation_path,
        plain.level,
        plain.ordinal,
        plain.kind,
    )
    assert (variant.source_path, variant.source_url, variant.source_format) == (
        plain.source_path,
        plain.source_url,
        plain.source_format,
    )
    assert inventory[4].sha256 == inventory[3].sha256
    assert inventory[4].metadata is not None
    assert inventory[4].metadata["variant"] == "effective-2027-01-01"
    assert inventory[4].metadata["canonical_citation_path"] == plain.citation_path


# --- Invariants over generated pages ---------------------------------------
#
# For every page of 1-4 renditions, each with no marker, "[effective <date>]",
# "[effective until <date>]" or a marker with an impossible date, and for a
# valid, missing or malformed expression date:
#   1. differential: the plain section equals what origin/main f1916d73b
#      produced, error for error with identical messages, so no plain row
#      moves. The oracle is that commit's ``_select_section_rendition`` and
#      ``_rendition_effective_marker``, copied verbatim below; the body parser
#      they feed was moved into ``_parse_section_divs`` without change, so the
#      differential isolates rendition selection;
#   2. selection: on well-formed inputs the plain section is the one rendition
#      a model of the markers says is in force (a page with one rendition is
#      read whole), and parsing raises exactly when the model finds none;
#   3. conservation: each printed rendition is exactly one section, in printed
#      order after the plain one, with its own heading and body and the
#      page's shared History;
#   4. naming: variant names follow the marker, are unique or rejected, and
#      give grammar-valid sibling paths whose canonical path is the plain one;
#   5. status: a dated variant is never in force, and its status and
#      effective_note follow its marker;
#   6. determinism: parsing twice gives equal results.

_WORDS = ("income", "tax", "deduction", "shall", "be", "allowed", "household", "the", "$1,000")
_DATES = (date(2025, 1, 1), date(2026, 7, 1), date(2027, 1, 1), date(2028, 6, 30))
_IMPOSSIBLE = "February 30, 2027"
# None, (date, until), or (None, until) for a marker with an impossible date.
_MARKERS = st.one_of(
    st.none(),
    st.tuples(st.sampled_from(_DATES), st.booleans()),
    st.tuples(st.none(), st.booleans()),
)
_LINES = st.lists(st.sampled_from(_WORDS), min_size=1, max_size=6).map(" ".join)
_HEADINGS = st.lists(
    st.sampled_from(("Household", "deduction", "Payment", "credit")), min_size=1, max_size=3
).map(" ".join)
_RENDITIONS = st.lists(
    st.tuples(_HEADINGS, _MARKERS, st.lists(_LINES, min_size=1, max_size=3)),
    min_size=1,
    max_size=4,
)
_EXPRESSION_DATES = st.one_of(
    st.dates(min_value=date(2024, 1, 1), max_value=date(2029, 12, 31)).map(date.isoformat),
    st.sampled_from((None, "2026-13-01")),
)


def _marker_text(marker: tuple[date | None, bool]) -> str:
    when, until = marker
    printed = _IMPOSSIBLE if when is None else f"{when:%B} {when.day}, {when.year}"
    return f"effective {'until ' if until else ''}{printed}"


_REFERENCE_EFFECTIVE_RE = re.compile(
    r"\[effective(?P<until>\s+until)?\s+"
    r"(?P<date>[A-Z][a-z]+\s+\d{1,2},\s+\d{4})\]",
    re.I,
)


def _reference_select_section_rendition(
    divs,
    *,
    section,
    expression_date,
):
    """Select one effective rendition when an Idaho page publishes several."""
    starts = [
        index
        for index, div in enumerate(divs)
        if _strip_section_heading(_clean_text(div), section)[1] is not None
    ]
    if len(starts) <= 1:
        return divs
    if expression_date is None:
        raise ValueError(
            f"Idaho section {section} publishes {len(starts)} renditions; "
            "expression_date is required"
        )

    as_of = _coerce_expression_date(expression_date)
    matching: list[int] = []
    unmarked: list[int] = []
    for start in starts:
        marker = _reference_rendition_effective_marker(_clean_text(divs[start]))
        if marker is None:
            unmarked.append(start)
            continue
        effective_date, is_until = marker
        if (is_until and as_of < effective_date) or (not is_until and as_of >= effective_date):
            matching.append(start)
    if len(matching) == 1:
        selected_start = matching[0]
    elif not matching and len(unmarked) == 1:
        selected_start = unmarked[0]
    else:
        raise ValueError(f"Idaho section {section} has no unique rendition for {as_of.isoformat()}")

    history_start = next(
        (
            index
            for index in range(starts[-1] + 1, len(divs))
            if _is_history_marker(_clean_text(divs[index]))
        ),
        len(divs),
    )
    next_start = next((start for start in starts if start > selected_start), history_start)
    selected_end = min(next_start, history_start)
    return (*divs[: starts[0]], *divs[selected_start:selected_end], *divs[history_start:])


def _reference_rendition_effective_marker(text: str):
    match = _REFERENCE_EFFECTIVE_RE.search(text)
    if match is None:
        return None
    effective_date = datetime.strptime(match.group("date"), "%B %d, %Y").date()
    return effective_date, match.group("until") is not None


def _reference_plain_section(html: str, expression_date: str | None):
    divs = _section_content_divs(BeautifulSoup(html, "lxml"))
    selected = _reference_select_section_rendition(
        divs, section=RENDITIONED_LISTING.section, expression_date=expression_date
    )
    return _parse_section_divs(selected, listing=RENDITIONED_LISTING, source=SAMPLE_RECORDED)


def _in_force(marker: tuple[date, bool], as_of: date) -> bool:
    when, until = marker
    return as_of < when if until else as_of >= when


def _outcome(call):
    try:
        return call()
    except ValueError as exc:
        return exc


@settings(max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    renditions=_RENDITIONS,
    expression_date=_EXPRESSION_DATES,
    history=st.sampled_from(("", "[Added 2026.]")),
)
def test_idaho_rendition_invariants(renditions, expression_date, history):
    printed = []
    expected_bodies = []
    for heading, marker, lines in renditions:
        first = f"[{_marker_text(marker)}] {lines[0]}" if marker else lines[0]
        printed.append((f"{heading}. {first}", lines[1:]))
        expected_bodies.append("\n".join([first, *lines[1:]]))
    html = _section_page(RENDITIONED_LISTING.section, printed, history)

    def parse():
        return parse_idaho_section_versions(
            html,
            listing=RENDITIONED_LISTING,
            source=SAMPLE_RECORDED,
            expression_date=expression_date,
        )

    reference = _outcome(lambda: _reference_plain_section(html, expression_date))
    outcome = _outcome(parse)

    # 1. differential, error for error.
    if isinstance(reference, ValueError):
        event("main raises: branch raises the same error")
        assert isinstance(outcome, ValueError)
        assert str(outcome) == str(reference)
        return
    if isinstance(outcome, ValueError):
        event("two variants share a name: fails closed")
        assert "two renditions named" in str(outcome)
        names = [
            _variant_name(r[1], i) for i, r in enumerate(renditions) if r[1] is None or r[1][0]
        ]
        assert len(set(names)) < len(names) or len(renditions) > 1
        return
    sections = outcome
    plain, variants = sections[0], sections[1:]
    assert plain == reference
    event(f"{len(variants)} variant(s)")
    # 6. determinism.
    assert sections == parse()

    if len(renditions) == 1:
        assert variants == ()
        assert plain.body == expected_bodies[0]
        return

    # 2. selection (well-formed inputs only reach here with several renditions:
    # main raises on a missing or malformed date and on an impossible marker).
    as_of = date.fromisoformat(expression_date)
    matching = [i for i, r in enumerate(renditions) if r[1] and _in_force(r[1], as_of)]
    unmarked = [i for i, r in enumerate(renditions) if not r[1]]
    primary = matching[0] if len(matching) == 1 else unmarked[0]
    assert len(matching) == 1 or (not matching and len(unmarked) == 1)
    others = [i for i in range(len(renditions)) if i != primary]
    assert plain.variant is None
    assert plain.citation_path == "us-id/statute/63-3022E"
    assert plain.heading == renditions[primary][0]
    assert plain.body == expected_bodies[primary]
    # 3. conservation: every printed rendition is exactly one section.
    assert [section.body for section in variants] == [expected_bodies[i] for i in others]
    assert [section.heading for section in variants] == [renditions[i][0] for i in others]
    assert sorted(section.body or "" for section in sections) == sorted(expected_bodies)
    assert all(section.source_history == ((history,) if history else ()) for section in sections)
    # 4. naming.
    assert [section.variant for section in variants] == [
        _variant_name(renditions[i][1], i) for i in others
    ]
    paths = [section.citation_path for section in sections]
    assert len(set(paths)) == len(paths)
    for index, section in zip(others, variants, strict=True):
        assert section.canonical_citation_path == plain.citation_path
        assert section.citation_path == f"{plain.citation_path}--{section.variant}"
        assert CITATION_PATH_RE.fullmatch(section.citation_path)
        assert SEGMENT_RE.fullmatch(section.citation_path.rsplit("/", 1)[1])
        # 5. status.
        marker = renditions[index][1]
        if marker is None:
            assert (section.status, section.effective_note) == (None, None)
        else:
            assert not _in_force(marker, as_of)
            assert section.effective_note == _marker_text(marker)
            assert section.status == ("effective_until" if marker[1] else "future_or_conditional")


def _variant_name(marker: tuple[date | None, bool] | None, index: int) -> str:
    if marker is None:
        return f"variant-{index + 1}"
    when, until = marker
    assert when is not None
    return f"effective-{'until-' if until else ''}{when.isoformat()}"
