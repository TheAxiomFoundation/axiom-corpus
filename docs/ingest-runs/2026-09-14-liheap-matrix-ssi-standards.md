# LIHEAP benefit matrices and state manuals (LIHEAP-ST-09/ST-18) and SSI state-supplement payment standards (SSI-ST-4/ST-2)

Date: 2026-09-14
Work order: close the two state-level chart families of the needs-driven closure check
(`docs/coverage/needs-closure-2026-09-11/liheap.md`, `ssi.md`): LIHEAP-ST-09 (heating/cooling benefit matrix, a plan
attachment) for the 37 EXTRACTABLE and 13 REVIEW states, and SSI-ST-4 (state supplement payment standards by living
arrangement, current year) for the 10 REVIEW states, with SSI-ST-2 where the same publisher carries the authority.
Branch `discovery/ingest-liheap-matrix-ssi-standards` in the sparse worktree `~/axiom-corpus-worktrees/liheap-ssi-charts`
(`data/corpus/` excluded, never symlinked; re-synced to `origin/main` 5c2505ec6 on 2026-09-14 before the artifacts were
committed); every extraction wrote to the main checkout's corpus root (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`)
with `--source-as-of 2026-09-14`; the artifacts stay uncommitted for the controller. Versions
`2026-09-14-liheap-benefit-matrix` and `2026-09-14-ssi-state-supplement-standards`. Agent timing: discovery 2026-09-13
about 21:10 to 23:40 EDT (four read-only discovery sub-agents in parallel, about 13 minutes each, plus the direct probes),
manifests and extraction 2026-09-14 00:00 to about 01:30 EDT; per-scope extraction seconds are in the tables.
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. No library function was modified.
Code changes are two new generator scripts, `scripts/build_liheap_benefit_matrix_manifests.py` and
`scripts/build_ssi_state_supplement_standards_manifests.py`, whose STATES tables are the verified facts per state
(URLs, dates, matrix pages, access evidence) and whose queue writers add one record per jurisdiction row.
Disk: `df -g ~` 32 GB free at start, 29 GB at the end (the 65 source directories total about 190 MB); the 5 GB stop
line was checked before every LIHEAP extraction.

