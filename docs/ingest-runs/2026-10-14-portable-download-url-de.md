# DE Kindergeld

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
type. 33 scopes, 1186 repaired rows (inventory and provisions), 0 other
differences. Per-scope reports, source hashes and the exact commands: `2026-10-14-portable-download-url-de-audit.json`.

| Locked scope | Mode | Rows repaired | New download URLs | Media types |
| --- | --- | ---: | ---: | --- |
| `de/guidance/2026-09-08-de-kindergeld-eea-parties` | reextract | 4 | 1 | text/html (4) |
| `de/guidance/2026-09-08-de-kindergeld-handbooks-retained` | reextract | 8 | 2 | text/html (8) |
| `de/guidance/2026-09-09-de-kindergeld-adult-services` | reextract | 8 | 2 | application/pdf (8) |
| `de/guidance/2026-09-09-de-kindergeld-allowance-explanation` | reextract | 4 | 1 | application/pdf (4) |
| `de/guidance/2026-09-09-de-kindergeld-bmf-letter-context` | reextract | 12 | 3 | application/pdf (8), text/html (4) |
| `de/guidance/2026-09-09-de-kindergeld-civil-partner-letter` | reextract | 4 | 1 | text/html (4) |
| `de/guidance/2026-09-10-de-kindergeld-disability-case` | reextract | 4 | 1 | application/pdf (4) |
| `de/guidance/2026-09-11-de-kindergeld-bgh-counterpart` | reextract | 4 | 1 | application/pdf (4) |
| `de/guidance/2026-09-11-de-kindergeld-bgh-form-predecessor` | reextract | 4 | 1 | application/pdf (4) |
| `de/guidance/2026-09-14-de-kindergeld-dakg2025-evidence` | reextract | 4 | 1 | application/pdf (4) |
| `de/guidance/2026-09-14-de-kindergeld-dakg2025-sections` | reextract | 842 | 1 | application/pdf (842) |
| `de/guidance/2026-09-15-de-kindergeld-cross-border-priority` | reextract | 20 | 5 | application/pdf (20) |
| `de/guidance/2026-09-15-de-kindergeld-dakg2025-preface` | reextract | 4 | 1 | application/pdf (4) |
| `de/guidance/2026-09-15-de-kindergeld-eu-priority-references` | reextract | 28 | 7 | text/html (28) |
| `de/guidance/2026-09-15-de-kindergeld-priority-followup` | reextract | 16 | 4 | application/pdf (12), text/html (4) |
| `de/regulation/2026-09-08-de-kindergeld-arb` | reextract | 4 | 1 | application/pdf (4) |
| `de/regulation/2026-09-08-de-kindergeld-bilateral` | reextract | 88 | 22 | application/pdf (88) |
| `de/regulation/2026-09-08-de-kindergeld-eea` | reextract | 4 | 1 | application/pdf (4) |
| `de/regulation/2026-09-08-de-kindergeld-withdrawal` | reextract | 4 | 1 | application/pdf (4) |
| `de/regulation/2026-09-09-de-kindergeld-eu-articles` | reextract | 32 | 2 | application/pdf (32) |
| `de/regulation/2026-09-09-de-kindergeld-swiss-coordination` | reextract | 8 | 2 | application/pdf (8) |
| `de/regulation/2026-09-09-de-kindergeld-treaty-texts` | reextract | 8 | 2 | application/pdf (8) |
| `de/regulation/2026-09-14-de-kindergeld-eu-territory` | reextract | 12 | 3 | text/html (12) |
| `de/statute/2026-09-08-de-kindergeld-parentage-context` | reextract | 4 | 1 | application/pdf (4) |
| `de/statute/2026-09-08-de-kindergeld-parentage-history` | reextract | 4 | 1 | application/pdf (4) |
| `de/statute/2026-09-09-de-kindergeld-adult-service-history` | reextract | 4 | 1 | text/html (4) |
| `de/statute/2026-09-09-de-kindergeld-marginal-employment-history` | reextract | 4 | 1 | text/html (4) |
| `de/statute/2026-09-09-de-kindergeld-sgbiv8-threshold-paragraph` | reextract | 4 | 1 | text/html (4) |
| `de/statute/2026-09-09-de-kindergeld-treaty-texts` | reextract | 8 | 2 | application/pdf (8) |
| `de/statute/2026-09-10-de-kindergeld-maternity-amendments` | reextract | 8 | 2 | application/pdf (8) |
| `de/statute/2026-09-10-de-kindergeld-maternity-history` | reextract | 8 | 2 | text/html (8) |
| `de/statute/2026-09-11-de-kindergeld-disability-definition-history` | reextract | 8 | 2 | text/html (8) |
| `de/statute/2026-09-11-de-kindergeld-disability-paragraphs` | reextract | 8 | 2 | text/html (8) |

## Releases

Jurisdiction owner: Pavel Makarchuk (the DE Kindergeld scopes and their de-rulespec-2026-09-* selectors). No selector changes here. The predecessors appear in
33 tracked selector(s); serving keeps the old rows until the owner cuts a
release that names the successors in their place (`scripts/audit_local_file_urls.py
--release <selector>` lists any leaky scope a selector still names).

- `de/guidance/2026-09-08-de-kindergeld-eea-parties`: 33 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-08-de-kindergeld-handbooks-retained`: 33 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-09-de-kindergeld-adult-services`: 20 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-09-de-kindergeld-allowance-explanation`: 28 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-09-de-kindergeld-bmf-letter-context`: 27 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-09-de-kindergeld-civil-partner-letter`: 26 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-10-de-kindergeld-disability-case`: 16 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-11-de-kindergeld-bgh-counterpart`: 9 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-11-de-kindergeld-bgh-form-predecessor`: 8 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-14-de-kindergeld-dakg2025-evidence`: 6 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-14-de-kindergeld-dakg2025-sections`: 5 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-15-de-kindergeld-cross-border-priority`: 3 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-15-de-kindergeld-dakg2025-preface`: 4 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/guidance/2026-09-15-de-kindergeld-eu-priority-references`: 1 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-eu-priority-references`
- `de/guidance/2026-09-15-de-kindergeld-priority-followup`: 2 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/regulation/2026-09-08-de-kindergeld-arb`: 33 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/regulation/2026-09-08-de-kindergeld-bilateral`: 33 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/regulation/2026-09-08-de-kindergeld-eea`: 33 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/regulation/2026-09-08-de-kindergeld-withdrawal`: 33 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/regulation/2026-09-09-de-kindergeld-eu-articles`: 24 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/regulation/2026-09-09-de-kindergeld-swiss-coordination`: 25 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/regulation/2026-09-09-de-kindergeld-treaty-texts`: 26 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/regulation/2026-09-14-de-kindergeld-eu-territory`: 7 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/statute/2026-09-08-de-kindergeld-parentage-context`: 30 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/statute/2026-09-08-de-kindergeld-parentage-history`: 31 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/statute/2026-09-09-de-kindergeld-adult-service-history`: 20 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/statute/2026-09-09-de-kindergeld-marginal-employment-history`: 18 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/statute/2026-09-09-de-kindergeld-sgbiv8-threshold-paragraph`: 17 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/statute/2026-09-09-de-kindergeld-treaty-texts`: 26 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/statute/2026-09-10-de-kindergeld-maternity-amendments`: 16 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/statute/2026-09-10-de-kindergeld-maternity-history`: 16 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/statute/2026-09-11-de-kindergeld-disability-definition-history`: 10 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
- `de/statute/2026-09-11-de-kindergeld-disability-paragraphs`: 9 selector(s), most recent `de-rulespec-2026-09-15-kindergeld-priority-followup`
