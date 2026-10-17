"""Version identity for concurrent California LegInfo versions (``california_versions``)."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from axiom_corpus.corpus.california_versions import (
    ALL_VERSIONS,
    LegInfoVersion,
    leginfo_act_slug,
    leginfo_note_clauses,
    leginfo_page_version,
    leginfo_variant_slug,
    parse_leginfo_act_slug,
    parse_leginfo_picker,
    validate_leginfo_selector,
)
from axiom_corpus.corpus.citation_segment import (
    VARIANT_SEPARATOR,
    citation_segment,
    variant_segment,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
CITATION_PATH_PATTERN = re.compile(
    json.loads((REPO_ROOT / "schema/citation-path.v1.json").read_text())["$defs"]["citation_path"][
        "pattern"
    ]
)
# The WIC 11450 picker LegInfo served on 2026-07-14, retained by the July recovery.
RECOVERY_WIC_PICKER = (
    CORPUS_ROOT / "sources/us-ca/statute/2026-07-13-recovery/official-documents/us-ca-code-wic"
)
CALWORKS_WIC_11450 = (
    CORPUS_ROOT
    / "sources/us-ca/statute/2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12"
    "-wic-11451.5-wic-11452-wic-11452.018/california-leginfo-sections/WIC-11450.html"
)

# History notes LegInfo printed for every concurrent version of every multi-version
# section the corpus carried on 2026-09-26, with the slug each must get.
OBSERVED_NOTES = (
    (
        ("2024", "798", "1"),
        "(Amended (as amended by Stats. 2022, Ch. 715, Sec. 2) by Stats. 2024, Ch. 798, Sec. 1. "
        "(SB 1415) Effective January 1, 2025. Section conditionally operative July 1, 2021, or "
        "later date, as prescribed by its own provisions. Conditionally inoperative on or after "
        "July 1, 2024, by its own provisions. Repealed conditionally by its own provisions. See "
        "later operative version, as amended by Sec. 2 of Stats. 2026, Ch. 310.)",
        "operative-2021-07-01",
        {
            "operative": {"date": "2021-07-01", "conditional": True},
            "inoperative": {"date": "2024-07-01", "conditional": True},
        },
    ),
    (
        ("2024", "798", "2"),
        "(Amended (as added by Stats. 2022, Ch. 715, Sec. 3) by Stats. 2024, Ch. 798, Sec. 2. "
        "(SB 1415) Effective January 1, 2025. Conditionally operative on or after July 1, 2024, "
        "by its own provisions.)",
        "operative-2024-07-01",
        {"operative": {"date": "2024-07-01", "conditional": True}},
    ),
    (
        ("2026", "310", "2"),
        "(Amended (as amended by Stats. 2024, Ch. 798, Sec. 2) by Stats. 2026, Ch. 310, Sec. 2. "
        "(AB 2765) Effective September 18, 2026. Conditionally operative on or after July 1, "
        "2024, by its own provisions.)",
        "operative-2024-07-01",
        {"operative": {"date": "2024-07-01", "conditional": True}},
    ),
    (
        ("2019", "27", "59"),
        "(Amended by Stats. 2019, Ch. 27, Sec. 59. (SB 80) Effective June 27, 2019. Repealed on "
        "or after June 1, 2020, as prescribed by its own provisions.)",
        "repealed-2020-06-01",
        {"repealed": {"date": "2020-06-01", "conditional": False}},
    ),
    (
        ("2022", "588", "5"),
        "(Amended (as added by Stats. 2019, Ch. 27, Sec. 60) by Stats. 2022, Ch. 588, Sec. 5. "
        "(AB 2300) Effective January 1, 2023. Section conditionally operative June 1, 2020, or "
        "after, as prescribed by its own provisions. Conditionally inoperative on or after "
        "October 1, 2024, by its own provisions. Repealed conditionally by its own provisions. "
        "See later operative version added by Sec. 6 of Stats. 2022, Ch. 588.)",
        "operative-2020-06-01",
        {
            "operative": {"date": "2020-06-01", "conditional": True},
            "inoperative": {"date": "2024-10-01", "conditional": True},
        },
    ),
    (
        ("2022", "588", "6"),
        "(Repealed (in Sec. 5) and added by Stats. 2022, Ch. 588, Sec. 6. (AB 2300) Effective "
        "January 1, 2023. Conditionally operative on or after October 1, 2024, by its own "
        "provisions.)",
        "operative-2024-10-01",
        {"operative": {"date": "2024-10-01", "conditional": True}},
    ),
    (
        ("2002", "34", "22"),
        "(Added by Stats. 2002, Ch. 34, Sec. 22. Effective May 8, 2002. See identical section "
        "added by Stats. 2002, Ch. 35.)",
        "stats-2002-ch-34-sec-22",
        {},
    ),
    (
        ("2002", "35", "22"),
        "(Added by Stats. 2002, Ch. 35, Sec. 22. Effective May 8, 2002.)",
        "stats-2002-ch-35-sec-22",
        {},
    ),
)


@pytest.mark.parametrize(("triple", "note", "slug", "clauses"), OBSERVED_NOTES)
def test_every_observed_leginfo_note_gets_its_slug_and_clauses(triple, note, slug, clauses):
    version = LegInfoVersion(*triple)
    assert leginfo_variant_slug(note, version) == slug
    assert leginfo_note_clauses(note) == clauses
    assert validate_leginfo_selector(slug) == slug


def test_the_slugs_of_one_section_are_distinct():
    by_section = {"11450": OBSERVED_NOTES[:3:2], "11451.5": OBSERVED_NOTES[3:6]}
    for rows in by_section.values():
        slugs = [leginfo_variant_slug(note, LegInfoVersion(*triple)) for triple, note, *_ in rows]
        assert len(set(slugs)) == len(slugs)


def test_a_note_naming_an_impossible_date_raises():
    with pytest.raises(ValueError, match="impossible operative date 'February 30, 2024'"):
        leginfo_variant_slug(
            "(Conditionally operative on or after February 30, 2024.)",
            LegInfoVersion("2024", "1", "1"),
        )


def test_the_slug_of_the_later_wic_11450_version_survives_ab_2765():
    """LegInfo re-keyed WIC 11450's later version from Stats. 2024, Ch. 798, Sec. 2
    (2026-09-25) to Stats. 2026, Ch. 310, Sec. 2 (2026-09-26). Its path must not move."""
    before, after = OBSERVED_NOTES[1], OBSERVED_NOTES[2]
    assert LegInfoVersion(*before[0]).act_slug != LegInfoVersion(*after[0]).act_slug
    assert leginfo_variant_slug(before[1], LegInfoVersion(*before[0])) == leginfo_variant_slug(
        after[1], LegInfoVersion(*after[0])
    )


def test_act_slugs_label_each_leginfo_field_and_omit_empty_ones():
    assert leginfo_act_slug("2024", "798", "2") == "stats-2024-ch-798-sec-2"
    assert leginfo_act_slug("2004", "", "12") == "stats-2004-sec-12"  # Prop. 63 (RTC 17043)
    assert leginfo_act_slug("1955", "939", "") == "stats-1955-ch-939"  # RTC 17001
    assert LegInfoVersion("2004", "", "12").label == "Stats. 2004, Sec. 12"
    assert LegInfoVersion("2026", "310", "2").label == "Stats. 2026, Ch. 310, Sec. 2"
    with pytest.raises(ValueError, match="op_statues"):
        leginfo_act_slug("", "798", "2")
    with pytest.raises(ValueError, match="slug-safe"):
        leginfo_act_slug("2024", "7-98", "2")


def test_selectors_accept_all_role_and_act_slugs_only():
    assert validate_leginfo_selector(" ALL ") == ALL_VERSIONS
    assert validate_leginfo_selector("Operative-2024-07-01") == "operative-2024-07-01"
    assert validate_leginfo_selector("stats-2002-ch-35-sec-22") == "stats-2002-ch-35-sec-22"
    for bad in ("", "latest", "operative-2024-7-1", "operative-2024-02-30", "stats-", "v2"):
        with pytest.raises(ValueError):
            validate_leginfo_selector(bad)


def test_the_retained_recovery_picker_parses_into_leginfo_s_two_links():
    picker = parse_leginfo_picker(RECOVERY_WIC_PICKER.read_bytes())
    assert picker is not None
    assert picker.action == "/faces/selectFromMultiples.xhtml"
    assert [link.version.normalized() for link in picker.links] == [
        ("2024", "798", "1"),
        ("2024", "798", "2"),
    ]
    assert picker.links[1].text == (
        "(Amended (as added by Stats. 2022, Ch. 715, Sec. 3) by Stats. 2024, Ch. 798, Sec. 2.)"
    )
    assert picker.links[1].command_key == "selectFromMultiples:j_idt139:1:j_idt141"
    payload = picker.post_payload(picker.links[1])
    assert payload["op_section"] == "2"
    assert payload["sectionNum"] == "11450."
    assert "javax.faces.ViewState" in payload
    assert "javax.faces.ViewState" not in picker.retrieval_fields(picker.links[1])


def test_a_section_page_is_not_a_picker_and_names_its_own_version():
    html = CALWORKS_WIC_11450.read_bytes()
    assert parse_leginfo_picker(html) is None
    assert leginfo_page_version(html) == LegInfoVersion("2024", "798", "1")
    assert leginfo_page_version(b"<html><body>no script</body></html>") is None


# --- properties -----------------------------------------------------------------------

_VALUES = st.from_regex(r"[0-9a-z]{1,4}(\.[0-9a-z]{1,3})?", fullmatch=True)
_TRIPLES = st.tuples(_VALUES, st.one_of(st.just(""), _VALUES), st.one_of(st.just(""), _VALUES))
_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
_DATES = st.dates(min_value=date(1850, 1, 1), max_value=date(2099, 12, 31))


def _long(value: date) -> str:
    return f"{_MONTHS[value.month - 1]} {value.day}, {value.year}"


@given(_TRIPLES)
def test_act_slugs_round_trip_and_stay_one_grammar_safe_segment(triple):
    slug = leginfo_act_slug(*triple)
    assert parse_leginfo_act_slug(slug).normalized() == LegInfoVersion(*triple).normalized()
    assert citation_segment(slug) == slug
    assert VARIANT_SEPARATOR not in slug and "/" not in slug
    path = f"us-ca/statute/wic/{variant_segment('11450', slug)}"
    assert CITATION_PATH_PATTERN.fullmatch(path)


@given(_TRIPLES, _TRIPLES)
def test_act_slugs_are_injective_over_leginfo_triples(first, second):
    same_triple = LegInfoVersion(*first).normalized() == LegInfoVersion(*second).normalized()
    assert (leginfo_act_slug(*first) == leginfo_act_slug(*second)) == same_triple


@given(st.text(max_size=400), _TRIPLES)
def test_variant_slugs_are_deterministic_valid_selectors_for_any_note(note, triple):
    version = LegInfoVersion(*triple)
    try:
        slug = leginfo_variant_slug(note, version)
    except ValueError as exc:
        assert "impossible" in str(exc)
        return
    assert slug == leginfo_variant_slug(note, version)
    assert validate_leginfo_selector(slug) == slug
    assert citation_segment(slug) == slug
    assert CITATION_PATH_PATTERN.fullmatch(f"us-ca/statute/wic/{variant_segment('11450', slug)}")


@given(_DATES, _DATES, _TRIPLES)
def test_a_start_date_outranks_an_end_date_that_can_be_added_later(start, end, triple):
    """A version keeps its start date when a later act gives it an end date or moves
    that end date, so the operative clause decides the slug whenever there is one."""
    version = LegInfoVersion(*triple)
    later = f"(Conditionally operative on or after {_long(start)}, by its own provisions.)"
    with_end = (
        f"(Amended by Stats. 2028. Conditionally operative on or after {_long(start)}. "
        f"Conditionally inoperative on or after {_long(end)}, by its own provisions.)"
    )
    assert leginfo_variant_slug(later, version) == f"operative-{start.isoformat()}"
    assert leginfo_variant_slug(with_end, version) == f"operative-{start.isoformat()}"
    assert leginfo_note_clauses(with_end)["inoperative"] == {
        "date": end.isoformat(),
        "conditional": True,
    }


@given(_DATES, _DATES, _TRIPLES)
def test_an_end_date_names_a_version_with_no_start_date(end, repeal, triple):
    version = LegInfoVersion(*triple)
    note = (
        f"(Amended by Stats. 2019. Inoperative on {_long(end)}. Repealed as of "
        f"{_long(repeal)}, by its own provisions.)"
    )
    assert leginfo_variant_slug(note, version) == f"inoperative-{end.isoformat()}"


@given(_DATES, _TRIPLES, st.sampled_from(["on or after ", "on ", "as of ", ""]))
def test_operative_and_repealed_clauses_carry_their_own_date(when, triple, joiner):
    version = LegInfoVersion(*triple)
    operative = f"(Conditionally operative {joiner}{_long(when)}, by its own provisions.)"
    repealed = f"(Added by Stats. 1999. Repealed {joiner}{_long(when)}, by its own provisions.)"
    assert leginfo_variant_slug(operative, version) == f"operative-{when.isoformat()}"
    assert leginfo_variant_slug(repealed, version) == f"repealed-{when.isoformat()}"
    assert leginfo_variant_slug(f"(Effective {_long(when)}.)", version) == version.act_slug
