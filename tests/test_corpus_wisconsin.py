import hashlib
import json
from pathlib import Path

import pytest
import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters import wisconsin
from axiom_corpus.corpus.state_adapters.wisconsin import (
    WISCONSIN_STATUTES_SOURCE_FORMAT,
    WisconsinChapterLink,
    WisconsinSource,
    extract_wisconsin_publication_note,
    extract_wisconsin_statutes,
    parse_wisconsin_chapter_links,
    parse_wisconsin_chapter_page,
)

ROOT = Path(__file__).resolve().parents[1]
RECOVERY_MANIFEST_PATH = ROOT / "manifests/state-statutes.pit-west-recovery.yaml"
RECOVERY_VERSION = "2026-07-16-pit-west-chapter-71"
RECOVERY_INGEST_MANIFEST_PATH = (
    ROOT / ".axiom/ingest-manifests/us-wi/statute" / f"{RECOVERY_VERSION}.json"
)
SUBUNITS_MANIFEST_PATH = ROOT / "manifests/us-wi-statutes-chapter-71-subunits.yaml"
SUBUNITS_VERSION = "2026-09-23-income-tax-subunits-chapter-71"

TOC_HTML = """
<html><body>
<div class="qssubhead"><span class="qstr">Updated through 2025 Wisconsin Act 103 and through all Orders of the Controlled Substances Board affecting Chapter 961 and Supreme Court Orders filed before and in effect on April 3, 2026.</span></div>
<div class="qstoc_entry"><span class="qstr"><a rel="statutes/ch. 71" href="/document/statutes/ch.%2071" title="Statutes ch. 71">71. Income and franchise taxes for state and local revenues.</a></span></div>
<div class="qstoc_entry"><span class="qstr"><a rel="statutes/ch. 72" href="/document/statutes/ch.%2072" title="Statutes ch. 72">72. Estate tax.</a></span></div>
</body></html>
"""

CHAPTER_HTML = """
<html><body><div id="document">
<div class="qsnum_chap" data-path="/statutes/statutes/71/title"><span class="qstr">CHAPTER 71</span></div>
<div class="qstitle_chap"><span class="qstr">INCOME AND FRANCHISE TAXES FOR STATE AND LOCAL REVENUES</span></div>
<div class="qsnum_subchap level2" data-path="/statutes/statutes/71/i" data-cites='["statutes/subch. I of ch. 71"]'><a class="reference" href="/document/statutes/subch. I of ch. 71">subch. I of ch. 71</a><span class="qstr">SUBCHAPTER I</span></div>
<div class="qstitle_subchap"><span class="qstr">TAXATION OF INDIVIDUALS AND FIDUCIARIES</span></div>
<div class="qsatxt_1sect level3" data-path="/statutes/statutes/71/i/01" data-section="71.01" data-cites='["statutes/71.01","statutes/71.01(intro.)"]'><a class="reference" href="/document/statutes/71.01">71.01</a><span class="qsnum_sect"><span class="qstr">71.01</span></span><span class="qstitle_sect"><span class="qstr">Definitions.</span></span><span class="qstr"> In this chapter in regard to natural persons:</span></div>
<div class="qsatxt_2subsect level4" data-path="/statutes/statutes/71/i/01/1" data-section="71.01" data-cites='["statutes/71.01(1)"]'><a class="reference" href="/document/statutes/71.01(1)">71.01(1)</a><span class="qsnum_subsect"><span class="qstr">(1)</span></span><span class="qstr"> &ldquo;Adjusted gross income&rdquo; has the meaning given in s. <a rel="statutes/71.02" href="/document/statutes/71.02">71.02</a>.</span></div>
<div class="qsnote_history" data-path="/statutes/statutes/71/i/01/_1" data-section="71.01" data-cites="[]"><span class="reference">71.01 History</span><span class="qstr">History: 1973 c. 147.</span></div>
</div></body></html>
"""

TOC_HTML_PUBLISHED = """
<html><body>
<div class="qsnote_note"><span class="qstr">2023-24 Wisconsin Statutes updated through 2025 Wis. Act 247 and through all Supreme Court Orders and Controlled Substances Board Orders filed before and in effect on September 4, 2026. Published and certified under s. 35.18. Changes effective after September 4, 2026, are designated by NOTES. (Published 9-4-26)</span></div>
</body></html>
"""

