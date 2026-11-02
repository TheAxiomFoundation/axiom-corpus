"""A failed table of contents stays a visible coverage gap (axiom-corpus#890).

Each case gives one container a listing the run cannot use: the page cannot be
fetched, is a maintenance or empty page, has the wrong shape, or lists no
children. Its children are never seen, so the container itself must be the
gap: an error, an inventory item with no provision, and incomplete coverage
under strict release validation. A container that could not be fetched is
sourced from the parent listing that names it; one that was fetched but is
unusable is sourced from its own page.
"""

import json

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.state_adapters.maryland import extract_maryland_code
from axiom_corpus.corpus.state_adapters.massachusetts import (
    extract_massachusetts_general_laws,
)
from axiom_corpus.corpus.state_adapters.michigan import extract_michigan_compiled_laws
from axiom_corpus.corpus.state_adapters.missouri import extract_missouri_revised_statutes
from axiom_corpus.corpus.state_adapters.nevada import extract_nevada_nrs
from axiom_corpus.corpus.state_adapters.new_hampshire import extract_new_hampshire_rsa
from tests.test_corpus_maryland import SAMPLE_SECTION_HTML as MD_SECTION_HTML
from tests.test_corpus_massachusetts import (
    SAMPLE_CHAPTER_HTML as MA_CHAPTER_HTML,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_CHAPTERS_FRAGMENT as MA_CHAPTERS_FRAGMENT,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_INDEX_HTML as MA_INDEX_HTML,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_PART_HTML as MA_PART_HTML,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_SECTION_HTML as MA_SECTION_TWO_HTML,
)
from tests.test_corpus_massachusetts import (
    SAMPLE_SECTION_ONE_HTML as MA_SECTION_ONE_HTML,
)
from tests.test_corpus_michigan import SAMPLE_CHAPTER_XML as MI_CHAPTER_XML
from tests.test_corpus_michigan import SAMPLE_INDEX_HTML as MI_INDEX_HTML
from tests.test_corpus_missouri import SAMPLE_CHAPTER_HTML as MO_CHAPTER_HTML
from tests.test_corpus_missouri import SAMPLE_ROOT_HTML as MO_ROOT_HTML
from tests.test_corpus_missouri import SAMPLE_VIEW_CHAPTER_HTML as MO_VIEW_HTML
from tests.test_corpus_nevada import SAMPLE_NEVADA_CHAPTER as NV_CHAPTER_HTML
from tests.test_corpus_nevada import SAMPLE_NEVADA_INDEX as NV_INDEX_HTML
from tests.test_corpus_new_hampshire import (
    SAMPLE_CHAPTER_TOC_HTML as NH_CHAPTER_TOC_HTML,
)
from tests.test_corpus_new_hampshire import (
    SAMPLE_MERGED_CHAPTER_HTML as NH_MERGED_HTML,
)
from tests.test_corpus_new_hampshire import (
    SAMPLE_REPEALED_CHAPTER_HTML as NH_REPEALED_MERGED_HTML,
)
from tests.test_corpus_new_hampshire import (
    SAMPLE_REPEALED_CHAPTER_TOC_HTML as NH_REPEALED_TOC_HTML,
)
from tests.test_corpus_new_hampshire import SAMPLE_ROOT_HTML as NH_ROOT_HTML
from tests.test_corpus_new_hampshire import SAMPLE_TITLE_HTML as NH_TITLE_HTML
from tests.test_state_extraction_gaps import MAINTENANCE, _assert_visible_gaps, _write_sources

EMPTY_PAGE = ""
WRONG_SHAPE_HTML = "<html><body><main><h1>Search results</h1><p>No entries.</p></main></body></html>"
# "missing-file" stands in for a page that could not be fetched at all.
TOC_FAILURES = ["missing-file", "maintenance", "empty", "wrong-shape", "no-children"]


