# Medicaid state eligibility manuals, batch 2

Date: 2026-09-10
Program: Medicaid (board Year 1 list; `manifests/medicaid-agent-queue.yaml`)
Agent: started_at 2026-09-10T20:32:47+0200, finished_at 2026-09-10T21:09:41+02:00, wall time 0h 36m 54s (a first
attempt at this batch stalled before doing anything; this is the second attempt, from a clean worktree).
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. No function in
`src/axiom_corpus` was modified and no adapter was added. The only code change is to the batch-1 generator
`scripts/build_medicaid_state_eligibility_manual_manifests.py`: eight new `build_xx()` functions, a
`document2()` wrapper (batch-2 provenance string), batch-2 static rows, and `main()` rewritten to take
`--batch {1,2,all}` / `--only` so batch 2 can be rebuilt without re-crawling the batch-1 publishers (the
batch-1 builders themselves are untouched apart from an unused-variable rename in `build_ny` that
`ruff` reported).

## Batch selection (reviewer judgment)

Batch 2 = the next ten states by population after batch 1: WA, AZ, TN, MA, IN, MD, MO, WI, CO, MN.
Before attempting each, `manifests/` and `data/corpus/provisions/<jurisdiction>/` in the main checkout
were checked for a combined manual already carrying the Medicaid eligibility chapters: none does. The
Washington EA-Z manual scope (`us-wa-eaz-manual.yaml`) has a few DSHS pages that mention Medicaid
(NGMA procedures, citizenship documents) but not the HCA Apple Health eligibility manual; the AZ DES,
TN, IN, MD, MO, WI, MN combined manuals are SNAP/cash only; Colorado's 10 CCR 2505-10 is not in the
`us-co/regulation` scopes (2506-1, 2503-5/6, 1403-1 only). Today's CHIP batch
(`*-2026-09-10-chip-state-eligibility-manual*`) took MA 130 CMR 505/506, IN IHCPPM chapters 1600/3000
and MO MAGI appendices A/E under CHIP citation paths (`us-ma/regulation/130-cmr/505`,
`us-in/manual/fssa/chip/...`, `us-mo/manual/dss/chip/...`); those are partial overlaps, not coverage of
the eligibility manual, so the states were attempted and the overlapping documents re-fetched under the
Medicaid paths (the TX precedent from batch 1). No replacement state was therefore pulled; the ten
attempted are the ten listed. Attempted: 10. Extracted: WA, MA, IN, MD, MO, WI, CO, MN (8). Blocked:
AZ, TN (2). Batch-1 blocked rows CA and OH were retried once each (below).

Family per state: the state Medicaid agency's eligibility policy manual (MAGI and non-MAGI eligibility,
income, resources, household composition, LTSS financial eligibility), confirmed from the agency's own
index page; transmittals, action transmittals, bulletins, prior handbook releases, provider/benefit
regulations, forms, calculators and spreadsheets on the same index are separate families, inventoried
but not taken.

Scope: document_class `manual`, version `2026-09-10-medicaid-state-eligibility-manual`, citation paths
`us-xx/manual/<agency>/medicaid/<section>`, `source_as_of` and `expression_date` 2026-09-10 (current
manual trees as fetched; effective dates printed inside the documents were not parsed; same judgment as
batch 1).

Extraction: `uv run axiom-corpus-ingest extract-official-documents`, no new adapter, all artifacts
under the main checkout's `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus` (this worktree is
sparse). PDFs use the extractor's page granularity with `ocr: true`; HTML pages use
`html_content_selector` per publisher. Where the publisher's index page carries no text and only a PDF
(MA, CO), the page is `source_url` and the PDF is `download_url` (existing manifest option). TLS
verification was never disabled and no publisher needed a certificate bundle (no `data/certs` change).
No smoke runs with `--limit` were needed: MA (14 PDFs, 5 s) and IN (22 PDFs, 40 s) were run first and
served as the smoke for the PDF path, MN (344 pages, 61 s) for the HTML path. Coverage is
`complete: true` with 0 missing, 0 extra and 0 duplicate citation paths for every extracted scope;
`citation_path` uniqueness within each provisions JSONL and absence from every other provisions JSONL
under `data/corpus/provisions/<jurisdiction>/` (all document classes) were verified independently with a
counter script (0 in-file duplicates, 0 cross-scope collisions for all eight scopes).

