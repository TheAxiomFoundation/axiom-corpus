#!/usr/bin/env python3
"""Measure what ``pre`` handling changes in locked official-document HTML scopes.

Until 2026-10-12 the official-document HTML extractor
(``documents._extract_html_blocks``) read heading, ``p``, ``li``, ``table`` and
``blockquote`` nodes only. Text in a ``pre`` element reached a row only inside one
of those or through the root fallback of a page with no other text node. This
script measures, for every locked scope, what that left out and what the current
extractor changes. Run note: ``docs/ingest-runs/2026-10-12-html-pre-gap.md``.

For every official-document source (``.html``, ``.htm``, ``.xhtml``, ``.json``)
of every lock:

1. Read its bytes from the shared corpus cache (hash-checked; nothing is placed
   under ``data/corpus``) and look for a ``pre`` element (in a JSON source, in any
   string, base64-decoded where it is base64).
2. Replay the extractor at ``--baseline-ref`` under every manifest entry that could
   have produced the source (same jurisdiction, document class and
   ``safe_segment(source_id)``, in ``manifests/`` here and at each ``--ref``, every
   version of a manifest kept). An entry whose replay equals the locked rows (kind,
   heading, body, in order) is a verified config. A source with no verified config is
   ``unverified``; one whose verified configs disagree on the current extractor's
   output is ``ambiguous`` (measured under the first, and counted).
3. Under the verified config, parse the page the way the extractor does and, for
   every outermost ``pre`` under the content root, read its text as the current
   extractor reads a ``pre`` and count its words. Its words are in the gap when no
   single locked row (heading or body) holds that text. The test ignores whitespace,
   so it reads ``ab`` and ``a b`` as the same text.
4. Replay the current extractor under the same config and compare its blocks (kind,
   heading, body, metadata) with the baseline replay (``--all`` does this for sources
   without ``pre`` too).

    uv run python scripts/audit_html_pre_gap.py --baseline-ref 2b9ca4ba2 \\
        --ref origin/ingest/ssa-oasdi-source-conflict-texts --all --workers 4 \\
        --output /tmp/html-pre-gap.json
"""

from __future__ import annotations

import argparse
import base64
import collections
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import types
from collections.abc import Iterable, Iterator, Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from axiom_corpus.corpus.artifacts import safe_segment
from axiom_corpus.corpus.content_store import ContentCache
from axiom_corpus.corpus.corpus_locks import (
    CorpusLock,
    LockEntry,
    load_locks,
    load_locks_at_ref,
    read_tree_blobs,
)

HTML_SUFFIXES = (".html", ".htm", ".xhtml", ".json")
OFFICIAL_DOCUMENTS = "/official-documents/"
DOCUMENTS_MODULE = "src/axiom_corpus/corpus/documents.py"
MAX_WORKERS = 4
_PRE_BYTES = re.compile(rb"<\s*pre[\s>/]", re.IGNORECASE)
_PRE_TEXT = re.compile(r"<\s*pre[\s>/]", re.IGNORECASE)
_BASE64 = re.compile(r"[A-Za-z0-9+/=\s]+")

Row = tuple[str, str | None, str]
FullRow = tuple[str, str | None, str, str]


@dataclass(frozen=True)
class Job:
    scope: str
    entry: LockEntry
    source_format: str | None
    locked: tuple[Row, ...]
    configs: tuple[dict[str, Any], ...]


def has_pre(content: bytes, suffix: str) -> bool:
    """True when the source holds a ``pre`` start tag (in a JSON source, in a string)."""
    if suffix != ".json":
        return bool(_PRE_BYTES.search(content))
    try:
        data = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return bool(_PRE_BYTES.search(content))
    for text in _json_strings(data):
        if _PRE_TEXT.search(text):
            return True
        if _BASE64.fullmatch(text):
            try:
                decoded = base64.b64decode(text).decode("utf-8", "replace")
            except ValueError:
                continue
            if _PRE_TEXT.search(decoded):
                return True
    return False


def _json_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _json_strings(item)


def words(text: str | None) -> int:
    return len((text or "").replace("\u200b", "").replace("\ufeff", "").split())


def _squeeze(text: str) -> str:
    return "".join(text.replace("\u200b", "").replace("\ufeff", "").split())


def _rows_text(rows: Iterable[Row | FullRow]) -> str:
    return " ".join(f"{row[1] or ''} {row[2] or ''}" for row in rows)


