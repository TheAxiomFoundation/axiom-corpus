#!/usr/bin/env python3
"""Reproduce the remaining USITC HTS 2026 revision snapshot ingest.

Ingests the 2026 Basic Edition and Revisions 1, 2, 5-11, and 13 of the
USITC Harmonized Tariff Schedule JSON. It normalizes chapters 72, 76, and
95 plus every 9903 row, complementing the Revision 3/4/12/14 snapshots in
``us_hts_tariff_snapshots.py`` without re-ingesting those four revisions.

Ten inputs are Internet Archive captures of official USITC static URLs.
Revision 11 has no Wayback capture: its source bytes are the gunzipped Yale
Budget Lab mirror, verified identical across two independent checkouts. Every
retained input is pinned by SHA-256 and byte size and is fully verified in a
temporary staging directory before any destination artifact is written.
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
EDITION = "2026"
CHAPTER_PREFIXES = ("72", "76", "95", "9903")
OFFICIAL_URL_TEMPLATE = (
    "https://www.usitc.gov/sites/default/files/tata/hts/{filename}"
)
WAYBACK_URL_TEMPLATE = "https://web.archive.org/web/{timestamp}id_/{official_url}"
YALE_REPOSITORY = "yale-budget-lab/tariff-rate-tracker"
YALE_MIRROR_DIRECTORY = "data/hts_archives"
YALE_RAW_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/Budget-Lab-Yale/tariff-rate-tracker/"
    "master/data/hts_archives/{filename}"
)
REPRO_COMMAND = (
    "uv run --extra dev python "
    "scripts/repro/us_hts_tariff_snapshots_2026_gapfill.py --base data/corpus"
)


@dataclass(frozen=True)
class RevisionSnapshot:
    """One pinned full-edition USITC HTS JSON snapshot."""

    revision: int | str
    expression_date: str
    yale_cover_date: str | None
    wayback_timestamp: str | None
    wayback_body_gzip: bool
    sha256: str
    size_bytes: int
    total_rows: int
    target_rows: int
    rows_by_chapter: dict[str, int]
    yale_mirror: str | None
    yale_gunzip_sha256: str | None
    yale_byte_equal: bool | None

    @property
    def key(self) -> str:
        return str(self.revision)

    @property
    def is_basic(self) -> bool:
        return self.revision == "basic"

    @property
    def version(self) -> str:
        suffix = "basic" if self.is_basic else f"rev{self.revision}"
        return f"2026-08-01-usitc-hts-{EDITION}-{suffix}"

    @property
    def official_filename(self) -> str:
        if self.is_basic:
            return f"hts_{EDITION}_basic_edition_json.json"
        return f"hts_{EDITION}_revision_{self.revision}_json.json"

    @property
    def official_url(self) -> str:
        return OFFICIAL_URL_TEMPLATE.format(filename=self.official_filename)

    @property
    def wayback_url(self) -> str | None:
        if self.wayback_timestamp is None:
            return None
        return WAYBACK_URL_TEMPLATE.format(
            timestamp=self.wayback_timestamp,
            official_url=self.official_url,
        )

    @property
    def yale_mirror_path(self) -> str | None:
        if self.yale_mirror is None:
            return None
        return f"{YALE_MIRROR_DIRECTORY}/{self.yale_mirror}"

    @property
    def yale_mirror_url(self) -> str | None:
        if self.yale_mirror is None:
            return None
        return YALE_RAW_URL_TEMPLATE.format(filename=self.yale_mirror)

    @property
    def download_url(self) -> str:
        if self.wayback_url is not None:
            return self.wayback_url
        if self.yale_mirror_url is None:
            raise ValueError(f"snapshot {self.key} has no download provenance")
        return self.yale_mirror_url

    @property
    def source_id(self) -> str:
        suffix = "basic" if self.is_basic else f"rev{self.revision}"
        return f"usitc-hts-{EDITION}-{suffix}"

    @property
    def title(self) -> str:
        if self.is_basic:
            return f"Harmonized Tariff Schedule of the United States ({EDITION}) Basic Edition"
        return (
            f"Harmonized Tariff Schedule of the United States ({EDITION}) "
            f"Revision {self.revision}"
        )


SNAPSHOTS = (
    RevisionSnapshot(
        revision="basic",
        expression_date="2025-12-31",
        yale_cover_date="2026-01-01",
        wayback_timestamp="20260624200855",
        wayback_body_gzip=True,
        sha256="a718007c8455c93a88ddc68f15f036cee10e9a820065a4c356da1481f4131858",
        size_bytes=13_642_171,
        total_rows=35_571,
        target_rows=1_772,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 691},
        yale_mirror="hts_2026_basic.json.gz",
        yale_gunzip_sha256=(
            "a718007c8455c93a88ddc68f15f036cee10e9a820065a4c356da1481f4131858"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=1,
        expression_date="2026-01-16",
        yale_cover_date="2026-01-16",
        wayback_timestamp="20260624200855",
        wayback_body_gzip=True,
        sha256="8d258c60f75c09f2f61c8e184aa8f38b5a3f7ba0e0edcfc608282ca51cbc8ef2",
        size_bytes=13_648_615,
        total_rows=35_580,
        target_rows=1_781,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 700},
        yale_mirror="hts_2026_rev_1.json.gz",
        yale_gunzip_sha256=(
            "8d258c60f75c09f2f61c8e184aa8f38b5a3f7ba0e0edcfc608282ca51cbc8ef2"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=2,
        expression_date="2026-01-30",
        yale_cover_date="2026-01-30",
        wayback_timestamp="20260624200856",
        wayback_body_gzip=True,
        sha256="b56567588ca6165772d409d7ad097e7b96327fa7f19d18b6a95f70317ad864a1",
        size_bytes=13_690_141,
        total_rows=35_720,
        target_rows=1_781,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 700},
        yale_mirror="hts_2026_rev_2.json.gz",
        yale_gunzip_sha256=(
            "b56567588ca6165772d409d7ad097e7b96327fa7f19d18b6a95f70317ad864a1"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=5,
        expression_date="2026-04-08",
        yale_cover_date="2026-04-06",
        wayback_timestamp="20260624200856",
        wayback_body_gzip=True,
        sha256="0e6117efc73e98a8b0203205e8e7f09e6a6a9aa2c793f15def3680d447d68448",
        size_bytes=13_471_071,
        total_rows=35_493,
        target_rows=1_568,
        rows_by_chapter={"72": 738, "76": 182, "95": 162, "9903": 486},
        yale_mirror="hts_2026_rev_5.json.gz",
        yale_gunzip_sha256=(
            "0a8789f5a540f69117b74855c348ce2aaa62b6e57efe80ef46b45248053e9c37"
        ),
        yale_byte_equal=False,
    ),
    RevisionSnapshot(
        revision=6,
        expression_date="2026-04-23",
        yale_cover_date="2026-04-23",
        wayback_timestamp="20260624200856",
        wayback_body_gzip=True,
        sha256="8258abee12b65e04a1c5b04519377040c711b8c31653d2b069fbf5e87a00e4d8",
        size_bytes=13_472_235,
        total_rows=35_495,
        target_rows=1_570,
        rows_by_chapter={"72": 738, "76": 182, "95": 162, "9903": 488},
        yale_mirror="hts_2026_rev_6.json.gz",
        yale_gunzip_sha256=(
            "8258abee12b65e04a1c5b04519377040c711b8c31653d2b069fbf5e87a00e4d8"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=7,
        expression_date="2026-04-29",
        yale_cover_date="2026-04-29",
        wayback_timestamp="20260624200856",
        wayback_body_gzip=True,
        sha256="0a8789f5a540f69117b74855c348ce2aaa62b6e57efe80ef46b45248053e9c37",
        size_bytes=13_472_793,
        total_rows=35_496,
        target_rows=1_571,
        rows_by_chapter={"72": 738, "76": 182, "95": 162, "9903": 489},
        yale_mirror="hts_2026_rev_7.json.gz",
        yale_gunzip_sha256=(
            "0a8789f5a540f69117b74855c348ce2aaa62b6e57efe80ef46b45248053e9c37"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=8,
        expression_date="2026-05-22",
        yale_cover_date=None,
        wayback_timestamp="20260624200856",
        wayback_body_gzip=True,
        sha256="04f4ddda584823a954097b65cd8ca3a5aa1982317c344c582aa4cc3d5021433a",
        size_bytes=13_472_793,
        total_rows=35_496,
        target_rows=1_571,
        rows_by_chapter={"72": 738, "76": 182, "95": 162, "9903": 489},
        yale_mirror="hts_2026_rev_8.json.gz",
        yale_gunzip_sha256=(
            "04f4ddda584823a954097b65cd8ca3a5aa1982317c344c582aa4cc3d5021433a"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=9,
        expression_date="2026-05-28",
        yale_cover_date="2026-05-28",
        wayback_timestamp="20260624200856",
        wayback_body_gzip=True,
        sha256="2dc811962b6809736e2e30c8753d0d0bc3fb3f1c65bbb15728663959247957ae",
        size_bytes=13_476_771,
        total_rows=35_502,
        target_rows=1_577,
        rows_by_chapter={"72": 738, "76": 182, "95": 162, "9903": 495},
        yale_mirror="hts_2026_rev_9.json.gz",
        yale_gunzip_sha256=(
            "1135180124deac6707b127c4c54b5e80c583be233bc4a683e0d76a14f7247ef8"
        ),
        yale_byte_equal=False,
    ),
    RevisionSnapshot(
        revision=10,
        expression_date="2026-06-08",
        yale_cover_date="2026-06-08",
        wayback_timestamp="20260624200856",
        wayback_body_gzip=True,
        sha256="66375d1cc8e56cae00bbf8327c400e62586eefe128cad7c8e4d936dc3d4eda2f",
        size_bytes=13_481_362,
        total_rows=35_509,
        target_rows=1_584,
        rows_by_chapter={"72": 738, "76": 182, "95": 162, "9903": 502},
        yale_mirror="hts_2026_rev_10.json.gz",
        yale_gunzip_sha256=(
            "66375d1cc8e56cae00bbf8327c400e62586eefe128cad7c8e4d936dc3d4eda2f"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=11,
        expression_date="2026-07-01",
        yale_cover_date="2026-07-01",
        wayback_timestamp=None,
        wayback_body_gzip=False,
        sha256="16cc1f30b40430019a52463416baa3cd682f15228b955be5bc44e7dd39e51e30",
        size_bytes=13_572_076,
        total_rows=35_668,
        target_rows=1_586,
        rows_by_chapter={"72": 740, "76": 182, "95": 162, "9903": 502},
        yale_mirror="hts_2026_rev_11.json.gz",
        yale_gunzip_sha256=(
            "16cc1f30b40430019a52463416baa3cd682f15228b955be5bc44e7dd39e51e30"
        ),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=13,
        expression_date="2026-07-28",
        yale_cover_date=None,
        wayback_timestamp="20260801211320",
        wayback_body_gzip=True,
        sha256="3b4057c56e3bfaa48285b5371f771007840ea007c5094772f04c4754b6e3c6a5",
        size_bytes=12_623_527,
        total_rows=35_779,
        target_rows=1_696,
        rows_by_chapter={"72": 740, "76": 182, "95": 162, "9903": 612},
        yale_mirror=None,
        yale_gunzip_sha256=None,
        yale_byte_equal=None,
    ),
)

SPECIAL_MIRROR_VERIFICATION = {
    "5": (
        "capture-authoritative: the Wayback capture is the pristine Revision 5 "
        "static file; Yale Budget Lab mirror "
        "yale-budget-lab/tariff-rate-tracker data/hts_archives/"
        "hts_2026_rev_5.json.gz reflects later in-place edits (3 row-level "
        "differences and 3 mirror-only heading rows)"
    ),
    "9": (
        "content-identical to Yale Budget Lab mirror "
        "yale-budget-lab/tariff-rate-tracker data/hts_archives/"
        "hts_2026_rev_9.json.gz after dropping the static file's extra leading "
        "0101 heading row and stripping HTML presentation tags"
    ),
    "11": (
        "single-source Yale Budget Lab mirror gunzip from "
        "yale-budget-lab/tariff-rate-tracker data/hts_archives/"
        "hts_2026_rev_11.json.gz; no Wayback capture exists; CDX returned 503 "
        "during reconnaissance and three Save Page Now attempts returned 520 "
        "on 2026-08-01; gunzip bytes were identical across two independent "
        "checkouts"
    ),
    "13": (
        "single-source Wayback capture of the official USITC static URL; "
        "no Yale Budget Lab mirror exists"
    ),
}


def _mirror_verification(snapshot: RevisionSnapshot) -> str:
    special = SPECIAL_MIRROR_VERIFICATION.get(snapshot.key)
    if special is not None:
        return special
    if not snapshot.yale_byte_equal or snapshot.yale_mirror_path is None:
        raise ValueError(f"missing mirror-verification rule for snapshot {snapshot.key}")
    return (
        "byte-identical to Yale Budget Lab mirror "
        f"{YALE_REPOSITORY} {snapshot.yale_mirror_path} after gunzip "
        f"(same SHA-256 {snapshot.sha256})"
    )


def _download_provenance(snapshot: RevisionSnapshot) -> dict[str, Any]:
    if snapshot.wayback_url is not None:
        return {
            "kind": "wayback_capture",
            "url": snapshot.wayback_url,
            "wayback_timestamp": snapshot.wayback_timestamp,
            "wayback_body_gzip": snapshot.wayback_body_gzip,
        }
    return {
        "kind": "yale_mirror_gunzip",
        "repository": YALE_REPOSITORY,
        "path": snapshot.yale_mirror_path,
        "url": snapshot.yale_mirror_url,
        "gunzip_sha256": snapshot.yale_gunzip_sha256,
    }


# Regime anchors are literal excerpts observed in the normalized bodies built
# from the pinned inputs. Absence anchors verify both the pre-section-122 and
# pre-forced-labor-301 boundaries represented in this slice.
EXPECTED_EXCERPTS: dict[str, dict[str, tuple[str, ...]]] = {
    "basic": {
        f"{CITATION_ROOT}/7202.11.10.00": ("Rates of duty (1-General): 1.4%",),
        f"{CITATION_ROOT}/9903.01.25": (
            "The duty provided in the applicable subheading + 10%",
        ),
    },
    "5": {
        f"{CITATION_ROOT}/9903.03.01": (
            "subdivision (aa) of U.S. note 2 to this subchapter",
            "The duty provided in the applicable subheading + 10%",
        ),
    },
    "13": {
        f"{CITATION_ROOT}/9903.05.20": (
            "articles the product of Algeria",
            "The duty provided in the applicable subheading + 12.5%",
        ),
    },
}
EXPECTED_ABSENT: dict[str, tuple[str, ...]] = {
    "basic": (f"{CITATION_ROOT}/9903.03.01",),
    "2": (f"{CITATION_ROOT}/9903.03.01",),
    "11": (
        f"{CITATION_ROOT}/9903.05.20",
        f"{CITATION_ROOT}/9903.06.01",
    ),
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
                f"official source hash mismatch for snapshot {snapshot.key}: "
                f"expected {snapshot.sha256}, got {actual_hash}"
            )
        if len(content) != snapshot.size_bytes:
            raise ValueError(
                f"official source size mismatch for snapshot {snapshot.key}: "
                f"expected {snapshot.size_bytes}, got {len(content)}"
            )
        if snapshot.yale_byte_equal and snapshot.yale_gunzip_sha256 != actual_hash:
            raise ValueError(
                f"Yale gunzip hash mismatch for snapshot {snapshot.key}: "
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


def _snapshot_metadata(snapshot: RevisionSnapshot) -> dict[str, Any]:
    return {
        "edition": EDITION,
        "revision": snapshot.revision,
        "revision_effective_date": snapshot.expression_date,
        "yale_cover_date": snapshot.yale_cover_date,
        "download_provenance": _download_provenance(snapshot),
        "wayback_timestamp": snapshot.wayback_timestamp,
        "wayback_url": snapshot.wayback_url,
        "wayback_body_gzip": snapshot.wayback_body_gzip,
        "yale_mirror_repository": YALE_REPOSITORY if snapshot.yale_mirror else None,
        "yale_mirror_path": snapshot.yale_mirror_path,
        "yale_mirror_url": snapshot.yale_mirror_url,
        "yale_gunzip_sha256": snapshot.yale_gunzip_sha256,
        "yale_byte_equal": snapshot.yale_byte_equal,
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
                    f"unexpected download_url on {row['citation_path']} for "
                    f"snapshot {snapshot.key}"
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
                raise ValueError(
                    f"missing anchor row {citation_path} in snapshot {snapshot.key}"
                )
            body = str(row.get("body") or "")
            for excerpt in excerpts:
                if excerpt not in body:
                    raise ValueError(
                        f"required excerpt missing from {citation_path} in "
                        f"snapshot {snapshot.key}: {excerpt}"
                    )
        for citation_path in EXPECTED_ABSENT.get(snapshot.key, ()):
            if citation_path in rows_by_path:
                raise ValueError(
                    f"regime-absent path unexpectedly present in snapshot "
                    f"{snapshot.key}: {citation_path}"
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

    with TemporaryDirectory(prefix="repro-us-hts-2026-gapfill-") as staging_name:
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
