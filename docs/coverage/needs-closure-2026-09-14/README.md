# Needs-driven closure check, re-run 2026-09-14 on the sixth cut (ten board Year 1 programs)

Question: does the corpus, as cut by `manifests/releases/us-rulespec-2026-09-14-wave4-r2-union.json` (1,042 scopes; release 6, a superset of the active release 5), hold every source-document family a complete encoding of each program's rulebook needs, per jurisdiction? Same schemas, element lists and status vocabulary as the 2026-09-11 check (`../needs-closure-2026-09-11/`), so the numbers compare cell for cell: PRESENT (a cited provision in a selected scope carries the element), EXTRACTABLE (an official publisher lists the carrying family; not taken), ABSENT (nobody publishes it), OUTREACH (publisher blocked or gated), REVIEW (a human must classify). Federal elements are decided once and inherited by states; percentages are of state-level checked cells (INHERITED and N/A excluded), computed the same way for both dates by one script, so they differ slightly from the per-program reports' own denominators.

## Roll-up: 2026-09-11 corpus vs the sixth cut

| Program | State cells | Present 09-11 | **Present now** | Extractable 09-11 | **Extractable now** | Absent | Outreach | Review now |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SNAP | 3,111 | 79% | **84%** | 3% | **0%** | 14% | 2% | 0% |
| WIC | 1,581 | 37% | **44%** | 1% | **0%** | 31% | 19% | 5% |
| Medicaid | 7,089 | 48% | **64%** | 30% | **0%** | 8% | 1% | 26% |
| CHIP | 2,550 | 47% | **74%** | 37% | **0%** | 2% | 0% | 24% |
| TANF | 1,632 | 70% | **83%** | 9% | **0%** | 4% | 2% | 11% |
| CCDF | 1,530 | 74% | **80%** | 8% | **2%** | 1% | 10% | 8% |
| SSI | 6,681 | 48% | **98%** | 50% | **0%** | 1% | 0% | 0% |
| LIHEAP | 2,091 | 34% | **89%** | 60% | **0%** | 7% | 0% | 4% |
| Medicare | 3,468 | 37% | **99%** | 60% | **0%** | 0% | 1% | 1% |
| Income tax | 1,465 | 54% | **90%** | 44% | **1%** | 0% | 5% | 4% |
| **All ten** | 31,198 | 51% | **82%** | 34% | **0%** | 6% | 2% | 10% |

Federal rows (one per element, inherited by all 51 jurisdictions):

| Program | Federal elements | Present 09-11 | Present now | Extractable now | Absent now |
| --- | ---: | ---: | ---: | ---: | ---: |
| SNAP | 332 | 200 | 331 | 0 | 0 |
| WIC | 83 | 59 | 83 | 0 | 0 |
| Medicaid | 302 | 259 | 296 | 0 | 0 |
| CHIP | 186 | 183 | 183 | 0 | 0 |
| TANF | 149 | 0 | 148 | 0 | 0 |
| CCDF | 69 | 61 | 68 | 0 | 0 |
| SSI | 131 | 60 | 125 | 0 | 6 |
| LIHEAP | 41 | 0 | 21 | 0 | 20 |
| Medicare | 68 | 20 | 61 | 0 | 7 |
| Income tax | 164 | 98 | 163 | 0 | 1 |

## What moved, and why

The 2026-09-11 check's largest single closer was "federal statute and regulation layers never taken" (each missing federal section cost 51 cells). Waves 3 and 4 (PRs #701, #704, #706, #712) took them: U.S. Code titles for eight programs, 27 eCFR parts, POMS SI remainder and POMS HI, CMS IOM 100-02/04/16/18, the 2026 annual figures, the CMS-posted Medicaid and CHIP state plan packages for all 51 jurisdictions, TANF/CCDF/SNAP E&T/WIC state plans, LIHEAP benefit matrices, MSP and SSI supplement standards, whole TANF manuals for CT/GA/DE, income-tax statute chapters for 16 states and income-tax regulations for 37. That is what moved the ten-program PRESENT share from 51% to 78% and EXTRACTABLE from 34% to 4%:

