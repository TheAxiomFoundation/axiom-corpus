"""PDF page filters are read only by the segmentations that support them.

``_filtered_pdf_styled_lines`` reads seven page filters (``page_windows``,
``start_page``, ``end_page``, ``start_after_pattern``, ``drop_lines``,
``drop_line_patterns`` and ``page_header_patterns``) for the ``single_block``,
``numbered_sections`` and ``labeled_sections`` segmentations. The default
per-page segmentation emits every page and used to ignore them, so a manifest
could ask for pages 182 to 186 and get all 743. It now refuses them.

Invariants, checked for every input by the Hypothesis tests:

1. Under any segmentation other than the three, an extraction that sets at least
   one page filter raises ``ValueError`` naming exactly the filters set, in
   ``_SINGLE_BLOCK_PDF_FILTER_KEYS`` order, and the segmentation.
2. A page filter set to ``None`` is not set: the default extraction is the same
   as with no extraction mapping at all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]
import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.documents import (
    _PDF_PAGE_FILTER_SEGMENTATIONS,
    _SINGLE_BLOCK_PDF_FILTER_KEYS,
)

REPO = Path(__file__).resolve().parents[1]

# A valid value for each page filter, all of which keep pages 2 and 3.
VALID_FILTERS: dict[str, Any] = {
    "page_windows": [{"start_page": 2, "end_page": 3}],
    "start_page": 2,
    "end_page": 3,
    "start_after_pattern": r"^Body text 1\.$",
    "drop_lines": ["Running header"],
    "drop_line_patterns": [r"^Running header$"],
    "page_header_patterns": [r"^Running header$"],
}


def _pdf(pages: int = 3) -> bytes:
    document = fitz.open()
    for number in range(1, pages + 1):
        document.new_page().insert_text(
            (72, 72),
            "\n".join(["Running header", f"10{number}. HEADING {number}", f"Body text {number}."]),
        )
    content = document.tobytes()
    document.close()
    return content


PDF = _pdf()


def _expected_message(keys: list[str], segmentation: object) -> str:
    return (
        f"the default per-page PDF segmentation (used for segmentation={segmentation!r}) "
        f"does not read page filters, so {', '.join(keys)} would be ignored; "
        "only the single_block, numbered_sections and labeled_sections "
        "segmentations read them"
    )


def _blocks(extraction: dict[str, Any] | None) -> list[tuple[Any, ...]]:
    return [
        (block.kind, block.ordinal, block.heading, block.body, block.metadata)
        for block in documents_module._extract_pdf_blocks(PDF, extraction=extraction)
    ]


def test_the_valid_values_cover_every_page_filter() -> None:
    assert set(VALID_FILTERS) == set(_SINGLE_BLOCK_PDF_FILTER_KEYS)


# 1. Each filter ------------------------------------------------------------------


@pytest.mark.parametrize("key", _SINGLE_BLOCK_PDF_FILTER_KEYS)
def test_the_default_segmentation_rejects_each_page_filter(key: str) -> None:
    with pytest.raises(ValueError) as raised:
        documents_module._extract_pdf_blocks(PDF, extraction={key: VALID_FILTERS[key]})

    assert str(raised.value) == _expected_message([key], None)


def test_the_error_names_every_filter_set_in_canonical_order() -> None:
    extraction = {"end_page": 3, "drop_lines": ["x"], "start_page": 2}

    with pytest.raises(ValueError) as raised:
        documents_module._extract_pdf_blocks(PDF, extraction=extraction)

    assert str(raised.value) == _expected_message(["start_page", "end_page", "drop_lines"], None)


def test_an_unrecognized_segmentation_is_named() -> None:
    """An unknown segmentation falls through to the per-page path; say which one it was."""
    with pytest.raises(ValueError) as raised:
        documents_module._extract_pdf_blocks(
            PDF, extraction={"segmentation": "labelled_sections", "start_page": 2}
        )

    assert str(raised.value) == _expected_message(["start_page"], "labelled_sections")


@pytest.mark.parametrize("value", [[], "", 0, False])
def test_an_empty_value_still_counts_as_set(value: object) -> None:
    """Only ``None`` means unset, as for the ``single_block`` filtered path."""
    with pytest.raises(ValueError, match="does not read page filters, so drop_lines"):
        documents_module._extract_pdf_blocks(PDF, extraction={"drop_lines": value})


def test_a_filter_set_to_none_is_not_set() -> None:
    extraction = dict.fromkeys(_SINGLE_BLOCK_PDF_FILTER_KEYS)

    assert _blocks(extraction) == _blocks(None)
    assert [block[2] for block in _blocks(extraction)] == ["Page 1", "Page 2", "Page 3"]


def test_sort_blocks_does_not_lift_the_rule() -> None:
    """``sort_blocks`` runs on the default per-page path, so the filters are still refused."""
    with pytest.raises(ValueError) as raised:
        documents_module._extract_pdf_blocks(PDF, extraction={"sort_blocks": True, "end_page": 3})

    assert str(raised.value) == _expected_message(["end_page"], None)


def test_the_amendment_markup_page_range_is_not_a_page_filter() -> None:
    """``amendment_markup`` keeps its own nested start_page and end_page."""
    blocks = documents_module._extract_pdf_blocks(
        PDF, extraction={"amendment_markup": {"start_page": 2, "end_page": 3}}
    )

    assert [block.metadata["page_number"] for block in blocks] == [1, 2, 3]


# 2. The segmentations that read the filters --------------------------------------


SEGMENTATION_CONFIGS: dict[str, dict[str, Any]] = {
    "single_block": {"segmentation": "single_block"},
    "numbered_sections": {"segmentation": "numbered_sections"},
    "labeled_sections": {
        "segmentation": "labeled_sections",
        "section_heading_pattern": r"^(?P<label>10\d)\. (?P<heading>.+)$",
    },
}


def test_every_supported_segmentation_has_a_config() -> None:
    assert tuple(SEGMENTATION_CONFIGS) == _PDF_PAGE_FILTER_SEGMENTATIONS


@pytest.mark.parametrize("key", _SINGLE_BLOCK_PDF_FILTER_KEYS)
@pytest.mark.parametrize("segmentation", _PDF_PAGE_FILTER_SEGMENTATIONS)
def test_supported_segmentations_still_read_each_filter(segmentation: str, key: str) -> None:
    extraction = {**SEGMENTATION_CONFIGS[segmentation], key: VALID_FILTERS[key]}

    blocks = documents_module._extract_pdf_blocks(PDF, extraction=extraction)

    text = "\n".join(block.body for block in blocks)
    assert "Body text 2." in text
    assert "Body text 3." in text
    if key in {"page_windows", "start_page", "start_after_pattern"}:
        assert "Body text 1." not in text
    if key in {"drop_lines", "drop_line_patterns", "page_header_patterns"}:
        assert "Running header" not in text


# 3. Properties -------------------------------------------------------------------

FILTER_SUBSETS = st.sets(st.sampled_from(_SINGLE_BLOCK_PDF_FILTER_KEYS))
UNSUPPORTED_SEGMENTATIONS = st.one_of(
    st.none(), st.text(max_size=20).filter(lambda s: s not in _PDF_PAGE_FILTER_SEGMENTATIONS)
)


@settings(max_examples=200, deadline=None)
@given(keys=FILTER_SUBSETS.filter(bool), segmentation=UNSUPPORTED_SEGMENTATIONS)
def test_property_any_filter_under_an_unsupported_segmentation_is_named(
    keys: set[str], segmentation: str | None
) -> None:
    extraction: dict[str, Any] = {key: VALID_FILTERS[key] for key in keys}
    if segmentation is not None:
        extraction["segmentation"] = segmentation
    expected = [key for key in _SINGLE_BLOCK_PDF_FILTER_KEYS if key in keys]

    with pytest.raises(ValueError) as raised:
        documents_module._extract_pdf_blocks(PDF, extraction=extraction)

    assert str(raised.value) == _expected_message(expected, segmentation)


@settings(max_examples=30, deadline=None)
@given(keys=FILTER_SUBSETS)
def test_property_filters_set_to_none_change_nothing(keys: set[str]) -> None:
    assert _blocks(dict.fromkeys(keys)) == _blocks(None)


# 4. Tracked manifests ------------------------------------------------------------


def _documents(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        payload = yaml.load(handle, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    if not isinstance(payload, dict) or not isinstance(payload.get("documents"), list):
        return []
    return [row for row in payload["documents"] if isinstance(row, dict)]


def test_no_tracked_pdf_manifest_sets_a_filter_its_segmentation_ignores() -> None:
    """Catch the manifest before an ingest does; a source with no format may be a PDF.

    Only a file that names a page filter can set one, so the others are not parsed.
    """
    filtered_pdf_sources = 0
    offenders = []
    manifests = (REPO / "manifests").rglob("*")
    for path in sorted(p for p in manifests if p.suffix in {".yaml", ".yml"}):
        text = path.read_text(encoding="utf-8")
        if not any(key in text for key in _SINGLE_BLOCK_PDF_FILTER_KEYS):
            continue
        for row in _documents(path):
            extraction = row.get("extraction")
            if not isinstance(extraction, dict):
                continue
            if str(row.get("source_format") or "pdf").lower() != "pdf":
                continue
            keys = [k for k in _SINGLE_BLOCK_PDF_FILTER_KEYS if extraction.get(k) is not None]
            if not keys:
                continue
            filtered_pdf_sources += 1
            if extraction.get("segmentation") not in _PDF_PAGE_FILTER_SEGMENTATIONS:
                manifest = path.relative_to(REPO).as_posix()
                offenders.append(f"{manifest} {row.get('source_id')}: {', '.join(keys)}")

    # The scan is not vacuous: hundreds of PDF sources use page filters.
    assert filtered_pdf_sources > 100
    assert offenders == []


def test_the_belgian_manifests_no_longer_carry_the_ignored_filters() -> None:
    for manifest, source_id in (
        ("be-income-tax-official-documents.yaml", "be-cir92-fisconetplus-current-code-2025-income"),
        ("be-vat-official-documents.yaml", "be-vat-royal-decree-20-moniteur-original-pdf"),
    ):
        rows = {row["source_id"]: row for row in _documents(REPO / "manifests" / manifest)}
        assert rows[source_id]["source_format"] == "pdf"
        assert rows[source_id].get("extraction") is None
