#!/usr/bin/env python3
"""Report stored eCFR provisions that lack the table captions the adapter now emits.

Until 2026-10-12 the eCFR adapter's ``_table_text`` read only ``TR`` rows, so
every table's ``<CAPTION>`` was dropped from provision bodies. For every
``ecfr-xml`` record under ``--base`` whose retained source XML holds a captioned
table inside that record's section or appendix, this script re-extracts the
record from the retained bytes with the current adapter and compares the
result with the stored body:

- ``caption_only_change`` is true when the re-extraction equals the stored body
  plus inserted lines, and the inserted non-blank lines are exactly that
  provision's caption lines. Such a record is a successor candidate whose
  re-extraction changes nothing but its captions.
- A record already carrying its captions reports no change and is omitted.
- A container (part or subpart) whose stored body was materialized from
  descendants is reported when it carries a captioned descendant table's rows
  without the caption; it is not re-extracted.

Each scope lists the named releases (``manifests/releases``) that select it. The
script writes no corpus artifacts.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from axiom_corpus.corpus.ecfr import (
    EcfrPartTarget,
    _element_citation_path,
    _table_caption_lines,
    _table_text,
    iter_ecfr_title_provisions,
)
from axiom_corpus.corpus.resolver import require_materialized

REPO_ROOT = Path(__file__).resolve().parents[1]
ECFR_SOURCE_FORMAT = "ecfr-xml"
JURISDICTION = "us"
DOCUMENT_CLASS = "regulation"


def _captioned_tables(root: ET.Element, title: int) -> list[dict[str, Any]]:
    """Each captioned table with text: its provision, caption lines, and rows."""
    parents = {child: parent for parent in root.iter() for child in parent}
    tables: list[dict[str, Any]] = []
    for table in root.iter("TABLE"):
        captions = [child for child in table if child.tag == "CAPTION"]
        lines = [line for caption in captions for line in _table_caption_lines(caption)]
        if not lines:
            continue
        node, provision = table, None
        while provision is None and node in parents:
            node = parents[node]
            provision = _element_citation_path(title, node)
        rows = ET.Element(table.tag, table.attrib)
        rows.extend(child for child in table if child.tag != "CAPTION")
        tables.append(
            {"provision": provision, "caption_lines": lines, "rows": _table_text(rows)}
        )
    return tables


def _caption_only_change(stored: str, extracted: str, caption_lines: list[str]) -> bool:
    stored_lines = stored.split("\n")
    extracted_lines = extracted.split("\n")
    matcher = difflib.SequenceMatcher(None, stored_lines, extracted_lines, autojunk=False)
    inserted: list[str] = []
    for op, _, _, start, end in matcher.get_opcodes():
        if op == "equal":
            continue
        if op != "insert":
            return False
        inserted.extend(extracted_lines[start:end])
    return Counter(line for line in inserted if line) == Counter(caption_lines)


def _release_names(releases_dir: Path) -> dict[str, list[str]]:
    names: dict[str, set[str]] = defaultdict(set)
    for selector in sorted(releases_dir.glob("*.json")):
        manifest = json.loads(selector.read_text())
        for scope in manifest.get("scopes", []):
            key = "/".join((scope["jurisdiction"], scope["document_class"], scope["version"]))
            names[key].add(manifest["name"])
    return {key: sorted(value) for key, value in names.items()}


def _load_records(base: Path) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    for provisions_path in sorted((base / "provisions" / JURISDICTION / DOCUMENT_CLASS).glob("*.jsonl")):
        rows = [
            json.loads(line)
            for line in provisions_path.read_text().splitlines()
            if line.strip()
        ]
        records[provisions_path.stem] = [
            row for row in rows if row.get("source_format") == ECFR_SOURCE_FORMAT
        ]
    return records


def _reextract(
    xml_text: str, title: int, paths: set[str], *, appendices: bool
) -> dict[str, str | None]:
    parts = {path.split("/")[3] for path in paths}
    return {
        record.citation_path: record.body
        for record in iter_ecfr_title_provisions(
            xml_text,
            tuple(EcfrPartTarget(title=title, part=part) for part in sorted(parts)),
            version="audit",
            source_path="audit.xml",
            allowed_citation_paths=paths,
            include_appendices=appendices,
        )
    }


def audit(base: Path, releases_dir: Path) -> dict[str, Any]:
    released = _release_names(releases_dir)
    records_by_version = _load_records(base)
    # Retained XML is parsed once per distinct byte string; several scopes
    # carry copies of the same snapshot.
    tables_by_digest: dict[str, list[dict[str, Any]]] = {}
    extracted: dict[tuple[str, str], str | None] = {}
    scopes: list[dict[str, Any]] = []

    for version, records in records_by_version.items():
        by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            by_source[record["source_path"]].append(record)
        findings: list[dict[str, Any]] = []
        for source_path, source_records in sorted(by_source.items()):
            data = (base / source_path).read_bytes()
            if b"<CAPTION" not in data:
                continue
            title = int(source_records[0]["citation_path"].split("/")[2])
            digest = hashlib.sha256(data).hexdigest()
            if digest not in tables_by_digest:
                tables_by_digest[digest] = _captioned_tables(ET.fromstring(data), title)
            tables = tables_by_digest[digest]
            captioned = {table["provision"] for table in tables}
            for appendices in (False, True):
                wanted = {
                    record["citation_path"]
                    for record in source_records
                    if record["citation_path"] in captioned
                    and (record.get("kind") == "appendix") == appendices
                    and (digest, record["citation_path"]) not in extracted
                }
                if wanted:
                    bodies = _reextract(data.decode("utf-8"), title, wanted, appendices=appendices)
                    for path in wanted:
                        extracted[(digest, path)] = bodies.get(path)
            for record in source_records:
                path = record["citation_path"]
                stored = record.get("body") or ""
                own = [table for table in tables if table["provision"] == path]
                descendant = [
                    table
                    for table in tables
                    if table["provision"] and table["provision"].startswith(path + "/")
                    and table["rows"] and table["rows"].split("\n", 1)[0] in stored
                ]
                if own:
                    body = extracted[(digest, path)]
                    if body is None or body == stored:
                        continue
                    captions = [line for table in own for line in table["caption_lines"]]
                    findings.append(
                        {
                            "citation_path": path,
                            "kind": record.get("kind"),
                            "caption_lines": captions,
                            "caption_only_change": _caption_only_change(stored, body, captions),
                            "source_path": source_path,
                        }
                    )
                elif descendant:
                    missing = [
                        table
                        for table in descendant
                        if "\n".join([*table["caption_lines"], table["rows"].split("\n", 1)[0]])
                        not in stored
                    ]
                    if missing:
                        findings.append(
                            {
                                "citation_path": path,
                                "kind": record.get("kind"),
                                "caption_lines": [
                                    line for table in missing for line in table["caption_lines"]
                                ],
                                "caption_only_change": None,
                                "materialized_from": sorted(
                                    {table["provision"] for table in missing}
                                ),
                                "source_path": source_path,
                            }
                        )
        if findings:
            key = f"{JURISDICTION}/{DOCUMENT_CLASS}/{version}"
            scopes.append(
                {
                    "scope": key,
                    "released_in": released.get(key, []),
                    "record_count": len(findings),
                    "caption_line_count": sum(len(item["caption_lines"]) for item in findings),
                    "records": findings,
                }
            )

    released_scopes = [scope for scope in scopes if scope["released_in"]]
    return {
        "summary": {
            "scopes": len(scopes),
            "released_scopes": len(released_scopes),
            "records": sum(scope["record_count"] for scope in scopes),
            "released_records": sum(scope["record_count"] for scope in released_scopes),
            "records_with_other_changes": sum(
                1
                for scope in scopes
                for item in scope["records"]
                if item["caption_only_change"] is False
            ),
        },
        "scopes": scopes,
    }


def ensure_corpus_inputs(base: Path) -> None:
    """Fetch the locked files the audit reads. Does nothing without locks.

    The audit walks every us/regulation provisions file, so all of them must be
    present (a partly fetched directory would silently shrink the report); then
    it reads the eCFR XML those rows name.
    """
    provisions_dir = (base / "provisions" / JURISDICTION / DOCUMENT_CLASS).absolute()
    require_materialized([provisions_dir], fetch=True)
    sources = sorted(
        {
            record["source_path"]
            for records in _load_records(base).values()
            for record in records
        }
    )
    # Resolved against the checkout holding ``base``, not the working directory.
    require_materialized([(base / source).absolute() for source in sources], fetch=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument(
        "--releases", type=Path, default=REPO_ROOT / "manifests" / "releases",
        help="Directory of named release selectors.",
    )
    parser.add_argument("--output", type=Path, help="Write the JSON report here.")
    args = parser.parse_args()
    ensure_corpus_inputs(args.base)
    report = audit(args.base, args.releases)
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
