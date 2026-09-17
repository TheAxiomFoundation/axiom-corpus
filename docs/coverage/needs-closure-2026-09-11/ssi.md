# SSI (federal SSI and state supplements): needs-driven closure check

Corpus as selected on 2026-09-11 (draft union selector plus the three 2026-09-11 federal scopes); checked 2026-09-12. Schema: `ssi-schema.yaml` (131 elements: 125 federal, 6 state). Matrix: `ssi-matrix.csv` (6812 cells = 52 jurisdictions x 131 elements, one row each). Builder: `build_ssi_liheap_medicare_matrices.py`; verifier: `verify_matrices.py` (re-opens every PRESENT cell: 0 failures).

## Method

The schema follows the law's own structure, in order of authority: one element per section of
42 U.S.C. 1381 to 1383f (20 sections), one per subpart of 20 CFR 416 (22 subparts, A to V, plus the
Subpart K appendix), one per POMS SI subchapter as listed on SSA's own part SI chapter list on
2026-09-10 (every subchapter, taken or not), three annual-figure families (the COLA notice with the
federal benefit rate, the student earned income exclusion and the SGA amounts), and six state-level
elements for the supplement: whether the state runs an optional program and who administers it
(SI 01415.010), the state authority, the eligibility categories and living arrangements, the payment
amounts, the state income and resource methodology, and, for federally administered programs, SSA's
living-arrangement codes and payment levels (SI 01415.058). A POMS subchapter is treated as one
element because the encoder reads the subchapter as a unit; the schema file records the number of
sections behind each. Statute elements are whole sections; the held scope carries subsection rows.

Selected scopes read: `us/statute/2026-06-20-ssi-title-xvi-...` (226 rows, 1381 to 1382j),
`us/regulation/2026-09-11-title-20-part-416` (622 rows, complete), `us/manual/2026-09-10-ssi-poms-si`
(11,028 rows, 23 subchapters), `us/guidance/2026-07-05-ssa-cola-2026`,
`us/guidance/2026-05-17-ssa-automatic-determinations-2026`, and the state-supplement scopes named in
`manifests/ssi-agent-queue.yaml` (27 extracted, 22 done by pointer to older scopes). For every state
the cited row was opened and its heading and body checked; the paths are in the CSV. Status rules are
the brief's: PRESENT only with a selected scope and a citation path whose body carries the fact
(`verify_matrices.py` re-opens every PRESENT cell and checks selector membership); EXTRACTABLE when the
publisher lists the family and the queue or run note shows it was not taken; ABSENT with an `n/a`
note where the law gives the jurisdiction nothing to set; OUTREACH for the two publisher blocks;
REVIEW where the scope is present but the row that would carry the fact could not be identified or
carries the method without the figure.

## Cells by status

| status | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cells | 3291 | 3386 | 83 | 8 | 44 | 6812 |

Federal elements are checked once and inherited by the 51 states (`evidence_note` = `inherited from federal`); the federal row alone: PRESENT 60, EXTRACTABLE 65, ABSENT 6. State-level cells (51 x 6): PRESENT 171, EXTRACTABLE 6, ABSENT 77, OUTREACH 8, REVIEW 44.

## Federal roll-up by document family

| federal family | elements | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| statute (US Code Title 42 ch. 7 subch. XVI) | 20 | 12 | 8 | 0 | 0 | 0 |
| regulation (eCFR) | 23 | 22 | 1 | 0 | 0 | 0 |
| agency manual (SSA POMS part SI) | 79 | 23 | 56 | 0 | 0 | 0 |
| annual notice (Federal Register / SSA OACT) | 3 | 3 | 0 | 0 | 0 | 0 |

## Per-jurisdiction roll-up (state-level elements)

