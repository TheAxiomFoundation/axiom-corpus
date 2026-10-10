# ACF-hosted and state-posted TANF and CCDF plan documents (2026-09-13)

Date: 2026-09-13
Programs: TANF (`manifests/tanf-agent-queue.yaml`) and CCDF (`manifests/ccdf-agent-queue.yaml`)
Branch: `discovery/ingest-acf-state-plans` (sparse worktree, artifacts written to the main
checkout's `data/corpus`; nothing under `data/corpus` is committed here)
Work order: the needs-driven closure check of 2026-09-11
(`docs/coverage/needs-closure-2026-09-11/tanf.md`, `tanf-schema.yaml`, `ccdf.md`, `ccdf-schema.yaml`):
tanf-s32 (state TANF plan as a certified document; 49 states without one), ccdf-s27 (Appendix 1,
51 ACF-hosted PDFs inventoried and never taken), ccdf-s28 (separately posted plan amendments),
ccdf-s30 (current-year payment rate and copayment schedules).

Timing: discovery and generator work 2026-09-13 about 18:20Z to 20:10Z; extraction passes
2026-09-13T20:11:45Z to 20:12:47Z (Appendix 1, 51 scopes, 62 s), 20:15:10Z to 20:17:11Z
(amendments, 11 scopes, 121 s), 20:17:12Z to 20:17:21Z (rate schedules, 5 scopes, 9 s),
20:17:44Z to 20:19:49Z (TANF plans, 36 scopes, 125 s of which South Dakota's 21-page OCR is 67 s).
Per-jurisdiction seconds are in the tables below (wall time of one `extract-official-documents`
call, download included).

GitNexus MCP tools were not available in this session, so no impact analysis was run. No
extractor code changed: `scripts/build_ccdf_state_plan_manifests.py` gained constants and a
`--family` mode (existing functions untouched; the default plan-family path is unchanged) and
`scripts/build_tanf_state_plan_manifests.py` is new.

## Scopes and conventions

| Family | Version | Citation path | Provision unit | Scopes | Rows |
| --- | --- | --- | --- | ---: | ---: |
| TANF state plan | `2026-09-13-tanf-state-plan` | `us-xx/policy/acf/tanf-plan/<period>` (`-attachments`, `-certifications` for second documents) | PDF page plus document root (Guam/Alabama precedent); HTML heading blocks for Illinois | 36 | 1,583 |
| CCDF Appendix 1 | `2026-09-13-ccdf-state-plan-appendices` | `us-xx/policy/acf/ccdf-plan/fy2025-2027-appendix-1/<finding-slug>` | one provision per non-compliance finding plus root | 51 | 741 |
| CCDF plan amendments | `2026-09-13-ccdf-state-plan-amendments` | `us-xx/policy/acf/ccdf-plan/fy2025-2027-amendment-N/<section>` (`-approval-letter` roots for DC, VT) | 41 preprint subsections plus root (CARS pattern of the 2026-09-10 run); single block for approval letters | 11 | 578 |
| CCDF rate/copay schedules | `2026-09-13-ccdf-rate-schedules` | `us-xx/policy/ccdf/rate-schedules/<document-slug>` | single block per PDF; heading blocks for the one Word file | 5 | 29 |

document_class is `policy` for all four (CCDF plan precedent). `--source-as-of 2026-09-13`;
`expression_date` is the plan's stated effective date (TANF), the plan period start 2024-10-01
(Appendix 1), the CARS "Approved as of" date (amendments) or the schedule's effective date.
None of the new roots shares a path with the 2026-09-13 follow-up selection: the CCDF plan
scopes hold `us-xx/policy/acf/ccdf-plan/fy2025-2027` and its 41 children only, the released TANF
plans are `us-al/policy/dhr/tanf/state-plan/2024`, `us-ny/policy/otda/tanf-state-plan-2024-2026`
and `us-gu/policy/acf/tanf-plan/fy2024-2026`, and no `us-xx/policy/ccdf/` prefix existed.

Verification: every scope reports `coverage.complete: true` with 0 missing, 0 extra and 0
duplicate citation paths; every citation path matches `^[a-z0-9./-]+$`; no empty body. The
draft selector `docs/ingest-runs/2026-09-13-acf-state-plans-draft.selector.json` (the
2026-09-13 follow-up draft of 556 scopes plus these 103) validates with
`uv run axiom-corpus-ingest validate-release --base /Users/pavelmakarchuk/axiom-corpus/data/corpus --release <draft> --ignore-r2-missing --max-issues 50`:
`ok: true`, 0 errors, 546 warnings (all the pre-existing `missing_parent_id` warnings of the
released `us-ca/regulation/2026-07-13-recovery` scope). The same check after the CCDF batch
alone (623 scopes) also passed with 0 errors.

## Family 1: TANF state plans (tanf-s32)

Discovery. ACF OFA posts no plan index (re-checked 2026-09-13: `acf.gov/ofa/programs/tanf`, the
state map and the resource library carry no state plan links; `/ofa/programs/tanf/state-plans`
still 404). Each state was searched on its own agency site (TANF program page, the agency's
"state plans" or "reports" page, or its own site search), the candidate file was downloaded
once, its first pages read for the plan period, and the result frozen in `RESOLUTIONS` in
`scripts/build_tanf_state_plan_manifests.py`. Rules applied:

1. Take the currently posted certified or approved plan, even where it is old (California's
   newest posted plan is the ACF-approved 2022 plan; Colorado's is the 2018 plan on Google
   Drive; Mississippi's is the plan filed as Title 18 Part 19 of the administrative code, linked
   from the MDHS State Plans page; Utah's is effective October 2022).
2. A plan the state posts only as a public-comment draft is not taken (Alaska CCDF precedent,
   2026-09-10): Indiana (2026 renewal draft), New Jersey (public-notice drafts only), Texas
   (October 2025 renewal draft), North Dakota (2022 and 2025 drafts, the latter now 404).
   Illinois's 01/01/2026 renewal is likewise a draft, so its approved 2023-2025 plan (an HTML
   page) was taken.
3. Where the agency hosts the file but its index page does not list it (AR, KS, NC, NE, OH, SC,
   UT), the file was located with a web search restricted to the agency host, taken, and the row
   records `listed_on_publisher_index: false` with what the index page shows.
4. Publisher blocks recorded, never worked around: Arizona (des.az.gov cloudflare on the plan
   PDF and the Cash Assistance pages), Minnesota (dcyf.mn.gov perfdrive challenge; the
   impersonated TLS handshake also failed on 2026-09-13). Arkansas answers every page with a WAF
   403 but serves the PDF; both Arkansas hosts omit their Sectigo intermediate, so extraction ran
   with `REQUESTS_CA_BUNDLE` = certifi + `data/certs/sectigo-public-server-authentication-ca-ov-r36.pem`
   (the CCDF run's intermediate; `data/certs/tanf-state-plan-ca-bundle.pem` is generated and
   ignored). No verification was disabled.
5. Combined-plan states: Nebraska, Tennessee, Washington and Wisconsin post the TANF section of
   their WIOA combined state plan as the TANF State Plan; those are what the states publish and
   were taken as such (Wisconsin's index labels the 2026 file "Proposed Modifications to the
   Current TANF State Plan"; the print says effective July 1, 2024, modifications March 15, 2026;
   flagged for the reviewer). Ohio's 2024 combined print carries "Effective Date: TBD";
   `expression_date` is set to the FFY 2025 start and flagged.
6. Documents that are not the plan were not taken: Rhode Island's "TANF state plan within WIOA
   plan" link is the 180-page WIOA Policy Manual (TANF mentioned 11 times); Maryland's FIA "State
   Plans" folder holds a 2017 web capture of the WIOA plan; Indiana's "TANF State Plan amendment"
   is undated WIOA-section text.

Requests: MA, NH, MS and MT need `browser_impersonation` (HTTP 403 to plain clients); every other
host answered the plain client. Colorado's Google Drive `open?id=` link is fetched through
`download_url` (the `uc?export=download` form). South Dakota's plan is a 21-page image-only scan
(`ocr: true`; Tesseract page OCR, 46,720 characters, smallest page 104). Illinois uses
`html_content_selector: "#ItemContentDiv"` (19 heading blocks; the largest, "SECTION 2 - CASH
ASSISTANCE PROGRAM", is 42 KB).

Pre-existing manifest name: `manifests/us-ny-tanf-state-plan.yaml` (the July NY compatibility
manifest reading a local `/tmp` file) matches the `us-*-tanf-state-plan.yaml` glob; the loop's
NY call failed at download before writing any artifact and New York (plan already in the corpus)
is not part of this family. Loops over this family should exclude it.

### TANF state plans: taken (36)

| State | Plan taken (publisher's description) | Index page read | Listed there | Rows | Pages | Min / total body chars | Seconds |
|---|---|---|---|---:|---:|---|---:|
| us-ak | Alaska TANF State Plan 2026-2028, plan effective December 31, 2025 (Office of the Governor and Department of Health) | https://health.alaska.gov/en/services/alaska-temporary-assistance/ | yes | 34 | 33 | 173 / 76,521 | 3 |
| us-ar | Arkansas State Plan for Title IV-A, signed 2023 (DWS signature copy); the DWS site posts the same 45-page plan as AR-TANF-State-Plan-03152023-CLEAN.pdf | https://humanservices.arkansas.gov/divisions-shared-services/county-operations/temporary-assistance-for-needy-families/ | no | 45 | 44 | 80 / 85,900 | 1 |
| us-ca | ACF Approved TANF State Plan 2022, effective October 1, 2022 (the newest plan the CDSS TANF State Plan page posts; the 2019 plan and addendum are also listed) | https://www.cdss.ca.gov/inforesources/data-portal/state-plans/tanf-state-plan | yes | 36 | 35 | 316 / 85,506 | 3 |
| us-co | Colorado State Plan TANF effective July 1, 2018: the newest TANF State Plan the Colorado Works page links (2018, 2015, 2012, 2009, all on Google Drive); later renewals are not posted | https://cdhs.colorado.gov/colorado-works | yes | 22 | 21 | 170 / 53,515 | 2 |
| us-ct | CT TANF State Plan FFY 2024-2026 (October 1, 2023 through September 30, 2026), 4/15/24 amendment print | https://portal.ct.gov/dss/knowledge-base/articles/state-plans-and-federal-reports/tanf-state-plans-and-federal-reports | yes | 55 | 54 | 208 / 108,811 | 2 |
| us-dc | 2023 District of Columbia State Plan for Administration of the TANF Block Grant, effective October 1, 2023 | https://dhs.dc.gov/service/temporary-cash-assistance-needy-families-tanf | yes | 47 | 46 | 153 / 71,456 | 1 |
| us-de | Delaware TANF State Plan 10-1-23 to 09-30-26 (listed as 'Delaware TANF State Plan 2023-2026 (PUBLIC NOTICE)') | https://dhss.delaware.gov/dss/division-of-social-services/forms-and-publications/ | yes | 60 | 59 | 217 / 124,847 | 2 |
| us-fl | Florida TANF State Plan 2026-2028 (effective July 1, 2026) | https://www.myflfamilies.com/services/public-assistance/temporary-cash-assistance | yes | 74 | 73 | 170 / 181,616 | 1 |
| us-ga | Georgia's TANF State Plan Renewal FY2026, effective January 2026 (the earlier 'draft' renewal file is also posted, not taken) | https://dfcs.georgia.gov/services/temporary-assistance-needy-families | yes | 56 | 55 | 2 / 119,663 | 2 |
| us-hi | Hawaii TANF State Plan effective October 1, 2023 (signed, certified); a plan 'Effective 2025Oct01, Certified 2025Dec23' is in the search index but its URL answers HTTP 404 and the TANF Strategic Plans page does not list it | https://humanservices.hawaii.gov/tanf-strategic-plans/ | yes | 92 | 91 | 26 / 196,560 | 2 |
| us-ia | Iowa's TANF State Plan, effective October 1, 2025 - September 30, 2028, with its attachments volume | https://hhs.iowa.gov/assistance-programs/cash-assistance/tanf | yes | 78 | 76 | 35 / 164,289 | 2 |
| us-id | Idaho State Plan Renewal for TANF FY2026-FY2028, effective October 1, 2025 (Laserfiche WebLink DocView id=35475, served by the repository's ElectronicFile endpoint) | https://healthandwelfare.idaho.gov/services-programs/financial-assistance/about-tafi | yes | 25 | 24 | 101 / 67,559 | 2 |
| us-il | TANF State Plan for January 1, 2023 - June 30, 2025, published as an HTML page (the newest approved plan; the 01/01/2026 renewal is posted only as a public-comment draft PDF, not taken) | https://www.dhs.state.il.us/page.aspx?item=56061 | yes | 20 | 19 | 75 / 90,261 | 1 |
| us-ks | State of Kansas TANF State Plan effective October 1, 2023 - September 30, 2026; the DCF site search lists the 'TANF State Plan completion letter' and the EES pages list no plan, so the file was located with a web search on the same host | https://www.dcf.ks.gov/search/Pages/SearchResults.aspx?k=TANF%20state%20plan | no | 36 | 35 | 231 / 93,026 | 2 |
| us-ky | Kentucky TANF State Plan 2023 (10/1/2023-09/30/2026, DocuSign copy) | https://www.chfs.ky.gov/agencies/dcbs/dfs/fssb/Pages/default.aspx | yes | 61 | 60 | 153 / 92,037 | 2 |
| us-ma | TANF Massachusetts State Plan 2024 (renewal; the document states no effective date, FFY 2025 start assumed for expression_date) | https://www.mass.gov/doc/tanf-massachusetts-state-plan-2024-pdf | yes | 24 | 23 | 965 / 67,382 | 2 |
| us-me | Maine TANF State Plan (signed) 2024-2026, effective January 1, 2024 (Data and Reports page, 'Other Reports and Analysis') | https://www.maine.gov/dhhs/ofi/about-us/data-reports | yes | 33 | 32 | 165 / 71,082 | 1 |
| us-mi | TANF State Plan Effective January 1, 2026 (the 2023 plan and its 2024/2025 revisions are also listed) | https://www.michigan.gov/mdhhs/inside-mdhhs/state-plans-and-amendments | yes | 31 | 30 | 142 / 64,242 | 1 |
| us-ms | TANF State Plan (Economic Assistance) as filed in the Mississippi Administrative Code, Title 18 Part 19 (period beginning July 1, 2020); the MDHS State Plans page links the Secretary of State copy | https://www.mdhs.ms.gov/reports/plans/ | yes | 32 | 31 | 50 / 77,330 | 1 |
| us-mt | TANF State Plan 1/2024-12/2026 (effective January 1, 2024 to December 31, 2026), listed on the TANF Policy Manual page | https://dphhs.mt.gov/hcsd/Manuals/TANFpolicymanual | yes | 34 | 33 | 249 / 72,057 | 2 |
| us-nc | North Carolina TANF State Plan FFY 2026-FFY 2028 (effective October 1, 2025 - September 30, 2028), hosted at ncdhhs.gov/2026-2028-tanf-state-plan-162026; the publications page still lists only the 2022-2025 signed plan | https://www.ncdhhs.gov/divisions/social-services/publications/temporary-assistance-needy-families-state-plan | no | 75 | 74 | 276 / 203,525 | 2 |
| us-ne | Nebraska State TANF Plan 2024 (WIOA combined state plan TANF section, year 2024), hosted at dhhs.ne.gov/Documents; the TANF page lists the Work Verification Plan and the 2025 TANF Expenditure Plan but not this file; the '2026 WIOA Nebraska State Plan Modification for TANF' URL answers 404 | https://dhhs.ne.gov/Pages/TANF.aspx | no | 38 | 37 | 142 / 106,301 | 1 |
| us-nh | TANF State Plan Renewal October 2023 (effective October 1, 2023) | https://www.dhhs.nh.gov/temporary-assistance-needy-families-tanf | yes | 39 | 38 | 202 / 107,669 | 2 |
| us-nm | FFY 2024-2026 Final TANF State Plan (July 2024; period July 1, 2024 through June 30, 2026) | https://www.hca.nm.gov/income-support-division-plans-and-reports/ | yes | 42 | 41 | 435 / 110,408 | 1 |
| us-nv | FFY24 Nevada TANF State Plan, effective December 31, 2023 (final) | https://www.dss.nv.gov/programs/tanf/documents-and-links/ | yes | 57 | 56 | 293 / 143,772 | 1 |
| us-oh | 2024 TANF State Plan Combined (State Title IV-A Plan submitted under 42 U.S.C. 602; the print says 'Effective Date: TBD'), hosted on the ODJFS asset host; the Cash Assistance page links no plan, located with a web search; expression_date is the FFY 2025 start and should be reviewed | https://jfs.ohio.gov/public-assistance/cash-assistance | no | 44 | 43 | 61 / 103,830 | 1 |
| us-ok | TANF State Plan (2023 renewal effective December 1, 2023, with the August 1, 2024 transmittal letter to ACF OFA) | https://oklahoma.gov/okdhs/services/tanf/tanfhome.html | yes | 31 | 30 | 553 / 67,060 | 2 |
| us-pa | 2024 Pennsylvania TANF State Plan, effective October 1, 2024 (submitted to HHS December 2024) | https://www.pa.gov/agencies/dhs/resources/cash-assistance/tanf/tanf-state-plan | yes | 62 | 61 | 2 / 147,054 | 1 |
| us-sc | South Carolina TANF State Plan December 2025 (effective October 2025), hosted on dss.sc.gov; the TANF program and TANF data pages do not list it (located with a web search) | https://dss.sc.gov/assistance-programs/tanf/ | no | 36 | 35 | 143 / 68,170 | 1 |
| us-sd | South Dakota State Plan for TANF effective October 1, 2023 through September 30, 2026 (scanned image-only PDF, 21 pages; Tesseract page OCR) | https://dss.sd.gov/economicassistance/tanf.aspx | yes | 22 | 21 | 104 / 46,720 | 67 |
| us-tn | TANF State Plan 2024, signed 7/2/2024 (WIOA combined state plan TANF program-specific requirements, effective July 1, 2024) | https://www.tn.gov/humanservices/for-families/families-first-tanf.html | yes | 21 | 20 | 160 / 53,262 | 3 |
| us-ut | Utah TANF State Plan (effective October 2022); jobs.utah.gov answers the state plans directory with HTTP 403 and the FEP pages with HTTP 500 to this client, so the listing page could not be read (located with a web search) | https://jobs.utah.gov/edo/stateplans/ | no | 35 | 34 | 5 / 73,213 | 1 |
| us-vt | Vermont TANF State Plan Renewal October 1, 2024 through December 31, 2027 | https://dcf.vermont.gov/esd/resources/reports | yes | 37 | 36 | 90 / 78,713 | 1 |
| us-wa | Washington's TANF State Plan Components, August 1, 2026 (Talent and Prosperity for All WIOA combined plan, TANF-only portion) with the signed 2026 certifications | https://workfirst.wa.gov/tanf | yes | 19 | 17 | 144 / 43,666 | 2 |
| us-wi | Wisconsin's Combined State Plan under WIOA, Section VII TANF, PY 2024-2027, effective July 1, 2024, modifications March 15, 2026; the index labels the file 'Proposed Modifications to the Current TANF State Plan' (the stand-alone FFY 2021-2023 plan is the newest non-WIOA print) | https://dcf.wisconsin.gov/w2/researchers/state-plans | yes | 71 | 70 | 155 / 185,166 | 1 |
| us-wv | Temporary Assistance for Needy Families State Plan FFY2024 (October 1, 2024 - September 30, 2026, effective October 1, 2024) | https://bfa.wv.gov/state-plans | yes | 59 | 58 | 269 / 127,217 | 2 |

### TANF state plans: not taken (13)

| State | Status | What was checked |
|---|---|---|
| us-az | blocked_primary_source | Publisher blocked: des.az.gov answers the TANF State Plan PDF (https://des.az.gov/sites/default/files/dl/tanf_state_plan_oct_2026.pdf, 'State of Arizona TANF State Plan', October 2026 per the search index) and the Cash Assistance pages with HTTP 403 cloudflare 'Just a moment' challenges for plain and browser-impersonated clients (2026-09-13), the same wall the CCDF run recorded. |
| us-in | needs_review | Not taken: the DFR page posts the '2026 TANF State Plan - Renewal Draft' for public comment (to 2025-12-20) and an undated 'Indiana TANF State Plan amendment' (WIOA combined-plan TANF section text, 18 pages); no certified or approved current plan is posted. |
| us-la | needs_review | Not taken: the DCFS 'TANF State Plan' page (page/56) renders no plan link or plan text to plain or browser clients (230 KB of navigation only); the plan PDFs search engines index are the 2011-2012 and 2012 renewals and the WIOA combined-plan TANF portion (undated); no current plan is reachable. |
| us-md | needs_review | Not taken: the FIA documents page's 'State Plans' folder holds the SNAP E&T FY25 plan and a 2017 web capture of the WIOA State Plan; the Temporary Cash Assistance page links no plan; no current TANF state plan is posted (the plan is part of Maryland's WIOA combined plan filed on the federal portal). |
| us-mn | blocked_primary_source | Publisher blocked: dcyf.mn.gov (Lead Agency since 2025) redirects plain clients to the validate.perfdrive.com bot challenge and refused the curl_cffi impersonated TLS handshake on 2026-09-13; the legacy mn.gov/dhs MFIP pages answer 404; Minnesota's TANF plan is the MFIP section of the WIOA combined plan (federal portal), not a state-hosted document reachable here. |
| us-mo | needs_review | Not taken: the DSS 'What is the TANF State Plan?' page indexed by search engines (FFY 2026-2027 modifications, comments through 2026-01-09) answers HTTP 404, as do dss.mo.gov/fsd/pdf/mo-tanf-plan-ffy2021-2023.pdf, tanf-wioa-2024-2027.pdf and the Temporary Assistance pages' plan paths (2026-09-13); no plan is reachable on the publisher's site. |
| us-nd | needs_review | Not taken: the TANF page links no plan; the two plan files search engines index (draft-2022-ND-TANF-State-Plan.pdf, EA/draft-tanf-state-plan-2025.pdf) are public-comment drafts and the 2025 one answers HTTP 404 (2026-09-13); no certified plan is posted. |
| us-nj | needs_review | Not taken: the Work First New Jersey and DFD pages link no plan; the only plan files on nj.gov are public-comment drafts under providers/grants/public/publicnoticefiles (FFY 2018-2020, FFY 2021-2023, FFY 2024-2026), and the FFY 2024-2026 draft URL answers HTTP 404 (2026-09-13). |
| us-or | needs_review | Not taken: the ODHS TANF Cash Benefits page links no plan and the FFY 2023 plan URL search engines index (odhs/data/sspdata/2022-10-01-tanf-state-plan-fy23.pdf) answers HTTP 404 (2026-09-13); the ODHS data page (odhs/data/pages/ssp.aspx) answers 404; no current plan is posted. |
| us-ri | needs_review | Not taken: the DHS State Plans page's 'TANF state plan within WIOA plan' link (media/2731) is the 180-page WIOA Policy Manual (State, updated 03/18/2021), which mentions TANF eleven times and carries no TANF plan text; the RI Works page links no plan; no TANF state plan is posted. |
| us-tx | needs_review | Not taken: hhs.texas.gov posts only the 'Texas State Plan for TANF Renewal' dated October 1, 2025 as a draft (texas-tanf-state-plan-draft-2025.pdf; HTTP 403 to plain clients, served to a browser-impersonated client) and the superseded October 2019 plan; no certified renewal is posted. |
| us-va | needs_review | Not taken: the VDSS TANF pages (program, manual, data, VIEW) link the TANF Manual, forms and Title IV-A of the Social Security Act but no state plan; web search finds no TANF state plan on dss.virginia.gov (Virginia's plan is filed within the WIOA combined plan on the federal portal). |
| us-wy | needs_review | Not taken: the DFS Cash Assistance pages and the SNAP and POWER Policy Manual page link no TANF state plan (the '2025.2026 State Model Plan Draft' is the LIHEAP model plan); web search finds none on dfs.wyo.gov. |

## Family 2: CCDF Appendix 1 (ccdf-s27)

Index: https://acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027, re-read 2026-09-13 (browser
User-Agent; acf.gov answers non-browser agents with HTTP 202 and an empty body, so the manifests
set `request: browser_user_agent: true`). 51 Appendix PDFs (50 states + DC; none for the five
territories), all Aspose.Words CARS exports "Appendix 1: Lead Agency Implementation Plan for
<State> FFY 2025-2027, Version: Initial Plan" with the accepted plan status line, 3 to 48 pages
(NM 3, WV 48), 3.5 KB to 85 KB of text. The index lists no amendments (confirmed again: the only
"amend" on the page is the 45 CFR 98.14(d) posting requirement), so the task's "approved
amendments ACF posts" resolved to the Lead Agency pages (family 3).

Provision unit: one provision per non-compliance finding. Every finding starts with an all-caps
`AREA:TOPIC` line ("EQUAL ACCESS:PAYMENT RATES"); 40 distinct headings occur across the 51
files (`APPENDIX_FINDING_SLUGS`). `labeled_sections` uses that line as the label, appends the
wrapped second line of the seven long headings through `heading_continuation_pattern`, and maps
each heading to a slug-safe segment through `section_label_replacements` (the NH CHIP precedent
of 2026-09-12: display labels are not citation segments). No heading repeats within a file. New
Mexico has one finding (2 rows); the mean is 13.5 findings. A post-extraction check confirmed
every path is lowercase-slug and every finding body is at least 277 characters.

### CCDF Appendix 1 (51 jurisdictions)

| State | Findings | Pages | Min body chars | Seconds |
|---|---:|---:|---:|---:|
| us-ak | 20 | 24 | 572 | 1 |
| us-al | 15 | 21 | 629 | 1 |
| us-ar | 4 | 4 | 706 | 1 |
| us-az | 19 | 18 | 538 | 2 |
| us-ca | 30 | 20 | 277 | 1 |
| us-co | 8 | 8 | 782 | 1 |
| us-ct | 7 | 7 | 478 | 2 |
| us-dc | 9 | 9 | 461 | 2 |
| us-de | 20 | 24 | 486 | 2 |
| us-fl | 6 | 7 | 618 | 2 |
| us-ga | 6 | 7 | 634 | 1 |
| us-hi | 16 | 22 | 662 | 1 |
| us-ia | 18 | 20 | 712 | 1 |
| us-id | 16 | 29 | 1178 | 2 |
| us-il | 21 | 27 | 529 | 1 |
| us-in | 16 | 16 | 443 | 1 |
| us-ks | 19 | 20 | 582 | 1 |
| us-ky | 12 | 17 | 1524 | 1 |
| us-la | 4 | 5 | 628 | 1 |
| us-ma | 17 | 14 | 659 | 2 |
| us-md | 15 | 35 | 2003 | 1 |
| us-me | 6 | 5 | 542 | 1 |
| us-mi | 22 | 22 | 521 | 1 |
| us-mn | 21 | 15 | 646 | 1 |
| us-mo | 12 | 11 | 534 | 1 |
| us-ms | 24 | 31 | 881 | 2 |
| us-mt | 7 | 7 | 669 | 1 |
| us-nc | 10 | 9 | 581 | 1 |
| us-nd | 16 | 12 | 472 | 1 |
| us-ne | 24 | 26 | 505 | 1 |
| us-nh | 17 | 17 | 586 | 1 |
| us-nj | 11 | 17 | 882 | 1 |
| us-nm | 1 | 3 | 1676 | 1 |
| us-nv | 14 | 10 | 328 | 1 |
| us-ny | 4 | 7 | 1471 | 1 |
| us-oh | 8 | 10 | 1194 | 2 |
| us-ok | 18 | 14 | 776 | 1 |
| us-or | 7 | 6 | 471 | 1 |
| us-pa | 7 | 11 | 883 | 1 |
| us-ri | 6 | 6 | 490 | 1 |
| us-sc | 10 | 10 | 761 | 2 |
| us-sd | 5 | 5 | 631 | 1 |
| us-tn | 18 | 18 | 494 | 1 |
| us-tx | 4 | 4 | 556 | 1 |
| us-ut | 7 | 10 | 760 | 1 |
| us-va | 8 | 5 | 288 | 1 |
| us-vt | 20 | 16 | 509 | 2 |
| us-wa | 22 | 15 | 529 | 1 |
| us-wi | 21 | 16 | 484 | 1 |
| us-wv | 29 | 48 | 409 | 1 |
| us-wy | 13 | 10 | 563 | 1 |

Total appendix rows: 741 (51 roots + 690 findings).

## Family 3: CCDF plan amendments (ccdf-s28)

The 11 states the closure check marked EXTRACTABLE (CA, DC, MA, ME, NC, ND, OH, OR, SD, VT, WA)
were re-read on their Lead Agency pages (the same `publisher_index_url` as the plan rows). Every
FFY 2025-2027 amendment print posted was taken as its own document (root
`fy2025-2027-amendment-N`), so the scope carries the amendment history rather than only the
latest consolidation: ME 1-3, SD 1-3, MA 1-2, ND 1-2, OH 1-2, CA 1, NC 2, OR 1, WA 1. All but
California are CARS prints (41/41 subsections with `CARS_EXTRACTION`); California posts its own
Word export (`CA_EXTRACTION`, no CARS status line). DC and VT post only ACF approval letters for
their amendments; those were taken as single-block documents (`-approval-letter` roots), which
carry the approval dates the element asks for but not the amended plan text. Not taken: Maine
Amendment #4 (6.26.26) answers HTTP 200 application/pdf with a 0-byte body; North Carolina's
"with Amendment 1" and "with Amendment 2" links resolve to the same file (Amendment 2, taken
once); Michigan's Amendment 1 link is dead and its Amendment 2 print is already the taken plan;
Missouri's Amendment #1/#2 sit behind the blocked dese.mo.gov media path.

### CCDF plan amendments (11 states)

| State | Documents taken (approved as of) | Rows | Min body chars | Seconds |
|---|---|---:|---:|---:|
| us-ca | Amendment 1 (2024-10-01) | 42 | 2683 | 9 |
| us-dc | Amendment 1 approval letter (2024-10-01); Amendment 2 approval letter (2026-05-28) | 4 | 2808 | 2 |
| us-ma | Amendment 1 (2026-03-02); Amendment 2 (2026-04-27) | 84 | 1728 | 7 |
| us-me | Amendment 1 (2025-05-27); Amendment 2 (2025-08-18); Amendment 3 (2025-12-18) | 126 | 1079 | 14 |
| us-nc | Amendment 2 (2026-03-12) | 42 | 2395 | 5 |
| us-nd | Amendment 1 (2025-08-12); Amendment 2 (2026-04-10) | 84 | 2331 | 8 |
| us-oh | Amendment 1 (2025-12-18); Amendment 2 (2026-07-16) | 84 | 1228 | 11 |
| us-or | Amendment 1 (2025-11-14) | 42 | 1308 | 7 |
| us-sd | Amendment 1 (2025-07-09); Amendment 2 (2026-02-05); Amendment 3 (2026-05-29) | 126 | 1975 | 52 |
| us-vt | Amendment 1 approval letter (2024-10-07) | 2 | 3086 | 2 |
| us-wa | Amendment 1 (2026-05-29) | 42 | 1319 | 4 |

## Family 4: CCDF payment rate and copayment schedules (ccdf-s30)

The 17 publisher pages the 2026-09-10 run notes flagged were re-read. Four post operative
schedules and were taken: Maine (county maximum market rates 5/19/25, the FY26 parent fee guide
and the 4/18/26 income guidelines, the last a Word file), Idaho (ICCP copay chart 10/1/2025 and
local market rates 7/1/2025, both Laserfiche WebLink documents served by the repository's
ElectronicFile endpoint), Tennessee (income eligibility limits and parent co-pay fees 10/1/2025;
provider weekly reimbursement rates with QRIS bonuses 1/1/2026) and South Carolina (Scholarship
fee scale, maximum payments and income standards for 10/1/2025-9/30/2026). North Carolina's
Subsidy Services "Market Rates" page (one hop from its CCDF page; the closure check had it as
REVIEW) posts the subsidized child care market rate tables for centers and homes, current
(effective 10/1/2023) and upcoming (effective 10/1/2026, revised 8/18/2026); all four were taken.

The other 13 pages (KY, UT, MN, NJ, CO, CT, LA, OR, VA, RI, PA, MS, VT) list market rate survey
reports, narrow cost analyses or alternative-methodology reports only. Reviewer judgment: those
are the basis for rate setting (45 CFR 98.45(f)), not the rate or copay schedule the element
asks for, so they were not taken; the rows say so (`needs_review` under
`ccdf_rate_and_copay_schedules`). If the reviewer wants the MRS reports as a family, the URLs
are in the run notes of 2026-09-10 and on the pages named in `RATE_PAGES_REPORTS_ONLY`.

### CCDF rate and copay schedules (5 states)

| State | Documents taken (effective) | Rows | Body chars | Seconds |
|---|---|---:|---|---:|
| us-id | Idaho Child Care Copay Chart, effective October 1, 2025 (2025-10-01); Idaho Child Care Program Local Market Rates, effective July 1, 2025 (2025-07-01) | 4 | 1201, 1374 | 2 |
| us-me | Maine Child Care Market Rates (maximum rates by county and setting), May 19, 2025 (2025-05-19); CCAP Parent Fee Guide (FY26), effective April 18, 2026 (2026-04-18); CCAP Current Income Guidelines (125% SMI), April 18, 2026 (2026-04-18) | 7 | 1386, 3380, 473, 1012 | 1 |
| us-nc | Subsidized Child Care Market Rates for Child Care Centers, effective October 1, 2023 (current) (2023-10-01); Subsidized Child Care Market Rates for Family Child Care Homes, effective October 1, 2023 (current) (2023-10-01); Subsidized Child Care Market Rates for Child Care Centers, effective October 1, 2026 (revised August 18, 2026) (2026-10-01); Subsidized Child Care Market Rates for Family Child Care Homes, effective October 1, 2026 (revised August 18, 2026) (2026-10-01) | 8 | 9958, 11754, 11903, 12822 | 2 |
| us-sc | SC Child Care Scholarship Program Fee Scale, October 1, 2025 - September 30, 2026 (2025-10-01); SC Child Care Scholarship Maximum Payments Allowed, October 1, 2025 - September 30, 2026 (2025-10-01); Child Care Income Standards, 2025-2026 (2025-10-01) | 6 | 1913, 14992, 644 | 1 |
| us-tn | Child Care Certificate Program Income Eligibility Limits and Parent Co-Pay Fees, effective October 1, 2025 (2025-10-01); Child Care Certificate Program Provider Weekly Reimbursement Rates including QRIS Scorecard Bonus Payments, effective January 1, 2026 (2026-01-01) | 4 | 4743, 2985 | 3 |

## Queue records

Both queues keep one row per jurisdiction: the new families are recorded on the existing rows
under `additional_families` (family, queue_status, index_url, primary_source_url(s),
target_manifest, target_scope, taken_count, notes) rather than as new rows. The CCDF queue on
`main` already has two `us` rows (the federal directory row and the 45 CFR 98 row) and two
`us-in` rows (plan and CCDF Policy Manual); they were left as they are and the family entries
attach to the first `policy`-class row of each jurisdiction. Note that the default (no
`--family`) path of `build_ccdf_state_plan_manifests.py` rebuilds the state rows from
`RESOLUTIONS` and would drop the second `us` row and any `additional_families` if re-run; the
family modes only annotate rows in place. `status_counts` at the top of each queue count rows,
not family entries, and are unchanged.

## Closure cells

- tanf-s32: 36 states move to PRESENT (the 35 REVIEW states taken plus Montana's EXTRACTABLE
  cell); 13 stay open: AZ and MN as OUTREACH (bot walls), IN, NJ, TX and ND as REVIEW (drafts
  only), LA, MD, MO, OR, RI, VA and WY as ABSENT-on-publisher (nothing posted or every plan URL
  404). With AL and NY already PRESENT, 38 of 51 jurisdictions now carry a state TANF plan.
- ccdf-s27: all 51 EXTRACTABLE cells close.
- ccdf-s28: the 11 EXTRACTABLE cells close (DC and VT with approval letters rather than plan
  text; the reviewer may want to keep those two as partial). The 5 PRESENT-by-amended-plan cells
  (AR, IA, LA, MI, MN) are unchanged; the 6 OUTREACH and 29 REVIEW cells are unchanged.
- ccdf-s30: ME, ID, TN, SC (EXTRACTABLE) and NC (REVIEW) close; 12 EXTRACTABLE cells stay open
  by the reports-versus-schedules judgment above and are now annotated in the queue.

## Disk and environment

`df -h /` showed 21 GiB free at the start of the session, 8.2 GiB before the Appendix batch and
4.7 GiB before the TANF batch (other sessions writing concurrently); the 3 GB stop line was not
reached. The new artifacts total about 250 MB of sources. The worktree's `.venv` lost the
editable `axiom_corpus` install once during the run (concurrent `uv run` calls); `uv sync` in the
worktree restored it. `uv sync` was never run in the main checkout.

## Lint and tests

`uv run ruff check scripts`: passes. `uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`: 286 passed, 2 skipped, 12 failed. The 12 failures are the known sparse-worktree `data/corpus` absences (Armenia tax code continuity sources, BE rulespec promotion, NY TANF compatibility x2, Israel OpenLaw pilot manifest, BE source promotion, AK/CT/MI/MT/ND/NY SNAP manual TOC tests); none touches the TANF or CCDF generators, manifests or queues, and the same selection passes in the main checkout. Note: plain `uv run pytest` in a fresh worktree resolves to the anaconda pytest (Python 3.10) because pytest lives in the `dev` extra, and fails collection with `ModuleNotFoundError: axiom_corpus` or `NameError: Citation`; run it with `--extra dev`.

## Controller section

Selector additions (all `document_class: policy`), also written into
`docs/ingest-runs/2026-09-13-acf-state-plans-draft.selector.json` on top of the 2026-09-13
follow-up draft (556 + 103 = 659 scopes; `ok: true`, 0 errors):

- `2026-09-13-ccdf-state-plan-appendices`: us-ak, us-al, us-ar, us-az, us-ca, us-co, us-ct, us-dc,
  us-de, us-fl, us-ga, us-hi, us-ia, us-id, us-il, us-in, us-ks, us-ky, us-la, us-ma, us-md, us-me,
  us-mi, us-mn, us-mo, us-ms, us-mt, us-nc, us-nd, us-ne, us-nh, us-nj, us-nm, us-nv, us-ny, us-oh,
  us-ok, us-or, us-pa, us-ri, us-sc, us-sd, us-tn, us-tx, us-ut, us-va, us-vt, us-wa, us-wi, us-wv,
  us-wy (51).
- `2026-09-13-ccdf-state-plan-amendments`: us-ca, us-dc, us-ma, us-me, us-nc, us-nd, us-oh, us-or,
  us-sd, us-vt, us-wa (11).
- `2026-09-13-ccdf-rate-schedules`: us-id, us-me, us-nc, us-sc, us-tn (5).
- `2026-09-13-tanf-state-plan`: us-ak, us-ar, us-ca, us-co, us-ct, us-dc, us-de, us-fl, us-ga,
  us-hi, us-ia, us-id, us-il, us-ks, us-ky, us-ma, us-me, us-mi, us-ms, us-mt, us-nc, us-ne, us-nh,
  us-nm, us-nv, us-oh, us-ok, us-pa, us-sc, us-sd, us-tn, us-ut, us-vt, us-wa, us-wi, us-wv (36).

Then `sign-ingest-manifest` per scope, the artifact commit on the release branch, and
`publish_corpus.py --dry-run`. No pull request was opened.

Decisions for the reviewer:

1. Drafts: IN, NJ, TX and ND post only public-comment drafts (the Texas and Indiana drafts are
   the current renewals). Taking drafts would close four more tanf-s32 cells; the CCDF precedent
   says no.
2. Combined-plan TANF sections (NE, TN, WA, WI) and Wisconsin's "Proposed Modifications" label;
   Ohio's "Effective Date: TBD" print; the seven files taken although the agency's index page
   does not list them (AR, KS, NC, NE, OH, SC, UT).
3. Old-but-current postings: CA 2022, CO 2018, MS 2020, UT 2022 are the newest plans those
   agencies post.
4. DC and VT amendment scopes hold approval letters only.
5. Market rate survey reports (12 states) left untaken for ccdf-s30.
6. Maine CCDF Amendment #4 is a 0-byte file on the publisher; re-check later.

Rebuild:

```bash
uv run python scripts/build_ccdf_state_plan_manifests.py --family appendices
uv run python scripts/build_ccdf_state_plan_manifests.py --family amendments
uv run python scripts/build_ccdf_state_plan_manifests.py --family rate-schedules
uv run python scripts/build_tanf_state_plan_manifests.py
export REQUESTS_CA_BUNDLE=$PWD/data/certs/tanf-state-plan-ca-bundle.pem
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
for m in manifests/us-*-ccdf-state-plan-appendix-fy2025-2027.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-13-ccdf-state-plan-appendices --manifest $m --source-as-of 2026-09-13 --expression-date 2024-10-01; done
for m in manifests/us-*-ccdf-state-plan-amendments-fy2025-2027.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-13-ccdf-state-plan-amendments --manifest $m --source-as-of 2026-09-13; done
for m in manifests/us-*-ccdf-rate-schedules.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-13-ccdf-rate-schedules --manifest $m --source-as-of 2026-09-13; done
for m in $(ls manifests/us-*-tanf-state-plan.yaml | grep -v us-ny); do
  uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-13-tanf-state-plan --manifest $m --source-as-of 2026-09-13; done
```
