# Hollow document root audit (2026-10-13)

PR #847 adds a release content check whose `hollow_document_root` finding marks a
`document` row with no body when no row below it carries text (or when nothing is below
it). Its content baseline, `manifests/release-content-baseline.json` on branch
`feat/withdrawn-scopes-content-checks` (head `e076a2648`), records 188 such findings
across 43 locked scopes. This note classifies every one, names the code path or source
behind it, records its downstream exposure, and lists what to do next.

The per-finding table is
[`2026-10-13-hollow-document-root-audit.csv`](2026-10-13-hollow-document-root-audit.csv)
(188 rows: family, scope, citation path, classification, cause, evidence and its basis,
code or source reference, remedy, whether #847 withdraws the scope, release-selector count
and newest selector, rulespec-us files that cite the path).

Nothing was published, loaded or activated, and no merged scope was edited. Extractor
fixes are in a separate PR (see [Fixes](#fixes)).

## Method

1. Fetched the locked bytes of all 43 scopes (`corpus fetch`, 7,271 files) at
   `origin/main` `a2543bef8` and re-ran #847's `content_quality.py` (content-check-v1)
   over them. It reproduced all 188 findings exactly, scope by scope.
2. For each finding, read the row, its descendants with the check's verdict on each,
   the retained source, the signed ingest manifest and the extractor that built it.
   Eight families were investigated in parallel by independent reviewers (GPT-6.1 Sol)
   and separately by the author, and the note was then reviewed adversarially. Every
   classification rests on the retained bytes, except Illinois: that scope retains no
   per-item source, so its rows rest on the live official pages fetched 2026-10-13, and
   the CSV says so on each row.
3. Downstream exposure: every `manifests/releases/*.json` selector that names the scope
   (selectors select whole scopes), and every exact occurrence of the citation path, or a
   path below it, in `rulespec-us` `origin/main` (`4b35d0872`, 2026-10-12). The 41 other
   local `rulespec-*` repositories cite none of the 187 distinct paths.

Classifications:

- `extractor_defect`: the retained source holds the text and the extractor, as configured,
  did not keep it. A scanned PDF whose manifest asks for OCR counts here.
- `missing_or_placeholder_source`: the retained source does not hold the text: a
  placeholder page, a page that only links to an unretained document, or a scan whose
  manifest does not ask for OCR (the Belgian gazette).
- `expected_empty`: the official node has no operative text of its own: an index, a table
  of contents, a cross-reference stub, a reserved item, a repealed part whose page carries
  only the repeal notice and history.
- `check_false_positive`: the node has text the check does not count.

## Results

| Family | Findings | Extractor defect | Missing or placeholder source | Expected empty | Check false positive |
| --- | ---: | ---: | ---: | ---: | ---: |
| New York NYCRR Part notes and refs (Westlaw) | 49 | 46 | 0 | 3 | 0 |
| Illinois Cash, SNAP and Medical Manual | 55 | 0 | 2 | 52 | 1 |
| CMS Medicaid and CHIP state plans (2026-09-13) | 22 | 22 | 0 | 0 | 0 |
| CMS CHIP FCEP SPA summaries | 20 | 20 | 0 | 0 | 0 |
| SSA POMS exhibits, forms and a redacted section | 6 | 0 | 6 | 0 | 0 |
| State HTML manuals (AK, CT, ND, NH, WA) | 17 | 0 | 2 | 15 | 0 |
| Statutes (CA, ID, ME recovery; MD TCA) | 12 | 11 | 1 | 0 | 0 |
| Other regulations and policy (BE, CA, MA, NM) | 7 | 4 | 1 | 2 | 0 |
| **Total** | **188** | **103** | **12** | **72** | **1** |

Of the 103 extractor defects, the fix PR repairs 92 (NY 46, CMS 22, FCEP 20, MD 2,
MA 2); 2 (Canada) were fixed in the builder on main, one of them without a successor scope
yet; 9 (ID, ME) sit in recovery scopes #847 withdraws, whose sections carry text, with
caveats, in successor scopes.

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
- No other rows are affected: none of the 267 section pages (228 income-tax, 39 SNAP)
  has `co_refsAnnos` text, and the fix leaves every section body unchanged.
- The income-tax scope's signed ingest manifest records the command as
  `extract-official-documents`; the run note
  (`2026-09-14-state-tax-regulations.md`) shows it was `extract-nycrr-parts` with
  `manifests/us-ny-income-tax-regulations.yaml`.

### Illinois Cash, SNAP and Medical Manual: 52 expected empty, 2 missing sources, 1 check false positive

Scope `us-il/manual/2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained`
(54) and the recovery row in `us-il/manual/2026-07-13-recovery-r2026-07-17-dedup` (1).

- 52 of the 54 rows have no descendants; items 13473 and 67224 have one block each. The
  original 2026-05-27 ingest (`a5d9b220a`) had the same rows and bodies; the July rebuild
  copied all 12,450 rows unchanged.
- The scope retains one source file, the manual's table of contents (item 13473), and
  every one of its 12,450 rows names that file as its source, though each row's
  `metadata.download_url` names its own IDHS page.
  `scripts/repair_us_release_source_references.py` (commit `de4c33abb`) rewrote every
  inventory item and provision to the single retained snapshot. That misattributes
  12,448 rows (all but item 13473 and its block), flagged or not. Neither the scope's
  lock nor its signed ingest manifest references any per-item page, and the original
  ingest commit holds none.
- So the retained bytes cannot show what the items say, and the classifications rest on
  the 54 live pages, fetched 2026-10-13, four and a half months after the May capture.
  The May extraction found no text for these items either. On the live pages, 35 are
  headings whose only content is sidebar links: for 33 every linked sub-item is a
  separate document in the scope (expected empty), but the Glossary (23 links) and
  Abbreviations and Acronyms (17 links) link sub-pages none of which is in the scope, so
  those two are missing sources. Of the rest, 10 are "Reserved" (4 of them showing a
  deleted-text marker image), 4 hold a lone "Deleted Text" marker image, and 3 have an
  empty content area: all expected empty. Item 13473 is the table of contents (10 words,
  25 links): expected empty.
- Item 67224 ("WAG 25-06-05-a (1) Minimum Monthly SNAP Benefit Amount for 1-2
  Persons") has one block holding the benefit table: date ranges and amounts from
  "$15" to "$24". The check counts only tokens with a letter, so an all-numeric table
  reads as no text: a check false positive.
- The recovery row `us-il/manual/recovery/release-scope-…` is a synthetic row for the same
  table-of-contents page (expected empty, like item 13473), in a scope #847 withdraws.

### CMS Medicaid and CHIP state plans: 22 extractor defects

The 2026-09-13 state-plan scopes for AK, CT, DC (two), IL, IN, MT, NH, NM, NY, OH, RI,
SC, VT (two), WI and WY, built by `extract-official-documents` from manifests that
`scripts/build_cms_state_plan_manifests.py` generates.

- **18 `…/spa-index/pNN` rows.** A medicaid.gov SPA index page prints each SPA as an
  accordion card: the transmittal number inside the card heading's `<button>`, and the
  state, summary, approval and effective dates and topics in `<div>` grid cells. Some
  summaries are wrapped in `<p>`; most are bare text. `documents.py::_html_text_nodes`
  takes only headings, paragraphs, list items, tables and blockquotes by default, so bare
  summaries, dates and topics are lost, and `button` is a default drop selector. The
  "Approval Package" list items survive, so the whole-page fallback in
  `_extract_html_blocks` never runs. On the 18 flagged pages what survives (link labels,
  plus at most three `<p>` summaries) reads as navigation. The scopes' run note expected
  each page's block to carry every record's summary, dates, link labels and topics; it
  accepted losing the `<button>` record headings.
- **The loss is much wider than the findings.** The 240 index pages in the 102 CMS
  state-plan scopes hold 17,495 SPA cards (2 have no summary): 4,037 summaries sit in
  `<p>` and survive, and 13,456 are bare text and lost. 218 of the 222 unflagged pages lose
  some, 12,911 in all (for example CT p01 keeps 66 and loses 34); 4 unflagged pages lose
  every summary (AR p03, FL p03, ID p03, NE p03). Every page loses every date.
- **4 `…/spa/<id>/attachment` rows** (IN-12-014, OH-12-004, OH-12-006, OH-13-001) are
  scanned page images ("Scan-to-email", CCITT) whose text layer is only a date stamp
  such as "9/4/13". The generator sets `ocr: true` on every state-plan PDF, but
  `documents.py::_pdf_page_text` ran OCR only when the text layer was empty, so the stamp
  stopped it. OCR recovers the pages (for example OH-12-004: Freestanding Birth Centers
  coverage, 170 to 238 words a page). The Ohio scans are stored with `/Rotate 270`.
- **Pages the fixed OCR rule now sends to OCR.** The rule (below) reads a page by OCR when
  its text layer has fewer than 30 words with a letter and images of at least 100 dpi
  cover at least 90% of it. Across the 3,921 retained PDFs of every `ocr: true` manifest
  document (counted as file paths, so a PDF kept by two scopes counts twice; one such
  document has no retained PDF to match), it sends 1,041 pages in 328 PDFs to OCR despite
  a non-empty text layer: 1,021 in the CMS state-plan scopes (the 4
  flagged attachments among them) and 20 in 14 other PDFs (Ghana and Uganda gazette
  scans, South Carolina health policy, a Hawaii manual, the Alabama WIC plan). On 208 of
  those pages the layer has no word with a letter. 974 pages meet a simple scan rule (the
  page's largest image is 1-bit, CCITT or JBIG2 encoded, or at least 150 dpi). Of the 67
  outside it (mostly CMS pages imaged at 100 to 149 dpi), nine were rendered and
  inspected: three gazette scans (one holding only show-through from the reverse side
  beside its printer's line, which OCR may read as noise), two imaged tables of
  contents, an imaged benefit-plan page, a print-view standards table, and two CMS-179
  forms (one whose layer is garbled glyph codes). Each of the others shows its text as an
  image; on the
  standards table the merge keeps the layer's dollar amounts if OCR misreads them. A
  Georgia slide inspected earlier no longer qualifies (70 dpi background). Re-extracting
  the 335 manifest documents behind the 336 PDFs that the rule reached before the 100 dpi
  floor (a superset of these 328) with the old and the new code (sharing Tesseract
  output) gives no error on either side, so every start and stop marker still
  matches; no section label changes; 316 documents change (11.2 to 12.4 million
  characters in all), 304 gaining text and 12 swapping a stamp or garbled layer for OCR
  text of about the same length (at most 338 characters shorter); and of the 539 text-layer tokens with a digit that disappear, 526
  sit in garbled-font lines (control characters) and 13 differ from what OCR read only in
  punctuation.

### CMS CHIP FCEP SPA summaries: 20 extractor defects

Scope `us/policy/2026-07-05-cms-chip-fcep-spa`. Each `…/summary` row is one SPA card on
a medicaid.gov page filtered to that SPA. In the 16 unflagged summaries the description
is wrapped in `<p>` and survives; in the 20 flagged ones it is bare `<div>` text and
only "Approval Package" survives (same code path as above). The 16 unflagged summaries
still lose the state, dates and topics.

### SSA POMS: 6 missing or placeholder sources

SI 00502.306, HI 00801.309, HI 01001.380, HI 01015.045 and SI 02306.703 are exhibit and
form pages: headings plus GIF images of the exhibits or forms, each with a "View In PDF"
link. HI R04125.001 is a redacted section: a figure caption and a PDF link. The headings
and caption survive; the content is in the linked images and PDFs, which were not
retained.

### State HTML manuals: 15 expected empty, 2 missing or placeholder sources

- Expected empty: AK SNAP 608 (chapter heading with Previous/Next links; its sections are
  separate documents); CT SNAP Desk Aids and Examples, Examples, and the JSON table of
  contents (deliberately `segmentation: source_only`); ND CCAP Archived IMs (an index of
  memo links); NH FSM 511 Green Thumb (a "see" cross-reference to Senior Citizen Community
  Service Employment Income); the three NH "Navigating the … Manual" pages (chapter link
  lists); four WA EA-Z citizenship and immigration index pages; WA EA-Z CEAP (a relocation
  stub whose target page is retained in the same scope, 18 blocks); the WA Apple Health
  long-term services and supports index.
- Missing source: ND 510-05-105-10 (the hard card is a linked PDF) and the WA Apple
  Health flowchart (a linked PDF). Neither PDF is retained.
- The 14,000-word sizes of the two WA Apple Health sources are site navigation; the
  selected article is the index or link sentence.

### Statutes: 11 extractor defects, 1 missing source

- **ID 63-3022D, 63-3022E, 63-3024, 63-3024A, 63-3025D and ME 36 §§5124-C, 5126-A,
  5213-A, 5219-S** (recovery scopes, withdrawn by #847). The retained pages hold the
  section text in `<div>`/`<span>` containers that the default HTML text nodes skip, so
  only site menus became blocks. The rows are `scripts/recover_ingest_batch.py::_generic`
  output, which passes `extraction=None`: the 2026-09-27 recovery sibling-scopes audit,
  which covers these scopes, replays `_generic` on the retained bytes and reproduces the
  rows exactly (`test_rows_are_what_the_recovery_builders_make_of_the_retained_bytes`),
  as the 2026-09-25 CA audit (#748) does for the CA scope. The scopes were added in
  `ed8464a37`. The same sections carry text in
  `us-id/statute/2026-09-14-income-tax-chapter-us-id-title-63-chapter-30` and
  `us-me/statute/2026-09-14-income-tax-chapter-us-me-title-36`, which the newest union
  selectors include, with caveats: the ID successors keep only the "[effective until
  January 1, 2027]" rendition of 63-3022E and 63-3025D, which open PR #823 keeps both
  of, and the ME scope drops lettered paragraphs, which open PR #754 restores (recorded
  in the 2026-09-27 audit).
- ME §5219-SS lost its text the same way but escapes the check: its menu is 69.2%
  navigation, under the 70% threshold. rulespec-us cites it too; it has text (5,280
  characters) in the 2026-09-14 scope.
- **MD Human Services §§5-312 and 5-316** (`us-md/statute/2026-07-03-md-tca-statutes`,
  not withdrawn). The statute is bare text and `<br>` breaks inside `#StatuteText`; the
  manifest selects `body`, so only the site menus became blocks. No other locked MD scope
  holds either section.
- **CA WIC 11450(a)(1)(A)** (recovery, withdrawn). WIC 11450 has two concurrent
  versions, and the retained page is LegInfo's "select from multiples" picker between them,
  not the section. The only WIC 11450 text in the corpus is the section row
  `us-ca/statute/wic/11450` in `2026-06-25-ca-wic-calworks-…` and its
  `-r2026-09-24-preserve-tables` revision, and it is the Stats. 2024, ch. 798, §1
  version. By its subdivision (p) that version
  becomes inoperative on the later of July 1, 2024 and the date CDSS notifies the
  Legislature that the Statewide Automated Welfare System can implement the change
  (whether that notice has been given is not verified here); its history note points to a
  "later operative version, as amended by Sec. 2 of Stats. 2024, Ch. 798". That later
  version is not ingested, and no scope holds a row at `…/11450/a/1/A` with text. Open PR
  #752 captures LegInfo's concurrent versions of WIC 11450 as same-number variant rows.

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
  text opens at 701.050, and 702's page header reads "702 .000" because
  `documents.py::_docx_table_text` joins a cell's Word runs with spaces. The
  labeled-sections extractor then returned no sections instead of failing. 701.000 is
  listed in the chapter's contents but its text is not in the retained DOCX.
- **BE Arrêté royal no. 20 of 20 July 1970** (Moniteur original). An 80-page image-only
  scan; the manifest does not ask for OCR and notes that OCR is not yet configured, so the
  retained source holds no text. The consolidated text is in the same scope
  (FisconetPlus), and no release selects the scope.
- **NM 8.139.640 and 8.139.650 NMAC.** Repealed parts. Their pages hold the repeal notice
  ("[This part was repealed on April 1, 2014.]"; 650's definitions moved to 8.139.100)
  and filing history, and no operative provisions, so the labeled-sections extractor found
  no section. Expected empty; keeping the repeal notice as the body would also be right.

## Downstream exposure

Release selectors (`manifests/releases/`) select whole scopes; counts per scope are in
the CSV. The flagged scopes sit in 0 to 44 selectors; the newest that select them are
`us-rulespec-2026-10-12-w5-benefits-union` and
`us-rulespec-2026-10-13-snap-fy2026-memo-source-corrected`.

rulespec-us cites 12 of the 188 paths, all in the statutes family:

| Path | rulespec-us files | Corpus text for the path |
| --- | --- | --- |
| `us-ca/statute/wic/11450/a/1/A` | `us-ca/policies/cdss/calworks/monthly-aid-payment.yaml` (module `source_verification.corpus_citation_path` and eight proof-atom citations) | None in any scope. The parent row `us-ca/statute/wic/11450` holds only the §1 version, conditionally inoperative; the later §2 version is not ingested (#752). |
| `us-id/statute/63-3022D`, `-3022E`, `-3024`, `-3024A`, `-3025D` | `us-id/statutes/*.yaml`, encoding manifests, `us-id/policies/income_tax/2026_full_year_resident_source_hold.yaml`, `pilot_liability_pipeline.yaml` | In `2026-09-14-income-tax-chapter-us-id-title-63-chapter-30` (and `2026-07-31-id-title-63-chapter-30-successor`); 63-3022E and 63-3025D only in their pre-2027 rendition |
| `us-me/statute/36/5124-C`, `5126-A`, `5213-A`, `5219-S` | `us-me/statutes/36/*.yaml`, encoding manifests, `us-me/policies/income_tax/2026_resident_liability_source_hold.yaml` | In `2026-09-14-income-tax-chapter-us-me-title-36`, without lettered paragraphs until #754 |
| `us-md/statute/human-services/5-312/temporary-cash-assistance`, `…/5-316/fip-funding` | `us-md/policies/dhs/fia/im-26-13/2026-tca-tdap-benefit-increase/allowable-tca-monthly-payment.yaml` (`upstream_source_check.checked_paths`) | None until a successor of the TCA scope |

The CalWORKs gap already exists. The 2026-09-25 CA statute recovery audit (#748) found
the version picker, and the 2026-09-24 selectors began replacing the recovery scope; the
newest selector that includes it is dated 2026-09-24, and the four us-rulespec selectors
dated after it leave it out, so in those releases the cited path has no row at all. #847's
withdrawal only removes the hollow row from the older selectors.

## What the check misses and over-counts

For the #847 owner; none of these blocks the baseline, which pins findings per scope.

- **Numeric-only text.** `classify_body` counts only tokens with a letter, so a body that
  is all dates and amounts is "not substantive" (IL item 67224). Counting numeric tokens
  as text would clear that false positive.
- **The 70% navigation threshold.** ME §5219-SS lost all of its text and kept a menu
  that is 69.2% navigation, so it is neither `navigation_body` nor a hollow root.
- **Partial loss.** The check sees only roots with nothing left. Unflagged losses found
  in this audit: 12,911 CMS SPA summaries on 218 unflagged index pages and every date on
  all 240; the state, dates and topics of 16 FCEP summaries; scanned state-plan pages
  read as their stamp or typed overlay (the 1,021 pages above are candidates; only the
  4 flagged attachments were confirmed). Reviewers' censuses, not re-verified
  here, add: 40 MA TAFDC section bodies with spaces inserted between Word runs; 30 WA EA-Z
  documents missing inline text; in the NH FAM, 2 inline-text omissions and 19 discarded
  policy-pointer headings; ND 510-05-100-* topics, 17 of 20 without their named
  attachments; ME §5111 (its table kept, its prose lost); 10 CA R&TC roots in the CA
  recovery scope whose blocks omit history notes beside menu children. A source-coverage
  check (visible source text against extracted text) would catch this class.
- **Reviewed-empty nodes.** 72 findings are correct as empty (refs pages, tables of
  contents, link indexes, cross-reference stubs, reserved items, repealed parts). A
  reviewed-empty list, or a reason recorded on the row, would let the check exempt them
  explicitly.

## Fixes

Extractor PR #854 (branch `fix/hollow-root-extractor-defects`), each change with tests:

- `nycrr.py::_document_body` reads `.co_refsAnnos` when a page has no `.co_body`.
  Recovers all 46 NY Notes bodies; Refs pages stay bodyless; section bodies unchanged.
- `documents.py::_pdf_page_text`: with `ocr`, a page is read by OCR when its text layer is
  empty (as before) or has fewer than 30 words with a letter while images of at least 100
  dpi cover at least 90% of the visible page (their exact union, measured in the crop
  box's frame, so rotation and crop offsets do not matter). A text-layer line is kept
  after the OCR text when one of its tokens with a digit is not among OCR's tokens, so
  typed values OCR misreads are never lost; lines with control characters (garbled fonts)
  are dropped. Recovers the 4 attachments.
- `documents.py`: a `start_after_pattern` (labeled DOCX, styled DOCX, PDF lines) or page
  window `start_at_pattern` that never matches now raises, as the HTML selectors already
  do. Of the 385 manifest documents that set one, 381 have retained sources: 379 extract
  as before and only MA 701 and 702 fail.
- Manifests: `INDEX_PAGE_EXTRACTION` in `scripts/build_cms_state_plan_manifests.py` and
  the 240 index pages in the 102 state-plan manifests (one block per SPA, headed by its
  transmittal number); `html_text_selector` for the 36 FCEP summaries;
  `html_text_selector` with the new opt-in `html_br_breaks` for the two MD TCA sections
  (subsections stay separate paragraphs); corrected start markers for MA 701 and 702.

Re-extracting the 46 non-NY fixable documents from their retained bytes into a scratch
corpus and re-running #847's check leaves none hollow and none with a navigation-only child.

## Recommendations

1. **Successor scopes** (new versions; the merged scopes stay as they are), then
   successor selectors: the two NY regulation scopes; the 102 CMS state-plan scopes
   (index pages and OCR); `us/policy/2026-07-05-cms-chip-fcep-spa`;
   `us-md/statute/2026-07-03-md-tca-statutes`;
   `us-ma/regulation/2026-06-27-ma-tafdc-regulations`;
   `ca/policy/2026-07-21-ca-rulespec-source-complete` (the builder fix is on main).
2. **CA WIC 11450 and rulespec-us CalWORKs**: land #752 (both concurrent versions of WIC
   11450 as variant rows), then repoint `monthly-aid-payment.yaml` at the version it
   encodes. The citation has had no corpus row in the releases selected since 2026-09-24.
3. **Illinois manual**: a successor that retains each item's page, or at least records in
   each row which page it came from, and that takes the Glossary and Abbreviations
   sub-pages. Guard
   `repair_us_release_source_references.py` so it cannot assign one snapshot to rows whose
   own `download_url` differs.
4. **Retain linked documents** where the HTML page is only a pointer: POMS exhibit and
   section PDFs, the ND hard card, the WA Apple Health flowchart.
5. **Successor completeness** for the ID and ME sections rulespec-us cites: both dated
   renditions of ID 63-3022E and 63-3025D (#823), and the ME lettered paragraphs (#754).
6. **Check refinements** listed above for #847: numeric tokens, a reviewed-empty
   exemption, and a source-coverage check for partial loss.
7. **Wider extractor robustness**: bare text in `<div>` and `<span>` is dropped by default
   whenever any paragraph or list item is present. A general fix needs a corpus-wide
   before/after comparison first. So does the DOCX table-cell run joining.
8. **Provenance**: correct the NY income-tax ingest manifest's recorded command in the
   successor.

## Reproduce

The evidence lives outside the repository, in `~/reviews/axiom-corpus-hollow-roots-2026-10-13/`
(see its `README.md` for every file's schema). It holds the baseline copy;
`build_dossier.py` (reproduces the 188 findings and builds per-finding evidence);
`scripts/build_table.py` (writes the CSV); `scripts/cms_index_sweep.py` (the index-page
counts); `scripts/pdf_text_layer_sweep.py` and `scripts/ocr_rule_sweep_all.py` (text
layers, and the pages the OCR rule reaches, with the scan rule); `scripts/start_marker_sweep.py`;
`scripts/il_item_states.py` (the Illinois page states, from the live pages kept there);
`scripts/reextract_verify.py` (the end-to-end check); `scripts/ocr_before_after.py` and
`scripts/ocr_before_after_diff.py` (the OCR rule's before/after extraction and its
comparison); and the reviewer briefs and reports (`briefs/`,
`out/`).
