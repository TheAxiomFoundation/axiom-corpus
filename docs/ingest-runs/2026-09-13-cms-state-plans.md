# CMS-posted Medicaid and CHIP state plans (medicaid.gov), 50 states + DC

Date: 2026-09-13
Programs: Medicaid and CHIP (needs-driven closure check `docs/coverage/needs-closure-2026-09-11/{medicaid,chip}.md`,
"CMS-posted approved state plan" family, the single largest state-level gap: about 2,560 Medicaid cells and
1,180 CHIP cells).
Branch: `discovery/ingest-cms-state-plans` (sparse worktree `~/axiom-corpus-worktrees/cms-state-plans`, cut from
`origin/main` 8dc613000; artifacts written to the main checkout's `data/corpus`, uncommitted).
Generator: `scripts/build_cms_state_plan_manifests.py` (new). One small edit to
`scripts/build_chip_state_eligibility_manifests.py` so a rerun carries the second per-jurisdiction queue row through.
Impact analysis: not run; the GitNexus MCP tools were not available in this session. No library function was modified.
Timing: started 2026-09-13T19:35Z (discovery), extraction driver started 2026-09-13T20:06:49Z; in progress at this checkpoint.

## Discovery: what CMS actually hosts

The work order and the closure check assumed medicaid.gov posts each state's compiled approved Medicaid state plan
(attachment 2.2-A, sections 2.1-2.6, 2.6-A supplements, 4.18) and each state's compiled CHIP state plan (sections
1-9). Probed 2026-09-13 (curl_cffi chrome120 impersonation; plain clients get Akamai HTTP 403 "Access Denied",
444 bytes, for every medicaid.gov path):

- **medicaid.gov posts no compiled Medicaid state plan for any state.** The old `/medicaid/medicaid-state-plan-amendments/index.html`
  and `/state-overviews/index.html` paths answer 404; the state-profiles page is an SVG map with no per-state document
  links; the sitemap (1,543 URLs) has no per-state state-plan page. Compiled Medicaid plans are hosted by the states
  (the AL, CA, NE publishers that block are exactly the ones the closure check flagged).
- **What CMS does host is the SPA record.** The "Medicaid State Plan Amendments" search
  (`/medicaid/medicaid-state-plan-amendments`, Drupal/Solr, 16,727 records; 16,489 for the 50 states + DC) lists every
  approved SPA with transmittal number, state, summary, approval and effective dates, topic tags (107 topics) and links
  to the approval package PDF (approval letter, CMS-179, **the approved state plan pages**: the amended attachment
  2.2-A / 2.6-A supplement / 4.18 / MACPro S-series pages as approved). The topic "Current State Plan" (253 records) is
  a tag on ordinary SPAs, not a compiled plan; "State Plan Factsheet" carries 5 Medicaid records.
- **CHIP.** The "CHIP State Plan Amendments" search (`/chip/state-program-information/chip-spa`, 1,007 records; 1,006
  for the 50 states + DC, 25 topics) lists every approved CHIP SPA the same way, and additionally carries one
  CMS-compiled **"Current State Plan" PDF plus a factsheet per state** (topic "State Plan Factsheet", 47 records,
  compiled 2010-2011 "as amended by SPA n"; e.g. `/CHIP/Downloads/AL/ALCurrentStatePlan.pdf`, 66 pages, text-bearing).
  Several older records also link a "Final Approved State Plan" PDF. So the CMS-hosted CHIP plan is the 2010-11
  compiled plan plus every later approval package.
- The `/chip/state-program-information` page itself is two SVG maps (program structure, FCEP) fed by JSON files
  already in the corpus (`us/form/2026-07-05-cms-chip-children-coverage-map`).

Reviewer judgment on the family: the CMS-hosted "approved state plan" is modeled as **the state's SPA index plus the
approval packages of every eligibility-bearing SPA**. That is what closes the closure schema's `M-SS-SPA`, `M-435-10`,
`M-435-814`, `M-435-843`, `C-SS-STATE-PLAN`, `C-457-50`, `C-457-60`, `C-457-305` elements (SPA on record, approved
plan, SPA process) and carries the approved plan pages the other `plan_family` elements name, **for the pages a state
has amended since CMS began posting packages (about 2009; MACPro pages since 2014)**. Plan pages a state has not
amended since then are not on medicaid.gov at all and stay with the state's own compiled plan (see "Still missing").

## Method

- **Per state, per program** the generator crawls the state's SPA index (`filter[field_state][in][]=<id>`, 100 per
  page, sorted by approval date; records are de-duplicated by Drupal node id and a shortfall is re-filled from a
  title-sorted pass, because Solr ties move records across page boundaries between requests; the count is checked
  against the index's own total). Listings are cached under the scratchpad for reruns (`--cache`).
