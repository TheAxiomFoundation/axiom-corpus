#!/usr/bin/env python3
"""Reproduce White House text renditions of Proclamation 11046 annexes.

The Federal Register PDF for 91 FR 46639–46652 renders Annexes I and II as
page images.  The White House publication of the same proclamation supplies
the annexes as two official text-layer PDFs.  This reproducer retains those
two byte-pinned PDFs and emits one annex root plus each exact PyMuPDF page
body.  It never OCRs or uses the graphics-only Federal Register pages as
provision bodies.
"""

from __future__ import annotations

import argparse
import json
import shlex
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from axiom_corpus.corpus import documents
from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.documents import OfficialDocumentSource, _DocumentBlock
from axiom_corpus.corpus.models import (
    DocumentClass,
    ProvisionRecord,
    SourceInventoryItem,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RETAINED_BASE = REPO_ROOT / "data/corpus"

JURISDICTION = "us"
DOCUMENT_CLASS = DocumentClass.RULEMAKING.value
VERSION = "2026-08-02-tariff-338-alcohol-annex-text-renditions"
FR_ROOT_CITATION = "us/rulemaking/federal-register/2026-07-23/2026-14991"
SOURCE_AS_OF = "2026-08-02"
EXPRESSION_DATE = "2026-07-23"
CONTENT_TYPE = "application/pdf"
LANDING_PAGE_URL = (
    "https://www.whitehouse.gov/presidential-actions/2026/07/"
    "imposing-additional-duties-to-offset-canadian-discrimination-against-"
    "the-commerce-of-the-united-states-with-respect-to-alcoholic-beverages/"
)
FR_OFFICIAL_URL = (
    "https://www.govinfo.gov/content/pkg/FR-2026-07-23/pdf/2026-14991.pdf"
)
FR_WAYBACK_TIMESTAMP = "20260724112256"
FR_WAYBACK_URL = (
    f"https://web.archive.org/web/{FR_WAYBACK_TIMESTAMP}id_/{FR_OFFICIAL_URL}"
)
FR_SOURCE_FILENAME = "fr-2026-14991-s338-alcohol.pdf"
FR_SOURCE_SHA256 = "f8e536b4131993736fd315128209d8828078644856cd2566c4fb011efa0a5775"
FR_SOURCE_SIZE_BYTES = 1_300_037
FR_PAGE_COUNT = 14
FR_GRAPHICS_NOTE = (
    "The Federal Register rendition of these annexes is graphics-only "
    "([GRAPHIC][TIFF OMITTED] TD23JY26.050–.059), and the White House "
    "publication is the official text rendition of the same annexes."
)
REPRO_ARGV = (
    "uv",
    "run",
    "--extra",
    "dev",
    "python",
    "scripts/repro/us_s338_alcohol_annexes.py",
    "--base",
    "data/corpus",
)
REPRO_COMMAND = shlex.join(REPRO_ARGV)
if shlex.join(shlex.split(REPRO_COMMAND)) != REPRO_COMMAND:
    raise AssertionError("Section 338 annex repro command is not shlex-canonical")


@dataclass(frozen=True)
class AnnexSpec:
    """One pinned White House annex PDF and its page-text expectations."""

    roman: str
    slug: str
    source_filename: str
    official_url: str
    wayback_timestamp: str
    sha256: str
    size_bytes: int
    page_count: int
    federal_register_pages: str
    body_sha256: tuple[str, ...]

    @property
    def citation_path(self) -> str:
        return f"{FR_ROOT_CITATION}/{self.slug}"

    @property
    def source_id(self) -> str:
        return f"whitehouse-proclamation-11046-{self.slug}"

    @property
    def title(self) -> str:
        return (
            f"Annex {self.roman} to Proclamation 11046—Official White House "
            "Text Rendition"
        )

    @property
    def wayback_url(self) -> str:
        return (
            f"https://web.archive.org/web/{self.wayback_timestamp}id_/"
            f"{self.official_url}"
        )

    @property
    def source_relative_path(self) -> Path:
        return (
            Path("sources")
            / JURISDICTION
            / DOCUMENT_CLASS
            / VERSION
            / "official-documents"
            / self.source_filename
        )


ANNEXES = (
    AnnexSpec(
        roman="I",
        slug="annex-i",
        source_filename="whitehouse-s338-alcohol-annex-1.pdf",
        official_url=(
            "https://www.whitehouse.gov/wp-content/uploads/2026/07/ANNEX-I-2.pdf"
        ),
        wayback_timestamp="20260729174628",
        sha256="055f714425c51050f7c180c14a73f4596f74ee3dd76bb2c26a986421747e917f",
        size_bytes=153_594,
        page_count=3,
        federal_register_pages="46643–46645",
        body_sha256=(
            "b6cba06403f17cddadb31e2c49fc428aba074666174fab840b06bbf427ae0741",
            "e04a2d5375e8f2da9c9cd88644d4f64e0560f59f2852343faf7595c6479da099",
            "69521ed7bdd861c0913446b480f4671646c255934708a88e7dc65b4e54969299",
        ),
    ),
    AnnexSpec(
        roman="II",
        slug="annex-ii",
        source_filename="whitehouse-s338-alcohol-annex-2.pdf",
        official_url=(
            "https://www.whitehouse.gov/wp-content/uploads/2026/07/Annex-II-1.pdf"
        ),
        wayback_timestamp="20260729174629",
        sha256="2b9237b2dcaf7dbe42ebfa408e1fa81247a1bc9b18196d48f283ac261200d24b",
        size_bytes=151_746,
        page_count=7,
        federal_register_pages="46646–46652",
        body_sha256=(
            "120b44380372809b3f9dd73bf888550da249537d9d726eda2e20ee8d1cd76e2e",
            "f60b3bf3bf43764ec69a893441b09cd015b98df53ffe1fe910fdcea106e5c422",
            "37be3689b44cfdaa330d3abd1a8d7aaa6d9fb9b99ce0dbea7cee4bdd8e82cb2f",
            "548a0849ce1aa50a8d5ca0e55cd6f4f7dde768ae5854b605752c0fb6a9aa0cd7",
            "941add820e4a41479e6e49aaee0878e45c8d6a1ff2c2845d7f5f60e6ccd5564d",
            "c4e578b7ef5b30dbd8a56d690590717b254655b8eb35fc22dd126467c3115f38",
            "8800aa080964a5dd3712cb923b868abab9664599c30a676ceeaca77265ca8a47",
        ),
    ),
)

INVENTORY_RELATIVE_PATH = (
    Path("inventory") / JURISDICTION / DOCUMENT_CLASS / f"{VERSION}.json"
)
PROVISIONS_RELATIVE_PATH = (
    Path("provisions") / JURISDICTION / DOCUMENT_CLASS / f"{VERSION}.jsonl"
)
COVERAGE_RELATIVE_PATH = (
    Path("coverage") / JURISDICTION / DOCUMENT_CLASS / f"{VERSION}.json"
)
GENERATED_RELATIVE_PATHS = (
    *(annex.source_relative_path for annex in ANNEXES),
    INVENTORY_RELATIVE_PATH,
    PROVISIONS_RELATIVE_PATH,
    COVERAGE_RELATIVE_PATH,
)


def _resolve_input_path(source_dir: Path, annex: AnnexSpec) -> Path:
    candidates = (
        source_dir / annex.source_filename,
        source_dir / annex.source_relative_path,
    )
    for candidate in candidates:
        if candidate.is_symlink():
            raise ValueError(f"official source must not be a symlink: {candidate}")
        if candidate.is_file():
            return candidate
    choices = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        f"official Annex {annex.roman} source not found; checked {choices}"
    )


