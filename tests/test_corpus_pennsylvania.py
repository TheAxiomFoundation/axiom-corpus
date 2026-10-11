from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.pennsylvania import (
    PENNSYLVANIA_SOURCE_FORMAT,
    extract_pennsylvania_statutes,
    parse_pennsylvania_title_html,
)
from axiom_corpus.corpus.state_adapters.pennsylvania_unconsolidated import (
    PENNSYLVANIA_UNCONSOLIDATED_SOURCE_FORMAT,
    extract_pennsylvania_unconsolidated_statutes,
    parse_pennsylvania_unconsolidated_article_html,
)

SAMPLE_PENNSYLVANIA_TITLE_HTML = """<!doctype html>
<html>
<body>
<div class="BodyContainer">
<div class="Comment">72cc</div>
<p>TABLE OF CONTENTS</p>
<p>TITLE 72</p>
<p>TAXATION AND FISCAL AFFAIRS</p>

<div class="Comment">72c3101h</div>
<p>CHAPTER 31</p>
<p>MICROENTERPRISE ASSISTANCE</p>
<p>SUBCHAPTER B</p>
<p>MICROENTERPRISE LOAN PROGRAMS</p>

<div class="Comment">72c3116s</div>
<p><b>§ 3116.  Microenterprise loans.</b></p>
<p><b>(a)  Loan issuance.--</b>An administrative entity may issue a loan.</p>
<p>The department shall publish guidelines under
<a href="/statutes/consolidated/view-statute?txtType=HTM&amp;ttl=72&amp;sctn=3121&amp;iFrame=true">section 3121</a>.</p>
<p><b>Cross References.  </b>Section 3116 is referred to in section 3121.</p>
<p><b>History.--</b>Act 2004-32, effective 60 days after July 7, 2004.</p>

<div class="Comment">72c3117s</div>
<p><b>§ 3117.  Administration of program.</b></p>
<p>The department shall administer the program.</p>
</div>
</body>
</html>
"""

SAMPLE_PENNSYLVANIA_SINGLE_DIGIT_TITLE_HTML = """<!doctype html>
<html>
<body>
<div class="BodyContainer">
<div class="Comment">01cc</div>
<p>TABLE OF CONTENTS</p>
<p>TITLE 1</p>
<p>GENERAL PROVISIONS</p>
<div class="Comment">01c101h</div>
<p>CHAPTER 1</p>
<p>SHORT TITLE, FORM OF CITATION AND</p>
<p>EFFECTIVE DATE</p>
<div class="Comment">01c101s</div>
<p><b>§ 101. Short title.</b></p>
<p>This title shall be known as the Consolidated Statutes.</p>
</div>
</body>
</html>
"""

SAMPLE_PENNSYLVANIA_UNCONSOLIDATED_ARTICLE_HTML = """<!doctype html>
<html>
<head><meta name="revised" content="2025-05-29 10:42:33 AM"></head>
<body>
<div class="BodyContainer">
<div class="Comment">19710002u301h</div>
<p>ARTICLE III</p>
<p>PERSONAL INCOME TAX</p>
<div class="Comment">19710002u301s</div>
<p>Section 301. Definitions.--The following words have the meanings given.</p>
<p>(301 amended July 7, 2005, P.L.149, No.40)</p>
<div class="Comment">19710002u302h</div>
<p>PART II</p>
<p>IMPOSITION OF TAX</p>
<div class="Comment">19710002u302s</div>
<p>Section 302. Imposition of Tax.--(a) Every resident individual shall pay a tax
at the rate of three and seven hundredths per cent.</p>
<p>(b) Every nonresident individual shall pay the same rate.</p>
<p>(302 amended Dec. 14, 2023, P.L.  , No.64)</p>
<div class="Comment">19710002u302v</div>
<p><b>Compiler's Note:</b> Section 2(1) of Act 64 of 2023 applies to tax years.</p>
<div class="Comment">19710002u302.1s</div>
<p>Section 302.1. Rate Changes Occurring During the Taxable Year.--The rate shall
be prorated.</p>
</div>
</body>
</html>
"""

