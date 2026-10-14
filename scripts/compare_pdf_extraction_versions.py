#!/usr/bin/env python3
"""Measure what a PyMuPDF version change does to PDF extraction across the corpus.

A PyMuPDF release can read the same PDF differently, so moving the version
`uv.lock` pins can change the text extracted from sources the corpus already
holds (docs/dependency-lock.md). This script measures that before a move. It
reads the fetched corpus (`axiom-corpus-ingest corpus fetch --all`).

    # 1. Once: what to re-extract.
    uv run python scripts/compare_pdf_extraction_versions.py plan --out plan.jsonl

    # 2. In each environment: the locked one, and one that differs from the
    #    lock only in PyMuPDF (uv export --frozen, then install the other one).
    uv run python scripts/compare_pdf_extraction_versions.py snapshot \\
        --plan plan.jsonl --out locked.jsonl
    PYTHONPATH=src other-venv/bin/python scripts/compare_pdf_extraction_versions.py \\
        snapshot --plan plan.jsonl --out candidate.jsonl

    # 3. Compare the two with each other and with the committed provisions.
    uv run python scripts/compare_pdf_extraction_versions.py compare \\
        --plan plan.jsonl --locked locked.jsonl --candidate candidate.jsonl

The plan has two kinds of task:

- ``document``: one PDF source that committed ``source_format: pdf`` provision
  rows name. A snapshot runs the official-document extractor
  (``documents._extract_blocks``) on the stored bytes once for each extraction
  configuration the manifests at HEAD give its ``source_id``, and records a
  digest of every block. ``compare`` counts the documents whose blocks differ
  between the snapshots, and how many committed rows each snapshot reproduces.
  Where a ``source_id`` has several configurations, ``compare`` compares one
  (the one that extracts on both snapshots and reproduces the most committed
  rows); a difference in another configuration is not counted. Configurations
  are told apart by ``citation_path`` and ``extraction``; a manifest row's
  ``title`` changes only block headings, and both snapshots use the same row.
- ``pdf``: one distinct PDF file under ``data/corpus/sources``. A snapshot
  records per-page digests of ``get_text()``, ``get_text("text", sort=True)``
  and ``get_text("words")``, the calls the statute adapters make. ``compare``
  counts the pages that differ.

Both kinds record the SHA-256 of the bytes they read, and ``compare`` sets
aside any task whose snapshots read different bytes (or bytes other than the
lock's), so a fetch or a branch switch between the two runs cannot pass for a
PyMuPDF difference.

The manifests and extractor at HEAD are not always the ones that wrote a
committed row, so some committed rows are reproduced by neither snapshot. Those
say nothing about the PyMuPDF version, and ``compare`` counts them apart.

Each task runs in a worker process that the parent kills after ``--timeout``
seconds; a task whose worker dies or is killed gets a record saying so, and the
run goes on with a new worker. Snapshots are JSONL, written and flushed per
task by the parent. A rerun skips finished tasks; ``--retry-errors`` also reruns
tasks recorded as timed out or as killing their worker. ``compare`` reads the
last record of each task.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Iterator
from contextlib import suppress
from dataclasses import dataclass
from multiprocessing.connection import Connection, wait
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DIGEST_CHARS = 16
# A document snapshot's block entry.
PATH, HEADING, BODY, BODY_LENGTH, NONSPACE, NONSPACE_LENGTH, METADATA = range(7)
# A pdf snapshot's page entry: get_text() (its digest, the digest and length of
# its non-space characters), get_text("text", sort=True) (digest, non-space
# digest), get_text("words") (digest of the words joined by spaces).
TEXT, TEXT_NONSPACE, TEXT_NONSPACE_LENGTH, SORTED, SORTED_NONSPACE, WORDS = range(6)
# Errors a rerun with --retry-errors runs again: the task, not its extraction,
# failed (the worker was killed at the time limit, or died).
RETRYABLE_ERROR_PREFIXES = ("timeout after", "worker exited")
# A worker process is replaced after this many tasks, to bound memory growth.
TASKS_PER_WORKER = 100

TaskFunction = Callable[[dict[str, Any], str], dict[str, Any]]


def digest(text: str) -> str:
    """Short SHA-256 of ``text``; equal digests are read as equal text."""
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:DIGEST_CHARS]


def nonspace(text: str) -> str:
    return "".join(text.split())


# --------------------------------------------------------------------------- plan


def _locked_files(root: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (scope, lock entry) for every file the corpus locks name."""
    for lock_path in sorted((root / ".axiom" / "corpus-locks").glob("*/*/*.json")):
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        scope = f"{lock['jurisdiction']}/{lock['document_class']}/{lock['version']}"
        for entry in lock["files"]:
            yield scope, entry