def _fail_page(pages: dict[str, str], relative: str, failure: str, bodies: dict[str, str]) -> None:
    if failure == "missing-file":
        pages.pop(relative, None)
        return
    pages[relative] = {
        "maintenance": MAINTENANCE,
        "empty": EMPTY_PAGE,
        "wrong-shape": WRONG_SHAPE_HTML,
        **bodies,
    }[failure]


# --- Maryland: articles.json -> sections/<article>.json -> section pages ---

MD_ARTICLES = [
    {"DisplayText": "Agriculture - (gag)", "Value": "gag"},
    {"DisplayText": "Business Regulation - (gbr)", "Value": "gbr"},
]
MD_SECTIONS = [{"DisplayText": "1-101", "Value": "100"}, {"DisplayText": "1-102", "Value": "200"}]
MD_GOOD_PAGES = {
    "maryland-code-json/articles.json": json.dumps(MD_ARTICLES),
    "maryland-code-json/sections/gag.json": json.dumps(MD_SECTIONS),
    "maryland-code-html/gag/1-101.html": MD_SECTION_HTML,
    "maryland-code-html/gag/1-102.html": MD_SECTION_HTML.replace("1&ndash;101", "1&ndash;102"),
}
MD_EXTRACTED = {
    "us-md/statute/gag",
    "us-md/statute/gag/title-1",
    "us-md/statute/gag/1-101",
    "us-md/statute/gag/1-102",
}


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_maryland_failed_article_section_list_remains_inventory_gap(tmp_path, failure):
    failed = "maryland-code-json/sections/gbr.json"
    pages = dict(MD_GOOD_PAGES)
    pages[failed] = json.dumps(MD_SECTIONS)
    _fail_page(
        pages,
        failed,
        failure,
        {"wrong-shape": json.dumps({"Message": "An error has occurred."}), "no-children": "[]"},
    )
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_maryland_code(store, version="2026-05-09", source_dir=tmp_path / "source")
    assert report.section_count == 2
    assert "gbr" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MD_EXTRACTED | {"us-md/statute/gbr"},
        missing={"us-md/statute/gbr"},
        gap_source=(
            "maryland-code-json/articles.json" if failure == "missing-file" else "sections/gbr.json"
        ),
    )


# --- Massachusetts: index -> part page -> title chapter fragment -> chapter page ---

MA_PART_II_LINK = """
  <li><a href="/Laws/GeneralLaws/PartII">
    <span class="part">Part II</span>
    <span class="partTitle">REAL AND PERSONAL PROPERTY AND DOMESTIC RELATIONS</span>
    <span class="chapters">Chapters 183-210</span>
  </a></li>
</ul>"""
MA_TITLE_X_PANEL = """
  <div id="Xtitle" class="panel panel-default">
    <div class="panel-heading">
      <h4 class="glTitle panel-title">
        <a href="#titleX" onclick="accordionAjaxLoad('1', '10', 'X')">Title X</a>
      </h4>
      <h4 class="panel-title">
        <a href="#titleX" onclick="accordionAjaxLoad('1', '10', 'X')">PUBLIC RECORDS</a>
      </h4>
    </div>
  </div>
</div>
</body>"""
MA_CHAPTER_63_LINK = """
    <li><a href="/Laws/GeneralLaws/PartI/TitleIX/Chapter63">
      <span class="chapter">Chapter 63</span>
      <span class="chapterTitle">TAXATION OF CORPORATIONS</span>
    </a></li>
  </ul>"""
