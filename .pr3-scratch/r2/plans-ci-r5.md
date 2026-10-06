401299 provision rows, 306923 base rows, 456 shadowed; serving the release derived the layered state in 14.7 s.

### current_provisions?citation_path=eq.<base-only path>

```
Nested Loop Anti Join  (cost=2.02..29.79 rows=1 width=726) (actual time=0.037..0.037 rows=1 loops=1)
  Buffers: shared hit=4 read=4
  ->  Nested Loop Semi Join  (cost=1.75..13.48 rows=1 width=726) (actual time=0.035..0.035 rows=1 loops=1)
        Join Filter: ((p.jurisdiction = active.jurisdiction) AND (p.version = scopes.version) AND (COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text) = active.document_class))
        Rows Removed by Join Filter: 25
        Buffers: shared hit=2 read=4
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.42..8.44 rows=1 width=726) (actual time=0.017..0.017 rows=1 loops=1)
              Index Cond: (citation_path = 'us/statute/30/500'::text)
              Buffers: shared read=4
        ->  Hash Join  (cost=1.33..3.72 rows=66 width=41) (actual time=0.011..0.016 rows=26 loops=1)
              Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
              Buffers: shared hit=2
              ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.003..0.004 rows=26 loops=1)
                    Buffers: shared hit=1
              ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.005..0.005 rows=12 loops=1)
                    Buckets: 1024  Batches: 1  Memory Usage: 9kB
                    Buffers: shared hit=1
                    ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.002..0.002 rows=12 loops=1)
                          Buffers: shared hit=1
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..8.29 rows=1 width=16) (actual time=0.001..0.001 rows=0 loops=1)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=2
Planning:
  Buffers: shared hit=28
Planning Time: 0.215 ms
Execution Time: 0.053 ms
```

### current_provisions?citation_path=eq.<collision path>

```
Nested Loop Anti Join  (cost=2.02..29.79 rows=1 width=726) (actual time=0.084..0.085 rows=1 loops=1)
  Buffers: shared hit=12 read=4
  ->  Nested Loop Semi Join  (cost=1.75..13.48 rows=1 width=726) (actual time=0.065..0.079 rows=2 loops=1)
        Join Filter: ((p.jurisdiction = active.jurisdiction) AND (p.version = scopes.version) AND (COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text) = active.document_class))
        Rows Removed by Join Filter: 112
        Buffers: shared hit=6 read=4
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.42..8.44 rows=1 width=726) (actual time=0.016..0.023 rows=3 loops=1)
              Index Cond: (citation_path = 'us/statute/3/1'::text)
              Buffers: shared hit=2 read=4
        ->  Hash Join  (cost=1.33..3.72 rows=66 width=41) (actual time=0.005..0.015 rows=38 loops=3)
              Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
              Buffers: shared hit=4
              ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.002..0.004 rows=43 loops=3)
                    Buffers: shared hit=3
              ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.006..0.006 rows=12 loops=1)
                    Buckets: 1024  Batches: 1  Memory Usage: 9kB
                    Buffers: shared hit=1
                    ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.002..0.003 rows=12 loops=1)
                          Buffers: shared hit=1
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..8.29 rows=1 width=16) (actual time=0.002..0.002 rows=0 loops=2)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 1
        Buffers: shared hit=6
Planning:
  Buffers: shared hit=28
Planning Time: 0.278 ms
Execution Time: 0.104 ms
```

### current_navigation_nodes?jurisdiction=eq.us&order=citation_path.asc&limit=1000

