# TANF: needs-driven closure check (2026-09-11)

Question: does the corpus hold every source-document family a complete encoding of the TANF
rulebook needs, per jurisdiction (federal plus the 50 states and DC), and where not, is the gap
EXTRACTABLE, ABSENT, OUTREACH or REVIEW? The bar is the law's own structure; PolicyEngine is a
cross-check only. Files: `tanf-schema.yaml`, `tanf-matrix.csv`, `build_tanf_ccdf_matrix.py`,
`summary.json`, `tanf-present-cells.tsv` (the PRESENT cells, for sampling).

## Method

1. Schema (step 1). Federal statute 42 U.S.C. 601-619 section by section (20 elements); every
   live section of 45 CFR 260-265 from the eCFR title-45 structure snapshot of 2026-09-09 retained
   with the part 98 scope (128 elements, each flagged when it sets or bounds a state-level element);
   one ACF OFA guidance element; 32 state-level elements derived from the chapter structure of the
   selected state rulebooks (MT 400-19, ND 400-19, VA chapters 100-1000, TN 23-series, PA 100-192,
   WI W-2 chapters, MS Vol. III, CA MPP 40-44, CO 9 CCR 2503-6, DE DSSM 4000, IA 441 IAC 40-47,
   NE 468 NAC 1-5, NM 8.102, OK 340:10, SD 67:10, VT 2000-2500, ID 16.03.08) and the 42 U.S.C.
   602(a) plan contents. Each state element carries a `facts` list naming what an encoder reads
   (e.g. tanf-s06: maximum grant by unit size, regional tables, adult-included vs child-only
   tables, ratable-reduction factor, effective date). 181 elements in total.
2. Check (step 2). Selected scopes are the 2026-09-11 union selector plus
   `us/regulation/2026-09-11-title-45-part-98`; the per-state TANF scopes searched are listed in
   `TANF_SCOPES` in the builder (all verified against the selector JSON). PRESENT requires a
   provision body in a selected scope whose heading matches the element's pattern, or whose body
   matches it at least twice; the scope, `citation_path` and a snippet are recorded. A single body
   mention is reported as REVIEW with the candidate path. For HI, ME, MD and NC the on-disk but
   unselected July scopes are searched too: a hit there is EXTRACTABLE (re-selection closes it).
   EXTRACTABLE otherwise comes from the queue rows and run notes (publisher lists the document;
   slice taken; DSSM 3000 not taken), OUTREACH from the recorded NY bot wall, REVIEW when the
   evidence does not decide. Federal elements are checked once at `us` and inherited.
3. Cross-check (step 3). PolicyEngine `gov/hhs/tanf` (20 parameter files) and 46 state TANF
   trees; rulespec-us `programs/us-*/tanf/fy-2026.yaml` (15 states, every one with
   `acknowledged_incomplete`).

Row convention: state elements have one row per state (32 x 51 = 1,632); federal elements have
one row at `us` (149) and are inherited, so `tanf-matrix.csv` has 1,781 rows and every
(jurisdiction, element) pair that applies has exactly one row.

## Results

| | cells | PRESENT | EXTRACTABLE | OUTREACH | ABSENT | REVIEW |
|---|---:|---:|---:|---:|---:|---:|
| federal (us) | 149 | 0 | 148 | 0 | 0 | 1 |
| state (51 x 32) | 1,632 | 1,140 | 152 | 12 | 0 | 328 |
| all | 1,781 | 1,140 | 300 | 12 | 0 | 329 |

No cell is ABSENT: no TANF queue row records a publisher that posts nothing.

The federal layer is the single largest gap and is uniform: 42 U.S.C. 601-619 is in no
`us/statute` scope (citation_path scan of every `data/corpus/provisions/us/statute/*.jsonl` for
`us/statute/42/601`-`619`: 0 rows) and 45 CFR 260-265 is in no `us/regulation` scope (only parts
98 and 1302 of title 45 exist). Both publishers (uscode.house.gov, eCFR Versioner API) already
serve the corpus, and the eCFR adapter's gzip requirement was fixed on 2026-09-11, so these 148
elements are EXTRACTABLE with no adapter work: `extract-uscode` for title 42 chapter 7
subchapter IV part A and `extract-ecfr --only-title 45 --only-part 260..265`.

