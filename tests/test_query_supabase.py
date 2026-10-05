"""Tests for the query supabase module.

Tests cover Rule/Section dataclasses and SupabaseQuery class.
HTTP calls are mocked, or served by an emulated PostgREST over rows built by
the corpus's own projection and navigation code.
"""

import os
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.navigation import build_navigation_nodes
from axiom_corpus.corpus.supabase import iter_supabase_rows
from axiom_corpus.query.supabase import CHILD_ID_BATCH, Rule, Section, SupabaseQuery


def _make_rule(**kwargs):
    defaults = {
        "id": "us/statute/26/32",
        "jurisdiction": "us",
        "doc_type": "statute",
        "parent_id": None,
        "level": 0,
        "ordinal": 1,
        "heading": "Earned income tax credit",
        "body": "A tax credit is allowed...",
        "effective_date": "2024-01-01",
        "repeal_date": None,
        "source_url": "https://uscode.house.gov",
        "source_path": "26/32",
        "rulespec_path": "rulespec-us/statutes/26/32.yaml",
        "has_rulespec": True,
        "citation_path": "us/statute/26/32",
    }
    defaults.update(kwargs)
    return Rule(**defaults)


class TestRule:
    def test_create(self):
        rule = _make_rule()
        assert rule.id == "us/statute/26/32"
        assert rule.jurisdiction == "us"
        assert rule.has_rulespec is True

    def test_optional_fields(self):
        rule = _make_rule(
            heading=None,
            body=None,
            effective_date=None,
            repeal_date=None,
            source_url=None,
            source_path=None,
            rulespec_path=None,
            citation_path=None,
            ordinal=None,
        )
        assert rule.heading is None
        assert rule.body is None


class TestSection:
    def test_create(self):
        rule = _make_rule()
        section = Section(rule=rule, children=[])
        assert section.rule is rule
        assert section.children == []

    def test_full_text_no_children(self):
        rule = _make_rule()
        section = Section(rule=rule, children=[])
        text = section.full_text
        assert "Earned income tax credit" in text
        assert "A tax credit" in text

    def test_full_text_with_children(self):
        parent = _make_rule(heading="Main heading", body="Main body")
        child1 = _make_rule(heading="Sub A", body="Sub A body")
        child2 = _make_rule(heading="Sub B", body="Sub B body")

        section = Section(rule=parent, children=[child1, child2])
        text = section.full_text
        assert "Main heading" in text
        assert "Sub A" in text
        assert "Sub B" in text

    def test_full_text_no_heading(self):
        rule = _make_rule(heading=None)
        section = Section(rule=rule, children=[])
        text = section.full_text
        assert "A tax credit" in text

    def test_full_text_no_body(self):
        rule = _make_rule(body=None)
        section = Section(rule=rule, children=[])
        text = section.full_text
        assert "Earned income tax credit" in text

    def test_citation_with_source_path(self):
        rule = _make_rule(source_path="26/32")
        section = Section(rule=rule, children=[])
        assert section.citation == "us/statute/26/32"

    def test_citation_without_source_path(self):
        rule = _make_rule(source_path=None)
        section = Section(rule=rule, children=[])
        assert section.citation == "us/statute/26/32"


