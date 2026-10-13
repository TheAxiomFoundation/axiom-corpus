"""``scripts/measure_source_coverage.py``: the offline measure of locked HTML scopes.

The differential test here is the one that ties the two implementations together: for
a scope the extractor has just built, the script's figures for each HTML source, read
back from the files on disk, equal the figures the extractor recorded.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from bs4 import BeautifulSoup

import scripts.measure_source_coverage as script
from axiom_corpus.corpus import documents
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.content_store import ContentCache
from axiom_corpus.corpus.corpus_locks import lock_from_worktree, write_lock
from axiom_corpus.corpus.source_coverage import words

SCOPE = ("us-xx", "policy", "2026-10-13")

PAGE = b"""<html><head><title>Chapter 5</title><script>var hidden = "script words";</script>
</head><body>
<header>Department banner <a href="/">Home</a></header>
<nav>Programs Offices</nav>
<div id="search">Search this site</div>
<main>
  <h1>Chapter 5 Eligibility</h1>
  <p>First paragraph kept, see <a href="/s/6">section 6</a>.</p>
  <div>Bare summary text the default text tags skip.</div>
  <button>Print</button>
  <!-- a comment is not text -->
</main>
<footer>Contact the webmaster</footer></body></html>"""

CARD_PAGE = b"""<html><body><main><form>Search and filter the list</form>
<div class="card"><div class="summary">The state extends coverage to new groups.</div>
<div>Effective Date: July 1, 2024</div></div></main></body></html>"""

DOCUMENTS = (
    ("page", "Eligibility chapter", "page.html", PAGE, None),
    ("cards", "Amendment summaries", "cards.html", CARD_PAGE, {"html_text_selector": "div.card"}),
    ("selected", "Selected part", "selected.html", PAGE, {"html_content_selector": "main"}),
)


def _manifest_rows(sources: Path) -> list[dict[str, Any]]:
    return [
        {
            "source_id": source_id,
            "jurisdiction": SCOPE[0],
            "document_class": SCOPE[1],
            "title": title,
            "source_url": f"https://example.test/{source_id}",
            "local_path": str(sources / filename),
            "source_format": "html",
            **({"extraction": extraction} if extraction else {}),
        }
        for source_id, title, filename, _content, extraction in DOCUMENTS
    ]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A checkout with one locked scope built by the extractor, and its manifests."""
    root = tmp_path / "repo"
    sources = tmp_path / "retained"
    sources.mkdir()
    for _source_id, _title, filename, content, _extraction in DOCUMENTS:
        (sources / filename).write_bytes(content)
    (root / "manifests").mkdir(parents=True)
    manifest = root / "manifests" / "us-xx-policy.yaml"
    manifest.write_text(yaml.safe_dump({"documents": _manifest_rows(sources)}))
    documents.extract_official_documents(
        CorpusArtifactStore(root / "data" / "corpus"), manifest_path=manifest, version=SCOPE[2]
    )
    write_lock(root, lock_from_worktree(root, SCOPE))
    ingest = root / ".axiom" / "ingest-manifests" / SCOPE[0] / SCOPE[1] / f"{SCOPE[2]}.json"
    ingest.parent.mkdir(parents=True)
    ingest.write_text(
        json.dumps(
            {
                "command": {
                    "text": "uv run axiom-corpus-ingest extract-official-documents --base "
                    "data/corpus --version 2026-10-13 --manifest manifests/us-xx-policy.yaml"
                }
            }
        )
    )
    return root


def _files(repo: Path, tmp_path: Path) -> script.LockedFiles:
    return script.LockedFiles(repo, ContentCache(tmp_path / "empty-cache"))


def _recorded(repo: Path) -> dict[str, dict[str, Any]]:
    coverage = repo / "data" / "corpus" / "coverage" / SCOPE[0] / SCOPE[1] / f"{SCOPE[2]}.json"
    return {
        row["source_path"]: row
        for row in json.loads(coverage.read_text())["source_coverage"]["sources"]
    }