# Markup mirrors the official chapter 71 page (docs.legis.wisconsin.gov, published
# 9-4-26): every unit below the section is its own div whose data-path extends the
# section's data-path and whose data-cites carries the official self-citation.
SUBUNIT_CHAPTER_HTML = """
<html><body><div id="document">
<div class="qsnum_subchap level2" data-path="/statutes/statutes/71/i" data-cites='["statutes/subch. I of ch. 71"]'><span class="qstr">SUBCHAPTER I</span></div>
<div class="qstitle_subchap"><span class="qstr">TAXATION OF INDIVIDUALS AND FIDUCIARIES</span></div>
<div class="qsatxt_1sect level3" data-path="/statutes/statutes/71/i/01" data-section="71.01" data-cites='["statutes/71.01"]'><a class="reference" href="/document/statutes/71.01">71.01</a><span class="qsnum_sect"><span class="qstr">71.01</span></span><span class="qstitle_sect"><span class="qstr">Definitions.</span></span></div>
<div class="qsatxt_2subsect level4" data-path="/statutes/statutes/71/i/01/6" data-section="71.01" data-cites='["statutes/71.01(6)","statutes/71.01(6)(intro.)"]'><a class="reference" href="/document/statutes/71.01(6)">71.01(6)</a><span class="qsnum_subsect"><span><span class="qstr">(6)</span></span></span><span class="qstr"> &ldquo;Internal Revenue Code&rdquo; means:</span></div>
<div class="qsatxt_3para level5" data-path="/statutes/statutes/71/i/01/6/l" data-section="71.01" data-cites='["statutes/71.01(6)(L)"]'><a class="reference" href="/document/statutes/71.01(6)(L)">71.01(6)(L)</a><span class="qsnum_para"><span><span class="qstr">(L)</span></span></span><span class="qstr">  For taxable year 2010, the code in effect on December 31, 2009.</span></div>
<div class="qsatxt_1sect level3" data-path="/statutes/statutes/71/i/05" data-section="71.05" data-cites='["statutes/71.05"]'><a class="reference" href="/document/statutes/71.05">71.05</a><span class="qsnum_sect"><span class="qstr">71.05</span></span><span class="qstr"> </span><span class="qstitle_sect"><span class="qstr">Income computation.</span></span><span class="qstr">  </span></div>
<div class="qsatxt_2subsect level4" data-path="/statutes/statutes/71/i/05/6" data-section="71.05" data-cites='["statutes/71.05(6)","statutes/71.05(6)(intro.)"]'><a class="reference" href="/document/statutes/71.05(6)">71.05(6)</a><span class="qsnum_subsect"><span><span class="qstr">(6)</span></span></span><span class="qstr"> </span><span class="qstitle_subsect"><span class="qstr">Modifications and transitional adjustments.</span></span><span class="qstr">  Some of the modifications referred to in s. <a rel="statutes/71.01(13)" href="/document/statutes/71.01(13)">71.01 (13)</a> are:</span></div>
<div class="qsatxt_3para level5" data-path="/statutes/statutes/71/i/05/6/b" data-section="71.05" data-cites='["statutes/71.05(6)(b)","statutes/71.05(6)(b)(intro.)"]'><a class="reference" href="/document/statutes/71.05(6)(b)">71.05(6)(b)</a><span class="qsnum_para"><span><span class="qstr">(b)</span></span></span><span class="qstr">  </span><span class="qstitle_para"><span class="qstr">Subtractions.</span></span><span class="qstr">  From federal adjusted gross income subtract:</span></div>
<div class="qsatxt_4subdiv level6" data-path="/statutes/statutes/71/i/05/6/b/9" data-section="71.05" data-cites='["statutes/71.05(6)(b)9."]'><a class="reference" href="/document/statutes/71.05(6)(b)9.">71.05(6)(b)9.</a><span class="qsnum_subdiv"><span><span class="qstr">9.</span></span></span><span class="qstr">  On assets held more than one year, 30 percent of the capital gain.</span></div>
<div class="qsatxt_4subdiv level6" data-path="/statutes/statutes/71/i/05/6/b/54m" data-section="71.05" data-cites='["statutes/71.05(6)(b)54m."]'><a class="reference" href="/document/statutes/71.05(6)(b)54m.">71.05(6)(b)54m.</a><span class="qsnum_subdiv"><span><span class="qstr">54m.</span></span></span><span class="qstr">  </span></div>
<div class="qsatxt_5subdivpara level7" data-path="/statutes/statutes/71/i/05/6/b/54m/a" data-section="71.05" data-cites='["statutes/71.05(6)(b)54m.a."]'><a class="reference" href="/document/statutes/71.05(6)(b)54m.a.">71.05(6)(b)54m.a.</a><span class="qsnum_subdivpara"><span><span class="qstr">a.</span></span></span><span class="qstr">  Payments from a qualified retirement plan, subject to subd. <a rel="statutes/71.05(6)(b)54m.b." href="/document/statutes/71.05(6)(b)54m.b.">54m. b.</a></span></div>
<div class="qsatxt_5subdivpara level7" data-path="/statutes/statutes/71/i/05/6/b/54m/b" data-section="71.05" data-cites='["statutes/71.05(6)(b)54m.b."]'><a class="reference" href="/document/statutes/71.05(6)(b)54m.b.">71.05(6)(b)54m.b.</a><span class="qsnum_subdivpara"><span><span class="qstr">b.</span></span></span><span class="qstr">  No credit listed under s. <a rel="statutes/71.07" href="/document/statutes/71.07">71.07</a> may be claimed.</span></div>
<div class="qsnote_subdiv" data-path="/statutes/statutes/71/i/05/6/b/54m/_1" data-section="71.05" data-cites="[]"><span class="qstr">NOTE: An editorial note that is not statutory text.</span></div>
<div class="qsatxt_4subdiv level6" data-path="/statutes/statutes/71/i/05/6/b/55" data-section="71.05" data-cites='["statutes/71.05(6)(b)55."]'><a class="reference" href="/document/statutes/71.05(6)(b)55.">71.05(6)(b)55.</a><span class="qsnum_subdiv"><span><span class="qstr">55.</span></span></span><span class="qstr">  Amounts received as a medal.</span></div>
<div class="qsnote_history" data-path="/statutes/statutes/71/i/05/_1" data-section="71.05" data-cites="[]"><span class="reference">71.05 History</span><span class="qstr">History: 2025 a. 15.</span></div>
</div></body></html>
"""