- **Taken:** (1) every index page as an HTML document (`us-xx/policy/cms/<program>-state-plan/spa-index/pNN`,
  `html_content_selector: .medicaid-solr-searches-results`; the accordion's record headings sit in `<button>`s the
  extractor drops, so each page yields one block with every record's summary, dates, link labels and topics);
  (2) every PDF link of every record tagged with an eligibility-bearing topic — Medicaid: Eligibility, Cost Sharing,
  Premiums, Current State Plan, Blind Disabled, Medicaid Expansion, Affordable Care Act, Individual CoPayments or
  Insurance Payments, Outreach & Enrollment, State Plan Factsheet, Third Party Liability, Children's Health Insurance
  Program; CHIP: Eligibility, Cost Sharing, Premiums, Current State Plan, State Plan Factsheet, Enrollment, Outreach &
  Enrollment, Expansion, MCHIP Program, Benefits, Dental — plus the CHIP compiled-plan records
  (`.../compiled/current-state-plan`, `.../compiled/factsheet`). SPA PDFs sit at
  `.../spa/<transmittal-slug>/<link-label-slug>` (approval-document, approval-package, form-cms-179, attachment,
  final-approved-state-plan; `-2`, `-3` suffixes when a record repeats a label).
- **Inventoried, not taken:** records tagged only with other topics (reimbursement, drugs, managed care, program
  administration, ...) and untagged records (older SPAs carry no topics), per state in the queue row's
  `index_families` and in the tables below.
- Scope: `document_class: policy` (the LIHEAP and CCDF state-plan precedent), versions `2026-09-13-medicaid-state-plan`
  and `2026-09-13-chip-state-plan`, `source_as_of` 2026-09-13, `expression_date` = the SPA's effective date (approval
  date if none; 2026-09-13 for index pages). Citation root `us-xx/policy/cms/` is new (no released or draft scope
  carries any `us-xx/policy/cms/...` path; the 2026-07-05 FCEP scope lives under jurisdiction `us`), so the scopes
  cannot collide with the eligibility-manual scopes of `docs/ingest-runs/2026-09-13-us-rulespec-followup-union.selector.json`.
- Extraction: `extract-official-documents`, no new adapter. Every document carries
  `request: browser_impersonation_direct: true` (curl_cffi chrome120; TLS verified; medicaid.gov is the publisher,
  no mirror or proxy). PDFs use the extractor's default page granularity with `ocr: true` (image-only pages fall back
  to Tesseract 5.5.3); the SPA packages are small (150-600 KB, mostly text-bearing).
- Queue: one `family: cms_state_plan` row per state appended after the state's eligibility-manual row in
  `manifests/medicaid-agent-queue.yaml` and `manifests/chip-agent-queue.yaml` (`source_kind:
  cms_posted_state_plan_amendments`, `index_document_count` = SPA records + index pages, `taken_count` = documents,
  `index_families` = per-topic found/taken). The Medicaid generator already carried extra per-jurisdiction rows
  through; the CHIP generator now does too.

## Results

Manifests: 51 `manifests/us-xx-medicaid-state-plan.yaml` and 51 `manifests/us-xx-chip-state-plan.yaml`; no
jurisdiction was blocked (medicaid.gov answered every listing and document request through impersonation).
Extraction seconds are wall seconds of the `extract-official-documents` command per scope (driver log), run while
another agent's extraction shared the corpus root.

**Progress checkpoint (partial, 37 of 102 scopes extracted at the time of this commit; the driver is still running in the background on the controller machine; rows with '-' seconds and MISSING coverage are not yet extracted; the note is rewritten when the run completes).**

### Medicaid per state

