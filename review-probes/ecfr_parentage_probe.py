from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.ecfr import (
    EcfrPartTarget,
    _scoped_structure_from_part_xml,
    build_ecfr_inventory_from_structures,
    extract_ecfr,
    iter_ecfr_title_provisions,
    part_targets_from_structure,
)
from axiom_corpus.corpus.io import load_provisions


def section_parts(element: ET.Element) -> tuple[str, str] | None:
    match = re.search(
        r"([0-9A-Za-z]+)\.([0-9A-Za-z][0-9A-Za-z.-]*)",
        element.get("N", ""),
    )
    return match.groups() if match else None


def selected_source_parentage(
    xml_content: str,
    *,
    title: int,
    part: str,
    selectors: tuple[str, ...],
) -> tuple[dict[str, tuple[str, int]], dict[str, int]]:
    root = ET.fromstring(xml_content)
    part_element = next(
        element
        for element in root.iter("DIV5")
        if element.get("TYPE") == "PART" and element.get("N") == part
    )
    formal_subpart_by_section: dict[ET.Element, str] = {}
    formal_subpart_tags: Counter[str] = Counter()
    for child in part_element:
        if child.get("TYPE") != "SUBPART":
            continue
        formal_subpart_tags[child.tag] += 1
        subpart = child.get("N")
        if subpart is None:
            continue
        for section in child.iter():
            if section.get("TYPE") == "SECTION" and section_parts(section):
                formal_subpart_by_section[section] = subpart

    requested = set(selectors)
    result: dict[str, tuple[str, int]] = {}
    for section in part_element.iter():
        if section.get("TYPE") != "SECTION":
            continue
        parsed = section_parts(section)
        if parsed is None:
            continue
        actual_part, number = parsed
        selector = f"{actual_part}.{number}"
        if selector not in requested:
            continue
        citation_path = f"us/regulation/{title}/{actual_part}/{number}"
        subpart = formal_subpart_by_section.get(section)
        if subpart is None:
            result[citation_path] = (f"us/regulation/{title}/{actual_part}", 1)
        else:
            result[citation_path] = (
                f"us/regulation/{title}/{actual_part}/subpart-{subpart}",
                2,
            )
    return result, dict(formal_subpart_tags)


def case_result(
    xml_path: Path,
    *,
    title: int,
    part: str,
    selectors: tuple[str, ...],
    run_extract: bool,
) -> dict[str, object]:
    source_bytes = xml_path.read_bytes()
    xml_content = source_bytes.decode("utf-8")
    source_parentage, formal_subpart_tags = selected_source_parentage(
        xml_content,
        title=title,
        part=part,
        selectors=selectors,
    )
    structure = _scoped_structure_from_part_xml(
        xml_content,
        title=title,
        part=part,
        only_sections=selectors,
    )
    inventory = build_ecfr_inventory_from_structures(
        (structure,),
        only_part=part,
        only_sections=selectors,
        run_id="round4-parentage-probe",
    )
    inventory_paths = [item.citation_path for item in inventory.items]
    inventory_parentage = {
        item.citation_path: (
            (item.metadata or {}).get("parent_citation_path"),
            2 if (item.metadata or {}).get("subpart") else 1,
        )
        for item in inventory.items
        if (item.metadata or {}).get("kind") == "section"
    }
    targets = part_targets_from_structure(structure)
    records = tuple(
        iter_ecfr_title_provisions(
            xml_content,
            targets,
            version="round4-parentage-probe",
            source_path=str(xml_path),
            source_as_of="2026-07-27",
            expression_date="2026-07-27",
            allowed_citation_paths=set(inventory_paths),
        )
    )
    record_parentage = {
        record.citation_path: (record.parent_citation_path, record.level)
        for record in records
        if record.kind == "section"
    }
    result: dict[str, object] = {
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "title": title,
        "part": part,
        "selectors": selectors,
        "formal_subpart_tags": formal_subpart_tags,
        "source_parentage": source_parentage,
        "inventory_paths": inventory_paths,
        "inventory_parentage": inventory_parentage,
        "record_paths": [record.citation_path for record in records],
        "record_parentage": record_parentage,
        "inventory_matches_source": inventory_parentage == source_parentage,
        "records_match_source": record_parentage == source_parentage,
        "missing_iterator_sections": sorted(set(source_parentage) - set(record_parentage)),
        "dangling_iterator_parents": sorted(
            {
                parent
                for parent, _level in record_parentage.values()
                if parent not in inventory_paths
            }
        ),
    }

    if run_extract:
        with tempfile.TemporaryDirectory(prefix="pr523-r4-ecfr-extract-") as temp_dir:
            report = extract_ecfr(
                CorpusArtifactStore(Path(temp_dir) / "corpus"),
                version="round4-parentage-probe",
                as_of="2026-07-27",
                expression_date=date(2026, 7, 27),
                source_xml=xml_path,
                only_title=title,
                only_part=part,
                only_sections=selectors,
                workers=1,
            )
            extracted = load_provisions(report.provisions_path)
            result["extract_coverage_complete"] = report.coverage.complete
            result["extract_records"] = [
                {
                    "citation_path": record.citation_path,
                    "parent_citation_path": record.parent_citation_path,
                    "level": record.level,
                    "body_is_none": record.body is None,
                    "body_status": (record.metadata or {}).get("body_status"),
                    "structure_only": (record.metadata or {}).get("structure_only"),
                }
                for record in extracted
            ]
    return result