def _chapter_71() -> WisconsinChapterLink:
    return parse_wisconsin_chapter_links(TOC_HTML)[0]


def _chapter_71_source() -> WisconsinSource:
    return WisconsinSource(
        source_url=_chapter_71().source_url,
        source_path="sources/us-wi/statute/test/wisconsin-statutes-html/statutes/statutes/71.html",
        source_format=WISCONSIN_STATUTES_SOURCE_FORMAT,
        sha256="abc",
        source_document_id="chapter-71",
    )


def _write_chapter_sources(source_dir, chapter_html: str) -> None:
    files = {
        f"{WISCONSIN_STATUTES_SOURCE_FORMAT}/statutes/prefaces/toc.html": TOC_HTML,
        f"{WISCONSIN_STATUTES_SOURCE_FORMAT}/statutes/statutes/71.html": chapter_html,
    }
    for relative_path, text in files.items():
        path = source_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_parse_wisconsin_chapter_links_from_official_toc():
    chapters = parse_wisconsin_chapter_links(TOC_HTML)

    assert [(chapter.label, chapter.heading) for chapter in chapters] == [
        ("71", "Income and franchise taxes for state and local revenues."),
        ("72", "Estate tax."),
    ]
    assert chapters[0].source_url == "https://docs.legis.wisconsin.gov/statutes/statutes/71?view=section"
    assert chapters[0].relative_path == (
        f"{WISCONSIN_STATUTES_SOURCE_FORMAT}/statutes/statutes/71.html"
    )


def test_parse_wisconsin_publication_note():
    note = extract_wisconsin_publication_note(TOC_HTML)

    assert note is not None
    assert "2025 Wisconsin Act 103" in note
    assert "April 3, 2026" in note


def test_parse_wisconsin_publication_note_for_any_publication_date():
    note = extract_wisconsin_publication_note(TOC_HTML_PUBLISHED)

    assert note is not None
    assert note.startswith("2023-24 Wisconsin Statutes updated through 2025 Wis. Act 247")
    assert note.endswith("(Published 9-4-26)")


