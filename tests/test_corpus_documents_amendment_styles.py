"""Opt-in amendment styles and HTML/DOCX options used by the SNAP child support sources.

New Jersey register proposals print additions in bold and deletions in brackets;
the Washington State Register prints ``((<strike>...</strike>))`` deletions and
``<u>`` insertions in legacy windows-1252 HTML; the Louisiana Administrative Code
DOCX stores its definition dashes as Word ``<w:sym>`` glyphs. Every option here
is opt-in: without it, extraction is unchanged.

The property tests use a seeded generator rather than Hypothesis, which is not a
dependency of this repository; each property runs over a few thousand
deterministic cases.
"""

from __future__ import annotations

import random
import re
import zipfile
from io import BytesIO
from xml.sax.saxutils import escape

import fitz
import pytest

from axiom_corpus.corpus import documents

_DELETED = documents._AMENDMENT_DELETED
_INSERTED = documents._AMENDMENT_INSERTED


def _pdf(pages: list[list[tuple[str, str]]]) -> bytes:
    """Build a PDF whose pages hold (text, fontname) lines, one per 20 points."""
    with fitz.open() as pdf:
        for lines in pages:
            page = pdf.new_page()
            for number, (text, fontname) in enumerate(lines):
                page.insert_text((72, 72 + 20 * number), text, fontname=fontname)
        return pdf.tobytes()


def _bodies(content: bytes, markup: dict | bool | None) -> list[str]:
    extraction = None if markup is None else {"amendment_markup": markup}
    return [block.body for block in documents._extract_pdf_blocks(content, extraction=extraction)]


# PDF: bold insertions -------------------------------------------------------------


def test_bold_pdf_insertions_are_opt_in_and_limited_to_selected_pages() -> None:
    page = [("Heading emphasis", "hebo"), ("[Deleted clause]", "helv"), ("Inserted clause", "hebo")]
    content = _pdf([page, page])
    plain = documents._extract_pdf_blocks(content, extraction=None)
    marked = documents._extract_pdf_blocks(
        content,
        extraction={"amendment_markup": {"start_page": 2, "end_page": 2, "inserted_style": "bold"}},
    )
    assert marked[0] == plain[0]
    # Every bold span in the marked pages is an insertion, headings included; a
    # manifest restricts the page range (or lists typographic_underlines) to
    # keep bold typography out.
    assert marked[1].body == "{+Heading emphasis+}\n[Deleted clause]\n{+Inserted clause+}".replace(
        "\n", " "
    )
    assert "[Deleted clause]" in marked[1].body
    metadata = marked[1].metadata["amendment_markup"]
    assert metadata["inserted_source_markup"] == "bold"
    assert metadata["deleted_source_markup"] == "strike-through"
    assert documents._strip_amendment_markup(marked[1].body) == plain[1].body
    # The established default detects drawn underlines, not bold emphasis.
    assert _bodies(content, True) == [block.body for block in plain]


def test_default_markup_metadata_keeps_its_keys_and_order() -> None:
    content = _pdf([[("Plain text", "helv")]])
    (block,) = documents._extract_pdf_blocks(content, extraction={"amendment_markup": True})
    assert list(block.metadata["amendment_markup"]) == [
        "notation",
        "deleted",
        "inserted",
        "deleted_source_markup",
        "inserted_source_markup",
        "deleted_runs",
        "inserted_runs",
    ]
    assert block.metadata["amendment_markup"]["deleted_source_markup"] == "strike-through"
    assert block.metadata["amendment_markup"]["inserted_source_markup"] == "underline"


def test_bold_text_that_is_also_struck_through_fails() -> None:
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Struck bold", fontname="hebo", fontsize=11)
        # A strike sits about a quarter of the font size above the baseline.
        page.draw_line((70, 69.3), (150, 69.3), width=0.6)
        content = pdf.tobytes()
    with pytest.raises(ValueError, match="both struck through and bold"):
        documents._extract_pdf_blocks(
            content, extraction={"amendment_markup": {"inserted_style": "bold"}}
        )


