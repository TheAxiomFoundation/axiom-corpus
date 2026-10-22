"""Nonoperative section markup cannot satisfy statute completeness gates."""

from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from bs4 import BeautifulSoup
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.state_adapters.maine import (
    MAINE_REVISED_STATUTES_INDEX,
    extract_maine_revised_statutes,
)
from axiom_corpus.corpus.states import extract_ohio_revised_code
from tests.test_corpus_maine import (
    SAMPLE_CHAPTER_HTML,
    SAMPLE_SECTION_HTML,
    SAMPLE_TITLE_HTML,
    SAMPLE_TITLE_INDEX_HTML,
)
from tests.test_corpus_states import (
    SAMPLE_OHIO_CHAPTER,
    SAMPLE_OHIO_INDEX,
    SAMPLE_OHIO_TITLE,
)
from tests.test_state_extraction_gaps import (
    MAINE_CONTAINERS,
    OHIO_CONTAINERS,
    _assert_visible_gaps,
    _write_sources,
)

_NONOPERATIVE_FRAGMENTS = st.lists(
    st.tuples(
        st.sampled_from(("heading", "notice", "history", "doctype", "comment", "empty")),
        st.text(alphabet="abc XYZ019,.;:$%&é£\t\n", max_size=60),
        st.lists(st.sampled_from(("div", "span", "section")), max_size=2),
        st.sampled_from(("", " ", "\n", "\t", "\u00a0")),
    ),
    max_size=10,
)


def _nonoperative_markup(fragments, *, jurisdiction):
    headings = []
    body = []
    for kind, payload, wrappers, whitespace in fragments:
        text = escape(payload)
        if kind == "heading":
            markup = (
                f'<h3 class="heading_section">§5219-S. {text}</h3>'
                if jurisdiction == "us-me"
                else f"<h3>{text}</h3>"
            )
        elif kind == "notice":
            css_class = "note" if jurisdiction == "us-me" else "laws-notice"
            markup = f'<div class="{css_class}"><p>{text}</p></div>'
        elif kind == "history":
            css_class = "qhistory" if jurisdiction == "us-me" else "laws-notice"
            markup = f'<div class="{css_class}">SECTION HISTORY {text}</div>'
        elif kind == "doctype":
            markup = "<!DOCTYPE html>"
        elif kind == "comment":
            markup = f"<!--{payload}-->"
        else:
            markup = ""
        for wrapper in wrappers:
            markup = f"<{wrapper}>{whitespace}{markup}{whitespace}</{wrapper}>"
        markup = whitespace + markup + whitespace
        # Ohio's recognized section heading belongs to the metadata outside
        # .laws-body, as in the official chapter fixture.
        destination = headings if kind == "heading" and jurisdiction == "us-oh" else body
        destination.append(markup)
    return "".join(headings), "".join(body)


@pytest.mark.parametrize("jurisdiction", ["us-me", "us-oh"])
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@example(fragments=[("doctype", "", [], "")])
@given(fragments=_NONOPERATIVE_FRAGMENTS)
def test_generated_nonoperative_sections_remain_incomplete(tmp_path, jurisdiction, fragments):
    headings, body = _nonoperative_markup(fragments, jurisdiction=jurisdiction)
    with TemporaryDirectory(dir=tmp_path) as directory:
        root = Path(directory)
        source = root / "source"
        store = CorpusArtifactStore(root / "corpus")
        if jurisdiction == "us-me":
            empty_section = (
                '<html><body><div class="MRSSection status_current">'
                '<h3 class="heading_section">§5219-S. Earned income credit</h3>'
                f"{body}</div></body></html>"
            )
            _write_sources(
                source,
                {
                    MAINE_REVISED_STATUTES_INDEX: SAMPLE_TITLE_INDEX_HTML,
                    "36/title36ch0sec0.html": SAMPLE_TITLE_HTML,
                    "36/title36ch822sec0.html": SAMPLE_CHAPTER_HTML,
                    "36/title36sec5219-S.html": empty_section,
                    "36/title36sec5219-T.html": SAMPLE_SECTION_HTML.replace("5219-S", "5219-T"),
                },
            )
            report = extract_maine_revised_statutes(
                store, version="2026-05-09", source_dir=source, only_title="36", workers=1
            )
            expected = MAINE_CONTAINERS | {"us-me/statute/36/5219-S", "us-me/statute/36/5219-T"}
            missing = {"us-me/statute/36/5219-S"}
            gap_source = "36/title36ch822sec0.html"
        else:
            chapter = BeautifulSoup(SAMPLE_OHIO_CHAPTER, "html.parser")
            body_tag = chapter.select("section.laws-body")[0]
            body_tag.clear()
            for node in list(BeautifulSoup(body, "html.parser").contents):
                body_tag.append(node)
            info = chapter.select(".laws-section-info")[0]
            for node in list(BeautifulSoup(headings, "html.parser").contents):
                info.append(node)
            _write_sources(
                source,
                {
                    "ohio-revised-code/index.html": SAMPLE_OHIO_INDEX,
                    "ohio-revised-code/titles/title-51.html": SAMPLE_OHIO_TITLE,
                    "ohio-revised-code/chapters/chapter-5160.html": str(chapter),
                },
            )
            report = extract_ohio_revised_code(
                store, version="2026-05-09", source_dir=source, only_title="51"
            )
            expected = OHIO_CONTAINERS | {"us-oh/statute/5160.01", "us-oh/statute/5160.011"}
            missing = {"us-oh/statute/5160.01"}
            gap_source = "ohio-revised-code/chapters/chapter-5160.html"
        assert report.section_count == 1
        _assert_visible_gaps(
            store,
            report,
            expected=expected,
            missing=missing,
            gap_source=gap_source,
        )
