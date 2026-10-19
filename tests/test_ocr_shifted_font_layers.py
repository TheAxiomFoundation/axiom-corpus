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
S6. The order of the lines, repeated lines and lines without unmapped characters change
    nothing; shift 0 is never returned. A line that decodes under a font's shift to a
    line's text with fewer decoded characters adds nothing to that shift's evidence: the
    font keeps its shift unless the line is evidence for another shift (then it has none),
    and no other font changes.

Reading a page, ``_pdf_decoded_span_lines`` and ``_pdf_page_text`` (built PDFs, and
retained CMS pages with Tesseract's stored output):

S7. Decoding returns ``_pdf_layer_lines``' spans unchanged on a page without an unmapped
    character, and every span's paint and font unchanged on every page. It runs after
    ``_with_layer_marks``, so under PyMuPDF 1.26 a font whose codes print as combining
    marks is decoded and its lines kept (1.28 moves the marks, and nothing is decoded).
S8. A span without an unmapped character is never changed. A font is not decoded in a line
    where some of its characters are mapped, nor anywhere when it is named "" (MuPDF's
    name for text in a font it can't load or drawn with no font) or another font object
    the page's text can be drawn in has its name, as MuPDF names spans: a Type0 font by its
    descendant, a Type 3 font by its /Name (one the cut leaves empty is "", only a missing
    /Name is "Unnamed-T3"), every name cut to 31 bytes. Those fonts include the fonts of
    forms, tiling patterns and every annotation's appearance, and what a graphics state
    reaches: the font a /Font entry in any object it reaches selects (a stream's
    dictionary included), the array written there or as an object of its own, whatever
    the font's /Type; and soft-mask groups, written as dictionaries or streams, reached
    through any object whatever it looks like (two unmapped fonts of one name can number
    their glyphs differently). A line is decoded whole or not at all: not when one of its
    characters, in any of its spans, would decode outside printable ASCII, nor when a span
    of it would still hold a control character.
S9. The unmapped characters are exactly those PyMuPDF's text trace, another device,
    reports as U+FFFD (a differential test on every retained page); every span holding one
    is one MuPDF marks UNICODE_IS_CID or _IS_GID; and a character is paired with the other
    read's only where the reads agree at its origin (``_pdf_unmapped_status``).
S10. Only a Type0 font is decoded, and only when its /W gives a width for every code it
    draws unmapped on the page and leaves a code without one between the least and the
    greatest of those (a font numbering its glyphs in order of use has a glyph for each),
    whatever the /W says elsewhere; it may be a font only an annotation draws. /W read back
    gives exactly the codes written, as merged ranges.
S11. When the page's fonts can't be known for certain (a font, a descendant, a graphics
    state's font or an annotation written inline; a /Subtype or /BaseFont not written in
    the font's dictionary; a /Subtype other than /Type0, /Type1, /MMType1, /TrueType and
    /Type3, whose type MuPDF guesses; an annotation, other than a Link or Popup, without a
    stored appearance MuPDF uses, a signature widget MuPDF reads as unsigned, or any such
    annotation when the form's /NeedAppearances is anything but absent or false, since
    MuPDF then makes the appearance itself in fonts it chooses; a reference printed
    with another generation or to an object the file lacks; a page tree deeper than the
    walk follows; or more distinct objects than it takes, each counted once), nothing on
    the page is decoded, and nothing raises.
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
    _with_layer_marks,
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


def _rival_shifts(lines, font: str, shift: int, ocr_text: str) -> set[int]:
    """The shifts other than ``shift`` that some line of ``font`` alone is evidence for."""
    return {
        other
        for other in _ALL_SHIFTS
        if other != shift
        for line in lines
        if {f for _, f in line if f is not None} == {font}
        and (decoded := _reference_decode(line, {font: other})) is not None
        and sum(1 for c, f in line if f and chr(ord(c) + other).isalnum())
        >= _PDF_SHIFT_LINE_LETTERS
        and _reference_reads(ocr_text, decoded)
    }


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
        assert _rival_shifts(lines, font, shift, ocr_text), "the shift was lost without a rival"
    if shifts == {font: shift}:
        assert [_pdf_decoded_layer_line(line, shifts) for line in lines] == texts
    if not enough:
        assert shifts == {}


@st.composite
def partly_mapped_copies(draw, lines, shifts):
    """For some lines of fonts with a shift, a copy whose first characters are mapped:
    under the font's shift it decodes to the same text with fewer decoded characters, the
    case where counting a text once per line made the order matter."""
    copies = []
    for chars in lines:
        fonts = {font for _, font in chars if font is not None}
        if len(fonts) != 1 or not fonts <= shifts.keys() or not draw(st.booleans()):
            continue
        (font,) = fonts
        shift = shifts[font]
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
    shifts = _pdf_font_code_shifts(lines, ocr_text)

    # S6: order, repeats and lines without unmapped characters change nothing.
    shuffled = [*lines, *lines[:2], *mapped]
    random.shuffle(shuffled)
    assert _pdf_font_code_shifts(shuffled, ocr_text) == shifts
    assert _pdf_font_code_shifts(list(reversed(lines)), ocr_text) == shifts
    assert 0 not in shifts.values()

    # S6: a line that decodes under a font's shift to a line's text with fewer decoded
    # characters adds nothing to that shift's evidence. The font keeps its shift unless
    # such a line is evidence for another shift, which leaves the font with none; no
    # other font changes.
    copies = data.draw(partly_mapped_copies(lines, shifts))
    with_copies = _pdf_font_code_shifts([*lines, *copies], ocr_text)
    assert with_copies.keys() <= shifts.keys()
    for font, shift in shifts.items():
        if with_copies.get(font) != shift:
            assert font not in with_copies
            assert _rival_shifts(copies, font, shift, ocr_text)


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


def test_a_shift_whose_greatest_code_decodes_to_the_last_printable_character():
    # The shift search runs up to the shift that takes a line's greatest code to "~"
    # (_PDF_SHIFT_LAST); a range one short would drop these lines as evidence. The
    # hypothesis alphabet stops at "z", so this pins the boundary directly.
    font = "MinionPro-Regular"
    lines = [_encode("Wendy 2019~", font, 31), _encode("Hill 2020~", font, 31)]
    ocr_text = "Signed: Wendy 2019~\nHill 2020~"
    assert max(ord(c) for line in lines for c, _ in line) + 31 == 0x7E
    assert _pdf_font_code_shifts(lines, ocr_text) == {font: 31}
    assert _reference_shifts(lines, ocr_text) == {font: 31}


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


def _type3_font(document: fitz.Document, codes: set[int], name: str | None) -> int:
    """A Type 3 font whose glyphs' names (/g<code>) give MuPDF no Unicode, named ``name``
    (without a /Name when None)."""
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
        "<< /Type /Font /Subtype /Type3"
        + ("" if name is None else " /Name /" + name)
        + " /FontBBox [0 0 1000 1000]"
        " /FontMatrix [0.001 0 0 0.001 0 0]"
        " /CharProcs << " + " ".join(f"/g{c} {x} 0 R" for c, x in procs.items()) + " >>"
        " /Encoding << /Type /Encoding /Differences ["
        + " ".join(f"{c} /g{c}" for c in procs)
        + "] >>"
        f" /FirstChar {first} /LastChar {last}"
        " /Widths [" + " ".join("500" for _ in range(first, last + 1)) + "] >>",
    )
    return font


def _type0_font(
    document: fitz.Document,
    codes: set[int],
    name: str,
    *,
    widths: set[int] | None = None,
    mapped: dict[int, str] | None = None,
    top: str | None = None,
) -> int:
    """A Type0 Identity-H font, not embedded, whose descendant is named ``name`` and which
    is itself named ``top`` (by default ``name``-Identity-H), whose /W gives widths for
    ``widths`` (by default the codes it draws) and whose ToUnicode map, if ``mapped`` gives
    one, maps only those codes. MuPDF reads a code below about 0x1000 of such a font through its
    substitute font's glyph order (code + 29), but has no Unicode for a higher one and
    prints the code, as for the shifted fonts' embedded programs, which name no glyph."""
    descriptor = document.get_new_xref()
    document.update_object(
        descriptor,
        f"<< /Type /FontDescriptor /FontName /{name} /Flags 32 /FontBBox [0 0 1000 1000]"
        " /ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 >>",
    )
    w = " ".join(f"{code} [500]" for code in sorted(codes if widths is None else widths))
    descendant = document.get_new_xref()
    document.update_object(
        descendant,
        f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{name}"
        " /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >>"
        f" /FontDescriptor {descriptor} 0 R /DW 1000 /W [{w}] /CIDToGIDMap /Identity >>",
    )
    to_unicode = ""
    if mapped:
        cmap = document.get_new_xref()
        document.update_object(cmap, "<< >>")
        entries = "\n".join(
            f"<{code:04X}> <{''.join(f'{ord(c):04X}' for c in text)}>"
            for code, text in sorted(mapped.items())
        )
        document.update_stream(
            cmap,
            (
                "/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
                "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
                "/CMapName /Adobe-Identity-UCS def /CMapType 2 def\n"
                "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
                f"{len(mapped)} beginbfchar\n{entries}\nendbfchar\n"
                "endcmap CMapName currentdict /CMap defineresource pop end end"
            ).encode(),
        )
        to_unicode = f" /ToUnicode {cmap} 0 R"
    font = document.get_new_xref()
    document.update_object(
        font,
        f"<< /Type /Font /Subtype /Type0 /BaseFont /{top or name + '-Identity-H'} /Encoding /Identity-H"
        f" /DescendantFonts [{descendant} 0 R]{to_unicode} >>",
    )
    return font


def _code(char: str, shift: int | dict[str, int]) -> int:
    """``char``'s code: ``shift`` below it, or the code a table gives it."""
    return shift[char] if isinstance(shift, dict) else ord(char) - shift


def _form_pdf(
    path: Path,
    lines: list[tuple],
    *,
    name: str | None = "Shifted",
    mapped_name: str = "Helvetica",
    group_names: dict[int, str | None] | None = None,
    kind: str = "type0",
    widths: dict[int, set[int]] | None = None,
    mapped: dict[int, dict[int, str]] | None = None,
    tops: dict[int, str] | None = None,
) -> Path:
    """A page scan with typed lines (text, shift[, group[, y[, x[, size]]]]): in a font
    whose codes are ``shift`` below the text (or, for a dict, the codes it gives), one font
    object per group, named ``name`` unless ``group_names`` names its group: a Type0 font
    (``_type0_font``, with ``widths`` and ``mapped`` for its group) or, with ``kind``
    "type3", a Type 3 font; or, with shift None, in a Helvetica named ``mapped_name``.
    Lines run down from (72, 700) in 10-point text unless given a y, x and size; two lines
    at one y and x overprint."""
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=SCAN_PNG, keep_proportion=False)
    entries = [
        (line[0], line[1], line[2] if len(line) > 2 else 0, line[3] if len(line) > 3 else None)
        for line in lines
    ]
    xs = [line[4] if len(line) > 4 else 72 for line in lines]
    sizes = [line[5] if len(line) > 5 else 10 for line in lines]
    fonts = {}
    for group in sorted({group for _, shift, group, _ in entries if shift is not None}):
        codes = {
            _code(c, shift)
            for text, shift, g, _ in entries
            if g == group and shift is not None
            for c in text
        }
        font_name = (group_names or {}).get(group, name)
        fonts[f"T{group}"] = (
            _type3_font(document, codes, font_name)
            if kind == "type3"
            else _type0_font(
                document,
                codes,
                font_name,
                widths=(widths or {}).get(group),
                mapped=(mapped or {}).get(group),
                top=(tops or {}).get(group),
            )
        )
    if any(shift is None for _, shift, _, _ in entries):
        helvetica = document.get_new_xref()
        document.update_object(
            helvetica,
            f"<< /Type /Font /Subtype /Type1 /BaseFont /{mapped_name} /Encoding /WinAnsiEncoding >>",
        )
        fonts["F8"] = helvetica
    stream = []
    digits = 2 if kind == "type3" else 4
    for index, ((text, shift, group, y), x, size) in enumerate(
        zip(entries, xs, sizes, strict=True)
    ):
        y = 700 - 24 * index if y is None else y
        if shift is None:
            literal = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream.append(f"BT /F8 {size} Tf {x} {y} Td ({literal}) Tj ET")
        else:
            hexed = "".join(f"{_code(c, shift):0{digits}x}" for c in text)
            stream.append(f"BT /T{group} {size} Tf {x} {y} Td <{hexed}> Tj ET")
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