## Per-jurisdiction results

| Jurisdiction | Index | Documents taken | Provisions | Extraction seconds |
| --- | --- | ---: | ---: | ---: |
| us-ma | EOHHS/MassHealth, 130 CMR law library (mass.gov) | 14 | 276 | 5 |
| us-in | FSSA OMPP Medicaid Eligibility Policy Manual (IHCPPM) | 22 | 590 | 40 |
| us-md | MDH Medicaid Manual page | 19 | 863 | 48 (re-run after re-ordering the manifest: 35) |
| us-co | Secretary of State CCR, Medical Services Board (Volume 8) | 1 | 291 | 5 |
| us-wi | DHS publications library, P-10030 and P-10171 collections | 2 | 833 | 9 |
| us-mn | DHS Eligibility Policy Manual (EPM) RoboHelp TOC | 344 | 2,749 | 61 |
| us-wa | HCA Apple Health eligibility manual overview + 4 hub pages | 202 | 1,751 | 266 |
| us-mo | DSS Manuals: Family MO HealthNet (MAGI) + MHABD manuals | 565 | 1,190 | 611 |

Total: 1,169 documents, 8,543 provisions across 8 scopes. Index documents found versus taken are in
the queue rows (`index_document_count`, `taken_count`, `index_families`): found 1,337 across the eight
extracted indexes, taken 1,169.

### Index inventories (every document family on the publisher index; taken counts)

**us-wa** — https://www.hca.wa.gov/health-care-services-supports/program-administration/apple-health-eligibility-manual
The overview links four hub pages (Drupal views blocks `eligibility-manual-general`, `-non-magi`,
`-magi`, `-ltss`) that list the manual pages. General requirements 63 found / 63 taken; Classic
(non-MAGI) 46 / 46; MAGI 16 / 16; LTSS 77 / 77; hub landing pages 4 / 0. "Additional tools":
Introduction overview and Program standards for income and resources 2 found / 0 taken as separate
documents because both resolve to pages already listed in the General hub (`introduction-overview`,
`program-standard-income-and-resources`); WAC index, revision log, Forms and publications and the DSHS
authorized-representative form 14-532: 4 found / 0 taken. 212 found, 202 taken. Each manual page carries
the WAC text of its rules (nested `node--type-wac` articles) plus clarifying information and worked
examples; selector `main article.node--type-eligibility-manual`, dropping the "report a problem" field.
Citation paths `us-wa/manual/hca/medicaid/resource-exclusions` etc. (page slug).

**us-ma** — https://www.mass.gov/law-library/130-cmr
The MassHealth member eligibility regulations 130 CMR 501.000–508.000 and 515.000–522.000 (the
publisher lists 501, 502, 503, 504, 505, 506, 508, 515, 516, 517, 518, 519, 520, 522; there is no 507,
509–514 or 521): 14 found / 14 taken. Other 130 CMR chapters on the same index (provider regulations
401–450, 610–650 etc.): 57 found / 0 taken. The mass.gov regulation page carries only the downloads (the
`.ma__download-link__file-link` marked "Open PDF file"), so each document is the page as `source_url`
and the official PDF as `download_url`. mass.gov rate-limits (intermittent HTTP 403 "Not allowed");
the builder paces requests at 3 s and retries a 403 after 20 s; extraction itself did not hit one.
Citation paths `us-ma/manual/eohhs/medicaid/130-cmr-501` … `130-cmr-522`. Reviewer judgment: these are
codified regulations ingested as `manual` per the work order (the NJ precedent from batch 1); 130 CMR
505 and 506 also exist in today's CHIP scope as `us-ma/regulation/130-cmr/505` and `/506`.