| Jurisdiction | SPA records on CMS index | Index pages | Eligibility-bearing records | Documents (PDFs) | Provisions | Coverage | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| us-ak | 164 | 2 | 29 | 37 (35) | 0 | MISSING | - |
| us-al | 187 | 2 | 25 | 35 (32) | 0 | MISSING | - |
| us-ar | 226 | 3 | 30 | 33 (27) | 0 | MISSING | - |
| us-az | 319 | 4 | 27 | 45 (41) | 0 | MISSING | - |
| us-ca | 575 | 6 | 60 | 82 (76) | 0 | MISSING | - |
| us-co | 545 | 6 | 30 | 46 (39) | 0 | MISSING | - |
| us-ct | 508 | 6 | 56 | 64 (57) | 0 | MISSING | - |
| us-dc | 207 | 3 | 24 | 27 (24) | 0 | MISSING | - |
| us-de | 160 | 2 | 33 | 49 (47) | 0 | MISSING | - |
| us-fl | 226 | 3 | 19 | 28 (25) | 0 | MISSING | - |
| us-ga | 194 | 2 | 27 | 31 (29) | 0 | MISSING | - |
| us-hi | 137 | 2 | 28 | 32 (30) | 0 | MISSING | - |
| us-ia | 329 | 4 | 38 | 55 (51) | 0 | MISSING | - |
| us-id | 206 | 3 | 33 | 37 (34) | 0 | MISSING | - |
| us-il | 312 | 4 | 33 | 37 (33) | 0 | MISSING | - |
| us-in | 235 | 3 | 32 | 45 (41) | 0 | MISSING | - |
| us-ks | 297 | 3 | 25 | 30 (27) | 0 | MISSING | - |
| us-ky | 191 | 2 | 25 | 27 (25) | 0 | MISSING | - |
| us-la | 561 | 6 | 43 | 51 (45) | 0 | MISSING | - |
| us-ma | 479 | 5 | 37 | 42 (36) | 0 | MISSING | - |
| us-md | 276 | 3 | 43 | 74 (71) | 0 | MISSING | - |
| us-me | 320 | 4 | 46 | 56 (51) | 0 | MISSING | - |
| us-mi | 383 | 4 | 48 | 52 (47) | 0 | MISSING | - |
| us-mn | 436 | 5 | 46 | 63 (56) | 0 | MISSING | - |
| us-mo | 276 | 3 | 31 | 38 (34) | 0 | MISSING | - |
| us-ms | 262 | 3 | 24 | 31 (27) | 0 | MISSING | - |
| us-mt | 485 | 5 | 39 | 71 (66) | 0 | MISSING | - |
| us-nc | 423 | 5 | 35 | 44 (39) | 0 | MISSING | - |
| us-nd | 363 | 4 | 31 | 37 (33) | 0 | MISSING | - |
| us-ne | 279 | 3 | 55 | 108 (105) | 0 | MISSING | - |
| us-nh | 363 | 4 | 44 | 48 (43) | 0 | MISSING | - |
| us-nj | 280 | 3 | 37 | 48 (45) | 0 | MISSING | - |
| us-nm | 181 | 2 | 26 | 28 (26) | 0 | MISSING | - |
| us-nv | 295 | 3 | 35 | 44 (40) | 0 | MISSING | - |
| us-ny | 855 | 9 | 46 | 55 (45) | 0 | MISSING | - |
| us-oh | 512 | 6 | 90 | 121 (113) | 0 | MISSING | - |
| us-ok | 338 | 4 | 35 | 39 (35) | 0 | MISSING | - |
| us-or | 287 | 3 | 20 | 25 (21) | 0 | MISSING | - |
| us-pa | 510 | 6 | 38 | 52 (46) | 0 | MISSING | - |
| us-ri | 212 | 3 | 33 | 38 (35) | 0 | MISSING | - |
| us-sc | 300 | 3 | 25 | 33 (30) | 0 | MISSING | - |
| us-sd | 176 | 2 | 25 | 27 (25) | 0 | MISSING | - |
| us-tn | 91 | 1 | 20 | 23 (22) | 0 | MISSING | - |
| us-tx | 646 | 7 | 26 | 35 (27) | 0 | MISSING | - |
| us-ut | 329 | 4 | 30 | 36 (32) | 0 | MISSING | - |
| us-va | 267 | 3 | 30 | 33 (30) | 0 | MISSING | - |
| us-vt | 215 | 3 | 37 | 40 (36) | 0 | MISSING | - |
| us-wa | 494 | 5 | 43 | 48 (42) | 0 | MISSING | - |
| us-wi | 303 | 4 | 53 | 67 (62) | 0 | MISSING | - |
| us-wv | 128 | 2 | 19 | 23 (21) | 0 | MISSING | - |
| us-wy | 146 | 2 | 22 | 24 (21) | 0 | MISSING | - |
| **total** | 16,489 | 189 | 1,786 | 2,294 (2,080) | 0 | 0/0 complete | 0 |

Verification (medicaid): 0 scopes on disk, 0 coverage-complete, 0 document roots, 0 page provisions, 0 empty non-root bodies, 0 duplicate citation paths, 0 rows without expression_date.


### Chip per state

