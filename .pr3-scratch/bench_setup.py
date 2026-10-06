"""Scratch: build a production-shaped database for layered-serving plan measurements."""

from __future__ import annotations

import os
import sys
import time
from contextlib import closing
from pathlib import Path

import psycopg2
from psycopg2 import sql

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tests import test_atomic_release_postgres as t  # noqa: E402

ADMIN = os.environ["DATABASE_URL"]
DB = sys.argv[1] if len(sys.argv) > 1 else "layered_bench"
LAYERED = "--layered" in sys.argv

PRODUCTION_SHAPE = """
-- Pre-layer serving objects as production has them (latest definitions).
CREATE OR REPLACE VIEW corpus.legacy_provisions AS
SELECT p.* FROM corpus.provisions p
WHERE NOT EXISTS (
  SELECT 1 FROM corpus.current_release_scopes s
  WHERE s.jurisdiction = p.jurisdiction
    AND s.document_class = COALESCE(NULLIF(p.doc_type, ''), 'unknown')
    AND s.version = p.version);
CREATE OR REPLACE VIEW corpus.current_navigation_nodes AS
SELECT n.* FROM corpus.navigation_nodes n
WHERE EXISTS (
  SELECT 1 FROM corpus.current_release_scopes s
  WHERE s.jurisdiction = n.jurisdiction
    AND s.document_class = COALESCE(NULLIF(n.doc_type, ''), 'unknown')
    AND s.version = n.version);
GRANT SELECT ON corpus.current_navigation_nodes TO anon, authenticated;
GRANT SELECT ON corpus.current_provisions, corpus.current_release_scopes TO anon, authenticated;
ALTER TABLE corpus.navigation_nodes ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON corpus.navigation_nodes TO anon, authenticated;
CREATE POLICY anon_read ON corpus.navigation_nodes FOR SELECT TO anon USING (
  EXISTS (SELECT 1 FROM corpus.current_release_scopes s
    WHERE s.jurisdiction = navigation_nodes.jurisdiction
      AND s.document_class = COALESCE(NULLIF(navigation_nodes.doc_type, ''), 'unknown')
      AND s.version = navigation_nodes.version));
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_parent_sort
  ON corpus.navigation_nodes (parent_path, sort_key);
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_scope_parent_sort
  ON corpus.navigation_nodes (jurisdiction, doc_type, parent_path, sort_key);
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_provision_id
  ON corpus.navigation_nodes (provision_id) WHERE provision_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_scope_version_parent_sort
  ON corpus.navigation_nodes (jurisdiction, doc_type, version, parent_path, sort_key);
CREATE INDEX IF NOT EXISTS idx_navigation_nodes_roots_by_scope_version
  ON corpus.navigation_nodes (jurisdiction, doc_type, version) WHERE parent_path IS NULL;
CREATE INDEX IF NOT EXISTS idx_provisions_release_scope_version
  ON corpus.provisions (jurisdiction, (COALESCE(NULLIF(doc_type, ''), 'unknown')), version);
CREATE INDEX IF NOT EXISTS idx_provisions_jurisdiction_doc_type_id
  ON corpus.provisions (jurisdiction, doc_type, id) INCLUDE (level);
CREATE OR REPLACE FUNCTION corpus.get_root_document_counts()
RETURNS TABLE (jurisdiction text, doc_type text, document_count bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = corpus, public AS $$
  SELECT jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown') AS doc_type,
         COUNT(*)::bigint AS document_count
  FROM corpus.current_navigation_nodes
  WHERE parent_path IS NULL AND jurisdiction IS NOT NULL
  GROUP BY jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown')
  ORDER BY jurisdiction, doc_type
$$;
GRANT EXECUTE ON FUNCTION corpus.get_root_document_counts() TO anon, authenticated;
"""

