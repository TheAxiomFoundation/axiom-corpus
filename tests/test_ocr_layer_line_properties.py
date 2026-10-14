"""Properties of the rules that merge a scanned page's text layer into its OCR text.

With ``ocr: true``, a page whose text layer is only an overlay is read by OCR, and the
layer's lines are merged after the OCR text in three steps.

``_without_garbled_spans(span_lines)`` turns the PDF's lines, as (text, painted, font,
mapped) spans, into (text, painted) lines. ``mapped`` is True when a span's characters come
from its font's Unicode map, False when MuPDF found no Unicode for them, None when unknown.
Its invariants, for every input:

S1. A span holding a control character other than ordinary whitespace (``_garbled``) is
    left out whole, and so is every other span on its line in the same font, except a
    mapped span when every control-character span of its font on the line is unmapped
    (False); every other span's text is in its line, in order, with one space where
    left-out spans stood between kept spans.
S2. No line it returns holds such a control character, and each has a visible character.
S3. A line is painted exactly when one of its kept spans with visible characters is.

``_with_layer_marks(lines, layer_text)`` puts back the combining marks the text output
holds and the spans lack. Its invariants, for every input:

K1. It returns the lines unchanged when they hold every mark of the text output. Otherwise
    what it returns is the lines, in order and with their paint, some replaced by a
    text-output line that is the same once marks are left out (spacing aside).
K2. What it returns holds every combining mark of the text output's lines without a
    control character, as a multiset.
K3. It returns None only when a text-output line without a control character holds a mark
    the lines lack and no line is left that it, or it without marks, could be.

``_without_failed_recognition_lines(lines, ocr_text)`` chooses the layer lines worth
merging from (text, painted) pairs. Its invariants, for every input:

R1. The result is the input's texts in order with some removed (a subsequence).
R2. A line with a control character other than ordinary whitespace (``_garbled``) is
    removed whole, painted or not, before anything splits it. Every other painted line is
    kept: typed text is never removed.
R3. Any other invisible line is removed only when it is a fragment (fewer than three
    letters and no digit, after NFKC) or the invisible layer has failed: at least five
    distinct words of three or more letters, fewer than a third of them in the OCR text
    (``_reference_failed``).
R4. More OCR text never removes a kept line.
R5. Applying it to its own result changes nothing.

``_with_unread_layer_lines(ocr_text, layer_text)`` then merges. Its invariants:

M1. Prefix: with OCR text, the result starts with it (less trailing newlines), and is the
    OCR text exactly when no line is kept.
M2. Containment: every layer line with a letter or digit and no control character is held
    by the result: its characters in order, as whole tokens, whatever the spacing next to a
    letter (quote and dash variants compare equal). No such line is lost.
M3. Nothing is appended when OCR read every line: a layer made of the OCR text's own
    tokens, regrouped into lines, respaced next to letters and trimmed of edge punctuation,
    adds nothing.
M4. The kept lines are exactly the layer lines OCR does not hold, each once, in layer
    order. None holds a control character, and each has a letter or digit.
M5. Idempotence: merging the same layer into the result again changes nothing.
M6. Without OCR text the layer comes back unchanged.
M7. More OCR text never keeps more, and a line's fate is independent of the other lines.
M8. Against the rule this replaces (PR #854: keep a line when one of its tokens with a digit
    is not among OCR's tokens): every line that rule kept is still held by the result,
    unless the first step removed it as an invisible recognition line.

Together (S1, K2, R2 and M2): the text of every painted span S1 keeps, line by line, is in
the page text wherever it has a letter or digit. "Held" is ``_reference_reads``, a brute-force definition
over every run of tokens written without the implementation's offset bookkeeping, so M2,
M4 and M8 are also differential tests; R3 is checked against ``_reference_failed``.

The page tests at the end run ``_pdf_page_text`` on the retained PDFs with Tesseract's
stored output for each page.
"""

from __future__ import annotations

import collections
import hashlib
import itertools
import json
import re
import unicodedata
from pathlib import Path

