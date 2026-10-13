"""The source-coverage measure: examples, invariants and an independent recount.

Invariants (for every region and every extracted text):

- ``0 <= kept_words <= region_words`` and ``0 <= coverage <= 1``;
- coverage is 1.0 when the extracted text is the region's text;
- removing extracted text never raises ``kept_words`` or coverage;
- a change of case, whitespace or punctuation in the extracted text changes nothing;
- the missing runs partition the missing words: their lengths sum to
  ``region_words - kept_words``;
- the figures are a function of their inputs (two calls agree);
- ``kept_words`` equals a recount by an independent tokenizer and plain counting.
"""

from __future__ import annotations

import json
import unicodedata
from collections import Counter
from dataclasses import dataclass

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.source_coverage import (
    MISSING_RUN_HEAD_CHARS,
    MISSING_RUN_LIMIT,
    MISSING_RUN_TAIL_CHARS,
    REVIEW_COVERAGE,
    REVIEW_MIN_REGION_WORDS,
    SOURCE_COVERAGE_VERSION,
    MissingRun,
    SourceCoverage,
    SourceCoverageEntry,
    SourceCoverageReport,
    SourceRegion,
    UnmeasuredSource,
    measure_source_coverage,
    missing_run_lengths,
    needs_review,
    normalized,
    row_texts,
    words,
)

# --------------------------------------------------------------------------- words


def test_words_are_casefolded_runs_of_letters_and_digits() -> None:
    assert words("The OFFICE\u2019s \u201creport\u201d, \u00a75219-SS: $1,234.50 (a)(1)") == [
        "the",
        "office",
        "s",
        "report",
        "5219",
        "ss",
        "1",
        "234",
        "50",
        "a",
        "1",
    ]


def test_compatibility_forms_fold_to_the_same_words() -> None:
    # A ligature, full-width letters, a superscript and a no-break space.
    assert words("\ufb01le \uff21\uff22\uff23 x\u00b2 a\u00a0b") == ["file", "abc", "x2", "a", "b"]


def test_soft_hyphens_and_zero_width_characters_do_not_split_words() -> None:
    assert words("in\u00adcome elig\u200bible re\u200dport\ufeff") == [
        "income",
        "eligible",
        "report",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "the appli-\ncant must",
        "the appli- cant must",
        "the appli-  \n  cant must",
        "the appli\u2010\ncant must",
    ],
)
def test_a_word_hyphenated_at_a_line_end_is_joined(text: str) -> None:
    assert words(text) == ["the", "applicant", "must"]


def test_hyphens_inside_a_line_and_between_numbers_are_not_line_ends() -> None:
    assert words("self-employed 63-\n3022 pages 4 - 5 pre -tax") == [
        "self",
        "employed",
        "63",
        "3022",
        "pages",
        "4",
        "5",
        "pre",
        "tax",
    ]


def test_normalized_keeps_case_and_punctuation() -> None:
    assert normalized("Sec\u00adtion 5.\ufb01rst") == "Section 5.first"


# --------------------------------------------------------------------------- examples

# Maine Title 36 section 656 in miniature: the page prints numbered subsections with
# lettered paragraphs; the rows kept only the numbered heads (the loss #754 repairs).
MAINE_REGION = [
    "\u00a7656. Real estate",
    "1. Real estate. The following real estate is exempt from taxation:",
    "A. The aqueducts, pipes and conduits of any corporation supplying a municipality with water;",
    "B. Mines of gold, silver or baser metals, when opened and in the process of development;",
    "2. Personal property. The following personal property is exempt:",
    "A. Household furniture, including television sets and musical instruments;",
]
MAINE_ROWS = ["\u00a7656. Real estate", "1. Real estate.", "2. Personal property."]


def test_a_page_that_kept_only_its_numbered_heads_is_mostly_missing() -> None:
    figures = measure_source_coverage(MAINE_REGION, MAINE_ROWS)

    # 3 + 11 + 14 + 16 + 9 + 9 words printed; the three rows hold 3 words each.
    assert figures.region_words == len(words("\n".join(MAINE_REGION))) == 62
    assert figures.kept_words == 9
    assert figures.missing_words == 53
    assert figures.coverage == pytest.approx(9 / 62)
    # One run: the kept head "2. Personal property." is three words, too few to end it.
    (run,) = figures.longest_missing_runs
    assert (run.offset, run.words) == (6, 53)
    assert run.text.startswith(
        "The following real estate is exempt from taxation: A. The aqueducts"
    )
    assert run.text.endswith("television sets and musical instruments;")
    assert run.before == "\u00a7656. Real estate 1. Real estate."


