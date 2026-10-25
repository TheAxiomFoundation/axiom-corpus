"""Regression tests for the extractor defects behind the hollow_document_root audit.

docs/ingest-runs/2026-10-13-hollow-document-root-audit.md classifies the 188
``hollow_document_root`` findings in the release content baseline. The defects fixed
here left document rows with no text although their retained sources held it:

* medicaid.gov SPA pages (CMS state-plan index pages and CHIP FCEP summaries) print each
  SPA's summary, dates and topics as bare ``<div>`` text, which the default HTML text
  nodes (headings, paragraphs, list items) skip;
* the Maryland StatuteText page prints the statute as bare text and ``<br>`` breaks;
* 106 CMR 701 and 702 configured start markers that never occur in their DOCX files, and
  the labeled-section extractors returned no sections instead of failing.

The real-source tests read the retained bytes of the merged scopes, which stay as they
are; the fixed manifests apply to successor scopes.
"""

from __future__ import annotations

import copy
import glob
import importlib.util
import io
import json
import re
import zipfile
from pathlib import Path

import fitz
import pytest
import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.documents import (
    _extract_docx_blocks,
    _extract_html_blocks,
    extract_official_documents,
)

REPO = Path(__file__).resolve().parents[1]
SOURCES = REPO / "data/corpus/sources"
STATE_PLAN_SOURCES = "us-{state}/policy/2026-09-13-{program}-state-plan/official-documents"
FCEP_SOURCES = SOURCES / "us/policy/2026-07-05-cms-chip-fcep-spa/official-documents"
MD_SOURCES = SOURCES / "us-md/statute/2026-07-03-md-tca-statutes/official-documents"
MA_SOURCES = SOURCES / "us-ma/regulation/2026-06-27-ma-tafdc-regulations/official-documents"


