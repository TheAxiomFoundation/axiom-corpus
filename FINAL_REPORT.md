VERDICT: REQUEST-CHANGES

Target reviewed:
`49b0ae93367c48b7134576bf15a157c516d44a73` (tree
`ea61a8a8ebf3d637526399abb6944b8ae67dbc58`) in disposable worktree
`/Users/maxghenis/TheAxiomFoundation/axiom-corpus/.git/review-worktrees/pr523-round6-49b0ae`.
No PR-branch, remote, GitHub, publication, or production-data write was made.

## Blocking finding

1. **MEDIUM — the mixed-part fix reorders direct sections that follow formal
   subparts.** At `src/axiom_corpus/corpus/ecfr.py:1179`, the target gathers
   every immediate direct `DIV8` and yields those sections before entering the
   formal-subpart loop at line 1206. For valid mixed XML ordered as:

   ```text
   part → subpart A → §900.1 → direct §900.2 → subpart B → §900.3
   ```

   the target yields:

   ```text
   part → direct §900.2 → subpart A → §900.1 → subpart B → §900.3
   ```

   Presence, real bodies, parent paths, and levels are correct. The defect is
   order: the iterator no longer preserves official XML order for the explicit
   direct-after-subpart adversary.

   This is durable rather than cosmetic. `scripts/recover_ingest.py` and
   `scripts/recover_ingest_batch.py` construct inventory and provision lists
   directly from iterator order. The main extractor also folds iterator output
   by citation path in iteration order. A synthetic duplicate §903.1 placed
   first in a subpart and later directly under the part is emitted direct-first
   then subpart, so the subpart body/parent wins instead of the later official
   direct occurrence. No such duplicate exists in the retained scope, but it
   demonstrates that the ordering change can alter normalized content.

   The new committed regression covers official §1302.1, whose direct section
   appears before all ten formal subparts, so it cannot catch the requested
   after-subpart case. The review-owned adversarial probe result SHA-256 is
   `c60fe29732fa3016d7dae50390328b1ae75bf3c513d0823b83127e0e90c805ad`;
   the pre-fix-parent result is
   `fc6fd558cfb100142197a7a80ce8f2a8bde099dce52de2b68e5d69607b0c91fb`.

   Repair should traverse a mixed part's immediate children once in XML order,
   processing direct sections and formal subparts in place, while retaining the
   existing recursive no-formal-subpart branch. Add direct-after-subpart,
   direct-after-empty/reserved-subpart, and only-direct controls.

## Round-4 probe re-runs

- **The retained eCFR omission is fixed.** Round 4's own full retained-scope
  `ecfr_parentage_probe.py scan` found seven canonical XMLs, 3,764 section
  occurrences, and 3,501 unique paths. Source, inventory, and iterator each
  contain all 3,501 paths. Missing iterator sections, inventory parent
  mismatches, and iterator parent mismatches are all empty. Digest:
  `384c4609027843ef2bc4d84e5966d72ae5ece438ab6f2add125a1d77bd95258c`.
- The focused end-to-end §1302.1 case agrees on
  `us/regulation/45/1302` parent and level 1, extracts a real body, has no
  structure-only/body-status marker, and reports complete coverage. Digest:
  `7efe47ca396b8eda364c245d2a6a1f9806a81bb75ba8325492a318ecac52522b`.
- **USC remains unchanged and exact.** Round 4's own independent official
  probe derived 58,368 structural occurrences and exactly 58,351 unique
  official paths. Traversal retains all occurrences; inventory and provisions
  each contain 58,351 unique paths and exactly match the official path set and
  order, with no missing or extra path. Official XML SHA-256:
  `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621`;
  canonical full-result SHA-256:
  `db983eade28d34b2b44657ccb31ef84fdf9afd065f858f6776e8c2dcd56ef7b9`.

## Delta-only adversarial disposition

- Direct-after-subpart: all entries/bodies/parents recovered, but document
  order fails as described above.
- Reserved and empty subparts followed by a direct section: all entries are
  emitted, but the later direct section is moved before both subparts.
- No-formal-subpart/only-direct control: unchanged recursive behavior, correct
  parents and bodies, and exact document order.