def test_a_few_kept_words_do_not_end_a_run_and_four_do() -> None:
    region = ["lost1 lost2 kept1 kept2 kept3 lost3", "kept4 kept5 kept6 kept7", "lost4"]
    figures = measure_source_coverage(region, ["kept1 kept2 kept3", "kept4 kept5 kept6 kept7"])

    assert [(run.offset, run.words, run.text) for run in figures.longest_missing_runs] == [
        (0, 3, "lost1 lost2 kept1 kept2 kept3 lost3"),
        (10, 1, "lost4"),
    ]
    assert figures.missing_words == 4 == sum(run.words for run in figures.longest_missing_runs)


def test_words_are_counted_as_a_multiset() -> None:
    region = ["This notice applies. Benefits end in June.", "This notice applies."]
    once = measure_source_coverage(region, ["This notice applies."])
    twice = measure_source_coverage(region, ["This notice applies.", "This notice applies."])

    assert (once.region_words, once.kept_words) == (10, 3)
    assert twice.kept_words == 6
    # A phrase kept once covers one of its two printings, not both.
    assert [run.text for run in once.longest_missing_runs] == [
        "Benefits end in June. This notice applies."
    ]


def test_extra_extracted_words_never_count_for_more_than_the_region_holds() -> None:
    figures = measure_source_coverage(["income limit"], ["income income income limit title"])
    assert (figures.region_words, figures.kept_words, figures.coverage) == (2, 2, 1.0)


def test_a_lost_paragraph_is_one_run_though_its_common_words_survive_elsewhere() -> None:
    region = [
        "The applicant must file the form with the office of the state.",
        "A lost paragraph about the duties of the office and the state of the form.",
        "The office reviews the form and the state pays the applicant.",
    ]
    figures = measure_source_coverage(region, [region[0], region[2]])

    assert figures.kept_words == len(words(region[0])) + len(words(region[2]))
    assert [(run.offset, run.words) for run in figures.longest_missing_runs] == [
        (len(words(region[0])), len(words(region[1])))
    ]
    assert figures.longest_missing_runs[0].text == region[1]


def test_a_region_with_no_words_has_nothing_to_lose() -> None:
    figures = measure_source_coverage(["", " \u2014 "], ["anything"])
    assert (figures.region_words, figures.kept_words, figures.coverage) == (0, 0, 1.0)
    assert figures.longest_missing_runs == ()


def test_a_region_with_nothing_extracted_is_one_missing_run() -> None:
    figures = measure_source_coverage(["Section one.", "Section two."], [])
    assert (figures.region_words, figures.kept_words, figures.coverage) == (4, 0, 0.0)
    assert [
        (run.offset, run.words, run.text, run.before) for run in figures.longest_missing_runs
    ] == [(0, 4, "Section one. Section two.", "")]


def test_text_dropped_on_purpose_is_counted_apart() -> None:
    figures = measure_source_coverage(
        ["Eligibility rules apply."],
        ["Eligibility rules apply."],
        dropped=["Skip to content", "Home"],
    )
    assert (figures.region_words, figures.kept_words, figures.deliberately_dropped_words) == (
        3,
        3,
        4,
    )
    assert figures.coverage == 1.0


def test_text_dropped_after_it_was_read_leaves_the_region() -> None:
    region = ["Home About Contact", "63-3022. Additions to income.", "Body of the section."]
    figures = measure_source_coverage(
        region,
        ["63-3022. Additions to income.", "Body of the section."],
        dropped_from_region=[region[0]],
    )
    assert figures.deliberately_dropped_words == 3
    assert figures.region_words == len(words("\n".join(region))) - 3
    assert figures.kept_words == figures.region_words
    assert figures.longest_missing_runs == ()