class TestSupabaseQuery:
    def test_init_defaults(self):
        with patch.dict(os.environ, {"SUPABASE_ANON_KEY": "test-key"}):
            query = SupabaseQuery()
        assert query.url is not None
        assert query.anon_key is not None
        assert "rest/v1" in query.rest_url

    def test_init_has_public_anon_key_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            query = SupabaseQuery()
        assert query.url is not None
        assert query.anon_key
        assert query.headers["Accept-Profile"] == "corpus"

    def test_init_with_explicit_url(self):
        query = SupabaseQuery(
            url="https://test.supabase.co",
            anon_key="test-key",
        )
        assert query.url == "https://test.supabase.co"
        assert query.anon_key == "test-key"
        assert query.rest_url == "https://test.supabase.co/rest/v1"
        assert query.headers["apikey"] == "test-key"
        assert query.provisions_table == "current_provisions"
        assert query.provision_counts_table == "current_provision_counts"

    def test_init_can_include_legacy_rows(self):
        query = SupabaseQuery(
            url="https://test.supabase.co",
            anon_key="test-key",
            include_legacy=True,
        )
        assert query.provisions_table == "provisions"
        assert query.provision_counts_table == "provision_counts"

    def test_init_prefers_service_key_for_legacy_rows(self):
        with patch.dict(
            os.environ,
            {
                "SUPABASE_ANON_KEY": "anon-key",
                "SUPABASE_SERVICE_ROLE_KEY": "service-key",
            },
            clear=True,
        ):
            query = SupabaseQuery(
                url="https://test.supabase.co",
                include_legacy=True,
            )

        assert query.anon_key == "service-key"
        assert query.provisions_table == "provisions"

    def test_init_from_env(self):
        with patch.dict(
            os.environ,
            {"AXIOM_SUPABASE_URL": "https://env.supabase.co", "SUPABASE_ANON_KEY": "env-key"},
        ):
            query = SupabaseQuery()
            assert query.url == "https://env.supabase.co"

    def test_normalizes_us_code_shorthand(self):
        assert SupabaseQuery._normalize_citation_path("26/32") == "us/statute/26/32"
        assert SupabaseQuery._normalize_citation_path("usc/26/32") == "us/statute/26/32"

    def test_normalizes_full_citation_path(self):
        assert SupabaseQuery._normalize_citation_path("us/statute/26/32") == "us/statute/26/32"
        assert (
            SupabaseQuery._normalize_citation_path("statute/tax/606", jurisdiction="us-ny")
            == "us-ny/statute/tax/606"
        )

    def test_get_section_queries_citation_path(self):
        query = SupabaseQuery(url="https://test.supabase.co", anon_key="test-key")
        data = _make_rule().__dict__

        with patch.object(query, "_request", return_value=[data]) as request:
            result = query.get_section("26/32")

        assert result is not None
        assert result.citation_path == "us/statute/26/32"
        request.assert_called_once()
        table, params = request.call_args.args
        assert table == "current_provisions"
        assert params["citation_path"] == "eq.us/statute/26/32"
        assert params["jurisdiction"] == "eq.us"
        assert "source_path" not in params

    def test_get_section_deep_queries_descendants_by_citation_path(self):
        query = SupabaseQuery(url="https://test.supabase.co", anon_key="test-key")
        parent = _make_rule().__dict__
        child = _make_rule(
            id="us/statute/26/32/a",
            citation_path="us/statute/26/32/a",
            parent_id=parent["id"],
        ).__dict__

        with patch.object(query, "_request", side_effect=[[parent], [child]]) as request:
            section = query.get_section_with_children("26/32", deep=True)

        assert section is not None
        assert [c.citation_path for c in section.children] == ["us/statute/26/32/a"]
        child_table, child_params = request.call_args_list[1].args
        assert child_table == "current_provisions"
        assert child_params == [
            ("citation_path", "gte.us/statute/26/32/"),
            ("citation_path", "lt.us/statute/26/320"),
            ("jurisdiction", "eq.us"),
            ("order", "citation_path"),
            ("limit", "1000"),
        ]
        assert all(name != "source_path" for name, _ in child_params)

    def test_get_section_children_of_legacy_rows_use_parent_ids(self):
        query = SupabaseQuery(
            url="https://test.supabase.co",
            anon_key="test-key",
            include_legacy=True,
        )
        parent = _make_rule().__dict__
        child = _make_rule(id="us/statute/26/32/a", parent_id=parent["id"]).__dict__

        with patch.object(query, "_request", side_effect=[[parent], [child]]) as request:
            section = query.get_section_with_children("26/32")

        assert section is not None
        assert [c.id for c in section.children] == ["us/statute/26/32/a"]
        table, params = request.call_args_list[1].args
        assert table == "provisions"
        assert params == {"parent_id": f"eq.{parent['id']}", "order": "ordinal"}

    def test_search_orders_by_citation_path(self):
        query = SupabaseQuery(url="https://test.supabase.co", anon_key="test-key")

        with patch.object(query, "_request", return_value=[]) as request:
            query.search("earned income", jurisdiction="us")

        table, params = request.call_args.args
        assert table == "current_provisions"
        assert params["order"] == "jurisdiction,citation_path"

    def test_get_stats_reads_current_counts_by_default(self):
        query = SupabaseQuery(url="https://test.supabase.co", anon_key="test-key")

        with patch.object(
            query,
            "_request",
            return_value=[
                {"jurisdiction": "us", "provision_count": 2},
                {"jurisdiction": "us-co", "provision_count": "3"},
            ],
        ) as request:
            stats = query.get_stats()

        table, params = request.call_args.args
        assert table == "current_provision_counts"
        assert params["select"] == "jurisdiction,provision_count"
        assert stats == {"us": 2, "us-co": 3, "total": 5}


