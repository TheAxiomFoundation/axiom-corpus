"""Pin Maryland's complete chapter, Pennsylvania's existing text, and VT repeal."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import yaml
from bs4 import BeautifulSoup

from scripts.build_snap_child_support_md_manifest import build_manifest

BASE = Path(__file__).resolve().parents[1]
CORPUS = BASE / "data/corpus"
MD_VERSION = "2026-09-27-md-comar-07-03-17-snap"
MD_ROOT = "us-md/regulation/title-07/subtitle-03/chapter-17"
VT_VERSION = "2026-09-27-vt-dcf-b18-06f"


def _rows(scope: str) -> dict[str, dict]:
    return {
        row["citation_path"]: row
        for line in (CORPUS / "provisions" / f"{scope}.jsonl").read_text().splitlines()
        if (row := json.loads(line))
    }


def test_maryland_manifest_covers_every_regulation_in_retained_dsd_index() -> None:
    source = CORPUS / "sources/us-md/regulation" / MD_VERSION / "official-documents/md-comar-07-03-17-index.html"
    manifest = yaml.safe_load((BASE / "manifests/us-md-comar-07-03-17-snap.yaml").read_text())
    assert build_manifest(source.read_bytes()) == manifest
    soup = BeautifulSoup(source.read_bytes(), "html.parser")
    numbers = {str(a["href"]).rsplit(".", 1)[-1] for a in soup.select("article.content nav.toc a")}
    assert numbers == {f"{i:02}" for i in range(1, 62)} | {"09-1"}
    rows = _rows(f"us-md/regulation/{MD_VERSION}")
    for number in numbers:
        assert rows[f"{MD_ROOT}/regulation-{number}/block-1"]["body"]


def test_maryland_deducts_child_support_in_net_calculation() -> None:
    rows = _rows(f"us-md/regulation/{MD_VERSION}")
    assert (
        "A household member who has verification of having made legally obligated child "
        "support payments to or for an individual living outside the household is allowed a deduction."
    ) in rows[f"{MD_ROOT}/regulation-35/block-1"]["body"]
    assert "child support" in rows[f"{MD_ROOT}/regulation-43/block-1"]["body"].lower()
    assert rows[f"{MD_ROOT}/regulation-30/block-1"]["body"]
    assert rows[f"{MD_ROOT}/regulation-42/block-1"]["body"]
    assert rows[f"{MD_ROOT}/regulation-35"]["expression_date"] == "2009-12-14"
    assert rows[f"{MD_ROOT}/regulation-30"]["expression_date"] == "2015-06-22"


def test_pennsylvania_released_handbook_already_has_both_requested_passages() -> None:
    rows = _rows("us-pa/manual/2026-07-21-pa-snap-handbook")
    root = "us-pa/manual/dhs/snap/560-income-deductions"
    assert (
        "A household is eligible for a child support deduction from net income before "
        "calculation of the shelter deduction if all of the following conditions are met:"
    ) in rows[f"{root}-560-6-child-support-deduction/block-1"]["body"]
    appendix = [row for path, row in rows.items() if path.startswith(f"{root}-560-appendix-a/block-")]
    assert len(appendix) == 12
    assert all("Child Support 7 CFR § 273.9(d)(5)" in row["body"] for row in appendix)


def test_vermont_live_repeal_preserves_options_without_stating_an_election() -> None:
    rows = _rows(f"us-vt/rulemaking/{VT_VERSION}")
    root = "us-vt/rulemaking/dcf/2018-12-10/b18-06f"
    assert (
        "Current program options and waivers will be maintained (subject to approval "
        "by the federal Food and Nutrition Service)."
    ) in rows[f"{root}/page-1"]["body"]
    assert rows[root]["expression_date"] == "2018-12-10"
    assert rows[root]["metadata"]["effective_date"] == "2019-01-01"
    pdf = CORPUS / "sources/us-vt/rulemaking" / VT_VERSION / "official-documents/vt-dcf-b18-06f.pdf"
    with pymupdf.open(pdf) as document:
        assert len(document) == 3
        assert all(page.get_text().strip() for page in document)


def test_maryland_and_vermont_coverage_complete() -> None:
    for scope in (f"us-md/regulation/{MD_VERSION}", f"us-vt/rulemaking/{VT_VERSION}"):
        report = json.loads((CORPUS / "coverage" / f"{scope}.json").read_text())
        assert report["complete"] is True
