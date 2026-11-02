# CHIP: needs-driven closure check (pass 2 schema, re-run 2026-09-14 on the sixth cut)

Question: does the corpus hold every source-document family a complete encoding of the CHIP
rulebook (Title XXI, 42 CFR 457, and the Medicaid rules that govern Medicaid-expansion CHIP) needs,
per jurisdiction, and where it does not, is the gap extractable, absent, outreach or review?

Files: `chip-schema.yaml` (186 elements), `chip-matrix.csv` (9,672 rows = 186 x 52), `tools/`.
The method, search rules, pass-1 audit and timing are those of `medicaid.md`; only what differs
is stated here.

## Method (differences from Medicaid)

- **Schema.** 42 U.S.C. 1397aa-1397mm section by section (15 elements, including 2110(b) targeted
  low-income child, 2112 pregnant women and the unborn-child/FCEP option), every section of 42 CFR
  457 subparts A-L (163 elements, one per held section; 457.340 and 457.960 are held in the
  CMS-2454-IFC conforming-amendments scope, the rest in the released recovery scope), the six
  42 CFR 435 rules that 457.70, .315, .342, .355 and .360 apply to Medicaid-expansion CHIP children
  (435.229, .118, .603, .926, .1102, .117), and three state-structure elements (approved CHIP state
  plan, current-year income band and premium table, the state's disqualifying-coverage rule).
  Levels: 136 `federal_only`, 10 `federal_with_state_option`, 40 `state`.
- **Search universe.** The state's CHIP scope and its Medicaid scope together (Medicaid-expansion
  CHIP is determined under the Medicaid manual, and 13 CHIP queue rows are pointers into Medicaid
  scopes), plus the pointer scopes; elements flagged `chip_context` require a CHIP program name or
  Title XXI reference within 600 characters when the hit is in a Medicaid scope.
- **Fallbacks.** 457.70 (program type) and the FCEP election are settled by the CMS CHIP
  children-coverage map record for the state (`us/form/2026-07-05-cms-chip-children-coverage-map`),
  whose body carries the program type and "+ FCEP option" where elected; the evidence note says
  whether the record elects or does not elect FCEP. 457.60 (SPAs on record) is PRESENT for the 20
  states whose CHIP SPAs are in `us/policy/2026-07-05-cms-chip-fcep-spa`. The CMS eligibility-levels
  table is accepted (with a staleness note) for the separate-CHIP upper income limit and the
  M-CHIP band (457.310, 435.229, 435.118, 2110(b)) but not for `C-SS-INCOME-PREMIUM-TABLE`.
- **Gap rules.** OUTREACH follows the CHIP queue row's block (CA, DC, FL, MT, WY); for the 13
  done-by-pointer rows it follows the Medicaid row. ABSENT applies only where the queue row records
  that the agency publishes no CHIP manual (AL, CT, NY) and no CMS plan section carries the element.
- **Pass-2 audit.** A 20-cell random sample of PRESENT cells was read: 16 carry the element; 4 are
  wrong or marginal (NC 2112 matched "Pregnancy Medical Home"; NC 457.350 matched an enumeration
  penalty paragraph; WV 457.330 and WA 457.380 cite change-log and public-health-emergency pages).
  The residual false-positive rate is estimated at 15-20%, higher than Medicaid because CHIP text
  is thinner and the CHIP-context test lets Medicaid-manual paragraphs through.

## Results

> Re-run 2026-09-14 against `manifests/releases/us-rulespec-2026-09-14-wave4-r2-union.json` (the sixth cut) with the 2026-09-12 element list unchanged (`tools/build_matrix.py --selector --program chip`); every PRESENT cell passed the builder's self-check. SPA-document cells now cite the first body-bearing summary block of the CMS CHIP SPA package; the children-coverage-map scope (`us/form/2026-07-05-cms-chip-children-coverage-map`) is not in the sixth cut, so a cell that only it carries is REVIEW. The tables below are `tools/summarize.py` output for that run; the sections from "Top gaps" down keep the 2026-09-12 reading.

### Status totals (all cells)

| Status | Cells |
| --- | ---: |
| PRESENT | 2039 |
| EXTRACTABLE | 11 |
| ABSENT | 2 |
| OUTREACH | 7 |
| REVIEW | 674 |
| INHERITED | 6936 |
| NOT_APPLICABLE | 3 |
| total | 9672 |

