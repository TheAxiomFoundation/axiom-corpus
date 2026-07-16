"""Offline recovery driver tests against committed official-source snapshots."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pathlib
import pytest

from axiom_corpus.corpus.ecfr import EcfrPartTarget, iter_ecfr_title_provisions
from scripts.recover_ingest import load_fetched_files, recover
from scripts.recover_ingest_batch import (
    _assembled_html_pages,
    _ecfr_paragraph_records,
    _load_file,
    _plan_document_id,
    _targeted_state_html,
)

REPO = Path(__file__).parents[1]


def test_recovery_matches_fetch_safe_document_id() -> None:
    assert _plan_document_id(Path("agency_rule_part"), {"agency/rule/part"}) == (
        "agency/rule/part"
    )


def test_recovery_matches_uslm_title_archive() -> None:
    assert _plan_document_id(Path("usc-title05.zip"), {"uscode-title-5"}) == (
        "uscode-title-5"
    )


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
    html = b"<html><body><h2>\xc2\xa7 1102. One</h2><p>" + b"a" * 200 + (
        b"</p><h2>\xc2\xa7 1108. Two</h2><p>" + b"b" * 200
    ) + b"</p><h2>\xc2\xa7 1109. Three</h2><p>" + b"c" * 200 + b"</p></body></html>"
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


def test_recovery_normalizes_montana_printed_rule_dots() -> None:
    target = "us-mt/regulation/title-37/chapter-37-78/subchapter-37-78-4/rule-37-78-420"
    html = ("<html><body><h1>37.78.420 Assistance standards</h1><p>" + "text " * 60 + "</p></body></html>").encode()
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
        pytest.skip("local recovery payloads (recovered-fetched/) not present; recovery fixtures are session-local")


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
            "data/corpus/sources/us/statute/2026-06-24-doe-rebates-title-42-title-42-r2026-07-15-self-contained/uslm/usc42.xml",
            {},
            "statute",
        ),
        (
            "uscode-olrc-xml",
            "data/corpus/sources/us/statute/2026-06-23-medicare-426-title-42-r2026-07-15-self-contained/uslm/usc42.xml",
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
