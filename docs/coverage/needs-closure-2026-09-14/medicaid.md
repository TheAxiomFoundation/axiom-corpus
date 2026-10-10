# Medicaid: needs-driven closure check (pass 2 schema, re-run 2026-09-14 on the sixth cut)

Question: does the corpus hold every source-document family a complete encoding of the Medicaid
rulebook needs, per jurisdiction (federal plus the 50 states and DC), and where it does not, is the
gap extractable, absent, outreach or review? The bar is the law's own structure, not PolicyEngine.

Files: `medicaid-schema.yaml` (302 elements), `medicaid-matrix.csv` (15,704 rows = 302 x 52),
`tools/` (builders; `tools/search-universe.json` lists the scopes searched per state).

## Method

1. **Schema.** Elements were enumerated from (1) 42 U.S.C. 1396a and the sections it invokes
   (1396b(v), 1396d, 1396o, 1396p, 1396r-5, 1396r-6, 1396u-1, 1320b-7, 1382-1382c, 8 U.S.C.
   1611-1641, 1315), (2) every section of 42 CFR 435 (as held in `us/regulation/2026-06-25-title-42-part-435`
   plus the CMS-2454-IFC 435.550-435.563 scope), 436 (`2026-09-11-title-42-part-436`, 75 sections),
   447 subpart A (eCFR structure 2026-09-09; not held) and, for the CHIP cross-references, 457, and
   (3) the structure of the state rulebooks held in the corpus (the tables of contents of the
   2026-09-10 Medicaid state scopes), the approved state plan and SPAs, and annual income-level
   tables. Every held 435/436/457 section maps to exactly one element (checked both ways: no held
   section is missing from the schema; every schema `cfr_path` except part 447 is held). Levels:
   163 `federal_only`, 46 `federal_with_state_option`, 93 `state`.
2. **Federal row.** A statute or regulation element is PRESENT when its citation path (or a child)
   has a non-empty body in a selected federal scope; the Medicaid statute scope holds 1396a(a)(10),
   (e)(1)-(16), (f), (l), (m), 1396b(f), (v), 1396d(a), (n), (p), (q), 1396p(f), 1396u-1; the
   P.L. 119-21 scope holds 1396a(xx); the released recovery statute scope holds 8 U.S.C. 1612, 1613,
   1641 (not 1611); the consolidated title-42 scope holds 1397aa-1397mm.
3. **State rows.** For `federal_only` elements the state row is INHERITED (part 436: NOT_APPLICABLE,
   territories only). For the 139 state-level and state-option elements each state's provisions
   were searched by regex over heading and body, restricted to the state's own program scopes
   (`2026-09-10-medicaid-state-eligibility-manual`, `2026-09-10-chip-state-eligibility-manual`) plus
   the pointer scopes the queue rows name for done-by-pointer states (FL ESS manual, IL CSMM, MI
   Bridges, WV IMM, ID IDAPA 16.03.05, IN `us-in-ssp-sapn` chapter 5000, TX `tx-manuals`). 52,654
   provisions in all; per state from 0 (CA) to 7,700 (IL).
   - strong pattern hit -> PRESENT, citing the provision and the matched snippet;
   - weak pattern hit, a hit only in a table-of-contents provision, or a hit without a value
     signal where the element is a state-set standard (`needs_number`) -> REVIEW with the candidate;
   - cost-sharing elements reject windows that are about Medicare premiums or ACA credits;
     community-engagement elements reject HCBS-waiver "community engagement" services;
   - no hit -> OUTREACH when the Medicaid queue row is `blocked_primary_source` (AL, CA, NE);
     ABSENT for the 435.551-435.561 community-engagement elements (the IFC compliance date is
     2027-01-01 and no state has posted implementing rules; the Georgia Pathways, Montana CMA 310-1,
     New Hampshire Granite Advantage and Arkansas texts that do exist are PRESENT); EXTRACTABLE when
     the queue row lists an untaken family or when the CMS-posted state plan family carries the
     election (named per element in `plan_family`); REVIEW otherwise.
   - The CMS Medicaid/CHIP/BHP eligibility-levels table (`us/form/2026-05-12-...`, state decisions
     as of 2023-12-01) is accepted as PRESENT for the group income standards (435.110, .116, .118,
     .119) when the state's own text was not found, with a staleness note; it is *not* accepted for
     `M-SS-INCOME-TABLE` (current-year table), which stays a gap.
4. **Pass 1 audit.** The 2026-09-11 pass searched every scope of the state (SNAP, TANF, WIC, tax)
   with a Medicaid-context window and used single-word patterns. A 40-cell random sample of its
   PRESENT cells showed hits in CalFresh regulations (CA 435.831), a SNAP appendix (OK 435.236),
   "retroactive unemployment compensation" (MA 435.915), the ACA individual-responsibility exemption
   (VT 447.56) and table-of-contents lines (KY 1396p(f)). Pass 2 replaced the universe, the pattern
   tiers and the gap rules; pass-1 builders are kept as `tools/*_pass1.py`.
