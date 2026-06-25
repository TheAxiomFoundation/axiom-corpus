from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.federal_register import (
    FederalRegisterCfrSectionRef,
    extract_federal_register,
    extract_federal_register_cfr_sections,
)
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
        if (
            url
            == "https://www.federalregister.gov/documents/full_text/text/2026/05/01/2026-00001.txt"
        ):
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
        if (
            url
            == "https://www.federalregister.gov/documents/full_text/text/2026/05/01/2026-00002.txt"
        ):
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
                "agencies": [
                    {"name": "Food and Nutrition Service", "slug": "food-and-nutrition-service"}
                ],
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
    assert (
        store.root
        / "sources/us/rulemaking/2026-05-15-types-rule-prorule/federal-register/api/documents-page-1.json"
    ).exists()
    assert (
        store.root
        / "sources/us/rulemaking/2026-05-15-types-rule-prorule/federal-register/documents/2026-00001.txt"
    ).exists()

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


def test_extract_federal_register_cfr_sections_writes_regulation_slices(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    source = store.source_path(
        "us",
        "rulemaking",
        "2026-06-03-cms-2454-ifc",
        "federal-register/documents/2026-11094.txt",
    )
    store.write_text(
        source,
        """PART 431--STATE ORGANIZATION AND GENERAL ADMINISTRATION

0
2. Section 431.213 is amended by revising paragraph (d) to read as
follows:


Sec.  431.213  Exceptions from advance notice.

* * * * *
    (d) The beneficiary's whereabouts are unknown and the post office
returns agency mail directed to him indicating no forwarding address.
* * * * *

0
3. Section 431.231 is amended by adding paragraph (d) to read as
follows:


Sec.  431.231  Reinstating services.

* * * * *
    (d) Any discontinued services must be reinstated if his whereabouts
become known during the time he is eligible for services.

PART 457--ALLOTMENTS AND GRANTS TO STATES

0
18. Section 457.340 is amended by revising paragraph (d)(1) to read as
follows:


Sec.  457.340  Application for and enrollment in CHIP.

* * * * *
    (d) Timely determination of eligibility. (1) The terms in Sec.
435.912 apply equally to CHIP, except that transfer standards are pursuant to
Sec.  457.350 and application standards are pursuant to Sec.  457.348.
* * * * *


Sec.  457.344  [Removed]

0
19. Section 457.344 is removed.

0
20. Section 457.960 is added to read as follows:


Sec.  457.960   Reporting changes in eligibility and redetermining
eligibility.

    If the State requires reporting of changes in circumstances, the State
must establish procedures.

PART 600--ADMINISTRATION

0
22. Section 600.320 is amended by revising paragraph (b) to read as
follows:


Sec.  600.320   Determination of eligibility for and enrollment in a
standard health plan.

* * * * *
    (b) Timely determinations. The terms of Sec.  435.912 apply to
eligibility determinations for enrollment in a standard health plan.
* * * * *

Robert F. Kennedy, Jr.,
Secretary, Department of Health and Human Services.
[FR Doc. 2026-11094 Filed 6-1-26; 4:45 pm]
""",
    )

    report = extract_federal_register_cfr_sections(
        store,
        version="2026-06-03-cms-2454-ifc-42-cfr-conforming-amendments",
        source_text_path=source,
        sections=(
            FederalRegisterCfrSectionRef(title=42, part=431, section="213"),
            FederalRegisterCfrSectionRef(title=42, part=457, section="340"),
            FederalRegisterCfrSectionRef(title=42, part=457, section="344"),
            FederalRegisterCfrSectionRef(title=42, part=600, section="320"),
        ),
        document_number="2026-11094",
        document_citation="91 FR 33348",
        document_title="Medicaid Program; Community Engagement Requirement",
        document_type="interim_final_rule_with_comment_period",
        source_url="https://www.federalregister.gov/documents/2026/06/03/2026-11094/example",
        source_as_of="2026-06-03",
        expression_date="2026-07-31",
    )

    assert report.coverage.complete
    assert report.sections_written == 4
    assert report.provisions_written == 7
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/regulation/42/431",
        "us/regulation/42/457",
        "us/regulation/42/600",
        "us/regulation/42/431/213",
        "us/regulation/42/457/340",
        "us/regulation/42/457/344",
        "us/regulation/42/600/320",
    ]
    assert records[0].kind == "part"
    assert records[0].heading == "STATE ORGANIZATION AND GENERAL ADMINISTRATION"
    assert records[3].source_format == "federal-register-raw-text-slice"
    assert records[3].source_path.endswith("federal-register/documents/2026-11094.txt")
    assert records[3].heading == "Exceptions from advance notice"
    assert "Sec.  431.231" not in (records[3].body or "")
    assert records[4].heading == "Application for and enrollment in CHIP"
    assert "Sec.  457.350" in (records[4].body or "")
    assert "Sec.  457.344" not in (records[4].body or "")
    assert records[5].heading == "[Removed]"
    assert "Section 457.344 is removed" in (records[5].body or "")
    assert records[6].heading == (
        "Determination of eligibility for and enrollment in a standard health plan"
    )
    assert "Robert F. Kennedy" not in (records[6].body or "")

    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == [
        "us/regulation/42/431",
        "us/regulation/42/457",
        "us/regulation/42/600",
        "us/regulation/42/431/213",
        "us/regulation/42/457/340",
        "us/regulation/42/457/344",
        "us/regulation/42/600/320",
    ]
