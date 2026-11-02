# Release consolidation for the 2026-09-10 program ingestion (2026-09-11)

Controller pass that turned the 2026-09-10 program ingestion (265 complete scopes, 88,199
provisions, ten branches) into a successor selector that deep-validates with zero errors.
Everything here is local and unsigned; the artifacts are under `data/corpus` on the
controller's machine only.

Draft selector: `docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json`
(`us-rulespec-2026-09-11-program-ingestion-union`, 536 scopes, 263 unreleased). It is kept
outside `manifests/releases/` on purpose: CI deep-validates every tracked selector against the
checked-in `data/corpus`, so it can only be tracked on the release branch after the artifact
commit. `scripts/sign_release_scopes.sh` does that copy.

## Starting point

A draft successor (the released `us-rulespec-2026-08-23-canada-338-suspension-union`, 275
scopes, plus all 265 `2026-09-10*` scopes) failed `validate-release` with 8
`duplicate_release_citation` errors and 546 warnings (541 pre-existing `missing_parent_id`
warnings in the released `us-ca/regulation/2026-07-13-recovery` scope, plus 5 advisory
`unsectioned_document_body` warnings on single-body WIC and tax documents in GA, IA, KY, MD, OR).

| Collision | Scopes | Rows |
| --- | --- | --- |
| Colorado 9 CCR 2503-6 | released `us-co/regulation/2026-07-13-recovery` vs new `2026-09-10-tanf-state-policy-manual` | 3.606.1, 3.606.2, 3.606.6 with different text |
| Ohio OAC root | released `us-oh/regulation/2026-07-16-agency-5101-4` vs new `2026-09-10-tanf-state-policy-manual-agency-5101-1` and `2026-09-10-ssi-state-supplement-agency-5122-chapter-5122-36` | `us-oh/regulation` collection row |
| Maryland COMAR containers | new `...title-07-subtitle-03-chapter-06` vs `...chapter-07` | `us-md/regulation`, `title-07`, `title-07/subtitle-03` |

## What the Colorado collision actually is

The released recovery scope holds only three rows under `9-ccr-2503-6`, produced by a page
split: headings `Page 110`, `Page 53`, `Page 61`, and the body of `3.606.1` is the volume's
amendment-history page, not the section. The new TANF scope holds the whole rule (61 rows,
section-level, correct headings). `rulespec-us-co` cites `us-co/regulation/9-ccr-2503-6/3.606.1`
subsections E through H, which exist only in the new text. Keeping the released rows would have
served the wrong text; dropping the new rows (what `scripts/deduplicate_release_selector.py` does
by construction, since the released scope is canonical) would have removed the correct ones.

## Resolution: consolidated successor scopes

`scripts/deduplicate_release_selector.py` refuses both the Ohio case (two added scopes carry the
same path) and the Maryland case (removing a container would orphan a retained child), so the
tool used is `scripts/consolidate_release_scopes.py`, the same mechanism as the July 17
`-r2026-07-17-dedup` re-versions. It builds one immutable scope from ordered sources, treats
structurally identical container rows as one row, and requires an explicit carrier for
conflicting text. Released scopes are untouched; the selector swaps them for their successors.

```bash
uv run python scripts/consolidate_release_scopes.py --base data/corpus \
  --jurisdiction us-oh --document-class regulation \
  --source-version 2026-07-16-agency-5101-4 \
  --source-version 2026-09-10-tanf-state-policy-manual-agency-5101-1 \
  --source-version 2026-09-10-ssi-state-supplement-agency-5122-chapter-5122-36 \
  --target-version 2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated

uv run python scripts/consolidate_release_scopes.py --base data/corpus \
  --jurisdiction us-md --document-class regulation \
  --source-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapter-06 \
  --source-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapter-07 \
  --target-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07

uv run python scripts/consolidate_release_scopes.py --base data/corpus \
  --jurisdiction us-co --document-class regulation \
  --source-version 2026-07-13-recovery \
  --source-version 2026-09-10-tanf-state-policy-manual \
  --target-version 2026-07-13-recovery-r2026-09-11-tanf-consolidated \
  --prefer-duplicate-carrier us-co/regulation/9-ccr-2503-6/3.606.1=2026-09-10-tanf-state-policy-manual \
  --prefer-duplicate-carrier us-co/regulation/9-ccr-2503-6/3.606.2=2026-09-10-tanf-state-policy-manual \
  --prefer-duplicate-carrier us-co/regulation/9-ccr-2503-6/3.606.6=2026-09-10-tanf-state-policy-manual
```

| Consolidated scope | Sources | Rows | Check |
| --- | --- | ---: | --- |
| `us-oh/regulation/2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated` | 93 + 70 + 8 | 169 | two shared roots folded |
| `us-md/regulation/2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07` | 14 + 19 | 30 | three shared containers folded |
| `us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated` | 192 + 61 | 250 | 3.606.x bodies byte-equal to the TANF scope |

All three report complete coverage with no duplicate citations. The selector drops the seven
inputs (two released, five unreleased) and adds the three successors: 275 - 2 + 260 + 3 = 536
scopes. `validate-release --ignore-r2-missing` on the draft: `ok: true`, 0 errors, 546 warnings,
all as listed above.

Provision ids inside consolidated files derive from `(citation_path, version)`, while older
scope files derive from the citation path alone. This does not matter for serving: the
Supabase loader recomputes ids from `(citation_path, release version)` for every scope
(`deterministic_provision_id` in `src/axiom_corpus/corpus/supabase.py`), and RuleSpec
encodings reference citation paths, not ids.

The five superseded unreleased scopes (Colorado TANF, Ohio TANF and SSI, Maryland chapters 06
and 07) stay on disk for provenance but are not selected, committed or signed. The agent queue
rows and run notes still name them as extraction run ids; the selector is the release truth.

## Branch merge check

All ten branches merge cleanly onto `main` in one union after one fix: the Medicaid branch's
copy of `data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem` had CRLF line endings
and conflicted with the LF copy on the SSI, TANF and SNAP branches. Normalized to the TANF bytes
in `58e97801` on `discovery/ingest-medicaid` (pushed). On the union, `ruff check` passes and the
focused selection (`-k "manifest or official_documents or discovery"`) passes 298 with 2
skipped even without `data/corpus`, so the ten sparse-worktree failures noted in the hand-off do
not reproduce on a full merge.

## Controller commands from here

1. Merge #670 to `main`, then the nine program PRs (retarget to `main` or merge in order; they
   merge together cleanly).
2. Cut a release branch from `main`. Export `AXIOM_CORPUS_INGEST_PRIVATE_KEY` in that shell only.
3. `scripts/sign_release_scopes.sh docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json manifests/releases/us-rulespec-2026-08-23-canada-338-suspension-union.json`
   commits the 263 unreleased scopes' artifacts (about 2.2 GB; no file above 40 MB), signs
   them, tracks the selector and deep-validates it.
4. Open the PR; CI runs `guard-ingested` and validates the selector. Then
   `publish_corpus.py --release manifests/releases/us-rulespec-2026-09-11-program-ingestion-union.json --dry-run`
   and the protected `activate-release.yml` flow.

Disk: the controller machine had 2 GB free at one point during this pass. Stale worktrees from
other sessions under `/private/tmp` (`axiom-corpus-1248`, `axiom-corpus-620527`,
`de-kindergeld-closure`, about 29 GB together) and the 15 GB uv cache are the obvious reclaim
targets before the 2.2 GB data commit.