5. **Pass 2 audit.** A fresh 30-cell random sample of pass-2 PRESENT cells was read: 26 carry the
   element in the cited provision; 3 are wrong or marginal (IN 447.55 cites a QMB Medicare-premium
   paragraph inside a Medicaid chapter; TX 435.912 cites a 45-day verification look-back, not the
   timeliness standard; ME 447.56 cites a premium due-date section). The residual false-positive
   rate of PRESENT cells is therefore estimated at roughly 10%, concentrated in the procedural
   elements (435.911, 435.912, 435.916) and the 447 cost-sharing elements. REVIEW cells are
   candidates, not gaps: 47 states have a REVIEW for 435.520/.540 only because the age-65 and
   disability-definition patterns were deliberately kept weak.

Timing: schema generation < 1 s; matrix build 314 s (Medicaid) + 137 s (CHIP) per run, two pass-2
runs on 2026-09-12; pass-1 build and the corpus checks (statute and CFR path listings, scope
inventories, run-note and queue reads) about 40 minutes of interactive work. No network access,
no writes under `data/corpus`.

## Results

> Re-run 2026-09-14 against `manifests/releases/us-rulespec-2026-09-14-wave4-r2-union.json` (the sixth cut) with the 2026-09-12 element list unchanged (`tools/build_matrix.py --selector`); every PRESENT cell passed the builder's self-check (selected scope, citation_path with a body). The tables below are `tools/summarize.py` output for that run; the sections from "Top gaps" down keep the 2026-09-12 reading.

### Status totals (all cells)

| Status | Cells |
| --- | ---: |
| PRESENT | 4649 |
| EXTRACTABLE | 170 |
| ABSENT | 400 |
| OUTREACH | 109 |
| REVIEW | 2057 |
| INHERITED | 4488 |
| NOT_APPLICABLE | 3831 |
| total | 15704 |

### Status totals (state-level checked cells only)

| Status | Cells | Share |
| --- | ---: | ---: |
| PRESENT | 4353 | 61.4% |
| EXTRACTABLE | 170 | 2.4% |
| ABSENT | 400 | 5.6% |
| OUTREACH | 109 | 1.5% |
| REVIEW | 2057 | 29.0% |
| total | 7089 | |

### Federal row (us)

| Status | Elements |
| --- | ---: |
| PRESENT | 296 |
| NOT_APPLICABLE | 6 |

Federal elements not PRESENT (NOT_APPLICABLE rows are state-only structure elements):


### Per-jurisdiction roll-up (state-level checked elements)

