"""CI upload of a signed ingest's locked objects (docs/corpus-ci-upload.md).

The privileged job accepts an object only when a signed manifest, the lock
that equals it, and the uploaded bytes all agree. Each refusal below is one
way they can disagree; every one must leave the object store untouched.
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
import threading
from base64 import b64encode
from io import BytesIO
from pathlib import Path

import pytest
import yaml
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus import ci_upload
from axiom_corpus.corpus.ci_upload import (
    ARCHIVE_ASSET_NAME,
    UploadRefusedError,
    build_upload_plan,
    execute_upload,
    pack_objects,
    select_staged_asset,
    stage_archive,
)
from axiom_corpus.corpus.cli import main as cli_main
from axiom_corpus.corpus.content_store import R2ObjectStore, content_key
from axiom_corpus.corpus.corpus_locks import (
    lock_from_worktree,
    lock_path_for_scope,
    serialize_lock,
    write_lock,
)
from axiom_corpus.corpus.ingest_manifests import build_ingest_manifest, sign_ingest_manifest

SCOPE = ("us-az", "manual", "2026-11-24-pages")
OTHER_SCOPE = ("us-az", "policy", "2026-11-24-pages")
MANIFEST = ".axiom/ingest-manifests/us-az/manual/2026-11-24-pages.json"
FILES = {
    "data/corpus/sources/us-az/manual/2026-11-24-pages/official/faa3.html": b"<p>FAA3</p>\n",
    "data/corpus/sources/us-az/manual/2026-11-24-pages/official/faa4.html": b"<p>FAA4</p>\n",
    "data/corpus/inventory/us-az/manual/2026-11-24-pages.json": b'{"items": []}\n',
    "data/corpus/provisions/us-az/manual/2026-11-24-pages.jsonl": b'{"citation_path":"a"}\n',
    "data/corpus/coverage/us-az/manual/2026-11-24-pages.json": b'{"complete": true}\n',
}
WORKFLOW = Path(".github/workflows/corpus-object-upload.yml")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _keys() -> tuple[str, str]:
    key = Ed25519PrivateKey.generate()
    private = b64encode(
        key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
    ).decode("ascii")
    public = b64encode(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
    ).decode("ascii")
    return private, public


class FakeR2:
    """In-memory S3 subset with R2's conditional-write semantics."""

    def __init__(self, objects: dict[str, bytes] | None = None):
        self.objects = dict(objects or {})
        self.puts: list[str] = []
        self._lock = threading.Lock()

    def get_object(self, **kwargs):
        return {"Body": BytesIO(self.objects[kwargs["Key"]])}

    def head_object(self, **kwargs):
        return {"ContentLength": len(self.objects[kwargs["Key"]])}

    def put_object(self, **kwargs):
        body = kwargs["Body"]
        payload = body.read() if hasattr(body, "read") else bytes(body)
        with self._lock:
            if kwargs.get("IfNoneMatch") != "*":
                raise AssertionError("every corpus object write must be conditional")
            if kwargs["Key"] in self.objects:
                raise ClientError(
                    {
                        "Error": {"Code": "PreconditionFailed"},
                        "ResponseMetadata": {"HTTPStatusCode": 412},
                    },
                    "PutObject",
                )
            self.objects[kwargs["Key"]] = payload
            self.puts.append(kwargs["Key"])


def _store(objects: dict[str, bytes] | None = None) -> tuple[R2ObjectStore, FakeR2]:
    fake = FakeR2(objects)
    return R2ObjectStore(bucket="axiom-corpus", client=fake, legacy_path_keys=False), fake


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / ".gitignore").write_text("data/\n")
    (path / "README.md").write_text("seed\n")
    _git(path, "add", ".gitignore", "README.md")
    _git(path, "commit", "-q", "-m", "seed")
    return path


@pytest.fixture
def keys() -> tuple[str, str]:
    return _keys()


