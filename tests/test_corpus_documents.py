import json
import zipfile
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import requests

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.documents import (
    OFFICIAL_DOCUMENT_BROWSER_USER_AGENT,
    OFFICIAL_DOCUMENT_USER_AGENT,
    OfficialDocumentSource,
    _download_document,
    _normalize_text,
    extract_official_documents,
    google_drive_download_url,
)
from axiom_corpus.corpus.io import load_provisions


def test_google_drive_download_url_converts_file_view():
    url = "https://drive.google.com/file/d/abc123XYZ/view?usp=drive_link"

    assert (
        google_drive_download_url(url) == "https://drive.google.com/uc?export=download&id=abc123XYZ"
    )


def test_normalize_text_removes_invisible_markers():
    assert _normalize_text("\ufeff\u200b Requirements\n\nA rule applies.") == (
        "Requirements\n\nA rule applies."
    )


def test_download_document_retries_browser_user_agent_on_forbidden():
    class FakeResponse:
        def __init__(self, status_code: int, content: bytes = b""):
            self.status_code = status_code
            self.content = content
            self.headers = {"content-type": "application/pdf"}
            self.url = "https://example.test/doc.pdf"

        def close(self):
            return None

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError("final response should not be an error")

    class FakeSession:
        def __init__(self):
            self.headers = {"User-Agent": OFFICIAL_DOCUMENT_USER_AGENT}
            self.calls: list[dict[str, str]] = []

        def get(self, url, *, headers=None, timeout=None, allow_redirects=None, verify=None):
            del url, timeout, allow_redirects, verify
            self.calls.append(dict(headers or self.headers))
            if len(self.calls) == 1:
                return FakeResponse(403)
            return FakeResponse(200, b"%PDF-1.7")

    source = OfficialDocumentSource(
        source_id="doc",
        jurisdiction="us-test",
        document_class="form",
        title="Document",
        source_url="https://example.test/doc.pdf",
    )
    session = FakeSession()

    downloaded = _download_document(source, session=session)  # pyright: ignore[reportPrivateUsage]

    assert downloaded.content == b"%PDF-1.7"
    assert session.calls[0]["User-Agent"] == OFFICIAL_DOCUMENT_USER_AGENT
    assert session.calls[1]["User-Agent"] == OFFICIAL_DOCUMENT_BROWSER_USER_AGENT


def test_download_document_retries_transient_request_errors(monkeypatch):
    class FakeResponse:
        status_code = 200
        content = b"<html><body>ok</body></html>"
        headers = {"content-type": "text/html"}
        url = "https://example.test/doc.html"

        def close(self):
            return None

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.headers = {"User-Agent": OFFICIAL_DOCUMENT_USER_AGENT}
            self.calls = 0

        def get(self, url, *, headers=None, timeout=None, allow_redirects=None, verify=None):
            del url, headers, timeout, allow_redirects, verify
            self.calls += 1
            if self.calls == 1:
                raise requests.exceptions.ChunkedEncodingError("connection reset")
            return FakeResponse()

    monkeypatch.setattr(documents_module.time, "sleep", lambda seconds: None)
    source = OfficialDocumentSource(
        source_id="doc",
        jurisdiction="us-test",
        document_class="manual",
        title="Document",
        source_url="https://example.test/doc.html",
    )
    session = FakeSession()

    downloaded = _download_document(source, session=session)  # pyright: ignore[reportPrivateUsage]

    assert downloaded.content == b"<html><body>ok</body></html>"
    assert session.calls == 2


def test_download_document_can_disable_tls_verification():
    class FakeResponse:
        status_code = 200
        content = b'{"ok": true}'
        headers = {"content-type": "application/json"}
        url = "https://example.test/doc.json"

        def close(self):
            return None

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.headers = {"User-Agent": OFFICIAL_DOCUMENT_USER_AGENT}
            self.verify_values: list[bool | None] = []

        def get(self, url, *, headers=None, timeout=None, allow_redirects=None, verify=None):
            del url, headers, timeout, allow_redirects
            self.verify_values.append(verify)
            return FakeResponse()

    source = OfficialDocumentSource(
        source_id="doc",
        jurisdiction="us-test",
        document_class="regulation",
        title="Document",
        source_url="https://example.test/doc.json",
        request={"verify_tls": False},
    )
    session = FakeSession()

    downloaded = _download_document(source, session=session)  # pyright: ignore[reportPrivateUsage]

    assert downloaded.content == b'{"ok": true}'
    assert session.verify_values == [False]


