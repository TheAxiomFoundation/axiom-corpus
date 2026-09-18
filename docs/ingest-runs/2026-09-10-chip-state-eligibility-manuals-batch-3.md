# CHIP state eligibility manuals, handbook chapters and adopted rules, batch 3

Date: 2026-09-10
Program: CHIP (board Year 1 list; `manifests/chip-agent-queue.yaml`)
Branch: `discovery/ingest-chip` (continues docs/ingest-runs/2026-09-10-chip-state-eligibility-manuals-batch-2.md)

Timing: started_at 2026-09-10T20:43:54Z, finished_at 2026-09-10T21:21:00Z, agent wall time 37 min 6 s
(a first attempt was killed at startup and left nothing behind; this run started from the clean worktree).
GitNexus impact analysis was not run: the GitNexus MCP tools were not available in this session. No
adapter or library function was modified and no new adapter was needed. The only code change is in
`scripts/build_chip_state_eligibility_manifests.py`: batch-3 dictionaries (`CONFIRMED_BATCH3`,
`BLOCKED_BATCH3`, `DONE_BATCH3`, `NEW_ROW_NAMES_BATCH3`), four small helpers (`_ms_chapter_extraction`,
`_nm_part_doc`, `_sd_chapter_doc`, the Oklahoma record constants) and four one-line merges in `main()`.
Batch-1 and batch-2 manifests regenerate byte-identical (git shows only the queue and the eight new
manifests). `uv run ruff check scripts/build_chip_state_eligibility_manifests.py` passes.

Source family and conventions are batch 1's: the state agency's own CHIP eligibility manual, handbook
chapter, or adopted eligibility rule (or the combined Medicaid eligibility manual chapters / MAGI rules
that govern Medicaid-expansion CHIP), confirmed from the publisher's own index; document_class `manual`
(or `regulation` for an adopted rule); version `2026-09-10-chip-state-eligibility-manual`; citation
paths `us-xx/manual/<agency>/chip/<section>`, regulation scopes following each jurisdiction's existing
regulation citation convention. CMS state plan amendments were not re-ingested.

