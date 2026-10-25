# CCDF FFY 2025-2027 state and territory plans (ACF-118): retry pass 2 (US network)

Date: 2026-09-10
Program: CCDF (board Year 1 list; `manifests/ccdf-agent-queue.yaml`)
Branch: `discovery/ingest-ccdf`
Earlier notes: `docs/ingest-runs/2026-09-10-ccdf-state-plans-fy2025-2027.md` (first run: 25 extracted, 25 blocked,
6 needs_review) and `...-retry.md` (retry 1: ME, MS, PA added; 25 hosts re-probed, all still blocked).

Timing: started_at 2026-09-10T21:32:58Z, finished_at 2026-09-10T21:55:03Z, agent wall time 22 min 5 s (1325 s).
Probe pass 2026-09-10T21:34:53Z to 21:35:01Z (26 URLs, 8 threads). Extraction pass 2026-09-10T21:46:29Z to
21:48:08Z (99 s for 16 jurisdictions; per-jurisdiction seconds below).

## Scope and conventions

Unchanged from the first run: the FFY 2025-2027 ACF-118 plan posted by each Lead Agency and reached through the ACF
directory https://acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027; document_class `policy`; version
`2026-09-10-ccdf-plan-fy2025-2027`; citation path `us-xx/policy/acf/ccdf-plan/fy2025-2027`; 41 second-level
subsections plus the document root (42 provisions per plan); `--source-as-of 2026-09-10`,
`--expression-date 2024-10-01`. Work order: retry every `blocked_primary_source` row (the queue held 25, not the 23
in the work order text; all 25 were retried) and the Indiana `needs_review` plan row, now that the controller's network
exits from a US address.

## Per-host retry

Method: one plain `requests` GET with a browser User-Agent and one `curl_cffi` `impersonate="chrome"` GET per URL,
20 s timeout each, `REQUESTS_CA_BUNDLE` = certifi + the Arkansas Sectigo intermediate (`data/certs/ccdf-ca-bundle.pem`,
generated). Nothing was worked around: no proxies, mirrors or archived copies, and TLS verification was never
disabled (no new certificate files were needed; every newly answering host presented a complete chain).