def test_extract_official_documents_from_local_html_and_pdf(tmp_path):
    html_path = tmp_path / "snap.html"
    long_html_text = "Long eligibility detail. " * 180
    html_path.write_text(
        f"""
        <html>
          <head><title>Ignored browser title</title></head>
          <body>
            <nav>Navigation should not become its own block.</nav>
            <main>
              <h1>Colorado SNAP Policy</h1>
              <h2>Eligibility</h2>
              <p>Households may qualify based on income and household size.</p>
              <p>{long_html_text}</p>
              <ul><li>County departments determine eligibility.</li></ul>
            </main>
          </body>
        </html>
        """
    )
    pdf_path = tmp_path / "waiver.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "SNAP waiver approval\nApproved for a limited area.")
    document.save(pdf_path)
    document.close()
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: co-snap-page
    jurisdiction: us-co
    document_class: policy
    title: Colorado SNAP Policy
    source_url: https://cdhs.colorado.gov/snap
    citation_path: us-co/policy/cdhs/snap
    source_format: html
    local_path: {json.dumps(str(html_path))}
    metadata:
      source_authority: Colorado Department of Human Services
      document_subtype: agency_page
  - source_id: co-snap-waiver
    jurisdiction: us-co
    document_class: policy
    title: Colorado SNAP Waiver Approval
    source_url: https://www.fns.usda.gov/example.pdf
    source_format: pdf
    local_path: {json.dumps(str(pdf_path))}
    metadata:
      source_authority: USDA Food and Nutrition Service
      document_subtype: waiver_approval
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-04-30",
        source_as_of="2026-04-30",
    )

    assert report.document_count == 2
    assert report.block_count == 2
    assert report.provisions_written == 4
    assert report.coverage.complete
    assert report.inventory_path.exists()
    assert len(report.source_paths) == 2

    inventory = json.loads(report.inventory_path.read_text())
    assert [item["citation_path"] for item in inventory["items"]] == [
        "us-co/policy/cdhs/snap",
        "us-co/policy/cdhs/snap/block-1",
        "us-co/policy/co-snap-waiver",
        "us-co/policy/co-snap-waiver/page-1",
    ]
    records = load_provisions(report.provisions_path)
    page_record = next(record for record in records if record.kind == "page")
    assert page_record.body is not None
    assert "Approved for a limited area" in page_record.body
    assert page_record.source_id == "co-snap-waiver"
    assert page_record.source_document_id is None
    assert page_record.metadata is not None
    assert page_record.metadata["document_subtype"] == "waiver_approval"