Work order: the next ten states by population not in the queue (KY, OR, OK, UT, NV, AR, MS, NM, NE,
WV) with up to six replacements. AR and WV are already covered by combined manuals in the corpus and
were marked done by pointer; OR and NE blocked on the first probe; the six replacements HI, NH, ME, MT,
RI, SD were drawn in that order, of which HI, NH and MT blocked. UT then blocked with no replacement
left, so 8 states were attempted for extraction (the order's target was ten) and 16 states were probed
(the cap). Probe = one plain request plus one chrome120 browser-impersonation request, 20 s timeouts.

## Result

| Jurisdiction | Status | Scope | Index docs | Taken | Provisions | Extract s |
|---|---|---|---|---|---|---|
| us-ky | agent_ready | us-ky/regulation | 2 | 2 | 4 | 3 |
| us-or | blocked_primary_source | - | n/a (DNS SERVFAIL) | 0 | - | - |
| us-ok | agent_ready | us-ok/regulation | 397 | 1 | 28 | 5 |
| us-ut | blocked_primary_source | - | n/a (403) | 0 | - | - |
| us-nv | agent_ready | us-nv/manual | 93 | 2 | 22 | 2 |
| us-ar | done (pointer, Medicaid run) | us-ar/manual (medicaid) | 1 | 0 | - | - |
| us-ms | agent_ready | us-ms/manual | 27 | 3 | 201 | 6 |
| us-nm | agent_ready | us-nm/regulation | 4 | 4 | 78 | 2 |
| us-ne | blocked_primary_source | - | n/a (403 after chain repair) | 0 | - | - |
| us-wv | done (pointer, existing IMM scope) | us-wv/manual (IMM) | 1 | 0 | - | - |
| us-hi | blocked_primary_source | - | n/a (522) | 0 | - | - |
| us-nh | blocked_primary_source | - | n/a (403) | 0 | - | - |
| us-me | agent_ready | us-me/regulation | 6 | 1 | 11 | 1 |
| us-mt | blocked_primary_source | - | n/a (SPA, API 403) | 0 | - | - |
| us-ri | agent_ready | us-ri/regulation | 4 | 2 | 44 | 2 |
| us-sd | agent_ready | us-sd/regulation | 13 | 2 | 33 | 3 |

Probed 16; attempted 8; extracted 8 jurisdictions (17 documents, 421 provisions); blocked 6;
done-by-pointer 2. Index documents found on the eight extracted publishers' indexes: 546; taken 17.
Coverage `complete: true` for every extracted scope, 0 missing, 0 extra, 0 duplicate citation paths
(and 0 duplicate source citations). Uniqueness was re-verified directly on each provisions JSONL; every
new citation path was checked against every other provisions JSONL under
`data/corpus/provisions/<jurisdiction>/` (0 cross-scope collisions, so no document was skipped for
that reason). Every inventory item names an existing non-symlink regular file under the exact
`sources/<jurisdiction>/<class>/<version>/` boundary with a matching SHA-256, and every provision's
source path is in its inventory. Smoke runs (scratch base) for all eight scopes preceded the full runs;
changes between smoke and full run: NM label pattern (the SRCA pages write `8.291.400 .1` with a space
before the dot, so the label is now built from the section number group), OK switched from the OHCA
policy site pages to the Secretary of State rules API (see reviewer judgment 1), and the OK disclaimer
drop selector. Extract seconds are wall seconds of the final `extract-official-documents` command.
Queue status_counts after this batch: done 8, agent_ready 25, blocked_primary_source 14 (47 rows).

Artifacts (unsigned, uncommitted, awaiting controller; `data/corpus` lives in the main checkout, the
worktree is sparse):

- `data/corpus/sources/us-xx/<class>/2026-09-10-chip-state-eligibility-manual/official-documents/*`
- `data/corpus/inventory/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.json`
- `data/corpus/provisions/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.jsonl`
- `data/corpus/coverage/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.json`

for us-nv, us-ms (manual) and us-ky, us-ok, us-nm, us-me, us-ri, us-sd (regulation).

TLS: verification was never disabled. rules.nebraska.gov (Secretary of State, Nebraska Administrative
Code) serves its leaf certificate without the issuing intermediate "DigiCert Global G2 TLS RSA SHA256
2020 CA1"; that intermediate was already committed at `data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem`
and was used through REQUESTS_CA_BUNDLE / CURL_CA_BUNDLE (certifi + that file); the chain then
verifies, after which the host returns HTTP 403, so NE is blocked, not a TLS problem. `data/certs` is
unchanged. Hosts that 403 plain clients and are read through the existing manifest
`request: browser_impersonation: true` fallback: prod-ok-rules-api.tecuity.com (Oklahoma rules API).

Rebuild:

```bash
uv run python scripts/build_chip_state_eligibility_manifests.py
for j in ky ok nv ms nm me ri sd; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-chip-state-eligibility-manual \
    --manifest manifests/us-$j-chip-state-eligibility-manual.yaml --source-as-of 2026-09-10
done
```

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped. The 10 failures are the known sparse-worktree failures (BE rulespec
promotion, NY TANF compatibility x2, BE source promotion, AK/CT/MI/MT/ND/NY SNAP manual tests), all
`data/corpus` artifacts absent from this worktree; none touch CHIP files.

## Per-jurisdiction index inventories

- **us-ky** LRC index for 907 KAR Chapter 4 https://apps.legislature.ky.gov/law/kar/titles/907/004/:
  2 regulations (one family, KAR regulation HTML pages): 907 KAR 4:020 KCHIP Medicaid Expansion and
  907 KAR 4:030 KCHIP Phase III, both amended effective 2023-01-12 (HISTORY lines). Taken 2, one HTML
  document each (`div.regulation-content`), one provision per regulation: the LRC page marks every
  section and paragraph as an h2 with the text in spans, so the extractor's fallback whole-container
  text is used (7,307 and 7,092 characters; Section 1 through the last section present; the HISTORY /
  FILED WITH LRC footer sits outside the container and is not captured). The DCBS Operations Manual
  Volume IVA was not located on a public chfs.ky.gov index.
- **us-or** (blocked) OAR chapter 410 (OHA) on the Secretary of State OARD
  https://secure.sos.state.or.us/oard/displayChapterRules.action?selectedChapter=94: the oregon.gov
  DNS zone did not resolve at 20:52Z (dig @1.1.1.1 and @8.8.8.8: SERVFAIL for secure.sos.state.or.us,
  www.oregon.gov and the oregon.gov NS lookup); plain and chrome120 probes failed with name resolution
  errors. Probably transient. 0 taken.
- **us-ok** Oklahoma Secretary of State Office of Administrative Rules chapter listing for OAC 317:35
  (rules.ok.gov segments API, same publisher and mechanism as us-ok-snap-rules.yaml): 397 segments,
  families 350 sections, 29 parts, 17 subchapters, 1 chapter (292 in force, 82 Revoked, 17 Terminated,
  4 Reserved, 2 AmendedAndRenumbered). Taken 1 document: the chapter JSON filtered to Subchapter 6
  SoonerCare for Pregnant Women and Families with Children (label prefix 317:35-6-, Revoked/Reserved
  excluded): 27 section provisions plus the document record; 317:35-6-62 and 62.1 (AmendedAndRenumbered)
  carry no text in the API. The OHCA policy site
  https://oklahoma.gov/ohca/policies-and-rules/xpolicy/medical-assistance-for-adults-and-children-eligibility/soonercare-for-pregnant-women-and-families-with-children.html
  lists the same 29 sections (this was the first probe, HTTP 200) but its footer states the copies are
  unofficial, so it is recorded only as `agency_policy_site_index`. Not taken: subchapters 5, 10, 22.
- **us-ut** (blocked) Utah DHHS Office of Eligibility Policy CHIP Manual index
  https://oepmanuals-chip.dhhs.utah.gov/Welcome_page.htm (separate CHIP manual, effective 2024-05-01):
  HTTP 403 AccessDenied (111-byte XML) to plain and chrome120 clients for the welcome page and the root.
  medicaidpolicy.utah.gov and bepmanuals.health.utah.gov (former Medicaid eligibility manual hosts) are
  NXDOMAIN; R382-10 lives only in the eRules single-page app (adminrules.utah.gov, plain client 404, no
  public rule endpoint in its bundle); medicaid.utah.gov (HTTP 200) publishes no eligibility manual;
  jobs.utah.gov/customereducation 403. The existing us-ut/manual DWS Eligibility Manual has no CHIP
  chapter. 0 taken.
- **us-nv** DWSS Medical Assistance Manual index
  https://dwss.nv.gov/programs/medical/medical-assistance-manual/: 93 documents. Families: chapter PDFs
  23 (A-100 to H-200), appendix PDFs 9, full manual PDF 1, table of contents 1, manual transmittal
  letters 59. Nevada Check Up (separate CHIP) is section B-120.2 of B-100 MAGI Medical Categories.
  Taken 2: B-100 (March 2017, 8 pages) and Appendix A MAGI Income Charts (November 2024, 12 pages),
  page-level. Not taken: E-100 MAGI Budget Methodology; the 2014 Nevada Check Up Manual "revised
  sections" PDF linked from the Nevada Check Up page. dhcfp.nv.gov (Nevada Medicaid) answers but its
  CHIP pages redirect to the home page; the first DWSS URL guess 404'd before the index was found.
- **us-ar** (done by pointer) DHS Division of County Operations Medical Services Policy Manual
  (MS-Policy-9.26-New.pdf, one document, 563 page provisions at us-ar/manual/dco/medicaid/policy-manual,
  version 2026-09-10-medicaid-state-eligibility-manual, parallel Medicaid run); the text names ARKids A
  and ARKids B throughout. Nothing separate to add. Not probed.
- **us-ms** Division of Medicaid Eligibility Policy and Procedures Manual index
  https://medicaid.ms.gov/medicaid-coverage/eligibility-policy/: 27 documents (chapter PDFs 7: 100, 101,
  102, 200, 300, 400, 500; appendix PDFs 20). Taken 3: Chapter 101 Coverage Groups and Processing
  Applications and Reviews (September 2025, 120 pages, 111 labeled sections from page 6), Chapter 400 ABD
  and MAGI Eligibility Criteria and Budgeting (July 2025, 92 pages, 74 labeled sections from page 4;
  400.18-400.19 children and CHIP), Appendix A-3 MAGI Income Limits chart (13 pages, page-level). The
  chapter running headers and "Effective Month" lines are dropped; two-line headings (label on one line,
  title on the next) are joined. 101.18 and 101.19 are title-only containers.