def test_parse_wisconsin_chapter_page_extracts_sections_and_metadata():
    chapter = parse_wisconsin_chapter_links(TOC_HTML)[0]
    source = WisconsinSource(
        source_url=chapter.source_url,
        source_path="sources/us-wi/statute/test/wisconsin-statutes-html/statutes/statutes/71.html",
        source_format=WISCONSIN_STATUTES_SOURCE_FORMAT,
        sha256="abc",
        source_document_id="chapter-71",
    )

    subchapters, sections = parse_wisconsin_chapter_page(
        CHAPTER_HTML,
        chapter=chapter,
        source=source,
    )

    assert [(subchapter.label, subchapter.heading) for subchapter in subchapters] == [
        ("I", "TAXATION OF INDIVIDUALS AND FIDUCIARIES")
    ]
    assert len(sections) == 1
    section = sections[0]
    assert section.label == "71.01"
    assert section.heading == "Definitions."
    assert section.parent_citation_path == "us-wi/statute/chapter-71/subchapter-i"
    assert section.lines == [
        "In this chapter in regard to natural persons:",
        "(1) \u201cAdjusted gross income\u201d has the meaning given in s. 71.02.",
    ]
    assert section.history == ["History: 1973 c. 147."]
    assert section.references_to == ["us-wi/statute/71.02"]


def test_extract_wisconsin_statutes_from_source_dir(tmp_path):
    source_dir = tmp_path / "source"
    _write_chapter_sources(source_dir, CHAPTER_HTML)

    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_wisconsin_statutes(
        store,
        version="2026-05-10",
        source_dir=source_dir,
        source_as_of="2026-04-03",
        expression_date="2026-04-03",
        only_title="71",
        include_subunits=True,
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 1
    assert report.section_count == 1
    assert report.provisions_written == 4
    assert len(load_source_inventory(report.inventory_path)) == 4
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-wi/statute/chapter-71",
        "us-wi/statute/chapter-71/subchapter-i",
        "us-wi/statute/71.01",
        "us-wi/statute/71.01/1",
    ]
    section = records[2]
    assert section.body == (
        "In this chapter in regard to natural persons:\n"
        "(1) \u201cAdjusted gross income\u201d has the meaning given in s. 71.02."
    )
    assert section.metadata is not None
    assert section.metadata["history"] == ["History: 1973 c. 147."]
    assert section.metadata["references_to"] == ["us-wi/statute/71.02"]
    subsection = records[3]
    assert subsection.kind == "subsection"
    assert subsection.body == "\u201cAdjusted gross income\u201d has the meaning given in s. 71.02."
    assert subsection.parent_citation_path == "us-wi/statute/71.01"
    assert subsection.parent_id == section.id


def test_extract_wisconsin_statutes_source_dir_never_falls_back_to_network(tmp_path, monkeypatch):
    # A source_dir that points one level too deep (at the format directory rather
    # than the scope directory) matches no retained file. It must fail loudly
    # instead of silently snapshotting the live pages under the old version.
    source_dir = tmp_path / "source"
    _write_chapter_sources(source_dir, CHAPTER_HTML)

    def no_network(source_url, *, fetcher):
        raise AssertionError(f"unexpected download: {source_url}")

    monkeypatch.setattr(wisconsin, "_download_wisconsin_source", no_network)

    with pytest.raises(FileNotFoundError, match="Wisconsin source file does not exist"):
        extract_wisconsin_statutes(
            CorpusArtifactStore(tmp_path / "corpus"),
            version="2026-05-10",
            source_dir=source_dir / WISCONSIN_STATUTES_SOURCE_FORMAT,
            only_title="71",
        )


