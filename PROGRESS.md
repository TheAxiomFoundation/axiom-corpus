# PR #523 Round-4 Blind Adversarial Re-review

## State

- Verdict: `REQUEST-CHANGES`
- Target PR head: `1e0fde9ba3bb3a9cfaa90c16bff02326d4b8667a`
- Target parent: `7e1c8ab9b5efffa104841ce49fa42a30f63268b6`
- Round-3 target: `a64ec80693ad37f56ab9f1ea5102c4998b9c01d9`
- Review branch: `codex/rereview-523-round4-1e0fde`
- Review worktree:
  `/Users/maxghenis/TheAxiomFoundation/axiom-corpus/.git/review-worktrees/pr523-round4-1e0fde`
- Mode: review only; no PR-branch, remote, GitHub, or publication writes
- Blocking state: MEDIUM retained mixed-part eCFR iteration omits direct
  §1302.1, causing a false structure-only body and making the required
  hierarchy/iterator agreement invariant fail.

## Done

- Read `/Users/maxghenis/.agents/skills/gitnexus-pr-review/SKILL.md`.
- Read `/Users/maxghenis/.agents/skills/gitnexus-cli/SKILL.md` before building
  the target-local graph.
- Read the round-3 ledger at
  `/Users/maxghenis/TheAxiomFoundation/axiom-corpus/.git/review-worktrees/pr523-round3-a64ec/PROGRESS.md`.
- Resolved the requested target with:
  `git cat-file -t 1e0fde9ba3bb3a9cfaa90c16bff02326d4b8667a`
  (`commit`).
- Confirmed the target's parent with:
  `git show -s --format='%H%n%P%n%T%n%s' 1e0fde9ba3bb3a9cfaa90c16bff02326d4b8667a`.
- Created this disposable worktree and throwaway local branch directly from the
  exact requested commit:
  `git worktree add -b codex/rereview-523-round4-1e0fde
  /Users/maxghenis/TheAxiomFoundation/axiom-corpus/.git/review-worktrees/pr523-round4-1e0fde
  1e0fde9ba3bb3a9cfaa90c16bff02326d4b8667a`.
- Tool-call failure: the first `git worktree add` invocation never started
  because its process working directory was the not-yet-created worktree
  (`No such file or directory`). It changed nothing; the retry above succeeded
  from the repository root.
- Committed this ledger at
  `1f11b33a498c5b8dfe7d67e823dd765c199cc084`; its sole parent is the exact
  target commit.
- Confirmed the round-4 delta is exactly two linear commits:
  `7e1c8ab9b5efffa104841ce49fa42a30f63268b6` (USC) and
  `1e0fde9ba3bb3a9cfaa90c16bff02326d4b8667a` (eCFR).
- Ran
  `git diff --name-status a64ec80693ad37f56ab9f1ea5102c4998b9c01d9..1e0fde9ba3bb3a9cfaa90c16bff02326d4b8667a`.
  The delta is five files: two source modules, two test modules, and one
  changelog fragment. This matches the requested categories but not the
  request's literal `6 files` count.
- `npx gitnexus --help` produced no output for 35 seconds, likely while trying
  unavailable network/package resolution, and was interrupted with exit 130.
  The cached standalone `gitnexus` binary was used instead.
- `gitnexus analyze` parsed the target worktree and wrote a usable ignored
  local index, but the sandbox blocked registration at
  `/Users/maxghenis/.gitnexus/registry.json` with `EPERM`; the hung process was
  then interrupted with exit 130. `gitnexus status` nevertheless reports the
  local index up to date at review-ledger commit `1f11b33a`: 1,317 files,
  20,154 nodes, 56,362 edges, 1,164 communities, and 300 processes.
- The first CLI graph-query batch failed with exit 1 because several registered
  repositories made the missing `--repo` argument ambiguous. No query result
  from that failed batch was counted.
- Used the worktree-local graph directly through GitNexus's `LocalBackend`,
  pinned to this worktree's `.gitnexus/lbug`, to run `detect_changes`, context,
  and upstream impact analysis. Exact-delta detection reported 5 files and 81
  indexed symbols. `build_usc_inventory_from_xml` is HIGH risk (15 direct,
  29 total, 2 processes); `iter_usc_title_provisions` is MEDIUM (12 direct,
  26 total, 2 processes); `_iter_sections` is MEDIUM (1 direct, 36 total,
  2 processes). The remaining changed traversal helpers and
  `_scoped_structure_from_part_xml` were LOW in the graph. Direct USC callers
  include CLI extraction, directory extraction, source slimming, and recovery
  scripts.
- Created the independent, review-owned
  `review-probes/usc_official_probe.py`. It derives the official structural
  identifier/path set directly from retained XML, inventories sibling
  collisions without adapter helpers, walks pre-output adapter objects, compares
  exact inventory/provision path sets, and isolates §45X(d)(4). Ruff formatting,
  Ruff checking, and bytecode compilation pass for the probe.
- Sandbox failure: `apply_patch` rejected the first attempt to create that
  probe under `/private/tmp/pr523-round4-main.PMpyfX`, so no file was created
  there. The durable probe above was created inside this review worktree.
- Extracted the exact round-3 `src/axiom_corpus` tree without checkout using
  `git archive a64ec80693ad37f56ab9f1ea5102c4998b9c01d9
  src/axiom_corpus | tar -x -C
  /private/tmp/pr523-round4-main.PMpyfX/base`, then ran the same independent
  probe with that tree first on `PYTHONPATH` and with the target tree first on
  `PYTHONPATH`.