SAMPLE_PENNSYLVANIA_FISCAL_CODE_ARTICLE_HTML = """<!doctype html>
<html>
<head><meta name="revised" content="2025-12-03 03:56:34 PM"></head>
<body>
<div class="BodyContainer">
<div class="Comment">19290176u1601-W.2h</div>
<p>ARTICLE XVI-W.2</p>
<p>WORKING PENNSYLVANIANS TAX CREDIT</p>
<div class="Comment">19290176u1601-W.2s</div>
<p>Section 1601-W.2. Scope of article.</p>
<p>This article relates to the working Pennsylvanians tax credit.</p>
<p>(1601-W.2 added Nov. 12, 2025, P.L.156, No.45)</p>
<div class="Comment">19290176u1603-W.2s</div>
<p>Section 1603-W.2. Working Pennsylvanians tax credit.--The tax credit shall
be equal to 10% of the Federal earned income tax credit.</p>
<p>(1603-W.2 added Nov. 12, 2025, P.L.156, No.45)</p>
<div class="Comment">19290176u1606-W.2s</div>
<p>Section 1606-W.2. Applicability.--This article shall apply to taxable years
beginning after December 31, 2024.</p>
<p>(1606-W.2 added Nov. 12, 2025, P.L.156, No.45)</p>
</div>
</body>
</html>
"""

SAMPLE_PENNSYLVANIA_MULTILINE_ARTICLE_HEADING_HTML = """<!doctype html>
<html>
<body>
<div class="BodyContainer">
<div class="Comment">19290176u1601-Wh</div>
<p>ARTICLE XVI-W</p>
<p>PENNSYLVANIA CHILD AND DEPENDENT</p>
<p>CARE ENHANCEMENT TAX CREDIT PROGRAM</p>
<p>(Art. added Dec. 13, 2023, P.L.251, No.34)</p>
<p><b>Compiler's Note:</b> See section 34 of Act 34 of 2023.</p>
<div class="Comment">19290176u1601-Ws</div>
<p>Section 1601-W. Scope of article.</p>
<p>This article relates to the tax credit program.</p>
</div>
</body>
</html>
"""


def test_parse_pennsylvania_title_html_extracts_real_comment_marker_structure():
    provisions = parse_pennsylvania_title_html(SAMPLE_PENNSYLVANIA_TITLE_HTML, title=72)

    assert [provision.kind for provision in provisions] == [
        "title",
        "chapter",
        "section",
        "section",
    ]
    title, chapter, section, next_section = provisions
    assert title.citation_path == "us-pa/statute/title-72"
    assert title.heading == "Taxation and Fiscal Affairs"
    assert chapter.citation_path == "us-pa/statute/title-72/chapter-31"
    assert chapter.heading == "Microenterprise Assistance"
    assert section.citation_path == "us-pa/statute/72/3116"
    assert section.heading == "Microenterprise loans"
    assert section.parent_citation_path == "us-pa/statute/title-72/chapter-31"
    assert section.body is not None
    assert "Loan issuance" in section.body
    assert "History.-- Act 2004-32" in section.body
    assert section.references_to == ("us-pa/statute/72/3121",)
    assert section.source_history == (
        "History.-- Act 2004-32, effective 60 days after July 7, 2004.",
    )
    assert section.notes == ("Cross References. Section 3116 is referred to in section 3121.",)
    assert next_section.citation_path == "us-pa/statute/72/3117"


def test_parse_pennsylvania_title_html_handles_zero_padded_single_digit_markers():
    provisions = parse_pennsylvania_title_html(
        SAMPLE_PENNSYLVANIA_SINGLE_DIGIT_TITLE_HTML,
        title=1,
    )

    assert [provision.citation_path for provision in provisions] == [
        "us-pa/statute/title-1",
        "us-pa/statute/title-1/chapter-1",
        "us-pa/statute/1/101",
    ]
    assert provisions[1].heading == "Short Title, Form of Citation and Effective Date"
    assert provisions[2].legal_identifier == "1 Pa.C.S. § 101"