| jurisdiction | state elements | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | closure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| us-ak | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-al | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-ar | 6 | 1 | 0 | 5 | 0 | 0 | closed |
| us-az | 6 | 1 | 0 | 5 | 0 | 0 | closed |
| us-ca | 6 | 5 | 0 | 1 | 0 | 0 | closed |
| us-co | 6 | 5 | 0 | 1 | 0 | 0 | closed |
| us-ct | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-dc | 6 | 4 | 0 | 0 | 0 | 2 | 2 open |
| us-de | 6 | 4 | 0 | 0 | 0 | 2 | 2 open |
| us-fl | 6 | 5 | 0 | 1 | 0 | 0 | closed |
| us-ga | 6 | 3 | 0 | 2 | 0 | 1 | 1 open |
| us-hi | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-ia | 6 | 4 | 0 | 0 | 0 | 2 | 2 open |
| us-id | 6 | 5 | 0 | 1 | 0 | 0 | closed |
| us-il | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-in | 6 | 3 | 0 | 2 | 0 | 1 | 1 open |
| us-ks | 6 | 2 | 0 | 2 | 0 | 2 | 2 open |
| us-ky | 6 | 5 | 0 | 1 | 0 | 0 | closed |
| us-la | 6 | 3 | 0 | 2 | 0 | 1 | 1 open |
| us-ma | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-md | 6 | 5 | 0 | 1 | 0 | 0 | closed |
| us-me | 6 | 5 | 0 | 1 | 0 | 0 | closed |
| us-mi | 6 | 4 | 0 | 0 | 0 | 2 | 2 open |
| us-mn | 6 | 3 | 0 | 1 | 0 | 2 | 2 open |
| us-mo | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-ms | 6 | 1 | 0 | 5 | 0 | 0 | closed |
| us-mt | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-nc | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-nd | 6 | 1 | 0 | 5 | 0 | 0 | closed |
| us-ne | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-nh | 6 | 3 | 0 | 1 | 0 | 2 | 2 open |
| us-nj | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-nm | 6 | 5 | 0 | 1 | 0 | 0 | closed |
| us-nv | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-ny | 6 | 1 | 0 | 1 | 4 | 0 | 4 open |
| us-oh | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-ok | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-or | 6 | 1 | 3 | 1 | 0 | 1 | 4 open |
| us-pa | 6 | 4 | 0 | 0 | 0 | 2 | 2 open |
| us-ri | 6 | 4 | 0 | 0 | 0 | 2 | 2 open |
| us-sc | 6 | 3 | 0 | 1 | 0 | 2 | 2 open |
| us-sd | 6 | 3 | 0 | 1 | 0 | 2 | 2 open |
| us-tn | 6 | 1 | 0 | 5 | 0 | 0 | closed |
| us-tx | 6 | 3 | 0 | 2 | 0 | 1 | 1 open |
| us-ut | 6 | 3 | 1 | 2 | 0 | 0 | 1 open |
| us-va | 6 | 2 | 1 | 1 | 0 | 2 | 3 open |
| us-vt | 6 | 4 | 0 | 1 | 0 | 1 | 1 open |
| us-wa | 6 | 4 | 0 | 2 | 0 | 0 | closed |
| us-wi | 6 | 3 | 1 | 2 | 0 | 0 | 1 open |
| us-wv | 6 | 1 | 0 | 5 | 0 | 0 | closed |
| us-wy | 6 | 1 | 0 | 1 | 4 | 0 | 4 open |

## Top gaps by how many states share them

