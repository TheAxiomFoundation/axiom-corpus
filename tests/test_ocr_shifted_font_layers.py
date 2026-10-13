"""Decoding text-layer fonts whose character codes are a constant shift from ASCII.

With ``ocr: true``, a scanned page whose text layer is only an overlay is read by OCR and
the layer lines OCR did not read are kept after it (tests/test_ocr_layer_line_properties.py).
On CMS state-plan forms the dates, names and notes typed onto the scan are often in a
Type0 Identity-H font with no ToUnicode map: MuPDF has no Unicode for those characters and
prints their codes, which there are a constant shift from ASCII (Minion Pro's 31 below,
Arial's and Times New Roman's 29). With OCR text, ``_pdf_decoded_span_lines`` finds those
characters, learns each font's shift from the font's lines OCR read, and decodes the
font's spans before ``_without_garbled_spans`` would leave them out.

Decoding a line, ``_pdf_decoded_layer_line(chars, shifts)``, for every input:

S1. One for one: the result has a character for each of the line's, and every character
    that is mapped, or of a font with no shift or shift 0, is unchanged.
S2. Each unmapped character of a font with shift k becomes chr(code + k) in printable
    ASCII, and the result is None exactly when one would fall outside it.
S3. With no shifts the result is the line's characters as they are.

Learning the shifts, ``_pdf_font_code_shifts(lines, ocr_text)``:

S4. It is ``_reference_shifts``: every shift tried on every line whose unmapped characters
    are all one font's, read with #868's brute-force reader (``_reference_reads``), and a
    font's shift kept only when it is the font's one shift with evidence and that evidence
    is enough. A differential test against a definition written without range bookkeeping.
S5. Round trip: ASCII lines written in a font by a shift k, read by OCR, give k back
    unless another shift also has evidence, and decoding gives the lines back exactly.
S6. Lines without unmapped characters, the order of the lines and repeated lines change
    nothing, and shift 0 is never returned.

Reading a page, ``_pdf_decoded_span_lines`` and ``_pdf_page_text`` (built PDFs, and
retained CMS pages with Tesseract's stored output):

S7. Decoding returns ``_pdf_layer_lines``' spans unchanged on a page without an unmapped
    character, and every span's paint unchanged on every page.
S8. A span without an unmapped character is never changed, even when it shares its font's
    name with a shifted one, and a font whose characters in a line are partly mapped is not
    decoded in that line.
"""

from __future__ import annotations

import hashlib
import json
import string
import unicodedata
from pathlib import Path

import fitz
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.documents as documents_module
from axiom_corpus.corpus.documents import (
    _PDF_SHIFT_FIRST,
    _PDF_SHIFT_LAST,
    _PDF_SHIFT_LETTERS,
    _PDF_SHIFT_LINE_LETTERS,
    _pdf_decoded_layer_line,
    _pdf_decoded_span_lines,
    _pdf_font_code_shifts,
    _pdf_layer_lines,
    _pdf_page_text,
    _pdf_text_flags,
    _without_garbled_spans,
)
from tests.test_ocr_layer_line_properties import _reference_reads

REPO_ROOT = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------------------- the reference

# Every shift that could take a test code (below 0x200) into printable ASCII, and more.
_ALL_SHIFTS = range(-0x300, 0x100)


def _reference_decode(chars: list[tuple[str, str | None]], shifts: dict[str, int]) -> str | None:
    out = ""
    for char, font in chars:
        if font is None or not shifts.get(font):
            out += char
            continue
        code = ord(char) + shifts[font]
        if code < 0x20 or code > 0x7E:
            return None
        out += chr(code)
    return out