- **SSI 48% -> 96%, Medicare 37% -> 95%, LIHEAP 34% -> 83%**: almost entirely federal rows flipping from EXTRACTABLE to PRESENT (SSI 60 -> 123 of 131 federal elements; Medicare 20 -> 59 of 68; LIHEAP 0 -> 20 of 41), inherited by every state. State-level cells for these three are unchanged from 09-11 because the builders' state pointers were not re-read (see "Known limits").
- **Medicaid 48% -> 61%**: the CMS SPA approval packages made the plan-carried elements PRESENT; the remainder moved to REVIEW (29%), which is the pass-2 builder's honest answer for a keyword hit that a person has not read.
- **TANF 70% -> 81%**: 45 CFR 260-265 and 42 U.S.C. 601-619 (federal 0 -> 147 of 149), plus the CT/GA/DE whole manuals.
- **Income tax 54% -> 69%**: whole statute chapters for 16 states and regulations for 37 (state PRESENT 794 -> 1,017).
- **CCDF 74% -> 79%**: ACF-posted Appendix 1 for all 51 jurisdictions (`ccdf-s27` 0 -> 51 PRESENT), amendments for 11 and rate schedules for 5.
- **SNAP 79% -> 81%, WIC 37% -> 44%**: EXTRACTABLE is 1% for both. What remains is ABSENT (nobody publishes it), OUTREACH and REVIEW; more crawling will not move these two.
- **CHIP 47% -> 73%**: the CMS CHIP SPA approval packages and the state CHIP eligibility manuals (`chip-state-eligibility-manual`, 2026-09-10) turned most EXTRACTABLE cells PRESENT; the remainder is REVIEW (26%), same reading as Medicaid.

## What remains, by kind

| Kind | Cells | What closes it |
| --- | ---: | --- |
| REVIEW | see table | A reading pass: a keyword hit was found in a selected scope but nobody has confirmed it carries the element. Medicaid (2,057 cells) and TANF (289) dominate. This is analyst time, not ingestion. |
| EXTRACTABLE | see table | Genuinely postable-and-untaken families: income-tax forms/instructions and remaining statute chapters (tax, 419 cells), CHIP compiled plans, LIHEAP state manuals, CCDF rulebooks and rate sheets (13 states). Wave-5 territory. |
| ABSENT | see table | Publisher posts nothing carrying it: WIC state manuals (20 states publish none), SNAP state plans of operation (no state posts its 7 CFR 272.2 plan). Only outreach can change this. |
| OUTREACH | see table | Durable publisher blocks (NY OTDA/OCFS, CA DHCS Imperva, AZ DES, MO, MD, GA, TX AWS WAF), Lexis-only AR/MS/NJ, DC postback-only regulations, UT browser-only ids, WY image-only tables. Hand to whoever owns publisher relationships. |

## Verification