def _block_rows(blocks: Iterable[Any]) -> tuple[FullRow, ...]:
    return tuple(
        (block.kind, block.heading, block.body, json.dumps(block.metadata, sort_keys=True))
        for block in blocks
    )


def _locked_shape(rows: Iterable[FullRow]) -> tuple[Row, ...]:
    """The fields a provision row keeps of a block, to compare with the locked rows."""
    return tuple((kind, heading, body) for kind, heading, body, _ in rows)


def load_module(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def baseline_module_path(repo: Path, ref: str, directory: Path) -> Path:
    source = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{DOCUMENTS_MODULE}"],
        check=True,
        capture_output=True,
    ).stdout
    path = directory / "documents_baseline.py"
    path.write_bytes(source)
    return path


def manifest_configs(
    payloads: Iterable[bytes],
) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    """Index every manifest document by (jurisdiction, document class, source file stem)."""
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    index: dict[tuple[str, str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for payload in payloads:
        try:
            data = yaml.load(payload, Loader=loader)  # noqa: S506 - a safe loader
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict) or not isinstance(data.get("documents"), list):
            continue
        for row in data["documents"]:
            if not isinstance(row, dict) or "source_id" not in row or "jurisdiction" not in row:
                continue
            key = (
                str(row["jurisdiction"]),
                str(row.get("document_class", "policy")),
                safe_segment(str(row["source_id"])),
            )
            config = {
                "title": None if row.get("title") is None else str(row["title"]),
                "source_url": str(row.get("source_url", "")),
                "extraction": row.get("extraction"),
            }
            if config not in index[key]:
                index[key].append(config)
    return index


def read_entry(cache: ContentCache, entry: LockEntry) -> bytes:
    if not cache.usable(entry.sha256, entry.size):
        raise SystemExit(
            f"{entry.path} is not in the corpus cache; run "
            f"`axiom-corpus-ingest corpus fetch --path {entry.path}` first"
        )
    return cache.object_path(entry.sha256).read_bytes()


def build_jobs(
    locks: Iterable[CorpusLock],
    configs: Mapping[tuple[str, str, str], list[dict[str, Any]]],
    cache: ContentCache,
) -> list[Job]:
    jobs: list[Job] = []
    for lock in locks:
        sources = [
            entry
            for entry in lock.files
            if OFFICIAL_DOCUMENTS in entry.path and Path(entry.path).suffix.lower() in HTML_SUFFIXES
        ]
        if not sources:
            continue
        provisions = [
            entry for entry in lock.files if entry.path.startswith("data/corpus/provisions/")
        ]
        rows_by_source: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for entry in provisions:
            for line in read_entry(cache, entry).decode("utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    rows_by_source[str(row.get("source_path"))].append(row)
        scope = "/".join(lock.scope)
        for entry in sources:
            rows = rows_by_source.get(entry.path.removeprefix("data/corpus/"), [])
            blocks = sorted(
                (row for row in rows if row.get("kind") != "document"), key=lambda r: r["ordinal"]
            )
            name = Path(entry.path).name
            stem = name[: -len(Path(name).suffix)]
            jobs.append(
                Job(
                    scope=scope,
                    entry=entry,
                    source_format=str(rows[0]["source_format"]) if rows else None,
                    locked=tuple(
                        (row["kind"], row.get("heading"), row.get("body")) for row in blocks
                    ),
                    configs=tuple(configs.get((lock.jurisdiction, lock.document_class, stem), [])),
                )
            )
    return jobs


_WORKER: dict[str, Any] = {}


def _init_worker(baseline_path: str, cache_root: str, compare_all: bool) -> None:
    import warnings

    warnings.filterwarnings("ignore")
    from axiom_corpus.corpus import documents

    _WORKER["baseline"] = load_module("documents_baseline", Path(baseline_path))
    _WORKER["current"] = documents
    _WORKER["cache"] = ContentCache(Path(cache_root))
    _WORKER["all"] = compare_all


def audit_job(job: Job) -> dict[str, Any]:
    baseline = _WORKER["baseline"]
    current = _WORKER["current"]
    content = read_entry(_WORKER["cache"], job.entry)
    suffix = Path(job.entry.path).suffix.lower()
    result: dict[str, Any] = {
        "scope": job.scope,
        "path": job.entry.path,
        "has_pre": has_pre(content, suffix),
        "candidate_configs": len(job.configs),
    }
    if not result["has_pre"] and not _WORKER["all"]:
        return result
    if job.source_format is None:
        result["status"] = "no_locked_rows"
        return result
    verified: list[dict[str, Any]] = []
    errors = []
    replayed = False
    for config in job.configs or ({"title": None, "source_url": "", "extraction": None},):
        kwargs = dict(config)
        try:
            before = _block_rows(baseline._extract_blocks(content, job.source_format, **kwargs))
        except Exception as exc:  # noqa: BLE001 - reported; the current extractor is not run
            errors.append(f"{type(exc).__name__}: {exc}"[:200])
            continue
        try:
            after = _block_rows(current._extract_blocks(content, job.source_format, **kwargs))
        except Exception as exc:  # noqa: BLE001 - the baseline read it: a regression
            result["current_error"] = f"{type(exc).__name__}: {exc}"[:200]
            after = ()
        replayed = True
        if _locked_shape(before) == job.locked:
            verified.append({"config": config, "before": before, "after": after})
        if before != after and not result["has_pre"]:
            result["changed_without_pre"] = True
    result["replayed"] = replayed
    if not replayed:
        result["status"] = "not_replayable"
        result["error"] = errors[0] if errors else "no config"
        return result
    if not verified:
        result["status"] = "unverified"
        return result
    result["verified_configs"] = len(verified)
    outputs = {entry["after"] for entry in verified}
    result["status"] = "verified" if len(outputs) == 1 else "ambiguous"
    before, after = verified[0]["before"], verified[0]["after"]
    result["identical"] = before == after
    if result["has_pre"]:
        result.update(
            _pre_gap(
                baseline,
                current,
                content,
                job.source_format,
                verified[0]["config"],
                _locked_shape(before),
            )
        )
    if before != after:
        result.update(
            {
                "rows_before": len(before),
                "rows_after": len(after),
                "rows_changed": sum(1 for a, b in zip(before, after, strict=False) if a != b)
                + abs(len(before) - len(after)),
                "headings_changed": sum(
                    1 for a, b in zip(before, after, strict=False) if a[1] != b[1]
                ),
                "words_before": words(_rows_text(before)),
                "words_after": words(_rows_text(after)),
                "same_text_ignoring_whitespace": _squeeze(_rows_text(before))
                == _squeeze(_rows_text(after)),
            }
        )
    return result


def _pre_gap(
    module: types.ModuleType,
    current: types.ModuleType,
    content: bytes,
    source_format: str,
    config: dict[str, Any],
    rows: tuple[Row, ...],
) -> dict[str, Any]:
    """Words in ``pre`` elements under the content root, and those no locked row holds.

    ``module`` parses the page as the baseline did; ``current`` reads each ``pre``.
    """
    extraction = config.get("extraction") or {}
    if source_format == "json":
        if extraction.get("segmentation") in {"records", "source_only"}:
            return {"measurement_status": "json_records"}
        html_text = module._json_path(
            json.loads(content.decode("utf-8")), extraction["json_html_field"]
        )
        if extraction.get("json_html_base64"):
            html_text = base64.b64decode(html_text).decode("utf-8", errors="replace")
        content = html_text.encode("utf-8")
    soup = module._html_soup(content, parser=extraction.get("html_parser"))
    kept = set(module._html_keep_default_drop_selectors(extraction))
    for selector in (
        *(s for s in module._HTML_DEFAULT_DROP_SELECTORS if s not in kept),
        *module._html_drop_selectors(extraction),
    ):
        for node in soup.select(selector):
            node.decompose()
    root = module._html_content_root(soup, extraction=extraction)
    pres = [pre for pre in root.find_all("pre") if pre.find_parent("pre") is None]
    texts = [current._html_node_text(pre) for pre in pres]
    held = [_squeeze(part) for _, heading, body in rows for part in (heading or "", body or "")]
    missing = [
        text for text in texts if words(text) and not any(_squeeze(text) in row for row in held)
    ]
    return {
        "pre_elements": len(pres),
        "pre_words": sum(words(text) for text in texts),
        "gap_pre_elements": len(missing),
        "gap_words": sum(words(text) for text in missing),
        "gap_samples": [" ".join(text.split())[:160] for text in missing[:3]],
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts: collections.Counter[str] = collections.Counter()
    scopes: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for result in results:
        counts["sources"] += 1
        counts["sources_with_pre"] += bool(result["has_pre"])
        status = result.get("status")
        if status:
            counts[f"status_{status}"] += 1
        counts["current_errors"] += "current_error" in result
        if not result["has_pre"]:
            if result.get("replayed"):
                counts["without_pre_replayed"] += 1
                counts["without_pre_changed"] += bool(result.get("changed_without_pre"))
            continue
        scope = scopes[result["scope"]]
        scope["sources_with_pre"] += 1
        for key in (
            "pre_elements",
            "pre_words",
            "gap_pre_elements",
            "gap_words",
            "rows_changed",
            "headings_changed",
        ):
            scope[key] += int(result.get(key, 0) or 0)
        scope["sources_gaining_text"] += bool(result.get("gap_words"))
        scope["sources_changed"] += result.get("identical") is False
        scope["sources_unverified"] += status not in {"verified", "ambiguous"}
        scope["sources_ambiguous"] += status == "ambiguous"
    return {
        "counts": dict(counts),
        "scopes": {key: dict(value) for key, value in sorted(scopes.items())},
    }


def markdown_table(summary: Mapping[str, Any]) -> str:
    lines = [
        "| scope | sources with `pre` | `pre` under root | words | words no row holds | sources gaining text | sources changed | rows changed |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    ordered = sorted(
        summary["scopes"].items(),
        key=lambda item: (
            -item[1].get("gap_words", 0),
            -item[1].get("sources_changed", 0),
            item[0],
        ),
    )
    for scope, row in ordered:
        lines.append(
            f"| `{scope}` | {row.get('sources_with_pre', 0)} | {row.get('pre_elements', 0)} | "
            f"{row.get('pre_words', 0):,} | {row.get('gap_words', 0):,} | "
            f"{row.get('sources_gaining_text', 0)} | {row.get('sources_changed', 0)} | "
            f"{row.get('rows_changed', 0)} |"
        )
    return "\n".join(lines)


def run(
    repo: Path,
    *,
    baseline_path: Path,
    refs: Iterable[str] = (),
    cache: ContentCache | None = None,
    compare_all: bool = False,
    workers: int = MAX_WORKERS,
) -> dict[str, Any]:
    if workers > MAX_WORKERS:
        raise SystemExit(f"--workers is capped at {MAX_WORKERS}")
    cache = cache or ContentCache()
    lock_set = load_locks(repo)
    if lock_set.errors:
        raise SystemExit("\n".join(lock_set.errors))
    locks = dict(lock_set.locks)
    # Every version of a manifest is kept: a ref may hold the config that made a scope.
    manifests = [path.read_bytes() for path in sorted((repo / "manifests").rglob("*.yaml"))]
    for ref in refs:
        for scope, lock in load_locks_at_ref(repo, ref).locks.items():
            locks.setdefault(scope, lock)
        blobs = read_tree_blobs(repo, ref, "manifests")
        manifests.extend(blobs[path] for path in sorted(blobs) if path.endswith(".yaml"))
    jobs = build_jobs((locks[scope] for scope in sorted(locks)), manifest_configs(manifests), cache)
    jobs.sort(key=lambda job: -job.entry.size)
    initargs = (str(baseline_path), str(cache.root), compare_all)
    if workers <= 1:
        _init_worker(*initargs)
        results = [audit_job(job) for job in jobs]
    else:
        with ProcessPoolExecutor(
            max_workers=workers, initializer=_init_worker, initargs=initargs
        ) as pool:
            results = list(pool.map(audit_job, jobs, chunksize=8))
    results.sort(key=lambda result: result["path"])
    return {
        "summary": summarize(results),
        "sources": [
            result for result in results if result["has_pre"] or result.get("changed_without_pre")
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--baseline-ref", required=True, help="git ref of the extractor to compare against"
    )
    parser.add_argument(
        "--ref", action="append", default=[], help="also read locks and manifests at this ref"
    )
    parser.add_argument("--all", action="store_true", help="also compare sources without pre")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as directory:
        baseline = baseline_module_path(args.repo, args.baseline_ref, Path(directory))
        report = run(
            args.repo,
            baseline_path=baseline,
            refs=args.ref,
            compare_all=args.all,
            workers=args.workers,
        )
    report["baseline_ref"] = args.baseline_ref
    report["refs"] = args.ref
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps(report["summary"]["counts"], indent=1, sort_keys=True))
    print(markdown_table(report["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
