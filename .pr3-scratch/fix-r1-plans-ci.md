401299 provision rows, 306923 base rows, 456 shadowed; serving the release derived the layered state in 6.9 s.

### current_provisions?citation_path=eq.<base-only path>

```
Nested Loop Anti Join  (cost=5.57..29.95 rows=2 width=726) (actual time=0.091..0.094 rows=1 loops=1)
  Buffers: shared hit=4 read=4
  ->  Hash Semi Join  (cost=5.30..17.35 rows=2 width=726) (actual time=0.080..0.082 rows=1 loops=1)
        Hash Cond: ((p.jurisdiction = active.jurisdiction) AND (COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text) = active.document_class) AND (p.version = scopes.version))
        Buffers: shared hit=2 read=4
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.42..12.35 rows=2 width=726) (actual time=0.014..0.015 rows=1 loops=1)
              Index Cond: (citation_path = 'us/statute/30/500'::text)
              Buffers: shared read=4
        ->  Hash  (cost=3.72..3.72 rows=66 width=41) (actual time=0.059..0.060 rows=60 loops=1)
              Buckets: 1024  Batches: 1  Memory Usage: 13kB
              Buffers: shared hit=2
              ->  Hash Join  (cost=1.33..3.72 rows=66 width=41) (actual time=0.008..0.027 rows=60 loops=1)
                    Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                    Buffers: shared hit=2
                    ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.003..0.009 rows=74 loops=1)
                          Buffers: shared hit=1
                    ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.004..0.004 rows=12 loops=1)
                          Buckets: 1024  Batches: 1  Memory Usage: 9kB
                          Buffers: shared hit=1
                          ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.001..0.002 rows=12 loops=1)
                                Buffers: shared hit=1
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..4.29 rows=1 width=16) (actual time=0.009..0.009 rows=0 loops=1)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=2
Planning:
  Buffers: shared hit=22
Planning Time: 0.195 ms
Execution Time: 0.111 ms
```

### current_provisions?citation_path=eq.<collision path>

```
Nested Loop Anti Join  (cost=5.57..29.95 rows=2 width=726) (actual time=0.042..0.042 rows=1 loops=1)
  Buffers: shared hit=9 read=4
  ->  Hash Semi Join  (cost=5.30..17.35 rows=2 width=726) (actual time=0.035..0.039 rows=2 loops=1)
        Hash Cond: ((p.jurisdiction = active.jurisdiction) AND (COALESCE(NULLIF(p.doc_type, ''::text), 'unknown'::text) = active.document_class) AND (p.version = scopes.version))
        Buffers: shared hit=4 read=4
        ->  Index Scan using idx_provisions_citation_path_version on provisions p  (cost=0.42..12.35 rows=2 width=726) (actual time=0.008..0.013 rows=3 loops=1)
              Index Cond: (citation_path = 'us/statute/3/1'::text)
              Buffers: shared hit=2 read=4
        ->  Hash  (cost=3.72..3.72 rows=66 width=41) (actual time=0.022..0.022 rows=60 loops=1)
              Buckets: 1024  Batches: 1  Memory Usage: 13kB
              Buffers: shared hit=2
              ->  Hash Join  (cost=1.33..3.72 rows=66 width=41) (actual time=0.007..0.016 rows=60 loops=1)
                    Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                    Buffers: shared hit=2
                    ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.002..0.005 rows=74 loops=1)
                          Buffers: shared hit=1
                    ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.003..0.004 rows=12 loops=1)
                          Buckets: 1024  Batches: 1  Memory Usage: 9kB
                          Buffers: shared hit=1
                          ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.001..0.002 rows=12 loops=1)
                                Buffers: shared hit=1
  ->  Index Only Scan using idx_layered_shadowed_rows_provision_id on layered_shadowed_rows shadowed  (cost=0.27..4.29 rows=1 width=16) (actual time=0.001..0.001 rows=0 loops=2)
        Index Cond: (provision_id = p.id)
        Heap Fetches: 0
        Buffers: shared hit=5
Planning:
  Buffers: shared hit=22
Planning Time: 0.190 ms
Execution Time: 0.055 ms
```

