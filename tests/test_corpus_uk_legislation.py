import json
from datetime import date

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.uk_legislation import extract_uk_legislation_sections
from axiom_corpus.parsers.clml import parse_section

SAMPLE_UKSI_REGULATION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             DocumentURI="http://www.legislation.gov.uk/uksi/2006/965/regulation/2"
             RestrictExtent="E+W+S+N.I.">
<ukm:Metadata>
    <dc:title>The Child Benefit and Guardian's Allowance Up-rating Regulations 2006</dc:title>
    <ukm:PrimaryMetadata>
        <ukm:Year Value="2006"/>
        <ukm:Number Value="965"/>
        <ukm:EnactmentDate Date="2006-03-29"/>
    </ukm:PrimaryMetadata>
</ukm:Metadata>
<Primary>
    <Body>
        <P1 DocumentURI="http://www.legislation.gov.uk/uksi/2006/965/regulation/2" id="regulation-2">
            <Pnumber>2</Pnumber>
            <P1para>
                <P2 id="regulation-2-1">
                    <Pnumber>1</Pnumber>
                    <P2para>
                        <Text>The weekly rate of child benefit is £17.45.</Text>
                    </P2para>
                </P2>
            </P1para>
        </P1>
    </Body>
</Primary>
</Legislation>
"""


SAMPLE_UKPGA_SECTION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             DocumentURI="http://www.legislation.gov.uk/ukpga/2007/3/section/35"
             RestrictExtent="E+W+S+N.I.">
<ukm:Metadata>
    <dc:title>Income Tax Act 2007</dc:title>
    <ukm:PrimaryMetadata>
        <ukm:Year Value="2007"/>
        <ukm:Number Value="3"/>
        <ukm:EnactmentDate Date="2007-03-20"/>
    </ukm:PrimaryMetadata>
</ukm:Metadata>
<Primary>
    <Body>
        <P1 DocumentURI="http://www.legislation.gov.uk/ukpga/2007/3/section/35" id="section-35">
            <Pnumber>35</Pnumber>
            <P1para>
                <P2 id="section-35-1">
                    <Pnumber>1</Pnumber>
                    <P2para>
                        <Text>An individual is entitled to a personal allowance.</Text>
                    </P2para>
                </P2>
            </P1para>
        </P1>
    </Body>
</Primary>
</Legislation>
"""


SAMPLE_UKSI_TABLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             xmlns:xhtml="http://www.w3.org/1999/xhtml"
             DocumentURI="http://www.legislation.gov.uk/uksi/2013/376/regulation/36">
<ukm:Metadata>
    <dc:title>The Universal Credit Regulations 2013</dc:title>
    <ukm:PrimaryMetadata>
        <ukm:Year Value="2013"/>
        <ukm:Number Value="376"/>
        <ukm:EnactmentDate Date="2013-02-25"/>
    </ukm:PrimaryMetadata>
</ukm:Metadata>
<Secondary>
    <Body>
        <P1 DocumentURI="http://www.legislation.gov.uk/uksi/2013/376/regulation/36">
            <Pnumber>36</Pnumber>
            <P1para>
                <P2>
                    <Pnumber>1</Pnumber>
                    <P2para>
                        <Text>The amounts are given in the following table.</Text>
                        <Tabular>
                            <xhtml:table>
                                <xhtml:tbody>
                                    <xhtml:tr>
                                        <xhtml:td>Standard allowance</xhtml:td>
                                        <xhtml:td>£400.14</xhtml:td>
                                    </xhtml:tr>
                                    <xhtml:tr>
                                        <xhtml:td>Carer element</xhtml:td>
                                        <xhtml:td>£209.34</xhtml:td>
                                    </xhtml:tr>
                                </xhtml:tbody>
                            </xhtml:table>
                        </Tabular>
                    </P2para>
                </P2>
            </P1para>
        </P1>
    </Body>
