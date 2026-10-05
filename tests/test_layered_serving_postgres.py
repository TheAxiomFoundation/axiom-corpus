"""PostgreSQL behavior of layered release serving (20260927110000).

A base scope is served underneath the primary scopes of its release: for a
citation path both layers of a (jurisdiction, document_class) pair carry, the
primary row is served, and the base row everywhere else. These tests run on a
schema shaped like production before the layered migration (the serving views,
navigation policies, root counts and reference RPC as their latest migrations
define them, navigation_nodes in its production column order), with the
layered migration applied on top. The previous definitions are also installed,
unchanged, in a separate ``reference`` schema, so the differential tests can
compare the migrated objects with them on the same rows.

Release objects are built and signed by the publisher's own code
(``build_unsigned_release_object`` picks v3 or v4) and verified with
``verify_release_object`` before activation, so every object the database
accepts here is one the publisher could have produced.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import uuid
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.navigation import (
    _break_parent_cycles,
    _normalize_sort_segment,
    _resolve_depths,
    _segment,
    build_navigation_nodes,
    merge_layered_parent_paths,
    scope_parent_paths,
)
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    LAYER_BASE,
    LAYER_PRIMARY,
    ReleaseManifest,
    ReleaseScope,
)
from axiom_corpus.corpus.supabase import iter_supabase_rows
from axiom_corpus.query.supabase import SupabaseQuery
from axiom_corpus.release.manifest import (
    RELEASE_OBJECT_SCHEMA_V3,
    RELEASE_OBJECT_SCHEMA_V4,
    build_unsigned_release_object,
    content_addressed_r2_key,
    selector_sha256,
    sign_release_object,
    verify_release_object,
)
from tests.test_atomic_release_postgres import (
    CHUNKED_ACTIVATION_MIGRATION,
    COMPACT_RELEASE_OBJECTS_MIGRATION,
    LAYERED_SERVING_MIGRATION,
    MIGRATION,
    PRE_MIGRATION_SCHEMA,
    PROFILED_RELEASE_MIGRATION,
    REQUIRED_ROLES,
    SCOPE_MIGRATION,
    STAGED_RELEASE_OBJECT_MIGRATION,
    STAGED_RELEASE_OBJECT_V4_MIGRATION,
    TEST_PUBLIC_KEY,
    TEST_SIGNING_KEY,
)

psycopg2 = pytest.importorskip("psycopg2")
errors = pytest.importorskip("psycopg2.errors")
sql = pytest.importorskip("psycopg2.sql")
Json = pytest.importorskip("psycopg2.extras").Json

DATABASE_URL = os.environ.get("DATABASE_URL")
MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
PRIVATE_KEY = base64.b64encode(
    TEST_SIGNING_KEY.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
).decode()

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for PostgreSQL migration integration tests",
)


def _migration_slice(name: str, start: str, end: str | None = None) -> str:
    """Return the text of one historical migration from ``start`` up to ``end``."""
    text = (MIGRATIONS / name).read_text(encoding="utf-8")
    begin = text.index(start)
    stop = len(text) if end is None else text.index(end, begin)
    return text[begin:stop]


# navigation_nodes in production column order and types (20260505120000 plus
# the version column 20260513101000 appended), so CREATE OR REPLACE VIEW in the
# layered migration is checked against the column list production has.
_FIXTURE_NAVIGATION_COLUMNS = """  provision_id uuid,
  citation_path text,
  has_children boolean NOT NULL DEFAULT false,
  child_count integer NOT NULL DEFAULT 0,
  has_rulespec boolean NOT NULL DEFAULT false,
  encoded_descendant_count integer NOT NULL DEFAULT 0,
  status text,
  version text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);"""
_PRODUCTION_NAVIGATION_COLUMNS = """  provision_id text,
  citation_path text,
  has_children boolean NOT NULL DEFAULT false,
  child_count integer NOT NULL DEFAULT 0,
  has_rulespec boolean NOT NULL DEFAULT false,
  encoded_descendant_count integer NOT NULL DEFAULT 0,
  status text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version text
);"""
assert PRE_MIGRATION_SCHEMA.count(_FIXTURE_NAVIGATION_COLUMNS) == 1
PRODUCTION_SHAPED_SCHEMA = PRE_MIGRATION_SCHEMA.replace(
    _FIXTURE_NAVIGATION_COLUMNS, _PRODUCTION_NAVIGATION_COLUMNS
)
NAVIGATION_COLUMNS = (
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
    "has_children",
    "child_count",
    "has_rulespec",
    "encoded_descendant_count",
    "status",
    "created_at",
    "updated_at",
    "version",
)
TREE_COLUMNS = (
    "parent_path",
    "segment",
    "label",
    "sort_key",
    "depth",
    "has_children",
    "child_count",
    "encoded_descendant_count",
)

# Root-document counts as open PR #666 (20260910140000) defines them: served
# roots only, the intended definition. The 20260910150000 index comment assumes
# it, and production's function returns it (checked read-only, in the PR
# body). This repository last defined the function in 20260910120000, which
# counts every stored root; test_root_counts_are_served_roots_not_every_stored_root
# shows where the two differ.
PR_666_ROOT_COUNTS = """
CREATE OR REPLACE FUNCTION corpus.get_root_document_counts()
RETURNS TABLE (
  jurisdiction text,
  doc_type text,
  document_count bigint
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = corpus, public
AS $$
  SELECT
    jurisdiction,
    COALESCE(NULLIF(doc_type, ''), 'unknown') AS doc_type,
    COUNT(*)::bigint AS document_count
  FROM corpus.current_navigation_nodes
  WHERE parent_path IS NULL
    AND jurisdiction IS NOT NULL
  GROUP BY jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown')
  ORDER BY jurisdiction, doc_type
$$;
GRANT EXECUTE ON FUNCTION corpus.get_root_document_counts() TO anon, authenticated;
"""


def _production_serving_sql() -> str:
    """The pre-layer serving objects, from the migrations that last define them."""
    return "\n".join(
        (
            # Navigation indexes production has (20260505120000, 20260513140000,
            # 20260910150000) and the provisions scope index (20260513140000).
            _migration_slice(
                "20260505120000_corpus_navigation_nodes.sql",
                "CREATE INDEX IF NOT EXISTS idx_navigation_nodes_parent_sort",
                "-- Encoded-only browsing",
            ),
            _migration_slice(
                "20260513140000_restore_navigation_nodes_policy.sql",
                "CREATE INDEX IF NOT EXISTS idx_provisions_release_scope_version",
                "-- ====",
            ),
            _migration_slice(
                "20260910150000_root_document_counts_index_version.sql",
                "CREATE INDEX IF NOT EXISTS idx_navigation_nodes_roots_by_scope_version",
                "DROP INDEX",
            ),
            # The serving views and navigation policies (20260513180000).
            "ALTER TABLE corpus.navigation_nodes ENABLE ROW LEVEL SECURITY;",
            "GRANT SELECT ON corpus.navigation_nodes TO anon, authenticated;",
            _migration_slice(
                "20260513180000_tighten_version_aware_views.sql",
                "CREATE OR REPLACE VIEW corpus.current_provisions AS",
                "-- ============================================================================\n"
                "-- 3. Refresh",
            ),
            "GRANT SELECT ON corpus.current_release_scopes TO anon, authenticated;",
            "GRANT SELECT ON corpus.current_provisions TO anon, authenticated;",
            "GRANT SELECT ON corpus.current_provision_counts TO anon, authenticated;",
            PR_666_ROOT_COUNTS,
            # Citation references (20260416220000) with the current-release RPC
            # of 20260507150000, and provision anchors (20260704120000).
            (MIGRATIONS / "20260416220000_corpus_provision_references.sql").read_text(
                encoding="utf-8"
            ),
            _migration_slice(
                "20260507150000_restrict_public_corpus_base_reads.sql",
                "CREATE OR REPLACE FUNCTION corpus.get_provision_references",
                "REVOKE EXECUTE ON FUNCTION corpus.get_all_corpus_stats",
            ),
            (MIGRATIONS / "20260704120000_corpus_provision_anchors.sql").read_text(
                encoding="utf-8"
            ),
        )
    )


# The pre-layer definitions, unchanged except for living in their own schema:
# current_release_scopes (20260718193000), current_provisions, legacy_provisions,
# current_navigation_nodes and the navigation policy (20260513180000), the
# current_provision_counts aggregate (20260507110000) and #666's root counts.
REFERENCE_SQL = """
CREATE SCHEMA reference;
CREATE VIEW reference.current_release_scopes AS
SELECT
  scopes.release_name,
  scopes.jurisdiction,
  scopes.document_class,
  scopes.version,
  scopes.synced_at
FROM corpus.release_scopes scopes
JOIN corpus.active_scope_pointer active
  ON active.jurisdiction = scopes.jurisdiction
 AND active.document_class = scopes.document_class
 AND active.release_name = scopes.release_name;

CREATE VIEW reference.current_provisions AS
SELECT p.*
FROM corpus.provisions p
WHERE EXISTS (
  SELECT 1
  FROM reference.current_release_scopes s
  WHERE s.jurisdiction = p.jurisdiction
    AND s.document_class = COALESCE(NULLIF(p.doc_type, ''), 'unknown')
    AND s.version = p.version
);

CREATE VIEW reference.legacy_provisions AS
SELECT p.*
FROM corpus.provisions p
WHERE NOT EXISTS (
  SELECT 1
  FROM reference.current_release_scopes s
  WHERE s.jurisdiction = p.jurisdiction
    AND s.document_class = COALESCE(NULLIF(p.doc_type, ''), 'unknown')
    AND s.version = p.version
);

CREATE VIEW reference.current_navigation_nodes AS
SELECT n.*
FROM corpus.navigation_nodes n
WHERE EXISTS (
  SELECT 1
  FROM reference.current_release_scopes s
  WHERE s.jurisdiction = n.jurisdiction
    AND s.document_class = COALESCE(NULLIF(n.doc_type, ''), 'unknown')
    AND s.version = n.version
);

CREATE VIEW reference.policy_navigation_nodes AS
SELECT n.*
FROM corpus.navigation_nodes n
WHERE EXISTS (
  SELECT 1
  FROM reference.current_release_scopes s
  WHERE s.jurisdiction = n.jurisdiction
    AND s.document_class = COALESCE(NULLIF(n.doc_type, ''), 'unknown')
    AND s.version = n.version
);

CREATE VIEW reference.current_provision_counts AS
SELECT
  jurisdiction,
  COALESCE(NULLIF(doc_type, ''), 'unknown') AS document_class,
  COUNT(*)::bigint AS provision_count,
  COUNT(*) FILTER (WHERE body IS NOT NULL AND BTRIM(body) <> '')::bigint AS body_count,
  COUNT(*) FILTER (WHERE parent_id IS NULL)::bigint AS top_level_count,
  COUNT(*) FILTER (WHERE has_rulespec IS TRUE)::bigint AS rulespec_count
FROM reference.current_provisions
WHERE jurisdiction IS NOT NULL
GROUP BY jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown');

CREATE VIEW reference.root_document_counts AS
SELECT
  jurisdiction,
  COALESCE(NULLIF(doc_type, ''), 'unknown') AS doc_type,
  COUNT(*)::bigint AS document_count
FROM reference.current_navigation_nodes
WHERE parent_path IS NULL
  AND jurisdiction IS NOT NULL
GROUP BY jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown');
"""

RESET_TABLES = (
    "scope_activation_history",
    "active_scope_pointer",
    "active_release_pointer",
    "release_activation_upload_chunks",
    "release_scopes",
    "release_objects",
    "provision_anchors",
    "provision_references",
    "provisions",
    "navigation_nodes",
    "layered_shadowed_rows",
    "layered_navigation_overrides",
)


def _create_database(*, layered: bool) -> Iterator[str]:
    assert DATABASE_URL is not None
    database_name = f"axiom_layered_serving_{uuid.uuid4().hex}"
    created_roles: list[str] = []
    with closing(psycopg2.connect(DATABASE_URL)) as admin:
        admin.autocommit = True
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)",
                (list(REQUIRED_ROLES),),
            )
            existing_roles = {str(row[0]) for row in cursor.fetchall()}
            for role in REQUIRED_ROLES:
                if role not in existing_roles:
                    cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
                    created_roles.append(role)
            cursor.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(database_name)
                )
            )
        dsn = psycopg2.extensions.make_dsn(DATABASE_URL, dbname=database_name)
        try:
            with closing(psycopg2.connect(dsn)) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(PRODUCTION_SHAPED_SCHEMA)
                    for migration in (
                        MIGRATION,
                        SCOPE_MIGRATION,
                        PROFILED_RELEASE_MIGRATION,
                        COMPACT_RELEASE_OBJECTS_MIGRATION,
                        CHUNKED_ACTIVATION_MIGRATION,
                        STAGED_RELEASE_OBJECT_MIGRATION,
                        STAGED_RELEASE_OBJECT_V4_MIGRATION,
                    ):
                        cursor.execute(migration.read_text(encoding="utf-8"))
                    cursor.execute(_production_serving_sql())
                    cursor.execute(REFERENCE_SQL)
                    if layered:
                        cursor.execute(LAYERED_SERVING_MIGRATION.read_text(encoding="utf-8"))
                connection.commit()
            yield dsn
        finally:
            with admin.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (database_name,),
                )
                cursor.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name))
                )
                for role in reversed(created_roles):
                    cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))


@pytest.fixture(scope="module")
def layered_dsn() -> Iterator[str]:
    yield from _create_database(layered=True)


@pytest.fixture
def db(layered_dsn: str) -> Iterator[Any]:
    _reset(layered_dsn)
    with closing(psycopg2.connect(layered_dsn)) as connection:
        yield connection
    _reset(layered_dsn)


def _reset(dsn: str) -> None:
    with closing(psycopg2.connect(dsn)) as connection, connection.cursor() as cursor:
        # Signed membership and released rows refuse TRUNCATE, so a test
        # database is emptied with triggers off (a superuser setting).
        cursor.execute("SET session_replication_role = replica")
        cursor.execute(
            sql.SQL("TRUNCATE TABLE {}").format(
                sql.SQL(", ").join(sql.Identifier("corpus", table) for table in RESET_TABLES)
            )
        )
        cursor.execute("RESET session_replication_role")
        cursor.execute("REFRESH MATERIALIZED VIEW corpus.current_provision_counts")
        connection.commit()


# ---------------------------------------------------------------------------
# Staged scopes and signed release objects.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    """One provision of a synthetic scope."""

    path: str
    parent: str | None = None
    heading: str | None = None
    ordinal: int | None = None
    encoded: bool = False


@dataclass(frozen=True)
class Scope:
    jurisdiction: str
    document_class: str
    version: str
    nodes: tuple[Node, ...]
    layer: str = LAYER_PRIMARY
    expression_date: str = "2026-09-01"

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.jurisdiction, self.document_class, self.version)

    @property
    def pair(self) -> tuple[str, str]:
        return (self.jurisdiction, self.document_class)

    def records(self) -> tuple[ProvisionRecord, ...]:
        return tuple(
            ProvisionRecord(
                jurisdiction=self.jurisdiction,
                document_class=self.document_class,
                citation_path=node.path,
                parent_citation_path=node.parent,
                version=self.version,
                heading=node.heading,
                body=f"Text of {node.path} in {self.version}.",
                ordinal=node.ordinal,
                has_rulespec=node.encoded,
                kind="section",
                source_path=f"sources/{self.jurisdiction}/{self.document_class}/"
                f"{self.version}/source.xml",
                source_as_of="2026-09-01",
                expression_date=self.expression_date,
            )
            for node in self.nodes
        )


def _insert_rows(cursor: Any, table: str, rows: Sequence[Mapping[str, object]]) -> None:
    for row in rows:
        columns = tuple(row)
        cursor.execute(
            sql.SQL("INSERT INTO corpus.{} ({}) VALUES ({})").format(
                sql.Identifier(table),
                sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                sql.SQL(", ").join(sql.Placeholder() for _column in columns),
            ),
            tuple(Json(value) if isinstance(value, dict) else value for value in row.values()),
        )


def _stage(connection: Any, *scopes: Scope) -> None:
    """Load provisions and navigation exactly as the publisher stages a scope.

    A scope already staged is reused as it is, as publication reuses one.
    """
    with connection.cursor() as cursor:
        for scope in scopes:
            cursor.execute(
                "SELECT 1 FROM corpus.provisions "
                "WHERE jurisdiction = %s AND doc_type = %s AND version = %s LIMIT 1",
                scope.key,
            )
            if cursor.fetchone() is not None:
                continue
            records = scope.records()
            _insert_rows(cursor, "provisions", list(iter_supabase_rows(records)))
            _insert_rows(
                cursor,
                "navigation_nodes",
                [node.to_supabase_row() for node in build_navigation_nodes(records)],
            )
    connection.commit()


def _evidence(connection: Any, scope: Scope) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT provision_count, navigation_count,
                   provision_projection_sha256, navigation_projection_sha256
            FROM corpus.get_staged_release_scope_evidence(%s::jsonb)
            """,
            (
                Json(
                    [
                        {
                            "jurisdiction": scope.jurisdiction,
                            "document_class": scope.document_class,
                            "version": scope.version,
                        }
                    ]
                ),
            ),
        )
        row = cursor.fetchone()
    connection.commit()
    assert row is not None
    return {
        "provision_rows": int(row[0]),
        "navigation_rows": int(row[1]),
        "provision_projection_sha256": row[2],
        "navigation_projection_sha256": row[3],
    }