| Jurisdiction | SPA records on CMS index | Index pages | Eligibility-bearing records | Documents (PDFs) | Provisions | Coverage | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| us-ak | 5 | 1 | 5 | 8 (7) | 124 | complete | 12 |
| us-al | 33 | 1 | 23 | 28 (27) | 1,238 | complete | 25 |
| us-ar | 21 | 1 | 15 | 17 (16) | 871 | complete | 29 |
| us-az | 22 | 1 | 16 | 19 (18) | 429 | complete | 92 |
| us-ca | 20 | 1 | 15 | 19 (18) | 832 | complete | 9 |
| us-co | 33 | 1 | 20 | 23 (22) | 427 | complete | 70 |
| us-ct | 17 | 1 | 13 | 16 (15) | 579 | complete | 65 |
| us-dc | 3 | 1 | 3 | 5 (4) | 61 | complete | 11 |
| us-de | 21 | 1 | 20 | 24 (23) | 636 | complete | 53 |
| us-fl | 18 | 1 | 13 | 18 (17) | 818 | complete | 44 |
| us-ga | 29 | 1 | 21 | 26 (25) | 851 | complete | 117 |
| us-hi | 8 | 1 | 7 | 9 (8) | 150 | complete | 16 |
| us-ia | 29 | 1 | 22 | 27 (26) | 1,196 | complete | 71 |
| us-id | 24 | 1 | 19 | 23 (22) | 1,288 | complete | 42 |
| us-il | 18 | 1 | 13 | 15 (14) | 873 | complete | 41 |
| us-in | 24 | 1 | 19 | 22 (21) | 1,052 | complete | 41 |
| us-ks | 30 | 1 | 24 | 26 (25) | 526 | complete | 69 |
| us-ky | 22 | 1 | 17 | 22 (21) | 1,101 | complete | 62 |
| us-la | 27 | 1 | 21 | 22 (21) | 411 | complete | 39 |
| us-ma | 23 | 1 | 18 | 20 (19) | 457 | complete | 89 |
| us-md | 11 | 1 | 9 | 11 (10) | 541 | complete | 12 |
| us-me | 20 | 1 | 17 | 20 (19) | 815 | complete | 52 |
| us-mi | 22 | 1 | 14 | 17 (16) | 488 | complete | 31 |
| us-mn | 16 | 1 | 15 | 17 (16) | 331 | complete | 54 |
| us-mo | 22 | 1 | 18 | 20 (19) | 774 | complete | 39 |
| us-ms | 19 | 1 | 16 | 19 (18) | 417 | complete | 57 |
| us-mt | 21 | 1 | 18 | 21 (20) | 590 | complete | 68 |
| us-nc | 21 | 1 | 14 | 16 (15) | 979 | complete | 70 |
| us-nd | 11 | 1 | 8 | 11 (10) | 324 | complete | 10 |
| us-ne | 20 | 1 | 15 | 18 (17) | 836 | complete | 34 |
| us-nh | 6 | 1 | 6 | 9 (8) | 231 | complete | 9 |
| us-nj | 24 | 1 | 18 | 22 (21) | 784 | complete | 309 |
| us-nm | 4 | 1 | 4 | 6 (5) | 179 | complete | 9 |
| us-nv | 22 | 1 | 19 | 22 (21) | 504 | complete | 66 |
| us-ny | 34 | 1 | 28 | 36 (35) | 1,245 | complete | 118 |
| us-oh | 8 | 1 | 7 | 9 (8) | 414 | complete | 9 |
| us-ok | 18 | 1 | 14 | 15 (14) | 484 | complete | 48 |
| us-or | 28 | 1 | 22 | 30 (29) | 0 | MISSING | - |
| us-pa | 21 | 1 | 13 | 15 (14) | 0 | MISSING | - |
| us-ri | 20 | 1 | 16 | 19 (18) | 0 | MISSING | - |
| us-sc | 5 | 1 | 5 | 8 (7) | 0 | MISSING | - |
| us-sd | 18 | 1 | 18 | 20 (19) | 0 | MISSING | - |
| us-tn | 24 | 1 | 17 | 19 (18) | 0 | MISSING | - |
| us-tx | 23 | 1 | 18 | 21 (20) | 0 | MISSING | - |
| us-ut | 30 | 1 | 21 | 23 (22) | 0 | MISSING | - |
| us-va | 28 | 1 | 21 | 23 (22) | 0 | MISSING | - |
| us-vt | 8 | 1 | 8 | 13 (12) | 0 | MISSING | - |
| us-wa | 19 | 1 | 16 | 20 (19) | 0 | MISSING | - |
| us-wi | 24 | 1 | 16 | 17 (16) | 0 | MISSING | - |
| us-wv | 21 | 1 | 17 | 19 (18) | 0 | MISSING | - |
| us-wy | 11 | 1 | 7 | 10 (9) | 0 | MISSING | - |
| **total** | 1,006 | 51 | 779 | 935 (884) | 23,856 | 37/37 complete | 1,992 |

