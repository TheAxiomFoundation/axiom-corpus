"""Part-qualified and schedule-like UK citation support (axiom-corpus#322).

legislation.gov.uk serves council-tax-reduction applicable-amount provisions only
at citation forms the old model rejected or collapsed:

* ``schedule/N/part/M/paragraph/P`` — part-qualified schedule paragraph
  (SI 2012/2885 pensioner applicable amounts).
* ``schedule/N/part/M`` — a paragraph-less part (SI 2012/2885 Sch 2 Part 4).
* ``schedule/paragraph/P`` — an unnumbered outer schedule (SI 2012/2886, the
  England working-age default scheme; ``schedule/1/paragraph/16`` 404s while
  ``schedule/paragraph/16`` 200s).
* ``appendix/N/paragraph/M`` — an internal schedule served as an appendix
  (SI 2012/2886 Schedules 1-10). Appendix paragraph URIs are flat: never
  ``appendix/N/part/M/paragraph/P``.

The canonical stored ``citation_path`` mirrors the official URL exactly (no
schedule number for an unnumbered schedule; the ``appendix`` segment preserved):

* ``uk/regulation/uksi/2012/2885/schedule/2/part/1/paragraph/1``
* ``uk/regulation/uksi/2012/2885/schedule/2/part/4``
* ``uk/regulation/uksi/2012/2886/schedule/paragraph/16``
* ``uk/regulation/uksi/2012/2886/appendix/3/paragraph/1``

The inline fixtures reproduce the element nesting and DocumentURI structure
observed in the live CLML for these instruments.
"""

import json
from datetime import date

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.uk_legislation import (
    _parent_citation_path,
    extract_uk_legislation_sections,
    uk_citation_path,
)
from axiom_corpus.models_uk import UKCitation, UKSection
from axiom_corpus.parsers.clml import parse_section

# ---------------------------------------------------------------------------
# Faithful inline CLML fixtures (real DocumentURIs + real 2013-vintage amounts).
# ---------------------------------------------------------------------------

# SI 2012/2885 Schedule 2 Part 1 paragraph 1 — pensioner personal allowance.
PART_QUALIFIED_PARAGRAPH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             DocumentURI="http://www.legislation.gov.uk/uksi/2012/2885"
             IdURI="http://www.legislation.gov.uk/id/uksi/2012/2885"
             RestrictExtent="E+W">
<ukm:Metadata>
    <dc:identifier>http://www.legislation.gov.uk/uksi/2012/2885/schedule/2/part/1/paragraph/1</dc:identifier>
    <dc:title>The Council Tax Reduction Schemes (Prescribed Requirements) (England) Regulations 2012</dc:title>
    <ukm:SecondaryMetadata><ukm:Year Value="2012"/><ukm:Number Value="2885"/></ukm:SecondaryMetadata>
    <ukm:EnactmentDate Date="2012-11-16"/>
</ukm:Metadata>
<Secondary>
  <Schedules>
    <Schedule DocumentURI="http://www.legislation.gov.uk/uksi/2012/2885/schedule/2" id="schedule-2">
      <Number>SCHEDULE 2</Number>
      <ScheduleBody>
        <Part DocumentURI="http://www.legislation.gov.uk/uksi/2012/2885/schedule/2/part/1" id="schedule-2-part-1">
          <Number>PART 1</Number>
          <Title>Pensioners</Title>
          <P1group>
            <Title>Personal allowance</Title>
            <P1 DocumentURI="http://www.legislation.gov.uk/uksi/2012/2885/schedule/2/part/1/paragraph/1"
                IdURI="http://www.legislation.gov.uk/id/uksi/2012/2885/schedule/2/part/1/paragraph/1"
                id="schedule-2-part-1-paragraph-1">
              <Pnumber>1</Pnumber>
              <P1para>
                <Text>The amounts specified for the purposes of paragraph 6(1)(a) are, for a single applicant, £256.00, and for a couple, £383.35.</Text>
              </P1para>
            </P1>
          </P1group>
        </Part>
      </ScheduleBody>
    </Schedule>
  </Schedules>