def _tracked_manifests(root: Path) -> list[Path]:
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "manifests/*.yaml", "manifests/*.yml"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    # Official-document manifests sit directly under manifests/.
    return [root / name for name in listed if name.count("/") == 1]


def _manifest_rows(root: Path) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    """Index official-document manifest rows by (jurisdiction, class, source_id)."""
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    index: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for path in _tracked_manifests(root):
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=loader)  # noqa: S506
        documents = data.get("documents") if isinstance(data, dict) else None
        if not isinstance(documents, list):
            continue
        for row in documents:
            if not isinstance(row, dict) or "source_id" not in row or "jurisdiction" not in row:
                continue
            key = (
                str(row["jurisdiction"]),
                str(row.get("document_class", "policy")),
                str(row["source_id"]),
            )
            index[key].append({"manifest": path.relative_to(root).as_posix(), "row": row})
    return index


def _config_identity(row: dict[str, Any]) -> str:
    """Two manifest rows with these equal extract the same block bodies from the same bytes."""
    return json.dumps(
        [row.get("citation_path"), row.get("extraction")], sort_keys=True, default=str
    )


def build_plan(root: Path) -> list[dict[str, Any]]:
    manifest_rows = _manifest_rows(root)
    locked = list(_locked_files(root))
    locked_sha256 = {entry["path"]: entry["sha256"] for _, entry in locked}
    tasks: list[dict[str, Any]] = []
    pdfs: dict[str, str] = {}
    for scope, entry in locked:
        path = entry["path"]
        if path.startswith("data/corpus/sources/") and path.lower().endswith(".pdf"):
            # One task per distinct file; of the paths holding it, the first by name.
            pdfs[entry["sha256"]] = min(path, pdfs.get(entry["sha256"], path))
        if not path.startswith("data/corpus/provisions/"):
            continue
        jurisdiction, document_class, _version = scope.split("/", 2)
        sources: Counter[tuple[str, str]] = Counter()
        with (root / path).open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                if str(row.get("source_format")) == "pdf":
                    sources[(str(row.get("source_path")), str(row.get("source_id")))] += 1
        for (source_path, source_id), rows in sorted(sources.items()):
            candidates = []
            seen = set()
            for item in manifest_rows.get((jurisdiction, document_class, source_id), []):
                if str(item["row"].get("source_format") or "pdf") != "pdf":
                    continue
                identity = _config_identity(item["row"])
                if identity not in seen:
                    seen.add(identity)
                    candidates.append(item)
            tasks.append(
                {
                    "kind": "document",
                    "key": f"{scope}|{source_path}|{source_id}",
                    "scope": scope,
                    "provisions_path": path,
                    "source_path": source_path,
                    "source_sha256": locked_sha256.get(f"data/corpus/{source_path}"),
                    "source_id": source_id,
                    "rows": rows,
                    "ocr": any(
                        (item["row"].get("extraction") or {}).get(setting)
                        for item in candidates
                        for setting in ("ocr", "force_ocr")
                    ),
                    "candidates": candidates,
                }
            )
    tasks.extend(
        {"kind": "pdf", "key": sha256, "path": path}
        for sha256, path in sorted(pdfs.items(), key=lambda item: item[1])
    )
    return tasks


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Records of a JSONL file; a torn last line (a run killed mid-write) is skipped."""
    records = []
    lines = path.read_text(encoding="utf-8").split("\n")
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            if number == len(lines):
                continue
            raise
    return records


def _latest(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The last record of each task (a retried task has more than one)."""
    return {record["key"]: record for record in records}


# ----------------------------------------------------------------------- snapshot


def _quiet_mupdf() -> None:
    import fitz

    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)


def pymupdf_versions() -> dict[str, str]:
    import fitz

    return {"pymupdf": str(fitz.VersionBind), "mupdf": str(fitz.mupdf_version)}


def _default_candidate(task: dict[str, Any]) -> dict[str, Any]:
    """The extractor's default (one block per page) for a source no manifest names."""
    jurisdiction, document_class, _version = task["scope"].split("/", 2)
    return {
        "manifest": None,
        "row": {
            "source_id": task["source_id"],
            "jurisdiction": jurisdiction,
            "document_class": document_class,
            "title": task["source_id"],
            "source_url": "about:blank",
        },
    }