Verification (chip): 37 scopes on disk, 37 coverage-complete, 678 document roots, 23,141 page provisions, 0 empty non-root bodies, 0 duplicate citation paths, 0 rows without expression_date.


### Medicaid SPA topics across the 51 indexes (records found / records taken)

| Topic | Found | Taken |
| --- | ---: | ---: |
| Financing & Reimbursement | 5,527 | 160 |
| Program Administration | 3,742 | 351 |
| Reimbursement | 2,595 | 40 |
| Benefits | 1,672 | 250 |
| (untagged) | 1,609 | 0 |
| Eligibility | 1,239 | 1,239 |
| Coverage | 826 | 129 |
| Disaster Relief | 648 | 118 |
| Prescription Drugs | 541 | 51 |
| Current State Plan | 248 | 248 |
| Medicaid and CHIP Program (MACPro) | 248 | 141 |
| Coverage and Reimbursement | 244 | 4 |
| Cost Sharing | 197 | 197 |
| Dental | 195 | 9 |
| spa_index_page | 189 | 189 |
| Health Homes | 143 | 6 |
| Home and Community Based Services | 128 | 12 |
| Alternative Benefit Plan | 121 | 6 |
| Managed Care | 114 | 9 |
| Premiums | 92 | 92 |
| Other Licensed Practitioners | 91 | 6 |
| Prescribed Drugs | 81 | 1 |
| Targeted Case Management | 79 | 25 |
| Third Party Liability | 63 | 63 |
| Preventative Services | 54 | 4 |
| Tribal Issues | 51 | 2 |
| ABP | 46 | 0 |
| Health Services Initiatives | 42 | 7 |
| Prior Authorization | 33 | 4 |
| Value Based Purchasing | 31 | 0 |
| Transportation | 29 | 1 |
| Home Health | 29 | 1 |
| Clinic | 27 | 0 |
| Covered Outpatient Drug | 27 | 0 |
| Preventive Services | 26 | 4 |
| Vaccine | 20 | 0 |
| Drugs and Related Services | 20 | 1 |
| Physician Administered Drugs | 18 | 0 |
| Tribal/Indian Health Services | 17 | 1 |
| Drug Shortages | 14 | 0 |
| Long-Term Services & Support | 14 | 2 |
| Inpatient | 12 | 2 |
| Professional Dispensing Fee | 11 | 0 |
| Outreach & Enrollment | 11 | 11 |
| Federal Financial Participation | 10 | 1 |
| Preferred Drug Lists | 10 | 1 |
| Medical Supplies & Devices | 10 | 0 |
| Program Integrity | 9 | 1 |
| Indian Health Services | 9 | 0 |
| Individual CoPayments or Insurance Payments | 9 | 9 |
| Medicaid Expansion | 9 | 9 |
| Excluded Drug Coverage | 8 | 0 |
| Supplemental Rebate Agreement | 8 | 0 |
| Weight Loss Drugs | 7 | 0 |
| Coverage/MAT | 7 | 0 |
| Medicaid-Medicare Issues | 7 | 4 |
| Rebate/Reimbursement Updates | 7 | 0 |
| Adjustment Codes | 6 | 0 |
| Allocation Methodologies | 6 | 1 |
| Supplemental Rebates and Managed Care | 6 | 0 |
| Quality of Care | 5 | 0 |
| State Plan Factsheet | 5 | 5 |
| Grants | 5 | 0 |
| Delivery System | 5 | 0 |
| Drugs Purchased | 4 | 0 |
| Vaccine - Policy Clarification | 4 | 1 |
| Obesity Drugs | 4 | 0 |
| Over-the-Counter Drugs | 4 | 0 |
| Federal Financial Match | 4 | 1 |
| Drug Utilization Review (DUR) | 4 | 0 |
| 340B Program | 4 | 0 |
| Prescription Limitations | 3 | 0 |
| Substance Use Disorders | 3 | 1 |
| Children's Health Insurance Program | 3 | 3 |
| 21st Century Cures Act | 3 | 0 |
| Additional Rebate | 2 | 0 |
| Long-Acting Reversible Contraception (LARC) | 2 | 0 |
| Non-prescription Drugs | 2 | 0 |
| Affordable Care Act | 2 | 2 |
| Contraceptive Drugs | 2 | 0 |
| Federal Upper Limit | 2 | 0 |
| Vaccine - Reimbursement | 2 | 0 |
| Active Pharmaceutical Ingredient & Excipient Removal | 1 | 0 |
| Eligible for FFP | 1 | 0 |
| New Labeler Codes | 1 | 0 |
| Prescription Drug Monitoring Program | 1 | 0 |
| Fertility Drugs | 1 | 0 |
| Average Sales Price (ASP) | 1 | 0 |
| Additional Rebate Calculation Revision | 1 | 0 |
| All Drugs Used for Smoking Cessation | 1 | 1 |
| Drug Rebate Reporting | 1 | 0 |
| Data Definition Update | 1 | 0 |
| National Average Drug Acquisition Cost (NADAC) | 1 | 0 |
| Data & Systems | 1 | 1 |
| Pharmacy Benefit Managers (PBMs) | 1 | 0 |
| Adjustments that Cause Rebate Corrections | 1 | 0 |
| State Drug Utilization Data | 1 | 0 |
| Veteran Homes | 1 | 0 |
| Tribal/Indian Health Issues | 1 | 0 |
| State Plan Amendment Requirement | 1 | 0 |
| Inpatient Drug Prices for Public Hospitals | 1 | 0 |
| Best Price  - Calculation Methodology Revision | 1 | 0 |
| Blood Clotting Drugs | 1 | 0 |
| Branded Prescription Drug Fees | 1 | 0 |
| Institution for Mental Disease | 1 | 1 |
| Hemophilia Disease Management | 1 | 0 |

