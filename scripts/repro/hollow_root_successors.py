#!/usr/bin/env python3
"""Rebuild the scopes behind the fixed hollow-document-root findings as successor scopes.

The 2026-10-13 audit (docs/ingest-runs/2026-10-13-hollow-document-root-audit.md)
traced 93 of PR #847's ``hollow_document_root`` findings to extractor or builder
defects that are now fixed: the NYCRR Notes text (``.co_refsAnnos``), the CMS
SPA index pages (``INDEX_PAGE_EXTRACTION``) and scanned attachments (the OCR
overlay rule), the CHIP FCEP summaries and the Maryland TCA statutes
(``html_text_selector``), the 106 CMR 701/702 start markers, and the Canadian
composite's empty primary-document leaf (477c6650c). Merged scopes are
immutable, so each fix reaches the corpus only through a successor scope:
``<original version>-r2026-10-13-hollow-roots``.

Every successor is rebuilt from its original's retained bytes. Nothing is
fetched: the network is blocked for the whole run, official documents are
served from the original scope's sources (with the content type and final URL
the original inventory recorded), the NYCRR adapter reads the retained pages
from a copy placed under the successor version, and the Canadian composite is
recomposed from the merged scope itself, as the oracle-complete v2 scope was.

Run from the repository root:

    uv run --extra dev python scripts/repro/hollow_root_successors.py build \\
        --base data/corpus --workers 4 --ocr-cache ~/.axiom/ocr-cache

``--source-base`` (default ``--base``) is where the originals are read, so the
same command run from another checkout into a scratch base is a control
build with that checkout's code and manifests. ``compare`` writes the
per-scope comparison of two builds (or of a build and the originals).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

REVISION = "r2026-10-13-hollow-roots"

STATE_PLAN_JURISDICTIONS = (
    "us-ak", "us-al", "us-ar", "us-az", "us-ca", "us-co", "us-ct", "us-dc", "us-de",
    "us-fl", "us-ga", "us-hi", "us-ia", "us-id", "us-il", "us-in", "us-ks", "us-ky",
    "us-la", "us-ma", "us-md", "us-me", "us-mi", "us-mn", "us-mo", "us-ms", "us-mt",
    "us-nc", "us-nd", "us-ne", "us-nh", "us-nj", "us-nm", "us-nv", "us-ny", "us-oh",
    "us-ok", "us-or", "us-pa", "us-ri", "us-sc", "us-sd", "us-tn", "us-tx", "us-ut",
    "us-va", "us-vt", "us-wa", "us-wi", "us-wv", "us-wy",
)  # fmt: skip


@dataclass(frozen=True)
class SuccessorSpec:
    """One original scope and how its successor is rebuilt."""

    jurisdiction: str
    document_class: str
    original_version: str
    kind: str  # official-documents | nycrr | ca-composite
    manifest: str
    # The original command's --source-as-of / --expression-date. None reproduces
    # the original default, which the extractors derive from the version.
    source_as_of: str | None = None
    expression_date: str | None = None

    @property
    def version(self) -> str:
        return f"{self.original_version}-{REVISION}"

    @property
    def original_key(self) -> str:
        return f"{self.jurisdiction}/{self.document_class}/{self.original_version}"

    @property
    def key(self) -> str:
        return f"{self.jurisdiction}/{self.document_class}/{self.version}"


def successor_specs() -> tuple[SuccessorSpec, ...]:
    specs = [
        SuccessorSpec(
            "us-ny",
            "regulation",
            "2026-09-14-income-tax-regulations",
            "nycrr",
            "manifests/us-ny-income-tax-regulations.yaml",
            "2026-09-14",
            "2026-09-14",
        ),
        SuccessorSpec(
            "us-ny",
            "regulation",
            "2026-07-17-ny-snap-regulations",
            "nycrr",
            "manifests/us-ny-snap-regulations.yaml",
            "2026-07-17",
            "2026-07-17",
        ),
    ]
    for program in ("medicaid", "chip"):
        for jurisdiction in STATE_PLAN_JURISDICTIONS:
            specs.append(
                SuccessorSpec(
                    jurisdiction,
                    "policy",
                    f"2026-09-13-{program}-state-plan",
                    "official-documents",
                    f"manifests/{jurisdiction}-{program}-state-plan.yaml",
                )
            )
    specs.extend(
        (
            SuccessorSpec(
                "us",
                "policy",
                "2026-07-05-cms-chip-fcep-spa",
                "official-documents",
                "manifests/us-cms-chip-fcep-spa-official-documents.yaml",
            ),
            SuccessorSpec(
                "us-md",
                "statute",
                "2026-07-03-md-tca-statutes",
                "official-documents",
                "manifests/us-md-tca-statutes-official-documents.yaml",
                "2026-07-03",
                "2026-07-03",
            ),
            SuccessorSpec(
                "us-ma",
                "regulation",
                "2026-06-27-ma-tafdc-regulations",
                "official-documents",
                "manifests/us-ma-tafdc-regulations.yaml",
            ),
            SuccessorSpec(
                "ca",
                "policy",
                "2026-07-21-ca-rulespec-source-complete",
                "ca-composite",
                "manifests/releases/ca-rulespec-2026-07-21-source-complete.json",
            ),
        )
    )
    return tuple(specs)


CA_CITATION_CONTRACT = "tests/fixtures/releases/ca-rulespec-2026-07-21-complete-citations.json"


# --------------------------------------------------------------------------- offline guards


class NetworkBlockedError(RuntimeError):
    """A successor build tried to reach the network."""


def block_network() -> Callable[[], None]:
    """Make every IP connection from this process fail; successors read retained bytes only.

    Returns a function that restores the patched callables.
    """
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def connect(self: socket.socket, address: Any) -> Any:
        if self.family == socket.AF_UNIX:
            return real_connect(self, address)
        raise NetworkBlockedError(f"network blocked during successor build: {address!r}")

    def connect_ex(self: socket.socket, address: Any) -> Any:
        if self.family == socket.AF_UNIX:
            return real_connect_ex(self, address)
        raise NetworkBlockedError(f"network blocked during successor build: {address!r}")

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise NetworkBlockedError("curl_cffi request blocked during successor build")

    patched: list[tuple[Any, str, Any]] = [
        (socket.socket, "connect", connect),
        (socket.socket, "connect_ex", connect_ex),
    ]
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:  # pragma: no cover
        pass
    else:
        patched += [(curl_requests, "get", refuse), (curl_requests, "request", refuse)]
    originals = [(owner, name, getattr(owner, name)) for owner, name, _ in patched]
    for owner, name, replacement in patched:
        setattr(owner, name, replacement)

    def restore() -> None:
        for owner, name, original in originals:
            setattr(owner, name, original)

    return restore


class _NoNetworkSession:
    """A NYCRR session that refuses every request: all pages come from the retained copy."""

    def get(self, url: str, timeout: float | None = None) -> Any:
        raise NetworkBlockedError(f"NYCRR page not retained: {url}")


@dataclass
class OcrStats:
    hits: int = 0
    misses: int = 0


_OCR_STATS = OcrStats()


def install_ocr_cache(cache_dir: Path) -> None:
    """Cache Tesseract output by the exact rendered page image, language and mode.

    The key is the SHA-256 of the pixmap the OCR step renders (its size, channel
    count and samples) together with the dpi, language and page segmentation
    mode, so a cached text is only ever reused for byte-identical input to
    Tesseract. It only saves time across the control and successor builds.
    """
    import axiom_corpus.corpus.documents as documents

    real = documents._ocr_pdf_page_text
    cache_dir.mkdir(parents=True, exist_ok=True)

    def cached(page: Any, *, extraction: dict[str, Any]) -> str:
        dpi = documents._pdf_ocr_dpi(extraction)
        language = str(extraction.get("ocr_language") or "eng")
        psm = extraction.get("ocr_psm")
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
        digest = hashlib.sha256()
        digest.update(f"{pixmap.width}x{pixmap.height}x{pixmap.n}|{dpi}|{language}|{psm}|".encode())
        digest.update(pixmap.samples)
        name = digest.hexdigest()
        path = cache_dir / name[:2] / f"{name}.txt"
        if path.exists():
            _OCR_STATS.hits += 1
            return path.read_bytes().decode("utf-8")
        text: str = real(page, extraction=extraction)
        _OCR_STATS.misses += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{name}.{os.getpid()}.tmp")
        temporary.write_bytes(text.encode("utf-8"))
        os.replace(temporary, path)
        return text

    documents._ocr_pdf_page_text = cached


# --------------------------------------------------------------------------- builds


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scope_files(root: Path) -> dict[str, str]:
    """Relative path -> sha256 for every file under ``root`` (hidden files included)."""
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _artifact_paths(
    base: Path, jurisdiction: str, document_class: str, version: str
) -> dict[str, Path]:
    return {
        "sources": base / "sources" / jurisdiction / document_class / version,
        "inventory": base / "inventory" / jurisdiction / document_class / f"{version}.json",
        "provisions": base / "provisions" / jurisdiction / document_class / f"{version}.jsonl",
        "coverage": base / "coverage" / jurisdiction / document_class / f"{version}.json",
    }


def _refuse_existing(paths: Mapping[str, Path], *, key: str) -> None:
    present = [str(path) for path in paths.values() if path.exists()]
    if present:
        raise FileExistsError(f"successor {key} already exists: {present}")


def build_official_documents(
    spec: SuccessorSpec, *, base: Path, source_base: Path
) -> dict[str, Any]:
    """Re-extract one official-documents scope from its retained sources."""
    import axiom_corpus.corpus.documents as documents
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore
    from axiom_corpus.corpus.io import load_source_inventory

    original = _artifact_paths(
        source_base, spec.jurisdiction, spec.document_class, spec.original_version
    )
    inventory = load_source_inventory(original["inventory"])
    roots = {
        item.citation_path: item
        for item in inventory
        if (item.metadata or {}).get("kind") == "document"
    }
    manifest = documents.OfficialDocumentManifest.load(spec.manifest)
    manifest.require_unique_sources()
    retained: dict[str, tuple[Path, str, str | None, str, str]] = {}
    for source in manifest.documents:
        root_path = documents._root_citation_path(source)
        item = roots.get(root_path)
        if item is None:
            raise ValueError(
                f"{spec.original_key}: manifest document {root_path} has no original root"
            )
        metadata = item.metadata or {}
        if item.source_path is None:
            raise ValueError(f"{spec.original_key}: {root_path} has no retained source")
        retained[source.source_id] = (
            source_base / item.source_path,
            str(item.sha256),
            metadata.get("content_type"),
            str(metadata.get("download_url") or source.source_url),
            str(item.source_format),
        )
    unmatched = sorted(set(roots) - {documents._root_citation_path(s) for s in manifest.documents})
    if unmatched:
        raise ValueError(
            f"{spec.original_key}: original roots missing from the manifest: {unmatched}"
        )

    def retained_document(source: Any, *, session: Any) -> Any:
        path, sha256, content_type, final_url, _ = retained[source.source_id]
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != sha256:
            raise ValueError(f"retained source changed: {path}")
        return documents._DownloadedDocument(
            source=source, content=content, content_type=content_type, final_url=final_url
        )

    successor = _artifact_paths(base, spec.jurisdiction, spec.document_class, spec.version)
    _refuse_existing(successor, key=spec.key)
    real_download = documents._download_document
    documents._download_document = retained_document
    try:
        report = documents.extract_official_documents(
            CorpusArtifactStore(base),
            manifest_path=spec.manifest,
            version=spec.version,
            source_as_of=spec.source_as_of or spec.original_version,
            expression_date=spec.expression_date,
        )
    finally:
        documents._download_document = real_download
    return {"coverage_complete": report.coverage.complete, "provisions": report.provisions_written}


def build_nycrr(spec: SuccessorSpec, *, base: Path, source_base: Path) -> dict[str, Any]:
    """Re-run the NYCRR adapter over a copy of the retained Westlaw pages."""
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore
    from axiom_corpus.corpus.cli import _load_nycrr_adopted_amendments, _load_nycrr_part_sources
    from axiom_corpus.corpus.nycrr import extract_nycrr_parts

    original = _artifact_paths(
        source_base, spec.jurisdiction, spec.document_class, spec.original_version
    )
    successor = _artifact_paths(base, spec.jurisdiction, spec.document_class, spec.version)
    _refuse_existing(successor, key=spec.key)
    retained = _scope_files(original["sources"])
    for relative in retained:
        target = successor["sources"] / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original["sources"] / relative, target)
    manifest = Path(spec.manifest)
    report = extract_nycrr_parts(
        CorpusArtifactStore(base),
        version=spec.version,
        part_sources=_load_nycrr_part_sources(manifest),
        adopted_amendments=_load_nycrr_adopted_amendments(manifest),
        source_as_of=spec.source_as_of,
        expression_date=date.fromisoformat(spec.expression_date) if spec.expression_date else None,
        delay_seconds=0,
        retry_attempts=1,
        refresh=False,
        session=_NoNetworkSession(),
    )
    return {"coverage_complete": report.coverage.complete, "provisions": report.provisions_written}


def build_ca_composite(spec: SuccessorSpec, *, base: Path, source_base: Path) -> dict[str, Any]:
    """Recompose the Canadian source-complete scope with the fixed root normalization."""
    repo = Path.cwd()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    module_spec = importlib.util.spec_from_file_location(
        "_build_ca_rulespec_composite_scope",
        repo / "scripts" / "build_ca_rulespec_composite_scope.py",
    )
    if module_spec is None or module_spec.loader is None:
        raise ImportError("scripts/build_ca_rulespec_composite_scope.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)

    successor = _artifact_paths(base, spec.jurisdiction, spec.document_class, spec.version)
    _refuse_existing(successor, key=spec.key)
    if base.resolve() != source_base.resolve():
        # The composer reads its source scope from the base it writes to.
        original = _artifact_paths(
            source_base, spec.jurisdiction, spec.document_class, spec.original_version
        )
        local = _artifact_paths(base, spec.jurisdiction, spec.document_class, spec.original_version)
        for name, path in original.items():
            if local[name].exists():
                continue
            local[name].parent.mkdir(parents=True, exist_ok=True)
            if path.is_dir():
                shutil.copytree(path, local[name])
            else:
                shutil.copyfile(path, local[name])
    module.build_ca_rulespec_composite_scope(
        base=base,
        selector_path=Path(spec.manifest),
        citation_contract_path=Path(CA_CITATION_CONTRACT),
        target_version=spec.version,
    )
    coverage = json.loads(successor["coverage"].read_text(encoding="utf-8"))
    return {
        "coverage_complete": bool(coverage.get("complete")),
        "provisions": coverage.get("provision_count"),
    }


BUILDERS = {
    "official-documents": build_official_documents,
    "nycrr": build_nycrr,
    "ca-composite": build_ca_composite,
}


def _expected_sources(spec: SuccessorSpec, original_sources: Mapping[str, str]) -> dict[str, str]:
    if spec.kind == "ca-composite":
        # The composer nests each source scope's files under its version.
        return {f"{spec.original_version}/{path}": sha for path, sha in original_sources.items()}
    return dict(original_sources)


def _share_retained_blocks(
    spec: SuccessorSpec, *, base: Path, original_root: Path, successor_root: Path
) -> int:
    """Replace each verified successor source with a copy-on-write clone of its retained file.

    The bytes are already checked equal, so this changes no content; on APFS the
    successor's sources then share blocks with the originals instead of taking a
    second copy on disk. Clones are made outside every scope and moved into place.
    """
    from axiom_corpus.corpus.content_store import clone_file

    staging = base / ".hollow-root-successors-tmp"
    staging.mkdir(parents=True, exist_ok=True)
    nested = f"{spec.original_version}/" if spec.kind == "ca-composite" else ""
    cloned = 0
    for path in sorted(successor_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(successor_root).as_posix()
        source = original_root / relative.removeprefix(nested)
        temporary = staging / f"{os.getpid()}-{cloned}"
        if temporary.exists():
            temporary.unlink()
        if clone_file(source, temporary) == "clonefile":
            os.replace(temporary, path)
            cloned += 1
        else:
            temporary.unlink()
    return cloned


def build_one(
    spec: SuccessorSpec, *, base: Path, source_base: Path, share_blocks: bool = True
) -> dict[str, Any]:
    original = _artifact_paths(
        source_base, spec.jurisdiction, spec.document_class, spec.original_version
    )
    original_sources = _scope_files(original["sources"])
    result = BUILDERS[spec.kind](spec, base=base, source_base=source_base)
    successor = _artifact_paths(base, spec.jurisdiction, spec.document_class, spec.version)
    successor_sources = _scope_files(successor["sources"])
    expected = _expected_sources(spec, original_sources)
    if successor_sources != expected:
        missing = sorted(set(expected) - set(successor_sources))
        extra = sorted(set(successor_sources) - set(expected))
        changed = sorted(
            path
            for path in set(expected) & set(successor_sources)
            if expected[path] != successor_sources[path]
        )
        raise ValueError(
            f"{spec.key}: sources are not the retained bytes "
            f"(missing {missing[:5]}, extra {extra[:5]}, changed {changed[:5]})"
        )
    if not result["coverage_complete"]:
        raise ValueError(f"{spec.key}: coverage is incomplete")
    cloned = (
        _share_retained_blocks(
            spec, base=base, original_root=original["sources"], successor_root=successor["sources"]
        )
        if share_blocks
        else 0
    )
    if cloned and _scope_files(successor["sources"]) != expected:
        raise ValueError(f"{spec.key}: sources changed while sharing blocks")
    return {
        "scope": spec.key,
        "original": spec.original_key,
        "kind": spec.kind,
        "sources": len(successor_sources),
        "sources_cloned": cloned,
        **result,
    }


def _worker_init(ocr_cache: str | None) -> None:
    block_network()
    if ocr_cache:
        install_ocr_cache(Path(ocr_cache).expanduser())


def _free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def _existing_state(spec: SuccessorSpec, base: Path) -> str:
    """``absent``, ``complete`` (coverage written and complete) or ``partial``."""
    paths = _artifact_paths(base, spec.jurisdiction, spec.document_class, spec.version)
    present = [name for name, path in paths.items() if path.exists()]
    if not present:
        return "absent"
    if len(present) == len(paths):
        try:
            coverage = json.loads(paths["coverage"].read_text(encoding="utf-8"))
        except ValueError:
            return "partial"
        if coverage.get("complete") is True:
            return "complete"
    return "partial"


def _remove_successor(spec: SuccessorSpec, base: Path) -> None:
    for path in _artifact_paths(
        base, spec.jurisdiction, spec.document_class, spec.version
    ).values():
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def _worker(
    spec: SuccessorSpec,
    base: str,
    source_base: str,
    resume: bool = False,
    min_free_gb: float | None = None,
) -> dict[str, Any]:
    _OCR_STATS.hits = _OCR_STATS.misses = 0
    try:
        if resume:
            state = _existing_state(spec, Path(base))
            if state == "complete":
                # Built by an earlier, interrupted run: keep it, but only if its
                # sources are still exactly the retained bytes.
                original = _artifact_paths(
                    Path(source_base), spec.jurisdiction, spec.document_class, spec.original_version
                )
                successor = _artifact_paths(
                    Path(base), spec.jurisdiction, spec.document_class, spec.version
                )
                expected = _expected_sources(spec, _scope_files(original["sources"]))
                if _scope_files(successor["sources"]) != expected:
                    raise ValueError(f"{spec.key}: existing successor sources differ")
                return {"scope": spec.key, "original": spec.original_key, "skipped": "complete"}
            if state == "partial":
                _remove_successor(spec, Path(base))
        if min_free_gb is not None and _free_gb(Path(base)) < min_free_gb:
            return {
                "scope": spec.key,
                "original": spec.original_key,
                "deferred": f"free disk under {min_free_gb} GB",
            }
        result = build_one(spec, base=Path(base), source_base=Path(source_base))
    except Exception as error:  # reported per scope; the run fails at the end
        return {"scope": spec.key, "error": f"{type(error).__name__}: {error}"}
    return {**result, "ocr_cache_hits": _OCR_STATS.hits, "ocr_runs": _OCR_STATS.misses}


def select_specs(names: Sequence[str]) -> tuple[SuccessorSpec, ...]:
    specs = successor_specs()
    if not names:
        return specs
    chosen = tuple(
        spec
        for spec in specs
        if any(
            spec.original_key == name or spec.original_key.startswith(name.rstrip("/") + "/")
            for name in names
        )
    )
    unmatched = [
        name
        for name in names
        if not any(
            spec.original_key == name or spec.original_key.startswith(name.rstrip("/") + "/")
            for spec in specs
        )
    ]
    if unmatched:
        raise SystemExit(f"no successor spec matches {unmatched}")
    return chosen


def cmd_build(args: argparse.Namespace) -> int:
    base = args.base.resolve()
    source_base = (args.source_base or args.base).resolve()
    specs = select_specs(args.scope)
    results: list[dict[str, Any]] = []
    ocr_cache = str(args.ocr_cache) if args.ocr_cache else None
    if args.workers <= 1:
        _worker_init(ocr_cache)
        for spec in specs:
            results.append(
                _worker(spec, str(base), str(source_base), args.resume, args.min_free_gb)
            )
            print(json.dumps(results[-1]), flush=True)
    else:
        with ProcessPoolExecutor(
            max_workers=args.workers, initializer=_worker_init, initargs=(ocr_cache,)
        ) as pool:
            futures = [
                pool.submit(
                    _worker, spec, str(base), str(source_base), args.resume, args.min_free_gb
                )
                for spec in specs
            ]
            for future in as_completed(futures):
                results.append(future.result())
                print(json.dumps(results[-1]), flush=True)
    shutil.rmtree(base / ".hollow-root-successors-tmp", ignore_errors=True)
    results.sort(key=lambda row: row["scope"])
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    errors = [row for row in results if "error" in row]
    deferred = [row for row in results if "deferred" in row]
    skipped = [row for row in results if "skipped" in row]
    built = len(results) - len(errors) - len(deferred) - len(skipped)
    print(
        f"built {built} of {len(results)} successor scopes "
        f"({len(skipped)} already complete, {len(deferred)} deferred, {len(errors)} failed)",
        file=sys.stderr,
    )
    return 1 if errors else 2 if deferred else 0


# --------------------------------------------------------------------------- comparison


def _rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def source_prefix_map(
    spec: SuccessorSpec, left_version: str, right_version: str
) -> tuple[str, str]:
    """The source-path prefix of ``left_version`` and what it becomes in ``right_version``.

    Official-document and NYCRR successors keep each retained file at the same
    relative path under the new version. The Canadian composer nests a source
    scope's files under that scope's version, so a recomposed original's
    ``<original>/<rest>`` becomes ``<successor>/<original>/<rest>``.
    """
    scope = f"sources/{spec.jurisdiction}/{spec.document_class}"
    left = f"{scope}/{left_version}/"
    if spec.kind == "ca-composite" and left_version == spec.original_version:
        return left, f"{scope}/{right_version}/{spec.original_version}/"
    return left, f"{scope}/{right_version}/"


def _normalize(value: Any, old: str, new: str) -> Any:
    """Rewrite every ``old`` source-path prefix to ``new``, at any depth of one field."""
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [_normalize(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(item, old, new) for key, item in value.items()}
    return value


def _row_key(row: Mapping[str, Any]) -> str:
    return str(row["citation_path"])


def _id_rule(row: Mapping[str, Any], *, name: str, path: str | None, version: str) -> str:
    """Which deterministic rule a row's ``id`` or ``parent_id`` follows."""
    from axiom_corpus.corpus.supabase import deterministic_provision_id

    value = row.get(name)
    if value is None or path is None:
        return "none" if value is None else "unknown"
    if value == deterministic_provision_id(path):
        return "path"
    if value == deterministic_provision_id(path, version):
        return "path+version"
    return "unknown"


