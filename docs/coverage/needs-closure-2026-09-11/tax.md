# Needs-driven closure check: individual income tax (federal + 50 states + DC)

Date: 2026-09-11 (run 2026-09-12, 08:44 to 09:30 EDT). Branch `analysis/needs-closure-tax`.
Read-only against `data/corpus`; the outputs are `tax-schema.yaml`, `tax-matrix.csv`,
`tax-stats.json` and the generator `tax-check.py` in this folder.

Question answered: does the corpus, as selected by
`docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json`, hold every
source-document family a complete encoding of the income tax rulebook needs, per
jurisdiction, and where not, is the gap extractable, absent, outreach, or review?

Short answer: **no jurisdiction is closed.** The federal statute core, the TY2025 IRS
forms core and the TY2026 revenue procedure are present; 26 CFR part 1 is essentially
absent (one section); 31 individual-facing IRC sections and 16 IRS products are not taken.
Of the 42 income-tax states, 24 hold their whole individual income tax chapter and 18 hold
a handful of sections; no state holds its revenue-department income tax regulations; 28
states lack a TY2025 resident return and 30 lack any TY2026 indexed-amount document in
the selection.

## Method

1. **Schema from the law, not from PolicyEngine.** Federal elements are facts read section
   by section from 26 U.S.C. subtitle A chapter 1 (subchapters A and B; individual-facing
   parts of D, E, F, N, O, P), chapters 2, 2A, 21, 24, 61, 65, 68 and 79, the 26 CFR part 1
   and part 31 families, the annual revenue procedures, notices and SSA determinations, and
   the IRS forms, schedules, instructions and publications (164 elements, `F001`-`F164`).
   State elements are the facts a section-by-section reading of a state individual income
   tax chapter yields (imposition, conformity date, residency, filing statuses, starting
   point, rate schedule, indexing, standard deduction, itemized treatment, personal and
   dependent exemptions, aged/blind amounts, additions, subtractions, Social Security,
   pensions, military, capital gains, EITC and its deviations, child credit amount and
   phase-out, CDCC, other-state credit, low-income relief, circuit breaker, other credits,
   AMT, surtax, nonresident apportionment, withholding, estimated tax, filing threshold,
   due dates, local taxes), the regulations chapter, and the annual products (TY2025 return,
   instruction booklet, printed rate schedule, printed deduction/exemption amounts, printed
   EITC/child-credit parameters, TY2026 indexed amounts) (42 elements, `S01`-`S35`, `R01`,
   `F01`-`F06`). A federal element appears once (jurisdiction `us`) and is inherited by all
   51 jurisdictions; a state element has 51 rows. 164 + 42 x 51 = 2,306 cells.
2. **Evidence by reading bodies.** For every cell the script reads the provision bodies of
   the selected scopes for that jurisdiction (statute rows restricted to the income-tax
   chapter by a per-state citation-path filter, plus the tax form/guidance scopes) and
   matches an element-specific regular expression; the matched snippet is quoted in
   `evidence_note`. A document title never makes a cell PRESENT. Whole-chapter dumps over
   200k characters count as weak evidence and are flagged in the note.
3. **Statuses.** PRESENT (body carries the fact, scope version and citation_path cited);
   EXTRACTABLE (the rule exists and the publisher posts the carrying family; not taken);
   ABSENT (the rule exists but the publisher posts nothing carrying it); OUTREACH (queue
   records a publisher block); REVIEW (could not tell); and **N/A** (the jurisdiction's law
   has no such rule, e.g. the nine no-broad-tax states, or a state without an EITC). N/A is
   an addition to the five requested statuses; it keeps ABSENT honest. A statute-family
   fact that is only carried by a form or guidance body is EXTRACTABLE, not PRESENT (the
   enabling section is the carrier the encoder must read); the two exceptions are S01
   (imposition/bar) and S29 (surtax and its annual threshold), where guidance may carry it.
