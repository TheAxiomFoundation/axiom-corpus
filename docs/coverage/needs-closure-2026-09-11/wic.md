# WIC: needs-driven closure check (2026-09-11 corpus)

Corpus as selected on 2026-09-11 (draft union selector plus the twelve SNAP superseding scopes on disk); checked 2026-09-12. Schema: `wic-schema.yaml` (114 elements: 83 federal, 31 state). Matrix: `wic-matrix.csv` (5897 cells = 52 jurisdictions x 114 elements, one row each). Builder: `check_snap_wic.py` (read-only over `data/corpus`; 193.7 s, 128 scopes and 63884 provision rows loaded for both programs); PRESENT evidence: `wic-hits.jsonl`.

## Method

The schema follows the law's own structure. (1) Federal statute: the 19 subsections of 42 U.S.C.
1786 (a) to (s), section 17 of the Child Nutrition Act, each a distinct rule-carrying unit (eligibility
in (d), state plan in (f), funds and rebates in (h), FMNP in (m), vendor disqualification in (n)-(o)).
(2) Federal regulation: the 30 sections of 7 CFR 246 as listed by the eCFR structure API (current
edition, read 2026-09-12) plus 25 participant-facing paragraph elements of 246.7 (residency,
categories, income standard and determination, adjunctive eligibility, nutritional risk, processing
standards, certification periods, priority, rights, notices, dual participation, VOC, institutions,
remote certification), 246.10 (food lists, tailoring, medical documentation, food packages I to VII
and CVB), 246.12 (issuance, vendors, participant sanctions), 246.4(a), 246.2, 246.9, 246.11 and
246.16a. (3) FNS/FNA guidance: the income eligibility guidelines, the CVB memo, the food package
memos, the nutrition-risk criteria list, the pre-FY 2025 memo family, the Federal Register notice
family, infant formula rebate guidance and state-plan guidance. (4) State rulebook: 31 elements the
state's WIC policy manual, state plan or administrative rule must carry (income standard and
guidelines table, income determination, adjunctive programs, categories, nutritional risk, bloodwork,
certification periods, residency and physical presence, documentation, temporary certification,
priority, processing standards, food packages and CVB, food list, medical documentation,
breastfeeding categories, dual participation and VOC, participant sanctions, notices, fair hearings,
nutrition education, vendors, issuance, local agencies, migrant and homeless, FMNP, civil rights,
caseload, state plan, state rule chapter).

Selected scopes: `us/guidance/2026-09-10-wic-fns-guidance` (11 documents) and the paragraph-granular
7 CFR 246 in `us/regulation/2026-07-13-recovery-r2026-07-17-dedup` at the federal level; the 21 state
scopes `us-xx/manual/2026-09-10-wic-state-policy-manual` (one root plus one body provision per policy
PDF). Federal statute and 246.7 paragraph elements are checked by citation path; 246.4, 246.10 and
246.12 have no paragraph rows, so their paragraph elements are checked by keyword regex over the
section body; guidance by regex over the selected guidance bodies; state elements by regex over every
policy body of the state's WIC scope, taking the policy with the most matches. Every regex is in
`wic-schema.yaml`; every PRESENT match with its snippet is in `wic-hits.jsonl`.

Status rules: PRESENT only with a cited provision body. EXTRACTABLE when the queue row or run note
names an untaken family that carries it (state plans on MT, VT, WI, UT, WV, CT, MA and AL sites;
Tennessee's WIC rule 1200-15-02; Minnesota's exhibits, Connecticut's attachments and the other
not-taken index items where a mandatory element was not found). ABSENT for the 20 publishers that
post no manual (queue `blocked_primary_source`, not published) and for optional elements a complete
manual does not carry. OUTREACH for the 10 publishers that block or gate the manual (AR, AZ as served,
DE, IL, KS, MA, NH access blocks; MO, NM, NV login or password). REVIEW where no family was
inventoried (state plans and state rule chapters for most states) or a mandatory regex found nothing
in a complete manual. Federal elements are decided at the `us` row and inherited.

## Cells by status

