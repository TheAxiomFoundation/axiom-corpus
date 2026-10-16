#!/usr/bin/env python3
"""Re-version a locked scope whose rows record a file: download URL.

Before the extractor fix, a manifest ``local_path`` extraction wrote the
extracting machine's path (``file:///Users/<name>/...``) as every row's
``metadata.download_url`` and left ``content_type`` null; a few recovery
scripts did the same. This script writes a successor scope,
``<version>-<tag>``, from the locked scope's own bytes, then proves that the
successor differs from it only in those two fields and the version.

Two modes:

``reextract`` (scopes produced by ``extract-official-documents``) runs the fixed
extractor on the committed manifest's entries for the scope's documents, each
with ``local_path`` pointing at the scope's locked source file and with the
locked ``source_as_of`` and ``expression_date``. A document the original run
fetched over the network keeps its recorded ``download_url``, and each
document's manifest metadata is recovered from its locked root row (runtime
manifests sometimes carried keys the committed manifest lacks). The extractor
then records each retained copy's official URL and media type itself.

``rewrite`` (scopes no committed manifest reproduces, such as the July
recovery batch) copies the source files byte for byte and replaces each
``file:`` download URL with the URL the other artifact records for the same
citation, else the row's own ``source_url``; a null ``content_type`` becomes the
other artifact's, else the source format's media type.

Before writing anything it checks that the locked scope's files in this
checkout match its lock exactly (fetch never replaces an edited file). Then
``verify`` builds, from each locked row, the exact row the successor may hold
(version, version-bearing ids and source paths mapped; on repaired rows a web
``download_url`` and a media type), and fails on any other difference in any
inventory item, provision row, coverage field or source file. The report never
repeats a ``file:`` path.

    uv run python scripts/repair_local_file_download_urls.py reextract \\
        --scope de/guidance/2026-09-14-de-kindergeld-dakg2025-sections \\
        --manifest manifests/de-kindergeld-dakg2025-sections.yaml \\
        --tag r2026-10-14-portable-download-url --report report.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.corpus_locks import load_locks
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import _SOURCE_FORMAT_CONTENT_TYPES, extract_official_documents
from axiom_corpus.corpus.ingest_manifests import (
    LocalFileUrlScanError,
    local_file_url_fields,
    redact_file_urls,
)
from axiom_corpus.corpus.resolver import ensure_corpus_scopes
from axiom_corpus.corpus.supabase import deterministic_provision_id

REPO = Path(__file__).resolve().parents[1]


def _is_file_url(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith("file:")


def _is_web_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))


# RFC 9110 section 8.3.1: type "/" subtype *( OWS ";" OWS parameter ), where a
# parameter is token "=" ( token / quoted-string ).
_TOKEN = r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+"
_QUOTED = r'"(?:[\t !#-\[\]-~\x80-\xff]|\\[\t -~\x80-\xff])*"'
_MEDIA_TYPE = re.compile(rf"{_TOKEN}/{_TOKEN}(?:[ \t]*;[ \t]*{_TOKEN}=(?:{_TOKEN}|{_QUOTED}))*")


def _is_media_type(value: object) -> bool:
    """A well-formed media type that names no file: URL, even in a parameter."""
    return (
        isinstance(value, str)
        and _MEDIA_TYPE.fullmatch(value) is not None
        and "file:" not in value.lower()
    )


def _essence(content_type: str) -> str:
    """The media type without parameters, as the report shows it."""
    return content_type.split(";", 1)[0].strip().lower()


def _redact_report(value: Any) -> Any:
    """Every string in the report, keys included, with file: URLs replaced."""
    if isinstance(value, dict):
        return {_redact_report(key): _redact_report(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact_report(child) for child in value]
    return redact_file_urls(value) if isinstance(value, str) else value


def _parse_scope(text: str) -> tuple[str, str, str]:
    parts = text.strip("/").split("/")
    if len(parts) != 3 or not all(parts):
        raise SystemExit(f"--scope must be <jurisdiction>/<document_class>/<version>: {text}")
    return parts[0], parts[1], parts[2]


class Scope:
    """Raw artifacts of one scope under a corpus base."""

    def __init__(self, base: Path, jurisdiction: str, document_class: str, version: str):
        self.base = base
        self.jurisdiction = jurisdiction
        self.document_class = document_class
        self.version = version

    @property
    def label(self) -> str:
        return f"{self.jurisdiction}/{self.document_class}/{self.version}"

    @property
    def source_prefix(self) -> str:
        return f"sources/{self.jurisdiction}/{self.document_class}/{self.version}/"

    @property
    def inventory_path(self) -> Path:
        return (
            self.base
            / "inventory"
            / self.jurisdiction
            / self.document_class
            / f"{self.version}.json"
        )

    @property
    def provisions_path(self) -> Path:
        return (
            self.base
            / "provisions"
            / self.jurisdiction
            / self.document_class
            / f"{self.version}.jsonl"
        )

    @property
    def coverage_path(self) -> Path:
        return (
            self.base
            / "coverage"
            / self.jurisdiction
            / self.document_class
            / f"{self.version}.json"
        )

    def exists(self) -> bool:
        return (
            any(
                path.exists()
                for path in (self.inventory_path, self.provisions_path, self.coverage_path)
            )
            or (self.base / self.source_prefix).exists()
        )

    def inventory_document(self) -> dict[str, Any]:
        document = json.loads(self.inventory_path.read_text())
        if not isinstance(document, dict) or not isinstance(document.get("items"), list):
            raise SystemExit(f"{self.label}: inventory is not a mapping with an items list")
        return document

    def inventory(self) -> list[dict[str, Any]]:
        return list(self.inventory_document()["items"])

    def provisions(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.provisions_path.read_text().splitlines() if line]

    def coverage(self) -> dict[str, Any]:
        return dict(json.loads(self.coverage_path.read_text()))

    def source_hashes(self) -> dict[str, str]:
        root = self.base / self.source_prefix
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }


def _root_rows(old: Scope) -> dict[str, dict[str, Any]]:
    roots: dict[str, dict[str, Any]] = {}
    for row in old.provisions():
        if row.get("kind") == "document" and row.get("level") == 1:
            source_id = str(row["source_id"])
            if source_id in roots:
                raise SystemExit(f"{old.label}: two document roots for source {source_id}")
            roots[source_id] = row
    if not roots:
        raise SystemExit(f"{old.label}: no document root rows; use rewrite")
    return roots


# Keys extract-official-documents adds to a document root's manifest metadata.
_EXTRACTOR_ROOT_METADATA = ("title", "content_type", "download_url", "block_count")


def _manifest_metadata(root: dict[str, Any]) -> dict[str, Any]:
    """Recover the metadata the original run's manifest gave a document.

    A root row records ``{"kind": "document", **manifest_metadata, title,
    content_type, download_url, block_count}``, so dropping the extractor's
    keys gives back the manifest's metadata exactly (a manifest ``kind`` would
    have overridden ``"document"`` and is kept). Runtime manifests sometimes
    carried keys the committed manifest lacks, such as the retained copy's
    sha256.
    """
    metadata = {
        key: value
        for key, value in (root.get("metadata") or {}).items()
        if key not in _EXTRACTOR_ROOT_METADATA
    }
    if metadata.get("kind") == "document":
        del metadata["kind"]
    return metadata


def reextract(old: Scope, new: Scope, manifest: Path, work_dir: Path) -> None:
    """Run the fixed extractor on the scope's locked source files."""
    roots = _root_rows(old)
    data = yaml.safe_load(manifest.read_text())
    entries = {
        str(entry["source_id"]): entry
        for entry in data.get("documents") or []
        if isinstance(entry, dict) and str(entry.get("source_id")) in roots
    }
    missing = sorted(set(roots) - set(entries))
    if missing:
        raise SystemExit(f"{manifest} has no entry for {old.label} sources {missing}")
    documents = []
    for source_id, root in roots.items():  # the locked scope's document order
        entry = dict(entries[source_id])
        entry.pop("local_path", None)
        source_path = str(root["source_path"])
        if not source_path.startswith(old.source_prefix):
            raise SystemExit(f"{old.label}: {source_id} source_path is outside the scope")
        entry["local_path"] = str((old.base / source_path).resolve())
        entry["source_as_of"] = root["source_as_of"]
        entry["expression_date"] = root["expression_date"]
        entry["metadata"] = _manifest_metadata(root)
        recorded = (root.get("metadata") or {}).get("download_url")
        if recorded and not _is_file_url(recorded):
            entry["download_url"] = recorded  # fetched over the network originally
        documents.append(entry)
    runtime = work_dir / f"{new.version}.runtime-manifest.yaml"
    runtime.write_text(
        yaml.safe_dump({"documents": documents}, sort_keys=False, allow_unicode=True)
    )
    extract_official_documents(
        CorpusArtifactStore(new.base), manifest_path=runtime, version=new.version
    )


