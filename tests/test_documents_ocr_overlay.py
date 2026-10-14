"""OCR of scanned PDF pages whose text layer is only an overlay (stamp, typed form fields).

The 2026-09-13 CMS state-plan attachments (for example OH-12-004-Att.pdf) are page scans
whose only text is a date stamp ("9/4/13"). Their manifests set ``ocr: true``, but the stamp
made the text layer non-empty, so OCR never ran and each page's body was the stamp. Such a
page is now read by OCR, and the text-layer lines OCR did not reproduce are kept after it,
so nothing typed onto the scan (dates, transmittal numbers, amounts, the signing official's
name and title) is lost. The rule's invariants are in tests/test_ocr_layer_line_properties.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

import axiom_corpus.corpus.documents as documents_module
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.documents import (
    _pdf_layer_lines,
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
    render_mode: int = 0,
    fill_opacity: float = 1,
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
        page.insert_textbox(
            fitz.Rect(72, 72, 540, 720),
            overlay,
            fontsize=9,
            render_mode=render_mode,
            fill_opacity=fill_opacity,
        )
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

    # The fake OCR read none of the typed fields, so every layer line is kept, in order:
    # the dates, and the name and title that have no digit.
    lines = _layer_lines(pdf)
    assert "Hughes" in " ".join(lines) and "Administrator" in " ".join(lines)
    assert text == SCAN_TEXT + "\n\n" + "\n".join(lines)
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


def test_a_typed_date_whose_day_and_year_ocr_read_elsewhere_is_kept(tmp_path, monkeypatch):
    # CMS-179 forms carry several dates. OCR reading "19" and "2014" in one of them must
    # not count as reading another (HI-14-005: DATE APPROVED was lost this way).
    pdf = _pdf(tmp_path / "form.pdf", image_rect="page", overlay="November 19, 2014")
    ocr = "17. DATE RECEIVED: March 19, 2014\n18. DATE APPROVED:\n"
    monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: ocr)

    assert _first_page_text(pdf, {"ocr": True}) == ocr.rstrip("\n") + "\n\nNovember 19, 2014"


def test_a_typed_name_and_title_ocr_did_not_read_are_kept(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path / "form.pdf", image_rect="page", overlay="Hye Sun Lee")
    ocr = "21. TYPED NAME: Hye Sun Lec\n22. TITLE:\n"
    monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: ocr)

    assert _first_page_text(pdf, {"ocr": True}) == ocr.rstrip("\n") + "\n\nHye Sun Lee"


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
    # Each unread line is kept once, with or without a digit.
    assert _with_unread_layer_lines("A", "9/4/13\n9/4/13\nB") == "A\n\n9/4/13\nB"
    # Tokens compare whole: "24" is not read by "2024", nor "Lee" by "Leeward".
    assert _with_unread_layer_lines("Total 2024", "24") == "Total 2024\n\n24"
    assert _with_unread_layer_lines("Leeward", "Lee") == "Leeward\n\nLee"
    # A line is read as a run: its words scattered over the page do not count.
    assert _with_unread_layer_lines("March 19, 2014 November", "November 19, 2014") == (
        "March 19, 2014 November\n\nNovember 19, 2014"
    )
    # OCR's line breaks do not matter, and neither does punctuation around the run.
    assert _with_unread_layer_lines("Hye\nSun\nLee", "Hye Sun Lee") == "Hye\nSun\nLee"
    assert _with_unread_layer_lines("Amount: ($1,234,567).", "$1,234,567") == (
        "Amount: ($1,234,567)."
    )
    assert _with_unread_layer_lines("(Check One):", "Check One)") == "(Check One):"
    # A currency sign, a minus and a percent sign are part of a value.
    assert _with_unread_layer_lines("$5 -5 5%", "5") == "$5 -5 5%\n\n5"
    # A line starts at the start of a token and ends at the end of one: not in the
    # punctuation trailing the token before it, nor inside a run of punctuation.
    assert _with_unread_layer_lines("2024. 5 items", ".5") == "2024. 5 items\n\n.5"
    assert _with_unread_layer_lines("a .. b", ". b") == "a .. b\n\n. b"
    # Spacing next to a letter is not compared: layers and OCR break words differently.
    assert _with_unread_layer_lines("Page 12 of 36", "Page12of36") == "Page 12 of 36"
    assert _with_unread_layer_lines("EffectiveDate", "Effective Date") == "EffectiveDate"
    # Spacing between digits and punctuation is: OCR's "1" and "2" are not a typed "12".
    assert _with_unread_layer_lines("1\n2", "12") == "1\n2\n\n12"
    assert _with_unread_layer_lines("3.1", "3. 1") == "3.1\n\n3. 1"
    # Letter case and every character count.
    assert _with_unread_layer_lines("january 1, 2018", "January 1, 2018") == (
        "january 1, 2018\n\nJanuary 1, 2018"
    )
    assert _with_unread_layer_lines("Isl", "/s/") == "Isl\n\n/s/"
    # A soft hyphen (format character) does not make a line garbage.
    assert _with_unread_layer_lines("Total", "Amount\u00ad 1,000") == "Total\n\nAmount\u00ad 1,000"
    # A garbled-font layer (control characters) is never appended.
    assert _with_unread_layer_lines("March 1, 2021", ".BSDI\x01\x14\x12 0DUPCFS") == (
        "March 1, 2021"
    )
    # A line with no letter or digit is not text.
    assert _with_unread_layer_lines("Total", "\u00b7 \u00b7\u00b7.\n\u25a1\n~") == "Total"


@pytest.mark.parametrize(
    ("render_mode", "fill_opacity", "painted"),
    [(0, 1, True), (3, 1, False), (0, 0, False), (1, 1, True)],
    ids=["filled", "invisible-mode-3", "transparent", "stroked"],
)
def test_layer_lines_report_whether_text_is_painted(tmp_path, render_mode, fill_opacity, painted):
    pdf = _pdf(
        tmp_path / "scan.pdf",
        image_rect="page",
        overlay="Associate Regional Administrator\nJanuary 1, 2018",
        render_mode=render_mode,
        fill_opacity=fill_opacity,
    )
    with fitz.open(pdf) as document:
        span_lines = _pdf_layer_lines(document[0], extraction={})
        text = document[0].get_text("text")

    assert ["".join(span for span, _, _ in spans) for spans in span_lines] == text.splitlines()
    flags = [flag for spans in span_lines for span, flag, _ in spans if span.strip()]
    assert flags and all(flag is painted for flag in flags)


# A recognition layer that agrees with none of OCR's words: five words of 3+ letters.
NOISE_LAYER = "Ckm rML err\nurrr jhofe\nAl"


def test_a_failed_invisible_recognition_layer_is_not_appended(tmp_path, monkeypatch):
    ocr = "Applicant Household Size\n"
    monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: ocr)
    hidden = _pdf(tmp_path / "hidden.pdf", image_rect="page", overlay=NOISE_LAYER, render_mode=3)
    painted = _pdf(tmp_path / "painted.pdf", image_rect="page", overlay=NOISE_LAYER)

    assert _first_page_text(hidden, {"ocr": True}) == ocr
    # The same lines painted are typed onto the scan, and every one is kept.
    assert _first_page_text(painted, {"ocr": True}) == (
        "Applicant Household Size\n\nCkm rML err\nurrr jhofe\nAl"
    )


def test_an_agreeing_recognition_layer_keeps_what_ocr_missed_but_not_fragments(
    tmp_path, monkeypatch
):
    # The layer's words mostly occur in the OCR text, so the layer is trusted; OCR missed
    # the title, and "cc:" is a fragment of a recognition layer.
    overlay = "Sincerely,\nAssociate Regional Administrator\nDivision of Medicaid Operations\ncc:"
    ocr = "Sincerely,\nDivision of Medicaid Operations\nce:\n"
    monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: ocr)
    hidden = _pdf(tmp_path / "hidden.pdf", image_rect="page", overlay=overlay, render_mode=3)
    painted = _pdf(tmp_path / "painted.pdf", image_rect="page", overlay=overlay)

    assert _first_page_text(hidden, {"ocr": True}) == (
        ocr.rstrip("\n") + "\n\nAssociate Regional Administrator"
    )
    assert _first_page_text(painted, {"ocr": True}) == (
        ocr.rstrip("\n") + "\n\nAssociate Regional Administrator\ncc:"
    )


def test_blank_ocr_keeps_an_invisible_layer_as_it_is(tmp_path, monkeypatch):
    monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: "")
    hidden = _pdf(tmp_path / "hidden.pdf", image_rect="page", overlay=NOISE_LAYER, render_mode=3)

    assert _first_page_text(hidden, {"ocr": True}).split() == NOISE_LAYER.split()


def _set_page_font(document, page, resource: str, value: str) -> None:
    resources = document.xref_get_key(page.xref, "Resources")
    holder = int(resources[1].split()[0]) if resources[0] == "xref" else page.xref
    prefix = "" if resources[0] == "xref" else "Resources/"
    fonts = document.xref_get_key(holder, prefix + "Font")
    if fonts[0] == "xref":
        document.xref_set_key(int(fonts[1].split()[0]), resource, value)
    else:
        document.xref_set_key(holder, f"{prefix}Font/{resource}", value)


def _type3_scan_pdf(lines: list[str], *, font_keys: str = "", render_mode: int = 0) -> bytes:
    """A scanned page whose lines are set in a Type3 font (``font_keys`` adds /Name or
    /BaseFont; render mode 0 fills the glyphs, 3 makes them invisible)."""
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=SCAN_PNG, keep_proportion=False)
    page.insert_text((0, 0), " ", fontsize=1)  # gives the page a /Font dictionary
    names = {code: chr(code) for code in range(65, 91)} | {
        code: chr(code) for code in range(97, 123)
    }
    names |= {32: "space", 46: "period", 47: "slash"}
    proc = document.get_new_xref()
    document.update_object(proc, "<< >>")
    document.update_stream(proc, b"600 0 0 0 500 700 d1 0 0 500 700 re f")
    differences = " ".join(f"{code} /{name}" for code, name in sorted(names.items()))
    procs = " ".join(f"/{name} {proc} 0 R" for name in sorted(set(names.values())))
    font = document.get_new_xref()
    document.update_object(
        font,
        "<< /Type /Font /Subtype /Type3 /FontBBox [0 0 1000 1000] "
        "/FontMatrix [0.001 0 0 0.001 0 0] "
        f"/CharProcs << {procs} >> /Encoding << /Type /Encoding /Differences [{differences}] >> "
        f"/FirstChar 32 /LastChar 126 /Widths [{' '.join(['600'] * 95)}] /Resources << >> "
        f"{font_keys} >>",
    )
    _set_page_font(document, page, "F3", f"{font} 0 R")
    body = b" ".join(
        b"BT %d Tr /F3 12 Tf 72 %d Td (%s) Tj ET" % (render_mode, 700 - 20 * index, line.encode())
        for index, line in enumerate(lines)
    )
    content = document.get_new_xref()
    document.update_object(content, "<< >>")
    document.update_stream(content, body)
    contents = document.xref_get_key(page.xref, "Contents")
    if contents[0] == "array":
        document.xref_set_key(page.xref, "Contents", contents[1][:-1] + f" {content} 0 R]")
    else:
        document.xref_set_key(page.xref, "Contents", f"[{contents[1]} {content} 0 R]")
    return document.tobytes()


TYPE3_OCR = "DEPARTMENT OF HEALTH AND HUMAN SERVICES\n20. SIGNATURE OF REGIONAL OFFICIAL:\n"
TYPE3_LINES = ["/s/", "Hye Sun Lee", "Acting Associate Regional Administrator"]


@pytest.mark.parametrize(
    ("font_keys", "span_name"),
    [
        ("", "Unnamed-T3"),
        ("/Name /T3F", "T3F"),
        ("/BaseFont /Foo /Name /Bar", "Bar"),
        ("/BaseFont /Foo", "Unnamed-T3"),
        ("/Name /ABCDEF+Foo", "Foo"),
        ("/Name /ab12cd+Foo", "Foo"),
        ("/Name /Foo#20Bar", "Foo Bar"),
        ("/Name /A#2341", "A#41"),
        ("/Name /F#E9", "F\u00e9"),
        ("/Name /F#C3#A9", "F\u00c3\u00a9"),
    ],
)
def test_typed_lines_in_a_type3_font_are_kept(monkeypatch, font_keys, span_name):
    # Review r3/r4: PyMuPDF before 1.27 (1.26 is locked here) reports filled Type3 glyphs as
    # unpainted, so typed lines in a Type3 font looked like a failed recognition layer.
    # There a Type3 font's spans count as painted, matched by the name MuPDF gives them
    # (/Name without a subset prefix, else "Unnamed-T3"); 1.27 and later report the paint.
    monkeypatch.setattr(
        documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: TYPE3_OCR
    )
    with fitz.open("pdf", _type3_scan_pdf(TYPE3_LINES, font_keys=font_keys)) as document:
        span_lines = _pdf_layer_lines(document[0], extraction={})
        result = _pdf_page_text(document[0], extraction={"ocr": True})

    spans = [(text, painted, font) for line in span_lines for text, painted, font in line]
    assert all(painted for text, painted, _ in spans if text.strip())
    if documents_module._PDF_TYPE3_PAINT_UNREPORTED:
        assert any(font == span_name for _, _, font in spans)
    assert result == TYPE3_OCR.rstrip("\n") + "\n\n" + "\n".join(TYPE3_LINES)


def _type3_font_written_inline(document, page) -> None:
    font = next(font[0] for font in page.get_fonts(full=True) if font[2] == "Type3")
    _set_page_font(document, page, "F3", document.xref_object(font, compressed=True))


def _type3_name_made_indirect(printed: str):
    def change(document, page) -> None:
        font = next(font[0] for font in page.get_fonts(full=True) if font[2] == "Type3")
        name = document.get_new_xref()
        document.update_object(name, printed)
        document.xref_set_key(font, "Name", f"{name} 0 R")

    return change


def _type3_resource_named(printed: str):
    """Renames the page's Type3 font resource /F3 (``printed`` as PDF writes the name)."""

    def change(document, page) -> None:
        for xref in page.get_contents():
            stream = document.xref_stream(xref)
            document.update_stream(xref, stream.replace(b"/F3 ", f"/{printed} ".encode()))
        kind, resources = document.xref_get_key(page.xref, "Resources")
        holder = int(resources.split()[0]) if kind == "xref" else page.xref
        fonts = document.xref_get_key(holder, "Font" if kind == "xref" else "Resources/Font")
        target = int(fonts[1].split()[0]) if fonts[0] == "xref" else holder
        text = document.xref_object(target, compressed=True)
        assert text.count("/F3") == 1
        document.update_object(target, text.replace("/F3", f"/{printed}"))

    return change


