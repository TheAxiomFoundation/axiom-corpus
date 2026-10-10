"""How the provision-anchors parser assigns paragraph depth.

A stored eCFR section body keeps printed labels but not the italics that tell
CFR's fifth and sixth levels from its second and third, so one label can fit at
more than one depth. The parser places labels by sequence continuity. Three
kinds of test pin that down:

1. Examples — one per way the outline is printed, each a regression for a
   mis-nesting the 1.0.0 extractor produced.
2. Properties (Hypothesis) — an outline rendered the way eCFR prints one parses
   back to the same tree; for any input the accepted labels tile the body, a
   child lies inside its parent, and sibling labels increase.
3. A differential check — for real section bodies, the parser's paths equal
   the paragraph ids eCFR itself publishes for that section on that date.

Structural invariants alone cannot catch a mis-nested paragraph: the 1.0.0
tree for 42 CFR 435.603(f) tiled the body perfectly while filing (f)(3) under
(f)(2)(iii)(B). The round-trip property and the differential check are what
would have caught it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.anchors import (
    AnchorVerificationError,
    ProvisionAnchor,
    _build_tree,
    _Head,
    _iter_nodes,
    _label_ordinal,
    _scan_heads,
    generate_anchors_for_provision,
    verify_anchor,
)
from axiom_corpus.corpus.ecfr import EcfrPartTarget, iter_ecfr_title_provisions
from axiom_corpus.corpus.models import ProvisionRecord
from scripts.recover_ingest_batch import _ecfr_paragraph_records

FIXTURES = Path(__file__).parent / "fixtures" / "provision_anchors"
SECTION = "us/regulation/1/1/1"


def _provision(body: str, citation_path: str = SECTION) -> ProvisionRecord:
    return ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path=citation_path,
        id="00000000-0000-0000-0000-000000000001",
        version="test",
        body=body,
    )


def _anchors(body: str) -> list[ProvisionAnchor]:
    return generate_anchors_for_provision(_provision(body))


def _relative(anchor: ProvisionAnchor) -> str:
    return anchor.citation_path.removeprefix(anchor.parent_citation_path + "/")


def _paths(body: str) -> list[str]:
    return [_relative(anchor) for anchor in _anchors(body)]


def _texts(body: str) -> dict[str, str]:
    return {_relative(anchor): anchor.text for anchor in _anchors(body)}


def _paragraphs(*blocks: str) -> str:
    """Join blocks the way the eCFR extractor does: one paragraph per block."""
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- #
# Examples                                                                       #
# --------------------------------------------------------------------------- #


def test_numeral_after_a_capital_letter_continues_the_second_level() -> None:
    # The shape of 42 CFR 435.603(f). "(3)" follows "(B)": it is the next label
    # of (1), (2), not the first numeral under (B), which would be "(1)".
    body = _paragraphs(
        "(f) Household—(1) Basic rule. The household is the taxpayer's.",
        "(2) Tax dependents. The household is the taxpayer's, except for—",
        "(i) Individuals other than a spouse or child; and",
        "(ii) Individuals living with both parents; and",
        "(iii) Individuals claimed by a non-custodial parent. For this purpose—",
        "(A) A court order establishing physical custody controls; or",
        "(B) Otherwise the custodial parent is where the child spends most nights.",
        "(3) Neither filers nor dependents. The household consists of—",
        "(i) The individual's spouse;",
        "(ii) The individual's children; and",
        "(iii) The individual's parents.",
        "(iv) The age specified is either of the following—",
        "(A) Age 19; or",
        "(B) Age 19 or, for full-time students, age 21.",
        "(4) Married couples. Each spouse is in the other's household.",
        "(5) Family size. The agency may adopt the Exchange's rule.",
    )
    texts = _texts(body)
    assert list(texts) == [
        "f",
        "f/1",
        "f/2",
        "f/2/i",
        "f/2/ii",
        "f/2/iii",
        "f/2/iii/A",
        "f/2/iii/B",
        "f/3",
        "f/3/i",
        "f/3/ii",
        "f/3/iii",
        "f/3/iv",
        "f/3/iv/A",
        "f/3/iv/B",
        "f/4",
        "f/5",
    ]
    # The spans follow: (2) and its last descendant stop where (3) begins.
    assert texts["f/2"].endswith("spends most nights.")
    assert texts["f/2/iii/B"].startswith("(B) Otherwise")
    assert texts["f/2/iii/B"].endswith("spends most nights.")
    assert texts["f/3"].endswith("age 21.")
    assert texts["f/3/iv/B"] == "(B) Age 19 or, for full-time students, age 21."
    assert texts["f/5"] == "(5) Family size. The agency may adopt the Exchange's rule."


def test_a_genuine_fifth_level_list_stays_under_its_capital_letter() -> None:
    # "(1)" is the first label of a new list, so it nests; "(2)" continues it.
    body = _paragraphs(
        "(a) Scope—(1) Covered groups:",
        "(i) Aliens with one of the following statuses:",
        "(A) An alien who is a battered spouse, with—",
        "(1) Status as a spouse of a United States citizen;",
        "(2) Classification under clause (ii);",
        "(3) Suspension of deportation;",
        "(B) An alien who is a parolee.",
        "(ii) Citizens.",
        "(2) Excluded groups.",
    )
    assert _paths(body) == [
        "a",
        "a/1",
        "a/1/i",
        "a/1/i/A",
        "a/1/i/A/1",
        "a/1/i/A/2",
        "a/1/i/A/3",
        "a/1/i/B",
        "a/1/ii",
        "a/2",
    ]


def test_a_roman_numeral_after_a_fifth_level_list_resumes_the_third_level() -> None:
    # "(ii)" directly after the fifth-level "(2)": the next label of (i), not
    # (2)'s first roman child, which would be "(i)". The 7 CFR 246.7(d)(2)(v)
    # shape, which the 1.0.0 extractor filed under (d)(2)(iv)(D)(35).
    body = _paragraphs(
        "(a) General—(1) Rule:",
        "(i) First case:",
        "(A) With these parts:",
        "(1) Part one;",
        "(2) Part two.",
        "(ii) Second case.",
        "(iii) Third case.",
        "(2) Exception.",
    )
    assert _paths(body) == [
        "a",
        "a/1",
        "a/1/i",
        "a/1/i/A",
        "a/1/i/A/1",
        "a/1/i/A/2",
        "a/1/ii",
        "a/1/iii",
        "a/2",
    ]


def test_a_capital_letter_after_a_sixth_level_list_resumes_the_fourth_level() -> None:
    # "(B)" directly after the sixth-level "(ii)": the next label of (A).
    body = _paragraphs(
        "(a) General—(1) Rule:",
        "(i) First case:",
        "(A) With these parts:",
        "(1) Part one, either:",
        "(i) Option one; or",
        "(ii) Option two.",
        "(B) Without parts.",
        "(C) With other parts.",
        "(ii) Second case.",
    )
    assert _paths(body) == [
        "a",
        "a/1",
        "a/1/i",
        "a/1/i/A",
        "a/1/i/A/1",
        "a/1/i/A/1/i",
        "a/1/i/A/1/ii",
        "a/1/i/B",
        "a/1/i/C",
        "a/1/ii",
    ]


def _lettered(upto: str, *, last: str = "") -> list[str]:
    """Top-level paragraphs (a) … (upto), each with numbered children."""
    blocks = []
    for code in range(ord("a"), ord(upto) + 1):
        blocks += [f"({chr(code)}) Heading. (1) First.", "(2) Second."]
    return blocks + ([last] if last else [])


@pytest.mark.parametrize(
    ("following", "expected_tail"),
    [
        # Run-in first child: the 7 CFR 273.18(i) shape.
        (
            ["(i) Interstate claims. (1) Unless transferred.", "(2) You may accept."],
            ["i", "i/1", "i/2"],
        ),
        # Followed by the next letter.
        (["(i) Verification. Each month.", "(j) Notices."], ["i", "j"]),
        # The last paragraph of the section.
        (["(i) Effective date. This section applies."], ["i"]),
        # Reserved.
        (["(i) [Reserved]", "(j) Penalties."], ["i", "j"]),
        # Chained first child.
        (["(i)(1) First.", "(2) Second."], ["i", "i/1", "i/2"]),
    ],
)
def test_paragraph_i_after_h_is_a_paragraph(following: list[str], expected_tail: list[str]) -> None:
    # "(i)" after "(h)(2)" reads as (2)'s first roman child or as paragraph
    # (i). The labels that follow settle it.
    paths = _paths(_paragraphs(*_lettered("h"), *following))
    assert paths[-len(expected_tail) :] == expected_tail
    assert "h/2/i" not in paths
    # (h) stops where (i) starts.
    texts = _texts(_paragraphs(*_lettered("h"), *following))
    assert texts["h"].endswith("(2) Second.")


def test_a_roman_list_after_h_stays_roman() -> None:
    body = _paragraphs(
        *_lettered("g"),
        "(h) Heading. (1) First.",
        "(2) Second, one of:",
        "(i) Roman one; or",
        "(ii) Roman two.",
        "(i) Paragraph i.",
        "(j) Paragraph j.",
    )
    paths = _paths(body)
    assert paths[-7:] == ["h", "h/1", "h/2", "h/2/i", "h/2/ii", "i", "j"]


def test_the_label_confirmed_soonest_wins() -> None:
    # The 42 CFR 435.831(i) shape. Read as (h)(3)'s roman child, "(i)" would
    # still find a later label to agree with it (the second "(i)", as paragraph
    # (i)). Read as paragraph (i), the very next label confirms it: "(1)".
    body = _paragraphs(
        *_lettered("g"),
        "(h) Order of deduction. (1) By service date.",
        "(2) By bill date.",
        "(3) By submission date, under paragraph (h)(1) or (h)(2).",
        "(i) Eligibility based on incurred expenses. (1) An individual is eligible—",
        "(i) If spenddown is met; or",
        "(ii) If expenses are projected.",
        "(2) Other individuals.",
    )
    assert _paths(body)[-8:] == ["h/1", "h/2", "h/3", "i", "i/1", "i/1/i", "i/1/ii", "i/2"]


def test_chained_labels_open_first_children() -> None:
    # "(a)(1)": (a) has no text of its own. Its first child ends at "(2)" —
    # the recovery batch's stand-in row for 42 CFR 435.602(a)(1) ran to the end
    # of (a).
    body = _paragraphs(
        "(a)(1) Except as specified, the agency must consider income.",
        "(2) The agency may not consider relatives' income.",
        "(b)(1)(i) First.",
        "(ii) Second.",
        "(8) (i) Spaced chain.",
        "(ii) Its sibling.",
    )
    texts = _texts(body)
    assert list(texts) == [
        "a",
        "a/1",
        "a/2",
        "b",
        "b/1",
        "b/1/i",
        "b/1/ii",
        "b/8",
        "b/8/i",
        "b/8/ii",
    ]
    assert texts["a/1"] == "(1) Except as specified, the agency must consider income."
    assert texts["a"].endswith("relatives' income.")


def test_a_chained_label_that_is_not_a_first_label_is_a_reference() -> None:
    # "(b)(2)" at a line start reads as a chained head, but "(2)" is not a
    # first label and "of this section" follows: the whole line is a wrapped
    # citation, not paragraph (b).
    body = _paragraphs(
        "(a) Paragraph (b)(2) of this section applies.",
        "(b)(2) of this section is where that sentence wrapped.",
    )
    assert _paths(body) == ["a"]
    # Without the reference phrase, (b) is a paragraph and "(2)" is still not
    # its first child.
    body = _paragraphs("(a) First.", "(b)(2) Second.")
    assert _paths(body) == ["a", "b"]


@pytest.mark.parametrize(
    "heading",
    [
        "(d) How is income defined? (1) Income means gross income.",
        "(d) Data requirements.(1) States must evaluate their changes.",
        "(d) Data requirements: (1) States must evaluate their changes.",
        "(d) Data requirements—(1) States must evaluate their changes.",
    ],
)
def test_a_first_child_runs_in_after_its_parents_heading(heading: str) -> None:
    body = _paragraphs("(c) Earlier.", heading, "(2) Second.", "(i) Detail.", "(e) Later.")
    assert _paths(body) == ["c", "d", "d/1", "d/2", "d/2/i", "e"]


def test_an_inline_label_that_is_not_a_first_label_is_text() -> None:
    body = _paragraphs(
        "(a) Contact. Write to CMS; phone: (410) 786-4132 or (877) 267-2323.",
        "(b) See paragraph (a). (2) is not where a list starts.",
        "(c) Abbreviations. (PTC) means premium tax credit.",
    )
    assert _paths(body) == ["a", "b", "c"]


@pytest.mark.parametrize(
    "citation",
    [
        "(a) Scope. See: (1)(i) of this section.",
        "(a) Total.\n(b) Divide the total under paragraph\n(d)(1)(i) of this section by 4.33.",
        "(a) Total.\n(b) Meets the criteria at paragraphs\n(c)(1)(i)(A) through (C) of this section.",
        "(a) Total.\n(b) As described in paragraphs (a)(1) through\n(4) of this section.",
        "(a) Total.\n(b) Consistent with § 431.210(a) and\n(b) of this subchapter.",
        "(a) Total.\n(b) Under paragraph\n(a)(1), (2) and (3) of this section.",
    ],
)
def test_a_cited_run_of_labels_is_not_a_paragraph(citation: str) -> None:
    # A run of labels followed by "of this section", "through", "and (" or
    # ", (" cites other paragraphs, even at a line start (a wrapped Federal
    # Register line) or after a colon. Review of #812 found 2.0.0's first cut
    # anchored "(a) See: (1)(i) of this section." as a/1 and a/1/i.
    paths = _paths(_paragraphs(citation, "(z) Last."))
    assert paths[-1] == "z"
    assert all(len(path) == 1 for path in paths), paths


def test_a_paragraph_that_opens_in_lower_case_is_still_a_paragraph() -> None:
    # 7 CFR 273.7(c)(17)(iv)(B) begins "(B) of those required to participate".
    body = _paragraphs(
        "(a) Reports. (1) Mandatory programs.",
        "(i) The State shall report the following:",
        "(A) the number required to participate;",
        "(B) of those required to participate the number referred; and",
        "(C) the number found ineligible.",
    )
    assert _paths(body) == ["a", "a/1", "a/1/i", "a/1/i/A", "a/1/i/B", "a/1/i/C"]


def test_a_section_that_is_one_roman_list_stays_roman() -> None:
    # The first label sets the top-level form: "(i)" that opens a list is
    # roman, so (ii) and (iii) follow it. Review of #812 found the first cut
    # kept only (i).
    assert _paths(_paragraphs("(i) X.", "(ii) Y.", "(iii) Z.")) == ["i", "ii", "iii"]
    assert _paths(_paragraphs("(i) X.", "(j) Y.", "(k) Z.")) == ["i", "j", "k"]


def test_the_look_ahead_reads_each_head_a_bounded_number_of_times() -> None:
    # Every "(i)" below fits as a roman child and as the next top-level
    # numeral's sibling list, so each one triggers the look-ahead. It must
    # read forward from the head, not re-walk the list from the start (review
    # of #812: the first cut grew quadratically).
    class CountingHeads(list[_Head]):
        reads = 0

        def __getitem__(self, index):  # type: ignore[no-untyped-def]
            CountingHeads.reads += 1
            return super().__getitem__(index)

        def __iter__(self):  # type: ignore[no-untyped-def]
            for head in super().__iter__():
                CountingHeads.reads += 1
                yield head

    body = "\n".join(
        f"({n}) Root\n(i) Roman\n(A) Alpha\n(1) Num\n(i) One\n(ii) Two" for n in range(1000, 1400)
    )
    heads = CountingHeads(_scan_heads(body))
    _build_tree(body, heads)
    assert CountingHeads.reads <= 4 * len(heads)


def test_a_range_head_stands_for_every_label_it_spans() -> None:
    # 26 CFR 1.62-1: "(d)-(h) [Reserved]" is followed by paragraph (i).
    body = _paragraphs(
        "(a) General.",
        "(b) Definitions.",
        "(c) Deductions. (1) Allowed.",
        "(2) Not allowed.",
        "(d)-(h) [Reserved]",
        "(i) Effective date.",
        "(j) through (m) [Reserved]",
        "(n) Cross-reference.",
    )
    assert _paths(body) == ["a", "b", "c", "c/1", "c/2", "d", "i", "j", "n"]


def test_a_label_that_continues_no_open_sequence_stays_text() -> None:
    # A roman list printed directly under (a), and a "(B)" with no "(i)" open.
    # Neither is a top-level paragraph; (a) and (b) keep their full text.
    body = _paragraphs(
        "(a) Definitions. Like plan type means one of the following:",
        "(i) PDP replaced with another PDP.",
        "(ii) MA replaced with another MA.",
        "(b) Refunds—(1) Amounts incorrectly collected. (A) Means excess amounts;",
        "(B) Includes amounts collected in error.",
        "(c) Next.",
    )
    texts = _texts(body)
    assert list(texts) == ["a", "b", "b/1", "c"]
    assert texts["a"].endswith("(ii) MA replaced with another MA.")
    assert texts["b/1"].endswith("(B) Includes amounts collected in error.")


def test_a_mislabelled_item_does_not_derail_its_list() -> None:
    # 7 CFR 247.9(d)(3) prints "(xxiv)" where "(xxix)" belongs. The item has no
    # label of its own to stand on; the list carries on and (d)(4), (e) stay put.
    body = _paragraphs(
        "(d) Income. (1) Income means gross income.",
        "(2) Exclusions.",
        "(3) The agency must exclude:",
        "(i) First payment;",
        "(ii) Second payment;",
        "(iii) Third payment;",
        "(ii) Fourth payment, mislabelled;",
        "(v) Fifth payment.",
        "(4) The agency may average income.",
        "(e) Other options.",
    )
    texts = _texts(body)
    assert list(texts) == [
        "d",
        "d/1",
        "d/2",
        "d/3",
        "d/3/i",
        "d/3/ii",
        "d/3/iii",
        "d/3/v",
        "d/4",
        "e",
    ]
    assert texts["d/3/iii"].endswith("mislabelled;")


def test_a_restarted_top_level_list_still_fails_loudly() -> None:
    # Two lettered lists at the top level (question-and-answer sections) is an
    # outline this parser cannot represent. It must not guess.
    body = _paragraphs("(a) First answer.", "(b) More.", "(a) Second answer.")
    with pytest.raises(AnchorVerificationError, match="duplicate anchor citation paths"):
        _anchors(body)


def test_a_list_longer_than_the_alphabet_doubles_its_letters() -> None:
    blocks = [f"({chr(code)}) Term." for code in range(ord("a"), ord("z") + 1)]
    blocks += ["(aa) Term.", "(bb) Term. (1) Sense one.", "(2) Sense two."]
    assert _paths(_paragraphs(*blocks))[-5:] == ["z", "aa", "bb", "bb/1", "bb/2"]
    assert _label_ordinal("aa", "alpha_lower") == 27
    assert _label_ordinal("bb", "alpha_lower") == 28


def test_a_numbered_top_level_is_an_outline_too() -> None:
    body = _paragraphs(
        "(1) Applicant means one of:",
        "(i) An individual, either:",
        "(A) Seeking coverage; or",
        "(B) Renewing it.",
        "(ii) An employer.",
        "(2) Enrollee means a covered individual.",
    )
    assert _paths(body) == ["1", "1/i", "1/i/A", "1/i/B", "1/ii", "2"]


def test_omitted_paragraphs_leave_a_gap_not_a_new_level() -> None:
    # A slice of a section: (a), then (d) with its children.
    body = _paragraphs("(a) First.", "(d) Items:", "(1) One.", "(3) Three.")
    assert _paths(body) == ["a", "d", "d/1", "d/3"]


# --------------------------------------------------------------------------- #
# Invariants                                                                     #
# --------------------------------------------------------------------------- #


def _without_whitespace(text: str) -> str:
    return "".join(text.split())


def assert_outline_invariants(body: str) -> list[ProvisionAnchor] | None:
    """Check every invariant the parser promises for any body.

    Returns the anchors, or ``None`` when the parser refused the body because
    two labels would share a path (the one failure it is allowed).
    """
    try:
        anchors = generate_anchors_for_provision(_provision(body))
    except AnchorVerificationError as exc:
        assert "duplicate anchor citation paths" in str(exc)
        return None

    # Deterministic.
    again = generate_anchors_for_provision(_provision(body))
    assert [a.to_mapping() for a in again] == [a.to_mapping() for a in anchors]

    by_path = {anchor.citation_path: anchor for anchor in anchors}
    assert len(by_path) == len(anchors), "paths are unique"
    ordered = sorted(anchors, key=lambda anchor: anchor.char_start)
    assert ordered == anchors, "anchors come out in document order"
    starts = [anchor.char_start for anchor in ordered]
    assert starts == sorted(set(starts)), "no two labels share an offset"

    pieces: list[tuple[int, int]] = []
    for position, anchor in enumerate(ordered):
        # The two mechanical gates, and no trailing whitespace in a span.
        verify_anchor(anchor, body)
        assert anchor.text == anchor.text.rstrip(" \t\r\n")

        # A span runs exactly to the next paragraph that is not inside it.
        inside = anchor.citation_path + "/"
        after = [b for b in ordered[position + 1 :] if not b.citation_path.startswith(inside)]
        boundary = after[0].char_start if after else len(body)
        assert anchor.char_end <= boundary
        assert body[anchor.char_end : boundary].strip() == ""

        # A child lies inside its parent, after the parent's own label.
        parent = by_path.get(anchor.citation_path.rsplit("/", 1)[0])
        if parent is not None:
            assert parent.char_start < anchor.char_start
            assert anchor.char_end <= parent.char_end
            assert anchor.depth == parent.depth + 1

        # The text this paragraph adds: all of a leaf, or a parent's lead-in.
        following = ordered[position + 1] if position + 1 < len(ordered) else None
        if following is not None and following.citation_path.startswith(inside):
            pieces.append((anchor.char_start, following.char_start))
        else:
            pieces.append((anchor.char_start, anchor.char_end))

    # Tiling: leaf bodies and parent lead-ins, in order, are the section body
    # from its first label on. Nothing between them but whitespace, no overlap.
    for (_, end), (start, _) in zip(pieces, pieces[1:], strict=False):
        assert end <= start
        assert body[end:start].strip() == ""
    if pieces:
        first = pieces[0][0]
        rebuilt = "".join(body[start:end] for start, end in pieces)
        assert _without_whitespace(rebuilt) == _without_whitespace(body[first:])

    # Sibling labels of one form strictly increase below the top level, and the
    # top level holds at most the ladder's first form and the section's own.
    roots = _build_tree(body, _scan_heads(body))
    assert {root.form for root in roots} <= {"alpha_lower", roots[0].form if roots else ""}
    for node in _iter_nodes(roots):
        ordinals = [_label_ordinal(child.token, child.form) for child in node.children]
        assert len({child.form for child in node.children}) <= 1
        assert all(ordinal is not None for ordinal in ordinals)
        assert ordinals == sorted(set(ordinals)), "sibling labels strictly increase"
    return anchors


#: The six CFR paragraph levels (1 CFR 21.11): (a)(1)(i)(A)(1)(i).
LEVEL_FORMS = ("alpha_lower", "digit", "roman_lower", "alpha_upper", "digit", "roman_lower")
ROMAN = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii")
#: How a paragraph introduces its first child in print.
STYLES = ("line", "dash", "run_in", "question", "no_space", "chained")
WORDS = ("agency", "household", "income", "State", "must", "the", "of", "benefit", "period")


def _label(level: int, ordinal: int) -> str:
    form = LEVEL_FORMS[level]
    if form == "digit":
        return str(ordinal)
    if form == "roman_lower":
        return ROMAN[ordinal - 1]
    letter = chr(ord("a") + ordinal - 1)
    return letter if form == "alpha_lower" else letter.upper()


@dataclass
class Para:
    text: str
    style: str = "line"
    children: list[Para] = field(default_factory=list)


@st.composite
def outlines(draw: st.DrawFn, level: int = 0) -> list[Para]:
    """A well-formed outline: every list runs consecutively from its first label.

    Lists below the top level have at least two items, as drafting rules
    require; the parser's tie-breaks lean on that.
    """
    count = draw(st.integers(1, 11) if level == 0 else st.integers(2, 4))
    paragraphs = []
    for _ in range(count):
        text = " ".join(draw(st.lists(st.sampled_from(WORDS), min_size=1, max_size=5)))
        nested = level + 1 < len(LEVEL_FORMS) and draw(st.integers(0, 2 + level)) == 0
        children = draw(outlines(level + 1)) if nested else []
        style = draw(st.sampled_from(STYLES)) if children else "line"
        paragraphs.append(Para(text, style, children))
    return paragraphs


def _render(paragraphs: list[Para], level: int = 0) -> str:
    return "\n\n".join(
        _render_one(para, _label(level, ordinal), level)
        for ordinal, para in enumerate(paragraphs, start=1)
    )


def _render_one(para: Para, label: str, level: int) -> str:
    head = f"({label})"
    if not para.children:
        return f"{head} {para.text}."
    children = _render(para.children, level + 1)
    return {
        "line": f"{head} {para.text}:\n\n{children}",
        "dash": f"{head} {para.text}—{children}",
        "run_in": f"{head} {para.text}. {children}",
        "question": f"{head} {para.text}? {children}",
        "no_space": f"{head} {para.text}.{children}",
        "chained": f"{head}{children}",
    }[para.style]


def _expected_paths(paragraphs: list[Para], level: int = 0, prefix: str = "") -> list[str]:
    paths = []
    for ordinal, para in enumerate(paragraphs, start=1):
        path = prefix + _label(level, ordinal)
        paths.append(path)
        paths += _expected_paths(para.children, level + 1, path + "/")
    return paths


def _ends_one_list_where_another_resumes(paragraphs: list[Para]) -> bool:
    """Whether the outline has a label only italics could place.

    A second-level "(3)" that follows a fifth-level list which itself reached
    "(2)" reads equally well as that list's "(3)". The stored body has no
    italics, so the parser keeps such a label in the deeper list. Same for a
    third-level roman after a sixth-level list.
    """
    # [level, children seen] for each paragraph still open, outermost first.
    open_paragraphs: list[list[int]] = []

    def walk(nodes: list[Para], level: int) -> bool:
        for ordinal, para in enumerate(nodes, start=1):
            for open_level, seen in open_paragraphs:
                child_level = open_level + 1
                if (
                    open_level >= level
                    and child_level < len(LEVEL_FORMS)
                    and LEVEL_FORMS[child_level] == LEVEL_FORMS[level]
                    and ordinal >= 2
                    and seen == ordinal - 1
                ):
                    return True
            while open_paragraphs and open_paragraphs[-1][0] >= level:
                open_paragraphs.pop()
            if open_paragraphs:
                open_paragraphs[-1][1] = ordinal
            open_paragraphs.append([level, 0])
            if walk(para.children, level + 1):
                return True
        return False

    return walk(paragraphs, 0)


PROPERTY_SETTINGS = settings(
    max_examples=300,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


@PROPERTY_SETTINGS
@given(outlines())
def test_a_printed_outline_parses_back_to_itself(outline: list[Para]) -> None:
    assume(not _ends_one_list_where_another_resumes(outline))
    body = _render(outline)
    anchors = assert_outline_invariants(body)
    assert anchors is not None
    assert [_relative(anchor) for anchor in anchors] == _expected_paths(outline)
    # Every sibling sequence is consecutive from its first label.
    for node in _iter_nodes(_build_tree(body, _scan_heads(body))):
        ordinals = [_label_ordinal(child.token, child.form) for child in node.children]
        assert ordinals == list(range(1, len(ordinals) + 1))


@PROPERTY_SETTINGS
@given(outlines())
def test_every_printed_outline_keeps_the_invariants(outline: list[Para]) -> None:
    # Includes the outlines only italics could resolve: their paths may differ
    # from the generated ones, but the tree is still a tree over the body.
    anchors = assert_outline_invariants(_render(outline))
    assert anchors is not None
    assert len(anchors) <= len(_expected_paths(outline))


FRAGMENTS = (
    "(a)", "(b)", "(c)", "(h)", "(i)", "(j)", "(ii)", "(iii)", "(v)", "(x)",
    "(1)", "(2)", "(3)", "(A)", "(B)", "(aa)", "(PTC)", "(xxiv)", "(410) 786-4132",
    "(d)-(h) [Reserved]", "(b)(2) of this section", "\n\n", "\n", " ", ". ", "? ",
    ": ", ".", "—", "–", "-", "; ", "income ", "Heading", "[Reserved]",
)  # fmt: skip


@PROPERTY_SETTINGS
@given(st.lists(st.sampled_from(FRAGMENTS), max_size=40).map("".join))
def test_any_text_keeps_the_invariants(body: str) -> None:
    assert_outline_invariants(body)


@PROPERTY_SETTINGS
@given(st.text(max_size=200))
def test_arbitrary_text_never_breaks_the_parser(body: str) -> None:
    assert_outline_invariants(body)


def test_the_invariant_check_can_fail() -> None:
    # Anti-vacuous: a body the parser refuses returns None rather than passing,
    # and a real outline returns its anchors.
    assert assert_outline_invariants("(a) One.\n\n(a) One again.") is None
    assert len(assert_outline_invariants("(a) One.\n\n(b) Two.") or []) == 2


# --------------------------------------------------------------------------- #
# Differential: the parser against eCFR's published paragraph ids                #
# --------------------------------------------------------------------------- #

ECFR_SECTIONS = json.loads((FIXTURES / "ecfr_paragraph_ids.json").read_text())


@pytest.mark.parametrize(
    "section", ECFR_SECTIONS, ids=[section["citation"] for section in ECFR_SECTIONS]
)
def test_paths_equal_the_paragraph_ids_ecfr_publishes(section: dict) -> None:
    # eCFR renders each paragraph as <div id="p-435.603(f)(3)(iv)(A)">. Those
    # ids are the publisher's own reading of the outline, from markup the
    # stored body no longer has.
    body = section["body"]
    assert hashlib.sha256(body.encode()).hexdigest() == section["body_sha256"]
    anchors = generate_anchors_for_provision(_provision(body, section["citation_path"]))
    paths = [_relative(anchor) for anchor in anchors]
    assert sorted(paths) == sorted(section["ecfr_paragraph_ids"])
    assert not set(paths) & set(section["extractor_1_0_0_paths_not_in_ecfr"])
    assert assert_outline_invariants(body) is not None


def test_the_fixture_covers_the_reported_defect() -> None:
    # Anti-vacuous: the 435.603 fixture is the section the defect was reported
    # on, and its eCFR ids disagree with what the 1.0.0 extractor emitted.
    section = next(s for s in ECFR_SECTIONS if s["citation"] == "42 CFR 435.603")
    ids = set(section["ecfr_paragraph_ids"])
    assert {"f/3", "f/3/iv/B", "f/4", "f/5", "i"} <= ids
    assert {
        "f/2/iii/B/3",
        "f/2/iii/B/3/iv/B/4",
        "f/2/iii/B/3/iv/B/5",
        "h/3/i",
    } <= set(section["extractor_1_0_0_paths_not_in_ecfr"])
    assert sum(len(s["extractor_1_0_0_paths_not_in_ecfr"]) for s in ECFR_SECTIONS) >= 40


def test_recovery_paragraph_rows_follow_the_printed_outline() -> None:
    # The recovery batch turns each anchor into a paragraph row whose
    # citation path and parent come from the tree. Run 42 CFR 435.603 through
    # it from XML, as the batch does.
    section = next(s for s in ECFR_SECTIONS if s["citation"] == "42 CFR 435.603")
    paragraphs = "".join(f"<P>{escape(block)}</P>" for block in section["body"].split("\n\n"))
    xml = (
        '<ECFR><DIV5 N="435" TYPE="PART"><HEAD>Part 435</HEAD>'
        '<DIV8 N="§ 435.603" TYPE="SECTION"><HEAD>§ 435.603 Application of MAGI.</HEAD>'
        f"{paragraphs}</DIV8></DIV5></ECFR>"
    )
    structural = list(
        iter_ecfr_title_provisions(
            xml,
            (EcfrPartTarget(42, "435"),),
            "2026-06-25-test",
            "sources/test.xml",
            "2026-06-25",
            "2026-06-25",
        )
    )
    rows = {row.citation_path: row for row in _ecfr_paragraph_records(structural)}
    prefix = section["citation_path"] + "/"
    assert sorted(path.removeprefix(prefix) for path in rows) == sorted(
        section["ecfr_paragraph_ids"]
    )
    section_row = next(row for row in structural if row.kind == "section")
    for path, row in rows.items():
        assert row.parent_citation_path == path.rsplit("/", 1)[0]
        assert row.level == section_row.level + path.removeprefix(prefix).count("/") + 1
    f2 = rows[prefix + "f/2"].body or ""
    assert f2.endswith("the custodial parent is the parent with whom the child spends most nights.")
    assert (rows[prefix + "f/3"].body or "").startswith(
        "(3) Rules for individuals who neither file"
    )
    assert (rows[prefix + "f/5"].body or "").startswith("(5) For purposes of paragraph (f)(1)")
    assert (rows[prefix + "h"].body or "").count("(i) If the household income") == 0
    assert (rows[prefix + "i"].body or "").startswith("(i) If the household income")
