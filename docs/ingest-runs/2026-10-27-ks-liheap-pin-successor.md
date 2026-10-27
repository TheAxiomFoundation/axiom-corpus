# Kansas LIHEAP pin successor release

Date: 2026-10-27. Selector: `us-rulespec-2026-10-27-ks-liheap`.
Reproducer: `scripts/repro/us_rulespec_2026_10_27_ks_liheap.py`.

## Why a second Kansas selector

[axiom-corpus#926](https://github.com/TheAxiomFoundation/axiom-corpus/pull/926)
added `us-rulespec-2026-10-23-ks-liheap` as a successor of
`us-rulespec-2026-10-22-ca-concurrent-versions`. Before it was published, the
rulespec-us pin line moved on twice, to `us-rulespec-2026-10-25-nyc-ch127-title-52`
and then to `us-rulespec-2026-10-25-mt-separate-filing`, which rulespec-us pins
now. Its one publish attempt (run
[40376163944](https://github.com/TheAxiomFoundation/axiom-corpus/actions/runs/40376163944),
2026-10-26) passed deep validation (275 scopes, 0 errors) and then failed in
R2 staging with a transient `ServiceUnavailable` ("Reduce your rate of
simultaneous reads on the same object"); the same error failed two
mt-separate-filing attempts on 2026-10-25 before a third succeeded.

Publishing the October 23 selector and pinning it would now drop nine scopes
the pin selects (the Montana separate-filing authority and W6 Montana forms and
statute, SSI POMS SI and its remainder, the Title 52 election statutes and the
W6 federal public laws) and move the NYC Administrative Code back from
`2026-09-28-nyc-admin-code` to `2026-06-05-nyc-admin-code`. **Do not publish
`us-rulespec-2026-10-23-ks-liheap`.** This selector replaces it.

## Scope

This selector keeps all 276 scopes of `us-rulespec-2026-10-25-mt-separate-filing`
and adds exactly the seven scopes that #926 added, for 283 scopes. It keeps the
pin's NYC capture, so the only scope of the October 23 selector it does not
select is the older `us-ny/statute/2026-06-05-nyc-admin-code`. No selector,
signed ingest, lock, corpus artifact, citation ceiling or content baseline
changes.

| Added scope | Provision rows | Locked artifacts |
| --- | ---: | ---: |
| `us-ks/manual/2026-10-02-ks-lieap-historical` | 34 | 20 |
| `us-ks/policy/2026-10-02-ks-liheap-plan-fy2025` | 21 | 4 |
| `us-ks/policy/2026-10-02-ks-liheap-matrix-fy2025` | 4 | 4 |
| `us/guidance/2026-10-02-hhs-poverty-2024-2025` | 4 | 5 |
| `us-ks/policy/2026-09-10` | 21 | 4 |
| `us-ks/policy/2026-09-14-liheap-benefit-matrix` | 5 | 4 |
| `us/statute/2026-09-13-liheap-statute-chapter-94-title-42` | 269 | 4 |

The additions hold 358 provision rows and 45 locked artifacts, the same as in
#926. The first four scopes were admitted by
[axiom-corpus#778](https://github.com/TheAxiomFoundation/axiom-corpus/pull/778);
their 33 objects were uploaded and remotely verified on 2026-10-20. The other
three were already signed and locked on main. The release needs no new capture
or upload.

The selector digest is
`c21298ad892a164d2775aef441c30329b4b534f9612d08ac5016603c19362908`. It is not
the published release content hash and must not be used as a RuleSpec content
pin.

## Withdrawal exceptions

The pin keeps the `us-me`, `us-mi` and `us-mn` `statute/2026-07-13-recovery`
scopes under explicit exceptions until
[rulespec-us#1365](https://github.com/TheAxiomFoundation/rulespec-us/pull/1365)
re-points the modules that cite them; #1365 is still open (checked 2026-10-27).
This selector keeps the same three scopes with exceptions bound to its own
digest in `manifests/withdrawn-scopes.yaml` and admits no other withdrawn
scope. The first cut in the line after #1365 lands drops them.

## Validation

- The reproducer regenerates the committed selector byte for byte; the set
  difference against the base is exactly the seven scopes, and all 283 scope
  identities are unique and sorted.
- With every artifact the selector names fetched (16,075 locked files),
  `axiom-corpus-ingest validate-release` passed: 283 scopes, 0 errors, 541
  warnings and 35 notices. The base pin gives the same 541 warnings and 35
  notices, so the additions add none.
- `tests/test_us_rulespec_2026_10_27_ks_liheap.py` checks the delta, the
  superseded selector's coverage, the locks, the withdrawal exceptions, the
  quality profile and two cited paths (the October 2024 KEESM 13360 income
  table and `us/statute/42/8624/b/2/B`). It passes with the release-policy and
  release-manifest tests (188 passed). The repository-wide policy tests need
  the full corpus and run in CI.

## Publication and RuleSpec re-pin

**Publish only; do not activate this release.**

1. Merge this selector after CI passes.
2. Dispatch `publish.yml` on main with release `us-rulespec-2026-10-27-ks-liheap`.
   If R2 staging fails with `ServiceUnavailable`, dispatch it again; do not change
   the selector.
3. Take `release` and `content_sha256` from the successful run's signed release
   object, then dispatch `mirror-release.yml` with that run ID and identity.
4. Re-pin rulespec-us to the published name and content hash as in
   [rulespec-us#1872](https://github.com/TheAxiomFoundation/rulespec-us/pull/1872):
   `.axiom/toolchain.toml`, `.axiom/workflow-toolchain.toml`'s
   `axiom_corpus_ref` (the signed release's `content.git.commit`), and the
   matching expectation in `tests/test_bulk_applied_artifacts.py`.

The Kansas policy questions recorded in the October 23 run note (matrix
adoption, payment supplements, the federal income floor) stay open for the
encoding request in
[rulespec-us#1469](https://github.com/TheAxiomFoundation/rulespec-us/issues/1469).
