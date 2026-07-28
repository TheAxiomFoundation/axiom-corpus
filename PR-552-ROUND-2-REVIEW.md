VERDICT: REQUEST-CHANGES

# PR #552 round-2 review

Reviewed `ingest/ca-bbce-authority` independently at immutable head
`40e8513e71a66093cfdf2361eae56d36d8d875cb` against base
`10142cb0f07403c2de4599c76bec01e96640fda9`.

Three of the four round-1 blockers are closed: the corpus reproduces
byte-identically under both required PyMuPDF versions, the federal/state MCE
map is exhaustive against current retained authority, and ACL 14-63 is the
preferred zero-benefit authority. The fourth blocker remains in the immutable
head: tracked final-state documentation still says the repaired manifests are
stale and must be re-signed, even though the final two PR commits replaced and
validly signed them.

## Blocking finding: final-state signing claims are still stale

The following immutable-head statements are false:

- `docs/ingest-runs/2026-07-28-ca-calfresh-bbce-authority.md:116-121` says both
  signatures describe pre-repair artifacts, were intentionally left untouched,
  and must be replaced and re-signed.
- `40e8513e:PROGRESS.md:13-17`, `:64-66`, `:99-103`, and `:111-115` makes the
  same stale claims. It also says the signing guard was unavailable and leaves
  re-signing as the next task.

The final tree proves the opposite:

- The guidance manifest has a valid Ed25519 signature, covers nine applied
  files at 47/47, and attests content commit
  `256634f618f99cbf431b1e37b933aff5682aa50d`.
- The combined WIC §§18901.3/18901.5 statute manifest has a valid Ed25519
  signature, covers five applied files at 2/2, and attests
  `b1d42e7ef7be8ed903d36b63bcc4bd17aa1e39f7`.
- Both attested commits are ancestors of the reviewed head. Every applied hash
  matches, and `guard-ingested` passes all 14 protected changes with
  `issues: []`.
- Commit `b1d42e7e` re-signed guidance after the repair; commit `40e8513e`
  added the signed combined statute manifest and removed the superseded
  one-section manifest.

This directly repeats a named round-1 blocker and can mislead a release
operator into disregarding valid attestations or performing unnecessary
signing work. Correct both tracked documents to describe the actual signed,
guard-validated final state. No corpus regeneration or re-signing is needed
for this documentation-only repair unless an applied artifact changes.

## Round-1 blocker disposition

| Round-1 blocker | Round-2 result |
| --- | --- |
| PyMuPDF version determinism | **PASS** — real 1.26.7 and 1.28.0 runs emitted the same 14 committed artifacts |
| Non-exhaustive MCE exclusions | **PASS** — all seven paragraph-(vii) household gates and all five separate paragraph-(ix) member exclusions are covered |
| ACL 14-63 preference | **PASS** — retained and marked primary for zero-benefit denial/discontinuance; ACL 14-56 is context |
| Stale signing claims | **FAIL** — the run document and immutable-head ledger still describe the final valid manifests as stale |

## Per-parameter authority verification

The audit used the retained provision text, not just manifest metadata or
tests. Each excerpt below is present verbatim in the cited retained row.

