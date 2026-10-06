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