def test_parse_wisconsin_chapter_page_builds_subunits_from_official_data_paths():
    _subchapters, sections = parse_wisconsin_chapter_page(
        SUBUNIT_CHAPTER_HTML,
        chapter=_chapter_71(),
        source=_chapter_71_source(),
        include_subunits=True,
    )

    income = next(section for section in sections if section.label == "71.05")
    assert income.data_path == "/statutes/statutes/71/i/05"
    assert [unit.citation_path for unit in income.subunits] == [
        "us-wi/statute/71.05/6",
        "us-wi/statute/71.05/6/b",
        "us-wi/statute/71.05/6/b/9",
        "us-wi/statute/71.05/6/b/54m",
        "us-wi/statute/71.05/6/b/54m/a",
        "us-wi/statute/71.05/6/b/54m/b",
        "us-wi/statute/71.05/6/b/55",
    ]
    by_path = {unit.citation_path: unit for unit in income.subunits}
    subtractions = by_path["us-wi/statute/71.05/6/b"]
    assert subtractions.kind == "paragraph"
    assert subtractions.heading == "Subtractions."
    assert subtractions.official_citation == "71.05(6)(b)"
    assert subtractions.parent_citation_path == "us-wi/statute/71.05/6"
    assert subtractions.level == 4
    retirement = by_path["us-wi/statute/71.05/6/b/54m"]
    assert retirement.kind == "subdivision"
    assert retirement.heading is None
    assert retirement.official_citation == "71.05(6)(b)54m."
    assert retirement.legal_identifier == "Wis. Stat. 71.05(6)(b)54m."
    assert retirement.parent_citation_path == "us-wi/statute/71.05/6/b"
    assert retirement.ordinal == 2
    # The unit's own number is dropped (it has no text of its own); descendants
    # keep theirs, and editorial notes stay out as they do for sections.
    assert retirement.lines == [
        "a. Payments from a qualified retirement plan, subject to subd. 54m. b.",
        "b. No credit listed under s. 71.07 may be claimed.",
    ]
    assert retirement.references_to == ["us-wi/statute/71.07"]
    assert by_path["us-wi/statute/71.05/6/b/54m/a"].kind == "subdivision_paragraph"
    assert by_path["us-wi/statute/71.05/6/b/54m/a"].parent_citation_path == (
        "us-wi/statute/71.05/6/b/54m"
    )
    assert by_path["us-wi/statute/71.05/6/b/9"].lines == [
        "On assets held more than one year, 30 percent of the capital gain."
    ]
    assert subtractions.lines == [
        "From federal adjusted gross income subtract:",
        "9. On assets held more than one year, 30 percent of the capital gain.",
        "54m.",
        "a. Payments from a qualified retirement plan, subject to subd. 54m. b.",
        "b. No credit listed under s. 71.07 may be claimed.",
        "55. Amounts received as a medal.",
    ]
    section_body = "\n".join(income.lines)
    for unit in income.subunits:
        assert "\n".join(unit.lines) in section_body

    definitions = next(section for section in sections if section.label == "71.01")
    paragraph_l = definitions.subunits[-1]
    assert paragraph_l.citation_path == "us-wi/statute/71.01/6/l"
    assert paragraph_l.official_citation == "71.01(6)(L)"



def test_parse_wisconsin_chapter_page_can_skip_subunits():
    kwargs = {"chapter": _chapter_71(), "source": _chapter_71_source()}
    _subchapters, full = parse_wisconsin_chapter_page(
        SUBUNIT_CHAPTER_HTML, include_subunits=True, **kwargs
    )
    _subchapters, bare = parse_wisconsin_chapter_page(
        SUBUNIT_CHAPTER_HTML, include_subunits=False, **kwargs
    )

    assert all(section.subunits for section in full)
    assert all(not section.subunits for section in bare)
    assert [(section.label, section.lines, section.references_to) for section in bare] == [
        (section.label, section.lines, section.references_to) for section in full
    ]


def test_extract_wisconsin_statutes_emits_subunit_records(tmp_path):
    source_dir = tmp_path / "source"
    _write_chapter_sources(source_dir, SUBUNIT_CHAPTER_HTML)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_wisconsin_statutes(
        store,
        version="2026-09-23",
        source_dir=source_dir,
        source_as_of="2026-09-04",
        expression_date="2026-09-04",
        only_title="71",
        include_subunits=True,
    )

    assert report.coverage.complete is True
    assert report.section_count == 2
    records = load_provisions(report.provisions_path)
    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == [
        record.citation_path for record in records
    ]
    by_path = {record.citation_path: record for record in records}
    assert all(
        record.parent_citation_path in by_path
        for record in records
        if record.parent_citation_path
    )
    retirement = by_path["us-wi/statute/71.05/6/b/54m"]
    assert retirement.version == "2026-09-23-chapter-71"
    assert retirement.kind == "subdivision"
    assert retirement.citation_label == "Wis. Stat. 71.05(6)(b)54m."
    assert retirement.source_id == "71.05(6)(b)54m."
    assert retirement.parent_id == by_path["us-wi/statute/71.05/6/b"].id
    assert retirement.level == 5
    assert retirement.body == (
        "a. Payments from a qualified retirement plan, subject to subd. 54m. b.\n"
        "b. No credit listed under s. 71.07 may be claimed."
    )
    assert retirement.identifiers == {
        "wisconsin:chapter": "71",
        "wisconsin:section": "71.05",
        "wisconsin:citation": "71.05(6)(b)54m.",
    }
    assert retirement.metadata is not None
    assert retirement.metadata["data_path"] == "/statutes/statutes/71/i/05/6/b/54m"
    assert retirement.metadata["section_heading"] == "Income computation."
    assert retirement.metadata["subchapter"] == "I"
    assert by_path["us-wi/statute/71.05/6/b/9"].body == (
        "On assets held more than one year, 30 percent of the capital gain."
    )
    # The section record is unchanged by child emission.
    assert by_path["us-wi/statute/71.05"].body is not None
    assert by_path["us-wi/statute/71.05"].body.startswith(
        "(6) Modifications and transitional adjustments."
    )