def compare_rows(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    *,
    left_version: str,
    right_version: str,
    prefixes: tuple[str, str],
    ignore: Iterable[str] = (),
) -> dict[str, Any]:
    """Summarize how ``right``'s rows differ from ``left``'s, versions normalized.

    ``version`` must be each side's own version; source paths are compared after
    ``prefixes`` maps the left prefix to the right one (at any depth, so the
    NYCRR amendment paths inside ``metadata`` are covered); ``id`` and
    ``parent_id`` must follow the same deterministic rule on both sides
    (path-only, or path and version), each evaluated with its own version.
    """
    ignored = set(ignore)
    old, new = prefixes
    left_by = {_row_key(row): row for row in left}
    right_by = {_row_key(row): row for row in right}
    if len(left_by) != len(left) or len(right_by) != len(right):
        raise ValueError("duplicate citation paths in a compared scope")
    fields: Counter[str] = Counter()
    id_rules: Counter[str] = Counter()
    changed: list[str] = []
    for path in sorted(left_by.keys() & right_by.keys()):
        a, b = left_by[path], right_by[path]
        differing = []
        for name in sorted(set(a) | set(b)):
            if name in ignored:
                continue
            av, bv = a.get(name), b.get(name)
            if name == "version":
                av, bv = (av == left_version), (bv == right_version)
            elif name in ("id", "parent_id") and "id" in a:
                target = path if name == "id" else a.get("parent_citation_path")
                target_b = path if name == "id" else b.get("parent_citation_path")
                av = _id_rule(a, name=name, path=target, version=left_version)
                bv = _id_rule(b, name=name, path=target_b, version=right_version)
                id_rules[f"{name}:{av}->{bv}"] += 1
                if av == "unknown" or bv == "unknown":
                    av, bv = a.get(name), b.get(name)
            else:
                av = _normalize(av, old, new)
            if av != bv:
                differing.append(name)
        if differing:
            changed.append(path)
            fields.update(differing)
    order_left = [path for path in (_row_key(row) for row in left) if path in right_by]
    order_right = [path for path in (_row_key(row) for row in right) if path in left_by]
    return {
        "left": len(left),
        "right": len(right),
        "removed": sorted(left_by.keys() - right_by.keys()),
        "added": sorted(right_by.keys() - left_by.keys()),
        "changed": changed,
        "changed_fields": dict(sorted(fields.items())),
        "id_rules": dict(sorted(id_rules.items())),
        "order_preserved": order_left == order_right,
        "left_body_chars": sum(len(row.get("body") or "") for row in left),
        "right_body_chars": sum(len(row.get("body") or "") for row in right),
    }


