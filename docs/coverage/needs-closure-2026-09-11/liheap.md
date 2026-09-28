# LIHEAP (federal block grant and the FY2026 state plans): needs-driven closure check

Corpus as selected on 2026-09-11 (draft union selector plus the three 2026-09-11 federal scopes); checked 2026-09-12. Schema: `liheap-schema.yaml` (41 elements: 23 federal, 18 state). Matrix: `liheap-matrix.csv` (2132 cells = 52 jurisdictions x 41 elements, one row each). Builder: `build_ssi_liheap_medicare_matrices.py`; verifier: `verify_matrices.py` (re-opens every PRESENT cell: 0 failures).

## Method

The schema follows 42 U.S.C. 8621 to 8630 (ten sections), 45 CFR 96 subpart H (96.80 to 96.89), the
three federal figures a plan encoder needs every year (HHS poverty guidelines, the ACF state median
income table, the model plan instructions), and the FY2026 Detailed Model Plan section by section: the
plan is the state rulebook, so its sections 1 to 17 map to 17 state elements (program components and
dates; funding allocation; categorical eligibility; the SNAP nominal payment; countable income and
household definition; the heating threshold, extra rules and priority groups, benefit variables and
min/max; the benefit matrix attachment; cooling; crisis definitions, response times and benefit levels;
weatherization; outreach and agency designation; hearings; Assurance 16 and performance measures;
monitoring), plus one element for the state policy/operations manual that the clearinghouse index lists
beside each plan and that carries the application procedures and vendor rules the plan only summarises.

Every plan body was opened by regular expression on the extracted text of sections 1, 2, 3 and 4
(`us-xx/policy/acf/liheap-plan/fy2026/N`, 51 scopes of 21 rows): dates of operation, the 2.1 and 4.1
thresholds (`HHS Poverty Guidelines 150.00%`, `State Median Income 60.00%`), the 2.6 minimum and maximum
benefit, the 1.7b nominal amount, the 4.x response hours and the crisis dollar figures. The parsed
values are in the evidence notes so a reader can check them against the plan.

## Cells by status

| status | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cells | 712 | 1268 | 44 | 1 | 107 | 2132 |

Federal elements are checked once and inherited by the 51 states (`evidence_note` = `inherited from federal`); the federal row alone: EXTRACTABLE 23, ABSENT 18. State-level cells (51 x 18): PRESENT 712, EXTRACTABLE 72, ABSENT 26, OUTREACH 1, REVIEW 107.

## Federal roll-up by document family

| federal family | elements | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| statute (US Code Title 42 ch. 94 subch. II) | 10 | 0 | 10 | 0 | 0 | 0 |
| regulation (eCFR, 45 CFR 96 subpart H) | 10 | 0 | 10 | 0 | 0 | 0 |
| annual notice (Federal Register, HHS/ASPE) | 1 | 0 | 1 | 0 | 0 | 0 |
| annual guidance (ACF OCS LIHEAP Information Memorandum) | 1 | 0 | 1 | 0 | 0 | 0 |
| agency guidance (ACF OCS) | 1 | 0 | 1 | 0 | 0 | 0 |

## Per-jurisdiction roll-up (state-level elements)

