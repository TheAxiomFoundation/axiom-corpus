#!/usr/bin/env python3
"""Write the wave-7 federal decisions CSV, one row per work-order row, verified.

Every PRESENT or ALREADY-HELD row must name a citation path that is a row of the
named scope on disk, and every PRESENT scope must report coverage `complete: true`
with no missing, extra or duplicate rows. The run fails closed otherwise.

    uv run python scripts/build_w7_federal_decisions.py \\
      --work-order docs/coverage/program-bundle-gaps-2026-10-12/wave7/federal.csv \\
      --base /Users/pavelmakarchuk/axiom-corpus/data/corpus
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

OUT = Path("docs/ingest-runs/2026-10-12-w7-federal-decisions.csv")
COLUMNS = [
    "id",
    "jurisdiction",
    "programs",
    "action",
    "new_status",
    "scope_version",
    "citation_path",
    "official_url",
    "note",
]
GUIDANCE = "us/guidance/2026-10-12-w7-federal-guidance"
OLRC = "https://uscode.house.gov/download/releasepoints/us/pl/119/120/xml_usc{t:0>2}@119-120.zip"
USC_NOTE = (
    "{title} U.S.C. {section} ({heading}), whole section from OLRC release point 119-120 "
    "(current through Pub. L. 119-120, 2026-10-07; xml_usc{t:0>2}@119-120.zip retained as the "
    "inventoried source); a self-contained root (title parent detached), {rows} rows"
)

DECISIONS: dict[str, tuple[str, str, str, str, str]] = {
    # id: (new_status, scope_version, citation_path, official_url, note)
    "https://www.irs.gov/pub/irs-drop/rp-21-45.pdf": (
        "PRESENT",
        GUIDANCE,
        "us/guidance/irs/rev-proc-2021-45",
        "https://www.irs.gov/pub/irs-drop/rp-21-45.pdf",
        "Rev. Proc. 2021-45, the 2022 inflation-adjusted items (page 1: 'SECTION 3. 2022 ADJUSTED "
        "ITEMS'; 29 pages), one row per page; expression_date 2022-01-01",
    ),
    "https://www.irs.gov/pub/irs-drop/rp-22-38.pdf": (
        "PRESENT",
        GUIDANCE,
        "us/guidance/irs/rev-proc-2022-38",
        "https://www.irs.gov/pub/irs-drop/rp-22-38.pdf",
        "Rev. Proc. 2022-38, the 2023 inflation-adjusted items (page 1: 'SECTION 3. 2023 ADJUSTED "
        "ITEMS'; 28 pages), one row per page; expression_date 2023-01-01",
    ),
    "https://www.acf.hhs.gov/occ/form/approved-ccdf-plans-fy-2025-2027": (
        "PRESENT",
        GUIDANCE,
        "us/guidance/acf/occ/approved-ccdf-plans-fy-2025-2027",
        "https://acf.gov/occ/data/approved-ccdf-plans-fy-2025-2027",
        "ACF OCC 'FY 2025-2027 State/Territory CCDF Plans' (published 2024-12-19, updated "
        "2026-09-01): the bundle address 301-redirects to acf.gov/occ/form/..., which now answers "
        "404 (browser User-Agent) or a 202 AWS WAF challenge (corpus User-Agent); ACF's own site "
        "search lists the same page at acf.gov/occ/data/. Fetched with the browser_user_agent "
        "option documented for acf.gov in docs/ingest-runs/2026-09-13-acf-state-plans.md. The "
        "state plans it links are held in the us-xx/policy CCDF plan scopes",
    ),
    "us/statute/26/subtitle-A": (
        "SKIPPED",
        "",
        "",
        "",
        "replaced by the sections of the parts it names (axiom-corpus#836)",
    ),
    "us/statute/42/chapter-7": (
        "SKIPPED",
        "",
        "",
        "",
        "replaced by the sections of the parts it names (axiom-corpus#836)",
    ),
}

USC_SECTIONS = {
    "us/statute/8/1611": ("8", "1611"),
    "us/statute/8/1645": ("8", "1645"),
    "us/statute/20/1091": ("20", "1091"),
    "us/statute/25/1603": ("25", "1603"),
    "us/statute/25/1679": ("25", "1679"),
    "us/statute/29/206": ("29", "206"),
    "us/statute/29/207": ("29", "207"),
    "us/statute/38/101": ("38", "101"),
}


def read_scope(base: Path, scope: str) -> tuple[dict[str, dict], dict]:
    jur, cls, version = scope.split("/", 2)
    rows: dict[str, dict] = {}
    with (base / "provisions" / jur / cls / f"{version}.jsonl").open() as f:
        for line in f:
            row = json.loads(line)
            rows[row["citation_path"]] = row
    coverage = json.loads((base / "coverage" / jur / cls / f"{version}.json").read_text())
    return rows, coverage


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work-order", type=Path, required=True)
    ap.add_argument("--base", type=Path, required=True)
    args = ap.parse_args()

    with args.work_order.open(newline="") as f:
        orders = list(csv.DictReader(f))
    scopes: dict[str, tuple[dict[str, dict], dict]] = {}
    out = []
    for order in orders:
        doc_id = order["id"]
        if doc_id in USC_SECTIONS:
            title, section = USC_SECTIONS[doc_id]
            scope = f"us/statute/2026-10-12-w7-federal-usc-closure-title-{title}"
            scopes.setdefault(scope, read_scope(args.base, scope))
            rows = scopes[scope][0]
            section_rows = [p for p in rows if p == doc_id or p.startswith(f"{doc_id}/")]
            heading = (rows.get(doc_id) or {}).get("heading") or ""
            decision = (
                "PRESENT",
                scope,
                doc_id,
                OLRC.format(t=title),
                USC_NOTE.format(
                    title=title, section=section, heading=heading, t=title, rows=len(section_rows)
                ),
            )
        else:
            decision = DECISIONS[doc_id]
        status, scope, path, url, note = decision
        if status in {"PRESENT", "ALREADY-HELD"}:
            scopes.setdefault(scope, read_scope(args.base, scope))
            rows, coverage = scopes[scope]
            if path not in rows:
                raise SystemExit(f"{doc_id}: {path} is not a row of {scope}")
            if status == "PRESENT" and not (
                coverage.get("complete")
                and not coverage.get("missing_from_provisions")
                and not coverage.get("extra_provisions")
                and not coverage.get("duplicate_provision_citations")
            ):
                raise SystemExit(f"{doc_id}: coverage of {scope} is not complete")
        out.append(
            {
                "id": doc_id,
                "jurisdiction": order["jurisdiction"],
                "programs": order["programs"],
                "action": order["action"],
                "new_status": status,
                "scope_version": scope,
                "citation_path": path,
                "official_url": url,
                "note": note,
            }
        )
    if [r["id"] for r in out] != [o["id"] for o in orders]:
        raise SystemExit("decisions do not match the work order row for row")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(out)
    counts: dict[str, int] = {}
    for r in out:
        counts[r["new_status"]] = counts.get(r["new_status"], 0) + 1
    print(f"{len(out)} decisions -> {OUT}: {counts}")


if __name__ == "__main__":
    main()
