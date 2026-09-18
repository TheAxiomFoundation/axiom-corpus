# Medicaid state eligibility manuals, batch 1

Date: 2026-09-10
Program: Medicaid (board Year 1 list; `manifests/medicaid-agent-queue.yaml`)
Agent: started_at 2026-09-10T16:35:28+0200, finished_at 2026-09-10T17:47:15+0200, wall time 1h 11m 47s (the last extraction, TX, finished 2026-09-10T17:25:54+0200, 50m 26s after start; the agent's session ended before the run note was finalized, and a follow-up controller session filled the TX counts, totals and this line, re-ran the tests, and committed; no manifests, queue rows or artifacts changed after 17:25:54).
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. No existing
function was modified: the only code added is `scripts/build_medicaid_state_eligibility_manual_manifests.py`.

## Batch selection (reviewer judgment)

Batch 1 = the two state rows already in the queue (AR, VA) plus the eight largest states by
population (CA, TX, FL, NY, PA, IL, OH, GA). States whose Medicaid eligibility chapters are already
in the corpus under a combined manual were marked `done` with a pointer and replaced by the next
largest state: IL (Cash, SNAP and Medical Manual) -> NC; FL (ESS Program Policy Manual) -> MI,
which is itself covered by the Bridges Eligibility Manual -> NJ. Attempted: AR, VA, CA, TX, NY,
PA, OH, GA, NC, NJ. Extracted: AR, VA, TX, NY, PA, GA, NC, NJ (8). Blocked: CA, OH (2).
Done-already (pointers, not counted): FL, IL, MI.

Family per state: the state Medicaid agency's eligibility policy manual (MAGI and non-MAGI
eligibility, income, resources, household composition), confirmed from the agency's own index page;
transmittals, bulletins, administrative letters, change notices and forms listed on the same index
are separate document families and were inventoried but not taken.

Scope: document_class `manual`, version `2026-09-10-medicaid-state-eligibility-manual`, citation
paths `us-xx/manual/<agency>/medicaid/<chapter or section>`, `source_as_of` and `expression_date`
2026-09-10 (current-effective manual trees as fetched; per-chapter effective dates printed inside
the documents were not parsed into `expression_date`; reviewer judgment).

Extraction: `uv run axiom-corpus-ingest extract-official-documents`, no new adapter. PDFs use the
extractor's default page granularity (one provision per text-bearing page plus the document root,
`ocr: true` so image-only pages fall back to Tesseract), the same shape as the Virginia SNAP manual
scope; HTML pages use `html_content_selector` per publisher. Section-level segmentation of the PDF
manuals is left for a later revision (reviewer judgment). TLS verification was never disabled and no
publisher needed a certificate bundle (no `data/certs` change). Hosts that 403 the Axiom user agent
(health.ny.gov) use the existing manifest option `request: browser_impersonation: true`.

Smoke runs (scratch base): VA complete (21 documents, 1,950 provisions); NY one PDF through the
browser-impersonation path; GA, TX, PA with `--limit 3`. The first full TX run failed on section
landing pages that carry only a "Pages in this section" sub-menu; the TX builder was rewritten to
crawl that hierarchy and the manifest selector scoped to `article.c-article div.c-field--name-body`
(the footer carries a same-named block). Coverage is `complete: true` with 0 missing, 0 extra and
0 duplicate citation paths for every extracted scope; duplicate-freedom of `citation_path` in each
provisions JSONL was verified independently with a counter.

## Per-jurisdiction results