| Row | URL probed | Plain requests | curl_cffi chrome | Outcome |
| --- | --- | --- | --- | --- |
| AK | aws.state.ak.us OnlinePublicNotices View.aspx?id=215530 | 200 (39.8 KB) | 200 | answers; only the 2024-05-24 public-comment draft is posted: needs_review |
| AS | www.dhss.as/index.html | SSLCertVerificationError (self-signed, expired CN=cmaster70) | curl 60 | same failure |
| AZ | des.az.gov .../child-care-and-development-fund-state-plan | 403 cloudflare | 403 cloudflare | same failure |
| CO | cdec.colorado.gov/resources/state-plans | 200 | 200 | plan located (Google Drive): extracted |
| CT | www.ctoec.org/ccdf/ | 200 | 403 cloudflare | plan located; plain requests only: extracted |
| GA | www.decal.ga.gov/BftS/CCDFPlan.aspx | remote end closed connection | curl 52 empty reply | same failure |
| ID | publicdocuments.dhw.idaho.gov WebLink DocView id=32013 | 200 | 200 | plan served by the WebLink ElectronicFile.aspx endpoint: extracted |
| KS | www.dcf.ks.gov .../Child-care-and-early-education.aspx | 200 | 200 | page has no plan link; plan found with the DCF site search: extracted |
| KY | www.chfs.ky.gov/agencies/dcbs/dcc/Pages/default.aspx | 200 | 200 | plan located: extracted |
| LA | louisianabelieves.com -> doe.louisiana.gov early-childhood policy guidance | 200 | 200 | Amendment 1 (only approved version): extracted |
| MD | earlychildhood.marylandpublicschools.org/2025-2027-ccdf-plan | 403 cloudflare (107 KB) | 403 | same failure (the about/ccdf-state-plan landing page answers 200) |
| MN | dcyf.mn.gov/child-care-and-development-fund | 200 redirected to validate.perfdrive.com challenge | 200 dcyf.mn.gov page (TLS verified) | Amendment 3 (only version posted), impersonation: extracted |
| MO | dese.mo.gov/media/pdf/acf-118-ccdf-ffy-2025-2027-missouri | 200 text/html Drupal antibot form + Incapsula (52.9 KB) | 200 same | same failure |
| MP | www.childcare.gov.mp/ | 403 nginx | 403 nginx | same failure |
| NE | dhhs.ne.gov/Pages/Child-Care-and-Development-Fund-Plan.aspx | 200 | 200 | plan located: extracted |
| NJ | childcarenj.gov .../CCDF_State_Plan_for_New_Jersey_FFY25-27.pdf | 200 application/pdf (3,003,475 B) | 200 | direct PDF from the ACF index: extracted |
| NY | ocfs.ny.gov/main/childcare/stateplan/ | 200 F5/Shape TSPD challenge (7.5 KB) | 200 same | same failure |
| OR | www.oregon.gov/delc/about-us/pages/state-plans.aspx | 200 | 200 | plan located: extracted |
| RI | dhs.ri.gov/regulations/state-plans | 200 | 200 | plan located: extracted |
| SC | www.scchildcare.org/resources/ -> scchildcare.org | 200 | 200 | plan located: extracted |
| TN | www.tn.gov/humanservices/.../tdhs-reports-and-information.html | 200 (1 of 3 requests: SSL unexpected EOF) | 200 | plan located: extracted |
| TX | www.twc.texas.gov/programs/child-care/data-reports-plans | 202 empty body (CloudFront) | 202 AWS WAF JavaScript challenge (2.4 KB) | same failure class (was 403 CloudFront) |
| UT | jobs.utah.gov/occ/plans.html | 200 | 200 | plan located: extracted |
| VT | outside.vermont.gov .../CCDF-Plan-2025-2027-Approved.pdf | 200 application/pdf (2,962,868 B) | 200 | extracted with a heading whitelist (below) |
| VA | www.childcare.virginia.gov .../virginia-child-care-plan | 403 AkamaiGHost | 200 | plan located, impersonation: extracted |
| IN | www.in.gov/fssa/carefinder/information-and-resources2/ | 200 | 200 | same page, same certified 2024-06-30 file (7,742,708 B, Last-Modified 2026-06-19): needs_review |