- **us-nm** SRCA NMAC Title 8 index https://www.srca.nm.gov/nmac-home/nmac-titles/title-8-social-services/:
  Chapter 291 Medicaid Eligibility - Affordable Care (the chapter link 301-redirects to the title page,
  whose chapter 291 entry lists only reserved ranges; the in-force parts were confirmed by fetching:
  400, 410, 420, 430 HTTP 200; 440-600 404). Taken 4 (one family, NMAC part HTML): 8.291.400 Eligibility
  Requirements (14 sections, amended through 2024-09-01), 8.291.410 General Recipient Requirements (26,
  2024-07-01), 8.291.420 Recipient Rights and Responsibilities (18, 2024-07-01), 8.291.430 Financial
  Responsibility Requirements (16, 2025-04-01); same selector and heading pattern as
  us-nm-snap-regulations.yaml.
- **us-ne** (blocked) dhhs.ne.gov/Pages/Medicaid-Regulations.aspx: TCP connect timeout 20 s plain and
  chrome120. rules.nebraska.gov (Secretary of State NAC): certificate chain repaired as described
  above, then HTTP 403 (2,174-byte body) for the site root and the agency listing, plain and chrome120.
  0 taken.
- **us-wv** (done by pointer) BFA Income Maintenance Manual landing page https://bfa.wv.gov/income-maintenance-manual
  (one combined PDF effective 2026-07-01, 2,276 page provisions at us-wv/manual/bfa/income-maintenance-manual,
  version 2026-07-21-wv-income-maintenance-manual, manifests/us-wv-manuals.yaml); the WVCHIP chapters
  are inside it (WVCHIP appears throughout the MAGI provisions). The former dhhr.wv.gov manual index
  returns 404. Nothing separate to add.
