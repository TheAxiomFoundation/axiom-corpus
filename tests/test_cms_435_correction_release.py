from __future__ import annotations

import json
from pathlib import Path

from axiom_corpus.corpus.io import load_provisions

REPO_ROOT = Path(__file__).parents[1]
VERSION = (
    "2026-06-29-cms-2454-ifc-42-cfr-435-community-engagement-"
    "corrected-r2026-07-24-self-contained"
)
RETIRED_VERSION = (
    "2026-06-03-cms-2454-ifc-42-cfr-435-community-engagement-"
    "r2026-07-15-self-contained-r2026-07-15-cascade-contained-"
    "r2026-07-15-self-contained-r2026-07-17-dedup"
)


def test_cms_435_correction_release_uses_complete_corrected_sections() -> None:
    provisions_path = (
        REPO_ROOT / f"data/corpus/provisions/us/regulation/{VERSION}.jsonl"
    )
    records = {record.citation_path: record for record in load_provisions(provisions_path)}
    section_557 = records["us/regulation/42/435/557"]
    section_558 = records["us/regulation/42/435/558"]

    assert len(records) == 14
    assert section_557.source_document_id == "C1-2026-11094"
    assert section_558.source_document_id == "C1-2026-11094"
    assert section_557.source_as_of == "2026-06-29"
    assert section_558.source_as_of == "2026-06-29"

    body_557 = section_557.body or ""
    body_558 = section_558.body or ""
    assert "(B) If an enrollee declares specified excluded individual status" in body_557
    assert "(iii) After verifying an individual's specified excluded individual" in body_557
    assert "(2) The agency must comply with all applicable Federal privacy" in body_557
    assert "(g) Verification of mandatory and optional exceptions." in body_557
    assert "Sec.  435.558   Noncompliance procedures." not in body_557

    assert body_558.startswith("Sec.  435.558   Noncompliance procedures.")
    assert "(a) Provision of notice of noncompliance." in body_558
    assert "(f) Reconsideration period." in body_558
    assert "(B) If an enrollee declares specified excluded individual status" not in body_558
    assert "(g) Verification of mandatory and optional exceptions." not in body_558

    release = json.loads(
        (
            REPO_ROOT
            / "manifests/releases/us-rulespec-2026-07-24-cms-435-correction.json"
        ).read_text()
    )
    versions = {scope["version"] for scope in release["scopes"]}
    assert VERSION in versions
    assert RETIRED_VERSION not in versions
