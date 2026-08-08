#!/usr/bin/env python3
"""Build the NY TANF compatibility scope from retained signed artifacts.

The signed June 5 scope has four compatibility aliases but an incomplete
inventory and no retained source directory.  This adapter combines those four
aliases with the complete August 3 official-source recovery while preserving
an auditable, byte-exact link from each alias to its source PDF pages.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from base64 import b64decode
from binascii import Error as BinasciiError
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.ingest_manifests import (
    INGEST_MANIFEST_KEY_ID,
    INGEST_MANIFEST_SCHEMA_VERSION,
    INGEST_MANIFEST_SIGNATURE_ALGORITHM,
    sha256_file,
)
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id

JURISDICTION = "us-ny"
DOCUMENT_CLASS = "policy"
CURRENT_VERSION = "2026-08-03-ny-tanf-official-source-recovery"
LEGACY_VERSION = "2026-06-05-ny-tanf"
SOURCE_DOCUMENT_NAME = "ny-otda-tanf-state-plan-2024-2026.pdf"
ALIASES = (
    "us-ny/policy/otda/tanf-state-plan-2024-2026/financial-eligibility-and-income-disregards",
    "us-ny/policy/otda/tanf-state-plan-2024-2026/shelter-allowance-with-children",
    "us-ny/policy/otda/tanf-state-plan-2024-2026/shelter-allowance-without-children",
    "us-ny/policy/otda/tanf-state-plan-2024-2026/standard-of-need-and-monthly-grant",
)
ALIAS_PAGE_NUMBERS = {
    ALIASES[0]: (10, 11, 12),
    ALIASES[1]: (78, 79, 80),
    ALIASES[2]: (81, 82),
    ALIASES[3]: (76, 77, 78),
}
PAGE_CITATION_PREFIX = "us-ny/policy/otda/tanf-state-plan-2024-2026/page-"
FULL_GIT_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _manifest_path(repo: Path, version: str) -> Path:
    return (
        repo
        / ".axiom"
        / "ingest-manifests"
        / JURISDICTION
        / DOCUMENT_CLASS
        / f"{version}.json"
    )


def assert_manifest_attested_file(
    *,
    repo: Path,
    relative: Path,
    version: str,
) -> dict[str, Any]:
    """Require one structurally signed manifest entry matching local bytes.

    This validates immutable input identity and byte attestation.  It does not
    apply authorizing-manifest ancestry policy: ``guard-ingested`` owns that
    check for changed outputs, and a trusted historical input manifest may name
    a signer-side commit that is not an ancestor of the current branch.
    """
    manifest_path = _manifest_path(repo, version)
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError(f"input manifest is not a regular file: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"input manifest is not valid JSON: {manifest_path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"input manifest must be an object: {manifest_path}")

    expected_identity = {
        "schema_version": INGEST_MANIFEST_SCHEMA_VERSION,
        "jurisdiction": JURISDICTION,
        "document_class": DOCUMENT_CLASS,
        "version": version,
    }
    for field, expected in expected_identity.items():
        if payload.get(field) != expected:
            raise ValueError(
                f"input manifest {field} mismatch for {manifest_path}: "
                f"{payload.get(field)!r} != {expected!r}"
            )

    git_metadata = payload.get("axiom_corpus_git")
    if not isinstance(git_metadata, dict):
        raise ValueError(f"input manifest lacks axiom_corpus_git: {manifest_path}")
    if git_metadata.get("root") != "." or git_metadata.get("dirty_tracked") is not False:
        raise ValueError(f"input manifest has non-canonical git state: {manifest_path}")
    signer_commit = git_metadata.get("commit")
    if not isinstance(signer_commit, str) or not FULL_GIT_COMMIT_PATTERN.fullmatch(
        signer_commit
    ):
        raise ValueError(f"input manifest has an invalid signer commit: {manifest_path}")

    signature = payload.get("signature")
    if not isinstance(signature, dict):
        raise ValueError(f"input manifest is not structurally signed: {manifest_path}")
    if signature.get("algorithm") != INGEST_MANIFEST_SIGNATURE_ALGORITHM:
        raise ValueError(f"input manifest signature algorithm is invalid: {manifest_path}")
    if signature.get("key_id") != INGEST_MANIFEST_KEY_ID:
        raise ValueError(f"input manifest signature key id is invalid: {manifest_path}")
    signature_value = signature.get("value")
    if not isinstance(signature_value, str) or not signature_value:
        raise ValueError(f"input manifest signature value is missing: {manifest_path}")
    try:
        signature_bytes = b64decode(signature_value.encode("ascii"), validate=True)
    except (BinasciiError, UnicodeEncodeError) as error:
        raise ValueError(
            f"input manifest signature encoding is invalid: {manifest_path}"
        ) from error
    if len(signature_bytes) != 64:
        raise ValueError(f"input manifest signature length is invalid: {manifest_path}")

    raw_entries = payload.get("applied_files")
    if not isinstance(raw_entries, list):
        raise ValueError(f"input manifest applied_files must be a list: {manifest_path}")
    entries_by_path: dict[str, dict[str, Any]] = {}
    for entry in raw_entries:
        if not isinstance(entry, dict):
            raise ValueError(f"input manifest has a malformed applied file: {manifest_path}")
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError(f"input manifest applied file lacks a path: {manifest_path}")
        if raw_path in entries_by_path:
            raise ValueError(
                f"input manifest repeats applied file {raw_path}: {manifest_path}"
            )
        entries_by_path[raw_path] = entry

    relative_text = relative.as_posix()
    entry = entries_by_path.get(relative_text)
    if entry is None or entry.get("deleted") is True:
        raise ValueError(
            f"input artifact is absent from signed manifest: {relative_text}"
        )
    expected_sha256 = entry.get("sha256")
    if not isinstance(expected_sha256, str) or not SHA256_PATTERN.fullmatch(
        expected_sha256
    ):
        raise ValueError(
            f"input manifest has invalid sha256 for {relative_text}: {expected_sha256!r}"
        )
    artifact_path = repo / relative
    if not artifact_path.is_file() or artifact_path.is_symlink():
        raise ValueError(f"input artifact is not a regular file: {artifact_path}")
    actual_sha256 = sha256_file(artifact_path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"signed artifact hash mismatch for {relative_text}: "
            f"{expected_sha256} != {actual_sha256}"
        )
    print(
        "INPUT_MANIFEST_ATTESTATION",
        relative_text,
        actual_sha256,
        manifest_path.relative_to(repo).as_posix(),
    )
    return payload


def _rewritten_source_path(value: str | None, *, target_version: str) -> str | None:
    if value is None:
        return None
    source_prefix = f"sources/{JURISDICTION}/{DOCUMENT_CLASS}/{CURRENT_VERSION}/"
    if not value.startswith(source_prefix):
        raise ValueError(f"unexpected current source path: {value}")
    relative = value[len(source_prefix) :]
    return (
        f"sources/{JURISDICTION}/{DOCUMENT_CLASS}/{target_version}/"
        f"{CURRENT_VERSION}/{relative}"
    )


def _portable_metadata(
    metadata: dict[str, Any] | None,
    *,
    alias_from: str | None = None,
) -> dict[str, Any] | None:
    if metadata is None:
        return None
    portable = dict(metadata)
    download_url = portable.get("download_url")
    if isinstance(download_url, str) and download_url.startswith("file://"):
        portable.pop("download_url")
    if alias_from is not None:
        portable.update(
            {
                "compatibility_alias": True,
                "compatibility_alias_from_signed_scope": alias_from,
                "compatibility_source_scope": CURRENT_VERSION,
            }
        )
    return portable or None


def _rewritten_record(
    record: ProvisionRecord,
    *,
    target_version: str,
    alias_from: str | None = None,
) -> ProvisionRecord:
    if alias_from is None:
        source_path = _rewritten_source_path(
            record.source_path,
            target_version=target_version,
        )
    else:
        source_path = (
            f"sources/{JURISDICTION}/{DOCUMENT_CLASS}/{target_version}/"
            f"{CURRENT_VERSION}/official-documents/{SOURCE_DOCUMENT_NAME}"
        )
    return replace(
        record,
        version=target_version,
        id=deterministic_provision_id(record.citation_path, target_version),
        parent_id=(
            deterministic_provision_id(record.parent_citation_path, target_version)
            if record.parent_citation_path
            else None
        ),
        source_path=source_path,
        metadata=_portable_metadata(record.metadata, alias_from=alias_from),
    )


def _assert_alias_page_equivalence(
    *,
    old_by_citation: dict[str, ProvisionRecord],
    current_by_citation: dict[str, ProvisionRecord],
) -> None:
    for alias, page_numbers in ALIAS_PAGE_NUMBERS.items():
        page_bodies: list[str] = []
        for page_number in page_numbers:
            citation = f"{PAGE_CITATION_PREFIX}{page_number}"
            page = current_by_citation.get(citation)
            if page is None:
                raise ValueError(
                    f"signed current recovery is missing alias source page: {citation}"
                )
            if not isinstance(page.body, str):
                raise ValueError(f"alias source page is bodyless: {citation}")
            page_bodies.append(page.body)
        expected_body = "\n\n".join(page_bodies)
        if old_by_citation[alias].body != expected_body:
            raise ValueError(
                "compatibility alias is not an exact current-page concatenation: "
                f"{alias} != {page_numbers}"
            )
        print("ALIAS_CURRENT_PAGE_EQUIVALENCE", alias, list(page_numbers))


def _remove_artifact(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def build_ny_tanf_compatibility_scope(
    *,
    repo: Path,
    target_version: str,
    verify_only: bool = False,
) -> tuple[Path, ...]:
    """Create the NY TANF successor or verify its signed-input proofs."""
    repo = repo.resolve()
    base = repo / "data" / "corpus"
    store = CorpusArtifactStore(base)
    current_inventory_path = store.inventory_path(
        JURISDICTION,
        DOCUMENT_CLASS,
        CURRENT_VERSION,
    )
    current_provisions_path = store.provisions_path(
        JURISDICTION,
        DOCUMENT_CLASS,
        CURRENT_VERSION,
    )
    old_provisions_path = store.provisions_path(
        JURISDICTION,
        DOCUMENT_CLASS,
        LEGACY_VERSION,
    )
    current_source_relative = Path(
        f"data/corpus/sources/{JURISDICTION}/{DOCUMENT_CLASS}/{CURRENT_VERSION}/"
        f"official-documents/{SOURCE_DOCUMENT_NAME}"
    )
    current_source_dir = (
        base / "sources" / JURISDICTION / DOCUMENT_CLASS / CURRENT_VERSION
    )
    if not current_source_dir.is_dir() or current_source_dir.is_symlink():
        raise ValueError(f"input source directory is not regular: {current_source_dir}")
    if any(path.is_symlink() for path in current_source_dir.rglob("*")):
        raise ValueError(f"input source directory contains a symlink: {current_source_dir}")

    attested_inputs = (
        (current_inventory_path.relative_to(repo), CURRENT_VERSION),
        (current_provisions_path.relative_to(repo), CURRENT_VERSION),
        (old_provisions_path.relative_to(repo), LEGACY_VERSION),
        (current_source_relative, CURRENT_VERSION),
    )
    for relative, version in attested_inputs:
        assert_manifest_attested_file(repo=repo, relative=relative, version=version)

    current_inventory = tuple(load_source_inventory(current_inventory_path))
    current_provisions = tuple(load_provisions(current_provisions_path))
    old_provisions = tuple(load_provisions(old_provisions_path))
    current_coverage = compare_provision_coverage(
        current_inventory,
        current_provisions,
        JURISDICTION,
        DOCUMENT_CLASS,
        CURRENT_VERSION,
    )
    if not current_coverage.complete:
        raise ValueError(
            f"signed current recovery coverage is incomplete: {current_coverage.to_mapping()}"
        )

    current_source_path = current_source_relative.relative_to(Path("data/corpus")).as_posix()
    current_source_sha256 = sha256_file(repo / current_source_relative)
    for item in current_inventory:
        if item.source_path != current_source_path or item.sha256 != current_source_sha256:
            raise ValueError(
                "signed current inventory does not consistently identify the attested PDF: "
                f"{item.citation_path}"
            )
    print(
        "CURRENT_SCOPE_COVERAGE",
        json.dumps(current_coverage.to_mapping(), sort_keys=True),
    )

    current_by_citation = {row.citation_path: row for row in current_provisions}
    old_by_citation = {row.citation_path: row for row in old_provisions}
    if len(current_by_citation) != len(current_provisions):
        raise ValueError("signed current recovery contains duplicate citations")
    if len(old_by_citation) != len(old_provisions):
        raise ValueError("signed legacy scope contains duplicate citations")
    missing_current_from_legacy = sorted(set(current_by_citation) - set(old_by_citation))
    legacy_only = set(old_by_citation) - set(current_by_citation)
    if missing_current_from_legacy or legacy_only != set(ALIASES):
        raise ValueError(
            "signed legacy/current citation delta is not exactly the four aliases; "
            f"missing_current_from_legacy={missing_current_from_legacy}, "
            f"legacy_only={sorted(legacy_only)}"
        )
    _assert_alias_page_equivalence(
        old_by_citation=old_by_citation,
        current_by_citation=current_by_citation,
    )
    if verify_only:
        return ()

    target_source_dir = base / "sources" / JURISDICTION / DOCUMENT_CLASS / target_version
    target_inventory_path = store.inventory_path(
        JURISDICTION,
        DOCUMENT_CLASS,
        target_version,
    )
    target_provisions_path = store.provisions_path(
        JURISDICTION,
        DOCUMENT_CLASS,
        target_version,
    )
    target_coverage_path = store.coverage_path(
        JURISDICTION,
        DOCUMENT_CLASS,
        target_version,
    )
    targets = (
        target_source_dir,
        target_inventory_path,
        target_provisions_path,
        target_coverage_path,
    )
    for path in targets:
        if path.exists() or path.is_symlink():
            raise ValueError(f"target artifact already exists: {path}")

    rewritten_inventory = [
        replace(
            item,
            source_path=_rewritten_source_path(
                item.source_path,
                target_version=target_version,
            ),
            metadata=_portable_metadata(item.metadata),
        )
        for item in current_inventory
    ]
    rewritten_provisions = [
        _rewritten_record(row, target_version=target_version) for row in current_provisions
    ]
    for citation in ALIASES:
        record = _rewritten_record(
            old_by_citation[citation],
            target_version=target_version,
            alias_from=LEGACY_VERSION,
        )
        rewritten_provisions.append(record)
        rewritten_inventory.append(
            SourceInventoryItem(
                citation_path=record.citation_path,
                source_url=record.source_url,
                source_path=record.source_path,
                source_format=record.source_format,
                sha256=current_source_sha256,
                metadata=record.metadata,
            )
        )

    coverage = compare_provision_coverage(
        tuple(rewritten_inventory),
        tuple(rewritten_provisions),
        JURISDICTION,
        DOCUMENT_CLASS,
        target_version,
    )
    expected_count = len(current_provisions) + len(ALIASES)
    if not coverage.complete or (
        coverage.source_count,
        coverage.provision_count,
        coverage.matched_count,
    ) != (expected_count, expected_count, expected_count):
        raise ValueError(f"successor coverage is incomplete: {coverage.to_mapping()}")

    with TemporaryDirectory(prefix=".build-ny-tanf-", dir=base) as temporary:
        staging_store = CorpusArtifactStore(Path(temporary))
        staged_source_dir = (
            staging_store.root
            / "sources"
            / JURISDICTION
            / DOCUMENT_CLASS
            / target_version
        )
        shutil.copytree(current_source_dir, staged_source_dir / CURRENT_VERSION)
        staged_inventory = staging_store.inventory_path(
            JURISDICTION,
            DOCUMENT_CLASS,
            target_version,
        )
        staged_provisions = staging_store.provisions_path(
            JURISDICTION,
            DOCUMENT_CLASS,
            target_version,
        )
        staged_coverage = staging_store.coverage_path(
            JURISDICTION,
            DOCUMENT_CLASS,
            target_version,
        )
        staging_store.write_inventory(staged_inventory, rewritten_inventory)
        staging_store.write_provisions(staged_provisions, rewritten_provisions)
        staging_store.write_json(staged_coverage, coverage.to_mapping())
        staged = (
            staged_source_dir,
            staged_inventory,
            staged_provisions,
            staged_coverage,
        )
        committed: list[Path] = []
        try:
            for staged_path, target_path in zip(staged, targets, strict=True):
                target_path.parent.mkdir(parents=True, exist_ok=True)
                staged_path.replace(target_path)
                committed.append(target_path)
        except Exception:
            for target_path in reversed(committed):
                _remove_artifact(target_path)
            raise
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--target-version", required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    generated = build_ny_tanf_compatibility_scope(
        repo=args.repo,
        target_version=args.target_version,
        verify_only=args.verify_only,
    )
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