- **us-hi** (blocked) Med-QUEST administrative rules index https://medquest.hawaii.gov/en/plans-providers/har.html:
  HTTP 522 (Cloudflare origin timeout, empty body, ~20 s) plain and chrome120. 0 taken.
- **us-nh** (blocked) He-W 800 rules at the Office of Legislative Services
  https://www.gencourt.state.nh.us/rules/state_agencies/he-w800.html: HTTP 403 "Error 403" plain;
  chrome120 connection closed abruptly (curl 56). 0 taken.
- **us-me** Secretary of State APA Office page for 10-144 C.M.R. Chapter 332 MaineCare Eligibility
  Manual https://www.maine.gov/sos/cec/rules/10/ch332.htm: 6 documents (Chapter 332 docx, its
  appendices and charts docx, Chapter 333 docx, Chapters 334-336 doc). Taken 1: Chapter 332, Part 5
  Children's Health Insurance Program (CHIP, formerly CubCare), 10 sections, last updated (effective)
  2025-04-29, filing 2025-101; start after the body "PART 5" heading, stop at "PART 6". Not taken: the
  other 11 parts, the appendices, Chapters 333-336.
- **us-mt** (blocked) ARM 37.79 Healthy Montana Kids at the Secretary of State
  https://rules.mt.gov/gateway/ChapterHome.asp?Chapter=37%2E79: HTTP 200 but the site is now the
  Esper "policy-library-public" single-page app; the shell carries no rule text, its search API returns
  HTTP 403 AccessDenied to the plain client and the HTML shell to the chrome120 client, and no document
  endpoint is discoverable in the bundle. dphhs.mt.gov/hmk (HTTP 200) publishes only the member guide
  and evidence of coverage. 0 taken.
- **us-ri** Rhode Island Code of Regulations (Department of State) Title 210 Chapter 30
  https://rules.sos.ri.gov/organizations/chapter/210-30 (4 subchapters) -> Subchapter 00 Affordable
  Coverage Groups https://rules.sos.ri.gov/Organizations/SubChapter/210-30-00: 4 active parts (1, 3, 4,
  5; one family). Taken 2: 210-RICR-30-00-1 Medicaid Affordable Care Coverage Groups Overview and
  Eligibility Pathways (effective 2025-08-17, 22 pages) and 210-RICR-30-00-5 Medicaid MAGI Financial
  Eligibility Determinations and Verification (effective 2025-08-28, 20 pages), the "Download
  Regulation" PDFs from the Department of State's document store, page-level as in us-ri-snap-rules.yaml.
  Not taken: parts 3 and 4.
