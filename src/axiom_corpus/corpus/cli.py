"""CLI for the source-first corpus pipeline."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from collections.abc import Iterable
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from axiom_corpus.corpus.analytics import (
    build_analytics_report,
    load_provision_count_snapshot,
)
from axiom_corpus.corpus.anchors import (
    AnchorResolver,
    generate_anchors_for_provision,
    generate_stored_leaf_anchors,
    load_anchors,
    verify_anchors_against_provisions,
    write_anchors_jsonl,
)
from axiom_corpus.corpus.anchors_supabase import load_anchors_to_supabase
from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.belgium_eli import (
    BelgianELIExtractReport,
    BelgianMoniteurDiscoveryReport,
    discover_belgian_moniteur_sources,
    extract_belgian_eli,
)
from axiom_corpus.corpus.california_mpp import (
    MppDocxSource,
    extract_california_mpp_calfresh,
)
from axiom_corpus.corpus.colorado import extract_colorado_ccr
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.document_sections import split_document_body
from axiom_corpus.corpus.documents import extract_official_documents
from axiom_corpus.corpus.ecfr import (
    build_ecfr_inventory,
    ecfr_run_id,
    extract_ecfr,
    load_ecfr_graphic_transcriptions,
)
from axiom_corpus.corpus.eli import extract_eli_documents
from axiom_corpus.corpus.federal_register import (
    DEFAULT_DOCUMENT_TYPES,
    FederalRegisterCfrSectionRef,
    extract_federal_register,
    extract_federal_register_cfr_sections,
)
from axiom_corpus.corpus.germany_gii import (
    GermanGiiExtractReport,
    GermanLaw,
    extract_german_gii,
)
from axiom_corpus.corpus.illinois_admin_code import extract_illinois_admin_code
from axiom_corpus.corpus.ingest_manifests import (
    INGEST_MANIFEST_PRIVATE_KEY_ENV,
    build_ingest_manifest,
    guard_ingested_artifacts,
    write_signed_ingest_manifest,
)
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.maryland_comar import extract_maryland_comar
from axiom_corpus.corpus.models import (
    CorpusManifest,
    CorpusSource,
    DocumentClass,
    ProvisionRecord,
)
from axiom_corpus.corpus.montana_admin_rules import extract_montana_admin_rules
from axiom_corpus.corpus.navigation import (
    NavigationNode,
    build_navigation_nodes,
)
from axiom_corpus.corpus.navigation_supabase import (
    fetch_navigation_statuses,
    fetch_provisions_for_navigation,
    write_navigation_nodes_to_supabase,
)
from axiom_corpus.corpus.new_jersey_snap import reconstruct_new_jersey_snap_rules
from axiom_corpus.corpus.ny_rulemaking import extract_ny_state_register
from axiom_corpus.corpus.nycrr import extract_nycrr
from axiom_corpus.corpus.nz_legislation import (
    NZLegislationExtractReport,
    extract_nz_legislation,
)
from axiom_corpus.corpus.ohio_admin_code import extract_ohio_admin_code
from axiom_corpus.corpus.oregon_admin_rules import extract_oregon_admin_rules
from axiom_corpus.corpus.pennsylvania_code import extract_pennsylvania_code
from axiom_corpus.corpus.policyengine_references import (
    PolicyEngineReference,
    PolicyEngineReferenceScope,
    scan_policyengine_references,
    summarize_policyengine_references,
    write_policyengine_references_jsonl,
    write_policyengine_url_inventory,
)
from axiom_corpus.corpus.r2 import (
    DEFAULT_ARTIFACT_PREFIXES,
    DEFAULT_RELEASE_ARTIFACT_PREFIXES,
    build_artifact_report,
    build_artifact_report_with_r2,
    load_r2_config,
    sync_artifacts_to_r2,
)
from axiom_corpus.corpus.regulation_completion import (
    build_regulation_completion_report,
)
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, resolve_release_manifest_path
from axiom_corpus.corpus.rulespec_paths import (
    JURISDICTION_REPO_MAP,
    discover_encoded_paths,
    discover_encoded_paths_for_jurisdictions,
    monorepo_dir_name_for_jurisdiction,
    repo_prefix_for_jurisdiction,
    resolve_jurisdiction_dir,
)
from axiom_corpus.corpus.scope_tracking import verify_scope_tracked
from axiom_corpus.corpus.source_discovery import build_source_discovery_report
from axiom_corpus.corpus.source_promotion import promote_source_discovery_group
from axiom_corpus.corpus.state_adapters.alabama import extract_alabama_code
from axiom_corpus.corpus.state_adapters.alaska import (
    ALASKA_STATUTES_DEFAULT_YEAR,
    extract_alaska_statutes,
)
from axiom_corpus.corpus.state_adapters.arizona import extract_arizona_revised_statutes
from axiom_corpus.corpus.state_adapters.colorado_crs import (
    extract_colorado_revised_statutes,
)
from axiom_corpus.corpus.state_adapters.connecticut import extract_connecticut_statutes
from axiom_corpus.corpus.state_adapters.delaware import extract_delaware_code
from axiom_corpus.corpus.state_adapters.florida import (
    FLORIDA_STATUTES_DEFAULT_YEAR,
    extract_florida_statutes,
)
from axiom_corpus.corpus.state_adapters.hawaii import extract_hawaii_revised_statutes
from axiom_corpus.corpus.state_adapters.idaho import extract_idaho_statutes
from axiom_corpus.corpus.state_adapters.illinois import extract_illinois_ilcs
from axiom_corpus.corpus.state_adapters.indiana import (
    INDIANA_CODE_DEFAULT_YEAR,
    extract_indiana_code,
)
from axiom_corpus.corpus.state_adapters.iowa import (
    IOWA_CODE_DEFAULT_YEAR,
    extract_iowa_code,
)
from axiom_corpus.corpus.state_adapters.kansas import extract_kansas_statutes
from axiom_corpus.corpus.state_adapters.louisiana import (
    extract_louisiana_revised_statutes,
)
from axiom_corpus.corpus.state_adapters.maine import extract_maine_revised_statutes
from axiom_corpus.corpus.state_adapters.maryland import extract_maryland_code
from axiom_corpus.corpus.state_adapters.massachusetts import (
    extract_massachusetts_general_laws,
)
from axiom_corpus.corpus.state_adapters.michigan import (
    extract_michigan_compiled_laws,
)
from axiom_corpus.corpus.state_adapters.missouri import (
    extract_missouri_revised_statutes,
)
from axiom_corpus.corpus.state_adapters.montana import (
    MONTANA_CODE_DEFAULT_YEAR,
    extract_montana_code,
)
from axiom_corpus.corpus.state_adapters.nevada import (
    NEVADA_NRS_DEFAULT_YEAR,
    extract_nevada_nrs,
)
from axiom_corpus.corpus.state_adapters.new_hampshire import extract_new_hampshire_rsa
from axiom_corpus.corpus.state_adapters.new_jersey import (
    NEW_JERSEY_STATUTES_ZIP_URL,
    extract_new_jersey_statutes,
)
from axiom_corpus.corpus.state_adapters.new_mexico import extract_new_mexico_statutes
from axiom_corpus.corpus.state_adapters.new_york import (
    extract_new_york_consolidated_laws,
    extract_new_york_openleg_api,
    extract_new_york_openleg_sections,
)
from axiom_corpus.corpus.state_adapters.nyc_admin_code import extract_nyc_admin_code
from axiom_corpus.corpus.state_adapters.oklahoma import extract_oklahoma_statutes
from axiom_corpus.corpus.state_adapters.oregon import (
    OREGON_ORS_DEFAULT_YEAR,
    extract_oregon_ors,
)
from axiom_corpus.corpus.state_adapters.pennsylvania import extract_pennsylvania_statutes
from axiom_corpus.corpus.state_adapters.rhode_island import (
    RHODE_ISLAND_GENERAL_LAWS_DEFAULT_YEAR,
    extract_rhode_island_general_laws,
)
from axiom_corpus.corpus.state_adapters.south_carolina import extract_south_carolina_code
from axiom_corpus.corpus.state_adapters.south_dakota import (
    extract_south_dakota_codified_laws,
)
from axiom_corpus.corpus.state_adapters.utah import (
    UTAH_CODE_SOURCE_URL,
    extract_utah_code,
)
from axiom_corpus.corpus.state_adapters.west_virginia import extract_west_virginia_code
from axiom_corpus.corpus.state_adapters.wisconsin import (
    WISCONSIN_STATUTES_TOC_URL,
    extract_wisconsin_statutes,
)
from axiom_corpus.corpus.state_statute_completion import (
    build_state_statute_completion_report,
    load_source_access_statuses,
)
from axiom_corpus.corpus.states import (
    StateStatuteExtractReport,
    extract_california_code_sections,
    extract_california_codes_bulk,
    extract_cic_html_release,
    extract_cic_odt_release,
    extract_colorado_docx_release,
    extract_dc_code,
    extract_minnesota_statutes,
    extract_nebraska_revised_statutes,
    extract_ohio_revised_code,
    extract_state_html_directory,
    extract_texas_tcas,
    extract_washington_rcw,
)
from axiom_corpus.corpus.supabase import (
    DEFAULT_ACCESS_TOKEN_ENV,
    DEFAULT_AXIOM_SUPABASE_URL,
    DEFAULT_SERVICE_KEY_ENV,
    backfill_version_chunk,
    delete_supabase_provisions_scope,
    deterministic_provision_id,
    fetch_provision_counts,
    fetch_release_provision_counts,
    list_single_active_release_scopes,
    load_provisions_to_supabase,
    resolve_service_key,
    verify_release_coverage,
    write_supabase_rows_jsonl,
)
from axiom_corpus.corpus.uk_legislation import (
    UKLegislationExtractReport,
    extract_uk_legislation_sections,
)
from axiom_corpus.corpus.usc import (
    build_usc_inventory_from_xml,
    decode_uslm_bytes,
    extract_usc,
    extract_usc_directory,
    infer_uslm_title,
    usc_run_id,
)
from axiom_corpus.corpus.virginia_vac import extract_virginia_vac
from axiom_corpus.corpus.washington_wac import extract_washington_wac
from axiom_corpus.fetchers.nz_legislation_api import (
    NZ_LEGISLATION_API_KEY_ENV,
    NZ_LEGISLATION_DEFAULT_TYPES,
    NZLegislationAPIDownloadReport,
    download_nz_legislation_api_sources,
)


def _cmd_validate_manifest(args: argparse.Namespace) -> int:
    manifest = CorpusManifest.load(args.path)
    manifest.require_unique_sources()
    print(
        json.dumps(
            {
                "ok": True,
                "version": manifest.version,
                "sources": len(manifest.sources),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_sign_ingest_manifest(args: argparse.Namespace) -> int:
    private_key = os.environ.get(INGEST_MANIFEST_PRIVATE_KEY_ENV)
    if not private_key:
        print(f"{INGEST_MANIFEST_PRIVATE_KEY_ENV} is required to sign ingest manifests.")
        return 2
    repo = args.repo.resolve()
    applied_files: list[Path] | None = None
    if args.file:
        applied_files = list(args.file)
    deleted_files: list[Path] = list(args.deleted_file or [])
    reasoning_logs: list[Path] = list(args.reasoning_log or [])
    manifest = build_ingest_manifest(
        repo=repo,
        base=args.base,
        jurisdiction=args.jurisdiction,
        document_class=args.document_class,
        version=args.version,
        command=args.command,
        applied_files=applied_files,
        deleted_files=deleted_files,
        reasoning_logs=reasoning_logs,
    )
    manifest_path = write_signed_ingest_manifest(
        repo=repo,
        manifest=manifest,
        private_key=private_key,
        output=args.output,
        key_id=args.key_id,
    )
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "applied_files": len(manifest["applied_files"]),
                "reasoning_logs": len(manifest["reasoning_logs"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_guard_ingested(args: argparse.Namespace) -> int:
    result = guard_ingested_artifacts(
        repo=args.repo,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
    )
    if args.json:
        print(json.dumps(result.to_mapping(), indent=2, sort_keys=True))
    elif result.passed:
        if result.protected_changes:
            print("All changed corpus artifacts have signed ingest manifests.")
        else:
            print("No protected corpus artifact changes.")
    else:
        for issue in result.issues:
            print(issue)
    return 0 if result.passed else 1


def _cmd_verify_scope_tracked(args: argparse.Namespace) -> int:
    result = verify_scope_tracked(
        repo=args.repo,
        jurisdiction=args.jurisdiction,
        document_class=args.document_class,
        version=args.version,
    )
    if result.passed:
        print(
            f"Verified {result.files_verified} referenced files across "
            f"{result.scopes_checked} inventory scopes."
        )
        return 0
    for path in result.missing_paths:
        print(path)
    print(shlex.join(["git", "add", "-f", *result.missing_paths]))
    return 1


def _cmd_inventory_ecfr(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    run_id = ecfr_run_id(args.version, args.only_title, args.only_part, args.limit)
    inventory = build_ecfr_inventory(
        as_of=args.as_of,
        only_title=args.only_title,
        only_part=args.only_part,
        limit=args.limit,
        run_id=run_id,
    )
    out = store.inventory_path("us", DocumentClass.REGULATION, run_id)
    store.write_inventory(out, inventory.items)
    print(
        json.dumps(
            {
                "jurisdiction": "us",
                "document_class": DocumentClass.REGULATION.value,
                "version": args.version,
                "run_id": run_id,
                "as_of": args.as_of,
                "title_count": inventory.title_count,
                "part_count": inventory.part_count,
                "items_written": len(inventory.items),
                "unique_citation_count": inventory.unique_citation_count,
                "written_to": str(out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_inventory_usc(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    source_bytes = args.source_xml.read_bytes()
    xml_content = decode_uslm_bytes(source_bytes)
    title = args.title or infer_uslm_title(xml_content)
    try:
        allowed_citation_paths = _usc_allowed_citation_paths(
            title,
            sections=args.section,
            citation_paths=args.citation_path,
            include_title=args.include_title,
        )
    except ValueError as exc:
        print(str(exc))
        return 2
    run_id = usc_run_id(args.version, title, args.limit)
    inventory = build_usc_inventory_from_xml(
        xml_content,
        title=title,
        run_id=run_id,
        source_sha256=sha256_bytes(source_bytes),
        source_download_url=args.source_url,
        limit=args.limit,
        allowed_citation_paths=allowed_citation_paths,
    )
    out = store.inventory_path("us", DocumentClass.STATUTE, run_id)
    store.write_inventory(out, inventory.items)
    print(
        json.dumps(
            {
                "jurisdiction": "us",
                "document_class": DocumentClass.STATUTE.value,
                "version": args.version,
                "run_id": run_id,
                "title": title,
                "section_count": inventory.section_count,
                "items_written": len(inventory.items),
                "unique_citation_count": inventory.unique_citation_count,
                "written_to": str(out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _usc_allowed_citation_paths(
    title: str | int,
    *,
    sections: Iterable[str] | None = None,
    citation_paths: Iterable[str] | None = None,
    include_title: bool = False,
) -> set[str] | None:
    section_values = tuple(sections or ())
    citation_path_values = tuple(citation_paths or ())
    if not section_values and not citation_path_values:
        return None

    title_token = str(title).strip().lower().removeprefix("title ")
    allowed: set[str] = set()
    if include_title:
        allowed.add(f"us/statute/{title_token}")

    for section in section_values:
        allowed.add(_usc_section_citation_path(title_token, section))
    for citation_path in citation_path_values:
        normalized = citation_path.strip().strip("/")
        if not normalized.startswith("us/statute/"):
            raise ValueError(f"invalid US Code citation path: {citation_path!r}")
        allowed.add(normalized)
    return allowed


def _usc_section_citation_path(title: str, section: str) -> str:
    value = section.strip()
    if value.startswith("us/statute/"):
        return value.strip("/")
    match = re.fullmatch(
        r"(?:(?P<title>[0-9]+[a-z]?)\s+(?:U\.?S\.?C\.?|USC)\s+)?"
        r"(?:§+\s*)?(?P<section>[0-9A-Za-z][0-9A-Za-z.-]*)",
        value,
        re.I,
    )
    if not match:
        raise ValueError(f"invalid US Code section: {section!r}")
    section_title = (match.group("title") or title).lower()
    if section_title != title:
        raise ValueError(f"section {section!r} belongs to title {section_title}, not title {title}")
    return f"us/statute/{title}/{match.group('section')}"


def _cmd_export_supabase(args: argparse.Namespace) -> int:
    records = load_provisions(args.provisions)
    rows_written = write_supabase_rows_jsonl(args.output, records)
    print(
        json.dumps(
            {
                "rows_written": rows_written,
                "provisions": str(args.provisions),
                "output": str(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_generate_anchors(args: argparse.Namespace) -> int:
    """Generate the derived provision_anchors JSONL from asserted provisions.

    Rebuildable: reads provisions, parses the paragraph tree (or wraps stored
    block leaves), verifies every anchor's mechanical gates, and writes JSONL
    mirroring the provisions layout. Deterministic for a fixed input.
    """
    records = load_provisions(args.provisions)
    by_path = {record.citation_path: record for record in records}
    targets = list(args.target or [])
    stored_leaves = list(args.stored_leaf or [])
    if not targets and not stored_leaves:
        # Default: parse every provision in the file that has a body.
        targets = [r.citation_path for r in records if (r.body or "").strip()]

    anchors = []
    for citation_path in targets:
        record = by_path.get(citation_path)
        if record is None:
            print(
                f"error: target provision {citation_path!r} not found in "
                f"{args.provisions}",
                file=sys.stderr,
            )
            return 2
        anchors.extend(generate_anchors_for_provision(record))
    for citation_path in stored_leaves:
        record = by_path.get(citation_path)
        if record is None:
            print(
                f"error: stored-leaf provision {citation_path!r} not found in "
                f"{args.provisions}",
                file=sys.stderr,
            )
            return 2
        anchors.extend(generate_stored_leaf_anchors(record))

    # Re-verify the whole set against parent bodies before writing.
    verify_anchors_against_provisions(anchors, records)

    written = write_anchors_jsonl(args.output, anchors)
    confidence_split: dict[str, int] = {}
    for anchor in anchors:
        confidence_split[anchor.confidence] = (
            confidence_split.get(anchor.confidence, 0) + 1
        )
    print(
        json.dumps(
            {
                "command": "generate-anchors",
                "provisions": str(args.provisions),
                "output": str(args.output),
                "anchors_written": written,
                "confidence_split": confidence_split,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_resolve_anchor(args: argparse.Namespace) -> int:
    """Resolve a citation path to (provision_id, span) over an anchors artifact."""
    anchors = load_anchors(args.anchors)
    resolver = AnchorResolver(anchors)
    resolution = resolver.resolve(args.citation_path)
    if resolution is None:
        print(
            json.dumps(
                {
                    "citation_path": args.citation_path,
                    "resolved": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "citation_path": args.citation_path,
                "resolved": True,
                "match": resolution.match,
                "provision_id": resolution.provision_id,
                "parent_citation_path": resolution.parent_citation_path,
                "span": list(resolution.span),
                "text_head": resolution.text[:120],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_load_anchors_supabase(args: argparse.Namespace) -> int:
    """Upsert a provision_anchors JSONL artifact into Supabase (optional)."""
    anchors = load_anchors(args.anchors)
    if args.provisions:
        # Re-verify against provided parent provisions before loading.
        provisions = load_provisions(args.provisions)
        verify_anchors_against_provisions(anchors, provisions)
    service_key = ""
    if not args.dry_run:
        service_key = resolve_service_key(
            args.supabase_url,
            service_key_env=args.service_key_env,
            access_token_env=args.access_token_env,
        )
    report = load_anchors_to_supabase(
        anchors,
        service_key=service_key,
        supabase_url=args.supabase_url,
        chunk_size=args.chunk_size,
        dry_run=args.dry_run,
        progress_stream=sys.stderr,
    )
    payload = report.to_mapping()
    payload["anchors"] = str(args.anchors)
    payload["supabase_url"] = args.supabase_url
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_load_supabase(args: argparse.Namespace) -> int:
    # load_provisions returns () for a missing path; a load that
    # "succeeds" with zero rows because of a typoed path masks real
    # failures (a broken reload loop once reported 11 scopes OK while
    # loading nothing), so refuse explicitly.
    if not Path(args.provisions).exists():
        raise SystemExit(f"provisions file not found: {args.provisions}")
    records = load_provisions(args.provisions)
    if not records:
        raise SystemExit(f"provisions file has no records: {args.provisions}")
    service_key = ""
    if not args.dry_run:
        service_key = resolve_service_key(
            args.supabase_url,
            service_key_env=args.service_key_env,
            access_token_env=args.access_token_env,
        )
    replace_report = None
    if args.replace_scope:
        jurisdiction, document_class = _single_provision_scope(records)
        versions = sorted({record.version for record in records if record.version})
        if not versions or any(not record.version for record in records):
            raise SystemExit(
                "--replace-scope needs a version on every record so the delete "
                "can be limited to the loaded scope; this file has version-less "
                "records. Load without --replace-scope or backfill versions."
            )
        replace_report = delete_supabase_provisions_scope(
            jurisdiction=jurisdiction,
            document_class=document_class,
            versions=versions,
            service_key=service_key,
            supabase_url=args.supabase_url,
            dry_run=args.dry_run,
            progress_stream=sys.stderr,
        )
    report = load_provisions_to_supabase(
        records,
        service_key=service_key,
        supabase_url=args.supabase_url,
        chunk_size=args.chunk_size,
        dry_run=args.dry_run,
        progress_stream=sys.stderr,
    )
    payload: dict[str, Any] = report.to_mapping()
    if replace_report is not None:
        payload["replace_scope"] = replace_report.to_mapping()
    payload["provisions"] = str(args.provisions)
    payload["supabase_url"] = args.supabase_url

    if args.build_navigation and not args.dry_run and report.rows_loaded:
        navigation_records: list[ProvisionRecord] = []
        existing_navigation_statuses: dict[str, str] = {}
        release_scopes = _provision_release_scopes(records)
        if args.navigation_source == "local":
            navigation_records.extend(records)
        else:
            for jurisdiction, document_class, version in release_scopes:
                navigation_records.extend(
                    fetch_provisions_for_navigation(
                        service_key=service_key,
                        supabase_url=args.supabase_url,
                        jurisdiction=jurisdiction,
                        doc_type=document_class,
                        version=version,
                    )
                )
        for jurisdiction, document_class, version in release_scopes:
            if args.preserve_navigation_statuses:
                existing_navigation_statuses.update(
                    fetch_navigation_statuses(
                        service_key=service_key,
                        supabase_url=args.supabase_url,
                        jurisdiction=jurisdiction,
                        doc_type=document_class,
                        version=version,
                    )
                )
        encoded_paths = _resolve_encoded_paths(
            args, {jurisdiction for jurisdiction, _, _ in release_scopes}
        )
        nodes = build_navigation_nodes(
            _apply_navigation_status_overrides(
                navigation_records,
                existing_statuses=existing_navigation_statuses,
                overrides=records,
            ),
            encoded_paths=encoded_paths,
        )
        navigation_report = write_navigation_nodes_to_supabase(
            nodes,
            service_key=service_key,
            supabase_url=args.supabase_url,
            chunk_size=args.chunk_size,
            replace_scope=True,
            replace_scopes=release_scopes,
            dry_run=False,
            progress_stream=sys.stderr,
        )
        payload["navigation"] = navigation_report.to_mapping()
        payload["navigation"]["source"] = args.navigation_source
    elif args.build_navigation and args.dry_run:
        payload["navigation"] = {"skipped": "dry-run"}

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_snapshot_provision_counts(args: argparse.Namespace) -> int:
    service_key = resolve_service_key(
        args.supabase_url,
        service_key_env=args.service_key_env,
        access_token_env=args.access_token_env,
    )
    release_path = None
    if args.release:
        if args.base is None:
            raise ValueError("--base is required with --release")
        release_path = resolve_release_manifest_path(args.release)
        rows = fetch_release_provision_counts(
            ReleaseManifest.load(release_path),
            service_key=service_key,
            supabase_url=args.supabase_url,
        )
    else:
        rows = fetch_provision_counts(
            service_key=service_key,
            supabase_url=args.supabase_url,
            include_legacy=args.include_legacy,
        )
    payload: dict[str, object] = {"rows": list(rows)}
    if release_path is not None:
        payload["release_path"] = str(release_path)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        payload["written_to"] = str(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_backfill_versions(args: argparse.Namespace) -> int:
    """Chunked backfill of corpus.provisions.version and
    corpus.navigation_nodes.version for single-active release scopes.

    The original synchronous backfill timed out via the pooler's
    statement_timeout. This implementation calls a chunked RPC
    repeatedly until exhausted. Idempotent and resumable: rows that
    already have a version are not touched.
    """
    service_key = resolve_service_key(
        args.supabase_url,
        service_key_env=args.service_key_env,
        access_token_env=args.access_token_env,
    )

    scopes_to_process: tuple[dict[str, str], ...]
    if args.jurisdiction and args.doc_type and args.version:
        scopes_to_process = (
            {
                "jurisdiction": args.jurisdiction,
                "document_class": args.doc_type,
                "version": args.version,
            },
        )
    else:
        scopes_to_process = list_single_active_release_scopes(
            service_key=service_key,
            supabase_url=args.supabase_url,
        )
        if args.jurisdiction:
            scopes_to_process = tuple(
                s for s in scopes_to_process if s["jurisdiction"] == args.jurisdiction
            )
        if args.doc_type:
            scopes_to_process = tuple(
                s for s in scopes_to_process if s["document_class"] == args.doc_type
            )

    tables = ("provisions", "navigation_nodes") if not args.table else (args.table,)

    summary: list[dict[str, object]] = []
    for scope in scopes_to_process:
        for table in tables:
            total_updated = 0
            chunks = 0
            while True:
                if args.dry_run:
                    print(
                        f"DRY RUN: would backfill {table} for "
                        f"{scope['jurisdiction']}/{scope['document_class']} "
                        f"→ version={scope['version']}",
                        file=sys.stderr,
                    )
                    break
                updated = backfill_version_chunk(
                    jurisdiction=scope["jurisdiction"],
                    document_class=scope["document_class"],
                    version=scope["version"],
                    table_name=table,
                    chunk_size=args.chunk_size,
                    service_key=service_key,
                    supabase_url=args.supabase_url,
                    progress_stream=sys.stderr,
                )
                chunks += 1
                total_updated += updated
                if updated > 0:
                    print(
                        f"  {scope['jurisdiction']}/{scope['document_class']}/{table}: "
                        f"chunk {chunks} → {updated} rows (running total {total_updated})",
                        file=sys.stderr,
                        flush=True,
                    )
                if updated < args.chunk_size:
                    break
            summary.append(
                {
                    "jurisdiction": scope["jurisdiction"],
                    "document_class": scope["document_class"],
                    "version": scope["version"],
                    "table": table,
                    "rows_updated": total_updated,
                    "chunks": chunks,
                    "dry_run": args.dry_run,
                }
            )

    print(
        json.dumps(
            {
                "scopes_processed": len(scopes_to_process),
                "dry_run": args.dry_run,
                "results": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_verify_release_coverage(args: argparse.Namespace) -> int:
    service_key = resolve_service_key(
        args.supabase_url,
        service_key_env=args.service_key_env,
        access_token_env=args.access_token_env,
    )
    report = verify_release_coverage(
        service_key=service_key,
        supabase_url=args.supabase_url,
    )
    print(json.dumps(report.to_mapping(), indent=2, sort_keys=True))
    return 0 if report.ok else 2


def _cmd_build_navigation_index(args: argparse.Namespace) -> int:
    if args.all and not args.provisions and not args.from_supabase:
        raise SystemExit("build-navigation-index --all requires --provisions or --from-supabase")
    if not args.provisions and not args.from_supabase:
        raise SystemExit("build-navigation-index requires --provisions, --from-supabase, or --all")

    will_write_supabase = not args.skip_supabase and not args.dry_run
    service_key = ""
    if will_write_supabase or args.from_supabase:
        service_key = resolve_service_key(
            args.supabase_url,
            service_key_env=args.service_key_env,
            access_token_env=args.access_token_env,
        )

    records: tuple[ProvisionRecord, ...]
    existing_navigation_statuses: dict[str, str] = {}
    if args.provisions:
        loaded: list[ProvisionRecord] = []
        for path in args.provisions:
            loaded.extend(load_provisions(path))
        records = tuple(loaded)
        sources_used = [str(path) for path in args.provisions]
        # Preserve manually-set statuses from the live nav table when we are
        # going to write back, so a rebuild from a partial JSONL does not wipe
        # them. Fetch is scoped per release scope to avoid pulling rows for
        # unrelated jurisdictions, document classes, or versions.
        if will_write_supabase and args.preserve_statuses:
            for jurisdiction, document_class, version in _provision_release_scopes(records):
                existing_navigation_statuses.update(
                    fetch_navigation_statuses(
                        service_key=service_key,
                        supabase_url=args.supabase_url,
                        jurisdiction=jurisdiction,
                        doc_type=document_class,
                        version=version,
                    )
                )
    else:
        records = fetch_provisions_for_navigation(
            service_key=service_key,
            supabase_url=args.supabase_url,
            jurisdiction=args.jurisdiction,
            doc_type=args.doc_type,
            version=args.version,
        )
        if args.preserve_statuses:
            existing_navigation_statuses = fetch_navigation_statuses(
                service_key=service_key,
                supabase_url=args.supabase_url,
                jurisdiction=args.jurisdiction,
                doc_type=args.doc_type,
                version=args.version,
            )
        sources_used = [f"supabase:{args.supabase_url}"]

    encoded_jurisdictions = (
        {args.jurisdiction} if args.jurisdiction else {r.jurisdiction for r in records}
    )
    encoded_paths = _resolve_encoded_paths(args, encoded_jurisdictions)

    nodes: tuple[NavigationNode, ...] = build_navigation_nodes(
        _apply_navigation_status_overrides(
            records,
            existing_statuses=existing_navigation_statuses,
            overrides=records if args.provisions else (),
        ),
        jurisdiction=args.jurisdiction,
        document_class=args.doc_type,
        encoded_paths=encoded_paths,
    )

    payload: dict[str, object] = {
        "nodes_built": len(nodes),
        "provisions_input": len(records),
        "jurisdiction": args.jurisdiction,
        "doc_type": args.doc_type,
        "sources": sources_used,
        "preserved_status_count": len(existing_navigation_statuses),
        "encoded_paths_seen": len(encoded_paths),
        "nodes_with_rulespec": sum(1 for n in nodes if n.has_rulespec),
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            "\n".join(json.dumps(node.to_supabase_row(), sort_keys=True) for node in nodes)
            + ("\n" if nodes else "")
        )
        payload["written_to"] = str(args.output)

    if args.skip_supabase:
        payload["skipped_supabase"] = True
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    replace_scope = _build_navigation_replace_scope(args)
    write_report = write_navigation_nodes_to_supabase(
        nodes,
        service_key=service_key,
        supabase_url=args.supabase_url,
        chunk_size=args.chunk_size,
        replace_scope=replace_scope,
        replace_scopes=_explicit_navigation_replace_scopes(args),
        dry_run=args.dry_run,
        progress_stream=sys.stderr,
    )
    payload["supabase"] = write_report.to_mapping()
    payload["supabase_url"] = args.supabase_url
    payload["replace_scope"] = replace_scope
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _provision_scopes(records: tuple[ProvisionRecord, ...]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted({(record.jurisdiction, record.document_class) for record in records}))


def _provision_release_scopes(
    records: tuple[ProvisionRecord, ...],
) -> tuple[tuple[str, str, str | None], ...]:
    return tuple(
        sorted(
            {(record.jurisdiction, record.document_class, record.version) for record in records},
            key=lambda scope: (scope[0], scope[1], scope[2] or ""),
        )
    )


def _explicit_navigation_replace_scopes(
    args: argparse.Namespace,
) -> tuple[tuple[str, str, str | None], ...]:
    if args.jurisdiction and args.doc_type:
        return ((args.jurisdiction, args.doc_type, args.version),)
    return ()


def _build_navigation_replace_scope(args: argparse.Namespace) -> bool:
    if args.replace_scope is not None:
        return bool(args.replace_scope)
    return bool(args.from_supabase)


def _resolve_encoded_paths(
    args: argparse.Namespace,
    jurisdictions: Iterable[str],
) -> set[str]:
    """Combine ``--rulespec-repo`` and ``--rulespec-root`` flags into a set of
    canonical encoded citation paths for the given jurisdictions.

    ``--rulespec-repo`` is a repeatable explicit checkout, paired with the
    jurisdiction(s) it covers — a legacy per-jurisdiction repo covers one
    jurisdiction, a country monorepo covers every jurisdiction directory it
    holds. ``--rulespec-root`` points at a directory holding ``rulespec-*``
    checkouts and resolves each jurisdiction in the monorepo layout first,
    then the legacy sibling layout. ``--rulespec-auto`` (the default) silently
    runs the same resolution against the directory next to this corpus
    checkout. Empty when no repo is on disk for any input jurisdiction.
    """
    encoded: set[str] = set()
    juris_list = sorted({j for j in jurisdictions if j})

    repos: list[tuple[str, Path]] = []
    for repo_arg in args.rulespec_repo or []:
        repo_path = Path(repo_arg)
        # Infer the jurisdiction(s) from the repo dir name and contents
        # (rulespec-us-co -> us-co; a rulespec-us monorepo -> us, us-ca, ...).
        repo_jurisdictions = _jurisdictions_for_repo_checkout(repo_path)
        if not repo_jurisdictions:
            print(
                f"warning: cannot infer jurisdiction from rulespec repo path {repo_path}",
                file=sys.stderr,
            )
            continue
        repos.extend((repo_juris, repo_path) for repo_juris in repo_jurisdictions)

    if args.rulespec_root:
        root_paths = [Path(p) for p in args.rulespec_root]
        for root in root_paths:
            for j, paths in discover_encoded_paths_for_jurisdictions(root, juris_list).items():
                encoded.update(paths)
                # Mark the repo seen so --rulespec-auto doesn't double-count.
                resolved = resolve_jurisdiction_dir(root, j)
                if resolved is not None:
                    repos.append((j, resolved))

    if args.rulespec_auto:
        # Auto-discover rulespec-* checkouts next to this corpus repo, in
        # either layout (monorepo jurisdiction dir first, legacy sibling next).
        sibling_root = Path.cwd().parent
        for j in juris_list:
            resolved = resolve_jurisdiction_dir(sibling_root, j)
            if resolved is None:
                continue
            if any(p.exists() and p.samefile(resolved) for _, p in repos):
                continue
            repos.append((j, resolved))

    for j, repo_path in repos:
        encoded.update(discover_encoded_paths(repo_path, j))
    return encoded


def _jurisdictions_for_repo_checkout(repo_path: Path) -> list[str]:
    """Return the jurisdictions whose encodings live inside a checkout.

    A legacy checkout name (``rulespec-us-co``) maps to its single
    jurisdiction. A country monorepo checkout (``rulespec-us``) additionally
    covers every known jurisdiction with a directory inside it
    (``us/``, ``us-ca/``, ...).
    """
    name = repo_path.name
    jurisdictions = [
        jurisdiction for jurisdiction, repo_dir in JURISDICTION_REPO_MAP.items() if repo_dir == name
    ]
    for jurisdiction in JURISDICTION_REPO_MAP:
        if jurisdiction in jurisdictions:
            continue
        if monorepo_dir_name_for_jurisdiction(jurisdiction) != name:
            continue
        prefix = repo_prefix_for_jurisdiction(jurisdiction)
        if prefix is not None and (repo_path / prefix).is_dir():
            jurisdictions.append(jurisdiction)
    return jurisdictions


def _apply_navigation_status_overrides(
    records: Iterable[ProvisionRecord],
    *,
    existing_statuses: dict[str, str] | None = None,
    overrides: Iterable[ProvisionRecord],
) -> tuple[ProvisionRecord, ...]:
    """Inject curated navigation statuses onto a stream of provision records.

    Statuses are editorial metadata that don't live in `corpus.provisions`;
    extractors typically leave `metadata.status` unset. To keep manually
    curated statuses across rebuilds we resolve each record's status as:

    * If a record in ``overrides`` has a non-empty ``metadata.status`` it
      wins. Re-extracted source records can therefore introduce or change a
      status without colliding with curated state.
    * Otherwise we fall back to ``existing_statuses`` (typically a snapshot
      of the live `corpus.navigation_nodes.status` column).
    * Otherwise the record's own ``metadata.status`` (if any) is left alone.

    A ``None`` override is treated as "no opinion" rather than "clear" so
    that fresh source data doesn't accidentally wipe curated statuses.
    """
    overrides_with_status: dict[str, str] = {}
    for record in overrides:
        status = _navigation_status(record)
        if status is not None:
            overrides_with_status[record.citation_path] = status
    resolved: dict[str, str] = dict(existing_statuses or {})
    resolved.update(overrides_with_status)
    if not resolved:
        return tuple(records)
    updated: list[ProvisionRecord] = []
    for record in records:
        target = resolved.get(record.citation_path)
        if target is None:
            updated.append(record)
            continue
        if _navigation_status(record) == target:
            updated.append(record)
            continue
        metadata = dict(record.metadata or {})
        metadata["status"] = target
        updated.append(replace(record, metadata=metadata))
    return tuple(updated)


def _navigation_status(record: ProvisionRecord) -> str | None:
    if not record.metadata:
        return None
    status = record.metadata.get("status")
    if isinstance(status, str) and status.strip():
        return status.strip()
    return None


def _single_provision_scope(records: tuple[ProvisionRecord, ...]) -> tuple[str, str]:
    jurisdictions = {record.jurisdiction for record in records}
    document_classes = {record.document_class for record in records}
    if len(jurisdictions) != 1 or len(document_classes) != 1:
        raise ValueError("replace-scope requires one jurisdiction and one document class")
    return str(next(iter(jurisdictions))), str(next(iter(document_classes)))


def _cmd_extract_ecfr(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date or args.as_of)
    graphic_transcriptions = (
        load_ecfr_graphic_transcriptions(args.graphic_transcriptions)
        if args.graphic_transcriptions
        else None
    )
    report = extract_ecfr(
        store,
        version=args.version,
        as_of=args.as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        only_part=args.only_part,
        limit=args.limit,
        workers=args.workers,
        progress_stream=sys.stderr,
        graphic_transcriptions=graphic_transcriptions,
    )
    print(
        json.dumps(
            {
                "jurisdiction": "us",
                "document_class": DocumentClass.REGULATION.value,
                "version": args.version,
                "as_of": args.as_of,
                "title_count": report.title_count,
                "part_count": report.part_count,
                "title_error_count": report.title_error_count,
                "title_errors": list(report.title_errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if graphic_transcriptions and report.title_error_count:
        return 2
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_usc(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    try:
        allowed_citation_paths = _usc_allowed_citation_paths(
            args.title or infer_uslm_title(decode_uslm_bytes(args.source_xml.read_bytes())),
            sections=args.section,
            citation_paths=args.citation_path,
            include_title=args.include_title,
        )
    except ValueError as exc:
        print(str(exc))
        return 2
    report = extract_usc(
        store,
        version=args.version,
        source_xml=args.source_xml,
        title=args.title,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        source_download_url=args.source_url,
        limit=args.limit,
        allowed_citation_paths=allowed_citation_paths,
    )
    print(
        json.dumps(
            {
                "jurisdiction": "us",
                "document_class": DocumentClass.STATUTE.value,
                "version": args.version,
                "title": report.title,
                "title_count": report.title_count,
                "section_count": report.section_count,
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_usc_dir(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_usc_directory(
        store,
        version=args.version,
        source_dir=args.source_dir,
        only_title=args.only_title,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        source_download_url=args.source_url,
        limit=args.limit,
    )
    print(
        json.dumps(
            {
                "jurisdiction": "us",
                "document_class": DocumentClass.STATUTE.value,
                "version": args.version,
                "run_title": report.title,
                "title_count": report.title_count,
                "section_count": report.section_count,
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_uk_legislation(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_uk_legislation_sections(
        store,
        version=args.version,
        source_xmls=tuple(args.source_xml or ()),
        citations=tuple(args.citation or ()),
        source=args.source,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        lex_limit=args.lex_limit,
    )
    print(json.dumps(_uk_legislation_report_json(report), indent=2, sort_keys=True))
    return (
        0
        if all(class_report.coverage.complete for class_report in report.class_reports)
        or args.allow_incomplete
        else 2
    )


def _uk_legislation_report_json(report: UKLegislationExtractReport) -> dict[str, Any]:
    return {
        "jurisdiction": "uk",
        "version": report.version,
        "source_count": report.source_count,
        "provisions_written": report.provisions_written,
        "classes": [
            {
                "document_class": class_report.document_class,
                "source_file_count": len(class_report.source_paths),
                "provisions_written": class_report.provisions_written,
                "inventory_path": str(class_report.inventory_path),
                "provisions_path": str(class_report.provisions_path),
                "coverage_path": str(class_report.coverage_path),
                "coverage_complete": class_report.coverage.complete,
                "source_count": class_report.coverage.source_count,
                "provision_count": class_report.coverage.provision_count,
                "matched_count": class_report.coverage.matched_count,
                "missing_count": len(class_report.coverage.missing_from_provisions),
                "extra_count": len(class_report.coverage.extra_provisions),
            }
            for class_report in report.class_reports
        ],
    }


def _cmd_extract_nz_legislation(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_nz_legislation(
        store,
        version=args.version,
        source_xmls=tuple(args.source_xml or ()),
        source_dir=args.source_dir,
        source_pattern=args.source_pattern,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        limit=args.limit,
    )
    print(json.dumps(_nz_legislation_report_json(report), indent=2, sort_keys=True))
    return (
        0
        if all(class_report.coverage.complete for class_report in report.class_reports)
        or args.allow_incomplete
        else 2
    )


def _nz_legislation_report_json(report: NZLegislationExtractReport) -> dict[str, Any]:
    return {
        "jurisdiction": "nz",
        "version": report.version,
        "source_count": report.source_count,
        "provisions_written": report.provisions_written,
        "classes": [
            {
                "document_class": class_report.document_class,
                "source_file_count": len(class_report.source_paths),
                "provisions_written": class_report.provisions_written,
                "inventory_path": str(class_report.inventory_path),
                "provisions_path": str(class_report.provisions_path),
                "coverage_path": str(class_report.coverage_path),
                "coverage_complete": class_report.coverage.complete,
                "source_count": class_report.coverage.source_count,
                "provision_count": class_report.coverage.provision_count,
                "matched_count": class_report.coverage.matched_count,
                "missing_count": len(class_report.coverage.missing_from_provisions),
                "extra_count": len(class_report.coverage.extra_provisions),
            }
            for class_report in report.class_reports
        ],
    }


def _cmd_extract_belgian_eli(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    source_urls = list(args.source_url or ())
    source_jurisdiction_overrides: dict[str, str] = {}
    if args.manifest:
        manifest = CorpusManifest.load(args.manifest)
        manifest.require_unique_sources()
        unsupported = sorted(
            {source.adapter for source in manifest.sources if source.adapter != "belgian-eli"}
        )
        if unsupported:
            raise ValueError(
                "extract-belgian-eli only supports belgian-eli manifest sources; "
                f"found {', '.join(unsupported)}"
            )
        source_urls.extend(source.source_url for source in manifest.sources if source.source_url)
        source_jurisdiction_overrides.update(
            {
                source.source_url: source.jurisdiction
                for source in manifest.sources
                if source.source_url
            }
        )
    report = extract_belgian_eli(
        store,
        version=args.version,
        source_htmls=tuple(args.source_html or ()),
        source_dir=args.source_dir,
        source_pattern=args.source_pattern,
        source_urls=tuple(source_urls),
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        request_timeout=args.request_timeout,
        limit=args.limit,
        source_jurisdiction_overrides=source_jurisdiction_overrides,
    )
    print(json.dumps(_belgian_eli_report_json(report), indent=2, sort_keys=True))
    return (
        0
        if all(class_report.coverage.complete for class_report in report.class_reports)
        or args.allow_incomplete
        else 2
    )


def _belgian_eli_report_json(report: BelgianELIExtractReport) -> dict[str, Any]:
    return {
        "version": report.version,
        "source_count": report.source_count,
        "provisions_written": report.provisions_written,
        "classes": [
            {
                "jurisdiction": class_report.jurisdiction,
                "document_class": class_report.document_class,
                "source_file_count": len(class_report.source_paths),
                "provisions_written": class_report.provisions_written,
                "inventory_path": str(class_report.inventory_path),
                "provisions_path": str(class_report.provisions_path),
                "coverage_path": str(class_report.coverage_path),
                "coverage_complete": class_report.coverage.complete,
                "source_count": class_report.coverage.source_count,
                "provision_count": class_report.coverage.provision_count,
                "matched_count": class_report.coverage.matched_count,
                "missing_count": len(class_report.coverage.missing_from_provisions),
                "extra_count": len(class_report.coverage.extra_provisions),
            }
            for class_report in report.class_reports
        ],
    }


def _cmd_extract_de_gii(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    laws: list[GermanLaw] = []
    for xml_path in args.source_xml or ():
        laws.append(GermanLaw(slug=Path(xml_path).stem, local_source=Path(xml_path)))
    if args.source_dir:
        for path in sorted(Path(args.source_dir).glob("*")):
            if path.suffix.lower() in {".xml", ".zip"}:
                laws.append(GermanLaw(slug=path.stem, local_source=path))
    report = extract_german_gii(
        store,
        version=args.version,
        laws=tuple(laws),
        manifest=args.manifest,
        source_as_of=args.source_as_of,
        expression_date=args.expression_date,
        request_timeout=args.request_timeout,
        limit=args.limit,
    )
    print(json.dumps(_de_gii_report_json(report), indent=2, sort_keys=True))
    return (
        0
        if all(scope.coverage.complete for scope in report.scope_reports) or args.allow_incomplete
        else 2
    )


def _de_gii_report_json(report: GermanGiiExtractReport) -> dict[str, Any]:
    return {
        "version": report.version,
        "source_count": report.source_count,
        "provisions_written": report.provisions_written,
        "scopes": [
            {
                "jurisdiction": scope.jurisdiction,
                "document_class": scope.document_class,
                "law_count": scope.law_count,
                "source_file_count": len(scope.source_paths),
                "provisions_written": scope.provisions_written,
                "inventory_path": str(scope.inventory_path),
                "provisions_path": str(scope.provisions_path),
                "coverage_path": str(scope.coverage_path),
                "complete": scope.coverage.complete,
                "source_count": scope.coverage.source_count,
                "provision_count": scope.coverage.provision_count,
                "matched_count": scope.coverage.matched_count,
                "missing_count": len(scope.coverage.missing_from_provisions),
                "extra_count": len(scope.coverage.extra_provisions),
            }
            for scope in report.scope_reports
        ],
    }


def _cmd_discover_belgian_moniteur(args: argparse.Namespace) -> int:
    report = discover_belgian_moniteur_sources(
        start_date=args.start_date,
        end_date=args.end_date,
        language=args.language,
        request_timeout=args.request_timeout,
        limit=args.limit,
        max_editions=args.max_editions,
    )
    if args.manifest_output:
        _write_belgian_moniteur_manifest(
            args.manifest_output,
            report=report,
            version=args.version,
        )
    print(json.dumps(_belgian_moniteur_discovery_json(report), indent=2, sort_keys=True))
    return 0


def _belgian_moniteur_discovery_json(
    report: BelgianMoniteurDiscoveryReport,
) -> dict[str, Any]:
    return {
        "start_date": report.start_date,
        "end_date": report.end_date,
        "language": report.language,
        "summary_pages_fetched": report.summary_pages_fetched,
        "source_count": len(report.sources),
        "sources": [
            {
                "source_id": source.source_id,
                "source_url": source.source_url,
                "jurisdiction": source.jurisdiction,
                "document_class": source.document_class,
                "document_type": source.document_type,
                "numac": source.numac,
                "title": source.title,
                "publication_date": source.publication_date,
                "edition": source.edition,
                "section_title": source.section_title,
                "moniteur_url": source.moniteur_url,
                "justel_url": source.justel_url,
                "authority": source.authority,
            }
            for source in report.sources
        ],
    }


def _write_belgian_moniteur_manifest(
    path: Path,
    *,
    report: BelgianMoniteurDiscoveryReport,
    version: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": version,
        "sources": [
            {
                "source_id": source.source_id,
                "jurisdiction": source.jurisdiction,
                "document_class": source.document_class,
                "adapter": "belgian-eli",
                "source_url": source.source_url,
                "metadata": {
                    "source_authority": "Moniteur belge / Belgisch Staatsblad",
                    "source_status": "official_original_publication",
                    "source_family": "full-belgian-statutes-regulations",
                    "publication_date": source.publication_date,
                    "edition": source.edition,
                    "section_title": source.section_title,
                    "document_type": source.document_type,
                    "numac": source.numac,
                    "title": source.title,
                    "legal_authority_url": source.moniteur_url,
                    "justel_url": source.justel_url,
                    "issuing_authority": source.authority,
                },
            }
            for source in report.sources
        ],
    }
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
    )


def _cmd_download_nz_legislation_api(args: argparse.Namespace) -> int:
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise ValueError(f"{args.api_key_env} is required")
    report = download_nz_legislation_api_sources(
        args.output_dir,
        api_key=api_key,
        legislation_types=tuple(args.legislation_type or NZ_LEGISLATION_DEFAULT_TYPES),
        publisher=args.publisher,
        search_term=args.search_term,
        per_page=args.per_page,
        max_pages=args.max_pages,
        limit=args.limit,
        resume=not args.no_resume,
        allow_failures=args.allow_failures,
        workers=args.workers,
        manifest_path=args.manifest_path,
    )
    print(json.dumps(_nz_legislation_api_download_report_json(report), indent=2, sort_keys=True))
    return 0 if report.failed_count == 0 or args.allow_failures else 2


def _nz_legislation_api_download_report_json(
    report: NZLegislationAPIDownloadReport,
) -> dict[str, Any]:
    return {
        "jurisdiction": "nz",
        "output_dir": str(report.output_dir),
        "discovered_count": report.discovered_count,
        "downloaded_count": report.downloaded_count,
        "skipped_count": report.skipped_count,
        "failed_count": report.failed_count,
        "manifest_path": str(report.manifest_path) if report.manifest_path else None,
        "downloaded_paths": [str(path) for path in report.downloaded_paths],
        "skipped_paths": [str(path) for path in report.skipped_paths],
        "failures": list(report.failures),
    }


def _cmd_extract_dc_code(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_dc_code(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": DocumentClass.STATUTE.value,
                "version": args.version,
                "title_count": report.title_count,
                "container_count": report.container_count,
                "section_count": report.section_count,
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_cic_html(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_cic_html_release(
        store,
        jurisdiction=args.jurisdiction,
        version=args.version,
        release_dir=args.release_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": DocumentClass.STATUTE.value,
                "version": args.version,
                "title_count": report.title_count,
                "container_count": report.container_count,
                "section_count": report.section_count,
                "skipped_source_count": report.skipped_source_count,
                "error_count": len(report.errors),
                "errors": list(report.errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_cic_odt(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_cic_odt_release(
        store,
        jurisdiction=args.jurisdiction,
        version=args.version,
        release_dir=args.release_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": DocumentClass.STATUTE.value,
                "version": args.version,
                "title_count": report.title_count,
                "container_count": report.container_count,
                "section_count": report.section_count,
                "skipped_source_count": report.skipped_source_count,
                "error_count": len(report.errors),
                "errors": list(report.errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_colorado_docx(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_colorado_docx_release(
        store,
        version=args.version,
        release_dir=args.release_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": DocumentClass.STATUTE.value,
                "version": args.version,
                "title_count": report.title_count,
                "container_count": report.container_count,
                "section_count": report.section_count,
                "skipped_source_count": report.skipped_source_count,
                "error_count": len(report.errors),
                "errors": list(report.errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_texas_tcas(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_texas_tcas(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        workers=args.workers,
        download_dir=args.download_dir,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-tx-statutes",
                adapter="texas-tcas",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_ohio_revised_code(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_ohio_revised_code(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        download_dir=args.download_dir,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-oh-revised-code",
                adapter="ohio-revised-code",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_minnesota_statutes(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_minnesota_statutes(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        workers=args.workers,
        download_dir=args.download_dir,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-mn-statutes",
                adapter="minnesota-statutes",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_nebraska_revised_statutes(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_nebraska_revised_statutes(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        workers=args.workers,
        download_dir=args.download_dir,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-ne-revised-statutes",
                adapter="nebraska-revised-statutes",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_washington_rcw(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_washington_rcw(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        workers=args.workers,
        download_dir=args.download_dir,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-wa-rcw",
                adapter="washington-rcw",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_illinois_ilcs(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_illinois_ilcs(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_chapter=args.only_chapter,
        only_act=args.only_act,
        limit=args.limit,
        workers=args.workers,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-il-ilcs",
                adapter="illinois-ilcs",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_indiana_code(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_indiana_code(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_zip=args.source_zip,
        source_year=args.source_year,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        download_dir=args.download_dir,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-in-code",
                adapter="indiana-code",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_canada_acts(args: argparse.Namespace) -> int:
    from axiom_corpus.corpus.canada import extract_canada_acts

    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    only_acts = tuple(args.only_act) if args.only_act else None
    report = extract_canada_acts(
        store,
        version=args.version,
        only_acts=only_acts,
        limit_acts=args.limit_acts,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": args.version,
                "act_count": report.act_count,
                "section_count": report.section_count,
                "subsection_count": report.subsection_count,
                "skipped_act_count": report.skipped_act_count,
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
                "errors": list(report.errors[:20]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_montana_code(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_montana_code(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_year=args.source_year,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        workers=args.workers,
        download_dir=args.download_dir,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-mt-code",
                adapter="montana-code",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_nevada_nrs(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_nevada_nrs(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_year=args.source_year,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        only_chapter=args.only_chapter,
        limit=args.limit,
        workers=args.workers,
        download_dir=args.download_dir,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-nv-nrs",
                adapter="nevada-nrs",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_new_york_consolidated_laws(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_new_york_consolidated_laws(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        workers=args.workers,
        download_dir=args.download_dir,
        request_delay_seconds=args.request_delay_seconds,
        timeout_seconds=args.timeout_seconds,
        request_attempts=args.request_attempts,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-ny-consolidated-laws",
                adapter="new-york-consolidated-laws",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if _state_statute_report_success(report) or args.allow_incomplete else 2


def _cmd_extract_new_york_openleg_api(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
    report = extract_new_york_openleg_api(
        store,
        version=args.version,
        api_key=api_key,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        download_dir=args.download_dir,
        api_base_url=args.api_base_url,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-ny-openleg-api",
                adapter="new-york-openleg-api",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if _state_statute_report_success(report) or args.allow_incomplete else 2


def _cmd_extract_new_york_openleg_sections(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
    report = extract_new_york_openleg_sections(
        store,
        version=args.version,
        sections=tuple(args.section),
        api_key=api_key,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        download_dir=args.download_dir,
        api_base_url=args.api_base_url,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-ny-openleg-sections",
                adapter="new-york-openleg-sections",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if _state_statute_report_success(report) or args.allow_incomplete else 2


def _cmd_extract_nyc_admin_code(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_nyc_admin_code(
        store,
        version=args.version,
        sections=tuple(args.section) if args.section is not None else None,
        urls=tuple(args.url) if args.url is not None else None,
        source_dir=args.source_dir,
        download_dir=args.download_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        timeout_seconds=args.timeout_seconds,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-ny-nyc-admin-code",
                adapter="nyc-admin-code",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if _state_statute_report_success(report) or args.allow_incomplete else 2


def _cmd_extract_delaware_code(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_delaware_code(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        only_chapter=args.only_chapter,
        limit=args.limit,
        workers=args.workers,
        download_dir=args.download_dir,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-de-code",
                adapter="delaware-code",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_oregon_ors(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_oregon_ors(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_year=args.source_year,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        only_chapter=args.only_chapter,
        limit=args.limit,
        workers=args.workers,
        download_dir=args.download_dir,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-or-ors",
                adapter="oregon-ors",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_rhode_island_general_laws(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_rhode_island_general_laws(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_year=args.source_year,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        only_chapter=args.only_chapter,
        limit=args.limit,
        workers=args.workers,
        download_dir=args.download_dir,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-ri-general-laws",
                adapter="rhode-island-general-laws",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_california_codes_bulk(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_california_codes_bulk(
        store,
        version=args.version,
        source_zip=args.source_zip,
        source_url=args.source_url,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        download_dir=args.download_dir,
        include_inactive=args.include_inactive,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-ca-codes",
                adapter="california-codes-bulk",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_california_code_sections(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_california_code_sections(
        store,
        version=args.version,
        sections=tuple(args.section),
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        download_dir=args.download_dir,
        request_delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        request_attempts=args.request_attempts,
    )
    print(
        json.dumps(
            _state_statute_report_payload(
                report,
                source_id="us-ca-code-sections",
                adapter="california-code-sections",
                version=args.version,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_state_statutes(args: argparse.Namespace) -> int:
    manifest_path = args.manifest
    manifest = CorpusManifest.load(manifest_path)
    manifest.require_unique_sources()
    store = CorpusArtifactStore(args.base)
    selected = [
        source
        for source in manifest.sources
        if source.document_class == DocumentClass.STATUTE.value
        and (not args.only_jurisdiction or source.jurisdiction in args.only_jurisdiction)
        and (not args.only_source_id or source.source_id in args.only_source_id)
    ]
    if not selected:
        print(
            json.dumps(
                {
                    "ok": False,
                    "version": manifest.version,
                    "source_count": 0,
                    "error": "no matching statute sources",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    if args.dry_run:
        plan_rows = [
            _state_statute_plan_payload(
                source,
                manifest_path=manifest_path,
                manifest_version=manifest.version,
                limit_override=args.limit_per_source,
            )
            for source in selected
        ]
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "version": manifest.version,
                    "source_count": len(plan_rows),
                    "rows": plan_rows,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if all(row["source_path_exists"] for row in plan_rows) else 1

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for source in selected:
        try:
            report = _extract_state_statute_source(
                store,
                manifest_path=manifest_path,
                manifest_version=manifest.version,
                source=source,
                limit_override=args.limit_per_source,
            )
        except Exception as exc:
            failures.append(
                {
                    "source_id": source.source_id,
                    "jurisdiction": source.jurisdiction,
                    "adapter": source.adapter,
                    "error": str(exc),
                }
            )
            continue
        rows.append(
            _state_statute_report_payload(
                report,
                source_id=source.source_id,
                adapter=source.adapter,
                version=source.version or manifest.version,
            )
        )

    coverage_complete = bool(rows) and all(row["coverage_complete"] for row in rows)
    successful = bool(rows) and all(_state_statute_row_success(row) for row in rows)
    payload = {
        "version": manifest.version,
        "source_count": len(selected),
        "completed_count": len(rows),
        "failed_count": len(failures),
        "coverage_complete": coverage_complete,
        "successful": successful,
        "provisions_written": sum(int(row["provisions_written"]) for row in rows),
        "rows": rows,
        "failures": failures,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if failures:
        return 1
    return 0 if successful or args.allow_incomplete else 2


def _extract_state_statute_source(
    store: CorpusArtifactStore,
    *,
    manifest_path: Path,
    manifest_version: str,
    source: CorpusSource,
    limit_override: int | None,
) -> StateStatuteExtractReport:
    options = _state_source_options(source)
    adapter = _canonical_state_statute_adapter(source.adapter)
    version = source.version or manifest_version
    source_as_of = _optional_text(options.get("source_as_of"))
    expression_date = _optional_text(options.get("expression_date"))
    only_title = _optional_text(options.get("only_title"))
    limit = limit_override if limit_override is not None else _optional_int(options.get("limit"))
    if adapter == "alabama-code":
        return extract_alabama_code(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            graphql_url=_optional_text(options.get("graphql_url"))
            or "https://alison.legislature.state.al.us/graphql",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.05,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 90.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            page_size=_optional_int(options.get("page_size")) or 1000,
        )
    if adapter == "alaska-statutes":
        return extract_alaska_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_year=_optional_int(options.get("source_year")) or ALASKA_STATUTES_DEFAULT_YEAR,
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url"))
            or "https://www.akleg.gov/basis/statutes.asp",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.05,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 30.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            workers=_optional_int(options.get("workers")) or 1,
        )
    if adapter == "arizona-revised-statutes":
        return extract_arizona_revised_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url")) or "https://www.azleg.gov",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.03,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 30.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            workers=_optional_int(options.get("workers")) or 8,
        )
    if adapter == "colorado-revised-statutes":
        return extract_colorado_revised_statutes(
            store,
            version=version,
            title=_optional_text(options.get("title")) or "39",
            edition=_optional_text(options.get("edition")) or "2025",
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_article=_optional_text(options.get("only_article")),
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url")) or "https://olls.info/crs/",
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 120.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 1.0,
        )
    if adapter == "connecticut-statutes":
        return extract_connecticut_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            current_base_url=_optional_text(options.get("current_base_url"))
            or "https://www.cga.ct.gov/current/pub/",
            supplement_base_url=_optional_text(options.get("supplement_base_url"))
            or "https://www.cga.ct.gov/2026/sup/",
            include_supplement=_optional_bool(options.get("include_supplement"), default=True),
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.05,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            verify_ssl=_optional_bool(options.get("verify_ssl"), default=True),
        )
    if adapter == "florida-statutes":
        return extract_florida_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_year=_optional_int(options.get("source_year")) or FLORIDA_STATUTES_DEFAULT_YEAR,
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            source_zip=_optional_manifest_path(manifest_path, options, "source_zip"),
            source_zip_url=_optional_text(options.get("source_zip_url")),
            base_url=_optional_text(options.get("base_url"))
            or "https://www.leg.state.fl.us/statutes/",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.05,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "hawaii-revised-statutes":
        return extract_hawaii_revised_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url"))
            or "https://data.capitol.hawaii.gov/hrscurrent/",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.02,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            workers=_optional_int(options.get("workers")) or 8,
        )
    if adapter == "kansas-statutes":
        return extract_kansas_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url")) or "https://ksrevisor.gov/",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.03,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            workers=_optional_int(options.get("workers")) or 8,
        )
    if adapter == "louisiana-revised-statutes":
        return extract_louisiana_revised_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url")) or "https://www.legis.la.gov/Legis/",
            root_folder=_optional_text(options.get("root_folder")) or "75",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.02,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            workers=_optional_int(options.get("workers")) or 8,
        )
    if adapter == "dc-code":
        return extract_dc_code(
            store,
            version=version,
            source_dir=_required_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
        )
    if adapter == "cic-html":
        return extract_cic_html_release(
            store,
            jurisdiction=source.jurisdiction,
            version=version,
            release_dir=_required_manifest_path(manifest_path, options, "release_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
        )
    if adapter == "cic-odt":
        return extract_cic_odt_release(
            store,
            jurisdiction=source.jurisdiction,
            version=version,
            release_dir=_required_manifest_path(manifest_path, options, "release_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
        )
    if adapter == "colorado-docx":
        return extract_colorado_docx_release(
            store,
            version=version,
            release_dir=_required_manifest_path(manifest_path, options, "release_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
        )
    if adapter == "local-state-html":
        return extract_state_html_directory(
            store,
            jurisdiction=source.jurisdiction,
            version=version,
            source_dir=_required_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
        )
    if adapter == "texas-tcas":
        return extract_texas_tcas(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 4,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
        )
    if adapter == "ohio-revised-code":
        return extract_ohio_revised_code(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
        )
    if adapter == "minnesota-statutes":
        return extract_minnesota_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 4,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
        )
    if adapter == "nebraska-revised-statutes":
        return extract_nebraska_revised_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 4,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
        )
    if adapter == "washington-rcw":
        return extract_washington_rcw(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 4,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
        )
    if adapter == "illinois-ilcs":
        return extract_illinois_ilcs(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_chapter=only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 8,
        )
    if adapter == "indiana-code":
        return extract_indiana_code(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_zip=_optional_manifest_path(manifest_path, options, "source_zip"),
            source_year=_optional_int(options.get("source_year")) or INDIANA_CODE_DEFAULT_YEAR,
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
        )
    if adapter == "iowa-code":
        return extract_iowa_code(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_year=_optional_int(options.get("source_year")) or IOWA_CODE_DEFAULT_YEAR,
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.05,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            workers=_optional_int(options.get("workers")) or 1,
        )
    if adapter == "idaho-statutes":
        return extract_idaho_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url"))
            or "https://legislature.idaho.gov/statutesrules/idstat/",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.05,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            workers=_optional_int(options.get("workers")) or 1,
        )
    if adapter == "maine-revised-statutes":
        return extract_maine_revised_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            workers=_optional_int(options.get("workers")) or 8,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url"))
            or "https://legislature.maine.gov/statutes/",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.02,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "maryland-code":
        return extract_maryland_code(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_article=_optional_text(options.get("only_article")) or only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 8,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url"))
            or "https://mgaleg.maryland.gov/mgawebsite",
            include_constitution=_optional_bool(options.get("include_constitution"), default=False),
            enactments=_optional_bool(options.get("enactments"), default=False),
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.02,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "massachusetts-general-laws":
        return extract_massachusetts_general_laws(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_part=_optional_text(options.get("only_part")),
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            workers=_optional_int(options.get("workers")) or 8,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url")) or "https://malegislature.gov",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.02,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "michigan-compiled-laws":
        return extract_michigan_compiled_laws(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 8,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url"))
            or "https://legislature.mi.gov/documents/mcl/",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.02,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 120.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "missouri-revised-statutes":
        return extract_missouri_revised_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 8,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url")) or "https://revisor.mo.gov/main/",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.02,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "new-hampshire-rsa":
        return extract_new_hampshire_rsa(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 1,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url")) or "https://gc.nh.gov/rsa/html/",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.25,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 30.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 2,
        )
    if adapter == "new-jersey-statutes":
        return extract_new_jersey_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_zip=_optional_manifest_path(manifest_path, options, "source_zip"),
            source_url=_optional_text(options.get("source_url"))
            or source.source_url
            or NEW_JERSEY_STATUTES_ZIP_URL,
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 180.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "oklahoma-statutes":
        return extract_oklahoma_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 4,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url"))
            or "https://www.oklegislature.gov/OK_Statutes/CompleteTitles/",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.05,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "south-dakota-codified-laws":
        return extract_south_dakota_codified_laws(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            workers=_optional_int(options.get("workers")) or 8,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            base_url=_optional_text(options.get("base_url")) or "https://sdlegislature.gov",
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.02,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "utah-code":
        return extract_utah_code(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_url=_optional_text(options.get("source_url"))
            or source.source_url
            or UTAH_CODE_SOURCE_URL,
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.02,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            workers=_optional_int(options.get("workers")) or 8,
        )
    if adapter == "wisconsin-statutes":
        return extract_wisconsin_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_url=_optional_text(options.get("source_url"))
            or source.source_url
            or WISCONSIN_STATUTES_TOC_URL,
            base_url=_optional_text(options.get("base_url")) or "https://docs.legis.wisconsin.gov",
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.02,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 90.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
            workers=_optional_int(options.get("workers")) or 8,
        )
    if adapter == "montana-code":
        return extract_montana_code(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_year=_optional_int(options.get("source_year")) or MONTANA_CODE_DEFAULT_YEAR,
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 8,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
        )
    if adapter == "nevada-nrs":
        return extract_nevada_nrs(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_year=_optional_int(options.get("source_year")) or NEVADA_NRS_DEFAULT_YEAR,
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            workers=_optional_int(options.get("workers")) or 8,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
        )
    if adapter == "new-york-consolidated-laws":
        return extract_new_york_consolidated_laws(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            workers=_optional_int(options.get("workers")) or 1,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.35,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 15.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 2,
        )
    if adapter == "new-york-openleg-api":
        api_key_env = _optional_text(options.get("api_key_env")) or "NYSENATE_OPENLEG_API_KEY"
        return extract_new_york_openleg_api(
            store,
            version=version,
            api_key=os.environ.get(api_key_env),
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            api_base_url=_optional_text(options.get("api_base_url"))
            or "https://legislation.nysenate.gov",
        )
    if adapter == "delaware-code":
        return extract_delaware_code(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            workers=_optional_int(options.get("workers")) or 1,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
        )
    if adapter == "oregon-ors":
        return extract_oregon_ors(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_year=_optional_int(options.get("source_year")) or OREGON_ORS_DEFAULT_YEAR,
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            workers=_optional_int(options.get("workers")) or 8,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
        )
    if adapter == "pennsylvania-statutes":
        return extract_pennsylvania_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.2,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 120.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "south-carolina-code":
        return extract_south_carolina_code(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.15,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 90.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "west-virginia-code":
        return extract_west_virginia_code(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_chapter=_optional_text(options.get("only_chapter")) or only_title,
            only_article=_optional_text(options.get("only_article")),
            limit=limit,
            workers=_optional_int(options.get("workers")) or 1,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.05,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 90.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "new-mexico-statutes":
        return extract_new_mexico_statutes(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.1,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 90.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    if adapter == "rhode-island-general-laws":
        return extract_rhode_island_general_laws(
            store,
            version=version,
            source_dir=_optional_manifest_path(manifest_path, options, "source_dir"),
            source_year=_optional_int(options.get("source_year"))
            or RHODE_ISLAND_GENERAL_LAWS_DEFAULT_YEAR,
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            only_chapter=_optional_text(options.get("only_chapter")),
            limit=limit,
            workers=_optional_int(options.get("workers")) or 8,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
        )
    if adapter == "california-codes-bulk":
        return extract_california_codes_bulk(
            store,
            version=version,
            source_zip=_optional_manifest_path(manifest_path, options, "source_zip"),
            source_url=source.source_url,
            source_as_of=source_as_of,
            expression_date=expression_date,
            only_title=only_title,
            limit=limit,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            include_inactive=bool(options.get("include_inactive", False)),
        )
    if adapter == "california-code-sections":
        raw_sections = options.get("sections", ())
        sections = (
            (str(raw_sections),)
            if isinstance(raw_sections, str)
            else tuple(str(item) for item in raw_sections)
        )
        return extract_california_code_sections(
            store,
            version=version,
            sections=sections,
            source_as_of=source_as_of,
            expression_date=expression_date,
            download_dir=_optional_manifest_path(manifest_path, options, "download_dir"),
            request_delay_seconds=_optional_float(options.get("request_delay_seconds")) or 0.25,
            timeout_seconds=_optional_float(options.get("timeout_seconds")) or 60.0,
            request_attempts=_optional_int(options.get("request_attempts")) or 3,
        )
    raise ValueError(f"unsupported state statute adapter: {source.adapter}")


def _state_statute_plan_payload(
    source: CorpusSource,
    *,
    manifest_path: Path,
    manifest_version: str,
    limit_override: int | None,
) -> dict[str, Any]:
    options = _state_source_options(source)
    adapter = _canonical_state_statute_adapter(source.adapter)
    path_key = "source_dir" if adapter in {"dc-code", "local-state-html"} else "release_dir"
    source_path = _state_statute_source_path_for_plan(
        adapter,
        manifest_path=manifest_path,
        options=options,
        path_key=path_key,
    )
    return {
        "source_id": source.source_id,
        "jurisdiction": source.jurisdiction,
        "document_class": source.document_class,
        "adapter": adapter,
        "version": source.version or manifest_version,
        "source_path": str(source_path) if source_path is not None else None,
        "source_path_exists": True if source_path is None else source_path.exists(),
        "only_title": _optional_text(options.get("only_title")),
        "limit": (
            limit_override if limit_override is not None else _optional_int(options.get("limit"))
        ),
    }


def _state_statute_report_payload(
    report: StateStatuteExtractReport,
    *,
    source_id: str,
    adapter: str,
    version: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "adapter": _canonical_state_statute_adapter(adapter),
        "jurisdiction": report.jurisdiction,
        "document_class": DocumentClass.STATUTE.value,
        "version": version,
        "title_count": report.title_count,
        "container_count": report.container_count,
        "section_count": report.section_count,
        "skipped_source_count": report.skipped_source_count,
        "error_count": len(report.errors),
        "errors": list(report.errors[:20]),
        "source_file_count": len(report.source_paths),
        "provisions_written": report.provisions_written,
        "inventory_path": str(report.inventory_path),
        "provisions_path": str(report.provisions_path),
        "coverage_path": str(report.coverage_path),
        "coverage_complete": report.coverage.complete,
        "source_count": report.coverage.source_count,
        "provision_count": report.coverage.provision_count,
        "matched_count": report.coverage.matched_count,
        "missing_count": len(report.coverage.missing_from_provisions),
        "extra_count": len(report.coverage.extra_provisions),
    }


def _state_statute_row_success(row: dict[str, Any]) -> bool:
    return (
        bool(row["coverage_complete"])
        and int(row["skipped_source_count"]) == 0
        and int(row["error_count"]) == 0
    )


def _state_statute_report_success(report: StateStatuteExtractReport) -> bool:
    return report.coverage.complete and report.skipped_source_count == 0 and len(report.errors) == 0


def _state_source_options(source: CorpusSource) -> dict[str, Any]:
    if source.options is None:
        return {}
    return dict(source.options)


def _canonical_state_statute_adapter(adapter: str) -> str:
    normalized = adapter.lower().replace("_", "-")
    aliases = {
        "dc": "dc-code",
        "dc-code": "dc-code",
        "dc-law-xml": "dc-code",
        "cic-html": "cic-html",
        "cic-state-code-html": "cic-html",
        "cic-odt": "cic-odt",
        "cic-state-code-odt": "cic-odt",
        "state-html": "local-state-html",
        "state-html-directory": "local-state-html",
        "local-state-html": "local-state-html",
        "legacy-state-html": "local-state-html",
        "al": "alabama-code",
        "alabama": "alabama-code",
        "alabama-code": "alabama-code",
        "alabama-code-graphql": "alabama-code",
        "ak": "alaska-statutes",
        "alaska": "alaska-statutes",
        "alaska-statutes": "alaska-statutes",
        "alaska-statutes-html": "alaska-statutes",
        "az": "arizona-revised-statutes",
        "arizona": "arizona-revised-statutes",
        "arizona-revised-statutes": "arizona-revised-statutes",
        "arizona-ars": "arizona-revised-statutes",
        "ars": "arizona-revised-statutes",
        "ct": "connecticut-statutes",
        "connecticut": "connecticut-statutes",
        "connecticut-statutes": "connecticut-statutes",
        "connecticut-general-statutes": "connecticut-statutes",
        "cga-ct": "connecticut-statutes",
        "fl": "florida-statutes",
        "florida": "florida-statutes",
        "florida-statutes": "florida-statutes",
        "florida-statutes-html": "florida-statutes",
        "hi": "hawaii-revised-statutes",
        "hawaii": "hawaii-revised-statutes",
        "hawaii-revised-statutes": "hawaii-revised-statutes",
        "hawaii-hrs": "hawaii-revised-statutes",
        "hrs": "hawaii-revised-statutes",
        "ks": "kansas-statutes",
        "kansas": "kansas-statutes",
        "kansas-statutes": "kansas-statutes",
        "kansas-statutes-html": "kansas-statutes",
        "kansas-ksa": "kansas-statutes",
        "ksa": "kansas-statutes",
        "la": "louisiana-revised-statutes",
        "louisiana": "louisiana-revised-statutes",
        "louisiana-revised-statutes": "louisiana-revised-statutes",
        "louisiana-rs": "louisiana-revised-statutes",
        "la-rs": "louisiana-revised-statutes",
        "colorado-docx": "colorado-docx",
        "colorado-crs-docx": "colorado-docx",
        "ohio": "ohio-revised-code",
        "ohio-revised-code": "ohio-revised-code",
        "orc": "ohio-revised-code",
        "minnesota": "minnesota-statutes",
        "minnesota-statutes": "minnesota-statutes",
        "mn": "minnesota-statutes",
        "nebraska": "nebraska-revised-statutes",
        "nebraska-revised-statutes": "nebraska-revised-statutes",
        "neb-rev-stat": "nebraska-revised-statutes",
        "ne": "nebraska-revised-statutes",
        "washington": "washington-rcw",
        "washington-rcw": "washington-rcw",
        "rcw": "washington-rcw",
        "wa": "washington-rcw",
        "il": "illinois-ilcs",
        "ilcs": "illinois-ilcs",
        "illinois": "illinois-ilcs",
        "illinois-ilcs": "illinois-ilcs",
        "in": "indiana-code",
        "indiana": "indiana-code",
        "indiana-code": "indiana-code",
        "indiana-code-html": "indiana-code",
        "ia": "iowa-code",
        "iowa": "iowa-code",
        "iowa-code": "iowa-code",
        "iowa-code-html": "iowa-code",
        "id": "idaho-statutes",
        "idaho": "idaho-statutes",
        "idaho-statutes": "idaho-statutes",
        "idaho-code": "idaho-statutes",
        "idaho-statutes-html": "idaho-statutes",
        "me": "maine-revised-statutes",
        "maine": "maine-revised-statutes",
        "maine-revised-statutes": "maine-revised-statutes",
        "maine-statutes": "maine-revised-statutes",
        "mrs": "maine-revised-statutes",
        "maine-revised-statutes-html": "maine-revised-statutes",
        "md": "maryland-code",
        "maryland": "maryland-code",
        "maryland-code": "maryland-code",
        "maryland-statutes": "maryland-code",
        "maryland-code-html": "maryland-code",
        "maryland-mga": "maryland-code",
        "ma": "massachusetts-general-laws",
        "massachusetts": "massachusetts-general-laws",
        "massachusetts-general-laws": "massachusetts-general-laws",
        "massachusetts-statutes": "massachusetts-general-laws",
        "mass-general-laws": "massachusetts-general-laws",
        "massachusetts-general-laws-html": "massachusetts-general-laws",
        "mgl": "massachusetts-general-laws",
        "mi": "michigan-compiled-laws",
        "michigan": "michigan-compiled-laws",
        "michigan-compiled-laws": "michigan-compiled-laws",
        "michigan-mcl": "michigan-compiled-laws",
        "mcl": "michigan-compiled-laws",
        "mo": "missouri-revised-statutes",
        "missouri": "missouri-revised-statutes",
        "missouri-revised-statutes": "missouri-revised-statutes",
        "missouri-rs": "missouri-revised-statutes",
        "rsmo": "missouri-revised-statutes",
        "mt": "montana-code",
        "montana": "montana-code",
        "montana-code": "montana-code",
        "montana-code-html": "montana-code",
        "mca": "montana-code",
        "nv": "nevada-nrs",
        "nevada": "nevada-nrs",
        "nevada-nrs": "nevada-nrs",
        "nrs": "nevada-nrs",
        "nevada-nrs-html": "nevada-nrs",
        "nh": "new-hampshire-rsa",
        "new-hampshire": "new-hampshire-rsa",
        "new-hampshire-rsa": "new-hampshire-rsa",
        "new-hampshire-statutes": "new-hampshire-rsa",
        "nh-rsa": "new-hampshire-rsa",
        "rsa-nh": "new-hampshire-rsa",
        "nj": "new-jersey-statutes",
        "new-jersey": "new-jersey-statutes",
        "new-jersey-statutes": "new-jersey-statutes",
        "new-jersey-statutes-text": "new-jersey-statutes",
        "nj-statutes": "new-jersey-statutes",
        "njsa": "new-jersey-statutes",
        "ok": "oklahoma-statutes",
        "oklahoma": "oklahoma-statutes",
        "oklahoma-statutes": "oklahoma-statutes",
        "ok-statutes": "oklahoma-statutes",
        "sd": "south-dakota-codified-laws",
        "south-dakota": "south-dakota-codified-laws",
        "south-dakota-codified-laws": "south-dakota-codified-laws",
        "south-dakota-statutes": "south-dakota-codified-laws",
        "sdcl": "south-dakota-codified-laws",
        "ut": "utah-code",
        "utah": "utah-code",
        "utah-code": "utah-code",
        "utah-code-xml": "utah-code",
        "ut-code": "utah-code",
        "wi": "wisconsin-statutes",
        "wisconsin": "wisconsin-statutes",
        "wisconsin-statutes": "wisconsin-statutes",
        "wisconsin-code": "wisconsin-statutes",
        "wi-statutes": "wisconsin-statutes",
        "ny": "new-york-openleg-api",
        "new-york": "new-york-openleg-api",
        "new-york-openleg-api": "new-york-openleg-api",
        "ny-openleg": "new-york-openleg-api",
        "openleg": "new-york-openleg-api",
        "new-york-openleg-sections": "new-york-openleg-sections",
        "ny-openleg-sections": "new-york-openleg-sections",
        "new-york-sections": "new-york-openleg-sections",
        "ny-sections": "new-york-openleg-sections",
        "openleg-sections": "new-york-openleg-sections",
        "new-york-consolidated-laws": "new-york-consolidated-laws",
        "nysenate": "new-york-consolidated-laws",
        "ny-senate": "new-york-consolidated-laws",
        "nyc-admin-code": "nyc-admin-code",
        "new-york-city-admin-code": "nyc-admin-code",
        "new-york-city-administrative-code": "nyc-admin-code",
        "co-crs": "colorado-revised-statutes",
        "colorado-crs": "colorado-revised-statutes",
        "colorado-revised-statutes": "colorado-revised-statutes",
        "crs": "colorado-revised-statutes",
        "de": "delaware-code",
        "delaware": "delaware-code",
        "delaware-code": "delaware-code",
        "delaware-code-html": "delaware-code",
        "or": "oregon-ors",
        "oregon": "oregon-ors",
        "oregon-ors": "oregon-ors",
        "oregon-ors-html": "oregon-ors",
        "ors": "oregon-ors",
        "pa": "pennsylvania-statutes",
        "pennsylvania": "pennsylvania-statutes",
        "pennsylvania-statutes": "pennsylvania-statutes",
        "pennsylvania-consolidated-statutes": "pennsylvania-statutes",
        "pennsylvania-consolidated-statutes-html": "pennsylvania-statutes",
        "pacode": "pennsylvania-statutes",
        "pa-consolidated-statutes": "pennsylvania-statutes",
        "sc": "south-carolina-code",
        "south-carolina": "south-carolina-code",
        "south-carolina-code": "south-carolina-code",
        "south-carolina-code-html": "south-carolina-code",
        "sc-code": "south-carolina-code",
        "wv": "west-virginia-code",
        "west-virginia": "west-virginia-code",
        "west-virginia-code": "west-virginia-code",
        "west-virginia-code-html": "west-virginia-code",
        "wv-code": "west-virginia-code",
        "nm": "new-mexico-statutes",
        "new-mexico": "new-mexico-statutes",
        "new-mexico-statutes": "new-mexico-statutes",
        "new-mexico-nmsa": "new-mexico-statutes",
        "nmone": "new-mexico-statutes",
        "nmonesource": "new-mexico-statutes",
        "ri": "rhode-island-general-laws",
        "rhode-island": "rhode-island-general-laws",
        "rhode-island-general-laws": "rhode-island-general-laws",
        "rhode-island-general-laws-html": "rhode-island-general-laws",
        "rigl": "rhode-island-general-laws",
        "ca": "california-codes-bulk",
        "california": "california-codes-bulk",
        "california-codes": "california-codes-bulk",
        "california-codes-bulk": "california-codes-bulk",
        "california-leginfo": "california-codes-bulk",
        "ca-leginfo": "california-codes-bulk",
        "california-code-sections": "california-code-sections",
        "california-section": "california-code-sections",
        "california-sections": "california-code-sections",
        "ca-code-sections": "california-code-sections",
        "ca-sections": "california-code-sections",
        "texas-tcas": "texas-tcas",
        "texas-api": "texas-tcas",
        "tcas": "texas-tcas",
    }
    if normalized not in aliases:
        raise ValueError(f"unsupported state statute adapter: {adapter}")
    return aliases[normalized]


def _required_manifest_path(
    manifest_path: Path,
    options: dict[str, Any],
    key: str,
) -> Path:
    value = options.get(key)
    if value is None:
        raise ValueError(f"missing required option: {key}")
    path = Path(str(value))
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path


def _state_statute_source_path_for_plan(
    adapter: str,
    *,
    manifest_path: Path,
    options: dict[str, Any],
    path_key: str,
) -> Path | None:
    if adapter in {
        "alabama-code",
        "alaska-statutes",
        "arizona-revised-statutes",
        "connecticut-statutes",
        "florida-statutes",
        "hawaii-revised-statutes",
        "kansas-statutes",
        "louisiana-revised-statutes",
        "minnesota-statutes",
        "nebraska-revised-statutes",
        "ohio-revised-code",
        "texas-tcas",
        "washington-rcw",
        "illinois-ilcs",
        "indiana-code",
        "iowa-code",
        "idaho-statutes",
        "maine-revised-statutes",
        "maryland-code",
        "massachusetts-general-laws",
        "michigan-compiled-laws",
        "missouri-revised-statutes",
        "montana-code",
        "nevada-nrs",
        "new-hampshire-rsa",
        "new-jersey-statutes",
        "oklahoma-statutes",
        "south-dakota-codified-laws",
        "utah-code",
        "wisconsin-statutes",
        "new-york-consolidated-laws",
        "new-york-openleg-api",
        "nyc-admin-code",
        "delaware-code",
        "oregon-ors",
        "pennsylvania-statutes",
        "south-carolina-code",
        "west-virginia-code",
        "new-mexico-statutes",
        "rhode-island-general-laws",
    }:
        return _optional_manifest_path(manifest_path, options, "source_dir") or (
            _optional_manifest_path(manifest_path, options, "source_zip")
            if adapter == "indiana-code"
            else None
        )
    if adapter == "california-codes-bulk":
        return _optional_manifest_path(manifest_path, options, "source_zip")
    if adapter == "california-code-sections":
        return _optional_manifest_path(manifest_path, options, "download_dir")
    if adapter == "local-state-html":
        return _required_manifest_path(manifest_path, options, "source_dir")
    return _required_manifest_path(manifest_path, options, path_key)


def _optional_manifest_path(
    manifest_path: Path,
    options: dict[str, Any],
    key: str,
) -> Path | None:
    value = options.get(key)
    if value is None:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _cmd_extract_colorado_ccr(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_colorado_ccr(
        store,
        version=args.version,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_series=args.only_series,
        limit=args.limit,
        workers=args.workers,
        release_dir=args.release_dir,
        download_dir=args.download_dir,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": args.version,
                "document_count": report.document_count,
                "section_count": report.section_count,
                "skipped_source_count": report.skipped_source_count,
                "error_count": len(report.errors),
                "errors": list(report.errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_washington_wac(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_washington_wac(
        store,
        version=args.version,
        source_dir=args.source_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        only_chapter=args.only_chapter,
        limit=args.limit,
        workers=args.workers,
        download_dir=args.download_dir,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": report.version,
                "title_count": report.title_count,
                "chapter_count": report.chapter_count,
                "section_count": report.section_count,
                "skipped_source_count": report.skipped_source_count,
                "error_count": len(report.errors),
                "errors": list(report.errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_virginia_vac(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_virginia_vac(
        store,
        version=args.version,
        source_dir=args.source_dir,
        download_dir=args.download_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        only_agency=args.only_agency,
        only_chapter=args.only_chapter,
        limit=args.limit,
        workers=args.workers,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": report.version,
                "title_count": report.title_count,
                "agency_count": report.agency_count,
                "chapter_count": report.chapter_count,
                "section_count": report.section_count,
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_maryland_comar(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_maryland_comar(
        store,
        version=args.version,
        source_dir=args.source_dir,
        download_dir=args.download_dir,
        publication_branch=args.publication_branch,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        only_subtitle=args.only_subtitle,
        only_chapter=args.only_chapter,
        limit=args.limit,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": report.version,
                "publication_branch": report.publication_branch,
                "title_count": report.title_count,
                "subtitle_count": report.subtitle_count,
                "chapter_count": report.chapter_count,
                "regulation_count": report.regulation_count,
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_illinois_admin_code(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_illinois_admin_code(
        store,
        version=args.version,
        source_dir=args.source_dir,
        download_dir=args.download_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        workers=args.workers,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": report.version,
                "title_count": report.title_count,
                "subtitle_count": report.subtitle_count,
                "chapter_count": report.chapter_count,
                "subchapter_count": report.subchapter_count,
                "part_count": report.part_count,
                "section_count": report.section_count,
                "appendix_count": report.appendix_count,
                "skipped_source_count": report.skipped_source_count,
                "error_count": len(report.errors),
                "errors": list(report.errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return (
        0
        if (report.coverage.complete and report.skipped_source_count == 0) or args.allow_incomplete
        else 2
    )


def _cmd_extract_ohio_admin_code(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_ohio_admin_code(
        store,
        version=args.version,
        source_dir=args.source_dir,
        download_dir=args.download_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_agency=args.only_agency,
        only_chapter=args.only_chapter,
        limit=args.limit,
        workers=args.workers,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": report.version,
                "agency_count": report.agency_count,
                "chapter_count": report.chapter_count,
                "rule_count": report.rule_count,
                "skipped_source_count": report.skipped_source_count,
                "error_count": len(report.errors),
                "errors": list(report.errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return (
        0
        if (report.coverage.complete and report.skipped_source_count == 0) or args.allow_incomplete
        else 2
    )


def _cmd_extract_oregon_admin_rules(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_oregon_admin_rules(
        store,
        version=args.version,
        source_dir=args.source_dir,
        download_dir=args.download_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_chapter=args.only_chapter,
        only_division=args.only_division,
        limit=args.limit,
        workers=args.workers,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": report.version,
                "chapter_count": report.chapter_count,
                "division_count": report.division_count,
                "rule_count": report.rule_count,
                "skipped_source_count": report.skipped_source_count,
                "error_count": len(report.errors),
                "errors": list(report.errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return (
        0
        if (report.coverage.complete and report.skipped_source_count == 0) or args.allow_incomplete
        else 2
    )


def _cmd_extract_pennsylvania_code(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_pennsylvania_code(
        store,
        version=args.version,
        source_dir=args.source_dir,
        download_dir=args.download_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        only_chapter=args.only_chapter,
        limit_titles=args.limit_titles,
        limit_chapters=args.limit_chapters,
        workers=args.workers,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": report.version,
                "title_count": report.title_count,
                "chapter_count": report.chapter_count,
                "reserved_chapter_count": report.reserved_chapter_count,
                "section_count": report.section_count,
                "skipped_source_count": report.skipped_source_count,
                "error_count": len(report.errors),
                "errors": list(report.errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return (
        0
        if (report.coverage.complete and report.skipped_source_count == 0) or args.allow_incomplete
        else 2
    )


def _cmd_extract_montana_admin_rules(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_montana_admin_rules(
        store,
        version=args.version,
        source_dir=args.source_dir,
        download_dir=args.download_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        only_section=args.only_section,
        include_not_effective=args.include_not_effective,
        limit_sections=args.limit_sections,
        limit_rules=args.limit_rules,
        workers=args.workers,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": report.version,
                "title_count": report.title_count,
                "chapter_count": report.chapter_count,
                "subchapter_count": report.subchapter_count,
                "rule_count": report.rule_count,
                "skipped_source_count": report.skipped_source_count,
                "error_count": len(report.errors),
                "errors": list(report.errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return (
        0
        if (report.coverage.complete and report.skipped_source_count == 0) or args.allow_incomplete
        else 2
    )


def _cmd_extract_nycrr(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_nycrr(
        store,
        version=args.version,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_title=args.only_title,
        limit=args.limit,
        delay_seconds=args.delay_seconds,
        retry_attempts=args.retry_attempts,
        refresh=args.refresh,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": args.version,
                "page_count": report.page_count,
                "browse_page_count": report.browse_page_count,
                "document_page_count": report.document_page_count,
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_california_mpp_calfresh(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    docx_sources = _load_california_mpp_docx_sources(args.manifest)
    report = extract_california_mpp_calfresh(
        store,
        version=args.version,
        docx_sources=docx_sources,
        download_dir=args.download_dir,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        request_delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        request_attempts=args.request_attempts,
    )
    print(
        json.dumps(
            {
                "adapter": "california-mpp-calfresh",
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": args.version,
                "source_file_count": len(report.source_paths),
                "section_count": report.section_count,
                "subsection_count": report.subsection_count,
                "container_count": report.container_count,
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _load_california_mpp_docx_sources(manifest_path: Path) -> tuple[MppDocxSource, ...]:
    """Load DOCX source declarations from the CA MPP manifest."""
    import yaml  # local import — cli.py already pulls yaml via other paths

    manifest = yaml.safe_load(manifest_path.read_text())
    sources = manifest.get("sources") or []
    if not sources:
        raise ValueError(f"manifest has no sources entry: {manifest_path}")
    # MVP: take the first source block. Multi-source manifests can grow later.
    options = sources[0].get("options") or {}
    docx_sources_raw = options.get("docx_sources") or []
    if not docx_sources_raw:
        raise ValueError(f"manifest has no docx_sources under options: {manifest_path}")
    return tuple(
        MppDocxSource(
            file=str(entry["file"]),
            url=str(entry["url"]),
            chapter=str(entry["chapter"]),
            sections=tuple(str(s) for s in entry.get("sections", ())),
            summary=str(entry.get("summary", "")),
        )
        for entry in docx_sources_raw
    )


def _cmd_extract_ny_state_register(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_ny_state_register(
        store,
        version=args.version,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        limit=args.limit,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": args.version,
                "issue_count": report.issue_count,
                "notice_count": report.notice_count,
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_federal_register(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date) if args.end_date else start_date
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_federal_register(
        store,
        version=args.version,
        start_date=start_date,
        end_date=end_date,
        document_types=tuple(args.document_type or DEFAULT_DOCUMENT_TYPES),
        term=args.term,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        limit=args.limit,
        per_page=args.per_page,
        fetch_full_text=not args.skip_full_text,
        timeout_seconds=args.timeout_seconds,
        request_attempts=args.request_attempts,
        request_delay_seconds=args.request_delay_seconds,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": report.version,
                "start_date": report.start_date,
                "end_date": report.end_date,
                "document_types": list(report.document_types),
                "page_count": report.page_count,
                "document_count": report.document_count,
                "text_error_count": report.text_error_count,
                "errors": list(report.errors[:20]),
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_federal_register_cfr_sections(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    report = extract_federal_register_cfr_sections(
        store,
        version=args.version,
        source_text_path=args.source_text,
        sections=tuple(_parse_cfr_section_ref(value) for value in args.section),
        document_number=args.document_number,
        document_citation=args.document_citation,
        document_title=args.document_title,
        document_type=args.document_type,
        source_url=args.source_url,
        source_as_of=args.source_as_of,
        expression_date=args.expression_date,
        source_document_citation_path=args.source_document_citation_path,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": report.version,
                "requested_sections": list(report.requested_sections),
                "sections_written": report.sections_written,
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _parse_cfr_section_ref(value: str) -> FederalRegisterCfrSectionRef:
    cleaned = value.strip()
    match = re.fullmatch(
        r"(?:(?P<title>\d+)\s*CFR\s+)?(?P<part>\d+)\.(?P<section>\d+[A-Za-z]?)",
        cleaned,
        flags=re.I,
    )
    if match is None:
        match = re.fullmatch(
            r"(?P<title>\d+)[:/](?P<part>\d+)[:/](?P<section>\d+[A-Za-z]?)",
            cleaned,
        )
    if match is None:
        raise ValueError("CFR section must look like '42 CFR 431.213' or '42:431:213'")
    title = int(match.group("title") or 42)
    return FederalRegisterCfrSectionRef(
        title=title,
        part=int(match.group("part")),
        section=match.group("section"),
    )


def _cmd_extract_official_documents(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_official_documents(
        store,
        manifest_path=args.manifest,
        version=args.version,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_source_id=args.only_source_id,
        limit=args.limit,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": args.version,
                "document_count": report.document_count,
                "block_count": report.block_count,
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_extract_eli_documents(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    expression_date = date.fromisoformat(args.expression_date) if args.expression_date else None
    report = extract_eli_documents(
        store,
        manifest_path=args.manifest,
        version=args.version,
        source_as_of=args.source_as_of,
        expression_date=expression_date,
        only_source_id=args.only_source_id,
        limit=args.limit,
        allow_superseded=args.allow_superseded,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "adapter": "eli",
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": args.version,
                "document_count": report.document_count,
                "section_count": report.block_count,
                "source_file_count": len(report.source_paths),
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_reconstruct_new_jersey_snap_rules(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    report = reconstruct_new_jersey_snap_rules(
        store,
        version=args.version,
        base_provisions_path=args.base_provisions,
        rulemaking_provisions_path=args.rulemaking_provisions,
        source_as_of=args.source_as_of,
        expression_date=args.expression_date,
        progress_stream=sys.stderr,
    )
    print(
        json.dumps(
            {
                "jurisdiction": report.jurisdiction,
                "document_class": report.document_class,
                "version": report.version,
                "provisions_written": report.provisions_written,
                "inventory_path": str(report.inventory_path),
                "provisions_path": str(report.provisions_path),
                "coverage_path": str(report.coverage_path),
                "coverage_complete": report.coverage.complete,
                "source_count": report.coverage.source_count,
                "provision_count": report.coverage.provision_count,
                "matched_count": report.coverage.matched_count,
                "missing_count": len(report.coverage.missing_from_provisions),
                "extra_count": len(report.coverage.extra_provisions),
                "modified_count": len(report.modified_citation_paths),
                "added_count": len(report.added_citation_paths),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.coverage.complete or args.allow_incomplete else 2


def _cmd_coverage(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    source_inventory = load_source_inventory(args.source_inventory)
    provisions = load_provisions(args.provisions)
    report = compare_provision_coverage(
        source_inventory,
        provisions,
        jurisdiction=args.jurisdiction,
        document_class=args.document_class,
        version=args.version,
    )
    payload = report.to_mapping()
    if args.write:
        out = store.coverage_path(args.jurisdiction, args.document_class, args.version)
        store.write_json(out, payload)
        payload["written_to"] = str(out)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if report.complete or args.allow_incomplete else 2


def _cmd_analytics(args: argparse.Namespace) -> int:
    store = CorpusArtifactStore(args.base)
    report = build_analytics_report(
        store,
        version=args.version,
        provision_counts=load_provision_count_snapshot(
            args.supabase_counts,
            default_document_class=args.default_count_document_class,
        ),
        jurisdictions=tuple(args.jurisdiction),
        document_classes=tuple(args.document_class),
    )
    payload = report.to_mapping()
    if args.write or args.output:
        out = args.output or (store.root / "analytics" / f"{args.version}.json")
        store.write_json(out, payload)
        payload["written_to"] = str(out)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_sync_r2(args: argparse.Namespace) -> int:
    config = load_r2_config(
        credential_path=args.credentials_file,
        bucket=args.bucket,
        endpoint_url=args.endpoint_url,
    )
    report = sync_artifacts_to_r2(
        args.base,
        config=config,
        prefixes=tuple(args.prefix or DEFAULT_ARTIFACT_PREFIXES),
        jurisdiction=args.jurisdiction,
        document_class=args.document_class,
        version=args.version,
        dry_run=not args.apply,
        limit=args.limit,
        workers=args.workers,
        force=args.force,
        progress_stream=sys.stderr,
    )
    print(json.dumps(report.to_mapping(), indent=2, sort_keys=True))
    return 0


def _cmd_artifact_report(args: argparse.Namespace) -> int:
    prefixes = tuple(args.prefix or DEFAULT_ARTIFACT_PREFIXES)
    release = None
    release_path = None
    release_name = args.release
    if release_name:
        release_path = resolve_release_manifest_path(release_name)
        release = ReleaseManifest.load(release_path)
    if args.include_r2:
        config = load_r2_config(
            credential_path=args.credentials_file,
            bucket=args.bucket,
            endpoint_url=args.endpoint_url,
        )
        report = build_artifact_report_with_r2(
            args.base,
            config=config,
            prefixes=prefixes,
            version=args.version,
            jurisdiction=args.jurisdiction,
            document_class=args.document_class,
            supabase_counts_path=args.supabase_counts,
            release_name=release.name if release else None,
            release_scopes=release.scope_keys if release else None,
        )
    else:
        report = build_artifact_report(
            args.base,
            prefixes=prefixes,
            version=args.version,
            jurisdiction=args.jurisdiction,
            document_class=args.document_class,
            supabase_counts_path=args.supabase_counts,
            release_name=release.name if release else None,
            release_scopes=release.scope_keys if release else None,
        )
    payload = report.to_mapping()
    if release_path:
        payload["release_path"] = str(release_path)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        payload["written_to"] = str(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_section_provisions(args: argparse.Namespace) -> int:
    """Split a scope's monolithic document bodies into section children."""
    store = CorpusArtifactStore(args.base)
    path = store.provisions_path(args.jurisdiction, args.document_class, args.version)
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    section_slug = re.compile(r"/(?:part|step|schedule)-\d+$")
    existing_paths = {record["citation_path"] for record in lines}
    documents = [
        record
        for record in lines
        if record.get("level", 1) == 1 and record.get("kind") == "document"
    ]
    split_docs = []
    new_records: list[tuple[dict[str, Any], str, list[dict[str, Any]]]] = []
    for parent in documents:
        if any(
            other.startswith(parent["citation_path"] + "/") and section_slug.search(other)
            for other in existing_paths
        ):
            continue
        split = split_document_body(parent.get("body") or "")
        if split is None:
            continue
        children = []
        for i, section in enumerate(split.sections):
            child = dict(parent)
            citation_path = f"{parent['citation_path']}/{section.slug}"
            child.update(
                citation_path=citation_path,
                citation_label=f"{parent.get('citation_label') or parent.get('heading')} — {section.heading}",
                heading=section.heading,
                id=deterministic_provision_id(citation_path, parent.get("version")),
                kind="section",
                level=2,
                ordinal=2 + i,
                body=section.body,
            )
            metadata = dict(parent.get("metadata") or {})
            if metadata.get("title"):
                metadata["title"] = f"{metadata['title']} — {section.heading}"
            if metadata.get("document_subtype"):
                # Same convention as the "_values" supplementary children.
                metadata["document_subtype"] = f"{metadata['document_subtype']}_section"
            child["metadata"] = metadata
            children.append(child)
        split_docs.append(
            {
                "citation_path": parent["citation_path"],
                "sections": [child["citation_path"] for child in children],
                "intro_chars": len(split.intro),
            }
        )
        new_records.append((parent, split.intro, children))
    payload: dict[str, Any] = {
        "provisions": str(path),
        "documents": len(documents),
        "split": split_docs,
        "applied": bool(args.apply and split_docs),
    }
    if args.apply and new_records:
        out: list[dict[str, Any]] = []
        replaced: dict[int, tuple[str, list[dict[str, Any]]]] = {
            id(parent): (intro, children) for parent, intro, children in new_records
        }
        trailing: list[dict[str, Any]] = []
        for record in lines:
            if id(record) in replaced:
                intro, children = replaced[id(record)]
                out.append(dict(record, body=intro, ordinal=1))
                out.extend(children)
            elif record.get("level", 1) == 1:
                out.append(record)
            else:
                trailing.append(record)
        for offset, record in enumerate(trailing):
            record = dict(record, ordinal=len(out) + 1 + offset)
            out.append(record)
        with path.open("w") as handle:
            for record in out:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_validate_release(args: argparse.Namespace) -> int:
    release_path = resolve_release_manifest_path(args.release)
    release = ReleaseManifest.load(release_path)
    prefixes = tuple(args.prefix or DEFAULT_RELEASE_ARTIFACT_PREFIXES)
    if args.include_r2:
        config = load_r2_config(
            credential_path=args.credentials_file,
            bucket=args.bucket,
            endpoint_url=args.endpoint_url,
        )
        artifact_report = build_artifact_report_with_r2(
            args.base,
            config=config,
            prefixes=prefixes,
            supabase_counts_path=args.supabase_counts,
            release_name=release.name,
            release_scopes=release.scope_keys,
        )
    else:
        artifact_report = build_artifact_report(
            args.base,
            prefixes=prefixes,
            supabase_counts_path=args.supabase_counts,
            release_name=release.name,
            release_scopes=release.scope_keys,
        )
    report = validate_release(
        args.base,
        release,
        artifact_report=artifact_report,
        max_issues=args.max_issues,
        strict_warnings=args.strict_warnings,
        ignore_r2_missing=args.ignore_r2_missing,
    )
    payload = report.to_mapping()
    payload["release_path"] = str(release_path)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        payload["written_to"] = str(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if report.ok else 2


def _cmd_state_statute_completion(args: argparse.Namespace) -> int:
    release_path = resolve_release_manifest_path(args.release)
    release = ReleaseManifest.load(release_path)
    prefixes = tuple(args.prefix or DEFAULT_RELEASE_ARTIFACT_PREFIXES)
    source_access_queue = _resolve_state_source_access_queue(args.base, args.source_access_queue)
    validation_report_path = args.validation_report
    if validation_report_path is None:
        candidate = args.base / "analytics" / f"validate-release-{release.name}.json"
        if candidate.exists():
            validation_report_path = candidate
    if args.include_r2:
        config = load_r2_config(
            credential_path=args.credentials_file,
            bucket=args.bucket,
            endpoint_url=args.endpoint_url,
        )
        artifact_report = build_artifact_report_with_r2(
            args.base,
            config=config,
            prefixes=prefixes,
            document_class=DocumentClass.STATUTE.value,
            supabase_counts_path=args.supabase_counts,
            release_name=release.name,
            release_scopes=release.scope_keys,
        )
    else:
        artifact_report = build_artifact_report(
            args.base,
            prefixes=prefixes,
            document_class=DocumentClass.STATUTE.value,
            supabase_counts_path=args.supabase_counts,
            release_name=release.name,
            release_scopes=release.scope_keys,
        )
    report = build_state_statute_completion_report(
        args.base,
        release=release,
        artifact_report=artifact_report,
        supabase_counts_path=args.supabase_counts,
        validation_report_path=validation_report_path,
        source_access_statuses=load_source_access_statuses(source_access_queue),
    )
    payload = report.to_mapping()
    payload["release_path"] = str(release_path)
    if source_access_queue is not None:
        payload["source_access_queue_path"] = str(source_access_queue)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        payload["written_to"] = str(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_complete and not report.complete:
        return 2
    return 0


def _cmd_regulation_completion(args: argparse.Namespace) -> int:
    release_path = resolve_release_manifest_path(args.release)
    release = ReleaseManifest.load(release_path)
    prefixes = tuple(args.prefix or DEFAULT_RELEASE_ARTIFACT_PREFIXES)
    validation_report_path = args.validation_report
    if validation_report_path is None:
        candidate = args.base / "analytics" / f"validate-release-{release.name}.json"
        if candidate.exists():
            validation_report_path = candidate
    if args.include_r2:
        config = load_r2_config(
            credential_path=args.credentials_file,
            bucket=args.bucket,
            endpoint_url=args.endpoint_url,
        )
        artifact_report = build_artifact_report_with_r2(
            args.base,
            config=config,
            prefixes=prefixes,
            document_class=DocumentClass.REGULATION.value,
            supabase_counts_path=args.supabase_counts,
            release_name=release.name,
            release_scopes=release.scope_keys,
        )
    else:
        artifact_report = build_artifact_report(
            args.base,
            prefixes=prefixes,
            document_class=DocumentClass.REGULATION.value,
            supabase_counts_path=args.supabase_counts,
            release_name=release.name,
            release_scopes=release.scope_keys,
        )
    report = build_regulation_completion_report(
        args.base,
        release=release,
        artifact_report=artifact_report,
        supabase_counts_path=args.supabase_counts,
        validation_report_path=validation_report_path,
    )
    payload = report.to_mapping()
    payload["release_path"] = str(release_path)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        payload["written_to"] = str(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_complete and not report.complete:
        return 2
    return 0


def _cmd_source_discovery(args: argparse.Namespace) -> int:
    if not args.input and not args.reference_input:
        print(
            json.dumps(
                {"error": "source-discovery requires --input or --reference-input"},
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    release = None
    release_path = None
    covered_source_urls = None
    if args.release:
        release_path = resolve_release_manifest_path(args.release)
        release = ReleaseManifest.load(release_path)
        covered_source_urls = _release_inventory_source_urls(
            CorpusArtifactStore(args.base),
            release,
        )
    report = build_source_discovery_report(
        tuple(args.input or ()),
        reference_input_paths=tuple(args.reference_input or ()),
        release=release,
        covered_source_urls=covered_source_urls,
        source_name=args.source_name,
    )
    payload = report.to_mapping()
    if release_path is not None:
        payload["release_path"] = str(release_path)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        payload["written_to"] = str(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_promote_source_discovery_group(args: argparse.Namespace) -> int:
    report = promote_source_discovery_group(
        report_path=args.report,
        group_key=args.group_key,
        output_path=args.output,
        source_as_of=args.source_as_of,
        expression_date=args.expression_date,
        limit=args.limit,
        exclude_urls=tuple(args.exclude_url or ()),
        url_rewrites=_parse_url_rewrites(args.rewrite_url or ()),
        fail_on_unsupported=not args.allow_unsupported,
    )
    print(json.dumps(report.to_mapping(), indent=2, sort_keys=True))
    return 0


def _parse_url_rewrites(values: Iterable[str]) -> dict[str, str]:
    rewrites: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"--rewrite-url must be FROM=TO: {value}")
        source, target = value.split("=", 1)
        if not source or not target:
            raise ValueError(f"--rewrite-url must be FROM=TO: {value}")
        rewrites[source] = target
    return rewrites


def _cmd_policyengine_references(args: argparse.Namespace) -> int:
    projects = tuple(args.project or ())
    repos = tuple(args.repo)
    if projects and len(projects) != len(repos):
        print(
            json.dumps(
                {
                    "error": "--project must be supplied once per --repo when used",
                    "project_count": len(projects),
                    "repo_count": len(repos),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    records: list[PolicyEngineReference] = []
    for index, repo in enumerate(repos):
        project = projects[index] if projects else None
        records.extend(
            scan_policyengine_references(
                repo,
                project=project,
                scope=PolicyEngineReferenceScope(args.scope),
            )
        )
    references = tuple(records)
    write_policyengine_references_jsonl(references, args.output)
    if args.url_output:
        write_policyengine_url_inventory(references, args.url_output)

    payload = summarize_policyengine_references(references)
    payload["repo_count"] = len(repos)
    payload["scope"] = args.scope
    payload["written_to"] = str(args.output)
    if args.url_output:
        payload["url_inventory_written_to"] = str(args.url_output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _release_inventory_source_urls(
    store: CorpusArtifactStore,
    release: ReleaseManifest,
) -> tuple[str, ...]:
    """Collect official source URLs that have already been materialized."""

    urls: set[str] = set()
    for scope in release.scopes:
        inventory_path = store.inventory_path(
            scope.jurisdiction,
            scope.document_class,
            scope.version,
        )
        if not inventory_path.exists():
            continue
        for item in load_source_inventory(inventory_path):
            if item.source_url:
                urls.add(item.source_url)
            metadata = item.metadata or {}
            for key in ("download_url", "final_url", "source_url"):
                value = metadata.get(key)
                if isinstance(value, str) and value:
                    urls.add(value)
    return tuple(sorted(urls))


def _resolve_state_source_access_queue(base: Path, value: Path | None) -> Path | None:
    if value is not None:
        return value if str(value) else None
    candidates = (
        Path("manifests/state-statute-agent-queue.yaml"),
        base.parent.parent / "manifests" / "state-statute-agent-queue.yaml",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _artifact_scope_filter_supplied(args: argparse.Namespace) -> bool:
    return any((args.version, args.jurisdiction, args.document_class))


def _add_rulespec_args(sub_parser: argparse.ArgumentParser) -> None:
    """Attach the shared --rulespec-* flags so build-navigation-index and
    load-supabase can both pull encoded paths from local rulespec-* checkouts."""
    sub_parser.add_argument(
        "--rulespec-repo",
        action="append",
        default=[],
        help=(
            "Path to a local rulespec-* checkout (e.g. /path/to/rulespec-us). "
            "Repeatable. Jurisdiction is inferred from the directory name."
        ),
    )
    sub_parser.add_argument(
        "--rulespec-root",
        action="append",
        default=[],
        help=(
            "Path to a directory holding sibling rulespec-* checkouts. The "
            "builder discovers each jurisdiction's repo by name (rulespec-us, "
            "rulespec-us-co, …). Repeatable."
        ),
    )
    sub_parser.add_argument(
        "--rulespec-auto",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Automatically check ../rulespec-{repo} next to the corpus checkout "
            "for each input jurisdiction. Disable with --no-rulespec-auto."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Source-first corpus pipeline tools.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-manifest", help="Validate a corpus manifest.")
    validate.add_argument("path", type=Path)
    validate.set_defaults(func=_cmd_validate_manifest)

    sign_ingest = sub.add_parser(
        "sign-ingest-manifest",
        help="Sign generated corpus artifacts for one ingestion scope.",
    )
    sign_ingest.add_argument("--repo", type=Path, default=Path("."))
    sign_ingest.add_argument("--base", type=Path, default=Path("data/corpus"))
    sign_ingest.add_argument("--jurisdiction", required=True)
    sign_ingest.add_argument("--document-class", required=True)
    sign_ingest.add_argument("--version", required=True)
    sign_ingest.add_argument(
        "--command",
        required=True,
        help="Exact ingestion command or run description to record in the manifest.",
    )
    sign_ingest.add_argument(
        "--file",
        type=Path,
        action="append",
        help="Specific artifact file to include; defaults to inferred scope artifacts.",
    )
    sign_ingest.add_argument(
        "--deleted-file",
        type=Path,
        action="append",
        help="Deleted artifact path to mark as removed in the signed manifest.",
    )
    sign_ingest.add_argument(
        "--reasoning-log",
        type=Path,
        action="append",
        help="Optional reasoning or run log file to hash into the manifest.",
    )
    sign_ingest.add_argument("--output", type=Path)
    sign_ingest.add_argument("--key-id", default="axiom-corpus-ingest-v1")
    sign_ingest.set_defaults(func=_cmd_sign_ingest_manifest)

    guard_ingested = sub.add_parser(
        "guard-ingested",
        help="Reject generated corpus artifact changes without signed ingest manifests.",
    )
    guard_ingested.add_argument("--repo", type=Path, default=Path("."))
    guard_ingested.add_argument("--base-ref")
    guard_ingested.add_argument("--head-ref", default="HEAD")
    guard_ingested.add_argument("--json", action="store_true")
    guard_ingested.set_defaults(func=_cmd_guard_ingested)

    verify_tracked = sub.add_parser(
        "verify-scope-tracked",
        help="Reject inventory or signed-manifest references to untracked files.",
    )
    verify_tracked.add_argument("--repo", type=Path, default=Path("."))
    verify_tracked.add_argument("--jurisdiction")
    verify_tracked.add_argument("--document-class")
    verify_tracked.add_argument("--version")
    verify_tracked.set_defaults(func=_cmd_verify_scope_tracked)

    inventory_ecfr = sub.add_parser(
        "inventory-ecfr",
        help="Build a source inventory from eCFR structure JSON.",
    )
    inventory_ecfr.add_argument("--base", type=Path, required=True)
    inventory_ecfr.add_argument("--version", "--run-id", dest="version", required=True)
    inventory_ecfr.add_argument("--as-of", required=True)
    inventory_ecfr.add_argument("--only-title", type=int)
    inventory_ecfr.add_argument("--only-part")
    inventory_ecfr.add_argument("--limit", type=int)
    inventory_ecfr.set_defaults(func=_cmd_inventory_ecfr)

    inventory_usc = sub.add_parser(
        "inventory-usc",
        help="Build a source inventory from official USLM XML for one US Code title.",
    )
    inventory_usc.add_argument("--base", type=Path, required=True)
    inventory_usc.add_argument("--version", "--run-id", dest="version", required=True)
    inventory_usc.add_argument("--source-xml", type=Path, required=True)
    inventory_usc.add_argument("--title")
    inventory_usc.add_argument("--source-url")
    inventory_usc.add_argument("--limit", type=int)
    inventory_usc.add_argument(
        "--section",
        action="append",
        default=[],
        help="US Code section to include; repeat for multiple sections.",
    )
    inventory_usc.add_argument(
        "--citation-path",
        action="append",
        default=[],
        help="Exact corpus citation path to include; repeat for multiple paths.",
    )
    inventory_usc.add_argument(
        "--include-title",
        action="store_true",
        help="Include the title-level provision when section filters are used.",
    )
    inventory_usc.set_defaults(func=_cmd_inventory_usc)

    extract_ecfr_cmd = sub.add_parser(
        "extract-ecfr",
        help="Snapshot eCFR source XML and extract normalized provision JSONL.",
    )
    extract_ecfr_cmd.add_argument("--base", type=Path, required=True)
    extract_ecfr_cmd.add_argument("--version", required=True)
    extract_ecfr_cmd.add_argument("--as-of", required=True)
    extract_ecfr_cmd.add_argument("--expression-date")
    extract_ecfr_cmd.add_argument("--only-title", type=int)
    extract_ecfr_cmd.add_argument("--only-part")
    extract_ecfr_cmd.add_argument("--limit", type=int)
    extract_ecfr_cmd.add_argument("--workers", type=int, default=2)
    extract_ecfr_cmd.add_argument(
        "--graphic-transcriptions",
        type=Path,
        help=(
            "Reviewed SHA-256-bound transcriptions for image-only eCFR formulas. "
            "Formula images are archived even when no transcription is supplied."
        ),
    )
    extract_ecfr_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_ecfr_cmd.set_defaults(func=_cmd_extract_ecfr)

    extract_usc_cmd = sub.add_parser(
        "extract-usc",
        help="Snapshot USLM XML and extract normalized US Code provision JSONL.",
    )
    extract_usc_cmd.add_argument("--base", type=Path, required=True)
    extract_usc_cmd.add_argument("--version", required=True)
    extract_usc_cmd.add_argument("--source-xml", type=Path, required=True)
    extract_usc_cmd.add_argument("--title")
    extract_usc_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_usc_cmd.add_argument("--expression-date")
    extract_usc_cmd.add_argument("--source-url")
    extract_usc_cmd.add_argument("--limit", type=int)
    extract_usc_cmd.add_argument(
        "--section",
        action="append",
        default=[],
        help="US Code section to extract; repeat for multiple sections.",
    )
    extract_usc_cmd.add_argument(
        "--citation-path",
        action="append",
        default=[],
        help="Exact corpus citation path to extract; repeat for multiple paths.",
    )
    extract_usc_cmd.add_argument(
        "--include-title",
        action="store_true",
        help="Include the title-level provision when section filters are used.",
    )
    extract_usc_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_usc_cmd.set_defaults(func=_cmd_extract_usc)

    extract_usc_dir_cmd = sub.add_parser(
        "extract-usc-dir",
        help="Snapshot a directory of USLM XML files and extract combined US Code provision JSONL.",
    )
    extract_usc_dir_cmd.add_argument("--base", type=Path, required=True)
    extract_usc_dir_cmd.add_argument("--version", required=True)
    extract_usc_dir_cmd.add_argument("--source-dir", type=Path, required=True)
    extract_usc_dir_cmd.add_argument("--only-title")
    extract_usc_dir_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_usc_dir_cmd.add_argument("--expression-date")
    extract_usc_dir_cmd.add_argument("--source-url")
    extract_usc_dir_cmd.add_argument("--limit", type=int)
    extract_usc_dir_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_usc_dir_cmd.set_defaults(func=_cmd_extract_usc_dir)

    extract_uk_cmd = sub.add_parser(
        "extract-uk-legislation",
        help="Snapshot UK legislation text and extract normalized provision JSONL.",
    )
    extract_uk_cmd.add_argument("--base", type=Path, required=True)
    extract_uk_cmd.add_argument("--version", required=True)
    extract_uk_cmd.add_argument(
        "--source-xml",
        type=Path,
        action="append",
        help="Local legislation.gov.uk CLML section/regulation XML file.",
    )
    extract_uk_cmd.add_argument(
        "--citation",
        action="append",
        help=(
            "Fetch a UK citation. With --source lex, act-level (ukpga/2007/3) "
            "ingests every section; section-level (ukpga/2007/3/section/35) "
            "ingests one. CLML requires section-level."
        ),
    )
    extract_uk_cmd.add_argument(
        "--source",
        choices=("clml", "lex"),
        default="clml",
        help="Backend for --citation fetches (default: clml).",
    )
    extract_uk_cmd.add_argument(
        "--lex-limit",
        type=int,
        default=None,
        help="Max sections to request per act from Lex (default: act provision count).",
    )
    extract_uk_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_uk_cmd.add_argument("--expression-date")
    extract_uk_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_uk_cmd.set_defaults(func=_cmd_extract_uk_legislation)

    extract_nz_cmd = sub.add_parser(
        "extract-nz-legislation",
        help="Snapshot NZ PCO XML and extract normalized provision JSONL.",
    )
    extract_nz_cmd.add_argument("--base", type=Path, required=True)
    extract_nz_cmd.add_argument("--version", required=True)
    extract_nz_cmd.add_argument(
        "--source-xml",
        type=Path,
        action="append",
        help="Local legislation.govt.nz PCO XML file.",
    )
    extract_nz_cmd.add_argument(
        "--source-dir",
        type=Path,
        help="Directory containing legislation.govt.nz PCO XML files.",
    )
    extract_nz_cmd.add_argument(
        "--source-pattern",
        default="*.xml",
        help="Glob used with --source-dir (default: *.xml).",
    )
    extract_nz_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_nz_cmd.add_argument("--expression-date")
    extract_nz_cmd.add_argument("--limit", type=int)
    extract_nz_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_nz_cmd.set_defaults(func=_cmd_extract_nz_legislation)

    extract_be_cmd = sub.add_parser(
        "extract-belgian-eli",
        help="Snapshot Belgian ELI/Moniteur/Justel HTML and extract normalized provision JSONL.",
    )
    extract_be_cmd.add_argument("--base", type=Path, required=True)
    extract_be_cmd.add_argument("--version", required=True)
    extract_be_cmd.add_argument(
        "--manifest",
        type=Path,
        help="Corpus manifest containing belgian-eli source URLs.",
    )
    extract_be_cmd.add_argument(
        "--source-html",
        type=Path,
        action="append",
        help="Local Belgian ELI, Moniteur, or Justel HTML file.",
    )
    extract_be_cmd.add_argument(
        "--source-dir",
        type=Path,
        help="Directory containing Belgian ELI, Moniteur, or Justel HTML files.",
    )
    extract_be_cmd.add_argument(
        "--source-pattern",
        default="*.html",
        help="Glob used with --source-dir (default: *.html).",
    )
    extract_be_cmd.add_argument(
        "--source-url",
        action="append",
        help="Belgian ELI, Moniteur, or Justel URL to fetch; repeat for multiple URLs.",
    )
    extract_be_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_be_cmd.add_argument("--expression-date")
    extract_be_cmd.add_argument("--request-timeout", type=float, default=30.0)
    extract_be_cmd.add_argument("--limit", type=int)
    extract_be_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_be_cmd.set_defaults(func=_cmd_extract_belgian_eli)

    extract_de_cmd = sub.add_parser(
        "extract-de-gii",
        help=(
            "Fetch gesetze-im-internet.de juris XML for German federal statutes "
            "and extract per-section normalized provision JSONL."
        ),
    )
    extract_de_cmd.add_argument("--base", type=Path, required=True)
    extract_de_cmd.add_argument("--version", required=True)
    extract_de_cmd.add_argument(
        "--manifest",
        type=Path,
        help="gesetze-im-internet official-documents manifest listing law slugs.",
    )
    extract_de_cmd.add_argument(
        "--source-xml",
        type=Path,
        action="append",
        help="Local juris XML or xml.zip file; the law slug is the filename stem.",
    )
    extract_de_cmd.add_argument(
        "--source-dir",
        type=Path,
        help="Directory of local juris XML/zip files (slug = filename stem).",
    )
    extract_de_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_de_cmd.add_argument("--expression-date")
    extract_de_cmd.add_argument("--request-timeout", type=float, default=60.0)
    extract_de_cmd.add_argument("--limit", type=int)
    extract_de_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_de_cmd.set_defaults(func=_cmd_extract_de_gii)

    discover_be_cmd = sub.add_parser(
        "discover-belgian-moniteur",
        help=(
            "Discover Moniteur belge statute/regulation article URLs from "
            "official daily summary pages."
        ),
    )
    discover_be_cmd.add_argument("--start-date", required=True)
    discover_be_cmd.add_argument("--end-date", required=True)
    discover_be_cmd.add_argument("--version", required=True)
    discover_be_cmd.add_argument("--language", default="fr")
    discover_be_cmd.add_argument("--request-timeout", type=float, default=30.0)
    discover_be_cmd.add_argument("--limit", type=int)
    discover_be_cmd.add_argument("--max-editions", type=int, default=5)
    discover_be_cmd.add_argument(
        "--manifest-output",
        type=Path,
        help="Optional corpus manifest path to write for extract-belgian-eli.",
    )
    discover_be_cmd.set_defaults(func=_cmd_discover_belgian_moniteur)

    download_nz_api_cmd = sub.add_parser(
        "download-nz-legislation-api",
        help="Discover and download NZ Legislation API XML format URLs.",
    )
    download_nz_api_cmd.add_argument("--output-dir", type=Path, required=True)
    download_nz_api_cmd.add_argument(
        "--api-key-env",
        default=NZ_LEGISLATION_API_KEY_ENV,
        help=f"Environment variable containing the API key (default: {NZ_LEGISLATION_API_KEY_ENV}).",
    )
    download_nz_api_cmd.add_argument(
        "--legislation-type",
        action="append",
        choices=NZ_LEGISLATION_DEFAULT_TYPES,
        help="Legislation type to discover. May be repeated; defaults to all supported types.",
    )
    download_nz_api_cmd.add_argument(
        "--publisher",
        default="Parliamentary Counsel Office",
        help="API publisher filter (default: Parliamentary Counsel Office).",
    )
    download_nz_api_cmd.add_argument(
        "--search-term",
        help="Optional title search term for scoped discovery smoke runs.",
    )
    download_nz_api_cmd.add_argument("--per-page", type=int, default=100)
    download_nz_api_cmd.add_argument("--max-pages", type=int)
    download_nz_api_cmd.add_argument("--limit", type=int)
    download_nz_api_cmd.add_argument("--manifest-path", type=Path)
    download_nz_api_cmd.add_argument("--no-resume", action="store_true")
    download_nz_api_cmd.add_argument("--allow-failures", action="store_true")
    download_nz_api_cmd.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Concurrent XML download workers (default: 1).",
    )
    download_nz_api_cmd.set_defaults(func=_cmd_download_nz_legislation_api)

    extract_dc_cmd = sub.add_parser(
        "extract-dc-code",
        help="Snapshot local DC Code XML and extract normalized provision JSONL.",
    )
    extract_dc_cmd.add_argument("--base", type=Path, required=True)
    extract_dc_cmd.add_argument("--version", required=True)
    extract_dc_cmd.add_argument("--source-dir", type=Path, required=True)
    extract_dc_cmd.add_argument("--only-title")
    extract_dc_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_dc_cmd.add_argument("--expression-date")
    extract_dc_cmd.add_argument("--limit", type=int)
    extract_dc_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_dc_cmd.set_defaults(func=_cmd_extract_dc_code)

    extract_cic_html_cmd = sub.add_parser(
        "extract-cic-state-html",
        help="Snapshot a Public.Resource.org CIC state-code HTML release.",
    )
    extract_cic_html_cmd.add_argument("--base", type=Path, required=True)
    extract_cic_html_cmd.add_argument("--version", required=True)
    extract_cic_html_cmd.add_argument("--jurisdiction", required=True)
    extract_cic_html_cmd.add_argument("--release-dir", type=Path, required=True)
    extract_cic_html_cmd.add_argument("--only-title")
    extract_cic_html_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_cic_html_cmd.add_argument("--expression-date")
    extract_cic_html_cmd.add_argument("--limit", type=int)
    extract_cic_html_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_cic_html_cmd.set_defaults(func=_cmd_extract_cic_html)

    extract_cic_odt_cmd = sub.add_parser(
        "extract-cic-state-odt",
        help="Snapshot a Public.Resource.org CIC state-code ODT release.",
    )
    extract_cic_odt_cmd.add_argument("--base", type=Path, required=True)
    extract_cic_odt_cmd.add_argument("--version", required=True)
    extract_cic_odt_cmd.add_argument("--jurisdiction", required=True)
    extract_cic_odt_cmd.add_argument("--release-dir", type=Path, required=True)
    extract_cic_odt_cmd.add_argument("--only-title")
    extract_cic_odt_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_cic_odt_cmd.add_argument("--expression-date")
    extract_cic_odt_cmd.add_argument("--limit", type=int)
    extract_cic_odt_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_cic_odt_cmd.set_defaults(func=_cmd_extract_cic_odt)

    extract_colorado_docx_cmd = sub.add_parser(
        "extract-colorado-docx",
        help="Snapshot the official Colorado CRS DOCX release.",
    )
    extract_colorado_docx_cmd.add_argument("--base", type=Path, required=True)
    extract_colorado_docx_cmd.add_argument("--version", required=True)
    extract_colorado_docx_cmd.add_argument("--release-dir", type=Path, required=True)
    extract_colorado_docx_cmd.add_argument("--only-title")
    extract_colorado_docx_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_colorado_docx_cmd.add_argument("--expression-date")
    extract_colorado_docx_cmd.add_argument("--limit", type=int)
    extract_colorado_docx_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_colorado_docx_cmd.set_defaults(func=_cmd_extract_colorado_docx)

    extract_ohio_revised_code_cmd = sub.add_parser(
        "extract-ohio-revised-code",
        help="Snapshot official Ohio Revised Code HTML.",
    )
    extract_ohio_revised_code_cmd.add_argument("--base", type=Path, required=True)
    extract_ohio_revised_code_cmd.add_argument("--version", required=True)
    extract_ohio_revised_code_cmd.add_argument("--source-dir", type=Path)
    extract_ohio_revised_code_cmd.add_argument("--download-dir", type=Path)
    extract_ohio_revised_code_cmd.add_argument("--only-title")
    extract_ohio_revised_code_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_ohio_revised_code_cmd.add_argument("--expression-date")
    extract_ohio_revised_code_cmd.add_argument("--limit", type=int)
    extract_ohio_revised_code_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_ohio_revised_code_cmd.set_defaults(func=_cmd_extract_ohio_revised_code)

    extract_minnesota_statutes_cmd = sub.add_parser(
        "extract-minnesota-statutes",
        help="Snapshot official Minnesota Statutes HTML.",
    )
    extract_minnesota_statutes_cmd.add_argument("--base", type=Path, required=True)
    extract_minnesota_statutes_cmd.add_argument("--version", required=True)
    extract_minnesota_statutes_cmd.add_argument("--source-dir", type=Path)
    extract_minnesota_statutes_cmd.add_argument("--download-dir", type=Path)
    extract_minnesota_statutes_cmd.add_argument("--only-title")
    extract_minnesota_statutes_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_minnesota_statutes_cmd.add_argument("--expression-date")
    extract_minnesota_statutes_cmd.add_argument("--limit", type=int)
    extract_minnesota_statutes_cmd.add_argument("--workers", type=int, default=4)
    extract_minnesota_statutes_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_minnesota_statutes_cmd.set_defaults(func=_cmd_extract_minnesota_statutes)

    extract_nebraska_statutes_cmd = sub.add_parser(
        "extract-nebraska-revised-statutes",
        help="Snapshot official Nebraska Revised Statutes HTML.",
    )
    extract_nebraska_statutes_cmd.add_argument("--base", type=Path, required=True)
    extract_nebraska_statutes_cmd.add_argument("--version", required=True)
    extract_nebraska_statutes_cmd.add_argument("--source-dir", type=Path)
    extract_nebraska_statutes_cmd.add_argument("--download-dir", type=Path)
    extract_nebraska_statutes_cmd.add_argument("--only-title")
    extract_nebraska_statutes_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_nebraska_statutes_cmd.add_argument("--expression-date")
    extract_nebraska_statutes_cmd.add_argument("--limit", type=int)
    extract_nebraska_statutes_cmd.add_argument("--workers", type=int, default=4)
    extract_nebraska_statutes_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_nebraska_statutes_cmd.set_defaults(func=_cmd_extract_nebraska_revised_statutes)

    extract_washington_rcw_cmd = sub.add_parser(
        "extract-washington-rcw",
        help="Snapshot official Revised Code of Washington HTML.",
    )
    extract_washington_rcw_cmd.add_argument("--base", type=Path, required=True)
    extract_washington_rcw_cmd.add_argument("--version", required=True)
    extract_washington_rcw_cmd.add_argument("--source-dir", type=Path)
    extract_washington_rcw_cmd.add_argument("--download-dir", type=Path)
    extract_washington_rcw_cmd.add_argument("--only-title")
    extract_washington_rcw_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_washington_rcw_cmd.add_argument("--expression-date")
    extract_washington_rcw_cmd.add_argument("--limit", type=int)
    extract_washington_rcw_cmd.add_argument("--workers", type=int, default=4)
    extract_washington_rcw_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_washington_rcw_cmd.set_defaults(func=_cmd_extract_washington_rcw)

    extract_illinois_ilcs_cmd = sub.add_parser(
        "extract-illinois-ilcs",
        help="Snapshot official Illinois ILCS FTP HTML.",
    )
    extract_illinois_ilcs_cmd.add_argument("--base", type=Path, required=True)
    extract_illinois_ilcs_cmd.add_argument("--version", required=True)
    extract_illinois_ilcs_cmd.add_argument("--source-dir", type=Path)
    extract_illinois_ilcs_cmd.add_argument("--only-chapter")
    extract_illinois_ilcs_cmd.add_argument("--only-act")
    extract_illinois_ilcs_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_illinois_ilcs_cmd.add_argument("--expression-date")
    extract_illinois_ilcs_cmd.add_argument("--limit", type=int)
    extract_illinois_ilcs_cmd.add_argument("--workers", type=int, default=8)
    extract_illinois_ilcs_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_illinois_ilcs_cmd.set_defaults(func=_cmd_extract_illinois_ilcs)

    extract_canada_acts_cmd = sub.add_parser(
        "extract-canada-acts",
        help="Snapshot Canadian federal acts from laws-lois.justice.gc.ca.",
    )
    extract_canada_acts_cmd.add_argument("--base", type=Path, required=True)
    extract_canada_acts_cmd.add_argument("--version", required=True)
    extract_canada_acts_cmd.add_argument(
        "--only-act",
        action="append",
        default=[],
        help=("Restrict the extract to a specific consolidated number (e.g. I-3.3). Repeatable."),
    )
    extract_canada_acts_cmd.add_argument(
        "--limit-acts",
        type=int,
        help="Stop after this many acts (after enumerating).",
    )
    extract_canada_acts_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_canada_acts_cmd.add_argument("--expression-date")
    extract_canada_acts_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_canada_acts_cmd.set_defaults(func=_cmd_extract_canada_acts)

    extract_indiana_code_cmd = sub.add_parser(
        "extract-indiana-code",
        help="Snapshot official Indiana Code HTML.",
    )
    extract_indiana_code_cmd.add_argument("--base", type=Path, required=True)
    extract_indiana_code_cmd.add_argument("--version", required=True)
    extract_indiana_code_cmd.add_argument("--source-dir", type=Path)
    extract_indiana_code_cmd.add_argument("--source-zip", type=Path)
    extract_indiana_code_cmd.add_argument(
        "--source-year",
        type=int,
        default=INDIANA_CODE_DEFAULT_YEAR,
    )
    extract_indiana_code_cmd.add_argument("--download-dir", type=Path)
    extract_indiana_code_cmd.add_argument("--only-title")
    extract_indiana_code_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_indiana_code_cmd.add_argument("--expression-date")
    extract_indiana_code_cmd.add_argument("--limit", type=int)
    extract_indiana_code_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_indiana_code_cmd.set_defaults(func=_cmd_extract_indiana_code)

    extract_montana_code_cmd = sub.add_parser(
        "extract-montana-code",
        help="Snapshot official Montana Code Annotated HTML.",
    )
    extract_montana_code_cmd.add_argument("--base", type=Path, required=True)
    extract_montana_code_cmd.add_argument("--version", required=True)
    extract_montana_code_cmd.add_argument("--source-dir", type=Path)
    extract_montana_code_cmd.add_argument(
        "--source-year",
        type=int,
        default=MONTANA_CODE_DEFAULT_YEAR,
    )
    extract_montana_code_cmd.add_argument("--download-dir", type=Path)
    extract_montana_code_cmd.add_argument("--only-title")
    extract_montana_code_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_montana_code_cmd.add_argument("--expression-date")
    extract_montana_code_cmd.add_argument("--limit", type=int)
    extract_montana_code_cmd.add_argument("--workers", type=int, default=8)
    extract_montana_code_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_montana_code_cmd.set_defaults(func=_cmd_extract_montana_code)

    extract_nevada_nrs_cmd = sub.add_parser(
        "extract-nevada-nrs",
        help="Snapshot official Nevada Revised Statutes HTML.",
    )
    extract_nevada_nrs_cmd.add_argument("--base", type=Path, required=True)
    extract_nevada_nrs_cmd.add_argument("--version", required=True)
    extract_nevada_nrs_cmd.add_argument("--source-dir", type=Path)
    extract_nevada_nrs_cmd.add_argument(
        "--source-year",
        type=int,
        default=NEVADA_NRS_DEFAULT_YEAR,
    )
    extract_nevada_nrs_cmd.add_argument("--download-dir", type=Path)
    extract_nevada_nrs_cmd.add_argument("--only-title")
    extract_nevada_nrs_cmd.add_argument("--only-chapter")
    extract_nevada_nrs_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_nevada_nrs_cmd.add_argument("--expression-date")
    extract_nevada_nrs_cmd.add_argument("--limit", type=int)
    extract_nevada_nrs_cmd.add_argument("--workers", type=int, default=8)
    extract_nevada_nrs_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_nevada_nrs_cmd.set_defaults(func=_cmd_extract_nevada_nrs)

    extract_new_york_cmd = sub.add_parser(
        "extract-new-york-consolidated-laws",
        help="Snapshot official New York Senate OpenLegislation HTML.",
    )
    extract_new_york_cmd.add_argument("--base", type=Path, required=True)
    extract_new_york_cmd.add_argument("--version", required=True)
    extract_new_york_cmd.add_argument("--source-dir", type=Path)
    extract_new_york_cmd.add_argument("--download-dir", type=Path)
    extract_new_york_cmd.add_argument("--only-title")
    extract_new_york_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_new_york_cmd.add_argument("--expression-date")
    extract_new_york_cmd.add_argument("--limit", type=int)
    extract_new_york_cmd.add_argument("--workers", type=int, default=1)
    extract_new_york_cmd.add_argument("--request-delay-seconds", type=float, default=0.35)
    extract_new_york_cmd.add_argument("--timeout-seconds", type=float, default=15.0)
    extract_new_york_cmd.add_argument("--request-attempts", type=int, default=2)
    extract_new_york_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_new_york_cmd.set_defaults(func=_cmd_extract_new_york_consolidated_laws)

    extract_new_york_api_cmd = sub.add_parser(
        "extract-new-york-openleg-api",
        help="Snapshot official New York OpenLegislation law JSON.",
    )
    extract_new_york_api_cmd.add_argument("--base", type=Path, required=True)
    extract_new_york_api_cmd.add_argument("--version", required=True)
    extract_new_york_api_cmd.add_argument("--source-dir", type=Path)
    extract_new_york_api_cmd.add_argument("--download-dir", type=Path)
    extract_new_york_api_cmd.add_argument("--only-title")
    extract_new_york_api_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_new_york_api_cmd.add_argument("--expression-date")
    extract_new_york_api_cmd.add_argument("--limit", type=int)
    extract_new_york_api_cmd.add_argument(
        "--api-key-env",
        default="NYSENATE_OPENLEG_API_KEY",
    )
    extract_new_york_api_cmd.add_argument(
        "--api-base-url",
        default="https://legislation.nysenate.gov",
    )
    extract_new_york_api_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_new_york_api_cmd.set_defaults(func=_cmd_extract_new_york_openleg_api)

    extract_new_york_sections_cmd = sub.add_parser(
        "extract-new-york-openleg-sections",
        help=(
            "Snapshot selected official New York OpenLegislation sections "
            "(for example Tax Law Article 22 personal-income-tax sections) "
            "without walking a whole law."
        ),
    )
    extract_new_york_sections_cmd.add_argument("--base", type=Path, required=True)
    extract_new_york_sections_cmd.add_argument("--version", required=True)
    extract_new_york_sections_cmd.add_argument(
        "--section",
        action="append",
        required=True,
        help="New York section spec such as TAX:601 or an OpenLegislation URL.",
    )
    extract_new_york_sections_cmd.add_argument("--source-dir", type=Path)
    extract_new_york_sections_cmd.add_argument("--download-dir", type=Path)
    extract_new_york_sections_cmd.add_argument(
        "--source-as-of", "--as-of", dest="source_as_of"
    )
    extract_new_york_sections_cmd.add_argument("--expression-date")
    extract_new_york_sections_cmd.add_argument(
        "--api-key-env",
        default="NYSENATE_OPENLEG_API_KEY",
    )
    extract_new_york_sections_cmd.add_argument(
        "--api-base-url",
        default="https://legislation.nysenate.gov",
    )
    extract_new_york_sections_cmd.add_argument(
        "--allow-incomplete", action="store_true"
    )
    extract_new_york_sections_cmd.set_defaults(
        func=_cmd_extract_new_york_openleg_sections
    )

    extract_nyc_admin_code_cmd = sub.add_parser(
        "extract-nyc-admin-code",
        help="Snapshot selected NYC Administrative Code section HTML from CodeLibrary.",
    )
    extract_nyc_admin_code_cmd.add_argument("--base", type=Path, required=True)
    extract_nyc_admin_code_cmd.add_argument("--version", required=True)
    extract_nyc_admin_code_cmd.add_argument("--source-dir", type=Path)
    extract_nyc_admin_code_cmd.add_argument("--download-dir", type=Path)
    extract_nyc_admin_code_cmd.add_argument(
        "--section",
        action="append",
        help="NYC Administrative Code section to extract; defaults to the NYC income-tax core sections.",
    )
    extract_nyc_admin_code_cmd.add_argument(
        "--url",
        action="append",
        help="Additional SECTION=URL mapping for a CodeLibrary section page.",
    )
    extract_nyc_admin_code_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_nyc_admin_code_cmd.add_argument("--expression-date")
    extract_nyc_admin_code_cmd.add_argument("--timeout-seconds", type=float, default=20.0)
    extract_nyc_admin_code_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_nyc_admin_code_cmd.set_defaults(func=_cmd_extract_nyc_admin_code)

    extract_delaware_code_cmd = sub.add_parser(
        "extract-delaware-code",
        help="Snapshot official Delaware Code HTML.",
    )
    extract_delaware_code_cmd.add_argument("--base", type=Path, required=True)
    extract_delaware_code_cmd.add_argument("--version", required=True)
    extract_delaware_code_cmd.add_argument("--source-dir", type=Path)
    extract_delaware_code_cmd.add_argument("--download-dir", type=Path)
    extract_delaware_code_cmd.add_argument("--only-title")
    extract_delaware_code_cmd.add_argument("--only-chapter")
    extract_delaware_code_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_delaware_code_cmd.add_argument("--expression-date")
    extract_delaware_code_cmd.add_argument("--limit", type=int)
    extract_delaware_code_cmd.add_argument("--workers", type=int, default=1)
    extract_delaware_code_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_delaware_code_cmd.set_defaults(func=_cmd_extract_delaware_code)

    extract_oregon_ors_cmd = sub.add_parser(
        "extract-oregon-ors",
        help="Snapshot official Oregon Revised Statutes HTML.",
    )
    extract_oregon_ors_cmd.add_argument("--base", type=Path, required=True)
    extract_oregon_ors_cmd.add_argument("--version", required=True)
    extract_oregon_ors_cmd.add_argument("--source-dir", type=Path)
    extract_oregon_ors_cmd.add_argument(
        "--source-year",
        type=int,
        default=OREGON_ORS_DEFAULT_YEAR,
    )
    extract_oregon_ors_cmd.add_argument("--download-dir", type=Path)
    extract_oregon_ors_cmd.add_argument("--only-title")
    extract_oregon_ors_cmd.add_argument("--only-chapter")
    extract_oregon_ors_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_oregon_ors_cmd.add_argument("--expression-date")
    extract_oregon_ors_cmd.add_argument("--limit", type=int)
    extract_oregon_ors_cmd.add_argument("--workers", type=int, default=8)
    extract_oregon_ors_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_oregon_ors_cmd.set_defaults(func=_cmd_extract_oregon_ors)

    extract_rhode_island_cmd = sub.add_parser(
        "extract-rhode-island-general-laws",
        help="Snapshot official Rhode Island General Laws HTML.",
    )
    extract_rhode_island_cmd.add_argument("--base", type=Path, required=True)
    extract_rhode_island_cmd.add_argument("--version", required=True)
    extract_rhode_island_cmd.add_argument("--source-dir", type=Path)
    extract_rhode_island_cmd.add_argument(
        "--source-year",
        type=int,
        default=RHODE_ISLAND_GENERAL_LAWS_DEFAULT_YEAR,
    )
    extract_rhode_island_cmd.add_argument("--download-dir", type=Path)
    extract_rhode_island_cmd.add_argument("--only-title")
    extract_rhode_island_cmd.add_argument("--only-chapter")
    extract_rhode_island_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_rhode_island_cmd.add_argument("--expression-date")
    extract_rhode_island_cmd.add_argument("--limit", type=int)
    extract_rhode_island_cmd.add_argument("--workers", type=int, default=8)
    extract_rhode_island_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_rhode_island_cmd.set_defaults(func=_cmd_extract_rhode_island_general_laws)

    extract_california_codes_cmd = sub.add_parser(
        "extract-california-codes",
        help="Snapshot official California Legislative Counsel bulk code data.",
    )
    extract_california_codes_cmd.add_argument("--base", type=Path, required=True)
    extract_california_codes_cmd.add_argument("--version", required=True)
    extract_california_codes_cmd.add_argument("--source-zip", type=Path)
    extract_california_codes_cmd.add_argument(
        "--source-url",
        default="https://downloads.leginfo.legislature.ca.gov/pubinfo_2025.zip",
    )
    extract_california_codes_cmd.add_argument("--download-dir", type=Path)
    extract_california_codes_cmd.add_argument("--only-title")
    extract_california_codes_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_california_codes_cmd.add_argument("--expression-date")
    extract_california_codes_cmd.add_argument("--limit", type=int)
    extract_california_codes_cmd.add_argument("--include-inactive", action="store_true")
    extract_california_codes_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_california_codes_cmd.set_defaults(func=_cmd_extract_california_codes_bulk)

    extract_california_sections_cmd = sub.add_parser(
        "extract-california-code-sections",
        help="Snapshot selected official California Legislative Counsel code sections.",
    )
    extract_california_sections_cmd.add_argument("--base", type=Path, required=True)
    extract_california_sections_cmd.add_argument("--version", required=True)
    extract_california_sections_cmd.add_argument(
        "--section",
        action="append",
        required=True,
        help="California section spec such as WIC:11450.12 or a LegInfo section URL.",
    )
    extract_california_sections_cmd.add_argument("--download-dir", type=Path)
    extract_california_sections_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_california_sections_cmd.add_argument("--expression-date")
    extract_california_sections_cmd.add_argument("--delay-seconds", type=float, default=0.25)
    extract_california_sections_cmd.add_argument("--timeout-seconds", type=float, default=60.0)
    extract_california_sections_cmd.add_argument("--request-attempts", type=int, default=3)
    extract_california_sections_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_california_sections_cmd.set_defaults(func=_cmd_extract_california_code_sections)

    extract_texas_tcas_cmd = sub.add_parser(
        "extract-texas-tcas",
        help="Snapshot official Texas statutes from the TCSS API/resources.",
    )
    extract_texas_tcas_cmd.add_argument("--base", type=Path, required=True)
    extract_texas_tcas_cmd.add_argument("--version", required=True)
    extract_texas_tcas_cmd.add_argument("--source-dir", type=Path)
    extract_texas_tcas_cmd.add_argument("--download-dir", type=Path)
    extract_texas_tcas_cmd.add_argument("--only-title")
    extract_texas_tcas_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_texas_tcas_cmd.add_argument("--expression-date")
    extract_texas_tcas_cmd.add_argument("--limit", type=int)
    extract_texas_tcas_cmd.add_argument("--workers", type=int, default=4)
    extract_texas_tcas_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_texas_tcas_cmd.set_defaults(func=_cmd_extract_texas_tcas)

    extract_state_statutes_cmd = sub.add_parser(
        "extract-state-statutes",
        help="Run state statute extract adapters from a corpus manifest.",
    )
    extract_state_statutes_cmd.add_argument("--base", type=Path, required=True)
    extract_state_statutes_cmd.add_argument("--manifest", type=Path, required=True)
    extract_state_statutes_cmd.add_argument("--only-jurisdiction", action="append", default=[])
    extract_state_statutes_cmd.add_argument("--only-source-id", action="append", default=[])
    extract_state_statutes_cmd.add_argument("--limit-per-source", type=int)
    extract_state_statutes_cmd.add_argument("--dry-run", action="store_true")
    extract_state_statutes_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_state_statutes_cmd.set_defaults(func=_cmd_extract_state_statutes)

    extract_colorado_ccr_cmd = sub.add_parser(
        "extract-colorado-ccr",
        help="Snapshot current Colorado Code of Regulations PDFs.",
    )
    extract_colorado_ccr_cmd.add_argument("--base", type=Path, required=True)
    extract_colorado_ccr_cmd.add_argument("--version", required=True)
    extract_colorado_ccr_cmd.add_argument("--only-series")
    extract_colorado_ccr_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_colorado_ccr_cmd.add_argument("--expression-date")
    extract_colorado_ccr_cmd.add_argument("--limit", type=int)
    extract_colorado_ccr_cmd.add_argument("--workers", type=int, default=4)
    extract_colorado_ccr_cmd.add_argument("--release-dir", type=Path)
    extract_colorado_ccr_cmd.add_argument("--download-dir", type=Path)
    extract_colorado_ccr_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_colorado_ccr_cmd.set_defaults(func=_cmd_extract_colorado_ccr)

    extract_washington_wac_cmd = sub.add_parser(
        "extract-washington-wac",
        help="Snapshot current Washington Administrative Code HTML.",
    )
    extract_washington_wac_cmd.add_argument("--base", type=Path, required=True)
    extract_washington_wac_cmd.add_argument("--version", required=True)
    extract_washington_wac_cmd.add_argument("--source-dir", type=Path)
    extract_washington_wac_cmd.add_argument("--download-dir", type=Path)
    extract_washington_wac_cmd.add_argument("--only-title")
    extract_washington_wac_cmd.add_argument("--only-chapter")
    extract_washington_wac_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_washington_wac_cmd.add_argument("--expression-date")
    extract_washington_wac_cmd.add_argument("--limit", type=int)
    extract_washington_wac_cmd.add_argument("--workers", type=int, default=4)
    extract_washington_wac_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_washington_wac_cmd.set_defaults(func=_cmd_extract_washington_wac)

    extract_virginia_vac_cmd = sub.add_parser(
        "extract-virginia-vac",
        help="Snapshot current Virginia Administrative Code API data.",
    )
    extract_virginia_vac_cmd.add_argument("--base", type=Path, required=True)
    extract_virginia_vac_cmd.add_argument("--version", required=True)
    extract_virginia_vac_cmd.add_argument("--source-dir", type=Path)
    extract_virginia_vac_cmd.add_argument("--download-dir", type=Path)
    extract_virginia_vac_cmd.add_argument("--only-title")
    extract_virginia_vac_cmd.add_argument("--only-agency")
    extract_virginia_vac_cmd.add_argument("--only-chapter")
    extract_virginia_vac_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_virginia_vac_cmd.add_argument("--expression-date")
    extract_virginia_vac_cmd.add_argument("--limit", type=int)
    extract_virginia_vac_cmd.add_argument("--workers", type=int, default=8)
    extract_virginia_vac_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_virginia_vac_cmd.set_defaults(func=_cmd_extract_virginia_vac)

    extract_maryland_comar_cmd = sub.add_parser(
        "extract-maryland-comar",
        help="Snapshot official Maryland COMAR bulk XML.",
    )
    extract_maryland_comar_cmd.add_argument("--base", type=Path, required=True)
    extract_maryland_comar_cmd.add_argument("--version", required=True)
    extract_maryland_comar_cmd.add_argument("--source-dir", type=Path)
    extract_maryland_comar_cmd.add_argument("--download-dir", type=Path)
    extract_maryland_comar_cmd.add_argument("--publication-branch")
    extract_maryland_comar_cmd.add_argument("--only-title")
    extract_maryland_comar_cmd.add_argument("--only-subtitle")
    extract_maryland_comar_cmd.add_argument("--only-chapter")
    extract_maryland_comar_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_maryland_comar_cmd.add_argument("--expression-date")
    extract_maryland_comar_cmd.add_argument("--limit", type=int)
    extract_maryland_comar_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_maryland_comar_cmd.set_defaults(func=_cmd_extract_maryland_comar)

    extract_illinois_admin_code_cmd = sub.add_parser(
        "extract-illinois-admin-code",
        help="Snapshot Illinois Administrative Code HTML.",
    )
    extract_illinois_admin_code_cmd.add_argument("--base", type=Path, required=True)
    extract_illinois_admin_code_cmd.add_argument("--version", required=True)
    extract_illinois_admin_code_cmd.add_argument("--source-dir", type=Path)
    extract_illinois_admin_code_cmd.add_argument("--download-dir", type=Path)
    extract_illinois_admin_code_cmd.add_argument("--only-title")
    extract_illinois_admin_code_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_illinois_admin_code_cmd.add_argument("--expression-date")
    extract_illinois_admin_code_cmd.add_argument("--limit", type=int)
    extract_illinois_admin_code_cmd.add_argument("--workers", type=int, default=8)
    extract_illinois_admin_code_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_illinois_admin_code_cmd.set_defaults(func=_cmd_extract_illinois_admin_code)

    extract_ohio_admin_code_cmd = sub.add_parser(
        "extract-ohio-administrative-code",
        help="Snapshot official Ohio Administrative Code HTML.",
    )
    extract_ohio_admin_code_cmd.add_argument("--base", type=Path, required=True)
    extract_ohio_admin_code_cmd.add_argument("--version", required=True)
    extract_ohio_admin_code_cmd.add_argument("--source-dir", type=Path)
    extract_ohio_admin_code_cmd.add_argument("--download-dir", type=Path)
    extract_ohio_admin_code_cmd.add_argument("--only-agency")
    extract_ohio_admin_code_cmd.add_argument("--only-chapter")
    extract_ohio_admin_code_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_ohio_admin_code_cmd.add_argument("--expression-date")
    extract_ohio_admin_code_cmd.add_argument("--limit", type=int)
    extract_ohio_admin_code_cmd.add_argument("--workers", type=int, default=8)
    extract_ohio_admin_code_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_ohio_admin_code_cmd.set_defaults(func=_cmd_extract_ohio_admin_code)

    extract_oregon_admin_rules_cmd = sub.add_parser(
        "extract-oregon-administrative-rules",
        help="Snapshot official Oregon Administrative Rules HTML.",
    )
    extract_oregon_admin_rules_cmd.add_argument("--base", type=Path, required=True)
    extract_oregon_admin_rules_cmd.add_argument("--version", required=True)
    extract_oregon_admin_rules_cmd.add_argument("--source-dir", type=Path)
    extract_oregon_admin_rules_cmd.add_argument("--download-dir", type=Path)
    extract_oregon_admin_rules_cmd.add_argument("--only-chapter")
    extract_oregon_admin_rules_cmd.add_argument("--only-division")
    extract_oregon_admin_rules_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_oregon_admin_rules_cmd.add_argument("--expression-date")
    extract_oregon_admin_rules_cmd.add_argument("--limit", type=int)
    extract_oregon_admin_rules_cmd.add_argument("--workers", type=int, default=8)
    extract_oregon_admin_rules_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_oregon_admin_rules_cmd.set_defaults(func=_cmd_extract_oregon_admin_rules)

    extract_pennsylvania_code_cmd = sub.add_parser(
        "extract-pennsylvania-code",
        help="Snapshot official Pennsylvania Code HTML.",
    )
    extract_pennsylvania_code_cmd.add_argument("--base", type=Path, required=True)
    extract_pennsylvania_code_cmd.add_argument("--version", required=True)
    extract_pennsylvania_code_cmd.add_argument("--source-dir", type=Path)
    extract_pennsylvania_code_cmd.add_argument("--download-dir", type=Path)
    extract_pennsylvania_code_cmd.add_argument("--only-title")
    extract_pennsylvania_code_cmd.add_argument("--only-chapter")
    extract_pennsylvania_code_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_pennsylvania_code_cmd.add_argument("--expression-date")
    extract_pennsylvania_code_cmd.add_argument("--limit-titles", type=int)
    extract_pennsylvania_code_cmd.add_argument("--limit-chapters", type=int)
    extract_pennsylvania_code_cmd.add_argument("--workers", type=int, default=8)
    extract_pennsylvania_code_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_pennsylvania_code_cmd.set_defaults(func=_cmd_extract_pennsylvania_code)

    extract_montana_admin_rules_cmd = sub.add_parser(
        "extract-montana-administrative-rules",
        aliases=["extract-montana-admin-rules"],
        help="Snapshot official Montana Administrative Rules JSON and HTML.",
    )
    extract_montana_admin_rules_cmd.add_argument("--base", type=Path, required=True)
    extract_montana_admin_rules_cmd.add_argument("--version", required=True)
    extract_montana_admin_rules_cmd.add_argument("--source-dir", type=Path)
    extract_montana_admin_rules_cmd.add_argument("--download-dir", type=Path)
    extract_montana_admin_rules_cmd.add_argument("--only-title")
    extract_montana_admin_rules_cmd.add_argument("--only-section")
    extract_montana_admin_rules_cmd.add_argument(
        "--include-not-effective",
        action="store_true",
        help="Include repealed and otherwise not-effective ARM entries.",
    )
    extract_montana_admin_rules_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_montana_admin_rules_cmd.add_argument("--expression-date")
    extract_montana_admin_rules_cmd.add_argument("--limit-sections", type=int)
    extract_montana_admin_rules_cmd.add_argument("--limit-rules", type=int)
    extract_montana_admin_rules_cmd.add_argument("--workers", type=int, default=12)
    extract_montana_admin_rules_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_montana_admin_rules_cmd.set_defaults(func=_cmd_extract_montana_admin_rules)

    extract_nycrr_cmd = sub.add_parser(
        "extract-nycrr",
        help="Snapshot the public New York Codes, Rules and Regulations tree.",
    )
    extract_nycrr_cmd.add_argument("--base", type=Path, required=True)
    extract_nycrr_cmd.add_argument("--version", required=True)
    extract_nycrr_cmd.add_argument("--only-title", type=int)
    extract_nycrr_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_nycrr_cmd.add_argument("--expression-date")
    extract_nycrr_cmd.add_argument("--limit", type=int)
    extract_nycrr_cmd.add_argument("--delay-seconds", type=float, default=0.25)
    extract_nycrr_cmd.add_argument("--retry-attempts", type=int, default=4)
    extract_nycrr_cmd.add_argument("--refresh", action="store_true")
    extract_nycrr_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_nycrr_cmd.set_defaults(func=_cmd_extract_nycrr)

    extract_california_mpp_cmd = sub.add_parser(
        "extract-california-mpp-calfresh",
        help="Snapshot CDSS MPP Division 63 (CalFresh) DOCX files.",
    )
    extract_california_mpp_cmd.add_argument("--base", type=Path, required=True)
    extract_california_mpp_cmd.add_argument("--version", required=True)
    extract_california_mpp_cmd.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path to manifests/us-ca-cdss-mpp-calfresh.yaml (declares the DOCX source set).",
    )
    extract_california_mpp_cmd.add_argument("--download-dir", type=Path)
    extract_california_mpp_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_california_mpp_cmd.add_argument("--expression-date")
    extract_california_mpp_cmd.add_argument("--delay-seconds", type=float, default=0.25)
    extract_california_mpp_cmd.add_argument("--timeout-seconds", type=float, default=60.0)
    extract_california_mpp_cmd.add_argument("--request-attempts", type=int, default=3)
    extract_california_mpp_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_california_mpp_cmd.set_defaults(func=_cmd_extract_california_mpp_calfresh)

    extract_ny_state_register_cmd = sub.add_parser(
        "extract-ny-state-register",
        help="Snapshot NY Department of State Register issue PDFs.",
    )
    extract_ny_state_register_cmd.add_argument("--base", type=Path, required=True)
    extract_ny_state_register_cmd.add_argument("--version", required=True)
    extract_ny_state_register_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_ny_state_register_cmd.add_argument("--expression-date")
    extract_ny_state_register_cmd.add_argument("--limit", type=int)
    extract_ny_state_register_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_ny_state_register_cmd.set_defaults(func=_cmd_extract_ny_state_register)

    extract_federal_register_cmd = sub.add_parser(
        "extract-federal-register",
        help="Snapshot Federal Register rulemaking and regulatory activity documents.",
    )
    extract_federal_register_cmd.add_argument("--base", type=Path, required=True)
    extract_federal_register_cmd.add_argument("--version", required=True)
    extract_federal_register_cmd.add_argument("--start-date", required=True)
    extract_federal_register_cmd.add_argument(
        "--end-date",
        help="Inclusive publication-date end. Defaults to --start-date.",
    )
    extract_federal_register_cmd.add_argument(
        "--document-type",
        action="append",
        choices=["RULE", "PRORULE", "NOTICE", "PRESDOCU"],
        help=(
            "Federal Register type to include. Repeatable. Defaults to RULE, PRORULE, and NOTICE."
        ),
    )
    extract_federal_register_cmd.add_argument(
        "--term",
        help="Optional Federal Register full-text search term.",
    )
    extract_federal_register_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_federal_register_cmd.add_argument("--expression-date")
    extract_federal_register_cmd.add_argument("--limit", type=int)
    extract_federal_register_cmd.add_argument("--per-page", type=int, default=100)
    extract_federal_register_cmd.add_argument("--skip-full-text", action="store_true")
    extract_federal_register_cmd.add_argument("--timeout-seconds", type=float, default=30.0)
    extract_federal_register_cmd.add_argument("--request-attempts", type=int, default=3)
    extract_federal_register_cmd.add_argument(
        "--request-delay-seconds",
        type=float,
        default=0.1,
    )
    extract_federal_register_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_federal_register_cmd.set_defaults(func=_cmd_extract_federal_register)

    extract_federal_register_cfr_cmd = sub.add_parser(
        "extract-federal-register-cfr-sections",
        help="Slice CFR section records from a saved Federal Register raw-text document.",
    )
    extract_federal_register_cfr_cmd.add_argument("--base", type=Path, required=True)
    extract_federal_register_cfr_cmd.add_argument("--version", required=True)
    extract_federal_register_cfr_cmd.add_argument("--source-text", type=Path, required=True)
    extract_federal_register_cfr_cmd.add_argument(
        "--section",
        action="append",
        required=True,
        help="CFR section to extract, e.g. '42 CFR 431.213' or '42:431:213'.",
    )
    extract_federal_register_cfr_cmd.add_argument("--document-number", required=True)
    extract_federal_register_cfr_cmd.add_argument("--document-citation", required=True)
    extract_federal_register_cfr_cmd.add_argument("--document-title", required=True)
    extract_federal_register_cfr_cmd.add_argument("--document-type", required=True)
    extract_federal_register_cfr_cmd.add_argument("--source-url", required=True)
    extract_federal_register_cfr_cmd.add_argument(
        "--source-as-of",
        "--as-of",
        dest="source_as_of",
        required=True,
    )
    extract_federal_register_cfr_cmd.add_argument("--expression-date", required=True)
    extract_federal_register_cfr_cmd.add_argument("--source-document-citation-path")
    extract_federal_register_cfr_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_federal_register_cfr_cmd.set_defaults(func=_cmd_extract_federal_register_cfr_sections)

    extract_documents_cmd = sub.add_parser(
        "extract-official-documents",
        help="Snapshot official HTML/PDF policy documents from a manifest.",
    )
    extract_documents_cmd.add_argument("--base", type=Path, required=True)
    extract_documents_cmd.add_argument("--version", required=True)
    extract_documents_cmd.add_argument("--manifest", type=Path, required=True)
    extract_documents_cmd.add_argument("--only-source-id")
    extract_documents_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_documents_cmd.add_argument("--expression-date")
    extract_documents_cmd.add_argument("--limit", type=int)
    extract_documents_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_documents_cmd.set_defaults(func=_cmd_extract_official_documents)

    extract_eli_cmd = sub.add_parser(
        "extract-eli-documents",
        help="Snapshot ELI metadata graphs and extract section-level LexDania XML.",
    )
    extract_eli_cmd.add_argument("--base", type=Path, required=True)
    extract_eli_cmd.add_argument("--version", required=True)
    extract_eli_cmd.add_argument("--manifest", type=Path, required=True)
    extract_eli_cmd.add_argument("--only-source-id")
    extract_eli_cmd.add_argument("--source-as-of", "--as-of", dest="source_as_of")
    extract_eli_cmd.add_argument("--expression-date")
    extract_eli_cmd.add_argument("--limit", type=int)
    extract_eli_cmd.add_argument("--allow-superseded", action="store_true")
    extract_eli_cmd.add_argument("--allow-incomplete", action="store_true")
    extract_eli_cmd.set_defaults(func=_cmd_extract_eli_documents)

    reconstruct_nj_snap_cmd = sub.add_parser(
        "reconstruct-new-jersey-snap-rules",
        help="Compile current N.J.A.C. 10:87 SNAP rules from official base and notices.",
    )
    reconstruct_nj_snap_cmd.add_argument("--base", type=Path, required=True)
    reconstruct_nj_snap_cmd.add_argument("--version", required=True)
    reconstruct_nj_snap_cmd.add_argument("--base-provisions", type=Path, required=True)
    reconstruct_nj_snap_cmd.add_argument("--rulemaking-provisions", type=Path, required=True)
    reconstruct_nj_snap_cmd.add_argument(
        "--source-as-of", "--as-of", dest="source_as_of", required=True
    )
    reconstruct_nj_snap_cmd.add_argument("--expression-date", required=True)
    reconstruct_nj_snap_cmd.add_argument("--allow-incomplete", action="store_true")
    reconstruct_nj_snap_cmd.set_defaults(func=_cmd_reconstruct_new_jersey_snap_rules)

    coverage = sub.add_parser(
        "coverage",
        help="Compare source inventory with normalized provision records.",
    )
    coverage.add_argument("--base", type=Path, required=True)
    coverage.add_argument("--source-inventory", type=Path, required=True)
    coverage.add_argument("--provisions", type=Path, required=True)
    coverage.add_argument("--jurisdiction", required=True)
    coverage.add_argument(
        "--document-class",
        choices=[document_class.value for document_class in DocumentClass],
        default=DocumentClass.STATUTE.value,
    )
    coverage.add_argument("--version", required=True)
    coverage.add_argument("--write", action="store_true")
    coverage.add_argument("--allow-incomplete", action="store_true")
    coverage.set_defaults(func=_cmd_coverage)

    export_supabase = sub.add_parser(
        "export-supabase",
        help="Project normalized provision JSONL into corpus.provisions JSONL.",
    )
    export_supabase.add_argument("--provisions", type=Path, required=True)
    export_supabase.add_argument("--output", type=Path, required=True)
    export_supabase.set_defaults(func=_cmd_export_supabase)

    load_supabase = sub.add_parser(
        "load-supabase",
        help=(
            "Stage versioned provision JSONL in corpus.provisions without "
            "changing the active named release."
        ),
    )
    load_supabase.add_argument("--provisions", type=Path, required=True)
    load_supabase.add_argument(
        "--supabase-url",
        default=os.environ.get("AXIOM_SUPABASE_URL", DEFAULT_AXIOM_SUPABASE_URL),
    )
    load_supabase.add_argument("--chunk-size", type=int, default=500)
    load_supabase.add_argument("--dry-run", action="store_true")
    load_supabase.add_argument(
        "--replace-scope",
        action="store_true",
        help=(
            "Delete the JSONL's exact unreleased version scope before staging. "
            "Database immutability guards reject this for released scopes."
        ),
    )
    load_supabase.add_argument("--service-key-env", default=DEFAULT_SERVICE_KEY_ENV)
    load_supabase.add_argument("--access-token-env", default=DEFAULT_ACCESS_TOKEN_ENV)
    load_supabase.add_argument(
        "--build-navigation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Rebuild corpus.navigation_nodes for the loaded scope after the "
            "provisions upsert succeeds. Disabled with --no-build-navigation."
        ),
    )
    load_supabase.add_argument(
        "--preserve-navigation-statuses",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Carry curated corpus.navigation_nodes.status values across the "
            "post-load nav rebuild. Disable with --no-preserve-navigation-statuses."
        ),
    )
    load_supabase.add_argument(
        "--navigation-source",
        choices=("local", "supabase"),
        default="local",
        help=(
            "Input used for post-load navigation rebuilds. Default local builds "
            "from the provisions JSONL just loaded, avoiding a large readback "
            "from Supabase. Use supabase for legacy migration loads that need "
            "database-assigned provision IDs."
        ),
    )
    _add_rulespec_args(load_supabase)
    load_supabase.set_defaults(func=_cmd_load_supabase)

    generate_anchors = sub.add_parser(
        "generate-anchors",
        help=(
            "Generate the derived corpus.provision_anchors leaf layer from an "
            "asserted provisions JSONL. Parses the printed paragraph tree "
            "(--target) and/or wraps stored block leaves (--stored-leaf); every "
            "anchor is verified byte-equal with its label at the span head."
        ),
    )
    generate_anchors.add_argument(
        "--provisions",
        type=Path,
        required=True,
        help="Asserted provisions JSONL to derive anchors from.",
    )
    generate_anchors.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Anchors JSONL to write (mirror the provisions layout under "
        "data/corpus/anchors/).",
    )
    generate_anchors.add_argument(
        "--target",
        action="append",
        default=[],
        help=(
            "Citation path of an asserted provision whose paragraph tree to "
            "parse into inferred leaves (repeatable). Omit --target and "
            "--stored-leaf to parse every provision in the file with a body."
        ),
    )
    generate_anchors.add_argument(
        "--stored-leaf",
        action="append",
        default=[],
        help=(
            "Citation path of a provision that is already a stored block leaf "
            "(e.g. .../365/180/A); emit it machine_asserted plus any run-in "
            "numbered children. Repeatable."
        ),
    )
    generate_anchors.set_defaults(func=_cmd_generate_anchors)

    resolve_anchor = sub.add_parser(
        "resolve-anchor",
        help=(
            "Resolve a citation path to (provision_id, span) over an anchors "
            "JSONL, with descendant/ancestor fallback."
        ),
    )
    resolve_anchor.add_argument("--anchors", type=Path, required=True)
    resolve_anchor.add_argument("citation_path")
    resolve_anchor.set_defaults(func=_cmd_resolve_anchor)

    load_anchors_supabase = sub.add_parser(
        "load-anchors-supabase",
        help=(
            "Upsert a provision_anchors JSONL into corpus.provision_anchors "
            "(optional; keyed on citation_path). Pass --provisions to re-verify "
            "the mechanical gates before loading."
        ),
    )
    load_anchors_supabase.add_argument("--anchors", type=Path, required=True)
    load_anchors_supabase.add_argument(
        "--provisions",
        type=Path,
        default=None,
        help="Parent provisions JSONL; when given, re-verify anchors first.",
    )
    load_anchors_supabase.add_argument(
        "--supabase-url",
        default=os.environ.get("AXIOM_SUPABASE_URL", DEFAULT_AXIOM_SUPABASE_URL),
    )
    load_anchors_supabase.add_argument("--chunk-size", type=int, default=500)
    load_anchors_supabase.add_argument("--dry-run", action="store_true")
    load_anchors_supabase.add_argument(
        "--service-key-env", default=DEFAULT_SERVICE_KEY_ENV
    )
    load_anchors_supabase.add_argument(
        "--access-token-env", default=DEFAULT_ACCESS_TOKEN_ENV
    )
    load_anchors_supabase.set_defaults(func=_cmd_load_anchors_supabase)

    build_navigation = sub.add_parser(
        "build-navigation-index",
        help=(
            "Build (and optionally upsert) corpus.navigation_nodes from a "
            "provisions JSONL or directly from corpus.provisions in Supabase."
        ),
    )
    build_navigation.add_argument(
        "--provisions",
        type=Path,
        action="append",
        default=[],
        help="Path to a provisions JSONL file. Repeatable.",
    )
    build_navigation.add_argument(
        "--from-supabase",
        action="store_true",
        help="Fetch provisions to navigate from Supabase instead of local JSONL.",
    )
    build_navigation.add_argument(
        "--all",
        action="store_true",
        help=(
            "Rebuild every (jurisdiction, doc_type) scope. Requires --from-supabase "
            "or --provisions input."
        ),
    )
    build_navigation.add_argument(
        "--jurisdiction",
        help="Filter provisions/scope to one jurisdiction (e.g. us-co).",
    )
    build_navigation.add_argument(
        "--doc-type",
        choices=[document_class.value for document_class in DocumentClass],
        help="Filter to one document class (e.g. statute, regulation).",
    )
    build_navigation.add_argument(
        "--version",
        help=(
            "Filter to one source/release version when building from Supabase "
            "or explicitly replacing an empty navigation scope."
        ),
    )
    build_navigation.add_argument(
        "--output",
        type=Path,
        help="Optionally write the built navigation rows to JSONL for inspection.",
    )
    build_navigation.add_argument(
        "--replace-scope",
        dest="replace_scope",
        action="store_true",
        default=None,
        help=(
            "Prune stale rows for rebuilt scopes. Defaults to on with "
            "--from-supabase and off with --provisions."
        ),
    )
    build_navigation.add_argument(
        "--no-replace-scope",
        dest="replace_scope",
        action="store_false",
        help="Skip pruning stale rows for rebuilt scopes.",
    )
    build_navigation.add_argument("--chunk-size", type=int, default=500)
    build_navigation.add_argument("--dry-run", action="store_true")
    build_navigation.add_argument(
        "--skip-supabase",
        action="store_true",
        help="Build rows locally without contacting Supabase.",
    )
    build_navigation.add_argument(
        "--supabase-url",
        default=os.environ.get("AXIOM_SUPABASE_URL", DEFAULT_AXIOM_SUPABASE_URL),
    )
    build_navigation.add_argument("--service-key-env", default=DEFAULT_SERVICE_KEY_ENV)
    build_navigation.add_argument("--access-token-env", default=DEFAULT_ACCESS_TOKEN_ENV)
    build_navigation.add_argument(
        "--preserve-statuses",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Carry curated corpus.navigation_nodes.status values across the "
            "rebuild. Disable with --no-preserve-statuses to wipe and rederive."
        ),
    )
    _add_rulespec_args(build_navigation)
    build_navigation.set_defaults(func=_cmd_build_navigation_index)

    snapshot_counts = sub.add_parser(
        "snapshot-provision-counts",
        aliases=["snapshot-supabase-counts"],
        help="Snapshot current-release provision counts from Supabase.",
    )
    snapshot_counts.add_argument(
        "--supabase-url",
        default=os.environ.get("AXIOM_SUPABASE_URL", DEFAULT_AXIOM_SUPABASE_URL),
    )
    snapshot_counts.add_argument("--output", type=Path)
    snapshot_counts.add_argument("--base", type=Path)
    snapshot_counts.add_argument(
        "--release",
        help=(
            "Release manifest name or path. When provided, count matching "
            "corpus.provisions rows directly instead of reading the materialized "
            "current_provision_counts view."
        ),
    )
    snapshot_counts.add_argument(
        "--include-legacy",
        action="store_true",
        help="Read corpus.provision_counts instead of the current-release count view.",
    )
    snapshot_counts.add_argument("--service-key-env", default=DEFAULT_SERVICE_KEY_ENV)
    snapshot_counts.add_argument("--access-token-env", default=DEFAULT_ACCESS_TOKEN_ENV)
    snapshot_counts.set_defaults(func=_cmd_snapshot_provision_counts)

    backfill_versions_cmd = sub.add_parser(
        "backfill-versions",
        help=(
            "Chunked backfill of corpus.provisions.version and "
            "corpus.navigation_nodes.version for single-active release scopes. "
            "Calls corpus.backfill_version_chunk RPC repeatedly until "
            "exhausted. Idempotent and resumable."
        ),
    )
    backfill_versions_cmd.add_argument("--jurisdiction")
    backfill_versions_cmd.add_argument("--doc-type", dest="doc_type")
    backfill_versions_cmd.add_argument(
        "--version",
        help=(
            "If set together with --jurisdiction and --doc-type, "
            "backfill that exact scope. Otherwise auto-discover single-"
            "active scopes."
        ),
    )
    backfill_versions_cmd.add_argument(
        "--table",
        choices=("provisions", "navigation_nodes"),
        help="Restrict to one table. Default: both.",
    )
    backfill_versions_cmd.add_argument(
        "--chunk-size",
        type=int,
        default=10000,
        help=(
            "Rows per RPC call. Default 10000. Larger chunks risk hitting "
            "the pooler's statement_timeout; smaller chunks slow the run."
        ),
    )
    backfill_versions_cmd.add_argument("--dry-run", action="store_true")
    backfill_versions_cmd.add_argument(
        "--supabase-url",
        default=os.environ.get("AXIOM_SUPABASE_URL", DEFAULT_AXIOM_SUPABASE_URL),
    )
    backfill_versions_cmd.add_argument("--service-key-env", default=DEFAULT_SERVICE_KEY_ENV)
    backfill_versions_cmd.add_argument("--access-token-env", default=DEFAULT_ACCESS_TOKEN_ENV)
    backfill_versions_cmd.set_defaults(func=_cmd_backfill_versions)

    verify_release_coverage_cmd = sub.add_parser(
        "verify-release-coverage",
        help=(
            "Check that every jurisdiction × document_class with navigation "
            "rows also has rows in corpus.current_provisions. Exits non-zero "
            "if any jurisdiction is missing — the historical UK regression "
            "(rows in corpus.provisions and navigation_nodes but zero in "
            "current_provisions because release_scopes had no matching row)."
        ),
    )
    verify_release_coverage_cmd.add_argument(
        "--supabase-url",
        default=os.environ.get("AXIOM_SUPABASE_URL", DEFAULT_AXIOM_SUPABASE_URL),
    )
    verify_release_coverage_cmd.add_argument("--service-key-env", default=DEFAULT_SERVICE_KEY_ENV)
    verify_release_coverage_cmd.add_argument("--access-token-env", default=DEFAULT_ACCESS_TOKEN_ENV)
    verify_release_coverage_cmd.set_defaults(func=_cmd_verify_release_coverage)

    analytics = sub.add_parser(
        "analytics",
        help="Summarize source, provision, and Supabase count coverage.",
    )
    analytics.add_argument("--base", type=Path, required=True)
    analytics.add_argument("--version", required=True)
    analytics.add_argument("--supabase-counts", type=Path)
    analytics.add_argument("--jurisdiction", action="append", default=[])
    analytics.add_argument(
        "--document-class",
        action="append",
        choices=[document_class.value for document_class in DocumentClass],
        default=[],
    )
    analytics.add_argument(
        "--default-count-document-class",
        default=DocumentClass.STATUTE.value,
        choices=[document_class.value for document_class in DocumentClass],
    )
    analytics.add_argument("--output", type=Path)
    analytics.add_argument("--write", action="store_true")
    analytics.set_defaults(func=_cmd_analytics)

    sync_r2 = sub.add_parser(
        "sync-r2",
        help="Plan or upload local corpus artifacts to the configured R2 bucket.",
    )
    sync_r2.add_argument("--base", type=Path, required=True)
    sync_r2.add_argument(
        "--prefix",
        action="append",
        choices=list(DEFAULT_ARTIFACT_PREFIXES),
        default=[],
        help="Top-level artifact prefix to include. Repeatable; defaults to all artifact prefixes.",
    )
    sync_r2.add_argument("--bucket")
    sync_r2.add_argument("--endpoint-url")
    sync_r2.add_argument("--credentials-file", type=Path)
    sync_r2.add_argument("--jurisdiction")
    sync_r2.add_argument(
        "--document-class",
        choices=[document_class.value for document_class in DocumentClass],
    )
    sync_r2.add_argument("--version")
    sync_r2.add_argument("--limit", type=int)
    sync_r2.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Concurrent upload workers to use when --apply is set.",
    )
    sync_r2.add_argument(
        "--apply",
        action="store_true",
        help="Upload files. Without this flag the command only prints a dry-run plan.",
    )
    sync_r2.add_argument(
        "--force",
        action="store_true",
        help="Upload matching-size files too.",
    )
    sync_r2.set_defaults(func=_cmd_sync_r2)

    artifact_report = sub.add_parser(
        "artifact-report",
        help="Report local/R2/Supabase artifact coverage by jurisdiction and document class.",
    )
    artifact_report.add_argument("--base", type=Path, required=True)
    artifact_report.add_argument("--version")
    artifact_report.add_argument("--jurisdiction")
    release_group = artifact_report.add_mutually_exclusive_group()
    release_group.add_argument(
        "--release",
        help=(
            "Release manifest name or path. Names resolve to "
            "<base>/releases/<name>.json or manifests/releases/<name>.json."
        ),
    )
    release_group.add_argument(
        "--all-scopes",
        action="store_true",
        help="Report every discovered scope (the default when no named release is supplied).",
    )
    artifact_report.add_argument(
        "--document-class",
        choices=[document_class.value for document_class in DocumentClass],
    )
    artifact_report.add_argument("--supabase-counts", type=Path)
    artifact_report.add_argument(
        "--prefix",
        action="append",
        choices=list(DEFAULT_ARTIFACT_PREFIXES),
        default=[],
        help="Top-level artifact prefix to include. Repeatable; defaults to all artifact prefixes.",
    )
    artifact_report.add_argument("--include-r2", action="store_true")
    artifact_report.add_argument("--bucket")
    artifact_report.add_argument("--endpoint-url")
    artifact_report.add_argument("--credentials-file", type=Path)
    artifact_report.add_argument("--output", type=Path)
    artifact_report.set_defaults(func=_cmd_artifact_report)

    section_provisions_cmd = sub.add_parser(
        "section-provisions",
        help=(
            "Split a scope's monolithic document-level provisions into "
            "per-section child provisions (Part/Step/Schedule markers)."
        ),
    )
    section_provisions_cmd.add_argument("--base", type=Path, required=True)
    section_provisions_cmd.add_argument("--jurisdiction", required=True)
    section_provisions_cmd.add_argument("--document-class", required=True)
    section_provisions_cmd.add_argument("--version", required=True)
    section_provisions_cmd.add_argument(
        "--apply",
        action="store_true",
        help="Rewrite the provisions file (default: dry-run report).",
    )
    section_provisions_cmd.set_defaults(func=_cmd_section_provisions)

    validate_release_cmd = sub.add_parser(
        "validate-release",
        help="Validate release artifacts, coverage, provision invariants, and optional R2/Supabase state.",
    )
    validate_release_cmd.add_argument("--base", type=Path, required=True)
    validate_release_cmd.add_argument("--release", required=True)
    validate_release_cmd.add_argument("--supabase-counts", type=Path)
    validate_release_cmd.add_argument(
        "--prefix",
        action="append",
        choices=list(DEFAULT_RELEASE_ARTIFACT_PREFIXES),
        default=[],
        help="Top-level artifact prefix to include in the artifact report.",
    )
    validate_release_cmd.add_argument("--include-r2", action="store_true")
    validate_release_cmd.add_argument(
        "--ignore-r2-missing",
        action="store_true",
        help=(
            "Do not fail release validation only because local artifacts have "
            "not yet been mirrored to R2. Other artifact mismatches still fail."
        ),
    )
    validate_release_cmd.add_argument("--bucket")
    validate_release_cmd.add_argument("--endpoint-url")
    validate_release_cmd.add_argument("--credentials-file", type=Path)
    validate_release_cmd.add_argument("--strict-warnings", action="store_true")
    validate_release_cmd.add_argument("--max-issues", type=int, default=200)
    validate_release_cmd.add_argument("--output", type=Path)
    validate_release_cmd.set_defaults(func=_cmd_validate_release)

    state_statute_completion = sub.add_parser(
        "state-statute-completion",
        help="Classify 50-state plus DC statute ingestion against a named release.",
    )
    state_statute_completion.add_argument("--base", type=Path, required=True)
    state_statute_completion.add_argument("--release", required=True)
    state_statute_completion.add_argument("--supabase-counts", type=Path)
    state_statute_completion.add_argument(
        "--validation-report",
        type=Path,
        help=(
            "validate-release JSON output. Defaults to "
            "<base>/analytics/validate-release-<release>.json when present."
        ),
    )
    state_statute_completion.add_argument(
        "--prefix",
        action="append",
        choices=list(DEFAULT_RELEASE_ARTIFACT_PREFIXES),
        default=[],
        help="Top-level artifact prefix to inspect. Defaults to release content prefixes.",
    )
    state_statute_completion.add_argument("--include-r2", action="store_true")
    state_statute_completion.add_argument("--bucket")
    state_statute_completion.add_argument("--endpoint-url")
    state_statute_completion.add_argument("--credentials-file", type=Path)
    state_statute_completion.add_argument(
        "--source-access-queue",
        type=Path,
        help=(
            "State statute agent queue with blocked source-access statuses. "
            "Defaults to manifests/state-statute-agent-queue.yaml when present."
        ),
    )
    state_statute_completion.add_argument("--output", type=Path)
    state_statute_completion.add_argument(
        "--require-complete",
        action="store_true",
        help="Exit nonzero unless every expected state/DC statute is productionized and validated.",
    )
    state_statute_completion.set_defaults(func=_cmd_state_statute_completion)

    regulation_completion = sub.add_parser(
        "regulation-completion",
        help="Classify federal plus state regulation ingestion against a named release.",
    )
    regulation_completion.add_argument("--base", type=Path, required=True)
    regulation_completion.add_argument("--release", required=True)
    regulation_completion.add_argument("--supabase-counts", type=Path)
    regulation_completion.add_argument(
        "--validation-report",
        type=Path,
        help=(
            "validate-release JSON output. Defaults to "
            "<base>/analytics/validate-release-<release>.json when present."
        ),
    )
    regulation_completion.add_argument(
        "--prefix",
        action="append",
        choices=list(DEFAULT_RELEASE_ARTIFACT_PREFIXES),
        default=[],
        help="Top-level artifact prefix to inspect. Defaults to release content prefixes.",
    )
    regulation_completion.add_argument("--include-r2", action="store_true")
    regulation_completion.add_argument("--bucket")
    regulation_completion.add_argument("--endpoint-url")
    regulation_completion.add_argument("--credentials-file", type=Path)
    regulation_completion.add_argument("--output", type=Path)
    regulation_completion.add_argument(
        "--require-complete",
        action="store_true",
        help=(
            "Exit nonzero unless every expected federal/state regulation corpus is "
            "productionized and validated."
        ),
    )
    regulation_completion.set_defaults(func=_cmd_regulation_completion)

    source_discovery = sub.add_parser(
        "source-discovery",
        help="Classify static external URL inventories for source-discovery operations.",
    )
    source_discovery.add_argument("--base", type=Path, required=True)
    source_discovery.add_argument(
        "--input",
        type=Path,
        action="append",
        help="Static URL-list file to classify. Repeatable.",
    )
    source_discovery.add_argument(
        "--reference-input",
        type=Path,
        action="append",
        help=(
            "PolicyEngine reference JSONL file to classify by its reference_url "
            "records. Repeatable."
        ),
    )
    source_discovery.add_argument(
        "--source-name",
        default="policyengine-us",
        help="External discovery source label to write into the report.",
    )
    source_discovery.add_argument(
        "--release",
        default="",
        help="Release manifest to compare for matching jurisdiction/class scopes. Use empty string to skip.",
    )
    source_discovery.add_argument("--output", type=Path)
    source_discovery.set_defaults(func=_cmd_source_discovery)

    promote_source_discovery = sub.add_parser(
        "promote-source-discovery-group",
        help="Create an official-document manifest from one ready source-discovery group.",
    )
    promote_source_discovery.add_argument(
        "--report",
        type=Path,
        required=True,
        help="Source-discovery JSON report containing rows and group_rows.",
    )
    promote_source_discovery.add_argument(
        "--group-key",
        required=True,
        help="Ready group key, e.g. uk/statute/statute.",
    )
    promote_source_discovery.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Official-document manifest path to write.",
    )
    promote_source_discovery.add_argument("--source-as-of")
    promote_source_discovery.add_argument("--expression-date")
    promote_source_discovery.add_argument("--limit", type=int)
    promote_source_discovery.add_argument(
        "--exclude-url",
        action="append",
        help="Canonical source-discovery URL to omit from the generated manifest. Repeatable.",
    )
    promote_source_discovery.add_argument(
        "--rewrite-url",
        action="append",
        help="Rewrite one canonical source-discovery URL as FROM=TO. Repeatable.",
    )
    promote_source_discovery.add_argument(
        "--allow-unsupported",
        action="store_true",
        help="Skip non-HTML/PDF rows instead of failing.",
    )
    promote_source_discovery.set_defaults(func=_cmd_promote_source_discovery_group)

    policyengine_references = sub.add_parser(
        "policyengine-references",
        help=(
            "Extract offline PolicyEngine reference provenance into JSONL and "
            "optional URL inventories."
        ),
    )
    policyengine_references.add_argument(
        "--repo",
        type=Path,
        action="append",
        required=True,
        help="PolicyEngine checkout to scan. Repeatable.",
    )
    policyengine_references.add_argument(
        "--project",
        action="append",
        help="Project label matching each --repo, e.g. policyengine-us. Repeatable.",
    )
    policyengine_references.add_argument(
        "--scope",
        choices=[scope.value for scope in PolicyEngineReferenceScope],
        default=PolicyEngineReferenceScope.POLICY.value,
        help=(
            "policy scans parameters, params_on_demand, and variables only; "
            "all scans supported files throughout the checkout."
        ),
    )
    policyengine_references.add_argument(
        "--output",
        type=Path,
        required=True,
        help="JSONL path for provenance-rich reference records.",
    )
    policyengine_references.add_argument(
        "--url-output",
        type=Path,
        help="Optional static URL-list path consumable by source-discovery.",
    )
    policyengine_references.set_defaults(func=_cmd_policyengine_references)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