### Chip SPA topics across the 51 indexes (records found / records taken)

| Topic | Found | Taken |
| --- | ---: | ---: |
| Benefits | 328 | 328 |
| Eligibility | 293 | 293 |
| Program Administration | 168 | 89 |
| Financing & Reimbursement | 104 | 49 |
| Current State Plan | 88 | 88 |
| Health Services Initiatives | 72 | 47 |
| Disaster Relief | 64 | 15 |
| spa_index_page | 51 | 51 |
| State Plan Factsheet | 47 | 47 |
| Cost Sharing | 46 | 46 |
| Expansion | 31 | 31 |
| (untagged) | 18 | 0 |
| Managed Care | 15 | 1 |
| Delivery System | 14 | 5 |
| Dental | 13 | 13 |
| Premiums | 9 | 9 |
| Medicaid and CHIP Program (MACPro) | 7 | 7 |
| Children's Health Insurance Program | 6 | 4 |
| Grants | 5 | 0 |
| Outreach & Enrollment | 5 | 5 |
| Tribal Issues | 2 | 1 |
| Prescription Drugs | 2 | 1 |
| MCHIP Program | 2 | 2 |
| Behavioral Health Services | 1 | 0 |
| Maternal Health | 1 | 1 |
| Disaster Relief Activation | 1 | 1 |
| Enrollment | 1 | 1 |


### Publisher access record

- medicaid.gov, plain client (curl, Chrome or Axiom User-Agent, TLS 1.3): HTTP 403 "Access Denied" (Akamai), 408-449
  bytes, 0.1-0.3 s, for every path including `/`.
- medicaid.gov, curl_cffi `chrome120` (also `chrome131`, `safari17_0`, `firefox133`): HTTP 200 for every listing and
  PDF; 0.1-1.3 s per listing page, 0.1-0.3 s per PDF. This is the manifest option `browser_impersonation_direct`,
  the same publisher access the released `us/form/2026-05-12-cms-medicaid-chip-bhp-eligibility-levels` and
  `us/policy/2026-07-05-cms-chip-fcep-spa` scopes used. No block was worked around and nothing was fetched from a
  mirror.

## Closure elements

Element ids from `medicaid-schema.yaml` / `chip-schema.yaml` whose `plan_family` names medicaid.gov, and what these
scopes do for them (cell counts are the pass-2 matrix's EXTRACTABLE + REVIEW cells for the 50 states + DC; the
OUTREACH cells of AL, CA, NE (Medicaid) and CA, DC, FL, MT, WY (CHIP) are also served by these scopes because
medicaid.gov is not the blocked publisher):

