#!/usr/bin/env python3
"""Reproduce USITC HTS 2025 Revision 22-32 snapshot ingestion.

Ingests eleven full-revision USITC Harmonized Tariff Schedule JSON snapshots
(Revisions 22 through 32 of the 2025 edition) and normalizes the tariff rows
for chapters 72, 76, and 95 plus every subchapter III/IV Chapter 99 heading
in the 9903 family.

Every retained source is an Internet Archive Wayback Machine capture of its
official USITC static URL. Each capture was independently verified as
byte-identical, after gunzip, to the corresponding Yale Budget Lab mirror and
is pinned here by SHA-256 and byte size.
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
    "https://www.usitc.gov/sites/default/files/tata/hts/hts_2025_revision_{revision}_json.json"
)
WAYBACK_URL_TEMPLATE = "https://web.archive.org/web/{timestamp}id_/{official_url}"
YALE_MIRROR_REPOSITORY = "yale-budget-lab/tariff-rate-tracker"
YALE_MIRROR_PATH_TEMPLATE = "data/hts_archives/hts_2025_rev_{revision}.json.gz"
REPRO_COMMAND = (
    "uv run --extra dev python "
    "scripts/repro/us_hts_tariff_snapshots_2025_part3.py --base data/corpus "
    "--source-dir ~/.axiom/workspace/laneA-hts-downloads"
)


@dataclass(frozen=True)
class RevisionSnapshot:
    """One pinned full-revision USITC HTS JSON snapshot."""

    revision: int
    expression_date: str
    yale_cover_date: str | None
    wayback_timestamp: str
    wayback_body_gzip: bool
    sha256: str
    size_bytes: int
    total_rows: int
    target_rows: int
    rows_by_chapter: dict[str, int]
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
    def source_id(self) -> str:
        return f"usitc-hts-2025-rev{self.revision}"

    @property
    def title(self) -> str:
        return f"Harmonized Tariff Schedule of the United States (2025) Revision {self.revision}"

    @property
    def yale_mirror_path(self) -> str:
        return YALE_MIRROR_PATH_TEMPLATE.format(revision=self.revision)

    @property
    def mirror_verification(self) -> str:
        return (
            "byte-identical to Yale Budget Lab mirror "
            f"{YALE_MIRROR_REPOSITORY}:{self.yale_mirror_path} after gunzip "
            f"(SHA-256 {self.yale_gunzip_sha256})"
        )


SNAPSHOTS = (
    RevisionSnapshot(
        revision=22,
        expression_date="2025-09-09",
        yale_cover_date="2025-09-03",
        wayback_timestamp="20260121193240",
        wayback_body_gzip=True,
        sha256="dd2ecdfc045eedfcd7080bf9ddbd3741c08ccee412e0c109f5edccbd772a13dc",
        size_bytes=13_841_826,
        total_rows=36_093,
        target_rows=1_706,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 625},
        yale_gunzip_sha256=("dd2ecdfc045eedfcd7080bf9ddbd3741c08ccee412e0c109f5edccbd772a13dc"),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=23,
        expression_date="2025-09-16",
        yale_cover_date="2025-09-12",
        wayback_timestamp="20260121193114",
        wayback_body_gzip=True,
        sha256="2520132cb2eeb5efd3ecbafab739f04be1875482991d1128098ec0bd047e2e07",
        size_bytes=13_848_103,
        total_rows=36_100,
        target_rows=1_713,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 632},
        yale_gunzip_sha256=("2520132cb2eeb5efd3ecbafab739f04be1875482991d1128098ec0bd047e2e07"),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=24,
        expression_date="2025-09-26",
        yale_cover_date="2025-09-19",
        wayback_timestamp="20260121192933",
        wayback_body_gzip=True,
        sha256="284be76a38366f798012b99e351d226213d77098c2dd97349e3f1a16951f2034",
        size_bytes=13_854_239,
        total_rows=36_108,
        target_rows=1_721,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 640},
        yale_gunzip_sha256=("284be76a38366f798012b99e351d226213d77098c2dd97349e3f1a16951f2034"),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=25,
        expression_date="2025-10-10",
        yale_cover_date="2025-09-26",
        wayback_timestamp="20260801211219",
        wayback_body_gzip=True,
        sha256="c86beb392418c2db581fae8bb1b6243db90c3c25e2bfda01214b8aef8fbd10f8",
        size_bytes=13_860_274,
        total_rows=36_115,
        target_rows=1_728,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 647},
        yale_gunzip_sha256=("c86beb392418c2db581fae8bb1b6243db90c3c25e2bfda01214b8aef8fbd10f8"),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=26,
        expression_date="2025-10-31",
        yale_cover_date="2025-10-06",
        wayback_timestamp="20260121192501",
        wayback_body_gzip=True,
        sha256="b0721d6da3ba653e30ea11832c0ea8ddb34d7f3a92e32a4004f3d574ad45a6fe",
        size_bytes=13_871_177,
        total_rows=36_131,
        target_rows=1_744,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 663},
        yale_gunzip_sha256=("b0721d6da3ba653e30ea11832c0ea8ddb34d7f3a92e32a4004f3d574ad45a6fe"),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=27,
        expression_date="2025-11-07",
        yale_cover_date="2025-10-15",
        wayback_timestamp="20260121192344",
        wayback_body_gzip=True,
        sha256="29b8eba1b5a1bfeeb421e2b99cf880f6c0748abf6265986ac299c524579488c9",
        size_bytes=13_876_393,
        total_rows=36_136,
        target_rows=1_749,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 668},
        yale_gunzip_sha256=("29b8eba1b5a1bfeeb421e2b99cf880f6c0748abf6265986ac299c524579488c9"),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=28,
        expression_date="2025-11-10",
        yale_cover_date="2025-10-22",
        wayback_timestamp="20251114030416",
        wayback_body_gzip=False,
        sha256="98973df36de2f2cc02cef868a2e9fc943eff08f0177dbbe3e2a3b3d02f5d1872",
        size_bytes=13_876_398,
        total_rows=36_136,
        target_rows=1_749,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 668},
        yale_gunzip_sha256=("98973df36de2f2cc02cef868a2e9fc943eff08f0177dbbe3e2a3b3d02f5d1872"),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=29,
        expression_date="2025-11-17",
        yale_cover_date="2025-10-31",
        wayback_timestamp="20260121191948",
        wayback_body_gzip=True,
        sha256="3e02879465307fe177c8f1e5e6f94f1e9c4a4b7e7a1b47dfa43019f132a70749",
        size_bytes=13_878_134,
        total_rows=36_137,
        target_rows=1_750,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 669},
        yale_gunzip_sha256=("3e02879465307fe177c8f1e5e6f94f1e9c4a4b7e7a1b47dfa43019f132a70749"),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=30,
        expression_date="2025-11-21",
        yale_cover_date="2025-11-05",
        wayback_timestamp="20260121191745",
        wayback_body_gzip=True,
        sha256="5a72090f3e975c04af388bb9e27601738308393db595aa5ce731d042be5224f7",
        size_bytes=13_878_803,
        total_rows=36_138,
        target_rows=1_751,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 670},
        yale_gunzip_sha256=("5a72090f3e975c04af388bb9e27601738308393db595aa5ce731d042be5224f7"),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=31,
        expression_date="2025-11-28",
        yale_cover_date="2025-11-12",
        wayback_timestamp="20260123082012",
        wayback_body_gzip=True,
        sha256="c3d74cae8cb2a5993963ac6699d65444722544f6e2043aedcc2199f52b6b5d12",
        size_bytes=13_878_801,
        total_rows=36_138,
        target_rows=1_751,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 670},
        yale_gunzip_sha256=("c3d74cae8cb2a5993963ac6699d65444722544f6e2043aedcc2199f52b6b5d12"),
        yale_byte_equal=True,
    ),
    RevisionSnapshot(
        revision=32,
        expression_date="2025-12-05",
        yale_cover_date="2025-11-15",
        wayback_timestamp="20260203103455",
        wayback_body_gzip=True,
        sha256="aa2056b68dc18a815fb8f467453dbdf457d73f2b495d3cb2499b3028527743d3",
        size_bytes=13_887_062,
        total_rows=36_148,
        target_rows=1_761,
        rows_by_chapter={"72": 738, "76": 181, "95": 162, "9903": 680},
        yale_gunzip_sha256=("aa2056b68dc18a815fb8f467453dbdf457d73f2b495d3cb2499b3028527743d3"),
        yale_byte_equal=True,
    ),
)

# These excerpts were read from the normalized bodies generated from every
# pinned snapshot. They assert both a stable Chapter 72 line and the continuing
# IEEPA reciprocal-tariff heading throughout this slice.
EXPECTED_EXCERPTS: dict[int, dict[str, tuple[str, ...]]] = {
    snapshot.revision: {
        f"{CITATION_ROOT}/7202.11.10.00": (
            "Containing by weight more than 2 percent but not more than 4 percent of carbon",
            "Rates of duty (1-General): 1.4%",
        ),
        f"{CITATION_ROOT}/9903.01.25": (
            "Rates of duty (1-General): The duty provided in the applicable subheading + 10%",
        ),
    }
    for snapshot in SNAPSHOTS
}

# Section 122 heading 9903.03.01 did not exist in any 2025 snapshot.
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
                f"Yale gunzip hash differs from the retained hash for revision {snapshot.revision}"
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


def _snapshot_metadata(snapshot: RevisionSnapshot) -> dict[str, Any]:
    return {
        "edition": "2025",
        "revision": snapshot.revision,
        "revision_effective_date": snapshot.expression_date,
        "yale_cover_date": snapshot.yale_cover_date,
        "wayback_timestamp": snapshot.wayback_timestamp,
        "wayback_url": snapshot.wayback_url,
        "wayback_body_gzip": snapshot.wayback_body_gzip,
        "mirror_verification": snapshot.mirror_verification,
        "yale_mirror_repository": YALE_MIRROR_REPOSITORY,
        "yale_mirror_path": snapshot.yale_mirror_path,
        "yale_gunzip_sha256": snapshot.yale_gunzip_sha256,
        "yale_byte_equal": snapshot.yale_byte_equal,
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

        expected_metadata = _snapshot_metadata(snapshot)
        for row in rows:
            citation_path = row["citation_path"]
            if row.get("version") != snapshot.version:
                raise ValueError(
                    f"unexpected version on {citation_path} for revision {snapshot.revision}"
                )
            if row.get("expression_date") != snapshot.expression_date:
                raise ValueError(
                    f"unexpected expression_date on {citation_path} for revision "
                    f"{snapshot.revision}"
                )
            if row.get("source_url") != snapshot.official_url:
                raise ValueError(
                    f"unexpected source_url on {citation_path} for revision {snapshot.revision}"
                )
            metadata = row.get("metadata", {})
            if metadata.get("download_url") != snapshot.wayback_url:
                raise ValueError(
                    f"unexpected download_url on {citation_path} for revision {snapshot.revision}"
                )
            for key, expected in expected_metadata.items():
                if metadata.get(key) != expected:
                    raise ValueError(
                        f"unexpected metadata field {key} on {citation_path} for "
                        f"revision {snapshot.revision}: expected {expected!r}, "
                        f"got {metadata.get(key)!r}"
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
                        f"required excerpt missing from {citation_path} in revision "
                        f"{snapshot.revision}: {excerpt}"
                    )
        for citation_path in EXPECTED_ABSENT.get(snapshot.revision, ()):
            if citation_path in rows_by_path:
                raise ValueError(
                    f"regime-absent path unexpectedly present in revision "
                    f"{snapshot.revision}: {citation_path}"
                )

        inventory = json.loads(
            (staging_base / _inventory_path(snapshot)).read_text(encoding="utf-8")
        )["items"]
        if {item["citation_path"] for item in inventory} != set(rows_by_path):
            raise ValueError(f"inventory/provision paths differ for revision {snapshot.revision}")

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
                    f"unexpected coverage field {key} for revision "
                    f"{snapshot.revision}: expected {expected!r}, "
                    f"got {coverage.get(key)!r}"
                )


def reproduce(base: Path, source_dir: Path | None = None) -> dict[str, Any]:
    target_base = base.resolve()
    input_root = (source_dir or RETAINED_BASE).resolve()
    source_bytes = _read_verified_sources(input_root)

    with TemporaryDirectory(prefix="repro-us-hts-2025-part3-") as staging_name:
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
            "filenames or the retained canonical paths; defaults to "
            "repository data/corpus."
        ),
    )
    args = parser.parse_args()
    print(json.dumps(reproduce(args.base, args.source_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
