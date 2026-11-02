# TANF state policy manuals, batch 1

Date: 2026-09-10
Program: TANF (board Year 1 list; `manifests/tanf-agent-queue.yaml`)
Branch: `discovery/ingest-tanf` (worktree, sparse checkout without `data/corpus`; artifacts written to the shared corpus root of the main checkout)

started_at: 2026-09-10T16:36:01+0200
finished_at: 2026-09-10T17:12:08+0200
agent wall time: 36 min 7 s

## Batch rule (reviewer judgment 1)

Queue rows were walked in queue order (AL, AZ, CA, CO, DC, DE, FL, GA, HI, IL, IN, KS, ME, MO, MS, MT,
NC, ND, NV, NY, OK, OR, PA, SC, SD, TX, VA, WA). A state whose current TANF cash assistance policy
manual, or the adopted rule the state itself publishes as its primary policy document, is already in
the corpus (`data/corpus/coverage/us-xx`, the prior-ingest manifest list, `docs/ingest-runs/2026-07-0*`)
was marked `done` with the existing manifest and scope and does not count toward the batch. The
combined manuals FL (DCF ESS Program Policy Manual, FS/TCA/Medicaid), IL (DHS Cash, SNAP and Medical
Manual), IN (FSSA SNAP/TANF Program Policy Manual, page-level) and NV (DWSS Eligibility and Payments
Manual) were judged to count as the TANF manual even though they are not on the prior-ingest list.
AL (rule 660-2-2 + state plan + payment-manual appendix, no separate DHR manual index) and NC (only
Work First Manual section 114 is in the corpus) are `done` per the prior-ingest list with that caveat
recorded on the row.

Batch 1 = the first ten remaining rows: **CA, CO, DC, MO, MS, MT, ND, NY, OK, OR**. Blocked publishers
count as attempted. PA, SC, SD, VA stay `needs_review` with a batch-2 note.

## Results

| jurisdiction | status | document_class | documents taken / on index | provisions | elapsed s |
|---|---|---|---|---|---|
| us-ca | extracted | regulation | 13 / 27 | 315 | 20 |
| us-co | extracted | regulation | 1 / 31 (1 current + 30 archived versions) | 61 | 6 |
| us-dc | extracted | manual | 1 / 2 | 551 | 5 |
| us-mo | extracted | manual | 486 / 486 | 1039 | 418 |
| us-ms | extracted | manual | 1 / 2 | 975 | 8 |
| us-mt | extracted | manual | 93 / 93 | 395 | 41 |
| us-nd | extracted | manual | 310 / 310 | 622 | 56 |
| us-ok | extracted | regulation | 1 / 190 API segments | 63 | 4 |
| us-ny | blocked_primary_source | manual | 0 / 1 | 0 | - |
| us-or | blocked_primary_source | regulation | 0 / unknown | 0 | - |

Attempted 10, extracted 8, blocked 2, done-already 14 (AL, AZ, DE, FL, GA, HI, IL, IN, KS, ME, NC, NV,
TX, WA), later batch 4 (PA, SC, SD, VA), federal row recorded (see below).

Provision total: 4,021 rows across 8 scopes, every scope `complete: true`, 0 missing,
0 extra, 0 duplicate citation paths (duplicates re-checked directly on the provisions JSONL:
`citation_path` values unique in every file). Version for every scope:
`2026-09-10-tanf-state-policy-manual`; document_class `manual` for agency manuals and `regulation`
where the state's primary policy document is an adopted rule the state itself publishes (CA MPP,
CO 9 CCR 2503-6, OK OAC 340:10). Smoke runs (scratch base): CO first, then OK, MT, MO, MS, DC, ND, CA.

Artifacts (unsigned, uncommitted, awaiting controller), per scope:

- `data/corpus/sources/<jur>/<class>/2026-09-10-tanf-state-policy-manual/official-documents/...`
- `data/corpus/inventory/<jur>/<class>/2026-09-10-tanf-state-policy-manual.json`
- `data/corpus/provisions/<jur>/<class>/2026-09-10-tanf-state-policy-manual.jsonl`
- `data/corpus/coverage/<jur>/<class>/2026-09-10-tanf-state-policy-manual.json`

## Index inventories