# Type0 codes 0xE000 above ASCII, in the Private Use Area: MuPDF has no Unicode for any
# of them and prints each code as itself, neither a control character nor a mark.
PUA = -0xE000
# Type 3 codes 0x60 above ASCII: every one is above 0x7F, where MuPDF prints U+FFFD without
# TEXT_CID_FOR_UNKNOWN_UNICODE, so every character of the font is unmapped.
HIGH = -0x60


def test_a_shifted_fonts_typed_lines_ocr_missed_are_decoded(tmp_path, monkeypatch):
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("6/24/19", PUA), ("Wendy Hill Petras", PUA), ("Acting Deputy Director", PUA)],
    )
    ocr = "18. DATE APPROVED: 6/24/19\n21. TYPED NAME: Wendy Hill Petras\n22. TITLE:\n"

    result = _page_text(pdf, ocr, monkeypatch)

    # The two lines OCR read are the evidence (20 letters and digits); the title it missed
    # is decoded and kept.
    assert _appended(ocr, result) == ["Acting Deputy Director"]


def test_a_line_with_a_character_its_shift_cannot_decode_is_not_decoded(tmp_path):
    # U+007F in the title has code 0xE07F, which the shift takes to U+007F, outside
    # printable ASCII; the line is left as read (S8), the other two are decoded.
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("6/24/19", PUA), ("Wendy Hill Petras", PUA), ("Acting\x7fDirector", PUA)],
    )
    ocr = "18. DATE APPROVED: 6/24/19\n21. TYPED NAME: Wendy Hill Petras\n"

    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr)

    assert [[text for text, *_ in line] for line in decoded[:2]] == [
        ["6/24/19"],
        ["Wendy Hill Petras"],
    ]
    assert decoded[2] == spans[2]


def test_a_line_whose_spans_do_not_all_decode_is_not_decoded(tmp_path):
    # The review's case: one font's line "1234" and, in a span of its own (another size),
    # a character whose code the shift takes outside printable ASCII (U+00A0). Decoding
    # the first span alone would keep "1234" and lose the character, so the line is left
    # as read.
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [
            ("June 2020", PUA),
            ("Scott 2021", PUA),
            ("1234", PUA, 0, 600, 72, 10),
            ("\xa0", PUA, 0, 600, 96, 12),
        ],
    )
    ocr = "June 2020\nSigned: Scott 2021\n"
    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr)

    split = [line for line in spans if len(line) == 2]
    assert split and all(line in decoded for line in split)
    assert [[text for text, *_ in line] for line in decoded[:2]] == [["June 2020"], ["Scott 2021"]]


def test_without_evidence_nothing_is_decoded(tmp_path, monkeypatch):
    pdf = _form_pdf(tmp_path / "form.pdf", [("6/24/19", PUA), ("Acting Deputy Director", PUA)])
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
    pdf = _form_pdf(tmp_path / "form.pdf", [("6/24/19", PUA), ("Wendy Hill Petras", PUA)])
    with fitz.open(pdf) as document:
        raw = document[0].get_text("text")

    assert _page_text(pdf, "  \n", monkeypatch) == raw


def test_unmapped_characters_are_exactly_the_unmapped_fonts_characters(tmp_path):
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("6/24/19", HIGH), ("Wendy Hill", HIGH), ("Anne M. Costello", None)],
        name="ArialMT",
        kind="type3",
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
    """The layer lines ``_pdf_page_text`` merges: marks put back, then decoding, then
    garbled spans left out."""
    extraction = extraction or {}
    spans = _pdf_layer_lines(page, extraction=extraction)
    text = page.get_text(
        "text",
        sort=bool(extraction.get("sort_text")),
        flags=_pdf_text_flags(extraction, default=fitz.TEXTFLAGS_TEXT),
    )
    marked = _with_layer_marks(spans, text)
    assert marked is not None
    spans = _pdf_decoded_span_lines(page, marked, extraction=extraction, ocr_text=ocr_text)
    return [text for text, _ in _without_garbled_spans(spans)]


TYPED_FORM = [("4/6/2020", PUA), ("Anne Marie Costello", PUA), ("NEW", PUA)]
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
    assert ["Anne M. Costello"] in [[text for text, *_ in line] for line in spans]


def test_two_unmapped_fonts_of_one_name_are_not_decoded(tmp_path, monkeypatch):
    # The review's case: font A (codes 0xE000 above ASCII) writes "June 2020" and "Scott
    # 2021", which OCR reads; font B, of the same name, is 0xE001 above. A's shift would
    # read B's unread "Wendy 6666" as "Xfoez!7777".
    lines = [("June 2020", PUA), ("Scott 2021", PUA), ("Wendy 6666", PUA - 1, 1)]
    ocr = "June 2020\nSigned: Scott 2021\n"
    same = _form_pdf(tmp_path / "same.pdf", lines, name="ArialMT")
    with fitz.open(same) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        assert documents_module._pdf_font_span_name_counts(page)["ArialMT"] == 2
        assert _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr) == spans
    assert "Xfoez" not in _page_text(same, ocr, monkeypatch)


def test_a_line_is_decoded_whole_or_not_at_all(tmp_path):
    # One line in two unmapped fonts: "Fees:" in font B (no evidence), "$40" in font A
    # (its shift found from two other lines). Decoding A alone would leave B's codes
    # beside it, so the line stays as read.
    pdf = tmp_path / "form.pdf"
    _form_pdf(
        pdf,
        [
            ("June 2020", PUA),
            ("Scott 2021", PUA),
            ("Fees:", PUA - 1, 1, 600, 72),
            ("$40", PUA, 0, 600, 98),
        ],
        group_names={1: "Other"},
    )
    ocr = "June 2020\nSigned: Scott 2021\n"
    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr)
    texts = ["".join(text for text, *_ in line) for line in decoded]
    assert "June 2020" in texts and "Scott 2021" in texts
    mixed = [line for line in spans if len({font for _, _, font, *_ in line}) == 2]
    assert mixed and all(line in decoded for line in mixed)


def test_a_font_named_like_an_annotations_font_is_not_decoded(tmp_path):
    # get_text reads annotations' appearance streams and get_fonts does not list their
    # fonts, so those are counted too: here a FreeText note's Helvetica shares its name
    # with the unmapped font, which is therefore not decoded.
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("June 2020", PUA), ("Scott 2021", PUA), ("Wendy Hill", PUA)],
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
    assert ["Note"] in [[text for text, *_ in line] for line in spans]
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
        [("June 2020", PUA), ("Scott 2021", PUA), ("F", None, 0, 600), ("Q", PUA, 0, 600)],
    )
    ocr = "June 2020\nSigned: Scott 2021\n"
    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr)
    texts = ["".join(text for text, *_ in line) for line in decoded]
    assert "June 2020" in texts and "Scott 2021" in texts
    overprinted = [old for old in spans if any(text == "F" for text, *_ in old)]
    assert overprinted and all(line in decoded for line in overprinted)


def test_a_partly_unmapped_type3_font_is_never_decoded(tmp_path):
    # Codes 31 below ASCII: MuPDF prints the printable codes of a Type 3 font whose glyph
    # names it does not know as themselves, as if mapped, and only the control codes show
    # as unmapped ("\x01" for a space here), in spans of their own. A Type 3 font is not
    # decoded (S10); were it, the title line, which mixes mapped and unmapped characters,
    # would not be (a decoded "\x01" span beside the raw letters would read as
    # '"DUJOH %FQVUZ').
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("6/24/19", 31), ("4/1/19", 31), ("Acting Deputy Director", 31), ("Wendy", 31)],
        kind="type3",
    )
    ocr = "DATE APPROVED: 6/24/19\nEFFECTIVE: 4/1/19\n"

    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr)

    assert decoded == spans
    assert "".join(span[0] for span in spans[2]) == '"DUJOH\x01%FQVUZ\x01%JSFDUPS'


def test_a_font_whose_characters_in_a_line_are_partly_mapped_is_not_decoded_there(tmp_path):
    # The font's ToUnicode map gives "y" the character "q". Lines without a "y" show the
    # shift; decoding only the unmapped characters of the line with one would give
    # "Wendq 1999".
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("Scott2021", PUA), ("June2020", PUA), ("Wendy 1999", PUA)],
        mapped={0: {ord("y") - PUA: "q"}},
    )
    ocr = "Scott2021\nJune2020\n"
    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        decoded = _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr)

    assert [[text for text, *_ in line] for line in decoded[:2]] == [["Scott2021"], ["June2020"]]
    assert "q" in "".join(text for text, *_ in spans[2])
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
    pdf = _form_pdf(tmp_path / "form.pdf", [("6/24/19", PUA), ("Wendy Hill Petras", PUA)])
    ocr = "6/24/19 Wendy Hill Petras"
    with fitz.open(pdf) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        assert _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr) != spans
        # Spans that are not the page's (another reading) are returned as they are.
        other = [[(text + "x", *rest) for text, *rest in line] for line in spans]
        assert _pdf_decoded_span_lines(page, other, extraction={}, ocr_text=ocr) == other


