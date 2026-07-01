"""Extract Public Law 119-21 section 71119 Medicaid community engagement text.

The current US Code release in the Medicaid corpus includes the conforming
cross-reference in 42 U.S.C. 1396a(a)(10)(A)(i)(VIII), but not yet the newly
added 42 U.S.C. 1396a(xx) subsection text. GovInfo's enrolled Public Law USLM
is the primary source for that amendment until the US Code release catches up.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-06-29-pl-119-21-medicaid-community-engagement"
SOURCE_URL = "https://www.govinfo.gov/content/pkg/PLAW-119publ21/uslm/PLAW-119publ21.xml"
SOURCE_AS_OF = "2025-08-14"
EXPRESSION_DATE = "2025-07-04"
SOURCE_DIR = ROOT / "data" / "corpus" / "sources" / "us" / "statute" / VERSION / "uslm"
SOURCE_PATH = SOURCE_DIR / "PLAW-119publ21.xml"
PROVISIONS_PATH = (
    ROOT / "data" / "corpus" / "provisions" / "us" / "statute" / f"{VERSION}.jsonl"
)
INVENTORY_PATH = (
    ROOT / "data" / "corpus" / "inventory" / "us" / "statute" / f"{VERSION}.json"
)
COVERAGE_PATH = (
    ROOT / "data" / "corpus" / "coverage" / "us" / "statute" / f"{VERSION}.json"
)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _num_value(element: ET.Element) -> str | None:
    for child in element:
        if _local_name(child.tag) == "num":
            return child.attrib.get("value")
    return None


def _direct_children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local_name(child.tag) == name]


def _normalized_text(element: ET.Element) -> str:
    text = " ".join(part.strip() for part in element.itertext() if part.strip())
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip()


def _deterministic_id(citation_path: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"axiom:{citation_path}"))


def _download_source() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    with urlopen(SOURCE_URL, timeout=60) as response:
        SOURCE_PATH.write_bytes(response.read())


def _source_sha256() -> str:
    return hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()


def _find_section_71119(root: ET.Element) -> ET.Element:
    for element in root.iter():
        if _local_name(element.tag) != "section":
            continue
        if element.attrib.get("identifier") == "/us/pl/119/21/tVII/stB/ch1/schD/s71119":
            return element
    msg = "Public Law 119-21 section 71119 not found in GovInfo USLM source"
    raise RuntimeError(msg)


def _find_quoted_xx_subsection(section_71119: ET.Element) -> ET.Element:
    for quoted in section_71119.iter():
        if _local_name(quoted.tag) != "quotedContent":
            continue
        for element in quoted.iter():
            if _local_name(element.tag) == "subsection" and _num_value(element) == "xx":
                return element
    msg = "Quoted 42 U.S.C. 1396a(xx) subsection not found in section 71119"
    raise RuntimeError(msg)


def _record(
    *,
    citation_path: str,
    body: str,
    kind: str,
    level: int,
    ordinal: int,
    heading: str | None,
    source_id: str,
    identifiers: dict[str, str],
    metadata: dict[str, object],
    source_hash: str,
    parent_citation_path: str | None,
) -> dict[str, object]:
    return {
        "body": body,
        "citation_label": identifiers["legal_identifier"],
        "citation_path": citation_path,
        "document_class": "statute",
        "expression_date": EXPRESSION_DATE,
        "heading": heading,
        "id": _deterministic_id(citation_path),
        "identifiers": identifiers,
        "jurisdiction": "us",
        "kind": kind,
        "language": "en",
        "legal_identifier": identifiers["legal_identifier"],
        "level": level,
        "metadata": metadata,
        "ordinal": ordinal,
        "parent_citation_path": parent_citation_path,
        "parent_id": _deterministic_id(parent_citation_path)
        if parent_citation_path
        else None,
        "source_as_of": SOURCE_AS_OF,
        "source_format": "uslm-xml",
        "source_id": source_id,
        "source_path": str(SOURCE_PATH.relative_to(ROOT)),
        "source_sha256": source_hash,
        "source_url": SOURCE_URL,
        "version": VERSION,
    }


def _metadata(
    *,
    identifier: str,
    kind: str,
    heading: str | None,
    paragraph: str | None = None,
    parent_citation_path: str | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "created_date": EXPRESSION_DATE,
        "heading": heading,
        "identifier": identifier,
        "kind": kind,
        "parent_citation_path": parent_citation_path,
        "publication_name": "Public Law 119-21",
        "public_law": "119-21",
        "references_to": [
            "us/statute/26/45R",
            "us/statute/29/206",
            "us/statute/42/1315",
            "us/statute/42/1396a",
        ],
        "section": "1396a",
        "section_heading": "State plans for medical assistance",
        "source_download_url": SOURCE_URL,
        "source_public_law_section": "71119(a)",
        "subsection": "xx",
        "title": "42",
        "title_heading": "THE PUBLIC HEALTH AND WELFARE",
    }
    if paragraph is not None:
        metadata["paragraph"] = paragraph
    return metadata


def _build_records(xx_subsection: ET.Element, source_hash: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    xx_path = "us/statute/42/1396a/xx"
    heading = "Community Engagement Requirement for Applicable Individuals"
    xx_identifier = "/us/usc/t42/s1396a/xx"
    records.append(
        _record(
            citation_path=xx_path,
            body=_normalized_text(xx_subsection),
            kind="subsection",
            level=2,
            ordinal=13961024,
            heading=heading,
            source_id="/us/pl/119/21/tVII/stB/ch1/schD/s71119/a/quoted/xx",
            identifiers={
                "legal_identifier": "42 U.S.C. \u00a7 1396a(xx)",
                "usc:section": "1396a",
                "usc:subsection": "xx",
                "usc:title": "42",
                "uslm:identifier": xx_identifier,
                "public-law:section": "71119(a)",
            },
            metadata=_metadata(
                identifier=xx_identifier,
                kind="subsection",
                heading=heading,
                parent_citation_path="us/statute/42/1396a",
            ),
            source_hash=source_hash,
            parent_citation_path="us/statute/42/1396a",
        )
    )

    for index, paragraph in enumerate(_direct_children(xx_subsection, "paragraph"), start=1):
        value = _num_value(paragraph)
        if not value:
            continue
        paragraph_heading = None
        for child in paragraph:
            if _local_name(child.tag) == "heading":
                paragraph_heading = _normalized_text(child)
                break
        citation_path = f"{xx_path}/{value}"
        identifier = f"{xx_identifier}/{value}"
        records.append(
            _record(
                citation_path=citation_path,
                body=_normalized_text(paragraph),
                kind="paragraph",
                level=3,
                ordinal=13961024000 + index,
                heading=paragraph_heading,
                source_id=(
                    "/us/pl/119/21/tVII/stB/ch1/schD/s71119/a/quoted/"
                    f"xx/{value}"
                ),
                identifiers={
                    "legal_identifier": f"42 U.S.C. \u00a7 1396a(xx)({value})",
                    "usc:paragraph": value,
                    "usc:section": "1396a",
                    "usc:subsection": "xx",
                    "usc:title": "42",
                    "uslm:identifier": identifier,
                    "public-law:section": "71119(a)",
                },
                metadata=_metadata(
                    identifier=identifier,
                    kind="paragraph",
                    heading=paragraph_heading,
                    paragraph=value,
                    parent_citation_path=xx_path,
                ),
                source_hash=source_hash,
                parent_citation_path=xx_path,
            )
        )
    return records


def _write_artifacts(records: list[dict[str, object]], source_hash: str) -> None:
    for path in (PROVISIONS_PATH, INVENTORY_PATH, COVERAGE_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)

    with PROVISIONS_PATH.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    inventory_items = [
        {
            "citation_path": record["citation_path"],
            "metadata": record["metadata"],
            "sha256": source_hash,
            "source_format": "uslm-xml",
            "source_path": str(SOURCE_PATH.relative_to(ROOT)),
            "source_url": SOURCE_URL,
        }
        for record in records
    ]
    INVENTORY_PATH.write_text(
        json.dumps({"items": inventory_items}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    COVERAGE_PATH.write_text(
        json.dumps(
            {
                "complete": True,
                "document_class": "statute",
                "duplicate_provision_citations": [],
                "duplicate_source_citations": [],
                "extra_provisions": [],
                "jurisdiction": "us",
                "matched_count": len(records),
                "missing_from_provisions": [],
                "provision_count": len(records),
                "source_count": len(records),
                "version": VERSION,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    _download_source()
    source_hash = _source_sha256()
    root = ET.parse(SOURCE_PATH).getroot()
    section_71119 = _find_section_71119(root)
    xx_subsection = _find_quoted_xx_subsection(section_71119)
    records = _build_records(xx_subsection, source_hash)
    _write_artifacts(records, source_hash)
    print(f"Wrote {len(records)} Public Law 119-21 Medicaid community engagement provisions.")
    print(PROVISIONS_PATH.relative_to(ROOT))


if __name__ == "__main__":
    main()
