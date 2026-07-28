# PR #552 Blind Adversarial Review Progress

## State

- Review target: PR #552, `ingest/ca-bbce-authority`.
- GitHub-verified immutable head:
  `058cf9ff662161de6ea008e7d0098cb38e9571d8`.
- GitHub-verified base: `main` at
  `10142cb0f07403c2de4599c76bec01e96640fda9`.
- Disposable review branch: `review/pr-552-058cf9f-blind`.
- Disposable worktree:
  `.git/review-worktrees/pr-552-058cf9f`.
- Output file: `PR-552-REVIEW.md`.
- Review is complete with a `REQUEST-CHANGES` verdict. No PR branch, remote,
  GitHub, publication, or serving database writes were made.

## Done

- Read the repository instructions and GitNexus PR-review workflow.
- Verified PR metadata through the read-only GitHub connector.
- Confirmed the local branch and remote-tracking ref both resolve to the exact
  GitHub head.
- Confirmed the PR merge base is the GitHub base SHA.
- Created the isolated review worktree and local review branch at the exact
  head.
- Rebuilt the worktree-local GitNexus index at the exact head. Graph generation
  succeeded; global registry registration was sandbox-blocked at
  `/Users/maxghenis/.gitnexus/registry.json`, so a temporary local registry is
  used for review queries.
- Ran pre-edit impact analysis for `PROGRESS.md`: LOW risk, with zero direct
  dependents, affected processes, or affected modules.
- Inventoried the immutable PR range: 23 changed paths, 12 PR commits, and 39
  indexed changed symbols.
- Ran GitNexus compare-scope change detection against the exact base: LOW risk
  and zero affected execution flows.
- Ran upstream impact analysis on every uniquely named non-trivial repro
  function. Each is LOW risk; direct callers stay inside the new standalone
  repro chain and focused test.
- GitNexus's name-only impact interface selected unrelated same-named symbols
  for `_load_jsonl`, `_verify_generated_scope`, `reproduce`, and `main`.
  Exact-UID context fallback confirmed their complete incoming/outgoing chain
  is confined to the new repro script and its deterministic replay test, with
  no execution-flow participation.
- Confirmed the target shape is 12 corpus artifacts, two signed ingest
  manifests, one source manifest, one release selector, one repro script, one
  focused test file, one ingest run record, one changelog fragment, one
  citation census edit, `.gitattributes`, and the expected tracked
  `PROGRESS.md`.
- Confirmed all six retained source files match the untracked source-lane
  worker report and source cache byte-for-byte. Direct shell downloads were
  DNS-blocked, but read-only web retrieval reached the live official CDSS and
  LegInfo endpoints. The five PDFs have the asserted CDSS letterhead, ACL
  numbers, dates, and page counts; the HTML is the official current WIC
  chapter containing section 18901.5.
- Verified all 13 asserted authority excerpts occur verbatim in the retained
  normalized rows. The state mandate, inclusive 200% gross screen, PUB 275
  trigger, resource waiver, net-test waiver, former drug-felony change, and
  elderly/disabled neighboring route are substantively supported.
- Found a major authority-map defect: the row labeled `Current MCE exclusions`
  treats the IPV and head-of-household work examples in ACL 15-42 as the
  current set. Current 7 CFR 273.2(j)(2)(vii), already retained in the corpus,
  also preserves applicable reporting, household workfare, fleeing-felon,
  probation/parole, and certain crime/sentence gates. Current WIC 18901.3
  removes conviction-alone ineligibility but preserves fleeing-felon and
  probation/parole restrictions.
- Found a minor authority-completeness issue: ACL 14-63 is the later focused
  operational authority for zero-benefit handling. ACL 14-56 page 6 is
  behaviorally consistent but is not the best controlling citation.
- Verified the claimed 45 rows: one statute row plus 44 guidance rows, split
  `8/5/14/13/4`. All 39 page bodies match text extracted from their stated PDF
  pages, and citation paths/granularity match the existing California
  ACL/ACIN convention.
- Ran the committed literal repro against retained sources and again with the
  source-lane local directory under the locked PyMuPDF 1.26.7 environment.
  Both runs reproduced all 12 artifacts byte-identically with zero tracked
  drift.
- Found a blocking portability defect in exact-head CI run `30378087303`: its
  pip environment resolved permitted PyMuPDF 1.28.0, and the PR-added
  byte-determinism test failed because that extractor adds accessibility text
  absent under locked PyMuPDF 1.26.7. The declared
  `pymupdf>=1.25.0` range therefore does not support the claimed portable,
  byte-identical replay.
- Verified both Ed25519 signatures with the repository public key. Applied-file
  hashes match the PR tree and the attested ancestor commits; the manifest
  command is the literal documented invocation.
- Passed citation census, both tracked-scope checks, strict two-scope release
  validation, changelog/Towncrier checks, Ruff, MyPy, and diff hygiene.
- Found stale tracked status text in the ingest run record and PR-head
  `PROGRESS.md`: both still say the final manifests are unsigned even though
  the last two PR commits signed them.
- Compared full local suites under the same sandbox-safe environment. The PR
  has `1 failed, 4122 passed, 69 skipped, 208 deselected`; clean main has
  `1 failed, 4118 passed, 69 skipped, 208 deselected`. The sole shared local
  failure is the pre-existing PostgreSQL mock test. Exact-head CI independently
  fails the new deterministic-replay test and is red.
- Wrote the complete evidence digest and per-parameter authority determination
  to `PR-552-REVIEW.md`; its first line records the required verdict.

## Next

- PR owner: stabilize the PDF extraction contract across supported installs,
  correct the incomplete current-exclusions map, and update stale final-state
  documentation.
- After remediation: regenerate and re-sign any changed applied artifacts,
  then rerun fresh-install deterministic replay, authority-completeness, full
  CI, manifest guard, and release gates.
