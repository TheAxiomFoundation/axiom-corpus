"""Offline recovery driver tests against committed official-source snapshots."""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from axiom_corpus.corpus.ecfr import EcfrPartTarget, iter_ecfr_title_provisions
from scripts import recover_ingest_batch
from scripts.recover_ingest import load_fetched_files, recover
from scripts.recover_ingest_batch import (
    _assembled_html_pages,
    _ecfr_paragraph_records,
    _load_file,
    _plan_document_id,
    _targeted_state_html,
)

REPO = Path(__file__).parents[1]


@pytest.fixture
def ecfr_recovery_case(tmp_path: Path) -> tuple[dict, Path, bytes, dict]:
    # Real parser input: the appendix is present but excluded by ordinary recovery.
    data = b'''<?xml version="1.0"?><ECFR><DIV5 N="604" TYPE="PART">
    <HEAD>Part 604</HEAD><DIV8 N="604.1" TYPE="SECTION"><HEAD>Scope</HEAD>
    <P>Retained section.</P></DIV8><DIV9 N="Appendix A to Part 604" TYPE="APPENDIX">
    <HEAD>Appendix A</HEAD><P>Retained appendix.</P><IMG SRC="form.gif"/>
    </DIV9></DIV5></ECFR>'''
    fetched = tmp_path / "fetched"
    fetched.mkdir()
    source = fetched / "ecfr-45-604.xml"
    source.write_bytes(data)
    provenance = {
        "file": source.name,
        "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-08-27/title-45.xml?part=604",
        "fetched_at": "2026-08-27T00:00:00Z",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    source.with_name(source.name + ".provenance.json").write_text(json.dumps(provenance))
    entry = {
        "parser": "ecfr-xml",
        "jurisdiction": "us",
        "document_class": "regulation",
        "version": "test",
        "title": 45,
        "parts": ["604"],
    }
    return entry, fetched, data, provenance


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("declaration", ["opt-in", "target", "existing-inventory"])
def test_recovery_refuses_appendix_replay_before_writes(
    tmp_path: Path, ecfr_recovery_case: tuple, declaration: str, dry_run: bool
) -> None:
    entry, fetched, _, _ = ecfr_recovery_case
    base = tmp_path / "corpus"
    base.mkdir()
    marker = base / "untouched.png"
    marker.write_bytes(b"retained graphic bytes")
    if declaration == "opt-in":
        entry["include_appendices"] = True
    elif declaration == "target":
        entry["covers_citation_paths"] = ["us/regulation/45/604/appendix-a/1"]
    else:
        inventory = base / "inventory/us/regulation/test.json"
        inventory.parent.mkdir(parents=True)
        inventory.write_text(json.dumps({"items": [{
            "citation_path": "us/regulation/45/604/appendix-a",
            "metadata": {"kind": "appendix", "structure_only": True},
        }]}))
    before = {p.relative_to(base): p.read_bytes() for p in base.rglob("*") if p.is_file()}

    with pytest.raises(ValueError, match="appendix recovery is unsupported"):
        recover(entry, fetched, base=base, repo=tmp_path, dry_run=dry_run)

    assert {p.relative_to(base): p.read_bytes() for p in base.rglob("*") if p.is_file()} == before
    assert not (tmp_path / ".ingest").exists()


def test_recovery_default_still_excludes_appendices(ecfr_recovery_case: tuple, tmp_path: Path) -> None:
    entry, fetched, data, provenance = ecfr_recovery_case
    result = recover(entry, fetched, base=tmp_path / "corpus", repo=tmp_path, dry_run=True)
    assert result.provisions == 2
    batch_entry = {
        **entry,
        "parser": "ecfr:xml",
        "document_id": "ecfr-45-part-604",
        "proposed_version": "test",
        "covers_citation_paths": ["us/regulation/45/604/1"],
    }
    items, records = recover_ingest_batch._parse(
        batch_entry, fetched / "ecfr-45-604.xml", data, provenance, "sources/test.xml"
    )
    assert [r.citation_path for r in records] == ["us/regulation/45/604", "us/regulation/45/604/1"]
    assert [r.citation_path for r in items] == [r.citation_path for r in records]
    assert records[1].body == "Retained section."


@pytest.mark.parametrize("declaration", ["opt-in", "target"])
def test_batch_parser_refuses_appendix_replay(ecfr_recovery_case: tuple, declaration: str) -> None:
    entry, fetched, data, provenance = ecfr_recovery_case
    entry.update(parser="ecfr:xml", document_id="ecfr-45-part-604", proposed_version="test")
    if declaration == "opt-in":
        entry["include_appendices"] = True
    else:
        entry["covers_citation_paths"] = ["us/regulation/45/604/appendix-a"]
    with pytest.raises(ValueError, match="appendix recovery is unsupported"):
        recover_ingest_batch._parse(
            entry, fetched / "ecfr-45-604.xml", data, provenance, "sources/test.xml"
        )


@pytest.mark.parametrize("previously_parsed", [False, True])
@pytest.mark.parametrize("declaration", ["opt-in", "existing-inventory"])
def test_batch_refuses_appendix_replay_before_report_or_artifact_writes(
    tmp_path: Path, ecfr_recovery_case: tuple, monkeypatch: pytest.MonkeyPatch,
    previously_parsed: bool, declaration: str,
) -> None:
    entry, fetched, _, _ = ecfr_recovery_case
    entry.update(
        parser="ecfr:xml", document_id="ecfr-45-part-604", proposed_version="test",
        covers_citation_paths=["us/regulation/45/604/1"],
    )
    base = tmp_path / "corpus"
    if declaration == "opt-in":
        entry["include_appendices"] = True
    else:
        inventory = base / "inventory/us/regulation/test.json"
        inventory.parent.mkdir(parents=True)
        inventory.write_text(json.dumps({"items": [{
            "citation_path": "us/regulation/45/604/appendix-a",
        }]}))
    artifacts_before = {p.relative_to(base): p.read_bytes() for p in base.rglob("*") if p.is_file()}
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"documents": [entry]}))
    report = tmp_path / "report.json"
    report.write_text(json.dumps({entry["document_id"]: {
        "parsed": previously_parsed, "rows": 2, "citations_resolved": "1/1", "issues": [],
    }}))
    before = report.read_bytes()
    for name, value in {"PLAN": plan, "REPORT": report, "BASE": base, "FETCHED": fetched}.items():
        monkeypatch.setattr(recover_ingest_batch, name, value)
    monkeypatch.delenv("AXIOM_RECOVERY_ONLY_DOCUMENT_ID", raising=False)

    with pytest.raises(ValueError, match="appendix recovery is unsupported"):
        recover_ingest_batch.main()

    assert report.read_bytes() == before
    assert {p.relative_to(base): p.read_bytes() for p in base.rglob("*") if p.is_file()} == artifacts_before