def _measure(repo: Path, tmp_path: Path, **settings: Any) -> dict[str, Any]:
    lock = script.load_locks(repo).locks[SCOPE]
    return script.measure_scope(
        lock,
        _files(repo, tmp_path),
        manifest=settings.pop("manifest", None),
        manifest_settings=settings.pop("manifest_settings", {}),
        source_id_settings=settings.pop("source_id_settings", {}),
    )


# --------------------------------------------------------------------------- whole pages


def test_whole_page_region_is_the_visible_text_without_navigation() -> None:
    region = script.whole_page_region(PAGE)
    assert region is not None and region.kind == "html_whole_page"
    # Links, the nav, the page header and footer and the button are navigation; the
    # search box is chrome outside any of them, so it stays in the region.
    assert region.texts == (
        "Search this site Chapter 5 Eligibility First paragraph kept, see . "
        "Bare summary text the default text tags skip.",
    )
    figures = region.measure(["Chapter 5 Eligibility", "First paragraph kept, see section 6."])
    assert figures.region_words == 18
    assert figures.kept_words == 7
    # The header's link is counted once, with the header that holds it.
    assert figures.deliberately_dropped_words == len(
        words("Department banner Home Programs Offices section 6 Print Contact the webmaster")
    )


def test_whole_page_text_is_what_get_text_gives_the_same_tree() -> None:
    soup = BeautifulSoup(PAGE, "lxml")
    for node in soup.select("script, a[href], nav, header, footer, button"):
        node.decompose()
    region = script.whole_page_region(PAGE)
    assert region is not None and soup.body is not None
    assert " ".join(region.texts) == soup.body.get_text(" ", strip=True)


def test_whole_page_region_refuses_bytes_that_are_not_a_page() -> None:
    assert script.whole_page_region(b"") is None


# --------------------------------------------------------------------------- manifests


def test_the_ingest_manifest_names_the_scope_manifest(repo: Path) -> None:
    assert script.manifest_named_by_ingest(repo, SCOPE) == "manifests/us-xx-policy.yaml"
    assert script.manifest_named_by_ingest(repo, ("us-xx", "policy", "absent")) is None
    other = repo / ".axiom" / "ingest-manifests" / "us-xx" / "policy" / "rebuilt.json"
    other.write_text(json.dumps({"command": {"text": "rebuild: see docs/ingest-runs/x.md"}}))
    assert script.manifest_named_by_ingest(repo, ("us-xx", "policy", "rebuilt")) is None
    other.write_text("not json")
    assert script.manifest_named_by_ingest(repo, ("us-xx", "policy", "rebuilt")) is None


def test_manifest_index_reads_settings_by_manifest_and_by_source_id(repo: Path) -> None:
    index = script.ManifestIndex(repo)
    assert index.documents_of("manifests/us-xx-policy.yaml") == {
        "page": None,
        "cards": {"html_text_selector": "div.card"},
        "selected": {"html_content_selector": "main"},
    }
    assert index.documents_of("manifests/absent.yaml") == {}
    assert index.settings_by_source_id("us-xx", "policy", "cards") == {
        "html_text_selector": "div.card"
    }
    assert index.settings_by_source_id("us-xx", "policy", "page") is None
    assert index.settings_by_source_id("us-xx", "policy", "unlisted") is False
    assert index.settings_by_source_id("us-yy", "policy", "cards") is False


def test_a_source_id_two_manifests_disagree_on_matches_neither(repo: Path) -> None:
    same = yaml.safe_load((repo / "manifests" / "us-xx-policy.yaml").read_text())
    (repo / "manifests" / "copy.yaml").write_text(yaml.safe_dump(same))
    assert script.ManifestIndex(repo).settings_by_source_id("us-xx", "policy", "cards") == {
        "html_text_selector": "div.card"
    }
    same["documents"][1]["extraction"] = {"html_text_selector": "div.summary"}
    (repo / "manifests" / "changed.yaml").write_text(yaml.safe_dump(same))
    (repo / "manifests" / "not-a-manifest.yaml").write_text("releases: []\n")
    index = script.ManifestIndex(repo)
    assert index.settings_by_source_id("us-xx", "policy", "cards") is False
    assert index.settings_by_source_id("us-xx", "policy", "selected") == {
        "html_content_selector": "main"
    }


