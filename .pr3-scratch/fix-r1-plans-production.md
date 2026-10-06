1521299 provision rows, 306923 base rows, 456 shadowed; serving the release derived the layered state in 7.3 s.

### current_provisions?citation_path=eq.<base-only path>

```
Nested Loop Anti Join  (cost=1.12..54.90 rows=4 width=719) (actual time=0.097..0.141 rows=1 loops=1)
  Buffers: shared hit=48 read=13
  ->  Nested Loop Semi Join  (cost=0.85..38.72 rows=4 width=719) (actual time=0.095..0.139 rows=1 loops=1)
        Buffers: shared hit=46 read=13
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.43..16.15 rows=4 width=719) (actual time=0.022..0.052 rows=11 loops=1)
              Index Cond: (citation_path = 'us/statute/30/500'::text)
              Buffers: shared hit=1 read=13
        ->  Nested Loop  (cost=0.42..5.63 rows=1 width=33) (actual time=0.007..0.007 rows=0 loops=11)
              Join Filter: (p.version = scopes.version)
              Rows Removed by Join Filter: 23
              Buffers: shared hit=45
              ->  Index Scan using active_scope_pointer_pkey on active_scope_pointer active  (cost=0.15..5.17 rows=1 width=25) (actual time=0.001..0.001 rows=1 loops=11)
                    Index Cond: ((jurisdiction = p.jurisdiction) AND (document_class = COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text)))
                    Buffers: shared hit=22
              ->  Index Only Scan using release_scopes_pkey on release_scopes scopes  (cost=0.27..0.45 rows=1 width=34) (actual time=0.004..0.005 rows=23 loops=11)
                    Index Cond: ((release_name = active.release_name) AND (jurisdiction = active.jurisdiction) AND (document_class = active.document_class))
                    Heap Fetches: 0
                    Buffers: shared hit=23
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..3.29 rows=1 width=16) (actual time=0.001..0.001 rows=0 loops=1)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=2
Planning:
  Buffers: shared hit=30
Planning Time: 0.415 ms
Execution Time: 0.165 ms
```

### current_provisions?citation_path=eq.<collision path>

```
Nested Loop Anti Join  (cost=1.12..54.90 rows=4 width=719) (actual time=0.066..0.067 rows=1 loops=1)
  Buffers: shared hit=20 read=4
  ->  Nested Loop Semi Join  (cost=0.85..38.72 rows=4 width=719) (actual time=0.045..0.061 rows=2 loops=1)
        Buffers: shared hit=15 read=4
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.43..16.15 rows=4 width=719) (actual time=0.022..0.032 rows=3 loops=1)
              Index Cond: (citation_path = 'us/statute/3/1'::text)
              Buffers: shared hit=2 read=4
        ->  Nested Loop  (cost=0.42..5.63 rows=1 width=33) (actual time=0.009..0.009 rows=1 loops=3)
              Join Filter: (p.version = scopes.version)
              Rows Removed by Join Filter: 9
              Buffers: shared hit=13
              ->  Index Scan using active_scope_pointer_pkey on active_scope_pointer active  (cost=0.15..5.17 rows=1 width=25) (actual time=0.002..0.002 rows=1 loops=3)
                    Index Cond: ((jurisdiction = p.jurisdiction) AND (document_class = COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text)))
                    Buffers: shared hit=6
              ->  Index Only Scan using release_scopes_pkey on release_scopes scopes  (cost=0.27..0.45 rows=1 width=34) (actual time=0.004..0.005 rows=10 loops=3)
                    Index Cond: ((release_name = active.release_name) AND (jurisdiction = active.jurisdiction) AND (document_class = active.document_class))
                    Heap Fetches: 0
                    Buffers: shared hit=7
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..3.29 rows=1 width=16) (actual time=0.002..0.002 rows=0 loops=2)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=5
Planning:
  Buffers: shared hit=30
Planning Time: 0.423 ms
Execution Time: 0.093 ms
```

### current_navigation_nodes?jurisdiction=eq.us&order=citation_path.asc&limit=1000

