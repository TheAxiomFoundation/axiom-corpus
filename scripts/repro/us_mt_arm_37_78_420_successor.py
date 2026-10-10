#!/usr/bin/env python3
"""Rebuild ARM 37.78.420 from its retained rules.mt.gov page as a successor scope.

``us-mt/regulation/2026-07-13-recovery`` holds one row: the whole visible text
of the rules.mt.gov page for ARM 37.78.420 (menus, the rule twice-headed, the
rule, the accordions and the version list). This script builds its successor
from the same retained bytes. The row keeps the citation path; its body is the
rule text read from the page's react-pdf text layer, and the source notes and
the page's version facts go to metadata.

Two steps:

``fetch`` (network, run once): downloads the Esper policy JSON for the rule and
two renditions of rule version 33678, the version the retained page shows as
active: its PDF and its accessible HTML. Each rendition's hash must be the one
the policy JSON declares. They are stored in the successor with provenance
records and serve only as checks.

``build`` (offline): copies the retained page and its provenance byte for byte,
parses the rule, checks it against the fetched renditions (the PDF's characters
and the accessible HTML's lines), and writes the inventory, provisions and
coverage.

    uv run --extra dev python scripts/repro/us_mt_arm_37_78_420_successor.py fetch --base data/corpus
    uv run --extra dev python scripts/repro/us_mt_arm_37_78_420_successor.py build --base data/corpus
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitz
import requests

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.io import load_source_inventory
from axiom_corpus.corpus.models import DocumentClass, SourceInventoryItem
from axiom_corpus.corpus.montana_admin_rules import MONTANA_RULES_USER_AGENT
from axiom_corpus.corpus.montana_rule_page import (
    MontanaRuleDocument,
    MontanaRulePageChrome,
    montana_accessible_html_lines,
    montana_rule_record,
    parse_montana_rule_document,
    parse_montana_rule_page_chrome,
    text_layer_lines,
)

JURISDICTION = "us-mt"
DOCUMENT_CLASS = DocumentClass.REGULATION
SOURCE_VERSION = "2026-07-13-recovery"
VERSION = f"{SOURCE_VERSION}-r2026-09-27-chrome-free"
SOURCE_AS_OF = "2026-07-13"
EXPRESSION_DATE = "2026-07-13"
CITATION_PATH = "us-mt/regulation/title-37/chapter-37-78/subchapter-37-78-4/rule-37-78-420"
DOCUMENT_ID = "us-mt-arm-37-78"
RETAINED_LEAF = f"official-documents/{DOCUMENT_ID}"
RETAINED_PROVENANCE_LEAF = f"provenance/{DOCUMENT_ID}.json"
TEXT_SOURCE = "react-pdf text layer (div.react-pdf__Page__textContent) of the retained page"

COLLECTION_UUID = "aec52c46-128e-4279-9068-8af5d5432d74"
POLICY_UUID = "81418fed-12b0-4ed9-a953-50b600e353d1"
VERSION_NUMBER = "33678"
VERSION_UUID = "d13f3962-467e-4fbc-9c2a-f0fdba477711"
API_BASE_URL = "https://rules.mt.gov/api/policy-library-public"
POLICY_URL = f"{API_BASE_URL}/collections/{COLLECTION_UUID}/policies/{POLICY_UUID}"
POLICY_LEAF = f"montana-rules/policies/37-78-420-{POLICY_UUID}.json"
POLICY_PROVENANCE_LEAF = "provenance/us-mt-arm-37-78-420-policy.json"
VERSION_HTML_LEAF = f"montana-rules/html/37-78-420-{POLICY_UUID}-{VERSION_UUID}.html"
VERSION_HTML_PROVENANCE_LEAF = f"provenance/us-mt-arm-37-78-420-version-{VERSION_NUMBER}-html.json"
VERSION_PDF_LEAF = f"montana-rules/pdf/37-78-420-{POLICY_UUID}-{VERSION_UUID}.pdf"
VERSION_PDF_PROVENANCE_LEAF = f"provenance/us-mt-arm-37-78-420-version-{VERSION_NUMBER}-pdf.json"


@dataclass(frozen=True)
class _Rendition:
    key: str
    leaf: str
    provenance_leaf: str
    document_id: str
    purpose: str


VERSION_RENDITIONS = (
    _Rendition(
        key="accessibleHtmlDocument",
        leaf=VERSION_HTML_LEAF,
        provenance_leaf=VERSION_HTML_PROVENANCE_LEAF,
        document_id=f"us-mt-arm-37-78-420-version-{VERSION_NUMBER}-html",
        purpose=(
            f"verification: the accessible HTML of rule version {VERSION_NUMBER}, checked "
            "line for line against the text-layer reconstruction"
        ),
    ),
    _Rendition(
        key="previewDocument",
        leaf=VERSION_PDF_LEAF,
        provenance_leaf=VERSION_PDF_PROVENANCE_LEAF,
        document_id=f"us-mt-arm-37-78-420-version-{VERSION_NUMBER}-pdf",
        purpose=(
            f"verification: the PDF of rule version {VERSION_NUMBER}, whose text the "
            "retained page's text layer must carry character for character"
        ),
    ),
)
VERIFICATION_LEAVES = (
    POLICY_LEAF,
    POLICY_PROVENANCE_LEAF,
    *(
        leaf
        for rendition in VERSION_RENDITIONS
        for leaf in (rendition.leaf, rendition.provenance_leaf)
    ),
)


def _scope_root(base: Path, version: str) -> Path:
    return Path(base, "sources", JURISDICTION, DOCUMENT_CLASS.value, version)


def _source_key(leaf: str) -> str:
    return f"sources/{JURISDICTION}/{DOCUMENT_CLASS.value}/{VERSION}/{leaf}"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _get(session: requests.Session, url: str) -> requests.Response:
    response = session.get(url, timeout=90)
    response.raise_for_status()
    return response


def policy_version(policy_payload: dict[str, Any], version_uuid: str) -> dict[str, Any]:
    """The policy JSON's entry for one rule version."""

    policy = policy_payload.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("policy payload has no policy object")
    matches = [
        version
        for version in policy.get("policyVersions") or []
        if isinstance(version, dict) and version.get("uuid") == version_uuid
    ]
    if len(matches) != 1:
        raise ValueError(f"policy JSON has {len(matches)} versions with uuid {version_uuid}")
    return matches[0]


