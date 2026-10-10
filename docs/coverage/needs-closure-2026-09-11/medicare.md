# Medicare (federal Parts A, B, D and the state Medicare Savings Programs): needs-driven closure check

Corpus as selected on 2026-09-11 (draft union selector plus the three 2026-09-11 federal scopes); checked 2026-09-12. Schema: `medicare-schema.yaml` (68 elements: 61 federal, 7 state). Matrix: `medicare-matrix.csv` (3536 cells = 52 jurisdictions x 68 elements, one row each). Builder: `build_ssi_liheap_medicare_matrices.py`; verifier: `verify_matrices.py` (re-opens every PRESENT cell: 0 failures).

## Method

The schema takes the eligibility, enrollment, premium and cost-sharing sections of 42 U.S.C.
subchapter XVIII (426, 426-1, 1395c to 1395e, 1395i-2, 1395i-2a, 1395k, 1395l, 1395o to 1395s, 1395v,
1395w-21, 1395w-22, 1395w-101, 1395w-102, 1395w-113, 1395w-114) plus the Medicaid sections that define
the MSP groups (1396a(a)(10)(E), 1396d(p), 1396u-3); 42 CFR 406, 407, 408 and the three 423 subparts that
carry Part D eligibility, premiums and the low-income subsidy; 42 CFR 435 as used by MSP determinations;
one element per chapter of IOM Pub 100-01 and 100-24 and one per publication for 100-02 and 100-04;
the four IOM publications that carry Part D, Part C, NCD and MSP material and were not taken; six POMS
HI subchapters; the four annual CMS figure families; the cms.gov eligibility page; and seven state
elements: MSP coverage groups, income standards, resource test, income methodology, buy-in coverage
group (from Pub 100-24), QMB cost-sharing payment policy, and the current-year standards chart.

State MSP rules were searched in the selected Medicaid eligibility scope of each state (41 from the
2026-09-10 Medicaid run, FL/ID/IL/MI/WV/WY/OR by pointer). The scan is keyword-based but strict: a row
counts for MED-ST-1 only if an MSP group name (QMB, SLMB, QI, QDWI, Medicare Savings Program, buy-in) is
in its heading or appears three or more times in its body, after dropping tables of contents,
glossaries, change logs, bulletins and Q&A pages; MED-ST-2/3/4/6/7 require the qualifying text (an
FPL percentage, a resource limit or no-resource-test statement, a disregard, a cost-sharing statement,
a 2025/2026-dated dollar figure) within 250 characters of the group term, and the matched sentence is
written into the evidence note so the reader can judge it without opening the row. Every state-level
PRESENT snippet was then read by the analyst; eight cells where the first hit was wrong (LA and UT income
rows, IL/MS/RI non-MSP disregards, NC's Medicaid deductible, MI's code table) or a better carrier existed
(IN disregards) are corrected through the `MED_OVERRIDE` table in the builder, so the correction is
reproducible.

## Cells by status

| status | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cells | 1311 | 2132 | 7 | 18 | 68 | 3536 |

Federal elements are checked once and inherited by the 51 states (`evidence_note` = `inherited from federal`); the federal row alone: PRESENT 20, EXTRACTABLE 41, ABSENT 7. State-level cells (51 x 7): PRESENT 271, OUTREACH 18, REVIEW 68.

## Federal roll-up by document family

| federal family | elements | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| statute (US Code Title 42 ch. 7 subch. XVIII / XIX) | 24 | 3 | 21 | 0 | 0 | 0 |
| regulation (eCFR) | 7 | 1 | 6 | 0 | 0 | 0 |
| agency manual (CMS IOM) | 19 | 15 | 4 | 0 | 0 | 0 |
| agency manual (SSA POMS part HI) | 6 | 0 | 6 | 0 | 0 | 0 |
| annual notice (Federal Register / CMS) | 4 | 0 | 4 | 0 | 0 | 0 |
| agency guidance (cms.gov) | 1 | 1 | 0 | 0 | 0 | 0 |