# PDF: bracket deletions -----------------------------------------------------------

_BRACKETS = {
    "start_page": 2,
    "end_page": 3,
    "inserted_style": "bold",
    "deleted_style": "brackets",
    "unmarked_line_patterns": [r"- \d+ -"],
}


def test_bracket_deletions_become_delimited_runs_across_a_page_break() -> None:
    content = _pdf(
        [
            [("Cover page [not marked]", "helv")],
            [("- 2 -", "helv"), ("Kept text [old clause", "helv"), ("continues here", "helv")],
            [("- 3 -", "helv"), ("and ends] then", "helv"), ("New words", "hebo")],
        ]
    )
    blocks = documents._extract_pdf_blocks(content, extraction={"amendment_markup": _BRACKETS})
    assert [block.body for block in blocks] == [
        "Cover page [not marked]",
        "- 2 - Kept text [-old clause continues here-]",
        "- 3 - [-and ends-] then {+New words+}",
    ]
    second, third = (block.metadata["amendment_markup"] for block in blocks[1:])
    assert second["deleted_source_markup"] == third["deleted_source_markup"] == "brackets"
    assert second["deletion_continues_to_next_page"] is True
    assert "deletion_continues_from_previous_page" not in second
    assert third["deletion_continues_from_previous_page"] is True
    assert "deletion_continues_to_next_page" not in third
    assert (second["deleted_runs"], third["deleted_runs"], third["inserted_runs"]) == (1, 1, 1)
    assert "amendment_markup" not in blocks[0].metadata


