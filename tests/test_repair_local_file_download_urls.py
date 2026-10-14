"""The successor scope differs from a legacy local_path scope only in the repair.

Invariants (``scripts/repair_local_file_download_urls.py``):

1. ``reextract`` and ``rewrite`` leave every source file byte, inventory item,
   provision row and coverage field equal to the locked scope's, except the
   version, the version-bearing ids and source paths, and
   ``metadata.download_url``/``content_type`` on rows that recorded a ``file:``
   URL.
2. After the repair no row records a ``file:`` URL, and every repaired row
   records a web URL and a media type.
3. ``verify`` reports any other difference, compares exact values rather than
   placeholders, and its report never repeats a ``file:`` path.
4. The repair reads only a locked scope whose files match its lock.
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import extract_official_documents
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.repair_local_file_download_urls import (
    Scope,
    lock_mismatches,
    reextract,
    rewrite,
    verify,
)

TAG = "r2026-10-14-portable-download-url"
LEAK = "file:///Users/someone/retained/"


def _pdf(path: Path, text: str) -> Path:
    document = fitz.open()
    document.new_page().insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path


def _legacy(scope: Scope, leaked: set[str]) -> None:
    """Rewrite a fresh extraction the way the pre-fix extractor recorded it."""
    for path, rows in (
        (scope.inventory_path, scope.inventory()),
        (scope.provisions_path, scope.provisions()),
    ):
        for row in rows:
            source_id = row.get("source_id") or row["source_path"].rsplit("/", 1)[-1].split(".")[0]
            if source_id in leaked:
                row["metadata"]["download_url"] = f"{LEAK}{source_id}.pdf"
                row["metadata"]["content_type"] = None
        if path.suffix == ".json":
            path.write_text(json.dumps({"items": rows}, indent=2, sort_keys=True) + "\n")
        else:
            path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


@pytest.fixture
def legacy_scope(tmp_path: Path) -> tuple[Scope, Path]:
    retained = tmp_path / "retained"
    retained.mkdir()
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        f"""
documents:
  - source_id: fetched
    jurisdiction: de
    document_class: guidance
    title: Fetched over the network
    source_url: https://www.example.de/fetched
    source_format: pdf
    local_path: {json.dumps(str(_pdf(retained / "fetched.pdf", "Network text")))}
  - source_id: retained
    jurisdiction: de
    document_class: guidance
    title: Retained copy
    source_url: https://www.example.de/retained
    download_url: https://www.example.de/retained.pdf
    source_format: pdf
    local_path: {json.dumps(str(_pdf(retained / "retained.pdf", "Retained text")))}
    metadata:
      source_authority: Bundeszentralamt fuer Steuern
      snapshot_sha256: runtime-only-provenance
