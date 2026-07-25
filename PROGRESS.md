# Progress

## State

Part A and its repository checks are complete. Part B's transcription and
unsigned manifest draft are prepared in `scratch/`, but the PDF byte capture
and requested `ops/` copy are blocked by this environment's network and
filesystem sandbox.

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
- Repository-wide Ruff passes.
- The full suite completed with 4,085 passed, 68 skipped, 208 deselected, and
  one reproducible unrelated failure in
  `tests/test_storage_postgres.py::TestPostgresStorageSubsectionConversion::test_dict_to_subsection`.
- The required repository-wide mypy check reports 180 existing errors across
  26 unrelated files and none in `germany_gii.py`.
- `towncrier check` reports no news fragment; this task explicitly restricts
  Part A changes to `src/` and `tests/`.
- Prepared and schema-validated the unsigned draft at
  `scratch/de-sgb4-20-supplement/de-sgb4-20-supplement-manifest.draft.yaml`.
- Verified the formulas are raster-only on PDF page 26 and that § 20 continues
  to page 27, where § 21 begins; the draft captures pages 26–27 and stops at
  § 21.
- Confirmed no safe route to exact PDF bytes: shell egress is blocked, the web
  reader exposes extracted text rather than a file, and no matching local
  cached copy exists. No retrieval timestamp or SHA-256 was invented.

## Next

- From an environment with outbound access, download
  `https://www.gesetze-im-internet.de/sgb_4/SGB_4.pdf` into the scratch
  directory, record its UTC retrieval timestamp and SHA-256, and replace the
  draft's provenance TODOs.
- Render and inspect pages 26–27, then run the forced-OCR extraction and verify
  that both stacked fractions and multiplication signs survive faithfully.
- Copy the reviewed draft to
  `/Users/maxghenis/TheAxiomFoundation/ops/de-lane/de-sgb4-20-supplement-manifest.draft.yaml`
  from a filesystem context that can write the ops tree.
- Review and sign only from the clean-root workflow requested by the user.