## Per-jurisdiction roll-up (state-level elements)

| jurisdiction | state elements | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | closure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| us-ak | 7 | 7 | 0 | 0 | 0 | 0 | closed |
| us-al | 7 | 1 | 0 | 0 | 6 | 0 | 6 open |
| us-ar | 7 | 7 | 0 | 0 | 0 | 0 | closed |
| us-az | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-ca | 7 | 1 | 0 | 0 | 6 | 0 | 6 open |
| us-co | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-ct | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-dc | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-de | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-fl | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-ga | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-hi | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-ia | 7 | 7 | 0 | 0 | 0 | 0 | closed |
| us-id | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-il | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-in | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-ks | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-ky | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-la | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-ma | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-md | 7 | 7 | 0 | 0 | 0 | 0 | closed |
| us-me | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-mi | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-mn | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-mo | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-ms | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-mt | 7 | 7 | 0 | 0 | 0 | 0 | closed |
| us-nc | 7 | 4 | 0 | 0 | 0 | 3 | 3 open |
| us-nd | 7 | 7 | 0 | 0 | 0 | 0 | closed |
| us-ne | 7 | 1 | 0 | 0 | 6 | 0 | 6 open |
| us-nh | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-nj | 7 | 3 | 0 | 0 | 0 | 4 | 4 open |
| us-nm | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-nv | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-ny | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-oh | 7 | 4 | 0 | 0 | 0 | 3 | 3 open |
| us-ok | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-or | 7 | 1 | 0 | 0 | 0 | 6 | 6 open |
| us-pa | 7 | 7 | 0 | 0 | 0 | 0 | closed |
| us-ri | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-sc | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-sd | 7 | 5 | 0 | 0 | 0 | 2 | 2 open |
| us-tn | 7 | 7 | 0 | 0 | 0 | 0 | closed |
| us-tx | 7 | 7 | 0 | 0 | 0 | 0 | closed |
| us-ut | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-va | 7 | 7 | 0 | 0 | 0 | 0 | closed |
| us-vt | 7 | 4 | 0 | 0 | 0 | 3 | 3 open |
| us-wa | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-wi | 7 | 7 | 0 | 0 | 0 | 0 | closed |
| us-wv | 7 | 6 | 0 | 0 | 0 | 1 | 1 open |
| us-wy | 7 | 1 | 0 | 0 | 0 | 6 | 6 open |

## Top gaps by how many states share them

