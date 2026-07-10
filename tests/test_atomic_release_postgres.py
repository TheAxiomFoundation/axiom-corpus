"""Behavioral PostgreSQL coverage for atomic named-release activation.

These tests deliberately apply the checked-in migration to a small schema that
matches the state immediately before the hard cut.  Unit tests that inspect the
SQL text cannot prove transaction rollback, lock lifetime, privileges, or
trigger behavior; this module exercises those properties in PostgreSQL itself.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import uuid
from collections.abc import Iterator, Mapping
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.navigation import build_navigation_nodes
from axiom_corpus.corpus.projection_digest import (
    navigation_projection_sha256,
    provision_projection_sha256,
)
from axiom_corpus.corpus.supabase import iter_supabase_rows
from axiom_corpus.release.manifest import verify_release_object

psycopg2 = pytest.importorskip("psycopg2")
errors = pytest.importorskip("psycopg2.errors")
sql = pytest.importorskip("psycopg2.sql")
Json = pytest.importorskip("psycopg2.extras").Json


DATABASE_URL = os.environ.get("DATABASE_URL")
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase/migrations/20260710180000_atomic_named_release_activation.sql"
)
REQUIRED_ROLES = ("anon", "authenticated", "service_role", "postgres")
TEST_SIGNING_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
TEST_PUBLIC_KEY = base64.b64encode(
    TEST_SIGNING_KEY.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
).decode()

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for PostgreSQL migration integration tests",
)


PRE_MIGRATION_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA corpus;
GRANT USAGE ON SCHEMA corpus TO anon, authenticated, service_role;

CREATE TABLE corpus.provisions (
  id uuid PRIMARY KEY,
  citation_path text NOT NULL,
  jurisdiction text NOT NULL,
  doc_type text NOT NULL,
  version text,
  body text,
  parent_id uuid,
  level integer,
  ordinal integer,
  heading text,
  source_url text,
  source_path text,
  rulespec_path text,
  has_rulespec boolean NOT NULL DEFAULT false,
  source_document_id uuid,
  source_as_of date,
  expression_date date,
  language text,
  legal_identifier text,
  identifiers jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT provisions_citation_path_unique UNIQUE (citation_path)
);

CREATE TABLE corpus.navigation_nodes (
  id text PRIMARY KEY,
  jurisdiction text NOT NULL,
  doc_type text NOT NULL,
  path text NOT NULL,
  parent_path text,
  segment text NOT NULL,
  label text NOT NULL,
  sort_key text NOT NULL,
  depth integer NOT NULL,
  provision_id uuid,
  citation_path text,
  has_children boolean NOT NULL DEFAULT false,
  child_count integer NOT NULL DEFAULT 0,
  has_rulespec boolean NOT NULL DEFAULT false,
  encoded_descendant_count integer NOT NULL DEFAULT 0,
  status text,
  version text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_navigation_nodes_path ON corpus.navigation_nodes (path);

-- Historical migrations granted the staging role every table privilege. The
-- hard-cut migration must remove TRUNCATE while preserving row-level staging.
GRANT ALL ON corpus.provisions, corpus.navigation_nodes TO service_role;

CREATE TABLE corpus.release_scopes (
  release_name text NOT NULL,
  jurisdiction text NOT NULL,
  document_class text NOT NULL,
  version text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  synced_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (release_name, jurisdiction, document_class, version)
);
ALTER TABLE corpus.release_scopes ENABLE ROW LEVEL SECURITY;
GRANT ALL ON corpus.release_scopes TO service_role;

CREATE POLICY release_scopes_anon_read
  ON corpus.release_scopes FOR SELECT TO anon USING (active IS TRUE);
CREATE POLICY release_scopes_authenticated_read
  ON corpus.release_scopes FOR SELECT TO authenticated USING (active IS TRUE);

CREATE VIEW corpus.current_release_scopes AS
SELECT release_name, jurisdiction, document_class, version, synced_at
FROM corpus.release_scopes
WHERE release_name = 'current' AND active IS TRUE;

CREATE VIEW corpus.current_provisions AS
SELECT provisions.*
FROM corpus.provisions provisions
WHERE EXISTS (
  SELECT 1
  FROM corpus.current_release_scopes scopes
  WHERE scopes.jurisdiction = provisions.jurisdiction
    AND scopes.document_class = COALESCE(NULLIF(provisions.doc_type, ''), 'unknown')
    AND scopes.version = provisions.version
);

CREATE MATERIALIZED VIEW corpus.current_provision_counts AS
SELECT
  jurisdiction,
  COALESCE(NULLIF(doc_type, ''), 'unknown') AS document_class,
  COUNT(*)::bigint AS provision_count,
  COUNT(*) FILTER (WHERE body IS NOT NULL AND BTRIM(body) <> '')::bigint AS body_count,
  COUNT(*) FILTER (WHERE parent_id IS NULL)::bigint AS top_level_count,
  COUNT(*) FILTER (WHERE has_rulespec IS TRUE)::bigint AS rulespec_count,
  now() AS refreshed_at
FROM corpus.current_provisions
WHERE jurisdiction IS NOT NULL
GROUP BY jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown')
WITH NO DATA;

-- Both mutable aliases and older unsigned named memberships existed before
-- this migration. The hard cut must remove all of them before adding the FK
-- from release_scopes to signed release_objects.
INSERT INTO corpus.release_scopes (
  release_name, jurisdiction, document_class, version, active
) VALUES
  ('current', 'legacy-current', 'statute', '2025-01-01', true),
  ('unsigned-legacy', 'legacy-named', 'statute', '2025-01-01', false);
"""


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _artifact(
    artifact_class: str,
    path: str,
    *,
    rows: int | None = None,
) -> dict[str, Any]:
    raw = f"test artifact: {path}\n".encode()
    digest = hashlib.sha256(raw).hexdigest()
    artifact: dict[str, Any] = {
        "artifact_class": artifact_class,
        "path": path,
        "sha256": digest,
        "bytes": len(raw),
        "r2_bucket": "axiom-corpus",
        "r2_key": f"objects/sha256/{digest[:2]}/{digest}",
    }
    if rows is not None:
        artifact["rows"] = rows
    return artifact


