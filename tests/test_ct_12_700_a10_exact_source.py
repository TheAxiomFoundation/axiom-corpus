from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-07-26-ct-12-700-a-10"
ROOT_CITATION = "us-ct/statute/12-700-a-10"
BODY_CITATION = f"{ROOT_CITATION}/operative-text"
SOURCE_SHA256 = "9bda4ecdbbe3937466237f934178f2d1d478b74f586d49cafdca262844467d8a"
BODY_SHA256 = "2666576e22017a34830ba1a51ef140502b47b39fd9383cb24e5751631c1b8bf1"


def _provisions() -> list[dict[str, object]]:
    path = ROOT / f"data/corpus/provisions/us-ct/statute/{VERSION}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_ct_12_700_a10_anchor_range_is_unique_and_ordered() -> None:
    manifest = yaml.safe_load(
        (ROOT / "manifests/us-ct-12-700-a-10-current.yaml").read_text(
            encoding="utf-8"
        )
    )
    document = manifest["documents"][0]
    extraction = document["extraction"]
    source = (
        ROOT
        / f"data/corpus/sources/us-ct/statute/{VERSION}/official-documents/"
        "us-ct-cga-current-section-12-700-a-10.html"
    )
    source_bytes = source.read_bytes()
    soup = BeautifulSoup(source_bytes, "html.parser")
    starts = soup.select(extraction["html_start_selector"])
    stops = soup.select(extraction["html_stop_selector"])

    assert document["citation_path"] == ROOT_CITATION
    assert extraction["citation_suffix"] == "operative-text"
    assert hashlib.sha256(source_bytes).hexdigest() == SOURCE_SHA256
    assert len(starts) == len(stops) == 1
    assert starts[0].sourceline is not None
    assert stops[0].sourceline is not None
    assert starts[0].sourceline < stops[0].sourceline


def test_ct_12_700_a10_scope_is_exact_and_complete() -> None:
    provisions = _provisions()
    assert [record["citation_path"] for record in provisions] == [
        ROOT_CITATION,
        BODY_CITATION,
    ]
    assert all(
        not str(record["citation_path"]).startswith("us-ct/statute/12-700/a")
        for record in provisions
    )

    body = provisions[1]["body"]
    assert isinstance(body, str)
    assert len(body) == 11_486
    assert hashlib.sha256(body.encode()).hexdigest() == BODY_SHA256
    assert body.startswith(
        "(10) For taxable years commencing on or after January 1, 2024"
    )
    for marker in (
        "(A) (i) For any person",
        "(B) (i) For any person",
        "(C) (i) For any husband and wife",
        "(D) (i) For any person",
        "(E) For trusts or estates",
    ):
        assert body.count(marker) == 1
    for excluded in (
        "(11) The provisions of this subsection",
        "Sec. 12-700a.",
        "Sec. 12-701.",
        "History:",
    ):
        assert excluded not in body


def test_ct_12_700_a10_coverage_has_no_gaps_or_duplicates() -> None:
    coverage = json.loads(
        (
            ROOT / f"data/corpus/coverage/us-ct/statute/{VERSION}.json"
        ).read_text(encoding="utf-8")
    )
    assert coverage == {
        "complete": True,
        "document_class": "statute",
        "duplicate_provision_citations": [],
        "duplicate_source_citations": [],
        "extra_provisions": [],
        "jurisdiction": "us-ct",
        "matched_count": 2,
        "missing_from_provisions": [],
        "provision_count": 2,
        "source_count": 2,
        "version": VERSION,
    }
