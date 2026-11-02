"""Read-only export binds the signed member, its immutable lock, and exact bytes."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from io import BytesIO
from pathlib import Path

import pytest

from axiom_corpus.corpus.content_store import R2ObjectStore, content_key
from axiom_corpus.corpus.corpus_locks import CorpusLock, LockEntry, write_lock
from axiom_corpus.release.manifest import build_unsigned_release_object, sign_release_object
from tests.test_release_manifest import _keys, _valid_content, _validation_for

SPEC = importlib.util.spec_from_file_location(
    "export_release_artifact", Path(__file__).parents[1] / "scripts/export_release_artifact.py"
)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


class ReadOnlyClient:
    def __init__(self, key, body):
        self.key, self.body, self.calls = key, body, []

    def get_object(self, **kwargs):
        bucket, key = kwargs["Bucket"], kwargs["Key"]
        self.calls.append((bucket, key))
        if key != self.key:
            raise KeyError(key)
        return {"Body": BytesIO(self.body)}


@pytest.fixture
def setup(tmp_path):
    content = _valid_content(tmp_path)
    repo = tmp_path / "repo"
    member = next(a for a in content["artifacts"] if a["artifact_class"] == "provisions")
    body = (repo / member["path"]).read_bytes()
    entry = LockEntry(member["path"], member["sha256"], member["bytes"])
    scope = exporter.scope_for_path(entry.path)
    write_lock(repo, CorpusLock(*scope, (entry,)))
    exporter.git(repo, "add", ".axiom")
    exporter.git(repo, "-c", "commit.gpgsign=false", "commit", "-qm", "lock")
    commit = exporter.git(repo, "rev-parse", "HEAD").decode().strip()
    exporter.git(repo, "update-ref", "refs/remotes/origin/main", commit)
    content["git"]["commit"] = commit
    private, public = _keys()
    payload = sign_release_object(build_unsigned_release_object(content), private_key=private)
    client = ReadOnlyClient(content_key(entry.sha256), body)
    args = {
        "run_id": "123",
        "run_attempt": "1",
        "workflow_ref": "test-fixture",
        "repo": repo,
        "payload": payload,
        "public_key": public,
        "release": payload["release"],
        "content_sha": payload["content_sha256"],
        "artifact_path": entry.path,
        "destination": tmp_path / "export",
        "remote": R2ObjectStore(bucket="axiom-corpus", client=client),
    }
    return args, client, body, private


def resign(args, private):
    content = args["payload"]["content"]
    content["validation"] = _validation_for(content)
    args["payload"] = sign_release_object(
        build_unsigned_release_object(content), private_key=private
    )
    args["content_sha"] = args["payload"]["content_sha256"]


def test_exact_valid_read_fixed_layout(setup):
    args, client, body, _ = setup
    receipt = exporter.export_release_artifact(**args)
    assert sorted(p.name for p in args["destination"].iterdir()) == ["payload.bin", "receipt.json"]
    assert (args["destination"] / "payload.bin").read_bytes() == body
    assert receipt["sha256"] == hashlib.sha256(body).hexdigest()
    assert json.loads((args["destination"] / "receipt.json").read_text()) == receipt
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "change",
    ["signature", "identity", "path", "nonprovision", "oversize", "lock", "bucket", "unreachable"],
)
def test_reject_before_remote_read(setup, change):
    args, client, _, private = setup
    if change == "signature":
        args["payload"]["content"]["created_at"] = "2026-07-11T00:00:00Z"
    elif change == "identity":
        args["content_sha"] = "0" * 64
    elif change == "path":
        args["artifact_path"] = "data/corpus/provisions/../../escape"
    elif change == "nonprovision":
        args["artifact_path"] = next(
            a["path"]
            for a in args["payload"]["content"]["artifacts"]
            if a["artifact_class"] != "provisions"
        )
    elif change in ("oversize", "lock"):
        member = next(
            a for a in args["payload"]["content"]["artifacts"] if a["path"] == args["artifact_path"]
        )
        member["bytes"] = (
            exporter.MAX_ARTIFACT_BYTES + 1 if change == "oversize" else member["bytes"] + 1
        )
        resign(args, private)
    elif change == "bucket":
        args["remote"].bucket = "other"
    else:
        exporter.git(args["repo"], "update-ref", "refs/remotes/origin/main", "HEAD~1")
    with pytest.raises((ValueError, RuntimeError, subprocess.CalledProcessError)):
        exporter.export_release_artifact(**args)
    assert client.calls == []
    assert not args["destination"].exists()


@pytest.mark.parametrize("body", [b"wrong", b"", b"x" * 10000])
def test_corrupt_remote_never_leaves_output(setup, body):
    args, client, _, _ = setup
    client.body = body
    with pytest.raises(ValueError):
        exporter.export_release_artifact(**args)
    assert not args["destination"].exists()


def test_same_size_hash_mismatch(setup):
    args, client, body, _ = setup
    client.body = b"x" * len(body)
    with pytest.raises(ValueError, match="differs"):
        exporter.export_release_artifact(**args)
    assert not args["destination"].exists()


def test_legacy_key_read_still_checks_signed_bytes(setup):
    args, client, body, _ = setup
    client.key = args["artifact_path"].removeprefix("data/corpus/")
    exporter.export_release_artifact(**args)
    assert len(client.calls) == 2
    assert (args["destination"] / "payload.bin").read_bytes() == body


def test_existing_destination_not_overwritten(setup):
    args, _, _, _ = setup
    args["destination"].mkdir()
    (args["destination"] / "sentinel").write_text("original")
    with pytest.raises(FileExistsError):
        exporter.export_release_artifact(**args)
    assert (args["destination"] / "sentinel").read_text() == "original"


@pytest.mark.parametrize("kind", ["symlink", "noncanonical", "wrong_hash"])
def test_invalid_committed_lock(setup, kind):
    args, client, _, private = setup
    scope = exporter.scope_for_path(args["artifact_path"])
    lock = args["repo"] / exporter.lock_path_for_scope(scope)
    if kind == "symlink":
        lock.unlink()
        lock.symlink_to("/tmp/not-a-lock")
    elif kind == "noncanonical":
        lock.write_bytes(b" " + lock.read_bytes())
    else:
        content = lock.read_text()
        digest = next(
            a["sha256"]
            for a in args["payload"]["content"]["artifacts"]
            if a["path"] == args["artifact_path"]
        )
        lock.write_text(content.replace(digest, "f" * 64))
    exporter.git(args["repo"], "add", ".axiom")
    exporter.git(args["repo"], "-c", "commit.gpgsign=false", "commit", "-qm", "invalid-lock")
    commit = exporter.git(args["repo"], "rev-parse", "HEAD").decode().strip()
    exporter.git(args["repo"], "update-ref", "refs/remotes/origin/main", commit)
    args["payload"]["content"]["git"]["commit"] = commit
    resign(args, private)
    with pytest.raises(ValueError):
        exporter.export_release_artifact(**args)
    assert client.calls == []


def test_missing_object_fails_without_payload(setup):
    args, client, _, _ = setup
    client.key = "absent"
    with pytest.raises(ValueError, match="unavailable"):
        exporter.export_release_artifact(**args)
    assert not args["destination"].exists()


def test_existing_symlink_destination_refuses(setup, tmp_path):
    args, client, _, _ = setup
    protected = tmp_path / "original"
    protected.mkdir()
    (protected / "sentinel").write_text("untouched")
    args["destination"].symlink_to(protected, target_is_directory=True)
    with pytest.raises(FileExistsError):
        exporter.export_release_artifact(**args)
    assert client.calls == []
    assert (protected / "sentinel").read_text() == "untouched"


@pytest.mark.parametrize(
    "field,value",
    [
        ("GITHUB_REPOSITORY", "other/corpus"),
        ("GITHUB_REF", "refs/heads/feature"),
        ("GITHUB_EVENT_NAME", "pull_request"),
    ],
)
def test_cli_rejects_nonofficial_context_before_read(monkeypatch, field, value):
    monkeypatch.setenv("GITHUB_REPOSITORY", exporter.OFFICIAL_REPOSITORY)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv(field, value)
    monkeypatch.setattr(
        "sys.argv",
        [
            "export",
            "--release-object",
            "/not-read",
            "--release",
            "test",
            "--content-sha",
            "0" * 64,
            "--artifact-path",
            "not-read",
            "--destination",
            "/not-written",
        ],
    )
    with pytest.raises(ValueError, match="official main"):
        exporter.main()


def test_actual_cli_with_signed_fixture(setup, monkeypatch, tmp_path):
    args, client, body, _ = setup
    repo = args["repo"]
    exporter.git(
        repo, "remote", "add", "origin", f"https://github.com/{exporter.OFFICIAL_REPOSITORY}.git"
    )
    release_file = tmp_path / "release.json"
    release_file.write_text(json.dumps(args["payload"]))
    monkeypatch.chdir(repo)
    for key, value in {
        "GITHUB_REPOSITORY": exporter.OFFICIAL_REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": exporter.git(repo, "rev-parse", "HEAD").decode().strip(),
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_WORKFLOW_REF": f"{exporter.OFFICIAL_REPOSITORY}/.github/workflows/export-release-artifact.yml@refs/heads/main",
        "RELEASE_TRUST_ROOT": args["public_key"],
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(exporter.R2ObjectStore, "from_environment", lambda **kwargs: args["remote"])
    monkeypatch.setattr(
        "sys.argv",
        [
            "export",
            "--release-object",
            str(release_file),
            "--release",
            args["release"],
            "--content-sha",
            args["content_sha"],
            "--artifact-path",
            args["artifact_path"],
            "--destination",
            str(args["destination"]),
        ],
    )
    exporter.main()
    receipt = json.loads((args["destination"] / "receipt.json").read_text())
    assert receipt["exporter_run_id"] == "123"
    assert receipt["exporter_run_attempt"] == "2"
    assert (args["destination"] / "payload.bin").read_bytes() == body
    assert len(client.calls) == 1
