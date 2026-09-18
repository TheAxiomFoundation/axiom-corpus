# DE Kindergeld treaty territory capture

This scope captures complete German TEU Articles 50 and 52 and TFEU Article
355 from EUR-Lex's 7 June 2016 consolidated expression. The original HTML
snapshots are retained without byte normalization. The native official-document
adapter produces three document rows and three complete article rows. Coverage
matches all six inventory citations, with no missing, extra, or duplicate rows.
The companion JSON audit binds each original snapshot and article body by SHA-256.

The public manifest contains official URLs and extraction selectors. Initial
individual-article PDF endpoints returned HTTP 404; the successful captures use
the official HTML endpoints. Extraction was replayed from those exact downloaded
bytes with a temporary runtime manifest supplying local_path for each source.
To reproduce, copy the public manifest, set each document's local_path to its
snapshot_path in the audit, and run:

```bash
axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-14-de-kindergeld-eu-territory \
  --manifest /path/to/runtime-manifest.json
```

The local-file download_url in generated metadata records the actual replay
transport. source_url and the audit retain the official origin. No provision
body, inventory, coverage report, or source snapshot was manually edited.

The body comparison starts at the article heading inside the legal document
container, includes every following legal paragraph, and normalizes whitespace
only for comparison. TEU Article 50 contains all five paragraphs; Article 52
contains both paragraphs; TFEU Article 355 contains all six paragraphs including
paragraph 5(a)–(c). Masthead and navigation text are excluded.

The expression date is a publication/consolidation date, not commencement.
Article 52's historical member list includes the United Kingdom. Determining
membership in 2025 requires reconciliation with withdrawal instruments. Article
355's territorial exceptions, annex, treaty and protocol references remain
legal dependencies. These captures neither determine territorial eligibility
nor close a ledger dependency without an authenticated encoding and its bindings.

The new cumulative release selector preserves all 55 preceding DE scopes in
their existing order and adds this one scope. No US release selector is changed.
Signing and publication must use the native ingest/release workflow after review;
a signed capture is not a certification claim.
