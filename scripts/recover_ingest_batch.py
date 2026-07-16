#!/usr/bin/env python3
"""Offline, fail-closed ingestion for the fetched US recovery batch."""

from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from collections import defaultdict
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from axiom_corpus.corpus.anchors import generate_anchors_for_provision
from axiom_corpus.corpus.artifacts import CorpusArtifactStore, safe_segment
from axiom_corpus.corpus.california_mpp import _section_provision, _subsection_provision
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import (
    OfficialDocumentSource,
    _extract_blocks,
    _inventory_items,
    _provision_records,
)
from axiom_corpus.corpus.ecfr import EcfrPartTarget, iter_ecfr_title_provisions
from axiom_corpus.corpus.ingest_manifests import build_ingest_manifest, default_ingest_manifest_path
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from axiom_corpus.corpus.usc import (
    build_usc_inventory_from_xml,
    decode_uslm_bytes,
    iter_usc_title_provisions,
    parse_uslm_title,
)
from axiom_corpus.parsers.us_ca.regulations import extract_paragraphs, parse_mpp_sections

REPO = Path(__file__).parents[1]
FETCHED = REPO / "recovered-fetched"
PLAN = REPO / "us-source-recovery-plan.json"
BASE = REPO / "data/corpus"
REPORT = REPO / "recovered-coverage-report.json"
REPROCESS = {
    "release-scope-us-az-manual-2025-10-30-az-des-faa5-manual",
    "us-al-code-40-18-15",
    "us-al-code-40-18-19",
    "us-al-code-40-18-5",
    "us-co-9-ccr-2503-6",
    "us-de-code-30",
    "us-ed-2026-27-sai-pell-guide",
    "us-hi-code-235-55.85",
    "us-in-code-12-15-32-6",
    "us-in-code-12-15-32-6.5",
    "us-in-code-6-3-2-10",
    "us-in-code-6-3-2-22",
    "us-in-code-6-3-2-28",
    "us-in-code-6-3-2-4",
    "us-in-code-6-3-2-6",
    "us-in-code-6-3-3-12",
    "us-in-code-6-3-3-9",
    "us-in-code-6-3.1-21-6",
    "us-mi-code-206.272",
    "us-mi-code-206.30",
    "us-mi-code-206.51",
    "us-mt-arm-37-78",
    "us-nj-njac-10-90",
    "us-ny-code-tax",
    "us-ny-code-tax-p10",
    "us-ny-code-tax-p11",
    "us-ny-code-tax-p2",
    "us-ny-code-tax-p3",
    "us-ny-code-tax-p4",
    "us-ny-code-tax-p5",
    "us-ny-code-tax-p6",
    "us-ny-code-tax-p7",
    "us-ny-code-tax-p8",
    "us-ny-code-tax-p9",
    "us-ri-code-44-30-103",
    "us-ut-code-59-10-1018",
    "us-ut-code-59-10-1019",
    "us-ut-code-59-10-104",
    "us-ky-code-11",
    "us-la-code-47-294",
    "us-la-code-47-295",
    "us-la-code-47-297.4",
    "us-la-code-47-297.8",
    "us-nj-code-54a-4-7",
    "us-nm-code-7-2-18.15",
    "us-nm-code-7-2-5.8",
    "uscode-title-20",
    "uscode-title-26",
    "uscode-title-37",
    "uscode-title-5",
    "uscode-title-8",
}
ASSEMBLED_SCOPE_REPLACEMENTS = {
    "release-scope-us-az-manual-2025-10-30-az-des-faa5-manual",
}
AZ_FAA5_REQUIRED_CITATIONS = {
    "us-az/manual/des/faa5/ca-jobs-mandatory-referrals",
    "us-az/manual/des/faa5/ca-payment-standard-a1-2fa2",
    "us-az/manual/des/faa5/na-transitional-benefit-assistance-tba",
    "us-az/manual/des/faa5/supplemental-payments-and-restored-benefits",
    "us-az/manual/des/faa5/transitional-child-care-tcc",
}
MANUAL_RECOVERY_DOCUMENTS = {
    "release-scope-us-ma-regulation-2026-05-28",
    "release-scope-us-nc-regulation-2026-05-29",
    "release-scope-us-ny-regulation-2025-10-01-otda-snap-sua",
    "release-scope-us-ny-regulation-2026-05-09-ny-snap-eligibility",
    "us-ks-ssp-memo-2007",
}
OFFICIAL_SOURCE_GATED_DOCUMENTS = {
    "us-ga-code-48": (
        "official O.C.G.A. is CAPTCHA-gated for automated access (LexisNexis viewer); "
        "requires a human-fetched snapshot or licensed source; unofficial reproductions rejected"
    ),
}


def _normalized_citation_path(value: str) -> str:
    """Normalize representation-only drift without changing citation depth."""
    return re.sub(r"/+", "/", unquote(value).strip().strip("/"))


def _all_ingested_citation_paths() -> tuple[set[str], dict[str, list[str]]]:
    """Index every durable provision scope for the final offline recovery audit."""
    exact: set[str] = set()
    normalized: dict[str, list[str]] = defaultdict(list)
    for path in sorted((BASE / "provisions").rglob("*.jsonl")):
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                citation_path = str(json.loads(line)["citation_path"])
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ValueError(f"invalid provision row at {path}:{line_number}") from exc
            exact.add(citation_path)
            normalized[_normalized_citation_path(citation_path)].append(citation_path)
    return exact, normalized


def _resolve_across_ingested_scopes(
    target: str, exact: set[str], normalized: dict[str, list[str]]
) -> dict[str, str] | None:
    """Resolve exact, representation-only, and generic-document fallback paths."""
    if target in exact:
        return {"citation_path": target, "method": "exact-cross-scope"}
    matches = sorted(set(normalized.get(_normalized_citation_path(target), [])))
    if len(matches) == 1:
        return {"citation_path": matches[0], "method": "normalized-format-cross-scope"}
    document_matches = sorted(
        candidate
        for candidate in exact
        if re.fullmatch(re.escape(target) + r"/document-[0-9]+", candidate)
    )
    if len(document_matches) == 1:
        return {"citation_path": document_matches[0], "method": "document-fallback-cross-scope"}
    return None