def test_extract_official_documents_uses_html_content_selector(tmp_path: Path) -> None:
    html_path = tmp_path / "wa-eaz.html"
    html_path.write_text(
        """
        <html>
          <head><title>Browser title</title></head>
          <body>
            <h1>Basic Food - Work Requirements</h1>
            <div class="site-shell">Navigation text should be ignored.</div>
            <div class="field-name-body">
              <p>Revised June 1, 2026</p>
              <h2>Purpose</h2>
              <p>Basic Food applicants must meet work registration rules.</p>
            </div>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: wa-eaz-work-requirements
    jurisdiction: us-wa
    document_class: manual
    title: Basic Food - Work Requirements
    source_url: https://www.dshs.wa.gov/esa/example
    source_format: html
    local_path: {json.dumps(str(html_path))}
    extraction:
      html_content_selector: .field-name-body
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-27-wa-eaz-manual",
    )

    assert report.block_count == 2
    records = load_provisions(report.provisions_path)
    bodies = "\n".join(record.body or "" for record in records)
    assert "Basic Food applicants must meet work registration rules" in bodies
    assert "Navigation text should be ignored" not in bodies


def test_extract_official_documents_splits_labeled_html_sections(tmp_path: Path) -> None:
    html_path = tmp_path / "nm-nmac.html"
    html_path.write_text(
        """
        <html>
          <head><title>8.139.520 NMAC</title></head>
          <body>
            <div class="WordSection1">
              <p>TITLE 8 SOCIAL SERVICES</p>
              <p>8.139.520.1 ISSUING AGENCY: New Mexico Health Care Authority.</p>
              <p>[8.139.520.1 NMAC - Rp, 11/21/2023]</p>
              <p>8.139.520.2 SCOPE: General public.</p>
              <p>[8.139.520.2 NMAC - Rp, 11/21/2023]</p>
            </div>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: nm-nmac-8-139-520
    jurisdiction: us-nm
    document_class: regulation
    title: 8.139.520 NMAC Eligibility Policy - Income and Deductions
    source_url: https://www.srca.nm.gov/parts/title08/08.139.0520.html
    source_format: html
    local_path: {json.dumps(str(html_path))}
    citation_path: us-nm/regulation/nmac/8/139/520
    extraction:
      html_content_selector: .WordSection1
      segmentation: labeled_sections
      section_heading_pattern: '^(?P<label>8\\.139\\.520\\.\\d+)\\s+(?P<heading>[A-Z][A-Z ]+:)(?:\\s+(?P<body>.*))?$'
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-27-nm-snap-regulations",
    )

    assert report.block_count == 2
    records = load_provisions(report.provisions_path)
    assert [
        record.citation_path for record in records if record.kind == "section"
    ] == [
        "us-nm/regulation/nmac/8/139/520/8.139.520.1",
        "us-nm/regulation/nmac/8/139/520/8.139.520.2",
    ]
    section_body = next(
        record.body for record in records if record.citation_path.endswith("8.139.520.1")
    )
    assert section_body == (
        "New Mexico Health Care Authority.\n\n"
        "[8.139.520.1 NMAC - Rp, 11/21/2023]"
    )


def test_extract_official_documents_formats_labeled_html_section_labels(
    tmp_path: Path,
) -> None:
    html_path = tmp_path / "nh-he-w-700.html"
    html_path.write_text(
        """
        <html>
          <body>
            <div class="WordSection1">
              <p>He-W 701 .02 Definitions F - O .</p>
              <p>(a) "Fraud" means an intentional program violation.</p>
              <p>He-W 702.03 Telephone Application .</p>
              <p>(a) Applicants may request assistance by telephone.</p>
              <p>APPENDIX A</p>
              <p>He-W 701.02 RSA 161:4-a, IV</p>
            </div>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: nh-he-w-700
    jurisdiction: us-nh
    document_class: regulation
    title: New Hampshire He-W 700 SNAP Rules
    source_url: https://gc.nh.gov/rules/state_agencies/he-w700.html
    source_format: html
    local_path: {json.dumps(str(html_path))}
    citation_path: us-nh/regulation/he-w-700
    extraction:
      html_content_selector: .WordSection1
      segmentation: labeled_sections
      section_heading_pattern: '^(?P<prefix>He-W)\\s+(?P<part>\\d+)\\s*\\.\\s*(?P<section>\\d+)\\s*(?P<heading>.+?)\\.?$'
      section_label_template: '{{prefix}} {{part}}.{{section}}'
      stop_text_pattern: '^APPENDIX A$'
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-27-nh-he-w-700-snap-rules",
    )

    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records if record.kind == "section"] == [
        "us-nh/regulation/he-w-700/He-W 701.02",
        "us-nh/regulation/he-w-700/He-W 702.03",
    ]
    assert records[-1].body == "(a) Applicants may request assistance by telephone."


def test_extract_official_documents_keeps_content_inside_aspnet_form(
    tmp_path: Path,
) -> None:
    html_path = tmp_path / "il-dhs.html"
    html_path.write_text(
        """
        <html>
          <body>
            <form id="aspnetForm">
              <input type="hidden" name="__VIEWSTATE" value="ignored" />
              <div id="Main2">
                <h1>PM 13: SNAP Eligibility and Benefit Amount</h1>
                <p>SNAP eligibility rules are published in the manual body.</p>
              </div>
            </form>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: il-dhs-pm13
    jurisdiction: us-il
    document_class: manual
    title: "PM 13: SNAP Eligibility and Benefit Amount"
    source_url: https://www.dhs.state.il.us/page.aspx?item=16111
    source_format: html
    local_path: {json.dumps(str(html_path))}
    extraction:
      html_content_selector: "#Main2"
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-27-il-snap-manual",
    )

    assert report.block_count == 1
    records = load_provisions(report.provisions_path)
    bodies = "\n".join(record.body or "" for record in records)
    assert "SNAP eligibility rules are published in the manual body" in bodies
    assert "__VIEWSTATE" not in bodies


