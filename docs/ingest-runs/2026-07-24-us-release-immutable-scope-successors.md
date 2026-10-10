# US release immutable scope successors

## Purpose

The production publication attempt for
`us-rulespec-2026-07-24-cms-435-correction` failed closed because three scopes
selected by earlier signed releases had subsequently been changed in place.
The immutable publication gate correctly rejected reuse whose local artifacts
and database projection no longer matched the released scope.

## Remediation

The corrected artifacts are re-versioned into new self-contained scopes:

- Iowa statute:
  `2026-07-16-pit-east-us-ia-title-x-chapter-422-r2026-07-24-immutable`
- Maryland statute:
  `2026-07-13-recovery-r2026-07-24-immutable`
- Oklahoma statute:
  `2026-07-16-pit-central-us-ok-title-68-r2026-07-24-immutable`

The source snapshots are byte-identical copies of the corrected official
captures. Inventory and provision source paths, nested metadata source paths,
scope versions, provision identifiers, and parent identifiers are regenerated
for each successor version. The previously released scope paths remain
unchanged by this repair.

## Release

`us-rulespec-2026-07-24-cms-435-correction-immutable-scopes` succeeds the failed
selector. It retains the corrected federal CMS scope and replaces only the
three historically mutated state-statute selections.

## Validation

```text
uv run --extra dev python -m pytest -q \
  tests/test_reversion_expression_dates.py \
  tests/test_us_release_immutable_scope_successors.py
uv run --extra dev axiom-corpus-ingest validate-release \
  --base data/corpus \
  --release us-rulespec-2026-07-24-cms-435-correction-immutable-scopes \
  --max-issues 200
uv run --extra dev python scripts/publish_corpus.py \
  --release manifests/releases/us-rulespec-2026-07-24-cms-435-correction-immutable-scopes.json \
  --dry-run
```