def _write_files(repo: Path, files: dict[str, bytes]) -> None:
    for rel, data in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _sign(repo: Path, private: str, scope=SCOPE, *, applied: list[str] | None = None) -> Path:
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction=scope[0],
        document_class=scope[1],
        version=scope[2],
        command="axiom-corpus-ingest extract-official-documents",
        applied_files=[Path(p) for p in applied] if applied is not None else None,
    )
    signed = sign_ingest_manifest(manifest, private_key=private)
    path = repo / ".axiom/ingest-manifests" / scope[0] / scope[1] / f"{scope[2]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(signed, indent=2, sort_keys=True) + "\n")
    return path


def _ingest(repo: Path, private: str, files: dict[str, bytes] = FILES, scope=SCOPE) -> str:
    """Sign and lock one scope on a branch; return the head commit."""
    _git(repo, "checkout", "-q", "-B", "ingest")
    _write_files(repo, files)
    _sign(repo, private, scope)
    write_lock(repo, lock_from_worktree(repo, scope))
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "ingest")
    return _git(repo, "rev-parse", "HEAD")


def _plan(repo: Path, head: str, public: str, **kwargs):
    return build_upload_plan(repo, base_ref="main", head_commit=head, public_key=public, **kwargs)


def _tar(tmp_path: Path, members: list[tuple[tarfile.TarInfo, bytes | None]]) -> Path:
    path = tmp_path / f"archive-{len(list(tmp_path.glob('archive-*')))}.tar"
    with tarfile.open(path, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for info, data in members:
            archive.addfile(info, io.BytesIO(data) if data is not None else None)
    return path


def _member(name: str, data: bytes) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    return info, data


def _good_members(files: dict[str, bytes] = FILES) -> list[tuple[tarfile.TarInfo, bytes | None]]:
    return [_member(_sha(data), data) for data in files.values()]


def _refused(plan, archive: Path, tmp_path: Path, match: str) -> None:
    """Staging refuses, so no upload can start."""
    with pytest.raises(UploadRefusedError, match=match):
        stage_archive(archive, plan, tmp_path / f"stage-{archive.stem}")


# --------------------------------------------------------------------------- accept


def test_signed_ingest_uploads_every_object_under_its_content_key(repo, keys, tmp_path) -> None:
    private, public = keys
    head = _ingest(repo, private)
    plan = _plan(repo, head, public)
    assert plan.scopes == (SCOPE,)
    assert plan.manifests == (MANIFEST,)
    assert {e.path for e in plan.entries} == set(FILES)

    archive = tmp_path / ARCHIVE_ASSET_NAME
    packed = pack_objects(repo, plan.entries, archive)
    assert packed["objects"] == len(FILES)
    staged = stage_archive(archive, plan, tmp_path / "stage")
    store, fake = _store()
    result = execute_upload(plan, staged, store)

    assert result.ok and not result.already_present
    assert sorted(result.uploaded) == sorted(_sha(d) for d in FILES.values())
    assert fake.objects == {content_key(_sha(d)): d for d in FILES.values()}


def test_rerun_with_the_same_inputs_writes_nothing(repo, keys, tmp_path) -> None:
    private, public = keys
    head = _ingest(repo, private)
    plan = _plan(repo, head, public)
    archive = _tar(tmp_path, _good_members())
    store, fake = _store()
    assert execute_upload(plan, stage_archive(archive, plan, tmp_path / "s1"), store).ok
    first_puts = list(fake.puts)

    second = execute_upload(plan, stage_archive(archive, plan, tmp_path / "s2"), store)

    assert second.ok and not second.uploaded
    assert len(second.already_present) == len(FILES)
    assert fake.puts == first_puts


def test_object_already_present_with_the_same_bytes_is_not_rewritten(repo, keys, tmp_path) -> None:
    private, public = keys
    head = _ingest(repo, private)
    plan = _plan(repo, head, public)
    present = next(iter(FILES.values()))
    store, fake = _store({content_key(_sha(present)): present})

    result = execute_upload(
        plan, stage_archive(_tar(tmp_path, _good_members()), plan, tmp_path / "stage"), store
    )

    assert result.ok
    assert result.already_present == [_sha(present)]
    assert content_key(_sha(present)) not in fake.puts
    assert len(fake.puts) == len(FILES) - 1


def test_archive_may_omit_objects_r2_already_holds(repo, keys, tmp_path) -> None:
    private, public = keys
    head = _ingest(repo, private)
    plan = _plan(repo, head, public)
    data = list(FILES.values())
    store, fake = _store({content_key(_sha(data[0])): data[0]})
    archive = _tar(tmp_path, [_member(_sha(d), d) for d in data[1:]])

    result = execute_upload(plan, stage_archive(archive, plan, tmp_path / "stage"), store)

    assert result.ok and len(fake.objects) == len(FILES)


def test_object_already_present_with_different_bytes_is_never_overwritten(
    repo, keys, tmp_path
) -> None:
    private, public = keys
    head = _ingest(repo, private)
    plan = _plan(repo, head, public)
    victim = next(iter(FILES.values()))
    store, fake = _store({content_key(_sha(victim)): b"other bytes"})

    result = execute_upload(
        plan, stage_archive(_tar(tmp_path, _good_members()), plan, tmp_path / "stage"), store
    )

    assert not result.ok
    assert set(result.failed) == {_sha(victim)}
    assert fake.objects[content_key(_sha(victim))] == b"other bytes"
    assert content_key(_sha(victim)) not in fake.puts


def test_unstaged_object_with_different_remote_bytes_refuses_before_any_write(
    repo, keys, tmp_path
) -> None:
    private, public = keys
    head = _ingest(repo, private)
    plan = _plan(repo, head, public)
    data = list(FILES.values())
    store, fake = _store({content_key(_sha(data[0])): b"x" * len(data[0])})
    archive = _tar(tmp_path, [_member(_sha(d), d) for d in data[1:]])

    with pytest.raises(UploadRefusedError, match="do not match its key"):
        execute_upload(plan, stage_archive(archive, plan, tmp_path / "stage"), store)
    assert fake.puts == []


# --------------------------------------------------------------------------- archive refusals


def test_wrong_hash_is_refused(repo, keys, tmp_path) -> None:
    private, public = keys
    plan = _plan(repo, _ingest(repo, private), public)
    data = list(FILES.values())
    tampered = bytes([data[0][0] ^ 1]) + data[0][1:]
    members = [_member(_sha(data[0]), tampered)] + [_member(_sha(d), d) for d in data[1:]]
    _refused(plan, _tar(tmp_path, members), tmp_path, "does not hold the bytes")


def test_wrong_size_is_refused(repo, keys, tmp_path) -> None:
    private, public = keys
    plan = _plan(repo, _ingest(repo, private), public)
    data = next(iter(FILES.values()))
    _refused(
        plan, _tar(tmp_path, [_member(_sha(data), data + b"extra")]), tmp_path, "lock entry pins"
    )


def test_extra_file_is_refused(repo, keys, tmp_path) -> None:
    private, public = keys
    plan = _plan(repo, _ingest(repo, private), public)
    extra = b"not in any signed lock"
    members = [*_good_members(), _member(_sha(extra), extra)]
    _refused(plan, _tar(tmp_path, members), tmp_path, "not an object of the signed lock")


def test_duplicate_member_is_refused(repo, keys, tmp_path) -> None:
    private, public = keys
    plan = _plan(repo, _ingest(repo, private), public)
    data = next(iter(FILES.values()))
    members = [_member(_sha(data), data), _member(_sha(data), data)]
    _refused(plan, _tar(tmp_path, members), tmp_path, "appears twice")


def test_missing_file_is_refused_before_any_write(repo, keys, tmp_path) -> None:
    private, public = keys
    plan = _plan(repo, _ingest(repo, private), public)
    archive = _tar(tmp_path, _good_members()[1:])
    store, fake = _store()

    with pytest.raises(UploadRefusedError, match="neither in the archive nor in R2"):
        execute_upload(plan, stage_archive(archive, plan, tmp_path / "stage"), store)
    assert fake.objects == {}


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/etc/passwd",
        "objects/sha256/aa/" + "a" * 64,
        "data/corpus/sources/us-az/manual/2026-11-24-pages/official/faa3.html",
        "A" * 64,
        "a" * 63,
        "a" * 64 + "/..",
        "./" + "a" * 64,
    ],
)
def test_path_traversal_and_other_names_are_refused(repo, keys, tmp_path, name: str) -> None:
    private, public = keys
    plan = _plan(repo, _ingest(repo, private), public)
    stage = tmp_path / "stage-names"
    with pytest.raises(UploadRefusedError, match="not named by a lowercase sha256"):
        stage_archive(_tar(tmp_path, [_member(name, b"payload")]), plan, stage)
    assert list(stage.iterdir()) == []
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize(
    "kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE]
)
def test_symlink_and_other_non_regular_members_are_refused(repo, keys, tmp_path, kind) -> None:
    private, public = keys
    plan = _plan(repo, _ingest(repo, private), public)
    info = tarfile.TarInfo(name=_sha(next(iter(FILES.values()))))
    info.type = kind
    info.linkname = "/etc/passwd"
    _refused(plan, _tar(tmp_path, [(info, None)]), tmp_path, "not a plain regular file")