### Status totals (state-level checked cells only)

| Status | Cells | Share |
| --- | ---: | ---: |
| PRESENT | 1856 | 72.8% |
| EXTRACTABLE | 11 | 0.4% |
| ABSENT | 2 | 0.1% |
| OUTREACH | 7 | 0.3% |
| REVIEW | 674 | 26.4% |
| total | 2550 | |

### Federal row (us)

| Status | Elements |
| --- | ---: |
| PRESENT | 183 |
| NOT_APPLICABLE | 3 |

Federal elements not PRESENT (NOT_APPLICABLE rows are state-only structure elements):


### Per-jurisdiction roll-up (state-level checked elements)

| Jurisdiction | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | checked | PRESENT share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| us-ak | 35 | 1 | 0 | 0 | 14 | 50 | 70% |
| us-al | 36 | 0 | 1 | 0 | 13 | 50 | 72% |
| us-ar | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-az | 35 | 1 | 0 | 0 | 14 | 50 | 70% |
| us-ca | 36 | 0 | 0 | 1 | 13 | 50 | 72% |
| us-co | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-ct | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-dc | 33 | 0 | 0 | 5 | 12 | 50 | 66% |
| us-de | 36 | 0 | 0 | 0 | 14 | 50 | 72% |
| us-fl | 36 | 1 | 0 | 0 | 13 | 50 | 72% |
| us-ga | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-hi | 36 | 1 | 0 | 0 | 13 | 50 | 72% |
| us-ia | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-id | 36 | 0 | 0 | 0 | 14 | 50 | 72% |
| us-il | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-in | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-ks | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-ky | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-la | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-ma | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-md | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-me | 36 | 1 | 0 | 0 | 13 | 50 | 72% |
| us-mi | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-mn | 36 | 1 | 0 | 0 | 13 | 50 | 72% |
| us-mo | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-ms | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-mt | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-nc | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-nd | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-ne | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-nh | 36 | 1 | 0 | 0 | 13 | 50 | 72% |
| us-nj | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-nm | 36 | 1 | 0 | 0 | 13 | 50 | 72% |
| us-nv | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-ny | 36 | 0 | 1 | 0 | 13 | 50 | 72% |
| us-oh | 35 | 1 | 0 | 0 | 14 | 50 | 70% |
| us-ok | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-or | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-pa | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-ri | 36 | 1 | 0 | 0 | 13 | 50 | 72% |
| us-sc | 30 | 1 | 0 | 0 | 19 | 50 | 60% |
| us-sd | 36 | 0 | 0 | 0 | 14 | 50 | 72% |
| us-tn | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-tx | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-ut | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-va | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-vt | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-wa | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-wi | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-wv | 37 | 0 | 0 | 0 | 13 | 50 | 74% |
| us-wy | 36 | 0 | 0 | 1 | 13 | 50 | 72% |

### Top gaps by how many states share them

Not PRESENT in all 51: 457.50, 457.305, `C-SS-STATE-PLAN` (no CHIP state plan held for any state);
457.80, .90, .110 (coordination, outreach, enrollment assistance); 457.320(a) (residency,
citizenship, age, SSN: REVIEW in 46 states, the weak pattern matched but the CHIP-specific rule was
not confirmed); 457.340 (effective dates: 36 REVIEW); 457.348; 457.410 (benefit package: 29 REVIEW);
457.520, .525, .540; 457.1005, .1010, .1110. Then 457.810 (43), 457.805 crowd-out procedures (41),
457.320(a)(9) waiting period (31: 20 states carry one in their text, the rest either have none or
keep it in the plan), 457.60 SPAs (31 states without a held SPA), 457.510 premiums (27; 15 are
REVIEW because the premium text carries no dollar amount), 457.570 disenrollment protections (27).

### Gap families, ranked by cells, with what would close each