| jurisdiction | state elements | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | closure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| us-ak | 18 | 14 | 2 | 1 | 0 | 1 | 3 open |
| us-al | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-ar | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-az | 18 | 15 | 2 | 0 | 0 | 1 | 3 open |
| us-ca | 18 | 15 | 0 | 0 | 0 | 3 | 3 open |
| us-co | 18 | 13 | 2 | 1 | 0 | 2 | 4 open |
| us-ct | 18 | 14 | 2 | 1 | 0 | 1 | 3 open |
| us-dc | 18 | 14 | 0 | 0 | 0 | 4 | 4 open |
| us-de | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-fl | 18 | 15 | 2 | 0 | 0 | 1 | 3 open |
| us-ga | 18 | 15 | 2 | 0 | 0 | 1 | 3 open |
| us-hi | 18 | 15 | 2 | 0 | 0 | 1 | 3 open |
| us-ia | 18 | 13 | 2 | 1 | 0 | 2 | 4 open |
| us-id | 18 | 14 | 0 | 1 | 0 | 3 | 3 open |
| us-il | 18 | 14 | 0 | 1 | 0 | 3 | 3 open |
| us-in | 18 | 13 | 2 | 1 | 0 | 2 | 4 open |
| us-ks | 18 | 16 | 0 | 1 | 0 | 1 | 1 open |
| us-ky | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-la | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-ma | 18 | 14 | 0 | 1 | 0 | 3 | 3 open |
| us-md | 18 | 14 | 2 | 1 | 0 | 1 | 3 open |
| us-me | 18 | 14 | 2 | 1 | 0 | 1 | 3 open |
| us-mi | 18 | 14 | 2 | 1 | 0 | 1 | 3 open |
| us-mn | 18 | 13 | 2 | 1 | 0 | 2 | 4 open |
| us-mo | 18 | 13 | 2 | 1 | 0 | 2 | 4 open |
| us-ms | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-mt | 18 | 14 | 2 | 1 | 0 | 1 | 3 open |
| us-nc | 18 | 13 | 0 | 1 | 0 | 4 | 4 open |
| us-nd | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-ne | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-nh | 18 | 13 | 2 | 1 | 0 | 2 | 4 open |
| us-nj | 18 | 15 | 2 | 0 | 0 | 1 | 3 open |
| us-nm | 18 | 14 | 0 | 0 | 0 | 4 | 4 open |
| us-nv | 18 | 13 | 2 | 1 | 0 | 2 | 4 open |
| us-ny | 18 | 15 | 1 | 0 | 1 | 1 | 3 open |
| us-oh | 18 | 13 | 2 | 1 | 0 | 2 | 4 open |
| us-ok | 18 | 14 | 0 | 0 | 0 | 4 | 4 open |
| us-or | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-pa | 18 | 13 | 2 | 1 | 0 | 2 | 4 open |
| us-ri | 18 | 13 | 0 | 1 | 0 | 4 | 4 open |
| us-sc | 18 | 14 | 0 | 0 | 0 | 4 | 4 open |
| us-sd | 18 | 14 | 2 | 1 | 0 | 1 | 3 open |
| us-tn | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-tx | 18 | 15 | 0 | 0 | 0 | 3 | 3 open |
| us-ut | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-va | 18 | 14 | 2 | 0 | 0 | 2 | 4 open |
| us-vt | 18 | 13 | 2 | 1 | 0 | 2 | 4 open |
| us-wa | 18 | 13 | 0 | 1 | 0 | 4 | 4 open |
| us-wi | 18 | 14 | 2 | 1 | 0 | 1 | 3 open |
| us-wv | 18 | 16 | 1 | 0 | 0 | 1 | 2 open |
| us-wy | 18 | 13 | 0 | 1 | 0 | 4 | 4 open |

## Top gaps by how many states share them

| element | name | status | states | which |
| --- | ---: | ---: | ---: | ---: |
| LIHEAP-ST-05 | Countable income (gross/net, income types) and household definition (1.8-1.12) | REVIEW | 51 | ak al ar az ca co ct dc de fl ga hi ia id il in ks ky la ma md me mi mn mo ms mt nc nd ne nh nj nm nv ny oh ok or pa ri sc sd tn tx ut va vt wa wi wv wy |
| LIHEAP-ST-09 | Heating/cooling benefit matrix (plan attachment) | EXTRACTABLE | 37 | ak al ar az co ct de fl ga hi ia in ky la md me mi mn mo ms mt nd ne nh nj nv ny oh or pa sd tn ut va vt wi wv |
| LIHEAP-ST-18 | State LIHEAP policy/operations manual (application procedures, matrices, vendor rules) | EXTRACTABLE | 35 | ak al ar az co ct de fl ga hi ia in ky la md me mi mn mo ms mt nd ne nh nj nv oh or pa sd tn ut va vt wi |
| LIHEAP-ST-03 | Categorical eligibility policy and automatic enrollment (1.4-1.6) | REVIEW | 30 | al ar co dc de ia in ky la mn mo ms nc nd ne nh nm nv oh ok or pa ri sc tn ut va vt wa wy |
| LIHEAP-ST-09 | Heating/cooling benefit matrix (plan attachment) | REVIEW | 13 | ca dc id il ma nc nm ok ri sc tx wa wy |
| LIHEAP-ST-18 | State LIHEAP policy/operations manual (application procedures, matrices, vendor rules) | REVIEW | 13 | ca dc id il ma nc nm ok ri sc tx wa wy |
| LIHEAP-ST-18 | State LIHEAP policy/operations manual (application procedures, matrices, vendor rules) | OUTREACH | 1 | ny |

## What would close each class

