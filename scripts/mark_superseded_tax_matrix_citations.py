#!/usr/bin/env python3
"""Point stale 2026-09-11 tax-matrix citations at the scopes that now carry the text.

``docs/coverage/needs-closure-2026-09-11/tax-matrix.csv`` records, per element,
the row of the 2026-09-11 union that carried it. For six states that row is in a
July 2026 recovery scope that the 2026-09-14 wave4 line swapped out for a
whole-chapter scope: CA (axiom-corpus#748) and ME, MI, MN, NY, UT
(axiom-corpus#757). Those audits show the chapter scopes carry the cited
sections: the same text, except MI, whose chapter scope holds later, amended
text of 206.30 and 206.51.

The matrix is a dated snapshot, and ``verify_matrices.py`` checks each PRESENT
row against the 2026-09-11 selector, so ``scope_version`` and ``citation_path``
stay as they were. This script appends to each such row's ``evidence_note`` the
path that carries the section in the chapter scope: the longest prefix of the
cited path that is a row there. It is idempotent.

    uv run --extra dev python scripts/mark_superseded_tax_matrix_citations.py
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

from axiom_corpus.corpus.resolver import ensure_corpus_paths

MATRIX = Path("docs/coverage/needs-closure-2026-09-11/tax-matrix.csv")
RECOVERY = "2026-07-13-recovery"
# jurisdiction -> (the whole-chapter statute scope the wave4 line selects, audit PR)
CARRIERS: dict[str, tuple[str, int]] = {
    "us-ca": ("2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7", 748),
    "us-me": ("2026-09-14-income-tax-chapter-us-me-title-36", 757),
    "us-mi": ("2026-09-14-income-tax-chapter-us-mi-chapter-206", 757),
    "us-mn": ("2026-09-14-income-tax-chapter-us-mn-title-290", 757),
    "us-ny": ("2026-09-14-income-tax-chapter", 757),
    "us-ut": ("2026-09-14-income-tax-chapter-title-59", 757),
}
MARKER = " [superseded after this cut:"


def carrier_paths(base: Path, jurisdiction: str) -> set[str]:
    version = CARRIERS[jurisdiction][0]
    path = base / "provisions" / jurisdiction / "statute" / f"{version}.jsonl"
    # Corpus files are fetched, not tracked: fetch this locked file if absent.
    ensure_corpus_paths([path.absolute()])
    return {
        json.loads(line)["citation_path"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    }


def carried_at(citation_path: str, carried: set[str]) -> str | None:
    """The longest prefix of ``citation_path`` that is a row of the carrier."""
    parts = citation_path.split("/")
    for end in range(len(parts), 2, -1):
        candidate = "/".join(parts[:end])
        if candidate in carried:
            return candidate
    return None


def pointer(jurisdiction: str, path: str) -> str:
    version, pr = CARRIERS[jurisdiction]
    return (
        f"{MARKER} the 2026-09-14 line carries this section as {path} in "
        f"{jurisdiction}/statute/{version}; see axiom-corpus#{pr}]"
    )


def mark(text: str, base: Path) -> str:
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    column = {name: index for index, name in enumerate(header)}
    carried: dict[str, set[str]] = {}
    for row in rows[1:]:
        jurisdiction = row[column["jurisdiction"]]
        if jurisdiction not in CARRIERS or row[column["scope_version"]] != RECOVERY:
            continue
        note = row[column["evidence_note"]]
        if MARKER in note:
            continue
        if jurisdiction not in carried:
            carried[jurisdiction] = carrier_paths(base, jurisdiction)
        path = carried_at(row[column["citation_path"]], carried[jurisdiction])
        if path is None:
            raise ValueError(f"no carrier row for {row[column['citation_path']]}")
        row[column["evidence_note"]] = note + pointer(jurisdiction, path)
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return out.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--matrix", type=Path, default=MATRIX)
    args = parser.parse_args()
    with args.matrix.open(encoding="utf-8", newline="") as handle:
        text = handle.read()
    marked = mark(text, args.base)
    with args.matrix.open("w", encoding="utf-8", newline="") as handle:
        handle.write(marked)
    print(f"marked {marked.count(MARKER) - text.count(MARKER)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