### current_navigation_nodes?jurisdiction=eq.us&order=citation_path.asc&limit=1000

```
Limit  (cost=8.14..25569.77 rows=1000 width=52) (actual time=1.576..3.809 rows=1000 loops=1)
  Buffers: shared hit=500 read=732
  ->  Merge Append  (cost=8.14..3169701.70 rows=124002 width=52) (actual time=1.576..3.773 rows=1000 loops=1)
        Sort Key: n.citation_path
        Buffers: shared hit=500 read=732
        ->  Index Scan using idx_navigation_nodes_jurisdiction_citation_path on navigation_nodes n  (cost=7.84..3166671.88 rows=113166 width=51) (actual time=1.566..3.566 rows=699 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 310
              Buffers: shared hit=208 read=732
              SubPlan 1
                ->  Hash Join  (cost=1.33..3.72 rows=66 width=30) (actual time=0.020..0.038 rows=60 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=2
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.005..0.010 rows=74 loops=1)
                            Buffers: shared hit=1
                      ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.009..0.009 rows=12 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 9kB
                            Buffers: shared hit=1
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.003..0.004 rows=12 loops=1)
                                  Buffers: shared hit=1
              SubPlan 2
                ->  Nested Loop  (cost=0.00..3.53 rows=2 width=12) (actual time=0.013..0.016 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 22
                      Buffers: shared hit=2
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..1.12 rows=12 width=24) (actual time=0.002..0.002 rows=12 loops=1)
                            Buffers: shared hit=1
                      ->  Materialize  (cost=0.00..1.94 rows=2 width=25) (actual time=0.000..0.001 rows=2 loops=12)
                            Buffers: shared hit=1
                            ->  Seq Scan on release_scopes scopes_1  (cost=0.00..1.93 rows=2 width=25) (actual time=0.002..0.006 rows=2 loops=1)
                                  Filter: (layer = 'base'::text)
                                  Rows Removed by Filter: 72
                                  Buffers: shared hit=1
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.004..0.041 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..574.82 rows=10836 width=33) (actual time=0.004..0.458 rows=10836 loops=1)
                      Heap Fetches: 0
                      Buffers: shared hit=103
        ->  Index Scan using idx_layered_navigation_overrides_citation_path on layered_navigation_overrides o  (cost=0.29..1789.79 rows=10836 width=66) (actual time=0.008..0.151 rows=302 loops=1)
              Index Cond: (jurisdiction = 'us'::text)
              Buffers: shared hit=292
Planning:
  Buffers: shared hit=8
Planning Time: 0.233 ms
Execution Time: 3.861 ms
```

### current_navigation_nodes?parent_path=eq.us/statute/2&order=sort_key (merged children)