def _reference_shifts(lines: list[list[tuple[str, str | None]]], ocr_text: str) -> dict[str, int]:
    """S4, written out: per font, the distinct decoded lines OCR reads, by shift."""
    found: dict[str, dict[int, dict[str, int]]] = {}
    for chars in lines:
        fonts = {font for _, font in chars if font is not None}
        if len(fonts) != 1:
            continue
        font = fonts.pop()
        for shift in _ALL_SHIFTS:
            decoded = _reference_decode(chars, {font: shift} if shift else {})
            if decoded is None:
                continue
            if shift == 0 and any(not 0x20 <= ord(c) <= 0x7E for c, f in chars if f):
                continue  # shift 0 too decodes only into printable ASCII
            letters = sum(1 for c, f in chars if f and chr(ord(c) + shift).isalnum())
            if letters >= _PDF_SHIFT_LINE_LETTERS and _reference_reads(ocr_text, decoded):
                found.setdefault(font, {}).setdefault(shift, {})[" ".join(decoded.split())] = (
                    letters
                )
    return {
        font: shift
        for font, by_shift in found.items()
        if len(by_shift) == 1
        for shift, read in by_shift.items()
        if shift and sum(read.values()) >= _PDF_SHIFT_LETTERS
    }


def _encode(text: str, font: str, shift: int) -> list[tuple[str, str | None]]:
    """``text`` written in ``font`` with codes ``shift`` below its characters, unmapped."""
    return [(chr(ord(char) - shift), font) for char in text]


# -------------------------------------------------------------------------- strategies

ASCII_TEXT = string.ascii_letters + string.digits + " /.,-:&'()"
# Shifts whose codes stay clear of surrogates, U+FFFD and negative values for ASCII text.
SHIFT = st.integers(min_value=-0x180, max_value=0x1F).filter(bool)
FONT = st.sampled_from(["MinionPro-Regular", "ArialMT", "T23"])
TYPED = st.text(alphabet=st.sampled_from(ASCII_TEXT), min_size=1, max_size=24)
MAPPED_CHAR = st.tuples(st.sampled_from("Ab1 /.\x01é’"), st.none())
UNMAPPED_CHAR = st.tuples(
    st.integers(min_value=0, max_value=0x1FF).map(chr).filter(lambda c: c != "�"), FONT
)
CHARS = st.lists(st.one_of(MAPPED_CHAR, UNMAPPED_CHAR), max_size=16)


@st.composite
def page_lines(draw):
    """Lines in up to two shifted fonts and mapped text, with OCR text that reads some."""
    fonts = draw(st.lists(st.tuples(FONT, SHIFT), min_size=1, max_size=2, unique_by=lambda x: x[0]))
    lines, typed = [], []
    for _ in range(draw(st.integers(min_value=1, max_value=6))):
        font, shift = draw(st.sampled_from(fonts))
        text = draw(TYPED)
        typed.append(text)
        line = _encode(text, font, shift)
        if draw(st.booleans()):
            line = [(char, None) for char in draw(st.text(alphabet="Ab1 ", max_size=4))] + line
        lines.append(line)
    if draw(st.booleans()):
        lines.append(draw(CHARS))
    read = draw(st.lists(st.sampled_from(typed), max_size=len(typed)))
    noise = draw(
        st.lists(st.sampled_from(["Date", "12/10/15", "Acting", "of", "2020"]), max_size=4)
    )
    return lines, "\n".join(read + noise)


# ------------------------------------------------------------------------- decoding a line


@settings(max_examples=500, deadline=None)
@given(CHARS, st.dictionaries(FONT, st.integers(min_value=-0x200, max_value=0x80), max_size=3))
def test_decoding_changes_only_unmapped_characters_of_shifted_fonts(chars, shifts):
    decoded = _pdf_decoded_layer_line(chars, shifts)

    outside = any(
        font is not None
        and shifts.get(font)
        and not _PDF_SHIFT_FIRST <= ord(char) + shifts[font] <= _PDF_SHIFT_LAST
        for char, font in chars
    )
    # S2: None exactly when a shifted character would leave printable ASCII.
    assert (decoded is None) == outside
    if decoded is None:
        return
    # S1: one for one; S2: each shifted character moved by its font's shift.
    assert len(decoded) == len(chars)
    for out, (char, font) in zip(decoded, chars, strict=True):
        if font is None or not shifts.get(font):
            assert out == char
        else:
            assert out == chr(ord(char) + shifts[font])
            assert _PDF_SHIFT_FIRST <= ord(out) <= _PDF_SHIFT_LAST
    assert decoded == _reference_decode(chars, shifts)


