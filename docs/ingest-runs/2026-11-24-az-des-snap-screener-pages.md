# Arizona DES SNAP screener pages (person-saved captures)

Date: 2026-11-24. Branch `claude/az-des-snap-screener-pages`, cut from `origin/main` 085e7fe07.

Scopes:

- `us-az/manual/2026-11-24-az-des-snap-screener-pages` (11 documents, 88 rows)
- `us-az/policy/2026-11-24-az-des-snap-screener-pages` (1 document, 2 rows)
- `us-az/manual/2026-11-24-az-des-faa6-utility-allowance-ffy-2027` (1 document, 2 rows)

## Why

The Arizona SNAP screener cites FAA3, FAA4 and FAA6 pages of the DES Cash and Nutrition
Assistance Policy Manual and the FAA2 2026 ABAWD geographic-waiver bulletin. None is in the
corpus. The program bundle lists 11 of the citation paths with the note "Draft manifest ..., not
in a corpus PR". The FFY 2027 amounts (income standards, resource limit, utility allowances) were
missing sources for FY2027 parity.

## Official source and access

`dbmefaapolicy.azdes.gov` answers unattended clients with a Cloudflare challenge. No automated
fetch, no `request.browser_impersonation` and no third-party copy was used.

A person opened each official URL in an ordinary Chrome browser on 2026-11-24 between 9:01pm
and 9:14pm EST, passed the challenge, and saved:

- each HTML page with "View Frame Source", then "Save As, Webpage, HTML Only". The DES manual
  shows each page inside a frameset; a plain save of the outer page stores the frameset shell
  ("CNAP Manual"), which was discarded and not used;
- the bulletin PDF as the file itself.

The saved HTML is the raw WebWorks source: it starts with `<!DOCTYPE html >`, keeps the
`ww_skin_page_body` body with `style="visibility: hidden;"` (removed by script in a rendered
page), carries the response's Cloudflare beacon and challenge-platform trailer, and has no
"saved from url" mark, no view-source line table and no `_files/` folder. Against the 2026-10-04
check of the same pages, only WebWorks element ids, anchor ids, the Cloudflare trailer and the
content changes listed below differ.

Each manifest entry's `local_path` names the retained copy under the scope's
`sources/.../official-documents/`. A provenance sidecar per file is in the scope's
`sources/.../provenance/<file>.json` (`url`, `sha256`, `fetched_at` = file modification time in
UTC, `fetch_method` "person, browser save", `http` null because a saved file records no status),
the layout of `us-az/manual/2026-07-17-faa5-recovery` (#383).

| File | Bytes | sha256 |
| --- | ---: | --- |
| `az-des-faa6-self-employment-deduction-current.html` | 6805 | `0e97cdb68309e1bd1a4a14ed8c1f890ac5ca4ba580768d051e126ec5727e86c9` |
| `az-des-faa6-na-200-percent-fpl-standard.html` | 17745 | `90ef005457c1e4c654b05ad094b163193ddc02ee44c6cfc996c6da273bc7e203` |
| `az-des-faa6-na-gross-monthly-income-standard.html` | 29495 | `a19acc28a906e07af784489b52ef0dd953fc9bd705994d9ad4708330408bec91` |
| `az-des-faa6-na-net-monthly-income-standard.html` | 28776 | `cb24da10503e1b4207e9beee3e828a5226330e61d489c57e4ffa3218275abe16` |
| `az-des-faa6-na-elderly-disability-standard.html` | 29116 | `9c360ac8cd2fba6bd3d99533b1176e769601d9615838f6f468b89c1dac9dfc06` |
| `az-des-faa6-maximum-na-resource-limit.html` | 11657 | `5d32c00656e0fa7c0ec5801b9328f64de868c3d7f192252ed2173ad58dac9e1e` |
| `az-des-faa4-income-eligibility-requirements.html` | 57893 | `c6ae43684e1c02ad9de4b715927567dba414414b0005799d0877222ef148595f` |
| `az-des-faa4-na-resources.html` | 9306 | `ad0463d2541c8c2e4bbba139ae107a9db93cfe3221a012e62028e6f9b5af8f44` |
| `az-des-faa3-na-qualified-noncitizens.html` | 49164 | `c6db40473e25ff3672311d10766b096f49a922969de04a1976185737abcfb690` |
| `az-des-faa3-arizona-residency.html` | 57826 | `cca5e716c18c5876baf9cac2c2fe45eede31bc93a612474eaa8db04609d20696` |
| `az-des-faa3-residents-of-institutions-for-na.html` | 91609 | `7b4770ecfa3bc0b515f4823c317f2c6b9476a99c1d129c2ba93ac858a1a6e6c5` |
| `az-des-2026-abawd-geographic-waiver-bulletin.pdf` | 779827 | `c4b28a9463462865b56657f32bd617e56cbd498b9c4bade27dd098e3c0247f49` |
| `az-des-faa6-utility-allowance-current-amount-ffy-2027.html` | 10645 | `39442b86875ffd694c28e21a6efa87c10a9295b4cf75a37b25b8867944c557c4` |

## Content changes since the 2026-10-04 check

- `faa3/arizona-residency`: last revised 11/09/2026 (was 09/28/2026); block-15 adds the VR
  denial/closure reason-code sentence. `expression_date` is 2026-11-09.
- `faa3/na-qualified-noncitizens`: the "determine whether the noncitizen is a qualified
  noncitizen" steps now extract in block-5, not block-8 (same text; last revised 02/17/2026).
- No other text change. The FAA6 tables already carried the 10/01/2026 sections.

## Dated values in the rows

- Gross 130% FPL, effective 10/01/2026: $1,729 (1) ... $6,037 (8), +$616.
- Net 100% FPL, effective 10/01/2026: $1,330 (1) ... $4,644 (8), +$474.
- Elderly/disability 165%, effective 10/01/2026: $2,195 (1) ... $7,662 (8), +$781.
- 200% FPL, ECE and simplified-reporting use effective 03/01/2026; 10/01/2026 table $2,660 (1)
  ... $9,288 (8), +$948.
- Resource limit, effective 10/01/2026: $3,000; $4,750 with an elderly or disabled member
  (was $4,500 from 10/01/2024).
- Self-employment standard deduction 55% (change index date 06/29/2026).
- Utility allowances, effective 10/01/2026: SUA $335 (1-3) / $454 (4+); LUA $154 / $208;
  TUA $46 (10/01/2025: $323 / $438, $149 / $201, $44).

## Results

Coverage is complete for all three scopes. Content findings: two `navigation_body` rows,
`us-az/manual/des/faa3/arizona-residency/block-2` (the page's "Quick Access Menu") and
`us-az/manual/des/faa3/na-qualified-noncitizens/block-12` ("Noncitizen Job Aid"). They are
recorded in `manifests/release-content-baseline.json` after locking.

## Commands

```bash
uv run axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-11-24-az-des-snap-screener-pages --manifest manifests/us-az-des-snap-screener-pages-manual.yaml --source-as-of 2026-11-24
uv run axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-11-24-az-des-snap-screener-pages --manifest manifests/us-az-des-snap-screener-pages-policy.yaml --source-as-of 2026-11-24
uv run axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-11-24-az-des-faa6-utility-allowance-ffy-2027 --manifest manifests/us-az-des-faa6-utility-allowance-ffy-2027.yaml --source-as-of 2026-11-24
```

The provenance sidecars were placed in each scope's `provenance/` folder after extraction, after
checking that each sidecar's sha256 equals the extracted file. Signing, locking, upload and the
release selector follow in later commits.