| Family (schema `plan_family`) | Element ids | Cells not PRESENT | What the CMS scopes carry |
| --- | --- | ---: | --- |
| SPA on record / approved plan / SPA process (Medicaid) | M-SS-STATE-PLAN, M-SS-SPA, M-435-10, M-435-814, M-435-843 | 255 (51 each) | **Closed** for all 51: the SPA index pages list every approved SPA; the approval packages are the approved plan pages. |
| CHIP state plan as a document | C-SS-STATE-PLAN, C-457-50, C-457-305, C-457-60 | 153 + 31 | **Closed** for all 51 (index + compiled Current State Plan for 47 states; the 4 without a compiled record have their packages). |
| Attachment 2.2-A groups covered | M-ST-1396a-m, M-ST-1396b-v, M-ST-1396r-6, M-ST-1396a-a10Aii-buyin, M-435-4, .112-.139, .145, .150, .170, .172, .210-.236, .301-.330, .406, .926 (57) | 1,183 EXTRACTABLE + 348 REVIEW (+157 OUTREACH) | Partial: the Eligibility / Current State Plan / Medicaid Expansion / ACA packages carry the 2.2-A and S-series pages amended since 2009 (every MAGI group, expansion, most optional-group elections); legacy protected groups never re-approved are not on medicaid.gov. |
| Sections 2.1-2.5 | M-ST-1396a-a34, M-435-403, .407, .520, .530, .531, .540, .541, .907, .910, .915, .916 | 37 + 128 REVIEW | Partial (residency, retroactive eligibility and SSN pages appear in Eligibility SPAs; age/blindness/disability definitions rarely re-approved). |
| 2.6-A and supplements (financial standards) | M-ST-1396a-a17, M-435-110, .116, .118, .601, .602, .603, .622, .631, M-SS-RESOURCE-TABLE | 128 + 2 | Partial (MAGI standards S-series pages and 1902(r)(2) supplements approved since 2014; older resource standards not). |
| 2.6-A supplement (medically needy levels) | M-435-811, .831, .832, .840, .845 | 116 + 42 | Partial (MNIL SPAs when re-approved). |
| 2.6-A supplements 8-12 (post-eligibility, transfers, trusts, estate recovery, spousal) | (9 ids, 435.7xx/8xx) | 136 + 4 | Partial. |
| 4.18 premiums and cost sharing | M-447-52 to M-447-57 | 125 + 6 | Largely closed where a state charges cost sharing: every Cost Sharing / Premiums / Individual CoPayments package is taken. |
| 4.2 fair hearings, 4.22 TPL, 3.1-A benefits | M-ST-1396a-a3, M-SS-HEARINGS, M-ST-1396a-a25, M-435-610, M-SS-BENEFITS | 5 + 5 + 48 REVIEW | TPL packages taken (Third Party Liability topic); hearings and benefits packages not taken (topics outside the set; inventoried). |
| Presumptive eligibility (S-series) | M-435-1102, .1103, .1110, C-435-1102 | 9 + 27 REVIEW + 17 | Closed where the state filed a PE SPA (Eligibility topic). |
| MAGI verification plan | M-435-920, .945, .948, .949, .952, .956 | 33 + 33 REVIEW | **Not taken**: CMS posts verification plans on `/medicaid/eligibility-policy/medicaid/chip-eligibility-verification-plans`, a separate page not in this run. |
| CHIP sections 4.1-4.4, 4-5, 4.4, 6, 8, 9 | C-ST-1397jj-b, C-ST-1397ll, C-ST-FCEP, C-457-70, .80, .90, .110, .125, .310, .315, .320-a, .320-b, .330, .340, .342, .343, .348, .350, .355, .360, .380, .410, .505-.570, .805, .810, .960, .1005, .1010, .1110, .1120, C-SS-DISQUALIFYING-COVERAGE (39) | 726 + 229 REVIEW (+142 OUTREACH) | Closed for 47 states by the compiled Current State Plan (all sections as of 2010-11) plus every later Eligibility / Cost Sharing / Benefits / Enrollment / Expansion package; the 4 states without a compiled record (AK, DC, NH, NM by record count) rely on packages alone. |
| CHIP: Medicaid 2.2-A / 2.6-A elements | C-435-229, .926, .117, .118, .603 | 17 + 13 REVIEW | As for Medicaid above (M-CHIP pages travel in Medicaid SPAs). |

Estimate: of the 2,563 Medicaid and about 1,180 CHIP cells the closure check attributed to this family, these scopes
settle the 255 + 184 state-plan/SPA-record cells outright and carry the approved text for the CHIP section cells
(about 950 including REVIEW) and for the Medicaid cells whose pages have been amended since 2009. A re-run of the
closure matrix builders over these scopes is the only honest count; a reviewer should expect the Medicaid 2.2-A
row to move from EXTRACTABLE to PRESENT for the MAGI, expansion and optional-group elections and to stay open for
the legacy protected groups.

## Still missing and decisions

1. **The compiled Medicaid state plan is not on medicaid.gov.** Plan pages never amended since ~2009 exist only in
   the state's own posted plan (state Medicaid agency sites). That is a new state-publisher family
   (`<state> Medicaid state plan (compiled)`), 51 publishers, three of which block (AL, CA, NE). Decision needed:
   queue it as its own work order, or accept the SPA-package coverage as the CMS layer.
2. **MAGI-based verification plans** (6 elements, 66 cells): CMS posts them at
   `/medicaid/eligibility-policy/medicaid/chip-eligibility-verification-plans`; not in this run (separate index);
   cheap follow-on with the same generator pattern.
