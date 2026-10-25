# BGH counterpart judgment

The native official-document adapter captures all13 pages of BGH XII ZR129/16
(7March2018), following the pending consumer lead de-kg-suppl-132. The legacy
juris address redirected to an HTML search page; the official decision-search
form supplied the current PDF URL. Only the actual PDF was ingested.

Two native rows retain the document root and complete text. Coverage has zero
missing and extra rows. PDF and body hashes, complete body and reviewed scope
limitations are retained in the adjacent audit JSON. The general BGB126 receipt
requirement is distinct from the special BGB550 rental-documentation result.
No general no-receipt exception or complete contract validity is inferred.

```bash
PYTHONPATH=src axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-09-11-de-kindergeld-bgh-counterpart --manifest manifests/de-kindergeld-bgh-counterpart.yaml
```

The local run used the native adapter's local_path option on the unchanged
HTTPS-downloaded official PDF. The selector retains52 previous scopes and adds
the BGH scope and a separate disability-paragraph scope:54 scopes,10211 rows,407 artifacts. No adapter or generated legal body was
edited. Publication does not activate serving. No certified claim.