@pytest.mark.parametrize(
    ("pages", "error"),
    [
        ([[("x", "helv")], [("a [b [c] d]", "helv")], [("e", "helv")]], "nested deletion bracket"),
        ([[("x", "helv")], [("a b] c", "helv")], [("e", "helv")]], "never opened"),
        ([[("x", "helv")], [("a", "helv")], [("b [c", "helv")]], "not closed by the last page"),
        (
            [[("x", "helv")], [("a", "helv")], [("b [c", "helv")], [("d] e", "helv")]],
            "outside the marked pages",
        ),
        ([[("x", "helv")], [("a [b", "helv"), ("bold", "hebo"), ("c]", "helv")], [("e", "helv")]],
         "inserted inside a bracketed deletion"),
    ],
)
def test_bracket_deletions_fail_closed(pages: list, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        documents._extract_pdf_blocks(_pdf(pages), extraction={"amendment_markup": _BRACKETS})


def test_bracket_mode_refuses_drawn_strike_throughs() -> None:
    with fitz.open() as pdf:
        pdf.new_page()
        page = pdf.new_page()
        page.insert_text((72, 72), "Struck plain", fontname="helv", fontsize=11)
        page.draw_line((70, 69.3), (150, 69.3), width=0.6)
        pdf.new_page()
        content = pdf.tobytes()
    with pytest.raises(ValueError, match="struck through, but amendment_markup deleted_style"):
        documents._extract_pdf_blocks(content, extraction={"amendment_markup": _BRACKETS})


def _struck_page_one(*, underlined: bool) -> bytes:
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Page 1", fontname="helv", fontsize=11)
        page.draw_line((70, 69.3), (150, 69.3), width=0.6)
        if underlined:
            page.draw_line((70, 73.5), (150, 73.5), width=0.6)
        return pdf.tobytes()


def test_unmarked_lines_are_exempt_before_any_classification() -> None:
    # A struck running page number would otherwise fail bracket mode.
    content = _struck_page_one(underlined=False)
    config = {"inserted_style": "bold", "deleted_style": "brackets", "unmarked_line_patterns": ["Page 1"]}
    assert _bodies(content, config) == ["Page 1"]
    assert _bodies(content, True) == ["[-Page 1-]"]


def test_bold_mode_ignores_drawn_underlines_even_on_struck_text() -> None:
    content = _struck_page_one(underlined=True)
    assert _bodies(content, {"inserted_style": "bold"}) == ["[-Page 1-]"]
    # The default still refuses a character that is both struck and underlined.
    with pytest.raises(ValueError, match="both struck through and underlined"):
        _bodies(content, True)


@pytest.mark.parametrize(
    ("config", "error"),
    [
        ({"inserted_style": "italic"}, "inserted_style must be underline or bold"),
        ({"deleted_style": "strike"}, "deleted_style must be strike-through or brackets"),
        ({"unmarked_line_patterns": "- 1 -"}, "unmarked_line_patterns must be a list"),
        ({"unmarked_line_patterns": [""]}, "unmarked_line_patterns must be a list"),
        ({"deletion_style": "brackets"}, "unknown amendment_markup keys"),
    ],
)
def test_amendment_style_configuration_is_validated(config: dict, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        documents._pdf_amendment_markup_config({"amendment_markup": config})


# HTML -----------------------------------------------------------------------------


def _html(content: bytes, extraction: dict | None) -> tuple[documents._DocumentBlock, ...]:
    return documents._extract_html_blocks(
        content, source_url="https://example.gov/rule", fallback_title="Rule", extraction=extraction
    )


def test_html_amendments_keep_nested_tags_paragraphs_and_selected_underlines_only() -> None:
    content = b"""<html><body><u>AMENDATORY SECTION</u>
    <p>Old <strike><b>deleted</b> words</strike> clause.</p>
    <u class="amendment"><p>New <b>inserted</b> clause.</p><p>Continuation.</p></u>
    </body></html>"""
    options = {"html_content_selector": "html", "html_text_selector": "body"}
    (plain,) = _html(content, options)
    (marked,) = _html(
        content,
        {
            **options,
            "html_amendment_markup": {
                "deleted_selector": "strike",
                "inserted_selector": "u.amendment",
            },
        },
    )
    assert marked.body == (
        "AMENDATORY SECTION\n\nOld [-deleted words-] clause.\n\n"
        "{+New inserted clause.+}\n\n{+Continuation.+}"
    )
    stripped = documents._strip_amendment_markup(marked.body)
    assert re.sub(r"\s", "", stripped) == re.sub(r"\s", "", plain.body)
    assert marked.metadata["amendment_markup"]["deleted_runs"] == 1
    assert marked.metadata["amendment_markup"]["inserted_runs"] == 2


def test_html_amendment_tags_inside_words_add_no_spaces() -> None:
    content = b"<html><body><p>the household; ((<strike>and</strike>)) member<u>s</u>.</p></body></html>"
    (block,) = _html(
        content,
        {
            "html_text_selector": "body",
            "html_amendment_markup": {"deleted_selector": "strike", "inserted_selector": "u"},
        },
    )
    assert block.body == "the household; (([-and-])) member{+s+}."


_MARKED = {
    "html_text_selector": "body",
    "html_amendment_markup": {"inserted_selector": "u", "deleted_selector": "strike"},
}


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        # Text after a closing block is a new paragraph, not glued to the block.
        (b"<body><div>Income <u>limit</u></div>Exception <strike>no</strike></body>",
         "Income {+limit+}\n\nException [-no-]"),
        # Table cells are separate words; rows are separate paragraphs.
        (b"<body><table><tr><td>1</td><td><u>200</u></td></tr><tr><td><strike>3</strike></td></tr></table></body>",
         "1 {+200+}\n\n[-3-]"),
        # <br> separates words.
        (b"<body><p>First<br><u>Second</u> <strike>x</strike></p></body>", "First {+Second+} [-x-]"),
        # Comments and CDATA are not text (the default lxml parse drops CDATA).
        (b"<body><p>A<!-- hidden --> <u>B</u><![CDATA[ hidden ]]> <strike>C</strike></p></body>",
         "A {+B+} [-C-]"),
    ],
)
def test_html_amendment_text_keeps_word_and_paragraph_boundaries(
    content: bytes, expected: str
) -> None:
    (block,) = _html(content, _MARKED)
    assert block.body == expected
    (default,) = _html(content, {"html_text_selector": "body"})
    assert documents._strip_amendment_markup(block.body).split() == default.body.split()


