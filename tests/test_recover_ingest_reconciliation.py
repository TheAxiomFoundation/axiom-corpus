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
import shutil
from pathlib import Path

import pytest

import scripts.recover_ingest_batch as batch

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
    """The ten R&TC sections resolve to the chapter scope; WIC 11450(a)(1)(A) does not resolve."""
    corpus = REPO_ROOT / "data/corpus"
    for scope in (RECOVERY, CHAPTER):
        relative = Path("provisions", *scope[:2], f"{scope[2]}.jsonl")
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(corpus / relative, tmp_path / relative)
    shutil.copytree(corpus / "sources" / Path(*RECOVERY), tmp_path / "sources" / Path(*RECOVERY))
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
