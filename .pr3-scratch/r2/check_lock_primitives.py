"""Scratch: which relations a no-op ALTER VIEW ... OWNER TO and pg_get_viewdef lock."""
from contextlib import closing
import psycopg2
import tests.test_layered_serving_postgres as L

LOCKS = ("SELECT relation::regclass::text, mode FROM pg_locks WHERE pid = pg_backend_pid() "
         "AND locktype = 'relation' AND relation::regclass::text LIKE 'corpus.%' ORDER BY 1, 2")
gen = L._create_database(layered=True)
dsn = next(gen)
try:
    for statement in (
        "ALTER VIEW corpus.current_provisions OWNER TO test",
        "SELECT pg_get_viewdef('corpus.current_provisions'::regclass)",
        "LOCK TABLE corpus.current_provisions IN ACCESS EXCLUSIVE MODE",
        "SELECT 1 FROM corpus.current_provisions LIMIT 0",
    ):
        with closing(psycopg2.connect(dsn)) as c, c.cursor() as cur:
            cur.execute(statement)
            cur.execute(LOCKS)
            print(statement, "->", cur.fetchall())
            c.rollback()
finally:
    gen.close()
