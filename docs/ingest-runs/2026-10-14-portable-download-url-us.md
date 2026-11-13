# US

## Why

Before axiom-corpus#878, `extract-official-documents` recorded a manifest `local_path` copy
as `metadata.download_url = file:///<extracting machine path>` with a null `content_type`, and
the July recovery batch did the same for files it read from disk. These scopes therefore
publish paths on the machines that extracted them. Each successor below is the same scope
re-versioned as `<version>-r2026-10-14-portable-download-url`, written from the locked scope's own source bytes by
`scripts/repair_local_file_download_urls.py`:

- `reextract`: the fixed extractor over the committed manifest's entries, with `local_path`
  pointing at the locked source file and with the locked `source_as_of`, `expression_date` and
  manifest metadata. The extractor records the manifest's `download_url` (else `source_url`)
  and the source format's media type.
- `rewrite`: a byte-for-byte copy with each `file:` download URL replaced by the web URL the
  other artifact records for the same citation, else the row's own `source_url`; a null
  `content_type` becomes the other artifact's, else the source format's media type.

## Verification

The script's `verify` compared every source file (sha256), inventory item, provision row and
coverage field of each successor with its locked predecessor. The only differences are the
version, version-bearing source paths and ids, and `metadata.download_url`/`content_type` on
rows that recorded a `file:` URL. Every repaired row now records an `https://` URL and a media
type. 5 scopes, 140 repaired rows (inventory and provisions), 0 other
differences. Per-scope reports, source hashes and the exact commands: `2026-10-14-portable-download-url-us-audit.json`.

| Locked scope | Mode | Rows repaired | New download URLs | Media types |
| --- | --- | ---: | ---: | --- |
| `us-mn/manual/2026-10-12-w7-state-benefits-manual-mn` | reextract | 20 | 4 | text/html (20) |
| `us-co/statute/2026-07-13-us-co-tax-credit-session-laws-r2026-07-19-expression-date` | rewrite | 4 | 2 | application/pdf (4) |
| `us-nc/regulation/2026-05-29` | rewrite | 92 | 23 | application/pdf (92) |
| `us/guidance/2026-05-17-ssa-automatic-determinations-2026` | rewrite | 20 | 6 | text/html (20) |
| `us/guidance/2026-05-26-ssa-contribution-and-benefit-base-2024` | rewrite | 4 | 1 | text/html (4) |

## Releases

Jurisdiction owner: Max Ghenis for the recovery-batch scopes (us SSA, us-co, us-nc); Pavel Makarchuk for us-mn W7 (us-rulespec-2026-10-13-w7-bundle-gaps-union). No selector changes here. The predecessors appear in
41 tracked selector(s); serving keeps the old rows until the owner cuts a
release that names the successors in their place (`scripts/audit_local_file_urls.py
--release <selector>` lists any leaky scope a selector still names).

- `us-mn/manual/2026-10-12-w7-state-benefits-manual-mn`: 1 selector(s), most recent `us-rulespec-2026-10-13-w7-bundle-gaps-union`
- `us-co/statute/2026-07-13-us-co-tax-credit-session-laws-r2026-07-19-expression-date`: 38 selector(s), most recent `us-rulespec-2026-10-22-ca-concurrent-versions`
- `us-nc/regulation/2026-05-29`: 41 selector(s), most recent `us-rulespec-2026-10-22-ca-concurrent-versions`
- `us/guidance/2026-05-17-ssa-automatic-determinations-2026`: 41 selector(s), most recent `us-rulespec-2026-10-22-ca-concurrent-versions`
- `us/guidance/2026-05-26-ssa-contribution-and-benefit-base-2024`: 41 selector(s), most recent `us-rulespec-2026-10-22-ca-concurrent-versions`
