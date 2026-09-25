"""Build the US RuleSpec union that serves every HTS-numbered line of HTS 2026 Revision 15.

The full-schedule scope ``2026-08-09-usitc-hts-2026-rev15-full-schedule`` (PR #595)
is in no release selector, so 12,815 of its 13,790 rate-line citations do not
resolve. It cannot simply be added next to the rulespec scope that carries the
predecessor union's HTS lines,
``2026-08-09-rulespec-hts-current-with-legacy-aluminum-and-witnesses``: the two
share 1,711 citation paths (including the ``us/statute/hts`` root), and a release
with the ``complete-expression-dates-v1`` profile (other than the grandfathered
``us-rulespec-2026-07-19``) rejects a citation path carried by two scopes
(``duplicate_release_citation``), even when the bodies are byte-identical, as
they are here.

So the successor selects the full schedule under its own version in place of the
rulespec scope, and the full schedule carries every shared path. The rulespec
scope also carried three 2025 Revision 16 aluminum lines, 9903.85.02, 9903.85.08
and 9903.85.12. The Revision 15 schedule has no rows for them, and rulespec-us
still cites them. They move to a three-row scope built from
``2026-08-01-usitc-hts-2025-rev16``. Their parent, the ``us/statute/hts`` root, is
carried by the full schedule, and release validation resolves a row's parent only
within the row's own scope. This scope therefore detaches that link the way
``scripts/self_contain_usc_scope.py`` does for partial US Code scopes:
``parent_citation_path`` and ``parent_id`` are cleared, and the row's metadata
records ``self_contained_root`` and ``detached_parent_citation_path``.

Run from the repository root::

    uv run python -m scripts.repro.us_rulespec_2026_09_22_hts_full_schedule_union selector
    uv run python -m scripts.repro.us_rulespec_2026_09_22_hts_full_schedule_union verify
    uv run python -m scripts.repro.us_rulespec_2026_09_22_hts_full_schedule_union scope --base <corpus>

``verify`` checks the committed legacy scope. ``scope`` rebuilds it into a corpus
base that holds the Revision 16 scope and the full-schedule and replaced provisions
but not the legacy scope itself; on a checkout of this branch the scope already
exists and ``consolidate_release_scopes`` refuses to overwrite it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.consolidate_release_scopes import consolidate_release_scopes
from scripts.self_contain_usc_scope import self_contain_scope

JURISDICTION = "us"
DOCUMENT_CLASS = "statute"
HTS_ROOT = "us/statute/hts"

BASE_RELEASE = "us-rulespec-2026-09-14-wave4-r2-union"
RELEASE = "us-rulespec-2026-09-22-hts-full-schedule-union"

FULL_SCHEDULE_VERSION = "2026-08-09-usitc-hts-2026-rev15-full-schedule"
REPLACED_VERSION = "2026-08-09-rulespec-hts-current-with-legacy-aluminum-and-witnesses"
LEGACY_SOURCE_VERSION = "2026-08-01-usitc-hts-2025-rev16"
LEGACY_CITATIONS = (
    "us/statute/hts/9903.85.02",
    "us/statute/hts/9903.85.08",
    "us/statute/hts/9903.85.12",
)
LEGACY_VERSION = f"{LEGACY_SOURCE_VERSION}-r2026-09-22-legacy-aluminum-self-contained"
# The replaced scope took these four lines from the Revision 14 witness-lines
# scope; the full schedule carries the same text with Revision 15 dates and URLs.
WITNESS_CITATIONS = frozenset(
    {
        "us/statute/hts/2203.00.00",
        "us/statute/hts/2203.00.00.30",
        "us/statute/hts/8541.42.00",
        "us/statute/hts/8541.42.00.10",
    }
)

DESCRIPTION = (
    f"Seventh release after {BASE_RELEASE}: every HTS-numbered line of the USITC HTS "
    "2026 Revision 15 schedule (docs/ingest-runs/2026-09-22-hts-full-schedule-union.md). "
    f"It selects {JURISDICTION}/{DOCUMENT_CLASS}/{FULL_SCHEDULE_VERSION} in place of "
    f"{JURISDICTION}/{DOCUMENT_CLASS}/{REPLACED_VERSION}; the two share 1,711 citation "
    "paths with byte-identical bodies, and the full schedule now serves them. The three "
    "2025 Revision 16 aluminum lines only the replaced scope carried (9903.85.02, "
    "9903.85.08, 9903.85.12) stay served from "
    f"{JURISDICTION}/{DOCUMENT_CLASS}/{LEGACY_VERSION}. Every other scope is unchanged."
)


def _scope(version: str) -> dict[str, str]:
    return {
        "jurisdiction": JURISDICTION,
        "document_class": DOCUMENT_CLASS,
        "version": version,
    }


def _provisions(base: Path, version: str) -> tuple[ProvisionRecord, ...]:
    path = CorpusArtifactStore(base).provisions_path(JURISDICTION, DOCUMENT_CLASS, version)
    if not path.is_file():
        raise ValueError(f"provisions artifact not found: {path}")
    records = load_provisions(path)
    if not records:
        raise ValueError(f"provisions artifact is empty: {path}")
    if len({record.citation_path for record in records}) != len(records):
        raise ValueError(f"provisions artifact repeats a citation path: {path}")
    return records


def _inventory(base: Path, version: str) -> tuple[SourceInventoryItem, ...]:
    path = CorpusArtifactStore(base).inventory_path(JURISDICTION, DOCUMENT_CLASS, version)
    if not path.is_file():
        raise ValueError(f"inventory artifact not found: {path}")
    return load_source_inventory(path)


def _sources_dir(base: Path, version: str) -> Path:
    return base / "sources" / JURISDICTION / DOCUMENT_CLASS / version


def _retained_source_path(source_path: str | None) -> str | None:
    """Return where the legacy scope retains a Revision 16 source file."""
    if source_path is None:
        return None
    prefix = f"sources/{JURISDICTION}/{DOCUMENT_CLASS}/{LEGACY_SOURCE_VERSION}/"
    if not source_path.startswith(prefix):
        raise ValueError(f"{source_path} is outside source scope {LEGACY_SOURCE_VERSION}")
    relative = source_path[len(prefix) :]
    return (
        f"sources/{JURISDICTION}/{DOCUMENT_CLASS}/{LEGACY_VERSION}/"
        f"{LEGACY_SOURCE_VERSION}/{relative}"
    )


def _portable_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Mirror consolidation's metadata rule: drop a file:// download_url, {} -> None."""
    if metadata is None:
        return None
    portable = dict(metadata)
    download_url = portable.get("download_url")
    if isinstance(download_url, str) and download_url.startswith("file://"):
        portable.pop("download_url")
    return portable or None