def _read_verified_sources(source_dir: Path) -> dict[str, bytes]:
    source_bytes: dict[str, bytes] = {}
    for annex in ANNEXES:
        content = _resolve_input_path(source_dir, annex).read_bytes()
        actual_sha256 = sha256_bytes(content)
        if actual_sha256 != annex.sha256:
            raise ValueError(
                f"Annex {annex.roman} source hash mismatch: "
                f"expected {annex.sha256}, got {actual_sha256}"
            )
        if len(content) != annex.size_bytes:
            raise ValueError(
                f"Annex {annex.roman} source size mismatch: "
                f"expected {annex.size_bytes}, got {len(content)}"
            )
        source_bytes[annex.slug] = content
    _verify_optional_fr_rendition(source_dir)
    return source_bytes


def _verify_optional_fr_rendition(source_dir: Path) -> None:
    """Verify the staged graphics-only FR rendition when it is available."""

    source_path = source_dir / FR_SOURCE_FILENAME
    if not source_path.exists():
        return
    if source_path.is_symlink() or not source_path.is_file():
        raise ValueError(f"Federal Register provenance PDF is invalid: {source_path}")
    content = source_path.read_bytes()
    actual_sha256 = sha256_bytes(content)
    if actual_sha256 != FR_SOURCE_SHA256:
        raise ValueError(
            "Federal Register provenance PDF hash mismatch: "
            f"expected {FR_SOURCE_SHA256}, got {actual_sha256}"
        )
    if len(content) != FR_SOURCE_SIZE_BYTES:
        raise ValueError(
            "Federal Register provenance PDF size mismatch: "
            f"expected {FR_SOURCE_SIZE_BYTES}, got {len(content)}"
        )
    try:
        import fitz

        with fitz.open(stream=content, filetype="pdf") as document:
            if document.page_count != FR_PAGE_COUNT:
                raise ValueError(
                    "Federal Register provenance PDF page-count mismatch: "
                    f"expected {FR_PAGE_COUNT}, got {document.page_count}"
                )
    except ImportError as exc:  # pragma: no cover - corpus runtime always has PyMuPDF
        raise RuntimeError("PyMuPDF is required to verify the provenance PDF") from exc


