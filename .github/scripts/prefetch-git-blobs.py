#!/usr/bin/env python3
"""Prefetch endpoint metadata, first-parent policy history and HEAD lock payloads.

Checkout must first hydrate HEAD. All subsequent reads disable lazy fetching.
This preparation supplements the unchanged signature, SHA256 and history gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

OID = re.compile(r"[0-9a-f]{40}\Z")
PROTECTED = tuple(
    f"data/corpus/{kind}/".encode() for kind in ("sources", "inventory", "provisions", "coverage")
)


def git(repo: Path, *args: str, input: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input,
        capture_output=True,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1"},
        check=False,
    )
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def commit(repo: Path, ref: str) -> str:
    value = (
        git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()
    )
    if not OID.fullmatch(value):
        raise ValueError(f"unexpected commit identifier: {value!r}")
    return value


def tree(repo: Path, ref: str) -> dict[bytes, str]:
    blobs = {}
    for record in git(repo, "ls-tree", "-r", "-z", ref).split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        _mode, kind, oid = metadata.decode("ascii").split()
        if kind == "blob":
            if not OID.fullmatch(oid) or path in blobs:
                raise ValueError("invalid or duplicate tree entry")
            blobs[path] = oid
        elif kind != "commit":
            raise ValueError(f"unexpected recursive tree entry kind: {kind}")
    return blobs


def local_headers(repo: Path, oids: list[str]) -> dict[str, int | None]:
    request = "".join(f"{oid}\n" for oid in oids).encode("ascii")
    lines = git(repo, "cat-file", "--batch-check", input=request).decode("ascii").splitlines()
    if len(lines) != len(oids):
        raise ValueError("local object reply count differs from the request")
    result = {}
    for oid, line in zip(oids, lines, strict=True):
        fields = line.split()
        if fields == [oid, "missing"]:
            result[oid] = None
        elif (
            len(fields) == 3
            and fields[:2] == [oid, "blob"]
            and fields[2].isascii()
            and fields[2].isdecimal()
            and str(int(fields[2])) == fields[2]
        ):
            result[oid] = int(fields[2])
        else:
            raise ValueError(f"unexpected local object reply: {line!r}")
    return result


def historical_policy_blobs(repo: Path, main: str) -> set[str]:
    """Keep every policy/selector version the first-parent release test reads."""
    records = iter(
        git(
            repo,
            "-c",
            "log.showSignature=false",
            "log",
            "--first-parent",
            "--diff-merges=first-parent",
            "--root",
            "--raw",
            "--no-renames",
            "--no-abbrev",
            "-z",
            "--format=",
            main,
            "--",
            "manifests/withdrawn-scopes.yaml",
            "manifests/releases",
        ).split(b"\0")
    )
    blobs = set()
    for raw in records:
        header = raw.lstrip(b"\n")
        if not header:
            continue
        if not header.startswith(b":"):
            raise ValueError("unexpected historical policy diff header")
        fields = header[1:].split()
        path = next(records, None)
        if len(fields) != 5 or path is None:
            raise ValueError("incomplete historical policy diff record")
        old_mode, new_mode, old_oid, new_oid, _status = fields
        if not (
            path == b"manifests/withdrawn-scopes.yaml" or path.startswith(b"manifests/releases/")
        ):
            raise ValueError("unexpected historical policy path")
        for mode, raw_oid in ((old_mode, old_oid), (new_mode, new_oid)):
            oid = raw_oid.decode("ascii")
            if not OID.fullmatch(oid):
                raise ValueError("invalid historical policy object identifier")
            if mode in {b"100644", b"100755", b"120000"} and oid != "0" * 40:
                blobs.add(oid)
    return blobs


def inventory(
    repo: Path, head: str, base: str | None
) -> tuple[dict[str, int], set[str], dict[str, str]]:
    if any(os.environ.get(name) != "1" for name in ("GIT_NO_LAZY_FETCH", "GIT_NO_REPLACE_OBJECTS")):
        raise ValueError("canonical lock reads require the offline Git environment")
    # The installed verifier's canonical parser rejects malformed/irregular
    # locks. Do not infer objects for entries that intentionally use R2 only.
    from axiom_corpus.corpus.corpus_locks import load_locks_at_ref

    main = commit(repo, os.environ.get("AXIOM_CORPUS_MAIN_REF", "origin/main"))
    refs = {"head": head, "main": main}
    if base:
        refs["base"] = base
        merge_base = git(repo, "merge-base", base, head).decode().strip()
        if not OID.fullmatch(merge_base):
            raise ValueError("unable to establish one complete merge base")
        refs["merge_base"] = merge_base
    tree_refs = {head, *([base, refs["merge_base"]] if base else [])}
    trees = {ref: tree(repo, ref) for ref in tree_refs}
    metadata = {
        oid
        for blobs in trees.values()
        for path, oid in blobs.items()
        if not path.startswith(PROTECTED)
    }
    metadata.update(historical_policy_blobs(repo, main))
    if base:
        changed = git(
            repo,
            "diff",
            "--no-ext-diff",
            "--name-only",
            "--no-renames",
            "-z",
            refs["merge_base"],
            head,
            "--",
        ).split(b"\0")
        for ref in (head, refs["merge_base"]):
            metadata.update(trees[ref][path] for path in changed if path in trees[ref])
    locks = load_locks_at_ref(repo, head)
    if locks.errors:
        raise ValueError("invalid HEAD locks: " + "; ".join(locks.errors))
    payloads = {}
    for entry in locks.entries():
        if entry.git_blob is None:
            continue
        if entry.git_blob in payloads and payloads[entry.git_blob] != entry.size:
            raise ValueError(f"conflicting lock sizes for {entry.git_blob}")
        payloads[entry.git_blob] = entry.size
    return payloads, metadata, refs


def prepare(repo: Path, head: str, base: str | None, output: Path, *, plan_only: bool) -> dict:
    started = time.monotonic()
    if git(repo, "rev-parse", "--show-object-format").strip() != b"sha1":
        raise ValueError("CI prefetch requires a SHA-1 repository")
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("CI verification requires full commit/tree history")
    head = commit(repo, head)
    if commit(repo, "HEAD") != head:
        raise ValueError("expected head differs from the actual checked-out commit")
    base = commit(repo, base) if base else None
    payloads, metadata, refs = inventory(repo, head, base)
    oids = sorted(set(payloads) | metadata)
    before = local_headers(repo, oids)
    missing = [oid for oid in oids if before[oid] is None]
    for oid, size in payloads.items():
        if before[oid] is not None and before[oid] != size:
            raise ValueError(f"local blob size differs from HEAD lock: {oid}")
    output.mkdir(parents=True, exist_ok=True)
    request = "".join(f"{oid}\n" for oid in missing).encode("ascii")
    (output / "missing-oids.txt").write_bytes(request)
    (output / "payload-inventory.json").write_text(
        json.dumps([{"oid": oid, "size": size} for oid, size in sorted(payloads.items())]) + "\n"
    )
    receipt = {
        "mode": "plan_only" if plan_only else "prefetch_and_verify",
        "refs": refs,
        "payload_object_count": len(payloads),
        "payload_declared_bytes": sum(payloads.values()),
        "metadata_object_count": len(metadata),
        "required_object_count": len(oids),
        "missing_before": len(missing),
        "missing_oid_set_sha256": hashlib.sha256(request).hexdigest(),
        "git_objects_before": git(repo, "count-objects", "-v").decode("ascii"),
    }
    if not plan_only:
        if missing:
            git(
                repo,
                "-c",
                "fetch.negotiationAlgorithm=noop",
                "fetch",
                "--no-tags",
                "--no-write-fetch-head",
                "--recurse-submodules=no",
                "--filter=blob:none",
                "origin",
                "--stdin",
                input=request,
            )
        after = local_headers(repo, oids)
        if any(size is None for size in after.values()):
            raise ValueError("explicit prefetch left required local objects missing")
        # Metadata has no independently declared size; its required type and
        # tree-anchored OID are checked above. Payload sizes come from HEAD locks.
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("verify-git-blobs.py")),
                "--repo",
                str(repo),
                "--inventory",
                str(output / "payload-inventory.json"),
            ],
            check=True,
            env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1"},
        )
        receipt["missing_after"] = 0
        receipt["git_objects_after"] = git(repo, "count-objects", "-v").decode("ascii")
    receipt["elapsed_seconds"] = time.monotonic() - started
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--base-ref")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args(argv)
    # Canonical lock-loader subprocesses inherit the process environment;
    # forcing flags only in this script's own Git wrapper would miss them.
    os.environ["GIT_NO_LAZY_FETCH"] = "1"
    os.environ["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        result = prepare(
            args.repo, args.head_ref, args.base_ref, args.output_dir, plan_only=args.plan_only
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"prefetch-git-blobs: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
