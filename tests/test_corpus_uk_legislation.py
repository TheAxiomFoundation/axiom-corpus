import json
from datetime import date

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.uk_legislation import extract_uk_legislation_sections
from axiom_corpus.fetchers.legislation_uk import UKLegislationFetcher
from axiom_corpus.models_uk import UKCitation
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


SAMPLE_UKSI_SCHEDULE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             xmlns:xhtml="http://www.w3.org/1999/xhtml"
             DocumentURI="http://www.legislation.gov.uk/uksi/2002/2005/2026-04-06">
<ukm:Metadata>
    <dc:identifier>http://www.legislation.gov.uk/uksi/2002/2005/schedule/2/2026-04-06</dc:identifier>
    <dc:title>The Working Tax Credit (Entitlement and Maximum Rate) Regulations 2002</dc:title>
    <ukm:SecondaryMetadata>
        <ukm:Year Value="2002"/>
        <ukm:Number Value="2005"/>
        <ukm:Made Date="2002-07-30"/>
    </ukm:SecondaryMetadata>
</ukm:Metadata>
<Secondary>
    <Schedules>
        <Schedule DocumentURI="http://www.legislation.gov.uk/uksi/2002/2005/schedule/2/2026-04-06"
                  id="schedule-2"
                  RestrictExtent="E+W+S+N.I.">
            <Number>SCHEDULE 2</Number>
            <TitleBlock>
                <Title>MAXIMUM RATES OF THE ELEMENTS OF A WORKING TAX CREDIT</Title>
            </TitleBlock>
            <ScheduleBody>
                <Tabular>
                    <xhtml:table>
                        <xhtml:tbody>
                            <xhtml:tr>
                                <xhtml:td>Relevant element of working tax credit</xhtml:td>
                                <xhtml:td>Maximum annual rate</xhtml:td>
                            </xhtml:tr>
                            <xhtml:tr>
                                <xhtml:td>
                                    <P1 DocumentURI="http://www.legislation.gov.uk/uksi/2002/2005/schedule/2/paragraph/1">
                                        <Pnumber>1</Pnumber>
                                        <P1para>
                                            <Text>Basic element</Text>
                                        </P1para>
                                    </P1>
                                </xhtml:td>
                                <xhtml:td>£2,435</xhtml:td>
                            </xhtml:tr>
                        </xhtml:tbody>
                    </xhtml:table>
                </Tabular>
            </ScheduleBody>
        </Schedule>
    </Schedules>
</Secondary>
<Commentaries>
    <Commentary id="c1"><Para><Text>Sch. 2 modified by another instrument.</Text></Para></Commentary>
</Commentaries>
</Legislation>
"""


SAMPLE_UKSI_SCHEDULE_PARAGRAPH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             DocumentURI="http://www.legislation.gov.uk/uksi/2013/376"
             RestrictExtent="E+W+S">
<ukm:Metadata>
    <dc:identifier>http://www.legislation.gov.uk/uksi/2013/376/schedule/4/paragraph/7</dc:identifier>
    <dc:title>The Universal Credit Regulations 2013</dc:title>
    <ukm:SecondaryMetadata>
        <ukm:Year Value="2013"/>
        <ukm:Number Value="376"/>
        <ukm:Made Date="2013-02-25"/>
    </ukm:SecondaryMetadata>
</ukm:Metadata>
<Secondary>
    <Schedules>
        <Schedule DocumentURI="http://www.legislation.gov.uk/uksi/2013/376/schedule/4"
                  id="schedule-4">
            <Number>SCHEDULE 4</Number>
            <ScheduleBody>
                <P1group>
                    <Title>Relevant payments calculated monthly</Title>
                    <P1 DocumentURI="http://www.legislation.gov.uk/uksi/2013/376/schedule/4/paragraph/7"
                        IdURI="http://www.legislation.gov.uk/id/uksi/2013/376/schedule/4/paragraph/7"
                        id="schedule-4-paragraph-7">
                        <Pnumber>7</Pnumber>
                        <P1para>
                            <P2 DocumentURI="http://www.legislation.gov.uk/uksi/2013/376/schedule/4/paragraph/7/1">
                                <Pnumber>1</Pnumber>
                                <P2para>
                                    <Text>The amount of that payment is to be calculated as a monthly amount.</Text>
                                </P2para>
                            </P2>
                            <P2 DocumentURI="http://www.legislation.gov.uk/uksi/2013/376/schedule/4/paragraph/7/2">
                                <Pnumber>2</Pnumber>
                                <P2para>
                                    <Text>Weekly payments are multiplied by 52 and divided by 12.</Text>
                                </P2para>
                            </P2>
                        </P1para>
                    </P1>
                </P1group>
            </ScheduleBody>
        </Schedule>
    </Schedules>
</Secondary>
</Legislation>
"""


