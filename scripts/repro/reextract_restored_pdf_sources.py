#!/usr/bin/env python3
"""Re-extract each restored PDF with the code of its original ingest and compare.

For each scope ``scripts/restore_unlocked_pdf_sources.py`` restores, this builds
the axiom-corpus tree of the commit that ingested it (``git archive`` plus
``uv sync --frozen``, so the PyMuPDF that commit locks), points that commit's
extraction manifest at the restored file with ``local_path``, runs
``extract-official-documents`` into a scratch directory, and compares the rows
with the committed ones.

Every field must match except two that depend on fetching rather than on the
PDF: ``metadata.download_url`` (a local run records ``file://``) and
``metadata.content_type`` (taken from the HTTP response). Committed rows that
the extractor does not produce must be hand-segmented ``section`` rows whose
sentences all appear verbatim in the extracted page text (the four New York
TANF units of axiom-corpus#85).

    uv run --extra dev python scripts/repro/reextract_restored_pdf_sources.py [--keep DIR]

Needs network access for ``uv sync`` and, on a cold cache, for R2.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from axiom_corpus.corpus.resolver import require_materialized

REPO = Path(__file__).resolve().parents[2]
TRANSPORT_FIELDS = ("download_url", "content_type")

_spec = importlib.util.spec_from_file_location(
    "restore_unlocked_pdf_sources", REPO / "scripts" / "restore_unlocked_pdf_sources.py"
)
assert _spec and _spec.loader
restore = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = restore
_spec.loader.exec_module(restore)


@dataclass(frozen=True)
class Case:
    scope: str
    commit: str
    manifest: str
    source_id: str


CASES = (
    Case(
        "us-ny/policy/2026-06-05-ny-tanf",
        "5e77f4b27",
        "us-ny-tanf-state-plan.yaml",
        "ny-otda-tanf-state-plan-2024-2026",
    ),
    Case(
        "us-sd/manual/2026-05-27-sd-snap-manual",
        "a5d9b220a",
        "us-sd-snap-manual.yaml",
        "sd-dss-snap-policy-procedure-manual",
    ),
    Case(
        "us-va/manual/2026-05-27-va-snap-manual",
        "a5d9b220a",
        "us-va-snap-manual.yaml",
        "va-dss-snap-full-manual-2025-10-01",
    ),
    Case(
        "us-wi/manual/2026-05-27-wi-foodshare-manual",
        "cbf189403",
        "us-wi-foodshare-manual.yaml",
        "wi-dhs-foodshare-handbook-26-01",
    ),
    # Extracted without --only-source-id, so the run writes the scope version
    # the committed (renamed) artifacts carry.
    Case(
        "us/guidance/2026-07-08-snap-qc-fy2024-technical-documentation",
        "7d18a1102",
        "us-snap-guidance.yaml",
        "snap-qc-fy2024-technical-documentation",
    ),
)


def _rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _without_transport(row: dict[str, Any]) -> dict[str, Any]:
    metadata = {k: v for k, v in (row.get("metadata") or {}).items() if k not in TRANSPORT_FIELDS}
    return {**row, "metadata": metadata}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _tree(commit: str, root: Path) -> Path:
    tree = root / f"axiom-corpus-{commit}"
    if not (tree / ".venv").is_dir():
        tree.mkdir(parents=True, exist_ok=True)
        archive = subprocess.run(
            [
                "git",
                "archive",
                commit,
                "src",
                "pyproject.toml",
                "uv.lock",
                "README.md",
                "LICENSE.txt",
                "manifests",
            ],
            cwd=REPO,
            check=True,
            capture_output=True,
        ).stdout
        subprocess.run(["tar", "-x", "-C", str(tree)], input=archive, check=True)
        subprocess.run(["uv", "sync", "--frozen", "--quiet"], cwd=tree, check=True)
    return tree


def reextract(case: Case, root: Path) -> list[str]:
    restoration = next(r for r in restore.RESTORATIONS if r.scope == case.scope)
    jurisdiction, document_class, version = case.scope.split("/")
    pdf = REPO / "data/corpus" / restoration.source_path
    committed_path = REPO / "data/corpus/provisions" / f"{case.scope}.jsonl"
    require_materialized([pdf, committed_path], repo=REPO, fetch=True)

    tree = _tree(case.commit, root)
    manifest = yaml.safe_load((tree / "manifests" / case.manifest).read_text(encoding="utf-8"))
    (document,) = [d for d in manifest["documents"] if d["source_id"] == case.source_id]
    document["local_path"] = str(pdf)
    run = root / case.scope.replace("/", "__")
    run.mkdir(parents=True, exist_ok=True)
    run_manifest = run / "manifest.yaml"
    run_manifest.write_text(yaml.safe_dump({"documents": [document]}, sort_keys=False), "utf-8")
    subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--quiet",
            "axiom-corpus-ingest",
            "extract-official-documents",
            "--base",
            str(run / "corpus"),
            "--version",
            version,
            "--manifest",
            str(run_manifest),
        ],
        cwd=tree,
        check=True,
        capture_output=True,
    )

    extracted = {
        row["citation_path"]: row
        for row in _rows(
            run / "corpus/provisions" / jurisdiction / document_class / f"{version}.jsonl"
        )
    }
    committed = {row["citation_path"]: row for row in _rows(committed_path)}
    problems = [
        f"{case.scope}: extractor writes {cp}, not committed"
        for cp in extracted.keys() - committed.keys()
    ]
    for cp in sorted(extracted.keys() & committed.keys()):
        if _without_transport(extracted[cp]) != _without_transport(committed[cp]):
            problems.append(f"{case.scope}: {cp} differs beyond {', '.join(TRANSPORT_FIELDS)}")
    page_text = _normalize(" ".join(str(row.get("body") or "") for row in extracted.values()))
    extra = sorted(committed.keys() - extracted.keys())
    for cp in extra:
        row = committed[cp]
        sentences = [
            s
            for s in re.split(r"(?<=[.;:])\s+", _normalize(str(row.get("body") or "")))
            if len(s) > 40
        ]
        if (
            row.get("kind") != "section"
            or not sentences
            or any(s not in page_text for s in sentences)
        ):
            problems.append(
                f"{case.scope}: committed {cp} is not a section cut from the extracted pages"
            )
    same = len(extracted.keys() & committed.keys())
    print(
        f"{case.scope} @ {case.commit}: {same} rows reproduced, {len(extra)} section rows verified, "
        f"{len(problems)} problems"
    )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--keep", type=Path, help="Build and run under this directory and keep it.")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="reextract-") as scratch:
        root = args.keep.resolve() if args.keep else Path(scratch)
        problems = [problem for case in CASES for problem in reextract(case, root)]
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
