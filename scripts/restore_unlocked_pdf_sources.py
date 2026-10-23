#!/usr/bin/env python3
"""Restore PDF sources that committed provision rows name but no lock lists.

Five scopes committed pdf provision rows without the PDF they were extracted
from. The original bytes survived (in R2 under another scope's lock, or in the
checkout that ran the ingest); each restoration below names them by sha256.
The evidence for each is in
``docs/ingest-runs/2026-10-13-restore-unlocked-pdf-sources.md``.

The script places each file at the ``source_path`` its rows name, taking the
bytes from the shared cache, R2, or a local file passed with ``--from``. Every
source is checked against the expected sha256 and size before anything is
placed. For the SNAP QC technical documentation it also completes a rename the
ingest left half done: the artifacts were committed under the scope version,
but their contents still carry the extractor's run id (the version with the
source id appended) as ``version`` and in ``source_path``.

Afterwards, sign each scope from a clean tracked tree::

    uv run axiom-corpus-ingest sign-ingest-manifest --jurisdiction J \\
        --document-class C --version V --command "..." --lock --push

``--check`` places and rewrites nothing; it reports whether every row of the
five scopes names a present file with the expected bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.content_store import materialize_entry
from axiom_corpus.corpus.corpus_locks import LockEntry
from axiom_corpus.corpus.resolver import CorpusResolver, require_materialized

REPO = Path(__file__).resolve().parents[1]
CORPUS = "data/corpus"


@dataclass(frozen=True)
class Restoration:
    jurisdiction: str
    document_class: str
    version: str
    source_path: str
    sha256: str
    size: int

    @property
    def scope(self) -> str:
        return f"{self.jurisdiction}/{self.document_class}/{self.version}"


SNAP_QC_VERSION = "2026-07-08-snap-qc-fy2024-technical-documentation"
SNAP_QC_RUN_ID = f"{SNAP_QC_VERSION}-snap-qc-fy2024-technical-documentation"
SNAP_QC_PDF = "official-documents/snap-qc-fy2024-technical-documentation.pdf"

RESTORATIONS = (
    Restoration(
        "us-ny",
        "policy",
        "2026-06-05-ny-tanf",
        "sources/us-ny/policy/2026-06-05-ny-tanf/official-documents/"
        "ny-otda-tanf-state-plan-2024-2026.pdf",
        "f222c3316f975a3a9281846e724ee3ce2c34878d14fe073f24def5c057f94c2f",
        856867,
    ),
    Restoration(
        "us-sd",
        "manual",
        "2026-05-27-sd-snap-manual",
        "sources/us-sd/manual/2026-05-27-sd-snap-manual/official-documents/"
        "sd-dss-snap-policy-procedure-manual.pdf",
        "9b2d299bf6637787306c3ba8571fb19aa5a64e2f24e42b265abb328bd5f3cba9",
        2749383,
    ),
    Restoration(
        "us-va",
        "manual",
        "2026-05-27-va-snap-manual",
        "sources/us-va/manual/2026-05-27-va-snap-manual/official-documents/"
        "va-dss-snap-full-manual-2025-10-01.pdf",
        "9868c25c0d17685234301783bc1833b4dab494d2380b050ab0dffb73dc4e8d8a",
        8147430,
    ),
    Restoration(
        "us-wi",
        "manual",
        "2026-05-27-wi-foodshare-manual",
        "sources/us-wi/manual/2026-05-27-wi-foodshare-manual/official-documents/"
        "wi-dhs-foodshare-handbook-26-01.pdf",
        "6e76d7710eee559264bf019adadd5b9faa15ed79cf7a74311e245e54ab2850d7",
        2685819,
    ),
    Restoration(
        "us",
        "guidance",
        SNAP_QC_VERSION,
        f"sources/us/guidance/{SNAP_QC_VERSION}/{SNAP_QC_PDF}",
        "59b6999d1b9e51ebe920e00899d9aab066d69f1227ea83b0a3e9f16fd8137e33",
        4345993,
    ),
)


@dataclass(frozen=True)
class RunIdRename:
    """Point a scope's contents at the scope version instead of the run id."""

    jurisdiction: str
    document_class: str
    version: str
    run_id: str

    def _path(self, version: str) -> str:
        return f"sources/{self.jurisdiction}/{self.document_class}/{version}/{SNAP_QC_PDF}"

    @property
    def old_source_path(self) -> str:
        return self._path(self.run_id)

    @property
    def new_source_path(self) -> str:
        return self._path(self.version)