def _release_object(
    release_name: str,
    scope: Mapping[str, Any],
) -> dict[str, Any]:
    jurisdiction = str(scope["jurisdiction"])
    document_class = str(scope["document_class"])
    version = str(scope["version"])
    rows = int(scope["provision_rows"])
    base = f"{jurisdiction}/{document_class}/{version}"
    artifacts = sorted(
        [
            _artifact("coverage", f"data/corpus/coverage/{base}.json"),
            _artifact("inventory", f"data/corpus/inventory/{base}.json"),
            _artifact("provisions", f"data/corpus/provisions/{base}.jsonl", rows=rows),
            _artifact("sources", f"data/corpus/sources/{base}/source.txt"),
        ],
        key=lambda artifact: str(artifact["path"]),
    )
    selector = {
        "name": release_name,
        "scopes": [
            {field: scope[field] for field in ("jurisdiction", "document_class", "version")}
        ],
    }
    content = {
        "release": release_name,
        "created_at": "2026-07-10T00:00:00Z",
        "selector_sha256": hashlib.sha256(_canonical_json_bytes(selector)).hexdigest(),
        "corpus_base": "data/corpus",
        "git": {
            "commit": "a" * 40,
            "committed_at": "2026-07-10T00:00:00Z",
        },
        "r2": {"bucket": "axiom-corpus", "addressing": "sha256"},
        "scopes": [dict(scope)],
        "artifacts": artifacts,
        "validation": {
            "passed": True,
            "deep_validation": {
                "error_count": 0,
                "warning_count": 0,
                "scope_count": 1,
            },
            "r2_readback": {
                "bucket": "axiom-corpus",
                "artifact_count": len(artifacts),
                "artifact_bytes": sum(int(artifact["bytes"]) for artifact in artifacts),
                "verified_keys": [artifact["r2_key"] for artifact in artifacts],
            },
            "supabase_projection_evidence": [
                {
                    "jurisdiction": jurisdiction,
                    "document_class": document_class,
                    "version": version,
                    "expected": rows,
                    "actual": rows,
                    "expected_navigation": int(scope["navigation_rows"]),
                    "actual_navigation": int(scope["navigation_rows"]),
                    "expected_provision_projection_sha256": scope["provision_projection_sha256"],
                    "actual_provision_projection_sha256": scope["provision_projection_sha256"],
                    "expected_navigation_projection_sha256": scope["navigation_projection_sha256"],
                    "actual_navigation_projection_sha256": scope["navigation_projection_sha256"],
                }
            ],
        },
    }
    unsigned = {
        "schema_version": "axiom-corpus/release-object/v2",
        "release": release_name,
        "content_sha256": hashlib.sha256(_canonical_json_bytes(content)).hexdigest(),
        "content": content,
    }
    signature = TEST_SIGNING_KEY.sign(_canonical_json_bytes(unsigned))
    return {
        **unsigned,
        "signature": {
            "algorithm": "ed25519",
            "key_id": "axiom-corpus-release-v2",
            "value": base64.b64encode(signature).decode(),
        },
    }


