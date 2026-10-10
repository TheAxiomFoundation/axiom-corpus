#!/usr/bin/env python3
"""Reproduce the USITC HTS 2026 Revision 15 full-schedule provision scope.

Normalizes EVERY row of the pinned Revision 15 snapshot that carries an
HTS number (29,845 rows across 99 chapter keys) into per-line provisions
at ``us/statute/hts/<htsno>``, from the same retained source bytes as the
witness-chapter version ``2026-08-04-usitc-hts-2026-rev15`` (SHA-256
``59a76c12…``). The witness-chapter version normalized chapters 72/76/95
plus 9903 (1,706 rows); this version is its full-schedule superset and
exists so that generated full-schedule rate encodings (rulespec-us
us-tariff-duty line tables) can ground proof atoms on per-line provisions
for every rated line, not only the witness slice.

Provision bodies use the same canonical rendering as the witness-chapter
version (description, unit of quantity, rate columns, footnotes), so the
1,706 overlapping citation paths carry byte-identical bodies; local-corpus
resolution that selects the newest ``source_as_of`` resolves to identical
text either way. Row metadata is deliberately minimal — the body text IS
the canonical rendering proof atoms ground against, and structured field
access belongs to the pinned snapshot bytes, so per-row metadata carries
only {htsno, indent, row_index} plus short identifiers. Full download
provenance and mirror verification live on the document root row only.
At 29,846 provisions this keeps the artifact ~30 MB instead of ~97 MB
(the snapshot versions' per-row provenance duplication would put the
full schedule at GitHub's file-size limit). The retained source file is
byte-identical to the witness version's (same blob), re-retained under
this version's canonical path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, replace
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
SOURCE_AS_OF = "2026-08-09"
EDITION = "2026"
NORMALIZATION_SCOPE = "full-schedule-all-htsno-rows"
RESTSTOP_EXPORT_URL = (
    "https://hts.usitc.gov/reststop/exportList?from=0101&to=9999&format=JSON&styles=false"
)
EXPECTED_STATIC_URL = (
    "https://www.usitc.gov/sites/default/files/tata/hts/hts_2026_revision_15_json.json"
)
RELEASE_NAME = "2026HTSRev15"
WITNESS_VERSION = "2026-08-04-usitc-hts-2026-rev15"
WITNESS_ROW_COUNT = 1_706
# Metadata keys that must appear ONLY on the document root row.
ROOT_ONLY_METADATA_KEYS = frozenset(
    {
        "download_provenance",
        "mirror_verification",
        "expected_static_url",
        "static_url_published_at_ingest",
        "revision",
        "revision_effective_date",
        "total_rows",
        "target_rows",
        "witness_chapter_version",
    }
)
# Pre-existing us/statute citation paths whose SELECTED body (newest
# source_as_of wins in local-corpus resolution) legitimately changes when
# this version lands: Revision 4 -> Revision 15 dropped the general-column
# "See 9903..." footnotes on the beer and solar witness lines. Pinned by
# body sha256 prefix (old selected -> this version). Any OTHER selected-body
# change across the whole us/statute provisions tree is a hard failure.
EXPECTED_SELECTED_BODY_CHANGES = {
    "us/statute/hts/2203.00.00": ("8716b1ca17658e8f", "999fb5d98cfbd9c8"),
    "us/statute/hts/8541.42.00": ("fda9cf9c05dbaadb", "d3b5808b56fb6f23"),
    "us/statute/hts/8541.43.00": ("9f6d0178a4d89f39", "c794db81b9212f96"),
}
REPRO_COMMAND = (
    "uv run --extra dev python "
    "scripts/repro/us_hts_tariff_full_schedule_2026_rev15.py --base data/corpus"
)


@dataclass(frozen=True)
class RevisionSnapshot:
    """The pinned full-edition USITC HTS JSON snapshot, full-schedule scope."""

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
        return f"{SOURCE_AS_OF}-usitc-hts-{EDITION}-rev{self.revision}-full-schedule"

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
        return f"usitc-hts-{EDITION}-rev{self.revision}-full-schedule"

    @property
    def title(self) -> str:
        return (
            f"Harmonized Tariff Schedule of the United States ({EDITION}) "
            f"Revision {self.revision} (full schedule)"
        )


SNAPSHOTS = (
    RevisionSnapshot(
        revision=15,
        expression_date="2026-08-03",
        sha256="59a76c12e28d7a28975f31a8876bfb08e64927b922fe2b4f88801ff4459181e6",
        size_bytes=12_630_559,
        total_rows=35_789,
        target_rows=29_845,
        rows_by_chapter={
            "01": 100,
            "02": 223,
            "03": 697,
            "04": 310,
            "05": 56,
            "06": 96,
            "07": 533,
            "08": 330,
            "09": 118,
            "10": 92,
            "11": 75,
            "12": 220,
            "13": 33,
            "14": 21,
            "15": 169,
            "16": 248,
            "17": 120,
            "18": 105,
            "19": 134,
            "20": 374,
            "21": 141,
            "22": 161,
            "23": 84,
            "24": 260,
            "25": 144,
            "26": 137,
            "27": 178,
            "28": 459,
            "29": 1501,
            "30": 231,
            "31": 37,
            "32": 214,
            "33": 95,
            "34": 71,
            "35": 49,
            "36": 27,
            "37": 91,
            "38": 284,
            "39": 432,
            "40": 271,
            "41": 247,
            "42": 157,
            "43": 51,
            "44": 695,
            "45": 26,
            "46": 62,
            "47": 35,
            "48": 433,
            "49": 69,
            "50": 41,
            "51": 170,
            "52": 722,
            "53": 83,
            "54": 368,
            "55": 500,
            "56": 116,
            "57": 110,
            "58": 159,
            "59": 103,
            "60": 154,
            "61": 1054,
            "62": 1575,
            "63": 311,
            "64": 507,
            "65": 88,
            "66": 12,
            "67": 19,
            "68": 135,
            "69": 173,
            "70": 397,
            "71": 191,
            "72": 740,
            "73": 759,
            "74": 192,
            "75": 43,
            "76": 182,
            "78": 19,
            "79": 18,
            "80": 17,
            "81": 108,
            "82": 264,
            "83": 129,
            "84": 2290,
            "85": 1301,
            "86": 50,
            "87": 527,
            "88": 84,
            "89": 78,
            "90": 570,
            "91": 229,
            "92": 84,
            "93": 93,
            "94": 374,
            "95": 162,
            "96": 209,
            "97": 40,
            "98": 503,
            "99": 2474,
            "9903": 622,
        },
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
        "retained_bytes_identical_to_version": WITNESS_VERSION,
    }


def _mirror_verification(snapshot: RevisionSnapshot) -> str:
    return (
        "byte-identical to the retained source of version "
        f"{WITNESS_VERSION} (official reststop exportList response 0101-9999, "
        f"fetched while reststop/currentRelease reported {RELEASE_NAME} "
        "immediately before and after the download; see that version's "
        "provenance for the full download record). This version re-normalizes "
        "the same pinned bytes at full-schedule scope."
    )


# Regime anchors are literal excerpts observed in the normalized bodies built
# from the pinned input. The witness-chapter anchors prove continuity with the
# 2026-08-04 version's bodies; the far-corner anchors prove the widened scope
# actually reaches chapters the witness version never normalized.
EXPECTED_EXCERPTS: dict[str, dict[str, tuple[str, ...]]] = {
    "15": {
        f"{CITATION_ROOT}/7202.11.10.00": (
            "Rates of duty (1-General): 1.4%",
            "Rates of duty (2): 6.5%",
        ),
        f"{CITATION_ROOT}/9903.04.63": (
            "Patented pharmaceutical articles that are the product of the United Kingdom",
            "The duty provided in the applicable subheading +0%",
        ),
        f"{CITATION_ROOT}/0101.21.00": (
            "Purebred breeding animals",
            "Rates of duty (1-General): Free",
        ),
        f"{CITATION_ROOT}/2909.19.18.00": ("Rates of duty (2): 37%",),
        f"{CITATION_ROOT}/9802.00.91.00": ("Textile and apparel goods, assembled in Mexico",),
        f"{CITATION_ROOT}/8471.30.01.00": ("Rates of duty (1-General): Free",),
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


def _witness_source_path(snapshot: RevisionSnapshot) -> Path:
    return (
        Path("sources")
        / JURISDICTION
        / DOCUMENT_CLASS
        / WITNESS_VERSION
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
        source_dir / _witness_source_path(snapshot),
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
    return bool(str(row.get("htsno") or ""))


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


def _row_metadata_base() -> dict[str, Any]:
    return {
        "edition": EDITION,
        "release": RELEASE_NAME,
        "normalization_scope": NORMALIZATION_SCOPE,
    }


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
                        "row_index": row_index,
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
        **_row_metadata_base(),
        "revision": snapshot.revision,
        "revision_effective_date": snapshot.expression_date,
        "download_provenance": _download_provenance(snapshot),
        "expected_static_url": EXPECTED_STATIC_URL,
        "static_url_published_at_ingest": False,
        "mirror_verification": _mirror_verification(snapshot),
        "total_rows": snapshot.total_rows,
        "target_rows": snapshot.target_rows,
        "witness_chapter_version": WITNESS_VERSION,
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
        metadata=_row_metadata_base(),
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

    inventory = list(
        documents._inventory_items(
            source,
            blocks=blocks,
            source_key=source_key,
            source_format="json",
            source_sha=source_sha,
            content_type="application/json",
            final_url=snapshot.download_url,
        )
    )
    records = list(
        documents._provision_records(
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
    )
    # The document root alone carries the verbose provenance; every hts-row
    # keeps the minimal metadata assembled above.
    root_metadata_extra = _snapshot_metadata(snapshot)
    records[0] = replace(
        records[0],
        metadata={**(records[0].metadata or {}), **root_metadata_extra},
    )
    inventory[0] = replace(
        inventory[0],
        metadata={**(inventory[0].metadata or {}), **root_metadata_extra},
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


def _selection_key(record: dict[str, Any]) -> tuple[str, int, str]:
    official = 1 if record.get("source_format") == "legislation.gov.uk-clml" else 0
    return (
        str(record.get("source_as_of") or ""),
        official,
        str(record.get("version") or ""),
    )


def _verify_selected_body_changes(staging_base: Path) -> None:
    """F2 gate: this version must change local-corpus selected bodies for
    EXACTLY the allowlisted citation paths, with pinned sha256 prefixes.

    Local-corpus resolution (pinned axiom-encode) picks the maximum of
    (source_as_of, official-source flag, version) among body-bearing rows
    for a citation path; this version's rows win every overlap. Scans every
    pre-existing us/statute provisions file in the repository.
    """
    snapshot = SNAPSHOTS[0]
    existing_dir = RETAINED_BASE / "provisions" / JURISDICTION / DOCUMENT_CLASS
    best_old: dict[str, dict[str, Any]] = {}
    for provisions_file in sorted(existing_dir.glob("*.jsonl")):
        if provisions_file.stem == snapshot.version:
            continue
        for record in _load_jsonl(provisions_file):
            citation = record.get("citation_path")
            if not citation or not str(record.get("body") or "").strip():
                continue
            current = best_old.get(citation)
            if current is None or _selection_key(record) > _selection_key(current):
                best_old[citation] = record
    new_rows = {
        record["citation_path"]: record
        for record in _load_jsonl(staging_base / _provisions_path(snapshot))
        if str(record.get("body") or "").strip()
    }
    changed: dict[str, tuple[str, str]] = {}
    for citation, old in best_old.items():
        new = new_rows.get(citation)
        if new is None:
            continue
        old_body, new_body = str(old["body"]), str(new["body"])
        if old_body != new_body:
            changed[citation] = (
                hashlib.sha256(old_body.encode()).hexdigest()[:16],
                hashlib.sha256(new_body.encode()).hexdigest()[:16],
            )
    if changed != EXPECTED_SELECTED_BODY_CHANGES:
        unexpected = {
            citation: shas
            for citation, shas in changed.items()
            if EXPECTED_SELECTED_BODY_CHANGES.get(citation) != shas
        }
        missing = sorted(set(EXPECTED_SELECTED_BODY_CHANGES) - set(changed))
        raise ValueError(
            "selected-body changes diverge from the allowlist: "
            f"unexpected={unexpected} missing={missing}"
        )


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
            if row.get("source_as_of") != SOURCE_AS_OF:
                raise ValueError(
                    f"unexpected source_as_of on {row['citation_path']} for snapshot {snapshot.key}"
                )
            if row.get("source_url") != snapshot.official_url:
                raise ValueError(
                    f"unexpected source_url on {row['citation_path']} for snapshot {snapshot.key}"
                )
            metadata = row.get("metadata", {})
            for key, expected in _row_metadata_base().items():
                if metadata.get(key) != expected:
                    raise ValueError(
                        f"unexpected metadata field {key} on {row['citation_path']} "
                        f"for snapshot {snapshot.key}"
                    )
            if row is not root_row:
                leaked = ROOT_ONLY_METADATA_KEYS & set(metadata)
                if leaked:
                    raise ValueError(
                        f"root-only provenance {sorted(leaked)} leaked onto "
                        f"{row['citation_path']} for snapshot {snapshot.key}"
                    )

        root_metadata = root_row.get("metadata", {})
        for key, expected in _snapshot_metadata(snapshot).items():
            if root_metadata.get(key) != expected:
                raise ValueError(
                    f"unexpected root metadata field {key} for snapshot {snapshot.key}"
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

        witness_provisions = (
            RETAINED_BASE
            / "provisions"
            / JURISDICTION
            / DOCUMENT_CLASS
            / (WITNESS_VERSION + ".jsonl")
        )
        if not witness_provisions.is_file():
            raise ValueError(f"witness provisions missing: {witness_provisions}")
        witness_rows = [
            row for row in _load_jsonl(witness_provisions) if row.get("kind") == "hts-row"
        ]
        if len(witness_rows) != WITNESS_ROW_COUNT:
            raise ValueError(f"witness hts-row count {len(witness_rows)} != {WITNESS_ROW_COUNT}")
        witness_bodies = {row["citation_path"]: str(row.get("body") or "") for row in witness_rows}
        if len(witness_bodies) != len(witness_rows):
            raise ValueError("duplicate citation paths in witness provisions")
        not_covered = sorted(set(witness_bodies) - set(rows_by_path))
        if not_covered:
            raise ValueError(
                "witness citation paths missing from full schedule: "
                f"{not_covered[:5]} ({len(not_covered)} total)"
            )
        mismatched = [
            path
            for path, body in witness_bodies.items()
            if str(rows_by_path[path].get("body") or "") != body
        ]
        if mismatched:
            raise ValueError(
                "full-schedule bodies diverge from witness-chapter bodies: "
                f"{mismatched[:5]} ({len(mismatched)} total)"
            )

        inventory = json.loads(
            (staging_base / _inventory_path(snapshot)).read_text(encoding="utf-8")
        )["items"]
        if {item["citation_path"] for item in inventory} != set(rows_by_path):
            raise ValueError(f"inventory/provision paths differ for snapshot {snapshot.key}")
        for item in inventory:
            if item["citation_path"] == CITATION_ROOT:
                continue
            leaked = ROOT_ONLY_METADATA_KEYS & set(item.get("metadata") or {})
            if leaked:
                raise ValueError(
                    f"root-only provenance {sorted(leaked)} leaked onto inventory "
                    f"item {item['citation_path']} for snapshot {snapshot.key}"
                )

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

    with TemporaryDirectory(prefix="repro-us-hts-2026-rev15-full-") as staging_name:
        staging_base = Path(staging_name) / "corpus"
        scopes = [
            _build_snapshot_scope(staging_base, snapshot, source_bytes[snapshot.key])
            for snapshot in SNAPSHOTS
        ]
        _verify_generated_scope(staging_base, source_bytes)
        _verify_selected_body_changes(staging_base)

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
            "the witness version's retained canonical path, or this "
            "version's canonical path; defaults to repository data/corpus."
        ),
    )
    args = parser.parse_args()
    print(json.dumps(reproduce(args.base, args.source_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