def _artifact(artifact_class: str, path: str, *, rows: int | None = None) -> dict[str, Any]:
    raw = f"test artifact: {path}\n".encode()
    digest = hashlib.sha256(raw).hexdigest()
    entry: dict[str, Any] = {
        "artifact_class": artifact_class,
        "path": path,
        "sha256": digest,
        "bytes": len(raw),
        "r2_bucket": "axiom-corpus",
        "r2_key": content_addressed_r2_key(digest),
    }
    if rows is not None:
        entry["rows"] = rows
    return entry


def _release_object(connection: Any, name: str, scopes: Sequence[Scope]) -> dict[str, Any]:
    """Sign a release over staged scopes with the publisher's own builder."""
    entries: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    for scope in scopes:
        evidence = _evidence(connection, scope)
        entry: dict[str, Any] = {
            "jurisdiction": scope.jurisdiction,
            "document_class": scope.document_class,
            "version": scope.version,
            **evidence,
        }
        if scope.layer == LAYER_BASE:
            entry["layer"] = LAYER_BASE
        entries.append(entry)
        stem = "/".join(scope.key)
        artifacts.extend(
            (
                _artifact("coverage", f"data/corpus/coverage/{stem}.json"),
                _artifact("inventory", f"data/corpus/inventory/{stem}.json"),
                _artifact(
                    "provisions",
                    f"data/corpus/provisions/{stem}.jsonl",
                    rows=evidence["provision_rows"],
                ),
                _artifact("sources", f"data/corpus/sources/{stem}/source.xml"),
            )
        )
    artifacts.sort(key=lambda entry: str(entry["path"]))
    manifest = ReleaseManifest(
        name=name,
        quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
        scopes=tuple(ReleaseScope(*scope.key, layer=scope.layer) for scope in scopes),
    )
    content = {
        "release": name,
        "created_at": "2026-10-01T00:00:00Z",
        "selector_sha256": selector_sha256(manifest),
        "corpus_base": "data/corpus",
        "git": {"commit": "a" * 40, "committed_at": "2026-10-01T00:00:00Z"},
        "r2": {"bucket": "axiom-corpus", "addressing": "sha256"},
        "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
        "scopes": entries,
        "artifacts": artifacts,
        "validation": {
            "passed": True,
            "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
            "deep_validation": {
                "error_count": 0,
                "warning_count": 0,
                "scope_count": len(entries),
            },
            "r2_readback": {
                "bucket": "axiom-corpus",
                "artifact_count": len(artifacts),
                "artifact_bytes": sum(int(entry["bytes"]) for entry in artifacts),
                "verified_keys": [entry["r2_key"] for entry in artifacts],
            },
            "supabase_projection_evidence": [
                {
                    "jurisdiction": entry["jurisdiction"],
                    "document_class": entry["document_class"],
                    "version": entry["version"],
                    "expected": entry["provision_rows"],
                    "actual": entry["provision_rows"],
                    "expected_navigation": entry["navigation_rows"],
                    "actual_navigation": entry["navigation_rows"],
                    "expected_provision_projection_sha256": entry["provision_projection_sha256"],
                    "actual_provision_projection_sha256": entry["provision_projection_sha256"],
                    "expected_navigation_projection_sha256": entry["navigation_projection_sha256"],
                    "actual_navigation_projection_sha256": entry["navigation_projection_sha256"],
                }
                for entry in sorted(
                    entries,
                    key=lambda e: (e["jurisdiction"], e["document_class"], e["version"]),
                )
            ],
        },
    }
    signed = sign_release_object(build_unsigned_release_object(content), private_key=PRIVATE_KEY)
    verify_release_object(signed, public_key=TEST_PUBLIC_KEY)
    return signed


def _reseal(release_object: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, Any]:
    """Re-sign altered content so the database, not the signature, judges it."""
    unsigned = {
        "schema_version": release_object["schema_version"],
        "release": release_object["release"],
        "content_sha256": hashlib.sha256(_canonical(content)).hexdigest(),
        "content": dict(content),
    }
    signature = TEST_SIGNING_KEY.sign(_canonical(unsigned))
    return {
        **unsigned,
        "signature": {
            "algorithm": "ed25519",
            "key_id": "axiom-corpus-release-v2",
            "value": base64.b64encode(signature).decode(),
        },
    }


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()


def _activate(connection: Any, release_object: Mapping[str, Any]) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT corpus.activate_corpus_release(%s::jsonb)", (Json(dict(release_object)),)
        )
        row = cursor.fetchone()
    connection.commit()
    assert row is not None
    return row[0]


def _publish(connection: Any, name: str, *scopes: Scope, stage: bool = True) -> dict[str, Any]:
    if stage:
        _stage(connection, *scopes)
    release_object = _release_object(connection, name, scopes)
    _activate(connection, release_object)
    return release_object