# ---------------------------------------------------------------------------
# Direct children, through an emulated PostgREST.
# ---------------------------------------------------------------------------


class _EmulatedPostgrest:
    """The part of PostgREST the query client uses, over in-memory rows.

    Filters ``eq.``, ``in.(...)``, ``gte.``, ``lt.`` and ``is.null``; ``order``
    by ascending columns with nulls last, as PostgreSQL orders them; ``limit``,
    ``offset`` and ``select``. A filter or selected column the relation lacks is
    an error, as PostgREST answers 400. Every response is capped at
    ``max_rows`` rows, as db-max-rows caps it (1,000 on Supabase by default).
    """

    def __init__(
        self,
        tables: Mapping[str, Sequence[Mapping[str, Any]]],
        *,
        columns: Mapping[str, Iterable[str]] | None = None,
        max_rows: int = 1000,
    ) -> None:
        self.tables = {name: [dict(row) for row in rows] for name, rows in tables.items()}
        self.columns = {
            name: set((columns or {}).get(name, ())) | {key for row in rows for key in row}
            for name, rows in tables.items()
        }
        self.max_rows = max_rows
        self.requests: list[tuple[str, list[tuple[str, str]]]] = []

    def __call__(
        self, table: str, params: Any = None, single: bool = False
    ) -> list[dict[str, Any]]:
        items = list(params.items()) if isinstance(params, Mapping) else list(params or [])
        self.requests.append((table, items))
        rows = list(self.tables[table])
        known = self.columns[table]
        order, limit, offset, select = "", None, 0, "*"
        for key, value in items:
            if key == "order":
                order = value
            elif key == "limit":
                limit = int(value)
            elif key == "offset":
                offset = int(value)
            elif key == "select":
                select = value
            else:
                if key not in known:
                    raise ValueError(f"column {table}.{key} does not exist")
                rows = [row for row in rows if _matches(row.get(key), value)]
        for column in reversed([c for c in order.split(",") if c]):
            name = column.removesuffix(".asc")
            rows.sort(key=lambda row, name=name: (row.get(name) is None, row.get(name) or 0))
        rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]
        rows = rows[: self.max_rows]
        if select == "*":
            return [dict(row) for row in rows]
        selected = select.split(",")
        for name in selected:
            if name not in known:
                raise ValueError(f"column {table}.{name} does not exist")
        return [{name: row.get(name) for name in selected} for row in rows]


def _matches(value: Any, spec: str) -> bool:
    operator, _, operand = spec.partition(".")
    if operator == "is":
        assert operand == "null", spec
        return value is None
    if value is None:
        return False
    if operator == "eq":
        return str(value) == operand
    if operator == "in":
        return str(value) in operand.removeprefix("(").removesuffix(")").split(",")
    if operator == "gte":
        return str(value) >= operand
    if operator == "lt":
        return str(value) < operand
    raise AssertionError(spec)


Tree = Sequence[tuple[str, str | None, int | None]]


def _records(version: str, tree: Tree) -> list[ProvisionRecord]:
    """One staged scope of fx/statute: (path, declared parent, ordinal) per row."""
    return [
        ProvisionRecord(
            jurisdiction="fx",
            document_class="statute",
            citation_path=path,
            parent_citation_path=parent,
            version=version,
            heading=f"Heading {path}",
            body=f"Text of {path} in {version}.",
            ordinal=ordinal,
            source_path=f"sources/fx/statute/{version}/source.xml",
            expression_date="2026-09-01",
        )
        for path, parent, ordinal in tree
    ]


def _release_scopes(
    versions: Sequence[str], *, base: str | None, layer_column: bool
) -> list[dict[str, Any]]:
    rows = []
    for version in versions:
        row: dict[str, Any] = {
            "release_name": "fx-rulespec",
            "jurisdiction": "fx",
            "document_class": "statute",
            "version": version,
            "synced_at": "2026-10-01T00:00:00Z",
        }
        if layer_column:
            row["layer"] = "base" if version == base else "primary"
        rows.append(row)
    return rows


_SCOPE_COLUMNS = ("release_name", "jurisdiction", "document_class", "version", "synced_at")