def test_text_dropped_after_reading_counts_only_where_the_region_holds_it() -> None:
    figures = measure_source_coverage(["alpha beta"], ["alpha"], dropped_from_region=["beta gamma"])
    assert (figures.region_words, figures.kept_words, figures.deliberately_dropped_words) == (
        1,
        1,
        1,
    )


def test_a_long_run_is_recorded_by_its_opening_and_its_close() -> None:
    lost = " ".join(f"word{index}" for index in range(200))
    figures = measure_source_coverage([f"Kept heading. {lost}"], ["Kept heading."])
    run = figures.longest_missing_runs[0]

    assert run.words == 200
    assert len(run.text) <= MISSING_RUN_HEAD_CHARS + MISSING_RUN_TAIL_CHARS + 3
    assert run.text.startswith("word0 word1 ") and run.text.endswith(" word198 word199")
    assert " \u2026 " in run.text
    assert run.before == "Kept heading."


def test_only_the_longest_runs_are_recorded() -> None:
    kept = [" ".join(f"kept{index}{letter}" for letter in "abcd") for index in range(1, 16)]
    region = [f"{kept[index - 1]} lost{index} " + "gone " * index for index in range(1, 16)]
    figures = measure_source_coverage(region, kept)

    assert len(figures.longest_missing_runs) == MISSING_RUN_LIMIT == 10
    assert [run.words for run in figures.longest_missing_runs] == list(range(16, 6, -1))
    assert missing_run_lengths(region, kept) == list(range(2, 17))
    assert sum(missing_run_lengths(region, kept)) == figures.missing_words


def test_runs_of_equal_length_are_ordered_by_position() -> None:
    figures = measure_source_coverage(
        ["a1 a2 a3 a4 x1 b1 b2 b3 b4 x2 c1 c2 c3 c4 x3"], ["a1 a2 a3 a4 b1 b2 b3 b4 c1 c2 c3 c4"]
    )
    assert [(run.offset, run.text) for run in figures.longest_missing_runs] == [
        (4, "x1"),
        (9, "x2"),
        (14, "x3"),
    ]


def test_a_word_split_across_two_rows_is_read_in_each_row_alone() -> None:
    # The region is one text, so the page-break hyphenation joins; each row is its own.
    region = ["the appli-", "cant must file"]
    assert measure_source_coverage(region, ["the appli- cant must file"]).coverage == 1.0
    split = measure_source_coverage(region, ["the appli-", "cant must file"])
    assert (split.region_words, split.kept_words) == (4, 3)
    assert [run.text for run in split.longest_missing_runs] == ["applicant"]


# --------------------------------------------------------------------------- records


def test_figures_reject_impossible_values() -> None:
    with pytest.raises(ValueError, match="kept_words .* exceeds region_words"):
        SourceCoverage(region_words=3, kept_words=4)
    with pytest.raises(ValueError, match="region_words must be a non-negative integer"):
        SourceCoverage(region_words=-1, kept_words=0)
    with pytest.raises(ValueError, match="kept_words must be a non-negative integer"):
        SourceCoverage(region_words=1, kept_words=True)


