# Child tax credit source history (issue #744)

This run implements [axiom-corpus#744](https://github.com/TheAxiomFoundation/axiom-corpus/issues/744)
(decision d256): official P.L. 115-97 §11022 and P.L. 119-21 §70104, plus a dated
prior expression of 26 U.S.C. §24. All artifacts remain **unsigned**. The
dispatcher signs the ingest manifests after review. No R2 upload, Supabase load,
release publication, registration, or activation was run.

This is source ingestion only. It does not change RuleSpec or establish that an
encoder can now answer every historical tax year. In particular, the historical
section includes the separate special rules for 2021; $2,000 must not be treated
as the universal 2021 credit. Per the work order, TY2018–2024 remain fail closed
until the supervised encoder can ground its answers from appropriate sources.
The annual IRS revenue procedures mentioned in the issue are outside this
work order and are not ingested here.

## Sources and identities

| Scope under `us/statute` | Source | Expression date |
| --- | --- | --- |
| `2026-09-27-ctc-history-public-laws` | [P.L. 115-97 USLM](https://www.govinfo.gov/content/pkg/PLAW-115publ97/uslm/PLAW-115publ97.xml), §11022 | 2017-12-22 |
| same | [P.L. 119-21 USLM](https://www.govinfo.gov/content/pkg/PLAW-119publ21/uslm/PLAW-119publ21.xml), §70104 | 2025-07-04 |
| `2026-09-27-ctc-history-rp-118-209-title-26` | [OLRC prior release point 118-209, except 118-159](https://uscode.house.gov/download/releasepoints/us/pl/118/209not159/xml_usc26@118-209not159.zip), §24 | 2024-12-23 |

The public-law manifest is `manifests/us-ctc-history-public-laws.yaml`. Each
scope retains all four artifact kinds under `data/corpus/{sources,inventory,
provisions,coverage}/us/statute/`. The source snapshots are complete official
files; the normalized rows are explicitly scoped to the selected sections.
Dates for public laws come from USLM `approvedDate`; tax-year applicability stays
in the provisions' bodies. The historical USC expression uses the release-point
date for both `source_as_of` and `expression_date`, as in
[PR #732](https://github.com/TheAxiomFoundation/axiom-corpus/pull/732).
It is the precisely identified OLRC release point, not a claim to be the GovInfo
2024 annual edition. The downloaded ZIP matches #732's retained source SHA-256:
`92e448a694abbf65e8c7272ec88be3bf9e57818cb3d1cc7bc2624b937cb83148`.
The public-law XML snapshots hash to
`cefc985106e4c648ac16698ee693d115623bd560fc9e10e680832020bff182c3`
(115-97) and
`762ae9af06640f023ddb9eb6f474ff7cfa275691de338d4fd985cfb04a7b6dea`
(119-21).
The `usc26.xml` member hashes to
`d8c9b276af1ffec7da5ba416be8888726d44b6e0de2a2df4f5a2b6fd0d720bec`.

[PR #349](https://github.com/TheAxiomFoundation/axiom-corpus/pull/349) supplies a
source-law fixture and ingest-manifest precedent, but its records are codified
USC provisions from a bridge source, not public-law paths. Existing P.L. 119-21
Medicaid snapshots also project quoted USC text (`us/statute/42/1396a/xx`). This
run adds a documented public-law family in `schema/citation-path.v1.json`,
following the official USLM `/us/pl/<congress>/<number>` identity:

- `us/statute/pl/115/97/11022`, `/a`, `/b` (plus the law container).
- `us/statute/pl/119/21/70104`, `/a`, `/a/1`, `/a/2`, `/a/3`, `/b`, `/c`, `/d`,
  `/e`, `/f` (plus the law container).
- `us/statute/26/24` and its published descendants. Historical and current USC
  paths are identical; `version` and `expression_date` distinguish expressions.
  No date segment is invented and no existing current-text scope is modified.

The new `extract-public-laws` adapter writes 15 rows, validates the XML identity
against the govinfo package URL, rejects missing/ambiguous selected sections,
and preserves quoted replacements inside the amending provision. It does not
execute amendments or emit quoted USC subsections as public-law descendants.
All 13 text-bearing public-law rows were compared independently against their
selected source XML element: text matches after removing whitespace, layout
markers, and the provision's separately stored own heading/number.

## Reproduce from official sources

```bash
mkdir -p /tmp/ctc-history-sources
curl -fL --retry 3 https://www.govinfo.gov/content/pkg/PLAW-115publ97/uslm/PLAW-115publ97.xml \
  -o /tmp/ctc-history-sources/PLAW-115publ97.xml
curl -fL --retry 3 https://www.govinfo.gov/content/pkg/PLAW-119publ21/uslm/PLAW-119publ21.xml \
  -o /tmp/ctc-history-sources/PLAW-119publ21.xml
uv run axiom-corpus-ingest extract-public-laws --base data/corpus \
  --version 2026-09-27-ctc-history-public-laws \
  --manifest manifests/us-ctc-history-public-laws.yaml \
  --download-dir /tmp/ctc-history-sources

curl -fL --retry 3 \
  'https://uscode.house.gov/download/releasepoints/us/pl/118/209not159/xml_usc26@118-209not159.zip' \
  -o '/tmp/ctc-history-sources/xml_usc26@118-209not159.zip'
uv run axiom-corpus-ingest extract-usc --base data/corpus \
  --version 2026-09-27-ctc-history-rp-118-209 \
  --source-zip '/tmp/ctc-history-sources/xml_usc26@118-209not159.zip' \
  --title 26 --section 24 --source-as-of 2024-12-23 --expression-date 2024-12-23 \
  --source-url 'https://uscode.house.gov/download/releasepoints/us/pl/118/209not159/xml_usc26@118-209not159.zip' \
  --prior-release-point
uv run python scripts/self_contain_usc_scope.py --base data/corpus \
  --version 2026-09-27-ctc-history-rp-118-209-title-26

for version in 2026-09-27-ctc-history-public-laws 2026-09-27-ctc-history-rp-118-209-title-26; do
  uv run axiom-corpus-ingest coverage --base data/corpus \
    --source-inventory "data/corpus/inventory/us/statute/${version}.json" \
    --provisions "data/corpus/provisions/us/statute/${version}.jsonl" \
    --jurisdiction us --document-class statute --version "$version" --write
done
```

The public-law regression tests verify §70104(a)(2)'s strike/insert, the replacement
SSN rule in (b), replacement §24(i) in (c), replacement §24(h)(5) in (d), and the
post-2024 applicability in (f). They also verify TCJA's $2,000 credit, old
refundable-cap indexing and child SSN text, and post-2017 applicability.
Historical §24 directly supplies `h/2`, `h/5/B`, `h/7`, and the old 2021 `i`.
Its 115 rows comprise one section, 11 subsections, 28 paragraphs, 35
subparagraphs, 25 clauses, and 15 subclauses. The section root records its
detached `us/statute/26` parent in metadata; every remaining parent is in scope.
Both scope coverage reports are complete with no missing, extra, or duplicate
citations (15/15 and 115/115).

## Draft releases and exact dispatcher handoff

Two inert draft selectors live next to this note, outside `manifests/releases/`:

- `2026-09-27-ctc-history-public-laws.selector.json`: the tracked
  `us-rulespec-2026-09-14-wave4-r2-union` plus the new public-law scope (1,043
  scopes). **Unverified:** this baseline's equality to production serving state.
  The dispatcher must reconcile against the applicable active union before
  canonical promotion, preserving every existing served `(us, statute)` scope.
- `2026-09-27-ctc-history-rp-118-209.selector.json`: one historical scope for a
  publish-only immutable release. **Never activate this minimal historical
  release.** Current and historical citation paths overlap; a union carrying
  both expressions fails release-wide citation uniqueness. Activation replaces
  the whole `(us, statute)` pair and would regress serving.

Remaining steps, owned by the dispatcher/authorized publication operator:

1. On the clean reviewed artifact commit, run `sign-ingest-manifest` for **each**
   of the two scope versions, using the authorized signing environment. This
   task reads no secrets and creates no signatures. Example (repeat with the
   other version and its recorded extraction command):

   ```bash
   uv run axiom-corpus-ingest sign-ingest-manifest --repo . --base data/corpus \
     --jurisdiction us --document-class statute \
     --version 2026-09-27-ctc-history-public-laws \
     --command 'axiom-corpus-ingest extract-public-laws --base data/corpus --version 2026-09-27-ctc-history-public-laws --manifest manifests/us-ctc-history-public-laws.yaml' \
     --reasoning-log docs/ingest-runs/2026-09-27-ctc-history.md
   ```

   Commit the resulting `.axiom/ingest-manifests/us/statute/<version>.json`
   before running `uv run axiom-corpus-ingest guard-ingested --base-ref origin/main
   --head-ref HEAD`. Unsigned artifact changes are
   expected to fail CI's ingest guard; do not bypass it.

2. Reconcile the public-law union, review both selectors, and promote only an
   authorized selector to `manifests/releases/<immutable-name>.json`. Run the
   clean-checkout checks and `publish_corpus.py --dry-run` from
   `SIGNING-RUNBOOK.md`. A docs-directory draft can instead be locally checked
   with `validate-release --ignore-r2-missing`.

3. Publish and register via the repository's protected workflow (either the
   canonical selector merge trigger or an explicit dispatch):

   ```bash
   gh workflow run publish.yml -R TheAxiomFoundation/axiom-corpus \
     --ref main -f release=<immutable-name>
   ```

   `.github/workflows/publish.yml` signs/uploads/stages and registers the
   verified release via `scripts/stage_release_object.py`; it does **not**
   activate. Keep its run ID, signed object, release name, and content SHA.
   Historical JSONL or published immutable artifacts require a consumer that
   explicitly selects the historical version. Encoder consumer compatibility
   is **unverified** by this corpus task.

4. For the reconciled **full public-law union only**, obtain separate activation
   authorization, preview every takeover, then request protected approval:

   ```bash
   gh workflow run activate-release.yml -R TheAxiomFoundation/axiom-corpus \
     --ref main -f publish_run_id=<id> -f release=<name> \
     -f content_sha=<sha> -f request_activation=false
   # Only after reviewing the preview and receiving activation authorization:
   gh workflow run activate-release.yml -R TheAxiomFoundation/axiom-corpus \
     --ref main -f publish_run_id=<id> -f release=<name> \
     -f content_sha=<sha> -f request_activation=true
   ```

   The authorized operator approves the `release-activation` environment. No
   activation step is appropriate for the historical-only selector.

## Validation

Final command results are recorded below before the draft PR handoff.

- `uv run --extra dev ruff check .`: passed.
- `uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports`:
  passed, 94 source files.
- `.venv/bin/python -m pytest -q tests/test_corpus_public_laws.py`: 13 passed,
  including real-source regressions and CLI extraction.
- `.venv/bin/python -m pytest -q tests/test_corpus_ctc_history.py`: 1 passed.
- Explicit `coverage --write` on each scope: complete, 15/15 and 115/115.
- Independent source/selector review: all 13 text-bearing public-law bodies
  preserve XML text; historical inventory, hashes, dates, and parents match;
  the draft union preserves all 1,042 baseline scopes and has no new
  public-law citation collision against its US statute scopes.
- Full offline pytest, whole-suite pytest, citation-path validation and deep
  release validation: results pending at the initial artifact commit; the
  final handoff records their results.

GitNexus: the pre-existing index failed with database-format mismatch (42 vs
40). A full workspace rebuild stalled while parsing; a bounded fresh index of
`cli.py`, `public_laws.py`, `test_corpus_cli.py`, and
`test_corpus_public_laws.py` succeeded (329 nodes, 711 edges, 13 flows).
Upstream `build_parser` impact is MEDIUM: direct production caller `main`, with
CLI tests downstream. The new extractor's impact is LOW. Staged
`detect_changes` returned HIGH across 47 symbols/10 flows in the three expected
feature files, including unchanged CLI functions. This warning was reviewed:
AST comparison with `origin/main` finds only `build_parser` changed and
`_cmd_extract_public_laws` added; no existing function removed. Existing
subcommand dispatch remains unchanged and is covered by CLI tests. This is a
bounded graph check, not a claim of full-repository graph coverage.

Workspace note: the supplied detached worktree's Git metadata was outside the
writable sandbox. The task used workspace-local Git metadata and a branch from
`origin/main` (`f1916d73b568616cbd0b4c3c26a92796835188d9`), without writing to the
caller's checkout. During the tree update, historical extraction used the
existing `extract_usc` Python API with the exact CLI-equivalent arguments above;
self-containment and the explicit coverage CLI then completed successfully.