**us-in** — https://www.in.gov/fssa/ompp/forms-documents-and-tools/medicaid-eligibility-policy-manual/
IHCPPM chapter PDFs 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2600, 2800, 3000, 3200, 3300,
3400, 3500, 3600, 3800, 4200, 4600, 4700, 4800, 5000: 22 found / 22 taken. "All Chapters" combined PDF:
1 / 0. Transmittals page (`.../medicaid-program-policy-manual-transmittals`): 12 PDFs found / 0 taken.
35 found, 22 taken. Citation paths `us-in/manual/fssa/medicaid/ihcppm-chapter-2800`. Chapters 1600 and
3000 are also in today's CHIP scope under `us-in/manual/fssa/chip/ihcppm-chapter-*`.

**us-md** — https://health.maryland.gov/mmcp/Pages/MedicaidManual.aspx
Medicaid Manual PDFs: Beginning of Manual, Manual Table of Contents, Sections 200 Definitions, 300
Coverage Groups, 400 Application Requirements, 500 Non-Financial Eligibility Requirements, 600 The
Assistance Unit, 700 Income, 800 Resources, 800 Resource Table 2024, 900 Determining Financial
Eligibility for Non-Institutionalized Persons, 1000 Eligibility for Institutionalized Persons, 1100
Certification Periods, 1200 Post-Eligibility Requirements, 1300 Hearings, 1400 Fraud and Abuse, 1500
Liens, 1600 COMAR, Appendix schedules 2026 (effective 1/1/2026): 19 found / 19 taken. Manual
Supplements (Action Transmittals AT 06-25 … AT 07-11): 10 found / 0 taken (the `/mmcp/ManualSupplements/`
directory itself answers HTTP 401). Coverage-group guides (Guide to Medicaid Coverage Groups, Quick
Reference Guide, Point of Entry Crosswalk): 3 found / 0 taken. 32 found, 19 taken. Citation paths
`us-md/manual/mdh/medicaid/section-700`, `.../section-800-resource-table-2024`,
`.../appendix-schedules-2026`. Several section files carry old dates in their names (Section 1000
"Final 5-15-14", Section 1600 "COMAR 7-15-13"); HTTP Last-Modified for Section 700 is 2021-04-16.

**us-mo** — https://dssmanuals.mo.gov/family-mo-healthnet-magi/ and
https://dssmanuals.mo.gov/mo-healthnet-for-the-aged-blind-and-disabled/
The DSS Manuals site (WordPress) lists sections in a sidebar menu; as the MO SNAP manual scope did, the
pages were enumerated from the site's own sitemap (`wp-sitemap-posts-page-1.xml`, `-2.xml`) filtered to
the two manual prefixes. Family MO HealthNet (MAGI) manual pages incl. the landing page: 245 found / 245
taken; MAGI appendix PDFs (A income standards and CHIP premiums, D poverty guidelines, E CHIP premium
chart, F affordability-test instructions, H ME codes, I program descriptions, J lottery winnings): 7 / 7;
MAGI appendix spreadsheets (B reasonable-compatibility calculator .xlsx, G affordability calculator
.xlsm, K mandatory-programs .xlsx): 3 / 0. MHABD manual pages incl. landing page: 309 / 309; MHABD
appendix PDFs (C JCAHO facilities, H spend-down calculator instructions, J non-MAGI eligibility
standards, K non-MAGI eligibility): 4 / 4. 568 found, 565 taken. Selector `.entry-content`. Citation
paths keep the manual nesting: `us-mo/manual/dss/medicaid/magi/1805-000-00/1805-030-00/1805-030-10`,
`.../mhabd/0805-000-00/...`, appendices `.../magi/appendix-a`. MAGI appendices A and E are also in
today's CHIP scope under `us-mo/manual/dss/chip/magi-appendix-*`. Reviewer judgment: the same site also
hosts a General Information manual (189 pages), a December 1973 Eligibility Requirements manual (195
pages) and the Supplemental Nursing Care, Blind Pension, SAB and Supplemental Payments manuals; they are
not on the two Medicaid manual indexes and were not taken; the first two are Medicaid-adjacent and a
later batch should decide on them.