def test_decoding_stays_in_printable_ascii():
    # S2 at its edges: U+0020 and U+007E are printable ASCII, U+001F and U+007F (DEL) not.
    font = "MinionPro-Regular"
    assert _pdf_decoded_layer_line([("\x01", font), ("_", font)], {font: 31}) == " ~"
    assert _pdf_decoded_layer_line([("\x00", font)], {font: 31}) is None
    assert _pdf_decoded_layer_line([("`", font)], {font: 31}) is None
    # A mapped character outside printable ASCII is not decoded, so it never counts.
    assert _pdf_decoded_layer_line([("é", None), ("\x01", font)], {font: 31}) == "é "


@given(CHARS)
def test_decoding_without_shifts_is_the_identity(chars):
    # S3.
    assert _pdf_decoded_layer_line(chars, {}) == "".join(char for char, _ in chars)


# ---------------------------------------------------------------------- learning the shifts


@settings(max_examples=400, deadline=None)
@given(page_lines())
def test_shifts_are_the_reference_shifts(case):
    lines, ocr_text = case
    assume(ocr_text.split())

    # S4.
    assert _pdf_font_code_shifts(lines, ocr_text) == _reference_shifts(lines, ocr_text)


@settings(max_examples=400, deadline=None)
@given(
    FONT,
    SHIFT,
    st.lists(
        st.text(alphabet=st.sampled_from(ASCII_TEXT), min_size=4, max_size=24).filter(
            lambda text: sum(c.isalnum() for c in text) >= _PDF_SHIFT_LINE_LETTERS
        ),
        min_size=1,
        max_size=4,
    ),
    st.lists(st.sampled_from(["Date", "of", "2020", "Acting"]), max_size=3),
)
def test_lines_written_by_a_shift_give_the_shift_and_their_text_back(font, shift, texts, noise):
    lines = [_encode(text, font, shift) for text in texts]
    ocr_text = "\n".join(texts + noise)
    letters = sum(sum(c.isalnum() for c in text) for text in set(texts))

    shifts = _pdf_font_code_shifts(lines, ocr_text)

    # S5: the shift comes back when the evidence is enough and no other shift has any; the
    # lines then decode to the text exactly.
    reference = _reference_shifts(lines, ocr_text)
    assert shifts == reference
    if letters >= _PDF_SHIFT_LETTERS and shifts != {font: shift}:
        assert shifts == {}
        rivals = {
            other
            for other in _ALL_SHIFTS
            if other != shift
            for line in lines
            if (decoded := _reference_decode(line, {font: other})) is not None
            and sum(1 for c, _ in line if chr(ord(c) + other).isalnum()) >= _PDF_SHIFT_LINE_LETTERS
            and _reference_reads(ocr_text, decoded)
        }
        assert rivals, "the shift was lost without a rival shift"
    if shifts == {font: shift}:
        assert [_pdf_decoded_layer_line(line, shifts) for line in lines] == texts
    if letters < _PDF_SHIFT_LETTERS:
        assert shifts == {}


@settings(max_examples=300, deadline=None)
@given(page_lines(), st.lists(st.lists(MAPPED_CHAR, max_size=8), max_size=3), st.randoms())
def test_mapped_lines_order_and_repeats_change_nothing(case, mapped, random):
    lines, ocr_text = case
    assume(ocr_text.split())
    shifts = _pdf_font_code_shifts(lines, ocr_text)

    shuffled = [*lines, *lines[:2], *mapped]
    random.shuffle(shuffled)
    # S6.
    assert _pdf_font_code_shifts(shuffled, ocr_text) == shifts
    assert 0 not in shifts.values()


