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

Either way the check compares every inventory item, provision row, coverage
field and source file of the two scopes and fails on any other difference.
The report never repeats a ``file:`` path.

    uv run python scripts/repair_local_file_download_urls.py reextract \\
        --scope de/guidance/2026-09-14-de-kindergeld-dakg2025-sections \\
        --manifest manifests/de-kindergeld-dakg2025-sections.yaml \\
        --tag r2026-10-14-portable-download-url --report report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import _SOURCE_FORMAT_CONTENT_TYPES, extract_official_documents
from axiom_corpus.corpus.resolver import ensure_corpus_scopes
from axiom_corpus.corpus.supabase import deterministic_provision_id

REPO = Path(__file__).resolve().parents[1]
REPAIRED_FIELDS = ("download_url", "content_type")


def _is_file_url(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith("file:")


def _is_web_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))


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
        return self.base / "inventory" / self.jurisdiction / self.document_class / f"{self.version}.json"

    @property
    def provisions_path(self) -> Path:
        return (
            self.base / "provisions" / self.jurisdiction / self.document_class / f"{self.version}.jsonl"
        )

    @property
    def coverage_path(self) -> Path:
        return self.base / "coverage" / self.jurisdiction / self.document_class / f"{self.version}.json"

    def exists(self) -> bool:
        return any(
            path.exists()
            for path in (self.inventory_path, self.provisions_path, self.coverage_path)
        ) or (self.base / self.source_prefix).exists()

    def inventory(self) -> list[dict[str, Any]]:
        return list(json.loads(self.inventory_path.read_text())["items"])

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
    runtime.write_text(yaml.safe_dump({"documents": documents}, sort_keys=False, allow_unicode=True))
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
    inventory = old.inventory()
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
    store.write_json(new.inventory_path, {"items": new_inventory})
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


def _split(row: dict[str, Any], scope: Scope, *, provision: bool) -> tuple[Any, dict[str, Any]]:
    """Return the row with repaired fields and version-bearing fields normalized."""
    normalized = dict(row)
    metadata = dict(normalized.get("metadata") or {})
    repaired = {field: metadata.pop(field, None) for field in REPAIRED_FIELDS}
    normalized["metadata"] = metadata
    source_path = normalized.get("source_path")
    if isinstance(source_path, str) and source_path.startswith(scope.source_prefix):
        normalized["source_path"] = "sources/<scope>/" + source_path[len(scope.source_prefix) :]
    if provision:
        normalized["version"] = "<version>" if row.get("version") == scope.version else row.get(
            "version"
        )
        for key, path_key in (("id", "citation_path"), ("parent_id", "parent_citation_path")):
            if (
                row.get(key) is not None
                and row.get(path_key) is not None
                and row[key] == deterministic_provision_id(str(row[path_key]), scope.version)
            ):
                normalized[key] = "<versioned id>"
    return normalized, repaired


def verify(old: Scope, new: Scope) -> dict[str, Any]:
    """Compare two scopes; ``problems`` lists every difference outside the repair."""
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
    for kind, old_rows, new_rows in (
        ("inventory", old.inventory(), new.inventory()),
        ("provisions", old.provisions(), new.provisions()),
    ):
        if len(old_rows) != len(new_rows):
            problems.append(f"{kind}: {len(old_rows)} rows became {len(new_rows)}")
            continue
        provision = kind == "provisions"
        for index, (old_row, new_row) in enumerate(zip(old_rows, new_rows, strict=True)):
            old_norm, old_fields = _split(old_row, old, provision=provision)
            new_norm, new_fields = _split(new_row, new, provision=provision)
            where = f"{kind}[{index}] {old_row.get('citation_path')}"
            if old_norm != new_norm:
                keys = sorted(
                    key
                    for key in set(old_norm) | set(new_norm)
                    if old_norm.get(key) != new_norm.get(key)
                )
                if keys == ["metadata"]:
                    keys = sorted(
                        f"metadata.{key}"
                        for key in set(old_norm["metadata"]) | set(new_norm["metadata"])
                        if old_norm["metadata"].get(key) != new_norm["metadata"].get(key)
                    )
                problems.append(f"{where}: {', '.join(keys)} changed")
            if _is_file_url(old_fields["download_url"]):
                repaired_rows += 1
                if not _is_web_url(new_fields["download_url"]):
                    problems.append(f"{where}: download_url is not a web URL after repair")
                if old_fields["content_type"] not in (None, new_fields["content_type"]):
                    problems.append(f"{where}: content_type changed from a recorded value")
                if new_fields["content_type"] is None:
                    problems.append(f"{where}: content_type is still null")
                urls[str(new_row.get("source_url"))] = str(new_fields["download_url"])
                content_types[str(new_fields["content_type"])] = (
                    content_types.get(str(new_fields["content_type"]), 0) + 1
                )
            elif old_fields != new_fields:
                problems.append(f"{where}: {', '.join(REPAIRED_FIELDS)} changed on a web-fetched row")
            if any(_is_file_url(value) for value in new_fields.values()):
                problems.append(f"{where}: still records a file: URL")
    old_coverage, new_coverage = old.coverage(), new.coverage()
    for coverage in (old_coverage, new_coverage):
        coverage.pop("version", None)
    if old_coverage != new_coverage:
        problems.append("coverage differs")
    return {
        "scope": old.label,
        "repaired_scope": new.label,
        "source_files": dict(sorted(new_sources.items())),
        "inventory_rows": len(new.inventory()),
        "provision_rows": len(new.provisions()),
        "repaired_rows": repaired_rows,
        "download_urls_by_source_url": dict(sorted(urls.items())),
        "content_types": dict(sorted(content_types.items())),
        "coverage_complete": new_coverage.get("complete"),
        "problems": problems,
    }


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
    old = Scope(base, jurisdiction, document_class, version)
    new = Scope(base, jurisdiction, document_class, f"{version}-{args.tag}")
    ensure_corpus_scopes([(jurisdiction, document_class, version)], repo=REPO)
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
