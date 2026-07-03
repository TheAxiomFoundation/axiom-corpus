"""Signed corpus release manifests.

A release manifest records, for a single point-in-time corpus state, the
SHA-256 (and row counts, for line-delimited JSONL) of every published corpus
artifact under ``data/corpus`` plus the tracked ``claims`` files and
``DATA_INVENTORY.md``. Local artifact hashes are the source of truth; R2 object
keys are recorded as declared paths so a release can be resolved from the
bucket without requiring R2 credentials at manifest-build time.

The manifest is signed with HMAC-SHA256 over its canonical JSON encoding using
the key in the ``AXIOM_CORPUS_RELEASE_SIGNING_KEY`` environment variable. This
mirrors the applied-encoding manifest signing in ``axiom-encode`` so the two
repositories share one canonicalization and signature convention.
"""

from __future__ import annotations

from .manifest import (
    RELEASE_MANIFEST_SCHEMA_VERSION,
    RELEASE_MANIFEST_SIGNATURE_ALGORITHM,
    RELEASE_MANIFEST_SIGNATURE_KEY_ID,
    RELEASE_MANIFEST_SIGNING_KEY_ENV,
    ReleaseManifestError,
    build_release_manifest,
    canonical_manifest_bytes,
    manifest_signature_issue,
    serialize_manifest,
    sign_manifest,
    verify_manifest,
)

__all__ = [
    "RELEASE_MANIFEST_SCHEMA_VERSION",
    "RELEASE_MANIFEST_SIGNATURE_ALGORITHM",
    "RELEASE_MANIFEST_SIGNATURE_KEY_ID",
    "RELEASE_MANIFEST_SIGNING_KEY_ENV",
    "ReleaseManifestError",
    "build_release_manifest",
    "canonical_manifest_bytes",
    "manifest_signature_issue",
    "serialize_manifest",
    "sign_manifest",
    "verify_manifest",
]