def test_parse_pennsylvania_unconsolidated_article_extracts_complete_section_bodies():
    provisions = parse_pennsylvania_unconsolidated_article_html(
        SAMPLE_PENNSYLVANIA_UNCONSOLIDATED_ARTICLE_HTML,
        act_year=1971,
        act_number=2,
        article=3,
    )

    assert [provision.kind for provision in provisions] == [
        "act",
        "article",
        "section",
        "section",
        "section",
    ]
    assert provisions[1].heading == "Personal Income Tax"
    rate = provisions[3]
    assert rate.citation_path == "us-pa/statute/act-1971-2/article-3/section-302"
    assert rate.legal_identifier == "Tax Reform Code of 1971 § 302 (72 P.S. § 7302)"
    assert rate.heading == "Imposition of Tax"
    assert rate.body is not None
    assert "three and seven hundredths per cent" in rate.body
    assert "Compiler's Note" in rate.body
    assert "PART II" not in provisions[2].body
    assert rate.source_history == ("(302 amended Dec. 14, 2023, P.L., No.64)",)
    assert rate.notes == (
        "Compiler's Note: Section 2(1) of Act 64 of 2023 applies to tax years.",
    )


def test_parse_pennsylvania_unconsolidated_alphanumeric_article():
    provisions = parse_pennsylvania_unconsolidated_article_html(
        SAMPLE_PENNSYLVANIA_FISCAL_CODE_ARTICLE_HTML,
        act_year=1929,
        act_number=176,
        article="16W.2",
        act_name="The Fiscal Code",
    )

    assert [provision.citation_path for provision in provisions] == [
        "us-pa/statute/act-1929-176",
        "us-pa/statute/act-1929-176/article-16w.2",
        "us-pa/statute/act-1929-176/article-16w.2/section-1601-w.2",
        "us-pa/statute/act-1929-176/article-16w.2/section-1603-w.2",
        "us-pa/statute/act-1929-176/article-16w.2/section-1606-w.2",
    ]
    assert provisions[0].legal_identifier == "The Fiscal Code (Act 176 of 1929)"
    assert provisions[1].legal_identifier == "The Fiscal Code, Article XVI-W.2"
    credit = provisions[3]
    assert credit.legal_identifier == "The Fiscal Code § 1603-W.2"
    assert credit.heading == "Working Pennsylvanians tax credit"
    assert credit.body is not None
    assert "10% of the Federal earned income tax credit" in credit.body
    assert credit.source_history == ("(1603-W.2 added Nov. 12, 2025, P.L.156, No.45)",)


def test_parse_pennsylvania_unconsolidated_multiline_article_heading():
    provisions = parse_pennsylvania_unconsolidated_article_html(
        SAMPLE_PENNSYLVANIA_MULTILINE_ARTICLE_HEADING_HTML,
        act_year=1929,
        act_number=176,
        article="16W",
        act_name="The Fiscal Code",
    )

    assert provisions[1].heading == (
        "Pennsylvania Child And Dependent Care Enhancement Tax Credit Program"
    )