def test_extract_official_documents_from_json_html_field(tmp_path: Path) -> None:
    json_path = tmp_path / "ne-title-475-chapter-1.json"
    json_path.write_text(
        json.dumps(
            {
                "isSuccess": True,
                "output": {
                    "chapterHtml": (
                        "<p><strong>TITLE 475</strong></p>"
                        "<p><strong>CHAPTER 1 GENERAL PROVISIONS</strong></p>"
                        "<p>SNAP is a federal low income nutrition program.</p>"
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: ne-title-475-chapter-1
    jurisdiction: us-ne
    document_class: regulation
    title: "Nebraska Title 475 NAC Chapter 1: General Provisions"
    source_url: https://rules.nebraska.gov/api/chapter/1741
    source_format: json
    local_path: {json.dumps(str(json_path))}
    extraction:
      json_html_field: output.chapterHtml
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-27-ne-snap-rules",
    )

    assert report.block_count == 1
    records = load_provisions(report.provisions_path)
    assert records[1].source_format == "json"
    assert "SNAP is a federal low income nutrition program" in (records[1].body or "")


def test_extract_official_documents_from_json_records(tmp_path: Path) -> None:
    json_path = tmp_path / "ok-oac-340-50.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "id": 1,
                    "sectionNum": "340:50-1-1",
                    "description": "Purpose, legal base, and responsibilities",
                    "name": "Section",
                    "statusName": "Undefined",
                    "text": (
                        "<div>(a) <b>Purpose.</b> SNAP policy text.</div>"
                        "<div>(b) Other text.</div>"
                    ),
                },
                {
                    "id": 2,
                    "sectionNum": "340:50-1-2",
                    "description": "Legal basis",
                    "name": "Section",
                    "statusName": "Revoked",
                    "text": "<div>Old revoked text.</div>",
                },
                {
                    "id": 3,
                    "sectionNum": None,
                    "description": "General Provisions",
                    "name": "Subchapter",
                    "statusName": "Undefined",
                    "text": None,
                },
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: ok-oac-340-50-snap
    jurisdiction: us-ok
    document_class: regulation
    title: "Oklahoma OAC 340:50 Supplemental Nutrition Assistance Program"
    source_url: https://rules.ok.gov/home
    source_format: json
    local_path: {json.dumps(str(json_path))}
    citation_path: us-ok/regulation/oac/340/50
    extraction:
      segmentation: records
      json_record_text_field: text
      json_record_text_is_html: true
      json_record_label_field: sectionNum
      json_record_heading_field: description
      json_record_kind_field: name
      json_record_status_field: statusName
      json_record_exclude_statuses:
        - Revoked
      json_record_metadata_fields:
        - id
        - sectionNum
        - statusName
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-27-ok-snap-rules",
    )

    assert report.block_count == 1
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-ok/regulation/oac/340/50",
        "us-ok/regulation/oac/340/50/340-50-1-1",
    ]
    assert records[1].heading == (
        "340:50-1-1 Purpose, legal base, and responsibilities"
    )
    assert records[1].kind == "section"
    assert records[1].metadata is not None
    assert records[1].metadata["id"] == 1
    assert "SNAP policy text" in (records[1].body or "")
    assert "Old revoked text" not in (records[1].body or "")


def test_extract_official_documents_drops_configured_html_selectors(
    tmp_path: Path,
) -> None:
    html_path = tmp_path / "ks-keesm.html"
    html_path.write_text(
        """
        <html>
          <head><title>4200 Assistance Planning</title></head>
          <body>
            <h1>Kansas Economic and Employment Services Manual</h1>
            <h2>4000 Assistance Planning</h2>
            <h6>04-26</h6>
            <p>Food assistance household composition rules apply.</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: ks-keesm-4200
    jurisdiction: us-ks
    document_class: manual
    title: "Kansas KEESM: 4200 Assistance Planning"
    source_url: https://content.dcf.ks.gov/EES/KEESM/Current/keesm4200.htm
    source_format: html
    local_path: {json.dumps(str(html_path))}
    extraction:
      html_drop_selectors:
        - h1
        - h6
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-27-ks-keesm",
    )

    assert report.block_count == 1
    records = load_provisions(report.provisions_path)
    block = records[1]
    assert block.heading == "4000 Assistance Planning"
    assert "Food assistance household composition rules apply" in (block.body or "")
    assert "04-26" not in (block.body or "")


def test_extract_official_documents_reads_docx_sections(tmp_path: Path) -> None:
    docx_path = tmp_path / "chapter-365.docx"
    document_xml = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>365.100 Special Situation Households</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>SNAP households may include special living arrangements.</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Household</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Treatment</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading2"/></w:pPr>
      <w:r><w:t>365.110 Residents of Institutions</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>Institution residents are subject to program rules.</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: ma-dta-chapter-365
    jurisdiction: us-ma
    document_class: regulation
    title: "Massachusetts DTA Chapter 365"
    source_url: https://www.mass.gov/doc/chapter-365-special-situation-households/download
    source_format: docx
    local_path: {json.dumps(str(docx_path))}
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-27-ma-dta-regulations",
    )

    assert report.block_count == 2
    records = load_provisions(report.provisions_path)
    first_block = records[1]
    assert first_block.heading == "365.100 Special Situation Households"
    assert "SNAP households may include special living arrangements" in (
        first_block.body or ""
    )
    assert "Household | Treatment" in (first_block.body or "")
    second_block = records[2]
    assert second_block.heading == "365.110 Residents of Institutions"


def test_extract_official_documents_reads_webworks_policy_divs(tmp_path: Path) -> None:
    html_path = tmp_path / "az-faa5.html"
    html_path.write_text(
        """
        <html>
          <head><title>A CA Benefit Determination</title></head>
          <body>
            <div id="ww_content_container">
              <div id="page_content_container">
                <div id="page_content">
                  <div class="Heading_Subject">CA Benefit Determination</div>
                  <div class="WebWorks_MiniTOC">
                    <a class="WebWorks_MiniTOC_Link" href="#policy">Policy</a>
                  </div>
                  <div class="Body_Text_Public">
                    This section identifies how benefit amounts are determined.
                  </div>
                  <div class="Heading_Section_Public">Policy</div>
                  <div class="Body_Text_Public">
                    Countable income is compared to the payment standard.
                  </div>
                  <div class="List_Bullet_Public">
                    <span class="WebWorks_Number">-</span> Net income is subtracted.
                  </div>
                  <div class="Heading_Section_Public">Examples</div>
                  <div class="ww_skin_page_overflow">
                    <table>
                      <tr>
                        <td><div class="Body_Text_Bullet_Public">Individual</div></td>
                        <td><div class="Body_Text_Bullet_Public">Family Member</div></td>
                      </tr>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: az-faa5-ca-benefit
    jurisdiction: us-az
    document_class: manual
    title: Arizona DES FAA5 CA Benefit Determination
    source_url: https://dbmefaapolicy.azdes.gov/FAA5/CA_Benefit_Determination.html
    source_format: html
    local_path: {json.dumps(str(html_path))}
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2025-10-30-az-des-faa5-manual",
    )

    assert report.block_count == 3
    records = load_provisions(report.provisions_path)
    policy_block = next(record for record in records if record.heading == "Policy")
    policy_body = policy_block.body or ""
    assert "Countable income is compared to the payment standard" in policy_body
    assert "Net income is subtracted" in policy_body
    assert "WebWorks_MiniTOC" not in policy_body
    examples_block = next(record for record in records if record.heading == "Examples")
    assert "Individual" in (examples_block.body or "")


def test_extract_official_documents_splits_numbered_pdf_sections(tmp_path):
    pdf_path = tmp_path / "rules.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "\n".join(
            [
                "IDAHO ADMINISTRATIVE CODE",
                "Section 000",
                "Page 1",
                "000.",
                "LEGAL AUTHORITY.",
                "Legal authority text.",
                "001.",
                "SCOPE.",
                "01.",
                "Scope body.",
                "002. -- 009.",
                "(RESERVED)",
            ]
        ),
    )
    document.save(pdf_path)
    document.close()
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: idaho-rule
    jurisdiction: us-id
    document_class: regulation
    title: IDAPA 35.01.01 - Income Tax Administrative Rules
    source_url: https://adminrules.idaho.gov/rules/current/35/350101.pdf
    citation_path: us-id/regulation/idapa/35/01/01
    source_format: pdf
    local_path: {json.dumps(str(pdf_path))}
    extraction:
      segmentation: numbered_sections
      drop_lines:
        - IDAHO ADMINISTRATIVE CODE
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-12-idapa-35-01-01",
    )

    assert report.block_count == 3
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-id/regulation/idapa/35/01/01",
        "us-id/regulation/idapa/35/01/01/000",
        "us-id/regulation/idapa/35/01/01/001",
        "us-id/regulation/idapa/35/01/01/002-009",
    ]
    first_section = records[1]
    assert first_section.kind == "section"
    assert first_section.heading == "000. LEGAL AUTHORITY."
    assert first_section.body == "Legal authority text."
    assert first_section.metadata is not None
    assert first_section.metadata["page_start"] == 1
    assert "section_end_label" not in first_section.metadata
    reserved_section = records[3]
    assert reserved_section.metadata is not None
    assert reserved_section.metadata["section_end_label"] == "009"