- **us-sd** Legislative Research Council ARSD Article 67:46 Eligibility for Medical Services, read from
  the Legislature's rules API https://sdlegislature.gov/api/Rules/67:46 (the HTML page
  sdlegislature.gov/Rules/Administrative/67:46 is script-rendered): 13 chapters (one family). Taken 2:
  Chapter 67:46:14 Nonmedicaid Children's Health Insurance Program (14 sections, latest effective
  2024-11-11) and Chapter 67:46:12 MAGI Medicaid Eligibility Standards (17 sections, 2023-07-03), one
  JSON document each (Html field), sections split on the body headings "67:46:14:NN."; the chapter's
  table-of-contents lines (no period after the number) are not sections.

## Reviewer judgments

1. **Oklahoma publisher switch.** The first probe (OHCA policy site, HTTP 200) confirmed the 29
   Subchapter 6 sections, but that site's footer says its copies are unofficial and the official OAC is
   the Secretary of State's; the scope therefore uses the Secretary of State rules API (already used by
   us-ok-snap-rules.yaml), which 403s plain clients and is read through the manifest
   browser-impersonation fallback. The chapter document's expression_date is source_as_of; each
   section's own `effectiveDate` is kept in record metadata. 62 and 62.1 yield no provision.
2. **Kentucky granularity.** One provision per regulation (whole text) because the LRC page structure
   (h2 per paragraph, text in spans) defeats section splitting without code changes; the HISTORY line is
   outside the captured container (dates are recorded in metadata).
3. **Nevada as page-level.** B-100's running page header repeats the current section label, so labeled
   sections would collide; page-level was used, and Appendix A is a chart. Both PDFs carry a watermark
   line ("MAGI MAGI ...") in their text layer.
4. **Mississippi selection and dates.** Chapters 101 and 400 plus Appendix A-3 were taken from a
   combined Medicaid/CHIP manual; chapters 102 (non-financial) and 200 (income) also apply. Appendix
   A-3's expression_date is its publisher upload month (2026-03) because the chart has no cover date.
5. **New Mexico, South Dakota, Rhode Island** take the MAGI Medicaid rules that govern
   Medicaid-expansion CHIP children (NM whole chapter 291; SD 67:46:12 alongside the separate-CHIP rule
   67:46:14; RI parts 1 and 5) rather than a CHIP-only document, which those states do not publish.
6. **Maine** takes only Part 5 of Chapter 332 under `us-me/regulation/dhhs/ofi/chapter-332/part-5`;
   the rest of the chapter (basic eligibility, MAGI budgeting) is referenced by Part 5 and not taken.
7. **Done-by-pointer to another branch's artifacts (AR).** The pointer names the parallel Medicaid
   run's scope; if that run is not merged or cut differently the row needs revisiting. WV points to an
   existing committed scope.
8. **Montana and Utah** are recorded as blocked although their sites answer HTTP 200 for a shell: the
   rule/manual text is unreachable without their JavaScript applications, and their APIs deny or
   redirect plain and impersonated clients. A reviewer may prefer a distinct status.
9. **Oregon, Nebraska (dhhs.ne.gov), Hawaii** blocks look transient (DNS SERVFAIL, connect timeout,
   origin timeout); New Hampshire, Nebraska SoS and Utah are 403s.
10. **Serving overlap.** Every new `manual` and `regulation` scope shares its
    `(jurisdiction, document_class)` pair with existing scopes (e.g. us-ok/regulation SNAP rules,
    us-nm/regulation SNAP regulations, us-me/regulation SNAP/TANF rules, us-ri/regulation SNAP rules,
    us-sd/regulation TANF manual, us-nv/manual and us-ms/manual SNAP manuals); the controller must
    include both versions in a release's membership when activating.
11. **Eight attempted, not ten.** The replacement cap (six) was reached after AR/WV (pointers), OR/NE
    (blocked) and the blocked replacements HI, NH, MT; Utah's later block could not be replaced.

Remaining (controller): `sign-ingest-manifest` per scope, immutable release selector,
`publish_corpus.py --dry-run` then publish (Supabase, R2). Not done here: push, sign, publish,
Supabase load. States still not attempted for CHIP: OR, NE, HI, NH, UT, MT (blocked this batch), the
batch-1/2 blocked rows (FL, KS, LA, WI, CA, OH, AZ, SC), and the never-queued jurisdictions AK, DC,
ND, VT, WY.