MA_INDEX = "pages/Laws/GeneralLaws/index.html"
MA_PART_I = "pages/Laws/GeneralLaws/PartI.html"
MA_TITLE_IX = "ajax/GetChaptersForTitle/part-1-title-9-IX.html"
MA_CHAPTER_62 = "pages/Laws/GeneralLaws/PartI/TitleIX/Chapter62.html"
MA_GOOD_PAGES = {
    MA_INDEX: MA_INDEX_HTML,
    MA_PART_I: MA_PART_HTML,
    MA_TITLE_IX: MA_CHAPTERS_FRAGMENT,
    MA_CHAPTER_62: MA_CHAPTER_HTML,
    "pages/Laws/GeneralLaws/PartI/TitleIX/Chapter62/Section1.html": MA_SECTION_ONE_HTML,
    "pages/Laws/GeneralLaws/PartI/TitleIX/Chapter62/Section2.html": MA_SECTION_TWO_HTML,
}
MA_EXTRACTED = {
    "us-ma/statute/part-i",
    "us-ma/statute/part-i/title-ix",
    "us-ma/statute/part-i/title-ix/chapter-62",
    "us-ma/statute/62/1",
    "us-ma/statute/62/2",
}
# A page of the right kind that lists nothing, at each level.
MA_EMPTY_PART = MA_PART_HTML.split('<div id="Ititle"')[0] + "</div></body></html>"
MA_EMPTY_FRAGMENT = '<div class="panel-collapse"><ul class="generalLawsList"></ul></div>'
MA_EMPTY_CHAPTER = MA_CHAPTER_HTML.split("<li>")[0] + "</ul></body></html>"


def _extract_massachusetts(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_massachusetts_general_laws(
        store, version="2026-05-09", source_dir=tmp_path / "source", workers=1
    )
    return store, report


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_massachusetts_failed_part_page_remains_inventory_gap(tmp_path, failure):
    failed = "pages/Laws/GeneralLaws/PartII.html"
    pages = dict(MA_GOOD_PAGES)
    pages[MA_INDEX] = MA_INDEX_HTML.replace("</ul>", MA_PART_II_LINK, 1)
    pages[failed] = MA_PART_HTML
    _fail_page(pages, failed, failure, {"no-children": MA_EMPTY_PART})
    store, report = _extract_massachusetts(tmp_path, pages)
    assert report.section_count == 2
    assert "PartII" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MA_EXTRACTED | {"us-ma/statute/part-ii"},
        missing={"us-ma/statute/part-ii"},
        gap_source=MA_INDEX if failure == "missing-file" else failed,
    )


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_massachusetts_failed_title_chapter_list_remains_inventory_gap(tmp_path, failure):
    failed = "ajax/GetChaptersForTitle/part-1-title-10-X.html"
    pages = dict(MA_GOOD_PAGES)
    pages[MA_PART_I] = MA_PART_HTML.replace("</div>\n</body>", MA_TITLE_X_PANEL, 1)
    pages[failed] = MA_CHAPTERS_FRAGMENT
    _fail_page(pages, failed, failure, {"no-children": MA_EMPTY_FRAGMENT})
    store, report = _extract_massachusetts(tmp_path, pages)
    assert report.section_count == 2
    assert "title-10-X" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MA_EXTRACTED | {"us-ma/statute/part-i/title-x"},
        missing={"us-ma/statute/part-i/title-x"},
        gap_source=MA_PART_I if failure == "missing-file" else failed,
    )


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_massachusetts_failed_chapter_page_remains_inventory_gap(tmp_path, failure):
    # On main a chapter page that could not be fetched was logged as an error
    # with no inventory item, so coverage still read complete.
    failed = "pages/Laws/GeneralLaws/PartI/TitleIX/Chapter63.html"
    pages = dict(MA_GOOD_PAGES)
    pages[MA_TITLE_IX] = MA_CHAPTERS_FRAGMENT.replace("  </ul>", MA_CHAPTER_63_LINK, 1)
    pages[failed] = MA_CHAPTER_HTML
    _fail_page(pages, failed, failure, {"no-children": MA_EMPTY_CHAPTER})
    store, report = _extract_massachusetts(tmp_path, pages)
    assert report.section_count == 2
    assert "chapter 63" in report.errors[0]
    chapter = "us-ma/statute/part-i/title-ix/chapter-63"
    _assert_visible_gaps(
        store,
        report,
        expected=MA_EXTRACTED | {chapter},
        missing={chapter},
        gap_source=MA_TITLE_IX if failure == "missing-file" else failed,
    )


