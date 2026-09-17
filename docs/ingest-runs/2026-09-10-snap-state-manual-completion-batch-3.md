# SNAP state policy manuals, completion batch 3 (axiom-corpus#680)

Date: 2026-09-11
Program: SNAP (`manifests/state-snap-manual-agent-queue.yaml`, 51 rows, unchanged; this pass is
tracked in `manifests/snap-completion-agent-queue.yaml`, 28 rows after this batch: seven rows added,
the AZ and NY rows extended with the re-probe, the other 19 rows unchanged)
Issue: https://github.com/TheAxiomFoundation/axiom-corpus/issues/680 ("SNAP discovery missed
~24 states")
Agent: one session from a US network. started_at 2026-09-11T09:35:47Z, finished_at
2026-09-11T10:10:03Z, wall time 34m 16s. Per-state extraction seconds: none; no state in this batch had a
document to take, so `extract-official-documents` was not run and no corpus artifact was written.
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. No existing
function's behaviour was changed: the code change in
`scripts/build_snap_state_manual_completion_manifests.py` is additive (the batch-3 static rows
`STATIC_ROWS_BATCH3`, `BATCH3_NOTE`, `RUN_NOTE_BATCH3`, seven `NAMES` entries, a docstring
paragraph, and in `main()` a `--static-only` flag that skips the live builders, the batch-3 dict in
the static-row merge and the batch-3 note in the policy-notes loop). No new adapter.

## Selection rule (reviewer judgment)

Step 1: re-probe the two blocked publishers once each, one plain Axiom request and one curl-cffi
chrome120 browser-impersonation request, 20 s timeouts. AZ and NY are both still bot-challenged
(below) and stay `blocked_primary_source`.

Step 2: the issue's seven remaining discovery-gap states in its order, NC, OH, MT, OK, GA, TN, MI (TN
and MI borderline, re-checked against the publisher rather than the threshold). Per state: the
released scope's inventory and coverage under `/Users/pavelmakarchuk/axiom-corpus/data/corpus` were
read, the publisher's own index was fetched live and every document on it was inventoried by family
and compared, by URL and by section number, with the released manifest; then the released files were
compared with the publisher's current files (SHA-256 where the released inventory carries per-file
hashes, Last-Modified headers or new file names where the release is a self-contained object).
Attempted: 7; publishers probed: 9 (plus the eManuals legacy host). Extracted: 0. Index confirmed
complete, nothing to take: NC, MT, OK, GA, TN, MI (6). Blocked: OH for the eManuals manual family
(its OAC 5101:4 scope is complete), AZ, NY (3).

The result of this batch is that the issue's seven remaining states were never thin: each publishes
one manual (or one rule chapter) that the released scope already holds in full. The thin "captured"
counts in #680 are document counts (NC 79, MT 83, GA 110, MI 196, NY 18, NE 5, NV 51) or rule counts
(OH 82, OK 87, ID 70), not evidence of missing text; the issue anticipated this for TN and MI.

