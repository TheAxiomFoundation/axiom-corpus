"""Build one corpus manifest per jurisdiction for the FFY 2025-2027 CCDF State/Territory
Plans (ACF-118) and update the CCDF agent queue.

Central index: https://acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 (HHS Administration
for Children and Families, Office of Child Care; acf.hhs.gov 301-redirects there). Unlike the
LIHEAP Clearinghouse, ACF does not host the plans: each row links to the state or territory
Lead Agency's own website for the plan and, for the 50 states and DC, to an ACF-hosted
"Appendix" PDF (the Lead Agency implementation plan for federal non-compliances). The plan
documents themselves were located on each Lead Agency's page on 2026-09-10; that review is
frozen in RESOLUTIONS below so the run is reproducible. Rows the publisher blocked (HTTP 403,
bot challenge, TCP timeout, broken TLS) are recorded verbatim and never worked around.

TLS: dese.ade.arkansas.gov serves only its leaf certificate (issuer Sectigo Public Server
Authentication CA OV R36, root Sectigo Public Server Authentication Root R46).
data/certs/sectigo-public-server-authentication-ca-ov-r36.pem is that public intermediate,
fetched from the leaf certificate's AIA URL. Run extraction with REQUESTS_CA_BUNDLE pointing
at certifi + that file (built here as data/certs/ccdf-ca-bundle.pem). No verification is
disabled.

Retry 2026-09-10T18:36Z (docs/ingest-runs/2026-09-10-ccdf-state-plans-fy2025-2027-retry.md): the 25 blocked
hosts were probed once each with plain requests and curl_cffi impersonation (30 s); 24 failed identically, Minnesota
moved to a new host that is blocked the same way. Maine, Mississippi and Pennsylvania were located on the publishers'
own sites and added.

Retry 2 2026-09-10T21:35Z (docs/ingest-runs/2026-09-10-ccdf-state-plans-fy2025-2027-retry-2.md), from a US network: 17 of the 25
blocked hosts answered. 16 plans were located on the Lead Agency pages and added (CO, CT, ID, KS, KY, LA, MN, NE, NJ, OR,
RI, SC, TN, UT, VA, VT); Alaska posts only the public-comment draft (needs_review); AS, AZ, GA, MD, MO, MP, NY and TX
failed the same way (plain request plus curl_cffi impersonation, 20 s). Vermont needs VT_EXTRACTION (heading whitelist).

    uv run python scripts/build_ccdf_state_plan_manifests.py
"""
from __future__ import annotations

import datetime as dt
import html
import re
import sys
from pathlib import Path

import certifi
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
INDEX = "https://acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027"
INDEX_LEAD = "https://acf.hhs.gov/occ/form/approved-ccdf-plans-fy-2025-2027"
BASE = "https://acf.gov"
INTERMEDIATE = ROOT / "data" / "certs" / "sectigo-public-server-authentication-ca-ov-r36.pem"
SOURCE_AS_OF = dt.date.today().isoformat()
VERSION = f"{SOURCE_AS_OF}-ccdf-plan-fy2025-2027"
EXPRESSION_DATE = "2024-10-01"          # FFY 2025-2027 plans cover 10/01/2024 - 09/30/2027
FY = "2025-2027"
# acf.gov answers a non-browser User-Agent with HTTP 202 and an empty body.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

CODES = {
    "Alabama": "al", "Alaska": "ak", "American Samoa": "as", "Arizona": "az", "Arkansas": "ar",
    "California": "ca", "Colorado": "co", "Connecticut": "ct", "Delaware": "de",
    "District of Columbia": "dc", "Florida": "fl", "Georgia": "ga", "Guam": "gu", "Hawaii": "hi",
    "Idaho": "id", "Illinois": "il", "Indiana": "in", "Iowa": "ia", "Kansas": "ks",
    "Kentucky": "ky", "Louisiana": "la", "Maine": "me", "Maryland": "md", "Massachusetts": "ma",
    "Michigan": "mi", "Minnesota": "mn", "Mississippi": "ms", "Missouri": "mo", "Montana": "mt",
    "Nebraska": "ne", "Nevada": "nv", "New Hampshire": "nh", "New Jersey": "nj",
    "New Mexico": "nm", "New York": "ny", "North Carolina": "nc", "North Dakota": "nd",
    "Northern Mariana Islands": "mp", "Ohio": "oh", "Oklahoma": "ok", "Oregon": "or",
    "Pennsylvania": "pa", "Puerto Rico": "pr", "Rhode Island": "ri", "South Carolina": "sc",
    "South Dakota": "sd", "Tennessee": "tn", "Texas": "tx", "Utah": "ut", "Vermont": "vt",
    "Virgin Islands": "vi", "Virginia": "va", "Washington": "wa", "West Virginia": "wv",
    "Wisconsin": "wi", "Wyoming": "wy",
}