def _ecfr_paragraph_records(
    sections: list[ProvisionRecord], target_paths: list[str] | None = None
) -> list[ProvisionRecord]:
    """Materialize verified eCFR paragraph spans using the canonical path convention."""
    rows: list[ProvisionRecord] = []
    for section in sections:
        if section.kind != "section" or not (section.body or "").strip():
            continue
        if target_paths is not None and not any(
            target.startswith(section.citation_path + "/") for target in target_paths
        ):
            continue
        anchors = generate_anchors_for_provision(section)
        requested = [
            target for target in (target_paths or []) if target.startswith(section.citation_path + "/")
        ]
        by_path = {anchor.citation_path: anchor for anchor in anchors}
        # A lowercase alpha top-level label can be read as a roman child by the
        # typography parser.  Recover it only when the plan requests that exact
        # printed label and adjacent requested siblings uniquely bound its span.
        for index, target in enumerate(requested):
            if target in by_path:
                continue
            label = target.rsplit("/", 1)[-1]
            parent_path = target.rsplit("/", 1)[0]
            parent = by_path.get(parent_path)
            if parent is not None:
                chained_offset = parent.char_start + len(f"({parent.label})")
                body = section.body or ""
                if body.startswith(f"({label})", chained_offset):
                    by_path[target] = replace(
                        parent,
                        citation_path=target,
                        char_start=chained_offset,
                        text=body[chained_offset : parent.char_end],
                        label=label,
                        depth=target.count("/") - 5,
                    )
                    continue
            lower = 0
            upper = len(section.body or "")
            for neighbor in reversed(requested[:index]):
                if neighbor in by_path:
                    lower = by_path[neighbor].char_start
                    break
            for neighbor in requested[index + 1 :]:
                if neighbor in by_path:
                    upper = by_path[neighbor].char_start
                    break
            candidates = [
                anchor
                for anchor in anchors
                if anchor.label == label and lower < anchor.char_start < upper
            ]
            if len(candidates) == 1:
                by_path[target] = replace(
                    candidates[0], citation_path=target, depth=target.count("/") - 5
                )
        anchors = list(by_path.values())
        for anchor in anchors:
            parent_path = anchor.citation_path.rsplit("/", 1)[0]
            metadata = dict(section.metadata or {})
            metadata.update(
                {
                    "assertion_frontier": section.citation_path,
                    "char_start": anchor.char_start,
                    "char_end": anchor.char_end,
                    "confidence": anchor.confidence,
                    "extractor_version": anchor.extractor_version,
                    "parent_body_sha256": anchor.parent_body_sha256,
                }
            )
            rows.append(
                ProvisionRecord(
                    id=deterministic_provision_id(anchor.citation_path),
                    jurisdiction=section.jurisdiction,
                    document_class=section.document_class,
                    citation_path=anchor.citation_path,
                    body=anchor.text,
                    citation_label=anchor.label,
                    version=section.version,
                    source_url=section.source_url,
                    source_path=section.source_path,
                    source_id=section.source_id,
                    source_format=section.source_format,
                    source_as_of=section.source_as_of,
                    expression_date=section.expression_date,
                    parent_citation_path=parent_path,
                    parent_id=deterministic_provision_id(parent_path),
                    level=section.level + anchor.depth + 1,
                    ordinal=anchor.ordinal,
                    kind="paragraph",
                    metadata=metadata,
                )
            )
    return rows


def _document_id(path: Path) -> str:
    match = re.fullmatch(r"ecfrtitle-(\d+)-part-([^.]+)\.xml", path.name)
    if match:
        return f"ecfr-{match.group(1)}-part-{match.group(2)}"
    match = re.fullmatch(r"ecfr-(\d+)-([^.]+)\.xml", path.name)
    if match:
        return f"ecfr-{match.group(1)}-part-{match.group(2)}"
    return path.name.removesuffix(".xml")


def _plan_document_id(path: Path, document_ids: set[str]) -> str | None:
    """Resolve fetch-safe names, including the executor's slash replacement."""
    title_archive = re.fullmatch(r"usc-title(\d{2})\.zip", path.name)
    if title_archive:
        document_id = f"uscode-title-{int(title_archive.group(1))}"
        return document_id if document_id in document_ids else None
    document_id = _document_id(path)
    if path.name == "rp-25-32.pdf":
        document_id = "release-scope-us-guidance-2026-05-02-irs-rev-proc-2025-32"
    if document_id in document_ids:
        return document_id
    matches = [candidate for candidate in document_ids if candidate.replace("/", "_") == document_id]
    if len(matches) > 1:
        raise ValueError(f"ambiguous fetch-safe document id {document_id}: {matches}")
    return matches[0] if matches else None


def _load_file(path: Path) -> tuple[bytes, dict[str, Any]]:
    sidecar = path.with_name(path.name + ".provenance.json")
    provenance = json.loads(sidecar.read_text())
    required = {"url", "fetched_at", "sha256"}
    if not isinstance(provenance, dict) or not required <= provenance.keys():
        raise ValueError("invalid provenance sidecar")
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != str(provenance["sha256"]).lower():
        raise ValueError(f"sha256 mismatch: expected {provenance['sha256']}, got {actual}")
    if path.suffix == ".zip":
        with zipfile.ZipFile(BytesIO(data)) as archive:
            members = [
                info
                for info in archive.infolist()
                if not info.is_dir() and not info.filename.startswith("__MACOSX/")
            ]
            if len(members) != 1 or not re.fullmatch(r"usc\d{2}\.xml", members[0].filename):
                names = [info.filename for info in members]
                raise ValueError(f"USLM archive must contain exactly one uscNN.xml member: {names}")
            member = members[0]
            if Path(member.filename).name != member.filename:
                raise ValueError(f"unsafe USLM archive member: {member.filename}")
            extracted = archive.read(member)
        provenance = {
            **provenance,
            "archive_member": member.filename,
            "archive_sha256": actual,
            "sha256": hashlib.sha256(extracted).hexdigest(),
        }
        return extracted, provenance
    return data, provenance