# One generated scope = (jurisdiction, doc_type, version, row_generator_sql). Rows
# are produced into a staging table with (path, parent_path, depth, ordinal).
DATA = r"""
CREATE UNLOGGED TABLE bench_rows (
  jurisdiction text, doc_type text, version text, path text, parent_path text,
  depth int, ordinal int, has_rulespec boolean DEFAULT false
);

-- us/statute base: 53 titles, 60,393 sections.
INSERT INTO bench_rows
SELECT 'us','statute','2026-04-29','us/statute/'||t, NULL, 0, t
FROM generate_series(1,53) t;
INSERT INTO bench_rows
SELECT 'us','statute','2026-04-29','us/statute/'||(1+(i%53))||'/'||(i/53+1),
       'us/statute/'||(1+(i%53)), 1, i/53+1
FROM generate_series(0,60392) i;

-- us/regulation base: 49 titles, 4,900 parts, 241,528 sections.
INSERT INTO bench_rows
SELECT 'us','regulation','2026-05-01','us/regulation/'||t, NULL, 0, t
FROM generate_series(1,49) t;
INSERT INTO bench_rows
SELECT 'us','regulation','2026-05-01','us/regulation/'||(1+(i%49))||'/'||(i/49+1),
       'us/regulation/'||(1+(i%49)), 1, i/49+1
FROM generate_series(0,4899) i;
INSERT INTO bench_rows
SELECT 'us','regulation','2026-05-01',
       'us/regulation/'||(1+(p%49))||'/'||(p/49+1)||'/'||(p/49+1)||'.'||(i/4900+1),
       'us/regulation/'||(1+(p%49))||'/'||(p/49+1), 2, i/4900+1
FROM generate_series(0,241527) i, LATERAL (SELECT i%4900 AS p) part;

-- 48 primary us scopes, 300 rows each: 24 statute, 24 regulation. Odd scopes
-- carry their title/part row; every scope collides with 5 base sections.
INSERT INTO bench_rows
SELECT 'us','statute','2026-09-'||lpad(k::text,2,'0')||'-primary-statute-'||k,
       'us/statute/'||(1+k*2)||'/'||(1000+k*300+i)||'x',
       CASE WHEN k%2=1 THEN 'us/statute/'||(1+k*2) END, CASE WHEN k%2=1 THEN 1 ELSE 0 END, i
FROM generate_series(0,23) k, generate_series(0,289) i;
INSERT INTO bench_rows
SELECT 'us','statute','2026-09-'||lpad(k::text,2,'0')||'-primary-statute-'||k,
       'us/statute/'||(1+k*2)||'/'||(c+1),
       CASE WHEN k%2=1 THEN 'us/statute/'||(1+k*2) END, CASE WHEN k%2=1 THEN 1 ELSE 0 END, 900+c
FROM generate_series(0,23) k, generate_series(0,8) c;
INSERT INTO bench_rows
SELECT 'us','statute','2026-09-'||lpad(k::text,2,'0')||'-primary-statute-'||k,
       'us/statute/'||(1+k*2), NULL, 0, 1
FROM generate_series(0,23) k WHERE k%2=1;
INSERT INTO bench_rows
SELECT 'us','regulation','2026-09-'||lpad(k::text,2,'0')||'-primary-regulation-'||k,
       'us/regulation/'||(1+k*2)||'/'||(k+1)||'/'||(k+1)||'.'||(1000+i),
       CASE WHEN k%2=1 THEN 'us/regulation/'||(1+k*2)||'/'||(k+1) END,
       CASE WHEN k%2=1 THEN 1 ELSE 0 END, i
FROM generate_series(0,23) k, generate_series(0,289) i;
INSERT INTO bench_rows
SELECT 'us','regulation','2026-09-'||lpad(k::text,2,'0')||'-primary-regulation-'||k,
       'us/regulation/'||(1+k*2)||'/'||(k+1)||'/'||(k+1)||'.'||(c+1),
       CASE WHEN k%2=1 THEN 'us/regulation/'||(1+k*2)||'/'||(k+1) END,
       CASE WHEN k%2=1 THEN 1 ELSE 0 END, 900+c
FROM generate_series(0,23) k, generate_series(0,8) c;
INSERT INTO bench_rows
SELECT 'us','regulation','2026-09-'||lpad(k::text,2,'0')||'-primary-regulation-'||k,
       'us/regulation/'||(1+k*2)||'/'||(k+1), NULL, 0, 1
FROM generate_series(0,23) k WHERE k%2=1;

-- 400,000 superseded us rows: 40 historical versions of 10,000 statute sections.
INSERT INTO bench_rows
SELECT 'us','statute','2026-0'||(1+v%6)||'-historical-'||v,
       'us/statute/'||(1+(i%53))||'/'||(i/53+1), NULL, 0, i
FROM generate_series(0,39) v, generate_series(v*1000, v*1000+9999) i;

-- 200 other jurisdictions, 4,000 rows each, half served, half historical.
INSERT INTO bench_rows
SELECT 'x'||j, 'statute', CASE WHEN h=0 THEN 'served' ELSE 'old' END,
       'x'||j||'/statute/'||(i/100)||CASE WHEN i%100=0 THEN '' ELSE '/'||(i%100) END,
       CASE WHEN i%100=0 THEN NULL ELSE 'x'||j||'/statute/'||(i/100) END,
       CASE WHEN i%100=0 THEN 0 ELSE 1 END, i
FROM generate_series(1,200) j, generate_series(0,1) h, generate_series(0,1999) i;

UPDATE bench_rows SET has_rulespec = true
WHERE version LIKE '2026-09-%' AND ordinal % 7 = 0;

INSERT INTO corpus.provisions (id, citation_path, jurisdiction, doc_type, version, body,
  parent_id, level, ordinal, heading, source_path, expression_date, has_rulespec)
SELECT md5('p'||version||path)::uuid, path, jurisdiction, doc_type, version,
       repeat(md5(path), 12), CASE WHEN parent_path IS NULL THEN NULL
       ELSE md5('p'||version||parent_path)::uuid END,
       depth, ordinal, 'Heading '||path, 'sources/'||jurisdiction||'/'||version,
       DATE '2026-01-01', has_rulespec
FROM bench_rows;

INSERT INTO corpus.navigation_nodes (id, jurisdiction, doc_type, path, parent_path, segment,
  label, sort_key, depth, provision_id, citation_path, has_children, child_count,
  has_rulespec, encoded_descendant_count, status, version)
SELECT md5('n'||r.version||r.path), r.jurisdiction, r.doc_type, r.path, r.parent_path,
       regexp_replace(r.path, '^.*/', ''), 'Heading '||r.path,
       lpad(r.ordinal::text, 8, '0')||'|'||regexp_replace(r.path, '^.*/', ''),
       r.depth, md5('p'||r.version||r.path)::uuid, r.path,
       COALESCE(c.n, 0) > 0, COALESCE(c.n, 0), r.has_rulespec, 0, NULL, r.version
FROM bench_rows r
LEFT JOIN (
  SELECT version, parent_path, COUNT(*)::int AS n FROM bench_rows
  WHERE parent_path IS NOT NULL GROUP BY 1, 2
) c ON c.version = r.version AND c.parent_path = r.path;

-- Release membership: one served release for every served scope; 300 inert
-- historical memberships so release_scopes has production-like size.
INSERT INTO corpus.release_objects (release_name, content_sha256, release_object)
VALUES ('bench-current', repeat('a', 64), '{"content":{"created_at":"2026-09-30T00:00:00Z"}}'),
       ('bench-old', repeat('b', 64), '{"content":{"created_at":"2026-01-01T00:00:00Z"}}');
INSERT INTO corpus.release_scopes (release_name, jurisdiction, document_class, version)
SELECT DISTINCT 'bench-current', jurisdiction, doc_type, version FROM bench_rows
WHERE version NOT LIKE '%historical%' AND version <> 'old';
INSERT INTO corpus.release_scopes (release_name, jurisdiction, document_class, version)
SELECT DISTINCT 'bench-old', jurisdiction, doc_type, version FROM bench_rows
WHERE version LIKE '%historical%' OR version = 'old';
INSERT INTO corpus.active_scope_pointer (jurisdiction, document_class, release_name, content_sha256)
SELECT DISTINCT jurisdiction, document_class, 'bench-current', repeat('a', 64)
FROM corpus.release_scopes WHERE release_name = 'bench-current';
DROP TABLE bench_rows;
"""