```
Limit  (cost=8.14..3340.24 rows=100 width=265) (actual time=1.372..1.586 rows=100 loops=1)
  Buffers: shared hit=121 read=106
  ->  Merge Append  (cost=8.14..5739.35 rows=172 width=265) (actual time=1.372..1.583 rows=100 loops=1)
        Sort Key: n.sort_key
        Buffers: shared hit=121 read=106
        ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes n  (cost=7.84..5729.31 rows=171 width=265) (actual time=1.366..1.574 rows=100 loops=1)
              Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/2'::text))
              Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
              Rows Removed by Filter: 2
              Buffers: shared hit=119 read=106
              SubPlan 1
                ->  Hash Join  (cost=1.33..3.72 rows=66 width=30) (actual time=0.015..0.032 rows=60 loops=1)
                      Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                      Buffers: shared hit=2
                      ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.004..0.009 rows=74 loops=1)
                            Buffers: shared hit=1
                      ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.008..0.008 rows=12 loops=1)
                            Buckets: 1024  Batches: 1  Memory Usage: 9kB
                            Buffers: shared hit=1
                            ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.003..0.004 rows=12 loops=1)
                                  Buffers: shared hit=1
              SubPlan 2
                ->  Nested Loop  (cost=0.00..3.53 rows=2 width=12) (actual time=0.025..0.027 rows=2 loops=1)
                      Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                      Rows Removed by Join Filter: 22
                      Buffers: shared hit=2
                      ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..1.12 rows=12 width=24) (actual time=0.001..0.002 rows=12 loops=1)
                            Buffers: shared hit=1
                      ->  Materialize  (cost=0.00..1.94 rows=2 width=25) (actual time=0.000..0.002 rows=2 loops=12)
                            Buffers: shared hit=1
                            ->  Seq Scan on release_scopes scopes_1  (cost=0.00..1.93 rows=2 width=25) (actual time=0.002..0.018 rows=2 loops=1)
                                  Filter: (layer = 'base'::text)
                                  Rows Removed by Filter: 72
                                  Buffers: shared hit=1
              SubPlan 4
                ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.003..0.029 rows=456 loops=1)
                      Buffers: shared hit=12
              SubPlan 6
                ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..574.82 rows=10836 width=33) (actual time=0.004..0.354 rows=10836 loops=1)
                      Heap Fetches: 0
                      Buffers: shared hit=103
        ->  Index Scan using idx_layered_navigation_overrides_parent_sort on layered_navigation_overrides o  (cost=0.29..8.31 rows=1 width=286) (actual time=0.005..0.005 rows=0 loops=1)
              Index Cond: (parent_path = 'us/statute/2'::text)
              Filter: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text))
              Buffers: shared hit=2
Planning:
  Buffers: shared hit=8
Planning Time: 0.426 ms
Execution Time: 1.633 ms
```

### current_navigation_nodes?select=provision_id&parent_path=eq.us/statute/2&order=sort_key,path,id&limit=1000 (client children page)

```
Limit  (cost=41.47..5747.09 rows=172 width=106) (actual time=2.319..5.546 rows=1000 loops=1)
  Buffers: shared hit=413 read=743
  ->  Incremental Sort  (cost=41.47..5747.09 rows=172 width=106) (actual time=2.319..5.489 rows=1000 loops=1)
        Sort Key: n.sort_key, n.path, n.id
        Presorted Key: n.sort_key
        Full-sort Groups: 32  Sort Method: quicksort  Average Memory: 29kB  Peak Memory: 29kB
        Buffers: shared hit=413 read=743
        ->  Merge Append  (cost=8.14..5739.35 rows=172 width=106) (actual time=2.250..5.288 rows=1001 loops=1)
              Sort Key: n.sort_key
              Buffers: shared hit=413 read=743
              ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes n  (cost=7.84..5729.31 rows=171 width=106) (actual time=2.240..5.218 rows=1001 loops=1)
                    Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/2'::text))
                    Filter: ((hashed SubPlan 1) AND ((NOT (hashed SubPlan 2)) OR ((NOT (hashed SubPlan 4)) AND (NOT (hashed SubPlan 6)))))
                    Rows Removed by Filter: 19
                    Buffers: shared hit=411 read=743
                    SubPlan 1
                      ->  Hash Join  (cost=1.33..3.72 rows=66 width=30) (actual time=0.013..0.031 rows=60 loops=1)
                            Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                            Buffers: shared hit=2
                            ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.003..0.008 rows=74 loops=1)
                                  Buffers: shared hit=1
                            ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.007..0.007 rows=12 loops=1)
                                  Buckets: 1024  Batches: 1  Memory Usage: 9kB
                                  Buffers: shared hit=1
                                  ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.002..0.003 rows=12 loops=1)
                                        Buffers: shared hit=1
                    SubPlan 2
                      ->  Nested Loop  (cost=0.00..3.53 rows=2 width=12) (actual time=0.011..0.014 rows=2 loops=1)
                            Join Filter: ((scopes_1.jurisdiction = active_1.jurisdiction) AND (scopes_1.document_class = active_1.document_class) AND (scopes_1.release_name = active_1.release_name))
                            Rows Removed by Join Filter: 22
                            Buffers: shared hit=2
                            ->  Seq Scan on active_scope_pointer active_1  (cost=0.00..1.12 rows=12 width=24) (actual time=0.001..0.001 rows=12 loops=1)
                                  Buffers: shared hit=1
                            ->  Materialize  (cost=0.00..1.94 rows=2 width=25) (actual time=0.000..0.001 rows=2 loops=12)
                                  Buffers: shared hit=1
                                  ->  Seq Scan on release_scopes scopes_1  (cost=0.00..1.93 rows=2 width=25) (actual time=0.002..0.006 rows=2 loops=1)
                                        Filter: (layer = 'base'::text)
                                        Rows Removed by Filter: 72
                                        Buffers: shared hit=1
                    SubPlan 4
                      ->  Seq Scan on layered_shadowed_rows shadowed  (cost=0.00..16.56 rows=456 width=33) (actual time=0.002..0.041 rows=456 loops=1)
                            Buffers: shared hit=12
                    SubPlan 6
                      ->  Index Only Scan using layered_navigation_overrides_pkey on layered_navigation_overrides overrides  (cost=0.29..574.82 rows=10836 width=33) (actual time=0.004..0.654 rows=10836 loops=1)
                            Heap Fetches: 0
                            Buffers: shared hit=103
              ->  Index Scan using idx_layered_navigation_overrides_parent_sort on layered_navigation_overrides o  (cost=0.29..8.31 rows=1 width=109) (actual time=0.009..0.009 rows=0 loops=1)
                    Index Cond: (parent_path = 'us/statute/2'::text)
                    Filter: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text))
                    Buffers: shared hit=2
Planning:
  Buffers: shared hit=8
Planning Time: 0.461 ms
Execution Time: 5.636 ms
```