def _rows(connection: Any, query: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    connection.commit()
    return rows


@contextmanager
def _as_role(connection: Any, role: str) -> Iterator[Any]:
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        try:
            yield cursor
        finally:
            connection.rollback()


def _ids(connection: Any, relation: str, *, role: str | None = None) -> set[str]:
    query = f"SELECT id::text FROM {relation}"
    if role is None:
        return {row[0] for row in _rows(connection, query)}
    with _as_role(connection, role) as cursor:
        cursor.execute(query)
        return {row[0] for row in cursor.fetchall()}


def _navigation(connection: Any, relation: str = "corpus.current_navigation_nodes") -> dict:
    columns = ", ".join(NAVIGATION_COLUMNS)
    return {
        row[0]: dict(zip(NAVIGATION_COLUMNS, row, strict=True))
        for row in _rows(connection, f"SELECT {columns} FROM {relation}")
    }


def _provision_id(path: str, version: str) -> str:
    from axiom_corpus.corpus.supabase import deterministic_provision_id

    return deterministic_provision_id(path, version)


def _snapshot(connection: Any) -> dict[str, Any]:
    """Everything an activation may change, for atomicity checks."""
    return {
        "objects": _rows(
            connection, "SELECT release_name, content_sha256 FROM corpus.release_objects ORDER BY 1"
        ),
        "scopes": _rows(
            connection,
            "SELECT release_name, jurisdiction, document_class, version, layer "
            "FROM corpus.release_scopes ORDER BY 1, 2, 3, 4",
        ),
        "pointers": _rows(
            connection,
            "SELECT jurisdiction, document_class, release_name, content_sha256, activated_at "
            "FROM corpus.active_scope_pointer ORDER BY 1, 2",
        ),
        "history": _rows(connection, "SELECT COUNT(*) FROM corpus.scope_activation_history"),
        "shadowed": _rows(
            connection, "SELECT * FROM corpus.layered_shadowed_rows ORDER BY 1, 2, 3"
        ),
        "overrides": _rows(
            connection, "SELECT * FROM corpus.layered_navigation_overrides ORDER BY id"
        ),
        "counts": _rows(
            connection,
            "SELECT jurisdiction, document_class, provision_count "
            "FROM corpus.current_provision_counts ORDER BY 1, 2",
        ),
    }


def _stored(connection: Any) -> list[tuple[Any, ...]]:
    return _rows(
        connection,
        "SELECT (SELECT COUNT(*) FROM corpus.provisions), "
        "(SELECT COUNT(*) FROM corpus.navigation_nodes)",
    )


def _attempt(
    connection: Any, statement: str, params: Sequence[Any] | Mapping[str, Any] = ()
) -> Exception | None:
    """Run one owner-level write and commit it; return the error it raised, if any."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
        connection.commit()
    except psycopg2.Error as exc:
        connection.rollback()
        return exc
    return None


@contextmanager
def _triggers_off(connection: Any) -> Iterator[Any]:
    """Write as an owner could only by turning the guards off (a superuser setting)."""
    with connection.cursor() as cursor:
        cursor.execute("SET session_replication_role = replica")
        try:
            yield cursor
        finally:
            cursor.execute("RESET session_replication_role")
    connection.commit()


def _derived_rows(cursor: Any) -> dict[str, list[tuple[Any, ...]]]:
    cursor.execute("SELECT * FROM corpus.layered_shadowed_rows ORDER BY 1, 2, 3")
    shadowed = cursor.fetchall()
    cursor.execute("SELECT * FROM corpus.layered_navigation_overrides ORDER BY id")
    return {"shadowed": shadowed, "overrides": cursor.fetchall()}


def _assert_serving_is_consistent(connection: Any) -> None:
    """What is served is what a derivation from scratch would serve.

    The derived tables equal a fresh derivation of every served pair (made in a
    transaction that is rolled back), each pair serves a citation path at most
    once in each view, and navigation serves exactly the served provisions.
    """
    with connection.cursor() as cursor:
        stored = _derived_rows(cursor)
        cursor.execute("SELECT corpus.rederive_layered_serving()")
        fresh = _derived_rows(cursor)
    connection.rollback()
    assert stored == fresh
    provisions = _rows(
        connection,
        "SELECT jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown'), citation_path, id::text "
        "FROM corpus.current_provisions",
    )
    navigation = _rows(
        connection,
        "SELECT jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown'), path, provision_id::text "
        "FROM corpus.current_navigation_nodes",
    )
    assert len({row[:3] for row in provisions}) == len(provisions)
    assert len({row[:3] for row in navigation}) == len(navigation)
    assert {row[3] for row in navigation if row[3]} == {row[3] for row in provisions}


# ---------------------------------------------------------------------------
# Python reference model of layered serving.
# ---------------------------------------------------------------------------


def _staged_navigation(scope: Scope) -> list[dict[str, Any]]:
    return [node.to_supabase_row() for node in build_navigation_nodes(scope.records())]


def _reference_served_provisions(scopes: Sequence[Scope]) -> set[str]:
    """Ids served for one release: primary rows, and base rows no primary path shadows."""
    primary_paths: dict[tuple[str, str], set[str]] = {}
    for scope in scopes:
        if scope.layer == LAYER_PRIMARY:
            primary_paths.setdefault(scope.pair, set()).update(n.path for n in scope.nodes)
    served: set[str] = set()
    for scope in scopes:
        for node in scope.nodes:
            if scope.layer == LAYER_BASE and node.path in primary_paths.get(scope.pair, set()):
                continue
            served.add(_provision_id(node.path, scope.version))
    return served


def _reference_merged_tree(scopes: Sequence[Scope]) -> dict[str, dict[str, Any]]:
    """The merged navigation of one layered pair, by the rules of the migration.

    Uses navigation.py's own cycle breaking, depth, segment and sort-key
    helpers, so the SQL is checked against the builder it mirrors.
    """
    primary = [row for s in scopes if s.layer == LAYER_PRIMARY for row in _staged_navigation(s)]
    base = [row for s in scopes if s.layer == LAYER_BASE for row in _staged_navigation(s)]
    headed = {
        (scope.version, node.path)
        for scope in scopes
        for node in scope.nodes
        if node.heading and node.heading.strip()
    }
    primary_paths = {row["path"] for row in primary}
    base_by_path = {row["path"]: row for row in base}
    winners = [dict(row, layer=LAYER_PRIMARY) for row in primary] + [
        dict(row, layer=LAYER_BASE) for row in base if row["path"] not in primary_paths
    ]
    by_path = {row["path"]: row for row in winners}
    parents: dict[str, str | None] = {}
    for row in winners:
        parent = row["parent_path"]
        if row["layer"] == LAYER_PRIMARY and parent is None:
            twin = base_by_path.get(row["path"])
            if twin is not None:
                parent = twin["parent_path"]
            else:
                parts = row["path"].split("/")
                for size in range(len(parts) - 1, 0, -1):
                    candidate = "/".join(parts[:size])
                    if candidate in by_path:
                        parent = candidate
                        break
        parents[row["path"]] = parent
    _break_parent_cycles(parents)
    depths = _resolve_depths(parents)
    child_counts = Counter(parent for parent in parents.values() if parent is not None)
    encoded: Counter[str] = Counter()
    for path in sorted(parents, key=lambda p: -depths[p]):
        own = (1 if by_path[path]["has_rulespec"] else 0) + encoded[path]
        parent = parents[path]
        if parent is not None:
            encoded[parent] += own
    merged: dict[str, dict[str, Any]] = {}
    for row in winners:
        path = row["path"]
        parent = parents[path]
        segment = row["segment"]
        label = row["label"]
        sort_key = row["sort_key"]
        if parent != row["parent_path"]:
            new_segment = _segment(path, parent)
            if new_segment != segment:
                if label == segment and (row["version"], path) not in headed:
                    label = new_segment
                sort_key = sort_key.split("|", 1)[0] + "|" + _normalize_sort_segment(new_segment)
                segment = new_segment
        merged[row["id"]] = {
            **{column: row.get(column) for column in NAVIGATION_COLUMNS},
            "parent_path": parent,
            "segment": segment,
            "label": label,
            "sort_key": sort_key,
            "depth": depths[path],
            "has_children": child_counts[path] > 0,
            "child_count": child_counts[path],
            "encoded_descendant_count": encoded[path],
        }
    return merged


def _built_over_winners(scopes: Sequence[Scope]) -> dict[str, dict[str, Any]]:
    """build_navigation_nodes run over the records the pair serves."""
    primary_paths = {n.path for s in scopes if s.layer == LAYER_PRIMARY for n in s.nodes}
    winners = [
        record
        for scope in scopes
        for record in scope.records()
        if scope.layer == LAYER_PRIMARY or record.citation_path not in primary_paths
    ]
    return {node.id: node.to_supabase_row() for node in build_navigation_nodes(winners)}


def _tree(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, tuple[Any, ...]]:
    return {
        str(row["path"]): tuple(row[column] for column in ("id", *TREE_COLUMNS))
        for row in rows.values()
    }


def _pair_rows(rows: Mapping[str, Mapping[str, Any]], pair: tuple[str, str]) -> dict:
    return {
        key: row
        for key, row in rows.items()
        if (row["jurisdiction"], row["doc_type"] or "unknown") == pair
    }


# ---------------------------------------------------------------------------
# Shared fixtures of one layered pair.
# ---------------------------------------------------------------------------

BASE = Scope(
    "fx",
    "statute",
    "2026-04-29-base",
    (
        Node("fx/statute/1", heading="Title 1", ordinal=1),
        Node("fx/statute/1/1", "fx/statute/1", "Section 1-1", 1),
        Node("fx/statute/1/2", "fx/statute/1", "Section 1-2", 2),
        Node("fx/statute/1/3", "fx/statute/1", "Section 1-3", 3),
        Node("fx/statute/1/3/a", "fx/statute/1/3", "Section 1-3(a)", 1),
        Node("fx/statute/2", heading="Title 2", ordinal=2),
        Node("fx/statute/2/1", "fx/statute/2", "Section 2-1", 1),
        Node("fx/statute/2/2", "fx/statute/2", "Section 2-2", 2),
        Node("fx/statute/3", heading="Title 3", ordinal=3),
        Node("fx/statute/3/1", "fx/statute/3", "Section 3-1", 1),
    ),
    layer=LAYER_BASE,
    expression_date="2026-04-29",
)
# A primary scope with its own title: re-encodes title 1 and section 1-1, and
# adds a section the base does not carry.
PRIMARY_TITLE = Scope(
    "fx",
    "statute",
    "2026-09-20-title-1",
    (
        Node("fx/statute/1", heading="Title 1 (encoded)", ordinal=1),
        Node("fx/statute/1/1", "fx/statute/1", "Section 1-1 (encoded)", 1, encoded=True),
        Node("fx/statute/1/4", "fx/statute/1", "Section 1-4 (new)", 4, encoded=True),
    ),
)
# A primary scope without its title: section 2-2 and its new subsection are
# roots of their scope, and belong under base title 2 once merged.
PRIMARY_SECTIONS = Scope(
    "fx",
    "statute",
    "2026-09-21-title-2-sections",
    (
        Node("fx/statute/2/2", "fx/statute/2", "Section 2-2 (encoded)", 2, encoded=True),
        Node("fx/statute/2/2/b", "fx/statute/2/2", "Section 2-2(b) (new)", 2, encoded=True),
        Node("fx/statute/2/5/x", None, None, None, encoded=True),
    ),
)
OTHER_PAIR = Scope(
    "fx",
    "regulation",
    "2026-09-01-regs",
    (
        Node("fx/regulation/1", heading="Chapter 1", ordinal=1),
        Node("fx/regulation/1/1", "fx/regulation/1", "Part 1", 1),
    ),
)
LAYERED_RELEASE = "fx-rulespec-2026-09-22-base"
LAYERED_SCOPES = (BASE, PRIMARY_TITLE, PRIMARY_SECTIONS, OTHER_PAIR)


def _publish_layered(connection: Any) -> dict[str, Any]:
    return _publish(connection, LAYERED_RELEASE, *LAYERED_SCOPES)


# ---------------------------------------------------------------------------
# The migration itself.
# ---------------------------------------------------------------------------


def test_migration_keeps_every_serving_column_and_appends_the_layer(db: Any) -> None:
    columns = {
        relation: [
            row[0]
            for row in _rows(
                db,
                "SELECT attname FROM pg_attribute WHERE attrelid = %s::regclass "
                "AND attnum > 0 AND NOT attisdropped ORDER BY attnum",
                (relation,),
            )
        ]
        for relation in (
            "corpus.current_release_scopes",
            "corpus.current_provisions",
            "corpus.legacy_provisions",
            "corpus.current_navigation_nodes",
            "corpus.provisions",
            "corpus.navigation_nodes",
        )
    }
    assert columns["corpus.current_release_scopes"] == [
        "release_name",
        "jurisdiction",
        "document_class",
        "version",
        "synced_at",
        "layer",
    ]
    assert columns["corpus.current_provisions"] == columns["corpus.provisions"]
    assert columns["corpus.legacy_provisions"] == columns["corpus.provisions"]
    assert columns["corpus.current_navigation_nodes"] == list(NAVIGATION_COLUMNS)
    assert columns["corpus.navigation_nodes"] == list(NAVIGATION_COLUMNS)


def test_migration_is_rerunnable_and_rederivation_reproduces_the_state(db: Any) -> None:
    _publish_layered(db)
    before = _snapshot(db)
    with db.cursor() as cursor:
        cursor.execute(LAYERED_SERVING_MIGRATION.read_text(encoding="utf-8"))
    db.commit()
    assert _snapshot(db) == before
    _rows(db, "SELECT corpus.rederive_layered_serving()")
    assert _snapshot(db) == before


def test_historical_memberships_become_primary(db: Any) -> None:
    _publish(db, "fx-rulespec-2026-09-01", PRIMARY_TITLE)
    assert _rows(db, "SELECT DISTINCT layer FROM corpus.release_scopes") == [("primary",)]
    # The membership guard rejects the write first; with triggers off (as an
    # owner could), the check constraint still holds the layer to its values.
    assert isinstance(
        _attempt(db, "UPDATE corpus.release_scopes SET layer = 'secondary'"),
        errors.RaiseException,
    )
    with pytest.raises(errors.CheckViolation):
        with db.cursor() as cursor:
            cursor.execute("SET session_replication_role = replica")
            cursor.execute("UPDATE corpus.release_scopes SET layer = 'secondary'")
    db.rollback()


def test_derived_state_and_refresh_functions_are_private(db: Any) -> None:
    _publish_layered(db)
    for table in ("layered_shadowed_rows", "layered_navigation_overrides"):
        for role in ("anon", "authenticated"):
            with _as_role(db, role) as cursor, pytest.raises(errors.InsufficientPrivilege):
                cursor.execute(f"SELECT 1 FROM corpus.{table}")
    for function in (
        "corpus.refresh_layered_serving('fx', 'statute')",
        "corpus.activate_corpus_release('{}'::jsonb)",
    ):
        for role in ("anon", "authenticated", "service_role"):
            with _as_role(db, role) as cursor, pytest.raises(errors.InsufficientPrivilege):
                cursor.execute(f"SELECT {function}")


# ---------------------------------------------------------------------------
# With no base scope active, every serving object is exactly the previous one.
# ---------------------------------------------------------------------------


def _assert_matches_reference(connection: Any) -> None:
    pairs = (
        ("corpus.current_provisions", "reference.current_provisions"),
        ("corpus.legacy_provisions", "reference.legacy_provisions"),
    )
    for migrated, reference in pairs:
        assert _rows(connection, f"SELECT * FROM {migrated} ORDER BY id") == _rows(
            connection, f"SELECT * FROM {reference} ORDER BY id"
        ), migrated
    navigation_columns = ", ".join(NAVIGATION_COLUMNS)
    assert _rows(
        connection,
        f"SELECT {navigation_columns} FROM corpus.current_navigation_nodes ORDER BY id",
    ) == _rows(
        connection,
        f"SELECT {navigation_columns} FROM reference.current_navigation_nodes ORDER BY id",
    )
    assert _rows(
        connection,
        "SELECT release_name, jurisdiction, document_class, version, synced_at "
        "FROM corpus.current_release_scopes ORDER BY 1, 2, 3, 4",
    ) == _rows(connection, "SELECT * FROM reference.current_release_scopes ORDER BY 1, 2, 3, 4")
    assert _rows(connection, "SELECT * FROM corpus.get_root_document_counts()") == _rows(
        connection, "SELECT * FROM reference.root_document_counts ORDER BY 1, 2"
    )
    assert _rows(
        connection,
        "SELECT jurisdiction, document_class, provision_count, body_count, top_level_count, "
        "rulespec_count FROM corpus.current_provision_counts ORDER BY 1, 2",
    ) == _rows(connection, "SELECT * FROM reference.current_provision_counts ORDER BY 1, 2")
    for role in ("anon", "authenticated"):
        assert _ids(connection, "corpus.navigation_nodes", role=role) == _ids(
            connection, "reference.policy_navigation_nodes"
        ), role
    assert _rows(connection, "SELECT COUNT(*) FROM corpus.layered_shadowed_rows") == [(0,)]
    assert _rows(connection, "SELECT COUNT(*) FROM corpus.layered_navigation_overrides") == [(0,)]


_SEGMENTS = st.sampled_from(["1", "2", "3", "10", "a", "b"])


@st.composite
def _primary_world(draw: st.DrawFn) -> list[tuple[str, list[Scope]]]:
    """Releases of primary scopes only, over two jurisdictions and classes.

    Scope versions recur across releases (immutable reuse), and the same
    citation path recurs across versions, as superseded history does.
    """
    versions: dict[tuple[str, str, str], Scope] = {}
    releases: list[tuple[str, list[Scope]]] = []
    for index in range(draw(st.integers(1, 4))):
        scopes: list[Scope] = []
        pairs = draw(
            st.lists(
                st.sampled_from([("fx", "statute"), ("fx", "regulation"), ("fy", "statute")]),
                min_size=1,
                max_size=3,
                unique=True,
            )
        )
        for jurisdiction, document_class in pairs:
            version = f"2026-09-0{draw(st.integers(1, 4))}-v"
            key = (jurisdiction, document_class, version)
            if key not in versions:
                titles = draw(st.lists(_SEGMENTS, min_size=1, max_size=3, unique=True))
                nodes: list[Node] = []
                for title in titles:
                    root = f"{jurisdiction}/{document_class}/{title}"
                    if draw(st.booleans()):
                        nodes.append(Node(root, heading=f"T{title}", ordinal=int(title, 36)))
                    for child in draw(st.lists(_SEGMENTS, max_size=3, unique=True)):
                        nodes.append(
                            Node(
                                f"{root}/{child}",
                                root,
                                draw(st.sampled_from([None, f"S{child}"])),
                                draw(st.sampled_from([None, 1, 2])),
                                draw(st.booleans()),
                            )
                        )
                if not nodes:
                    nodes.append(Node(f"{jurisdiction}/{document_class}/x"))
                versions[key] = Scope(jurisdiction, document_class, version, tuple(nodes))
            scopes.append(versions[key])
        releases.append((f"fx-world-{index}", scopes))
    return releases


@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(world=_primary_world())
def test_without_a_base_scope_every_view_is_the_previous_definition(
    layered_dsn: str, world: list[tuple[str, list[Scope]]]
) -> None:
    _reset(layered_dsn)
    with closing(psycopg2.connect(layered_dsn)) as connection:
        staged: set[tuple[str, str, str]] = set()
        for name, scopes in world:
            fresh = [scope for scope in scopes if scope.key not in staged]
            _stage(connection, *fresh)
            staged.update(scope.key for scope in fresh)
            release_object = _release_object(connection, name, scopes)
            assert release_object["schema_version"] == RELEASE_OBJECT_SCHEMA_V3
            _activate(connection, release_object)
            _assert_matches_reference(connection)


# ---------------------------------------------------------------------------
# Layered serving.
# ---------------------------------------------------------------------------


def test_layered_release_signs_v4_and_activates(db: Any) -> None:
    release_object = _publish_layered(db)
    assert release_object["schema_version"] == RELEASE_OBJECT_SCHEMA_V4
    assert [scope.get("layer") for scope in release_object["content"]["scopes"]] == [
        "base",
        None,
        None,
        None,
    ]
    assert _rows(
        db,
        "SELECT version, layer FROM corpus.current_release_scopes "
        "WHERE document_class = 'statute' ORDER BY version",
    ) == [
        ("2026-04-29-base", "base"),
        ("2026-09-20-title-1", "primary"),
        ("2026-09-21-title-2-sections", "primary"),
    ]


def test_each_citation_path_serves_the_primary_row_when_both_layers_carry_it(db: Any) -> None:
    _publish_layered(db)
    served = _rows(
        db,
        "SELECT citation_path, version FROM corpus.current_provisions "
        "WHERE jurisdiction = 'fx' AND doc_type = 'statute' ORDER BY citation_path",
    )
    paths = [path for path, _version in served]
    assert len(paths) == len(set(paths))
    assert dict(served) == {
        "fx/statute/1": "2026-09-20-title-1",
        "fx/statute/1/1": "2026-09-20-title-1",
        "fx/statute/1/2": "2026-04-29-base",
        "fx/statute/1/3": "2026-04-29-base",
        "fx/statute/1/3/a": "2026-04-29-base",
        "fx/statute/1/4": "2026-09-20-title-1",
        "fx/statute/2": "2026-04-29-base",
        "fx/statute/2/1": "2026-04-29-base",
        "fx/statute/2/2": "2026-09-21-title-2-sections",
        "fx/statute/2/2/b": "2026-09-21-title-2-sections",
        "fx/statute/2/5/x": "2026-09-21-title-2-sections",
        "fx/statute/3": "2026-04-29-base",
        "fx/statute/3/1": "2026-04-29-base",
    }
    assert _ids(db, "corpus.current_provisions") == _reference_served_provisions(LAYERED_SCOPES)
    # The other pair of the release is served whole, as before.
    assert _ids(db, "corpus.current_provisions WHERE doc_type = 'regulation'") == {
        _provision_id(node.path, OTHER_PAIR.version) for node in OTHER_PAIR.nodes
    }


def test_primary_wins_whatever_the_dates_and_scope_order(db: Any) -> None:
    newer_base = replace(BASE, version="2026-12-31-base", expression_date="2026-12-31")
    older_primary = replace(
        PRIMARY_TITLE, version="2026-01-01-title-1", expression_date="2026-01-01"
    )
    _publish(db, "fx-rulespec-2026-09-23", older_primary, newer_base)
    assert _rows(
        db,
        "SELECT version FROM corpus.current_provisions WHERE citation_path = 'fx/statute/1/1'",
    ) == [("2026-01-01-title-1",)]


def test_served_and_suppressed_rows_partition_the_staged_rows(db: Any) -> None:
    _publish_layered(db)
    current = _ids(db, "corpus.current_provisions")
    legacy = _ids(db, "corpus.legacy_provisions")
    staged = _ids(db, "corpus.provisions")
    assert current.isdisjoint(legacy)
    assert current | legacy == staged
    shadowed = {
        row[0] for row in _rows(db, "SELECT provision_id::text FROM corpus.layered_shadowed_rows")
    }
    assert shadowed == {
        _provision_id(path, BASE.version)
        for path in ("fx/statute/1", "fx/statute/1/1", "fx/statute/2/2")
    }
    assert shadowed <= legacy
    signed_rows = sum(len(scope.nodes) for scope in LAYERED_SCOPES)
    assert len(current) + len(shadowed) == signed_rows
    assert _rows(
        db,
        "SELECT jurisdiction, document_class, provision_count FROM corpus.current_provision_counts "
        "ORDER BY 1, 2",
    ) == [("fx", "regulation", 2), ("fx", "statute", 13)]


def test_merged_navigation_places_primary_nodes_in_the_base_tree(db: Any) -> None:
    _publish_layered(db)
    served = _navigation(db)
    tree = {
        row["path"]: (row["parent_path"], row["depth"], row["child_count"], row["version"])
        for row in served.values()
        if row["doc_type"] == "statute"
    }
    assert tree == {
        "fx/statute/1": (None, 0, 4, "2026-09-20-title-1"),
        "fx/statute/1/1": ("fx/statute/1", 1, 0, "2026-09-20-title-1"),
        "fx/statute/1/2": ("fx/statute/1", 1, 0, "2026-04-29-base"),
        "fx/statute/1/3": ("fx/statute/1", 1, 1, "2026-04-29-base"),
        "fx/statute/1/3/a": ("fx/statute/1/3", 2, 0, "2026-04-29-base"),
        "fx/statute/1/4": ("fx/statute/1", 1, 0, "2026-09-20-title-1"),
        "fx/statute/2": (None, 0, 3, "2026-04-29-base"),
        "fx/statute/2/1": ("fx/statute/2", 1, 0, "2026-04-29-base"),
        # A root of its own scope, placed where its base twin sits.
        "fx/statute/2/2": ("fx/statute/2", 1, 1, "2026-09-21-title-2-sections"),
        "fx/statute/2/2/b": ("fx/statute/2/2", 2, 0, "2026-09-21-title-2-sections"),
        # No base twin: under the nearest served ancestor path, skipping the
        # missing 2/5, with its segment, label and sort key recomputed.
        "fx/statute/2/5/x": ("fx/statute/2", 1, 0, "2026-09-21-title-2-sections"),
        "fx/statute/3": (None, 0, 1, "2026-04-29-base"),
        "fx/statute/3/1": ("fx/statute/3", 1, 0, "2026-04-29-base"),
    }
    skipped = next(row for row in served.values() if row["path"] == "fx/statute/2/5/x")
    assert skipped["segment"] == "5/x"
    assert skipped["label"] == "5/x"
    assert skipped["sort_key"] == "zzzzzzzz|000000000005/x"
    encoded = {
        row["path"]: row["encoded_descendant_count"]
        for row in served.values()
        if row["encoded_descendant_count"]
    }
    assert encoded == {"fx/statute/1": 2, "fx/statute/2": 3, "fx/statute/2/2": 1}
    statute = (BASE, PRIMARY_TITLE, PRIMARY_SECTIONS)
    assert _tree(_pair_rows(served, ("fx", "statute"))) == _tree(_reference_merged_tree(statute))
    assert _tree(_pair_rows(served, ("fx", "statute"))) == _tree(_built_over_winners(statute))
    assert _rows(
        db,
        "SELECT COUNT(*), COUNT(DISTINCT id), COUNT(DISTINCT path) "
        "FROM corpus.current_navigation_nodes WHERE doc_type = 'statute'",
    ) == [(13, 13, 13)]


def test_navigation_overrides_hold_only_rows_whose_tree_fields_changed(db: Any) -> None:
    _publish_layered(db)
    stored = _navigation(db, "corpus.navigation_nodes")
    overrides = _navigation(db, "corpus.layered_navigation_overrides")
    # Title 1 and title 2 (children and encoded counts), 2/2 and 2/5/x
    # (re-parented), 2/2/b (one level deeper).
    assert {row["path"] for row in overrides.values()} == {
        "fx/statute/1",
        "fx/statute/2",
        "fx/statute/2/2",
        "fx/statute/2/2/b",
        "fx/statute/2/5/x",
    }
    for node_id, row in overrides.items():
        assert any(row[column] != stored[node_id][column] for column in TREE_COLUMNS), row["path"]
        assert {
            column: row[column] for column in NAVIGATION_COLUMNS if column not in TREE_COLUMNS
        } == {
            column: stored[node_id][column]
            for column in NAVIGATION_COLUMNS
            if column not in TREE_COLUMNS
        }


def test_direct_navigation_reads_hide_shadowed_base_rows(db: Any) -> None:
    _publish_layered(db)
    served_ids = set(_navigation(db))
    shadowed = {
        row[0] for row in _rows(db, "SELECT navigation_id FROM corpus.layered_shadowed_rows")
    }
    for role in ("anon", "authenticated"):
        visible = _ids(db, "corpus.navigation_nodes", role=role)
        assert visible == served_ids, role
        assert visible.isdisjoint(shadowed)
        with _as_role(db, role) as cursor:
            cursor.execute(
                "SELECT version FROM corpus.navigation_nodes WHERE path = 'fx/statute/1/1'"
            )
            assert cursor.fetchall() == [("2026-09-20-title-1",)]
    # Base rows nothing shadows stay visible, with their stored tree fields.
    with _as_role(db, "anon") as cursor:
        cursor.execute(
            "SELECT parent_path FROM corpus.navigation_nodes WHERE path = 'fx/statute/2/5/x'"
        )
        assert cursor.fetchall() == [(None,)]


def test_root_counts_count_the_roots_the_view_serves(db: Any) -> None:
    _publish_layered(db)
    expected = _rows(
        db,
        "SELECT jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown'), COUNT(*) "
        "FROM corpus.current_navigation_nodes WHERE parent_path IS NULL "
        "GROUP BY 1, 2 ORDER BY 1, 2",
    )
    assert expected == [("fx", "regulation", 1), ("fx", "statute", 3)]
    with _as_role(db, "anon") as cursor:
        cursor.execute("SELECT * FROM corpus.get_root_document_counts()")
        assert cursor.fetchall() == expected


def _root_count(scope: Scope) -> int:
    return sum(1 for row in _staged_navigation(scope) if row["parent_path"] is None)


def test_root_counts_are_served_roots_not_every_stored_root(db: Any) -> None:
    """This repository's 20260910120000 counts every stored root. The intended
    count (#666, this migration) leaves out roots of superseded and of never
    released scopes, so the two differ wherever such roots are stored."""
    with db.cursor() as cursor:
        cursor.execute(
            _migration_slice(
                "20260910120000_root_document_counts.sql",
                "CREATE OR REPLACE FUNCTION corpus.get_root_document_counts()",
                "GRANT EXECUTE",
            ).replace(
                "corpus.get_root_document_counts()", "reference.repository_root_document_counts()"
            )
        )
    db.commit()

    def counts() -> tuple[list[tuple[Any, ...]], ...]:
        return (
            _rows(db, "SELECT * FROM corpus.get_root_document_counts()"),
            _rows(db, "SELECT * FROM reference.root_document_counts ORDER BY 1, 2"),
            _rows(db, "SELECT * FROM reference.repository_root_document_counts()"),
        )

    _publish(db, "fx-rulespec-2026-09-01", PRIMARY_TITLE, OTHER_PAIR)
    served, pr_666, repository = counts()
    assert served == pr_666 == repository
    successor = replace(PRIMARY_TITLE, version="2026-09-25-title-1")
    _publish(db, "fx-rulespec-2026-09-25", successor, OTHER_PAIR)
    _stage(db, STRAY)
    served, pr_666, repository = counts()
    assert (
        served
        == pr_666
        == [
            ("fx", "regulation", _root_count(OTHER_PAIR)),
            ("fx", "statute", _root_count(successor)),
        ]
    )
    # The repository's definition adds the superseded and the unreleased roots.
    assert repository == [
        ("fx", "regulation", _root_count(OTHER_PAIR)),
        ("fx", "statute", sum(map(_root_count, (successor, PRIMARY_TITLE, STRAY)))),
    ]
    assert repository != served


def test_same_layer_duplicate_in_a_layered_pair_is_rejected_atomically(db: Any) -> None:
    _publish(db, "fx-rulespec-2026-09-01", OTHER_PAIR)
    before = _snapshot(db)
    duplicate = replace(
        PRIMARY_TITLE,
        version="2026-09-22-duplicate",
        nodes=(Node("fx/statute/1/4", "fx/statute/1", "Again", 4),),
    )
    _stage(db, BASE, PRIMARY_TITLE, duplicate)
    release_object = _release_object(db, "fx-rulespec-2026-09-24", (BASE, PRIMARY_TITLE, duplicate))
    with pytest.raises(errors.RaiseException, match="ambiguous primary citation ownership"):
        _activate(db, release_object)
    db.rollback()
    assert _snapshot(db) == before


def test_failed_evidence_leaves_every_pointer_scope_and_derived_row_unchanged(db: Any) -> None:
    _publish_layered(db)
    before = _snapshot(db)
    successor = replace(PRIMARY_TITLE, version="2026-09-25-title-1")
    _stage(db, successor)
    release_object = _release_object(
        db, "fx-rulespec-2026-09-25", (BASE, successor, PRIMARY_SECTIONS)
    )
    with db.cursor() as cursor:
        cursor.execute(
            "DELETE FROM corpus.provisions WHERE version = %s AND citation_path = %s",
            (successor.version, "fx/statute/1/4"),
        )
    db.commit()
    with pytest.raises(errors.RaiseException, match="staged row-count mismatch"):
        _activate(db, release_object)
    db.rollback()
    assert _snapshot(db) == before


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda scopes: [{**s, "layer": "primary"} if "layer" in s else s for s in scopes],
            "unsupported layer",
        ),
        (
            lambda scopes: [{k: v for k, v in s.items() if k != "layer"} for s in scopes],
            "reserved for releases with a base scope",
        ),
    ],
)
def test_v4_layer_rules_are_enforced_by_activation(db: Any, mutate: Any, message: str) -> None:
    _stage(db, BASE, PRIMARY_TITLE)
    release_object = _release_object(db, "fx-rulespec-2026-09-26", (BASE, PRIMARY_TITLE))
    content = dict(release_object["content"])
    content["scopes"] = mutate(content["scopes"])
    with pytest.raises(errors.RaiseException, match=message):
        _activate(db, _reseal(release_object, content))
    db.rollback()
    assert _rows(db, "SELECT COUNT(*) FROM corpus.release_objects") == [(0,)]


def test_layers_are_rejected_outside_v4(db: Any) -> None:
    _stage(db, BASE, PRIMARY_TITLE)
    release_object = _release_object(db, "fx-rulespec-2026-09-27", (BASE, PRIMARY_TITLE))
    resealed = _reseal(release_object, release_object["content"])
    resealed["schema_version"] = RELEASE_OBJECT_SCHEMA_V3
    resealed = _reseal(resealed, resealed["content"])
    with pytest.raises(errors.RaiseException, match="only release-object/v4 may sign scope layers"):
        _activate(db, resealed)
    db.rollback()


def test_two_base_scopes_for_one_pair_are_rejected(db: Any) -> None:
    second_base = replace(BASE, version="2026-05-01-base")
    _stage(db, BASE, second_base, PRIMARY_TITLE)
    release_object = _release_object(db, "fx-rulespec-2026-09-28", (BASE, PRIMARY_TITLE))
    content = dict(release_object["content"])
    extra = dict(content["scopes"][0])
    extra.update(_evidence(db, second_base), version=second_base.version)
    content["scopes"] = [*content["scopes"], extra]
    with pytest.raises(errors.RaiseException, match="more than one base scope"):
        _activate(db, _reseal(release_object, content))
    db.rollback()


def test_successor_keeps_the_base_and_unrelated_pairs(db: Any) -> None:
    _publish(
        db,
        "fy-rulespec-2026-09-01",
        replace(
            OTHER_PAIR,
            jurisdiction="fy",
            nodes=(Node("fy/regulation/1", heading="Chapter 1", ordinal=1),),
        ),
    )
    _publish_layered(db)
    unrelated = _rows(db, "SELECT * FROM corpus.active_scope_pointer WHERE jurisdiction = 'fy'")
    first = _snapshot(db)
    # The successor re-encodes title 1 differently and drops the sections scope.
    successor = replace(
        PRIMARY_TITLE,
        version="2026-09-29-title-1",
        nodes=(Node("fx/statute/1/2", "fx/statute/1", "Section 1-2 (encoded)", 2, encoded=True),),
    )
    _stage(db, successor)
    _activate(db, _release_object(db, "fx-rulespec-2026-09-29-base", (BASE, successor)))
    served = dict(
        _rows(
            db,
            "SELECT citation_path, version FROM corpus.current_provisions "
            "WHERE doc_type = 'statute'",
        )
    )
    assert served["fx/statute/1/1"] == BASE.version
    assert served["fx/statute/1/2"] == successor.version
    assert served["fx/statute/2/2"] == BASE.version
    assert "fx/statute/2/5/x" not in served
    assert (
        _rows(db, "SELECT * FROM corpus.active_scope_pointer WHERE jurisdiction = 'fy'")
        == unrelated
    )
    assert _tree(_pair_rows(_navigation(db), ("fx", "statute"))) == _tree(
        _reference_merged_tree((BASE, successor))
    )
    # Rolling back to the first release restores its exact derived state.
    _activate(db, _release_object(db, LAYERED_RELEASE, LAYERED_SCOPES))
    rolled_back = _snapshot(db)
    for part in ("shadowed", "overrides", "counts"):
        assert rolled_back[part] == first[part], part


def test_a_primary_only_successor_drops_the_layered_state(db: Any) -> None:
    _publish_layered(db)
    _activate(db, _release_object(db, "fx-rulespec-2026-09-30", (PRIMARY_TITLE, OTHER_PAIR)))
    assert _rows(db, "SELECT COUNT(*) FROM corpus.layered_shadowed_rows") == [(0,)]
    assert _rows(db, "SELECT COUNT(*) FROM corpus.layered_navigation_overrides") == [(0,)]
    _assert_matches_reference(db)


def test_reaffirming_the_serving_release_writes_nothing(db: Any) -> None:
    release_object = _publish_layered(db)
    before = _snapshot(db)
    xmins = _rows(db, "SELECT xmin::text, id FROM corpus.layered_navigation_overrides ORDER BY id")
    result = _activate(db, release_object)
    assert result["scopes"]["activated"] == []
    assert _snapshot(db) == before
    assert (
        _rows(db, "SELECT xmin::text, id FROM corpus.layered_navigation_overrides ORDER BY id")
        == xmins
    )


def test_any_pointer_move_keeps_the_derived_state_in_step(db: Any) -> None:
    _publish(db, "fx-rulespec-2026-09-01", PRIMARY_TITLE, OTHER_PAIR)
    _publish_layered(db)
    layered = _snapshot(db)
    with db.cursor() as cursor:
        cursor.execute(
            "UPDATE corpus.active_scope_pointer AS active "
            "SET release_name = objects.release_name, content_sha256 = objects.content_sha256 "
            "FROM corpus.release_objects objects "
            "WHERE objects.release_name = 'fx-rulespec-2026-09-01' "
            "AND active.jurisdiction = 'fx' AND active.document_class = 'statute'"
        )
        # Counts follow activation, not a hand repoint, as before this migration.
        cursor.execute("REFRESH MATERIALIZED VIEW corpus.current_provision_counts")
    db.commit()
    _assert_matches_reference(db)
    with db.cursor() as cursor:
        cursor.execute(
            "UPDATE corpus.active_scope_pointer AS active "
            "SET release_name = objects.release_name, content_sha256 = objects.content_sha256 "
            "FROM corpus.release_objects objects "
            "WHERE objects.release_name = %s "
            "AND active.jurisdiction = 'fx' AND active.document_class = 'statute'",
            (LAYERED_RELEASE,),
        )
    db.commit()
    assert _snapshot(db)["overrides"] == layered["overrides"]
    with db.cursor() as cursor:
        cursor.execute(
            "DELETE FROM corpus.active_scope_pointer "
            "WHERE jurisdiction = 'fx' AND document_class = 'statute'"
        )
    db.commit()
    assert _rows(db, "SELECT COUNT(*) FROM corpus.layered_shadowed_rows") == [(0,)]
    _activate(db, _release_object(db, LAYERED_RELEASE, LAYERED_SCOPES))
    with db.cursor() as cursor:
        cursor.execute("TRUNCATE corpus.active_scope_pointer, corpus.scope_activation_history")
    db.commit()
    assert _rows(db, "SELECT COUNT(*) FROM corpus.layered_navigation_overrides") == [(0,)]


def test_a_parent_cycle_between_layers_is_broken_at_its_smallest_path(db: Any) -> None:
    base = Scope(
        "fx",
        "statute",
        "2026-04-29-cycle-base",
        (
            Node("fx/statute/9", heading="Title 9"),
            Node("fx/statute/9/a", "fx/statute/9", "A"),
            Node("fx/statute/9/b", "fx/statute/9/a", "B under A"),
        ),
        layer=LAYER_BASE,
    )
    # The primary scope disagrees: it puts A under B, and B is its root.
    primary = Scope(
        "fx",
        "statute",
        "2026-09-20-cycle",
        (
            Node("fx/statute/9/b", None, "B"),
            Node("fx/statute/9/a", "fx/statute/9/b", "A under B"),
        ),
    )
    _publish(db, "fx-rulespec-2026-09-20-cycle", base, primary)
    served = _pair_rows(_navigation(db), ("fx", "statute"))
    assert {row["path"]: row["parent_path"] for row in served.values()} == {
        "fx/statute/9": None,
        "fx/statute/9/a": None,
        "fx/statute/9/b": "fx/statute/9/a",
    }
    assert _tree(served) == _tree(_reference_merged_tree((base, primary)))


def test_a_cycle_is_broken_in_code_point_order(db: Any) -> None:
    """'B' sorts before 'a' by code point, as in Python; en_US collation disagrees."""
    base = Scope(
        "fx",
        "statute",
        "2026-04-29-cycle-case",
        (
            Node("fx/statute/9", heading="Title 9"),
            Node("fx/statute/9/a", "fx/statute/9", "a"),
            Node("fx/statute/9/B", "fx/statute/9/a", "B under a"),
        ),
        layer=LAYER_BASE,
    )
    primary = Scope(
        "fx",
        "statute",
        "2026-09-20-cycle-case",
        (Node("fx/statute/9/B", None, "B"), Node("fx/statute/9/a", "fx/statute/9/B", "a under B")),
    )
    _publish(db, "fx-rulespec-2026-09-20-cycle-case", base, primary)
    served = _pair_rows(_navigation(db), ("fx", "statute"))
    assert {row["path"]: row["parent_path"] for row in served.values()} == {
        "fx/statute/9": None,
        "fx/statute/9/B": None,
        "fx/statute/9/a": "fx/statute/9/B",
    }
    assert _tree(served) == _tree(_reference_merged_tree((base, primary)))


def test_a_cycle_is_broken_at_its_own_smallest_member_not_its_tail(db: Any) -> None:
    base = Scope(
        "fx",
        "statute",
        "2026-04-29-cycle-tail",
        (
            Node("fx/statute/2", heading="Title 2"),
            Node("fx/statute/2/1", "fx/statute/2", "2-1"),
            Node("fx/statute/2/2", "fx/statute/2/1", "2-2 under 2-1"),
            Node("fx/statute/1", "fx/statute/2/2", "1 under 2-2"),
        ),
        layer=LAYER_BASE,
    )
    primary = Scope(
        "fx",
        "statute",
        "2026-09-20-cycle-tail",
        (
            Node("fx/statute/2/2", None, "2-2"),
            Node("fx/statute/2/1", "fx/statute/2/2", "2-1 under 2-2"),
        ),
    )
    _publish(db, "fx-rulespec-2026-09-20-cycle-tail", base, primary)
    served = _pair_rows(_navigation(db), ("fx", "statute"))
    # fx/statute/1 hangs from the cycle and is smaller than every member, but
    # only a member of the cycle may become its root.
    assert {row["path"]: row["parent_path"] for row in served.values()} == {
        "fx/statute/2": None,
        "fx/statute/2/1": None,
        "fx/statute/2/2": "fx/statute/2/1",
        "fx/statute/1": "fx/statute/2/2",
    }
    assert _tree(served) == _tree(_reference_merged_tree((base, primary)))


def test_a_headed_node_keeps_its_label_when_its_segment_changes(db: Any) -> None:
    base = Scope(
        "fx",
        "statute",
        "2026-04-29-label",
        (Node("fx/statute/2", heading="Title 2"), Node("fx/statute/2/1", "fx/statute/2", "2-1")),
        layer=LAYER_BASE,
    )
    # Heading "x" equals the stored segment of the scope root fx/statute/2/5/x.
    primary = Scope("fx", "statute", "2026-09-20-label", (Node("fx/statute/2/5/x", None, "x"),))
    _publish(db, "fx-rulespec-2026-09-20-label", base, primary)
    served = _pair_rows(_navigation(db), ("fx", "statute"))
    node = next(row for row in served.values() if row["path"] == "fx/statute/2/5/x")
    assert (node["segment"], node["label"]) == ("5/x", "x")
    assert _tree(served) == _tree(_built_over_winners((base, primary)))


REGULATION_BASE = Scope(
    "fx",
    "regulation",
    "2026-05-01-regulation-base",
    (
        Node("fx/regulation/1", heading="Chapter 1", ordinal=1),
        Node("fx/regulation/1/1", "fx/regulation/1", "Part 1", 1),
        Node("fx/regulation/1/2", "fx/regulation/1", "Part 2", 2),
    ),
    layer=LAYER_BASE,
)
REGULATION_PRIMARY = Scope(
    "fx",
    "regulation",
    "2026-09-20-regulation",
    (
        Node("fx/regulation/1/1", "fx/regulation/1", "Part 1 (encoded)", 1, encoded=True),
        Node("fx/regulation/1/9", "fx/regulation/1", "Part 9 (new)", 9, encoded=True),
    ),
)


def test_two_layered_pairs_register_activate_and_move_independently(db: Any) -> None:
    """The restoration's shape: us/statute and us/regulation bases in one release."""

    def derived(document_class: str) -> dict[str, Any]:
        return {
            "shadowed": _rows(
                db,
                "SELECT * FROM corpus.layered_shadowed_rows WHERE document_class = %s ORDER BY 3",
                (document_class,),
            ),
            "overrides": _rows(
                db,
                "SELECT * FROM corpus.layered_navigation_overrides "
                "WHERE document_class = %s ORDER BY id",
                (document_class,),
            ),
        }

    scopes = (BASE, PRIMARY_TITLE, REGULATION_BASE, REGULATION_PRIMARY)
    _stage(db, *scopes)
    release_object = _release_object(db, "fx-rulespec-2026-09-20-two-bases", scopes)
    assert _stage_object(db, release_object)["inserted"] is True
    _activate(db, release_object)
    served = _navigation(db)
    for pair, pair_scopes in (
        (("fx", "statute"), (BASE, PRIMARY_TITLE)),
        (("fx", "regulation"), (REGULATION_BASE, REGULATION_PRIMARY)),
    ):
        assert _tree(_pair_rows(served, pair)) == _tree(_reference_merged_tree(pair_scopes))
    regulation = derived("regulation")
    assert regulation["shadowed"]
    successor = replace(PRIMARY_TITLE, version="2026-09-29-title-1")
    _stage(db, successor)
    _activate(db, _release_object(db, "fx-rulespec-2026-09-29-statute", (BASE, successor)))
    assert derived("regulation") == regulation


def test_activation_compares_the_stored_layer_with_the_signed_one(db: Any) -> None:
    release_object = _publish_layered(db)
    before = _snapshot(db)
    demote_base = (
        "UPDATE corpus.release_scopes SET layer = 'primary' "
        "WHERE release_name = %s AND layer = 'base'"
    )
    error = _attempt(db, demote_base, (LAYERED_RELEASE,))
    # Checked right after the write: nothing it would have changed is served.
    assert isinstance(error, errors.RaiseException), error
    assert "immutable" in str(error)
    assert _snapshot(db) == before
    _assert_serving_is_consistent(db)
    # Second line of defence, for membership altered before the guard existed
    # (simulated with triggers off): activation compares the stored layer with
    # the signed one and refuses, and serving is left as it was.
    with db.cursor() as cursor:
        cursor.execute("SET session_replication_role = replica")
        cursor.execute(demote_base, (LAYERED_RELEASE,))
        cursor.execute("RESET session_replication_role")
    db.commit()
    altered = _snapshot(db)
    with pytest.raises(errors.RaiseException, match="membership differs"):
        _activate(db, release_object)
    db.rollback()
    assert _snapshot(db) == altered


def test_service_role_cannot_write_the_derived_state(db: Any) -> None:
    _publish_layered(db)
    for table in ("layered_shadowed_rows", "layered_navigation_overrides"):
        for statement in (f"DELETE FROM corpus.{table}", f"TRUNCATE corpus.{table}"):
            with _as_role(db, "service_role") as cursor:
                with pytest.raises(errors.InsufficientPrivilege):
                    cursor.execute(statement)


def test_a_pointer_moved_to_another_pair_clears_the_old_pair(db: Any) -> None:
    _publish_layered(db)
    with db.cursor() as cursor:
        cursor.execute(
            "DELETE FROM corpus.active_scope_pointer "
            "WHERE jurisdiction = 'fx' AND document_class = 'regulation'"
        )
        cursor.execute(
            "UPDATE corpus.active_scope_pointer SET document_class = 'regulation' "
            "WHERE jurisdiction = 'fx' AND document_class = 'statute'"
        )
    db.commit()
    assert _rows(db, "SELECT COUNT(*) FROM corpus.layered_shadowed_rows") == [(0,)]
    assert _rows(db, "SELECT COUNT(*) FROM corpus.layered_navigation_overrides") == [(0,)]


def test_the_ambiguity_check_covers_only_layered_pairs(db: Any) -> None:
    """A path twice in an unlayered pair is release validation's to reject, as before."""
    twin = replace(
        OTHER_PAIR,
        version="2026-09-02-regs",
        nodes=(Node("fx/regulation/1/1", "fx/regulation/1", "Part 1 again", 1),),
    )
    _publish(db, "fx-rulespec-2026-09-20-unlayered-twin", BASE, PRIMARY_TITLE, OTHER_PAIR, twin)
    assert _rows(
        db,
        "SELECT COUNT(*) FROM corpus.current_provisions WHERE citation_path = 'fx/regulation/1/1'",
    ) == [(2,)]


# ---------------------------------------------------------------------------
# The derived state stays what a derivation from scratch gives: an owner-level
# write to what it is derived from is rejected, or re-derives in the same
# statement.
# ---------------------------------------------------------------------------

# A staged scope no release signs, carrying a path the base carries.
STRAY = Scope(
    "fx",
    "statute",
    "2026-09-25-stray",
    (Node("fx/statute/3/1", heading="Section 3-1 (stray)", ordinal=1),),
)

# A statement that removes the release object and puts it back, so the
# foreign keys, checked at the end of the statement, still hold.
_HIDE_THE_OBJECT = (
    "WITH hidden AS (DELETE FROM corpus.release_objects WHERE release_name = %(release)s "
    "RETURNING *), restored AS (INSERT INTO corpus.release_objects "
    "SELECT * FROM hidden RETURNING 1) "
)
_SERVED_INPUT_WRITES = {
    "demote the base scope": (
        "UPDATE corpus.release_scopes SET layer = 'primary' "
        "WHERE release_name = %(release)s AND layer = 'base'",
        "immutable",
    ),
    "move a primary scope to another version": (
        "UPDATE corpus.release_scopes SET version = %(stray)s "
        "WHERE release_name = %(release)s AND version = %(primary)s",
        "immutable",
    ),
    "delete a primary scope": (
        "DELETE FROM corpus.release_scopes "
        "WHERE release_name = %(release)s AND version = %(primary)s",
        "immutable",
    ),
    "delete the base scope": (
        "DELETE FROM corpus.release_scopes WHERE release_name = %(release)s AND version = %(base)s",
        "immutable",
    ),
    "add an unsigned primary scope": (
        "INSERT INTO corpus.release_scopes (release_name, jurisdiction, document_class, version) "
        "VALUES (%(release)s, 'fx', 'statute', %(stray)s)",
        "not one of its signed scopes",
    ),
    "delete a scope while the object is hidden": (
        _HIDE_THE_OBJECT + "DELETE FROM corpus.release_scopes "
        "WHERE release_name = %(release)s AND version = %(primary)s",
        "immutable",
    ),
    "add a scope while the object is hidden": (
        _HIDE_THE_OBJECT + "INSERT INTO corpus.release_scopes "
        "(release_name, jurisdiction, document_class, version) "
        "VALUES (%(release)s, 'fx', 'statute', %(stray)s)",
        "immutable",
    ),
    "delete a released navigation row while the object is hidden": (
        _HIDE_THE_OBJECT + "DELETE FROM corpus.navigation_nodes "
        "WHERE version = %(primary)s AND path = 'fx/statute/1/4'",
        "immutable",
    ),
    "sign an extra scope into the stored object": (
        "UPDATE corpus.release_objects SET release_object = jsonb_set(release_object, "
        "'{content,scopes}', (release_object #> '{content,scopes}') || jsonb_build_array("
        "jsonb_build_object('jurisdiction', 'fx', 'document_class', 'statute', "
        "'version', %(stray)s))) WHERE release_name = %(release)s",
        "immutable",
    ),
    "delete the release object": (
        "DELETE FROM corpus.release_objects WHERE release_name = %(release)s",
        "immutable",
    ),
    "truncate membership": ("TRUNCATE corpus.release_scopes", "immutable"),
    "truncate release objects": ("TRUNCATE corpus.release_objects CASCADE", "immutable"),
    "truncate navigation": ("TRUNCATE corpus.navigation_nodes", "immutable"),
    "truncate provisions": ("TRUNCATE corpus.provisions CASCADE", "immutable"),
    "truncate both staged tables": (
        "TRUNCATE corpus.provisions, corpus.navigation_nodes CASCADE",
        "immutable",
    ),
    "delete derived rows": ("DELETE FROM corpus.layered_navigation_overrides", "derivation"),
    "truncate a derived table": ("TRUNCATE corpus.layered_shadowed_rows", "derivation"),
    "add a derived row": (
        "INSERT INTO corpus.layered_shadowed_rows (jurisdiction, document_class, "
        "citation_path, release_name, content_sha256, base_version, navigation_id) "
        "VALUES ('fx', 'statute', 'fx/statute/9', %(release)s, repeat('0', 64), "
        "%(base)s, 'n')",
        "derivation",
    ),
}


@pytest.mark.parametrize("write", list(_SERVED_INPUT_WRITES))
def test_writes_under_a_served_layered_release_are_rejected(db: Any, write: str) -> None:
    _stage(db, STRAY)
    _publish_layered(db)
    before = _snapshot(db)
    stored = _stored(db)
    statement, message = _SERVED_INPUT_WRITES[write]
    error = _attempt(
        db,
        statement,
        {
            "release": LAYERED_RELEASE,
            "stray": STRAY.version,
            "primary": PRIMARY_TITLE.version,
            "base": BASE.version,
        },
    )
    # Checked right after the write: serving is still exactly what a
    # derivation from scratch serves, and nothing changed.
    _assert_serving_is_consistent(db)
    assert isinstance(error, errors.RaiseException), error
    assert message in str(error)
    assert _snapshot(db) == before
    assert _stored(db) == stored


def test_released_rows_and_membership_refuse_truncate_for_every_release(db: Any) -> None:
    """The statement-level twin of the released-row guard, layered or not."""
    _publish(db, "fx-rulespec-2026-09-01", OTHER_PAIR)
    for statement in (
        "TRUNCATE corpus.navigation_nodes",
        "TRUNCATE corpus.provisions CASCADE",
        "TRUNCATE corpus.release_scopes",
    ):
        error = _attempt(db, statement)
        assert isinstance(error, errors.RaiseException), statement
        assert "immutable" in str(error)
    _assert_matches_reference(db)


def test_truncate_still_clears_rows_no_release_signs(db: Any) -> None:
    _stage(db, BASE, OTHER_PAIR)
    assert _attempt(db, "TRUNCATE corpus.provisions, corpus.navigation_nodes CASCADE") is None
    assert _rows(db, "SELECT COUNT(*) FROM corpus.provisions") == [(0,)]


def test_only_signed_scopes_join_membership(db: Any) -> None:
    """Membership rows of a signed release cannot be deleted, so no stray one gets in."""
    _stage(db, STRAY, PRIMARY_TITLE)
    release_object = _release_object(db, "fx-rulespec-2026-09-01", (PRIMARY_TITLE,))
    _stage_object(db, release_object)
    insert = (
        "INSERT INTO corpus.release_scopes "
        "(release_name, jurisdiction, document_class, version, layer) "
        "VALUES ('fx-rulespec-2026-09-01', 'fx', 'statute', %s, %s)"
    )
    for version, layer in ((STRAY.version, "primary"), (PRIMARY_TITLE.version, "base")):
        error = _attempt(db, insert, (version, layer))
        assert isinstance(error, errors.RaiseException), (version, layer)
        assert "not one of its signed scopes" in str(error)
    assert _attempt(db, insert, (PRIMARY_TITLE.version, "primary")) is None
    _activate(db, release_object)
    assert _ids(db, "corpus.current_provisions") == {
        _provision_id(node.path, PRIMARY_TITLE.version) for node in PRIMARY_TITLE.nodes
    }


@pytest.mark.parametrize("restore", ["reactivation", "insert"])
def test_restoring_membership_lost_before_the_guard_rederives_the_pair(
    db: Any, restore: str
) -> None:
    """Membership altered before the guard existed (simulated with triggers off)
    is restored by re-activating the release, or by inserting the signed scope
    back. Its pointer does not move, so the restored row re-derives the pair."""
    release_object = _publish_layered(db)
    expected = _snapshot(db)
    with db.cursor() as cursor:
        cursor.execute("SET session_replication_role = replica")
        cursor.execute(
            "DELETE FROM corpus.release_scopes WHERE release_name = %s AND version = %s",
            (LAYERED_RELEASE, PRIMARY_TITLE.version),
        )
        cursor.execute("RESET session_replication_role")
        # The owner brings the derived state in line with what is now served.
        cursor.execute("SELECT corpus.refresh_layered_serving('fx', 'statute')")
    db.commit()
    _assert_serving_is_consistent(db)
    assert _snapshot(db)["overrides"] != expected["overrides"]
    if restore == "reactivation":
        assert _activate(db, release_object)["scopes"]["activated"] == []
    else:
        restored = _attempt(
            db,
            "INSERT INTO corpus.release_scopes "
            "(release_name, jurisdiction, document_class, version) "
            "VALUES (%s, 'fx', 'statute', %s)",
            (LAYERED_RELEASE, PRIMARY_TITLE.version),
        )
        assert restored is None
    _assert_serving_is_consistent(db)
    assert _snapshot(db) == expected


def test_reactivating_an_earlier_signed_release_restores_its_serving(db: Any) -> None:
    first = _publish_layered(db)
    served = _snapshot(db)
    _activate(
        db,
        _release_object(db, "fx-rulespec-2026-09-30-base", (BASE, PRIMARY_SECTIONS, OTHER_PAIR)),
    )
    _assert_serving_is_consistent(db)
    assert _snapshot(db)["overrides"] != served["overrides"]
    result = _activate(db, first)
    assert {
        (pair["jurisdiction"], pair["document_class"]) for pair in result["scopes"]["activated"]
    } == {
        ("fx", "regulation"),
        ("fx", "statute"),
    }
    _assert_serving_is_consistent(db)
    again = _snapshot(db)
    assert (again["shadowed"], again["overrides"]) == (served["shadowed"], served["overrides"])


def test_release_objects_change_only_their_publication_time(db: Any) -> None:
    _publish_layered(db)
    assert (
        _attempt(
            db,
            "UPDATE corpus.release_objects SET created_at = created_at + interval '1 day' "
            "WHERE release_name = %s",
            (LAYERED_RELEASE,),
        )
        is None
    )
    for statement in (
        "UPDATE corpus.release_objects SET content_sha256 = repeat('0', 64) "
        "WHERE release_name = %s",
        "UPDATE corpus.release_objects SET release_name = 'fx-renamed' WHERE release_name = %s",
    ):
        error = _attempt(db, statement, (LAYERED_RELEASE,))
        assert isinstance(error, errors.RaiseException), statement
    # An object no release membership names (registered, never activated) can go.
    _stage(db, STRAY)
    _stage_object(db, _release_object(db, "fx-rulespec-2026-09-26-stray", (STRAY,)))
    assert (
        _attempt(
            db,
            "DELETE FROM corpus.release_objects WHERE release_name = 'fx-rulespec-2026-09-26-stray'",
        )
        is None
    )
    _assert_serving_is_consistent(db)


@pytest.mark.parametrize("isolation", ["REPEATABLE READ", "SERIALIZABLE"])
def test_derivation_and_membership_inserts_need_read_committed(db: Any, isolation: str) -> None:
    """A snapshot older than the statement could miss membership committed meanwhile."""
    _publish(db, "fx-rulespec-2026-09-01", PRIMARY_TITLE, OTHER_PAIR)
    _stage(db, *LAYERED_SCOPES)
    release_object = _release_object(db, LAYERED_RELEASE, LAYERED_SCOPES)
    _stage_object(db, release_object)
    before = _snapshot(db)
    statements = (
        # A pointer write, which re-derives its pair.
        "DELETE FROM corpus.active_scope_pointer WHERE document_class = 'statute'",
        # A signed scope inserted into membership, which re-derives a served pair.
        "INSERT INTO corpus.release_scopes (release_name, jurisdiction, document_class, version) "
        f"VALUES ('{LAYERED_RELEASE}', 'fx', 'regulation', '{OTHER_PAIR.version}')",
        "SELECT corpus.rederive_layered_serving()",
        "SELECT corpus.refresh_layered_serving('fx', 'statute')",
    )
    for statement in statements:
        with db.cursor() as cursor:
            cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
            with pytest.raises(errors.RaiseException, match="only under READ COMMITTED"):
                cursor.execute(statement)
        db.rollback()
    assert _snapshot(db) == before
    _activate(db, release_object)
    _assert_serving_is_consistent(db)


_COUNTS = (
    "SELECT jurisdiction, document_class, provision_count, body_count, top_level_count, "
    "rulespec_count FROM corpus.current_provision_counts ORDER BY 1, 2"
)


def test_rederivation_refreshes_served_counts_when_the_shadowed_rows_change(db: Any) -> None:
    _publish_layered(db)
    counts = _rows(db, _COUNTS)
    with _triggers_off(db) as cursor:
        # Derived rows lost by hand, and the counts refreshed over them.
        cursor.execute("DELETE FROM corpus.layered_shadowed_rows")
        cursor.execute("REFRESH MATERIALIZED VIEW corpus.current_provision_counts")
    assert _rows(db, _COUNTS) != counts
    _rows(db, "SELECT corpus.rederive_layered_serving()")
    assert _rows(db, _COUNTS) == counts
    _assert_serving_is_consistent(db)


# ---------------------------------------------------------------------------
# Deployment: the file never derives a served base layer; the derivation is
# its own step.
# ---------------------------------------------------------------------------


def test_applying_the_file_with_a_base_scope_served_leaves_the_derivation_to_its_own_step(
    db: Any,
) -> None:
    _publish_layered(db)
    served = _snapshot(db)
    with _triggers_off(db) as cursor:
        # Removed by hand, so only a derivation brings them back.
        cursor.execute("DELETE FROM corpus.layered_navigation_overrides")
    del db.notices[:]
    with db.cursor() as cursor:
        cursor.execute(LAYERED_SERVING_MIGRATION.read_text(encoding="utf-8"))
    db.commit()
    assert _rows(db, "SELECT COUNT(*) FROM corpus.layered_navigation_overrides") == [(0,)]
    assert any("rederive_layered_serving" in notice for notice in db.notices), db.notices
    assert _rows(db, "SELECT corpus.rederive_layered_serving()") == [(len(served["shadowed"]),)]
    _assert_serving_is_consistent(db)
    assert _snapshot(db) == served


def test_applying_the_file_with_no_base_scope_served_empties_the_derived_state(db: Any) -> None:
    _publish(db, "fx-rulespec-2026-09-01", PRIMARY_TITLE, OTHER_PAIR)
    with _triggers_off(db) as cursor:
        cursor.execute(
            "INSERT INTO corpus.layered_shadowed_rows (jurisdiction, document_class, "
            "citation_path, release_name, content_sha256, base_version, navigation_id) "
            "VALUES ('fx', 'statute', 'fx/statute/9', 'stale', repeat('0', 64), 'v', 'n')"
        )
    with db.cursor() as cursor:
        cursor.execute(LAYERED_SERVING_MIGRATION.read_text(encoding="utf-8"))
    db.commit()
    assert _rows(db, "SELECT COUNT(*) FROM corpus.layered_shadowed_rows") == [(0,)]
    _assert_matches_reference(db)


def test_rederivation_takes_only_activation_locks_and_blocks_no_read(
    layered_dsn: str, db: Any
) -> None:
    _publish_layered(db)
    served = set(_navigation(db))
    with (
        closing(psycopg2.connect(layered_dsn)) as deriving,
        closing(psycopg2.connect(layered_dsn)) as other,
    ):
        with deriving.cursor() as cursor:
            cursor.execute("SELECT corpus.rederive_layered_serving()")
            cursor.execute(
                "SELECT relation.relname, lock.mode FROM pg_locks lock "
                "JOIN pg_class relation ON relation.oid = lock.relation "
                "JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace "
                "WHERE lock.pid = pg_backend_pid() AND namespace.nspname = 'corpus' "
                "AND relation.relkind IN ('r', 'm')"
            )
            locks = set(cursor.fetchall())
        derived = {"layered_shadowed_rows", "layered_navigation_overrides"}
        # Activation takes EXCLUSIVE on the pointers and, deriving, writes and
        # analyzes the two derived tables; everything else is only read. The
        # derived state did not change, so current_provision_counts is not
        # refreshed (the lock its refresh takes is not held).
        assert ("active_scope_pointer", "ExclusiveLock") in locks
        assert {(relation, mode) for relation, mode in locks if mode != "AccessShareLock"} <= {
            ("active_scope_pointer", "ExclusiveLock")
        } | {
            (relation, mode)
            for relation in derived
            for mode in ("RowExclusiveLock", "ShareUpdateExclusiveLock")
        }
        # Serving reads go on, and see the committed state, while it is open.
        with other.cursor() as cursor:
            cursor.execute("SET lock_timeout = '1s'")
            cursor.execute("SET ROLE anon")
            cursor.execute("SELECT id FROM corpus.current_navigation_nodes")
            assert {row[0] for row in cursor.fetchall()} == served
            cursor.execute("SELECT id FROM corpus.navigation_nodes")
            assert {row[0] for row in cursor.fetchall()} == served
            cursor.execute("SELECT COUNT(*) FROM corpus.current_provisions")
            cursor.execute("SELECT * FROM corpus.get_root_document_counts()")
        other.rollback()
        # A pointer write waits for it, as it waits for an activation.
        with other.cursor() as cursor:
            cursor.execute("SET lock_timeout = '200ms'")
            with pytest.raises(errors.LockNotAvailable):
                cursor.execute("UPDATE corpus.active_scope_pointer SET activated_at = now()")
        other.rollback()
        deriving.commit()
    _assert_serving_is_consistent(db)


def test_derivation_analyzes_the_layered_tables(db: Any) -> None:
    """Planner statistics follow the derived rows; an unlayered activation leaves them alone."""
    tables = ("layered_shadowed_rows", "layered_navigation_overrides")
    with db.cursor() as cursor:
        for table in tables:
            # Keep autovacuum from analyzing between the checks below.
            cursor.execute(f"ALTER TABLE corpus.{table} SET (autovacuum_enabled = false)")
    db.commit()

    def estimated() -> dict[str, float]:
        return {
            relation: float(rows)
            for relation, rows in _rows(
                db,
                "SELECT relname, reltuples FROM pg_class WHERE oid IN "
                "('corpus.layered_shadowed_rows'::regclass, "
                "'corpus.layered_navigation_overrides'::regclass)",
            )
        }

    def actual() -> dict[str, float]:
        return {
            table: float(_rows(db, f"SELECT COUNT(*) FROM corpus.{table}")[0][0])
            for table in tables
        }

    # Emptied by TRUNCATE in the reset: never analyzed since.
    assert set(estimated().values()) == {-1.0}
    _publish(db, "fx-rulespec-2026-09-01", PRIMARY_TITLE, OTHER_PAIR)
    assert set(estimated().values()) == {-1.0}
    _publish_layered(db)
    assert min(actual().values()) > 0
    assert estimated() == actual()
    _activate(db, _release_object(db, "fx-rulespec-2026-09-30", (PRIMARY_TITLE, OTHER_PAIR)))
    assert estimated() == actual() == dict.fromkeys(tables, 0.0)
    _publish_layered(db)
    with _triggers_off(db) as cursor:
        cursor.execute("DELETE FROM corpus.layered_shadowed_rows")
        cursor.execute("DELETE FROM corpus.layered_navigation_overrides")
        cursor.execute("ANALYZE corpus.layered_shadowed_rows")
        cursor.execute("ANALYZE corpus.layered_navigation_overrides")
    assert estimated() == dict.fromkeys(tables, 0.0)
    _rows(db, "SELECT corpus.rederive_layered_serving()")
    assert min(actual().values()) > 0
    assert estimated() == actual()
    # Removing every pointer empties the tables, and analyzes them.
    with db.cursor() as cursor:
        cursor.execute("TRUNCATE corpus.active_scope_pointer, corpus.scope_activation_history")
    db.commit()
    assert estimated() == actual() == dict.fromkeys(tables, 0.0)


def test_a_blank_heading_follows_its_segment_as_navigation_py_does(db: Any) -> None:
    """A heading of only non-ASCII spaces is no heading to str.strip()."""
    sections = replace(
        PRIMARY_SECTIONS,
        nodes=(Node("fx/statute/2/5/x", None, " 　", None, encoded=True),),
    )
    _publish(db, "fx-rulespec-2026-09-22-blank", BASE, sections)
    node = _navigation(db)[
        next(row["id"] for row in _staged_navigation(sections) if row["path"] == "fx/statute/2/5/x")
    ]
    assert (node["parent_path"], node["segment"], node["label"]) == (
        "fx/statute/2",
        "5/x",
        "5/x",
    )


_SEGMENT_TEXT = st.text(alphabet="aZ09 .:-–/", min_size=1, max_size=30)


@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    path=_SEGMENT_TEXT, parent=st.one_of(st.none(), _SEGMENT_TEXT), digits=st.integers(0, 10**14)
)
def test_sql_segment_helpers_equal_navigation_py(
    layered_dsn: str, path: str, parent: str | None, digits: int
) -> None:
    segment = f"{path}{digits}"
    with closing(psycopg2.connect(layered_dsn)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT corpus.navigation_sort_segment(%s), corpus.navigation_segment(%s, %s)",
            (segment, path, parent),
        )
        sort_segment, sql_segment = cursor.fetchone()
    assert sort_segment == _normalize_sort_segment(segment)
    assert sql_segment == _segment(path, parent)


# Every character str.isspace() accepts, and two that it does not.
_HEADING_TEXT = st.text(
    alphabet=("\t\n\x0b\x0c\r\x1c\x1d\x1e\x1f \x85\xa0                　​H"),
    max_size=6,
)


@settings(
    max_examples=300,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(heading=st.one_of(st.none(), _HEADING_TEXT))
def test_sql_heading_blankness_equals_python_strip(layered_dsn: str, heading: str | None) -> None:
    """navigation._label_text falls back to the segment exactly when this is true."""
    with closing(psycopg2.connect(layered_dsn)) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT corpus.navigation_heading_is_blank(%s)", (heading,))
        (blank,) = cursor.fetchone()
    assert blank is (heading is None or not heading.strip())


@pytest.fixture(scope="module")
def pre_layer_dsn() -> Iterator[str]:
    yield from _create_database(layered=False)


def test_memberships_that_exist_when_the_migration_is_applied_become_primary(
    pre_layer_dsn: str,
) -> None:
    """Production applies the file to a database with activated releases."""
    with closing(psycopg2.connect(pre_layer_dsn)) as connection:
        _publish(connection, "fx-rulespec-2026-09-01", PRIMARY_TITLE, OTHER_PAIR)
        _publish(connection, "fx-rulespec-2026-09-02", replace(BASE, layer=LAYER_PRIMARY))
        with connection.cursor() as cursor:
            cursor.execute(LAYERED_SERVING_MIGRATION.read_text(encoding="utf-8"))
        connection.commit()
        assert _rows(connection, "SELECT DISTINCT layer FROM corpus.release_scopes") == [
            ("primary",)
        ]
        _assert_matches_reference(connection)


class _ServedRest:
    """The query client's PostgREST requests, answered by the serving views as anon.

    Filters ``eq.`` and ``in.(...)``, ``order``, ``limit``, ``offset`` and
    ``select``, with every response capped at ``max_rows`` rows, as
    db-max-rows caps a PostgREST response.
    """

    def __init__(self, connection: Any, *, max_rows: int) -> None:
        self.connection = connection
        self.max_rows = max_rows

    def __call__(self, table: str, params: Any = None, single: bool = False) -> list[dict]:
        items = list(params.items()) if isinstance(params, Mapping) else list(params or [])
        conditions: list[Any] = []
        arguments: list[Any] = []
        order: list[Any] = []
        limit, offset, select = self.max_rows, 0, "*"
        for key, value in items:
            if key == "order":
                order = [sql.Identifier(column) for column in value.split(",")]
            elif key == "limit":
                limit = min(int(value), self.max_rows)
            elif key == "offset":
                offset = int(value)
            elif key == "select":
                select = value
            else:
                operator, _, operand = value.partition(".")
                if operator == "eq":
                    conditions.append(sql.SQL("{}::text = %s").format(sql.Identifier(key)))
                    arguments.append(operand)
                else:
                    assert operator == "in", value
                    conditions.append(sql.SQL("{}::text = ANY(%s)").format(sql.Identifier(key)))
                    arguments.append(operand.removeprefix("(").removesuffix(")").split(","))
        query = sql.SQL("SELECT {} FROM corpus.{}{}{} LIMIT %s OFFSET %s").format(
            sql.SQL("*")
            if select == "*"
            else sql.SQL(", ").join(sql.Identifier(column) for column in select.split(",")),
            sql.Identifier(table),
            sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions) if conditions else sql.SQL(""),
            sql.SQL(" ORDER BY ") + sql.SQL(", ").join(order) if order else sql.SQL(""),
        )
        with _as_role(self.connection, "anon") as cursor:
            cursor.execute(query, (*arguments, limit, offset))
            names = [column.name for column in cursor.description]
            return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def test_the_query_client_reads_children_through_the_serving_views(db: Any) -> None:
    """Merged children for a layered pair, parent ids for an unlayered one."""
    _publish_layered(db)
    query = SupabaseQuery(url="https://test.supabase.co", anon_key="test-key")
    query._request = _ServedRest(db, max_rows=2)  # type: ignore[method-assign]
    section = query.get_section_with_children("fx/statute/2", jurisdiction="fx")
    assert section is not None
    assert [(child.citation_path, child.id) for child in section.children] == [
        ("fx/statute/2/1", _provision_id("fx/statute/2/1", BASE.version)),
        ("fx/statute/2/2", _provision_id("fx/statute/2/2", PRIMARY_SECTIONS.version)),
        ("fx/statute/2/5/x", _provision_id("fx/statute/2/5/x", PRIMARY_SECTIONS.version)),
    ]
    section = query.get_section_with_children("fx/statute/1", jurisdiction="fx")
    assert section is not None
    assert [child.citation_path for child in section.children] == [
        "fx/statute/1/1",
        "fx/statute/1/2",
        "fx/statute/1/3",
        "fx/statute/1/4",
    ]
    section = query.get_section_with_children("fx/regulation/1", jurisdiction="fx")
    assert section is not None
    assert [child.citation_path for child in section.children] == ["fx/regulation/1/1"]


def test_references_follow_the_served_row_of_each_path(db: Any) -> None:
    _stage(db, BASE, PRIMARY_TITLE)
    base_section = _provision_id("fx/statute/1/1", BASE.version)
    primary_section = _provision_id("fx/statute/1/1", PRIMARY_TITLE.version)
    base_title_3 = _provision_id("fx/statute/3/1", BASE.version)
    with db.cursor() as cursor:
        for source, target, path, offset in (
            (base_section, base_title_3, "fx/statute/3/1", 0),
            (primary_section, base_title_3, "fx/statute/3/1", 10),
            (base_title_3, base_section, "fx/statute/1/1", 0),
        ):
            cursor.execute(
                "INSERT INTO corpus.provision_references (source_provision_id, "
                "target_citation_path, target_provision_id, citation_text, pattern_kind, "
                "start_offset, end_offset) VALUES (%s, %s, %s, 'cite', 'internal', %s, %s)",
                (source, path, target, offset, offset + 4),
            )
    db.commit()
    _activate(db, _release_object(db, "fx-rulespec-2026-09-20-refs", (BASE, PRIMARY_TITLE)))
    with _as_role(db, "anon") as cursor:
        cursor.execute(
            "SELECT direction, start_offset, other_provision_id::text, target_resolved "
            "FROM corpus.get_provision_references('fx/statute/1/1')"
        )
        # Only the served (primary) row's own references surface.
        assert cursor.fetchall() == [("outgoing", 10, base_title_3, True)]
        cursor.execute(
            "SELECT direction, start_offset, other_provision_id::text, target_resolved "
            "FROM corpus.get_provision_references('fx/statute/3/1')"
        )
        # A reference from the shadowed base row is not served; one to it is
        # left unresolved, as a reference to any unserved row is.
        assert cursor.fetchall() == [
            ("incoming", 10, primary_section, True),
            ("outgoing", 0, None, False),
        ]


def test_anchor_resolution_reads_anchors_only(db: Any) -> None:
    _stage(db, BASE, PRIMARY_TITLE)
    base_section = _provision_id("fx/statute/1/1", BASE.version)
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO corpus.provision_anchors (citation_path, parent_provision_id, "
            "parent_citation_path, char_start, char_end, anchor_text, label, depth, "
            "extractor_version) VALUES ('fx/statute/1/1/a', %s, 'fx/statute/1/1', 0, 4, "
            "'Text', 'a', 0, 'test')",
            (base_section,),
        )
    db.commit()
    before = _rows(db, "SELECT * FROM corpus.resolve_provision_anchor('fx/statute/1/1/a')")
    _activate(db, _release_object(db, "fx-rulespec-2026-09-20-anchors", (BASE, PRIMARY_TITLE)))
    assert _rows(db, "SELECT * FROM corpus.resolve_provision_anchor('fx/statute/1/1/a')") == before
    # The anchored base row is shadowed; its path resolves to the primary row.
    assert (base_section,) in _rows(db, "SELECT id::text FROM corpus.legacy_provisions")


# ---------------------------------------------------------------------------
# Properties over generated layered pairs.
# ---------------------------------------------------------------------------


@st.composite
def _well_formed_pair(draw: st.DrawFn) -> tuple[Scope, ...]:
    """A base scope closed under ancestors, and primary scopes that agree with it.

    Every provision's explicit parent is its immediate path prefix. Primary
    scopes partition a set of base and new paths; a scope never skips a level
    between two of its own nodes. Under these conditions the migration's merge
    must equal build_navigation_nodes run over the winning records.
    """
    universe: dict[str, str | None] = {}

    def grow(prefix: str | None, path: str, depth: int) -> None:
        universe[path] = prefix
        if depth < 3:
            for segment in draw(st.lists(_SEGMENTS, max_size=3, unique=True)):
                grow(path, f"{path}/{segment}", depth + 1)

    for title in draw(st.lists(st.sampled_from(["1", "2", "3"]), min_size=1, unique=True)):
        grow(None, f"fx/statute/{title}", 0)
    paths = sorted(universe, key=lambda p: (p.count("/"), p))
    base: set[str] = set()
    for path in draw(st.lists(st.sampled_from(paths), min_size=1, unique=True)):
        cursor: str | None = path
        while cursor is not None:
            base.add(cursor)
            cursor = universe[cursor]
    owner: dict[str, int | None] = {}
    lineage: dict[str, frozenset[int]] = {}
    for path in paths:
        parent = universe[path]
        parent_owner = owner.get(parent) if parent is not None else None
        used = lineage.get(parent, frozenset()) if parent is not None else frozenset()
        choices: list[int | None] = [] if path not in base else [None]
        if parent_owner is not None:
            choices.append(parent_owner)
        choices.extend(index for index in range(3) if index not in used)
        if not choices:
            # Every scope is taken above: the base carries the path (its parent
            # is a base path, so the base stays closed under ancestors).
            base.add(path)
            choices = [None]
        choice = draw(st.sampled_from(choices))
        owner[path] = choice
        lineage[path] = used | ({choice} if choice is not None else frozenset())

    def node(path: str) -> Node:
        return Node(
            path,
            universe[path],
            draw(st.sampled_from([None, f"H {path}", "\u00a0"])),
            draw(st.sampled_from([None, 1, 2, 3])),
            draw(st.booleans()),
        )

    scopes = [
        Scope(
            "fx",
            "statute",
            "2026-04-29-base",
            tuple(node(path) for path in paths if path in base),
            layer=LAYER_BASE,
        )
    ]
    for index in range(3):
        nodes = tuple(node(path) for path in paths if owner[path] == index)
        if nodes:
            scopes.append(Scope("fx", "statute", f"2026-09-2{index}-primary", nodes))
    return tuple(scopes)


@st.composite
def _arbitrary_pair(draw: st.DrawFn) -> tuple[Scope, ...]:
    """Base and primary scopes with arbitrary explicit parents, cycles included."""
    pool = [
        f"fx/statute/{a}" + (f"/{b}" if b else "") + (f"/{c}" if c else "")
        for a in ("1", "2")
        for b in ("", "1", "2")
        for c in ("", "a")
        if not (c and not b)
    ]

    def scope(version: str, layer: str, min_size: int) -> Scope:
        paths = draw(st.lists(st.sampled_from(pool), min_size=min_size, max_size=6, unique=True))
        return Scope(
            "fx",
            "statute",
            version,
            tuple(
                Node(
                    path,
                    draw(st.sampled_from([None, *pool])),
                    draw(st.sampled_from([None, "H", "\u00a0\u3000"])),
                    draw(st.sampled_from([None, 1, 2])),
                    draw(st.booleans()),
                )
                for path in paths
            ),
            layer=layer,
        )

    base = scope("2026-04-29-base", LAYER_BASE, 1)
    first = scope("2026-09-20-primary", LAYER_PRIMARY, 1)
    taken = {node.path for node in first.nodes}
    second = scope("2026-09-21-primary", LAYER_PRIMARY, 0)
    second = replace(second, nodes=tuple(n for n in second.nodes if n.path not in taken))
    return tuple(s for s in (base, first, second) if s.nodes)


def _check_layered_pair(dsn: str, scopes: tuple[Scope, ...]) -> dict[str, dict[str, Any]]:
    _reset(dsn)
    with closing(psycopg2.connect(dsn)) as connection:
        release_object = _publish(connection, "fx-rulespec-generated", *scopes)
        layered = any(scope.layer == LAYER_BASE for scope in scopes) and any(
            scope.layer == LAYER_PRIMARY for scope in scopes
        )
        assert release_object["schema_version"] == (
            RELEASE_OBJECT_SCHEMA_V4
            if any(scope.layer == LAYER_BASE for scope in scopes)
            else RELEASE_OBJECT_SCHEMA_V3
        )
        current = _ids(connection, "corpus.current_provisions")
        legacy = _ids(connection, "corpus.legacy_provisions")
        assert current == _reference_served_provisions(scopes)
        assert current.isdisjoint(legacy)
        assert current | legacy == _ids(connection, "corpus.provisions")
        paths = [
            row[0]
            for row in _rows(connection, "SELECT citation_path FROM corpus.current_provisions")
        ]
        assert len(paths) == len(set(paths))
        assert _rows(
            connection,
            "SELECT COUNT(*), COUNT(DISTINCT id), COUNT(DISTINCT path) "
            "FROM corpus.current_navigation_nodes",
        ) == [(len(current),) * 3]
        served = _navigation(connection)
        assert _tree(served) == _tree(_reference_merged_tree(scopes))
        bases = [scope for scope in scopes if scope.layer == LAYER_BASE]
        if bases:
            # Release validation predicts the tree serving builds.
            predicted = merge_layered_parent_paths(
                scope_parent_paths((node.path, node.parent) for node in bases[0].nodes),
                [
                    scope_parent_paths((node.path, node.parent) for node in scope.nodes)
                    for scope in scopes
                    if scope.layer == LAYER_PRIMARY
                ],
            )
            assert predicted.parent_paths == {
                row["path"]: row["parent_path"] for row in served.values()
            }
        assert {row["provision_id"] for row in served.values()} == current
        for role in ("anon", "authenticated"):
            assert _ids(connection, "corpus.navigation_nodes", role=role) == set(served)
        roots = Counter(
            (row["jurisdiction"], row["doc_type"])
            for row in served.values()
            if row["parent_path"] is None
        )
        assert _rows(connection, "SELECT * FROM corpus.get_root_document_counts()") == sorted(
            (j, dc, count) for (j, dc), count in roots.items()
        )
        assert _rows(connection, "SELECT provision_count FROM corpus.current_provision_counts") == [
            (len(current),)
        ]
        if not layered:
            _assert_matches_reference(connection)
        return served


@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(scopes=_well_formed_pair())
def test_merge_equals_building_navigation_over_the_winning_records(
    layered_dsn: str, scopes: tuple[Scope, ...]
) -> None:
    served = _check_layered_pair(layered_dsn, scopes)
    assert _tree(served) == _tree(_built_over_winners(scopes))


@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(scopes=_arbitrary_pair())
def test_merge_follows_its_rules_on_arbitrary_parents(
    layered_dsn: str, scopes: tuple[Scope, ...]
) -> None:
    _check_layered_pair(layered_dsn, scopes)


# ---------------------------------------------------------------------------
# Registration of v4 objects (20260927100000).
# ---------------------------------------------------------------------------


def _stage_object(connection: Any, release_object: Mapping[str, Any]) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT corpus.stage_corpus_release_object(%s::jsonb)",
            (Json(dict(release_object)),),
        )
        row = cursor.fetchone()
    connection.commit()
    assert row is not None
    return row[0]


