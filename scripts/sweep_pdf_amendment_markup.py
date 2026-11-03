#!/usr/bin/env python3
"""Compare PDF amendment markup in two versions of the extractor, page by page.

``amendment_markup`` is opt-in, and only a few manifests turn it on. A change to
how it classifies rules or reads its markup back can still change any page it
might read, so this script reads every page of every PDF it is given twice: with
the extractor at a base git ref, and with the extractor in the working tree.

    # Every locked PDF (fetch them first: axiom-corpus-ingest corpus fetch --all)
    uv run python scripts/sweep_pdf_amendment_markup.py run \\
        --base-ref origin/main --out-dir ~/.axiom/workspace/amendment-markup-sweep

    # Chosen PDFs, against an exported tree instead of a git ref
    uv run python scripts/sweep_pdf_amendment_markup.py run \\
        --base-src /path/to/other/src --out-dir sweep --pdf a.pdf --paths-from list.txt

On each side, for each page, it records:

- the default page text (``_pdf_page_text``, normalized), which every manifest
  without ``amendment_markup`` extracts; and
- the page read with ``amendment_markup: true`` (``_pdf_page_layered_text``, as
  ``_extract_pdf_blocks`` calls it): the marked text, its metadata and its
  ``PdfAmendmentMarkupWarning`` messages, or the error that refuses the page.
  The sweep reads the marked text back itself (``read_marked_text``) and keeps
  the state of each non-space character (plain, deleted or inserted).

The comparison sorts every page into one outcome:

==========================  ===================================================
``identical``               same default text; same marked text, metadata and
                            warnings, or the same error
``fixed``                   the base refuses the page; the working tree marks it
``refused_differently``     both refuse the page, with different errors
``newly_refused``           the base marks the page; the working tree refuses it
``marks_removed``           both mark it; every character whose state differs is
                            plain in the working tree
``marks_added``             both mark it; every such character is plain in the base
``marks_changed``           both mark it, and states differ in another way
``same_marks_other_output`` the same character states, but other marked text
                            (runs joined across spaces differently), metadata or
                            warnings
``read_back_mismatch``      a side's marked text does not read back to its
                            default text
``default_text_changed``    the default page text differs
==========================  ===================================================

A PDF whose page count differs is ``page_count_differs``; one read with
different bytes on the two sides, or bytes other than the lock's, is
``bytes_differ``; one either side could not open is ``unreadable``.

``run`` exits 0 when the sweep passes: every PDF was read on both sides with
the same bytes, and no page is ``newly_refused``, ``marks_*``,
``same_marks_other_output``, ``read_back_mismatch`` or ``default_text_changed``,
except the outcomes named with ``--allow``. It exits 1 when a page fails, and 2
when the sweep is incomplete (a PDF is missing, unreadable or timed out). The
report goes to stdout and to ``report.json`` in the output directory, and every
page that is not ``identical`` to ``details.jsonl``.

Each side's records go to a JSONL file named after its code
(``snapshot-<digest of src/axiom_corpus>.jsonl``), written per PDF. A rerun
with the same code skips finished PDFs, so an interrupted run (Ctrl-C)
resumes, and a run whose base is the head of an earlier run in the same output
directory reuses that snapshot. ``--retry-errors`` reruns PDFs recorded as
timed out or as killing their worker. ``compare`` compares two existing
snapshot files again, with other ``--allow`` outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import time
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compare_pdf_extraction_versions import (  # noqa: E402
    _bytes_check,
    _latest,
    _locked_files,
    _quiet_mupdf,
    _read_jsonl,
    digest,
    run_snapshot,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTION: dict[str, Any] = {"amendment_markup": True}
# A page entry: the default text (digest, length); the markup outcome ("ok" or
# "error"); the marked text's digest, or the error; the metadata's digest; the
# states of the non-space characters (run-length, "P12D3P40"); the digest of the
# warning messages; the number of Type 3 fonts the page uses.
DEFAULT, DEFAULT_LENGTH, OUTCOME, DETAIL, METADATA, STATES, WARNINGS, TYPE3_FONTS = range(8)
ERROR_CHARS = 300
PLAIN, DELETED, INSERTED = "P", "D", "I"
_OPENERS = {"[-": (DELETED, "-]"), "{+": (INSERTED, "+}")}
_SIGNATURE = re.compile(r"(?:[PDI][0-9]+)*")
# Outcomes that fail the sweep unless named with --allow.
FAILING = (
    "newly_refused",
    "marks_removed",
    "marks_added",
    "marks_changed",
    "same_marks_other_output",
    "read_back_mismatch",
    "default_text_changed",
)
INCOMPLETE = ("missing_on_a_side", "unreadable", "timeout", "worker_died")
PDF_FAILING = ("page_count_differs", "bytes_differ")


# ----------------------------------------------------------------- marked text


def read_marked_text(text: str) -> list[tuple[str, str]]:
    """Split wdiff-marked text into (text, state) runs, read left to right.

    Outside a run only an opener (``[-`` or ``{+``) is a delimiter, and inside a
    run only that run's closer (``-]`` or ``+}``) is, the first one ending the
    run. That is how ``_render_amendment_markup`` writes a run whose last
    character and closer make a token (a struck "[" is ``[-[-]``). Markup an
    older extractor accepted, which holds no delimiter inside a run or between
    runs, reads the same way. A run left open raises ``ValueError``.
    """
    runs: list[tuple[str, str]] = []
    position = 0
    while position < len(text):
        found = [(text.find(opener, position), opener) for opener in _OPENERS]
        found = [(start, opener) for start, opener in found if start >= 0]
        if not found:
            runs.append((text[position:], PLAIN))
            break
        start, opener = min(found)
        if start > position:
            runs.append((text[position:start], PLAIN))
        state, closer = _OPENERS[opener]
        end = text.find(closer, start + len(opener))
        if end < 0:
            raise ValueError(f"marked run opened at offset {start} is never closed")
        runs.append((text[start + len(opener) : end], state))
        position = end + len(closer)
    return runs


def state_signature(runs: list[tuple[str, str]]) -> str:
    """Run-length states of the runs' non-space characters, such as ``P12D3P40``."""
    parts: list[tuple[str, int]] = []
    for text, state in runs:
        count = sum(1 for character in text if not character.isspace())
        if not count:
            continue
        if parts and parts[-1][0] == state:
            parts[-1] = (state, parts[-1][1] + count)
        else:
            parts.append((state, count))
    return "".join(f"{state}{count}" for state, count in parts)


def expand_signature(signature: str) -> str:
    """One state letter per non-space character."""
    out: list[str] = []
    state, digits = "", ""
    for character in signature + PLAIN:
        if character.isdigit():
            digits += character
            continue
        if state:
            out.append(state * int(digits))
        state, digits = character, ""
    return "".join(out)


# -------------------------------------------------------------------- snapshot


def _import_documents(src: str) -> Any:
    """``axiom_corpus.corpus.documents`` from ``src``; refuse one imported from elsewhere."""
    wanted = Path(src).resolve()
    if sys.path[:1] != [str(wanted)]:
        sys.path.insert(0, str(wanted))
    from axiom_corpus.corpus import documents

    actual = Path(documents.__file__).resolve()
    if not actual.is_relative_to(wanted):
        raise RuntimeError(f"documents imported from {actual}, not from {wanted}")
    return documents


def _page_entry(documents: Any, page: Any, number: int, markup: Any) -> list[Any]:
    default_text = documents._normalize_text(documents._pdf_page_text(page, extraction={}))
    type3 = sum(1 for font in page.get_fonts() if font[2] == "Type3")
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            text, metadata = documents._pdf_page_layered_text(
                page, extraction=EXTRACTION, markup=markup, page_number=number
            )
    except Exception as exc:  # noqa: BLE001 - recorded and compared, not hidden
        message = f"{type(exc).__name__}: {exc}"[:ERROR_CHARS]
        return [digest(default_text), len(default_text), "error", message, "", "", "", type3]
    try:
        runs = read_marked_text(text)
    except ValueError:
        states = "unreadable"
    else:
        stripped = "".join(run for run, _state in runs)
        states = state_signature(runs) if stripped == default_text else "mismatch"
    return [
        digest(default_text),
        len(default_text),
        "ok",
        digest(text),
        digest(json.dumps(metadata, sort_keys=True, default=str)),
        states,
        digest("\n".join(str(item.message) for item in caught)),
        type3,
    ]


def snapshot_markup(task: dict[str, Any], root: str) -> dict[str, Any]:
    """Read every page of one PDF with the extractor in ``task["src"]``."""
    started = time.monotonic()
    result: dict[str, Any] = {"key": task["key"], "path": task["path"]}
    try:
        documents = _import_documents(task["src"])
    except Exception as exc:  # noqa: BLE001 - recorded, and fails the comparison
        result["error"] = f"code: {type(exc).__name__}: {exc}"[:ERROR_CHARS]
        return result
    import fitz

    _quiet_mupdf()
    result["code"] = task["code"]
    markup = documents._pdf_amendment_markup_config(EXTRACTION)
    path = Path(root) / task["path"]
    try:
        content = path.read_bytes()
    except OSError as exc:
        result["error"] = f"read: {exc!r}"[:ERROR_CHARS]
        return result
    result["pdf_sha256"] = hashlib.sha256(content).hexdigest()
    try:
        with fitz.open(stream=content, filetype="pdf") as document:
            result["pages"] = [
                _page_entry(documents, page, number, markup)
                for number, page in enumerate(document, start=1)
            ]
    except Exception as exc:  # noqa: BLE001 - recorded and compared, not hidden
        result["error"] = f"open: {type(exc).__name__}: {exc}"[:ERROR_CHARS]
    result["seconds"] = round(time.monotonic() - started, 3)
    return result


# ------------------------------------------------------------------------ plan


def locked_pdfs(root: Path) -> list[dict[str, Any]]:
    """One task per distinct locked source PDF (by sha256), at the first of its paths."""
    paths: dict[str, str] = {}
    for _scope, entry in _locked_files(root):
        path = entry["path"]
        if path.startswith("data/corpus/sources/") and path.lower().endswith(".pdf"):
            paths[entry["sha256"]] = min(path, paths.get(entry["sha256"], path))
    return [
        {"key": sha256, "path": path, "sha256": sha256}
        for sha256, path in sorted(paths.items(), key=lambda item: item[1])
    ]


def listed_pdfs(root: Path, paths: list[str]) -> list[dict[str, Any]]:
    """One task per listed file; a path inside ``root`` is kept relative to it."""
    tasks: dict[str, dict[str, Any]] = {}
    for name in paths:
        path = Path(name).expanduser().resolve()
        key = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
        tasks[key] = {"key": key, "path": key, "sha256": None}
    return list(tasks.values())


def export_tree(root: Path, ref: str, out_dir: Path) -> tuple[Path, str]:
    """Export ``src/axiom_corpus`` at ``ref`` into ``out_dir``; return its src dir and commit."""
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", f"{ref}^{{commit}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    target = out_dir / f"base-src-{commit[:12]}"
    src = target / "src"
    if not (src / "axiom_corpus" / "corpus" / "documents.py").is_file():
        archive = subprocess.run(
            ["git", "-C", str(root), "archive", "--format=tar", commit, "src/axiom_corpus"],
            check=True,
            capture_output=True,
        ).stdout
        partial = out_dir / f".base-src-{commit[:12]}.partial"
        for leftover in (partial, target):
            shutil.rmtree(leftover, ignore_errors=True)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(partial, filter="data")
        partial.replace(target)
    return src, commit


def tree_digest(src: Path) -> str:
    """SHA-256 over the paths and bytes of every file under ``src/axiom_corpus``."""
    hasher = hashlib.sha256()
    package = src / "axiom_corpus"
    for path in sorted(package.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            hasher.update(path.relative_to(package).as_posix().encode() + b"\0")
            hasher.update(hashlib.sha256(path.read_bytes()).digest())
    return hasher.hexdigest()


# --------------------------------------------------------------------- compare


def _is_signature(states: str) -> bool:
    return _SIGNATURE.fullmatch(states) is not None


def classify_page(base: list[Any], head: list[Any]) -> str:
    """The outcome of one page read on both sides (see the module docstring)."""
    if base[DEFAULT] != head[DEFAULT]:
        return "default_text_changed"
    base_ok, head_ok = base[OUTCOME] == "ok", head[OUTCOME] == "ok"
    if not base_ok and not head_ok:
        return "identical" if base[DETAIL] == head[DETAIL] else "refused_differently"
    if not base_ok:
        return "fixed" if _is_signature(head[STATES]) else "read_back_mismatch"
    if not head_ok:
        return "newly_refused"
    if not (_is_signature(base[STATES]) and _is_signature(head[STATES])):
        return "read_back_mismatch"
    if base[DETAIL : WARNINGS + 1] == head[DETAIL : WARNINGS + 1]:
        return "identical"
    base_states, head_states = expand_signature(base[STATES]), expand_signature(head[STATES])
    if len(base_states) != len(head_states):
        return "read_back_mismatch"
    changed = [(a, b) for a, b in zip(base_states, head_states, strict=True) if a != b]
    if not changed:
        return "same_marks_other_output"
    if all(b == PLAIN for _a, b in changed):
        return "marks_removed"
    if all(a == PLAIN for a, _b in changed):
        return "marks_added"
    return "marks_changed"


def _changed_characters(base: list[Any], head: list[Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    both_read = base[OUTCOME] == head[OUTCOME] == "ok"
    if both_read and _is_signature(base[STATES]) and _is_signature(head[STATES]):
        base_states, head_states = expand_signature(base[STATES]), expand_signature(head[STATES])
        if len(base_states) == len(head_states):
            for a, b in zip(base_states, head_states, strict=True):
                if a != b:
                    counts[f"{a}>{b}"] += 1
    return dict(sorted(counts.items()))


def _record_error_kind(record: dict[str, Any]) -> str:
    error = str(record.get("error", ""))
    if error.startswith("timeout after"):
        return "timeout"
    if error.startswith("worker exited"):
        return "worker_died"
    return "unreadable"


def compare(
    plan: list[dict[str, Any]],
    base_records: list[dict[str, Any]],
    head_records: list[dict[str, Any]],
    *,
    allow: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compare two snapshots of ``plan``; return the report and the non-identical pages."""
    unknown = allow - set(FAILING)
    if unknown:
        raise ValueError(f"--allow takes outcomes from {list(FAILING)}, not {sorted(unknown)}")
    base, head = _latest(base_records), _latest(head_records)
    pdfs: Counter[str] = Counter()
    pages: Counter[str] = Counter()
    type3_pages: Counter[str] = Counter()
    details: list[dict[str, Any]] = []
    codes: dict[str, set[str]] = {"base": set(), "head": set()}
    for task in plan:
        pdfs["planned"] += 1
        a, b = base.get(task["key"]), head.get(task["key"])
        if a is None or b is None:
            pdfs["missing_on_a_side"] += 1
            details.append({"path": task["path"], "outcome": "missing_on_a_side"})
            continue
        for side, record in (("base", a), ("head", b)):
            if record.get("code"):
                codes[side].add(record["code"])
        if _bytes_check(a, b, task.get("sha256")) == "differ":
            pdfs["bytes_differ"] += 1
            details.append({"path": task["path"], "outcome": "bytes_differ"})
            continue
        if a.get("error") or b.get("error"):
            kind = _record_error_kind(a if a.get("error") else b)
            pdfs[kind] += 1
            details.append(
                {"path": task["path"], "outcome": kind, "errors": [a.get("error"), b.get("error")]}
            )
            continue
        if len(a["pages"]) != len(b["pages"]):
            pdfs["page_count_differs"] += 1
            details.append(
                {
                    "path": task["path"],
                    "outcome": "page_count_differs",
                    "pages": [len(a["pages"]), len(b["pages"])],
                }
            )
            continue
        pdfs["compared"] += 1
        outcomes: Counter[str] = Counter()
        for number, (x, y) in enumerate(zip(a["pages"], b["pages"], strict=True), start=1):
            outcome = classify_page(x, y)
            outcomes[outcome] += 1
            pages[outcome] += 1
            if y[TYPE3_FONTS]:
                type3_pages[outcome] += 1
            if outcome != "identical":
                details.append(
                    {
                        "path": task["path"],
                        "page": number,
                        "outcome": outcome,
                        "type3_fonts": y[TYPE3_FONTS],
                        "base": x[DETAIL] if x[OUTCOME] == "error" else "marked",
                        "head": y[DETAIL] if y[OUTCOME] == "error" else "marked",
                        "changed_characters": _changed_characters(x, y),
                    }
                )
        if set(outcomes) != {"identical"}:
            pdfs["with_a_page_not_identical"] += 1
    failing = {name: pages[name] for name in FAILING if pages[name] and name not in allow}
    failing.update({name: pdfs[name] for name in PDF_FAILING if pdfs[name]})
    incomplete = {name: pdfs[name] for name in INCOMPLETE if pdfs[name]}
    if any(len(found) > 1 for found in codes.values()):
        failing["code_differs_within_a_side"] = 1
    verdict = "fail" if failing else ("incomplete" if incomplete else "pass")
    report = {
        "verdict": verdict,
        "failing": failing,
        "incomplete": incomplete,
        "allowed": sorted(allow),
        "pdfs": dict(sorted(pdfs.items())),
        "pages": dict(sorted(pages.items())),
        "pages_with_a_type3_font": dict(sorted(type3_pages.items())),
        "code": {side: sorted(found) for side, found in codes.items()},
    }
    return report, details


def _write_report(out_dir: Path, report: dict[str, Any], details: list[dict[str, Any]]) -> None:
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (out_dir / "details.jsonl").open("w", encoding="utf-8") as handle:
        for item in details:
            handle.write(json.dumps(item, sort_keys=True) + "\n")


def _exit_code(report: dict[str, Any]) -> int:
    return {"pass": 0, "fail": 1, "incomplete": 2}[report["verdict"]]


# ------------------------------------------------------------------------- CLI


def _plan(root: Path, args: argparse.Namespace) -> list[dict[str, Any]]:
    names = list(args.pdf or [])
    if args.paths_from:
        lines = args.paths_from.read_text(encoding="utf-8").splitlines()
        names += [line.strip() for line in lines if line.strip()]
    return listed_pdfs(root, names) if names else locked_pdfs(root)


def _snapshot(
    plan: list[dict[str, Any]],
    out_path: Path,
    *,
    root: Path,
    src: Path,
    code: str,
    args: argparse.Namespace,
) -> None:
    tasks = [{**task, "kind": "pdf", "src": str(src), "code": code} for task in plan]
    started = time.monotonic()
    count = run_snapshot(
        tasks,
        out_path,
        root=root,
        kinds={"pdf"},
        workers=args.workers,
        timeout=args.timeout,
        retry_errors=args.retry_errors,
        task_function=snapshot_markup,
    )
    print(f"{out_path.name}: {count} PDF(s) in {time.monotonic() - started:.0f}s", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root")
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="snapshot both sides and compare them")
    base = run_parser.add_mutually_exclusive_group(required=True)
    base.add_argument("--base-ref", help="git ref whose src/axiom_corpus is the base")
    base.add_argument("--base-src", type=Path, help="a src directory holding axiom_corpus")
    run_parser.add_argument("--out-dir", type=Path, required=True)
    run_parser.add_argument("--pdf", action="append", help="a PDF to read (repeatable)")
    run_parser.add_argument("--paths-from", type=Path, help="a file listing PDFs, one per line")
    run_parser.add_argument("--workers", type=int, default=2, help="worker processes per side")
    run_parser.add_argument("--timeout", type=float, default=900, help="seconds per PDF")
    run_parser.add_argument("--retry-errors", action="store_true")
    run_parser.add_argument("--allow", action="append", default=[], choices=FAILING)

    compare_parser = commands.add_parser("compare", help="compare two existing snapshots")
    compare_parser.add_argument("--out-dir", type=Path, required=True)
    compare_parser.add_argument("--base", type=Path, required=True)
    compare_parser.add_argument("--head", type=Path, required=True)
    compare_parser.add_argument("--allow", action="append", default=[], choices=FAILING)

    args = parser.parse_args(argv)
    root = args.root.resolve()
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    allow = frozenset(args.allow)
    if args.command == "compare":
        plan = _read_jsonl(out_dir / "plan.jsonl")
        report, details = compare(plan, _read_jsonl(args.base), _read_jsonl(args.head), allow=allow)
        _write_report(out_dir, report, details)
        print(json.dumps(report, indent=2))
        return _exit_code(report)

    if args.workers < 1:
        parser.error("--workers must be at least 1: each side's code runs in its own processes")
    plan = _plan(root, args)
    with (out_dir / "plan.jsonl").open("w", encoding="utf-8") as handle:
        for task in plan:
            handle.write(json.dumps(task, sort_keys=True) + "\n")
    commit = None
    if args.base_ref:
        base_src, commit = export_tree(root, args.base_ref, out_dir)
    else:
        base_src = args.base_src.expanduser().resolve()
    head_src = root / "src"
    base_digest, head_digest = tree_digest(base_src), tree_digest(head_src)
    if base_digest == head_digest:
        parser.error("the base and the working tree hold the same src/axiom_corpus")
    # A snapshot is named after its code, so a later run reuses it: the head of one
    # change is the base of the change stacked on it.
    base_name, head_name = f"snapshot-{base_digest[:12]}", f"snapshot-{head_digest[:12]}"
    base_path, head_path = out_dir / f"{base_name}.jsonl", out_dir / f"{head_name}.jsonl"
    print(f"{len(plan)} PDF(s); base {base_src}, head {head_src}", file=sys.stderr)
    _snapshot(plan, base_path, root=root, src=base_src, code=base_name, args=args)
    _snapshot(plan, head_path, root=root, src=head_src, code=head_name, args=args)
    report, details = compare(plan, _read_jsonl(base_path), _read_jsonl(head_path), allow=allow)
    report["snapshots"] = {
        "base": base_path.name,
        "base_ref": args.base_ref,
        "base_commit": commit,
        "head": head_path.name,
    }
    _write_report(out_dir, report, details)
    print(json.dumps(report, indent=2))
    return _exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
