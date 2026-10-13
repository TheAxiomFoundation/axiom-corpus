# Hollow document root audit (2026-10-13)

PR #847 adds a release content check whose `hollow_document_root` finding marks a
`document` row with no body when no row below it carries text (or when nothing is below
it). Its content baseline, `manifests/release-content-baseline.json` on branch
`feat/withdrawn-scopes-content-checks` (head `e076a2648`), records 188 such findings
across 43 locked scopes. This note classifies every one, names the code path or source
behind it, records its downstream exposure, and lists what to do next.

The per-finding table is
[`2026-10-13-hollow-document-root-audit.csv`](2026-10-13-hollow-document-root-audit.csv)
(188 rows: family, scope, citation path, classification, cause, evidence, code or source
reference, remedy, whether #847 withdraws the scope, release-selector count and newest
selector, rulespec-us files that cite the path).

Nothing was published, loaded or activated, and no merged scope was edited. Extractor
fixes are in a separate PR (see [Fixes](#fixes)).

## Method

1. Fetched the locked bytes of all 43 scopes (`corpus fetch`, 7,271 files) at
   `origin/main` `a2543bef8` and re-ran #847's `content_quality.py` (content-check-v1)
   over them. It reproduced all 188 findings exactly, scope by scope.
2. For each finding, read the row, its descendants with the check's verdict on each,
   the retained source, the signed ingest manifest and the extractor that built it.
   Eight families were investigated in parallel by independent reviewers (GPT-6.1 Sol)
   and separately by the author; every classification below was checked against the
   retained bytes or, where the scope retains no per-item source, against the live
   official page (Illinois only, fetched 2026-10-13).
3. Downstream exposure: every `manifests/releases/*.json` selector that names the scope
   (selectors select whole scopes), and every exact occurrence of the citation path, or a
   path below it, in `rulespec-us` `origin/main` (`4b35d0872`, 2026-10-12). The 41 other
   local `rulespec-*` repositories cite none of the 187 distinct paths.

Classifications: `extractor_defect` (the source holds the text, the extractor did not
keep it), `missing_or_placeholder_source` (the retained source does not hold the text),
`expected_empty` (the official node has no text of its own), and
`check_false_positive` (the node has text the check does not count).

## Results

| Family | Findings | Extractor defect | Missing or placeholder source | Expected empty | Check false positive |
| --- | ---: | ---: | ---: | ---: | ---: |
| New York NYCRR Part notes and refs (Westlaw) | 49 | 46 | 0 | 3 | 0 |
| Illinois Cash, SNAP and Medical Manual | 55 | 0 | 1 | 53 | 1 |
| CMS Medicaid and CHIP state plans (2026-09-13) | 22 | 22 | 0 | 0 | 0 |
| CMS CHIP FCEP SPA summaries | 20 | 20 | 0 | 0 | 0 |
| SSA POMS exhibits and forms | 6 | 0 | 6 | 0 | 0 |
| State HTML manuals (AK, CT, ND, NH, WA) | 17 | 0 | 3 | 14 | 0 |
| Statutes (CA, ID, ME recovery; MD TCA) | 12 | 11 | 1 | 0 | 0 |
| Other regulations and policy (BE, CA, MA, NM) | 7 | 4 | 1 | 2 | 0 |
| **Total** | **188** | **103** | **12** | **72** | **1** |

Of the 103 extractor defects, the fix PR repairs 92 (NY 46, CMS 22, FCEP 20, MD 2,
MA 2); 2 (Canada) were already fixed on main; 9 (ID, ME) sit in recovery scopes #847
withdraws, whose sections carry text in successor scopes.

### New York NYCRR Part notes and refs: 46 extractor defects, 3 expected empty

Scopes `us-ny/regulation/2026-09-14-income-tax-regulations` (46) and
`us-ny/regulation/2026-07-17-ny-snap-regulations` (3), both built by
`extract-nycrr-parts` (`nycrr.py`). Every flagged row is a Part's "Notes" or "Refs"
page, and every Notes and Refs row in both scopes is flagged.

- Westlaw section pages keep their text in `#co_document .co_contentBlock.co_body`;
  Notes pages have no `.co_body` and keep theirs in `.co_contentBlock.co_refsAnnos`.
  `nycrr.py::_document_body` read only `.co_body`, so all 46 Notes rows have no body.
  The lost text is the Part's statutory-authority line (43 to 592 characters), and on
  27 income-tax Parts a note that the Part does not reflect later Tax Law amendments
  (for example 20 NYCRR Part 106 Notes: "Section 106.1 of this Part does not reflect
  amendments to the Tax Law made by the Tax Reform and Reduction Act of 1987").
- The three Refs pages (18 NYCRR 387, 20 NYCRR 151 and 152) have an empty
  `co_refsAnnos` block: expected empty.
- No other rows are affected: all 228 income-tax and 39 SNAP section pages have no
  `co_refsAnnos` text, and the fix leaves every section body unchanged.
- The income-tax scope's signed ingest manifest records the command as
  `extract-official-documents`; the run note
  (`2026-09-14-state-tax-regulations.md`) shows it was `extract-nycrr-parts` with
  `manifests/us-ny-income-tax-regulations.yaml`.

### Illinois Cash, SNAP and Medical Manual: 53 expected empty, 1 placeholder, 1 check false positive

Scope `us-il/manual/2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained`
(54) and the recovery row in `us-il/manual/2026-07-13-recovery-r2026-07-17-dedup` (1).

- The 54 rows have no descendants in the scope, and had none in the original
  2026-05-27 ingest (`a5d9b220a`); the July rebuild copied rows and bodies unchanged.
- The scope retains one source file, the manual's table of contents (item 13473), and
  every one of its 12,450 rows names that file as its source, though each row's
  `metadata.download_url` names its own IDHS page. The per-item pages are not in the
  original ingest commit and not under R2's legacy `sources/us-il/manual/` keys. `scripts/repair_us_release_source_references.py` (commit `de4c33abb`)
  pointed every inventory item and provision at the single retained snapshot. This
  misattributes all 12,450 rows, not only the flagged ones.
- Because the retained bytes cannot show what the items say, the 54 live pages were
  fetched on 2026-10-13 (evidence kept with the review). 52 have an empty content area:
  "Reserved" items, a lone "Deleted Text" marker, nothing at all, or a heading whose only
  content is sidebar links to its sub-items, which are separate documents in the scope. Item 13473 is the
  table of contents (10 words, 25 links). All 53 are expected empty.
- Item 67224 ("WAG 25-06-05-a (1) Minimum Monthly SNAP Benefit Amount for 1-2
  Persons") has one child holding the benefit table: date ranges and amounts from
  "$16" to "$24". The check counts only tokens with a letter, so an all-numeric table
  reads as no text: a check false positive.
- The recovery row `us-il/manual/recovery/release-scope-…` is a synthetic row for the
  table-of-contents page: a placeholder in a scope #847 withdraws.

### CMS Medicaid and CHIP state plans: 22 extractor defects

The 2026-09-13 state-plan scopes for AK, CT, DC (two), IL, IN, MT, NH, NM, NY, OH, RI,
SC, VT (two), WI and WY, built by `extract-official-documents` from manifests that
`scripts/build_cms_state_plan_manifests.py` generates.

- **18 `…/spa-index/pNN` rows.** A medicaid.gov SPA index page prints each SPA as an
  accordion card: the transmittal number inside the card heading's `<button>`, and the
  state, summary, approval and effective dates and topics as bare text in `<div>` grid
  cells. `documents.py::_html_text_nodes` takes only headings, paragraphs, list items,
  tables and blockquotes by default, and `button` is a default drop selector, so all
  that text is lost; the "Approval Package" list items survive, so the whole-page
  fallback in `_extract_html_blocks` never runs. The 18 flagged pages are the ones
  whose summaries are all bare text, leaving only link labels. The run note for these
  scopes intended the index blocks to carry every record's fields.
- **The loss is much wider than the findings.** Across all 240 index pages in the 102
  CMS state-plan scopes there are 17,495 SPA cards: 4,037 summaries sit in `<p>` and
  survive, and 13,456 are bare text and lost. 218 pages lose some summaries without
  being flagged, 12,911 summaries in all (for example CT p01 keeps 66 and loses 34). Every page loses every
  transmittal number and date.
- **4 `…/spa/<id>/attachment` rows** (IN-12-014, OH-12-004, OH-12-006, OH-13-001) are
  scanned page images ("Scan-to-email", CCITT) whose text layer is only a date stamp
  such as "9/4/13". The generator sets `ocr: true` on every state-plan PDF, but
  `documents.py::_pdf_page_text` ran OCR only when the text layer was empty, so the stamp
  stopped it. OCR recovers the pages (for example OH-12-004: Freestanding Birth Centers
  coverage, 170 to 238 words a page). The Ohio scans are stored with `/Rotate 270`.
- **Also wider than the findings.** Of 61,690 pages in the 2,964 PDFs these scopes
  retain, the fixed OCR rule reads 1,024 more pages (318 PDFs, 69 scopes) whose text
  layer is only a stamp or typed form fields over a page scan; 205 of those pages carry
  no word with a letter at all.

### CMS CHIP FCEP SPA summaries: 20 extractor defects

Scope `us/policy/2026-07-05-cms-chip-fcep-spa`. Each `…/summary` row is one SPA card on
a medicaid.gov page filtered to that SPA. In the 16 unflagged summaries the description
is wrapped in `<p>` and survives; in the 20 flagged ones it is bare `<div>` text and
only "Approval Package" survives (same code path as above). The 16 unflagged summaries
still lose the state, dates and topics.

### SSA POMS exhibits and forms: 6 missing or placeholder sources

SI 00502.306, HI 00801.309, HI 01001.380, HI 01015.045, HI R04125.001 and SI 02306.703.
The pages hold headings and GIF images of the exhibits or forms, each with a "View In
PDF" link. The exhibit titles survive as block headings; the content is in the linked
images and PDFs, which were not retained.

### State HTML manuals: 14 expected empty, 3 missing or placeholder sources

- Expected empty: AK SNAP 608 (chapter heading with Previous/Next links; its sections are
  separate documents); CT SNAP Desk Aids and Examples, Examples, and the JSON table of
  contents (deliberately `segmentation: source_only`); ND CCAP Archived IMs (an index of
  memo links); NH FSM 511 Green Thumb (a "see" cross-reference to Senior Citizen Community
  Service Employment Income); the three NH "Navigating the … Manual" pages (chapter link
  lists); four WA EA-Z citizenship and immigration index pages; the WA Apple Health
  long-term services and supports index.
- Missing source: ND 510-05-105-10 (the hard card is a linked PDF), WA EA-Z CEAP (a
  relocation stub linking the CEAP page), WA Apple Health flowchart (a linked PDF). None of
  the linked documents is retained.
- The 14,000-word sizes of the two WA Apple Health sources are site navigation; the
  selected article is the index or link sentence.

### Statutes: 11 extractor defects, 1 missing source

- **ID 63-3022D, 63-3022E, 63-3024, 63-3024A, 63-3025D and ME 36 §§5124-C, 5126-A,
  5213-A, 5219-S** (recovery scopes, withdrawn by #847). The retained pages hold the
  section text in `<div>`/`<span>` containers; `scripts/recover_ingest_batch.py::_generic`
  passes `extraction=None`, so only site menus survived. The same sections carry text in
  `us-id/statute/2026-09-14-income-tax-chapter-us-id-title-63-chapter-30` and
  `us-me/statute/2026-09-14-income-tax-chapter-us-me-title-36`, which the newest union
  selectors include. ME §5219-SS lost its text the same way but escapes the check: its
  menu is 69.2% navigation, under the 70% threshold. rulespec-us cites it too; it has
  text (5,280 characters) in the 2026-09-14 scope.
- **MD Human Services §§5-312 and 5-316** (`us-md/statute/2026-07-03-md-tca-statutes`,
  not withdrawn). The statute is bare text and `<br>` breaks inside `#StatuteText`; the
  manifest selects `body`, so only the site menus became blocks. No other locked MD scope
  holds either section.
- **CA WIC 11450(a)(1)(A)** (recovery, withdrawn). The retained page is LegInfo's
  "select from multiples" version picker, not the section. The section's full text,
  including (a)(1)(A), is at `us-ca/statute/wic/11450` in
  `2026-06-25-ca-wic-calworks-…-r2026-09-24-preserve-tables`; no scope holds a row at
  `…/11450/a/1/A` with text.

### Other regulations and policy: 4 extractor defects, 1 missing source, 2 expected empty

- **CA CRA TD1 `…/provincial-territorial-personal-credits/primary-document`** (two
  composite scopes). The Canada composite builder cloned an empty program root into an
  empty `/primary-document` leaf; the 12 provincial and territorial sections carry their
  text as siblings. `scripts/build_ca_rulespec_composite_scope.py::promote_program_roots`
  was fixed on main by `477c6650c` (2026-07-21), and the oracle-complete scope has a
  signed v2 successor; the source-complete scope does not.
- **MA 106 CMR 701 and 702** (`us-ma/regulation/2026-06-27-ma-tafdc-regulations`). The
  DOCX files hold the chapters (about 9,000 words each), but the manifest's
  `start_after_pattern` (`Page | 701.000`, `Page | 702.000`) never occurs: chapter 701's
  text opens at 701.050, and 702's page header reads "702 .000" because the table-cell
  text joins Word runs with spaces. The labeled-sections extractor then returned no
  sections instead of failing. 701.000 is listed in the chapter's contents but its text is
  not in the retained DOCX.
- **BE Arrêté royal no. 20 of 20 July 1970** (Moniteur original). An 80-page image-only
  scan; the manifest records that OCR is not yet configured. The consolidated text is in
  the same scope (FisconetPlus), and no release selects the scope.
- **NM 8.139.640 and 8.139.650 NMAC.** Repealed parts whose pages hold only the repeal
  notice and filing history: expected empty.

## Downstream exposure

Release selectors (`manifests/releases/`) select whole scopes; counts per scope are in
the CSV. The flagged scopes sit in 0 to 44 selectors; the newest that select them are
`us-rulespec-2026-10-12-w5-benefits-union` and
`us-rulespec-2026-10-13-snap-fy2026-memo-source-corrected`.

rulespec-us cites 12 of the 188 paths, all in the statutes family:

| Path | rulespec-us files | Corpus text for the path |
| --- | --- | --- |
| `us-ca/statute/wic/11450/a/1/A` | `us-ca/policies/cdss/calworks/monthly-aid-payment.yaml` (module `source_verification.corpus_citation_path` and eight proof-atom citations) | None in any scope. The parent section `us-ca/statute/wic/11450` has the text. |
| `us-id/statute/63-3022D`, `-3022E`, `-3024`, `-3024A`, `-3025D` | `us-id/statutes/*.yaml`, encoding manifests, `us-id/policies/income_tax/2026_full_year_resident_source_hold.yaml`, `pilot_liability_pipeline.yaml` | In `2026-09-14-income-tax-chapter-us-id-title-63-chapter-30` (and `2026-07-31-id-title-63-chapter-30-successor`) |
| `us-me/statute/36/5124-C`, `5126-A`, `5213-A`, `5219-S` | `us-me/statutes/36/*.yaml`, encoding manifests, `us-me/policies/income_tax/2026_resident_liability_source_hold.yaml` | In `2026-09-14-income-tax-chapter-us-me-title-36` |
| `us-md/statute/human-services/5-312/temporary-cash-assistance`, `…/5-316/fip-funding` | `us-md/policies/dhs/fia/im-26-13/2026-tca-tdap-benefit-increase/allowable-tca-monthly-payment.yaml` (`upstream_source_check.checked_paths`) | None until a successor of the TCA scope |

The CalWORKs module is the one exposure that #847's withdrawal makes worse: its only
corpus row for the cited path is in a withdrawn scope, and that row has no text.

## What the check misses and over-counts

For the #847 owner; none of these blocks the baseline, which pins findings per scope.

- **Numeric-only text.** `classify_body` counts only tokens with a letter, so a body that
  is all dates and amounts is "not substantive" (IL item 67224). Counting numeric tokens
  as text would clear that false positive.
- **The 70% navigation threshold.** ME §5219-SS lost all of its text and kept a menu
  that is 69.2% navigation, so it is neither `navigation_body` nor a hollow root.
- **Partial loss.** The check sees only roots with nothing left. Unflagged losses found
  in this audit: 12,911 CMS SPA summaries on 218 unflagged index pages (and every
  transmittal number and date on all 240 pages); state, dates and topics on 16 FCEP
  summaries; 1,024 scanned state-plan PDF pages read as their stamp; and, from the
  reviewers' censuses (not re-verified here), 40 MA TAFDC section bodies with spaces
  inserted between Word runs and 30 WA EA-Z and 21 NH FAM documents missing inline
  text. A source-coverage check (visible source text against
  extracted text) would catch this class.
- **Reviewed-empty nodes.** 72 findings are correct as empty (refs pages, tables of
  contents, link indexes, reserved items, repealed parts). A reviewed-empty list, or a
  reason recorded on the row, would let the check exempt them explicitly.

## Fixes

Extractor PR (branch `fix/hollow-root-extractor-defects`), each with tests:

- `nycrr.py::_document_body` reads `.co_refsAnnos` when a page has no `.co_body`.
  Recovers all 46 NY Notes bodies; Refs pages stay bodyless; section bodies unchanged.
- `documents.py::_pdf_page_text`: with `ocr`, a page is read by OCR when its text layer is
  empty (as before) or has fewer than 30 words with a letter while one image covers at
  least 90% of the page. Image rectangles are mapped through the page's rotation matrix.
  If OCR returns nothing, the text layer is kept. Recovers the 4 attachments.
- `documents.py`: a `start_after_pattern` (labeled DOCX, styled DOCX, PDF lines) or page
  window `start_at_pattern` that never matches now raises, as the HTML selectors already
  do. Run against every manifest document that sets one (385 retained sources), only MA
  701 and 702 fail; 379 extract as before and 4 have no retained source.
- Manifests: `INDEX_PAGE_EXTRACTION` in `scripts/build_cms_state_plan_manifests.py` and
  the 240 index pages in the 102 state-plan manifests (one block per SPA, headed by its
  transmittal number); `html_text_selector` for the 36 FCEP summaries and the two MD TCA
  sections; corrected start markers for MA 701 and 702.

Re-extracting the 46 non-NY fixable documents from their retained bytes into a scratch
corpus and re-running #847's check leaves none hollow and none with a navigation-only child.

## Recommendations

1. **Successor scopes** (new versions; the merged scopes stay as they are), then
   successor selectors: the two NY regulation scopes; the 102 CMS state-plan scopes
   (index pages and OCR); `us/policy/2026-07-05-cms-chip-fcep-spa`;
   `us-md/statute/2026-07-03-md-tca-statutes`;
   `us-ma/regulation/2026-06-27-ma-tafdc-regulations`.
2. **rulespec-us CalWORKs**: point `monthly-aid-payment.yaml` at
   `us-ca/statute/wic/11450` (which holds (a)(1)(A) and its table), or ingest
   subsection rows for WIC 11450, before #847's withdrawal of the CA recovery scope takes
   effect in a release.
3. **Illinois manual attribution**: a successor that retains each item's page, or at
   least records in each row which page it came from. Guard
   `repair_us_release_source_references.py` so it cannot assign one snapshot to rows whose
   own `download_url` differs.
4. **Retain linked documents** where the HTML page is only a pointer: POMS exhibit PDFs,
   the ND hard card, the WA Apple Health flowchart, the WA CEAP page.
5. **Check refinements** listed above for #847: numeric tokens, a reviewed-empty
   exemption, and a source-coverage check for partial loss.
6. **Wider extractor robustness**: bare text in `<div>` and `<span>` is dropped by default
   whenever any paragraph or list item is present. A general fix needs a corpus-wide
   before/after comparison first. So does the DOCX table-cell run-joining defect (MA's 40
   sections).
7. **Provenance**: correct the NY income-tax ingest manifest's recorded command in the
   successor.

## Reproduce

The review folder `~/reviews/axiom-corpus-hollow-roots-2026-10-13/` holds the baseline
copy, `build_dossier.py` (reproduces the 188 findings and builds per-finding evidence),
`scripts/build_table.py` (writes the CSV), `scripts/reextract_verify.py`, the reviewer
briefs and reports (`briefs/`, `out/`), and the evidence files: live Illinois pages, the
CMS index-page and PDF text-layer sweeps, the OCR-rule impact, and the start-marker sweep.