</Secondary>
</Legislation>
"""


SAMPLE_UKSI_SINGLE_ROW_TABLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             xmlns:xhtml="http://www.w3.org/1999/xhtml"
             DocumentURI="http://www.legislation.gov.uk/uksi/2013/376/regulation/36">
<ukm:Metadata>
    <dc:title>The Universal Credit Regulations 2013</dc:title>
    <ukm:PrimaryMetadata>
        <ukm:Year Value="2013"/>
        <ukm:Number Value="376"/>
        <ukm:EnactmentDate Date="2013-02-25"/>
    </ukm:PrimaryMetadata>
</ukm:Metadata>
<Secondary>
    <Body>
        <P1 DocumentURI="http://www.legislation.gov.uk/uksi/2013/376/regulation/36">
            <Pnumber>36</Pnumber>
            <P1para>
                <P2>
                    <Pnumber>1</Pnumber>
                    <P2para>
                        <Tabular>
                            <xhtml:table>
                                <xhtml:tbody>
                                    <xhtml:tr>
                                        <xhtml:td>Single row</xhtml:td>
                                        <xhtml:td>£1.00</xhtml:td>
                                    </xhtml:tr>
                                </xhtml:tbody>
                            </xhtml:table>
                        </Tabular>
                    </P2para>
                </P2>
            </P1para>
        </P1>
    </Body>
</Secondary>
</Legislation>
"""


def test_parse_section_preserves_xhtml_tables():
    section = parse_section(SAMPLE_UKSI_TABLE_XML)

    assert "The amounts are given in the following table." in section.text
    assert "| Standard allowance | £400.14 |" in section.text
    assert "| Carer element | £209.34 |" in section.text


def test_parse_section_preserves_single_row_xhtml_tables():
    section = parse_section(SAMPLE_UKSI_SINGLE_ROW_TABLE_XML)

    assert section.text == "| Single row | £1.00 |"


def test_extract_uk_legislation_requires_source_or_citation(tmp_path):
    with pytest.raises(ValueError, match="at least one source XML path or citation is required"):
        extract_uk_legislation_sections(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-05-29-uk-benefits",
        )


def test_extract_uk_legislation_writes_regulation_artifacts(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / "child-benefit-reg-2.xml"
    source_xml.write_text(SAMPLE_UKSI_REGULATION_XML)

    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="2026-05-29-uk-benefits",
        source_xmls=(source_xml,),
        source_as_of="2026-05-29",
    )

    assert report.source_count == 1
    assert report.provisions_written == 1
    class_report = report.class_reports[0]
    assert class_report.document_class == "regulation"
    assert class_report.coverage.complete

    provisions_path = base / "provisions/uk/regulation/2026-05-29-uk-benefits.jsonl"
    row = json.loads(provisions_path.read_text().strip())
    assert row["citation_path"] == "uk/regulation/uksi/2006/965/2"
    assert row["source_url"] == "http://www.legislation.gov.uk/uksi/2006/965/regulation/2"
    assert row["kind"] == "regulation"
    assert row["body"] == "The weekly rate of child benefit is £17.45."


def test_extract_uk_legislation_writes_statute_artifacts(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / "ita-2007-section-35.xml"
    source_xml.write_text(SAMPLE_UKPGA_SECTION_XML)

    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="2026-05-29-uk-income-tax",
        source_xmls=(source_xml,),
        expression_date="2026-04-06",
    )

    assert report.source_count == 1
    assert report.provisions_written == 1
    class_report = report.class_reports[0]
    assert class_report.document_class == "statute"
    assert class_report.coverage.complete

    provisions_path = base / "provisions/uk/statute/2026-05-29-uk-income-tax.jsonl"
    row = json.loads(provisions_path.read_text().strip())
    assert row["citation_path"] == "uk/statute/ukpga/2007/3/35"
    assert row["citation_label"] == "2007 c. 3 s. 35"
    assert row["kind"] == "section"
    assert row["ordinal"] == 35
    assert row["expression_date"] == "2026-04-06"


