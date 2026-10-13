"""Properties of the rule that merges a scanned page's text layer into its OCR text.

``_with_unread_layer_lines(ocr_text, layer_text)`` is the body of a page that ``ocr: true``
reads by OCR although it has a text layer. Its invariants, for every input:

1. Prefix: with OCR text, the result starts with it (less trailing newlines), and is the
   OCR text exactly when no line is kept.
2. Containment: every layer line with a letter or digit and no control character is held
   by the result: its characters in order, as whole tokens, whatever the spacing next to a
   letter. No such line is lost.
3. Nothing is appended when OCR read every line: a layer made of the OCR text's own
   tokens, regrouped into lines, respaced next to letters and trimmed of edge punctuation,
   adds nothing.
4. The kept lines are exactly the layer lines OCR does not hold, each once, in layer
   order. None holds a control character, and each has a letter or digit.
5. Idempotence: merging the same layer into the result again changes nothing.
6. Without OCR text the layer comes back unchanged.
7. More OCR text never keeps more: text added after the OCR text cannot make a line
   unread. Each line's fate is independent of the other layer lines.
8. Against the rule this replaces (PR #854: keep a line when one of its tokens with a digit
   is not among OCR's tokens): every line that rule kept is still held by the result.

"Held" is ``_reference_reads``: a brute-force definition over every run of tokens, written
without the offset bookkeeping the implementation uses, so properties 2, 4 and 8 are also
a differential test of the two.

Intended, and pinned by the page tests at the end: a layer line that is not typed text
but has letters and no control character (a failed recognition layer over a sideways
scan, a font whose codes are shifted by one) is kept too. Nothing in the text tells it
from a typed name.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.documents import _with_unread_layer_lines

# The reference's own copy of the edge punctuation: a leading currency sign or minus and a
# trailing percent sign are part of a value.
_LEAD = re.compile(r"^[^\w$€£%-]+")
_TRAIL = re.compile(r"[^\w%]+$")


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
    letter and the punctuation leading the run's first token or trailing its last."""
    target = _fold(line.split())
    tokens = text.split()
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
    """The lines PR #854's rule kept (copied from f98fa2bbd, for property 8)."""
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


# A small alphabet, so layer lines often occur in the OCR text, in part or whole: letters,
# digits, punctuation the edge rules treat differently, a non-ASCII letter, a soft hyphen
# (format character), a control character, and several kinds of whitespace.
CHARS = "abAB129.,/()$%-:'_é­\x01 \t\n "
TEXT = st.text(alphabet=st.sampled_from(CHARS), max_size=48)
OCR = TEXT.filter(lambda text: bool(text.split()))
TOKEN = st.text(alphabet=st.sampled_from("abAB129.,/()$%-:'_é"), min_size=1, max_size=6)


@settings(max_examples=600, deadline=None)
@given(OCR, TEXT)
def test_result_is_the_ocr_text_plus_exactly_the_unread_layer_lines(ocr_text, layer_text):
    result = _with_unread_layer_lines(ocr_text, layer_text)

    expected = [
        line
        for line in _layer_lines(layer_text)
        if _is_text(line) and not _reference_reads(ocr_text, line)
    ]
    # Properties 1 and 4 (and the fast search against the brute-force reference).
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
        # Trim part of the punctuation leading the run and trailing it.
        lead, _ = _edges(run[0])
        _, trail = _edges(run[-1])
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
        lines.append(line)
    return ocr_text, tokens, lines


@settings(max_examples=600, deadline=None)
@given(_ocr_and_a_layer_it_read())
def test_nothing_is_appended_when_ocr_read_every_line(case):
    ocr_text, tokens, lines = case

    # Runs of the OCR text's tokens, respaced only next to letters and trimmed only of
    # edge punctuation, in any order and repeated.
    assert _with_unread_layer_lines(ocr_text, "\n".join(lines)) == ocr_text
    # The OCR text's own lines and tokens are always read.
    assert _with_unread_layer_lines(ocr_text, ocr_text) == ocr_text
    assert _with_unread_layer_lines(ocr_text, "\n".join(tokens)) == ocr_text


@settings(max_examples=400, deadline=None)
@given(TEXT, TEXT)
def test_merging_the_same_layer_twice_changes_nothing(ocr_text, layer_text):
    once = _with_unread_layer_lines(ocr_text, layer_text)

    assert _with_unread_layer_lines(once, layer_text) == once


@given(st.text(alphabet=st.sampled_from(" \t\n ​"), max_size=6), TEXT)
def test_without_ocr_text_the_layer_is_returned_unchanged(blank, layer_text):
    assert _with_unread_layer_lines(blank, layer_text) == layer_text


@settings(max_examples=400, deadline=None)
@given(OCR, TEXT, TEXT, TEXT)
def test_more_ocr_text_or_more_layer_lines_never_unkeep_a_line(
    ocr_text, more_ocr, layer_text, more_layer
):
    kept = _kept(ocr_text, _with_unread_layer_lines(ocr_text, layer_text))

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
    assert not _reference_reads("Total 2024", "24")
    assert not _reference_reads("1\n2\n3", "12")
    assert not _reference_reads("Date: 11/21/2013", "Date: 11/ 21/ 2013")
    assert not _reference_reads("2024. 5 items", ".5")
    assert not _reference_reads("-5 $5 5%", "5")
    assert not _reference_reads("March 19, 2014", "November 19, 2014")


# --------------------------------------------------------------------------- real pages

PAGES = json.loads(
    (
        Path(__file__).parent / "fixtures" / "ocr_overlay" / "cms_state_plan_layer_pages.json"
    ).read_text(encoding="utf-8")
)["pages"]
SPA = "{state}/policy/cms/medicaid-state-plan/spa/{rest}"