| status | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | INHERITED | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cells | 637 | 41 | 602 | 299 | 85 | 4233 | 5897 |

Federal elements are checked once at the `us` row and inherited by the 51 states (`INHERITED`, 4233 cells whose note names the federal status). The federal row alone (83 elements): PRESENT 59, EXTRACTABLE 24, ABSENT 0, OUTREACH 0, REVIEW 0. State-level cells (51 x 31 = 1581): PRESENT 578, EXTRACTABLE 17, ABSENT 602, OUTREACH 299, REVIEW 85.

## Federal roll-up by document family

| federal family | elements | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| statute | 19 | 0 | 19 | 0 | 0 | 0 |
| regulation (eCFR) | 56 | 56 | 0 | 0 | 0 | 0 |
| FNS/FNA guidance | 8 | 3 | 5 | 0 | 0 | 0 |

Federal cells not PRESENT:

- 19 elements EXTRACTABLE: 42 U.S.C. 1786(a) to (s) (42 USC 1786 is in no selected scope (no us/statute/42/1786 row in any corpus JSONL); uscode.house.gov serves it and the corpus already holds 7 USC ch. 51 and 42 USC titles from the same publisher (us/statute/2026-07-19-rulespec-title-42-consolidated))
- `wic_g04` EXTRACTABLE: no selected federal scope carries it (regex 'nutrition risk criteria.{0,300}(allowed|list|code|justification)' over 11 federal scopes); publisher lists it: FNA resource browser, WIC Guidance Documents family (195 documents; none taken), fna.usda.gov/resources?
- `wic_g05` EXTRACTABLE: no selected federal scope carries it (regex '^WIC Policy Memorandum #(19\\d\\d|200\\d|201\\d|202[0-4])-\\d+' over 11 federal scopes); publisher lists it: FNA resource browser, WIC Policy Memos family (154; 11 FY2025-2026 memos taken)
- `wic_g06` EXTRACTABLE: no selected federal scope carries it (regex 'Federal Register|\\d+ FR \\d+|final rule' over 11 federal scopes); publisher lists it: FNA resource browser, WIC Federal Register Notices family (70; none taken; the two income-guideline notices are wic_g01)
- `wic_g07` EXTRACTABLE: no selected federal scope carries it (regex 'infant formula.{0,120}(rebate|cost containment|contract)' over 11 federal scopes); publisher lists it: FNA WIC infant formula guidance (Guidance Documents family)
- `wic_g08` EXTRACTABLE: no selected federal scope carries it (regex 'State Plan (Guidance|Template|Submission)' over 11 federal scopes); publisher lists it: FNA WIC State Plan guidance (Guidance Documents family)

## Per-jurisdiction roll-up (state-level elements)

