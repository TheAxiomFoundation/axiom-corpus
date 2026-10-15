#!/usr/bin/env python3
"""Re-extract locked official-document HTML scopes offline and measure the navigation-block filter.

``documents._extract_html_blocks`` drops a positional block (``block-N``) that is
its page's navigation (``content_quality.is_navigation_block``). Locked scopes are
immutable, so this script never writes under ``data/corpus``: for each named scope
it re-extracts every retained HTML source that a tracked official-document
manifest describes, twice, from the bytes the scope's lock pins:

* with ``html_keep_navigation_blocks: true``, the extractor's behaviour before
  the filter. Its provision rows must equal the locked rows byte for byte
  (``reproduced``); a document whose rows differ (``drift``: the manifest or the
  extractor changed since the ingest) is reported and left out of the
  measurement, because its successor would differ for reasons other than the
  filter;
* with the source's own ``extraction``, the filter on.

It writes the rows a successor ingest of each scope would hold (the locked rows,
with every reproduced document's rows replaced by its filtered rows) to
``<out>/provisions/<scope>.jsonl``, scans them with the release content check,
and writes ``<out>/summary.json`` and ``<out>/dropped.jsonl``. A source is
matched to its manifest entry by jurisdiction, document class, retained file
name, title, source URL and root citation path, across every manifest under
``manifests/`` and the manifest the scope's signed ingest command names, as it
stood at the ingest commit.

Run it from the repository root after fetching the scopes' locked files
(``axiom-corpus-ingest corpus fetch <scope>...``)::

    uv run python scripts/measure_html_navigation_blocks.py --out <scratch dir> <scope>...
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from axiom_corpus.corpus import documents
from axiom_corpus.corpus.artifacts import safe_segment
from axiom_corpus.corpus.content_quality import (
    NAVIGATION_BODY,
    ScopeContentScanner,
    classify_body,
    page_navigation,
)
from axiom_corpus.corpus.models import ProvisionRecord

CORPUS = Path("data/corpus")
INGEST_MANIFESTS = Path(".axiom/ingest-manifests")
KEEP = {"html_keep_navigation_blocks": True}
_OFFICIAL = re.compile(
    r"^sources/(?P<j>[^/]+)/(?P<dc>[^/]+)/(?P<run>[^/]+)/official-documents/(?P<file>[^/]+)$"
)
_MANIFEST_ARG = re.compile(r"--manifest\s+(\S+)")
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


@dataclass(frozen=True)
class Candidate:
    manifest: str
    source: documents.OfficialDocumentSource


def _load_manifest_text(text: str, label: str) -> list[Candidate]:
    if "source_id" not in text:
        return []
    try:
        data = yaml.load(text, Loader=_YAML_LOADER)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict) or not isinstance(data.get("documents"), list):
        return []
    out = []
    for row in data["documents"]:
        if not isinstance(row, dict):
            continue
        try:
            out.append(Candidate(label, documents.OfficialDocumentSource.from_mapping(row)))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def _index_candidates(scopes: Iterable[str]) -> dict[tuple[str, str, str], list[Candidate]]:
    """Every manifest source, keyed by jurisdiction, class and retained file stem."""
    candidates: list[Candidate] = []
    for path in sorted(Path("manifests").rglob("*.yaml")):
        candidates.extend(_load_manifest_text(path.read_text(errors="replace"), str(path)))
    for scope in scopes:
        ingest = INGEST_MANIFESTS / f"{scope}.json"
        if not ingest.is_file():
            continue
        data = json.loads(ingest.read_text())
        command = str((data.get("command") or {}).get("text") or "")
        commit = str((data.get("axiom_corpus_git") or {}).get("commit") or "")
        for manifest in _MANIFEST_ARG.findall(command):
            if not commit:
                continue
            shown = subprocess.run(
                ["git", "show", f"{commit}:{manifest}"], capture_output=True, text=True
            )
            if shown.returncode == 0:
                candidates.extend(_load_manifest_text(shown.stdout, f"{commit[:9]}:{manifest}"))
    index: dict[tuple[str, str, str], list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        source = candidate.source
        index[(source.jurisdiction, source.document_class, safe_segment(source.source_id))].append(
            candidate
        )
    return index


def _rows(path: Path) -> list[dict[str, Any]]:
    with path.open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _records(
    candidate: Candidate,
    blocks: tuple[Any, ...],
    root: dict[str, Any],
    *,
    version: str,
) -> list[dict[str, Any]]:
    metadata = root.get("metadata") or {}
    records = documents._provision_records(
        candidate.source,
        blocks=blocks,
        version=version,
        source_key=root["source_path"],
        source_format=root["source_format"],
        source_as_of=root["source_as_of"],
        expression_date=root["expression_date"],
        content_type=metadata.get("content_type"),
        final_url=metadata.get("download_url") or candidate.source.source_url,
    )
    return [record.to_mapping() for record in records]


def _canonical(rows: list[dict[str, Any]]) -> list[str]:
    return [json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows]


def _extract(candidate: Candidate, content: bytes, *, keep: bool) -> tuple[Any, ...]:
    extraction = dict(candidate.source.extraction or {})
    if keep:
        extraction.update(KEEP)
    return tuple(
        documents._extract_blocks(
            content,
            "html",
            source_url=candidate.source.source_url,
            title=candidate.source.title,
            extraction=extraction or None,
        )
    )


def measure_scope(
    scope: str,
    index: dict[tuple[str, str, str], list[Candidate]],
    out: Path,
    dropped_out: Any,
) -> dict[str, Any]:
    jurisdiction, document_class, version = scope.split("/")
    locked = _rows(CORPUS / "provisions" / f"{scope}.jsonl")
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in locked:
        by_source[str(row.get("source_path") or "")].append(row)
    status: Counter[str] = Counter()
    replaced: dict[str, list[dict[str, Any]]] = {}
    manifests: Counter[str] = Counter()
    drift: list[str] = []
    for source_path, rows in by_source.items():
        match = _OFFICIAL.match(source_path)
        roots = [
            row
            for row in rows
            if row.get("kind") == "document" and not row.get("parent_citation_path")
        ]
        if not match or len(roots) != 1 or roots[0].get("source_format") != "html":
            status["not_official_html"] += 1
            continue
        root = roots[0]
        stem = match["file"].rsplit(".", 1)[0]
        candidates = [
            candidate
            for candidate in index.get((jurisdiction, document_class, stem), [])
            if candidate.source.title == root.get("heading")
            and candidate.source.source_url == root.get("source_url")
            and documents._root_citation_path(candidate.source) == root["citation_path"]
        ]
        if not candidates:
            status["no_manifest_entry"] += 1
            continue
        content = (CORPUS / source_path).read_bytes()
        expected = _canonical(rows)
        reproduced: Candidate | None = None
        for candidate in candidates:
            try:
                before = _extract(candidate, content, keep=True)
            except Exception:  # noqa: BLE001 - a manifest entry that no longer parses
                continue
            if _canonical(_records(candidate, before, root, version=version)) == expected:
                reproduced = candidate
                break
        if reproduced is None:
            status["drift"] += 1
            drift.append(source_path)
            continue
        status["reproduced"] += 1
        manifests[reproduced.manifest] += 1
        after = _extract(reproduced, content, keep=False)
        after_rows = _records(reproduced, after, root, version=version)
        replaced[source_path] = after_rows
        kept_paths = {row["citation_path"] for row in after_rows}
        page = page_navigation(content)
        for row in rows:
            if row["citation_path"] in kept_paths:
                continue
            verdict = classify_body(
                row.get("body"), page, heading=row.get("heading"), label=row.get("citation_label")
            )
            dropped_out.write(
                json.dumps(
                    {
                        "scope": scope,
                        "citation_path": row["citation_path"],
                        "heading": row.get("heading"),
                        "body": row.get("body"),
                        "check_navigation": verdict.navigation,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        # Kept rows keep their paths and text; only block_count may move.
        before_by_path = {row["citation_path"]: row for row in rows}
        for row in after_rows:
            old = before_by_path.get(row["citation_path"])
            if old is None or (old.get("body"), old.get("heading")) != (
                row.get("body"),
                row.get("heading"),
            ):
                status["kept_row_changed"] += 1
    successor: list[dict[str, Any]] = []
    for source_path, rows in by_source.items():
        successor.extend(replaced.get(source_path, rows))
    target = out / "provisions" / f"{scope}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w") as handle:
        for row in successor:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    before_findings = _scan(locked)
    after_findings = _scan(successor)
    return {
        "scope": scope,
        "sources": dict(status),
        "manifests": dict(manifests),
        "drift_sources": drift,
        "rows_before": len(locked),
        "rows_after": len(successor),
        "findings_before": dict(Counter(code for code, _ in before_findings)),
        "findings_after": dict(Counter(code for code, _ in after_findings)),
        "navigation_paths_after": sorted(
            path for code, path in after_findings if code == NAVIGATION_BODY
        ),
        "new_findings": sorted(f"{code} {path}" for code, path in after_findings - before_findings),
    }


def _scan(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    scanner = ScopeContentScanner(CORPUS)
    for row in rows:
        scanner.add(ProvisionRecord.from_mapping(row))
    return {finding.key() for finding in scanner.findings()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("scopes", nargs="+", help="<jurisdiction>/<class>/<version>")
    parser.add_argument("--out", type=Path, required=True, help="scratch output directory")
    args = parser.parse_args()
    if args.out.resolve().is_relative_to(CORPUS.resolve()):
        parser.error("--out must be outside data/corpus")
    args.out.mkdir(parents=True, exist_ok=True)
    index = _index_candidates(args.scopes)
    summaries = []
    with (args.out / "dropped.jsonl").open("w") as dropped_out:
        for scope in args.scopes:
            summaries.append(measure_scope(scope, index, args.out, dropped_out))
            print(
                json.dumps(
                    {
                        key: summaries[-1][key]
                        for key in ("scope", "sources", "findings_before", "findings_after")
                    }
                ),
                flush=True,
            )
    (args.out / "summary.json").write_text(json.dumps(summaries, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
