# Progress

## State

- Repair round 2 is complete as a defensive correctness-and-completeness audit
  of PR #552 on branch `ingest/ca-bbce-authority`; the repaired content commit
  is `c06ba01fc6e0a547bcafd6824249deae99e18a0b`.
- Starting head: `058cf9ff662161de6ea008e7d0098cb38e9571d8`.
- The round-1 reviewer returned `REQUEST-CHANGES`: PyMuPDF 1.28.0 does not
  byte-reproduce the committed PDF rows, the current MCE-exclusion map is
  incomplete, ACL 14-63 is missing as the focused zero-benefit authority, and
  tracked final-state documentation misstates signing.
- At the start of this repair, both ingest manifests were signed and their
  applied-file hashes matched the existing 45-row corpus state. The repaired
  content now makes both attestations stale. Per instruction, their existing
  signatures remain untouched for the main lane to replace and re-sign after
  the repaired content lands.
- The supplied source cache and session reports remain intentionally
  untracked. No push, GitHub write, R2/Supabase publication, release
  activation, production-row deletion, or signing is authorized.

## Done

- Round 1 retained six byte-verified official sources and emitted 45 rows:
  44 guidance rows from five CDSS PDFs plus one WIC §18901.5 statute row.
- Round 1 added an offline reproducer, focused tests, strict two-scope release
  selection, coverage, manifests, a run document, and signed the two manifests
  in the final two commits.
- Read the pinned round-1 review at commit `4cbf22f3` before beginning repair
  work and accepted all four findings as the repair scope.
- Verified the two newly supplied official-source bytes:
  - ACL 14-63 PDF: SHA-256
    `4392ab0dedfcfb6f247bb7d3d913e90ff2a97a673ea01efac02ec9f3d6ee2841`.
  - WIC §18901.3 HTML: SHA-256
    `793afbd116aa7664fde4137f55d34ad659e80c10f37849d59bb4ea07b43fffdc`.
- Confirmed the worktree begins with only the supplied source cache and prior
  worker report untracked.
- Read the GitNexus debugging and impact-analysis instructions. GitNexus MCP
  tools are not exposed in this session; the local index/CLI and explicit
  caller/diff inspection will be used where possible, with any remaining
  limitation disclosed.
- Refreshed the worktree-local GitNexus graph. The graph build completed and
  reports LOW upstream risk for both shared PDF page-text functions and the CA
  reproducer helpers; its global registry update was denied by the sandbox, so
  queries use the worktree-local graph directly.
- Isolated the PyMuPDF 1.28.0 drift to three accessibility strings on page 1
  of ACL 14-56 and ACL 13-32. The four other PDFs in the repaired scope,
  including ACL 14-63, have version-stable page text.
- Added the repository's pending opt-in, manifest-driven PDF text replacement
  facility across plain, segmented, styled, and OCR extraction modes, with
  validation and focused unit tests. This keeps source-specific normalization
  explicit rather than pinning every corpus PDF to one library version.
- Configured only ACL 14-56 and ACL 13-32 to remove the three known
  accessibility strings. Full offline dry runs and the seven focused
  PR-scope tests pass under both PyMuPDF 1.26.7 and cached 1.28.0. All 14
  generated artifact hashes are identical across the two resolutions;
  guidance JSONL is
  `41f7997a9704cfa05b22a4e6873e2a6721e2e1d3f6822ac7d41ef72f4769675d`.
- Ingested all eight verified official sources: six CDSS PDFs over 41 pages
  and WIC §§18901.3 and 18901.5. The repaired scopes contain 47/47 guidance
  rows and 2/2 statute rows, 49 total, at the conventional combined statute
  version
  `2026-07-28-ca-cdss-calfresh-bbce-authority-us-ca-sections-wic-18901.3-wic-18901.5`.
- Replaced the four tracked one-section statute artifacts with the five
  two-section artifacts. The removed files remain recoverable from Git; the
  obsolete signed manifest was later removed by the main lane when it
  re-signed the round-two manifests (see the closing entry below).
- Added a closed seven-gate MCE exclusion map against the exact current
  retained `us/regulation/7/273/2` row and supporting `273/11` row. The map
  hashes the exact 7 CFR 273.2(j)(2)(vii) text, separately preserves the five
  paragraph (ix) member exclusions, and maps only the drug-felony and
  fleeing/probation-parole gates to the WIC §18901.3 state overlay.
- Promoted ACL 14-63 as the focused zero-benefit denial/discontinuance
  authority while retaining ACL 14-56 as context.
- Added a prior-row conservation oracle: all 45 round-1 rows retain the stable
  semantic projection hash
  `6a79caf1945521a9d13aaf58248cd453a1d938b545d309d6b3f4b570fed68edd`.
- Updated the release selector, citation-path census ratchet, run document,
  changelog, and source attributes for the repaired two-scope content and
  corrected the run document's stale signing claim.
- Passed the exact offline byte-determinism test under both PyMuPDF 1.26.7 and
  1.28.0 after the content commit. Each run regenerated all 14 scoped
  artifacts and compared them byte-for-byte with the committed corpus.
- Passed the full repository suite: 4,130 passed, 74 skipped, and 208
  deselected. Ruff, Towncrier check and draft, manifest loading,
  `git diff --check`, both explicit coverage rewrites, and focused
  PDF-replacement tests also pass.
- Passed citation validation at 143,779 records and 125,251 unique paths, with
  `page_n` exactly 31,399/31,399 and no identity drift or ratchet regression.
