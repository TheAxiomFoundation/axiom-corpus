# Successor scopes for the fixed hollow-document-root findings

Date: 2026-10-13, updated 2026-10-15 for #868.
Branch `ingest/hollow-root-successors`, on `origin/main` (merged in at `0f4e8a2dd`), which
includes #854 (merged as f98fa2bbd) and #868 (merged as 38d893d50).

- **First build.** 46 successors were built at `acf071fe1`: #854's head with `origin/main`
  `91d69e6d3` merged in, a tree identical to #854's merged head. The other 62 were built
  at this branch's `0b1ae81b6`. Between those two commits, `main` changed no extraction
  code, composer or manifest these scopes use.
- **Rebuild after #868.** All 108 were rebuilt at `0f4e8a2dd`, once #868's OCR overlay
  merge rule was on `main`.
  - 57 rebuilt byte for byte (inventory, provisions and coverage), and their manifests
    stand.
  - The other 51 are exactly the state-plan scopes on #868's scope list. They differ
    only in 360 PDF page bodies: no row, inventory item, coverage figure or source
    changes. They were replaced and re-signed.
Builder: `scripts/repro/hollow_root_successors.py`.
Per-scope figures: `docs/ingest-runs/2026-10-13-hollow-root-successors.json`.
Evidence (comparisons, content-check and validation output, logs and the scripts that
made them), on the machine that built the scopes:
`~/reviews/axiom-corpus-hollow-root-successors-2026-10-13/`.

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
  3.64 GB of sources share blocks with the originals on disk.
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

Of the 108 control builds, 107 reproduce their originals exactly: the same rows in
the same order, the same inventory items and coverage report, and the same source
bytes. The exception is the Canadian scope, whose control already drops the empty
`/primary-document` leaf, because the composer fix (477c6650c) is on `main`; its
control and successor are identical. So, in the first build, every difference between
an original and its successor came from #854, or for Canada from 477c6650c, and none
from other changes since the originals were extracted. The final successors also carry
#868: in the rebuild after it, the only further differences are 360 PDF page bodies in
the 51 state-plan scopes on its list (see the header).

## Results

Per-scope figures, including every removed path, are in
`docs/ingest-runs/2026-10-13-hollow-root-successors.json`.

| Family | Scopes | Source files | Rows before | Rows after | Added | Removed | Changed | Body characters before | after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| NYCRR | 2 | 364 | 3,693 | 3,693 | 0 | 0 | 46 | 3,604,185 | 3,611,913 |
| CMS Medicaid state plans | 51 | 2,294 | 31,251 | 47,551 | 16,300 | 0 | 1,350 | 57,536,899 | 62,470,573 |
| CMS CHIP state plans | 51 | 935 | 33,871 | 34,826 | 955 | 0 | 144 | 68,434,080 | 68,688,215 |
| CHIP FCEP | 1 | 76 | 2,347 | 2,347 | 0 | 0 | 36 | 4,847,709 | 4,855,993 |
| Maryland TCA | 1 | 2 | 6 | 4 | 0 | 2 | 4 | 2,562 | 9,258 |
| Massachusetts TAFDC | 1 | 8 | 216 | 289 | 73 | 0 | 2 | 431,544 | 534,088 |
| Canada | 1 | 197 | 461 | 460 | 0 | 1 | 0 | 6,094,075 | 6,094,075 |
| **Total** | **108** | **3,876** | **71,845** | **89,170** | **17,328** | **3** | **1,582** | **140,951,054** | **146,264,115** |

- **In every scope** the sources are the original's bytes, coverage is complete, the
  rows that remain keep their order, and ids follow the original's rule (path-only
  for 107 scopes, path and version for the Canadian composite).
- **NYCRR.** The 46 changed rows are the Part Notes pages, which now carry their
  statutory-authority text. No other row changes.
- **CMS state plans.** The 240 SPA index pages each change their root and `block-1`
  (480 rows) and add one block per further SPA card (17,255 rows), each headed
  `Transmittal Number: …` with the state, summary, approval and effective dates, links
  and topics. The other 1,014 changed rows are PDF pages that the OCR overlay rule now
  reads with Tesseract (below).
- **CHIP FCEP.** The 36 summaries' `block-1` rows now hold the state, summary, dates and
  topics. Before, 20 of them held only the card's link chrome, and the other 16 held the
  summary alone.
- **Maryland TCA.** Each section is one block of 32 or 41 paragraphs; the two `block-2`
  rows, which held the site's menus, are gone.
- **Massachusetts TAFDC.** 106 CMR 701 and 702 gain their 73 sections.
- **Canada.** Only the empty `ca/policy/cra/td1-2026/provincial-territorial-personal-credits/primary-document`
  leaf is removed (row and inventory item).

The three removed rows are those two Maryland `block-2` rows and the Canadian leaf.