def _repaired_metadata(
    metadata: dict[str, Any] | None,
    *,
    sibling: dict[str, Any] | None,
    source_url: object,
    source_format: object,
    where: str,
) -> dict[str, Any] | None:
    if metadata is None or not _is_file_url(metadata.get("download_url")):
        return metadata
    repaired = dict(metadata)
    sibling_metadata = (sibling or {}).get("metadata") or {}
    if _is_web_url(sibling_metadata.get("download_url")):
        repaired["download_url"] = sibling_metadata["download_url"]
    elif _is_web_url(source_url):
        repaired["download_url"] = source_url
    else:
        raise SystemExit(f"{where}: no web URL to replace the file: download_url")
    if repaired.get("content_type") is None:
        repaired["content_type"] = sibling_metadata.get("content_type") or (
            _SOURCE_FORMAT_CONTENT_TYPES.get(str(source_format).lower())
        )
    return repaired


def _moved_source_path(value: object, old: Scope, new: Scope) -> object:
    if value is None:
        return None
    text = str(value)
    if not text.startswith(old.source_prefix):
        raise SystemExit(f"{old.label}: source_path outside the scope: {text}")
    return new.source_prefix + text[len(old.source_prefix) :]


def _moved_id(value: object, citation_path: object, old: Scope, new: Scope) -> object:
    if value is None or citation_path is None:
        return value
    if value == deterministic_provision_id(str(citation_path), old.version):
        return deterministic_provision_id(str(citation_path), new.version)
    return value  # version-free ids carry over unchanged


