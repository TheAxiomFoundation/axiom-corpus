"""The recovery batch's final reconciliation reads bodies and stops a scope vouching for itself.

The July 2026 report counted every us-ca LegInfo page as ``1/1`` resolved by
``exact-cross-scope`` although none was parsed in that run: the index held
every path of every provisions file, the scope's own empty roots included
(docs/ingest-runs/2026-09-25-us-ca-statute-recovery-audit.md, "Why the recovery
report counted these rows as recovered"). Now a path resolves a target only
where its row carries text, and the target's own planned scope counts only when
its document was parsed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.recover_ingest_batch as batch
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem

REPO_ROOT = Path(__file__).resolve().parents[1]
OWN = ("us-xx", "statute", "2026-07-13-recovery")
OTHER = ("us-xx", "statute", "2026-09-14-chapter")
MENU = "Home\n\nAdvanced Search\n\nContact Us"
PAGE = (
    "<!doctype html><html><body><nav><a href='/'>Home</a> <a href='/s'>Advanced Search</a> "
    "<a href='/c'>Contact Us</a></nav><p>Every individual domiciled here is a resident.</p>"
    "</body></html>"
)
LAW = "Every individual domiciled here is a resident."


def _write(
    base: Path, scope: tuple[str, str, str], rows: list[tuple[str, str | None, str]]
) -> None:
    source = f"sources/{'/'.join(scope)}/page.html"
    (base / source).parent.mkdir(parents=True, exist_ok=True)
    (base / source).write_text(PAGE, encoding="utf-8")
    path = base / "provisions" / scope[0] / scope[1] / f"{scope[2]}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "jurisdiction": scope[0],
                "document_class": scope[1],
                "version": scope[2],
                "citation_path": citation_path,
                "body": body,
                "kind": kind,
                "source_path": source,
            }
        )
        for citation_path, body, kind in rows
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _index(monkeypatch: pytest.MonkeyPatch, base: Path) -> tuple[dict, dict]:
    monkeypatch.setattr(batch, "BASE", base)
    monkeypatch.setattr(batch, "REPO", base.parent)
    return batch._all_ingested_citation_paths()


def _resolve(index: tuple[dict, dict], target: str, *, parsed: bool) -> dict[str, str] | None:
    carriers, normalized = index
    return batch._resolve_across_ingested_scopes(
        target, carriers, normalized, own_scope=OWN, include_own=parsed
    )


def test_an_unparsed_documents_own_rows_do_not_resolve_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write(
        tmp_path,
        OWN,
        [
            ("us-xx/statute/17014", None, "document"),
            ("us-xx/statute/17014/block-1", MENU, "block"),
            ("us-xx/statute/17014/block-2", LAW, "block"),
        ],
    )
    index = _index(monkeypatch, tmp_path)
    assert index[0]["us-xx/statute/17014"] == frozenset({OWN})
    assert _resolve(index, "us-xx/statute/17014", parsed=False) is None
    assert _resolve(index, "us-xx/statute/17014", parsed=True) == {
        "citation_path": "us-xx/statute/17014",
        "method": "exact-own-scope",
    }


def test_a_root_with_only_navigation_below_it_never_resolves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write(
        tmp_path,
        OWN,
        [("us-xx/statute/17014", None, "document"), ("us-xx/statute/17014/block-1", MENU, "block")],
    )
    index = _index(monkeypatch, tmp_path)
    assert "us-xx/statute/17014" not in index[0]
    assert "us-xx/statute/17014/block-1" not in index[0]
    assert _resolve(index, "us-xx/statute/17014", parsed=True) is None


def test_another_scope_resolves_only_with_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write(tmp_path, OWN, [("us-xx/statute/17014", None, "document")])
    _write(
        tmp_path,
        OTHER,
        [
            ("us-xx/statute/17014", LAW, "section"),
            ("us-xx/statute/17016", MENU, "section"),
            ("us-xx/statute/17017/document-1", LAW, "document"),
            ("us-xx/statute/17018", LAW, "section"),
        ],
    )
    index = _index(monkeypatch, tmp_path)
    assert _resolve(index, "us-xx/statute/17014", parsed=False) == {
        "citation_path": "us-xx/statute/17014",
        "method": "exact-cross-scope",
    }
    assert _resolve(index, "us-xx/statute/17016", parsed=True) is None
    assert _resolve(index, "us-xx/statute/17017", parsed=False) == {
        "citation_path": "us-xx/statute/17017/document-1",
        "method": "document-fallback-cross-scope",
    }
    assert _resolve(index, "/us-xx//statute/17018/", parsed=False) == {
        "citation_path": "us-xx/statute/17018",
        "method": "normalized-format-cross-scope",
    }


def test_planned_scope_needs_all_three_parts() -> None:
    entry = {"jurisdiction": "us-ca", "document_class": "statute", "proposed_version": "v"}
    assert batch._planned_scope(entry) == ("us-ca", "statute", "v")
    assert batch._planned_scope({**entry, "proposed_version": ""}) is None


RECOVERY = ("us-ca", "statute", "2026-07-13-recovery")
CHAPTER = (
    "us-ca",
    "statute",
    "2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7-r2026-09-24-preserve-tables",
)


def test_the_us_ca_recovery_targets_resolve_to_what_carries_their_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The ten R&TC sections resolve to the chapter scope; WIC 11450(a)(1)(A) does not resolve.

    Both scopes are read with their retained pages (linked, not copied), so the
    navigation test runs on the scope that resolves the targets as well.
    """
    corpus = REPO_ROOT / "data/corpus"
    for scope in (RECOVERY, CHAPTER):
        provisions = Path("provisions", *scope[:2], f"{scope[2]}.jsonl")
        (tmp_path / provisions).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / provisions).symlink_to(corpus / provisions)
        sources = Path("sources", *scope)
        (tmp_path / sources).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / sources).symlink_to(corpus / sources, target_is_directory=True)
    carriers, normalized = _index(monkeypatch, tmp_path)
    for parsed in (False, True):
        rtc = batch._resolve_across_ingested_scopes(
            "us-ca/statute/rtc/17014", carriers, normalized, own_scope=RECOVERY, include_own=parsed
        )
        assert rtc == {"citation_path": "us-ca/statute/rtc/17014", "method": "exact-cross-scope"}
        wic = batch._resolve_across_ingested_scopes(
            "us-ca/statute/wic/11450/a/1/A",
            carriers,
            normalized,
            own_scope=RECOVERY,
            include_own=parsed,
        )
        assert wic is None
    # The recovery scope's rows that carry text are the R&TC roots and their
    # section-text blocks; no menu block and nothing from the WIC picker.
    recovery_text = sorted(path for path, scopes in carriers.items() if RECOVERY in scopes)
    assert all("/wic/" not in path and not path.endswith("/block-1") for path in recovery_text)
    assert len(recovery_text) == 20
    # Every R&TC section the recovery scope names is carried by the chapter scope.
    assert all(
        CHAPTER in carriers[f"us-ca/statute/rtc/{section}"]
        for section in ("17014", "17016", "17017", "17029", "17034", "17038", "17053.6")
    )


