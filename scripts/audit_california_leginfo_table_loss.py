#!/usr/bin/env python3
"""Measure what the default California LegInfo extraction drops, per section.

The ``california-code-sections`` adapter's default body collects every ``<p>`` and
``<i>`` block of a LegInfo page and keeps only the first copy of any repeated
block, so repeated table cells, repeated row labels and repeated statutory
paragraphs disappear. ``--preserve-tables`` renders each table row as one
``cell | cell`` line and drops nothing. For every California LegInfo section
scope under ``--base``, this script re-extracts each retained page both ways and
reports which mode produced the committed bodies, which sections change, and
the blocks the default mode dropped (inside or outside a table). Each body is
also compared, as a multiset of words, with the section's visible text (the
section ``div`` less its ``h6`` number heading): ``*_missing_words`` counts
visible words a body lacks and ``*_extra_words`` counts words a body repeats
beyond the page. The table-preserving body should have zero of both in every
section. It writes no corpus artifacts.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from axiom_corpus.corpus.states import (
    CALIFORNIA_SECTION_HTML_SOURCE_FORMAT,
    _california_html_current_section_div,
    _california_html_section_body,
    _clean_text,
)

_WORD = re.compile(r"\S+")


def _words(text: str | None) -> Counter[str]:
    return Counter(word for word in _WORD.findall(text or "") if word != "|")


def _visible_words(search_root: Tag | BeautifulSoup) -> Counter[str]:
    """Words a reader sees in the section, less the section-number heading."""
    visible = copy.copy(search_root)
    for heading in visible.find_all("h6"):
        heading.decompose()
    return _words(visible.get_text(" ", strip=True))


def audit_section(html: bytes, committed_body: str | None) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    root: Tag | BeautifulSoup = soup.find(id="single_law_section") or soup
    search_root: Tag | BeautifulSoup = _california_html_current_section_div(root) or root
    default_body = _california_html_section_body(root)
    preserve_body = _california_html_section_body(root, preserve_tables=True)

    seen: set[str] = set()
    dropped: list[dict[str, Any]] = []
    for elem in search_root.find_all(["p", "i"]):
        text = _clean_text(elem.get_text(" ", strip=True))
        if not text:
            continue
        if text in seen:
            dropped.append({"text": text, "in_table": elem.find_parent("table") is not None})
        seen.add(text)

    tables = [
        table for table in search_root.find_all("table") if table.find_parent("table") is None
    ]
    visible = _visible_words(search_root)
    default_words = _words(default_body)
    preserve_words = _words(preserve_body)
    if committed_body == default_body == preserve_body:
        mode = "either"
    elif committed_body == default_body:
        mode = "default"
    elif committed_body == preserve_body:
        mode = "preserve-tables"
    else:
        mode = "neither"
    return {
        "committed_mode": mode,
        "tables": len(tables),
        "changed_by_preserve_tables": default_body != preserve_body,
        "default_lines": len((default_body or "").splitlines()),
        "preserve_tables_lines": len((preserve_body or "").splitlines()),
        "dropped_blocks_in_tables": sum(1 for block in dropped if block["in_table"]),
        "dropped_blocks_outside_tables": sum(1 for block in dropped if not block["in_table"]),
        "dropped_blocks": dropped,
        "visible_words": sum(visible.values()),
        "default_missing_words": sum((visible - default_words).values()),
        "default_extra_words": sum((default_words - visible).values()),
        "preserve_tables_missing_words": sum((visible - preserve_words).values()),
        "preserve_tables_extra_words": sum((preserve_words - visible).values()),
    }


def audit_scope(base: Path, provisions_path: Path) -> dict[str, Any] | None:
    records = [
        json.loads(line) for line in provisions_path.read_text().splitlines() if line.strip()
    ]
    records = [
        record
        for record in records
        if record.get("source_format") == CALIFORNIA_SECTION_HTML_SOURCE_FORMAT
    ]
    if not records:
        return None
    sections: dict[str, dict[str, Any]] = {}
    modes: Counter[str] = Counter()
    preserve_gaps: Counter[str] = Counter()
    for record in records:
        entry = audit_section((base / record["source_path"]).read_bytes(), record.get("body"))
        modes[entry["committed_mode"]] += 1
        preserve_gaps["missing"] += entry["preserve_tables_missing_words"]
        preserve_gaps["extra"] += entry["preserve_tables_extra_words"]
        if entry["tables"] or entry["changed_by_preserve_tables"]:
            sections[record["citation_path"]] = entry
    changed = {
        path: entry for path, entry in sections.items() if entry["changed_by_preserve_tables"]
    }
    return {
        "version": provisions_path.stem,
        "document_class": records[0]["document_class"],
        "sections": len(records),
        "committed_modes": dict(sorted(modes.items())),
        "sections_with_tables": sum(1 for entry in sections.values() if entry["tables"]),
        "sections_changed_by_preserve_tables": len(changed),
        "dropped_blocks_in_tables": sum(e["dropped_blocks_in_tables"] for e in changed.values()),
        "dropped_blocks_outside_tables": sum(
            e["dropped_blocks_outside_tables"] for e in changed.values()
        ),
        "default_missing_words": sum(e["default_missing_words"] for e in changed.values()),
        "default_extra_words": sum(e["default_extra_words"] for e in changed.values()),
        "preserve_tables_missing_words": preserve_gaps["missing"],
        "preserve_tables_extra_words": preserve_gaps["extra"],
        "section_details": sections,
    }


def audit(base: Path, jurisdiction: str = "us-ca") -> dict[str, Any]:
    scopes = []
    for provisions_path in sorted((base / "provisions" / jurisdiction).glob("*/*.jsonl")):
        scope = audit_scope(base, provisions_path)
        if scope is not None:
            scopes.append(scope)
    return {"jurisdiction": jurisdiction, "scopes": scopes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--jurisdiction", default="us-ca")
    parser.add_argument("--output", type=Path, help="Write the JSON report here.")
    args = parser.parse_args()
    report = audit(args.base, args.jurisdiction)
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
