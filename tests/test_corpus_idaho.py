import json
import re
from datetime import date, datetime, timedelta
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
    IdahoRenditionError,
    IdahoSection,
    IdahoSectionListing,
    _clean_heading,
    _clean_text,
    _coerce_expression_date,
    _decode,
    _extract_section_references,
    _is_centered_header,
    _is_history_marker,
    _is_note_marker,
    _join_paragraphs,
    _RecordedSource,
    _section_content_divs,
    _section_status,
    _strip_note_marker,
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


def _versions_error(html: str, expression_date: str | None = "2026-09-14") -> IdahoRenditionError:
    with pytest.raises(IdahoRenditionError) as raised:
        parse_idaho_section_versions(
            html,
            listing=RENDITIONED_LISTING,
            source=SAMPLE_RECORDED,
            expression_date=expression_date,
        )
    # The plain section is still exactly the single-row API's.
    assert raised.value.primary == parse_idaho_section_page(
        html, listing=RENDITIONED_LISTING, source=SAMPLE_RECORDED, expression_date=expression_date
    )
    return raised.value


def test_two_renditions_with_one_name_keep_the_plain_row_and_report_the_page():
    html = _section_page(
        "63-3022E",
        [
            ("Current text. [effective until January 1, 2027] (1) Old.", []),
            ("Future text. [effective January 1, 2027] (1) New.", []),
            ("Future text. [effective January 1, 2027] (1) Newer.", []),
        ],
        "[Added 2026.]",
    )

    error = _versions_error(html)

    assert "two renditions named 'effective-2027-01-01'" in str(error)
    assert error.primary.heading == "Current text"
    assert error.primary.body == "[effective until January 1, 2027] (1) Old."


def test_a_section_heading_quoted_in_a_note_is_never_a_variant():
    page = _section_page(
        "63-3022E",
        [("Current text. [effective until January 1, 2027] (1) Old.", [])],
        "",
    ).replace(
        "</div></body>",
        _rendition_div("Compiler's notes:")
        + _rendition_div("63-3022E. Quotation. Commentary.")
        + "</div></body>",
    )

    error = _versions_error(page)

    assert "rendition 2 after its History or notes begin" in str(error)
    assert error.primary.body == "[effective until January 1, 2027] (1) Old."


def test_a_quoted_marker_never_names_a_variant():
    html = _section_page(
        "63-3022E",
        [
            ("Current text. [effective until January 1, 2027] (1) Old.", []),
            ("Other text. (1) Applies after the [effective January 1, 2027] change.", []),
        ],
        "[Added 2026.]",
    )

    error = _versions_error(html)

    assert "rendition 2 has a marker inside its text" in str(error)


