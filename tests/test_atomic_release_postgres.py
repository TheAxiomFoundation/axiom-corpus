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
import threading
import time
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
SCOPE_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase/migrations/20260718193000_scope_level_activation.sql"
)
PROFILED_RELEASE_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase/migrations/20260719043000_profiled_release_activation.sql"
)
COMPACT_RELEASE_OBJECTS_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase/migrations/20260721102000_compact_released_scope_objects.sql"
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
                    cursor.execute(SCOPE_MIGRATION.read_text(encoding="utf-8"))
                    cursor.execute(PROFILED_RELEASE_MIGRATION.read_text(encoding="utf-8"))
                    cursor.execute(COMPACT_RELEASE_OBJECTS_MIGRATION.read_text(encoding="utf-8"))
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
              corpus.scope_activation_history,
              corpus.active_scope_pointer,
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


def _profiled_release_object(release_object: Mapping[str, Any]) -> dict[str, Any]:
    profiled = copy.deepcopy(dict(release_object))
    content = profiled["content"]
    profile = "complete-expression-dates-v1"
    content["quality_profile"] = profile
    content["validation"]["quality_profile"] = profile
    selector = {
        "name": content["release"],
        "quality_profile": profile,
        "scopes": [
            {field: scope[field] for field in ("jurisdiction", "document_class", "version")}
            for scope in content["scopes"]
        ],
    }
    content["selector_sha256"] = hashlib.sha256(_canonical_json_bytes(selector)).hexdigest()
    unsigned = {
        "schema_version": "axiom-corpus/release-object/v3",
        "release": profiled["release"],
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


def test_profiled_release_fixture_verifies_and_activates(
    clean_postgres: str,
) -> None:
    identity = _scope_identity("profiled-v3")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        release_object = _profiled_release_object(
            _release_object(
                "profiled-v3-release",
                _scope_evidence(connection, identity),
            )
        )
        verify_release_object(release_object, public_key=TEST_PUBLIC_KEY)

        result = _activate(connection, release_object)
        connection.commit()

    assert result["active"] is True
    assert result["release"] == "profiled-v3-release"


@pytest.mark.parametrize("case", ["missing", "mismatch"])
def test_profiled_release_activation_rejects_invalid_quality_attestation(
    clean_postgres: str,
    case: str,
) -> None:
    identity = _scope_identity(f"profile-{case}")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        release_object = _profiled_release_object(
            _release_object(
                f"profile-{case}-release",
                _scope_evidence(connection, identity),
            )
        )
        if case == "missing":
            release_object["content"].pop("quality_profile")
        else:
            release_object["content"]["validation"]["quality_profile"] = "different-profile"

        with pytest.raises(
            psycopg2.Error,
            match="unsupported quality profile|validation quality profile does not match",
        ):
            _activate(connection, release_object)
        connection.rollback()
        assert _active_scope_map(connection) == {}


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

        # The first activation moves the scope; the identical retry reaffirms it
        # and changes nothing. Idempotency is now the reaffirm, not a byte-equal
        # response.
        assert len(first_result["scopes"]["activated"]) == 1
        assert first_result["scopes"]["reaffirmed"] == []
        assert second_result["scopes"]["activated"] == []
        assert len(second_result["scopes"]["reaffirmed"]) == 1
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


# ---------------------------------------------------------------------------
# Scope-level activation (20260718193000): serving follows a per-(jurisdiction,
# document_class) map, so activating one release no longer un-serves others.
# ---------------------------------------------------------------------------
def _versioned(identity: Mapping[str, str], version: str) -> dict[str, str]:
    return {**identity, "version": version}


def _multi_scope_release_object(
    release_name: str,
    scopes: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Sign a release object carrying several scopes (mirrors _release_object)."""
    artifacts: list[dict[str, Any]] = []
    projection_evidence: list[dict[str, Any]] = []
    for scope in scopes:
        jurisdiction = str(scope["jurisdiction"])
        document_class = str(scope["document_class"])
        version = str(scope["version"])
        rows = int(scope["provision_rows"])
        base = f"{jurisdiction}/{document_class}/{version}"
        artifacts.extend(
            [
                _artifact("coverage", f"data/corpus/coverage/{base}.json"),
                _artifact("inventory", f"data/corpus/inventory/{base}.json"),
                _artifact("provisions", f"data/corpus/provisions/{base}.jsonl", rows=rows),
                _artifact("sources", f"data/corpus/sources/{base}/source.txt"),
            ]
        )
        projection_evidence.append(
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
        )
    artifacts.sort(key=lambda artifact: str(artifact["path"]))
    selector = {
        "name": release_name,
        "scopes": [
            {field: scope[field] for field in ("jurisdiction", "document_class", "version")}
            for scope in scopes
        ],
    }
    content = {
        "release": release_name,
        "created_at": "2026-07-10T00:00:00Z",
        "selector_sha256": hashlib.sha256(_canonical_json_bytes(selector)).hexdigest(),
        "corpus_base": "data/corpus",
        "git": {"commit": "a" * 40, "committed_at": "2026-07-10T00:00:00Z"},
        "r2": {"bucket": "axiom-corpus", "addressing": "sha256"},
        "scopes": [dict(scope) for scope in scopes],
        "artifacts": artifacts,
        "validation": {
            "passed": True,
            "deep_validation": {
                "error_count": 0,
                "warning_count": 0,
                "scope_count": len(scopes),
            },
            "r2_readback": {
                "bucket": "axiom-corpus",
                "artifact_count": len(artifacts),
                "artifact_bytes": sum(int(artifact["bytes"]) for artifact in artifacts),
                "verified_keys": [artifact["r2_key"] for artifact in artifacts],
            },
            "supabase_projection_evidence": projection_evidence,
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


def _active_scope_map(connection: Any) -> dict[tuple[str, str], str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT jurisdiction, document_class, release_name FROM corpus.active_scope_pointer"
        )
        return {(r[0], r[1]): r[2] for r in cursor.fetchall()}


def _served_scope_keys(connection: Any) -> set[tuple[str, str, str]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT jurisdiction, document_class, version FROM corpus.current_release_scopes"
        )
        return {(r[0], r[1], r[2]) for r in cursor.fetchall()}


def _served_provision_jurisdictions(connection: Any) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT jurisdiction FROM corpus.current_provisions")
        return {str(r[0]) for r in cursor.fetchall()}


def _scope_history(connection: Any) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT jurisdiction, document_class, release_name, previous_release_name "
            "FROM corpus.scope_activation_history ORDER BY id"
        )
        return list(cursor.fetchall())


def test_activating_one_jurisdiction_leaves_other_jurisdictions_served(
    clean_postgres: str,
) -> None:
    alpha = _scope_identity("alpha")
    beta = _scope_identity("beta")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, alpha)
        _seed_scope(connection, beta)
        release_alpha = _release_object("alpha-release", _scope_evidence(connection, alpha))
        release_beta = _release_object("beta-release", _scope_evidence(connection, beta))

        _activate(connection, release_alpha)
        connection.commit()
        assert _served_provision_jurisdictions(connection) == {alpha["jurisdiction"]}

        # Activating a different jurisdiction must NOT un-serve alpha -- this is
        # the exact regression behind the 2026-07-18 "lost US content" incident.
        _activate(connection, release_beta)
        connection.commit()

        assert _served_provision_jurisdictions(connection) == {
            alpha["jurisdiction"],
            beta["jurisdiction"],
        }
        assert _served_scope_keys(connection) == {
            (alpha["jurisdiction"], "statute", alpha["version"]),
            (beta["jurisdiction"], "statute", beta["version"]),
        }
        assert _active_scope_map(connection) == {
            (alpha["jurisdiction"], "statute"): "alpha-release",
            (beta["jurisdiction"], "statute"): "beta-release",
        }


def test_one_release_serves_every_version_of_a_multi_version_pair(
    clean_postgres: str,
) -> None:
    # A single release legitimately carries many versions of one
    # (jurisdiction, document_class) pair (e.g. us/statute spans 15 versions in
    # us-rulespec-2026-07-17). The pointer names the release, and serving must
    # expose EVERY version the release carries for the pair -- not collapse to one.
    v1 = _scope_identity("multi")
    v2 = _versioned(v1, "2026-07-11")
    v3 = _versioned(v1, "2026-07-12")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        for scope in (v1, v2, v3):
            _seed_scope(connection, scope)
        release_object = _multi_scope_release_object(
            "multi-release",
            [_scope_evidence(connection, scope) for scope in (v1, v2, v3)],
        )
        result = _activate(connection, release_object)
        connection.commit()

        # One pointer row for the pair; all three versions served.
        assert _active_scope_map(connection) == {
            (v1["jurisdiction"], "statute"): "multi-release",
        }
        assert _served_scope_keys(connection) == {
            (v1["jurisdiction"], "statute", v1["version"]),
            (v1["jurisdiction"], "statute", v2["version"]),
            (v1["jurisdiction"], "statute", v3["version"]),
        }
        # The activation report is per pair (deduped across versions), not per scope.
        assert len(result["scopes"]["activated"]) == 1
        assert result["scope_count"] == 3


def test_overlapping_pair_last_activation_wins_and_records_history(
    clean_postgres: str,
) -> None:
    v1 = _scope_identity("gamma")
    v2 = _versioned(v1, "2026-07-11")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, v1)
        first = _release_object("gamma-v1", _scope_evidence(connection, v1))
        _activate(connection, first)
        connection.commit()
        assert _served_scope_keys(connection) == {(v1["jurisdiction"], "statute", v1["version"])}

        # A later release claiming the same (jurisdiction, document_class) takes
        # the pair over; the prior occupant release is recorded.
        _seed_scope(connection, v2)
        second = _release_object("gamma-v2", _scope_evidence(connection, v2))
        result = _activate(connection, second)
        connection.commit()

        assert _active_scope_map(connection) == {
            (v1["jurisdiction"], "statute"): "gamma-v2",
        }
        assert _served_scope_keys(connection) == {
            (v2["jurisdiction"], "statute", v2["version"]),
        }
        activated = result["scopes"]["activated"]
        assert len(activated) == 1
        assert activated[0]["displaced_release"] == "gamma-v1"
        history = _scope_history(connection)
        assert history[-1] == (
            v1["jurisdiction"],
            "statute",
            "gamma-v2",
            "gamma-v1",
        )


def test_reactivating_the_same_release_reaffirms_without_new_history(
    clean_postgres: str,
) -> None:
    identity = _scope_identity("delta")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        release_object = _release_object("delta-release", _scope_evidence(connection, identity))
        first = _activate(connection, release_object)
        connection.commit()
        assert len(first["scopes"]["activated"]) == 1
        assert first["scopes"]["reaffirmed"] == []
        history_after_first = _scope_history(connection)

        second = _activate(connection, release_object)
        connection.commit()
        assert second["scopes"]["activated"] == []
        assert len(second["scopes"]["reaffirmed"]) == 1
        # Re-affirming an unchanged pair writes no new history row.
        assert _scope_history(connection) == history_after_first


def test_preview_reports_takeover_without_moving_serving(clean_postgres: str) -> None:
    v1 = _scope_identity("epsilon")
    v2 = _versioned(v1, "2026-07-11")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, v1)
        first = _release_object("epsilon-v1", _scope_evidence(connection, v1))
        _activate(connection, first)
        connection.commit()
        _seed_scope(connection, v2)
        second = _release_object("epsilon-v2", _scope_evidence(connection, v2))

        pointer_before = _active_scope_map(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT jurisdiction, document_class, current_release_name, changes "
                "FROM corpus.preview_corpus_release_activation(%s::jsonb)",
                (Json(dict(second)),),
            )
            preview = cursor.fetchall()
        connection.commit()

        assert preview == [
            (v1["jurisdiction"], "statute", "epsilon-v1", True),
        ]
        # Preview is read-only: serving is untouched.
        assert _active_scope_map(connection) == pointer_before
        assert _served_scope_keys(connection) == {(v1["jurisdiction"], "statute", v1["version"])}


def test_concurrent_activations_serialize_and_record_true_displacement(
    clean_postgres: str,
) -> None:
    # Two activations racing on the same pair must serialize (the RPC takes an
    # EXCLUSIVE lock on active_scope_pointer), so the second reads the first's
    # committed release as its displaced occupant -- the append-only history
    # chain O -> A -> B stays accurate.
    pair = _scope_identity("nu")
    with closing(psycopg2.connect(clean_postgres)) as origin_conn:
        _seed_scope(origin_conn, pair)
        release_o = _release_object("nu-origin", _scope_evidence(origin_conn, pair))
        release_a = _release_object("nu-a", _scope_evidence(origin_conn, pair))
        release_b = _release_object("nu-b", _scope_evidence(origin_conn, pair))
        _activate(origin_conn, release_o)
        origin_conn.commit()

    barrier = threading.Event()
    errors_out: list[BaseException] = []
    b_pid: list[int] = []

    def activate_b() -> None:
        try:
            with closing(psycopg2.connect(clean_postgres)) as conn_b:
                with conn_b.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    b_pid.append(int(cursor.fetchone()[0]))
                barrier.wait(timeout=10)
                # Blocks on the EXCLUSIVE lock until conn_a commits, then reads A.
                _activate(conn_b, release_b)
                conn_b.commit()
        except BaseException as exc:  # noqa: BLE001 - surfaced to the test thread
            errors_out.append(exc)

    def _b_is_blocked_on_pointer_lock(observer: Any) -> bool:
        with observer.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM pg_locks locks
                WHERE locks.pid = %s
                  AND NOT locks.granted
                  AND locks.relation = 'corpus.active_scope_pointer'::regclass
                """,
                (b_pid[0],),
            )
            return int(cursor.fetchone()[0]) > 0

    with closing(psycopg2.connect(clean_postgres)) as conn_a:
        _activate(conn_a, release_a)  # acquires the EXCLUSIVE lock, uncommitted
        thread = threading.Thread(target=activate_b)
        thread.start()
        barrier.set()
        # Positively observe conn_b waiting on the active_scope_pointer lock before
        # committing A -- proving serialization, not merely timing. A missing or
        # ineffective EXCLUSIVE lock would let B run to completion here instead.
        deadline = 15.0
        blocked = False
        with closing(psycopg2.connect(clean_postgres)) as observer:
            observer.autocommit = True
            waited = 0.0
            while waited < deadline:
                if b_pid and _b_is_blocked_on_pointer_lock(observer):
                    blocked = True
                    break
                time.sleep(0.1)
                waited += 0.1
        assert blocked, "conn_b never blocked on the active_scope_pointer EXCLUSIVE lock"
        assert thread.is_alive()  # B is still waiting, not done
        conn_a.commit()
        thread.join(timeout=15)

    assert not errors_out, errors_out
    assert not thread.is_alive()
    with closing(psycopg2.connect(clean_postgres)) as check:
        assert _active_scope_map(check) == {(pair["jurisdiction"], "statute"): "nu-b"}
        chain = [(row[2], row[3]) for row in _scope_history(check)]
        assert chain == [
            ("nu-origin", None),
            ("nu-a", "nu-origin"),
            ("nu-b", "nu-a"),
        ]


def test_preview_wrapper_query_matches_the_function_contract(clean_postgres: str) -> None:
    # Run the Python wrapper's EXACT query string (supabase.PREVIEW_ACTIVATION_QUERY)
    # against the live function, so the two cannot drift apart (a mismatch would
    # break activate_release.py --dry-run in production, not in any test that
    # hand-writes the column list).
    from axiom_corpus.corpus import supabase

    identity = _scope_identity("preview-contract")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, identity)
        release_object = _release_object(
            "preview-contract-release", _scope_evidence(connection, identity)
        )
        _activate(connection, release_object)
        connection.commit()
        with connection.cursor() as cursor:
            cursor.execute(
                f"PREPARE preview_contract (text, text) AS {supabase.PREVIEW_ACTIVATION_QUERY}"
            )
            cursor.execute(
                "EXECUTE preview_contract(%s, %s)",
                (release_object["release"], release_object["content_sha256"]),
            )
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
        assert columns == [
            "jurisdiction",
            "document_class",
            "current_release_name",
            "current_content_sha256",
            "changes",
        ]
        # Previewing the already-active release: current occupant is itself,
        # changes is False.
        assert rows == [
            (
                identity["jurisdiction"],
                "statute",
                "preview-contract-release",
                release_object["content_sha256"],
                False,
            )
        ]

        with connection.cursor() as cursor:
            cursor.execute(
                f"PREPARE activation_contract (text, text) AS "
                f"{supabase.ACTIVATE_RELEASE_QUERY}"
            )
            cursor.execute(
                "EXECUTE activation_contract(%s, %s)",
                (release_object["release"], release_object["content_sha256"]),
            )
            result = cursor.fetchone()[0]
        assert result["active"] is True
        assert result["release"] == release_object["release"]
        assert result["content_sha256"] == release_object["content_sha256"]


