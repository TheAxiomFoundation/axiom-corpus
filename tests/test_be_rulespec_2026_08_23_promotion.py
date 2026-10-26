"""Regression checks for the 2026-08-23 Belgian statute promotion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/corpus"
OLD_VERSION = "2026-07-10-be-rulespec-source-promotion"
NEW_VERSION = "2026-08-23-be-rulespec-source-promotion"
FULL_VERSION = "2026-06-30-be-income-tax-consolidated"
LIVE_RELEASE_PATH = ROOT / "manifests/releases/be-rulespec-2026-08-23.json"
SUCCESSOR_RELEASE_PATH = ROOT / "manifests/releases/be-rulespec-2026-08-29.json"
INGEST_MANIFEST_PATH = (
    ROOT / ".axiom/ingest-manifests/be/statute" / f"{NEW_VERSION}.json"
)
CIR_PARENT = "be/statute/fisconetplus/cir92/revenus-2025"
REQUIRED_PAGES = frozenset({183, 188, 189, 190, 192, 268, 269, 270, 271, 272, 275})
RECOMMENDED_PAGES = frozenset({252, 254, 257, 258})
ADDED_PAGES = REQUIRED_PAGES | RECOMMENDED_PAGES
ADDED_CITATIONS = frozenset(f"{CIR_PARENT}/page-{page}" for page in ADDED_PAGES)
OLD_PROVISIONS_PATH = BASE / "provisions/be/statute" / f"{OLD_VERSION}.jsonl"
NEW_PROVISIONS_PATH = BASE / "provisions/be/statute" / f"{NEW_VERSION}.jsonl"
FULL_PROVISIONS_PATH = BASE / "provisions/be/statute" / f"{FULL_VERSION}.jsonl"
OLD_INPUTS = BASE / "sources/be/statute" / OLD_VERSION / "inputs"
NEW_INPUTS = BASE / "sources/be/statute" / NEW_VERSION / "inputs"
CIR_INPUT_NAME = (
    "axiom-corpus-9be12db7c693-2026-06-30-be-income-tax-consolidated.selected.jsonl"
)


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _rows_by_citation(path: Path) -> dict[str, dict[str, object]]:
    rows = _load_jsonl(path)
    result = {str(row["citation_path"]): row for row in rows}
    assert len(result) == len(rows)
    return result


def _raw_rows_by_citation(path: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for line in path.read_bytes().splitlines():
        citation = str(json.loads(line)["citation_path"])
        assert citation not in result
        result[citation] = line
    return result


def test_be_rulespec_2026_08_29_selector_reuses_every_other_scope() -> None:
    old = ReleaseManifest.load(LIVE_RELEASE_PATH)
    new = ReleaseManifest.load(SUCCESSOR_RELEASE_PATH)
    old_scopes = {
        (scope.jurisdiction, scope.document_class): scope.version for scope in old.scopes
    }
    new_scopes = {
        (scope.jurisdiction, scope.document_class): scope.version for scope in new.scopes
    }

    assert new.name == "be-rulespec-2026-08-29"
    assert new.quality_profile == "complete-expression-dates-v1"
    assert len(old_scopes) == len(new_scopes) == 13
    assert old_scopes.keys() == new_scopes.keys()
    assert old_scopes[("be", "statute")] == OLD_VERSION
    assert new_scopes[("be", "statute")] == NEW_VERSION
    assert {
        key: version for key, version in new_scopes.items() if key != ("be", "statute")
    } == {
        key: version for key, version in old_scopes.items() if key != ("be", "statute")
    }


def test_be_rulespec_2026_08_23_preserves_old_rows_and_adds_exact_pages() -> None:
    old = _rows_by_citation(OLD_PROVISIONS_PATH)
    new = _rows_by_citation(NEW_PROVISIONS_PATH)
    full = _rows_by_citation(FULL_PROVISIONS_PATH)

    assert len(old) == 169
    assert len(new) == 184
    assert new.keys() - old.keys() == ADDED_CITATIONS
    assert old.keys() <= new.keys()

    for citation, old_row in old.items():
        expected = dict(old_row)
        expected["version"] = NEW_VERSION
        expected["source_path"] = str(expected["source_path"]).replace(
            f"sources/be/statute/{OLD_VERSION}/inputs/",
            f"sources/be/statute/{NEW_VERSION}/inputs/",
            1,
        )
        assert new[citation] == expected
        assert new[citation].get("body") == old_row.get("body")

    for citation in ADDED_CITATIONS:
        expected = dict(full[citation])
        expected["version"] = NEW_VERSION
        expected["expression_date"] = "2026-06-30"
        expected["source_path"] = f"sources/be/statute/{NEW_VERSION}/inputs/{CIR_INPUT_NAME}"
        assert new[citation] == expected
        assert new[citation].get("body") == full[citation].get("body")
        assert new[citation]["parent_citation_path"] == CIR_PARENT
        assert str(new[citation]["parent_id"]) == str(new[CIR_PARENT]["id"])


def test_be_rulespec_2026_08_23_source_boundary_is_raw_line_superset() -> None:
    old_cir = _raw_rows_by_citation(OLD_INPUTS / CIR_INPUT_NAME)
    new_cir = _raw_rows_by_citation(NEW_INPUTS / CIR_INPUT_NAME)
    full_cir = _raw_rows_by_citation(FULL_PROVISIONS_PATH)
    selected_citations = old_cir.keys() | ADDED_CITATIONS
    expected_lines = [
        line
        for line in FULL_PROVISIONS_PATH.read_bytes().splitlines()
        if str(json.loads(line)["citation_path"]) in selected_citations
    ]

    assert len(old_cir) == 37
    assert len(new_cir) == 52
    assert new_cir.keys() == selected_citations
    assert (NEW_INPUTS / CIR_INPUT_NAME).read_bytes().splitlines() == expected_lines
    assert all(new_cir[citation] == line for citation, line in old_cir.items())
    assert all(new_cir[citation] == full_cir[citation] for citation in ADDED_CITATIONS)

    old_other_inputs = {
        path.name: path for path in OLD_INPUTS.iterdir() if path.name != CIR_INPUT_NAME
    }
    new_other_inputs = {
        path.name: path for path in NEW_INPUTS.iterdir() if path.name != CIR_INPUT_NAME
    }
    assert old_other_inputs.keys() == new_other_inputs.keys()
    assert len(old_other_inputs) == 10
    for name, old_path in old_other_inputs.items():
        assert new_other_inputs[name].read_bytes() == old_path.read_bytes()


def test_be_rulespec_2026_08_29_passes_strict_release_validation() -> None:
    report = validate_release(
        BASE,
        ReleaseManifest.load(SUCCESSOR_RELEASE_PATH),
        strict_warnings=True,
        max_issues=500,
    )

    assert report.to_mapping() == {
        "release": "be-rulespec-2026-08-29",
        "scope_count": 13,
        "ok": True,
        "error_count": 0,
        "warning_count": 0,
        "strict_warnings": True,
        "issue_count": 0,
        "issues_returned": 0,
        "issues_truncated": False,
        "issues": [],
    }


def test_be_rulespec_2026_08_23_ingest_manifest_covers_every_artifact() -> None:
    manifest = json.loads(INGEST_MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = {
        (
            BASE
            / artifact_class
            / "be/statute"
            / f"{NEW_VERSION}{'.jsonl' if artifact_class == 'provisions' else '.json'}"
        ).relative_to(ROOT).as_posix()
        for artifact_class in ("coverage", "inventory", "provisions")
    }
    expected.update(
        path.relative_to(ROOT).as_posix() for path in NEW_INPUTS.iterdir() if path.is_file()
    )
    applied = {item["path"]: item["sha256"] for item in manifest["applied_files"]}

    assert manifest["coverage"] == {
        "complete": True,
        "extra_count": 0,
        "matched_count": 184,
        "missing_count": 0,
        "provision_count": 184,
        "source_count": 184,
    }
    assert applied.keys() == expected
    assert all(
        hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
        for path, digest in applied.items()
    )