class _Cited:
    def __init__(self, citation_path: str):
        self.citation_path = citation_path


def rewrite(old: Scope, new: Scope) -> None:
    """Copy the scope with each file: download URL replaced.

    Rows stay raw JSON mappings, so every field the locked scope recorded is
    written back exactly as it was, in the store's canonical encoding.
    """
    store = CorpusArtifactStore(new.base)
    source_root = old.base / old.source_prefix
    for relative in old.source_hashes():
        store.write_bytes(
            new.base / new.source_prefix / relative, (source_root / relative).read_bytes()
        )
    envelope = old.inventory_document()  # keys besides "items" are written back as they are
    inventory = list(envelope.pop("items"))
    provisions = old.provisions()
    inventory_by_path = {item["citation_path"]: item for item in inventory}
    provisions_by_path = {row["citation_path"]: row for row in provisions}
    new_inventory = []
    for item in inventory:
        moved = dict(item)
        if "source_path" in item:
            moved["source_path"] = _moved_source_path(item["source_path"], old, new)
        if "metadata" in item:
            moved["metadata"] = _repaired_metadata(
                item["metadata"],
                sibling=provisions_by_path.get(item["citation_path"]),
                source_url=item.get("source_url"),
                source_format=item.get("source_format"),
                where=f"{old.label} inventory {item['citation_path']}",
            )
        new_inventory.append(moved)
    new_provisions = []
    for row in provisions:
        moved = dict(row)
        moved["version"] = new.version
        if "source_path" in row:
            moved["source_path"] = _moved_source_path(row["source_path"], old, new)
        for key, path_key in (("id", "citation_path"), ("parent_id", "parent_citation_path")):
            if key in row:
                moved[key] = _moved_id(row[key], row.get(path_key), old, new)
        if "metadata" in row:
            moved["metadata"] = _repaired_metadata(
                row["metadata"],
                sibling=inventory_by_path.get(row["citation_path"]),
                source_url=row.get("source_url"),
                source_format=row.get("source_format"),
                where=f"{old.label} provision {row['citation_path']}",
            )
        new_provisions.append(moved)
    store.write_json(new.inventory_path, {**envelope, "items": new_inventory})
    store.write_text(
        new.provisions_path,
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in new_provisions),
    )
    coverage = compare_provision_coverage(
        tuple(_Cited(item["citation_path"]) for item in new_inventory),
        tuple(_Cited(row["citation_path"]) for row in new_provisions),
        jurisdiction=new.jurisdiction,
        document_class=new.document_class,
        version=new.version,
    )
    store.write_json(new.coverage_path, coverage.to_mapping())


def _redacted(value: object) -> str:
    return "<file: URL>" if _is_file_url(value) else str(value)