- Passed guidance and statute tracked-scope verification, confirmed all 14
  generated artifacts are tracked, and passed strict two-scope release
  validation with zero errors and zero warnings.
- The prescribed broad MyPy command reports 168 errors in untouched legacy
  modules. The pinned round-1 review worktree reports 177 errors under the same
  installed MyPy 1.19.0 environment, with zero branch-only diagnostics. Both
  changed Python source files pass strict MyPy with external imports skipped.
- Refreshed the post-commit GitNexus graph at `c06ba01f`; final comparison
  reports LOW risk, zero affected execution processes, and the expected 23
  changed files across all round-2 commits.
- Confirmed the unchanged signed guidance manifest now has three stale applied
  hashes and the unchanged one-section statute manifest has four missing old
  paths. Signed-ingest guard verification could not proceed cryptographically
  because this lane has no `AXIOM_CORPUS_INGEST_PUBLIC_KEY`; replacing and
  re-signing both manifests was reserved for the main lane, which completed
  it after this entry (see the closing entry below).
- Disclosed environment limits: the default uv cache and GitNexus global
  registry are sandbox-read-only, so uv used a `/private/tmp` cache and
  GitNexus used its successfully refreshed worktree-local graph. A fresh
  PyMuPDF 1.28.0 download was blocked by sandbox DNS/network access, but an
  existing verified local 1.28.0 archive enabled the required real-version
  reproduction proof.

## Next

- Main lane: replace/re-sign the stale manifests for all nine guidance
  artifacts and all five combined-scope statute artifacts, then rerun the
  signed-ingest guard with the configured public key.
- Keep the final per-parameter audit report untracked. Do not publish, push,
  activate a release, upload to R2, load Supabase, or delete production rows
  without separate user authorization.

## Closing entry — main-lane signing complete (2026-07-28)

- After the round-two content commit, the main lane re-signed the guidance
  manifest and signed the combined WIC 18901.3 + 18901.5 statute manifest;
  every applied-file hash matches the committed artifacts, each attested
  commit is an ancestor of its signing commit, and `guard-ingested` passes.
- The superseded single-section statute manifest
  (`...-us-ca-sections-wic-18901.5.json`), whose artifacts no longer exist
  under that version name, was removed in the same commit.
- The round-one review statements that the manifests "remain unsigned" and
  the round-two statements that they "remain stale" describe intermediate
  states and are superseded by this entry.

# PR #552 Round-3 Review Ledger (review-only)

## State

- Scoped confirmation is complete at immutable target
  `5fe8dbf3217fd33f546b4c6a2ceed5230aff6ebb`.
- All four requested checks pass; `PR-552-ROUND-3-CONFIRM.md` records
  `VERDICT: APPROVE`.
- Disposable local review branch:
  `review/pr-552-r3-5fe8dbf3-blind`.
- Disposable worktree:
  `.git/review-worktrees/pr-552-r3-5fe8dbf3`.
- Output file: `PR-552-ROUND-3-CONFIRM.md`.
- No PR-branch, remote, GitHub, publication, R2, Supabase, or serving-database
  writes are authorized or planned.

## Done

- Read the repository rules and GitNexus PR-review workflow.
- Created the disposable worktree at the exact requested head.
- Built a fresh exact-head GitNexus index: 20,300 nodes, 56,657 edges,
  1,173 clusters, and 300 flows.
- Ran pre-edit impact analysis for `PROGRESS.md`: LOW risk, with zero direct
  dependents, affected processes, or affected modules.
- Verified both active ingest manifests contain Ed25519 signatures. Recomputed
  every applied-file digest against the immutable target: all 9 guidance and
  all 5 statute hashes match.
- Verified the attested-to-signing ancestry pairs with
  `git merge-base --is-ancestor`: guidance
  `256634f6 -> b1d42e7e` and statute `b1d42e7e -> 40e8513e`.
- Ran the keyed full-PR `guard-ingested` check from base `10142cb0` to target
  `5fe8dbf3`: `passed: true`, 14 protected changes, and `issues: []`.
  The docs-only `40e8513e..5fe8dbf3` guard also passes with zero protected
  changes and zero issues.
- Confirmed the superseded one-section statute manifest and all artifacts
  under its old version name are absent. Commit `40e8513e` added the combined
  manifest and deleted the superseded manifest together.
- Audited immutable-target `PROGRESS.md`. Its dated closing entry explicitly
  labels the earlier unsigned/stale statements as intermediate and superseded;
  every factual claim in the entry is supported by manifests, hashes, ancestry,
  history, and guard output.
- Verified `40e8513e..5fe8dbf3` is exactly one linear, non-merge commit whose
  parent is `40e8513e`, touching only `PROGRESS.md` and the CA BBCE ingest run
  document. `git diff --check` passes.
- Ran the literal offline reproduction command under PyMuPDF 1.26.7 / MuPDF
  1.26.12. It exited zero with 47 guidance rows, 2 statute rows, seven MCE
  gates, and all 14 regenerated artifacts byte-for-byte and hash-identical to
  the target. The worktree remained clean.
- Ran GitNexus compare-scope detection and document impact/context checks:
  LOW risk, zero affected execution flows, modules, or direct dependents.
- Wrote the final evidence report to `PR-552-ROUND-3-CONFIRM.md`.
- No PR-branch, remote, GitHub, publication, R2, Supabase, or serving-database
  writes were performed.

## Next

- Return the committed report and required approval verdict. No PR-side action
  remains in this scoped confirmation.
