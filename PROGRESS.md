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
- Ran that matrix against `a64ec806` and `1e0fde9b` with the same base/target
  `PYTHONPATH` isolation used by the official-source probe. Base result digest
  was `2794d2911d394e8d375ebe32ee03324e9ba1f720e1134b72adbfdc79dc49ff96`;
  target digest was
  `555d87d32acfead1f10e824a40ad9535fc9305400aeb63318e8adc8efe4022fc`.
- Target retained all three immediate colliding siblings and unique A/B/C
  branches both when each sibling had a distinct source `id` and when all
  lacked `id` and position fallback applied; base retained only the first/A.
  Reusing an `id` at different depths or beneath different parents did not
  collide, and identical printed section numbers in titles 26 and 42 produced
  disjoint paths.
- A synthetic same-parent duplicate `id` makes target drop the later unique
  branch because `_source_traversal_key` treats `id` as identity. This is
  invalid USLM input, not a retained-source blocker: a direct full-document
  census printed `id_occurrences=82680 unique_ids=82680 duplicates=0`, and the
  official USLM User Guide defines `id` as an XML Schema ID whose values are
  document-unique:
  `https://xml.house.gov/schemas/uslm/1.0/USLM-User-Guide.pdf`.
- Residual modeling limitation: the schema-valid repeal→reenact triplicate is
  fully retained before normalized emission and all unique A/B/C descendants
  survive, but citation-unique inventory/provision output intentionally keeps
  only the first colliding parent's heading/body (`Repealed`) rather than
  separately representing `Reenacted` and `Third enactment`. No retained Title
  26 collision group is repeal→reenact, so this is non-blocking for the
  reviewed official source.
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
- Re-ran the target-pinned history and scope checks. Target commit and tree are
  `1e0fde9ba3bb3a9cfaa90c16bff02326d4b8667a` and
  `91c0d556adcdb526cd52a1c9d5a077b424d3a5af`. The local comparison base is
  `origin/main` at `5b5ad3b83259e90b9452c1554eb8e3b759bd175d`.
  `git rev-list --count
  5b5ad3b83259e90b9452c1554eb8e3b759bd175d..1e0fde9b`
  reports seven PR-only commits. The a64→target delta contains the two exact
  linear commits requested and five files, not the prompt's literal six:
  `src/axiom_corpus/corpus/{usc,ecfr}.py`,
  `tests/test_corpus_{usc,ecfr}.py`, and the changelog fragment.
- `git log --format= --name-only
  5b5ad3b83259e90b9452c1554eb8e3b759bd175d..1e0fde9b |
  sort -u | rg '(^|/)(PROGRESS\.md|scratchpad|session)'` returned no paths.
  The same target-pinned diff contains no `.github/workflows`, `CODEOWNERS`,
  `pyproject.toml`, or `uv.lock` change.
- Both signed ingest manifests record
  `axiom_corpus_git.commit=afab29fc555af3d5bc25bba795e5b0c6ef936adc`;
  `git merge-base --is-ancestor <recorded> 1e0fde9b` returned 0 for each.
  Both record the committed command
  `uv run --extra dev python
  scripts/repro/us_1401_coordination_repair.py --base data/corpus`, and both
  signatures are `ed25519`, key `axiom-corpus-ingest-v1`, with 88-character
  values. Manifest SHA-256 values are statute
  `4c5569fbf37660441db6f8d2cffbd6a061da36c547d088a66a3f7f97b006fbe2`
  and regulation
  `56f7f5dc58046e9757e1b389f7dc1b69490b06a941fccdc6d57b6ae4f922796b`.
- Attempted the required exact reproduction command:
  `uv run --no-cache --extra dev python
  scripts/repro/us_1401_coordination_repair.py --base data/corpus`.
  It exited 1 before entering the script because sandboxed DNS could not fetch
  `fsspec` after three retries. The incomplete ignored `.venv` was moved to
  `/private/tmp/pr523-round4-1e0fde-failed-no-cache-venv`; a later failed uv
  probe created another ignored 76 KiB `.venv`. Neither changed tracked files.
- Ran the script itself with the target source and already-populated locked
  repository environment:
  `PYTHONPATH="$PWD/src"
  /Users/maxghenis/TheAxiomFoundation/axiom-corpus/.venv/bin/python
  scripts/repro/us_1401_coordination_repair.py --base data/corpus`.
  It exited 0 with statute 21/21 and 18 anchors plus regulation 2/2 and 12
  anchors. Pre/post SHA-256 comparison proved all eleven scoped artifacts
  byte-identical; the ordered-hash digest was
  `5e8c0646ab2015987725991f188b08af954f2bc7134c0ccf30a5b8fa43403b02`.
  Individual unchanged hashes were:
  ZIP `d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0`,
  USC XML
  `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621`,
  eCFR XML
  `1e5ca5d86df2ebf303d2df1eb9d162412e549896118779621d41139c9662001a`,
  statute inventory
  `014369a372affa906a3afc2ce058d96364e0e6f631bd5ec0bd49d33d1fb430bf`,
  regulation inventory
  `ed035858bb79b09e3bb83f6d7ed6f8893d3fbf9d6971df5bb1d844f0532213bb`,
  statute provisions
  `cda76f0ea15210b1df7a5800d985ddb6abc016b5e694ea5d35e60f0f01a36a54`,
  regulation provisions
  `73c1f3e656fefb1d9101cb6fd281654583f621be93224635af3bf199d6bbbc9b`,
  statute coverage
  `c4af9dbafd80857116ab94b5ac1a968abaaf4b7abce13cba0a85ddc6bb6ec7cc`,
  regulation coverage
  `2a3ecdfaaa2b7c92eab01bb4593c9622f29bbc726a8f3a2eb1358c0f823e861a`,
  statute anchors
  `b9bb848c6ea0901d54149aeab03cd210ed1fe385fdbdc28130166dac396f59ed`,
  and regulation anchors
  `c42504293a8528d240a5f470b01867f2fcceeab697f7786cf3baf280a89c3e7c`.
  `git diff --exit-code` passed afterward.