def test_evidence_thresholds():
    font, shift = "MinionPro-Regular", 31
    three = _encode("6/2/1", font, shift)  # 3 letters or digits
    four = _encode("10 P & I", font, shift)  # 4
    four_more = _encode("12 P & I", font, shift)
    eight = _encode("James Scott", font, shift)  # 10
    # A line with fewer than four decoded letters or digits is no evidence, however many
    # such lines OCR reads.
    assert _pdf_font_code_shifts([three], "6/2/1") == {}
    threes = [_encode(text, font, shift) for text in ("6/2/1", "7/3/1", "8/4/1")]
    assert _pdf_font_code_shifts(threes, "6/2/1 7/3/1 8/4/1") == {}
    # Only decoded characters count: mapped letters beside them are no evidence.
    labelled = [[(c, None) for c in f"Approved{n} "] + _encode("6/2/1", font, shift) for n in "AB"]
    assert _pdf_font_code_shifts(labelled, "ApprovedA 6/2/1 ApprovedB 6/2/1") == {}
    # Four are a line's worth, but one such line is not enough.
    assert _pdf_font_code_shifts([four], "10 P & I") == {}
    assert _pdf_font_code_shifts([four, four], "10 P & I") == {}  # the same line twice
    # Two distinct lines of four, or one of eight or more, are.
    assert _pdf_font_code_shifts([four, four_more], "10 P & I\n12 P & I") == {font: shift}
    assert _pdf_font_code_shifts([eight], "Signed: James Scott") == {font: shift}
    # A line OCR does not read is no evidence.
    assert _pdf_font_code_shifts([eight], "James Scot") == {}
    # Another shift with evidence for the same font makes both ambiguous.
    rival = _encode("James Scott", font, 30)
    assert _pdf_font_code_shifts([eight, rival], "James Scott") == {}
    # So does shift 0: codes that are already the text.
    plain = [(char, font) for char in "Director"]
    assert _pdf_font_code_shifts([eight, plain], "James Scott Director") == {}
    assert _pdf_font_code_shifts([plain], "Director") == {}
    # A line whose unmapped characters are two fonts' is no evidence for either.
    mixed = _encode("James ", font, shift) + _encode("Scott", "ArialMT", 29)
    assert _pdf_font_code_shifts([mixed], "James Scott") == {}


# ---------------------------------------------------------------------------- built pages


def _png(width: int, height: int) -> bytes:
    pixmap = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, width, height), False)
    pixmap.clear_with(200)
    return pixmap.tobytes("png")


SCAN_PNG = _png(1275, 1650)


def _type3_font(document: fitz.Document, codes: set[int], name: str) -> int:
    """A Type 3 font whose glyphs' names (/g<code>) give MuPDF no Unicode."""
    procs = {}
    for code in sorted(codes):
        xref = document.get_new_xref()
        document.update_object(xref, "<< >>")
        document.update_stream(xref, b"500 0 d0")
        procs[code] = xref
    first, last = min(codes), max(codes)
    font = document.get_new_xref()
    document.update_object(
        font,
        "<< /Type /Font /Subtype /Type3 /Name /" + name + " /FontBBox [0 0 1000 1000]"
        " /FontMatrix [0.001 0 0 0.001 0 0]"
        " /CharProcs << " + " ".join(f"/g{c} {x} 0 R" for c, x in procs.items()) + " >>"
        " /Encoding << /Type /Encoding /Differences ["
        + " ".join(f"{c} /g{c}" for c in procs)
        + "] >>"
        f" /FirstChar {first} /LastChar {last}"
        " /Widths [" + " ".join("500" for _ in range(first, last + 1)) + "] >>",
    )
    return font


def _form_pdf(path: Path, lines: list[tuple[str, int | None]], *, name: str = "ShiftedT3") -> Path:
    """A page scan with typed lines: (text, shift) in a Type 3 font whose codes are
    ``shift`` below the text, or (text, None) in Helvetica, named ``name`` too."""
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=SCAN_PNG, keep_proportion=False)
    codes = {ord(c) - shift for text, shift in lines if shift is not None for c in text}
    fonts = {}
    if codes:
        fonts["F9"] = _type3_font(document, codes, name)
    helvetica = document.get_new_xref()
    document.update_object(
        helvetica,
        f"<< /Type /Font /Subtype /Type1 /BaseFont /{name} /Encoding /WinAnsiEncoding >>",
    )
    fonts["F8"] = helvetica
    stream = []
    for index, (text, shift) in enumerate(lines):
        y = 700 - 24 * index
        if shift is None:
            literal = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream.append(f"BT /F8 10 Tf 72 {y} Td ({literal}) Tj ET")
        else:
            hexed = "".join(f"{ord(c) - shift:02x}" for c in text)
            stream.append(f"BT /F9 10 Tf 72 {y} Td <{hexed}> Tj ET")
    # insert_image drew the scan and keeps the page resources in an object of their own.
    resources = int(document.xref_get_key(page.xref, "Resources")[1].split()[0])
    document.xref_set_key(
        resources, "Font", "<< " + " ".join(f"/{k} {x} 0 R" for k, x in fonts.items()) + " >>"
    )
    contents = document.get_new_xref()
    document.update_object(contents, "<< >>")
    document.update_stream(contents, "\n".join(stream).encode())
    document.xref_set_key(
        page.xref,
        "Contents",
        "[" + " ".join(f"{x} 0 R" for x in [*page.get_contents(), contents]) + "]",
    )
    document.save(path)
    document.close()
    return path