"""
    )
    base = tmp_path / "corpus"
    extract_official_documents(
        CorpusArtifactStore(base),
        manifest_path=manifest,
        version="2026-09-14-example",
        source_as_of="2026-09-14",
        expression_date="2025-01-01",
    )
    scope = Scope(base, "de", "guidance", "2026-09-14-example")
    _legacy(scope, {"retained"})
    committed = tmp_path / "committed.yaml"
    # The committed manifest lacks the runtime-only metadata the original run carried.
    committed.write_text(
        manifest.read_text()
        .replace("    local_path:", "    # was local_path:")
        .replace("      snapshot_sha256: runtime-only-provenance\n", "")
    )
    return scope, committed


def _successor(old: Scope) -> Scope:
    return Scope(old.base, old.jurisdiction, old.document_class, f"{old.version}-{TAG}")


def test_reextract_changes_only_the_leaked_fields(legacy_scope, tmp_path: Path) -> None:
    old, committed = legacy_scope
    new = _successor(old)
    work = tmp_path / "work"
    work.mkdir()
    reextract(old, new, committed, work)
    report = verify(old, new)

    assert report["problems"] == []
    assert report["repaired_rows"] == 4  # root + page, inventory and provisions
    assert report["download_urls_by_source_url"] == {
        "https://www.example.de/retained": "https://www.example.de/retained.pdf"
    }
    assert report["content_types"] == {"application/pdf": 4}
    serialized = new.inventory_path.read_text() + new.provisions_path.read_text()
    assert "file:" not in serialized
    assert "file:///" not in json.dumps(report) and "/Users/someone" not in json.dumps(report)
    fetched = [row for row in new.provisions() if row["source_id"] == "fetched"]
    assert {row["metadata"]["download_url"] for row in fetched} == {
        "https://www.example.de/fetched"
    }
    assert {row["version"] for row in new.provisions()} == {new.version}
    retained = [row for row in new.provisions() if row["source_id"] == "retained"]
    assert {row["metadata"]["snapshot_sha256"] for row in retained} == {"runtime-only-provenance"}


def test_verify_reports_any_other_difference(legacy_scope, tmp_path: Path) -> None:
    old, committed = legacy_scope
    new = _successor(old)
    work = tmp_path / "work"
    work.mkdir()
    reextract(old, new, committed, work)

    rows = new.provisions()
    rows[-1]["body"] = rows[-1]["body"] + " edited"
    rows[0]["metadata"]["source_authority"] = "someone else"
    new.provisions_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    source = next((new.base / new.source_prefix).rglob("*.pdf"))
    source.write_bytes(source.read_bytes() + b"\n")
    problems = verify(old, new)["problems"]

    assert any(problem.startswith("source files differ") for problem in problems)
    assert any(problem.endswith(": body changed") for problem in problems)
    assert any("metadata.source_authority added" in problem for problem in problems)


def test_verify_rejects_a_repair_that_keeps_a_file_url(legacy_scope, tmp_path: Path) -> None:
    old, committed = legacy_scope
    new = _successor(old)
    work = tmp_path / "work"
    work.mkdir()
    reextract(old, new, committed, work)
    _legacy(new, {"retained"})
    report = verify(old, new)
    problems = report["problems"]
    assert any("download_url is not a web URL" in problem for problem in problems)
    assert any("content_type is not a media type" in problem for problem in problems)
    # Review finding: a failed repair repeated the leaked path in its report.
    assert "file:///" not in json.dumps(report) and "/Users/someone" not in json.dumps(report)
    assert report["download_urls_by_source_url"] == {
        "https://www.example.de/retained": "<not a web URL>"
    }


def test_reextract_requires_a_manifest_entry_for_every_document(legacy_scope, tmp_path) -> None:
    old, committed = legacy_scope
    partial = tmp_path / "partial.yaml"
    partial.write_text(committed.read_text().split("  - source_id: retained")[0])
    with pytest.raises(SystemExit, match="no entry for"):
        reextract(old, _successor(old), partial, tmp_path)


def _recovery_scope(base: Path) -> Scope:
    scope = Scope(base, "us-ma", "regulation", "2026-05-28")
    store = CorpusArtifactStore(base)
    source = scope.source_prefix + "official-documents/reg.pdf"
    store.write_bytes(base / source, b"%PDF-1.7 recovered")
    paths = ["us-ma/regulation/reg", "us-ma/regulation/reg/1", "us-ma/regulation/other"]
    inventory = [
        {
            "citation_path": path,
            "sha256": "0" * 64,
            "source_format": "pdf",
            "source_path": source,
            "source_url": "https://www.mass.gov/reg",
            "metadata": {"download_url": f"{LEAK}reg.pdf", "content_type": None},
        }
        for path in paths
    ]
    provisions = [
        {
            "citation_path": path,
            "id": deterministic_provision_id(path, scope.version),
            "parent_citation_path": "us-ma/regulation/reg" if path.endswith("/1") else None,
            "parent_id": (
                deterministic_provision_id("us-ma/regulation/reg", scope.version)
                if path.endswith("/1")
                else None
            ),
            "jurisdiction": "us-ma",
            "document_class": "regulation",
            "version": scope.version,
            "source_format": "pdf",
            "source_path": source,
            "source_url": "https://www.mass.gov/reg",
            "body": f"text of {path}",
            "metadata": (
                {
                    "download_url": "https://www.mass.gov/doc/reg/download",
                    "content_type": "application/pdf",
                }
                if path == "us-ma/regulation/reg"
                else {"download_url": f"{LEAK}reg.pdf", "content_type": None}
            ),
        }
        for path in paths
    ]
    store.write_json(scope.inventory_path, {"items": inventory})
    store.write_text(
        scope.provisions_path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in provisions)
    )
    store.write_json(
        scope.coverage_path,
        compare_provision_coverage(
            tuple(SourceInventoryItem.from_mapping(item) for item in inventory),
            tuple(ProvisionRecord.from_mapping(row) for row in provisions),
            jurisdiction="us-ma",
            document_class="regulation",
            version=scope.version,
        ).to_mapping(),
    )
    return scope


def test_rewrite_uses_the_sibling_url_then_the_source_url(tmp_path: Path) -> None:
    old = _recovery_scope(tmp_path / "corpus")
    new = _successor(old)
    rewrite(old, new)
    report = verify(old, new)

    assert report["problems"] == []
    assert report["repaired_rows"] == 5
    inventory = {item["citation_path"]: item["metadata"] for item in new.inventory()}
    assert inventory["us-ma/regulation/reg"] == {
        "download_url": "https://www.mass.gov/doc/reg/download",
        "content_type": "application/pdf",
    }
    assert inventory["us-ma/regulation/other"] == {
        "download_url": "https://www.mass.gov/reg",
        "content_type": "application/pdf",
    }
    child = next(row for row in new.provisions() if row["citation_path"].endswith("/1"))
    assert child["id"] == deterministic_provision_id("us-ma/regulation/reg/1", new.version)
    assert child["parent_id"] == deterministic_provision_id("us-ma/regulation/reg", new.version)
    assert child["source_path"].startswith(new.source_prefix)
    assert "file:" not in new.inventory_path.read_text() + new.provisions_path.read_text()


def _rewrite_rows(scope: Scope, edit) -> None:
    rows = scope.provisions()
    for row in rows:
        edit(row)
    scope.provisions_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    )


def test_placeholder_strings_do_not_stand_in_for_successor_values(tmp_path: Path) -> None:
    """Review finding: verify normalized to placeholders, so literal ones passed."""
    old = _recovery_scope(tmp_path / "corpus")
    new = _successor(old)
    rewrite(old, new)

    def placeholders(row):
        row["version"] = "<version>"
        row["id"] = "<versioned id>"
        row["source_path"] = "sources/<scope>/official-documents/reg.pdf"

    _rewrite_rows(new, placeholders)
    problems = verify(old, new)["problems"]
    assert len([p for p in problems if p.startswith("provisions[")]) == 3
    assert all("version changed" in p and "id changed" in p for p in problems)
    assert all("source_path changed" in p for p in problems)


@pytest.mark.parametrize("coverage_version", ["wrong-scope", None])
def test_coverage_version_must_name_the_successor(tmp_path: Path, coverage_version) -> None:
    """Review finding: the coverage version was dropped before comparison."""
    old = _recovery_scope(tmp_path / "corpus")
    new = _successor(old)
    rewrite(old, new)
    coverage = new.coverage()
    if coverage_version is None:
        del coverage["version"]
    else:
        coverage["version"] = coverage_version
    new.coverage_path.write_text(json.dumps(coverage))
    problems = verify(old, new)["problems"]
    assert problems == [
        "coverage: version " + ("removed" if coverage_version is None else "changed")
    ]


def test_null_repair_fields_cannot_be_added_to_an_unrepaired_row(tmp_path: Path) -> None:
    """Review finding: metadata absent before and null-filled after passed."""
    old = _recovery_scope(tmp_path / "corpus")
    rows = old.provisions()
    rows[0].pop("metadata")
    old.provisions_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    new = _successor(old)
    rewrite(old, new)
    assert verify(old, new)["problems"] == []

    def add_nulls(row):
        if "metadata" not in row:
            row["metadata"] = {"download_url": None, "content_type": None}

    _rewrite_rows(new, add_nulls)
    (problem,) = verify(old, new)["problems"]
    assert problem.endswith("metadata added")


def test_repair_refuses_a_scope_that_differs_from_its_lock(tmp_path: Path) -> None:
    """Review finding: an edited worktree copy was compared as if it were the lock."""
    from axiom_corpus.corpus.corpus_locks import lock_from_worktree, write_lock

    repo = tmp_path / "repo"
    old = _recovery_scope(repo / "data/corpus")
    write_lock(repo, lock_from_worktree(repo, (old.jurisdiction, old.document_class, old.version)))
    assert lock_mismatches(old, repo) == []

    text = old.provisions_path.read_text()
    old.provisions_path.write_text(text.replace("text of", "TEXT of", 1))
    stray = repo / "data/corpus" / old.source_prefix / "official-documents/extra.pdf"
    stray.write_bytes(b"%PDF stray")
    (repo / "data/corpus" / old.source_prefix / "official-documents/reg.pdf").unlink()
    problems = lock_mismatches(old, repo)
    prefix = "data/corpus/"
    assert f"{prefix}provisions/us-ma/regulation/2026-05-28.jsonl differs from its lock" in problems
    assert f"{prefix}{old.source_prefix}official-documents/reg.pdf is absent" in problems
    assert f"{prefix}{old.source_prefix}official-documents/extra.pdf is not in the lock" in problems
    assert lock_mismatches(_successor(old), repo) == [f"{_successor(old).label} has no lock"]


@pytest.mark.parametrize(
    ("before", "after"),
    [([1], [True]), ([1], [1.0]), ([{"rank": 1}], [{"rank": True}]), ([1, 2], [1])],
)
def test_lists_compare_element_by_element_with_types(tmp_path: Path, before, after) -> None:
    """Review finding: list equality treated 1, 1.0 and True as equal."""
    old = _recovery_scope(tmp_path / "corpus")
    rows = old.provisions()
    rows[1]["metadata"]["ranks"] = before
    old.provisions_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    new = _successor(old)
    rewrite(old, new)
    assert verify(old, new)["problems"] == []

    def change(row):
        if "ranks" in row["metadata"]:
            row["metadata"]["ranks"] = after

    _rewrite_rows(new, change)
    (problem,) = verify(old, new)["problems"]
    assert "metadata.ranks" in problem


@pytest.mark.parametrize(
    "content_type",
    [
        "file:///Users/someone/private.pdf",
        False,
        "pdf",
        "",
        # Review round 3: parameters bypassed the old pattern.
        "application/pdf;file:///Users/someone/private.pdf",
        'application/pdf; name="file:///Users/someone/private.pdf"',
        "application/pdf; charset=",
        'application/pdf; name="unterminated',
        'application/pdf; name="fi\tle:///Users/someone/private.pdf"',
    ],
)
def test_repaired_content_type_must_be_a_media_type(tmp_path: Path, content_type) -> None:
    """Review finding: any non-null content_type passed, and reached the report verbatim."""
    old = _recovery_scope(tmp_path / "corpus")
    new = _successor(old)
    rewrite(old, new)

    def bad_type(row):
        if row["citation_path"].endswith("/1"):
            row["metadata"]["content_type"] = content_type

    _rewrite_rows(new, bad_type)
    report = verify(old, new)
    assert any("content_type is not a media type" in p for p in report["problems"])
    assert "file:///" not in json.dumps(report) and "/Users/someone" not in json.dumps(report)
    assert "<not a media type>" in report["content_types"]


def test_rewrite_keeps_the_inventory_envelope_and_verify_checks_it(tmp_path: Path) -> None:
    """Review finding: rewrite wrote only "items" and verify did not notice."""
    old = _recovery_scope(tmp_path / "corpus")
    document = json.loads(old.inventory_path.read_text())
    document["provenance"] = {"authority": "Official publisher", "ranks": [1]}
    old.inventory_path.write_text(json.dumps(document))
    new = _successor(old)
    rewrite(old, new)
    assert json.loads(new.inventory_path.read_text())["provenance"] == document["provenance"]
    assert verify(old, new)["problems"] == []

    document = json.loads(new.inventory_path.read_text())
    document["provenance"]["ranks"] = [True]
    document["added"] = "x"
    new.inventory_path.write_text(json.dumps(document))
    (problem,) = verify(old, new)["problems"]
    assert problem == "inventory envelope: added added, provenance.ranks[0] changed"


def test_verify_scans_the_successor_bytes_for_any_file_url(tmp_path: Path) -> None:
    """A file: URL the locked scope also carried, outside download_url, is not a repair."""
    old = _recovery_scope(tmp_path / "corpus")
    rows = old.provisions()
    rows[2]["metadata"]["legal_authority_url"] = "file:///Users/someone/authority.html"
    old.provisions_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    new = _successor(old)
    rewrite(old, new)
    report = verify(old, new)
    assert report["problems"] == [f"{new.version}.jsonl: 1 URL field(s) still record a file: URL"]
    assert "file:///" not in json.dumps(report) and "/Users/someone" not in json.dumps(report)


def test_a_well_formed_media_type_with_parameters_is_reported_by_its_essence(
    tmp_path: Path,
) -> None:
    old = _recovery_scope(tmp_path / "corpus")
    new = _successor(old)
    rewrite(old, new)

    def with_parameter(row):
        if row["citation_path"].endswith("/1"):
            row["metadata"]["content_type"] = 'Application/PDF; charset="binary"'

    _rewrite_rows(new, with_parameter)
    report = verify(old, new)
    assert report["problems"] == []
    assert report["content_types"] == {"application/pdf": 5}