</Secondary>
</Legislation>
"""

# SI 2012/2885 Schedule 2 Part 4 — "Amounts of premium", a paragraph-less part.
PARAGRAPH_LESS_PART_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             DocumentURI="http://www.legislation.gov.uk/uksi/2012/2885"
             IdURI="http://www.legislation.gov.uk/id/uksi/2012/2885"
             RestrictExtent="E+W">
<ukm:Metadata>
    <dc:identifier>http://www.legislation.gov.uk/uksi/2012/2885/schedule/2/part/4</dc:identifier>
    <dc:title>The Council Tax Reduction Schemes (Prescribed Requirements) (England) Regulations 2012</dc:title>
    <ukm:SecondaryMetadata><ukm:Year Value="2012"/><ukm:Number Value="2885"/></ukm:SecondaryMetadata>
    <ukm:EnactmentDate Date="2012-11-16"/>
</ukm:Metadata>
<Secondary>
  <Schedules>
    <Schedule DocumentURI="http://www.legislation.gov.uk/uksi/2012/2885/schedule/2" id="schedule-2">
      <Number>SCHEDULE 2</Number>
      <ScheduleBody>
        <Part DocumentURI="http://www.legislation.gov.uk/uksi/2012/2885/schedule/2/part/4"
              IdURI="http://www.legislation.gov.uk/id/uksi/2012/2885/schedule/2/part/4"
              id="schedule-2-part-4">
          <Title>Amounts of premium</Title>
          <P1para>
            <Text>Severe Disability Premium — where the applicant satisfies the condition, £86.05; where both members of a couple satisfy the condition, £172.10.</Text>
          </P1para>
        </Part>
      </ScheduleBody>
    </Schedule>
  </Schedules>
</Secondary>
</Legislation>
"""

# SI 2012/2886 outer scheme — one UNNUMBERED schedule; paragraph 16 (Class D).
UNNUMBERED_SCHEDULE_PARAGRAPH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             DocumentURI="http://www.legislation.gov.uk/uksi/2012/2886"
             IdURI="http://www.legislation.gov.uk/id/uksi/2012/2886"
             RestrictExtent="E+W">
<ukm:Metadata>
    <dc:identifier>http://www.legislation.gov.uk/uksi/2012/2886/schedule/paragraph/16</dc:identifier>
    <dc:title>The Council Tax Reduction Schemes (Default Scheme) (England) Regulations 2012</dc:title>
    <ukm:SecondaryMetadata><ukm:Year Value="2012"/><ukm:Number Value="2886"/></ukm:SecondaryMetadata>
    <ukm:EnactmentDate Date="2012-11-16"/>
</ukm:Metadata>
<Secondary>
  <Schedules>
    <Schedule DocumentURI="http://www.legislation.gov.uk/uksi/2012/2886/schedule" id="schedule">
      <Number/>
      <Title>Council Tax Reduction Scheme (Default Scheme)</Title>
      <ScheduleBody>
        <Part DocumentURI="http://www.legislation.gov.uk/uksi/2012/2886/schedule/part/4">
          <Number>PART 4</Number>
          <Title>Classes of person entitled to a reduction</Title>
          <P1group>
            <Title>Class D: persons who are not pensioners whose income is less than the applicable amount</Title>
            <P1 DocumentURI="http://www.legislation.gov.uk/uksi/2012/2886/schedule/paragraph/16"
                IdURI="http://www.legislation.gov.uk/id/uksi/2012/2886/schedule/paragraph/16"
                id="schedule-paragraph-16">
              <Pnumber>16</Pnumber>
              <P1para>
                <Text>On any day class D consists of any person who is not a pensioner whose income is less than the applicable amount.</Text>
              </P1para>
            </P1>
          </P1group>
        </Part>
      </ScheduleBody>
    </Schedule>
  </Schedules>