def main() -> None:
    with closing(psycopg2.connect(ADMIN)) as admin:
        admin.autocommit = True
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(DB)))
            cursor.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(DB))
            )
    dsn = psycopg2.extensions.make_dsn(ADMIN, dbname=DB)
    with closing(psycopg2.connect(dsn)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(t.PRE_MIGRATION_SCHEMA)
            for path in (
                t.MIGRATION,
                t.SCOPE_MIGRATION,
                t.PROFILED_RELEASE_MIGRATION,
                t.COMPACT_RELEASE_OBJECTS_MIGRATION,
                t.CHUNKED_ACTIVATION_MIGRATION,
                t.STAGED_RELEASE_OBJECT_MIGRATION,
                t.STAGED_RELEASE_OBJECT_V4_MIGRATION,
            ):
                cursor.execute(path.read_text(encoding="utf-8"))
            cursor.execute(PRODUCTION_SHAPE)
        connection.commit()
        started = time.time()
        with connection.cursor() as cursor:
            cursor.execute(DATA)
        connection.commit()
        print(f"data loaded in {time.time() - started:.1f}s")
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("VACUUM ANALYZE corpus.provisions")
            cursor.execute("VACUUM ANALYZE corpus.navigation_nodes")
            cursor.execute("ANALYZE")
            cursor.execute("SELECT COUNT(*) FROM corpus.provisions")
            print("provisions", cursor.fetchone()[0])
            cursor.execute(
                "SELECT COUNT(*) FROM corpus.navigation_nodes WHERE jurisdiction = 'us'"
            )
            print("us navigation rows", cursor.fetchone()[0])


if __name__ == "__main__":
    main()