def _decoded(path: Path, ocr_text: str):
    """The page's layer spans and ``_pdf_decoded_span_lines``' result for them."""
    with fitz.open(path) as document:
        page = document[0]
        spans = _pdf_layer_lines(page, extraction={})
        return spans, _pdf_decoded_span_lines(page, spans, extraction={}, ocr_text=ocr_text)


def _texts(lines) -> list[str]:
    return ["".join(text for text, *_ in line) for line in lines]


EVIDENCE = [("June 2020", PUA), ("Scott 2021", PUA)]
# Before PyMuPDF 1.27 a combining mark keeps its own place in its line.
_MARKS_KEEP_THEIR_PLACE = tuple(fitz.pymupdf_version_tuple[:2]) < (1, 27)
EVIDENCE_OCR = "June 2020\nSigned: Scott 2021\n"


@pytest.mark.parametrize("name", ["T23", None])
def test_a_type3_font_is_never_decoded(tmp_path, name):
    # Every character of the Type 3 font is unmapped (codes 0x80 and up) and OCR reads two
    # lines' worth of evidence, but only a Type0 font is decoded (S10). The spans of a Type
    # 3 font without a /Name are named "Unnamed-T3" by PyMuPDF 1.26 and "Type3 (<n> 0 R)"
    # by 1.28; it is counted under both, so a collision is seen on either.
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [("June 2020", HIGH), ("Scott 2021", HIGH), ("Wendy Hill", HIGH)],
        name=name,
        kind="type3",
    )
    spans, decoded = _decoded(pdf, EVIDENCE_OCR)
    with fitz.open(pdf) as document:
        page = document[0]
        unmapped = documents_module._pdf_unmapped_characters(
            page, sort=False, flags=fitz.TEXTFLAGS_TEXT
        )
        counts = documents_module._pdf_font_span_name_counts(page)
        (font,) = [font for font in page.get_fonts(full=True) if font[2] == "Type3"]

    assert all(all(flags) for flags in unmapped.values())
    assert decoded == spans
    if name is None:
        assert counts["Unnamed-T3"] == counts[f"Type3 ({font[0]} 0 R)"] == 1


def test_a_font_numbering_glyphs_in_order_of_use_is_not_decoded(tmp_path):
    # The review's case: a font numbers its glyphs from 0xE000 in the order they are first
    # used, and its first eleven are "89:;<=>?@AB", so one shift reads that line and
    # "8899AABB", which OCR reads: twelve letters and digits, four glyphs, two classes. The
    # next glyph, "x", gets the next code, which the shift would read as "C". Every code
    # from the least to the greatest it draws on the page has a glyph, so /W, giving each
    # a width, leaves no gap there, and the font is not decoded (S10). That holds however
    # /W is written: dense, or (review round 3) with .notdef at code 0 and so a gap below
    # the codes drawn, or with one more width far above them.
    table = {char: 0xE000 + index for index, char in enumerate("89:;<=>?@ABx")}
    lines = [("89:;<=>?@AB", table), ("8899AABB", table), ("xB", table)]
    ocr = "89:;<=>?@AB\n8899AABB\n"
    for label, widths in (
        ("dense", None),
        ("notdef", {0: {0, *table.values()}}),
        ("above", {0: {*table.values(), 0xE0F0}}),
    ):
        pdf = _form_pdf(tmp_path / f"{label}.pdf", lines, widths=widths)
        spans, decoded = _decoded(pdf, ocr)
        assert decoded == spans, label
        assert "CB" not in _texts(decoded), label


def test_a_font_whose_widths_miss_a_code_it_draws_is_not_decoded(tmp_path):
    # /W gives no width for the code of "W": the array is not the font's glyphs, so it
    # says nothing about their order, and the font is not decoded (S10).
    lines = [*EVIDENCE, ("Wendy Hill", PUA)]
    codes = {ord(char) - PUA for text, _ in lines for char in text}
    missing = _form_pdf(tmp_path / "missing.pdf", lines, widths={0: codes - {ord("W") - PUA}})
    whole = _form_pdf(tmp_path / "whole.pdf", lines)

    spans, decoded = _decoded(missing, EVIDENCE_OCR)
    assert decoded == spans
    assert "Wendy Hill" in _texts(_decoded(whole, EVIDENCE_OCR)[1])


def test_a_font_whose_codes_print_as_combining_marks_is_decoded(tmp_path, monkeypatch):
    # The review's case in small: the font's codes print as characters from U+1D9F up,
    # "A" to "D" as combining marks (U+1DC0 to U+1DC3), and the shift is plain from
    # "ABCD1234", which OCR reads. Decoded before ``_with_layer_marks``, the spans would
    # lack marks the text output holds, the marks could not be placed, and the page would
    # fall back to the text output's undecoded lines. ``_pdf_page_text`` places the marks
    # first, against the text as printed, so "BAD 4321" is decoded and kept (S7).
    # PyMuPDF 1.28 gives a combining mark the origin of the character before it and can
    # carry a line's leading marks onto the line above ("1234" then the marks of "BAD"),
    # so there the built lines are not the lines drawn and nothing is decoded.
    shift = ord("A") - 0x1DC0
    pdf = _form_pdf(tmp_path / "form.pdf", [("ABCD1234", shift), ("BAD 4321", shift)])

    spans, decoded = _decoded(pdf, "ABCD1234\n")
    result = _page_text(pdf, "ABCD1234\n", monkeypatch)
    assert any(unicodedata.category(char) == "Mn" for char in "".join(_texts(spans)))
    if not _MARKS_KEEP_THEIR_PLACE:
        assert decoded == spans
        assert "BAD" not in result
        return
    assert _texts(decoded) == ["ABCD1234", "BAD 4321"]
    assert _appended("ABCD1234\n", result) == ["BAD 4321"]


def _noted(path: Path) -> Path:
    """``path`` with a FreeText note (a Helvetica appearance) added to its page."""
    with fitz.open(path) as document:
        note = document[0].add_freetext_annot(fitz.Rect(300, 100, 500, 140), "Note", fontsize=10)
        note.update()
        noted = path.with_name("noted-" + path.name)
        document.save(noted)
    return noted


def test_an_annotation_font_whose_name_is_not_written_in_it_stops_decoding(tmp_path):
    # The review's case: the note's font has /BaseFont 70 0 R, an object holding /ArialMT,
    # and MuPDF names its spans ArialMT. Read bare, the key would give "70 0 R" and leave
    # the page's unmapped ArialMT counted once. Which object carries a name is then not
    # known for certain, so nothing on the page is decoded (S11).
    pdf = _noted(_form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)], name="ArialMT"))
    with fitz.open(pdf) as document:
        page = document[0]
        assert documents_module._pdf_font_span_name_counts(page)["ArialMT"] == 1
        (font,) = documents_module._pdf_drawn_font_xrefs(page) - {
            font[0] for font in page.get_fonts(full=True)
        }
        name = document.get_new_xref()
        document.update_object(name, "/ArialMT")
        document.xref_set_key(font, "BaseFont", f"{name} 0 R")
        document.save(tmp_path / "indirect.pdf")
    with fitz.open(tmp_path / "indirect.pdf") as document:
        page = document[0]
        span_fonts = {
            span["font"]
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", ())
            for span in line["spans"]
            if span["text"] == "Note"
        }
        counts = documents_module._pdf_font_span_name_counts(page)
    spans, decoded = _decoded(tmp_path / "indirect.pdf", EVIDENCE_OCR)

    assert span_fonts == {"ArialMT"}
    assert counts == Counter()
    assert decoded == spans


def test_object_references_of_another_generation_stop_decoding(tmp_path):
    references = documents_module._pdf_object_references
    assert references("<< /N 50 0 R /D << /On 51 0 R /Off 52 0 R >> >>") == [50, 51, 52]
    assert references("<< /N 50 1 R >>") is None
    # The review's case: an appearance referred to as "50 1 R", which a lookup by number
    # may not reach, so its fonts are not known (S11).
    pdf = _noted(_form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)]))
    with fitz.open(pdf) as document:
        page = document[0]
        (annotation, *_) = page.annot_xrefs()[0]
        (stream,) = references(document.xref_get_key(annotation, "AP")[1])
        document.xref_set_key(annotation, "AP", f"<< /N {stream} 1 R >>")
        assert documents_module._pdf_drawn_font_xrefs(page) is None
        assert documents_module._pdf_font_span_name_counts(page) == Counter()


def test_a_walk_beyond_its_limit_stops_decoding(tmp_path, monkeypatch):
    # The review's case: a walk that stops at its limit knows only some fonts, so it gives
    # none (S11). This page has two resource holders, its own and the note's appearance
    # (and its scan image, which has no resources).
    pdf = _noted(_form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)]))
    with fitz.open(pdf) as document:
        page = document[0]
        assert len(documents_module._pdf_drawn_font_xrefs(page)) == 2
        monkeypatch.setattr(documents_module, "_PDF_RESOURCE_WALK", 1)
        assert documents_module._pdf_drawn_font_xrefs(page) is None
        assert documents_module._pdf_font_span_name_counts(page) == Counter()


def test_width_ranges_examples():
    codes = documents_module._pdf_width_ranges
    # As PyMuPDF prints a real font's /W (MA-20-0024's Minion Pro, abridged); ranges that
    # meet are merged.
    assert codes("[1[227]13[228]15[228 331 480]18 20 480]") == [(1, 1), (13, 13), (15, 20)]
    assert codes("[]") == []
    assert codes("[1 [227] 5]") is None  # cut short
    assert codes("[1 2 0 R]") is None  # an indirect width
    assert codes("[0 70000 500]") is None  # beyond a two-byte CID
    assert codes("[5 3 500]") is None
    assert codes("12 0 R") is None


@settings(max_examples=300, deadline=None)
@given(
    st.lists(
        st.tuples(st.integers(0, 0xFF00), st.integers(1, 40), st.booleans(), st.booleans()),
        max_size=8,
    )
)
def test_width_ranges_are_the_codes_written(runs):
    # S10: /W read back gives exactly the codes written, in either form, however spaced,
    # as sorted ranges that neither overlap nor meet.
    entries, expected = [], set()
    for first, length, as_range, tight in runs:
        last = first + length - 1
        expected.update(range(first, last + 1))
        widths = " ".join(["500"] * length)
        entries.append(
            f"{first} {last} 500" if as_range else f"{first}[{widths}]" if tight else f"{first} [ {widths} ]"
        )
    ranges = documents_module._pdf_width_ranges("[" + " ".join(entries) + "]")
    assert {code for first, last in ranges for code in range(first, last + 1)} == expected
    assert all(last + 1 < first for (_, last), (first, _) in zip(ranges, ranges[1:], strict=False))