| Jurisdiction | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | checked | PRESENT share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| us-ak | 84 | 4 | 9 | 0 | 42 | 139 | 60% |
| us-al | 60 | 0 | 0 | 65 | 14 | 139 | 43% |
| us-ar | 89 | 2 | 8 | 0 | 40 | 139 | 64% |
| us-az | 86 | 3 | 8 | 0 | 42 | 139 | 62% |
| us-ca | 72 | 0 | 0 | 44 | 23 | 139 | 52% |
| us-co | 87 | 2 | 8 | 0 | 42 | 139 | 63% |
| us-ct | 86 | 2 | 8 | 0 | 43 | 139 | 62% |
| us-dc | 82 | 4 | 9 | 0 | 44 | 139 | 59% |
| us-de | 85 | 3 | 9 | 0 | 42 | 139 | 61% |
| us-fl | 86 | 0 | 8 | 0 | 45 | 139 | 62% |
| us-ga | 87 | 2 | 8 | 0 | 42 | 139 | 63% |
| us-hi | 86 | 2 | 9 | 0 | 42 | 139 | 62% |
| us-ia | 87 | 2 | 9 | 0 | 41 | 139 | 63% |
| us-id | 81 | 8 | 10 | 0 | 40 | 139 | 58% |
| us-il | 86 | 0 | 8 | 0 | 45 | 139 | 62% |
| us-in | 91 | 2 | 7 | 0 | 39 | 139 | 65% |
| us-ks | 85 | 3 | 9 | 0 | 42 | 139 | 61% |
| us-ky | 88 | 3 | 9 | 0 | 39 | 139 | 63% |
| us-la | 89 | 0 | 9 | 0 | 41 | 139 | 64% |
| us-ma | 85 | 3 | 9 | 0 | 42 | 139 | 61% |
| us-md | 87 | 2 | 8 | 0 | 42 | 139 | 63% |
| us-me | 85 | 3 | 8 | 0 | 43 | 139 | 61% |
| us-mi | 87 | 1 | 8 | 0 | 43 | 139 | 63% |
| us-mn | 87 | 3 | 8 | 0 | 41 | 139 | 63% |
| us-mo | 85 | 2 | 9 | 0 | 43 | 139 | 61% |
| us-ms | 85 | 0 | 9 | 0 | 45 | 139 | 61% |
| us-mt | 95 | 4 | 1 | 0 | 39 | 139 | 68% |
| us-nc | 89 | 3 | 9 | 0 | 38 | 139 | 64% |
| us-nd | 86 | 4 | 9 | 0 | 40 | 139 | 62% |
| us-ne | 96 | 4 | 1 | 0 | 38 | 139 | 69% |
| us-nh | 92 | 0 | 5 | 0 | 42 | 139 | 66% |
| us-nj | 84 | 5 | 9 | 0 | 41 | 139 | 60% |
| us-nm | 87 | 0 | 8 | 0 | 44 | 139 | 63% |
| us-nv | 86 | 3 | 8 | 0 | 42 | 139 | 62% |
| us-ny | 86 | 4 | 8 | 0 | 41 | 139 | 62% |
| us-oh | 87 | 3 | 9 | 0 | 40 | 139 | 63% |
| us-ok | 85 | 3 | 9 | 0 | 42 | 139 | 61% |
| us-or | 75 | 2 | 9 | 0 | 53 | 139 | 54% |
| us-pa | 84 | 3 | 8 | 0 | 44 | 139 | 60% |
| us-ri | 88 | 2 | 9 | 0 | 40 | 139 | 63% |
| us-sc | 86 | 3 | 10 | 0 | 40 | 139 | 62% |
| us-sd | 78 | 8 | 9 | 0 | 44 | 139 | 56% |
| us-tn | 89 | 2 | 9 | 0 | 39 | 139 | 64% |
| us-tx | 85 | 0 | 8 | 0 | 46 | 139 | 61% |
| us-ut | 86 | 1 | 9 | 0 | 43 | 139 | 62% |
| us-va | 88 | 2 | 8 | 0 | 41 | 139 | 63% |
| us-vt | 90 | 1 | 9 | 0 | 39 | 139 | 65% |
| us-wa | 89 | 2 | 8 | 0 | 40 | 139 | 64% |
| us-wi | 90 | 3 | 7 | 0 | 39 | 139 | 65% |
| us-wv | 90 | 0 | 8 | 0 | 41 | 139 | 65% |
| us-wy | 64 | 52 | 9 | 0 | 14 | 139 | 46% |

### Top gaps by how many states share them

Elements not PRESENT in all 51 jurisdictions (48 states plus the 3 blocked): the 435.10/814/843
state-plan elements and `M-SS-STATE-PLAN`/`M-SS-SPA` (no state plan or Medicaid SPA is held for any
state); the legacy protected groups 435.115, .122, .130, .132, .133, .134, .138; the optional
groups 435.172, .210, .211, .218, .220, .222, .223, .227, .230, .234; the medically needy
sub-groups 435.308, .310, .320, .322, .324, .330 (the general medically needy election 435.301 is
PRESENT in 45 states); 435.520, .531, .540 (weak-pattern definitional elements, REVIEW in most
states); 435.561 (CE outreach, ABSENT everywhere); the 209(b) financial and post-eligibility
elements 435.631, .733, .735; 435.832, .845; 435.904, .908, .918, .949; 447.57.

### Gap families, ranked by cells (state-level cells not PRESENT), with what would close each

| Family that would close the gap | Cells | States | Closure |
| --- | ---: | ---: | --- |
| Medicaid state plan attachment 2.2-A (groups covered) on medicaid.gov | 1,530 | 49 | Take each state's compiled state plan from the CMS state-plan pages (one PDF set per state; never queued). Attachment 2.2-A settles every optional-group election in one document. |
| Community-engagement implementing rules (435.551-435.561) | 434 | 48 | Nothing to take yet: the IFC compliance date is 2027-01-01 and no state has posted rules; re-check the state manuals and the CMS SPA index after states file. GA, MT, NH and AR already carry text. |
| State's own manual or codified rule, publisher block (AL, CA, NE) | 359 | 3 | Outreach: AL (TLS), CA (Imperva), NE (SOS API 403 since 2026-09-11; retry the 477 NAC chapter API). |
| Approved Medicaid state plan and SPA index (435.10, 435.814, 435.843, M-SS-STATE-PLAN, M-SS-SPA) | 255 | 51 | Same CMS state-plan pages plus the Medicaid SPA index; one crawl closes all 51. |
| State plan sections 2.1-2.5 (application, residency, blindness, disability) | 164 | 48 | Same document; 128 of the 164 are REVIEW candidates already sitting in the manuals (age 65, disability definition) and only need a reader. |
| State plan attachment 2.6-A supplement (medically needy levels) | 158 | 48 | Same document; the MNIL/resource levels tables. |
| State eligibility manual or codified regulation (no plan section) | 152 | 48 | 86 cells have an untaken publisher family named in the queue row (e.g. NY full manual and update archive, NC administrative letters and change notices, CT policy transmittals, MD action transmittals, TX TWH parts B-X, WA additional tools); 66 are REVIEW. |
| State plan attachment 2.6-A supplements 8-12 (post-eligibility, transfers, trusts, estate recovery, spousal impoverishment) | 136 | 48 | Same document; mostly the 209(b)-only elements (12 states are 209(b) or 1634-variant, the rest legitimately have nothing). |
| State plan attachment 2.6-A and supplements (financial standards) | 129 | 48 | Same document. |
| State plan attachment 4.18 (premiums and cost sharing) | 125 | 49 | Same document; also close the federal 447 gap first. |
| MAGI-based verification plan (posted by CMS) | 66 | 48 | CMS posts each state's verification plan next to the state plan. |
| WY Medicaid manual (Google Sites) | 125 of the WY row | 1 | A Google-Sites content adapter or a WDH export; index inventoried (107 policy pages, 17 tables). |

