#!/usr/bin/env python3
"""Report stored eCFR provisions that lack the table captions the adapter now emits.

Until 2026-10-12 the eCFR adapter's ``_table_text`` read only ``TR`` rows, so
every table's ``<CAPTION>`` was dropped from provision bodies. For every
``ecfr-xml`` record under ``--base`` whose retained source XML holds a captioned
table, this script decides whether the stored body carries that table's caption:

- A section or appendix holding a captioned table is re-rendered from the
  retained bytes with the current adapter (``_section_body``). For each caption
  line, a shortfall in how often it appears as a whole line in the stored body,
  against the re-rendered body, is a missing caption line. Counting caption
  lines only, rather than comparing whole bodies, keeps the answer independent
  of unrelated changes to how other text is rendered.
- A part or subpart whose stored body was materialized from descendants inherits
  the missing lines of each captioned descendant whose stored body it contains.
  Descent is read from the XML (DIV5 part, DIV6 subpart) and from the scope's
  ``parent_citation_path`` links.

``caption_only_change`` records, for a section or appendix with missing lines,
whether the re-rendered body equals the stored body plus inserted lines that are
exactly the missing caption lines. It holds for the adapter that produced this
report; it is evidence for that commit, not a property later adapters keep.

Each scope lists the named releases (``manifests/releases``) that select it. The
script writes no corpus artifacts.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from axiom_corpus.corpus.ecfr import (
    _element_citation_path,
    _local_name,
    _section_body,
    _table_caption_lines,
    _table_text,
)
from axiom_corpus.corpus.resolver import require_materialized

REPO_ROOT = Path(__file__).resolve().parents[1]
ECFR_SOURCE_FORMAT = "ecfr-xml"
JURISDICTION = "us"
DOCUMENT_CLASS = "regulation"


def _container_path(title: int, elem: ET.Element, part: str | None) -> str | None:
    if elem.tag == "DIV5" and elem.get("TYPE") == "PART" and elem.get("N"):
        return f"us/regulation/{title}/{elem.get('N')}"
    if elem.tag == "DIV6" and elem.get("TYPE") == "SUBPART" and elem.get("N") and part:
        return f"us/regulation/{title}/{part}/subpart-{elem.get('N')}"
    return None


def captioned_provisions(root: ET.Element, title: int) -> dict[str, dict[str, Any]]:
    """Sections and appendices holding a captioned table, keyed by citation path.

    Each entry has the provision element, its containers in the XML (part, then
    subpart), and per table the caption lines and the first rendered row.
    """
    parents = {child: parent for parent in root.iter() for child in parent}
    provisions: dict[str, dict[str, Any]] = {}
    for table in root.iter():
        if _local_name(table.tag) != "TABLE":
            continue
        captions = [child for child in table if _local_name(child.tag) == "CAPTION"]
        lines = [line for caption in captions for line in _table_caption_lines(caption)]
        if not lines:
            continue
        ancestry: list[ET.Element] = []
        node = table
        while node in parents:
            node = parents[node]
            ancestry.append(node)
        element = next(
            (node for node in ancestry if _element_citation_path(title, node)), None
        )
        if element is None:
            continue
        path = _element_citation_path(title, element)
        assert path is not None
        part = path.split("/")[3]
        containers = [
            container
            for node in reversed(ancestry)
            if (container := _container_path(title, node, part)) is not None
        ]
        rows = ET.Element(table.tag, table.attrib)
        rows.extend(child for child in table if _local_name(child.tag) != "CAPTION")
        entry = provisions.setdefault(
            path, {"element": element, "containers": containers, "tables": []}
        )
        entry["tables"].append(
            {"caption_lines": lines, "first_row": _table_text(rows).split("\n", 1)[0]}
        )
    return provisions


def missing_caption_lines(
    stored: str, rendered: str, caption_lines: Iterable[str]
) -> list[str]:
    """Caption lines the rendered body carries as whole lines more often than the stored one."""
    stored_counts = Counter(stored.split("\n"))
    rendered_counts = Counter(rendered.split("\n"))
    missing: list[str] = []
    for line in dict.fromkeys(caption_lines):
        missing.extend([line] * max(0, rendered_counts[line] - stored_counts[line]))
    return missing


def caption_only_change(stored: str, rendered: str, missing: list[str]) -> bool:
    stored_lines = stored.split("\n")
    rendered_lines = rendered.split("\n")
    matcher = difflib.SequenceMatcher(None, stored_lines, rendered_lines, autojunk=False)
    inserted: list[str] = []
    for op, _, _, start, end in matcher.get_opcodes():
        if op == "equal":
            continue
        if op != "insert":
            return False
        inserted.extend(rendered_lines[start:end])
    return Counter(line for line in inserted if line) == Counter(missing)


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
    provisions_dir = base / "provisions" / JURISDICTION / DOCUMENT_CLASS
    for provisions_path in sorted(provisions_dir.glob("*.jsonl")):
        rows = [
            json.loads(line)
            for line in provisions_path.read_text().splitlines()
            if line.strip()
        ]
        records[provisions_path.stem] = [
            row for row in rows if row.get("source_format") == ECFR_SOURCE_FORMAT
        ]
    return records


def _ancestors(path: str, parent_of: dict[str, str | None]) -> set[str]:
    seen: set[str] = set()
    parent = parent_of.get(path)
    while parent and parent not in seen:
        seen.add(parent)
        parent = parent_of.get(parent)
    return seen


def _scope_findings(
    base: Path,
    records: list[dict[str, Any]],
    parsed: dict[str, dict[str, dict[str, Any]]],
    rendered: dict[tuple[str, str], str],
) -> list[dict[str, Any]]:
    parent_of = {record["citation_path"]: record.get("parent_citation_path") for record in records}
    by_path = {record["citation_path"]: record for record in records}
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_source[record["source_path"]].append(record)

    findings: list[dict[str, Any]] = []
    for source_path, source_records in sorted(by_source.items()):
        data = (base / source_path).read_bytes()
        if b"<CAPTION" not in data.upper():
            continue
        title = int(source_records[0]["citation_path"].split("/")[2])
        digest = hashlib.sha256(data).hexdigest()
        if digest not in parsed:
            parsed[digest] = captioned_provisions(ET.fromstring(data), title)
        provisions = parsed[digest]

        missing_by_path: dict[str, list[str]] = {}
        for record in source_records:
            path = record["citation_path"]
            provision = provisions.get(path)
            if provision is None:
                continue
            key = (digest, path)
            if key not in rendered:
                rendered[key] = _section_body(
                    provision["element"], appendix=record.get("kind") == "appendix"
                )
            stored = record.get("body") or ""
            captions = [
                line for table in provision["tables"] for line in table["caption_lines"]
            ]
            missing = missing_caption_lines(stored, rendered[key], captions)
            if not missing:
                continue
            missing_by_path[path] = missing
            findings.append(
                {
                    "citation_path": path,
                    "kind": record.get("kind"),
                    "missing_caption_lines": missing,
                    "caption_only_change": caption_only_change(stored, rendered[key], missing),
                    "source_path": source_path,
                }
            )

        for record in source_records:
            path = record["citation_path"]
            body = record.get("body") or ""
            if path in provisions or not body:
                continue
            inherited: list[str] = []
            sources: list[str] = []
            for descendant, provision in provisions.items():
                if path not in provision["containers"] and path not in _ancestors(
                    descendant, parent_of
                ):
                    continue
                stored_descendant = (by_path.get(descendant) or {}).get("body")
                if stored_descendant and stored_descendant in body:
                    lines = missing_by_path.get(descendant, [])
                else:
                    # The descendant is not stored in this scope: look for each
                    # table's first row and its caption block just above it.
                    lines = [
                        line
                        for table in provision["tables"]
                        if table["first_row"] and table["first_row"] in body
                        and "\n".join([*table["caption_lines"], table["first_row"]]) not in body
                        for line in table["caption_lines"]
                    ]
                if lines:
                    inherited.extend(lines)
                    sources.append(descendant)
            if inherited:
                findings.append(
                    {
                        "citation_path": path,
                        "kind": record.get("kind"),
                        "missing_caption_lines": inherited,
                        "caption_only_change": None,
                        "materialized_from": sources,
                        "source_path": source_path,
                    }
                )
    return findings


def audit(base: Path, releases_dir: Path) -> dict[str, Any]:
    released = _release_names(releases_dir)
    # Retained XML is parsed once per distinct byte string; several scopes
    # carry copies of the same snapshot.
    parsed: dict[str, dict[str, dict[str, Any]]] = {}
    rendered: dict[tuple[str, str], str] = {}
    scopes: list[dict[str, Any]] = []
    for version, records in _load_records(base).items():
        findings = _scope_findings(base, records, parsed, rendered)
        if not findings:
            continue
        key = f"{JURISDICTION}/{DOCUMENT_CLASS}/{version}"
        scopes.append(
            {
                "scope": key,
                "released_in": released.get(key, []),
                "record_count": len(findings),
                "missing_caption_line_count": sum(
                    len(item["missing_caption_lines"]) for item in findings
                ),
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
            "missing_caption_lines": sum(
                scope["missing_caption_line_count"] for scope in scopes
            ),
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