def _font_object(document: fitz.Document, base: str) -> int:
    font = document.get_new_xref()
    document.update_object(font, f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} >>")
    return font


def _form(document: fitz.Document, stream: bytes, resources: str, bbox: str = "0 0 612 792") -> int:
    form = document.get_new_xref()
    document.update_object(
        form, f"<< /Type /XObject /Subtype /Form /BBox [{bbox}] /Resources << {resources} >> >>"
    )
    document.update_stream(form, stream)
    return form


def _annotate(path: Path, out: Path, stream: bytes, resources: str, subtype: str = "Square") -> Path:
    """``path`` with an annotation of ``subtype`` whose appearance draws ``stream`` (in a
    form over the whole page) with ``resources``."""
    with fitz.open(path) as document:
        page = document[0]
        form = _form(document, stream, resources)
        annotation = document.get_new_xref()
        document.update_object(
            annotation,
            f"<< /Type /Annot /Subtype /{subtype} /Rect [0 0 612 792] /F 4 /AP << /N {form} 0 R >> >>",
        )
        kind, value = document.xref_get_key(page.xref, "Annots")
        existing = value.strip("[]") if kind == "array" else ""
        document.xref_set_key(page.xref, "Annots", f"[{existing} {annotation} 0 R]")
        document.save(out)
    return out


def test_a_type0_font_is_named_by_its_descendant(tmp_path):
    # The review's case: font B is a Type0 font named Arial-Identity-H over a descendant
    # named ArialMT, and MuPDF names its spans ArialMT, as it does font A's. Counted by
    # B's own name, ArialMT would have one object, and A's shift, with B's codes in A's
    # /W, would read B's "Wendy 6666" as "Xfoez!7777". Both are counted as ArialMT.
    lines = [*EVIDENCE, ("Wendy 6666", PUA - 1, 1)]
    a_codes = {ord(char) - PUA for text, _ in EVIDENCE for char in text}
    b_codes = {ord(char) - PUA + 1 for char in "Wendy 6666"}
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        lines,
        group_names={0: "ArialMT", 1: "ArialMT"},
        tops={1: "Arial-Identity-H"},
        widths={0: a_codes | b_codes},
    )
    spans, decoded = _decoded(pdf, EVIDENCE_OCR)
    with fitz.open(pdf) as document:
        page = document[0]
        assert {font[3] for font in page.get_fonts(full=True)} == {
            "ArialMT-Identity-H",
            "Arial-Identity-H",
        }
        assert {span[2] for line in spans for span in line} == {"ArialMT"}
        assert documents_module._pdf_font_span_name_counts(page)["ArialMT"] == 2
    assert decoded == spans


def test_font_names_are_cut_as_mupdf_cuts_them(tmp_path):
    # The review's case: MuPDF keeps 31 bytes of a name, then PyMuPDF drops the subset
    # prefix, so "ABCDEF+ABCDEFGHIJKLMNOPQRSTUVWXExtra" names its spans as
    # "ABCDEFGHIJKLMNOPQRSTUVWX" does. Both fonts are counted under that name.
    short, long = "ABCDEFGHIJKLMNOPQRSTUVWX", "ABCDEF+ABCDEFGHIJKLMNOPQRSTUVWXExtra"
    pdf = _form_pdf(
        tmp_path / "form.pdf",
        [*EVIDENCE, ("Wendy6666", PUA - 1, 1)],
        group_names={0: short, 1: long},
    )
    spans, decoded = _decoded(pdf, EVIDENCE_OCR)
    with fitz.open(pdf) as document:
        counts = documents_module._pdf_font_span_name_counts(document[0])
    assert {span[2] for line in spans for span in line} == {short}
    assert counts[short] == 2
    assert decoded == spans


def test_a_soft_mask_groups_fonts_are_counted(tmp_path):
    # The review's case: MuPDF extracts text in a soft-mask group, and get_fonts does not
    # list its font, so a font of the unmapped font's name there must be counted.
    base = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)], name="Courier")
    masked = tmp_path / "masked.pdf"
    with fitz.open(base) as document:
        page = document[0]
        font = _font_object(document, "Courier")
        group = _form(
            document, b"BT /M1 12 Tf 72 500 Td (MaskText) Tj ET", f"/Font << /M1 {font} 0 R >>"
        )
        resources = int(document.xref_get_key(page.xref, "Resources")[1].split()[0])
        document.xref_set_key(
            resources, "ExtGState", f"<< /GS1 << /SMask << /S /Luminosity /G {group} 0 R >> >> >>"
        )
        contents = document.get_new_xref()
        document.update_object(contents, "<< >>")
        document.update_stream(contents, b"q /GS1 gs 0 g 50 400 300 200 re f Q")
        document.xref_set_key(
            page.xref,
            "Contents",
            "[" + " ".join(f"{x} 0 R" for x in [*page.get_contents(), contents]) + "]",
        )
        document.save(masked)
    spans, decoded = _decoded(masked, EVIDENCE_OCR)
    with fitz.open(masked) as document:
        page = document[0]
        assert font not in {f[0] for f in page.get_fonts(full=True)}
        assert documents_module._pdf_font_span_name_counts(page)["Courier"] == 2
    assert ["MaskText"] in [[t for t, *_ in line] for line in spans]
    assert decoded == spans


def test_an_annotation_of_any_subtype_is_walked(tmp_path):
    # An annotation PyMuPDF does not list (its /Subtype is /Foo) still has its appearance
    # drawn and its text extracted; its Times-Bold shares the unmapped font's name.
    base = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)], name="Times-Bold")
    with fitz.open(base) as document:
        font = _font_object(document, "Times-Bold")
        document.save(tmp_path / "fonted.pdf")
    pdf = _annotate(
        tmp_path / "fonted.pdf",
        tmp_path / "unknown.pdf",
        b"BT /A1 12 Tf 72 500 Td (AnnotText) Tj ET",
        f"/Font << /A1 {font} 0 R >>",
        subtype="Foo",
    )
    spans, decoded = _decoded(pdf, EVIDENCE_OCR)
    with fitz.open(pdf) as document:
        page = document[0]
        assert page.annot_xrefs() == []
        assert documents_module._pdf_font_span_name_counts(page)["Times-Bold"] == 2
    assert ["AnnotText"] in [[t for t, *_ in line] for line in spans]
    assert decoded == spans


def test_a_tiling_patterns_fonts_are_walked(tmp_path):
    base = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE])
    with fitz.open(base) as document:
        page = document[0]
        font = _font_object(document, "Times-Roman")
        pattern = document.get_new_xref()
        document.update_object(
            pattern,
            "<< /Type /Pattern /PatternType 1 /PaintType 1 /TilingType 1 /BBox [0 0 200 50]"
            f" /XStep 200 /YStep 50 /Resources << /Font << /P1 {font} 0 R >> >> >>",
        )
        document.update_stream(pattern, b"BT /P1 12 Tf 5 20 Td (PatternText) Tj ET")
        resources = int(document.xref_get_key(page.xref, "Resources")[1].split()[0])
        document.xref_set_key(resources, "Pattern", f"<< /Pa {pattern} 0 R >>")
        assert font in documents_module._pdf_drawn_font_xrefs(page)
        assert font not in {f[0] for f in page.get_fonts(full=True)}


def test_broken_annotations_stop_decoding_without_an_error(tmp_path, monkeypatch):
    # The reviews' cases: an annotation written inline (as FPDF writes a link), an
    # appearance referring to an object the file does not have, and an unused font
    # resource doing so. PyMuPDF raises on each; the walk gives "not known", so nothing is
    # decoded and the page is read as #868 reads it.
    lines = [*EVIDENCE, ("Wendy Hill", PUA)]
    cases = {}
    base = _form_pdf(tmp_path / "form.pdf", lines)
    with fitz.open(base) as document:
        page = document[0]
        document.xref_set_key(
            page.xref, "Annots", "[<< /Type /Annot /Subtype /Link /Rect [0 0 10 10] >>]"
        )
        cases["inline"] = tmp_path / "inline.pdf"
        document.save(cases["inline"])
    with fitz.open(base) as document:
        page = document[0]
        annotation = document.get_new_xref()
        document.update_object(
            annotation, "<< /Type /Annot /Subtype /Square /Rect [0 0 10 10] /AP << /N 999999 0 R >> >>"
        )
        document.xref_set_key(page.xref, "Annots", f"[{annotation} 0 R]")
        cases["dangling"] = tmp_path / "dangling.pdf"
        document.save(cases["dangling"])
    noted = _noted(base)
    with fitz.open(noted) as document:
        page = document[0]
        (annotation, *_) = page.annot_xrefs()[0]
        (stream,) = documents_module._pdf_object_references(document.xref_get_key(annotation, "AP")[1])
        document.xref_set_key(stream, "Resources/Font/Unused", "999999 0 R")
        cases["unused"] = tmp_path / "unused.pdf"
        document.save(cases["unused"])
    for label, path in cases.items():
        spans, decoded = _decoded(path, EVIDENCE_OCR)
        with fitz.open(path) as document:
            assert documents_module._pdf_drawn_font_xrefs(document[0]) is None, label
        assert decoded == spans, label
        assert "Wendy Hill" not in _page_text(path, EVIDENCE_OCR, monkeypatch), label


def test_annotation_fonts_written_inline_or_typed_indirectly_stop_decoding(tmp_path):
    # S11's other cases: a font written inline in an appearance's resources, and a note's
    # font whose /Subtype refers to another object.
    lines = [*EVIDENCE, ("Wendy Hill", PUA)]
    inline = _annotate(
        _form_pdf(tmp_path / "form.pdf", lines),
        tmp_path / "inline.pdf",
        b"BT /A1 12 Tf 72 500 Td (AnnotText) Tj ET",
        "/Font << /A1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >>",
    )
    noted = _noted(_form_pdf(tmp_path / "form2.pdf", lines))
    with fitz.open(noted) as document:
        page = document[0]
        (font,) = documents_module._pdf_drawn_font_xrefs(page) - {
            font[0] for font in page.get_fonts(full=True)
        }
        subtype = document.get_new_xref()
        document.update_object(subtype, "/Type1")
        document.xref_set_key(font, "Subtype", f"{subtype} 0 R")
        document.save(tmp_path / "typed.pdf")
    for path in (inline, tmp_path / "typed.pdf"):
        spans, decoded = _decoded(path, EVIDENCE_OCR)
        with fitz.open(path) as document:
            assert documents_module._pdf_font_span_name_counts(document[0]) == Counter()
        assert decoded == spans