def test_extract_uk_legislation_fetches_citation_xml(tmp_path, monkeypatch):
    import axiom_corpus.corpus.uk_legislation as uk_legislation

    fetched_urls = []

    class FakeFetcher:
        def build_url(self, citation):
            return citation.data_xml_url

        async def _fetch_xml(self, url):
            fetched_urls.append(url)
            return SAMPLE_UKSI_REGULATION_XML

    monkeypatch.setattr(uk_legislation, "UKLegislationFetcher", FakeFetcher)
    base = tmp_path / "data" / "corpus"

    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="2026-05-29-uk-benefits",
        citations=("uksi/2006/965/regulation/2",),
        expression_date=date(2026, 4, 6),
    )

    assert fetched_urls == ["https://www.legislation.gov.uk/uksi/2006/965/regulation/2/data.xml"]
    assert report.source_count == 1
    row = json.loads((base / "provisions/uk/regulation/2026-05-29-uk-benefits.jsonl").read_text())
    assert row["expression_date"] == "2026-04-06"


def test_extract_uk_legislation_fetch_rejects_document_level_citations(tmp_path):
    with pytest.raises(ValueError, match="section or regulation required"):
        extract_uk_legislation_sections(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-05-29-uk-benefits",
            citations=("uksi/2006/965",),
        )


class _FakeLexClient:
    """Stub Lex client returning a fixed act plus its raw sections."""

    def __init__(self, enactment_date="2013-02-25", valid_date=None, sections=None):
        self.enactment_date = enactment_date
        self.valid_date = valid_date
        self.sections = sections or []
        self.section_requests = []

    def lookup_legislation(self, leg_type, year, number):
        from axiom_corpus.fetchers.lex import LexLegislation

        return LexLegislation(
            id=f"http://www.legislation.gov.uk/id/{leg_type}/{year}/{number}",
            type=leg_type,
            year=year,
            number=number,
            enactment_date=self.enactment_date,
            valid_date=self.valid_date,
            number_of_provisions=len(self.sections),
        )

    def lookup_sections_raw(self, legislation_id, limit):
        self.section_requests.append((legislation_id, limit))
        return self.sections


_LEX_UC_SECTIONS = [
    {
        "id": "http://www.legislation.gov.uk/id/uksi/2013/376/regulation/36",
        "uri": "http://www.legislation.gov.uk/uksi/2013/376/regulation/36",
        "title": "Table of amounts",
        "text": "The amounts are given in the following table.",
        "number": 36,
        "provision_type": "section",
    },
    {
        "id": "http://www.legislation.gov.uk/id/uksi/2013/376/schedule/1",
        "uri": "http://www.legislation.gov.uk/uksi/2013/376/schedule/1",
        "title": "Schedule 1",
        "text": "Schedule body.",
        "number": 1,
        "provision_type": "schedule",
    },
]


def test_extract_uk_legislation_ingests_full_act_from_lex(tmp_path, monkeypatch):
    import axiom_corpus.corpus.uk_legislation as uk_legislation

    fake = _FakeLexClient(sections=_LEX_UC_SECTIONS)
    monkeypatch.setattr(uk_legislation, "LexClient", lambda *a, **k: fake)
    base = tmp_path / "data" / "corpus"

    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="2026-05-29-uk-benefits",
        citations=("uksi/2013/376",),
        source="lex",
    )

    # The schedule provision is skipped; only the regulation is written.
    assert report.provisions_written == 1
    assert fake.section_requests == [("uksi/2013/376", 2)]

    provisions_path = base / "provisions/uk/regulation/2026-05-29-uk-benefits.jsonl"
    row = json.loads(provisions_path.read_text().strip())
    assert row["citation_path"] == "uk/regulation/uksi/2013/376/36"
    assert row["kind"] == "regulation"
    assert row["body"] == "The amounts are given in the following table."
    assert row["source_format"] == "lex.lab.i.ai.gov.uk"
    assert row["source_url"] == "http://www.legislation.gov.uk/uksi/2013/376/regulation/36"


