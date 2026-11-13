"""Real signatures and tiny Git stores exercise the R2 preparation boundary."""

from __future__ import annotations

import base64
import hashlib
import json
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tests.test_ci_git_blob_prefetch import clone, commit, git, prefetch


def keys():
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption())
    public = key.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    return base64.b64encode(private).decode(), base64.b64encode(public).decode()


def make_signed(tmp_path, monkeypatch, count=2):
    from axiom_corpus.corpus.corpus_locks import CorpusLock, LockEntry, write_lock
    from axiom_corpus.corpus.ingest_manifests import build_ingest_manifest, sign_ingest_manifest

    seed = tmp_path / "seed"
    git(tmp_path, "init", "-q", "-b", "main", str(seed))
    (seed / "README.md").write_text("signed fixture\n")
    paths = [
        "data/corpus/provisions/nz/statute/v1.jsonl",
        "data/corpus/coverage/nz/statute/v1.json",
    ]
    paths += [f"data/corpus/sources/nz/statute/v1/inputs/{i}.txt" for i in range(count - 2)]
    for i, name in enumerate(paths):
        path = seed / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"complete": True, "fixture": i}) + "\n")
    commit(seed, "original corpus bytes")
    entries = [
        LockEntry(
            name,
            hashlib.sha256((seed / name).read_bytes()).hexdigest(),
            (seed / name).stat().st_size,
            git(seed, "rev-parse", f"HEAD:{name}").decode().strip(),
        )
        for name in paths
    ]
    git(seed, "checkout", "-q", "-b", "side")
    (seed / "README.md").write_text("side-only ancestor\n")
    side = commit(seed, "not an ancestor of main head")
    git(seed, "checkout", "-q", "main")
    private, public = keys()
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY", public)
    monkeypatch.setenv("GIT_NO_LAZY_FETCH", "1")
    monkeypatch.setenv("GIT_NO_REPLACE_OBJECTS", "1")
    payload = build_ingest_manifest(
        repo=seed,
        base=seed / "data/corpus",
        jurisdiction="nz",
        document_class="statute",
        version="v1",
        command="fixture",
        applied_files=[seed / name for name in paths],
    )
    manifest = seed / ".axiom/ingest-manifests/nz/statute/v1.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(sign_ingest_manifest(payload, private_key=private)))
    lock = write_lock(seed, CorpusLock.from_entries(("nz", "statute", "v1"), entries))
    for name in paths:
        (seed / name).unlink()
    base = commit(seed, "signed migration")
    (seed / "README.md").write_text("unchanged signed lock\n")
    head = commit(seed, "code-only head")
    return SimpleNamespace(
        seed=seed,
        entries=entries,
        manifest=manifest,
        lock=lock,
        base=base,
        head=head,
        side=side,
        private=private,
        public=public,
    )


def view(f, tmp_path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "clone", "--bare", "-q", str(f.seed), str(origin))
    git(origin, "config", "uploadpack.allowFilter", "true")
    return clone(origin, tmp_path / "partial")


@pytest.mark.parametrize(
    "kind", ["valid", "unsigned", "bad-sha", "deleted", "wrong-ancestor", "bad-signature"]
)
def test_r2_plan_omits_only_valid_unchanged_signed_payload(tmp_path, monkeypatch, kind):
    from axiom_corpus.corpus.ingest_manifests import audit_lock_attestation, sign_ingest_manifest

    f = make_signed(tmp_path, monkeypatch)
    if kind == "unsigned":
        f.manifest.unlink()
    elif kind != "valid":
        payload = json.loads(f.manifest.read_text())
        target = next(row for row in payload["applied_files"] if row["path"] == f.entries[0].path)
        if kind == "bad-sha":
            target["sha256"] = "0" * 64
        elif kind == "deleted":
            target["deleted"] = True
        elif kind == "wrong-ancestor":
            payload["axiom_corpus_git"]["commit"] = f.side
        private = keys()[0] if kind == "bad-signature" else f.private
        f.manifest.write_text(json.dumps(sign_ingest_manifest(payload, private_key=private)))
    if kind != "valid":
        f.head = commit(f.seed, kind)
    repo = view(f, tmp_path)
    objects = [entry.git_blob for entry in f.entries]
    assert all(v is None for v in prefetch.local_headers(repo, objects).values())
    out = tmp_path / "plan"
    result = prefetch.prepare(repo, f.head, f.base, out, plan_only=False, payload_source="r2")
    actual = {row["oid"] for row in json.loads((out / "payload-inventory.json").read_text())}
    expected = (
        set()
        if kind == "valid"
        else {objects[0]}
        if kind in {"bad-sha", "deleted"}
        else set(objects)
    )
    assert actual == expected and result["payload_source"] == "r2"
    # This is the unchanged, real full audit; valid signatures need no local payload.
    assert audit_lock_attestation(repo, ref=f.head, public_key=f.public) == []
    if kind == "valid":
        assert all(v is None for v in prefetch.local_headers(repo, objects).values())