| jurisdiction | state elements | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | closure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| us-al | 31 | 0 | 1 | 29 | 0 | 1 | 2 open |
| us-ak | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-az | 31 | 0 | 0 | 0 | 30 | 1 | 31 open |
| us-ar | 31 | 0 | 0 | 0 | 30 | 1 | 31 open |
| us-ca | 31 | 29 | 0 | 0 | 0 | 2 | 2 open |
| us-co | 31 | 28 | 0 | 1 | 0 | 2 | 2 open |
| us-ct | 31 | 28 | 2 | 0 | 0 | 1 | 3 open |
| us-de | 31 | 0 | 0 | 0 | 30 | 1 | 31 open |
| us-dc | 31 | 29 | 0 | 0 | 0 | 2 | 2 open |
| us-fl | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-ga | 31 | 29 | 0 | 0 | 0 | 2 | 2 open |
| us-hi | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-id | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-il | 31 | 0 | 0 | 0 | 30 | 1 | 31 open |
| us-in | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-ia | 31 | 29 | 0 | 0 | 0 | 2 | 2 open |
| us-ks | 31 | 0 | 0 | 0 | 30 | 1 | 31 open |
| us-ky | 31 | 28 | 1 | 0 | 0 | 2 | 3 open |
| us-la | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-me | 31 | 28 | 1 | 0 | 0 | 2 | 3 open |
| us-md | 31 | 29 | 0 | 0 | 0 | 2 | 2 open |
| us-ma | 31 | 0 | 1 | 0 | 29 | 1 | 31 open |
| us-mi | 31 | 29 | 0 | 0 | 0 | 2 | 2 open |
| us-mn | 31 | 26 | 2 | 1 | 0 | 2 | 4 open |
| us-ms | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-mo | 31 | 0 | 0 | 0 | 30 | 1 | 31 open |
| us-mt | 31 | 0 | 1 | 29 | 0 | 1 | 2 open |
| us-ne | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-nv | 31 | 0 | 0 | 0 | 30 | 1 | 31 open |
| us-nh | 31 | 0 | 0 | 0 | 30 | 1 | 31 open |
| us-nj | 31 | 11 | 0 | 18 | 0 | 2 | 2 open |
| us-nm | 31 | 0 | 0 | 0 | 30 | 1 | 31 open |
| us-ny | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-nc | 31 | 29 | 0 | 0 | 0 | 2 | 2 open |
| us-nd | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-oh | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-ok | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-or | 31 | 28 | 1 | 0 | 0 | 2 | 3 open |
| us-pa | 31 | 27 | 0 | 1 | 0 | 3 | 3 open |
| us-ri | 31 | 27 | 2 | 0 | 0 | 2 | 4 open |
| us-sc | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-sd | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |
| us-tn | 31 | 0 | 1 | 29 | 0 | 1 | 2 open |
| us-tx | 31 | 29 | 0 | 0 | 0 | 2 | 2 open |
| us-ut | 31 | 29 | 1 | 0 | 0 | 1 | 2 open |
| us-vt | 31 | 0 | 1 | 29 | 0 | 1 | 2 open |
| us-va | 31 | 28 | 0 | 1 | 0 | 2 | 2 open |
| us-wa | 31 | 29 | 0 | 0 | 0 | 2 | 2 open |
| us-wv | 31 | 29 | 1 | 0 | 0 | 1 | 2 open |
| us-wi | 31 | 0 | 1 | 29 | 0 | 1 | 2 open |
| us-wy | 31 | 0 | 0 | 29 | 0 | 2 | 2 open |

`closure` counts cells that are neither PRESENT nor ABSENT (EXTRACTABLE, OUTREACH and REVIEW): what still needs an action or a decision. ABSENT cells are closed in the sense that the publisher posts nothing; for optional elections they read as "not elected".

## Top gaps by how many states share them

