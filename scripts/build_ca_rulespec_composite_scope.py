#!/usr/bin/env python3
"""Build one source-complete Canadian RuleSpec program scope.

The builder consolidates the ca/policy scopes of a selector into a new scope
and promotes the contracted program roots in that scope's files. A selector
that holds a base scope is refused before consolidation, since a base is
carried unchanged into every successor.

Promotion rewrites a scope's inventory, provisions and coverage in place. It
reads the selectors committed at HEAD of ``releases_dir`` (by default this
script's checkout), of the checkouts that physically hold those three files,
of each checkout the resolver recognises that holds a link on them as given,
and of the checkouts holding each path in ``holders_of``. It refuses a scope
any of them marks as a base, a link or a shared file on its three files, and
any of the three that a base it knows reaches through a link. A checkout it
does not read is one of the threat model's stated limits (2, 11 and 15).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.corpus.resolver import cli_repo
from axiom_corpus.corpus.successors import (
    canonical_scope_key,
    guard_scope_artifacts,
    refuse_links_into_bases,
    tracked_base_scopes,
)
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.consolidate_release_scopes import consolidate_release_scopes

# The tracked selectors are the only record of which scopes are bases.
DEFAULT_RELEASES_DIR = Path(__file__).resolve().parents[1] / "manifests" / "releases"


def _load_citation_contract(path: Path) -> tuple[str, ...]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "citation_paths" not in payload:
        raise ValueError("citation contract must contain citation_paths")
    raw_paths = payload["citation_paths"]
    if not isinstance(raw_paths, list) or not all(
        isinstance(value, str) and value for value in raw_paths
    ):
        raise ValueError("citation_paths must be a list of non-empty strings")
    paths = tuple(raw_paths)
    if len(paths) != len(set(paths)):
        raise ValueError("citation contract contains duplicate paths")
    return paths


def promote_program_roots(
    *,
    base: Path,
    version: str,
    citation_paths: tuple[str, ...],
    releases_dir: Path | None = None,
    holders_of: Iterable[Path] = (),
) -> tuple[Path, Path, Path]:
    """Move each root body to a child so root resolution composes all documents.

    Promotion rewrites the scope's inventory, provisions and coverage in
    place, so before it reads any of them it refuses a version spelled in a
    way no selector can hold (``successors.canonical_scope_key``) and a scope
    that a tracked selector of ``releases_dir`` marks as a base; ``None``
    means ``DEFAULT_RELEASES_DIR``, this script's checkout. It then reads the
    selectors committed at HEAD of the checkouts that physically hold the
    three files, of each checkout the resolver recognises that holds a link
    on them as given, and of the checkouts holding each path in
    ``holders_of``, with the same refusal. It refuses a link at a checkout's
    guarded place that leads into no checkout, a file that resolves to
    another scope's path or has another hard link, and a file that a base it
    knows reaches through a link (``successors.guard_scope_artifacts`` and
    ``refuse_links_into_bases``). A checkout it does not read is one of the
    threat model's stated limits (2, 11 and 15).
    """
    key = canonical_scope_key("ca", "policy", version)
    directory = DEFAULT_RELEASES_DIR if releases_dir is None else releases_dir
    known = set(tracked_base_scopes(directory))
    refusal = (
        f"base scopes are carried unchanged and cannot be promoted in place: ca/policy/{version}"
    )
    if key in known:
        raise ValueError(refusal)
    store = CorpusArtifactStore(base)
    inventory_path = store.inventory_path("ca", "policy", version)
    provisions_path = store.provisions_path("ca", "policy", version)
    coverage_path = store.coverage_path("ca", "policy", version)
    files: Sequence[Path] = (inventory_path, provisions_path, coverage_path)
    for holder_inventory in guard_scope_artifacts(
        files, releases_dir=directory, rewritten=files, holders_of=holders_of
    ):
        extra = tracked_base_scopes(holder_inventory)
        if key in extra:
            raise ValueError(refusal)
        known |= extra
    # The store rewrites each file through a temporary file and a replace, so
    # a base's symlink to one of them would read the promoted bytes.
    refuse_links_into_bases(corpus=store.root, bases=known, rewritten=files)
    inventory = list(load_source_inventory(inventory_path))
    provisions = list(load_provisions(provisions_path))
    inventory_by_path = {item.citation_path: item for item in inventory}
    provisions_by_path = {record.citation_path: record for record in provisions}

    missing = sorted(set(citation_paths) - provisions_by_path.keys())
    if missing:
        raise ValueError(f"composite scope is missing contracted roots: {missing}")

    promoted_inventory: dict[str, SourceInventoryItem] = dict(inventory_by_path)
    promoted_provisions: dict[str, ProvisionRecord] = dict(provisions_by_path)
    for citation_path in citation_paths:
        root = promoted_provisions[citation_path]
        child_path = f"{citation_path}/primary-document"
        if root.body is None or not root.body.strip():
            if not any(
                record.body is not None
                and bool(record.body.strip())
                and record.citation_path.startswith(f"{citation_path}/")
                for record in provisions
            ):
                raise ValueError(f"bodyless program root has no document: {citation_path}")
            if root.body is not None:
                promoted_provisions[citation_path] = replace(root, body=None)
            existing_child = promoted_provisions.get(child_path)
            if existing_child is not None and not (existing_child.body or "").strip():
                promoted_provisions.pop(child_path)
                promoted_inventory.pop(child_path, None)
            continue

        if child_path in promoted_provisions or child_path in promoted_inventory:
            raise ValueError(f"primary document path already exists: {child_path}")
        inventory_item = promoted_inventory[citation_path]
        promoted_inventory[child_path] = replace(
            inventory_item,
            citation_path=child_path,
        )
        promoted_provisions[citation_path] = replace(root, body=None)
        promoted_provisions[child_path] = replace(
            root,
            citation_path=child_path,
            id=deterministic_provision_id(child_path, version),
            parent_citation_path=citation_path,
            parent_id=deterministic_provision_id(citation_path, version),
            level=(root.level or 1) + 1,
            ordinal=1,
            kind="document",
        )

    ordered_inventory = tuple(
        promoted_inventory[path] for path in sorted(promoted_inventory)
    )
    ordered_provisions = tuple(
        promoted_provisions[path] for path in sorted(promoted_provisions)
    )
    coverage = compare_provision_coverage(
        ordered_inventory,
        ordered_provisions,
        "ca",
        "policy",
        version,
    )
    if not coverage.complete:
        raise ValueError("promoted composite scope does not have complete coverage")
    store.write_inventory(inventory_path, ordered_inventory)
    store.write_provisions(provisions_path, ordered_provisions)
    store.write_json(coverage_path, coverage.to_mapping())
    return inventory_path, provisions_path, coverage_path


def build_ca_rulespec_composite_scope(
    *,
    base: Path,
    selector_path: Path,
    citation_contract_path: Path,
    target_version: str,
    supplemental_versions: tuple[str, ...] = (),
    additional_citation_paths: tuple[str, ...] = (),
    releases_dir: Path | None = None,
    holders_of: Iterable[Path] = (),
) -> tuple[Path, ...]:
    """Consolidate the selector's ca/policy scopes and promote the contracted roots.

    A selector that holds a base scope raises ``ValueError`` before
    consolidation, with consolidation's refusal text. ``releases_dir`` names
    the tracked selectors that say which scopes are bases, as consolidation
    and promotion read them; ``None`` means the checkout this script belongs
    to. ``main()`` passes the ``manifests/releases`` of the checkout holding
    ``--base``. Consolidation and promotion also read the selectors committed
    at HEAD of the checkouts that physically hold their paths, of each
    checkout the resolver recognises that holds a link on them as spelled
    through ``base``, and of the checkouts holding each path in ``holders_of``
    (``main()`` passes the working directory). A checkout they do not read is
    one of the threat model's stated limits (2, 11 and 15).
    """
    release = ReleaseManifest.load(selector_path)
    unexpected = sorted(
        scope.key
        for scope in release.scopes
        if scope.jurisdiction != "ca" or scope.document_class != "policy"
    )
    if unexpected:
        raise ValueError(f"selector contains non-Canadian-policy scopes: {unexpected}")
    selected_bases = sorted("/".join(scope.key) for scope in release.scopes if scope.is_base)
    if selected_bases:
        raise ValueError(
            "base scopes are carried unchanged and cannot be consolidated: "
            + ", ".join(selected_bases)
        )
    holders = tuple(holders_of)
    contracted_paths = _load_citation_contract(citation_contract_path)
    citation_paths = (*contracted_paths, *additional_citation_paths)
    if len(citation_paths) != len(set(citation_paths)):
        raise ValueError("composite citation paths must be unique")
    source_versions = tuple(scope.version for scope in release.scopes)
    all_source_versions = (*source_versions, *supplemental_versions)
    if len(all_source_versions) != len({*all_source_versions}):
        raise ValueError("composite source versions must be unique")
    generated = consolidate_release_scopes(
        base=base,
        jurisdiction="ca",
        document_class="policy",
        source_versions=all_source_versions,
        target_version=target_version,
        releases_dir=releases_dir,
        holders_of=holders,
    )
    promote_program_roots(
        base=base,
        version=target_version,
        citation_paths=citation_paths,
        releases_dir=releases_dir,
        holders_of=holders,
    )
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--selector", type=Path, required=True)
    parser.add_argument("--citation-contract", type=Path, required=True)
    parser.add_argument("--target-version", required=True)
    parser.add_argument(
        "--supplemental-version",
        action="append",
        default=[],
        help="Additional ca/policy source version to compose (repeatable).",
    )
    parser.add_argument(
        "--additional-citation",
        action="append",
        default=[],
        help="Additional program-root citation outside the base contract (repeatable).",
    )
    args = parser.parse_args()
    repo = cli_repo(args)
    if repo is None:
        parser.error(
            "neither --base nor the working directory is in an axiom-corpus checkout, so no "
            "tracked selectors say which scopes are bases"
        )
    generated = build_ca_rulespec_composite_scope(
        base=args.base,
        selector_path=args.selector,
        citation_contract_path=args.citation_contract,
        target_version=args.target_version,
        supplemental_versions=tuple(args.supplemental_version),
        additional_citation_paths=tuple(args.additional_citation),
        releases_dir=repo / "manifests" / "releases",
        holders_of=(Path.cwd(),),
    )
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