def test_only_a_parsed_result_lets_its_own_scope_vouch() -> None:
    """The recorded result decides: an earlier parse that a run carries forward
    is parsed, and a reparse that failed is not."""
    assert batch._own_scope_vouches({"parsed": True})
    assert not batch._own_scope_vouches({"parsed": False})
    assert not batch._own_scope_vouches({})


def test_the_index_fetches_sources_as_well_as_provisions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[Path]] = []

    def record(paths, **kwargs):  # type: ignore[no-untyped-def]
        calls.append([Path(path) for path in paths])

    monkeypatch.setattr(batch, "require_materialized", record)
    (tmp_path / "provisions").mkdir()
    _index(monkeypatch, tmp_path)
    assert calls == [[tmp_path / "provisions", tmp_path / "sources"]]


def _batch_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A three-document plan whose doc-b an earlier run parsed into OWN; returns the report.

    doc-b's snapshot sits in recovered-fetched without its provenance sidecar,
    so any attempt to reparse it fails.
    """
    base = tmp_path / "corpus"
    _write(base, OWN, [("us-xx/statute/200", LAW, "section")])
    fetched = tmp_path / "recovered-fetched"
    fetched.mkdir()
    (fetched / "doc-b.xml").write_text("<law/>", encoding="utf-8")

    def document(document_id: str, target: str) -> dict[str, object]:
        return {
            "document_id": document_id,
            "jurisdiction": OWN[0],
            "document_class": OWN[1],
            "proposed_version": OWN[2],
            "parser": "generic",
            "official_url": f"https://example.gov/{document_id}",
            "covers_citation_paths": [target],
        }

    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "documents": [
                    document("doc-a", "us-xx/statute/100"),
                    document("doc-b", "us-xx/statute/200"),
                    document("doc-c", "us-xx/statute/300"),
                ]
            }
        )
    )
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {"doc-b": {"parsed": True, "rows": 1, "citations_resolved": "1/1", "issues": []}}
        )
    )
    for name, value in {
        "PLAN": plan,
        "REPORT": report,
        "BASE": base,
        "FETCHED": fetched,
        "REPO": tmp_path,
    }.items():
        monkeypatch.setattr(batch, name, value)
    monkeypatch.setattr(batch, "REPROCESS", {"doc-b"})
    return report


@pytest.mark.parametrize(
    ("body", "kind", "resolved"),
    [(None, "document", False), (MENU, "section", False), (LAW, "section", True)],
)
def test_a_successful_parse_reports_targets_without_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    body: str | None,
    kind: str,
    resolved: bool,
) -> None:
    """A parsed row's path alone cannot suppress the missing-text diagnostic."""
    report = _batch_run(monkeypatch, tmp_path)
    _write(batch.BASE, OWN, [])
    (batch.FETCHED / "doc-b.xml.provenance.json").write_text("{}")
    monkeypatch.setenv("AXIOM_RECOVERY_ONLY_DOCUMENT_ID", "doc-b")
    monkeypatch.setenv("AXIOM_RECOVERY_SKIP_MANIFESTS", "1")
    monkeypatch.setattr(
        batch, "_load_file", lambda path: (PAGE.encode(), {"url": "https://example.gov/doc-b"})
    )

    def parse(
        entry: dict[str, object],
        path: Path,
        data: bytes,
        provenance: dict[str, object],
        source_key: str,
    ) -> tuple[list[SourceInventoryItem], list[ProvisionRecord]]:
        target = "us-xx/statute/200"
        return (
            [SourceInventoryItem(citation_path=target, source_path=source_key)],
            [
                ProvisionRecord(
                    jurisdiction=OWN[0],
                    document_class=OWN[1],
                    version=OWN[2],
                    citation_path=target,
                    body=body,
                    kind=kind,
                    source_path=source_key,
                )
            ],
        )

    monkeypatch.setattr(batch, "_parse", parse)
    assert batch.main() == 0
    result = json.loads(report.read_text())["doc-b"]
    assert result["parsed"] is True
    assert result["citations_resolved"] == ("1/1" if resolved else "0/1")
    assert result["unresolved_citations"] == ([] if resolved else ["us-xx/statute/200"])
    assert result["issues"] == (
        []
        if resolved
        else ["not all planned citation paths resolve to text in this document's parsed rows"]
    )


