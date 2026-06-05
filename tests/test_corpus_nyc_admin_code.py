from __future__ import annotations

from dataclasses import dataclass

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.nyc_admin_code import (
    extract_nyc_admin_code,
    parse_nyc_admin_code_section,
)

SECTION_HTML = """
<html><body>
<div id="maincontent">
  <div class="codenav__left">Title navigation that should not be included.</div>
  <div class="codenav__section-body">
    <div>Chapter 17: City Personal Income Tax on Residents</div>
    <div>Share</div><div>Download</div>
    <div>§ 11-1701</div>
    <div>Imposition of tax.</div>
    <p>General.</p>
    <p>A tax is hereby imposed on the city taxable income of every city resident individual.</p>
    <p>Not over $12,000</p>
    <p>2.7% of the city taxable income</p>
  </div>
</div>
</body></html>
"""


@dataclass
class _FakeResponse:
    content: bytes
    url: str

    def raise_for_status(self) -> None:
        return None


class _NycAdminCodeSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.urls: list[str] = []

    def get(self, url: str, *, timeout: float = 20.0) -> _FakeResponse:
        self.urls.append(url)
        return _FakeResponse(SECTION_HTML.encode(), url)


def test_parse_nyc_admin_code_section_uses_section_body() -> None:
    parsed = parse_nyc_admin_code_section(
        SECTION_HTML,
        section_hint="11-1701",
        source_url="https://example.test/section",
    )

    assert parsed.section == "11-1701"
    assert parsed.heading == "§ 11-1701 Imposition of tax."
    assert "city taxable income" in parsed.body
    assert "Title navigation" not in parsed.body


def test_extract_nyc_admin_code_writes_source_first_records(tmp_path) -> None:
    store = CorpusArtifactStore(tmp_path / "corpus")
    session = _NycAdminCodeSession()

    report = extract_nyc_admin_code(
        store,
        version="2026-06-05",
        sections=(),
        urls=("11-1701=https://example.test/nyc/11-1701",),
        session=session,
    )

    assert report.coverage.complete
    assert report.section_count == 1
    assert report.skipped_source_count == 0
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == ["us-ny/statute/NYC/11-1701"]
    assert records[0].legal_identifier == "NYC Administrative Code § 11-1701"
    assert records[0].source_format == "nyc-admin-code-amlegal-html"
    inventory = load_source_inventory(report.inventory_path)
    assert inventory[0].citation_path == "us-ny/statute/NYC/11-1701"
    assert inventory[0].source_format == "nyc-admin-code-amlegal-html"
    assert session.urls == ["https://example.test/nyc/11-1701"]
