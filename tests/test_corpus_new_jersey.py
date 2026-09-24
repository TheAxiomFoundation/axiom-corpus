from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.new_jersey import (
    NEW_JERSEY_STATUTES_TEXT_MEMBER,
    NEW_JERSEY_STATUTES_TEXT_SOURCE_FORMAT,
    NewJerseySource,
    extract_new_jersey_statutes,
    parse_new_jersey_statutes_text,
)

SAMPLE_STATUTES_TEXT = """
NEW JERSEY GENERAL AND PERMANENT STATUTES
(UPDATED THROUGH P.L.2025, c.271)

TITLE 1         ACTS, LAWS AND STATUTES

1:1-1.  General rules of construction
    Words and phrases shall be read with their context and may refer to 1:1-2.

     L.1937, c.188, s.1.

1:1-2  Words and phrases defined.
    Unless otherwise provided, the following words and phrases have the
    meanings herein given to them.

     amended 1948, c.4.

TITLE 52        STATE GOVERNMENT, DEPARTMENTS AND OFFICERS

52:9H 34  Findings, declarations.
    The Legislature finds and declares that public policy benefits from
    economic analyses.

    L.1993, c.149, s.1.

APPENDIX A     EMERGENCY AND TEMPORARY ACTS

App.A:10-1.  Authority to accept grants
    Agencies are authorized to accept grants.

     L.1942, c.226, s.1.
"""

SAMPLE_SOURCE = NewJerseySource(
    source_url="https://pub.njleg.state.nj.us/Statutes/STATUTES-TEXT.zip",
    source_path="sources/us-nj/statute/test/STATUTES.TXT",
    source_format=NEW_JERSEY_STATUTES_TEXT_SOURCE_FORMAT,
    sha256="abc",
)


def test_parse_new_jersey_statutes_text():
    provisions = parse_new_jersey_statutes_text(
        SAMPLE_STATUTES_TEXT,
        source=SAMPLE_SOURCE,
    )

    assert [provision.citation_path for provision in provisions] == [
        "us-nj/statute/title-1",
        "us-nj/statute/chapter-1:1",
        "us-nj/statute/1:1-1",
        "us-nj/statute/1:1-2",
        "us-nj/statute/title-52",
        "us-nj/statute/chapter-52:9h",
        "us-nj/statute/52:9h-34",
        "us-nj/statute/title-app-a",
        "us-nj/statute/chapter-app-a:10",
        "us-nj/statute/app.a:10-1",
    ]
    assert provisions[2].heading == "General rules of construction"
    assert provisions[2].references_to == ("us-nj/statute/1:1-2",)
    assert provisions[2].source_history == ("L.1937, c.188, s.1.",)
    assert provisions[6].citation_label == "52:9H-34"
    assert provisions[8].legal_identifier == "N.J. Stat. Title Appendix A, ch. 10"


def test_parse_new_jersey_statutes_text_skips_repeated_self_header():
    provisions = parse_new_jersey_statutes_text(
        """
TITLE 54A NEW JERSEY GROSS INCOME TAX ACT

54A:2-1  Imposition of tax.
    54A:10A-1. Imposition of tax. There is hereby imposed a tax for each
    taxable year on the New Jersey gross income of every individual.

54A:2-2  Partners and partnerships.
    A partnership as such shall not be subject to tax under this act.
""",
        source=SAMPLE_SOURCE,
    )

    rate_section = next(
        provision
        for provision in provisions
        if provision.citation_path == "us-nj/statute/54a:2-1"
    )
    assert rate_section.body == (
        "There is hereby imposed a tax for each taxable year on the New Jersey "
        "gross income of every individual."
    )
    assert all(
        provision.citation_path != "us-nj/statute/54a:10a-1"
        for provision in provisions
    )