def retained_scan(source_root: Path) -> dict[str, object]:
    file_results: list[dict[str, object]] = []
    source_section_occurrences = 0
    source_section_paths: set[str] = set()
    inventory_section_paths: set[str] = set()
    iterator_section_paths: set[str] = set()
    missing: list[dict[str, str]] = []
    inventory_parent_mismatches: list[dict[str, object]] = []
    iterator_parent_mismatches: list[dict[str, object]] = []
    formal_subpart_tags: Counter[str] = Counter()
    parts_without_subparts = 0
    parts_with_mixed_direct_sections = 0

    for xml_path in sorted(source_root.glob("*/ecfr/title-*-part-*.xml")):
        match = re.fullmatch(r"title-(\d+)-part-([0-9A-Za-z]+)\.xml", xml_path.name)
        if match is None:
            continue
        title = int(match.group(1))
        part = match.group(2)
        xml_content = xml_path.read_text()
        root = ET.fromstring(xml_content)
        part_element = next(
            element
            for element in root.iter("DIV5")
            if element.get("TYPE") == "PART" and element.get("N") == part
        )
        selectors = tuple(
            dict.fromkeys(
                f"{actual_part}.{section}"
                for element in part_element.iter()
                if element.get("TYPE") == "SECTION"
                and (parsed := section_parts(element)) is not None
                for actual_part, section in (parsed,)
            )
        )
        source_section_occurrences += len(selectors)
        source_parentage, tags = selected_source_parentage(
            xml_content,
            title=title,
            part=part,
            selectors=selectors,
        )
        formal_subpart_tags.update(tags)
        source_section_paths.update(source_parentage)
        has_subparts = bool(tags)
        if not has_subparts:
            parts_without_subparts += 1
        direct_section_count = sum(
            1
            for parent, _level in source_parentage.values()
            if parent == f"us/regulation/{title}/{part}"
        )
        if has_subparts and direct_section_count:
            parts_with_mixed_direct_sections += 1

        structure = _scoped_structure_from_part_xml(
            xml_content,
            title=title,
            part=part,
            only_sections=selectors,
        )
        inventory = build_ecfr_inventory_from_structures(
            (structure,),
            only_part=part,
            only_sections=selectors,
            run_id="round4-retained-scan",
        )
        inventory_paths = [item.citation_path for item in inventory.items]
        inventory_parentage = {
            item.citation_path: (
                (item.metadata or {}).get("parent_citation_path"),
                2 if (item.metadata or {}).get("subpart") else 1,
            )
            for item in inventory.items
            if (item.metadata or {}).get("kind") == "section"
        }
        inventory_section_paths.update(inventory_parentage)
        targets = part_targets_from_structure(structure)
        records = tuple(
            iter_ecfr_title_provisions(
                xml_content,
                targets,
                version="round4-retained-scan",
                source_path=str(xml_path),
                source_as_of="2026-07-27",
                expression_date="2026-07-27",
                allowed_citation_paths=set(inventory_paths),
            )
        )
        record_parentage = {
            record.citation_path: (record.parent_citation_path, record.level)
            for record in records
            if record.kind == "section"
        }
        iterator_section_paths.update(record_parentage)
        for path, expected in source_parentage.items():
            if inventory_parentage.get(path) != expected:
                inventory_parent_mismatches.append(
                    {
                        "file": str(xml_path),
                        "path": path,
                        "expected": expected,
                        "actual": inventory_parentage.get(path),
                    }
                )
            if path not in record_parentage:
                missing.append({"file": str(xml_path), "path": path})
            elif record_parentage[path] != expected:
                iterator_parent_mismatches.append(
                    {
                        "file": str(xml_path),
                        "path": path,
                        "expected": expected,
                        "actual": record_parentage[path],
                    }
                )
        file_results.append(
            {
                "file": str(xml_path),
                "source_sections": len(source_parentage),
                "inventory_sections": len(inventory_parentage),
                "iterator_sections": len(record_parentage),
            }
        )

    return {
        "xml_file_count": len(file_results),
        "source_section_occurrences": source_section_occurrences,
        "source_unique_section_paths": len(source_section_paths),
        "inventory_unique_section_paths": len(inventory_section_paths),
        "iterator_unique_section_paths": len(iterator_section_paths),
        "formal_subpart_tags": dict(formal_subpart_tags),
        "parts_without_subparts": parts_without_subparts,
        "parts_with_mixed_direct_sections": parts_with_mixed_direct_sections,
        "missing_iterator_sections": missing,
        "inventory_parent_mismatches": inventory_parent_mismatches,
        "iterator_parent_mismatches": iterator_parent_mismatches,
        "file_results": file_results,
    }