def test_html_amendment_ranges_span_paragraphs_while_paragraphs_follow_lxml() -> None:
    # lxml alone would close the <u> at the second <p>; html.parser alone would end
    # the second paragraph at </u>. The aligned parses keep both right.
    (block,) = _html(b"<body><p>a <u>b<p>c</u> d<p>e <strike>f</strike></body>", _MARKED)
    assert block.body == "a {+b+}\n\n{+c+} d\n\ne [-f-]"


def test_html_amendment_states_fail_when_the_two_parses_disagree() -> None:
    root = documents._html_soup(b"<html><body><p>x y</p></body></html>").body
    with pytest.raises(RuntimeError, match="disagree at non-space character 1"):
        documents._html_amendment_states(
            b"<html><body><p><u>x</u> z</p></body></html>",
            root,
            original_encoding=None,
            drop_selectors=[],
            extraction={"html_content_selector": "body", "html_amendment_markup": {"inserted_selector": "u"}},
        )
    with pytest.raises(RuntimeError, match="has text the lxml parse lacks"):
        documents._html_amendment_states(
            b"<html><body><p><u>x</u> y extra</p></body></html>",
            root,
            original_encoding=None,
            drop_selectors=[],
            extraction={"html_content_selector": "body", "html_amendment_markup": {"inserted_selector": "u"}},
        )


def test_explicit_html_encoding_decodes_strictly_and_keeps_the_default_parser() -> None:
    (block,) = _html(
        b"<html><body><p>WAC \xa7 388-450-0015 <u>new text</u></p></body></html>",
        {"html_encoding": "windows-1252", "html_amendment_markup": {"inserted_selector": "u"}},
    )
    assert block.body == "WAC § 388-450-0015 {+new text+}"
    # html_encoding alone changes decoding only, not lxml's paragraph handling.
    content = b"<html><body><p>One<p>Two \xa7<h2>Heading</h2><p>Three</body></html>"
    default = _html(content.replace(b"\xa7", b"&#167;"), None)
    encoded = _html(content, {"html_encoding": "windows-1252"})
    assert [(b.heading, b.body) for b in encoded] == [(b.heading, b.body) for b in default]
    assert encoded[0].body == "One\n\nTwo §"


