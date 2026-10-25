# SSI: SSA POMS part SI (federal family) and state-supplement queue

Date: 2026-09-10
Program: SSI (board Year 1 list; `manifests/ssi-agent-queue.yaml`)
Agent timing: started_at 2026-09-10T16:34:05+0200, finished_at 2026-09-10T16:52:26+0200, wall time 18 min 21 s (1101 s).
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. No existing
function was modified; the only code added is a new generator script.

## Source

SSA Program Operations Manual System (POMS), public site https://secure.ssa.gov/poms.nsf/.
Index: https://secure.ssa.gov/poms.nsf/chapterlist!openview&restricttocategory=05 (part SI chapter
list, 15 chapters). Each chapter links to
`https://secure.ssa.gov/apps10/poms.nsf/subchapterlist!openview&restricttocategory=05<chapter>`, which
enumerates every section of every subchapter (national and regional) with its `lnx` URL. The
section pages themselves print `Effective Dates: mm/dd/yyyy - Present` and a transmittal line
`TN nn (mm-yy)`. secure.ssa.gov served plain HTTP clients with the extractor's own User-Agent
(no 403); the manifest still carries `request: browser_impersonation: true` so the extractor's
existing fallback applies if SSA starts rejecting plain clients. TLS chain was intact; nothing
in `data/certs/` was needed.

## Scope

Jurisdiction `us`, document_class `manual`, version `2026-09-10-ssi-poms-si`. One manifest
document per POMS section, citation path `us/manual/ssa/poms/si/<section number>` (regional
sections keep their region prefix, lowercased: `us/manual/ssa/poms/si/phi01415.009`). The
extractor emits the document row plus one block per heading level that carries text (`.../block-N`).
`--source-as-of 2026-09-10`; `expression_date` per document = the section's printed Effective
Dates start date (all 915 sections print one; range 1989-11-30 to 2026-08-28); the CLI
`--expression-date 2026-09-10` is only the fallback and was never used.

Extraction: `html_content_selector: div.poms`, `html_drop_selectors: [p.tninfo, div.poms-citation]`.
The transmittal line goes to `metadata.transmittal`; the "CITATIONS:" box is dropped because its
Act/CFR references sit in `<div>` nodes the HTML extractor does not read and would otherwise leave
an empty "CITATIONS:" block.

### Index inventory (SI table of contents, 2026-09-10)

Counts are sections the subchapter list enumerates, including regional sections and the `.000`
table-of-contents section. 1,693 sections in part SI; 915 taken.