def _resources_inherited_from_the_page_tree(document, page) -> None:
    resources = document.xref_get_key(page.xref, "Resources")[1]
    pages = int(document.xref_get_key(page.xref, "Parent")[1].split()[0])
    document.xref_set_key(pages, "Resources", resources)
    document.xref_set_key(page.xref, "Resources", "null")


def _resources_written_into_the_page(document, page) -> None:
    kind, resources = document.xref_get_key(page.xref, "Resources")
    assert kind == "xref"
    resources = document.xref_object(int(resources.split()[0]), compressed=True)
    document.xref_set_key(page.xref, "Resources", resources)


def _page_drawn_by_a_form(document, page) -> None:
    content = b"\n".join(document.xref_stream(xref) for xref in page.get_contents())
    resources = document.xref_get_key(page.xref, "Resources")[1]
    form = document.get_new_xref()
    document.update_object(
        form, f"<< /Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources {resources} >>"
    )
    document.update_stream(form, content)
    contents = document.get_new_xref()
    document.update_object(contents, "<< >>")
    document.update_stream(contents, b"q /Fm1 Do Q")
    document.xref_set_key(page.xref, "Resources", f"<< /XObject << /Fm1 {form} 0 R >> >>")
    document.xref_set_key(page.xref, "Contents", f"{contents} 0 R")