def test_compressed_or_garbage_archive_is_refused(repo, keys, tmp_path) -> None:
    private, public = keys
    plan = _plan(repo, _ingest(repo, private), public)
    gz = tmp_path / "archive.tar.gz"
    with tarfile.open(gz, mode="w:gz") as archive:
        info, data = _good_members()[0]
        archive.addfile(info, io.BytesIO(data or b""))
    _refused(plan, gz, tmp_path, "not a readable tar")
    garbage = tmp_path / "garbage.tar"
    garbage.write_bytes(b"\x01" * 2048)
    _refused(plan, garbage, tmp_path, "not a readable tar")


def test_archive_that_is_a_symlink_or_too_large_is_refused(
    repo, keys, tmp_path, monkeypatch
) -> None:
    private, public = keys
    plan = _plan(repo, _ingest(repo, private), public)
    real = _tar(tmp_path, _good_members())
    link = tmp_path / "link.tar"
    link.symlink_to(real)
    _refused(plan, link, tmp_path, "not a regular file")
    monkeypatch.setattr(ci_upload, "MAX_ARCHIVE_BYTES", 100)
    _refused(plan, real, tmp_path, "the limit is")


def test_staged_files_are_named_by_the_lock_not_by_the_archive(repo, keys, tmp_path) -> None:
    private, public = keys
    plan = _plan(repo, _ingest(repo, private), public)
    staged = stage_archive(_tar(tmp_path, _good_members()), plan, tmp_path / "stage")
    assert {path.name for path in staged.values()} == set(plan.objects)
    assert {path.parent for path in staged.values()} == {tmp_path / "stage"}
    with pytest.raises(UploadRefusedError, match="not in the plan"):
        execute_upload(plan, {**staged, "f" * 64: tmp_path / "x"}, _store()[0])


