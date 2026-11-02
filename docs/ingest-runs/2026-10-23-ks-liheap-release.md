# Kansas LIHEAP corpus pin release

Date: 2026-10-23. Selector: `us-rulespec-2026-10-23-ks-liheap`.

## Scope and purpose

This selector preserves all 268 scopes of
`us-rulespec-2026-10-22-ca-concurrent-versions`, the RuleSpec US pin at
`829d85e9c`, and adds exactly the following seven scopes. The result is 275
scopes. No existing selector, signed ingest, lock, or corpus artifact changes.

| Added scope | Provision rows | Locked artifacts | Purpose |
| --- | ---: | ---: | --- |
| `us-ks/manual/2026-10-02-ks-lieap-historical` | 34 | 20 | Dated KEESM pages, including the income and exemption rules cited in Pavel's October 23 comment on rulespec-us#1469. |
| `us-ks/policy/2026-10-02-ks-liheap-plan-fy2025` | 21 | 4 | FY2025 Kansas plan. |
| `us-ks/policy/2026-10-02-ks-liheap-matrix-fy2025` | 4 | 4 | FY2025 Kansas payment matrix. |
| `us/guidance/2026-10-02-hhs-poverty-2024-2025` | 4 | 5 | The 2024 and 2025 HHS poverty notices, reusable beyond Kansas. |
| `us-ks/policy/2026-09-10` | 21 | 4 | Existing FY2026 Kansas plan. |
| `us-ks/policy/2026-09-14-liheap-benefit-matrix` | 5 | 4 | Existing FY2026 Kansas payment matrix. |
| `us/statute/2026-09-13-liheap-statute-chapter-94-title-42` | 269 | 4 | Shared federal LIHEAP statute, including `us/statute/42/8624/b/2/B`. |

These additions contain 358 provision rows and 45 locked artifacts. The first
four scopes were admitted by [axiom-corpus#778](https://github.com/TheAxiomFoundation/axiom-corpus/pull/778),
merged at `64a386d9da736521cd0d0ed80e48eef56fbd32b9`. Their 33 objects were
uploaded and remotely verified before merge. The remaining three scopes are
already signed and locked on corpus main. This release adds no new source
capture or object-upload requirement.

The selector digest is
`0a7bbd78608da08d9a1b3572719d2190f843bd3780d1b59c29b5989d82740793`.
It is **not** the published release content hash and must not be used as a
RuleSpec content pin.

## Existing withdrawal exceptions

The current pin retains `us-me`, `us-mi`, and `us-mn`
`statute/2026-07-13-recovery` scopes under explicit exceptions. This successor
retains those same three scopes, with exceptions bound to its own selector
digest in `manifests/withdrawn-scopes.yaml`. It adds no other withdrawn scope.

[rulespec-us#1365](https://github.com/TheAxiomFoundation/rulespec-us/pull/1365)
remains open as checked on October 23. Dropping these scopes before that
citation migration would break existing modules. As in the current pin's
release decision, the first successor after that migration lands must remove
them and select their replacements. This is a deliberate continuation of the
existing pin's compatibility exception, not a claim that the withdrawn source
quality issues are resolved.

## Validation

The exact set difference against the base selector is seven scopes; inherited
scope entries are unchanged and all 275 scope identities are unique and sorted.
All 45 added artifacts matched their committed locks. Deep validation of the
seven additions together passed with zero errors and zero warnings, including
the inherited quality profile and current content policy.

Ruff, mypy (105 files), and 17 repository release-policy metadata tests pass
locally. The metadata tests deliberately use the documented partial-tree mode;
the corpus-reading tests are left to full CI. Full local validation cannot read 36 artifacts in
five inherited scopes that are absent from the retained local cache; these are
existing 12 CFR, Arizona, California and South Carolina inputs, not missing
Kansas artifacts. The complete test suite also requires the corpus outside
this release. CI's
`Validate named release selectors` job fetches and deeply validates all selected
artifact bytes, including citation uniqueness and the content baseline. The
publisher independently repeats deep validation, exact R2 readback, and staged
database evidence before signing.

No extraction logic, citation ceiling, or content-quality baseline is changed.
The inherited `complete-expression-dates-v1` quality profile is retained.

## Publication and RuleSpec handoff

**Publish and mirror only; do not activate this release.**

1. Review and merge this selector after CI passes.
2. Explicitly dispatch `publish.yml` on corpus `main` with release
   `us-rulespec-2026-10-23-ks-liheap`. GitHub's protected publication environment
   supplies signing, R2, and Supabase credentials. The contributor does not need
   copies of those secrets locally.
3. Obtain the actual `release` and `content_sha256` from the successfully
   published signed release object. Dispatch `mirror-release.yml` with that
   publication run ID and exact identity. Verify the public signed object.
4. Update RuleSpec `.axiom/toolchain.toml` to that release name and verified
   content hash; preserve its existing validation-waiver hash. Update
   `.axiom/workflow-toolchain.toml`'s `axiom_corpus_ref` and the corresponding
   expectation in `tests/test_bulk_applied_artifacts.py` to the actual corpus
   commit recorded in the signed release's `content.git.commit` (which includes
   this selector and may be later than its merge commit). Follow the repin workflow in
   [rulespec-us#1872](https://github.com/TheAxiomFoundation/rulespec-us/pull/1872).
5. Run the RuleSpec bulk-artifact and repository-layout tests, then full PR CI.
   Encoding against this pin starts after the real signed identity is available
   and the repin is accepted. Never reuse the old release's content hash for
   the new name or substitute the selector digest.

Source admission and publication do not settle the Kansas issue's remaining
interpretations (including matrix adoption and payment supplements), nor do
they encode the federal floor. Preserve those questions and Pavel's military
retirement/SBP test additions in the encoding request. This selector does not
claim source closure for the other states' LIHEAP issues.
