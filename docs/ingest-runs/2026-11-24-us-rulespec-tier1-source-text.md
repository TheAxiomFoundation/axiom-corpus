# us-rulespec-2026-11-24-tier1-source-text: release selector

Date: 2026-11-24. `scripts/repro/us_rulespec_2026_11_24_tier1_source_text.py` builds the selector
`manifests/releases/us-rulespec-2026-11-24-tier1-source-text.json`, and
`tests/test_us_rulespec_2026_11_24_tier1_source_text.py` checks it. It ingests nothing.

## Why

The encoder reads source text through rulespec-us's corpus pin,
`us-rulespec-2026-10-29-ecfr-section-text` (276 scopes). A count on 2026-11-24 found 386 Tier 1
documents of the SNAP, Medicaid, CHIP and UI program bundles (`manifests/program-bundles/`, at
`ebcce4552`) with no text-bearing row at or under their citation path in that release.

Checked against every locked `us` and `us-*` provision file, the signed ingest manifests and the
release selectors:

| Group | Documents | Meaning |
| --- | ---: | --- |
| Ingested and signed, not selected by the pin | 364 | All are in scopes that `us-rulespec-2026-10-13-w7-bundle-gaps-union` selects; the pin line's newest cut serves 17 of them |
| Ingested and locked, no signed ingest manifest | 1 | `us/rulemaking/federal-register/2026-06-03/2026-11094`, in `us/rulemaking/2026-06-03-cms-2454-ifc-types-rule-term-cms-2454-ifc-limit-1` |
| Bundle names a container or a URL; the text is under other paths | 5 | 42 CFR part 435 subpart D, Alabama title 25 chapter 4, California WIC nodes 16.7.2 and 16.7.3, D.C. Code 4-261.04 |
| Never ingested (the bundle holds only a URL) | 16 | 1 federal, 15 state |

The union line holds the text; the pin line never selected it. This selector adds it to the pin line.

## What it selects

The base is the newest cut of the pin line on `main`, `us-rulespec-2026-11-11-cms-w6-federal-guidance`
(284 scopes). The selector keeps 282 of its scopes, adds 149 signed scopes and selects 431.

- **Added (149).** Every scope the union selector selects that carries the text of a group-one
  document the base does not serve: 21 federal scopes (9 statute, 6 regulation, 3 guidance, 2 form,
  1 policy) and 128 state scopes in 42 jurisdictions. Together with the base's CMS guidance scope
  they serve all 364 documents (17 through the base, 347 through the additions). The federal
  statute scopes carry the 80 missing U.S. Code sections: 52 in title 26, 22 in title 42, 2 each
  in titles 8 and 25, 1 each in titles 29 and 38.
- **Replaced (2).** Two additions are consolidated successors of a base scope and hold every
  citation path of it with the same body text, so the base scope is dropped:
  `us-co/statute/2026-07-19-rulespec-us-co-title-39-consolidated` (1,137 paths; successor
  `…-r2026-10-07-w6-title-10-consolidated`, 1,449) and
  `us-wa/regulation/2026-06-25-388-450-r2026-07-15-self-contained` (45 paths; successor
  `…-r2026-10-07-388-400-424-470-w6-110-15-182-consolidated`, 238). The union selector made the same
  swaps.
- No other citation path of an added scope is in a kept scope or in another added scope.
- It keeps the line's three withdrawn scopes, `us-me`, `us-mi` and `us-mn`
  `statute/2026-07-13-recovery`. `manifests/withdrawn-scopes.yaml` records an exception for this
  selector on each and pins them to its digest (`5911edf2…`). rulespec-us#1365 is closed without a
  merge (checked 2026-11-24).

Not added: the unsigned rulemaking scope (it needs a signed ingest manifest first), and anything for
the 16 documents that were never ingested.

## Checks

- The reproducer matches the committed selector byte for byte; the test pins the additions by count
  and digest and the replacements as literals.
- Every added scope has a lock and a signed ingest manifest, is selected by the union selector and
  is not in the withdrawn-scope ledger.
- Each replacement holds every row of the scope it replaces with identical body text.
- The 80 U.S. Code sections have text in this selector and none in the pin.
- The lineage tests pass; the description names the base first, and every
  `(jurisdiction, document_class)` pair of the pin and the base keeps a version.
- `axiom-corpus-ingest validate-release --ignore-r2-missing`:

| Selection | Scopes | Errors | Warnings | Notices | `ok` |
| --- | ---: | ---: | ---: | ---: | --- |
| This selector | 431 | 0 | 541 | 57 | true |
| The base | 284 | 0 | 541 | 36 | true |

  The 541 warnings are the same `missing_parent_id` warnings in `us-ca/regulation/2026-07-13-recovery`
  that every cut of the line carries. The 21 new notices are recorded content findings and reviewed
  empty nodes of the added scopes.

- `scripts/publish_corpus.py --dry-run` passes and plans 431 scopes, 22,043 artifacts and 179,913
  provision rows, with no external writes. The base alone plans 117,101 rows.

## Coordination

Drafts #996 (`us-rulespec-2026-11-14-cms-smd-26-006`) and #980
(`us-rulespec-2026-11-05-mt-arm-37-78-420-successor`) also cut from this line. The lineage check
rejects two unrecorded successors of one selector, so the cuts go one after another: whichever
merges second sets its `BASE_RELEASE` to the first, reruns its reproducer and re-records its digest
and the ME/MI/MN exceptions.

## After merge

1. Dispatch `publish.yml` with this release, then `mirror-release.yml`. **Publish only. Do not
   activate it.** See `docs/named-release-publication.md`.
2. Re-pin rulespec-us (`.axiom/workflow-toolchain.toml` / `.axiom/toolchain.toml`) to this release
   with the published `content_sha256`, and move `axiom_corpus_ref` to a `main` commit at or after
   the release's signed provenance.