| Chapter / subchapter | Title | Sections listed | Taken |
| --- | --- | ---: | --- |
| **SI 005** | Eligibility | 173 | 116 |
| SI 00500 | Eligibility | 1 |  |
| SI 00501 | Eligibility Under the Supplemental Security Income (SSI) Provisions | 32 | yes |
| SI 00502 | SSI Alien Eligibility | 46 | yes |
| SI 00510 | Requirement to File for Other Program Benefits | 9 |  |
| SI 00515 | SSA Access to Financial Institutions (AFI) | 5 |  |
| SI 00520 | Institutionalization | 38 | yes |
| SI 00529 | No Social Security Benefits for Prisoners Title XVI | 1 |  |
| SI 00530 | Fugitive Felons and Parole and Probation Violators | 41 |  |
| **SI 006** | The SSI Application Process | 133 | 0 |
| SI 00600 | The SSI Application Process | 1 |  |
| SI 00601 | General Applications and Interviewing Policy | 15 |  |
| SI 00602 | Abbreviated Application Process for Clear Technical Denials | 7 |  |
| SI 00603 | The SSI Disability/Blindness Initial Claims Process | 17 |  |
| SI 00604 | Completion of Form SSA-8000-BK, Application for Supplemental Security Income | 80 |  |
| SI 00605 | Use and Completion of Form SSA-8001-BK | 13 |  |
| **SI 008** | Income | 373 | 345 |
| SI 00800 | Income | 1 |  |
| SI 00810 | General - Income Rules for the Supplemental Security Income Program | 27 | yes |
| SI 00815 | What Is Not Income | 24 | yes |
| SI 00820 | Earned Income | 44 | yes |
| SI 00830 | Unearned Income | 183 | yes |
| SI 00832 | Unearned Income Anderson Case | 7 |  |
| SI 00835 | Living Arrangements and In-Kind Support and Maintenance | 67 | yes |
| SI 00870 | Plans to Achieve Self-Support for Blind or Disabled People | 20 |  |
| **SI 011** | Resources | 252 | 214 |
| SI 01100 | Resources | 1 |  |
| SI 01110 | Resources, General | 28 | yes |
| SI 01120 | Identifying Resources | 63 | yes |
| SI 01130 | Resources Exclusions | 86 | yes |
| SI 01140 | Types of Countable Resources | 37 | yes |
| SI 01150 | Other Resources Provisions | 37 |  |
| **SI 012** | Grandfathered Income and Resource Provisions | 52 | 0 |
| SI 01200 | Grandfathered Income and Resource Provisions | 1 |  |
| SI 01210 | Special Blind Income Provision | 37 |  |
| SI 01220 | Special Resource Provision | 14 |  |
| **SI 013** | Deeming | 131 | 130 |
| SI 01300 | Deeming | 1 |  |
| SI 01310 | Deeming, General | 53 | yes |
| SI 01320 | Deeming of Income | 55 | yes |
| SI 01330 | Deeming of Resources | 22 | yes |
| **SI 014** | State Supplementary Payments | 84 | 84 |
| SI 01400 | State Supplementary Payments | 1 | yes |
| SI 01401 | Introduction to State Supplementation | 4 | yes |
| SI 01403 | Pass Along of Federal Supplemental Security Income Benefit Cost of Living Increases | 3 | yes |
| SI 01405 | Federal and State Administrative Considerations | 2 | yes |
| SI 01410 | Federal Administration of State Supplementary Payments | 9 | yes |
| SI 01415 | Elements of State Supplementary Payments | 65 | yes |
| **SI 017** | Medicaid Eligibility | 45 | 0 |
| SI 01700 | Medicaid Eligibility | 1 |  |
| SI 01715 | Medicaid and the SSI Program | 6 |  |
| SI 01730 | SSA Determinations of Medicaid Eligibility | 38 |  |
| **SI 018** | Supplemental Nutrition Assistance Program (SNAP) | 35 | 0 |
| SI 01800 | Food Stamps | 1 |  |
| SI 01801 | Supplemental Nutrition Assistance Program (SNAP) | 34 |  |
| **SI 020** | Benefits and Payments | 122 | 26 |
| SI 02000 | Benefits and Payments | 1 |  |
| SI 02001 | Computation of Benefits - Introduction | 5 | yes |
| SI 02002 | Monitoring State Accounting for Interim Assistance Reimbursement (IAR) Payments | 6 |  |
| SI 02003 | Interim Assistance Payments | 45 |  |
| SI 02004 | Direct Field Office Payments | 8 |  |
| SI 02005 | Computation of Benefits - SSI | 21 | yes |
| SI 02006 | Windfall Offset and Effect on Title XVI Payments | 15 |  |
| SI 02007 | SSI Interim Benefits Payments | 5 |  |
| SI 02009 | Computation of Payments for Months Prior to April 1982 | 16 |  |
| **SI 021** | Title XVI (SSI) Underpayments | 15 | 0 |
| SI 02100 | Title XVI (SSI) Underpayments | 1 |  |
| SI 02101 | Title XVI (SSI) Underpayments | 14 |  |
| **SI 022** | Overpayments | 54 | 0 |
| SI 02200 | Overpayments | 1 |  |
| SI 02201 | Supplemental Security Income Overpayments - Overview | 10 |  |
| SI 02205 | Supplemental Security Income Overpayments - Sponsor/Alien Cases | 3 |  |
| SI 02220 | Recovery Procedures for Supplemental Security Income Overpayments | 40 |  |
| **SI 023** | Posteligibility Events | 165 | 0 |
| SI 02300 | Posteligibility Events | 1 |  |
| SI 02301 | Posteligibility Changes | 30 |  |
| SI 02302 | Continuing Benefits and Recipient Status Under Sections 1619(A) and 1619(B) for Individuals Who Work | 17 |  |
| SI 02305 | Redeterminations of Eligibility and/or Payment Amount | 73 |  |
| SI 02306 | Miscellaneous Posteligibility Issues | 5 |  |
| SI 02309 | Critical Birthday and Insured Status Diaries | 8 |  |
| SI 02310 | SSI Interfaces | 31 |  |
| **SI 029** | State Financial Management | 6 | 0 |
| SI 02900 | State Financial Management | 1 |  |
| SI 02901 | SSI Administrative Costs | 5 |  |
| **SI 040** | Administrative Review, Appeals and Finality - SSI | 53 | 0 |
| SI 04000 | Reconsideration - SSI | 1 |  |
| SI 04005 | Administrative Review (Appeals) Process - SSI | 7 |  |
| SI 04010 | Initial Determinations - SSI | 3 |  |
| SI 04020 | Reconsideration - SSI | 7 |  |
| SI 04030 | Administrative Law Judge (ALJ) Hearings - SSI | 9 |  |
| SI 04040 | Appeals Council (AC) Review - SSI | 7 |  |
| SI 04050 | Litigation - SSI | 6 |  |
| SI 04060 | Expedited Appeals Process (Title XVI Only) - SSI | 2 |  |
| SI 04070 | Administrative Finality - SSI | 11 |  |
| **Total** | | 1693 | 915 |