def test_an_annotations_own_type0_font_is_decoded(tmp_path):
    # The review's case: a unique unmapped Type0 font drawn only in an annotation's
    # appearance, its /W covering every code it draws with a gap, writes "June2020" and
    # "Scott2021", which OCR reads, and "WendyHill", which it does not; it is decoded.
    texts = ["June2020", "Scott2021", "WendyHill"]
    base = _form_pdf(tmp_path / "form.pdf", [("Note", None)])
    with fitz.open(base) as document:
        codes = {ord(char) - PUA for text in texts for char in text}
        font = _type0_font(document, codes, "Shifted")
        document.save(tmp_path / "fonted.pdf")
    stream = b"\n".join(
        f"BT /T0 10 Tf 300 {600 - 24 * index} Td <{''.join(f'{ord(c) - PUA:04x}' for c in text)}> Tj ET".encode()
        for index, text in enumerate(texts)
    )
    pdf = _annotate(tmp_path / "fonted.pdf", tmp_path / "annotated.pdf", stream, f"/Font << /T0 {font} 0 R >>")

    spans, decoded = _decoded(pdf, "June2020\nScott2021\n")
    assert "WendyHill" in _texts(decoded)
    assert "WendyHill" not in _texts(spans)


def test_a_line_left_with_a_control_character_is_not_decoded(tmp_path):
    # The review's case: AL-20-0004's "03/01/2020" with its "3" in a mapped font whose map
    # gives U+0016 (a Type 3 glyph named uni0016, which MuPDF maps in both reads). Decoding
    # the rest would leave "0 /01/2020" once that span is left out as garbled, so the line
    # is left as read.
    # The font's /W gives widths for the split line's codes too, which it draws as well.
    drawn = {ord(char) - PUA for char in "June 2020 Scott 2021 0/01/2020"}
    pdf = _form_pdf(tmp_path / "form.pdf", EVIDENCE, widths={0: drawn})
    with fitz.open(pdf) as document:
        page = document[0]
        procedure = document.get_new_xref()
        document.update_object(procedure, "<< >>")
        document.update_stream(procedure, b"500 0 d0")
        odd = document.get_new_xref()
        document.update_object(
            odd,
            "<< /Type /Font /Subtype /Type3 /Name /Odd /FontBBox [0 0 1000 1000]"
            f" /FontMatrix [0.001 0 0 0.001 0 0] /CharProcs << /uni0016 {procedure} 0 R >>"
            " /Encoding << /Type /Encoding /Differences [51 /uni0016] >>"
            " /FirstChar 51 /LastChar 51 /Widths [500] >>",
        )
        resources = int(document.xref_get_key(page.xref, "Resources")[1].split()[0])
        fonts = document.xref_get_key(resources, "Font")[1]
        document.xref_set_key(resources, "Font", fonts.replace(">>", f" /O3 {odd} 0 R >>", 1))
        shifted = "".join(f"{ord(c) - PUA:04x}" for c in "/01/2020")
        contents = document.get_new_xref()
        document.update_object(contents, "<< >>")
        document.update_stream(
            contents,
            (
                f"BT /T0 10 Tf 72 600 Td <{ord('0') - PUA:04x}> Tj ET"
                " BT /O3 10 Tf 77 600 Td (3) Tj ET"
                f" BT /T0 10 Tf 82 600 Td <{shifted}> Tj ET"
            ).encode(),
        )
        document.xref_set_key(
            page.xref,
            "Contents",
            "[" + " ".join(f"{x} 0 R" for x in [*page.get_contents(), contents]) + "]",
        )
        document.save(tmp_path / "odd.pdf")
    spans, decoded = _decoded(tmp_path / "odd.pdf", EVIDENCE_OCR)
    split = [line for line in spans if any("\x16" in text for text, *_ in line)]
    assert split and all(len(line) == 3 for line in split)
    assert all(line in decoded for line in split)
    assert [[text for text, *_ in line] for line in decoded[:2]] == [["June 2020"], ["Scott 2021"]]


def _draw(document: fitz.Document, page, resource: str, key: str, xref: int, content: bytes) -> None:
    """Add ``xref`` to the page's ``resource`` dictionary under ``key`` and ``content`` to its
    page content."""
    resources = int(document.xref_get_key(page.xref, "Resources")[1].split()[0])
    kind, value = document.xref_get_key(resources, resource)
    entries = value.strip()[2:-2] if kind == "dict" else ""
    document.xref_set_key(resources, resource, f"<< {entries} /{key} {xref} 0 R >>")
    contents = document.get_new_xref()
    document.update_object(contents, "<< >>")
    document.update_stream(contents, content)
    document.xref_set_key(
        page.xref,
        "Contents",
        "[" + " ".join(f"{x} 0 R" for x in [*page.get_contents(), contents]) + "]",
    )


@pytest.mark.parametrize("indirect", [False, True])
def test_a_type3_fonts_name_is_cut_as_mupdf_cuts_it(tmp_path, indirect):
    # Review round 4: MuPDF cuts a Type 3 font's /Name, direct or indirect, to 31 bytes, as
    # it does every font's (checked under PyMuPDF 1.26.7 and 1.28.2). A Type 3 font named
    # "ABCDEF+ABCDEFGHIJKLMNOPQRSTUVWXExtra" shares its spans' name with the Type0 font
    # named "ABCDEFGHIJKLMNOPQRSTUVWX", which is therefore not decoded.
    short, long = "ABCDEFGHIJKLMNOPQRSTUVWX", "ABCDEF+ABCDEFGHIJKLMNOPQRSTUVWXExtra"
    pdf = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)], name=short)
    with fitz.open(pdf) as document:
        page = document[0]
        font = _type3_font(document, {65}, long)
        if indirect:
            name = document.get_new_xref()
            document.update_object(name, "/" + long)
            document.xref_set_key(font, "Name", f"{name} 0 R")
        _draw(document, page, "Font", "L3", font, b"BT /L3 10 Tf 72 400 Td (A) Tj ET")
        document.save(tmp_path / "type3.pdf")
    spans, decoded = _decoded(tmp_path / "type3.pdf", EVIDENCE_OCR)
    with fitz.open(tmp_path / "type3.pdf") as document:
        counts = documents_module._pdf_font_span_name_counts(document[0])
    assert {span[2] for line in spans for span in line} == {short}
    assert counts[short] == 2 and long[7:] not in counts
    assert decoded == spans


def test_a_long_type3_name_does_not_shadow_a_font_named_as_it_reads_uncut(tmp_path):
    # The converse: the Type 3 font is named only by its cut name, so a Type0 font named
    # "ABCDEFGHIJKLMNOPQRSTUVWXExtra" (29 bytes, kept whole) stays unique and is decoded.
    whole, long = "ABCDEFGHIJKLMNOPQRSTUVWXExtra", "ABCDEF+ABCDEFGHIJKLMNOPQRSTUVWXExtra"
    pdf = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)], name=whole)
    with fitz.open(pdf) as document:
        page = document[0]
        font = _type3_font(document, {65}, long)
        _draw(document, page, "Font", "L3", font, b"BT /L3 10 Tf 72 400 Td (A) Tj ET")
        document.save(tmp_path / "type3.pdf")
    _, decoded = _decoded(tmp_path / "type3.pdf", EVIDENCE_OCR)
    with fitz.open(tmp_path / "type3.pdf") as document:
        assert documents_module._pdf_font_span_name_counts(document[0])[whole] == 1
    assert "Wendy Hill" in _texts(decoded)


def test_a_soft_mask_written_as_a_stream_is_followed(tmp_path):
    # Review round 4: /ExtGState << /GS1 << /SMask S 0 R >> >>, where S is a stream whose
    # dictionary holds the group in /G. MuPDF extracts the group's text; the walk follows
    # S's references as well as walking it as a holder.
    pdf = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)], name="Courier")
    with fitz.open(pdf) as document:
        page = document[0]
        font = _font_object(document, "Courier")
        group = _form(
            document, b"BT /M1 12 Tf 72 500 Td (MaskText) Tj ET", f"/Font << /M1 {font} 0 R >>"
        )
        mask = document.get_new_xref()
        document.update_object(mask, f"<< /S /Luminosity /G {group} 0 R >>")
        document.update_stream(mask, b"")
        state = document.get_new_xref()
        document.update_object(state, f"<< /SMask {mask} 0 R >>")
        _draw(document, page, "ExtGState", "GS1", state, b"q /GS1 gs 0 g 50 400 300 200 re f Q")
        document.save(tmp_path / "masked.pdf")
    spans, decoded = _decoded(tmp_path / "masked.pdf", EVIDENCE_OCR)
    with fitz.open(tmp_path / "masked.pdf") as document:
        assert documents_module._pdf_font_span_name_counts(document[0])["Courier"] == 2
    assert ["MaskText"] in [[t for t, *_ in line] for line in spans]
    assert decoded == spans


def test_a_graphics_states_font_with_an_indirect_type_is_counted(tmp_path):
    # Review round 4: /ExtGState << /GS2 << /Font [B 0 R 12] >> >>, B's /Type an indirect
    # /Font. MuPDF draws "GsText" in B; the walk resolves the /Type and counts B.
    pdf = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)], name="Courier")
    with fitz.open(pdf) as document:
        page = document[0]
        kind = document.get_new_xref()
        document.update_object(kind, "/Font")
        font = document.get_new_xref()
        document.update_object(font, f"<< /Type {kind} 0 R /Subtype /Type1 /BaseFont /Courier >>")
        state = document.get_new_xref()
        document.update_object(state, f"<< /Font [{font} 0 R 12] >>")
        _draw(document, page, "ExtGState", "GS2", state, b"q /GS2 gs BT 72 450 Td (GsText) Tj ET Q")
        document.save(tmp_path / "gs.pdf")
    spans, decoded = _decoded(tmp_path / "gs.pdf", EVIDENCE_OCR)
    with fitz.open(tmp_path / "gs.pdf") as document:
        assert documents_module._pdf_font_span_name_counts(document[0])["Courier"] == 2
    assert ["GsText"] in [[t for t, *_ in line] for line in spans]
    assert decoded == spans


