# CCDF FFY 2025-2027 state and territory plans (ACF-118): retry pass

Date: 2026-09-10
Program: CCDF (board Year 1 list; `manifests/ccdf-agent-queue.yaml`)
Branch: `discovery/ingest-ccdf`
First run: `docs/ingest-runs/2026-09-10-ccdf-state-plans-fy2025-2027.md` (25 extracted, 25 blocked, 6 needs_review).

Timing: started_at 2026-09-10T18:33:57Z, finished_at 2026-09-10T18:51:53Z, agent wall time
17 min 56 s (1076 s). Retry probes 2026-09-10T18:36:21Z to 18:36:56Z (25 hosts, threaded). Extraction pass
2026-09-10T18:46:54Z to 18:47:17Z (21 s for 3 jurisdictions; per-jurisdiction seconds below).

## Selection

Same scope and conventions as the first run: the FFY 2025-2027 ACF-118 plan posted by each Lead Agency and
reached through the ACF directory https://acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027; document_class
`policy`; version `2026-09-10-ccdf-plan-fy2025-2027`; citation path `us-xx/policy/acf/ccdf-plan/fy2025-2027`;
41 second-level subsections plus the document root (42 provisions per plan); `--source-as-of 2026-09-10`,
`--expression-date 2024-10-01`. No new jurisdictions. Work order: (1) retry the 25 `blocked_primary_source` rows
once, (2) re-check the six `needs_review` rows on the publisher's own site, (3) fix the 56 ruff C408 findings in
`scripts/build_ccdf_state_plan_manifests.py`.

## Per-host retry (work order item 1)

Method: one plain `requests` GET with a browser User-Agent (connect 15 s, read 30 s) and one `curl_cffi`
`impersonate="chrome"` GET (30 s) per host, run at 2026-09-10T18:36Z with `REQUESTS_CA_BUNDLE` = certifi +
the Arkansas Sectigo intermediate. Nothing was worked around: no proxies, mirrors, archived copies, or
disabled verification. Every row note now ends with "retried 2026-09-10T18:36Z, same failure" except MN.