def _load_generator():
    path = REPO / "scripts/build_cms_state_plan_manifests.py"
    spec = importlib.util.spec_from_file_location("build_cms_state_plan_manifests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INDEX_PAGE_EXTRACTION = _load_generator().INDEX_PAGE_EXTRACTION


def _manifest_documents(path: str) -> list[dict]:
    return yaml.safe_load((REPO / path).read_text())["documents"]


def _blocks(path: Path, extraction: dict) -> tuple:
    return _extract_html_blocks(
        path.read_bytes(),
        source_url="https://example.test",
        fallback_title="T",
        extraction=extraction,
    )


def _norm(text: str) -> str:
    return " ".join(text.split())


# An abridged medicaid.gov SPA index page: one card with a bare-text summary, one with a
# paragraph-wrapped summary, and the share link the manifests drop.
SPA_INDEX_HTML = """
<html><body><main>
<form><button>Reset</button><select><option>Approval Newest</option></select></form>
<div class="usa-accordion medicaid-solr-searches-results">
  <div class="usa-accordion-wrapper">
    <h4 class="usa-accordion__heading"><button class="usa-accordion__button">
      Transmittal Number: AK-22-0001</button></h4>
    <div class="usa-accordion__content usa-prose"><div class="usa-accordion-content-wrapper">
      <div class="grid-row"><div class="grid-col-12 margin-bottom-2 margin-top-1em">Alaska</div></div>
      <div class="grid-row"><div class="grid-col-12 margin-bottom-3">
        This SPA updates performance goals and strategic objectives.</div></div>
      <div class="grid-row">
        <div class="tablet:grid-col-6 margin-bottom-2"><b>Approval Date:</b> February 22, 2022</div>
        <div class="tablet:grid-col-6 margin-bottom-2"><b>Effective Date:</b> August 1, 2021</div>
      </div>
      <div class="grid-row"><div class="tablet:grid-col grid-col-12">
        <b>Links: </b><ul><li><a href="/CHIP/Downloads/AK/AK-22-0001.pdf">Approval Package</a></li></ul>
        <a class="mailto" href="mailto:?subject=AK-22-0001">Share via email</a>
      </div></div>
    </div></div>
  </div>
  <div class="usa-accordion-wrapper">
    <h4 class="usa-accordion__heading"><button class="usa-accordion__button">
      Transmittal Number: AK-CSPA-4</button></h4>
    <div class="usa-accordion__content usa-prose"><div class="usa-accordion-content-wrapper">
      <div class="grid-row"><div class="grid-col-12 margin-bottom-2 margin-top-1em">Alaska</div></div>
      <div class="grid-row"><div class="grid-col-12 margin-bottom-3">
        <p>Twelve month continuous eligibility.</p></div></div>
      <div class="grid-row">
        <div class="tablet:grid-col-6 margin-bottom-2"><b>Approval Date:</b> May 28, 2009</div>
        <div class="tablet:grid-col-6 margin-bottom-2"><b>Effective Date:</b> April 1, 2009</div>
      </div>
    </div></div>
  </div>
</div>
</main></body></html>
"""


def test_default_text_nodes_lose_bare_spa_summaries():
    # The 2026-09-13 configuration: the bare summary, dates and transmittal numbers vanish.
    old = {
        "html_content_selector": ".medicaid-solr-searches-results",
        "html_drop_selectors": [".mailto"],
    }
    blocks = _extract_html_blocks(
        SPA_INDEX_HTML.encode(), source_url="x", fallback_title="T", extraction=old
    )
    text = " ".join(block.body for block in blocks)

    assert "performance goals" not in text
    assert "Approval Date" not in text
    assert "Twelve month continuous eligibility." in text


def test_index_page_extraction_makes_one_block_per_spa():
    blocks = _extract_html_blocks(
        SPA_INDEX_HTML.encode(),
        source_url="x",
        fallback_title="T",
        extraction=copy.deepcopy(INDEX_PAGE_EXTRACTION),
    )

    assert [block.heading for block in blocks] == [
        "Transmittal Number: AK-22-0001",
        "Transmittal Number: AK-CSPA-4",
    ]
    first, second = (_norm(block.body) for block in blocks)
    assert first.startswith("Alaska This SPA updates performance goals and strategic objectives.")
    assert "Approval Date: February 22, 2022" in first
    assert "Effective Date: August 1, 2021" in first
    assert "Links: Approval Package" in first
    assert "Share via email" not in first
    assert "Reset" not in first and "Approval Newest" not in first
    assert second.count("Twelve month continuous eligibility.") == 1
    assert "Approval Date: May 28, 2009" in second


def test_every_cms_state_plan_index_page_uses_the_index_extraction():
    paths = sorted(
        glob.glob(str(REPO / "manifests/us-*-medicaid-state-plan.yaml"))
        + glob.glob(str(REPO / "manifests/us-*-chip-state-plan.yaml"))
    )
    assert len(paths) == 102
    index_pages = [
        document
        for path in paths
        for document in yaml.safe_load(Path(path).read_text())["documents"]
        if document["metadata"].get("document_subtype") == "cms_spa_index_page"
    ]
    assert len(index_pages) == 240
    assert all(document["extraction"] == INDEX_PAGE_EXTRACTION for document in index_pages)


@pytest.mark.parametrize(
    ("state", "program", "page"),
    [("ak", "chip", 1), ("ct", "medicaid", 6), ("il", "medicaid", 2), ("ny", "medicaid", 5)],
)
def test_retained_index_pages_keep_every_spa_summary(state, program, page):
    # Four of the 18 index pages the baseline flags as hollow roots.
    directory = SOURCES / STATE_PLAN_SOURCES.format(state=state, program=program)
    source = directory / f"us-{state}-cms-{program}-state-plan-spa-index-p{page:02d}.html"
    raw = source.read_bytes()
    soup_cards = re.findall(rb'class="usa-accordion__content usa-prose"', raw)

    blocks = _extract_html_blocks(
        raw, source_url="x", fallback_title="T", extraction=copy.deepcopy(INDEX_PAGE_EXTRACTION)
    )

    assert len(blocks) == len(soup_cards)
    assert all(block.heading.startswith("Transmittal Number: ") for block in blocks)
    assert all("Approval Date:" in block.body for block in blocks)


def test_fcep_summaries_keep_their_summary_and_dates():
    summaries = [
        document
        for document in _manifest_documents(
            "manifests/us-cms-chip-fcep-spa-official-documents.yaml"
        )
        if document["metadata"]["document_subtype"] == "chip_state_plan_amendment_summary"
    ]
    assert len(summaries) == 36
    for document in summaries:
        blocks = _blocks(FCEP_SOURCES / f"{document['source_id']}.html", document["extraction"])
        assert len(blocks) == 1, document["source_id"]
        body = _norm(blocks[0].body)
        assert body.startswith(document["metadata"]["state"]), document["source_id"]
        assert "Approval Date:" in body and "Effective Date:" in body, document["source_id"]
        # More than the state, dates and links: the summary itself.
        assert len(body.split()) > 15, document["source_id"]


def test_fcep_all_babies_summary_is_extracted():
    document = next(
        document
        for document in _manifest_documents(
            "manifests/us-cms-chip-fcep-spa-official-documents.yaml"
        )
        if document["source_id"] == "cms-chip-spa-al-al-23-0026-rim2-147101-summary"
    )

    body = _norm(
        _blocks(FCEP_SOURCES / f"{document['source_id']}.html", document["extraction"])[0].body
    )

    assert "Alabama expands its ALL Babies coverage to an additional 33 counties" in body
    assert "Approval Date: April 20, 2023" in body
    assert "Effective Date: May 1, 2023" in body


@pytest.mark.parametrize(
    ("source_id", "opening"),
    [
        (
            "md-human-services-5-312-temporary-cash-assistance-current",
            "§5–312. (a) This section is not intended to create an incentive",
        ),
        (
            "md-human-services-5-316-fip-funding-current",
            "§5–316. (a) (1) Except as provided in paragraph (2) of this subsection",
        ),
    ],
)
def test_maryland_statute_text_is_extracted(source_id, opening):
    document = next(
        document
        for document in _manifest_documents("manifests/us-md-tca-statutes-official-documents.yaml")
        if document["source_id"] == source_id
    )

    blocks = _blocks(MD_SOURCES / f"{source_id}.html", document["extraction"])

    assert len(blocks) == 1
    body = _norm(blocks[0].body)
    assert opening in body
    assert "Sign In" not in body
    assert "Find My Representatives" not in body
    # html_br_breaks keeps each <br><br>-separated subsection a paragraph of its own.
    paragraphs = blocks[0].body.split("\n\n")
    assert paragraphs[:2] == ["Article - Human Services", opening.split(" ")[0]]
    assert paragraphs[2].startswith("(a)")
    assert sum(paragraph.startswith("(b)") for paragraph in paragraphs) == 1


@pytest.mark.parametrize(("chapter", "sections"), [("701", 31), ("702", 42)])
def test_ma_tafdc_chapters_701_and_702_extract_their_sections(chapter, sections):
    document = next(
        document
        for document in _manifest_documents("manifests/us-ma-tafdc-regulations.yaml")
        if document["citation_path"].endswith(f"/106-cmr/{chapter}")
    )

    blocks = _extract_docx_blocks(
        (MA_SOURCES / f"ma-dta-106-cmr-{chapter}.docx").read_bytes(),
        extraction=document["extraction"],
    )

    assert len(blocks) == sections
    labels = [block.metadata["section_label"] for block in blocks]
    assert labels == sorted(labels)
    assert labels[0] == ("701.050" if chapter == "701" else "702.000")
    assert all(block.body for block in blocks if "Reserved" not in block.heading)


def _docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


LABELED = {
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^(?P<label>701\.\d{3}):?\s+(?P<heading>.+)$",
}


def test_labeled_docx_starts_after_its_marker():
    content = _docx(["701.050 Overview", "Page | 701.050", "701.050: Overview", "Body text."])

    blocks = _extract_docx_blocks(
        content, extraction={**LABELED, "start_after_pattern": r"Page\s+\|\s+701\.050$"}
    )

    assert [(block.metadata["section_label"], block.body) for block in blocks] == [
        ("701.050", "Body text.")
    ]


def test_labeled_docx_fails_when_its_start_marker_never_appears():
    content = _docx(["701.050 Overview", "Page | 701.050", "701.050: Overview", "Body text."])

    with pytest.raises(ValueError, match="start_after_pattern did not match"):
        _extract_docx_blocks(
            content, extraction={**LABELED, "start_after_pattern": r"Page\s+\|\s+701\.000$"}
        )


def test_styled_labeled_docx_fails_when_its_start_marker_never_appears():
    content = _docx(["44-207 INCOME ELIGIBILITY", "Body text."])

    with pytest.raises(ValueError, match="start_after_pattern did not match"):
        _extract_docx_blocks(
            content,
            extraction={
                "segmentation": "styled_labeled_sections",
                "section_heading_pattern": r"^(?P<label>44-\d{3})\s+(?P<heading>.+)$",
                "start_after_pattern": r"^BEGIN REGULATIONS$",
            },
        )


def _pdf(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "rules.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "\n".join(lines))
    document.save(path)
    document.close()
    return path


def _extract_pdf(tmp_path: Path, pdf: Path, extraction: str) -> None:
    manifest = tmp_path / "documents.yaml"
    manifest.write_text(
        f"""
documents:
  - source_id: rules
    jurisdiction: us-test
    document_class: regulation
    title: Rules
    source_url: https://example.test/rules.pdf
    citation_path: us-test/regulation/rules
    source_format: pdf
    local_path: {json.dumps(str(pdf))}
    extraction:
{extraction}
"""
    )
    extract_official_documents(
        CorpusArtifactStore(tmp_path / "corpus"), manifest_path=manifest, version="2026-10-13-rules"
    )


def test_labeled_pdf_fails_when_its_start_marker_never_appears(tmp_path):
    pdf = _pdf(tmp_path, ["TABLE OF CONTENTS", "49-001 First Section", "Body text."])

    with pytest.raises(ValueError, match="start_after_pattern did not match"):
        _extract_pdf(
            tmp_path,
            pdf,
            "      segmentation: labeled_sections\n"
            "      start_after_pattern: '^BEGIN RULE TEXT$'\n"
            "      section_heading_pattern: '^(?P<label>49-[0-9]{3})\\s+(?P<heading>.+)$'",
        )


def test_pdf_page_window_fails_when_its_start_marker_never_appears(tmp_path):
    pdf = _pdf(tmp_path, ["TABLE OF CONTENTS", "49-001 First Section", "Body text."])

    with pytest.raises(ValueError, match="start_at_pattern did not match"):
        _extract_pdf(
            tmp_path,
            pdf,
            "      segmentation: labeled_sections\n"
            "      section_heading_pattern: '^(?P<label>49-[0-9]{3})\\s+(?P<heading>.+)$'\n"
            "      page_windows:\n"
            "        - start_page: 1\n"
            "          end_page: 1\n"
            "          start_at_pattern: '^49-999 '",
        )


BR_PAGE = """<html><body><main><div id="StatuteText">
<div><span>Article - Human Services</span></div><br><br>
&sect;5&ndash;312.<br><br>
(a) This section is not intended
to create an incentive.<br><br>
(b) A local department<br>shall provide assistance.
</div></main></body></html>"""


def test_br_breaks_split_paragraphs_only_at_double_breaks():
    extraction = {"html_text_selector": "#StatuteText", "html_br_breaks": True}

    blocks = _extract_html_blocks(
        BR_PAGE.encode(), source_url="x", fallback_title="T", extraction=extraction
    )

    assert blocks[0].body.split("\n\n") == [
        "Article - Human Services",
        "§5–312.",
        # The source's own line break inside (a) does not split the paragraph.
        "(a) This section is not intended to create an incentive.",
        # A single <br> joins its lines.
        "(b) A local department shall provide assistance.",
    ]


def test_br_breaks_ignore_crlf_source_line_breaks():
    page = BR_PAGE.replace("\n", "\r\n").replace("intended\r\nto", "intended\r\n\r\nto")
    extraction = {"html_text_selector": "#StatuteText", "html_br_breaks": True}

    blocks = _extract_html_blocks(
        page.encode(), source_url="x", fallback_title="T", extraction=extraction
    )

    assert "(a) This section is not intended to create an incentive." in blocks[0].body.split(
        "\n\n"
    )


def test_without_br_breaks_the_statute_is_one_paragraph():
    blocks = _extract_html_blocks(
        BR_PAGE.encode(),
        source_url="x",
        fallback_title="T",
        extraction={"html_text_selector": "#StatuteText"},
    )

    assert "\n\n" not in blocks[0].body


def test_pdf_start_page_beyond_the_document_names_its_page_count(tmp_path):
    pdf = _pdf(tmp_path, ["49-001 First Section", "Body text."])

    with pytest.raises(ValueError, match="start_page 5 is beyond its 1 pages"):
        _extract_pdf(
            tmp_path,
            pdf,
            "      segmentation: labeled_sections\n"
            "      start_page: 5\n"
            "      start_after_pattern: '^BEGIN$'\n"
            "      section_heading_pattern: '^(?P<label>49-[0-9]{3})\\s+(?P<heading>.+)$'",
        )
