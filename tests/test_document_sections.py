"""Tests for document body sectioning and its release-validation gate."""

from axiom_corpus.corpus.document_sections import split_document_body
from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.release_quality import (
    _IssueCollector,
    _warn_unsectioned_document,
)
from axiom_corpus.corpus.releases import ReleaseScope

FILLER = "Taxable income from line 26000 of your return. " * 10

FORM = (
    "Intro text before any section.\n"
    "Part 1 – Adjusted taxable income\n"
    f"line one\n{FILLER}\n"
    "Part 1 – Adjusted taxable income (continued)\n"
    f"line two\n{FILLER}\n"
    "Part 2 – Basic federal tax\n"
    f"line three\n{FILLER}\n"
)


def _record(body: str, citation_path: str = "ca/policy/cra/t1-2025/example", **overrides):
    fields = {
        "jurisdiction": "ca",
        "document_class": "policy",
        "citation_path": citation_path,
        "body": body,
        "kind": "document",
        "level": 1,
    }
    fields.update(overrides)
    return ProvisionRecord(**fields)


def _scope() -> ReleaseScope:
    return ReleaseScope(jurisdiction="ca", document_class="policy", version="v1")


def test_split_on_part_markers_merges_continued_runs():
    split = split_document_body(FORM)
    assert split is not None
    assert [s.slug for s in split.sections] == ["part-1", "part-2"]
    assert split.sections[0].heading == "Part 1 – Adjusted taxable income"
    assert "(continued)" in split.sections[0].body
    assert split.intro == "Intro text before any section.\n"


def test_split_reassembles_the_original_body_exactly():
    split = split_document_body(FORM)
    assert split.intro + "".join(s.body for s in split.sections) == FORM


def test_step_and_schedule_families_split():
    body = f"intro\nStep 1 - Income\n{FILLER}\nStep 2 - Tax\n{FILLER}\n"
    split = split_document_body(body)
    assert [s.slug for s in split.sections] == ["step-1", "step-2"]
    body = f"intro\nSchedule 1 Federal\n{FILLER}\nSchedule 2 Provincial\n{FILLER}\n"
    split = split_document_body(body)
    assert [s.slug for s in split.sections] == ["schedule-1", "schedule-2"]


def test_non_consecutive_marker_repeat_disqualifies_the_body():
    # A capture concatenating sibling forms (one Schedule 6 per province)
    # repeats Step 1..N once per form; splitting would interleave them.
    body = "Step 1 - A\nx\nStep 2 - B\ny\nStep 1 - A\nz\nStep 2 - B\nw\n"
    assert split_document_body(body) is None


def test_mostly_stub_sections_are_rejected_as_a_table_of_contents():
    # The t4127 guide lists "Step 1 … Step 6" up front; splitting on
    # those produced five tiny stubs and one 170k catch-all.
    body = (
        "Step 1 - Overview\nStep 2 - Rates\nStep 3 - Formulas\n"
        + "Step 4 - The actual content\n" + ("x" * 5000)
    )
    assert split_document_body(body) is None


def test_collision_in_one_family_falls_through_to_the_next():
    # T657 repeats Part numbers inside its per-year charts but has
    # clean top-level Steps.
    filler = "y" * 400
    body = (
        f"intro\nStep 1 - Calc\nPart 1\n{filler}\nPart 2\n{filler}\n"
        f"Step 2 - More\nPart 1\n{filler}\nPart 2\n{filler}\n"
    )
    split = split_document_body(body)
    assert split is not None
    assert [s.slug for s in split.sections] == ["step-1", "step-2"]


def test_unstructured_bodies_are_left_alone():
    assert split_document_body("just a flat worksheet with no markers") is None
    assert split_document_body("Part 1 – Only one part\nbody\n") is None
    # Table columns are not an outline.
    assert split_document_body("Column 1: You\nColumn 2: Spouse\n") is None


def test_validator_warns_on_unsectioned_document():
    record = _record(FORM)
    collector = _IssueCollector(max_issues=10)
    _warn_unsectioned_document(record, {record.citation_path: record}, _scope(), collector)
    assert collector.warning_count == 1
    assert collector.issues[0].code == "unsectioned_document_body"


def test_validator_is_silent_once_any_children_exist():
    record = _record(FORM)
    for child_segment in ("part-1", "alberta", "values"):
        child = _record(
            "Part 1 – Adjusted taxable income\nline one\n",
            citation_path=f"{record.citation_path}/{child_segment}",
            kind="section",
            level=2,
        )
        by_path = {record.citation_path: record, child.citation_path: child}
        collector = _IssueCollector(max_issues=10)
        _warn_unsectioned_document(record, by_path, _scope(), collector)
        assert collector.warning_count == 0, child_segment


def test_validator_ignores_unsplittable_and_non_document_records():
    collector = _IssueCollector(max_issues=10)
    flat = _record("no structure here")
    _warn_unsectioned_document(flat, {flat.citation_path: flat}, _scope(), collector)
    section = _record(FORM, kind="section", level=2)
    _warn_unsectioned_document(section, {section.citation_path: section}, _scope(), collector)
    assert collector.warning_count == 0
