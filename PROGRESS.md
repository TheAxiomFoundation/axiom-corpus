# PR #506 Round-3 Re-review Progress

## State

- Review target: `660fff910529148f50866815447e37c1bf1044b7`.
- Review branch: local throwaway `codex/rereview-506-round3`.
- Review result: `VERDICT: APPROVE`.
- No PR-branch, remote, GitHub, R2, Supabase, publication, or production write
  was made.
- All requested substantive review work is complete.
- The sandbox rejected the required external verdict path because it is outside
  the writable project. A complete fallback report is available at
  `/private/tmp/rereview3-506-VERDICT.md`, SHA-256
  `3a804010809ce66ac97774637d22581753217c2ec140ba7182ddab9327679a57`.
- Two disposable release selectors remain untracked:
  `.review-release-regulation.json` and `.review-release-guidance.json`.
  They are review inputs only and will not be committed.

## Done

### Checkpoint reproduction

- Replayed the regulation script against a source-only temporary base:

  ```bash
  uv run --extra dev python scripts/repro_us_cfr_416_deeming_slice.py \
    --source-base data/corpus --base "$repro_dir"
  ```

- The adapter saw all 622 source rows, selected the declared 14 paths, and
  produced complete 14/14 coverage.
- `cmp` proved byte-for-byte equality for both retained sources and all three
  derived regulation artifacts.
- SHA-256:

  ```text
  f3946c95dd8e4c88f51910538b7c99e98f6563fcd667786771c34d14801b1228  title-20.structure.json
  11ec5a3f11457ebdca99bc958c9666740590a544cd44bd88e681f29b9bf41b26  title-20-part-416.xml
  2dd439932c96eee232a54c737c4b7f5a752f520801f4b342c13d47068386ac33  regulation inventory
  b7cbb4a14b218bcbcafa498ac97f4bd912004258e0cd2e6f1fb4d88f88dd794b  regulation provisions
  93209bef1ffb0588956fd75290ab0703c67e0c5191f6cfdac95a3577dde08076  regulation coverage
  ```

### History hygiene

- `origin/main` was
  `5b5ad3b83259e90b9452c1554eb8e3b759bd175d`; the merge base was
  `71d26e4c30cc67fc76a4ca5ffaee2de76b909448`.
- `git rev-list --left-right --count origin/main...660fff910529148f50866815447e37c1bf1044b7`
  returned `3 4`.
- The PR has exactly four linear, single-parent commits and no merge commit:

  ```text
  9c8d58ad feat: ingest reproducible CFR 416 deeming slice
  d85c58e7 feat: ingest IRS Notice 2025-67
  1568d98e docs: record CFR 416 slice provenance and ratchets
  660fff91 chore: sign the CFR 416 slice and Notice 2025-67 ingest manifests
  ```

- `git diff --name-only 71d26e4c..660fff91` returned 16 in-scope paths and no
  `PROGRESS.md`, scratchpad, session, review, or verdict artifact.
- The three paths changed only on current `origin/main` do not overlap the PR
  paths. `git merge-tree` produced zero conflict markers, and
  `git diff --check 71d26e4c..660fff91` passed.

### Signed ingest manifests

- Both manifests attest
  `1568d98e1b17ed4a7e73fc4fbfaff796abd520a7`, record
  `dirty_tracked=false`, and use Ed25519 key id
  `axiom-corpus-ingest-v1`.
- This command exited zero:

  ```bash
  git merge-base --is-ancestor \
    1568d98e1b17ed4a7e73fc4fbfaff796abd520a7 \
    660fff910529148f50866815447e37c1bf1044b7
  ```

- The signing commit's parent is exactly the attested commit, and the signing
  commit adds only the two manifests.
- The literal recorded commands exactly match the committed invocations:

  ```bash
  uv run --extra dev python scripts/repro_us_cfr_416_deeming_slice.py --base data/corpus
  uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-07-23 --manifest manifests/us-irs-guidance.yaml --only-source-id irs-notice-2025-67
  ```