def version_field(version: dict[str, Any], key: str) -> str | None:
    for field in version.get("fields") or []:
        if isinstance(field, dict) and field.get("key") == key and field.get("value") is not None:
            return str(field["value"])
    return None


def fetch_verification_sources(*, base: Path) -> tuple[Path, ...]:
    """Download the policy JSON and two renditions of version 33678, with provenance."""

    store = CorpusArtifactStore(base)
    root = _scope_root(base, VERSION)
    session = requests.Session()
    session.headers.update({"User-Agent": MONTANA_RULES_USER_AGENT})

    fetched_at = _now()
    policy_response = _get(session, POLICY_URL)
    policy_bytes = policy_response.content
    version = policy_version(json.loads(policy_bytes), VERSION_UUID)
    if version_field(version, "version_number") != VERSION_NUMBER:
        raise ValueError(f"version {VERSION_UUID} is not number {VERSION_NUMBER}")
    files: dict[str, bytes] = {POLICY_LEAF: policy_bytes}
    provenance: dict[str, dict[str, object]] = {
        POLICY_PROVENANCE_LEAF: {
            "document_id": "us-mt-arm-37-78-420-policy",
            "url": POLICY_URL,
            "fetched_at": fetched_at,
            "sha256": sha256_bytes(policy_bytes),
            "http": policy_response.status_code,
            "content_type": policy_response.headers.get("Content-Type"),
            "fetch_method": "http-get",
            "confidence": "high",
            "purpose": "verification: identifies rule version 33678 and its renditions",
        }
    }
    for rendition in VERSION_RENDITIONS:
        document = version.get(rendition.key)
        if not isinstance(document, dict) or not document.get("contentUrl"):
            raise ValueError(f"version {VERSION_NUMBER} has no {rendition.key}")
        url = f"https://rules.mt.gov/{str(document['contentUrl']).lstrip('/')}"
        declared = str(document.get("contentHashSha256") or "")
        document_fetched_at = _now()
        response = _get(session, url)
        if sha256_bytes(response.content) != declared:
            raise ValueError(
                f"{rendition.key} hash {sha256_bytes(response.content)} is not the declared "
                f"{declared}"
            )
        files[rendition.leaf] = response.content
        provenance[rendition.provenance_leaf] = {
            "document_id": rendition.document_id,
            "url": url,
            "final_url": response.url,
            "fetched_at": document_fetched_at,
            "sha256": declared,
            "declared_sha256": declared,
            "http": response.status_code,
            "content_type": response.headers.get("Content-Type"),
            "fetch_method": "http-get",
            "confidence": "high",
            "purpose": rendition.purpose,
        }

    written = []
    for leaf, content in files.items():
        store.write_bytes(root / leaf, content)
        written.append(root / leaf)
    for leaf, record in provenance.items():
        store.write_bytes(root / leaf, (json.dumps(record, indent=2) + "\n").encode("utf-8"))
        written.append(root / leaf)
    return tuple(written)


