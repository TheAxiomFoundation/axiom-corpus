"""Scratch: EXPLAIN (ANALYZE, BUFFERS) the serving queries as anon."""

from __future__ import annotations

import os
import sys
from contextlib import closing

import psycopg2

DB = sys.argv[1] if len(sys.argv) > 1 else "layered_bench"
VERBOSE = "-v" in sys.argv
REPEAT = int(os.environ.get("REPEAT", "5"))
ONLY = [arg for arg in sys.argv[2:] if not arg.startswith("-")]
dsn = psycopg2.extensions.make_dsn(os.environ["DATABASE_URL"], dbname=DB)

QUERIES = {
    "provision_base_only": (
        "SELECT * FROM corpus.current_provisions WHERE citation_path = 'us/statute/30/500'"
    ),
    "provision_collision": (
        "SELECT * FROM corpus.current_provisions WHERE citation_path = 'us/statute/3/1'"
    ),
    "provision_primary_only": (
        "SELECT * FROM corpus.current_provisions WHERE citation_path = 'us/statute/3/1300x'"
    ),
    "provision_title_prefix": (
        "SELECT citation_path FROM corpus.current_provisions WHERE jurisdiction = 'us' "
        "AND citation_path >= 'us/statute/3/' AND citation_path < 'us/statute/30' "
        "ORDER BY citation_path LIMIT 1000"
    ),
    "nav_us_page": (
        "SELECT jurisdiction, doc_type, citation_path, has_children, child_count, "
        "has_rulespec, version FROM corpus.current_navigation_nodes "
        "WHERE jurisdiction = 'us' ORDER BY citation_path LIMIT 1000"
    ),
    "nav_us_deep_page": (
        "SELECT jurisdiction, doc_type, citation_path, has_children, child_count, "
        "has_rulespec, version FROM corpus.current_navigation_nodes "
        "WHERE jurisdiction = 'us' ORDER BY citation_path LIMIT 1000 OFFSET 250000"
    ),
    "nav_view_children": (
        "SELECT * FROM corpus.current_navigation_nodes WHERE jurisdiction = 'us' "
        "AND doc_type = 'statute' AND parent_path = 'us/statute/3' ORDER BY sort_key LIMIT 100"
    ),
    "nav_view_roots": (
        "SELECT * FROM corpus.current_navigation_nodes WHERE jurisdiction = 'us' "
        "AND doc_type = 'statute' AND parent_path IS NULL ORDER BY sort_key LIMIT 100"
    ),
    "root_counts": "SELECT * FROM corpus.get_root_document_counts()",
    "nav_table_children": (
        "SELECT * FROM corpus.navigation_nodes WHERE jurisdiction = 'us' "
        "AND doc_type = 'statute' AND parent_path = 'us/statute/3' ORDER BY sort_key LIMIT 100"
    ),
    "nav_table_children_count": (
        "SELECT COUNT(*) FROM corpus.navigation_nodes WHERE jurisdiction = 'us' "
        "AND doc_type = 'statute' AND parent_path = 'us/statute/3'"
    ),
    "nav_table_path": (
        "SELECT * FROM corpus.navigation_nodes WHERE path = 'us/statute/3/1' "
        "ORDER BY sort_key DESC LIMIT 1"
    ),
    "nav_table_roots": (
        "SELECT doc_type, path FROM corpus.navigation_nodes WHERE jurisdiction = 'us' "
        "AND parent_path IS NULL ORDER BY doc_type LIMIT 200"
    ),
}

REF = {
    "ref_provision_title_prefix": QUERIES["provision_title_prefix"].replace("corpus.current_provisions", "ref.current_provisions"),
    "ref_nav_us_page": QUERIES["nav_us_page"].replace("corpus.current_navigation_nodes", "ref.current_navigation_nodes"),
    "ref_nav_us_deep_page": QUERIES["nav_us_deep_page"].replace("corpus.current_navigation_nodes", "ref.current_navigation_nodes"),
    "ref_nav_view_children": QUERIES["nav_view_children"].replace("corpus.current_navigation_nodes", "ref.current_navigation_nodes"),
    "ref_nav_view_roots": QUERIES["nav_view_roots"].replace("corpus.current_navigation_nodes", "ref.current_navigation_nodes"),
    "ref_root_counts": (
        "SELECT jurisdiction, COALESCE(NULLIF(doc_type, ''), 'unknown') AS doc_type, COUNT(*) "
        "FROM ref.current_navigation_nodes WHERE parent_path IS NULL AND jurisdiction IS NOT NULL "
        "GROUP BY 1, 2 ORDER BY 1, 2"
    ),
}
if "--ref" in sys.argv:
    QUERIES.update(REF)


def main() -> None:
    with closing(psycopg2.connect(dsn)) as connection, connection.cursor() as cursor:
        cursor.execute("SET ROLE anon")
        cursor.execute("SET statement_timeout = '3s'")
        for name, query in QUERIES.items():
            if ONLY and name not in ONLY:
                continue
            try:
                times = []
                for _ in range(REPEAT):
                    cursor.execute("EXPLAIN (ANALYZE, BUFFERS) " + query)
                    lines = [row[0] for row in cursor.fetchall()]
                    execution = next(line for line in lines if line.startswith("Execution Time"))
                    times.append(float(execution.split()[2]))
                times.sort()
                print(f"{name:28s} min {times[0]:9.2f} ms  median {times[len(times) // 2]:9.2f} ms")
                if VERBOSE:
                    print("\n".join("    " + line for line in lines))
            except psycopg2.Error as exc:
                connection.rollback()
                cursor.execute("SET ROLE anon")
                cursor.execute("SET statement_timeout = '3s'")
                print(f"{name:28s} ERROR {exc.pgcode} {str(exc).splitlines()[0]}")


if __name__ == "__main__":
    main()