def snapshot_document(task: dict[str, Any], root: str) -> dict[str, Any]:
    from axiom_corpus.corpus import documents

    _quiet_mupdf()
    started = time.monotonic()
    result: dict[str, Any] = {"key": task["key"], "candidates": []}
    try:
        content = (Path(root) / "data" / "corpus" / task["source_path"]).read_bytes()
    except OSError as exc:
        result["error"] = f"read: {exc!r}"[:300]
        return result
    result["pdf_sha256"] = hashlib.sha256(content).hexdigest()
    for candidate in task["candidates"] or [_default_candidate(task)]:
        entry: dict[str, Any] = {
            "manifest": candidate["manifest"],
            "config": digest(_config_identity(candidate["row"])),
        }
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                source = documents.OfficialDocumentSource.from_mapping(candidate["row"])
                blocks = documents._extract_blocks(
                    content,
                    "pdf",
                    source_url=source.source_url,
                    title=source.title,
                    extraction=source.extraction,
                )
                entry["blocks"] = [
                    [
                        documents._block_citation_path(source, block),
                        digest(block.heading or ""),
                        digest(block.body or ""),
                        len(block.body or ""),
                        digest(nonspace(block.body or "")),
                        len(nonspace(block.body or "")),
                        digest(json.dumps(block.metadata, sort_keys=True, default=str)),
                    ]
                    for block in blocks
                ]
            entry["warnings"] = len(caught)
            if caught:
                entry["warning_digest"] = digest("\n".join(str(item.message) for item in caught))
        except Exception as exc:  # noqa: BLE001 - recorded and compared, not hidden
            entry["error"] = f"{type(exc).__name__}: {exc}"[:400]
        result["candidates"].append(entry)
    result["seconds"] = round(time.monotonic() - started, 3)
    return result


def snapshot_pdf(task: dict[str, Any], root: str) -> dict[str, Any]:
    import fitz

    _quiet_mupdf()
    started = time.monotonic()
    path = Path(root) / task["path"]
    result: dict[str, Any] = {"key": task["key"], "path": task["path"]}
    try:
        with path.open("rb") as handle:
            result["pdf_sha256"] = hashlib.file_digest(handle, "sha256").hexdigest()
        with fitz.open(str(path)) as document:
            result["page_count"] = document.page_count
            pages = []
            for page in document:
                text = str(page.get_text())
                sorted_text = str(page.get_text("text", sort=True))
                words = " ".join(str(word[4]) for word in page.get_text("words"))
                pages.append(
                    [
                        digest(text),
                        digest(nonspace(text)),
                        len(nonspace(text)),
                        digest(sorted_text),
                        digest(nonspace(sorted_text)),
                        digest(words),
                    ]
                )
            result["pages"] = pages
    except Exception as exc:  # noqa: BLE001 - recorded and compared, not hidden
        result["error"] = f"{type(exc).__name__}: {exc}"[:400]
    result["seconds"] = round(time.monotonic() - started, 3)
    return result


def snapshot_task(task: dict[str, Any], root: str) -> dict[str, Any]:
    worker = snapshot_document if task["kind"] == "document" else snapshot_pdf
    return worker(task, root)


def select_tasks(
    plan: list[dict[str, Any]], *, done: set[str], kinds: set[str], ocr: str
) -> list[dict[str, Any]]:
    """The tasks a snapshot run still has to do.

    ``ocr`` is ``all``, ``skip`` or ``only``: whether to run the documents whose
    manifest rows turn OCR on (they call Tesseract and are much slower).
    """
    selected = []
    for task in plan:
        if task["kind"] not in kinds or task["key"] in done:
            continue
        if task["kind"] == "document" and ocr != "all" and task["ocr"] != (ocr == "only"):
            continue
        selected.append(task)
    return selected


def _finished_keys(records: list[dict[str, Any]], *, retry_errors: bool) -> set[str]:
    latest = _latest(records)
    if not retry_errors:
        return set(latest)
    return {
        key
        for key, record in latest.items()
        if not str(record.get("error", "")).startswith(RETRYABLE_ERROR_PREFIXES)
    }


def _trim_torn_tail(path: Path) -> None:
    """Drop a last line a killed run left half-written, so appending starts on a new line."""
    if not path.exists():
        return
    content = path.read_bytes()
    if content and not content.endswith(b"\n"):
        with path.open("r+b") as handle:
            handle.truncate(content.rfind(b"\n") + 1)