### QA sample of PRESENT cells

40 PRESENT cells drawn at random (seed 20260912) were read by hand around the matched text:
29 cite the carrying provision (e.g. CO 3.606.8 diversion, NM 8.102.410.18 lifetime limits,
TN 23.05 gross income standard 185% of CNS, SC page 154 EBT locations, ND 400-19-45-40-25-10
five-year ban); 6 cite a provision that carries the topic but is not the primary section (IA
45.27 rounding cited for the payment standard, TN 23.24 work incentive payment cited for the
maximum grant, KY and UT caretaker-relative cooperation pages for the relationship rule, IL
budgeting history page for disregards, CT program-standards chart page); 5 are false positives
(UT Refugee Cash Assistance non-citizen status for tanf-s04, DC Transitional Medicaid page for
tanf-s30, WV benefit-repayment page for tanf-s06, WI verification list mentioning motor vehicle
registration for tanf-s12, CT standards chart for tanf-s06). Read as a rate, PRESENT overstates
carrying-provision coverage by roughly 10-15 percent, concentrated in page-level scopes (WV, DC,
NJ, MS, VA, AR, KY, TN, VT, AL, SC pages carry no section headings) and in combined manuals.
The stricter evidence rule moved 137 single-mention cells from the earlier draft's PRESENT to
REVIEW; the 40-cell sample is the basis for the "roughly" above, not a full audit.

## Per-jurisdiction roll-up

The table lists, per state, the state-element cells by status and the most common gap note
(truncated). Structural findings first:

- Four states are "done" in the TANF queue by pointer to a scope that is on disk but not in
  the 2026-09-11 union selector (it was in the July foundation releases only): HI (HAR
  17-656/676/678), ME (10-144 CMR ch. 331), MD (COMAR 07.03.03), NC (Work First section 114
  only). Their selected scopes are empty (HI, NC) or a chart (ME Rule 125A, 2 rows; MD IM 26-13,
  4 rows). Re-selecting the four scopes closes 19 + 25 + 16 + 13 = 73 EXTRACTABLE cells at once;
  NC additionally needs the other Work First sections from policies.ncdhhs.gov.
- Four states hold a slice of a rulebook the publisher posts whole: CT (13 UPM sections; 28
  EXTRACTABLE), GA (4 manual sections; 20), AZ (7 FAA topic pages plus the FAA5 recovery scope;
  13), DE (DSSM 4000 only; the 3000-series TANF program rules were never taken although the queue
  row says "DSSM 3000 already ingested"; 17).