Hosts retried: 25 blocked rows plus IN. Hosts that now serve content: 17 of 25 (AK, CO, CT, ID, KS, KY, LA, MN, NE, NJ,
OR, RI, SC, TN, UT, VT, VA). Still failing: 8 (AS, AZ, GA, MD, MO, MP, NY, TX); each row note now ends with
"retried 2026-09-10T21:35Z from US network, same failure" plus the observed response. The first two passes' reading
(geo-restriction of the agent's earlier network) is confirmed for the 17 hosts that now answer; the remaining 8 are bot
challenges (AZ, MD, MO, NY, TX), a broken TLS chain (AS), a closed connection (GA) and a 403 (MP) that do not depend
on the client's location.

## Extraction

Same `CARS_EXTRACTION` pattern as before, except Vermont. Before extraction every candidate PDF was downloaded once and
checked: 15 are Aspose.Words CARS prints (CT is a PDFium re-save of one) and the pattern matched 41/41 labels with no
repeats; Vermont matched 83 labels (75 unique) because the plan embeds the state's child care licensing rules inside
section 5.3, whose numbered rule headings ("5.3 Managing Infectious Diseases", "5.6 Administration of Medication",
"9.1 Staff shall ...", "13.1 ...") collide with the preprint labels. `VT_EXTRACTION` (new constant in
`scripts/build_ccdf_state_plan_manifests.py`) keeps `CARS_EXTRACTION` but restricts the heading to the 41 preprint
headings, with the wrapped 2.4 heading allowed as its first line plus the existing continuation pattern; it matched
41/41 on the VT PDF and, as a control, 41/41 on the CT and AK PDFs too. No extractor code was changed.

| Jurisdiction | Version taken | Plan Status (CARS) | Pages | Source bytes | Seconds | Provisions | Coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| us-co | Initial Plan | Approved as of 2024-11-09 | 286 | 3,154,578 | 9 | 42 | complete, 0/0/0 |
| us-ct | Initial Plan | Approved as of 2024-11-09 | 219 | 2,802,777 | 6 | 42 | complete, 0/0/0 |
| us-id | Initial Plan | Approved as of 2024-11-09 | 260 | 3,034,795 | 6 | 42 | complete, 0/0/0 |
| us-ks | Initial Plan | Approved as of 2024-11-09 | 281 | 3,087,758 | 8 | 42 | complete, 0/0/0 |
| us-ky | Initial Plan | Approved as of 2024-11-09 | 281 | 3,033,014 | 6 | 42 | complete, 0/0/0 |
| us-la | Amendment 1 | Approved as of 2025-03-26 | 183 | 2,790,158 | 5 | 42 | complete, 0/0/0 |
| us-mn | Amendment 3 | Approved as of 2026-08-11 | 288 | 3,176,312 | 6 | 42 | complete, 0/0/0 |
| us-ne | Initial Plan | Approved as of 2024-11-09 | 212 | 4,338,405 | 5 | 42 | complete, 0/0/0 |
| us-nj | Initial Plan | Certified as of 2024-09-27 | 265 | 3,003,475 | 6 | 42 | complete, 0/0/0 |
| us-or | Initial Plan | Approved as of 2024-11-09 | 303 | 3,269,046 | 6 | 42 | complete, 0/0/0 |
| us-ri | Initial Plan | Approved as of 2024-11-09 | 205 | 2,892,328 | 4 | 42 | complete, 0/0/0 |
| us-sc | Initial Plan | Approved as of 2024-11-09 | 339 | 3,349,554 | 8 | 42 | complete, 0/0/0 |
| us-tn | Initial Plan | Approved as of 2024-11-09 | 241 | 2,979,215 | 7 | 42 | complete, 0/0/0 |
| us-ut | Initial Plan | Approved as of 2024-11-09 | 270 | 3,052,904 | 5 | 42 | complete, 0/0/0 |
| us-va | Initial Plan | Certified as of 2024-10-01 | 297 | 3,164,255 | 7 | 42 | complete, 0/0/0 |
| us-vt | Initial Plan | Approved as of 2024-11-09 | 229 | 2,962,868 | 5 | 42 | complete, 0/0/0 |

Coverage columns: missing / extra / duplicate citation paths. Independent check over all 44 scopes (25 first run + 3
retry 1 + 16 here), read directly from the artifacts rather than the CLI output: `coverage.complete: true`,
`provision_count` 42, `matched_count` 42 of `source_count` 42, empty `missing_from_provisions`, `extra_provisions`,
`duplicate_provision_citations` and `duplicate_source_citations`; 42 rows and 42 distinct `citation_path` values in
every JSONL; the single inventoried source file is a regular non-symlink file under
`sources/us-xx/policy/2026-09-10-ccdf-plan-fy2025-2027/`, its SHA-256 equals the inventory value, and every provision's
`source_path` is that file; smallest section body 966 characters (NH, first run), 1,308 among the 16 new scopes (OR).
Total 1,848 provisions (44 x 42).

Request options: MN and VA manifests set `request: browser_impersonation: true` (existing option; MN's plain response is
the perfdrive challenge page, which the extractor's existing PDF-vs-HTML check treats as a block before falling back;
VA's is a 403). CO uses the extractor's existing Google Drive download path from the `/file/d/<id>/view` URL the CDEC
page links (WY precedent). ID's `source_url` is the WebLink `ElectronicFile.aspx?docid=32013` endpoint that the
publisher's own document viewer (DocView id=32013, linked from the index) serves the file from.

## Index inventories for the newly taken rows

ACF index rows (unchanged, produced by the generator): each of the 16 has 2 documents on the ACF index (plan link to
the Lead Agency page or, for NJ, directly to the PDF, plus the ACF-hosted Appendix); `taken_count` 1, Appendix family
not taken. New Jersey has no separate publisher page (the ACF index links the PDF; `publisher_index_url` is the ACF
index). Publisher pages, document links by family (page-body links; site navigation excluded):

Colorado, https://cdec.colorado.gov/resources/state-plans: 24 document links (all Google Drive).

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plans (2024-27 [FFY 2025-2027], 2022-24, 2019-21) | 3 | 1 |
| Department performance plans SFY 2023-24 to 2026-27 and FY 2023-24 annual performance report | 5 | 0 |
| CDEC Strategic Plan 2023-28; Early Childhood Mental Health Strategic Plan | 2 | 0 |
| Statewide early childhood strategic plan materials (Elevating Early Childhood, At-a-Glance, Colorado Framework, plan summary; English, Spanish, Arabic) | 9 | 0 |
| Birth-through-Five Needs Assessment 2023 (English, Spanish, Arabic) | 3 | 0 |
| Market rate survey reports (2017-18, 2021-22) | 2 | 0 |

Connecticut, https://www.ctoec.org/ccdf/: 38 document links (36 files plus 2 WordPress preview links for the 2022-2024
Amendments 2 and 4).

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027: final plan, draft, implementation summaries (English, Spanish), public comment report | 5 | 1 (final) |
| 2024 Market Rate Survey and Narrow Cost Analysis reports | 2 | 0 |
| CCDF plan 2022-2024: final submitted, draft, Amendments 1-4, implementation summaries (2), cabinet presentation, public comment report | 10 | 0 |
| 2022 Market Rate Survey; 2022 Narrow Cost Analysis (family child care, center-based) | 3 | 0 |
| CCDF plan 2019-2021: initial submission, Amendments 1-7, key approaches, advisory council presentation, public comment report | 11 | 0 |
| 2018 Market Rate Survey | 1 | 0 |
| Older CCDF plans (2016-2018, 2014-2015, 2012-2013, 2010-2011, 2008-2009, 2006-2007) | 6 | 0 |

Idaho, https://healthandwelfare.idaho.gov/providers/child-care-providers/child-care-resources: 18 document links, 17
distinct (a background-check form is linked twice); all state documents are Laserfiche WebLink DocView pages.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF State Plan FY2025-2027 (DocView id=32013) | 1 | 1 |
| Aggregate child care reports; child care disaster recovery plan | 2 | 0 |
| ICCP copay chart and local market rates; market rate reports 2021, 2024 | 4 | 0 |
| Quality Progress Report 2023 | 1 | 0 |
| Licensing and background-check forms (juvenile justice records x2, daycare licensing application, ISP name-based check, fire safety inspection) | 5 | 0 |
| Safe sleep guidance (provider guide, ICCP practices, sample policy) | 3 | 0 |
| External references (Idaho SB 1060, Caring for Our Children standards) | 2 | 0 |

Kansas, https://www.dcf.ks.gov/search/Pages/SearchResults.aspx?k=CCDF%20state%20plan (publisher's own site search;
the index-linked page and its Child Care Subsidy and Child Care Providers siblings list no CCDF plan): 10 results.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027: Initial Plan, Initial Plan Approval Letter, Waiver Approval Letter | 3 | 1 (Initial Plan) |
| CCDF plan FFY 2022-2024: Amendment 4; approval letters for Amendments 2-5 | 5 | 0 |
| CCDF plan 2019-2021 Amendment 3 | 1 | 0 |
| SSBG Proposed State Plan SFY2027 | 1 | 0 |