def _worker_loop(
    connection: Connection, root: str, task_function: TaskFunction, results: str
) -> None:
    """Run tasks the parent sends until it sends None or goes away.

    Each result goes to a file in ``results``, and the worker sends only the
    file's name. The parent blocks in ``recv`` until a message is complete; a
    name is a few dozen bytes, written by one system call, so a worker that
    stalls cannot leave the parent waiting on half a message past every
    deadline, as it could with a large result sent through the pipe.
    """
    finished = 0
    while True:
        try:
            task = connection.recv()
        except EOFError:
            return
        if task is None:
            return
        finished += 1
        name = f"{os.getpid()}-{finished}.json"
        partial = Path(results) / f"{name}.partial"
        partial.write_text(json.dumps(task_function(task, root)), encoding="utf-8")
        partial.replace(Path(results) / name)
        connection.send(name)


@dataclass
class _Worker:
    process: BaseProcess
    connection: Connection
    tasks_run: int = 0
    task: dict[str, Any] | None = None
    deadline: float = 0.0


def _run_in_workers(
    tasks: list[dict[str, Any]],
    *,
    root: str,
    workers: int,
    timeout: float,
    task_function: TaskFunction,
    emit: Callable[[dict[str, Any]], None],
) -> None:
    """Run each task in a worker process and emit one record per task, in finishing order.

    The parent knows which task each worker holds, so a worker that dies (a
    MuPDF crash, the out-of-memory killer) or passes its deadline (a hang inside
    MuPDF, where no Python signal handler runs) costs only that task: it is
    recorded and the worker replaced.
    """
    context = multiprocessing.get_context("spawn")
    pending = deque(tasks)
    busy: dict[Connection, _Worker] = {}
    # Every started worker until it is stopped, busy or not, so that an
    # exception anywhere (in emit, or KeyboardInterrupt) still reaps it.
    live: dict[int, _Worker] = {}
    results = tempfile.mkdtemp(prefix="compare-pdf-extraction-")

    def start() -> _Worker:
        parent, child = context.Pipe()
        process = context.Process(
            target=_worker_loop, args=(child, root, task_function, results), daemon=True
        )
        process.start()
        child.close()
        worker = _Worker(process=process, connection=parent)
        live[id(worker)] = worker
        return worker

    def stop(worker: _Worker, *, kill: bool) -> None:
        live.pop(id(worker), None)
        if kill:
            worker.process.kill()
        else:
            with suppress(OSError):
                worker.connection.send(None)
        worker.process.join(10)
        if worker.process.is_alive():
            worker.process.kill()
            worker.process.join()
        worker.connection.close()

    def assign(worker: _Worker) -> None:
        """Give ``worker`` the next task, or retire it when there is none."""
        if not pending:
            stop(worker, kill=False)
            return
        if worker.tasks_run >= TASKS_PER_WORKER:
            stop(worker, kill=False)
            worker = start()
        task = pending.popleft()
        try:
            worker.connection.send(task)
        except OSError:
            # The idle worker died between tasks; the task was never sent.
            stop(worker, kill=True)
            pending.appendleft(task)
            assign(start())
            return
        worker.task, worker.deadline = task, time.monotonic() + timeout
        worker.tasks_run += 1
        busy[worker.connection] = worker

    try:
        for _ in range(min(workers, len(pending))):
            assign(start())
        while busy:
            next_deadline = min(worker.deadline for worker in busy.values())
            ready = wait(list(busy), timeout=max(0.0, next_deadline - time.monotonic()))
            for connection in ready:
                worker = busy.pop(connection)  # type: ignore[arg-type]
                assert worker.task is not None
                try:
                    name = worker.connection.recv()
                except (EOFError, OSError):
                    worker.process.join(10)
                    emit(
                        {
                            "key": worker.task["key"],
                            "error": f"worker exited with code {worker.process.exitcode}",
                        }
                    )
                    stop(worker, kill=True)
                    assign(start())
                    continue
                path = Path(results) / name
                record = json.loads(path.read_text(encoding="utf-8"))
                path.unlink()
                emit(record)
                assign(worker)
            now = time.monotonic()
            for connection, worker in list(busy.items()):
                if worker.deadline <= now:
                    del busy[connection]
                    assert worker.task is not None
                    stop(worker, kill=True)
                    emit({"key": worker.task["key"], "error": f"timeout after {timeout:g}s"})
                    assign(start())
    finally:
        for worker in list(live.values()):
            stop(worker, kill=True)
        shutil.rmtree(results, ignore_errors=True)