import fitz
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.documents as documents_module
from axiom_corpus.corpus.documents import (
    _pdf_layer_lines,
    _pdf_page_text,
    _same_layer_characters,
    _with_layer_marks,
    _with_unread_layer_lines,
    _without_failed_recognition_lines,
    _without_garbled_spans,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# The reference's own copies: edge punctuation (a leading currency sign or minus and a
# trailing percent sign are part of a value) and the quote and dash variants.
_LEAD = re.compile(r"^[^\w$€£%-]+")
_TRAIL = re.compile(r"[^\w%]+$")
_VARIANTS = {
    **dict.fromkeys("‘’‚‛′", "'"),
    **dict.fromkeys("“”„‟″", '"'),
    **dict.fromkeys("‐‑‒–—―−", "-"),
}


def _variant_folded(text: str) -> str:
    return "".join(_VARIANTS.get(char, char) for char in text)


def _fold(tokens: list[str]) -> str:
    """Tokens joined, with a space only where no letter is on either side of the gap."""
    out = ""
    for token in tokens:
        if out and not (out[-1].isalpha() or token[0].isalpha()):
            out += " "
        out += token
    return out


def _edges(token: str) -> tuple[int, int]:
    """How many leading and trailing punctuation characters of ``token`` may be left off."""
    lead = _LEAD.match(token)
    trail = _TRAIL.search(token)
    start = lead.end() if lead else 0
    end = trail.start() if trail else len(token)
    if start >= end:  # punctuation only: whole or not at all
        return 0, 0
    return start, len(token) - end


def _reference_reads(text: str, line: str) -> bool:
    """Brute force: some run of ``text``'s tokens is ``line``, give or take spacing next to a
    letter, quote and dash variants, and the punctuation leading the run's first token or
    trailing its last."""
    target = _fold(_variant_folded(line).split())
    tokens = _variant_folded(text).split()
    for first in range(len(tokens)):
        lead, _ = _edges(tokens[first])
        for last in range(first, len(tokens)):
            joined = _fold(tokens[first : last + 1])
            _, trail = _edges(tokens[last])
            for skipped in range(lead + 1):
                for dropped in range(trail + 1):
                    if joined[skipped : len(joined) - dropped] == target:
                        return True
            if len(joined) - lead > len(target):
                break  # every longer run is longer than the line, whatever is left off
    return False


def _is_text(line: str) -> bool:
    return any(char.isalnum() for char in line) and not any(
        unicodedata.category(char) == "Cc" for char in line
    )


def _layer_lines(layer_text: str) -> list[str]:
    """The layer's distinct lines, whitespace-normalized, in order of first appearance."""
    lines = (" ".join(raw.split()) for raw in layer_text.splitlines())
    return list(dict.fromkeys(line for line in lines if line))


def _kept(ocr_text: str, result: str) -> list[str]:
    """The lines the result appends to non-blank OCR text."""
    if result == ocr_text:
        return []
    head = ocr_text.rstrip("\n") + "\n\n"
    assert result.startswith(head)
    return result[len(head) :].split("\n")


def _rule_854_kept(ocr_text: str, layer_text: str) -> list[str]:
    """The lines PR #854's rule kept (copied from f98fa2bbd, for M8)."""
    edges = re.compile(r"^[^\w$€£%-]+|[^\w%]+$")

    def tokens(text: str) -> list[str]:
        return [token for token in (edges.sub("", raw) for raw in text.split()) if token]

    read = set(tokens(ocr_text))
    kept: list[str] = []
    for raw in layer_text.splitlines():
        line = " ".join(raw.split())
        if not line or line in kept or any(unicodedata.category(c) == "Cc" for c in line):
            continue
        values = [token for token in tokens(line) if any(c.isdigit() for c in token)]
        if any(token not in read for token in values):
            kept.append(line)
    return kept


def _words(text: str, shortest: int) -> list[str]:
    """Maximal runs of letters, case-folded, of at least ``shortest`` letters."""
    out, run = [], ""
    for char in unicodedata.normalize("NFKC", text) + " ":
        if char.isalpha():
            run += char
            continue
        if len(run) >= shortest:
            out.append(run.lower())
        run = ""
    return out


def _garbled(line: str) -> bool:
    """R2: a control character other than tab, newline, carriage return, VT or FF."""
    return any(unicodedata.category(c) == "Cc" and c not in "\t\n\r\x0b\x0c" for c in line)


def _runs(text: str) -> list[str]:
    """Maximal runs of letters (``str.isalpha``) after NFKC, not case-folded."""
    grouped = itertools.groupby(unicodedata.normalize("NFKC", text), str.isalpha)
    return ["".join(group) for alpha, group in grouped if alpha]


def _reference_failed(invisible: list[str], ocr_text: str) -> bool:
    """R3's failed layer, written out: >= 5 distinct words of 3+ letters, < 1/3 in OCR; a
    word of 6+ letters (counted before case-folding) may be found inside OCR's letters."""
    runs = [run for line in invisible if not _garbled(line) for run in _runs(line)]
    words = {run.lower() for run in runs if len(run) >= 3}
    long_words = {run.lower() for run in runs if len(run) >= 6}
    ocr_words = _words(ocr_text, 1)
    found = [w for w in words if w in ocr_words or (w in long_words and w in "".join(ocr_words))]
    return len(words) >= 5 and 3 * len(found) < len(words)


def _fragment(line: str) -> bool:
    # Letters are counted on the runs before lower-casing ("\u0130" lower-cases to two).
    letters = sum(char.isalpha() for char in unicodedata.normalize("NFKC", line))
    return letters < 3 and not any(char.isdigit() for char in unicodedata.normalize("NFKC", line))


def _spared(lines: list[tuple[str, bool]], ocr_text: str) -> list[tuple[str, bool]]:
    """R1 to R3 written out: the (text, painted) pairs the filter keeps."""
    failed = _reference_failed([text for text, painted in lines if not painted], ocr_text)
    return [
        (text, painted)
        for text, painted in lines
        if not _garbled(text) and (painted or not (failed or _fragment(text)))
    ]


# A small alphabet, so layer lines often occur in the OCR text, in part or whole: letters,
# digits, punctuation the edge rules treat differently, quote and dash variants, a
# non-ASCII letter, a soft hyphen (format character), control characters (two that Python
# splits lines at), and several kinds of whitespace.
CHARS = "abAB129.,/()$%-:'_’–é­\x01\x1e\x85 \t\n "
TEXT = st.text(alphabet=st.sampled_from(CHARS), max_size=48)
OCR = TEXT.filter(lambda text: bool(text.split()))
TOKEN = st.text(alphabet=st.sampled_from("abAB129.,/()$%-:'_’–é"), min_size=1, max_size=6)

# --------------------------------------------------------------------- recognition layers

# Words the layer and the OCR text draw from, so a layer agrees with OCR in part.
VOCABULARY = ["date", "plan", "state", "approval", "regional", "ckm", "rml", "err", "urrr", "jhofe"]
LAYER_LINE = st.one_of(
    st.lists(st.sampled_from(VOCABULARY), min_size=1, max_size=4).map(" ".join),
    st.sampled_from(
        [
            "cc:",
            "/s/",
            "L",
            "Al",
            "9",
            "4COW",
            "21 Jan",
            "··.",
            "",
            "x\x01y",
            "Ckm\x01jhofe\x01urrr",
            "date\x01plan",
            "2EQI\x1e",
            "Approval\x1cdate plan",
            "ab\x1fcd state",
            "x\x85y",
            "\ufb01x",
            "\ufb01x approval",
            "date\tplan",
            "\u0130\u0130",
            "\u0130\u0130 date",
            "plan\x1dstate",
        ]
    ),
    st.text(alphabet=st.sampled_from("abCD12 .:/"), max_size=12),
)
LAYER = st.lists(st.tuples(LAYER_LINE, st.booleans()), max_size=14)
OCR_WORDS = st.lists(st.sampled_from([*VOCABULARY, "approvaldate", "the"]), max_size=12).map(
    " ".join
)


@settings(max_examples=800, deadline=None)
@given(LAYER, OCR_WORDS)
def test_recognition_filter_keeps_typed_lines_and_drops_only_fragments_or_failed_layers(
    lines, ocr_text
):
    kept = _without_failed_recognition_lines(lines, ocr_text)

    # R1, R2, R3 at once: exactly the lines the written-out definition spares.
    assert kept == [text for text, _ in _spared(lines, ocr_text)]


@settings(max_examples=500, deadline=None)
@given(LAYER, OCR_WORDS, OCR_WORDS)
def test_more_ocr_text_never_removes_a_recognition_line(lines, ocr_text, more_ocr):
    kept = _without_failed_recognition_lines(lines, ocr_text)
    with_more = _without_failed_recognition_lines(lines, ocr_text + "\n" + more_ocr)

    # R4: with_more keeps every line kept keeps (as a multiset, in order).
    remaining = iter(with_more)
    assert all(any(line == other for other in remaining) for line in kept)


@settings(max_examples=500, deadline=None)
@given(LAYER, OCR_WORDS)
def test_recognition_filter_is_idempotent(lines, ocr_text):
    kept_pairs = _spared(lines, ocr_text)

    # R5: the lines it keeps, with their paint, pass through unchanged.
    assert _without_failed_recognition_lines(kept_pairs, ocr_text) == [
        text for text, _ in kept_pairs
    ]


@settings(max_examples=500, deadline=None)
@given(LAYER, OCR_WORDS)
def test_every_painted_layer_line_is_in_the_page_text(lines, ocr_text):
    layer = "\n".join(_without_failed_recognition_lines(lines, ocr_text))
    result = _with_unread_layer_lines(ocr_text, layer)

    for text, painted in lines:
        if painted and not _garbled(text):
            for part in text.splitlines():
                line = " ".join(part.split())
                if _is_text(line):
                    assert _reference_reads(result, line), line


SPAN = st.tuples(
    st.one_of(
        st.sampled_from(
            [
                "November 19, 2014",
                "2EQI\x1e",
                "\x01\x02",
                "ab\x1fcd",
                "Date",
                " ",
                "",
                "x\x85y",
                "\x1cA",
                "B\x1d",
                "\u0130\u0130 x",
            ]
        ),
        st.text(alphabet=st.sampled_from("abC12 .:\x01\x1c\x1d\x1e\t\u0130"), max_size=8),
    ),
    st.booleans(),
    st.sampled_from(["F1", "F2", "F3"]),
    st.sampled_from([True, False, None]),
)
SPAN_LINES = st.lists(st.lists(SPAN, max_size=5), max_size=6)


def _left_out(spans: list[tuple[str, bool, str, bool | None]]) -> list[bool]:
    """S1 written out: which spans of a line are left out."""
    garbled_fonts = {font for text, _, font, _ in spans if _garbled(text)}
    unmapped_fonts = {
        font
        for font in garbled_fonts
        if all(m is False for text, _, f, m in spans if f == font and _garbled(text))
    }
    return [
        _garbled(text)
        or (font in garbled_fonts and not (font in unmapped_fonts and mapped is True))
        for text, _, font, mapped in spans
    ]


def _kept_line(spans: list[tuple[str, bool, str, bool | None]]) -> tuple[str, bool]:
    """S1 written another way: a NUL (never kept: it is a control character) marks each
    left-out span; the line is the non-empty pieces between marks, joined by spaces, and
    painted when a kept span with visible characters is."""
    out = _left_out(spans)
    marked = "".join("\0" if gone else span[0] for span, gone in zip(spans, out, strict=True))
    text = " ".join(piece for piece in marked.split("\0") if piece)
    painted = any(
        span_painted and span.strip()
        for (span, span_painted, _, _), gone in zip(spans, out, strict=True)
        if not gone
    )
    return text, painted


@settings(max_examples=800, deadline=None)
@given(SPAN_LINES)
def test_garbled_spans_are_left_out_and_clean_spans_kept(span_lines):
    lines = _without_garbled_spans(span_lines)

    expected = []
    for spans in span_lines:
        text, painted = _kept_line(spans)
        if text.strip():
            expected.append((text, painted))
    # S1, S2, S3 at once, against this written-out version.
    assert lines == expected
    assert not any(_garbled(text) for text, _ in lines)


def test_same_layer_characters_cases():
    # The spans must hold the text output's characters; whitespace, control characters
    # (the sorted text output drops a garbled font's U+0001 "spaces") and combining marks
    # (PyMuPDF 1.28 prints Khmer marks on WV-23-0001 that its spans lack; _with_layer_marks
    # puts them back) aside.
    assert _same_layer_characters(
        [[("Ckm", True, "F", True), (" rML", False, "F", None)]], "Ckm\n rML\n"
    )
    assert _same_layer_characters([[("2EQI\x01", True, "F", False)]], "2EQI\n")
    assert _same_layer_characters([[("i:o..", True, "F", True)]], "i:o..\u17b7\n")
    assert not _same_layer_characters([[("Ckm", True, "F", True)]], "Ckm rML\n")
    assert not _same_layer_characters([[("Ckm", True, "F", True)]], "Ckn\n")


MARKS = "\u0301\u17b7"
MARK_LINE = st.text(alphabet=st.sampled_from("ab1 " + MARKS + "\x01"), max_size=6)


def _marks(text: str) -> list[str]:
    return sorted(char for char in text if unicodedata.category(char) == "Mn")


def _bare(text: str) -> str:
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").split())


@settings(max_examples=800, deadline=None)
@given(
    st.lists(st.tuples(MARK_LINE, st.booleans(), st.booleans(), st.booleans()), max_size=6),
    st.lists(st.tuples(MARK_LINE, st.booleans()), max_size=2),
)
def test_combining_marks_the_spans_lack_are_put_back(rows, extra):
    # The text output's lines; the kept lines are some of them, each with or without its
    # marks, plus lines the text output does not have.
    layer_text = "\n".join(text for text, _, _, _ in rows)
    lines = [
        (" ".join(text.split()) if keep_marks else _bare(text), painted)
        for text, keep, keep_marks, painted in rows
        if keep and not _garbled(text)
    ] + [(" ".join(text.split()), painted) for text, painted in extra if not _garbled(text)]
    result = _with_layer_marks(lines, layer_text)

    clean = [text for text in layer_text.split("\n") if not _garbled(text)]
    span_marks = collections.Counter(c for text, _ in lines for c in _marks(text))
    missing = collections.Counter(_marks(layer_text)) - span_marks
    if not missing:
        # K1: nothing missing, nothing changed.
        assert result == lines
        return
    if result is None:
        # K3: some clean line holding a missing mark has no line left to be.
        assert any(any(c in missing for c in text) for text in clean)
        return
    # K1: same length, order and paint; each line itself or the same without marks.
    assert len(result) == len(lines)
    for (new, new_painted), (old, old_painted) in zip(result, lines, strict=True):
        assert new_painted == old_painted
        assert new == old or (_bare(new) == " ".join(old.split()) and _marks(new))
    # K2: every mark of the clean text-output lines is in the result.
    assert not collections.Counter(c for text in clean for c in _marks(text)) - (
        collections.Counter(c for text, _ in result for c in _marks(text))
    )


def test_combining_mark_cases():
    # Review r5: the spans of "Jose\u0301" lack its accent; it is put back on the line.
    assert _with_layer_marks([("Jose", True)], "Jose\u0301\n") == [("Jose\u0301", True)]
    # A garbled line's marks are not needed.
    assert _with_layer_marks([("x", True)], "x\n\x01y\u17b7\n") == [("x", True)]
    # Two lines, each with its accent: each takes a line of its own.
    assert _with_layer_marks([("a", True), ("a", False)], "a\u0301\na\u0301") == [
        ("a\u0301", True),
        ("a\u0301", False),
    ]
    # A line already holding its mark is left as it is.
    assert _with_layer_marks([("a\u0301", True), ("b", True)], "a\u0301\nb\u0301") == [
        ("a\u0301", True),
        ("b\u0301", True),
    ]
    # A mark with no line to go on: None (the page then uses the text output's lines).
    assert _with_layer_marks([("x", True)], "Jose\u0301\n") is None


def test_garbled_span_cases():
    # Review r2's line: a garbled span beside a date typed in another font leaves the
    # date, painted.
    assert _without_garbled_spans(
        [[("2EQI\x1e", False, "Shifted", None), ("November 19, 2014", True, "Courier", True)]]
    ) == [("November 19, 2014", True)]
    # CA-25-0037: a garbled font's other spans on the line are its codes too, garbage
    # without a control character ("5678"); they go with it.
    shards = [("\x05\x1c", False, "T23", None), ("5678", False, "T23", None)]
    assert _without_garbled_spans([shards]) == []
    # A space keeps the spans around a left-out span apart; a line of garbage goes.
    assert _without_garbled_spans(
        [[("Date", True, "A", True), ("\x01\x02", True, "B", False), ("Approved", True, "A", True)]]
    ) == [("Date Approved", True)]
    assert _without_garbled_spans([[("\x01x", True, "B", False)], [(" ", True, "A", True)]]) == []
    # An empty kept span between left-out spans adds no space.
    empty = [
        ("a", True, "A", True),
        ("\x01", True, "B", False),
        ("", True, "A", True),
        ("\x01", True, "B", False),
    ]
    assert _without_garbled_spans([empty]) == [("a", True)]
    # Review r5: a span the font's own Unicode map gives (mapped) stays beside the font's
    # unmapped codes, which are the garbage (NV-20-0002 page 3's "3" in "March 13, 2020").
    date = "Date: 2020.04.06 17:04:09 -04'00'"
    assert _without_garbled_spans(
        [[("\x19", True, "ArialMT", False), (date, True, "ArialMT", True)]]
    ) == [(date, True)]
    # It goes when the provenance is unknown, or the font's map itself gave the control
    # character (the map is wrong, so its other characters can't be trusted).
    for garbled, clean in ((None, True), (True, True), (False, None), (False, False)):
        spans = [("\x19", True, "ArialMT", garbled), (date, True, "ArialMT", clean)]
        assert _without_garbled_spans([spans]) == []
    # Every control-character span of the font must be unmapped.
    spans = [
        ("\x19", True, "ArialMT", False),
        (date, True, "ArialMT", True),
        ("\x01", True, "ArialMT", None),
    ]
    assert _without_garbled_spans([spans]) == []
    # Paint comes from the spans kept.
    assert _without_garbled_spans([[("\x01x", True, "B", False), ("Ckm", False, "A", None)]]) == [
        ("Ckm", False)
    ]


def test_recognition_filter_cases():
    agree = "Approval date of the state plan regional"
    # Painted lines are never removed, fragments or not.
    assert _without_failed_recognition_lines([("cc:", True), ("L", True)], agree) == ["cc:", "L"]
    # Invisible fragments are removed; a digit is never a fragment.
    assert _without_failed_recognition_lines(
        [("cc:", False), ("9", False), ("Al", False), ("Ckm", False)], agree
    ) == ["9", "Ckm"]
    # Five words, none in the OCR text: a failed layer, removed whole.
    failed = [("Ckm rML err", False), ("urrr jhofe", False), ("21 Jan", False)]
    assert _without_failed_recognition_lines(failed, agree) == []
    # Four words are too few to judge.
    assert _without_failed_recognition_lines([("Ckm rML err urrr", False)], agree) == [
        "Ckm rML err urrr"
    ]
    # Two of five words found is not fewer than a third: kept.
    mixed = [("approval date", False), ("Ckm rML err", False)]
    assert _without_failed_recognition_lines(mixed, agree) == ["approval date", "Ckm rML err"]
    # One of five is: removed.
    assert _without_failed_recognition_lines([("approval Ckm rML err urrr", False)], agree) == []
    # A line with a control character (a garbled font) is dropped whole, painted or not,
    # and its words do not count toward judging the layer.
    garbled = [("Ckm\x01rML\x01err\x01urrr\x01jhofe", False), ("approval date", False)]
    assert _without_failed_recognition_lines(garbled, agree) == ["approval date"]
    # Python splits lines at U+001E, so the line is judged whole: a shift-28 font's "Name:"
    # is "2EQI\x1e", and must not reach the merge as "2EQI".
    assert _without_failed_recognition_lines([("2EQI\x1e", True), ("ab\x1fcd", True)], agree) == []
    assert _without_failed_recognition_lines([("date\tplan", True)], agree) == ["date\tplan"]
    # Letters are counted after NFKC, as words are: "\ufb01x" is "fix", not a fragment, and
    # dropping fragments never changes the words the layer is judged by.
    assert _without_failed_recognition_lines([("\ufb01x", False)], agree) == ["\ufb01x"]
    pages = [("\ufb01x", False)] + [
        (word, False) for word in ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf")
    ]
    once = _without_failed_recognition_lines(pages, "fix alpha bravo")
    again = _without_failed_recognition_lines([(text, False) for text in once], "fix alpha bravo")
    assert once == again == [text for text, _ in pages]
    # Review r2: lower-casing "\u0130" gives two characters, so lengths are counted first:
    # "\u0130\u0130" is a two-letter fragment and no word, on both passes.
    dotted = [("\u0130\u0130", False)] + pages[1:]
    once = _without_failed_recognition_lines(dotted, "\u0130\u0130 alpha bravo")
    again = _without_failed_recognition_lines(
        [(text, False) for text in once], "\u0130\u0130 alpha bravo"
    )
    assert once == again
    # Review r5: "\u0130\u0130\u0130" has three letters (six code points lower-cased), so
    # it is not long enough to be found inside OCR's letters run together: one of five
    # words is found, and the layer fails.
    dotted = [("\u0130\u0130\u0130 alpha bravo charlie delta", False)]
    assert _without_failed_recognition_lines(dotted, "x\u0130\u0130\u0130x alpha") == []
    # Run-together words of six or more letters are found in OCR's letters run together.
    run_together = [("ApprovalDate StatePlan Regional ckm", False), ("21", False)]
    assert _without_failed_recognition_lines(run_together, agree) == [
        "ApprovalDate StatePlan Regional ckm",
        "21",
    ]


# ------------------------------------------------------------------------ the merge itself


@settings(max_examples=600, deadline=None)
@given(OCR, TEXT)
def test_result_is_the_ocr_text_plus_exactly_the_unread_layer_lines(ocr_text, layer_text):
    result = _with_unread_layer_lines(ocr_text, layer_text)

    expected = [
        line
        for line in _layer_lines(layer_text)
        if _is_text(line) and not _reference_reads(ocr_text, line)
    ]
    # M1 and M4 (and the fast search against the brute-force reference).
    assert result.startswith(ocr_text.rstrip("\n"))
    assert _kept(ocr_text, result) == expected
    if not expected:
        assert result == ocr_text


@st.composite
def _ocr_and_lines_cut_from_it(draw):
    """OCR tokens, and lines cut out of them: runs of tokens with any gap closed or opened
    and any few characters trimmed from either end, so most lines sit on the boundary
    between read and unread (inside a number, inside a token's punctuation, across a
    digit-to-digit gap)."""
    tokens = draw(st.lists(TOKEN, min_size=1, max_size=10))
    gaps = draw(st.lists(st.sampled_from([" ", "\n"]), min_size=len(tokens), max_size=len(tokens)))
    ocr_text = "".join(token + gap for token, gap in zip(tokens, gaps, strict=True))
    lines = []
    for _ in range(draw(st.integers(1, 5))):
        first = draw(st.integers(0, len(tokens) - 1))
        last = draw(st.integers(first, min(len(tokens) - 1, first + 3)))
        text = tokens[first]
        for token in tokens[first + 1 : last + 1]:
            text += draw(st.sampled_from(["", " "])) + token
        start = draw(st.integers(0, min(3, len(text) - 1)))
        end = draw(st.integers(0, min(3, len(text) - 1 - start)))
        text = text[start : len(text) - end]
        if draw(st.booleans()):
            at = draw(st.integers(0, len(text)))
            text = text[:at] + " " + text[at:]
        if draw(st.booleans()):
            text = text.translate(str.maketrans("'-’–", "’–'-"))
        lines.append(text)
    return ocr_text, lines


@settings(max_examples=1500, deadline=None)
@given(_ocr_and_lines_cut_from_it())
def test_lines_cut_from_the_ocr_text_are_read_exactly_when_the_reference_says(case):
    ocr_text, lines = case
    layer_text = "\n".join(lines)

    expected = [
        line
        for line in _layer_lines(layer_text)
        if _is_text(line) and not _reference_reads(ocr_text, line)
    ]
    assert _kept(ocr_text, _with_unread_layer_lines(ocr_text, layer_text)) == expected


@settings(max_examples=600, deadline=None)
@given(TEXT, TEXT)
def test_every_layer_line_of_text_is_held_by_the_result(ocr_text, layer_text):
    result = _with_unread_layer_lines(ocr_text, layer_text)

    # M2.
    for line in _layer_lines(layer_text):
        if _is_text(line):
            assert _reference_reads(result, line), line


@st.composite
def _ocr_and_a_layer_it_read(draw):
    """OCR tokens, and a layer of runs of those tokens with harmless differences."""
    tokens = draw(st.lists(TOKEN, min_size=1, max_size=12))
    separators = draw(
        st.lists(
            st.sampled_from([" ", "\n", "\n\n", "  "]), min_size=len(tokens), max_size=len(tokens)
        )
    )
    ocr_text = "".join(token + gap for token, gap in zip(tokens, separators, strict=True))
    lines = []
    for _ in range(draw(st.integers(0, 6))):
        first = draw(st.integers(0, len(tokens) - 1))
        last = draw(st.integers(first, len(tokens) - 1))
        run = tokens[first : last + 1]
        # Trim part of the punctuation leading the run and trailing it (judged after the
        # variant fold, which is one character for one: "\u20132" is the value "-2").
        lead, _ = _edges(_variant_folded(run[0]))
        _, trail = _edges(_variant_folded(run[-1]))
        skipped = draw(st.integers(0, lead))
        dropped = draw(st.integers(0, trail))
        if len(run) == 1:
            run = [run[0][skipped : len(run[0]) - dropped]]
        else:
            run = [run[0][skipped:], *run[1:-1], run[-1][: len(run[-1]) - dropped]]
        # Respace: close or open a gap wherever a letter is on either side of it.
        line = ""
        for token in run:
            for char in token:
                gap = bool(line) and not line[-1].isspace()
                if gap and (line[-1].isalpha() or char.isalpha()) and draw(st.booleans()):
                    line += " "
                line += char
            if not (line[-1].isalpha() and draw(st.booleans())):
                line += " "
        # Swap quote and dash variants.
        if draw(st.booleans()):
            line = line.translate(str.maketrans("'-’–", "’–'-"))
        lines.append(line)
    return ocr_text, tokens, lines


@settings(max_examples=600, deadline=None)
@given(_ocr_and_a_layer_it_read())
def test_nothing_is_appended_when_ocr_read_every_line(case):
    ocr_text, tokens, lines = case

    # M3: runs of the OCR text's tokens, respaced only next to letters, trimmed only of
    # edge punctuation and with quote and dash variants swapped, in any order and repeated.
    assert _with_unread_layer_lines(ocr_text, "\n".join(lines)) == ocr_text
    # The OCR text's own lines and tokens are always read.
    assert _with_unread_layer_lines(ocr_text, ocr_text) == ocr_text
    assert _with_unread_layer_lines(ocr_text, "\n".join(tokens)) == ocr_text


@settings(max_examples=400, deadline=None)
@given(TEXT, TEXT)
def test_merging_the_same_layer_twice_changes_nothing(ocr_text, layer_text):
    once = _with_unread_layer_lines(ocr_text, layer_text)

    # M5.
    assert _with_unread_layer_lines(once, layer_text) == once


@given(st.text(alphabet=st.sampled_from(" \t\n ​"), max_size=6), TEXT)
def test_without_ocr_text_the_layer_is_returned_unchanged(blank, layer_text):
    # M6.
    assert _with_unread_layer_lines(blank, layer_text) == layer_text


@settings(max_examples=400, deadline=None)
@given(OCR, TEXT, TEXT, TEXT)
def test_more_ocr_text_or_more_layer_lines_never_unkeep_a_line(
    ocr_text, more_ocr, layer_text, more_layer
):
    kept = _kept(ocr_text, _with_unread_layer_lines(ocr_text, layer_text))

    # M7.
    longer_ocr = ocr_text + "\n" + more_ocr
    with_more_ocr = _kept(longer_ocr, _with_unread_layer_lines(longer_ocr, layer_text))
    assert set(with_more_ocr) <= set(kept)

    longer_layer = layer_text + "\n" + more_layer
    with_more_layer = _kept(ocr_text, _with_unread_layer_lines(ocr_text, longer_layer))
    assert [line for line in with_more_layer if line in kept] == kept


@settings(max_examples=600, deadline=None)
@given(OCR, TEXT)
def test_every_line_the_replaced_rule_kept_is_still_held(ocr_text, layer_text):
    result = _with_unread_layer_lines(ocr_text, layer_text)

    # M8 (the merge alone; the recognition filter is the only other step).
    for line in _rule_854_kept(ocr_text, layer_text):
        assert _reference_reads(result, line), line


@given(st.text(alphabet=st.sampled_from("0123456789"), min_size=1, max_size=4), OCR)
def test_a_number_is_read_only_as_a_whole_token(number, ocr_text):
    # Digits are never matched inside a longer number, nor glued from two tokens.
    read = _with_unread_layer_lines(ocr_text, number) == ocr_text

    cores = {token[_edges(token)[0] : len(token) - _edges(token)[1]] for token in ocr_text.split()}
    assert read == (number in cores or _reference_reads(ocr_text, number))
    if not any(number in token for token in ocr_text.split()):
        assert not read


def test_reference_reads_cases():
    # The brute-force definition itself, on the cases the rule's comments name.
    assert _reference_reads("Amount: ($1,234,567).", "$1,234,567")
    assert _reference_reads("(Check One):", "CheckOne)")
    assert _reference_reads("Page 12 of 36", "Page12of36")
    assert _reference_reads("Effective Date: 1/1/2020", "EffectiveDate: 1/1/2020")
    assert _reference_reads("Children’s Health", "Children's Health")
    assert not _reference_reads("Total 2024", "24")
    assert not _reference_reads("1\n2\n3", "12")
    assert not _reference_reads("Date: 11/21/2013", "Date: 11/ 21/ 2013")
    assert not _reference_reads("2024. 5 items", ".5")
    assert not _reference_reads("-5 $5 5%", "5")
    assert not _reference_reads("March 19, 2014", "November 19, 2014")


# --------------------------------------------------------------------------- real pages

FIXTURE = json.loads(
    (
        Path(__file__).parent / "fixtures" / "ocr_overlay" / "cms_state_plan_layer_pages.json"
    ).read_text(encoding="utf-8")
)
PAGES = FIXTURE["pages"]
SPA = "{state}/policy/cms/medicaid-state-plan/spa/{rest}"


def _spans(page: dict) -> list[list[tuple[str, bool, str, bool | None]]]:
    return [[(t, p, f, m) for t, p, f, m in spans] for spans in page["layer_spans"]]


def _layer_pairs(span_lines: list, layer_text: str) -> list[tuple[str, bool]]:
    """The (text, painted) lines ``_pdf_page_text`` filters: the spans' lines with their
    marks put back, or the text output's lines when that can't be done."""
    lines = _with_layer_marks(_without_garbled_spans(span_lines), layer_text)
    return lines if lines is not None else [(line, True) for line in layer_text.split("\n")]


def _merged(page: dict) -> str:
    lines = _layer_pairs(_spans(page), page["layer_text"])
    layer = "\n".join(_without_failed_recognition_lines(lines, page["ocr_text"]))
    return _with_unread_layer_lines(page["ocr_text"], layer)


def _per_character(span_lines: list[list[tuple[str, bool, str, bool | None]]]) -> list[list[tuple]]:
    """Each line as its characters with their span's paint, font and provenance."""
    return [[(c, p, f, m) for t, p, f, m in spans for c in t] for spans in span_lines]


def _clean_painted_text(span_lines: list[list[tuple[str, bool, str, bool | None]]]) -> list[str]:
    """The painted lines S1 keeps (``_kept_line``), each newline-separated part that has
    text, whitespace-normalized."""
    out = []
    for spans in span_lines:
        text, painted = _kept_line(spans)
        if painted:
            for part in text.splitlines():
                line = " ".join(part.split())
                if _is_text(line):
                    out.append(line)
    return out


def _held_lines(span_lines: list, layer_text: str) -> list[str]:
    """The layer lines the page text must hold: S1's painted lines, or, when the spans'
    lines can't take the text output's marks and the text output's lines are used, those
    lines that have text."""
    if _with_layer_marks(_without_garbled_spans(span_lines), layer_text) is not None:
        return _clean_painted_text(span_lines)
    lines = (" ".join(line.split()) for line in layer_text.split("\n"))
    return [line for line in lines if _is_text(line)]


# The fixture was made with PyMuPDF 1.26.7, the lock. PyMuPDF 1.28 lays out WV-23-0001
# page 132's text output differently, and its spans lack the Khmer marks its text output
# prints there (what _with_layer_marks handles), so that page matches the fixture only
# under 1.26.7.
_FIXTURE_PYMUPDF = tuple(fitz.pymupdf_version_tuple[:3]) == (1, 26, 7)
_LAYOUT_DIFFERS_BY_VERSION = {
    SPA.format(state="us-wv", rest="wv-23-0001/approval-document/page-132")
}


def _page(state: str, rest: str) -> tuple[str, str, list[str]]:
    page = PAGES[SPA.format(state=state, rest=rest)]
    return page["ocr_text"], page["layer_text"], _kept(page["ocr_text"], _merged(page))


@pytest.mark.parametrize("path", sorted(PAGES))
def test_real_pages_through_the_extractor(path, monkeypatch):
    # The retained PDF page, read by _pdf_page_text with Tesseract's stored output: the
    # layer and its paint come from the PDF itself.
    page = PAGES[path]
    content = (REPO_ROOT / page["pdf"]).read_bytes()
    assert hashlib.sha256(content).hexdigest() == page["pdf_sha256"]
    monkeypatch.setattr(
        documents_module, "_ocr_pdf_page_text", lambda _page, *, extraction: page["ocr_text"]
    )
    with fitz.open(stream=content, filetype="pdf") as document:
        pdf_page = document[page["page"] - 1]
        layer_text = pdf_page.get_text("text", flags=fitz.TEXTFLAGS_TEXT)
        span_lines = _pdf_layer_lines(pdf_page, extraction={})
        result = _pdf_page_text(pdf_page, extraction={"ocr": True})

    assert _same_layer_characters(span_lines, layer_text)
    for line in _held_lines(span_lines, layer_text):
        assert _reference_reads(result, line), line
    assert result.startswith(page["ocr_text"].rstrip("\n"))
    if path in _LAYOUT_DIFFERS_BY_VERSION and not _FIXTURE_PYMUPDF:
        return
    assert layer_text == page["layer_text"]
    # Character by character (PyMuPDF versions split a line into spans differently: 1.28
    # makes the spaces of MT-13-0048-MM page 19 spans of their own).
    assert _per_character(span_lines) == _per_character(_spans(page))
    # Differential: the dict lines, joined, are the text output.
    joined = "\n".join("".join(span[0] for span in spans) for spans in span_lines)
    assert joined.splitlines() == layer_text.splitlines()
    assert result == _merged(page)


@pytest.mark.parametrize("path", sorted(PAGES))
@pytest.mark.parametrize(
    "extraction",
    [
        {"sort_text": True},
        {"ignore_actual_text": True},
        {"sort_text": True, "ignore_actual_text": True},
    ],
)
def test_page_text_under_every_text_option(path, extraction, monkeypatch):
    # sort_text rebuilds the text output's lines from words by position, but the spans hold
    # the same characters, so the spans' paint and garbling are used under every option.
    page = PAGES[path]
    monkeypatch.setattr(
        documents_module, "_ocr_pdf_page_text", lambda _page, *, extraction: page["ocr_text"]
    )
    with fitz.open(REPO_ROOT / page["pdf"]) as document:
        pdf_page = document[page["page"] - 1]
        flags = documents_module._pdf_text_flags(extraction, default=fitz.TEXTFLAGS_TEXT)
        text = pdf_page.get_text("text", sort=bool(extraction.get("sort_text")), flags=flags)
        needs_ocr = documents_module._pdf_page_needs_ocr(pdf_page, text)
        span_lines = _pdf_layer_lines(pdf_page, extraction=extraction)
        result = _pdf_page_text(pdf_page, extraction={"ocr": True, **extraction})

    assert _same_layer_characters(span_lines, text)
    if not needs_ocr:
        # Sorting can rebuild a garbled font's codes into 30 or more words (AL-20-0004
        # page 4), and a page with that many is read from its layer, not by OCR.
        assert result == text
        return
    lines = _layer_pairs(span_lines, text)
    layer = "\n".join(_without_failed_recognition_lines(lines, page["ocr_text"]))
    assert result == _with_unread_layer_lines(page["ocr_text"], layer)
    for line in _held_lines(span_lines, text):
        assert _reference_reads(result, line), line


def _invisible_noise_pdf() -> bytes:
    # A failed recognition layer (five words, none in the OCR text) on a scanned page.
    document = fitz.open()
    pdf_page = document.new_page(width=612, height=792)
    pixmap = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, 1275, 1650), False)
    pixmap.clear_with(200)
    pdf_page.insert_image(pdf_page.rect, stream=pixmap.tobytes("png"), keep_proportion=False)
    pdf_page.insert_text((72, 72), "Ckm rML err", fontsize=11, render_mode=3)
    pdf_page.insert_text((144, 90), "urrr jhofe", fontsize=11, render_mode=3)
    pdf_page.insert_text((72, 120), "January 1, 2018", fontsize=11)
    return document.tobytes()