def compare_scope(
    spec: SuccessorSpec,
    *,
    left_base: Path,
    left_version: str,
    right_base: Path,
    right_version: str,
) -> dict[str, Any]:
    left = _artifact_paths(left_base, spec.jurisdiction, spec.document_class, left_version)
    right = _artifact_paths(right_base, spec.jurisdiction, spec.document_class, right_version)
    prefixes = source_prefix_map(spec, left_version, right_version)
    left_inventory = json.loads(left["inventory"].read_text(encoding="utf-8"))
    right_inventory = json.loads(right["inventory"].read_text(encoding="utf-8"))
    left_coverage = json.loads(left["coverage"].read_text(encoding="utf-8"))
    right_coverage = json.loads(right["coverage"].read_text(encoding="utf-8"))
    coverage_fields = sorted(
        name
        for name in set(left_coverage) | set(right_coverage)
        if name != "version" and left_coverage.get(name) != right_coverage.get(name)
    )
    left_sources = _scope_files(left["sources"])
    right_sources = _scope_files(right["sources"])
    old, new = prefixes
    nested = new.removeprefix(f"sources/{spec.jurisdiction}/{spec.document_class}/{right_version}/")
    expected_sources = {f"{nested}{path}": sha for path, sha in left_sources.items()}
    return {
        "scope": spec.original_key,
        "left_version": left_version,
        "right_version": right_version,
        "sources_identical": expected_sources == right_sources,
        "source_files": len(right_sources),
        "provisions": compare_rows(
            _rows(left["provisions"]),
            _rows(right["provisions"]),
            left_version=left_version,
            right_version=right_version,
            prefixes=prefixes,
        ),
        "inventory": compare_rows(
            left_inventory["items"],
            right_inventory["items"],
            left_version=left_version,
            right_version=right_version,
            prefixes=prefixes,
        ),
        "coverage_fields_changed": coverage_fields,
        "coverage_complete": bool(right_coverage.get("complete")),
    }