@pytest.mark.parametrize(
    ("font_keys", "changes", "span_name"),
    [
        ("/BaseFont /Foo /Name /Bar", [_type3_font_written_inline], "Bar"),
        ("/BaseFont /Foo", [_type3_font_written_inline], "Unnamed-T3"),
        ("/Name /ab12cd+Bar", [_type3_font_written_inline], "Bar"),
        (
            "/BaseFont /Foo /Name /Bar",
            [_type3_font_written_inline, _resources_written_into_the_page],
            "Bar",
        ),
        (
            "/BaseFont /Foo /Name /Bar",
            [_type3_font_written_inline, _resources_inherited_from_the_page_tree],
            "Bar",
        ),
        ("/Name /T3F", [_resources_inherited_from_the_page_tree], "T3F"),
        ("/BaseFont /Foo /Name /Bar", [_type3_font_written_inline, _page_drawn_by_a_form], "Bar"),
        ("/Name /T3F", [_page_drawn_by_a_form], "T3F"),
        ("/BaseFont /Foo /Name /Placeholder", [_type3_name_made_indirect("/Ind")], "Ind"),
        ("/BaseFont /Foo /Name /Placeholder", [_type3_name_made_indirect("/F#E9")], "F\u00e9"),
        ("/BaseFont /Foo /Name /Placeholder", [_type3_name_made_indirect("/Foo#20Bar")], "Foo Bar"),
        ("/BaseFont /Foo /Name /Placeholder", [_type3_name_made_indirect("/AB12CD+X")], "X"),
        (
            "/BaseFont /Foo /Name /Bar",
            [_type3_font_written_inline, _type3_resource_named("F#203")],
            "Bar",
        ),
        ("/Name /Bar", [_type3_font_written_inline, _type3_resource_named("F#2F3")], "Bar"),
        ("/Name /Bar", [_type3_font_written_inline, _type3_resource_named("F#E9")], "Bar"),
    ],
)
def test_type3_fonts_are_named_however_they_are_written(monkeypatch, font_keys, changes, span_name):
    # Review r4: a Type3 font written inline in the resources has no object number, and
    # reading its /Name by object number raised ValueError, failing the page. Its /Name is
    # read through the resources that hold it (inherited or in a form too), and an indirect
    # /Name is resolved (its #xx escapes undone), so the name matches the spans' under
    # PyMuPDF before 1.27. An inline font whose resource name can't be addressed ("F/3", or
    # a byte that isn't UTF-8, which made the lookup raise TypeError) is named by the name
    # get_fonts lists, its /Name.
    monkeypatch.setattr(
        documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: TYPE3_OCR
    )
    with fitz.open("pdf", _type3_scan_pdf(TYPE3_LINES, font_keys=font_keys)) as document:
        for change in changes:
            change(document, document[0])
        pdf = document.tobytes()
    with fitz.open("pdf", pdf) as document:
        page = document[0]
        fonts = [font for font in page.get_fonts(full=True) if font[2] == "Type3"]
        span_fonts = {font for line in _pdf_layer_lines(page, extraction={}) for _, _, font in line}
        names = documents_module._pdf_type3_font_names(page)
        result = _pdf_page_text(page, extraction={"ocr": True})

    assert len(fonts) == 1
    assert (fonts[0][0] == 0) == (_type3_font_written_inline in changes)
    assert (fonts[0][6] != 0) == (_page_drawn_by_a_form in changes)
    if documents_module._PDF_TYPE3_PAINT_UNREPORTED:
        assert names == {span_name}
        assert span_name in span_fonts
    else:
        assert names == frozenset()
    assert result == TYPE3_OCR.rstrip("\n") + "\n\n" + "\n".join(TYPE3_LINES)


