# us-rulespec-2026-10-13-ca-concurrent-versions-union

Successor to `us-rulespec-2026-10-13-w7-bundle-gaps-union` (#856). It selects every scope of that cut, 1,567, and
adds one: the California LegInfo concurrent-versions scope of #752,

- `us-ca/statute/2026-09-26-ca-leginfo-concurrent-versions-us-ca-sections-wic-11450--all-wic-11451.5--all-rtc-17552.3--all-rtc-17563.5--all`
  (9 rows; run note `docs/ingest-runs/2026-09-26-us-ca-leginfo-concurrent-versions.md`).

That gives 1,568 scopes. The new scope is signed and locked in #752; this cut adds only the selector and this note.
It removes nothing.

## Why

The scope gives each current LegInfo version of four sections its own same-number variant row
(`<section>--<slug>`). One of them is in no selected scope: WIC 11450's later version,
`us-ca/statute/wic/11450--operative-2024-07-01` (Stats. 2024, ch. 798, sec. 2, as amended by Stats. 2026, ch. 310,
sec. 2). The plain path `us-ca/statute/wic/11450`, carried by the CalWORKs scope and its table-preserving successor,
holds the earlier version.

The later version governs today. CDSS All County Information Notice I-15-25 (April 17, 2025) says the automation
is done, that CDSS "has notified the Legislature", and that the automation-dependent SB 1083 changes are operational
effective March 5, 2025. By the later version's (n) and the earlier version's (p), the later version is operative
from that date; the earlier one became inoperative then and was repealed on January 1, 2026.

rulespec-us `us-ca/policies/cdss/calworks/monthly-aid-payment.yaml` cites `us-ca/statute/wic/11450/a/1/A`, a path
whose only row is in the withdrawn July recovery scope, and which no release cut since 2026-09-24 carries
(hollow-root audit, #853). Its (a)(1)(A) text and table read the same in both versions. Once a release the
rulespec-us toolchain pins carries this scope, the module can cite the version in force.

## Checks

- The scope joins the us-ca statute scopes of `us-rulespec-2026-10-13-w7-bundle-gaps-union` with strict warnings and
  0 issues (`test_the_scope_joins_the_newest_cuts_us_ca_statute_scopes_cleanly`, #752). Those are #742's
  table-preserving successors of the CalWORKs and income tax chapter scopes, SSI/SSP, CalFresh BBCE and the
  2026-10-06 WIC title scope.
- Release validation keys uniqueness on `citation_path`, and every path starts with its jurisdiction and document
  class, so only us-ca statute scopes could collide with the new rows. No other us-ca scope carries a `--` path
  (`test_no_other_us_ca_scope_carries_a_variant_path`).
- The selector differs from its predecessor only in `name`, `description` and the one added scope; it loads with
  `ReleaseManifest.load` (1,568 scopes).
- Deep validation, run locally because CI runs only on pull requests into `main` and this one is stacked: every
  scope of both selectors fetched (52,376 locked files), then
  `AXIOM_CORPUS_NO_FETCH=1 axiom-corpus-ingest validate-release --base data/corpus --max-issues 100 --workers 4`
  with both `--release` paths, as CI's step does. Both are ok with 0 errors and 564 warnings each, the same codes
  in the same numbers (`missing_parent_id` 94, `empty_provision_text` 4, `unsectioned_document_body` 2 among the
  first 100), so the added scope brings no new warning. CI deep-validates every selector again once this targets
  `main`.

## Merge order and publication

This branch is stacked on #752 and merges after it. Merging a selector does not publish: publication is a manual
dispatch of `.github/workflows/publish.yml`, and activation is a separate step.

If the union lineage has moved past `us-rulespec-2026-10-13-w7-bundle-gaps-union` by the time #752 merges, either
add the scope to the next union cut, or regenerate this selector from the newest one:

```bash
BASE=manifests/releases/<newest union cut>.json
jq --argjson s '{"jurisdiction":"us-ca","document_class":"statute","version":"2026-09-26-ca-leginfo-concurrent-versions-us-ca-sections-wic-11450--all-wic-11451.5--all-rtc-17552.3--all-rtc-17563.5--all"}' \
  '.scopes += [$s] | .scopes |= sort_by(.jurisdiction, .document_class, .version)' "$BASE"
```

Then set `name` and `description`, and add the new cut to the parametrized list of
`test_the_scope_joins_the_newest_cuts_us_ca_statute_scopes_cleanly`.