# --------------------------------------------------------------------------- one scope


def test_the_script_reproduces_the_figures_recorded_at_extraction(
    repo: Path, tmp_path: Path
) -> None:
    """The differential test: recorded at extraction against recomputed from disk."""
    recorded = _recorded(repo)
    index = script.ManifestIndex(repo)
    result = _measure(
        repo,
        tmp_path,
        manifest="manifests/us-xx-policy.yaml",
        manifest_settings=index.documents_of("manifests/us-xx-policy.yaml"),
    )

    assert result["scope"] == "us-xx/policy/2026-10-13"
    # Three document rows and one block row each.
    assert result["rows"] == 6 and result["uncited_sources"] == 0
    assert [row["source_path"] for row in result["sources"]] == sorted(recorded)
    for row in result["sources"]:
        expected = recorded[row["source_path"]]
        assert row["matched_by"] == "manifest"
        for key in ("region", "region_words", "kept_words", "deliberately_dropped_words"):
            assert row[key] == expected[key], (row["source_path"], key)
        assert row["longest_missing_runs"] == expected["longest_missing_runs"][: script.REPORT_RUNS]
        assert row["coverage"] == round(expected["kept_words"] / expected["region_words"], 4)
    by_name = {Path(row["source_path"]).name: row for row in result["sources"]}
    # 3 + 6 + 8 words in the content root; the rows keep the heading and the paragraph.
    assert (by_name["page.html"]["region"], by_name["page.html"]["region_words"]) == (
        "html_main_content",
        17,
    )
    assert by_name["page.html"]["coverage"] == round(9 / 17, 4)
    assert (by_name["cards.html"]["region"], by_name["cards.html"]["coverage"]) == (
        "html_text_selector",
        1.0,
    )
    assert by_name["page.html"]["rows"] == 2
    assert by_name["page.html"]["first_row"] == "us-xx/policy/page"
    # The block row's body: "First paragraph kept, see section 6."
    assert by_name["page.html"]["row_body_words"] == 6


def test_settings_matched_by_source_id_give_the_same_figures(repo: Path, tmp_path: Path) -> None:
    index = script.ManifestIndex(repo)
    named = _measure(
        repo, tmp_path, manifest_settings=index.documents_of("manifests/us-xx-policy.yaml")
    )
    by_id = _measure(
        repo,
        tmp_path,
        source_id_settings={
            stem: index.settings_by_source_id("us-xx", "policy", stem)
            for stem in ("page", "cards", "selected")
        },
    )
    assert [row["matched_by"] for row in by_id["sources"]] == ["source_id"] * 3
    strip = lambda rows: [{k: v for k, v in row.items() if k != "matched_by"} for row in rows]  # noqa: E731
    assert strip(by_id["sources"]) == strip(named["sources"])


def test_a_source_no_manifest_lists_is_measured_as_a_whole_page(repo: Path, tmp_path: Path) -> None:
    result = _measure(repo, tmp_path)
    by_name = {Path(row["source_path"]).name: row for row in result["sources"]}

    assert {row["matched_by"] for row in result["sources"]} == {"whole_page"}
    assert {row["region"] for row in result["sources"]} == {"html_whole_page"}
    # The same page reads lower as a whole page than through its manifest: the search
    # box is counted, and the form above the cards with it.
    assert by_name["page.html"]["region_words"] == 18
    assert by_name["cards.html"]["coverage"] < 1.0
    assert "Search and filter the list" in by_name["cards.html"]["longest_missing_runs"][0]["text"]