```
Limit  (cost=8.14..48922.68 rows=1000 width=52) (actual time=4.614..20.076 rows=1000 loops=1)
  Buffers: shared hit=948 read=732
  ->  Merge Append  (cost=8.14..6051812.69 rows=123722 width=52) (actual time=4.612..20.032 rows=1000 loops=1)
        Sort Key: n.citation_path
        Buffers: shared hit=948 read=732
        ->  Index Scan using idx_navigation_nodes_jurisdiction_citation_path on navigation_nodes n  (cost=7.84..6048785.67 rows=112886 width=51) (actual time=4.590..19.795 rows=699 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 310
              Buffers: shared hit=656 read=732
              SubPlan 1
                ->  Hash Join  (cost=1.33..3.72 rows=66 width=30) (actual time=0.014..0.043 rows=60 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=2
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.004..0.020 rows=74 loops=1)
                            Buffers: shared hit=1
                      ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.007..0.008 rows=12 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 9kB
                            Buffers: shared hit=1
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.002..0.003 rows=12 loops=1)
                                  Buffers: shared hit=1
              SubPlan 2
                ->  Nested Loop  (cost=0.00..3.53 rows=2 width=12) (actual time=0.013..0.015 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 22
                      Buffers: shared hit=2
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..1.12 rows=12 width=24) (actual time=0.002..0.002 rows=12 loops=1)
                            Buffers: shared hit=1
                      ->  Materialize  (cost=0.00..1.94 rows=2 width=25) (actual time=0.000..0.001 rows=2 loops=12)
                            Buffers: shared hit=1
                            ->  Seq Scan on release_scopes scopes_1  (cost=0.00..1.93 rows=2 width=25) (actual time=0.002..0.007 rows=2 loops=1)
                                  Filter: (layer = 'base'::text)
                                  Rows Removed by Filter: 72
                                  Buffers: shared hit=1
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.003..0.071 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Seq Scan on layered_navigation_overrides overrides  (cost=0.00..659.36 rows=10836 width=33) (actual time=0.006..1.828 rows=10836 loops=1)
                      Buffers: shared hit=551
        ->  Index Scan using idx_layered_navigation_overrides_citation_path on layered_navigation_overrides o  (cost=0.29..1789.79 rows=10836 width=66) (actual time=0.020..0.149 rows=302 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Buffers: shared hit=292
Planning:
  Buffers: shared hit=12
Planning Time: 0.369 ms
Execution Time: 20.145 ms
```

### current_navigation_nodes?parent_path=eq.us/statute/2&order=sort_key (merged children)

```
Limit  (cost=8.14..5874.77 rows=100 width=263) (actual time=2.758..5.504 rows=100 loops=1)
  Buffers: shared hit=569 read=106
  ->  Merge Append  (cost=8.14..11858.74 rows=202 width=263) (actual time=2.757..5.498 rows=100 loops=1)
        Sort Key: n.sort_key
        Buffers: shared hit=569 read=106
        ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes n  (cost=7.84..11848.41 rows=201 width=263) (actual time=2.744..5.478 rows=100 loops=1)
              Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/2'::text))
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 2
              Buffers: shared hit=567 read=106
              SubPlan 1
                ->  Hash Join  (cost=1.33..3.72 rows=66 width=30) (actual time=0.016..0.035 rows=60 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=2
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.006..0.011 rows=74 loops=1)
                            Buffers: shared hit=1
                      ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.007..0.008 rows=12 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 9kB
                            Buffers: shared hit=1
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.003..0.004 rows=12 loops=1)
                                  Buffers: shared hit=1
              SubPlan 2
                ->  Nested Loop  (cost=0.00..3.53 rows=2 width=12) (actual time=0.013..0.016 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 22
                      Buffers: shared hit=2
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..1.12 rows=12 width=24) (actual time=0.001..0.002 rows=12 loops=1)
                            Buffers: shared hit=1
                      ->  Materialize  (cost=0.00..1.94 rows=2 width=25) (actual time=0.000..0.001 rows=2 loops=12)
                            Buffers: shared hit=1
                            ->  Seq Scan on release_scopes scopes_1  (cost=0.00..1.93 rows=2 width=25) (actual time=0.002..0.006 rows=2 loops=1)
                                  Filter: (layer = 'base'::text)
                                  Rows Removed by Filter: 72
                                  Buffers: shared hit=1
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.003..0.049 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Seq Scan on layered_navigation_overrides overrides  (cost=0.00..659.36 rows=10836 width=33) (actual time=0.003..1.140 rows=10836 loops=1)
                      Buffers: shared hit=551
        ->  Index Scan using idx_layered_navigation_overrides_parent_sort on layered_navigation_overrides o  (cost=0.29..8.31 rows=1 width=286) (actual time=0.012..0.012 rows=0 loops=1)
              Index Cond: (parent_path = 'us/statute/2'::text)
              Filter: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text))
              Buffers: shared hit=2
Planning:
  Buffers: shared hit=12
Planning Time: 0.591 ms
Execution Time: 5.583 ms
```

### current_navigation_nodes?select=provision_id&parent_path=eq.us/statute/2&order=sort_key,path,id&limit=1000 (client children page)

