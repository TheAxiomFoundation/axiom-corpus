VERDICT: APPROVE

# PR #552 Round-3 Confirmation

Target: `5fe8dbf3217fd33f546b4c6a2ceed5230aff6ebb`

Prior reviewed head: `40e8513e71a66093cfdf2361eae56d36d8d875cb`

Risk: LOW. This is one documentation-only commit with no affected execution
flows, and all four requested confirmation checks pass.

## 1. Run-document signing paragraph

The signing paragraph in
`docs/ingest-runs/2026-07-28-ca-calfresh-bbce-authority.md` is accurate.

- The active guidance and combined-statute manifests both contain nonempty
  Ed25519 signatures under key ID `axiom-corpus-ingest-v1`.
- All 14 applied-file hashes match the immutable target tree: 9/9 guidance
  files and 5/5 statute files.
- Both attested-to-signing ancestry checks exit zero:
  - guidance: `256634f6 -> b1d42e7e`;
  - combined statute: `b1d42e7e -> 40e8513e`.
- A keyed full-PR guard from base `10142cb0` to target `5fe8dbf3` reports
  `passed: true`, all 14 protected changes, and `issues: []`.
- A second guard over only `40e8513e..5fe8dbf3` reports `passed: true`,
  `protected_changes: []`, and `issues: []`.
- The superseded manifest
  `.axiom/ingest-manifests/us-ca/statute/2026-07-28-ca-cdss-calfresh-bbce-authority-us-ca-sections-wic-18901.5.json`
  is absent, as are all corpus artifacts under that old version name. Commit
  `40e8513e` added the combined manifest and deleted the superseded manifest
  together.

## 2. `PROGRESS.md` closing entry

The immutable target's closing entry at lines 122–133 is accurate and clearly
supersedes the append-only historical narrative.

- The heading says main-lane signing is complete.
- The entry explicitly labels the prior "remain unsigned" and "remain stale"
  statements as intermediate states and says they are superseded.
- The nearby historical entries now point readers to the closing entry where
  needed.
- Every factual claim is verifiable from the target manifests, Git history,
  recomputed hashes, ancestry checks, guard output, and target-tree absence of
  the superseded manifest and old-version artifacts.

The older current-tense `Next` item remains as historical narrative, but the
later dated closing entry unambiguously overrides it. It is not an unresolved
instruction.

## 3. Delta from round 2

`40e8513e..5fe8dbf3` is exactly one linear, non-merge commit:

- subject: `docs: record the completed main-lane signing state`;
- sole parent and merge base: `40e8513e`;
- commit count: 1;
- files:
  - `PROGRESS.md`;
  - `docs/ingest-runs/2026-07-28-ca-calfresh-bbce-authority.md`.

No other path changed, and `git diff --check 40e8513e 5fe8dbf3` passes.

## 4. Determinism replay

The documented literal command was replayed successfully:

```bash
uv run --extra dev python scripts/repro/us_ca_calfresh_bbce_authority.py --base data/corpus
```

Runtime: PyMuPDF 1.26.7 / MuPDF 1.26.12.

The command exited zero and regenerated 47 guidance rows, 2 statute rows, and
the seven-gate MCE map. All 14 scoped artifacts matched the target Git blobs
byte-for-byte and by SHA-256. The full `data/corpus` comparison and final Git
index comparison both passed, and the review worktree remained clean.

The default uv cache was sandbox-inaccessible and offline dependency syncing
could not rebuild an environment. The successful replay therefore used an
isolated copy of the existing locked environment with offline/no-sync runtime
overrides and `PYTHONPATH` pinned to this exact worktree; the documented command
line itself was unchanged.

## Change scope and side effects

A fresh exact-head GitNexus index reports LOW risk for the two documentation
files, with zero direct dependents, affected modules, or affected execution
flows. No PR-branch, remote, GitHub, publication, R2, Supabase, or
serving-database writes were performed.

Recommendation: approve PR #552 at `5fe8dbf3`.