**us-wi** — https://www.dhs.wisconsin.gov/library/collection/p-10030 (Medicaid Eligibility Handbook)
and https://www.dhs.wisconsin.gov/library/collection/p-10171 (BadgerCare Plus Eligibility Handbook)
The online handbooks live on emhandbooks.wisconsin.gov, which does not answer TCP from this network
(curl 28 connection timeout at 20 s for `meh-ebd/meh.htm`, `bcplus/bcplus.htm` and the FoodShare
`fsh/home.htm`, plain and chrome120-impersonated). The Department's own publications library lists each
handbook release as a PDF; as the FoodShare handbook scope did (`us-wi-foodshare-manual.yaml`, release
26-01 PDF), the current release of each is taken: MEH Release 26-03 (`p10030-26-03.pdf`, 5.4 MB, 502
text-bearing pages) 1 found / 1 taken, prior MEH releases 19-02 … 26-02: 24 / 0; BadgerCare Plus
Eligibility Handbook Release 26-03 (`p10171-26-03.pdf`, 3.3 MB, 329 pages) 1 / 1, prior releases 24 / 0.
50 found, 2 taken. Citation paths `us-wi/manual/dhs/medicaid/meh-release-26-03`,
`.../badgercare-plus-handbook-release-26-03`. Not marked blocked: the PDF is the publisher's own copy,
not a mirror; the online-handbook URL is recorded in metadata for a later section-level pass.

**us-co** — Colorado Secretary of State CCR, Medical Services Board (Volume 8; Medical Assistance,
Children's Health Plan) rule list (`NumericalCCRDocList.do?deptID=7&agencyID=69`). Colorado publishes no
separate eligibility manual; Medical Assistance eligibility is 10 CCR 2505-10 Section 8.100
("Eligibility, Provider Screening, NPI"). The list carries 21 rules: 8.100 1 found / 1 taken; the other
20 (10 CCR 2505-3 CHP+ financial management; 2505-10 basis-and-purpose history; 8.000, 8.200–8.1000
benefits and provider rules; 8.2000 repealed; 8.3000–8.8000 fees, reports, COVID-19 expired, HCBS,
rural grants; MED 11E repealed) 20 / 0. The rule-info page is `source_url`; the current version's PDF
(`GenerateRulePdf.do?ruleVersionId=12656`, effective 08/14/2026 per the page) is `download_url`; 290
pages. Citation path `us-co/manual/hcpf/medicaid/10-ccr-2505-10-8-100`. Reviewer judgment: this is a
codified regulation taken as `manual` through the generic extractor at page granularity; the repository
already has `extract-colorado-ccr` (document_class `regulation`, section granularity, used for 10 CCR
2506-1); the controller may prefer to re-cut CO as `us-co/regulation/10-ccr-2505-10-8.100` with that
adapter. HCPF's own rules page (hcpf.colorado.gov) returns CloudFront 403 to every client; the SOS is the
official publisher of the CCR either way.

**us-mn** — https://hcopub.dhs.state.mn.us/epm/home.htm
RoboHelp output like the PA handbook; the topic tree comes from `whxdata/toc.new.js` and nested
`tocN.new.js`: 345 TOC entries (chapters 1 MHCP, 2 Medical Assistance, 3 MinnesotaCare, 4 Other Health
Care Programs, Appendices A–I), 344 distinct pages (topic 2.1.1.2.1 is listed twice): 345 found / 344
taken. Bulletin PDFs on the home page: 3 / 0. 348 found, 344 taken. Chapter/subchapter "book" pages are
short landing pages with an intro paragraph and were taken like PA's chapter title pages; archive links
inside topics (epmarchive) were not inventoried. Selector `#rh-topic`, dropping `p.Footer`. Citation
paths `us-mn/manual/dhs/medicaid/2-2-3-4`, `.../appendix-a`.

### Blocked publishers (no workaround attempted)

**us-az** — https://www.azahcccs.gov/Resources/EligibilityPolicy/ (AHCCCS Eligibility Policy Manual).
azahcccs.gov returns HTTP 403 Forbidden from `Microsoft-Azure-Application-Gateway/v2` within 1 s for
the Eligibility Policy path, the Medical Policy Manual path and the site root, for the Axiom user agent,
a plain Chrome user agent and curl-cffi chrome120 impersonation (179–581 byte bodies). No index
inventory possible.

**us-tn** — https://www.tn.gov/tenncare/policy-guidelines/eligibility-policy.html (TennCare Eligibility
Policy). tn.gov returns HTTP 403 Forbidden from `awselb/2.0` within 1 s (118–520 byte bodies) for the
Axiom user agent, a plain Chrome user agent and chrome120 impersonation; `tn.gov/tenncare.html` did not
answer at all. No index inventory possible.