def test_a_report_round_trips_through_its_mapping() -> None:
    report = SourceCoverageReport(
        sources=(
            SourceCoverageEntry(
                source_path="sources/us-xx/policy/v1/official-documents/a.html",
                source_format="html",
                region="html_main_content",
                figures=measure_source_coverage(MAINE_REGION, MAINE_ROWS, dropped=["Menu"]),
            ),
        ),
        unmeasured=(
            UnmeasuredSource(
                source_path="sources/us-xx/policy/v1/official-documents/b.csv", source_format="csv"
            ),
        ),
    )
    mapping = json.loads(json.dumps(report.to_mapping()))

    assert mapping["measure"] == SOURCE_COVERAGE_VERSION == "source-coverage-v1"
    assert list(mapping) == ["measure", "sources", "unmeasured"]
    assert list(mapping["sources"][0]) == [
        "source_path",
        "source_format",
        "region",
        "region_words",
        "kept_words",
        "deliberately_dropped_words",
        "longest_missing_runs",
    ]
    assert list(mapping["sources"][0]["longest_missing_runs"][0]) == [
        "offset",
        "words",
        "text",
        "before",
    ]
    assert SourceCoverageReport.from_mapping(mapping) == report


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda data: data.update(measure=""), "measure must be a non-empty string"),
        (lambda data: data.update(sources="x"), "sources and unmeasured must be lists"),
        (
            lambda data: data["sources"][0].update(region_words="3"),
            "region_words must be a non-negative",
        ),
        (lambda data: data["sources"][0].pop("kept_words"), "kept_words must be a non-negative"),
        (lambda data: data["sources"][0].update(kept_words=99), "exceeds region_words"),
        (lambda data: data["sources"][0].update(region=None), "region must be a non-empty string"),
        (lambda data: data["sources"][0].update(longest_missing_runs={}), "must be a list"),
        (
            lambda data: data["sources"][0].update(
                longest_missing_runs=[{"offset": 0, "words": 0, "text": ""}]
            ),
            "invalid missing run",
        ),
        (lambda data: data["unmeasured"].append("x"), "must be a mapping"),
    ],
)
def test_a_malformed_report_is_refused(change, message: str) -> None:
    data = SourceCoverageReport(
        sources=(
            SourceCoverageEntry(
                source_path="sources/a.html",
                source_format="html",
                region="html_main_content",
                figures=SourceCoverage(region_words=3, kept_words=2),
            ),
        )
    ).to_mapping()
    change(data)
    with pytest.raises(ValueError, match=message):
        SourceCoverageReport.from_mapping(data)


def test_a_region_must_be_started_before_it_is_measured() -> None:
    region = SourceRegion()
    region.read("text an unsupported path never declared")
    assert not region.measured
    with pytest.raises(ValueError, match="no region was read"):
        region.measure(["text"])


def test_a_region_collects_what_was_read_and_dropped() -> None:
    region = SourceRegion()
    region.start("html_main_content")
    region.drop("Skip to content")
    for text in ("Menu Home", "", "First paragraph.", "Second paragraph."):
        region.read(text)
    region.drop("Menu Home", read=True)
    region.drop("")

    assert region.measured and region.kind == "html_main_content"
    assert region.texts == ("Menu Home", "First paragraph.", "Second paragraph.")
    figures = region.measure(["First paragraph."])
    assert (figures.region_words, figures.kept_words, figures.deliberately_dropped_words) == (
        4,
        2,
        5,
    )


def test_the_review_bar_needs_a_region_of_fifty_words_under_half_kept() -> None:
    assert (REVIEW_COVERAGE, REVIEW_MIN_REGION_WORDS) == (0.5, 50)
    assert needs_review(SourceCoverage(region_words=50, kept_words=24))
    assert not needs_review(SourceCoverage(region_words=50, kept_words=25))
    assert not needs_review(SourceCoverage(region_words=49, kept_words=0))
    assert not needs_review(SourceCoverage(region_words=0, kept_words=0))


@dataclass
class _Row:
    heading: str | None
    body: str | None


def test_row_texts_are_each_rows_heading_then_body() -> None:
    rows = [
        _Row("Title", None),
        _Row("1. Head", "Body one."),
        _Row(None, "Body two."),
        _Row("", ""),
    ]
    assert row_texts(rows) == ["Title", "1. Head", "Body one.", "Body two."]


def test_a_missing_run_mapping_names_its_fields() -> None:
    assert MissingRun(offset=3, words=2, text="lost words", before="kept").to_mapping() == {
        "offset": 3,
        "words": 2,
        "text": "lost words",
        "before": "kept",
    }


# --------------------------------------------------------------------------- properties

# Letters and digits with the characters the normalisation acts on: case, ligatures and
# width variants, soft hyphens and zero-width characters, hyphens before line ends, and
# punctuation and whitespace of several kinds.
_ALPHABET = st.sampled_from(
    list("abcdeABCDE019")
    + ["\ufb01", "\uff21", "\u00e9", "\u0130", "\u00df", "\u00b2"]
    + ["\u00ad", "\u200b", "\ufeff"]
    + ["-", "\u2010", "\u2011", "\u2013"]
    + [" ", " ", "\n", "\t", "\u00a0"]
    + list(".,;:()[]$%/'_")
    + ["\u2019", "\u00a7"]
)
_TEXT = st.text(alphabet=_ALPHABET, max_size=60)
# A small vocabulary, so words repeat and the multiset counting is exercised.
_VOCABULARY = st.sampled_from(
    ["the", "of", "state", "income", "tax", "section", "1", "a", "shall", "be"]
)
_SENTENCE = st.lists(_VOCABULARY, max_size=25).map(" ".join)
_PIECES = st.lists(st.one_of(_TEXT, _SENTENCE), max_size=6)