| element | name | status | states | which |
| --- | ---: | ---: | ---: | ---: |
| MED-ST-7 | Current-year MSP income/resource figures table (state standards chart) | REVIEW | 36 | az co ct dc de fl ga hi id in ks ky la ma me mi mn mo ms nc nh nj nm nv ny oh ok or ri sc sd ut vt wa wv wy |
| MED-ST-4 | MSP income methodology and state disregards ($20 general disregard, SSI methodology, state | REVIEW | 10 | il me ms nc nj oh or ri vt wy |
| MED-ST-3 | MSP resource test (whether applied; limits) | REVIEW | 9 | az dc de hi nj or sd vt wy |
| MED-ST-2 | MSP income standards (percent of FPL, state options above the federal floor) | REVIEW | 6 | ga id mn oh or wy |
| MED-ST-6 | State payment of Medicare cost-sharing for QMBs / balance-billing protection (state plan o | REVIEW | 5 | mi nc nj or wy |
| MED-ST-1 | MSP coverage groups defined in the state Medicaid rule/manual (QMB, SLMB, QI, QDWI) | OUTREACH | 3 | al ca ne |
| MED-ST-2 | MSP income standards (percent of FPL, state options above the federal floor) | OUTREACH | 3 | al ca ne |
| MED-ST-3 | MSP resource test (whether applied; limits) | OUTREACH | 3 | al ca ne |
| MED-ST-4 | MSP income methodology and state disregards ($20 general disregard, SSI methodology, state | OUTREACH | 3 | al ca ne |
| MED-ST-6 | State payment of Medicare cost-sharing for QMBs / balance-billing protection (state plan o | OUTREACH | 3 | al ca ne |
| MED-ST-7 | Current-year MSP income/resource figures table (state standards chart) | OUTREACH | 3 | al ca ne |
| MED-ST-1 | MSP coverage groups defined in the state Medicaid rule/manual (QMB, SLMB, QI, QDWI) | REVIEW | 2 | or wy |

## What would close each class

- **MED-F-USC**: 42 U.S.C. subchapter XVIII: only 426 is held. Seventeen sections from uscode.house.gov (same USLM adapter as the held Title 42 scopes) close the statute layer; 1396u-3 (QI) rides along.
- **MED-F-CFR**: 42 CFR 406, 407, 408 and 423 subparts B, D, P: none is in the corpus. Four `extract-ecfr` runs (423 is a large part; the subpart filter or a whole-part take both work).
- **MED-F-IOM**: IOM Pub 100-18 (Prescription Drug Benefit Manual, whole-manual PDF: needs a heading proof for the single file), Pub 100-16 (Managed Care, 15 chapters), Pub 100-03 and 100-05: the chapter-PDF generator transfers; each publication must be proven separately as the 100-02/100-04 run did.
- **MED-F-POMS**: POMS part HI (chapter list category 06): the SI extractor and index parser apply unchanged; HI 00801/00805/00815/01001/01101/03001 are the six subchapters an encoder needs.
- **MED-F-ANN**: Annual Part A/B premium and deductible notices (CMS-8xxx-N in the Federal Register), the Part D parameters announcement, the LIS/MSP resource memo and the HHS poverty guidelines: one `guidance` document per year each.
- **MED-ST-7**: Current-year MSP standards chart (26 states REVIEW): the manual states the percentages but the dollar table is a separate annual standards document (for example CT program standards, KY MS 4455 scale, MO Appendix J is held but undated for MSP, NH MAM 601 tables). Take the standards document as a `guidance` scope per state per year.
- **MED-ST-2/3**: GA, ID, MN, OH state the income limit by reference (to 1396d(p) or a 'QMB income limit'); AZ, DC, DE, HI, NJ, SD, VT do not state the resource rule near the group term. These need a reader to open the coverage-group rule, or the standards chart above.
- **OUTREACH/REVIEW**: AL (medicaid.alabama.gov TLS timeout), CA (DHCS Imperva 403), NE (rules.nebraska.gov 403 on 2026-09-11): agency outreach. OR: OAR 461 / 410-200-0435 region on OARD (HTTP 200). WY: EOM on Google Sites needs a rendering fetch.

## Elements beyond PolicyEngine

PolicyEngine-US models 15 of 68 elements in full, 15 in part, and 38 not at all. The schema YAML lists every element; the ones PolicyEngine lacks entirely are:

- MED-F-USC-426-1: 42 U.S.C. 426-1: End stage renal disease program entitlement
- MED-F-USC-1395c: 42 U.S.C. 1395c: Description of Part A program
- MED-F-USC-1395d: 42 U.S.C. 1395d: Scope of Part A benefits (inpatient, SNF, home health, hospice)
- MED-F-USC-1395i-2a: 42 U.S.C. 1395i-2a: Part A for qualified disabled and working individuals (QDWI premium)
- MED-F-USC-1395k: 42 U.S.C. 1395k: Scope of Part B benefits
- MED-F-USC-1395p: 42 U.S.C. 1395p: Part B enrollment periods (IEP, GEP, SEPs)
- MED-F-USC-1395q: 42 U.S.C. 1395q: Part B coverage period
- MED-F-USC-1395s: 42 U.S.C. 1395s: Payment of Part B premiums
- MED-F-USC-1395v: 42 U.S.C. 1395v: State buy-in agreements
- MED-F-USC-1395w-21: 42 U.S.C. 1395w-21: Part C eligibility, election and enrollment
- MED-F-USC-1395w-22: 42 U.S.C. 1395w-22: Part C benefits and beneficiary protections
- MED-F-USC-1395w-101: 42 U.S.C. 1395w-101: Part D eligibility, enrollment and information
- MED-F-USC-1395w-102: 42 U.S.C. 1395w-102: Part D prescription drug benefit (deductible, cost-sharing, out-of-pocket cap)
- MED-F-USC-1395w-114: 42 U.S.C. 1395w-114: Part D premium and cost-sharing subsidies for low-income individuals (LIS / Extra Help)
- MED-F-CFR-423-B: 42 CFR 423 subpart B: Part D eligibility, enrollment and disenrollment
- MED-F-CFR-423-P: 42 CFR 423 subpart P: premium and cost-sharing subsidies for low-income individuals
- MED-F-IOM-100-01-1: IOM Pub 100-01 ch.1: General program benefits and administration
- MED-F-IOM-100-01-4: IOM Pub 100-01 ch.4: Physician certification and recertification
- MED-F-IOM-100-01-5: IOM Pub 100-01 ch.5: Definitions
- MED-F-IOM-100-01-6: IOM Pub 100-01 ch.6: Disclosure of information
- MED-F-IOM-100-01-7: IOM Pub 100-01 ch.7: Contractor responsibilities
- MED-F-IOM-100-24-2: IOM Pub 100-24 ch.2: Data exchange processes
- MED-F-IOM-100-24-3: IOM Pub 100-24 ch.3: Data exchange
- MED-F-IOM-100-24-4: IOM Pub 100-24 ch.4: Code descriptions
- MED-F-IOM-100-24-5: IOM Pub 100-24 ch.5: Premium billing
- MED-F-IOM-100-24-6: IOM Pub 100-24 ch.6: Problem cases and resources
- MED-F-IOM-100-02: IOM Pub 100-02 Medicare Benefit Policy Manual (17 chapters: covered services, durations, exclusions)
- MED-F-IOM-100-04: IOM Pub 100-04 Medicare Claims Processing Manual (39 chapters incl. ch.30 financial liability, ch.28 Medigap/Medicaid coordination)
- MED-F-IOM-100-18: IOM Pub 100-18 Medicare Prescription Drug Benefit Manual (Part D eligibility, enrollment, LIS)
- MED-F-IOM-100-16: IOM Pub 100-16 Medicare Managed Care Manual (Part C eligibility, enrollment, benefits)
- MED-F-IOM-100-03: IOM Pub 100-03 National Coverage Determinations Manual
- MED-F-IOM-100-05: IOM Pub 100-05 Medicare Secondary Payer Manual
- MED-F-POMS-HI-00801: POMS HI 00801: Hospital insurance entitlement (age, disability, ESRD)
- MED-F-POMS-HI-00805: POMS HI 00805: Supplementary medical insurance enrollment
- MED-F-POMS-HI-00815: POMS HI 00815: State buy-in
- MED-F-POMS-HI-01001: POMS HI 01001: Premium billing and collection (Part A/B premiums, penalties)
- MED-F-POMS-HI-03001: POMS HI 03001-03050: Medicare Part D Extra Help (LIS) eligibility, income and resources
- MED-ST-5: State buy-in coverage groups (Part B / Part A buy-in status per state)

Modeled only in part:

- MED-F-USC-1395l: 42 U.S.C. 1395l: Part B payment: deductible, coinsurance
- MED-F-USC-1396u-3: 42 U.S.C. 1396u-3: Qualifying individuals (QI) program and federal allotments
- MED-F-CFR-406: 42 CFR 406: Hospital insurance eligibility and entitlement (subparts A-D)
- MED-F-CFR-407: 42 CFR 407: Supplementary medical insurance enrollment and entitlement (subparts A-D incl. state buy-in)
- MED-F-CFR-423-D: 42 CFR 423 subpart D: Part D premiums, cost-sharing, IRMAA (423.286)
- MED-F-CFR-435-MSP: 42 CFR 435 provisions used by MSP determinations (435.4 definitions, 435.601/435.725 financial methodologies, 435.914-.916 redeterminations)
- MED-F-IOM-100-01-2: IOM Pub 100-01 ch.2: Hospital insurance and SMI entitlement, enrollment periods, state buy-in
- MED-F-IOM-100-01-3: IOM Pub 100-01 ch.3: Deductibles, coinsurance amounts and payment limitations (Part B premium 20.6)
- MED-F-IOM-100-24-1: IOM Pub 100-24 ch.1: State payment of Medicare premiums, program overview and policy (buy-in groups, QMB Part A)
- MED-F-POMS-HI-01101: POMS HI 01101: Income-related monthly adjustment amount (Part B and D)
- MED-F-ANN-D: Annual Part D base beneficiary premium, IRMAA and standard benefit parameters (CMS annual release)
- MED-F-ANN-LIS: Annual Part D LIS resource limits and MSP resource standards (CMS annual LIS/MSP resource memo)
- MED-ST-4: MSP income methodology and state disregards ($20 general disregard, SSI methodology, state-specific disregards)
- MED-ST-6: State payment of Medicare cost-sharing for QMBs / balance-billing protection (state plan option)
- MED-ST-7: Current-year MSP income/resource figures table (state standards chart)

rulespec-us encodes 6 of the elements (paths in the schema's `rulespec_cross_check`).

## Where the schema is uncertain

Subchapter XVIII was reduced to household-facing sections; payment-system sections (1395ww and
similar) are out of scope. Part C is represented by two statute sections and Pub 100-16 only. The state
scan finds the carrier row and quotes it, but PRESENT for MED-ST-3 often means the manual states that
a resource test exists (or does not) with the figure elsewhere; MED-ST-7 PRESENT means a dated dollar
figure sits next to a group term, which a few pages satisfy with a related figure (NC MA-3315 quotes the
2026 IRMAA threshold). State MSP expansions above the federal floor (CT 211% FPL, DC 300%, ME 185%,
MA 210%, VT 202%, WA 110% QMB) are visible in the evidence and are exactly the state-set values
PolicyEngine's single federal parameter set does not carry.

## Searches run and timing

- Statute scopes: every `us/statute/*.jsonl` (128 files) scanned for citation paths under 42/1383*, 42/1395*, 42/1396a, 42/1396d, 42/1396u-3, 42/862[1-9], 42/8630; regulation scopes for 42/406, 42/407, 42/408, 42/423, 45/96; the selector JSON for scope membership.
- POMS, IOM and eCFR inventories: the run notes' index tables (2026-09-10-ssi-poms-si, 2026-09-10-medicare-cms-iom-100-01/-100-24, 2026-09-11-medicare-cms-iom-100-02-100-04, 2026-09-11-federal-cfr-followon-parts).
- State rows: the queue rows in `manifests/*-agent-queue.yaml`, then targeted body searches in each selected scope (regular expressions over heading and body; the cited row's body was opened for every PRESENT cell and re-opened by `verify_matrices.py`).
- PolicyEngine: `policyengine_us/parameters/gov/{ssa/ssi,hhs/liheap,hhs/medicare}` and `gov/states/*` walked 2026-09-11/12; rulespec-us and rulespec-us-{ca,co,ny} grepped for the statute, POMS, CMS and state program paths on 2026-09-12.
- Timing: a first attempt on 2026-09-11 (18:05 to 18:13 EDT) drafted the builder and stopped; this run 2026-09-12 08:37 to about 09:20 EDT, including three build-verify cycles (each build about 60 s, each verify about 60 s) and the manual re-grading of the state rows after reading the evidence dumps.