# --------------------------------------------------------------------------- plan refusals


def test_unsigned_manifest_is_refused(repo, keys) -> None:
    private, public = keys
    _ingest(repo, private)
    path = repo / MANIFEST
    payload = json.loads(path.read_text())
    del payload["signature"]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _git(repo, "commit", "-q", "-am", "strip signature")
    with pytest.raises(UploadRefusedError, match="Missing ingest manifest signature"):
        _plan(repo, _git(repo, "rev-parse", "HEAD"), public)


def test_manifest_signed_by_another_key_is_refused(repo, keys) -> None:
    private, _public = keys
    head = _ingest(repo, private)
    with pytest.raises(UploadRefusedError, match="Invalid ingest manifest signature"):
        _plan(repo, head, _keys()[1])


def test_manifest_edited_after_signing_is_refused(repo, keys) -> None:
    private, public = keys
    _ingest(repo, private)
    new = dict(FILES)
    target = "data/corpus/provisions/us-az/manual/2026-11-24-pages.jsonl"
    new[target] = b'{"citation_path":"forged"}\n'
    _write_files(repo, new)
    path = repo / MANIFEST
    payload = json.loads(path.read_text())
    for item in payload["applied_files"]:
        if item["path"] == target:
            item["sha256"] = _sha(new[target])
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    write_lock(repo, lock_from_worktree(repo, SCOPE))
    _git(repo, "commit", "-q", "-am", "forge")
    with pytest.raises(UploadRefusedError, match="Invalid ingest manifest signature"):
        _plan(repo, _git(repo, "rev-parse", "HEAD"), public)


