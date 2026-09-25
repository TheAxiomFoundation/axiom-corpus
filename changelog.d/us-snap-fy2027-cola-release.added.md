Added the immutable `us-rulespec-2026-09-24-snap-fy2027-cola` release selector,
preserving the scopes of `us-rulespec-2026-08-08-obbb-alien-snap` and adding the
USDA SNAP Fiscal Year 2027 cost-of-living adjustments memorandum. It is a
publish-only pin release for rulespec-us: do not dispatch it to
`activate-release.yml`, because it is built on an older lineage and activating
it would roll back most US serving pairs.