def test_registration_accepts_a_v4_object_without_serving_it(db: Any) -> None:
    _stage(db, BASE, PRIMARY_TITLE)
    release_object = _release_object(db, "fx-rulespec-2026-09-20-staged", (BASE, PRIMARY_TITLE))
    assert _stage_object(db, release_object)["inserted"] is True
    assert _rows(db, "SELECT COUNT(*) FROM corpus.release_scopes") == [(0,)]
    assert _rows(db, "SELECT COUNT(*) FROM corpus.active_scope_pointer") == [(0,)]
    assert _activate(db, release_object)["active"] is True


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda scopes: [{**s, "layer": "primary"} if "layer" in s else s for s in scopes],
            "unsupported layer",
        ),
        (
            lambda scopes: [{**s, "layer": "Base"} if "layer" in s else s for s in scopes],
            "unsupported layer",
        ),
        (
            lambda scopes: [{k: v for k, v in s.items() if k != "layer"} for s in scopes],
            "reserved for releases with a base scope",
        ),
        (
            lambda scopes: [*scopes, {**scopes[0], "version": "2026-05-01-base"}],
            "more than one base scope",
        ),
    ],
)
def test_registration_enforces_v4_layer_rules(db: Any, mutate: Any, message: str) -> None:
    _stage(db, BASE, PRIMARY_TITLE)
    release_object = _release_object(db, "fx-rulespec-2026-09-20-bad", (BASE, PRIMARY_TITLE))
    content = dict(release_object["content"])
    content["scopes"] = mutate(content["scopes"])
    with pytest.raises(errors.RaiseException, match=message):
        _stage_object(db, _reseal(release_object, content))
    db.rollback()


