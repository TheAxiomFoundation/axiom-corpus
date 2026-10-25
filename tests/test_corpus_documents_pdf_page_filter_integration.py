"""Merging the filter guard must preserve main's OCR of stamped scans."""

from typing import Any

import fitz  # type: ignore[import-untyped]
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.documents import _SINGLE_BLOCK_PDF_FILTER_KEYS


@settings(max_examples=30, deadline=None)
@given(keys=st.sets(st.sampled_from(_SINGLE_BLOCK_PDF_FILTER_KEYS)))
def test_unset_filters_preserve_ocr_of_a_stamped_scan(keys: set[str]) -> None:
    """Every subset of unset filters leaves scan OCR and its unread stamp intact."""
    image = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, 1275, 1650), False)
    image.clear_with(200)
    with fitz.open() as document:
        page = document.new_page(width=612, height=792)
        page.insert_image(page.rect, stream=image.tobytes("png"))
        page.insert_text((72, 72), "9/4/13")
        content = document.tobytes()

    calls = []

    def ocr(page: Any, *, extraction: dict[str, Any]) -> str:
        calls.append(page.number)
        return "Official body."

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", ocr)
        (block,) = documents_module._extract_pdf_blocks(
            content, extraction={"ocr": True, **dict.fromkeys(keys)}
        )

    assert block.body == "Official body.\n\n9/4/13"
    assert calls == [0]
