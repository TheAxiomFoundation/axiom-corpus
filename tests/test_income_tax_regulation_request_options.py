"""Request options and NYCRR citation handling added for the 2026-09-14 income-tax regulation run."""

from __future__ import annotations

from bs4 import BeautifulSoup

from axiom_corpus.corpus.documents import _request_headers_from_config
from axiom_corpus.corpus.nycrr import _part_child_citation_path


def test_request_headers_include_declared_cookies() -> None:
    headers = _request_headers_from_config(
        {"cookies": {"bhCookieSess": "1", "bhCookiePerm": "1"}, "browser_user_agent": True}
    )
    assert headers is not None
    assert headers["Cookie"] == "bhCookieSess=1; bhCookiePerm=1"
    assert headers["User-Agent"].startswith("Mozilla/5.0")


def test_request_headers_stay_none_without_options() -> None:
    assert _request_headers_from_config({}) is None
    assert _request_headers_from_config({"cookies": {}}) is None


def test_nycrr_repealed_range_link_gets_a_range_citation_path() -> None:
    soup = BeautifulSoup("<html><body><p>no citation label</p></body></html>", "html.parser")
    path = _part_child_citation_path(
        soup,
        part="101",
        part_citation_path="us-ny/regulation/20-nycrr/101",
        link_text="s 101.5 -- 101.7 (Repealed)",
    )
    assert path == "us-ny/regulation/20-nycrr/101/5-7"


def test_html_text_selector_reads_div_containers_once() -> None:
    from axiom_corpus.corpus.documents import _html_text_nodes

    soup = BeautifulSoup(
        "<div id='doc'><h1>Sec. 1</h1><div class='subsection'>Outer "
        "<div class='subsection'>inner</div></div><p>para</p></div>",
        "html.parser",
    )
    root = soup.select_one("#doc")
    assert root is not None
    default_nodes = _html_text_nodes(root, extraction=None)
    assert [node.name for node in default_nodes] == ["h1", "p"]
    selected = _html_text_nodes(root, extraction={"html_text_selector": "h1, div.subsection, p"})
    assert [node.get_text(" ", strip=True) for node in selected] == ["Sec. 1", "Outer inner", "para"]