def _page(state: str, rest: str) -> tuple[str, str, list[str]]:
    page = PAGES[SPA.format(state=state, rest=rest)]
    result = _with_unread_layer_lines(page["ocr_text"], page["layer_text"])
    return page["ocr_text"], page["layer_text"], _kept(page["ocr_text"], result)


@pytest.mark.parametrize("path", sorted(PAGES))
def test_real_pages_hold_every_layer_line_of_text(path):
    page = PAGES[path]
    result = _with_unread_layer_lines(page["ocr_text"], page["layer_text"])

    assert result.startswith(page["ocr_text"].rstrip("\n"))
    for line in _layer_lines(page["layer_text"]):
        if _is_text(line):
            assert _reference_reads(result, line), line
    assert _with_unread_layer_lines(result, page["layer_text"]) == result


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
        (
            "us-ak",
            "ak-13-0027-mm1/approval-document/page-3",
            ["cc:", "Associate Regional Administrator"],
        ),
        (
            "us-ne",
            "ne-12-07/form-cms-179/page-1",
            ["James G. Scott", "Associate Regional Administrator", "/s/"],
        ),
        (
            "us-in",
            "in-12-014/form-cms-179/page-1",
            ["Verlon Johnson", "Associate Regional Administrator"],
        ),
        (
            "us-in",
            "in-15-008/approval-document/page-3",
            ["/s/", "Ruth A. Hughes", "Associate Regional Administrator"],
        ),
        (
            "us-mn",
            "mn-18-0002/approval-document/page-3",
            ["Ruth A. Hughes", "Associate Regional Administrator"],
        ),
        (
            "us-ny",
            "ny-17-0014/approval-document/page-3",
            ["MICHAEL MELENDEZ", "ASSOCIATE REGIONAL ADMINISTRATOR"],
        ),
        (
            "us-ny",
            "ny-17-0069/approval-document/page-3",
            ["NOVEMBER 21, 2019", "ACTING DEPUTY DIRECTOR"],
        ),
        ("us-ny", "ny-19-0046/approval-document/page-3", ["ACTING DEPUTY DIRECTOR"]),
        (
            "us-oh",
            "oh-13-014/approval-document/page-3",
            [".s.", "Alan Freund", "Acting Associate Regional Administrator"],
        ),
        (
            "us-oh",
            "oh-15-001/approval-document/page-3",
            ["/s/", "Ruth A. Hughes", "Associate Regional Administrator"],
        ),
    ],
)
def test_the_signing_officials_typed_name_and_title_are_kept(state, rest, typed):
    ocr_text, _, kept = _page(state, rest)

    for line in typed:
        assert line in kept, line
        assert line not in ocr_text.splitlines()


def test_a_layer_line_ocr_read_with_other_spacing_is_not_repeated():
    # ND-20-0004: the hidden layer runs the footer's words together; OCR has the same
    # characters, so the line the old rule appended is no longer repeated.
    ocr_text, layer_text, kept = _page("us-nd", "nd-20-0004/approval-document/page-3")

    assert _layer_lines(layer_text) == [
        "TN: ND-20-0004Approval Date: 6/16/2020Effective Date: 1/1/2020"
    ]
    assert "TN: ND-20-0004 Approval Date: 6/16/2020 Effective Date: 1/1/2020" in ocr_text
    assert kept == []


def test_garbled_font_lines_with_control_characters_are_still_dropped():
    # WA-19-0012: the typed fields sit in a font whose codes are 31 below ASCII, so a space
    # is U+0001. Seven of the eight lines hold a control character.
    _, layer_text, kept = _page("us-wa", "wa-19-0012/approval-document/page-3")

    assert len(_layer_lines(layer_text)) == 8
    assert kept == ["%FQVUZ %"]  # "Deputy D": no control character, so kept (intended)


def test_lines_without_a_letter_or_digit_are_not_text():
    # NJ-14-0002: a recognition layer's specks ("·", "··.", "~") are never appended.
    _, layer_text, kept = _page("us-nj", "nj-14-0002/approval-document/page-9")

    specks = [line for line in _layer_lines(layer_text) if not any(c.isalnum() for c in line)]
    assert len(specks) >= 10
    assert not set(specks) & set(kept)
    assert all(any(char.isalnum() for char in line) for line in kept)


def test_a_failed_recognition_layer_is_kept_too():
    # Intended. UT-14-0007-MM page 21 is a slide scanned sideways: its hidden recognition
    # layer is noise ("Ckm", "rML"), and so is Tesseract's reading. No test on the text
    # separates this from typed text, so every line with a letter or digit is kept.
    ocr_text, layer_text, kept = _page("us-ut", "ut-14-0007-mm/approval-document/page-21")

    assert "(uas)pjiy usoqun sjuerddy" in ocr_text  # "Applicant's Unborn Child(ren)", inverted
    assert kept == _layer_lines(layer_text)
    assert "Ckm" in kept and "rML" in kept


def test_a_layer_in_a_shifted_font_without_control_characters_is_kept_too():
    # Intended. ID-20-0001: the digital signature's hidden text has every code one above
    # ASCII ("Ejhjubmmz!tjhofe!cz" is "Digitally signed by"). It holds no control
    # character, so it is kept as it is. Of the form labels, OCR read "(Check One):" and
    # misread "(If Applicable):" as "(/f Applicable):", so only the second is kept.
    ocr_text, _, kept = _page("us-id", "id-20-0001/approval-document/page-3")

    assert "(Check One):" in ocr_text and "(/f Applicable):" in ocr_text
    assert kept == [
        "IfApplicable)",
        "Svui!B/!Ivhift",
        "Ejhjubmmz!tjhofe!cz!Svui!B/!Ivhift!",
        "Ebuf;!3131/17/41!27;58;53!.16(11(",
    ]