The same constraints as batches 1 and 2 applied: released SNAP scopes are immutable, so a missing
document would have gone into a new scope per state, version `2026-09-10-snap-state-manual-completion`,
`document_class` per the state's existing convention, manifest `manifests/us-xx-snap-manual-completion.yaml`,
citation paths under the state's existing convention, every citation path checked against every
provisions JSONL under `/Users/pavelmakarchuk/axiom-corpus/data/corpus/provisions/<jurisdiction>/`.
None was needed. Every index was the publisher's own, fetched live; no mirrors, archives, compiled lists
or PolicyEngine files. TLS verification was never disabled (no chain problem arose; `data/certs/` is
unchanged). No publisher was worked around: OK's SPA home answers HTTP 403 and its own production API
(the released scope's `download_url`) was read instead; OH's rule pages rate-limited at HTTP 429 and
the per-rule revision check was abandoned rather than retried.

A recurring finding again: revised editions of documents already in a released scope (NC 4 sections,
GA 18 items, TN 1 section, OK 1 appendix, MI 9 documents) cannot be re-taken in a completion scope
because their citation paths exist; each is recorded in the queue row for a superseding scope.

## Re-probes

**us-az** — https://dbmefaapolicy.azdes.gov/FAA5.html: plain request HTTP 403 with a 5,654-byte page
(6.7 s); impersonation HTTP 403 with a 5,995-byte F5/TSPD JavaScript bot-challenge page (2.0 s). Batch 2
had the same. No index inventory possible; no workaround.

**us-ny** — https://otda.ny.gov/programs/snap/: plain request reset
(`requests.ConnectionError: ConnectionResetError(54, 'Connection reset by peer')`, 3.2 s);
impersonation HTTP 200 carrying a 7,355-byte TSPD challenge page (`/TSPD/...` scripts, no SNAP content;
a second read 7,358 bytes). Batches 1 and 2 had a reset and a 5,609/7,562-byte challenge page. No index
inventory possible; no workaround.

## Per-jurisdiction results

| Jurisdiction | Index | Found | Taken | Provisions | Extraction seconds | Status |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| us-az | DES FAA policy manual host | - | 0 | - | - | blocked_primary_source (re-probe failed) |
| us-ny | OTDA SNAP program page | - | 0 | - | - | blocked_primary_source (re-probe failed) |
| us-nc | NCDHHS FNS Policies & Manuals | 758 | 0 | - | - | done (index complete; 4 sections revised) |
| us-oh | OAC 5101:4 on codes.ohio.gov; eManuals | 82 | 0 | - | - | blocked_primary_source (eManuals; OAC complete) |
| us-mt | DPHHS SNAP policy manual page | 90 | 0 | - | - | done (index complete; unchanged) |
| us-ok | rules.ok.gov production API, OAC 340:50 | 11 | 0 | - | - | done (index complete; D-4-C revised) |
| us-ga | DHS PAMMS SNAP Policy Manual | 369 | 0 | - | - | done (index complete; MT 87 revised 18) |
| us-tn | TDHS Publications page | 106 | 0 | - | - | done (index complete; 24.31 revised) |
| us-mi | MDHHS BEM/BAM/RFT/RFS TOCs + BPB log | 639 | 0 | - | - | done (index complete; 9 revised) |

Total: 0 documents, 0 provisions, 0 new scopes. Found/taken per family are in the queue rows
(`index_document_count`, `taken_count`, `index_families`); families are disjoint, so `found` sums to
`index_document_count`. No coverage report was produced or needed; no citation-path collision check
was needed because no citation path was proposed.

### Index inventories and diagnoses

**us-nc** — https://policies.ncdhhs.gov/divisional-n-z/social-services/food-and-nutrition-services/fns-policies-manuals/,
the released row's `primary_source_url`. The page lists each FNS manual section as a WordPress document
page (`/document/fns-NNN-<slug>/`) with an "Open" link to the PDF. 77 sections (FNS 100-175, 200-270,
300-390, 400-450, 500-515, 600, 650, 700-705, 800-865, 900-915) plus Appendix 3100 (Social Security
district offices) and Appendix 3300 (glossary): 79 documents, all 79 in `manifests/us-nc-fns-manuals.yaml`
and `us-nc/manual/2026-05-27-nc-fns-manuals-r2026-07-15-self-contained` (723 provisions, coverage
complete); no section on the index is unregistered and no registered section is off the index. Revision:
the self-contained release object keeps one synthesized source file and no per-document hashes, so the
79 released URLs were re-fetched (all HTTP 200) and their Last-Modified headers read: none is modified
after 2026-05-27 (latest 2026-02-05, FNS 227). But four sections are now served under new August 2026
file names on the index: FNS 212 Household Composition Special Arrangements (8.17.2026, Last-Modified
2026-08-31), FNS 215 Residence (8.4.2026, 2026-08-05), FNS 340 Deductions (8.4.2026, 2026-08-05), FNS 515
SR Changes During the Certification Period (8.13.2026, 2026-08-14); the old files still answer at the
released URLs. Their citation paths exist, so a superseding NC scope is needed. Families (758 found, 0
taken): manual sections 77/0 (77 in corpus, 4 revised); appendices 2/0 (2 in corpus); FNS Administrative
Letters 367/0 (document pages dated 2002-2020, the transmittal family); FNS Change Notices 312/0 (2022-2026;
FNS-CN-01 to -03-2026 carry the four revised sections as attachments, the change-summary family). #680's
79 "captured" is the document count.

**us-oh** — The released SNAP row is the OAC adapter scope `us-oh/regulation/2026-07-16-agency-5101-4`
(93 rows: 82 rules in 9 chapters plus agency, division and OAC container rows), not an official-document
manifest. https://codes.ohio.gov/ohio-administrative-code/5101%3A4 lists chapters 5101:4-1 to 5101:4-9
with 6, 7, 8, 12, 2, 16, 10, 7 and 14 rules: 82, exactly the 82 in the scope (the adapter writes
`rule-5101-4-4-03-3` for 5101:4-4-03.3 and so on); nothing on the publisher is missing and nothing in the
scope is gone. So Ohio's gap is not OAC 5101:4 and no second OAC adapter scope is built (the adapter's
shared container rows would be flagged across scopes by release validation). A per-rule revision check
was started and abandoned: codes.ohio.gov answered HTTP 429 on 61 of 82 rule pages once six were fetched
in parallel; the corpus rows carry effective dates from April 1, 2026 back to December 1, 2023 and were
not re-verified. The SNAP-governing manual family is the ODJFS eManuals Food Assistance manual, and the
host does not answer from this network: https://emanuals.jfs.ohio.gov/FoodAssistance/ (156.63.50.60)
TCP connect timeout to the plain request (`requests.ConnectTimeout`, 20.7 s) and to curl-cffi chrome120
impersonation (`curl: (28) Connection timed out after 20002 milliseconds`); the legacy host
emanuals.odjfs.state.oh.us (156.63.65.106) also times out after 20 s, as did a later request to the FACH
index path on the primary host. No inventory of the manual is possible; `blocked_primary_source` for the
manual family with the OAC finding recorded. #680's 82 "captured" is the rule count.

