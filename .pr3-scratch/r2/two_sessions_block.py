# ---------------------------------------------------------------------------
# Two sessions: interleavings that a single connection cannot show.
# ---------------------------------------------------------------------------


class _Background:
    """Statements on a connection of their own, run in a thread, so that
    another session can be interleaved with them. Records the backend pid, the
    work's result and any error it raised (after rolling back)."""

    def __init__(self, dsn: str, work: Callable[[Any], Any]) -> None:
        self.connection = psycopg2.connect(dsn)
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            (self.pid,) = cursor.fetchone()
        self.connection.commit()
        self.result: Any = None
        self.error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, args=(work,), daemon=True)
        self._thread.start()

    def _run(self, work: Callable[[Any], Any]) -> None:
        try:
            self.result = work(self.connection)
        except BaseException as exc:  # noqa: BLE001 - surfaced to the test thread
            self.error = exc
            self.connection.rollback()

    def join(self, timeout: float = 30.0) -> None:
        self._thread.join(timeout)
        assert not self._thread.is_alive(), "background session did not finish"
        self.connection.close()


def _committing(statement: str, params: Sequence[Any] = ()) -> Callable[[Any], Any]:
    def work(connection: Any) -> None:
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
        connection.commit()

    return work


@contextmanager
def _observer(dsn: str) -> Iterator[Any]:
    with closing(psycopg2.connect(dsn)) as connection:
        connection.autocommit = True
        yield connection


def _wait_until_waiting(observer: Any, session: _Background, relation: str | None = None) -> None:
    """Return once ``session`` waits for a lock: any lock, or one on ``relation``."""
    query = "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE pid = %s AND NOT granted"
    params: list[Any] = [session.pid]
    if relation is not None:
        query += " AND relation = to_regclass(%s)"
        params.append(relation)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with observer.cursor() as cursor:
            cursor.execute(query + ")", params)
            if cursor.fetchone()[0]:
                return
        assert session._thread.is_alive(), session.error
        time.sleep(0.02)
    raise AssertionError(f"session {session.pid} never waited for {relation or 'a lock'}")


def _held(observer: Any, session: _Background, mode: str | None = None) -> set[str]:
    """Relations ``session`` holds a lock on, in ``mode`` if given."""
    query = (
        "SELECT DISTINCT relation::regclass::text FROM pg_locks "
        "WHERE pid = %s AND granted AND locktype = 'relation'"
    )
    params: list[Any] = [session.pid]
    if mode is not None:
        query += " AND mode = %s"
        params.append(mode)
    with observer.cursor() as cursor:
        cursor.execute(query, params)
        return {row[0] for row in cursor.fetchall()}


_SNAPSHOT_ISOLATIONS = ("REPEATABLE READ", "SERIALIZABLE")
_TRUNCATES = {
    "navigation": "TRUNCATE corpus.navigation_nodes",
    "provisions": "TRUNCATE corpus.provisions CASCADE",
    "membership": "TRUNCATE corpus.release_scopes",
    "pointers": "TRUNCATE corpus.active_scope_pointer, corpus.scope_activation_history",
}


@pytest.mark.parametrize("isolation", _SNAPSHOT_ISOLATIONS)
@pytest.mark.parametrize("truncate", list(_TRUNCATES))
def test_truncate_under_a_snapshot_older_than_an_activation_is_refused(
    layered_dsn: str, db: Any, isolation: str, truncate: str
) -> None:
    """Review round 2, Sol P1. TRUNCATE is not MVCC-safe: it removes every row,
    including rows its transaction's snapshot cannot see, so a guard that reads
    that snapshot can let it remove a release activated after the snapshot."""
    _stage(db, *LAYERED_SCOPES)
    release_object = _release_object(db, LAYERED_RELEASE, LAYERED_SCOPES)
    with closing(psycopg2.connect(layered_dsn)) as old:
        with old.cursor() as cursor:
            cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
            # The snapshot: nothing is released yet.
            cursor.execute("SELECT COUNT(*) FROM corpus.release_scopes")
            assert cursor.fetchone() == (0,)
        # Another session activates a layered release and commits.
        _activate(db, release_object)
        served = _snapshot(db)
        stored = _stored(db)
        error = _attempt(old, _TRUNCATES[truncate])
    assert isinstance(error, errors.RaiseException), error
    assert "only under READ COMMITTED" in str(error)
    _assert_serving_is_consistent(db)
    assert _snapshot(db) == served
    assert _stored(db) == stored