def test_extract_official_documents_splits_labeled_pdf_sections(tmp_path):
    pdf_path = tmp_path / "capi.pdf"
    document = fitz.open()
    first_page = document.new_page()
    first_page.insert_text(
        (72, 72),
        "\n".join(
            [
                "ELIGIBILITY AND ASSISTANCE STANDARDS",
                "49-001",
                "PROGRAM DEFINITION",
                ".1 Program definition text.",
                "CALIFORNIA-DSS-MANUAL-EAS",
                "Page 660.2",
            ]
        ),
    )
    second_page = document.new_page()
    second_page.insert_text(
        (72, 72),
        "\n".join(
            [
                "ELIGIBILITY AND ASSISTANCE STANDARDS",
                "49-001",
                "PROGRAM DEFINITION",
                ".2 Continued definition text.",
                "49-010",
                "ELIGIBILITY FOR CASH ASSISTANCE PROGRAM",
                "FOR IMMIGRANTS",
                "HANDBOOK BEGINS HERE",
                ".1 Eligibility text.",
            ]
        ),
    )
    document.save(pdf_path)
    document.close()
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: ca-capi
    jurisdiction: us-ca
    document_class: regulation
    title: California CAPI Regulations
    source_url: https://cdss.ca.gov/Portals/9/CAPI/CAPI_Regulations-Accessible.pdf
    citation_path: us-ca/regulation/cdss/eas/49
    source_format: pdf
    local_path: {json.dumps(str(pdf_path))}
    extraction:
      segmentation: labeled_sections
      section_label_pattern: "^(?P<label>49-[0-9]{{3}})$"
      drop_lines:
        - ELIGIBILITY AND ASSISTANCE STANDARDS
        - CALIFORNIA-DSS-MANUAL-EAS
      drop_line_patterns:
        - "^Page \\\\d+(?:\\\\.\\\\d+)?$"
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-12-capi",
    )

    assert report.block_count == 2
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-ca/regulation/cdss/eas/49",
        "us-ca/regulation/cdss/eas/49/49-001",
        "us-ca/regulation/cdss/eas/49/49-010",
    ]
    definition = records[1]
    assert definition.body == ".1 Program definition text. .2 Continued definition text."
    eligibility = records[2]
    assert eligibility.heading == "49-010 ELIGIBILITY FOR CASH ASSISTANCE PROGRAM FOR IMMIGRANTS"
    assert eligibility.body == "HANDBOOK BEGINS HERE .1 Eligibility text."
    assert eligibility.metadata is not None
    assert eligibility.metadata["page_start"] == 2