Kentucky, https://www.chfs.ky.gov/agencies/dcbs/dcc/Pages/default.aspx: 10 document links.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027: approved plan, approved plan Appendix (state copy), preliminary draft | 3 | 1 (approved plan) |
| CCDF plan FFY 2022-2024 approved amendment | 1 | 0 |
| ACF-218 Quality Progress Reports 2022, 2023, 2024 | 3 | 0 |
| ACF-696 financial reports 2022, 2023 | 2 | 0 |
| Child Care Provider Requirements (2026-03-04) | 1 | 0 |

Louisiana, https://doe.louisiana.gov/early-childhood/early-childhood-center-directors/early-childhood-poicy-guidance
(the ACF index's louisianabelieves.com URL redirects here; "poicy" is the publisher's spelling): 113 document links,
105 distinct.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027: approved plan (Amendment 1 print), public-comment draft, public hearing agenda | 3 | 1 (approved) |
| Earlier CCDF plans: 2022-2024 approved; 2019-2021 approved and Amendments 1-4, 2019 proposed amendment, 2019-2021 presentation; 2016 state plan webinar and public hearing presentation | 10 | 0 |
| Quality Progress Reports FFY 2021-2024 | 4 | 0 |
| Market rate surveys 2017, 2020, 2023 | 3 | 0 |
| 2018 ACF-696 financial report; 2018 annual report | 2 | 0 |
| ECCE Advisory Council overview, agendas, slides, proposed policy revisions, streaming directions (2021-2024) | about 45 (8 links repeat) | 0 |
| ECCE Commission and LA B to 3 agendas, slides, legislative reports and summaries (2019-2024) | about 26 | 0 |
| ECCE Task Force agendas (2022-2023) | 5 | 0 |
| Preschool Development Grant B-5 applications (initial, renewal) | 2 | 0 |
| Other (Picard longitudinal study, Act 893 FAQs, Senate Resolution 29, SRTC calculator, 2019 roundtables, statewide webinar deck, 2017-2018 policy updates) | 7 | 0 |