def test_extract_new_jersey_statutes_from_source_dir_writes_complete_artifacts(
    tmp_path,
):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / NEW_JERSEY_STATUTES_TEXT_MEMBER).write_text(
        SAMPLE_STATUTES_TEXT,
        encoding="cp1252",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_new_jersey_statutes(
        store,
        version="2026-05-09",
        source_dir=source_dir,
        source_as_of="2026-05-09",
        expression_date="2026-05-09",
    )

    assert report.coverage.complete is True
    assert report.title_count == 3
    assert report.container_count == 3
    assert report.section_count == 4
    assert report.provisions_written == 10
    assert len(load_source_inventory(report.inventory_path)) == 10
    records = load_provisions(report.provisions_path)
    assert records[2].citation_path == "us-nj/statute/1:1-1"
    assert records[2].metadata is not None
    assert records[2].metadata["references_to"] == ["us-nj/statute/1:1-2"]


REPEATED_HEADER_TEXT = """
TITLE 34        LABOR AND WORKMEN'S COMPENSATION

34:15C-10.4  Applicability.
     15. a. Sections 14 through 20 apply to a private career school.

    L.2021, c.27, s.15.

34:15C-10.  Private career school entrance into school-to-school teach-out agreement.
     16. a. A private career school shall enter into a teach-out agreement.

    L.2021, c.27, s.16.

34:15C-10.6  Approval of private career school to act as eligible transfer institution.
      17. a. The commissioner shall approve a private career school.

    L.2021, c.27, s.17.

34:16-43.  Authority of division and commission.
    5.    The division and the commission are hereby vested with the authority.

         L.1971, c. 272, s. 5.  Amended by L.1979, c. 335; 2017, c.131, s.137.

34:16-43.  Determination of eligibility for extended employment program
    The division and the commission are hereby vested with the authority.

     L.1971, c. 272, s. 5.  Amended by L.1979, c. 335, s. 4, eff. Jan. 21, 1980.

34:16-44.  Inapplicability of requirement for employer's permit
    The provisions relating to the ratio of employees shall not apply.

     L.1973, c. 45, s. 3, eff. Feb. 27, 1973.

TITLE 43        PENSIONS AND RETIREMENT AND UNEMPLOYMENT COMPENSATION

43:17-9  Membership qualifications.
43:17-9  Membership qualifications.
    43:17-9. The membership of such corporation shall consist of the officers.

43:21-7.  Contributions
    Employers shall pay contributions.
"""


def _section(provisions, citation_path):
    return next(
        provision
        for provision in provisions
        if provision.citation_path == citation_path
    )


def test_parse_new_jersey_statutes_text_keeps_later_blocks_under_a_repeated_header():
    provisions = parse_new_jersey_statutes_text(REPEATED_HEADER_TEXT, source=SAMPLE_SOURCE)

    assert [
        provision.citation_path
        for provision in provisions
        if provision.kind == "section"
    ] == [
        "us-nj/statute/34:15c-10.4",
        "us-nj/statute/34:15c-10",
        "us-nj/statute/34:15c-10.6",
        "us-nj/statute/34:16-43",
        "us-nj/statute/34:16-43--variant-2",
        "us-nj/statute/34:16-44",
        "us-nj/statute/43:17-9",
        "us-nj/statute/43:21-7",
    ]
    # A label printed once keeps the plain path, even when it is a misprint.
    teach_out = _section(provisions, "us-nj/statute/34:15c-10")
    assert teach_out.header_occurrence == 1
    assert teach_out.variant_citation_paths == ()
    assert teach_out.body is not None
    assert teach_out.body.startswith("16. a. A private career school")

    # Two same-label headers separated by text: the first header keeps its own
    # (current) body; the second block is its own provision.
    current = _section(provisions, "us-nj/statute/34:16-43")
    assert current.heading == "Authority of division and commission"
    assert current.body is not None
    assert current.body.startswith("5. The division and the commission")
    assert current.source_history == (
        "L.1971, c. 272, s. 5. Amended by L.1979, c. 335; 2017, c.131, s.137.",
    )
    assert current.variant_citation_paths == (
        "us-nj/statute/34:16-43--variant-2",
    )
    stale = _section(provisions, "us-nj/statute/34:16-43--variant-2")
    assert stale.header_occurrence == 2
    assert stale.variant == "variant-2"
    assert stale.canonical_citation_path == "us-nj/statute/34:16-43"
    assert stale.citation_label == "34:16-43"
    assert stale.legal_identifier == "N.J. Stat. § 34:16-43"
    assert stale.heading == "Determination of eligibility for extended employment program"
    assert stale.parent_citation_path == "us-nj/statute/chapter-34:16"
    assert stale.source_history == (
        "L.1971, c. 272, s. 5. Amended by L.1979, c. 335, s. 4, eff. Jan. 21, 1980.",
    )
    assert [
        provision.ordinal for provision in provisions if provision.kind == "section"
    ] == [1, 2, 3, 4, 5, 6, 7, 8]

    # The last section of Title 34 stops at the TITLE 43 header line.
    assert _section(provisions, "us-nj/statute/34:16-44").body == (
        "The provisions relating to the ratio of employees shall not apply."
        "\n\nL.1973, c. 45, s. 3, eff. Feb. 27, 1973."
    )

    # Adjacent repeated self-headers with no text between them stay one section.
    membership = _section(provisions, "us-nj/statute/43:17-9")
    assert membership.header_occurrence == 1
    assert membership.variant_citation_paths == ()
    assert membership.body == (
        "43:17-9. The membership of such corporation shall consist of the officers."
    )


def test_parse_new_jersey_statutes_text_keeps_non_adjacent_repeated_header():
    # The official text heads N.J.S.A. 34:15C-10.5 as "34:15C-10.", a label
    # already used earlier in the chapter. The later block is kept under its
    # own heading instead of being dropped.
    provisions = parse_new_jersey_statutes_text(
        """
TITLE 34        LABOR AND WORKMEN'S COMPENSATION

34:15C-10  Commission shall establish requirements for each workforce investment program.
     13. The commission shall establish such requirements as it deems appropriate.

    L.1989,c.293,s.13.

34:15C-10.4  Applicability.
     15. a. Sections 14 through 20 apply to a private career school.

    L.2021, c.27, s.15.

34:15C-10.  Private career school entrance into school-to-school teach-out agreement.
     16. a. A private career school shall enter into a teach-out agreement.

    L.2021, c.27, s.16.
""",
        source=SAMPLE_SOURCE,
    )

    first = _section(provisions, "us-nj/statute/34:15c-10")
    assert first.heading == (
        "Commission shall establish requirements for each workforce investment program"
    )
    assert first.variant_citation_paths == ("us-nj/statute/34:15c-10--variant-2",)
    second = _section(provisions, "us-nj/statute/34:15c-10--variant-2")
    assert second.heading == (
        "Private career school entrance into school-to-school teach-out agreement"
    )
    assert second.body == (
        "16. a. A private career school shall enter into a teach-out agreement."
        "\n\nL.2021, c.27, s.16."
    )
    assert second.source_history == ("L.2021, c.27, s.16.",)


def test_extract_new_jersey_statutes_records_repeated_header_links(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / NEW_JERSEY_STATUTES_TEXT_MEMBER).write_text(
        REPEATED_HEADER_TEXT,
        encoding="cp1252",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_new_jersey_statutes(
        store,
        version="2026-09-23",
        source_dir=source_dir,
        source_as_of="2026-09-23",
        expression_date="2026-09-23",
        only_title="34",
    )

    assert report.coverage.complete is True
    assert report.section_count == 6
    records = {record.citation_path: record for record in load_provisions(report.provisions_path)}
    assert set(records) == {
        "us-nj/statute/title-34",
        "us-nj/statute/chapter-34:15c",
        "us-nj/statute/chapter-34:16",
        "us-nj/statute/34:15c-10.4",
        "us-nj/statute/34:15c-10",
        "us-nj/statute/34:15c-10.6",
        "us-nj/statute/34:16-43",
        "us-nj/statute/34:16-43--variant-2",
        "us-nj/statute/34:16-44",
    }
    stale = records["us-nj/statute/34:16-43--variant-2"]
    assert stale.source_id == "34:16-43--variant-2"
    assert stale.identifiers == {
        "new_jersey:title": "34",
        "new_jersey:chapter": "16",
        "new_jersey:section": "34:16-43",
        "new_jersey:variant": "variant-2",
    }
    assert stale.metadata is not None
    assert stale.metadata["variant"] == "variant-2"
    assert stale.metadata["canonical_citation_path"] == "us-nj/statute/34:16-43"
    assert "variant_citation_paths" not in stale.metadata
    current = records["us-nj/statute/34:16-43"]
    assert "new_jersey:variant" not in current.identifiers
    assert current.metadata is not None
    assert current.metadata["variant_citation_paths"] == [
        "us-nj/statute/34:16-43--variant-2"
    ]
    assert "variant" not in current.metadata
    assert "canonical_citation_path" not in current.metadata
    # The Title 34 scope's last section does not absorb the TITLE 43 header.
    last = records["us-nj/statute/34:16-44"]
    assert last.body is not None
    assert "TITLE" not in last.body
    assert last.body.endswith("L.1973, c. 45, s. 3, eff. Feb. 27, 1973.")


def test_parse_new_jersey_statutes_text_ends_sections_at_title_headers():
    provisions = parse_new_jersey_statutes_text(
        SAMPLE_STATUTES_TEXT,
        source=SAMPLE_SOURCE,
    )

    # Before the fix, 1:1-2 ended with "TITLE 52 STATE GOVERNMENT, ..." and
    # 52:9h-34 with "APPENDIX A EMERGENCY AND TEMPORARY ACTS".
    assert _section(provisions, "us-nj/statute/1:1-2").body == (
        "Unless otherwise provided, the following words and phrases have the "
        "meanings herein given to them.\n\namended 1948, c.4."
    )
    assert _section(provisions, "us-nj/statute/52:9h-34").body == (
        "The Legislature finds and declares that public policy benefits from "
        "economic analyses.\n\nL.1993, c.149, s.1."
    )
    assert all(
        provision.body is None for provision in provisions if provision.kind == "title"
    )


def test_parse_new_jersey_statutes_text_keeps_title_preamble_on_the_title():
    # The official text prints a revision note between the APPENDIX A header
    # and its first section. It belongs to the appendix, not to the last
    # section of the preceding title.
    provisions = parse_new_jersey_statutes_text(
        """
TITLE 59        CLAIMS AGAINST PUBLIC ENTITIES

59:13-10  Short title.
    This act shall be known as the "Contractual Liability Act."

    L.1979, c. 222, s. 1.

APPENDIX A     EMERGENCY AND TEMPORARY ACTS

    Revision Note. The acts contained in this appendix have been compiled
    without change in wording.

    They have been here arranged for convenience of reference.

App.A:1-1  Short title.
    This act may be cited as the Emergency Act.

    L.1942, c.251, s.1.
""",
        source=SAMPLE_SOURCE,
    )

    assert _section(provisions, "us-nj/statute/59:13-10").body == (
        'This act shall be known as the "Contractual Liability Act."'
        "\n\nL.1979, c. 222, s. 1."
    )
    appendix = next(
        provision
        for provision in provisions
        if provision.citation_path == "us-nj/statute/title-app-a"
    )
    assert appendix.body == (
        "Revision Note. The acts contained in this appendix have been compiled "
        "without change in wording.\n\n"
        "They have been here arranged for convenience of reference."
    )
    title_59 = next(
        provision
        for provision in provisions
        if provision.citation_path == "us-nj/statute/title-59"
    )
    assert title_59.body is None


def test_parse_new_jersey_statutes_text_folds_a_header_reprinted_mid_section():
    # The official text reprints "52:27D-18.5  Extension of certification
    # renewal periods." between subsections c. and d. of the one section; the
    # first block has no source-history line yet, so it is one section.
    provisions = parse_new_jersey_statutes_text(
        """
TITLE 52        STATE GOVERNMENT, DEPARTMENTS AND OFFICERS

52:27D-18.5  Extension of certification renewal periods.
\t2.\tThe following certification renewal periods shall be extended by one year.

\tc.\tThe renewal period for registered municipal clerk certificates shall be extended.
52:27D-18.5  Extension of certification renewal periods.

\td.\tThe renewal period for county finance officer certificates shall be extended.

\tL.2020, c.34, s.2.

52:27D-18.6  Extension of term of acting municipal clerk.
\t3.\tA person appointed to serve as an acting municipal clerk may continue.

\tL.2020, c.34, s.3.
""",
        source=SAMPLE_SOURCE,
    )

    sections = [provision for provision in provisions if provision.kind == "section"]
    assert [provision.citation_path for provision in sections] == [
        "us-nj/statute/52:27d-18.5",
        "us-nj/statute/52:27d-18.6",
    ]
    extension = sections[0]
    assert extension.body == (
        "2. The following certification renewal periods shall be extended by one year."
        "\n\nc. The renewal period for registered municipal clerk certificates shall "
        "be extended.\n\nd. The renewal period for county finance officer certificates "
        "shall be extended.\n\nL.2020, c.34, s.2."
    )
    assert extension.variant_citation_paths == ()
    assert extension.source_history == ("L.2020, c.34, s.2.",)
    assert [provision.ordinal for provision in sections] == [1, 2]


def test_parse_new_jersey_statutes_text_keeps_same_heading_block_after_history():
    # A same-label, same-heading header after a block that already closed with
    # its source-history line starts a separate block (the official text prints
    # sections 3 and 4 of P.L.2006, c.63 both as "45:15-16.52 Applicability of act.").
    provisions = parse_new_jersey_statutes_text(
        """
TITLE 45        PROFESSIONS AND OCCUPATIONS

45:15-16.52  Applicability of act.

\t3.\tThis act shall apply to timeshare plans.

\tL.2006, c.63, s.3.

45:15-16.52  Applicability of act.

\t4. a.  This act shall not apply to any of the following plans.

\tL.2006, c.63, s.4.
""",
        source=SAMPLE_SOURCE,
    )

    first = _section(provisions, "us-nj/statute/45:15-16.52")
    assert first.body == "3. This act shall apply to timeshare plans.\n\nL.2006, c.63, s.3."
    assert first.variant_citation_paths == ("us-nj/statute/45:15-16.52--variant-2",)
    second = _section(provisions, "us-nj/statute/45:15-16.52--variant-2")
    assert second.body == (
        "4. a. This act shall not apply to any of the following plans."
        "\n\nL.2006, c.63, s.4."
    )


STATUS_TEXT = """
TITLE 43        PENSIONS AND RETIREMENT AND UNEMPLOYMENT COMPENSATION

43:3B-2  Adjustment of monthly retirement allowance.
    The allowance shall not be decreased, increased, revoked or repealed except
    as otherwise provided in this act.

    L.1958, c. 143, s. 2.

43:6A-45  Repeals.
    The following acts and parts of acts are repealed: P.L.1948, c. 391.

    L.1973, c. 140, s. 45.

43:18-3  Trustees; filling vacancy.
    A trustee shall serve in the place of the trustee whose term shall have then expired.

    L.1938, c. 24, s. 3.

43:21-3  Benefits.
    20% of his weekly benefit rate (fractional part of a dollar omitted).

    L.1936, c.270, s.3.

43:21-14a  ZIP Code reporting.
    Each employer shall report the ZIP Code where the employee regularly works.

    L. 1987, c. 450, s. 1; per s.4, expired April 19, 1993.

34:13B-6  Expired labor contracts; written notice of desired changes required.
    Whenever a labor contract has expired, a party shall give written notice.

    L.1946, c. 38, s. 6.

26:2H-12.2  Repealed by L.2005,c.83,s.20.

46:38-16  Custodial gift.
    A person may make a gift of a security to a minor.

    L. 1963, c. 177, s.4; repealed R.S. 46:38A-57 (effective July 1, 2007).

17:20-1  Definitions.
    As used in this chapter, the following terms are defined.

    Amended 1989,c.264,s.1; repealed in part (see N.J.S.17B:36-3b).

54:10A-5.1  Surtax.
    A surtax is imposed for accounting periods ending on or before June 30, 1994.

    L.1986, c.140, s.1; per s.5 as amended by s.7 of 1988, c.106, section expired for accounting periods ending after June 30, 1994.
"""


def test_parse_new_jersey_statutes_text_reads_status_from_heading_and_history_only():
    provisions = parse_new_jersey_statutes_text(STATUS_TEXT, source=SAMPLE_SOURCE)

    statuses = {
        provision.citation_label: provision.status
        for provision in provisions
        if provision.kind == "section"
    }
    assert statuses == {
        # Live law that only uses the words in its text or heading.
        "43:3B-2": None,
        "43:6A-45": None,
        "43:18-3": None,
        "43:21-3": None,
        "34:13B-6": None,
        "17:20-1": None,
        # A status-note heading, or a repeal or expiration in the final clause
        # of the section's source history.
        "43:21-14a": "expired",
        "26:2H-12.2": "repealed",
        "46:38-16": "repealed",
        "54:10A-5.1": "expired",
    }