def test_extract_official_documents_respects_labeled_pdf_end_page(tmp_path):
    pdf_path = tmp_path / "rules.pdf"
    document = fitz.open()
    first_page = document.new_page()
    first_page.insert_text(
        (72, 72),
        "\n".join(
            [
                "49-001",
                "FIRST SECTION",
                ".1 First section text.",
            ]
        ),
    )
    second_page = document.new_page()
    second_page.insert_text(
        (72, 72),
        "\n".join(
            [
                "49-002",
                "SECOND SECTION",
                ".1 Second section text.",
            ]
        ),
    )
    document.save(pdf_path)
    document.close()
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: bounded-rule
    jurisdiction: us-az
    document_class: regulation
    title: Bounded Rules
    source_url: https://apps.azsos.gov/public_services/Title_06/6-05.pdf
    citation_path: us-az/regulation/aac/title-6/chapter-5/article-49
    source_format: pdf
    local_path: {json.dumps(str(pdf_path))}
    extraction:
      segmentation: labeled_sections
      section_label_pattern: "^(?P<label>49-[0-9]{{3}})$"
      label_only_heading_pattern: "^[A-Z ]+$"
      start_page: 1
      end_page: 1
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-12-bounded",
    )

    assert report.block_count == 1
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-az/regulation/aac/title-6/chapter-5/article-49",
        "us-az/regulation/aac/title-6/chapter-5/article-49/49-001",
    ]
    assert records[1].body == ".1 First section text."