@pytest.fixture(scope="module")
def postgres_dsn() -> Iterator[str]:
    assert DATABASE_URL is not None
    database_name = f"axiom_atomic_release_{uuid.uuid4().hex}"
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
                    cursor.execute(PRE_MIGRATION_SCHEMA)
                    cursor.execute(MIGRATION.read_text(encoding="utf-8"))
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


def _reset_database(dsn: str) -> None:
    with closing(psycopg2.connect(dsn)) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE TABLE
              corpus.active_release_pointer,
              corpus.release_scopes,
              corpus.release_objects,
              corpus.provisions,
              corpus.navigation_nodes
            """
        )
        cursor.execute("REFRESH MATERIALIZED VIEW corpus.current_provision_counts")
        connection.commit()


@pytest.fixture
def clean_postgres(postgres_dsn: str) -> Iterator[str]:
    _reset_database(postgres_dsn)
    yield postgres_dsn
    _reset_database(postgres_dsn)


def _scope_identity(token: str) -> dict[str, str]:
    return {
        "jurisdiction": f"test-{token}",
        "document_class": "statute",
        "version": "2026-07-10",
    }


def _scope_projection_rows(
    identity: Mapping[str, str],
) -> tuple[dict[str, object], dict[str, object]]:
    token = hashlib.sha256(_canonical_json_bytes(identity)).hexdigest()[:12]
    citation_path = f"{identity['jurisdiction']}/statute/{token}"
    provision_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"provision:{token}")).upper()
    parent_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"parent:{token}")).upper()
    source_document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"source:{token}")).upper()
    record = ProvisionRecord(
        id=provision_id,
        jurisdiction=identity["jurisdiction"],
        document_class=identity["document_class"],
        citation_path=citation_path,
        parent_citation_path=f"{identity['jurisdiction']}/statute/parent",
        parent_id=parent_id,
        version=identity["version"],
        body="Original signed projection — π\nV3:x",
        source_url="https://example.test/source",
        source_path=f"sources/{identity['jurisdiction']}/statute/2026/source.txt",
        source_document_id=source_document_id,
        source_as_of="2026-07-10T23:00:00Z",
        expression_date="2026-07-11T01:02:03+02:00",
        ordinal=10_701_001_001,
        identifiers={"label": "π"},
        legal_identifier="Test § 1",
    )
    provision_row = next(iter_supabase_rows((record,)))
    navigation_row = build_navigation_nodes((record,))[0].to_supabase_row()
    return provision_row, navigation_row


def _insert_projection_row(cursor: Any, table: str, row: Mapping[str, object]) -> None:
    columns = tuple(row)
    query = sql.SQL("INSERT INTO corpus.{} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.SQL(", ").join(sql.Placeholder() for _column in columns),
    )
    values = tuple(Json(value) if isinstance(value, dict) else value for value in row.values())
    cursor.execute(query, values)


def _seed_scope(connection: Any, identity: Mapping[str, str]) -> None:
    provision_row, navigation_row = _scope_projection_rows(identity)
    with connection.cursor() as cursor:
        _insert_projection_row(cursor, "provisions", provision_row)
        _insert_projection_row(cursor, "navigation_nodes", navigation_row)


def _scope_evidence(connection: Any, identity: Mapping[str, str]) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              jurisdiction,
              document_class,
              version,
              provision_count,
              navigation_count,
              provision_projection_sha256,
              navigation_projection_sha256
            FROM corpus.get_staged_release_scope_evidence(%s::jsonb)
            """,
            (Json([dict(identity)]),),
        )
        row = cursor.fetchone()
    assert row is not None
    return {
        "jurisdiction": row[0],
        "document_class": row[1],
        "version": row[2],
        "provision_rows": row[3],
        "navigation_rows": row[4],
        "provision_projection_sha256": row[5],
        "navigation_projection_sha256": row[6],
    }


