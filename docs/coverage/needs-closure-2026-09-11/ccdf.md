# CCDF: needs-driven closure check (2026-09-11)

Question: does the corpus hold every source-document family a complete encoding of the CCDF
(child care subsidy) rulebook needs, per jurisdiction (federal plus the 50 states and DC), and
where not, is the gap EXTRACTABLE, ABSENT, OUTREACH or REVIEW? The bar is the law's own
structure; PolicyEngine is a cross-check only. Files: `ccdf-schema.yaml`, `ccdf-matrix.csv`,
`build_tanf_ccdf_matrix.py`, `summary.json`.

## Method

1. Schema. The CCDBG Act 42 U.S.C. 9857-9858r in seven section groups (the text is not in the
   corpus, so 9858d-9858m and 9858o-9858r are grouped rather than enumerated); every live section
   of 45 CFR 98 (61, from the eCFR structure of 2026-09-09; each flagged when it sets or bounds a
   state-level element); one ACF OCC guidance element (Program Instructions, ACF-118 preprint and
   instructions); 30 state-level elements taken from what 45 CFR 98.16 requires a Lead Agency to
   set, laid out along the ACF-118 FFY 2025-2027 plan preprint (10 sections, 41 subsections,
   numbered questions read from the Oklahoma plan bodies) plus the document families the run
   notes inventoried: Appendix 1, amendments, the state subsidy rulebook and current rate/copay
   schedules. Each state element carries a `facts` list. 99 elements in total.
2. Check. Selected scopes: the 2026-09-11 union selector (44 `2026-09-10-ccdf-plan-fy2025-2027`
   plan scopes, 43 states plus Guam) plus `us/regulation/2026-09-11-title-45-part-98`. Federal
   CFR elements are PRESENT when the section body in the part 98 scope is non-empty (all 61).
   Plan-carried state elements are PRESENT when the plan subsection named in the schema carries the
   element's vocabulary (scope, `citation_path` and a snippet recorded); Georgia's plan is
   page-level inside the June CAPS manual scope and is checked by section label plus pattern per
   page. ccdf-s29 (state rulebook) is PRESENT only where a selected scope carries a child-care
   subsidy chapter with the subsidy vocabulary (AZ, CO, GA, IL, KS, MI, NH, UT; every other
   selected TANF/combined scope was heading-scanned and carries none). EXTRACTABLE, OUTREACH and
   REVIEW for the document families come from the queue rows and the three run notes (publisher
   inventories by family, blocks, drafts).
3. Cross-check. PolicyEngine `gov/hhs/ccdf` and 37 state child-care trees; rulespec-us (no CCDF
   wrappers; two Arizona policies).

Row convention: 30 state elements x 51 = 1,530 state rows; 69 federal rows at `us`; 1,599 rows.

## Results

| | cells | PRESENT | EXTRACTABLE | OUTREACH | ABSENT | REVIEW |
|---|---:|---:|---:|---:|---:|---:|
| federal (us) | 69 | 61 | 7 | 0 | 0 | 1 |
| state (51 x 30) | 1,530 | 1,136 | 120 | 144 | 0 | 130 |
| all | 1,599 | 1,197 | 127 | 144 | 0 | 131 |

45 CFR 98 is complete in the corpus (taken 2026-09-11, 73 rows, every section body non-empty);
the CCDBG Act is absent (7 EXTRACTABLE groups, uscode.house.gov); OCC guidance and the ACF-118
preprint are not in the corpus (REVIEW). No cell is ABSENT.

The state picture splits into two: 43 states with a selected plan, where 26-28 of 30 elements
are PRESENT and the remainder are the four document families below; and 8 states without a
usable plan: AZ, MD, MO, NY, TX blocked (OUTREACH, 27-29 cells each; the queue records the exact
bot wall: cloudflare, "Access denied", Drupal antibot/Incapsula, F5/Shape TSPD, AWS WAF), IN
posts only a non-CARS certified submission (EXTRACTABLE with a pattern change, 28 cells), AK
posts only a 2024-05-24 draft (REVIEW, 29 cells: reviewer decision whether a draft counts), and
GA, whose approved plan is in the corpus page-level inside the CAPS scope but whose pages did
not match section label plus pattern for 22 elements (REVIEW: read the pages or re-extract the
plan with the CARS section pattern from the retained PDF).

### Top gaps by how many states share them

