# Successor scopes for the fixed hollow-document-root findings

Date: 2026-10-13.
Branch `ingest/hollow-root-successors`: #854's head (`abca5403c`) with `origin/main`
(`91d69e6d3`) merged in.
Builder: `scripts/repro/hollow_root_successors.py`.
Per-scope figures: `docs/ingest-runs/2026-10-13-hollow-root-successors.json`.

The hollow-document-root audit
([#853](https://github.com/TheAxiomFoundation/axiom-corpus/pull/853),
`docs/ingest-runs/2026-10-13-hollow-document-root-audit.md`) classified the 188
`hollow_document_root` findings in #847's release content baseline. It traced 93 of
them to extractor or builder defects that are now fixed: 92 by
[#854](https://github.com/TheAxiomFoundation/axiom-corpus/pull/854) and one by
477c6650c, already on `main`. Merged scopes are immutable, so a fix reaches the corpus
only through a successor scope. This run builds one successor for each of the 108
scopes those fixes change. It also prepares three draft successor selectors.

Nothing is published, loaded into Supabase or activated. No tracked selector is added
or changed.

## Scopes

Each successor's version is its original's with `-r2026-10-13-hollow-roots` appended,
as for the committed `-rYYYY-MM-DD-` successors. It keeps the original's capture date
and sorts after it, so the release gate's `scope_monotonicity` check reads the swap as
an advance.

| Family | Originals | How the successor is rebuilt | Fix it carries |
| --- | ---: | --- | --- |
| NYCRR | `us-ny/regulation/2026-09-14-income-tax-regulations`, `us-ny/regulation/2026-07-17-ny-snap-regulations` | `extract_nycrr_parts` over a copy of the retained Westlaw pages and Register PDFs, with each manifest and the original `--source-as-of`/`--expression-date` | Part Notes pages keep their `.co_refsAnnos` text (`nycrr._document_body`) |
| CMS state plans | the 102 `us-xx/policy/2026-09-13-{medicaid,chip}-state-plan` scopes | `extract_official_documents` with each state's manifest, the retained bytes served in place of the download | `INDEX_PAGE_EXTRACTION` on the 240 SPA index pages (one block per SPA); the OCR overlay rule for scanned attachment pages |
| CHIP FCEP | `us/policy/2026-07-05-cms-chip-fcep-spa` | as above | `html_text_selector: .grid-row > div` on the 36 summaries |
| Maryland TCA | `us-md/statute/2026-07-03-md-tca-statutes` | as above, `--source-as-of`/`--expression-date` 2026-07-03 | `html_text_selector: '#StatuteText'` with `html_br_breaks` |
| Massachusetts TAFDC | `us-ma/regulation/2026-06-27-ma-tafdc-regulations` | as above | 106 CMR 701/702 start markers that occur in their DOCX |
| Canada | `ca/policy/2026-07-21-ca-rulespec-source-complete` | `scripts/build_ca_rulespec_composite_scope.py` recomposes the merged scope, as the oracle-complete v2 scope was recomposed from oracle-complete | the composer drops an empty `/primary-document` clone of an empty program root (477c6650c) |

## Method

```bash
uv run --extra dev python scripts/repro/hollow_root_successors.py build \
  --base data/corpus --workers 4 --ocr-cache <dir>
```

- **No fetch.** The builder blocks every IP connection for the run (`block_network`),
  so a source missing from the retained bytes fails the scope instead of being fetched.
  - Official documents: the builder serves each manifest document from its original's
    retained file, found through the original inventory's `document` row. It passes
    the content type and final URL that row recorded, and checks the file against the
    row's SHA-256.
  - NYCRR: the adapter reads a page from the scope's own source directory before it
    fetches. The builder copies the retained pages there first and gives the adapter a
    session that refuses every request.
  - Canada: the composer reads only the merged scope.
- **Same bytes.** After each build, the successor's source files must equal the
  original's, path for path and byte for byte. The Canadian composer nests a source
  scope's files under that scope's version, so there the check maps
  `<original>/<path>` to `<successor>/<original>/<path>`. On APFS, each verified source
  is then replaced by a copy-on-write clone of the retained file, so the successors'
  @@SRCBYTES@@ of sources share blocks with the originals on disk.
- **Same defaults.** `extract_official_documents` derives a document's missing
  `source_as_of` and `expression_date` from `--source-as-of`, else from the version.
  The builder passes the original command's flags where it had them, and otherwise
  the original version, so no default moves with the new version string.
- **Tesseract.** The 102 state-plan manifests set `ocr: true` on their PDFs. Tesseract 5.5.3
  output is cached by the SHA-256 of the exact page image it is given (with dpi,
  language and page segmentation mode), so the control build below reads the same OCR
  text as the successor build without running Tesseract again.

### Control: the same builder with `origin/main`

To separate #854's changes from any other drift since the originals were extracted,
the builder ran a second time from a checkout of `origin/main` (`91d69e6d3`, without
#854), with that checkout's code and manifests, into a scratch base. Every
`--left original` comparison below normalizes only what a new version must change:
each row's `version`, and the version segment of each source path (at any depth, so
the NYCRR amendment paths inside `metadata` are included). Row ids are compared by
rule: the shared extractor and the NYCRR adapter emit path-only ids, the composer
path-and-version ids.

@@CONTROL@@

@@RESULTS@@

## Successor selectors

Tracked selectors are immutable, so none is edited. Since 35b8ce300, merging a selector
no longer publishes it (`publish.yml` runs only on a manual dispatch); the drafts still
sit under `docs/ingest-runs/`, because cutting a release is a release decision. Each is
its base selector with every selected original replaced in place by its successor, and
`name` and `description` changed; the other scopes, their order and the quality profile
are unchanged:

| Draft | Base (newest tracked cut of its line that selects an original) | Swapped |
| --- | --- | ---: |
| `2026-10-13-hollow-root-successors-union.selector.json` (`us-rulespec-2026-10-13-hollow-root-successors-union`) | `us-rulespec-2026-10-13-w7-bundle-gaps-union` (1,567 scopes) | 107 |
| `2026-10-13-hollow-root-successors-snap.selector.json` (`us-rulespec-2026-10-13-snap-fy2026-hollow-root-successors`) | `us-rulespec-2026-10-13-snap-fy2026-memo-source-corrected` (272) | 3: FCEP, MA TAFDC, NY SNAP regulations |
| `2026-10-13-hollow-root-successors-ca.selector.json` (`ca-rulespec-2026-10-13-source-complete-hollow-roots`) | `ca-rulespec-2026-07-21-source-complete` (1) | 1 |

46 tracked selectors select at least one original. Six union cuts select all 107 US
originals, `us-rulespec-2026-09-13-cms-state-plans-union` selects 106, and the others
select between one and four.

To swap the successors into whichever cut lands next in a line (for example
#860's `us-rulespec-2026-10-13-ca-concurrent-versions-union`, which is the w7 union plus
one scope), run:

```bash
uv run --extra dev python scripts/repro/hollow_root_successors.py selector \
  --base-selector manifests/releases/<base>.json --name <new name> --output <path>
```

- **Never select an original with its successor.** They share every citation path the
  fix did not change, which gives one `duplicate_release_citation` error per path. Do
  not resolve that with `scripts/deduplicate_release_selector.py`, which would delete
  the successor's colliding rows. `swap_successors` refuses a selector that already
  selects a successor.
- **The union line also owes #847's swaps.** Once #847 merges, a new union cut must
  also drop or replace the scopes `manifests/withdrawn-scopes.yaml` lists. The w7
  union is grandfathered at its own digest only, so the union draft above, like any
  new cut of that line, fails `withdrawn_scope_selected` under #847's gate until it
  takes those swaps too.
- **Canada.** `ca-rulespec-2026-07-21-oracle-complete-v2` already carries the same
  normalization, composed with the executable-oracle sources. The source-complete
  successor serves a cut of the source-complete line only.

@@CHECK847@@