Minnesota, https://dcyf.mn.gov/child-care-and-development-fund (Department of Children, Youth, and Families; the
mn.gov page the ACF index links is a meta-refresh to it): 2 document links.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027: "Amended 25-27 CCDF Plan" (round 3 amendments, Amendment 3 print) | 1 | 1 |
| Quality Progress Report FFY 2023 | 1 | 0 |

Nebraska, https://dhhs.ne.gov/Pages/Child-Care-and-Development-Fund-Plan.aspx: 5 document links.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027: approved plan | 1 | 1 |
| CCDF plan FFY 2022-2024: approved, amended copy | 2 | 0 |
| CCDF plan 2018-2021: approved, amended copy | 2 | 0 |

Oregon, https://www.oregon.gov/delc/about-us/pages/state-plans.aspx: 78 document links, 76 distinct.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027: plan, Appendix 1 (state copy), initial approval letter, Amendment 1, Amendment 1 approval letter, transitional waiver request, public comment documents (3) | 9 | 1 (plan) |
| Oregon Narrow Cost Analysis 2024 | 1 | 0 |
| CCDF plan 2022-2024: plan, Amendments 1-5, approval letters 1-5, feedback analysis (5 languages) | 16 | 0 |
| Early Learning Emergency Preparedness and Response Plan | 1 | 0 |
| CCDF plan 2019-2021: plan (linked twice), amendment approval letters (2), waiver letter | 5 | 0 |
| CCDF plan 2016-2018: plan (linked twice), revisions 1 and 3, waiver request, waiver approvals (2) | 7 | 0 |
| Older CCDF plans (2014-2015 x2, 2010-2011, 2008-2009 x2) | 5 | 0 |
| Cost of quality study (fact sheets in 5 languages, technical user guide, 2 Excel models) | 8 | 0 |
| Alternate rate-setting structure legislative report 2022 (summary, report) | 2 | 0 |
| ACF-696 financial reports FY21-FY23 (quarterly) | 12 | 0 |
| Quality Progress Reports 2018-2024 | 7 | 0 |
| Alternative rate methodology advisory committee applications (5 languages) | 5 | 0 |

Rhode Island, https://dhs.ri.gov/regulations/state-plans: 37 document links.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027 | 1 | 1 |
| CCDF plan 2022-2024: plan, Amendments 1-5, approval letters 1-5 | 11 | 0 |
| CCDF plan 2019-2021: plan, Amendments 1-6 | 7 | 0 |
| Child care Quality Progress Report FFY 2022; Child Care Emergency Preparedness Plan (rev. 2021) | 2 | 0 |
| Other DHS state plans (claims management, LIHEAP x2, healthy aging, ORS, SNAP outreach x2, SNAP disaster, SNAP E&T x3, SNAP nutrition education, WAP, TANF within WIOA) | 14 | 0 |
| Customer flyers ("Best Ways to Reach Us", "What Happens Next") | 2 | 0 |

