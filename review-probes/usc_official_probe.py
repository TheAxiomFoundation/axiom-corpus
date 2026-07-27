from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from gc import collect
from pathlib import Path
from xml.etree import ElementTree as ET

from axiom_corpus.corpus.usc import (
    UscNestedProvision,
    UscParagraph,
    UscSubsection,
    build_usc_inventory_from_xml,
    decode_uslm_bytes,
    iter_usc_title_provisions,
    parse_uslm_title,
)

STRUCTURAL_KINDS = {
    "title",
    "section",
    "subsection",
    "paragraph",
    "subparagraph",
    "clause",
    "subclause",
    "item",
    "subitem",
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def direct_text(element: ET.Element, child_name: str) -> str | None:
    for child in element:
        if local_name(child.tag) == child_name:
            text = " ".join(" ".join(child.itertext()).split())
            return text or None
    return None


def source_path(identifier: str) -> str:
    if identifier == "/us/usc/t26":
        return "us/statute/26"
    prefix = "/us/usc/t26/s"
    if not identifier.startswith(prefix):
        raise AssertionError(identifier)
    return "us/statute/26/" + identifier.removeprefix(prefix)


def walk_with_depth(element: ET.Element, depth: int = 0):
    yield element, depth
    for child in element:
        yield from walk_with_depth(child, depth + 1)


def sibling_groups(root: ET.Element, attr: str):
    groups: list[dict[str, object]] = []
    for parent in root.iter():
        by_value: dict[str, list[ET.Element]] = defaultdict(list)
        for child in parent:
            if local_name(child.tag) not in STRUCTURAL_KINDS:
                continue
            value = child.get(attr)
            if value:
                by_value[value].append(child)
        for value, siblings in by_value.items():
            if len(siblings) < 2:
                continue
            groups.append(
                {
                    "parent_identifier": parent.get("identifier"),
                    "parent_kind": local_name(parent.tag),
                    "attribute": attr,
                    "value": value,
                    "size": len(siblings),
                    "children": [
                        {
                            "kind": local_name(child.tag),
                            "identifier": child.get("identifier"),
                            "id": child.get("id"),
                            "num": direct_text(child, "num"),
                            "heading": direct_text(child, "heading"),
                            "status": child.get("status"),
                            "class": child.get("class"),
                        }
                        for child in siblings
                    ],
                }
            )
    return groups


def numbered_sibling_groups(root: ET.Element):
    groups: list[dict[str, object]] = []
    for parent in root.iter():
        by_number: dict[tuple[str, str], list[ET.Element]] = defaultdict(list)
        for child in parent:
            kind = local_name(child.tag)
            if kind not in STRUCTURAL_KINDS:
                continue
            number = direct_text(child, "num")
            if number:
                by_number[(kind, number)].append(child)
        for (kind, number), siblings in by_number.items():
            if len(siblings) < 2:
                continue
            groups.append(
                {
                    "parent_identifier": parent.get("identifier"),
                    "parent_kind": local_name(parent.tag),
                    "kind": kind,
                    "number": number,
                    "size": len(siblings),
                    "identifiers": [child.get("identifier") for child in siblings],
                    "ids": [child.get("id") for child in siblings],
                    "headings": [direct_text(child, "heading") for child in siblings],
                    "statuses": [child.get("status") for child in siblings],
                    "classes": [child.get("class") for child in siblings],
                }
            )
    return groups


def parsed_nodes(document):
    result: list[tuple[str, str, str | None]] = [
        ("title", document.citation_path, f"/us/usc/t{document.title}")
    ]

    def nested(provision: UscNestedProvision):
        result.append((provision.kind, provision.citation_path, provision.identifier))
        for child in provision.children:
            nested(child)

    def paragraph(provision: UscParagraph):
        result.append(("paragraph", provision.citation_path, provision.identifier))
        for child in provision.children:
            nested(child)

    def subsection(provision: UscSubsection):
        result.append(("subsection", provision.citation_path, provision.identifier))
        for child in provision.descendants:
            if isinstance(child, UscParagraph):
                paragraph(child)
            else:
                nested(child)

    for section in document.sections:
        result.append(("section", section.citation_path, section.identifier))
        for child in section.descendants:
            if isinstance(child, UscSubsection):
                subsection(child)
            else:
                nested(child)
    return result


def forty_five_x(document):
    section = next(section for section in document.sections if section.section == "45X")
    subsection = next(
        child
        for child in section.descendants
        if isinstance(child, UscSubsection) and child.label == "d"
    )
    paragraphs = [
        child
        for child in subsection.descendants
        if isinstance(child, UscParagraph) and child.label == "4"
    ]

    def descendants(provision):
        for child in provision.children:
            yield child.kind, child.identifier, child.citation_path
            yield from descendants(child)

    return [
        {
            "identifier": paragraph.identifier,
            "heading": paragraph.heading,
            "body_prefix": paragraph.body[:120],
            "descendants": list(descendants(paragraph)),
        }
        for paragraph in paragraphs
    ]


def main() -> None:
    xml_path = Path(sys.argv[1])
    source_bytes = xml_path.read_bytes()
    source_text = decode_uslm_bytes(source_bytes)
    root = ET.fromstring(source_text)
    source_nodes = [
        (element, depth)
        for element, depth in walk_with_depth(root)
        if local_name(element.tag) in STRUCTURAL_KINDS
        and (element.get("identifier") or "").startswith("/us/usc/t26")
    ]
    source_identifiers = [
        identifier
        for element, _ in source_nodes
        if (identifier := element.get("identifier")) is not None
    ]
    unique_source_identifiers = dict.fromkeys(source_identifiers)
    source_kind_by_identifier: dict[str, str] = {}
    for element, _ in source_nodes:
        identifier = element.get("identifier")
        if identifier is not None:
            source_kind_by_identifier.setdefault(identifier, local_name(element.tag))
    expected_paths = {source_path(identifier) for identifier in unique_source_identifiers}
    identifier_occurrences = Counter(source_identifiers)
    duplicate_identifiers = {
        identifier: count for identifier, count in identifier_occurrences.items() if count > 1
    }
    global_source_ids = Counter(
        element.get("id") for element, _ in source_nodes if element.get("id")
    )
    identifier_sibling_groups = sibling_groups(root, "identifier")
    id_sibling_groups = sibling_groups(root, "id")
    number_groups = numbered_sibling_groups(root)
    source_kind_occurrences = Counter(local_name(element.tag) for element, _ in source_nodes)
    source_structural_occurrences = len(source_nodes)
    del root
    del source_nodes
    collect()

    document = parse_uslm_title(source_text)
    traversed = parsed_nodes(document)
    parsed_45x_d_4 = forty_five_x(document)
    del document
    collect()

    inventory = build_usc_inventory_from_xml(source_text)
    inventory_paths = [item.citation_path for item in inventory.items]
    del inventory
    collect()

    record_paths = [
        record.citation_path
        for record in iter_usc_title_provisions(
            source_text,
            version="round4-independent-probe",
            source_path="official-title-26/uslm/usc26.xml",
        )
    ]

    output = {
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_bytes": len(source_bytes),
        "source_structural_occurrences": source_structural_occurrences,
        "source_structural_unique_identifiers": len(unique_source_identifiers),
        "source_kind_occurrences": source_kind_occurrences,
        "source_kind_unique_identifiers": Counter(source_kind_by_identifier.values()),
        "duplicate_identifier_count": len(duplicate_identifiers),
        "duplicate_identifiers": duplicate_identifiers,
        "duplicate_global_source_id_count": sum(
            1 for count in global_source_ids.values() if count > 1
        ),
        "identifier_sibling_group_size_distribution": Counter(
            group["size"] for group in identifier_sibling_groups
        ),
        "id_sibling_group_size_distribution": Counter(group["size"] for group in id_sibling_groups),
        "number_sibling_group_size_distribution": Counter(group["size"] for group in number_groups),
        "identifier_sibling_groups": identifier_sibling_groups,
        "number_sibling_groups": number_groups,
        "traversed_structural_occurrences": len(traversed),
        "traversed_kind_occurrences": Counter(kind for kind, _, _ in traversed),
        "traversed_unique_paths": len({path for _, path, _ in traversed}),
        "inventory_count": len(inventory_paths),
        "inventory_unique_paths": len(set(inventory_paths)),
        "records_count": len(record_paths),
        "records_unique_paths": len(set(record_paths)),
        "expected_unique_paths": len(expected_paths),
        "inventory_exact_source_path_set": set(inventory_paths) == expected_paths,
        "records_exact_source_path_set": set(record_paths) == expected_paths,
        "inventory_records_same_order": inventory_paths == record_paths,
        "source_paths_missing_inventory": sorted(expected_paths - set(inventory_paths))[:50],
        "inventory_paths_not_source": sorted(set(inventory_paths) - expected_paths)[:50],
        "parsed_45x_d_4": parsed_45x_d_4,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
