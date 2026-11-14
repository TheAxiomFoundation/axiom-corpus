# us-rulespec-2026-11-14-cms-smd-26-006: release selector

Date: 2026-11-14. `scripts/repro/us_rulespec_2026_11_14_cms_smd_26_006.py` builds the selector
`manifests/releases/us-rulespec-2026-11-14-cms-smd-26-006.json`, and
`tests/test_us_rulespec_2026_11_14_cms_smd_26_006.py` checks it.

## What it selects

This selector takes the newest cut of rulespec-us's corpus pin line,
`us-rulespec-2026-11-11-cms-w6-federal-guidance` (284 scopes), and adds one signed scope,
`us/guidance/2026-11-14-cms-smd-26-006` (`docs/ingest-runs/2026-11-14-cms-smd-26-006.md`, ingested in
this change; source manifest `manifests/us-cms-smd-26-006-hold-harmless.yaml`). It keeps every scope of
the base and the line's quality profile, `complete-expression-dates-v1`, so it selects 285.

rulespec-us `main` pins `us-rulespec-2026-10-29-ecfr-section-text` (276 scopes; `.axiom/toolchain.toml`,
last changed in `375793cd`, content sha `063457c6…`; checked 2026-11-14). This selector holds all 276
scopes of that pin, the seven Kansas LIHEAP scopes of `us-rulespec-2026-10-27-ks-liheap`, the wave-6
federal CMS guidance scope of `us-rulespec-2026-11-11-cms-w6-federal-guidance` and the SMD #26-006
scope.

## Why

The encoder reads source text through rulespec-us's pin. CMS issued State Medicaid Director letter
SMD# 26-006, "Optional Hold Harmless Period for Community Engagement Implementation", on 2026-11-13. It
offers states an optional period through June 30, 2027 during which they may suspend denials and
disenrollments for failure to demonstrate compliance with the community engagement requirement of
section 1902(xx) of the Social Security Act. No release selects the letter, so an encoding of the
option cannot cite it until rulespec-us pins a release that does.

## The base

`axiom_corpus.corpus.selector_lineage.line_heads`, run over the tracked selectors and
`manifests/selector-lineage-baseline.yaml` at `origin/main` 7242a0229, returns one head for the line
through the pin, `us-rulespec-2026-11-11-cms-w6-federal-guidance`. Its chain of named predecessors is
`us-rulespec-2026-10-27-ks-liheap`, then the pin. No open pull request other than #980 adds a selector
on this line (checked 2026-11-14). The description names the base first, so the lineage check compares
this cut with it.

## The added scope

| | |
| --- | --- |
| Provision rows | 5, in one document |
| Letter | one document row at `us/guidance/cms/smd/26-006` and four page rows `page-1` to `page-4` (3,284, 3,637, 3,303 and 815 body characters), source id `cms-smd-26-006`, `expression_date` 2026-11-13 |
| Source | the official PDF from medicaid.gov, 170,600 bytes, SHA-256 `9afc56d8…991be` |
| Citation paths | all under `us/guidance/cms/smd/26-006` |
| Content findings | none; no entry in `manifests/release-content-baseline.json` |

## Checks

- The reproducer matches the committed selector byte for byte.
- The selector equals the base plus the one scope, stays sorted and holds every scope of the pin. The
  test pins the addition as literals, so a change to the reproducer's constants cannot also change
  what the test checks.
- A lock file exists for the added scope, and the withdrawn-scope ledger does not list it. The
  selector picks up no withdrawn scope the base does not already select.
- It keeps the line's three withdrawn scopes, `us-me`, `us-mi` and `us-mn`
  `statute/2026-07-13-recovery`. Allowances do not carry forward, so `manifests/withdrawn-scopes.yaml`
  records an exception for this selector on each and pins them to its digest (`e4471a0a…`).
  rulespec-us#1365, which was to re-point the modules citing them, is still closed without a merge
  (checked 2026-11-14); the first cut in the line after that re-pointing lands drops them.
- The lineage tests pass with the selector in place: `tests/test_selector_lineage_repository.py` and
  `tests/test_selector_lineage_prose_repository.py`, 91 passed.
- `tests/test_release_policy_repository.py`: the ledger tests pass (no tracked selector selects a
  withdrawn scope without an allowance, every allowance names a tracked selector that selects the
  scope, grandfathered selectors predate their listing, no entry is listed in the future).
