VERDICT: REQUEST-CHANGES

# Blind adversarial review: PR #552

## Pinned review target

- PR: `#552`, branch `ingest/ca-bbce-authority`
- GitHub-verified head: `058cf9ff662161de6ea008e7d0098cb38e9571d8`
- GitHub-verified base: `main` at
  `10142cb0f07403c2de4599c76bec01e96640fda9`
- Merge base: exactly the base SHA above
- PR range: 12 commits, 23 changed paths
- Disposable review worktree:
  `.git/review-worktrees/pr-552-058cf9f`

The local review commits sit only on `review/pr-552-058cf9f-blind`. I made no
PR-branch, remote, GitHub, publication, R2, Supabase, or serving-database
writes.

## Findings requiring changes

### 1. BLOCKER — the claimed portable byte-identical reproduction fails in CI

The committed replay succeeds under the lockfile's PyMuPDF 1.26.7, but the
project metadata permits `pymupdf>=1.25.0`. The head-associated GitHub test job
therefore installed PyMuPDF 1.28.0 in a fresh supported pip environment.

[CI run 30378087303, job 90338774858](https://github.com/TheAxiomFoundation/axiom-corpus/actions/runs/30378087303/job/90338774858)
then failed the new
`test_offline_reproduction_is_byte_deterministic`:

- first differing artifact:
  `data/corpus/provisions/us-ca/guidance/2026-07-28-ca-cdss-calfresh-bbce-authority.jsonl`
- first differing byte: offset 2295
- committed/1.26.7 text begins with the ACL's date at that location
- 1.28.0 adds PDF accessibility text identifying the CDSS letterhead, logo,
  and California state seal before the date
- CI result: `1 failed, 4120 passed, 71 skipped, 208 deselected`

This is extractor-version nondeterminism, not a source-byte difference. The
CI log records both the accepted dependency range and the resolved 1.28.0
wheel; `uv.lock` records 1.26.7. A fresh install allowed by `pyproject.toml`
cannot reproduce the retained JSONL, so the portable replay claim is false.

Required remediation: make PDF extraction stable across the supported
dependency surface, or constrain the supported PyMuPDF version in install
metadata and CI—not only in `uv.lock`. Then regenerate any changed artifacts,
update the deterministic test, re-run a fresh pip-install replay, and re-sign
manifests whose applied files change.

### 2. MAJOR — the “Current MCE exclusions” authority map is incomplete

The worker map labels ACL 15-42 page 3 as `Current MCE exclusions` and gives
only intentional-program-violation and head-of-household work
noncompliance. Those excerpts are verbatim, but ACL 15-42 introduces them as
examples; it is not the exhaustive current controlling source.

Current [7 CFR 273.2(j)(2)(vii)](https://www.ecfr.gov/current/title-7/subtitle-B/chapter-II/subchapter-C/part-273/subpart-A/section-273.2)
also prevents household categorical eligibility for:

- applicable monthly-reporting disqualification;
- an entire-household workfare disqualification;
- fleeing-felon or probation/parole-violator status; and
- specified serious-crime conviction with sentence noncompliance.

That current federal section is already retained at
`us/regulation/7/273/2`, with `source_as_of: 2026-07-09`. Paragraph
(j)(2)(ix) separately preserves individual-member exclusions, including
noncitizen, student, institutional, and applicable work-rule ineligibility.
Current [WIC §18901.3](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=WIC&sectionNum=18901.3.)
removes conviction-alone drug-felony ineligibility in California, but
expressly preserves probation/parole compliance and fleeing-felon
ineligibility. Retained ACL 14-100 pages 2, 4, and 5 also describe those state
limits.

The focused test proves that 13 selected strings exist. It does not prove that
the exclusion set is complete, so it passes despite this defect. Encoding the
map as written could confer MCE where current law forbids it or could let MCE
override separately applicable nonfinancial eligibility gates.

Required remediation: map the complete exclusion surface to the retained
current federal provision plus the California opt-out authority, or explicitly
relabel the ACL row as two non-exhaustive examples and identify where every
remaining federal/state gate is composed. Add a semantic completeness test,
not only substring-presence assertions.

### 3. MINOR — later focused zero-benefit authority is omitted

ACL 14-56 page 6 supports the asserted behavior, but
[ACL 14-63](https://www.cdss.ca.gov/lettersnotices/entres/getinfo/acl/2014/14-63.pdf),
dated September 16, 2014, is the later focused operational instruction. It
specifies the minimum-benefit treatment for one- and two-person households,
table-based amounts for larger households even above the ordinary net
ceiling, and California's denial/termination treatment when the calculated
amount is zero.

This omission does not reverse the encoded result, but the authority map
should identify ACL 14-63 as the more direct controlling guidance or explain
why the older general letter is intentionally sufficient.

### 4. HYGIENE — tracked final-state documentation still says “unsigned”

The final two PR commits sign both manifests, yet:

- `docs/ingest-runs/2026-07-28-ca-calfresh-bbce-authority.md` says they
  “remain unsigned”; and
- the PR-head `PROGRESS.md` lines 94–120 says signatures are missing and
  signing remains next. It also claims a reasoning-log hash, although both
  final manifests have empty `reasoning_logs`.

Update these tracked records to the actual final signed state and final
validation results.

## Per-parameter authority verification

I checked all 13 `EXPECTED_EXCERPTS` independently against the normalized
JSONL. All 13 occur verbatim across the 10 asserted citation paths. Presence
and substantive sufficiency are distinct:

| Parameter or neighboring rule | Result | Evidence and current-authority conclusion |
| --- | --- | --- |
| California categorical-eligibility mandate | PASS | `us-ca/statute/wic/18901.5` matches the retained official HTML. The live [WIC §18901.5](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=WIC&sectionNum=18901.5.) remains unchanged and requires categorical eligibility subject to federal requirements. |
| Inclusive 200% FPL gross screen | PASS | ACL 14-56 page 1 says “at or below,” 14-56E page 2 says “at or less,” and 15-42 page 2 again says “at or below.” Encode `gross_income <= 200% FPL`, not `<`. USDA's [current BBCE table](https://www.fns.usda.gov/snap/broad-based-categorical-eligibility), updated December 29, 2025, still lists California at 200%. Historical dollar tables are correctly not asserted as current. |
| PUB 275 categorical trigger | PASS, qualified | ACL 15-42 page 2 supports issued or online access to PUB 275 at the inclusive screen while meeting all other conditions. ACL 14-56 page 3 correctly warns that the pamphlet alone does not confer MCE. The current USDA table still describes California's trigger as a pamphlet. |
| Asset/resource eligibility test waived | PASS | ACL 14-56 page 3 says PUB 275 receipt exempts resources once MCE and other conditions are met. The current USDA table lists California with no asset limit, and the [current CDSS MCE fact sheet](https://www.cdss.ca.gov/calfreshoutreach/res/pdf/CalFresh_Modified_Categorical_Eligibility_Fact_Sheet.pdf) repeats the resource exemption. This does not waive ordinary resource rules for a household that does not receive MCE. |
| Net-income eligibility ceiling waived | PASS | ACL 15-42 page 4 says MCE households are not disqualified merely for exceeding the ordinary net ceiling: one or two members receive the applicable minimum, while larger households use the benefit table. Current 7 CFR 273.2(j)(2)(xi) likewise excludes the ordinary gross/net eligibility provisions. Net income still drives benefit calculation; a calculated zero is a separate operational rule. |
| Current MCE exclusions | **FAIL** | ACL 15-42's IPV and head-work excerpts are verbatim but non-exhaustive. Current 7 CFR 273.2(j)(2)(vii), current WIC §18901.3, and retained ACL 14-100 preserve additional gates, as detailed in Finding 2. |
| Former drug-felony exclusion | PASS, narrowly | ACL 14-100 page 2 correctly removes conviction-alone denial effective April 1, 2015. Current WIC §18901.3 confirms the opt-out. Do not erase independently applicable probation/parole or fleeing-felon restrictions. |
| Elderly/disabled neighboring route | PASS | ACL 13-32 page 1 correctly says an E/D household has no gross test for ordinary eligibility; the 200% line determines MCE conferment. An E/D household above 200% falls back to current ordinary net/resource rules. |
| Zero-benefit neighboring rule | PASS on behavior; authority caveat | ACL 14-56 page 6 is consistent, but later ACL 14-63 is the focused operational authority. |

I found no current repeal of California's pamphlet/200%/no-asset BBCE
financial policy. USDA's current state table affirmatively corroborates those
values. The 2026 federal work and noncitizen changes are separate eligibility
gates; they make an exhaustive-exclusion map more important, not less.

## Source authenticity and byte faithfulness

All retained hashes and byte counts match both the supplied untracked
source-lane report at
`.worktrees/ca-bbce-authority/CA-BBCE-WORKER-REPORT.md` and its flat local
source cache:

| Source | Bytes | Pages | SHA-256 | Identity check |
| --- | ---: | ---: | --- | --- |
| WIC §18901.5 HTML | 164,166 | — | `97cae778729e0dd5d3c15797934690467876a14057e7d856d1500326e72d004e` | Official LegInfo title, assets, hierarchy, and current section text |
| ACL 14-56 | 278,260 | 7 | `8677c1d3e5c2ec9ecef23206b24061999817a46fa469ccb68a000b8f2f570d5e` | CDSS letterhead; ACL 14-56; August 22, 2014 |
| ACL 14-56E | 189,729 | 4 | `67e33a2613009abaef3759ebc2a583417fb852120f009848e3b1a1e3c3c11cbd` | CDSS letterhead; ACL 14-56E; April 10, 2015 |
| ACL 15-42 | 249,307 | 13 | `6aab92e4e2a2c9e0f234eba2b1c0eeb68d4d9d5dbc7ba752465a2358d9f2db33` | CDSS letterhead; ACL 15-42; April 15, 2015 |
| ACL 14-100 | 209,290 | 12 | `c981081163b361eea20aeeccec7934509dc5bf23d8d66c8035895586db60131e` | CDSS letterhead; ACL 14-100; December 19, 2014 |
| ACL 13-32 | 204,909 | 3 | `1a0bbfc2d6d69fd378aff3f1285d03d20b8b6abf2ff64c749b9897fd1cc55506` | CDSS letterhead; ACL 13-32; April 24, 2013 |

Read-only web retrieval reached all five live official CDSS PDF URLs and the
official LegInfo section/chapter. The PDFs' displayed numbers, dates,
letterhead, page labels, and pagination match the retained files; all 39 pages
have nonempty embedded text. Shell DNS was blocked, so I could not perform a
fresh raw-byte download and compare it independently. The byte-faithfulness
conclusion is therefore based on exact agreement with the main-lane recorded
hashes and cache, plus independent live-document identity checks—not a second
network byte comparison.

## Normalization

- Claimed count passes: 45 rows = one WIC row + 44 guidance rows.
- Per-document counts pass: ACLs 14-56/14-56E/15-42/14-100/13-32 emit
  `8/5/14/13/4`.
- The five PDFs have `7/4/13/12/3` physical pages. Each emits a bodyless
  document root plus exactly one body-bearing row per physical page.
- All 39 page bodies match their stated physical page's PyMuPDF 1.26.7 text.
- This granularity matches existing California ACL/ACIN guidance ingests.
- Citation paths are unique, sequential, and well formed.
- Citation census passes at 143,775 records and 125,247 unique paths, with
  `page_n` exactly `31,397/31,397`.
- The one-section statute slice's parent handling is self-contained while
  preserving the official hierarchy in metadata.

The normalization is internally correct for the extractor version that
created it. Finding 1 is about the unsupported cross-version byte contract.

## Reproduction

The committed literal command is:

```bash
uv run --extra dev python scripts/repro/us_ca_calfresh_bbce_authority.py --base data/corpus
```

The same text appears in the script constant, run document, and both
manifests.

- Entered literally with the default environment, it stopped before Python
  because the sandbox denied `/Users/maxghenis/.cache/uv`.
- A retry with a writable empty cache stopped on DNS while resolving a missing
  dependency.
- With a writable cache, `UV_NO_SYNC=1`, and the existing locked project
  environment, the literal command text completed. All 12 generated hashes
  matched, counts were 44/1, and the tracked index hash remained
  `b5d6f37dc8df5b5a476aed2206f85c3ed16c8e9c` before and after.
- The same environment with
  `--source-dir /Users/maxghenis/TheAxiomFoundation/axiom-corpus/.worktrees/ca-bbce-authority/.ca-bbce-sources`
  also reproduced all 12 artifacts byte-identically.
- Both local runs left zero tracked drift.

Those locked-environment passes verify the script and local-source option, but
do not cure the fresh-install CI failure in Finding 1.

## Manifests

- Guidance signature: valid Ed25519; attests
  `552dca6c41847df55fe192507496938e538d29d1`.
- Statute signature: valid Ed25519; attests
  `6aa19a44a92ef4483a0eb9a5920a95cca086a096`.
- Both attested commits are ancestors of the pinned PR head.
- Every one of the 12 applied-file hashes matches both its attested commit and
  the pinned PR tree.
- Both manifests record the literal portable invocation.
- `guard-ingested` with the repository's public verification key passes for
  the exact base/head range with `issues: []`.
- Coverage in the signed manifests is complete at 44/44 and 1/1.

## Hygiene, gates, and baseline comparison

| Check | Result |
| --- | --- |
| GitNexus compare/impact | LOW; 39 indexed changed symbols; zero affected execution flows. New repro callers stay inside the new script and focused test. |
| `ruff check .` | PASS |
| MyPy on `src/axiom_corpus/corpus` | PASS: 89 source files |
| Towncrier check and draft | PASS |
| Changelog fragment | Present |
| `git diff --check` | PASS |
| Guidance/statute tracked-scope checks | PASS: 8 and 4 applied files |
| Strict two-scope release validation | PASS: zero errors/warnings |
| Citation census | PASS |
| Signed-ingest guard | PASS |
| Local PR full pytest | `1 failed, 4122 passed, 69 skipped, 208 deselected` |
| Clean-main full pytest | `1 failed, 4118 passed, 69 skipped, 208 deselected` |
| Head-associated GitHub full pytest | **FAIL**: PR-added replay test under PyMuPDF 1.28.0 |

The sole local PR failure is the same pre-existing
`TestPostgresStorageSubsectionConversion::test_dict_to_subsection` failure
reproduced on clean main under the same environment. The four added local
passes are the PR's focused tests. In contrast, fresh-install CI introduces
the PR-specific deterministic-replay failure.

No session report is introduced in the immutable PR range. The tracked
`PROGRESS.md` is expected, and the worker report/source cache remain untracked
in the separate source worktree.

## Sandbox and review-environment disclosures

- Direct shell downloads failed because DNS resolution was blocked. Official
  CDSS, LegInfo, USDA, eCFR, and GitHub evidence was read through read-only
  connectors.
- Plain `uv run` commands initially hit the unwritable default uv cache.
  Sandbox-safe retries used a writable temporary cache and the existing
  project environment, as described above.
- A clean empty uv environment could not finish dependency resolution because
  DNS was blocked.
- GitNexus generated the exact-head worktree graph, but registration in
  `/Users/maxghenis/.gitnexus/registry.json` was denied. Queries used a
  temporary local registry.
- The public manifest verification key was read from the public Actions job
  environment; no private signing material was accessed.
- No remote or GitHub mutation was attempted.
