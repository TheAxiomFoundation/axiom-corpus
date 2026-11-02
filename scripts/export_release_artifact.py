#!/usr/bin/env python3
"""Export one authenticated provision member; never publish or sign corpus data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from axiom_corpus.corpus.content_store import R2ObjectStore
from axiom_corpus.corpus.corpus_locks import (
    LockEntry,
    lock_path_for_scope,
    parse_lock,
    scope_for_path,
)
from axiom_corpus.release.manifest import verify_release_object

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_RELEASE_BYTES = 64 * 1024 * 1024
OFFICIAL_REPOSITORY = "TheAxiomFoundation/axiom-corpus"


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def export_release_artifact(
    *,
    repo: Path,
    payload: dict,
    public_key: str,
    release: str,
    content_sha: str,
    artifact_path: str,
    destination: Path,
    remote: R2ObjectStore,
    run_id: str,
    run_attempt: str,
    workflow_ref: str,
) -> dict:
    """Bind signed inventory to its committed lock before reading remote bytes."""
    verify_release_object(payload, public_key=public_key)
    if payload["release"] != release or payload["content_sha256"] != content_sha:
        raise ValueError("release identity mismatch")
    matches = [a for a in payload["content"]["artifacts"] if a["path"] == artifact_path]
    if len(matches) != 1 or matches[0]["artifact_class"] != "provisions":
        raise ValueError("exactly one provision member required")
    member = matches[0]
    entry = LockEntry(artifact_path, member["sha256"], member["bytes"])
    if not 0 < entry.size <= MAX_ARTIFACT_BYTES:
        raise ValueError("provision exceeds export size bound")
    if remote.bucket != member["r2_bucket"]:
        raise ValueError("remote bucket differs from signed inventory")
    commit = payload["content"]["git"]["commit"]
    git(repo, "merge-base", "--is-ancestor", commit, "refs/remotes/origin/main")
    scope = scope_for_path(entry.path)
    if scope is None:
        raise ValueError("invalid provision scope")
    lock_path = lock_path_for_scope(scope).as_posix()
    tree_entry = git(repo, "ls-tree", commit, "--", lock_path).decode()
    if not tree_entry.startswith("100644 blob "):
        raise ValueError("release lock must be an ordinary committed file")
    lock = parse_lock(git(repo, "show", f"{commit}:{lock_path}"))
    locked = [item for item in lock.files if item.path == entry.path]
    if len(locked) != 1 or locked[0].content != entry.content or lock.scope != scope:
        raise ValueError("signed member and immutable lock disagree")
    # A new private directory prevents accidental overwrite or symlink traversal.
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    stream = None
    try:
        stream = remote.open(entry)
        if stream is None:
            raise ValueError("authenticated provision is unavailable in the content store")
        digest = hashlib.sha256()
        size = 0
        with (destination / "payload.bin").open("xb") as output:
            for chunk in stream:
                size += len(chunk)
                if size > entry.size:
                    raise ValueError("remote object exceeds signed size")
                digest.update(chunk)
                output.write(chunk)
        if size != entry.size or digest.hexdigest() != entry.sha256:
            raise ValueError("remote object differs from signed bytes")
        receipt = {
            "schema_version": "axiom-corpus/release-artifact-export/v1",
            "release": release,
            "content_sha256": content_sha,
            "source_commit": commit,
            "path": entry.path,
            "sha256": entry.sha256,
            "bytes": entry.size,
            "payload_filename": "payload.bin",
            "exporter_run_id": run_id,
            "exporter_run_attempt": run_attempt,
            "exporter_workflow_ref": workflow_ref,
            "exporter_commit": git(repo, "rev-parse", "HEAD").decode().strip(),
        }
        (destination / "receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
        return receipt
    except BaseException:
        shutil.rmtree(destination)
        raise
    finally:
        close = getattr(stream, "close", None)
        if close is not None:
            close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-object", type=Path, required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--content-sha", required=True)
    parser.add_argument("--artifact-path", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if (
        os.environ.get("GITHUB_REPOSITORY") != OFFICIAL_REPOSITORY
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
    ):
        raise ValueError("export requires official main workflow_dispatch")
    repo = Path.cwd()
    origin = git(repo, "remote", "get-url", "origin").decode().strip()
    if origin not in {
        f"https://github.com/{OFFICIAL_REPOSITORY}",
        f"https://github.com/{OFFICIAL_REPOSITORY}.git",
    }:
        raise ValueError("official origin required")
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    if head != os.environ.get("GITHUB_SHA"):
        raise ValueError("exporter checkout differs from workflow identity")
    git(repo, "merge-base", "--is-ancestor", head, "refs/remotes/origin/main")
    if not re.fullmatch(r"[0-9a-f]{64}", args.content_sha):
        raise ValueError("invalid release content address")
    with args.release_object.open("rb") as source:
        data = source.read(MAX_RELEASE_BYTES + 1)
    if len(data) > MAX_RELEASE_BYTES:
        raise ValueError("release object exceeds size bound")
    run_id, run_attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    workflow_ref = os.environ["GITHUB_WORKFLOW_REF"]
    if not re.fullmatch(r"[1-9][0-9]*", run_id) or not re.fullmatch(r"[1-9][0-9]*", run_attempt):
        raise ValueError("invalid workflow run identity")
    if (
        workflow_ref
        != f"{OFFICIAL_REPOSITORY}/.github/workflows/export-release-artifact.yml@refs/heads/main"
    ):
        raise ValueError("unexpected exporter workflow identity")
    receipt = export_release_artifact(
        repo=repo,
        payload=json.loads(data),
        public_key=os.environ["RELEASE_TRUST_ROOT"],
        release=args.release,
        content_sha=args.content_sha,
        artifact_path=args.artifact_path,
        destination=args.destination,
        remote=R2ObjectStore.from_environment(workers=1),
        run_id=run_id,
        run_attempt=run_attempt,
        workflow_ref=workflow_ref,
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