def test_resources_inherited_from_too_far_up_stop_decoding(tmp_path):
    # Review round 4: a page whose resources sit more than 64 page-tree nodes above it. The
    # walk does not follow that far, so the fonts are not known; three nodes up is fine.
    pdf = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)])
    with fitz.open(pdf) as document:
        page = document[0]
        resources = document.xref_get_key(page.xref, "Resources")[1]
        own = documents_module._pdf_drawn_font_xrefs(page)

        def chain(depth: int) -> int:
            node = document.get_new_xref()
            document.update_object(node, f"<< /Type /Pages /Kids [] /Count 0 /Resources {resources} >>")
            for _ in range(depth):
                below = document.get_new_xref()
                document.update_object(below, f"<< /Type /Pages /Kids [] /Count 0 /Parent {node} 0 R >>")
                node = below
            return node

        document.xref_set_key(page.xref, "Resources", "null")
        document.xref_set_key(page.xref, "Parent", f"{chain(3)} 0 R")
        assert documents_module._pdf_drawn_font_xrefs(page) == own
        document.xref_set_key(page.xref, "Parent", f"{chain(70)} 0 R")
        assert documents_module._pdf_drawn_font_xrefs(page) is None


def test_a_type0_font_with_an_inline_descendant_stops_decoding(tmp_path):
    # Review round 4: B's /DescendantFonts holds an inline CIDFont named /Shared whose one
    # reference is its FontDescriptor, which has an extra /BaseFont /Other. Read as "the
    # one reference", the descriptor would pass for the descendant and name B "Other";
    # the array must be exactly one reference, so B can't be named and nothing is decoded.
    lines = [*EVIDENCE, ("Wendy6666", PUA - 1, 1)]
    pdf = _form_pdf(tmp_path / "form.pdf", lines, group_names={0: "Shared", 1: "Shared"})
    with fitz.open(pdf) as document:
        page = document[0]
        resources = int(document.xref_get_key(page.xref, "Resources")[1].split()[0])
        (b,) = documents_module._pdf_object_references(document.xref_get_key(resources, "Font/T1")[1])
        (old,) = documents_module._pdf_object_references(document.xref_get_key(b, "DescendantFonts")[1])
        descriptor = document.get_new_xref()
        document.update_object(
            descriptor,
            "<< /Type /FontDescriptor /FontName /Shared /BaseFont /Other /Flags 32"
            " /FontBBox [0 0 1000 1000] /ItalicAngle 0 /Ascent 800 /Descent -200"
            " /CapHeight 700 /StemV 80 >>",
        )
        inline = document.xref_object(old).replace(
            document.xref_get_key(old, "FontDescriptor")[1], f"{descriptor} 0 R"
        )
        document.xref_set_key(b, "DescendantFonts", f"[{inline}]")
        assert documents_module._pdf_descendant(document, b) is None
        assert documents_module._pdf_descendant(document, old) is None  # not a Type0 font
        document.save(tmp_path / "inline.pdf")
    spans, decoded = _decoded(tmp_path / "inline.pdf", EVIDENCE_OCR)
    with fitz.open(tmp_path / "inline.pdf") as document:
        assert documents_module._pdf_font_span_name_counts(document[0]) == Counter()
    assert decoded == spans


def test_a_reference_met_twice_counts_once_against_the_limit(tmp_path, monkeypatch):
    # Review round 4: a form referred to twice (/Again and /F1) is one holder. This page
    # has four: its own, its scan image and two forms. The walk takes the last reference
    # first, so /Again, written first, is met last, after all four are walked.
    pdf = _form_pdf(tmp_path / "form.pdf", EVIDENCE)
    with fitz.open(pdf) as document:
        page = document[0]
        resources = int(document.xref_get_key(page.xref, "Resources")[1].split()[0])
        (image,) = documents_module._pdf_object_references(document.xref_get_key(resources, "XObject")[1])
        first, second = _form(document, b"", ""), _form(document, b"", "")
        document.xref_set_key(
            resources,
            "XObject",
            f"<< /Again {first} 0 R /Im0 {image} 0 R /F1 {first} 0 R /F2 {second} 0 R >>",
        )
        monkeypatch.setattr(documents_module, "_PDF_RESOURCE_WALK", 4)
        assert documents_module._pdf_drawn_font_xrefs(page) is not None
        monkeypatch.setattr(documents_module, "_PDF_RESOURCE_WALK", 3)
        assert documents_module._pdf_drawn_font_xrefs(page) is None


def _graphics_state(document: fitz.Document, page, key: str, entries: str, content: bytes, inline: bool) -> None:
    """A graphics state ``<< entries >>`` under ``key`` in the page's ExtGState, as an object
    of its own or written inline there, and ``content`` added to the page."""
    resources = int(document.xref_get_key(page.xref, "Resources")[1].split()[0])
    if inline:
        document.xref_set_key(resources, "ExtGState", f"<< /{key} << {entries} >> >>")
        _draw(document, page, "XObject", "Nothing", _form(document, b"", ""), content)
        return
    state = document.get_new_xref()
    document.update_object(state, f"<< {entries} >>")
    _draw(document, page, "ExtGState", key, state, content)


@pytest.mark.parametrize("inline", [False, True])
def test_a_graphics_states_font_without_a_type_is_counted(tmp_path, inline):
    # Review round 5: /ExtGState << /GS2 << /Font [B 0 R 10] >> >> selects Type0 B, named
    # Shared like the page's unmapped A, and B and its descendant have no /Type. The
    # walk reads the /Font entry itself and knows a font by its /Subtype as well.
    lines = [*EVIDENCE, ("Wendy Hill", PUA)]
    a_codes = {ord(char) - PUA for text, _ in lines for char in text}
    b_codes = {ord(char) - PUA + 1 for char in "Wendy6666"}
    pdf = _form_pdf(tmp_path / "form.pdf", lines, name="Shared", widths={0: a_codes | b_codes})
    with fitz.open(pdf) as document:
        page = document[0]
        b = _type0_font(document, b_codes, "Shared")
        (descendant,) = documents_module._pdf_object_references(
            document.xref_get_key(b, "DescendantFonts")[1]
        )
        document.xref_set_key(b, "Type", "null")
        document.xref_set_key(descendant, "Type", "null")
        hexed = "".join(f"{code:04x}" for code in (ord(c) - PUA + 1 for c in "Wendy6666"))
        _graphics_state(
            document,
            page,
            "GS2",
            f"/Font [{b} 0 R 10]",
            f"q /GS2 gs BT 72 450 Td <{hexed}> Tj ET Q".encode(),
            inline,
        )
        document.save(tmp_path / "gs.pdf")
    spans, decoded = _decoded(tmp_path / "gs.pdf", EVIDENCE_OCR)
    with fitz.open(tmp_path / "gs.pdf") as document:
        assert documents_module._pdf_font_span_name_counts(document[0])["Shared"] == 2
    b_line = "".join(chr(ord(c) - PUA + 1) for c in "Wendy6666")
    assert b_line in _texts(spans)  # MuPDF draws B
    assert decoded == spans
    assert "Xfoez7777" not in _texts(decoded)


@pytest.mark.parametrize("inline", [False, True])
def test_a_graphics_state_font_written_inline_stops_decoding(tmp_path, inline):
    # Review round 5: an inline font in a graphics state's /Font entry can't be counted.
    pdf = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)])
    with fitz.open(pdf) as document:
        page = document[0]
        _graphics_state(
            document,
            page,
            "GS3",
            "/Font [<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> 10]",
            b"q /GS3 gs BT 72 450 Td (Inline) Tj ET Q",
            inline,
        )
        document.save(tmp_path / "inline.pdf")
    spans, decoded = _decoded(tmp_path / "inline.pdf", EVIDENCE_OCR)
    with fitz.open(tmp_path / "inline.pdf") as document:
        assert documents_module._pdf_drawn_font_xrefs(document[0]) is None
    assert decoded == spans


@pytest.mark.parametrize("name", ["ABCDEF+", ""])
def test_a_type3_name_that_cuts_to_nothing_names_its_spans_nothing(tmp_path, name):
    # Review round 5: an explicit /Name that the cut leaves empty ("/ABCDEF+", or "/")
    # names a Type 3 font's spans "", as MuPDF does under 1.26.7 and 1.28.2; only a font
    # with no /Name at all is "Unnamed-T3". A Type0 font whose descendant is /ABCDEF+ is
    # "" too, so the two share the name and neither is decoded.
    pdf = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)], name="ABCDEF+")
    with fitz.open(pdf) as document:
        page = document[0]
        font = _type3_font(document, {65}, name)
        _draw(document, page, "Font", "E3", font, b"BT /E3 10 Tf 72 400 Td (A) Tj ET")
        document.save(tmp_path / "empty.pdf")
    spans, decoded = _decoded(tmp_path / "empty.pdf", EVIDENCE_OCR)
    with fitz.open(tmp_path / "empty.pdf") as document:
        counts = documents_module._pdf_font_span_name_counts(document[0])
    assert {span[2] for line in spans for span in line} == {""}
    assert counts[""] == 2 and "Unnamed-T3" not in counts
    assert decoded == spans


def test_the_walk_limit_counts_each_object_once(tmp_path, monkeypatch):
    # Review round 5: a soft-mask group is reached as a graphics-state object and walked
    # as a holder; it is one object against the limit. This page reaches four: itself,
    # its scan image, the group and the group's font.
    pdf = _form_pdf(tmp_path / "form.pdf", EVIDENCE, name="Courier")
    with fitz.open(pdf) as document:
        page = document[0]
        font = _font_object(document, "Courier")
        group = _form(
            document, b"BT /M1 12 Tf 72 500 Td (MaskText) Tj ET", f"/Font << /M1 {font} 0 R >>"
        )
        state = document.get_new_xref()
        document.update_object(state, f"<< /SMask << /S /Luminosity /G {group} 0 R >> >>")
        _draw(document, page, "ExtGState", "GS1", state, b"q /GS1 gs 0 g 50 400 300 200 re f Q")
        monkeypatch.setattr(documents_module, "_PDF_RESOURCE_WALK", 5)
        assert documents_module._pdf_drawn_font_xrefs(page) is not None
        monkeypatch.setattr(documents_module, "_PDF_RESOURCE_WALK", 4)
        assert documents_module._pdf_drawn_font_xrefs(page) is None


def _shared_rival(tmp_path: Path, name: str, build) -> tuple[list, list, set[int] | None, Counter]:
    """The page with A, named Shared, drawing EVIDENCE and "Wendy Hill" unmapped, and with
    /W widths for the codes "Wendy6666" takes one above them too, after ``build(document,
    page)`` adds a rival; its spans, the decoded spans, its drawn fonts and its counts."""
    lines = [*EVIDENCE, ("Wendy Hill", PUA)]
    a_codes = {ord(char) - PUA for text, _ in lines for char in text}
    widths = a_codes | {ord(char) - PUA + 1 for char in "Wendy6666"}
    pdf = _form_pdf(tmp_path / "form.pdf", lines, name="Shared", widths={0: widths})
    with fitz.open(pdf) as document:
        build(document, document[0])
        document.save(tmp_path / name)
    spans, decoded = _decoded(tmp_path / name, EVIDENCE_OCR)
    with fitz.open(tmp_path / name) as document:
        drawn = documents_module._pdf_drawn_font_xrefs(document[0])
        counts = documents_module._pdf_font_span_name_counts(document[0])
    return spans, decoded, drawn, counts