- Independent retained-OLRC reproduction:
  `PYTHONPATH=<base-or-target>/src
  /Users/maxghenis/TheAxiomFoundation/axiom-corpus/.venv/bin/python
  review-probes/usc_official_probe.py
  data/corpus/sources/us/statute/2026-07-24-1401-coordination-repair-title-26/uslm/usc26.xml`.
  The input is 55,856,053 bytes with SHA-256
  `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621`.
- The probe independently found 58,368 structural source occurrences and
  58,351 unique official identifiers/citation paths. It found 16 duplicated
  identifiers (17 excess occurrences), 13 immediate-sibling identifier
  collision groups, all pairs, and zero duplicate official `id` attributes.
  Thus there are no retained triplicate identifier siblings and no official
  source-identity collisions.
- At `a64ec806`, the adapter traversed/emitted only 58,347 paths. The exact
  four missing official paths were `us/statute/26/45X/d/4/A`,
  `.../A/i`, `.../A/ii`, and `.../B`; only the first §45X(d)(4) paragraph
  survived pre-output traversal.
- At `1e0fde9b`, pre-output traversal retained all 58,368 structural
  occurrences, including both §45X(d)(4) paragraphs and all four unique
  descendants. Inventory and provision iteration each emitted exactly 58,351
  unique paths, in the same order, and each path set was exactly equal to the
  independently derived official source set. This independently verifies the
  corrected 58,351 total rather than trusting the repair tests.
- Created `review-probes/usc_collision_matrix_probe.py` to exercise true
  immediate-sibling triplicates with unique source IDs and with position
  fallback, repeal→reenact ordering, repeated IDs at different depths/parents,
  invalid duplicate XML IDs, and cross-title path isolation. Ruff formatting,
  Ruff checking, and bytecode compilation pass.
- Created the independent, review-owned
  `review-probes/ecfr_parentage_probe.py`. Its `case` mode derives a selected
  section's formal-subpart parent directly from retained XML and compares
  hierarchy, inventory, iterator, and optional end-to-end extraction; `scan`
  exhausts every retained part XML; `synthetic` exercises non-DIV6 subparts,
  parts without formal subparts, and unselected subparts. Ruff formatting,
  Ruff checking, and bytecode compilation pass.
- Independently reproduced the round-3 eCFR defect with retained official
  `data/corpus/sources/us/regulation/2026-06-24-title-45-part-1302/ecfr/title-45-part-1302.xml`
  (SHA-256
  `1dc1b061cbb4b7ebb342b374ad58fdf6c66f118a39299b0e08b3bdb0e225e4b2`)
  and selector `1302.10`:
  `PYTHONPATH=<base-or-target>/src
  /Users/maxghenis/TheAxiomFoundation/axiom-corpus/.venv/bin/python
  review-probes/ecfr_parentage_probe.py case <xml> --title 45 --part 1302
  --section 1302.10 --extract`.
- At `a64ec806`, scoped hierarchy/inventory flattened §1302.10 under the part
  at level 1 while the iterator emitted it at level 2 beneath absent
  `subpart-A`; the independent result digest was
  `33b86059cdeb54000dc547d74a5f1a6a5ffe6e3a7a38cbca632d71d9a781fdb0`.
  At `1e0fde9b`, hierarchy, inventory, iterator, and extraction agree on
  part → subpart A → §1302.10 at levels 0/1/2, with body present and no
  dangling parent; result digest
  `dfac703cf86df44edb624ba1f186b424fe7a49c9d3e676f4558fcb10de39a413`.
  The stated round-3 eCFR defect is therefore fixed.
- **MEDIUM finding:** the same retained part contains direct §1302.1 before
  ten formal DIV6 subparts. The repaired scoped hierarchy correctly places it
  directly under the part, but `iter_ecfr_title_provisions` enters its
  `subpart_divs` branch and `continue`s after iterating subpart sections,
  skipping every direct section. The independent target command above with
  `--section 1302.1 --extract` found inventory
  `[us/regulation/45/1302, us/regulation/45/1302/1]` but iterator
  `[us/regulation/45/1302]`; result digest
  `4cc7dc7c48519493bab1e9d75f46488c94843841b5ed5f54baa3f413da455de0`.
  End-to-end extraction misleadingly reports complete coverage by manufacturing
  §1302.1 with `body=None`, `structure_only=true`, and
  `body_status=not_in_ecfr_full_xml`, even though the retained XML contains its
  text. The same digest at `a64ec806` confirms this is pre-existing, but it
  directly violates the requested round-4 retained-scope invariant and leaves
  the eCFR repair incomplete.
- Exhaustively ran target probe mode
  `ecfr_parentage_probe.py scan data/corpus/sources/us/regulation`.
  Across all 7 retained canonical part XML files, 3,764 section occurrences,
  and 3,501 unique section paths, hierarchy/inventory exactly matched
  independently derived source parents. Iterator output had 3,500 unique
  sections, zero parent mismatches among those emitted, and exactly one missing
  path: `us/regulation/45/1302/1`. All 78 retained formal subparts were direct
  `DIV6` children; the only retained no-subpart part (26 CFR part 1) passed.
  One mixed direct-section/formal-subpart part exists, and it is the failing
  45 CFR part 1302. Scan result digest:
  `03abab761762002fcfc586a59a2d5210632ff8a89e7f0f46a727cd423d950ac1`.
- Target synthetic eCFR probe result
  `43b4dca61a6879debd519e536b2842ef285c8643771390b93abb9fd2e4c2461b`
  confirms a non-DIV6 `TYPE=SUBPART` variant is consistently flattened by both
  hierarchy and iterator, a part with only `DIV6 TYPE=SUBJGRP` agrees at the
  part parent, and selecting subpart A emits neither unselected subpart B nor
  its section. No retained non-DIV6 formal-subpart variant exists.

## Next

- Run all requested invariants and local gates.
- Commit each coherent evidence update and the final report.