**California (us-ca, regulation).** Index: CDSS "Eligibility and Assistance Standards" regulations page,
https://www.cdss.ca.gov/inforesources/Rules-Regulations/Legislation-and-Regulations/CalWORKs-CalFresh-Regulations/Eligibility-and-Assistance-Standards.
One family: 27 MPP EAS DOCX files (`/Portals/9/Regs/Man/EAS/*.docx`, index ordinals 1-26 plus an
unnumbered Div 51 file), Divisions 40 through 91. Taken: ordinals 1-13 = Divisions 40-44 (reception
and application, eligibility, responsible relatives, assistance standards: income, AU composition and
need, MAP/payment). Not taken: Div 46-51 (refugee cash, IHSS, adoptions, foster care), Div 80-91
(administration, hearings, demonstration projects). Citation path `us-ca/regulation/mpp/eas/<ordinal>/<section>`
(e.g. `.../eas/10/44-113`); expression_date = each file's HTTP Last-Modified (2024-08-26 to 2026-06-30).
Extraction: new DOCX segmentation `styled_labeled_sections` (see code changes). 13 documents, 302
sections. The CDSS host answers plain clients with a link-less page, so `request.browser_impersonation`
is on (the plain fetch is tried first).

**Colorado (us-co, regulation).** Index: Secretary of State CCR rule-info page for 9 CCR 2503-6
(Colorado Works Program), https://www.coloradosos.gov/CCR/DisplayRule.do?action=ruleinfo&ruleId=3145&...
Family: 1 current version (effective 2025-07-01, permanent rule adopted 2025-05-09, PDF + DOCX) and
30 archived versions. Taken: the current PDF (`GenerateRulePdf.do?ruleVersionId=12030`), the official
version per the SoS page. Citation path `us-co/regulation/9-ccr-2503-6/<3.6xx[.y]>`; 60 sections
(3.600-3.609 with their numbered subsections). CDHS's own Colorado Works pages link to this SoS rule;
Colorado has no separate agency manual for Colorado Works. The prior CO SNAP scope used the
`extract-colorado-ccr` adapter; this one uses the official-documents extractor per the work order.

**District of Columbia (us-dc, manual).** Index: DHS "ESA Policy Manuals",
https://dhs.dc.gov/publication/esa-policy-manuals. Family: 2 PDFs - "ESA SNAP Policy Manual 1-24-25"
(already in the corpus as `us-dc/manual/dhs/esa/snap-policy-manual`) and "ESA Policy Manual-Combined
Revised 2" (TANF, Medical Assistance, GC, IDA, Burial Assistance; 550 pages; HTTP Last-Modified
2019-01-09). Taken: the combined manual. Citation path `us-dc/manual/dhs/tanf/esa-policy-manual/page-N`.

**Missouri (us-mo, manual).** Index: DSS Temporary Assistance/Case Management Manual,
https://dssmanuals.mo.gov/temporary-assistance-case-management/ (30 chapters 0200-0330 listed on the
landing page; every section page enumerated from the site's WordPress sitemaps
`wp-sitemap-posts-page-{1,2}.xml`). Family: landing page + 472 section pages + 14 appendix PDFs
(A-Y as listed: B consolidated standard, C maximum grant amounts and cash diversion amounts, H, I, K, L
sanction amounts, M, N, O, P, Q, R, Y). Taken: all 486. Citation path
`us-mo/manual/dss/tanf/<section number, e.g. 0210-005-05>` (the descriptive slug suffix is kept only
where two pages share a number prefix), `.../appendix-<letter>`, `.../navigation/landing`.
expression_date = sitemap lastmod per page; HTML content selector `.entry-content`; appendix PDFs page-level.
Titles come from each page's `<title>` (fetched during manifest generation).

**Mississippi (us-ms, manual).** Index: MDHS TANF page https://www.mdhs.ms.gov/help/tanf/ (links 2
documents: "TANF Policy Manual" and a TANF flyer; client forms are on a sub-page). The manual is
published through the Secretary of State administrative code as Title 18 Part 13 Volume III,
https://www.sos.ms.gov/adminsearch/ACCode/00000330c.pdf (976 pages, HTTP Last-Modified 2024-12-05;
the same host/pattern as the ingested MS SNAP manual). Taken: the manual, page-level
(`us-ms/manual/mdhs/tanf/volume-iii/page-N`, 974 non-empty pages). Both hosts answer plain clients
with resets/Akamai 403; `request.browser_impersonation` is on.