- **LIHEAP-F-USC**: 42 U.S.C. chapter 94 subchapter II: no section is in any statute scope (128 files checked). One uscode.house.gov USLM run over title 42 sections 8621 to 8630; the federal queue row (`needs_review`) already lists the ACF statute-and-regulations page as the lead.
- **LIHEAP-F-CFR96**: 45 CFR 96 subpart H: `extract-ecfr --only-title 45 --only-part 96` (the adapter's compression fix from 2026-09-11 is required); subpart H is ten sections.
- **LIHEAP-F-ANN**: HHS poverty guidelines (Federal Register notice) and the ACF LIHEAP-IM state median income table: one `guidance` document each per year from aspe.hhs.gov and the OCS policy-guidance index.
- **LIHEAP-ST-05**: Countable income and household definition (51 states REVIEW): the plan records gross/net and the income types as check boxes; the PDF text layer prints both `Yes No` labels with no state. Re-extract the plans reading the AcroForm field values (the OLDC form is a fillable PDF) or take the state policy manual, which states the rule in prose. The same fix closes LIHEAP-ST-03 (30 states) and firms up ST-07/08.
- **LIHEAP-ST-09**: Benefit matrix: a plan attachment that the clearinghouse PDF does not include (the extracted text ends at the 'Plan Attachments' list). 37 states have a policy manual on the clearinghouse index that carries the matrix; 13 have none listed and need their agency site inventoried (CA, DC, ID, IL, MA, NC, NM, OK, RI, SC, TX, WA, WY).
- **LIHEAP-ST-18**: State LIHEAP policy or operations manual: the clearinghouse 'State LIHEAP Policy Manuals' links read on 2026-09-11 give 37 documents (PDF, HTML manuals, one adopted rule chapter each for CO, ME, MS); KS (KEESM 13000) and WV (Income Maintenance Manual chapter 26) are already in selected scopes; NY's manual is behind the OTDA block.
- **OUTREACH**: New York: otda.ny.gov JavaScript challenge (SSI batch 1, TANF/SNAP queues); the FY2026 plan itself came from the ACF clearinghouse and is PRESENT.

## Elements beyond PolicyEngine

PolicyEngine-US models 2 of 41 elements in full, 11 in part, and 28 not at all. The schema YAML lists every element; the ones PolicyEngine lacks entirely are:

- LIHEAP-F-USC-8621: 42 U.S.C. 8621: Findings and purpose
- LIHEAP-F-USC-8622: 42 U.S.C. 8622: Definitions (home energy, household, State, poverty level, SMI)
- LIHEAP-F-USC-8623: 42 U.S.C. 8623: Authorization of appropriations; leveraging and REACH set-asides
- LIHEAP-F-USC-8625: 42 U.S.C. 8625: Administration (Secretary's duties)
- LIHEAP-F-USC-8626: 42 U.S.C. 8626: Payments to States; carryover limits
- LIHEAP-F-USC-8627: 42 U.S.C. 8627: Withholding of funds
- LIHEAP-F-USC-8628: 42 U.S.C. 8628: Technical assistance and training
- LIHEAP-F-USC-8629: 42 U.S.C. 8629: Reports, data collection and evaluation
- LIHEAP-F-USC-8630: 42 U.S.C. 8630: Incentive program for leveraging non-federal resources
- LIHEAP-F-CFR96-96-80: 45 CFR 96.80: Scope of subpart H
- LIHEAP-F-CFR96-96-81: 45 CFR 96.81: Carryover and reallotment
- LIHEAP-F-CFR96-96-82: 45 CFR 96.82: Required report on households assisted
- LIHEAP-F-CFR96-96-83: 45 CFR 96.83: Increase in maximum amount that may be used for weatherization
- LIHEAP-F-CFR96-96-84: 45 CFR 96.84: Miscellaneous (income eligibility definitions, nominal payments, categorical eligibility)
- LIHEAP-F-CFR96-96-86: 45 CFR 96.86: Exemption from requirement for additional outreach and intake services
- LIHEAP-F-CFR96-96-87: 45 CFR 96.87: Leveraging incentive program
- LIHEAP-F-CFR96-96-88: 45 CFR 96.88: Administrative costs
- LIHEAP-F-CFR96-96-89: 45 CFR 96.89: Exemptions from requirements in the Human Services Reauthorization Act of 1994
- LIHEAP-F-GUID-MODELPLAN: LIHEAP Model Plan (OMB form) and ACF instructions; LIHEAP Action Transmittals / Information Memoranda
- LIHEAP-ST-02: Funding allocation by component, carryover, admin and Assurance 16 shares (1.2-1.3)
- LIHEAP-ST-04: SNAP nominal payment policy and amount (1.7)
- LIHEAP-ST-07: Heating: additional eligibility rules and priority for vulnerable households (2.2-2.4)
- LIHEAP-ST-10: Cooling: threshold, eligibility, benefit levels (section 3)
- LIHEAP-ST-13: Weatherization component rules (section 5)
- LIHEAP-ST-14: Outreach, coordination, agency designation, energy-supplier agreements (6-9)
- LIHEAP-ST-15: Fair hearings (12)
- LIHEAP-ST-16: Assurance 16 services, leveraging, training, performance measures (13-16)
- LIHEAP-ST-17: Monitoring, audit and program integrity (10, 17)

Modeled only in part:

- LIHEAP-F-USC-8624: 42 U.S.C. 8624: Applications and requirements: allotment uses, the 16 assurances incl. income eligibility ceiling (150% poverty / 60% SMI, floor 110% poverty), outreach, priority to highest need, hearings, plan contents (2605(c))
- LIHEAP-F-CFR96-96-85: 45 CFR 96.85: Income eligibility (poverty guidelines and SMI; household definition)
- LIHEAP-ST-01: Program components operated and dates of operation (plan section 1.1)
- LIHEAP-ST-03: Categorical eligibility policy and automatic enrollment (1.4-1.6)
- LIHEAP-ST-05: Countable income (gross/net, income types) and household definition (1.8-1.12)
- LIHEAP-ST-06: Heating: income eligibility threshold by household size (2.1)
- LIHEAP-ST-08: Heating: benefit determination variables, minimum and maximum benefit (2.5-2.6)
- LIHEAP-ST-09: Heating/cooling benefit matrix (plan attachment)
- LIHEAP-ST-11: Crisis: threshold, crisis definition, life-threatening definition, response times (4.1-4.5)
- LIHEAP-ST-12: Crisis: additional eligibility and benefit levels / maximum crisis benefit (4.6-4.x)
- LIHEAP-ST-18: State LIHEAP policy/operations manual (application procedures, matrices, vendor rules)

rulespec-us encodes 0 of the elements (paths in the schema's `rulespec_cross_check`).

## Where the schema is uncertain

The check-box problem is the main one: PRESENT for ST-01/07/08/11/12 rests on the narrative
fields and parsed figures, not on the yes/no answers (asset test, renters, subsidized housing, priority
groups), so an encoder must still read the PDF for those. Sections 18 to 20 (certifications, assurances)
are not elements. Whether the plan or the policy manual is the rulebook for benefit determination
differs by state: where the plan says 'see attached matrix' the manual is the only carrier. Tribal and
territory plans (AS, GU, MP, PR extracted) are outside the 50+DC matrix.

## Searches run and timing

- Statute scopes: every `us/statute/*.jsonl` (128 files) scanned for citation paths under 42/1383*, 42/1395*, 42/1396a, 42/1396d, 42/1396u-3, 42/862[1-9], 42/8630; regulation scopes for 42/406, 42/407, 42/408, 42/423, 45/96; the selector JSON for scope membership.
- POMS, IOM and eCFR inventories: the run notes' index tables (2026-09-10-ssi-poms-si, 2026-09-10-medicare-cms-iom-100-01/-100-24, 2026-09-11-medicare-cms-iom-100-02-100-04, 2026-09-11-federal-cfr-followon-parts).
- State rows: the queue rows in `manifests/*-agent-queue.yaml`, then targeted body searches in each selected scope (regular expressions over heading and body; the cited row's body was opened for every PRESENT cell and re-opened by `verify_matrices.py`).
- PolicyEngine: `policyengine_us/parameters/gov/{ssa/ssi,hhs/liheap,hhs/medicare}` and `gov/states/*` walked 2026-09-11/12; rulespec-us and rulespec-us-{ca,co,ny} grepped for the statute, POMS, CMS and state program paths on 2026-09-12.
- Timing: a first attempt on 2026-09-11 (18:05 to 18:13 EDT) drafted the builder and stopped; this run 2026-09-12 08:37 to about 09:20 EDT, including three build-verify cycles (each build about 60 s, each verify about 60 s) and the manual re-grading of the state rows after reading the evidence dumps.