def expected_legacy_scope(
    base: Path,
) -> tuple[tuple[ProvisionRecord, ...], tuple[SourceInventoryItem, ...]]:
    """Derive the legacy scope's rows from Revision 16 without the build tools."""
    wanted = set(LEGACY_CITATIONS)
    records: list[ProvisionRecord] = []
    for record in _provisions(base, LEGACY_SOURCE_VERSION):
        if record.citation_path not in wanted:
            continue
        if record.parent_citation_path != HTS_ROOT:
            raise ValueError(f"{record.citation_path} is not a child of {HTS_ROOT}")
        records.append(
            replace(
                record,
                version=LEGACY_VERSION,
                id=deterministic_provision_id(record.citation_path, LEGACY_VERSION),
                parent_citation_path=None,
                parent_id=None,
                source_path=_retained_source_path(record.source_path),
                metadata={
                    **(_portable_metadata(record.metadata) or {}),
                    "self_contained_root": True,
                    "detached_parent_citation_path": HTS_ROOT,
                },
            )
        )
    items = [
        replace(
            item,
            metadata=_portable_metadata(item.metadata),
            source_path=_retained_source_path(item.source_path),
        )
        for item in _inventory(base, LEGACY_SOURCE_VERSION)
        if item.citation_path in wanted
    ]
    if sorted(record.citation_path for record in records) != sorted(wanted) or sorted(
        item.citation_path for item in items
    ) != sorted(wanted):
        raise ValueError(f"{LEGACY_SOURCE_VERSION} does not carry each legacy line exactly once")
    by_path = {item.citation_path: item for item in items}
    return tuple(records), tuple(by_path[record.citation_path] for record in records)


def _file_digests(directory: Path) -> dict[str, str]:
    """Map every entry under ``directory`` to its digest (``dir`` for directories)."""
    digests: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink():
            raise ValueError(f"source tree contains a symlink: {path}")
        digests[relative] = (
            "dir" if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
        )
    return digests


def _provisions_text(records: Iterable[ProvisionRecord]) -> str:
    return "".join(json.dumps(record.to_mapping(), sort_keys=True) + "\n" for record in records)


