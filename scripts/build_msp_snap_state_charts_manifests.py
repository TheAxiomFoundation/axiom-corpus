"""Build the 2026-09-14 state chart manifests for the two state-level families the
needs-driven closure check (docs/coverage/needs-closure-2026-09-11) left open, and record
them on the program agent queues.

* Family ``msp`` (medicare.md MED-ST-7, with MED-ST-2/3/4 where the chart carries them): the
  state Medicaid agency's current Medicare Savings Program income and resource standards
  publication (standards chart, income-limits notice, manual appendix or the manual chapter
  that prints the 2026 dollar figures). One scope per state,
  ``us-xx/<manual|guidance>/2026-09-14-msp-income-standards``; the document class follows
  the state's Medicaid precedent (a manual appendix or chapter is ``manual``; a notice,
  bulletin, transmittal or standalone chart is ``guidance``).
* Family ``snap`` (snap.md snap_s20): the state SNAP agency's FY 2026 change transmittal,
  COLA / mass-change notice, policy memorandum or standards table carrying the state's
  applied FY 2026 amounts (effective 2025-10-01). One scope per state,
  ``us-xx/guidance/2026-09-14-snap-fy2026-state-transmittal`` (class ``guidance`` unless
  the state's SNAP precedent says otherwise).

Every document record below was located on the publisher's own site and verified from this
machine on 2026-09-14 (HTTP status, content type, PDF text layer); blocked and absent
jurisdictions are recorded on the queue with their evidence and get no manifest. Every
citation path is checked against every provisions JSONL of its jurisdiction under the
corpus base (``--corpus-base``, default the main checkout) before the manifest is written.

    uv run python scripts/build_msp_snap_state_charts_manifests.py [--family msp,snap] [--only us-co,...]
        [--corpus-base /path/to/data/corpus] [--skip-queue] [--print-plan]
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_BASE = Path("/Users/pavelmakarchuk/axiom-corpus/data/corpus")
SOURCE_AS_OF = "2026-09-14"
RUN_NOTE = "docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.md"
MSP_VERSION = "2026-09-14-msp-income-standards"
SNAP_VERSION = "2026-09-14-snap-fy2026-state-transmittal"
IMPERSONATE = {"browser_impersonation": True, "browser_impersonation_direct": True}

STATE_NAMES = {
    "us-al": "Alabama", "us-ak": "Alaska", "us-az": "Arizona", "us-ar": "Arkansas", "us-ca": "California",
    "us-co": "Colorado", "us-ct": "Connecticut", "us-de": "Delaware", "us-dc": "District of Columbia",
    "us-fl": "Florida", "us-ga": "Georgia", "us-hi": "Hawaii", "us-id": "Idaho", "us-il": "Illinois",
    "us-in": "Indiana", "us-ia": "Iowa", "us-ks": "Kansas", "us-ky": "Kentucky", "us-la": "Louisiana",
    "us-me": "Maine", "us-md": "Maryland", "us-ma": "Massachusetts", "us-mi": "Michigan", "us-mn": "Minnesota",
    "us-ms": "Mississippi", "us-mo": "Missouri", "us-mt": "Montana", "us-ne": "Nebraska", "us-nv": "Nevada",
    "us-nh": "New Hampshire", "us-nj": "New Jersey", "us-nm": "New Mexico", "us-ny": "New York",
    "us-nc": "North Carolina", "us-nd": "North Dakota", "us-oh": "Ohio", "us-ok": "Oklahoma", "us-or": "Oregon",
    "us-pa": "Pennsylvania", "us-ri": "Rhode Island", "us-sc": "South Carolina", "us-sd": "South Dakota",
    "us-tn": "Tennessee", "us-tx": "Texas", "us-ut": "Utah", "us-vt": "Vermont", "us-va": "Virginia",
    "us-wa": "Washington", "us-wv": "West Virginia", "us-wi": "Wisconsin", "us-wy": "Wyoming",
}


@dataclass
class Doc:
    """One official document of a state scope."""

    source_id: str
    title: str
    source_url: str
    citation_path: str
    expression_date: str
    source_format: str = "pdf"
    download_url: str | None = None
    request: dict[str, Any] | None = None
    extraction: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class State:
    """One jurisdiction of one family: its documents (a manifest) or its blocked/absent record."""

    jurisdiction: str
    publisher: str
    index_url: str
    index_document_count: int | None
    source_kind: str
    note: str
    document_class: str = "guidance"
    documents: list[Doc] = field(default_factory=list)
    status: str = "agent_ready"  # agent_ready when documents were taken; blocked_primary_source; needs_review
    blocked_evidence: str | None = None
    index_families: dict[str, dict[str, int]] | None = None
    manifest_name: str | None = None
    pointer_scope: dict[str, str] | None = None  # the selected scope that already holds the document (done rows)


def document_record(state: State, d: Doc, *, program: str, closure_elements: list[str], group: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "source_id": d.source_id,
        "jurisdiction": state.jurisdiction,
        "document_class": state.document_class,
        "title": d.title,
        "source_url": d.source_url,
    }
    if d.download_url:
        out["download_url"] = d.download_url
    out.update({
        "source_format": d.source_format,
        "source_as_of": SOURCE_AS_OF,
        "expression_date": d.expression_date,
        "citation_path": d.citation_path,
    })
    if d.request:
        out["request"] = dict(d.request)
    if d.extraction:
        out["extraction"] = dict(d.extraction)
    out["metadata"] = {
        "primary_source": True,
        "source_authority": state.publisher,
        "program": program,
        "source_discovery_group": group,
        "index_url": state.index_url,
        "closure_elements": list(closure_elements),
        "discovered_via": "manual-review; needs-closure-2026-09-11 " + "/".join(closure_elements),
        **d.metadata,
    }
    return out


def corpus_citation_paths(corpus_base: Path | None, jurisdiction: str, *, exclude_version: str) -> set[str]:
    """Every citation_path in every provisions JSONL of the jurisdiction (all document classes,
    all versions) except the scope being regenerated. Empty when no corpus base is available."""
    if corpus_base is None or not corpus_base.exists():
        return set()
    paths: set[str] = set()
    for jsonl in sorted((corpus_base / "provisions" / jurisdiction).glob("*/*.jsonl")):
        if jsonl.stem == exclude_version:
            continue
        with jsonl.open() as handle:
            for line in handle:
                if line.strip():
                    paths.add(json.loads(line)["citation_path"])
    return paths


# ------------------------------------------------------------------------------------ MSP
MSP_GROUP_ELEMENTS = ["MED-ST-7"]


def msp_states() -> list[State]:
    from msp_snap_state_chart_records import MSP_STATES  # records module beside this script

    return MSP_STATES


def snap_states() -> list[State]:
    from msp_snap_state_chart_records import SNAP_STATES

    return SNAP_STATES


FAMILIES: dict[str, dict[str, Any]] = {
    "msp": {
        "version": MSP_VERSION,
        "program": "MEDICARE_SAVINGS_PROGRAMS",
        "queue": "medicare-agent-queue.yaml",
        "record_key": "msp_income_standards_scope",
        "manifest_suffix": "msp-income-standards-2026",
        "states": msp_states,
        "closure_elements": MSP_GROUP_ELEMENTS,
    },
    "snap": {
        "version": SNAP_VERSION,
        "program": "SNAP",
        "queue": "snap-completion-agent-queue.yaml",
        "record_key": "fy2026_state_transmittal_scope",
        "manifest_suffix": "snap-fy2026-state-transmittal",
        "states": snap_states,
        "closure_elements": ["snap_s20"],
    },
}


def write_manifest(state: State, family: dict[str, Any]) -> Path | None:
    if not state.documents:
        return None
    name = state.manifest_name or f"{state.jurisdiction}-{family['manifest_suffix']}.yaml"
    group = f"{state.jurisdiction}/{state.document_class}"
    docs = [
        document_record(state, d, program=family["program"], closure_elements=family["closure_elements"], group=group)
        for d in state.documents
    ]
    path = ROOT / "manifests" / name
    path.write_text(
        yaml.safe_dump({"version": family["version"], "documents": docs}, sort_keys=False, allow_unicode=True, width=120)
    )
    return path


def queue_row(state: State, family: dict[str, Any], manifest: Path | None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "jurisdiction": state.jurisdiction,
        "name": STATE_NAMES[state.jurisdiction],
        "lead_counts": {},
        "candidate_sources": [],
        "queue_status": state.status,
        "source_kind": state.source_kind,
        "primary_source_url": state.documents[0].source_url if state.documents else state.index_url,
        "target_manifest": str(manifest.relative_to(ROOT)) if manifest else None,
        "target_scope": (
            {"jurisdiction": state.jurisdiction, "document_class": state.document_class, "version": family["version"]}
            if state.documents
            else state.pointer_scope
        ),
        "index_url": state.index_url,
        "index_document_count": state.index_document_count if state.index_document_count is not None else 0,
        "taken_count": len(state.documents),
        "index_families": state.index_families
        or {family["record_key"]: {"found": state.index_document_count or 0, "taken": len(state.documents)}},
        "closure_elements": list(family["closure_elements"]),
        "run_note": RUN_NOTE,
    }
    if state.documents:
        row["citation_paths"] = [d.citation_path for d in state.documents]
    if state.pointer_scope and not state.documents:
        row["pointer"] = f"{state.pointer_scope['jurisdiction']}/{state.pointer_scope['document_class']}/{state.pointer_scope['version']}"
    if state.blocked_evidence:
        row["blocked_evidence"] = state.blocked_evidence
    row["notes"] = f"2026-09-14 closure run ({RUN_NOTE}): {state.note}"
    return row


def update_queue(queue_name: str, rows: list[dict[str, Any]], version: str) -> dict[str, int]:
    """Append one row per jurisdiction for this family; a rerun replaces the row this run wrote
    for the same jurisdiction (matched on run_note and closure elements) and leaves every other
    row untouched."""
    path = ROOT / "manifests" / queue_name
    queue = yaml.safe_load(path.read_text())
    states: list[dict[str, Any]] = queue["states"]
    for row in rows:
        for index, existing in enumerate(states):
            if (
                existing.get("jurisdiction") == row["jurisdiction"]
                and existing.get("run_note") == RUN_NOTE
                and existing.get("closure_elements") == row["closure_elements"]
            ):
                states[index] = row
                break
        else:
            states.append(row)
    counts: dict[str, int] = {}
    for existing in states:
        counts[existing["queue_status"]] = counts.get(existing["queue_status"], 0) + 1
    queue["status_counts"] = counts
    path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--family", default="msp,snap", help="comma-separated families (msp, snap)")
    parser.add_argument("--only", help="comma-separated jurisdictions (us-co,...)")
    parser.add_argument("--corpus-base", type=Path, default=DEFAULT_CORPUS_BASE)
    parser.add_argument("--skip-queue", action="store_true")
    parser.add_argument("--print-plan", action="store_true", help="print the per-state plan and exit")
    args = parser.parse_args()
    only = set(args.only.split(",")) if args.only else None
    for family_name in args.family.split(","):
        family = FAMILIES[family_name]
        states: list[State] = family["states"]()
        if only:
            states = [s for s in states if s.jurisdiction in only]
        rows = []
        for state in states:
            if args.print_plan:
                print(f"{family_name} {state.jurisdiction} {state.status} {state.document_class} "
                      f"{len(state.documents)} docs: {[d.citation_path for d in state.documents]}")
                continue
            paths = [d.citation_path for d in state.documents]
            assert len(paths) == len(set(paths)), f"{state.jurisdiction}: duplicate citation paths"
            existing = corpus_citation_paths(args.corpus_base, state.jurisdiction, exclude_version=family["version"])
            collisions = sorted(set(paths) & existing)
            assert not collisions, f"{state.jurisdiction}: citation paths already in the corpus: {collisions}"
            manifest = write_manifest(state, family)
            if manifest:
                print(f"{family_name} {state.jurisdiction}: wrote {manifest.relative_to(ROOT)} "
                      f"({len(state.documents)} documents, checked against {len(existing)} corpus paths)")
            else:
                print(f"{family_name} {state.jurisdiction}: {state.status}, no manifest")
            rows.append(queue_row(state, family, manifest))
        if rows and not args.skip_queue:
            counts = update_queue(family["queue"], rows, family["version"])
            print(f"  queue {family['queue']}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
