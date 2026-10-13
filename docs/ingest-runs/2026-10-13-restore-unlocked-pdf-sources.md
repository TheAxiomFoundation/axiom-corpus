# Restore five PDF sources that committed rows named but no lock listed

Run date: 2026-10-13

Nine scopes had committed `source_format: pdf` provision rows whose
`source_path` named a PDF that no `.axiom/corpus-locks/` lock listed, so the
rows could not be re-extracted or checked against their source. They were found
while re-extracting every committed PDF for the PyMuPDF comparison
(axiom-corpus#867), at `origin/main` 460549782. The original bytes of five of
the nine survived. This run restores those five through the signed path. The
other four, all Belgian, are recorded in
[axiom-corpus#872](https://github.com/TheAxiomFoundation/axiom-corpus/issues/872).

None of the nine files was ever committed to git or listed in any signed ingest
manifest, and R2 held none of them under a path key. Each ingest had committed
its provisions (later its inventory and coverage) without the PDF.

## What was restored

| Scope | File | sha256 | Bytes | Where the bytes were |
| --- | --- | --- | ---: | --- |
| `us-ny/policy/2026-06-05-ny-tanf` | `ny-otda-tanf-state-plan-2024-2026.pdf` | `f222c331…94c2f` | 856,867 | R2, locked by `us-ny/policy/2026-08-03-ny-tanf-official-source-recovery` |
| `us-sd/manual/2026-05-27-sd-snap-manual` | `sd-dss-snap-policy-procedure-manual.pdf` | `9b2d299b…3cba9` | 2,749,383 | only in the checkout that ran the ingest (`~/TheAxiomFoundation/axiom-corpus-wave1`) |
| `us-va/manual/2026-05-27-va-snap-manual` | `va-dss-snap-full-manual-2025-10-01.pdf` | `9868c25c…e8d8a` | 8,147,430 | R2, locked by `us-va/manual/2026-07-21-va-snap-manual` |
| `us-wi/manual/2026-05-27-wi-foodshare-manual` | `wi-dhs-foodshare-handbook-26-01.pdf` | `6e76d771…850d7` | 2,685,819 | R2, locked by `us-wi/manual/2026-07-21-wi-foodshare-manual` |
| `us/guidance/2026-07-08-snap-qc-fy2024-technical-documentation` | `snap-qc-fy2024-technical-documentation.pdf` | `59b6999d…37e33` | 4,345,993 | only in the checkout that ran the ingest (`~/TheAxiomFoundation/_worktrees/axiom-corpus-snap-fy2024`) |

Full digests are in `scripts/restore_unlocked_pdf_sources.py`.

## Why these are the original bytes

Three independent kinds of evidence, at least two for every file:

1. **A hash recorded at ingest time.** The SNAP QC inventory committed in
   axiom-corpus#282 gives `sha256` `59b6999d…` for all 201 items, and the New
   York inventory committed in axiom-corpus#85 gives `f222c331…` for all 115.
   Both inventories are still the locked ones; each names the same
   `source_path` as its rows.
2. **The file the ingest wrote.** The South Dakota, Virginia and Wisconsin
   PDFs were still at their exact `data/corpus/sources/…` paths in
   `axiom-corpus-wave1`, the clone that ran the state SNAP manual batch
   (axiom-corpus#59, #61), with birth times of 2026-05-27 06:18 to 09:10
   local time. The
   SNAP QC PDF was at its exact path in `axiom-corpus-snap-fy2024`, written
   2026-07-08 12:31. The Virginia and Wisconsin files hash to the objects the
   2026-07-21 successor scopes already lock, so those bytes were in R2 all
   along.
3. **Re-extraction reproduces the committed rows.** The extractor at each
   ingest's commit (5e77f4b27, a5d9b220a, cbf189403, 7d18a1102; each locks
   PyMuPDF 1.26.7), given the restored file through its manifest's
   `local_path`, reproduces every committed row in every field except two that
   depend on the download rather than the PDF: `metadata.download_url` (a
   local run records `file://…`) and `metadata.content_type` (taken from the
   HTTP response). That covers ids, bodies, headings, ordinals and dates.

   | Scope | Rows reproduced | Other committed rows |
   | --- | ---: | --- |
   | New York TANF | 115 | 4 hand-segmented `section` rows from axiom-corpus#85, every sentence of which appears verbatim in the extracted pages |
   | South Dakota SNAP | 339 | none |
   | Virginia SNAP | 676 | none |
   | Wisconsin FoodShare | 373 | none |
   | SNAP QC technical documentation | 201 | none |

   `scripts/repro/reextract_restored_pdf_sources.py` reruns all five
   comparisons from the locked bytes.

The comparison also explains a difference that looked like a revision. The
Virginia rows of 2026-05-27 and 2026-07-21 differ on their last pages
(678 rows against 676), yet both were extracted from the same bytes; the
extractor changed between May and July. The South Dakota manual, by contrast,
was revised: the 2026-07-21 capture (`a52d596a…`, 2,773,728 bytes) is the July
2026 edition, and its rows differ from these on 306 of 339 pages.

## The SNAP QC rename

`extract-official-documents --only-source-id` writes a run named after the
version with the source id appended. Axiom-corpus#282 committed that run's
provisions, inventory and coverage under the plain version
`2026-07-08-snap-qc-fy2024-technical-documentation`, but left their contents
naming the run id
`2026-07-08-snap-qc-fy2024-technical-documentation-snap-qc-fy2024-technical-documentation`:
each row's `version` and `source_path`, each inventory item's `source_path`,
and the coverage `version`. The PDF stayed under the run id's directory, which
is why the rows pointed outside their own scope (and why Supabase staged the
201 rows under the run id).

The restore finishes that rename instead of adding a second scope that holds
only a PDF (no lock in the corpus has that shape). It rewrites exactly those
fields and places the PDF in the scope's own directory. The rewritten artifacts
are what the axiom-corpus#282 extractor writes for the plain version: run
without `--only-source-id`, it produces the same rows, inventory and coverage
from the restored PDF, except the two download fields above, which keep their
original values.

## Commands

```bash
uv run --extra dev python scripts/restore_unlocked_pdf_sources.py \
  --from 9b2d299bf6637787306c3ba8571fb19aa5a64e2f24e42b265abb328bd5f3cba9=$HOME/TheAxiomFoundation/axiom-corpus-wave1/data/corpus/sources/us-sd/manual/2026-05-27-sd-snap-manual/official-documents/sd-dss-snap-policy-procedure-manual.pdf \
  --from 59b6999d1b9e51ebe920e00899d9aab066d69f1227ea83b0a3e9f16fd8137e33=$HOME/TheAxiomFoundation/_worktrees/axiom-corpus-snap-fy2024/data/corpus/sources/us/guidance/2026-07-08-snap-qc-fy2024-technical-documentation-snap-qc-fy2024-technical-documentation/official-documents/snap-qc-fy2024-technical-documentation.pdf

# Then, from a clean tracked tree, for each of the five scopes:
uv run --extra dev axiom-corpus-ingest sign-ingest-manifest \
  --jurisdiction <j> --document-class <c> --version <v> \
  --command "<restore command>" --lock --push
```

With the bytes in R2 after `--push`, `scripts/restore_unlocked_pdf_sources.py`
needs no `--from`, and `--check` verifies a checkout.

## What this changes

- Each of the five scopes gains its PDF in its lock and a newly signed
  manifest attesting all of its files.
- The SNAP QC scope's provisions, inventory and coverage change as described
  above; the other four scopes' existing artifacts are unchanged.
- Nothing served changes. No tracked selector and no published release includes
  any of the five scopes, and no row of theirs is served (Supabase,
  2026-10-13). The South Dakota, Virginia and Wisconsin scopes are superseded by
  their 2026-07-21 successors, which the US selectors use; the New York scope by
  `2026-08-03-ny-tanf-official-source-recovery` and its 2026-08-09 alias scope.