4. **Cross-checks.** `pe_modeled` reads the PolicyEngine-US parameter tree
   (`gov/irs`, `gov/states/<st>/tax`, `gov/local`, commit 84253b6a); `rulespec_encoded`
   reads rulespec-us `us/statutes/26`, `us/policies/irs` and `us-<st>/policies/income_tax`
   plus the state statute encodings (commit c8951033). Document carriers (forms,
   regulations) show `n/a (document carrier)` in `pe_modeled`.
5. **Analyst knowledge, flagged.** Whether a state has an EITC, a child credit, a CDCC, an
   AMT, a surtax, local income taxes, a standard deduction, exemptions, a capital-gains
   preference, indexing, low-income relief or a circuit breaker (TY2025 law) is encoded in
   `tax-check.py` (`K`) and drives the N/A rows. Every such note says "analyst knowledge,
   verify". The sets are listed in `tax-schema.yaml` under `known_law_sets`.

Searches run (all against the 52,015 statute/regulation/form/guidance rows of the 264
selected US scopes; runtime about 34 s per pass, about ten passes while calibrating):
section-presence scan of `us/statute/26/<n>`; 26 CFR presence scan of `us/regulation`;
product-id scan of `us/form/irs/ty2025/<id>`; dollar-figure scans of the 2025 Form 1040
instructions, Pub 17, Schedule 8812/D/SE instructions, Rev. Proc. 2025-32 pages, Notice
2025-67, SSA determinations; per-state regex scans listed in `tax-check.py` (`S`), with
per-element reject lists after a false-positive review of S07, S12, S18, S19, S20, S25,
S26, S27 and S35 snippets (business credits, housing credits, withholding exemptions,
"state and local income taxes", cross-references).

## Counts

| | PRESENT | EXTRACTABLE | REVIEW | ABSENT | OUTREACH | N/A | total |
|---|---:|---:|---:|---:|---:|---:|---:|
| federal (164 elements, 1 row each) | 98 | 65 | 0 | 1 | 0 | 0 | 164 |
| states (42 elements x 51) | 794 | 641 | 30 | 0 | 0 | 677 | 2,142 |
| all | 892 | 706 | 30 | 1 | 0 | 677 | 2,306 |

Gap cells by family (EXTRACTABLE + REVIEW + ABSENT): state statute 474; state form
instructions and rate schedules 125; state regulation 42; federal statute 31; state
department bulletins 30 (REVIEW); IRS forms and instructions 16; IRS regulation 16; revenue
procedure 3.

## Federal roll-up (inherited by all 51 jurisdictions)

Present, with bodies read: sections 1 (rates, 1(f), 1(g), 1(h)), 2, 21, 22, 24, 25A-25E,
26, 27/901/904, 30D, 32, 36B, 55-59, 61-65, 67, 68, 85, 86, 102, 104, 112, 151, 152, 163,
164, 165, 170, 172, 199A, 212, 213, 219, 221, 223, 224, 225, 408, 1211, 1212, 1222, 1401,
1402, 1411, 3101, 3102, 3111, 3121, 3401, 3402, 3405, 3406, 6012, 6013, 6401, 7701, 7703
(scopes `us/statute/2026-07-13-recovery-r2026-07-15-self-contained-r2026-07-17-dedup`,
`2026-08-03-rulespec-title-26-current-union`, `2026-07-17-hr6644-dependency-closure-title-26`).
Annual amounts present: TY2025 brackets, tax table, capital-gain breakpoints, EITC table
and amounts, standard deduction, refundable CTC cap, AMT exemption, kiddie threshold (2025
Form 1040 instructions and Schedule 8812/D instructions, `us/form/2026-09-10-tax-irs-forms-ty2025`);
TY2026 brackets, EITC, CTC, AMT, standard deduction, aged/blind, 199A, kiddie amount
(Rev. Proc. 2025-32); 2026 retirement limits (Notice 2025-67); 2026 and 2027 section 36B
tables (Rev. Proc. 2025-25, 2026-26); 2027 HSA (Rev. Proc. 2026-24); 2026 mileage; SSA wage
base 2026 and 2025.

