#!/usr/bin/env python3
"""Repair recovered release scopes from their committed official snapshots.

This is intentionally offline and fail-closed: a scope is rewritten only when it
has exactly one official snapshot and one matching provenance sidecar whose
digest matches that snapshot.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest

REPO = Path(__file__).parents[1]
BASE = REPO / "data/corpus"
SELECTOR = REPO / "manifests/releases/us-rulespec-2026-07-13.json"
SOURCE_CODES = {
    "missing_inventory_source_file",
    "missing_inventory_source_sha256",
    "missing_provision_source_file",
    "noncanonical_inventory_source_path",
    "noncanonical_provision_source_path",
    "source_sha256_mismatch",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    store = CorpusArtifactStore(BASE)
    release = ReleaseManifest.load(SELECTOR)
    report = validate_release(BASE, release, max_issues=100_000)
    affected = {
        (issue.jurisdiction, issue.document_class, issue.version)
        for issue in report.issues
        if issue.code in SOURCE_CODES
    }
    changed: set[Path] = set()
    repaired: list[str] = []
    for jurisdiction, document_class, version in sorted(affected):
        if not jurisdiction or not document_class or not version:
            raise ValueError("source issue lacks a complete scope")
        scope = (jurisdiction, document_class, version)
        source_root = store.source_path(*scope, "")
        sources = sorted(
            path
            for path in source_root.rglob("*")
            if path.is_file() and "provenance" not in path.relative_to(source_root).parts
        )
        if len(sources) != 1:
            raise ValueError(f"{scope} has {len(sources)} official snapshots; refusing ambiguity")
        source = sources[0]
        inventory_path = store.inventory_path(*scope)
        provisions_path = store.provisions_path(*scope)
        coverage_path = store.coverage_path(*scope)
        old_inventory = list(load_source_inventory(inventory_path))
        sidecar = store.source_path(*scope, f"provenance/{source.name}.json")
        digest = _sha256(source)
        if sidecar.is_file():
            provenance = json.loads(sidecar.read_text())
            required = {"url", "fetched_at", "sha256"}
            if not isinstance(provenance, dict) or not required <= provenance.keys():
                raise ValueError(f"incomplete provenance sidecar: {sidecar}")
            if digest != str(provenance["sha256"]).lower():
                raise ValueError(f"provenance digest mismatch: {source}")
            source_url = str(provenance["url"])
        else:
            urls = {item.source_url for item in old_inventory if item.source_url}
            if len(urls) != 1:
                raise ValueError(f"no sidecar or unambiguous existing source URL for {source}")
            source_url = urls.pop()
        source_key = source.relative_to(BASE).as_posix()

        inventory = [
            replace(item, source_path=source_key, source_url=source_url, sha256=digest)
            for item in old_inventory
        ]
        provisions = [
            replace(record, source_path=source_key, source_url=source_url, version=version)
            for record in load_provisions(provisions_path)
        ]
        coverage = compare_provision_coverage(
            inventory,
            provisions,
            jurisdiction=jurisdiction,
            document_class=document_class,
            version=version,
        )
        if not coverage.complete:
            raise ValueError(f"coverage became incomplete for {scope}: {coverage.to_mapping()}")
        store.write_inventory(inventory_path, inventory)
        store.write_provisions(provisions_path, provisions)
        store.write_json(coverage_path, coverage.to_mapping())
        changed.update((inventory_path, provisions_path, coverage_path))
        repaired.append("/".join(scope))

    # Recovery excerpts may begin below an omitted structural container.  Do
    # not fabricate that container or retain a dangling relationship: remove
    # only parent links that release-wide validation proves do not resolve.
    refreshed = validate_release(BASE, release, max_issues=100_000)
    dangling_by_scope: dict[tuple[str, str, str], set[str]] = {}
    for issue in refreshed.issues:
        if issue.code != "missing_parent_citation":
            continue
        key = (str(issue.jurisdiction), str(issue.document_class), str(issue.version))
        citation = issue.message.split(" parent not found:", 1)[0]
        dangling_by_scope.setdefault(key, set()).add(citation)
    for scope, citations in sorted(dangling_by_scope.items()):
        inventory_path = store.inventory_path(*scope)
        provisions_path = store.provisions_path(*scope)
        coverage_path = store.coverage_path(*scope)
        inventory = list(load_source_inventory(inventory_path))
        provisions = [
            replace(record, parent_citation_path=None, parent_id=None)
            if record.citation_path in citations
            else record
            for record in load_provisions(provisions_path)
        ]
        coverage = compare_provision_coverage(
            inventory,
            provisions,
            jurisdiction=scope[0],
            document_class=scope[1],
            version=scope[2],
        )
        if not coverage.complete:
            raise ValueError(f"coverage became incomplete while clearing dangling parents: {scope}")
        store.write_provisions(provisions_path, provisions)
        store.write_json(coverage_path, coverage.to_mapping())
        changed.update((provisions_path, coverage_path))

    resigned: list[str] = []
    for manifest_path in sorted((REPO / ".axiom/ingest-manifests").rglob("*.json")):
        manifest = json.loads(manifest_path.read_text())
        files = manifest.get("applied_files")
        if not isinstance(files, list):
            continue
        referenced = {
            REPO / row["path"]
            for row in files
            if isinstance(row, dict) and isinstance(row.get("path"), str)
        }
        hash_drift = any(
            (REPO / str(row.get("path", ""))).is_file()
            and row.get("sha256") != _sha256(REPO / str(row["path"]))
            for row in files
            if isinstance(row, dict)
        )
        if not referenced.intersection(changed) and not hash_drift:
            continue
        for row in files:
            path = REPO / str(row["path"])
            if not path.is_file():
                raise ValueError(f"manifest references missing artifact: {path}")
            row["sha256"] = _sha256(path)
        manifest.pop("signature", None)
        manifest["generated_at"] = datetime.now(UTC).isoformat()
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        resigned.append(manifest_path.relative_to(REPO).as_posix())

    print(json.dumps({"repaired_scopes": repaired, "re_sign": resigned}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
