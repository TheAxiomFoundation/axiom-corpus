"""Build one corpus manifest per state for the state-published TANF State Plan (42 U.S.C.
602(a)) and record the family on the TANF agent queue rows.

Work order: docs/coverage/needs-closure-2026-09-11/tanf.md, element tanf-s32 (state TANF plan as
a certified document): 49 of the 51 jurisdictions had no plan in the corpus (AL and NY do). ACF
OFA posts no consolidated plan index (checked 2026-09-10 and again 2026-09-13: the OFA program
page and the acf.gov resource library carry no state plan links), so every plan was located on the
state agency's own site on 2026-09-13 (agency TANF page, "state plans" or "reports" page, or the
agency's own site search) and that review is frozen in RESOLUTIONS below.

Conventions follow the Guam precedent (manifests/us-gu-tanf-state-policy-manual.yaml, version
2026-09-11-tanf-territory-state-plan): document_class ``policy``, citation path
``us-xx/policy/acf/tanf-plan/<plan period>``, page-level PDF extraction (one provision per page
plus the document root), ``ocr: true`` for the one scanned plan (SD), the publisher's HTML page
for Illinois. Version ``2026-09-13-tanf-state-plan``; ``expression_date`` is the plan's stated
effective date.

Rules applied: the state's currently posted certified/approved plan is taken; a plan the state
posts only as a public-comment draft is not (AK CCDF precedent, 2026-09-10 run) and is recorded;
where the agency's index page does not list the file but the agency hosts it, the row says so;
publisher blocks are recorded and never worked around. TLS: humanservices.arkansas.gov omits its
Sectigo intermediate (the same one dese.ade.arkansas.gov omits); extraction runs with
REQUESTS_CA_BUNDLE = certifi + data/certs/sectigo-public-server-authentication-ca-ov-r36.pem.

    uv run python scripts/build_tanf_state_plan_manifests.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import certifi
import yaml

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "manifests" / "tanf-agent-queue.yaml"
INTERMEDIATE = ROOT / "data" / "certs" / "sectigo-public-server-authentication-ca-ov-r36.pem"
BUNDLE = ROOT / "data" / "certs" / "tanf-state-plan-ca-bundle.pem"
SOURCE_AS_OF = "2026-09-13"
VERSION = f"{SOURCE_AS_OF}-tanf-state-plan"
FAMILY = "tanf_state_plan"
OFA_NOTE = (
    "ACF OFA posts no state plan index (acf.gov/ofa/programs/tanf and the resource library carry no plan links, "
    "checked 2026-09-10 and 2026-09-13); the plan is the state agency's own publication"
)

NAMES = {
    "ak": "Alaska", "ar": "Arkansas", "az": "Arizona", "ca": "California", "co": "Colorado",
    "ct": "Connecticut", "dc": "District of Columbia", "de": "Delaware", "fl": "Florida",
    "ga": "Georgia", "hi": "Hawaii", "ia": "Iowa", "id": "Idaho", "il": "Illinois", "in": "Indiana",
    "ks": "Kansas", "ky": "Kentucky", "la": "Louisiana", "ma": "Massachusetts", "md": "Maryland",
    "me": "Maine", "mi": "Michigan", "mn": "Minnesota", "mo": "Missouri", "ms": "Mississippi",
    "mt": "Montana", "nc": "North Carolina", "nd": "North Dakota", "ne": "Nebraska",
    "nh": "New Hampshire", "nj": "New Jersey", "nm": "New Mexico", "nv": "Nevada", "oh": "Ohio",
    "ok": "Oklahoma", "or": "Oregon", "pa": "Pennsylvania", "ri": "Rhode Island",
    "sc": "South Carolina", "sd": "South Dakota", "tn": "Tennessee", "tx": "Texas", "ut": "Utah",
    "va": "Virginia", "vt": "Vermont", "wa": "Washington", "wi": "Wisconsin", "wv": "West Virginia",
    "wy": "Wyoming",
}

# taken rows: index (the agency page read), listed (True when that page links the file), docs =
# [(suffix or None, url, title, extra)], period (citation segment), effective (expression_date),
# agency, status (plan_status text), optional impersonation / tls / note.
# not taken rows: status in {blocked_primary_source, needs_review}, index, reason.
RESOLUTIONS: dict[str, dict] = {
    "ak": {"status": "agent_ready", "index": "https://health.alaska.gov/en/services/alaska-temporary-assistance/", "listed": True,
           "period": "2026-2028", "effective": "2025-12-31", "agency": "Alaska Department of Health, Division of Public Assistance (Alaska Temporary Assistance Program)",
           "plan_status": "Alaska TANF State Plan 2026-2028, plan effective December 31, 2025 (Office of the Governor and Department of Health)",
           "docs": [(None, "https://health.alaska.gov/media/hgja52sa/alaska-tanf-state-plan-2026-2028.pdf", "Alaska TANF State Plan 2026-2028", {})]},
    "ar": {"status": "agent_ready", "index": "https://humanservices.arkansas.gov/divisions-shared-services/county-operations/temporary-assistance-for-needy-families/", "listed": False,
           "period": "2023", "effective": "2023-03-15", "agency": "Arkansas Department of Human Services (TANF program transferred to the Division of Workforce Services)",
           "plan_status": "Arkansas State Plan for Title IV-A, signed 2023 (DWS signature copy); the DWS site posts the same 45-page plan as AR-TANF-State-Plan-03152023-CLEAN.pdf",
           "tls": True,
           "note": "humanservices.arkansas.gov and dws.arkansas.gov answer every page request with HTTP 403 (WAF) to plain and browser clients while serving the PDF itself with HTTP 200; the plan was located with a web search and its listing page could not be read. Both hosts omit the Sectigo Public Server Authentication CA OV R36 intermediate; REQUESTS_CA_BUNDLE = certifi + data/certs/sectigo-public-server-authentication-ca-ov-r36.pem, no verification disabled.",
           "docs": [(None, "https://humanservices.arkansas.gov/wp-content/uploads/TANF-State-Plan-2023-Signed-DWS.pdf", "Arkansas TANF State Plan (Title IV-A), signed 2023", {})]},
    "az": {"status": "blocked_primary_source", "index": "https://des.az.gov/services/basic-needs/cash-assistance-ca",
           "reason": "des.az.gov answers the TANF State Plan PDF (https://des.az.gov/sites/default/files/dl/tanf_state_plan_oct_2026.pdf, 'State of Arizona TANF State Plan', October 2026 per the search index) and the Cash Assistance pages with HTTP 403 cloudflare 'Just a moment' challenges for plain and browser-impersonated clients (2026-09-13), the same wall the CCDF run recorded"},
    "ca": {"status": "agent_ready", "index": "https://www.cdss.ca.gov/inforesources/data-portal/state-plans/tanf-state-plan", "listed": True,
           "period": "2022", "effective": "2022-10-01", "agency": "California Department of Social Services (CalWORKs)",
           "plan_status": "ACF Approved TANF State Plan 2022, effective October 1, 2022 (the newest plan the CDSS TANF State Plan page posts; the 2019 plan and addendum are also listed)",
           "docs": [(None, "https://www.cdss.ca.gov/Portals/9/DSSDB/acf-approved-tanf-state-plan-2022.pdf", "California TANF State Plan (ACF approved 2022)", {})]},
    "co": {"status": "agent_ready", "index": "https://cdhs.colorado.gov/colorado-works", "listed": True,
           "period": "2018", "effective": "2018-07-01", "agency": "Colorado Department of Human Services (Colorado Works)",
           "plan_status": "Colorado State Plan TANF effective July 1, 2018: the newest TANF State Plan the Colorado Works page links (2018, 2015, 2012, 2009, all on Google Drive); later renewals are not posted",
           "docs": [(None, "https://drive.google.com/open?id=1eP8saG82zJe141J7s5wpAPAvtyNwzJbc", "Colorado TANF State Plan, effective July 1, 2018",
                     {"download_url": "https://drive.google.com/uc?export=download&id=1eP8saG82zJe141J7s5wpAPAvtyNwzJbc"})]},
    "ct": {"status": "agent_ready", "index": "https://portal.ct.gov/dss/knowledge-base/articles/state-plans-and-federal-reports/tanf-state-plans-and-federal-reports", "listed": True,
           "period": "fy2024-2026", "effective": "2023-10-01", "agency": "Connecticut Department of Social Services",
           "plan_status": "CT TANF State Plan FFY 2024-2026 (October 1, 2023 through September 30, 2026), 4/15/24 amendment print",
           "docs": [(None, "https://portal.ct.gov/dss/-/media/departments-and-agencies/dss/state-plans-and-federal-reports/tanf-state-plan/ct-tanf-state-plan-2024---2026---41524-amendment.pdf", "Connecticut TANF State Plan FFY 2024-2026", {})]},
    "dc": {"status": "agent_ready", "index": "https://dhs.dc.gov/service/temporary-cash-assistance-needy-families-tanf", "listed": True,
           "period": "2023", "effective": "2023-10-01", "agency": "District of Columbia Department of Human Services",
           "plan_status": "2023 District of Columbia State Plan for Administration of the TANF Block Grant, effective October 1, 2023",
           "docs": [(None, "https://dhs.dc.gov/sites/default/files/dc/sites/dhs/service_content/attachments/DC%20TANF%20State%20Plan_Oct-2023.pdf", "District of Columbia TANF State Plan, effective October 1, 2023", {})]},
    "de": {"status": "agent_ready", "index": "https://dhss.delaware.gov/dss/division-of-social-services/forms-and-publications/", "listed": True,
           "period": "fy2024-2026", "effective": "2023-10-01", "agency": "Delaware Department of Health and Social Services, Division of Social Services",
           "plan_status": "Delaware TANF State Plan 10-1-23 to 09-30-26 (listed as 'Delaware TANF State Plan 2023-2026 (PUBLIC NOTICE)')",
           "docs": [(None, "https://dhss.delaware.gov/wp-content/uploads/sites/2/2026/06/Delaware-TANF-State-Plan-2023-2026.pdf", "Delaware TANF State Plan, October 1, 2023 to September 30, 2026", {})]},
    "fl": {"status": "agent_ready", "index": "https://www.myflfamilies.com/services/public-assistance/temporary-cash-assistance", "listed": True,
           "period": "2026-2028", "effective": "2026-07-01", "agency": "Florida Department of Children and Families",
           "plan_status": "Florida TANF State Plan 2026-2028 (effective July 1, 2026)",
           "docs": [(None, "https://www.myflfamilies.com/documents/Florida%20TANF%20State%20Plan%202026-2028.pdf", "Florida TANF State Plan 2026-2028", {})]},
    "ga": {"status": "agent_ready", "index": "https://dfcs.georgia.gov/services/temporary-assistance-needy-families", "listed": True,
           "period": "fy2026", "effective": "2026-01-01", "agency": "Georgia Department of Human Services, Division of Family and Children Services",
           "plan_status": "Georgia's TANF State Plan Renewal FY2026, effective January 2026 (the earlier 'draft' renewal file is also posted, not taken)",
           "docs": [(None, "https://dfcs.georgia.gov/document/document/georgias-tanf-state-plan-renewal-fy2026pdf/download", "Georgia TANF State Plan Renewal FY2026", {})]},
    "hi": {"status": "agent_ready", "index": "https://humanservices.hawaii.gov/tanf-strategic-plans/", "listed": True,
           "period": "2023", "effective": "2023-10-01", "agency": "Hawaii Department of Human Services, Benefit, Employment and Support Services Division",
           "plan_status": "Hawaii TANF State Plan effective October 1, 2023 (signed, certified); a plan 'Effective 2025Oct01, Certified 2025Dec23' is in the search index but its URL answers HTTP 404 and the TANF Strategic Plans page does not list it",
           "docs": [(None, "https://humanservices.hawaii.gov/wp-content/uploads/2024/12/Hawaii_TANF_State_Plan_Signed_Certified-Eff_20231001.pdf", "Hawaii TANF State Plan, effective October 1, 2023", {})]},
    "ia": {"status": "agent_ready", "index": "https://hhs.iowa.gov/assistance-programs/cash-assistance/tanf", "listed": True,
           "period": "fy2026-2028", "effective": "2025-10-01", "agency": "Iowa Department of Health and Human Services (Family Investment Program)",
           "plan_status": "Iowa's TANF State Plan, effective October 1, 2025 - September 30, 2028, with its attachments volume",
           "docs": [(None, "https://hhs.iowa.gov/media/17445/download?inline", "Iowa TANF State Plan FFY 2026-2028", {}),
                    ("attachments", "https://hhs.iowa.gov/media/17446/download?inline", "Iowa TANF State Plan FFY 2026-2028: Attachments", {})]},
    "id": {"status": "agent_ready", "index": "https://healthandwelfare.idaho.gov/services-programs/financial-assistance/about-tafi", "listed": True,
           "period": "fy2026-2028", "effective": "2025-10-01", "agency": "Idaho Department of Health and Welfare (Temporary Assistance for Families in Idaho)",
           "plan_status": "Idaho State Plan Renewal for TANF FY2026-FY2028, effective October 1, 2025 (Laserfiche WebLink DocView id=35475, served by the repository's ElectronicFile endpoint)",
           "docs": [(None, "https://publicdocuments.dhw.idaho.gov/WebLink/ElectronicFile.aspx?docid=35475&dbid=0&repo=PUBLIC-DOCUMENTS", "Idaho TANF State Plan Renewal FY2026-FY2028", {})]},
    "il": {"status": "agent_ready", "index": "https://www.dhs.state.il.us/page.aspx?item=56061", "listed": True,
           "period": "2023-2025", "effective": "2023-01-01", "agency": "Illinois Department of Human Services",
           "plan_status": "TANF State Plan for January 1, 2023 - June 30, 2025, published as an HTML page (the newest approved plan; the 01/01/2026 renewal is posted only as a public-comment draft PDF, not taken)",
           "docs": [(None, "https://www.dhs.state.il.us/page.aspx?item=172771", "Illinois TANF State Plan, January 1, 2023 - June 30, 2025",
                     {"source_format": "html", "extraction": {"html_content_selector": "#ItemContentDiv"}})]},
    "in": {"status": "needs_review", "index": "https://www.in.gov/fssa/dfr/tanf-cash-assistance/about-tanf/",
           "reason": "the DFR page posts the '2026 TANF State Plan - Renewal Draft' for public comment (to 2025-12-20) and an undated 'Indiana TANF State Plan amendment' (WIOA combined-plan TANF section text, 18 pages); no certified or approved current plan is posted"},
    "ks": {"status": "agent_ready", "index": "https://www.dcf.ks.gov/search/Pages/SearchResults.aspx?k=TANF%20state%20plan", "listed": False,
           "period": "fy2024-2026", "effective": "2023-10-01", "agency": "Kansas Department for Children and Families",
           "plan_status": "State of Kansas TANF State Plan effective October 1, 2023 - September 30, 2026; the DCF site search lists the 'TANF State Plan completion letter' and the EES pages list no plan, so the file was located with a web search on the same host",
           "docs": [(None, "https://www.dcf.ks.gov/services/ees/Documents/Reports/TANF%20State%20Plan%20FFY%202024%20-%202026.pdf", "Kansas TANF State Plan FFY 2024-2026", {})]},
    "ky": {"status": "agent_ready", "index": "https://www.chfs.ky.gov/agencies/dcbs/dfs/fssb/Pages/default.aspx", "listed": True,
           "period": "fy2024-2026", "effective": "2023-10-01", "agency": "Kentucky Cabinet for Health and Family Services, Department for Community Based Services",
           "plan_status": "Kentucky TANF State Plan 2023 (10/1/2023-09/30/2026, DocuSign copy)",
           "docs": [(None, "https://www.chfs.ky.gov/agencies/dcbs/dfs/fssb/Documents/Kentucky%20TANF%20State%20Plan%202023.pdf", "Kentucky TANF State Plan, October 1, 2023 - September 30, 2026", {})]},
    "ma": {"status": "agent_ready", "index": "https://www.mass.gov/doc/tanf-massachusetts-state-plan-2024-pdf", "listed": True,
           "period": "2024", "effective": "2024-10-01", "agency": "Massachusetts Department of Transitional Assistance",
           "plan_status": "TANF Massachusetts State Plan 2024 (renewal; the document states no effective date, FFY 2025 start assumed for expression_date)",
           "impersonation": True,
           "docs": [(None, "https://www.mass.gov/doc/tanf-massachusetts-state-plan-2024-pdf/download", "Massachusetts TANF State Plan 2024", {})]},
    "md": {"status": "needs_review", "index": "https://dhs.maryland.gov/business-center/documents/fia/",
           "reason": "the FIA documents page's 'State Plans' folder holds the SNAP E&T FY25 plan and a 2017 web capture of the WIOA State Plan; the Temporary Cash Assistance page links no plan; no current TANF state plan is posted (the plan is part of Maryland's WIOA combined plan filed on the federal portal)"},
    "me": {"status": "agent_ready", "index": "https://www.maine.gov/dhhs/ofi/about-us/data-reports", "listed": True,
           "period": "2024-2026", "effective": "2024-01-01", "agency": "Maine Department of Health and Human Services, Office for Family Independence",
           "plan_status": "Maine TANF State Plan (signed) 2024-2026, effective January 1, 2024 (Data and Reports page, 'Other Reports and Analysis')",
           "docs": [(None, "https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/inline-files/Maine%20TANF%20State%20Plan%20%28signed%29%202024-26.pdf", "Maine TANF State Plan 2024-2026 (signed)", {})]},
    "mi": {"status": "agent_ready", "index": "https://www.michigan.gov/mdhhs/inside-mdhhs/state-plans-and-amendments", "listed": True,
           "period": "2026", "effective": "2026-01-01", "agency": "Michigan Department of Health and Human Services (Family Independence Program)",
           "plan_status": "TANF State Plan Effective January 1, 2026 (the 2023 plan and its 2024/2025 revisions are also listed)",
           "docs": [(None, "https://www.michigan.gov/mdhhs/-/media/Project/Websites/mdhhs/Inside-MDHHS/Reports-and-Statistics---Human-Services/State-Plans-and-Federal-Regulations/TANF_State_Plan_Effective_01-01-26.pdf", "Michigan TANF State Plan, effective January 1, 2026", {})]},
    "mn": {"status": "blocked_primary_source", "index": "https://dcyf.mn.gov/economic-assistance/minnesota-family-investment-program",
           "reason": "dcyf.mn.gov (Lead Agency since 2025) redirects plain clients to the validate.perfdrive.com bot challenge and refused the curl_cffi impersonated TLS handshake on 2026-09-13; the legacy mn.gov/dhs MFIP pages answer 404; Minnesota's TANF plan is the MFIP section of the WIOA combined plan (federal portal), not a state-hosted document reachable here"},
    "mo": {"status": "needs_review", "index": "https://dss.mo.gov/fsd/tanfstplan.htm",
           "reason": "the DSS 'What is the TANF State Plan?' page indexed by search engines (FFY 2026-2027 modifications, comments through 2026-01-09) answers HTTP 404, as do dss.mo.gov/fsd/pdf/mo-tanf-plan-ffy2021-2023.pdf, tanf-wioa-2024-2027.pdf and the Temporary Assistance pages' plan paths (2026-09-13); no plan is reachable on the publisher's site"},
    "ms": {"status": "agent_ready", "index": "https://www.mdhs.ms.gov/reports/plans/", "listed": True,
           "period": "2020", "effective": "2020-07-01", "agency": "Mississippi Department of Human Services, Division of Economic Assistance (filed with the Secretary of State as Title 18 Part 19)",
           "plan_status": "TANF State Plan (Economic Assistance) as filed in the Mississippi Administrative Code, Title 18 Part 19 (period beginning July 1, 2020); the MDHS State Plans page links the Secretary of State copy",
           "impersonation": True,
           "docs": [(None, "https://www.sos.ms.gov/adminsearch/ACCode/00000566c.pdf", "Mississippi TANF State Plan (Title 18 Part 19, Division of Economic Assistance)", {})]},
    "mt": {"status": "agent_ready", "index": "https://dphhs.mt.gov/hcsd/Manuals/TANFpolicymanual", "listed": True,
           "period": "2024-2026", "effective": "2024-01-01", "agency": "Montana Department of Public Health and Human Services, Human and Community Services Division",
           "plan_status": "TANF State Plan 1/2024-12/2026 (effective January 1, 2024 to December 31, 2026), listed on the TANF Policy Manual page",
           "impersonation": True,
           "docs": [(None, "https://dphhs.mt.gov/assets/hcsd/TANF/TANFStatePlan.pdf", "Montana TANF State Plan, January 1, 2024 to December 31, 2026", {})]},
    "nc": {"status": "agent_ready", "index": "https://www.ncdhhs.gov/divisions/social-services/publications/temporary-assistance-needy-families-state-plan", "listed": False,
           "period": "fy2026-2028", "effective": "2025-10-01", "agency": "North Carolina Department of Health and Human Services, Division of Social Services (Work First)",
           "plan_status": "North Carolina TANF State Plan FFY 2026-FFY 2028 (effective October 1, 2025 - September 30, 2028), hosted at ncdhhs.gov/2026-2028-tanf-state-plan-162026; the publications page still lists only the 2022-2025 signed plan",
           "docs": [(None, "https://ncdhhs.gov/2026-2028-tanf-state-plan-162026/download?attachment=", "North Carolina TANF State Plan FFY 2026-2028 (Work First)", {})]},
    "nd": {"status": "needs_review", "index": "https://www.hhs.nd.gov/applyforhelp/tanf",
           "reason": "the TANF page links no plan; the two plan files search engines index (draft-2022-ND-TANF-State-Plan.pdf, EA/draft-tanf-state-plan-2025.pdf) are public-comment drafts and the 2025 one answers HTTP 404 (2026-09-13); no certified plan is posted"},
    "ne": {"status": "agent_ready", "index": "https://dhhs.ne.gov/Pages/TANF.aspx", "listed": False,
           "period": "2024", "effective": "2024-01-01", "agency": "Nebraska Department of Health and Human Services (Aid to Dependent Children)",
           "plan_status": "Nebraska State TANF Plan 2024 (WIOA combined state plan TANF section, year 2024), hosted at dhhs.ne.gov/Documents; the TANF page lists the Work Verification Plan and the 2025 TANF Expenditure Plan but not this file; the '2026 WIOA Nebraska State Plan Modification for TANF' URL answers 404",
           "docs": [(None, "https://dhhs.ne.gov/Documents/Nebraska-State-TANF-Plan-2024.pdf", "Nebraska State TANF Plan 2024", {})]},
    "nh": {"status": "agent_ready", "index": "https://www.dhhs.nh.gov/temporary-assistance-needy-families-tanf", "listed": True,
           "period": "2023", "effective": "2023-10-01", "agency": "New Hampshire Department of Health and Human Services",
           "plan_status": "TANF State Plan Renewal October 2023 (effective October 1, 2023)",
           "impersonation": True,
           "docs": [(None, "https://www.dhhs.nh.gov/sites/g/files/ehbemt476/files/documents2/tanf-state-plan.pdf", "New Hampshire TANF State Plan, effective October 1, 2023", {})]},
    "nj": {"status": "needs_review", "index": "https://nj.gov/humanservices/wfnj/",
           "reason": "the Work First New Jersey and DFD pages link no plan; the only plan files on nj.gov are public-comment drafts under providers/grants/public/publicnoticefiles (FFY 2018-2020, FFY 2021-2023, FFY 2024-2026), and the FFY 2024-2026 draft URL answers HTTP 404 (2026-09-13)"},
    "nm": {"status": "agent_ready", "index": "https://www.hca.nm.gov/income-support-division-plans-and-reports/", "listed": True,
           "period": "fy2024-2026", "effective": "2024-07-01", "agency": "New Mexico Health Care Authority, Income Support Division (NM Works)",
           "plan_status": "FFY 2024-2026 Final TANF State Plan (July 2024; period July 1, 2024 through June 30, 2026)",
           "docs": [(None, "https://www.hca.nm.gov/wp-content/uploads/TANF-Final-State-Plan-2024-to-2026.pdf", "New Mexico TANF State Plan FFY 2024-2026 (final)", {})]},
    "nv": {"status": "agent_ready", "index": "https://www.dss.nv.gov/programs/tanf/documents-and-links/", "listed": True,
           "period": "fy2024", "effective": "2023-12-31", "agency": "Nevada Department of Health and Human Services, Division of Welfare and Supportive Services",
           "plan_status": "FFY24 Nevada TANF State Plan, effective December 31, 2023 (final)",
           "docs": [(None, "https://www.dss.nv.gov/uploadedFiles/dwssnvgov/content/TANF/FFY24%20Nevada%20TANF%20State%20Plan.%20effective%2012.31.23%20FINAL.pdf", "Nevada TANF State Plan FFY 2024, effective December 31, 2023", {})]},
    "oh": {"status": "agent_ready", "index": "https://jfs.ohio.gov/public-assistance/cash-assistance", "listed": False,
           "period": "2024", "effective": "2024-10-01", "agency": "Ohio Department of Job and Family Services (Ohio Works First)",
           "plan_status": "2024 TANF State Plan Combined (State Title IV-A Plan submitted under 42 U.S.C. 602; the print says 'Effective Date: TBD'), hosted on the ODJFS asset host; the Cash Assistance page links no plan, located with a web search; expression_date is the FFY 2025 start and should be reviewed",
           "docs": [(None, "https://dam.assets.ohio.gov/image/upload/jfs.ohio.gov/OWF/tanf/2024%20TANF%20State%20Plan%20Combined.pdf", "Ohio TANF State Title IV-A Plan, 2024 combined print", {})]},
    "ok": {"status": "agent_ready", "index": "https://oklahoma.gov/okdhs/services/tanf/tanfhome.html", "listed": True,
           "period": "2023", "effective": "2023-12-01", "agency": "Oklahoma Human Services (Adult and Family Services)",
           "plan_status": "TANF State Plan (2023 renewal effective December 1, 2023, with the August 1, 2024 transmittal letter to ACF OFA)",
           "docs": [(None, "https://oklahoma.gov/content/dam/ok/en/okdhs/documents/okdhs-pdf-library/adult-and-family-services/OklahomaTANFPlan.pdf", "Oklahoma TANF State Plan (2023 renewal, August 2024 print)", {})]},
    "or": {"status": "needs_review", "index": "https://www.oregon.gov/odhs/cash/pages/tanf.aspx",
           "reason": "the ODHS TANF Cash Benefits page links no plan and the FFY 2023 plan URL search engines index (odhs/data/sspdata/2022-10-01-tanf-state-plan-fy23.pdf) answers HTTP 404 (2026-09-13); the ODHS data page (odhs/data/pages/ssp.aspx) answers 404; no current plan is posted"},
    "pa": {"status": "agent_ready", "index": "https://www.pa.gov/agencies/dhs/resources/cash-assistance/tanf/tanf-state-plan", "listed": True,
           "period": "2024", "effective": "2024-10-01", "agency": "Pennsylvania Department of Human Services",
           "plan_status": "2024 Pennsylvania TANF State Plan, effective October 1, 2024 (submitted to HHS December 2024)",
           "docs": [(None, "https://www.pa.gov/content/dam/copapwp-pagov/en/dhs/documents/services/assistance/documents/tanf/tanf-state-plan-effective-october-1-2024.pdf", "Pennsylvania TANF State Plan, effective October 1, 2024", {})]},
    "ri": {"status": "needs_review", "index": "https://dhs.ri.gov/regulations/state-plans",
           "reason": "the DHS State Plans page's 'TANF state plan within WIOA plan' link (media/2731) is the 180-page WIOA Policy Manual (State, updated 03/18/2021), which mentions TANF eleven times and carries no TANF plan text; the RI Works page links no plan; no TANF state plan is posted"},
    "sc": {"status": "agent_ready", "index": "https://dss.sc.gov/assistance-programs/tanf/", "listed": False,
           "period": "2025", "effective": "2025-10-01", "agency": "South Carolina Department of Social Services",
           "plan_status": "South Carolina TANF State Plan December 2025 (effective October 2025), hosted on dss.sc.gov; the TANF program and TANF data pages do not list it (located with a web search)",
           "docs": [(None, "https://dss.sc.gov/media/ebfb3wuo/sc-tanf-state-plan-12-2025.pdf", "South Carolina TANF State Plan, December 2025", {})]},
    "sd": {"status": "agent_ready", "index": "https://dss.sd.gov/economicassistance/tanf.aspx", "listed": True,
           "period": "fy2024-2026", "effective": "2023-10-01", "agency": "South Dakota Department of Social Services",
           "plan_status": "South Dakota State Plan for TANF effective October 1, 2023 through September 30, 2026 (scanned image-only PDF, 21 pages; Tesseract page OCR)",
           "docs": [(None, "https://dss.sd.gov/docs/economicassistance/tanf/TANFStatePlan.pdf", "South Dakota TANF State Plan, October 1, 2023 - September 30, 2026", {"extraction": {"ocr": True}})]},
    "tn": {"status": "agent_ready", "index": "https://www.tn.gov/humanservices/for-families/families-first-tanf.html", "listed": True,
           "period": "2024", "effective": "2024-07-01", "agency": "Tennessee Department of Human Services (Families First)",
           "plan_status": "TANF State Plan 2024, signed 7/2/2024 (WIOA combined state plan TANF program-specific requirements, effective July 1, 2024)",
           "docs": [(None, "https://www.tn.gov/content/dam/tn/human-services/documents/TANF%20State%20Plan%202024%20Signed%207.2.2024.pdf", "Tennessee TANF State Plan 2024 (signed July 2, 2024)", {})]},
    "tx": {"status": "needs_review", "index": "https://www.hhs.texas.gov/about/reports-presentations",
           "reason": "hhs.texas.gov posts only the 'Texas State Plan for TANF Renewal' dated October 1, 2025 as a draft (texas-tanf-state-plan-draft-2025.pdf; HTTP 403 to plain clients, served to a browser-impersonated client) and the superseded October 2019 plan; no certified renewal is posted"},
    "ut": {"status": "agent_ready", "index": "https://jobs.utah.gov/edo/stateplans/", "listed": False,
           "period": "2022", "effective": "2022-10-01", "agency": "Utah Department of Workforce Services (Family Employment Program)",
           "plan_status": "Utah TANF State Plan (effective October 2022); jobs.utah.gov answers the state plans directory with HTTP 403 and the FEP pages with HTTP 500 to this client, so the listing page could not be read (located with a web search)",
           "docs": [(None, "https://jobs.utah.gov/edo/stateplans/tanfstateplan.pdf", "Utah TANF State Plan (effective October 2022)", {})]},
    "va": {"status": "needs_review", "index": "https://www.dss.virginia.gov/relief/tanf/",
           "reason": "the VDSS TANF pages (program, manual, data, VIEW) link the TANF Manual, forms and Title IV-A of the Social Security Act but no state plan; web search finds no TANF state plan on dss.virginia.gov (Virginia's plan is filed within the WIOA combined plan on the federal portal)"},
    "vt": {"status": "agent_ready", "index": "https://dcf.vermont.gov/esd/resources/reports", "listed": True,
           "period": "2024-2027", "effective": "2024-10-01", "agency": "Vermont Department for Children and Families, Economic Services Division (Reach Up)",
           "plan_status": "Vermont TANF State Plan Renewal October 1, 2024 through December 31, 2027",
           "docs": [(None, "https://outside.vermont.gov/dept/DCF/Shared%20Documents/Benefits/VT-TANF-State-Plan-2024-2027.pdf", "Vermont TANF State Plan Renewal 2024-2027", {})]},
    "wa": {"status": "agent_ready", "index": "https://workfirst.wa.gov/tanf", "listed": True,
           "period": "2026", "effective": "2026-08-01", "agency": "Washington State Department of Social and Health Services (WorkFirst)",
           "plan_status": "Washington's TANF State Plan Components, August 1, 2026 (Talent and Prosperity for All WIOA combined plan, TANF-only portion) with the signed 2026 certifications",
           "docs": [(None, "https://workfirst.wa.gov/sites/default/files/public/WA_TANF%20State%20Plan%202026%20FINAL.pdf", "Washington TANF State Plan Components, August 1, 2026 (final)", {}),
                    ("certifications", "https://workfirst.wa.gov/sites/default/files/public/SIGNED%20-%20WA%20TANF%20State%20Plan%20Certifications%202026.pdf", "Washington TANF State Plan Certifications 2026 (signed)", {})]},
    "wi": {"status": "agent_ready", "index": "https://dcf.wisconsin.gov/w2/researchers/state-plans", "listed": True,
           "period": "2024-2027", "effective": "2024-07-01", "agency": "Wisconsin Department of Children and Families (Wisconsin Works)",
           "plan_status": "Wisconsin's Combined State Plan under WIOA, Section VII TANF, PY 2024-2027, effective July 1, 2024, modifications March 15, 2026; the index labels the file 'Proposed Modifications to the Current TANF State Plan' (the stand-alone FFY 2021-2023 plan is the newest non-WIOA print)",
           "docs": [(None, "https://dcf.wisconsin.gov/files/w2/tanf-state-plans/2026-tanf-section-wioa-combined-plan-modifications.pdf", "Wisconsin TANF State Plan (WIOA combined plan Section VII, PY 2024-2027, 2026 modifications)", {})]},
    "wv": {"status": "agent_ready", "index": "https://bfa.wv.gov/state-plans", "listed": True,
           "period": "fy2024-2026", "effective": "2024-10-01", "agency": "West Virginia Department of Human Services, Bureau for Family Assistance (WV WORKS)",
           "plan_status": "Temporary Assistance for Needy Families State Plan FFY2024 (October 1, 2024 - September 30, 2026, effective October 1, 2024)",
           "docs": [(None, "https://bfa.wv.gov/media/39875/download?inline=", "West Virginia TANF State Plan, October 1, 2024 - September 30, 2026", {})]},
    "wy": {"status": "needs_review", "index": "https://dfs.wyo.gov/assistance-programs/cash-assistance/",
           "reason": "the DFS Cash Assistance pages and the SNAP and POWER Policy Manual page link no TANF state plan (the '2025.2026 State Model Plan Draft' is the LIHEAP model plan); web search finds none on dfs.wyo.gov"},
    "la": {"status": "needs_review", "index": "https://www.dcfs.louisiana.gov/page/56",
           "reason": "the DCFS 'TANF State Plan' page (page/56) renders no plan link or plan text to plain or browser clients (230 KB of navigation only); the plan PDFs search engines index are the 2011-2012 and 2012 renewals and the WIOA combined-plan TANF portion (undated); no current plan is reachable"},
}


def ca_bundle() -> Path:
    BUNDLE.write_text(Path(certifi.where()).read_text() + "\n" + INTERMEDIATE.read_text())
    return BUNDLE


def build_manifest(code: str, spec: dict) -> dict:
    jur = f"us-{code}"
    docs = []
    for suffix, url, title, extra in spec["docs"]:
        path = f"{jur}/policy/acf/tanf-plan/{spec['period']}" + (f"-{suffix}" if suffix else "")
        doc = {
            "source_id": f"{jur}-tanf-state-plan-{spec['period']}" + (f"-{suffix}" if suffix else ""),
            "jurisdiction": jur,
            "document_class": "policy",
            "title": title,
            "source_url": url,
            "source_format": extra.get("source_format", "pdf"),
            "source_as_of": SOURCE_AS_OF,
            "expression_date": spec["effective"],
            "citation_path": path,
        }
        if extra.get("download_url"):
            doc["download_url"] = extra["download_url"]
        if spec.get("impersonation"):
            doc["request"] = {"browser_impersonation": True}
        if extra.get("extraction"):
            doc["extraction"] = extra["extraction"]
        doc["metadata"] = {
            "primary_source": True,
            "source_authority": spec["agency"],
            "document_subtype": "state_plan_html" if doc["source_format"] == "html" else "state_plan_pdf",
            "program": "TANF",
            "federal_program": "TANF",
            "plan_status": spec["plan_status"],
            "publisher_index_url": spec["index"],
            "listed_on_publisher_index": spec["listed"],
            "ofa_index": OFA_NOTE,
            "source_discovery_group": f"{jur}/policy/tanf",
            "discovered_via": f"manual-review:tanf-agent-queue additional_families; index {spec['index']}",
            "closure_elements": ["tanf-s32"],
            "extraction_granularity": "html_blocks" if doc["source_format"] == "html" else "pdf_page",
        }
        if spec.get("tls"):
            doc["metadata"]["tls_note"] = ("server omits its Sectigo intermediate; extraction uses REQUESTS_CA_BUNDLE = certifi + "
                                           "data/certs/sectigo-public-server-authentication-ca-ov-r36.pem")
        if spec.get("note"):
            doc["metadata"]["source_note"] = spec["note"]
        if extra.get("extraction", {}).get("ocr"):
            doc["metadata"]["ocr_note"] = "scanned image-only PDF; Tesseract (eng) page OCR"
        docs.append(doc)
    return {"version": VERSION, "documents": docs}


def main() -> int:
    queue = yaml.safe_load(QUEUE_PATH.read_text())
    rows = {s["jurisdiction"]: s for s in queue["states"]}
    written = 0
    for code, spec in sorted(RESOLUTIONS.items()):
        jur = f"us-{code}"
        if jur not in rows:
            print(f"{jur}: no TANF queue row", file=sys.stderr)
            return 1
        stem = f"{jur}-tanf-state-plan"
        entry = {"family": FAMILY, "queue_status": spec["status"], "index_url": spec["index"]}
        if spec["status"] == "agent_ready":
            manifest = build_manifest(code, spec)
            (ROOT / "manifests" / f"{stem}.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120))
            written += 1
            entry.update({
                "primary_source_urls": [u for _s, u, _t, _e in spec["docs"]],
                "listed_on_publisher_index": spec["listed"],
                "target_manifest": f"manifests/{stem}.yaml",
                "target_scope": {"jurisdiction": jur, "document_class": "policy", "version": VERSION},
                "taken_count": len(spec["docs"]),
                "notes": f"State TANF plan taken {SOURCE_AS_OF} (closure tanf-s32): {spec['plan_status']}. {OFA_NOTE}."
                         + (f" {spec['note']}" if spec.get("note") else ""),
            })
        else:
            entry.update({
                "primary_source_url": None,
                "target_manifest": None,
                "target_scope": {"jurisdiction": jur, "document_class": "policy", "version": None},
                "taken_count": 0,
                "notes": ("Publisher blocked: " if spec["status"] == "blocked_primary_source" else "Not taken: ")
                         + spec["reason"] + f". {OFA_NOTE}. Nothing was worked around.",
            })
        row = rows[jur]
        families = [f for f in row.get("additional_families", []) if f.get("family") != FAMILY]
        families.append(entry)
        row["additional_families"] = families
    QUEUE_PATH.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    counts: dict[str, int] = {}
    for spec in RESOLUTIONS.values():
        counts[spec["status"]] = counts.get(spec["status"], 0) + 1
    print(f"wrote {written} manifests; state-plan family {counts}; ca bundle {ca_bundle()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