@pytest.mark.parametrize("truncate", list(_TRUNCATES))
def test_truncate_waiting_on_an_activation_sees_what_it_committed(
    layered_dsn: str, db: Any, truncate: str
) -> None:
    """Under READ COMMITTED, TRUNCATE takes ACCESS EXCLUSIVE before its guard
    runs and each statement of the guard reads a fresh snapshot, so a TRUNCATE
    that waited on an activation sees everything the activation committed."""
    _stage(db, *LAYERED_SCOPES)
    release_object = _release_object(db, LAYERED_RELEASE, LAYERED_SCOPES)
    with closing(psycopg2.connect(layered_dsn)) as activation, _observer(layered_dsn) as observer:
        with activation.cursor() as cursor:
            cursor.execute(
                "SELECT corpus.activate_corpus_release(%s::jsonb)", (Json(release_object),)
            )
        truncating = _Background(layered_dsn, _committing(_TRUNCATES[truncate]))
        _wait_until_waiting(observer, truncating)
        activation.commit()
        truncating.join()
    if truncate == "pointers":
        # Removing every pointer un-serves everything, and nothing stays derived.
        assert truncating.error is None
        assert _rows(db, "SELECT COUNT(*) FROM corpus.layered_shadowed_rows") == [(0,)]
        assert _rows(db, "SELECT COUNT(*) FROM corpus.layered_navigation_overrides") == [(0,)]
        assert _rows(db, "SELECT COUNT(*) FROM corpus.current_navigation_nodes") == [(0,)]
    else:
        assert isinstance(truncating.error, errors.RaiseException), truncating.error
        assert "immutable" in str(truncating.error)
        assert _rows(db, "SELECT COUNT(*) FROM corpus.layered_shadowed_rows") != [(0,)]
    _assert_serving_is_consistent(db)


# Two layered releases over one base whose primary scopes re-encode different
# sections without their titles, so their shadowed paths and navigation
# overrides are disjoint; and a third that shadows what the first does.
SECTION_1_2 = Scope(
    "fx",
    "statute",
    "2026-09-23-section-1-2",
    (Node("fx/statute/1/2", "fx/statute/1", "Section 1-2 (encoded)", 2),),
)
SECTION_2_1 = Scope(
    "fx",
    "statute",
    "2026-09-23-section-2-1",
    (Node("fx/statute/2/1", "fx/statute/2", "Section 2-1 (encoded)", 1),),
)
SECTION_1_2_AGAIN = replace(SECTION_1_2, version="2026-09-24-section-1-2")
_REPOINT = (
    "UPDATE corpus.active_scope_pointer AS active "
    "SET release_name = objects.release_name, content_sha256 = objects.content_sha256 "
    "FROM corpus.release_objects objects WHERE objects.release_name = %s "
    "AND active.jurisdiction = 'fx' AND active.document_class = 'statute'"
)
_REFRESH = "SELECT corpus.refresh_layered_serving('fx', 'statute')"


@pytest.mark.parametrize(
    ("successor", "first"),
    [
        pytest.param(SECTION_2_1, "refresh", id="refresh-first-disjoint-shadows"),
        pytest.param(SECTION_1_2_AGAIN, "refresh", id="refresh-first-same-shadows"),
        pytest.param(SECTION_2_1, "pointer", id="pointer-first"),
    ],
)
def test_a_direct_refresh_is_ordered_against_an_owner_pointer_write(
    layered_dsn: str, db: Any, successor: Scope, first: str
) -> None:
    """Review round 2, both reviewers: a direct refresh_layered_serving() and an
    owner's pointer UPDATE of the same pair, interleaved. Whichever runs first,
    the pair ends up derived from the release its pointer names."""
    one = _publish(db, "fx-rulespec-2026-09-23-one", BASE, SECTION_1_2)
    _publish(db, "fx-rulespec-2026-09-24-two", BASE, successor)
    expected = _snapshot(db)
    _activate(db, one)
    with _observer(layered_dsn) as observer:
        if first == "refresh":
            # The refresh re-derives the first release's rows, uncommitted ...
            with db.cursor() as cursor:
                cursor.execute(_REFRESH)
            # ... while the owner repoints the pair to the second.
            other = _Background(layered_dsn, _committing(_REPOINT, ("fx-rulespec-2026-09-24-two",)))
        else:
            with db.cursor() as cursor:
                cursor.execute(_REPOINT, ("fx-rulespec-2026-09-24-two",))
            other = _Background(layered_dsn, _committing(_REFRESH))
        _wait_until_waiting(observer, other)
        db.commit()
        other.join()
    assert other.error is None, other.error
    _assert_serving_is_consistent(db)
    after = _snapshot(db)
    for part in ("pointers", "shadowed", "overrides"):
        assert after[part] == expected[part], part


