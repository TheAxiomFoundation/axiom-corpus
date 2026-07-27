from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from axiom_corpus.corpus.ecfr import EcfrPartTarget, iter_ecfr_title_provisions


def section_parts(element: ET.Element) -> tuple[str, str] | None:
    match = re.search(
        r"([0-9A-Za-z]+)\.([0-9A-Za-z][0-9A-Za-z.-]*)",
        element.get("N", ""),
    )
    return match.groups() if match else None


def section_entry(
    element: ET.Element,
    *,
    title: int,
    parent: str,
    placement: str,
) -> dict[str, object] | None:
    parsed = section_parts(element)
    if parsed is None:
        return None
    part, section = parsed
    return {
        "kind": "section",
        "path": f"us/regulation/{title}/{part}/{section}",
        "parent": parent,
        "placement": placement,
    }


def source_entries(xml_content: str, *, title: int, part: str) -> list[dict[str, object]]:
    root = ET.fromstring(xml_content)
    part_element = next(
        element
        for element in root.iter("DIV5")
        if element.get("TYPE") == "PART" and element.get("N") == part
    )
    part_path = f"us/regulation/{title}/{part}"
    entries: list[dict[str, object]] = [
        {
            "kind": "part",
            "path": part_path,
            "parent": None,
            "placement": "part",
        }
    ]
    for child in part_element:
        if child.tag == "DIV6" and child.get("TYPE") == "SUBPART":
            subpart = child.get("N")
            if not subpart:
                continue
            subpart_path = f"{part_path}/subpart-{subpart}"
            entries.append(
                {
                    "kind": "subpart",
                    "path": subpart_path,
                    "parent": part_path,
                    "placement": "subpart",
                }
            )
            for section in child.iter("DIV8"):
                if section.get("TYPE") != "SECTION":
                    continue
                entry = section_entry(
                    section,
                    title=title,
                    parent=subpart_path,
                    placement=f"subpart-{subpart}",
                )
                if entry is not None:
                    entries.append(entry)
            continue

        for section in child.iter("DIV8"):
            if section.get("TYPE") != "SECTION":
                continue
            entry = section_entry(
                section,
                title=title,
                parent=part_path,
                placement="part-direct",
            )
            if entry is not None:
                entries.append(entry)
    return entries


def adapter_entries(xml_content: str, *, title: int, part: str) -> list[dict[str, object]]:
    records = tuple(
        iter_ecfr_title_provisions(
            xml_content,
            (EcfrPartTarget(title=title, part=part),),
            version="round6-delta-adversarial",
            source_path="synthetic.xml",
        )
    )
    return [
        {
            "kind": record.kind,
            "path": record.citation_path,
            "parent": record.parent_citation_path,
            "placement": (
                f"subpart-{(record.metadata or {}).get('subpart')}"
                if record.kind == "section" and (record.metadata or {}).get("subpart")
                else "part-direct"
                if record.kind == "section"
                else record.kind
            ),
            "body_present": record.body is not None if record.kind == "section" else None,
        }
        for record in records
    ]


def comparable(entry: dict[str, object]) -> tuple[object, object, object, object]:
    return (
        entry["kind"],
        entry["path"],
        entry["parent"],
        entry["placement"],
    )


def case_result(xml_content: str, *, title: int, part: str) -> dict[str, object]:
    source = source_entries(xml_content, title=title, part=part)
    adapter = adapter_entries(xml_content, title=title, part=part)
    source_comparable = [comparable(entry) for entry in source]
    adapter_comparable = [comparable(entry) for entry in adapter]
    return {
        "source_entries": source,
        "adapter_entries": adapter,
        "same_entries": Counter(source_comparable) == Counter(adapter_comparable),
        "same_document_order": source_comparable == adapter_comparable,
        "all_section_bodies_present": all(
            entry["body_present"]
            for entry in adapter
            if entry["kind"] == "section"
        ),
        "duplicate_adapter_paths": sorted(
            path
            for path, count in Counter(entry["path"] for entry in adapter).items()
            if count > 1
        ),
    }