### Reviewer judgments (federal)

1. Selection. Work-order minimum (SI 00501, 00810, 00820, 00830, 01110, 01120, 01130, 01310,
   01320, 02001, all of SI 014) plus seven subchapters PolicyEngine-US SSI variables cite and that
   carry parameter values: SI 00502 (alien eligibility), SI 00520 (institutionalization), SI 00815
   (what is not income), SI 00835 (living arrangements / ISM), SI 01140 (countable resources),
   SI 01330 (deeming of resources), SI 02005 (computation of benefits). Not taken: SI 006
   (application process), SI 012 (grandfathered), SI 017/018 (Medicaid, SNAP), SI 02002-02009
   except 02005, SI 021-023, SI 029, SI 040, and SI 00510/00515/00529/00530, SI 00832/00870,
   SI 01150. Change `TAKEN_SUBCHAPTERS` in the script to widen.
2. Whole subchapters, including regional (BOS/CHI/DAL/DEN/KC/NY/PHI/SEA/SF/ATL) sections and
   `.000` TOC sections, so `taken_count` equals the index count per subchapter and coverage is
   meaningful. 697 national + 218 regional sections. Regional citation paths use the region prefix.
3. Overlap with existing corpus. `us-dc-ossp-ssa-poms` (2026-07-03) holds SI 01415.058 (2026)
   and SI PHI01415.009 under `us/guidance/ssa/poms/si-01415-058/2026` and
   `us/guidance/ssa/poms/si-phi01415-009`; `us-de-ssi-state-supplement-poms` holds the Delaware
   subsection of SI 01415.058 under `us-de/guidance/...`. The manual family re-takes both full
   sections under `us/manual/ssa/poms/si/01415.058` and `.../phi01415.009`. No citation path is
   duplicated (checked: all 11,028 paths unique, and none exist in any other provisions JSONL);
   the same two source documents are now present under two document classes.
4. 20 CFR 416: the corpus holds only the explicit 14-row deeming slice
   `us/regulation/2026-07-23-title-20-part-416` (coverage complete 14/14; run note
   2026-07-23-us-cfr-416-deeming-and-irs-notice-2025-67.md, `scripts/repro_us_cfr_416_deeming_slice.py`).
   No manifest or coverage covers the rest of Part 416. Not re-ingested and not widened here; the
   remaining 608 Part 416 units are a separate follow-up.