3. **Untagged and other-topic SPAs** (about 14,700 Medicaid and 230 CHIP records) are inventoried, not taken. The untagged ones are the
   oldest records (pre-2010, often CMS-179 forms only); benefits (3.1-A), hearings and reimbursement topics were left
   out by design. Taking every SPA package for the 51 jurisdictions would be about 16,500 more PDFs.
4. **Overlap with the released FCEP scope**: the 20 states' FCEP SPAs in `us/policy/2026-07-05-cms-chip-fcep-spa`
   are also in the CHIP scopes here under different citation paths (`us-xx/policy/cms/chip-state-plan/spa/...` vs
   `us/policy/cms/chip-spa/...`); no citation-path collision, same bytes. Deep validation does not flag content
   duplicates; a later consolidation may retire the `us` copies.
5. **Index page granularity**: each index page is one block (the record headings are `<button>`s the extractor
   drops). Per-record summary pages (`?filter[nid][eq]=<nid>`, the FCEP precedent) were not taken to keep the
   document count at 3,229 rather than doubling it; the record fields are also in each PDF document's metadata
   (`transmittal_number`, `cms_node_id`, `cms_record_url`, `approval_date`, `effective_date`, `summary`, `topics`).
6. **Expression dates** are the SPA effective dates as CMS lists them; the compiled CHIP plans carry their 2003-2010
   effective dates. The `complete-expression-dates-v1` profile only requires the field to be present.
7. medicaid.gov's 403-to-plain-clients behavior is publisher-side bot protection that the repo already handles with
   `browser_impersonation_direct`; it is not a block on this network.

## Verification

- Coverage `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths for every extracted scope; duplicate-
  freedom re-checked directly on each provisions JSONL; every non-root provision has a non-empty body (counts in the
  tables above); every row carries `expression_date`.
- Draft selector `docs/ingest-runs/2026-09-13-cms-state-plans.selector.json` = the follow-up draft
  (`us-rulespec-2026-09-13-followup-union`, 556 scopes) + the 102 CMS state-plan scopes = 658 scopes.
  `uv run axiom-corpus-ingest validate-release --base /Users/pavelmakarchuk/axiom-corpus/data/corpus --release
  docs/ingest-runs/2026-09-13-cms-state-plans.selector.json --ignore-r2-missing --max-issues 50`:
  not yet run on the full draft; a partial draft (follow-up + the first 28 CHIP scopes) validated ok: true, 0 errors, 546 pre-existing missing_parent_id warnings.
- Disk: 21 GB free at start, 4.6-8 GB during the run (other agents extract into the same corpus root); the driver stops itself below 4 GB.
- `uv run ruff check scripts`: passes. Focused tests in the sparse worktree
  (`uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`): 286 passed,
  2 skipped, 12 failed; all 12 open other scopes' `data/corpus` artifacts the sparse worktree does not check out
  (FileNotFoundError): `test_armenia_arlis`, `test_be_rulespec_2026_08_23_promotion`,
  `test_build_ny_tanf_compatibility_scope` x2, `test_israel_openlaw`, `test_rulespec_be_source_promotion`,
  `test_us_{ak,ct,mi,mt,nd,ny}_snap_manual(s)`. The same selection passes in a full checkout (see the
  2026-09-11 consolidation note).

## Controller section: selector additions

Add to the successor selector (all `document_class: policy`):

- `us-xx/policy/2026-09-13-medicaid-state-plan` for xx in the 50 states + dc (51 scopes);
- `us-xx/policy/2026-09-13-chip-state-plan` for xx in the 50 states + dc (51 scopes).

The draft selector above already contains them. Artifacts (unsigned, uncommitted, main checkout):

- `data/corpus/sources/us-xx/policy/2026-09-13-{medicaid,chip}-state-plan/official-documents/*`
- `data/corpus/inventory/us-xx/policy/2026-09-13-{medicaid,chip}-state-plan.json`
- `data/corpus/provisions/us-xx/policy/2026-09-13-{medicaid,chip}-state-plan.jsonl`
- `data/corpus/coverage/us-xx/policy/2026-09-13-{medicaid,chip}-state-plan.json`

Rebuild:

```bash
uv run python scripts/build_cms_state_plan_manifests.py --program all   # live listings; --cache DIR to reuse
for p in medicaid chip; do for m in manifests/us-*-$p-state-plan.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-13-$p-state-plan --manifest $m --source-as-of 2026-09-13
done; done
```

Inventory of every state's index (records, pages, per-topic found/taken, the taken records with node ids, dates,
topics and links): `docs/ingest-runs/2026-09-13-cms-state-plans-inventory.json`.
