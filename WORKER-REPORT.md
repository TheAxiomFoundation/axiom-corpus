# Worker Report — corpus PR B: 26 USC AMT and FTC sections

## Result

- Status: complete and locally committed
- Branch: `ingest/usc-amt-ftc-sections`
- Worktree: `/Users/maxghenis/TheAxiomFoundation/axiom-corpus/.claude/worktrees/usc-amt-ftc`
- Base: local `origin/main` at `db12795577c5809009168982cf8a72fb58440620`
- Head: `c2f51414d0f94a0d7f9d895b01a4bb3c550bbc93`
- Content commit attested by the manifest: `e10287a7bd785cdb15e06f62533bfc5bb8442741`
- Publication: none; no push, GitHub write, Supabase/R2 operation, or release activation was performed
- Report files: `PROGRESS.md` and `WORKER-REPORT.md` are intentionally untracked

The scope ingests official House USLM prelim-edition text for 26 USC §§27, 57, 58, 59, 901, 903, and 904. It also retains exactly one non-operative §902 repeal-status atom because surviving §904 cross-references require the repealed section to resolve. The §902 atom has official `status="repealed"`, an empty body, and no descendants.

## Commits

1. `1866069d` — `feat: preserve official USC section status`
2. `0e09c568` — `feat: ingest USC AMT and foreign tax credit sections`
3. `e10287a7` — `docs: validate USC AMT and FTC ingest`
4. `c2f51414` — `chore: record unsigned USC ingest attestation`

The unsigned attestation was committed last. `git merge-base --is-ancestor e10287a7bd785cdb15e06f62533bfc5bb8442741 HEAD` succeeds.

## Per-section rows and hashes

Each hash below is SHA-256 over the exact ordered JSONL bytes, including line endings, for all rows whose `citation_path` is the section root or one of its descendants.

| Section | Rows | JSONL byte-slice SHA-256 |
|---|---:|---|
| 26 USC §27 | 1 | `9e0b7ef56a3cfca880da6ca105311278347d8425af87843b76bb470824d3927f` |
| 26 USC §57 | 43 | `d8c4f94c91896d69a0d8a7aac4c8a599eb788f9eaa5604ba8d204d9b3d629c42` |
| 26 USC §58 | 17 | `c9e5541d41557dae6d66a4945debd8a35684859ca0b8298f80fc30f0ce8de72e` |
| 26 USC §59 | 98 | `1f5026693d65d67e0c1a773eab4d1c6b033a50b3127cd34b02b3111b0d269c39` |
| 26 USC §901 | 131 | `1f8a60b061978f6913543046e51aeeca622693236419e0e7ccc68833c14ecb0d` |
| 26 USC §902, repeal status only | 1 | `4314193b35c4a8f8320b3435e415e4337a76d05afd7a2637e79ffe85a4562d15` |
| 26 USC §903 | 1 | `98abf3551902eed45f9e79a7be1f25290771203eb02f120986c51db35c953857` |
| 26 USC §904 | 259 | `1c2cd379da327d17499d1bd652aa40fccaab7ad61d8dba673e537d56d8dcc222` |

Target-section subtotal: 551 rows. The scoped title atom adds one row, for 552 total inventory and provision rows.

## Source and artifact hashes

Official source archive:

`https://uscode.house.gov/download/releasepoints/us/pl/119/102not101/xml_usc26@119-102not101.zip`

Expression/source-as-of date: 2026-07-12 (`Online@119-102`).

| Artifact | SHA-256 |
|---|---|
| Official OLRC ZIP | `d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0` |
| Exact `usc26.xml` ZIP member | `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621` |
| Inventory | `de82b7579b32a189caf19df0ebd8d8ed5b1b916661ee78ecd41d0bf85aed705a` |
| Provisions JSONL | `c72f43dcf5cd1f8e53f1873f058bed0645fb02334cdb2a07ad37eff5f30f90c3` |
| Coverage | `e40f5f24236097db279ce42975bfad53d6a6537304c46db16df7f567d649dee0` |

The ZIP has one member, `usc26.xml`; its decompressed bytes are identical to the retained XML. No statutory source bytes were edited.

## Deterministic reproduction

Literal copy-pasteable command recorded in the ingest manifest:

```bash
PYTHONPATH=src uv run --no-cache --no-sync --extra dev python scripts/repro/us_usc_amt_ftc_sections.py --base data/corpus
```

The command completed successfully. A second reproduction under a fresh `/private/tmp` corpus base byte-compared all five scoped source/generated artifacts with `cmp`; every comparison passed.

## Structural findings

- Every official descendant identifier for the requested sections appears exactly once and in official document order.
- No requested section contains the duplicate-numbered enacted-sibling or mixed-part/subpart ordering patterns fixed by corpus PR #523.
- No new traversal regression was necessary; the existing full-title §45X regression continues to exercise that bug class.
- Section status was previously omitted by the generic USC adapter. The adapter now preserves an official section-level status in both inventory and provision metadata, with a focused regression proving the behavior.
- The §902 source element is officially marked repealed and contains no operative text or descendant provisions. It is included only to resolve surviving references, notably in §904, and must not be treated as a 2026 operative rule.