Totals: LIHEAP 55 scopes over 47 jurisdictions, 208 documents, 4,041 provision rows; SSI 10 scopes over 8 jurisdictions,
23 documents, 140 rows. Every scope reports coverage `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths;
no document is without a text-bearing row (checked over the JSONL); no new citation path exists in any other scope on
the controller's disk (checked against every `provisions/us-*/*/*.jsonl`), so nothing collides and no consolidation is
needed. Coverage cannot see an empty body, so the image-only documents were read with `ocr: true` at 300 dpi and their
rows opened by hand (New Jersey grid 1,732 characters, Maryland EUSP matrix 986, the Virginia attachment 335 per page).

## Publisher access (2026-09-13/14)

- `liheapch.acf.gov` (the HHS/ACF LIHEAP Clearinghouse, operated by ACF/OCS through NCAT) still omits its Entrust
  intermediate; every Clearinghouse fetch used `REQUESTS_CA_BUNDLE` = certifi + `data/certs/entrust-dv-tls-issuing-rsa-ca-2.pem`
  (the bundle file `data/certs/liheapch-ca-bundle.pem` is rebuilt from those two, as the 2026-09-10 plan run did).
  Verification was never disabled. The 'State LIHEAP Policy Manuals' list on `stateplans.htm#MANUALS` (39 links: 38
  states, Vermont as two rule links) is the index every EXTRACTABLE row was checked against. The Clearinghouse also
  serves the plan attachments under `/docs/2026/benefits-matricies/XX_BenefitMatrix_2026.pdf` (21 states) and
  `/docs/2025/...` (33 states); no index page read (stateplans, the state profile pages, tables/benefits.htm,
  delivery/benefits.htm, snapshots) links them, so they are recorded as unindexed publisher files located by the
  publisher's own naming and taken only where the state itself posts no matrix (13 states below).
- Publisher decision: the Clearinghouse counts as an official publisher (HHS/ACF-operated index), as the 2026-09-10 plan
  run decided; the state agency's own copy is preferred when both exist (Arkansas, Louisiana, Maryland, New Jersey,
  Tennessee, California noted). Clearinghouse-hosted manuals (Florida, Georgia, South Dakota) carry `hosting_authority`.
- Blocked to the plain client, served to a chrome120 TLS fingerprint (`browser_impersonation`, verification on):
  `des.az.gov` (403, 5,578 bytes), `michigan.gov` (403, 503 bytes), `energy.nh.gov` (403, 524 bytes), `mass.gov`
  (403 to plain and Chrome-UA clients; pages and the DTA SSP chart 200 to chrome120, but the EOHLC HEAP chart downloads
  answer 404 even then), `dhhs.nh.gov` (403 / 200, as the 2026-09-10 SSI batch found), `dhs.state.mn.us` (HTTP 200
  with a 15 KB Radware challenge to plain and Chrome-UA clients; the manual page to chrome120, fetched with
  `browser_impersonation_direct`).
- Blocked outright, nothing worked around: `otda.ny.gov` (connection reset to plain clients; F5/Shape JavaScript
  challenge, 7,510 bytes, to chrome120: HEAP manual, HEAP page and the 2025-26 HEAP GIS alike); `jfs.ohio.gov` (404 to
  the plain client, 1.1 MB single-page application to a Chrome UA, HEAP page 502/504 to chrome120); `rules.ok.gov`
  (Cloudflare 403; its API served the SSP rule text but not the appendix); the Texas SOS administrative code portal
  (JavaScript shell only). No mirror, archived copy or proxy was used anywhere; the Clearinghouse-listed Ohio manual on
  `irp.cdn-website.com` (a third-party CDN) and the Kentucky link (a weatherization plan on kyhousing.org, the wrong
  program) were not taken.
- Third-party hosting of a publisher's own files: Tennessee's THDA serves its PDFs from its WordPress asset
  distribution (`dogvxws799i6n.cloudfront.net`), linked directly from the thda.org index page; Delaware's manual is on
  `bidcondocs.delaware.gov` (a state.delaware.gov service); Virginia's DARS rate letter is on dss.virginia.gov; Ohio's
  RSS brochure on `dam.assets.ohio.gov`. Each carries `hosting_authority` in metadata.
- TLS chains were intact elsewhere; `img1.scdhhs.gov` (Go Daddy G2 intermediate already in `data/certs`) lists the
  MPPM but links no Chapter 103, so nothing was fetched from it.

## Family 1: LIHEAP-ST-09 / ST-18, benefit matrices and state manuals (50 states + DC)

Method. Every Clearinghouse manual link was probed with the plain client (37 URLs: 22 served a PDF, 3 served only with
chrome120, 6 answered 404, 3 were the wrong or a non-official document, 3 were HTML manuals or index pages), the served
PDFs were opened with pdftotext for the dollar-dense pages, and four read-only discovery sub-agents inventoried the
agency sites of the 13 REVIEW states, the 13 states with dead or wrong links, and the 8 states whose manual prints no
matrix. The document classes follow the document: state policy/operations manuals and appendices `manual`; adopted
rules (Colorado 9 CCR 2503-7, Maine Chapter 24, Mississippi Title 18 Part 24, Vermont rules 2900 and 3100) `regulation`;
benefit matrices, plan attachments and allocation plans `policy` (the class of the FY 2026 plans; Clearinghouse copies
sit under `us-xx/policy/acf/liheap-plan/fy2026-benefit-matrix`, the plans' own path family); Nebraska's DHHS 'Guidance
Document' `guidance`. PDFs are page-granular (`page-N` counts text-bearing pages; the manifest metadata
`benefit_matrix_pdf_pages` gives the PDF page numbers with a `page_numbering_note`); the two RoboHelp HTML manuals
(Alaska HAP, Pennsylvania LIHEAP Handbook) were walked from their `whxdata/toc*.new.js` tables of contents (66 and 75
topic pages, the NH Adult Assistance Manual method) and extracted as HTML blocks; the District's matrix is a Word file.

| jurisdiction | class | documents | rows | extract s | coverage |
| --- | --- | ---: | ---: | ---: | --- |
| us-ak | manual | 66 | 132 | 11 | complete |
| us-ak | policy | 1 | 7 | 2 | complete |
| us-al | manual | 1 | 78 | 1 | complete |
| us-ar | policy | 6 | 17 | 2 | complete |
| us-az | manual | 1 | 42 | 1 | complete |
| us-ca | policy | 1 | 8 | 1 | complete |
| us-co | regulation | 1 | 39 | 2 | complete |
| us-ct | policy | 1 | 20 | 3 | complete |
| us-dc | policy | 1 | 2 | 0 | complete |
| us-de | manual | 1 | 98 | 2 | complete |
| us-fl | manual | 1 | 74 | 2 | complete |
| us-ga | manual | 1 | 90 | 2 | complete |
| us-hi | manual | 1 | 23 | 1 | complete |
| us-hi | policy | 1 | 4 | 2 | complete |
| us-ia | manual | 1 | 115 | 2 | complete |
| us-in | manual | 1 | 112 | 1 | complete |
| us-ks | policy | 1 | 5 | 2 | complete |
| us-la | manual | 1 | 109 | 1 | complete |
| us-la | policy | 1 | 61 | 1 | complete |
| us-ma | policy | 1 | 4 | 2 | complete |
| us-md | manual | 1 | 164 | 1 | complete |
| us-md | policy | 2 | 6 | 4 | complete |
| us-me | regulation | 1 | 34 | 2 | complete |
| us-mi | manual | 2 | 96 | 1 | complete |
| us-mn | manual | 1 | 309 | 4 | complete |
| us-mo | manual | 1 | 130 | 2 | complete |
| us-ms | regulation | 1 | 65 | 1 | complete |
| us-mt | manual | 1 | 136 | 4 | complete |
| us-nc | manual | 1 | 23 | 1 | complete |
| us-nd | manual | 1 | 370 | 2 | complete |
| us-ne | guidance | 1 | 7 | 1 | complete |
| us-nh | manual | 1 | 102 | 2 | complete |
| us-nh | policy | 1 | 3 | 1 | complete |
| us-nj | manual | 1 | 26 | 1 | complete |
| us-nj | policy | 1 | 2 | 3 | complete |
| us-nm | policy | 1 | 2 | 1 | complete |
| us-nv | manual | 1 | 117 | 2 | complete |
| us-nv | policy | 1 | 3 | 1 | complete |
| us-oh | policy | 1 | 2 | 1 | complete |
| us-ok | manual | 1 | 3 | 1 | complete |
| us-or | manual | 1 | 95 | 2 | complete |
| us-pa | manual | 75 | 204 | 5 | complete |
| us-pa | policy | 1 | 470 | 3 | complete |
| us-sc | policy | 1 | 3 | 1 | complete |
| us-sd | manual | 1 | 61 | 2 | complete |
| us-sd | policy | 1 | 2 | 1 | complete |
| us-tn | manual | 1 | 68 | 2 | complete |
| us-tn | policy | 2 | 7 | 2 | complete |
| us-ut | manual | 1 | 54 | 1 | complete |
| us-va | manual | 1 | 139 | 2 | complete |
| us-va | policy | 1 | 8 | 10 | complete |
| us-vt | manual | 6 | 24 | 3 | complete |
| us-vt | regulation | 2 | 81 | 1 | complete |
| us-wa | policy | 1 | 6 | 1 | complete |
| us-wi | manual | 1 | 179 | 3 | complete |

Per-state result (ST-09 status after this run; ST-18 closes wherever a manual or rule scope above exists):

- Matrix taken from the state agency: AR (five FFY 2026 fuel matrices and the eligibility chart, Arkansas Energy Office),
  CT (FFY 2026 allocation plan, basic benefit levels pages 10-11), DC (DOEE FY26 benefit matrix, docx), LA (LHC's own
  FFY 2026 model plan, whose PDF page 60 is the heating and cooling benefit matrix; the Clearinghouse plan copy omits it),
  MD (FY27 MEAP and EUSP matrices, program year from 2026-07-01), NJ (FY 2026 benefit grid, image-only, OCR; byte-identical
  to the Clearinghouse copy; the DCA pages now link the FY 2027 grid as a PNG), NM (FFY 2026 point and income guide),
  TN (2026 and FY 2027 matrices), OK (Appendix C-7-A), NC (EP-300 change #2-2026, chart on page 19).
- Matrix printed in the manual or rule taken: AL (payment assistance chart PY 2025, PDF page 57), AZ (page 39), CO (rule
  points table, page 33), IA (22-23), IN (60-71), MO (Appendix K, page 129, still labelled FFY 24), MS (39), MT (122-125),
  ND (137, 201, 245), NE (payment table, pages 3-4, effective 10/1/25), NH (19, 78), NV (63-64, 111-113), OR (77-80),
  SD (50), UT (37), VT (procedures P2915 and P2916 tables, rule 2914 steps), HI (points allocation, 19-20).
- Matrix taken from the Clearinghouse attachment family because the agency posts none: AK (FY 2026 benefit computation),
  CA (2026 county base benefit amounts; CSD's own 442-page plan prints the same tables on pages 182-188 and is noted),
  HI (2026 income tables), KS (LIEAP benefits matrix; KEESM 13000 already selected), MA (FY 2026 income eligibility and
  benefit levels; the EOHLC chart download is dead), NH (PY26 benefits), NV (FY 2026 Appendix A), OH (2025 benefit
  matrix headed DRAFT Funding, the FY 2026 plan attachment), PA (2025-2026 benefit charts for all 67 counties, 469
  pages), SC (2026 benefit matrix), SD (HY2026 regional matrix), VA (manual excerpts with the FFY 2026 income limits,
  OCR), WA (benefit calculation worksheet; Washington uses a formula).
- Manual or rule taken, matrix ABSENT: DE (manual says 'see current Delaware State Plan'; DHSS posts no plan or chart),
  FL and GA (manuals and plans refer to an attached matrix that neither the agency nor the Clearinghouse posts for 2026),
  ME (rule Chapter 24 and the 2026 HEAP state plan defer to a HEAP Guide that MaineHousing does not post; the linked
  PY2026 guide URL answers a 'Page Cannot Be Found' page), MI (MEAP manual computes the benefit; MDHHS ERM 301 carries
  the SER energy payment caps effective 2025-10-01; the Home Heating Credit table is a Treasury form, not inventoried),
  MN (chapter 4 computes the benefit from energy cost and income), WI (the HE+ system calculates benefits; PY 2026
  manual taken, PY 2027 also posted).
- ABSENT, nothing taken: ID, IL, WY (plans refer to a matrix that is not attached; the Clearinghouse serves only 2025
  files), KY (the Clearinghouse link is the weatherization health-and-safety plan; CHFS posts narrative only), RI (DHS
  posts the income table only; the Clearinghouse RI file is a provisional placeholder headed 'to be input 9/30/2025'),
  TX (a sliding scale in 10 TAC 6.309(e), no table; the rule sits on the SOS JavaScript portal), WV (the Clearinghouse
  lists the legacy wvdhhr.org chapter 26 files, dated to 2014, which refer to an unpublished payment chart; the current
  DoHS Income Maintenance Manual in the selected corpus assigns chapter 26 to the Medicaid Work Incentive and has no
  LIEAP chapter; BFA posts the FY 2026 fact sheet and plan only).
- BLOCKED: NY (OTDA JavaScript challenge, evidence above).

Decisions on the REVIEW cells: CA, DC, NC, NM, OK became EXTRACTABLE and were taken from the agency; MA, SC, WA became
EXTRACTABLE via the Clearinghouse attachment; ID, IL, RI, TX, WY are ABSENT with the evidence above. Of the 37
EXTRACTABLE cells, 33 were taken (matrix or manual), KY and WV are ABSENT (wrong or superseded document), NY is
OUTREACH/BLOCKED, and OH's manual is on a non-official host (its Clearinghouse attachment was taken instead).

Still missing: the FY 2026 matrices of DE, FL, GA, ME, MN, WI (formula or unpublished), ID, IL, KY, RI, TX, WY, WV;
New York entirely; the Pennsylvania county benefit table as the DHS dynamic lookup (the 2025-2026 charts stand in);
the Maine HEAP Guide; Colorado's current CCR rendition of 9 CCR 2503-7 (the Secretary of State's DisplayRule pages need
a browser session; the rendition the Clearinghouse links, ruleVersionId 7308 of 2017, is taken as listed and recorded
in the manifest note).

## Family 2: SSI-ST-4 / ST-2, state supplement payment standards (10 REVIEW states)

| jurisdiction | class | documents | rows | extract s | coverage |
| --- | --- | ---: | ---: | ---: | --- |
| us-ma | guidance | 1 | 2 | 1 | complete |
| us-mn | manual | 1 | 3 | 9 | complete |
| us-mn | statute | 1 | 15 | 0 | complete |
| us-ne | manual | 2 | 5 | 2 | complete |
| us-nh | guidance | 2 | 5 | 1 | complete |
| us-oh | guidance | 1 | 3 | 1 | complete |
| us-ok | manual | 1 | 9 | 1 | complete |
| us-sc | guidance | 1 | 72 | 1 | complete |
| us-va | guidance | 1 | 2 | 1 | complete |
| us-va | regulation | 12 | 24 | 4 | complete |

- MA: DTA 'Federal and State Payment Levels for Calendar Year 2026' (SSP amounts by SSI category and state living
  arrangement A, B, C, E, F, G), the current chart of the eleven (CY 2016-2026) the DTA SSP page lists. ST-4 closed.
- MN: Combined Manual 0020.21 MSA Assistance Standards, issue date 03/2026, with the 2026 monthly standards (living
  alone $1,055.00, with others $755.33, couples $1,582.00 / $1,058.00, pre-1994 couples), the current page of the
  section whose 09/2020 print is the stale page in the selected Combined Manual PDF scope (the sibling .doc is a 2021
  revision, not taken); Minn. Stat. 256D.44 (2025 Minnesota Statutes, 15 rows) for ST-2. Both closed.
- NE: 469-000-211 AABD/SDP Standard of Need (rev. 2021-01-01, the latest posted on the Title 469 appendix index) and
  477-000-044 ABD Standard of Need (rev. 2025-12-17, the 2026 figures in the same living-arrangement structure, issued
  under the Medicaid title). ST-4 closed with the 2026 figures; the AABD cash appendix itself is stale, recorded.
- NH: re-graded PRESENT: AAM 601 Table A in the selected 2026-09-10 scope carries the 2026 standards in its block-2 row
  (the closure check read the 60-character block-1 stub). Taken in addition: SR 26-01 dated 01/26 (the transmittal of
  the 2026 COLA-driven standards) and the BDS memo of 2026-01-01, both guidance.
- OH: re-graded PRESENT: OAC 5122-36-05(B)-(C) in the selected scopes prints the RSS payment level (one thousand six
  hundred dollars per month plus a personal needs allowance of at least two hundred dollars, effective 2023-07-01);
  DBH publishes no later rate. The DBH RSS brochure (2024) was taken as guidance.
- OK: OKDHS Appendix C-1 Maximum Income, Resource, and Payment Standards, 7/1/2026 (8 pages; Schedule VIII.A on PDF
  page 3: SSP categorically needy standard, individual $1,034, with spouse $1,532, couple $1,571, SSP amount at most
  $40), the appendix OAC 340:15-1-5 cites, from the OKDHS forms search center. ST-4 closed.
- SC: the SCDHHS 'Program Eligibility and Income Limits' page (Optional State Supplementation: monthly net income limit
  $1,804, resources $2,000, dated January 1, 2026), the publisher's current statement of the OSS limit; the current
  MPPM 103 is not linked from the img1.scdhhs.gov index (the only fetchable Chapter 103 is a 2014 Word 97 file, not
  taken); S.C. Code Title 43 chapter 5 carries no OSS rate (set by appropriations proviso). ST-4 closed as guidance.
- VA: the DARS Auxiliary Grant rate letter of 2025-11-10 (rate $2,130, Planning District 8 $2,450, effective 2026-01-01,
  personal needs allowance $87) linked from the VDSS assisted-living page, and all 12 sections of 22VAC30-80 from
  Virginia LIS for ST-2. Both closed.
- KS: ABSENT for the current year: the SSPP pays a flat $20 to institutionalized eligibles under the 2007 KHPA memo
  (already in `us-ks/guidance/2026-07-04-ks-sspp-guidance`) and KDHE has published nothing later (the April 2026 Kansas
  Medical Assistance manual, 121 topics, has no SSPP topic); K.S.A. 39-972 is on disk as
  `us-ks/statute/2026-07-04-ks-sspp-statute`, unselected (controller: select it for ST-2). Nothing new taken.
- SD: ABSENT: ARSD 67:12:14:04 pays 'at a rate approved by the department' and DSS publishes no rate (home, economic
  assistance, medical programs, forms pages and the DSS Handbook checked; SSA's state assistance series ends with the
  January 2011 edition). Nothing taken.

## Queue records

Each LIHEAP state row gains a `benefit_matrix_scope` record (status taken / absent / blocked, the scopes with manifest
and document counts, `index_url` = the Clearinghouse manuals index with `index_document_count` 39,
`publisher_index_url`, `on_clearinghouse_index`, `taken_count`, `matrix_status`, `closure_elements`, `run_note`, `notes`)
and a dated sentence in `notes`; each SSI row gains a `standards_scope` record of the same shape (`index_url` = the
publisher page, `closure_elements` SSI-ST-4 and, for MN and VA, SSI-ST-2). Rows are written by the two generators only
(`update_queue`); `yaml.safe_dump` rewrites the files as the earlier generators did. Verified after writing: every
`scopes` entry in both queues has a coverage file on disk with `complete: true`, and every coverage file of the two
versions is referenced by exactly one queue record.

## Tests

`uv run ruff check .`: passes. `uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or
official_documents or discovery or liheap or ssi"` in the sparse worktree: 365 passed, 8 skipped, 22 failed, every
failure a `FileNotFoundError` (three surfacing as assertions) on other scopes' `data/corpus` artifacts the sparse checkout
does not contain: `test_armenia_arlis` (x2), `test_be_rulespec_2026_08_23_promotion`, `test_build_ny_tanf_compatibility_scope`
(x2), `test_corpus_release_quality::test_historical_us_selector_retains_legacy_expression_date_warnings`,
`test_israel_openlaw`, `test_nz_rulespec_legacy_migration`, `test_rulespec_be_source_promotion`, the AK, CT, MI, MS (x2),
MT, ND and NY SNAP manual tests, and `test_us_or_2026_pit_session_laws` (x5). None touches the two generators, the 65
manifests or the queue files (a plain `uv run pytest` resolves to the system pytest in this worktree; `--extra dev` is
needed). No adapter was added, so no new tests; the two generators are data tables plus the RoboHelp TOC walk.

## Controller

Selector additions (artifacts unsigned, on the controller's disk under `/Users/pavelmakarchuk/axiom-corpus/data/corpus`,
not committed), as `jurisdiction / document_class / version`:

| jurisdiction | document_class | version |
| --- | --- | --- |
| us-ak | manual | 2026-09-14-liheap-benefit-matrix |
| us-ak | policy | 2026-09-14-liheap-benefit-matrix |
| us-al | manual | 2026-09-14-liheap-benefit-matrix |
| us-ar | policy | 2026-09-14-liheap-benefit-matrix |
| us-az | manual | 2026-09-14-liheap-benefit-matrix |
| us-ca | policy | 2026-09-14-liheap-benefit-matrix |
| us-co | regulation | 2026-09-14-liheap-benefit-matrix |
| us-ct | policy | 2026-09-14-liheap-benefit-matrix |
| us-dc | policy | 2026-09-14-liheap-benefit-matrix |
| us-de | manual | 2026-09-14-liheap-benefit-matrix |
| us-fl | manual | 2026-09-14-liheap-benefit-matrix |
| us-ga | manual | 2026-09-14-liheap-benefit-matrix |
| us-hi | manual | 2026-09-14-liheap-benefit-matrix |
| us-hi | policy | 2026-09-14-liheap-benefit-matrix |
| us-ia | manual | 2026-09-14-liheap-benefit-matrix |
| us-in | manual | 2026-09-14-liheap-benefit-matrix |
| us-ks | policy | 2026-09-14-liheap-benefit-matrix |
| us-la | manual | 2026-09-14-liheap-benefit-matrix |
| us-la | policy | 2026-09-14-liheap-benefit-matrix |
| us-ma | policy | 2026-09-14-liheap-benefit-matrix |
| us-md | manual | 2026-09-14-liheap-benefit-matrix |
| us-md | policy | 2026-09-14-liheap-benefit-matrix |
| us-me | regulation | 2026-09-14-liheap-benefit-matrix |
| us-mi | manual | 2026-09-14-liheap-benefit-matrix |
| us-mn | manual | 2026-09-14-liheap-benefit-matrix |
| us-mo | manual | 2026-09-14-liheap-benefit-matrix |
| us-ms | regulation | 2026-09-14-liheap-benefit-matrix |
| us-mt | manual | 2026-09-14-liheap-benefit-matrix |
| us-nc | manual | 2026-09-14-liheap-benefit-matrix |
| us-nd | manual | 2026-09-14-liheap-benefit-matrix |
| us-ne | guidance | 2026-09-14-liheap-benefit-matrix |
| us-nh | manual | 2026-09-14-liheap-benefit-matrix |
| us-nh | policy | 2026-09-14-liheap-benefit-matrix |
| us-nj | manual | 2026-09-14-liheap-benefit-matrix |
| us-nj | policy | 2026-09-14-liheap-benefit-matrix |
| us-nm | policy | 2026-09-14-liheap-benefit-matrix |
| us-nv | manual | 2026-09-14-liheap-benefit-matrix |
| us-nv | policy | 2026-09-14-liheap-benefit-matrix |
| us-oh | policy | 2026-09-14-liheap-benefit-matrix |
| us-ok | manual | 2026-09-14-liheap-benefit-matrix |
| us-or | manual | 2026-09-14-liheap-benefit-matrix |
| us-pa | manual | 2026-09-14-liheap-benefit-matrix |
| us-pa | policy | 2026-09-14-liheap-benefit-matrix |
| us-sc | policy | 2026-09-14-liheap-benefit-matrix |
| us-sd | manual | 2026-09-14-liheap-benefit-matrix |
| us-sd | policy | 2026-09-14-liheap-benefit-matrix |
| us-tn | manual | 2026-09-14-liheap-benefit-matrix |
| us-tn | policy | 2026-09-14-liheap-benefit-matrix |
| us-ut | manual | 2026-09-14-liheap-benefit-matrix |
| us-va | manual | 2026-09-14-liheap-benefit-matrix |
| us-va | policy | 2026-09-14-liheap-benefit-matrix |
| us-vt | manual | 2026-09-14-liheap-benefit-matrix |
| us-vt | regulation | 2026-09-14-liheap-benefit-matrix |
| us-wa | policy | 2026-09-14-liheap-benefit-matrix |
| us-wi | manual | 2026-09-14-liheap-benefit-matrix |
| us-ma | guidance | 2026-09-14-ssi-state-supplement-standards |
| us-mn | manual | 2026-09-14-ssi-state-supplement-standards |
| us-mn | statute | 2026-09-14-ssi-state-supplement-standards |
| us-ne | manual | 2026-09-14-ssi-state-supplement-standards |
| us-nh | guidance | 2026-09-14-ssi-state-supplement-standards |
| us-oh | guidance | 2026-09-14-ssi-state-supplement-standards |
| us-ok | manual | 2026-09-14-ssi-state-supplement-standards |
| us-sc | guidance | 2026-09-14-ssi-state-supplement-standards |
| us-va | guidance | 2026-09-14-ssi-state-supplement-standards |
| us-va | regulation | 2026-09-14-ssi-state-supplement-standards |

Also for the controller: select `us-ks/statute/2026-07-04-ks-sspp-statute` (K.S.A. 39-972, on disk, unselected) for
SSI-ST-2; the New Hampshire and Ohio SSI-ST-4 cells are PRESENT in already-selected scopes (re-graded above). Note the
two `us-ok/manual` scopes of this run (LIHEAP Appendix C-7-A and SSI Appendix C-1) share a class and differ by version;
the MN Combined Manual page adds `us-mn/manual/dhs/combined-manual/0020-21` beside the selected `.../current/page-N`
scope (distinct paths, no supersession).

Rebuild:

```bash
uv run python scripts/build_liheap_benefit_matrix_manifests.py          # 55 manifests + liheap-agent-queue records
uv run python scripts/build_ssi_state_supplement_standards_manifests.py # 10 manifests + ssi-agent-queue records
python3 -c "import certifi,pathlib; pathlib.Path('data/certs/liheapch-ca-bundle.pem').write_text(pathlib.Path(certifi.where()).read_text()+'\n'+pathlib.Path('data/certs/entrust-dv-tls-issuing-rsa-ca-2.pem').read_text())"
export REQUESTS_CA_BUNDLE=$PWD/data/certs/liheapch-ca-bundle.pem
for m in manifests/us-*-liheap-benefit-matrix-*.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-14-liheap-benefit-matrix --manifest "$m" --source-as-of 2026-09-14
done
for m in manifests/us-*-ssi-state-supplement-standards-*.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-14-ssi-state-supplement-standards --manifest "$m" --source-as-of 2026-09-14
done
```
