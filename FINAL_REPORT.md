VERDICT: APPROVE

Target reviewed:
`df36df25594e2cadf87910fec2bac6bfb21e39ba` (tree
`3c3d15bd69c6024ff7788f42d1cdfe616714b5a4`) in disposable worktree
`/Users/maxghenis/TheAxiomFoundation/axiom-corpus/.git/review-worktrees/pr523-round7-df36df`.
No PR-branch, remote, GitHub, publication, or production-data write was made.

## Decision

No blocking finding remains in the round-7 delta. The one-pass mixed-part walk
preserves official XML order while retaining correct direct-section and
subpart-section hierarchy and bodies. The round-6 ordering defect is fixed,
the prior-round eCFR and USC invariants remain exact, and all required gates
are within their expected envelopes.

## Independent ordering verification

- The review-owned, assertion-based
  `review-probes/ecfr_document_order_probe.py` uses fixtures independent of the
  PR regression for a direct section before a subpart, after a subpart, between
  two subparts, and duplicate §913.7 first inside subpart A then directly
  beneath the part.
- Every fixture matches document order exactly. Direct sections have the part
  parent at level 1; subpart sections have the subpart parent at level 2; all
  distinctive body markers match. Both duplicate occurrences are emitted in
  source order with the correct body and parent at each position.
- Independent result SHA-256:
  `0163acc589517c57338bf1181d7ff8f0b9c85c0d00d32023b2212f69972147cd`.
- Round 6's own adversarial probe now reports identical entry multisets, exact
  document order, and all bodies present in all four cases. Its seven-file
  retained census has zero direct-after-subpart, empty-subpart,
  reserved-empty-subpart, or cross-placement-duplicate hits. Result SHA-256:
  `d9aa3da58e82fb47d67464c8662a65ffa8b42e7560254172331e8af00b905f58`.

## Prior-round invariant reruns

- Round 4's eCFR parentage scan covers seven official XMLs and 3,764 section
  occurrences. Source, inventory, and iterator each contain 3,501 unique
  paths; missing sections and both parent-mismatch sets are empty. Result
  SHA-256:
  `384c4609027843ef2bc4d84e5966d72ae5ece438ab6f2add125a1d77bd95258c`.
- The official Title 26 USC probe remains unchanged: source and traversal each
  contain 58,368 structural occurrences, while official source derivation,
  inventory, and provisions each contain exactly 58,351 unique paths in the
  same order, with no missing or extra path. Source SHA-256:
  `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621`;
  canonical result SHA-256:
  `db983eade28d34b2b44657ccb31ef84fdf9afd065f858f6776e8c2dcd56ef7b9`.

## Delta, ancestry, and blast radius

- The target is exactly one non-merge commit atop
  `49b0ae93367c48b7134576bf15a157c516d44a73`. It modifies only
  `src/axiom_corpus/corpus/ecfr.py` and `tests/test_corpus_ecfr.py`;
  `git diff --check` passes.
- Target-pinned PR-only history
  `a64ec80693ad37f56ab9f1ea5102c4998b9c01d9..df36df25594e` contains five
  commits and only the eCFR/USC modules, their tests, and the USC changelog
  fragment. It contains no progress, report, review-probe, scratch, or session
  path.
- `afab29fc555af3d5bc25bba795e5b0c6ef936adc` remains the exact merge-base
  ancestor. Both Ed25519 ingest manifests attest that commit and remain
  byte-identical, with SHA-256 values
  `4c5569fbf37660441db6f8d2cffbd6a061da36c547d088a66a3f7f97b006fbe2`
  and
  `56f7f5dc58046e9757e1b389f7dc1b69490b06a941fccdc6d57b6ae4f922796b`.
- Target-local GitNexus impact is HIGH with tests included: 11 direct callers,
  14 total upstream impacts, three modules, and two recovery processes. Eight
  direct callers are tests; the three production callers are
  `_extract_one_title`, recovery `_ecfr_records`, and batch recovery `_parse`.
  The focused tests, byte-identical recovery repro, and full suite cover that
  material order-sensitive blast radius.
- Final GitNexus staged detection maps the ledger/report update to two
  review-only files, five indexed symbols, zero affected processes, and LOW
  risk. Target-to-review comparison contains only `PROGRESS.md`,
  `FINAL_REPORT.md`, and the independent probe: nine indexed symbols, zero
  affected processes, and LOW risk.

## Reproduction and gate digest

- The 1401 repro passes through the populated target-first environment:
  statute coverage 21/21 plus 18 anchors, and regulation coverage 2/2 plus 12
  anchors. All eleven scoped artifacts are byte-identical before and after;
  their ordered hash digest remains
  `5e8c0646ab2015987725991f188b08af954f2bc7134c0ccf30a5b8fa43403b02`,
  and the target-pinned artifact diff is empty.
- Focused USC/eCFR tests: 58 passed.
- Full pytest: 4,110 passed, 69 skipped, 208 deselected, and only the
  established PostgreSQL failure
  `TestPostgresStorageSubsectionConversion::test_dict_to_subsection`.
- Ruff, Towncrier, and the required mypy scope pass; mypy reports zero issues
  in 89 source files.
- Citation validation passes for 142,992 records and 124,467 unique paths with
  every ratchet exact.
- Release validation passes for two scopes with zero issues, errors, or
  warnings. Tracked-scope checks pass for five statute and four regulation
  files. Coverage is complete at 21/21 and 2/2 with no duplicates, missing
  paths, or extras.
- Resolver tests: 16 passed and 20 data-dependent skips; direct CLI sweep:
  30/30 exact.

## Tool and sandbox disclosures

- The exact no-cache `uv` repro wrapper exited 1 before the script because
  sandboxed DNS could not download `pycparser==2.23`. It left an ignored,
  incomplete worktree `.venv` and changed none of the eleven artifacts. The
  populated root environment with target-first `PYTHONPATH` ran the committed
  repro successfully.
- GitNexus twice created a complete usable target-local index but sandbox
  policy denied its optional global-registry write at
  `/Users/maxghenis/.gitnexus/registry.json`. The first analyzer exited 1; the
  final post-index process lingered and was interrupted with exit 130. Local
  status is up to date, and direct `LocalBackend` query, context, impact, and
  change-detection calls succeeded.
- The independent probe's first execution failed because the review oracle
  incorrectly expected no subpart metadata on subpart records. The adapter
  correctly returned `A`/`B`; correcting only the oracle made every assertion
  pass.

The committed `PROGRESS.md` is the command-level ledger, and
`review-probes/ecfr_document_order_probe.py` is the durable independent probe.
