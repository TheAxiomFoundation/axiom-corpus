#!/usr/bin/env python3
"""Build the self-contained North Carolina TY2026 income-tax statute core."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.recover_ingest_batch import _targeted_state_html

DEFAULT_VERSION = "2026-07-26-nc-ty2026-income-tax-core"
DEFAULT_MANIFEST = Path("manifests/us-nc-ty2026-income-tax-core.yaml")
BASE_SOURCE_ID = "us-nc-code-105"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("NC TY2026 manifest must be a mapping")
    return payload


def _validate_sources(
    base: Path, manifest: dict[str, Any]
) -> tuple[Path, dict[str, dict[str, Any]]]:
    version = str(manifest["version"])
    source_root = base / "sources/us-nc/statute" / version
    raw_sources = manifest.get("sources")
    if not isinstance(raw_sources, dict) or set(raw_sources) != {
        BASE_SOURCE_ID,
        "sl-2026-11",
        "sl-2026-31",
        "sl-2026-41",
    }:
        raise ValueError("NC TY2026 manifest must declare the audited four-source set")
    sources: dict[str, dict[str, Any]] = {}
    for source_id, raw in raw_sources.items():
        if not isinstance(raw, dict):
            raise ValueError(f"source {source_id} must be a mapping")
        source_url = str(raw["source_url"])
        if not source_url.startswith(
            "https://www.ncleg.gov/EnactedLegislation/"
        ):
            raise ValueError(f"source {source_id} is not an official NC legislative source")
        relative_path = Path(str(raw["source_path"]))
        source_path = source_root / relative_path
        if not source_path.is_file():
            raise ValueError(f"missing retained source snapshot: {source_path}")
        actual_sha = _sha256(source_path)
        expected_sha = str(raw["sha256"])
        if actual_sha != expected_sha:
            raise ValueError(
                f"source snapshot hash mismatch for {source_id}: "
                f"expected {expected_sha}, got {actual_sha}"
            )
        sources[str(source_id)] = {
            **raw,
            "artifact_path": (
                Path("sources/us-nc/statute") / version / relative_path
            ).as_posix(),
            "absolute_path": source_path,
        }
    return source_root, sources


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().replace("\N{NON-BREAKING HYPHEN}", "-")


def _replace_once(body: str, old: str, new: str, *, overlay: str) -> str:
    count = body.count(old)
    if count != 1:
        raise ValueError(f"{overlay} expected one audited prior-text match; found {count}")
    return body.replace(old, new)


def _session_law_rewrite(path: Path, marker: str, expected_heading: str) -> str:
    """Read one full reads-as-rewritten section, deleting struck prior text."""
    soup = BeautifulSoup(path.read_bytes(), "lxml")
    paragraphs = soup.find_all("p")
    start = next(
        (
            index
            for index, paragraph in enumerate(paragraphs)
            if marker in _normalized_text(paragraph.get_text(" ", strip=True))
        ),
        None,
    )
    if start is None:
        raise ValueError(f"session-law marker not found: {marker}")
    body_lines: list[str] = []
    for paragraph in paragraphs[start + 1 :]:
        raw_classes = paragraph.get("class")
        classes = (
            {str(value).lower() for value in raw_classes}
            if isinstance(raw_classes, list)
            else set()
        )
        if "abillsection" in classes:
            break
        fragment = BeautifulSoup(str(paragraph), "lxml")
        for deleted in fragment.find_all(["s", "strike"]):
            deleted.decompose()
        line = _normalized_text(fragment.get_text(" ", strip=True))
        if line:
            body_lines.append(line)
    body = " ".join(body_lines).strip()
    body = body.removeprefix('"').strip()
    body = body.removesuffix('"').strip()
    if not body.startswith(expected_heading):
        raise ValueError(
            f"session-law rewrite does not begin with {expected_heading!r}: {body[:120]!r}"
        )
    if "…" in body:
        raise ValueError(f"session-law rewrite for {expected_heading} is not complete")
    return body


def _apply_105_153_5_overlays(body: str) -> str:
    body = _replace_once(
        body,
        "included in adjusted gross income in an earlier taxable year",
        (
            "included in adjusted gross income, as modified in G.S. 105-153.5 "
            "and G.S. 105-153.6, in an earlier taxable year"
        ),
        overlay="SL2026-31 §1.8(a), itemized repayment deduction",
    )
    body = _replace_once(
        body,
        (
            "(14a) The amount received by a taxpayer for one or more of the following: "
            "a. The Business Recovery Grant Program. "
            "b. The ReTOOLNC grant program for recovery from the economic impacts "
            "of the COVID-19 pandemic. "
            "c. Rent and utility assistance pursuant to Section 3.3 of S.L. 2020-4, "
            "as amended by Section 1.2 of S.L. 2020-97."
        ),
        (
            "(14a) The amount received by a taxpayer for rent and utility assistance "
            "pursuant to Section 3.3 of S.L. 2020-4, as amended by Section 1.2 "
            "of S.L. 2020-97."
        ),
        overlay="SL2026-31 §1.8(a), rent and utility assistance deduction",
    )
    body = _replace_once(
        body,
        "(a1) Child Deduction Amount.",
        (
            "e. The amount allowed as a deduction for wagering losses under section "
            "165(d) of the Code, to the extent the losses are not deducted in arriving "
            "at adjusted gross income. (a1) Child Deduction Amount."
        ),
        overlay="SL2026-41 §44.2(a), wagering-loss itemized deduction",
    )
    return _replace_once(
        body,
        "January 1, 2027 - see note) Certain Real Property Donations.",
        "January 1, 2031 - see note) Certain Real Property Donations.",
        overlay="SL2026-11 §24(b), donation-deduction sunset",
    )


def _apply_105_153_11_overlays(body: str) -> str:
    expiry_count = body.count("January 1, 2027")
    if expiry_count != 3:
        raise ValueError(
            "SL2026-11 §24(a)-(b) expected three donation-credit expiry references; "
            f"found {expiry_count}"
        )
    body = body.replace("January 1, 2027", "January 1, 2031")
    body = _replace_once(
        body,
        "G.S. 105-130.34A(h).",
        "G.S. 105-130.34A(i).",
        overlay="SL2026-31 §1.5(b), total allocated credits cross-reference",
    )
    body = _replace_once(
        body,
        (
            "except payments of tax made by or on behalf of the individual "
            "or pass-through entity."
        ),
        "except payments of tax made by or on behalf of the individual.",
        overlay="SL2026-31 §1.5(b), individual credit cap",
    )
    return _replace_once(
        body,
        "allocate the total requested credits in accordance with this subsection.",
        (
            "allocate the total requested credits in accordance with subsection "
            "( l ) of this section."
        ),
        overlay="SL2026-31 §1.5(b), allocation cross-reference",
    )


def _component(
    source_id: str,
    sources: dict[str, dict[str, Any]],
    sections: list[str],
    effective: str | None = None,
) -> dict[str, Any]:
    source = sources[source_id]
    component = {
        "source_id": source_id,
        "source_url": source["source_url"],
        "source_path": source["artifact_path"],
        "sha256": source["sha256"],
        "sections": sections,
    }
    if effective is not None:
        component["effective"] = effective
    return component


def build_records(
    base: Path, manifest_path: Path
) -> tuple[dict[str, Any], tuple[SourceInventoryItem, ...], tuple[ProvisionRecord, ...]]:
    manifest = _load_manifest(manifest_path)
    version = str(manifest["version"])
    if int(manifest["tax_year"]) != 2026:
        raise ValueError("this successor builder is intentionally scoped to tax year 2026")
    _, sources = _validate_sources(base, manifest)
    targets = [str(value) for value in manifest["targets"]]
    base_source = sources[BASE_SOURCE_ID]
    entry = {
        "document_id": BASE_SOURCE_ID,
        "jurisdiction": "us-nc",
        "document_class": "statute",
        "proposed_version": version,
        "parser": "new:north-carolina-statutes-html",
        "covers_citation_paths": targets,
        "version_aware_splitter": {
            "kind": "north-carolina-tax-year",
            "tax_year": 2026,
        },
    }
    provenance = {
        "url": base_source["source_url"],
        "sha256": base_source["sha256"],
        "fetched_at": base_source["fetched_at"],
    }
    _, extracted = _targeted_state_html(
        entry,
        Path(base_source["absolute_path"]).read_bytes(),
        provenance,
        str(base_source["artifact_path"]),
    )
    by_path = {record.citation_path: record for record in extracted}
    if set(by_path) != set(targets):
        raise ValueError("base chapter extraction did not produce the exact target scope")

    component_sections = {
        "us-nc/statute/105/105-153.5": [
            _component(BASE_SOURCE_ID, sources, ["105-153.5"]),
            _component("sl-2026-11", sources, ["24(b)"], "2026-06-22"),
            _component(
                "sl-2026-31",
                sources,
                ["1.8"],
                "taxable years beginning on or after 2026-01-01",
            ),
            _component(
                "sl-2026-41",
                sources,
                ["44.2"],
                "taxable years beginning on or after 2025-01-01",
            ),
        ],
        "us-nc/statute/105/105-153.7": [
            _component(BASE_SOURCE_ID, sources, ["105-153.7"]),
            _component("sl-2026-41", sources, ["44.1"], "2026-07-07"),
        ],
        "us-nc/statute/105/105-153.9": [
            _component(BASE_SOURCE_ID, sources, ["105-153.9"]),
        ],
        "us-nc/statute/105/105-153.11": [
            _component(BASE_SOURCE_ID, sources, ["105-153.11"]),
            _component(
                "sl-2026-11", sources, ["24(a)", "24(b)"], "2026-06-22"
            ),
            _component("sl-2026-31", sources, ["1.5(b)"], "2026-07-02"),
        ],
    }
    bodies = {path: record.body or "" for path, record in by_path.items()}
    bodies["us-nc/statute/105/105-153.5"] = _apply_105_153_5_overlays(
        bodies["us-nc/statute/105/105-153.5"]
    )
    bodies["us-nc/statute/105/105-153.7"] = _session_law_rewrite(
        Path(sources["sl-2026-41"]["absolute_path"]),
        "SECTION 44.1.(a)",
        "§ 105-153.7.",
    )
    bodies["us-nc/statute/105/105-153.11"] = _apply_105_153_11_overlays(
        bodies["us-nc/statute/105/105-153.11"]
    )

    records: list[ProvisionRecord] = []
    inventory: list[SourceInventoryItem] = []
    for ordinal, path in enumerate(targets, 1):
        original = by_path[path]
        metadata = dict(original.metadata or {})
        metadata.update(
            {
                "tax_year": 2026,
                "temporal_consolidation": "base statute plus enacted session-law overlays",
                "component_sources": component_sections[path],
                "consolidated_body_sha256": hashlib.sha256(
                    bodies[path].encode()
                ).hexdigest(),
                "liability_status": manifest["liability_status"],
            }
        )
        record = ProvisionRecord(
            id=deterministic_provision_id(path, version),
            jurisdiction="us-nc",
            document_class="statute",
            citation_path=path,
            body=bodies[path],
            citation_label=original.citation_label,
            version=version,
            source_url=str(base_source["source_url"]),
            source_path=str(base_source["artifact_path"]),
            source_id=BASE_SOURCE_ID,
            source_format="html",
            source_as_of=str(manifest["expression_date"]),
            expression_date=str(manifest["expression_date"]),
            level=2,
            ordinal=ordinal,
            kind="section",
            metadata=metadata,
        )
        records.append(record)
        inventory.append(
            SourceInventoryItem(
                citation_path=path,
                source_url=record.source_url,
                source_path=record.source_path,
                source_format="html",
                sha256=str(base_source["sha256"]),
                metadata=metadata,
            )
        )
    return manifest, tuple(inventory), tuple(records)


def build_scope(base: Path, manifest_path: Path) -> tuple[Path, Path, Path]:
    manifest, inventory, records = build_records(base, manifest_path)
    version = str(manifest["version"])
    coverage = compare_provision_coverage(
        inventory, records, "us-nc", "statute", version
    )
    if not coverage.complete:
        raise ValueError("NC TY2026 successor scope does not have complete coverage")
    store = CorpusArtifactStore(base)
    inventory_path = store.inventory_path("us-nc", "statute", version)
    provisions_path = store.provisions_path("us-nc", "statute", version)
    coverage_path = store.coverage_path("us-nc", "statute", version)
    store.write_inventory(inventory_path, inventory)
    store.write_provisions(provisions_path, records)
    store.write_json(coverage_path, coverage.to_mapping())
    return inventory_path, provisions_path, coverage_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    for path in build_scope(args.base, args.manifest):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