```
Limit  (cost=48.01..27179.25 rows=1000 width=48) (actual time=2.558..4.677 rows=1000 loops=1)
  Buffers: shared hit=1083 read=262
  ->  Merge Append  (cost=48.01..6449142.58 rows=237700 width=48) (actual time=2.557..4.623 rows=1000 loops=1)
        Sort Key: n.citation_path
        Buffers: shared hit=1083 read=262
        ->  Index Scan using idx_navigation_nodes_jurisdiction_citation_path on navigation_nodes n  (cost=47.72..6444963.78 rows=226864 width=47) (actual time=2.543..4.401 rows=699 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 310
              Buffers: shared hit=792 read=262
              SubPlan 1
                ->  Hash Join  (cost=9.55..24.33 rows=280 width=21) (actual time=0.055..0.166 rows=250 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=10
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..10.90 rows=490 width=34) (actual time=0.004..0.041 rows=490 loops=1)
                            Buffers: shared hit=6
                      ->  Hash  (cost=6.02..6.02 rows=202 width=25) (actual time=0.047..0.048 rows=202 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 20kB
                            Buffers: shared hit=4
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..6.02 rows=202 width=25) (actual time=0.002..0.018 rows=202 loops=1)
                                  Buffers: shared hit=4
              SubPlan 2
                ->  Nested Loop  (cost=0.13..22.26 rows=1 width=12) (actual time=0.021..0.097 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 402
                      Buffers: shared hit=6
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..6.02 rows=202 width=25) (actual time=0.006..0.016 rows=202 loops=1)
                            Buffers: shared hit=4
                      ->  Materialize  (cost=0.13..8.17 rows=2 width=25) (actual time=0.000..0.000 rows=2 loops=202)
                            Buffers: shared hit=2
                            ->  Index Only Scan using release_scopes_one_base_per_pair on release_scopes scopes_1  (cost=0.13..8.16 rows=2 width=25) (actual time=0.006..0.006 rows=2 loops=1)
                                  Heap Fetches: 0
                                  Buffers: shared hit=2
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.003..0.045 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..566.82 rows=10836 width=33) (actual time=0.011..0.650 rows=10836 loops=1)
                      Heap Fetches: 0
                      Buffers: shared hit=101
        ->  Index Scan using idx_layered_navigation_overrides_citation_path on layered_navigation_overrides o  (cost=0.29..1801.79 rows=10836 width=66) (actual time=0.013..0.133 rows=302 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Buffers: shared hit=291
Planning:
  Buffers: shared hit=8
Planning Time: 0.511 ms
Execution Time: 4.754 ms
```

### current_navigation_nodes?parent_path=eq.us/statute/2&order=sort_key (merged children)

```
Limit  (cost=48.01..3835.00 rows=100 width=249) (actual time=2.397..2.570 rows=100 loops=1)
  Buffers: shared hit=228 read=6
  ->  Merge Append  (cost=48.01..38296.55 rows=1010 width=249) (actual time=2.397..2.563 rows=100 loops=1)
        Sort Key: n.sort_key
        Buffers: shared hit=228 read=6
        ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes n  (cost=47.72..38278.14 rows=1009 width=249) (actual time=2.388..2.548 rows=100 loops=1)
              Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/2'::text))
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 2
              Buffers: shared hit=226 read=6
              SubPlan 1
                ->  Hash Join  (cost=9.55..24.33 rows=280 width=21) (actual time=0.050..0.152 rows=250 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=10
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..10.90 rows=490 width=34) (actual time=0.003..0.039 rows=490 loops=1)
                            Buffers: shared hit=6
                      ->  Hash  (cost=6.02..6.02 rows=202 width=25) (actual time=0.043..0.044 rows=202 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 20kB
                            Buffers: shared hit=4
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..6.02 rows=202 width=25) (actual time=0.002..0.016 rows=202 loops=1)
                                  Buffers: shared hit=4
              SubPlan 2
                ->  Nested Loop  (cost=0.13..22.26 rows=1 width=12) (actual time=0.011..0.061 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 402
                      Buffers: shared hit=6
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..6.02 rows=202 width=25) (actual time=0.001..0.008 rows=202 loops=1)
                            Buffers: shared hit=4
                      ->  Materialize  (cost=0.13..8.17 rows=2 width=25) (actual time=0.000..0.000 rows=2 loops=202)
                            Buffers: shared hit=2
                            ->  Index Only Scan using release_scopes_one_base_per_pair on release_scopes scopes_1  (cost=0.13..8.16 rows=2 width=25) (actual time=0.003..0.003 rows=2 loops=1)
                                  Heap Fetches: 0
                                  Buffers: shared hit=2
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.002..0.038 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..566.82 rows=10836 width=33) (actual time=0.003..0.639 rows=10836 loops=1)
                      Heap Fetches: 0
                      Buffers: shared hit=101
        ->  Index Scan using idx_layered_navigation_overrides_parent_sort on layered_navigation_overrides o  (cost=0.29..8.31 rows=1 width=286) (actual time=0.008..0.008 rows=0 loops=1)
              Index Cond: (parent_path = 'us/statute/2'::text)
              Filter: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text))
              Buffers: shared hit=2
Planning:
  Buffers: shared hit=8
Planning Time: 0.491 ms
Execution Time: 2.624 ms
```

### current_navigation_nodes?select=provision_id&parent_path=eq.us/statute/2&order=sort_key,path,id&limit=1000 (client children page)

