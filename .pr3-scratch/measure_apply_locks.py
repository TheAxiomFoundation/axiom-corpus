"""Locks and duration of applying 20260927110000 (scratch measurement, not a test).

1. First application: a pre-layer database serving unlayered releases.
2. Re-application: the scale fixture (CI scale) with base scopes served.
For each, the file runs inside one transaction; before ROLLBACK/COMMIT, the
relation locks it holds in schema corpus are listed.
"""

from __future__ import annotations

import os
import time
from contextlib import closing

import psycopg2

import tests.test_layered_serving_postgres as L

LOCKS = """
SELECT relation.relname, relation.relkind, lock.mode
FROM pg_locks lock
JOIN pg_class relation ON relation.oid = lock.relation
JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
WHERE lock.pid = pg_backend_pid() AND namespace.nspname = 'corpus'
  AND relation.relkind IN ('r', 'v', 'm')
  AND lock.mode IN ('AccessExclusiveLock', 'ExclusiveLock', 'ShareRowExclusiveLock', 'ShareLock')
ORDER BY 3, 1
"""


def apply(dsn: str, label: str) -> None:
    sql_text = L.LAYERED_SERVING_MIGRATION.read_text(encoding="utf-8")
    with closing(psycopg2.connect(dsn)) as connection, connection.cursor() as cursor:
        started = time.monotonic()
        cursor.execute(sql_text)
        elapsed = time.monotonic() - started
        cursor.execute(LOCKS)
        locks = cursor.fetchall()
        connection.rollback()
    print(f"## {label}: file applied in {elapsed * 1000:.0f} ms (rolled back)")
    for name, kind, mode in locks:
        print(f"  {mode:24} {kind} {name}")


generator = L._create_database(layered=False)
dsn = next(generator)
try:
    with closing(psycopg2.connect(dsn)) as connection:
        L._publish(connection, "fx-rulespec-2026-09-01", L.PRIMARY_TITLE, L.OTHER_PAIR)
    apply(dsn, "first application, no base scope")
finally:
    generator.close()

generator = L._create_database(layered=True)
dsn = next(generator)
try:
    with closing(psycopg2.connect(dsn)) as connection:
        with connection.cursor() as cursor:
            scale_sql = L._SCALE_ROWS
            for name, value in L._SCALE.items():
                scale_sql = scale_sql.replace("{" + name + "}", str(value))
            cursor.execute(scale_sql)
        connection.commit()
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("VACUUM ANALYZE")
            cursor.execute(L._SCALE_SERVE)
            cursor.execute("SELECT COUNT(*) FROM corpus.provisions")
            print("provision rows:", cursor.fetchone()[0])
    apply(dsn, "re-application, base scopes served")
    with closing(psycopg2.connect(dsn)) as connection, connection.cursor() as cursor:
        started = time.monotonic()
        cursor.execute("SELECT corpus.rederive_layered_serving()")
        shadowed = cursor.fetchone()[0]
        elapsed = time.monotonic() - started
        cursor.execute(LOCKS)
        locks = cursor.fetchall()
        connection.commit()
    print(f"## rederive_layered_serving(): {elapsed:.1f} s, {shadowed} shadowed paths")
    for name, kind, mode in locks:
        print(f"  {mode:24} {kind} {name}")
finally:
    generator.close()
print("load:", os.getloadavg())