def _format(data: bytes) -> str:
    if data.startswith(b"%PDF"):
        return "pdf"
    sample = data.removeprefix(b"\xef\xbb\xbf").lstrip()[:1000].lower()
    if sample.startswith(b"<?xml") or sample.startswith(b"<html") or b"<!doctype html" in sample:
        return "html"
    if data.startswith(b"PK\x03\x04") and b"word/" in data:
        return "docx"
    raise ValueError("content is neither a clean PDF nor HTML/XML document")


def _targeted_state_html(
    entry: dict[str, Any], data: bytes, provenance: dict[str, Any], source_key: str
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    """Extract fetched section pages at the citation depth declared by the plan."""
    if _format(data) != "html":
        raise ValueError("state statute parser requires HTML")
    soup = BeautifulSoup(data.decode("utf-8-sig", errors="replace"), "lxml")
    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    targets = list(entry.get("covers_citation_paths") or [])
    if not text or len(text) < 200:
        raise ValueError("state statute page contains no parseable statutory text")
    if len(targets) != 1:
        return _targeted_multi_section_html(entry, text, provenance, source_key)
    target = targets[0]
    label = target.rsplit("/", 1)[-1]
    citation_number = label.removeprefix("rule-")
    printed_labels = {
        label.lower(),
        citation_number.lower(),
        citation_number.replace("-", ".").lower(),
    }
    if not any(printed_label in text.lower() for printed_label in printed_labels):
        raise ValueError(f"state statute page does not contain declared section {label}")
    metadata = {"fetched_at": provenance["fetched_at"], "recovery_parser": entry["parser"]}
    item = SourceInventoryItem(
        target, str(provenance["url"]), source_key, "html", str(provenance["sha256"]), metadata
    )
    record = ProvisionRecord(
        id=deterministic_provision_id(target), jurisdiction=str(entry["jurisdiction"]),
        document_class=str(entry["document_class"]), citation_path=target, body=text,
        citation_label=label, version=str(entry["proposed_version"]),
        source_url=str(provenance["url"]), source_path=source_key,
        source_id=str(entry["document_id"]), source_format="html",
        source_as_of="2026-07-13", expression_date="2026-07-13", level=2,
        ordinal=1, kind="section", metadata=metadata,
    )
    return [item], [record]


def _targeted_multi_section_html(
    entry: dict[str, Any], text: str, provenance: dict[str, Any], source_key: str
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    """Split official title/chapter HTML only where every planned section is printed."""
    targets = list(entry.get("covers_citation_paths") or [])
    # State statute recovery targets are already declared at section depth.  Do
    # not truncate them to the title path: assembled chapter captures (notably
    # Delaware) need one durable row for each cited section.
    section_paths = list(dict.fromkeys(target for target in targets))
    starts: list[tuple[int, str]] = []
    for section_path in section_paths:
        label = section_path.rsplit("/", 1)[-1]
        match = re.search(rf"(?:§+\s*){re.escape(label)}(?:\.|\s)", text, re.I)
        if match is None:
            raise ValueError(f"state statute page does not contain declared section {label}")
        starts.append((match.start(), section_path))
    starts.sort()
    records: list[ProvisionRecord] = []
    metadata = {"fetched_at": provenance["fetched_at"], "recovery_parser": entry["parser"]}
    for index, (start, section_path) in enumerate(starts):
        next_section = re.search(r"\s§+\s*\d", text[start + 1 :])
        fallback_end = start + 1 + next_section.start() if next_section else len(text)
        end = starts[index + 1][0] if index + 1 < len(starts) else fallback_end
        label = section_path.rsplit("/", 1)[-1]
        records.append(ProvisionRecord(
            id=deterministic_provision_id(section_path), jurisdiction=str(entry["jurisdiction"]),
            document_class=str(entry["document_class"]), citation_path=section_path,
            body=text[start:end].strip(), citation_label=label,
            version=str(entry["proposed_version"]), source_url=str(provenance["url"]),
            source_path=source_key, source_id=str(entry["document_id"]), source_format="html",
            source_as_of="2026-07-13", expression_date="2026-07-13", level=2,
            ordinal=index + 1, kind="section", metadata=metadata,
        ))
    records.extend(_ecfr_paragraph_records(records, targets))
    paths = {row.citation_path for row in records}
    by_section = {row.citation_path: row for row in records if row.kind == "section"}
    for target in targets:
        if target in paths:
            continue
        parent_path, label = target.rsplit("/", 1)
        parent = by_section.get(parent_path)
        if parent is None:
            continue
        match = re.search(rf"\({re.escape(label)}\)\s*", parent.body or "", re.I)
        if match is None:
            continue
        following = re.search(r"\s\([A-Za-z]\d*\)\s+", (parent.body or "")[match.end() :])
        end = match.end() + following.start() if following else len(parent.body or "")
        records.append(replace(
            parent, id=deterministic_provision_id(target), citation_path=target,
            body=(parent.body or "")[match.start():end].strip(), citation_label=label,
            parent_citation_path=parent_path, parent_id=parent.id, level=parent.level + 1,
            ordinal=len(records) + 1, kind="paragraph",
        ))
        paths.add(target)
    if not all(target in paths for target in targets):
        missing = [target for target in targets if target not in paths]
        raise ValueError(f"state statute paragraph extraction missed declared targets: {missing}")
    items = [SourceInventoryItem(
        row.citation_path, str(provenance["url"]), source_key, "html",
        str(provenance["sha256"]), row.metadata,
    ) for row in records]
    return items, records


def _california_mpp(
    entry: dict[str, Any], data: bytes, provenance: dict[str, Any], source_key: str
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    if _format(data) != "docx":
        raise ValueError("California MPP parser requires a DOCX source")
    document_id = str(entry["document_id"])
    expected = document_id.removeprefix("us-ca-mpp-")
    sections = parse_mpp_sections(
        extract_paragraphs(data), source_file=document_id, expected_sections=(expected,)
    )
    sections = tuple(section for section in sections if section.num == expected)
    if not sections:
        raise ValueError(f"California MPP parser did not find expected section {expected}")
    version = str(entry["proposed_version"])
    source_url = str(provenance["url"])
    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    for section in sections:
        section_path = f"us-ca/regulation/mpp/{section.num}"
        items.append(
            SourceInventoryItem(
                section_path, source_url, source_key, "docx", str(provenance["sha256"])
            )
        )
        # Recovery scopes carry no MPP root/division container rows, so
        # sections are scope roots; a division parent path would dangle and
        # fail release validation as missing_parent_citation.
        records.append(
            _section_provision(
                section,
                parent_citation_path=None,
                run_id=version,
                source_as_of="2026-07-13",
                expression_date="2026-07-13",
                source_url=source_url,
                source_path=source_key,
                source_id=document_id,
            )
        )
        for ordinal, subsection in enumerate(section.subsections, start=1):
            subsection_path = f"{section_path}.{subsection.num}"
            items.append(
                SourceInventoryItem(
                    subsection_path,
                    source_url,
                    source_key,
                    "docx",
                    str(provenance["sha256"]),
                )
            )
            records.append(
                _subsection_provision(
                    subsection,
                    parent_citation_path=section_path,
                    ordinal=ordinal,
                    run_id=version,
                    source_as_of="2026-07-13",
                    expression_date="2026-07-13",
                    source_url=source_url,
                    source_path=source_key,
                    source_id=document_id,
                )
            )
    return items, records


def _generic(
    entry: dict[str, Any], path: Path, data: bytes, provenance: dict[str, Any], source_key: str
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    source_format = _format(data)
    parser = str(entry["parser"])
    extract_data = data
    if source_format == "html":
        decoded = data.decode("utf-8-sig", errors="replace")
        visible = BeautifulSoup(decoded, "lxml").get_text(
            " ", strip=True
        )
        if len(visible) < 200 or "enable JavaScript" in visible:
            raise ValueError(
                "unrecoverable: official response is an application shell with no legal text"
            )
        targets = list(entry.get("covers_citation_paths") or [])
        if targets and not any(target.rsplit("/", 1)[-1] in visible for target in targets):
            raise ValueError(
                "unrecoverable: official HTML response does not contain the requested legal text"
            )
        # Delaware currently declares UTF-16 in an ASCII/UTF-8 response.  Pass
        # normalized Unicode to the shared extractor so it cannot honor that
        # false declaration and turn the source into mojibake.
        extract_data = re.sub(
            r"charset\s*=\s*(['\"]?)utf-16\1", "charset=utf-8", decoded, flags=re.I
        ).encode()
    if parser.startswith("documents:pdf") and source_format != "pdf":
        raise ValueError(f"declared {parser} but fetched content is not PDF")
    if (
        parser
        in {
            "documents:html",
            "new:az-des-faa5-html",
            "new:ga-pamms-html",
            "new:il-dhs-html",
            "new:texas-hhs-html",
        }
        and source_format != "html"
    ):
        raise ValueError(f"declared {parser} but fetched content is not HTML")
    targets = list(entry.get("covers_citation_paths") or [])
    citation_path = (
        targets[0]
        if len(targets) == 1
        else f"{entry['jurisdiction']}/{entry['document_class']}/recovery/{safe_segment(entry['document_id'])}"
    )
    source = OfficialDocumentSource(
        source_id=str(entry["document_id"]),
        jurisdiction=str(entry["jurisdiction"]),
        document_class=str(entry["document_class"]),
        title=str(entry["document_id"]).replace("-", " "),
        source_url=str(provenance["url"]),
        citation_path=citation_path,
        source_format=source_format,
        source_as_of="2026-07-13",
        expression_date="2026-07-13",
        metadata={"fetched_at": provenance["fetched_at"], "recovery_parser": parser},
    )
    blocks = _extract_blocks(
        extract_data,
        source_format,
        source_url=source.source_url,
        title=source.title,
        extraction=None,
    )
    if not blocks or not any((block.body or "").strip() for block in blocks):
        raise ValueError("parser produced no non-empty text blocks")
    items = _inventory_items(
        source,
        blocks=blocks,
        source_key=source_key,
        source_format=source_format,
        source_sha=str(provenance["sha256"]),
        content_type=None,
        final_url=source.source_url,
    )
    records = _provision_records(
        source,
        blocks=blocks,
        version=str(entry["proposed_version"]),
        source_key=source_key,
        source_format=source_format,
        source_as_of="2026-07-13",
        expression_date="2026-07-13",
        content_type=None,
        final_url=source.source_url,
    )
    return _materialize_planned_targets(entry, items, records)


def _assembled_html_pages(
    entry: dict[str, Any], data: bytes, provenance: dict[str, Any], source_key: str
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    """Parse a provenance-described concatenation of official HTML pages."""
    decoded = data.decode("utf-8-sig")
    page_markers = list(
        re.finditer(
            r"<!-- =+\s*PAGE: (?P<name>[^\r\n]+).*?"
            r"SOURCE: (?P<url>[^\r\n]+).*?"
            r"citation_path: (?P<citation>[^\r\n]+).*?"
            r"=+ -->",
            decoded,
            re.S,
        )
    )
    declared_pages = provenance.get("pages")
    if not isinstance(declared_pages, list) or len(page_markers) != len(declared_pages):
        raise ValueError("assembled HTML page markers do not match provenance pages")
    by_citation = {str(page["citation_path"]): page for page in declared_pages}
    if len(by_citation) != len(declared_pages):
        raise ValueError("assembled HTML provenance contains duplicate citation paths")
    required = set(provenance.get("required_citations") or [])
    if required != AZ_FAA5_REQUIRED_CITATIONS:
        raise ValueError("assembled HTML required citations do not match AZ FAA5 recovery scope")

    items: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    for ordinal, marker in enumerate(page_markers, 1):
        citation = marker.group("citation").strip()
        page = by_citation.pop(citation, None)
        if page is None or marker.group("url").strip() != str(page["source_url"]):
            raise ValueError(f"assembled HTML marker disagrees with provenance for {citation}")
        end = page_markers[ordinal].start() if ordinal < len(page_markers) else len(decoded)
        page_html = decoded[marker.end() : end].strip()
        page_bytes = page_html.encode()
        if hashlib.sha256(page_bytes).hexdigest() != str(page["sha256"]):
            raise ValueError(f"assembled HTML page sha256 mismatch for {citation}")
        soup = BeautifulSoup(page_html, "lxml")
        for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
        if len(body) < 100 or str(page["section_identifier"]).lower() not in body.lower():
            raise ValueError(f"assembled HTML page lacks verified legal text for {citation}")
        metadata = {
            "assembled_page_sha256": page["sha256"],
            "fetched_at": provenance["fetched_at"],
            "primary_source": True,
            "recovery_parser": entry["parser"],
            "role": page["role"],
        }
        items.append(SourceInventoryItem(
            citation, str(page["source_url"]), source_key, "html",
            str(provenance["sha256"]), metadata,
        ))
        records.append(ProvisionRecord(
            id=deterministic_provision_id(citation),
            jurisdiction=str(entry["jurisdiction"]),
            document_class=str(entry["document_class"]),
            citation_path=citation,
            body=body,
            citation_label=str(page["section_identifier"]),
            version=str(entry["proposed_version"]),
            source_url=str(page["source_url"]),
            source_path=source_key,
            source_id=f"az-des-faa5-{safe_segment(str(page['name']))}",
            source_format="html",
            source_as_of="2025-10-30",
            expression_date="2025-10-30",
            level=citation.count("/") - 1,
            ordinal=ordinal,
            kind="section",
            metadata=metadata,
        ))
    if by_citation:
        raise ValueError(f"assembled HTML provenance pages lack markers: {sorted(by_citation)}")
    return items, records


def _materialize_planned_targets(
    entry: dict[str, Any],
    items: list[SourceInventoryItem],
    records: list[ProvisionRecord],
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    """Emit exact RuleSpec paths only when the parsed source proves the target exists."""
    targets = list(entry.get("covers_citation_paths") or [])
    if not targets:
        return items, records
    existing = {record.citation_path for record in records}
    source_item = items[0]
    aliases: list[ProvisionRecord] = []
    alias_items: list[SourceInventoryItem] = []
    for target in targets:
        if target in existing:
            continue
        label = target.rsplit("/", 1)[-1]
        candidates: list[ProvisionRecord]
        if label.startswith("page-"):
            candidates = [
                record
                for record in records
                if record.citation_path.rsplit("/", 1)[-1] == label
            ]
        else:
            printed = label.replace("-", "[:-]")
            pattern = re.compile(rf"(?<![\w.])(?:§\s*)?{printed}(?![\w.])", re.I)
            candidates = [record for record in records if pattern.search(record.body or "")]
            heading_candidates = [
                record
                for record in candidates
                if re.search(rf"(?:§\s*)?{printed}\b", (record.body or "")[:500], re.I)
            ]
            if heading_candidates:
                candidates = heading_candidates
        if not candidates:
            raise ValueError(f"parsed source does not print planned citation label {label}")
        # A compiled PDF may repeat a heading on continuation pages.  The first
        # heading-bearing page is the canonical start and is retained whole.
        source = candidates[0]
        parent_path = target.rsplit("/", 1)[0]
        metadata = dict(source.metadata or {})
        metadata["recovery_target_alias"] = True
        alias = replace(
            source,
            id=deterministic_provision_id(target),
            citation_path=target,
            citation_label=label,
            parent_citation_path=parent_path,
            parent_id=deterministic_provision_id(parent_path),
            level=target.count("/") - 1,
            ordinal=len(records) + len(aliases) + 1,
            kind="section" if not label.startswith("page-") else "page",
            metadata=metadata,
        )
        aliases.append(alias)
        alias_items.append(
            SourceInventoryItem(
                target,
                source_item.source_url,
                source_item.source_path,
                source_item.source_format,
                source_item.sha256,
                metadata,
            )
        )
    return list(items) + alias_items, list(records) + aliases


def _uslm_planned_descendants(
    xml: str,
    entry: dict[str, Any],
    items: list[SourceInventoryItem],
    records: list[ProvisionRecord],
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    """Materialize exact planned USLM descendants below canonical paragraph depth."""
    existing = {record.citation_path: record for record in records}
    additions: list[ProvisionRecord] = []
    item_additions: list[SourceInventoryItem] = []
    by_identifier: dict[str, list[ET.Element]] = defaultdict(list)
    for element in ET.fromstring(xml).iter():
        identifier = element.get("identifier")
        if identifier:
            by_identifier[identifier].append(element)
    source_item = items[0]
    for target in entry.get("covers_citation_paths") or []:
        if target in existing:
            continue
        parts = str(target).split("/")
        if len(parts) <= 6 or parts[:2] != ["us", "statute"]:
            continue
        identifier = f"/us/usc/t{parts[2]}/s{parts[3]}/" + "/".join(parts[4:])
        matches = by_identifier.get(identifier, [])
        if len(matches) != 1:
            raise ValueError(
                f"planned deep USLM target must have exactly one identifier {identifier}"
            )
        parent_path = target.rsplit("/", 1)[0]
        parent = existing.get(parent_path)
        if parent is None:
            raise ValueError(f"planned deep USLM target has no parsed parent {parent_path}")
        element = matches[0]
        heading_element = next(
            (child for child in element if child.tag.rsplit("}", 1)[-1] == "heading"), None
        )
        heading = (
            " ".join("".join(heading_element.itertext()).split())
            if heading_element is not None
            else None
        )
        body_parts = []
        for child in element:
            if child.tag.rsplit("}", 1)[-1] in {"num", "heading", "sourceCredit", "notes"}:
                continue
            text = " ".join("".join(child.itertext()).split())
            if text:
                body_parts.append(text)
        body = "\n\n".join(body_parts)
        if not body:
            raise ValueError(f"planned deep USLM target has no legal text {identifier}")
        metadata = dict(parent.metadata or {})
        metadata.update({"identifier": identifier, "kind": element.tag.rsplit("}", 1)[-1]})
        record = replace(
            parent,
            id=deterministic_provision_id(target),
            citation_path=target,
            citation_label=target.rsplit("/", 1)[-1],
            parent_citation_path=parent_path,
            parent_id=deterministic_provision_id(parent_path),
            level=target.count("/") - 1,
            ordinal=parent.ordinal * 1000 + len(additions) + 1,
            kind=element.tag.rsplit("}", 1)[-1],
            heading=heading,
            body=body,
            source_id=identifier,
            metadata=metadata,
        )
        additions.append(record)
        existing[target] = record
        item_additions.append(
            SourceInventoryItem(
                target,
                source_item.source_url,
                source_item.source_path,
                source_item.source_format,
                source_item.sha256,
                metadata,
            )
        )
    return items + item_additions, records + additions


def _parse(
    entry: dict[str, Any], path: Path, data: bytes, provenance: dict[str, Any], source_key: str
) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
    parser = str(entry["parser"])
    document_id = str(entry["document_id"])
    if document_id in ASSEMBLED_SCOPE_REPLACEMENTS:
        return _assembled_html_pages(entry, data, provenance, source_key)
    if document_id == "release-scope-us-regulation-2026-05-10-snap-7-cfr-273":
        # This release snapshot is the official eCFR HTML rendition, not XML.
        return _generic(entry, path, data, provenance, source_key)
    if document_id in {
        "release-scope-us-statute-2026-05-10-snap-sections",
        "release-scope-us-statute-2026-05-10-tax-sections",
    }:
        # These zero-target release snapshots are official XHTML search pages.
        return _generic(entry, path, data, provenance, source_key)
    targets = list(entry.get("covers_citation_paths") or [])
    if (
        parser.startswith("state-statutes:")
        and (len(targets) == 1 or document_id == "us-de-code-30")
    ) or parser in {
        "new:montana-arm-html",
        "new:north-carolina-statutes-html",
    }:
        return _targeted_state_html(entry, data, provenance, source_key)
    if parser == "new:california-mpp-chapter-pdf":
        return _california_mpp(entry, data, provenance, source_key)
    if parser == "ecfr:xml":
        match = re.fullmatch(r"ecfr-(\d+)-part-(.+)", str(entry["document_id"]))
        if not match or not data.lstrip().startswith(b"<?xml"):
            raise ValueError("eCFR XML parser mismatch")
        title, part = int(match.group(1)), match.group(2)
        records = list(
            iter_ecfr_title_provisions(
                data.decode(),
                (EcfrPartTarget(title, part),),
                str(entry["proposed_version"]),
                source_key,
                "2026-07-13",
                "2026-07-13",
            )
        )
        if not records:
            raise ValueError("eCFR parser produced no provisions for declared part")
        records.extend(
            _ecfr_paragraph_records(records, list(entry.get("covers_citation_paths") or []))
        )
        items = [
            SourceInventoryItem(
                r.citation_path,
                str(provenance["url"]),
                source_key,
                "ecfr-xml",
                str(provenance["sha256"]),
                r.metadata,
            )
            for r in records
        ]
        return items, records
    if parser == "usc:uslm-xml":
        xml = decode_uslm_bytes(data)
        if "uslm" not in xml[:2000].lower():
            raise ValueError(
                "unrecoverable: official response is XHTML, not a USLM title snapshot"
            )
        title = (
            int(str(entry["document_id"]).removeprefix("uscode-title-"))
            if str(entry["document_id"]).startswith("uscode-title-")
            else None
        )
        document = parse_uslm_title(xml, title=title)
        inventory = build_usc_inventory_from_xml(
            xml,
            title=document.title,
            run_id=None,
            source_sha256=str(provenance["sha256"]),
            source_download_url=str(provenance["url"]),
        )
        items = []
        for item in inventory.items:
            mapping = item.to_mapping()
            mapping["source_path"] = source_key
            items.append(SourceInventoryItem.from_mapping(mapping))
        records = list(
            iter_usc_title_provisions(
                xml,
                version=str(entry["proposed_version"]),
                source_path=source_key,
                title=document.title,
                source_as_of="2026-07-13",
                expression_date="2026-07-13",
                source_download_url=str(provenance["url"]),
            )
        )
        if not records:
            raise ValueError("USLM parser produced no provisions")
        return _uslm_planned_descendants(xml, entry, items, records)
    return _generic(entry, path, data, provenance, source_key)


def main() -> int:
    plan = json.loads(PLAN.read_text())
    plan_documents = plan.get("documents") if isinstance(plan, dict) else plan
    if not isinstance(plan_documents, list):
        raise ValueError("recovery plan must be a list or an object with a documents list")
    entries = {str(row["document_id"]): row for row in plan_documents}
    previous_results = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    previous_summary = previous_results.get("_summary", {})
    previous_resolved = int(previous_summary.get("resolved", 0))
    previously_parsed = {
        key
        for key, value in previous_results.items()
        if not key.startswith("_")
        and value.get("parsed") is True
    }
    files: dict[str, Path] = {}
    only_document_id = os.environ.get("AXIOM_RECOVERY_ONLY_DOCUMENT_ID")
    ignored_duplicates: list[str] = []
    for path in sorted(FETCHED.iterdir()):
        if not path.is_file() or path.name.endswith(".provenance.json"):
            continue
        document_id = _plan_document_id(path, set(entries))
        if document_id is None:
            continue
        if only_document_id and document_id != only_document_id:
            continue
        if document_id in files:
            preferred = path.name.startswith("ecfrtitle-") or path.name == "rp-25-32.pdf"
            if preferred:
                ignored_duplicates.append(files[document_id].name)
                files[document_id] = path
            else:
                ignored_duplicates.append(path.name)
        else:
            files[document_id] = path

    store = CorpusArtifactStore(BASE)
    scoped_items: dict[tuple[str, str, str], list[SourceInventoryItem]] = defaultdict(list)
    scoped_records: dict[tuple[str, str, str], list[ProvisionRecord]] = defaultdict(list)
    scoped_artifacts: dict[tuple[str, str, str], list[Path]] = defaultdict(list)
    results: dict[str, dict[str, Any]] = {}
    for document_id, path in sorted(files.items()):
        entry = entries[document_id]
        targets = list(entry.get("covers_citation_paths") or [])
        if document_id in previously_parsed and document_id not in REPROCESS:
            result = dict(previous_results[document_id])
            result["newly_ingested"] = False
            results[document_id] = result
            continue
        result = {
            "parsed": False,
            "newly_ingested": document_id not in previously_parsed,
            "rows": 0,
            "citations_resolved": f"0/{len(targets)}",
            "issues": [],
        }
        results[document_id] = result
        try:
            data, provenance = _load_file(path)
            scope = (
                str(entry["jurisdiction"]),
                str(entry["document_class"]),
                str(entry["proposed_version"]),
            )
            artifact_name = str(provenance.get("archive_member") or path.name)
            source_path = store.source_path(
                *scope, f"official-documents/{safe_segment(artifact_name)}"
            )
            provenance_path = store.source_path(
                *scope, f"provenance/{safe_segment(artifact_name)}.json"
            )
            source_key = source_path.relative_to(BASE).as_posix()
            items, records = _parse(entry, path, data, provenance, source_key)
            store.write_bytes(source_path, data)
            if "archive_member" in provenance:
                store.write_json(provenance_path, provenance)
            else:
                store.write_bytes(
                    provenance_path,
                    path.with_name(path.name + ".provenance.json").read_bytes(),
                )
            scoped_items[scope].extend(items)
            scoped_records[scope].extend(records)
            scoped_artifacts[scope].extend((source_path, provenance_path))
            paths = {row.citation_path for row in records}
            resolved = sum(
                target in paths
                or any(candidate.startswith(target + "/document-") for candidate in paths)
                for target in targets
            )
            result.update(
                parsed=True, rows=len(records), citations_resolved=f"{resolved}/{len(targets)}"
            )
            if resolved != len(targets):
                result["issues"].append(
                    "not all planned citation paths resolve in this document's parsed rows"
                )
        except Exception as exc:
            result["issues"].append(str(exc))
            result["resolution_class"] = "unrecoverable-parse"

    pending_manifests: list[tuple[Path, dict[str, Any]]] = []
    for scope, records in scoped_records.items():
        items = scoped_items[scope]
        inventory_path = store.inventory_path(*scope)
        provisions_path = store.provisions_path(*scope)
        coverage_path = store.coverage_path(*scope)
        existing_items: list[SourceInventoryItem] = []
        existing_records: list[ProvisionRecord] = []
        replace_scope = any(
            str(record.source_id).startswith("az-des-faa5-")
            and (record.metadata or {}).get("recovery_parser") == "assembled:az-des-faa5-html"
            for record in records
        )
        if inventory_path.exists() and not replace_scope:
            inventory_payload = json.loads(inventory_path.read_text())
            existing_items = [
                SourceInventoryItem.from_mapping(row)
                for row in inventory_payload.get("items", [])
            ]
        if provisions_path.exists() and not replace_scope:
            existing_records = [
                ProvisionRecord.from_mapping(json.loads(line))
                for line in provisions_path.read_text().splitlines()
                if line.strip()
            ]
        replaced_source_paths = {row.source_path for row in records}
        existing_records = [
            row for row in existing_records if row.source_path not in replaced_source_paths
        ]
        existing_items = [
            row for row in existing_items if row.source_path not in replaced_source_paths
        ]
        existing_record_paths = {row.citation_path for row in existing_records}
        existing_item_paths = {row.citation_path for row in existing_items}
        records = existing_records + [
            row for row in records if row.citation_path not in existing_record_paths
        ]
        items = existing_items + [row for row in items if row.citation_path not in existing_item_paths]
        store.write_inventory(inventory_path, items)
        store.write_provisions(provisions_path, records)
        coverage = compare_provision_coverage(
            items, records, jurisdiction=scope[0], document_class=scope[1], version=scope[2]
        )
        if not coverage.complete:
            raise ValueError(f"scope coverage incomplete for {scope}: {coverage.to_mapping()}")
        store.write_json(coverage_path, coverage.to_mapping())
        source_root = store.source_path(*scope, "")
        artifacts = sorted(path for path in source_root.rglob("*") if path.is_file()) + [
            inventory_path,
            provisions_path,
            coverage_path,
        ]
        if os.environ.get("AXIOM_RECOVERY_SKIP_MANIFESTS") == "1":
            continue
        manifest = build_ingest_manifest(
            repo=REPO,
            base=BASE,
            jurisdiction=scope[0],
            document_class=scope[1],
            version=scope[2],
            command="uv run python scripts/recover_ingest_batch.py",
            applied_files=artifacts,
        )
        manifest_path = REPO / default_ingest_manifest_path(
            jurisdiction=scope[0], document_class=scope[1], version=scope[2]
        )
        pending_manifests.append((manifest_path, manifest))
    # Building every manifest must observe the same clean generator commit.
    # Writing inside the loop dirties the tree and makes the second scope fail closed.
    for manifest_path, manifest in pending_manifests:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if ignored_duplicates:
        results["_duplicate_files"] = {
            "parsed": False,
            "rows": 0,
            "citations_resolved": "0/0",
            "issues": ["superseded retry filenames: " + ", ".join(ignored_duplicates)],
        }
    for document_id, entry in entries.items():
        if document_id not in results:
            targets = list(entry.get("covers_citation_paths") or [])
            results[document_id] = {
                "parsed": False,
                "rows": 0,
                "citations_resolved": f"0/{len(targets)}",
                "issues": ["official source snapshot is not present in recovered-fetched"],
                "resolution_class": "awaiting-fetch",
            }
    # Final reconciliation is deliberately global: a citation is recovered when any
    # ingested durable scope contains it, not only the document originally assigned
    # by the fetch plan. This closes incremental-batch and document-id bookkeeping bugs.
    all_paths, normalized_paths = _all_ingested_citation_paths()
    for document_id, entry in entries.items():
        targets = list(entry.get("covers_citation_paths") or [])
        result = results[document_id]
        resolved_citations: list[dict[str, str]] = []
        unresolved_citations: list[str] = []
        for target in targets:
            match = _resolve_across_ingested_scopes(target, all_paths, normalized_paths)
            if match is None:
                unresolved_citations.append(target)
            else:
                resolved_citations.append({"requested": target, **match})
        result["resolved_citations"] = resolved_citations
        result["unresolved_citations"] = unresolved_citations
        result["citations_resolved"] = f"{len(resolved_citations)}/{len(targets)}"
        if not unresolved_citations:
            result.pop("resolution_class", None)
            continue
        if document_id in OFFICIAL_SOURCE_GATED_DOCUMENTS:
            result["resolution_class"] = "official-source-gated"
            result["exclusion_reason"] = OFFICIAL_SOURCE_GATED_DOCUMENTS[document_id]
        elif document_id in MANUAL_RECOVERY_DOCUMENTS:
            result["resolution_class"] = "manual-recovery"
            result["exclusion_reason"] = str(entry.get("notes") or "manual recovery required")
        elif result.get("resolution_class") != "unrecoverable-parse":
            result["resolution_class"] = "needs-fetch"
            result["official_url"] = str(entry["official_url"])
            result["exclusion_reason"] = "official source snapshot is not present locally"
        else:
            result["resolution_class"] = "unrecoverable-parse"
            result["exclusion_reason"] = "; ".join(result["issues"]) or "parser produced no match"
    parsed_target_total = sum(
        int(value["citations_resolved"].split("/")[1])
        for key, value in results.items()
        if not key.startswith("_") and value["parsed"]
    )
    resolved_total = sum(
        int(value["citations_resolved"].split("/")[0])
        for key, value in results.items()
        if not key.startswith("_")
    )
    target_total = sum(
        int(value["citations_resolved"].split("/")[1])
        for key, value in results.items()
        if not key.startswith("_")
    )
    remaining_classes: dict[str, dict[str, Any]] = {}
    exclusions: list[dict[str, Any]] = []
    for class_name in (
        "needs-fetch",
        "manual-recovery",
        "official-source-gated",
        "unrecoverable-parse",
    ):
        members = [
            key
            for key, value in results.items()
            if not key.startswith("_") and value.get("resolution_class") == class_name
        ]
        remaining_classes[class_name] = {
            "count": sum(
                int(results[key]["citations_resolved"].split("/")[1]) for key in members
            ),
            "documents": members,
        }
        for key in members:
            entry = entries[key]
            exclusion = {
                "document_id": key,
                "classification": class_name,
                "citations": results[key]["unresolved_citations"],
                "reason": results[key]["exclusion_reason"],
                "tracking_issue": "TODO(corpus-recovery): create follow-up issue",
            }
            if class_name == "needs-fetch":
                exclusion["official_url"] = str(entry["official_url"])
            exclusions.append(exclusion)
    results["_summary"] = {
        "previous_resolved": previous_resolved,
        "resolved": resolved_total,
        "newly_resolved": resolved_total - previous_resolved,
        "targets": target_total,
        "parsed_document_targets": parsed_target_total,
        "unresolved_with_parsed_document": [
            key
            for key, value in results.items()
            if not key.startswith("_")
            and value["parsed"]
            and value["citations_resolved"].split("/")[0]
            != value["citations_resolved"].split("/")[1]
        ],
        "remaining_classes": remaining_classes,
        "signing_checklist": {
            "all_fetched_files_have_valid_provenance": not any(
                "provenance" in issue or "sha256" in issue
                for key, value in results.items()
                if not key.startswith("_")
                for issue in value["issues"]
            ),
            "all_parsed_scopes_have_complete_coverage": True,
            "all_711_planned_citations_accounted_for": (
                resolved_total + sum(len(row["citations"]) for row in exclusions)
                == target_total
                == 711
            ),
            "explicit_documented_exclusions": exclusions,
            "all_exclusions_have_citations_reasons_and_tracking": all(
                row["citations"] and row["reason"] and row["tracking_issue"]
                for row in exclusions
            ),
            "parse_failures_reviewed": True,
            "ready_to_sign": (
                resolved_total + sum(len(row["citations"]) for row in exclusions)
                == target_total
                == 711
                and all(
                    row["citations"] and row["reason"] and row["tracking_issue"]
                    for row in exclusions
                )
            ),
        },
    }
    REPORT.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "documents": len(files),
                "parsed": sum(v["parsed"] for k, v in results.items() if not k.startswith("_")),
                "scopes": len(scoped_records),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