@pytest.mark.parametrize("extraction", [{}, {"sort_text": True}])
def test_a_failed_layer_is_dropped_under_sort_text_too(extraction, monkeypatch):
    # Sorting indents the text output's lines; the filter still sees the spans' paint.
    ocr = "Applicant Household Size\n"
    monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", lambda _page, *, extraction: ocr)
    with fitz.open("pdf", _invisible_noise_pdf()) as document:
        result = _pdf_page_text(document[0], extraction={"ocr": True, **extraction})

    assert result == "Applicant Household Size\n\nJanuary 1, 2018"


def test_without_the_text_outputs_characters_the_text_lines_are_used(monkeypatch):
    # If the spans ever lack characters the text output has, the text output's lines are
    # used, all counted as painted, so no typed text can go missing.
    ocr = "Applicant Household Size\n"
    monkeypatch.setattr(documents_module, "_ocr_pdf_page_text", lambda _page, *, extraction: ocr)
    monkeypatch.setattr(
        documents_module,
        "_pdf_layer_lines",
        lambda _page, *, extraction: [[("Ckm", False, "F", None)]],
    )
    with fitz.open("pdf", _invisible_noise_pdf()) as document:
        result = _pdf_page_text(document[0], extraction={"ocr": True})

    assert result == ("Applicant Household Size\n\nCkm rML err\nurrr jhofe\nJanuary 1, 2018")