</Secondary>
</Legislation>
"""

# SI 2012/2886 internal Schedule 3 served as appendix/3; paragraph 1 amounts.
APPENDIX_PARAGRAPH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"
             xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             DocumentURI="http://www.legislation.gov.uk/uksi/2012/2886"
             IdURI="http://www.legislation.gov.uk/id/uksi/2012/2886"
             RestrictExtent="E+W">
<ukm:Metadata>
    <dc:identifier>http://www.legislation.gov.uk/uksi/2012/2886/appendix/3/paragraph/1</dc:identifier>
    <dc:title>The Council Tax Reduction Schemes (Default Scheme) (England) Regulations 2012</dc:title>
    <ukm:SecondaryMetadata><ukm:Year Value="2012"/><ukm:Number Value="2886"/></ukm:SecondaryMetadata>
    <ukm:EnactmentDate Date="2012-11-16"/>
</ukm:Metadata>
<Secondary>
  <Schedules>
    <Appendix DocumentURI="http://www.legislation.gov.uk/uksi/2012/2886/appendix/3" id="appendix-3">
      <Number>SCHEDULE 3</Number>
      <Title>Applicable amounts: persons who are not pensioners</Title>
      <Part DocumentURI="http://www.legislation.gov.uk/uksi/2012/2886/appendix/3/part/1" id="appendix-3-part-1">
        <Number>PART 1</Number>
        <Title>Personal allowances</Title>
        <P1 DocumentURI="http://www.legislation.gov.uk/uksi/2012/2886/appendix/3/paragraph/1"
            IdURI="http://www.legislation.gov.uk/id/uksi/2012/2886/appendix/3/paragraph/1"
            id="appendix-3-paragraph-1">
          <Pnumber>1</Pnumber>
          <P1para>
            <Text>The amounts are, for a single applicant £71.70, for a lone parent £56.80, and for a couple £112.55.</Text>
          </P1para>
        </P1>
      </Part>
    </Appendix>
  </Schedules>
</Secondary>
</Legislation>
"""


# ---------------------------------------------------------------------------
# Model: UKCitation.from_string + url/path/short_cite round-trips.
# ---------------------------------------------------------------------------


class TestScheduleLikeCitationModel:
    def test_part_qualified_paragraph(self):
        c = UKCitation.from_string("uksi/2012/2885/schedule/2/part/1/paragraph/1")
        assert (c.provision_kind, c.section, c.part, c.paragraph) == ("schedule", "2", "1", "1")
        assert c.legislation_url == (
            "https://www.legislation.gov.uk/uksi/2012/2885/schedule/2/part/1/paragraph/1"
        )
        assert c.path == "uk/uksi/2012/2885/schedule/2/part/1/paragraph/1"
        assert c.short_cite == "UKSI 2012/2885 Sch. 2 Pt. 1 para. 1"

    def test_paragraph_less_part(self):
        c = UKCitation.from_string("uksi/2012/2885/schedule/2/part/4")
        assert (c.provision_kind, c.section, c.part, c.paragraph) == ("schedule", "2", "4", None)
        assert c.legislation_url == (
            "https://www.legislation.gov.uk/uksi/2012/2885/schedule/2/part/4"
        )
        assert c.path == "uk/uksi/2012/2885/schedule/2/part/4"
        assert c.short_cite == "UKSI 2012/2885 Sch. 2 Pt. 4"

    def test_unnumbered_schedule_paragraph(self):
        c = UKCitation.from_string("uksi/2012/2886/schedule/paragraph/16")
        assert c.provision_kind == "schedule"
        assert c.section is None
        assert c.part is None
        assert c.paragraph == "16"
        assert c.legislation_url == (
            "https://www.legislation.gov.uk/uksi/2012/2886/schedule/paragraph/16"
        )
        assert c.path == "uk/uksi/2012/2886/schedule/paragraph/16"
        assert c.short_cite == "UKSI 2012/2886 Sch. para. 16"

    def test_appendix_paragraph(self):
        c = UKCitation.from_string("uksi/2012/2886/appendix/3/paragraph/1")
        assert (c.provision_kind, c.section, c.part, c.paragraph) == ("appendix", "3", None, "1")
        assert c.legislation_url == (
            "https://www.legislation.gov.uk/uksi/2012/2886/appendix/3/paragraph/1"
        )
        assert c.path == "uk/uksi/2012/2886/appendix/3/paragraph/1"
        assert c.short_cite == "UKSI 2012/2886 App. 3 para. 1"

    def test_existing_numbered_schedule_paragraph_unchanged(self):
        c = UKCitation.from_string("uksi/2013/376/schedule/4/paragraph/7")
        assert (c.provision_kind, c.section, c.part, c.paragraph) == ("schedule", "4", None, "7")
        assert c.path == "uk/uksi/2013/376/schedule/4/paragraph/7"

    @pytest.mark.parametrize(
        "raw",
        [
            "uksi/2012/2885/schedule/2/part/1/paragraph/1",
            "uksi/2012/2885/schedule/2/part/4",
            "uksi/2012/2886/schedule/paragraph/16",
            "uksi/2012/2886/appendix/3/paragraph/1",
            "uksi/2013/376/schedule/4/paragraph/7",
            "uksi/2006/965/regulation/2",
            "ukpga/2003/1/section/62",
        ],
    )
    def test_url_round_trips(self, raw):
        assert UKCitation.from_string(raw).legislation_url.endswith(raw)


