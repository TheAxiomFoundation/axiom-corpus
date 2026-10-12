"""``scripts/audit_html_pre_gap.py`` on a two-source scope built in a temporary repo."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from axiom_corpus.corpus import documents
from axiom_corpus.corpus.content_store import ContentCache
from axiom_corpus.corpus.corpus_locks import CorpusLock, LockEntry, write_lock
from scripts.audit_html_pre_gap import has_pre, markdown_table, run

SCOPE = ("us", "manual", "2026-10-12-pre-audit")
SOURCE_DIR = "data/corpus/sources/us/manual/2026-10-12-pre-audit/official-documents"
# The table's ``pre`` reached a row before (read through the table); the printout did not.
PRE_PAGE = b"""<html><body><div class="poms"><h2>A. Printout</h2><p>Lead text.</p>
<table><tr><td>Code</td><td><pre>A1</pre></td></tr></table>
<pre>
 WAGE   TOTAL   32750.00
</pre></div></body></html>"""
PLAIN_PAGE = b"<html><body><main><h2>B. Rule</h2><p>Plain text only.</p></main></body></html>"
MANIFEST = """documents:
- source_id: with-pre
  jurisdiction: us
  document_class: manual
  title: With pre
  source_url: https://example.gov/with-pre
  extraction:
    html_content_selector: div.poms
- source_id: plain
  jurisdiction: us
  document_class: manual
  title: Plain
  source_url: https://example.gov/plain
"""


def _baseline_module(tmp_path: Path) -> Path:
    """The extractor with ``pre`` out of its text tags: the node set used before 2026-10-12."""
    source = Path(documents.__file__).read_text(encoding="utf-8")
    marker = '_PREFORMATTED_TAGS = {"pre"}'
    assert source.count(marker) == 1
    path = tmp_path / "documents_before_pre.py"
    path.write_text(
        source.replace(marker, "_PREFORMATTED_TAGS: set[str] = set()"), encoding="utf-8"
    )
    return path


def _entry(cache: ContentCache, path: str, content: bytes) -> LockEntry:
    sha = hashlib.sha256(content).hexdigest()
    cache.add_stream([content], sha256=sha, size=len(content))
    return LockEntry(path=path, sha256=sha, size=len(content))


def _rows(source_id: str, title: str, blocks: list[tuple[str, str]]) -> list[dict[str, object]]:
    source_path = f"{SOURCE_DIR.removeprefix('data/corpus/')}/{source_id}.html"
    rows: list[dict[str, object]] = [
        {
            "kind": "document",
            "ordinal": 0,
            "heading": title,
            "body": None,
            "source_path": source_path,
            "source_format": "html",
        }
    ]
    for ordinal, (heading, body) in enumerate(blocks, start=1):
        rows.append(
            {
                "kind": "block",
                "ordinal": ordinal,
                "heading": heading,
                "body": body,
                "source_path": source_path,
                "source_format": "html",
            }
        )
    return rows


def test_audit_measures_the_pre_gap_and_finds_other_pages_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "manifests").mkdir(parents=True)
    (repo / "manifests" / "pre-audit.yaml").write_text(MANIFEST, encoding="utf-8")
    cache = ContentCache(tmp_path / "cache")
    # The locked rows are what the extractor made before: the printout is in none of them.
    rows = _rows("with-pre", "With pre", [("A. Printout", "Lead text.\n\nCode A1")]) + _rows(
        "plain", "Plain", [("B. Rule", "Plain text only.")]
    )
    provisions = "".join(json.dumps(row) + "\n" for row in rows).encode()
    write_lock(
        repo,
        CorpusLock.from_entries(
            SCOPE,
            [
                _entry(cache, f"{SOURCE_DIR}/with-pre.html", PRE_PAGE),
                _entry(cache, f"{SOURCE_DIR}/plain.html", PLAIN_PAGE),
                _entry(
                    cache, "data/corpus/provisions/us/manual/2026-10-12-pre-audit.jsonl", provisions
                ),
            ],
        ),
    )

    report = run(
        repo, baseline_path=_baseline_module(tmp_path), cache=cache, compare_all=True, workers=1
    )

    counts = report["summary"]["counts"]
    assert counts["sources"] == 2
    assert counts["sources_with_pre"] == 1
    assert counts["status_verified"] == 2
    assert counts["without_pre_replayed"] == 1
    assert counts["without_pre_changed"] == 0
    assert counts["current_errors"] == 0
    scope = report["summary"]["scopes"]["us/manual/2026-10-12-pre-audit"]
    assert scope == {
        "sources_with_pre": 1,
        "pre_elements": 2,
        "pre_words": 4,
        "gap_pre_elements": 1,
        "gap_words": 3,
        "rows_changed": 1,
        "headings_changed": 0,
        "sources_gaining_text": 1,
        "sources_changed": 1,
        "sources_unverified": 0,
    }
    [source] = report["sources"]
    assert source["gap_samples"] == ["WAGE TOTAL 32750.00"]
    assert source["words_before"] + 3 == source["words_after"]
    assert "| `us/manual/2026-10-12-pre-audit` | 1 | 2 | 4 | 3 | 1 | 1 | 1 |" in markdown_table(
        report["summary"]
    )


def test_has_pre_reads_html_bytes_json_strings_and_base64_html() -> None:
    assert has_pre(b"<PRE class='x'>a</PRE>", ".html")
    assert not has_pre(b"<p>preamble</p><prefix/>", ".html")
    assert has_pre(json.dumps({"content": {"html": "<div><pre>a</pre></div>"}}).encode(), ".json")
    encoded = base64.b64encode(b"<div>" + b"x" * 200 + b"<pre>a</pre></div>").decode()
    assert has_pre(json.dumps({"html": encoded}).encode(), ".json")
    assert not has_pre(json.dumps({"html": "<p>none</p>"}).encode(), ".json")