**us-mt** — https://dphhs.mt.gov/hcsd/Manuals/snapmanual. The page links 90 PDFs: 82 SNAP manual
sections (TOC 7.2026, alpha index, introduction, sections 100-1900 and appendices) and 8 other documents
(Commodity Supplemental Food Program, CSBG, ESG, LIHEAP and Weatherization policy manuals, the TANF State
Plan 1/2024-12/2026, a qualified sign-language interpreter list, a state privacy notice). All 82 SNAP PDFs
are in `manifests/us-mt-snap-manual.yaml` and `us-mt/manual/2026-07-17-mt-snap-policy-manual` (435
provisions, coverage complete). The released inventory carries per-file hashes: all 83 released files
were re-fetched and are byte-identical (SHA-256) to the inventory, so nothing is revised. The 83rd, SNAP
1704.1 Nutrition Education Programs, is no longer linked from the index but still answers HTTP 200 at its
released URL. Families (90 found, 0 taken): SNAP manual sections 82/0 (82 in corpus); other-program and
site PDFs 8/0. #680's 83 "captured" is the document count.

**us-ok** — https://rules.ok.gov/home (the released `source_url`) answers HTTP 403 with a 5,607-byte page
to the plain request and 5,906 bytes to impersonation, but the site's own production API, the released
scope's `download_url`, answers: `GetSegmentsByChapterNum?titleNum=340&chapterNum=50` returns 205 segments
(1 chapter, 9 subchapters, 19 parts, 162 sections, 14 appendices). 77 sections have `statusName`
Undefined (active) and all 77 are in `us-ok/regulation/2026-07-21-ok-snap-rules` (78 rows with the chapter
root; 340:50-5-7.1, 5-10.1 and 5-64.1 are held with their dots); the other 85 sections (80 Revoked, 5
Reserved) and the 14 appendices (all Revoked) carry no text and are excluded by the released extraction's
`json_record_exclude_statuses`, so the regulation scope is complete. The supporting policy scope
`us-ok/policy/2026-07-21-ok-snap-policy` (113 provisions) holds seven OKDHS appendix documents (B-2, C-1,
C-3 PDF, C-3 landing page, C-3 allotment-table data, C-3-A, D-4-C) and the Chapter 2, 10 and 65 dependency
API responses. The OKDHS policy library (oklahoma.gov/okdhs/library/policy.html) now redirects to
rules.ok.gov/home (HTTP 403), so the appendices have no reachable HTML index; each was verified document
by document against the released inventory's hashes: B-2, C-1, C-3 PDF, C-3 data and C-3-A unchanged;
D-4-C (Indian food distribution programs) a new file, Last-Modified 2026-08-28 (revised edition); the C-3
landing page differs only in the site menu (the allotment table is still "Effective 10/01/2025"; a
10012026 page answers HTTP 404); the three dependency API responses are content-identical to the released
files (733, 190 and 95 segments, same ids, statuses and text). D-4-C's citation path exists, so a
superseding OK policy scope is needed. Families (11 found, 0 taken): Chapter 50 API response 1/0; OKDHS
appendix documents 7/0 (7 in corpus, 1 revised); dependency-chapter API responses 3/0. #680's 87
"captured" is 77 sections plus policy rows.

