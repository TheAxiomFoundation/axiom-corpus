#!/usr/bin/env python3
"""Cut the federal recovery statute scope to its release-plan citations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.usc import (
    _source_artifact_bytes,
    build_usc_inventory_from_xml,
    decode_uslm_bytes,
    iter_usc_title_provisions,
)

REPO = Path(__file__).parents[1]
BASE = REPO / "data/corpus"
PLAN = REPO / "us-source-recovery-plan.json"
VERSION = "2026-07-13-recovery"
SCOPE = ("us", "statute", VERSION)
TITLE_IDS = {"uscode-title-5", "uscode-title-8", "uscode-title-20", "uscode-title-26", "uscode-title-37"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_rows(path: Path) -> list[ProvisionRecord]:
    return [
        ProvisionRecord.from_mapping(json.loads(line))
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def main() -> int:
    store = CorpusArtifactStore(BASE)
    plan = json.loads(PLAN.read_text())
    entries = {
        row["document_id"]: row
        for row in plan["documents"]
        if row["document_id"] in TITLE_IDS
    }
    if set(entries) != TITLE_IDS:
        raise ValueError(f"missing federal title plan entries: {sorted(TITLE_IDS - set(entries))}")

    inventory_path = store.inventory_path(*SCOPE)
    provisions_path = store.provisions_path(*SCOPE)
    old_items = [
        SourceInventoryItem.from_mapping(row)
        for row in json.loads(inventory_path.read_text())["items"]
    ]
    old_records = _load_rows(provisions_path)
    old_items_by_path = {row.citation_path: row for row in old_items}
    old_records_by_path = {row.citation_path: row for row in old_records}
    items = [row for row in old_items if "/official-documents/usc" not in row.source_path]
    records = [row for row in old_records if "/official-documents/usc" not in row.source_path]

    source_root = store.source_path(*SCOPE, "official-documents")
    provenance_root = store.source_path(*SCOPE, "provenance")
    generated_sources: set[Path] = set()
    resolved: set[str] = set()

    for document_id, entry in sorted(entries.items()):
        title = str(int(document_id.rsplit("-", 1)[-1]))
        full_source = source_root / f"usc{int(title):02d}.xml"
        full_provenance = provenance_root / f"usc{int(title):02d}.xml.json"
        xml = decode_uslm_bytes(full_source.read_bytes())
        provenance = json.loads(full_provenance.read_text())
        targets = {str(path) for path in entry["covers_citation_paths"]}
        sections: dict[str, set[str]] = {}
        for target in targets:
            parts = target.split("/")
            if len(parts) < 4 or parts[:3] != ["us", "statute", title]:
                raise ValueError(f"out-of-scope citation for title {title}: {target}")
            sections.setdefault(parts[3], set()).add(target)

        for section, section_targets in sorted(sections.items()):
            section_path = f"us/statute/{title}/{section}"
            # A cited descendant still requires the complete cited section excerpt;
            # the title is the bodyless structural parent used by the USC adapter.
            allowed = {f"us/statute/{title}", section_path}
            excerpt = _source_artifact_bytes(xml, title=title, allowed_citation_paths=allowed)
            name = f"usc{int(title):02d}-section-{section}.xml"
            excerpt_path = source_root / name
            excerpt_sha = store.write_bytes(excerpt_path, excerpt)
            generated_sources.add(excerpt_path)
            source_key = excerpt_path.relative_to(BASE).as_posix()
            url = str(provenance["url"])
            excerpt_inventory = build_usc_inventory_from_xml(
                decode_uslm_bytes(excerpt),
                title=title,
                source_sha256=excerpt_sha,
                source_download_url=url,
                allowed_citation_paths=allowed,
            )
            excerpt_items = [replace(row, source_path=source_key) for row in excerpt_inventory.items]
            excerpt_records = list(
                iter_usc_title_provisions(
                    decode_uslm_bytes(excerpt),
                    version=VERSION,
                    source_path=source_key,
                    title=title,
                    source_as_of="2026-07-13",
                    expression_date="2026-07-13",
                    source_download_url=url,
                    allowed_citation_paths={row.citation_path for row in excerpt_items},
                )
            )
            paths = {row.citation_path for row in excerpt_records}
            missing = section_targets - paths
            for target in sorted(missing):
                old_item = old_items_by_path.get(target)
                old_record = old_records_by_path.get(target)
                if old_item is None or old_record is None:
                    raise ValueError(f"no previously verified exact row for {target}")
                excerpt_items.append(
                    replace(old_item, source_path=source_key, sha256=excerpt_sha)
                )
                excerpt_records.append(replace(old_record, source_path=source_key))
            paths = {row.citation_path for row in excerpt_records}
            missing = section_targets - paths
            if missing:
                raise ValueError(f"excerpt {name} did not resolve: {sorted(missing)}")
            resolved.update(section_targets)
            known_items = {row.citation_path for row in items}
            known_records = {row.citation_path for row in records}
            items.extend(row for row in excerpt_items if row.citation_path not in known_items)
            records.extend(row for row in excerpt_records if row.citation_path not in known_records)
            excerpt_provenance = {
                "document_id": document_id,
                "citation_paths": sorted(section_targets),
                "source_excerpt_sha256": _sha256(excerpt),
                "source_archive_member": provenance["archive_member"],
                "source_archive_sha256": provenance["archive_sha256"],
                "source_archive_url": url,
                "source_archive_member_sha256": provenance["sha256"],
                "extraction": "exact cited section with required structural ancestors",
            }
            store.write_json(provenance_root / f"{name}.json", excerpt_provenance)

        full_source.unlink()
        full_provenance.unlink()

    requested = {
        str(path)
        for entry in entries.values()
        for path in entry["covers_citation_paths"]
    }
    if resolved != requested:
        raise ValueError(f"citation reconciliation failed: {sorted(requested - resolved)}")

    store.write_inventory(inventory_path, items)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        items, records, jurisdiction="us", document_class="statute", version=VERSION
    )
    if not coverage.complete:
        raise ValueError(f"slim scope coverage incomplete: {coverage.to_mapping()}")
    store.write_json(store.coverage_path(*SCOPE), coverage.to_mapping())
    report_path = REPO / "recovered-coverage-report.json"
    report = json.loads(report_path.read_text())
    for document_id in sorted(TITLE_IDS):
        title = str(int(document_id.rsplit("-", 1)[-1]))
        report[document_id]["rows"] = sum(
            row.citation_path == f"us/statute/{title}"
            or row.citation_path.startswith(f"us/statute/{title}/")
            for row in records
        )
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    coverage_path = store.coverage_path(*SCOPE)
    artifacts = sorted(path for path in store.source_path(*SCOPE, "").rglob("*") if path.is_file())
    artifacts.extend((coverage_path, inventory_path, provisions_path))
    manifest_path = REPO / ".axiom/ingest-manifests/us/statute/2026-07-13-recovery.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("signature", None)
    manifest["generated_at"] = datetime.now(UTC).isoformat()
    manifest["command"] = {"text": "uv run python scripts/slim_us_recovery_statutes.py"}
    manifest["coverage"] = coverage.to_mapping()
    manifest["applied_files"] = [
        {"path": path.relative_to(REPO).as_posix(), "sha256": _sha256(path.read_bytes())}
        for path in sorted(artifacts)
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"requested": len(requested), "resolved": len(resolved), "rows": len(records), "sources": len(generated_sources), "coverage": coverage.to_mapping()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