Gaps (65 EXTRACTABLE, 1 ABSENT):

- **31 IRC sections not in any selected `us/statute` scope**: 3, 23, 25, 31, 35, 53, 66,
  71/215, 72, 101, 103, 108, 117, 121, 125, 129, 132, 135, 137, 139, 162, 217, 401/402/403/457,
  415, 461, 469, 529/529A/530, 1001/1011-1016, 1250, 6654, 6072/6081. Carrier: the USLM
  title-26 release point the 2026-08-03 union scope was built from. One extraction closes
  all 31.
- **26 CFR part 1 and part 31**: only 1.1401-1 is selected (`2026-07-24-1401-coordination-repair-title-26-part-1`).
  Sixteen regulation families the encoder needs (1.1-1/1.2-2, 1.21, 1.32, 1.36B, 1.61-1.63,
  1.151-1.152, 1.162-1.165, 1.170A, 1.199A, 1.213/1.219/1.221, 1.401(k)-1.408A, 1.1001-1.1212,
  1.1411, 1.6012-1.6654, 31.3101-31.3402, 301.7701-18/1.7703-1) are EXTRACTABLE from eCFR.
- **16 IRS products not taken**: Schedules C, E, 1-A (OBBBA deductions worksheet), Forms
  2441, 8863, 6251, 8959/8960, 8995, 8880, 1040-ES (2026), W-4 (2026), 1040-SR, Publications
  501, 596, 970, and Pub 15-T (withholding tables). The queue row lists 35 index products,
  19 taken.
- **Rev. Proc. 2024-40** (TY2025 items OBBBA did not amend: EITC, AMT, 199A, kiddie tax)
  and **Rev. Proc. 2025-19** (2026 HSA) not taken (irs.gov/irb). The TY2025 figures are
  otherwise readable only from the 2025 form instructions.
- **TY2027 revenue procedure**: ABSENT, not yet issued as of 2026-09-10 (batch-1 note
  scanned IRB 2026-01..37).

## Per-jurisdiction roll-up (state elements; 42 rows per jurisdiction)

P = PRESENT, X = EXTRACTABLE, R = REVIEW, NA = N/A. Statute coverage describes what the
selected statute scopes hold for the income-tax chapter.