def _source_metadata(annex: AnnexSpec) -> dict[str, Any]:
    return {
        "primary_source": True,
        "source_authority": "The White House",
        "document_subtype": "annex_text_rendition",
        "annex": annex.roman,
        "proclamation_number": "11046",
        "proclamation_date": "2026-07-20",
        "publication_date": EXPRESSION_DATE,
        "federal_register_citation": "91 FR 46639–46652",
        "federal_register_document_number": "2026-14991",
        "federal_register_annex_pages": annex.federal_register_pages,
        "parent_federal_register_citation_path": FR_ROOT_CITATION,
        "whitehouse_source_url": annex.official_url,
        "whitehouse_landing_page_url": LANDING_PAGE_URL,
        "wayback_timestamp": annex.wayback_timestamp,
        "wayback_url": annex.wayback_url,
        "wayback_byte_identical_to_official": True,
        "source_cross_verified_on": SOURCE_AS_OF,
        "federal_register_pdf_url": FR_OFFICIAL_URL,
        "federal_register_pdf_wayback_timestamp": FR_WAYBACK_TIMESTAMP,
        "federal_register_pdf_wayback_url": FR_WAYBACK_URL,
        "federal_register_pdf_sha256": FR_SOURCE_SHA256,
        "federal_register_pdf_size_bytes": FR_SOURCE_SIZE_BYTES,
        "federal_register_pdf_page_count": FR_PAGE_COUNT,
        "federal_register_graphics_note": FR_GRAPHICS_NOTE,
        "operator_visual_cross_verification": (
            "White House text matches the Federal Register page images "
            "46643–46652; verified 2026-08-02"
        ),
        "federal_register_pdf_retained_in_this_version": False,
        "federal_register_pdf_omission_reason": (
            "graphics-only annex pages are provenance, not provision bodies; "
            "retaining an unreferenced source would weaken scope integrity"
        ),
        "extraction_method": (
            "PyMuPDF page.get_text('text', sort=False) through the standard "
            "corpus PDF page extractor; no OCR or text replacements"
        ),
        "repro_command": REPRO_COMMAND,
    }


def _source(annex: AnnexSpec) -> OfficialDocumentSource:
    return OfficialDocumentSource(
        source_id=annex.source_id,
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS,
        title=annex.title,
        source_url=annex.official_url,
        citation_path=annex.citation_path,
        download_url=annex.wayback_url,
        source_format="pdf",
        source_as_of=SOURCE_AS_OF,
        expression_date=EXPRESSION_DATE,
        extraction={"page_citation_prefix": "page"},
        metadata=_source_metadata(annex),
    )