| Jurisdiction | Index | Documents taken | Provisions | Extraction seconds |
| --- | --- | ---: | ---: | ---: |
| us-ar | DHS Division of County Operations, DCO Policies | 2 | 563 | 5 |
| us-va | DMAS Eligibility Manual | 21 | 1,950 | 46 |
| us-ny | DOH Medicaid Reference Guide | 8 | 978 | 8 |
| us-nj | DHS current administrative rules (Title 10) | 6 | 914 | 9 |
| us-ga | DFCS Medicaid Policy Manual (PAMMS) | 251 | 2,208 | 71 (re-run; first run 252 documents, 2,216 provisions, 68 s) |
| us-nc | DHB Adult / Family & Children's Medicaid manuals | 149 | 2,509 | 106 |
| us-pa | DHS Medical Assistance Eligibility Handbook | 380 | 1,297 | 101 |
| us-tx | HHSC MEPD Handbook + Texas Works Handbook Part A | 712 | 5,026 | 85 |

Total: 1,529 documents, 15,445 provisions across 8 scopes (after the Georgia re-run below). Index documents found
versus taken are in the queue rows (`index_document_count`, `taken_count`, `index_families`).

### Index inventories (every document family on the publisher index; taken counts)

**us-ar** — https://humanservices.arkansas.gov/divisions-shared-services/county-operations/division-policies/
Medical Services Policy Manual PDF (dated 09/01/2026 on the index) and Medical Services Appendices
PDF: 2 found, 2 taken. Other DCO program manuals on the same page (SNAP manual, SNAP appendices,
basis-of-issuance charts, TEA manuals and appendices): 11 found, 0 taken. The "Medicaid Quick Chart"
is listed without a PDF link. The MS manual is one 500-page PDF, so the scope has 2 documents and
563 page provisions; citation paths `us-ar/manual/dco/medicaid/policy-manual` and `.../appendices`.

**us-va** — https://www.dmas.virginia.gov/for-applicants/eligibility-guidance/eligibility-manual/
Manual chapter PDFs (Table of Contents, M00 appendix income charts, M01–M08, M11, M13–M18,
M20–M23): 21 found, 21 taken. Other PDF (language taglines): 1 found, 0 taken. Citation paths
`us-va/manual/dmas/medicaid/m04` etc. Note the DMAS chapter files carry effective dates in their
names (e.g. `m04-1-1-26a.pdf`); the TOC file is dated 7-2022.

**us-ny** — https://www.health.ny.gov/health_care/medicaid/reference/mrg/
Manual chapter PDFs (Introduction, Glossary, Categorical Factors, Income, Resources, Other
Eligibility Requirements, Reference, Cumulative/Master Index): 8 found, 8 taken. Full-manual PDF
(`mrg.pdf`, the same chapters concatenated): 1 found, 0 taken. Update-archive PDFs/HTML pages
(2000–2012 change lists): 13 found, 0 taken. Reviewer judgment: the MRG chapter files were last
modified in 2012 (HTTP Last-Modified); DOH still publishes the MRG as the reference guide, but current
NY eligibility policy is also carried in GIS/ADM directives, which are a separate family not in scope.

**us-nc** — https://policies.ncdhhs.gov/divisional-a-m/health-benefits-nc-medicaid/
ABD (Aged, Blind and Disabled) manual section PDFs incl. TOC: 79 found, 79 taken. Family and
Children's Medicaid manual section PDFs incl. TOC: 69 found, 69 taken. Basic Medicaid Eligibility
Requirements PDF: 1 found, 1 taken. ABD administrative letters 117, ABD change notices 126, FCM
administrative letters 118, FCM change notices 81, DHB forms 400, EIS documents 5: found, 0 taken.
Citation paths `us-nc/manual/dhb/medicaid/ma-2250`, `.../ma-3233-a`, `.../abd-adult-medicaid-table-of-contents`.

