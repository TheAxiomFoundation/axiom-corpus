#!/usr/bin/env python3
"""Reproduce the USITC HTS 2025 Revision 11-21 snapshot ingest.

Ingests eleven full-revision USITC Harmonized Tariff Schedule JSON snapshots
(Revisions 11 through 21 of the 2025 edition) and normalizes the tariff rows
for chapters 72, 76, and 95 plus every Chapter 99 heading in the 9903 family.

Each retained source is a pinned Internet Archive Wayback Machine capture of
the official USITC static URL and was byte-verified after gunzip against the
corresponding Yale Budget Lab tariff-rate-tracker archive. Revision 12's
capture metadata does not establish whether the Wayback response body was
gzip encoded, so that field is retained explicitly as null.
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
SOURCE_AS_OF = "2026-08-01"
CHAPTER_PREFIXES = ("72", "76", "95", "9903")
OFFICIAL_URL_TEMPLATE = (
    "https://www.usitc.gov/sites/default/files/tata/hts/"
    "hts_2025_revision_{revision}_json.json"
)
WAYBACK_URL_TEMPLATE = "https://web.archive.org/web/{timestamp}id_/{official_url}"
YALE_MIRROR_REPOSITORY = "yale-budget-lab/tariff-rate-tracker"
YALE_MIRROR_PATH_TEMPLATE = "data/hts_archives/{filename}"
REPRO_COMMAND = (
    "uv run --extra dev python "
    "scripts/repro/us_hts_tariff_snapshots_2025_part2.py "
    "--base data/corpus "
    "--source-dir ~/.axiom/workspace/laneA-hts-downloads"
)


@dataclass(frozen=True)
class RevisionSnapshot:
    """One pinned full-revision USITC HTS JSON snapshot."""

    revision: int
    expression_date: str
    yale_cover_date: str | None
    wayback_timestamp: str
    wayback_body_gzip: bool | None
    sha256: str
    size_bytes: int
    total_rows: int
    target_rows: int
    rows_by_chapter: dict[str, int]
    yale_mirror: str
    yale_gunzip_sha256: str
    yale_byte_equal: bool

    @property
    def version(self) -> str:
        return f"2026-08-01-usitc-hts-2025-rev{self.revision}"

    @property
    def official_filename(self) -> str:
        return f"hts_2025_revision_{self.revision}_json.json"

    @property
    def official_url(self) -> str:
        return OFFICIAL_URL_TEMPLATE.format(revision=self.revision)

    @property
    def wayback_url(self) -> str:
        return WAYBACK_URL_TEMPLATE.format(
            timestamp=self.wayback_timestamp,
            official_url=self.official_url,
        )

    @property
    def yale_mirror_path(self) -> str:
        return YALE_MIRROR_PATH_TEMPLATE.format(filename=self.yale_mirror)

    @property
    def mirror_verification(self) -> str:
        return (
            "byte-identical to Yale Budget Lab mirror "
            f"{YALE_MIRROR_REPOSITORY}:{self.yale_mirror_path} after gunzip "
            f"(gunzip SHA-256 {self.yale_gunzip_sha256})"
        )

    @property
    def source_id(self) -> str:
        return f"usitc-hts-2025-rev{self.revision}"

    @property
    def title(self) -> str:
        return (
            "Harmonized Tariff Schedule of the United States (2025) "
            f"Revision {self.revision}"
        )


SNAPSHOTS = (
    RevisionSnapshot(
        revision=11,
        expression_date="2025-05-02",
        yale_cover_date="2025-04-11",
        wayback_timestamp="20260121194850",
        wayback_body_gzip=True,
        sha256="4ea6932ffbb8106dd2c7a2199d85475d07a3f486c68ff40068c9a0ce81a793a9",
        size_bytes=13_723_914,
        total_rows=35_940,
        target_rows=1_604,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 525},
        yale_mirror="hts_2025_rev_11.json.gz",
        yale_gunzip_sha256=(
            "4ea6932ffbb8106dd2c7a2199d85475d07a3f486c68ff40068c9a0ce81a793a9"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=12,
        expression_date="2025-05-13",
        yale_cover_date="2025-04-14",
        wayback_timestamp="20260106230832",
        wayback_body_gzip=None,
        sha256="5e8ed076fdde81f65b17b1df38e905dd5a79c22f7619d7784a8153eacae523ad",
        size_bytes=13_723_583,
        total_rows=35_940,
        target_rows=1_604,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 525},
        yale_mirror="hts_2025_rev_12.json.gz",
        yale_gunzip_sha256=(
            "5e8ed076fdde81f65b17b1df38e905dd5a79c22f7619d7784a8153eacae523ad"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=13,
        expression_date="2025-05-16",
        yale_cover_date="2025-04-22",
        wayback_timestamp="20260121194604",
        wayback_body_gzip=True,
        sha256="5e8ed076fdde81f65b17b1df38e905dd5a79c22f7619d7784a8153eacae523ad",
        size_bytes=13_723_583,
        total_rows=35_940,
        target_rows=1_604,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 525},
        yale_mirror="hts_2025_rev_13.json.gz",
        yale_gunzip_sha256=(
            "5e8ed076fdde81f65b17b1df38e905dd5a79c22f7619d7784a8153eacae523ad"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=14,
        expression_date="2025-06-06",
        yale_cover_date="2025-05-02",
        wayback_timestamp="20260121194441",
        wayback_body_gzip=True,
        sha256="0eb0ebeeff04d260ba6b05a16b23350eff4b93d38863ca8387d3b9555eaea43f",
        size_bytes=13_775_425,
        total_rows=35_950,
        target_rows=1_614,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 535},
        yale_mirror="hts_2025_rev_14.json.gz",
        yale_gunzip_sha256=(
            "0eb0ebeeff04d260ba6b05a16b23350eff4b93d38863ca8387d3b9555eaea43f"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=15,
        expression_date="2025-06-20",
        yale_cover_date="2025-05-14",
        wayback_timestamp="20260121194320",
        wayback_body_gzip=True,
        sha256="83e5fc468a032b72c7f3759add0290b6bd2ba53fca40f73a5da0c59f9511a444",
        size_bytes=13_731_683,
        total_rows=35_950,
        target_rows=1_614,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 535},
        yale_mirror="hts_2025_rev_15.json.gz",
        yale_gunzip_sha256=(
            "83e5fc468a032b72c7f3759add0290b6bd2ba53fca40f73a5da0c59f9511a444"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=16,
        expression_date="2025-07-01",
        yale_cover_date="2025-06-06",
        wayback_timestamp="20260121194147",
        wayback_body_gzip=True,
        sha256="69a3ddee24ff58342dbfcc74cc9eb2be8c405cf6fff72eb5407bdea66c2c503e",
        size_bytes=13_750_683,
        total_rows=36_007,
        target_rows=1_619,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 538},
        yale_mirror="hts_2025_rev_16.json.gz",
        yale_gunzip_sha256=(
            "69a3ddee24ff58342dbfcc74cc9eb2be8c405cf6fff72eb5407bdea66c2c503e"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=17,
        expression_date="2025-08-01",
        yale_cover_date="2025-07-01",
        wayback_timestamp="20260121194040",
        wayback_body_gzip=True,
        sha256="7940afb35ab29c4c09903d9fbe4f5ef0f99ee0a4fa7983976bc2c5ce5e6acba2",
        size_bytes=13_752_527,
        total_rows=36_009,
        target_rows=1_622,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 541},
        yale_mirror="hts_2025_rev_17.json.gz",
        yale_gunzip_sha256=(
            "7940afb35ab29c4c09903d9fbe4f5ef0f99ee0a4fa7983976bc2c5ce5e6acba2"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=18,
        expression_date="2025-08-07",
        yale_cover_date="2025-08-07",
        wayback_timestamp="20260106230033",
        wayback_body_gzip=False,
        sha256="f03008f78466bdbe4130790b9341a03ff14248f54c82e682d4287901a7307d12",
        size_bytes=13_836_410,
        total_rows=36_087,
        target_rows=1_700,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 619},
        yale_mirror="hts_2025_rev_18.json.gz",
        yale_gunzip_sha256=(
            "f03008f78466bdbe4130790b9341a03ff14248f54c82e682d4287901a7307d12"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=19,
        expression_date="2025-08-18",
        yale_cover_date="2025-08-12",
        wayback_timestamp="20260121193740",
        wayback_body_gzip=True,
        sha256="f03008f78466bdbe4130790b9341a03ff14248f54c82e682d4287901a7307d12",
        size_bytes=13_836_410,
        total_rows=36_087,
        target_rows=1_700,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 619},
        yale_mirror="hts_2025_rev_19.json.gz",
        yale_gunzip_sha256=(
            "f03008f78466bdbe4130790b9341a03ff14248f54c82e682d4287901a7307d12"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=20,
        expression_date="2025-08-27",
        yale_cover_date="2025-08-20",
        wayback_timestamp="20250901214308",
        wayback_body_gzip=True,
        sha256="cf8694ac954664df3eaf978cf27243e684520301ebc42ec39cebade38596f4ef",
        size_bytes=13_841_823,
        total_rows=36_093,
        target_rows=1_706,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 625},
        yale_mirror="hts_2025_rev_20.json.gz",
        yale_gunzip_sha256=(
            "cf8694ac954664df3eaf978cf27243e684520301ebc42ec39cebade38596f4ef"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=21,
        expression_date="2025-08-29",
        yale_cover_date="2025-08-28",
        wayback_timestamp="20260106230916",
        wayback_body_gzip=False,
        sha256="dd2ecdfc045eedfcd7080bf9ddbd3741c08ccee412e0c109f5edccbd772a13dc",
        size_bytes=13_841_826,
        total_rows=36_093,
        target_rows=1_706,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 625},
        yale_mirror="hts_2025_rev_21.json.gz",
        yale_gunzip_sha256=(
            "dd2ecdfc045eedfcd7080bf9ddbd3741c08ccee412e0c109f5edccbd772a13dc"
        ),
        yale_byte_equal=True,
    ),
)

# Anchors are matched against normalized provision bodies. Both headings are
# present in all eleven source snapshots with these official rate strings.
EXPECTED_EXCERPTS: dict[int, dict[str, tuple[str, ...]]] = {
    snapshot.revision: {
        f"{CITATION_ROOT}/7202.11.10.00": ("Rates of duty (1-General): 1.4%",),
        f"{CITATION_ROOT}/9903.01.25": (
            "The duty provided in the applicable subheading + 10%",
        ),
    }
    for snapshot in SNAPSHOTS
}

# Section 122 heading 9903.03.01 does not occur in any 2025 snapshot.
EXPECTED_ABSENT: dict[int, tuple[str, ...]] = {
    snapshot.revision: (f"{CITATION_ROOT}/9903.03.01",) for snapshot in SNAPSHOTS
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


def _read_verified_sources(source_dir: Path) -> dict[int, bytes]:
    source_bytes: dict[int, bytes] = {}
    for snapshot in SNAPSHOTS:
        content = _resolve_input_path(source_dir, snapshot).read_bytes()
        actual_hash = sha256_bytes(content)
        if actual_hash != snapshot.sha256:
            raise ValueError(
                f"official source hash mismatch for revision {snapshot.revision}: "
                f"expected {snapshot.sha256}, got {actual_hash}"
            )
        if len(content) != snapshot.size_bytes:
            raise ValueError(
                f"official source size mismatch for revision {snapshot.revision}: "
                f"expected {snapshot.size_bytes}, got {len(content)}"
            )
        if not snapshot.yale_byte_equal:
            raise ValueError(
                f"revision {snapshot.revision} is not marked byte-equal to its Yale mirror"
            )
        if snapshot.yale_gunzip_sha256 != snapshot.sha256:
            raise ValueError(
                f"Yale gunzip hash differs from retained source hash for revision "
                f"{snapshot.revision}"
            )
        source_bytes[snapshot.revision] = content
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
        metadata={
            "edition": "2025",
            "revision": snapshot.revision,
            "revision_effective_date": snapshot.expression_date,
            "yale_cover_date": snapshot.yale_cover_date,
            "wayback_timestamp": snapshot.wayback_timestamp,
            "wayback_url": snapshot.wayback_url,
            "wayback_body_gzip": snapshot.wayback_body_gzip,
            "yale_mirror_repository": YALE_MIRROR_REPOSITORY,
            "yale_mirror_path": snapshot.yale_mirror_path,
            "yale_gunzip_sha256": snapshot.yale_gunzip_sha256,
            "yale_byte_equal": snapshot.yale_byte_equal,
            "mirror_verification": snapshot.mirror_verification,
            "chapter_prefixes": list(CHAPTER_PREFIXES),
            "total_rows": snapshot.total_rows,
        },
    )


def _build_snapshot_scope(
    staging_base: Path,
    snapshot: RevisionSnapshot,
    content: bytes,
) -> dict[str, Any]:
    rows = json.loads(content.decode("utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"revision {snapshot.revision} snapshot is not a JSON list")
    if len(rows) != snapshot.total_rows:
        raise ValueError(
            f"unexpected total row count for revision {snapshot.revision}: "
            f"expected {snapshot.total_rows}, got {len(rows)}"
        )
    blocks = _target_blocks(rows)
    if len(blocks) != snapshot.target_rows:
        raise ValueError(
            f"unexpected target row count for revision {snapshot.revision}: "
            f"expected {snapshot.target_rows}, got {len(blocks)}"
        )
    actual_by_chapter = Counter(_chapter_key(str(block.metadata["htsno"])) for block in blocks)
    if dict(actual_by_chapter) != snapshot.rows_by_chapter:
        raise ValueError(
            f"unexpected chapter breakdown for revision {snapshot.revision}: "
            f"expected {snapshot.rows_by_chapter}, got {dict(actual_by_chapter)}"
        )
    htsnos = [str(block.metadata["htsno"]) for block in blocks]
    if len(set(htsnos)) != len(htsnos):
        duplicates = [item for item, count in Counter(htsnos).items() if count > 1]
        raise ValueError(f"duplicate HTS numbers in revision {snapshot.revision}: {duplicates}")

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
        final_url=snapshot.wayback_url,
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
        final_url=snapshot.wayback_url,
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
            f"incomplete coverage for revision {snapshot.revision}: {coverage.to_mapping()}"
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
    source_bytes: dict[int, bytes],
) -> None:
    for snapshot in SNAPSHOTS:
        generated = (staging_base / _canonical_source_path(snapshot)).read_bytes()
        if generated != source_bytes[snapshot.revision]:
            raise ValueError(f"generated source is not byte-equal for revision {snapshot.revision}")

        rows = _load_jsonl(staging_base / _provisions_path(snapshot))
        rows_by_path = {row["citation_path"]: row for row in rows}
        if len(rows) != len(rows_by_path):
            raise ValueError(f"duplicate citation paths in revision {snapshot.revision}")
        if len(rows) != snapshot.target_rows + 1:
            raise ValueError(
                f"unexpected provision count for revision {snapshot.revision}: "
                f"expected {snapshot.target_rows + 1}, got {len(rows)}"
            )
        root_row = rows_by_path.get(CITATION_ROOT)
        if root_row is None or root_row.get("kind") != "document":
            raise ValueError(f"missing document root row for revision {snapshot.revision}")
        for row in rows:
            if row.get("version") != snapshot.version:
                raise ValueError(
                    f"unexpected version on {row['citation_path']} for revision "
                    f"{snapshot.revision}"
                )
            if row.get("expression_date") != snapshot.expression_date:
                raise ValueError(
                    f"unexpected expression_date on {row['citation_path']} for "
                    f"revision {snapshot.revision}"
                )
            if row.get("source_url") != snapshot.official_url:
                raise ValueError(
                    f"unexpected source_url on {row['citation_path']} for "
                    f"revision {snapshot.revision}"
                )
            if row.get("metadata", {}).get("download_url") != snapshot.wayback_url:
                raise ValueError(
                    f"unexpected download_url on {row['citation_path']} for "
                    f"revision {snapshot.revision}"
                )

        expected_metadata = {
            "yale_cover_date": snapshot.yale_cover_date,
            "wayback_timestamp": snapshot.wayback_timestamp,
            "wayback_url": snapshot.wayback_url,
            "wayback_body_gzip": snapshot.wayback_body_gzip,
            "yale_mirror_repository": YALE_MIRROR_REPOSITORY,
            "yale_mirror_path": snapshot.yale_mirror_path,
            "yale_gunzip_sha256": snapshot.yale_gunzip_sha256,
            "yale_byte_equal": snapshot.yale_byte_equal,
            "mirror_verification": snapshot.mirror_verification,
        }
        root_metadata = root_row.get("metadata", {})
        for key, expected in expected_metadata.items():
            if key not in root_metadata or root_metadata[key] != expected:
                raise ValueError(
                    f"unexpected source metadata {key} for revision "
                    f"{snapshot.revision}: expected {expected!r}, "
                    f"got {root_metadata.get(key)!r}"
                )

        for citation_path, excerpts in EXPECTED_EXCERPTS.get(snapshot.revision, {}).items():
            row = rows_by_path.get(citation_path)
            if row is None:
                raise ValueError(
                    f"missing anchor row {citation_path} in revision {snapshot.revision}"
                )
            body = str(row.get("body") or "")
            for excerpt in excerpts:
                if excerpt not in body:
                    raise ValueError(
                        f"required excerpt missing from {citation_path} in "
                        f"revision {snapshot.revision}: {excerpt}"
                    )
        for citation_path in EXPECTED_ABSENT.get(snapshot.revision, ()):
            if citation_path in rows_by_path:
                raise ValueError(
                    "regime-absent path unexpectedly present in revision "
                    f"{snapshot.revision}: {citation_path}"
                )

        inventory = json.loads(
            (staging_base / _inventory_path(snapshot)).read_text(encoding="utf-8")
        )["items"]
        if {item["citation_path"] for item in inventory} != set(rows_by_path):
            raise ValueError(f"inventory/provision paths differ for revision {snapshot.revision}")

        coverage = json.loads(
            (staging_base / _coverage_path(snapshot)).read_text(encoding="utf-8")
        )
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
                    f"unexpected coverage field {key} for revision "
                    f"{snapshot.revision}: expected {expected!r}, "
                    f"got {coverage.get(key)!r}"
                )


def reproduce(base: Path, source_dir: Path | None = None) -> dict[str, Any]:
    target_base = base.resolve()
    input_root = (source_dir or RETAINED_BASE).resolve()
    source_bytes = _read_verified_sources(input_root)

    with TemporaryDirectory(prefix="repro-us-hts-2025-part2-") as staging_name:
        staging_base = Path(staging_name) / "corpus"
        scopes = [
            _build_snapshot_scope(staging_base, snapshot, source_bytes[snapshot.revision])
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
        "source_sha256": {
            snapshot.official_filename: snapshot.sha256 for snapshot in SNAPSHOTS
        },
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
            "Optional local input root. Accepts the eleven flat official "
            "filenames or the retained canonical paths; defaults to "
            "repository data/corpus."
        ),
    )
    args = parser.parse_args()
    print(json.dumps(reproduce(args.base, args.source_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
