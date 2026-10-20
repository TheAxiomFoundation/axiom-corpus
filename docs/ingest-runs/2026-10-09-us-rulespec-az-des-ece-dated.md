# us-rulespec-2026-10-09-az-des-ece-dated: release selector

Date: 2026-10-09; refreshed against the current RuleSpec pin on 2026-10-14.
Selector `manifests/releases/us-rulespec-2026-10-09-az-des-ece-dated.json`,
built by `scripts/repro/us_rulespec_2026_10_09_az_des_ece_dated.py` and checked by
`tests/test_us_rulespec_2026_10_09_az_des_ece_dated.py`.

## What it is

The selector is the current rulespec-us pin,
`us-rulespec-2026-10-13-snap-fy2026-memo-source-corrected` (272 scopes), plus
exactly two scopes: `us/guidance/2026-09-24-snap-fy2027-cola` for the FY 2027
SNAP COLA work (rulespec-us#1394), and
`us-az/manual/2026-10-09-az-des-snap-ece-dated-authority` for the Arizona DES
"What's Changed on 03/23/2026" notice (see
[its run note](2026-10-09-az-des-snap-ece-dated-authority.md)). That makes 274
scopes and is a strict superset of the current pin. One re-pin can therefore
serve both the FY 2027 leaves and the dated Arizona expanded categorical
eligibility encoding (rulespec-us#1460) without dropping the FY 2026 FNS
guidance or reverting California table-preserving source scopes.

**Publish only. Do not activate it.** Activation repoints the serving map for
every (jurisdiction, document_class) pair a release carries, and the last
activation wins. This selector is for a RuleSpec pin, not a serving-map
activation; activating it would repoint unrelated US serving pairs. See
`docs/named-release-publication.md` and the `snap-fy2027-cola` selector's
changelog. rulespec-us consumes a pin from the release object; it does not use
serving.

## California source identities

The current RuleSpec pin already carries the table-preserving California
income-tax chapter and WIC-CalWORKs scopes and no longer carries the defective
recovery and PIT-core scopes. This selector inherits those exact identities.
The [recovery-scope audit](2026-09-25-us-ca-statute-recovery-audit.md) requires
that later selectors not restore the defective recovery scope; no exception is
needed here.

## Checks run on the refreshed selector

`axiom-corpus-ingest corpus fetch --release` materialized 13,519 locked files
from the content cache. The four signed Arizona notice files were not available
to that local fetch, so the native extractor regenerated them from the manifest;
each SHA-256 matched the existing signed corpus lock exactly. No ingest manifest
or locked artifact was changed in Git.

- `axiom-corpus-ingest validate-release` returned `ok: true`, 274 scopes,
  zero errors and 541 `missing_parent_id` warnings. The current 272-scope
  predecessor has the same 541 warnings and zero errors on this checkout.
- The focused selector, California recovery-audit, and FY 2027 COLA tests:
  27 passed with `AXIOM_CORPUS_PARTIAL_TESTS=1`. They check exact reproduction,
  the two-scope delta, the current-pin superset, noncolliding citation paths,
  amendment targets, and the California source-identity rule.
- `guard-ingested --base-ref origin/main --head-ref HEAD` passed after commit
  using the repository's public verification key. No signed ingest bytes were
  edited.
- `publish_corpus.py --dry-run` succeeded: 274 scopes, 13,523 artifacts and
  95,325 provision rows. Nothing was published or activated.
- Ruff, mypy on `src/axiom_corpus/corpus`, and towncrier check passed.
- The full local pytest run on a partial checkout produced 198 failures and
  reported unfetched locked corpus files (5,588 passed, 106 skipped, 208
  deselected). Those failures were not all classified.
  It is not a green full-suite result; exact-head CI on a full corpus checkout
  is still required before merge.

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