### Batch-1 retries (CA, OH), about 60 s total

- **us-ca** — 2026-09-10T18:36Z plain request: HTTP 403, 881-byte Incapsula interstitial (incident id
  648000110658208525-192905496909841125). 2026-09-10T18:37Z curl-cffi chrome120, 20 s timeout: HTTP 403,
  882 bytes, Incapsula. Same failure; row note appended.
- **us-oh** — codes.ohio.gov (OAC 5160:1): plain request curl 28 connect timeout at 20 s; chrome120 the
  same. Same failure. medicaid.ohio.gov Medicaid Eligibility Procedure Letters index: plain request still
  HTTP 404 (5,279 bytes), but chrome120 impersonation now returns HTTP 200 (399,073 bytes) where batch 1
  saw 404. Reviewer judgment: not ingested in this batch. The eligibility manual is the OAC 5160:1 rule
  set, which remains unreachable; the procedure letters are a separate family and alone would not be the
  manual. Row stays `blocked_primary_source` with the outcome appended, and a later batch can take the
  MEPL family with `request: browser_impersonation: true` if the controller wants it before the rules.

### Already in corpus (done, pointers)

None this batch (see selection above).

## Artifacts (unsigned, uncommitted, awaiting controller)

- `data/corpus/sources/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual/official-documents/*`
- `data/corpus/inventory/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.json`
- `data/corpus/provisions/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.jsonl`
- `data/corpus/coverage/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.json`

for xx in wa, ma, in, md, mo, wi, co, mn, under `/Users/pavelmakarchuk/axiom-corpus/data/corpus` (main
checkout), alongside batch 1's artifacts.

Rebuild:

```bash
uv run python scripts/build_medicaid_state_eligibility_manual_manifests.py --batch 2
for j in wa ma in md mo wi co mn; do
  uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-10-medicaid-state-eligibility-manual \
    --manifest manifests/us-$j-medicaid-eligibility-manual.yaml \
    --source-as-of 2026-09-10 --expression-date 2026-09-10
done
```

