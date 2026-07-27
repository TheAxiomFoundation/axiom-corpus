# PR #523 Round-6 Blind Delta Review

## State

- Verdict: `REQUEST-CHANGES` candidate, pending completion of all gates.
- Target PR head:
  `49b0ae93367c48b7134576bf15a157c516d44a73`.
- Target parent:
  `7defeda51f1631ea9abec2409e2af35f304e0b85`.
- Settled round-4 target:
  `1e0fde9ba3bb3a9cfaa90c16bff02326d4b8667a`.
- Review branch: `codex/review-523-round6-49b0ae`.
- Review worktree:
  `/Users/maxghenis/TheAxiomFoundation/axiom-corpus/.git/review-worktrees/pr523-round6-49b0ae`.
- Mode: blind, delta-scoped review only; no PR-branch, remote, GitHub, or
  publication writes.
- Blocking state: MEDIUM candidate. In a valid mixed part whose direct section
  follows a formal subpart in XML order, the target emits every direct section
  before every subpart. Presence, body, and parentage are correct, but raw
  provision order no longer matches the official document. The iterator's two
  recovery callers consume that order directly.

## Done

- Read `/Users/maxghenis/.agents/skills/gitnexus-pr-review/SKILL.md`.
- Read `/Users/maxghenis/.agents/skills/gitnexus-cli/SKILL.md`.
- Read the complete round-4 `FINAL_REPORT.md`, `PROGRESS.md`, and all three
  durable probes under
  `/Users/maxghenis/TheAxiomFoundation/axiom-corpus/.git/review-worktrees/pr523-round4-1e0fde/review-probes/`.
- Confirmed the requested target resolves locally as a commit.
- Confirmed the target commit metadata:
  parent `7defeda51f1631ea9abec2409e2af35f304e0b85`, tree
  `ea61a8a8ebf3d637526399abb6944b8ae67dbc58`, and subject
  `fix: iterate direct sections in mixed eCFR parts`.
- Created this disposable worktree and throwaway local branch directly from the
  exact requested target:
  `git worktree add -b codex/review-523-round6-49b0ae
  /Users/maxghenis/TheAxiomFoundation/axiom-corpus/.git/review-worktrees/pr523-round6-49b0ae
  49b0ae93367c48b7134576bf15a157c516d44a73`.
- Committed the initial ledger at
  `ed2a575537823e9fc35cf53449a8dc6024660ddb`; its sole parent is the exact
  target.
- Confirmed the target is exactly two linear, non-merge commits atop round 4:
  `7defeda51f1631ea9abec2409e2af35f304e0b85` (test only), followed by
  `49b0ae93367c48b7134576bf15a157c516d44a73` (implementation only).
  The first modifies only `tests/test_corpus_ecfr.py`; the second modifies only
  `src/axiom_corpus/corpus/ecfr.py`. The combined binary-diff SHA-256 is
  `49a6b7d0d0656bafc668b737d7838cb45b61b7d36e1e30c19bd10deafa0326bc`;
  `git diff --check` passed.
- Confirmed the four-commit PR-only range
  `a64ec80693ad37f56ab9f1ea5102c4998b9c01d9..49b0ae93367c48b7134576bf15a157c516d44a73`
  contains exactly five paths: the eCFR and USC modules, their two test
  modules, and the USC changelog fragment. No progress, report, scratch, or
  session path occurs anywhere in that target-pinned history.
- Confirmed
  `git merge-base --is-ancestor
  afab29fc555af3d5bc25bba795e5b0c6ef936adc
  49b0ae93367c48b7134576bf15a157c516d44a73` exits 0 and the exact merge base
  is the attested commit.
- The GitNexus MCP tools were unavailable. The cached local CLI was therefore
  used according to the GitNexus CLI skill. `gitnexus analyze` built a usable
  target-local index at ledger commit `ed2a5755` (1,317 files, 20,140 nodes,
  56,359 edges, 1,149 communities, 300 processes), but sandbox policy denied
  its write to `/Users/maxghenis/.gitnexus/registry.json`; the hung process was
  interrupted after index completion. Initial CLI impact/context/query calls
  without an explicit repository then exited 1 because the global registry
  contains multiple repositories.
- Queried the target-local index directly through GitNexus `LocalBackend`.
  `iter_ecfr_title_provisions` has LOW upstream risk: three direct production
  callers (`_extract_one_title`, recovery `_ecfr_records`, and batch recovery
  `_parse`), six total upstream impacts, two affected recovery processes, and
  direct test coverage. Its outgoing calls are `_part_provision`,
  `_subpart_provision`, and `_section_provision`.
- Re-ran round 4's own `ecfr_parentage_probe.py scan` at the target. Across all
  seven retained canonical part XMLs, 3,764 section occurrences and 3,501
  unique paths, source, inventory, and iterator each have all 3,501 unique
  paths. Missing iterator sections, inventory parent mismatches, and iterator
  parent mismatches are all empty. Result SHA-256:
  `384c4609027843ef2bc4d84e5966d72ae5ece438ab6f2add125a1d77bd95258c`.
- Re-ran round 4's own `usc_official_probe.py` at the target. The official XML
  SHA-256 remains
  `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621`.
  The independent source derivation, adapter traversal, inventory, and
  provision output remain 58,368 structural occurrences and exactly 58,351
  unique paths; inventory and records exactly match the official set and order
  with no missing or extra path. Canonical full-result SHA-256:
  `db983eade28d34b2b44657ccb31ef84fdf9afd065f858f6776e8c2dcd56ef7b9`.
- Added `review-probes/ecfr_delta_adversarial_probe.py`; Ruff and bytecode
  compilation pass. Against the target, its result SHA-256 is
  `c60fe29732fa3016d7dae50390328b1ae75bf3c513d0823b83127e0e90c805ad`.
  Against the pre-fix parent its result SHA-256 is
  `fc6fd558cfb100142197a7a80ce8f2a8bde099dce52de2b68e5d69607b0c91fb`.
- The target fixes presence, body, and parentage in the synthetic
  direct-after-subpart and empty/reserved-subpart cases. A part with no formal
  subparts retains the old recursive, source-order behavior exactly. The seven
  retained XMLs contain one mixed part (45 CFR part 1302), one
  no-formal-subpart control (26 CFR part 1), zero direct sections after a
  formal subpart, zero empty/reserved formal subparts, and zero duplicate
  section paths across direct and subpart placements.
- **MEDIUM candidate:** the direct-after fixture's official sequence is
  part → subpart A → §900.1 → direct §900.2 → subpart B → §900.3, while the
  target yields part → direct §900.2 → subpart A → §900.1 → subpart B →
  §900.3. The empty/reserved-subpart fixture is reordered the same way. The new
  committed regression uses retained §1302.1, which precedes every subpart, so
  it cannot detect this. A synthetic cross-placement duplicate is likewise
  emitted direct-first then subpart; no such duplicate exists in retained
  scope. Final `extract_ecfr` rebuilds output in inventory order, but both
  recovery parsers use the raw iterator order to construct inventory and
  provisions.
- Tool-call failure: the first attempt to expand this ledger used an
  `apply_patch` context that did not exactly match the wrapped worktree path;
  it exited without changing the file. This full-file replacement succeeded.

## Next

- Commit the adversarial probe and this expanded ledger.
- Reproduce all eleven artifacts and execute the required gates.
- Commit the completed ledger and `FINAL_REPORT.md`, then report the verdict.
