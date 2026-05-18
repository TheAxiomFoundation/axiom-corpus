from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.oregon_admin_rules import extract_oregon_admin_rules


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_oregon_admin_rules_sources(source_dir: Path) -> None:
    _write(
        source_dir / "oregon-administrative-rules" / "rule-search.html",
        """<html><body>
<form id="browseForm">
<select name="selectedChapter" id="selectedChapter">
<option value="-1">Select a chapter...</option>
<option value="175">166 - Secretary of State, Archives Division</option>
</select>
</form>
</body></html>
""",
    )
    _write(
        source_dir
        / "oregon-administrative-rules"
        / "chapters"
        / "chapter-166.html",
        """<html><body><main>
<h1>Secretary of State</h1>
<h2>Archives Division - Chapter 166</h2>
<div id="accordion">
<h3><a href="/oard/displayDivisionRules.action?selectedDivision=614">Division 500 - OREGON ADMINISTRATIVE RULES FILING REQUIREMENTS</a></h3>
<h3><a href="/oard/displayDivisionRules.action?selectedDivision=614">OREGON ADMINISTRATIVE RULES FILING REQUIREMENTS</a></h3>
</div>
</main></body></html>
""",
    )
    _write(
        source_dir
        / "oregon-administrative-rules"
        / "divisions"
        / "chapter-166-division-500.html",
        """<html><body><main>
<h1>Secretary of State</h1>
<h2><a href="/oard/displayChapterRules.action?selectedChapter=175">Archives Division - Chapter 166</a></h2>
<h3>Division 500<br>OREGON ADMINISTRATIVE RULES FILING REQUIREMENTS</h3>
<div class="rule_div">
<p><strong><a href="/oard/viewSingleRule.action?ruleVrsnRsn=238184">166-500-0020</a></strong><br><strong>Oregon Administrative Rule (OAR) Filing Requirements</strong></p>
<p><p>(1) Agencies must use the Oregon Administrative Rules Database to submit filings.</p><p>(2) See OAR 166-500-0070 for deadlines.</p></p>
<p><b>Statutory/Other Authority:</b>&nbsp;ORS 183.360<br>
<b>Statutes/Other Implemented:</b>&nbsp;ORS 183.335 &amp; 183.360<br>
<b>History:</b><br>OSA 3-2017, amend filed 12/18/2017, effective 12/18/2017<br></p>
</div>
</main></body></html>
""",
    )


def test_extract_oregon_admin_rules_local_sources_writes_records(tmp_path):
    source_dir = tmp_path / "oregon-source"
    _write_oregon_admin_rules_sources(source_dir)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_oregon_admin_rules(
        store,
        version="2026-05-18",
        source_dir=source_dir,
        only_chapter="166",
        workers=1,
    )

    assert report.coverage.complete
    assert report.chapter_count == 1
    assert report.division_count == 1
    assert report.rule_count == 1
    assert report.provisions_written == 4

    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-or/regulation",
        "us-or/regulation/chapter-166",
        "us-or/regulation/chapter-166/division-500",
        "us-or/regulation/chapter-166/division-500/rule-166-500-0020",
    ]
    rule = records[-1]
    assert rule.heading == "Oregon Administrative Rule (OAR) Filing Requirements"
    assert rule.citation_label == "OAR 166-500-0020"
    assert rule.body is not None
    assert "Agencies must use the Oregon Administrative Rules Database" in rule.body
    assert rule.metadata is not None
    assert rule.metadata["statutory_authority"] == "ORS 183.360"
    assert rule.metadata["statutes_implemented"] == "ORS 183.335 & 183.360"
    assert rule.metadata["references_to"] == [
        "us-or/regulation/rule-166-500-0070",
        "us-or/statute/183.360",
        "us-or/statute/183.335",
    ]

    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == [
        record.citation_path for record in records
    ]
    assert inventory[-1].source_format == "oregon-administrative-rules-html"


def test_extract_oregon_admin_rules_cli_local_sources(tmp_path, capsys):
    source_dir = tmp_path / "oregon-source"
    _write_oregon_admin_rules_sources(source_dir)
    base = tmp_path / "corpus"

    exit_code = main(
        [
            "extract-oregon-administrative-rules",
            "--base",
            str(base),
            "--version",
            "2026-05-18",
            "--source-dir",
            str(source_dir),
            "--only-chapter",
            "166",
            "--workers",
            "1",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"jurisdiction": "us-or"' in out
    assert '"chapter_count": 1' in out
    assert '"division_count": 1' in out
    assert '"rule_count": 1' in out
    assert '"coverage_complete": true' in out
