from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import _canonical_state_statute_adapter
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.mississippi import (
    MISSISSIPPI_DOR_RATES_URL,
    MISSISSIPPI_HB1_HTML_URL,
    MISSISSIPPI_HB1_PDF_URL,
    MISSISSIPPI_HB1_SIGNING_URL,
    extract_mississippi_income_tax_statute,
    parse_mississippi_dor_rate_guidance,
    parse_mississippi_hb1_section_27_7_5,
)

SAMPLE_HB1_HTML = """<!doctype html><html><body>
<p>BE IT ENACTED BY THE LEGISLATURE OF THE STATE OF MISSISSIPPI:</p>
<p><b>SECTION 1.</b> Section 27-7-5, Mississippi Code of 1972, is amended as follows:</p>
<p>27-7-5. (1) (a) A tax is assessed at the following rates:</p>
<p>(b) (i) For calendar year 2023 and all calendar years thereafter, there shall be no
tax levied on taxable income through Ten Thousand Dollars ($10,000.00).</p>
<p>3. For calendar year 2026<b>&nbsp;*&nbsp;*&nbsp;*</b><s><span> and all calendar years
thereafter</span></s>, on such taxable income, the rate shall be four percent (4%)<s>.</s><u>;</u></p>
<p><u>4. For calendar year 2027, on such taxable income, the rate shall be three and
three-quarters percent (3.75%);</u></p>
<p><u>5. For calendar year 2028, on such taxable income, the rate shall be three and
one-half percent (3.5%);</u></p>
<p><u>6. For calendar year 2029, on such taxable income, the rate shall be three and
one-quarter percent (3.25%); and</u></p>
<p><u>7. For calendar year 2030 and all calendar years thereafter, except as otherwise
provided in Section 2 of this act, the rate shall be three percent (3%).</u></p>
<p>(2) An S corporation shall not be subject to the income tax imposed under this section.</p>
<p><b><u>SECTION 2.</u></b> Further annual reductions.</p>
<p><b>SECTION <u>30</u>.</b> Sections 1 through 13 of this act shall take effect and be
in force from and after July 1, 2025.</p>
</body></html>"""

SAMPLE_SIGNING_HTML = """<!doctype html><html><body>
<p>March 27, 2025</p>
<p>Governor Tate Reeves today signed historic legislation. House Bill 1 is the
Build Up Mississippi Act.</p>
</body></html>"""

SAMPLE_DOR_HTML = """<!doctype html><html><body>
<h2>Tax Rates</h2>
<p>0% on the first $10,000 of taxable income.</p>
<p>Tax Rates for Tax years 2025-2027:</p>
<table><tr><td>Tax Year 2026</td><td>Excess of $10,000 of Taxable Income is taxed @ 4%</td></tr></table>
</body></html>"""


def test_parse_mississippi_hb1_extracts_complete_enacted_section():
    body, effective_date = parse_mississippi_hb1_section_27_7_5(SAMPLE_HB1_HTML)

    assert body.startswith("(1) (a)")
    assert "For calendar year 2026, on such taxable income" in body
    assert "2026 and all calendar years thereafter" not in body
    assert "For calendar year 2030 and all calendar years thereafter" in body
    assert "An S corporation" in body
    assert "Further annual reductions" not in body
    assert effective_date == "2025-07-01"


def test_parse_mississippi_dor_rate_guidance_extracts_2026_rate():
    rate = parse_mississippi_dor_rate_guidance(SAMPLE_DOR_HTML, tax_year=2026)

    assert rate.tax_year == 2026
    assert rate.zero_rate_threshold == 10_000
    assert rate.excess_rate_percent == "4"


def test_extract_mississippi_writes_complete_bounded_scope(tmp_path):
    source_dir = tmp_path / "source"
    fixtures = {
        "mississippi-legislature/2025-hb-1-sg.html": SAMPLE_HB1_HTML.encode(),
        "mississippi-legislature/2025-hb-1-sg.pdf": b"%PDF-1.7\nfixture",
        "mississippi-governor/2025-hb-1-signing.html": SAMPLE_SIGNING_HTML.encode(),
        "mississippi-department-of-revenue/2026-individual-income-tax-rates.html": SAMPLE_DOR_HTML.encode(),
    }
    for relative_path, data in fixtures.items():
        path = source_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_mississippi_income_tax_statute(
        store,
        version="2026-07-16-pit-central",
        source_dir=source_dir,
        source_as_of="2026-07-16",
        expression_date="2026-07-16",
        only_title="27-7-5",
    )

    assert report.coverage.complete is True
    assert report.title_count == 1
    assert report.container_count == 2
    assert report.section_count == 1
    assert report.provisions_written == 3
    assert len(report.source_paths) == 4
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-ms/statute/title-27",
        "us-ms/statute/title-27/chapter-7",
        "us-ms/statute/27-7-5",
    ]
    assert len(inventory) == 3
    section = records[-1]
    assert section.parent_citation_path == "us-ms/statute/title-27/chapter-7"
    assert section.metadata is not None
    assert section.metadata["operative_rate"] == {
        "tax_year": 2026,
        "zero_rate_percent": "0",
        "zero_rate_threshold": 10_000,
        "excess_rate_percent": "4",
    }
    assert section.metadata["law_vintage"]["signed_date"] == "2025-03-27"
    assert section.metadata["law_vintage"]["effective_date"] == "2025-07-01"
    assert [row["role"] for row in section.metadata["source_components"]] == [
        "enacted_section_text",
        "official_bill_pdf",
        "enactment_confirmation",
        "operative_rate",
    ]


def test_mississippi_source_constants_are_official_government_urls():
    assert MISSISSIPPI_HB1_HTML_URL.startswith("https://billstatus.ls.state.ms.us/")
    assert MISSISSIPPI_HB1_PDF_URL.startswith("https://billstatus.ls.state.ms.us/")
    assert MISSISSIPPI_HB1_SIGNING_URL.startswith("https://governorreeves.ms.gov/")
    assert MISSISSIPPI_DOR_RATES_URL.startswith("https://www.dor.ms.gov/")


def test_mississippi_adapter_aliases_are_canonical():
    assert _canonical_state_statute_adapter("ms") == "mississippi-session-law"
    assert _canonical_state_statute_adapter("mississippi-code") == "mississippi-session-law"
