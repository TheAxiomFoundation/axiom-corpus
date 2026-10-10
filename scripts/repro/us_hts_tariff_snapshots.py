#!/usr/bin/env python3
"""Reproduce the USITC HTS 2026 revision snapshot ingest from exact sources.

Ingests four full-revision USITC Harmonized Tariff Schedule JSON snapshots
(Revisions 3, 4, 12, and 14 of the 2026 edition) and normalizes the tariff
rows for chapters 72, 76, and 95 plus every subchapter III/IV Chapter 99
heading in the 9903 family. The four revisions straddle the two 2026 tariff
regime boundaries: IEEPA-tariff termination / section 122 surcharge start
(2026-02-24 -> Revision 4 effective 2026-02-25) and the section 122 sunset /
forced-labor 301 tier start (2026-07-24 -> Revision 12 was operative
2026-07-21..2026-07-28 and Revision 14 became operative 2026-07-31).

Every snapshot is the Internet Archive Wayback Machine capture of the same
official USITC static URL family
(https://www.usitc.gov/sites/default/files/tata/hts/hts_2026_revision_N_json.json);
the retained bytes were cross-verified against independent mirrors (Yale
Budget Lab hts_archives for Revisions 3/4/12 and the live hts.usitc.gov
reststop export for Revision 14) before being pinned here by SHA-256.
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
    "https://www.usitc.gov/sites/default/files/tata/hts/hts_2026_revision_{revision}_json.json"
)
WAYBACK_URL_TEMPLATE = "https://web.archive.org/web/{timestamp}/{official_url}"
REPRO_COMMAND = (
    "uv run --extra dev python scripts/repro/us_hts_tariff_snapshots.py --base data/corpus"
)


@dataclass(frozen=True)
class RevisionSnapshot:
    """One pinned full-revision USITC HTS JSON snapshot."""

    revision: int
    expression_date: str
    wayback_timestamp: str
    sha256: str
    size_bytes: int
    total_rows: int
    target_rows: int
    rows_by_chapter: dict[str, int]

    @property
    def version(self) -> str:
        return f"2026-08-01-usitc-hts-2026-rev{self.revision}"

    @property
    def official_filename(self) -> str:
        return f"hts_2026_revision_{self.revision}_json.json"

    @property
    def official_url(self) -> str:
        return OFFICIAL_URL_TEMPLATE.format(revision=self.revision)

    @property
    def wayback_url(self) -> str:
        return WAYBACK_URL_TEMPLATE.format(
            timestamp=self.wayback_timestamp, official_url=self.official_url
        )

    @property
    def source_id(self) -> str:
        return f"usitc-hts-2026-rev{self.revision}"

    @property
    def title(self) -> str:
        return f"Harmonized Tariff Schedule of the United States (2026) Revision {self.revision}"


SNAPSHOTS = (
    RevisionSnapshot(
        revision=3,
        expression_date="2026-02-12",
        wayback_timestamp="20260216170026",
        sha256="fae12fab3c47b54cfb5db7325478d222409adbcfa8a10812fa2af0d213dff07e",
        size_bytes=13_689_892,
        total_rows=35_722,
        target_rows=1_783,
        rows_by_chapter={"72": 738, "76": 182, "95": 162, "9903": 701},
    ),
    RevisionSnapshot(
        revision=4,
        expression_date="2026-02-25",
        wayback_timestamp="20260312220249",
        sha256="0273ec6e6251479a3fc5056e2ed1d4f737fa7ee0675bc37c122364cc7a5732a3",
        size_bytes=13_698_812,
        total_rows=35_733,
        target_rows=1_794,
        rows_by_chapter={"72": 738, "76": 182, "95": 162, "9903": 712},
    ),
    RevisionSnapshot(
        revision=12,
        expression_date="2026-07-21",
        wayback_timestamp="20260801124018",
        sha256="c2df18de026f8ba78178a10dff5033b153c7a48fd66b5f218f529c1369fa0c72",
        size_bytes=13_535_498,
        total_rows=35_678,
        target_rows=1_595,
        rows_by_chapter={"72": 740, "76": 182, "95": 162, "9903": 511},
    ),
    RevisionSnapshot(
        revision=14,
        expression_date="2026-07-31",
        wayback_timestamp="20260801124009",
        sha256="a99da87129ebfd71352b9a747b2a36045a45f7f838ce8d4b9b02e157b78392ef",
        size_bytes=12_630_562,
        total_rows=35_789,
        target_rows=1_706,
        rows_by_chapter={"72": 740, "76": 182, "95": 162, "9903": 622},
    ),
)

MIRROR_VERIFICATION = {
    3: (
        "byte-identical to Yale Budget Lab mirror "
        "hts_archives/hts_2026_rev_3.json.gz (same SHA-256 after gunzip)"
    ),
    4: (
        "byte-identical to Yale Budget Lab mirror "
        "hts_archives/hts_2026_rev_4.json.gz (same SHA-256 after gunzip)"
    ),
    12: (
        "content-identical to Yale Budget Lab mirror "
        "hts_archives/hts_2026_rev_12.json.gz after dropping the static "
        "file's extra leading 0101 heading row, null/empty normalization, "
        "and stripping HTML presentation tags retained by the mirror"
    ),
    14: (
        "content-identical to the live hts.usitc.gov reststop exportList "
        "response after dropping the static file's extra leading 0101 "
        "heading row, null/empty normalization, and stripping HTML "
        "presentation tags retained by the export"
    ),
}

# Regime anchors that must hold in each retained revision. Excerpts are
# matched against normalized provision bodies.
EXPECTED_EXCERPTS: dict[int, dict[str, tuple[str, ...]]] = {
    3: {
        # IEEPA reciprocal baseline still on the books before 2026-02-24.
        f"{CITATION_ROOT}/9903.01.25": ("The duty provided in the applicable subheading + 10%",),
        f"{CITATION_ROOT}/7202.11.10.00": ("Rates of duty (1-General): 1.4%",),
    },
    4: {
        # Section 122 balance-of-payments surcharge headings arrive.
        f"{CITATION_ROOT}/9903.03.01": (
            "subdivision (aa) of U.S. note 2 to this subchapter",
            "The duty provided in the applicable subheading + 10%",
        ),
    },
    12: {
        # Section 122 surcharge still operative late in its window.
        f"{CITATION_ROOT}/9903.03.01": ("The duty provided in the applicable subheading + 10%",),
    },
    14: {
        # Forced-labor 301 country tiers and Brazil 301 in force.
        f"{CITATION_ROOT}/9903.05.20": (
            "articles the product of Algeria",
            "U.S. note 52 to this subchapter",
            "The duty provided in the applicable subheading + 12.5%",
        ),
        f"{CITATION_ROOT}/9903.05.49": ("Rates of duty (1-General): 12.5%",),
        f"{CITATION_ROOT}/9903.05.01": (
            "articles the product of Brazil",
            "U.S. note 50 to this subchapter",
            "The duty provided in the applicable subheading + 25%",
        ),
        f"{CITATION_ROOT}/9903.88.03": ("The duty provided in the applicable subheading + 25%",),
        f"{CITATION_ROOT}/7601.10.30.00": ("Rates of duty (1-General): 2.6%",),
        f"{CITATION_ROOT}/9506.62.40": (
            "Footballs and soccer balls",
            "Rates of duty (1-General): Free",
        ),
    },
}
# Citation paths that must NOT exist in a given revision (regime absence).
EXPECTED_ABSENT: dict[int, tuple[str, ...]] = {
    # No section 122 headings before 2026-02-25.
    3: (f"{CITATION_ROOT}/9903.03.01",),
    # No forced-labor 301 tier or country-exemption headings before Rev13.
    12: (
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
            "edition": "2026",
            "revision": snapshot.revision,
            "revision_effective_date": snapshot.expression_date,
            "wayback_timestamp": snapshot.wayback_timestamp,
            "wayback_url": snapshot.wayback_url,
            "mirror_verification": MIRROR_VERIFICATION[snapshot.revision],
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
                    f"unexpected version on {row['citation_path']} for revision {snapshot.revision}"
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

    with TemporaryDirectory(prefix="repro-us-hts-tariff-") as staging_name:
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
            "Optional local input root. Accepts the four flat official "
            "filenames or the retained canonical paths; defaults to "
            "repository data/corpus."
        ),
    )
    args = parser.parse_args()
    print(json.dumps(reproduce(args.base, args.source_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