| Family that would close the gap | Cells | States | Closure |
| --- | ---: | ---: | --- |
| CHIP state plan sections 4 and 5 (eligibility procedures, outreach, coordination, screening) | 286 | 48 | Take each state's approved CHIP state plan from medicaid.gov/chip/state-program-information (one PDF per state; PA's own index also lists it and it was left untaken). |
| CHIP state plan section 8 (cost sharing: premiums, copayments, 5% cap, disenrollment, AI/AN, well-child) | 232 | 47 | Same document. |
| State's own manual or codified rule, publisher block (CA, DC, FL, MT, WY) | 159 | 5 | Outreach: DC and WY need an ASP.NET-postback fetch or an agency export; FL needs s. 409.814 F.S. from the Legislature (queue note) and the AHCA rule; MT needs rules.mt.gov behind its CAPTCHA; CA needs DHCS. |
| Approved CHIP state plan as a document (457.50, 457.305, C-SS-STATE-PLAN) | 153 | 51 | Same crawl. |
| CHIP state plan section 6 (benefit package, waiver options) | 138 | 46 | Same document. |
| CHIP state plan sections 4.1-4.4 (eligibility standards, MAGI, newborns, PE, CE) | 129 | 49 | Same document; 66 cells are REVIEW candidates in the manuals (residency/citizenship, newborn) that need a reader. |
| CHIP state plan section 4.4 (substitution, waiting periods, disqualifying coverage) | 109 | 44 | Same document. |
| Section 9 and CS-series eligibility SPAs (review process, privacy) | 61 | 46 | Same document plus the CHIP SPA index. |
| CMS CHIP SPA index (457.60) | 31 | 31 | Crawl the CHIP SPA index for the 31 states with no held SPA. |
| Medicaid state plan attachment 2.2-A and PE pages (M-CHIP elements) | 41 | 21 | The Medicaid state plan crawl (see `medicaid.md`). |
| Current-year CHIP income band and premium table | 14 | 14 | 10 states list an untaken family (e.g. MO password-protected section 1840, IA 441 IAC 86, IN chapters 2800/3400, HI income charts); AL and NY publish no manual (ABSENT, the CMS 2023 table is the only held source). |

One crawl, the CMS-posted approved CHIP state plans (51 PDFs) plus the CHIP SPA index, would close
1,180 of the 1,198 EXTRACTABLE and REVIEW cells; the five publisher blocks account for the 159
OUTREACH cells.

### Elements PolicyEngine does not model

PolicyEngine models 16 of 186 elements (separate-CHIP child income limit and max age, pregnant
CHIP limit, FCEP limits and the Alabama flags, disqualifying coverage, the 5% cumulative cap,
premium and enrollment-fee schedules for 17 states, federal share, MAGI via the Medicaid pipeline,
continuous-eligibility and newborn rules are not among them). It does not model 170 elements, of
which 38 are state-level or state-option:

- program structure: program type (M-CHIP, S-CHIP, combination), the state plan and SPAs, the
  eligibility standards section, outreach and enrollment assistance, coordination with Medicaid and
  the Exchange, AI/AN provisions;
- eligibility: residency/citizenship/age/SSN standards as applied to CHIP, waiting periods and
  crowd-out procedures, premium-assistance substitution protections, application and effective
  dates, continuous eligibility (457.342 and 435.926), renewals, screening and referral,
  presumptive eligibility (457.355 and 435.1102), deemed newborns (457.360 and 435.117),
  verification, change reporting;
- cost sharing beyond the 5% cap and premiums: copayment schedules, well-child exemption, nominal
  charges at or below 150% FPL, public schedule, AI/AN exemption, disenrollment protections;
- benefits: benchmark option and the waiver options; review process and privacy.

rulespec-us encodes the CMS eligibility-levels wrappers per state (separate-CHIP limit, pregnant
CHIP availability, FCEP flag, M-CHIP band), the 1397jj(c)(1) child definition and the MAGI
pipeline; nothing else in this schema.

### Schema uncertainties

- 457.320 is split into two elements ((a)-(c) other standards; (a)(9) waiting period) because an
  encoder needs them separately; every other section is one element.
- 457.344 is held only as a removal notice (CMS-2454-IFC conforming amendments) and is not an
  element, although the rulespec-us wrappers cite it.
- For the 13 done-by-pointer states the CHIP elements were checked against the Medicaid scope; where
  a Medicaid manual mentions CHIP only in passing (OH, SC, AZ) the check under-reports what the
  state's separate CHIP documents (Ohio has none; SC's chapter 204.03 is chapter-level) would carry.
- The three agency-page states (AL, CT, NY) are ABSENT only for the current-year table; the queue
  row's "publishes no manual" finding was not re-verified against the agencies in this session.
- The coverage-map record is accepted as carrying the FCEP election for every state; the map is
  dated 2026-07-05 and a later SPA (e.g. NY-23-0034, MD-23-0002) could postdate a state's entry.