| gap | states affected | class | what closes it |
|---|---:|---|---|
| ccdf-s27 Appendix 1 (implementation plan for waived federal requirements) | 51 | EXTRACTABLE | 51 ACF-hosted PDFs listed on the FY 2025-2027 index, 0 taken: one manifest-driven run |
| ccdf-s30 current-year rate and copay schedules | 51 (17 EXTRACTABLE, 4 OUTREACH, 30 REVIEW) | mixed | the plan carries values as of 2024-10-01 only; 17 states' publisher pages list rate sheets, MRS reports or fee tables (run notes); 30 states' pages were not inventoried for this family |
| ccdf-s28 approved amendments | 46 (11 EXTRACTABLE, 6 OUTREACH, 29 REVIEW); 5 PRESENT because the amended plan was the only version posted | mixed | take the separately posted consolidated amendments for CA, DC, MA, ME, NC, ND, OH, OR, SD, VT, WA; re-check the other pages |
| ccdf-s29 state subsidy rulebook | 43 (15 EXTRACTABLE, 4 OUTREACH, 24 REVIEW) | mixed | 15 rulebooks are listed on publisher indexes already used (IN CCDF Policy Manual, KY Vol. VIII, NM 8.150, RI 218-RICR-20-00-4, SC, TN, ID 16.06.12, NE Title 392, OH 5101:2-16, OK 340:40, SD 67:47, OR OAR 414, WI Shares manual, VT CCFAP, ME 10-148 ch. 6); 24 states need an inventory |
| plan-carried elements where no plan is selected | 8 (AZ, MD, MO, NY, TX, IN, AK, GA) | OUTREACH 5, EXTRACTABLE 1, REVIEW 2 | publisher cooperation for the five bot walls; IN pattern change; AK reviewer decision; GA page read |
| 42 U.S.C. 9857-9858r | 51 (inherited) | EXTRACTABLE | `extract-uscode` title 42 chapter 105 subchapter II-B |

Gap cells by carrying family (state level): Appendix 51; rate/copay schedules 51; amendments 46;
state rulebook 43; the 26 plan-section families 7-8 each (the same 8 states).

## Elements beyond PolicyEngine

PolicyEngine models 9 of the 30 state elements fully (child age limit, initial income limit,
exit threshold where modeled, countable income, copay cap and sliding scale, copay method where
modeled, base rates, the state rulebook as a cited source, dated rate values) and 6 partially
(activity hours in 18 states, the asset limit in 5, immigration status in 5, copay waivers in 6,
provider types as rate categories, quality/special-needs add-ons in 10). The law has 15 state
elements PolicyEngine does not model: ccdf-s01 Lead Agency and local variation, s09 protective
services and foster care eligibility, s10 priority groups and very-low-income definition, s11
12-month eligibility and temporary changes, s12 continued assistance after job loss, s13 change
reporting, s14 presumptive eligibility, s19 market rate survey and cost analysis, s22 payment
practices (enrollment-based payment, absences, registration fees), s23 provider standards, s24
the TANF work-penalty exception definitions, s25 program integrity, s26 the plan document, s27
Appendix 1, s28 amendments. PolicyEngine models nothing of 45 CFR 98 or the CCDBG Act directly.
rulespec-us has no CCDF wrappers; the corpus now carries 45 CFR 98 whole and 43 approved plans,
so a first federal-plus-plan encoding is not blocked by the corpus except for the 8 states
above and the four document families.

## Schema uncertainties

- 42 U.S.C. 9858d-9858m and 9858o-9858r are grouped; take the title before treating the statute
  rows as section-complete.
- Plan-carried PRESENT means the plan subsection carries the element's vocabulary; the plan
  states values as of its submission (2024-10-01, or the amendment taken for AR, IA, LA, MI, MN),
  and whether an encoder may cite the plan in place of the state rule is a rules-repo decision.
  That is why ccdf-s29 (rulebook) and ccdf-s30 (current schedules) are separate elements.
- Provider standards (ccdf-s23) are summarized by the plan; the licensing code is out of scope.
- The 30 elements follow the preprint's question structure; a finer split (one element per
  numbered question, about 120) would not change the family-level findings because the same
  plan section carries them.

## Timing and searches

Same session as `tanf.md` (2026-09-12, 08:30-09:20 EDT). CCDF-specific searches: row listing of
`us/regulation/2026-09-11-title-45-part-98` (73 rows, 61 sections, all non-empty bodies) and its
structure snapshot; OK plan rows (42) and the 2.2/3.1/3.2/4.3 bodies for the question labels;
GA CAPS scope (506 rows, 389 plan pages) and the 2.2.3 page; AZ CCAP manual (82 rows) and AAC
article 49; heading scan of all 51 selected TANF/combined scopes for subsidy chapters; PolicyEngine
child-care trees (37 states, file lists for 21); rulespec-us grep for `ccdf|child care`.
The CCDF queue (all 57 rows) and the three run notes (first run, retry, retry 2 from a US network)
were read in full; their per-state family inventories are transcribed into `CCDF_RATE_SHEETS`,
`CCDF_RULEBOOK_LISTED`, `CCDF_AMENDMENTS`, `CCDF_PLAN_BLOCKED` and `CCDF_PLAN_NOT_TAKEN`.