# --- Michigan: directory index -> one chapter XML per chapter ---

MI_INDEX = "michigan-mcl-index-html/index.html"
MI_FAILED = "michigan-mcl-chapter-xml/chapter-750.xml"
MI_GOOD_PAGES = {
    MI_INDEX: MI_INDEX_HTML,
    "michigan-mcl-chapter-xml/chapter-206.xml": MI_CHAPTER_XML,
    MI_FAILED: MI_CHAPTER_XML.replace("<Name>206</Name>", "<Name>750</Name>"),
}
MI_EXTRACTED = {"us-mi/statute/chapter-206", "us-mi/statute/206.1", "us-mi/statute/206.2"}


def _michigan_chapter_without_sections(*, repealed: bool) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<MCLChapterInfo>'
        f"<DocumentID>1</DocumentID><Repealed>{str(repealed).lower()}</Repealed>"
        "<Name>750</Name><Title>MICHIGAN PENAL CODE</Title>"
        "<MCLDocumentInfoCollection /></MCLChapterInfo>"
    )


def _extract_michigan(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_michigan_compiled_laws(
        store, version="2026-05-10", source_dir=tmp_path / "source", workers=1
    )
    return store, report


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_michigan_failed_chapter_xml_remains_inventory_gap(tmp_path, failure):
    # On main a chapter that could not be fetched or parsed was logged as an
    # error with no inventory item, and an empty file raised out of the run.
    pages = dict(MI_GOOD_PAGES)
    _fail_page(
        pages,
        MI_FAILED,
        failure,
        {
            "wrong-shape": '<?xml version="1.0"?><Error><Message>Not found</Message></Error>',
            "no-children": _michigan_chapter_without_sections(repealed=False),
        },
    )
    store, report = _extract_michigan(tmp_path, pages)
    assert report.section_count == 2
    assert "chapter 750" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MI_EXTRACTED | {"us-mi/statute/chapter-750"},
        missing={"us-mi/statute/chapter-750"},
        gap_source=MI_INDEX if failure == "missing-file" else MI_FAILED,
    )


def test_michigan_repealed_chapter_without_sections_stays_complete(tmp_path):
    # The chapter XML marks the whole chapter repealed, so it lists nothing by
    # law and is written as a complete, repealed container.
    pages = dict(MI_GOOD_PAGES)
    pages[MI_FAILED] = _michigan_chapter_without_sections(repealed=True)
    _store, report = _extract_michigan(tmp_path, pages)
    assert report.errors == ()
    assert report.coverage.complete is True
    records = {record.citation_path: record for record in load_provisions(report.provisions_path)}
    assert set(records) == MI_EXTRACTED | {"us-mi/statute/chapter-750"}
    assert records["us-mi/statute/chapter-750"].metadata["status"] == "repealed"


# --- Missouri: root (titles and chapters) -> chapter index -> full-chapter text ---

MO_ROOT = "missouri-rs-root-html/Home.aspx.html"
MO_CHAPTER_143 = "missouri-rs-chapter-html/chapter-143.html"
MO_CHAPTER_144 = "missouri-rs-chapter-html/chapter-144.html"
MO_VIEW_144 = "missouri-rs-view-chapter-html/chapter-144.html"
MO_ROOT_TWO_CHAPTERS = MO_ROOT_HTML.replace(
    "</div>\n</details>",
    '</div>\n  <div><a href="/main/OneChapter.aspx?chapter=144">144 Sales Tax</a></div>\n</details>',
)
MO_GOOD_PAGES = {
    MO_ROOT: MO_ROOT_TWO_CHAPTERS,
    MO_CHAPTER_143: MO_CHAPTER_HTML,
    "missouri-rs-view-chapter-html/chapter-143.html": MO_VIEW_HTML,
    MO_CHAPTER_144: MO_CHAPTER_HTML.replace("143", "144"),
    MO_VIEW_144: MO_VIEW_HTML.replace("143", "144"),
}
MO_EXTRACTED = {"us-mo/statute/title-x", "us-mo/statute/chapter-143", "us-mo/statute/143.011"}
MO_EMPTY_CHAPTER = "<html><body><p>Title X TAXATION AND REVENUE Chapter 144 Sales Tax</p><table></table></body></html>"