- Cross-placement duplicate characterization: target emits both occurrences
  but reverses their official placement order. The seven retained XMLs contain
  zero duplicate section paths across direct and subpart placement.
- Retained census: the only mixed part is 45 CFR part 1302; its direct §1302.1
  precedes all subparts. Retained scope contains zero direct-after-subpart
  cases and zero empty/reserved formal subparts, so all retained files preserve
  order despite the general defect.

## History, scope, and blast radius

- The target is exactly two linear non-merge commits atop
  `1e0fde9ba3bb3a9cfaa90c16bff02326d4b8667a`:
  `7defeda51f1631ea9abec2409e2af35f304e0b85` modifies only
  `tests/test_corpus_ecfr.py`, then
  `49b0ae93367c48b7134576bf15a157c516d44a73` modifies only
  `src/axiom_corpus/corpus/ecfr.py`. Combined binary-diff SHA-256:
  `49a6b7d0d0656bafc668b737d7838cb45b61b7d36e1e30c19bd10deafa0326bc`.
- Target-pinned PR-only history
  `a64ec80693ad37f56ab9f1ea5102c4998b9c01d9..49b0ae93` contains only the
  eCFR/USC modules, their tests, and the USC changelog fragment. It contains no
  progress, report, scratch, or session path.
- Both signed manifests still attest
  `afab29fc555af3d5bc25bba795e5b0c6ef936adc`; the exact requested
  `git merge-base --is-ancestor afab29fc HEAD` check exited 0. Manifest hashes
  remain
  `4c5569fbf37660441db6f8d2cffbd6a061da36c547d088a66a3f7f97b006fbe2`
  and
  `56f7f5dc58046e9757e1b389f7dc1b69490b06a941fccdc6d57b6ae4f922796b`.
- Target-local GitNexus impact is LOW: three direct production callers, six
  total upstream impacts, and two affected recovery processes. The direct
  callers are `_extract_one_title`, recovery `_ecfr_records`, and batch
  recovery `_parse`.

## Reproduction and gates

- The committed reproduction script exited 0 through the populated locked
  repository environment with target-first source: statute 21/21 plus 18
  anchors and regulation 2/2 plus 12 anchors. All eleven artifacts were
  byte-identical before and after. Their ordered hash digest remained
  `5e8c0646ab2015987725991f188b08af954f2bc7134c0ccf30a5b8fa43403b02`;
  target-pinned artifact diff was empty.
- Focused USC/eCFR tests: 57 passed.
- Full pytest: exactly 4,109 passed, 69 skipped, 208 deselected, and the sole
  expected PostgreSQL failure
  `TestPostgresStorageSubsectionConversion::test_dict_to_subsection`.
- Ruff and Towncrier: pass.
- Mypy required scope: zero issues in 89 source files.
- Citation validation: 142,992 records, 124,467 unique paths, all ratchets
  exact.
- Release validation: two scopes, zero issues, errors, or warnings.
- Tracked-scope checks: five statute files and four regulation files.
- Coverage: statute 21/21 and regulation 2/2, with no missing, extra, or
  duplicate paths.
- Resolver tests: 16 passed, 20 data-dependent skips; direct CLI sweep 30/30
  exact.

## Tool and sandbox failures

- The GitNexus MCP tools were unavailable. The local CLI built a usable
  target-local index, but sandbox policy denied its global registry write at
  `/Users/maxghenis/.gitnexus/registry.json`; the hung process was interrupted
  after local index completion. Initial CLI queries without explicit repo
  selection failed because multiple repositories are registered; direct
  target-local backend calls then succeeded.
- The exact no-cache uv wrapper exited 1 before entering the reproduction
  script because sandboxed DNS could not fetch locked `jiter==0.12.0`. It left
  an ignored incomplete `.venv`; the failed attempt changed none of the eleven
  artifacts. The populated locked-environment fallback above ran the committed
  script successfully.
- A diagnostic used GNU-style `diff --exit-code`, unsupported by macOS
  `diff`, and exited 2. The `cmp -s` retry proved byte identity.
- One `apply_patch` attempt used stale wrapped-line context and exited without
  changing the ledger; a full-file replacement succeeded.

The committed `PROGRESS.md` is the command-level ledger, and
`review-probes/ecfr_delta_adversarial_probe.py` is the durable delta-only
adversarial probe.
