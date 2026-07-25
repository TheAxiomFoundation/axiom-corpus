# Progress

## State

Part A is committed. Part B provenance/transcription preparation and final
repository-wide checks are in progress.

## Done

- Confirmed this worktree is detached at `origin/main`.
- Confirmed no pre-existing `PROGRESS.md` was present.
- Added row-level `metadata.content_flags.image_only_content` detection without
  changing provision bodies.
- Added one warning per affected provision and focused converter regressions.
- Committed Part A as `4102bf28`.
- Ran the production detector across all current German statute source XML:
  the two unique affected provisions are SGB IV § 20 and SGB VI § 255e.
- Focused Germany converter tests pass: 48 versus the 44-test baseline.

## Next

- Complete the unsigned SGB IV § 20 PDF provenance and draft ops manifest.
- Run focused and repository-required checks.
- Record final commit/diffstat, PDF provenance, transcription notes, manifest
  location, and test counts in the final report.