South Carolina, https://scchildcare.org/resources/ (the ACF index's www.scchildcare.org URL redirects here): 219
document links, 202 distinct; counts marked "about" are family totals read from the link labels.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plans: FFY 2025-2027 approved; FFY 2022-2024 conditionally approved | 2 | 1 |
| Quality Progress Report 2023; 2020 market rate survey; alternative rate methodology report | 3 | 0 |
| Strategy and needs reports (Untapped Potential, ECE strategic plan, needs assessment, PDG B-5 application) | 4 | 0 |
| Emergency preparedness (templates, brochures, manual, procedures, hurricane guides, Ready Wrigley, salmonella notices) | about 17 | 0 |
| Fire safety documents (letters, procedures, forms, guides, inspection map) | about 15 | 0 |
| Child deaths and injuries report | 1 | 0 |
| ABC Quality (manuals, quality guides, policy templates, forms, nutrition and physical activity, early learning standards, toolkits, materials guides) | about 50 | 0 |
| Licensing forms (DSS forms 1081-2964, SAFE fingerprinting) | about 30 | 0 |
| Laws and regulations (Title 63, Article 7, Jessie's Law, crib standards, center/group/religious/family regulations, suggested standards, crosswalk) | about 13 | 0 |
| State advisory committee minutes 2018-2026 | about 33 | 0 |
| Child Care Scholarship Program (policy manuals vol. 36-39, fee scales, maximum payments, income standards, portal and payment guides) | about 17 | 0 |
| Provider checklists, inspection forms, FCCH and FFN policy manuals, new-hire requirements, playground handbook | about 15 | 0 |
| Health guidance (DPH exclusion handbook, measles, diarrheal illness, RSV) | 4 | 0 |
| Newsletter and sample documents | 6 | 0 |

Tennessee, https://www.tn.gov/humanservices/information-and-resources/tdhs-reports-and-information.html: 52 document links.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027: plan, Appendix 1 (state copy), transitional waiver approvals (2024-11-22, 2025-11-28) | 4 | 1 (plan) |
| TDHS annual reports FY2011-12 to FY2024-25 | 14 | 0 |
| ACF-218 Quality Progress Report FFY 2024; ACF-696 GY2023 Q1-Q4 | 5 | 0 |
| Aggregated child care data FFY 2023-2025 | 3 | 0 |
| Market rate surveys 2022-23, 2023-24, 2024-25; cost of quality care studies 2023-2025 | 6 | 0 |
| Income eligibility limits and co-pay table; state rate and QRIS bonus table | 2 | 0 |
| Other TDHS reports and studies (workforce council, APS framework, SRC, OIG, Pathways Out of Poverty, human trafficking plan, EBT photo ID, Welfare Roll to Payroll, drug testing progress reports x7, Families First studies x2, WIOA combined plan) | 18 | 0 |

Utah, https://jobs.utah.gov/occ/plans.html: 21 document links.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plans (2025-2027, 2022-2024) | 2 | 1 (2025-2027) |
| State Plan Appendix (state copy) | 1 | 0 |
| Market rate studies 2021, 2024 | 2 | 0 |
| Needs assessments (UHSCO 2025, out-of-school time 2024 with executive summary, PDG B-5 2019) | 4 | 0 |
| Child care disaster plan 2025; cost estimation model 2023 | 2 | 0 |
| Workforce bonus survey report and one-pager 2023 | 2 | 0 |
| Quality Progress Report 2024; annual report 2023 | 2 | 0 |
| ACF-696 quarterly reports (grant years 2024-2026) | 3 | 0 |
| PDG B-5 strategic plan 2019; child care access report 2020; early childhood services study 2017 | 3 | 0 |

Virginia, https://www.childcare.virginia.gov/reports-resources/administrative-program-manuals-reports-and-data/virginia-child-care-plan:
13 document links.

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027: "Virginia's Approved 2025-2027 CCDF State Plan" (Certified print), public hearing presentation | 2 | 1 (plan) |
| Earlier ACF-118 plans (2022-2024, 2019-2021, 2016-2018, 2014-2015) | 4 | 0 |
| Quality Progress Reports (submitted 2024; ACF-218 FFY 2018-2023) | 7 | 0 |

Vermont, https://dcf.vermont.gov/CDD/CCDF: 12 document links (files on outside.vermont.gov).

| Family | Count | Taken |
| --- | --- | --- |
| CCDF plan FFY 2025-2027: approved plan, Amendment 1 approval letter, draft | 3 | 1 (approved) |
| Child Care Market Rate Survey 2024 | 1 | 0 |
| CCDF plan 2022-2024: plan, Amendments 1-7 | 8 | 0 |

Alaska (needs_review), https://aws.state.ak.us/OnlinePublicNotices/Notices/View.aspx?id=215530: 1 attachment,
"2025-2027 CCDF State Plan 052424.pdf" (213 pages, Microsoft Word export created 2024-05-24, no CARS Plan Status line,
text refers to "this draft CCDF Plan" and to the public comment period); the Department of Health Child Care Program
Office page lists no CCDF plan document. Taken: 0.

## Reviewer judgments

1. Alaska: the only FFY 2025-2027 document the Lead Agency posts is the 2024-05-24 Word draft attached to the
   public-comment notice the ACF index links; it carries no certification or approval and describes itself as a
   draft. Following the Puerto Rico precedent (draft only), the row moves to `needs_review` rather than being
   extracted, although the 41-label pattern would have matched it.
2. Version choices follow the first run's rule. Initial approved plan where posted (CO, CT, ID, KS, KY, NE, OR, RI,
   SC, TN, UT, VT); the certified submission where no approval print is posted (NJ, VA: VA's page labels the
   certified print "Approved"); the only posted consolidated amendment where that is all the state posts (LA
   Amendment 1, approved 2025-03-26; MN Amendment 3, approved 2026-08-11). Separately posted amendments, approval
   letters, appendices and drafts are inventoried and not taken. expression_date stays 2024-10-01 for all.
