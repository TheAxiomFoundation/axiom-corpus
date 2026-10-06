"""Scratch stress check (review round 2, Opus 1): apply the layered migration
repeatedly while anon reads run in a loop, and count deadlocks and lock
timeouts on both sides.

Usage: python stress_apply.py <migration.sql> <label> [applications] [readers]
Readers: 1 in 3 holds a 20 ms read of current_release_scopes in flight (the
in-flight read that makes the file wait); the rest loop over current_provisions,
current_navigation_nodes, direct navigation_nodes and the root-count RPC.
Each application runs the whole file in one transaction and commits
(re-application on a database serving a layered release).
"""
from __future__ import annotations

import sys
import threading
import time
from collections import Counter
from contextlib import closing

import psycopg2

import tests.test_layered_serving_postgres as L

path, label = sys.argv[1], sys.argv[2]
applications = int(sys.argv[3]) if len(sys.argv) > 3 else 40
readers = int(sys.argv[4]) if len(sys.argv) > 4 else 12
# "first": a pre-layer database serving an unlayered release; each application
# is rolled back, so every one is a first application.
first = len(sys.argv) > 5 and sys.argv[5] == "first"
migration = open(path, encoding="utf-8").read()
READS = (
    "SELECT id FROM corpus.current_provisions WHERE citation_path = 'fx/statute/1/1'",
    "SELECT id FROM corpus.current_navigation_nodes WHERE jurisdiction = 'fx' ORDER BY citation_path LIMIT 1000",
    "SELECT id FROM corpus.navigation_nodes WHERE parent_path = 'fx/statute/1'",
    "SELECT * FROM corpus.get_root_document_counts()",
)
SLOW = "SELECT pg_sleep(0.02), release_name FROM corpus.current_release_scopes"

gen = L._create_database(layered=not first)
dsn = next(gen)
stop = threading.Event()
read_outcomes: Counter[str] = Counter()
lock = threading.Lock()


def reader(index: int) -> None:
    with closing(psycopg2.connect(dsn)) as connection:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE anon")
            n = 0
            while not stop.is_set():
                query = SLOW if index % 3 == 0 else READS[n % len(READS)]
                n += 1
                try:
                    cursor.execute(query)
                    cursor.fetchall()
                    outcome = "ok"
                except psycopg2.Error as exc:
                    outcome = f"{exc.pgcode} {type(exc).__name__}"
                with lock:
                    read_outcomes[outcome] += 1


try:
    with closing(psycopg2.connect(dsn)) as connection:
        if first:
            L._publish(connection, "fx-rulespec-2026-09-01", L.PRIMARY_TITLE, L.OTHER_PAIR)
        else:
            L._publish_layered(connection)
    threads = [threading.Thread(target=reader, args=(i,), daemon=True) for i in range(readers)]
    for thread in threads:
        thread.start()
    time.sleep(0.5)
    apply_outcomes: Counter[str] = Counter()
    started = time.monotonic()
    with closing(psycopg2.connect(dsn)) as connection:
        for _ in range(applications):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(migration)
                if first:
                    connection.rollback()
                    apply_outcomes["applied (rolled back)"] += 1
                else:
                    connection.commit()
                    apply_outcomes["committed"] += 1
            except psycopg2.Error as exc:
                connection.rollback()
                apply_outcomes[f"{exc.pgcode} {type(exc).__name__}"] += 1
            time.sleep(0.05)
    elapsed = time.monotonic() - started
    stop.set()
    for thread in threads:
        thread.join(10)
    print(f"## {label}: {applications} applications in {elapsed:.1f} s with {readers} anon readers")
    print("  applications:", dict(apply_outcomes))
    print("  reads:", dict(read_outcomes))
finally:
    gen.close()