def test_extract_uk_legislation_lex_filters_to_requested_section(tmp_path, monkeypatch):
    import axiom_corpus.corpus.uk_legislation as uk_legislation

    sections = _LEX_UC_SECTIONS + [
        {
            "id": "http://www.legislation.gov.uk/id/uksi/2013/376/regulation/37",
            "uri": "http://www.legislation.gov.uk/uksi/2013/376/regulation/37",
            "title": "Other",
            "text": "Other body.",
            "number": 37,
            "provision_type": "section",
        }
    ]
    fake = _FakeLexClient(sections=sections)
    monkeypatch.setattr(uk_legislation, "LexClient", lambda *a, **k: fake)
    base = tmp_path / "data" / "corpus"

    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="2026-05-29-uk-benefits",
        citations=("uksi/2013/376/regulation/37",),
        source="lex",
    )

    assert report.provisions_written == 1
    row = json.loads(
        (base / "provisions/uk/regulation/2026-05-29-uk-benefits.jsonl").read_text().strip()
    )
    assert row["citation_path"] == "uk/regulation/uksi/2013/376/37"
    assert row["body"] == "Other body."


def test_extract_uk_legislation_lex_falls_back_to_valid_date(tmp_path, monkeypatch):
    import axiom_corpus.corpus.uk_legislation as uk_legislation

    # Statutory instruments carry no enactment date in Lex.
    fake = _FakeLexClient(enactment_date=None, valid_date="2026-04-06", sections=_LEX_UC_SECTIONS)
    monkeypatch.setattr(uk_legislation, "LexClient", lambda *a, **k: fake)
    base = tmp_path / "data" / "corpus"

    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="2026-05-29-uk-benefits",
        citations=("uksi/2013/376",),
        source="lex",
    )

    assert report.provisions_written == 1


def test_extract_uk_legislation_lex_no_usable_date_raises(tmp_path, monkeypatch):
    import axiom_corpus.corpus.uk_legislation as uk_legislation

    fake = _FakeLexClient(enactment_date=None, valid_date=None, sections=_LEX_UC_SECTIONS)
    monkeypatch.setattr(uk_legislation, "LexClient", lambda *a, **k: fake)

    with pytest.raises(ValueError, match="no usable date"):
        extract_uk_legislation_sections(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-05-29-uk-benefits",
            citations=("uksi/2013/376",),
            source="lex",
        )


def test_extract_uk_legislation_lex_missing_section_raises(tmp_path, monkeypatch):
    import axiom_corpus.corpus.uk_legislation as uk_legislation

    fake = _FakeLexClient(sections=_LEX_UC_SECTIONS)
    monkeypatch.setattr(uk_legislation, "LexClient", lambda *a, **k: fake)

    with pytest.raises(ValueError, match="no section matching"):
        extract_uk_legislation_sections(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-05-29-uk-benefits",
            citations=("uksi/2013/376/regulation/999",),
            source="lex",
        )


def test_extract_uk_legislation_lex_matches_section_case_insensitively(tmp_path, monkeypatch):
    import axiom_corpus.corpus.uk_legislation as uk_legislation

    # Lex uppercases alphanumeric provision tokens (e.g. "11D"); citations in
    # the standard legislation.gov.uk form are lowercase ("11d").
    sections = [
        {
            "id": "http://www.legislation.gov.uk/id/ukpga/2007/3/section/11D",
            "uri": "http://www.legislation.gov.uk/ukpga/2007/3/section/11D",
            "title": "Income charged at the savings nil rate",
            "text": "Savings nil rate.",
            "number": None,
            "provision_type": "section",
        }
    ]
    fake = _FakeLexClient(enactment_date="2007-03-20", sections=sections)
    monkeypatch.setattr(uk_legislation, "LexClient", lambda *a, **k: fake)
    base = tmp_path / "data" / "corpus"

    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="2026-06-01-uk-statute",
        citations=("ukpga/2007/3/section/11d",),
        source="lex",
    )

    assert report.provisions_written == 1
    row = json.loads(
        (base / "provisions/uk/statute/2026-06-01-uk-statute.jsonl").read_text().strip()
    )
    assert row["citation_path"] == "uk/statute/ukpga/2007/3/11D"
    assert row["body"] == "Savings nil rate."
