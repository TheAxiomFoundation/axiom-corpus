"""Opt-in amendment styles used by NJ proposals and Washington register HTML."""

from __future__ import annotations

import fitz
import pytest

from axiom_corpus.corpus import documents


def test_bold_pdf_insertions_are_opt_in_and_limited_to_selected_pages() -> None:
    with fitz.open() as pdf:
        for _ in range(2):
            page = pdf.new_page()
            page.insert_text((72, 72), "Heading emphasis", fontname="hebo")
            page.insert_text((72, 100), "[Deleted clause]", fontname="helv")
            page.insert_text((72, 120), "Inserted clause", fontname="hebo")
        content = pdf.tobytes()
    plain = documents._extract_pdf_blocks(content, extraction=None)
    marked = documents._extract_pdf_blocks(
        content,
        extraction={
            "amendment_markup": {
                "start_page": 2,
                "end_page": 2,
                "inserted_style": "bold",
            }
        },
    )
    assert marked[0] == plain[0]
    assert "{+Inserted clause+}" in marked[1].body
    assert "[Deleted clause]" in marked[1].body
    assert marked[1].metadata["amendment_markup"]["inserted_source_markup"] == "bold"
    assert documents._strip_amendment_markup(marked[1].body) == plain[1].body
    # The established default detects drawn underlines, not bold emphasis.
    underline = documents._extract_pdf_blocks(content, extraction={"amendment_markup": True})
    assert [block.body for block in underline] == [block.body for block in plain]


def test_html_amendments_preserve_nested_tags_and_typographic_underlines() -> None:
    content = b"""<html><body><u>AMENDATORY SECTION</u>
    <p>Old <strike><b>deleted</b> words</strike> clause.</p>
    <u class="amendment"><p>New <b>inserted</b> clause.</p><p>Continuation.</p></u>
    </body></html>"""
    options = {"html_content_selector": "html", "html_text_selector": "body"}
    plain = documents._extract_html_blocks(
        content, source_url="https://example.gov/rule", fallback_title="Rule", extraction=options
    )
    marked = documents._extract_html_blocks(
        content,
        source_url="https://example.gov/rule",
        fallback_title="Rule",
        extraction={
            **options,
            "html_amendment_markup": {
                "deleted_selector": "strike",
                "inserted_selector": "u.amendment",
            },
        },
    )
    assert len(marked) == len(plain) == 1
    assert marked[0].body == (
        "AMENDATORY SECTION Old [-deleted words-] clause. {+New inserted clause. Continuation.+}"
    )
    assert documents._strip_amendment_markup(marked[0].body) == plain[0].body
    assert marked[0].metadata["amendment_markup"]["deleted_runs"] == 1
    assert marked[0].metadata["amendment_markup"]["inserted_runs"] == 1


def test_explicit_html_encoding_preserves_legacy_section_sign() -> None:
    (block,) = documents._extract_html_blocks(
        b"<html><body><p>WAC \xa7 388-450-0015 <u>new text</u></p></body></html>",
        source_url="https://example.gov/rule",
        fallback_title="Rule",
        extraction={
            "html_encoding": "windows-1252",
            "html_amendment_markup": {"inserted_selector": "u"},
        },
    )
    assert block.body == "WAC § 388-450-0015 {+new text+}"


@pytest.mark.parametrize(
    ("content", "options", "error"),
    [
        (b"<p>Plain</p>", {"inserted_selector": "u"}, "did not match"),
        (b"<u>{+existing+}</u>", {"inserted_selector": "u"}, "already contains"),
        (
            b"<p><u><strike>Conflicting</strike></u></p>",
            {"deleted_selector": "strike", "inserted_selector": "u"},
            "both inserted and deleted",
        ),
    ],
)
def test_html_amendment_configuration_fails_closed(
    content: bytes, options: dict[str, str], error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        documents._extract_html_blocks(
            content,
            source_url="https://example.gov/rule",
            fallback_title="Rule",
            extraction={"html_amendment_markup": options},
        )