### rpc/get_root_document_counts

```
Function Scan on get_root_document_counts  (cost=0.25..10.25 rows=1000 width=72) (actual time=19.180..19.180 rows=12 loops=1)
  Buffers: shared hit=15467 read=370
Planning Time: 0.004 ms
Execution Time: 19.186 ms
```

### navigation_nodes?parent_path=eq.us/statute/3 (direct read, anon policy)

```
Limit  (cost=4.44..2199.40 rows=100 width=265) (actual time=0.805..0.997 rows=100 loops=1)
  Buffers: shared hit=122 read=6
  ->  Index Scan using idx_navigation_nodes_scope_parent_sort on navigation_nodes  (cost=4.44..4109.03 rows=187 width=265) (actual time=0.804..0.990 rows=100 loops=1)
        Index Cond: ((jurisdiction = 'us'::text) AND (doc_type = 'statute'::text) AND (parent_path = 'us/statute/3'::text))
        Filter: ((NOT (hashed SubPlan 3)) AND (hashed SubPlan 2))
        Rows Removed by Filter: 10
        Buffers: shared hit=122 read=6
        SubPlan 3
          ->  ProjectSet  (cost=0.00..2.77 rows=500 width=32) (actual time=0.057..0.667 rows=456 loops=1)
                Buffers: shared hit=12
                ->  Result  (cost=0.00..0.01 rows=1 width=0) (actual time=0.000..0.000 rows=1 loops=1)
        SubPlan 2
          ->  Hash Join  (cost=1.33..3.72 rows=66 width=30) (actual time=0.020..0.038 rows=60 loops=1)
                Hash Cond: ((scopes.jurisdiction = active.jurisdiction) AND (scopes.document_class = active.document_class) AND (scopes.release_name = active.release_name))
                Buffers: shared hit=2
                ->  Seq Scan on release_scopes scopes  (cost=0.00..1.74 rows=74 width=43) (actual time=0.006..0.011 rows=74 loops=1)
                      Buffers: shared hit=1
                ->  Hash  (cost=1.12..1.12 rows=12 width=24) (actual time=0.009..0.009 rows=12 loops=1)
                      Buckets: 1024  Batches: 1  Memory Usage: 9kB
                      Buffers: shared hit=1
                      ->  Seq Scan on active_scope_pointer active  (cost=0.00..1.12 rows=12 width=24) (actual time=0.003..0.005 rows=12 loops=1)
                            Buffers: shared hit=1
Planning:
  Buffers: shared hit=4
Planning Time: 0.243 ms
Execution Time: 1.035 ms
```
