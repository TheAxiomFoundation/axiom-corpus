"""OCR of scanned PDF pages whose text layer is only an overlay (stamp, typed form fields).

The 2026-09-13 CMS state-plan attachments (for example OH-12-004-Att.pdf) are page scans
whose only text is a date stamp ("9/4/13"). Their manifests set ``ocr: true``, but the stamp
made the text layer non-empty, so OCR never ran and each page's body was the stamp.
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

import axiom_corpus.corpus.documents as documents_module
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.documents import (
    _pdf_page_image_coverage,
    _pdf_page_needs_ocr,
    _pdf_page_text,
    extract_official_documents,
)
from axiom_corpus.corpus.io import load_provisions

SCAN_TEXT = "State of Ohio Attachment 3.1-A Freestanding Birth Centers are provided."
LONG_TEXT = " ".join(f"word{index}" for index in range(40))


def _gray_png() -> bytes:
    pixmap = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, 8, 8), False)
    pixmap.clear_with(200)
    return pixmap.tobytes("png")


def _pdf(path: Path, *, image_rect: str | None, overlay: str | None, rotation: int = 0) -> Path:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    if image_rect == "page":
        page.insert_image(page.rect, stream=_gray_png())
    elif image_rect == "logo":
        page.insert_image(fitz.Rect(36, 36, 136, 86), stream=_gray_png())
    if overlay:
        page.insert_textbox(fitz.Rect(72, 72, 540, 720), overlay, fontsize=9)
    if rotation:
        # Like a scanner storing a landscape scan: content laid out, then /Rotate set.
        page.set_rotation(rotation)
    document.save(path)
    document.close()
    return path


@pytest.fixture
def ocr_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def fake_ocr_page(page, *, extraction):
        del page, extraction
        calls.append("ocr")
        return SCAN_TEXT

    monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", fake_ocr_page)
    return calls


def _first_page_text(path: Path, extraction: dict) -> str:
    with fitz.open(path) as document:
        return _pdf_page_text(document[0], extraction=extraction)


def test_stamp_over_a_page_scan_is_read_by_ocr(tmp_path, ocr_calls):
    pdf = _pdf(tmp_path / "scan.pdf", image_rect="page", overlay="9/4/13")

    assert _first_page_text(pdf, {"ocr": True}) == SCAN_TEXT
    assert ocr_calls == ["ocr"]


def test_typed_form_fields_over_a_page_scan_are_read_by_ocr(tmp_path, ocr_calls):
    overlay = "January 26, 2016 April 12, 2016 /s/ Ruth A. Hughes Associate Regional Administrator"
    pdf = _pdf(tmp_path / "form.pdf", image_rect="page", overlay=overlay)

    assert _first_page_text(pdf, {"ocr": True}) == SCAN_TEXT
    assert ocr_calls == ["ocr"]


def test_text_page_over_a_full_page_image_keeps_its_text_layer(tmp_path, ocr_calls):
    pdf = _pdf(tmp_path / "text-over-image.pdf", image_rect="page", overlay=LONG_TEXT)

    text = _first_page_text(pdf, {"ocr": True})

    assert "word39" in text
    assert ocr_calls == []


def test_short_text_page_with_a_small_logo_keeps_its_text_layer(tmp_path, ocr_calls):
    pdf = _pdf(tmp_path / "letterhead.pdf", image_rect="logo", overlay="Approval letter")

    assert "Approval letter" in _first_page_text(pdf, {"ocr": True})
    assert ocr_calls == []


def test_overlay_page_is_left_alone_without_ocr(tmp_path, ocr_calls):
    pdf = _pdf(tmp_path / "scan.pdf", image_rect="page", overlay="9/4/13")

    assert _first_page_text(pdf, {}).strip() == "9/4/13"
    assert ocr_calls == []


def test_empty_ocr_result_keeps_the_overlay(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path / "scan.pdf", image_rect="page", overlay="9/4/13")
    monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: " \n")

    assert _first_page_text(pdf, {"ocr": True}).strip() == "9/4/13"


def test_page_needs_ocr_rules(tmp_path):
    cases = {
        "blank": (_pdf(tmp_path / "blank.pdf", image_rect=None, overlay=None), True),
        "stamp-on-scan": (_pdf(tmp_path / "a.pdf", image_rect="page", overlay="9/4/13"), True),
        "stamp-no-image": (_pdf(tmp_path / "b.pdf", image_rect=None, overlay="9/4/13"), False),
        "text-on-scan": (_pdf(tmp_path / "c.pdf", image_rect="page", overlay=LONG_TEXT), False),
        "logo": (_pdf(tmp_path / "d.pdf", image_rect="logo", overlay="Approval letter"), False),
    }
    for name, (path, expected) in cases.items():
        with fitz.open(path) as document:
            page = document[0]
            text = page.get_text("text")
            assert _pdf_page_needs_ocr(page, text) is expected, name


def test_image_coverage_is_the_share_of_the_page(tmp_path):
    with fitz.open(_pdf(tmp_path / "scan.pdf", image_rect="page", overlay=None)) as document:
        assert _pdf_page_image_coverage(document[0]) == pytest.approx(1.0)
    with fitz.open(_pdf(tmp_path / "logo.pdf", image_rect="logo", overlay=None)) as document:
        assert _pdf_page_image_coverage(document[0]) < 0.02
    with fitz.open(_pdf(tmp_path / "none.pdf", image_rect=None, overlay="text")) as document:
        assert _pdf_page_image_coverage(document[0]) == 0.0


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_image_coverage_holds_on_rotated_pages(tmp_path, rotation):
    # OH-12-004-Att.pdf stores each landscape scan with /Rotate 270.
    scan = _pdf(tmp_path / "scan.pdf", image_rect="page", overlay=None, rotation=rotation)
    logo = _pdf(tmp_path / "logo.pdf", image_rect="logo", overlay=None, rotation=rotation)
    with fitz.open(scan) as document:
        assert _pdf_page_image_coverage(document[0]) == pytest.approx(1.0)
    with fitz.open(logo) as document:
        assert _pdf_page_image_coverage(document[0]) < 0.02


def test_stamp_over_a_rotated_page_scan_is_read_by_ocr(tmp_path, ocr_calls):
    pdf = _pdf(tmp_path / "scan.pdf", image_rect="page", overlay="9/4/13", rotation=270)

    assert _first_page_text(pdf, {"ocr": True}) == SCAN_TEXT
    assert ocr_calls == ["ocr"]


def test_extract_official_documents_ocrs_a_stamped_scan(tmp_path, ocr_calls):
    pdf = _pdf(tmp_path / "attachment.pdf", image_rect="page", overlay="9/4/13")
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: oh-12-004-attachment
    jurisdiction: us-test
    document_class: policy
    title: Scanned SPA attachment
    source_url: https://example.test/OH-12-004-Att.pdf
    citation_path: us-test/policy/spa/oh-12-004/attachment
    source_format: pdf
    local_path: {json.dumps(str(pdf))}
    extraction:
      ocr: true
"""
    )

    report = extract_official_documents(
        CorpusArtifactStore(tmp_path / "corpus"),
        manifest_path=manifest_path,
        version="2026-10-13-ocr-overlay",
    )

    records = load_provisions(report.provisions_path)
    bodies = [record.body or "" for record in records]
    assert any(SCAN_TEXT in body for body in bodies)
    assert not any(body.strip() == "9/4/13" for body in bodies)
    assert ocr_calls == ["ocr"]
