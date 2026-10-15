"""Only rendered operative content can make a statute section complete.

DOM properties preserve every BeautifulSoup node type and arbitrary nesting.
Extraction properties additionally check the persisted completeness gate after
HTML serialization; explicit regressions check coverage, release, and completion
selection together.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import (
    CData,
    Comment,
    Declaration,
    Doctype,
    ProcessingInstruction,
    XMLProcessingInstruction,
)
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.state_adapters.maine import (
    MAINE_REVISED_STATUTES_INDEX,
    _maine_section_body_lines,
    extract_maine_revised_statutes,
    parse_maine_section,
)
from axiom_corpus.corpus.states import _ohio_laws_body_text, extract_ohio_revised_code
from tests.test_corpus_maine import (
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

_NONRENDERED = ("template", "script", "style", "noscript", "head", "iframe", "object")
_SPECIAL_NODES = {
    "comment": Comment,
    "doctype": Doctype,
    "cdata": CData,
    "processing": ProcessingInstruction,
    "xml_processing": XMLProcessingInstruction,
    "declaration": Declaration,
}
_COMMON = (*_NONRENDERED, "hidden", "aria-hidden", *_SPECIAL_NODES)
_ANNOTATIONS = ("bhistory", "note", "qhistory", "headnote_blip", "heading_section")
_OHIO_METADATA = (
    "laws-notice",
    "laws-section-info",
    "laws-section-info-module",
    "content-head-text",
    "nav",
    "navigation-role",
)
_WHITESPACE = st.sampled_from(("", " ", "\n", "\t", "\u00a0", "\n \t"))
_PAYLOAD = st.text(alphabet="abc XYZ019,.;:$%&é£ \t\n", max_size=30).map(
    lambda text: "NONOPERATIVE " + text
)
_OPERATIVE = "A taxpayer shall receive a credit of 12 dollars."


def _kinds(jurisdiction):
    return (*_COMMON, *(_ANNOTATIONS if jurisdiction == "maine" else _OHIO_METADATA))


def _fragment_strategy(jurisdiction, *, serialized=False):
    kinds = _kinds(jurisdiction)
    wrappers = ("div", "span", "section")
    if not serialized:
        wrappers += tuple(kind for kind in kinds if kind not in _SPECIAL_NODES)
    return st.lists(
        st.tuples(
            st.sampled_from(kinds),
            _PAYLOAD,
            st.lists(st.sampled_from(wrappers), max_size=5),
            _WHITESPACE,
        ),
        max_size=8,
    )


def _nonoperative_node(soup, kind, payload):
    if kind in _SPECIAL_NODES:
        return _SPECIAL_NODES[kind](payload)
    if kind == "hidden":
        node = soup.new_tag("div", attrs={"hidden": ""})
    elif kind == "aria-hidden":
        node = soup.new_tag("div", attrs={"aria-hidden": "true"})
    elif kind == "navigation-role":
        node = soup.new_tag("div", attrs={"role": "navigation"})
    elif kind in _NONRENDERED or kind in {"div", "span", "section", "nav"}:
        node = soup.new_tag(kind)
    else:
        node = soup.new_tag("div", attrs={"class": kind})
    node.append(payload)
    return node


def _noise(soup, fragments):
    nodes = []
    for kind, payload, wrappers, whitespace in fragments:
        node = _nonoperative_node(soup, kind, payload)
        for wrapper in wrappers:
            # Special strings are leaves, so they can enclose serialized noise
            # as data; all element wrappers preserve their actual child nodes.
            parent = _nonoperative_node(soup, wrapper, "")
            if isinstance(parent, Tag):
                parent.clear()
                parent.append(whitespace)
                parent.append(node)
                parent.append(whitespace)
                node = parent
            else:
                node = type(parent)(str(node))
        nodes.extend((NavigableString(whitespace), node, NavigableString(whitespace)))
    return nodes


def _body(soup, jurisdiction, fragments, *, operative=False):
    root = soup.new_tag("div", attrs={"class": "MRSSection"})
    if jurisdiction == "ohio":
        root["class"] = "laws-body"
    for node in _noise(soup, fragments):
        root.append(node)
    if operative:
        paragraph = soup.new_tag("p")
        paragraph.append(_OPERATIVE)
        # Noise inside an operative paragraph must not change its text either.
        for node in _noise(soup, fragments):
            paragraph.insert(0, node)
        root.append(paragraph)
        for node in _noise(soup, fragments):
            root.append(node)
    return root


def _parsed_body(root, jurisdiction):
    if jurisdiction == "maine":
        return "\n".join(_maine_section_body_lines(root)) or None
    return _ohio_laws_body_text(root)


def _extract(root, jurisdiction, markup, *, failed_index=0):
    source = root / "source"
    store = CorpusArtifactStore(root / "corpus")
    if jurisdiction == "maine":
        sections = ("5219-S", "5219-T")
        failed_section = sections[failed_index]
        pages = {
            MAINE_REVISED_STATUTES_INDEX: SAMPLE_TITLE_INDEX_HTML,
            "36/title36ch0sec0.html": SAMPLE_TITLE_HTML,
            "36/title36ch822sec0.html": SAMPLE_CHAPTER_HTML,
            "36/title36sec5219-S.html": SAMPLE_SECTION_HTML,
            "36/title36sec5219-T.html": SAMPLE_SECTION_HTML.replace("5219-S", "5219-T"),
        }
        pages[f"36/title36sec{failed_section}.html"] = (
            '<div class="MRSSection status_current"><h3 class="heading_section">'
            f"§{failed_section}. Earned income credit</h3>{markup}</div>"
        )
        _write_sources(source, pages)
        report = extract_maine_revised_statutes(
            store, version="2026-05-09", source_dir=source, only_title="36", workers=1
        )
    else:
        failed_section = ("5160.01", "5160.011")[failed_index]
        chapter = BeautifulSoup(SAMPLE_OHIO_CHAPTER, "html.parser")
        body = chapter.select("section.laws-body")[failed_index]
        body.clear()
        for node in list(BeautifulSoup(markup, "html.parser").contents):
            body.append(node)
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
    return store, report, failed_section


def _visible_gap(store, report, jurisdiction, failed_section):
    if jurisdiction == "maine":
        expected = MAINE_CONTAINERS | {"us-me/statute/36/5219-S", "us-me/statute/36/5219-T"}
        missing = {f"us-me/statute/36/{failed_section}"}
        gap_source = "36/title36ch822sec0.html"
    else:
        expected = OHIO_CONTAINERS | {"us-oh/statute/5160.01", "us-oh/statute/5160.011"}
        missing = {f"us-oh/statute/{failed_section}"}
        gap_source = "ohio-revised-code/chapters/chapter-5160.html"
    assert report.section_count == 1
    _assert_visible_gaps(
        store, report, expected=expected, missing=missing, gap_source=gap_source
    )


@pytest.mark.parametrize("failed_index", [0, 1])
def test_ohio_template_only_section_remains_visible_gap(tmp_path, failed_index):
    store, report, failed_section = _extract(
        tmp_path,
        "ohio",
        "<template><p>Scheduled maintenance</p></template>",
        failed_index=failed_index,
    )
    _visible_gap(store, report, "ohio", failed_section)


@pytest.mark.parametrize("failed_index", [0, 1])
@pytest.mark.parametrize("wrapper", ["mrs-text", "MRSSubSection"])
def test_maine_embedded_history_only_section_remains_visible_gap(
    tmp_path, failed_index, wrapper
):
    store, report, failed_section = _extract(
        tmp_path,
        "maine",
        f'<div class="{wrapper}"><span class="bhistory">'
        "[PL 2020, c. 1 (NEW).]</span></div>",
        failed_index=failed_index,
    )
    _visible_gap(store, report, "maine", failed_section)


@pytest.mark.parametrize(
    "markup",
    [
        '<div class="headnote_blip">Scheduled maintenance</div>',
        '<div hidden><div class="headnote_blip">(REPEALED)</div></div>',
        '<div aria-hidden="true"><div class="headnote_blip">(REPEALED)</div></div>',
        '<template><div class="headnote_blip">(REPEALED)</div></template>',
        '<div class="bhistory"><div class="headnote_blip">(REPEALED)</div></div>',
    ],
)
def test_maine_nonoperative_status_cannot_revive_empty_body(markup):
    html = (
        '<div class="MRSSection"><h3 class="heading_section">§1. Example</h3>'
        f"{markup}</div>"
    )
    with pytest.raises(ValueError, match="lacks operative text or a status body"):
        parse_maine_section(html)


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
@pytest.mark.parametrize("depth", [0, 3])
def test_every_nonoperative_construct_is_inert_at_multiple_depths(jurisdiction, depth):
    for kind in _kinds(jurisdiction):
        fragments = [(kind, "NONOPERATIVE", ["div", "span", "section"][:depth], "\n\t ")]
        soup = BeautifulSoup("", "html.parser")
        assert _parsed_body(_body(soup, jurisdiction, fragments), jurisdiction) is None
        body = _body(soup, jurisdiction, fragments, operative=True)
        assert _parsed_body(body, jurisdiction) == _OPERATIVE


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
def test_nonoperative_ancestors_hide_the_entire_body(jurisdiction):
    for kind in _kinds(jurisdiction):
        if kind in _SPECIAL_NODES:
            continue
        soup = BeautifulSoup("", "html.parser")
        ancestor = _nonoperative_node(soup, kind, "")
        body = _body(soup, jurisdiction, [], operative=True)
        ancestor.append(body)
        assert _parsed_body(body, jurisdiction) is None


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
@settings(max_examples=40, deadline=None)
@given(data=st.data())
def test_generated_nonoperative_dom_never_has_body(jurisdiction, data):
    fragments = data.draw(_fragment_strategy(jurisdiction))
    soup = BeautifulSoup("", "html.parser")
    assert _parsed_body(_body(soup, jurisdiction, fragments), jurisdiction) is None


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
@settings(max_examples=40, deadline=None)
@given(data=st.data())
def test_generated_dom_noise_never_changes_operative_body(jurisdiction, data):
    fragments = data.draw(_fragment_strategy(jurisdiction))
    soup = BeautifulSoup("", "html.parser")
    body = _body(soup, jurisdiction, fragments, operative=True)
    assert _parsed_body(body, jurisdiction) == _OPERATIVE


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data())
def test_generated_nonoperative_extraction_stays_incomplete(tmp_path, jurisdiction, data):
    fragments = data.draw(_fragment_strategy(jurisdiction, serialized=True))
    soup = BeautifulSoup("", "html.parser")
    markup = _body(soup, jurisdiction, fragments).decode_contents()
    with TemporaryDirectory(dir=tmp_path) as directory:
        store, report, failed_section = _extract(Path(directory), jurisdiction, markup)
        _visible_gap(store, report, jurisdiction, failed_section)


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.data())
def test_generated_operative_paragraph_restores_complete_extraction(tmp_path, jurisdiction, data):
    fragments = data.draw(_fragment_strategy(jurisdiction, serialized=True))
    soup = BeautifulSoup("", "html.parser")
    markup = _body(soup, jurisdiction, fragments, operative=True).decode_contents()
    with TemporaryDirectory(dir=tmp_path) as directory:
        _, report, failed_section = _extract(Path(directory), jurisdiction, markup)
        assert report.section_count == 2
        assert report.errors == ()
        assert report.coverage.complete is True
        citation = (
            f"us-me/statute/36/{failed_section}"
            if jurisdiction == "maine"
            else f"us-oh/statute/{failed_section}"
        )
        record = next(
            record
            for record in load_provisions(report.provisions_path)
            if record.citation_path == citation
        )
        assert record.body == _OPERATIVE