| element | label | family | states not PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| wic_s30 | WIC State Plan filed with FNS (246.4) | state_plan | 51 | 8 | 0 | 9 | 34 |
| wic_s31 | State WIC administrative rule chapter (if the state codifies WIC) | state_regulation | 51 | 1 | 0 | 0 | 50 |
| wic_s10 | Presumptive / temporary certification of pregnant women pending income or risk documentation | state_manual_or_regulation | 36 | 4 | 21 | 10 | 1 |
| wic_s27 | Farmers' market nutrition program / farm direct | state_manual_or_regulation | 34 | 0 | 24 | 10 | 0 |
| wic_s12 | Processing standards (10/20 days) and appointment scheduling | state_manual_or_regulation | 32 | 1 | 21 | 10 | 0 |
| wic_s20 | Notice of ineligibility, termination and expiration | state_manual_or_regulation | 32 | 2 | 20 | 10 | 0 |
| wic_s01 | State income eligibility standard (185 percent or lower) and current income guidelines table | state_manual_or_regulation | 31 | 0 | 21 | 10 | 0 |
| wic_s02 | Income determination method: family size, current vs annual income, self-employment, in-kind | state_manual_or_regulation | 31 | 0 | 21 | 10 | 0 |
| wic_s03 | Adjunctive / automatic income eligibility programs recognised (Medicaid, SNAP, TANF, others) | state_manual_or_regulation | 31 | 0 | 21 | 10 | 0 |
| wic_s04 | Categorical eligibility definitions (pregnant, breastfeeding to 1 year, postpartum 6 months, in | state_manual_or_regulation | 31 | 0 | 21 | 10 | 0 |
| wic_s05 | Nutritional risk criteria in use and who may determine risk (CPA) | state_manual_or_regulation | 31 | 0 | 21 | 10 | 0 |
| wic_s06 | Anthropometric and hematological (bloodwork) requirements and deferral | state_manual_or_regulation | 31 | 0 | 21 | 10 | 0 |

## What the gaps are

**Federal statute.** 42 U.S.C. 1786 is in no corpus scope in any form: no `us/statute/42/1786` row
exists in any JSONL under `provisions/us/statute/` (the four files that mention "1786" cite it from
other sections). All 19 subsections are EXTRACTABLE from uscode.house.gov, the publisher of the
title 7 and title 42 statute scopes the corpus already holds.

**Federal regulation and guidance.** 7 CFR 246 is complete (30 sections, 231 paragraph rows under
246.7) as captured on 2026-07-13, so the 2024 food package final rule text is in force in the scope.
The 2026-2027 and 2025-2026 income eligibility guidelines, the FY 2026 CVB memo, the food package
flexibilities memo (#2025-5) and the fluid-milk increase memo (#2026-1) are PRESENT. The nutrition
risk criteria list, the 143 standing pre-FY 2025 policy memoranda, the 70 Federal Register notices,
infant formula rebate guidance and state plan guidance are EXTRACTABLE from the FNA resource browser
(the queue row inventoried the families; none taken).

**States without a manual in the corpus (30).** Twenty publishers post no WIC policy manual on their
own site (AK, AL, FL, HI, ID, IN, LA, MS, MT, ND, NE, NY, OH, OK, SC, SD, TN, VT, WI, WY): every
manual-carried element is ABSENT for them with the queue's finding as evidence. Ten publishers block
or gate it (AR, AZ, DE, IL, KS, MA, NH; MO, NM, NV): OUTREACH. For these 30 states the only corpus
route to the state's income guidelines, food list and certification rules is the state plan (posted
by MT, VT, WI, AL as a notice) or the state administrative rule (TN 1200-15-02), both EXTRACTABLE
where the queue saw them and REVIEW elsewhere.

**States with a manual (21).** The 29 manual-carried elements are PRESENT in nearly every state
with a manual; the exceptions are New Jersey (only the vendor-management functional area is
published, so 18 of 29 are ABSENT by the publisher's own choice) and a handful of REVIEW/EXTRACTABLE
cells where a mandatory element was not found and the queue lists untaken items that may carry it
(MN exhibits, CT attachments, RI's compiled manual, KY's policy-group PDFs, ME appendices).

**State plan and state rule (all 51).** No WIC state plan (246.4) is in the corpus for any state, and
no state administrative-code WIC chapter; the WIC queue inventoried the manual family only. These are
the two shared gaps that a manual cannot close: the state plan is where the income standard,
priority system, food list and certification procedures are filed with FNS every year.

## What would close each class of gap

- 42 U.S.C. 1786: one uscode.house.gov extraction (section 17 of the Child Nutrition Act) with the
  extractor that built `us/statute/2026-07-22-rulespec-title-7-consolidated`. Closes 19 federal cells.
- FNA guidance families: one manifest against the FNA resource browser on the origin host for the
  nutrition risk criteria list, the pre-FY 2025 memoranda, the Federal Register notices, rebate and
  state-plan guidance (the batch-1 run note records the facet counts: 195, 154, 70). Closes 5 federal
  cells.
- WIC state plans: FNS does not post them; eight states post theirs (MT, VT, WI, UT, WV, CT, MA, AL
  notice). A state-plan family manifest for those eight closes 8 cells and, for MT and VT, is the only
  published policy text. The other 43 need outreach or a FOIA-style request to FNS regional offices.
- State WIC rule chapters: a state-register inventory (the tax and SSI passes' method) for the states
  that codify WIC (TN 1200-15-02 is the one the queue saw); unverified elsewhere.
- Blocked publishers (AR, AZ, DE, IL, KS, MA, NH, MO, NM, NV): outreach for an official export; the
  batch-4 note names AZ (browser check of the agencies page) and KS (Document Center listing) as the
  first retries. Each closes 29 cells.
- Publishers that post no manual (20): nothing to extract; the gap is real and should be recorded as
  such against the program's closure, with the state plan as the fallback family.
- Untaken index items in states with a manual (MN exhibits 5-A/5-T/5-U/6-A, CT income guidelines
  sheet and attachments, ME appendices, WV attachments, DC clinical manuals, OR policy updates): small
  completion scopes from the recorded index families.

## Elements beyond PolicyEngine

PolicyEngine models 24 of the 114 elements at least partially (`pe_modeled` yes or partial) and none of the other 90. The law has these and PolicyEngine does not (grouped by level):

- **federal_only** (25): `wic_usc_1786_a` 42 USC 1786(a) Congressional findings and declaration of purpose; `wic_usc_1786_c` 42 USC 1786(c) Grants-in-aid; eligibility of local agencies; regulatio; `wic_usc_1786_e` 42 USC 1786(e) Nutrition education and drug abuse education; `wic_usc_1786_g` 42 USC 1786(g) Authorization of appropriations; `wic_usc_1786_h` 42 USC 1786(h) Funds for nutrition services and administration; infant; `wic_usc_1786_i` 42 USC 1786(i) Division of funds formula; reallocation; `wic_usc_1786_j` 42 USC 1786(j) Program services at community and migrant health center; `wic_usc_1786_k` 42 USC 1786(k) National Advisory Council on Maternal, Infant, and Feta; `wic_usc_1786_l` 42 USC 1786(l) Donation of foods by Secretary; `wic_usc_1786_n` 42 USC 1786(n) Disqualification of vendors disqualified under SNAP; `wic_usc_1786_o` 42 USC 1786(o) Disqualification of vendors convicted of trafficking or; `wic_usc_1786_p` 42 USC 1786(p) Criminal forfeiture; `wic_usc_1786_q` 42 USC 1786(q) Technical assistance to Secretary of Defense; `wic_usc_1786_r` 42 USC 1786(r) Emergencies and disasters; `wic_usc_1786_s` 42 USC 1786(s) Supply chain disruptions (infant formula flexibilities); `wic_cfr_246_7f` 7 CFR 246.7(f) Processing standards: 10 days (20 in remote areas), pri; `wic_cfr_246_7i` 7 CFR 246.7(i) Participant rights and responsibilities; notice of inel; `wic_cfr_246_7j` 7 CFR 246.7(j) Notification of ineligibility, termination, expiration;; `wic_cfr_246_7k` 7 CFR 246.7(k) Dual participation prohibition and claims; `wic_cfr_246_7l` 7 CFR 246.7(l) Transfer of certification (VOC) between agencies; `wic_cfr_246_7m` 7 CFR 246.7(m) Certification of participants in institutions and homel; `wic_cfr_246_10d` 7 CFR 246.10(d) Medical documentation for exempt formula and WIC-eligi; `wic_cfr_246_9` 7 CFR 246.9 Fair hearing procedures for participants (request period, ; `wic_cfr_246_11` 7 CFR 246.11 Nutrition education: two contacts per certification, brea; `wic_cfr_246_16a` 7 CFR 246.16a Infant formula rebate contracts and cost containment
- **federal_with_state_option** (11): `wic_usc_1786_f` 42 USC 1786(f) Plan of operation and administration by State agency; s; `wic_usc_1786_m` 42 USC 1786(m) Farmers' market nutrition program (FMNP): eligibility, ; `wic_cfr_246_7b` 7 CFR 246.7(b) Residency and physical presence; migrant, homeless and ; `wic_cfr_246_7g` 7 CFR 246.7(g) Certification periods by category (pregnancy, 6/12 mont; `wic_cfr_246_7h` 7 CFR 246.7(h) Priority system for caseload limits (priorities I-VII); `wic_cfr_246_7n` 7 CFR 246.7(n) Remote and other certification flexibilities (physical ; `wic_cfr_246_10b` 7 CFR 246.10(b) General food package requirements; state food lists; (; `wic_cfr_246_12a` 7 CFR 246.12(a)-(f) Food delivery systems, benefit issuance, EBT requi; `wic_cfr_246_12g` 7 CFR 246.12(g)-(l) Vendor authorization, selection criteria, agreemen; `wic_cfr_246_12u` 7 CFR 246.12(u) Participant violations, sanctions and disqualification; `wic_cfr_246_4a` 7 CFR 246.4(a) State plan contents (annual; local agency plan, certifi
- **federal_regulation** (27): `wic_cfr_246_1` 7 CFR 246.1 General purpose and scope; `wic_cfr_246_3` 7 CFR 246.3 Administration; `wic_cfr_246_4` 7 CFR 246.4 State plan; `wic_cfr_246_5` 7 CFR 246.5 Selection of local agencies; `wic_cfr_246_6` 7 CFR 246.6 Agreements with local agencies; `wic_cfr_246_8` 7 CFR 246.8 Nondiscrimination; `wic_cfr_246_9` 7 CFR 246.9 Fair hearing procedures for participants; `wic_cfr_246_11` 7 CFR 246.11 Nutrition education; `wic_cfr_246_12` 7 CFR 246.12 Food delivery methods; `wic_cfr_246_13` 7 CFR 246.13 Financial management system; `wic_cfr_246_14` 7 CFR 246.14 Program costs; `wic_cfr_246_15` 7 CFR 246.15 Program income other than grants; `wic_cfr_246_16` 7 CFR 246.16 Distribution of funds; `wic_cfr_246_16a` 7 CFR 246.16a Infant formula and authorized foods cost containment; `wic_cfr_246_17` 7 CFR 246.17 Closeout procedures; `wic_cfr_246_18` 7 CFR 246.18 Administrative review of State agency actions; `wic_cfr_246_19` 7 CFR 246.19 Management evaluation and monitoring reviews; `wic_cfr_246_20` 7 CFR 246.20 Audits; `wic_cfr_246_21` 7 CFR 246.21 Investigations; `wic_cfr_246_22` 7 CFR 246.22 Administrative appeal of FNS decisions; `wic_cfr_246_23` 7 CFR 246.23 Claims and penalties; `wic_cfr_246_24` 7 CFR 246.24 Procurement and property management; `wic_cfr_246_25` 7 CFR 246.25 Records and reports; `wic_cfr_246_26` 7 CFR 246.26 Other provisions; `wic_cfr_246_27` 7 CFR 246.27 Program information; `wic_cfr_246_28` 7 CFR 246.28 OMB control numbers; `wic_cfr_246_29` 7 CFR 246.29 Waivers of program requirements
- **federal_guidance** (4): `wic_g05` Standing WIC policy memoranda issued before FY 2025 (143 of the 154-me; `wic_g06` WIC Federal Register notices and final rules family other than the inc; `wic_g07` WIC infant formula rebate and cost-containment guidance (state contrac; `wic_g08` FNS WIC State Plan guidance and template (annual state plan submission
- **state** (23): `wic_s06` Anthropometric and hematological (bloodwork) requirements and deferral; `wic_s07` Certification periods by category; `wic_s08` Residency and physical presence requirements (and exceptions); `wic_s09` Identity, residency and income documentation and verification; `wic_s10` Presumptive / temporary certification of pregnant women pending income; `wic_s11` Priority system and waiting list management; `wic_s12` Processing standards (10/20 days) and appointment scheduling; `wic_s15` State-approved food list / authorized foods; `wic_s16` Medical documentation and special/exempt infant formula issuance; `wic_s18` Dual participation and transfer of certification (VOC); `wic_s19` Participant violations, sanctions, disqualification and claims; `wic_s20` Notice of ineligibility, termination and expiration; `wic_s21` Fair hearing procedures for participants; `wic_s22` Nutrition education contacts and breastfeeding promotion; `wic_s23` Vendor authorization, management and sanctions; `wic_s24` Benefit issuance / eWIC / food instrument rules; `wic_s25` Local agency selection, agreements and monitoring; `wic_s26` Migrant, homeless and institutional participant provisions; `wic_s27` Farmers' market nutrition program / farm direct; `wic_s28` Civil rights and nondiscrimination procedures; `wic_s29` Caseload management and participant scheduling; `wic_s30` WIC State Plan filed with FNS (246.4); `wic_s31` State WIC administrative rule chapter (if the state codifies WIC)

`pe_modeled` is recorded per element in the schema and per row in the matrix; `rulespec_scoped` records whether rulespec-us encodes the source or a state program spec cites it (federal elements are computed from the rulespec-us file tree and the `programs/*/snap` scope lists).

## Schema notes and uncertainty

- Federal statute elements are the 19 subsections of 42 USC 1786 (a)-(s); the section is in no corpus scope, so every one is EXTRACTABLE from uscode.house.gov.
- Federal regulation elements are the 30 sections of 7 CFR 246 plus 25 participant-facing paragraph elements (246.7, 246.10, 246.12, 246.4, 246.9, 246.11, 246.16a). The scope us/regulation/2026-07-13-recovery-r2026-07-17-dedup is paragraph-granular only for 246.7 (231 paragraph rows); 246.4, 246.10 and 246.12 are single section bodies, so their paragraph elements are checked by keyword over the section body.
- Schema uncertainty: 246.10(e) food packages I-VII are one element although each package's maximum monthly allowance is a distinct fact; 246.12 vendor management (g)-(l) is one element although it carries dozens of facts an encoder of vendor rules would need. The bar for a household-facing WIC encoding is 246.7 + 246.10 + the state's income guidelines and food list; vendor and local-agency elements are recorded for completeness.
- State elements: 31, of which 29 are checked by regex over the state's WIC policy manual scope (single_block per policy PDF, so a match cites the policy). Only 21 states have a manual scope; the other 30 inherit the queue's classification (OUTREACH for the 10 access/login blocks, ABSENT for the 20 publishers that post no manual).
- wic_s30 (state plan) and wic_s31 (state rule chapter) have no corpus family anywhere; the queue inventoried the manual family only, so most rows are REVIEW rather than ABSENT.
- PolicyEngine models WIC as eligibility (category, 185% income test, nutritional risk flag) plus a food-package value and the CVB; everything about certification, documentation, priority, sanctions, vendors, nutrition education and issuance is beyond it.

## Timing and searches

- Check run started 2026-09-12T09:19:38-0400, finished 2026-09-12T09:22:52-0400 (193.7 s for SNAP and WIC together); 128 scope files and 63884 provision rows read from `data/corpus/provisions`.
- Searches: for every element with a `regex` in the schema, that regex was run (case-insensitive, dot matches newline) over every provision body of the jurisdiction's selected scopes listed in `summary.json` under `scopes`; citation-path elements were looked up by exact path (then by children with bodies). The eCFR structure was read once from `https://www.ecfr.gov/api/versioner/v1/structure/current/title-7.json` (5.3 MB) and the parts 246 and 271-285 section lists embedded in `cfr_structure.py`.
- Queue evidence: `manifests/snap-completion-agent-queue.yaml` (index_families, queue_status, index_url per state), `manifests/state-snap-manual-agent-queue.yaml`, `manifests/wic-agent-queue.yaml` (queue_status, index_inventory, notes), plus the reviewer facts transcribed from the 2026-09-10/11 run notes into the script's tables (`SNAP_BLOCKED`, `SNAP_TRANSMITTAL_FAMILY`, `SNAP_ET_PLAN_PUBLISHER`, `WIC_BLOCK_CLASS`, `WIC_STATE_PLAN_PUBLISHER`, `WIC_NOT_TAKEN_FAMILY`).
- Spot checks: the PRESENT snippets of every optional-election element and every table element were read for false positives after each run; regexes were tightened three times (BBCE, mandatory SUA, LIHEAP heat-and-eat, standard medical deduction, table elements, TBA, state-funded programs, restaurant meals, state minimum supplements, SSI cash-out; WIC adjunctive eligibility and temporary certification) and a per-element exclusion window added. Residual false positives are possible for elements whose wording varies by state; the cited row is always given so a reader can check.