**Montana (us-mt, manual).** Index: DPHHS TANF Policy Manual,
https://dphhs.mt.gov/hcsd/Manuals/TANFpolicymanual (case-sensitive path; the lower-case URL and the
old `/hcsd/tanfpolicymanual` return 404). Family: 93 section PDFs with effective dates (0-1 TOC, 0-2
index, 0-3 introduction, 0-4 definitions, 001 monthly income standards, sections 101-1 through 1702-1;
effective dates 2018-01-01 to 2025-12-01). Taken: all 93, page-level like the MT SNAP manual
(`us-mt/manual/dphhs/tanf/<section>/page-N`), expression_date = the listed effective date per section.
The same page also lists the TANF State Plan 1/2024-12/2026 PDF (state-plan family, not taken).

**North Dakota (us-nd, manual).** Index: HHS TANF Policy Manual 400-19 (MadCap TriPane),
https://www.nd.gov/dhs/policymanuals/40019/40019.htm; TOC `Data/Tocs/40019_Chunk0.js`. Family: 307
topic pages (400-19-05 definitions through the sanction, hearing and payment sections) + landing
(`Default.htm`, "Current Release 26.1", last published June 30, 2026) + Release Log. Taken: all 310.
Citation path `us-nd/manual/hhs/tanf/400-19-105-25` etc., navigation snapshots under `.../navigation/`.
expression_date 2026-04-01 (Release 26.1 effective date from the release log). Content selector
`#mc-main-content`; the SNAP manual's `Content/` path layout does not apply here (topics live at the site root).

**Oklahoma (us-ok, regulation).** OKDHS publishes its TANF policy as OAC 340:10 through the
Secretary of State rules portal (the legacy `oklahoma.gov/okdhs/library/policy/current/oac-340/chapter-10.html`
redirects to https://rules.ok.gov/home). Family: the chapter API
(`GetSegmentsByChapterNum?titleNum=340&chapterNum=10`) returns 190 segments: 1 chapter, 17 + 3
subchapters, 4 parts, 62 active sections, 64 revoked sections, 39 revoked appendices. Taken: the chapter
as one JSON document, records for every non-revoked segment (63 provisions incl. root), same
extraction config as `us-ok-snap-rules`. rules.ok.gov and the API return Cloudflare 403 to plain
clients on 2026-09-10 (they did not in July), so the manifest uses `browser_impersonation_direct`.

**New York (us-ny) - blocked.** Index https://otda.ny.gov/programs/temporary-assistance/ links the
Temporary Assistance Source Book, https://otda.ny.gov/programs/temporary-assistance/TASB.pdf (HEAD
Last-Modified 2024-11-27). Plain requests/curl: TCP connection reset by peer. Browser impersonation
(chrome, chrome110, chrome124, edge101, firefox): HTTP 200 `text/html` 6.7 KB JavaScript bot-challenge
page ("Please enable JavaScript to view the page content. Your support ID is ...") instead of the PDF;
safari profiles: connection reset. Not worked around. The 2024-2026 TANF State Plan and the
Employment Policy Manual are already in the corpus.