def _activate(connection: Any, release_object: Mapping[str, Any]) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT corpus.activate_corpus_release(%s::jsonb)",
            (Json(dict(release_object)),),
        )
        result = cursor.fetchone()
    assert result is not None
    assert isinstance(result[0], dict)
    return result[0]


def _active_pointer(connection: Any) -> tuple[str, str] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT release_name, content_sha256 "
            "FROM corpus.active_release_pointer WHERE pointer_name = 'production'"
        )
        row = cursor.fetchone()
    return None if row is None else (str(row[0]), str(row[1]))


def _release_database_snapshot(connection: Any) -> tuple[tuple[Any, ...], ...]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT release_name, content_sha256, release_object, created_at
            FROM corpus.release_objects
            ORDER BY release_name
            """
        )
        release_objects = tuple(cursor.fetchall())
        cursor.execute(
            """
            SELECT release_name, jurisdiction, document_class, version, synced_at
            FROM corpus.release_scopes
            ORDER BY release_name, jurisdiction, document_class, version
            """
        )
        release_scopes = tuple(cursor.fetchall())
        cursor.execute(
            """
            SELECT pointer_name, release_name, content_sha256, activated_at
            FROM corpus.active_release_pointer
            ORDER BY pointer_name
            """
        )
        active_pointer = tuple(cursor.fetchall())
        cursor.execute(
            """
            SELECT jurisdiction, document_class, provision_count, body_count,
                   top_level_count, rulespec_count, refreshed_at
            FROM corpus.current_provision_counts
            ORDER BY jurisdiction, document_class
            """
        )
        current_counts = tuple(cursor.fetchall())
    return release_objects, release_scopes, active_pointer, current_counts


def test_actual_migration_applies_and_removes_unsigned_pre_cut_memberships(
    postgres_dsn: str,
) -> None:
    with closing(psycopg2.connect(postgres_dsn)) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              to_regclass('corpus.release_objects'),
              to_regclass('corpus.active_release_pointer'),
              to_regprocedure('corpus.activate_corpus_release(jsonb)'),
              to_regprocedure('corpus.get_staged_release_scope_evidence(jsonb)')
            """
        )
        assert all(value is not None for value in cursor.fetchone())
        cursor.execute("SELECT COUNT(*) FROM corpus.release_scopes")
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = 'corpus'
              AND table_name = 'release_scopes'
              AND column_name = 'active'
            """
        )
        assert cursor.fetchone()[0] == 0


def test_python_and_postgres_projection_digest_contracts_are_byte_identical(
    clean_postgres: str,
) -> None:
    identity = _scope_identity("digest-parity")
    provision_row, navigation_row = _scope_projection_rows(identity)
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        evidence = _scope_evidence(connection, identity)

    assert evidence["provision_projection_sha256"] == provision_projection_sha256([provision_row])
    assert evidence["navigation_projection_sha256"] == navigation_projection_sha256(
        [navigation_row]
    )


def test_postgres_release_fixture_satisfies_the_python_v2_verifier(
    clean_postgres: str,
) -> None:
    identity = _scope_identity("python-verifier")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        release_object = _release_object(
            "python-verifier-release",
            _scope_evidence(connection, identity),
        )

    verify_release_object(release_object, public_key=TEST_PUBLIC_KEY)


def test_count_mismatch_rolls_back_object_membership_and_active_pointer(
    clean_postgres: str,
) -> None:
    with closing(psycopg2.connect(clean_postgres)) as connection:
        baseline_identity = _scope_identity("baseline")
        _seed_scope(connection, baseline_identity)
        baseline = _release_object(
            "baseline-release",
            _scope_evidence(connection, baseline_identity),
        )
        _activate(connection, baseline)
        connection.commit()
        baseline_pointer = _active_pointer(connection)

        candidate_identity = _scope_identity("count-mismatch")
        _seed_scope(connection, candidate_identity)
        candidate_scope = _scope_evidence(connection, candidate_identity)
        candidate_scope["provision_rows"] = 2
        candidate_scope["navigation_rows"] = 2
        candidate = _release_object("count-mismatch-release", candidate_scope)
        with pytest.raises(errors.RaiseException, match="row-count mismatch"):
            _activate(connection, candidate)
        connection.rollback()

        assert _active_pointer(connection) == baseline_pointer
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM corpus.release_objects "
                "WHERE release_name = 'count-mismatch-release'"
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "SELECT COUNT(*) FROM corpus.release_scopes "
                "WHERE release_name = 'count-mismatch-release'"
            )
            assert cursor.fetchone()[0] == 0


@pytest.mark.parametrize(
    ("table", "mutation"),
    [
        ("provisions", "UPDATE corpus.provisions SET body = 'Substituted body'"),
        ("navigation_nodes", "UPDATE corpus.navigation_nodes SET label = 'Substituted label'"),
    ],
)
def test_same_count_projection_substitution_cannot_activate(
    clean_postgres: str,
    table: str,
    mutation: str,
) -> None:
    identity = _scope_identity(f"substitution-{table}")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        release_object = _release_object(
            f"substitution-{table.replace('_', '-')}",
            _scope_evidence(connection, identity),
        )
        with connection.cursor() as cursor:
            cursor.execute(f"{mutation} WHERE jurisdiction = %s", (identity["jurisdiction"],))
        connection.commit()

        with pytest.raises(errors.RaiseException, match="projection digest mismatch"):
            _activate(connection, release_object)
        connection.rollback()

        assert _active_pointer(connection) is None
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM corpus.release_objects WHERE release_name = %s",
                (release_object["release"],),
            )
            assert cursor.fetchone()[0] == 0


def test_activation_holds_write_locks_until_commit_then_rejects_scope_mutation(
    clean_postgres: str,
) -> None:
    identity = _scope_identity("locked")
    with closing(psycopg2.connect(clean_postgres)) as setup:
        _seed_scope(setup, identity)
        release_object = _release_object("locked-release", _scope_evidence(setup, identity))
        setup.commit()

    first = psycopg2.connect(clean_postgres)
    second = psycopg2.connect(clean_postgres)
    try:
        _activate(first, release_object)
        with first.cursor() as cursor:
            cursor.execute(
                """
                SELECT mode
                FROM pg_locks
                WHERE pid = pg_backend_pid()
                  AND relation IN (
                    'corpus.provisions'::regclass,
                    'corpus.navigation_nodes'::regclass
                  )
                  AND granted
                """
            )
            assert [row[0] for row in cursor.fetchall()].count("ShareLock") == 2

        with second.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '250ms'")
            with pytest.raises(errors.LockNotAvailable):
                cursor.execute(
                    "UPDATE corpus.provisions SET body = %s WHERE jurisdiction = %s",
                    ("Same row count, substituted content", identity["jurisdiction"]),
                )
        second.rollback()

        first.commit()

        with second.cursor() as cursor:
            with pytest.raises(errors.RaiseException, match="immutable corpus release"):
                cursor.execute(
                    "UPDATE corpus.provisions SET body = %s WHERE jurisdiction = %s",
                    ("Post-commit substitution", identity["jurisdiction"]),
                )
        second.rollback()
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize("table", ["provisions", "navigation_nodes"])
@pytest.mark.parametrize("operation", ["insert", "update", "delete"])
def test_post_commit_dml_against_a_released_scope_is_rejected(
    clean_postgres: str,
    table: str,
    operation: str,
) -> None:
    identity = _scope_identity(f"immutable-{table}-{operation}")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        _activate(
            connection,
            _release_object(
                f"immutable-{table.replace('_', '-')}-{operation}",
                _scope_evidence(connection, identity),
            ),
        )
        connection.commit()
        token = hashlib.sha256(_canonical_json_bytes(identity)).hexdigest()[:12]
        with connection.cursor() as cursor:
            with pytest.raises(errors.RaiseException, match="immutable corpus release"):
                if table == "provisions":
                    if operation == "insert":
                        cursor.execute(
                            """
                            INSERT INTO corpus.provisions (
                              id, citation_path, jurisdiction, doc_type, version, body
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                str(uuid.uuid5(uuid.NAMESPACE_URL, f"inserted:{token}")),
                                f"{identity['jurisdiction']}/statute/inserted-{token}",
                                identity["jurisdiction"],
                                identity["document_class"],
                                identity["version"],
                                "Unsigned addition",
                            ),
                        )
                    elif operation == "update":
                        cursor.execute(
                            "UPDATE corpus.provisions SET body = 'Unsigned rewrite' "
                            "WHERE jurisdiction = %s",
                            (identity["jurisdiction"],),
                        )
                    else:
                        cursor.execute(
                            "DELETE FROM corpus.provisions WHERE jurisdiction = %s",
                            (identity["jurisdiction"],),
                        )
                else:
                    if operation == "insert":
                        cursor.execute(
                            """
                            INSERT INTO corpus.navigation_nodes (
                              id, jurisdiction, doc_type, path, segment, label,
                              sort_key, depth, citation_path, version
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
                            """,
                            (
                                f"inserted-navigation-{token}",
                                identity["jurisdiction"],
                                identity["document_class"],
                                f"{identity['jurisdiction']}/statute/inserted-{token}",
                                token,
                                "Unsigned addition",
                                token,
                                f"{identity['jurisdiction']}/statute/inserted-{token}",
                                identity["version"],
                            ),
                        )
                    elif operation == "update":
                        cursor.execute(
                            "UPDATE corpus.navigation_nodes SET label = 'Unsigned rewrite' "
                            "WHERE jurisdiction = %s",
                            (identity["jurisdiction"],),
                        )
                    else:
                        cursor.execute(
                            "DELETE FROM corpus.navigation_nodes WHERE jurisdiction = %s",
                            (identity["jurisdiction"],),
                        )
        connection.rollback()


