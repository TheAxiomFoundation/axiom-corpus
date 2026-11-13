"""Tiny actual-Git checks for endpoint and historical CI prefetch, without real corpus data."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/prefetch-git-blobs.py"
spec = importlib.util.spec_from_file_location("ci_git_blob_prefetch", SCRIPT)
assert spec and spec.loader
prefetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prefetch)


def git(repo: Path, *args: str, input: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input,
        capture_output=True,
        check=True,
        env={
            **os.environ,
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "Tiny fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Tiny fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        },
        timeout=15,
    ).stdout


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").decode().strip()


def oid(repo: Path, ref: str, path: str) -> str:
    return git(repo, "rev-parse", f"{ref}:{path}").decode().strip()


def clone(origin: Path, target: Path, *, hydrate: bool = True) -> Path:
    git(
        target.parent,
        "clone",
        "-q",
        "--filter=blob:none",
        "--no-checkout",
        origin.as_uri(),
        str(target),
    )
    if hydrate:
        records = git(target, "ls-tree", "-r", "--format=%(objecttype) %(objectname)", "HEAD")
        objects = sorted(
            {line.split()[1] for line in records.splitlines() if line.startswith(b"blob ")}
        )
        git(
            target,
            "fetch",
            "--no-tags",
            "--filter=blob:none",
            "origin",
            "--stdin",
            input=b"\n".join(objects) + b"\n",
        )
        git(target, "checkout", "-q", "main")
    return target


@pytest.fixture(autouse=True)
def offline_git_environment(monkeypatch):
    monkeypatch.setenv("GIT_NO_LAZY_FETCH", "1")
    monkeypatch.setenv("GIT_NO_REPLACE_OBJECTS", "1")


@pytest.fixture
def history(tmp_path):
    from axiom_corpus.corpus.corpus_locks import CorpusLock, LockEntry, write_lock

    seed = tmp_path / "seed"
    git(tmp_path, "init", "-q", "-b", "main", "--object-format=sha1", str(seed))
    (seed / "README.md").write_text("tiny synthetic fixture\n")
    unrelated = seed / "unrelated-past.bin"
    unrelated.write_bytes(b"never required\n" * 16)
    registry = seed / "manifests/withdrawn-scopes.yaml"
    registry.parent.mkdir()
    registry.write_text("scopes: []\n# first main version\n")
    selector = seed / "manifests/releases/fixture.json"
    selector.parent.mkdir()
    selector.write_text('{"version":1}\n')
    first_policy_commit = commit(seed, "old unrelated payload and release policy")
    registry_oid = oid(seed, "HEAD", registry.relative_to(seed).as_posix())
    selector_oid = oid(seed, "HEAD", selector.relative_to(seed).as_posix())
    unrelated_oid = oid(seed, "HEAD", unrelated.name)
    unrelated.unlink()
    rel = "data/corpus/provisions/nz/statute/v1.jsonl"
    deleted = "data/corpus/coverage/nz/statute/v0.json"
    for name, data in [(rel, b'{"tiny":true}\n'), (deleted, b'{"deleted":true}\n')]:
        path = seed / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    registry.write_text("scopes: []\n# second main version\n")
    selector.write_text('{"version":2}\n')
    merge_base = commit(seed, "pre-migration tree")
    payload_oid, deleted_oid = oid(seed, "HEAD", rel), oid(seed, "HEAD", deleted)
    entry = LockEntry(rel, hashlib.sha256(b'{"tiny":true}\n').hexdigest(), 14, payload_oid)
    remote_only = LockEntry("data/corpus/coverage/nz/statute/v1.json", "0" * 64, 3)
    git(seed, "checkout", "-q", "-b", "base")
    side = seed / "data/corpus/provisions/nz/statute/side.jsonl"
    side.write_bytes(b'{"side":true}\n')
    registry.write_text("scopes: []\n# side-only policy\n")
    commit(seed, "side-only protected bytes")
    side_oid = oid(seed, "HEAD", side.relative_to(seed).as_posix())
    side_registry_oid = oid(seed, "HEAD", registry.relative_to(seed).as_posix())
    side.unlink()
    registry.write_text("scopes: []\n# second main version\n")
    for name in [rel, deleted]:
        (seed / name).unlink()
    base_meta = seed / "only-base.json"
    base_meta.write_text('{"base_only":true}\n')
    base_lock = write_lock(seed, CorpusLock.from_entries(("nz", "statute", "v1"), [entry]))
    base = commit(seed, "base migrates")
    base_lock_oid = oid(seed, "HEAD", base_lock.relative_to(seed).as_posix())
    base_meta_oid = oid(seed, "HEAD", base_meta.name)
    git(seed, "checkout", "-q", "main")
    for name in [rel, deleted]:
        (seed / name).unlink()
    (seed / "README.md").write_text("head metadata changed\n")
    registry.write_text("scopes: []\n# third main version\n")
    selector.write_text('{"version":3}\n')
    lock = write_lock(seed, CorpusLock.from_entries(("nz", "statute", "v1"), [entry, remote_only]))
    head = commit(seed, "head migrates with one R2-only entry")
    origin = tmp_path / "origin.git"
    git(tmp_path, "clone", "--bare", "-q", str(seed), str(origin))
    git(origin, "config", "uploadpack.allowFilter", "true")
    git(seed, "update-ref", "refs/remotes/origin/main", head)
    return {
        "seed": seed,
        "origin": origin,
        "head": head,
        "base": base,
        "merge_base": merge_base,
        "entry": entry,
        "remote_only": remote_only,
        "payload_oid": payload_oid,
        "deleted_oid": deleted_oid,
        "base_lock_oid": base_lock_oid,
        "base_meta_oid": base_meta_oid,
        "unrelated_oid": unrelated_oid,
        "side_oid": side_oid,
        "registry_oid": registry_oid,
        "selector_oid": selector_oid,
        "side_registry_oid": side_registry_oid,
        "first_policy_commit": first_policy_commit,
        "lock_rel": lock.relative_to(seed).as_posix(),
        "rel": rel,
        "side_rel": side.relative_to(seed).as_posix(),
    }


def test_prefetch_closure_and_local_only_guards(history, tmp_path, monkeypatch):
    from axiom_corpus.corpus.corpus_locks import load_locks_at_ref
    from axiom_corpus.corpus.ingest_manifests import first_parent_path_blobs

    repo = clone(history["origin"], tmp_path / "partial")
    calls = []
    actual_git = prefetch.git

    def observe(repo, *args, **kwargs):
        calls.append((args, kwargs))
        return actual_git(repo, *args, **kwargs)

    monkeypatch.setattr(prefetch, "git", observe)
    plan = tmp_path / "plan"
    receipt = prefetch.prepare(repo, history["head"], history["base"], plan, plan_only=True)
    missing = set((plan / "missing-oids.txt").read_text().splitlines())
    assert {
        history[k] for k in ["payload_oid", "deleted_oid", "base_lock_oid", "base_meta_oid"]
    } <= missing
    assert history["unrelated_oid"] not in missing and history["side_oid"] not in missing
    assert receipt["refs"] == {
        **{k: history[k] for k in ["head", "base", "merge_base"]},
        "main": history["head"],
    }
    assert json.loads((plan / "payload-inventory.json").read_text()) == [
        {"oid": history["payload_oid"], "size": 14}
    ]
    assert not any("fetch" in args for args, _kwargs in calls)
    assert prefetch.local_headers(repo, [history["payload_oid"]])[history["payload_oid"]] is None
    result = prefetch.prepare(
        repo, history["head"], history["base"], tmp_path / "result", plan_only=False
    )
    fetches = [kwargs["input"] for args, kwargs in calls if "fetch" in args]
    assert fetches == [(plan / "missing-oids.txt").read_bytes()]
    assert result["missing_after"] == 0 and result["missing_before"] == len(missing)
    assert result["missing_oid_set_sha256"] == hashlib.sha256(fetches[0]).hexdigest()
    assert not load_locks_at_ref(repo, history["base"]).errors
    assert prefetch.local_headers(repo, [history["unrelated_oid"], history["side_oid"]]) == {
        history["unrelated_oid"]: None,
        history["side_oid"]: None,
    }
    held = first_parent_path_blobs(
        repo,
        history["head"],
        {
            history["rel"]: {history["payload_oid"]},
            history["side_rel"]: {history["side_oid"]},
        },
    )
    assert held == {(history["rel"], history["payload_oid"])}


def test_schedule_uses_head_and_main_history_and_exempts_no_git_blob_entries(history, tmp_path):
    repo = clone(history["origin"], tmp_path / "partial")
    out = tmp_path / "schedule"
    receipt = prefetch.prepare(repo, history["head"], None, out, plan_only=False)
    assert receipt["refs"] == {"head": history["head"], "main": history["head"]}
    assert receipt["payload_object_count"] == 1
    assert set((out / "missing-oids.txt").read_text().splitlines()) == {
        history["payload_oid"],
        history["registry_oid"],
        history["selector_oid"],
        oid(history["seed"], history["merge_base"], "manifests/withdrawn-scopes.yaml"),
        oid(history["seed"], history["merge_base"], "manifests/releases/fixture.json"),
    }
    assert receipt["missing_after"] == 0


def test_historical_release_policy_reads_remain_strict_and_available(
    history, tmp_path, monkeypatch
):
    from tests import test_release_policy_repository as release_policy_test

    repo = clone(history["origin"], tmp_path / "partial")
    monkeypatch.setattr(release_policy_test, "REPO_ROOT", repo)
    commit_at = history["first_policy_commit"]
    with pytest.raises(subprocess.CalledProcessError):
        release_policy_test._show(commit_at, "manifests/withdrawn-scopes.yaml")
    out = tmp_path / "history-proof"
    prefetch.prepare(repo, history["head"], history["base"], out, plan_only=False)
    assert (
        release_policy_test._show(commit_at, "manifests/withdrawn-scopes.yaml")
        == "scopes: []\n# first main version\n"
    )
    assert (
        release_policy_test._show(commit_at, "manifests/releases/fixture.json") == '{"version":1}\n'
    )
    assert prefetch.local_headers(repo, [history["side_registry_oid"]]) == {
        history["side_registry_oid"]: None
    }


def test_shallow_checkout_and_head_mismatch_are_rejected(history, tmp_path):
    repo = clone(history["origin"], tmp_path / "partial")
    with pytest.raises(ValueError, match="expected head differs"):
        prefetch.prepare(repo, history["base"], None, tmp_path / "wrong-head", plan_only=True)
    shallow = tmp_path / "shallow"
    git(tmp_path, "clone", "-q", "--depth=1", history["origin"].as_uri(), str(shallow))
    with pytest.raises(ValueError, match="full commit/tree history"):
        prefetch.prepare(shallow, history["head"], None, tmp_path / "wrong-history", plan_only=True)


@pytest.mark.parametrize("kind", ["size", "type", "malformed", "collision", "missing"])
def test_bad_head_lock_or_required_object_is_rejected(history, tmp_path, kind):
    from axiom_corpus.corpus.corpus_locks import CorpusLock, LockEntry, write_lock

    seed = history["seed"]
    entry = history["entry"]
    value = LockEntry(
        entry.path,
        entry.sha256,
        15 if kind == "size" else 14,
        history["head"] if kind == "type" else "1" * 40 if kind == "missing" else entry.git_blob,
    )
    entries = [value]
    if kind == "collision":
        entries.append(
            LockEntry("data/corpus/inventory/nz/statute/v1.json", entry.sha256, 15, entry.git_blob)
        )
    lock = write_lock(seed, CorpusLock.from_entries(("nz", "statute", "v1"), entries))
    if kind == "malformed":
        lock.write_text('{"schema_version":"bad"}\n')
    head = commit(seed, "invalid fixture expectation")
    git(seed, "remote", "add", "origin", history["origin"].as_uri())
    with pytest.raises(ValueError):
        prefetch.prepare(seed, head, None, tmp_path / "bad", plan_only=False)
    assert not (tmp_path / "bad/receipt.json").exists()


def test_direct_parser_requires_offline_flags_and_cli_forces_them(history, tmp_path, monkeypatch):
    repo = clone(history["origin"], tmp_path / "unhydrated", hydrate=False)
    lock_oid = oid(repo, "HEAD", history["lock_rel"])
    monkeypatch.setenv("GIT_NO_LAZY_FETCH", "0")
    monkeypatch.setenv("GIT_NO_REPLACE_OBJECTS", "0")
    with pytest.raises(ValueError, match="offline Git environment"):
        prefetch.inventory(repo, history["head"], None)
    trace = tmp_path / "trace.jsonl"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--head-ref",
            history["head"],
            "--output-dir",
            str(tmp_path / "unhydrated-result"),
            "--plan-only",
        ],
        env={**os.environ, "GIT_TRACE2_EVENT": str(trace)},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert run.returncode == 1
    assert prefetch.local_headers(repo, [lock_oid])[lock_oid] is None
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    assert not any(e.get("event") == "start" and "fetch" in e.get("argv", []) for e in events)


@pytest.mark.parametrize(
    "reply", [b"", b"1 missing\n", b"a" * 40 + b" blob +1\n", b"a" * 40 + b" tree 1\n"]
)
def test_malformed_local_headers_fail_closed(monkeypatch, reply):
    monkeypatch.setattr(prefetch, "git", lambda *_args, **_kwargs: reply)
    with pytest.raises(ValueError):
        prefetch.local_headers(Path("/nonexistent-fixture-repository"), ["a" * 40])
