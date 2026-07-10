"""Canonical digests for the exact Supabase release projections.

The release signature must bind both immutable R2 artifacts and the database
rows made public by activation.  This module defines the Python half of the
cross-language serialization contract also implemented by the atomic-release
SQL migration.

Each scalar is encoded as ``N`` for NULL or ``V<utf8-byte-count>:<value>``.
Rows hash the ordered projection fields; scopes hash the ASCII row digests in
canonical identity order.  Length-prefixing makes the stream unambiguous
without relying on JSON formatting or locale-specific delimiters.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence

PROVISION_PROJECTION_COLUMNS = (
    "id",
    "jurisdiction",
    "doc_type",
    "parent_id",
    "level",
    "ordinal",
    "heading",
    "body",
    "source_url",
    "source_path",
    "citation_path",
    "version",
    "rulespec_path",
    "has_rulespec",
    "source_document_id",
    "source_as_of",
    "expression_date",
    "language",
    "legal_identifier",
    "identifiers",
)

NAVIGATION_PROJECTION_COLUMNS = (
    "id",
    "jurisdiction",
    "doc_type",
    "path",
    "parent_path",
    "segment",
    "label",
    "sort_key",
    "depth",
    "provision_id",
    "citation_path",
    "version",
    "has_children",
    "child_count",
    "has_rulespec",
    "encoded_descendant_count",
    "status",
)


class ProjectionDigestError(ValueError):
    """Raised when a projected row cannot be canonically serialized."""


def provision_projection_sha256(rows: Iterable[Mapping[str, object]]) -> str:
    """Hash exact provision projection rows in citation-path identity order."""
    return projection_sha256(
        rows,
        columns=PROVISION_PROJECTION_COLUMNS,
        order_by=("citation_path", "id"),
        mapping_columns={"identifiers"},
    )


def navigation_projection_sha256(rows: Iterable[Mapping[str, object]]) -> str:
    """Hash exact navigation projection rows in path identity order."""
    return projection_sha256(
        rows,
        columns=NAVIGATION_PROJECTION_COLUMNS,
        order_by=("path", "id"),
    )


def projection_sha256(
    rows: Iterable[Mapping[str, object]],
    *,
    columns: Sequence[str],
    order_by: Sequence[str],
    mapping_columns: set[str] | None = None,
) -> str:
    """Return the canonical digest for one complete scope projection."""
    materialized = tuple(rows)
    required = set(columns)
    for row in materialized:
        if set(row) != required:
            missing = sorted(required - set(row))
            extra = sorted(set(row) - required)
            raise ProjectionDigestError(
                f"projection row fields differ; missing={missing!r}, extra={extra!r}"
            )
    try:
        ordered = sorted(
            materialized,
            key=lambda row: tuple(_required_identity(row.get(field), field) for field in order_by),
        )
    except TypeError as exc:
        raise ProjectionDigestError("projection identity fields are not comparable") from exc

    scope = hashlib.sha256()
    mapping_fields = mapping_columns or set()
    for row in ordered:
        payload = "".join(
            _encode_identifiers(row[column])
            if column in mapping_fields
            else _encode_scalar(row[column])
            for column in columns
        )
        scope.update(hashlib.sha256(payload.encode("utf-8")).hexdigest().encode("ascii"))
    return scope.hexdigest()


def _required_identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProjectionDigestError(f"projection identity field {field!r} must be a string")
    return value


def _encode_scalar(value: object) -> str:
    if value is None:
        return "N"
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value
    else:
        raise ProjectionDigestError(f"unsupported projection scalar type: {type(value).__name__}")
    return f"V{len(text.encode('utf-8'))}:{text}"


def _encode_identifiers(value: object) -> str:
    if value is None:
        return "N"
    if not isinstance(value, Mapping):
        raise ProjectionDigestError("projection identifiers must be a string mapping")
    if any(not isinstance(key, str) for key in value):
        raise ProjectionDigestError("projection identifier keys must be strings")
    parts: list[str] = []
    for key in sorted(value):
        item = value[key]
        parts.append(_encode_scalar(key))
        parts.append(_encode_scalar(item))
    return _encode_scalar("".join(parts))