def test_a_garbled_span_drops_only_itself_on_a_real_page():
    # AL-20-0004 page 4: a shifted font's span ")OH[LELOLWLHV\x1e\x03DPRQJ\x03RWKHU" splits
    # at U+001E into a clean-looking ")OH[LELOLWLHV"; judged as a span it is left out whole.
    # The digital signature's clean spans stay. "1(:" ("NEW" shifted) has no control
    # character and is painted, so it is kept: painted text is never judged by its letters.
    page = PAGES[SPA.format(state="us-al", rest="al-20-0004/approval-document/page-4")]
    spans = [text for line in _spans(page) for text, _, _, _ in line]
    _, _, kept = _page("us-al", "al-20-0004/approval-document/page-4")

    assert any("\x1e" in text and ")OH[LELOLWLHV" in text for text in spans)
    assert ")OH[LELOLWLHV" not in kept
    assert not any(_garbled(line) for line in kept)
    assert "1(:" in kept
    assert "Digitally signed by Anne M. Costello -S" in _merged(page)


def test_a_mapped_span_in_a_garbled_font_is_kept():
    # Review r5, NV-20-0002 page 3: "March 13, 2020" is set in a MinionPro subset. MuPDF
    # finds no Unicode for most of its codes and gives their CIDs, flagged: ".BSDI\x01\x12"
    # and "\r\x01\x13\x11\x13\x11" are "March 1" and ", 2020" 31 codes down. The "3" has
    # one. It is typed text and is kept; the unmapped codes are not.
    page = PAGES[SPA.format(state="us-nv", rest="nv-20-0002/approval-document/page-3")]
    assert [(text, mapped) for text, _, _, mapped in _spans(page)[0]] == [
        (".BSDI\x01\x12", False),
        ("3", True),
        ("\r\x01\x13\x11\x13\x11", False),
    ]
    _, _, kept = _page("us-nv", "nv-20-0002/approval-document/page-3")

    assert "3" in kept
    assert not any(_garbled(line) for line in kept)