def synthetic_result() -> dict[str, object]:
    fixtures = {
        "non_div6_subpart": """
<ECFR><DIV5 N="9" TYPE="PART"><HEAD>Part 9</HEAD>
<DIV7 N="Q" TYPE="SUBPART"><HEAD>Subpart Q</HEAD>
<DIV8 N="9.1" TYPE="SECTION"><HEAD>§ 9.1 One.</HEAD><P>Body.</P></DIV8>
</DIV7></DIV5></ECFR>""",
        "part_without_subparts": """
<ECFR><DIV5 N="10" TYPE="PART"><HEAD>Part 10</HEAD>
<DIV6 N="Topic" TYPE="SUBJGRP"><HEAD>Topic</HEAD>
<DIV8 N="10.1" TYPE="SECTION"><HEAD>§ 10.1 One.</HEAD><P>Body.</P></DIV8>
</DIV6></DIV5></ECFR>""",
        "unselected_subpart": """
<ECFR><DIV5 N="11" TYPE="PART"><HEAD>Part 11</HEAD>
<DIV6 N="A" TYPE="SUBPART"><HEAD>Subpart A</HEAD>
<DIV8 N="11.1" TYPE="SECTION"><HEAD>§ 11.1 One.</HEAD><P>Body.</P></DIV8>
</DIV6>
<DIV6 N="B" TYPE="SUBPART"><HEAD>Subpart B</HEAD>
<DIV8 N="11.2" TYPE="SECTION"><HEAD>§ 11.2 Two.</HEAD><P>Body.</P></DIV8>
</DIV6></DIV5></ECFR>""",
    }
    cases = (
        ("non_div6_subpart", 9, "9", ("9.1",)),
        ("part_without_subparts", 10, "10", ("10.1",)),
        ("unselected_subpart", 11, "11", ("11.1",)),
    )
    result: dict[str, object] = {}
    for name, title, part, selectors in cases:
        xml_content = fixtures[name]
        structure = _scoped_structure_from_part_xml(
            xml_content,
            title=title,
            part=part,
            only_sections=selectors,
        )
        inventory = build_ecfr_inventory_from_structures(
            (structure,),
            only_part=part,
            only_sections=selectors,
            run_id="round4-synthetic",
        )
        inventory_paths = [item.citation_path for item in inventory.items]
        records = tuple(
            iter_ecfr_title_provisions(
                xml_content,
                (EcfrPartTarget(title=title, part=part),),
                version="round4-synthetic",
                source_path=f"synthetic-{name}.xml",
                allowed_citation_paths=set(inventory_paths),
            )
        )
        result[name] = {
            "inventory_paths": inventory_paths,
            "record_paths": [record.citation_path for record in records],
            "section_parents": {
                record.citation_path: record.parent_citation_path
                for record in records
                if record.kind == "section"
            },
        }
    return result


def with_digest(result: dict[str, object]) -> dict[str, object]:
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    return {"result_sha256": hashlib.sha256(canonical).hexdigest(), **result}


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    case_parser = subparsers.add_parser("case")
    case_parser.add_argument("xml_path", type=Path)
    case_parser.add_argument("--title", required=True, type=int)
    case_parser.add_argument("--part", required=True)
    case_parser.add_argument("--section", action="append", required=True)
    case_parser.add_argument("--extract", action="store_true")
    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("source_root", type=Path)
    subparsers.add_parser("synthetic")
    args = parser.parse_args()

    if args.mode == "case":
        result = case_result(
            args.xml_path,
            title=args.title,
            part=args.part,
            selectors=tuple(args.section),
            run_extract=args.extract,
        )
    elif args.mode == "scan":
        result = retained_scan(args.source_root)
    else:
        result = synthetic_result()
    print(json.dumps(with_digest(result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