- `content-check us/guidance/2026-11-14-cms-smd-26-006 --check-baseline` on the locked scope: no
  findings and no baseline differences.
- `guard-ingested --base-ref origin/main --head-ref HEAD`, with the repository's public verification
  key: "All changed corpus artifacts have signed ingest manifests."
- `corpus verify --remote --attest --changed-since origin/main`: 4 lock entries checked, 0 missing from
  R2.
- Ruff, mypy on `src/axiom_corpus/corpus`, and `towncrier check --compare-with origin/main` pass.
- Citation-path ratchet. The scope's five paths match the grammar, and each stored `id` is the
  path-only identity. The four page rows are the only members of any irregular family (`page_n`), so
  `schema/citation-path.v1.json` raises the `page_n` baseline from main 7242a0229's 178888 to 178892,
  with a sentence in the ratchet's description. The full-tree scan needs every locked scope, so PR CI
  runs it.
- A Hypothesis property checks the addition over arbitrary bases, including bases where other pairs
  reuse the added scope's version string. The reproducer refuses a base that already holds the scope
  or repeats a scope.

`axiom-corpus-ingest validate-release --strict-warnings`, under the line's quality profile:

| Selection | Scopes | Errors | Warnings | Notices | `ok` |
| --- | ---: | ---: | ---: | ---: | --- |
| The added scope alone | 1 | 0 | 0 | 0 | true |

Not run on this checkout:

- `validate-release` on the whole selector (285 scopes), on the base and on the pin;
- `scripts/publish_corpus.py --release manifests/releases/us-rulespec-2026-11-14-cms-smd-26-006.json
  --dry-run`;
- the tests that read other scopes' provisions: `test_no_citation_path_of_the_added_scope_is_already_in_the_base`
  in this selector's test file, and that test, `test_the_added_scope_holds_the_bulletin` and
  `test_the_added_scope_validates_alone_with_strict_warnings` in the 2026-11-11 test file. The other 13
  tests of this file and 11 of the 2026-11-11 file pass with `AXIOM_CORPUS_PARTIAL_TESTS=1`.

They need the base's 284 scopes in the worktree (16,104 more locked files, 2.03 GB). Every object is
already in the local content cache, so a fetch would place APFS clones and download nothing. This run
did not fetch them: the host stayed below its 100 GB free-disk floor (95 to 99 GB free) with a
one-minute load above 150 throughout, and the run's rules stop corpus fetches, whole-release validation
and publication dry runs under either condition. Exact-head CI on a full corpus checkout runs them.

## Coordination with #980

Draft #980 cuts `us-rulespec-2026-11-05-mt-arm-37-78-420-successor` from the pin; it was last updated
2026-11-05, before #938 and the 2026-11-11 cut merged. rulespec-us pins one release, and the lineage
check rejects two unrecorded successors of one selector, so the cuts go one after another:

- If this selector merges first, #980 sets its `BASE_RELEASE` to this selector, reruns its reproducer
  (one Montana scope swapped, so it selects 285), updates its expected count and re-records its
  digest and the ME/MI/MN exceptions.
- If #980 is re-cut on `us-rulespec-2026-11-11-cms-w6-federal-guidance` and merges first, this cut
  sets its `BASE_RELEASE` to #980's selector and reruns the reproducer. The change is the same one
  scope added; the count stays 285, and the digest and the three exceptions are re-recorded.

## Coordination with rulespec-us#2196

Draft rulespec-us#2196 re-pins rulespec-us to `us-rulespec-2026-11-11-cms-w6-federal-guidance`, this
selector's base. This selector holds all 284 of that release's scopes and adds only the letter, so
once it is published a re-pin to it supersedes #2196: the re-pin PR names #2196, and #2196 closes
unmerged, or is retargeted to this release, whichever Max prefers.

## After merge

1. Dispatch `publish.yml` with this release, then `mirror-release.yml`. Merging a selector does not
   publish it. **Publish only. Do not activate it.** rulespec-us pins this release; see
   `docs/named-release-publication.md`.
2. Re-pin rulespec-us to this release with the published `content_sha256`, and move its
   `axiom_corpus_ref` to a main commit at or after the release's signed provenance.
