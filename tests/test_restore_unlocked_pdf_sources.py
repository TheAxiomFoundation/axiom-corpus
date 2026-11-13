"""scripts/restore_unlocked_pdf_sources.py: the run-id rename and the restored sources.

The rename rewrites serialized fields in place. The properties check, for any
row or item, that it changes exactly the fields it names (the rest of each
line stays byte for byte), fails closed on anything else, and is idempotent.
The last tests read the real tree: each restored scope's rows name one locked
file whose sha256 and size are the ones the script restores.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "restore_unlocked_pdf_sources.py"

_spec = importlib.util.spec_from_file_location("restore_unlocked_pdf_sources", SCRIPT)
assert _spec and _spec.loader
restore = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = restore
_spec.loader.exec_module(restore)

RENAME = restore.SNAP_QC_RENAME
RestoreError = restore.RestoreError


def _row(**extra: object) -> dict[str, object]:
    return {
        "body": "Page text.",
        "citation_path": "us/guidance/usda/fns/snap-qc-fy2024-technical-documentation/page-1",
        "id": "855350de-93aa-51db-a862-10850587b5ed",
        "metadata": {"content_type": "application/pdf", "primary_source": True},
        "source_format": "pdf",
        "source_path": RENAME.old_source_path,
        "version": RENAME.run_id,
        **extra,
    }


def _jsonl(rows: list[dict[str, object]]) -> str:
    # The extractor's serialization: sorted keys, default separators.
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def test_rename_provisions_changes_only_version_and_source_path() -> None:
    payload = _jsonl([_row(), _row(citation_path="us/guidance/x/page-2", body=None)])

    rewritten = restore.rename_provisions(payload, RENAME)

    assert rewritten == payload.replace(
        f'"version": "{RENAME.run_id}"', f'"version": "{RENAME.version}"'
    ).replace(RENAME.old_source_path, RENAME.new_source_path)
    rows = [json.loads(line) for line in rewritten.splitlines()]
    assert {row["version"] for row in rows} == {RENAME.version}
    assert {row["source_path"] for row in rows} == {RENAME.new_source_path}


def test_rename_provisions_refuses_a_row_without_the_run_id() -> None:
    payload = _jsonl([_row(), _row(version=RENAME.version)])
    with pytest.raises(RestoreError, match="line 2"):
        restore.rename_provisions(payload, RENAME)


def test_rename_provisions_refuses_another_source() -> None:
    payload = _jsonl([_row(source_path="sources/us/guidance/other/x.pdf")])
    with pytest.raises(RestoreError, match="does not name the run id"):
        restore.rename_provisions(payload, RENAME)


def test_rename_inventory_changes_only_item_source_paths() -> None:
    inventory = {
        "items": [
            {"citation_path": "a", "sha256": "0" * 64, "source_path": RENAME.old_source_path},
            {"citation_path": "b", "sha256": "0" * 64, "source_path": RENAME.old_source_path},
        ]
    }
    payload = json.dumps(inventory, indent=2) + "\n"

    rewritten = restore.rename_inventory(payload, RENAME)

    assert rewritten == payload.replace(RENAME.old_source_path, RENAME.new_source_path)


def test_rename_inventory_refuses_the_run_id_elsewhere() -> None:
    inventory = {
        "items": [
            {
                "citation_path": "a",
                "metadata": {"note": RENAME.run_id},
                "source_path": RENAME.old_source_path,
            }
        ]
    }
    with pytest.raises(RestoreError, match="outside item source paths"):
        restore.rename_inventory(json.dumps(inventory, indent=2), RENAME)


def test_rename_coverage_changes_only_the_version() -> None:
    coverage = {"complete": True, "provision_count": 201, "version": RENAME.run_id}
    payload = json.dumps(coverage, indent=2, sort_keys=True) + "\n"

    rewritten = restore.rename_coverage(payload, RENAME)

    assert json.loads(rewritten) == {**coverage, "version": RENAME.version}
    assert rewritten == payload.replace(RENAME.run_id, RENAME.version)


def test_rename_coverage_refuses_another_version() -> None:
    with pytest.raises(RestoreError, match="not the run id"):
        restore.rename_coverage(json.dumps({"version": RENAME.version}), RENAME)


# Text that JSON-escapes in several ways, and may itself mention the run id.
_text = st.one_of(
    st.text(max_size=40),
    st.sampled_from([RENAME.run_id, f'"version": "{RENAME.run_id}"', RENAME.old_source_path]),
)
_extra = st.dictionaries(
    st.sampled_from(["body", "heading", "citation_label", "kind", "language", "ordinal"]),
    st.one_of(_text, st.none(), st.integers()),
    max_size=4,
)


@settings(max_examples=200, deadline=None)
@given(st.lists(_extra, min_size=1, max_size=6))
def test_rename_provisions_property(extras: list[dict[str, object]]) -> None:
    rows = [_row(**extra) for extra in extras]
    payload = _jsonl(rows)

    rewritten = restore.rename_provisions(payload, RENAME)

    after = [json.loads(line) for line in rewritten.splitlines()]
    assert after == [
        {**row, "version": RENAME.version, "source_path": RENAME.new_source_path} for row in rows
    ]
    # Each line keeps its bytes outside the two values.
    for before_line, after_line in zip(payload.splitlines(), rewritten.splitlines(), strict=True):
        assert len(after_line) == len(before_line) - 2 * (len(RENAME.run_id) - len(RENAME.version))


@settings(max_examples=100, deadline=None)
@given(st.lists(_extra, min_size=1, max_size=4), st.integers(min_value=0, max_value=3))
def test_rename_provisions_fails_closed_on_any_foreign_row(
    extras: list[dict[str, object]], position: int
) -> None:
    rows = [_row(**extra) for extra in extras]
    rows.insert(min(position, len(rows)), _row(version="2026-07-08-other"))
    with pytest.raises(RestoreError):
        restore.rename_provisions(_jsonl(rows), RENAME)


def _scope_repo(tmp_path: Path) -> Path:
    scope = f"{RENAME.jurisdiction}/{RENAME.document_class}/{RENAME.version}"
    files = {
        f"data/corpus/provisions/{scope}.jsonl": _jsonl([_row()]),
        f"data/corpus/inventory/{scope}.json": json.dumps(
            {"items": [{"citation_path": "a", "source_path": RENAME.old_source_path}]}, indent=2
        ),
        f"data/corpus/coverage/{scope}.json": json.dumps({"version": RENAME.run_id}, indent=2),
    }
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def test_apply_rename_is_idempotent(tmp_path: Path) -> None:
    repo = _scope_repo(tmp_path)

    first = restore.apply_rename(repo, RENAME)
    snapshot = {path: (repo / path).read_bytes() for path in first}
    second = restore.apply_rename(repo, RENAME)

    assert len(first) == 3
    assert second == []
    assert {path: (repo / path).read_bytes() for path in first} == snapshot


def test_check_reports_a_missing_or_wrong_source(tmp_path: Path, monkeypatch) -> None:
    payload = b"%PDF-1.4 restored bytes"
    restoration = restore.Restoration(
        "us",
        "guidance",
        "v1",
        "sources/us/guidance/v1/official-documents/doc.pdf",
        hashlib.sha256(payload).hexdigest(),
        len(payload),
    )
    monkeypatch.setattr(restore, "RESTORATIONS", (restoration,))
    provisions = tmp_path / "data/corpus/provisions/us/guidance/v1.jsonl"
    provisions.parent.mkdir(parents=True)
    provisions.write_text(json.dumps({"source_path": restoration.source_path}) + "\n")
    source = tmp_path / "data/corpus" / restoration.source_path

    assert restore.check(tmp_path) == [
        "us/guidance/v1: data/corpus/sources/us/guidance/v1/official-documents/doc.pdf is missing"
    ]
    source.parent.mkdir(parents=True)
    source.write_bytes(payload[:-1] + b"X")
    assert restore.check(tmp_path) == [
        "us/guidance/v1: data/corpus/sources/us/guidance/v1/official-documents/doc.pdf has other bytes"
    ]
    source.write_bytes(payload)
    assert restore.check(tmp_path) == []


def test_restored_sources_are_locked_with_the_restored_bytes() -> None:
    from axiom_corpus.corpus.corpus_locks import load_locks

    locks = load_locks(REPO_ROOT)
    for restoration in restore.RESTORATIONS:
        entry = locks.by_path.get(f"data/corpus/{restoration.source_path}")
        assert entry is not None, restoration.scope
        assert (entry.sha256, entry.size) == (restoration.sha256, restoration.size)


def test_restored_scopes_name_only_their_restored_source() -> None:
    assert restore.check(REPO_ROOT) == []
