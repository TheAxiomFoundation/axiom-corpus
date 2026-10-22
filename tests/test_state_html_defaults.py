"""Explicit expectations for all 45 constructs in the round-5 markup probe.

CSS-hidden operative text is intentionally retained. These assertions describe
the source structures independently of the production element exclusion list.
"""

import pytest
from bs4 import BeautifulSoup, Tag

from axiom_corpus.corpus.state_adapters.maine import parse_maine_section
from axiom_corpus.corpus.states import _ohio_laws_body_text
from tests.test_state_nonoperative_text import _extract, _visible_gap

NOISE = "Scheduled maintenance. Please try again later."
OPERATIVE = "A taxpayer shall receive a credit of 12 dollars."

# The third field explicitly states whether the construct supplies body text.
CONSTRUCTS = [
    ("control-visible-p", f"<p>{NOISE}</p>", NOISE),
    ("style-display-none-p", f'<p style="display:none">{NOISE}</p>', NOISE),
    ("style-display-none-div", f'<div style="display: none;">{NOISE}</div>', NOISE),
    ("style-visibility-hidden", f'<p style="visibility:hidden">{NOISE}</p>', NOISE),
    ("class-hidden-bootstrap", f'<p class="hidden d-none">{NOISE}</p>', NOISE),
    ("class-sr-only", f'<span class="sr-only visually-hidden">{NOISE}</span>', NOISE),
    ("title-in-body", f"<title>{NOISE}</title>", None),
    ("title-in-p", f"<p><title>{NOISE}</title></p>", None),
    ("dialog-closed", f"<dialog><p>{NOISE}</p></dialog>", None),
    ("details-closed-body", f"<details><summary></summary><p>{NOISE}</p></details>", None),
    ("datalist", f"<datalist><option>{NOISE}</option></datalist>", None),
    ("noembed", f"<noembed>{NOISE}</noembed>", None),
    ("noframes", f"<noframes>{NOISE}</noframes>", None),
    ("svg-title", f"<svg><title>{NOISE}</title></svg>", None),
    ("svg-desc", f"<svg><desc>{NOISE}</desc></svg>", None),
    (
        "math-annotation",
        f'<math><annotation encoding="text/plain">{NOISE}</annotation></math>',
        None,
    ),
    ("video-fallback", f"<video>{NOISE}</video>", None),
    ("audio-fallback", f"<audio>{NOISE}</audio>", None),
    ("canvas-fallback", f"<canvas>{NOISE}</canvas>", None),
    ("select-option", f"<select><option>{NOISE}</option></select>", NOISE),
    ("textarea", f"<textarea>{NOISE}</textarea>", NOISE),
    ("rp", f"<ruby><rp>{NOISE}</rp></ruby>", None),
    # RubyText is a special BeautifulSoup string, excluded by the existing rule.
    ("rt", f"<ruby>x<rt>{NOISE}</rt></ruby>", "x"),
    ("template", f"<template><p>{NOISE}</p></template>", None),
    ("hidden-attr", f"<p hidden>{NOISE}</p>", None),
    ("hidden-until-found", f'<p hidden="until-found">{NOISE}</p>', None),
    ("aria-hidden-TRUE", f'<p aria-hidden=" TRUE ">{NOISE}</p>', None),
    ("head-in-body", f"<head><p>{NOISE}</p></head>", None),
    ("comment", f"<!-- {NOISE} -->", None),
    ("cdata", f"<![CDATA[{NOISE}]]>", None),
    ("pi", f'<?php echo "{NOISE}"; ?>', None),
    ("zero-width-only", "<p>\u200b\u200c\u200d\u2060\ufeff</p>", None),
    ("soft-hyphen-only", "<p>\u00ad</p>", None),
    ("punctuation-only", "<p>.</p>", "."),
    ("nbsp-only", "<p>\u00a0&nbsp;</p>", None),
    ("input-hidden", f'<input type="hidden" value="{NOISE}">', None),
    ("img-alt", f'<img alt="{NOISE}">', None),
    ("frameset", f"<frameset><frame>{NOISE}</frame></frameset>", None),
    ("iframe", f"<iframe>{NOISE}</iframe>", None),
    ("object", f"<object>{NOISE}</object>", None),
    # In HTML, embed is void; the following text is its visible sibling.
    ("embed", f"<embed>{NOISE}</embed>", NOISE),
    ("applet", f"<applet>{NOISE}</applet>", NOISE),
    ("xmp", f"<xmp>{NOISE}</xmp>", NOISE),
    (
        "plaintext",
        f"<plaintext>{NOISE}",
        # Plaintext consumes all subsequent markup as literal visible text.
        {"maine": f"{NOISE}</div></div></div>", "ohio": f"{NOISE}</section>"},
    ),
    ("base-link-meta", f'<meta content="{NOISE}"><link href="x">', None),
]