def test_registration_migration_holds_only_the_registration_function() -> None:
    text = STAGED_RELEASE_OBJECT_V4_MIGRATION.read_text(encoding="utf-8")
    statements = re.findall(
        r"^(?:CREATE|ALTER|DROP|GRANT|REVOKE|INSERT|UPDATE|DELETE)\b.*$", text, re.M
    )
    assert statements == [
        "CREATE OR REPLACE FUNCTION corpus.stage_corpus_release_object(p_release_object jsonb)",
        "REVOKE EXECUTE ON FUNCTION corpus.stage_corpus_release_object(jsonb)",
        "GRANT EXECUTE ON FUNCTION corpus.stage_corpus_release_object(jsonb)",
    ]


# ---------------------------------------------------------------------------
# Query plans at representative scale.
#
# The May base layers restore 306,923 rows to us (60,446 statute and 246,477
# regulation). This builds them, 48 primary us scopes (24 statute, 24
# regulation; half without their title or part row, so their sections are
# roots of their scope) colliding with 456 base paths, superseded us history
# and other jurisdictions, serves them through the active scope map (whose
# trigger derives the layered state), and checks the plans of the requests the
# serving views answer. AXIOM_CORPUS_PLAN_SCALE=production adds the stored
# history production has (1.52M rows per table); AXIOM_CORPUS_PLAN_REPORT=<file>
# writes EXPLAIN (ANALYZE, BUFFERS) of each request, run as anon under the 3 s
# anon statement timeout.
# ---------------------------------------------------------------------------