The 17,255 new index blocks are positional `block-N` paths (`…/spa-index/pNN/block-K`),
the shared extractor's path for an unlabeled HTML block. They raise the citation-path
grammar's `block_n` ratchet (`schema/citation-path.v1.json`) from 88,143 to 105,398;
CI's `scripts/validate_citation_paths.py` count at this branch's head is exactly that,
and no other family changes.

### Content check

PR #847's content check (`content-check-v1`, `src/axiom_corpus/corpus/content_quality.py`
at #847's head `88c1435a5`) over each original and its successor. Each original's
findings equal its entry in #847's `manifests/release-content-baseline.json`.

| Family | `hollow_document_root` before | after | `navigation_body` before | after | `navigation_prefixed_body` before | after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NYCRR | 49 | 3 | 0 | 0 | 0 | 0 |
| CMS Medicaid state plans | 15 | 0 | 11 | 0 | 12 | 0 |
| CMS CHIP state plans | 7 | 0 | 7 | 0 | 0 | 0 |
| CHIP FCEP | 20 | 0 | 20 | 0 | 0 | 0 |
| Maryland TCA | 2 | 0 | 4 | 0 | 0 | 0 |
| Massachusetts TAFDC | 2 | 0 | 0 | 0 | 0 | 0 |
| Canada | 1 | 0 | 10 | 10 | 14 | 14 |
| **Total** | **96** | **3** | **52** | **10** | **26** | **14** |

- **All 93 audited defect findings are cleared.** 92 roots now have text below them,
  and the Canadian leaf is gone. The audit CSV
  (`docs/ingest-runs/2026-10-13-hollow-document-root-audit.csv`) lists each one.
- **What remains.**
  - The 3 hollow roots are the NYCRR Refs pages of 18 NYCRR 387 and 20 NYCRR 151 and
    152. The audit classed them as expected-empty: their `.co_refsAnnos` container is
    empty, and the rest of each page is headings, a currency notice and chrome.
  - The 24 Canadian navigation findings are the scope's own retained-page chrome. The
    composer recomposes rows; it does not re-extract them.
- **No new finding** in any successor.

### OCR overlay rule: words lost

