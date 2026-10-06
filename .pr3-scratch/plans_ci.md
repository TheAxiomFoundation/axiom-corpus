401299 provision rows, 306923 base rows, 456 shadowed; serving the release derived the layered state in 24.7 s.

### current_provisions?citation_path=eq.<base-only path>

```
Nested Loop Anti Join  (cost=5.57..29.96 rows=2 width=726) (actual time=0.151..0.153 rows=1 loops=1)
  Buffers: shared hit=8
  ->  Hash Semi Join  (cost=5.30..17.36 rows=2 width=726) (actual time=0.146..0.147 rows=1 loops=1)
        Hash Cond: ((p.jurisdiction = active.jurisdiction) AND (COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text) = active.document_class) AND (p.version = scopes.version))
        Buffers: shared hit=6
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.42..12.36 rows=2 width=726) (actual time=0.012..0.012 rows=1 loops=1)
              Index Cond: (citation_path = 'us/statute/30/500'::text)
              Buffers: shared hit=4
        ->  Hash  (cost=3.72..3.72 rows=66 width=41) (actual time=0.116..0.117 rows=60 loops=1)
              Buckets: 1024  Batches: 1  Memory Usage: 13kB
              Buffers: shared hit=2
              ->  Hash Join  (cost=1.33..3.72 rows=66 width=41) (actual time=0.043..0.055 rows=60 loops=1)
                    Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                    Buffers: shared hit=2
                    ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.027..0.031 rows=74 loops=1)
                          Buffers: shared hit=1
                    ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.008..0.008 rows=12 loops=1)
                          Buckets: 1024  Batches: 1  Memory Usage: 9kB
                          Buffers: shared hit=1
                          ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.003..0.004 rows=12 loops=1)
                                Buffers: shared hit=1
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..4.29 rows=1 width=16) (actual time=0.004..0.004 rows=0 loops=1)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=2
Planning:
  Buffers: shared hit=22
Planning Time: 0.257 ms
Execution Time: 0.173 ms
```

### current_provisions?citation_path=eq.<collision path>

```
Nested Loop Anti Join  (cost=5.57..29.96 rows=2 width=726) (actual time=0.045..0.045 rows=1 loops=1)
  Buffers: shared hit=13
  ->  Hash Semi Join  (cost=5.30..17.36 rows=2 width=726) (actual time=0.036..0.038 rows=2 loops=1)
        Hash Cond: ((p.jurisdiction = active.jurisdiction) AND (COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text) = active.document_class) AND (p.version = scopes.version))
        Buffers: shared hit=8
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.42..12.36 rows=2 width=726) (actual time=0.006..0.008 rows=3 loops=1)
              Index Cond: (citation_path = 'us/statute/3/1'::text)
              Buffers: shared hit=6
        ->  Hash  (cost=3.72..3.72 rows=66 width=41) (actual time=0.026..0.026 rows=60 loops=1)
              Buckets: 1024  Batches: 1  Memory Usage: 13kB
              Buffers: shared hit=2
              ->  Hash Join  (cost=1.33..3.72 rows=66 width=41) (actual time=0.008..0.019 rows=60 loops=1)
                    Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                    Buffers: shared hit=2
                    ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.002..0.006 rows=74 loops=1)
                          Buffers: shared hit=1
                    ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.004..0.004 rows=12 loops=1)
                          Buckets: 1024  Batches: 1  Memory Usage: 9kB
                          Buffers: shared hit=1
                          ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.001..0.002 rows=12 loops=1)
                                Buffers: shared hit=1
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..4.29 rows=1 width=16) (actual time=0.003..0.003 rows=0 loops=2)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=5
Planning:
  Buffers: shared hit=22
Planning Time: 0.208 ms
Execution Time: 0.064 ms
```

### current_navigation_nodes?jurisdiction=eq.us&order=citation_path.asc&limit=1000

```
Limit  (cost=8.14..25572.80 rows=1000 width=52) (actual time=2.234..18.652 rows=1000 loops=1)
  Buffers: shared hit=1232
  ->  Merge Append  (cost=8.14..3174577.02 rows=124178 width=52) (actual time=2.233..18.606 rows=1000 loops=1)
        Sort Key: n.citation_path
        Buffers: shared hit=1232
        ->  Index Scan using idx_navigation_nodes_jurisdiction_citation_path on navigation_nodes n  (cost=7.84..3171545.44 rows=113342 width=51) (actual time=2.209..18.355 rows=699 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 310
              Buffers: shared hit=940
              SubPlan 1
                ->  Hash Join  (cost=1.33..3.72 rows=66 width=30) (actual time=0.013..0.030 rows=60 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=2
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.003..0.008 rows=74 loops=1)
                            Buffers: shared hit=1
                      ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.006..0.007 rows=12 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 9kB
                            Buffers: shared hit=1
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.002..0.003 rows=12 loops=1)
                                  Buffers: shared hit=1
              SubPlan 2
                ->  Nested Loop  (cost=0.00..3.53 rows=2 width=12) (actual time=0.012..0.015 rows=2 loops=1)
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
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.002..0.045 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..574.82 rows=10836 width=33) (actual time=0.005..0.672 rows=10836 loops=1)
                      Heap Fetches: 0
                      Buffers: shared hit=103
        ->  Index Scan using idx_layered_navigation_overrides_citation_path on layered_navigation_overrides o  (cost=0.29..1789.79 rows=10836 width=66) (actual time=0.022..0.168 rows=302 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Buffers: shared hit=292
Planning:
  Buffers: shared hit=8
Planning Time: 0.276 ms
Execution Time: 18.735 ms
```