def _page_text(path: Path, ocr_text: str, monkeypatch, extraction: dict | None = None) -> str:
    monkeypatch.setattr(
        documents_module, "_ocr_pdf_page_text", lambda _page, *, extraction: ocr_text
    )
    with fitz.open(path) as document:
        return _pdf_page_text(document[0], extraction=extraction or {"ocr": True})


def _appended(ocr_text: str, result: str) -> list[str]:
    if result == ocr_text:
        return []
    head = ocr_text.rstrip("\n") + "\n\n"
    assert result.startswith(head)
    return result[len(head) :].split("\n")


# Codes 0x60 above ASCII: every one is above 0x7F, where MuPDF prints U+FFFD without
# TEXT_CID_FOR_UNKNOWN_UNICODE, so every character of the font is unmapped.
HIGH = -0x60


def test_a_shifted_fonts_typed_lines_ocr_missed_are_decoded(tmp_path, monkeypatch):
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("6/24/19", HIGH), ("Wendy Hill Petras", HIGH), ("Acting Deputy Director", HIGH)],
    )
    ocr = "18. DATE APPROVED: 6/24/19\n21. TYPED NAME: Wendy Hill Petras\n22. TITLE:\n"

    result = _page_text(pdf, ocr, monkeypatch)

    # The two lines OCR read are the evidence (20 letters and digits); the title it missed
    # is decoded and kept.
    assert _appended(ocr, result) == ["Acting Deputy Director"]


def test_a_span_its_fonts_shift_cannot_decode_is_left_out(tmp_path, monkeypatch):
    # U+007F in the title has code 0xDF, which the shift takes to U+007F, outside printable
    # ASCII. Raw, the span reads as Latin-1 letters ("¡ÃÔÉÎÇß¤..."), with no control
    # character to mark it, so it becomes a space and its line is dropped.
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("6/24/19", HIGH), ("Wendy Hill Petras", HIGH), ("Acting\x7fDirector", HIGH)],
    )
    ocr = "18. DATE APPROVED: 6/24/19\n21. TYPED NAME: Wendy Hill Petras\n"

    with fitz.open(pdf) as document:
        lines = _layer(document[0], ocr)

    assert lines == ["6/24/19", "Wendy Hill Petras"]
    assert _appended(ocr, _page_text(pdf, ocr, monkeypatch)) == []


def test_without_evidence_nothing_is_decoded(tmp_path, monkeypatch):
    pdf = _form_pdf(tmp_path / "form.pdf", [("6/24/19", HIGH), ("Acting Deputy Director", HIGH)])
    with fitz.open(pdf) as document:
        raw = document[0].get_text("text")
    ocr = "18. DATE APPROVED: 6/24/1\n"

    # OCR read neither line exactly, so the font's codes are not decoded, and the lines
    # are what #868 keeps of them: those without a control character.
    result = _page_text(pdf, ocr, monkeypatch)
    expected = [" ".join(line.split()) for line in raw.splitlines() if line.strip()]
    expected = [
        line
        for line in expected
        if not any(unicodedata.category(c) == "Cc" for c in line) and any(c.isalnum() for c in line)
    ]
    assert _appended(ocr, result) == expected
    assert "Acting Deputy Director" not in result


def test_without_ocr_text_the_layer_is_returned_as_it_is(tmp_path, monkeypatch):
    pdf = _form_pdf(tmp_path / "form.pdf", [("6/24/19", HIGH), ("Wendy Hill Petras", HIGH)])
    with fitz.open(pdf) as document:
        raw = document[0].get_text("text")

    assert _page_text(pdf, "  \n", monkeypatch) == raw