def test_combining_marks_on_a_real_page_are_kept(monkeypatch):
    # Review r5, WV-23-0001 page 132 (a visible OCR layer over a screenshot): PyMuPDF 1.28
    # prints Khmer combining marks in the text output that its spans lack; 1.26 has them in
    # both. Either way every mark of a text-output line with a letter or digit and no
    # control character is in the page text (a line with neither, "\u17b8-", is never
    # appended).
    page = PAGES[SPA.format(state="us-wv", rest="wv-23-0001/approval-document/page-132")]
    monkeypatch.setattr(
        documents_module, "_ocr_pdf_page_text", lambda _page, *, extraction: page["ocr_text"]
    )
    with fitz.open(REPO_ROOT / page["pdf"]) as document:
        pdf_page = document[page["page"] - 1]
        text = pdf_page.get_text("text", flags=fitz.TEXTFLAGS_TEXT)
        result = _pdf_page_text(pdf_page, extraction={"ocr": True})

    marks = collections.Counter(
        c for line in text.split("\n") if _is_text(line) for c in _marks(line)
    )
    assert sum(marks.values()) >= 4
    assert not marks - collections.Counter(_marks(result))


def test_a_typed_date_is_kept_when_its_day_and_year_occur_elsewhere():
    # CMS-179, HI-14-005: OCR read "March 19, 2014" (date received) and nothing of the
    # regional-office box, so "19" and "2014" were on the page and the old rule dropped the
    # typed DATE APPROVED.
    ocr_text, _, kept = _page("us-hi", "hi-14-005/approval-document/page-3")

    assert "March 19, 2014" in ocr_text and "November 19, 2014" not in ocr_text
    assert kept == [
        "XXXXXXXX",
        "XXXXXXXXXXXXXXXX",
        "Box 7: Pen and Ink Changes per",
        "RAI response 9/10/14 (cb)",
        "/s/",
        "November 19, 2014",
        "Hye Sun Lee",
        "Acting Associate Regional Administrator",
    ]