#854's audit counted only digit-bearing text-layer tokens that disappear.
`scripts/ocr_word_loss.py` in the evidence folder compares, word by word, the original
body (the page's text layer) with the successor's over all 1,014 PDF pages that change.

**#854's rule alone (the first build).** On 19 of the 961 changed pages whose layer has
no control characters (in 12 scopes), a legible layer word was missing.

- **The test is strict.** The word is absent even allowing for other spacing and for a
  near-identical OCR reading, and it is in the system word or name list.
- **What was lost.** Mostly the typed name, title or approval date of the CMS signing
  official. `_with_unread_layer_lines` kept a layer line only when one of its
  digit-bearing tokens was absent from the whole OCR text:
  - `us-hi/policy/cms/medicaid-state-plan/spa/hi-14-005/approval-document/page-3` lost
    its typed date approved, "November 19, 2014", because "19" and "2014" also occur in
    "March 19, 2014".
  - `us-nh/policy/cms/medicaid-state-plan/spa/nh-18-0001/approval-document/page-3` read
    "DATE APPROVED: 531 30, 2018" where the layer has "April 30, 2018".
- **Review.** Review r1 blocked the hand-off on these losses.

**With #868 (these successors).**
[#868](https://github.com/TheAxiomFoundation/axiom-corpus/pull/868) appends a layer
line unless the OCR text already holds the whole line, and drops the lines of
invisible recognition layers that fail against OCR. Its run note,
`docs/ingest-runs/2026-10-13-ocr-overlay-layer-lines.md`, gives the rule. On the same
1,014 pages:

- 965 pages gain words: the pages go from 17,267 words to 217,828.
- Legible layer words missing: 1 page, 1 word ("tint's", in a noise line of NJ CHIP
  22-0031), down from 19 pages and 32 words. HI 14-005 now keeps "November 19, 2014"
  and the signer's name and title, and NH 18-0001 keeps "April 30, 2018".
- 39 digit-bearing layer tokens on 16 pages are absent even ignoring spacing. All 16
  pages carry the failed recognition layers #868's run note names: MT 13-0048's
  mirrored layer, UT 14-0007's, NJ CHIP 22-0031, NJ 19-0009, and the shifted signature
  dates of ID 20-0001 and MO 20-0016 (where "3131" is "2020" shifted by one).
  Examples: "1ui", "sta1u", "4cow", "9jeo".

[#870](https://github.com/TheAxiomFoundation/axiom-corpus/pull/870), not merged, decodes
shifted-font layers. Its scope list names one page in each of 8 documents, in 5 of these
scopes: the AL, MA, MO, OR and WA Medicaid state plans. If #870 merges while this PR is
open, those five are rebuilt the same way. Otherwise they need a further successor
revision.

## Signing and locks

Each successor was signed from a clean checkout of this branch and locked:

```bash
uv run --extra dev axiom-corpus-ingest sign-ingest-manifest \
  --jurisdiction <j> --document-class <c> --version <successor version> \
  --command "uv run --extra dev python scripts/repro/hollow_root_successors.py build --base data/corpus --scope <original> (run note: docs/ingest-runs/2026-10-13-hollow-root-successors.md)" \
  --lock --push
```

- **Manifests.** Each signed manifest covers the scope's sources, inventory,
  provisions and coverage report. No reasoning log is hashed into it, so editing this
  note needs no re-signing. The signed commits must stay ancestors of the branch head,
  so update the branch from `main` by merging, never by rebasing.
- **R2.** R2 already held every source object, since each is byte-identical to the
  original's. `--push` uploaded only the new inventory, provisions and coverage objects.

The 108 manifests were signed over four commits of this branch: 10 over `0b1ae81b6`,
8 over `cb2218d1e`, 39 over `bf6bbe17f`, and the 51 rebuilt with #868 over `24689631f`.
`0b1ae81b6`, `cb2218d1e` and `bf6bbe17f` hold the same builder and extractor. `24689631f`
adds `main` with #868. It also removes the 51 replaced scopes' earlier manifests and
locks, so they are re-signed from a clean tree.

Checked on the head:

- `axiom-corpus-ingest guard-ingested --base-ref origin/main --head-ref HEAD`: every
  changed artifact has a signed manifest.
- `corpus verify --attest --ref HEAD`: all 68,059 lock entries attested.
- `corpus verify --remote --changed-since origin/main`: all 4,200 entries of the 108
  successor locks are in R2. The only new objects are the 324 inventory, provisions and
  coverage files (591 MB).
- `tests/test_hollow_root_successors.py` (18 tests) checks, for every successor:
  - its manifest and lock agree, and its sources are its original's locked bytes;
  - coverage is complete, and it lacks only the three documented paths;
  - each audited root has text at or below it, or is retired.
  
  It also rebuilds the Maryland, Massachusetts, NY SNAP and Canadian successors
  offline, byte for byte, and checks `swap_successors` and `compare_rows` with
  Hypothesis.


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
- **Both US lines also owe #847's swaps.** Once #847 merges, a new cut must also drop
  or replace the scopes `manifests/withdrawn-scopes.yaml` lists. Each base selector is
  grandfathered at its own digest only, so under #847's gate the US drafts fail
  `withdrawn_scope_selected`: 9 errors for the union, 16 for SNAP. Any new cut of those
  lines fails the same way until it takes those swaps too (below).
- **Canada.** `ca-rulespec-2026-07-21-oracle-complete-v2` already carries the same
  normalization, composed with the executable-oracle sources. The source-complete
  successor serves a cut of the source-complete line only.

## Release checks

`axiom-corpus-ingest validate-release --base data/corpus --release <selector>
--ignore-r2-missing`, on each draft and on its base selector:

| Line | Gate | Base | Draft |
| --- | --- | --- | --- |
| Union (1,567 scopes) | `main` | ok; 0 errors, 564 warnings | the same 564 warnings |
| SNAP (272) | `main` | ok; 0 errors, 541 warnings | the same 541 warnings |
| Canada (1) | `main` | ok; 1 warning | the same warning |
| Union | #847 (`88c1435a5`) | 129 errors, 564 warnings | the same 129 errors and 564 warnings |
| SNAP | #847 | not run | 16 errors (`withdrawn_scope_selected`), 541 warnings |
| Canada | #847 | not run | ok; 1 warning |

- **The swap adds no issue.** Under each gate, draft and base give the same issues,
  compared after mapping each successor version to its original.
- **Under #847's gate:**
  - The union's 129 errors are 9 `withdrawn_scope_selected`, plus 120 errors from the
    30 wave-7 scopes that `main` added after #847's branch point and that the #847
    checkout has no locks for (30 each of `missing_inventory`, `missing_provisions`,
    `missing_coverage` and `artifact_report_mismatch`).
  - The SNAP draft's 16 errors are all `withdrawn_scope_selected`, inherited from its
    base.
  - The `baselined_content_findings` notices drop from 28 originals to 2 successors,
    the two NYCRR scopes with their expected-empty Refs roots.

### PR #847's content baseline

Once #847 merges, CI runs `content-check --all --check-baseline`. That check fails on
any locked scope whose findings the baseline does not record, which would include the
three successors that keep findings: the two NYCRR scopes and Canada. In a checkout of
#847 with this branch's 108 locks:

- `content-check <the 108 successors>` gives the 27 findings above, the same as the
  module-level scan: 3
  `hollow_document_root`, 10 `navigation_body` and 14 `navigation_prefixed_body`, in
  3 scopes.
- `--update-baseline` records an entry for each of the 108 successors (108 added lines
  in `manifests/release-content-baseline.json`), after which `--check-baseline` on them
  reports no difference.

Whichever of #847 and this PR merges second must add those entries. The patch, made
against #847's head `88c1435a5`, is `evidence/release-content-baseline-successors.patch`
in the evidence folder. On `main` without #847 there is no
baseline, and nothing is needed.