def test_unmapped_characters_are_exactly_the_unmapped_fonts_characters(tmp_path):
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("6/24/19", HIGH), ("Wendy Hill", HIGH), ("Anne M. Costello", None)],
        name="ArialMT",
    )
    with fitz.open(pdf) as document:
        page = document[0]
        flags = fitz.TEXTFLAGS_TEXT
        unmapped = documents_module._pdf_unmapped_characters(page, sort=False, flags=flags)
        chars = [
            (span["font"], char)
            for block in page.get_text("rawdict", flags=flags)["blocks"]
            for line in block.get("lines", ())
            for span in line["spans"]
            for char in span["chars"]
        ]
        without_flag = documents_module._pdf_unmapped_characters(
            page, sort=False, flags=flags & ~fitz.TEXT_CID_FOR_UNKNOWN_UNICODE
        )

    # Every character of the two shifted lines (spaces included: code 0x80) and none of
    # the mapped line, though all three are in fonts named ArialMT.
    shifted = [(*char["origin"], 0) for _, char in chars if ord(char["c"]) >= 0x80]
    assert len(shifted) == len("6/24/19") + len("Wendy Hill")
    assert unmapped == frozenset(shifted)
    # Without TEXT_CID_FOR_UNKNOWN_UNICODE no code is printed, so nothing is unmapped.
    assert without_flag == frozenset()


def _layer(page, ocr_text: str, extraction: dict | None = None) -> list[str]:
    """The layer lines ``_pdf_page_text`` merges, after decoding and garbled spans."""
    extraction = extraction or {}
    spans = _pdf_layer_lines(page, extraction=extraction)
    spans = _pdf_decoded_span_lines(page, spans, extraction=extraction, ocr_text=ocr_text)
    return [text for text, _ in _without_garbled_spans(spans)]


def test_a_mapped_span_sharing_the_shifted_fonts_name_is_never_changed(tmp_path, monkeypatch):
    # AL-20-0004 page 4 in small: a signature appearance in a mapped "ArialMT", and typed
    # lines in an unmapped font of the same name.
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [
            ("4/6/2020", HIGH),
            ("Anne Marie Costello", HIGH),
            ("NEW", HIGH),
            ("Anne M. Costello", None),
        ],
        name="ArialMT",
    )
    ocr = "Date: 4/6/2020\nAnne Marie Costello\nNEW\n"

    with fitz.open(pdf) as document:
        lines = _layer(document[0], ocr)
    result = _page_text(pdf, ocr, monkeypatch)

    # S8: the mapped line is read as it is; the shifted lines decode, and OCR read them.
    assert lines == ["4/6/2020", "Anne Marie Costello", "NEW", "Anne M. Costello"]
    assert _appended(ocr, result) == ["Anne M. Costello"]


def test_a_font_mixing_mapped_and_unmapped_characters_in_a_line_is_not_decoded_there(
    tmp_path, monkeypatch
):
    # Codes 31 below ASCII: MuPDF prints the printable codes of a Type 3 font whose glyph
    # names it does not know as themselves, as if mapped, and only the control codes show
    # as unmapped ("\x01" for a space here), in spans of their own. "6/24/19" and
    # "4/1/19" are all control codes, so wholly unmapped.
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("6/24/19", 31), ("4/1/19", 31), ("Acting Deputy Director", 31), ("Wendy", 31)],
    )
    ocr = "DATE APPROVED: 6/24/19\nEFFECTIVE: 4/1/19\n"

    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr)

    # The date lines give the shift (9 digits) and decode. The title line mixes mapped
    # letters and unmapped spaces, so none of its spans is decoded (a decoded "\x01" span
    # beside the raw letters would read as '"DUJOH %FQVUZ'), nor the letter-only line.
    assert [[span[0] for span in line] for line in decoded[:2]] == [["6/24/19"], ["4/1/19"]]
    assert decoded[2:] == spans[2:]
    assert "".join(span[0] for span in spans[2]) == '"DUJOH\x01%FQVUZ\x01%JSFDUPS'


def test_a_page_without_unmapped_characters_is_not_decoded(tmp_path):
    pdf = _form_pdf(
        tmp_path / "form.pdf", [("Associate Regional Administrator", None), ("3/31/14", None)]
    )
    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        # S7.
        assert _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text="3/31/14") == spans


