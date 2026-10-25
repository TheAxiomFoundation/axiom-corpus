# us-rulespec-2026-10-25-ssi-poms-public-laws: release selector

Date: 2026-10-25. Selector `manifests/releases/us-rulespec-2026-10-25-ssi-poms-public-laws.json`,
built by `scripts/repro/us_rulespec_2026_10_25_ssi_poms_public_laws.py` and checked by
`tests/test_us_rulespec_2026_10_25_ssi_poms_public_laws.py`.

## What it is

rulespec-us's corpus pin, `us-rulespec-2026-10-22-ca-concurrent-versions` (268 scopes; rulespec-us
`.axiom/toolchain.toml` at `ad03b325`), plus exactly three scopes. All three are signed and locked,
and none is withdrawn:

| Scope | Paths | Ingested |
| --- | --- | --- |
| `us/manual/2026-09-10-ssi-poms-si` | `us/manual/ssa/poms/si/<section>` | `docs/ingest-runs/2026-09-10-ssi-poms-si.md` |
| `us/manual/2026-09-13-ssi-poms-si-remainder` | `us/manual/ssa/poms/si/<section>` (the sections the 2026-09-10 run did not take) | `manifests/us-ssa-poms-si-remainder-2026-09-13.yaml` |
| `us/statute/2026-10-06-w6-federal-public-laws` | `us/statute/public-law/<congress>-<number>` | `docs/ingest-runs/2026-10-06-w6-federal.md` |

That makes 271 scopes, a strict superset of the pin. The W6 (`2026-10-07`), W5 (`2026-10-11`,
`2026-10-12`) and W7 (`2026-10-13`) unions already select all three, the public-law scope next to the
pin's `2026-06-29-pl-119-21-medicaid-community-engagement` scopes. The 2026-09-13 cms-state-plans and
federal-and-plans unions and the 2026-09-14 wave4 unions select both SSI POMS scopes. The pin is a
narrower line and carries none of them.

## Why these three

- rulespec-us#1910 encodes SSI retirement-fund resources from POMS SI 01120.210, ingested at
  `us/manual/ssa/poms/si/01120.210` (expression date 2012-12-04). It also relies on SI 01330.120,
  SI 01330.220 and SI 00830.500 (same scope) and SI 00510.001 (the remainder scope).
- rulespec-us#415 extends the taxation-of-benefits allocation for PolicyEngine-US #10381, and needs
  section 121 of Pub. L. 98-21 as amended by section 13215 of Pub. L. 103-66. Both are documents of
  the public-law scope (`public-law-98-21.pdf`, `public-law-103-66.pdf`).

## Paths

A re-pin changes no existing resolution. The SSI POMS scopes use the `us/manual/ssa/poms/si` family.
The pin's two POMS scopes, `us/guidance/2026-07-03-dc-ossp-ssa-poms` and
`us-de/guidance/2026-07-03-de-ssi-state-supplement-poms`, are guidance scopes. The two SSI scopes are
disjoint: their manifests list 915 and 778 citation paths with none in common. The W6
run note's collision audit found that its document scopes, the public-law scope among them, share no
path with any scope on disk. They use the `public-law` family, which no U.S. Code scope emits. The
collision it records with the P.L. 119-21 Medicaid scopes belongs to
`2026-10-06-w6-federal-usc-medicaid-sections-title-42`, which this selector does not add. CI's
`Validate named release selectors` job deep-validates the cut with corpus data.

## Coordination with #926

axiom-corpus#926 cuts `us-rulespec-2026-10-23-ks-liheap` on the same base (268 plus seven Kansas LIHEAP
scopes, for rulespec-us#1469). rulespec-us pins one release, so whichever selector merges second must
be rebuilt on the first. If #926 merges first, set `BASE_RELEASE` to `us-rulespec-2026-10-23-ks-liheap`,
rerun the reproducer, raise the expected count to 278 and re-record the selector digest. Either way,
the next rulespec-us re-pin carries all ten added scopes.

## Checks

- The reproducer matches the committed selector byte for byte.
- The selector equals the pin plus the three scopes, sorted. Each added scope is locked and not withdrawn.
- It keeps the pin's three withdrawn scopes, `us-me`, `us-mi` and `us-mn` `statute/2026-07-13-recovery`.
  Allowances do not carry forward, so `manifests/withdrawn-scopes.yaml` records an exception for this
  selector on each, pinned to its digest. rulespec-us#1365, which re-points the modules citing them, has
  not landed; the first cut in the line after it drops them. A test requires each kept withdrawn scope
  to have its own exception and allows no other.
- A Hypothesis property checks the build rule over arbitrary bases, including bases that already hold
  any of the additions.
- Deep validation with corpus data runs in CI's `Validate named release selectors` job.

## After merge

1. Dispatch `publish.yml`, then `mirror-release.yml`. **Publish only. Do not activate it.** It is a
   pin release for rulespec-us; see `docs/named-release-publication.md`.
2. Re-pin rulespec-us to this release. That is the corpus half of rulespec-us#1910 and #415. Each
   encoding still needs its signed-encoder dispatch.
