# us-rulespec-2026-10-29-ecfr-section-text: release selector

Date: 2026-10-29. Selector `manifests/releases/us-rulespec-2026-10-29-ecfr-section-text.json`,
built by `scripts/repro/us_rulespec_2026_10_29_ecfr_section_text.py` and checked by
`tests/test_us_rulespec_2026_10_29_ecfr_section_text.py`.

## What it is

rulespec-us's corpus pin, `us-rulespec-2026-10-25-mt-separate-filing` (276 scopes; rulespec-us
`.axiom/toolchain.toml` on `main`), with three `us/regulation` scopes replaced by their eCFR
section-text successors. Each successor is signed and locked, and none is withdrawn:

| Replaces `us/regulation/…` | With `us/regulation/…` | Ingested |
| --- | --- | --- |
| `2026-06-18-title-47-part-54-r2026-07-15-self-contained` | `2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54` | `docs/ingest-runs/2026-10-29-ecfr-section-text-successors.md` (#944) |
| `2026-06-24-title-45-part-1302` | `2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302` | `docs/ingest-runs/2026-10-29-ecfr-section-text-successors.md` (#944) |
| `2026-07-13-recovery-r2026-07-17-dedup` | `2026-07-13-recovery-r2026-07-17-dedup-r2026-10-29-ecfr-section-text` | `docs/ingest-runs/2026-10-29-ecfr-section-text-assembled-successors.md` (#943) |

That keeps 276 scopes. Every other scope of the pin stays unchanged. These three are the only
scopes on the pin line that #832's rendering change affects; the union line's other affected scopes
(26 CFR 31 and part 1, 42 CFR 407, 423 and 447, 20 CFR 404 and 416) are not on the pin.

## Why

#832 makes the eCFR adapter keep table captions as `[Table caption: …]` blocks and separate words at
`<br/>` and block boundaries. Locked scopes keep their bytes, so a release picks up the fix only by
selecting successors. The successors change these bodies:

- **47 CFR 54**: four sections gain marked captions (54.505, 54.621, 54.1708, 54.2007). Native
  re-extraction also restores 16 source-backed bodies from earlier extractor repairs: note
  headings in 15 sections ("Effective Date Note" in 11, "Editorial Note" in 54.5 and 54.503,
  paragraph notes in 54.503, 54.626 and 54.715) and five formula and definition blocks in 54.303.
- **45 CFR 1302**: 1302.21 gains a marked caption, and the structure-only Overview placeholder at
  1302.1 now holds the section's paragraph text.
- **Recovery**: 7 CFR 246.10 gains four marked captions, and 42 CFR 457.555 separates a word at a
  line break. Every other recovery row keeps its body byte for byte; across all 1,073 rows only
  `version` and `source_path` change. axiom-corpus#942 lists 14 inherited omissions for a later
  round.

## Paths and rulespec-us impact

- Each successor carries exactly its predecessor's citation paths, so selecting both of a pair would
  fail `duplicate_release_citation`; the selector drops each predecessor. A test asserts the equal
  path sets from the provisions files.
- rulespec-us `main` at `8f893f23` cites none of the changed bodies. Its generated reverse index
  references 47 CFR 54.403 and 54.409 and 45 CFR 1302.12 in these scopes, and none of the recovery
  sections above. The re-pin's full CI remains the authoritative check.

## Checks

- The reproducer matches the committed selector byte for byte.
- The selector equals the pin with exactly the three swaps, sorted, and never holds a predecessor
  with its successor. The test pins the swaps as literals, so a change to the reproducer's constants
  cannot also change what is checked.
- Each successor is locked and not withdrawn, and the selector picks up no withdrawn scope the pin
  does not already select.
- It keeps the pin's three withdrawn scopes, `us-me`, `us-mi` and `us-mn` `statute/2026-07-13-recovery`.
  Allowances do not carry forward, so `manifests/withdrawn-scopes.yaml` records an exception for this
  selector on each, pinned to its digest (`444c008b…`). rulespec-us#1365, which re-points the modules
  citing them, has not landed; the first cut in the line after it drops them.
- A Hypothesis property checks the swap rule over arbitrary bases. A base that lacks a predecessor,
  already holds a successor or repeats a scope is refused. Six mutants of the reproducer and the
  registry (no sort, each refusal removed, swaps outside `us/regulation`, a missing exception) each
  fail the tests. The swap is limited to `us/regulation` because other jurisdictions reuse version
  strings such as `2026-07-13-recovery-r2026-07-17-dedup`.

## Coordination with #938

axiom-corpus#938 cuts `us-rulespec-2026-10-27-ks-liheap` on the same pin. rulespec-us pins one
release, so whichever of the two merges second rebuilds on the other: set its `BASE_RELEASE`
to the selector that merged, rerun its reproducer, update its expected count and re-record its digest
and the ME/MI/MN exceptions in `manifests/withdrawn-scopes.yaml`. If #938 merges second, its check that
only the older NYC Administrative Code capture leaves `us-rulespec-2026-10-23-ks-liheap` must also
list this release's three predecessors, since the swaps drop them, and its run note must say so.

## After merge

1. Dispatch `publish.yml` with this release, then `mirror-release.yml`. Merging a selector does not
   publish it. **Publish only. Do not activate it.** It is a pin release for rulespec-us; see
   `docs/named-release-publication.md`.
2. Re-pin rulespec-us to this release with the published `content_sha256`, and move its
   `axiom_corpus_ref` to a main commit at or after the release's signed provenance.