def test_uk_citation_parses_schedule_paragraph():
    citation = UKCitation.from_string("uksi/2013/376/schedule/4/paragraph/7")

    assert citation.type == "uksi"
    assert citation.year == 2013
    assert citation.number == 376
    assert citation.section == "4"
    assert citation.provision_segment == "schedule"
    assert citation.paragraph == "7"
    assert citation.legislation_url == (
        "https://www.legislation.gov.uk/uksi/2013/376/schedule/4/paragraph/7"
    )
    assert UKLegislationFetcher().build_url(citation) == (
        "https://www.legislation.gov.uk/uksi/2013/376/schedule/4/paragraph/7/data.xml"
    )
    assert citation.short_cite == "UKSI 2013/376 Sch. 4 para. 7"
    assert citation.path == "uk/uksi/2013/376/schedule/4/paragraph/7"


def test_parse_section_preserves_xhtml_tables():
    section = parse_section(SAMPLE_UKSI_TABLE_XML)

    assert "The amounts are given in the following table." in section.text
    assert "| Standard allowance | £400.14 |" in section.text
    assert "| Carer element | £209.34 |" in section.text


def test_parse_section_preserves_single_row_xhtml_tables():
    section = parse_section(SAMPLE_UKSI_SINGLE_ROW_TABLE_XML)

    assert section.text == "| Single row | £1.00 |"


def test_parse_section_handles_schedule_citation_and_text():
    section = parse_section(SAMPLE_UKSI_SCHEDULE_XML)

    assert section.citation.type == "uksi"
    assert section.citation.year == 2002
    assert section.citation.number == 2005
    assert section.citation.section == "2"
    assert section.citation.provision_segment == "schedule"
    assert section.title == "Schedule 2"
    assert section.source_url == "http://www.legislation.gov.uk/uksi/2002/2005/schedule/2/2026-04-06"
    assert "Maximum annual rate" in section.text
    assert "Basic element" in section.text
    assert "£2,435" in section.text
    assert "modified by another instrument" not in section.text


def test_parse_section_handles_schedule_paragraph_citation_and_text():
    section = parse_section(SAMPLE_UKSI_SCHEDULE_PARAGRAPH_XML)

    assert section.citation.type == "uksi"
    assert section.citation.year == 2013
    assert section.citation.number == 376
    assert section.citation.section == "4"
    assert section.citation.provision_segment == "schedule"
    assert section.citation.paragraph == "7"
    assert section.title == "Schedule 4 paragraph 7 - Relevant payments calculated monthly"
    assert section.source_url == "http://www.legislation.gov.uk/uksi/2013/376/schedule/4/paragraph/7"
    assert section.text == (
        "The amount of that payment is to be calculated as a monthly amount.\n"
        "Weekly payments are multiplied by 52 and divided by 12."
    )


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