def _read(markup, jurisdiction):
    if jurisdiction == "maine":
        html = (
            '<div class="MRSSection status_current">'
            '<h3 class="heading_section">§5219-S. Earned income credit</h3>'
            f'<div class="MRSSubSection"><div class="mrs-text">{markup}</div></div></div>'
        )
        try:
            return parse_maine_section(html).body
        except ValueError as exc:
            assert "lacks operative text or a status body" in str(exc)
            return None
    root = BeautifulSoup(f'<section class="laws-body">{markup}</section>', "html.parser").section
    assert isinstance(root, Tag)
    return _ohio_laws_body_text(root)


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
@pytest.mark.parametrize(("name", "markup", "expected"), CONSTRUCTS, ids=[c[0] for c in CONSTRUCTS])
def test_all_reviewer_markup_constructs(jurisdiction, name, markup, expected):
    if isinstance(expected, dict):
        expected = expected[jurisdiction]
    assert _read(markup, jurisdiction) == expected


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
@pytest.mark.parametrize("failed_index", [0, 1])
@pytest.mark.parametrize(
    ("name", "markup", "expected"),
    [case for case in CONSTRUCTS if case[2] is None],
    ids=[case[0] for case in CONSTRUCTS if case[2] is None],
)
def test_default_hidden_only_section_remains_inventory_gap(
    tmp_path, jurisdiction, failed_index, name, markup, expected
):
    store, report, failed_section = _extract(
        tmp_path, jurisdiction, markup, failed_index=failed_index
    )
    _visible_gap(store, report, jurisdiction, failed_section)


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        (f"<dialog open><p>{OPERATIVE}</p></dialog>", OPERATIVE),
        (f"<details><summary>{OPERATIVE}</summary><p>{NOISE}</p></details>", OPERATIVE),
        (f"<details><p>{NOISE}</p><summary>{OPERATIVE}</summary></details>", OPERATIVE),
        (f"<details>{NOISE}<summary>{OPERATIVE}</summary>{NOISE}</details>", OPERATIVE),
        (f"<details><summary>{OPERATIVE}</summary><summary>{NOISE}</summary></details>", OPERATIVE),
        (f"<details><div><summary>{NOISE}</summary></div></details>", None),
        (f"<details><summary hidden>{NOISE}</summary></details>", None),
        (
            f"<details open><summary>Credit</summary><p>{OPERATIVE}</p></details>",
            f"Credit {OPERATIVE}",
        ),
        (
            f"<math><semantics><mi>x</mi><annotation-xml>{NOISE}</annotation-xml></semantics></math>",
            "x",
        ),
        (f"<svg><desc>{NOISE}</desc><text>{OPERATIVE}</text></svg>", OPERATIVE),
    ],
)
def test_disclosures_and_graphics_keep_only_displayed_content(jurisdiction, markup, expected):
    body = _read(markup, jurisdiction)
    assert (" ".join(body.split()) if body is not None else None) == expected


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
@pytest.mark.parametrize(
    "ancestor",
    [
        "<dialog>{body}</dialog>",
        "<details><summary>Caption</summary>{body}</details>",
        "<details><summary>Caption</summary><summary>{body}</summary></details>",
        "<details><div>{body}</div></details>",
        "<svg><desc>{body}</desc></svg>",
        "<math><annotation-xml>{body}</annotation-xml></math>",
        "<video>{body}</video>",
    ],
)
def test_default_hidden_ancestors_do_not_expose_body(jurisdiction, ancestor):
    classname = "MRSSection" if jurisdiction == "maine" else "laws-body"
    soup = BeautifulSoup(
        ancestor.format(body=f'<div class="{classname}">{OPERATIVE}</div>'), "html.parser"
    )
    if jurisdiction == "maine":
        with pytest.raises(ValueError, match="lacks operative text or a status body"):
            parse_maine_section(str(soup))
    else:
        assert _ohio_laws_body_text(soup.select_one(".laws-body")) is None


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
@pytest.mark.parametrize(
    "char",
    [
        "\u200b",
        "\u200c",
        "\u200d",
        "\u2060",
        "\ufeff",
        "\u00ad",
        "\u202e",
        "\U000e0001",
        "\u034f",
        "\u17b4",
        "\u180b",
        "\ufe0f",
        "\U000e0100",
        "\U000e01ef",
    ],
)
def test_format_only_body_is_empty_but_inline_formatting_is_preserved(jurisdiction, char):
    assert _read(f"<p>\t {char} \n</p>", jurisdiction) is None
    text = f"Tax{char}payer shall receive a credit."
    assert _read(f"<p>{text}</p>", jurisdiction) == text


@pytest.mark.parametrize("jurisdiction", ["maine", "ohio"])
def test_visible_combining_mark_is_not_discarded_as_formatting(jurisdiction):
    assert _read("<p>\u0301</p>", jurisdiction) == "\u0301"


@pytest.mark.parametrize(
    "text", ["\u200b\u200c\u200d\u2060\ufeff", "\u034f", "\ufe0f", "\U000e0100"]
)
def test_maine_utf8_format_only_bytes_without_charset_do_not_become_body(text):
    html = (
        f'<div class="MRSSection"><h3 class="heading_section">§1. Example</h3><p>{text}</p></div>'
    )
    for value in (html, html.encode("utf-8")):
        with pytest.raises(ValueError, match="lacks operative text or a status body"):
            parse_maine_section(value)
