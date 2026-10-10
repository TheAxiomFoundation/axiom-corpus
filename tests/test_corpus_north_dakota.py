import fitz

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.north_dakota import (
    apply_north_dakota_rate_schedule_overlay,
    extract_north_dakota_code,
    parse_north_dakota_chapter_pdf,
    parse_north_dakota_fiduciary_rate_schedule,
    parse_north_dakota_index_html,
    parse_north_dakota_individual_rate_schedules,
)

SAMPLE_CODE_TEXT = """CHAPTER 57-38
INCOME TAX
57-38-30.2. Surtax on income.
Repealed by S.L. 1975, ch. 476, § 2.
57-38-30.3. Individual, estate, and trust income tax.
1.
A tax is hereby imposed for each taxable year upon income earned or received in that
taxable year by every resident and nonresident individual, estate, and trust.
a.
Single, other than head of household or surviving spouse.
If North Dakota taxable income is:
Over
Not over
The tax is equal to
Of amount over
$0
$44,725
$0.00 + 0.00%
$0
b.
Married filing jointly and surviving spouse.
If North Dakota taxable income is:
$0 | $74,750 | $0.00 + 0.00% | $0
c.
Married filing separately.
If North Dakota taxable income is:
$0 | $37,375 | $0.00 + 0.00% | $0
d.
Head of household.
If North Dakota taxable income is:
$0 | $59,950 | $0.00 + 0.00% | $0
e.
Estates and trusts.
If North Dakota taxable income is:
$0 | $3,000 | $0.00 + 0.00% | $0
f.
For an individual who is not a resident of this state for the entire year, the tax is
equal to the tax otherwise computed under this subsection multiplied by a fraction.
g.
The tax commissioner shall prescribe new rate schedules that apply in lieu of the
schedules set forth in subdivisions a through e.
2.
North Dakota taxable income means federal taxable income adjusted as provided here.
57-38-30.4. Income tax credit for comprehensive health association assessments.
Repealed by S.L. 2009, ch. 545, § 32.
57-38-30.4. This sentence-starting citation is not another section heading.
"""


def _text_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    result = page.insert_textbox(fitz.Rect(36, 36, 576, 756), text, fontsize=8)
    assert result > 0
    return document.tobytes()


def _individual_schedule_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((24, 36), "2026 Forms ND-1 and ND-EZ Tax Rate Schedules", fontsize=9)
    left = """Single
If North Dakota taxable income is:
Over But not over Your tax is:
$ 0 $ 49,575 $...... 0.00 + 0.00% of North Dakota taxable income
49,575 250,400 0.00 + 1.95% of amount over $ 49,575
250,400 3,916.09 + 2.50% of amount over 250,400
Married filing separately
If North Dakota taxable income is:
Over But not over Your tax is:
$ 0 $ 41,400 $...... 0.00 + 0.00% of North Dakota taxable income
41,400 152,425 0.00 + 1.95% of amount over $ 41,400
152,425 2,164.99 + 2.50% of amount over 152,425
"""
    right = """Married filing jointly and Qualifying surviving spouse
If North Dakota taxable income is:
Over But not over Your tax is:
$ 0 $ 82,800 $...... 0.00 + 0.00% of North Dakota taxable income
82,800 304,850 0.00 + 1.95% of amount over $ 82,800
304,850 4,329.98 + 2.50% of amount over 304,850
Head of household
If North Dakota taxable income is:
Over But not over Your tax is:
$ 0 $ 66,400 $...... 0.00 + 0.00% of North Dakota taxable income
66,400 277,600 0.00 + 1.95% of amount over $ 66,400
277,600 4,118.40 + 2.50% of amount over 277,600
"""
    page.insert_textbox(fitz.Rect(38, 70, 296, 500), left, fontsize=8)
    page.insert_textbox(fitz.Rect(317, 70, 590, 500), right, fontsize=8)
    return document.tobytes()


def _fiduciary_schedule_pdf() -> bytes:
    return _text_pdf(
        """2026 Tax Rate Schedule
Estates and Trusts
If North Dakota taxable income is:
Over But not over Your tax is:
$ 0 $ 3,300 $ 0.00 + 0.00% of North Dakota taxable income
3,300 11,900 0.00 + 1.95% of amount over $ 3,300
11,900 167.70 + 2.50% of amount over 11,900
2026 Form 38-ES
SFN 28723
"""
    )


