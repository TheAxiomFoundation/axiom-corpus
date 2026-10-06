1521299 provision rows, 306923 base rows, 456 shadowed; serving the release derived the layered state in 28.2 s.

### current_provisions?citation_path=eq.<base-only path>

```
Nested Loop Anti Join  (cost=1.12..54.86 rows=4 width=719) (actual time=0.045..0.063 rows=1 loops=1)
  Buffers: shared hit=61
  ->  Nested Loop Semi Join  (cost=0.85..38.68 rows=4 width=719) (actual time=0.044..0.061 rows=1 loops=1)
        Buffers: shared hit=59
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.43..16.11 rows=4 width=719) (actual time=0.007..0.016 rows=11 loops=1)
              Index Cond: (citation_path = 'us/statute/30/500'::text)
              Buffers: shared hit=14
        ->  Nested Loop  (cost=0.42..5.63 rows=1 width=33) (actual time=0.004..0.004 rows=0 loops=11)
              Join Filter: (p.version = scopes.version)
              Rows Removed by Join Filter: 23
              Buffers: shared hit=45
              ->  Index Scan using active_scope_pointer_pkey on active_scope_pointer active  (cost=0.15..5.17 rows=1 width=25) (actual time=0.001..0.001 rows=1 loops=11)
                    Index Cond: ((jurisdiction = p.jurisdiction) AND (document_class = COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text)))
                    Buffers: shared hit=22
              ->  Index Only Scan using release_scopes_pkey on release_scopes scopes  (cost=0.27..0.45 rows=1 width=34) (actual time=0.002..0.002 rows=23 loops=11)
                    Index Cond: ((release_name = active.release_name) AND (jurisdiction = active.jurisdiction) AND (document_class = active.document_class))
                    Heap Fetches: 0
                    Buffers: shared hit=23
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..3.29 rows=1 width=16) (actual time=0.001..0.001 rows=0 loops=1)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=2
Planning:
  Buffers: shared hit=30
Planning Time: 0.238 ms
Execution Time: 0.076 ms
```

### current_provisions?citation_path=eq.<collision path>

```
Nested Loop Anti Join  (cost=1.12..54.86 rows=4 width=719) (actual time=0.024..0.025 rows=1 loops=1)
  Buffers: shared hit=24
  ->  Nested Loop Semi Join  (cost=0.85..38.68 rows=4 width=719) (actual time=0.017..0.022 rows=2 loops=1)
        Buffers: shared hit=19
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.43..16.11 rows=4 width=719) (actual time=0.006..0.008 rows=3 loops=1)
              Index Cond: (citation_path = 'us/statute/3/1'::text)
              Buffers: shared hit=6
        ->  Nested Loop  (cost=0.42..5.63 rows=1 width=33) (actual time=0.004..0.004 rows=1 loops=3)
              Join Filter: (p.version = scopes.version)
              Rows Removed by Join Filter: 9
              Buffers: shared hit=13
              ->  Index Scan using active_scope_pointer_pkey on active_scope_pointer active  (cost=0.15..5.17 rows=1 width=25) (actual time=0.001..0.001 rows=1 loops=3)
                    Index Cond: ((jurisdiction = p.jurisdiction) AND (document_class = COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text)))
                    Buffers: shared hit=6
              ->  Index Only Scan using release_scopes_pkey on release_scopes scopes  (cost=0.27..0.45 rows=1 width=34) (actual time=0.002..0.002 rows=10 loops=3)
                    Index Cond: ((release_name = active.release_name) AND (jurisdiction = active.jurisdiction) AND (document_class = active.document_class))
                    Heap Fetches: 0
                    Buffers: shared hit=7
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..3.29 rows=1 width=16) (actual time=0.001..0.001 rows=0 loops=2)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=5
Planning:
  Buffers: shared hit=30
Planning Time: 0.153 ms
Execution Time: 0.034 ms
```

### current_navigation_nodes?jurisdiction=eq.us&order=citation_path.asc&limit=1000

```
Limit  (cost=48.01..27170.00 rows=1000 width=48) (actual time=2.992..6.762 rows=1000 loops=1)
  Buffers: shared hit=1345
  ->  Merge Append  (cost=48.01..6420853.66 rows=236738 width=48) (actual time=2.991..6.708 rows=1000 loops=1)
        Sort Key: n.citation_path
        Buffers: shared hit=1345
        ->  Index Scan using idx_navigation_nodes_jurisdiction_citation_path on navigation_nodes n  (cost=47.72..6416684.48 rows=225902 width=47) (actual time=2.975..6.423 rows=699 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 310
              Buffers: shared hit=1054
              SubPlan 1
                ->  Hash Join  (cost=9.55..24.33 rows=280 width=21) (actual time=0.035..0.143 rows=250 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=10
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..10.90 rows=490 width=34) (actual time=0.004..0.035 rows=490 loops=1)
                            Buffers: shared hit=6
                      ->  Hash  (cost=6.02..6.02 rows=202 width=25) (actual time=0.028..0.029 rows=202 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 20kB
                            Buffers: shared hit=4
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..6.02 rows=202 width=25) (actual time=0.002..0.012 rows=202 loops=1)
                                  Buffers: shared hit=4
              SubPlan 2
                ->  Nested Loop  (cost=0.13..22.26 rows=1 width=12) (actual time=0.012..0.080 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 402
                      Buffers: shared hit=6
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..6.02 rows=202 width=25) (actual time=0.002..0.008 rows=202 loops=1)
                            Buffers: shared hit=4
                      ->  Materialize  (cost=0.13..8.17 rows=2 width=25) (actual time=0.000..0.000 rows=2 loops=202)
                            Buffers: shared hit=2
                            ->  Index Only Scan using release_scopes_one_base_per_pair on release_scopes scopes_1  (cost=0.13..8.16 rows=2 width=25) (actual time=0.004..0.005 rows=2 loops=1)
                                  Heap Fetches: 0
                                  Buffers: shared hit=2
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.003..0.035 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..566.82 rows=10836 width=33) (actual time=0.008..0.733 rows=10836 loops=1)
                      Heap Fetches: 0
                      Buffers: shared hit=101
        ->  Index Scan using idx_layered_navigation_overrides_citation_path on layered_navigation_overrides o  (cost=0.29..1801.79 rows=10836 width=66) (actual time=0.015..0.191 rows=302 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Buffers: shared hit=291
Planning:
  Buffers: shared hit=8
Planning Time: 0.354 ms
Execution Time: 6.839 ms
```