def test_extract_pennsylvania_unconsolidated_article_writes_complete_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "article-3.html").write_text(
        SAMPLE_PENNSYLVANIA_UNCONSOLIDATED_ARTICLE_HTML,
        encoding="utf-8",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_pennsylvania_unconsolidated_statutes(
        store,
        version="2026-07-16-pit-west",
        act_year=1971,
        act_number=2,
        article=3,
        source_dir=source_dir,
        source_as_of="2025-05-29",
        expression_date="2025-05-29",
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 1
    assert report.section_count == 3
    assert report.provisions_written == 5
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    assert inventory[2].source_format == PENNSYLVANIA_UNCONSOLIDATED_SOURCE_FORMAT
    assert records[3].citation_path.endswith("/article-3/section-302")
    assert records[3].identifiers is not None
    assert records[3].identifiers["pennsylvania:purdons"] == "72 P.S. § 7302"
    assert records[3].source_path is not None
    assert records[3].source_path.endswith(
        "/pennsylvania-unconsolidated-statutes-html/act-1971-2/article-3.html"
    )


def test_extract_pennsylvania_fiscal_code_article_writes_complete_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "article-16w.2.html").write_text(
        SAMPLE_PENNSYLVANIA_FISCAL_CODE_ARTICLE_HTML,
        encoding="utf-8",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_pennsylvania_unconsolidated_statutes(
        store,
        version="2026-07-26-pa-refundable-tax-credits",
        act_year=1929,
        act_number=176,
        article="16W.2",
        act_name="The Fiscal Code",
        source_dir=source_dir,
        source_as_of="2025-12-03",
        expression_date="2025-12-03",
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 1
    assert report.section_count == 3
    assert report.provisions_written == 5
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    assert inventory[1].citation_path.endswith("/article-16w.2")
    assert inventory[1].source_url is not None
    assert "chpt=16W.2" in inventory[1].source_url
    assert records[3].citation_path.endswith("/article-16w.2/section-1603-w.2")
    assert records[3].identifiers is not None
    assert "pennsylvania:purdons" not in records[3].identifiers
    assert records[3].source_path is not None
    assert records[3].source_path.endswith(
        "/pennsylvania-unconsolidated-statutes-html/"
        "act-1929-176/article-16w.2.html"
    )


def test_extract_multiple_pennsylvania_fiscal_code_articles_without_duplicate_act(
    tmp_path,
):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "article-16w.html").write_text(
        SAMPLE_PENNSYLVANIA_FISCAL_CODE_ARTICLE_HTML.replace(
            "XVI-W.2", "XVI-W"
        ).replace("-W.2", "-W"),
        encoding="utf-8",
    )
    (source_dir / "article-16w.2.html").write_text(
        SAMPLE_PENNSYLVANIA_FISCAL_CODE_ARTICLE_HTML,
        encoding="utf-8",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_pennsylvania_unconsolidated_statutes(
        store,
        version="2026-07-26-pa-refundable-tax-credits",
        act_year=1929,
        act_number=176,
        articles=("16W", "16W.2"),
        act_name="The Fiscal Code",
        source_dir=source_dir,
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 2
    assert report.section_count == 6
    assert report.provisions_written == 9
    assert len(report.source_paths) == 2
    records = load_provisions(report.provisions_path)
    assert sum(record.kind == "act" for record in records) == 1
    assert {record.source_as_of for record in records} == {
        "2025-12-03",
    }
    assert report.provisions_path.name == (
        "2026-07-26-pa-refundable-tax-credits-us-pa-act-1929-176-"
        "articles-16w-16w.2.jsonl"
    )


def test_extract_pennsylvania_statutes_from_source_dir_writes_complete_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "title-72.html").write_text(
        SAMPLE_PENNSYLVANIA_TITLE_HTML,
        encoding="utf-8",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_pennsylvania_statutes(
        store,
        version="2026-05-08",
        source_dir=source_dir,
        source_as_of="2026-05-08",
        expression_date="2026-05-08",
        only_title=72,
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 1
    assert report.section_count == 2
    assert report.provisions_written == 4
    assert len(report.source_paths) == 1
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    assert inventory[0].source_format == PENNSYLVANIA_SOURCE_FORMAT
    assert records[2].citation_path == "us-pa/statute/72/3116"
    assert records[2].metadata is not None
    assert records[2].metadata["references_to"] == ["us-pa/statute/72/3121"]
    assert records[2].source_path is not None
    assert records[2].source_path.endswith(
        "/pennsylvania-consolidated-statutes-html/title-72.html"
    )
