"""PostgreSQL coverage for the navigation-view scope index (20260914000000).

The index exists so a per-jurisdiction page of ``corpus.current_navigation_nodes``
answers within the anon statement timeout. These tests apply the migration to
the production view, policy and serving-map definitions and prove in PostgreSQL
itself that (a) visibility through the view is unchanged by the index and still
follows ``corpus.active_scope_pointer`` exactly across a repoint, (b) the index
expression matches the view's scope test so the planner can drive the page from
the active scopes, and (c) the migration is idempotent.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")
sql = pytest.importorskip("psycopg2.sql")

DATABASE_URL = os.environ.get("DATABASE_URL")
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase/migrations/20260914000000_navigation_release_scope_index.sql"
)
INDEX_NAME = "idx_navigation_nodes_release_scope_version"
REQUIRED_ROLES = ("anon", "authenticated", "service_role", "postgres")
NAV_SELECT = (
    "jurisdiction, doc_type, citation_path, has_children, child_count, has_rulespec, version"
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for PostgreSQL migration integration tests",
)

# The objects the view depends on, as production defines them after
# 20260505120000, 20260513140000/180000, 20260710180000 and 20260718193000.
PRE_MIGRATION_SCHEMA = """
CREATE SCHEMA corpus;
GRANT USAGE ON SCHEMA corpus TO anon, authenticated, service_role;

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
  provision_id text,
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
CREATE INDEX idx_navigation_nodes_path ON corpus.navigation_nodes (path);
CREATE UNIQUE INDEX idx_navigation_nodes_path_version
  ON corpus.navigation_nodes (path, version) WHERE version IS NOT NULL;
CREATE INDEX idx_navigation_nodes_scope_version_parent_sort
  ON corpus.navigation_nodes (jurisdiction, doc_type, version, parent_path, sort_key);

CREATE TABLE corpus.release_objects (
  release_name text PRIMARY KEY,
  content_sha256 text NOT NULL UNIQUE,
  release_object jsonb NOT NULL,
  UNIQUE (release_name, content_sha256)
);
CREATE TABLE corpus.release_scopes (
  release_name text NOT NULL REFERENCES corpus.release_objects (release_name),
  jurisdiction text NOT NULL,
  document_class text NOT NULL,
  version text NOT NULL,
  synced_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (release_name, jurisdiction, document_class, version)
);
CREATE TABLE corpus.active_scope_pointer (
  jurisdiction text NOT NULL,
  document_class text NOT NULL,
  release_name text NOT NULL,
  content_sha256 text NOT NULL,
  activated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (jurisdiction, document_class),
  FOREIGN KEY (release_name, content_sha256)
    REFERENCES corpus.release_objects (release_name, content_sha256)
);
GRANT SELECT ON corpus.release_objects, corpus.release_scopes, corpus.active_scope_pointer
  TO anon, authenticated;

CREATE VIEW corpus.current_release_scopes AS
SELECT scopes.release_name, scopes.jurisdiction, scopes.document_class, scopes.version, scopes.synced_at
FROM corpus.release_scopes scopes
JOIN corpus.active_scope_pointer active
  ON active.jurisdiction = scopes.jurisdiction
 AND active.document_class = scopes.document_class
 AND active.release_name = scopes.release_name;

CREATE VIEW corpus.current_navigation_nodes AS
SELECT n.*
FROM corpus.navigation_nodes n
WHERE EXISTS (
  SELECT 1
  FROM corpus.current_release_scopes s
  WHERE s.jurisdiction = n.jurisdiction
    AND s.document_class = COALESCE(NULLIF(n.doc_type, ''), 'unknown')
    AND s.version = n.version
);
GRANT SELECT ON corpus.current_release_scopes, corpus.current_navigation_nodes TO anon, authenticated;

ALTER TABLE corpus.navigation_nodes ENABLE ROW LEVEL SECURITY;
CREATE POLICY anon_read ON corpus.navigation_nodes
  FOR SELECT TO anon
  USING (
    EXISTS (
      SELECT 1
      FROM corpus.current_release_scopes s
      WHERE s.jurisdiction = navigation_nodes.jurisdiction
        AND s.document_class = COALESCE(NULLIF(navigation_nodes.doc_type, ''), 'unknown')
        AND s.version = navigation_nodes.version
    )
  );
GRANT SELECT ON corpus.navigation_nodes TO anon, authenticated;
"""

# us/statute: v1 superseded, v2 served by release r1, v3 staged and signed into
# r2 but not active. us/regulation: only v1, served by r1. Another jurisdiction
# with an empty doc_type (the 'unknown' document class) is served by r3.
FIXTURE_ROWS = """
INSERT INTO corpus.release_objects VALUES
  ('r1', repeat('1', 64), '{}'), ('r2', repeat('2', 64), '{}'), ('r3', repeat('3', 64), '{}');
INSERT INTO corpus.release_scopes (release_name, jurisdiction, document_class, version) VALUES
  ('r1', 'us', 'statute', 'v2'), ('r1', 'us', 'regulation', 'v1'),
  ('r2', 'us', 'statute', 'v3'),
  ('r3', 'xx', 'unknown', 'v1');
INSERT INTO corpus.active_scope_pointer (jurisdiction, document_class, release_name, content_sha256) VALUES
  ('us', 'statute', 'r1', repeat('1', 64)),
  ('us', 'regulation', 'r1', repeat('1', 64)),
  ('xx', 'unknown', 'r3', repeat('3', 64));
INSERT INTO corpus.navigation_nodes
  (id, jurisdiction, doc_type, path, segment, label, sort_key, depth, citation_path, version)
