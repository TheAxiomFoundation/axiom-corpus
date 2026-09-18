"""Tests for the ``styled_labeled_sections`` DOCX segmentation.

Added for the CDSS MPP Eligibility and Assistance Standards (CalWORKs) DOCX
files, whose section headings are Word heading-styled paragraphs restated at
every page break with a ``(Continued)`` suffix, and whose relocation tables
quote other section numbers at the start of body lines.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.documents import (
    _extract_docx_blocks,
    extract_official_documents,
)
from axiom_corpus.corpus.io import load_provisions

_DOCUMENT_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>TABLE OF CONTENTS</w:t></w:r></w:p>
    <w:p><w:r><w:t>Income Eligibility 44-207</w:t></w:r></w:p>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>44-207 INCOME ELIGIBILITY</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>.1 Applicant cases shall pass the financial eligibility test.</w:t></w:r></w:p>
    <w:p><w:r><w:t>44-207 (Cont.) AU COMPOSITION AND NEED Regulations</w:t></w:r></w:p>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>44-207 INCOME ELIGIBILITY (Continued)</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>.2 Recipient cases shall pass the test each month.</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>44-209 GENERAL</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>82-820.4</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>44-209 IDENTIFICATION OF PERSONS 44-209</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>.1 General.</w:t></w:r></w:p>
    <w:p><w:r><w:t>MANUAL LETTER NO. EAS-14-02 Effective 7/1/14</w:t></w:r></w:p>
  </w:body>
</w:document>
"""

_EXTRACTION = {
    "segmentation": "styled_labeled_sections",
    "section_heading_pattern": r"^(?P<label>\d\d-\d\d\d)\s+(?P<heading>\S.*?)(?:\s+\d\d-\d\d\d)?$",
    "drop_line_patterns": [
        r"^\d\d-\d\d\d\s+\(Cont\.\)\s.*$",
        r"^MANUAL LETTER NO\. .*$",
    ],
}


def _docx_bytes(tmp_path: Path) -> Path:
    docx_path = tmp_path / "11EAS.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", _DOCUMENT_XML)
    return docx_path


def test_styled_labeled_sections_merge_page_break_restatements(tmp_path: Path) -> None:
    blocks = _extract_docx_blocks(_docx_bytes(tmp_path).read_bytes(), extraction=_EXTRACTION)

    assert [block.metadata["citation_suffix"] for block in blocks] == ["44-207", "44-209"]
    assert blocks[0].heading == "44-207 INCOME ELIGIBILITY"
    assert blocks[0].metadata["heading_occurrences"] == 2
    assert blocks[0].body == (
        ".1 Applicant cases shall pass the financial eligibility test.\n\n"
        ".2 Recipient cases shall pass the test each month.\n\n"
        "44-209 GENERAL | 82-820.4"
    )
    assert blocks[1].heading == "44-209 IDENTIFICATION OF PERSONS"
    assert blocks[1].body == ".1 General."


def test_styled_labeled_sections_ignore_unstyled_label_lines(tmp_path: Path) -> None:
    labeled = {**_EXTRACTION, "segmentation": "labeled_sections"}
    plain_blocks = _extract_docx_blocks(_docx_bytes(tmp_path).read_bytes(), extraction=labeled)
    # the plain labeled extractor sees the table row and the restated heading as sections
    assert [block.metadata["citation_suffix"] for block in plain_blocks] == [
        "44-207",
        "44-207",
        "44-209",
        "44-209",
    ]


def test_styled_labeled_sections_require_heading_pattern(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="section_heading_pattern"):
        _extract_docx_blocks(
            _docx_bytes(tmp_path).read_bytes(),
            extraction={"segmentation": "styled_labeled_sections"},
        )


def test_styled_labeled_sections_can_refuse_repeats(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repeated section label"):
        _extract_docx_blocks(
            _docx_bytes(tmp_path).read_bytes(),
            extraction={**_EXTRACTION, "merge_repeated_labels": False},
        )


def test_extract_official_documents_styled_labeled_docx_coverage(tmp_path: Path) -> None:
    docx_path = _docx_bytes(tmp_path)
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: us-ca-cdss-mpp-eas-11
    jurisdiction: us-ca
    document_class: regulation
    title: "CDSS MPP EAS 11"
    source_url: https://www.cdss.ca.gov/Portals/9/Regs/Man/EAS/11EAS.docx
    source_format: docx
    local_path: {json.dumps(str(docx_path))}
    citation_path: us-ca/regulation/mpp/eas/11
    extraction: {json.dumps(_EXTRACTION)}
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-09-10-tanf-state-policy-manual",
    )

    assert report.coverage.complete
    assert report.coverage.duplicate_provision_citations == ()
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-ca/regulation/mpp/eas/11",
        "us-ca/regulation/mpp/eas/11/44-207",
        "us-ca/regulation/mpp/eas/11/44-209",
    ]


def test_styled_labeled_sections_can_use_unstyled_uppercase_headings(tmp_path: Path) -> None:
    document_xml = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>44-101 INCOME DEFINITIONS</w:t></w:r></w:p>
    <w:p><w:r><w:t>.1 Earned income means wages.</w:t></w:r></w:p>
    <w:p><w:r><w:t>89-101 Federal Demonstration Projects - Introduction</w:t></w:r></w:p>
    <w:p><w:r><w:t>44-101 INCOME DEFINITIONS (Continued)</w:t></w:r></w:p>
    <w:p><w:r><w:t>.2 Unearned income means everything else.</w:t></w:r></w:p>
    <w:tbl>
      <w:tr><w:tc><w:p><w:r><w:t>44-102 AVAILABILITY OF INCOME</w:t></w:r></w:p></w:tc></w:tr>
    </w:tbl>
    <w:p><w:r><w:t>44-102 AVAILABILITY OF INCOME</w:t></w:r></w:p>
    <w:p><w:r><w:t>.1 Income is available when received.</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    docx_path = tmp_path / "10EAS.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    extraction = {
        **_EXTRACTION,
        "heading_paragraphs_only": False,
        "heading_text_pattern": r"^[A-Z0-9][A-Z0-9 ,/&()'.;:-]*$",
    }

    blocks = _extract_docx_blocks(docx_path.read_bytes(), extraction=extraction)

    assert [block.metadata["citation_suffix"] for block in blocks] == ["44-101", "44-102"]
    assert blocks[0].body == (
        ".1 Earned income means wages.\n\n"
        "89-101 Federal Demonstration Projects - Introduction\n\n"
        ".2 Unearned income means everything else.\n\n"
        "44-102 AVAILABILITY OF INCOME"
    )
    assert blocks[1].body == ".1 Income is available when received."
    # the default (heading-styled paragraphs only) finds nothing in this file
    assert _extract_docx_blocks(docx_path.read_bytes(), extraction=_EXTRACTION) == ()