# The 41 second-level section headings of the FFY 2025-2027 ACF-118 preprint (sections 1-10).
# The CARS "Print Template" PDFs carry them inline ("2.2 Eligible Children and Families");
# one provision per heading plus the document root.
PREPRINT_SECTIONS = [
    ("1.1", "CCDF Leadership"), ("1.2", "CCDF Policy Decision Authority"),
    ("1.3", "Consultation in the Development of the CCDF Plan"),
    ("2.1", "Reducing Barriers to Family Enrollment and Redetermination"),
    ("2.2", "Eligible Children and Families"),
    ("2.3", "Prioritizing Services for Vulnerable Children and Families"),
    ("2.4", "Lead Agency Outreach to Families Experiencing Homelessness, Families with Limited "
            "English Proficiency, and Persons with Disabilities"),
    ("2.5", "Promoting Continuity of Care"), ("3.1", "Family Co-payments"),
    ("3.2", "Calculation of Co-Payment"), ("3.3", "Waiving Family Co-payment"),
    ("4.1", "Access to Full Range of Provider Options"),
    ("4.2", "Assess Market Rates and Analyze the Cost of Child Care"),
    ("4.3", "Adequate Payment Rates"), ("4.4", "Payment Practices to Providers"),
    ("4.5", "Supply Building"), ("5.1", "Licensing Requirements"),
    ("5.2", "Ratios, Group Size, and Qualifications for CCDF Providers"),
    ("5.3", "Health and Safety Standards for CCDF Providers"),
    ("5.4", "Pre-Service or Orientation Training on Health and Safety Standards"),
    ("5.5", "Monitoring and Enforcement of Licensing and Health and Safety Requirements"),
    ("5.6", "Ongoing Health and Safety Training"), ("5.7", "Comprehensive Background Checks"),
    ("5.8", "Exemptions for Relative Providers"), ("6.1", "Supporting the Child Care Workforce"),
    ("6.2", "Professional Development Framework"),
    ("6.3", "Ongoing Training and Professional Development"),
    ("6.4", "Early Learning and Developmental Guidelines"),
    ("7.1", "Quality Activities Needs Assessment"), ("7.2", "Use of Quality Set-Aside Funds"),
    ("8.1", "Coordination with Partners to Expand Accessibility and Continuity of Care"),
    ("8.2", "Optional Use of Combined Funds, CCDF Matching, and Maintenance-of-Effort Funds"),
    ("8.3", "Coordination with Child Care Resource and Referral Systems"),
    ("8.4", "Public-Private Partnerships"), ("8.5", "Disaster Preparedness and Response Plan"),
    ("9.1", "Parental Complaint Process"), ("9.2", "Consumer Education Website"),
    ("9.3", "Increasing Engagement and Access to Information"),
    ("9.4", "Providing Information on Developmental Screenings"),
    ("10.1", "Effective Internal Controls"),
    ("10.2", "Fraud Investigation, Payment Recovery, and Sanctions"),
]

CARS_DROP = [r"^\d+ \| P a g e\s*$", r"^FFY 2025[–-]2027 CCDF State Plan\s*$"]
# CARS print-template PDF: "X.Y Heading" on one line; rate tables ("94.00 Per") are excluded by
# the single non-zero digit after the dot. Pages 1-3 (OMB notice, table of contents) are skipped
# by starting after the "Overview" heading. Section 10.2 absorbs the trailing Appendix 1 template.
CARS_EXTRACTION = {
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^(?P<label>\d{1,2}\.[1-9])\s+(?P<heading>[A-Z]\S.*)$",
    # 2.4 wraps after "Families with Limited"; take the second line into the heading.
    "heading_continuation_pattern": r"^(?P<heading>(?:English )?Proficiency, and Persons with Disabilities)$",
    "start_after_pattern": r"^Overview$",
    "drop_line_patterns": CARS_DROP,
}
# California posts its own Word export of the plan: most section labels sit alone on a line with
# the heading on the next line.
CA_EXTRACTION = {
    **CARS_EXTRACTION,
    "section_heading_pattern": r"^(?P<label>\d{1,2}\.[1-9])(?:\s+(?P<heading>[A-Z]\S.*))?$",
    "label_only_heading_pattern": r"^[A-Z][A-Za-z].*$",
    "label_only_requires_heading": True,
}
# Illinois publishes the plan as one HTML page (h3 headings). List items such as
# "1.2 Sliding fee scale" also start with a label, so the heading must be a preprint heading.
IL_EXTRACTION = {
    "segmentation": "labeled_sections",
    "html_content_selector": "#ItemContentDiv",
    "html_drop_selectors": ["#TableOfContents"],
    "section_heading_pattern": r"^(?P<label>\d{1,2}\.[1-9])\s+(?P<heading>"
    + "|".join(re.escape(heading) for _label, heading in PREPRINT_SECTIONS)
    + r")$",
    "stop_text_pattern": r"^Appendix 1: Lead Agency Implementation Plan$",
}
# Vermont embeds its child care licensing rules inside section 5.3; their numbered headings
# ("5.3 Managing Infectious Diseases", "9.1 Staff shall ...", "13.1 ...") collide with the preprint
# labels, so the heading must be one of the 41 preprint headings (2.4 wraps, see continuation).
VT_EXTRACTION = {
    **CARS_EXTRACTION,
    "section_heading_pattern": r"^(?P<label>\d{1,2}\.[1-9])\s+(?P<heading>"
    + "|".join(re.escape(heading) for label, heading in PREPRINT_SECTIONS if label != "2.4")
    + r"|Lead Agency Outreach to Families Experiencing Homelessness, Families with Limited(?: English)?)\s*$",
}

# Indiana CCDF Policy Manual (FSSA agency manual; a different family from the ACF-118 plans).
IN_MANUAL_INDEX = "https://www.in.gov/fssa/carefinder/information-and-resources2/"
IN_MANUAL_INDEX_COUNT = 11
IN_MANUAL_NOTE = (
    "Reviewed 2026-09-10: the carefinder page the ACF index links lists 11 documents (the certified "
    "FY2025-2027 plan PDF, public-comment summary, waiver request, CAP plan and letters); the CCDF Policy "
    "Manual is not listed there. The lead-list URL https://www.in.gov/fssa/carefinder/files/CCDF-Policy-Manual.pdf "
    "answers HTTP 200 (application/pdf, 4,417,558 bytes, Last-Modified 2026-06-24) and the Provider Manual "
    "likewise (1,067,593 bytes), but their own carefinder index page was not located without crawling in.gov. "
    "Not extracted in this run: the plan family is not fully complete (8 jurisdictions blocked, 4 needs_review after the 2026-09-10 second retry), "
    "so the work order's precondition for the separate 2026-09-10-ccdf-in-policy-manual version is not met."
)