Every PRESENT cell in all ten matrices was checked against the sixth-cut selector and the corpus on disk (cites a selected `(jurisdiction, document_class, version)` and a `citation_path` that exists in that scope's provisions): 0 missing paths. Exceptions, all deliberate and documented in the matrices' evidence notes:

- **SNAP, 56 cells** cite `us-nd/manual/2026-09-11-nd-snap-manual-supersede` (46) and `us-ok/policy/2026-09-11-ok-snap-manual-supersede` (10), which are on disk but held out of every release: Oklahoma because its text is identical to the released 2026-07-21 edition, North Dakota until its 2026-10-01 effective date (PR #698). `check_snap_wic.py` scans on-disk supersede scopes ahead of the selector by design; the released predecessors carry the same elements.
- **CHIP, 1 cell** falls back to the children-coverage-map family and is REVIEW, not PRESENT: `us/form/2026-07-05-cms-chip-children-coverage-map` is on disk and in the July foundation selectors but in no union selector. Re-selecting it is a one-line selector change. The 20 SPA-document cells cite the first body-bearing block of each CMS CHIP SPA package.
- **WIC** has one duplicated federal row (`wic_cfr_246_2`, emitted at two levels by `check_snap_wic.py`), inherited from 09-11; counts are off by one cell.

## Known limits of this re-run

- Element lists, patterns and status vocabulary are frozen at their 2026-09-11 (Medicaid/CHIP: 2026-09-12) definitions so the numbers compare. New scope families were wired into the builders only where the 09-11 status was EXTRACTABLE and the family is now selected; no new elements were added for the new families themselves.
- The SSI/LIHEAP/Medicare builder re-read the corpus for federal rows only; state-level pointers are the 09-11 literals (state-level counts identical to 09-11).
- The per-program `.md` reports have recomputed count tables; their narrative gap analyses are the 09-11 text unless a section says otherwise. `tax.md`'s per-state "statute coverage in the selection" column is 09-11 text.
- Seven July foundation scopes are in no union selector and are not superseded by name: the CHIP coverage map above; `us-ga/manual/2026-06-24-ga-ssp`, `us-mi/manual/2026-06-27-mi-mdhhs-rft-248`, `us-mn/manual/2026-06-27-mn-dhs-msa-revised-sections-2026-01`, `us-tx/manual/2026-07-13-tx-twh-c120` (state SSI-supplement manuals; SSI-ST cells for those states are PRESENT via POMS SI 01415 and other manuals, so the loss is depth, not coverage); `us-de/regulation/2026-07-03-de-dssm-13000`; and `us/statute/2026-06-26-chip-title-xxi-title-42`, whose 398 sections are carried by `us/statute/2026-07-19-rulespec-title-42-consolidated`. Candidates for the next selector.

## Re-running

All builders read `data/corpus` read-only and write only into this directory. From a checkout holding `manifests/`:

```
PY=~/axiom-corpus/.venv/bin/python; SEL=manifests/releases/us-rulespec-2026-09-14-wave4-r2-union.json; D=docs/coverage/needs-closure-2026-09-14
$PY $D/check_snap_wic.py --corpus ~/axiom-corpus/data/corpus --selector $SEL --queues manifests --rulespec ~/rulespec-us --out $D && $PY $D/write_snap_wic_reports.py --dir $D
$PY $D/tools/build_matrix.py --corpus ~/axiom-corpus/data/corpus --selector $SEL --repo . --out $D      # medicaid + chip; tools/summarize.py <prog> $D for the tables
$PY $D/build_tanf_ccdf_matrix.py --base ~/axiom-corpus/data/corpus --repo . --selector $SEL --out $D
$PY $D/build_ssi_liheap_medicare_matrices.py --base ~/axiom-corpus/data/corpus --selector $SEL && $PY $D/write_reports.py
$PY $D/tax-check.py --corpus ~/axiom-corpus/data/corpus --selector $SEL --queue manifests/tax-agent-queue.yaml --pe ~/policyengine-us/policyengine_us/parameters/gov --rulespec ~/rulespec-us --out $D
$PY $D/verify_matrices.py --selector $SEL --programs ssi,liheap,medicare   # PRESENT citations; tanf/ccdf/tax/snap/wic were checked with an equivalent script
```

Session: 2026-09-14 (recount launched 09-14 18:06, finished after the release-6 publish re-dispatch). Previous check: `../needs-closure-2026-09-11/README.md`.

## After wave 5 (2026-09-15, five agents, draft PRs #714–#718)

Wave 5 ran from the briefs in `wave5/` against these matrices. Each agent took its EXTRACTABLE families (federal documents
first), read a bounded sample of REVIEW cells, and recorded every decision in `docs/ingest-runs/2026-09-15-<group>-decisions.csv`
on its branch; `wave5/apply_decisions.py --write` folded all five files (2,214 rows) back into the matrices in this directory.
**The numbers below assume the 121 wave-5 scopes are selected**: they are on disk (`2026-09-15-*`, unsigned, additions only
except the North Carolina statute chapter, which collides with `2026-08-03-nc-income-tax-current-union` and must be a swap)
and 515 PRESENT cells cite them. Until release 7 selects them, the "sixth cut" table above is the served state.

| Program | State cells | Present before | Present after | Extractable before | after | Review before | after | changed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| snap | 3,111 | 81% | 84% | 1% | 0% | 7% | 0% | 232 |
| wic | 1,581 | 44% | 44% | 1% | 0% | 8% | 5% | 49 |
| medicaid | 7,089 | 61% | 64% | 2% | 0% | 29% | 26% | 385 |
| chip | 2,550 | 73% | 74% | 0% | 0% | 26% | 24% | 77 |
| tanf | 1,632 | 81% | 83% | 1% | 0% | 18% | 11% | 118 |
| ccdf | 1,530 | 79% | 80% | 4% | 2% | 8% | 8% | 40 |
| ssi | 6,681 | 96% | 98% | 2% | 0% | 1% | 0% | 126 |
| liheap | 2,091 | 83% | 89% | 11% | 0% | 5% | 4% | 249 |
| medicare | 3,468 | 95% | 99% | 3% | 0% | 2% | 1% | 141 |
| tax | 1,465 | 69% | 90% | 29% | 1% | 2% | 4% | 462 |

What wave 5 found, beyond the cells:

- **Most "EXTRACTABLE" was already held.** 22 of 34 SNAP/WIC cells, 166 of 286 tax statute cells, 60 LIHEAP manual cells, the
  CCDBG Act, 42 U.S.C. 614, 26 U.S.C. 71/215 and the 26 CFR sections were check-pattern misses on text in selected scopes.
  The run notes list the regex causes (thousands separators, 600-char windows, `tanf` in a version name excluding a scope,
  PDF ligatures, headings such as "Page 65" matching `M-435-520`).
- **Two schema elements are not law**: 45 CFR 96.80 and 96.87 are `[Reserved]` in the live eCFR structure. Drop them
  (102 cells).
- **The reading pass found structural evidence the checks never used**: the 2026-09-13 state-plan scopes hold MACPro
  "Options for Coverage" election pages for 33–48 states per 42 CFR 435 section; 25 of the 27 wave-4 MSP-standards scopes
  carry the 2026 figures for `MED-ST-7` and, for 12 states, `MED-ST-2/3/6`. Both are pattern changes for the next builder
  pass, not crawls.
- **Element verdicts**: PATTERN-CONFIRMED for `M-435-115`, `M-435-172`, `M-435-320`, `tanf-s14`; ABSENT-IN-CITED across the
  samples for `tanf-s29`, `tanf-s16`, `tanf-s28` (carried by state plans and work-program manuals: new EXTRACTABLE
  families), `M-435-520/551/552` (pattern defects) and the CHIP plan-template elements `C-457-340/410/1010/1005/1110`.
- **Publisher blocks confirmed once each, not worked around**: AZ DES (Cloudflare), CO CDEC (CloudFront), NJ child care,
  VA child care (503), FL DOE/KidCare, WI DCF manuals directory, KY Revenue and PA (client-rendered), MD Comptroller
  (ServiceNow), IL ilga.gov (403), AR/MS/NJ/DC/UT rules (Lexis or portal-only), NY OTDA, OH LIHEAP CDN. `acf.gov` now
  fronts an AWS WAF challenge; the LIHEAP Model Plan was taken with the documented chrome120 fallback and is flagged in
  PR #718 for a decision.
- **Corrections to the 09-11 inventory**: NM "8.150 NMAC child care" is the LIHEAP rule (child care is 8.9.3 NMAC); OH OAC
  5101:2-16 moved to 5180:6-1; SC DSS "Voucher" manual is a 2018 superseded volume; AK ID ND NE NV SC have no approved
  eligibility 1115 demonstration.
- **Still open after wave 5**: REVIEW cells with no cited provision (765 Medicaid, 282 TANF/CCDF, 85 WIC, 124
  SSI/LIHEAP/Medicare — research items, not reading); 55 tax statute cells on held chapters; Indiana's CCDF plan sections;
  M-SS-BENEFITS (attachment 3.1-A/B via the CMS SPA "Benefits" topic) for every state; the 22 SSI-ST-2 state statutes;
  MSP standards for FL IN KY LA MO OK UT WV WY.
- Three PRESENT cells cite `us-or/regulation/2026-09-10-tanf-state-policy-manual-chapter-461` (OAR 461, on disk, in no
  union selector) — same class as the seven foundation scopes above; add to release 7.

Release-7 selector inputs: the 121 `2026-09-15-*` scopes listed in the five run notes (NC statute as a swap), the OR
chapter-461 scope, the seven foundation scopes, and North Dakota's SNAP supersede after 2026-10-01.