def test_extract_wisconsin_statutes_can_stay_at_section_grain(tmp_path):
    source_dir = tmp_path / "source"
    _write_chapter_sources(source_dir, SUBUNIT_CHAPTER_HTML)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_wisconsin_statutes(
        store,
        version="2026-09-23",
        source_dir=source_dir,
        only_title="71",
        include_subunits=False,
    )

    assert report.coverage.complete is True
    assert [record.citation_path for record in load_provisions(report.provisions_path)] == [
        "us-wi/statute/chapter-71",
        "us-wi/statute/chapter-71/subchapter-i",
        "us-wi/statute/71.01",
        "us-wi/statute/71.05",
    ]


def test_extract_wisconsin_statutes_can_omit_publication_note(tmp_path):
    source_dir = tmp_path / "source"
    _write_chapter_sources(source_dir, CHAPTER_HTML)

    with_note = extract_wisconsin_statutes(
        CorpusArtifactStore(tmp_path / "with-note"),
        version="2026-05-10",
        source_dir=source_dir,
        only_title="71",
    )
    without_note = extract_wisconsin_statutes(
        CorpusArtifactStore(tmp_path / "without-note"),
        version="2026-05-10",
        source_dir=source_dir,
        only_title="71",
        include_publication_note=False,
    )

    noted = load_provisions(with_note.provisions_path)
    bare = load_provisions(without_note.provisions_path)
    assert all(
        record.metadata is not None
        and record.metadata["publication_note"].endswith("April 3, 2026")
        for record in noted
    )
    assert all(
        record.metadata is not None and "publication_note" not in record.metadata
        for record in bare
    )
    assert [record.body for record in bare] == [record.body for record in noted]


