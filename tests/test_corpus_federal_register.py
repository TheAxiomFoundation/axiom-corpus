from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.federal_register import extract_federal_register
from axiom_corpus.corpus.io import load_provisions, load_source_inventory


@dataclass
class _FakeResponse:
    content: bytes
    url: str

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def raise_for_status(self) -> None:
        return None


class _FederalRegisterSession:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.params: list[list[tuple[str, str]] | None] = []

    def get(
        self,
        url: str,
        *,
        params: list[tuple[str, str]] | None = None,
        timeout: float = 30,
    ) -> _FakeResponse:
        del timeout
        self.urls.append(url)
        self.params.append(params)
        if url.endswith("/api/v1/documents.json"):
            return _FakeResponse(json.dumps(_api_payload()).encode(), url)
        if url == "https://www.federalregister.gov/documents/full_text/text/2026/05/01/2026-00001.txt":
            return _FakeResponse(
                b"""<html>
<body><pre>
\x00[Federal Register Volume 91, Number 85]
From the Federal Register Online via <a href="https://www.gpo.gov">GPO</a>

Full final rule text with agency implementation details.
</pre><script>ignored()</script></body>
</html>""",
                url,
            )
        if url == "https://www.federalregister.gov/documents/full_text/text/2026/05/01/2026-00002.txt":
            return _FakeResponse(
                b"Full proposed rule text with public comment deadline.",
                url,
            )
        raise AssertionError(f"unexpected URL: {url}")


def _api_payload() -> dict:
    return {
        "count": 2,
        "total_pages": 1,
        "results": [
            {
                "document_number": "2026-00001",
                "title": "Supplemental Nutrition Assistance Program; Final Rule",
                "type": "Rule",
                "publication_date": "2026-05-01",
                "citation": "91 FR 1000",
                "raw_text_url": "https://www.federalregister.gov/documents/full_text/text/2026/05/01/2026-00001.txt",
                "html_url": "https://www.federalregister.gov/documents/2026/05/01/2026-00001/final-rule",
                "pdf_url": "https://www.govinfo.gov/content/pkg/FR-2026-05-01/pdf/2026-00001.pdf",
                "effective_on": "2026-06-01",
                "agencies": [{"name": "Food and Nutrition Service", "slug": "food-and-nutrition-service"}],
                "cfr_references": [{"title": 7, "part": 273}],
                "regulation_id_numbers": ["0584-AE99"],
                "docket_ids": ["FNS-2026-0001"],
            },
            {
                "document_number": "2026-00002",
                "title": "Medicaid Program; Proposed Rule",
                "type": "Proposed Rule",
                "publication_date": "2026-05-01",
                "citation": "91 FR 1010",
                "raw_text_url": "https://www.federalregister.gov/documents/full_text/text/2026/05/01/2026-00002.txt",
                "html_url": "https://www.federalregister.gov/documents/2026/05/01/2026-00002/proposed-rule",
                "comments_close_on": "2026-07-01",
                "agency_names": ["Centers for Medicare & Medicaid Services"],
            },
        ],
    }


def test_extract_federal_register_writes_rulemaking_activity_records(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    session = _FederalRegisterSession()

    report = extract_federal_register(
        store,
        version="2026-05-15",
        start_date="2026-05-01",
        end_date="2026-05-01",
        document_types=("RULE", "PRORULE"),
        session=session,
    )

    assert report.coverage.complete
    assert report.document_class == "rulemaking"
    assert report.document_count == 2
    assert report.provisions_written == 4
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/rulemaking/federal-register",
        "us/rulemaking/federal-register/2026-05-01",
        "us/rulemaking/federal-register/2026-05-01/2026-00001",
        "us/rulemaking/federal-register/2026-05-01/2026-00002",
    ]
    assert records[2].kind == "final_rule"
    assert records[2].source_format == "federal-register-raw-text"
    assert records[2].legal_identifier == "91 FR 1000"
    assert records[2].identifiers == {
        "federal-register:citation": "91 FR 1000",
        "federal-register:docket-ids": "FNS-2026-0001",
        "federal-register:document-number": "2026-00001",
        "federal-register:regulation-id-numbers": "0584-AE99",
    }
    assert records[2].metadata["agency_names"] == ["Food and Nutrition Service"]
    assert records[2].metadata["cfr_references"] == [{"title": 7, "part": 273}]
    assert records[2].body is not None
    assert records[2].body.startswith("[Federal Register Volume 91")
    assert "Full final rule text" in records[2].body
    assert "<html" not in records[2].body
    assert "<a " not in records[2].body
    assert "\x00" not in records[2].body
    assert records[3].kind == "proposed_rule"
    assert records[3].metadata["comments_close_on"] == "2026-07-01"

    inventory = load_source_inventory(report.inventory_path)
    assert inventory[0].metadata["document_types"] == ["RULE", "PRORULE"]
    assert inventory[2].source_format == "federal-register-raw-text"
    assert inventory[2].sha256
    assert (store.root / "sources/us/rulemaking/2026-05-15-types-rule-prorule/federal-register/api/documents-page-1.json").exists()
    assert (store.root / "sources/us/rulemaking/2026-05-15-types-rule-prorule/federal-register/documents/2026-00001.txt").exists()

    query = parse_qs(urlparse(inventory[0].source_url).query)
    assert query["conditions[publication_date][gte]"] == ["2026-05-01"]
    assert query["conditions[publication_date][lte]"] == ["2026-05-01"]
    assert query["conditions[type][]"] == ["RULE", "PRORULE"]
    assert session.urls == [
        "https://www.federalregister.gov/api/v1/documents.json",
        "https://www.federalregister.gov/documents/full_text/text/2026/05/01/2026-00001.txt",
        "https://www.federalregister.gov/documents/full_text/text/2026/05/01/2026-00002.txt",
    ]


def test_extract_federal_register_can_skip_full_text(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    session = _FederalRegisterSession()

    report = extract_federal_register(
        store,
        version="2026-05-15",
        start_date="2026-05-01",
        limit=1,
        fetch_full_text=False,
        session=session,
    )

    records = load_provisions(report.provisions_path)
    assert report.coverage.complete
    assert report.document_count == 1
    assert records[-1].source_format == "federal-register-api-json"
    assert "Supplemental Nutrition Assistance Program" in (records[-1].body or "")
    assert session.urls == ["https://www.federalregister.gov/api/v1/documents.json"]
