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
    font's shift kept only when it is the font's one shift with evidence and the evidence
    holds, with each distinct decoded line counted once at its most, at least 8 decoded
    letters or digits in lines of 4 or more, 4 distinct ones, from 2 of digits, capitals
    and small letters. A differential test against a definition written without range
    bookkeeping, with the thresholds as numbers rather than the module's constants.
S5. Round trip: ASCII lines written in a font by a shift k, read by OCR, give k back when
    the evidence is enough and no other shift has any, and decoding gives the lines back
    exactly; with too little evidence, no shift.
S6. The order of the lines, repeated lines, lines without unmapped characters, and lines
    that decode to another line's text with fewer decoded characters change nothing; shift
    0 is never returned.

Reading a page, ``_pdf_decoded_span_lines`` and ``_pdf_page_text`` (built PDFs, and
retained CMS pages with Tesseract's stored output):

S7. Decoding returns ``_pdf_layer_lines``' spans unchanged on a page without an unmapped
    character, and every span's paint and font unchanged on every page.
S8. A span without an unmapped character is never changed. A font is not decoded in a line
    where some of its characters are mapped, nor anywhere when another font object on the
    page has its name (two unmapped fonts of one name can number their glyphs differently),
    and a line is decoded whole or not at all.
S9. The unmapped characters are exactly those PyMuPDF's text trace, another device,
    reports as U+FFFD (a differential test on every retained page), and a character is
    paired with the other read's only where the reads agree at its origin
    (``_pdf_unmapped_status``).
"""

from __future__ import annotations

import hashlib
import json
import string
import unicodedata
from collections import Counter
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
    """S4, written out with the thresholds as numbers: per font and shift, the distinct
    decoded lines OCR reads (each at its most letters or digits) and their decoded glyphs."""
    found: dict[str, dict[int, dict[str, int]]] = {}
    glyphs: dict[tuple[str, int], set[str]] = {}
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
            new = [chr(ord(c) + shift) for c, f in chars if f]
            letters = sum(1 for c in new if c.isalnum())
            if letters >= 4 and _reference_reads(ocr_text, decoded):
                read = found.setdefault(font, {}).setdefault(shift, {})
                line = " ".join(decoded.split())
                read[line] = max(read.get(line, 0), letters)
                glyphs.setdefault((font, shift), set()).update(c for c in new if c.isalnum())

    def classes(seen: set[str]) -> int:
        return len({(c.isdigit(), c.isupper()) for c in seen})

    return {
        font: shift
        for font, by_shift in found.items()
        if len(by_shift) == 1
        for shift, read in by_shift.items()
        if shift
        and sum(read.values()) >= 8
        and len(glyphs[(font, shift)]) >= 4
        and classes(glyphs[(font, shift)]) >= 2
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
    glyphs = {c for text in texts for c in text if c.isalnum()}
    enough = (
        letters >= _PDF_SHIFT_LETTERS
        and len(glyphs) >= 4
        and len({(c.isdigit(), c.isupper()) for c in glyphs}) >= 2
    )

    shifts = _pdf_font_code_shifts(lines, ocr_text)

    # S5: the shift comes back when the evidence is enough (eight letters or digits, four
    # glyphs, two classes) and no other shift has any; the lines then decode to the text.
    reference = _reference_shifts(lines, ocr_text)
    assert shifts == reference
    if enough and shifts != {font: shift}:
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
    if not enough:
        assert shifts == {}


@st.composite
def partly_mapped_copies(draw, lines, shifts):
    """For some lines, a copy whose first characters are mapped: under the font's shift
    (the detected one, else any) it decodes to the same text with fewer decoded
    characters, the case where counting a text once per line made the order matter."""
    copies = []
    for chars in lines:
        fonts = {font for _, font in chars if font is not None}
        if len(fonts) != 1 or not draw(st.booleans()):
            continue
        (font,) = fonts
        shift = shifts.get(font) or draw(SHIFT)
        cut = draw(st.integers(min_value=0, max_value=len(chars)))
        prefix = []
        for char, char_font in chars[:cut]:
            code = ord(char) + shift if char_font is not None else ord(char)
            if char_font is not None and not 0x20 <= code <= 0x7E:
                break
            prefix.append((chr(code), None))  # the same character, mapped
        else:
            copies.append(prefix + chars[cut:])
    return copies


@settings(max_examples=300, deadline=None)
@given(
    page_lines(), st.lists(st.lists(MAPPED_CHAR, max_size=8), max_size=3), st.randoms(), st.data()
)
def test_line_order_repeats_and_mapped_lines_change_nothing(case, mapped, random, data):
    lines, ocr_text = case
    assume(ocr_text.split())
    lines = [
        *lines,
        *data.draw(partly_mapped_copies(lines, _pdf_font_code_shifts(lines, ocr_text))),
    ]
    shifts = _pdf_font_code_shifts(lines, ocr_text)

    shuffled = [*lines, *lines[:2], *mapped]
    random.shuffle(shuffled)
    # S6.
    assert _pdf_font_code_shifts(shuffled, ocr_text) == shifts
    assert _pdf_font_code_shifts(list(reversed(lines)), ocr_text) == shifts
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
    labelled = [
        [(c, None) for c in "Approved "] + _encode("J2a", font, shift),
        [(c, None) for c in "Signed "] + _encode("b3K", font, shift),
    ]
    assert _pdf_font_code_shifts(labelled, "Approved J2a Signed b3K") == {}
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


def test_evidence_must_show_the_shift_across_glyphs_and_classes():
    font = "T23"
    # The review's case: a font that numbers glyphs by first use gives "1234" and "1122"
    # codes 0-3 and 0011, and +49 reads both: eight digits, but four glyphs of one class.
    first_use = [[(chr(code), font) for code in codes] for codes in ((0, 1, 2, 3), (0, 0, 1, 1))]
    assert _pdf_font_code_shifts(first_use, "1234 1122") == {}
    # Digits alone, however many, are one class.
    digits = [_encode(text, font, 31) for text in ("12345678", "9/10/2020")]
    assert _pdf_font_code_shifts(digits, "12345678 9/10/2020") == {}
    # Two glyphs are too few, though from two classes and eight characters.
    two_glyphs = [_encode("11A1", font, 31), _encode("A1AA", font, 31)]
    assert _pdf_font_code_shifts(two_glyphs, "11A1 A1AA") == {}
    # Seven glyphs from three classes are enough.
    assert _pdf_font_code_shifts([_encode("Scott 2021", font, 31)], "Scott 2021") == {font: 31}


def test_evidence_does_not_depend_on_line_order():
    # The review's case: two lines decode to the same text, one wholly in the font (8
    # decoded letters or digits), one with a mapped prefix (4). Each text counts once, at
    # its most, in either order.
    font = "MinionPro-Regular"
    full = _encode("Scott 2021", font, 31)
    partial = [(char, None) for char in "Scott "] + _encode("2021", font, 31)
    assert _pdf_font_code_shifts([full, partial], "Scott 2021") == {font: 31}
    assert _pdf_font_code_shifts([partial, full], "Scott 2021") == {font: 31}


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


def _form_pdf(
    path: Path,
    lines: list[tuple],
    *,
    name: str = "ShiftedT3",
    mapped_name: str = "Helvetica",
    group_names: dict[int, str] | None = None,
) -> Path:
    """A page scan with typed lines (text, shift[, group[, y[, x]]]): in a Type 3 font
    whose codes are ``shift`` below the text, one font object per group, named ``name``
    unless ``group_names`` names its group; or, with shift None, in a Helvetica named
    ``mapped_name``. Lines run down from (72, 700) unless given a y and x; two lines at one
    y and x overprint."""
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=SCAN_PNG, keep_proportion=False)
    entries = [
        (line[0], line[1], line[2] if len(line) > 2 else 0, line[3] if len(line) > 3 else None)
        for line in lines
    ]
    xs = [line[4] if len(line) > 4 else 72 for line in lines]
    fonts = {}
    for group in sorted({group for _, shift, group, _ in entries if shift is not None}):
        codes = {
            ord(c) - shift
            for text, shift, g, _ in entries
            if g == group and shift is not None
            for c in text
        }
        fonts[f"T{group}"] = _type3_font(document, codes, (group_names or {}).get(group, name))
    if any(shift is None for _, shift, _, _ in entries):
        helvetica = document.get_new_xref()
        document.update_object(
            helvetica,
            f"<< /Type /Font /Subtype /Type1 /BaseFont /{mapped_name} /Encoding /WinAnsiEncoding >>",
        )
        fonts["F8"] = helvetica
    stream = []
    for index, ((text, shift, group, y), x) in enumerate(zip(entries, xs, strict=True)):
        y = 700 - 24 * index if y is None else y
        if shift is None:
            literal = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream.append(f"BT /F8 10 Tf {x} {y} Td ({literal}) Tj ET")
        else:
            hexed = "".join(f"{ord(c) - shift:02x}" for c in text)
            stream.append(f"BT /T{group} 10 Tf {x} {y} Td <{hexed}> Tj ET")
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
    shifted = {tuple(char["origin"]) for _, char in chars if ord(char["c"]) >= 0x80}
    assert len(shifted) == len("6/24/19") + len("Wendy Hill")
    assert {origin for origin, flags in unmapped.items() if any(flags)} == shifted
    assert all(flags in ((True,), (False,)) for flags in unmapped.values())
    # Without TEXT_CID_FOR_UNKNOWN_UNICODE no code is printed, so nothing is unmapped.
    assert without_flag == {}


def _layer(page, ocr_text: str, extraction: dict | None = None) -> list[str]:
    """The layer lines ``_pdf_page_text`` merges, after decoding and garbled spans."""
    extraction = extraction or {}
    spans = _pdf_layer_lines(page, extraction=extraction)
    spans = _pdf_decoded_span_lines(page, spans, extraction=extraction, ocr_text=ocr_text)
    return [text for text, _ in _without_garbled_spans(spans)]


TYPED_FORM = [("4/6/2020", HIGH), ("Anne Marie Costello", HIGH), ("NEW", HIGH)]
TYPED_OCR = "Date: 4/6/2020\nAnne Marie Costello\nNEW\n"


def test_a_shifted_font_decodes_beside_a_mapped_font_of_another_name(tmp_path, monkeypatch):
    pdf = _form_pdf(tmp_path / "form.pdf", [*TYPED_FORM, ("Anne M. Costello", None)])

    with fitz.open(pdf) as document:
        lines = _layer(document[0], TYPED_OCR)

    assert lines == ["4/6/2020", "Anne Marie Costello", "NEW", "Anne M. Costello"]
    assert _appended(TYPED_OCR, _page_text(pdf, TYPED_OCR, monkeypatch)) == ["Anne M. Costello"]


def test_a_shifted_font_sharing_its_name_with_a_mapped_font_is_not_decoded(tmp_path):
    # AL-20-0004 page 4 in small: a signature in a mapped "ArialMT", typed lines in an
    # unmapped font of the same name. Spans name fonts, not font objects, so the unmapped
    # font is not decoded; the mapped line is read as it is (S8).
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [*TYPED_FORM, ("Anne M. Costello", None)],
        name="ArialMT",
        mapped_name="ArialMT",
    )

    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=TYPED_OCR)
        counts = documents_module._pdf_font_span_name_counts(page)

    assert counts["ArialMT"] == 2
    assert decoded == spans
    assert ["Anne M. Costello"] in [[text for text, _, _ in line] for line in spans]


def test_two_unmapped_fonts_of_one_name_are_not_decoded(tmp_path, monkeypatch):
    # The review's case: font A (codes 0x60 above ASCII) writes "June 2020" and "Scott
    # 2021", which OCR reads; font B, of the same name, is 0x61 above. A's shift would read
    # B's unread "Wendy 6666" as "Vdmcx 5555".
    lines = [("June 2020", HIGH), ("Scott 2021", HIGH), ("Wendy 6666", -0x61, 1)]
    ocr = "June 2020\nSigned: Scott 2021\n"
    same = _form_pdf(tmp_path / "same.pdf", lines, name="ArialMT")
    with fitz.open(same) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        assert documents_module._pdf_font_span_name_counts(page)["ArialMT"] == 2
        assert _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr) == spans
    assert "Vdmcx" not in _page_text(same, ocr, monkeypatch)


def test_a_line_is_decoded_whole_or_not_at_all(tmp_path):
    # One line in two unmapped fonts: "Fees:" in font B (no evidence), "$40" in font A
    # (its shift found from two other lines). Decoding A alone would leave B's codes
    # beside it, so the line stays as read.
    pdf = tmp_path / "form.pdf"
    _form_pdf(
        pdf,
        [
            ("June 2020", HIGH),
            ("Scott 2021", HIGH),
            ("Fees:", -0x61, 1, 600, 72),
            ("$40", HIGH, 0, 600, 98),
        ],
        group_names={1: "OtherT3"},
    )
    ocr = "June 2020\nSigned: Scott 2021\n"
    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr)
    texts = ["".join(text for text, _, _ in line) for line in decoded]
    assert "June 2020" in texts and "Scott 2021" in texts
    mixed = [line for line in spans if len({font for _, _, font in line}) == 2]
    assert mixed and all(line in decoded for line in mixed)


def test_a_font_named_like_an_annotations_font_is_not_decoded(tmp_path):
    # get_text reads annotations' appearance streams and get_fonts does not list their
    # fonts, so those are counted too: here a FreeText note's Helvetica shares its name
    # with the unmapped font, which is therefore not decoded.
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("June 2020", HIGH), ("Scott 2021", HIGH), ("Wendy Hill", HIGH)],
        name="Helvetica",
    )
    with fitz.open(pdf) as document:
        page = document[0]
        note = page.add_freetext_annot(fitz.Rect(300, 100, 500, 140), "Note", fontsize=10)
        note.update()
        noted = fitz.open("pdf", document.tobytes())
    with noted:
        page = noted[0]
        spans = _pdf_layer_lines(page, extraction={})
        counts = documents_module._pdf_font_span_name_counts(page)
        decoded = _pdf_decoded_span_lines(
            page, spans, extraction={}, ocr_text="June 2020\nSigned: Scott 2021\n"
        )
    assert ["Note"] in [[text for text, _, _ in line] for line in spans]
    assert counts["Helvetica"] == 2
    assert decoded == spans


def test_unmapped_status_cases():
    # S9: a character pairs with the other read's only when the reads agree at its origin.
    status = documents_module._pdf_unmapped_status
    assert status("A", None, 1, 0) is False  # MuPDF's own spacing: nothing drawn there
    assert status("\x01", (True,), 1, 0) is True
    assert status("A", (False,), 1, 0) is False
    assert status("\x01", (True, True), 2, 1) is True
    # The review's case: mapped "F" and an unmapped code drawn at one origin. The reads
    # need not order them alike, so neither is known.
    assert status("F", (True, False), 2, 0) is None
    assert status("\x01", (True, False), 2, 1) is None
    # The reads draw different numbers of characters there.
    assert status("\x01", (True,), 2, 0) is None
    # U+FFFD with the flag is no code.
    assert status("\ufffd", (True,), 1, 0) is False


def test_characters_drawn_at_one_origin_by_mapped_and_unmapped_fonts_are_not_decoded(
    tmp_path,
):
    # A mapped "F" overprinted by an unmapped glyph: which one each read lists first is
    # unknown, so that line is not decoded, while the font's other lines are.
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("June 2020", HIGH), ("Scott 2021", HIGH), ("F", None, 0, 600), ("Q", HIGH, 0, 600)],
    )
    ocr = "June 2020\nSigned: Scott 2021\n"
    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr)
    texts = ["".join(text for text, _, _ in line) for line in decoded]
    assert "June 2020" in texts and "Scott 2021" in texts
    overprinted = [old for old in spans if any(text == "F" for text, _, _ in old)]
    assert overprinted and all(line in decoded for line in overprinted)


def test_a_partly_unmapped_type3_font_is_never_decoded(tmp_path):
    # Codes 31 below ASCII: MuPDF prints the printable codes of a Type 3 font whose glyph
    # names it does not know as themselves, as if mapped, and only the control codes show
    # as unmapped ("\x01" for a space here), in spans of their own. Those decode only to
    # digits and punctuation, one class, so no shift is found even from "6/24/19" and
    # "4/1/19", which OCR reads; and the title line mixes mapped and unmapped characters,
    # so it would not be decoded anyway (a decoded "\x01" span beside the raw letters
    # would read as '"DUJOH %FQVUZ').
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("6/24/19", 31), ("4/1/19", 31), ("Acting Deputy Director", 31), ("Wendy", 31)],
    )
    ocr = "DATE APPROVED: 6/24/19\nEFFECTIVE: 4/1/19\n"

    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr)

    assert decoded == spans
    assert "".join(span[0] for span in spans[2]) == '"DUJOH\x01%FQVUZ\x01%JSFDUPS'


def test_a_font_whose_characters_in_a_line_are_partly_mapped_is_not_decoded_there(tmp_path):
    # Codes 0x50 above ASCII: letters and digits land at 0x80 and up, where MuPDF has no
    # Unicode for them, but a space lands on "p", which it prints as if mapped. Lines with
    # no space show the shift; decoding only the unmapped characters of a line with one
    # would give "Wendyp1999".
    pdf = _form_pdf(
        tmp_path / "form.pdf", [("Scott2021", -0x50), ("June2020", -0x50), ("Wendy 1999", -0x50)]
    )
    ocr = "Scott2021\nJune2020\n"
    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr)

    assert [[text for text, _, _ in line] for line in decoded[:2]] == [["Scott2021"], ["June2020"]]
    assert decoded[2] == spans[2]


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
        # Director"; "4/1/19" is typed where OCR read "4 /1/19". The title has two clipped
        # copies: "Deputy D" decodes (#868 kept it garbled, "%FQVUZ %"), and "Acting Deputy
        # D" is drawn where another line's character is, so it is not decoded.
        ("us-wa", "wa-19-0012", 3, ["4/1/19", "Deputy D"], ["%FQVUZ %"]),
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
        # Arial (+29) decodes; the three ArialMT fonts (one mapped, for the signature)
        # share a name, so ArialMT is not decoded, nor any line mixing it with Arial. OCR
        # read every decoded line, and the garbled "1(:" #868 kept is "NEW".
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


def test_a_font_name_several_font_objects_carry_is_not_decoded(monkeypatch):
    # AL-20-0004 page 4: three ArialMT fonts (one, with a ToUnicode map, writes the
    # signature) and one Arial, all unmapped but that one.
    fixture = PAGES[SPA.format(state="us-al", rest="al-20-0004", page=4)]
    document, pdf_page = _real_page(fixture, monkeypatch)
    with document:
        spans = _pdf_layer_lines(pdf_page, extraction={})
        decoded = _pdf_decoded_span_lines(
            pdf_page, spans, extraction={}, ocr_text=fixture["ocr_text"]
        )
        counts = documents_module._pdf_font_span_name_counts(pdf_page)
        lines = _layer(pdf_page, fixture["ocr_text"])

    assert counts["ArialMT"] == 3 and counts["Arial"] == 1
    changed = [line for line, old in zip(decoded, spans, strict=True) if line != old]
    # Only lines wholly in Arial decode; a line with any ArialMT span is as read, so
    # "03/01/2020" (Arial "0" and "/01/2020", ArialMT "3") leaves no "0 /01/2020" fragment.
    assert all(font == "Arial" for line in changed for _, _, font in line)
    for line, old in zip(decoded, spans, strict=True):
        if any(font == "ArialMT" for _, _, font in old):
            assert line == old
    texts = ["".join(text for text, _, _ in line) for line in changed]
    assert "Section 1135(b) of the Social Security Act" in texts
    assert "Deputy Director, Center for Medicaid & CHIP Services" in texts
    # The mapped signature is read as it is.
    for line in ["Anne M. Costello -S", "Digitally signed by Anne M. Costello -S "]:
        assert line in lines
    assert not any(line.startswith("0 ") for line in lines)


def _traced_unmapped_origins(pdf_page) -> Counter:
    """Where the characters MuPDF has no Unicode for are drawn, from PyMuPDF's text trace,
    a device of its own that reports such a character as U+FFFD whatever the text flags."""
    return Counter(
        (round(char[2][0], 2), round(char[2][1], 2))
        for span in pdf_page.get_texttrace()
        for char in span["chars"]
        if char[0] == 0xFFFD
    )


def _raw_spans(pdf_page, extraction: dict) -> list[list[tuple[str, bool]]]:
    """Each rawdict span's characters and whether one is drawn where the text trace has an
    unmapped character (``_traced_unmapped_origins``), walked here."""
    flags = _pdf_text_flags(extraction, default=fitz.TEXTFLAGS_TEXT)
    sort = bool(extraction.get("sort_text"))
    traced = _traced_unmapped_origins(pdf_page)
    out = []
    for block in pdf_page.get_text("rawdict", sort=sort, flags=flags).get("blocks", ()):
        for line in block.get("lines", ()):
            spans = []
            for span in line["spans"]:
                text = "".join(char["c"] for char in span["chars"])
                has_unmapped = any(
                    (round(char["origin"][0], 2), round(char["origin"][1], 2)) in traced
                    for char in span["chars"]
                )
                spans.append((text, has_unmapped))
            out.append(spans)
    return out


@pytest.mark.parametrize("path", sorted(ALL_PAGES))
def test_unmapped_characters_are_those_the_text_trace_reports(path, monkeypatch):
    # A differential test: the two rawdict reads, matched by origin, find exactly the
    # characters PyMuPDF's text trace (another device) reports as U+FFFD, and where.
    page = ALL_PAGES[path]
    document, pdf_page = _real_page(page, monkeypatch)
    with document:
        found = documents_module._pdf_unmapped_characters(
            pdf_page, sort=False, flags=fitz.TEXTFLAGS_TEXT
        )
        traced = _traced_unmapped_origins(pdf_page)

    ours = Counter()
    for origin, unmapped in found.items():
        ours[(round(origin[0], 2), round(origin[1], 2))] += sum(unmapped)
    assert +ours == traced


@pytest.mark.parametrize("path", sorted(ALL_PAGES))
def test_spans_wholly_unmapped_are_those_mupdf_marks_as_codes(path, monkeypatch):
    # A second differential test: MuPDF marks a span whose characters are codes with
    # FZ_STEXT_UNICODE_IS_CID (char_flags 128). On every retained page that is exactly the
    # spans whose characters, MuPDF's own spaces aside, are all unmapped by the two reads.
    page = ALL_PAGES[path]
    document, pdf_page = _real_page(page, monkeypatch)
    with document:
        found = documents_module._pdf_unmapped_characters(
            pdf_page, sort=False, flags=fitz.TEXTFLAGS_TEXT
        )
        raw = pdf_page.get_text("rawdict", flags=fitz.TEXTFLAGS_TEXT)
    seen: Counter = Counter()
    for block in raw.get("blocks", ()):
        for line in block.get("lines", ()):
            for span in line["spans"]:
                unmapped = []
                for char in span["chars"]:
                    origin = (float(char["origin"][0]), float(char["origin"][1]))
                    k = seen[origin]
                    seen[origin] += 1
                    if char["c"] != " ":
                        flags = found.get(origin, ())
                        unmapped.append(k < len(flags) and flags[k])
                if unmapped and "char_flags" in span:
                    assert bool(int(span["char_flags"]) & 128) == all(unmapped), span["text"]


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