@pytest.mark.parametrize(
    ("expression_date", "message"),
    [
        (None, "expression_date is required"),
        ("invalid", "invalid Idaho expression_date: 'invalid'"),
    ],
)
def test_date_checks_come_before_marker_parsing(expression_date, message):
    html = _section_page(
        "63-3022E",
        [
            ("Current text. [effective until February 30, 2027] (1) Old.", []),
            ("Future text. [effective January 1, 2027] (1) New.", []),
        ],
        "[Added 2026.]",
    )

    for parse in (parse_idaho_section_page, parse_idaho_section_versions):
        with pytest.raises(ValueError, match=re.escape(message)):
            parse(
                html,
                listing=RENDITIONED_LISTING,
                source=SAMPLE_RECORDED,
                expression_date=expression_date,
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


def _two_chapter_source_dir(root: Path, section_3022e_html: str) -> Path:
    """Title 63 with chapter 30 (63-3022E) and chapter 31 (63-3101), both linked."""
    source_dir = root / "source"
    for directory in (
        source_dir / IDAHO_TITLE_INDEX_SOURCE_FORMAT,
        source_dir / IDAHO_TITLE_SOURCE_FORMAT,
        source_dir / IDAHO_CHAPTER_SOURCE_FORMAT / "title-63",
        source_dir / IDAHO_SECTION_SOURCE_FORMAT / "title-63" / "chapter-30",
        source_dir / IDAHO_SECTION_SOURCE_FORMAT / "title-63" / "chapter-31",
    ):
        directory.mkdir(parents=True)
    (source_dir / IDAHO_TITLE_INDEX_SOURCE_FORMAT / "index.html").write_text(
        SAMPLE_TITLE_INDEX_HTML, encoding="utf-8"
    )
    title_html = SAMPLE_TITLE_HTML.replace(
        "<td>CHAPTER 31</td>",
        '<td><a href="/statutesrules/idstat/Title63/T63CH31">CHAPTER 31</a></td>',
    ).replace("OLD TAX ACT [REPEALED]", "OTHER TAX")
    (source_dir / IDAHO_TITLE_SOURCE_FORMAT / "title-63.html").write_text(
        title_html, encoding="utf-8"
    )
    for chapter, section, heading in (
        ("30", "63-3022E", "HOUSEHOLD DEDUCTION"),
        ("31", "63-3101", "OTHER TAX"),
    ):
        listing_html = (
            f'<html><body><table><tr><td><a href="/statutesrules/idstat/Title63/T63CH{chapter}'
            f'/SECT{section}">{section}</a></td><td>&#160;</td><td> {heading}. </td></tr>'
            "</table></body></html>"
        )
        (
            source_dir / IDAHO_CHAPTER_SOURCE_FORMAT / "title-63" / f"chapter-{chapter}.html"
        ).write_text(listing_html, encoding="utf-8")
    sections = source_dir / IDAHO_SECTION_SOURCE_FORMAT / "title-63"
    (sections / "chapter-30" / "63-3022E.html").write_text(section_3022e_html, encoding="utf-8")
    (sections / "chapter-31" / "63-3101.html").write_text(
        SAMPLE_SECTION_HTML.replace("63-3002", "63-3101"), encoding="utf-8"
    )
    return source_dir


def test_limit_counts_sections_not_variant_rows(tmp_path):
    """With limit 2, the variant row of the first section must not use up the
    second section's slot in the next chapter."""
    source_dir = _two_chapter_source_dir(tmp_path, SAMPLE_RENDITIONED_SECTION_HTML)

    report = extract_idaho_statutes(
        CorpusArtifactStore(tmp_path / "corpus"),
        version="2026-09-27",
        source_dir=source_dir,
        source_as_of="2026-09-14",
        expression_date="2026-09-14",
        only_title="63",
        limit=2,
    )

    assert report.errors == ()
    assert report.section_count == 3
    assert [record.citation_path for record in load_provisions(report.provisions_path)] == [
        "us-id/statute/title-63",
        "us-id/statute/title-63/chapter-30",
        "us-id/statute/63-3022E",
        "us-id/statute/63-3022E--effective-2027-01-01",
        "us-id/statute/title-63/chapter-31",
        "us-id/statute/63-3101",
    ]


def test_extraction_keeps_the_plain_row_of_a_page_it_reports(tmp_path):
    clashing = _section_page(
        "63-3022E",
        [
            ("Current text. [effective until January 1, 2027] (1) Old.", []),
            ("Future text. [effective January 1, 2027] (1) New.", []),
            ("Future text. [effective January 1, 2027] (1) Newer.", []),
        ],
        "[Added 2026.]",
    )
    source_dir = _two_chapter_source_dir(tmp_path, clashing)

    report = extract_idaho_statutes(
        CorpusArtifactStore(tmp_path / "corpus"),
        version="2026-09-27",
        source_dir=source_dir,
        source_as_of="2026-09-14",
        expression_date="2026-09-14",
        only_title="63",
    )

    assert len(report.errors) == 1
    assert report.errors[0].startswith("section 63-3022E: Idaho section 63-3022E prints two")
    assert report.coverage.complete is True
    records = {record.citation_path: record for record in load_provisions(report.provisions_path)}
    assert "us-id/statute/63-3022E--effective-2027-01-01" not in records
    assert records["us-id/statute/63-3022E"].body == "[effective until January 1, 2027] (1) Old."
    assert "us-id/statute/63-3101" in records


# --- Invariants over generated pages ---------------------------------------
#
# Pages of 1-4 renditions. Each rendition has no marker, "[effective <date>]",
# "[effective until <date>]" or one with an impossible date, led by the marker
# or with it inside the text; pages may carry an unheaded prefix line, a
# History, and a compiler's note that may quote the section heading; the
# expression date is valid, missing or malformed. For every such page:
#   1. differential: ``parse_idaho_section_page`` equals origin/main
#      f1916d73b's ``parse_idaho_section_page``, error for error with identical
#      messages. The oracle below is that function with its
#      ``_select_section_rendition`` and ``_rendition_effective_marker``,
#      copied verbatim; the helpers it calls are unchanged by this branch;
#   2. the plain row never moves: ``parse_idaho_section_versions`` raises the
#      same error, or returns that section first, or raises
#      ``IdahoRenditionError`` carrying exactly that section;
#   3. it refuses exactly when a rendition opens after the History or notes
#      begin, a marker is not the first thing after its heading, or two
#      variants would share a name;
#   4. selection: on well-formed pages the plain row is the one rendition a
#      model of the markers says is in force (one rendition: the whole page);
#   5. conservation: each printed rendition is exactly one section, variants
#      in printed order after the plain one, each with its own heading and
#      body and the page's shared History;
#   6. naming: variant names follow the markers and give grammar-valid sibling
#      paths whose canonical path is the plain one;
#   7. status: a dated variant is never in force; its status and
#      effective_note follow its marker;
#   8. determinism: parsing twice gives equal results.

_WORDS = ("income", "tax", "deduction", "shall", "be", "allowed", "household", "the", "$1,000")
_DATES = (date(2025, 1, 1), date(2026, 7, 1), date(2027, 1, 1), date(2028, 6, 30))
_IMPOSSIBLE = "February 30, 2027"
# None, (date, until), or (None, until) for a marker with an impossible date,
# weighted towards well-formed markers so most pages reach the variant path.
_MARKER_CHOICES = (
    None,
    None,
    *((when, until) for when in _DATES for until in (False, True)),
    (None, False),
    (None, True),
)
_MARKERS = st.sampled_from(_MARKER_CHOICES)
_LINES = st.lists(st.sampled_from(_WORDS), min_size=1, max_size=6).map(" ".join)
_HEADINGS = st.lists(
    st.sampled_from(("Household", "deduction", "Payment", "credit")), min_size=1, max_size=3
).map(" ".join)
# (heading, marker, marker leads its text, lines)
_RENDITIONS = st.lists(
    st.tuples(
        _HEADINGS,
        _MARKERS,
        st.sampled_from((True,) * 7 + (False,)),
        st.lists(_LINES, min_size=1, max_size=3),
    ),
    min_size=1,
    max_size=4,
)
_VALID_DATES = st.dates(min_value=date(2024, 1, 1), max_value=date(2029, 12, 31)).map(
    date.isoformat
)
_EXPRESSION_DATES = st.one_of(
    _VALID_DATES, _VALID_DATES, _VALID_DATES, st.sampled_from((None, "2026-13-01"))
)
# None, a plain compiler's note, or one that quotes the section heading.
_NOTES = st.sampled_from((None,) * 6 + ("plain", "quotes heading"))


def _marker_text(marker: tuple[date | None, bool]) -> str:
    when, until = marker
    printed = _IMPOSSIBLE if when is None else f"{when:%B} {when.day}, {when.year}"
    return f"effective {'until ' if until else ''}{printed}"


_REFERENCE_EFFECTIVE_RE = re.compile(
    r"\[effective(?P<until>\s+until)?\s+"
    r"(?P<date>[A-Z][a-z]+\s+\d{1,2},\s+\d{4})\]",
    re.I,
)


def _reference_parse_idaho_section_page(
    html,
    *,
    listing,
    source,
    expression_date=None,
):
    """Parse one official Idaho Statutes section HTML page."""
    soup = BeautifulSoup(_decode(html), "lxml")
    content_divs = _section_content_divs(soup)
    if not content_divs:
        raise ValueError("Idaho section page has no statute content divs")
    content_divs = _reference_select_section_rendition(
        content_divs,
        section=listing.section,
        expression_date=expression_date,
    )

    heading = _clean_heading(listing.heading) or f"Section {listing.section}"
    body_parts: list[str] = []
    history_parts: list[str] = []
    note_parts: list[str] = []
    in_history = False
    in_notes = False
    found_section = False

    for div in content_divs:
        text = _clean_text(div)
        if not text:
            continue
        if _is_centered_header(div):
            continue
        if _is_history_marker(text):
            in_history = True
            in_notes = False
            continue
        if _is_note_marker(text):
            in_notes = True
            in_history = False
            note = _strip_note_marker(text)
            if note:
                note_parts.append(note)
            continue

        if in_history:
            history_parts.append(text)
            continue
        if in_notes:
            note_parts.append(text)
            continue

        if not found_section:
            section_text, parsed_heading = _strip_section_heading(text, listing.section)
            if parsed_heading:
                heading = parsed_heading
            if section_text:
                body_parts.append(section_text)
            found_section = True
            continue

        body_parts.append(text)

    body = _join_paragraphs(body_parts)
    history = tuple(part for part in (_join_paragraphs(history_parts),) if part)
    notes = tuple(part for part in (_join_paragraphs(note_parts),) if part)
    references_to = _extract_section_references(
        content_divs,
        "\n".join(part for part in [body or "", *notes] if part),
        current=listing.section,
    )
    status = _section_status(heading, body, history + notes)
    return IdahoSection(
        listing=listing,
        heading=heading,
        body=body,
        source_history=history,
        source_notes=notes,
        references_to=references_to,
        source_url=source.source_url,
        source_path=source.source_path,
        source_format=source.source_format,
        sha256=source.sha256,
        status=status,
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


def _in_force(marker: tuple[date, bool], as_of: date) -> bool:
    when, until = marker
    return as_of < when if until else as_of >= when


def _variant_name(marker: tuple[date | None, bool] | None, index: int) -> str:
    if marker is None:
        return f"variant-{index + 1}"
    when, until = marker
    assert when is not None
    return f"effective-{'until-' if until else ''}{when.isoformat()}"


def _outcome(parse, html, **kwargs):
    try:
        return parse(html, **kwargs)
    except ValueError as exc:
        return exc


@settings(max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    renditions=_RENDITIONS,
    expression_date=_EXPRESSION_DATES,
    history=st.sampled_from(("", "[Added 2026.]")),
    note=_NOTES,
    prefix=st.sampled_from((False,) * 5 + (True,)),
)
def test_idaho_rendition_invariants(renditions, expression_date, history, note, prefix):
    section = RENDITIONED_LISTING.section
    printed = []
    expected_bodies = []
    for heading, marker, leads, lines in renditions:
        if marker is None:
            first = lines[0]
        elif leads:
            first = f"[{_marker_text(marker)}] {lines[0]}"
        else:
            first = f"{lines[0]} [{_marker_text(marker)}]"
        printed.append((f"{heading}. {first}", lines[1:]))
        expected_bodies.append("\n".join([first, *lines[1:]]))
    html = _section_page(section, printed, history)
    if note is not None:
        quoted = (
            _rendition_div(f"{section}. Quoted. Commentary.") if note == "quotes heading" else ""
        )
        html = html.replace(
            "</div></body>",
            _rendition_div("Compiler's notes:")
            + _rendition_div("See the act.")
            + quoted
            + "</div></body>",
        )
    if prefix:
        html = html.replace(
            '<div class="pgbrk">', '<div class="pgbrk">' + _rendition_div("Prefix line.")
        )

    kwargs = {
        "listing": RENDITIONED_LISTING,
        "source": SAMPLE_RECORDED,
        "expression_date": expression_date,
    }
    reference = _outcome(_reference_parse_idaho_section_page, html, **kwargs)
    compat = _outcome(parse_idaho_section_page, html, **kwargs)
    versions = _outcome(parse_idaho_section_versions, html, **kwargs)

    # 1. the single-row API is origin/main's, error for error.
    if isinstance(reference, ValueError):
        assert isinstance(compat, ValueError) and str(compat) == str(reference)
        # 2. the all-renditions API raises the same error.
        assert isinstance(versions, ValueError)
        assert not isinstance(versions, IdahoRenditionError)
        assert str(versions) == str(reference)
        event("main raises: both APIs raise the same error")
        return
    assert compat == reference
    # 8. determinism.
    assert parse_idaho_section_page(html, **kwargs) == compat

    # 3. the refusals, modelled. Only a page main reads as several renditions
    # (the note's quoted heading counts as one) can be refused.
    starts = len(renditions) + (note == "quotes heading")
    in_apparatus = starts > 1 and note == "quotes heading"
    inside = starts > 1 and any(r[1] is not None and not r[2] for r in renditions)
    if isinstance(versions, IdahoRenditionError):
        # 2. the plain row is kept, unchanged.
        assert versions.primary == compat
        assert in_apparatus or inside or "two renditions named" in str(versions)
        event("refused: plain row kept")
        return
    assert not isinstance(versions, ValueError)
    assert not in_apparatus and not inside
    sections = versions
    assert sections == parse_idaho_section_versions(html, **kwargs)
    plain, variants = sections[0], sections[1:]
    assert plain == compat
    event(f"{len(variants)} variant(s)")
    if len(renditions) == 1 or prefix:
        # An unheaded prefix line takes the heading slot in main's body parser
        # (inherited); the differential above already covers those pages.
        assert len(variants) == len(renditions) - 1
        return

    # 4. selection on a well-formed page.
    as_of = date.fromisoformat(expression_date)
    matching = [i for i, r in enumerate(renditions) if r[1] and _in_force(r[1], as_of)]
    unmarked = [i for i, r in enumerate(renditions) if not r[1]]
    assert len(matching) == 1 or (not matching and len(unmarked) == 1)
    primary = matching[0] if len(matching) == 1 else unmarked[0]
    others = [i for i in range(len(renditions)) if i != primary]
    assert plain.variant is None
    assert plain.citation_path == "us-id/statute/63-3022E"
    assert plain.heading == renditions[primary][0]
    assert plain.body == expected_bodies[primary]
    # 5. conservation.
    assert [s.body for s in variants] == [expected_bodies[i] for i in others]
    assert [s.heading for s in variants] == [renditions[i][0] for i in others]
    assert sorted(s.body or "" for s in sections) == sorted(expected_bodies)
    assert all(s.source_history == ((history,) if history else ()) for s in sections)
    # 6. naming.
    assert [s.variant for s in variants] == [_variant_name(renditions[i][1], i) for i in others]
    paths = [s.citation_path for s in sections]
    assert len(set(paths)) == len(paths)
    for index, variant in zip(others, variants, strict=True):
        assert variant.canonical_citation_path == plain.citation_path
        assert variant.citation_path == f"{plain.citation_path}--{variant.variant}"
        assert CITATION_PATH_RE.fullmatch(variant.citation_path)
        assert SEGMENT_RE.fullmatch(variant.citation_path.rsplit("/", 1)[1])
        # 7. status.
        marker = renditions[index][1]
        if marker is None:
            assert (variant.status, variant.effective_note) == (None, None)
        else:
            assert not _in_force(marker, as_of)
            assert variant.effective_note == _marker_text(marker)
            assert variant.status == ("effective_until" if marker[1] else "future_or_conditional")


_GRID_MARKERS = (
    "",
    "[effective until January 1, 2027] ",
    "[effective January 1, 2027] ",
    "[effective February 30, 2027] ",
    "inside [effective January 1, 2027] ",
)


@pytest.mark.parametrize("expression_date", ["2026-09-14", "2027-01-01", None, "invalid"])
def test_single_row_api_matches_main_on_every_small_page(expression_date):
    """Exhaustive differential over 1-3 renditions with five marker choices each
    (155 pages per expression date): origin/main's parser and this branch's
    single-row API agree, error for error, and the all-renditions API keeps
    that row or raises the same error."""
    import itertools

    for count in (1, 2, 3):
        for markers in itertools.product(_GRID_MARKERS, repeat=count):
            html = _section_page(
                "63-3022E",
                [(f"Text {i}. {marker}(1) Line {i}.", []) for i, marker in enumerate(markers)],
                "[Added 2026.]",
            )
            kwargs = {
                "listing": RENDITIONED_LISTING,
                "source": SAMPLE_RECORDED,
                "expression_date": expression_date,
            }
            reference = _outcome(_reference_parse_idaho_section_page, html, **kwargs)
            compat = _outcome(parse_idaho_section_page, html, **kwargs)
            versions = _outcome(parse_idaho_section_versions, html, **kwargs)
            if isinstance(reference, ValueError):
                assert type(compat) is type(versions) is ValueError
                assert str(compat) == str(versions) == str(reference)
            elif isinstance(versions, IdahoRenditionError):
                assert compat == reference == versions.primary
            else:
                assert compat == reference == versions[0]


@st.composite
def _well_formed_pages(draw):
    """A page whose renditions have exactly one in force on ``as_of``, the
    others dated before or after it, and distinct names (the shape of the
    retained §§63-3022E and 63-3025D pages, generalised)."""
    as_of = draw(st.dates(min_value=date(2025, 1, 2), max_value=date(2028, 12, 30)))
    before = st.dates(max_value=as_of, min_value=date(2020, 1, 1))
    after = st.dates(min_value=as_of + timedelta(days=1), max_value=date(2032, 12, 31))
    in_force = draw(
        st.sampled_from(("unmarked", "until", "from")).flatmap(
            lambda kind: st.just((kind, None))
            if kind == "unmarked"
            else (after if kind == "until" else before).map(lambda when: (kind, when))
        )
    )
    others = draw(
        st.lists(
            st.one_of(
                after.map(lambda when: ("from", when)),
                before.map(lambda when: ("until", when)),
            ),
            min_size=1,
            max_size=3,
            unique_by=lambda item: item,
        )
    )
    renditions = [in_force, *others]
    order = draw(st.permutations(range(len(renditions))))
    lines = draw(st.lists(st.lists(_LINES, min_size=1, max_size=3), min_size=4, max_size=4))
    headings = draw(st.lists(_HEADINGS, min_size=4, max_size=4))
    return as_of, [renditions[i] for i in order], order.index(0), lines, headings


def _well_formed_marker(kind: str, when: date | None) -> tuple[date, bool] | None:
    return None if kind == "unmarked" or when is None else (when, kind == "until")


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(page=_well_formed_pages(), history=st.sampled_from(("", "[Added 2026.]")))
def test_well_formed_pages_keep_every_rendition(page, history):
    """Selection, conservation, naming and status on pages with one rendition in
    force: every rendition becomes exactly one row."""
    as_of, renditions, primary, lines, headings = page
    printed, bodies = [], []
    for index, (kind, when) in enumerate(renditions):
        marker = _well_formed_marker(kind, when)
        first = f"[{_marker_text(marker)}] {lines[index][0]}" if marker else lines[index][0]
        printed.append((f"{headings[index]}. {first}", lines[index][1:]))
        bodies.append("\n".join([first, *lines[index][1:]]))
    html = _section_page(RENDITIONED_LISTING.section, printed, history)

    sections = parse_idaho_section_versions(
        html,
        listing=RENDITIONED_LISTING,
        source=SAMPLE_RECORDED,
        expression_date=as_of.isoformat(),
    )

    others = [i for i in range(len(renditions)) if i != primary]
    plain, variants = sections[0], sections[1:]
    assert plain == _reference_parse_idaho_section_page(
        html,
        listing=RENDITIONED_LISTING,
        source=SAMPLE_RECORDED,
        expression_date=as_of.isoformat(),
    )
    assert (plain.variant, plain.body, plain.heading) == (None, bodies[primary], headings[primary])
    assert [s.body for s in variants] == [bodies[i] for i in others]
    assert [s.heading for s in variants] == [headings[i] for i in others]
    assert all(s.source_history == ((history,) if history else ()) for s in sections)
    assert len({s.citation_path for s in sections}) == len(sections)
    for index, variant in zip(others, variants, strict=True):
        marker = _well_formed_marker(*renditions[index])
        assert variant.variant == _variant_name(marker, index)
        assert variant.canonical_citation_path == plain.citation_path
        assert CITATION_PATH_RE.fullmatch(variant.citation_path)
        assert marker is not None and not _in_force(marker, as_of)
        assert variant.effective_note == _marker_text(marker)
        assert variant.status == ("effective_until" if marker[1] else "future_or_conditional")
    event(f"{len(variants)} variant(s)")