@pytest.mark.parametrize("resource", ["F#2F3", "F#E9"])
def test_an_unaddressable_inline_type3_font_with_a_base_font_is_a_known_limit(
    monkeypatch, resource
):
    # Limit, pinned: a Type3 font has no /BaseFont in a conforming file. If an inline one
    # has one and its resource name can't be addressed, get_fonts lists the /BaseFont, so
    # under PyMuPDF before 1.27 its spans (named by /Name) are not counted painted and the
    # typed lines are judged as a recognition layer. Nothing raises.
    monkeypatch.setattr(
        documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: TYPE3_OCR
    )
    pdf = _type3_scan_pdf(TYPE3_LINES, font_keys="/BaseFont /Foo /Name /Bar")
    with fitz.open("pdf", pdf) as document:
        _type3_font_written_inline(document, document[0])
        _type3_resource_named(resource)(document, document[0])
        pdf = document.tobytes()
    with fitz.open("pdf", pdf) as document:
        names = documents_module._pdf_type3_font_names(document[0])
        result = _pdf_page_text(document[0], extraction={"ocr": True})

    if documents_module._PDF_TYPE3_PAINT_UNREPORTED:
        assert names == {"Foo"}
        assert result == TYPE3_OCR
    else:
        assert names == frozenset()
        assert result == TYPE3_OCR.rstrip("\n") + "\n\n" + "\n".join(TYPE3_LINES)