def retained_census(source_root: Path) -> dict[str, object]:
    mixed_parts: list[str] = []
    only_direct_parts: list[str] = []
    direct_after_subpart: list[dict[str, object]] = []
    empty_subparts: list[dict[str, object]] = []
    reserved_empty_subparts: list[dict[str, object]] = []
    cross_placement_duplicates: list[dict[str, object]] = []
    xml_files = sorted(source_root.glob("*/ecfr/title-*-part-*.xml"))

    for xml_path in xml_files:
        name_match = re.fullmatch(
            r"title-(\d+)-part-([0-9A-Za-z]+)\.xml",
            xml_path.name,
        )
        if name_match is None:
            continue
        title = int(name_match.group(1))
        part = name_match.group(2)
        root = ET.fromstring(xml_path.read_text())
        part_element = next(
            element
            for element in root.iter("DIV5")
            if element.get("TYPE") == "PART" and element.get("N") == part
        )
        descriptor = f"{title} CFR part {part} @ {xml_path}"
        placements: dict[str, list[str]] = defaultdict(list)
        formal_subparts_seen = 0
        formal_subpart_count = 0
        direct_section_count = 0

        for child_index, child in enumerate(part_element):
            if child.tag == "DIV6" and child.get("TYPE") == "SUBPART":
                formal_subpart_count += 1
                formal_subparts_seen += 1
                sections = [
                    section
                    for section in child.iter("DIV8")
                    if section.get("TYPE") == "SECTION"
                    and section_parts(section) is not None
                ]
                subpart = child.get("N")
                if not sections:
                    heading = " ".join(
                        "".join((child.find("HEAD") or child).itertext()).split()
                    )
                    row = {
                        "part": descriptor,
                        "subpart": subpart,
                        "heading": heading,
                        "child_index": child_index,
                    }
                    empty_subparts.append(row)
                    if "reserved" in heading.lower():
                        reserved_empty_subparts.append(row)
                for section in sections:
                    actual_part, number = section_parts(section) or ("", "")
                    path = f"us/regulation/{title}/{actual_part}/{number}"
                    placements[path].append(f"subpart-{subpart}")
                continue

            direct_sections = [
                section
                for section in child.iter("DIV8")
                if section.get("TYPE") == "SECTION"
                and section_parts(section) is not None
            ]
            for section in direct_sections:
                direct_section_count += 1
                actual_part, number = section_parts(section) or ("", "")
                path = f"us/regulation/{title}/{actual_part}/{number}"
                placements[path].append("part-direct")
                if formal_subparts_seen:
                    direct_after_subpart.append(
                        {
                            "part": descriptor,
                            "path": path,
                            "child_index": child_index,
                            "prior_formal_subparts": formal_subparts_seen,
                        }
                    )

        if formal_subpart_count and direct_section_count:
            mixed_parts.append(descriptor)
        if not formal_subpart_count and direct_section_count:
            only_direct_parts.append(descriptor)
        for path, path_placements in placements.items():
            if "part-direct" in path_placements and any(
                placement.startswith("subpart-") for placement in path_placements
            ):
                cross_placement_duplicates.append(
                    {
                        "part": descriptor,
                        "path": path,
                        "placements": path_placements,
                    }
                )

    return {
        "xml_file_count": len(xml_files),
        "mixed_parts": mixed_parts,
        "only_direct_parts": only_direct_parts,
        "direct_sections_after_formal_subparts": direct_after_subpart,
        "empty_formal_subparts": empty_subparts,
        "reserved_empty_formal_subparts": reserved_empty_subparts,
        "duplicate_section_paths_across_direct_and_subpart": cross_placement_duplicates,
    }


def main() -> None:
    fixtures = {
        "direct_after_subpart": (
            900,
            "900",
            """
<ECFR><DIV5 N="900" TYPE="PART"><HEAD>Part 900</HEAD>
<DIV6 N="A" TYPE="SUBPART"><HEAD>Subpart A</HEAD>
<DIV8 N="900.1" TYPE="SECTION"><HEAD>§ 900.1 One.</HEAD><P>One body.</P></DIV8>
</DIV6>
<DIV8 N="900.2" TYPE="SECTION"><HEAD>§ 900.2 Two.</HEAD><P>Two body.</P></DIV8>
<DIV6 N="B" TYPE="SUBPART"><HEAD>Subpart B</HEAD>
<DIV8 N="900.3" TYPE="SECTION"><HEAD>§ 900.3 Three.</HEAD><P>Three body.</P></DIV8>
</DIV6></DIV5></ECFR>
""",
        ),
        "reserved_and_empty_subparts": (
            901,
            "901",
            """
<ECFR><DIV5 N="901" TYPE="PART"><HEAD>Part 901</HEAD>
<DIV6 N="R" TYPE="SUBPART"><HEAD>Subpart R—[Reserved]</HEAD></DIV6>
<DIV6 N="E" TYPE="SUBPART"><HEAD>Subpart E—Empty</HEAD></DIV6>
<DIV8 N="901.1" TYPE="SECTION"><HEAD>§ 901.1 One.</HEAD><P>Body.</P></DIV8>
</DIV5></ECFR>
""",
        ),
        "only_direct_sections": (
            902,
            "902",
            """
<ECFR><DIV5 N="902" TYPE="PART"><HEAD>Part 902</HEAD>
<DIV6 N="Topic" TYPE="SUBJGRP"><HEAD>Topic</HEAD>
<DIV8 N="902.1" TYPE="SECTION"><HEAD>§ 902.1 One.</HEAD><P>One body.</P></DIV8>
</DIV6>
<DIV8 N="902.2" TYPE="SECTION"><HEAD>§ 902.2 Two.</HEAD><P>Two body.</P></DIV8>
</DIV5></ECFR>
""",
        ),
        "duplicate_cross_placement": (
            903,
            "903",
            """
<ECFR><DIV5 N="903" TYPE="PART"><HEAD>Part 903</HEAD>
<DIV6 N="A" TYPE="SUBPART"><HEAD>Subpart A</HEAD>
<DIV8 N="903.1" TYPE="SECTION"><HEAD>§ 903.1 Subpart.</HEAD><P>Subpart body.</P></DIV8>
</DIV6>
<DIV8 N="903.1" TYPE="SECTION"><HEAD>§ 903.1 Direct.</HEAD><P>Direct body.</P></DIV8>
</DIV5></ECFR>
""",
        ),
    }
    cases = {
        name: case_result(xml, title=title, part=part)
        for name, (title, part, xml) in fixtures.items()
    }
    result: dict[str, Any] = {
        "cases": cases,
        "retained_census": retained_census(Path(sys.argv[1])),
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    print(
        json.dumps(
            {
                "result_sha256": hashlib.sha256(canonical).hexdigest(),
                **result,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