def _unlayered_postgrest(
    scopes: Mapping[str, Tree], *, layer_column: bool = True, max_rows: int = 1000
) -> _EmulatedPostgrest:
    """A pair served without a base scope: every served scope's rows as staged."""
    records = {version: _records(version, tree) for version, tree in scopes.items()}
    return _EmulatedPostgrest(
        {
            "current_provisions": [
                row for scope in records.values() for row in iter_supabase_rows(scope)
            ],
            "current_navigation_nodes": [
                node.to_supabase_row()
                for scope in records.values()
                for node in build_navigation_nodes(scope)
            ],
            "current_release_scopes": _release_scopes(
                list(scopes), base=None, layer_column=layer_column
            ),
        },
        columns={"current_release_scopes": _SCOPE_COLUMNS + (("layer",) if layer_column else ())},
        max_rows=max_rows,
    )


def _layered_postgrest(
    base: Tree,
    primaries: Mapping[str, Tree],
    *,
    max_rows: int = 1000,
    extra_navigation: Iterable[dict[str, Any]] = (),
) -> _EmulatedPostgrest:
    """A pair served with a base scope: the primary rows, and base rows no
    primary path shadows. Navigation is build_navigation_nodes over them, which
    the merge of 20260927110000 equals on well-formed pairs
    (tests/test_layered_serving_postgres.py)."""
    primary = [record for version, tree in primaries.items() for record in _records(version, tree)]
    shadowing = {record.citation_path for record in primary}
    winners = primary + [
        record
        for record in _records("2026-04-29-base", base)
        if record.citation_path not in shadowing
    ]
    return _EmulatedPostgrest(
        {
            "current_provisions": list(iter_supabase_rows(winners)),
            "current_navigation_nodes": [
                node.to_supabase_row() for node in build_navigation_nodes(winners)
            ]
            + list(extra_navigation),
            "current_release_scopes": _release_scopes(
                ["2026-04-29-base", *primaries], base="2026-04-29-base", layer_column=True
            ),
        },
        max_rows=max_rows,
    )


def _query(postgrest: _EmulatedPostgrest) -> SupabaseQuery:
    query = SupabaseQuery(url="https://test.supabase.co", anon_key="test-key")
    query._request = postgrest  # type: ignore[method-assign]
    return query


def _origin_main_children(query: SupabaseQuery, path: str, jurisdiction: str = "fx") -> list[Rule]:
    """get_section_with_children(deep=False) exactly as origin/main (595a64c5) has it."""
    rule = query.get_section(path, jurisdiction)
    assert rule is not None
    params = {
        "parent_id": f"eq.{rule.id}",
        "order": "ordinal",
    }
    children_data = query._request(query.provisions_table, params) or []
    return [query._to_rule(c) for c in children_data]


def _children(query: SupabaseQuery, path: str) -> list[Rule]:
    section = query.get_section_with_children(path, jurisdiction="fx")
    assert section is not None
    return section.children


# A title, a section that declares it, and one that declares no parent: the
# staged navigation hangs the second under the title, the provision rows do not.
_UNDECLARED_CHILD = (
    ("fx/statute/1", None, 1),
    ("fx/statute/1/1", "fx/statute/1", 1),
    ("fx/statute/1/2", None, 2),
)


def test_unlayered_children_are_the_parent_id_children_origin_main_returns() -> None:
    for layer_column in (True, False):
        postgrest = _unlayered_postgrest(
            {"2026-09-01": _UNDECLARED_CHILD}, layer_column=layer_column
        )
        query = _query(postgrest)
        expected = _origin_main_children(query, "fx/statute/1")
        assert [child.citation_path for child in expected] == ["fx/statute/1/1"]
        assert _children(query, "fx/statute/1") == expected
        # The probe reads every column: before 20260927110000 the view has no
        # layer column, so a filter on it would be an error.
        table, params = postgrest.requests[-2]
        assert table == "current_release_scopes"
        assert dict(params) == {
            "select": "*",
            "jurisdiction": "eq.fx",
            "document_class": "eq.statute",
        }


def test_unlayered_children_with_a_path_in_two_scopes_match_origin_main() -> None:
    """A release cut before citation paths were unique can serve a title twice."""
    tree = (("fx/statute/1", None, 1),) + tuple(
        (f"fx/statute/1/{index:04d}", "fx/statute/1", index) for index in range(1000)
    )
    query = _query(_unlayered_postgrest({"2026-09-01": tree, "2026-09-02": tree}))
    expected = _origin_main_children(query, "fx/statute/1")
    assert len(expected) == 1000
    assert _children(query, "fx/statute/1") == expected