def test_a_manifest_that_no_longer_fits_the_page_falls_back_and_says_so(
    repo: Path, tmp_path: Path
) -> None:
    result = _measure(
        repo, tmp_path, manifest_settings={"page": {"html_content_selector": "#gone"}}
    )
    page = next(row for row in result["sources"] if row["source_path"].endswith("page.html"))
    assert page["matched_by"] == "whole_page" and page["region"] == "html_whole_page"
    assert page["region_error"].startswith(
        "manifest region failed: ValueError: html content selector did not match"
    )


def test_a_scope_with_a_missing_file_is_reported_absent_not_measured_in_part(
    repo: Path, tmp_path: Path
) -> None:
    source = repo / "data/corpus/sources/us-xx/policy/2026-10-13/official-documents/cards.html"
    source.unlink()
    result = _measure(repo, tmp_path)
    assert result["absent"] == [source.relative_to(repo).as_posix()]
    assert result["sources"] == []
    assert script.summarize_scope(result) is None


def test_locked_files_come_from_the_checkout_or_the_cache(repo: Path, tmp_path: Path) -> None:
    lock = script.load_locks(repo).locks[SCOPE]
    entry = next(entry for entry in lock.files if entry.path.endswith("page.html"))
    cache = ContentCache(tmp_path / "cache")
    files = script.LockedFiles(repo, cache)

    assert files.path(entry) == repo / entry.path
    cache.add_file(repo / entry.path, sha256=entry.sha256, size=entry.size)
    (repo / entry.path).unlink()
    assert files.path(entry) == cache.object_path(entry.sha256)
    assert script.LockedFiles(repo, ContentCache(tmp_path / "empty")).path(entry) is None


# --------------------------------------------------------------------------- the report


def _source(coverage: float, region_words: int, matched_by: str = "manifest") -> dict[str, Any]:
    kept = round(coverage * region_words)
    return {
        "source_path": f"sources/x/{coverage}-{region_words}.html",
        "region": "html_main_content",
        "matched_by": matched_by,
        "region_words": region_words,
        "kept_words": kept,
        "coverage": round(kept / region_words, 4),
        "needs_review": region_words >= 50 and kept / region_words < 0.5,
        "row_body_words": kept,
    }


def test_a_scope_summary_counts_the_sources_under_the_review_bar() -> None:
    result = {
        "scope": "us-xx/policy/v1",
        "manifest": "manifests/x.yaml",
        "sources": [
            _source(1.0, 200),
            _source(0.9, 100),
            _source(0.1, 100),
            _source(0.0, 40, "whole_page"),
            {"source_path": "sources/x/broken.html", "error": "not parseable as HTML"},
        ],
    }
    assert script.summarize_scope(result) == {
        "scope": "us-xx/policy/v1",
        "region": "manifest+whole_page",
        "manifest": "manifests/x.yaml",
        "sources": 4,
        "median": 0.5,
        "p10": 0.0,
        "minimum": 0.0,
        "needs_review": 1,
        "needs_review_share": 0.25,
        "needs_review_with_body": 1,
        "region_words": 440,
        "missing_words": 0 + 10 + 90 + 40,
        "needs_review_missing_words": 90,
        "errors": 1,
    }
    assert script.summarize_scope({"scope": "s", "sources": []}) is None


def test_scopes_rank_by_sources_under_the_bar_then_by_median(tmp_path: Path) -> None:
    def summary(scope: str, needs_review: int, median: float) -> dict[str, Any]:
        row = script.summarize_scope(
            {"scope": scope, "manifest": None, "sources": [_source(1.0, 100)]}
        )
        assert row is not None
        return {**row, "needs_review": needs_review, "median": median}

    ranking = script.rank(
        [
            {**row, "withdrawn": False, "selectors": 0, "newest_selector": ""}
            for row in (
                summary("b", 2, 0.4),
                summary("a", 2, 0.4),
                summary("c", 9, 0.9),
                summary("d", 2, 0.1),
            )
        ]
    )
    assert [row["scope"] for row in ranking] == ["c", "d", "a", "b"]

    path = tmp_path / "out" / "ranking.csv"
    script.write_csv(path, ranking)
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["scope"] for row in rows] == ["c", "d", "a", "b"]
    assert list(rows[0]) == list(script._CSV_FIELDS)