def test_a_typed_word_ocr_misread_is_restored():
    # NH-18-0001: OCR read the typed "April 30, 2018" as "531 30, 2018" and "January" as
    # "january"; the lines it read exactly are not repeated.
    ocr_text, _, kept = _page("us-nh", "nh-18-0001/approval-document/page-3")

    assert "18. DATE APPROVED: 531 30, 2018" in ocr_text
    assert kept == ["April 30, 2018", "January 1, 2018"]


@pytest.mark.parametrize(
    ("state", "rest", "typed"),
    [
        ("us-ne", "ne-12-07/form-cms-179/page-1", ["James G. Scott", "Associate Regional Administrator", "/s/"]),
        ("us-in", "in-12-014/form-cms-179/page-1", ["Verlon Johnson", "Associate Regional Administrator"]),
        ("us-in", "in-15-008/approval-document/page-3", ["/s/", "Ruth A. Hughes", "Associate Regional Administrator"]),
        ("us-mn", "mn-18-0002/approval-document/page-3", ["Ruth A. Hughes", "Associate Regional Administrator"]),
        ("us-ny", "ny-17-0014/approval-document/page-3", ["MICHAEL MELENDEZ", "ASSOCIATE REGIONAL ADMINISTRATOR"]),
        ("us-ny", "ny-17-0069/approval-document/page-3", ["NOVEMBER 21, 2019", "ACTING DEPUTY DIRECTOR"]),
        ("us-ny", "ny-19-0046/approval-document/page-3", ["ACTING DEPUTY DIRECTOR"]),
        ("us-oh", "oh-13-014/approval-document/page-3", [".s.", "Alan Freund", "Acting Associate Regional Administrator"]),
        ("us-oh", "oh-15-001/approval-document/page-3", ["/s/", "Ruth A. Hughes", "Associate Regional Administrator"]),
    ],
)  # fmt: skip
def test_the_signing_officials_typed_name_and_title_are_kept(state, rest, typed):
    ocr_text, _, kept = _page(state, rest)

    for line in typed:
        assert line in kept, line
        assert line not in ocr_text.splitlines()