@settings(max_examples=150, deadline=None)
@given(
    scopes=st.dictionaries(
        st.sampled_from(["2026-09-01", "2026-09-02", "2026-09-03"]),
        st.lists(
            st.tuples(
                st.sampled_from(
                    [
                        "fx/statute/1",
                        "fx/statute/1/a",
                        "fx/statute/1/b",
                        "fx/statute/1/c",
                        "fx/statute/1/a/i",
                        "fx/statute/2",
                    ]
                ),
                st.sampled_from([None, "fx/statute/1", "fx/statute/1/a", "fx/statute/2"]),
                st.sampled_from([None, 1, 2, 3]),
            ),
            min_size=1,
            max_size=6,
            unique_by=lambda row: row[0],
        ),
        min_size=1,
    ),
    path=st.sampled_from(["fx/statute/1", "fx/statute/1/a", "fx/statute/2"]),
    max_rows=st.integers(1, 4),
    layer_column=st.booleans(),
)
def test_unlayered_children_equal_origin_main_on_any_served_rows(
    scopes: dict[str, list[tuple[str, str | None, int | None]]],
    path: str,
    max_rows: int,
    layer_column: bool,
) -> None:
    query = _query(_unlayered_postgrest(scopes, layer_column=layer_column, max_rows=max_rows))
    if query.get_section(path, "fx") is None:
        assert query.get_section_with_children(path, jurisdiction="fx") is None
        return
    assert _children(query, path) == _origin_main_children(query, path)


def _layered_children(postgrest: _EmulatedPostgrest, path: str) -> list[str | None]:
    """The served children of ``path`` in served navigation order."""
    nodes = sorted(
        (
            node
            for node in postgrest.tables["current_navigation_nodes"]
            if node["parent_path"] == path
        ),
        key=lambda node: (node["sort_key"], node["path"]),
    )
    paths: list[str | None] = []
    for node in nodes:
        if node["path"] not in paths:
            paths.append(node["path"])
    return paths


# A base title of 700 sections, and a primary scope that adds 600 sections
# without its title: once merged, 1,300 children of one title.
_BASE_TITLE = (("fx/statute/1", None, 1),) + tuple(
    (f"fx/statute/1/{index:04d}", "fx/statute/1", index) for index in range(700)
)
_NEW_SECTIONS = tuple((f"fx/statute/1/{index:04d}", None, index) for index in range(700, 1300))


def test_layered_children_page_through_the_row_cap() -> None:
    for max_rows in (1000, 250):
        postgrest = _layered_postgrest(
            _BASE_TITLE, {"2026-09-20-sections": _NEW_SECTIONS}, max_rows=max_rows
        )
        children = _children(_query(postgrest), "fx/statute/1")
        assert len(children) == 1300
        assert [child.citation_path for child in children] == _layered_children(
            postgrest, "fx/statute/1"
        )


def test_layered_children_page_before_keeping_one_per_path() -> None:
    """Navigation that serves a child twice (two scopes of one layer carrying it,
    which validation and activation reject) still yields every child once."""
    titled = (("fx/statute/1", None, 1),) + tuple(
        (f"fx/statute/1/{index:04d}", "fx/statute/1", index) for index in range(1000)
    )
    twin = tuple((path, None, ordinal) for path, _parent, ordinal in titled[1:])
    twin_rows = [
        node.to_supabase_row() for node in build_navigation_nodes(_records("2026-09-21-twin", twin))
    ]
    for row in twin_rows:
        row["parent_path"] = "fx/statute/1"
    postgrest = _layered_postgrest(
        (("fx/statute/1", None, 1),),
        {"2026-09-20-title": titled},
        extra_navigation=twin_rows,
    )
    postgrest.tables["current_provisions"].extend(
        iter_supabase_rows(_records("2026-09-21-twin", twin))
    )
    children = _children(_query(postgrest), "fx/statute/1")
    assert len(children) == 1000
    title_id = _query(postgrest).get_section("fx/statute/1", "fx").id  # type: ignore[union-attr]
    # One child per path, the title's own scope's.
    assert all(child.parent_id == title_id for child in children)


