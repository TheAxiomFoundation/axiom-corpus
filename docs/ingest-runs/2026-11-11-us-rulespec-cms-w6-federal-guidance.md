# us-rulespec-2026-11-11-cms-w6-federal-guidance: release selector

Date: 2026-11-11. `scripts/repro/us_rulespec_2026_11_11_cms_w6_federal_guidance.py` builds the
selector `manifests/releases/us-rulespec-2026-11-11-cms-w6-federal-guidance.json`, and
`tests/test_us_rulespec_2026_11_11_cms_w6_federal_guidance.py` checks it.

## What it selects

This selector takes the newest cut of rulespec-us's corpus pin line,
`us-rulespec-2026-10-27-ks-liheap` (283 scopes), and adds one signed scope,
`us/guidance/2026-10-06-w6-federal-cms-guidance` (`docs/ingest-runs/2026-10-06-w6-federal.md`, #786;
source manifest `manifests/us-cms-w6-federal-guidance.yaml`). It keeps every scope of the base and the
line's quality profile, `complete-expression-dates-v1`, so it selects 284. It ingests nothing.

rulespec-us `main` pins `us-rulespec-2026-10-29-ecfr-section-text` (276 scopes; `.axiom/toolchain.toml`,
last changed in `375793cd`, content sha `063457c6…`). This selector holds all 276 scopes of that pin,
the seven Kansas LIHEAP scopes that `us-rulespec-2026-10-27-ks-liheap` added to it (#938, merged
2026-11-10) and the CMS scope.

## Why

The encoder reads source text through rulespec-us's pin. The pin does not select the CMS scope, so
the encoder cannot read the CMCS Informational Bulletin of 2025-12-08, CMS's guidance on the Medicaid
community engagement requirements of 42 U.S.C. 1396a(xx). The scope is on the union lineage since
`us-rulespec-2026-10-07-w6-bundle-gaps-union`; the pin line never selected it.

## Why the base is not the pin

The request for this cut named the pin as the base. #938 merged the day before, and its selector names
the pin as its predecessor. On a scratch cut from the pin,
`tests/test_selector_lineage_repository.py` reports an unrecorded fork: "2 selectors name
us-rulespec-2026-10-29-ecfr-section-text as their predecessor (us-rulespec-2026-10-27-ks-liheap,
us-rulespec-2026-11-11-cms-w6-federal-guidance)". The check's first remedy is to cut from the newest
selector of the line, and this cut does that. A re-pin of rulespec-us to this selector therefore also
brings the seven Kansas LIHEAP scopes; it drops nothing the pin holds.

## The added scope

| | |
| --- | --- |
| Provision rows | 352, in 26 documents |
| Bulletin of 2025-12-08 | 14 rows at `us/guidance/cms/cib/2025-12-08`: one document row and 13 page blocks, 34,617 body characters, source id `cms-cib-2025-12-08`, `expression_date` 2025-12-08 |
| Other documents | four more CMCS bulletins, five State Health Official and State Medicaid Director letters, the MAGI household training deck, a MACPro implementation guide, and 14 CMS, Medicaid.gov, Medicare.gov and HealthCare.gov pages and fact sheets |
| Citation paths | all under `us/guidance/cms/`; none is in any of the base's 283 scopes |
| Content findings | 10 `navigation_body` findings, all recorded in `manifests/release-content-baseline.json` when the scope was locked; none is in the bulletin |

## Checks

- The reproducer matches the committed selector byte for byte.
- The selector equals the base plus the one scope, stays sorted and holds every scope of the pin. The
  test pins the addition as literals, so a change to the reproducer's constants cannot also change
  what the test checks.
- A lock file exists for the added scope, and the withdrawn-scope ledger does not list it. The
  selector picks up no withdrawn scope the base does not already select.
- It keeps the line's three withdrawn scopes, `us-me`, `us-mi` and `us-mn`
  `statute/2026-07-13-recovery`. Allowances do not carry forward, so `manifests/withdrawn-scopes.yaml`
  records an exception for this selector on each and pins them to its digest (`811d8842…`).
  rulespec-us#1365, which was to re-point the modules citing them, is closed without a merge (checked
  2026-11-11); the first cut in the line after that re-pointing lands drops them.
- The lineage tests pass with the selector in place; its description names the base first.
- `scripts/publish_corpus.py --dry-run` passes and plans 284 scopes, 16,104 artifacts and 117,101
  provision rows, with no external writes. The base alone has 116,749 rows.
- A Hypothesis property checks the addition over arbitrary bases, including bases where other pairs
  reuse the added scope's version string. The reproducer refuses a base that already holds the scope
  or repeats a scope.

`axiom-corpus-ingest validate-release --strict-warnings`, under the line's quality profile:

| Selection | Scopes | Errors | Warnings | Notices | `ok` |
| --- | ---: | ---: | ---: | ---: | --- |
| This selector | 284 | 0 | 541 | 36 | false |
| The base, `us-rulespec-2026-10-27-ks-liheap` | 283 | 0 | 541 | 35 | false |
| The pin, `us-rulespec-2026-10-29-ecfr-section-text` | 276 | 0 | 541 | 35 | false |
| The added scope alone | 1 | 0 | 0 | 1 | true |

Strict warnings fail the three whole selectors on the same 541 `missing_parent_id` warnings, all in
`us-ca/regulation/2026-07-13-recovery`; the three reports list them identically. The added scope adds
no error and no warning. It adds one notice, `baselined_content_findings`, for its 10 recorded
findings. Without strict warnings, which is how the publish gate runs, this selector validates `ok`.

## Coordination with #980

Draft #980 cuts `us-rulespec-2026-11-05-mt-arm-37-78-420-successor` from the pin, and it predates
#938's merge. rulespec-us pins one release, and the lineage check rejects two unrecorded successors of
one selector, so the cuts go one after another:

- If this selector merges first, #980 sets its `BASE_RELEASE` to this selector, reruns its reproducer
  (one Montana scope swapped, so it selects 284), updates its expected count and re-records its
  digest and the ME/MI/MN exceptions.
- If #980 is re-cut on `us-rulespec-2026-10-27-ks-liheap` and merges first, this cut sets its
  `BASE_RELEASE` to #980's selector and reruns the reproducer. The change is the same one scope added;
  the count stays 284, and the digest and the three exceptions are re-recorded.

## After merge

1. Dispatch `publish.yml` with this release, then `mirror-release.yml`. Merging a selector does not
   publish it. **Publish only. Do not activate it.** rulespec-us pins this release; see
   `docs/named-release-publication.md`.
2. Re-pin rulespec-us to this release with the published `content_sha256`, and move its
   `axiom_corpus_ref` to a main commit at or after the release's signed provenance.