```
Limit  (cost=239.37..37959.37 rows=1000 width=101) (actual time=2.402..4.223 rows=1000 loops=1)
  Buffers: shared hit=1096 read=22
  ->  Incremental Sort  (cost=239.37..38336.57 rows=1010 width=101) (actual time=2.401..4.166 rows=1000 loops=1)
        Sort Key: n.sort_key, n.path, n.id
        Presorted Key: n.sort_key
        Full-sort Groups: 32  Sort Method: quicksort  Average Memory: 29kB  Peak Memory: 29kB
        Buffers: shared hit=1096 read=22
        ->  Merge Append  (cost=48.01..38296.55 rows=1010 width=101) (actual time=2.338..3.937 rows=1001 loops=1)
              Sort Key: n.sort_key
              Buffers: shared hit=1096 read=22
              ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes n  (cost=47.72..38278.14 rows=1009 width=101) (actual time=2.331..3.872 rows=1001 loops=1)
                    Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/2'::text))
                    Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
                    Rows Removed by Filter: 19
                    Buffers: shared hit=1094 read=22
                    SubPlan 1
                      ->  Hash Join  (cost=9.55..24.33 rows=280 width=21) (actual time=0.048..0.148 rows=250 loops=1)
                            Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                            Buffers: shared hit=10
                            ->  Seq Scan on release_scopes scopes  (cost=0.00..10.90 rows=490 width=34) (actual time=0.003..0.038 rows=490 loops=1)
                                  Buffers: shared hit=6
                            ->  Hash  (cost=6.02..6.02 rows=202 width=25) (actual time=0.042..0.042 rows=202 loops=1)
                                  Buckets: 1024  Batches: 1  Memory Usage: 20kB
                                  Buffers: shared hit=4
                                  ->  Seq Scan on active_scope_pointer active  (cost=0.00..6.02 rows=202 width=25) (actual time=0.002..0.016 rows=202 loops=1)
                                        Buffers: shared hit=4
                    SubPlan 2
                      ->  Nested Loop  (cost=0.13..22.26 rows=1 width=12) (actual time=0.009..0.059 rows=2 loops=1)
                            Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                            Rows Removed by Join Filter: 402
                            Buffers: shared hit=6
                            ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..6.02 rows=202 width=25) (actual time=0.001..0.008 rows=202 loops=1)
                                  Buffers: shared hit=4
                            ->  Materialize  (cost=0.13..8.17 rows=2 width=25) (actual time=0.000..0.000 rows=2 loops=202)
                                  Buffers: shared hit=2
                                  ->  Index Only Scan using release_scopes_one_base_per_pair on release_scopes scopes_1  (cost=0.13..8.16 rows=2 width=25) (actual time=0.002..0.002 rows=2 loops=1)
                                        Heap Fetches: 0
                                        Buffers: shared hit=2
                    SubPlan 4
                      ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.002..0.040 rows=456 loops=1)
                            Buffers: shared hit=12
                    SubPlan 6
                      ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..566.82 rows=10836 width=33) (actual time=0.003..0.607 rows=10836 loops=1)
                            Heap Fetches: 0
                            Buffers: shared hit=101
              ->  Index Scan using idx_layered_navigation_overrides_parent_sort on layered_navigation_overrides o  (cost=0.29..8.31 rows=1 width=109) (actual time=0.006..0.007 rows=0 loops=1)
                    Index Cond: (parent_path = 'us/statute/2'::text)
                    Filter: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text))
                    Buffers: shared hit=2
Planning:
  Buffers: shared hit=8
Planning Time: 0.443 ms
Execution Time: 4.304 ms
```

### rpc/get_root_document_counts

```
Function Scan on get_root_document_counts  (cost=0.25..10.25 rows=1000 width=72) (actual time=23.462..23.467 rows=202 loops=1)
  Buffers: shared hit=30905 read=264
Planning Time: 0.005 ms
Execution Time: 23.479 ms
```

### navigation_nodes?parent_path=eq.us/statute/3 (direct read, anon policy)

```
Limit  (cost=4.44..6038.58 rows=100 width=249) (actual time=0.917..1.022 rows=100 loops=1)
  Buffers: shared hit=131 read=5
  ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes  (cost=4.44..46889.71 rows=777 width=249) (actual time=0.916..1.017 rows=100 loops=1)
        Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/3'::text))
        Filter: ((NOT (hashed SubPlan 3)) AND (hashed SubPlan 2))
        Rows Removed by Filter: 10
        Buffers: shared hit=131 read=5
        SubPlan 3
          ->  ProjectSet  (cost=0.00..2.77 rows=500 width=32) (actual time=0.052..0.636 rows=456 loops=1)
                Buffers: shared hit=12
                ->  Result  (cost=0.00..0.01 rows=1 width=0) (actual time=0.000..0.000 rows=1 loops=1)
        SubPlan 2
          ->  Hash Join  (cost=9.55..24.33 rows=280 width=21) (actual time=0.048..0.153 rows=250 loops=1)
                Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                Buffers: shared hit=10
                ->  Seq Scan on release_scopes scopes  (cost=0.00..10.90 rows=490 width=34) (actual time=0.003..0.044 rows=490 loops=1)
                      Buffers: shared hit=6
                ->  Hash  (cost=6.02..6.02 rows=202 width=25) (actual time=0.041..0.042 rows=202 loops=1)
                      Buckets: 1024  Batches: 1  Memory Usage: 20kB
                      Buffers: shared hit=4
                      ->  Seq Scan on active_scope_pointer active  (cost=0.00..6.02 rows=202 width=25) (actual time=0.002..0.015 rows=202 loops=1)
                            Buffers: shared hit=4
Planning:
  Buffers: shared hit=4
Planning Time: 0.222 ms
Execution Time: 1.050 ms
```
