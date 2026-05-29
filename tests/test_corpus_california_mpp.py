"""Adapter shape tests for the CDSS MPP CalFresh extractor."""

import zipfile
from io import BytesIO

import pytest

from axiom_corpus.corpus.california_mpp import _subsection_provision
from axiom_corpus.parsers.us_ca.regulations import (
    MppParagraph,
    MppSubsection,
    extract_paragraphs,
    parse_mpp_sections,
)


def _docx_bytes(document_xml: str) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _make_subsection(num: str, title: str, body: str) -> MppSubsection:
    return MppSubsection(num=num, title=title, body=body, parent_num="63-503")


def _provision(sub: MppSubsection):
    return _subsection_provision(
        sub,
        parent_citation_path="us-ca/regulation/mpp/63-503",
        ordinal=1,
        run_id="2026-05-12-cdss-mpp-calfresh",
        source_as_of="2026-05-12",
        expression_date="2026-05-12",
        source_url="https://example/fsman06.docx",
        source_path="data/corpus/sources/.../fsman06.docx",
        source_id="fsman06.docx",
    )


def test_subsection_with_separate_body_preserves_body_unchanged():
    """When the DOCX subsection has a header line + follow-on paragraphs, the
    parser populates both fields. The adapter must preserve body verbatim
    (no title duplication) so multi-paragraph subsections stay clean."""
    sub = _make_subsection(
        num="131",
        title="Using a calendar or fiscal month, households shall receive benefits prorated.",
        body="(a) Refer to Handbook Section 63-1101 for Reciprocal Table.",
    )
    prov = _provision(sub)
    assert prov.body == "(a) Refer to Handbook Section 63-1101 for Reciprocal Table."
    assert prov.heading.startswith(".131 Using a calendar or fiscal month")


def test_subsection_with_empty_body_falls_back_to_title():
    """Single-paragraph subsections (most of MPP §63) have the entire rule
    text captured as title with body empty. The encoder pipeline reads
    `body` to ground citation excerpts, so the adapter must surface the
    rule text in `body` rather than leaving it null."""
    sub = _make_subsection(
        num="132",
        title=(
            "After determining the prorated allotment, the CWD shall round "
            "the product down to the nearest lower whole dollar. If the "
            "computation results in an allotment of less than $10, then no "
            "issuance shall be made for the whole month."
        ),
        body="",
    )
    prov = _provision(sub)
    assert prov.body is not None
    assert "less than $10" in prov.body
    # Heading still carries the section marker + title for display continuity.
    assert prov.heading.startswith(".132 After determining")


def test_subsection_with_both_fields_empty_emits_null_body():
    """Defensive: a fully empty subsection should still emit a record with
    body=None rather than an empty string."""
    sub = _make_subsection(num="999", title="", body="")
    prov = _provision(sub)
    assert prov.body is None


def test_extract_paragraphs_reads_docx_text_tabs_and_breaks():
    document_xml = """
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p>
          <w:r><w:t>One</w:t></w:r>
          <w:r><w:tab/></w:r>
          <w:r><w:t>Two</w:t></w:r>
          <w:r><w:br/></w:r>
          <w:r><w:t>Three</w:t></w:r>
        </w:p>
        <w:p><w:r><w:t>   </w:t></w:r></w:p>
      </w:body>
    </w:document>
    """

    paragraphs = extract_paragraphs(_docx_bytes(document_xml))

    assert paragraphs == (MppParagraph(text="One Two Three", index=1),)


def test_extract_paragraphs_rejects_docx_without_text():
    document_xml = """
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p /></w:body>
    </w:document>
    """

    with pytest.raises(ValueError, match="no text paragraphs"):
        extract_paragraphs(_docx_bytes(document_xml))


def test_parse_mpp_sections_skips_toc_noise_and_repeated_headers():
    paragraphs = (
        MppParagraph("Table of contents", 1),
        MppParagraph("63-299 TABLE OF CONTENTS", 2),
        MppParagraph("63-300 APPLICATION PROCESS 63-300", 3),
        MppParagraph("CALIFORNIA-DSS-MANUAL-FS", 4),
        MppParagraph("63-300 APPLICATION PROCESS (Continued) 63-300", 5),
        MppParagraph(".1 General eligibility", 6),
        MppParagraph("First paragraph.", 7),
        MppParagraph("Second paragraph.", 8),
        MppParagraph(".2 Single line rule", 9),
        MppParagraph("63-300 APPLICATION PROCESS", 10),
        MppParagraph("63-301 ELIGIBILITY Regulations", 11),
        MppParagraph(".1 New section body", 12),
        MppParagraph("Final paragraph.", 13),
    )

    sections = parse_mpp_sections(
        paragraphs,
        source_file="fsman06.docx",
        expected_sections=("63-300", "63-301"),
    )

    assert [section.num for section in sections] == ["63-300", "63-301"]
    assert sections[0].title == "APPLICATION PROCESS"
    assert [sub.num for sub in sections[0].subsections] == ["1", "2"]
    assert sections[0].subsections[0].body == "First paragraph. Second paragraph."
    assert sections[0].subsections[1].body == ""
    assert sections[1].title == "ELIGIBILITY"
    assert sections[1].subsections[0].body == "Final paragraph."


def test_parse_mpp_sections_falls_back_to_first_paragraph_without_body_marker():
    paragraphs = (
        MppParagraph("Preface", 1),
        MppParagraph("63-300 Application Process", 2),
    )

    sections = parse_mpp_sections(paragraphs, source_file="fsman06.docx")

    assert len(sections) == 1
    assert sections[0].num == "63-300"
    assert sections[0].title == "Application Process"
