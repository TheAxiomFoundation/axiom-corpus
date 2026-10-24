# us-rulespec-2026-10-20-fs-pilot-reg-e-f: release selector

Date: 2026-10-20 to 2026-10-21.
Selector `manifests/releases/us-rulespec-2026-10-20-fs-pilot-reg-e-f.json`,
built by `scripts/repro/us_rulespec_2026_10_20_fs_pilot_reg_e_f.py` and checked by
`tests/test_us_rulespec_2026_10_20_fs_pilot_reg_e_f.py`.

## What it is

The selector starts from rulespec-us's current pin,
`us-rulespec-2026-10-09-az-des-ece-dated` (274 scopes). It adds the two
Regulation E and Regulation F scopes ingested and signed in axiom-corpus#894
(eCFR as of 2026-10-16):

- `us/regulation/2026-10-19-title-12-part-1005`, Regulation E (Electronic Fund
  Transfers);
- `us/regulation/2026-10-19-title-12-part-1006`, Regulation F (Debt Collection).

The financial-services pilot encodes 12 CFR 1005.6, 1005.11 and 1006.14 through
the production signed route, and the encoder reads source text from the signed
release rulespec-us pins. So these scopes have to be in a pinned release first.

**Publish only. Do not activate it.** Like its predecessor, it is a RuleSpec pin
release, not a serving-map activation; see `docs/named-release-publication.md`.

## Withdrawn scopes

The pin selects 16 scopes that `manifests/withdrawn-scopes.yaml` withdraws
(release decisions of 2026-10-03 on axiom-corpus#757 and 2026-10-11 on #760).
The pin itself is grandfathered for them; a new selector is not.

- **13 leave**, and the replacement scopes their entries name come in:
  - `us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated`;
  - `us-ny/statute/2026-09-14-income-tax-chapter`;
  - `us-sc/statute/2026-09-27-sc-act110-with-12-6-520-us-sc-title-12-chapter-6`;
  - `us-ut/statute/2026-09-14-income-tax-chapter-title-59`.

  The others are carried by scopes the selector already holds.
- **3 stay as recorded exceptions** (release decision on axiom-corpus#911): the
  us-me, us-mi and us-mn `statute/2026-07-13-recovery` scopes.
  - **Why:** dropping them would leave 13 cited paths in 14 rulespec-us modules
    unresolved: the ME `36/5111` block, MI subsections of `206.30` and `206.51`,
    and MN `290.06` blocks.
  - **Why not their replacements:** the five 2026-09-14 replacement scopes are
    not selected, because alongside the recovery scopes they would duplicate 12
    citation paths (`duplicate_release_citation`).
  - **When they go:** each exception is pinned to this selector's digest in
    `selector_digests` and stays with this immutable selector. The next cut in
    the line drops the three scopes and selects their replacements.
  - **Ordering for that cut:** rulespec-us#1365 re-points the 14 modules, and
    its MI paths resolve only in the MI replacement scope. So that cut has to be
    published first, and #1365 lands together with the re-pin to it.

The result is 267 scopes, sorted, with the same `quality_profile`.

## Checks

- **`validate-release --ignore-r2-missing`:** ok, 0 errors, 541 warnings (the
  same set as the pin), 33 notices, 267 scopes. With the five replacement scopes
  added back, it reports 12 `duplicate_release_citation` errors.
- **Citation regression against the pin:** the check covered every corpus path
  cited by rulespec-us main's 4,879 atomic modules. 5,409 cited paths resolve
  under the pin, and the same 5,409 under this selector, so 0 are lost.
  - This checks that each path is present, not that its text is unchanged.
  - Under the registry swaps, 53 cited paths move to a different scope, and 21
    of them carry different text, across 31 modules (CO, NY, SC and UT). That is
    the replacement working as intended. The rulespec-us re-pin has to check
    whether those 31 modules need re-verification or re-encoding.
- **Tests:** `tests/test_us_rulespec_2026_10_20_fs_pilot_reg_e_f.py` (10 tests).
  - The reproducer matches the committed selector byte for byte.
  - An independent derivation from the registry gives the same scopes.
  - The exact added and removed sets are pinned.
  - The three exceptions are pinned to this selector's digest.
  - A Hypothesis property checks the selection rule over arbitrary bases and
    registries.
  - Tests cover both input guards, the duplicate base and an addition that is also a replacement.
  - Each of 13 single-rule mutants of `select_scopes` is caught.
- **Release-policy tests:** the withdrawn-scope, exception and digest tests pass.

## After merge

1. Dispatch `publish.yml`, then `mirror-release.yml`.
2. Re-pin rulespec-us's `.axiom/toolchain.toml` to this release's content
   sha256.