def build_scope(*, base: Path, source_base: Path) -> tuple[Path, Path, Path]:
    """Build the successor from the retained page; check it against the fetched rendition."""

    store = CorpusArtifactStore(base)
    old_root = _scope_root(source_base, SOURCE_VERSION)
    verification_root = _scope_root(source_base, VERSION)
    new_root = _scope_root(base, VERSION)

    raw = (old_root / RETAINED_LEAF).read_bytes()
    provenance_bytes = (old_root / RETAINED_PROVENANCE_LEAF).read_bytes()
    provenance = json.loads(provenance_bytes)
    old_inventory = load_source_inventory(
        source_base / "inventory" / JURISDICTION / DOCUMENT_CLASS.value / f"{SOURCE_VERSION}.json"
    )
    if [item.citation_path for item in old_inventory] != [CITATION_PATH]:
        raise ValueError(f"{SOURCE_VERSION} no longer holds exactly {CITATION_PATH}")
    retained_sha = sha256_bytes(raw)
    if retained_sha != provenance["sha256"] or retained_sha != old_inventory[0].sha256:
        raise ValueError(f"retained page hash changed: {retained_sha}")
    store.write_bytes(new_root / RETAINED_LEAF, raw)
    store.write_bytes(new_root / RETAINED_PROVENANCE_LEAF, provenance_bytes)

    verification: dict[str, bytes] = {}
    for leaf in VERIFICATION_LEAVES:
        content = (verification_root / leaf).read_bytes()
        verification[leaf] = content
        store.write_bytes(new_root / leaf, content)

    document = parse_montana_rule_document(raw)
    chrome = parse_montana_rule_page_chrome(raw)
    check_against_verification_sources(raw, document, chrome, verification)

    retained_source_path = _source_key(RETAINED_LEAF)
    old_source_path = old_inventory[0].source_path
    lineage: dict[str, object] = {
        "successor_of_version": SOURCE_VERSION,
        "successor_of_source_path": old_source_path,
        "fetched_at": provenance["fetched_at"],
        "fetch_method": provenance["fetch_method"],
        "text_source": TEXT_SOURCE,
        "verification_source_paths": [
            _source_key(VERSION_HTML_LEAF),
            _source_key(VERSION_PDF_LEAF),
            _source_key(POLICY_LEAF),
        ],
    }
    record = montana_rule_record(
        document,
        chrome,
        citation_path=CITATION_PATH,
        version=VERSION,
        source_url=str(provenance["url"]),
        source_path=retained_source_path,
        source_format="html",
        source_as_of=SOURCE_AS_OF,
        expression_date=EXPRESSION_DATE,
        extra_metadata=lineage,
    )
    inventory = [
        SourceInventoryItem(
            citation_path=CITATION_PATH,
            source_url=str(provenance["url"]),
            source_path=retained_source_path,
            source_format="html",
            sha256=retained_sha,
            metadata={"kind": "rule", **lineage},
        )
    ]

    inventory_path = store.inventory_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    provisions_path = store.provisions_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    coverage_path = store.coverage_path(JURISDICTION, DOCUMENT_CLASS, VERSION)
    store.write_inventory(inventory_path, inventory)
    store.write_provisions(provisions_path, [record])
    coverage = compare_provision_coverage(
        tuple(inventory),
        (record,),
        jurisdiction=JURISDICTION,
        document_class=DOCUMENT_CLASS.value,
        version=VERSION,
    )
    if not coverage.complete:
        raise ValueError("ARM 37.78.420 successor coverage is incomplete")
    store.write_json(coverage_path, coverage.to_mapping())
    return inventory_path, provisions_path, coverage_path


