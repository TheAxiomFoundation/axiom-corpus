"""Immutable, public-key-verifiable corpus release objects.

A release object is created only by the publication controller after it has
staged and read back every content-addressed R2 object, checked exact Supabase
row counts, and rerun deep corpus validation.  The signature therefore attests
to that validated publication result, rather than to an arbitrary collection
of locally hashed bytes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from base64 import b64decode, b64encode
from binascii import Error as BinasciiError
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from axiom_corpus.corpus.models import DocumentClass
from axiom_corpus.corpus.releases import ReleaseManifest, validate_release_name

RELEASE_OBJECT_SCHEMA_VERSION = "axiom-corpus/release-object/v2"
RELEASE_OBJECT_SIGNATURE_ALGORITHM = "ed25519"
RELEASE_OBJECT_SIGNATURE_KEY_ID = "axiom-corpus-release-v2"
RELEASE_OBJECT_PRIVATE_KEY_ENV = "AXIOM_CORPUS_RELEASE_PRIVATE_KEY"
RELEASE_OBJECT_PUBLIC_KEY_ENV = "AXIOM_CORPUS_RELEASE_PUBLIC_KEY"
DEFAULT_R2_BUCKET = "axiom-corpus"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SCOPE_COMPONENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,255}$")
_ARTIFACT_CLASSES = ("inventory", "provisions", "coverage", "sources")


class ReleaseManifestError(RuntimeError):
    """Raised when a release object cannot be built, signed, or verified."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl_row_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Return the one canonical JSON encoding used for hashes and signatures."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def release_content_sha256(content: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def selector_sha256(release: ReleaseManifest) -> str:
    selector = {
        "name": release.name,
        "scopes": [
            {
                "jurisdiction": scope.jurisdiction,
                "document_class": scope.document_class,
                "version": scope.version,
            }
            for scope in release.scopes
        ],
    }
    return hashlib.sha256(canonical_json_bytes(selector)).hexdigest()


def content_addressed_r2_key(sha256: str) -> str:
    if not _SHA256_RE.fullmatch(sha256):
        raise ReleaseManifestError(f"invalid artifact sha256: {sha256!r}")
    return f"objects/sha256/{sha256[:2]}/{sha256}"


def release_object_r2_key(release_name: str, content_sha256: str) -> str:
    _require_release_name(release_name)
    if not _SHA256_RE.fullmatch(content_sha256):
        raise ReleaseManifestError(f"invalid release content sha256: {content_sha256!r}")
    return f"releases/{release_name}/{content_sha256}.json"


def build_release_content(
    repo_root: Path,
    *,
    release: ReleaseManifest,
    validation: Mapping[str, Any],
    base: str = "data/corpus",
    bucket: str = DEFAULT_R2_BUCKET,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build validated release content for an explicit named scope selector."""
    _require_release_name(release.name)
    if not release.scopes:
        raise ReleaseManifestError("a release must contain at least one scope")
    if validation.get("passed") is not True:
        raise ReleaseManifestError("release validation must have passed before signing")
    if base != "data/corpus":
        raise ReleaseManifestError("immutable releases require corpus_base data/corpus")

    root = repo_root.resolve()
    base_path = (root / base).resolve()
    try:
        base_path.relative_to(root)
    except ValueError as exc:
        raise ReleaseManifestError(f"corpus base escapes repository: {base}") from exc
    if not base_path.is_dir():
        raise ReleaseManifestError(f"corpus base directory not found: {base_path}")

    artifacts: list[dict[str, Any]] = []
    scopes: list[dict[str, Any]] = []
    for scope in release.scopes:
        scope_entries = _scope_artifact_entries(root, base_path, base, bucket, scope.key)
        provision_entries = [
            entry for entry in scope_entries if entry["artifact_class"] == "provisions"
        ]
        if len(provision_entries) != 1:
            raise ReleaseManifestError(
                "release scope must have exactly one provisions artifact: "
                f"{scope.jurisdiction}/{scope.document_class}/{scope.version}"
            )
        provision_rows = provision_entries[0].get("rows")
        if not isinstance(provision_rows, int) or provision_rows <= 0:
            raise ReleaseManifestError(
                "release scope provisions must contain at least one row: "
                f"{scope.jurisdiction}/{scope.document_class}/{scope.version}"
            )
        scopes.append(
            {
                "jurisdiction": scope.jurisdiction,
                "document_class": scope.document_class,
                "version": scope.version,
                "provision_rows": provision_rows,
                "navigation_rows": provision_rows,
            }
        )
        artifacts.extend(scope_entries)

    git = _git_provenance(root)
    if git is None:
        raise ReleaseManifestError("release publication requires an exact git checkout identity")
    if created_at is None:
        created_at = git["committed_at"]

    return {
        "release": release.name,
        "created_at": created_at,
        "selector_sha256": selector_sha256(release),
        "corpus_base": base,
        "git": git,
        "r2": {"bucket": bucket, "addressing": "sha256"},
        "scopes": scopes,
        "artifacts": sorted(artifacts, key=lambda entry: str(entry["path"])),
        "validation": copy.deepcopy(dict(validation)),
    }


def build_unsigned_release_object(content: Mapping[str, Any]) -> dict[str, Any]:
    release = content.get("release")
    if not isinstance(release, str):
        raise ReleaseManifestError("release content is missing its release name")
    _require_release_name(release)
    materialized = copy.deepcopy(dict(content))
    return {
        "schema_version": RELEASE_OBJECT_SCHEMA_VERSION,
        "release": release,
        "content_sha256": release_content_sha256(materialized),
        "content": materialized,
    }


def canonical_release_object_bytes(payload: Mapping[str, Any]) -> bytes:
    unsigned = copy.deepcopy(dict(payload))
    unsigned.pop("signature", None)
    return canonical_json_bytes(unsigned)


def sign_release_object(
    payload: Mapping[str, Any],
    *,
    private_key: str,
) -> dict[str, Any]:
    """Attach an Ed25519 signature to an already validated release object."""
    signed = copy.deepcopy(dict(payload))
    signed.pop("signature", None)
    _validate_unsigned_release_object(signed)
    signature = _load_ed25519_private_key(private_key).sign(canonical_release_object_bytes(signed))
    signed["signature"] = {
        "algorithm": RELEASE_OBJECT_SIGNATURE_ALGORITHM,
        "key_id": RELEASE_OBJECT_SIGNATURE_KEY_ID,
        "value": b64encode(signature).decode("ascii"),
    }
    return signed


def verify_release_object(payload: Mapping[str, Any], *, public_key: str) -> None:
    """Verify schema, content address, validation attestation, and signature."""
    materialized = copy.deepcopy(dict(payload))
    _validate_unsigned_release_object(materialized)
    signature = materialized.get("signature")
    if not isinstance(signature, dict):
        raise ReleaseManifestError("release object is missing its signature")
    if set(signature) != {"algorithm", "key_id", "value"}:
        raise ReleaseManifestError("release object signature does not match the v2 schema")
    if signature.get("algorithm") != RELEASE_OBJECT_SIGNATURE_ALGORITHM:
        raise ReleaseManifestError("release object uses an unsupported signature algorithm")
    if signature.get("key_id") != RELEASE_OBJECT_SIGNATURE_KEY_ID:
        raise ReleaseManifestError("release object uses an unknown signing key")
    encoded = signature.get("value")
    if not isinstance(encoded, str):
        raise ReleaseManifestError("release object signature value is missing")
    try:
        raw_signature = b64decode(encoded.encode("ascii"), validate=True)
    except (BinasciiError, UnicodeEncodeError) as exc:
        raise ReleaseManifestError("release object signature encoding is invalid") from exc
    try:
        _load_ed25519_public_key(public_key).verify(
            raw_signature,
            canonical_release_object_bytes(materialized),
        )
    except InvalidSignature as exc:
        raise ReleaseManifestError("release object signature is invalid") from exc


def serialize_release_object(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def load_release_object(path: Path, *, public_key: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseManifestError(f"cannot read release object {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseManifestError(f"release object {path} must be a JSON object")
    verify_release_object(payload, public_key=public_key)
    return payload


def _validate_unsigned_release_object(payload: Mapping[str, Any]) -> None:
    allowed = {"schema_version", "release", "content_sha256", "content", "signature"}
    extra = set(payload) - allowed
    if extra:
        raise ReleaseManifestError(
            f"release object has unsupported top-level fields: {', '.join(sorted(extra))}"
        )
    if payload.get("schema_version") != RELEASE_OBJECT_SCHEMA_VERSION:
        raise ReleaseManifestError("release object uses an unsupported schema version")
    release = payload.get("release")
    if not isinstance(release, str):
        raise ReleaseManifestError("release object is missing its release name")
    _require_release_name(release)
    content = payload.get("content")
    if not isinstance(content, dict):
        raise ReleaseManifestError("release object content must be a JSON object")
    if set(content) != {
        "release",
        "created_at",
        "selector_sha256",
        "corpus_base",
        "git",
        "r2",
        "scopes",
        "artifacts",
        "validation",
    }:
        raise ReleaseManifestError("release object content does not match the v2 schema")
    if content.get("release") != release:
        raise ReleaseManifestError("release object name does not match its content")
    if not isinstance(content.get("created_at"), str) or not content["created_at"]:
        raise ReleaseManifestError("release object has an invalid creation time")
    git = content.get("git")
    if not isinstance(git, dict) or set(git) != {"commit", "committed_at"}:
        raise ReleaseManifestError("release object has invalid git provenance")
    if (
        not isinstance(git.get("commit"), str)
        or re.fullmatch(r"[0-9a-f]{40}", git["commit"]) is None
        or not isinstance(git.get("committed_at"), str)
        or not git["committed_at"]
    ):
        raise ReleaseManifestError("release object has invalid git provenance")
    expected_digest = release_content_sha256(content)
    if payload.get("content_sha256") != expected_digest:
        raise ReleaseManifestError("release object content sha256 does not match")
    validation = content.get("validation")
    if not isinstance(validation, dict) or validation.get("passed") is not True:
        raise ReleaseManifestError("release object does not attest passed validation")
    scopes = content.get("scopes")
    artifacts = content.get("artifacts")
    if not isinstance(scopes, list) or not scopes:
        raise ReleaseManifestError("release object must contain at least one scope")
    if not isinstance(artifacts, list) or not artifacts:
        raise ReleaseManifestError("release object must contain artifact entries")
    _validate_scope_entries(scopes)
    selector = {
        "name": release,
        "scopes": [
            {field: raw[field] for field in ("jurisdiction", "document_class", "version")}
            for raw in scopes
        ],
    }
    if not isinstance(content.get("selector_sha256"), str) or not _SHA256_RE.fullmatch(
        content["selector_sha256"]
    ):
        raise ReleaseManifestError("release object has an invalid selector sha256")
    if content["selector_sha256"] != hashlib.sha256(canonical_json_bytes(selector)).hexdigest():
        raise ReleaseManifestError("release selector sha256 does not match its scopes")
    if content.get("corpus_base") != "data/corpus":
        raise ReleaseManifestError("release object uses a non-canonical corpus base")
    r2 = content.get("r2")
    if (
        not isinstance(r2, dict)
        or set(r2) != {"bucket", "addressing"}
        or not isinstance(r2.get("bucket"), str)
        or not r2["bucket"]
        or r2.get("addressing") != "sha256"
    ):
        raise ReleaseManifestError("release object has an invalid R2 content boundary")
    bucket = str(r2["bucket"])
    _validate_artifact_entries(artifacts, bucket=bucket)
    _validate_scope_artifact_membership(scopes, artifacts)
    _validate_validation_attestation(
        validation,
        scopes=scopes,
        artifacts=artifacts,
        bucket=bucket,
    )


def _validate_scope_entries(scopes: Sequence[Any]) -> None:
    seen: set[tuple[str, str, str]] = set()
    for raw in scopes:
        if not isinstance(raw, dict):
            raise ReleaseManifestError("release object contains a non-object scope")
        if set(raw) != {
            "jurisdiction",
            "document_class",
            "version",
            "provision_rows",
            "navigation_rows",
        }:
            raise ReleaseManifestError("release object scope does not match the v2 schema")
        key = tuple(
            str(raw.get(field) or "") for field in ("jurisdiction", "document_class", "version")
        )
        if any(not _SCOPE_COMPONENT_RE.fullmatch(part) for part in key):
            raise ReleaseManifestError("release object scope has an invalid identity field")
        try:
            DocumentClass(key[1])
        except ValueError as exc:
            raise ReleaseManifestError(
                f"release object scope has an invalid document class: {key[1]}"
            ) from exc
        typed_key = (key[0], key[1], key[2])
        if typed_key in seen:
            raise ReleaseManifestError(f"release object contains duplicate scope: {'/'.join(key)}")
        seen.add(typed_key)
        rows = raw.get("provision_rows")
        if not isinstance(rows, int) or isinstance(rows, bool) or rows <= 0:
            raise ReleaseManifestError(
                f"release object scope has invalid provision_rows: {'/'.join(key)}"
            )
        navigation_rows = raw.get("navigation_rows")
        if (
            not isinstance(navigation_rows, int)
            or isinstance(navigation_rows, bool)
            or navigation_rows != rows
        ):
            raise ReleaseManifestError(
                f"release object scope has inconsistent navigation_rows: {'/'.join(key)}"
            )


def _validate_artifact_entries(artifacts: Sequence[Any], *, bucket: str) -> None:
    seen_paths: set[str] = set()
    ordered_paths: list[str] = []
    for raw in artifacts:
        if not isinstance(raw, dict):
            raise ReleaseManifestError("release object contains a non-object artifact")
        required_fields = {
            "artifact_class",
            "path",
            "sha256",
            "bytes",
            "r2_bucket",
            "r2_key",
        }
        path = raw.get("path")
        digest = raw.get("sha256")
        size = raw.get("bytes")
        key = raw.get("r2_key")
        artifact_class = raw.get("artifact_class")
        if artifact_class not in _ARTIFACT_CLASSES:
            raise ReleaseManifestError("release artifact has an unsupported class")
        expected_fields = required_fields | ({"rows"} if artifact_class == "provisions" else set())
        if set(raw) != expected_fields:
            raise ReleaseManifestError("release artifact does not match the v2 schema")
        if (
            not isinstance(path, str)
            or not path.startswith("data/corpus/")
            or "\\" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))
        ):
            raise ReleaseManifestError("release artifact path is not canonical")
        expected_prefix = f"data/corpus/{artifact_class}/"
        if not path.startswith(expected_prefix):
            raise ReleaseManifestError(f"release artifact class does not match its path: {path}")
        if path in seen_paths:
            raise ReleaseManifestError(f"release object contains duplicate artifact: {path}")
        seen_paths.add(path)
        ordered_paths.append(path)
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise ReleaseManifestError(f"release artifact has invalid sha256: {path}")
        if key != content_addressed_r2_key(digest):
            raise ReleaseManifestError(
                f"release artifact has a non-content-addressed R2 key: {path}"
            )
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ReleaseManifestError(f"release artifact has invalid byte count: {path}")
        if raw.get("r2_bucket") != bucket:
            raise ReleaseManifestError(f"release artifact uses the wrong R2 bucket: {path}")
        if artifact_class == "provisions":
            rows = raw.get("rows")
            if not isinstance(rows, int) or isinstance(rows, bool) or rows <= 0:
                raise ReleaseManifestError(
                    f"release provisions artifact has an invalid row count: {path}"
                )
    if ordered_paths != sorted(ordered_paths):
        raise ReleaseManifestError("release artifacts are not in canonical path order")


def _validate_scope_artifact_membership(scopes: Sequence[Any], artifacts: Sequence[Any]) -> None:
    entries_by_path = {str(raw["path"]): raw for raw in artifacts if isinstance(raw, dict)}
    claimed_paths: set[str] = set()
    for raw_scope in scopes:
        if not isinstance(raw_scope, dict):
            raise ReleaseManifestError("release object contains a non-object scope")
        jurisdiction = str(raw_scope["jurisdiction"])
        document_class = str(raw_scope["document_class"])
        version = str(raw_scope["version"])
        identity = f"{jurisdiction}/{document_class}/{version}"
        required = {
            "inventory": (f"data/corpus/inventory/{jurisdiction}/{document_class}/{version}.json"),
            "provisions": (
                f"data/corpus/provisions/{jurisdiction}/{document_class}/{version}.jsonl"
            ),
            "coverage": (f"data/corpus/coverage/{jurisdiction}/{document_class}/{version}.json"),
        }
        for artifact_class, path in required.items():
            entry = entries_by_path.get(path)
            if not isinstance(entry, dict) or entry.get("artifact_class") != artifact_class:
                raise ReleaseManifestError(
                    f"release scope lacks its {artifact_class} artifact: {identity}"
                )
            claimed_paths.add(path)
        provision_entry = entries_by_path[required["provisions"]]
        if provision_entry.get("rows") != raw_scope["provision_rows"]:
            raise ReleaseManifestError(
                f"release scope row count does not match its provisions artifact: {identity}"
            )
        source_prefix = f"data/corpus/sources/{jurisdiction}/{document_class}/{version}/"
        source_paths = [
            path
            for path, entry in entries_by_path.items()
            if path.startswith(source_prefix) and entry.get("artifact_class") == "sources"
        ]
        if not source_paths:
            raise ReleaseManifestError(f"release scope lacks source artifacts: {identity}")
        claimed_paths.update(source_paths)
    extra = sorted(set(entries_by_path) - claimed_paths)
    if extra:
        raise ReleaseManifestError(
            "release object contains artifacts outside its declared scopes: " + ", ".join(extra)
        )


def _validate_validation_attestation(
    validation: Mapping[str, Any],
    *,
    scopes: Sequence[Any],
    artifacts: Sequence[Any],
    bucket: str,
) -> None:
    if set(validation) != {
        "passed",
        "deep_validation",
        "r2_readback",
        "supabase_counts",
    }:
        raise ReleaseManifestError("release validation does not match the v2 schema")
    deep = validation.get("deep_validation")
    if not isinstance(deep, dict):
        raise ReleaseManifestError("release object lacks deep-validation evidence")
    if (
        set(deep) != {"error_count", "warning_count", "scope_count"}
        or not isinstance(deep.get("error_count"), int)
        or isinstance(deep.get("error_count"), bool)
        or deep["error_count"] != 0
        or not isinstance(deep.get("scope_count"), int)
        or isinstance(deep.get("scope_count"), bool)
        or deep["scope_count"] != len(scopes)
        or not isinstance(deep.get("warning_count"), int)
        or isinstance(deep.get("warning_count"), bool)
        or deep["warning_count"] < 0
    ):
        raise ReleaseManifestError("release object deep-validation evidence is inconsistent")

    readback = validation.get("r2_readback")
    if not isinstance(readback, dict):
        raise ReleaseManifestError("release object lacks R2 readback evidence")
    if set(readback) != {"bucket", "artifact_count", "artifact_bytes", "verified_keys"}:
        raise ReleaseManifestError("release R2 readback does not match the v2 schema")
    expected_keys = [str(entry["r2_key"]) for entry in artifacts if isinstance(entry, dict)]
    expected_bytes = sum(int(entry["bytes"]) for entry in artifacts if isinstance(entry, dict))
    if (
        not isinstance(readback.get("artifact_count"), int)
        or isinstance(readback.get("artifact_count"), bool)
        or not isinstance(readback.get("artifact_bytes"), int)
        or isinstance(readback.get("artifact_bytes"), bool)
        or not isinstance(readback.get("verified_keys"), list)
        or not all(isinstance(key, str) for key in readback["verified_keys"])
        or readback.get("bucket") != bucket
        or readback.get("artifact_count") != len(artifacts)
        or readback.get("artifact_bytes") != expected_bytes
        or readback.get("verified_keys") != expected_keys
    ):
        raise ReleaseManifestError("release object R2 readback evidence is inconsistent")

    raw_counts = validation.get("supabase_counts")
    if not isinstance(raw_counts, list) or len(raw_counts) != len(scopes):
        raise ReleaseManifestError("release object staged-count evidence is incomplete")
    counts: dict[tuple[str, str, str], tuple[object, object, object, object]] = {}
    for raw in raw_counts:
        if not isinstance(raw, dict):
            raise ReleaseManifestError("release object has invalid staged-count evidence")
        if set(raw) != {
            "jurisdiction",
            "document_class",
            "version",
            "expected",
            "actual",
            "expected_navigation",
            "actual_navigation",
        }:
            raise ReleaseManifestError("release staged-count evidence does not match the v2 schema")
        if any(
            not isinstance(raw.get(field), int) or isinstance(raw.get(field), bool)
            for field in ("expected", "actual", "expected_navigation", "actual_navigation")
        ):
            raise ReleaseManifestError("release object has non-integer staged-count evidence")
        key = tuple(
            str(raw.get(field) or "") for field in ("jurisdiction", "document_class", "version")
        )
        typed_key = (key[0], key[1], key[2])
        if not all(typed_key) or typed_key in counts:
            raise ReleaseManifestError("release object has invalid staged-count identity")
        counts[typed_key] = (
            raw.get("expected"),
            raw.get("actual"),
            raw.get("expected_navigation"),
            raw.get("actual_navigation"),
        )
    for raw_scope in scopes:
        if not isinstance(raw_scope, dict):
            raise ReleaseManifestError("release object contains a non-object scope")
        key = (
            str(raw_scope["jurisdiction"]),
            str(raw_scope["document_class"]),
            str(raw_scope["version"]),
        )
        expected_rows = raw_scope["provision_rows"]
        expected_navigation = raw_scope["navigation_rows"]
        if counts.get(key) != (
            expected_rows,
            expected_rows,
            expected_navigation,
            expected_navigation,
        ):
            raise ReleaseManifestError(
                f"release object staged-count evidence does not match scope: {'/'.join(key)}"
            )


def _scope_artifact_entries(
    repo_root: Path,
    base_path: Path,
    base: str,
    bucket: str,
    scope_key: tuple[str, str, str],
) -> list[dict[str, Any]]:
    jurisdiction, document_class, version = scope_key
    relative_files: dict[str, list[Path]] = {
        "inventory": [base_path / "inventory" / jurisdiction / document_class / f"{version}.json"],
        "provisions": [
            base_path / "provisions" / jurisdiction / document_class / f"{version}.jsonl"
        ],
        "coverage": [base_path / "coverage" / jurisdiction / document_class / f"{version}.json"],
    }
    source_root = base_path / "sources" / jurisdiction / document_class / version
    relative_files["sources"] = (
        sorted(path for path in source_root.rglob("*") if path.is_file())
        if source_root.is_dir()
        else []
    )

    entries: list[dict[str, Any]] = []
    for artifact_class in _ARTIFACT_CLASSES:
        paths = relative_files[artifact_class]
        if not paths or any(not path.is_file() for path in paths):
            raise ReleaseManifestError(
                f"missing {artifact_class} artifact for {jurisdiction}/{document_class}/{version}"
            )
        for path in paths:
            digest = sha256_file(path)
            relative = path.relative_to(repo_root).as_posix()
            entry: dict[str, Any] = {
                "artifact_class": artifact_class,
                "path": relative,
                "sha256": digest,
                "bytes": path.stat().st_size,
                "r2_bucket": bucket,
                "r2_key": content_addressed_r2_key(digest),
            }
            if path.suffix == ".jsonl":
                entry["rows"] = jsonl_row_count(path)
            entries.append(entry)
    return entries


def _git_provenance(repo_root: Path) -> dict[str, str] | None:
    try:
        commit = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        epoch = subprocess.run(
            ["git", "-C", str(repo_root), "show", "-s", "--format=%ct", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    if not commit or not epoch:
        return None
    committed_at = datetime.fromtimestamp(int(epoch), tz=UTC).isoformat().replace("+00:00", "Z")
    return {"commit": commit, "committed_at": committed_at}


def _load_ed25519_private_key(private_key: str) -> Ed25519PrivateKey:
    text = private_key.strip().replace("\\n", "\n")
    if text.startswith("-----BEGIN "):
        try:
            loaded = serialization.load_pem_private_key(text.encode("utf-8"), password=None)
        except (TypeError, ValueError) as exc:
            raise ReleaseManifestError("release private key PEM is invalid") from exc
        if not isinstance(loaded, Ed25519PrivateKey):
            raise ReleaseManifestError("release private key must be Ed25519")
        return loaded
    raw = _load_raw_key(text, kind="private")
    return Ed25519PrivateKey.from_private_bytes(raw)


def _load_ed25519_public_key(public_key: str) -> Ed25519PublicKey:
    text = public_key.strip().replace("\\n", "\n")
    if text.startswith("-----BEGIN "):
        try:
            loaded = serialization.load_pem_public_key(text.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ReleaseManifestError("release public key PEM is invalid") from exc
        if not isinstance(loaded, Ed25519PublicKey):
            raise ReleaseManifestError("release public key must be Ed25519")
        return loaded
    raw = _load_raw_key(text, kind="public")
    return Ed25519PublicKey.from_public_bytes(raw)


def _load_raw_key(text: str, *, kind: str) -> bytes:
    try:
        raw = b64decode(text.encode("ascii"), validate=True)
    except (BinasciiError, UnicodeEncodeError) as exc:
        raise ReleaseManifestError(f"release {kind} key must be raw base64 or PEM") from exc
    if len(raw) != 32:
        raise ReleaseManifestError(f"release {kind} key must decode to 32 bytes")
    return raw


def _require_release_name(name: str) -> None:
    try:
        validate_release_name(name)
    except ValueError as exc:
        raise ReleaseManifestError(str(exc)) from exc