def test_missing_manifest_and_missing_public_key_are_refused(repo, keys) -> None:
    private, public = keys
    head = _ingest(repo, private)
    for empty in (None, "", "  "):
        with pytest.raises(UploadRefusedError, match="AXIOM_CORPUS_INGEST_PUBLIC_KEY"):
            _plan(repo, head, empty)
    _git(repo, "rm", "-q", MANIFEST)
    _git(repo, "commit", "-q", "-m", "drop manifest")
    with pytest.raises(UploadRefusedError, match="has no ingest manifest"):
        _plan(repo, _git(repo, "rev-parse", "HEAD"), public)


def test_lock_that_differs_from_the_signed_manifest_is_refused(repo, keys) -> None:
    private, public = keys
    _ingest(repo, private)
    target = "data/corpus/provisions/us-az/manual/2026-11-24-pages.jsonl"
    _write_files(repo, {target: b'{"citation_path":"changed after signing"}\n'})
    write_lock(repo, lock_from_worktree(repo, SCOPE))
    _git(repo, "commit", "-q", "-am", "relock without signing")
    with pytest.raises(UploadRefusedError, match="does not equal its signed manifest.*sha256"):
        _plan(repo, _git(repo, "rev-parse", "HEAD"), public)


def test_lock_entry_the_manifest_does_not_sign_is_refused(repo, keys) -> None:
    private, public = keys
    _ingest(repo, private)
    extra = "data/corpus/sources/us-az/manual/2026-11-24-pages/official/unsigned.html"
    _write_files(repo, {extra: b"<p>unsigned</p>\n"})
    write_lock(repo, lock_from_worktree(repo, SCOPE))
    _git(repo, "commit", "-q", "-am", "add unsigned file to lock")
    with pytest.raises(UploadRefusedError, match="only in the lock"):
        _plan(repo, _git(repo, "rev-parse", "HEAD"), public)


def test_manifest_signed_for_another_scope_is_refused(repo, keys) -> None:
    """A valid signature for scope A must not admit a lock for scope B."""
    private, public = keys
    _ingest(repo, private)
    other_files = {
        path.replace("/manual/", "/policy/"): data + b"other\n" for path, data in FILES.items()
    }
    _write_files(repo, other_files)
    write_lock(repo, lock_from_worktree(repo, OTHER_SCOPE))
    other_manifest = repo / ".axiom/ingest-manifests/us-az/policy/2026-11-24-pages.json"
    other_manifest.parent.mkdir(parents=True, exist_ok=True)
    other_manifest.write_bytes((repo / MANIFEST).read_bytes())
    _git(repo, "add", ".axiom")
    _git(repo, "commit", "-q", "-m", "reuse a signature")
    with pytest.raises(UploadRefusedError, match="signed for another scope"):
        _plan(repo, _git(repo, "rev-parse", "HEAD"), public)