def pdf_text(content: bytes) -> str:
    with fitz.open(stream=content, filetype="pdf") as pdf:
        return "".join(page.get_text() for page in pdf)


def non_space_characters(text: str) -> Counter[str]:
    return Counter(re.sub(r"\s+", "", text))


def check_against_verification_sources(
    raw: bytes,
    document: MontanaRuleDocument,
    chrome: MontanaRulePageChrome,
    verification: dict[str, bytes],
) -> None:
    """Fail unless the retained page agrees with both fetched renditions of its version.

    * The policy JSON names version 33678 by the uuid the page's version list
      links to, with the same number, start date and history, and declares the
      hash of each rendition file.
    * The version's PDF carries exactly the characters of the page's text layer.
    * The version's accessible HTML, rendered line by line, equals the rule
      rebuilt from the text layer.
    """

    for leaf, provenance_leaf in (
        (POLICY_LEAF, POLICY_PROVENANCE_LEAF),
        *((rendition.leaf, rendition.provenance_leaf) for rendition in VERSION_RENDITIONS),
    ):
        if sha256_bytes(verification[leaf]) != json.loads(verification[provenance_leaf])["sha256"]:
            raise ValueError(f"{leaf} does not match its provenance")

    active = chrome.active_version
    if (chrome.collection_uuid, chrome.policy_uuid) != (COLLECTION_UUID, POLICY_UUID):
        raise ValueError("retained page is not policy 81418fed of the ARM collection")
    if (active.number, active.version_uuid) != (VERSION_NUMBER, VERSION_UUID):
        raise ValueError(f"retained page shows version {active.number} ({active.version_uuid})")
    version = policy_version(json.loads(verification[POLICY_LEAF]), VERSION_UUID)
    for rendition in VERSION_RENDITIONS:
        declared = str((version.get(rendition.key) or {}).get("contentHashSha256") or "")
        if declared != sha256_bytes(verification[rendition.leaf]):
            raise ValueError(f"{rendition.leaf} is not the {rendition.key} the policy declares")
    if version_field(version, "version_number") != active.number:
        raise ValueError("policy JSON and page disagree on the version number")
    if version_field(version, "effective_start_date") != active.effective_start_date:
        raise ValueError("policy JSON and page disagree on the effective start date")
    if version_field(version, "history") != document.history:
        raise ValueError("policy JSON and text layer disagree on the history note")

    layer = "".join(segment.text for line in text_layer_lines(raw) for segment in line.segments)
    if non_space_characters(pdf_text(verification[VERSION_PDF_LEAF])) != non_space_characters(
        layer
    ):
        raise ValueError("the text layer does not carry the characters of the version's PDF")

    official = montana_accessible_html_lines(verification[VERSION_HTML_LEAF])
    ours = document.document_lines()
    if ours != official:
        mismatches = [
            (index, mine, theirs)
            for index, (mine, theirs) in enumerate(zip(ours, official, strict=False))
            if mine != theirs
        ]
        raise ValueError(
            "text-layer reconstruction differs from the version's accessible HTML: "
            f"{len(ours)} vs {len(official)} lines; first {mismatches[:1]}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    subparsers = parser.add_subparsers(dest="command", required=True)
    fetch = subparsers.add_parser("fetch", help="download the verification sources (network)")
    fetch.add_argument("--base", type=Path, default=Path("data/corpus"))
    build = subparsers.add_parser("build", help="build the successor scope (offline)")
    build.add_argument("--base", type=Path, default=Path("data/corpus"))
    build.add_argument("--source-base", type=Path)
    args = parser.parse_args()
    if args.command == "fetch":
        for path in fetch_verification_sources(base=args.base):
            print(path)
        return
    for path in build_scope(base=args.base, source_base=args.source_base or args.base):
        print(path)


if __name__ == "__main__":
    main()
