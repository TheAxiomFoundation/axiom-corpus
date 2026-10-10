#!/usr/bin/env python3
"""Reproduce the USITC HTS 2026 Revision 15 snapshot ingest.

Ingests 2026 Revision 15 of the USITC Harmonized Tariff Schedule,
normalizing chapters 72, 76, and 95 plus every 9903 row, extending the
Basic-through-Revision-14 series ingested by ``us_hts_tariff_snapshots.py``
and ``us_hts_tariff_snapshots_2026_gapfill.py``.

Revision 15 was published August 3, 2026; its change record lists a single
substantive modification (9903.04.63, rates of duty, effective July 31,
2026). At ingest time (2026-08-04) USITC had not yet published the static
full-edition JSON file for Revision 15, so the retained source bytes are
the official ``hts.usitc.gov/reststop/exportList`` full-schedule response
(0101-9999) fetched while ``reststop/currentRelease`` reported
``2026HTSRev15`` both immediately before and immediately after the
download. The Internet Archive Save Page Now service did not return a
capture during the ingest window, so the Wayback fields are null,
following the Revision 11 precedent in the 2026 gapfill run. The retained
input is pinned by SHA-256 and byte size and fully verified in a temporary
staging directory before any destination artifact is written.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from axiom_corpus.corpus import documents
from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import OfficialDocumentSource, _DocumentBlock
from axiom_corpus.corpus.models import DocumentClass

REPO_ROOT = Path(__file__).resolve().parents[2]
RETAINED_BASE = REPO_ROOT / "data/corpus"

JURISDICTION = "us"
DOCUMENT_CLASS = DocumentClass.STATUTE.value
CITATION_ROOT = "us/statute/hts"
SOURCE_AS_OF = "2026-08-04"
EDITION = "2026"
CHAPTER_PREFIXES = ("72", "76", "95", "9903")
RESTSTOP_EXPORT_URL = (
    "https://hts.usitc.gov/reststop/exportList?from=0101&to=9999&format=JSON&styles=false"
)
EXPECTED_STATIC_URL = (
    "https://www.usitc.gov/sites/default/files/tata/hts/hts_2026_revision_15_json.json"
)
RELEASE_NAME = "2026HTSRev15"
REPRO_COMMAND = (
    "uv run --extra dev python "
    "scripts/repro/us_hts_tariff_snapshots_2026_rev15.py --base data/corpus"
)


@dataclass(frozen=True)
class RevisionSnapshot:
    """One pinned full-edition USITC HTS JSON snapshot."""

    revision: int | str
    expression_date: str
    sha256: str
    size_bytes: int
    total_rows: int
    target_rows: int
    rows_by_chapter: dict[str, int]

    @property
    def key(self) -> str:
        return str(self.revision)

    @property
    def version(self) -> str:
        return f"{SOURCE_AS_OF}-usitc-hts-{EDITION}-rev{self.revision}"

    @property
    def official_filename(self) -> str:
        return f"hts_{EDITION}_revision_{self.revision}_json.json"

    @property
    def official_url(self) -> str:
        return RESTSTOP_EXPORT_URL

    @property
    def download_url(self) -> str:
        return RESTSTOP_EXPORT_URL

    @property
    def source_id(self) -> str:
        return f"usitc-hts-{EDITION}-rev{self.revision}"

    @property
    def title(self) -> str:
        return (
            f"Harmonized Tariff Schedule of the United States ({EDITION}) Revision {self.revision}"
        )


SNAPSHOTS = (
    RevisionSnapshot(
        revision=15,
        expression_date="2026-08-03",
        sha256="59a76c12e28d7a28975f31a8876bfb08e64927b922fe2b4f88801ff4459181e6",
        size_bytes=12_630_559,
        total_rows=35_789,
        target_rows=1_706,
        rows_by_chapter={"72": 740, "76": 182, "95": 162, "9903": 622},
    ),
)


def _download_provenance(snapshot: RevisionSnapshot) -> dict[str, Any]:
    return {
        "kind": "usitc_reststop_export",
        "url": RESTSTOP_EXPORT_URL,
        "release_name": RELEASE_NAME,
        "release_checked_before_and_after_download": True,
        "expected_static_url": EXPECTED_STATIC_URL,
        "static_url_published_at_ingest": False,
    }


def _mirror_verification(snapshot: RevisionSnapshot) -> str:
    return (
        "official reststop exportList response (0101-9999) retained while "
        f"reststop/currentRelease reported {RELEASE_NAME} immediately before "
        "and after the download; the USITC static full-edition JSON for "
        "Revision 15 was not yet published at ingest time and the Internet "
        "Archive Save Page Now service returned no capture during the ingest "
        "window (Revision 11 gapfill precedent), so Wayback fields are null"
    )


# Regime anchors are literal excerpts observed in the normalized bodies built
# from the pinned input. 9903.04.63 carries the single substantive Revision 15
# change (UK patented-pharmaceutical rate reduced to zero effective July 31,
# 2026, per the Revision 15 change record and 91 FR 49406); 9903.05.20 pins
# forced-labor section 301 finalization continuity and 9903.03.01 pins the
# section 122 heading's continued presence in the schedule text.
EXPECTED_EXCERPTS: dict[str, dict[str, tuple[str, ...]]] = {
    "15": {
        f"{CITATION_ROOT}/9903.04.63": (
            "Patented pharmaceutical articles that are the product of the United Kingdom",
            "The duty provided in the applicable subheading +0%",
        ),
        f"{CITATION_ROOT}/9903.05.20": (
            "articles the product of Algeria",
            "The duty provided in the applicable subheading + 12.5%",
        ),
        f"{CITATION_ROOT}/9903.03.01": ("The duty provided in the applicable subheading + 10%",),
        f"{CITATION_ROOT}/7202.11.10.00": ("Rates of duty (1-General): 1.4%",),
    },
}

BODY_FIELD_LABELS = (
    ("Rates of duty (1-General)", "general"),
    ("Rates of duty (1-Special)", "special"),
    ("Rates of duty (2)", "other"),
    ("Additional duties", "additionalDuties"),
    ("Quota quantity", "quotaQuantity"),
)


def _canonical_source_path(snapshot: RevisionSnapshot) -> Path:
    return (
        Path("sources")
        / JURISDICTION
        / DOCUMENT_CLASS
        / snapshot.version
        / "usitc-hts"
        / snapshot.official_filename
    )


def _inventory_path(snapshot: RevisionSnapshot) -> Path:
    return Path("inventory") / JURISDICTION / DOCUMENT_CLASS / f"{snapshot.version}.json"


def _provisions_path(snapshot: RevisionSnapshot) -> Path:
    return Path("provisions") / JURISDICTION / DOCUMENT_CLASS / f"{snapshot.version}.jsonl"


def _coverage_path(snapshot: RevisionSnapshot) -> Path:
    return Path("coverage") / JURISDICTION / DOCUMENT_CLASS / f"{snapshot.version}.json"


GENERATED_RELATIVE_PATHS = tuple(
    path
    for snapshot in SNAPSHOTS
    for path in (
        _canonical_source_path(snapshot),
        _inventory_path(snapshot),
        _provisions_path(snapshot),
        _coverage_path(snapshot),
    )
)


def _resolve_input_path(source_dir: Path, snapshot: RevisionSnapshot) -> Path:
    candidates = (
        source_dir / snapshot.official_filename,
        source_dir / "hts_2026_rev15_reststop_full.json",
        source_dir / _canonical_source_path(snapshot),
    )
    for candidate in candidates:
        if candidate.is_symlink():
            raise ValueError(f"official source must not be a symlink: {candidate}")
        if candidate.is_file():
            return candidate
    choices = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        f"official source {snapshot.official_filename} not found; checked {choices}"
    )


def _read_verified_sources(source_dir: Path) -> dict[str, bytes]:
    source_bytes: dict[str, bytes] = {}
    for snapshot in SNAPSHOTS:
        content = _resolve_input_path(source_dir, snapshot).read_bytes()
        actual_hash = sha256_bytes(content)
        if actual_hash != snapshot.sha256:
            raise ValueError(
                f"official source hash mismatch for snapshot {snapshot.key}: "
                f"expected {snapshot.sha256}, got {actual_hash}"
            )
        if len(content) != snapshot.size_bytes:
            raise ValueError(
                f"official source size mismatch for snapshot {snapshot.key}: "
                f"expected {snapshot.size_bytes}, got {len(content)}"
            )
        source_bytes[snapshot.key] = content
    return source_bytes


def _is_target_row(row: dict[str, Any]) -> bool:
    htsno = str(row.get("htsno") or "")
    return htsno.startswith(CHAPTER_PREFIXES)


def _chapter_key(htsno: str) -> str:
    return "9903" if htsno.startswith("9903") else htsno[:2]


def _row_body(row: dict[str, Any]) -> str:
    lines = [str(row.get("description") or "").strip()]
    units = [str(unit).strip() for unit in row.get("units") or [] if str(unit).strip()]
    if units:
        lines.append("Unit of quantity: " + ", ".join(units))
    for label, field in BODY_FIELD_LABELS:
        value = str(row.get(field) or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    for footnote in row.get("footnotes") or []:
        columns = ",".join(str(column) for column in footnote.get("columns") or [] if str(column))
        value = str(footnote.get("value") or "").strip()
        if value:
            lines.append(f"Footnote [{columns}]: {value}")
    return "\n".join(lines)


def _target_blocks(rows: list[Any]) -> tuple[_DocumentBlock, ...]:
    blocks: list[_DocumentBlock] = []
    ancestors: list[dict[str, str]] = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"non-object HTS row at index {row_index}")
        indent_text = str(row.get("indent") or "0").strip()
        if not indent_text.isdigit():
            raise ValueError(f"non-numeric HTS indent at index {row_index}")
        indent = int(indent_text)
        while ancestors and int(ancestors[-1]["indent"]) >= indent:
            ancestors.pop()
        if _is_target_row(row):
            htsno = str(row["htsno"])
            body = _row_body(row)
            if not body.strip():
                raise ValueError(f"empty body for HTS row {htsno}")
            blocks.append(
                _DocumentBlock(
                    kind="hts-row",
                    ordinal=len(blocks) + 1,
                    heading=f"HTS {htsno}",
                    body=body,
                    metadata={
                        "citation_suffix": htsno,
                        "section_label": htsno,
                        "htsno": htsno,
                        "indent": indent,
                        "superior": row.get("superior"),
                        "units": row.get("units"),
                        "general": row.get("general"),
                        "special": row.get("special"),
                        "other": row.get("other"),
                        "footnotes": row.get("footnotes"),
                        "quotaQuantity": row.get("quotaQuantity"),
                        "additionalDuties": row.get("additionalDuties"),
                        "row_index": row_index,
                        "ancestors": list(ancestors),
                    },
                )
            )
        description = str(row.get("description") or "").strip()
        if description:
            ancestors.append(
                {
                    "indent": str(indent),
                    "htsno": str(row.get("htsno") or ""),
                    "description": description,
                }
            )
    return tuple(blocks)


def _snapshot_metadata(snapshot: RevisionSnapshot) -> dict[str, Any]:
    return {
        "edition": EDITION,
        "revision": snapshot.revision,
        "revision_effective_date": snapshot.expression_date,
        "release": RELEASE_NAME,
        "download_provenance": _download_provenance(snapshot),
        "wayback_timestamp": None,
        "wayback_url": None,
        "wayback_body_gzip": None,
        "expected_static_url": EXPECTED_STATIC_URL,
        "static_url_published_at_ingest": False,
        "mirror_verification": _mirror_verification(snapshot),
        "chapter_prefixes": list(CHAPTER_PREFIXES),
        "total_rows": snapshot.total_rows,
    }


def _snapshot_source(snapshot: RevisionSnapshot) -> OfficialDocumentSource:
    return OfficialDocumentSource(
        source_id=snapshot.source_id,
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS,
        title=snapshot.title,
        source_url=snapshot.official_url,
        citation_path=CITATION_ROOT,
        source_format="json",
        source_as_of=SOURCE_AS_OF,
        expression_date=snapshot.expression_date,
        metadata=_snapshot_metadata(snapshot),
    )


def _build_snapshot_scope(
    staging_base: Path,
    snapshot: RevisionSnapshot,
    content: bytes,
) -> dict[str, Any]:
    rows = json.loads(content.decode("utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"snapshot {snapshot.key} is not a JSON list")
    if len(rows) != snapshot.total_rows:
        raise ValueError(
            f"unexpected total row count for snapshot {snapshot.key}: "
            f"expected {snapshot.total_rows}, got {len(rows)}"
        )
    blocks = _target_blocks(rows)
    if len(blocks) != snapshot.target_rows:
        raise ValueError(
            f"unexpected target row count for snapshot {snapshot.key}: "
            f"expected {snapshot.target_rows}, got {len(blocks)}"
        )
    actual_by_chapter = Counter(_chapter_key(str(block.metadata["htsno"])) for block in blocks)
    if dict(actual_by_chapter) != snapshot.rows_by_chapter:
        raise ValueError(
            f"unexpected chapter breakdown for snapshot {snapshot.key}: "
            f"expected {snapshot.rows_by_chapter}, got {dict(actual_by_chapter)}"
        )
    htsnos = [str(block.metadata["htsno"]) for block in blocks]
    if len(set(htsnos)) != len(htsnos):
        duplicates = [item for item, count in Counter(htsnos).items() if count > 1]
        raise ValueError(f"duplicate HTS numbers in snapshot {snapshot.key}: {duplicates}")

    source = _snapshot_source(snapshot)
    store = CorpusArtifactStore(staging_base)
    canonical_source = _canonical_source_path(snapshot)
    source_sha = store.write_bytes(staging_base / canonical_source, content)
    source_key = canonical_source.as_posix()

    inventory = documents._inventory_items(
        source,
        blocks=blocks,
        source_key=source_key,
        source_format="json",
        source_sha=source_sha,
        content_type="application/json",
        final_url=snapshot.download_url,
    )
    records = documents._provision_records(
        source,
        blocks=blocks,
        version=snapshot.version,
        source_key=source_key,
        source_format="json",
        source_as_of=SOURCE_AS_OF,
        expression_date=snapshot.expression_date,
        content_type="application/json",
        final_url=snapshot.download_url,
    )
    store.write_inventory(staging_base / _inventory_path(snapshot), list(inventory))
    store.write_provisions(staging_base / _provisions_path(snapshot), list(records))
    coverage = compare_provision_coverage(
        tuple(inventory),
        tuple(records),
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS,
        version=snapshot.version,
    )
    if not coverage.complete:
        raise ValueError(
            f"incomplete coverage for snapshot {snapshot.key}: {coverage.to_mapping()}"
        )
    store.write_json(staging_base / _coverage_path(snapshot), coverage.to_mapping())
    return {
        "revision": snapshot.revision,
        "version": snapshot.version,
        "row_count": len(records),
        "rows_by_chapter": dict(actual_by_chapter),
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _verify_generated_scope(
    staging_base: Path,
    source_bytes: dict[str, bytes],
) -> None:
    for snapshot in SNAPSHOTS:
        generated = (staging_base / _canonical_source_path(snapshot)).read_bytes()
        if generated != source_bytes[snapshot.key]:
            raise ValueError(f"generated source is not byte-equal for snapshot {snapshot.key}")

        rows = _load_jsonl(staging_base / _provisions_path(snapshot))
        rows_by_path = {row["citation_path"]: row for row in rows}
        if len(rows) != len(rows_by_path):
            raise ValueError(f"duplicate citation paths in snapshot {snapshot.key}")
        if len(rows) != snapshot.target_rows + 1:
            raise ValueError(
                f"unexpected provision count for snapshot {snapshot.key}: "
                f"expected {snapshot.target_rows + 1}, got {len(rows)}"
            )
        root_row = rows_by_path.get(CITATION_ROOT)
        if root_row is None or root_row.get("kind") != "document":
            raise ValueError(f"missing document root row for snapshot {snapshot.key}")

        expected_metadata = _snapshot_metadata(snapshot)
        for row in rows:
            if row.get("version") != snapshot.version:
                raise ValueError(
                    f"unexpected version on {row['citation_path']} for snapshot {snapshot.key}"
                )
            if row.get("expression_date") != snapshot.expression_date:
                raise ValueError(
                    f"unexpected expression_date on {row['citation_path']} for "
                    f"snapshot {snapshot.key}"
                )
            if row.get("source_url") != snapshot.official_url:
                raise ValueError(
                    f"unexpected source_url on {row['citation_path']} for snapshot {snapshot.key}"
                )
            metadata = row.get("metadata", {})
            if metadata.get("download_url") != snapshot.download_url:
                raise ValueError(
                    f"unexpected download_url on {row['citation_path']} for snapshot {snapshot.key}"
                )
            for key, expected in expected_metadata.items():
                if metadata.get(key) != expected:
                    raise ValueError(
                        f"unexpected metadata field {key} on {row['citation_path']} "
                        f"for snapshot {snapshot.key}"
                    )

        for citation_path, excerpts in EXPECTED_EXCERPTS.get(snapshot.key, {}).items():
            row = rows_by_path.get(citation_path)
            if row is None:
                raise ValueError(f"missing anchor row {citation_path} in snapshot {snapshot.key}")
            body = str(row.get("body") or "")
            for excerpt in excerpts:
                if excerpt not in body:
                    raise ValueError(
                        f"required excerpt missing from {citation_path} in "
                        f"snapshot {snapshot.key}: {excerpt}"
                    )

        inventory = json.loads(
            (staging_base / _inventory_path(snapshot)).read_text(encoding="utf-8")
        )["items"]
        if {item["citation_path"] for item in inventory} != set(rows_by_path):
            raise ValueError(f"inventory/provision paths differ for snapshot {snapshot.key}")

        coverage = json.loads((staging_base / _coverage_path(snapshot)).read_text(encoding="utf-8"))
        expected_fields = {
            "complete": True,
            "document_class": DOCUMENT_CLASS,
            "jurisdiction": JURISDICTION,
            "matched_count": snapshot.target_rows + 1,
            "provision_count": snapshot.target_rows + 1,
            "source_count": snapshot.target_rows + 1,
            "version": snapshot.version,
        }
        for key, expected in expected_fields.items():
            if coverage.get(key) != expected:
                raise ValueError(
                    f"unexpected coverage field {key} for snapshot "
                    f"{snapshot.key}: expected {expected!r}, got {coverage.get(key)!r}"
                )


def reproduce(base: Path, source_dir: Path | None = None) -> dict[str, Any]:
    target_base = base.resolve()
    input_root = (source_dir or RETAINED_BASE).resolve()
    source_bytes = _read_verified_sources(input_root)

    with TemporaryDirectory(prefix="repro-us-hts-2026-rev15-") as staging_name:
        staging_base = Path(staging_name) / "corpus"
        scopes = [
            _build_snapshot_scope(staging_base, snapshot, source_bytes[snapshot.key])
            for snapshot in SNAPSHOTS
        ]
        _verify_generated_scope(staging_base, source_bytes)

        target_store = CorpusArtifactStore(target_base)
        generated_hashes: dict[str, str] = {}
        for relative_path in GENERATED_RELATIVE_PATHS:
            content = (staging_base / relative_path).read_bytes()
            target_store.write_bytes(target_base / relative_path, content)
            generated_hashes[relative_path.as_posix()] = sha256_bytes(content)

    return {
        "base": str(target_base),
        "command": REPRO_COMMAND,
        "files": generated_hashes,
        "scopes": scopes,
        "source_sha256": {snapshot.official_filename: snapshot.sha256 for snapshot in SNAPSHOTS},
        "versions": [snapshot.version for snapshot in SNAPSHOTS],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        type=Path,
        required=True,
        help="Destination corpus base.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help=(
            "Optional local input root. Accepts the flat official filename, "
            "the raw reststop download name, or the retained canonical path; "
            "defaults to repository data/corpus."
        ),
    )
    args = parser.parse_args()
    print(json.dumps(reproduce(args.base, args.source_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
