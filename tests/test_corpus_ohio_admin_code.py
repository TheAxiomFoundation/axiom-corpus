from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.ohio_admin_code import extract_ohio_admin_code


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_ohio_admin_code_sources(source_dir: Path) -> None:
    _write(
        source_dir / "ohio-administrative-code" / "index.html",
        """<html><body><main>
<div class="laws-header"><h1>Ohio Administrative Code</h1></div>
<table>
<tr><td class="name-cell"><a href="/ohio-administrative-code/5160:1">5160:1 <span class="codes-separator">|</span> Ohio Department of Medicaid <span class="codes-separator">|</span> Eligibility</a></td></tr>
</table>
</main></body></html>
""",
    )
    _write(
        source_dir / "ohio-administrative-code" / "agencies" / "5160-1.html",
        """<html><body><main>
<div class="laws-header"><h1>5160:1 <span class="codes-separator">|</span> Eligibility</h1></div>
<table>
<tr><td class="name-cell"><a href="/ohio-administrative-code/chapter-5160:1-1">Chapter 5160:1-1 <span class="codes-separator">|</span> Medicaid General Principles</a></td></tr>
</table>
</main></body></html>
""",
    )
    _write(
        source_dir / "ohio-administrative-code" / "chapters" / "chapter-5160-1-1.html",
        """<html><body><main>
<div class="laws-header"><h1>Chapter 5160:1-1 <span class="codes-separator">|</span> Medicaid General Principles</h1></div>
<table><tr><td class="name-cell">
<div class="list-content">
<span class="content-head"><span class="content-head-text"><a href="/ohio-administrative-code/rule-5160:1-1-01">Rule 5160:1-1-01 <span class="codes-separator">|</span> Medicaid: definitions.</a></span></span>
<div>
<div class="laws-section-info">
<div class="laws-section-info-module"><div class="label">Effective:</div><div class="value">January 1, 2025</div></div>
<div class="laws-section-info-module"><div class="label">Promulgated Under:</div><div class="value"><a class="section-link" href="/ohio-revised-code/section-119.03">119.03</a></div></div>
<div class="laws-section-info-module no-print"><div class="label">PDF:</div><div class="value"><a href="/assets/laws/administrative-code/authenticated/5160/1/1/5160$1-1-01_20250101.pdf">Download Authenticated PDF</a></div></div>
</div>
<section class="laws-body"><span>
<p class="first-paragraph level-1">(A) This rule defines terms used in rule <a class="rule-link" href="/ohio-administrative-code/rule-5160:1-1-02">5160:1-1-02</a> of the Administrative Code.</p>
<p>(B) "Medicaid" has the same meaning as in section <a class="section-link" href="/ohio-revised-code/section-5162.03">5162.03</a> of the Revised Code.</p>
<table><tr><th>Term</th><th>Meaning</th></tr><tr><td>MAGI</td><td>Modified adjusted gross income</td></tr></table>
</span><div class="laws-notice"><p>Last updated January 2, 2025 at 8:00 AM</p></div></section>
<section class="laws-history"><h2>Supplemental Information</h2><div class="laws-additional-information">
<strong>Authorized By:</strong><span>5164.02</span><br>
<strong>Amplifies:</strong><span>5162.03</span><br>
<strong>Five Year Review Date:</strong><span>1/1/2030</span><br>
<strong>Prior Effective Dates:</strong><span>1/1/2020</span><br>
</div></section>
</div>
</div>
</td></tr></table>
</main></body></html>
""",
    )


def test_extract_ohio_admin_code_local_sources_writes_records(tmp_path):
    source_dir = tmp_path / "ohio-source"
    _write_ohio_admin_code_sources(source_dir)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ohio_admin_code(
        store,
        version="2026-05-18",
        source_dir=source_dir,
        only_agency="5160:1",
        workers=1,
    )

    assert report.coverage.complete
    assert report.agency_count == 1
    assert report.chapter_count == 1
    assert report.rule_count == 1
    assert report.provisions_written == 4

    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-oh/regulation",
        "us-oh/regulation/agency-5160-1",
        "us-oh/regulation/agency-5160-1/chapter-5160-1-1",
        "us-oh/regulation/agency-5160-1/chapter-5160-1-1/rule-5160-1-1-01",
    ]
    rule = records[-1]
    assert rule.heading == "Medicaid: definitions"
    assert rule.citation_label == "Ohio Admin. Code 5160:1-1-01"
    assert rule.body is not None
    assert "Term | Meaning" in rule.body
    assert rule.metadata is not None
    assert rule.metadata["effective_date"] == "January 1, 2025"
    assert rule.metadata["pdf_url"].endswith("5160$1-1-01_20250101.pdf")
    assert rule.metadata["references_to"] == [
        "us-oh/regulation/rule-5160-1-1-02",
        "us-oh/statute/119.03",
        "us-oh/statute/5162.03",
    ]
    assert rule.metadata["last_updated"] == "Last updated January 2, 2025 at 8:00 AM"

    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == [
        record.citation_path for record in records
    ]
    assert inventory[-1].source_format == "ohio-administrative-code-html"


def test_extract_ohio_admin_code_cli_local_sources(tmp_path, capsys):
    source_dir = tmp_path / "ohio-source"
    _write_ohio_admin_code_sources(source_dir)
    base = tmp_path / "corpus"

    exit_code = main(
        [
            "extract-ohio-administrative-code",
            "--base",
            str(base),
            "--version",
            "2026-05-18",
            "--source-dir",
            str(source_dir),
            "--only-chapter",
            "5160:1-1",
            "--workers",
            "1",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"jurisdiction": "us-oh"' in out
    assert '"chapter_count": 1' in out
    assert '"rule_count": 1' in out
    assert '"coverage_complete": true' in out
