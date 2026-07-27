# PR #523 Round-7 Review Progress

## State

- Review worktree: `pr523-round7-df36df`
- Review branch: `codex/review-523-round7-df36df`
- PR target under review: `df36df25594e2cadf87910fec2bac6bfb21e39ba`
- Target parent: `49b0ae93367c48b7134576bf15a157c516d44a73`
- Status: independent ordering verification complete; no verdict yet

## Done

- Created a disposable worktree and throwaway review branch at the exact target.
- Confirmed the target has parent `49b0ae93367c48b7134576bf15a157c516d44a73`.
- Read the GitNexus PR-review workflow.
- Read the round-4 and round-6 final reports and the three required prior-round
  probes in full.
- Confirmed the round-7 target is exactly one non-merge commit atop round 6:
  `df36df25594e2cadf87910fec2bac6bfb21e39ba` has sole parent
  `49b0ae93367c48b7134576bf15a157c516d44a73`.
- Confirmed that one-commit delta modifies only
  `src/axiom_corpus/corpus/ecfr.py` and `tests/test_corpus_ecfr.py`
  (95 insertions, 30 deletions), and `git diff --check` passes.
- Reviewed the implementation diff. The sole production symbol changed is
  `iter_ecfr_title_provisions`: when formal subparts exist it now traverses
  immediate direct sections and formal subparts once in XML order, while the
  existing recursive no-formal-subpart path remains intact.
- Built a target-local GitNexus index at ledger commit `ae1f6fa9`:
  1,317 files, 20,155 nodes, 56,370 edges, 1,163 communities, 300 processes,
  and zero embeddings. The index is usable and `gitnexus status` reports it
  up to date.
- Ran GitNexus query, exact-delta detection, context, and upstream impact
  through the target-local `LocalBackend`. With tests included, the iterator
  has HIGH graph risk: 11 direct callers, 14 total upstream impacts, three
  affected modules, and two recovery processes. The three direct production
  callers are `_extract_one_title`, recovery `_ecfr_records`, and batch
  recovery `_parse`; the other eight direct callers are tests. Outgoing calls
  remain `_part_provision`, `_subpart_provision`, and `_section_provision`.
- Disclosed the HIGH graph result before creating review code. It reinforces
  the required ordering, recovery, focused, and full-suite gates; no production
  edit is being made by this review.
- GitNexus analysis exited 1 only after creating the complete local index
  because sandbox policy denied the optional global-registry write at
  `/Users/maxghenis/.gitnexus/registry.json`. Direct target-local graph calls
  succeeded.
- Added the review-owned, assertion-based
  `review-probes/ecfr_document_order_probe.py`. It uses four fixtures authored
  independently of the PR regression: direct section before a subpart, direct
  section after a subpart, direct section between two subparts, and duplicate
  §913.7 first inside subpart A then directly under the part.
- The independent probe passed exact record order, parent citation paths,
  levels, subpart metadata, and distinctive body-marker checks for every
  emitted section. Both duplicate occurrences are emitted in source order with
  the subpart body/parent first and direct body/parent second. Canonical result
  SHA-256:
  `0163acc589517c57338bf1181d7ff8f0b9c85c0d00d32023b2212f69972147cd`.
- Ruff and bytecode compilation pass for the independent probe.
- The first probe execution failed because the review oracle incorrectly
  expected `metadata.subpart=None` on subpart records; the adapter correctly
  returned `A`/`B`. Correcting only those expected metadata values made all
  assertions pass.

## Next

- Re-run the required prior-round probes and invariants.
- Run focused and repository-wide gates.
- Write and commit `FINAL_REPORT.md` with the final verdict and evidence digest.