```
Limit  (cost=67.40..11867.76 rows=202 width=105) (actual time=2.975..5.730 rows=1000 loops=1)
  Buffers: shared hit=943 read=661
  ->  Incremental Sort  (cost=67.40..11867.76 rows=202 width=105) (actual time=2.974..5.691 rows=1000 loops=1)
        Sort Key: n.sort_key, n.path, n.id
        Presorted Key: n.sort_key
        Full-sort Groups: 32  Sort Method: quicksort  Average Memory: 29kB  Peak Memory: 29kB
        Buffers: shared hit=943 read=661
        ->  Merge Append  (cost=8.14..11858.74 rows=202 width=105) (actual time=2.896..5.539 rows=1001 loops=1)
              Sort Key: n.sort_key
              Buffers: shared hit=943 read=661
              ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes n  (cost=7.84..11848.41 rows=201 width=105) (actual time=2.865..5.472 rows=1001 loops=1)
                    Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/2'::text))
                    Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
                    Rows Removed by Filter: 19
                    Buffers: shared hit=941 read=661
                    SubPlan 1
                      ->  Hash Join  (cost=1.33..3.72 rows=66 width=30) (actual time=0.009..0.021 rows=60 loops=1)
                            Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                            Buffers: shared hit=2
                            ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.003..0.006 rows=74 loops=1)
                                  Buffers: shared hit=1
                            ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.004..0.004 rows=12 loops=1)
                                  Buckets: 1024  Batches: 1  Memory Usage: 9kB
                                  Buffers: shared hit=1
                                  ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.001..0.002 rows=12 loops=1)
                                        Buffers: shared hit=1
                    SubPlan 2
                      ->  Nested Loop  (cost=0.00..3.53 rows=2 width=12) (actual time=0.007..0.010 rows=2 loops=1)
                            Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                            Rows Removed by Join Filter: 22
                            Buffers: shared hit=2
                            ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..1.12 rows=12 width=24) (actual time=0.001..0.001 rows=12 loops=1)
                                  Buffers: shared hit=1
                            ->  Materialize  (cost=0.00..1.94 rows=2 width=25) (actual time=0.000..0.000 rows=2 loops=12)
                                  Buffers: shared hit=1
                                  ->  Seq Scan on release_scopes scopes_1  (cost=0.00..1.93 rows=2 width=25) (actual time=0.001..0.004 rows=2 loops=1)
                                        Filter: (layer = 'base'::text)
                                        Rows Removed by Filter: 72
                                        Buffers: shared hit=1
                    SubPlan 4
                      ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.002..0.035 rows=456 loops=1)
                            Buffers: shared hit=12
                    SubPlan 6
                      ->  Seq Scan on layered_navigation_overrides overrides  (cost=0.00..659.36 rows=10836 width=33) (actual time=0.002..1.292 rows=10836 loops=1)
                            Buffers: shared hit=551
              ->  Index Scan using idx_layered_navigation_overrides_parent_sort on layered_navigation_overrides o  (cost=0.29..8.31 rows=1 width=109) (actual time=0.029..0.030 rows=0 loops=1)
                    Index Cond: (parent_path = 'us/statute/2'::text)
                    Filter: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text))
                    Buffers: shared hit=2
Planning:
  Buffers: shared hit=12
Planning Time: 0.432 ms
Execution Time: 5.802 ms
```

### rpc/get_root_document_counts

```
Function Scan on get_root_document_counts  (cost=0.25..10.25 rows=1000 width=72) (actual time=17.633..17.634 rows=12 loops=1)
  Buffers: shared hit=22675 read=370
Planning Time: 0.010 ms
Execution Time: 17.641 ms
```

### navigation_nodes?parent_path=eq.us/statute/3 (direct read, anon policy)

```
Limit  (cost=4.44..2209.67 rows=100 width=263) (actual time=0.839..0.964 rows=100 loops=1)
  Buffers: shared hit=122 read=6
  ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes  (cost=4.44..3643.08 rows=165 width=263) (actual time=0.838..0.958 rows=100 loops=1)
        Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/3'::text))
        Filter: ((NOT (hashed SubPlan 3)) AND (hashed SubPlan 2))
        Rows Removed by Filter: 10
        Buffers: shared hit=122 read=6
        SubPlan 3
          ->  ProjectSet  (cost=0.00..2.77 rows=500 width=32) (actual time=0.045..0.690 rows=456 loops=1)
                Buffers: shared hit=12
                ->  Result  (cost=0.00..0.01 rows=1 width=0) (actual time=0.000..0.001 rows=1 loops=1)
        SubPlan 2
          ->  Hash Join  (cost=1.33..3.72 rows=66 width=30) (actual time=0.022..0.039 rows=60 loops=1)
                Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                Buffers: shared hit=2
                ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.008..0.013 rows=74 loops=1)
                      Buffers: shared hit=1
                ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.009..0.009 rows=12 loops=1)
                      Buckets: 1024  Batches: 1  Memory Usage: 9kB
                      Buffers: shared hit=1
                      ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.003..0.004 rows=12 loops=1)
                            Buffers: shared hit=1
Planning:
  Buffers: shared hit=6
Planning Time: 0.239 ms
Execution Time: 0.995 ms
```