def test_parse_north_dakota_chapter_pdf_writes_body_bearing_sections():
    sections = parse_north_dakota_chapter_pdf(_text_pdf(SAMPLE_CODE_TEXT))

    assert [section.section for section in sections] == [
        "57-38-30.2",
        "57-38-30.3",
        "57-38-30.4",
    ]
    assert sections[0].status == "repealed"
    assert sections[1].citation_path == "us-nd/statute/57/57-38-30.3"
    assert sections[1].body.startswith("1.\nA tax is hereby imposed")


def test_parse_north_dakota_index_html_extracts_ordered_inventory():
    html = """<a href="t57c38.pdf">57-38-30.2</a>
<a href="t57c38.pdf">57-38-30.3</a>
<a href="t57c38.pdf">57-38-30.4</a>"""

    assert parse_north_dakota_index_html(html) == (
        "57-38-30.2",
        "57-38-30.3",
        "57-38-30.4",
    )


def test_parse_and_apply_north_dakota_2026_rate_schedules():
    section = parse_north_dakota_chapter_pdf(_text_pdf(SAMPLE_CODE_TEXT))[1]
    individual = parse_north_dakota_individual_rate_schedules(_individual_schedule_pdf())
    fiduciary = parse_north_dakota_fiduciary_rate_schedule(_fiduciary_schedule_pdf())

    current = apply_north_dakota_rate_schedule_overlay(
        section,
        schedules=(*individual, fiduciary),
        tax_year=2026,
    )

    assert "$0 | $49,575 | $0.00 + 0.00% | $0" in current.body
    assert "$250,400 |  | $3,916.09 + 2.50% | $250,400" in current.body
    assert "$0 | $3,300 | $0.00 + 0.00% | $0" in current.body
    assert "$44,725" not in current.body
    assert current.metadata == {
        "rate_schedule_overlay": {
            "tax_year": 2026,
            "authority": "N.D.C.C. § 57-38-30.3(1)(g)",
            "subdivisions": ["a", "b", "c", "d", "e"],
        }
    }


def test_extract_north_dakota_code_writes_complete_overlay_provenance(tmp_path):
    source_dir = tmp_path / "source"
    code_dir = source_dir / "north-dakota-century-code"
    tax_dir = source_dir / "north-dakota-tax-commissioner"
    code_dir.mkdir(parents=True)
    tax_dir.mkdir()
    (code_dir / "chapter-57-38.html").write_text(
        """<h1>Chapter 57-38</h1><p>Income Tax</p>
<a href="chapter-57-38.pdf">57-38-30.2</a>
<a href="chapter-57-38.pdf">57-38-30.3</a>
<a href="chapter-57-38.pdf">57-38-30.4</a>""",
        encoding="utf-8",
    )
    (code_dir / "chapter-57-38.pdf").write_bytes(_text_pdf(SAMPLE_CODE_TEXT))
    (tax_dir / "2026-form-nd-1es.pdf").write_bytes(_individual_schedule_pdf())
    (tax_dir / "2026-form-38-es.pdf").write_bytes(_fiduciary_schedule_pdf())
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_north_dakota_code(
        store,
        version="2026-07-16-pit-central",
        source_dir=source_dir,
        source_as_of="2026-07-16",
        expression_date="2026-07-16",
        only_title="57-38",
        tax_year=2026,
    )

    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    target = next(
        record for record in records if record.citation_path == "us-nd/statute/57/57-38-30.3"
    )
    assert report.coverage.complete is True
    assert report.section_count == 3
    assert len(inventory) == len(records) == 4
    assert target.body is not None
    assert "$49,575" in target.body
    assert target.parent_citation_path == "us-nd/statute/57"
    assert target.metadata is not None
    assert [row["role"] for row in target.metadata["source_components"]] == [
        "codified_base",
        "operative_2026_individual_rate_schedules",
        "operative_2026_fiduciary_rate_schedule",
    ]
