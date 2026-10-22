# us-rulespec-2026-10-22-ca-concurrent-versions: release selector

Date: 2026-10-22. Selector `manifests/releases/us-rulespec-2026-10-22-ca-concurrent-versions.json`,
built by `scripts/repro/us_rulespec_2026_10_22_ca_concurrent_versions.py` and checked by
`tests/test_us_rulespec_2026_10_22_ca_concurrent_versions.py`.

## What it is

rulespec-us's corpus pin, `us-rulespec-2026-10-20-fs-pilot-reg-e-f` (267 scopes), plus exactly one
scope: `us-ca/statute/2026-09-26-ca-leginfo-concurrent-versions-us-ca-sections-wic-11450--all-wic-11451.5--all-rtc-17552.3--all-rtc-17563.5--all`,
signed and locked in #752. That makes 268 scopes, a strict superset of the pin.

The added scope gives each current LegInfo version of the four sections its own
`<section>--<slug>` variant path. Plain section paths keep their existing carriers, so a re-pin
changes no existing resolution. It adds paths such as `us-ca/statute/wic/11450--operative-2024-07-01`,
WIC 11450's later version, which governs CalWORKs maximum aid payments.

**Publish only. Do not activate it.** It is a pin release for rulespec-us; see
`docs/named-release-publication.md`.

## Why not #860

#860 cut `us-rulespec-2026-10-13-ca-concurrent-versions-union` on the 2026-10-13 w7 union lineage
(1,568 scopes). After the withdrawn-scope registry, that selector fails validation with nine
`withdrawn_scope_selected` errors: a new selector does not inherit its predecessor's
grandfathering. rulespec-us also now pins the smaller pin line, so this selector carries #752's
scope on that line instead.

## Checks

- The reproducer matches the committed selector byte for byte.
- The selector equals the pin plus the one scope, sorted. The scope is locked and not withdrawn, and
  the selector adds no withdrawn scope beyond the pin's recorded exceptions.
- A Hypothesis property checks the build rule over arbitrary bases.
- Deep validation with corpus data runs in CI's `Validate named release selectors` job.

## After merge

1. Dispatch `publish.yml`, then `mirror-release.yml`.
2. A rulespec-us re-pin to this release is the corpus half of re-pointing the CalWORKs monthly aid
   payment module to the WIC 11450 version in force.