### current_navigation_nodes?parent_path=eq.us/statute/2&order=sort_key (merged children)

```
Limit  (cost=8.14..3337.23 rows=100 width=263) (actual time=16.568..16.801 rows=100 loops=1)
  Buffers: shared hit=227
  ->  Merge Append  (cost=8.14..5334.68 rows=160 width=263) (actual time=16.567..16.795 rows=100 loops=1)
        Sort Key: n.sort_key
        Buffers: shared hit=227
        ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes n  (cost=7.84..5324.77 rows=159 width=263) (actual time=16.554..16.776 rows=100 loops=1)
              Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/2'::text))
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 2
              Buffers: shared hit=225
              SubPlan 1
                ->  Hash Join  (cost=1.33..3.72 rows=66 width=30) (actual time=0.017..0.035 rows=60 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=2
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.005..0.010 rows=74 loops=1)
                            Buffers: shared hit=1
                      ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.008..0.009 rows=12 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 9kB
                            Buffers: shared hit=1
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.003..0.004 rows=12 loops=1)
                                  Buffers: shared hit=1
              SubPlan 2
                ->  Nested Loop  (cost=0.00..3.53 rows=2 width=12) (actual time=0.012..0.153 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 22
                      Buffers: shared hit=2
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..1.12 rows=12 width=24) (actual time=0.001..0.002 rows=12 loops=1)
                            Buffers: shared hit=1
                      ->  Materialize  (cost=0.00..1.94 rows=2 width=25) (actual time=0.000..0.012 rows=2 loops=12)
                            Buffers: shared hit=1
                            ->  Seq Scan on release_scopes scopes_1  (cost=0.00..1.93 rows=2 width=25) (actual time=0.002..0.007 rows=2 loops=1)
                                  Filter: (layer = 'base'::text)
                                  Rows Removed by Filter: 72
                                  Buffers: shared hit=1
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.005..0.051 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..574.82 rows=10836 width=33) (actual time=0.006..11.341 rows=10836 loops=1)
                      Heap Fetches: 0
                      Buffers: shared hit=103
        ->  Index Scan using idx_layered_navigation_overrides_parent_sort on layered_navigation_overrides o  (cost=0.29..8.31 rows=1 width=286) (actual time=0.012..0.012 rows=0 loops=1)
              Index Cond: (parent_path = 'us/statute/2'::text)
              Filter: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text))
              Buffers: shared hit=2
Planning:
  Buffers: shared hit=8
Planning Time: 5.146 ms
Execution Time: 16.858 ms
```

### rpc/get_root_document_counts

```
Function Scan on get_root_document_counts  (cost=0.25..10.25 rows=1000 width=72) (actual time=46.442..46.443 rows=12 loops=1)
  Buffers: shared hit=15837
Planning Time: 0.017 ms
Execution Time: 46.452 ms
```

### navigation_nodes?parent_path=eq.us/statute/3 (direct read, anon policy)

```
Limit  (cost=4.44..2204.54 rows=100 width=263) (actual time=0.880..1.013 rows=100 loops=1)
  Buffers: shared hit=128
  ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes  (cost=4.44..4426.64 rows=201 width=263) (actual time=0.879..1.007 rows=100 loops=1)
        Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/3'::text))
        Filter: ((NOT (hashed SubPlan 3)) AND (hashed SubPlan 2))
        Rows Removed by Filter: 10
        Buffers: shared hit=128
        SubPlan 3
          ->  ProjectSet  (cost=0.00..2.77 rows=500 width=32) (actual time=0.060..0.743 rows=456 loops=1)
                Buffers: shared hit=12
                ->  Result  (cost=0.00..0.01 rows=1 width=0) (actual time=0.000..0.000 rows=1 loops=1)
        SubPlan 2
          ->  Hash Join  (cost=1.33..3.72 rows=66 width=30) (actual time=0.017..0.038 rows=60 loops=1)
                Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                Buffers: shared hit=2
                ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.004..0.009 rows=74 loops=1)
                      Buffers: shared hit=1
                ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.008..0.009 rows=12 loops=1)
                      Buckets: 1024  Batches: 1  Memory Usage: 9kB
                      Buffers: shared hit=1
                      ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.003..0.004 rows=12 loops=1)
                            Buffers: shared hit=1
Planning:
  Buffers: shared hit=4
Planning Time: 0.324 ms
Execution Time: 1.049 ms
```