def _extract_missouri(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_missouri_revised_statutes(
        store,
        version="2026-05-10",
        source_dir=tmp_path / "source",
        expression_date="2026-05-10",
        workers=1,
    )
    return store, report


def test_missouri_title_listing_no_chapters_remains_inventory_gap(tmp_path):
    # Titles have no page of their own: the root lists each title's chapters.
    pages = dict(MO_GOOD_PAGES)
    pages[MO_ROOT] = MO_ROOT_HTML + (
        '<details><summary><span class="lr-font-emph">Chs. 156-175</span>'
        '<span class="lr-font-emph">XI EDUCATION AND LIBRARIES</span></summary></details>'
    )
    del pages[MO_CHAPTER_144], pages[MO_VIEW_144]
    store, report = _extract_missouri(tmp_path, pages)
    assert "title XI" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MO_EXTRACTED | {"us-mo/statute/title-xi"},
        missing={"us-mo/statute/title-xi"},
        gap_source=MO_ROOT,
    )


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_missouri_failed_chapter_index_remains_inventory_gap(tmp_path, failure):
    # On main a chapter index that could not be fetched was logged as an error
    # with no inventory item, so coverage still read complete.
    pages = dict(MO_GOOD_PAGES)
    _fail_page(pages, MO_CHAPTER_144, failure, {"no-children": MO_EMPTY_CHAPTER})
    store, report = _extract_missouri(tmp_path, pages)
    assert report.section_count == 1
    assert "chapter 144" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MO_EXTRACTED | {"us-mo/statute/chapter-144"},
        missing={"us-mo/statute/chapter-144"},
        gap_source=MO_ROOT if failure == "missing-file" else MO_CHAPTER_144,
    )


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_missouri_failed_full_chapter_text_remains_inventory_gap(tmp_path, failure):
    # The chapter index lists the sections; the full-chapter page carries them.
    pages = dict(MO_GOOD_PAGES)
    _fail_page(pages, MO_VIEW_144, failure, {"no-children": MO_VIEW_HTML})
    store, report = _extract_missouri(tmp_path, pages)
    assert report.section_count == 1
    assert "chapter 144 full text" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MO_EXTRACTED | {"us-mo/statute/chapter-144"},
        missing={"us-mo/statute/chapter-144"},
        gap_source=MO_CHAPTER_144 if failure == "missing-file" else MO_VIEW_144,
    )


# --- Nevada: index (titles and chapters) -> one chapter page per chapter ---

NV_EXTRACTED = {
    "us-nv/statute/title-32",
    "us-nv/statute/361",
    "us-nv/statute/361.010",
    "us-nv/statute/361.013",
    "us-nv/statute/361.013@effective-2026-07-01",
}
NV_EMPTY_CHAPTER = (
    "<html><body><p>[Rev. 4/15/2026 2:20:22 PM--2025]</p>"
    '<p class="Chapter">CHAPTER 361A - AGRICULTURAL REAL PROPERTY</p></body></html>'
)