def test_extract_labeled_pdf_sections_formats_section_labels(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "source-book.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "\n".join(
            [
                "SECTION 1 \u2013 FORWARD/NOTICE",
                "SECTION 1: Forward/Notice",
                "Forward text.",
                "SECTION 2: Eligibility",
                "Eligibility text.",
            ]
        ),
    )
    document.save(pdf_path)
    document.close()
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: ny-source-book
    jurisdiction: us-ny
    document_class: manual
    title: New York SNAP Source Book
    source_url: https://otda.ny.gov/programs/snap/SNAPSB.pdf
    citation_path: us-ny/manual/otda/snap-source-book
    source_format: pdf
    local_path: {json.dumps(str(pdf_path))}
    extraction:
      segmentation: labeled_sections
      section_heading_pattern: "^(?P<label>SECTION\\\\s+(?P<number>\\\\d+))(?::|\\\\s+[\\\\u2013-]\\\\s+)\\\\s*(?P<heading>.+)$"
      section_label_template: "section-{{number}}"
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-27-ny-source-book",
    )

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-ny/manual/otda/snap-source-book",
        "us-ny/manual/otda/snap-source-book/section-1",
        "us-ny/manual/otda/snap-source-book/section-2",
    ]
    assert records[1].metadata is not None
    assert records[1].metadata["section_label"] == "section-1"


def test_extract_labeled_pdf_sections_supports_label_heading_next_line(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "delaware.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "\n".join(
            [
                "9001",
                "Legal Base",
                "Legal base text.",
                "9002 Penalties",
                "Penalty text.",
                "9064.7 Households Entitled to a Deduction in DSSM",
                "9060",
                "[273.10(d)(7)]",
                "Continuation text.",
                "9065",
                "Calculating Net Income",
                "Net income text.",
            ]
        ),
    )
    document.save(pdf_path)
    document.close()
    manifest_path = tmp_path / "documents.yaml"
    manifest_path.write_text(
        f"""
documents:
  - source_id: de-snap-rules
    jurisdiction: us-de
    document_class: regulation
    title: Delaware SNAP Rules
    source_url: https://regulations.delaware.gov/AdminCode/title16/9000
    citation_path: us-de/regulation/title-16/9000-food-stamp-program
    source_format: pdf
    local_path: {json.dumps(str(pdf_path))}
    extraction:
      segmentation: labeled_sections
      section_heading_pattern: '^(?P<label>9\\d{{3}}(?:\\.\\d+)*)\\s+(?P<heading>[A-Z][A-Za-z0-9 ().,''/-]+)$'
      section_label_pattern: '^(?P<label>9\\d{{3}}(?:\\.\\d+)*)$'
      label_only_heading_pattern: '^[A-Z][A-Za-z0-9 ().,''/-]+$'
      label_only_requires_heading: true
"""
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_official_documents(
        store,
        manifest_path=manifest_path,
        version="2026-05-27-de-snap-rules",
    )

    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-de/regulation/title-16/9000-food-stamp-program",
        "us-de/regulation/title-16/9000-food-stamp-program/9001",
        "us-de/regulation/title-16/9000-food-stamp-program/9002",
        "us-de/regulation/title-16/9000-food-stamp-program/9064.7",
        "us-de/regulation/title-16/9000-food-stamp-program/9065",
    ]
    assert records[1].heading == "9001 Legal Base"
    assert "9060 [273.10(d)(7)] Continuation text." in (records[3].body or "")