def test_pointer_membership_trigger_rejects_an_uncovered_pair(clean_postgres: str) -> None:
    # A pointer row may only name a release that covers the pair. A direct insert
    # (simulating a stray migration / management-plane statement) that names a
    # signed release lacking the pair must be rejected, not create a serving hole.
    covered = _scope_identity("theta")
    other = _scope_identity("iota")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, covered)
        _seed_scope(connection, other)
        covered_release = _release_object("theta-release", _scope_evidence(connection, covered))
        other_release = _release_object("iota-release", _scope_evidence(connection, other))
        _activate(connection, covered_release)
        _activate(connection, other_release)
        connection.commit()

        with (
            connection.cursor() as cursor,
            pytest.raises(errors.RaiseException, match="does not cover the pair"),
        ):
            cursor.execute(
                """
                INSERT INTO corpus.active_scope_pointer (
                  jurisdiction, document_class, release_name, content_sha256
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (jurisdiction, document_class) DO UPDATE SET
                  release_name = EXCLUDED.release_name,
                  content_sha256 = EXCLUDED.content_sha256
                """,
                (
                    covered["jurisdiction"],
                    "statute",
                    "iota-release",
                    other_release["content_sha256"],
                ),
            )
        connection.rollback()


def test_compact_released_scope_rpc_returns_each_signed_object_once(
    clean_postgres: str,
) -> None:
    first = _scope_identity("compact-first")
    second = _scope_identity("compact-second")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, first)
        _seed_scope(connection, second)
        release_object = _multi_scope_release_object(
            "compact-release",
            [_scope_evidence(connection, first), _scope_evidence(connection, second)],
        )
        _activate(connection, release_object)
        connection.commit()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT corpus.get_released_scope_object_sets(%s::jsonb)",
                (Json([first, second]),),
            )
            result = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT
                  has_function_privilege(
                    'service_role',
                    'corpus.get_released_scope_object_sets(jsonb)',
                    'EXECUTE'
                  ),
                  has_function_privilege(
                    'anon',
                    'corpus.get_released_scope_object_sets(jsonb)',
                    'EXECUTE'
                  ),
                  has_function_privilege(
                    'authenticated',
                    'corpus.get_released_scope_object_sets(jsonb)',
                    'EXECUTE'
                  )
                """
            )
            privileges = cursor.fetchone()

    assert len(result) == 1
    assert result[0]["release_name"] == "compact-release"
    assert result[0]["release_object"] == release_object
    assert result[0]["scopes"] == sorted(
        [first, second],
        key=lambda scope: (
            scope["jurisdiction"],
            scope["document_class"],
            scope["version"],
        ),
    )
    assert privileges == (True, False, False)


def test_seed_carries_the_singleton_served_scopes_into_the_scope_map(
    clean_postgres: str,
) -> None:
    # The migration seeds active_scope_pointer from whatever the singleton served
    # at apply time, DISTINCT over versions. Reconstruct the pre-seed state and
    # run the seed statement exactly as the migration does, proving serving is
    # continuous across the cut for a multi-version pair.
    v1 = _scope_identity("zeta")
    v2 = _versioned(v1, "2026-07-11")
    with closing(psycopg2.connect(clean_postgres)) as connection:
        _seed_scope(connection, v1)
        _seed_scope(connection, v2)
        release_object = _multi_scope_release_object(
            "zeta-release",
            [_scope_evidence(connection, v1), _scope_evidence(connection, v2)],
        )
        _activate(connection, release_object)
        connection.commit()

        with connection.cursor() as cursor:
            # Simulate the pre-migration world: only the singleton is populated.
            cursor.execute("DELETE FROM corpus.active_scope_pointer")
            connection.commit()
            assert _active_scope_map(connection) == {}
            cursor.execute(
                """
                INSERT INTO corpus.active_scope_pointer (
                  jurisdiction, document_class, release_name, content_sha256, activated_at
                )
                SELECT DISTINCT scopes.jurisdiction, scopes.document_class,
                       scopes.release_name, pointer.content_sha256, now()
                FROM corpus.release_scopes scopes
                JOIN corpus.active_release_pointer pointer
                  ON pointer.pointer_name = 'production'
                 AND pointer.release_name = scopes.release_name
                ON CONFLICT (jurisdiction, document_class) DO NOTHING
                """
            )
        connection.commit()

        # One pointer row for the pair; both versions served again.
        assert _active_scope_map(connection) == {
            (v1["jurisdiction"], "statute"): "zeta-release",
        }
        assert _served_scope_keys(connection) == {
            (v1["jurisdiction"], "statute", v1["version"]),
            (v1["jurisdiction"], "statute", v2["version"]),
        }