@pytest.mark.parametrize(
    ("content", "encoding", "error"),
    [
        (b"<p>WAC \xa7 388</p>", "no-such-codec", "unknown html_encoding"),
        (b"<p>\x81 undefined in cp1252</p>", "windows-1252", "not valid windows-1252"),
    ],
)
def test_html_encoding_fails_instead_of_guessing(content: bytes, encoding: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        _html(content, {"html_encoding": encoding})


def test_html_encoding_is_refused_for_json_sources() -> None:
    with pytest.raises(ValueError, match="applies to HTML sources, not JSON"):
        documents._extract_json_html_blocks(
            b'{"html": "<p>x</p>"}',
            source_url="https://example.gov/rule",
            fallback_title="Rule",
            extraction={"json_html_field": "html", "html_encoding": "windows-1252"},
        )


def test_html_amendment_markup_false_is_the_default() -> None:
    content = b"<html><body><p>Plain <u>underlined</u> text.</p></body></html>"
    assert _html(content, {"html_amendment_markup": False}) == _html(content, None)


@pytest.mark.parametrize(
    ("content", "options", "error"),
    [
        (b"<p>Plain</p>", {"inserted_selector": "u"}, "did not match"),
        (b"<u>{+existing+}</u>", {"inserted_selector": "u"}, "already contains"),
        (
            b"<p><u><strike>Conflicting</strike></u></p>",
            {"deleted_selector": "strike", "inserted_selector": "u"},
            "text is both inserted and deleted",
        ),
        (
            b"<p><u class='x'>Twice</u></p>",
            {"deleted_selector": ".x", "inserted_selector": "u"},
            "node is both inserted and deleted",
        ),
        (b"<p><u>x</u></p>", {}, "requires deleted_selector or inserted_selector"),
        (b"<p><u>x</u></p>", "u", "requires deleted_selector or inserted_selector"),
        (b"<p><u>x</u></p>", {"underline_selector": "u"}, "requires deleted_selector"),
        (b"<p><u>x</u></p>", {"inserted_selector": " "}, "non-empty strings"),
    ],
)
def test_html_amendment_configuration_fails_closed(content: bytes, options, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        _html(content, {"html_amendment_markup": options})


def test_html_amendment_markup_refuses_segmented_and_webworks_html() -> None:
    options = {"html_amendment_markup": {"inserted_selector": "u"}}
    with pytest.raises(ValueError, match="supports only default HTML blocks"):
        _html(b"<p><u>x</u></p>", {**options, "segmentation": "anchor_range"})
    webworks = (
        b'<html><body><div id="page_content"><div class="Heading_Subject">Policy</div>'
        b'<div class="Body_Text_Public"><u>x</u></div></div></body></html>'
    )
    with pytest.raises(ValueError, match="does not support WebWorks HTML"):
        _html(webworks, options)


# DOCX -----------------------------------------------------------------------------


def _docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p>{paragraph}</w:p>" for paragraph in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def _run(text: str) -> str:
    return f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


_SYMBOL = '<w:r><w:sym w:font="Symbol" w:char="F0BE"/></w:r>'
_LABELED = {"segmentation": "labeled_sections", "section_heading_pattern": r"^§(?P<label>\d+)\.\s*(?P<heading>.+)$"}


def test_docx_symbol_map_writes_mapped_word_symbols() -> None:
    content = _docx([_run("§1. Terms"), _run("income") + _SYMBOL + _run("the value")])
    (default,) = documents._extract_docx_blocks(content, extraction=_LABELED)
    assert default.body == "incomethe value"  # the default skips <w:sym>
    (mapped,) = documents._extract_docx_blocks(
        content, extraction={**_LABELED, "docx_symbol_map": {"Symbol:f0be": "―"}}
    )
    assert mapped.body == "income―the value"


@pytest.mark.parametrize(
    ("extraction", "error"),
    [
        ({**_LABELED, "docx_symbol_map": {"Symbol:F0A7": "-"}}, "Symbol:F0BE is not in docx_symbol_map"),
        ({**_LABELED, "docx_symbol_map": {"F0BE": "-"}}, "keys look like"),
        ({**_LABELED, "docx_symbol_map": {}}, "non-empty mapping"),
        ({"docx_symbol_map": {"Symbol:F0BE": "-"}}, "supported only with labeled_sections"),
    ],
)
def test_docx_symbol_map_fails_closed(extraction: dict, error: str) -> None:
    content = _docx([_run("§1. Terms"), _run("income") + _SYMBOL + _run("the value")])
    with pytest.raises(ValueError, match=error):
        documents._extract_docx_blocks(content, extraction=extraction)


# Properties (seeded) --------------------------------------------------------------

_CASES = 3000


def _random_text(rng: random.Random, alphabet: str, length: int) -> str:
    return "".join(rng.choice(alphabet) for _ in range(length))


def test_property_rendered_markup_strips_back_to_the_normalized_text() -> None:
    rng = random.Random(20260928)
    for _ in range(_CASES):
        raw = _random_text(rng, "ab c.\n\t", rng.randint(0, 40))
        states = [rng.choice((None, None, _DELETED, _INSERTED)) for _ in raw]
        rendered = documents._render_amendment_markup(raw, states)
        assert documents._strip_amendment_markup(rendered.text) == documents._normalize_text(raw)
        assert rendered.text.count("[-") == rendered.text.count("-]") == rendered.deleted_runs
        assert rendered.text.count("{+") == rendered.text.count("+}") == rendered.inserted_runs


def _balanced(rng: random.Random) -> str:
    parts: list[str] = []
    for _ in range(rng.randint(0, 6)):
        parts.append(_random_text(rng, "ab c", rng.randint(0, 5)))
        if rng.random() < 0.5:
            parts.append("[" + _random_text(rng, "ab c\n", rng.randint(0, 6)) + "]")
    return "".join(parts)


def test_property_bracket_deletions_remove_brackets_and_split_anywhere() -> None:
    rng = random.Random(4006)
    for _ in range(_CASES):
        text = _balanced(rng)
        states: list[str | None] = [None] * len(text)
        chars, new_states, still_open = documents._pdf_bracket_deletions(
            list(text), states, [False] * len(text), open_deletion=False, page_number=1
        )
        assert "".join(chars) == text.replace("[", "").replace("]", "")
        assert still_open is False
        inside = False
        expected: list[str | None] = []
        for character in text:
            if character in "[]":
                inside = character == "["
                continue
            expected.append(_DELETED if inside and not character.isspace() else None)
        assert new_states == expected
        # Processing the text as two pages, with the open state carried across the
        # break, gives the same characters and states as one page.
        cut = rng.randint(0, len(text))
        first = documents._pdf_bracket_deletions(
            list(text[:cut]), states[:cut], [False] * cut, open_deletion=False, page_number=1
        )
        second = documents._pdf_bracket_deletions(
            list(text[cut:]),
            states[cut:],
            [False] * (len(text) - cut),
            open_deletion=first[2],
            page_number=2,
        )
        assert first[0] + second[0] == chars
        assert first[1] + second[1] == new_states
        assert second[2] is False


def _html_paragraphs(rng: random.Random) -> tuple[str, list[list[str]]]:
    """Random paragraphs of words, returned with the words each paragraph must read.

    Words are separated by random source whitespace; a word may be wrapped in an
    inline tag, or split by one mid-word. Paragraphs are <p>, <div>, <li> or bare
    text between blocks. The oracle is the generator's own word list.
    """
    html: list[str] = []
    expected: list[list[str]] = []
    previous_bare = False
    for _ in range(rng.randint(1, 4)):
        words: list[str] = []
        pieces: list[str] = []
        for _ in range(rng.randint(1, 4)):
            word = _random_text(rng, "ab", rng.randint(1, 3))
            tag = rng.choice(("u", "strike", "b", "span", "i", None))
            cut = rng.randint(1, len(word))
            if tag and cut < len(word) and rng.random() < 0.5:
                rendered = f"{word[:cut]}<{tag}>{word[cut:]}</{tag}>"
            elif tag:
                rendered = f"<{tag}>{word}</{tag}>"
            else:
                rendered = word
            if pieces:
                pieces.append(rng.choice((" ", "\n", "  ", " \t ")))
            pieces.append(rendered)
            words.append(word)
        container = rng.choice(("p", "div", "li", None if not previous_bare else "p"))
        body = "".join(pieces)
        html.append(f"<{container}>{body}</{container}>" if container else body)
        previous_bare = container is None
        expected.append(words)
    # Both selectors must match something.
    html.append("<p><u>z</u> <strike>y</strike></p>")
    expected.append(["z", "y"])
    return f"<html><body>{''.join(html)}</body></html>", expected


def test_property_html_markup_reads_the_generated_words_and_paragraphs() -> None:
    rng = random.Random(9622)
    for _ in range(_CASES // 3):
        content, expected = _html_paragraphs(rng)
        (block,) = _html(content.encode(), _MARKED)
        paragraphs = [
            documents._strip_amendment_markup(paragraph).split()
            for paragraph in block.body.split("\n\n")
        ]
        assert paragraphs == expected, content
        assert block.body.count("[-") == block.body.count("-]")
        assert block.body.count("{+") == block.body.count("+}")