### current_navigation_nodes?parent_path=eq.us/statute/2&order=sort_key (merged children)

```
Limit  (cost=48.01..3823.96 rows=100 width=249) (actual time=3.299..3.521 rows=100 loops=1)
  Buffers: shared hit=234
  ->  Merge Append  (cost=48.01..36599.19 rows=968 width=249) (actual time=3.298..3.515 rows=100 loops=1)
        Sort Key: n.sort_key
        Buffers: shared hit=234
        ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes n  (cost=47.72..36581.19 rows=967 width=249) (actual time=3.287..3.498 rows=100 loops=1)
              Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/2'::text))
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 2
              Buffers: shared hit=232
              SubPlan 1
                ->  Hash Join  (cost=9.55..24.33 rows=280 width=21) (actual time=0.059..0.178 rows=250 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=10
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..10.90 rows=490 width=34) (actual time=0.005..0.048 rows=490 loops=1)
                            Buffers: shared hit=6
                      ->  Hash  (cost=6.02..6.02 rows=202 width=25) (actual time=0.050..0.051 rows=202 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 20kB
                            Buffers: shared hit=4
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..6.02 rows=202 width=25) (actual time=0.003..0.020 rows=202 loops=1)
                                  Buffers: shared hit=4
              SubPlan 2
                ->  Nested Loop  (cost=0.13..22.26 rows=1 width=12) (actual time=0.014..0.073 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 402
                      Buffers: shared hit=6
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..6.02 rows=202 width=25) (actual time=0.002..0.011 rows=202 loops=1)
                            Buffers: shared hit=4
                      ->  Materialize  (cost=0.13..8.17 rows=2 width=25) (actual time=0.000..0.000 rows=2 loops=202)
                            Buffers: shared hit=2
                            ->  Index Only Scan using release_scopes_one_base_per_pair on release_scopes scopes_1  (cost=0.13..8.16 rows=2 width=25) (actual time=0.003..0.004 rows=2 loops=1)
                                  Heap Fetches: 0
                                  Buffers: shared hit=2
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.003..0.050 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..566.82 rows=10836 width=33) (actual time=0.005..0.768 rows=10836 loops=1)
                      Heap Fetches: 0
                      Buffers: shared hit=101
        ->  Index Scan using idx_layered_navigation_overrides_parent_sort on layered_navigation_overrides o  (cost=0.29..8.31 rows=1 width=286) (actual time=0.010..0.010 rows=0 loops=1)
              Index Cond: (parent_path = 'us/statute/2'::text)
              Filter: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text))
              Buffers: shared hit=2
Planning:
  Buffers: shared hit=8
Planning Time: 0.497 ms
Execution Time: 3.572 ms
```

### rpc/get_root_document_counts

```
Function Scan on get_root_document_counts  (cost=0.25..10.25 rows=1000 width=72) (actual time=30.879..30.885 rows=202 loops=1)
  Buffers: shared hit=31169
Planning Time: 0.010 ms
Execution Time: 30.903 ms
```

### navigation_nodes?parent_path=eq.us/statute/3 (direct read, anon policy)

```
Limit  (cost=4.44..6014.70 rows=100 width=249) (actual time=1.862..2.102 rows=100 loops=1)
  Buffers: shared hit=136
  ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes  (cost=4.44..58484.27 rows=973 width=249) (actual time=1.861..2.096 rows=100 loops=1)
        Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/3'::text))
        Filter: ((NOT (hashed SubPlan 3)) AND (hashed SubPlan 2))
        Rows Removed by Filter: 10
        Buffers: shared hit=136
        SubPlan 3
          ->  ProjectSet  (cost=0.00..2.77 rows=500 width=32) (actual time=0.163..1.376 rows=456 loops=1)
                Buffers: shared hit=12
                ->  Result  (cost=0.00..0.01 rows=1 width=0) (actual time=0.000..0.000 rows=1 loops=1)
        SubPlan 2
          ->  Hash Join  (cost=9.55..24.33 rows=280 width=21) (actual time=0.144..0.279 rows=250 loops=1)
                Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                Buffers: shared hit=10
                ->  Seq Scan on release_scopes scopes  (cost=0.00..10.90 rows=490 width=34) (actual time=0.006..0.061 rows=490 loops=1)
                      Buffers: shared hit=6
                ->  Hash  (cost=6.02..6.02 rows=202 width=25) (actual time=0.132..0.133 rows=202 loops=1)
                      Buckets: 1024  Batches: 1  Memory Usage: 20kB
                      Buffers: shared hit=4
                      ->  Seq Scan on active_scope_pointer active  (cost=0.00..6.02 rows=202 width=25) (actual time=0.020..0.054 rows=202 loops=1)
                            Buffers: shared hit=4
Planning:
  Buffers: shared hit=4
Planning Time: 0.357 ms
Execution Time: 2.146 ms
```
