#!/usr/bin/env python3
"""Stage already-fetched official sources as a complete corpus scope.

This command is deliberately offline.  Every input must have a provenance
sidecar containing ``url``, ``fetched_at``, ``sha256``, and ``file``.  The
recovery plan selects an explicit parser; content sniffing is used only to
reject mismatches, never to silently select another parser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import (
    OfficialDocumentSource,
    _extract_blocks,
    _inventory_items,
    _provision_records,
)
from axiom_corpus.corpus.ecfr import (
    EcfrPartTarget,
    iter_ecfr_title_provisions,
)
from axiom_corpus.corpus.ingest_manifests import (
    build_ingest_manifest,
    default_ingest_manifest_path,
)
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from axiom_corpus.corpus.usc import (
    build_usc_inventory_from_xml,
    decode_uslm_bytes,
    iter_usc_title_provisions,
    parse_uslm_title,
)

PARSERS = {"uscode-olrc-xml", "ecfr-xml", "federal-register", "html-manual", "pdf"}
PROVENANCE_KEYS = {"url", "fetched_at", "sha256", "file"}


@dataclass(frozen=True)
class FetchedFile:
    path: Path
    url: str
    fetched_at: str
    sha256: str
    sidecar: Path


@dataclass(frozen=True)
class RecoveryResult:
    parser: str
    jurisdiction: str
    document_class: str
    version: str
    provisions: int
    artifacts: tuple[Path, ...]
    manifest: Path | None
    dry_run: bool


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def load_plan_entry(path: Path, entry_id: str | None) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        entries = payload["entries"]
    elif isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = [payload]
    else:
        raise ValueError("recovery plan must be an object, list, or object with entries")
    candidates = [
        _mapping(row, "plan entry")
        for row in entries
        if entry_id is None or str(_mapping(row, "plan entry").get("id")) == entry_id
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"plan selection must resolve to exactly one entry (got {len(candidates)})"
        )
    entry = candidates[0]
    required = {"parser", "jurisdiction", "document_class", "version"}
    missing = required - entry.keys()
    if missing:
        raise ValueError(f"plan entry missing fields: {', '.join(sorted(missing))}")
    if entry["parser"] not in PARSERS:
        raise ValueError(
            f"unsupported parser {entry['parser']!r}; expected one of {sorted(PARSERS)}"
        )
    return entry


def load_fetched_files(fetched_dir: Path) -> tuple[FetchedFile, ...]:
    root = fetched_dir.resolve()
    found: list[FetchedFile] = []
    for sidecar in sorted(root.rglob("*.json")):
        try:
            payload = json.loads(sidecar.read_text())
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or not payload.keys() >= PROVENANCE_KEYS:
            continue
        relative = Path(str(payload["file"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe provenance file path in {sidecar}: {relative}")
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError(f"provenance file does not exist under fetched dir: {relative}")
        expected = str(payload["sha256"]).lower()
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if len(expected) != 64 or actual != expected:
            raise ValueError(f"sha256 mismatch for {relative}: expected {expected}, got {actual}")
        found.append(
            FetchedFile(source, str(payload["url"]), str(payload["fetched_at"]), actual, sidecar)
        )
    if not found:
        raise ValueError(f"no provenance sidecars found under {fetched_dir}")
    names = [row.path.name for row in found]
    if len(names) != len(set(names)):
        raise ValueError("fetched files must have unique basenames for deterministic staging")
    return tuple(found)


def _select_files(
    entry: dict[str, Any], fetched: tuple[FetchedFile, ...]
) -> tuple[FetchedFile, ...]:
    declared = entry.get("files")
    if declared is None:
        return fetched
    if not isinstance(declared, list) or not all(isinstance(item, str) for item in declared):
        raise ValueError("plan files must be a list of provenance file names or URLs")
    wanted = set(declared)
    selected = tuple(row for row in fetched if row.path.name in wanted or row.url in wanted)
    matched = {row.path.name for row in selected} | {row.url for row in selected}
    missing = wanted - matched
    if missing:
        raise ValueError(f"plan files absent from fetched provenance: {sorted(missing)}")
    return selected


def _assert_xml_kind(row: FetchedFile, parser: str) -> ET.Element:
    if row.path.suffix.lower() != ".xml":
        raise ValueError(f"{parser} requires .xml input: {row.path.name}")
    try:
        root = ET.fromstring(row.path.read_bytes())
    except ET.ParseError as exc:
        raise ValueError(f"invalid XML for {parser}: {row.path.name}: {exc}") from exc
    tags = {elem.tag.rsplit("}", 1)[-1].upper() for elem in root.iter()}
    if parser == "uscode-olrc-xml" and not ({"USLM", "TITLE", "SECTION"} & tags):
        raise ValueError(f"USLM parser mismatch: {row.path.name}")
    if parser == "ecfr-xml" and not ({"ECFR", "DIV5", "DIV8"} & tags):
        raise ValueError(f"eCFR parser mismatch: {row.path.name}")
    return root


def _stage_source(
    store: CorpusArtifactStore, entry: dict[str, Any], row: FetchedFile
) -> tuple[Path, str]:
    relative = f"official-documents/{safe_segment(row.path.name)}"
    path = store.source_path(
        entry["jurisdiction"], entry["document_class"], entry["version"], relative
    )
    store.write_bytes(path, row.path.read_bytes())
    key = path.relative_to(store.root).as_posix()
    return path, key


def _uscode_records(
    entry: dict[str, Any], rows: tuple[FetchedFile, ...], source_keys: dict[Path, str]
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    if entry["jurisdiction"] != "us" or entry["document_class"] != "statute":
        raise ValueError("uscode-olrc-xml requires jurisdiction=us and document_class=statute")
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    for row in rows:
        _assert_xml_kind(row, "uscode-olrc-xml")
        xml = decode_uslm_bytes(row.path.read_bytes())
        document = parse_uslm_title(xml, title=entry.get("title"))
        inventory = build_usc_inventory_from_xml(
            xml,
            title=document.title,
            run_id=None,
            source_sha256=row.sha256,
            source_download_url=row.url,
        )
        key = source_keys[row.path]
        for item in inventory.items:
            mapping = item.to_mapping()
            mapping["source_path"] = key
            items.append(SourceInventoryItem.from_mapping(mapping))
        records.extend(
            iter_usc_title_provisions(
                xml,
                version=entry["version"],
                source_path=key,
                title=document.title,
                source_as_of=entry.get("source_as_of"),
                expression_date=entry.get("expression_date"),
                source_download_url=row.url,
            )
        )
    return items, records


def _ecfr_records(
    entry: dict[str, Any], rows: tuple[FetchedFile, ...], source_keys: dict[Path, str]
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    if entry["jurisdiction"] != "us" or entry["document_class"] != "regulation":
        raise ValueError("ecfr-xml requires jurisdiction=us and document_class=regulation")
    title = int(entry["title"])
    parts = entry.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("ecfr-xml plan requires a non-empty parts list")
    targets = tuple(EcfrPartTarget(title=title, part=str(part)) for part in parts)
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    for row in rows:
        _assert_xml_kind(row, "ecfr-xml")
        parsed = list(
            iter_ecfr_title_provisions(
                row.path.read_text(),
                targets,
                entry["version"],
                source_keys[row.path],
                entry.get("source_as_of"),
                entry.get("expression_date"),
            )
        )
        if not parsed:
            raise ValueError(
                f"eCFR parser produced no provisions for declared title/parts: {row.path.name}"
            )
        records.extend(parsed)
        items.extend(
            SourceInventoryItem(
                citation_path=record.citation_path,
                source_url=row.url,
                source_path=source_keys[row.path],
                source_format="ecfr-xml",
                sha256=row.sha256,
                metadata=record.metadata,
            )
            for record in parsed
        )
    return items, records


def _document_records(
    entry: dict[str, Any], rows: tuple[FetchedFile, ...], source_keys: dict[Path, str]
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    expected = "html" if entry["parser"] == "html-manual" else "pdf"
    docs = entry.get("documents")
    if not isinstance(docs, list) or len(docs) != len(rows):
        raise ValueError(f"{entry['parser']} requires one documents config per selected file")
    configs = {
        str(doc.get("file")): _mapping(doc, "document config")
        for doc in docs
        if isinstance(doc, dict)
    }
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    for row in rows:
        config = configs.get(row.path.name)
        if config is None:
            raise ValueError(f"missing document config for {row.path.name}")
        if expected == "html" and row.path.suffix.lower() not in {".html", ".htm"}:
            raise ValueError(f"html-manual parser mismatch: {row.path.name}")
        if expected == "pdf" and (
            row.path.suffix.lower() != ".pdf" or not row.path.read_bytes().startswith(b"%PDF")
        ):
            raise ValueError(f"PDF parser mismatch: {row.path.name}")
        source = OfficialDocumentSource(
            source_id=str(config.get("source_id") or row.path.stem),
            jurisdiction=entry["jurisdiction"],
            document_class=entry["document_class"],
            title=str(config["title"]),
            source_url=row.url,
            citation_path=config.get("citation_path"),
            source_format=expected,
            source_as_of=entry.get("source_as_of"),
            expression_date=entry.get("expression_date"),
            extraction=config.get("extraction"),
            metadata={"fetched_at": row.fetched_at},
        )
        blocks = _extract_blocks(
            row.path.read_bytes(),
            expected,
            source_url=row.url,
            title=source.title,
            extraction=source.extraction,
        )
        if not blocks:
            raise ValueError(f"{entry['parser']} produced no text blocks: {row.path.name}")
        key = source_keys[row.path]
        items.extend(
            _inventory_items(
                source,
                blocks=blocks,
                source_key=key,
                source_format=expected,
                source_sha=row.sha256,
                content_type=None,
                final_url=row.url,
            )
        )
        records.extend(
            _provision_records(
                source,
                blocks=blocks,
                version=entry["version"],
                source_key=key,
                source_format=expected,
                source_as_of=entry.get("source_as_of") or entry["version"],
                expression_date=entry.get("expression_date")
                or entry.get("source_as_of")
                or entry["version"],
                content_type=None,
                final_url=row.url,
            )
        )
    return items, records


def _federal_register_records(
    entry: dict[str, Any], rows: tuple[FetchedFile, ...], source_keys: dict[Path, str]
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    if entry["jurisdiction"] != "us" or entry["document_class"] != "rulemaking":
        raise ValueError("federal-register requires jurisdiction=us and document_class=rulemaking")
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    root = "us/rulemaking/federal-register"
    first = rows[0]
    root_metadata = {"kind": "collection", "source": "FederalRegister.gov API"}
    items.append(
        SourceInventoryItem(
            root,
            first.url,
            source_keys[first.path],
            "federal-register-api-json",
            first.sha256,
            root_metadata,
        )
    )
    records.append(
        ProvisionRecord(
            id=deterministic_provision_id(root),
            jurisdiction="us",
            document_class="rulemaking",
            citation_path=root,
            heading="Federal Register Regulatory Activity",
            version=entry["version"],
            source_url=first.url,
            source_path=source_keys[first.path],
            source_id="federal-register",
            source_format="federal-register-api-json",
            source_as_of=entry.get("source_as_of") or entry["version"],
            expression_date=entry.get("expression_date") or entry["version"],
            level=1,
            kind="collection",
            metadata=root_metadata,
        )
    )
    dates: dict[str, tuple[FetchedFile, int]] = {}
    decoded: list[tuple[FetchedFile, dict[str, Any]]] = []
    for row in rows:
        if row.path.suffix.lower() != ".json":
            raise ValueError(f"Federal Register parser requires document JSON: {row.path.name}")
        data = _mapping(json.loads(row.path.read_text()), "Federal Register document")
        number = str(data.get("document_number") or "")
        publication_date = str(data.get("publication_date") or "")
        if not number or not publication_date or not data.get("title"):
            raise ValueError(f"Federal Register parser mismatch: {row.path.name}")
        decoded.append((row, data))
        prior = dates.get(publication_date)
        dates[publication_date] = (
            row if prior is None else prior[0],
            1 + (prior[1] if prior else 0),
        )
    for date_ordinal, (publication_date, (row, count)) in enumerate(sorted(dates.items()), start=1):
        date_path = f"{root}/{publication_date}"
        metadata = {
            "kind": "publication_date",
            "publication_date": publication_date,
            "document_count": count,
        }
        items.append(
            SourceInventoryItem(
                date_path,
                row.url,
                source_keys[row.path],
                "federal-register-api-json",
                row.sha256,
                metadata,
            )
        )
        records.append(
            ProvisionRecord(
                id=deterministic_provision_id(date_path),
                jurisdiction="us",
                document_class="rulemaking",
                citation_path=date_path,
                heading=f"Federal Register documents published {publication_date}",
                version=entry["version"],
                source_url=row.url,
                source_path=source_keys[row.path],
                source_id="federal-register",
                source_format="federal-register-api-json",
                source_as_of=entry.get("source_as_of") or publication_date,
                expression_date=publication_date,
                parent_citation_path=root,
                level=2,
                ordinal=date_ordinal,
                kind="publication_date",
                metadata=metadata,
            )
        )
    for ordinal, (row, data) in enumerate(decoded, start=1):
        number = str(data.get("document_number") or "")
        publication_date = str(data.get("publication_date") or "")
        citation_path = f"{root}/{publication_date}/{safe_segment(number)}"
        metadata = {
            "fetched_at": row.fetched_at,
            "document_number": number,
            "publication_date": publication_date,
            "type": data.get("type"),
        }
        items.append(
            SourceInventoryItem(
                citation_path,
                row.url,
                source_keys[row.path],
                "federal-register-api-json",
                row.sha256,
                metadata,
            )
        )
        body = str(data.get("body") or data.get("abstract") or data.get("action") or "").strip()
        records.append(
            ProvisionRecord(
                id=deterministic_provision_id(citation_path),
                jurisdiction="us",
                document_class="rulemaking",
                citation_path=citation_path,
                body=body or None,
                heading=str(data["title"]),
                citation_label=str(data.get("citation") or number),
                version=entry["version"],
                source_url=row.url,
                source_path=source_keys[row.path],
                source_id="federal-register",
                source_format="federal-register-api-json",
                source_document_id=number,
                source_as_of=entry.get("source_as_of") or publication_date,
                expression_date=publication_date,
                parent_citation_path=f"{root}/{publication_date}",
                level=3,
                ordinal=ordinal,
                kind=str(data.get("type") or "document").lower(),
                metadata=metadata,
            )
        )
    return items, records


def recover(
    entry: dict[str, Any], fetched_dir: Path, *, base: Path, repo: Path, dry_run: bool
) -> RecoveryResult:
    rows = _select_files(entry, load_fetched_files(fetched_dir))
    destination = base
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if dry_run:
        temporary = tempfile.TemporaryDirectory(prefix="recover-ingest-")
        destination = Path(temporary.name)
    store = CorpusArtifactStore(destination)
    staged: list[Path] = []
    source_keys: dict[Path, str] = {}
    for row in rows:
        path, key = _stage_source(store, entry, row)
        staged.append(path)
        source_keys[row.path] = key
        provenance_path = store.source_path(
            entry["jurisdiction"],
            entry["document_class"],
            entry["version"],
            f"provenance/{safe_segment(row.path.name)}.json",
        )
        store.write_bytes(provenance_path, row.sidecar.read_bytes())
        staged.append(provenance_path)
    parser = entry["parser"]
    if parser == "uscode-olrc-xml":
        items, records = _uscode_records(entry, rows, source_keys)
    elif parser == "ecfr-xml":
        items, records = _ecfr_records(entry, rows, source_keys)
    elif parser == "federal-register":
        items, records = _federal_register_records(entry, rows, source_keys)
    else:
        items, records = _document_records(entry, rows, source_keys)
    if (
        not records
        or {r.jurisdiction for r in records} != {entry["jurisdiction"]}
        or {r.document_class for r in records} != {entry["document_class"]}
        or {r.version for r in records} != {entry["version"]}
    ):
        raise ValueError(
            "parser output does not exactly match proposed jurisdiction/class/version scope"
        )
    inventory_path = store.inventory_path(
        entry["jurisdiction"], entry["document_class"], entry["version"]
    )
    provisions_path = store.provisions_path(
        entry["jurisdiction"], entry["document_class"], entry["version"]
    )
    coverage_path = store.coverage_path(
        entry["jurisdiction"], entry["document_class"], entry["version"]
    )
    store.write_inventory(inventory_path, items)
    store.write_provisions(provisions_path, records)
    coverage = compare_provision_coverage(
        items,
        records,
        jurisdiction=entry["jurisdiction"],
        document_class=entry["document_class"],
        version=entry["version"],
    )
    if not coverage.complete:
        raise ValueError(f"coverage is incomplete: {coverage.to_mapping()}")
    store.write_json(coverage_path, coverage.to_mapping())
    artifacts = tuple(staged + [inventory_path, provisions_path, coverage_path])
    manifest_path: Path | None = None
    if not dry_run:
        command = f"scripts/recover_ingest.py --fetched-dir {fetched_dir} --plan <plan>"
        manifest = build_ingest_manifest(
            repo=repo,
            base=base,
            jurisdiction=entry["jurisdiction"],
            document_class=entry["document_class"],
            version=entry["version"],
            command=command,
            applied_files=list(artifacts),
        )
        manifest_path = repo / default_ingest_manifest_path(
            jurisdiction=entry["jurisdiction"],
            document_class=entry["document_class"],
            version=entry["version"],
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    result = RecoveryResult(
        parser,
        entry["jurisdiction"],
        entry["document_class"],
        entry["version"],
        len(records),
        artifacts,
        manifest_path,
        dry_run,
    )
    if temporary is not None:
        temporary.cleanup()
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetched-dir", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--entry", help="Entry id when the plan contains multiple entries")
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = recover(
            load_plan_entry(args.plan, args.entry),
            args.fetched_dir,
            base=args.base,
            repo=args.repo.resolve(),
            dry_run=args.dry_run,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"recovery ingest refused: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "parser": result.parser,
                "scope": [result.jurisdiction, result.document_class, result.version],
                "provisions": result.provisions,
                "dry_run": result.dry_run,
                "artifacts": [str(path) for path in result.artifacts],
                "unsigned_manifest": str(result.manifest) if result.manifest else None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
