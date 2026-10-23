"""Opt-in amendment markers, checked against retained PCO XML and release rows.

The ordinary NZ extractor is deliberately unchanged. This module's command
re-extracts a predecessor scope before enriching its rows; it makes no captures.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NoReturn
from xml.etree import ElementTree as ET

import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.nz_legislation import extract_nz_legislation
from axiom_corpus.corpus.releases import ReleaseManifest

BASE_VERSION = "2026-10-20-rulespec-nz-pco"
VERSION = "2026-10-23-rulespec-nz-pco"
SOURCE_SHA256 = "aa6b16470e1302a80503a5a8fb44ea40159081cd234c731cad672652b5545f52"
_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
_LONG_DATE = r"([0-9]{1,2} [A-Z][a-z]+ [0-9]{4})"


def _text(element: ET.Element | None) -> str:
    return " ".join(" ".join(element.itertext()).split()) if element is not None else ""


def _fail(row: str, message: str) -> NoReturn:
    raise ValueError(f"{row}: {message}")


def _iso_date(long_date: str) -> str:
    day, month, year = long_date.split()
    return date(int(year), _MONTHS.index(month) + 1, int(day)).isoformat()


def _by_path(rows: Sequence[ProvisionRecord]) -> dict[str, ProvisionRecord]:
    result: dict[str, ProvisionRecord] = {}
    for row in rows:
        if row.citation_path in result:
            _fail(row.citation_path, "duplicate row")
        result[row.citation_path] = row
    return result


def _part_dates(root: ET.Element, commencement: ProvisionRecord) -> dict[str, str]:
    """Read operative subprovisions, never date.first.valid on a Part."""
    citation = commencement.citation_path
    element_id = (commencement.identifiers or {}).get("legislation.govt.nz:provision")
    element = root.find(f".//prov[@id='{element_id}']")
    if element is None:
        _fail(citation, "commencement XML element missing")
    statements = element.findall("./prov.body/subprov/para/text")
    dates: dict[str, str] = {}
    for statement_element in statements:
        statement = _text(statement_element)
        general = re.fullmatch(rf"This Act comes into force on {_LONG_DATE}\.", statement)
        exception = re.fullmatch(
            rf"However, Part ([0-9]+) comes into force on {_LONG_DATE}\.", statement
        )
        if general:
            key, long_date = "act", general[1]
        elif exception:
            key, long_date = exception[1], exception[2]
            part = root.find(f"./body/part[label='{key}']")
            references = statement_element.findall(".//intref")
            if part is None or len(references) != 1 or references[0].get("href") != part.get("id"):
                _fail(citation, "commencement exception does not link to its XML Part")
        else:
            _fail(citation, f"unsupported commencement statement: {statement!r}")
        if key in dates or statement not in " ".join((commencement.body or "").split()):
            _fail(citation, f"duplicate binding or missing English date {long_date}")
        try:
            dates[key] = _iso_date(long_date)
        except ValueError:
            _fail(citation, f"invalid English date {long_date}")
    if "act" not in dates:
        _fail(citation, "Act commencement date missing")
    return dates


def _principal(
    root: ET.Element,
    document: ProvisionRecord,
    rows: Mapping[str, ProvisionRecord],
    principal_rows: Sequence[ProvisionRecord],
) -> ProvisionRecord:
    citation = f"{document.citation_path}/section/3"
    section = rows.get(citation)
    element = root.find("./body/prov[label='3']")
    references = element.findall("./prov.body//leg-title") if element is not None else []
    if root.tag != "act" or not list(root.iter("amend")) or len(references) != 1:
        _fail(citation, "XML does not identify one amending Act and principal")
    reference = references[0]
    name = _text(reference)
    statement = f"This Act amends the {name} ."
    if (
        section is None
        or " ".join((section.body or "").split()) != statement
        or _text(element.find("prov.body") if element is not None else None) != statement
    ):
        _fail(citation, "row does not name the XML principal Act")
    candidates = [
        row
        for row in principal_rows
        if row.kind == "document"
        and (row.identifiers or {}).get("legislation.govt.nz:id") == reference.get("href")
        and " ".join((row.heading or "").split()) == name
        and (row.metadata or {}).get("stage") == "in-force"
    ]
    if len(candidates) != 1:
        _fail(citation, "XML principal href/title must resolve to one active release document")
    return candidates[0]


def _target_values(value: Any, citation: str) -> list[str]:
    targets = [value] if isinstance(value, str) else value
    if (
        not isinstance(targets, list)
        or not targets
        or any(not isinstance(target, str) for target in targets)
        or len(set(targets)) != len(targets)
    ):
        _fail(citation, "targets must be a nonempty unique string or list")
    return list(targets)


def _check_target(row: ProvisionRecord, target: ProvisionRecord, suffix: str) -> None:
    """Bind the target to the operative subject, not an incidental cross-reference."""
    citation = row.citation_path
    match = re.fullmatch(
        r"(section|schedule)/([0-9]+[A-Za-z]*)(/part/([0-9]+)/clause/([^/]+))?", suffix
    )
    if not match:
        _fail(citation, f"unsupported target {suffix}")
    kind, number = match[1], match[2]
    heading = " ".join((row.heading or "").split())
    subject = re.match(r"(Section|Schedule) ([0-9]+[A-Za-z]*) amended\b", heading)
    if subject is None or subject[1].lower() != kind or subject[2] != number:
        _fail(citation, f"target {suffix} is not the heading's amended provision")
    if match[3]:
        # The retained principal represents the whole Part 7 table as one
        # unlabelled provision. Check both its XML ID and replaced table rows.
        part, token = match[4], match[5]
        body = row.body or ""
        replacement = re.match(
            rf"In Schedule {number}\s*, Part {part}, replace clauses ([0-9A-Z]+) to ([0-9A-Z]+) with:",
            body,
        )
        identifier = (target.identifiers or {}).get("legislation.govt.nz:provision", "")
        if replacement is None or identifier.lower() != token:
            _fail(citation, f"target {suffix} does not identify the replaced table")
        first, last = replacement[1], replacement[2]
        labels = set(re.findall(r"^([0-9]+[A-Z]*)\s*\|", target.body or "", re.MULTILINE))
        first_number = int(first.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        last_number = int(last.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        expected = {first, last, *map(str, range(first_number, last_number + 1))}
        if not expected <= labels:
            _fail(citation, f"target {suffix} lacks replaced clauses {sorted(expected - labels)}")


def enrich_amendment_rows(
    raw_xml: bytes,
    rows: Sequence[ProvisionRecord],
    principal_rows: Sequence[ProvisionRecord],
    overlay: dict[str, Any],
) -> list[ProvisionRecord]:
    """Return metadata-only copies; reject unverified or incomplete routing claims."""
    by_path = _by_path(rows)
    documents = [row for row in rows if row.kind == "document"]
    if len(documents) != 1:
        _fail("nz/statute", "expected exactly one amendment document")
    document = documents[0]
    path = document.citation_path
    root = ET.fromstring(raw_xml)
    if (document.identifiers or {}).get("legislation.govt.nz:id") != root.get("id"):
        _fail(path, "document XML ID mismatch")
    principal = _principal(root, document, by_path, principal_rows)
    principal_by_path = _by_path(principal_rows)
    commencement_path = f"{path}/section/2"
    if commencement_path not in by_path:
        _fail(commencement_path, "commencement row missing")
    dates = _part_dates(root, by_path[commencement_path])
    if (
        not isinstance(overlay, dict)
        or set(overlay) != {"targets", "insertions"}
        or not isinstance(overlay["targets"], dict)
    ):
        _fail(path, "overlay must contain only targets and insertions")
    targets = overlay["targets"]
    for suffix in targets:
        if not isinstance(suffix, str) or not re.fullmatch(r"section/[0-9]+", suffix):
            _fail(f"{path}/{suffix}", "overlay target key must identify an amending section")
    insertions = overlay["insertions"]
    if not isinstance(insertions, list) or any(not isinstance(v, str) for v in insertions):
        _fail(path, "insertions must be a list of section paths")
    if len(set(insertions)) != len(insertions) or set(targets) & set(insertions):
        _fail(path, "duplicate or overlapping overlay sections")

    bindings: dict[str, tuple[str, str]] = {}
    section_by_id: dict[str, str] = {}
    for part in root.findall("./body/part"):
        part_number = _text(part.find("label"))
        if not re.fullmatch(r"[0-9]+", part_number):
            _fail(path, "unlabelled amendment Part")
        effective = dates.get(part_number, dates["act"])
        for section in part.findall("prov"):
            suffix = f"section/{_text(section.find('label'))}"
            citation = f"{path}/{suffix}"
            if citation not in by_path:
                _fail(citation, "XML section row missing")
            bindings[suffix] = (part_number, effective)
            section_by_id[section.get("id", "")] = suffix
    for suffix in sorted(set(bindings) ^ (set(targets) | set(insertions))):
        _fail(f"{path}/{suffix}", "XML Part sections and reviewed overlay differ")
    part_labels = {_text(p.find("label")) for p in root.findall("./body/part")}
    if set(dates) - {"act"} - part_labels:
        _fail(commencement_path, "commencement exception names a missing XML Part")

    additions: dict[str, dict[str, Any]] = {
        path: {"document_type": "amendment_act", "amends": [principal.citation_path]}
    }
    for suffix, (part_number, effective) in bindings.items():
        citation = f"{path}/{suffix}"
        row = by_path[citation]
        metadata: dict[str, Any] = {
            "part": part_number,
            "commencement_date": effective,
            "commencement_citation_path": commencement_path,
        }
        if suffix in insertions:
            if not re.match(r"New (?:section|subpart)s?\b.*\binserted\b", row.heading or ""):
                _fail(citation, "overlay insertion is not a new provision")
        else:
            target_paths = []
            for target_suffix in _target_values(targets[suffix], citation):
                target_path = f"{principal.citation_path}/{target_suffix}"
                target = principal_by_path.get(target_path)
                if target is None or (target.metadata or {}).get("stage") != "in-force":
                    _fail(citation, f"target {target_path} is not an active principal release row")
                _check_target(row, target, target_suffix)
                target_paths.append(target_path)
            if len(target_paths) == 1:
                metadata["amendment_target"] = target_paths[0]
            else:
                metadata["amendment_targets"] = target_paths
        additions[citation] = metadata

    for schedule in root.findall("./schedule.group/schedule"):
        schedule_path = f"{path}/schedule/{_text(schedule.find('label'))}"
        references = schedule.findall("./empowering-prov//intref")
        suffix = section_by_id.get(references[0].get("href", "")) if len(references) == 1 else None
        if suffix is None or f"{path}/{suffix}" not in additions:
            _fail(schedule_path, "schedule must link to one amending section in an XML Part")
        number = _text(schedule.find("label"))
        inserting_row = by_path[f"{path}/{suffix}"]
        if (
            _text(references[0]) != f"s {suffix.split('/')[-1]}"
            or f"Part set out in Schedule {number} of this Act"
            not in " ".join((inserting_row.body or "").split())
        ):
            _fail(schedule_path, "schedule reference is not its operative insertion section")
        metadata = additions[f"{path}/{suffix}"]
        for citation in by_path:
            if citation == schedule_path or citation.startswith(f"{schedule_path}/"):
                additions[citation] = dict(metadata)

    # All provision/structural rows except preliminary ss 1–3 must be bound.
    for citation in by_path:
        if citation not in additions and citation not in {f"{path}/section/{n}" for n in (1, 2, 3)}:
            _fail(citation, "row has no verified amendment Part binding")
    # The encoder drops bodyless rows and checks amendment status on each
    # surviving row. Apply document markers after checking Part bindings so
    # an unexpected body-bearing row cannot bypass completeness validation.
    document_markers = additions[path]
    for row in rows:
        if row.body is not None:
            additions[row.citation_path] = {
                **additions.get(row.citation_path, {}), **document_markers
            }
    return [
        replace(row, metadata={**(row.metadata or {}), **additions[row.citation_path]})
        if row.citation_path in additions
        else row
        for row in rows
    ]


def _read_rows(path: Path) -> list[ProvisionRecord]:
    return [
        ProvisionRecord.from_mapping(json.loads(line)) for line in path.read_text().splitlines()
    ]


def reproduce_scope(
    *,
    base: Path,
    output: Path,
    overlay_path: Path,
    base_release: Path,
    base_version: str = BASE_VERSION,
    version: str = VERSION,
    temp_root: Path,
) -> dict[str, Any]:
    """Re-extract and verify predecessor bytes, then write an unsigned new scope."""
    source_root = base / "sources/nz/statute" / base_version
    source_paths = sorted(source_root.rglob("*.xml"))
    if len(source_paths) != 1 or sha256_bytes(source_paths[0].read_bytes()) != SOURCE_SHA256:
        _fail("nz/statute/act/public/2026/0054", "retained official source SHA-256 mismatch")
    baseline = _read_rows(base / "provisions/nz/statute" / f"{base_version}.jsonl")
    dates = {(r.source_as_of, r.expression_date) for r in baseline}
    if len(dates) != 1:
        _fail(baseline[0].citation_path, "inconsistent capture dates")
    source_as_of, expression_date = dates.pop()
    temp_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="reextract-", dir=temp_root) as temporary:
        scratch = Path(temporary)
        report = extract_nz_legislation(
            CorpusArtifactStore(scratch),
            version=base_version,
            source_dir=source_root,
            source_as_of=source_as_of,
            expression_date=expression_date,
        ).class_reports[0]
        generated = [
            report.inventory_path,
            report.provisions_path,
            report.coverage_path,
            *report.source_paths,
        ]
        for artifact in generated:
            relative = artifact.relative_to(scratch)
            if artifact.read_bytes() != (base / relative).read_bytes():
                _fail(str(relative), "legacy extraction is not byte-identical")
        extracted = _read_rows(report.provisions_path)

    release = ReleaseManifest.load(base_release)
    if ("nz", "statute", base_version) not in release.scope_keys:
        _fail(str(base_release), "release does not select the predecessor scope")
    principal_rows = []
    for scope in release.scopes:
        if (
            scope.jurisdiction == "nz"
            and scope.document_class == "statute"
            and scope.version != base_version
        ):
            principal_rows.extend(
                _read_rows(base / "provisions/nz/statute" / f"{scope.version}.jsonl")
            )
    overlay = yaml.safe_load(overlay_path.read_text())
    enriched = enrich_amendment_rows(
        source_paths[0].read_bytes(), extracted, principal_rows, overlay
    )
    for old, new in zip(baseline, enriched, strict=True):
        if replace(old, metadata=None) != replace(new, metadata=None):
            _fail(old.citation_path, "enrichment changed a field other than metadata")
    inventory_data = json.loads(
        (base / "inventory/nz/statute" / f"{base_version}.json").read_text()
    )
    store = CorpusArtifactStore(output)
    source = store.source_path(
        "nz", "statute", version, source_paths[0].relative_to(source_root).as_posix()
    )
    # Scope identity follows the successor; citation identity and capture dates
    # remain those of the verified predecessor. Derive the reference from the
    # same store layout as the ordinary extractor, independent of output root.
    source_key = source.relative_to(output).as_posix()
    enriched = [replace(row, version=version, source_path=source_key) for row in enriched]
    # Inventory items normally omit version. Retain every serialized field and
    # add it explicitly for this opt-in scope, as required by its identity
    # contract; SourceInventoryItem is only the coverage projection below.
    inventory_data["items"] = [
        {**item, "version": version, "source_path": source_key}
        for item in inventory_data["items"]
    ]
    inventory = [SourceInventoryItem.from_mapping(item) for item in inventory_data["items"]]
    store.write_bytes(source, source_paths[0].read_bytes())
    store.write_json(store.inventory_path("nz", "statute", version), inventory_data)
    store.write_provisions(store.provisions_path("nz", "statute", version), enriched)
    coverage = compare_provision_coverage(
        inventory, enriched, jurisdiction="nz", document_class="statute", version=version
    )
    store.write_json(store.coverage_path("nz", "statute", version), coverage.to_mapping())
    return {
        "version": version,
        "rows": len(enriched),
        "coverage": coverage.to_mapping(),
        "source_sha256": SOURCE_SHA256,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--output", type=Path, default=Path("data/corpus"))
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument(
        "--base-release", type=Path, default=Path("manifests/releases/nz-rulespec-2026-10-20.json")
    )
    parser.add_argument("--temp-root", type=Path, required=True)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            reproduce_scope(
                base=args.base,
                output=args.output,
                overlay_path=args.overlay,
                base_release=args.base_release,
                temp_root=args.temp_root,
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