_UNLAYERED_RELEASE = "fx-rulespec-2026-09-01"


@pytest.mark.parametrize("isolation", _SNAPSHOT_ISOLATIONS)
def test_unlayered_releases_activate_and_move_under_any_isolation(
    db: Any, isolation: str
) -> None:
    """Review round 2: requirement 1, no behavior change for releases without a
    base scope. Activating one, its successor, a rollback, a reaffirm, hand
    repoints, a pointer removal and restore, and a membership insert all work
    as before under REPEATABLE READ and SERIALIZABLE."""
    _stage(db, PRIMARY_TITLE, PRIMARY_SECTIONS, OTHER_PAIR, STRAY)
    first = _release_object(db, _UNLAYERED_RELEASE, (PRIMARY_TITLE, OTHER_PAIR))
    second = _release_object(db, "fx-rulespec-2026-09-02", (PRIMARY_SECTIONS, OTHER_PAIR))
    registered = _release_object(db, "fx-rulespec-2026-09-03", (STRAY,))
    _stage_object(db, registered)

    def under_isolation(statement: str, params: Sequence[Any] = ()) -> None:
        with db.cursor() as cursor:
            cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
            cursor.execute(statement, params)
        db.commit()

    for release_object in (first, second, first, first):
        under_isolation("SELECT corpus.activate_corpus_release(%s::jsonb)", (Json(release_object),))
        _assert_matches_reference(db)
    under_isolation(_REPOINT, ("fx-rulespec-2026-09-02",))
    under_isolation(
        "DELETE FROM corpus.active_scope_pointer "
        "WHERE jurisdiction = 'fx' AND document_class = 'regulation'"
    )
    under_isolation(
        "INSERT INTO corpus.active_scope_pointer (jurisdiction, document_class, release_name, "
        "content_sha256) SELECT 'fx', 'regulation', release_name, content_sha256 "
        "FROM corpus.release_objects WHERE release_name = %s",
        (_UNLAYERED_RELEASE,),
    )
    under_isolation(
        "INSERT INTO corpus.release_scopes (release_name, jurisdiction, document_class, version) "
        "VALUES ('fx-rulespec-2026-09-03', 'fx', 'statute', %s)",
        (STRAY.version,),
    )
    # Counts follow activation, not a hand repoint, as before this migration.
    _rows(db, "REFRESH MATERIALIZED VIEW corpus.current_provision_counts")
    _assert_matches_reference(db)


@pytest.mark.parametrize("isolation", _SNAPSHOT_ISOLATIONS)
def test_layered_serving_still_moves_only_under_read_committed(db: Any, isolation: str) -> None:
    """The other half of requirement 1: whatever involves a release with a base
    scope for the pair still runs only under READ COMMITTED, and is refused
    whole otherwise."""
    _publish(db, _UNLAYERED_RELEASE, PRIMARY_TITLE, OTHER_PAIR)
    _stage(db, *LAYERED_SCOPES)
    layered = _release_object(db, LAYERED_RELEASE, LAYERED_SCOPES)
    unlayered = _release_object(db, _UNLAYERED_RELEASE, (PRIMARY_TITLE, OTHER_PAIR))

    def refused(statement: str, params: Sequence[Any] = ()) -> None:
        before = _snapshot(db)
        with db.cursor() as cursor:
            cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
            with pytest.raises(errors.RaiseException, match="only under READ COMMITTED"):
                cursor.execute(statement, params)
        db.rollback()
        assert _snapshot(db) == before

    activate = "SELECT corpus.activate_corpus_release(%s::jsonb)"
    # Moving an unlayered pair to a layered release.
    refused(activate, (Json(layered),))
    _activate(db, layered)
    # Moving a layered pair to an unlayered release, by activation or by hand,
    # and removing its pointer.
    refused(activate, (Json(unlayered),))
    refused(_REPOINT, (_UNLAYERED_RELEASE,))
    refused("DELETE FROM corpus.active_scope_pointer WHERE document_class = 'statute'")
    # The unlayered pair of the layered release moves freely.
    with db.cursor() as cursor:
        cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
        cursor.execute(
            "DELETE FROM corpus.active_scope_pointer WHERE document_class = 'regulation'"
        )
    db.commit()
    _assert_serving_is_consistent(db)