AUTHORITY = "HHS Administration for Children and Families, Office of Child Care (ACF-118 CCDF Plan; published by the state or territory CCDF Lead Agency)"

# Reviewed 2026-09-10 by following each ACF index "plan" link to the Lead Agency page.
# taken: (plan_url, publisher_index_url, source_format, plan_version, plan_status, extra)
# blocked/needs_review: (publisher_index_url, reason)
RESOLUTIONS: dict[str, dict] = {
    "al": {"status": "agent_ready", "url": "https://dhr.alabama.gov/wp-content/uploads/2023/04/2025-2027-CCDF-State-Plan-with-Approval-Letter.pdf",
               "index": "https://dhr.alabama.gov/child-care/", "version": "Initial Plan", "plan_status": "Approved (state PDF prefixed with the ACF approval letter; 301 pages)"},
    "ak": {"status": "needs_review", "index": "https://aws.state.ak.us/OnlinePublicNotices/Notices/View.aspx?id=215530",
               "reason": "retry 2 2026-09-10T21:35Z from a US network: aws.state.ak.us now answers (first two passes: TCP connect timeout); the Online Public Notice the ACF index links carries one attachment, '2025-2027 CCDF State Plan 052424.pdf' (Attachment.aspx?id=148401, 213 pages, Microsoft Word export dated 2024-05-24, no CARS Plan Status line, text refers to 'this draft CCDF Plan' posted for public comment); the Department of Health Child Care Program Office page lists no CCDF plan; no approved or certified FFY 2025-2027 plan is posted, so not extracted"},
    "as": {"status": "blocked_primary_source", "index": "https://www.dhss.as/index.html",
               "reason": "TLS: www.dhss.as presents a self-signed, expired certificate (CN=cmaster70); verification impossible, not disabled; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (SSLCertVerificationError / curl 60 self-signed, expired certificate)"},
    "az": {"status": "blocked_primary_source", "index": "https://des.az.gov/services/child-and-family/child-care/child-care-and-development-fund-state-plan",
               "reason": "HTTP 403 (cloudflare) for requests with browser UA and curl_cffi chrome120/safari17_0/edge101; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (HTTP 403 cloudflare for plain requests and chrome impersonation)"},
    "ar": {"status": "agent_ready", "url": "https://dese.ade.arkansas.gov/Files/ACF-118_CCDF_FFY_2025-2027_For_Arkansas_OEC.pdf",
               "index": "https://dese.ade.arkansas.gov/Offices/office-of-early-childhood/forms--documents", "version": "Amendment 2", "plan_status": "Approved as of 2026-05-13 (only FFY 2025-2027 version posted)",
               "tls": True},
    "ca": {"status": "agent_ready", "url": "https://www.cdss.ca.gov/Portals/9/CCDD/CCDF_2025-2027_CCDF_Approved.pdf",
               "index": "https://www.cdss.ca.gov/inforesources/child-care-and-development/fund-state-plan", "version": "Initial Plan", "plan_status": "Approved (state Word export, not the CARS print template; amendments #1 posted separately, not taken)",
               "extraction": CA_EXTRACTION},
    "co": {"status": "agent_ready", "url": "https://drive.google.com/file/d/1zaT-E7tSLFKir9ANtSBRxy0f3T5sm-li/view?usp=sharing",
               "index": "https://cdec.colorado.gov/resources/state-plans", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (located on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 CloudFront on the first two passes; the CDEC State Plans page labels it '2024-27 Child Care and Development Fund State Plan' and links it on Google Drive, fetched through the extractor's existing Google Drive download path)"},
    "ct": {"status": "agent_ready", "url": "https://www.ctoec.org/forms-documents/25-27-ccdf-plan.pdf",
               "index": "https://www.ctoec.org/ccdf/", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('Final CCDF Plan 2025-2027', a PDFium re-save of the CARS print, 219 pages; located on retry 2 2026-09-10T21:35Z from a US network: plain requests now answer 200 while curl_cffi chrome impersonation still gets HTTP 403 cloudflare, so no impersonation is configured; the draft, implementation summaries and public comment report are posted separately, not taken)"},
    "de": {"status": "agent_ready", "url": "https://mychildde.org/wp-content/uploads/4.15.26-ACF-118-CCDF-FFY-2025-2027-For-Delaware.pdf",
               "index": "https://www.mychildde.org/", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09"},
    "dc": {"status": "agent_ready", "url": "https://osse.dc.gov/sites/default/files/dc/sites/osse/publication/attachments/CCDF%20FFY%202025-2027%20For%20District%20of%20Columbia.pdf",
               "index": "https://osse.dc.gov/publication/dc-child-care-and-development-fund", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (amendment 1 and 2 approval letters posted separately, not taken)"},
    "fl": {"status": "agent_ready", "url": "https://www.fldoe.org/file/20628/2025-2027CCDFStatePlan.pdf",
               "index": "https://www.fldoe.org/schools/early-learning/rep-pol-guide/ccdf-plan.stml", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09", "impersonation": True},
    "ga": {"status": "blocked_primary_source", "index": "http://www.decal.ga.gov/BftS/CCDFPlan.aspx",
               "reason": "connection reset by peer (curl 56) from www.decal.ga.gov for plain curl and curl_cffi; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (remote end closed connection without response / curl 52 empty reply)"},
    "gu": {"status": "agent_ready", "url": "https://guamchildcare.com/sites/default/files/ccdf_state_plan_ffy_2025-2027_for_guam_amendment_01.pdf",
               "index": "https://guamchildcare.com/ccdf-state-plan", "version": "Amendment 1", "plan_status": "Approved as of 2026-03-26 (only FFY 2025-2027 version posted)"},
    "hi": {"status": "agent_ready", "url": "https://humanservices.hawaii.gov/bessd/files/2024/11/ACF-118-CCDF-FFY-2025-2027-For-Hawaii.pdf",
               "index": "https://humanservices.hawaii.gov/bessd/child-care-program/", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (state labels the link 'Conditional Approval')"},
    "id": {"status": "agent_ready", "url": "https://publicdocuments.dhw.idaho.gov/WebLink/ElectronicFile.aspx?docid=32013&dbid=0&repo=PUBLIC-DOCUMENTS",
               "index": "https://healthandwelfare.idaho.gov/providers/child-care-providers/child-care-resources", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (located on retry 2 2026-09-10T21:35Z from a US network: publicdocuments.dhw.idaho.gov now answers after TCP connect timeouts on the first two passes; the index links the Laserfiche WebLink DocView page id=32013, whose viewer serves the file from the same repository's ElectronicFile.aspx endpoint, taken as source_url)"},
    "il": {"status": "agent_ready", "url": "https://www.dhs.state.il.us/page.aspx?item=163746",
               "index": "https://www.dhs.state.il.us/page.aspx?item=59282", "version": "Initial Plan", "plan_status": "Published as an HTML page (no PDF on the publisher's index)",
               "source_format": "html", "extraction": IL_EXTRACTION},
    "in": {"status": "needs_review", "index": "https://www.in.gov/fssa/carefinder/information-and-resources2/",
               "reason": "publisher posts https://www.in.gov/dA/ce627c931e/ACF-118-CCDF-FY2025-2027-IN.pdf?language_id=1: the certified 2024-06-30 submission (399 pages, 7.7 MB, non-CARS layout with attached state rules); the CARS section pattern finds 5 unique labels, so it was not extracted; approved version not posted; retried 2026-09-10: same file (7,742,708 bytes, Last-Modified 2026-06-19), 1 of 41 labels after the Overview start, the carefinder index lists the same 11 documents; retried 2026-09-10T21:35Z from US network: same page (the plan plus 9 CAP and letter documents), same file (HTTP 200, 7,742,708 bytes, Last-Modified 2026-06-19); approved print still not posted"},
    "ia": {"status": "agent_ready", "url": "https://hhs.iowa.gov/media/13429/download?inline",
               "index": "https://hhs.iowa.gov/programs/programs-and-services/child-care", "version": "Amendment 1", "plan_status": "Approved as of 2026-03-26 (only FFY 2025-2027 version posted)"},
    "ks": {"status": "agent_ready", "url": "https://www.dcf.ks.gov/services/ees/Documents/Child_Care/FFY%202025-2027%20CCDF%20Initial%20CCDF%20Plan.pdf",
               "index": "https://www.dcf.ks.gov/search/Pages/SearchResults.aspx?k=CCDF%20state%20plan", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (located on retry 2 2026-09-10T21:35Z from a US network: www.dcf.ks.gov now answers after TCP connect timeouts on the first two passes; the Child care and early education page the ACF index links carries no CCDF plan link, nor do the Child Care Subsidy and Child Care Providers pages; 'FFY 2025-2027 CCDF Initial CCDF Plan' was located with the publisher's own site search, which also lists the Initial Plan Approval Letter and the Waiver Approval Letter, not taken)"},
    "ky": {"status": "agent_ready", "url": "https://www.chfs.ky.gov/agencies/dcbs/dcc/Documents/stateplan20252027.pdf",
               "index": "https://www.chfs.ky.gov/agencies/dcbs/dcc/Pages/default.aspx", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('Kentucky CCDF FFY 2025-2027 Approved State Plan'; located on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 on the first two passes; the state-hosted Appendix and the Preliminary Draft are posted separately, not taken)"},
    "la": {"status": "agent_ready", "url": "https://doe.louisiana.gov/docs/default-source/early-childhood/approved-2025-2027-ccdf-state-plan.pdf?sfvrsn=3316f8f1_12",
               "index": "https://doe.louisiana.gov/early-childhood/early-childhood-center-directors/early-childhood-poicy-guidance", "version": "Amendment 1", "plan_status": "Approved as of 2025-03-26 (the only approved FFY 2025-2027 version posted, labelled 'Approved 2025-2027 CCDF State Plan'; the CARS print carries 'Amendment 1'; the public-comment draft and hearing agenda are posted separately, not taken; located on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 cloudflare on the first two passes; the ACF index link on louisianabelieves.com redirects to this doe.louisiana.gov page)"},
    "me": {"status": "agent_ready", "url": "https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/inline-files/Maine%20State%20Plan%20CCDF%20FFY%202025-2027%20For%20Maine_1.pdf",
               "index": "https://www.maine.gov/dhhs/ocfs/provider-resources/child-care-subsidy-information-for-providers", "version": "Initial Plan",
               "plan_status": "Certified as of 2024-09-12 (located on retry 2026-09-10: the ACF index link goes to the 'paying for child care' page; the plan is 'Maine State Plan CCDF FFY 2025-2027 for Maine' on the OCFS 'Child Care Affordability Information & Resources' page; Amendments #1-#4, the Appendix, public comments and the Notice of Compliance are posted separately, not taken; approved print not posted)"},
    "md": {"status": "blocked_primary_source", "index": "https://earlychildhood.marylandpublicschools.org/about/ccdf-state-plan",
               "reason": "landing page 200; the linked plan page https://earlychildhood.marylandpublicschools.org/2025-2027-ccdf-plan returns HTTP 403 'Access denied'; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (HTTP 403 cloudflare on the 2025-2027-ccdf-plan page for plain and impersonated requests; the about/ccdf-state-plan landing page answers 200 and links only that page)"},
    "ma": {"status": "agent_ready", "url": "https://www.mass.gov/doc/20241108-approved-2025-2027-ccdf-state-plan/download",
               "index": "https://www.mass.gov/lists/child-care-and-development-fund-ccdf-state-plans", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (amendment 1 and 2 consolidated plans posted separately, not taken)", "impersonation": True},
    "mi": {"status": "agent_ready", "url": "https://www.michigan.gov/mileap/-/media/Project/Websites/mileap/Documents/Early-Childhood-Education/Child-Development-and-Care/data-and-reporting/CARS-118-FFY2025-2027-CCDF-Plan-Print-Template.pdf?rev=7d0ee04737634947b4883ee964af46a7&hash=C3B5F436B5ECD5F2D57742378BDE464C",
               "index": "https://www.michigan.gov/mileap/early-childhood-education/early-learners-and-care/cdc/data-and-reporting", "version": "Amendment 2", "plan_status": "Approved as of 2026-03-12 (state posts Amendment 1 and 2 consolidated plans and the Appendix; initial approved plan not posted)", "impersonation": True},
    "mn": {"status": "agent_ready", "url": "https://dcyf.mn.gov/sites/default/files/2026-09/CCDF%2025_27_plan_round_3_amendments.pdf",
               "index": "https://dcyf.mn.gov/child-care-and-development-fund", "version": "Amendment 3", "plan_status": "Approved as of 2026-08-11 ('Amended 25-27 CCDF Plan', the only FFY 2025-2027 version posted by the Department of Children, Youth, and Families, which replaced DHS as Lead Agency; the mn.gov page the ACF index links is a meta-refresh to this page; retry 2 2026-09-10T21:35Z from a US network: plain requests are still redirected to the validate.perfdrive.com challenge, curl_cffi chrome impersonation now completes TLS verification and receives the page and the PDF)", "impersonation": True},
    "ms": {"status": "agent_ready", "url": "https://www.mdhs.ms.gov/wp-content/uploads/2025/01/ACF-118-CCDF-FFY-2025-2027-For-Mississippi.pdf",
               "index": "https://www.mdhs.ms.gov/eccd/reports-archives/", "version": "Initial Plan",
               "plan_status": "Approved as of 2024-11-09 (located on retry 2026-09-10: the State Plans page still lists only 2022-2024; the plan is '2025 - 2027 CCDF Triennial State Plan' on the ECCD 'Child Care Reports & Archives' page, whose /document/2025-2027-ccdf-triennial-state-plan/ landing URL 302s to this PDF; the Appendix is posted separately, not taken)"},
    "mo": {"status": "blocked_primary_source", "index": "https://dese.mo.gov/childhood/child-care-subsidy/child-care-dev-fund",
               "reason": "plan link https://dese.mo.gov/media/pdf/acf-118-ccdf-ffy-2025-2027-missouri returns an HTML Drupal antibot form (HTTP 200) instead of the PDF for requests and curl_cffi chrome120; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (HTTP 200 text/html Drupal antibot form with an Incapsula script instead of the PDF, plain and impersonated; the landing page also lists Amendment #1 and 'Current' Amendment #2 behind the same media path)"},
    "mt": {"status": "agent_ready", "url": "https://dphhs.mt.gov/assets/ecfsd/childcare/documentsandresources/MontanaCCDFStatePlan.pdf",
               "index": "https://dphhs.mt.gov/ecfsd/childcare/documentsandresources", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09"},
    "ne": {"status": "agent_ready", "url": "https://dhhs.ne.gov/Child%20Care%20Documents/ACF-118%20CCDF%20FFY%202025-2027%20For%20Nebraska%20-%20APPROVED.pdf",
               "index": "https://dhhs.ne.gov/Pages/Child-Care-and-Development-Fund-Plan.aspx", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('approved 2025-2027 State Plan'; located on retry 2 2026-09-10T21:35Z from a US network after TCP connect timeouts on the first two passes)"},
    "nv": {"status": "agent_ready", "url": "https://www.dss.nv.gov/uploadedFiles/dwssnvgov/content/Care/ACF-118%20CCDF%20FFY%202025-2027%20For%20Nevada_Final%20Submission.pdf",
               "index": "https://www.dss.nv.gov/programs/child-care/", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (dwss.nv.gov index link redirects to dss.nv.gov)"},
    "nh": {"status": "agent_ready", "url": "https://www.dhhs.nh.gov/sites/g/files/ehbemt476/files/documents2/ccdf-state-plan-2025-2027.pdf",
               "index": INDEX, "version": "Initial Plan", "plan_status": "Certified as of 2024-09-26 (submitted version linked directly from the ACF index; approved print not posted)", "impersonation": True},
    "nj": {"status": "agent_ready", "url": "https://www.childcarenj.gov/ChildCareNJ/media/media_library/CCDF_State_Plan_for_New_Jersey_FFY25-27.pdf",
               "index": INDEX, "version": "Initial Plan", "plan_status": "Certified as of 2024-09-27 (submitted version linked directly from the ACF index; approved print not posted; the PDF answered HTTP 200 on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 cloudflare on the first two passes)"},
    "nm": {"status": "agent_ready", "url": "https://www.nmececd.org/wp-content/uploads/2025/04/Approved-FFY2025-2027-Child-Care-and-Development-Fund-State-Plan.pdf",
               "index": "https://www.nmececd.org/ccdfsessions/", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09"},
    "ny": {"status": "blocked_primary_source", "index": "https://ocfs.ny.gov/main/childcare/stateplan/",
               "reason": "ocfs.ny.gov returns an F5/Shape JavaScript bot-challenge page (TSPD) instead of the index; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (F5/Shape TSPD JavaScript challenge page, 7.5 KB, plain and impersonated)"},
    "nc": {"status": "agent_ready", "url": "https://ncchildcare.ncdhhs.gov/Portals/0/documents/pdf/A/ACF-118_CCDF_FFY_2025-2027_For_North_Carolina_November_2024.pdf?ver=5Qk3uXFjaCh3xyBqG3faZg%3d%3d",
               "index": "https://ncchildcare.ncdhhs.gov/Services/Child-Care-Development-Fund-CCDF", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (Amendment 2 consolidated plan and the Appendix posted separately, not taken)"},
    "nd": {"status": "agent_ready", "url": "https://www.hhs.nd.gov/sites/default/files/documents/website-archive/human-services/2025-2027-ccdfstateplan-initial-archived.pdf",
               "index": "https://www.hhs.nd.gov/cfs/early-childhood-services/child-care-development-fund", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (Amendment 1, Amendment 2 and Appendix posted separately, not taken)"},
    "mp": {"status": "blocked_primary_source", "index": "https://www.childcare.gov.mp/",
               "reason": "HTTP 403 (nginx) for requests with browser UA and curl_cffi chrome120/safari17_0/edge101; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (HTTP 403 nginx)"},
    "oh": {"status": "agent_ready", "url": "https://dam.assets.ohio.gov/image/upload/childrenandyouth.ohio.gov/For%20Providers/CCDF/Approved_State_Plan_2025-2027.pdf",
               "index": "https://childrenandyouth.ohio.gov/for-providers/resources/child-care-and-development-fund-state-plan", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (amendments 1 and 2 posted separately, not taken)"},
    "ok": {"status": "agent_ready", "url": "https://oklahoma.gov/content/dam/ok/en/okdhs/documents/okdhs-pdf-library/child-care-services/ACF-118%20CCDF%20FFY%202025-2027%20For%20Oklahoma.pdf",
               "index": INDEX, "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (linked directly from the ACF index)"},
    "or": {"status": "agent_ready", "url": "https://www.oregon.gov/delc/about-us/Documents/ACF-118_CCDF_2025-2027_Oregon.pdf",
               "index": "https://www.oregon.gov/delc/about-us/pages/state-plans.aspx", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('2025-27 Plan (303 pages)'; Amendment 1 with its approval letter, the initial approval letter, the state-hosted Appendix 1, public comment documents and the transitional waiver request are posted separately, not taken; www.oregon.gov resolved and answered on retry 2 2026-09-10T21:35Z from a US network)"},
    "pa": {"status": "agent_ready", "url": "https://www.pa.gov/content/dam/copapwp-pagov/en/dhs/documents/services/children/documents/2025-2027-ocdel-ccdf-state-plan.pdf",
               "index": "https://www.pa.gov/agencies/dhs/resources/early-learning-child-care", "version": "Initial Plan",
               "plan_status": "Approved as of 2024-11-09 (located on retry 2026-09-10: the ACF index link redirects to the generic pa.gov DHS agency page; the plan is linked as '2025-2027 Pennsylvania State Plan for Child Care Development Block Grant Report (CCDBG)' on the DHS 'Early Learning & Child Care' resources page; no amendments or Appendix posted there)"},
    "pr": {"status": "needs_review", "index": "https://www.acuden.pr.gov/documentos",
               "reason": "publisher's documents page lists only 'Borrador Plan Estatal Child Care 2025-2027' (draft) plus hearing notices and supporting studies; no approved plan; retried 2026-09-10: unchanged (draft, hearing notice, 'Fee Scale State Plan 2025-2027' supporting document, emergency plan); no approved or certified plan"},
    "ri": {"status": "agent_ready", "url": "https://dhs.ri.gov/media/8381/download?language=en",
               "index": "https://dhs.ri.gov/regulations/state-plans", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('Child Care Development Fund State Plan FFY25-27'; located on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 cloudflare on the first two passes)"},
    "sc": {"status": "agent_ready", "url": "https://scchildcare.org/media/bxkiasbl/acf-118-ccdf-ffy-2025-2027-for-south-carolina-approved-state-plan.pdf",
               "index": "https://www.scchildcare.org/resources/", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('Child Care Development Fund State Plan FFY 2025-2027 Approved State Plan' on the SC Child Care resources page, which redirects to scchildcare.org; located on retry 2 2026-09-10T21:35Z from a US network after TCP connect timeouts on the first two passes)"},
    "sd": {"status": "agent_ready", "url": "https://dss.sd.gov/docs/childcare/state_plan/2025-2027/2025-2027_State_Plan_original.pdf",
               "index": "https://dss.sd.gov/childcare/stateplan/default.aspx", "version": "Initial Plan", "plan_status": "Certified as of 2024-09-24 ('original'; Amendments 1-3 consolidated plans posted separately, not taken)"},
    "tn": {"status": "agent_ready", "url": "https://www.tn.gov/content/dam/tn/human-services/documents/CCDF%20State%20Plan%20FFY%202025-2027%20Tennessee.pdf",
               "index": "https://www.tn.gov/humanservices/information-and-resources/tdhs-reports-and-information.html", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('CCDF State Plan FFY 2025-2027' on the TDHS Reports and Information page; Appendix 1 and two transitional waiver approvals are posted separately, not taken; located on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 awselb on the first two passes; one of three page requests on the retry ended with an SSL unexpected EOF, the others answered 200)"},
    "tx": {"status": "blocked_primary_source", "index": "https://www.twc.texas.gov/programs/child-care/data-reports-plans",
               "reason": "HTTP 403 (CloudFront) for requests with browser UA and curl_cffi chrome120/safari17_0/edge101; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure class (HTTP 202 with an AWS WAF JavaScript challenge body instead of the page, plain and impersonated; the first two passes saw 403 CloudFront)"},
    "ut": {"status": "agent_ready", "url": "https://jobs.utah.gov/occ/ccdfplan.pdf",
               "index": "https://jobs.utah.gov/occ/plans.html", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('2025-2027 State Plan' on the OCC Plans and Reports page; the state-hosted Appendix is posted separately, not taken; located on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 awselb on the first two passes)"},
    "vt": {"status": "agent_ready", "url": "https://outside.vermont.gov/dept/DCF/Shared%20Documents/CDD/Reports/CCDF-Plans/CCDF-Plan-2025-2027-Approved.pdf",
               "index": "https://dcf.vermont.gov/CDD/CCDF", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('CCDF-Plan-2025-2027-Approved'; the PDF answered HTTP 200 on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 on the first two passes; the plan embeds Vermont's child care licensing rules inside section 5.3, whose numbered rule headings (5.3, 5.6, 9.1-9.4, 13.1) collide with the preprint labels, so the section pattern is restricted to the 41 preprint headings)", "extraction": VT_EXTRACTION},
    "vi": {"status": "needs_review", "index": "https://dhs.vi.gov/child-care-regulatory/",
               "reason": "publisher's site lists only a CCDF preprint draft for FFY 2019-2021; no FFY 2025-2027 plan found; retried 2026-09-10: the home page still lists the 2019-2021 preprint draft and the Office of Child Care & Regulatory Services page lists the FFY 2022-2024 plan (submitted 2021-09-17), policy memoranda and the 2022 market rate survey; site search for 'CCDF 2025' returns nothing; no FFY 2025-2027 plan"},
    "va": {"status": "agent_ready", "url": "https://www.childcare.virginia.gov/home/showpublisheddocument/55566/638647472799800000",
               "index": "https://www.childcare.virginia.gov/reports-resources/administrative-program-manuals-reports-and-data/virginia-child-care-plan", "version": "Initial Plan", "plan_status": "Certified as of 2024-10-01 (the publisher labels it \"Virginia's Approved 2025-2027 CCDF State Plan\"; the CARS print carries Plan Status Certified and no approval print is posted; retry 2 2026-09-10T21:35Z from a US network: plain requests still get HTTP 403 AkamaiGHost, curl_cffi chrome impersonation receives the page and the PDF)", "impersonation": True},
    "wa": {"status": "agent_ready", "url": "https://www.dcyf.wa.gov/sites/default/files/pdf/2025-2027-CCDF-Current-Plan.pdf",
               "index": "https://www.dcyf.wa.gov/about/government-affairs/ccdf", "version": "Initial Plan", "plan_status": "Certified as of 2024-09-25 ('2025-2027 CCDF Plan'; Amendment 1 posted separately, not taken)"},
    "wv": {"status": "agent_ready", "url": "https://bfa.wv.gov/media/39915/download?inline",
               "index": INDEX, "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (linked directly from the ACF index)"},
    "wi": {"status": "agent_ready", "url": "https://dcf.wisconsin.gov/files/wishares/ccdbg/2025-27-ccdf-plan-draft-10-2024.pdf",
               "index": INDEX, "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (file name says draft-10-2024; content is the approved print, linked directly from the ACF index)"},
    "wy": {"status": "agent_ready", "url": "https://drive.google.com/file/d/10TJ3S8d_nwyNxdkkbyk2gzCfHTk7CTcA/view?usp=sharing",
               "index": "https://dfs.wyo.gov/services/family-services/child-care/", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (dfs.wyo.gov links the plan on Google Drive; fetched through the extractor's Google Drive download path)"},
}


def ca_bundle() -> Path:
    out = ROOT / "data" / "certs" / "ccdf-ca-bundle.pem"
    out.write_text(Path(certifi.where()).read_text() + "\n" + INTERMEDIATE.read_text())
    return out


def fetch_index() -> list[dict]:
    resp = requests.get(INDEX, headers={"User-Agent": BROWSER_UA}, timeout=60)
    resp.raise_for_status()
    page = resp.text
    table = page[page.find("<table") : page.find("</table>") + 8]
    rows = []
    for row in re.findall(r"<tr>(.*?)</tr>", table, re.S)[1:]:
        cells = re.findall(r"<td>(.*?)</td>", row, re.S)
        name = re.sub(r"<[^>]+>", "", html.unescape(cells[0])).strip()
        plan = re.findall(r'href="([^"]+)"', cells[1])
        appendix = re.findall(r'href="([^"]+)"', cells[2])
        rows.append({
            "name": name,
            "code": CODES[name],
            "plan_link": html.unescape(plan[0]) if plan else None,
            "appendix_url": (BASE + html.unescape(appendix[0])) if appendix else None,
        })
    return rows


def main() -> int:
    bundle = ca_bundle()
    rows = fetch_index()
    if len(rows) != 56 or {r["code"] for r in rows} != set(RESOLUTIONS):
        print(f"index has {len(rows)} rows; layout changed?", file=sys.stderr)
        return 1
    direct_pdf = [r for r in rows if r["plan_link"] and re.search(r"\.pdf(\?|$)", r["plan_link"], re.I)]
    appendix = [r for r in rows if r["appendix_url"]]
    queue_path = ROOT / "manifests" / "ccdf-agent-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    existing = {s["jurisdiction"]: s for s in queue["states"]}
    states = []
    written = 0
    for r in rows:
        code, name = r["code"], r["name"]
        jur = f"us-{code}"
        res = RESOLUTIONS[code]
        row = {"jurisdiction": jur, "name": name}
        row["queue_status"] = res["status"]
        row["index_url"] = INDEX
        row["index_document_count"] = int(bool(r["plan_link"])) + int(bool(r["appendix_url"]))
        row["index_plan_link"] = r["plan_link"]
        row["index_appendix_url"] = r["appendix_url"]
        row["publisher_index_url"] = res["index"]
        row["target_scope"] = {"jurisdiction": jur, "document_class": "policy", "version": VERSION}
        if res["status"] == "agent_ready":
            fmt = res.get("source_format", "pdf")
            stem = f"{jur}-ccdf-state-plan-fy{FY}"
            doc = {
                "source_id": f"{jur}-acf-ccdf-plan-fy{FY}",
                "jurisdiction": jur,
                "document_class": "policy",
                "title": f"{name} CCDF Plan, FFY {FY}",
                "source_url": res["url"],
                "source_format": fmt,
                "source_as_of": SOURCE_AS_OF,
                "expression_date": EXPRESSION_DATE,
                "citation_path": f"{jur}/policy/acf/ccdf-plan/fy{FY}",
            }
            if res.get("impersonation"):
                doc["request"] = {"browser_impersonation": True}
            doc["extraction"] = res.get("extraction", CARS_EXTRACTION)
            doc["metadata"] = {
                "primary_source": True,
                "source_authority": AUTHORITY,
                "document_subtype": "state_plan_html" if fmt == "html" else "state_plan_pdf",
                "program": "CCDF",
                "form": "ACF-118",
                "fiscal_years": FY,
                "plan_period": "2024-10-01 to 2027-09-30",
                "plan_version": res["version"],
                "plan_status": res["plan_status"],
                "central_index_url": INDEX,
                "publisher_index_url": res["index"],
                "acf_appendix_url": r["appendix_url"],
                "source_discovery_group": f"{jur}/policy/ccdf",
                "discovered_via": "manual-review:ccdf-agent-queue; index https://acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027",
            }
            if res.get("tls"):
                doc["metadata"]["tls_note"] = "server omits its intermediate certificate; extraction uses REQUESTS_CA_BUNDLE = certifi + data/certs/sectigo-public-server-authentication-ca-ov-r36.pem"
            manifest = {"version": VERSION, "documents": [doc]}
            (ROOT / "manifests" / f"{stem}.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120))
            written += 1
            row.update({
                "source_kind": "official_html_state_plan" if fmt == "html" else "official_pdf_state_plan",
                "primary_source_url": res["url"],
                "target_manifest": f"manifests/{stem}.yaml",
                "taken_count": 1,
                "notes": f"FFY {FY} ACF-118 CCDF Plan ({res['version']}; {res['plan_status']}) located on the Lead Agency page linked from the ACF index; extraction proven. The ACF-hosted Appendix on the index is a separate document family, not taken.",
            })
        else:
            row.update({
                "source_kind": "official_state_plan_page",
                "primary_source_url": None,
                "target_manifest": f"manifests/us-{code}-ccdf-state-plan-fy{FY}.yaml",
                "taken_count": 0,
                "notes": ("Publisher blocked: " if res["status"] == "blocked_primary_source" else "Not extracted: ") + res["reason"] + ". Nothing was worked around.",
            })
        states.append(row)
    # Keep the pre-existing federal row first and the Indiana agency-manual row (a different
    # document family from the plans) last; both stay needs_review with the findings recorded.
    us_row = existing["us"]
    in_manual = existing["us-in"]
    states = [us_row, *states, in_manual]
    us_row["queue_status"] = "needs_review"
    us_row["index_url"] = INDEX
    us_row["index_document_count"] = len(rows) + len(appendix)
    us_row["taken_count"] = 0
    us_row["notes"] = (
        "Reviewed 2026-09-10: the lead-list URL (acf.hhs.gov) 301-redirects to acf.gov; that page is the FY 2025-2027 "
        "plan directory, not a federal source document. Federal CCDF rules are 45 CFR part 98: not in the corpus "
        "(no us/regulation title-45-part-98 coverage; no us/regulation/45/98 provisions); the CCDBG Act (42 U.S.C. 9857 et seq.) "
        "appears only as scattered cross-reference rows in other us/statute scopes. Ingest 45 CFR 98 through extract-ecfr "
        "(--only-title 45 --only-part 98) in a separate run; not re-ingested here."
    )
    in_manual["name"] = "Indiana (CCDF Policy Manual, FSSA Office of Early Childhood and Out-of-School Learning)"
    in_manual["queue_status"] = "needs_review"
    in_manual["source_kind"] = "official_pdf_agency_manual"
    in_manual["primary_source_url"] = "https://www.in.gov/fssa/carefinder/files/CCDF-Policy-Manual.pdf"
    in_manual["target_scope"] = {"jurisdiction": "us-in", "document_class": "manual", "version": f"{SOURCE_AS_OF}-ccdf-in-policy-manual"}
    in_manual["index_url"] = IN_MANUAL_INDEX
    in_manual["index_document_count"] = IN_MANUAL_INDEX_COUNT
    in_manual["taken_count"] = 0
    in_manual["notes"] = IN_MANUAL_NOTE
    queue["status_counts"] = {}
    for s in states:
        queue["status_counts"][s["queue_status"]] = queue["status_counts"].get(s["queue_status"], 0) + 1
    queue["states"] = states
    queue["queue_status"] = "in_progress"
    queue["index_inventory"] = {
        "index_url": INDEX,
        "lead_list_url": INDEX_LEAD,
        "reviewed": SOURCE_AS_OF,
        "jurisdictions": len(rows),
        "families": {
            "state_plan_links": {"count": len(rows), "direct_pdf": len(direct_pdf), "lead_agency_pages": len(rows) - len(direct_pdf), "hosted_by": "state/territory Lead Agency", "taken": written},
            "acf118_appendix_pdfs": {"count": len(appendix), "hosted_by": "acf.gov", "taken": 0, "note": "Lead Agency implementation plans for federal non-compliances; separate family, not taken"},
            "preprint_instructions": {"count": 0}, "amendments": {"count": 0, "note": "amendments are posted on Lead Agency pages, not on the ACF index"},
        },
    }
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    print(f"wrote {written} manifests; queue {queue['status_counts']}; ca bundle {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
