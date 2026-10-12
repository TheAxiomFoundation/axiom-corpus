"""PDF extraction options for amended rule text: amendment markup, block order, ActualText.

The options are opt-in manifest ``extraction`` keys (``amendment_markup``,
``sort_blocks``, ``ignore_actual_text``); without them the per-page PDF text is
unchanged.
"""

from __future__ import annotations

from typing import Any

import fitz  # type: ignore[import-untyped]
import pytest

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.documents import _normalize_text

FONT = "helv"


def _marked_pdf(lines: list[tuple[float, list[tuple[Any, ...]]]], *, size: float = 12.0) -> bytes:
    """Build a one-page PDF whose runs carry drawn strike-through or underline rules.

    Each run is ``(text, state)`` or ``(text, state, font_size, baseline_shift)``;
    ``state`` is ``None``, ``"struck"`` or ``"underlined"``. Rules are drawn the
    way the source PDFs draw them: a strike as a stroked line through the
    lower-case letters, an underline as a thin filled rectangle below the
    baseline.
    """
    document = fitz.open()
    page = document.new_page()
    for baseline, runs in lines:
        x = 72.0
        for text, state, *rest in runs:
            font_size = rest[0] if rest else size
            y = baseline + (rest[1] if len(rest) > 1 else 0.0)
            page.insert_text((x, y), text, fontname=FONT, fontsize=font_size)
            width = fitz.get_text_length(text, fontname=FONT, fontsize=font_size)
            if state == "struck":
                page.draw_line(
                    (x, y - 0.25 * font_size), (x + width, y - 0.25 * font_size), width=0.6
                )
            elif state == "underlined":
                page.draw_rect(
                    fitz.Rect(x, y + 0.1 * font_size, x + width, y + 0.15 * font_size),
                    color=None,
                    fill=(0, 0, 0),
                )
            x += width
    content = document.tobytes()
    document.close()
    return content


def _pages(content: bytes, extraction: dict[str, Any]) -> list[documents_module._DocumentBlock]:
    return list(documents_module._extract_pdf_blocks(content, extraction=extraction))


def test_amendment_markup_wraps_struck_and_underlined_runs() -> None:
    content = _marked_pdf(
        [
            (
                100,
                [
                    ("Keep ", None),
                    ("old words", "struck"),
                    (" and ", None),
                    ("new words", "underlined"),
                    (".", None),
                ],
            ),
            (114, [("(", None), ("h", "struck"), ("g", "underlined"), (") next", None)]),
        ]
    )

    (page,) = _pages(content, {"amendment_markup": True})

    assert page.body == "Keep [-old words-] and {+new words+}. ([-h-]{+g+}) next"
    assert page.metadata["amendment_markup"] == {
        "notation": "wdiff",
        "deleted": "[-text-]",
        "inserted": "{+text+}",
        "deleted_source_markup": "strike-through",
        "inserted_source_markup": "underline",
        "deleted_runs": 2,
        "inserted_runs": 2,
    }


def test_amendment_markup_joins_a_run_across_lines_and_keeps_paragraph_text() -> None:
    content = _marked_pdf(
        [
            (100, [("(a) ", None), ("The deduction is the amount", "struck")]),
            (114, [("actually paid.", "struck")]),
        ]
    )

    (page,) = _pages(content, {"amendment_markup": True})

    assert page.body == "(a) [-The deduction is the amount actually paid.-]"


def test_amendment_markup_classifies_raised_superscripts() -> None:
    # "18th" with a raised, smaller "th" that has its own strike at its own
    # height (as CDSS ACL 06-31 draws it).
    content = _marked_pdf(
        [
            (
                100,
                [
                    ("attains their ", None),
                    ("18", "struck"),
                    ("th", "struck", 8.0, -4.0),
                    (" birthday", None),
                ],
            )
        ]
    )

    (page,) = _pages(content, {"amendment_markup": True})

    assert page.body == "attains their [-18th-] birthday"


