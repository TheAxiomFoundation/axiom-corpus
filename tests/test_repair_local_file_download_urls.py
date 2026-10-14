"""The successor scope differs from a legacy local_path scope only in the repair.

Invariants (``scripts/repair_local_file_download_urls.py``):

1. ``reextract`` and ``rewrite`` leave every source file byte, inventory item,
   provision row and coverage field equal to the locked scope's, except the
   version, the version-bearing ids and source paths, and
   ``metadata.download_url``/``content_type`` on rows that recorded a ``file:``
   URL.
2. After the repair no row records a ``file:`` URL, and every repaired row
   records a web URL and a media type.
3. ``verify`` reports any other difference, and its report never repeats a
   ``file:`` path.
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
from scripts.repair_local_file_download_urls import Scope, reextract, rewrite, verify

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
    assert "file:" not in json.dumps(report)
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
    assert any("metadata.source_authority changed" in problem for problem in problems)


def test_verify_rejects_a_repair_that_keeps_a_file_url(legacy_scope, tmp_path: Path) -> None:
    old, committed = legacy_scope
    new = _successor(old)
    work = tmp_path / "work"
    work.mkdir()
    reextract(old, new, committed, work)
    _legacy(new, {"retained"})
    problems = verify(old, new)["problems"]
    assert any("download_url is not a web URL" in problem for problem in problems)
    assert any("still records a file: URL" in problem for problem in problems)
    assert all("/Users/someone" not in problem for problem in problems)


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
                {"download_url": "https://www.mass.gov/doc/reg/download", "content_type": "application/pdf"}
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
