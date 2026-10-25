"""Restored PDF replay inputs stay portable and keep the original locked hashes."""

from __future__ import annotations

import json
import shlex
from pathlib import Path, PurePosixPath

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

REPO = Path(__file__).resolve().parents[1]
SCOPES = (
    "us-sd/manual/2026-05-27-sd-snap-manual",
    "us/guidance/2026-07-08-snap-qc-fy2024-technical-documentation",
)
RUN_NOTE = REPO / "docs/ingest-runs/2026-10-13-restore-unlocked-pdf-sources.md"
PREFIX = ["uv", "run", "--extra", "dev", "python", "scripts/restore_unlocked_pdf_sources.py"]


@pytest.mark.parametrize("scope", SCOPES)
def test_restored_manifest_records_a_runnable_portable_command(scope: str) -> None:
    manifest = json.loads((REPO / f".axiom/ingest-manifests/{scope}.json").read_text())
    lock = json.loads((REPO / f".axiom/corpus-locks/{scope}.json").read_text())
    (source,) = [entry for entry in lock["files"] if entry["path"].endswith(".pdf")]

    assert shlex.split(manifest["command"]["text"]) == [
        *PREFIX,
        "--from",
        f"{source['sha256']}={source['path']}",
    ]
    assert manifest["applied_files"] == [
        {"path": entry["path"], "sha256": entry["sha256"]} for entry in lock["files"]
    ]


@settings(deadline=None)
@given(
    scope=st.sampled_from(SCOPES),
    checkout=st.lists(
        st.from_regex(r"[a-z][a-z0-9_-]{0,15}", fullmatch=True), min_size=1, max_size=5
    ),
)
def test_replay_keeps_the_original_source_hash_in_any_checkout(
    scope: str, checkout: list[str]
) -> None:
    manifest = json.loads((REPO / f".axiom/ingest-manifests/{scope}.json").read_text())
    args = shlex.split(manifest["command"]["text"])
    assert args[:6] == PREFIX
    assert args[6] == "--from"
    digest, relative = args[7].split("=", 1)
    root = PurePosixPath(*checkout)
    resolved = root / relative
    assert resolved.is_relative_to(root)
    assert ".." not in resolved.parts
    assert resolved.relative_to(root).as_posix() == relative
    (source,) = [entry for entry in manifest["applied_files"] if entry["path"].endswith(".pdf")]
    assert (digest, relative) == (source["sha256"], source["path"])


def test_restoration_note_uses_portable_source_inputs() -> None:
    text = RUN_NOTE.read_text()
    for local_spelling in ("~/", "$HOME", "/Users/", "/private/"):
        assert local_spelling not in text
    for scope in SCOPES:
        manifest = json.loads((REPO / f".axiom/ingest-manifests/{scope}.json").read_text())
        replay_input = shlex.split(manifest["command"]["text"])[-1]
        assert f"--from {replay_input}" in text