def test_single_document_reruns_keep_every_earlier_parse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Two runs limited to other documents leave an earlier parse, and its own-scope rows, intact.

    doc-b is in REPROCESS with a snapshot that cannot parse, so a run that did
    not honour the one-document limit would record it unparsed.
    """
    report = _batch_run(monkeypatch, tmp_path)
    for only in ("doc-a", "doc-c"):
        monkeypatch.setenv("AXIOM_RECOVERY_ONLY_DOCUMENT_ID", only)
        assert batch.main() == 0
        results = json.loads(report.read_text())
        assert results["doc-b"]["parsed"] is True
        assert results["doc-b"]["resolved_citations"] == [
            {
                "requested": "us-xx/statute/200",
                "citation_path": "us-xx/statute/200",
                "method": "exact-own-scope",
            }
        ]
        assert results["doc-a"]["parsed"] is False
        assert results["doc-a"]["resolution_class"] == "needs-fetch"
        assert results["_summary"]["resolved"] == 1


def test_a_failed_reparse_answers_the_same_in_every_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A REPROCESS document whose reparse fails stops vouching for itself at once.

    Its rows from the earlier parse are still in its own scope, but the first
    failed run, a full rerun and a rerun limited to another document all record
    the same unparsed, unresolved result with its provenance error.
    """
    report = _batch_run(monkeypatch, tmp_path)
    answers = []
    for only in (None, None, "doc-a"):
        if only is None:
            monkeypatch.delenv("AXIOM_RECOVERY_ONLY_DOCUMENT_ID", raising=False)
        else:
            monkeypatch.setenv("AXIOM_RECOVERY_ONLY_DOCUMENT_ID", only)
        assert batch.main() == 0
        results = json.loads(report.read_text())
        result = results["doc-b"]
        summary = results["_summary"]
        answers.append(
            {
                **{
                    key: result.get(key)
                    for key in (
                        "parsed",
                        "issues",
                        "citations_resolved",
                        "resolved_citations",
                        "unresolved_citations",
                        "resolution_class",
                        "exclusion_reason",
                    )
                },
                "remaining": summary["remaining_classes"]["unrecoverable-parse"],
                "provenance_ok": summary["signing_checklist"][
                    "all_fetched_files_have_valid_provenance"
                ],
            }
        )
    assert answers[0] == answers[1] == answers[2]
    assert answers[0]["parsed"] is False
    assert answers[0]["resolved_citations"] == []
    assert answers[0]["unresolved_citations"] == ["us-xx/statute/200"]
    assert answers[0]["resolution_class"] == "unrecoverable-parse"
    assert answers[0]["remaining"] == {"count": 1, "documents": ["doc-b"]}
    assert answers[0]["provenance_ok"] is False