**Oregon (us-or) - blocked.** Oregon's TANF policy is OAR chapter 461 (ODHS per-rule PDFs at
https://ch461rules.odhs.oregon.gov/ ; SoS OARD at https://secure.sos.state.or.us/oard/). From the
ingest environment neither host resolved: the system resolver returns SERVFAIL for
`ch461rules.odhs.oregon.gov`, `www.oregon.gov` and `secure.sos.state.or.us` (dig EDE "at delegation
oregon.gov"), 8.8.8.8 and 9.9.9.9 return no answer, 1.1.1.1 does resolve them, and Python
`getaddrinfo`/requests/curl all fail with name-resolution errors. No index could be inventoried;
retry from another network. The existing `us-or/manual` scope (OPEN eligibility notebook) is not the
TANF manual. Chapter 461 is a combined rulebook for all self-sufficiency programs, and an OAR adapter
(`extract-oregon-administrative-rules`) already exists - both are noted on the queue row.

**Federal (us).** 45 CFR parts 260-265 are not in the corpus: `data/corpus/coverage/us/regulation`
holds title 45 part 1302 only, and no manifest or ingest-run note references parts 260-265 (the
queue file's own lead list is the only mention). Not re-ingested. The ACF Office of Family
Assistance TANF state plans are a separate later family: no consolidated plan index was found on
acf.gov on 2026-09-10 (`/ofa/programs/tanf/state-plans` 404; the OFA TANF program page and the
state map page carry no plan links; the resource-library type filter answers HTTP 202 challenge to
non-browser clients). `index_document_count` is left null on the row.

## Code changes

`src/axiom_corpus/corpus/documents.py`: new DOCX segmentation `styled_labeled_sections`
(`_extract_styled_labeled_docx_section_blocks`) plus a two-line dispatch at the top of
`_extract_docx_blocks`. It starts sections only at heading-styled paragraphs (or, with
`heading_paragraphs_only: false`, at body paragraphs whose heading text matches
`heading_text_pattern`), never at table rows, strips `(Continued)`/`(Cont.)` and merges a label that
reappears (page-break restatements) into its first section. Tests:
`tests/test_corpus_documents_styled_labeled_docx.py` (6 tests). GitNexus impact analysis was NOT run
because the GitNexus MCP tools were unavailable in this session; the only existing function touched
is `_extract_docx_blocks` (added dispatch branch before the existing `labeled_sections` branch,
existing inputs unchanged).

Why: the CDSS EAS DOCX files restate every section heading at each page break and quote section
numbers at the start of relocation-table rows, so the plain `labeled_sections` DOCX extractor produced
duplicate citation paths (coverage fails) and the `california-mpp-calfresh` adapter is hard-wired to
Division 63.

## Reviewer judgments

1. Batch rule and done/combined-manual calls (above), including AL and NC caveats, and NV/FL/IL/IN
   combined manuals counted as done.
2. Blocked publishers NY (bot challenge) and OR (DNS from this environment) count as attempted
   batch-1 rows; OR may not be a publisher block - retry elsewhere before assigning adapter work.
3. `regulation` for CA, CO, OK (state-published adopted rules are the primary policy document) with
   the existing regulation citation conventions (`us-ca/regulation/mpp/...`, `us-co/regulation/9-ccr-2503-6`,
   `us-ok/regulation/oac/340/10`) rather than the manual convention `us-xx/manual/<agency>/tanf/...`.
4. CA scope = EAS Divisions 40-44 only (13 of 27 files); merged headings keep the first heading text,
   so where a relocation-table line precedes the real heading (11EAS: 44-203, 44-205, 44-206) the
   section heading is the table row's text and the relocation rows are attributed to those sections.
5. Page-level extraction for DC (Part/Chapter numbering restarts per part), MS (chapter pagination
   without machine-stable labels), MT and MO appendix PDFs; section-level extraction for CO (3.6xx
   and 3.6xx.y; the editor's notes at the end fall into 3.609.74; 3.609's wrapped heading keeps only
   its first line as heading).
6. DC's combined ESA manual is dated 2019-01-09 but is what DHS lists as current; MS's manual file is
   dated 2024-12-05 with per-section revision dates inside.
7. MO citation suffixes use the section number, with the descriptive slug kept for the two number
   prefixes shared by two pages (`0205-040-05-17*`, `0235-010-01*`).
8. Tests: the focused subset passes except 10 tests that read `data/corpus` artifacts absent from
   this sparse worktree (listed below); the same 10 pass in the main checkout.

## Timing

Per-jurisdiction extraction seconds (full runs, shared corpus root): CA 20, CO 6, DC 5, MO 418,
MS 8, MT 41, ND 56, OK 4. Manifest generation about 10 s per state plus about 10 min for the Missouri
title fetch (cached for the run).

## Tests

`uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery or styled_labeled"`
-> 261 passed, 10 failed, 2 skipped in the worktree. The 10 failures are `FileNotFoundError` on
`data/corpus/...` artifacts (sparse checkout): test_be_rulespec_2026_08_23_promotion,
test_build_ny_tanf_compatibility_scope (2), test_rulespec_be_source_promotion, test_us_ak_snap_manual,
test_us_ct_snap_manual, test_us_mi_snap_manual, test_us_mt_snap_manual, test_us_nd_snap_manual,
test_us_ny_snap_manuals. Re-run of exactly those 10 in the main checkout (`-p no:cacheprovider`):
10 passed. New tests: 6 passed.

## Rebuild

```bash
uv run python scripts/build_tanf_state_policy_manual_manifests.py   # fetches every index live
for st in ca co dc mo ms mt nd ok; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base data/corpus --version 2026-09-10-tanf-state-policy-manual \
    --manifest manifests/us-$st-tanf-state-policy-manual.yaml
done
```

No TLS chain repair was needed (no `data/certs` additions). No credentials read or written.

## Remaining

Batch 2 (queue order): PA (OIM Cash Assistance Handbook, HTML), SC (TANF Policy Manual Volume 65 PDF),
SD (ARSD 67:10 rules), VA (TANF manual PDFs). Retry NY and OR. Federal: 45 CFR 260-265 via
`extract-ecfr`, and locate the ACF OFA state plan index. Controller: `sign-ingest-manifest` per scope,
immutable release selector, `publish_corpus.py --dry-run`, publish.