**us-ga** — https://pamms.dhs.ga.gov/dfcs/snap/. The index links 369 distinct `dfcs/snap` URLs: 82 policy
sections (3000-3810), 14 appendix pages (Appendix A financial standards and income limits, the Appendix B
hearings set, D, E glossary, F forms TOC, J, L), 4 Appendix A BOI table PDFs (FY26, with and without
cents), 87 Manual Transmittal cover letters (MT 1-87), 181 form attachments under Appendix F (applications,
notices and verification forms, many in 16 languages) and the landing page. All 100 section and appendix
documents are in `manifests/us-ga-snap-manual.yaml` and `us-ga/manual/2026-05-27-ga-snap-manual-r2026-07-15-self-contained`
(1,214 provisions, coverage complete). Revision: Manual Transmittal 87, dated June 1, 2026 (after the
released 2026-05-27 scope), revised sections 3035, 3105, 3110, 3205, 3335, 3350, 3405, 3420, 3515, 3614,
3617, 3710, 3715, 3725, 3730 and 3805 and Appendices E and F (18 items; MT 86 of January 3, 2026 and MT 85
of November 1, 2025 predate the release). Their citation paths exist, so a superseding GA scope is needed.
Families (369 found, 0 taken): sections 82/0 (82 in corpus, 16 revised); appendix pages 14/0 (14 in
corpus, 2 revised); appendix table PDFs 4/0 (4 in corpus); MT cover letters 87/0 (the change-summary
family); form attachments 181/0 (the form family); landing 1/0. #680's 110 "captured" is the document count
plus queue rows.

**us-tn** — https://www.tn.gov/humanservices/information-and-resources/dhs-publications.html. The page
links 106 PDFs; 27 are the SNAP policy sections 24.00-24.31, all in `manifests/us-tn-snap-policies.yaml`
and `us-tn/manual/2026-05-27-tn-snap-policies-r2026-07-15-self-contained` (233 provisions, coverage
complete); the other 79 are Families First, child care, child support, Adult Protective Services and
agency publications. The "Nutrition Programs and SNAP Resources" resource-library page lists 11 customer
flyers and checklists (customer portal, ebtEDGE, reporting checklists), no policy. Revision (self-contained
release, Last-Modified headers): 26 sections are dated 2026-04-24, before the release; 24.31 Tennessee
Summer Nutrition Initiative is dated 2026-06-01, a revised edition whose citation path exists (superseding
TN scope). The TN regulation scope (Tenn. Comp. R. & Regs. 1240-01, 351 provisions) is republished by
Cornell LII (`primary_source: false`); a primary Secretary of State edition is a follow-on family, not a
SNAP-manual gap. Families (106 found, 0 taken): SNAP manual sections 27/0 (27 in corpus, 1 revised);
other TDHS publications 79/0. #680's 180 "captured" is the manual plus regulation section count; the
manual is complete, as the issue said.

