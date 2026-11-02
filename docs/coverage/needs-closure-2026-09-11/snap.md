# SNAP: needs-driven closure check (2026-09-11 corpus)

Corpus as selected on 2026-09-11 (draft union selector plus the twelve SNAP superseding scopes on disk); checked 2026-09-12. Schema: `snap-schema.yaml` (393 elements: 332 federal, 61 state). Matrix: `snap-matrix.csv` (20375 cells = 52 jurisdictions x 393 elements, one row each). Builder: `check_snap_wic.py` (read-only over `data/corpus`; 193.7 s, 128 scopes and 63884 provision rows loaded for both programs); PRESENT evidence: `snap-hits.jsonl`.

## Method

The schema follows the law's own structure, in order of authority. (1) Federal statute: every
section of 7 U.S.C. chapter 51 (2011 to 2036d; 2030 and 2033 are repealed container rows and are
noted, not counted) and every subsection of the four household-facing sections 2012 (definitions),
2014 (eligible households), 2015 (disqualifications) and 2017 (allotment), plus the state-plan
subsections 2020(e), (i), (s) and the E&T funding subsection 2025(h). (2) Federal regulation: every
non-reserved section of 7 CFR 271 to 285 as listed by the eCFR structure API (current edition, read
2026-09-12; `cfr_structure.py`), plus 54 paragraph-level elements of 7 CFR 273 (household concept,
application processing, non-citizens, students, work provisions, resources, income and deductions,
benefit computation, special households, reporting, notices, recertification, hearings, IPV, claims,
MRRB, ABAWD, TBA). Sections carrying a state option are marked `federal_with_state_option` and have
state-level children. (3) FNS/FNA guidance: the FY 2026 COLA tables and income standards (nine
figures), the annual state SUA table, the ABAWD waiver list, the BBCE chart, the two OBBBA
implementation memos in the corpus and the rest of that series, and the State Options Report as a
cross-check. (4) State rulebook: 61 elements a state's manual, regulation, annual table or
transmittal, state plan or statute must carry, each a fact an encoder reads (an amount, a threshold,
an election, a period, a disqualification rule), grouped by the family that carries it.

Selected scopes are those of `docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json`
with the twelve SNAP superseding scopes on disk (`2026-09-11-<st>-snap-manual-supersede` for AR, GA,
KY, ME, MI, NC, ND, NE, NV, OK, TN, WY) replacing their released versions. A state's SNAP rulebook is
its manual, regulation, policy and SNAP guidance scopes (the list per state is in `summary.json`
under `scopes`; other-program scopes such as Medicaid, TANF, WIC, LIHEAP and tax are excluded by
name). Federal statute and paragraph-granular regulation elements are checked by citation path: the
row must exist with a non-empty body. The selected 7 CFR 273 scopes are section-granular (273.2 is
one 154 KB body), so 273 paragraph elements are checked by a keyword regex over the section body;
guidance elements by regex over the selected federal guidance bodies; state elements by regex over
every provision body of the state's SNAP scopes, taking the provision with the most matches as the
citation (a longer body breaks ties). Every regex is recorded per element in `snap-schema.yaml`, and
every PRESENT match with its snippet is in `snap-hits.jsonl`; a reviewer can open the cited row.

Status rules: PRESENT only when a provision body in a selected scope carries the element (cited with
scope version, citation path and snippet). EXTRACTABLE when the completion queue row or a run note
records that the publisher lists the carrying family and it was not taken (the family and index are
named). ABSENT when the publisher's index was inventoried family-by-family in the #680 completion
pass and no listed family or rulebook text carries the fact (for optional elections this reads as
"not elected"). OUTREACH for the three publisher blocks the queue records (AZ DES FAA host, NY OTDA,
OH eManuals). REVIEW when the regex found nothing and the publisher index was not inventoried
family-by-family (the 23 states outside the completion queue), or when a 273 paragraph regex failed
inside a present section. Federal-level elements are decided once at the `us` row and inherited
(`INHERITED`) by the 51 states, so each state row carries the federal status in its note rather than
repeating the evidence.

## Cells by status

| status | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | INHERITED | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cells | 2647 | 210 | 214 | 56 | 316 | 16932 | 20375 |

Federal elements are checked once at the `us` row and inherited by the 51 states (`INHERITED`, 16932 cells whose note names the federal status). The federal row alone (332 elements): PRESENT 200, EXTRACTABLE 131, ABSENT 0, OUTREACH 0, REVIEW 1. State-level cells (51 x 61 = 3111): PRESENT 2447, EXTRACTABLE 79, ABSENT 214, OUTREACH 56, REVIEW 315.

## Federal roll-up by document family

| federal family | elements | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| statute | 81 | 81 | 0 | 0 | 0 | 0 |
| regulation (eCFR) | 235 | 109 | 126 | 0 | 0 | 0 |
| FNS/FNA guidance | 16 | 10 | 5 | 0 | 0 | 1 |