# What the layered migration takes ACCESS EXCLUSIVE on, in the order every
# serving read takes its locks: a read locks the relation it names, then the
# relations that relation's definition or policy names (current_release_scopes
# before release_scopes, which it is defined over).
_EXCLUSIVE_LOCK_ORDER = (
    "corpus.current_provisions",
    "corpus.legacy_provisions",
    "corpus.current_navigation_nodes",
    "corpus.navigation_nodes",
    "corpus.current_release_scopes",
    "corpus.release_scopes",
)
# Every serving read of the fixture schema, as the role that makes it.
_SERVING_READS = {
    "current_provisions": (
        "anon",
        "SELECT id FROM corpus.current_provisions WHERE citation_path = 'fx/statute/1/1'",
    ),
    "current_navigation_nodes": (
        "anon",
        "SELECT id FROM corpus.current_navigation_nodes WHERE jurisdiction = 'fx' "
        "ORDER BY citation_path LIMIT 1000",
    ),
    "navigation_nodes": (
        "anon",
        "SELECT id FROM corpus.navigation_nodes WHERE parent_path = 'fx/statute/1'",
    ),
    "current_release_scopes": (
        "anon",
        "SELECT * FROM corpus.current_release_scopes WHERE jurisdiction = 'fx'",
    ),
    "legacy_provisions": ("service_role", "SELECT id FROM corpus.legacy_provisions"),
    "rpc/get_root_document_counts": ("anon", "SELECT * FROM corpus.get_root_document_counts()"),
    "rpc/get_provision_references": (
        "anon",
        "SELECT * FROM corpus.get_provision_references('fx/statute/1/1')",
    ),
}


