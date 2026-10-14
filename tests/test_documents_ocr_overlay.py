"""OCR of scanned PDF pages whose text layer is only an overlay (stamp, typed form fields).

The 2026-09-13 CMS state-plan attachments (for example OH-12-004-Att.pdf) are page scans
whose only text is a date stamp ("9/4/13"). Their manifests set ``ocr: true``, but the stamp
made the text layer non-empty, so OCR never ran and each page's body was the stamp. Such a
page is now read by OCR, and the text-layer lines OCR did not reproduce are kept after it,
so exact typed values (dates, transmittal numbers, amounts) are never lost.
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
    _rect_union_area,
    _with_unread_layer_lines,
    extract_official_documents,
)
from axiom_corpus.corpus.io import load_provisions

SCAN_TEXT = "State of Ohio Attachment 3.1-A Freestanding Birth Centers are provided."
LONG_TEXT = " ".join(f"word{index}" for index in range(40))


def _png(width: int, height: int) -> bytes:
    pixmap = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, width, height), False)
    pixmap.clear_with(200)
    return pixmap.tobytes("png")


# A letter page scanned at 150 dpi, and a 70 dpi slide background.
SCAN_PNG = _png(1275, 1650)
SLIDE_PNG = _png(595, 770)


def _gray_png() -> bytes:
    return SCAN_PNG


def _pdf(
    path: Path,
    *,
    image_rect: str | None,
    overlay: str | None,
    rotation: int = 0,
    cropbox: tuple[float, float, float, float] | None = None,
    mediabox: tuple[float, float, float, float] | None = None,
) -> Path:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    if mediabox:
        page.set_mediabox(fitz.Rect(*mediabox))
    if image_rect == "page":
        page.insert_image(page.rect, stream=_gray_png(), keep_proportion=False)
    elif image_rect == "logo":
        page.insert_image(fitz.Rect(36, 36, 136, 86), stream=_gray_png(), keep_proportion=False)
    elif image_rect == "strips":
        # A scan stored as two half-page strips.
        page.insert_image(fitz.Rect(0, 0, 612, 396), stream=_gray_png(), keep_proportion=False)
        page.insert_image(fitz.Rect(0, 396, 612, 792), stream=_gray_png(), keep_proportion=False)
    elif image_rect == "slide":
        page.insert_image(page.rect, stream=SLIDE_PNG, keep_proportion=False)
    elif image_rect == "overhang":
        # A scan placed partly off the page: 60% of the page is covered.
        page.insert_image(fitz.Rect(-200, 0, 367.2, 792), stream=_gray_png(), keep_proportion=False)
    if overlay:
        page.insert_textbox(fitz.Rect(72, 72, 540, 720), overlay, fontsize=9)
    if cropbox:
        page.set_cropbox(fitz.Rect(*cropbox))
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


def _layer_lines(path: Path) -> list[str]:
    with fitz.open(path) as document:
        text = document[0].get_text("text")
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def test_stamp_over_a_page_scan_is_read_by_ocr(tmp_path, ocr_calls):
    pdf = _pdf(tmp_path / "scan.pdf", image_rect="page", overlay="9/4/13")

    assert _first_page_text(pdf, {"ocr": True}) == SCAN_TEXT + "\n\n9/4/13"
    assert ocr_calls == ["ocr"]


def test_typed_form_fields_over_a_page_scan_are_read_by_ocr_and_kept_exactly(tmp_path, ocr_calls):
    overlay = "January 26, 2016 April 12, 2016 /s/ Ruth A. Hughes Associate Regional Administrator"
    pdf = _pdf(tmp_path / "form.pdf", image_rect="page", overlay=overlay)

    text = _first_page_text(pdf, {"ocr": True})

    assert text.startswith(SCAN_TEXT)
    # The fake OCR read none of the typed values, so every layer line with a digit is kept.
    dated = [line for line in _layer_lines(pdf) if any(char.isdigit() for char in line)]
    assert dated and all(line in text for line in dated)
    assert ocr_calls == ["ocr"]


def test_overlay_ocr_already_read_is_not_repeated(tmp_path, monkeypatch):
    # OCR groups the typed form fields into different lines than the text layer does.
    overlay = "January 26, 2016 April 12, 2016 /s/ Ruth A. Hughes"
    pdf = _pdf(tmp_path / "form.pdf", image_rect="page", overlay=overlay)
    ocr = "TRANSMITTAL\nJanuary 26, 2016\nApril 12, 2016\n/s/ Ruth A. Hughes\n"
    monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: ocr)

    assert _first_page_text(pdf, {"ocr": True}) == ocr


def test_layer_values_ocr_misreads_are_kept(tmp_path, monkeypatch):
    # OCR of a CMS-179 form box can turn "$1,234,567" into "$1.234.S67"; the typed value stays.
    pdf = _pdf(tmp_path / "form.pdf", image_rect="page", overlay="FFY 2013 $1,234,567")
    monkeypatch.setattr(
        documents_module,
        "_ocr_pdf_page_text",
        lambda page, *, extraction: "FEDERAL BUDGET IMPACT\nFFY 2013 $1.234.S67\n",
    )

    text = _first_page_text(pdf, {"ocr": True})

    assert text == "FEDERAL BUDGET IMPACT\nFFY 2013 $1.234.S67\n\nFFY 2013 $1,234,567"


def test_layer_lines_ocr_reproduced_are_not_repeated(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path / "scan.pdf", image_rect="page", overlay="9/4/13")
    monkeypatch.setattr(
        documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: "Page 12\n9/4/13\n"
    )

    assert _first_page_text(pdf, {"ocr": True}) == "Page 12\n9/4/13\n"


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


def test_with_unread_layer_lines_cases():
    assert _with_unread_layer_lines("", "") == ""
    assert _with_unread_layer_lines("OCR text\n", "") == "OCR text\n"
    # No OCR text: the layer exactly as it was.
    assert _with_unread_layer_lines("", " 9/4/13 \n\n9/4/13") == " 9/4/13 \n\n9/4/13"
    assert _with_unread_layer_lines("A\n9/4/13", "9/4/13\n9/4/13") == "A\n9/4/13"
    # Kept once; a line with no digit adds nothing OCR lacks.
    assert _with_unread_layer_lines("A", "9/4/13\n9/4/13\nB") == "A\n\n9/4/13"
    # Tokens compare whole: "24" is not read by "2024".
    assert _with_unread_layer_lines("Total 2024", "24") == "Total 2024\n\n24"
    # Edge punctuation does not matter.
    assert _with_unread_layer_lines("Amount: ($1,234,567).", "$1,234,567") == (
        "Amount: ($1,234,567)."
    )
    # A soft hyphen (format character) does not make a line garbage.
    assert _with_unread_layer_lines("Total", "Amount\u00ad 1,000") == "Total\n\nAmount\u00ad 1,000"
    # A garbled-font layer (control characters) is never appended.
    assert _with_unread_layer_lines("March 1, 2021", ".BSDI\x01\x14\x12 0DUPCFS") == (
        "March 1, 2021"
    )


def test_page_needs_ocr_rules(tmp_path):
    cases = {
        "blank": (_pdf(tmp_path / "blank.pdf", image_rect=None, overlay=None), True),
        "stamp-on-scan": (_pdf(tmp_path / "a.pdf", image_rect="page", overlay="9/4/13"), True),
        "stamp-no-image": (_pdf(tmp_path / "b.pdf", image_rect=None, overlay="9/4/13"), False),
        "text-on-scan": (_pdf(tmp_path / "c.pdf", image_rect="page", overlay=LONG_TEXT), False),
        "logo": (_pdf(tmp_path / "d.pdf", image_rect="logo", overlay="Approval letter"), False),
        "strips": (_pdf(tmp_path / "e.pdf", image_rect="strips", overlay="9/4/13"), True),
        "overhang": (_pdf(tmp_path / "f.pdf", image_rect="overhang", overlay="9/4/13"), False),
        # A born-digital slide over a 70 dpi background photo is not a scan.
        "slide": (
            _pdf(tmp_path / "g.pdf", image_rect="slide", overlay="Medicaid Fair 2021"),
            False,
        ),
    }
    for name, (path, expected) in cases.items():
        with fitz.open(path) as document:
            page = document[0]
            text = page.get_text("text")
            assert _pdf_page_needs_ocr(page, text) is expected, name


def _coverage(path: Path) -> float:
    with fitz.open(path) as document:
        return _pdf_page_image_coverage(document[0])


def test_image_coverage_is_the_share_of_the_page(tmp_path):
    assert _coverage(_pdf(tmp_path / "scan.pdf", image_rect="page", overlay=None)) == 1.0
    assert _coverage(_pdf(tmp_path / "logo.pdf", image_rect="logo", overlay=None)) < 0.02
    assert _coverage(_pdf(tmp_path / "none.pdf", image_rect=None, overlay="text")) == 0.0
    assert _coverage(_pdf(tmp_path / "strips.pdf", image_rect="strips", overlay=None)) == 1.0
    overhang = _coverage(_pdf(tmp_path / "over.pdf", image_rect="overhang", overlay=None))
    assert overhang == pytest.approx(0.6, abs=1e-6)
    assert _coverage(_pdf(tmp_path / "slide.pdf", image_rect="slide", overlay=None)) == 0.0


def test_rect_union_area_is_exact():
    assert _rect_union_area([]) == 0.0
    a, b = fitz.Rect(0, 0, 10, 10), fitz.Rect(5, 5, 15, 15)
    assert _rect_union_area([a, b]) == 175.0
    assert _rect_union_area([a, fitz.Rect(2, 2, 3, 3)]) == 100.0
    assert _rect_union_area([fitz.Rect(0, 0, 10, 1), fitz.Rect(0, 1, 10, 2)]) == 20.0


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize(
    ("cropbox", "mediabox"),
    [
        (None, None),
        ((50, 50, 562, 742), None),
        (None, (100, 100, 712, 892)),
        ((0, 0, 612, 600), None),
        ((150, 150, 650, 780), (100, 100, 712, 892)),
    ],
    ids=["plain", "inset-cropbox", "offset-mediabox", "short-cropbox", "inset-and-offset"],
)
def test_image_coverage_holds_across_rotation_cropbox_and_mediabox(
    tmp_path, rotation, cropbox, mediabox
):
    # OH-12-004-Att.pdf stores each landscape scan with /Rotate 270.
    scan = _pdf(
        tmp_path / "scan.pdf",
        image_rect="page",
        overlay=None,
        rotation=rotation,
        cropbox=cropbox,
        mediabox=mediabox,
    )
    logo = _pdf(
        tmp_path / "logo.pdf",
        image_rect="logo",
        overlay=None,
        rotation=rotation,
        cropbox=cropbox,
        mediabox=mediabox,
    )
    assert _coverage(scan) == 1.0
    assert _coverage(logo) < 0.02


@pytest.mark.parametrize("rotation", [0, 90, 270])
def test_partial_image_coverage_under_an_asymmetric_crop(tmp_path, rotation):
    # A half-width, half-height image in the top-left corner, under a crop box that cuts
    # 192 pt off the bottom: a flipped or shifted frame would measure it wrongly.
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(fitz.Rect(0, 0, 306, 396), stream=SCAN_PNG, keep_proportion=False)
    page.set_cropbox(fitz.Rect(0, 0, 612, 600))
    if rotation:
        page.set_rotation(rotation)
    reopened = fitz.open("pdf", document.tobytes())

    assert _pdf_page_image_coverage(reopened[0]) == pytest.approx(
        (306 * 396) / (612 * 600), abs=1e-9
    )


def test_stamp_over_a_rotated_page_scan_is_read_by_ocr(tmp_path, ocr_calls):
    pdf = _pdf(tmp_path / "scan.pdf", image_rect="page", overlay="9/4/13", rotation=270)

    assert _first_page_text(pdf, {"ocr": True}).startswith(SCAN_TEXT)
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
    assert any(SCAN_TEXT in body and "9/4/13" in body for body in bodies)
    assert not any(body.strip() == "9/4/13" for body in bodies)
    assert ocr_calls == ["ocr"]