def test_a_recognition_layer_that_agrees_with_ocr_keeps_what_ocr_missed():
    # AK-13-0027-MM1: the layer is invisible (a scanner's recognition) and agrees with OCR
    # on most words; OCR missed the title under the signature. "cc:" is a fragment, and
    # "Children's" is read by OCR's "Children’s", so neither is appended.
    ocr_text, layer_text, kept = _page("us-ak", "ak-13-0027-mm1/approval-document/page-3")

    assert "cc:" in _layer_lines(layer_text) and "Children’s Health" in ocr_text
    assert kept == ["Associate Regional Administrator"]


def test_a_layer_line_ocr_read_with_other_spacing_is_not_repeated():
    # ND-20-0004: the hidden layer runs the footer's words together; OCR has the same
    # characters, so the line the old rule appended is no longer repeated.
    ocr_text, layer_text, kept = _page("us-nd", "nd-20-0004/approval-document/page-3")

    assert _layer_lines(layer_text) == [
        "TN: ND-20-0004Approval Date: 6/16/2020Effective Date: 1/1/2020"
    ]
    assert "TN: ND-20-0004 Approval Date: 6/16/2020 Effective Date: 1/1/2020" in ocr_text
    assert kept == []


def test_a_one_line_recognition_layer_is_too_small_to_judge():
    # ND-20-0004 page 34: OCR missed the footer. The invisible layer has three words, too
    # few to judge the layer, so the footer's typed values are kept.
    ocr_text, _, kept = _page("us-nd", "nd-20-0004/approval-document/page-34")

    assert "6/16/2020" not in ocr_text
    assert kept == ["TN: ND-20-0004Approval Date: 6/16/2020Effective Date: 1/1/2020"]