def _extract_nevada(tmp_path, pages: dict[str, str], **filters):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_nevada_nrs(
        store, version="2026-05-05", source_dir=tmp_path / "source", workers=1, **filters
    )
    return store, report


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_nevada_failed_chapter_page_remains_inventory_gap(tmp_path, failure):
    # On main a chapter page that could not be fetched was counted as skipped
    # with no inventory item, so coverage still read complete.
    pages = {"index.html": NV_INDEX_HTML, "NRS-361.html": NV_CHAPTER_HTML}
    pages["NRS-361A.html"] = NV_CHAPTER_HTML.replace("361", "361A")
    _fail_page(pages, "NRS-361A.html", failure, {"no-children": NV_EMPTY_CHAPTER})
    store, report = _extract_nevada(tmp_path, pages, only_title="32")
    assert report.section_count == 3
    assert "NRS-361A.html" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=NV_EXTRACTED | {"us-nv/statute/361A"},
        missing={"us-nv/statute/361A"},
        gap_source="index.html" if failure == "missing-file" else "NRS-361A.html",
    )


def test_nevada_title_listing_no_chapters_remains_inventory_gap(tmp_path):
    # Titles have no page of their own: the index lists each title's chapters.
    # On main a title listed with no chapters was left out of the inventory.
    index = NV_INDEX_HTML.split('<div class="card">\n  <h3 class="card-title h5">TITLE 1 ')[0]
    index += """<div class="card">
  <h3 class="card-title h5">TITLE 32-REVENUE AND TAXATION</h3>
  <ul><li class="list-group-item"><a href="NRS-361.html">Chapter 361</a> - Property Tax</li></ul>
</div>
<div class="card">
  <h3 class="card-title h5">TITLE 33 - LIBRARIES AND ARCHIVES</h3>
  <ul></ul>
</div>
</body></html>"""
    index = index.replace(
        '<h3 class="card-title h5"><a href="NRS-000.html">PRELIMINARY CHAPTER</a></h3>', ""
    )
    pages = {"index.html": index, "NRS-361.html": NV_CHAPTER_HTML}
    store, report = _extract_nevada(tmp_path, pages)
    assert "title 33" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=NV_EXTRACTED | {"us-nv/statute/title-33"},
        missing={"us-nv/statute/title-33"},
        gap_source="index.html",
    )


# --- New Hampshire: root -> title TOC -> chapter TOC + merged chapter page ---

NH_ROOT = "new-hampshire-rsa-root-html/nhtoc.htm"
NH_TITLE_V = "new-hampshire-rsa-title-toc-html/NHTOC-V.htm"
NH_TOC_77B = "new-hampshire-rsa-chapter-toc-html/NHTOC-V-77-B.htm"
NH_MERGED_77B = "new-hampshire-rsa-merged-chapter-html/V/77-B/77-B-mrg.htm"
NH_CHAPTER_77B_LINK = '<li><a href="NHTOC-V-77-B.htm">CHAPTER 77-B: COMMUTERS INCOME TAX</a></li>\n</ul>'
NH_GOOD_PAGES = {
    NH_ROOT: NH_ROOT_HTML,
    NH_TITLE_V: NH_TITLE_HTML,
    "new-hampshire-rsa-chapter-toc-html/NHTOC-V-77-A.htm": NH_CHAPTER_TOC_HTML,
    "new-hampshire-rsa-merged-chapter-html/V/77-A/77-A-mrg.htm": NH_MERGED_HTML,
}
NH_EXTRACTED = {
    "us-nh/statute/title-v",
    "us-nh/statute/chapter-77-a",
    "us-nh/statute/77-a:1",
    "us-nh/statute/77-a:2",
}
NH_EMPTY_TITLE = "<html><body><ul></ul></body></html>"
NH_EMPTY_CHAPTER_TOC = '<html><body><h2><a href="../V/77-B/77-B-mrg.htm">Entire Chapter</a></h2><ul></ul></body></html>'


def _new_hampshire_with_chapter_77b() -> dict[str, str]:
    pages = dict(NH_GOOD_PAGES)
    pages[NH_TITLE_V] = NH_TITLE_HTML.replace("</ul>", NH_CHAPTER_77B_LINK, 1)
    pages[NH_TOC_77B] = NH_CHAPTER_TOC_HTML.replace("77-A", "77-B")
    pages[NH_MERGED_77B] = NH_MERGED_HTML.replace("77-A", "77-B")
    return pages