def test_lock_listing_a_path_outside_its_scope_is_refused(repo, keys) -> None:
    private, public = keys
    _ingest(repo, private)
    lock = lock_from_worktree(repo, SCOPE)
    outside = "data/corpus/provisions/us/statute/2026-01-01.jsonl"
    raw = serialize_lock(lock).decode("ascii").replace(lock.files[0].path, outside)
    (repo / lock_path_for_scope(SCOPE)).write_text(raw)
    _git(repo, "commit", "-q", "-am", "lock a path outside the scope")
    with pytest.raises(UploadRefusedError, match="lock files at the head are invalid"):
        _plan(repo, _git(repo, "rev-parse", "HEAD"), public)


def test_head_must_be_a_full_commit_with_changed_entries(repo, keys) -> None:
    private, public = keys
    head = _ingest(repo, private)
    for bad in ("ingest", head[:12], "HEAD", "0" * 40, head.upper()):
        with pytest.raises(UploadRefusedError):
            _plan(repo, bad, public)
    with pytest.raises(UploadRefusedError, match="adds or changes no lock entry"):
        _plan(repo, _git(repo, "rev-parse", "main"), public)


def test_object_count_and_byte_caps_are_enforced(repo, keys) -> None:
    private, public = keys
    head = _ingest(repo, private)
    with pytest.raises(UploadRefusedError, match="at most 2"):
        _plan(repo, head, public, max_objects=2)
    with pytest.raises(UploadRefusedError, match="at most 10"):
        _plan(repo, head, public, max_total_bytes=10)


def test_only_entries_changed_since_the_merge_base_are_planned(repo, keys) -> None:
    private, public = keys
    _ingest(repo, private)
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "ingest", "-m", "merge ingest")
    other_files = {
        path.replace("/manual/", "/policy/"): data + b"policy\n" for path, data in FILES.items()
    }
    head = _ingest(repo, private, other_files, OTHER_SCOPE)

    plan = _plan(repo, head, public)

    assert plan.scopes == (OTHER_SCOPE,)
    assert {e.path for e in plan.entries} == set(other_files)


# --------------------------------------------------------------------------- pack


def test_pack_refuses_files_that_differ_from_the_lock_and_symlinks(repo, keys, tmp_path) -> None:
    private, public = keys
    plan = _plan(repo, _ingest(repo, private), public)
    target = repo / next(iter(FILES))
    original = target.read_bytes()
    target.write_bytes(b"edited after locking\n")
    with pytest.raises(UploadRefusedError, match="does not hold the bytes"):
        pack_objects(repo, plan.entries, tmp_path / "a.tar")
    target.unlink()
    (tmp_path / "elsewhere").write_bytes(original)
    target.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(UploadRefusedError, match="not a regular file"):
        pack_objects(repo, plan.entries, tmp_path / "b.tar")


def test_pack_stores_shared_bytes_once(repo, keys, tmp_path) -> None:
    private, public = keys
    files = dict(FILES)
    files["data/corpus/sources/us-az/manual/2026-11-24-pages/official/copy.html"] = FILES[
        "data/corpus/sources/us-az/manual/2026-11-24-pages/official/faa3.html"
    ]
    plan = _plan(repo, _ingest(repo, private, files), public)
    packed = pack_objects(repo, plan.entries, tmp_path / "a.tar")
    assert packed["objects"] == len(FILES) == len(plan.objects)
    with tarfile.open(tmp_path / "a.tar") as archive:
        assert sorted(archive.getnames()) == sorted(plan.objects)


# --------------------------------------------------------------------------- CLI


