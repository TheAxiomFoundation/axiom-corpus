# PR #552 Round-2 Review Progress

## State

- Review target: PR #552, `ingest/ca-bbce-authority`.
- GitHub-verified immutable head:
  `40e8513e71a66093cfdf2361eae56d36d8d875cb`.
- GitHub-verified base: `main` at
  `10142cb0f07403c2de4599c76bec01e96640fda9`.
- Disposable review branch: `review/pr-552-r2-40e8513e-blind`.
- Disposable worktree:
  `.git/review-worktrees/pr-552-r2-40e8513e`.
- Output file: `PR-552-ROUND-2-REVIEW.md`.
- The substantive authority audit and all local release/hygiene gates are
  complete. One independently confirmed review blocker remains: the final
  tracked run document and PR-head ledger still describe the repaired
  manifests as stale and awaiting re-signing, contrary to the final two PR
  commits. No PR-branch, remote, GitHub, publication, R2, Supabase, or
  serving-database writes are authorized.

## Done

- Read the repository instructions and GitNexus PR-review workflow.
- Independently verified the PR head/base, open state, commit/file counts, and
  round-2 repair claims through the read-only GitHub connector.
- Created the isolated worktree and local review branch at the exact requested
  head.
- Generated a worktree-local GitNexus index at the exact head: 20,279 nodes,
  56,649 edges, 1,153 clusters, and 300 flows. Global registry registration
  was sandbox-blocked, so a temporary local registry is used for review
  queries.
- Ran pre-edit impact analysis for `PROGRESS.md`: LOW risk, with zero direct
  dependents, affected processes, or affected modules.
- Ran GitNexus compare-scope detection against the exact base: 87 indexed
  changed symbols in 28 files, LOW aggregate risk, and no affected execution
  flows. The review-only ledger commit adds no affected flow.
- Reviewed upstream impact for the shared PDF replacement chain. The parser
  has MEDIUM blast radius (six direct callers: two extraction paths and four
  focused tests); the replacement helper and both PDF text paths are LOW risk.
  The MCE semantic verifier is LOW risk and stays inside the standalone repro
  and focused test chain.
- Independently compared the retained 7 CFR 273.2(j)(2)(vii), (ix), and (xi)
  text with the live eCFR, which is current through July 24, 2026 and last
  amended July 9, 2026. The retained July 9 text has the same seven household
  gates, five separate member exclusions, and financial-test exceptions.
- Independently compared retained WIC §§18901.3 and 18901.5 with current
  California Legislative Information text; the drug-felony opt-out,
  probation/parole and fleeing-felon conditions, and categorical-eligibility
  mandate match.
- Confirmed the two final PR commits replace the stale manifests: guidance
  now attests `256634f6` with 47/47 coverage and the combined statute manifest
  attests `b1d42e7e` with 2/2 coverage. Nevertheless, immutable-head
  `PROGRESS.md` lines 13–16, 99–103, and 113–115 and the run document lines
  115–121 still say the manifests are stale and must be re-signed. The
  round-1 signing-documentation defect therefore remains.
- Completed an independent current-authority audit of every RuleSpec-US #1098
  parameter. The retained text controls the inclusive 200% FPL screen, PUB 275
  trigger, asset/resource waiver, ordinary net-eligibility-test waiver,
  MCE exclusions, drug-felony California overlay, ACL 14-63 zero-benefit
  treatment, and the non-MCE E/D route. No materially superseding authority
  was found.
- Exhaustively matched current 7 CFR 273.2(j)(2)(vii)'s seven household gates:
  two clause-A gates, one clause-B gate, one clause-C gate, and three clause-D
  gates. WIC §18901.3 correctly removes conviction-alone drug-felony
  ineligibility but does not replace the universal fleeing/probation/parole
  rule. The five separate paragraph-(ix) member exclusions are also retained
  and verified.
- Authenticated all six retained PDFs locally by ACL number, date, CDSS
  identity, and physical pagination (`7/4/2/13/12/3`). All eight retained
  source files match the worker report and supplied local-source cache byte for
  byte. Shell redownloads from CDSS and LegInfo were DNS-blocked; read-only
  browser retrieval nevertheless reached live ACL 14-63 and both current WIC
  sections and confirmed their identity/text.
- Ran the documented literal repro text under PyMuPDF 1.26.7 using only
  sandbox-safe runtime environment overrides. It regenerated all 14 scoped
  files at the committed hashes, reported 47 guidance plus 2 statute rows and
  seven MCE gates, and left zero tracked drift. The first default-cache attempt
  was sandbox-denied and the writable-cache sync retry was DNS-blocked; an
  offline/no-sync retry used the existing locked environment successfully.
- Independently repeated the literal repro and focused tests in detached
  exact-head worktrees under both PyMuPDF 1.26.7/MuPDF 1.26.12 and PyMuPDF
  1.28.0/MuPDF 1.29.0. Both engines emitted the same 14 committed hashes,
  passed the replay test, all seven PR-scope tests, and all nine replacement
  tests, and left zero tracked corpus drift. The only raw-version differences
  are the three declared accessibility strings on ACL 14-56 page 1 and ACL
  13-32 page 1; opt-in replacement normalizes every extraction mode to the
  same cooked bytes.
- Passed the focused document/authority/reproduction suite (`109 passed`),
  Ruff, Towncrier check, `git diff --check`, citation census (143,779 records,
  125,251 unique paths, no drift/regression), both tracked-scope checks
  (9 guidance and 5 statute files), strict two-scope release validation (zero
  errors/warnings), and the signed-ingest guard (14 protected files, no
  issues).
- Compared the same full local pytest command at head and clean base. Head:
  `1 failed, 4134 passed, 69 skipped, 208 deselected`; base:
  `1 failed, 4118 passed, 69 skipped, 208 deselected`. The sole failure in both
  is the pre-existing PostgreSQL `MagicMock` subsection conversion test.
- The prescribed broad MyPy command reports the same 180 errors in 26
  untouched legacy files at head and clean base under the installed MyPy
  1.19.0 environment. Exact-head GitHub CI independently passes its MyPy step,
  ingest guard, release gates, and full test job under its fresh environment.

## Next

- Write and commit the final evidence report and completed ledger.
