#!/usr/bin/env python3
"""Reproduce the first tranche of USITC HTS 2025 revision snapshots.

Ingests the 2025 Basic Edition and Revisions 1 through 10 of the full USITC
Harmonized Tariff Schedule JSON snapshots. It normalizes the tariff rows for
chapters 72, 76, and 95 plus every subchapter III/IV Chapter 99 heading in the
9903 family.

Every snapshot is a Wayback Machine capture of its official USITC static URL.
The retained capture bytes were independently verified as byte-identical,
after gunzip, to the corresponding Yale Budget Lab tariff-rate-tracker mirror
and are pinned here by SHA-256.
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
OFFICIAL_URL_ROOT = "https://www.usitc.gov/sites/default/files/tata/hts"
WAYBACK_URL_TEMPLATE = "https://web.archive.org/web/{timestamp}id_/{official_url}"
YALE_MIRROR_REPOSITORY = "yale-budget-lab/tariff-rate-tracker"
YALE_MIRROR_DIRECTORY = "data/hts_archives"
REPRO_COMMAND = (
    "uv run --extra dev python scripts/repro/"
    "us_hts_tariff_snapshots_2025_part1.py --base data/corpus"
)


@dataclass(frozen=True)
class RevisionSnapshot:
    """One pinned full-edition USITC HTS JSON snapshot."""

    revision: str | int
    expression_date: str
    yale_cover_date: str | None
    wayback_timestamp: str
    wayback_body_gzip: bool
    yale_mirror_filename: str
    yale_gunzip_sha256: str
    yale_byte_equal: bool
    sha256: str
    size_bytes: int
    total_rows: int
    target_rows: int
    rows_by_chapter: dict[str, int]

    @property
    def key(self) -> str:
        return str(self.revision)

    @property
    def is_basic(self) -> bool:
        return self.revision == "basic"

    @property
    def label(self) -> str:
        return "basic edition" if self.is_basic else f"revision {self.revision}"

    @property
    def version(self) -> str:
        suffix = "basic" if self.is_basic else f"rev{self.revision}"
        return f"2026-08-01-usitc-hts-2025-{suffix}"

    @property
    def official_filename(self) -> str:
        if self.is_basic:
            return "hts_2025_basic_edition_json.json"
        return f"hts_2025_revision_{self.revision}_json.json"

    @property
    def official_url(self) -> str:
        return f"{OFFICIAL_URL_ROOT}/{self.official_filename}"

    @property
    def wayback_url(self) -> str:
        return WAYBACK_URL_TEMPLATE.format(
            timestamp=self.wayback_timestamp,
            official_url=self.official_url,
        )

    @property
    def source_id(self) -> str:
        suffix = "basic" if self.is_basic else f"rev{self.revision}"
        return f"usitc-hts-2025-{suffix}"

    @property
    def title(self) -> str:
        if self.is_basic:
            return "Harmonized Tariff Schedule of the United States (2025) Basic Edition"
        return (
            "Harmonized Tariff Schedule of the United States "
            f"(2025) Revision {self.revision}"
        )

    @property
    def yale_mirror_path(self) -> str:
        return f"{YALE_MIRROR_DIRECTORY}/{self.yale_mirror_filename}"

    @property
    def mirror_verification(self) -> str:
        if not self.yale_byte_equal:
            raise ValueError(f"no byte-equal Yale verification for {self.label}")
        return (
            "byte-identical to Yale Budget Lab mirror "
            f"{YALE_MIRROR_REPOSITORY}/{self.yale_mirror_path} after gunzip"
        )


SNAPSHOTS = (
    RevisionSnapshot(
        revision="basic",
        expression_date="2024-12-31",
        yale_cover_date="2025-01-01",
        wayback_timestamp="20260121200457",
        wayback_body_gzip=True,
        yale_mirror_filename="hts_2025_basic.json.gz",
        yale_gunzip_sha256=(
            "fe9de40662e7ab4d263f3dfb2d9090f8f78892bf881ce521628bbb5440829d01"
        ),
        yale_byte_equal=True,
        sha256="fe9de40662e7ab4d263f3dfb2d9090f8f78892bf881ce521628bbb5440829d01",
        size_bytes=13_637_579,
        total_rows=35_859,
        target_rows=1_526,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 447},
    ),
    RevisionSnapshot(
        revision=1,
        expression_date="2025-02-05",
        yale_cover_date="2025-01-27",
        wayback_timestamp="20260121200305",
        wayback_body_gzip=True,
        yale_mirror_filename="hts_2025_rev_1.json.gz",
        yale_gunzip_sha256=(
            "c1fcdf003066f6e0471ae82068cee3289ff26bc74c75ee00c75fcf1ba06c159f"
        ),
        yale_byte_equal=True,
        sha256="c1fcdf003066f6e0471ae82068cee3289ff26bc74c75ee00c75fcf1ba06c159f",
        size_bytes=13_641_117,
        total_rows=35_865,
        target_rows=1_530,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 451},
    ),
    RevisionSnapshot(
        revision=2,
        expression_date="2025-02-12",
        yale_cover_date="2025-02-01",
        wayback_timestamp="20251209180513",
        wayback_body_gzip=True,
        yale_mirror_filename="hts_2025_rev_2.json.gz",
        yale_gunzip_sha256=(
            "a25ac13d6442f3c4bf075440cb26f4cfdeaa6be655e9e923a2ac7a01064a12fc"
        ),
        yale_byte_equal=True,
        sha256="a25ac13d6442f3c4bf075440cb26f4cfdeaa6be655e9e923a2ac7a01064a12fc",
        size_bytes=13_641_211,
        total_rows=35_865,
        target_rows=1_530,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 451},
    ),
    RevisionSnapshot(
        revision=3,
        expression_date="2025-03-06",
        yale_cover_date="2025-02-04",
        wayback_timestamp="20260121200009",
        wayback_body_gzip=True,
        yale_mirror_filename="hts_2025_rev_3.json.gz",
        yale_gunzip_sha256=(
            "6177777ed76cf40b2c00b2835f74e8f9486ecae4851e50ca98128848c959c108"
        ),
        yale_byte_equal=True,
        sha256="6177777ed76cf40b2c00b2835f74e8f9486ecae4851e50ca98128848c959c108",
        size_bytes=13_647_949,
        total_rows=35_874,
        target_rows=1_538,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 459},
    ),
    RevisionSnapshot(
        revision=4,
        expression_date="2025-03-11",
        yale_cover_date="2025-03-04",
        wayback_timestamp="20260121195833",
        wayback_body_gzip=True,
        yale_mirror_filename="hts_2025_rev_4.json.gz",
        yale_gunzip_sha256=(
            "e164aeccdc9cb948b6f351f3d05997024e45b26a834ad53d72ec8bf880c3a772"
        ),
        yale_byte_equal=True,
        sha256="e164aeccdc9cb948b6f351f3d05997024e45b26a834ad53d72ec8bf880c3a772",
        size_bytes=13_713_162,
        total_rows=35_890,
        target_rows=1_554,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 475},
    ),
    RevisionSnapshot(
        revision=5,
        expression_date="2025-03-14",
        yale_cover_date="2025-03-05",
        wayback_timestamp="20260121195705",
        wayback_body_gzip=True,
        yale_mirror_filename="hts_2025_rev_5.json.gz",
        yale_gunzip_sha256=(
            "ca15d92fddaeb48e32547f983c8376ac7e40d238e275964f73eca73d0a67bf05"
        ),
        yale_byte_equal=True,
        sha256="ca15d92fddaeb48e32547f983c8376ac7e40d238e275964f73eca73d0a67bf05",
        size_bytes=13_677_804,
        total_rows=35_890,
        target_rows=1_554,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 475},
    ),
    RevisionSnapshot(
        revision=6,
        expression_date="2025-04-03",
        yale_cover_date="2025-03-12",
        wayback_timestamp="20260121195550",
        wayback_body_gzip=True,
        yale_mirror_filename="hts_2025_rev_6.json.gz",
        yale_gunzip_sha256=(
            "1d078537a8ab86bc22ce9221e838511b5246151a66a04d23e95d9b4149fd485e"
        ),
        yale_byte_equal=True,
        sha256="1d078537a8ab86bc22ce9221e838511b5246151a66a04d23e95d9b4149fd485e",
        size_bytes=13_724_411,
        total_rows=35_894,
        target_rows=1_558,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 479},
    ),
    RevisionSnapshot(
        revision=7,
        expression_date="2025-04-04",
        yale_cover_date="2025-04-02",
        wayback_timestamp="20260121195434",
        wayback_body_gzip=True,
        yale_mirror_filename="hts_2025_rev_7.json.gz",
        yale_gunzip_sha256=(
            "99caf1e37916595d19f385ba02cefc205964216e253adb73c30756877a2ced13"
        ),
        yale_byte_equal=True,
        sha256="99caf1e37916595d19f385ba02cefc205964216e253adb73c30756877a2ced13",
        size_bytes=13_714_757,
        total_rows=35_938,
        target_rows=1_602,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 523},
    ),
    RevisionSnapshot(
        revision=8,
        expression_date="2025-04-09",
        yale_cover_date="2025-04-03",
        wayback_timestamp="20260121195316",
        wayback_body_gzip=True,
        yale_mirror_filename="hts_2025_rev_8.json.gz",
        yale_gunzip_sha256=(
            "84d998126e8bb0aafe9f287a511fd25742474874720033db342ca9cf083ab41b"
        ),
        yale_byte_equal=True,
        sha256="84d998126e8bb0aafe9f287a511fd25742474874720033db342ca9cf083ab41b",
        size_bytes=13_714_757,
        total_rows=35_938,
        target_rows=1_602,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 523},
    ),
    RevisionSnapshot(
        revision=9,
        expression_date="2025-04-11",
        yale_cover_date="2025-04-05",
        wayback_timestamp="20260121195155",
        wayback_body_gzip=True,
        yale_mirror_filename="hts_2025_rev_9.json.gz",
        yale_gunzip_sha256=(
            "a36d2079ac19f9d5a051aee175d379fa2eb57353ee56c8cf158ec9b9a77a644e"
        ),
        yale_byte_equal=True,
        sha256="a36d2079ac19f9d5a051aee175d379fa2eb57353ee56c8cf158ec9b9a77a644e",
        size_bytes=13_722_426,
        total_rows=35_938,
        target_rows=1_602,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 523},
    ),
    RevisionSnapshot(
        revision=10,
        expression_date="2025-04-15",
        yale_cover_date="2025-04-09",
        wayback_timestamp="20260121195021",
        wayback_body_gzip=True,
        yale_mirror_filename="hts_2025_rev_10.json.gz",
        yale_gunzip_sha256=(
            "90d50a0433456141452826469638303a3e928601e20e6f1554172b53f60bfadc"
        ),
        yale_byte_equal=True,
        sha256="90d50a0433456141452826469638303a3e928601e20e6f1554172b53f60bfadc",
        size_bytes=13_766_161,
        total_rows=35_938,
        target_rows=1_602,
        rows_by_chapter={"72": 738, "76": 179, "95": 162, "9903": 523},
    ),
)

# Regime anchors derived from the retained source rows. The stable Chapter 72
# rate is checked in every snapshot. The 9903.01.25 reciprocal-tariff heading
# first appears in Revision 7; the section 122 heading is absent throughout.
EXPECTED_EXCERPTS: dict[str, dict[str, tuple[str, ...]]] = {
    "basic": {
        f"{CITATION_ROOT}/7202.11.10.00": ("Rates of duty (1-General): 1.4%",),
    },
    **{
        str(revision): {
            f"{CITATION_ROOT}/7202.11.10.00": (
                "Rates of duty (1-General): 1.4%",
            ),
        }
        for revision in range(1, 7)
    },
    **{
        str(revision): {
            f"{CITATION_ROOT}/7202.11.10.00": (
                "Rates of duty (1-General): 1.4%",
            ),
            f"{CITATION_ROOT}/9903.01.25": (
                "The duty provided in the applicable subheading + 10%",
            ),
        }
        for revision in range(7, 11)
    },
}
EXPECTED_ABSENT: dict[str, tuple[str, ...]] = {
    "basic": (
        f"{CITATION_ROOT}/9903.01.25",
        f"{CITATION_ROOT}/9903.03.01",
    ),
    **{
        str(revision): (
            f"{CITATION_ROOT}/9903.01.25",
            f"{CITATION_ROOT}/9903.03.01",
        )
        for revision in range(1, 7)
    },
    **{
        str(revision): (f"{CITATION_ROOT}/9903.03.01",)
        for revision in range(7, 11)
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
                f"official source hash mismatch for {snapshot.label}: "
                f"expected {snapshot.sha256}, got {actual_hash}"
            )
        if len(content) != snapshot.size_bytes:
            raise ValueError(
                f"official source size mismatch for {snapshot.label}: "
                f"expected {snapshot.size_bytes}, got {len(content)}"
            )
        if snapshot.yale_byte_equal and snapshot.yale_gunzip_sha256 != actual_hash:
            raise ValueError(
                f"Yale gunzip hash mismatch for {snapshot.label}: "
                f"expected {actual_hash}, got {snapshot.yale_gunzip_sha256}"
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
        raise ValueError(f"{snapshot.label} snapshot is not a JSON list")
    if len(rows) != snapshot.total_rows:
        raise ValueError(
            f"unexpected total row count for {snapshot.label}: "
            f"expected {snapshot.total_rows}, got {len(rows)}"
        )
    blocks = _target_blocks(rows)
    if len(blocks) != snapshot.target_rows:
        raise ValueError(
            f"unexpected target row count for {snapshot.label}: "
            f"expected {snapshot.target_rows}, got {len(blocks)}"
        )
    actual_by_chapter = Counter(_chapter_key(str(block.metadata["htsno"])) for block in blocks)
    if dict(actual_by_chapter) != snapshot.rows_by_chapter:
        raise ValueError(
            f"unexpected chapter breakdown for {snapshot.label}: "
            f"expected {snapshot.rows_by_chapter}, got {dict(actual_by_chapter)}"
        )
    htsnos = [str(block.metadata["htsno"]) for block in blocks]
    if len(set(htsnos)) != len(htsnos):
        duplicates = [item for item, count in Counter(htsnos).items() if count > 1]
        raise ValueError(f"duplicate HTS numbers in {snapshot.label}: {duplicates}")

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
        raise ValueError(f"incomplete coverage for {snapshot.label}: {coverage.to_mapping()}")
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
            raise ValueError(f"generated source is not byte-equal for {snapshot.label}")

        rows = _load_jsonl(staging_base / _provisions_path(snapshot))
        rows_by_path = {row["citation_path"]: row for row in rows}
        if len(rows) != len(rows_by_path):
            raise ValueError(f"duplicate citation paths in {snapshot.label}")
        if len(rows) != snapshot.target_rows + 1:
            raise ValueError(
                f"unexpected provision count for {snapshot.label}: "
                f"expected {snapshot.target_rows + 1}, got {len(rows)}"
            )
        root_row = rows_by_path.get(CITATION_ROOT)
        if root_row is None or root_row.get("kind") != "document":
            raise ValueError(f"missing document root row for {snapshot.label}")

        expected_metadata = {
            "download_url": snapshot.wayback_url,
            "wayback_timestamp": snapshot.wayback_timestamp,
            "wayback_url": snapshot.wayback_url,
            "wayback_body_gzip": snapshot.wayback_body_gzip,
            "yale_cover_date": snapshot.yale_cover_date,
            "yale_mirror_repository": YALE_MIRROR_REPOSITORY,
            "yale_mirror_path": snapshot.yale_mirror_path,
            "yale_gunzip_sha256": snapshot.yale_gunzip_sha256,
            "yale_byte_equal": snapshot.yale_byte_equal,
            "mirror_verification": snapshot.mirror_verification,
        }
        for row in rows:
            if row.get("version") != snapshot.version:
                raise ValueError(
                    f"unexpected version on {row['citation_path']} for {snapshot.label}"
                )
            if row.get("expression_date") != snapshot.expression_date:
                raise ValueError(
                    f"unexpected expression_date on {row['citation_path']} for "
                    f"{snapshot.label}"
                )
            if row.get("source_url") != snapshot.official_url:
                raise ValueError(
                    f"unexpected source_url on {row['citation_path']} for {snapshot.label}"
                )
            metadata = row.get("metadata", {})
            for key, expected in expected_metadata.items():
                if metadata.get(key) != expected:
                    raise ValueError(
                        f"unexpected metadata {key} on {row['citation_path']} for "
                        f"{snapshot.label}: expected {expected!r}, got {metadata.get(key)!r}"
                    )

        for citation_path, excerpts in EXPECTED_EXCERPTS.get(snapshot.key, {}).items():
            row = rows_by_path.get(citation_path)
            if row is None:
                raise ValueError(f"missing anchor row {citation_path} in {snapshot.label}")
            body = str(row.get("body") or "")
            for excerpt in excerpts:
                if excerpt not in body:
                    raise ValueError(
                        f"required excerpt missing from {citation_path} in "
                        f"{snapshot.label}: {excerpt}"
                    )
        for citation_path in EXPECTED_ABSENT.get(snapshot.key, ()):
            if citation_path in rows_by_path:
                raise ValueError(
                    f"regime-absent path unexpectedly present in {snapshot.label}: "
                    f"{citation_path}"
                )

        inventory = json.loads(
            (staging_base / _inventory_path(snapshot)).read_text(encoding="utf-8")
        )["items"]
        if {item["citation_path"] for item in inventory} != set(rows_by_path):
            raise ValueError(f"inventory/provision paths differ for {snapshot.label}")

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
                    f"unexpected coverage field {key} for {snapshot.label}: "
                    f"expected {expected!r}, got {coverage.get(key)!r}"
                )


def reproduce(base: Path, source_dir: Path | None = None) -> dict[str, Any]:
    target_base = base.resolve()
    input_root = (source_dir or RETAINED_BASE).resolve()
    source_bytes = _read_verified_sources(input_root)

    with TemporaryDirectory(prefix="repro-us-hts-2025-part1-") as staging_name:
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
            "filenames or retained canonical paths; defaults to repository "
            "data/corpus."
        ),
    )
    args = parser.parse_args()
    print(json.dumps(reproduce(args.base, args.source_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