**us-ga** — https://pamms.dhs.ga.gov/dfcs/medicaid/
Numbered manual sections (2000–2985) as HTML pages: 241 found, 240 taken; section 2578 (SSI Recipients) is
inventoried under its own family and not taken because `manifests/us-ga-ssp-manual.yaml` already carries it in the
released scope `us-ga/manual/2026-07-13-recovery-r2026-07-17-dedup` under the same citation path
`us-ga/manual/dfcs/medicaid/2578` with byte-identical text (release deep validation rejects duplicate citation
paths across scopes). The scope was re-extracted after the controller removed it: 251 documents, 2,208 provisions,
coverage complete, 71 s. Appendix pages
(B hearings, B appeal, B OSAH responsibilities, C Medicaid issuance, E glossary, and the four
Appendix H administrative-review sub-pages listed on the Appendix H TOC): 11 found, 11 taken.
TOC pages (manual TOC, Appendix B/G/H TOCs): 6 found, 0 taken. PDF export of the whole manual: 1,
0 taken. Manual transmittal (MT) cover-letter PDFs on the Appendix G TOC: 169 found, 0 taken
(transmittal family). Extraction selector `article.doc` as in the GA SNAP manual scope.

**us-pa** — http://services.dpw.state.pa.us/oimpolicymanuals/ma/index.htm
RoboHelp handbook; topics enumerated from `whxdata/toc.new.js` and the nested `tocN.new.js` files
(917 TOC entries, 380 distinct topic pages once in-page anchors are collapsed). Handbook topic pages
(chapters 303–392 incl. chapter title pages): 380 found, 380 taken. Chapter 300 catalog pages
(Operations Memoranda, Policy Clarifications, Forms, title page): 4 found, 0 taken. The publisher
serves the handbook over plain http only (https connections time out), as for the PA SNAP handbook
scope. Extraction drops `.topic-header`/`.topic-header-shadow` as the SNAP scope does. Citation
paths keep the handbook's chapter/topic nesting, e.g. `us-pa/manual/dhs/medicaid/312-aca/312-title`.

**us-tx** — https://fhb.hhs.texas.gov/handbooks/medicaid-elderly-people-disabilities-handbook and
https://fhb.hhs.texas.gov/handbooks/texas-works-handbook
Texas splits Medicaid eligibility across two handbooks: MEPD (non-MAGI) and the Texas Works
Handbook (TWH; MAGI Medicaid interleaved with SNAP and TANF). Reviewer judgment: batch 1 takes the
whole MEPD handbook (chapter sections, appendices, glossary) and TWH Part A "Determining
Eligibility" (which holds the MAGI policy: A-200 household composition, A-800 Medicaid eligibility,
A-1300 income, ...). TWH Parts B–X (case management, appendix, CHIP, former foster care, refugee
medical assistance, Healthy Texas Women, MBCC) are inventoried below and left for a later batch.
Eleven TWH Part A sections are already in the corpus under `us-tx-manuals.yaml` (SNAP scope) with
different citation paths; this scope re-fetches them under `us-tx/manual/hhsc/medicaid/twh-*`.
Index families (MEPD handbook index and TWH index, 1,015 documents found, 712 taken): MEPD chapter landing pages 18 found, 0 taken; MEPD section pages 502 found, 502 taken; MEPD section landing pages (sub-menu only) 72 found, 0 taken; MEPD appendix pages 53 found, 53 taken; MEPD appendix landing pages 2 found, 0 taken; MEPD glossary 1 found, 1 taken; MEPD forms, notices, revisions and bulletins pages 5 found, 0 taken. TWH part landing pages 10 found, 0 taken; TWH Part A section pages 156 found, 156 taken; TWH Part A section landing pages 26 found, 0 taken; TWH Part B 14, Part C 14, Part D 23, Part E 24, Part F 24, Part M 24, Part W 24 and Part X 23 chapter pages found, 0 taken; TWH Part R (refugee medical assistance) is listed as a part but the builder found 0 chapter pages under it (reviewer should confirm on the live index). Citation paths `us-tx/manual/hhsc/medicaid/mepd-a-1000`, `.../mepd-appendix-*`, `.../mepd-glossary`, `.../twh-a-1000` etc. Extraction: 712 documents, 5,026 provisions (one root plus one per HTML block, 4,314 blocks), coverage complete, 85 s.