| Row | URL probed | Plain requests | curl_cffi chrome | Outcome |
| --- | --- | --- | --- | --- |
| AK | aws.state.ak.us OnlinePublicNotices View.aspx?id=215530 | ConnectTimeout (16 s) | curl 28 timeout (30 s) | same failure |
| AS | www.dhss.as/index.html | SSLError (self-signed, expired CN=cmaster70) | curl 60 unable to get local issuer | same failure |
| AZ | des.az.gov .../child-care-and-development-fund-state-plan | 403 cloudflare challenge | 403 cloudflare challenge | same failure |
| CO | cdec.colorado.gov/resources/state-plans | 403 CloudFront | 403 CloudFront | same failure |
| CT | www.ctoec.org/ccdf/ | 403 cloudflare challenge | 403 cloudflare challenge | same failure |
| GA | www.decal.ga.gov/BftS/CCDFPlan.aspx | connection reset by peer | curl 56 reset by peer | same failure |
| ID | publicdocuments.dhw.idaho.gov WebLink DocView id=32013 | ConnectTimeout (16 s) | curl 28 timeout (30 s) | same failure |
| KS | www.dcf.ks.gov .../Child-care-and-early-education.aspx | ConnectTimeout (18 s) | curl 28 timeout (30 s) | same failure |
| KY | www.chfs.ky.gov/agencies/dcbs/dcc/Pages/default.aspx | 403 | 403 | same failure |
| LA | louisianabelieves.com -> doe.louisiana.gov early-childhood-policy-guidance | 403 cloudflare captcha | 403 cloudflare captcha | same failure |
| MD | earlychildhood.marylandpublicschools.org/2025-2027-ccdf-plan | 403 (cloudflare, 107 KB access-denied page) | 403 | same failure |
| MN | mn.gov/dhs .../child-care-development-fund/ | 200 redirected to validate.perfdrive.com challenge | 200 mn.gov page: only a `<meta http-equiv="refresh">` to https://dcyf.mn.gov/child-care-and-development-fund | new host, still blocked (below) |
| MO | dese.mo.gov/media/pdf/acf-118-ccdf-ffy-2025-2027-missouri | 200 text/html Drupal antibot form (53 KB) | 200 same antibot form | same failure |
| MP | www.childcare.gov.mp/ | 403 nginx | 403 nginx | same failure |
| NE | dhhs.ne.gov/Pages/Child-Care-and-Development-Fund-Plan.aspx | ConnectTimeout (15 s) | curl 28 timeout (30 s) | same failure |
| NJ | childcarenj.gov .../CCDF_State_Plan_for_New_Jersey_FFY25-27.pdf | 403 cloudflare challenge | 403 cloudflare challenge | same failure |
| NY | ocfs.ny.gov/main/childcare/stateplan/ | 200 F5/Shape TSPD challenge page (5.5 KB) | 200 same challenge page | same failure |
| OR | www.oregon.gov/delc/about-us/pages/state-plans.aspx | NameResolutionError | curl 6 could not resolve host | same failure |
| RI | dhs.ri.gov/regulations/state-plans | 403 cloudflare captcha | 403 cloudflare captcha | same failure |
| SC | www.scchildcare.org/resources/ | ConnectTimeout (15 s) | curl 28 timeout (30 s) | same failure |
| TN | www.tn.gov/humanservices/.../tdhs-reports-and-information.html | 403 awselb | 403 awselb | same failure |
| TX | www.twc.texas.gov/programs/child-care/data-reports-plans | 403 CloudFront | 403 CloudFront | same failure |
| UT | jobs.utah.gov/occ/plans.html | 403 awselb | 403 awselb | same failure |
| VT | outside.vermont.gov .../CCDF-Plan-2025-2027-Approved.pdf | 403 volt-adc "requested URL was rejected" | 403 same | same failure |
| VA | www.childcare.virginia.gov .../virginia-child-care-plan | 403 AkamaiGHost access denied | 403 AkamaiGHost | same failure |