def test_amendment_markup_only_changes_delimiters() -> None:
    content = _marked_pdf(
        [
            (100, [("Plain ", None), ("struck text", "struck"), (" plain", None)]),
            (114, [("underlined text", "underlined")]),
        ]
    )

    (plain,) = _pages(content, {})
    (marked,) = _pages(content, {"amendment_markup": True})

    assert "amendment_markup" not in plain.metadata
    assert plain.body == "Plain struck text plain underlined text"
    assert documents_module._strip_amendment_markup(marked.body) == plain.body


def test_default_page_text_is_unchanged_by_the_new_code_path() -> None:
    content = _marked_pdf([(100, [("Plain ", None), ("struck text", "struck")])])

    (page,) = _pages(content, {})
    with fitz.open(stream=content, filetype="pdf") as document:
        expected = _normalize_text(document[0].get_text("text"))

    assert page.body == expected


def test_amendment_markup_page_range_leaves_other_pages_unmarked() -> None:
    document = fitz.open()
    for page_number in (1, 2):
        page = document.new_page()
        page.insert_text((72, 100), f"Emphasis on page {page_number}", fontname=FONT, fontsize=12)
        width = fitz.get_text_length(f"Emphasis on page {page_number}", fontname=FONT, fontsize=12)
        page.draw_rect(fitz.Rect(72, 101.2, 72 + width, 101.8), color=None, fill=(0, 0, 0))
    content = document.tobytes()

    first, second = _pages(content, {"amendment_markup": {"start_page": 2}})

    assert first.body == "Emphasis on page 1"
    assert "amendment_markup" not in first.metadata
    assert second.body == "{+Emphasis on page 2+}"
    assert second.metadata["amendment_markup"]["inserted_runs"] == 1


def test_amendment_markup_typographic_underlines_are_not_insertions() -> None:
    content = _marked_pdf(
        [
            (
                100,
                [
                    ("order in ", None),
                    ("Jones", "underlined"),
                    (" v. ", None),
                    ("Yeutter", "underlined"),
                    ("; and ", None),
                    ("new text", "underlined"),
                ],
            )
        ]
    )

    (page,) = _pages(
        content,
        {"amendment_markup": {"typographic_underlines": ["Jones v. Yeutter"]}},
    )

    assert page.body == "order in Jones v. Yeutter; and {+new text+}"
    assert page.metadata["amendment_markup"]["inserted_runs"] == 1
    assert page.metadata["amendment_markup"]["typographic_underlines"] == {"Jones v. Yeutter": 1}


def test_amendment_markup_rejects_a_typographic_underline_that_never_occurs() -> None:
    content = _marked_pdf([(100, [("Jones", "underlined"), (" v. Yeutter", None)])])

    with pytest.raises(ValueError, match="typographic_underlines not found"):
        _pages(content, {"amendment_markup": {"typographic_underlines": ["Hamilton v. Lyng"]}})


def test_amendment_markup_rejects_text_that_already_uses_the_delimiters() -> None:
    content = _marked_pdf([(100, [("see [-1] and ", None), ("new", "underlined")])])

    with pytest.raises(ValueError, match="already contains amendment markup delimiters"):
        _pages(content, {"amendment_markup": True})


def test_amendment_markup_rejects_text_both_struck_and_underlined() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "both", fontname=FONT, fontsize=12)
    width = fitz.get_text_length("both", fontname=FONT, fontsize=12)
    page.draw_line((72, 97), (72 + width, 97), width=0.6)
    page.draw_rect(fitz.Rect(72, 101.2, 72 + width, 101.8), color=None, fill=(0, 0, 0))

    with pytest.raises(ValueError, match="both struck through and underlined"):
        _pages(document.tobytes(), {"amendment_markup": True})