def test_cli_pack_then_verify_only_then_summary(repo, keys, tmp_path, monkeypatch, capsys) -> None:
    private, public = keys
    head = _ingest(repo, private)
    archive = tmp_path / ARCHIVE_ASSET_NAME
    assert (
        cli_main(
            ["corpus", "ci-pack", "--repo", str(repo), "--changed-since", "main",
             "--output", str(archive)]
        )
        == 0
    )
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY", public)
    for name in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_ACCOUNT_ID"):
        monkeypatch.delenv(name, raising=False)
    summary = tmp_path / "summary.md"
    arguments = ["corpus", "ci-upload", "--repo", str(repo), "--base", "main", "--head", head,
                 "--archive", str(archive), "--summary", str(summary)]

    assert cli_main([*arguments, "--verify-only"]) == 0
    assert "Verification passed" in summary.read_text()
    assert "us-az/manual/2026-11-24-pages" in summary.read_text()

    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY", _keys()[1])
    assert cli_main([*arguments, "--verify-only"]) == 1
    assert "Refused" in summary.read_text()
    capsys.readouterr()


def test_cli_upload_writes_through_the_environment_store(
    repo, keys, tmp_path, monkeypatch, capsys
) -> None:
    private, public = keys
    head = _ingest(repo, private)
    archive = _tar(tmp_path, _good_members())
    store, fake = _store()
    store.legacy_path_keys = True  # the command must turn legacy path reads off
    monkeypatch.setattr(R2ObjectStore, "from_environment", classmethod(lambda cls, **_: store))
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY", public)
    arguments = ["corpus", "ci-upload", "--repo", str(repo), "--base", "main", "--head", head,
                 "--archive", str(archive), "--json"]

    assert cli_main(arguments) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["ok"] and len(first["result"]["uploaded"]) == len(FILES)
    assert store.legacy_path_keys is False

    assert cli_main(arguments) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["result"]["uploaded"] == [] and len(fake.puts) == len(FILES)


def test_cli_upload_without_credentials_fails_closed(
    repo, keys, tmp_path, monkeypatch, capsys
) -> None:
    private, public = keys
    head = _ingest(repo, private)

    def no_credentials(cls, **_):
        raise RuntimeError("R2 credentials are not configured")

    monkeypatch.setattr(R2ObjectStore, "from_environment", classmethod(no_credentials))
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PUBLIC_KEY", public)
    code = cli_main(
        ["corpus", "ci-upload", "--repo", str(repo), "--base", "main", "--head", head,
         "--archive", str(_tar(tmp_path, _good_members()))]
    )
    assert code == 1
    assert "cannot open the R2 store" in capsys.readouterr().err


# --------------------------------------------------------------------------- release asset


def _release(**overrides) -> dict:
    release = {
        "id": 7,
        "tag_name": "corpus-upload-pr-1013",
        "draft": True,
        "assets": [
            {
                "id": 99,
                "name": ARCHIVE_ASSET_NAME,
                "state": "uploaded",
                "size": 4096,
                "uploader": {"login": "ingester"},
            }
        ],
    }
    release.update(overrides)
    return release


def test_select_staged_asset_accepts_one_draft_with_one_archive() -> None:
    other = _release(id=8, tag_name="corpus-upload-pr-10130")
    for listing in ([other, _release()], [[other], [_release()]]):
        asset = select_staged_asset(listing, pr_number="1013")
        assert (asset.asset_id, asset.size, asset.release_id, asset.uploader) == (
            99, 4096, 7, "ingester"
        )


@pytest.mark.parametrize(
    ("releases", "match"),
    [
        ([], "found 0"),
        ([_release(), _release(id=8)], "found 2"),
        ([_release(draft=False)], "not a draft"),
        ([_release(assets=[])], "exactly one asset"),
        ([_release(assets=[*_release()["assets"], *_release()["assets"]])], "exactly one asset"),
        ([_release(assets=[{**_release()["assets"][0], "name": "x.tar"}])], "must be named"),
        ([_release(assets=[{**_release()["assets"][0], "state": "starter"}])], "not fully"),
        ([_release(assets=[{**_release()["assets"][0], "size": 2**40}])], "the limit is"),
        ([_release(assets=[{**_release()["assets"][0], "id": "99"}])], "invalid asset id"),
        ({"tag_name": "corpus-upload-pr-1013"}, "not a JSON list"),
    ],
)
def test_select_staged_asset_refuses_everything_else(releases, match: str) -> None:
    with pytest.raises(UploadRefusedError, match=match):
        select_staged_asset(releases, pr_number="1013")