| element | name | status | states | which |
| --- | ---: | ---: | ---: | ---: |
| SSI-ST-2 | State authority establishing the supplement (statute or adopted rule) | REVIEW | 24 | ak ct dc de ga hi ia il in ks la mi mn mo mt nc nh nj nv pa ri sc tx vt |
| SSI-ST-4 | State supplement payment standards / amounts by living arrangement (current year) | REVIEW | 10 | ks ma mn ne nh oh ok sc sd va |
| SSI-ST-5 | State income and resource methodology for a state-administered supplement (disregards, lim | REVIEW | 9 | al dc de ia mi pa ri sd va |
| SSI-ST-2 | State authority establishing the supplement (statute or adopted rule) | EXTRACTABLE | 4 | or ut va wi |
| SSI-ST-2 | State authority establishing the supplement (statute or adopted rule) | OUTREACH | 2 | ny wy |
| SSI-ST-3 | State eligibility categories and living-arrangement definitions for the supplement | OUTREACH | 2 | ny wy |
| SSI-ST-4 | State supplement payment standards / amounts by living arrangement (current year) | OUTREACH | 2 | ny wy |
| SSI-ST-5 | State income and resource methodology for a state-administered supplement (disregards, lim | OUTREACH | 2 | ny wy |
| SSI-ST-3 | State eligibility categories and living-arrangement definitions for the supplement | REVIEW | 1 | or |
| SSI-ST-4 | State supplement payment standards / amounts by living arrangement (current year) | EXTRACTABLE | 1 | or |
| SSI-ST-5 | State income and resource methodology for a state-administered supplement (disregards, lim | EXTRACTABLE | 1 | or |

## What would close each class

- **SSI-F-USC**: 42 U.S.C. 1383 to 1383f (procedures, overpayments, representative payees, penalties, Medicaid eligibility of SSI recipients, outreach): eight sections, same publisher and adapter as the held Title XVI scope (uscode.house.gov USLM); one `extract-uscode` run with the section list widened.
- **SSI-F-POMS**: POMS part SI: 56 subchapters listed by SSA and not taken (SI 006 application process, SI 00530 fugitive felons, SI 00870 PASS, SI 01150 transfers and trusts, SI 012 grandfathered provisions, SI 017 Medicaid, SI 018 SNAP, SI 020 payments except 02001/02005, SI 021 to 023 underpayments, overpayments, posteligibility, SI 029, SI 040 appeals). Widen `TAKEN_SUBCHAPTERS` in `scripts/build_ssi_poms_si_manifests.py`; the extractor and index are proven.
- **SSI-F-CFR416-APPK**: 20 CFR 416 Subpart K appendix: extend the eCFR adapter's `_appendix_citation_from_identifier` to subpart-scoped appendices and re-take with `--include-appendices` (run note 2026-09-11-federal-cfr-followon-parts).
- **SSI-ST-2**: State enabling statutes for 24 state-administered or shared programs (for example AS 47.25, Conn. Gen. Stat. 17b-600, D.C. Code 4-205, 305 ILCS 5/3, Minn. Stat. 256D, RSMo 208, G.S. 108A, RSA 167, Wis. Stat. 49.77): a state-statute family through the existing state-code adapters. rulespec-us already encodes Conn. Gen. Stat. 17b-600 and D.C. Code 4-205.49 from text that is not in the selected corpus, so these two are the first to take.
- **SSI-ST-4**: Payment standards that the rule text delegates to a chart or notice: OKDHS Appendix C-1 (OK), the DTA SSP standards chart behind 106 CMR 327.330 (MA), AAM 601 Table A (NH, a table image the HTML extractor dropped), the OhioMHAS RSS payment notice (OH), MPPM 103 net income limits (SC), the DARS AG rate broadcast (VA), the 469 NAC standard-of-need table (NE), the department-approved rate (SD), a current KHPA/KDHE SSPP amount (KS), and the DHS MSA revised sections 01/2026 (MN: already on disk as `us-mn/manual/2026-06-27-mn-dhs-msa-revised-sections-2026-01`, only unselected). Ten states; each is one small document.
- **SSI-ST-5**: State income and resource methodology where the program has its own: AK, AL (page not located), ID, IL, MA, MO, NC, NE, NM, OK, SC, KY, CO, CT, FL, ME are PRESENT; VA and SD need the rule page identified; the F/S states (DC, DE, IA, MI, PA, RI) need the state-administered part inventoried (the queue covered only the SSA-administered part).
- **SSI-ST-OR**: Oregon: OAR chapter 461 (OSIP eligibility 461-135, payment standard 461-155-0250, income deductions 461-160) on the Secretary of State OARD, which answered HTTP 200 on 2026-09-10; the OPEN notebook cites the rules by number only.
- **OUTREACH**: New York (otda.ny.gov JavaScript challenge) and Wyoming (ecom.wyo.gov Google-Sites embed): agency contact for a document copy, or a browser-rendered fetch under a recorded exception.

## Elements beyond PolicyEngine

PolicyEngine-US models 9 of 131 elements in full, 30 in part, and 92 not at all. The schema YAML lists every element; the ones PolicyEngine lacks entirely are:

- SSI-F-USC-1381: 42 U.S.C. 1381: Statement of purpose
- SSI-F-USC-1381a: 42 U.S.C. 1381a: Basic entitlement to benefits
- SSI-F-USC-1382d: 42 U.S.C. 1382d: Rehabilitation services for blind and disabled individuals
- SSI-F-USC-1382h: 42 U.S.C. 1382h: Continuing benefits and Medicaid for working recipients (1619(a)/(b))
- SSI-F-USC-1382i: 42 U.S.C. 1382i: Medical and social services for certain handicapped persons
- SSI-F-USC-1382j: 42 U.S.C. 1382j: Attribution of sponsor's income and resources to aliens
- SSI-F-USC-1383: 42 U.S.C. 1383: Procedure for payment of benefits: applications, representative payees, overpayments, redeterminations, PASS
- SSI-F-USC-1383a: 42 U.S.C. 1383a: Penalties for fraud
- SSI-F-USC-1383b: 42 U.S.C. 1383b: Administration
- SSI-F-USC-1383c: 42 U.S.C. 1383c: Eligibility for medical assistance of aged, blind, or disabled individuals (Medicaid link)
- SSI-F-USC-1383d: 42 U.S.C. 1383d: Outreach program for children
- SSI-F-USC-1383e: 42 U.S.C. 1383e: Annual report on program
- SSI-F-USC-1383f: 42 U.S.C. 1383f: Report on SSI eligibility / recipient counts
- SSI-F-CFR416-A: 20 CFR 416 Subpart A: Introduction, General Provisions and Definitions
- SSI-F-CFR416-C: 20 CFR 416 Subpart C: Filing of Applications
- SSI-F-CFR416-E: 20 CFR 416 Subpart E: Payment of Benefits, Overpayments, and Underpayments
- SSI-F-CFR416-F: 20 CFR 416 Subpart F: Representative Payment
- SSI-F-CFR416-G: 20 CFR 416 Subpart G: Reports Required
- SSI-F-CFR416-H: 20 CFR 416 Subpart H: Determination of Age
- SSI-F-CFR416-I: 20 CFR 416 Subpart I: Determining Disability and Blindness
- SSI-F-CFR416-J: 20 CFR 416 Subpart J: Determinations of Disability (state agency process)
- SSI-F-CFR416-M: 20 CFR 416 Subpart M: Suspensions and Terminations
- SSI-F-CFR416-N: 20 CFR 416 Subpart N: Determinations, Administrative Review Process, and Reopening
- SSI-F-CFR416-O: 20 CFR 416 Subpart O: Representation of Parties
- SSI-F-CFR416-Q: 20 CFR 416 Subpart Q: Referral to Other Agencies
- SSI-F-CFR416-S: 20 CFR 416 Subpart S: Interim Assistance Provisions
- SSI-F-CFR416-U: 20 CFR 416 Subpart U: Medicaid Eligibility Determinations
- SSI-F-CFR416-V: 20 CFR 416 Subpart V: Payments for Vocational Rehabilitation Services
- SSI-F-CFR416-APPK: 20 CFR 416 Appendix to Subpart K (income excluded under other federal laws)
- SSI-F-POMS-SI-00500: POMS SI 00500: Eligibility (chapter TOC)
- SSI-F-POMS-SI-00510: POMS SI 00510: Requirement to File for Other Program Benefits
- SSI-F-POMS-SI-00515: POMS SI 00515: SSA Access to Financial Institutions (AFI)
- SSI-F-POMS-SI-00529: POMS SI 00529: No Social Security Benefits for Prisoners Title XVI
- SSI-F-POMS-SI-00530: POMS SI 00530: Fugitive Felons and Parole and Probation Violators
- SSI-F-POMS-SI-00600: POMS SI 00600: The SSI Application Process (chapter TOC)
- SSI-F-POMS-SI-00601: POMS SI 00601: General Applications and Interviewing Policy
- SSI-F-POMS-SI-00602: POMS SI 00602: Abbreviated Application Process for Clear Technical Denials
- SSI-F-POMS-SI-00603: POMS SI 00603: The SSI Disability/Blindness Initial Claims Process
- SSI-F-POMS-SI-00604: POMS SI 00604: Completion of Form SSA-8000-BK
- SSI-F-POMS-SI-00605: POMS SI 00605: Use and Completion of Form SSA-8001-BK
- SSI-F-POMS-SI-00800: POMS SI 00800: Income (chapter TOC)
- SSI-F-POMS-SI-00832: POMS SI 00832: Unearned Income Anderson Case
- SSI-F-POMS-SI-00870: POMS SI 00870: Plans to Achieve Self-Support (PASS)
- SSI-F-POMS-SI-01100: POMS SI 01100: Resources (chapter TOC)
- SSI-F-POMS-SI-01150: POMS SI 01150: Other Resources Provisions (transfers, trusts)
- SSI-F-POMS-SI-01200: POMS SI 01200: Grandfathered Income and Resource Provisions (chapter TOC)
- SSI-F-POMS-SI-01210: POMS SI 01210: Special Blind Income Provision
- SSI-F-POMS-SI-01220: POMS SI 01220: Special Resource Provision
- SSI-F-POMS-SI-01300: POMS SI 01300: Deeming (chapter TOC)
- SSI-F-POMS-SI-01400: POMS SI 01400: State Supplementary Payments (chapter TOC)
- SSI-F-POMS-SI-01401: POMS SI 01401: Introduction to State Supplementation
- SSI-F-POMS-SI-01403: POMS SI 01403: Pass Along of Federal SSI COLA Increases
- SSI-F-POMS-SI-01405: POMS SI 01405: Federal and State Administrative Considerations
- SSI-F-POMS-SI-01410: POMS SI 01410: Federal Administration of State Supplementary Payments
- SSI-F-POMS-SI-01700: POMS SI 01700: Medicaid Eligibility (chapter TOC)
- SSI-F-POMS-SI-01715: POMS SI 01715: Medicaid and the SSI Program
- SSI-F-POMS-SI-01730: POMS SI 01730: SSA Determinations of Medicaid Eligibility (1634 states)
- SSI-F-POMS-SI-01800: POMS SI 01800: SNAP (chapter TOC)
- SSI-F-POMS-SI-01801: POMS SI 01801: Supplemental Nutrition Assistance Program
- SSI-F-POMS-SI-02000: POMS SI 02000: Benefits and Payments (chapter TOC)
- SSI-F-POMS-SI-02001: POMS SI 02001: Computation of Benefits - Introduction
- SSI-F-POMS-SI-02002: POMS SI 02002: Monitoring State Accounting for IAR Payments
- SSI-F-POMS-SI-02003: POMS SI 02003: Interim Assistance Payments
- SSI-F-POMS-SI-02004: POMS SI 02004: Direct Field Office Payments
- SSI-F-POMS-SI-02006: POMS SI 02006: Windfall Offset and Effect on Title XVI Payments
- SSI-F-POMS-SI-02007: POMS SI 02007: SSI Interim Benefits Payments
- SSI-F-POMS-SI-02009: POMS SI 02009: Computation of Payments for Months Prior to April 1982
- SSI-F-POMS-SI-02100: POMS SI 02100: Underpayments (chapter TOC)
- SSI-F-POMS-SI-02101: POMS SI 02101: Title XVI Underpayments
- SSI-F-POMS-SI-02200: POMS SI 02200: Overpayments (chapter TOC)
- SSI-F-POMS-SI-02201: POMS SI 02201: SSI Overpayments - Overview
- SSI-F-POMS-SI-02205: POMS SI 02205: SSI Overpayments - Sponsor/Alien Cases
- SSI-F-POMS-SI-02220: POMS SI 02220: Recovery Procedures for SSI Overpayments
- SSI-F-POMS-SI-02300: POMS SI 02300: Posteligibility Events (chapter TOC)
- SSI-F-POMS-SI-02301: POMS SI 02301: Posteligibility Changes
- SSI-F-POMS-SI-02302: POMS SI 02302: Continuing Benefits Under Sections 1619(a) and 1619(b)
- SSI-F-POMS-SI-02305: POMS SI 02305: Redeterminations of Eligibility and/or Payment Amount
- SSI-F-POMS-SI-02306: POMS SI 02306: Miscellaneous Posteligibility Issues
- SSI-F-POMS-SI-02309: POMS SI 02309: Critical Birthday and Insured Status Diaries
- SSI-F-POMS-SI-02310: POMS SI 02310: SSI Interfaces
- SSI-F-POMS-SI-02900: POMS SI 02900: State Financial Management (chapter TOC)
- SSI-F-POMS-SI-02901: POMS SI 02901: SSI Administrative Costs
- SSI-F-POMS-SI-04000: POMS SI 04000: Administrative Review, Appeals and Finality (chapter TOC)
- SSI-F-POMS-SI-04005: POMS SI 04005: Administrative Review (Appeals) Process - SSI
- SSI-F-POMS-SI-04010: POMS SI 04010: Initial Determinations - SSI
- SSI-F-POMS-SI-04020: POMS SI 04020: Reconsideration - SSI
- SSI-F-POMS-SI-04030: POMS SI 04030: ALJ Hearings - SSI
- SSI-F-POMS-SI-04040: POMS SI 04040: Appeals Council Review - SSI
- SSI-F-POMS-SI-04050: POMS SI 04050: Litigation - SSI
- SSI-F-POMS-SI-04060: POMS SI 04060: Expedited Appeals Process - SSI
- SSI-F-POMS-SI-04070: POMS SI 04070: Administrative Finality - SSI
- SSI-ST-2: State authority establishing the supplement (statute or adopted rule)

Modeled only in part:

- SSI-F-USC-1382b: 42 U.S.C. 1382b: Resources: definition, exclusions, transfers, trusts
- SSI-F-USC-1382c: 42 U.S.C. 1382c: Definitions: aged, blind, disabled, child, marriage, eligible spouse
- SSI-F-USC-1382e: 42 U.S.C. 1382e: Supplementary assistance by States (optional and mandatory supplementation, administration, pass-along)
- SSI-F-USC-1382g: 42 U.S.C. 1382g: Payments to institutions and residents (institutional rate)
- SSI-F-CFR416-B: 20 CFR 416 Subpart B: Eligibility
- SSI-F-CFR416-L: 20 CFR 416 Subpart L: Resources and Exclusions
- SSI-F-CFR416-P: 20 CFR 416 Subpart P: Residence and Citizenship
- SSI-F-CFR416-R: 20 CFR 416 Subpart R: Relationship (marriage, parent-child)
- SSI-F-CFR416-T: 20 CFR 416 Subpart T: State Supplementation Provisions; Agreement; Payments
- SSI-F-POMS-SI-00501: POMS SI 00501: Eligibility Under the SSI Provisions
- SSI-F-POMS-SI-00502: POMS SI 00502: SSI Alien Eligibility
- SSI-F-POMS-SI-00520: POMS SI 00520: Institutionalization
- SSI-F-POMS-SI-00810: POMS SI 00810: General - Income Rules for the SSI Program
- SSI-F-POMS-SI-00815: POMS SI 00815: What Is Not Income
- SSI-F-POMS-SI-00820: POMS SI 00820: Earned Income
- SSI-F-POMS-SI-00830: POMS SI 00830: Unearned Income
- SSI-F-POMS-SI-00835: POMS SI 00835: Living Arrangements and In-Kind Support and Maintenance
- SSI-F-POMS-SI-01110: POMS SI 01110: Resources, General
- SSI-F-POMS-SI-01120: POMS SI 01120: Identifying Resources
- SSI-F-POMS-SI-01130: POMS SI 01130: Resources Exclusions
- SSI-F-POMS-SI-01140: POMS SI 01140: Types of Countable Resources
- SSI-F-POMS-SI-01330: POMS SI 01330: Deeming of Resources
- SSI-F-POMS-SI-01415: POMS SI 01415: Elements of State Supplementary Payments (state tables, payment levels)
- SSI-F-POMS-SI-02005: POMS SI 02005: Computation of Benefits - SSI
- SSI-F-ANN-SGA: Substantial gainful activity amounts for the current year
- SSI-ST-1: State supplementation program existence and administration (mandatory/optional; federal, state or shared administration)
- SSI-ST-3: State eligibility categories and living-arrangement definitions for the supplement
- SSI-ST-4: State supplement payment standards / amounts by living arrangement (current year)
- SSI-ST-5: State income and resource methodology for a state-administered supplement (disregards, limits)
- SSI-ST-6: Federally administered optional supplement: SSA living-arrangement codes and payment levels

rulespec-us encodes 12 of the elements (paths in the schema's `rulespec_cross_check`).

## Where the schema is uncertain

Whether a POMS subchapter is the right grain (an encoder may want section-level elements for
SI 00830 with 183 sections); whether the mandatory pass-along supplement deserves its own state element
(it is folded into SSI-ST-1); the reading that a flat institutional add-on (GA, IN, LA, TX, UT, WA, WI)
has no state income methodology (SSI-ST-5 marked n/a) is the analyst's; and for the F/S states the
state-administered part of the program is outside what the queue inventoried, so SSI-ST-5 is REVIEW
rather than ABSENT.

## Searches run and timing

- Statute scopes: every `us/statute/*.jsonl` (128 files) scanned for citation paths under 42/1383*, 42/1395*, 42/1396a, 42/1396d, 42/1396u-3, 42/862[1-9], 42/8630; regulation scopes for 42/406, 42/407, 42/408, 42/423, 45/96; the selector JSON for scope membership.
- POMS, IOM and eCFR inventories: the run notes' index tables (2026-09-10-ssi-poms-si, 2026-09-10-medicare-cms-iom-100-01/-100-24, 2026-09-11-medicare-cms-iom-100-02-100-04, 2026-09-11-federal-cfr-followon-parts).
- State rows: the queue rows in `manifests/*-agent-queue.yaml`, then targeted body searches in each selected scope (regular expressions over heading and body; the cited row's body was opened for every PRESENT cell and re-opened by `verify_matrices.py`).
- PolicyEngine: `policyengine_us/parameters/gov/{ssa/ssi,hhs/liheap,hhs/medicare}` and `gov/states/*` walked 2026-09-11/12; rulespec-us and rulespec-us-{ca,co,ny} grepped for the statute, POMS, CMS and state program paths on 2026-09-12.
- Timing: a first attempt on 2026-09-11 (18:05 to 18:13 EDT) drafted the builder and stopped; this run 2026-09-12 08:37 to about 09:20 EDT, including three build-verify cycles (each build about 60 s, each verify about 60 s) and the manual re-grading of the state rows after reading the evidence dumps.
