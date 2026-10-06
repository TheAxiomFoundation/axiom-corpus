"""Scratch: median time to apply the file (rolled back) to the small layered
fixture database, first application and re-application, 20 runs each."""
import statistics, time
from contextlib import closing
import psycopg2
import tests.test_layered_serving_postgres as L

text = L.LAYERED_SERVING_MIGRATION.read_text(encoding="utf-8")
for layered, label in ((False, "first application"), (True, "re-application")):
    gen = L._create_database(layered=layered)
    dsn = next(gen)
    try:
        with closing(psycopg2.connect(dsn)) as c:
            if layered:
                L._publish_layered(c)
            else:
                L._publish(c, "fx-rulespec-2026-09-01", L.PRIMARY_TITLE, L.OTHER_PAIR)
            times = []
            for _ in range(20):
                t = time.monotonic()
                with c.cursor() as cur:
                    cur.execute(text)
                times.append((time.monotonic() - t) * 1000)
                c.rollback()
        print(f"{label}: median {statistics.median(times):.1f} ms (min {min(times):.1f}, max {max(times):.1f})")
    finally:
        gen.close()
