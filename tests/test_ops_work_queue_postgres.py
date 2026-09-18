"""Exercise the checked-in work queue migration in an isolated PostgreSQL DB."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")
errors = pytest.importorskip("psycopg2.errors")
sql = pytest.importorskip("psycopg2.sql")

DATABASE_URL = os.environ.get("DATABASE_URL")
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase/migrations/20260818000000_ops_work_queue.sql"
)
REQUIRED_ROLES = ("anon", "authenticated", "service_role")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for PostgreSQL migration integration tests",
)


@pytest.fixture(scope="module")
def migration_notifications() -> list[tuple[str, str]]:
    return []


@pytest.fixture(scope="module")
def queue_dsn(migration_notifications: list[tuple[str, str]]) -> Iterator[str]:
    assert DATABASE_URL is not None
    database_name = f"axiom_work_queue_{uuid.uuid4().hex}"
    created_roles: list[str] = []
    with closing(psycopg2.connect(DATABASE_URL)) as admin:
        admin.autocommit = True
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)",
                (list(REQUIRED_ROLES),),
            )
            existing_roles = {row[0] for row in cursor.fetchall()}
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
                    cursor.execute("LISTEN pgrst")
                connection.commit()
                with connection.cursor() as cursor:
                    cursor.execute(MIGRATION.read_text(encoding="utf-8"))
                connection.commit()
                connection.poll()
                migration_notifications.extend(
                    (notification.channel, notification.payload)
                    for notification in connection.notifies
                )
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
                    cursor.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


@pytest.fixture
def queue(queue_dsn: str) -> Iterator[str]:
    with closing(psycopg2.connect(queue_dsn)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE ops.work_items, ops.work_queues, ops.priority_events")
            cursor.execute(
                "INSERT INTO ops.work_queues (queue_id, status, source) "
                "VALUES ('test', 'active', 'test-repo@test-sha:inventory.json')"
            )
        connection.commit()
    yield queue_dsn


def _item(
    dsn: str,
    item_id: str,
    *,
    dependencies: list[str | None] | None = None,
    status: str = "pending",
    kind: str = "encode",
    queue_id: str = "test",
    priority: int = 100,
) -> None:
    with closing(psycopg2.connect(dsn)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO ops.work_items "
            "(id, queue_id, kind, payload, depends_on, status, priority, lease_expires_at) "
            "VALUES (%s, %s, %s, '{}'::jsonb, %s, %s, %s, "
            "CASE WHEN %s = 'leased' THEN now() + interval '1 hour' ELSE NULL END)",
            (item_id, queue_id, kind, dependencies or [], status, priority, status),
        )
        connection.commit()


def _claim(dsn: str, *, kinds: list[str] | None = None) -> list[tuple]:
    with closing(psycopg2.connect(dsn)) as connection, connection.cursor() as cursor:
        # Exercise the migration's real grants and default invoker privileges.
        cursor.execute("SET ROLE service_role")
        cursor.execute(
            "SELECT id, claimed_by, attempts, "
            "lease_expires_at = now() + interval '120 seconds' "
            "FROM ops.claim_work('test-agent', %s, 120)",
            (kinds,),
        )
        rows = cursor.fetchall()
        connection.commit()
        return rows


@pytest.mark.parametrize("with_completed_dependency", [False, True])
def test_missing_dependency_stays_pending_until_present_and_completed(
    queue: str, with_completed_dependency: bool
) -> None:
    dependencies = ["missing"]
    if with_completed_dependency:
        _item(queue, "done", status="completed")
        dependencies.insert(0, "done")
    _item(queue, "dependent", dependencies=dependencies)

    assert _claim(queue, kinds=["encode"]) == []
    with closing(psycopg2.connect(queue)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, attempts, claimed_by, lease_expires_at "
            "FROM ops.work_items WHERE id = 'dependent'"
        )
        assert cursor.fetchone() == ("pending", 0, None, None)

    # Insert the dependency after its dependent. It still must complete before
    # the dependent is eligible; its kind prevents claiming it in this test.
    _item(queue, "missing", kind="prepare")
    assert _claim(queue, kinds=["encode"]) == []
    with closing(psycopg2.connect(queue)) as connection, connection.cursor() as cursor:
        cursor.execute("UPDATE ops.work_items SET status = 'completed' WHERE id = 'missing'")
        connection.commit()
    assert _claim(queue, kinds=["encode"]) == [("dependent", "test-agent", 1, True)]


@pytest.mark.parametrize("status", ["pending", "leased", "failed", "blocked", "completed"])
def test_every_existing_dependency_must_be_completed(queue: str, status: str) -> None:
    _item(queue, "first", status="completed")
    _item(queue, "second", status=status, kind="prepare")
    _item(queue, "dependent", dependencies=["first", "second"])
    expected = [("dependent", "test-agent", 1, True)] if status == "completed" else []
    assert _claim(queue, kinds=["encode"]) == expected


@pytest.mark.parametrize("dependencies", [[None], ["done", None]])
def test_null_dependency_id_cannot_be_silently_satisfied(
    queue: str, dependencies: list[str | None]
) -> None:
    _item(queue, "done", status="completed")
    _item(queue, "dependent", dependencies=dependencies)
    assert _claim(queue) == []


def test_empty_dependency_array_is_eligible(queue: str) -> None:
    _item(queue, "independent")
    assert _claim(queue) == [("independent", "test-agent", 1, True)]
    assert _claim(queue) == []


def test_blocked_dependency_does_not_prevent_claiming_lower_priority_work(queue: str) -> None:
    _item(queue, "blocked", dependencies=["absent"], priority=1)
    _item(queue, "ready", priority=2)
    assert _claim(queue) == [("ready", "test-agent", 1, True)]


def test_queue_kind_and_priority_filters_remain_effective(queue: str) -> None:
    with closing(psycopg2.connect(queue)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO ops.work_queues (queue_id, status, source, priority) VALUES "
            "('paused', 'paused', 'test', 1), "
            "('retired', 'retired', 'test', 1), "
            "('preferred', 'active', 'test', 10)"
        )
        connection.commit()
    _item(queue, "paused", queue_id="paused", priority=1)
    _item(queue, "retired", queue_id="retired", priority=1)
    _item(queue, "other-kind", kind="prepare", queue_id="preferred", priority=1)
    _item(queue, "ordinary", priority=1)
    _item(queue, "preferred-b", queue_id="preferred", priority=20)
    _item(queue, "preferred-a", queue_id="preferred", priority=20)
    _item(queue, "preferred-first", queue_id="preferred", priority=10)
    assert [_claim(queue, kinds=["encode"])[0][0] for _ in range(4)] == [
        "preferred-first", "preferred-a", "preferred-b", "ordinary"
    ]
    assert _claim(queue, kinds=["encode"]) == []
    assert _claim(queue, kinds=[]) == []
    assert _claim(queue)[0][0] == "other-kind"


def test_concurrent_claim_skips_locked_item_and_does_not_double_lease(queue: str) -> None:
    _item(queue, "first", priority=1)
    _item(queue, "second", priority=2)
    with closing(psycopg2.connect(queue)) as first, first.cursor() as cursor:
        cursor.execute("SET ROLE service_role")
        cursor.execute("SET statement_timeout = '2s'")
        cursor.execute("SELECT id FROM ops.claim_work('first-agent', null, 120)")
        assert cursor.fetchall() == [("first",)]

        # The first transaction remains open with its row lock held. A second
        # real connection must finish without waiting for that lock or claiming
        # the same item. Bound the wait so a locking regression fails promptly.
        with closing(psycopg2.connect(queue)) as second, second.cursor() as other:
            other.execute("SET ROLE service_role")
            other.execute("SET statement_timeout = '2s'")
            other.execute("SELECT id FROM ops.claim_work('second-agent', null, 120)")
            assert other.fetchall() == [("second",)]
            second.commit()
        first.commit()
    assert _claim(queue) == []
    with closing(psycopg2.connect(queue)) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id, claimed_by, attempts FROM ops.work_items ORDER BY id")
        assert cursor.fetchall() == [("first", "first-agent", 1), ("second", "second-agent", 1)]


def test_rolled_back_claim_does_not_consume_attempt_or_lease(queue: str) -> None:
    _item(queue, "item")
    with closing(psycopg2.connect(queue)) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id FROM ops.claim_work('rolled-back-agent', null, 120)")
        assert cursor.fetchall() == [("item",)]
        connection.rollback()
    assert _claim(queue) == [("item", "test-agent", 1, True)]


def test_only_expired_leases_are_reclaimed(queue: str) -> None:
    _item(queue, "unexpired", status="leased", priority=1)
    _item(queue, "expired", status="leased", priority=2)
    with closing(psycopg2.connect(queue)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ops.work_items SET claimed_by = 'old-agent', attempts = 3, "
            "lease_expires_at = now() + CASE id WHEN 'expired' THEN interval '-1 minute' "
            "ELSE interval '1 hour' END"
        )
        connection.commit()
    assert _claim(queue) == [("expired", "test-agent", 4, True)]
    assert _claim(queue) == []
    with closing(psycopg2.connect(queue)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, claimed_by, attempts, lease_expires_at > now() "
            "FROM ops.work_items WHERE id = 'unexpired'"
        )
        assert cursor.fetchone() == ("leased", "old-agent", 3, True)


@pytest.mark.parametrize("lease_seconds", [None, 0, -1])
def test_invalid_lease_duration_does_not_claim_work(queue: str, lease_seconds: int | None) -> None:
    _item(queue, "item")
    with closing(psycopg2.connect(queue)) as connection, connection.cursor() as cursor:
        cursor.execute("SET ROLE service_role")
        with pytest.raises(errors.InvalidParameterValue, match="lease duration must be positive"):
            cursor.execute("SELECT id FROM ops.claim_work('agent', null, %s)", (lease_seconds,))
        connection.rollback()
        cursor.execute(
            "SELECT status, attempts, claimed_by, lease_expires_at "
            "FROM ops.work_items WHERE id = 'item'"
        )
        assert cursor.fetchone() == ("pending", 0, None, None)
    assert _claim(queue) == [("item", "test-agent", 1, True)]


@pytest.mark.parametrize("operation", ["insert", "update"])
def test_leased_item_requires_an_expiry(queue: str, operation: str) -> None:
    if operation == "update":
        _item(queue, "item")
    with closing(psycopg2.connect(queue)) as connection, connection.cursor() as cursor:
        cursor.execute("SET ROLE service_role")
        with pytest.raises(errors.CheckViolation, match="work_items_leased_expiry_required"):
            if operation == "insert":
                cursor.execute(
                    "INSERT INTO ops.work_items (id, queue_id, kind, payload, status) "
                    "VALUES ('item', 'test', 'encode', '{}', 'leased')"
                )
            else:
                cursor.execute("UPDATE ops.work_items SET status = 'leased' WHERE id = 'item'")
        connection.rollback()


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_claim_rpc_is_not_executable_by_non_service_roles(queue: str, role: str) -> None:
    with closing(psycopg2.connect(queue)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_function_privilege(%s, 'ops.claim_work(text,text[],integer)', 'EXECUTE')",
            (role,),
        )
        assert cursor.fetchone() == (False,)
        # Even future read-only schema exposure must not expose the claim RPC.
        # Keep this hypothetical grant inside the rolled-back test transaction.
        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA ops TO {}").format(sql.Identifier(role)))
        cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        with pytest.raises(errors.InsufficientPrivilege, match="permission denied for function claim_work"):
            cursor.execute("SELECT id FROM ops.claim_work('untrusted', null, 120)")
        connection.rollback()


def test_reclaim_skips_locked_expired_lease(queue: str) -> None:
    _item(queue, "held", status="leased", priority=1)
    _item(queue, "expired", status="leased", priority=2)
    _item(queue, "pending", priority=3)
    with closing(psycopg2.connect(queue)) as first, first.cursor() as cursor:
        cursor.execute(
            "UPDATE ops.work_items SET lease_expires_at = now() - interval '1 minute' "
            "WHERE status = 'leased'"
        )
        first.commit()
        cursor.execute("SET ROLE service_role")
        cursor.execute("SELECT id FROM ops.work_items WHERE id = 'held' FOR UPDATE")
        assert cursor.fetchone() == ("held",)
        with closing(psycopg2.connect(queue)) as second, second.cursor() as other:
            other.execute("SET ROLE service_role")
            other.execute("SET statement_timeout = '2s'")
            for expected in ("expired", "pending"):
                other.execute("SELECT id FROM ops.claim_work('second-agent', null, 120)")
                assert other.fetchall() == [(expected,)]
                second.commit()
        first.commit()
    assert _claim(queue) == [("held", "test-agent", 1, True)]


def test_migration_notifies_postgrest(
    queue_dsn: str, migration_notifications: list[tuple[str, str]]
) -> None:
    assert migration_notifications == [("pgrst", "reload schema")]