- Because network-blocked uv could not materialize this worktree's environment,
  all remaining gates used
  `PYTHONPATH="$PWD/src"
  /Users/maxghenis/TheAxiomFoundation/axiom-corpus/.venv/bin/<tool>` so that
  imports remained pinned to the exact target source. These exited 0:
  `ruff check .`; `towncrier check`;
  `python scripts/validate_citation_paths.py`;
  `axiom-corpus-ingest validate-release --base data/corpus --release
  manifests/releases/us-2026-07-24-1401-coordination-repair.json --max-issues
  100`; both `verify-scope-tracked` commands for the statute and regulation
  versions; both non-writing `coverage` commands with their exact scoped
  inventory/provision paths; `python -m pytest -q
  tests/test_corpus_usc.py tests/test_corpus_ecfr.py`; and
  `python -m pytest -q tests/test_provision_anchors.py`.
- Gate outcomes: citation validation checked 142,992 records / 124,467 unique
  paths with every ratchet exact; release validation reported two scopes and
  zero issues; tracked-scope checks reported five statute and four regulation
  files; coverage was 21/21 and 2/2; focused adapter tests were 56 passed; the
  resolver module was 16 passed and 20 data-dependent skips. A direct CLI
  resolver sweep over both anchor JSONLs resolved 30/30 exactly, including
  operative anchor `b5ca26f8-eb9f-5d11-b715-4df58e67143c` beneath
  `us/regulation/26/1/1401-1` at span `[2881,3299]`.
- Full test command
  `PYTHONPATH="$PWD/src"
  /Users/maxghenis/TheAxiomFoundation/axiom-corpus/.venv/bin/python -m pytest
  -q` exited 1 with exactly the expected known PostgreSQL-only failure,
  `tests/test_storage_postgres.py::
  TestPostgresStorageSubsectionConversion::test_dict_to_subsection`;
  totals were 1 failed, 4,108 passed, 69 skipped, 208 deselected, 37 warnings in
  140.85 seconds.
- The uncached CI mypy command
  `PYTHONPATH="$PWD/src"
  /Users/maxghenis/TheAxiomFoundation/axiom-corpus/.venv/bin/mypy
  --no-incremental src/axiom_corpus/corpus --ignore-missing-imports` exited 0
  on target and current `origin/main`: 89 files, zero issues on both. The
  prompt's older 180-error “full mypy” baseline could not be reproduced with
  the available installed environments. The system `mypy` 1.19.1 gave equal
  212 errors on target and current `origin/main` for the same focused path
  because development stubs were absent. Two exploratory broader invocations
  with the populated environment (`mypy src` and
  `mypy src/axiom_corpus`) exited 1 with 2,201 errors because they are outside
  the configured CI scope. A temporary incomplete `origin/main` archive
  invocation exited 1 with 161 errors and is not a valid parity result.
- One diagnostic `jq paths(...)` command exited 5 because it applied paths from
  the first manifest to a second JSON input. Direct `.axiom_corpus_git.commit`
  queries then succeeded and supplied the attestation results above.
- USC subreview recovered diagnostics: a guessed full `7e1c8ab9` SHA caused
  one invalid-revision exit; `git rev-parse` supplied the correct hash. One
  `npx --no-install gitnexus` attempt hung and was interrupted (130); a bare
  `python` shim and absent worktree `.venv/bin/python` each exited 127; a
  no-cache uv probe could not fetch `pyparsing`; a query without `--repo`
  exited 1; three private helpers were absent from the older registered graph;
  `apply_patch` rejected a temporary path; and two git diagnostics run from a
  non-repository exited 128. Correct-hash, cached-GitNexus, `/usr/bin/python3`,
  populated-repository-environment, target-local graph, permitted-temp-helper,
  and review-worktree retries succeeded. Initial temporary-probe Ruff found
  three auto-fixable import diagnostics; final formatted durable probes pass.
- Final staged GitNexus `detect_changes` over `PROGRESS.md` and the new
  `FINAL_REPORT.md` reported two changed files, five indexed review-ledger
  symbols, zero affected processes, and LOW risk. The new report is not present
  in the target-era graph; every mapped symbol belongs to `PROGRESS.md`.

## Next

- Hand off `REQUEST-CHANGES`; next repair should iterate direct sections
  alongside formal subparts and regression-test the real §1302.1 body.