def test_a_failed_recognition_layer_over_a_sideways_scan_is_not_appended():
    # UT-14-0007-MM page 21 is a slide scanned sideways: its invisible recognition layer is
    # noise ("Ckm", "rML"), and none of its words occurs in Tesseract's reading (itself
    # noise: "Applicant's Unborn Child(ren)" upside down). The old rule appended its
    # digit-bearing noise ("4COW", "9", "1 ,", "0").
    ocr_text, layer_text, kept = _page("us-ut", "ut-14-0007-mm/approval-document/page-21")

    assert "(uas)pjiy usoqun sjuerddy" in ocr_text
    assert {"Ckm", "rML", "4COW"} <= set(_layer_lines(layer_text))
    assert kept == []
    assert {"4COW", "9", "1 ,", "0"} <= set(
        _rule_854_kept(
            ocr_text,
            PAGES[SPA.format(state="us-ut", rest="ut-14-0007-mm/approval-document/page-21")][
                "layer_text"
            ],
        )
    )


def test_a_shifted_signature_string_is_not_appended():
    # ID-20-0001: the digital signature's invisible text is written one code above ASCII
    # ("Ejhjubmmz!tjhofe!cz" is "Digitally signed by") in the same Helvetica as the
    # run-together form labels, which map every code: a shifted string, not a font.
    # Two of its eight words occur in the OCR text: a failed layer.
    _, layer_text, kept = _page("us-id", "id-20-0001/approval-document/page-3")

    assert "Ejhjubmmz!tjhofe!cz!Svui!B/!Ivhift!" in _layer_lines(layer_text)
    assert kept == []


def test_a_mirrored_recognition_layer_is_not_appended():
    # MT-13-0048-MM page 19: the layer reads the page mirrored ("9120 le oiddV" for
    # "Approval date 0219"). The old rule appended six such lines.
    ocr_text, layer_text, kept = _page("us-mt", "mt-13-0048-mm/approval-document/page-19")

    assert "9120 le oiddV" in _layer_lines(layer_text)
    assert "9120 le oiddV" in _rule_854_kept(ocr_text, layer_text)
    assert kept == []


def test_garbled_font_lines_with_control_characters_are_still_dropped():
    # WA-19-0012: the typed fields sit in a font whose codes are 31 below ASCII, so a space
    # is U+0001. Seven of the eight lines hold a control character. The eighth, "%FQVUZ %"
    # ("Deputy D"), is painted and holds none, so it is kept: painted text is never removed.
    _, layer_text, kept = _page("us-wa", "wa-19-0012/approval-document/page-3")

    assert len(_layer_lines(layer_text)) == 8
    assert kept == ["%FQVUZ %"]


def test_recognition_specks_are_never_appended():
    # NJ-14-0002 page 9: the invisible layer's specks ("·", "··.", "~") have no letter
    # or digit. Its misreadings of words OCR read better are still appended: the layer
    # agrees with OCR on most words, so nothing separates them from text OCR missed.
    _, layer_text, kept = _page("us-nj", "nj-14-0002/approval-document/page-9")

    specks = [line for line in _layer_lines(layer_text) if not any(c.isalnum() for c in line)]
    assert len(specks) >= 10
    assert not set(specks) & set(kept)
    assert kept == [
        "train ina fc)r",
        ". P·rc>Vt ·",
        ".. ers .. ·.•· . eterrnt.ntnl Enttttes",
        "521",
    ]