def test_retrying_the_identical_signed_object_is_idempotent(clean_postgres: str) -> None:
    identity = _scope_identity("retry")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        release_object = _release_object("retry-release", _scope_evidence(connection, identity))
        first_result = _activate(connection, release_object)
        connection.commit()
        first_snapshot = _release_database_snapshot(connection)
        second_result = _activate(connection, release_object)
        connection.commit()

        assert second_result == first_result
        assert _release_database_snapshot(connection) == first_snapshot
        assert _active_pointer(connection) == (
            "retry-release",
            release_object["content_sha256"],
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM corpus.release_objects WHERE release_name = 'retry-release'"
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                "SELECT COUNT(*) FROM corpus.release_scopes WHERE release_name = 'retry-release'"
            )
            assert cursor.fetchone()[0] == 1


def test_successor_release_can_reuse_an_identical_immutable_scope(clean_postgres: str) -> None:
    identity = _scope_identity("shared")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        evidence = _scope_evidence(connection, identity)
        predecessor = _release_object("shared-predecessor", evidence)
        successor = _release_object("shared-successor", evidence)
        _activate(connection, predecessor)
        connection.commit()
        _activate(connection, successor)
        connection.commit()

        assert _active_pointer(connection) == (
            "shared-successor",
            successor["content_sha256"],
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT release_name
                FROM corpus.release_scopes
                WHERE jurisdiction = %s AND document_class = %s AND version = %s
                ORDER BY release_name
                """,
                tuple(identity.values()),
            )
            assert [row[0] for row in cursor.fetchall()] == [
                "shared-predecessor",
                "shared-successor",
            ]


def test_idempotent_retry_rejects_extra_stored_membership(clean_postgres: str) -> None:
    identity = _scope_identity("membership")
    extra_identity = _scope_identity("unsigned-extra")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        release_object = _release_object(
            "membership-release",
            _scope_evidence(connection, identity),
        )
        _activate(connection, release_object)
        connection.commit()
        pointer = _active_pointer(connection)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO corpus.release_scopes (
                  release_name, jurisdiction, document_class, version
                ) VALUES (%s, %s, %s, %s)
                """,
                (
                    "membership-release",
                    extra_identity["jurisdiction"],
                    extra_identity["document_class"],
                    extra_identity["version"],
                ),
            )
        connection.commit()

        with pytest.raises(errors.RaiseException, match="membership differs"):
            _activate(connection, release_object)
        connection.rollback()
        assert _active_pointer(connection) == pointer