- Idaho's selected rule (IDAPA 16.03.08, 2026 zero-based rewrite, 18 sections) names household
  members, cooperation, IRP, sanctions and overpayments but carries no need or payment standard,
  income limit, disregard, resource limit, time limit or work-hour rule; 25 REVIEW cells. Where
  Idaho publishes those values (the TAFI State Plan; IDHW's TAFI page links no manual) was not
  inventoried.
- New York: the Temporary Assistance Source Book is behind an F5/TSPD bot wall (12 OUTREACH
  cells); the 2024-2026 TANF State Plan carries 20 elements. 18 NYCRR parts 350-397 (the adopted
  rule, published by the Department of State) were never inventoried and would close most of
  the 12 without OTDA's cooperation.
- Wyoming's POWER manual is three document-level blocks (up to 84K characters) so matches cite a
  whole block (13 REVIEW). South Dakota (15 REVIEW) and Texas (12 REVIEW) are whole rulebooks
  where the patterns did not find the element; SD's rule is terse and TX's Texas Works Handbook
  uses its own vocabulary (e.g. "budgetary needs", "recommended grant").

### Top gaps by how many states share them

| gap | states affected | class | what closes it |
|---|---:|---|---|
| 42 U.S.C. 601-619 (20 elements) and 45 CFR 260-265 (128 elements) absent | 51 (inherited) | EXTRACTABLE | `extract-uscode` title 42 ch. 7 subch. IV-A; `extract-ecfr --only-title 45 --only-part 260..265` (adapter ready) |
| tanf-s32 state TANF plan document | 49 (48 REVIEW, MT EXTRACTABLE); AL and NY PRESENT | REVIEW | the TANF queue's family is manuals/adopted rules only and ACF OFA posts no plan index; inventory each state's posted plan (MT lists it on the manual page) |
| tanf-s18 child-care exception to sanctions (single parent, child under six) | 43 (38 REVIEW) | REVIEW | the definitions live in CCDF plan 2.2.9, PRESENT for 43 states in `ccdf-matrix.csv` (ccdf-s24); cross-program closure rather than new extraction |
| tanf-s02 dependent child age limit and student extension | 32 (25 REVIEW) | REVIEW | vocabulary check: the rule is in every state's eligibility chapter; the pattern under-matches page-level scopes |
| tanf-s29 EBT access restrictions | 27 (21 REVIEW) | REVIEW | often in a separate EBT rule or the state plan; check per state |
| tanf-s12 vehicle limit, s21 diversion, s24 FVO | 26 each | REVIEW | optional elements: REVIEW cannot be turned into ABSENT without reading the rulebook |
| whole-rulebook re-selection (HI, ME, MD, NC) | 4 | EXTRACTABLE | add the four July scopes to the selector (73 cells) |
| slice taken, publisher posts whole (CT, GA, AZ, DE) | 4 | EXTRACTABLE | take the full UPM, Georgia TANF manual, FAA1-FAA6, DSSM 3000 (78 cells) |
| NY Source Book | 1 | OUTREACH | OTDA cooperation, or inventory 18 NYCRR on the DOS publisher |

Gap cells by carrying family (state level): state regulation/manual 443 (146 EXTRACTABLE, 12
OUTREACH, 285 REVIEW, incl. the assistance-unit chapter); state TANF plan 49 (1 EXTRACTABLE, 48
REVIEW). Every REVIEW cell in the matrix carries the scope searched and, where one exists, the
single-mention candidate path, so a reviewer can resolve it without re-running the search.

## Elements beyond PolicyEngine

PolicyEngine models 9 of the 32 state elements fully (age limit and student extension, need
standard, payment standard, income tests, earned income disregards, dependent care deduction,
resource limit, benefit computation, unearned income treatment) and 8 partially (assistance
unit composition, immigrant eligibility, child support pass-through, vehicle limits, work hours,
sanctions for DC only, teen parents for MA/AZ, child-only for IL/TX). The law has 15 state
elements PolicyEngine does not model at all: tanf-s03 relationship/living-with, s14 time limits
and hardship extensions, s16 countable work activities, s18 child-care exception, s19 IRP, s21
diversion, s23 residency, s24 FVO, s25 application/redetermination/reporting, s26 notices and
hearings, s27 overpayments/IPV, s28 disqualifications (fugitive/drug felony/fraud), s29 EBT
restrictions, s30 transitional/supportive services, s32 the state plan. At the federal level
PolicyEngine cites 42 U.S.C. 607/608 for two variables and models nothing of 45 CFR 260-265.
The rulespec-us wrappers (15 states) encode the same subset PolicyEngine does (need/payment
standards, disregards, income tests, resource limits) and every one lists its eligibility
judgment under `acknowledged_incomplete`; the corpus already carries the time-limit, work,
sanction and unit rules for 37-45 states (tanf-s14/s15/s17/s01 PRESENT counts), so the
encoding gap there is encoder work, not corpus work.

## Schema uncertainties

- The 42 U.S.C. 601-619 section list is from the compiler's knowledge of the title; the text is
  not in the corpus, so headings should be re-checked once extracted.
- The 32 state elements are a normalized cross-state list; states split or merge them (WI W-2
  placements replace need/payment standards; MN MFIP has a food portion; NH FANF and VT Reach Up
  use their own program structures). The `facts` lists are indicative, not exhaustive.
- Procedural elements (s25, s26, s27) are broad; PRESENT says the chapter exists.
- REVIEW is never converted to ABSENT for optional elements (diversion, drug-felony option, EBT
  penalties, FVO): absence of a pattern match does not show the state sets nothing.
- PRESENT is pattern evidence plus a 40-cell hand sample, not a full read; see the QA section.

## Timing and searches

Session 2026-09-12, 08:30-09:20 EDT (about 50 minutes wall; an earlier 2026-09-11 draft of the
builder in this worktree was reviewed, corrected and re-run rather than discarded). Builder runs:
TANF matrix 100 s, CCDF matrix 0.4 s (provision JSONL cached in memory). Searches run for this
report, all read-only against `/Users/pavelmakarchuk/axiom-corpus/data/corpus`:
citation_path scans of every `us/statute` file for 42 U.S.C. 601-619 and 9857-9858r (0 rows);
listing of `us/regulation` title-45 scopes (parts 98, 1302 only); selector membership check of
every `TANF_SCOPES` and `CCDF_RULEBOOK_ALLOW` entry; release-manifest grep for the four
unselected July scopes (foundation releases only); row-shape inspection of the AK, AL, AR, CT,
DE, GA, ID, MD, ME, NC, NJ, WY, OK-plan and NY scopes; a heading scan of every selected
TANF/combined scope for child-care subsidy chapters (feeds `CCDF_RULEBOOK_ALLOW`); PolicyEngine
parameter-tree walk (`gov/hhs/tanf`, `gov/hhs/ccdf`, `gov/states/*`); rulespec-us
`programs/us-*/tanf` and grep for CCDF. The queue rows and the seven TANF/CCDF run notes were read
in full and transcribed into the builder's constant tables with their source named.


## Generated roll-up tables (from summary.json, build of 2026-09-12)

### Per-jurisdiction roll-up (state-level elements)

| jurisdiction | PRESENT | EXTRACTABLE | OUTREACH | ABSENT | REVIEW | main gap note |
|---|---:|---:|---:|---:|---:|---|
| us-ak | 25 | 0 | 0 | 0 | 7 | no body in the selected scope(s) [regulation/2026-07-01-ak-atap-regulations, guidance/2026-07-01-ak-atap-stand |
| us-al | 22 | 0 | 0 | 0 | 10 | single body mention only at us-al/policy/2026-07-02-al-tanf-official-documents us-al/policy/dhr/tanf/state-pla |
| us-ar | 21 | 0 | 0 | 0 | 11 | single body mention only at us-ar/policy/2026-07-02-ar-tea-official-documents us-ar/policy/dhs/tea/manual/2024 |
| us-az | 18 | 13 | 0 | 0 | 1 | AZ DES FAA policy manual: 7 topic pages plus the 143-row FAA5 recovery scope are in the corpus |
| us-ca | 27 | 0 | 0 | 0 | 5 | no body in the selected scope(s) [regulation/2026-09-10-tanf-state-policy-manual, guidance/2026-06-24-ca-cdss- |
| us-co | 25 | 0 | 0 | 0 | 7 | single body mention only at us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated us-co/regulatio |
| us-ct | 3 | 28 | 0 | 0 | 1 | CT DSS Uniform Policy Manual: 13 UPM sections plus the 2026 standards chart are in the corpus (28 rows) |
| us-dc | 28 | 0 | 0 | 0 | 4 | single body mention only at us-dc/manual/2026-09-10-tanf-state-policy-manual us-dc/manual/dhs/tanf/esa-policy- |
| us-de | 14 | 17 | 0 | 0 | 1 | Delaware selected scope us-de/regulation/2026-07-03-de-tanf-rules holds DSSM section 4000 (Financial Responsib |
| us-fl | 24 | 0 | 0 | 0 | 8 | single body mention only at us-fl/manual/2026-05-27-fl-ess-manual-r2026-07-15-self-contained us-fl/manual/dcf/ |
| us-ga | 11 | 20 | 0 | 0 | 1 | Georgia TANF Policy Manual: only sections 1525, 1605, 1615 and Appendix A are in the corpus (47 block rows) |
| us-hi | 0 | 19 | 0 | 0 | 13 | found in unselected on-disk scope us-hi/regulation/2026-07-03-hi-tanf-admin-rules at us-hi/regulation/har/17/6 |
| us-ia | 29 | 0 | 0 | 0 | 3 | no body in the selected scope(s) [regulation/2026-07-03-ia-fip-admin-rules] matched the evidence patterns with |
| us-id | 7 | 0 | 0 | 0 | 25 | no body in the selected scope(s) [regulation/2026-09-10-tanf-state-policy-manual] matched the evidence pattern |
| us-il | 27 | 0 | 0 | 0 | 5 | single body mention only at us-il/manual/2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained us- |
| us-in | 28 | 0 | 0 | 0 | 4 | no body in the selected scope(s) [manual/2026-05-27-in-snap-manual-r2026-07-15-self-contained] matched the evi |
| us-ks | 28 | 0 | 0 | 0 | 4 | single body mention only at us-ks/manual/2026-05-27-ks-keesm-r2026-07-15-self-contained us-ks/manual/dcf/keesm |
| us-ky | 25 | 0 | 0 | 0 | 7 | single body mention only at us-ky/manual/2026-09-10-tanf-state-policy-manual us-ky/manual/dcbs/dfs/volume-iii- |
| us-la | 28 | 0 | 0 | 0 | 4 | no body in the selected scope(s) [manual/2026-09-10-tanf-state-policy-manual] matched the evidence patterns wi |
| us-ma | 25 | 0 | 0 | 0 | 7 | no body in the selected scope(s) [regulation/2026-06-27-ma-tafdc-regulations] matched the evidence patterns wi |
| us-md | 2 | 16 | 0 | 0 | 14 | found in unselected on-disk scope us-md/regulation/2026-07-03-md-tca-comar-publication-2026-06-29-title-07-sub |
| us-me | 3 | 25 | 0 | 0 | 4 | found in unselected on-disk scope us-me/regulation/2026-07-03-me-tanf-regulation at us-me/regulation/dhhs/ofi/ |
| us-mi | 24 | 0 | 0 | 0 | 8 | single body mention only at us-mi/manual/2026-07-17-mi-bridges-manual us-mi/manual/mdhhs/bridges/bem/230a/page |
| us-mn | 29 | 0 | 0 | 0 | 3 | single body mention only at us-mn/manual/2026-05-27-mn-combined-manual-r2026-07-15-self-contained us-mn/manual |
| us-mo | 28 | 0 | 0 | 0 | 4 | single body mention only at us-mo/manual/2026-09-10-tanf-state-policy-manual us-mo/manual/dss/tanf/0205-005-00 |
| us-ms | 28 | 0 | 0 | 0 | 4 | single body mention only at us-ms/manual/2026-09-10-tanf-state-policy-manual us-ms/manual/mdhs/tanf/volume-iii |
| us-mt | 28 | 1 | 0 | 0 | 3 | no body in the selected scope(s) [manual/2026-09-10-tanf-state-policy-manual] matched the evidence patterns wi |
| us-nc | 0 | 13 | 0 | 0 | 19 | not located by pattern in the selected scope(s) nor in the unselected on-disk scope |
| us-nd | 29 | 0 | 0 | 0 | 3 | single body mention only at us-nd/manual/2026-09-10-tanf-state-policy-manual us-nd/manual/hhs/tanf/400-19-05/b |
| us-ne | 25 | 0 | 0 | 0 | 7 | single body mention only at us-ne/regulation/2026-09-10-tanf-state-policy-manual us-ne/regulation/title-468/ch |
| us-nh | 27 | 0 | 0 | 0 | 5 | no body in the selected scope(s) [manual/2026-09-10-tanf-state-policy-manual] matched the evidence patterns wi |
| us-nj | 26 | 0 | 0 | 0 | 6 | no body in the selected scope(s) [regulation/2026-07-13-recovery] matched the evidence patterns with a heading |
| us-nm | 26 | 0 | 0 | 0 | 6 | single body mention only at us-nm/regulation/2026-09-10-tanf-state-policy-manual us-nm/regulation/nmac/8/102/1 |
| us-nv | 31 | 0 | 0 | 0 | 1 | state-published TANF plan not in the corpus and not inventoried: the TANF queue's document family is tanf_poli |
| us-ny | 20 | 0 | 12 | 0 | 0 | single body mention only at us-ny/policy/2026-08-09-ny-tanf-official-source-recovery-with-aliases us-ny/policy |
| us-oh | 26 | 0 | 0 | 0 | 6 | no body in the selected scope(s) [regulation/2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated] |
| us-ok | 27 | 0 | 0 | 0 | 5 | single body mention only at us-ok/regulation/2026-09-10-tanf-state-policy-manual us-ok/regulation/oac/340/10/3 |
| us-or | 26 | 0 | 0 | 0 | 6 | single body mention only at us-or/regulation/2026-09-10-tanf-state-policy-manual-chapter-461 us-or/regulation/ |
| us-pa | 30 | 0 | 0 | 0 | 2 | single body mention only at us-pa/manual/2026-09-10-tanf-state-policy-manual us-pa/manual/dhs/cash/104-applica |
| us-ri | 26 | 0 | 0 | 0 | 6 | single body mention only at us-ri/regulation/2026-09-10-tanf-state-policy-manual us-ri/regulation/218-ricr/20/ |
| us-sc | 29 | 0 | 0 | 0 | 3 | single body mention only at us-sc/manual/2026-09-10-tanf-state-policy-manual us-sc/manual/dss/tanf-policy-manu |
| us-sd | 17 | 0 | 0 | 0 | 15 | single body mention only at us-sd/regulation/2026-09-10-tanf-state-policy-manual us-sd/regulation/arsd/67/10/0 |
| us-tn | 27 | 0 | 0 | 0 | 5 | no body in the selected scope(s) [manual/2026-09-10-tanf-state-policy-manual] matched the evidence patterns wi |
| us-tx | 20 | 0 | 0 | 0 | 12 | no body in the selected scope(s) [manual/2026-05-27-tx-manuals-r2026-07-15-self-contained] matched the evidenc |
| us-ut | 26 | 0 | 0 | 0 | 6 | no body in the selected scope(s) [regulation/2026-07-02-ut-fep-official-documents, manual/2026-05-27-ut-manual |
| us-va | 26 | 0 | 0 | 0 | 6 | single body mention only at us-va/manual/2026-09-10-tanf-state-policy-manual us-va/manual/dss/tanf/chapter-100 |
| us-vt | 23 | 0 | 0 | 0 | 9 | single body mention only at us-vt/regulation/2026-09-10-tanf-state-policy-manual us-vt/regulation/dcf/esd-rule |
| us-wa | 28 | 0 | 0 | 0 | 4 | single body mention only at us-wa/manual/2026-07-21-wa-eaz-manual us-wa/manual/dshs/eaz/esa-eligibility-z-manu |
| us-wi | 23 | 0 | 0 | 0 | 9 | no body in the selected scope(s) [manual/2026-09-10-tanf-state-policy-manual] matched the evidence patterns wi |
| us-wv | 26 | 0 | 0 | 0 | 6 | single body mention only at us-wv/manual/2026-07-21-wv-income-maintenance-manual us-wv/manual/bfa/income-maint |
| us-wy | 19 | 0 | 0 | 0 | 13 | no body in the selected scope(s) [manual/2026-05-27-wy-manuals-r2026-07-15-self-contained] matched the evidenc |

### Elements by number of states not PRESENT

| element | name | PRESENT | EXTRACTABLE | OUTREACH | ABSENT | REVIEW |
|---|---|---:|---:|---:|---:|---:|
| tanf-s32 | State TANF plan (42 U.S.C. 602(a)) as a certified document | 2 | 1 | 0 | 0 | 48 |
| tanf-s18 | Child-care exception to work sanctions for single parents of children under six | 8 | 4 | 1 | 0 | 38 |
| tanf-s02 | Dependent child age limit and student extension | 19 | 6 | 1 | 0 | 25 |
| tanf-s29 | EBT access restrictions (liquor stores, casinos, adult entertainment) | 24 | 6 | 0 | 0 | 21 |
| tanf-s12 | Vehicle exclusion / equity limit | 25 | 5 | 1 | 0 | 20 |
| tanf-s21 | Diversion / one-time non-recurrent short-term benefits (state design) | 25 | 3 | 1 | 0 | 22 |
| tanf-s24 | Family Violence Option: screening, good-cause waivers of requirements | 25 | 6 | 0 | 0 | 20 |
| tanf-s05 | Need standard (standard of need) by family size and region | 31 | 4 | 0 | 0 | 16 |
| tanf-s10 | Dependent care and work-related expense deductions | 34 | 3 | 0 | 0 | 14 |
| tanf-s22 | Child-only cases and non-needy / ineligible caretaker relatives (incl. kinship payments) | 35 | 1 | 0 | 0 | 15 |
| tanf-s19 | Individual responsibility plan / assessment (state design) | 36 | 6 | 1 | 0 | 8 |
| tanf-s07 | Income eligibility tests for applicants and recipients (gross/net limits) | 37 | 1 | 1 | 0 | 12 |
| tanf-s14 | Lifetime time limit (60 months or shorter) and hardship extensions/exemptions | 37 | 8 | 0 | 0 | 6 |
| tanf-s16 | Countable work activities (core and non-core) and limits on education/job search | 37 | 5 | 0 | 0 | 9 |
| tanf-s28 | Disqualifications: fugitive felons, drug-felony option, fraud/misrepresentation of residen | 37 | 6 | 1 | 0 | 7 |
| tanf-s30 | Transitional and supportive services (transitional child care, transportation, work suppor | 39 | 6 | 1 | 0 | 5 |
| tanf-s11 | Resource (asset) limit and countable/excluded resources | 40 | 3 | 0 | 0 | 8 |
| tanf-s23 | State residency and temporary absence | 40 | 5 | 1 | 0 | 5 |
| tanf-s03 | Relationship to caretaker relative and living-with requirement | 41 | 6 | 0 | 0 | 4 |
| tanf-s13 | Benefit computation (deficit, proration, rounding, minimum grant) | 41 | 5 | 1 | 0 | 4 |
| tanf-s20 | Minor (teen) parent rules: school attendance and adult-supervised living arrangement | 42 | 6 | 1 | 0 | 2 |
| tanf-s25 | Application, verification, redetermination and change reporting (procedural rules, effecti | 42 | 8 | 0 | 0 | 1 |
| tanf-s26 | Notices and fair hearings / appeals | 42 | 7 | 0 | 0 | 2 |
| tanf-s04 | Citizenship and immigrant eligibility (qualified alien, five-year bar, state option) | 43 | 5 | 0 | 0 | 3 |
| tanf-s09 | Child support assignment, cooperation, pass-through and disregard | 43 | 5 | 0 | 0 | 3 |
| tanf-s08 | Earned income disregards (applicant and recipient; flat and percentage) | 44 | 3 | 0 | 0 | 4 |
| tanf-s01 | Assistance unit composition (who must be included; mandatory and optional members) | 45 | 5 | 0 | 0 | 1 |
| tanf-s06 | Payment standard / maximum grant by family size and region | 45 | 3 | 0 | 0 | 3 |
| tanf-s15 | Work requirements: participation hours, exemptions, work-eligible individuals | 45 | 5 | 0 | 0 | 1 |
| tanf-s17 | Sanctions for work non-compliance (pro-rata or full-family, duration, cure) and good cause | 45 | 6 | 0 | 0 | 0 |
| tanf-s31 | Unearned income treatment, exclusions, deeming (stepparent, sponsor), lump sums | 45 | 4 | 1 | 0 | 1 |
| tanf-s27 | Overpayments, underpayments, recovery and intentional program violations | 46 | 5 | 0 | 0 | 0 |

### Gap cells by carrying family

| family | EXTRACTABLE | OUTREACH | ABSENT | REVIEW | total |
|---|---:|---:|---:|---:|---:|
| state regulation/manual | 146 | 12 | 0 | 279 | 437 |
| state TANF plan (state-published | 1 | 0 | 0 | 48 | 49 |
| state regulation/manual (assistance unit chapter) | 5 | 0 | 0 | 1 | 6 |

### Federal rows

{'EXTRACTABLE': 148, 'REVIEW': 1}