def _extract_new_hampshire(tmp_path, pages: dict[str, str]):
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_new_hampshire_rsa(
        store, version="2026-05-10", source_dir=tmp_path / "source", request_delay_seconds=0
    )
    return store, report


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_new_hampshire_failed_title_toc_remains_inventory_gap(tmp_path, failure):
    # On main a title TOC that could not be fetched was logged as an error with
    # no inventory item, and one that listed no chapters raised out of the run.
    failed = "new-hampshire-rsa-title-toc-html/NHTOC-VI.htm"
    pages = dict(NH_GOOD_PAGES)
    pages[NH_ROOT] = NH_ROOT_HTML.replace(
        "</ul>",
        '  <li><a href="NHTOC/NHTOC-VI.htm">TITLE VI: PUBLIC OFFICERS AND EMPLOYEES</a></li>\n</ul>',
        1,
    )
    pages[failed] = NH_TITLE_HTML
    _fail_page(pages, failed, failure, {"no-children": NH_EMPTY_TITLE})
    store, report = _extract_new_hampshire(tmp_path, pages)
    assert report.section_count == 2
    assert "title VI" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=NH_EXTRACTED | {"us-nh/statute/title-vi"},
        missing={"us-nh/statute/title-vi"},
        gap_source=NH_ROOT if failure == "missing-file" else failed,
    )


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_new_hampshire_failed_chapter_toc_remains_inventory_gap(tmp_path, failure):
    # On main a chapter TOC that could not be fetched was logged as an error
    # with no inventory item, and one that listed nothing read complete.
    pages = _new_hampshire_with_chapter_77b()
    _fail_page(pages, NH_TOC_77B, failure, {"no-children": NH_EMPTY_CHAPTER_TOC})
    store, report = _extract_new_hampshire(tmp_path, pages)
    assert report.section_count == 2
    assert "chapter 77-B" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=NH_EXTRACTED | {"us-nh/statute/chapter-77-b"},
        missing={"us-nh/statute/chapter-77-b"},
        gap_source=NH_TITLE_V if failure == "missing-file" else NH_TOC_77B,
    )


@pytest.mark.parametrize("failure", TOC_FAILURES)
def test_new_hampshire_failed_merged_chapter_remains_inventory_gap(tmp_path, failure):
    # The chapter TOC lists the sections; the merged page carries their text.
    pages = _new_hampshire_with_chapter_77b()
    _fail_page(pages, NH_MERGED_77B, failure, {"no-children": "<html><body><p>Chapter 77-B</p></body></html>"})
    store, report = _extract_new_hampshire(tmp_path, pages)
    assert report.section_count == 2
    assert "chapter 77-B" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=NH_EXTRACTED | {"us-nh/statute/chapter-77-b"},
        missing={"us-nh/statute/chapter-77-b"},
        gap_source=NH_TITLE_V if failure == "missing-file" else NH_MERGED_77B,
    )


def test_new_hampshire_repealed_chapter_without_sections_stays_complete(tmp_path):
    # A repealed chapter's TOC lists no sections and its merged page says the
    # entire chapter was repealed: it lists nothing by law, so it stays a
    # complete container. Chapter 77 also has its own repeal check; this one
    # needs no session-law sources.
    pages = _new_hampshire_with_chapter_77b()
    pages[NH_TOC_77B] = NH_REPEALED_TOC_HTML.replace("77", "77-B")
    pages[NH_MERGED_77B] = NH_REPEALED_MERGED_HTML.replace("77", "77-B")
    _store, report = _extract_new_hampshire(tmp_path, pages)
    assert report.errors == ()
    assert report.coverage.complete is True
    provisions = {record.citation_path for record in load_provisions(report.provisions_path)}
    assert provisions == NH_EXTRACTED | {"us-nh/statute/chapter-77-b"}