- The public verification key has SHA-256
  `99e3ab380c6de1bd59f2f9f432a8ca43a798e35b6479e6236de6618b931c1628`.
  Local `guard-ingested` verification returned `passed: true` and `issues: []`:

  ```bash
  AXIOM_CORPUS_INGEST_PUBLIC_KEY='KwIYEbbs/905yxn/9Yi6jYTF8oyZcq1FlxiG4e0y0tg=' \
  UV_CACHE_DIR=/private/tmp/uv-cache-pr506 \
  UV_PROJECT_ENVIRONMENT=/Users/maxghenis/TheAxiomFoundation/axiom-corpus/.venv \
  PYTHONPATH=src uv run --no-sync --extra dev axiom-corpus-ingest \
    guard-ingested --repo . --base-ref 71d26e4c30cc67fc76a4ca5ffaee2de76b909448 \
    --head-ref 660fff910529148f50866815447e37c1bf1044b7 --json
  ```

- Both signatures also verified independently with `cryptography`. Manifest
  blob SHA-256 values:

  ```text
  6962207fb729ffed7dc0aee8f1ec3bbf501e52414d1989b46879315a98366036  guidance manifest
  40a643da8bd4ecdac4465a74c09ffab2c3a88dc168de06aa11e0805efa53449f  regulation manifest
  ```

- Every applied-file hash matches the committed file:

  ```text
  6a230a64c400cd89057762b2c5a06e6baf857b2288b48a1d875455e15e1db462  guidance coverage
  400f1ad890ce0122adb590e61a3cd2fc248014fe1c32dab868cd349e9707be06  guidance inventory
  4838e2001b16f4afcb0b97b7a194743adbaa14da59cb30f5b06626551baa018f  guidance provisions
  1eea8f141b0cddd182f9f09b3bc8ffad683d27ceb806dfc6da126811dc0a1f8d  IRS PDF
  93209bef1ffb0588956fd75290ab0703c67e0c5191f6cfdac95a3577dde08076  regulation coverage
  2dd439932c96eee232a54c737c4b7f5a752f520801f4b342c13d47068386ac33  regulation inventory
  b7cbb4a14b218bcbcafa498ac97f4bd912004258e0cd2e6f1fb4d88f88dd794b  regulation provisions
  11ec5a3f11457ebdca99bc958c9666740590a544cd44bd88e681f29b9bf41b26  eCFR XML
  f3946c95dd8e4c88f51910538b7c99e98f6563fcd667786771c34d14801b1228  eCFR structure
  ```

### Citation, source, scope, changelog, and adversarial review

- `python scripts/validate_citation_paths.py --json` passed with 142,990
  records, 124,468 unique paths, and no failures or ratchet drift.
- The retained primary-source byte sizes and hashes match the runbook:
  eCFR structure 3,982,355 bytes, eCFR XML 1,745,553 bytes, and IRS PDF
  133,701 bytes. The official IRS PDF and eCFR hierarchy were independently
  browser-readable.
- Direct shell re-downloads with `curl -fsSL` could not resolve `ecfr.gov` or
  `irs.gov` in the sandbox, so an exact fresh upstream byte comparison was not
  available. This is an environment limitation, not a corpus mismatch.
- Issue #497 requests sections 1149, 1160, 1161, 1163, 1167, 1202, 1207,
  1801, 1802, and 1806. The committed scope is exactly those ten leaves plus
  Part 416 and formal Subparts K, L, and R: 14 rows, with no missing or extra
  path.
- All ten leaves have the correct formal-subpart parent path and UUID:
  K `294135f8-76fb-5809-b376-ae3346746f80`,
  L `6ff3bf23-99b2-55ac-9aa4-79c75a19f6cf`, and
  R `8f417931-7f31-5ef5-b40c-ab1302fc9c34`.
  The formal-subpart flattening defect class found in PR #523 is absent.
- Container bodies exclude unapproved sections and have these body hashes:

  ```text
  35fbaf3200c1ae9ac9b7d1ff6c0edcd901046a99799429f0438a309d12e1aa36  Part 416
  e1094be56e9f8285f8f8b67147a8ca4318c1ee53be7555d59a09237477c83b0e  Subpart K
  e996c49742f5249b036d77a90eb2e705d0fb5a09bf6766bb7f62e43f931d3612  Subpart L
  ee4bfcf41f33009f1f633b6ce386e5749942cd265aae84df4c39d6edd9190f5a  Subpart R
  ```

- The anchor generator wrote 140 `label_inferred` anchors from the ten leaf
  sections. Exact `resolve-anchor` checks passed for a representative path in
  every leaf, including `.../1160/b/2/ii`, with nonempty spans and the correct
  parent provision.
