# us-rulespec-2026-11-05-mt-arm-37-78-420-successor: release selector

Date: 2026-11-05. `scripts/repro/us_rulespec_2026_11_05_mt_arm_37_78_420_successor.py` builds the
selector `manifests/releases/us-rulespec-2026-11-05-mt-arm-37-78-420-successor.json`, and
`tests/test_us_rulespec_2026_11_05_mt_arm_37_78_420_successor.py` checks it.

## What it selects

This selector takes rulespec-us's corpus pin, `us-rulespec-2026-10-29-ecfr-section-text` (276 scopes;
rulespec-us `.axiom/toolchain.toml` on `main` at `fe62a527`), and swaps
`us-mt/regulation/2026-07-13-recovery` for its signed successor,
`us-mt/regulation/2026-07-13-recovery-r2026-09-27-chrome-free`
(`docs/ingest-runs/2026-09-27-us-mt-arm-37-78-420-successor.md`, #761). It keeps every other scope of
the pin, so it still selects 276, and it ingests nothing.

## Why

Each of the two scopes holds one row, ARM 37.78.420, Montana's TANF assistance standards. Locked
scopes keep their bytes, so a release picks up the clean row only by selecting the successor:

| | `2026-07-13-recovery` | `…-r2026-09-27-chrome-free` |
| --- | --- | --- |
| Kind, level | section, 2 | rule, 4 |
| Citation label | `rule-37-78-420` | `ARM 37.78.420` |
| Heading | none | TANF: ASSISTANCE STANDARDS; TABLES; METHODS OF COMPUTING AMOUNT OF MONTHLY BENEFIT PAYMENT |
| Body | 6,638 characters, opening with the rules.mt.gov page title and "Skip to main content" | 4,768 characters, opening at paragraph (1) |
| First-month post-employment standard | `$ 37 5` | `$ 375` |
| `expression_date`, `source_as_of` | 2026-07-13 | 2026-07-13 |

Both rows carry rule version 33678, the text in force on 2026-07-13. The retained policy JSON records
an end date of 2026-09-25 for that version and an effective date of 2026-09-26 for AMD 2026-529. No
scope on the pin carries the amended text, so this selector keeps Montana TANF at version 33678. The
2026-09-27 run note lists the amendment's ingest and the module's next version as follow-ups.

## Paths and rulespec-us impact

- The successor carries its predecessor's citation path, so selecting both would fail
  `duplicate_release_citation`; the selector drops the predecessor. A test asserts the equal path from
  the provisions files.
- rulespec-us `main` at `fe62a527` cites the path from one module,
  `us-mt/regulations/title-37/chapter-37-78/subchapter-37-78-4/rule-37-78-420.yaml`, and from its
  companion test, its encoding manifest and `.axiom/index/provisions_to_rules.json`.
- An active waiver covers that module (`known-validation-gaps.yaml`, fingerprint `sha256:7507f0c5…`,
  rulespec-us#782, expires 2026-12-21). The "Downstream" section of the 2026-09-27 run note records why
  the re-pin must update or remove it. This cut ran no rulespec-us validation against the successor;
  the re-pin's CI does.

## Checks

- The reproducer matches the committed selector byte for byte.
- The selector equals the pin apart from the swap, stays sorted, and never holds the predecessor with
  the successor. The test pins the swap as literals, so a change to the reproducer's constants cannot
  also change what the test checks.
- A lock file exists for the successor, the withdrawn-scope ledger does not list it, and the selector
  picks up no withdrawn scope the pin does not already select.
- It keeps the pin's three withdrawn scopes, `us-me`, `us-mi` and `us-mn` `statute/2026-07-13-recovery`.
  Allowances do not carry forward, so `manifests/withdrawn-scopes.yaml` records an exception for this
  selector on each and pins them to its digest (`a9cf3db1…`). rulespec-us#1365, which re-points the
  modules citing them, has not landed; the first cut in the line after it drops them.
- `axiom-corpus-ingest content-check` finds nothing in the successor, so
  `manifests/release-content-baseline.json` needs no entry for it.
- `scripts/publish_corpus.py --dry-run` passes and plans 276 scopes, 16,036 artifacts and 116,391
  provision rows, with no external writes.
- A Hypothesis property checks the swap rule over arbitrary bases, including bases where other pairs
  reuse the predecessor's and successor's version strings, as 40 pairs of the pin reuse
  `2026-07-13-recovery`. The reproducer refuses a base that lacks the predecessor, already holds the
  successor or repeats a scope. Nineteen mutants each fail the tests. Nine change the reproducer: swaps
  keyed on the version alone or the version plus one other field, no sort, each refusal removed, the
  predecessor kept beside the successor, and a cut on the older selector. Six change the selector and
  four the ledger.

`axiom-corpus-ingest validate-release --strict-warnings`, under the line's quality profile,
`complete-expression-dates-v1`:

| Selection | Errors | Warnings | Notices | `ok` |
| --- | ---: | ---: | ---: | --- |
| This selector | 0 | 541 | 34 | false |
| The pin | 0 | 541 | 35 | false |
| This selector's two `us-mt/regulation` scopes | 0 | 0 | 0 | true |
| The pin's two `us-mt/regulation` scopes | 0 | 0 | 1 | true |

Strict warnings fail both whole selectors on the same 541 `missing_parent_id` warnings, all in
`us-ca/regulation/2026-07-13-recovery`, and the two reports list those warnings identically. The
notices differ in two ways: this selector loses the pin's `baselined_content_findings` notice on the
predecessor, and its three withdrawn-scope notices cite this selector's exceptions in place of the
pin's. The publish gate runs without strict warnings.

## Coordination with #938

axiom-corpus#938 cuts `us-rulespec-2026-10-27-ks-liheap` (283 scopes) on the same pin. rulespec-us pins
one release, and `tests/test_selector_lineage_repository.py` rejects two unrecorded successors of one
selector, so whichever of the two merges second rebuilds on the other. That cut sets its `BASE_RELEASE`
to the selector that merged, reruns its reproducer, updates its expected count and re-records its digest
and the ME/MI/MN exceptions in `manifests/withdrawn-scopes.yaml`. If #938 merges second, its
`test_it_carries_everything_the_superseded_selector_added` must also list
`us-mt/regulation/2026-07-13-recovery`, since this swap drops it.

## After merge

1. Dispatch `publish.yml` with this release, then `mirror-release.yml`. Merging a selector does not
   publish it. **Publish only. Do not activate it.** rulespec-us pins this release; see
   `docs/named-release-publication.md`.
2. Re-pin rulespec-us to this release with the published `content_sha256`, and move its
   `axiom_corpus_ref` to a main commit at or after the release's signed provenance. Stage the Montana
   waiver's update or removal through rulespec-us's waiver route.
