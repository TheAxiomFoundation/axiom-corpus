"""The CI object preflight must not succeed through cache or remote fallback."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/verify-git-blobs.py"
spec = importlib.util.spec_from_file_location("ci_git_blob_preflight", SCRIPT)
assert spec and spec.loader
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def git(repo: Path, *args: str, input: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input,
        capture_output=True,
        check=True,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str]:
    git(tmp_path, "init", "-q", "--object-format=sha1")
    oid = git(tmp_path, "hash-object", "-w", "--stdin", input=b"tiny fixture\n").decode().strip()
    return tmp_path, oid


def write_inventory(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload))
    return path


def test_actual_local_git_checks_objects_and_cli(repo, tmp_path):
    root, oid = repo
    inventory = write_inventory(tmp_path / "inventory.json", [{"oid": oid, "size": 13}] * 2)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(root), "--inventory", str(inventory)],
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "0"},
        check=True,
    )
    assert json.loads(result.stdout) == {
        "object_count": 1,
        "total_expected_bytes": 13,
        "oid_set_sha256": hashlib.sha256(f"{oid}\n".encode()).hexdigest(),
    }


def test_actual_missing_object_fails_with_warm_cache_and_available_fake_remote(repo, tmp_path):
    from axiom_corpus.corpus.content_store import ContentCache, ensure_cached
    from axiom_corpus.corpus.corpus_locks import LockEntry

    class FakeRemote:
        name = "fake-r2"
        calls = 0

        def open(self, _entry):
            self.calls += 1
            return iter([b"tiny fixture\n"])

    root, _oid = repo
    missing = "1" * 40
    remote = FakeRemote()
    entry = LockEntry(
        "data/corpus/provisions/nz/statute/v1.jsonl",
        hashlib.sha256(b"tiny fixture\n").hexdigest(),
        13,
        missing,
    )
    cache = ContentCache(tmp_path / "warm-cache")
    ensure_cached(entry, cache, [remote])
    assert ensure_cached(entry, cache, [remote])[1] == "cache"
    assert remote.calls == 1
    inventory = write_inventory(tmp_path / "inventory.json", [{"oid": missing, "size": 13}])
    assert preflight.main(["--repo", str(root), "--inventory", str(inventory)]) == 1
    assert remote.calls == 1


def test_actual_type_size_and_unsupported_repository_format(repo, tmp_path):
    root, oid = repo
    tree = git(root, "mktree", input=b"").decode().strip()
    with pytest.raises(ValueError, match="expected blob"):
        preflight.verify_inventory(root, {tree: 0})
    with pytest.raises(ValueError, match="wrong blob size"):
        preflight.verify_inventory(root, {oid: 12})
    other = tmp_path / "sha256-repo"
    other.mkdir()
    git(other, "init", "-q", "--object-format=sha256")
    with pytest.raises(ValueError, match="unsupported Git object format"):
        preflight.verify_inventory(other, {})


def test_empty_inventory_has_a_deterministic_empty_digest(repo):
    root, _oid = repo
    assert preflight.verify_inventory(root, {}) == {
        "object_count": 0,
        "total_expected_bytes": 0,
        "oid_set_sha256": hashlib.sha256(b"").hexdigest(),
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [None],
        [{"oid": "a" * 40}],
        [{"oid": "a" * 40, "size": 1, "extra": 0}],
        [{"oid": "A" * 40, "size": 1}],
        [{"oid": "a" * 39, "size": 1}],
        [{"oid": "a" * 64, "size": 1}],
        [{"oid": "a" * 40, "size": True}],
        [{"oid": "a" * 40, "size": -1}],
        [{"oid": "a" * 40, "size": 1.0}],
        [{"oid": "a" * 40, "size": "1"}],
        [{"oid": "a" * 40, "size": 0}, {"oid": "a" * 40, "size": 1}],
    ],
)
def test_invalid_inventory_is_rejected(tmp_path, payload):
    with pytest.raises(ValueError):
        preflight.load_inventory(write_inventory(tmp_path / "inventory.json", payload))


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text('[{"oid":"' + "a" * 40 + '","size":0,"size":1}]')
    with pytest.raises(ValueError, match="duplicate JSON key"):
        preflight.load_inventory(path)


@pytest.mark.parametrize("reply", ["", "extra\n", "reversed", "duplicate", "size-token"])
def test_reply_count_order_and_malformed_replies_fail_closed(monkeypatch, reply):
    a, b = "a" * 40, "b" * 40
    replies = {
        "reversed": f"{b} blob 2\n{a} blob 1\n",
        "duplicate": f"{a} blob 1\n{a} blob 1\n",
        "size-token": f"{a} blob +1\n{b} blob 2\n",
    }

    def run(command, **kwargs):
        assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        assert kwargs["env"]["GIT_NO_REPLACE_OBJECTS"] == "1"
        assert kwargs["check"] is False
        stdout = "sha1\n" if "rev-parse" in command else replies.get(reply, reply)
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(preflight.subprocess, "run", run)
    with pytest.raises(ValueError):
        preflight.verify_inventory(Path("/nonexistent-fixture-repository"), {b: 2, a: 1})


def test_git_subprocess_failure_is_not_a_success(monkeypatch):
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 128, "", "fixture failure"),
    )
    with pytest.raises(ValueError, match="local Git check failed"):
        preflight.verify_inventory(Path("/nonexistent-fixture-repository"), {})


@settings(max_examples=20, deadline=None)
@given(
    st.dictionaries(
        st.integers(min_value=0, max_value=2**160 - 1),
        st.integers(0, 10**6),
        min_size=1,
        max_size=10,
    )
)
def test_inventory_deduplication_and_conflicting_sizes_property(records):
    payload = [{"oid": f"{oid:040x}", "size": size} for oid, size in records.items()]
    expected = {row["oid"]: row["size"] for row in payload}
    path = Path("/nonexistent-fixture-inventory.json")
    # Reordering and repeating exact metadata must preserve the inventory.
    with patch.object(Path, "read_text", return_value=json.dumps(payload + payload[::-1])):
        assert preflight.load_inventory(path) == expected
    # Every generated example also includes an actual conflicting duplicate.
    conflict = {"oid": payload[0]["oid"], "size": payload[0]["size"] + 1}
    with patch.object(Path, "read_text", return_value=json.dumps(payload + [conflict])):
        with pytest.raises(ValueError, match="conflicting expected sizes"):
            preflight.load_inventory(path)