_SCALE = {
    "ci": {"history_versions": 4, "history_rows": 10_000, "others": 10, "other_rows": 2_000},
    "production": {
        "history_versions": 40,
        "history_rows": 10_000,
        "others": 200,
        "other_rows": 2_000,
    },
}[os.environ.get("AXIOM_CORPUS_PLAN_SCALE", "ci")]

_SCALE_ROWS = """
CREATE TEMP TABLE scale_rows (
  jurisdiction text, doc_type text, version text, path text, parent_path text,
  depth int, ordinal int, has_rulespec boolean DEFAULT false
);
-- us/statute base: 53 titles, 60,393 sections.
INSERT INTO scale_rows
SELECT 'us', 'statute', '2026-04-29', 'us/statute/' || t, NULL, 0, t
FROM generate_series(1, 53) t;
INSERT INTO scale_rows
SELECT 'us', 'statute', '2026-04-29', 'us/statute/' || (1 + i % 53) || '/' || (i / 53 + 1),
       'us/statute/' || (1 + i % 53), 1, i / 53 + 1
FROM generate_series(0, 60392) i;
-- us/regulation base: 49 titles, 4,900 parts, 241,528 sections.
INSERT INTO scale_rows
SELECT 'us', 'regulation', '2026-05-01', 'us/regulation/' || t, NULL, 0, t
FROM generate_series(1, 49) t;
INSERT INTO scale_rows
SELECT 'us', 'regulation', '2026-05-01',
       'us/regulation/' || (1 + i % 49) || '/' || (i / 49 + 1),
       'us/regulation/' || (1 + i % 49), 1, i / 49 + 1
FROM generate_series(0, 4899) i;
INSERT INTO scale_rows
SELECT 'us', 'regulation', '2026-05-01',
       'us/regulation/' || (1 + p % 49) || '/' || (p / 49 + 1) || '/' || (p / 49 + 1)
         || '.' || (i / 4900 + 1),
       'us/regulation/' || (1 + p % 49) || '/' || (p / 49 + 1), 2, i / 4900 + 1
FROM generate_series(0, 241527) i, LATERAL (SELECT i % 4900 AS p) part;
-- 48 primary scopes of 300 rows; odd ones carry their title or part row.
INSERT INTO scale_rows
SELECT 'us', 'statute', '2026-09-' || lpad(k::text, 2, '0') || '-statute-' || k,
       'us/statute/' || (1 + k * 2) || '/' || CASE WHEN i < 290
         THEN (1000 + k * 300 + i)::text || 'x' ELSE (i - 289)::text END,
       CASE WHEN k % 2 = 1 THEN 'us/statute/' || (1 + k * 2) END,
       CASE WHEN k % 2 = 1 THEN 1 ELSE 0 END, i
FROM generate_series(0, 23) k, generate_series(0, 298) i;
INSERT INTO scale_rows
SELECT 'us', 'statute', '2026-09-' || lpad(k::text, 2, '0') || '-statute-' || k,
       'us/statute/' || (1 + k * 2), NULL, 0, 1
FROM generate_series(0, 23) k WHERE k % 2 = 1;
INSERT INTO scale_rows
SELECT 'us', 'regulation', '2026-09-' || lpad(k::text, 2, '0') || '-regulation-' || k,
       'us/regulation/' || (1 + k * 2) || '/' || (k + 1) || '/' || (k + 1) || '.'
         || CASE WHEN i < 290 THEN (1000 + i)::text ELSE (i - 289)::text END,
       CASE WHEN k % 2 = 1 THEN 'us/regulation/' || (1 + k * 2) || '/' || (k + 1) END,
       CASE WHEN k % 2 = 1 THEN 1 ELSE 0 END, i
FROM generate_series(0, 23) k, generate_series(0, 298) i;
INSERT INTO scale_rows
SELECT 'us', 'regulation', '2026-09-' || lpad(k::text, 2, '0') || '-regulation-' || k,
       'us/regulation/' || (1 + k * 2) || '/' || (k + 1), NULL, 0, 1
FROM generate_series(0, 23) k WHERE k % 2 = 1;
UPDATE scale_rows SET has_rulespec = true
WHERE version LIKE '2026-09-%' AND ordinal % 7 = 0;
-- Superseded us history and other jurisdictions (half served, half stored).
INSERT INTO scale_rows
SELECT 'us', 'statute', '2026-0' || (1 + v % 6) || '-history-' || v,
       'us/statute/' || (1 + i % 53) || '/' || (i / 53 + 1),
       'us/statute/' || (1 + i % 53), 1, i
FROM generate_series(0, {history_versions} - 1) v,
     generate_series(v * 1000, v * 1000 + {history_rows} - 1) i;
INSERT INTO scale_rows
SELECT 'x' || j, 'statute', CASE WHEN h = 0 THEN 'served' ELSE 'stored' END,
       'x' || j || '/statute/' || (i / 100) || CASE WHEN i % 100 = 0 THEN ''
         ELSE '/' || (i % 100) END,
       CASE WHEN i % 100 = 0 THEN NULL ELSE 'x' || j || '/statute/' || (i / 100) END,
       CASE WHEN i % 100 = 0 THEN 0 ELSE 1 END, i
FROM generate_series(1, {others}) j, generate_series(0, 1) h,
     generate_series(0, {other_rows} - 1) i;

INSERT INTO corpus.provisions (id, citation_path, jurisdiction, doc_type, version, body,
  parent_id, level, ordinal, heading, source_path, expression_date, has_rulespec)
SELECT md5('p' || version || path)::uuid, path, jurisdiction, doc_type, version,
       repeat(md5(path), 12),
       CASE WHEN parent_path IS NOT NULL THEN md5('p' || version || parent_path)::uuid END,
       depth, ordinal, 'Heading ' || path, 'sources/' || jurisdiction || '/' || version,
       DATE '2026-01-01', has_rulespec
FROM scale_rows;
INSERT INTO corpus.navigation_nodes (id, jurisdiction, doc_type, path, parent_path, segment,
  label, sort_key, depth, provision_id, citation_path, has_children, child_count,
  has_rulespec, encoded_descendant_count, status, version)
SELECT md5('n' || r.version || r.path), r.jurisdiction, r.doc_type, r.path, r.parent_path,
       regexp_replace(r.path, '^.*/', ''), 'Heading ' || r.path,
       lpad(r.ordinal::text, 8, '0') || '|' || regexp_replace(r.path, '^.*/', ''),
       r.depth, md5('p' || r.version || r.path)::uuid::text, r.path,
       COALESCE(c.n, 0) > 0, COALESCE(c.n, 0), r.has_rulespec, 0, NULL, r.version
FROM scale_rows r
LEFT JOIN (
  SELECT version, parent_path, COUNT(*)::int AS n
  FROM scale_rows WHERE parent_path IS NOT NULL GROUP BY 1, 2
) c ON c.version = r.version AND c.parent_path = r.path;

-- Membership is checked against the signed scope list of its release object.
INSERT INTO corpus.release_objects (release_name, content_sha256, release_object)
SELECT release_name, content_sha256,
       jsonb_build_object('content', jsonb_build_object('created_at', created_at, 'scopes', scopes))
FROM (
  SELECT 'scale-served' AS release_name, repeat('a', 64) AS content_sha256,
         '2026-10-01T00:00:00Z' AS created_at,
         jsonb_agg(
           jsonb_build_object('jurisdiction', jurisdiction, 'document_class', doc_type,
                              'version', version)
           || CASE WHEN version IN ('2026-04-29', '2026-05-01')
                THEN jsonb_build_object('layer', 'base') ELSE '{}'::jsonb END
         ) AS scopes
  FROM (SELECT DISTINCT jurisdiction, doc_type, version FROM scale_rows
        WHERE version NOT LIKE '%history%' AND version <> 'stored') served
  UNION ALL
  SELECT 'scale-history', repeat('b', 64), '2026-01-01T00:00:00Z',
         jsonb_agg(jsonb_build_object('jurisdiction', jurisdiction, 'document_class', doc_type,
                                      'version', version))
  FROM (SELECT DISTINCT jurisdiction, doc_type, version FROM scale_rows
        WHERE version LIKE '%history%' OR version = 'stored') history
) objects;
INSERT INTO corpus.release_scopes (release_name, jurisdiction, document_class, version, layer)
SELECT DISTINCT 'scale-served', jurisdiction, doc_type, version,
       CASE WHEN version IN ('2026-04-29', '2026-05-01') THEN 'base' ELSE 'primary' END
FROM scale_rows WHERE version NOT LIKE '%history%' AND version <> 'stored';
INSERT INTO corpus.release_scopes (release_name, jurisdiction, document_class, version)
SELECT DISTINCT 'scale-history', jurisdiction, doc_type, version
FROM scale_rows WHERE version LIKE '%history%' OR version = 'stored';
"""
# Serving the release fires sync_layered_serving for every pair: the layered
# state of us/statute and us/regulation is derived here, as activation would.
_SCALE_SERVE = """
INSERT INTO corpus.active_scope_pointer (jurisdiction, document_class, release_name,
  content_sha256)
SELECT DISTINCT jurisdiction, document_class, 'scale-served', repeat('a', 64)
FROM corpus.release_scopes WHERE release_name = 'scale-served';
"""