def test_the_command_measures_selected_scopes_and_writes_both_reports(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(tmp_path / "empty-cache"))
    output = tmp_path / "out" / "report.json"
    ranking = tmp_path / "out" / "ranking.csv"

    assert (
        script.main(
            [
                "us-xx",
                "--repo",
                str(repo),
                "--workers",
                "1",
                "--output",
                str(output),
                "--csv",
                str(ranking),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text())
    assert report["measure"] == "source-coverage-v1"
    assert report["review_bar"] == {"coverage": 0.5, "min_region_words": 50}
    assert (
        report["scopes_selected"],
        report["scopes_with_html_sources"],
        report["scopes_measured"],
    ) == (1, 1, 1)
    assert report["scopes_absent"] == [] and report["scopes_failed"] == {}
    assert [row["matched_by"] for row in report["scopes"][0]["sources"]] == ["manifest"] * 3
    assert report["ranking"][0]["scope"] == "us-xx/policy/2026-10-13"
    assert report["ranking"][0]["manifest"] == "manifests/us-xx-policy.yaml"
    assert ranking.read_text().splitlines()[1].startswith("us-xx/policy/2026-10-13,manifest,3,")
    assert "us-xx/policy/2026-10-13: 3 sources (manifest)" in capsys.readouterr().out

    # Without the ingest manifest the same sources are matched by source id.
    (repo / ".axiom" / "ingest-manifests" / "us-xx" / "policy" / "2026-10-13.json").unlink()
    assert (
        script.main(["--all", "--repo", str(repo), "--workers", "1", "--output", str(output)]) == 0
    )
    assert [
        row["matched_by"] for row in json.loads(output.read_text())["scopes"][0]["sources"]
    ] == ["source_id"] * 3


def test_the_command_fails_when_a_scope_cannot_be_read(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(tmp_path / "empty-cache"))
    (repo / "data/corpus/provisions/us-xx/policy/2026-10-13.jsonl").unlink()
    output = tmp_path / "report.json"

    assert (
        script.main(["--all", "--repo", str(repo), "--workers", "1", "--output", str(output)]) == 1
    )
    report = json.loads(output.read_text())
    assert report["scopes_absent"] == ["us-xx/policy/2026-10-13"]
    assert report["scopes_measured"] == 0

    with pytest.raises(SystemExit):
        script.main(["--repo", str(repo), "--output", str(output)])


def test_release_context_marks_withdrawn_scopes_and_counts_selectors(repo: Path) -> None:
    releases = repo / "manifests" / "releases"
    releases.mkdir()
    scope = {"jurisdiction": "us-xx", "document_class": "policy", "version": "2026-10-13"}
    other = {"jurisdiction": "us-xx", "document_class": "policy", "version": "older"}
    for name, scopes in (
        ("us-rulespec-2026-07-13", [scope, other]),
        ("us-rulespec-2026-10-12-w5-benefits-union", [scope]),
        ("us-rulespec-2026-09-01", [scope]),
    ):
        (releases / f"{name}.json").write_text(json.dumps({"name": name, "scopes": scopes}))

    context = script.release_context(repo)
    assert context["us-xx/policy/2026-10-13"] == {
        "withdrawn": False,
        "selectors": 3,
        "newest_selector": "us-rulespec-2026-10-12-w5-benefits-union",
    }
    assert context["us-xx/policy/older"]["selectors"] == 1
    assert context["us-xx/policy/unselected"] == {
        "withdrawn": False,
        "selectors": 0,
        "newest_selector": "",
    }