**us-mi** — https://mdhhs-pres-prod.michigan.gov/OLMWeb/ex/BP/Public/BEM/000.pdf and BAM/000.pdf (the
released boundary; the released row excludes the HTML landing page because it links future-effective
documents), with RF/Public/RFT/000.pdf, RF/Public/RFS/000.pdf, BPG/GLOSSARY.pdf and BPB/LOG.pdf. The
current BEM 000 (BPB 2026-024, 8-1-2026) lists 128 chapters and BAM 000 (BPB 2026-023, 8-1-2026) 55; with
the two TOCs, all 185 are in `manifests/us-mi-bridges-manual.yaml` and `us-mi/manual/2026-07-17-mi-bridges-manual`
(2,310 provisions, coverage complete); no chapter is unregistered and none registered is gone. RFT 000
(RFB 2026-006, 5-1-2026) lists 21 reference tables, 6 in the scope (248 SSI payment levels, 250 FAP income
limits, 255 food assistance standards, 260 issuance table, 262 restaurants, 295 combined budget tables)
plus the TOC; the other 15 (zip codes, MA shelter areas, FIP/RCA/SDA payment standards, MA protected
income levels and poverty levels, CDC scale, diagnostic exam fees) are other programs' tables, as the
released row decided. RFS 000 (RFB 2026-003, 1-1-2026) lists 7 schedules, 1 in the scope (305 Bridges
transaction deadlines and issuance schedule) plus the TOC; the other 6 (SSI payroll, home help, APS, Great
Start, foster care, independent living) are other programs. The bulletin log lists 422 Bridges Policy
Bulletins (served as `BPB/<year>-<nnn>.pdf`), the change-summary family. Revision: the six August 2026
bulletins (BPB 2026-019 Bridge Card replacement fees, -020 August policy updates, -021 children's clothing
allowance, -022 RCA/RMA time period, -023 CDC case actions, -024 MiChoice waiver), all after the released
2026-07-01 TOC edition, revised BEM 106, 230B, 554 and 630, BAM 220 and 401E, both TOCs and the log: 9
revised editions whose citation paths exist (superseding MI scope); RFT 000 and RFS 000 are the released
editions. Families (639 found, 0 taken): BEM 129/0 (129 in corpus, 5 revised); BAM 56/0 (56 in corpus, 3
revised); RFT 22/0 (7 in corpus); RFS 8/0 (2 in corpus); BPG glossary 1/0 (in corpus); BPB log 1/0 (in
corpus, revised); BPB bulletins 422/0. #680's 196 "captured" is the document count; the manual is complete.

### Blocked publishers (no workaround attempted)

**us-az**, **us-ny** — see Re-probes.

**us-oh** (eManuals manual family) — see the us-oh diagnosis; `blocked_primary_source` with the exact
failures in the queue row. The OAC 5101:4 family is complete.

## Artifacts

None. No manifest `manifests/us-xx-snap-manual-completion.yaml` was written for this batch and nothing
under `/Users/pavelmakarchuk/axiom-corpus/data/corpus` changed; the batch-1 (tx, nh) and batch-2 (ky, wy,
nd) artifacts there remain unsigned and uncommitted. `data/certs/` is unchanged (both intermediates from
batches 1 and 2 remain).

Rebuild of the queue rows (no live builder runs; batch-1 and batch-2 manifests are never regenerated):

```bash
uv run python scripts/build_snap_state_manual_completion_manifests.py --static-only
```

Ruff: `uv run ruff check scripts/build_snap_state_manual_completion_manifests.py` -> all checks passed.

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 10 failed, 255 passed, 2 skipped, 4275 deselected. The 10 failures are exactly the known sparse-worktree failures (BE rulespec promotion, NY
TANF compatibility x2, BE source promotion, AK/CT/MI/MT/ND/NY SNAP manual tests), all opening `data/corpus`
artifacts this worktree does not check out; the same 10 failed on the baseline run before this batch's
edits. No test reads the completion queue or the generator.