def test_extract_uk_legislation_writes_schedule_artifacts(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / "wtc-schedule-2.xml"
    source_xml.write_text(SAMPLE_UKSI_SCHEDULE_XML)

    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="2026-06-05-uk-tax-credits",
        source_xmls=(source_xml,),
        expression_date="2026-04-06",
    )

    assert report.source_count == 1
    assert report.provisions_written == 1
    class_report = report.class_reports[0]
    assert class_report.document_class == "regulation"
    assert class_report.coverage.complete

    provisions_path = base / "provisions/uk/regulation/2026-06-05-uk-tax-credits.jsonl"
    row = json.loads(provisions_path.read_text().strip())
    assert row["citation_path"] == "uk/regulation/uksi/2002/2005/schedule/2"
    assert row["citation_label"] == "UKSI 2002/2005 Sch. 2"
    assert row["kind"] == "schedule"
    assert row["ordinal"] == 2
    assert row["source_url"] == "http://www.legislation.gov.uk/uksi/2002/2005/schedule/2/2026-04-06"
    assert row["source_path"] == (
        "sources/uk/regulation/2026-06-05-uk-tax-credits/"
        "uksi/2002/2005/schedule-2.xml"
    )
    assert "Basic element" in row["body"]
    assert "£2,435" in row["body"]


def test_extract_uk_legislation_writes_schedule_paragraph_artifacts(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / "uc-schedule-4-paragraph-7.xml"
    source_xml.write_text(SAMPLE_UKSI_SCHEDULE_PARAGRAPH_XML)

    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="2026-06-06-uk-universal-credit-schedule4-paragraph7",
        source_xmls=(source_xml,),
        expression_date="2026-04-30",
    )

    assert report.source_count == 1
    assert report.provisions_written == 1
    class_report = report.class_reports[0]
    assert class_report.document_class == "regulation"
    assert class_report.coverage.complete

    provisions_path = (
        base
        / "provisions/uk/regulation/2026-06-06-uk-universal-credit-schedule4-paragraph7.jsonl"
    )
    row = json.loads(provisions_path.read_text().strip())
    assert row["citation_path"] == "uk/regulation/uksi/2013/376/schedule/4/paragraph/7"
    assert row["citation_label"] == "UKSI 2013/376 Sch. 4 para. 7"
    assert row["parent_citation_path"] == "uk/regulation/uksi/2013/376/schedule/4"
    assert row["kind"] == "paragraph"
    assert row["level"] == 2
    assert row["ordinal"] == 7
    assert row["identifiers"]["legislation.gov.uk:provision"] == "schedule/4/paragraph/7"
    assert row["metadata"]["schedule"] == "4"
    assert row["source_path"] == (
        "sources/uk/regulation/2026-06-06-uk-universal-credit-schedule4-paragraph7/"
        "uksi/2013/376/schedule-4-paragraph-7.xml"
    )
    assert "monthly amount" in row["body"]


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


def test_extract_uk_legislation_fetches_schedule_paragraph_citation_xml(tmp_path, monkeypatch):
    import axiom_corpus.corpus.uk_legislation as uk_legislation

    fetched_urls = []

    class FakeFetcher:
        def build_url(self, citation):
            return citation.data_xml_url

        async def _fetch_xml(self, url):
            fetched_urls.append(url)
            return SAMPLE_UKSI_SCHEDULE_PARAGRAPH_XML

    monkeypatch.setattr(uk_legislation, "UKLegislationFetcher", FakeFetcher)
    base = tmp_path / "data" / "corpus"

    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="2026-06-06-uk-universal-credit-schedule4-paragraph7",
        citations=("uksi/2013/376/schedule/4/paragraph/7",),
        expression_date=date(2026, 4, 30),
    )

    assert fetched_urls == [
        "https://www.legislation.gov.uk/uksi/2013/376/schedule/4/paragraph/7/data.xml"
    ]
    assert report.source_count == 1
    row = json.loads(
        (
            base
            / "provisions/uk/regulation/2026-06-06-uk-universal-credit-schedule4-paragraph7.jsonl"
        ).read_text()
    )
    assert row["citation_path"] == "uk/regulation/uksi/2013/376/schedule/4/paragraph/7"


def test_extract_uk_legislation_fetch_rejects_document_level_citations(tmp_path):
    with pytest.raises(ValueError, match="section, regulation, or schedule required"):
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