def test_decoding_needs_the_rawdict_spans_to_be_the_dict_spans(tmp_path):
    pdf = _form_pdf(tmp_path / "form.pdf", [("6/24/19", HIGH), ("Wendy Hill Petras", HIGH)])
    ocr = "6/24/19 Wendy Hill Petras"
    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        assert _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr) != spans
        # Spans that are not the page's (another reading) are returned as they are.
        other = [[(text + "x", painted, font) for text, painted, font in line] for line in spans]
        assert _pdf_decoded_span_lines(page, other, extraction={}, ocr_text=ocr) == other


# ---------------------------------------------------------------------------- real pages

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "ocr_overlay" / "shifted_font_pages.json").read_text(
        encoding="utf-8"
    )
)
PAGES = FIXTURE["pages"]
LAYER_FIXTURE = json.loads(
    (
        Path(__file__).parent / "fixtures" / "ocr_overlay" / "cms_state_plan_layer_pages.json"
    ).read_text(encoding="utf-8")
)["pages"]
ALL_PAGES = {**PAGES, **LAYER_FIXTURE}
SPA = "{state}/policy/cms/medicaid-state-plan/spa/{rest}/approval-document/page-{page}"


def _real_page(page: dict, monkeypatch):
    content = (REPO_ROOT / page["pdf"]).read_bytes()
    assert hashlib.sha256(content).hexdigest() == page["pdf_sha256"]
    monkeypatch.setattr(
        documents_module, "_ocr_pdf_page_text", lambda _page, *, extraction: page["ocr_text"]
    )
    document = fitz.open(stream=content, filetype="pdf")
    return document, document[page["page"] - 1]


@pytest.mark.parametrize(
    ("state", "rest", "page", "added", "removed"),
    [
        # Minion Pro (+31). OCR read "6/24/19", "Wendy Hill Petras" and "Acting Deputy
        # Director"; "4/1/19" is typed where OCR read "4 /1/19", and the title has two
        # clipped copies. #868 kept the one garbled span without a control character.
        ("us-wa", "wa-19-0012", 3, ["4/1/19", "Acting Deputy D", "Deputy D"], ["%FQVUZ %"]),
        ("us-ma", "ma-20-0024", 3, ["09/30/20"], ["%JSFDUPS"]),
        (
            "us-or", "or-19-0002", 3,
            [
                "4, 13, 25, and 32",
                "5/28/19-State authorized a P&I change to blocks # 8 and 9",
                "10/31/19-State authorized a P&I change to blocks #8 and 9",
                "5/2/19",
                "11/7/19",
                "11/1/19",
                "David L. Meacham",
            ],
            [],
        ),
        (
            "us-wa", "wa-14-0003", 3,
            [
                "9/24/15: The state authorizes P&I changes to box 8 and box 9.",
                "1/01/14",
                "9/28/15",
                "David L. Meacham",
                "Associate Regional Administrator",
            ],
            [],
        ),
        # Times New Roman (+29): the typed dates.
        ("us-or", "or-15-0006", 3, ["11/30/15", "12/10/15", "12/01/15"], []),
        # Arial (+29), beside a mapped ArialMT signature of a shifted font's name: OCR read
        # every decoded line ("NEW", "Flexibilities among other", ...), and the garbled
        # "1(:" #868 kept is "NEW".
        ("us-al", "al-20-0004", 4, [], ["1(:"]),
        # "March 13, 2020": the "3" is a mapped Minion Pro of the same name, so the line is
        # not decoded (OCR read it).
        ("us-nv", "nv-20-0002", 3, [], []),
        # Every decoded line was read by OCR.
        ("us-md", "md-19-0003", 4, [], []),
        # The one-code-too-high signature strings are in a WinAnsi Helvetica that maps every
        # code, and on ID-20-0001 the same font object holds correct text: not decoded.
        ("us-id", "id-20-0001", 3, [], []),
        ("us-mo", "mo-20-0016", 3, [], []),
        # A Type 3 font whose codes are its glyphs in order of use: no shift reads it.
        ("us-ca", "ca-25-0037", 16, [], []),
    ],
)  # fmt: skip
def test_real_pages_append_exactly_the_reviewed_lines(
    state, rest, page, added, removed, monkeypatch
):
    fixture = PAGES[SPA.format(state=state, rest=rest, page=page)]
    ocr = fixture["ocr_text"]
    document, pdf_page = _real_page(fixture, monkeypatch)
    with document:
        result = _pdf_page_text(pdf_page, extraction={"ocr": True})
        # #868's page text: the same, with nothing decoded.
        monkeypatch.setattr(
            documents_module,
            "_pdf_decoded_span_lines",
            lambda page, span_lines, *, extraction, ocr_text: span_lines,
        )
        by_868 = _pdf_page_text(pdf_page, extraction={"ocr": True})

    lines, lines_868 = _appended(ocr, result), _appended(ocr, by_868)
    assert [line for line in lines if line not in lines_868] == added
    assert [line for line in lines_868 if line not in lines] == removed
    if not added and not removed:
        assert result == by_868