def _unreadable_xref(xref, key):
    raise ValueError("bad xref")


@pytest.mark.parametrize(
    ("font", "span_name"),
    [
        ((12, "n/a", "Type3", "ABCDEF+Foo", "F3", "", 0), "Foo"),
        ((0, "n/a", "Type3", "Foo", "F3", "", 0), "Foo"),
        ((12, "n/a", "Type3", "", "F3", "", 0), "Unnamed-T3"),
    ],
)
def test_a_type3_name_that_cannot_be_read_falls_back_to_the_listed_name(font, span_name):
    page = SimpleNamespace(xref=5, parent=SimpleNamespace(xref_get_key=_unreadable_xref))
    assert documents_module._pdf_type3_span_name(page, font) == span_name


def test_an_invisible_type3_layer_is_judged_where_paint_is_reported(monkeypatch):
    # A failed recognition layer set invisibly (render mode 3) in a Type3 font. PyMuPDF
    # 1.27+ reports it unpainted and it is dropped. Before 1.27 invisible and filled Type3
    # text look alike, so it counts as painted and is kept (a known limit of the lock).
    noise = ["Ckm rML Qzvx Plort Wexd", "Brnq Tholv Gremz Fuxt", "Yolp Kranv Dext Mopr"]
    monkeypatch.setattr(
        documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: TYPE3_OCR
    )
    pdf = _type3_scan_pdf(noise, font_keys="/Name /T3F", render_mode=3)
    with fitz.open("pdf", pdf) as document:
        result = _pdf_page_text(document[0], extraction={"ocr": True})

    if documents_module._PDF_TYPE3_PAINT_UNREPORTED:
        assert result == TYPE3_OCR.rstrip("\n") + "\n\n" + "\n".join(noise)
    else:
        assert result == TYPE3_OCR


