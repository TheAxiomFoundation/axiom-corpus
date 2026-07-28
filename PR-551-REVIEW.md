VERDICT: REQUEST-CHANGES

# Blind adversarial review: axiom-corpus PR #551

## Pinned scope

- Reviewed PR head: `f1176ed6641d31b09b1750eb1bc8eed84dd2159e`
- PR branch: `ingest/usc-amt-ftc-sections`
- Base and merge base: `db12795577c5809009168982cf8a72fb58440620`
- Disposable review branch: `review/pr-551-f1176ed-blind`
- Target diff: 14 files and 5 commits

The local branch, remote-tracking ref, and read-only GitHub PR metadata all
agreed on the exact head before review. No PR branch, remote, or GitHub state
was changed.

## Changes required

1. **Make every committed reproduction instruction portable.** The signed
   manifest correctly records:

   ```text
   uv run --extra dev python scripts/repro/us_usc_amt_ftc_sections.py --base data/corpus
   ```

   However, `docs/ingest-runs/2026-07-27-usc-amt-ftc-sections.md:43` and
   `scripts/repro/us_usc_amt_ftc_sections.py:26-29` still advertise and print:

   ```text
   PYTHONPATH=src uv run --no-cache --no-sync --extra dev python scripts/repro/us_usc_amt_ftc_sections.py --base data/corpus
   ```

   From the same clean checkout with no `.venv`, that stale committed command
   exits 1 with `ModuleNotFoundError: No module named 'pydantic'`. The final
   signing commit corrected only the manifest. Update the run record and
   `REPRO_COMMAND`, make the script's output agree with the manifest, rerun the
   clean-state reproduction, and re-attest/re-sign the resulting ancestor.

2. **Correct the PR's claimed section census.** The claimed
   `3/43/17/98/133/3/1/260` values are not the official enacted hierarchy and
   sum to 558, not 552. The committed artifacts and tests use the correct
   root-inclusive section counts:
   `1/43/17/98/131/1/1/259`. Those sum to 551, and the shared Title 26 row
   makes 552. The ingest data is correct; the review claim is not.

3. **Resolve the concurrent PR #550 census deliberately.** The two branches
   have one forced content conflict, `schema/citation-path.v1.json`. PR #551's
   branch-only value is correctly 6,710. PR #550 adds 82 disjoint uppercase
   paths, so the post-integration value must be **6,792**. Choosing either
   branch's file wholesale is destructive; regenerate the census and rerun
   citation/release validation when the second prerequisite lands.

## Official-source and byte-faithfulness audit

The retained release-point ZIP is 8,289,527 bytes with SHA-256:

```text
d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0
```

It passes ZIP integrity checking and has exactly one member, `usc26.xml`. That
55,856,053-byte member has SHA-256:

```text
d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621
```

The member is byte-identical to the committed XML and to the same official
release-point bytes already retained by the main-branch §1401 scope. All 552
inventory entries attest that XML hash.

I independently projected source identifiers, headings, and statutory bodies
from the XML for all 551 section/hierarchy rows. Comparison with the JSONL
found zero identifier, heading, body, or sequence mismatches. No hand-edited
statutory text was found.

Long-section truncation checks also pass:

- §59 is complete through §59(l)(3). Its root-body projection is 16,742 UTF-8
  bytes, SHA-256 `5e68eb35dea365b9450c0f5f4edccd300c4f4d112aca8b5d560846e1a70e43cd`.
  The source and JSONL canonical section streams both hash to
  `b248e3048c7394a3fdca97464bdcbd9e17c78f75d93e3aed0e52727e9f4fad96`.
- §904 is complete through §904(k). Its root-body projection is 48,581 UTF-8
  bytes, SHA-256 `25e81dfd8b781dec290bb5015bc44a6545c5297a9723c3bcc693c82e205b0ec8`.
  The source and JSONL canonical section streams both hash to
  `956edc9aaf872247f7c4d59853b96d83e17e54d135cb9be3a5b8b08f7d3a4ff1`.