_PLAN_REQUESTS = {
    "current_provisions?citation_path=eq.<base-only path>": (
        "SELECT * FROM corpus.current_provisions WHERE citation_path = 'us/statute/30/500'"
    ),
    "current_provisions?citation_path=eq.<collision path>": (
        "SELECT * FROM corpus.current_provisions WHERE citation_path = 'us/statute/3/1'"
    ),
    "current_navigation_nodes?jurisdiction=eq.us&order=citation_path.asc&limit=1000": (
        "SELECT jurisdiction, doc_type, citation_path, has_children, child_count, has_rulespec, "
        "version FROM corpus.current_navigation_nodes WHERE jurisdiction = 'us' "
        "ORDER BY citation_path LIMIT 1000"
    ),
    "current_navigation_nodes?parent_path=eq.us/statute/2&order=sort_key (merged children)": (
        "SELECT * FROM corpus.current_navigation_nodes WHERE jurisdiction = 'us' "
        "AND doc_type = 'statute' AND parent_path = 'us/statute/2' ORDER BY sort_key LIMIT 100"
    ),
    # SupabaseQuery.get_section_with_children's page of a layered title's children.
    "current_navigation_nodes?select=provision_id&parent_path=eq.us/statute/2"
    "&order=sort_key,path,id&limit=1000 (client children page)": (
        "SELECT provision_id FROM corpus.current_navigation_nodes WHERE jurisdiction = 'us' "
        "AND parent_path = 'us/statute/2' AND doc_type = 'statute' "
        "ORDER BY sort_key, path, id LIMIT 1000 OFFSET 0"
    ),
    "rpc/get_root_document_counts": "SELECT * FROM corpus.get_root_document_counts()",
    "navigation_nodes?parent_path=eq.us/statute/3 (direct read, anon policy)": (
        "SELECT * FROM corpus.navigation_nodes WHERE jurisdiction = 'us' "
        "AND doc_type = 'statute' AND parent_path = 'us/statute/3' ORDER BY sort_key LIMIT 100"
    ),
}