**us-nj** — https://www.nj.gov/humanservices/notices/rules-and-fees/rules-and-regulations/
The DMAHS "Eligibility and Service Manuals" page
(https://www.nj.gov/humanservices/dmahs/providers-stakeholders/provider-resources/eligibility/) now
only links to the LexisNexis N.J.A.C. site; the DHS Office of Legal and Regulatory Affairs hosts the
current chapter PDFs itself on the index above (the NJ SNAP rules scope uses the same host).
Medicaid eligibility chapters N.J.A.C. 10:69 AFDC-Related Medicaid, 10:70 Medically Needy, 10:71
Medicaid Only, 10:72 NJ Care Special Medicaid Programs Manual, 10:78 NJ FamilyCare, 10:79 NJ
FamilyCare Children's Program: 6 found, 6 taken. Other Title 10 chapters on the index: 109 found,
0 taken. Reviewer judgment: NJ's "manuals" are codified administrative code; this run follows the
work order (`document_class: manual`), whereas the NJ SNAP precedent (`us-nj-snap-rules.yaml`) used
`regulation`. The controller should pick one before publication.

### Blocked publishers (no workaround attempted)

**us-ca** — https://www.dhcs.ca.gov/services/medi-cal/eligibility/Pages/MEPM.aspx (Medi-Cal
Eligibility Procedures Manual index). HTTP 403 with an Imperva/Incapsula "Request unsuccessful"
interstitial (incident id 648000110623365723-464410415712436979) for the Axiom user agent, a plain
Chrome user agent, and curl-cffi impersonation profiles chrome120, chrome131, safari17_0,
firefox133 and edge101 (i.e. the existing `browser_impersonation` option cannot get through).
No index inventory possible.

**us-oh** — Ohio's eligibility manual is OAC 5160:1 on codes.ohio.gov (Ohio Laws and
Administrative Rules, the publisher used for the OH SNAP rules scope) plus ODM Medicaid Eligibility
Procedure Letters on medicaid.ohio.gov. codes.ohio.gov: TCP connect to 198.234.74.32:443 times out
(curl error 28 after 60–75 s; curl-cffi chrome120 the same; WebFetch ECONNREFUSED).
medicaid.ohio.gov and ohio.gov: every path including the site roots returns HTTP 404 (a 5,279-byte
error page) from this client and from WebFetch; only the dam.assets.ohio.gov asset host answers.
Retry from another network before treating this as a permanent block.

### Already in corpus (done, pointers)

- us-fl: `manifests/us-fl-ess-manual.yaml` (Florida DCF ESS Program Policy Manual, 48 documents)
  carries the MFAM/MSSI Medicaid chapters (1400/1600/1800 MFAM-MSSI, 2000 Coverage Groups, 2200,
  2400, 2600, Appendix A-7, A-9, A-9.1).
- us-il: `manifests/us-il-snap-manual.yaml` (Illinois DHS Cash, SNAP and Medical Manual, 4,750
  documents) includes PM/WAG 15 Eligibility for Medical Only Programs and PM/WAG 20 Medical Program.
- us-mi: `manifests/us-mi-bridges-manual.yaml` (Bridges Eligibility Manual, 196 documents) includes
  BEM 105–174, 211, 260, 402, 405, 530–547 (MA chapters).

### Federal row

42 CFR part 435 is already in the corpus as `us/regulation` version `2026-06-25-title-42-part-435`
(coverage complete, 168 provisions) plus the CMS-2454-IFC community-engagement scopes. 42 CFR part
436 is not in the corpus (no coverage file, manifest or ingest-run note mentions it). Nothing federal
was re-ingested; none of the federal lead-list URLs (medicaid.gov CIBs, eCFR/govinfo section links,
Federal Register documents, uscode.house.gov, the CHIP eligibility-levels page) were taken in this
run. The row stays `needs_review` with that finding.

## Artifacts (unsigned, uncommitted, awaiting controller)

- `data/corpus/sources/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual/official-documents/*`
- `data/corpus/inventory/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.json`
- `data/corpus/provisions/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.jsonl`
- `data/corpus/coverage/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.json`