| st | P | X | R | NA | statute coverage in the selection |
|---|---:|---:|---:|---:|---|
| ak | 1 | 0 | 0 | 41 | AS 43.20.011-.013 (individual tax repealed 1980); bar PRESENT |
| al | 12 | 17 | 1 | 12 | 40-18-5, -15, -19 only; TY2025 forms + tax table + SD chart |
| ar | 6 | 26 | 1 | 9 | Act 2 of 2026 (rates) only; TY2025 forms + brackets |
| az | 14 | 21 | 0 | 7 | 43-1011, -1023, -1041, -1072, -1072.01, -1073, -1073.01; 2026 140ES only |
| ca | 16 | 23 | 0 | 3 | RTC 17041, 17043, 17045, 17052, 17054, 17073.5 + 11 short sections; 2025 rate schedule, 2026 540-ES |
| co | 28 | 6 | 1 | 7 | full title 39 (39-22 article); DR 0104 + Book 2025 |
| ct | 19 | 12 | 1 | 10 | 12-700(a)(10), 12-704e; 12-700/704e/704i as a 473k-char chapter dump |
| dc | 29 | 5 | 1 | 7 | full title 47 chapter 18; D-40 + booklet 2025 |
| de | 8 | 25 | 1 | 8 | 30/1102 plus five 6-27-char stubs (1108, 1109, 1110, 1114, 1117); PIT-RES + instructions + table |
| fl | 1 | 0 | 0 | 41 | constitution art. VII s. 5, ch. 220 (corporate), 2026 session law; bar PRESENT |
| ga | 27 | 6 | 1 | 8 | full title 48 (48-7); IT-511 2025 booklet |
| hi | 26 | 9 | 1 | 6 | full chapter 235; 2025 N-11 capital-gain worksheet only |
| ia | 30 | 7 | 1 | 4 | full chapter 422; IA 1040 + expanded instructions 2025 |
| id | 12 | 21 | 1 | 8 | 63-3022D, -3022E, -3024, -3024A, -3025D; Form 40 + instructions + 39R |
| il | 20 | 14 | 0 | 8 | 35 ILCS 5 core sections (201, 203, 204, 208, 212, 244 + 20 recovery sections); 2026 exemption notice |
| in | 28 | 4 | 0 | 10 | full title 6 (6-3, 6-3.1, 6-3.6); IT-40 + booklet 2025; 2026 rate notice |
| ks | 23 | 12 | 0 | 7 | full 79-32 article + 2026 core; 2026 K-40ES + rate notice |
| ky | 9 | 23 | 0 | 10 | KRS 141.020, 141.081 (recovery rows are 78-char stubs); 2026 740-ES |
| la | 22 | 9 | 0 | 11 | full title 47; 2026 IT-540ES |
| ma | 19 | 17 | 0 | 6 | ch. 62 ss. 3, 4, 6 (118k) + 9 minor; 2026 Form 1-ES; surtax guidance |
| md | 6 | 31 | 1 | 4 | TG 10-105, 10-211 only; queue pointer version null |
| me | 3 | 35 | 0 | 4 | 36/5111 body; 5124-C, 5126-A, 5213-A, 5219-S, 5219-SS are 158-char header stubs; 2026 rate schedules |
| mi | 15 | 17 | 0 | 10 | 206.30, 206.51, 206.272; 2026 rate notice |
| mn | 17 | 20 | 1 | 4 | 290.06, 290.0121, 290.0123, 290.067, 290.0671 as blocks; 2026 inflation bodies carry 2019 columns |
| mo | 23 | 11 | 1 | 7 | full chapter 143; queue pointer null |
| ms | 6 | 22 | 1 | 13 | 27-7-5 only; 80-105 + 80-100 2025 |
| mt | 24 | 11 | 1 | 6 | full 15-30; Form 2 + instructions 2025 |
| nc | 15 | 16 | 1 | 10 | 105-153.5, .7, .9, .11 + Part 2 as a 112k dump |
| nd | 18 | 9 | 1 | 14 | full 57-38 + 57-38-01.28 as 69 pages; queue pointer null |
| ne | 14 | 21 | 0 | 7 | 77-2715.03, -2715.07, -2716.01; 2026 1040N-ES |
| nh | 2 | 0 | 0 | 40 | RSA 77 chapter row (101 chars); TIR 2025-001 repeal (guidance) |
| nj | 24 | 11 | 1 | 6 | full title 54A; NJ-1040 + instructions 2025 |
| nm | 29 | 9 | 1 | 3 | full 7-2 article; PIT-1 + instructions + look-up table 2025 |
| nv | 1 | 0 | 0 | 41 | constitution art. 10 s. 1(9); bar PRESENT |
| ny | 26 | 13 | 1 | 2 | Tax Law 601, 606 (419k), 614, 615, 616 + 11 recovery sections; NYC 11-1701, -1704.1, -1706; IT-201/215/216 instructions |
| oh | 8 | 26 | 1 | 7 | 5747.02, .025, .71, .98 only; HB 96 analysis; pointer null |
| ok | 29 | 8 | 1 | 4 | full title 68 (68-23xx); 511 packet 2025 |
| or | 27 | 11 | 0 | 4 | full chapter 316 + 315.264/315.266 dumps; 2026 OR-ESTIMATE |
| pa | 13 | 17 | 1 | 11 | full article III; rate-table guidance (172 chars) |
| ri | 24 | 10 | 1 | 7 | full 44-30; ADV 2025-22 (TY2026 amounts) |
| sc | 19 | 12 | 1 | 10 | full 12-6; pointer null |
| sd | 1 | 0 | 0 | 41 | 10-43 bank tax boundary; sales-tax guide states no personal income tax |
| tn | 2 | 0 | 0 | 40 | Hall tax zero-rate act pages; DOR guidance |
| tx | 0 | 1 | 0 | 41 | queue pointer `2026-07-24-tx-individual-income-tax-prohibition` exists on disk but is NOT selected |
| ut | 8 | 21 | 1 | 12 | 59-10-104, -1018, -1019 only; TC-40 + instructions 2025 |
| va | 10 | 23 | 1 | 8 | 58.1-320, -321, -322.03, -339.8 only; pointer null |
| vt | 30 | 7 | 1 | 4 | full chapter 151; IN-111 + instructions + rate schedules 2025 |
| wa | 3 | 2 | 0 | 37 | RCW 82.87 (capital gains excise) full; DOR income-tax page; WFTC statute (82.08.0206) not selected |
| wi | 27 | 9 | 1 | 5 | full chapter 71 (71.05 100k, 71.07 208k); 2026 Form 1-ES |
| wv | 20 | 10 | 1 | 11 | full 11-21; pointer null |
| wy | 0 | 1 | 0 | 41 | queue pointer `2026-07-24-wy-individual-income-tax-absence` and the art. 15 s. 18 constitution scope exist on disk but are NOT selected |