| #1098 parameter | Retained controlling authority and decisive excerpt | Result |
| --- | --- | --- |
| California categorical-eligibility mandate | `us-ca/statute/wic/18901.5`: “The department shall establish a program of categorical eligibility for CalFresh” | **PASS** |
| Inclusive 200% FPL gross screen | `us-ca/guidance/cdss/acl-2014-14-56/page-1`: “gross income at or below 200 percent”; ACL 14-56E page 2 says “at or less than 200 percent”; ACL 15-42 page 2 again says “at or below” | **PASS** — encode `<= 200%`, not `< 200%` |
| PUB 275 trigger | `.../acl-2015-15-42/page-2`: households “must be conferred MCE status” when issued or given online access to PUB 275 and otherwise qualified; `.../acl-2014-14-56/page-3`: receipt “in and of itself, does not confer MCE status” | **PASS** |
| Asset/resource test waived | `.../acl-2014-14-56/page-3`: “receipt of the PUB 275 exempts all resources in the determination of eligibility”; retained 7 CFR 273.2(j)(2)(xi)(A) excludes the ordinary §273.8 resource rules | **PASS** |
| Gross/net eligibility tests waived | Retained 7 CFR 273.2(j)(2)(xi)(B)-(E) excludes the ordinary §273.9(a), §273.10(a)(1)(i), (b), and eligibility-use of (c) provisions; `.../acl-2015-15-42/page-4` expressly gives the applicable allotment even when net income exceeds the ordinary maximum | **PASS** — net income still determines benefit amount; it is not an eligibility ceiling for MCE |
| MCE exclusion gates | Retained `us/regulation/7/273/2` paragraph (j)(2)(vii), supported where needed by `us/regulation/7/273/11` and WIC §18901.3 | **PASS** — exhaustive map detailed below |
| Prior drug-felony result in California | WIC §18901.3: “California opts out” and the described person “shall be eligible”; `.../acl-2014-14-100/page-2`: “no person will be denied aid because they have a prior felony drug conviction” | **PASS** — conviction alone does not trigger the gate; independent fleeing/probation/parole rules still apply |
| Zero-benefit treatment | Preferred `.../acl-2014-14-63/page-2`: “California has opted to deny zero benefit cases,” followed by application denial, discontinuance, and recertification-denial instructions; page 1 preserves one/two-person minimum-allotment treatment | **PASS** |
| Elderly/disabled non-MCE route | `.../acl-2013-13-32/page-1`: “E/D households are not subject to a gross income test for actual program eligibility” | **PASS** — above the MCE screen, use the ordinary E/D route with current figures, rather than treating old ACL dollar examples as current |

### Exhaustive federal/state MCE gate audit

Current 7 CFR 273.2(j)(2)(vii) contains exactly seven household gates. The
retained map has the correct clause count `A2/B1/C1/D3`:

| Gate | Federal retained text/map | California result |
| --- | --- | --- |
| Intentional program violation, §273.16 | Clause A: member “disqualified for an intentional Program violation” | Federal household gate controls |
| Monthly-reporting failure, §273.21 | Clause A: “failure to comply with monthly reporting requirements” | Federal household gate controls |
| Entire-household workfare disqualification, §273.22 | Clause B: entire household disqualified because a member “failed to comply with workfare” | Federal household gate controls |
| Head-of-household work disqualification, §273.7 | Clause C: head “disqualified for failure to comply with the work requirements” | Federal household gate controls |
| Drug-felony member ineligibility, §273.11(m) | Clause D plus the retained federal legislative-opt-out rule | WIC §18901.3 opts California out; conviction alone does not trigger this gate |
| Fleeing felon or probation/parole violator, §273.11(n) | Clause D plus retained §273.11(n) member rule | Federal gate applies universally; WIC §18901.3 confirms it for the drug-felony cohort and does not narrow the federal gate |
| Certain serious crimes plus sentence noncompliance, §273.11(s) | Clause D plus retained §273.11(s) predicate | Federal household gate controls; no state overlay |

No paragraph-(vii) gate is missing or mapped to superseded authority. The map
also correctly keeps paragraph (j)(2)(ix)'s five person-level exclusions
separate rather than silently treating them as household gates:

1. ineligible alien under §273.4;
2. ineligible student under §273.5;
3. SSI recipient in a cash-out state under §273.20;
4. institutionalization in a nonexempt facility under §273.1(e); and
5. individual work-requirement noncompliance under §273.7.

California ended SSI cash-out in 2019, so the third person-level exclusion is
dormant in California and should not be encoded as a generic current
California SSI exclusion.