Practically: one family, the CMS-posted approved state plan (with its 2.2-A, 2.6-A, 4.18 attachments,
supplements, the SPA index and the verification plan), would close 2,563 of the 2,888 EXTRACTABLE and
REVIEW cells; the publisher blocks account for 359; the community-engagement
rules cannot be closed before 2027.

### Elements PolicyEngine does not model

PolicyEngine (policyengine-us 84253b6, 2026-08-17) models 41 of the 302 elements fully or partially
and does not model 261, of which 109 are state-level or state-option elements an Axiom encoding
must carry. The full list is the `pe_modeled: 'no'` rows of the schema; the substantive groups are:

- eligibility groups PE lacks: MSP (QMB, SLMB, QI, QDWI), 1931 extensions (TMA, spousal-support
  extension), deemed newborns, IV-E and former foster care, BCCP, TB, family planning, HCBS waiver
  and 1915(i) groups, Katie Beckett, the special income level (300% SSI) institutional group,
  the legacy protected groups (Pickle, 1973 groups, disabled widows), reasonable classifications
  of under-21s, state supplement recipients, all medically needy sub-groups (PE has the MN limits
  but not the group structure);
- financial rules: 1902(r)(2) less-restrictive methodologies, spousal impoverishment, transfers
  and look-back, trusts, estate recovery, post-eligibility treatment of income (patient liability,
  PNA), 209(b) income rules, retroactive eligibility;
- cost sharing: every 447 element except the working-disabled buy-in premium PE has as a variable;
- process: application, SSN, timeliness, effective dates, renewals, notices, changes, verification
  plan and electronic sources, reasonable compatibility, authorized representatives, continuous
  eligibility, presumptive eligibility (children, other groups, hospital), coordination with the
  Exchange, fair hearings, TPL;
- community engagement: PE models the applicable-adult test, hours and the dependent/foster-care
  exceptions, but not the hardship exception, compliance assessment and verification, noncompliance
  procedures, implementation timing or outreach;
- the state plan, SPAs, benefit package and residency/citizenship-documentation elements.

rulespec-us (c8951033) encodes the CMS eligibility-levels wrappers for every state (435.110, .116,
.118, .119 levels and the expansion flag), the MAGI household/income pipeline (1396a(e)(14),
435.603) and the Georgia SSI-recipient rule (435.120); nothing else in this schema.

### Schema uncertainties

- Level assignments for 435 subpart C optional groups are `state` (the state elects and sets the
  standard); a reviewer may prefer `federal_with_state_option` for the yes/no elections. The
  matrix treats both the same way.
- The 447 subpart A element list follows the eCFR 2026-09-09 structure from memory of the part
  (447.1-447.90 with 447.50-447.57); it was not read from the API in this session and should be
  checked when part 447 is taken.
- 42 CFR 457.344 is held only as a "[Removed]" notice in the CMS-2454-IFC conforming-amendments
  scope; the rulespec-us CHIP wrappers still cite it as a checked path.
- `M-ST-1315` (1115 terms) and `M-SS-BENEFITS` are listed because an encoder needs them, but their
  carrying documents (special terms and conditions, attachment 3.1-A) are outside every queue and
  the matrix can only report mentions.
- The `plan_family` names (attachment and section numbers of the CMS preprint) are the standard
  Medicaid state plan preprint layout; MACPro-converted plans use different page names for the same
  content.
- 42 CFR 431, 433, 440 and 441 are not enumerated (outside the requested regulation set); a
  complete rulebook check will need them.
