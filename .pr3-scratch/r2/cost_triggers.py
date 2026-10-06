"""Scratch: cost of the layered triggers on a 7 MB release object (1042 scopes,
288 pairs, 45,880 artifacts; the shape the round-3 reviewer measured), per
isolation level, with the sync triggers on and off. Each run rolls back."""
import time
from contextlib import closing
import psycopg2
import tests.test_layered_serving_postgres as L

BIG = open(".review-scratch/r3-sql/cost_release_layers_pair.sql").read().split("\\timing off")[1].split("SELECT pg_size_pretty")[0]
MEMBERSHIP = """INSERT INTO corpus.release_scopes (release_name, jurisdiction, document_class, version)
SELECT 'cost-big', s->>'jurisdiction', s->>'document_class', s->>'version'
FROM corpus.release_objects o, jsonb_array_elements(o.release_object #> '{content,scopes}') s
WHERE o.release_name = 'cost-big'"""
POINTERS = """INSERT INTO corpus.active_scope_pointer (jurisdiction, document_class, release_name, content_sha256)
SELECT DISTINCT s->>'jurisdiction', s->>'document_class', 'cost-big', repeat('c', 64)
FROM corpus.release_objects o, jsonb_array_elements(o.release_object #> '{content,scopes}') s
WHERE o.release_name = 'cost-big'"""
gen = L._create_database(layered=True)
dsn = next(gen)
try:
    with closing(psycopg2.connect(dsn)) as c:
        with c.cursor() as cur:
            cur.execute(BIG)
            cur.execute("SELECT pg_size_pretty(pg_column_size(release_object)::bigint) FROM corpus.release_objects WHERE release_name='cost-big'")
            print("object stored size:", cur.fetchone()[0])
        c.commit()
        for isolation in ("READ COMMITTED", "REPEATABLE READ"):
            for triggers in ("on", "off"):
                with c.cursor() as cur:
                    cur.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
                    if triggers == "off":
                        cur.execute("ALTER TABLE corpus.release_scopes DISABLE TRIGGER sync_layered_serving_membership")
                        cur.execute("ALTER TABLE corpus.active_scope_pointer DISABLE TRIGGER sync_layered_serving")
                    t = time.monotonic(); cur.execute(MEMBERSHIP); m = time.monotonic() - t
                    t = time.monotonic(); cur.execute(POINTERS); p = time.monotonic() - t
                c.rollback()
                print(f"{isolation:16} sync triggers {triggers:3}: 1042-row membership insert {m*1000:7.1f} ms, 288 pointer inserts {p*1000:7.1f} ms")
finally:
    gen.close()