def run_snapshot(
    plan: list[dict[str, Any]],
    out_path: Path,
    *,
    root: Path,
    kinds: set[str],
    ocr: str = "all",
    workers: int = 2,
    timeout: float = 900,
    retry_errors: bool = False,
    task_function: TaskFunction = snapshot_task,
) -> int:
    """Append a record for every unfinished task to ``out_path``; return how many ran.

    ``workers`` worker processes run the tasks under ``timeout`` seconds each;
    ``workers=0`` runs them in this process, with no time limit.
    """
    versions = pymupdf_versions()
    _trim_torn_tail(out_path)
    records = _read_jsonl(out_path) if out_path.exists() else []
    done = _finished_keys(records, retry_errors=retry_errors)
    tasks = select_tasks(plan, done=done, kinds=kinds, ocr=ocr)
    print(f"{versions}: {len(tasks)} task(s) to run, {len(done)} done", file=sys.stderr)
    written = 0
    with out_path.open("a", encoding="utf-8") as out:

        def emit(record: dict[str, Any]) -> None:
            nonlocal written
            out.write(json.dumps({**record, **versions}, sort_keys=True) + "\n")
            out.flush()
            written += 1
            if written % 500 == 0:
                print(f"{written}/{len(tasks)}", file=sys.stderr, flush=True)

        if workers <= 0:
            for task in tasks:
                emit(task_function(task, str(root)))
        else:
            _run_in_workers(
                tasks,
                root=str(root),
                workers=workers,
                timeout=timeout,
                task_function=task_function,
                emit=emit,
            )
    return len(tasks)


# ------------------------------------------------------------------------ compare