The retained federal scope is version
`2026-07-15-title-7-part-273`, `source_as_of: 2026-07-09`. Independent
comparison with the [current official eCFR §273.2](https://www.ecfr.gov/current/title-7/subtitle-B/chapter-II/subchapter-C/part-273/subpart-A/section-273.2)
and [§273.11](https://www.ecfr.gov/current/title-7/subtitle-B/chapter-II/subchapter-C/part-273/subpart-D/section-273.11)
found the same controlling text; Title 7 was current through July 24, 2026 and
last amended July 9, 2026. Current
[WIC §18901.3](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=WIC&sectionNum=18901.3)
and [§18901.5](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=WIC&sectionNum=18901.5)
match the retained sections.

No CDSS index marks ACL 14-56, 14-56E, 14-63, 14-100, or 15-42 superseded in
a way material to these parameters; the indexes explicitly mark other ACLs
when superseded. Current CDSS/FNS material continues to corroborate
California's 200% threshold and no asset limit. Historical benefit tables and
resource-dollar examples in the ACLs are not current parameters; downstream
encoding should use the retained FY2026 annual figures. Likewise, downstream
encoding of §273.11(n)/(s) must use the full retained predicates, not the map's
short labels.

## PyMuPDF 1.26.7 and 1.28.0 reproduction

The committed portable command is identical in the script constant, both
signed manifests, and the run document:

```bash
uv run --extra dev python scripts/repro/us_ca_calfresh_bbce_authority.py --base data/corpus
```

Independent detached worktrees at exact head ran that command with real:

- PyMuPDF 1.26.7 / MuPDF 1.26.12 / Python 3.14; and
- PyMuPDF 1.28.0 / MuPDF 1.29.0 / Python 3.14.

Both runs reported six documents/41 PDF blocks/47 guidance rows, two
sections/two statute rows, and seven MCE gates. Both produced the following
generated hashes:

| Generated artifact | SHA-256 under both engines |
| --- | --- |
| Guidance coverage | `c0edbfcbf16dd12954dd2ea79b71a4cdd25cb5a639be0a95c810b034d74ab386` |
| Statute coverage | `a8950fdd0fa8752bef6ad381733e557785e4e41d93d3d62a561ea96633459b81` |
| Guidance inventory | `5defe07565a11a8ac00874672bd85fe75406ace59a6c670ba7498d19e3e83c14` |
| Statute inventory | `74ade1657a6711d8d1d905ebcc77b714fda11f8dc3a224b701f877b6bbb3bd06` |
| Guidance provisions | `41f7997a9704cfa05b22a4e6873e2a6721e2e1d3f6822ac7d41ef72f4769675d` |
| Statute provisions | `b4ab85f9d45b56003fb6433d2799c5b4c33b473886b58519c54bd52380d28060` |

There was zero tracked corpus drift under either engine. Under each version,
the exact replay test passed, all seven PR authority/repro tests passed, and
all nine replacement-focused tests passed.

The raw extractor difference is confined to three accessibility strings:
one on ACL 14-56 page 1 and two on ACL 13-32 page 1. Only those two source
entries opt into exact replacements. After replacement, cooked per-source
text hashes match across versions for all six PDFs. The hook is exercised for
plain, single-block, styled/segmented, and forced/fallback OCR paths and is a
no-op for manifests without replacements. GitNexus rated the shared
replacement chain MEDIUM because it has six direct callers, but found no
affected execution flow; the focused tests cover those callers.

The script also accepts a local source directory using either flat original
filenames or retained canonical paths and verifies source hashes before use.

## Source authenticity and byte-faithfulness

Shell `curl` redownloads from both CDSS and LegInfo failed with
`Could not resolve host`, so I could not independently hash a second network
download. This sandbox limitation is material and is not hidden.

Within that limitation:

- Every retained file is byte-identical to the supplied local source cache and
  matches the size and SHA-256 recorded in the untracked main-lane worker
  report.
- Read-only browser retrieval reached the live
  [official ACL 14-63 PDF](https://www.cdss.ca.gov/lettersnotices/entres/getinfo/acl/2014/14-63.pdf)
  and official LegInfo pages. ACL 14-63 is a two-page CDSS letter dated
  September 16, 2014 and contains the retained zero-benefit rules; the live WIC
  sections match the retained text.
- Local `pdfinfo`/`pdftotext` and visual checks confirm CDSS identity, ACL
  number/date, letterhead, and actual PDF pagination for all six letters.

| Source | Bytes/pages | Retained/report SHA-256 |
| --- | ---: | --- |
| WIC §18901.3 HTML | 163,929 | `793afbd116aa7664fde4137f55d34ad659e80c10f37849d59bb4ea07b43fffdc` |
| WIC §18901.5 HTML | 164,166 | `97cae778729e0dd5d3c15797934690467876a14057e7d856d1500326e72d004e` |
| ACL 14-56 | 278,260 / 7 | `8677c1d3e5c2ec9ecef23206b24061999817a46fa469ccb68a000b8f2f570d5e` |
| ACL 14-56E | 189,729 / 4 | `67e33a2613009abaef3759ebc2a583417fb852120f009848e3b1a1e3c3c11cbd` |
| ACL 14-63 | 120,344 / 2 | `4392ab0dedfcfb6f247bb7d3d913e90ff2a97a673ea01efac02ec9f3d6ee2841` |
| ACL 15-42 | 249,307 / 13 | `6aab92e4e2a2c9e0f234eba2b1c0eeb68d4d9d5dbc7ba752465a2358d9f2db33` |
| ACL 14-100 | 209,290 / 12 | `c981081163b361eea20aeeccec7934509dc5bf23d8d66c8035895586db60131e` |
| ACL 13-32 | 204,909 / 3 | `1a0bbfc2d6d69fd378aff3f1285d03d20b8b6abf2ff64c749b9897fd1cc55506` |

## Normalization and scope spot-check

The repaired head intentionally contains 49 rows, not the original round-1
45: all 45 prior rows retain semantic projection hash
`6a79caf1945521a9d13aaf58248cd453a1d938b545d309d6b3f4b570fed68edd`,
and ACL 14-63 contributes three rows while WIC §18901.3 contributes one.

- Guidance has 47 rows: six level-1 document roots and 41 contiguous level-2
  physical-page rows. Counts by letter are `8/5/3/14/13/4` for
  14-56/14-56E/14-63/15-42/14-100/13-32.
- Every page row has the expected sequential path and document-root parent,
  and all 41 bodies match the corresponding physical page.
- Statute has exactly two level-2 section rows at
  `us-ca/statute/wic/18901.3` and `/18901.5`, with no unresolved parent
  fields; the official WIC hierarchy is preserved in metadata.
- This matches existing California ACL/ACIN document-root-plus-page
  normalization and bounded California statute-section granularity.

## Manifests, hygiene, and checks

| Check | Result |
| --- | --- |
| Ed25519/applied hashes/ancestors | **PASS** — two valid signatures, 14 matching protected files, both attestations are head ancestors |
| Recorded repro command | **PASS** — exact portable invocation in script, run doc, and both manifests |
| Guidance/statute coverage | **PASS** — 47/47 and 2/2 |
| Tracked-scope verification | **PASS** — 9 guidance and 5 statute references |
| Strict named-release validation | **PASS** — 2 scopes, 0 errors, 0 warnings |
| Citation census | **PASS** — 143,779 records, 125,251 unique paths, no grammar/identity/ratchet issue |
| Focused tests | **PASS** — 109 passed under the local 1.26.7 environment; required subsets also pass under 1.28.0 |
| Ruff | **PASS** |
| Towncrier/changelog | **PASS** — check and draft pass; both fragments present |
| `git diff --check` | **PASS** |
| Full pytest, head | `1 failed, 4,134 passed, 69 skipped, 208 deselected` |
| Full pytest, clean base | `1 failed, 4,118 passed, 69 skipped, 208 deselected` |
| Broad local MyPy, head/base | Same 180 errors in the same 26 untouched legacy files under local MyPy 1.19.0; no PR delta |
| Exact-head GitHub CI | **PASS** — ingest guard, changelog, Ruff, MyPy, tests, citation and release jobs; fresh job resolved PyMuPDF 1.28.0 |

The sole full-pytest failure on both local trees is the pre-existing
`TestPostgresStorageSubsectionConversion::test_dict_to_subsection` MagicMock
failure. Exact-head adds 16 passes under the paired environment. The prescribed
broad local MyPy check is not clean, but its result is byte-for-byte/count-for-
count the clean-base result; exact-head CI's fresh MyPy environment passes.

No tracked session report or source cache appears in
`origin/main..40e8513e`; the target's tracked `PROGRESS.md` is expected.
The worker report and supplied source cache remain untracked. No PR branch,
remote, GitHub, R2, Supabase, release, or serving-state write was performed.

## Required repair

Update only the stale final-state text in the run document and PR-head
`PROGRESS.md` so it says the two final manifests are signed, their applied
hashes match, their attested commits are ancestors, and the guard passes. Then
rerun the documentation/hygiene checks. The authority, PyMuPDF, ACL 14-63,
normalization, and manifest cryptography dimensions need no further content
repair based on this review.