3. Kansas source: the page the ACF index links carries no CCDF plan link and neither do its sibling pages; the plan
   was located with the publisher's own site search (same approach as MS and VI in retry 1). `publisher_index_url`
   is that search-results URL because no DCF page listing the file was found without crawling; a reviewer may prefer
   to record a listing page if one exists.
4. Idaho source: the index links a Laserfiche WebLink viewer page; `source_url` is the viewer's own
   `ElectronicFile.aspx` endpoint on the same host and repository, which is how the viewer delivers the file. This is
   the publisher's URL, not a mirror.
5. Vermont: `VT_EXTRACTION` restricts headings to the 41 preprint headings because the embedded licensing rules reuse
   the same "N.N Heading" form. It is a manifest-level pattern (like the IL heading whitelist); no extractor function
   changed. The rule text remains inside the 5.3 provision body, as the first run's convention keeps sub-subsections
   inside their parent.
6. Connecticut is fetched with plain requests only: on this network the publisher answers a plain browser-UA request
   with 200 but a curl_cffi chrome impersonation with 403, the reverse of the usual pattern, so no impersonation flag
   is set.
7. Minnesota and Virginia use the existing `browser_impersonation` option; for MN the plain response is a perfdrive
   challenge page (HTML where a PDF is declared), which the extractor's existing check treats as a block before the
   impersonation fallback. The dcyf.mn.gov chain that failed curl_cffi verification in retry 1 verified cleanly this
   pass; nothing was disabled.