def test_pit_west_recovery_manifest_replays_the_signed_wisconsin_scope(
    tmp_path, capsys, monkeypatch
):
    # The released section-grain scope must be reproducible from its retained,
    # git-tracked bytes: the recovery manifest's source_dir, include_subunits and
    # include_publication_note must together give back every signed artifact
    # byte for byte, without touching the network.
    def no_network(source_url, *, fetcher):
        raise AssertionError(f"unexpected download: {source_url}")

    monkeypatch.setattr(wisconsin, "_download_wisconsin_source", no_network)
    base = tmp_path / "corpus"

    exit_code = main(
        [
            "extract-state-statutes",
            "--base",
            str(base),
            "--manifest",
            str(RECOVERY_MANIFEST_PATH),
            "--only-source-id",
            "us-wi-statutes",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0, payload
    assert payload["completed_count"] == 1
    assert payload["provisions_written"] == 116
    signed = json.loads(RECOVERY_INGEST_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert signed["version"] == RECOVERY_VERSION
    applied = {
        entry["path"].removeprefix("data/corpus/"): entry["sha256"]
        for entry in signed["applied_files"]
    }
    written = {
        path.relative_to(base).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }
    assert written == applied


def test_chapter_71_subunit_scope_replays_and_resolves_policybench_targets(
    tmp_path, capsys, monkeypatch
):
    # The committed us-wi/statute/2026-09-23-income-tax-subunits-chapter-71 scope
    # must be exactly what this adapter produces from the scope's own retained,
    # git-tracked official bytes, and it must resolve the subdivision paths the
    # PolicyBench oracle encodings cite (Wis. Stat. 71.05(6)(b)9. and 54m.).
    def no_network(source_url, *, fetcher):
        raise AssertionError(f"unexpected download: {source_url}")

    monkeypatch.setattr(wisconsin, "_download_wisconsin_source", no_network)
    committed = ROOT / "data/corpus"
    retained = committed / "sources/us-wi/statute" / SUBUNITS_VERSION
    manifest = yaml.safe_load(SUBUNITS_MANIFEST_PATH.read_text(encoding="utf-8"))
    (source,) = manifest["sources"]
    source["options"].pop("download_dir")
    source["options"]["source_dir"] = str(retained)
    manifest_path = tmp_path / "replay.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    base = tmp_path / "corpus"

    exit_code = main(
        ["extract-state-statutes", "--base", str(base), "--manifest", str(manifest_path)]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0, payload
    assert payload["completed_count"] == 1
    assert payload["provisions_written"] == 5034
    written = {
        path.relative_to(base).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }
    assert sorted(written) == [
        f"coverage/us-wi/statute/{SUBUNITS_VERSION}.json",
        f"inventory/us-wi/statute/{SUBUNITS_VERSION}.json",
        f"provisions/us-wi/statute/{SUBUNITS_VERSION}.jsonl",
        f"sources/us-wi/statute/{SUBUNITS_VERSION}/wisconsin-statutes-html/statutes/prefaces/toc.html",
        f"sources/us-wi/statute/{SUBUNITS_VERSION}/wisconsin-statutes-html/statutes/statutes/71.html",
    ]
    for relative, digest in written.items():
        assert hashlib.sha256((committed / relative).read_bytes()).hexdigest() == digest, relative

    by_path = {
        record.citation_path: record
        for record in load_provisions(
            committed / "provisions/us-wi/statute" / f"{SUBUNITS_VERSION}.jsonl"
        )
    }
    section = by_path["us-wi/statute/71.05"]
    expected = {
        "us-wi/statute/71.05/6": (
            "subsection",
            "Wis. Stat. 71.05(6)",
            "us-wi/statute/71.05",
            "Some of the modifications referred to in s. 71.01 (13) and (14) are:\n",
        ),
        "us-wi/statute/71.05/6/b": (
            "paragraph",
            "Wis. Stat. 71.05(6)(b)",
            "us-wi/statute/71.05/6",
            "From federal adjusted gross income subtract ",
        ),
        "us-wi/statute/71.05/6/b/9": (
            "subdivision",
            "Wis. Stat. 71.05(6)(b)9.",
            "us-wi/statute/71.05/6/b",
            "On assets held more than one year and on all assets acquired from a "
            "decedent, 30 percent of the capital gain ",
        ),
        "us-wi/statute/71.05/6/b/54m": (
            "subdivision",
            "Wis. Stat. 71.05(6)(b)54m.",
            "us-wi/statute/71.05/6/b",
            "a. Except for a payment that is exempt under sub. (1) (a), (am), or (an)",
        ),
    }
    for citation_path, (kind, label, parent, body_start) in expected.items():
        record = by_path[citation_path]
        assert record.kind == kind
        assert record.citation_label == label
        assert record.parent_citation_path == parent
        assert record.body is not None and record.body.startswith(body_start), citation_path
        assert record.body in (section.body or ""), citation_path

    modifications = by_path["us-wi/statute/71.05/6"].body or ""
    assert "\n(b) Subtractions. From federal adjusted gross income subtract " in modifications
    subtractions = by_path["us-wi/statute/71.05/6/b"].body or ""
    assert subtractions.endswith("veterinary loan repayment grant program under s. 39.389.")
    # Paragraph (b) is the last unit of subsection (6), so (6) closes with its text.
    assert modifications.endswith(subtractions)
    capital_gain = by_path["us-wi/statute/71.05/6/b/9"].body or ""
    assert "\n" not in capital_gain
    assert capital_gain.endswith("netted before application of the percentage.")
    retirement = by_path["us-wi/statute/71.05/6/b/54m"].body or ""
    assert [line[:2] for line in retirement.split("\n")] == ["a.", "b.", "c.", "d.", "e."]
    assert "not to exceed $24,000" in retirement
    assert "may not exceed $48,000" in retirement
    assert retirement.endswith(
        "A nonresident of this state is not eligible to claim the subtraction under "
        "this subdivision."
    )
