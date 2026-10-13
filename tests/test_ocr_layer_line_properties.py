"""Properties of the rules that merge a scanned page's text layer into its OCR text.

With ``ocr: true``, a page whose text layer is only an overlay is read by OCR, and the
layer's lines are merged after the OCR text in two steps.

``_without_failed_recognition_lines(lines, ocr_text)`` chooses the layer lines worth
merging from (text, painted) pairs. Its invariants, for every input:

R1. The result is the input's texts in order with some removed (a subsequence).
R2. Every painted line is kept: typed text is never removed.
R3. An invisible line is removed only when it is a fragment (fewer than three letters and
    no digit) or the invisible layer has failed: at least five distinct words of three or
    more letters, fewer than a third of them in the OCR text (``_reference_failed``).
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

Together (R2 and M2): every painted layer line with a letter or digit and no control
character is in the page text. "Held" is ``_reference_reads``, a brute-force definition
over every run of tokens written without the implementation's offset bookkeeping, so M2,
M4 and M8 are also differential tests; R3 is checked against ``_reference_failed``.

The page tests at the end run ``_pdf_page_text`` on the retained PDFs with Tesseract's
stored output for each page.
"""

from __future__ import annotations

import hashlib
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
    _with_unread_layer_lines,
    _without_failed_recognition_lines,
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


def _reference_failed(invisible: list[str], ocr_text: str) -> bool:
    """R3's failed layer, written out: >= 5 distinct words of 3+ letters, < 1/3 in OCR."""
    words = {
        word
        for line in invisible
        if not any(unicodedata.category(c) == "Cc" and not c.isspace() for c in line)
        for word in _words(line, 3)
    }
    ocr_words = _words(ocr_text, 1)
    found = [w for w in words if w in ocr_words or (len(w) >= 6 and w in "".join(ocr_words))]
    return len(words) >= 5 and 3 * len(found) < len(words)


def _fragment(line: str) -> bool:
    return sum(char.isalpha() for char in line) < 3 and not any(char.isdigit() for char in line)


# A small alphabet, so layer lines often occur in the OCR text, in part or whole: letters,
# digits, punctuation the edge rules treat differently, quote and dash variants, a
# non-ASCII letter, a soft hyphen (format character), a control character, and several
# kinds of whitespace.
CHARS = "abAB129.,/()$%-:'_’–é­\x01 \t\n "
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

    failed = _reference_failed([text for text, painted in lines if not painted], ocr_text)
    expected = [text for text, painted in lines if painted or not (failed or _fragment(text))]
    # R1, R2, R3 at once: exactly the painted lines and the invisible lines R3 spares.
    assert kept == expected


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
    failed = _reference_failed([text for text, painted in lines if not painted], ocr_text)
    kept_pairs = [
        (text, painted) for text, painted in lines if painted or not (failed or _fragment(text))
    ]

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
        line = " ".join(text.split())
        if painted and _is_text(line):
            assert _reference_reads(result, line), line


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
    # Words on a line with a control character (a garbled font) do not count.
    garbled = [("Ckm\x01rML\x01err\x01urrr\x01jhofe", False), ("approval date", False)]
    assert _without_failed_recognition_lines(garbled, agree) == [text for text, _ in garbled]
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


def _merged(page: dict) -> str:
    lines = [(text, painted) for text, painted in page["layer_lines"]]
    layer = "\n".join(_without_failed_recognition_lines(lines, page["ocr_text"]))
    return _with_unread_layer_lines(page["ocr_text"], layer)


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
        layer_lines = _pdf_layer_lines(pdf_page, extraction={})
        result = _pdf_page_text(pdf_page, extraction={"ocr": True})

    assert layer_text == page["layer_text"]
    assert [[text, painted] for text, painted in layer_lines] == page["layer_lines"]
    # Differential: the dict lines are the text output's lines.
    assert "\n".join(text for text, _ in layer_lines).splitlines() == layer_text.splitlines()
    assert result == _merged(page)
    # Every painted line of text is in the page text; the result is a fixed point.
    for text, painted in layer_lines:
        line = " ".join(text.split())
        if painted and _is_text(line):
            assert _reference_reads(result, line), line
    assert result.startswith(page["ocr_text"].rstrip("\n"))


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


def test_a_layer_in_a_shifted_font_is_not_appended():
    # ID-20-0001: the digital signature's invisible text has every code one above ASCII
    # ("Ejhjubmmz!tjhofe!cz" is "Digitally signed by"), beside run-together form labels.
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