def _extract_pages(
    annex: AnnexSpec,
    content: bytes,
) -> tuple[_DocumentBlock, ...]:
    blocks = documents._extract_blocks(
        content,
        "pdf",
        source_url=annex.official_url,
        title=annex.title,
        extraction={"page_citation_prefix": "page"},
    )
    if len(blocks) != annex.page_count:
        raise ValueError(
            f"expected {annex.page_count} Annex {annex.roman} pages, "
            f"got {len(blocks)}"
        )
    for page_number, block in enumerate(blocks, start=1):
        if block.kind != "page" or block.ordinal != page_number:
            raise ValueError(
                f"unexpected Annex {annex.roman} block at page {page_number}"
            )
        if block.metadata != {
            "page_number": page_number,
            "citation_suffix": f"page-{page_number}",
        }:
            raise ValueError(
                f"unexpected Annex {annex.roman} metadata at page {page_number}"
            )
        body_sha256 = sha256_bytes(block.body.encode("utf-8"))
        if body_sha256 != annex.body_sha256[page_number - 1]:
            raise ValueError(
                f"Annex {annex.roman} page {page_number} extracted-text "
                f"hash mismatch: {body_sha256}"
            )
    return blocks


def _leveled_records(
    records: tuple[ProvisionRecord, ...],
) -> tuple[ProvisionRecord, ...]:
    return tuple(
        replace(record, level=4 if index == 0 else 5)
        for index, record in enumerate(records)
    )