## Top gaps by how many states share them, and what closes each class

1. **State income tax regulations (R01): 42 of 42 income-tax states.** No selected
   `us-xx/regulation` scope is a revenue-department income tax regulation; every selected
   regulation scope is a benefit-program rule (SNAP, TANF, Medicaid, CHIP, SSI, WIC). Close:
   one regulation extraction per state from the state's administrative code publisher
   (e.g. 18 CCR div. 3 ch. 2.5, 20 NYCRR part 100 et seq., 86 Ill. Adm. Code 100, 10 CCR
   2506-1 is NOT tax); a new work order, not a fetch of anything already indexed.
2. **TY2026 indexed amounts (F06): 30 states REVIEW, 12 PRESENT.** Present where a 2026
   estimated-tax booklet or department notice was taken (AZ, CA, IL, IN, KS, KY, LA, MA,
   ME, MI, NE, OR); MN's 2026 inflation bodies carry columns labelled 2019 (extraction
   defect, REVIEW); 29 states have no 2026-labelled document. Close: take each department's
   2026 estimated-tax instructions or withholding/indexing bulletin (most publish TY2026
   figures there by October), and re-extract the MN table.
3. **Partial income-tax chapters (S12, S13, S14, S17, S15, S16, S10, S11, S02, S03 ... ):
   18 states hold only a few sections.** AL, AR, AZ, CA, CT, DE, ID, KY, MD, ME, MI, MN,
   MS, NE, NY (Tax Law), OH, UT, VA. In these states 20-35 statute elements are
   EXTRACTABLE because the section was never taken, not because it is hard to reach (the
   state legislature posts the chapter). Close: one whole-chapter statute extraction per
   state (40-18 AL, 26-51 AR, 43-10 AZ, RTC 17001-19802 CA, 12-700 et seq. CT, 30/11 DE,
   63-30 ID, KRS 141 KY, TG 10 MD, 36/8 ME, MCL 206 MI, 290 MN, 27-7 MS, 77-27 NE, Tax Law
   art. 22 NY, ORC 5747 OH, 59-10 UT, 58.1-3 VA), replacing the "recovery" fragments and the
   header-only stubs (DE 1108-1117, ME 5124-C et al., KY recovery blocks).