Lint: `uv run ruff check scripts/build_medicaid_state_eligibility_manual_manifests.py` is clean (it
reported one B007 in the batch-1 `build_ny`, fixed by renaming the unused loop variable).
`uv run ruff check scripts/` also reports 8 pre-existing findings in `scripts/build_liheap_state_plan_manifests.py`
(unused `os` import) and `scripts/draft_program_work_orders.py` (import style, semicolons); those
scripts are outside this batch and were left alone (reviewer judgment).

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped (62 s). The 10 failures are exactly the expected pre-existing data-dependent
tests of this sparse worktree (`test_be_rulespec_2026_08_23_promotion`, `test_build_ny_tanf_compatibility_scope` x2,
`test_rulespec_be_source_promotion`, `test_us_ak/ct/mi/mt/nd/ny_snap_manual`); none touches the Medicaid manifests or
the generator, and no other test failed.

## Reviewer judgments (all of them)

1. Batch selection: the next ten states by population, none replaced; partial CHIP-scope overlaps
   (MA 130 CMR 505/506, IN IHCPPM 1600/3000, MO MAGI appendices A/E) were not treated as existing
   coverage and the documents were re-fetched under Medicaid citation paths.
2. PDF manuals at page granularity with OCR fallback; `expression_date` = fetch date (as batch 1).
3. WA: the 202 hub-listed pages are the manual; hub landing pages, WAC index, revision log and forms
   are not taken; the two "additional tools" pages are the same nodes as two General-hub pages.
4. MA: 130 CMR 501–522 (codified regulations) ingested as `manual` per the work order, PDF via
   `download_url` because the regulation page carries no text; provider chapters not taken.
5. IN: the combined "All Chapters" PDF and the 12 transmittals are not taken.
6. MD: the 2024 resource table and the 2026 appendix schedules are taken as manual documents; action
   transmittals and coverage-group guides are not.
7. MO: both manuals in full from the site sitemap with the landing pages as roots; PDF appendices taken,
   spreadsheet appendices not; the General Information and December 1973 Eligibility Requirements
   manuals on the same site left for a later decision.
8. WI: the publisher's current-release PDFs (26-03) are taken because the online-handbook host is
   unreachable; prior releases not taken; not marked blocked.
9. CO: 10 CCR 2505-10 8.100 alone is the eligibility "manual", taken as `manual` at page granularity
   through the generic extractor instead of the existing CCR adapter/regulation class; the other 20
   Volume 8 rules are not taken.
10. MN: all 344 TOC pages incl. book landing pages; home-page bulletins not taken.
11. AZ and TN recorded as blocked from this network with the WAF responses; no impersonation beyond the
    existing manifest option, no proxies, no mirrors.
12. CA: same failure on retry. OH: codes.ohio.gov same failure; medicaid.ohio.gov MEPL index newly
    reachable with impersonation but not ingested (rules are the manual; letters are a separate family).
13. `ruff` findings in two unrelated scripts under `scripts/` left unfixed.
14. The generator's `main()` was rewritten (batch switch) and `build_ny` had a variable renamed; no
    library function was touched.

## Remaining for later batches

States not yet attempted (by population): SC, AL, LA, KY, OR, OK, CT, UT, IA, NV, MS, KS, NM, NE, ID,
WV, HI, NH, ME, MT, RI, DE, SD, ND, AK, DC, VT, WY, plus the territories. Probes made while selecting
this batch (not attempts): scdhhs.gov HTTP 403 (919 bytes), ldh.la.gov HTTP 403 (4,542 bytes),
chfs.ky.gov HTTP 403 (1,484 bytes), medicaid.alabama.gov no TCP answer within 20 s; SC/LA/KY/AL will
need another network or an official export. CA, OH, AZ, TN need a retry from another network or an
official export. Follow-on families: MO General Information and December 1973 Eligibility Requirements
manuals; WI section-level pass from the online handbook when reachable; MD action transmittals; IN
transmittals; NY GIS/ADM and the batch-1 list (TX TWH Parts B–X, NC letters/change notices, GA MTs,
federal 42 CFR part 436). Controller steps after review: decide `manual` vs `regulation` for MA, CO
(and batch 1's NJ), `sign-ingest-manifest` per scope, immutable release selector,
`publish_corpus.py --dry-run`, then publication and activation.