def test_a_class_counts_only_its_unresolved_citations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A partly resolved document adds only its unresolved targets to its class's count."""
    report = _batch_run(monkeypatch, tmp_path)
    plan = json.loads(batch.PLAN.read_text())
    for document in plan["documents"]:
        if document["document_id"] == "doc-a":
            document["covers_citation_paths"] = ["us-xx/statute/100", "us-xx/statute/310"]
    batch.PLAN.write_text(json.dumps(plan))
    _write(batch.BASE, OTHER, [("us-xx/statute/310", LAW, "section")])
    monkeypatch.setenv("AXIOM_RECOVERY_ONLY_DOCUMENT_ID", "doc-c")
    assert batch.main() == 0
    results = json.loads(report.read_text())
    assert results["doc-a"]["citations_resolved"] == "1/2"
    assert results["doc-a"]["resolution_class"] == "needs-fetch"
    needs_fetch = results["_summary"]["remaining_classes"]["needs-fetch"]
    assert needs_fetch == {"count": 2, "documents": ["doc-a", "doc-c"]}


def test_a_run_limited_to_a_document_answers_it_as_a_full_run_would(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Once a failed document's snapshot is gone, a run limited to it reports the
    missing snapshot, exactly as a full run does, not the earlier failure."""
    report = _batch_run(monkeypatch, tmp_path)
    monkeypatch.delenv("AXIOM_RECOVERY_ONLY_DOCUMENT_ID", raising=False)
    assert batch.main() == 0
    assert json.loads(report.read_text())["doc-b"]["resolution_class"] == "unrecoverable-parse"
    (batch.FETCHED / "doc-b.xml").unlink()
    after_failure = report.read_text()
    answers = []
    for only in (None, "doc-b"):
        report.write_text(after_failure)
        if only is None:
            monkeypatch.delenv("AXIOM_RECOVERY_ONLY_DOCUMENT_ID", raising=False)
        else:
            monkeypatch.setenv("AXIOM_RECOVERY_ONLY_DOCUMENT_ID", only)
        assert batch.main() == 0
        results = json.loads(report.read_text())
        answers.append(
            (
                results["doc-b"],
                results["_summary"]["signing_checklist"]["all_fetched_files_have_valid_provenance"],
            )
        )
    assert answers[0] == answers[1]
    result, provenance_ok = answers[1]
    assert result["parsed"] is False
    assert result["issues"] == ["official source snapshot is not present in recovered-fetched"]
    assert result["resolution_class"] == "needs-fetch"
    assert provenance_ok is True
