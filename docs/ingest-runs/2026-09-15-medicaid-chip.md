# Wave 5 — Medicaid and CHIP closure: MAGI verification plans (51 states), 1115 STCs (7 states), the Wyoming EOM, and the REVIEW reading pass

Date: 2026-09-15 (UTC; the evening of 2026-09-14 on the controller's machine).
Work order: `docs/coverage/needs-closure-2026-09-14/wave5/00-common-preamble.md` and `.../wave5/medicaid-chip-brief.md`
(branch `analysis/needs-closure-2026-09-14`, worktree `closure-r6`): 181 EXTRACTABLE cells
(`wave5/medicaid-chip-extractable.csv`), 2,731 REVIEW cells (`wave5/medicaid-chip-review.csv`, 765 of them with no cited
provision), schemas `medicaid-schema.yaml` (302 elements) and `chip-schema.yaml`.
Branch `discovery/ingest-w5-medicaid-chip` cut from `main` 9b0641afc in the sparse worktree
`~/axiom-corpus-worktrees/w5-medicaid-chip` (`data/corpus/` excluded, never symlinked); every extraction wrote to the main
checkout's corpus root (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`), artifacts uncommitted. Timing: started
2026-09-14T23:59Z (19:59 EDT), reading pass, probes and generators to 00:20Z, extractions 00:20Z-00:24Z, decisions file
and this note to about 00:45Z; about 50 minutes of agent time, well inside the four-hour box. Disk: `df -h /` 26 GB free
at the start, 28 GB at the end (the three new families hold 156 MB of source files under `data/corpus/sources`; the stop
line of 5 GB was never approached; checked before each extraction loop and by the loops themselves).
Impact analysis: not run (the GitNexus MCP tools are not available in this session). No library function under `src/` was
modified; the code changes are two new generator scripts and one batch added to an existing generator (below).

Outputs: this note; `docs/ingest-runs/2026-09-15-medicaid-chip-decisions.csv` (513 rows); 59 new manifests; the
Medicaid agent queue; three generators. Nothing under `data/corpus/` is committed.

## Summary

| Family | Version | Scopes | Provision rows | Chars | Cells |
| --- | --- | ---: | ---: | ---: | --- |
| CMS-posted MAGI verification plans | `us-xx/policy/2026-09-15-medicaid-magi-verification-plan` | 51 | 827 | 1,231,637 | 69 non-PRESENT cells of 435.920/.945/.948/.949/.952 -> PRESENT (13 EXTRACTABLE 949, 7 EXTRACTABLE 952, 2+2 EXTRACTABLE 920/948, 36 REVIEW 949/952, 8 OUTREACH AL/CA, 1 945) |
| CMS 1115 approval documents (STCs) | `us-xx/policy/2026-09-15-medicaid-1115-stc` | 7 (10 documents) | 620 | 1,553,999 | M-ST-1315: 7 EXTRACTABLE -> PRESENT (KY MT PA SD VA WI WY); 6 -> ABSENT with the reason (AK ID ND NE NV SC) |
| Wyoming Eligibility Online Manual | `us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure` | 1 (121 documents) | 458 | 362,513 | 53 WY EXTRACTABLE cells: 17 PRESENT, 5 REVIEW, 30 ABSENT (manual held, no hit), 1 OUTREACH (image-only tables) |
| Held-text check of the 435.904/.908/.918/.912/.1200 cells | existing scopes | - | - | - | 34 ALREADY-HELD (check-pattern misses), 82 ABSENT with the carrying page named |
| Reading pass (Part B) | existing scopes | - | - | - | 246 cells read across 41 elements: 83 PRESENT, 163 ABSENT-IN-CITED; 3 elements PATTERN-CONFIRMED, 18 ABSENT-IN-CITED, 20 mixed (stay REVIEW) |
| Income and premium tables | - | - | - | - | 16 cells not attempted (WY's Table 1 is in the EOM scope: PRESENT) |

Every new scope reports coverage `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths.

## Publisher access (2026-09-15T00:03Z to 00:24Z, plain extractor client, TLS verified, no impersonation, no mirror)

- `www.medicaid.gov`: every request answered HTTP 200 to the plain client (corpus user agent) - the 1115 landing page,
  the demonstration list `/medicaid/section-1115-demo/demonstration-and-waiver-list` (state and status filters,
  `limit=100`), 30 demonstration pages, the verification-plan index
  `/medicaid/eligibility-policy/medicaid/chip-eligibility-verification-plans` (152,470 bytes) and 61 PDFs
  (`/sites/default/files/2019-12/...`, `/medicaid/eligibility/downloads/...`, `/medicaid/section-1115-demonstrations/downloads/...`).
  The 2026-09-13 state-plan run met an Akamai 403 for plain clients and used `browser_impersonation_direct`; tonight the
  plain client was not challenged once, so the new manifests carry no `request` block (the 09-13 manifests are not
  changed). The old `state-waivers-list` URLs the queue lead list carries answer 404 (30,487-byte error page); the live
  list is the `section-1115-demo` path above.
- `ecom.wyo.gov` (Wyoming WDH Eligibility Online Manual, Google Sites): index HTTP 200 (218,666 bytes), every one of the
  107 M-series pages and 17 Tables HTTP 200 (fetched once each by the generator, 22 s for the 124 probes, then again by the
  extractor, 16 s). The batch-5 finding that the generic HTML path reduces each page to the site title is a selector
  problem, not a publisher problem: `[role='main']` holds the site title only; the page's content column is
  `div.UtePc` (site title, page title, the POL/Reference/Clarifying/Worker-Responsibilities sections), 2,900-3,700
  characters per policy page. Three Tables (`/tables/table7`, `/tables/table2a`, `/tables/table5b`) render the table as
  an image inside that column with no text: inventoried as `eligibility_table_image_only`, not taken, OUTREACH (a text
  or spreadsheet export from WDH). Fourteen Tables are text (Table 1 FPL Standards effective 2026-04-01, Table 1A ABD
  income standards, ...).
- No other publisher was contacted. The 16 income/premium-table cells (HI ID KS MN OH for Medicaid; AK AZ FL HI ME MN
  NH NM OH RI SC for CHIP) were not attempted: each needs its own publisher research and the reading pass was the
  priority; their queue notes still name the located index.
- No TLS chain was broken; nothing added to `data/certs/`; `REQUESTS_CA_BUNDLE` pointed at certifi only.

## Part A1 - MAGI-based verification plans (new family, 51 scopes)

Method. 42 CFR 435.945(j) makes every state file its MAGI-based verification plan with CMS, and CMS posts the plans on
one index page, one "State Eligibility Verification Plan" PDF per state (2019-12 uploads for 39 states, later re-postings
for CA IL LA ME MS MO NH NJ NY TN VT WI, VA 2023-12), plus COVID-era "Disaster Addendum" PDFs (17 states) and unwinding
"Mitigation Plan" PDFs (MO TN VT). The plan is the closure schema's own `plan_family` for 435.920, .945, .948, .949 and
.952 (SSN verification, the verification plan, electronic data sources, hub verification, reasonable compatibility): a
one-document family that clears those elements for every state at once. New generator
`scripts/build_medicaid_magi_verification_plan_manifests.py` reads the live index, takes the verification plan only
(addenda and mitigation plans inventoried in `index_families`, not taken - temporary flexibilities, not the standing
plan), writes `manifests/us-xx-medicaid-magi-verification-plan.yaml` (document class `policy`, citation path
`us-xx/policy/cms/magi-verification-plan/<file stem>`, page-level rows, `ocr: true` as a fallback for scanned forms) and
one `family: magi_verification_plan` queue row per state after the state's last row. All 51 jurisdictions post a plan;
none is missing.

Extraction (`extract-official-documents --version 2026-09-15-medicaid-magi-verification-plan --source-as-of 2026-09-15`,
one manifest per state, 1-6 s each, 51 scopes in about 90 s):

| Jurisdiction | Version | Documents | Rows | Chars | Seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| us-ak | 2026-09-15-medicaid-magi-verification-plan | 1 | 16 | 22,245 | 1 |
| us-al | 2026-09-15-medicaid-magi-verification-plan | 1 | 11 | 18,100 | 1 |
| us-ar | 2026-09-15-medicaid-magi-verification-plan | 1 | 15 | 20,202 | 1 |
| us-az | 2026-09-15-medicaid-magi-verification-plan | 1 | 43 | 57,914 | 1 |
| us-ca | 2026-09-15-medicaid-magi-verification-plan | 1 | 13 | 29,913 | 1 |
| us-co | 2026-09-15-medicaid-magi-verification-plan | 1 | 13 | 23,132 | 1 |
| us-ct | 2026-09-15-medicaid-magi-verification-plan | 1 | 16 | 24,012 | 1 |
| us-dc | 2026-09-15-medicaid-magi-verification-plan | 1 | 15 | 27,913 | 1 |
| us-de | 2026-09-15-medicaid-magi-verification-plan | 1 | 16 | 23,118 | 1 |
| us-fl | 2026-09-15-medicaid-magi-verification-plan | 1 | 15 | 20,508 | 1 |
| us-ga | 2026-09-15-medicaid-magi-verification-plan | 1 | 21 | 25,860 | 1 |
| us-hi | 2026-09-15-medicaid-magi-verification-plan | 1 | 15 | 21,305 | 1 |
| us-ia | 2026-09-15-medicaid-magi-verification-plan | 1 | 14 | 24,408 | 1 |
| us-id | 2026-09-15-medicaid-magi-verification-plan | 1 | 16 | 19,264 | 1 |
| us-il | 2026-09-15-medicaid-magi-verification-plan | 1 | 24 | 28,601 | 1 |
| us-in | 2026-09-15-medicaid-magi-verification-plan | 1 | 16 | 22,450 | 1 |
| us-ks | 2026-09-15-medicaid-magi-verification-plan | 1 | 17 | 28,931 | 1 |
| us-ky | 2026-09-15-medicaid-magi-verification-plan | 1 | 19 | 21,290 | 1 |
| us-la | 2026-09-15-medicaid-magi-verification-plan | 1 | 17 | 25,190 | 1 |
| us-ma | 2026-09-15-medicaid-magi-verification-plan | 1 | 17 | 29,620 | 1 |
| us-md | 2026-09-15-medicaid-magi-verification-plan | 1 | 16 | 27,561 | 1 |
| us-me | 2026-09-15-medicaid-magi-verification-plan | 1 | 23 | 26,692 | 1 |
| us-mi | 2026-09-15-medicaid-magi-verification-plan | 1 | 14 | 23,924 | 1 |
| us-mn | 2026-09-15-medicaid-magi-verification-plan | 1 | 12 | 17,533 | 1 |
| us-mo | 2026-09-15-medicaid-magi-verification-plan | 1 | 15 | 24,419 | 1 |
| us-ms | 2026-09-15-medicaid-magi-verification-plan | 1 | 15 | 23,801 | 1 |
| us-mt | 2026-09-15-medicaid-magi-verification-plan | 1 | 16 | 22,809 | 1 |
| us-nc | 2026-09-15-medicaid-magi-verification-plan | 1 | 17 | 21,074 | 1 |
| us-nd | 2026-09-15-medicaid-magi-verification-plan | 1 | 14 | 19,259 | 1 |
| us-ne | 2026-09-15-medicaid-magi-verification-plan | 1 | 15 | 24,355 | 1 |
| us-nh | 2026-09-15-medicaid-magi-verification-plan | 1 | 17 | 20,101 | 1 |
| us-nj | 2026-09-15-medicaid-magi-verification-plan | 1 | 15 | 17,920 | 1 |
| us-nm | 2026-09-15-medicaid-magi-verification-plan | 1 | 15 | 19,298 | 1 |
| us-nv | 2026-09-15-medicaid-magi-verification-plan | 1 | 15 | 22,892 | 1 |
| us-ny | 2026-09-15-medicaid-magi-verification-plan | 1 | 14 | 22,900 | 1 |
| us-oh | 2026-09-15-medicaid-magi-verification-plan | 1 | 13 | 22,115 | 1 |
| us-ok | 2026-09-15-medicaid-magi-verification-plan | 1 | 13 | 21,911 | 1 |
| us-or | 2026-09-15-medicaid-magi-verification-plan | 1 | 17 | 27,441 | 1 |
| us-pa | 2026-09-15-medicaid-magi-verification-plan | 1 | 19 | 28,334 | 1 |
| us-ri | 2026-09-15-medicaid-magi-verification-plan | 1 | 13 | 18,012 | 1 |
| us-sc | 2026-09-15-medicaid-magi-verification-plan | 1 | 17 | 22,034 | 1 |
| us-sd | 2026-09-15-medicaid-magi-verification-plan | 1 | 18 | 28,792 | 1 |
| us-tn | 2026-09-15-medicaid-magi-verification-plan | 1 | 14 | 18,999 | 1 |
| us-tx | 2026-09-15-medicaid-magi-verification-plan | 1 | 12 | 23,197 | 0 |
| us-ut | 2026-09-15-medicaid-magi-verification-plan | 1 | 20 | 29,919 | 1 |
| us-va | 2026-09-15-medicaid-magi-verification-plan | 1 | 13 | 17,948 | 1 |
| us-vt | 2026-09-15-medicaid-magi-verification-plan | 1 | 14 | 19,391 | 1 |
| us-wa | 2026-09-15-medicaid-magi-verification-plan | 1 | 11 | 19,081 | 1 |
| us-wi | 2026-09-15-medicaid-magi-verification-plan | 1 | 17 | 32,987 | 1 |
| us-wv | 2026-09-15-medicaid-magi-verification-plan | 1 | 18 | 26,750 | 1 |
| us-wy | 2026-09-15-medicaid-magi-verification-plan | 1 | 16 | 26,212 | 1 |

Cells. `M-435-949` (hub verification) was EXTRACTABLE in 13 states and REVIEW in 36: the plan text hits the element pattern
in all 51 (PRESENT), including AL and CA whose manuals are blocked (OUTREACH -> PRESENT). `M-435-952` (reasonable
compatibility): 7 EXTRACTABLE + 2 REVIEW -> PRESENT. `M-435-920` 4 and `M-435-948` 2 -> PRESENT, `M-435-945` 3. The
remaining cells of those elements were already PRESENT from the manuals and are not re-recorded.

## Part A2 - 1115 special terms and conditions (new family, 7 scopes)

Method. The live demonstration list, filtered per state and `Approved`, was read for the thirteen M-ST-1315 target states
(AK ID KY MT ND NE NV PA SC SD VA WI WY: 7-20 listings each, mostly 1915(c) waivers listed alongside). For each
eligibility-bearing approved demonstration the demonstration page's newest "Demonstration Approval" (or an "Amendment
Approval" that re-issues the STCs) was chosen; SUD/SMI, reentry, CCBHC and payment demonstrations are service authority
and are not taken. New generator `scripts/build_medicaid_1115_stc_manifests.py` holds that selection as a table (node id,
title, file name, approval date, what it carries), re-reads every demonstration page at build time and fails if a chosen
link is no longer listed, and writes `manifests/us-xx-medicaid-1115-stc.yaml` (class `policy`, citation path
`us-xx/policy/cms/1115-stc/<demonstration slug>`, `expression_date` = the approval date) plus a `family: cms_1115_stc`
queue row for each of the thirteen states - the six without an approved eligibility demonstration get a `needs_review`
row that records why (AK: Behavioral Health Reform is SUD/SMI only; ID: Medicaid Reform Waiver pending, ID-04 is
1915(b); ND: 1915(b)/(c) only; NE: Heritage Health Adult terminated 2021-09-02; NV: Healthy Futures pending,
Comprehensive Care Waiver expired; SC: Healthy Connections Works and Palmetto Pathways withdrawn, 2025 applications
pending). Those six cells are ABSENT in the decisions file, not OUTREACH: the publisher answers and posts nothing to take.

Documents taken: KY TEAMKY technical-corrections approval 2025-03-20 (the 2024-12-12 extension STCs as corrected);
MT Plan First 2019-03-29 extension approval (full STCs) and the 2025-04-30 STI/STD amendment (the first extraction took
the amendment alone - 3 rows, an approval letter - so the generator was corrected to take both and the scope was
re-extracted under the same, still-unreleased version); PA former foster care youth / SUD continuous-eligibility
amendment approval 2024-11-14 and Keystones of Health approval 2024-12-26; SD former foster care youth extension
approval 2023-10-30; VA "Building and Transforming Coverage" 2026 renewal approval 2026-07-31 and FAMIS MOMS / FAMIS
Select approval 2021-11-18; WI BadgerCare Reform approval 2025-05-12 and SeniorCare COVID-19 amendment approval
2022-06-07 (the re-issued STCs); WY Pregnant By Choice STI/STD amendment approval 2025-04-30.

| Jurisdiction | Version | Documents | Rows | Chars | Seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| us-ky | 2026-09-15-medicaid-1115-stc | 1 | 157 | 360,925 | 2 |
| us-mt | 2026-09-15-medicaid-1115-stc | 2 | 37 | 89,386 | 2 |
| us-pa | 2026-09-15-medicaid-1115-stc | 2 | 120 | 317,562 | 1 |
| us-sd | 2026-09-15-medicaid-1115-stc | 1 | 32 | 81,488 | 1 |
| us-va | 2026-09-15-medicaid-1115-stc | 2 | 127 | 333,400 | 25 |
| us-wi | 2026-09-15-medicaid-1115-stc | 2 | 88 | 232,206 | 21 |
| us-wy | 2026-09-15-medicaid-1115-stc | 1 | 59 | 139,032 | 2 |

## Part A3 - Wyoming EOM (batch 8 of the manual generator)

Batch 8 was added to `scripts/build_medicaid_state_eligibility_manual_manifests.py` (`--batch 8 --only us-wy`, version
`2026-09-15-medicaid-eligibility-manual-closure`, source date 2026-09-15): `build_wy` now fetches every index link once
(`_wy_probe`), inventories 404s as `dead_index_link` (none tonight) and image-only Tables as
`eligibility_table_image_only` (3), and takes the rest with `html_content_selector: div.UtePc` and drop selectors for
the navigation and banner. 121 documents (107 policy pages, 14 text Tables), citation root `us-wy/manual/wdh/medicaid`,
458 rows (121 document roots + 337 blocks), 362,513 characters, 16 s. The batch-5 `needs_review` queue row becomes
`agent_ready` with the batch-8 note appended.

Cells (53 WY EXTRACTABLE cells, decided by the schema's own patterns over the new scope, headings first): 17 PRESENT
(1396p(b) M403, 1396p(c) and 1396r-5 in M200 definitions, 435.135 M1005D Pickle, 435.541, 435.602 M1101 QMB, 435.911,
.912, .917 M1500 Notices, .919, .920, .923, .945 M301A, M-SS-INCOME-TABLE Table 1, ...), 5 REVIEW (weak-pattern
candidates: 435.531, .540 Table 8, .904, .908 in M400), 30 ABSENT - the manual is now held and the strong pattern finds
no text (Wyoming has no medically needy program, no 209(b) rules, no spousal-support extension chapter, and the
optional groups of 435.2xx are not described), 1 OUTREACH (the image-only Tables 7, 2a, 5b: resource standards and the
ABD/institutional standards).

## Part A4 - the 435.904 / 435.908 / 435.918 / 435.912 / 435.1200 EXTRACTABLE cells (held-text check)

The 09-14 check named an untaken family for each of these cells, but the elements are narrow (outstation locations,
application assisters, electronic notices, timeliness, coordination with the exchange) and the named families are
mostly unrelated (prior editions, transmittal letters, table-of-contents repeats). Before extracting anything the
state's program, CHIP and CMS state-plan scopes were searched with a broadened vocabulary (`out-stationed`,
`outreach site`, `application (site|location)`, `assister`, `navigator`, `notices electronically`, `e-notice`,
`electronic format` ...). Result: 34 cells are check-pattern misses, the text is held (`ALREADY-HELD` rows with the
citation): 435.904 in 17 states (AR MS manual "out-stationed DCO workers" - the schema pattern `outstation` misses the
hyphen; MA 130 CMR 502 "MassHealth outreach site"; ND 510-03-25-05 applications at a DSH hospital or FQHC; NY MRG
outreach sites; UT 107-1 outreach location; twelve CMS CHIP plans that describe outstationed eligibility workers; and TN's
MACPro S-series page "B. Establishment of Outstation Locations"), 435.908 in 10 (CHIP plan outreach sections; AK fee
agents; SD hospital PE application assistance), 435.918 in 6 (DCMR 29-9500 election to receive notices electronically,
NC MA-2420, RI 210-RICR-30-00-3 secure online account, CO and VA application forms, TN's MACPro S-series "G. Notices"
page), 435.1200 in MA. The other 82 cells are `ABSENT` with the carrying page named: for a converted state the MACPro
S-series pages "Establishment of Outstation Locations", application assistance and "Notices" carry the election (held
only for TN tonight); for the rest the CHIP-plan hits are the CMS template guidance sentence, not state text. The
CMS-template sentences ("Outreach strategies may include ... outstationed eligibility workers") should be excluded from
any tightened pattern.

## Part B - reading pass (246 cells, 41 elements)

Method as the preamble: elements sorted by REVIEW count; for each, six cited provisions spread across the alphabetical
state list were opened from the JSONL (heading, kind, a 500-900 character window around the pattern hit) and read
against the schema definition. Medicaid first (eligibility-group and income elements, then administrative), CHIP last;
the 765 REVIEW rows with no cited provision were not read (there is nothing to open; they are "not found" rows). Every
read cell is in the decisions file (`REVIEW -> PRESENT | ABSENT-IN-CITED`, with the citation and a one-line reading);
each element has an `all` row with the verdict and the stronger pattern or carrying family.

Verdicts:

- **PATTERN-CONFIRMED (3).** `M-435-115` (four-month spousal-support extension: AK 832, HAR 17-1717.1-4, KY MS 4100,
  NC MA-3400, OAR 410-200-0440, UT 343 - 6/6; promote the weak pattern, heading vocabulary "Four Months Transitional",
  "4 Month Extended"); `M-435-172` (hospitalized child at 19: the MACPro "Continuous Eligibility for Children" page
  section A in AR KS MI PA UT plus DE DSSM 15300.4 - 6/6; pattern "Continuous Eligibility for Hospitalized Children");
  `M-435-320` (aged medically needy: the MACPro S-series "F. Countable Income Deductions for the Medically Needy ... age
  65 or older or who have blindness or a disability" page in AK DE MN, NJAC 10:70-5.3, SD supplement 2 - 5/6).
- **ABSENT-IN-CITED (18 elements).** The hit is a cross-reference or a different rule. Three are pattern defects:
  `M-435-520` (`age(d)? 65` matched the heading "Page 65" in five of six cells), `M-435-552` (`(80|eighty) hours` matches
  payroll examples, the PRA burden statement on every MACPro page and the SNAP ABAWD rule), `M-435-551` (`work
  requirement` matches SNAP/TANF and buy-in employment rules). The rest name the carrying family: the MACPro
  reviewable-unit election pages in the 2026-09-13 state-plan scopes for the optional groups (`M-435-220` 35 states hold
  "42 CFR 435.220 ... The state elects", `M-435-227`, `M-435-211`, `M-435-324`, `M-ST-1396a-m` "Age and
  Disability-Related Poverty Level"), the CMS SPA "Benefits" topic packages (attachment 3.1-A/B) for `M-SS-BENEFITS`
  (untaken by the 09-13 state-plan generator: EXTRACTABLE), the 1115 STCs for `M-ST-1315` (taken tonight for seven
  states), attachment 2.6-A supplements for `M-435-735`, `M-435-845`, and for CHIP the plan-template items whose hits
  are the template's own instruction text (`C-457-340`, `C-457-410`, `C-457-1010`, `C-457-1005`, `C-457-1110`).
- **Mixed, stay REVIEW (20 elements)** with per-cell verdicts and the stronger pattern recorded: e.g. `M-435-218/222/223`
  (the MACPro RU pages carry the election but the summary lists lose their radio glyphs to OCR; pattern
  `42 CFR 435\.2xx.{0,300}elects` in state-plan scopes), `M-435-230/631` (the S-series 1634/SSI-criteria/209(b)
  election page settles applicability; only nine 209(b) states), `M-435-130/132/133` (grandfathered-group chapters),
  `M-435-531` (medical review team vocabulary), `C-457-320-a`, `C-457-348` ("transfer(red)? to the FFM|Marketplace"),
  `C-457-525` (the state's answer after "(42CFR 457.505(b))"), `C-457-540` (exclude the template guidance sentence).

A structural finding for the checker: for the 42 CFR 435 subpart B-D optional groups the 2026-09-13 medicaid-state-plan
scopes hold the MACPro "Eligibility Groups - Options for Coverage" reviewable-unit pages (`42 CFR 435.xxx ... The state
elects to cover ... Yes/No`) for 33-48 states per section (counted over the scopes: 435.110 36, .116 37, .118 36, .119
48, .120 37, .150 35, .214 37, .218 33, .219 10, .220 35, .222 37, .226 35, .227 34, .229 35, .406 43, .601 20, .603
34). A pattern on that page settles the election for every converted state; the OCR'd radio glyphs are legible on the
per-group pages (MS, DE) and lost on the summary lists.

## Code changes

- `scripts/build_medicaid_magi_verification_plan_manifests.py` (new), `scripts/build_medicaid_1115_stc_manifests.py`
  (new): official-document manifests plus queue rows, as above; both read every cited page live.
- `scripts/build_medicaid_state_eligibility_manual_manifests.py`: batch 8 (`build_wy_closure`, `_wy_probe`,
  `VERSION_BATCH8`, the selector change in `build_wy`, the `BATCHES`/`BATCH_VERSIONS` entries, `--batch 8`,
  `builder_row_note` date and run-note for batch 8, the batch-8 row suffix).
- `manifests/medicaid-agent-queue.yaml`: 51 `magi_verification_plan` rows, 13 `cms_1115_stc` rows, the us-wy first row
  resolved, three policy notes; `status_counts` {needs_review 7, agent_ready 155, blocked_primary_source 7, done 6}.
- `uv run ruff check` on the three generators: clean. Focused tests
  `uv run --extra dev pytest -q -m "not integration and not slow" -k "medicaid or official_documents or manifest"`:
  9 passed, 1 failed - `tests/test_armenia_arlis.py::test_checked_in_tax_code_2024_continuity_sources_match_manifest`,
  the sparse-checkout fixture failure the wave-4 notes list (it needs a `data/corpus` artifact the worktree does not
  hold); nothing touched by this branch.

## What stays open

- EXTRACTABLE (16): the income and premium tables for HI ID KS MN OH (Medicaid) and AK AZ FL HI ME MN NH NM OH RI SC
  (CHIP), not attempted this wave; and `M-SS-BENEFITS` for every state (attachment 3.1-A/B via the CMS SPA "Benefits"
  topic, a TAKE_TOPICS extension of `build_cms_state_plan_manifests.py`).
- `M-ST-1315` for the 35 REVIEW states: the same STC family; the 2026-09-13 lead-list URL for the 1115 list is dead.
- OUTREACH (1): the three image-only Wyoming Tables.
- REVIEW: the 20 mixed elements (per-cell verdicts recorded) and the 765 no-citation REVIEW rows, which are "not found"
  rows the checker should re-label.
- Pattern fixes for the checker: `M-435-520`, `M-435-552`, `M-435-551`, the CMS CHIP-template sentences, the MACPro RU
  page patterns above.

## Controller

Additions only, no swaps: 51 `us-xx/policy/2026-09-15-medicaid-magi-verification-plan`, 7
`us-xx/policy/2026-09-15-medicaid-1115-stc` (KY MT PA SD VA WI WY), 1 `us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure`.
No existing scope is superseded (Wyoming had no released Medicaid manual scope; the collision scan of the new citation
roots `cms/magi-verification-plan`, `cms/1115-stc` and `us-wy/manual/wdh/medicaid` against the same-jurisdiction scopes
found no shared path). Artifacts are unsigned on the controller's disk.

Rebuild:

```bash
cd ~/axiom-corpus-worktrees/w5-medicaid-chip
export REQUESTS_CA_BUNDLE=$(uv run python -c "import certifi;print(certifi.where())")
uv run python scripts/build_medicaid_magi_verification_plan_manifests.py
uv run python scripts/build_medicaid_1115_stc_manifests.py
uv run python scripts/build_medicaid_state_eligibility_manual_manifests.py --batch 8 --only us-wy
for m in manifests/us-*-medicaid-magi-verification-plan.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-15-medicaid-magi-verification-plan --manifest $m --source-as-of 2026-09-15; done
for m in manifests/us-*-medicaid-1115-stc.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-15-medicaid-1115-stc --manifest $m --source-as-of 2026-09-15; done
uv run axiom-corpus-ingest extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --version 2026-09-15-medicaid-eligibility-manual-closure --manifest manifests/us-wy-medicaid-eligibility-manual.yaml \
  --source-as-of 2026-09-15
```