def _independent_words(text: str) -> list[str]:
    """The words of ``text`` by a character loop, written without the module's patterns."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(char for char in text if char not in "\u00ad\u200b\u200c\u200d\u2060\ufeff")

    def letter(char: str) -> bool:
        return char.isalnum() and not char.isdecimal()

    joined: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in "-\u2010\u2011" and joined and letter(joined[-1]):
            end = index + 1
            while end < len(text) and text[end].isspace():
                end += 1
            if end > index + 1 and end < len(text) and letter(text[end]):
                index = end  # a line-end hyphen: drop it and the break after it
                continue
        joined.append(char)
        index += 1

    found: list[str] = []
    current = ""
    for char in joined:
        if char.isalnum():
            current += char
        elif current:
            found.append(current.casefold())
            current = ""
    if current:
        found.append(current.casefold())
    return found


def _independent_counts(texts: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(_independent_words(text))
    return counts


@given(_TEXT)
@settings(max_examples=400, deadline=None)
def test_words_agree_with_an_independent_tokenizer(text: str) -> None:
    assert words(text) == _independent_words(text)


@given(_PIECES, _PIECES, _PIECES, _PIECES)
@settings(max_examples=300, deadline=None)
def test_figures_are_bounded_and_match_an_independent_recount(
    region: list[str], extracted: list[str], dropped: list[str], set_aside: list[str]
) -> None:
    figures = measure_source_coverage(
        region, extracted, dropped=dropped, dropped_from_region=set_aside
    )

    assert 0 <= figures.kept_words <= figures.region_words
    assert 0.0 <= figures.coverage <= 1.0
    assert figures.deliberately_dropped_words >= 0
    assert figures.missing_words == figures.region_words - figures.kept_words

    region_counts = Counter(_independent_words("\n".join(region)))
    taken = Counter()
    for word, count in _independent_counts(set_aside).items():
        taken[word] = min(count, region_counts[word])
    left = Counter({word: count - taken[word] for word, count in region_counts.items()})
    extracted_counts = _independent_counts(extracted)
    assert figures.region_words == sum(left.values())
    assert figures.kept_words == sum(
        min(count, extracted_counts[word]) for word, count in left.items()
    )
    assert figures.deliberately_dropped_words == sum(_independent_counts(dropped).values()) + sum(
        taken.values()
    )


@given(_PIECES)
@settings(max_examples=300, deadline=None)
def test_coverage_is_one_when_the_extracted_text_is_the_regions_text(region: list[str]) -> None:
    figures = measure_source_coverage(region, ["\n".join(region)])
    assert figures.kept_words == figures.region_words
    assert figures.coverage == 1.0
    assert figures.longest_missing_runs == ()


@given(_TEXT)
@settings(max_examples=200, deadline=None)
def test_a_text_covers_itself(text: str) -> None:
    assert measure_source_coverage([text], [text]).coverage == 1.0


@given(_PIECES, _PIECES, st.data())
@settings(max_examples=300, deadline=None)
def test_removing_extracted_text_never_raises_coverage(
    region: list[str], extracted: list[str], data: st.DataObject
) -> None:
    keep = data.draw(st.lists(st.booleans(), min_size=len(extracted), max_size=len(extracted)))
    fewer = [text for text, kept in zip(extracted, keep, strict=True) if kept]
    full = measure_source_coverage(region, extracted)
    less = measure_source_coverage(region, fewer)

    assert less.region_words == full.region_words
    assert less.kept_words <= full.kept_words
    assert less.coverage <= full.coverage


@given(_PIECES, st.lists(_VOCABULARY, max_size=40), st.data())
@settings(max_examples=200, deadline=None)
def test_removing_extracted_words_never_raises_coverage(
    region: list[str], extracted_words: list[str], data: st.DataObject
) -> None:
    cut = data.draw(st.integers(min_value=0, max_value=len(extracted_words)))
    full = measure_source_coverage(region, [" ".join(extracted_words)])
    less = measure_source_coverage(region, [" ".join(extracted_words[:cut])])
    assert less.kept_words <= full.kept_words


@given(_PIECES, _PIECES, _PIECES)
@settings(max_examples=300, deadline=None)
def test_the_missing_runs_partition_the_missing_words(
    region: list[str], extracted: list[str], set_aside: list[str]
) -> None:
    figures = measure_source_coverage(region, extracted, dropped_from_region=set_aside)
    lengths = missing_run_lengths(region, extracted, dropped_from_region=set_aside)

    assert all(length >= 1 for length in lengths)
    assert sum(lengths) == figures.missing_words
    recorded = figures.longest_missing_runs
    assert len(recorded) == min(len(lengths), MISSING_RUN_LIMIT)
    assert [run.words for run in recorded] == sorted(lengths, reverse=True)[:MISSING_RUN_LIMIT]
    # Recorded runs are distinct stretches of the region: each starts at a word of the
    # region, and a later one starts after the missing words of the one before it.
    total = len(_independent_words("\n".join(region)))
    in_order = sorted(recorded, key=lambda run: run.offset)
    assert all(0 <= run.offset < total for run in in_order)
    assert all(
        first.offset + first.words <= second.offset
        for first, second in zip(in_order, in_order[1:], strict=False)
    )
    for run in recorded:
        assert run.text and run.text == " ".join(run.text.split())


@given(_PIECES, _PIECES, _PIECES, _PIECES)
@settings(max_examples=150, deadline=None)
def test_the_figures_are_a_function_of_their_inputs(
    region: list[str], extracted: list[str], dropped: list[str], set_aside: list[str]
) -> None:
    first = measure_source_coverage(
        region, extracted, dropped=dropped, dropped_from_region=set_aside
    )
    again = measure_source_coverage(
        list(region), list(extracted), dropped=tuple(dropped), dropped_from_region=tuple(set_aside)
    )
    assert first == again
    assert first.to_mapping() == again.to_mapping()
    assert SourceCoverage.from_mapping(json.loads(json.dumps(first.to_mapping()))) == first


@given(_PIECES, st.lists(_SENTENCE, max_size=5))
@settings(max_examples=200, deadline=None)
def test_case_whitespace_and_punctuation_of_the_extracted_text_do_not_matter(
    region: list[str], extracted: list[str]
) -> None:
    plain = measure_source_coverage(region, extracted)
    changed = measure_source_coverage(
        region, [text.upper().replace(" ", " ,\n\t(") + " ." for text in extracted]
    )
    assert (changed.region_words, changed.kept_words) == (plain.region_words, plain.kept_words)


@given(st.lists(_VOCABULARY, min_size=1, max_size=40), st.data())
@settings(max_examples=200, deadline=None)
def test_what_is_kept_of_the_region_is_exactly_what_was_extracted_from_it(
    region_words: list[str], data: st.DataObject
) -> None:
    keep = data.draw(
        st.lists(st.booleans(), min_size=len(region_words), max_size=len(region_words))
    )
    kept = [word for word, flag in zip(region_words, keep, strict=True) if flag]
    figures = measure_source_coverage([" ".join(region_words)], [" ".join(kept)])
    assert figures.kept_words == len(kept)
    assert figures.missing_words == len(region_words) - len(kept)


@given(_PIECES, _PIECES)
@settings(max_examples=150, deadline=None)
def test_how_the_region_is_cut_into_pieces_does_not_change_the_figures(
    region: list[str], extracted: list[str]
) -> None:
    whole = measure_source_coverage(["\n".join(region)], extracted)
    pieces = measure_source_coverage(region, extracted)
    assert pieces == whole


@given(_PIECES, _PIECES, _PIECES)
@settings(max_examples=150, deadline=None)
def test_setting_text_aside_never_adds_missing_words(
    region: list[str], extracted: list[str], set_aside: list[str]
) -> None:
    plain = measure_source_coverage(region, extracted)
    aside = measure_source_coverage(region, extracted, dropped_from_region=set_aside)
    assume(plain.region_words > 0)
    assert aside.region_words <= plain.region_words
    assert aside.missing_words <= plain.missing_words
