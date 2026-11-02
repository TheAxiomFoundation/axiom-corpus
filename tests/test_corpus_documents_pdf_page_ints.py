"""Strict positive-integer PDF extraction keys.

``_positive_int`` read every PDF page key and ``ocr_dpi`` with ``int(value)``, so
``start_page: true`` meant page 1, ``2.5`` was cut to page 2 and ``"3"`` was page
3. axiom-corpus#741 made the ``amendment_markup`` page keys strict; these tests
pin the same rule for the legacy ``start_page``/``end_page`` filters, each
``page_windows`` entry and ``ocr_dpi``, with the failing key named.

Invariants, checked for every input by the Hypothesis tests:

1. The parser returns ``default`` for ``None``, returns any other value only if it
   is an ``int`` (not a ``bool``) of at least 1, and then returns it unchanged.
2. Every other value raises ``ValueError`` naming the key and the value.
3. Differential: wherever the strict parser returns, the old lenient parser
   (``int(value)``, rejecting values below 1) returns the same page, so no
   accepted manifest value changes meaning.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import Any

import fitz  # type: ignore[import-untyped]
import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.documents import _positive_int

NOT_POSITIVE_INTS: list[Any] = [
    True,
    False,
    2.5,
    2.0,
    "3",
    "",
    0,
    -1,
    [1],
    {"page": 1},
    Decimal(2),
    Fraction(2, 1),
]


def _pdf(pages: int = 3) -> bytes:
    document = fitz.open()
    for number in range(1, pages + 1):
        document.new_page().insert_text((72, 72), f"{number}. Page {number} text.")
    content = document.tobytes()
    document.close()
    return content


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _lenient_positive_int(value: Any, *, default: int) -> int:
    """The parser before this change, kept as the differential reference."""
    if value is None:
        return default
    parsed = int(value)
    if parsed < 1:
        raise ValueError("page numbers must be positive")
    return parsed


# 1. Each key ---------------------------------------------------------------------


@pytest.mark.parametrize("value", NOT_POSITIVE_INTS, ids=repr)
@pytest.mark.parametrize("key", ["start_page", "end_page"])
def test_legacy_page_filters_reject_anything_but_a_positive_int(key: str, value: Any) -> None:
    with pytest.raises(ValueError) as raised:
        documents_module._filtered_pdf_lines(_pdf(), extraction={key: value})

    assert str(raised.value) == f"{key} must be a positive integer page number, not {value!r}"


@pytest.mark.parametrize("value", NOT_POSITIVE_INTS, ids=repr)
@pytest.mark.parametrize("key", ["start_page", "end_page"])
def test_page_windows_name_the_window_and_key(key: str, value: Any) -> None:
    window = {"start_page": 3, "end_page": 3, key: value}
    extraction = {"page_windows": [{"start_page": 1, "end_page": 1}, window]}

    with pytest.raises(ValueError) as raised:
        documents_module._filtered_pdf_lines(_pdf(), extraction=extraction)

    assert str(raised.value) == (
        f"page_windows[1].{key} must be a positive integer page number, not {value!r}"
    )


def test_a_page_window_missing_a_bound_still_says_so() -> None:
    with pytest.raises(ValueError, match="requires start_page and end_page"):
        documents_module._filtered_pdf_lines(
            _pdf(), extraction={"page_windows": [{"start_page": 2, "end_page": None}]}
        )


@pytest.mark.parametrize("value", NOT_POSITIVE_INTS, ids=repr)
@pytest.mark.parametrize("ocr", [{}, {"ocr": False}, {"ocr": True}], ids=repr)
@pytest.mark.parametrize(
    "segmentation", [None, "single_block", "numbered_sections", "labeled_sections"]
)
def test_ocr_dpi_is_checked_with_every_segmentation(
    segmentation: str | None, ocr: dict[str, bool], value: Any
) -> None:
    """The pages have text, so OCR never runs: the check must not wait for a scan.

    It must not depend on the ``ocr`` switch either: with OCR absent or off,
    ``ocr_dpi`` is still a PDF extraction key and a bad value still fails.
    """
    extraction: dict[str, Any] = {**ocr, "ocr_dpi": value}
    if segmentation is not None:
        extraction["segmentation"] = segmentation
    if segmentation == "labeled_sections":
        extraction["section_label_pattern"] = r"^(?P<label>\d+)\."

    with pytest.raises(ValueError) as raised:
        documents_module._extract_pdf_blocks(_pdf(), extraction=extraction)

    assert str(raised.value) == f"ocr_dpi must be a positive integer DPI, not {value!r}"


def test_amendment_markup_page_messages_are_unchanged() -> None:
    with pytest.raises(ValueError) as raised:
        documents_module._extract_pdf_blocks(
            _pdf(), extraction={"amendment_markup": {"start_page": 2.0}}
        )

    assert str(raised.value) == (
        "amendment_markup start_page must be a positive integer page number, not 2.0"
    )


# 2. Values a YAML manifest really produces --------------------------------------


@pytest.mark.parametrize(
    ("yaml_value", "parsed"),
    [
        ("true", True),
        ("yes", True),  # YAML 1.1 boolean
        ("on", True),  # YAML 1.1 boolean
        ("2.5", 2.5),
        ("3.0", 3.0),
        ('"3"', "3"),
        ("1e1", "1e1"),  # PyYAML reads an exponent without a dot as a string
    ],
)
def test_yaml_scalars_that_are_not_integers_fail(yaml_value: str, parsed: Any) -> None:
    extraction = yaml.safe_load(f"segmentation: single_block\nstart_page: {yaml_value}\n")
    assert extraction["start_page"] == parsed

    with pytest.raises(ValueError, match=r"^start_page must be a positive integer page number"):
        documents_module._extract_pdf_blocks(_pdf(), extraction=extraction)


def test_yaml_integers_still_select_pages() -> None:
    extraction = yaml.safe_load(
        "segmentation: single_block\nstart_page: 2\nend_page: 0x3\nocr_dpi: 300\n"
    )

    (block,) = documents_module._extract_pdf_blocks(_pdf(4), extraction=extraction)

    assert block.body == "2. Page 2 text.\n\n3. Page 3 text."


def test_page_windows_still_select_pages() -> None:
    extraction = {
        "segmentation": "single_block",
        "page_windows": [{"start_page": 1, "end_page": 1}, {"start_page": 3, "end_page": 4}],
    }

    (block,) = documents_module._extract_pdf_blocks(_pdf(4), extraction=extraction)

    assert block.body == "1. Page 1 text.\n\n3. Page 3 text.\n\n4. Page 4 text."


# 3. Invariants for every input --------------------------------------------------

_ANY_VALUE = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**70), max_value=2**70),
    st.floats(allow_nan=True, allow_infinity=True),
    st.text(max_size=6),
    st.decimals(allow_nan=False, allow_infinity=False),
    st.fractions(),
    st.lists(st.integers(), max_size=2),
)


@given(value=_ANY_VALUE, default=st.integers(min_value=0, max_value=500))
def test_property_returns_only_unchanged_positive_ints(value: Any, default: int) -> None:
    try:
        result = _positive_int(value, key="the_key", default=default)
    except ValueError as error:
        assert value is not None
        assert not _is_positive_int(value)
        assert str(error) == f"the_key must be a positive integer page number, not {value!r}"
        return
    if value is None:
        assert result == default
    else:
        assert _is_positive_int(value)
        assert type(result) is int and result == value


@given(value=_ANY_VALUE, default=st.integers(min_value=0, max_value=500))
def test_property_strict_parser_agrees_with_the_lenient_one_where_it_accepts(
    value: Any, default: int
) -> None:
    try:
        strict = _positive_int(value, key="the_key", default=default)
    except ValueError:
        return
    assert _lenient_positive_int(value, default=default) == strict