The [official House download index](https://uscode.house.gov/download/download.shtml/)
identifies the same Title 26 release point, current through Public Law 119-102
except 119-101.

## Independent descendant census

“Descendants” below means identified enacted structural descendants, excluding
the section root. “Source nodes” includes that root and is directly comparable
to emitted inventory/provision paths.

| Section | Official descendants | Source nodes including root | Ingested paths | Kind distribution |
|---|---:|---:|---:|---|
| §27 | 0 | 1 | 1 | section 1 |
| §57 | 42 | 43 | 43 | section 1, subsection 2, paragraph 9, subparagraph 8, clause 14, subclause 9 |
| §58 | 16 | 17 | 17 | section 1, subsection 3, paragraph 7, subparagraph 6 |
| §59 | 97 | 98 | 98 | section 1, subsection 12, paragraph 19, subparagraph 33, clause 23, subclause 10 |
| §901 | 130 | 131 | 131 | section 1, subsection 14, paragraph 44, subparagraph 34, clause 32, subclause 6 |
| §902 | 0 | 1 | 1 | section 1 |
| §903 | 0 | 1 | 1 | section 1 |
| §904 | 258 | 259 | 259 | section 1, subsection 11, paragraph 39, subparagraph 99, clause 86, subclause 23 |
| **Total** | **543** | **551** | **551** | plus one shared Title 26 row = 552 |

Every source path appears exactly once in both inventory and provisions and in
the same depth-first document order. The #523 regression classes were tested
explicitly:

- zero duplicate source identifiers;
- zero duplicate-numbered enacted sibling groups;
- zero mixed-kind structural child lists;
- zero skipped hierarchy levels;
- zero missing or extra paths; and
- zero source-to-JSONL ordering differences.

The XML does contain identifierless quotation/notes structures. Those are not
operative enacted descendants and must not be counted as normalized statutory
atoms. Counting tags without respecting identifiers and the enacted hierarchy
produces spurious totals.

## Section 902 discipline

Section 902 emits exactly one row, `us/statute/26/902`, with:

- official repeal heading;
- `body: ""`;
- `metadata.status: "repealed"`; and
- no descendant paths.

No operative amount is present. The target diff adds no computation, RuleSpec,
formula, or individual-tax implementation. Repository-wide target searches
found §902 only in the corpus artifacts, release/run documentation,
reproduction assertions, and tests. Sections 901 and 904 retain metadata
cross-references to §902 because the official operative text names it; those
references do not turn §902 into a rule or amount. Nothing in this ingest can
supply a §902 amount to an individual computation.

## Reproduction and manifest integrity

The manifest's command was extracted rather than retyped and run unchanged in
a fresh detached worktree with no `.venv` and no `PYTHONPATH`. A sandbox-local
writable uv cache was supplied. The command exited 0, created a fresh
environment, installed 122 locked packages, and left:

- `git diff --exit-code`: 0;
- modified tracked files: 0; and
- nonignored untracked files: 0.

A second run into a brand-new corpus base byte-compared equal for every scoped
artifact. The five manifest hashes all match:

| Applied file | SHA-256 |
|---|---|
| coverage | `e40f5f24236097db279ce42975bfad53d6a6537304c46db16df7f567d649dee0` |
| inventory | `de82b7579b32a189caf19df0ebd8d8ed5b1b916661ee78ecd41d0bf85aed705a` |
| provisions | `c72f43dcf5cd1f8e53f1873f058bed0645fb02334cdb2a07ad37eff5f30f90c3` |
| retained ZIP | `d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0` |
| retained XML | `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621` |

Repository manifest verification with the documented public key passes with
`issues=[]`. The Ed25519 signature is valid. Attested commit
`c2f51414d0f94a0d7f9d895b01a4bb3c550bbc93` is a full ancestor of the reviewed
head. Coverage in the signed payload is complete at 552/552.

This validates the signed manifest but does not cure the contradictory stale
command in the run document and script output; those files are not bound as
`applied_files`, and `reasoning_logs` is empty.

## Normalization, hygiene, and integration

The target emits one title, eight sections, 42 subsections, 118 paragraphs,
180 subparagraphs, 155 clauses, and 48 subclauses at levels 0–6. This matches
the full-hierarchy USLM granularity used by neighboring main-branch Title 26
scopes. The whole-title ZIP/XML exists only as retained source evidence; it is
not passed off as a normalized atom.

The PR target contains no `PROGRESS`, worker report, session, or review-ledger
artifact. It has a changelog entry, target release selector, source snapshot,
inventory, provisions, coverage, reproduction code, focused tests, and the
minimal parser change needed to preserve official `status`. No unrelated
target file was found.

Citation validation counts 143,567 records and 125,041 unique paths on this
branch. The branch adds 552 rows, 551 unique paths (the title is shared), and
383 uppercase paths over main; the 6,710 branch-only ratchet is exact.

Concurrent PR #550 is pinned at
`a942613cb190f09f191657aeb7199d31c8774f13`, with the same base. Its source
artifacts use distinct scope paths and the same retained official ZIP/XML
bytes. The only overlapping changed file is the citation census. `git
merge-tree` reports an explicit content conflict there, so the problem cannot
merge silently, but resolving it with “ours” or “theirs” would lose valid
census data.

`git diff --check` reports CRLF whitespace on the first two lines of the added
official XML. Those bytes are in the official ZIP member; normalizing them
would violate byte-faithfulness, so this is not a hygiene defect.

## Gates

| Gate | Result |
|---|---|
| Ruff | PASS — all checks passed |
| mypy | PASS — no issues in 89 corpus source files, using an isolated cache |
| Towncrier | PASS — changelog fragment found |
| Citation-path validation | PASS — 143,567 records; 125,041 unique; uppercase 6,710/6,710 |
| Release validation | PASS — 78 selectors, 0 failed; target selector has 0 issues/warnings/errors |
| Scoped tracked-file verification | PASS — 5 referenced files across 1 scope |
| Coverage | PASS — complete 552/552; no gaps, extras, or duplicates |
| Signed-ingest guard | PASS — signature, ancestry, and all 5 protected artifacts valid |
| Full pytest | BASELINE-ONLY FAILURE — 4,116 passed, 69 skipped, 208 deselected; one known PostgreSQL conversion test failed identically on clean main |

The sole pytest failure is
`tests/test_storage_postgres.py::TestPostgresStorageSubsectionConversion::test_dict_to_subsection`.
The same `ValidationError` reproduces on a clean detached `origin/main`. No
failure unique to PR #551 was found.

Global, unscoped tracked-file verification also reports historical missing
source files, but its target and clean-main outputs are byte-identical (1,204
lines; SHA-256
`040ebdcc91ea56fda37bacdc84ce96b5a515824955e67c2eac16f3d368992604`).
The requested target scope passes.

## Sandbox and tooling disclosures

- Direct `gh` and fresh endpoint access were network/DNS blocked; the
  read-only GitHub connector established the PR SHA, and direct House ZIP
  retrieval returned HTTP 403. The retained official ZIP/member/XML and prior
  retained release-point copy were therefore the byte-verification basis.
- The default uv cache under the home directory was not writable. Clean
  reproduction succeeded with a writable temporary offline cache. One
  separate dependency-sync attempt was DNS-blocked.
- Requested gates used the repository's complete environment with
  `PYTHONPATH=src`; the manifest's exact command was separately proven in the
  clean detached worktree.
- A broken local bare-`python` wrapper was bypassed with `/usr/bin/python3` for
  independent XML analysis.
- GitNexus global registry registration was sandbox-blocked. A fresh index of
  the pinned worktree was queried through its local backend instead. Impact
  analysis marked the changed USC parser surface as high risk through
  inventory/provision callers; focused and full tests cover both. Final
  change detection found only the intended review documents on the throwaway
  branch.
- No remote, PR branch, GitHub, publication, R2, Supabase, or production state
  was modified.

