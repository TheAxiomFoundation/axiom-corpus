# bo and mz

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
type. 2 scopes, 16 repaired rows (inventory and provisions), 0 other
differences. Per-scope reports, source hashes and the exact commands: `2026-10-14-portable-download-url-bomz-audit.json`.

| Locked scope | Mode | Rows repaired | New download URLs | Media types |
| --- | --- | ---: | ---: | --- |
| `bo/regulation/2026-07-23-bo-bolmod-t1-regulations` | reextract | 4 | 1 | application/pdf (4) |
| `mz/statute/2026-07-23-mz-mozmod-t1-statutes` | reextract | 12 | 3 | application/pdf (12) |

## Releases

Jurisdiction owner: Max Ghenis (bo BolMod and mz MozMod tranche 1 ingests). No selector changes here. The predecessors appear in
4 tracked selector(s); serving keeps the old rows until the owner cuts a
release that names the successors in their place (`scripts/audit_local_file_urls.py
--release <selector>` lists any leaky scope a selector still names).

- `bo/regulation/2026-07-23-bo-bolmod-t1-regulations`: 3 selector(s), most recent `bo-rulespec-2026-07-24-r2`
- `mz/statute/2026-07-23-mz-mozmod-t1-statutes`: 1 selector(s), most recent `mz-rulespec-2026-07-23`
