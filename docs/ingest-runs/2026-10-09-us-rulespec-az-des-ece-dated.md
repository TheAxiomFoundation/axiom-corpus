# us-rulespec-2026-10-09-az-des-ece-dated: release selector

Date: 2026-10-09. Selector `manifests/releases/us-rulespec-2026-10-09-az-des-ece-dated.json`,
built by `scripts/repro/us_rulespec_2026_10_09_az_des_ece_dated.py` and checked by
`tests/test_us_rulespec_2026_10_09_az_des_ece_dated.py`.

## What it is

The selector is `us-rulespec-2026-09-24-snap-fy2027-cola` (273 scopes) plus one
scope, `us-az/manual/2026-10-09-az-des-snap-ece-dated-authority` (the Arizona DES
"What's Changed on 03/23/2026" notice; see
[its run note](2026-10-09-az-des-snap-ece-dated-authority.md)). That makes 274
scopes. It is a strict superset of both:

- `us-rulespec-2026-08-08-obbb-alien-snap`, which rulespec-us pins today; and
- `us-rulespec-2026-09-24-snap-fy2027-cola`, which the FY 2027 SNAP COLA work
  (rulespec-us#1394) planned to pin.

One re-pin to this release therefore serves both the FY 2027 leaves and the
dated Arizona expanded categorical eligibility encoding (rulespec-us#1460). The
`us/guidance/2026-09-24-snap-fy2027-cola` scope is selected unchanged, as are
the other 272.

**Publish only. Do not activate it.** Activation repoints the serving map for
every (jurisdiction, document_class) pair a release carries, and the last
activation wins. This release is built on the older obbb-alien-snap line, so
activating it would roll most US serving pairs back. See
`docs/named-release-publication.md` and the `snap-fy2027-cola` selector's
changelog. rulespec-us consumes a pin from the release object; it does not use
serving.

## Exception to the us-ca recovery-scope rule

The predecessor selects `us-ca/statute/2026-07-13-recovery`.
[2026-09-25-us-ca-statute-recovery-audit.md](2026-09-25-us-ca-statute-recovery-audit.md)
says the next cut in this line should drop it and the PIT core scope and add
the income tax chapter scope. `test_no_new_tracked_selector_selects_the_recovery_scope`
enforces that rule.

This selector keeps the recovery scope, and the test allowlists it by name with
the reason in code. The reason: that run note records that the swap "changes
what the ten R&TC modules and the CalWORKs module resolve to" and
"re-fingerprints the CalWORKs module's waiver" in rulespec-us. The re-pin this
release exists for has to change nothing but the Arizona notice and the FY 2027
memorandum. The swap is still owed, in a cut and re-pin of its own. The rule
for later cuts is otherwise unchanged.

Keeping the scope adds no new defect. Apart from the notice's two rows and the
FY 2027 memorandum, every row the release selects is already selected by the
pin rulespec-us uses today.

## Checks run

All checks ran on the branch, after `axiom-corpus-ingest corpus fetch --release
manifests/releases/us-rulespec-2026-10-09-az-des-ece-dated.json` materialized
12,507 locked files (1,454,972,546 bytes, 0 failed).

- `axiom-corpus-ingest validate-release --base data/corpus --release
  manifests/releases/us-rulespec-2026-10-09-az-des-ece-dated.json --max-issues 100`:
  `ok: true`, 274 scopes, 0 errors, 541 warnings, all `missing_parent_id`. The
  predecessor gives the same 541 warnings and 0 errors on the same tree.
- `axiom-corpus-ingest guard-ingested --base-ref origin/main --head-ref HEAD`:
  "All changed corpus artifacts have signed ingest manifests."
- `axiom-corpus-ingest corpus verify --remote --changed-since origin/main`:
  4 entries checked, 0 missing from R2.
- `axiom-corpus-ingest corpus verify --attest`: 62,527 entries checked, OK.
- Tests:
  - `tests/test_us_rulespec_2026_10_09_az_des_ece_dated.py`:
    - the reproducer is byte-identical;
    - the scope delta is exact;
    - the selector is a strict superset of the rulespec-us pin;
    - the new paths are disjoint from the predecessor's;
    - the amendment targets resolve in `2026-07-17-faa5-recovery`;
    - the body is at most 12,000 characters;
    - a Hypothesis property over arbitrary base selectors holds.
  - `tests/test_us_ca_statute_recovery_audit.py` passes.
  - `tests/test_us_rulespec_2026_09_24_snap_fy2027_cola.py` passes.
- Mutation check: the new tests fail under three mutations:
  - dropping the us-ca recovery scope from the selector (3 failures);
  - pointing `amends` at a page the release does not carry (1 failure);
  - setting `expression_date` to the capture date (1 failure).
- `scripts/publish_corpus.py --release
  manifests/releases/us-rulespec-2026-10-09-az-des-ece-dated.json --dry-run`
  (results in the pull request).

## After merge

`publish.yml` publishes the selector on the push to `main`: it validates,
uploads, stages, signs and registers it. It does not activate. Next:

1. Read the content SHA-256 from the run's `publication end:` log line or its
   `signed-corpus-release-object` artifact. Confirm `"activation": null`.
2. Dispatch `mirror-release.yml` with that publish run id, release name and
   SHA-256. axiom-encode's `targeted-signed-reencode.yml` fetches release
   objects only from the public bucket.
3. Check that
   `https://pub-a8952f8657fc49fda358146ac001366c.r2.dev/releases/us-rulespec-2026-10-09-az-des-ece-dated/<sha>.json`
   returns 200.
4. rulespec-us re-pins `.axiom/toolchain.toml` (`axiom_corpus_release` and
   `axiom_corpus_release_content_sha256`). It also moves
   `.axiom/workflow-toolchain.toml` `axiom_corpus_ref` to a corpus commit that
   descends from this selector's merge commit.