B_CODES = {ord(char) - PUA + 1 for char in "Wendy6666"}
B_HEX = "".join(f"{ord(char) - PUA + 1:04x}" for char in "Wendy6666")
B_LINE = "".join(chr(ord(char) - PUA + 1) for char in "Wendy6666")


@pytest.mark.parametrize("inline", [False, True])
def test_a_graphics_states_font_array_written_as_an_object_is_read(tmp_path, inline):
    # Review round 6 (the author's check): /ExtGState << /GS2 << /Font F 0 R >> >>, F the
    # array [B 0 R 10] as an object of its own. B is named Shared like A, and B and its
    # descendant have /Type /Foo; MuPDF draws in B all the same (1.26.7 and 1.28.2). The
    # walk reads the array and takes B whatever its /Type, so A is not decoded.
    fonts = {}

    def build(document, page):
        b = fonts["B"] = _type0_font(document, B_CODES, "Shared")
        (descendant,) = documents_module._pdf_object_references(
            document.xref_get_key(b, "DescendantFonts")[1]
        )
        document.xref_set_key(b, "Type", "/Foo")
        document.xref_set_key(descendant, "Type", "/Foo")
        array = document.get_new_xref()
        document.update_object(array, f"[{b} 0 R 10]")
        content = f"q /GS2 gs BT 72 450 Td <{B_HEX}> Tj ET Q".encode()
        _graphics_state(document, page, "GS2", f"/Font {array} 0 R", content, inline)

    spans, decoded, drawn, counts = _shared_rival(tmp_path, "array.pdf", build)
    assert B_LINE in _texts(spans)  # MuPDF draws B
    assert drawn is not None and fonts["B"] in drawn and counts["Shared"] == 2
    assert decoded == spans


@pytest.mark.parametrize("guess", ["Type0", "Type3"])
def test_a_font_whose_type_mupdf_guesses_is_not_named(tmp_path, guess):
    # Review round 6 (the author's check): MuPDF loads a font of another /Subtype as the
    # type its /DescendantFonts or /CharProcs suggest, and names its spans as that type's:
    # by the descendant, or by the /Name (1.26.7 and 1.28.2). B, /Subtype /Foo, prints
    # "Shared" so, though its own /BaseFont says otherwise. Such a font is not named, so
    # the page's fonts are not known and A is not decoded.
    fonts = {}

    def build(document, page):
        if guess == "Type0":
            b = _type0_font(document, B_CODES, "Shared")
            content = f"BT /B1 10 Tf 72 450 Td <{B_HEX}> Tj ET".encode()
        else:
            b = _type3_font(document, {65}, "Shared")
            document.xref_set_key(b, "BaseFont", "/Other")
            content = b"BT /B1 10 Tf 72 450 Td (A) Tj ET"
        document.xref_set_key(b, "Subtype", "/Foo")
        fonts["B"] = b
        _draw(document, page, "Font", "B1", b, content)

    spans, decoded, _, counts = _shared_rival(tmp_path, "guessed.pdf", build)
    assert {span[2] for line in spans for span in line} == {"Shared"}
    assert (B_LINE if guess == "Type0" else "A") in _texts(spans)  # MuPDF draws B as Shared
    with fitz.open(tmp_path / "guessed.pdf") as document:
        assert documents_module._pdf_font_names(document[0], fonts["B"]) is None
    assert counts == Counter()
    assert decoded == spans


@pytest.mark.parametrize("missing", [False, True])
def test_a_font_named_nothing_is_never_decoded(tmp_path, missing):
    # Review round 6 (the author's check): MuPDF names "" the spans of a font it can't load
    # and of text drawn in a font the resources lack (1.26.7 and 1.28.2), which have no
    # font object to count. A, whose descendant is /ABCDEF+, is "" as well, so it is never
    # decoded, with such text on the page or without.
    pdf = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)], name="ABCDEF+")
    with fitz.open(pdf) as document:
        page = document[0]
        if missing:
            content = b"BT /Nope 10 Tf 72 450 Td (Missing) Tj ET"
            _draw(document, page, "XObject", "Nothing", _form(document, b"", ""), content)
        document.save(tmp_path / "nothing.pdf")
    spans, decoded = _decoded(tmp_path / "nothing.pdf", EVIDENCE_OCR)
    with fitz.open(tmp_path / "nothing.pdf") as document:
        assert documents_module._pdf_font_span_name_counts(document[0]) == Counter({"": 1})
    assert {span[2] for line in spans for span in line} == {""}
    assert ("Missing" in _texts(spans)) is missing
    assert decoded == spans


def test_a_graphics_state_written_as_a_stream_has_its_font_entry_read(tmp_path):
    # Review round 6: /ExtGState << /GS S 0 R >>, S a stream whose dictionary holds
    # /Font [B 0 R 10], B and its descendant of /Type /Foo. MuPDF draws in B (1.26.7 and
    # 1.28.2). The walk reads a stream's dictionary for /Font entries as it reads any
    # object's, so B is counted and A is not decoded.
    fonts = {}

    def build(document, page):
        b = fonts["B"] = _type0_font(document, B_CODES, "Shared")
        (descendant,) = documents_module._pdf_object_references(
            document.xref_get_key(b, "DescendantFonts")[1]
        )
        document.xref_set_key(b, "Type", "/Foo")
        document.xref_set_key(descendant, "Type", "/Foo")
        state = document.get_new_xref()
        document.update_object(state, f"<< /Font [{b} 0 R 10] >>")
        document.update_stream(state, b"")
        content = f"q /GS gs BT 72 450 Td <{B_HEX}> Tj ET Q".encode()
        _draw(document, page, "ExtGState", "GS", state, content)

    spans, decoded, drawn, counts = _shared_rival(tmp_path, "stream.pdf", build)
    assert B_LINE in _texts(spans)  # MuPDF draws B
    assert drawn is not None and fonts["B"] in drawn and counts["Shared"] == 2
    assert decoded == spans


@pytest.mark.parametrize("inline", [False, True])
def test_an_object_that_looks_like_a_font_is_walked_through(tmp_path, inline):
    # Review round 6: the graphics state << /Subtype /Type1 /BaseFont /Other /SMask << /S
    # /Luminosity /G G 0 R >> >>, G a group whose resources hold B, which G draws. MuPDF
    # extracts B's text. The walk counts fonts only where MuPDF selects them, and follows
    # every object's references whatever the object looks like, so G is walked, B is
    # counted, and nothing is counted as "Other". (Taken for a font, the state hid G.)
    fonts = {}

    def build(document, page):
        b = fonts["B"] = _type0_font(document, B_CODES, "Shared")
        group = _form(
            document, f"BT /B1 10 Tf 72 450 Td <{B_HEX}> Tj ET".encode(), f"/Font << /B1 {b} 0 R >>"
        )
        entries = f"/Subtype /Type1 /BaseFont /Other /SMask << /S /Luminosity /G {group} 0 R >>"
        content = b"q /GS gs 0 g 50 400 300 200 re f Q"
        _graphics_state(document, page, "GS", entries, content, inline)

    spans, decoded, drawn, counts = _shared_rival(tmp_path, "masked.pdf", build)
    assert B_LINE in _texts(spans)  # MuPDF extracts the group's text
    assert drawn is not None and fonts["B"] in drawn
    assert counts["Shared"] == 2 and "Other" not in counts
    assert decoded == spans


def _annotated(
    tmp_path: Path, name: str, entries: str, acroform: str | None = None, *, form_object: bool = False
):
    """The page with A (Shared) drawing EVIDENCE and "Wendy Hill" unmapped, and one
    annotation ``<< entries >>`` ("{stored}" in them a stored appearance drawing "Stored" in
    Courier; "{Widget}", "{Link}", "{FreeText}" and "{Sig}" references to those names
    written as objects of their own; "{signature}" a signature dictionary as an object;
    "{sigfield}" and "{signedfield}" parent fields of type /Sig, without and with a
    value), with the catalog's /AcroForm ``acroform`` ("{annotation}" in it
    the annotation; "{true}" and "{false}" references to those booleans, and "{chain}" to
    a reference to true), written in the catalog or, with ``form_object``, as an object of
    its own; its spans, the decoded spans and the fonts the walk finds."""
    pdf = _form_pdf(tmp_path / "form.pdf", [*EVIDENCE, ("Wendy Hill", PUA)], name="Shared")
    with fitz.open(pdf) as document:
        page = document[0]
        font = _font_object(document, "Courier")
        stored = _form(document, b"BT /F9 12 Tf 80 310 Td (Stored) Tj ET", f"/Font << /F9 {font} 0 R >>")
        names = {"stored": f"{stored} 0 R"}
        for key, value in (
            ("Widget", "/Widget"),
            ("Link", "/Link"),
            ("FreeText", "/FreeText"),
            ("true", "true"),
            ("false", "false"),
        ):
            xref = document.get_new_xref()
            document.update_object(xref, value)
            names[key] = f"{xref} 0 R"
        chain = document.get_new_xref()
        document.update_object(chain, names["true"])
        names["chain"] = f"{chain} 0 R"
        for key, value in (
            ("Sig", "/Sig"),
            ("signature", "<< /Type /Sig /Filter /Adobe.PPKLite /ByteRange [0 0 0 0] /Contents <00> >>"),
        ):
            xref = document.get_new_xref()
            document.update_object(xref, value)
            names[key] = f"{xref} 0 R"
        for key, value in (
            ("sigfield", "<< /FT /Sig /T (s1) >>"),
            ("signedfield", "<< /FT /Sig /T (s1) /V " + names["signature"] + " >>"),
        ):
            xref = document.get_new_xref()
            document.update_object(xref, value)
            names[key] = f"{xref} 0 R"
        annotation = document.get_new_xref()
        document.update_object(
            annotation, "<< /Type /Annot /Rect [72 300 400 340] " + entries.format(**names) + " >>"
        )
        document.xref_set_key(page.xref, "Annots", f"[{annotation} 0 R]")
        if acroform is not None:
            form = acroform.format(annotation=f"{annotation} 0 R", **names)
            if form_object:
                holder = document.get_new_xref()
                document.update_object(holder, form)
                form = f"{holder} 0 R"
            document.xref_set_key(document.pdf_catalog(), "AcroForm", form)
        document.save(tmp_path / name)
    spans, decoded = _decoded(tmp_path / name, EVIDENCE_OCR)
    with fitz.open(tmp_path / name) as document:
        drawn = documents_module._pdf_drawn_font_xrefs(document[0])
    return spans, decoded, drawn