4. **TY2025 resident return and instruction booklet (F01: 28 states, F02: 24 states)**,
   and with them the printed rate schedule (F03: 24), printed deduction/exemption amounts
   (F04: 26) and printed EITC/child-credit parameters (F05: 23). The queue marks 34 states
   "done by pointer", but nine pointers are estimated-tax products (AZ 140ES, CA 540-ES,
   KS K-40ES, KY 740-ES, LA IT-540ES, MA 1-ES, NE 1040N-ES, OR OR-ESTIMATE, WI 1-ES), six
   are statute-only or rate notices (CT, IL, MI, MN, NC, PA), one is a worksheet (HI N-11
   capital gain), one holds instructions without the form (NY IT-201), and seven have a
   null version (MD, MO, ND, OH, SC, VA, WV). Close: run the batch-1 pattern
   (`scripts/build_tax_forms_manifests.py`) for these 24-28 states; every publisher index
   is already recorded in the queue rows for the 17 states done in September.
5. **Federal regulations and secondary IRS products (16 + 16 elements, inherited by all
   51).** Close with one eCFR title-26 part-1/part-31 extraction and one forms manifest
   extension (Schedules C/E/1-A, Forms 2441/8863/6251/8959/8960/8995/8880/1040-ES/W-4/
   1040-SR, Pubs 501/596/970/15-T).

Smaller classes: local income tax statutes (S35: 13 states, the enabling acts sit outside
the income-tax chapter: ORC 718 and 5748, MCL 141.501, Pa. Local Tax Enabling Act, Mo.
ch. 92, TG 10-106, Iowa 257.21, KRS 68.180); other-state credit (S24: 15); child credit
amount and phase-out (S21/S22: 14-15, mostly the partial-chapter states plus CA 17052.1,
MN 290.0661, NY 606(c-1) in the 419k dump); WA Working Families Tax Credit (RCW
82.08.0206, not selected); S01 for TX and WY where the on-disk scopes need a selector
change, not a fetch.

## Data-quality findings a reviewer should act on

- `us-mn/guidance/2026-07-22-mn-income-tax-inflation-adjusted-amounts-2026`: the four
  bracket bodies (106-110 chars) read "2nd Bracket Threshold 2019 $33,310 ..."; the 2026
  columns were not captured.
- `us-de/statute/2026-07-13-recovery`: 30/1108, 1109, 1110, 1114, 1117 bodies are 6-27
  characters; `us-me/statute/2026-07-13-recovery`: 5124-C, 5126-A, 5213-A, 5219-S, 5219-SS
  carry only a 154-160-char title block; `us-ky/statute/2026-07-13-recovery`: 78-char
  blocks; `us-nh/statute/.../chapter-77`: 101 chars. These are stubs, not sections.
- Whole-chapter dumps used as section bodies: CT 12-700, 12-704e, 12-704i (473k chars
  each, identical), OR 315.264, 315.266 (331k), 316.085 (348k), NC Part 2 (112k), NY Tax
  Law 606 (419k), MI 206.30 repeated as seven identical 43k subsections. They make PRESENT
  cells weak (flagged in `evidence_note`) and need `section-provisions`.
- TX and WY zero-liability scopes exist on disk (`us-tx/statute/2026-07-24-tx-individual-income-tax-prohibition`,
  `us-wy/guidance/2026-07-24-wy-individual-income-tax-absence`, `us-wy/statute/2026-07-24-wy-constitution-income-tax-credit`)
  but are not in the 2026-09-11 selector; the queue rows say "done".
- SD's pointer is a sales-and-use tax guide (the "no personal income tax" sentence is on
  page 3); AK's pointer is AS 43.20.011, whose individual subsections read "[Repealed]".
  Both are evidence of the bar, but thin.

## PolicyEngine cross-check: what the law has that PE does not model

