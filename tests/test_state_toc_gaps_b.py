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
from axiom_corpus.corpus.state_adapters.maryland import extract_maryland_code
from tests.test_corpus_maryland import SAMPLE_SECTION_HTML as MD_SECTION_HTML
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