def committed_rows(root: Path, plan: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Task key -> citation path -> body digest, for committed pdf rows with a body."""
    by_file: dict[str, dict[tuple[str, str], str]] = defaultdict(dict)
    for task in plan:
        if task["kind"] == "document":
            by_file[task["provisions_path"]][(task["source_path"], task["source_id"])] = task["key"]
    rows: dict[str, dict[str, str]] = defaultdict(dict)
    for provisions_path, sources in by_file.items():
        with (root / provisions_path).open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                key = sources.get((str(row.get("source_path")), str(row.get("source_id"))))
                body = row.get("body")
                if key is not None and body and str(row.get("source_format")) == "pdf":
                    rows[key][row["citation_path"]] = digest(body)
    return rows


def reproduced_rows(blocks: dict[str, list[Any]], committed: dict[str, str]) -> set[str]:
    """Citation paths of the committed rows whose body this extraction produced.

    A row is reproduced when the block at its citation path has its body, or,
    failing that, when another block not matched to a row has it: the manifest
    row at HEAD may name the blocks differently from the run that wrote the
    row. Each block reproduces at most one row.
    """
    by_path = {
        path for path, body in committed.items() if path in blocks and blocks[path][BODY] == body
    }
    spare = Counter(block[BODY] for path, block in blocks.items() if path not in by_path)
    by_body = set()
    for path, body in committed.items():
        if path not in by_path and spare[body] > 0:
            spare[body] -= 1
            by_body.add(path)
    return by_path | by_body


def _blocks(candidate: dict[str, Any]) -> dict[str, list[Any]]:
    return {block[PATH]: block for block in candidate.get("blocks", [])}


def choose_configuration(a: dict[str, Any], b: dict[str, Any], committed: dict[str, str]) -> int:
    """Index of the configuration to compare for a document.

    A source_id can have several manifest rows. Take the configuration that
    extracts on more snapshots, then the one that reproduces the most committed
    rows on either snapshot, then the one with the fewest blocks the committed
    rows do not have, then the first.
    """

    def score(index: int) -> tuple[int, int, int, int]:
        candidate_a, candidate_b = a["candidates"][index], b["candidates"][index]
        blocks_a, blocks_b = _blocks(candidate_a), _blocks(candidate_b)
        return (
            (not candidate_a.get("error")) + (not candidate_b.get("error")),
            max(
                len(reproduced_rows(blocks_a, committed)), len(reproduced_rows(blocks_b, committed))
            ),
            -min(
                sum(1 for path in blocks_a if path not in committed),
                sum(1 for path in blocks_b if path not in committed),
            ),
            -index,
        )

    return max(range(len(a["candidates"])), key=score)


def _error_kind(error: str) -> str:
    if error.startswith("read:"):
        return "source_file_unreadable"
    if error.startswith("timeout after"):
        return "timeout"
    if error.startswith("worker exited"):
        return "worker_died"
    return error.split(":", 1)[0]


def _bytes_check(a: dict[str, Any], b: dict[str, Any], expected: str | None) -> str:
    """``same``, ``differ`` or ``unchecked`` (a snapshot did not record its hash)."""
    sha_a, sha_b = a.get("pdf_sha256"), b.get("pdf_sha256")
    if sha_a is None or sha_b is None:
        return "unchecked"
    if sha_a != sha_b or (expected is not None and sha_a != expected):
        return "differ"
    return "same"


def compare_documents(
    plan: list[dict[str, Any]],
    locked: dict[str, dict[str, Any]],
    candidate: dict[str, dict[str, Any]],
    committed: dict[str, dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    documents: Counter[str] = Counter()
    rows: Counter[str] = Counter()
    scopes: set[str] = set()
    differing_scopes: set[str] = set()
    details: list[dict[str, Any]] = []
    for task in plan:
        if task["kind"] != "document":
            continue
        documents["planned"] += 1
        key = task["key"]
        a, b = locked.get(key), candidate.get(key)
        if a is None or b is None:
            documents["not_in_both_snapshots"] += 1
            continue
        # Different bytes explain any difference, an error included: set them aside first.
        bytes_check = _bytes_check(a, b, task.get("source_sha256"))
        if bytes_check == "differ":
            documents["source_bytes_differ"] += 1
            details.append({"key": key, "source_bytes": [a["pdf_sha256"], b["pdf_sha256"]]})
            continue
        error_a, error_b = a.get("error"), b.get("error")
        if error_a or error_b:
            kinds = {_error_kind(error) if error else "none" for error in (error_a, error_b)}
            if len(kinds) == 1:
                documents[f"task_fails_on_both:{kinds.pop()}"] += 1
            else:
                # One snapshot failed where the other did not, or failed another way.
                documents["task_fails_on_one_or_differently"] += 1
                scopes.add(task["scope"])
                differing_scopes.add(task["scope"])
                details.append({"key": key, "locked_error": error_a, "candidate_error": error_b})
            continue
        if len(a["candidates"]) != len(b["candidates"]):
            raise ValueError(f"the snapshots ran different configurations for {key}")
        if bytes_check == "unchecked":
            documents["source_bytes_unchecked"] += 1
        committed_document = committed.get(key, {})
        choice = choose_configuration(a, b, committed_document)
        candidate_a, candidate_b = a["candidates"][choice], b["candidates"][choice]
        error_a, error_b = candidate_a.get("error"), candidate_b.get("error")
        if error_a and error_b:
            # The same failure on both (a source named .pdf that is not a PDF).
            documents[f"extraction_fails_on_both:{_error_kind(error_a)}"] += 1
            continue
        scopes.add(task["scope"])
        if error_a or error_b:
            documents["extraction_fails_on_one"] += 1
            differing_scopes.add(task["scope"])
            details.append({"key": key, "locked_error": error_a, "candidate_error": error_b})
            continue
        documents["extracted_on_both"] += 1
        blocks_a, blocks_b = _blocks(candidate_a), _blocks(candidate_b)
        common = [path for path in blocks_a if path in blocks_b]
        one_side = len(blocks_a) + len(blocks_b) - 2 * len(common)
        body = [path for path in common if blocks_a[path][BODY] != blocks_b[path][BODY]]
        characters = [path for path in body if blocks_a[path][NONSPACE] != blocks_b[path][NONSPACE]]
        other = [
            path
            for path in common
            if blocks_a[path][HEADING] != blocks_b[path][HEADING]
            or blocks_a[path][METADATA] != blocks_b[path][METADATA]
        ]
        rows["blocks_compared"] += len(common)
        rows["blocks_on_one_snapshot_only"] += one_side
        rows["blocks_differing_in_characters"] += len(characters)
        rows["blocks_differing_in_whitespace_only"] += len(body) - len(characters)
        rows["blocks_differing_in_heading_or_metadata"] += len(other)
        differs = bool(one_side or body or other)
        if characters or one_side:
            documents["differ_in_characters_or_blocks"] += 1
        elif body:
            documents["differ_in_whitespace_only"] += 1
        elif other:
            documents["differ_in_heading_or_metadata_only"] += 1
        else:
            documents["identical"] += 1
        warnings_a = (candidate_a.get("warnings"), candidate_a.get("warning_digest"))
        if warnings_a != (candidate_b.get("warnings"), candidate_b.get("warning_digest")):
            documents["warnings_differ"] += 1

        on_a = reproduced_rows(blocks_a, committed_document)
        on_b = reproduced_rows(blocks_b, committed_document)
        rows["committed_rows"] += len(committed_document)
        rows["committed_rows_reproduced_on_both"] += len(on_a & on_b)
        rows["committed_rows_reproduced_on_locked_only"] += len(on_a - on_b)
        rows["committed_rows_reproduced_on_candidate_only"] += len(on_b - on_a)
        rows["committed_rows_reproduced_on_neither"] += len(committed_document) - len(on_a | on_b)
        if not differs:
            continue
        differing_scopes.add(task["scope"])
        complete_a = bool(committed_document) and len(on_a) == len(committed_document)
        complete_b = bool(committed_document) and len(on_b) == len(committed_document)
        reproduces = {
            (True, True): "both",
            (True, False): "locked",
            (False, True): "candidate",
            (False, False): "neither",
        }[(complete_a, complete_b)]
        documents[f"differing_with_every_committed_row_reproduced_by:{reproduces}"] += 1
        details.append(
            {
                "key": key,
                "scope": task["scope"],
                "manifest": candidate_a.get("manifest"),
                "ocr": task["ocr"],
                "blocks": [len(blocks_a), len(blocks_b)],
                "blocks_on_one_snapshot_only": one_side,
                "blocks_differing_in_characters": len(characters),
                "blocks_differing_in_whitespace_only": len(body) - len(characters),
                "blocks_differing_in_heading_or_metadata": len(other),
                "nonspace_characters_candidate_minus_locked": sum(
                    blocks_b[path][NONSPACE_LENGTH] - blocks_a[path][NONSPACE_LENGTH]
                    for path in characters
                ),
                "committed_rows": len(committed_document),
                "reproduced": [len(on_a), len(on_b)],
                "every_committed_row_reproduced_by": reproduces,
                "example_paths": (characters or body or other)[:3],
            }
        )
    summary = {
        "documents": dict(sorted(documents.items())),
        "rows": dict(sorted(rows.items())),
        "scopes_compared": len(scopes),
        "scopes_with_a_differing_document": len(differing_scopes),
    }
    return summary, details


def compare_pdfs(
    plan: list[dict[str, Any]],
    locked: dict[str, dict[str, Any]],
    candidate: dict[str, dict[str, Any]],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts: Counter[str] = Counter()
    details: list[dict[str, Any]] = []
    for task in plan:
        if task["kind"] != "pdf":
            continue
        counts["pdfs_planned"] += 1
        a, b = locked.get(task["key"]), candidate.get(task["key"])
        if a is None or b is None:
            counts["pdfs_not_in_both_snapshots"] += 1
            continue
        # A pdf task's key is the sha256 the lock records for the file. Different
        # bytes explain any difference, an error included: set them aside first.
        bytes_check = _bytes_check(a, b, task["key"])
        if bytes_check == "differ":
            counts["pdfs_bytes_differ"] += 1
            details.append({"key": task["key"], "path": task["path"], "status": "bytes_differ"})
            continue
        error_a, error_b = a.get("error"), b.get("error")
        if error_a or error_b:
            kinds = {_error_kind(error) if error else "none" for error in (error_a, error_b)}
            if len(kinds) == 1:
                counts["pdfs_failing_on_both"] += 1
            else:
                counts["pdfs_failing_on_one_or_differently"] += 1
                details.append(
                    {"key": task["key"], "path": task["path"], "errors": [error_a, error_b]}
                )
            continue
        if bytes_check == "unchecked":
            counts["pdfs_bytes_unchecked"] += 1
        pages_a, pages_b = a["pages"], b["pages"]
        counts["pdfs_compared"] += 1
        if len(pages_a) != len(pages_b):
            counts["pdfs_with_differing_page_count"] += 1
            details.append({"key": task["key"], "path": task["path"], "status": "page_count"})
            continue
        counts["pages_compared"] += len(pages_a)
        pairs = list(zip(pages_a, pages_b, strict=True))
        text = [index for index, (x, y) in enumerate(pairs) if x[TEXT] != y[TEXT]]
        characters = [i for i in text if pairs[i][0][TEXT_NONSPACE] != pairs[i][1][TEXT_NONSPACE]]
        sorted_text = [index for index, (x, y) in enumerate(pairs) if x[SORTED] != y[SORTED]]
        words = [index for index, (x, y) in enumerate(pairs) if x[WORDS] != y[WORDS]]
        counts["pages_differing_in_get_text"] += len(text)
        counts["pages_differing_in_get_text_characters"] += len(characters)
        counts["pages_differing_in_sorted_get_text"] += len(sorted_text)
        counts["pages_differing_in_words"] += len(words)
        if text or sorted_text or words:
            counts["pdfs_with_a_differing_page"] += 1
            details.append(
                {
                    "key": task["key"],
                    "path": task["path"],
                    "status": "differs",
                    "pages": len(pages_a),
                    "pages_differing_in_get_text": len(text),
                    "pages_differing_in_get_text_characters": len(characters),
                    "nonspace_characters_candidate_minus_locked": sum(
                        pairs[i][1][TEXT_NONSPACE_LENGTH] - pairs[i][0][TEXT_NONSPACE_LENGTH]
                        for i in characters
                    ),
                    "example_pages": [index + 1 for index in (characters or text or words)[:5]],
                }
            )
        if characters:
            counts["pdfs_with_a_page_differing_in_characters"] += 1
    return dict(sorted(counts.items())), details


def compare(
    root: Path,
    plan: list[dict[str, Any]],
    locked_records: list[dict[str, Any]],
    candidate_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    locked, candidate = _latest(locked_records), _latest(candidate_records)
    summary, document_details = compare_documents(
        plan, locked, candidate, committed_rows(root, plan)
    )
    pdf_counts, pdf_details = compare_pdfs(plan, locked, candidate)

    def versions(records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        seen = {(record.get("pymupdf"), record.get("mupdf")) for record in records.values()}
        return [{"pymupdf": pymupdf, "mupdf": mupdf} for pymupdf, mupdf in sorted(seen, key=str)]

    report = {
        "locked": versions(locked),
        "candidate": versions(candidate),
        **summary,
        "pdfs": pdf_counts,
    }
    details = [{"kind": "document", **item} for item in document_details]
    details += [{"kind": "pdf", **item} for item in pdf_details]
    return report, details


# ---------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root")
    commands = parser.add_subparsers(dest="command", required=True)

    plan_parser = commands.add_parser("plan", help="list what to re-extract")
    plan_parser.add_argument("--out", type=Path, required=True)

    snapshot_parser = commands.add_parser("snapshot", help="extract with the installed PyMuPDF")
    snapshot_parser.add_argument("--plan", type=Path, required=True)
    snapshot_parser.add_argument("--out", type=Path, required=True)
    snapshot_parser.add_argument("--kind", choices=["document", "pdf", "all"], default="all")
    snapshot_parser.add_argument(
        "--ocr",
        choices=["all", "skip", "only"],
        default="all",
        help="documents whose manifest rows turn OCR on (they call Tesseract)",
    )
    snapshot_parser.add_argument(
        "--workers", type=int, default=2, help="worker processes (0: run in this process)"
    )
    snapshot_parser.add_argument(
        "--timeout",
        type=float,
        default=900,
        help="seconds a task may take before its worker is killed",
    )
    snapshot_parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="rerun tasks recorded as timed out or as killing their worker",
    )

    compare_parser = commands.add_parser("compare", help="compare two snapshots")
    compare_parser.add_argument("--plan", type=Path, required=True)
    compare_parser.add_argument("--locked", type=Path, required=True)
    compare_parser.add_argument("--candidate", type=Path, required=True)
    compare_parser.add_argument("--details", type=Path, help="write each difference here (JSONL)")

    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "plan":
        tasks = build_plan(root)
        with args.out.open("w", encoding="utf-8") as handle:
            for task in tasks:
                handle.write(json.dumps(task, sort_keys=True, default=str) + "\n")
        kinds = Counter(task["kind"] for task in tasks)
        print(json.dumps({"documents": kinds["document"], "pdfs": kinds["pdf"]}))
        return 0
    plan = _read_jsonl(args.plan)
    if args.command == "snapshot":
        started = time.monotonic()
        count = run_snapshot(
            plan,
            args.out,
            root=root,
            kinds={"document", "pdf"} if args.kind == "all" else {args.kind},
            ocr=args.ocr,
            workers=args.workers,
            timeout=args.timeout,
            retry_errors=args.retry_errors,
        )
        print(f"{count} task(s) in {time.monotonic() - started:.0f}s", file=sys.stderr)
        return 0
    report, details = compare(root, plan, _read_jsonl(args.locked), _read_jsonl(args.candidate))
    if args.details:
        with args.details.open("w", encoding="utf-8") as handle:
            for item in details:
                handle.write(json.dumps(item, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