def test_changed_lock_keeps_entire_head_scope_even_when_signed(tmp_path, monkeypatch):
    f = make_signed(tmp_path, monkeypatch)
    f.lock.chmod(0o755)
    git(f.seed, "update-index", "--chmod=+x", str(f.lock.relative_to(f.seed)))
    head = commit(f.seed, "lock mode changed; same signed entries")
    assert str(f.lock.relative_to(f.seed)).encode() in git(
        f.seed, "diff", "--name-only", f.head, head
    )
    repo = view(f, tmp_path)
    payloads, _metadata, _refs = prefetch.inventory(repo, head, f.head, payload_source="r2")
    assert payloads == {e.git_blob: e.size for e in f.entries}


def test_schedule_keeps_all_thirty_unsigned_fallbacks(tmp_path, monkeypatch):
    from axiom_corpus.corpus.ingest_manifests import audit_lock_attestation

    f = make_signed(tmp_path, monkeypatch, count=30)
    f.manifest.unlink()
    head = commit(f.seed, "unsigned schedule fallback")
    repo = view(f, tmp_path)
    result = prefetch.prepare(
        repo, head, None, tmp_path / "plan", plan_only=False, payload_source="r2"
    )
    assert result["payload_object_count"] == 30 and result["missing_after"] == 0
    assert audit_lock_attestation(repo, ref=head, public_key=f.public) == []


def test_missing_key_and_missing_objects_after_successful_transport_fail_closed(
    tmp_path, monkeypatch
):
    f = make_signed(tmp_path, monkeypatch)
    f.manifest.unlink()
    head = commit(f.seed, "unsigned fallback")
    repo = view(f, tmp_path)
    monkeypatch.delenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY")
    with pytest.raises(ValueError, match="requires AXIOM_CORPUS_INGEST_PUBLIC_KEY"):
        prefetch.prepare(repo, head, None, tmp_path / "no-key", plan_only=True, payload_source="r2")
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY", f.public)
    real_git = prefetch.git

    def omit_historical_payload(repo, *args, **kwargs):
        if "fetch" in args:
            # A real successful filtered ref fetch deliberately omits wanted blobs.
            return real_git(repo, "fetch", "--no-tags", "--filter=blob:none", "origin", "main")
        return real_git(repo, *args, **kwargs)

    monkeypatch.setattr(prefetch, "git", omit_historical_payload)
    with pytest.raises(ValueError, match="left required local objects missing"):
        prefetch.prepare(
            repo, head, None, tmp_path / "missing", plan_only=False, payload_source="r2"
        )


def test_no_git_fetch_rejects_corrupt_r2_without_falling_back_to_real_git(
    tmp_path, monkeypatch, capsys
):
    from axiom_corpus.corpus import corpus_cli
    from axiom_corpus.corpus.cli import main

    f = make_signed(tmp_path, monkeypatch)

    class Transport:
        name = "r2"

        def open(self, _entry):
            return iter([b"corrupt transport bytes"])

    monkeypatch.setattr(
        corpus_cli.R2ObjectStore, "from_environment", classmethod(lambda cls, **kw: Transport())
    )
    args = [
        "corpus",
        "fetch",
        "--repo",
        str(f.seed),
        "--all",
        "--no-cache",
        "--workers",
        "1",
        "--json",
    ]
    assert main([*args, "--no-git"]) == 1
    failed = json.loads(capsys.readouterr().out)
    assert failed["failed"] and not failed["sources"]
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["sources"] == {"git": 2}