## Validation gates

- Focused USC, artifact, and citation tests: `50 passed`
- Full pytest: `4116 passed, 69 skipped, 208 deselected, 1 failed`
  - Sole failure: known baseline `tests/test_storage_postgres.py::TestPostgresStorageSubsectionConversion::test_dict_to_subsection`, a `MagicMock`/Pydantic validation failure in unrelated PostgreSQL storage code
- Ruff: clean
- Mypy for `src/axiom_corpus/corpus`: success across 89 files
- Towncrier check: fragment found; draft build succeeded
- Coverage: complete, 552/552 matched, 0 missing, 0 extra, 0 duplicates
- Targeted strict release validation: 0 issues, 0 warnings
- All release selectors: 78 validated, 0 failures
- Citation-path validation: 143,567 records and 125,041 unique paths; all live/baseline checks exact
- Citation census: `uppercase_segments` changed from 6,327 to 6,710; no identity drift
- Tracked-scope verification: `Verified 1 referenced files across 1 inventory scopes.`
- Final tracked diff check excluding the official XML: clean
- Final `git diff --name-only origin/main..HEAD`: reviewed; 14 files, all in this PR’s expected scope

`git diff --check` reports CRLF lines in the retained official XML as trailing whitespace. This is an expected byte-faithful-source exception: removing the carriage returns would change the official bytes. All other tracked files pass `git diff --check`.

## Signing status

Signing is incomplete by design because neither `AXIOM_CORPUS_INGEST_PRIVATE_KEY` nor `AXIOM_CORPUS_INGEST_PUBLIC_KEY` is available in this worker sandbox.

- `sign-ingest-manifest` exited 2 with: `AXIOM_CORPUS_INGEST_PRIVATE_KEY is required to sign ingest manifests.`
- An unsigned manifest was committed last at `.axiom/ingest-manifests/us/statute/2026-07-27-usc-amt-ftc-sections-title-26.json`.
- It attests the ancestor content commit `e10287a7bd785cdb15e06f62533bfc5bb8442741`, exact artifact hashes, coverage, reasoning log, and literal reproduction command.
- `guard-ingested` cannot pass here because `AXIOM_CORPUS_INGEST_PUBLIC_KEY` is absent; its only reported issue was the missing verification key.
- The main lane must sign this ingest manifest.

## Coordination and sandbox notes

- `schema/citation-path.v1.json` is a shared census artifact and may also be touched by concurrent corpus PR A (`ingest/usc-63-repair-165`). This branch records only PR B’s deterministic 6,327 → 6,710 update; resolve the combined census during integration rather than taking either branch’s baseline verbatim.
- `git fetch origin main` could not run because the sandbox could not resolve `github.com`; the worktree therefore uses the locally available `origin/main` named above.
- The default uv cache was outside writable sandbox scope, and network dependency resolution was unavailable. Checks ran with the repository’s existing environment plus `PYTHONPATH=src`; the temporary worktree symlink used for that environment was removed before handoff.
- GitNexus successfully analyzed the worktree but could not write its registration to `~/.gitnexus/registry.json` (`EPERM`). Required pre-edit impact analysis ran against the registered prior index: `UscSection` was MEDIUM risk, `_iter_sections` LOW, and `_section_metadata` HIGH; the HIGH blast radius was disclosed before editing and its direct callers were covered. Final `detect_changes` could not target the unregistered checkout and returned “Repository ... not found.”

## Final tracked file list

```text
.axiom/ingest-manifests/us/statute/2026-07-27-usc-amt-ftc-sections-title-26.json
changelog.d/usc-amt-ftc-sections.added.md
data/corpus/coverage/us/statute/2026-07-27-usc-amt-ftc-sections-title-26.json
data/corpus/inventory/us/statute/2026-07-27-usc-amt-ftc-sections-title-26.json
data/corpus/provisions/us/statute/2026-07-27-usc-amt-ftc-sections-title-26.jsonl
data/corpus/sources/us/statute/2026-07-27-usc-amt-ftc-sections-title-26/olrc/xml_usc26@119-102not101.zip
data/corpus/sources/us/statute/2026-07-27-usc-amt-ftc-sections-title-26/uslm/usc26.xml
docs/ingest-runs/2026-07-27-usc-amt-ftc-sections.md
manifests/releases/us-2026-07-27-usc-amt-ftc-sections.json
schema/citation-path.v1.json
scripts/repro/us_usc_amt_ftc_sections.py
src/axiom_corpus/corpus/usc.py
tests/test_corpus_usc.py
tests/test_us_usc_amt_ftc_sections.py
```