def test_the_mapped_signature_sharing_a_shifted_fonts_name_is_read_as_it_is(monkeypatch):
    # AL-20-0004 page 4: three ArialMT fonts, one (with a ToUnicode map) for the signature.
    fixture = PAGES[SPA.format(state="us-al", rest="al-20-0004", page=4)]
    document, pdf_page = _real_page(fixture, monkeypatch)
    with document:
        lines = _layer(pdf_page, fixture["ocr_text"])

    for line in ["Anne M. Costello -S", "Digitally signed by Anne M. Costello -S "]:
        assert line in lines
    assert "Section 1135(b) of the Social Security Act" in lines
    # The garbled-font codes, decoded: "COVID-19" and "89a" hold U+001C, a line break to
    # Python's splitlines().
    assert (
        "Medicaid Disaster Relief for the COVID-19 National Emergency: Modification of "
        "Telehealth and Copayment "
    ) in lines
    assert "COVID-19 National Emergency. Pages 89a - 89i" in lines
    assert "Deputy Director, Center for Medicaid & CHIP Services" in lines


def _raw_spans(pdf_page, extraction: dict) -> list[list[tuple[str, bool]]]:
    """Each rawdict span's characters and whether one is unmapped, walked here."""
    flags = _pdf_text_flags(extraction, default=fitz.TEXTFLAGS_TEXT)
    sort = bool(extraction.get("sort_text"))
    unmapped = documents_module._pdf_unmapped_characters(pdf_page, sort=sort, flags=flags)
    seen: dict[tuple, int] = {}
    out = []
    for block in pdf_page.get_text("rawdict", sort=sort, flags=flags).get("blocks", ()):
        for line in block.get("lines", ()):
            spans = []
            for span in line["spans"]:
                text, has_unmapped = "", False
                for char in span["chars"]:
                    origin = tuple(char["origin"])
                    k = seen.get(origin, 0)
                    seen[origin] = k + 1
                    text += char["c"]
                    has_unmapped |= (*origin, k) in unmapped and char["c"] != "�"
                spans.append((text, has_unmapped))
            out.append(spans)
    return out


@pytest.mark.parametrize("path", sorted(ALL_PAGES))
@pytest.mark.parametrize("extraction", [{}, {"sort_text": True}, {"ignore_actual_text": True}])
def test_real_pages_change_only_spans_with_unmapped_characters(path, extraction, monkeypatch):
    # S7 and S8 on every retained page, under every text option: the rawdict spans are the
    # dict spans (so decoding is not skipped), a span without an unmapped character and
    # every span's paint come through unchanged, and a page without one is unchanged.
    page = ALL_PAGES[path]
    document, pdf_page = _real_page(page, monkeypatch)
    with document:
        spans = _pdf_layer_lines(pdf_page, extraction=extraction)
        decoded = _pdf_decoded_span_lines(
            pdf_page, spans, extraction=extraction, ocr_text=page["ocr_text"]
        )
        raw = _raw_spans(pdf_page, extraction)

    assert [[text for text, _ in line] for line in raw] == [[s[0] for s in line] for line in spans]
    # Paint and font are never changed.
    assert [[s[1:] for s in line] for line in decoded] == [[s[1:] for s in line] for line in spans]
    for raw_line, line, decoded_line in zip(raw, spans, decoded, strict=True):
        for (_, has_unmapped), span, decoded_span in zip(raw_line, line, decoded_line, strict=True):
            if not has_unmapped:
                assert decoded_span == span
    if not any(has for line in raw for _, has in line):
        assert decoded == spans