def test_layered_children_follow_the_served_navigation_tree() -> None:
    """A primary title's children may be base rows, and a base title's primary rows."""
    postgrest = _layered_postgrest(
        (
            ("fx/statute/1", None, 1),
            ("fx/statute/1/1", "fx/statute/1", 1),
            ("fx/statute/1/2", "fx/statute/1", 2),
            ("fx/statute/2", None, 2),
            ("fx/statute/2/1", "fx/statute/2", 1),
        ),
        {
            "2026-09-20-title-1": (
                ("fx/statute/1", None, 1),
                ("fx/statute/1/3", "fx/statute/1", 3),
            ),
            "2026-09-21-title-2": (("fx/statute/2/2", None, 2),),
        },
    )
    query = _query(postgrest)
    assert [(c.citation_path, c.id) for c in _children(query, "fx/statute/1")] == [
        (row["citation_path"], row["id"])
        for path in ("fx/statute/1/1", "fx/statute/1/2", "fx/statute/1/3")
        for row in postgrest.tables["current_provisions"]
        if row["citation_path"] == path
    ]
    assert [c.citation_path for c in _children(query, "fx/statute/2")] == [
        "fx/statute/2/1",
        "fx/statute/2/2",
    ]
    navigation = [
        dict(params) for table, params in postgrest.requests if table == "current_navigation_nodes"
    ]
    assert navigation[0] == {
        "select": "provision_id",
        "jurisdiction": "eq.fx",
        "parent_path": "eq.fx/statute/1",
        "doc_type": "eq.statute",
        "order": "sort_key,path,id",
        "limit": "1000",
        "offset": "0",
    }


def test_layered_children_are_read_back_in_id_batches() -> None:
    sections = tuple(
        (f"fx/statute/1/{index:04d}", None, index) for index in range(CHILD_ID_BATCH + 5)
    )
    postgrest = _layered_postgrest((("fx/statute/1", None, 1),), {"2026-09-20": sections})
    children = _children(_query(postgrest), "fx/statute/1")
    assert len(children) == CHILD_ID_BATCH + 5
    batches = [
        dict(params)["id"]
        for table, params in postgrest.requests
        if table == "current_provisions" and "id" in dict(params)
    ]
    assert [batch.count(",") + 1 for batch in batches] == [CHILD_ID_BATCH, 5]


def test_layered_leaf_has_no_children_and_reads_no_provisions() -> None:
    postgrest = _layered_postgrest(_BASE_TITLE[:2], {"2026-09-20": _NEW_SECTIONS[:1]})
    assert _children(_query(postgrest), "fx/statute/1/0000") == []
    assert not any(
        "id" in dict(params)
        for table, params in postgrest.requests
        if table == "current_provisions"
    )


@st.composite
def _layered_pair(draw: st.DrawFn) -> tuple[Tree, dict[str, Tree]]:
    """A base closed under ancestors and primary scopes over its paths and new
    ones, every declared parent the immediate path prefix (the well-formed case)."""
    paths = (
        ["fx/statute/1"]
        + [f"fx/statute/1/{i}" for i in range(6)]
        + [f"fx/statute/1/{i}/{j}" for i in range(3) for j in ("a", "b")]
    )
    base_paths = {"fx/statute/1"} | set(draw(st.lists(st.sampled_from(paths[1:7]), max_size=6)))
    base_paths |= {
        p for p in paths[7:] if p.rsplit("/", 1)[0] in base_paths and draw(st.booleans())
    }

    def row(path: str, scope_paths: set[str]) -> tuple[str, str | None, int | None]:
        parent = path.rsplit("/", 1)[0]
        return (
            path,
            parent if parent in scope_paths else None,
            draw(st.sampled_from([None, 1, 2])),
        )

    base = tuple(row(path, base_paths) for path in paths if path in base_paths)
    primaries: dict[str, Tree] = {}
    taken: set[str] = set()
    for index in range(draw(st.integers(1, 2))):
        chosen = set(draw(st.lists(st.sampled_from(paths), max_size=8))) - taken
        taken |= chosen
        if chosen:
            primaries[f"2026-09-2{index}"] = tuple(
                row(path, chosen) for path in paths if path in chosen
            )
    return base, primaries


@settings(max_examples=150, deadline=None)
@given(
    pair=_layered_pair(),
    path=st.sampled_from(["fx/statute/1", "fx/statute/1/0", "fx/statute/1/1"]),
    max_rows=st.integers(1, 3),
)
def test_layered_children_are_the_served_navigation_children(
    pair: tuple[Tree, dict[str, Tree]], path: str, max_rows: int
) -> None:
    base, primaries = pair
    postgrest = _layered_postgrest(base, primaries, max_rows=max_rows)
    query = _query(postgrest)
    if query.get_section(path, "fx") is None:
        return
    assert [child.citation_path for child in _children(query, path)] == _layered_children(
        postgrest, path
    )
