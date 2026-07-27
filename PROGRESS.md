# PR #523 Round-7 Review Progress

## State

- Review worktree: `pr523-round7-df36df`
- Review branch: `codex/review-523-round7-df36df`
- PR target under review: `df36df25594e2cadf87910fec2bac6bfb21e39ba`
- Target parent: `49b0ae93367c48b7134576bf15a157c516d44a73`
- Status: probes, history, and reproduction invariants complete; no verdict yet

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
- Re-ran round 6's exact `ecfr_delta_adversarial_probe.py` against
  `data/corpus/sources/us/regulation`. All four cases have identical entry
  multisets, exact document order, and all section bodies present. The retained
  census covers seven XML files and has zero direct-after-subpart, empty
  subpart, reserved-empty-subpart, or cross-placement-duplicate hits. Result
  SHA-256:
  `d9aa3da58e82fb47d67464c8662a65ffa8b42e7560254172331e8af00b905f58`.
- Re-ran round 4's exact `ecfr_parentage_probe.py scan` against the same source
  root. Across seven XML files and 3,764 section occurrences, source,
  inventory, and iterator each contain 3,501 unique paths; missing sections,
  inventory parent mismatches, and iterator parent mismatches are all zero.
  Result SHA-256:
  `384c4609027843ef2bc4d84e5966d72ae5ece438ab6f2add125a1d77bd95258c`.
- Re-ran round 4's exact `usc_official_probe.py` against the retained official
  Title 26 XML. Source and traversal each contain 58,368 structural
  occurrences; the independently derived source, inventory, and provisions
  each contain exactly 58,351 unique paths, with exact sets and order and no
  missing or extra path. Source SHA-256:
  `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621`;
  canonical result SHA-256:
  `db983eade28d34b2b44657ccb31ef84fdf9afd065f858f6776e8c2dcd56ef7b9`.
- Pinned delta hygiene to the PR target rather than this review branch. The
  round-7 delta is exactly one commit, zero merges, with sole parent
  `49b0ae93367c48b7134576bf15a157c516d44a73`, and its only paths are
  `src/axiom_corpus/corpus/ecfr.py` and `tests/test_corpus_ecfr.py`.
- The complete target-pinned PR-only history
  `a64ec80693ad37f56ab9f1ea5102c4998b9c01d9..df36df25594e` contains five
  commits and exactly five unique paths: the eCFR and USC modules, their two
  test modules, and `changelog.d/usc-1401-coordination-repair.fixed.md`.
  It contains zero progress, report, review-probe, scratch, or session paths.
- `git merge-base --is-ancestor
  afab29fc555af3d5bc25bba795e5b0c6ef936adc df36df25594e` exited 0, and
  the merge base is exactly the attested commit.
- Both Ed25519 ingest manifests remain complete, clean-tracked attestations of
  `afab29fc555af3d5bc25bba795e5b0c6ef936adc` (statute 21/21 and regulation
  2/2). Their SHA-256 values remain
  `4c5569fbf37660441db6f8d2cffbd6a061da36c547d088a66a3f7f97b006fbe2`
  and
  `56f7f5dc58046e9757e1b389f7dc1b69490b06a941fccdc6d57b6ae4f922796b`.
- Captured SHA-256 values for all eleven scoped source, inventory, provision,
  coverage, and anchor artifacts before reproduction. Their ordered full-line
  digest was
  `5e8c0646ab2015987725991f188b08af954f2bc7134c0ccf30a5b8fa43403b02`,
  and the target-pinned artifact diff was initially empty.
- The exact requested
  `uv run --no-cache --extra dev python
  scripts/repro/us_1401_coordination_repair.py --base data/corpus` wrapper
  exited 1 before entering the script because sandboxed DNS could not download
  `pycparser==2.23`. It created an ignored incomplete worktree `.venv`; the
  failed attempt changed none of the eleven artifacts.
- Ran the committed repro through the populated root environment with this
  target's `src` first on `PYTHONPATH`. It exited 0: statute coverage is 21/21
  with 18 anchors, and regulation coverage is 2/2 with 12 anchors.
- Every post-repro artifact hash exactly matches its pre-repro hash. The
  ordered digest remains
  `5e8c0646ab2015987725991f188b08af954f2bc7134c0ccf30a5b8fa43403b02`,
  and `git diff --exit-code df36df25 -- <all eleven artifacts>` exits 0.

## Next

- Run focused and repository-wide gates.
- Run focused and repository-wide gates.
- Write and commit `FINAL_REPORT.md` with the final verdict and evidence digest.