def cmd_compare(args: argparse.Namespace) -> int:
    specs = select_specs(args.scope)
    rows = []
    for spec in specs:
        left_version = spec.original_version if args.left == "original" else spec.version
        right_version = spec.version
        rows.append(
            compare_scope(
                spec,
                left_base=args.left_base.resolve(),
                left_version=left_version,
                right_base=args.right_base.resolve(),
                right_version=right_version,
            )
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    identical = sum(
        1
        for row in rows
        if not any(
            row[part][k]
            for part in ("provisions", "inventory")
            for k in ("removed", "added", "changed")
        )
        and not row["coverage_fields_changed"]
    )
    print(f"compared {len(rows)} scopes; {identical} identical", file=sys.stderr)
    return 0


def swap_successors(selector: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return ``selector`` with each selected original replaced in place by its successor.

    Never select an original together with its successor: they share every
    citation path that did not change, so the pair would give a
    ``duplicate_release_citation`` error per path. A selector that already
    selects a successor is refused rather than half-swapped.
    """
    by_original = {spec.original_key: spec for spec in successor_specs()}
    successors = {spec.key for spec in by_original.values()}
    scopes = []
    swapped = []
    for scope in selector["scopes"]:
        key = f"{scope['jurisdiction']}/{scope['document_class']}/{scope['version']}"
        if key in successors:
            raise ValueError(f"selector already selects successor {key}")
        spec = by_original.get(key)
        if spec is None:
            scopes.append(dict(scope))
            continue
        scopes.append({**scope, "version": spec.version})
        swapped.append(key)
    return {**selector, "scopes": scopes}, swapped


def cmd_selector(args: argparse.Namespace) -> int:
    source = json.loads(args.base_selector.read_text(encoding="utf-8"))
    payload, swapped = swap_successors(source)
    if not swapped:
        raise SystemExit(f"{args.base_selector} selects none of the originals")
    payload["name"] = args.name
    payload["description"] = (
        f"Successor to {source['name']}: every scope of that cut, with {len(swapped)} "
        f"scope{'s' if len(swapped) != 1 else ''} replaced in place by "
        f"{'its' if len(swapped) == 1 else 'their'} -{REVISION} successor"
        f"{'' if len(swapped) == 1 else 's'}, rebuilt from the same retained sources with "
        "the hollow-document-root extraction fixes "
        "(docs/ingest-runs/2026-10-13-hollow-root-successors.md). "
        "This selector does not publish or activate the release."
    )
    ordered = {key: payload[key] for key in sorted(payload) if key != "scopes"}
    ordered["scopes"] = payload["scopes"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"{args.output}: {len(swapped)} of {len(source['scopes'])} scopes swapped", file=sys.stderr
    )
    return 0


def _iter_spec_rows() -> Iterator[dict[str, Any]]:
    for spec in successor_specs():
        yield {**asdict(spec), "version": spec.version}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Build successor scopes from retained bytes.")
    build.add_argument("--base", type=Path, default=Path("data/corpus"))
    build.add_argument("--source-base", type=Path)
    build.add_argument("--scope", action="append", default=[], help="Original scope or prefix.")
    build.add_argument("--workers", type=int, default=1)
    build.add_argument("--ocr-cache", type=Path)
    build.add_argument("--report", type=Path)
    build.add_argument(
        "--resume",
        action="store_true",
        help="Keep complete successors (sources re-checked); rebuild partial ones.",
    )
    build.add_argument(
        "--min-free-gb",
        type=float,
        help="Start no scope while the base's volume has less free space (decimal GB).",
    )
    build.set_defaults(func=cmd_build)
    compare = sub.add_parser(
        "compare", help="Compare successor scopes with originals or another build."
    )
    compare.add_argument("--left", choices=("original", "successor"), default="original")
    compare.add_argument("--left-base", type=Path, default=Path("data/corpus"))
    compare.add_argument("--right-base", type=Path, default=Path("data/corpus"))
    compare.add_argument("--scope", action="append", default=[])
    compare.add_argument("--output", type=Path, required=True)
    compare.set_defaults(func=cmd_compare)
    selector = sub.add_parser(
        "selector", help="Write a draft selector: a base selector with the successors swapped in."
    )
    selector.add_argument("--base-selector", type=Path, required=True)
    selector.add_argument("--name", required=True)
    selector.add_argument("--output", type=Path, required=True)
    selector.set_defaults(func=cmd_selector)
    specs = sub.add_parser("specs", help="Print the successor specs as JSON.")
    specs.set_defaults(func=lambda args: print(json.dumps(list(_iter_spec_rows()), indent=1)) or 0)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