@pytest.fixture(scope="module")
def scale_dsn() -> Iterator[str]:
    yield from _create_database(layered=True)


def _plan_nodes(plan: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    yield plan
    for child in plan.get("Plans", ()):
        yield from _plan_nodes(child)


def test_serving_plans_stay_index_driven_at_representative_scale(scale_dsn: str) -> None:
    with closing(psycopg2.connect(scale_dsn)) as connection:
        with connection.cursor() as cursor:
            scale_sql = _SCALE_ROWS
            for name, value in _SCALE.items():
                scale_sql = scale_sql.replace("{" + name + "}", str(value))
            cursor.execute(scale_sql)
        connection.commit()
        connection.autocommit = True
        with connection.cursor() as cursor:
            # Staged rows are analyzed long before activation in production.
            cursor.execute("VACUUM ANALYZE")
            started = time.monotonic()
            cursor.execute(_SCALE_SERVE)
            derivation_seconds = time.monotonic() - started
            cursor.execute("VACUUM ANALYZE")
            cursor.execute("SELECT COUNT(*) FROM corpus.provisions")
            (provision_rows,) = cursor.fetchone()
            cursor.execute(
                "SELECT COUNT(*) FROM corpus.provisions WHERE version IN ('2026-04-29', '2026-05-01')"
            )
            (base_rows,) = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM corpus.layered_shadowed_rows")
            (shadowed,) = cursor.fetchone()
        connection.autocommit = False
        assert base_rows == 306_923
        assert provision_rows >= 300_000
        assert shadowed == 456

        plans: dict[str, list[Mapping[str, Any]]] = {}
        report: list[str] = []
        with _as_role(connection, "anon") as cursor:
            cursor.execute("SET statement_timeout = '3s'")
            for request, query in _PLAN_REQUESTS.items():
                cursor.execute("EXPLAIN (FORMAT JSON) " + query)
                plans[request] = list(_plan_nodes(cursor.fetchone()[0][0]["Plan"]))
                cursor.execute("EXPLAIN (ANALYZE, BUFFERS) " + query)
                report.append(
                    f"### {request}\n\n```\n"
                    + "\n".join(row[0] for row in cursor.fetchall())
                    + "\n```\n"
                )

        for request in list(_PLAN_REQUESTS)[:2]:
            nodes = plans[request]
            # An index scan, or a bitmap scan of the same index: the planner
            # picks between them by a narrow cost margin.
            index_scans = [
                n
                for n in nodes
                if n["Node Type"] in {"Index Scan", "Bitmap Index Scan"}
                and n.get("Index Name") == "idx_provisions_citation_path_version"
            ]
            assert index_scans, request
            assert not any(
                n["Node Type"] == "Seq Scan" and n.get("Relation Name") == "provisions"
                for n in nodes
            ), request
            assert not any(n["Node Type"] in {"Sort", "WindowAgg"} for n in nodes), request
        children = plans[
            "current_navigation_nodes?select=provision_id&parent_path=eq.us/statute/2"
            "&order=sort_key,path,id&limit=1000 (client children page)"
        ]
        assert not any(
            n["Node Type"] == "Seq Scan" and n.get("Relation Name") == "navigation_nodes"
            for n in children
        )
        page = plans[
            "current_navigation_nodes?jurisdiction=eq.us&order=citation_path.asc&limit=1000"
        ]
        assert page[0]["Node Type"] == "Limit"
        assert page[1]["Node Type"] == "Merge Append"
        assert not any(
            n["Node Type"] == "Seq Scan" and n.get("Relation Name") == "navigation_nodes"
            for n in page
        )
        report_path = os.environ.get("AXIOM_CORPUS_PLAN_REPORT")
        if report_path:
            Path(report_path).write_text(
                f"{provision_rows} provision rows, {base_rows} base rows, {shadowed} shadowed; "
                f"serving the release derived the layered state in {derivation_seconds:.1f} s.\n\n"
                + "\n".join(report),
                encoding="utf-8",
            )
