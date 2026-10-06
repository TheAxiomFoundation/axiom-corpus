"""Scratch: what is served after Sol's TRUNCATE sequence and the refresh race, on the given migration.

Run against the worktree's migration file. Prints counts only.
"""
from contextlib import closing
import psycopg2
import tests.test_layered_serving_postgres as L
from psycopg2.extras import Json

def state(c, label):
    q = lambda s: L._rows(c, s)[0][0]
    print(f"  {label}: stored navigation={q('SELECT COUNT(*) FROM corpus.navigation_nodes')}, "
          f"membership={q('SELECT COUNT(*) FROM corpus.release_scopes')}, "
          f"pointers={q('SELECT COUNT(*) FROM corpus.active_scope_pointer')}, "
          f"served provisions={q('SELECT COUNT(*) FROM corpus.current_provisions')}, "
          f"served navigation={q('SELECT COUNT(*) FROM corpus.current_navigation_nodes')}, "
          f"of which overrides={q('SELECT COUNT(*) FROM corpus.layered_navigation_overrides')}, "
          f"shadowed={q('SELECT COUNT(*) FROM corpus.layered_shadowed_rows')}")

gen = L._create_database(layered=True)
dsn = next(gen)
try:
    for truncate in ("TRUNCATE corpus.navigation_nodes", "TRUNCATE corpus.release_scopes",
                     "TRUNCATE corpus.active_scope_pointer, corpus.scope_activation_history"):
        L._reset(dsn)
        with closing(psycopg2.connect(dsn)) as db, closing(psycopg2.connect(dsn)) as old:
            L._stage(db, *L.LAYERED_SCOPES)
            obj = L._release_object(db, L.LAYERED_RELEASE, L.LAYERED_SCOPES)
            with old.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                cur.execute("SELECT COUNT(*) FROM corpus.release_scopes")
            L._activate(db, obj)
            print(f"[F1] REPEATABLE READ snapshot, then activation, then {truncate}")
            state(db, "after activation")
            err = L._attempt(old, truncate)
            print("  TRUNCATE ->", "refused: " + str(err).splitlines()[0] if err else "committed")
            state(db, "after TRUNCATE")
    # F2, disjoint shadows
    L._reset(dsn)
    with closing(psycopg2.connect(dsn)) as db, L._observer(dsn) as obs:
        one = L._publish(db, "fx-rulespec-2026-09-23-one", L.BASE, L.SECTION_1_2)
        L._publish(db, "fx-rulespec-2026-09-24-two", L.BASE, L.SECTION_2_1)
        L._activate(db, one)
        with db.cursor() as cur:
            cur.execute(L._REFRESH)
        other = L._Background(dsn, L._committing(L._REPOINT, ("fx-rulespec-2026-09-24-two",)))
        L._wait_until_waiting(obs, other)
        db.commit(); other.join()
        print("[F2] direct refresh (uncommitted), then owner repoint to release two, then commit both")
        print("  repoint error:", other.error)
        print("  pointer:", L._rows(db, "SELECT release_name FROM corpus.active_scope_pointer WHERE document_class='statute'"))
        print("  shadowed rows by release:", L._rows(db, "SELECT release_name, citation_path FROM corpus.layered_shadowed_rows ORDER BY 2"))
        print("  fx/statute/1/2 served by current_provisions:", L._rows(db, "SELECT version FROM corpus.current_provisions WHERE citation_path='fx/statute/1/2'"))
        print("  overrides by release:", L._rows(db, "SELECT release_name, path, parent_path FROM corpus.layered_navigation_overrides ORDER BY 2"))
        print("  fx/statute/1/2 served by current_navigation_nodes:", L._rows(db, "SELECT version FROM corpus.current_navigation_nodes WHERE path='fx/statute/1/2'"))
finally:
    gen.close()
