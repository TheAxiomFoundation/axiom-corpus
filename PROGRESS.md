# PR #523 Re-review Progress

## State

- Round: 3 adversarial re-review
- Target: `a64ec80693ad37f56ab9f1ea5102c4998b9c01d9`
- Base: local `origin/main` at `5b5ad3b83259e90b9452c1554eb8e3b759bd175d`
- Mode: review only in a disposable worktree; no source edits, pushes, or GitHub writes
- Verdict: `REQUEST-CHANGES`
- Blocking state: official OLRC nodes are still dropped when enacted sibling
  numbering collides at 26 USC 45X(d)(4)

## Done

- Read the repository instructions and the GitNexus PR-review workflow.
- Recovered the prior verdict and enumerated its four blocking findings.
- Created this isolated local audit branch from the exact stated head.
- Confirmed the target is a linear descendant of the local `origin/main`.
- Inventoried five PR-only commits and 25 changed files.
- Confirmed the target-pinned PR-only name log contains no `PROGRESS.md`,
  `scratchpad/`, or session-report path.
- Built a fresh local GitNexus index of the reviewed source state. Registry
  registration was sandbox-blocked, but the repository-local graph is complete
  and reports up to date.
- Ran GitNexus context and upstream impact analysis for the changed shared
  parsing surfaces. USC inventory/extraction has HIGH blast radius through CLI,
  recovery, and source-slimming flows.
- Verified official retained-source identity and hashes. The OLRC ZIP's sole
  member is byte-identical to the native retained USLM XML; retained eCFR bytes
  are raw Part 1 XML rather than reconstructed structure JSON.
- Verified `_source_artifact_bytes` retains both `meta` and `title`, and the
  scoped 1401/3101 recovery path regenerates all 21 rows.
- Verified the enacted 26 USC 1401(b)(2)(B) `3121(b)(2)` scrivener's error is
  intact and text-equal to the official OLRC element.
- Independently reran the committed reproduction script and exact arguments.
  Statute 21/21 plus 18 anchors and regulation 2/2 plus 12 anchors remained
  byte-identical to the target artifacts.
- Verified both signed manifests record direct ancestor `afab29fc`, use the
  committed reproduction command, have matching applied-file hashes, and were
  added in the final target commit.
- Regenerated complete coverage for both scopes; exercised the real resolver
  for all 30 anchors, including `us/regulation/26/1/1401-1/d/2/i`; all resolved
  exact.
- Verified the citation-path ratchet is exactly the eight uppercase paths
  contributed by this PR, with no padding.
- Confirmed scope discipline, changelog presence, and clean PR-only path/object
  history with no progress, scratchpad, or session-report artifact.
- Reproduced a HIGH traversal defect: the second official §45X(d)(4) sibling is
  deduplicated before traversal, dropping its four unique official descendants.
  The new full-title test hard-codes the lossy adapter total and misses the
  duplicate-number class.
- Reproduced a MEDIUM retained-eCFR defect: selected sections beneath formal
  subparts are flattened directly under the part, while the provision iterator
  retains the missing subpart as parent.
- Ran all required local gates. Ruff, towncrier, citation validation, release
  validation, both tracked-scope checks, coverage, focused tests, and resolver
  checks pass. Full mypy reports the same 180 errors as current `origin/main`;
  full pytest reports one unchanged PostgreSQL failure on target and base, with
  4,107 target tests passing.
- Wrote identical verdict files (SHA-256
  `449cf77ffb484722d1f4854a0fdf0ee65a944274749246d84abef0000b887faa`)
  to both requested `/private/tmp` locations.

## Next

- Hand off `REQUEST-CHANGES`.
- Repair collision-aware USC traversal and add an independent retained-source
  duplicate-number regression; repair retained-eCFR formal-subpart scoping.
- Regenerate affected artifacts if needed and sign manifests last.