# ---------------------------------------------------------------------------
# parse_section: citation + scoped body + structural title.
# ---------------------------------------------------------------------------


class TestParseSectionScheduleLike:
    def test_part_qualified_paragraph(self):
        section = parse_section(PART_QUALIFIED_PARAGRAPH_XML)
        c = section.citation
        assert (c.type, c.number, c.provision_kind) == ("uksi", 2885, "schedule")
        assert (c.section, c.part, c.paragraph) == ("2", "1", "1")
        assert section.title == "Schedule 2 Part 1 paragraph 1 - Personal allowance"
        assert "£256.00" in section.text
        assert "£383.35" in section.text

    def test_paragraph_less_part(self):
        section = parse_section(PARAGRAPH_LESS_PART_XML)
        c = section.citation
        assert (c.section, c.part, c.paragraph) == ("2", "4", None)
        assert section.title == "Schedule 2 Part 4 - Amounts of premium"
        assert "£86.05" in section.text
        assert "£172.10" in section.text

    def test_unnumbered_schedule_paragraph(self):
        section = parse_section(UNNUMBERED_SCHEDULE_PARAGRAPH_XML)
        c = section.citation
        assert c.provision_kind == "schedule"
        assert c.section is None
        assert c.paragraph == "16"
        assert section.title.startswith("Schedule paragraph 16 - Class D")
        assert "class D" in section.text
        # Body is scoped to paragraph 16, not the whole scheme.
        assert "PART 4" not in section.text

    def test_appendix_paragraph(self):
        section = parse_section(APPENDIX_PARAGRAPH_XML)
        c = section.citation
        assert (c.provision_kind, c.section, c.paragraph) == ("appendix", "3", "1")
        assert section.title == "Appendix 3 paragraph 1"
        assert "£71.70" in section.text
        assert "£112.55" in section.text


# ---------------------------------------------------------------------------
# Full extraction pipeline: citation_path, kind, parent, identifiers, body.
# ---------------------------------------------------------------------------


def _extract_single(tmp_path, xml_text, filename):
    base = tmp_path / "data" / "corpus"
    source_xml = tmp_path / filename
    source_xml.write_text(xml_text)
    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="ctr",
        source_xmls=(source_xml,),
    )
    assert report.provisions_written == 1
    provisions_path = base / "provisions/uk/regulation/ctr.jsonl"
    return json.loads(provisions_path.read_text().strip())


def test_extract_part_qualified_paragraph(tmp_path):
    row = _extract_single(tmp_path, PART_QUALIFIED_PARAGRAPH_XML, "p1.xml")
    assert row["citation_path"] == "uk/regulation/uksi/2012/2885/schedule/2/part/1/paragraph/1"
    assert row["kind"] == "paragraph"
    assert row["ordinal"] == 1
    # Parent (the part) is not in this single-provision batch, so the link is dropped.
    assert "parent_citation_path" not in row
    assert row["identifiers"]["legislation.gov.uk:provision"] == (
        "schedule/2/part/1/paragraph/1"
    )
    assert row["metadata"]["schedule"] == "2"
    assert row["metadata"]["part"] == "1"
    assert "£256.00" in row["body"]
    assert "£383.35" in row["body"]
    assert row["source_path"].endswith(
        "/uksi/2012/2885/schedule-2-part-1-paragraph-1.xml"
    )


def test_extract_paragraph_less_part(tmp_path):
    row = _extract_single(tmp_path, PARAGRAPH_LESS_PART_XML, "p4.xml")
    assert row["citation_path"] == "uk/regulation/uksi/2012/2885/schedule/2/part/4"
    assert row["kind"] == "part"
    assert row["ordinal"] == 4
    assert "parent_citation_path" not in row
    assert row["identifiers"]["legislation.gov.uk:provision"] == "schedule/2/part/4"
    assert "£86.05" in row["body"]
    assert row["source_path"].endswith("/uksi/2012/2885/schedule-2-part-4.xml")


def test_extract_unnumbered_schedule_paragraph(tmp_path):
    row = _extract_single(tmp_path, UNNUMBERED_SCHEDULE_PARAGRAPH_XML, "s16.xml")
    # The paragraph is NOT dropped even though the outer schedule is unnumbered.
    assert row["citation_path"] == "uk/regulation/uksi/2012/2886/schedule/paragraph/16"
    assert row["kind"] == "paragraph"
    assert row["ordinal"] == 16
    assert "parent_citation_path" not in row
    assert row["identifiers"]["legislation.gov.uk:provision"] == "schedule/paragraph/16"
    assert "class D" in row["body"]
    assert row["source_path"].endswith("/uksi/2012/2886/schedule-paragraph-16.xml")


