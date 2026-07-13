"""Offline recovery driver tests against committed official-source snapshots."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.recover_ingest import load_fetched_files, recover

REPO = Path(__file__).parents[1]


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
            "data/corpus/sources/us/statute/2026-06-24-doe-rebates-title-42-title-42/uslm/usc42.xml",
            {},
            "statute",
        ),
        (
            "uscode-olrc-xml",
            "data/corpus/sources/us/statute/2026-06-23-medicare-426-title-42/uslm/usc42.xml",
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