class _TextOutputPage:
    """A real page whose text output is replaced (to give it a separator control)."""

    def __init__(self, page, text: str):
        self._page, self._text = page, text

    def get_text(self, kind="text", **kwargs):
        return self._text if kind == "text" else self._page.get_text(kind, **kwargs)

    def __getattr__(self, name):
        return getattr(self._page, name)


def test_the_text_line_fallback_still_drops_garbled_lines(tmp_path, monkeypatch):
    # Review r3: the fallback used splitlines(), which breaks "2EQI\x1e" at U+001E and
    # leaves a clean-looking "2EQI". It splits at newlines only, so the line keeps its
    # control character and is dropped; the typed line is kept.
    ocr = "Applicant Household Size\n"
    monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", lambda page, *, extraction: ocr)
    monkeypatch.setattr(
        documents_module, "_pdf_layer_lines", lambda page, *, extraction: [[("x", True, "F")]]
    )
    pdf = _pdf(tmp_path / "scan.pdf", image_rect="page", overlay="9/4/13")
    with fitz.open(pdf) as document:
        page = _TextOutputPage(document[0], "2EQI\x1e\nJanuary 1, 2018\n")
        result = _pdf_page_text(page, extraction={"ocr": True})

    assert result == "Applicant Household Size\n\nJanuary 1, 2018"


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