SELECT
  jurisdiction || '/' || doc_type || '/' || version || '/' || n,
  jurisdiction, doc_type,
  jurisdiction || '/' || COALESCE(NULLIF(doc_type, ''), 'unknown') || '/sec-' || n,
  'sec-' || n, 'Section ' || n, lpad(n::text, 4, '0'), 0,
  jurisdiction || '/' || COALESCE(NULLIF(doc_type, ''), 'unknown') || '/sec-' || n,
  version
FROM (VALUES
  ('us', 'statute', 'v1', 3), ('us', 'statute', 'v2', 3), ('us', 'statute', 'v3', 3),
  ('us', 'regulation', 'v1', 2), ('us', 'regulation', 'v0', 2),
  ('xx', '', 'v1', 2), ('xx', '', 'v0', 2)
) AS scopes (jurisdiction, doc_type, version, rows),
LATERAL generate_series(1, rows) AS n;
"""


@pytest.fixture(scope="module")
def postgres_dsn() -> Iterator[str]:
    assert DATABASE_URL is not None
    database_name = f"axiom_navigation_index_{uuid.uuid4().hex}"
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
                    cursor.execute(FIXTURE_ROWS)
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


def _visible_as_anon(dsn: str, jurisdiction: str) -> list[tuple[str, str]]:
    """The consumer's request: one jurisdiction of the view, ordered by citation_path."""
    with closing(psycopg2.connect(dsn)) as connection, connection.cursor() as cursor:
        cursor.execute("SET ROLE anon")
        cursor.execute(
            f"SELECT citation_path, version FROM ("
            f"SELECT {NAV_SELECT} FROM corpus.current_navigation_nodes "
            f"WHERE jurisdiction = %s ORDER BY citation_path ASC, version ASC LIMIT 1000 OFFSET 0) page",
            (jurisdiction,),
        )
        return [(str(path), str(version)) for path, version in cursor.fetchall()]


def _apply_migration(dsn: str) -> None:
    with closing(psycopg2.connect(dsn)) as connection, connection.cursor() as cursor:
        cursor.execute(MIGRATION.read_text(encoding="utf-8"))
        connection.commit()


EXPECTED_US = [("us/regulation/sec-1", "v1"), ("us/regulation/sec-2", "v1")] + [
    (f"us/statute/sec-{n}", "v2") for n in (1, 2, 3)
]


def test_index_keeps_visibility_identical_and_following_the_serving_map(postgres_dsn: str) -> None:
    before_us = _visible_as_anon(postgres_dsn, "us")
    before_xx = _visible_as_anon(postgres_dsn, "xx")
    assert before_us == EXPECTED_US
    assert before_xx == [("xx/unknown/sec-1", "v1"), ("xx/unknown/sec-2", "v1")]

    _apply_migration(postgres_dsn)
    assert _visible_as_anon(postgres_dsn, "us") == before_us
    assert _visible_as_anon(postgres_dsn, "xx") == before_xx

    # Activation repoints one (jurisdiction, document_class) pair; the page must
    # follow the map exactly, with no refresh step, index or otherwise.
    with closing(psycopg2.connect(postgres_dsn)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE corpus.active_scope_pointer SET release_name = 'r2', content_sha256 = repeat('2', 64) "
            "WHERE jurisdiction = 'us' AND document_class = 'statute'"
        )
        connection.commit()
    try:
        assert _visible_as_anon(postgres_dsn, "us") == [
            ("us/regulation/sec-1", "v1"),
            ("us/regulation/sec-2", "v1"),
        ] + [(f"us/statute/sec-{n}", "v3") for n in (1, 2, 3)]
    finally:
        with closing(psycopg2.connect(postgres_dsn)) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE corpus.active_scope_pointer SET release_name = 'r1', content_sha256 = repeat('1', 64) "
                "WHERE jurisdiction = 'us' AND document_class = 'statute'"
            )
            connection.commit()
    assert _visible_as_anon(postgres_dsn, "us") == EXPECTED_US


def test_index_matches_the_view_scope_test_so_the_planner_can_use_it(postgres_dsn: str) -> None:
    _apply_migration(postgres_dsn)
    with closing(psycopg2.connect(postgres_dsn)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = 'corpus' AND indexname = %s",
            (INDEX_NAME,),
        )
        (indexdef,) = cursor.fetchone()
        assert (
            "(jurisdiction, COALESCE(NULLIF(doc_type, ''::text), 'unknown'::text), version)"
            in indexdef
        )
        assert "INCLUDE (citation_path, has_children, child_count, has_rulespec)" in indexdef

        # The fixture is tiny, so a sequential scan is cheapest; disabling it shows
        # the index is *usable* for the scope test, which is what fails without
        # the COALESCE expression in the key.
        cursor.execute("SET ROLE anon")
        cursor.execute("SET enable_seqscan = off")
        cursor.execute(
            f"EXPLAIN (COSTS OFF) SELECT {NAV_SELECT} FROM corpus.current_navigation_nodes "
            "WHERE jurisdiction = 'us' ORDER BY citation_path ASC LIMIT 1000 OFFSET 0"
        )
        plan = "\n".join(str(row[0]) for row in cursor.fetchall())
    assert INDEX_NAME in plan, plan
    assert "COALESCE(NULLIF(doc_type, ''::text), 'unknown'::text) = " in plan, plan


def test_migration_is_idempotent(postgres_dsn: str) -> None:
    _apply_migration(postgres_dsn)
    _apply_migration(postgres_dsn)
    with closing(psycopg2.connect(postgres_dsn)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_indexes WHERE schemaname = 'corpus' AND indexname = %s",
            (INDEX_NAME,),
        )
        assert cursor.fetchone() == (1,)