def test_mutable_current_name_cannot_move_the_pointer(clean_postgres: str) -> None:
    identity = _scope_identity("current")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        release_object = _release_object("current", _scope_evidence(connection, identity))
        with pytest.raises(errors.RaiseException, match="invalid immutable corpus release name"):
            _activate(connection, release_object)
        connection.rollback()
        assert _active_pointer(connection) is None


def test_service_role_cannot_submit_a_signature_shaped_invalid_object(
    clean_postgres: str,
) -> None:
    identity = _scope_identity("untrusted")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        invalid_object = copy.deepcopy(
            _release_object("untrusted-release", _scope_evidence(connection, identity))
        )
        invalid_object["signature"]["value"] = base64.b64encode(bytes(64)).decode()
        connection.commit()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_function_privilege("
                "'service_role', 'corpus.activate_corpus_release(jsonb)', 'EXECUTE')"
            )
            assert cursor.fetchone()[0] is False
            cursor.execute("SET ROLE service_role")
            with pytest.raises(errors.InsufficientPrivilege):
                cursor.execute(
                    "SELECT corpus.activate_corpus_release(%s::jsonb)",
                    (Json(invalid_object),),
                )
        connection.rollback()
        assert _active_pointer(connection) is None


@pytest.mark.parametrize(
    "table",
    ["provisions", "navigation_nodes", "release_scopes"],
)
def test_service_role_cannot_truncate_release_state(
    clean_postgres: str,
    table: str,
) -> None:
    with closing(psycopg2.connect(clean_postgres)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_table_privilege('service_role', %s, 'TRUNCATE')",
            (f"corpus.{table}",),
        )
        assert cursor.fetchone()[0] is False
        cursor.execute("SET ROLE service_role")
        with pytest.raises(errors.InsufficientPrivilege):
            cursor.execute(sql.SQL("TRUNCATE TABLE corpus.{}").format(sql.Identifier(table)))


def test_service_role_retains_only_unreleased_row_staging_dml(clean_postgres: str) -> None:
    identity = _scope_identity("service-staging")
    provision_row, navigation_row = _scope_projection_rows(identity)
    with closing(psycopg2.connect(clean_postgres)) as connection, connection.cursor() as cursor:
        for table in ("provisions", "navigation_nodes"):
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                cursor.execute(
                    "SELECT has_table_privilege('service_role', %s, %s)",
                    (f"corpus.{table}", privilege),
                )
                assert cursor.fetchone()[0] is True
        cursor.execute("SET ROLE service_role")
        _insert_projection_row(cursor, "provisions", provision_row)
        _insert_projection_row(cursor, "navigation_nodes", navigation_row)
        cursor.execute("RESET ROLE")
        cursor.execute(
            "SELECT COUNT(*) FROM corpus.provisions WHERE jurisdiction = %s",
            (identity["jurisdiction"],),
        )
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            "SELECT COUNT(*) FROM corpus.navigation_nodes WHERE jurisdiction = %s",
            (identity["jurisdiction"],),
        )
        assert cursor.fetchone()[0] == 1