def _build_scope(
    staging_base: Path,
    source_bytes: dict[str, bytes],
) -> dict[str, Any]:
    store = CorpusArtifactStore(staging_base)
    inventory: list[SourceInventoryItem] = []
    records: list[ProvisionRecord] = []
    page_count = 0

    for annex in ANNEXES:
        content = source_bytes[annex.slug]
        source = _source(annex)
        source_sha = store.write_bytes(
            staging_base / annex.source_relative_path,
            content,
        )
        source_key = annex.source_relative_path.as_posix()
        blocks = _extract_pages(annex, content)
        page_count += len(blocks)
        inventory.extend(
            documents._inventory_items(
                source,
                blocks=blocks,
                source_key=source_key,
                source_format="pdf",
                source_sha=source_sha,
                content_type=CONTENT_TYPE,
                final_url=annex.wayback_url,
            )
        )
        records.extend(
            _leveled_records(
                documents._provision_records(
                    source,
                    blocks=blocks,
                    version=VERSION,
                    source_key=source_key,
                    source_format="pdf",
                    source_as_of=SOURCE_AS_OF,
                    expression_date=EXPRESSION_DATE,
                    content_type=CONTENT_TYPE,
                    final_url=annex.wayback_url,
                )
            )
        )

    store.write_inventory(staging_base / INVENTORY_RELATIVE_PATH, inventory)
    store.write_provisions(staging_base / PROVISIONS_RELATIVE_PATH, records)
    coverage = compare_provision_coverage(
        tuple(inventory),
        tuple(records),
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS,
        version=VERSION,
    )
    if not coverage.complete:
        raise ValueError(f"incomplete annex coverage: {coverage.to_mapping()}")
    store.write_json(staging_base / COVERAGE_RELATIVE_PATH, coverage.to_mapping())
    return {
        "annex_count": len(ANNEXES),
        "page_count": page_count,
        "row_count": len(records),
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _verify_critical_text(rows_by_path: dict[str, dict[str, Any]]) -> None:
    annex_one = rows_by_path[f"{FR_ROOT_CITATION}/annex-i/page-1"]["body"]
    section_338_note = (
        "Annex I Note: A 50% ad valorem Section 338 tariff shall apply to the "
        "following articles, unless they are subject to import restrictions "
        "imposed pursuant to section 232 of the Trade Expansion Act of 1962, "
        "as amended (18 U.S.C. 1862), or articles of civil aircraft or "
        "aircraft parts that meet the criteria of General Note 6 of the HTSUS."
    )
    if section_338_note not in annex_one:
        raise ValueError("critical Annex I Section 338 note is missing")
    if "Product Description 2203.00.00 Beer made from malt" not in annex_one:
        raise ValueError("critical Annex I beer witness line is missing")

    annex_two_page_one = rows_by_path[
        f"{FR_ROOT_CITATION}/annex-ii/page-1"
    ]["body"]
    required_page_one = (
        (
            "Effective with respect to goods entered for consumption, or "
            "withdrawn from warehouse for consumption, on or after 12:01 a.m. "
            "eastern time on August 19, 2026"
        ),
        "The following new U.S. note 51 is inserted in numerical order:",
        "Products that are provided for in headings 9903.03.12−9903.03.16",
        "Heading 9903.03.12 applies to articles classifiable",
        "2203.00.00 2204.10.00",
    )
    for text in required_page_one:
        if text not in annex_two_page_one:
            raise ValueError(f"critical U.S. note 51 text is missing: {text!r}")

    annex_two_page_two = rows_by_path[
        f"{FR_ROOT_CITATION}/annex-ii/page-2"
    ]["body"]
    required_page_two = (
        "headings 9903.82.02 and 9903.82.04–9903.82.26",
        "passenger vehicles (sedans, sport utility vehicles",
        "wood products provided for in headings 9903.76.01",
    )
    for text in required_page_two:
        if text not in annex_two_page_two:
            raise ValueError(f"critical subdivision (c) text is missing: {text!r}")

    annex_two_page_three = rows_by_path[
        f"{FR_ROOT_CITATION}/annex-ii/page-3"
    ]["body"]
    required_page_three = (
        "semiconductor articles provided for in heading 9903.79.01;",
        "patented pharmaceutical articles provided for in headings 9903.04.60–9903.04.66.",
        "(d) As provided in heading 9903.03.16",
        "articles of civil aircraft (all aircraft other than military aircraft",
    )
    for text in required_page_three:
        if text not in annex_two_page_three:
            raise ValueError(f"critical subdivision (c)/(d) text is missing: {text!r}")

    annex_two_page_six = rows_by_path[
        f"{FR_ROOT_CITATION}/annex-ii/page-6"
    ]["body"]
    heading_9903_03_12 = (
        "9903.03.12 Articles the product of Canada as provided in subdivision "
        "(b)(1) of U.S. note 51 to this subchapter ..................... The "
        "duty provided in the applicable subheading + 50% The duty provided "
        "in the applicable subheading + 50% No change"
    )
    if heading_9903_03_12 not in annex_two_page_six:
        raise ValueError("critical 9903.03.12 inserted heading is missing")

    annex_two_page_seven = rows_by_path[
        f"{FR_ROOT_CITATION}/annex-ii/page-7"
    ]["body"]
    if "9903.03.15 Articles of aluminum" not in annex_two_page_seven:
        raise ValueError("critical 9903.03.15 inserted heading is missing")
    if "9903.03.16 Articles of civil aircraft" not in annex_two_page_seven:
        raise ValueError("critical 9903.03.16 inserted heading is missing")
    if annex_two_page_seven.count("No change") != 6:
        raise ValueError("9903.03.15/.16 duty columns did not remain all 'No change'")


def _verify_generated_scope(
    staging_base: Path,
    source_bytes: dict[str, bytes],
) -> None:
    expected_paths: list[str] = []
    expected_bodies: dict[str, str | None] = {}
    for annex in ANNEXES:
        retained = (staging_base / annex.source_relative_path).read_bytes()
        if retained != source_bytes[annex.slug]:
            raise ValueError(f"retained Annex {annex.roman} PDF is not byte-identical")
        expected_paths.append(annex.citation_path)
        expected_bodies[annex.citation_path] = None
        for block in _extract_pages(annex, source_bytes[annex.slug]):
            path = f"{annex.citation_path}/page-{block.ordinal}"
            expected_paths.append(path)
            expected_bodies[path] = block.body

    records = _load_jsonl(staging_base / PROVISIONS_RELATIVE_PATH)
    rows_by_path = {record["citation_path"]: record for record in records}
    if len(rows_by_path) != len(records):
        raise ValueError("duplicate annex citation paths")
    if [record["citation_path"] for record in records] != expected_paths:
        raise ValueError("unexpected annex citation paths or ordering")

    specs_by_root = {annex.citation_path: annex for annex in ANNEXES}
    for record in records:
        citation_path = record["citation_path"]
        root_path = next(
            root
            for root in specs_by_root
            if citation_path == root or citation_path.startswith(f"{root}/")
        )
        annex = specs_by_root[root_path]
        if record.get("body") != expected_bodies[citation_path]:
            raise ValueError(f"body differs from standard PDF extraction: {citation_path}")
        if record.get("version") != VERSION or record.get("source_url") != annex.official_url:
            raise ValueError(f"scope provenance drifted: {citation_path}")
        metadata = record.get("metadata", {})
        required_metadata = _source_metadata(annex)
        for key, expected in required_metadata.items():
            if metadata.get(key) != expected:
                raise ValueError(
                    f"metadata {key} drifted for {citation_path}: "
                    f"expected {expected!r}, got {metadata.get(key)!r}"
                )
        if metadata.get("download_url") != annex.wayback_url:
            raise ValueError(f"download URL drifted: {citation_path}")
        if citation_path == root_path:
            if record.get("kind") != "document" or record.get("level") != 4:
                raise ValueError(f"annex root kind/level drifted: {citation_path}")
            if "parent_citation_path" in record or "parent_id" in record:
                raise ValueError(f"annex root has a cross-version parent: {citation_path}")
        else:
            if record.get("kind") != "page" or record.get("level") != 5:
                raise ValueError(f"annex page kind/level drifted: {citation_path}")
            if record.get("parent_citation_path") != root_path:
                raise ValueError(f"annex page parent drifted: {citation_path}")

    inventory = json.loads(
        (staging_base / INVENTORY_RELATIVE_PATH).read_text(encoding="utf-8")
    )["items"]
    if [item["citation_path"] for item in inventory] != expected_paths:
        raise ValueError("inventory and provision citation paths differ")
    for item in inventory:
        root_path = next(
            root
            for root in specs_by_root
            if item["citation_path"] == root
            or item["citation_path"].startswith(f"{root}/")
        )
        if item.get("sha256") != specs_by_root[root_path].sha256:
            raise ValueError(f"inventory source hash drifted: {item['citation_path']}")

    coverage = json.loads(
        (staging_base / COVERAGE_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    expected_count = len(ANNEXES) + sum(annex.page_count for annex in ANNEXES)
    expected_coverage = {
        "complete": True,
        "document_class": DOCUMENT_CLASS,
        "jurisdiction": JURISDICTION,
        "matched_count": expected_count,
        "provision_count": expected_count,
        "source_count": expected_count,
        "version": VERSION,
    }
    for key, expected in expected_coverage.items():
        if coverage.get(key) != expected:
            raise ValueError(
                f"unexpected coverage field {key}: expected {expected!r}, "
                f"got {coverage.get(key)!r}"
            )
    _verify_critical_text(rows_by_path)


def reproduce(base: Path, source_dir: Path | None = None) -> dict[str, Any]:
    """Verify the pinned White House PDFs and atomically reproduce the scope."""

    target_base = base.resolve()
    input_root = (source_dir or RETAINED_BASE).resolve()
    source_bytes = _read_verified_sources(input_root)
    with TemporaryDirectory(prefix="repro-us-s338-alcohol-annexes-") as staging_name:
        staging_base = Path(staging_name) / "corpus"
        scope = _build_scope(staging_base, source_bytes)
        _verify_generated_scope(staging_base, source_bytes)

        target_store = CorpusArtifactStore(target_base)
        generated_hashes: dict[str, str] = {}
        for relative_path in GENERATED_RELATIVE_PATHS:
            generated = (staging_base / relative_path).read_bytes()
            target_store.write_bytes(target_base / relative_path, generated)
            generated_hashes[relative_path.as_posix()] = sha256_bytes(generated)

    return {
        "base": str(target_base),
        "command": REPRO_COMMAND,
        "files": generated_hashes,
        "scope": scope,
        "source_sha256": {
            annex.source_filename: annex.sha256 for annex in ANNEXES
        },
        "version": VERSION,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True, help="Destination corpus base.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        help=(
            "Optional local input root containing the two flat staged PDFs "
            "or their retained corpus paths; defaults to data/corpus."
        ),
    )
    args = parser.parse_args()
    print(json.dumps(reproduce(args.base, args.source_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