def _differences(expected: Any, actual: Any, path: str = "") -> list[str]:
    """Dotted paths at which ``actual`` differs from ``expected``, keys and types included."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        found = []
        for key in sorted(set(expected) | set(actual), key=str):
            child = f"{path}.{key}" if path else str(key)
            if key not in expected:
                found.append(f"{child} added")
            elif key not in actual:
                found.append(f"{child} removed")
            else:
                found.extend(_differences(expected[key], actual[key], child))
        return found
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{path or '<row>'} length changed"]
        found = []
        for index, (want, have) in enumerate(zip(expected, actual, strict=True)):
            found.extend(_differences(want, have, f"{path}[{index}]"))
        return found
    if type(expected) is not type(actual) or expected != actual:  # 1, 1.0 and True differ
        return [f"{path or '<row>'} changed"]
    return []


def _expected_row(
    old_row: dict[str, Any],
    new_row: dict[str, Any],
    old: Scope,
    new: Scope,
    *,
    provision: bool,
) -> tuple[dict[str, Any], bool]:
    """The successor row the repair may write for ``old_row``.

    Fields that name the scope map to the successor: a provision's version,
    a version-bearing id or parent_id, and a source path inside the scope. On
    a row whose ``download_url`` was a ``file:`` URL, ``download_url`` and a
    null ``content_type`` take the successor's values, which ``verify`` checks
    on their own. Every other key and value must be the locked row's exactly.
    """
    expected = copy.deepcopy(old_row)
    if provision and old_row.get("version") == old.version:
        expected["version"] = new.version
    for key, path_key in (("id", "citation_path"), ("parent_id", "parent_citation_path")):
        citation = old_row.get(path_key)
        if (
            key in old_row
            and citation is not None
            and old_row[key] == deterministic_provision_id(str(citation), old.version)
        ):
            expected[key] = deterministic_provision_id(str(citation), new.version)
    source_path = old_row.get("source_path")
    if isinstance(source_path, str) and source_path.startswith(old.source_prefix):
        expected["source_path"] = new.source_prefix + source_path[len(old.source_prefix) :]
    old_metadata = old_row.get("metadata")
    repaired = isinstance(old_metadata, dict) and _is_file_url(old_metadata.get("download_url"))
    if repaired:
        assert isinstance(old_metadata, dict)
        new_metadata = new_row.get("metadata")
        new_metadata = new_metadata if isinstance(new_metadata, dict) else {}
        metadata = dict(old_metadata)
        metadata["download_url"] = new_metadata.get("download_url")
        if old_metadata.get("content_type") is None:
            metadata["content_type"] = new_metadata.get("content_type")
        expected["metadata"] = metadata
    return expected, repaired


def verify(old: Scope, new: Scope) -> dict[str, Any]:
    """Compare two scopes; ``problems`` lists every difference outside the repair.

    Each successor row must equal the row ``_expected_row`` builds from the
    locked row at the same position, key for key; every repaired row must now
    record a web URL and a media type; the inventory's other top-level keys
    must be unchanged; no URL field anywhere in the successor's bytes may hold
    a ``file:`` URL; the coverage report must equal the locked one with its
    version mapped; the source files must be the same names and bytes. Lists
    compare element by element and types count (``1``, ``1.0`` and ``true``
    differ). No ``file:`` value reaches the report.
    """
    problems: list[str] = []
    old_sources, new_sources = old.source_hashes(), new.source_hashes()
    if old_sources != new_sources:
        problems.append(
            "source files differ: "
            + ", ".join(
                sorted(
                    name
                    for name in set(old_sources) | set(new_sources)
                    if old_sources.get(name) != new_sources.get(name)
                )
            )
        )
    repaired_rows = 0
    urls: dict[str, str] = {}
    content_types: dict[str, int] = {}
    new_inventory, new_provisions = new.inventory(), new.provisions()
    for kind, old_rows, new_rows in (
        ("inventory", old.inventory(), new_inventory),
        ("provisions", old.provisions(), new_provisions),
    ):
        if len(old_rows) != len(new_rows):
            problems.append(f"{kind}: {len(old_rows)} rows became {len(new_rows)}")
            continue
        for index, (old_row, new_row) in enumerate(zip(old_rows, new_rows, strict=True)):
            where = f"{kind}[{index}] {old_row.get('citation_path')}"
            if not isinstance(old_row, dict) or not isinstance(new_row, dict):
                if old_row != new_row:
                    problems.append(f"{where}: row changed")
                continue
            expected, repaired = _expected_row(
                old_row, new_row, old, new, provision=kind == "provisions"
            )
            differences = _differences(expected, new_row)
            if differences:
                problems.append(f"{where}: {', '.join(differences)}")
            if not repaired:
                continue
            repaired_rows += 1
            metadata = new_row.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            download_url, content_type = metadata.get("download_url"), metadata.get("content_type")
            if not _is_web_url(download_url):
                problems.append(f"{where}: download_url is not a web URL after repair")
            if not _is_media_type(content_type):
                problems.append(f"{where}: content_type is not a media type after repair")
            urls[_redacted(new_row.get("source_url"))] = (
                str(download_url) if _is_web_url(download_url) else "<not a web URL>"
            )
            shown = _essence(content_type) if _is_media_type(content_type) else "<not a media type>"
            content_types[shown] = content_types.get(shown, 0) + 1
    old_envelope, new_envelope = old.inventory_document(), new.inventory_document()
    old_envelope.pop("items")
    new_envelope.pop("items")
    envelope_differences = _differences(old_envelope, new_envelope)
    if envelope_differences:
        problems.append(f"inventory envelope: {', '.join(envelope_differences)}")
    for path in (new.inventory_path, new.provisions_path):
        try:
            leaks = local_file_url_fields(path.name, path.read_bytes())
        except LocalFileUrlScanError as exc:
            problems.append(f"{path.name}: {exc}")
            continue
        if leaks:
            problems.append(f"{path.name}: {len(leaks)} URL field(s) still record a file: URL")
    old_coverage, new_coverage = old.coverage(), new.coverage()
    expected_coverage = copy.deepcopy(old_coverage)
    if old_coverage.get("version") == old.version:
        expected_coverage["version"] = new.version
    coverage_differences = _differences(expected_coverage, new_coverage)
    if coverage_differences:
        problems.append(f"coverage: {', '.join(coverage_differences)}")
    return _redact_report(
        {
            "scope": old.label,
            "repaired_scope": new.label,
            "source_files": dict(sorted(new_sources.items())),
            "inventory_rows": len(new_inventory),
            "provision_rows": len(new_provisions),
            "repaired_rows": repaired_rows,
            "download_urls_by_source_url": dict(sorted(urls.items())),
            "content_types": dict(sorted(content_types.items())),
            "coverage_complete": new_coverage.get("complete"),
            "problems": problems,
        }
    )


def lock_mismatches(scope: Scope, repo: Path) -> list[str]:
    """Every way the scope's files differ from its lock: absent, changed or unlocked.

    The repair reads the locked scope from the worktree, where fetch leaves a
    present file in place even if it was edited; this anchors both the repair
    and its comparison to the signed bytes.
    """
    lock = load_locks(repo).locks.get((scope.jurisdiction, scope.document_class, scope.version))
    if lock is None:
        return [f"{scope.label} has no lock"]
    problems = []
    locked = {entry.path: entry for entry in lock.files}
    for rel, entry in sorted(locked.items()):
        path = repo / rel
        if not path.is_file():
            problems.append(f"{rel} is absent")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != entry.sha256:
            problems.append(f"{rel} differs from its lock")
    on_disk = [scope.inventory_path, scope.provisions_path, scope.coverage_path]
    source_root = scope.base / scope.source_prefix
    if source_root.is_dir():
        on_disk.extend(path for path in source_root.rglob("*") if path.is_file())
    for path in on_disk:
        if path.is_file():
            rel = path.resolve().relative_to(repo.resolve()).as_posix()
            if rel not in locked:
                problems.append(f"{rel} is not in the lock")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("mode", choices=("reextract", "rewrite", "verify"))
    parser.add_argument("--scope", required=True, help="<jurisdiction>/<document_class>/<version>")
    parser.add_argument("--tag", required=True, help="Suffix for the successor version")
    parser.add_argument("--manifest", type=Path, help="Committed manifest (reextract)")
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--report", type=Path, help="Write the verification report here")
    args = parser.parse_args(argv)

    jurisdiction, document_class, version = _parse_scope(args.scope)
    base = args.base.resolve()
    if base != (REPO / "data" / "corpus").resolve():
        raise SystemExit(f"--base must be this checkout's data/corpus: {base}")
    old = Scope(base, jurisdiction, document_class, version)
    new = Scope(base, jurisdiction, document_class, f"{version}-{args.tag}")
    ensure_corpus_scopes([(jurisdiction, document_class, version)], repo=REPO)
    unlocked = lock_mismatches(old, REPO)
    if unlocked:
        raise SystemExit(f"{old.label} does not match its lock: " + "; ".join(unlocked[:5]))
    if args.mode != "verify":
        if new.exists():
            raise SystemExit(f"{new.label} already exists under {base}")
        if args.mode == "reextract":
            if args.manifest is None:
                raise SystemExit("reextract needs --manifest")
            with tempfile.TemporaryDirectory() as work_dir:
                reextract(old, new, args.manifest, Path(work_dir))
        else:
            rewrite(old, new)
    report = verify(old, new)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for problem in report["problems"]:
        print(f"{old.label}: {problem}", file=sys.stderr)
    print(
        f"{new.label}: {report['repaired_rows']} repaired row(s), "
        f"{len(report['problems'])} problem(s)",
        file=sys.stderr,
    )
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
