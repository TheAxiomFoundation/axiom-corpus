"""Validated, immutable corpus release objects."""

from __future__ import annotations

from .manifest import (
    RELEASE_OBJECT_PRIVATE_KEY_ENV,
    RELEASE_OBJECT_PUBLIC_KEY_ENV,
    RELEASE_OBJECT_SCHEMA_VERSION,
    RELEASE_OBJECT_SIGNATURE_ALGORITHM,
    RELEASE_OBJECT_SIGNATURE_KEY_ID,
    ReleaseManifestError,
    build_release_content,
    build_unsigned_release_object,
    canonical_release_object_bytes,
    content_addressed_r2_key,
    load_release_object,
    release_object_r2_key,
    serialize_release_object,
    sign_release_object,
    verify_release_object,
)
from .publication import R2ReadbackReport, stage_release_artifacts, stage_signed_release_object

__all__ = [
    "RELEASE_OBJECT_PRIVATE_KEY_ENV",
    "RELEASE_OBJECT_PUBLIC_KEY_ENV",
    "RELEASE_OBJECT_SCHEMA_VERSION",
    "RELEASE_OBJECT_SIGNATURE_ALGORITHM",
    "RELEASE_OBJECT_SIGNATURE_KEY_ID",
    "ReleaseManifestError",
    "build_release_content",
    "build_unsigned_release_object",
    "canonical_release_object_bytes",
    "content_addressed_r2_key",
    "load_release_object",
    "release_object_r2_key",
    "serialize_release_object",
    "sign_release_object",
    "verify_release_object",
    "R2ReadbackReport",
    "stage_release_artifacts",
    "stage_signed_release_object",
]
