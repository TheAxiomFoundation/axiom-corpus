# us-rulespec-2026-10-25-nyc-ch127-title-52: release selector

Date: 2026-10-25. Selector `manifests/releases/us-rulespec-2026-10-25-nyc-ch127-title-52.json`,
built by `scripts/repro/us_rulespec_2026_10_25_nyc_ch127_title_52.py` and checked by
`tests/test_us_rulespec_2026_10_25_nyc_ch127_title_52.py`.

## What it is

rulespec-us's corpus pin, `us-rulespec-2026-10-25-ssi-poms-public-laws` (271 scopes; rulespec-us
`.axiom/toolchain.toml` on `main`), with one scope replaced and one added. Both new scopes are signed
and locked, and neither is withdrawn:

| Change | Scope | Ingested |
| --- | --- | --- |
| Replaces `us-ny/statute/2026-06-05-nyc-admin-code` | `us-ny/statute/2026-09-28-nyc-admin-code` | `docs/ingest-runs/2026-09-28-nyc-admin-code-ch127.md` (#773) |
| Added | `us/statute/2026-09-29-election-statute-uocava-nvra-title-52` | `docs/ingest-runs/2026-09-29-election-statute-uocava-nvra.md` (#771) |

That makes 272 scopes. Every other scope of the pin is kept unchanged.

## Why

- **NYC Administrative Code.** Chapter 127 of 2026 (A.11561 Part D §§ 6-8) moves the reversion of the
  NYC resident income tax rates in § 11-1701 and of the 14% additional tax in § 11-1704.1 from 2027
  to 2030. The pin's 2026-06-05 scope holds the text before that amendment. rulespec-us#1438
  re-encodes §§ 11-1701 and 11-1704.1 against the amended text, which it can cite only once
  rulespec-us pins a release that carries the 2026-09-28 scope (axiom-corpus#766).
- **Title 52.** The election scope holds 52 U.S.C. 20302, 20310 and 20507 for RuleSpec encodings of
  voter-eligibility and deadline rules. No release on the rulespec-us pin line carries it yet.
  Carrying it here saves rulespec-us a second re-pin. This selector supersedes #772, which cut the
  same addition on an older base (`us-rulespec-2026-09-24-snap-fy2027-cola`) and would drop scopes
  the pin has gained since.

## Paths

- The two NYC scopes carry the same three citation paths, `us-ny/statute/NYC/11-1701`,
  `us-ny/statute/NYC/11-1704.1` and `us-ny/statute/NYC/11-1706`, with no parent rows. Selecting both
  would fail `duplicate_release_citation`, so the old scope is dropped. After the re-pin, rulespec-us's
  three NYC modules (`us-ny/statutes/NYC/11-1701.yaml`, `11-1704/1.yaml` and `11-1706.yaml`) resolve
  the same paths to the amended text. Their validation results can change at that re-pin, which is
  the point of #1438.
- The Title 52 scope uses the `us/statute/52` family. Its run note found that no tracked `us/statute`
  provisions file carried that family before it. CI's `Validate named release selectors` job
  deep-validates this cut with corpus data, including citation uniqueness under
  `complete-expression-dates-v1`.

## Checks

- The reproducer matches the committed selector byte for byte.
- The selector equals the pin minus the 2026-06-05 NYC scope plus the two scopes, sorted. The test
  pins the expected delta as literals, so a change to the reproducer's constants can't also change
  what is checked. Exactly one NYC Administrative Code scope is selected.
- Each added scope is locked and not withdrawn, and the selector picks up no withdrawn scope the pin
  does not already select.
- It keeps the pin's three withdrawn scopes, `us-me`, `us-mi` and `us-mn` `statute/2026-07-13-recovery`.
  Allowances do not carry forward, so `manifests/withdrawn-scopes.yaml` records an exception for this
  selector on each, pinned to its digest (`51c4f297…`). rulespec-us#1365, which re-points the modules
  citing them, has not landed; the first cut in the line after it drops them.
- A Hypothesis property checks the build rule over arbitrary bases. A base that lacks the replaced
  scope, or already holds an addition, is refused.

## Coordination with #926

axiom-corpus#926 cuts `us-rulespec-2026-10-23-ks-liheap` on `us-rulespec-2026-10-22-ca-concurrent-versions`,
which is no longer the pin. rulespec-us pins one release, so #926 must be rebuilt on the latest pin before
it is published: set its `BASE_RELEASE` to this selector (or whichever pin-line selector merges last),
rerun its reproducer, raise its expected count by the seven Kansas LIHEAP scopes and re-record its
selector digest in `manifests/withdrawn-scopes.yaml`.

## After merge

1. Dispatch `publish.yml` with this release, then `mirror-release.yml`. Merging a selector does not
   publish it (`docs/ingest-runs/2026-10-23-election-statute-uocava-nvra-review-addendum.md`).
   **Publish only. Do not activate it.** It is a pin release for rulespec-us; see
   `docs/named-release-publication.md`.
2. Re-pin rulespec-us to this release with the published `content_sha256`. Expect validation changes
   on the three NYC modules; #1438 re-encodes §§ 11-1701 and 11-1704.1.