5. 42 USC 1381-1382j is in `2026-06-20-ssi-title-xvi-title-42` (226 rows); not touched.
6. Heading-only levels: the HTML extractor only emits a block for a heading that has text
   directly under it, so an `h2` like "B. Description of supplements for California" that is
   immediately followed by an `h3` yields no block of its own; the `h3` headings ("1. Definitions
   of State living arrangement variations for California") still name the state. A reviewer who
   needs the letter-level anchors addressable should extend the extractor.
7. SI 01415.031-01415.057 are the January 1999-2025 payment-level tables; taken as part of the
   subchapter (history is useful for backdating) even though only SI 01415.058 is current.

## Counts and timing

- Smoke run (scratch base, `--limit 2`, SI 00501.000 and SI 00501.001): 2 documents, 8 provisions,
  coverage complete, 3 s first pass and 2 s with the final drop selectors.
- Full run: 915 documents, 915 source files (60.6 MB HTML), 11,028 provisions (915 documents +
  10,113 blocks), coverage `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths
  (verified independently over the JSONL). started_at 2026-09-10T16:45:41+0200, finished_at
  2026-09-10T16:49:20+0200, elapsed_seconds=219, exit 0, no `--allow-incomplete`.
- Generator (index + 915 section-page fetches for Effective Dates/TN): 197 s first pass; re-runs use
  the cache at `~/.axiom/poms-si-cache` (not in the repo).

Artifacts (unsigned, awaiting controller; in the main checkout, not this worktree):

- `data/corpus/sources/us/manual/2026-09-10-ssi-poms-si/official-documents/ssa-poms-si-<section>.html`
- `data/corpus/inventory/us/manual/2026-09-10-ssi-poms-si.json`
- `data/corpus/provisions/us/manual/2026-09-10-ssi-poms-si.jsonl`
- `data/corpus/coverage/us/manual/2026-09-10-ssi-poms-si.json`

Rebuild:

```bash
uv run python scripts/build_ssi_poms_si_manifests.py --print-index
s=$(date +%s); uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-10-ssi-poms-si --manifest manifests/us-ssa-poms-si-2026-09-10.yaml \
  --source-as-of 2026-09-10 --expression-date 2026-09-10; echo "elapsed_seconds=$(( $(date +%s) - s ))"
```

## State supplements (queue rows)

Categorisation source: POMS SI 01415.010 "Administration of State Supplementary Programs"
(TN 26, effective 09/23/2015; column Optional: F / F/S / S / N), cross-checked against
SI 01415.058A (TN 95, January 2026), which lists the same twelve federally administered states:
CA, DE, DC, HI, IA, MI, MT, NV, NJ, PA, RI, VT. SSA's compiled "State Assistance Programs for SSI
Recipients" report was not used. Six states have no optional program per SI 01415.010 (AZ, AR,
MS, ND, TN, WV) and get no row. 45 state rows + the federal row = 46 rows.

- done (7, not re-ingested): CA (`2026-06-27-ca-dor-ssi-ssp-newsletter`, us-ca/guidance), CT
  (`2026-07-02-ct-ssp-upm-and-standards`, us-ct/policy), DC (`2026-07-03-dc-ossp-ssa-poms`,
  us/guidance), DE (`2026-07-03-de-ssi-state-supplement-poms`, us-de/guidance), GA
  (`2026-06-24-ga-ssp`, us-ga/manual), IN (`2026-07-04-in-ssp-sapn`, us-in/manual), KS
  (`2026-07-04-ks-sspp-guidance`, us-ks/guidance).
- agent_ready via the federal family (9, SSA-administered F or F/S): HI, IA, MI, MT, NV, NJ, PA,
  RI, VT. `primary_source_url` is the state's subsection of SI 01415.058; regional per-state
  sections (e.g. SI BOS01415.013 and SI BOS01415.970 for Vermont, SI SF01415.200-.220 for Hawaii,
  SI SEA01415.034 for the Seattle region) are in the same extraction. No separate `us-xx` scope was
  created: the text is SSA's, so it lives under `us/manual`; a reviewer who wants per-state
  `us-xx` rows can slice the existing documents. For F/S states (IA, MI, PA, RI, and DE/DC) the
  state-administered part is not covered.
- needs_review (29, state-administered S): AK, AL, CO, FL, ID, IL, KY, LA, MA, MD, ME, MN, MO,
  NC, NE, NH, NM, NY, OH, OK, OR, SC, SD, TX, UT, VA, WA, WI, WY. None was extracted: the primary
  source is each state agency's own document and the official index was not confirmed within this
  run. `index_url` is recorded only for WI (https://www.dhs.wisconsin.gov/ssi/index.htm, HTTP 200,
  title "Supplemental Security Income In Wisconsin"). A single probe of guessed agency URLs for the
  other states returned 404, 403, or a bot challenge (mass.gov 403; mn.gov Radware challenge;
  hhs.texas.gov lead-list handbook page 403 to a plain client), so no unverified URL was recorded.
  Where SSA publishes a regional description of the state program (IL, ME, MA, NY, SD, WY, and the
  Seattle region AK/ID/OR/WA), the row's notes point at that federal-family citation path as
  discovery material, not as the primary source.
- blocked_primary_source: none (no state extraction was attempted, so nothing was blocked).

status_counts: agent_ready 10, done 7, needs_review 29; top-level `queue_status: in_progress`.

## Tests

`uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
in the sparse worktree: 255 passed, 2 skipped, 10 failed. All ten failures are `FileNotFoundError`
on `data/corpus/...` artifacts of other scopes (be statute promotion, NY TANF, AK/CT/MI/MT/ND/NY
SNAP manuals) that the sparse checkout does not contain; none touches the SSI manifest or script.
No adapter was added, so no new tests.

Remaining (controller): `sign-ingest-manifest` for `us/manual/2026-09-10-ssi-poms-si`, immutable
release selector, `publish_corpus.py --dry-run` then publish. Follow-ups: rest of 20 CFR 416;
state-administered supplement documents for the 29 `needs_review` rows.