def _lock_exclusively(connection: Any, relation: str) -> None:
    """ACCESS EXCLUSIVE on ``relation`` alone. LOCK TABLE on a view also locks
    every relation of its definition, so a view is locked by setting its owner
    to its owner, which changes nothing."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relkind, pg_get_userbyid(relowner) FROM pg_class WHERE oid = to_regclass(%s)",
            (relation,),
        )
        kind, owner = cursor.fetchone()
        if kind == "v":
            cursor.execute(
                sql.SQL("ALTER VIEW {} OWNER TO {}").format(
                    sql.SQL(relation), sql.Identifier(owner)
                )
            )
        else:
            cursor.execute(
                sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(sql.SQL(relation))
            )


def _reading(role: str, query: str) -> Callable[[Any], Any]:
    def work(connection: Any) -> list[tuple[Any, ...]]:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
            cursor.execute(query)
            rows = cursor.fetchall()
        connection.rollback()
        return rows

    return work


@pytest.mark.parametrize("blocked_at", _EXCLUSIVE_LOCK_ORDER)
def test_serving_reads_take_their_locks_in_the_order_the_file_takes_its_own(
    layered_dsn: str, db: Any, blocked_at: str
) -> None:
    """Review round 2, Opus 1. A read that waits for one of the file's
    relations must hold none that the file locks after it: otherwise the read
    waits for the file while the file waits for the read."""
    _publish_layered(db)
    later = set(_EXCLUSIVE_LOCK_ORDER[_EXCLUSIVE_LOCK_ORDER.index(blocked_at) + 1 :])
    with _observer(layered_dsn) as observer:
        for read, (role, query) in _SERVING_READS.items():
            with closing(psycopg2.connect(layered_dsn)) as holder:
                _lock_exclusively(holder, blocked_at)
                reader = _Background(layered_dsn, _reading(role, query))
                deadline = time.monotonic() + 2
                waiting = False
                while time.monotonic() < deadline and reader._thread.is_alive():
                    with observer.cursor() as cursor:
                        cursor.execute(
                            "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE pid = %s AND NOT granted)",
                            (reader.pid,),
                        )
                        waiting = cursor.fetchone()[0]
                    if waiting:
                        break
                    time.sleep(0.02)
                if waiting:
                    assert not (_held(observer, reader) & later), (read, blocked_at)
                holder.rollback()
                reader.join()
                assert reader.error is None, (read, reader.error)


def _applying(connection: Any) -> None:
    with connection.cursor() as cursor:
        cursor.execute(LAYERED_SERVING_MIGRATION.read_text(encoding="utf-8"))
    connection.rollback()


@pytest.fixture(scope="module")
def first_application_dsn() -> Iterator[str]:
    """A database before the layered migration, serving an unlayered release.
    Every test applies the file and rolls it back."""
    for dsn in _create_database(layered=False):
        with closing(psycopg2.connect(dsn)) as connection:
            _publish(connection, _UNLAYERED_RELEASE, PRIMARY_TITLE, OTHER_PAIR)
        yield dsn


@pytest.fixture(params=["first application", "re-application"])
def applied_dsn(request: Any, first_application_dsn: str, layered_dsn: str, db: Any) -> str:
    if request.param == "first application":
        return first_application_dsn
    _publish_layered(db)
    return layered_dsn


@pytest.mark.parametrize("blocked_at", _EXCLUSIVE_LOCK_ORDER)
def test_the_file_takes_its_exclusive_locks_first_in_the_order_reads_take_theirs(
    applied_dsn: str, blocked_at: str
) -> None:
    """Review round 2, Opus 1: with a read in flight on one of its relations,
    the file waits there first, holding ACCESS EXCLUSIVE on none that a read
    takes after it."""
    later = set(_EXCLUSIVE_LOCK_ORDER[_EXCLUSIVE_LOCK_ORDER.index(blocked_at) + 1 :])
    with closing(psycopg2.connect(applied_dsn)) as holder, _observer(applied_dsn) as observer:
        with holder.cursor() as cursor:
            # A read in flight: ACCESS SHARE on the relation and, for a view,
            # on every relation beneath it.
            cursor.execute(
                sql.SQL("LOCK TABLE {} IN ACCESS SHARE MODE").format(sql.SQL(blocked_at))
            )
        applying = _Background(applied_dsn, _applying)
        _wait_until_waiting(observer, applying)
        with observer.cursor() as cursor:
            cursor.execute(
                "SELECT relation::regclass::text FROM pg_locks "
                "WHERE pid = %s AND NOT granted AND locktype = 'relation'",
                (applying.pid,),
            )
            assert cursor.fetchall() == [(blocked_at,)]
        assert not (_held(observer, applying, "AccessExclusiveLock") & later), blocked_at
        holder.rollback()
        applying.join()
    assert applying.error is None, applying.error


@pytest.mark.parametrize("read", ["current_provisions", "current_navigation_nodes", "navigation_nodes"])
def test_applying_the_file_under_serving_reads_does_not_deadlock(
    applied_dsn: str, read: str
) -> None:
    """Review round 2, Opus 1, reproduced: a read in flight on
    current_release_scopes makes the file wait; a second read arrives and
    queues behind the file; once the first read ends, the file and the second
    read both finish (the file rolls back here), and the second read returns
    what a read after the file returns."""
    role, query = _SERVING_READS[read]
    with closing(psycopg2.connect(applied_dsn)) as in_flight, _observer(applied_dsn) as observer:
        with in_flight.cursor() as cursor:
            cursor.execute("SET ROLE anon")
            cursor.execute("SELECT * FROM corpus.current_release_scopes")
        applying = _Background(applied_dsn, _applying)
        _wait_until_waiting(observer, applying)
        queued = _Background(applied_dsn, _reading(role, query))
        _wait_until_waiting(observer, queued)
        in_flight.rollback()
        applying.join()
        queued.join()
    assert applying.error is None, applying.error
    assert queued.error is None, queued.error
    with closing(psycopg2.connect(applied_dsn)) as check:
        assert queued.result == _reading(role, query)(check)