def test_recovery_cli_refuses_appendix_before_output(
    tmp_path: Path, ecfr_recovery_case: tuple,
) -> None:
    entry, fetched, _, _ = ecfr_recovery_case
    entry["include_appendices"] = True
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(entry))
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts/recover_ingest.py"),
         "--plan", str(plan), "--fetched-dir", str(fetched),
         "--base", str(tmp_path / "corpus"), "--repo", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "appendix recovery is unsupported" in result.stderr
    assert not (tmp_path / "corpus").exists()


def test_batch_recovery_imports_when_executed_as_a_script() -> None:
    # A direct script invocation has scripts/, rather than the repo, at sys.path[0].
    result = subprocess.run(
        [sys.executable, "-c",
         "import runpy, sys; sys.path.insert(0, sys.argv[1]); "
         "runpy.run_path(sys.argv[1] + '/recover_ingest_batch.py')",
         str(REPO / "scripts")],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("script", ["recover_ingest.py", "recover_ingest_batch.py"])
def test_ecfr_recovery_does_not_import_document_parser(
    script: str, tmp_path: Path, ecfr_recovery_case: tuple,
) -> None:
    entry, fetched, _, _ = ecfr_recovery_case
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(entry))
    # A new process cannot inherit document/PDF imports from other pytest cases.
    code = """
import json, runpy, sys
from pathlib import Path
scripts, script, plan_path, fetched_path = sys.argv[1:]
sys.path.insert(0, scripts)
driver = runpy.run_path(str(Path(scripts) / script))
entry = json.loads(Path(plan_path).read_text())
fetched = Path(fetched_path)
if script == "recover_ingest.py":
    result = driver["recover"](
        entry, fetched, base=fetched.parent / "corpus", repo=fetched.parent, dry_run=True,
    )
    assert result.provisions == 2
else:
    entry.update(parser="ecfr:xml", document_id="ecfr-45-part-604", proposed_version="test")
    source = fetched / "ecfr-45-604.xml"
    provenance = json.loads(source.with_suffix(".xml.provenance.json").read_text())
    _, records = driver["_parse"](
        entry, source, source.read_bytes(), provenance, "sources/test.xml",
    )
    assert [record.citation_path for record in records] == [
        "us/regulation/45/604", "us/regulation/45/604/1",
    ]
loaded = set(sys.modules) & {"axiom_corpus.corpus.documents", "fitz", "pymupdf"}
assert not loaded, sorted(loaded)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(REPO / "scripts"), script, str(plan), str(fetched)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert not (tmp_path / "corpus").exists()


def test_recovery_matches_fetch_safe_document_id() -> None:
    assert _plan_document_id(Path("agency_rule_part"), {"agency/rule/part"}) == ("agency/rule/part")


def test_recovery_matches_uslm_title_archive() -> None:
    assert _plan_document_id(Path("usc-title05.zip"), {"uscode-title-5"}) == ("uscode-title-5")


def test_recovery_verifies_and_extracts_single_uslm_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "usc-title05.zip"
    xml = b'<uscDoc xmlns="http://xml.house.gov/schemas/uslm/1.0" />'
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("usc05.xml", xml)
    archive_sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_name(archive_path.name + ".provenance.json").write_text(
        json.dumps(
            {
                "url": "https://uscode.house.gov/usc05.zip",
                "fetched_at": "2026-07-14T00:00:00Z",
                "sha256": archive_sha,
            }
        )
    )

    extracted, provenance = _load_file(archive_path)

    assert extracted == xml
    assert provenance["archive_member"] == "usc05.xml"
    assert provenance["archive_sha256"] == archive_sha
    assert provenance["sha256"] == hashlib.sha256(xml).hexdigest()


def test_recovery_ecfr_emits_verified_paragraph_depth() -> None:
    xml = """<ECFR><DIV5 N="435" TYPE="PART"><HEAD>Part 435</HEAD>
    <DIV8 N="§ 435.601" TYPE="SECTION"><HEAD>§ 435.601 Test.</HEAD>
    <P>(a) First.</P><P>(d) Items:</P><P>(1) One.</P><P>(2) Two.</P>
    </DIV8></DIV5></ECFR>"""
    structural = list(
        iter_ecfr_title_provisions(
            xml,
            (EcfrPartTarget(42, "435"),),
            "2026-07-13-recovery-test",
            "sources/test.xml",
            "2026-07-13",
            "2026-07-13",
        )
    )

    paragraphs = _ecfr_paragraph_records(structural)
    by_path = {row.citation_path: row for row in paragraphs}

    assert "us/regulation/42/435/601/a" in by_path
    assert "us/regulation/42/435/601/d/1" in by_path
    assert by_path["us/regulation/42/435/601/d/1"].body == "(1) One."
    assert by_path["us/regulation/42/435/601/d/1"].parent_citation_path == (
        "us/regulation/42/435/601/d"
    )


def test_recovery_splits_assembled_state_sections_at_planned_depth() -> None:
    targets = [f"us-de/statute/30/{section}" for section in (1102, 1108, 1109)]
    html = (
        b"<html><body><h2>\xc2\xa7 1102. One</h2><p>"
        + b"a" * 200
        + (b"</p><h2>\xc2\xa7 1108. Two</h2><p>" + b"b" * 200)
        + b"</p><h2>\xc2\xa7 1109. Three</h2><p>"
        + b"c" * 200
        + b"</p></body></html>"
    )
    entry = {
        "document_id": "us-de-code-30",
        "jurisdiction": "us-de",
        "document_class": "statute",
        "proposed_version": "test",
        "parser": "state-statutes:delaware",
        "covers_citation_paths": targets,
    }
    provenance = {"url": "https://example.gov", "sha256": "0" * 64, "fetched_at": "now"}

    _, records = _targeted_state_html(entry, html, provenance, "sources/test.html")

    assert [record.citation_path for record in records] == targets


def test_recovery_rejects_repeated_planned_state_section_labels() -> None:
    targets = [
        "us-nc/statute/105/105-153.7",
        "us-nc/statute/105/105-153.9",
    ]
    source = (
        REPO
        / "data/corpus/sources/us-nc/statute/2026-07-13-recovery"
        / "official-documents/us-nc-code-105"
    )
    provenance = json.loads(
        source.parent.parent.joinpath("provenance/us-nc-code-105.json").read_text()
    )
    entry = {
        "document_id": "us-nc-code-105",
        "jurisdiction": "us-nc",
        "document_class": "statute",
        "proposed_version": "test",
        "parser": "new:north-carolina-statutes-html",
        "covers_citation_paths": targets,
    }

    with pytest.raises(
        ValueError,
        match=r"repeated planned section 105-153\.9; configure an explicit version-aware splitter",
    ):
        _targeted_state_html(entry, source.read_bytes(), provenance, "sources/us-nc-code-105")


def test_recovery_selects_nc_statute_rendition_for_explicit_tax_year() -> None:
    targets = [
        "us-nc/statute/105/105-153.7",
        "us-nc/statute/105/105-153.9",
    ]
    source = (
        REPO
        / "data/corpus/sources/us-nc/statute/2026-07-13-recovery"
        / "official-documents/us-nc-code-105"
    )
    provenance = json.loads(
        source.parent.parent.joinpath("provenance/us-nc-code-105.json").read_text()
    )
    entry = {
        "document_id": "us-nc-code-105",
        "jurisdiction": "us-nc",
        "document_class": "statute",
        "proposed_version": "test",
        "parser": "new:north-carolina-statutes-html",
        "covers_citation_paths": targets,
        "version_aware_splitter": {
            "kind": "north-carolina-tax-year",
            "tax_year": 2026,
        },
    }

    _, records = _targeted_state_html(
        entry, source.read_bytes(), provenance, "sources/us-nc-code-105"
    )

    by_path = {record.citation_path: record for record in records}
    selected = by_path["us-nc/statute/105/105-153.9"]
    assert "on or after January 1, 2023" in (selected.body or "")
    assert "beginning before January 1, 2023" not in (selected.body or "")
    selection = (selected.metadata or {})["version_selection"]
    assert selection["kind"] == "north-carolina-tax-year"
    assert selection["tax_year"] == 2026
    assert len(selection["renditions"]) == 2
    assert [row["selected"] for row in selection["renditions"]] == [False, True]
    assert all(len(row["body_sha256"]) == 64 for row in selection["renditions"])


def test_recovery_single_nc_target_cannot_bypass_explicit_tax_year_splitter() -> None:
    target = "us-nc/statute/105/105-153.9"
    source = (
        REPO
        / "data/corpus/sources/us-nc/statute/2026-07-13-recovery"
        / "official-documents/us-nc-code-105"
    )
    provenance = json.loads(
        source.parent.parent.joinpath("provenance/us-nc-code-105.json").read_text()
    )
    entry = {
        "document_id": "us-nc-code-105",
        "jurisdiction": "us-nc",
        "document_class": "statute",
        "proposed_version": "test",
        "parser": "new:north-carolina-statutes-html",
        "covers_citation_paths": [target],
        "version_aware_splitter": {
            "kind": "north-carolina-tax-year",
            "tax_year": 2026,
        },
    }

    _, records = _targeted_state_html(
        entry, source.read_bytes(), provenance, "sources/us-nc-code-105"
    )

    assert len(records) == 1
    assert records[0].citation_path == target
    assert "on or after January 1, 2023" in (records[0].body or "")
    assert "beginning before January 1, 2023" not in (records[0].body or "")
    assert (records[0].metadata or {})["version_selection"]["tax_year"] == 2026


def test_recovery_single_nc_target_without_selector_rejects_duplicate_renditions() -> None:
    target = "us-nc/statute/105/105-153.9"
    source = (
        REPO
        / "data/corpus/sources/us-nc/statute/2026-07-13-recovery"
        / "official-documents/us-nc-code-105"
    )
    provenance = json.loads(
        source.parent.parent.joinpath("provenance/us-nc-code-105.json").read_text()
    )
    entry = {
        "document_id": "us-nc-code-105",
        "jurisdiction": "us-nc",
        "document_class": "statute",
        "proposed_version": "test",
        "parser": "new:north-carolina-statutes-html",
        "covers_citation_paths": [target],
    }

    with pytest.raises(
        ValueError,
        match=r"repeated planned section 105-153\.9; configure an explicit version-aware splitter",
    ):
        _targeted_state_html(
            entry, source.read_bytes(), provenance, "sources/us-nc-code-105"
        )


@pytest.mark.parametrize(
    "selector",
    [
        {"kind": "heading-contains", "tax_year": "2026"},
        {"kind": "north-carolina-tax-year", "tax_year": True},
    ],
)
def test_recovery_single_nc_target_rejects_malformed_version_selector(
    selector: dict[str, object],
) -> None:
    target = "us-nc/statute/105/105-153.9"
    source = (
        REPO
        / "data/corpus/sources/us-nc/statute/2026-07-13-recovery"
        / "official-documents/us-nc-code-105"
    )
    provenance = json.loads(
        source.parent.parent.joinpath("provenance/us-nc-code-105.json").read_text()
    )
    entry = {
        "document_id": "us-nc-code-105",
        "jurisdiction": "us-nc",
        "document_class": "statute",
        "proposed_version": "test",
        "parser": "new:north-carolina-statutes-html",
        "covers_citation_paths": [target],
        "version_aware_splitter": selector,
    }

    with pytest.raises(
        ValueError,
        match="must be a North Carolina tax-year selector with an integer tax_year",
    ):
        _targeted_state_html(
            entry, source.read_bytes(), provenance, "sources/us-nc-code-105"
        )


def test_recovery_ignores_delaware_toc_and_cross_reference_labels() -> None:
    targets = [f"us-de/statute/30/{section}" for section in (1102, 1108, 1109)]
    source = (
        REPO
        / "data/corpus/sources/us-de/statute/2026-07-13-recovery"
        / "official-documents/us-de-code-30"
    )
    provenance = json.loads(
        source.parent.parent.joinpath("provenance/us-de-code-30.json").read_text()
    )
    entry = {
        "document_id": "us-de-code-30",
        "jurisdiction": "us-de",
        "document_class": "statute",
        "proposed_version": "test",
        "parser": "state-statutes:delaware",
        "covers_citation_paths": targets,
    }

    _, records = _targeted_state_html(
        entry, source.read_bytes(), provenance, "sources/us-de-code-30"
    )

    assert [record.citation_path for record in records] == targets
    assert all(
        record.body.startswith(f"§ {record.citation_label}.") for record in records
    )


def test_recovery_normalizes_montana_printed_rule_dots() -> None:
    target = "us-mt/regulation/title-37/chapter-37-78/subchapter-37-78-4/rule-37-78-420"
    html = (
        "<html><body><h1>37.78.420 Assistance standards</h1><p>"
        + "text " * 60
        + "</p></body></html>"
    ).encode()
    entry = {
        "document_id": "us-mt-arm-37-78",
        "jurisdiction": "us-mt",
        "document_class": "regulation",
        "proposed_version": "test",
        "parser": "new:montana-arm-html",
        "covers_citation_paths": [target],
    }
    provenance = {"url": "https://example.gov", "sha256": "0" * 64, "fetched_at": "now"}

    _, records = _targeted_state_html(entry, html, provenance, "sources/test.html")

    assert records[0].citation_path == target


def _require_recovery_payloads():
    root = pathlib.Path(__file__).resolve().parents[1] / "recovered-fetched"
    if not root.exists():
        pytest.skip(
            "local recovery payloads (recovered-fetched/) not present; recovery fixtures are session-local"
        )


def test_recovery_parses_assembled_az_faa5_at_declared_citation_depth() -> None:
    _require_recovery_payloads()
    path = REPO / "recovered-fetched/release-scope-us-az-manual-2025-10-30-az-des-faa5-manual"
    provenance = json.loads(path.with_name(path.name + ".provenance.json").read_text())
    entry = {
        "document_id": provenance["document_id"],
        "jurisdiction": provenance["jurisdiction"],
        "document_class": provenance["document_class"],
        "proposed_version": provenance["version"],
        "parser": "assembled:az-des-faa5-html",
        "covers_citation_paths": provenance["required_citations"],
    }

    items, records = _assembled_html_pages(
        entry, path.read_bytes(), provenance, "sources/us-az/manual/faa5.html"
    )

    assert len(items) == len(records) == 7
    assert provenance["required_citations"] == [
        row.citation_path for row in records if row.metadata["role"] == "REQUIRED-CITATION"
    ]


def _fetched(tmp_path: Path, *sources: str) -> Path:
    fetched = tmp_path / "fetched"
    fetched.mkdir()
    for index, relative in enumerate(sources):
        source = REPO / relative
        target = fetched / source.name
        shutil.copyfile(source, target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        (fetched / f"{index}.provenance.json").write_text(
            json.dumps(
                {
                    "url": f"https://official.example/{source.name}",
                    "fetched_at": "2026-07-13T12:00:00Z",
                    "sha256": digest,
                    "file": source.name,
                }
            )
        )
    return fetched


@pytest.mark.parametrize(
    ("parser", "source", "extra", "document_class"),
    [
        (
            "uscode-olrc-xml",
            "data/corpus/sources/us/statute/2026-06-24-doe-rebates-title-42-title-42-r2026-07-15-self-contained-r2026-07-17-dedup/uslm/usc42.xml",
            {},
            "statute",
        ),
        (
            "uscode-olrc-xml",
            "data/corpus/sources/us/statute/2026-06-23-medicare-426-title-42-r2026-07-15-self-contained-r2026-07-17-dedup/uslm/usc42.xml",
            {},
            "statute",
        ),
        (
            "ecfr-xml",
            "data/corpus/sources/us/regulation/2026-06-15-title-7-part-275/ecfr/title-7-part-275.xml",
            {"title": 7, "parts": ["275"]},
            "regulation",
        ),
        (
            "ecfr-xml",
            "data/corpus/sources/us/regulation/2026-06-24-title-45-part-1302/ecfr/title-45-part-1302.xml",
            {"title": 45, "parts": ["1302"]},
            "regulation",
        ),
        (
            "federal-register",
            "data/corpus/sources/us/rulemaking/2026-06-03-cms-2454-ifc-types-rule-term-cms-2454-ifc-limit-1/federal-register/documents/2026-11094.json",
            {},
            "rulemaking",
        ),
        (
            "html-manual",
            "data/corpus/sources/us/guidance/2026-07-05-ssa-cola-2026/official-documents/ssa-oact-latest-cola-2026.html",
            {
                "documents": [
                    {
                        "file": "ssa-oact-latest-cola-2026.html",
                        "title": "SSA COLA",
                        "citation_path": "us/guidance/ssa/cola",
                    }
                ]
            },
            "guidance",
        ),
        (
            "html-manual",
            "data/corpus/sources/us/guidance/2026-07-05-ssa-cola-2026/official-documents/ssa-cola-2026-federal-register-notice.html",
            {
                "documents": [
                    {
                        "file": "ssa-cola-2026-federal-register-notice.html",
                        "title": "SSA COLA Federal Register Notice",
                        "citation_path": "us/guidance/ssa/cola-notice",
                    }
                ]
            },
            "guidance",
        ),
        (
            "pdf",
            "data/corpus/sources/us/guidance/2026-06-01-irs-rev-proc-2025-25-irs-rev-proc-2025-25/official-documents/irs-rev-proc-2025-25.pdf",
            {
                "documents": [
                    {
                        "file": "irs-rev-proc-2025-25.pdf",
                        "title": "Revenue Procedure 2025-25",
                        "citation_path": "us/guidance/irs/rev-proc-2025-25",
                    }
                ]
            },
            "guidance",
        ),
        (
            "pdf",
            "data/corpus/sources/us/policy/2026-07-05-cms-chip-fcep-spa/official-documents/cms-chip-spa-or-or-cspa-7-1401-pdf-1.pdf",
            {
                "documents": [
                    {
                        "file": "cms-chip-spa-or-or-cspa-7-1401-pdf-1.pdf",
                        "title": "Oregon CHIP SPA",
                        "citation_path": "us/policy/cms/or-chip-spa",
                    }
                ]
            },
            "policy",
        ),
    ],
)
def test_dry_run_existing_official_sources(
    tmp_path: Path,
    parser: str,
    source: str,
    extra: dict[str, object],
    document_class: str,
) -> None:
    fetched = _fetched(tmp_path, source)
    entry = {
        "id": parser,
        "parser": parser,
        "jurisdiction": "us",
        "document_class": document_class,
        "version": "2026-07-13-recovery-test",
        "source_as_of": "2026-07-13",
        "expression_date": "2026-07-13",
        **extra,
    }

    result = recover(entry, fetched, base=tmp_path / "corpus", repo=REPO, dry_run=True)

    assert result.provisions > 0
    assert result.manifest is None


def test_provenance_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    fetched = _fetched(
        tmp_path,
        "data/corpus/sources/us/guidance/2026-07-05-ssa-cola-2026/official-documents/ssa-oact-latest-cola-2026.html",
    )
    sidecar = next(fetched.glob("*.provenance.json"))
    payload = json.loads(sidecar.read_text())
    payload["sha256"] = "0" * 64
    sidecar.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_fetched_files(fetched)


def test_parser_mismatch_fails_closed(tmp_path: Path) -> None:
    fetched = _fetched(
        tmp_path,
        "data/corpus/sources/us/guidance/2026-07-05-ssa-cola-2026/official-documents/ssa-oact-latest-cola-2026.html",
    )
    entry = {
        "parser": "pdf",
        "jurisdiction": "us",
        "document_class": "guidance",
        "version": "2026-07-13-recovery-test",
        "documents": [{"file": "ssa-oact-latest-cola-2026.html", "title": "Wrong parser"}],
    }

    with pytest.raises(ValueError, match="PDF parser mismatch"):
        recover(entry, fetched, base=tmp_path / "corpus", repo=REPO, dry_run=True)


def test_federal_register_collection_page_is_not_misparsed_as_a_document(
    tmp_path: Path,
) -> None:
    fetched = _fetched(
        tmp_path,
        "data/corpus/sources/us/rulemaking/2026-06-03-cms-2454-ifc-types-rule-term-cms-2454-ifc-limit-1/federal-register/api/documents-page-1.json",
    )
    entry = {
        "parser": "federal-register",
        "jurisdiction": "us",
        "document_class": "rulemaking",
        "version": "2026-07-13-recovery-test",
    }

    with pytest.raises(ValueError, match="Federal Register parser mismatch"):
        recover(entry, fetched, base=tmp_path / "corpus", repo=REPO, dry_run=True)