Federal (46 elements with `pe_modeled: no`, of 164): kiddie tax (1(g)); tax tables (3);
adoption credit (23) and adoption assistance exclusion (137); mortgage credit certificate
(25); credit ordering (26); foreign tax credit (27/901/904); withholding credit (31); HCTC
(35); prior-year minimum tax credit (53); 72(t) penalty; exclusions 101, 102, 104-106,
108, 112, 117, 121, 125, 132, 135, 139; NOL (172); 212; moving (217); HSA (223) and the
2026/2027 HSA amounts; IRA/Roth rules (408/408A); 415 limits; 461(l); 469; 529/529A/530;
basis (1001-1016); unrecaptured 1250; community income (66); withholding statute and Pub
15-T (3401-3406); joint-return rules (6013); 6401; estimated-tax penalty (6654); due
dates (6072/6081); marital status (7703/7701(b)); mileage rates; the TY2025 kiddie
threshold. What PE lacks is the return's periphery (exclusions, retirement-account rules,
basis, withholding and payment mechanics), not the Form 1040 arithmetic.

State (562 non-N/A cells with `pe_modeled: no`, of 1,465): seven elements for which the
PE state trees hold no parameters at all (7 x 42 = 294 cells): IRC conformity date (S02),
residency definitions (S03), credit for taxes paid to other states (S24), nonresident
apportionment (S30), withholding (S31), estimated tax (S32), due dates and joint liability
(S34); filing thresholds (S33) only in NJ and VA (40 cells). Then
military pay/retirement subtraction (S17: 36 states), other-state bond interest addition
(S13: 25), Social Security treatment (S15: 22) and pension exclusions (S16: 22; PE often
folds these into a generic subtraction), starting-point definition (S05: 20; PE hardcodes
it), circuit breakers (S26: 18), capital-gains preferences (S18: 11 of 17), aged/blind
amounts (S12: 9), local taxes (S35: 7 of 15; PE has gov/local for CO, DE, KY, MD, MO, NY,
OR, PA), CDCC (S23: 7), personal/dependent exemptions (S10/S11: 6 each).

rulespec-us encodes the federal chain 1(j), 24, 26, 32, 55 plus 61-63, 151-152, 163-164,
199A, 1401-1411, 3101-3406 and the Rev. Proc. 2025-32 / Notice 2025-67 / Rev. Proc.
2025-25 policies; every state has an `income_tax` pipeline file (49 of 51 jurisdictions
flagged `yes` on S06), but the wrappers under `programs/us/fiit` and `programs/us-ny/income-tax`
list every output as `acknowledged_incomplete`, and only NH and NY have income-tax program
wrappers at all.

## What the schema is unsure of

- The known-law sets (`K` in `tax-check.py`, `known_law_sets` in the schema) are analyst
  knowledge of TY2025 law: state EITC (32 incl. DC and WA), child credits (18 incl. NC's
  deduction and GA's 2026 credit), CDCC (29), AMT (CA, CO, CT, MN), surtax/special taxes
  (CA, MA, NY, NH, TN, WA), local income taxes (15), no-standard-deduction states (13),
  no-itemized states (10), no-exemption states (6), capital-gains preferences (17),
  indexed states (21), low-income relief (19), circuit breakers (31). Any error moves cells
  between N/A and EXTRACTABLE; it never creates a PRESENT.
- Regex evidence can miss a differently phrased fact (false EXTRACTABLE) or match a
  cross-reference (false PRESENT). The reviewed classes were tightened; residual risk is
  highest for S27 (other credits, a catch-all), S26 (circuit breakers inside long credit
  sections), S25 (Georgia's low-income credit was not found in the title 48 scope under
  any phrasing tried), and S12 in states whose age-65 rule sits inside a long "net income"
  section.
- S20 (EITC deviations) is derived: PRESENT when the EITC section is present, with a note
  saying whether ITIN/age/childless text was found. "No deviation text" means the section
  was read and none matched, not that none exists.
- F06 counts a 2026 estimated-tax booklet as carrying the TY2026 amounts; MA's PRESENT rests
  on the 2026 Form 1-ES and the surtax threshold notice, not on a bracket schedule.
- Elements are facts at the section-and-parameter grain the encoder reads; some sections
  yield one element (e.g. S24) where a full encoding would read several sub-rules. The
  federal list omits subchapter J/K/S pass-through rules and the possessions rules beyond
  931/933 as not individual-return-facing.
