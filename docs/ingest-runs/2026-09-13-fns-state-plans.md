# FNS-hosted state plans: SNAP E&T state plans, WIC state plans, SNAP plans of operation (2026-09-13)

Date: 2026-09-13
Work order: `docs/coverage/needs-closure-2026-09-11/snap.md` elements `snap_s31` (SNAP E&T State
Plan, 7 CFR 273.7(c)) and `snap_s32` (State Plan of Operation, 7 CFR 272.2); `wic.md` element
`wic_s30` (WIC State Plan, 7 CFR 246.4).
Branch: `discovery/ingest-fns-state-plans` (sparse worktree
`/Users/pavelmakarchuk/axiom-corpus-worktrees/fns-state-plans` cut from `origin/main`; `data/corpus`
excluded, every extraction wrote to the main checkout's `data/corpus` with `--base`). No pull request.
Queue: `manifests/fns-state-plan-agent-queue.yaml` (51 rows, one per state and DC, three families
per row), written by `scripts/build_fns_state_plan_manifests.py`; the WIC queue rows for the eight
state-plan publishers carry a `state_plan_scope` pointer.
Agent: one session, discovery from about 2026-09-13T19:45Z, extractions 20:15:01Z to 20:20Z, this
note and the checks to 20:26Z. Impact analysis: not run; the GitNexus MCP tools were not available in
this session. No existing function was modified; the only code added is the generator.

## Result

| family | element | states attempted | scopes taken | documents | provision rows | extraction seconds |
|---|---|---:|---:|---:|---:|---:|
| SNAP E&T state plan | snap_s31 | 51 | 49 | 50 | 7,563 | 172 |
| WIC state plan | wic_s30 | 8 (the publishers the closure report names) | 8 | 352 | 2,912 | 85 |
| SNAP plan of operation (272.2) | snap_s32 | 51 (index probe) | 0 | 0 | 0 | n/a |

Every scope reports `complete: true`, 0 missing, 0 extra, 0 duplicate citations, 0 empty bodies
(checked directly in each provisions JSONL). Draft selector
`docs/ingest-runs/2026-09-13-fns-state-plans.selector.json` = the 2026-09-13 follow-up draft (556
scopes, read from the main checkout's working tree) + 57 new scopes = 613 scopes;
`validate-release --ignore-r2-missing --max-issues 50`: `ok: true`, 0 errors, 546 warnings, all
pre-existing (541 `missing_parent_id` in the released `us-ca/regulation/2026-07-13-recovery` scope
and the 5 advisory `unsectioned_document_body` warnings the consolidation note lists). Validated
after batch 1 (E&T AL-KY plus the five single-document WIC scopes, 598 scopes) and again with every
scope (613); both `ok: true`, 0 errors.

Selection rule: all 51 state agencies for the E&T plan (the closure report's 50 EXTRACTABLE rows plus
Colorado, already PRESENT); for WIC only the eight publishers the closure report recorded as posting a
state plan (MT, VT, WI, UT, WV, CT, MA, AL); for 272.2 every state's SNAP publisher index. Batches:
E&T 1 (AL, AK, AZ, AR, CA, CT, DE, DC, FL, GA, HI, ID, IL, IN, IA, KS, KY), E&T 2 (LA-NY), E&T 3
(NC-WY), WIC 4 (CT, VT, MA, WI, AL, then MT, WV, UT). Disk (`df -h /`, free): 21 GB at session start,
8.4 GB before batch 1, 9.2 GB before batch 2, 4.7 GB during batch 2 and 5.1 GB at the end; the drop is
other agents' `data/corpus` growth (9.8 GB on disk), not this run (about 250 MB of sources and rows).
The 3 GB stop threshold was never reached.

## Publisher facts a reviewer needs

**FNA (fns.usda.gov, fna.usda.gov).** The closure report's index URL `fns.usda.gov/snap/et/plans`
answers HTTP 404 on the front door and on the origin host `fns-prod.azureedge.us`; the current index
is `https://www.fna.usda.gov/snap-et/stateplan` ("SNAP E&T State Plans", 189 KB), and the Akamai front
door now answers 200 to a plain browser user agent (the 2026-09-10 WIC pass recorded 403 to every
client), so no origin-host workaround was needed. The index lists 48 entries: 46 states plus DC as FNA
pages (`/snap-et/stateplan/<state>`, each with one "Print Version" PDF at
`/sites/default/files/resource-files/<st>-snapet-stateplanFY26.pdf`), New Mexico as a link to the
state's own FFY 2025 PDF on hca.nm.gov, plus Guam and the U.S. Virgin Islands pages and a territory
page (AS, CNMI, PR) that this pass did not take (territories are another agent's lane). Arkansas,
Colorado and Texas are not listed. State pages carry "Page updated" January 28-29, 2026 (AL-IA) or
August 07, 2026 (GA, IL, IN, KS-WY). Every FNA PDF is the FNS template ("USDA FNS SNAP E&T STATE PLAN
/ STATE NAME / STATE CODE / FEDERAL FISCAL YEAR / VERSION"), text-extractable on every page (minimum
153 characters per page across the 50 files; no OCR), 56 to 386 pages. FNA posts no WIC state plans
(resource browser filtered to WIC returns none; `/wic/state-plan`, `/wic/state-plans`,
`/wic/state-agency-plans` answer 404) and no 7 CFR 272.2 plans of operation.

**Arkansas (not on the FNA index).** The DHS SNAP Employment and Training page
(humanservices.arkansas.gov, Cloudflare: 403 to the plain client and the Chrome fingerprint, 200 to
the Safari 17 fingerprint, TLS verified against certifi; `curl_cffi` needs `CURL_CA_BUNDLE` or
`SSL_CERT_FILE` pointed at certifi on this machine, error 60 otherwise) links only the E&T provider
contact list. The DHS media library (`/wp-json/wp/v2/media?search=State Plan`) lists
`StatePlan_AR_2026_Original-Submission_126.pdf` (uploaded 2026-01-20, 112 pages, the FNS template
"Arkansas AR 2026") and the superseded FFY25 plan v1.3 (2024-11-26). The FY26 original submission is
taken; the same media-library route is the one the released Arkansas SNAP manual uses.

**New Mexico.** The FNA index links `hca.nm.gov/wp-content/uploads/FFY-2025-SNAP-ET-NM-State-Plan.pdf`
(107 pages). The HCA Income Support Division "Plans and Reports" page lists the FFY 2026 E&T Final
State Plan (77 pages, FNS approved), FFY 2026 Amendment 1 (99 pages) and a FFY 2027 draft. The two
FFY 2026 documents are taken (`.../snap-et-state-plan/ffy2026` and `/amendment-1`); the FFY 2025 file
is not.

**Texas (absent).** Not on the FNA index. TWC's SNAP program page (`twc.texas.gov/programs/snap`; the
host answers an AWS WAF JavaScript challenge, HTTP 202 / 2,007 bytes, to the Chrome fingerprint and
serves the page to the Safari fingerprint) links the SNAP E&T Guide, the TPP guide, 40 TAC Chapter 813
and an HHSC report page "SNAP E&T State Plan FFY 2024" that answers HTTP 404, and nothing newer. The
HHSC site search for "SNAP E&T State Plan" returns no plan, the Reports and Presentations listing
ignores its keyword filter, and the HHSC sitemap (2,012 URLs, one page) carries no E&T plan. Texas
files a plan every year; neither FNA nor the state posts it. Recorded as `not_published` with the four
probes' status, bytes and seconds; needs outreach to TWC or HHSC.

**Colorado.** Not on the FNA index; the FFY 2026 plan is already PRESENT
(`us-co/policy/co-cdhs-snap-et-state-plan-ffy2026`, released Colorado SNAP policy scope). Recorded
as `already_in_corpus`, nothing taken.

## Method

Generator `scripts/build_fns_state_plan_manifests.py` (`--only`, `--family et|wic|operation|all`)
fetches the FNA index and every state page live, reads the state publishers' own pages for the WIC
plans, writes one manifest per state and family (`manifests/us-xx-snap-et-state-plan.yaml`,
`manifests/us-xx-wic-state-plan.yaml`) and the queue rows with every probe's URL, status, bytes,
seconds and client. Manifests follow the Colorado E&T precedent and the LIHEAP/CCDF state-plan
manifests: `document_class: policy`, `document_subtype: state_plan`, `program`, `fiscal_year`,
effective/plan period, `source_status`/`policy_status` (E&T) or `plan_status` (WIC),
`extraction_granularity: pdf_page`, `publisher_index_url`, `publisher_page_url`, `discovered_via`
and `closure_element`. Versions `2026-09-13-snap-et-state-plan` and `2026-09-13-wic-state-plan`;
`expression_date` is the plan period's first day (2025-10-01 for FFY 2026; 2024-10-01 for the WV, CT
Section 1, VT and WI FY 2025 plans; 2026-10-01 for the UT, MA and AL FFY 2027 plans, which are ahead
of `source_as_of` and are flagged for the controller below).

Citation paths: `us-xx/policy/snap-et-state-plan/ffy2026` (New Mexico adds `/amendment-1`) and
`us-xx/policy/wic-state-plan/<fy>/...` (Montana by section and functional area, West Virginia by
chapter or appendix label, Utah by section and policy title, single-document plans at the fiscal-year
node). No extraction block: the extractor's default PDF path yields one document row plus one
`page-N` row per page with text, exactly as the Colorado E&T plan (426 rows) was taken. `ocr: true`
on WV (four image-only appendices), CT (one image page) and AL (22 image pages: signatures, forms);
OCR text was spot-checked (WV indirect cost rate agreement page 1: 1,772 characters; AL page 3: the
OMB-approved FNS assurance form). Every citation path was checked against every provisions JSONL of
its jurisdiction before extraction (`grep` for `snap-et-state-plan`, `wic-state-plan`,
`state-plan-of-operation` under `data/corpus/provisions/us-*/`): the only prior matches are
Colorado's E&T plan and Connecticut's manual paths (`us-ct/manual/dph/wic/...`), neither colliding.
Deep validation confirmed no `duplicate_release_citation`.

No mirrors, archives or reposts were used; TLS verification was never disabled; no `data/certs`
change. The FNS State Options Report was not used. Colorado was read from the corpus, not re-fetched.

## Scopes


### SNAP E&T scopes

| scope | documents | provisions (rows) | page rows | empty bodies | coverage | started (UTC) | seconds |
|---|---:|---:|---:|---:|---|---|---:|
| `us-ak/policy/2026-09-13-snap-et-state-plan` | 1 | 98 | 97 | 0 | complete | 2026-09-13T20:15:07Z | 2 |
| `us-al/policy/2026-09-13-snap-et-state-plan` | 1 | 193 | 192 | 0 | complete | 2026-09-13T20:15:01Z | 6 |
| `us-ar/policy/2026-09-13-snap-et-state-plan` | 1 | 113 | 112 | 0 | complete | 2026-09-13T20:16:00Z | 2 |
| `us-az/policy/2026-09-13-snap-et-state-plan` | 1 | 131 | 130 | 0 | complete | 2026-09-13T20:15:57Z | 3 |
| `us-ca/policy/2026-09-13-snap-et-state-plan` | 1 | 287 | 286 | 0 | complete | 2026-09-13T20:16:02Z | 4 |
| `us-ct/policy/2026-09-13-snap-et-state-plan` | 1 | 97 | 96 | 0 | complete | 2026-09-13T20:16:06Z | 2 |
| `us-dc/policy/2026-09-13-snap-et-state-plan` | 1 | 180 | 179 | 0 | complete | 2026-09-13T20:16:11Z | 2 |
| `us-de/policy/2026-09-13-snap-et-state-plan` | 1 | 97 | 96 | 0 | complete | 2026-09-13T20:16:08Z | 3 |
| `us-fl/policy/2026-09-13-snap-et-state-plan` | 1 | 100 | 99 | 0 | complete | 2026-09-13T20:16:14Z | 2 |
| `us-ga/policy/2026-09-13-snap-et-state-plan` | 1 | 109 | 108 | 0 | complete | 2026-09-13T20:16:16Z | 2 |
| `us-hi/policy/2026-09-13-snap-et-state-plan` | 1 | 87 | 86 | 0 | complete | 2026-09-13T20:16:18Z | 2 |
| `us-ia/policy/2026-09-13-snap-et-state-plan` | 1 | 106 | 105 | 0 | complete | 2026-09-13T20:16:29Z | 4 |
| `us-id/policy/2026-09-13-snap-et-state-plan` | 1 | 101 | 100 | 0 | complete | 2026-09-13T20:16:20Z | 2 |
| `us-il/policy/2026-09-13-snap-et-state-plan` | 1 | 269 | 268 | 0 | complete | 2026-09-13T20:16:22Z | 3 |
| `us-in/policy/2026-09-13-snap-et-state-plan` | 1 | 128 | 127 | 0 | complete | 2026-09-13T20:16:25Z | 4 |
| `us-ks/policy/2026-09-13-snap-et-state-plan` | 1 | 72 | 71 | 0 | complete | 2026-09-13T20:16:33Z | 3 |
| `us-ky/policy/2026-09-13-snap-et-state-plan` | 1 | 143 | 142 | 0 | complete | 2026-09-13T20:16:36Z | 4 |
| `us-la/policy/2026-09-13-snap-et-state-plan` | 1 | 116 | 115 | 0 | complete | 2026-09-13T20:17:53Z | 4 |
| `us-ma/policy/2026-09-13-snap-et-state-plan` | 1 | 168 | 167 | 0 | complete | 2026-09-13T20:18:04Z | 4 |
| `us-md/policy/2026-09-13-snap-et-state-plan` | 1 | 299 | 298 | 0 | complete | 2026-09-13T20:17:59Z | 5 |
| `us-me/policy/2026-09-13-snap-et-state-plan` | 1 | 69 | 68 | 0 | complete | 2026-09-13T20:17:57Z | 2 |
| `us-mi/policy/2026-09-13-snap-et-state-plan` | 1 | 182 | 181 | 0 | complete | 2026-09-13T20:18:08Z | 4 |
| `us-mn/policy/2026-09-13-snap-et-state-plan` | 1 | 254 | 253 | 0 | complete | 2026-09-13T20:18:12Z | 5 |
| `us-mo/policy/2026-09-13-snap-et-state-plan` | 1 | 227 | 226 | 0 | complete | 2026-09-13T20:18:20Z | 5 |
| `us-ms/policy/2026-09-13-snap-et-state-plan` | 1 | 105 | 104 | 0 | complete | 2026-09-13T20:18:17Z | 3 |
| `us-mt/policy/2026-09-13-snap-et-state-plan` | 1 | 104 | 103 | 0 | complete | 2026-09-13T20:18:25Z | 3 |
| `us-nc/policy/2026-09-13-snap-et-state-plan` | 1 | 219 | 218 | 0 | complete | 2026-09-13T20:19:31Z | 5 |
| `us-nd/policy/2026-09-13-snap-et-state-plan` | 1 | 72 | 71 | 0 | complete | 2026-09-13T20:19:36Z | 2 |
| `us-ne/policy/2026-09-13-snap-et-state-plan` | 1 | 160 | 159 | 0 | complete | 2026-09-13T20:18:28Z | 3 |
| `us-nh/policy/2026-09-13-snap-et-state-plan` | 1 | 60 | 59 | 0 | complete | 2026-09-13T20:18:34Z | 2 |
| `us-nj/policy/2026-09-13-snap-et-state-plan` | 1 | 117 | 116 | 0 | complete | 2026-09-13T20:18:36Z | 3 |
| `us-nm/policy/2026-09-13-snap-et-state-plan` | 2 | 178 | 176 | 0 | complete | 2026-09-13T20:18:39Z | 1 |
| `us-nv/policy/2026-09-13-snap-et-state-plan` | 1 | 78 | 77 | 0 | complete | 2026-09-13T20:18:32Z | 3 |
| `us-ny/policy/2026-09-13-snap-et-state-plan` | 1 | 313 | 312 | 0 | complete | 2026-09-13T20:18:40Z | 7 |
| `us-oh/policy/2026-09-13-snap-et-state-plan` | 1 | 122 | 121 | 0 | complete | 2026-09-13T20:19:38Z | 3 |
| `us-ok/policy/2026-09-13-snap-et-state-plan` | 1 | 157 | 156 | 0 | complete | 2026-09-13T20:19:41Z | 4 |
| `us-or/policy/2026-09-13-snap-et-state-plan` | 1 | 379 | 378 | 0 | complete | 2026-09-13T20:19:45Z | 6 |
| `us-pa/policy/2026-09-13-snap-et-state-plan` | 1 | 387 | 386 | 0 | complete | 2026-09-13T20:19:51Z | 10 |
| `us-ri/policy/2026-09-13-snap-et-state-plan` | 1 | 90 | 89 | 0 | complete | 2026-09-13T20:20:01Z | 4 |
| `us-sc/policy/2026-09-13-snap-et-state-plan` | 1 | 126 | 125 | 0 | complete | 2026-09-13T20:20:05Z | 3 |
| `us-sd/policy/2026-09-13-snap-et-state-plan` | 1 | 85 | 84 | 0 | complete | 2026-09-13T20:20:08Z | 3 |
| `us-tn/policy/2026-09-13-snap-et-state-plan` | 1 | 109 | 108 | 0 | complete | 2026-09-13T20:20:11Z | 3 |
| `us-ut/policy/2026-09-13-snap-et-state-plan` | 1 | 57 | 56 | 0 | complete | 2026-09-13T20:20:14Z | 2 |
| `us-va/policy/2026-09-13-snap-et-state-plan` | 1 | 87 | 86 | 0 | complete | 2026-09-13T20:20:19Z | 3 |
| `us-vt/policy/2026-09-13-snap-et-state-plan` | 1 | 160 | 159 | 0 | complete | 2026-09-13T20:20:16Z | 3 |
| `us-wa/policy/2026-09-13-snap-et-state-plan` | 1 | 310 | 309 | 0 | complete | 2026-09-13T20:20:22Z | 6 |
| `us-wi/policy/2026-09-13-snap-et-state-plan` | 1 | 231 | 230 | 0 | complete | 2026-09-13T20:20:31Z | 5 |
| `us-wv/policy/2026-09-13-snap-et-state-plan` | 1 | 120 | 119 | 0 | complete | 2026-09-13T20:20:28Z | 3 |
| `us-wy/policy/2026-09-13-snap-et-state-plan` | 1 | 111 | 110 | 0 | complete | 2026-09-13T20:20:36Z | 3 |

Totals: 49 scopes, 50 documents, 7563 provision rows, 172 s extraction wall time.

### WIC scopes

| scope | documents | provisions (rows) | page rows | empty bodies | coverage | started (UTC) | seconds |
|---|---:|---:|---:|---:|---|---|---:|
| `us-al/policy/2026-09-13-wic-state-plan` | 1 | 490 | 489 | 0 | complete | 2026-09-13T20:18:00Z | 15 |
| `us-ct/policy/2026-09-13-wic-state-plan` | 2 | 106 | 104 | 0 | complete | 2026-09-13T20:17:53Z | 3 |
| `us-ma/policy/2026-09-13-wic-state-plan` | 1 | 42 | 41 | 0 | complete | 2026-09-13T20:17:57Z | 2 |
| `us-mt/policy/2026-09-13-wic-state-plan` | 112 | 450 | 338 | 0 | complete | 2026-09-13T20:19:42Z | 32 |
| `us-ut/policy/2026-09-13-wic-state-plan` | 157 | 1270 | 1113 | 0 | complete | 2026-09-13T20:20:33Z | 12 |
| `us-vt/policy/2026-09-13-wic-state-plan` | 1 | 6 | 5 | 0 | complete | 2026-09-13T20:17:56Z | 1 |
| `us-wi/policy/2026-09-13-wic-state-plan` | 2 | 43 | 41 | 0 | complete | 2026-09-13T20:17:59Z | 1 |
| `us-wv/policy/2026-09-13-wic-state-plan` | 76 | 505 | 429 | 0 | complete | 2026-09-13T20:20:14Z | 19 |

Totals: 8 scopes, 352 documents, 2912 provision rows, 85 s extraction wall time.

### Per-state E&T discovery

| state | on FNA index | FNA page updated | PDF | bytes | status |
|---|---|---|---|---:|---|
| us-ak | yes | January 28, 2026 | fna:resource-files/ak-snapet-stateplanFY26.pdf | 473906 | taken |
| us-al | yes | January 28, 2026 | fna:resource-files/al-snapet-stateplanFY26.pdf | 2830956 | taken |
| us-ar | no |  | https://humanservices.arkansas.gov/wp-content/uploads/StatePlan_AR_2026_Original-Submission_126.pdf | 249923 | taken |
| us-az | yes | January 28, 2026 | fna:resource-files/az-snapet-stateplanFY26.pdf | 1439067 | taken |
| us-ca | yes | January 28, 2026 | fna:resource-files/ca-snapet-stateplanFY26.pdf | 3438474 | taken |
| us-co | no |  |  |  | already_in_corpus |
| us-ct | yes | January 28, 2026 | fna:resource-files/ct-snapet-stateplanFY26.pdf | 1122519 | taken |
| us-dc | yes | January 28, 2026 | fna:resource-files/dc-snapet-stateplanFY26.pdf | 1927562 | taken |
| us-de | yes | January 28, 2026 | fna:resource-files/de-snapet-stateplanFY26.pdf | 1060679 | taken |
| us-fl | yes | January 28, 2026 | fna:resource-files/fl-snapet-stateplanFY26.pdf | 1109897 | taken |
| us-ga | yes | August 07, 2026 | fna:resource-files/ga-snapet-stateplanFY26.pdf | 1761639 | taken |
| us-hi | yes | January 28, 2026 | fna:resource-files/hi-snapet-stateplanFY26.pdf | 989386 | taken |
| us-ia | yes | January 29, 2026 | fna:resource-files/ia-snapet-stateplanFY26.pdf | 1405487 | taken |
| us-id | yes | January 29, 2026 | fna:resource-files/id-snapet-stateplanFY26.pdf | 1243003 | taken |
| us-il | yes | August 07, 2026 | fna:resource-files/il-snapet-stateplanFY26.pdf | 4770795 | taken |
| us-in | yes | August 07, 2026 | fna:resource-files/in-snapet-stateplanFY26.pdf | 2025387 | taken |
| us-ks | yes | August 07, 2026 | fna:resource-files/ks-snapet-stateplanFY26.pdf | 1049301 | taken |
| us-ky | yes | August 07, 2026 | fna:resource-files/ky-snapet-stateplanFY26.pdf | 2601573 | taken |
| us-la | yes | August 07, 2026 | fna:resource-files/la-snapet-stateplanFY26.pdf | 1324922 | taken |
| us-ma | yes | August 07, 2026 | fna:resource-files/ma-snapet-stateplanFY26.pdf | 2712599 | taken |
| us-md | yes | August 07, 2026 | fna:resource-files/md-snapet-stateplanFY26.pdf | 4322435 | taken |
| us-me | yes | August 07, 2026 | fna:resource-files/me-snapet-stateplanFY26.pdf | 1019764 | taken |
| us-mi | yes | August 07, 2026 | fna:resource-files/mi-snapet-stateplanFY26.pdf | 2745448 | taken |
| us-mn | yes | August 07, 2026 | fna:resource-files/mn-snapet-stateplanFY26.pdf | 3804123 | taken |
| us-mo | yes | August 07, 2026 | fna:resource-files/mo-snapet-stateplanFY26.pdf | 4172441 | taken |
| us-ms | yes | August 07, 2026 | fna:resource-files/ms-snapet-stateplanFY26.pdf | 1350689 | taken |
| us-mt | yes | August 07, 2026 | fna:resource-files/mt-snapet-stateplanFY26.pdf | 1321986 | taken |
| us-nc | yes | August 07, 2026 | fna:resource-files/nc-snapet-stateplanFY26.pdf | 3626380 | taken |
| us-nd | yes | August 07, 2026 | fna:resource-files/nd-snapet-stateplanFY26.pdf | 844167 | taken |
| us-ne | yes | August 07, 2026 | fna:resource-files/ne-snapet-stateplanFY26.pdf | 2533514 | taken |
| us-nh | yes | August 07, 2026 | fna:resource-files/nh-snapet-stateplanFY26.pdf | 730574 | taken |
| us-nj | yes | August 07, 2026 | fna:resource-files/nj-snapet-stateplanFY26.pdf | 1433546 | taken |
| us-nm | yes |  | https://www.hca.nm.gov/wp-content/uploads/StatePlan_NM_2026_Original-Submission_Approved.pdf, https://www.hca.nm.gov/wp-content/uploads/StatePlan_NM_2026_Amendment.pdf |  | taken |
| us-nv | yes | August 07, 2026 | fna:resource-files/nv-snapet-stateplanFY26.pdf | 1052299 | taken |
| us-ny | yes | August 07, 2026 | fna:resource-files/ny-snapet-stateplanFY26.pdf | 4748978 | taken |
| us-oh | yes | August 07, 2026 | fna:resource-files/oh-snapet-stateplanFY26.pdf | 1656498 | taken |
| us-ok | yes | August 07, 2026 | fna:resource-files/ok-snapet-stateplanFY26.pdf | 2166623 | taken |
| us-or | yes | August 07, 2026 | fna:resource-files/or-snapet-stateplanFY26.pdf | 4543385 | taken |
| us-pa | yes | August 07, 2026 | fna:resource-files/pa-snapet-stateplanFY26.pdf | 7013686 | taken |
| us-ri | yes | August 07, 2026 | fna:resource-files/ri-snapet-stateplanFY26.pdf | 1102810 | taken |
| us-sc | yes | August 07, 2026 | fna:resource-files/sc-snapet-stateplanFY26.pdf | 1853925 | taken |
| us-sd | yes | August 07, 2026 | fna:resource-files/sd-snapet-stateplanFY26.pdf | 1047694 | taken |
| us-tn | yes | August 07, 2026 | fna:resource-files/tn-snapet-stateplanFY26.pdf | 1325554 | taken |
| us-tx | no |  |  |  | not_published |
| us-ut | yes | August 07, 2026 | fna:resource-files/ut-snapet-stateplanFY26.pdf | 728065 | taken |
| us-va | yes | August 07, 2026 | fna:resource-files/va-snapet-stateplanFY26.pdf | 1725175 | taken |
| us-vt | yes | August 07, 2026 | fna:resource-files/vt-snapet-stateplanFY26.pdf | 1814000 | taken |
| us-wa | yes | August 07, 2026 | fna:resource-files/wa-snapet-stateplanFY26.pdf | 4959278 | taken |
| us-wi | yes | August 07, 2026 | fna:resource-files/wi-snapet-stateplanFY26.pdf | 3343694 | taken |
| us-wv | yes | August 07, 2026 | fna:resource-files/wv-snapet-stateplanFY26.pdf | 1770908 | taken |
| us-wy | yes | August 07, 2026 | fna:resource-files/wy-snapet-stateplanFY26.pdf | 1460487 | taken |


## WIC state plans per publisher

**us-mt** (112 documents taken of 113 listed; index https://dphhs.mt.gov/ecfsd/wic/wicstateplan). Montana publishes its WIC policies only as the 2026 Montana WIC State Plan page: Goals and Objectives (the FFY 2023-2027 State Nutrition and Breastfeeding Services Plan), Section II attachments by functional area (vendor, nutrition, MIS, organization and management, NSA, caseload, certification/eligibility/coordination, food delivery, monitoring, civil rights), Section III attachments and plan Attachments (forms, food list, risk codes). Every PDF is text-extractable; the clinic location map is an image and is not taken.
  - not taken (1): clinic location map, image only (no policy text): MontanaWICMap.pdf

**us-wv** (76 documents taken of 86 listed; index https://dhhr.wv.gov/WIC/policyprocedure/Pages/Default.aspx). The WV WIC Policy/Procedure index links 'West Virginia WIC State Plan FY 2025' and 'FY 2024' pages beside the eleven policy chapters (the manual, released scope). The FY 2025 page lists the plan chapters I-XI (Food Delivery, Nutrition Services, MIS, Organization and Management, NSA, Food Funds, Caseload, Certification, Monitoring, Civil Rights), the FY 2024 policy status lists and the appendices; ten 'State Plan 2025/Appendix II' files answer HTTP 404 on the publisher and are recorded, not taken. Four appendices are image-only (contact sheet, indirect cost rate agreement, data sharing agreement, authorized user report), so the scope extracts with ocr: true.
  - not taken (10): publisher answers HTTP 404: Appendix%20II%20A%20-%20FY2024%20WIC%20BFPC%20Grants.pdf; Appendix%20II%20B%20-%20WIC%20BFPC%20Line-Item%20Budget%20Wo; Appendix%20II%20C%20-%20WV%20WIC%20Shopping%20Guide.pdf; Appendix%20II%20D%20-%20Regulatory%20Requirement%20Medicaid.; Appendix%20II%20E%20-%20Food%20Package%20Guide%20.pdf; Appendix%20II%20F%20-%20Participant%20Survey%20on%20Nutritio; Appendix%20II%20G%20-%20Pacify%20Participant%20Survey%20Resp; Appendix%20II%20H%20-%20Pacify%20Participant%20Survey%20Resu; Appendix%20II%20I%20-%20WV%20WIC%20Survey%202023%20%28Respon; II_Nutrition_Services_FY2025.docx.pdf

**us-ut** (157 documents taken of 168 listed; index https://wic.utah.gov/about/wic-policies/proposed-state-plan/). The Utah WIC 'State Plan' page (wic.utah.gov/about/wic-policies/proposed-state-plan) posts the FY 2027 Utah WIC State Plan as three section pages: Section I Goals and Objectives (1 PDF), Section II Local Agency Policy and Procedure Manual (110 draft policies) and Section III State Operations (57 PDFs). Ten Section II files are the same URLs the released Utah WIC manual scope already carries and are not re-taken; the 'No policies' placeholder is skipped. Every PDF is text-extractable.
  - not taken (10): same file already in us-ut/manual/2026-09-10-wic-state-policy-manual: Definitions-12.pdf; Card-Issuance-4.pdf; Positive-Breastfeeding-Clinic-Environment-3.pdf; Monitoring-and-Evaluation-NEP-10.pdf; Forms-and-Training-Modules-6.pdf; Steps-for-Certification-16.pdf; Dual-Participation-7.pdf; Participant-Violations-14.pdf; Self-Evaluation-Tool-17.pdf; Limited-English-Proficiency-10.pdf
  - not taken (1): placeholder ('No policies'): No-policies-1.pdf

**us-ct** (2 documents taken of 2 listed; index https://portal.ct.gov/dph/wic/ct-wic-state-plan). The CT DPH 'WIC State Plan' page links Section 1 'CT State Plan for Program Operations FY 2025' (92 pages) and the FY 2026 breastfeeding peer counseling update, then the State Plan Policies series 100-400 (the manual, released scope us-ct/manual/2026-09-10-wic-state-policy-manual). The two Section 1 PDFs are taken; one page is image-only so the scope extracts with ocr: true.

**us-vt** (1 documents taken of 1 listed; index https://www.healthvermont.gov/family/wic/wic-plans-reports). Vermont posts no WIC policy manual; the WIC 'Plans & Reports' page links '2025 State Plan Goals and Objectives' (5 pages) beside data reports. That document is the only state plan text posted and is taken.

**us-ma** (1 documents taken of 1 listed; index https://www.mass.gov/info-details/massachusetts-wic-state-plan). The mass.gov 'Massachusetts WIC State Plan' page links the 'Massachusetts WIC State Plan 2027' PDF (41 pages). The WIC Program Manual it names is not published (wic-agent-queue). Taken with the Safari fingerprint.

**us-wi** (2 documents taken of 2 listed; index https://www.dhs.wisconsin.gov/wic/state-plan.htm). dhs.wisconsin.gov serves the FY 2025 state plan sections wic/certification-eligibility-coordination.pdf and wic/caseload-management.pdf (the WIC queue found them; the WIC home, Providers and Professionals pages link no manual), while the index page wic/state-plan.htm answers the publisher's own HTTP 403 page (152 KB) to every client and the site search returns nothing. The two served sections are taken; no other section is reachable.

**us-al** (1 documents taken of 1 listed; index https://www.alabamapublichealth.gov/wic/index.html). The Alabama WIC home page carries 'Public Notice - WIC State Plan of Operations' linking the full '2027 State Plan of Program Operations' PDF (489 pages: administrative documents, goals and objectives, functional area chapters I-XI). 22 pages are image-only (signatures, forms), so the scope extracts with ocr: true.


The other 43 jurisdictions were not attempted for `wic_s30`: FNA posts no WIC state plans, and the
closure report records those publishers as REVIEW (the WIC queue inventoried the manual family only)
or OUTREACH (AZ, AR, DE, IL, KS, MO, NM, NV, NH blocked or gated). Their queue rows say so
(`not_published_or_not_inventoried`); a state-plan inventory of those 43 sites is a separate pass.

## SNAP plans of operation (7 CFR 272.2): nothing posted

FNA does not post them. Every index URL of `manifests/state-snap-manual-agent-queue.yaml` and
`manifests/snap-completion-agent-queue.yaml` (51 states and DC, 60 URLs) was fetched on 2026-09-13
(plain client, then the Safari fingerprint when the plain client was refused) and its links and text
(PDF indexes extracted with PyMuPDF) searched for "plan of operation", "272.2" and "state plan". No
state posts the plan or its option attachments. Text hits are manual language only: Arkansas
(available for public review at the Central Office on request), Idaho (IDAPA 16.03.04 rule 866,
available for public examination), Mississippi (Rule 1.6 describes the annual plan), Oklahoma (OAC
340:50, available upon request), plus unrelated "state plan" mentions (Montana TANF plan, New Jersey
rehabilitation plan, Rhode Island E&T plan reference, Wyoming 272.2 citations). New Mexico's "State
Verification Plan" (the closure report's EXTRACTABLE cell) is the MAGI-based Medicaid eligibility
verification plan (Nov 2018, 14 pages), not a SNAP attachment; its cell should read ABSENT. West
Virginia's BFA "State Plans" page lists SNAP E&T, Outreach, SNAP-Ed, D-SNAP, Summer EBT, TANF, LIHEAP,
Refugee and CCDF plans and no plan of operation. Arizona's DES FAA host still answers 403; the
Nebraska and Oregon index hosts present certificate chains certifi cannot complete (recorded as
`publisher_unreachable_tls`; the closure report already inventoried Nebraska as ABSENT and Oregon as
REVIEW). This is an index probe, not the family-by-family inventory the report's ABSENT status
requires, so the 23 REVIEW cells stay REVIEW with this probe as evidence.

| state | closure status (snap_s32) | index probed | status | bytes | seconds | text hits | finding |
|---|---|---|---|---:|---:|---:|---|
| us-ak | REVIEW | `dpaweb.hss.state.ak.us/manuals/fs/fsp.htm#t=title_page_alaska_fsp_m...` | 200 | 33481 | 1.4 |  | not_published |
| us-al | ABSENT | `apps.dhr.alabama.gov/POE/POEhome` | 200 | 7591 | 0.2 |  | not_published |
| us-ar | ABSENT | `humanservices.arkansas.gov/divisions-shared-services/county-operati...` | 200 | 437405 | 0.3 |  | not_published; The SNAP Certification Manual says the plan of operation and its planning documents are available for public review at the Central Office on request; not posted. |
|  |  | `humanservices.arkansas.gov/wp-content/uploads/SNAP-Policy-Manual-04...` | 200 | 5056427 | 0.7 | 2 |  |
| us-az | OUTREACH | `dbmefaapolicy.azdes.gov/FAA5.html` | 403 | 5824 | 0.1 |  | publisher_blocked |
|  |  | `dbmefaapolicy.azdes.gov/#page/How_To_Use_This_Manual/Customer_Info....` | 403 | 5776 | 0.1 |  |  |
| us-ca | ABSENT | `www.cdss.ca.gov/inforesources/letters-regulations/legislation-and-r...` | 200 | 28761 | 1.2 |  | not_published |
|  |  | `www.cdss.ca.gov/inforesources/Rules-Regulations/Legislation-and-Reg...` | 200 | 28761 | 1.8 |  |  |
| us-co | REVIEW | `www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2818` | 200 | 88282 | 0.6 |  | not_published |
| us-ct | REVIEW | `portal.ct.gov/dss/snap/snap-policy-manual` | 200 | 59918 | 0.5 |  | not_published |
| us-dc | REVIEW | `dhs.dc.gov/publication/esa-policy-manuals` | 200 | 168806 | 0.4 |  | not_published |
| us-de | REVIEW | `regulations.delaware.gov/AdminCode/title16/9000` | 200 | 65540 | 0.2 |  | not_published |
| us-fl | ABSENT | `www.myflfamilies.com/services/public-assistance/additional-resource...` | 200 | 31823 | 0.3 |  | not_published |
| us-ga | ABSENT | `pamms.dhs.ga.gov/dfcs/snap/` | 200 | 171111 | 0.6 |  | not_published |
| us-hi | ABSENT | `humanservices.hawaii.gov/admin-rules-2/admin-rules-for-programs/` | 200 | 97620 | 0.4 |  | not_published |
| us-ia | ABSENT | `hhs.iowa.gov/media/4035/download?inline` | 200 | 101577 | 0.6 |  | not_published |
| us-id | ABSENT | `adminrules.idaho.gov/current-rules/` | 200 | 196769 | 1.4 |  | not_published; IDAPA 16.03.04 rule 866 says state plans of operation are available for public examination; not posted. |
|  |  | `adminrules.idaho.gov/rules/current/16/160304.pdf` | 200 | 1246593 | 1.4 | 2 |  |
| us-il | REVIEW | `www.dhs.state.il.us/page.aspx?item=13473` | 200 | 10727 | 0.2 |  | not_published |
| us-in | REVIEW | `www.in.gov/fssa/dfr/forms-documents-and-tools/policy-manual/` | 200 | 85550 | 0.4 |  | not_published |
| us-ks | REVIEW | `content.dcf.ks.gov/EES/KEESM/Current/Home.htm` | 200 | 4446 | 0.4 |  | not_published |
| us-ky | ABSENT | `www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx` | 200 | 58132 | 1.6 |  | not_published |
| us-la | REVIEW | `public.powerdms.com/LADCFS/tree/documents/398463` | 200 | 2404 | 0.3 |  | not_published |
| us-ma | ABSENT | `www.mass.gov/lists/department-of-transitional-assistance-regulations` | 200 | 209572 | 0.5 |  | not_published |
| us-md | ABSENT | `dhs.maryland.gov/supplemental-nutrition-assistance-program/food-sup...` | 200 | 105282 | 0.8 |  | not_published |
| us-me | ABSENT | `www.maine.gov/sos/rulemaking/agency-rules/department-health-and-hum...` | 200 | 136019 | 0.1 |  | not_published |
| us-mi | ABSENT | `mdhhs-pres-prod.michigan.gov/OLMWeb/ex/BP/Public/BEM/000.pdf` | 200 | 167226 | 0.3 |  | not_published |
| us-mn | REVIEW | `www.dhs.state.mn.us/main/groups/county_access/documents/pub/dhs-327...` | 200 | 6389130 | 7.1 | 1 | not_published |
| us-mo | REVIEW | `dssmanuals.mo.gov/food-stamps/` | 200 | 46509 | 0.6 |  | not_published |
| us-ms | REVIEW | `www.sos.ms.gov/adminsearch/ACCode/00000331c.pdf` | 200 | 1635091 | 0.8 | 10 | not_published; MDHS SNAP manual Rule 1.6 describes the annual state plan of operation (7 CFR 272.2); the plan itself is not posted. |
| us-mt | ABSENT | `dphhs.mt.gov/hcsd/Manuals/snapmanual` | 200 | 72828 | 0.4 | 1 | not_published |
| us-nc | ABSENT | `policies.ncdhhs.gov/divisional-n-z/social-services/food-and-nutriti...` | 200 | 333424 | 1.1 |  | not_published |
| us-nd | ABSENT | `www.nd.gov/dhs/policymanuals/SNAP/Content/Home%202.htm` | 200 | 29054 | 0.3 |  | not_published |
| us-ne | ABSENT | `rules.nebraska.gov/rules?agencyId=37&titleId=230` | unreachable: SSLError: certificate chain not verifiable with certifi |  | 0.2 |  | publisher_unreachable_tls |
| us-nh | ABSENT | `www.dhhs.nh.gov/fsm_htm/newfsm.htm` | 200 | 5781 | 0.3 |  | not_published |
|  |  | `gc.nh.gov/rules/state_agencies/he-w700.html` | 200 | 569579 | 0.4 |  |  |
| us-nj | REVIEW | `www.nj.gov/humanservices/notices/rules-and-fees/rules-and-regulations/` | 200 | 74542 | 0.1 | 1 | not_published |
| us-nm | EXTRACTABLE | `www.hca.nm.gov/lookingforinformation/income-support-division-1/` | 200 | 246816 | 1.8 | 4 | not_published; The HCA Income Support Division page's 'State Verification Plan' (new-mexico-verification-plan-template-final-nov-2018-pw.pdf, 14 pages) is the MAGI-based Medicaid eligibility verification plan, not a SNAP 272.2 attachment; the closure report's EXTRACTABLE note is corrected here. The ISD Plans and Reports page lists E&T, Outreach, SNAP-Ed and D-SNAP plans, no plan of operation. |
| us-nv | ABSENT | `dwss.nv.gov/Home/Features/eligibility/eligibility-n-payment-info-ma...` | 200 | 90997 | 1.3 | 1 | not_published |
| us-ny | OUTREACH | `otda.ny.gov/programs/snap/` | 200 | 6620 | 0.2 |  | not_published |
|  |  | `otda.ny.gov/programs/snap/SNAPSB.pdf` | 200 | 6620 | 0.1 |  |  |
| us-oh | OUTREACH | `codes.ohio.gov/ohio-administrative-code/5101%3A4` | 200 | 14653 | 0.7 |  | not_published |
| us-ok | ABSENT | `prod-ok-rules-api.tecuity.com/GetSegmentsByChapterNum?titleNum=340&...` | 200 | 730010 | 2.0 | 3 | not_published; OAC 340:50 says State Plans of Operation are available upon request for inspection; not posted. |
|  |  | `rules.ok.gov/home` | 200 | 1551 | 0.5 |  |  |
| us-or | REVIEW | `sharedsystems.dhsoha.state.or.us/DHSForms/Served/de2818.pdf` | unreachable: SSLError: certificate chain not verifiable with certifi |  | 0.5 |  | publisher_unreachable_tls |
| us-pa | REVIEW | `services.dpw.state.pa.us/oimpolicymanuals/snap/index.htm#t=SNAP_Han...` | 200 | 33577 | 0.3 |  | not_published |
| us-ri | REVIEW | `rules.sos.ri.gov/regulations/part/218-20-00-1` | 200 | 1124513 | 0.4 | 2 | not_published |
| us-sc | REVIEW | `dss.sc.gov/about/data-and-resources/manuals/` | 200 | 76706 | 0.2 |  | not_published |
| us-sd | REVIEW | `dss.sd.gov/docs/economicassistance/snap/snapmanual.pdf` | 200 | 2773728 | 13.7 |  | not_published |
| us-tn | ABSENT | `www.tn.gov/humanservices/information-and-resources/dhs-publications...` | 200 | 94260 | 0.3 |  | not_published |
| us-tx | ABSENT | `fhb.hhs.texas.gov/handbooks/texas-works-handbook` | 200 | 30202 | 0.9 |  | not_published |
|  |  | `www.hhs.texas.gov/handbooks/texas-works-handbook` | 200 | 30202 | 0.3 |  |  |
| us-ut | REVIEW | `jobs.utah.gov/infosource/eligibilitymanual/eligibility_manual.htm` | 200 | 33544 | 1.0 |  | not_published |
| us-va | REVIEW | `www.dss.virginia.gov/relief/food-assistance/snap/snap-policy--proce...` | 200 | 46411 | 0.2 |  | not_published |
| us-vt | ABSENT | `www.ahsnet.ahs.state.vt.us/Public/3sVT/whxdata/toc.new.js` | 200 | 2863 | 0.3 |  | not_published |
|  |  | `www.ahsnet.ahs.state.vt.us/Public/3sVT/assets/BRM/100GenInfo.htm` | 200 | 23918 | 0.2 |  |  |
| us-wa | REVIEW | `www.dshs.wa.gov/esa/manuals/eaz` | 200 | 88777 | 0.9 |  | not_published |
| us-wi | REVIEW | `www.emhandbooks.wisconsin.gov/fsh/fsh.htm#t=home.htm` | 200 | 31704 | 0.3 |  | not_published |
| us-wv | REVIEW | `bfa.wv.gov/income-maintenance-manual` | 200 | 42526 | 0.1 | 1 | not_published; bfa.wv.gov/bfa-policy-and-plans/state-plans lists SNAP E&T, SNAP Outreach, SNAP-Ed, D-SNAP, Summer EBT, TANF, LIHEAP, Refugee and CCDF plans; no 7 CFR 272.2 plan of operation. |
| us-wy | ABSENT | `dfs.wyo.gov/about/policy-manuals/snap-and-power-policy-manual/` | 200 | 946427 | 1.6 | 2 | not_published |

## Closure cells

- `snap_s31`: 49 EXTRACTABLE cells become PRESENT once the scopes are selected (every state and DC
  except Colorado, already PRESENT, and Texas, which stays EXTRACTABLE-by-existence but is
  `not_published` on every reachable publisher page). The `snap-matrix.csv` evidence for the 49 rows
  is `us-xx/policy/2026-09-13-snap-et-state-plan`, citation path
  `us-xx/policy/snap-et-state-plan/ffy2026`.
- `wic_s30`: 8 EXTRACTABLE cells (MT, VT, WI, UT, WV, CT, MA, AL) become PRESENT; 43 stay REVIEW or
  OUTREACH.
- `snap_s32`: 0 closed. NM EXTRACTABLE should be corrected to ABSENT (the attachment is a Medicaid
  document). The other 50 cells keep their status; the queue records what was checked.

## Checks

`uv run ruff check scripts`: all checks passed. Focused tests from the worktree,
`uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`:
286 passed, 2 skipped, 12 failed, 4,531 deselected in 54 s. The 12 failures are the known
`data/corpus`-dependent set that only reproduces in a sparse worktree (they open other scopes'
retained artifacts): the BE rulespec promotion and BE source promotion tests, the two NY TANF
compatibility tests, the AK, CT, MI, MT, ND and NY SNAP manual tests, plus the Armenia ARLIS and
Israel OpenLaw manifest-continuity tests of the same shape:

- `tests/test_armenia_arlis.py::test_checked_in_tax_code_2024_continuity_sources_match_manifest`
- `tests/test_be_rulespec_2026_08_23_promotion.py::test_be_rulespec_2026_08_23_ingest_manifest_covers_every_artifact`
- `tests/test_build_ny_tanf_compatibility_scope.py::test_rejects_duplicate_manifest_attestation`
- `tests/test_build_ny_tanf_compatibility_scope.py::test_rejects_manifested_artifact_hash_mismatch`
- `tests/test_israel_openlaw.py::test_pilot_manifest_pins_all_three_instruments`
- `tests/test_rulespec_be_source_promotion.py::test_rulespec_be_source_snapshots_and_signed_manifests_are_complete`
- `tests/test_us_ak_snap_manual.py::test_alaska_snap_manifest_matches_retained_robohelp_toc`
- `tests/test_us_ct_snap_manual.py::test_connecticut_snap_manifest_matches_retained_official_toc`
- `tests/test_us_mi_snap_manual.py::test_michigan_manifest_matches_retained_official_manual_tocs`
- `tests/test_us_mt_snap_manual.py::test_montana_current_toc_covers_every_manifest_section`
- `tests/test_us_nd_snap_manual.py::test_north_dakota_manifest_matches_the_live_release_boundary`
- `tests/test_us_ny_snap_manuals.py::test_new_york_retained_pdfs_and_generated_rows_match_manifest`

Note: plain `uv run pytest` in a fresh worktree resolves to the Anaconda `pytest` on PATH (243
collection errors, `No module named 'axiom_corpus'`); the `--extra dev` form is the one that works.

## Controller section

Selector additions (57 scopes, all `document_class: policy`; the draft selector already
carries them on top of the 2026-09-13 follow-up draft):

- `2026-09-13-snap-et-state-plan` for: us-ak, us-al, us-ar, us-az, us-ca, us-ct, us-dc, us-de, us-fl, us-ga, us-hi, us-ia, us-id, us-il, us-in, us-ks, us-ky, us-la, us-ma, us-md, us-me, us-mi, us-mn, us-mo, us-ms, us-mt, us-nc, us-nd, us-ne, us-nh, us-nj, us-nm, us-nv, us-ny, us-oh, us-ok, us-or, us-pa, us-ri, us-sc, us-sd, us-tn, us-ut, us-va, us-vt, us-wa, us-wi, us-wv, us-wy
- `2026-09-13-wic-state-plan` for: us-al, us-ct, us-ma, us-mt, us-ut, us-vt, us-wi, us-wv

Decisions needed:

1. Texas E&T plan: outreach to TWC or HHSC for the FFY 2026 plan (TWC's link to the HHSC FFY 2024
   report page is dead). Nothing to select.
2. FFY 2027 plans (UT proposed, MA, AL) carry `expression_date: 2026-10-01`, after `source_as_of`.
   If the controller prefers the posting date for not-yet-effective plans, change the three manifests'
   `expression_date` to `2026-09-13` and re-extract (three small scopes); the validator accepts
   either.
3. Utah FY 2027 Section II is next year's draft of the local agency policy manual: 100 drafts are
   taken under the state-plan family and the 10 whose URL the released Utah manual scope already
   carries are not. If the manual family should own those drafts instead, drop Section II from
   `manifests/us-ut-wic-state-plan.yaml` and re-extract.
4. New Mexico E&T: two documents (FY26 original submission and Amendment 1) in one scope; keep both or
   select the amendment only.
5. West Virginia WIC FY 2025: ten Appendix II links answer 404 on the publisher and are recorded in
   the queue; nothing to do unless the publisher restores them.
6. The Guam, USVI and territory E&T plans on the FNA index were left to the territories lane.
7. `snap_s32` for New Mexico should be re-scored ABSENT in the next closure run.

Artifacts for the 57 scopes are under `/Users/pavelmakarchuk/axiom-corpus/data/corpus` only
(uncommitted, unsigned); `scripts/sign_release_scopes.sh` on the release branch commits and signs them
when the controller cuts the successor selector.