def test_extract_appendix_paragraph(tmp_path):
    row = _extract_single(tmp_path, APPENDIX_PARAGRAPH_XML, "a3p1.xml")
    assert row["citation_path"] == "uk/regulation/uksi/2012/2886/appendix/3/paragraph/1"
    assert row["kind"] == "paragraph"
    assert row["ordinal"] == 1
    assert "parent_citation_path" not in row
    assert row["identifiers"]["legislation.gov.uk:provision"] == "appendix/3/paragraph/1"
    assert "£71.70" in row["body"]
    assert "£112.55" in row["body"]
    assert row["source_path"].endswith("/uksi/2012/2886/appendix-3-paragraph-1.xml")


def _citation(raw: str) -> UKCitation:
    return UKCitation.from_string(raw)


def _section(raw: str) -> UKSection:
    return UKSection(
        citation=_citation(raw), title="t", text="b", enacted_date=date(2012, 11, 16)
    )


class TestScheduleLikePathHelpers:
    """Direct checks of the corpus citation-path and parent-path builders, whose
    parent links the single-provision extraction tests drop as orphans."""

    def test_citation_paths(self):
        assert uk_citation_path(_section("uksi/2012/2885/schedule/2/part/1/paragraph/1")) == (
            "uk/regulation/uksi/2012/2885/schedule/2/part/1/paragraph/1"
        )
        assert uk_citation_path(_section("uksi/2012/2885/schedule/2/part/4")) == (
            "uk/regulation/uksi/2012/2885/schedule/2/part/4"
        )
        assert uk_citation_path(_section("uksi/2012/2886/schedule/paragraph/16")) == (
            "uk/regulation/uksi/2012/2886/schedule/paragraph/16"
        )
        assert uk_citation_path(_section("uksi/2012/2886/appendix/3/paragraph/1")) == (
            "uk/regulation/uksi/2012/2886/appendix/3/paragraph/1"
        )

    def test_parent_paths(self):
        cases = {
            # A part-qualified paragraph's parent is its part.
            "uksi/2012/2885/schedule/2/part/1/paragraph/1": (
                "uk/regulation/uksi/2012/2885/schedule/2/part/1"
            ),
            # A part's parent is its (numbered) schedule.
            "uksi/2012/2885/schedule/2/part/4": "uk/regulation/uksi/2012/2885/schedule/2",
            # An unnumbered-schedule paragraph's parent is the schedule container.
            "uksi/2012/2886/schedule/paragraph/16": "uk/regulation/uksi/2012/2886/schedule",
            # An appendix paragraph's parent is the appendix.
            "uksi/2012/2886/appendix/3/paragraph/1": "uk/regulation/uksi/2012/2886/appendix/3",
        }
        for raw, expected_parent in cases.items():
            citation = _citation(raw)
            path = uk_citation_path(_section(raw))
            assert _parent_citation_path(citation, path) == expected_parent


def test_distinct_paragraphs_do_not_collide(tmp_path):
    """Two paragraphs of the same unnumbered schedule get distinct citation paths
    and distinct source captures -- the pre-fix bug deduped every paragraph to a
    single bare ``schedule`` record."""
    base = tmp_path / "data" / "corpus"
    p16 = tmp_path / "s16.xml"
    p16.write_text(UNNUMBERED_SCHEDULE_PARAGRAPH_XML)
    p1 = tmp_path / "a3p1.xml"
    p1.write_text(APPENDIX_PARAGRAPH_XML)
    report = extract_uk_legislation_sections(
        CorpusArtifactStore(base),
        version="ctr",
        source_xmls=(p16, p1),
    )
    assert report.provisions_written == 2
    rows = [
        json.loads(line)
        for line in (base / "provisions/uk/regulation/ctr.jsonl")
        .read_text()
        .splitlines()
        if line.strip()
    ]
    paths = {row["citation_path"] for row in rows}
    assert paths == {
        "uk/regulation/uksi/2012/2886/schedule/paragraph/16",
        "uk/regulation/uksi/2012/2886/appendix/3/paragraph/1",
    }