def _json_text(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _check_served_rows(
    replaced: tuple[ProvisionRecord, ...],
    full_schedule: dict[str, ProvisionRecord],
    legacy: dict[str, ProvisionRecord],
) -> None:
    """Fail unless every replaced citation still resolves with the same body and shape."""
    missing = sorted(
        record.citation_path
        for record in replaced
        if record.citation_path not in full_schedule and record.citation_path not in legacy
    )
    if missing:
        raise ValueError(f"replaced scope citations would stop resolving: {missing}")
    changed_bodies: list[str] = []
    changed_shape: list[str] = []
    dated_or_sourced_differently: set[str] = set()
    for old in replaced:
        new = full_schedule.get(old.citation_path) or legacy[old.citation_path]
        if new.body != old.body:
            changed_bodies.append(old.citation_path)
        if old.citation_path in legacy:
            parent = (new.metadata or {}).get("detached_parent_citation_path")
            same_shape = (
                new.kind == old.kind
                and new.level == old.level
                and new.heading == old.heading
                and new.expression_date == old.expression_date
                and parent == old.parent_citation_path
            )
        else:
            same_shape = (
                new.kind == old.kind
                and new.level == old.level
                and new.parent_citation_path == old.parent_citation_path
                and (new.heading == old.heading or old.citation_path == HTS_ROOT)
            )
            if new.expression_date != old.expression_date or new.source_url != old.source_url:
                dated_or_sourced_differently.add(old.citation_path)
        if not same_shape:
            changed_shape.append(old.citation_path)
    if changed_bodies:
        raise ValueError(f"served body text would change: {sorted(changed_bodies)}")
    if changed_shape:
        raise ValueError(f"served kind, level, heading or parent would change: {changed_shape}")
    if dated_or_sourced_differently != WITNESS_CITATIONS:
        raise ValueError(
            "expression_date or source_url changes outside the four Revision 14 witness "
            f"lines: {sorted(dated_or_sourced_differently ^ WITNESS_CITATIONS)}"
        )


def verify_scope(base: Path) -> dict[str, int]:
    """Fail unless the committed legacy scope is exactly the derived one and the swap is safe.

    The legacy scope's provisions, inventory and coverage must equal, byte for byte,
    what the build tools write for the rows derived from Revision 16, and its
    retained sources must be Revision 16's. Every citation path of the replaced
    scope must still resolve, in the full schedule or the legacy scope, with the
    same body, kind, level and parent; headings may differ only on the root, and
    dates and source URLs only on the four Revision 14 witness lines.
    """
    store = CorpusArtifactStore(base)
    legacy_path = store.provisions_path(JURISDICTION, DOCUMENT_CLASS, LEGACY_VERSION)
    inventory_path = store.inventory_path(JURISDICTION, DOCUMENT_CLASS, LEGACY_VERSION)
    coverage_path = store.coverage_path(JURISDICTION, DOCUMENT_CLASS, LEGACY_VERSION)
    legacy = _provisions(base, LEGACY_VERSION)
    inventory = _inventory(base, LEGACY_VERSION)
    expected_records, expected_items = expected_legacy_scope(base)
    if legacy_path.read_text(encoding="utf-8") != _provisions_text(expected_records):
        raise ValueError("legacy provisions differ from their derivation")
    if inventory_path.read_text(encoding="utf-8") != _json_text(
        {"items": [item.to_mapping() for item in expected_items]}
    ):
        raise ValueError("legacy inventory differs from its derivation")
    coverage = compare_provision_coverage(
        inventory, legacy, JURISDICTION, DOCUMENT_CLASS, LEGACY_VERSION
    )
    if not coverage.complete or coverage_path.read_text(encoding="utf-8") != _json_text(
        coverage.to_mapping()
    ):
        raise ValueError("legacy coverage is incomplete or stale")

    retained = _sources_dir(base, LEGACY_VERSION)
    if [path.name for path in retained.iterdir()] != [LEGACY_SOURCE_VERSION]:
        raise ValueError(f"unexpected retained source directories under {retained}")
    digests = _file_digests(retained / LEGACY_SOURCE_VERSION)
    if digests != _file_digests(_sources_dir(base, LEGACY_SOURCE_VERSION)):
        raise ValueError(f"retained sources differ from {LEGACY_SOURCE_VERSION}")
    retained_digests = {
        (retained / LEGACY_SOURCE_VERSION / relative).relative_to(base).as_posix(): digest
        for relative, digest in digests.items()
        if digest != "dir"
    }
    for item in inventory:
        if not item.source_path or not item.sha256:
            raise ValueError(f"{item.citation_path} has no source_path or sha256")
        if retained_digests.get(item.source_path) != item.sha256:
            raise ValueError(f"{item.citation_path} source is not retained or its digest differs")

    full_schedule = {
        record.citation_path: record for record in _provisions(base, FULL_SCHEDULE_VERSION)
    }
    if HTS_ROOT not in full_schedule:
        raise ValueError(f"the full schedule does not carry the detached parent {HTS_ROOT}")
    if set(LEGACY_CITATIONS) & set(full_schedule):
        raise ValueError("the full schedule already carries a legacy citation")
    replaced = _provisions(base, REPLACED_VERSION)
    replaced_paths = {record.citation_path for record in replaced}
    if not set(LEGACY_CITATIONS) <= replaced_paths:
        raise ValueError("the replaced scope does not carry every legacy citation")
    _check_served_rows(replaced, full_schedule, {record.citation_path: record for record in legacy})

    return {
        "legacy": len(legacy),
        "full_schedule": len(full_schedule),
        "replaced": len(replaced),
        "shared_with_replaced": len(replaced_paths & set(full_schedule)),
    }


def build_scope(base: Path) -> tuple[Path, ...]:
    """Build the three-row legacy scope, detach its parent link and verify it."""
    generated = consolidate_release_scopes(
        base=base,
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS,
        source_versions=(LEGACY_SOURCE_VERSION,),
        target_version=LEGACY_VERSION,
        included_citations_by_version={LEGACY_SOURCE_VERSION: frozenset(LEGACY_CITATIONS)},
    )
    try:
        self_contain_scope(
            base, jurisdiction=JURISDICTION, document_class=DOCUMENT_CLASS, version=LEGACY_VERSION
        )
        verify_scope(base)
    except BaseException:
        # consolidate_release_scopes refuses an existing target and stages its own
        # output, so every generated path was created by this run.
        for path in generated:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            elif path.exists() or path.is_symlink():
                path.unlink()
        raise
    return generated


def build_release(*, release_dir: Path, output_dir: Path | None = None) -> Path:
    """Swap the rulespec HTS scope for the full schedule and the legacy scope."""
    payload = json.loads((release_dir / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    replaced = _scope(REPLACED_VERSION)
    additions = [_scope(FULL_SCHEDULE_VERSION), _scope(LEGACY_VERSION)]
    if replaced not in scopes:
        raise ValueError(f"{REPLACED_VERSION} is not in {BASE_RELEASE}")
    if any(addition in scopes for addition in additions):
        raise ValueError(f"{BASE_RELEASE} already selects an added scope")

    final_scopes = sorted(
        [*(scope for scope in scopes if scope != replaced), *additions],
        key=lambda scope: (scope["jurisdiction"], scope["document_class"], scope["version"]),
    )
    identities = {
        (scope["jurisdiction"], scope["document_class"], scope["version"]) for scope in final_scopes
    }
    if len(identities) != len(final_scopes):
        raise ValueError("release selector would contain duplicate scopes")

    payload.update({"description": DESCRIPTION, "name": RELEASE, "scopes": final_scopes})
    output = (output_dir or release_dir) / f"{RELEASE}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the US RuleSpec HTS full-schedule union and its legacy-line scope."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    scope = commands.add_parser(
        "scope",
        help=(
            "build and verify the legacy-line scope in a base that has the Revision 16 scope "
            "and the full-schedule and replaced provisions but not the legacy scope"
        ),
    )
    scope.add_argument("--base", type=Path, default=Path("data/corpus"))
    verify = commands.add_parser("verify", help="verify the committed legacy-line scope")
    verify.add_argument("--base", type=Path, default=Path("data/corpus"))
    selector = commands.add_parser("selector", help="write the successor release selector")
    selector.add_argument("--release-dir", type=Path, default=Path("manifests/releases"))
    selector.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.command == "scope":
        for path in build_scope(args.base):
            print(path)
        print(json.dumps(verify_scope(args.base), sort_keys=True))
    elif args.command == "verify":
        print(json.dumps(verify_scope(args.base), sort_keys=True))
    else:
        print(build_release(release_dir=args.release_dir, output_dir=args.output_dir))


if __name__ == "__main__":
    main()