## Generated roll-up tables (from summary.json, build of 2026-09-12)

### Per-jurisdiction roll-up (state-level elements)

| jurisdiction | PRESENT | EXTRACTABLE | OUTREACH | ABSENT | REVIEW | main gap note |
|---|---:|---:|---:|---:|---:|---|
| us-ak | 0 | 1 | 0 | 0 | 29 | publisher posts only the 2024-05-24 draft '2025-2027 CCDF State Plan 052424.pdf' on the Online Public Notice ( |
| us-al | 26 | 1 | 0 | 0 | 3 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-ar | 27 | 1 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-az | 1 | 1 | 27 | 0 | 1 | HTTP 403 cloudflare from the AZ DES plan page (plain and impersonated |
| us-ca | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-co | 27 | 2 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-ct | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-dc | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-de | 26 | 1 | 0 | 0 | 3 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-fl | 26 | 1 | 0 | 0 | 3 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-ga | 6 | 1 | 1 | 0 | 22 | GA plan pages (CAPS scope) did not match the section label + pattern |
| us-hi | 26 | 1 | 0 | 0 | 3 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-ia | 27 | 1 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-id | 26 | 3 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-il | 27 | 1 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-in | 0 | 28 | 0 | 0 | 2 | carried by the certified plan the publisher posts |
| us-ks | 27 | 1 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-ky | 26 | 3 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-la | 27 | 2 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-ma | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-md | 0 | 1 | 29 | 0 | 0 | HTTP 403 'Access denied' on earlychildhood.marylandpublicschools.org/2025-2027-ccdf-plan (retried 3x) |
| us-me | 26 | 4 | 0 | 0 | 0 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-mi | 28 | 1 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-mn | 27 | 2 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-mo | 0 | 1 | 29 | 0 | 0 | dese.mo.gov serves a Drupal antibot/Incapsula form instead of the plan PDF (retried 3x) |
| us-ms | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-mt | 26 | 1 | 0 | 0 | 3 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-nc | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-nd | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-ne | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-nh | 27 | 1 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-nj | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-nm | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-nv | 26 | 1 | 0 | 0 | 3 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-ny | 0 | 1 | 29 | 0 | 0 | ocfs.ny.gov F5/Shape TSPD JavaScript challenge instead of the index (retried 3x) |
| us-oh | 26 | 3 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-ok | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-or | 26 | 4 | 0 | 0 | 0 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-pa | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-ri | 26 | 3 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-sc | 26 | 3 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-sd | 26 | 3 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-tn | 26 | 3 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-tx | 0 | 1 | 29 | 0 | 0 | HTTP 403 CloudFront / HTTP 202 AWS WAF challenge from the TWC plan page (retried 3x) |
| us-ut | 27 | 2 | 0 | 0 | 1 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-va | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-vt | 26 | 4 | 0 | 0 | 0 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-wa | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-wi | 26 | 2 | 0 | 0 | 2 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-wv | 26 | 1 | 0 | 0 | 3 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |
| us-wy | 26 | 1 | 0 | 0 | 3 | ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC ( |

### Elements by number of states not PRESENT

| element | name | PRESENT | EXTRACTABLE | OUTREACH | ABSENT | REVIEW |
|---|---|---:|---:|---:|---:|---:|
| ccdf-s27 | Plan Appendix 1: Lead Agency implementation plan for federal non-compliances (waived requi | 0 | 51 | 0 | 0 | 0 |
| ccdf-s30 | Current-year payment rate schedule and copay schedule updates (rate sheets, transmittals)  | 0 | 17 | 4 | 0 | 30 |
| ccdf-s28 | Plan amendments approved after the initial plan (consolidated amended plans) | 5 | 11 | 6 | 0 | 29 |
| ccdf-s29 | State CCDF subsidy rulebook (state regulation or policy manual operationalizing eligibilit | 8 | 15 | 4 | 0 | 24 |
| ccdf-s02 | Child age limit (under 13; optional to 19 if incapable of self-care/under court supervisio | 43 | 1 | 5 | 0 | 2 |
| ccdf-s03 | Reason for care: definitions of working, job training/education, job search; minimum activ | 43 | 1 | 5 | 0 | 2 |
| ccdf-s04 | Initial income eligibility limit (share of SMI or FPL by family size) | 43 | 1 | 5 | 0 | 2 |
| ccdf-s05 | Graduated phase-out / exit threshold at redetermination (second tier up to 85% SMI) | 43 | 1 | 5 | 0 | 2 |
| ccdf-s06 | Family asset limit ($1,000,000 certification) | 43 | 1 | 5 | 0 | 2 |
| ccdf-s07 | Countable income definition and treatment of irregular fluctuations in earnings | 43 | 1 | 5 | 0 | 2 |
| ccdf-s08 | Additional state eligibility criteria and residency (98.20(b)) | 43 | 1 | 5 | 0 | 2 |
| ccdf-s11 | Minimum 12-month eligibility period and temporary changes | 43 | 1 | 5 | 0 | 2 |
| ccdf-s12 | Job search and continued assistance after loss of activity (minimum three months) | 43 | 1 | 5 | 0 | 2 |
| ccdf-s13 | Change reporting requirements during the eligibility period | 43 | 1 | 5 | 0 | 2 |
| ccdf-s14 | Presumptive eligibility (optional, up to three months) | 43 | 1 | 5 | 0 | 2 |
| ccdf-s15 | Family co-payment cap (7% of income) and sliding fee scale by income and family size | 43 | 1 | 5 | 0 | 2 |
| ccdf-s16 | Co-payment calculation method (per child / per family, dollar vs percent) | 43 | 1 | 5 | 0 | 2 |
| ccdf-s17 | Co-payment waiver criteria (income at/below 150% FPL, protective services, homelessness, d | 43 | 1 | 5 | 0 | 2 |
| ccdf-s18 | Provider options, parental choice, certificates vs grants/contracts, in-home care limits | 43 | 1 | 5 | 0 | 2 |
| ccdf-s19 | Market rate survey or alternative methodology and narrow cost analysis (basis for rates) | 43 | 1 | 5 | 0 | 2 |
| ccdf-s20 | Base payment rates by provider type, age of child and region | 43 | 1 | 5 | 0 | 2 |
| ccdf-s21 | Tiered, differential and add-on rates (quality, special needs, non-traditional hours, infa | 43 | 1 | 5 | 0 | 2 |
| ccdf-s22 | Payment practices: enrollment-based payment, absence policy, timeliness, registration fees | 43 | 1 | 5 | 0 | 2 |
| ccdf-s24 | Exception to TANF work penalties for single parents of children under six (definitions of  | 43 | 1 | 5 | 0 | 2 |
| ccdf-s25 | Program integrity: fraud investigation, recovery of misspent funds, client and provider sa | 43 | 1 | 5 | 0 | 2 |
| ccdf-s01 | Lead Agency and policy-setting authority (statewide vs local variation) | 44 | 1 | 5 | 0 | 1 |
| ccdf-s09 | Protective services and foster care eligibility (waiver of income/activity requirements) | 44 | 1 | 5 | 0 | 1 |
| ccdf-s10 | Priority groups and definition of very low income; homeless enrollment grace period | 44 | 1 | 5 | 0 | 1 |
| ccdf-s23 | Provider standards: licensing, ratios/group size, health and safety, background checks, re | 44 | 1 | 5 | 0 | 1 |
| ccdf-s26 | CCDF state plan FFY 2025-2027 (ACF-118) as the certified/approved document | 44 | 1 | 5 | 0 | 1 |

### Gap cells by carrying family

| family | EXTRACTABLE | OUTREACH | ABSENT | REVIEW | total |
|---|---:|---:|---:|---:|---:|
| ACF-hosted Appendix PDF on the FY 2025-2027 index (51 listed, 0 taken) | 51 | 0 | 0 | 0 | 51 |
| state rate schedules / MRS sheets / transmittals (state-published) | 17 | 4 | 0 | 30 | 51 |
| amended plans posted on Lead Agency pages (inventoried, not taken except where the only posted version) | 11 | 6 | 0 | 29 | 46 |
| state regulation/manual for the subsidy program (CCAP/CCS/ERDC/Wisconsin Shares etc.) | 15 | 4 | 0 | 24 | 43 |
| CCDF state plan 2.2.1 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 2.2.2 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 2.2.3-2.2.4 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 2.5.5 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 2.2.6 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 2.2.5 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 2.2.7 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 2.5.2 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 2.5.3 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 2.5.4 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 2.1 / 2.5 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 3.1.1-3.1.2 (fee table) | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 3.2.1 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 3.3.1 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 4.1.1 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 4.2 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 4.3.1-4.3.2 (rate tables as of plan date) | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 4.3.3 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 4.4.1-4.4.3 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 2.2.9 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 10.1-10.2 | 1 | 5 | 0 | 2 | 8 |
| CCDF state plan 1.1-1.2 | 1 | 5 | 0 | 1 | 7 |
| CCDF state plan 2.2 / 2.3 | 1 | 5 | 0 | 1 | 7 |
| CCDF state plan 2.3.1-2.3.3 | 1 | 5 | 0 | 1 | 7 |
| CCDF state plan section 5 | 1 | 5 | 0 | 1 | 7 |
| CCDF state plan (Lead Agency publication reached via the ACF index) | 1 | 5 | 0 | 1 | 7 |

### Federal rows

{'EXTRACTABLE': 7, 'PRESENT': 61, 'REVIEW': 1}
