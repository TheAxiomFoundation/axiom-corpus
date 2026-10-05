"""Tests for the query supabase module.

Tests cover Rule/Section dataclasses and SupabaseQuery class.
HTTP calls are mocked.
"""

import os
from unittest.mock import patch

from axiom_corpus.query.supabase import Rule, Section, SupabaseQuery


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
        assert (
            SupabaseQuery._normalize_citation_path("us/statute/26/32")
            == "us/statute/26/32"
        )
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

    def test_get_section_children_follow_the_served_navigation_tree(self):
        """A served title's children may be rows of another scope (a base layer)."""
        query = SupabaseQuery(url="https://test.supabase.co", anon_key="test-key")
        parent = _make_rule(id="title-primary", citation_path="us/statute/26").__dict__
        base_child = _make_rule(
            id="section-base",
            citation_path="us/statute/26/1",
            parent_id="title-base",
        ).__dict__
        primary_child = _make_rule(
            id="section-primary",
            citation_path="us/statute/26/32",
            parent_id="title-primary",
        ).__dict__
        nodes = [{"provision_id": "section-base"}, {"provision_id": "section-primary"}]

        with patch.object(
            query, "_request", side_effect=[[parent], nodes, [primary_child, base_child]]
        ) as request:
            section = query.get_section_with_children("us/statute/26")

        assert section is not None
        assert [child.id for child in section.children] == ["section-base", "section-primary"]
        nav_table, nav_params = request.call_args_list[1].args
        assert nav_table == "current_navigation_nodes"
        assert nav_params == {
            "select": "provision_id",
            "jurisdiction": "eq.us",
            "parent_path": "eq.us/statute/26",
            "order": "sort_key,path",
        }
        rows_table, rows_params = request.call_args_list[2].args
        assert rows_table == "current_provisions"
        assert rows_params == {"id": "in.(section-base,section-primary)"}

    def test_get_section_children_batch_long_id_lists(self):
        from axiom_corpus.query.supabase import CHILD_ID_BATCH

        query = SupabaseQuery(url="https://test.supabase.co", anon_key="test-key")
        parent = _make_rule(id="title", citation_path="us/statute/42").__dict__
        ids = [f"section-{index:04d}" for index in range(CHILD_ID_BATCH + 5)]
        rows = {
            provision_id: _make_rule(
                id=provision_id, citation_path=f"us/statute/42/{provision_id}"
            ).__dict__
            for provision_id in ids
        }

        def respond(table, params):
            if table == "current_provisions" and "citation_path" in params:
                return [parent]
            if table == "current_navigation_nodes":
                return [{"provision_id": provision_id} for provision_id in ids]
            requested = params["id"].removeprefix("in.(").removesuffix(")").split(",")
            # The last child is not served: it is left out, not invented.
            return [rows[i] for i in requested if i != ids[-1]]

        with patch.object(query, "_request", side_effect=respond) as request:
            section = query.get_section_with_children("us/statute/42")

        assert section is not None
        assert [child.id for child in section.children] == ids[:-1]
        id_requests = [
            call.args[1]["id"] for call in request.call_args_list if "id" in call.args[1]
        ]
        assert len(id_requests) == 2
        assert id_requests[0].count(",") == CHILD_ID_BATCH - 1

    def test_get_section_children_keep_one_row_per_citation_path(self):
        query = SupabaseQuery(url="https://test.supabase.co", anon_key="test-key")
        parent = _make_rule(id="title-a", citation_path="us/statute/26").__dict__
        other_scope = _make_rule(
            id="section-b", citation_path="us/statute/26/1", parent_id="title-b"
        ).__dict__
        own_scope = _make_rule(
            id="section-a", citation_path="us/statute/26/1", parent_id="title-a"
        ).__dict__
        sibling = _make_rule(
            id="section-2", citation_path="us/statute/26/2", parent_id="title-b"
        ).__dict__
        nodes = [
            {"provision_id": "section-b"},
            {"provision_id": "section-a"},
            {"provision_id": "section-2"},
        ]

        with patch.object(
            query, "_request", side_effect=[[parent], nodes, [own_scope, other_scope, sibling]]
        ):
            section = query.get_section_with_children("us/statute/26")

        assert section is not None
        assert [child.id for child in section.children] == ["section-a", "section-2"]

    def test_get_section_children_of_a_leaf_skip_the_provision_lookup(self):
        query = SupabaseQuery(url="https://test.supabase.co", anon_key="test-key")
        leaf = _make_rule(citation_path="us/statute/26/32/a").__dict__

        with patch.object(query, "_request", side_effect=[[leaf], []]) as request:
            section = query.get_section_with_children("us/statute/26/32/a")

        assert section is not None
        assert section.children == []
        assert request.call_count == 2

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