def test_amendment_markup_ignores_white_and_thick_rules() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "plain", fontname=FONT, fontsize=12)
    width = fitz.get_text_length("plain", fontname=FONT, fontsize=12)
    page.draw_line((72, 97), (72 + width, 97), width=0.6, color=(1, 1, 1))
    page.draw_rect(fitz.Rect(72, 100.5, 72 + width, 103.5), color=None, fill=(0, 0, 0))

    (block,) = _pages(document.tobytes(), {"amendment_markup": True})

    assert block.body == "plain"


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"start_page": 3, "end_page": 2}, "end_page must not precede start_page"),
        ({"pages": "1-2"}, "unknown amendment_markup keys"),
        ({"typographic_underlines": "Jones v. Yeutter"}, "must be a list"),
        ({"typographic_underlines": [" padded"]}, "must be a list"),
        ("yes", "must be true or a mapping"),
    ],
)
def test_amendment_markup_config_is_validated(config: Any, message: str) -> None:
    content = _marked_pdf([(100, [("text", None)])])

    with pytest.raises(ValueError, match=message):
        _pages(content, {"amendment_markup": config})


@pytest.mark.parametrize("key", ["amendment_markup", "sort_blocks"])
def test_layered_options_require_page_segmentation(key: str) -> None:
    content = _marked_pdf([(100, [("text", None)])])

    with pytest.raises(ValueError, match="support only the default per-page"):
        _pages(content, {key: True, "segmentation": "single_block"})


@pytest.mark.parametrize("key", ["ocr", "text_replacements"])
def test_layered_options_reject_ocr_and_text_replacements(key: str) -> None:
    content = _marked_pdf([(100, [("text", None)])])
    extraction: dict[str, Any] = {"sort_blocks": True}
    extraction[key] = {"a": "b"} if key == "text_replacements" else True

    with pytest.raises(ValueError, match="do not support"):
        _pages(content, extraction)


def test_sort_blocks_places_a_box_drawn_last_where_it_is_printed() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 100), "26. Child support payments are excluded.", fontname=FONT, fontsize=11
    )
    page.insert_text((72, 200), "V. Next heading", fontname=FONT, fontsize=11)
    page.draw_rect(fitz.Rect(90, 130, 400, 170), color=(0, 0, 0), fill=(0.8, 0.8, 0.8))
    page.insert_text((100, 150), "Exception: boxed note.", fontname=FONT, fontsize=11)
    content = document.tobytes()

    (content_order,) = _pages(content, {})
    (printed_order,) = _pages(content, {"sort_blocks": True})

    assert content_order.body == (
        "26. Child support payments are excluded. V. Next heading Exception: boxed note."
    )
    assert printed_order.body == (
        "26. Child support payments are excluded. Exception: boxed note. V. Next heading"
    )


def _pdf_with_empty_actual_text() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "Hidden by tag.", fontname=FONT, fontsize=11)
    page.insert_text((72, 130), "Always visible.", fontname=FONT, fontsize=11)
    hidden = b"Hidden by tag.".hex().encode()
    for xref in page.get_contents():
        stream = document.xref_stream(xref)
        start = stream.find(hidden)
        if start < 0:
            continue
        begin = stream.rfind(b"BT", 0, start)
        end = stream.find(b"ET", start) + 2
        stream = (
            stream[:begin]
            + b"/Span <</ActualText ()>> BDC\n"
            + stream[begin:end]
            + b"\nEMC"
            + stream[end:]
        )
        document.update_stream(xref, stream)
        break
    else:  # pragma: no cover - fixture guard
        raise AssertionError("hidden text not found in the content stream")
    content = document.tobytes()
    document.close()
    return content


@pytest.mark.parametrize("segmentation", [None, "single_block"])
def test_ignore_actual_text_recovers_text_an_empty_actual_text_hides(
    segmentation: str | None,
) -> None:
    content = _pdf_with_empty_actual_text()
    extraction: dict[str, Any] = {}
    if segmentation is not None:
        extraction["segmentation"] = segmentation

    (default,) = _pages(content, extraction)
    (recovered,) = _pages(content, {**extraction, "ignore_actual_text": True})

    assert default.body == "Always visible."
    assert recovered.body == "Hidden by tag. Always visible."


def test_ignore_actual_text_applies_to_the_layered_path() -> None:
    content = _pdf_with_empty_actual_text()

    (page,) = _pages(content, {"sort_blocks": True, "ignore_actual_text": True})

    assert page.body == "Hidden by tag. Always visible."