SNAP_QC_RENAME = RunIdRename("us", "guidance", SNAP_QC_VERSION, SNAP_QC_RUN_ID)


class RestoreError(RuntimeError):
    pass


def _swap_once(text: str, old: str, new: str, *, where: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RestoreError(f"{where}: expected {old!r} exactly once, found {count}")
    return text.replace(old, new)


def _field(name: str, value: str) -> str:
    return f"{json.dumps(name)}: {json.dumps(value)}"


def rename_provisions(payload: str, rename: RunIdRename) -> str:
    """Rewrite ``version`` and ``source_path`` on every row, nothing else.

    Substitutes the serialized fields in place, so each row keeps its key order
    and spacing, and fails unless every row names the run id exactly once per
    field and parses back to the same row with only those two fields changed.
    """
    lines = payload.splitlines(keepends=True)
    out: list[str] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            out.append(line)
            continue
        where = f"provisions line {number}"
        row = json.loads(line)
        if row.get("version") != rename.run_id or row.get("source_path") != rename.old_source_path:
            raise RestoreError(f"{where} does not name the run id {rename.run_id}")
        new_line = _swap_once(
            line,
            _field("version", rename.run_id),
            _field("version", rename.version),
            where=where,
        )
        new_line = _swap_once(
            new_line,
            _field("source_path", rename.old_source_path),
            _field("source_path", rename.new_source_path),
            where=where,
        )
        expected = {**row, "version": rename.version, "source_path": rename.new_source_path}
        if json.loads(new_line) != expected:
            raise RestoreError(f"{where} changed beyond version and source_path")
        out.append(new_line)
    return "".join(out)


def rename_inventory(payload: str, rename: RunIdRename) -> str:
    """Rewrite ``source_path`` on every inventory item, nothing else."""
    inventory = json.loads(payload)
    items = inventory.get("items")
    if not isinstance(items, list) or not items:
        raise RestoreError("inventory has no items")
    if any(item.get("source_path") != rename.old_source_path for item in items):
        raise RestoreError(f"inventory items do not all name {rename.old_source_path}")
    old = _field("source_path", rename.old_source_path)
    if payload.count(old) != len(items) or payload.count(rename.run_id) != len(items):
        raise RestoreError("inventory names the run id outside item source paths")
    rewritten = payload.replace(old, _field("source_path", rename.new_source_path))
    expected = {
        **inventory,
        "items": [{**item, "source_path": rename.new_source_path} for item in items],
    }
    if json.loads(rewritten) != expected:
        raise RestoreError("inventory changed beyond item source paths")
    return rewritten


def rename_coverage(payload: str, rename: RunIdRename) -> str:
    """Rewrite the coverage report's ``version``, nothing else."""
    coverage = json.loads(payload)
    if coverage.get("version") != rename.run_id:
        raise RestoreError(f"coverage version is not the run id {rename.run_id}")
    rewritten = _swap_once(
        payload,
        _field("version", rename.run_id),
        _field("version", rename.version),
        where="coverage",
    )
    if rename.run_id in rewritten:
        raise RestoreError("coverage names the run id outside its version")
    if json.loads(rewritten) != {**coverage, "version": rename.version}:
        raise RestoreError("coverage changed beyond its version")
    return rewritten


def _artifact_paths(repo: Path, rename: RunIdRename) -> dict[str, Path]:
    scope = f"{rename.jurisdiction}/{rename.document_class}/{rename.version}"
    return {
        "provisions": repo / CORPUS / "provisions" / f"{scope}.jsonl",
        "inventory": repo / CORPUS / "inventory" / f"{scope}.json",
        "coverage": repo / CORPUS / "coverage" / f"{scope}.json",
    }


REWRITERS = {
    "provisions": rename_provisions,
    "inventory": rename_inventory,
    "coverage": rename_coverage,
}


def apply_rename(repo: Path, rename: RunIdRename) -> list[str]:
    """Rewrite the scope's artifacts; a file already rewritten is left as is."""
    changed: list[str] = []
    for kind, path in _artifact_paths(repo, rename).items():
        text = path.read_text(encoding="utf-8")
        if rename.run_id not in text:
            continue
        path.write_text(REWRITERS[kind](text, rename), encoding="utf-8")
        changed.append(path.relative_to(repo).as_posix())
    return changed


def _sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def place(repo: Path, restoration: Restoration, from_file: Path | None) -> str:
    resolver = CorpusResolver(repo)
    if from_file is not None:
        resolver.cache.add_file(from_file, sha256=restoration.sha256, size=restoration.size)
    entry = LockEntry(
        path=f"{CORPUS}/{restoration.source_path}",
        sha256=restoration.sha256,
        size=restoration.size,
    )
    state, source, _method = materialize_entry(
        repo, entry, resolver.cache, resolver.sources, verify=True
    )
    if state == "modified":
        raise RestoreError(f"{entry.path} exists with other bytes; not replacing it")
    return f"{entry.path}: {state}" + (f" from {source}" if source else "")


def check(repo: Path) -> list[str]:
    """Return problems: rows naming a missing file or other bytes than expected."""
    problems: list[str] = []
    for restoration in RESTORATIONS:
        provisions = repo / CORPUS / "provisions" / f"{restoration.scope}.jsonl"
        named: set[str] = set()
        for line in provisions.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row: dict[str, Any] = json.loads(line)
                named.add(str(row.get("source_path")))
        if named != {restoration.source_path}:
            problems.append(f"{restoration.scope}: rows name {sorted(named)}")
            continue
        target = repo / CORPUS / restoration.source_path
        if not target.is_file():
            problems.append(f"{restoration.scope}: {target.relative_to(repo)} is missing")
        elif _sha256(target) != (restoration.sha256, restoration.size):
            problems.append(f"{restoration.scope}: {target.relative_to(repo)} has other bytes")
    return problems


def _parse_from(values: list[str]) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    for value in values:
        sha256, sep, path = value.partition("=")
        if not sep or len(sha256) != 64:
            raise SystemExit(f"--from takes SHA256=PATH, got {value!r}")
        sources[sha256] = Path(path).expanduser()
    return sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument(
        "--from",
        dest="from_files",
        action="append",
        default=[],
        metavar="SHA256=PATH",
        help="Local file holding the bytes for one restoration (verified before use).",
    )
    parser.add_argument("--check", action="store_true", help="Verify only; change nothing.")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    from_files = _parse_from(args.from_files)
    unknown = set(from_files) - {r.sha256 for r in RESTORATIONS}
    if unknown:
        raise SystemExit(f"--from names no restoration: {sorted(unknown)}")

    # Fetching the scopes' locked artifacts changes no tracked state.
    require_materialized(
        [
            repo / CORPUS / kind / f"{r.scope}{suffix}"
            for r in RESTORATIONS
            for kind, suffix in (
                ("provisions", ".jsonl"),
                ("inventory", ".json"),
                ("coverage", ".json"),
            )
        ],
        repo=repo,
        fetch=True,
    )
    if not args.check:
        for path in apply_rename(repo, SNAP_QC_RENAME):
            print(f"rewrote {path}")
        for restoration in RESTORATIONS:
            print(place(repo, restoration, from_files.get(restoration.sha256)))

    problems = check(repo)
    for problem in problems:
        print(problem, file=sys.stderr)
    if not problems:
        print(
            f"{len(RESTORATIONS)} scopes: every row names a present source with the expected bytes."
        )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
