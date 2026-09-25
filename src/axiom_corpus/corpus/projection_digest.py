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
    """Return the canonical digest for one complete scope projection.

    Rows are consumed one at a time: each row's digest is computed as it
    arrives, and only its identity and 32-byte digest are kept for the final
    ordering, so memory does not grow with row bodies.
    """
    digest = ProjectionDigest(columns=columns, order_by=order_by, mapping_columns=mapping_columns)
    for row in rows:
        digest.add(row)
    return digest.hexdigest()


class ProjectionDigest:
    """Incremental form of :func:`projection_sha256`.

    ``hexdigest`` returns the digest, or raises the error, that hashing the
    same rows as one materialized collection gives. That computation checked
    every row's field set, then every row's identity, then encoded rows in
    identity order, so a failing row surfaces here in the same precedence: the
    first field-set mismatch in input order, else the first invalid identity in
    input order, else the first encoding failure in identity order. Errors are
    therefore held until ``hexdigest``; ``add`` raises nothing.
    """

    def __init__(
        self,
        *,
        columns: Sequence[str],
        order_by: Sequence[str],
        mapping_columns: set[str] | None = None,
    ) -> None:
        self._columns = tuple(columns)
        self._order_by = tuple(order_by)
        self._required = set(columns)
        self._mapping_fields = frozenset(mapping_columns or ())
        self._field_error: ProjectionDigestError | None = None
        self._identity_error: ProjectionDigestError | None = None
        # (identity + input index, exception) of the encoding failure that
        # comes first in identity order.
        self._encode_error: tuple[tuple[str | int, ...], Exception] | None = None
        self._entries: list[tuple[tuple[str | int, ...], bytes]] = []
        self._count = 0

    def add(self, row: Mapping[str, object]) -> None:
        index = self._count
        self._count += 1
        if self._field_error is not None:
            return
        if set(row) != self._required:
            missing = sorted(self._required - set(row))
            extra = sorted(set(row) - self._required)
            self._field_error = ProjectionDigestError(
                f"projection row fields differ; missing={missing!r}, extra={extra!r}"
            )
            return
        if self._identity_error is not None:
            return
        try:
            identity = tuple(_required_identity(row.get(field), field) for field in self._order_by)
        except ProjectionDigestError as exc:
            self._identity_error = exc
            return
        order: tuple[str | int, ...] = (*identity, index)
        try:
            payload = "".join(
                _encode_identifiers(row[column])
                if column in self._mapping_fields
                else _encode_scalar(row[column])
                for column in self._columns
            )
            row_digest = hashlib.sha256(payload.encode("utf-8")).digest()
        except Exception as exc:
            if self._encode_error is None or order < self._encode_error[0]:
                self._encode_error = (order, exc)
            return
        self._entries.append((order, row_digest))

    def hexdigest(self) -> str:
        if self._field_error is not None:
            raise self._field_error
        if self._identity_error is not None:
            raise self._identity_error
        if self._encode_error is not None:
            raise self._encode_error[1]
        # Identities are non-empty strings and the input index is unique, so
        # the sort never compares digests and matches a stable identity sort.
        self._entries.sort()
        scope = hashlib.sha256()
        for _order, row_digest in self._entries:
            scope.update(row_digest.hex().encode("ascii"))
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


def encode_identifiers_projection(value: object) -> str:
    """Public canonical encoding of one ``identifiers`` mapping.

    This is the exact serialization the signed provision projection digest
    binds (and the SQL migration mirrors), so two identifier values encode
    equal here if and only if they hash equal in release evidence. Raises
    :class:`ProjectionDigestError` for values outside the projection contract
    (non-string keys, nested structures, floats).
    """
    return _encode_identifiers(value)