## Reviewer judgments (all of them)

1. Re-probe rule: AZ and NY once each, one plain request and one browser-impersonation request, 20 s
   timeouts; both still bot-challenged, left blocked with the exact failure; no workaround.
2. Order: NC, OH, MT, OK, GA, TN, MI in the issue's order; all seven attempted, none replaced.
3. Diagnosis method: the published index is the publisher's own page or, where the page is a JavaScript
   app, the same-origin data the page itself loads (OK's production rules API; MI's PDF tables of
   contents, the released boundary). Completeness is judged on the index against the released
   manifest by URL and by section number; revision on SHA-256 where the released inventory has per-file
   hashes (MT, OK), otherwise on Last-Modified headers and new file names (NC, TN) or the publisher's own
   transmittal record (GA MT 87, MI BPB 2026-019 to -024).
4. Revised editions of documents already in a released scope are never re-taken in a completion scope
   (their citation paths exist and a release rejects duplicates): NC FNS 212, 215, 340, 515; GA 16
   sections and Appendices E and F (MT 87); TN 24.31; OK D-4-C; MI BEM 106, 230B, 554, 630, BAM 220, 401E,
   BEM 000, BAM 000, BPB log. Each is recorded in the queue row for a superseding scope.
5. NC: Administrative Letters (2002-2020) and Change Notices (2022-2026) are transmittal and
   change-summary families, not the manual; the four revised sections are the attachments of FNS-CN-01
   to -03-2026.
6. OH: the gap is not OAC 5101:4 (82 of 82 rules present); no second OAC adapter scope; the eManuals Food
   Assistance manual is the manual family and is blocked by a TCP connect timeout on both hosts; the
   abandoned per-rule revision check (HTTP 429) is recorded and was not retried.
7. MT: byte-identical files mean no revision; SNAP 1704.1, delisted but still served, stays in the
   released scope and is not a gap.
8. OK: revoked and reserved sections and the 14 revoked appendices (no text) are correctly excluded by the
   released extraction; the production API is the publisher's own index; the C-3 landing page's menu-only
   change is not a revision; D-4-C's new file is.
9. GA: MT cover letters are the change-summary family and Appendix F form attachments the form family;
   MT 87 of June 1, 2026 is the revision record.
10. TN: the resource-library flyers are not policy; the 79 other publications are other programs; the
    Cornell LII regulation scope is a follow-on (primary edition), not a manual gap.
11. MI: the 15 unregistered RFT tables and 6 RFS schedules are other programs' tables, as the released row
    decided; the 422 bulletins are the change-summary family; only the six August bulletins postdate the
    released edition.
12. Generator: batch 3 is static rows only, so a `--static-only` flag was added instead of abusing
    `--only` with a non-existent jurisdiction; the AZ and NY batch-2 rows are carried forward verbatim in
    the batch-3 dict with the re-probe appended (the later dict wins in the merge), so no batch-2 finding is
    lost; no manifest was written and the 19 other queue rows are byte-for-byte unchanged.
13. No corpus artifact, no coverage report and no collision check: nothing was taken, so none applied.
14. Timing measured with `date` stamps at session start and before the commit.

## Remaining from #680

Discovery-gap states not yet attempted: none. Blocked and needing another route or an official export:
NY (OTDA, TSPD challenge), AZ (DES FAA host, TSPD challenge), OH eManuals Food Assistance manual (host
does not answer). Superseding scopes needed for revised editions found in this batch: NC FNS 212, 215,
340, 515 (August 2026); GA MT 87 items (sections 3035, 3105, 3110, 3205, 3335, 3350, 3405, 3420, 3515,
3614, 3617, 3710, 3715, 3725, 3730, 3805, Appendices E and F); TN 24.31; OK Appendix D-4-C; MI BEM 106,
230B, 554, 630, BAM 220, 401E, BEM 000, BAM 000 and the BPB log; plus those from batches 1 and 2 (KY
Volumes II and IIA, NE Title 475 chapters 2 and 3, AR manual and appendices, NV six chapters, WY Table II,
ND landing/TOC/topics, ME Ch. 609). Follow-on families: NC Change Notices and Administrative Letters; GA MT
cover letters; MI Bridges Policy Bulletins; TN primary Secretary of State edition of 1240-01; plus the
batch-1 and batch-2 families (KY SNAP E&T State Plan 2026, AR SNAP E&T State Plans, WY CM Updates, NV
transmittal letters, ND pre-26.5 release PDFs, MA DTA Online Guide, NH Service Releases, OTDA ADM/INF/GIS
directives, FL quarterly Summary of Changes). Controller steps after review: `sign-ingest-manifest` for
the five batch-1 and batch-2 scopes (TX, NH, KY, WY, ND), an immutable release selector,
`publish_corpus.py --dry-run`, then publication and activation.