@pytest.mark.parametrize("number", ["", "0", "01", "-1", "1013 ", "1013/../x", "1e3", "１０"])
def test_pull_request_number_must_be_a_plain_positive_integer(number: str) -> None:
    with pytest.raises(UploadRefusedError, match="positive integer"):
        select_staged_asset([_release()], pr_number=number)


def test_cli_select_asset_writes_outputs(tmp_path, capsys) -> None:
    releases = tmp_path / "releases.json"
    releases.write_text(json.dumps([[_release()]]))
    output = tmp_path / "github-output"
    code = cli_main(
        ["corpus", "ci-select-asset", "--releases", str(releases), "--pr", "1013",
         "--github-output", str(output)]
    )
    assert code == 0
    assert output.read_text() == "asset_id=99\nasset_size=4096\n"
    releases.write_text(json.dumps([_release(draft=False)]))
    assert cli_main(["corpus", "ci-select-asset", "--releases", str(releases), "--pr", "1013"]) == 1
    capsys.readouterr()


# --------------------------------------------------------------------------- workflow shape


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_starts_only_by_dispatch_and_never_from_a_pull_request() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    document = _workflow()
    # PyYAML reads the bare key ``on`` as True.
    assert list(document[True]) == ["workflow_dispatch"]
    assert "pull_request_target" not in text
    assert "workflow_run" not in text
    assert document["permissions"] == {}


def test_every_job_runs_only_on_main_of_this_repository() -> None:
    for name, job in _workflow()["jobs"].items():
        assert job["if"] == (
            "github.repository == 'TheAxiomFoundation/axiom-corpus' "
            "&& github.ref == 'refs/heads/main' && github.event_name == 'workflow_dispatch'"
        ), name


def test_r2_write_credentials_reach_only_the_final_upload_step() -> None:
    jobs = _workflow()["jobs"]
    assert "secrets." not in json.dumps(jobs["stage"])
    upload = jobs["upload"]
    assert upload["environment"] == "corpus-object-upload"
    assert upload["permissions"] == {"contents": "read"}
    assert "secrets." not in json.dumps({k: v for k, v in upload.items() if k != "steps"})
    with_secrets = [
        step.get("name") for step in upload["steps"] if "secrets." in json.dumps(step)
    ]
    assert with_secrets == ["Upload the verified objects to R2"]
    assert upload["steps"][-1]["name"] == "Upload the verified objects to R2"


def test_the_write_token_job_holds_no_r2_credentials_and_the_r2_job_no_write_token() -> None:
    jobs = _workflow()["jobs"]
    assert jobs["stage"]["permissions"] == {"contents": "write"}
    assert "environment" not in jobs["stage"]
    assert "GH_TOKEN" not in json.dumps(jobs["upload"])
    assert "github.token" not in json.dumps(jobs["upload"])


def test_checkouts_take_main_and_do_not_persist_credentials() -> None:
    for name, job in _workflow()["jobs"].items():
        checkouts = [
            step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        assert len(checkouts) == 1, name
        options = checkouts[0]["with"]
        assert options["persist-credentials"] is False
        assert "ref" not in options and "repository" not in options


def test_pull_request_data_is_read_from_git_objects_never_checked_out() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "git checkout" not in text and "git switch" not in text and "git worktree" not in text
    assert "git merge" not in text and "git reset" not in text
    assert "--base HEAD" in text


def test_dispatch_inputs_never_enter_a_script_as_text() -> None:
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            assert "${{ inputs." not in str(step.get("run", "")), step.get("name")
            assert "${{ github.event.inputs." not in str(step.get("run", "")), step.get("name")