Minnesota: the Lead Agency moved from DHS to the Department of Children, Youth, and Families; the mn.gov page
the ACF index links is now a meta-refresh to https://dcyf.mn.gov/child-care-and-development-fund. That host
redirects plain requests to the Radware `validate.perfdrive.com` bot challenge, and answers `curl_cffi`
chrome and safari17_0 impersonation with a certificate chain that fails verification (curl 60 "self signed
certificate in certificate chain"), while `openssl s_client` on the same host sees a valid Sectigo EV chain
(leaf dcyf.mn.gov <- Sectigo Public Server Authentication CA EV R36 <- Root R46, verify return 0). The plan
page was never served; verification was not disabled. The row stays `blocked_primary_source`;
`publisher_index_url` now records the dcyf.mn.gov page.

Hosts retried: 25. Hosts that now answer with content: 0 (mn.gov answers impersonation but only with a
redirect to a blocked host). Newly extracted from the retry: none. Time spent on the still-failing hosts:
about 6 minutes (threaded probes plus the Minnesota follow-up), within the 20-minute cap. The first run's
reading of the pattern (consistent with geo-restriction of the agent's network) is unchanged and remains an
inference.

## needs_review rows (work order item 2)

Each publisher's own site was checked (site navigation and, for MS and VI, the site's own search); no third
parties.

| Row | Found on the publisher's site | Outcome |
| --- | --- | --- |
| IN | Same carefinder page, same 11 documents; the plan PDF is the same certified 2024-06-30 submission (7,742,708 bytes, Last-Modified 2026-06-19, 399 pages, Word export with attached state rules); 1 of 41 labels after the Overview start. Approved print not posted. | needs_review (non-conforming document only) |
| ME | OCFS "Child Care Affordability Information & Resources" page (reached from the OCFS home page nav "CCAP & CCDF Information") posts "Maine State Plan CCDF FFY 2025-2027 for Maine" (CARS print, Certified as of 2024-09-12, 301 pages), Amendments #1-#4, the Appendix, public comments and the Notice of Compliance. | taken: Initial Plan (certified), extracted |
| MS | ECCD "Child Care Reports & Archives" page (home page nav) posts "2025 - 2027 CCDF Triennial State Plan"; the /document/ landing URL 302s to `wp-content/uploads/2025/01/ACF-118-CCDF-FFY-2025-2027-For-Mississippi.pdf` (CARS print, Approved as of 2024-11-09, 219 pages). The "State Plans" page still lists only 2022-2024. | taken: Initial Plan (approved), extracted |
| PA | DHS "Early Learning & Child Care" resources page posts "2025-2027 Pennsylvania State Plan for Child Care Development Block Grant Report (CCDBG)" = `2025-2027-ocdel-ccdf-state-plan.pdf` (CARS print, Approved as of 2024-11-09, 219 pages). The ACF index link still redirects to the generic DHS agency page; the "CCDF Executive Summary" page carries no plan link. | taken: Initial Plan (approved), extracted |
| PR | acuden.pr.gov/documentos unchanged: "Borrador Plan Estatal Child Care 2025-2027" (draft), hearing notice, "Fee Scale State Plan 2025-2027", emergency plan and studies. No approved or certified plan. | needs_review (draft only) |
| VI | dhs.vi.gov home page: "CCDF State Plan Preprint FFY 2019-2021 Draft"; Office of Child Care & Regulatory Services page: "VI CCDF State Plan 2022-2024" (submitted 2021-09-17), policy memoranda, 2022 market rate survey, ACF-218 QPR FFY2022; site search "CCDF 2025" returns nothing. | needs_review (no FFY 2025-2027 document); publisher_index_url now the OCCRS page |

## Extraction

Same `CARS_EXTRACTION` pattern as the first run (labeled_sections, `^Overview$` start, page header/footer
drop, 2.4 heading continuation); all three PDFs are Aspose.Words CARS prints in which the pattern matched 41/41
labels with no repeats before extraction was run.

| Jurisdiction | Version taken | Pages | Source bytes | Seconds | Provisions | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| us-me | Initial Plan, Certified as of 2024-09-12 | 301 | 3,168,735 | 8 | 42 | complete, 0 missing, 0 extra, 0 duplicate |
| us-ms | Initial Plan, Approved as of 2024-11-09 | 219 | 2,910,081 | 7 | 42 | complete, 0 missing, 0 extra, 0 duplicate |
| us-pa | Initial Plan, Approved as of 2024-11-09 | 219 | 2,935,038 | 6 | 42 | complete, 0 missing, 0 extra, 0 duplicate |

Independent check over all 28 scopes (25 first-run + 3): coverage `complete: true`, 42 provisions each,
42 unique `citation_path` values per JSONL (checked directly), inventory SHA-256 equals the stored source
file, smallest section body 1,014 characters. Total 1,176 provisions (28 x 42).

## Index inventories for the newly taken rows

ACF index rows (unchanged): ME, MS and PA each have 2 documents on the ACF index (plan link to the Lead
Agency page + ACF-hosted Appendix); this run takes 1 (the plan), Appendix family not taken. Publisher pages:

Maine, https://www.maine.gov/dhhs/ocfs/provider-resources/child-care-subsidy-information-for-providers:
62 document links.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027: initial (certified) plan, Amendments #1-#4, Appendix, public comment and responses, Notice of Compliance | 8 | 1 (initial plan) |
| CCDF plan FFY 2022-2024: plan, Amendments #1-#5, public comment and responses | 7 | 0 |
| Older CCDF plans (2019-2021, 2016-2018, 2014-2015 x2, 2012-2013 x3, 2010-2011) | 8 | 0 |
| ACF-218 Quality Progress Report FFY 2024 | 1 | 0 |
| Emergency planning (DHHS Child Care Emergency Plan, YIKES guide and response plan) | 3 | 0 |
| Cost modeling and rate setting report | 1 | 0 |
| Market rate survey reports (2018, 2021, 2024) and market rate sheets (2018, 2021, 2024, 2025) | 7 | 0 |
| CCAP rules, income guidelines, memos, notices, forms and provider agreements | 18 | 0 |
| Billing schedules and instructions | 3 | 0 |
| Baxter system guides (webinar, MFA setup, MFA FAQ, uploads, training manual, portal FAQ) | 6 | 0 |

Mississippi, https://www.mdhs.ms.gov/eccd/reports-archives/: 13 document links, 12 distinct documents
(the 2025-2027 Appendix is linked twice: landing page and direct PDF).

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plans (2025-2027 Triennial State Plan, FFY 2022-2024, FFY 2019-2021) | 3 | 1 (2025-2027) |
| CCDF plan Appendix 2025-2027 (state-hosted copy of the ACF-118 Appendix) | 1 | 0 |
| Agency policy manuals (DECCD Child Policy Manual 2021, 2023; CCPP Policy Manual 2026) | 3 | 0 |
| Market rate surveys (2021, 2024) and Narrow Cost Analysis Report 2024 | 3 | 0 |
| Quality Progress Report 2024 | 1 | 0 |
| DECCD Emergency Plan | 1 | 0 |

Pennsylvania, https://www.pa.gov/agencies/dhs/resources/early-learning-child-care: 5 document links in the
page body (4 on pa.gov, 1 on a constantcontact.com host); site-wide navigation links to the CHIP and
Medicaid state plans not counted.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027 ("2025-2027 Pennsylvania State Plan for CCDBG Report") | 1 | 1 |
| 2025 Child Care Market Rate Survey report and summary report | 2 | 0 |
| Provider notices (Bureau of Certification regional office list, text messaging terms) | 2 | 0 |

## Lint (work order item 3)

`uv run ruff check --unsafe-fixes --fix scripts/build_ccdf_state_plan_manifests.py` rewrote the 56 `dict(...)`
calls in the module-level `RESOLUTIONS` constant as literals (C408). Before any other edit the generator was
re-run and every committed manifest and the queue file were byte-identical, so the fix is behaviour-neutral.
`uv run ruff check scripts/build_ccdf_state_plan_manifests.py` passes. `uv run ruff check scripts/` still
reports 8 pre-existing findings in other scripts (`draft_program_work_orders.py`: E401, E701, E702 x3, F401,
I001; `build_liheap_state_plan_manifests.py`: F401); those files were not touched.

## Reviewer judgments

1. Maine version: the certified initial plan (Certified as of 2024-09-12) was taken, following the first
   run's NH/SD/WA convention for states that post the certified submission rather than an approval print.
   Amendments #1-#4 (the latest dated 2026-06-26), the Appendix, public comments and the Notice of
   Compliance are inventoried and not taken. A reviewer may prefer the Amendment 4 consolidated plan.
2. Mississippi source: the plan is not on the "State Plans" page the ACF index links but on the ECCD
   "Child Care Reports & Archives" page; `source_url` is the PDF that the `/document/` landing URL redirects
   to, and `publisher_index_url` is the archive page. The state-hosted Appendix copy is not taken.
3. Pennsylvania source: found on the DHS "Early Learning & Child Care" resources page after the ACF index
   link redirected to the generic agency page; the page label reads "CCDBG Report" but the file is the CARS
   ACF-118 print with Plan Status "Approved as of 2024-11-09".
4. Minnesota: `publisher_index_url` moved to the dcyf.mn.gov page because the mn.gov page is now only a
   meta-refresh. The impersonation-only TLS chain failure on dcyf.mn.gov was not bypassed; the row stays
   blocked with the exact failure recorded.
5. The 24 other blocked hosts were probed once each (plain + impersonation, 30 s) and failed with the same
   class of error; "retried 2026-09-10T18:36Z, same failure" is appended verbatim to each row note.
   Geo-restriction remains the agent's inference, not an observed fact.
6. IN, PR, VI stay `needs_review` with the retry findings appended; VI's `publisher_index_url` now points at
   the Office of Child Care & Regulatory Services page, which is where the CCDF documents actually sit.
7. Queue row notes for ME, MS and PA are produced by the generator's shared template ("located on the Lead
   Agency page linked from the ACF index"); the `plan_status` text inside each note records that the plan
   was located elsewhere on the publisher's site. The template was not changed because that would rewrite
   the 25 first-run rows.
8. Queue row fields keep the first run's schema: `index_url`/`index_document_count` describe the ACF index
   row (2 documents), `taken_count` 1; the publisher-page inventories by family are recorded in this note
   rather than as a new per-row `index_families` field.
9. `IN_MANUAL_NOTE` now says "25 jurisdictions blocked, 3 needs_review after the 2026-09-10 retry"; the
   Indiana CCDF Policy Manual row stays `needs_review` because the plan family is still incomplete.
10. GitNexus MCP tools were unavailable in this session, so no impact analysis was run. No existing function
    was modified: the diff to `scripts/build_ccdf_state_plan_manifests.py` touches the module docstring, the
    `RESOLUTIONS` and `IN_MANUAL_NOTE` constants, and the ruff literal rewrite inside `RESOLUTIONS`.

## Artifacts (unsigned, uncommitted, shared corpus root of the main checkout)

For `us-me`, `us-ms`, `us-pa`:

- `data/corpus/sources/us-xx/policy/2026-09-10-ccdf-plan-fy2025-2027/official-documents/us-xx-acf-ccdf-plan-fy2025-2027.pdf`
- `data/corpus/inventory/us-xx/policy/2026-09-10-ccdf-plan-fy2025-2027.json`
- `data/corpus/provisions/us-xx/policy/2026-09-10-ccdf-plan-fy2025-2027.jsonl`
- `data/corpus/coverage/us-xx/policy/2026-09-10-ccdf-plan-fy2025-2027.json`

Committed: `manifests/us-me-ccdf-state-plan-fy2025-2027.yaml`, `manifests/us-ms-...`, `manifests/us-pa-...`,
`manifests/ccdf-agent-queue.yaml` (status_counts: agent_ready 28, blocked_primary_source 25, needs_review 5:
us, us-in plan, us-pr, us-vi, us-in manual), `scripts/build_ccdf_state_plan_manifests.py`, this note. No
certificate changes (`data/certs/ccdf-ca-bundle.pem` remains generated and ignored).

## Rebuild

```bash
uv run python scripts/build_ccdf_state_plan_manifests.py
export REQUESTS_CA_BUNDLE=$PWD/data/certs/ccdf-ca-bundle.pem
for m in manifests/us-{me,ms,pa}-ccdf-state-plan-fy2025-2027.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-ccdf-plan-fy2025-2027 \
    --manifest $m --source-as-of 2026-09-10 --expression-date 2024-10-01
done
```

## Tests

`uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 2 skipped, 10 failed. The 10 failures are the known sparse-worktree `data/corpus` absences
(BE rulespec promotion, NY TANF compatibility x2, BE source promotion, AK/CT/MI/MT/ND/NY SNAP manuals);
none touches CCDF code or manifests.

## Remaining

Controller: `sign-ingest-manifest` for the 28 scopes, immutable release selector, `publish_corpus.py
--dry-run`, publish. The 25 blocked jurisdictions need a run from a US network (or the publishers' cooperation);
IN, PR and VI need the publisher to post an approved or certified FFY 2025-2027 plan. Decide whether the
Appendix family, the amendments, and 45 CFR 98 get their own runs.