## Final status of every state named in #680

Status is the `queue_status` in `manifests/snap-completion-agent-queue.yaml` after this batch (28 rows:
20 done, 5 agent_ready, 3 blocked_primary_source). "Extracted" is the new completion scope's documents and
provisions, unsigned and uncommitted under `/Users/pavelmakarchuk/axiom-corpus/data/corpus`.

| State | #680 list | Batch | Final status | Finding |
| --- | --- | --- | --- | --- |
| FL | ingestion gap (68/48) | 1 | done | nothing failed to land; Summary of Changes is a separate family |
| AL | ingestion gap (59/17) | 1 | done | nothing failed to land; 42 LII rule sections in no queue |
| MD | ingestion gap (54/53) | 1 | done | nothing failed to land |
| MA | ingestion gap (54/12) | 1 | done | nothing failed to land; DTA Online Guide is a follow-on family |
| NH | discovery gap (1) | 1 | agent_ready | extracted: 502 documents, 1,006 provisions |
| KY | discovery gap (2) | 1, 2 | agent_ready | blocked in batch 1; extracted in batch 2: 1 document, 257 provisions |
| ME | discovery gap (2) | 1 | done | index complete; Ch. 609 revised |
| NE | discovery gap (5) | 2 | done | index complete; chapters 2-3 revised |
| WY | discovery gap (5) | 2 | agent_ready | extracted: 4 documents, 8 provisions |
| AZ | discovery gap (7) | 2, 3 | blocked_primary_source | DES FAA host HTTP 403 / TSPD challenge, re-probe failed |
| AR | discovery gap (8) | 2 | done | index complete; manual and appendices revised |
| TX | discovery gap (11) | 1 | agent_ready | extracted: 283 documents, 4,392 provisions |
| IA | discovery gap (12) | 2 | done | index complete; unchanged |
| CA | discovery gap (18) | 1 | done | index complete |
| NY | discovery gap (18) | 1, 2, 3 | blocked_primary_source | OTDA reset / TSPD challenge, two re-probes failed |
| HI | discovery gap (20) | 2 | done | index complete; unchanged |
| NM | discovery gap (28) | 2 | done | index complete; unchanged |
| VT | discovery gap (32) | 2 | done | index complete; unchanged |
| NV | discovery gap (51) | 2 | done | index complete; six chapters revised |
| ND | discovery gap (67) | 2 | agent_ready | extracted: 4 documents, 60 provisions |
| ID | discovery gap (70) | 2 | done | taken as the AZ replacement; index complete; unchanged |
| NC | discovery gap (79) | 3 | done | index complete; 4 sections revised |
| OH | discovery gap (82) | 3 | blocked_primary_source | OAC 5101:4 complete (82/82); eManuals host does not answer |
| MT | discovery gap (83) | 3 | done | index complete; unchanged |
| OK | discovery gap (87) | 3 | done | index complete; Appendix D-4-C revised |
| GA | discovery gap (110) | 3 | done | index complete; MT 87 revised 18 items |
| TN | borderline (180) | 3 | done | manual complete; 24.31 revised |
| MI | borderline (196) | 3 | done | manual complete; 9 documents revised |

Totals across the three batches: 28 states; 5 extracted (794 documents, 5,723 provisions in five new
unsigned scopes); 20 done with the index confirmed complete; 3 blocked.