8. Louisiana's `publisher_index_url` is the doe.louisiana.gov page the ACF index's louisianabelieves.com link
   redirects to (final URL recorded, including the publisher's "poicy" spelling); the queue's `index_plan_link` keeps
   the ACF value.
9. The 8 still-blocked rows: AZ, MD, MO, NY and TX answer with bot challenges (cloudflare, Drupal antibot + Incapsula,
   F5/Shape TSPD, AWS WAF), AS presents a self-signed expired certificate, GA closes the connection, MP returns 403
   nginx; none is location-dependent on the evidence here. Each was probed once plain and once impersonated at 20 s;
   row notes record the exact response. Nothing was worked around.
10. Indiana: same page and same certified 2024-06-30 file as before (byte count and Last-Modified unchanged); stays
    `needs_review` for the non-conforming document. `IN_MANUAL_NOTE` now says "8 jurisdictions blocked, 4
    needs_review after the 2026-09-10 second retry"; the CCDF Policy Manual row stays `needs_review` because the plan
    family is still incomplete.
11. The work order named 23 blocked rows; the queue held 25 (retry 1 kept all 25 blocked). All 25 were retried.
12. Queue row fields keep the first run's schema (`index_url`, `index_document_count` describe the ACF index row;
    `taken_count` 1); publisher-page inventories by family live in this note. The shared row-note template
    ("located on the Lead Agency page linked from the ACF index") is unchanged for the reasons given in retry 1; the
    `plan_status` text inside each new note records where the plan was actually found.
13. GitNexus MCP tools were unavailable in this session, so no impact analysis was run. No existing function was
    modified: the diff to `scripts/build_ccdf_state_plan_manifests.py` touches the module docstring, the
    `RESOLUTIONS` and `IN_MANUAL_NOTE` constants, and adds the `VT_EXTRACTION` constant. Before any edit the generator
    was re-run against the committed script and the 28 existing manifests were byte-identical after this run as well
    (`git status` shows only the queue, the script and 16 new manifests).

## Artifacts (unsigned, uncommitted, shared corpus root `/Users/pavelmakarchuk/axiom-corpus/data/corpus`)

For each of `us-co`, `us-ct`, `us-id`, `us-ks`, `us-ky`, `us-la`, `us-mn`, `us-ne`, `us-nj`, `us-or`, `us-ri`,
`us-sc`, `us-tn`, `us-ut`, `us-va`, `us-vt`:

- `sources/us-xx/policy/2026-09-10-ccdf-plan-fy2025-2027/official-documents/us-xx-acf-ccdf-plan-fy2025-2027.pdf`
- `inventory/us-xx/policy/2026-09-10-ccdf-plan-fy2025-2027.json`
- `provisions/us-xx/policy/2026-09-10-ccdf-plan-fy2025-2027.jsonl`
- `coverage/us-xx/policy/2026-09-10-ccdf-plan-fy2025-2027.json`

Committed: 16 new `manifests/us-xx-ccdf-state-plan-fy2025-2027.yaml`, `manifests/ccdf-agent-queue.yaml`
(status_counts: agent_ready 44, blocked_primary_source 8, needs_review 6: us, us-ak, us-in plan, us-pr, us-vi, us-in
manual), `scripts/build_ccdf_state_plan_manifests.py`, this note. No certificate changes
(`data/certs/ccdf-ca-bundle.pem` remains generated and ignored; no new intermediate was needed).

## Rebuild

```bash
uv run python scripts/build_ccdf_state_plan_manifests.py
export REQUESTS_CA_BUNDLE=$PWD/data/certs/ccdf-ca-bundle.pem
for j in co ct id ks ky la mn ne nj or ri sc tn ut va vt; do
  uv run axiom-corpus-ingest extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-ccdf-plan-fy2025-2027 \
    --manifest manifests/us-$j-ccdf-state-plan-fy2025-2027.yaml --source-as-of 2026-09-10 --expression-date 2024-10-01
done
```

## Lint and tests

`uv run ruff check scripts/build_ccdf_state_plan_manifests.py`: passes.
`uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 2 skipped, 10 failed. The 10 failures are the known sparse-worktree `data/corpus` absences (BE rulespec
promotion, NY TANF compatibility x2, BE source promotion, AK/CT/MI/MT/ND/NY SNAP manuals); none touches CCDF code or
manifests.

## Remaining

Controller: `sign-ingest-manifest` for the 44 scopes, immutable release selector, `publish_corpus.py --dry-run`,
publish. AS, AZ, GA, MD, MO, MP, NY, TX need the publishers' cooperation (bot challenges, a broken TLS chain, a closed
connection); AK, IN, PR and VI need the publisher to post an approved or certified FFY 2025-2027 plan. Decide whether
the Appendix family, the amendments, and 45 CFR 98 get their own runs.