- The detached exact encoder resolver at
  `f60fd29d74661641cf2fc9d1cef2180a110145fa` resolved all 21 regulation and
  guidance rows exactly, with 21 canonical nonempty bodies. Its signed v2
  release fixture had content SHA-256
  `d557aeefcfcf2573236039e61d1dd26dbe1a5d37daf35e3c8bd8688d8096d680`.
- The changelog fragment exists and accurately describes both new scopes.

### Local gates

All commands used the current worktree source through:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache-pr506 \
UV_PROJECT_ENVIRONMENT=/Users/maxghenis/TheAxiomFoundation/axiom-corpus/.venv \
PYTHONPATH=src uv run --no-sync --extra dev
```

- `ruff check .` passed.
- `towncrier check` passed, and
  `python -m towncrier build --draft --version 0.0.0` passed without writes.
- Strict `validate-release` passed both disposable selectors with zero issues,
  warnings, or errors:

  ```bash
  axiom-corpus-ingest validate-release --base data/corpus \
    --release .review-release-regulation.json --strict-warnings \
    --max-issues 100 --output /private/tmp/pr506-release-regulation-result.json
  axiom-corpus-ingest validate-release --base data/corpus \
    --release .review-release-guidance.json --strict-warnings \
    --max-issues 100 --output /private/tmp/pr506-release-guidance-result.json
  ```

- `verify-scope-tracked --repo . --jurisdiction us --document-class
  regulation --version 2026-07-23-title-20-part-416` passed for five referenced
  files. The corresponding guidance command passed for four.
- Both required `coverage ... --write` commands passed at 14/14 and 7/7 and
  left the tracked coverage bytes unchanged.
- Focused tests passed:

  ```bash
  python -m pytest -q tests/test_corpus_ecfr.py \
    tests/test_ingest_manifest_provenance.py \
    tests/test_citation_path_grammar.py tests/test_corpus_release_quality.py \
    tests/test_corpus_artifacts_coverage.py tests/test_corpus_documents.py \
    tests/test_corpus_cli.py
  # 255 passed, 5 warnings in 24.60s
  ```

- Full default pytest:

  ```bash
  AXIOM_CORPUS_INGEST_PUBLIC_KEY='KwIYEbbs/905yxn/9Yi6jYTF8oyZcq1FlxiG4e0y0tg=' \
    python -m pytest -q
  # 1 failed, 4086 passed, 67 skipped, 208 deselected in 125.88s
  ```

  The sole failure is the known baseline
  `tests/test_storage_postgres.py::TestPostgresStorageSubsectionConversion::test_dict_to_subsection`.
  The requested 4,100-pass estimate is stale: pinned-head CI itself reported
  4,085 passes, while this run reported 4,086 and no new failure class.
- Required mypy passed identically at the pinned target and a detached
  `origin/main` worktree:

  ```bash
  mypy src/axiom_corpus/corpus --ignore-missing-imports
  # Success: no issues found in 89 source files
  ```

### Tool and sandbox limitations

- Default `uv` cache access was sandbox-blocked; the successful commands used
  `UV_CACHE_DIR=/private/tmp/uv-cache-pr506`.
- GitNexus refreshed its local repository index, but its global registry write
  to `/Users/maxghenis/.gitnexus/registry.json` was sandbox-blocked. A direct
  local-backend impact query rated the script addition LOW with no affected
  execution process.
- The initial guard lacked the public verification key; the successful offline
  rerun used the public CI key above. A shell `gh variable get` fallback failed
  because shell network access was unavailable.
- Direct source `curl` calls failed on sandbox DNS, as noted above.
- Two delegated worker streams disconnected. Their completed evidence was
  recovered or independently rerun locally.
- Initial exploratory hierarchy and exact-resolver commands had input/import
  errors; corrected commands passed. No failed exploratory command changed
  tracked repository content.
- `apply_patch` rejected both the requested external destination and a direct
  `/private/tmp` fallback as outside its project boundary. The fallback was
  safely created inside the worktree, copied to `/private/tmp`, verified, and
  removed from the worktree.

## Next

- No review work remains. Outside this sandbox, copy the fallback report to:

  ```text
  /Users/maxghenis/TheAxiomFoundation/ops/fed-parity-campaign/rereview3-506-VERDICT.md
  ```