HELV = "/DA (/Helv 12 Tf 0 g)"
NEED_APPEARANCES = "<< /Fields [{annotation}] /NeedAppearances true >>"


@pytest.mark.parametrize(
    ("entries", "text"),
    [
        (f"/Subtype /FreeText /Contents (Hello) {HELV}", "Hello"),
        (f"/Subtype /FreeText /Contents (Hello) {HELV} /AP null", "Hello"),
        (f"/Subtype /FreeText /Contents (Hello) {HELV} /AP << /N << /On {{stored}} >> >>", "Hello"),
        ("/Subtype /Stamp /Name /Approved", "APPROVED"),
        ("/Subtype /Line /L [72 300 400 300] /Cap true /Contents (Hello)", "Hello"),
        (f"/Subtype /Widget /FT /Tx /T (f1) /V (Hello) {HELV}", "Hello"),
        (f"/Subtype {{FreeText}} /Contents (Hello) {HELV}", "Hello"),
    ],
    ids=[
        "FreeText",
        "FreeText-AP-null",
        "FreeText-states-without-AS",
        "Stamp",
        "Line-caption",
        "text-field",
        "FreeText-indirect-Subtype",
    ],
)
def test_an_appearance_mupdf_makes_itself_stops_decoding(tmp_path, entries, text):
    # Review round 7: MuPDF makes an appearance itself for an annotation without a stored
    # one it can use (no /AP /N stream, nor a dictionary with one under /AS), and draws its
    # text in fonts no object in the file carries (Helvetica, Times-Bold; 1.26.7 and
    # 1.28.2). One of those can share A's name, and its unmapped characters would then be
    # decoded by A's shift (the review's "000"), so the page's fonts are not known.
    spans, decoded, drawn = _annotated(tmp_path, "made.pdf", entries)
    assert any(span[0] == text and span[2] != "Shared" for line in spans for span in line)
    assert drawn is None
    assert decoded == spans


@pytest.mark.parametrize(
    "entries",
    [
        f"/Subtype /Widget /FT /Tx /T (f1) /V (Hello) {HELV} /AP << /N {{stored}} >>",
        f"/Subtype {{Widget}} /FT /Tx /T (f1) /V (Hello) {HELV} /AP << /N {{stored}} >>",
        f"/Subtype /FreeText /Contents (Hello) {HELV} /AP << /N {{stored}} >>",
    ],
    ids=["text-field", "text-field-indirect-Subtype", "FreeText"],
)
def test_a_form_that_says_to_make_appearances_anew_stops_decoding(tmp_path, entries):
    # With the form's /NeedAppearances true, PyMuPDF 1.28.2 makes a text field's appearance
    # anew though one is stored ("Hello" in Helvetica), its /Subtype written directly or as
    # an object of its own (review round 8); 1.26.7 draws the stored one. Every annotation
    # but a Link or Popup then stops decoding, a FreeText one too, though neither version
    # was seen to remake it.
    spans, decoded, drawn = _annotated(tmp_path, "remade.pdf", entries, NEED_APPEARANCES)
    assert {"Stored", "Hello"} & set(_texts(spans))
    assert drawn is None
    assert decoded == spans


@pytest.mark.parametrize(
    ("value", "form_object"),
    [("true", False), ("{true}", False), ("{chain}", False), ("true", True)],
    ids=["direct", "indirect", "chain", "AcroForm-object"],
)
def test_a_need_appearances_written_any_way_stops_decoding(tmp_path, value, form_object):
    # Review round 9: /NeedAppearances is read through an /AcroForm written as an object of
    # its own, and resolved once when indirect; anything but absent or false counts. A chain
    # of references is refused too, though MuPDF reads it as false and draws the stored
    # appearance (1.26.7 and 1.28.2): failing closed keeps the rule off MuPDF's reading.
    entries = f"/Subtype /Widget /FT /Tx /T (f1) /V (Hello) {HELV} /AP << /N {{stored}} >>"
    acroform = "<< /Fields [{annotation}] /NeedAppearances " + value + " >>"
    spans, decoded, drawn = _annotated(tmp_path, "need.pdf", entries, acroform, form_object=form_object)
    assert {"Stored", "Hello"} & set(_texts(spans))
    assert drawn is None
    assert decoded == spans


SIGNED = "/V << /Type /Sig /Filter /Adobe.PPKLite /ByteRange [0 0 0 0] /Contents <00> >>"
SIG_FORM = "<< /Fields [{annotation}] /SigFlags 1 >>"
STORED = "/AP << /N {stored} >>"


@pytest.mark.parametrize(
    ("entries", "text"),
    [
        (f"/Subtype /Widget /FT /Sig /T (s1) {STORED}", "SIGN"),
        (f"/Subtype /Widget /Parent {{sigfield}} {STORED}", "SIGN"),
        (f"/Subtype /Widget /FT /Sig /T (s1) /V null {STORED}", "SIGN"),
        (f"/Subtype /Widget /FT /Sig /T (s1) /V (x) {STORED}", "SIGN"),
        (f"/Subtype /Widget /FT /Sig /T (s1) /V << /Type /Foo >> {STORED}", "SIGN"),
        (f"/Subtype /Widget /FT {{Sig}} /T (s1) {STORED}", "Stored"),
    ],
    ids=["unsigned", "inherited-FT", "V-null", "V-string", "V-other-Type", "FT-indirect"],
)
def test_an_unsigned_signature_widget_stops_decoding(tmp_path, entries, text):
    # Review round 10: MuPDF draws an unsigned signature field's appearance itself ("SIGN"
    # in NimbusSans-Regular), whatever is stored (1.26.7 and 1.28.2), as on OH-19-0025
    # page 3. Unsigned means a field type of /Sig, inherited through /Parent, and a value,
    # inherited likewise, that is not a dictionary whose /Type is absent or /Sig. A /Sig
    # field type written as an object of its own MuPDF does not read as a signature (it
    # draws the stored appearance); it is refused anyway.
    spans, decoded, drawn = _annotated(tmp_path, "sig.pdf", entries, SIG_FORM)
    assert text in _texts(spans)
    assert drawn is None
    assert decoded == spans


@pytest.mark.parametrize(
    "entries",
    [
        f"/Subtype /Widget /FT /Sig /T (s1) {SIGNED} {STORED}",
        f"/Subtype /Widget /FT /Sig /T (s1) /V << >> {STORED}",
        f"/Subtype /Widget /FT /Sig /T (s1) /V {{signature}} {STORED}",
        f"/Subtype /Widget /Parent {{signedfield}} {STORED}",
    ],
    ids=["signed", "V-empty-dict", "V-indirect", "inherited-V"],
)
def test_a_signed_signature_widget_leaves_decoding_alone(tmp_path, entries):
    # The converse: a signed signature field, its value a dictionary written in place or as
    # an object, or inherited, is drawn from its stored appearance, and A is decoded.
    spans, decoded, drawn = _annotated(tmp_path, "signed.pdf", entries, SIG_FORM)
    assert "SIGN" not in _texts(spans) and "Stored" in _texts(spans)
    assert drawn is not None
    assert "Wendy Hill" in _texts(decoded)


@pytest.mark.parametrize(
    ("entries", "acroform"),
    [
        (f"/Subtype /FreeText /Contents (Hello) {HELV} /AP << /N {{stored}} >>", None),
        (f"/Subtype /FreeText /Contents (Hello) {HELV} /AS /On /AP << /N << /On {{stored}} >> >>", None),
        (f"/Subtype /Widget /FT /Tx /T (f1) /V (Hello) {HELV} /AP << /N {{stored}} >>", None),
        (
            f"/Subtype /Widget /FT /Tx /T (f1) /V (Hello) {HELV} /AP << /N {{stored}} >>",
            "<< /Fields [{annotation}] /NeedAppearances false >>",
        ),
        ("/Subtype /Link /Border [0 0 0] /A << /S /URI /URI (http://example.org) >>", None),
        ("/Subtype /Popup /Contents (Hello)", None),
        ("/Subtype {Link} /Border [0 0 0] /A << /S /URI /URI (http://example.org) >>", None),
        ("/Subtype /Link /Border [0 0 0] /A << /S /URI /URI (http://example.org) >>", NEED_APPEARANCES),
        (
            f"/Subtype /Widget /FT /Tx /T (f1) /V (Hello) {HELV} /AP << /N {{stored}} >>",
            "<< /Fields [{annotation}] /NeedAppearances {false} >>",
        ),
    ],
    ids=[
        "FreeText",
        "FreeText-AS",
        "text-field",
        "text-field-NeedAppearances-false",
        "Link",
        "Popup",
        "Link-indirect-Subtype",
        "Link-NeedAppearances",
        "text-field-NeedAppearances-indirect-false",
    ],
)
def test_annotations_drawn_from_stored_appearances_leave_decoding_alone(tmp_path, entries, acroform):
    # The converse: a stored appearance MuPDF uses, or a Link or Popup (its /Subtype
    # resolved when indirect, as MuPDF resolves it), which MuPDF never gives an appearance of
    # its own, leaves the fonts known and A decoded.
    spans, decoded, drawn = _annotated(tmp_path, "stored.pdf", entries, acroform)
    assert "Hello" not in _texts(spans)
    assert drawn is not None
    assert "Wendy Hill" in _texts(decoded)


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
    assert all(font == "Arial" for line in changed for _, _, font, *_ in line)
    for line, old in zip(decoded, spans, strict=True):
        if any(font == "ArialMT" for _, _, font, *_ in old):
            assert line == old
    texts = ["".join(text for text, *_ in line) for line in changed]
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
def test_every_span_with_an_unmapped_character_is_one_mupdf_marks_as_codes(path, monkeypatch):
    # A second differential test: MuPDF marks a span whose characters stand in for missing
    # Unicode with FZ_STEXT_UNICODE_IS_CID or _IS_GID (char_flags 128, 256). Every span
    # holding a character the two reads find unmapped carries one of them. The converse
    # does not hold: on WV-23-0001 page 132 nine marked spans hold characters MuPDF maps
    # ("."), so the mark alone does not say which characters to decode.
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
                unmapped = False
                for char in span["chars"]:
                    origin = (float(char["origin"][0]), float(char["origin"][1]))
                    k = seen[origin]
                    seen[origin] += 1
                    flags = found.get(origin, ())
                    unmapped |= k < len(flags) and flags[k]
                if unmapped and "char_flags" in span:
                    text = "".join(char["c"] for char in span["chars"])
                    assert int(span["char_flags"]) & (128 | 256), text


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