for xx in ar, va, ny, nj, ga, nc, pa, tx.

Rebuild:

```bash
uv run python scripts/build_medicaid_state_eligibility_manual_manifests.py
for j in ar va ny nj ga nc pa tx; do
  uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-10-medicaid-state-eligibility-manual \
    --manifest manifests/us-$j-medicaid-eligibility-manual.yaml \
    --source-as-of 2026-09-10 --expression-date 2026-09-10
done
```

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped. All 10 failures are pre-existing data-dependent tests
(`test_be_rulespec_2026_08_23_promotion`, `test_build_ny_tanf_compatibility_scope` x2,
`test_rulespec_be_source_promotion`, `test_us_ak/ct/mi/mt/nd/ny_snap_manual`) that open
`data/corpus/...` artifacts which this sparse worktree does not check out (FileNotFoundError or an
existence assertion on those paths); none touch the Medicaid manifests or the generator.

## Reviewer judgments (all of them)

1. Batch selection rule (AR, VA + eight largest states; done-already states replaced by the next
   largest: IL->NC, FL->MI->NJ).
2. PDF manuals extracted at page granularity with OCR fallback rather than section segmentation.
3. `expression_date` = fetch date for every document instead of the chapter effective dates
   printed in the documents.
4. VA: the 2022 table of contents and the M00 income-chart appendix are taken as manual chapters.
5. NY: the eight MRG chapter PDFs (2012 files) are taken; the concatenated full-manual PDF and the
   update archive are not; GIS/ADM directives are out of scope.
6. NC: both the ABD and the Family & Children's manuals plus the Basic Requirements document form
   the family; letters, change notices, forms and EIS documents do not.
7. GA: TOC pages, the PDF export and the MT cover letters are not taken; the four Appendix H
   sub-pages are taken because the Appendix H TOC is the only index that lists them. Section 2578
   is not taken because the released SSP manual scope already carries it under the same citation path
   (controller change after `validate-release` on the draft successor selector flagged 8 duplicate
   citation paths). Section 2136 also exists in the unreleased, superseded scope
   `us-ga/manual/2026-06-24-ga-ssp` (7 rows); that scope is not in any release selector, so 2136 is
   kept here; a reviewer who re-releases the 06-24 scope must drop one side.
8. PA: the chapter 300 catalog pages are not taken (the PA SNAP handbook scope did take its
   equivalent chapter 500 catalog pages); anchors into one topic page are one document.
9. TX: MEPD in full plus TWH Part A only; TWH Parts B–X deferred; overlap with the eleven TWH
   sections already in `us-tx-manuals.yaml` under other citation paths.
10. NJ: N.J.A.C. Title 10 eligibility chapters ingested as `manual` per the work order although
    the NJ SNAP precedent used `regulation`; the DHS OLRA rules page used as the index because the
    Medicaid division's own manuals page defers to LexisNexis.
11. CA and OH recorded as blocked from this network; no impersonation beyond the existing manifest
    option, no proxying, no mirrors.
12. Federal: part 436 flagged as missing but not ingested in this run.

## Remaining for later batches

States not yet attempted (by population): WA, AZ, TN, MA, IN, MD, MO, WI, CO, MN, SC, AL, LA, KY,
OR, OK, CT, UT, IA, NV, MS, KS, NM, NE, ID, WV, HI, NH, ME, MT, RI, DE, SD, ND, AK, DC, VT, WY, plus
the territories. CA and OH need a retry from another network or an official export. TX TWH Parts B–X,
NC administrative letters/change notices, GA manual transmittals and NY GIS/ADM directives are
follow-on families. Federal 42 CFR part 436 needs an `extract-ecfr --only-title 42 --only-part 436`
run. Controller steps after review: `sign-ingest-manifest` per scope, immutable release selector,
`publish_corpus.py --dry-run`, then publication and activation.
