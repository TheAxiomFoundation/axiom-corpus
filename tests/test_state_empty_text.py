"""Metadata and HTML declarations cannot make an empty statute complete."""

import pytest
from bs4 import BeautifulSoup
from bs4.element import CData, Comment, Declaration, Doctype, ProcessingInstruction

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.state_adapters.maine import extract_maine_revised_statutes
from axiom_corpus.corpus.states import _ohio_laws_body_text, extract_ohio_revised_code
from tests.test_corpus_maine import (
    MAINE_REVISED_STATUTES_INDEX,
    SAMPLE_CHAPTER_HTML,
    SAMPLE_SECTION_HTML,
    SAMPLE_TITLE_HTML,
    SAMPLE_TITLE_INDEX_HTML,
)
from tests.test_corpus_states import SAMPLE_OHIO_CHAPTER, SAMPLE_OHIO_INDEX, SAMPLE_OHIO_TITLE
from tests.test_state_extraction_gaps import (
    MAINE_CONTAINERS,
    OHIO_CONTAINERS,
    _assert_visible_gaps,
    _write_sources,
)

MAINE_METADATA = [
    "",
    '<div class="note">Temporarily unavailable</div>',
    '<div class="qhistory">SECTION HISTORY</div><span class="bhistory">History</span>',
    "<script>loadSection()</script><style>body { display: none; }</style>",
    "<!DOCTYPE html><!-- No law available -->",
]


def _maine_pages():
    return {
        MAINE_REVISED_STATUTES_INDEX: SAMPLE_TITLE_INDEX_HTML,
        "36/title36ch0sec0.html": SAMPLE_TITLE_HTML,
        "36/title36ch822sec0.html": SAMPLE_CHAPTER_HTML,
        "36/title36sec5219-S.html": SAMPLE_SECTION_HTML,
        "36/title36sec5219-T.html": SAMPLE_SECTION_HTML.replace("5219-S", "5219-T"),
    }


@pytest.mark.parametrize("failed_section", ["5219-S", "5219-T"])
@pytest.mark.parametrize("container", ["MRSSection", "section-content"])
@pytest.mark.parametrize("metadata", MAINE_METADATA)
def test_maine_metadata_only_section_stays_inventory_gap(
    tmp_path, failed_section, container, metadata
):
    pages = _maine_pages()
    failed_path = f"36/title36sec{failed_section}.html"
    pages[failed_path] = (
        f'<div class="{container}"><h3 class="heading_section">'
        f"§{failed_section}. Earned income credit</h3>{metadata}</div>"
    )
    _write_sources(tmp_path / "source", pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_maine_revised_statutes(
        store, version="2026-05-09", source_dir=tmp_path / "source", only_title="36", workers=1
    )

    assert report.section_count == 1
    assert failed_path in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MAINE_CONTAINERS | {"us-me/statute/36/5219-S", "us-me/statute/36/5219-T"},
        missing={f"us-me/statute/36/{failed_section}"},
        gap_source="36/title36ch822sec0.html",
    )


@pytest.mark.parametrize("section", ["5219-S", "5219-T"])
@pytest.mark.parametrize("status_class", ["headnote_blip", "mrs-text"])
def test_maine_short_repealed_body_remains_complete(tmp_path, section, status_class):
    pages = _maine_pages()
    pages[f"36/title36sec{section}.html"] = (
        '<div class="MRSSection"><h3 class="heading_section">'
        f'§{section}. Former law</h3><div class="{status_class}">(REPEALED)</div></div>'
    )
    _write_sources(tmp_path / "source", pages)
    report = extract_maine_revised_statutes(
        CorpusArtifactStore(tmp_path / "corpus"),
        version="2026-05-09",
        source_dir=tmp_path / "source",
        only_title="36",
        workers=1,
    )

    assert report.section_count == 2
    assert report.errors == ()
    assert report.coverage.complete is True
    record = next(
        record
        for record in load_provisions(report.provisions_path)
        if record.citation_path == f"us-me/statute/36/{section}"
    )
    assert record.body == "(REPEALED)"
    if status_class == "headnote_blip":
        assert record.metadata["status"] == "repealed"


@pytest.mark.parametrize("metadata", MAINE_METADATA)
def test_maine_all_metadata_only_sections_raise(tmp_path, metadata):
    pages = _maine_pages()
    for section in ("5219-S", "5219-T"):
        pages[f"36/title36sec{section}.html"] = (
            '<div class="MRSSection"><h3 class="heading_section">'
            f"§{section}. Credit</h3>{metadata}</div>"
        )
    _write_sources(tmp_path / "source", pages)

    with pytest.raises(ValueError, match="no Maine sections extracted"):
        extract_maine_revised_statutes(
            CorpusArtifactStore(tmp_path / "corpus"),
            version="2026-05-09",
            source_dir=tmp_path / "source",
            only_title="36",
            workers=1,
        )


@pytest.mark.parametrize("failed_index", [0, 1])
@pytest.mark.parametrize(
    "markup",
    [
        "<!DOCTYPE html>",
        "<!-- No law available -->",
        "<![CDATA[Not statutory text]]>",
        '<?xml version="1.0"?>',
        "<!notice Not statutory text>",
    ],
)
def test_ohio_serialized_special_nodes_and_notice_stay_inventory_gap(
    tmp_path, failed_index, markup
):
    chapter = BeautifulSoup(SAMPLE_OHIO_CHAPTER, "html.parser")
    body = chapter.select("section.laws-body")[failed_index]
    body.clear()
    # Round-trip the markup through the real chapter parser, including DOCTYPE.
    body.append(BeautifulSoup(markup, "html.parser"))
    notice = chapter.new_tag("div", attrs={"class": "laws-notice"})
    notice.string = "Last updated"
    body.append(notice)
    _write_sources(
        tmp_path / "source",
        {
            "ohio-revised-code/index.html": SAMPLE_OHIO_INDEX,
            "ohio-revised-code/titles/title-51.html": SAMPLE_OHIO_TITLE,
            "ohio-revised-code/chapters/chapter-5160.html": str(chapter),
        },
    )
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_ohio_revised_code(
        store, version="2026-05-09", source_dir=tmp_path / "source", only_title="51"
    )

    assert report.section_count == 1
    failed_section = ("5160.01", "5160.011")[failed_index]
    assert failed_section in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=OHIO_CONTAINERS | {"us-oh/statute/5160.01", "us-oh/statute/5160.011"},
        missing={f"us-oh/statute/{failed_section}"},
        gap_source="ohio-revised-code/chapters/chapter-5160.html",
    )


@pytest.mark.parametrize("node_type", [Comment, Doctype, CData, ProcessingInstruction, Declaration])
def test_ohio_body_walker_excludes_special_string_types(node_type):
    soup = BeautifulSoup('<section class="laws-body"></section>', "html.parser")
    body = soup.section
    body.append(node_type("NON_STATUTORY_METADATA"))

    assert _ohio_laws_body_text(body) is None
    body.append("Operative text.")
    assert _ohio_laws_body_text(body) == "Operative text."