Federal cells not PRESENT:

- 126 elements EXTRACTABLE: 7 CFR parts 271, 272, 274, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285 (part in no selected scope (selected federal scopes hold 7 CFR 246, 247, 273 and 275 only); eCFR title 7 chapter II subchapter C lists it (structure API read 2026-09-12); same extractor as us/regulation/2026-06-15-title-7)
- `snap_g09` EXTRACTABLE: no selected federal scope carries it (regex 'minimum (benefit|allotment).{0,80}\\$\\s?\\d' over 10 federal scopes); publisher lists it: FNS COLA memo 'FY 2026 Cost-of-Living Adjustments' (the full memo carries the minimum benefit; the corpus holds only the two
- `snap_g10` EXTRACTABLE: no selected federal scope carries it (regex 'standard utility allowance.{0,600}(Alabama|Alaska|Arizona)' over 10 federal scopes); publisher lists it: FNS SUA page fns.usda.gov/snap/eligibility/deduction/standard-utility-allowances (annual state table); also FY
- `snap_g11` EXTRACTABLE: no selected federal scope carries it (regex '(waiver|waived).{0,200}able.bodied|ABAWD.{0,200}waiver.{0,200}(state|area|county)' over 10 federal scopes); publisher lists it: FNS ABAWD waivers page fns.usda.gov/snap/abawd/waivers (per-state approval letters and 
- `snap_g12` EXTRACTABLE: no selected federal scope carries it (regex 'broad.based categorical.{0,600}(Alabama|Alaska|Arizona)' over 10 federal scopes); publisher lists it: FNS BBCE chart fns.usda.gov/snap/broad-based-categorical-eligibility
- `snap_g15` EXTRACTABLE: no selected federal scope carries it (regex 'internet.{0,200}(utility|SUA)|heat.and.eat|cost.shar(e|ing).{0,200}(payment error|state)' over 10 federal scopes); publisher lists it: FNS OBBBA implementation memo series fna.usda.gov/snap/obbb (front door 403; ori
- `snap_g16` REVIEW: no selected federal scope carries it (regex 'State Options Report' over 10 federal scopes); publisher lists it: FNS SNAP State Options Report (fns.usda.gov/snap/waivers/state-options-report); queue policy lists State Options Reports as a forbidden source for s

## Per-jurisdiction roll-up (state-level elements)

| jurisdiction | state elements | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | closure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| us-al | 61 | 44 | 1 | 11 | 0 | 5 | 6 open |
| us-ak | 61 | 51 | 1 | 0 | 0 | 9 | 10 open |
| us-az | 61 | 35 | 1 | 0 | 25 | 0 | 26 open |
| us-ar | 61 | 53 | 1 | 7 | 0 | 0 | 1 open |
| us-ca | 61 | 55 | 1 | 5 | 0 | 0 | 1 open |
| us-co | 61 | 52 | 0 | 0 | 0 | 9 | 9 open |
| us-ct | 61 | 49 | 1 | 0 | 0 | 11 | 12 open |
| us-de | 61 | 44 | 1 | 0 | 0 | 16 | 17 open |
| us-dc | 61 | 52 | 1 | 0 | 0 | 8 | 9 open |
| us-fl | 61 | 48 | 3 | 10 | 0 | 0 | 3 open |
| us-ga | 61 | 51 | 3 | 7 | 0 | 0 | 3 open |
| us-hi | 61 | 44 | 1 | 7 | 0 | 9 | 10 open |
| us-id | 61 | 39 | 1 | 11 | 0 | 10 | 11 open |
| us-il | 61 | 54 | 1 | 0 | 0 | 6 | 7 open |
| us-in | 61 | 49 | 1 | 0 | 0 | 11 | 12 open |
| us-ia | 61 | 49 | 1 | 8 | 0 | 3 | 4 open |
| us-ks | 61 | 45 | 1 | 0 | 0 | 15 | 16 open |
| us-ky | 61 | 53 | 3 | 5 | 0 | 0 | 3 open |
| us-la | 61 | 52 | 1 | 0 | 0 | 8 | 9 open |
| us-me | 61 | 48 | 1 | 9 | 0 | 3 | 4 open |
| us-md | 61 | 55 | 1 | 5 | 0 | 0 | 1 open |
| us-ma | 61 | 45 | 6 | 10 | 0 | 0 | 6 open |
| us-mi | 61 | 50 | 4 | 7 | 0 | 0 | 4 open |
| us-mn | 61 | 48 | 1 | 0 | 0 | 12 | 13 open |
| us-ms | 61 | 44 | 1 | 0 | 0 | 16 | 17 open |
| us-mo | 61 | 46 | 1 | 0 | 0 | 14 | 15 open |
| us-mt | 61 | 50 | 1 | 9 | 0 | 1 | 2 open |
| us-ne | 61 | 42 | 1 | 10 | 0 | 8 | 9 open |
| us-nv | 61 | 52 | 1 | 8 | 0 | 0 | 1 open |
| us-nh | 61 | 44 | 8 | 9 | 0 | 0 | 8 open |
| us-nj | 61 | 45 | 1 | 0 | 0 | 15 | 16 open |
| us-nm | 61 | 46 | 2 | 7 | 0 | 6 | 8 open |
| us-ny | 61 | 48 | 1 | 0 | 12 | 0 | 13 open |
| us-nc | 61 | 49 | 3 | 9 | 0 | 0 | 3 open |
| us-nd | 61 | 50 | 4 | 7 | 0 | 0 | 4 open |
| us-oh | 61 | 41 | 1 | 0 | 19 | 0 | 20 open |
| us-ok | 61 | 47 | 1 | 12 | 0 | 1 | 2 open |
| us-or | 61 | 51 | 1 | 0 | 0 | 9 | 10 open |
| us-pa | 61 | 50 | 1 | 0 | 0 | 10 | 11 open |
| us-ri | 61 | 46 | 1 | 0 | 0 | 14 | 15 open |
| us-sc | 61 | 52 | 1 | 0 | 0 | 8 | 9 open |
| us-sd | 61 | 49 | 1 | 0 | 0 | 11 | 12 open |
| us-tn | 61 | 43 | 1 | 12 | 0 | 5 | 6 open |
| us-tx | 61 | 49 | 1 | 8 | 0 | 3 | 4 open |
| us-ut | 61 | 45 | 1 | 0 | 0 | 15 | 16 open |
| us-vt | 61 | 49 | 1 | 9 | 0 | 2 | 3 open |
| us-va | 61 | 50 | 1 | 0 | 0 | 10 | 11 open |
| us-wa | 61 | 51 | 1 | 0 | 0 | 9 | 10 open |
| us-wv | 61 | 47 | 1 | 0 | 0 | 13 | 14 open |
| us-wi | 61 | 50 | 1 | 0 | 0 | 10 | 11 open |
| us-wy | 61 | 46 | 3 | 12 | 0 | 0 | 3 open |

`closure` counts cells that are neither PRESENT nor ABSENT (EXTRACTABLE, OUTREACH and REVIEW): what still needs an action or a decision. ABSENT cells are closed in the sense that the publisher posts nothing; for optional elections they read as "not elected".

## Top gaps by how many states share them

| element | label | family | states not PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| snap_s32 | State Plan of Operation (272.2) with elected options attachments | state_plan | 51 | 1 | 24 | 3 | 23 |
| snap_s31 | SNAP E&T State Plan (annual, filed with FNS) | state_plan | 50 | 50 | 0 | 0 | 0 |
| snap_s40 | Restaurant meals program election | state_manual_or_regulation | 45 | 0 | 22 | 2 | 21 |
| snap_s53 | State-funded minimum benefit supplement (NJ, MD, DC and others; if any) | state_statute | 45 | 0 | 23 | 3 | 19 |
| snap_s37 | State-funded food assistance for non-citizens ineligible under federal rules (if any) | state_statute | 44 | 0 | 22 | 3 | 19 |
| snap_s03 | BBCE asset test waived or elected asset limit | state_manual_or_regulation | 41 | 0 | 20 | 3 | 18 |
| snap_s59 | SSI cash-out / SSI recipients' treatment (CA CalFresh expansion, state supplement states) | state_manual_or_regulation | 41 | 0 | 18 | 3 | 20 |
| snap_s07 | Mandatory SUA election (standards used in place of actual utility costs) | state_manual_or_regulation | 33 | 0 | 18 | 3 | 12 |
| snap_s10 | Standard medical deduction (demonstration) amount and threshold | state_manual_or_regulation | 28 | 0 | 13 | 2 | 13 |
| snap_s33 | Transitional benefits alternative (TBA) election and period | state_manual_or_regulation | 27 | 0 | 13 | 1 | 13 |
| snap_s39 | Combined application project / elderly simplified application project | state_manual_or_regulation | 27 | 0 | 15 | 1 | 11 |
| snap_s20 | Current-FY change transmittal / COLA notice carrying the state's applied FY 2026 amounts | state_table_or_transmittal | 25 | 3 | 0 | 2 | 20 |

## What the gaps are

**Federal.** 7 CFR 271, 272, 274 and 276 to 285 (126 non-reserved sections) are in no selected
scope: the federal SNAP regulation in the corpus is 273 (complete across two scopes) and 275 only.
271.2 (definitions, including elderly or disabled member), 272.2 (state plan of operation), 272.8
(IEVS), 272.17 (lottery), 274.7 (benefit redemption, restaurant meals), 277 (administrative cost
sharing) and 278 (retailers) are the rule-carrying parts an encoder reads; 283 (QC appeals, 32
sections) and 279 are procedural. All are EXTRACTABLE from eCFR with the extractor that produced
`us/regulation/2026-06-15-title-7-part-275`. 42 U.S.C. chapter 51 is complete section by section and
subsection by subsection in `us/statute/2026-07-22-rulespec-title-7-consolidated`. Of the guidance
families, the FY 2026 allotment, deduction, asset and income tables are present; the FNS state SUA
table, the ABAWD waiver list, the BBCE chart and the remaining OBBBA memos are EXTRACTABLE from the
FNS/FNA origin host; the full COLA memo (minimum benefit figure) is EXTRACTABLE; the State Options
Report is REVIEW because the queue policy forbids it as a source for state rules.

**State plans (51 states each).** No SNAP E&T State Plan is in the corpus except Colorado's
(`us-co/policy/co-cdhs-snap-et-state-plan-ffy2026`), although FNS posts every state's plan and two
state indexes list theirs (AR, KY): 50 EXTRACTABLE. The 272.2 State Plan of Operation and its option
attachments are in no scope for any state; FNS does not post them, 24 inventoried publishers list
none (ABSENT), New Mexico lists a verification-plan attachment (EXTRACTABLE), and the rest are REVIEW.
These two families are the largest shared gap and the one the corpus cannot close from the manuals.

**Applied FY 2026 tables and transmittals.** The state's own applied table of standard deductions,
shelter caps, income limits and maximum allotments, and the transmittal that put the FY 2026 figures
into effect, were found in the rulebook text of 26 to 36 states; the federal figures are PRESENT for
everyone, so this is a provenance gap (which document the encoder cites for the state's applied
value), not a missing fact. Where the publisher lists a transmittal or table family that was not
taken (GA MT cover letters, NC change notices, MI policy bulletins and RFT tables, NV transmittals, FL
summaries of changes, ND release PDFs, NH service releases, KY OMTL volumes, AR media-library
editions, MA DTA Online Guide, CA ACLs) the cell is EXTRACTABLE; elsewhere REVIEW.

**Optional elections.** BBCE, its threshold and asset waiver, mandatory SUA, the standard medical
deduction, TBA, CAP/ESAP, restaurant meals, drug-felony modification, state-funded non-citizen food
assistance and state-funded minimum supplements are elections; a fully inventoried rulebook with no
text for them is ABSENT (not elected). Where the inventory was not family-by-family the cell is REVIEW.

**Blocked publishers.** Arizona (DES FAA manual host, F5 challenge; the released scope is a thin
archived-snapshot capture), New York (OTDA host bot-challenged; the SNAP Source Book scope carries 22
rows) and Ohio (eManuals Food Assistance manual host does not answer; OAC 5101:4 is complete) carry
OUTREACH for every element the regex did not find.

## What would close each class of gap

- 7 CFR 271-285: one eCFR extraction per part with the existing `extract-official-documents`
  path used for part 275 (126 sections; the whole title-7 subchapter C is about 2 MB of XML). Closes
  126 federal cells and, by inheritance, their 51 state rows each.
- FNS annual tables (SUA by state, ABAWD waiver status, BBCE chart, full COLA memo, remaining OBBBA
  memos): one guidance manifest against the FNA origin host `fns-prod.azureedge.us`, the host the
  existing `manifests/us-snap-guidance.yaml` already uses. Closes 5 federal cells; the SUA table alone
  gives every state's HCSUA/LUA/telephone figures an FNS citation.
- SNAP E&T State Plans: FNS posts all 51 on one index (`fns.usda.gov/snap/et/plans`, origin host);
  one manifest, one scope per state or one federal scope with 51 documents. Closes 50 cells.
- State transmittal and table families already inventoried (GA, NC, MI, NV, FL, ND, NH, KY, AR, MA,
  CA): per-state completion scopes from the recorded index families; these carry the applied FY 2026
  figures and the revision history the manuals cite. Closes most of the 15 to 25 non-PRESENT cells per
  table element (snap_s15 to s18, s20) and gives the transmittal element its own family.
- 272.2 State Plans of Operation: not published by FNS or by 24 inventoried states; outreach to state
  agencies (or a FOIA-style request to FNS regional offices) is the only route. Record as a standing
  gap rather than a queue item.
- AZ, NY, OH: outreach for an official export (AZ DES FAA manual, NY OTDA SNAP Source Book and policy
  directives, OH eManuals Food Assistance manual). Each closes 9 to 24 state cells.
- REVIEW cells in the 23 states outside the #680 completion queue: a family-by-family inventory of
  each publisher's SNAP index (the completion pass method) turns REVIEW into ABSENT or EXTRACTABLE
  without new extraction; the same pass can re-probe the regex misses for mandatory elements.

## Elements beyond PolicyEngine

PolicyEngine models 104 of the 393 elements at least partially (`pe_modeled` yes or partial) and none of the other 289. The law has these and PolicyEngine does not (grouped by level):

- **federal_statute** (28): `snap_usc_2011` 7 USC 2011 Congressional declaration of policy; `snap_usc_2012a` 7 USC 2012a Publicly operated community health centers; `snap_usc_2013` 7 USC 2013 Establishment of supplemental nutrition assistance program; `snap_usc_2014a` 7 USC 2014a Notice of change in State of residence of certified househ; `snap_usc_2016` 7 USC 2016 Issuance and use of program benefits; `snap_usc_2016a` 7 USC 2016a EBT benefit fraud prevention; `snap_usc_2018` 7 USC 2018 Approval of retail food stores and wholesale food concerns; `snap_usc_2019` 7 USC 2019 Redemption of program benefits; `snap_usc_2020` 7 USC 2020 Administration; `snap_usc_2021` 7 USC 2021 Civil penalties and disqualification of retail food stores ; `snap_usc_2022` 7 USC 2022 Disposition of claims; `snap_usc_2023` 7 USC 2023 Administrative and judicial review; restoration of rights; `snap_usc_2024` 7 USC 2024 Violations and enforcement; `snap_usc_2025` 7 USC 2025 Administrative cost-sharing and quality control; `snap_usc_2026` 7 USC 2026 Research, demonstration, and evaluations; `snap_usc_2026a` 7 USC 2026a Healthy fluid milk incentives projects; `snap_usc_2027` 7 USC 2027 Appropriations and allotments; `snap_usc_2028` 7 USC 2028 Consolidated block grants for Puerto Rico and American Samo; `snap_usc_2029` 7 USC 2029 Workfare; `snap_usc_2031` 7 USC 2031 Minnesota Family Investment Project; `snap_usc_2032` 7 USC 2032 Automated data processing and information retrieval systems; `snap_usc_2034` 7 USC 2034 Assistance for community food projects; `snap_usc_2035` 7 USC 2035 Simplified supplemental nutrition assistance program; `snap_usc_2036` 7 USC 2036 Availability of commodities for emergency food assistance p; `snap_usc_2036a` 7 USC 2036a Nutrition education and obesity prevention grant program; `snap_usc_2036b` 7 USC 2036b Retail food store and recipient trafficking; `snap_usc_2036c` 7 USC 2036c Annual State report on verification of SNAP participation; `snap_usc_2036d` 7 USC 2036d Pilot projects to encourage the use of public-private part
- **federal_only** (38): `snap_usc_2012_o` 7 USC 2012(o) Definition of retail food store; `snap_usc_2012_r` 7 USC 2012(r) Definition of State agency; `snap_usc_2014_b` 7 USC 2014(b) Eligibility standards; uniform national standards; `snap_usc_2014_h` 7 USC 2014(h) Temporary emergency (disaster) standards of eligibility; `snap_usc_2014_i` 7 USC 2014(i) Attribution of income and resources of sponsors to spons; `snap_usc_2014_k` 7 USC 2014(k) Assistance to third parties (vendor payments) counted or; `snap_usc_2014_l` 7 USC 2014(l) Earnings of on-the-job training participants under 19; `snap_usc_2015_a` 7 USC 2015(a) Additional conditions rendering individuals ineligible; `snap_usc_2015_b` 7 USC 2015(b) Fraud and misrepresentation: IPV disqualification period; `snap_usc_2015_c` 7 USC 2015(c) Refusal to provide necessary information; SSN; `snap_usc_2015_h` 7 USC 2015(h) Transfer of assets to qualify; `snap_usc_2015_j` 7 USC 2015(j) Disqualification for receipt of multiple benefits; `snap_usc_2015_k` 7 USC 2015(k) Disqualification of fleeing felons and probation/parole ; `snap_usc_2015_p` 7 USC 2015(p) Disqualification for destroying food to obtain cash; `snap_usc_2015_q` 7 USC 2015(q) Disqualification for sale of food purchased with benefit; `snap_usc_2015_r` 7 USC 2015(r) Disqualification for certain convicted felons (murder, s; `snap_usc_2015_s` 7 USC 2015(s) Ineligibility due to substantial lottery or gambling win; `snap_usc_2017_b` 7 USC 2017(b) Benefits not deemed income or resources; `snap_usc_2017_d` 7 USC 2017(d) Reduction of public assistance benefits does not increas; `snap_usc_2017_e` 7 USC 2017(e) Allotments for residents of drug and alcohol treatment c; `snap_usc_2017_f` 7 USC 2017(f) Alternative procedures for residents of group facilities; `snap_cfr_273_2_2g` 7 CFR 273.2(g) Normal processing standard (30 days); `snap_cfr_273_2_2i` 7 CFR 273.2(i) Expedited service (7-day standard; $150 gross income / ; `snap_cfr_273_2_2k` 7 CFR 273.2(k) Joint processing with public assistance (PA/GA) applica; `snap_cfr_273_2_2o` 7 CFR 273.2(o) Attestation of disqualified-felon status by applicants ; `snap_cfr_273_4_4c` 7 CFR 273.4(c) Sponsored aliens: deeming of sponsor income and resourc; `snap_cfr_273_7_7j` 7 CFR 273.7(j) Voluntary quit and reduction of work effort; `snap_cfr_273_8_8e` 7 CFR 273.8(e) Excluded resources (home, retirement, education account; `snap_cfr_273_10_10c` 7 CFR 273.10(c) Determining income: prospective budgeting, anticipatin; `snap_cfr_273_10_10d` 7 CFR 273.10(d) Determining deductions: anticipated expenses, averagin; `snap_cfr_273_11_11b` 7 CFR 273.11(b) Boarders; (d) treatment centers; (e) group living arra; `snap_cfr_273_12_12c` 7 CFR 273.12(c) State agency action on changes; (e) mass changes (COLA; `snap_cfr_273_13_13a` 7 CFR 273.13(a) Notice of adverse action timing (10 days) and content; `snap_cfr_273_14_14b` 7 CFR 273.14(b) Recertification process, application, interview, notic; `snap_cfr_273_15_15` 7 CFR 273.15 Fair hearings: request period (90 days), timeliness, cont; `snap_cfr_273_16_16` 7 CFR 273.16 IPV disqualification: 12 months, 24 months, permanent; ad; `snap_cfr_273_18_18` 7 CFR 273.18 Claims against households: IHE, IPV, AE claims; 20/10 per; `snap_cfr_273_24_24e` 7 CFR 273.24(e) Regaining eligibility after the time limit
- **federal_with_state_option** (22): `snap_usc_2012_k` 7 USC 2012(k) Definition of food; State restaurant meals option for el; `snap_usc_2014_f` 7 USC 2014(f) Calculation of household income; prospective or retrospe; `snap_usc_2015_g` 7 USC 2015(g) Residents of States providing SSI state supplementary pa; `snap_usc_2015_i` 7 USC 2015(i) Comparable treatment for disqualification under other pr; `snap_usc_2015_l` 7 USC 2015(l) Custodial parent cooperation with child support agency (; `snap_usc_2015_m` 7 USC 2015(m) Noncustodial parent cooperation with child support agenc; `snap_usc_2015_n` 7 USC 2015(n) Disqualification for child support arrears (state option; `snap_usc_2020_e` 7 USC 2020(e) Requisites of State plan of operation: application proce; `snap_usc_2020_i` 7 USC 2020(i) Application and denial procedures; combined application ; `snap_usc_2020_s` 7 USC 2020(s) Transitional benefits option (state election); `snap_usc_2025_h` 7 USC 2025(h) Funding of employment and training programs; E&T state p; `snap_cfr_273_2_2e` 7 CFR 273.2(e) Interview requirements and telephone-interview waiver; `snap_cfr_273_2_2f` 7 CFR 273.2(f) Verification requirements (mandatory and optional); `snap_cfr_273_7_7c` 7 CFR 273.7(c) E&T program requirements and (e) components; State E&T ; `snap_cfr_273_7_7d` 7 CFR 273.7(d) E&T participant reimbursement and support services (tra; `snap_cfr_273_7_7f` 7 CFR 273.7(f) Failure to comply: sanction periods (1, 3, 6 months; st; `snap_cfr_273_8_8f` 7 CFR 273.8(f) Vehicle treatment (fair market value / equity tests; TA; `snap_cfr_273_10_10f` 7 CFR 273.10(f) Certification periods (up to 12 months; 24 months elde; `snap_cfr_273_11_11k` 7 CFR 273.11(k) Reduction of benefits for failure to comply with other; `snap_cfr_273_12_12a` 7 CFR 273.12(a) Reporting requirements: change reporting (10 days, $10; `snap_cfr_273_21_21` 7 CFR 273.21 Monthly reporting and retrospective budgeting (state opti; `snap_cfr_273_26_26` 7 CFR 273.26-273.32 Transitional benefits alternative (state option; 5
- **federal_regulation** (170): `snap_cfr_271_1` 7 CFR 271.1 General purpose and scope; `snap_cfr_271_2` 7 CFR 271.2 Definitions; `snap_cfr_271_3` 7 CFR 271.3 Delegations to FNS for administration; `snap_cfr_271_4` 7 CFR 271.4 Delegations to State agencies for administration; `snap_cfr_271_5` 7 CFR 271.5 Benefits as obligations of the United States, crimes and o; `snap_cfr_271_6` 7 CFR 271.6 Complaint procedure; `snap_cfr_271_7` 7 CFR 271.7 Allotment reduction procedures; `snap_cfr_271_8` 7 CFR 271.8 Information collection/recordkeeping—OMB assigned control ; `snap_cfr_271_9` 7 CFR 271.9 Promotional activities; `snap_cfr_272_1` 7 CFR 272.1 General terms and conditions; `snap_cfr_272_2` 7 CFR 272.2 Plan of operation; `snap_cfr_272_3` 7 CFR 272.3 Operating guidelines and forms; `snap_cfr_272_4` 7 CFR 272.4 Program administration and personnel requirements; `snap_cfr_272_5` 7 CFR 272.5 Program informational activities; `snap_cfr_272_6` 7 CFR 272.6 Nondiscrimination compliance; `snap_cfr_272_7` 7 CFR 272.7 Procedures for program administration in Alaska; `snap_cfr_272_8` 7 CFR 272.8 State income and eligibility verification system; `snap_cfr_272_9` 7 CFR 272.9 Approval of homeless meal providers; `snap_cfr_272_10` 7 CFR 272.10 ADP/CIS Model Plan; `snap_cfr_272_11` 7 CFR 272.11 Systematic Alien Verification for Entitlements (SAVE) Pro; `snap_cfr_272_12` 7 CFR 272.12 Computer matching requirements; `snap_cfr_272_13` 7 CFR 272.13 Prisoner verification system (PVS); `snap_cfr_272_14` 7 CFR 272.14 Deceased matching system; `snap_cfr_272_15` 7 CFR 272.15 Major changes in program design; `snap_cfr_272_16` 7 CFR 272.16 National Directory of New Hires; `snap_cfr_272_17` 7 CFR 272.17 Substantial lottery or gambling winnings; `snap_cfr_272_18` 7 CFR 272.18 National Accuracy Clearinghouse; `snap_cfr_273_3` 7 CFR 273.3 Residency; `snap_cfr_273_6` 7 CFR 273.6 Social security numbers; `snap_cfr_273_12` 7 CFR 273.12 Reporting requirements; `snap_cfr_273_13` 7 CFR 273.13 Notice of adverse action; `snap_cfr_273_14` 7 CFR 273.14 Recertification; `snap_cfr_273_15` 7 CFR 273.15 Fair hearings; `snap_cfr_273_16` 7 CFR 273.16 Disqualification for intentional Program violation; `snap_cfr_273_17` 7 CFR 273.17 Restoration of lost benefits; `snap_cfr_273_18` 7 CFR 273.18 Claims against households; `snap_cfr_273_20` 7 CFR 273.20 SSI cash-out; `snap_cfr_273_21` 7 CFR 273.21 Monthly Reporting and Retrospective Budgeting (MRRB); `snap_cfr_273_23` 7 CFR 273.23 Simplified application and standardized benefit projects; `snap_cfr_273_25` 7 CFR 273.25 Simplified SNAP ...
- **federal_guidance** (1): `snap_g08` FY 2026 income eligibility standards: 165% FPL elderly/disabled separa
- **state** (30): `snap_s02` BBCE gross income threshold elected (130/165/185/200 percent of povert; `snap_s03` BBCE asset test waived or elected asset limit; `snap_s08` LIHEAP nominal-payment (heat-and-eat) SUA entitlement and post-OBBBA l; `snap_s10` Standard medical deduction (demonstration) amount and threshold; `snap_s22` Vehicle exclusion policy (federal FMV/equity tests or TANF vehicle-rul; `snap_s23` Simplified reporting election and periodic report requirements; `snap_s24` Certification period lengths by household type (state-set within 273.1; `snap_s25` Change reporting thresholds and timeframes (10 days; 130 percent gross; `snap_s29` Voluntary quit and reduction of work effort policy; `snap_s31` SNAP E&T State Plan (annual, filed with FNS); `snap_s32` State Plan of Operation (272.2) with elected options attachments; `snap_s33` Transitional benefits alternative (TBA) election and period; `snap_s38` Drug-felony disqualification: state opt-out or modification (21 USC 86; `snap_s39` Combined application project / elderly simplified application project; `snap_s40` Restaurant meals program election; `snap_s41` Interview mode (telephone/on-demand) and interview waiver policy; `snap_s42` Expedited service criteria and timeframe as applied; `snap_s43` Verification standards: mandatory items, acceptable documents, questio; `snap_s44` Fair hearing procedures and timeframes; `snap_s45` IPV disqualification periods and administrative disqualification heari; `snap_s46` Claims and overpayment recovery (IHE/AE/IPV; allotment reduction; comp; `snap_s48` Residency requirement as applied; `snap_s49` Social security number requirement as applied; `snap_s55` Prospective budgeting / income anticipation and conversion factors (4.; `snap_s56` Notice of adverse action / advance notice period as applied; `snap_s57` Recertification and notice of expiration process as applied; `snap_s58` Treatment center / group living / shelter resident rules as applied; `snap_s59` SSI cash-out / SSI recipients' treatment (CA CalFresh expansion, state; `snap_s60` Fleeing felon / parole violator disqualification as applied; `snap_s61` Lottery/gambling winnings disqualification threshold as applied

`pe_modeled` is recorded per element in the schema and per row in the matrix; `rulespec_scoped` records whether rulespec-us encodes the source or a state program spec cites it (federal elements are computed from the rulespec-us file tree and the `programs/*/snap` scope lists).

## Schema notes and uncertainty

- Federal statute elements are every section of 7 USC ch. 51 (2011-2036d; 2030 and 2033 are repealed container rows) plus every subsection of 2012, 2014, 2015 and 2017 and the state-plan subsections 2020(e),(i),(s) and 2025(h); 2012 subsections a-i, l, n-q, s-t, v are definitional and folded into the 2012 section element.
- Federal regulation elements are every non-reserved section of 7 CFR 271-285 as listed by the eCFR structure API (current edition, read 2026-09-12) plus 54 paragraph-level elements of 7 CFR 273. The selected 273 scopes are section-granular (273.2 is one 154 KB body), so paragraph elements are verified by keyword over the section body, not by citation path; 7 CFR 246 is paragraph-granular in its scope.
- Schema uncertainty: the paragraph-level split of 273 is a reviewer's reading of the section headings, not an exhaustive paragraph list; 273.2 (application processing) and 273.7 (work provisions) each carry more distinct facts than the elements enumerated here.
- Federal guidance elements: the FY 2026 COLA tables and income standards are read from the two-page FNS tables held in the corpus (the 165% table is on page 2 of the income standards); the full COLA memo, which carries the minimum benefit, is a separate document. The FY 2024 COLA memo in the corpus is excluded from the FY 2026 checks. The State Options Report is listed as a cross-check only because the queue policy forbids it as a source.
- State elements: 61 elements grouped by carrying family. 'mandatory' means every state's rulebook must carry the fact (a restatement or a state-set value); optional elections (BBCE, homeless deduction, SMD, TBA, CAP/ESAP, RMP, drug-felony opt-out, state-funded supplements) are ABSENT when a fully inventoried rulebook carries no text for them.
- Regex evidence is a keyword search of provision bodies; a PRESENT hit cites the provision that matched and a snippet. A hit shows the rulebook text carries the fact, not that the encoder can read the exact value from that row (single-block manuals such as KY, RI put a whole volume in one provision).
- Table elements (snap_s15-s18, s20) ask for the state's own applied FY 2026 table; the federal FY 2026 value is present at the federal level, so an ABSENT/EXTRACTABLE there is a provenance gap, not a missing fact.

## Timing and searches

- Check run started 2026-09-12T09:19:38-0400, finished 2026-09-12T09:22:52-0400 (193.7 s for SNAP and WIC together); 128 scope files and 63884 provision rows read from `data/corpus/provisions`.
- Searches: for every element with a `regex` in the schema, that regex was run (case-insensitive, dot matches newline) over every provision body of the jurisdiction's selected scopes listed in `summary.json` under `scopes`; citation-path elements were looked up by exact path (then by children with bodies). The eCFR structure was read once from `https://www.ecfr.gov/api/versioner/v1/structure/current/title-7.json` (5.3 MB) and the parts 246 and 271-285 section lists embedded in `cfr_structure.py`.
- Queue evidence: `manifests/snap-completion-agent-queue.yaml` (index_families, queue_status, index_url per state), `manifests/state-snap-manual-agent-queue.yaml`, `manifests/wic-agent-queue.yaml` (queue_status, index_inventory, notes), plus the reviewer facts transcribed from the 2026-09-10/11 run notes into the script's tables (`SNAP_BLOCKED`, `SNAP_TRANSMITTAL_FAMILY`, `SNAP_ET_PLAN_PUBLISHER`, `WIC_BLOCK_CLASS`, `WIC_STATE_PLAN_PUBLISHER`, `WIC_NOT_TAKEN_FAMILY`).
- Spot checks: the PRESENT snippets of every optional-election element and every table element were read for false positives after each run; regexes were tightened three times (BBCE, mandatory SUA, LIHEAP heat-and-eat, standard medical deduction, table elements, TBA, state-funded programs, restaurant meals, state minimum supplements, SSI cash-out; WIC adjunctive eligibility and temporary certification) and a per-element exclusion window added. Residual false positives are possible for elements whose wording varies by state; the cited row is always given so a reader can check.
