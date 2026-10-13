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
- ``pdf``: one distinct PDF file under ``data/corpus/sources``. A snapshot
  records per-page digests of ``get_text()``, ``get_text("text", sort=True)``
  and ``get_text("words")``, the calls the statute adapters make. ``compare``
  counts the pages that differ.

The manifests and extractor at HEAD are not always the ones that wrote a
committed row, so some committed rows are reproduced by neither snapshot. Those
say nothing about the PyMuPDF version, and ``compare`` counts them apart.

Snapshots are JSONL, written and flushed per task; a rerun skips finished tasks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
import subprocess
import sys
import time
import warnings
from collections import Counter, defaultdict
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
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
    """Two manifest rows with these equal extract the same blocks from the same bytes."""
    return json.dumps(
        [row.get("citation_path"), row.get("extraction")], sort_keys=True, default=str
    )


def build_plan(root: Path) -> list[dict[str, Any]]:
    manifest_rows = _manifest_rows(root)
    tasks: list[dict[str, Any]] = []
    pdfs: dict[str, str] = {}
    for scope, entry in _locked_files(root):
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
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


# ----------------------------------------------------------------------- snapshot


class _TimeoutError(Exception):
    pass


def _raise_timeout(_signum: int, _frame: Any) -> None:
    raise _TimeoutError


@contextmanager
def _time_limit(seconds: int) -> Iterator[None]:
    """Raise _TimeoutError after ``seconds`` (0: no limit, as in a test's own process)."""
    if seconds <= 0:
        yield
        return
    previous = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


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


def snapshot_document(task: dict[str, Any], root: str, timeout: int) -> dict[str, Any]:
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
            with _time_limit(timeout), warnings.catch_warnings(record=True) as caught:
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
        except _TimeoutError:
            entry["error"] = f"timeout after {timeout}s"
        except Exception as exc:  # noqa: BLE001 - recorded and compared, not hidden
            entry["error"] = f"{type(exc).__name__}: {exc}"[:400]
        result["candidates"].append(entry)
    result["seconds"] = round(time.monotonic() - started, 3)
    return result


def snapshot_pdf(task: dict[str, Any], root: str, timeout: int) -> dict[str, Any]:
    import fitz

    _quiet_mupdf()
    started = time.monotonic()
    result: dict[str, Any] = {"key": task["key"], "path": task["path"]}
    try:
        with _time_limit(timeout), fitz.open(str(Path(root) / task["path"])) as document:
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
    except _TimeoutError:
        result["error"] = f"timeout after {timeout}s"
    except Exception as exc:  # noqa: BLE001 - recorded and compared, not hidden
        result["error"] = f"{type(exc).__name__}: {exc}"[:400]
    result["seconds"] = round(time.monotonic() - started, 3)
    return result


def snapshot_task(task: dict[str, Any], root: str, timeout: int) -> dict[str, Any]:
    worker = snapshot_document if task["kind"] == "document" else snapshot_pdf
    return worker(task, root, timeout)


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


def run_snapshot(
    plan: list[dict[str, Any]],
    out_path: Path,
    *,
    root: Path,
    kinds: set[str],
    ocr: str = "all",
    workers: int = 1,
    timeout: int = 900,
) -> int:
    """Append a record for every unfinished task to ``out_path``; return how many ran.

    With one worker the tasks run in this process and ``timeout`` is not
    enforced; with more, each runs in a worker process under its own alarm.
    """
    versions = pymupdf_versions()
    done = {record["key"] for record in _read_jsonl(out_path)} if out_path.exists() else set()
    tasks = select_tasks(plan, done=done, kinds=kinds, ocr=ocr)
    print(f"{versions}: {len(tasks)} task(s) to run, {len(done)} done", file=sys.stderr)
    with out_path.open("a", encoding="utf-8") as out:

        def write(record: dict[str, Any], count: int) -> None:
            out.write(json.dumps({**record, **versions}, sort_keys=True) + "\n")
            out.flush()
            if count % 500 == 0:
                print(f"{count}/{len(tasks)}", file=sys.stderr, flush=True)

        if workers <= 1:
            for count, task in enumerate(tasks, start=1):
                write(snapshot_task(task, str(root), 0), count)
            return len(tasks)
        with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=100) as pool:
            futures = {
                pool.submit(snapshot_task, task, str(root), timeout): task["key"] for task in tasks
            }
            for count, future in enumerate(as_completed(futures), start=1):
                try:
                    record = future.result()
                except Exception as exc:  # noqa: BLE001 - a dead worker is a result too
                    record = {
                        "key": futures[future],
                        "error": f"worker: {type(exc).__name__}: {exc}"[:400],
                    }
                write(record, count)
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


def _configuration(a: dict[str, Any], b: dict[str, Any], committed: dict[str, str]) -> int:
    """Index of the configuration to compare for a document.

    A source_id can have several manifest rows; take the configuration that
    reproduces the most committed rows on either snapshot, then the one with
    the fewest blocks the committed rows do not have, then the first.
    """

    def score(index: int) -> tuple[int, int, int]:
        blocks_a, blocks_b = _blocks(a["candidates"][index]), _blocks(b["candidates"][index])
        return (
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
        if a.get("error") or b.get("error"):
            documents["source_file_unreadable"] += 1
            continue
        if len(a["candidates"]) != len(b["candidates"]):
            raise ValueError(f"the snapshots ran different configurations for {key}")
        committed_document = committed.get(key, {})
        choice = _configuration(a, b, committed_document)
        candidate_a, candidate_b = a["candidates"][choice], b["candidates"][choice]
        error_a, error_b = candidate_a.get("error"), candidate_b.get("error")
        if error_a and error_b:
            # The same failure on both (a source named .pdf that is not a PDF).
            documents[f"extraction_fails_on_both:{error_a.split(':', 1)[0]}"] += 1
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
        if a.get("error") or b.get("error"):
            both = a.get("error") and b.get("error")
            counts["pdfs_failing_on_both" if both else "pdfs_failing_on_one"] += 1
            if not both:
                details.append({"key": task["key"], "path": task["path"], "status": "error_one"})
            continue
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
    locked = {record["key"]: record for record in locked_records}
    candidate = {record["key"]: record for record in candidate_records}
    summary, document_details = compare_documents(
        plan, locked, candidate, committed_rows(root, plan)
    )
    pdf_counts, pdf_details = compare_pdfs(plan, locked, candidate)

    def versions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = {(record.get("pymupdf"), record.get("mupdf")) for record in records}
        return [{"pymupdf": pymupdf, "mupdf": mupdf} for pymupdf, mupdf in sorted(seen, key=str)]

    report = {
        "locked": versions(locked_records),
        "candidate": versions(candidate_records),
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
    snapshot_parser.add_argument("--workers", type=int, default=2)
    snapshot_parser.add_argument("--timeout", type=int, default=900, help="seconds per extraction")

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
