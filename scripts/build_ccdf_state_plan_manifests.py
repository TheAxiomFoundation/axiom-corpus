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

import argparse
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

# Re-probe 2026-09-13T19:57Z (docs/ingest-runs/2026-09-13-blocked-publishers-reprobe.md): every blocked row's
# Lead Agency URL was fetched once with the plain extractor client from a US network. GA and TX now answer and
# are extracted into their own scope version (REPROBE_SCOPE, applied with --only ga,tx); AS, AZ, MD, MO, NY and
# MP fail as on 2026-09-10 and their block is recorded as durable (two networks, two dates).
REPROBE_STAMP = "2026-09-13T19:57Z"
REPROBE_SCOPE = {"source_as_of": "2026-09-13", "scope_version": "2026-09-13-ccdf-plan-fy2025-2027"}
DURABLE = ("durable block: the same failure from two networks (the 2026-09-10 non-US and US exits) on two dates "
           "(2026-09-10 and 2026-09-13), so the dashboard should treat the cell as not available rather than pending")

# Reviewed 2026-09-10 by following each ACF index "plan" link to the Lead Agency page.
# taken: (plan_url, publisher_index_url, source_format, plan_version, plan_status, extra)
# blocked/needs_review: (publisher_index_url, reason)
RESOLUTIONS: dict[str, dict] = {
    "al": {"status": "agent_ready", "url": "https://dhr.alabama.gov/wp-content/uploads/2023/04/2025-2027-CCDF-State-Plan-with-Approval-Letter.pdf",
               "index": "https://dhr.alabama.gov/child-care/", "version": "Initial Plan", "plan_status": "Approved (state PDF prefixed with the ACF approval letter; 301 pages)"},
    "ak": {"status": "needs_review", "index": "https://aws.state.ak.us/OnlinePublicNotices/Notices/View.aspx?id=215530",
               "reason": "retry 2 2026-09-10T21:35Z from a US network: aws.state.ak.us now answers (first two passes: TCP connect timeout); the Online Public Notice the ACF index links carries one attachment, '2025-2027 CCDF State Plan 052424.pdf' (Attachment.aspx?id=148401, 213 pages, Microsoft Word export dated 2024-05-24, no CARS Plan Status line, text refers to 'this draft CCDF Plan' posted for public comment); the Department of Health Child Care Program Office page lists no CCDF plan; no approved or certified FFY 2025-2027 plan is posted, so not extracted"},
    "as": {"status": "blocked_primary_source", "index": "https://www.dhss.as/index.html",
               "reason": "TLS: www.dhss.as presents a self-signed, expired certificate (CN=cmaster70); verification impossible, not disabled; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (SSLCertVerificationError / curl 60 self-signed, expired certificate); retried 2026-09-11T21:15Z from a US network (territories pass), same failure: openssl reports the self-signed CN=cmaster70 certificate with verify return code 10 (certificate has expired), curl 60 for the plain client and for curl_cffi chrome120 alike; the plain-HTTP site http://dhss.as/index.html answers 200 but its Child Care, ASNAP and ASWIC menu entries all point at the 'coming.html' placeholder, so no plan is posted there either; "
                         f"re-probed {REPROBE_STAMP} from a US network with the plain extractor client, same failure (SSLCertVerificationError: self-signed certificate, 0.6 s; the plain-HTTP index still answers HTTP 200, 12,095 bytes, 1.0 s with the placeholder menu); {DURABLE}"},
    "az": {"status": "blocked_primary_source", "index": "https://des.az.gov/services/child-and-family/child-care/child-care-and-development-fund-state-plan",
               "reason": "HTTP 403 (cloudflare) for requests with browser UA and curl_cffi chrome120/safari17_0/edge101; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (HTTP 403 cloudflare for plain requests and chrome impersonation); "
                         f"re-probed {REPROBE_STAMP} from a US network with the plain extractor client, same failure (HTTP 403, 5,958 bytes, 0.1 s, Cloudflare 'Just a moment...' challenge page); {DURABLE}"},
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
    "ga": {"status": "agent_ready", "url": "https://www.decal.ga.gov/documents/attachments/CCDFStatePlan25-27.pdf",
               "index": "https://www.decal.ga.gov/BftS/CCDFPlan.aspx", "version": "Amendment 2",
               "plan_status": ("Approved as of 2026-02-13 ('Child Care and Development Fund (CCDF) State Plan FFY 2025-2027' on the DECAL CCDF Plan page, "
                               "the only FFY 2025-2027 plan version posted; the CARS print carries 'Amendment 2'; the FFY 2025 executive summary, "
                               f"public-hearing notice, acronym list and QPRs are posted separately, not taken; located on the {REPROBE_STAMP} "
                               "re-probe from a US network with the plain extractor client (HTTP 200, 81,837 bytes, 0.7 s; the PDF 3,483,574 bytes, "
                               "Last-Modified 2026-02-25) after connection resets on all three 2026-09-10 passes)"),
               **REPROBE_SCOPE},
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
               "reason": "landing page 200; the linked plan page https://earlychildhood.marylandpublicschools.org/2025-2027-ccdf-plan returns HTTP 403 'Access denied'; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (HTTP 403 cloudflare on the 2025-2027-ccdf-plan page for plain and impersonated requests; the about/ccdf-state-plan landing page answers 200 and links only that page); "
                         f"re-probed {REPROBE_STAMP} from a US network with the plain extractor client, same failure (landing page HTTP 200, 117,379 bytes, 0.5 s; the 2025-2027-ccdf-plan page HTTP 403, 107,539 bytes, 'Access denied' page served by cloudflare); {DURABLE}"},
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
               "reason": "plan link https://dese.mo.gov/media/pdf/acf-118-ccdf-ffy-2025-2027-missouri returns an HTML Drupal antibot form (HTTP 200) instead of the PDF for requests and curl_cffi chrome120; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (HTTP 200 text/html Drupal antibot form with an Incapsula script instead of the PDF, plain and impersonated; the landing page also lists Amendment #1 and 'Current' Amendment #2 behind the same media path); "
                         f"re-probed {REPROBE_STAMP} from a US network with the plain extractor client, same failure (landing page HTTP 200, 81,955 bytes, 0.1 s, with the Incapsula script; the plan media path HTTP 200 text/html 52,900 bytes and the Amendment #2 media path HTTP 200 text/html 60,052 bytes, both the Drupal antibot form instead of a PDF); {DURABLE}"},
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
               "reason": "ocfs.ny.gov returns an F5/Shape JavaScript bot-challenge page (TSPD) instead of the index; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (F5/Shape TSPD JavaScript challenge page, 7.5 KB, plain and impersonated); "
                         f"re-probed {REPROBE_STAMP} from a US network with the plain extractor client, same failure class (connection reset by peer after 0.1 s, no response); {DURABLE}"},
    "nc": {"status": "agent_ready", "url": "https://ncchildcare.ncdhhs.gov/Portals/0/documents/pdf/A/ACF-118_CCDF_FFY_2025-2027_For_North_Carolina_November_2024.pdf?ver=5Qk3uXFjaCh3xyBqG3faZg%3d%3d",
               "index": "https://ncchildcare.ncdhhs.gov/Services/Child-Care-Development-Fund-CCDF", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (Amendment 2 consolidated plan and the Appendix posted separately, not taken)"},
    "nd": {"status": "agent_ready", "url": "https://www.hhs.nd.gov/sites/default/files/documents/website-archive/human-services/2025-2027-ccdfstateplan-initial-archived.pdf",
               "index": "https://www.hhs.nd.gov/cfs/early-childhood-services/child-care-development-fund", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 (Amendment 1, Amendment 2 and Appendix posted separately, not taken)"},
    "mp": {"status": "blocked_primary_source", "index": "https://www.childcare.gov.mp/",
               "reason": "HTTP 403 (nginx) for requests with browser UA and curl_cffi chrome120/safari17_0/edge101; retried 2026-09-10T18:36Z, same failure; retried 2026-09-10T21:35Z from US network, same failure (HTTP 403 nginx); retried 2026-09-11T21:15Z from a US network (territories pass), same failure (HTTP 403, server nginx/1.29.8, 358-byte body, for the plain browser UA and curl_cffi chrome120; the parent Department of Community and Cultural Affairs site www.dcca.gov.mp answers the same 403); "
                         f"re-probed {REPROBE_STAMP} from a US network with the plain extractor client, same failure (HTTP 403, 358 bytes, 2.5 s, nginx/1.29.8 '403 Forbidden'); {DURABLE}"},
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
               "reason": "publisher's documents page lists only 'Borrador Plan Estatal Child Care 2025-2027' (draft) plus hearing notices and supporting studies; no approved plan; retried 2026-09-10: unchanged (draft, hearing notice, 'Fee Scale State Plan 2025-2027' supporting document, emergency plan); no approved or certified plan; re-read 2026-09-11T21:15Z (territories pass): unchanged, the documents page (84 file links) still lists only the 'Borrador Plan Estatal Child Care 2025-2027' draft with its hearing notice, fee-scale study and emergency-plan attachments, plus the Child Care 2026-27 proposal guide and forms and the adopted Reglamento del Programa Child Care (Num. 8687 de 2016), which is a separate regulation family"},
    "ri": {"status": "agent_ready", "url": "https://dhs.ri.gov/media/8381/download?language=en",
               "index": "https://dhs.ri.gov/regulations/state-plans", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('Child Care Development Fund State Plan FFY25-27'; located on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 cloudflare on the first two passes)"},
    "sc": {"status": "agent_ready", "url": "https://scchildcare.org/media/bxkiasbl/acf-118-ccdf-ffy-2025-2027-for-south-carolina-approved-state-plan.pdf",
               "index": "https://www.scchildcare.org/resources/", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('Child Care Development Fund State Plan FFY 2025-2027 Approved State Plan' on the SC Child Care resources page, which redirects to scchildcare.org; located on retry 2 2026-09-10T21:35Z from a US network after TCP connect timeouts on the first two passes)"},
    "sd": {"status": "agent_ready", "url": "https://dss.sd.gov/docs/childcare/state_plan/2025-2027/2025-2027_State_Plan_original.pdf",
               "index": "https://dss.sd.gov/childcare/stateplan/default.aspx", "version": "Initial Plan", "plan_status": "Certified as of 2024-09-24 ('original'; Amendments 1-3 consolidated plans posted separately, not taken)"},
    "tn": {"status": "agent_ready", "url": "https://www.tn.gov/content/dam/tn/human-services/documents/CCDF%20State%20Plan%20FFY%202025-2027%20Tennessee.pdf",
               "index": "https://www.tn.gov/humanservices/information-and-resources/tdhs-reports-and-information.html", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('CCDF State Plan FFY 2025-2027' on the TDHS Reports and Information page; Appendix 1 and two transitional waiver approvals are posted separately, not taken; located on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 awselb on the first two passes; one of three page requests on the retry ended with an SSL unexpected EOF, the others answered 200)"},
    "tx": {"status": "agent_ready", "url": "https://www.twc.texas.gov/sites/default/files/ccel/docs/ffy-2025-2027-ccdf-state-plan-amendment-1-accessible.pdf",
               "index": "https://www.twc.texas.gov/programs/child-care/data-reports-plans", "version": "Amendment 1",
               "plan_status": ("Approved as of 2026-07-01 ('Child Care and Development Fund 2025-2027 State Plan Amendment 1' on the TWC Child Care "
                               "Data, Reports & Plans page, the only FFY 2025-2027 plan version posted; the page links the ACF-hosted Appendix "
                               f"separately, not taken; located on the {REPROBE_STAMP} re-probe from a US network with the plain extractor client "
                               "(HTTP 200, 122,911 bytes, 0.2 s; the PDF 2,910,861 bytes, Last-Modified 2026-08-03) after HTTP 403 CloudFront and "
                               "an HTTP 202 AWS WAF challenge on the three 2026-09-10 passes)"),
               **REPROBE_SCOPE},
    "ut": {"status": "agent_ready", "url": "https://jobs.utah.gov/occ/ccdfplan.pdf",
               "index": "https://jobs.utah.gov/occ/plans.html", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('2025-2027 State Plan' on the OCC Plans and Reports page; the state-hosted Appendix is posted separately, not taken; located on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 awselb on the first two passes)"},
    "vt": {"status": "agent_ready", "url": "https://outside.vermont.gov/dept/DCF/Shared%20Documents/CDD/Reports/CCDF-Plans/CCDF-Plan-2025-2027-Approved.pdf",
               "index": "https://dcf.vermont.gov/CDD/CCDF", "version": "Initial Plan", "plan_status": "Approved as of 2024-11-09 ('CCDF-Plan-2025-2027-Approved'; the PDF answered HTTP 200 on retry 2 2026-09-10T21:35Z from a US network after HTTP 403 on the first two passes; the plan embeds Vermont's child care licensing rules inside section 5.3, whose numbered rule headings (5.3, 5.6, 9.1-9.4, 13.1) collide with the preprint labels, so the section pattern is restricted to the 41 preprint headings)", "extraction": VT_EXTRACTION},
    "vi": {"status": "needs_review", "index": "https://dhs.vi.gov/child-care-regulatory/",
               "reason": "publisher's site lists only a CCDF preprint draft for FFY 2019-2021; no FFY 2025-2027 plan found; retried 2026-09-10: the home page still lists the 2019-2021 preprint draft and the Office of Child Care & Regulatory Services page lists the FFY 2022-2024 plan (submitted 2021-09-17), policy memoranda and the 2022 market rate survey; site search for 'CCDF 2025' returns nothing; no FFY 2025-2027 plan; re-read 2026-09-11T21:15Z (territories pass): unchanged, the Office of Child Care & Regulatory Services page (36 PDFs) lists the FFY 2022-2024 plan (submitted 9-17-2021), the 2019 policy memoranda 101-106, the subsidy rules, the 2022 market rate survey and the ACF-218 QPR for FFY 2022; no FFY 2025-2027 plan"},
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



def ready_row_fields(code: str, name: str, res: dict, appendix_url: str | None) -> dict:
    """Write the one-document manifest of an agent_ready jurisdiction and return its queue-row fields.

    A resolution may pin its own ``scope_version`` and ``source_as_of`` (the 2026-09-13 re-probe scope for GA
    and TX); every other jurisdiction stays on the run-wide VERSION / SOURCE_AS_OF."""
    jur = f"us-{code}"
    fmt = res.get("source_format", "pdf")
    version = res.get("scope_version", VERSION)
    stem = f"{jur}-ccdf-state-plan-fy{FY}"
    doc = {
        "source_id": f"{jur}-acf-ccdf-plan-fy{FY}",
        "jurisdiction": jur,
        "document_class": "policy",
        "title": f"{name} CCDF Plan, FFY {FY}",
        "source_url": res["url"],
        "source_format": fmt,
        "source_as_of": res.get("source_as_of", SOURCE_AS_OF),
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
        "acf_appendix_url": appendix_url,
        "source_discovery_group": f"{jur}/policy/ccdf",
        "discovered_via": "manual-review:ccdf-agent-queue; index https://acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027",
    }
    if res.get("tls"):
        doc["metadata"]["tls_note"] = "server omits its intermediate certificate; extraction uses REQUESTS_CA_BUNDLE = certifi + data/certs/sectigo-public-server-authentication-ca-ov-r36.pem"
    manifest = {"version": version, "documents": [doc]}
    (ROOT / "manifests" / f"{stem}.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120))
    return {
        "queue_status": "agent_ready",
        "publisher_index_url": res["index"],
        "target_scope": {"jurisdiction": jur, "document_class": "policy", "version": version},
        "source_kind": "official_html_state_plan" if fmt == "html" else "official_pdf_state_plan",
        "primary_source_url": res["url"],
        "target_manifest": f"manifests/{stem}.yaml",
        "taken_count": 1,
        "notes": f"FFY {FY} ACF-118 CCDF Plan ({res['version']}; {res['plan_status']}) located on the Lead Agency page linked from the ACF index; extraction proven. The ACF-hosted Appendix on the index is a separate document family, not taken.",
    }


def refresh_rows_only(codes: list[str]) -> dict[str, int]:
    """Refresh the queue rows of the listed jurisdictions from RESOLUTIONS without fetching the ACF index
    (territories pass, 2026-09-11: AS, MP, PR, VI re-probed; re-probe 2026-09-13: GA and TX extracted, the
    other blocked rows re-recorded). A newly agent_ready row gets its manifest written from the ACF index
    facts the row already carries (index_plan_link, index_appendix_url); no other manifest is touched."""
    queue_path = ROOT / "manifests" / "ccdf-agent-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    rows = {s["jurisdiction"]: s for s in queue["states"]}
    for code in codes:
        res = RESOLUTIONS[code]
        row = rows[f"us-{code}"]
        if res["status"] == "agent_ready":
            row.update(ready_row_fields(code, row["name"], res, row.get("index_appendix_url")))
            continue
        row["queue_status"] = res["status"]
        row["publisher_index_url"] = res["index"]
        row["notes"] = (
            ("Publisher blocked: " if res["status"] == "blocked_primary_source" else "Not extracted: ")
            + res["reason"] + ". Nothing was worked around."
        )
    queue["status_counts"] = {}
    for s in queue["states"]:
        queue["status_counts"][s["queue_status"]] = queue["status_counts"].get(s["queue_status"], 0) + 1
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]



# --------------------------------------------------------------------------------------
# 2026-09-13 follow-up families (docs/ingest-runs/2026-09-13-acf-state-plans.md).
# The closure check (docs/coverage/needs-closure-2026-09-11/ccdf.md) found the ACF-hosted
# Appendix 1 PDFs inventoried but never taken (ccdf-s27, 51 states), the separately posted
# amended plans not taken (ccdf-s28) and the current-year rate and copay schedules not
# inventoried (ccdf-s30). ``--family appendices|amendments|rate-schedules`` builds those
# manifests and records them on the existing queue rows under ``additional_families`` so
# the queue keeps one row per jurisdiction.
# --------------------------------------------------------------------------------------
FOLLOWUP_AS_OF = "2026-09-13"
APPENDIX_VERSION = f"{FOLLOWUP_AS_OF}-ccdf-state-plan-appendices"
AMENDMENT_VERSION = f"{FOLLOWUP_AS_OF}-ccdf-state-plan-amendments"
RATE_VERSION = f"{FOLLOWUP_AS_OF}-ccdf-rate-schedules"
STATES_51 = sorted(code for name, code in CODES.items() if code not in {"as", "gu", "mp", "pr", "vi"})

# Appendix 1 (Lead Agency implementation plan for federal non-compliances) is a CARS export
# with one all-caps "AREA:TOPIC" finding heading per non-compliance. The 40 headings that occur
# across the 51 PDFs (read 2026-09-13) map to slug-safe citation segments; a heading outside
# this vocabulary would surface as an uppercase path and fail the post-extraction check.
APPENDIX_FINDING_SLUGS = {
    "COMPREHENSIVE BACKGROUND CHECK:BACKGROUND CHECK PROCESSES": "comprehensive-background-check-background-check-processes",
    "COMPREHENSIVE BACKGROUND CHECK:DISQUALIFICATIONS FOR EMPLOYMENT": "comprehensive-background-check-disqualifications-for-employment",
    "COMPREHENSIVE BACKGROUND CHECK:IN-STATE": "comprehensive-background-check-in-state",
    "COMPREHENSIVE BACKGROUND CHECK:INTER-STATE": "comprehensive-background-check-inter-state",
    "COMPREHENSIVE BACKGROUND CHECK:NATIONAL FINGERPRINT": "comprehensive-background-check-national-fingerprint",
    "COMPREHENSIVE BACKGROUND CHECK:NATIONAL NAME-BASED": "comprehensive-background-check-national-name-based",
    "COMPREHENSIVE BACKGROUND CHECK:PRE-SERVICE CHECK REQUIREMENTS": "comprehensive-background-check-pre-service-check-requirements",
    "COMPREHENSIVE BACKGROUND CHECK:5 YEAR RENEWAL": "comprehensive-background-check-5-year-renewal",
    "CONSUMER EDUCATION:WEBSITE AND RESOURCES FOR PARENTS": "consumer-education-website-and-resources-for-parents",
    "ELIGIBILITY AND ENROLLMENT:CONTINUITY OF CARE (12-MONTH ELIGIBILITY)": "eligibility-and-enrollment-continuity-of-care-12-month-eligibility",
    "ELIGIBILITY AND ENROLLMENT:ELIGIBILITY": "eligibility-and-enrollment-eligibility",
    "ELIGIBILITY AND ENROLLMENT:PRIORITIZATION OF POPULATIONS": "eligibility-and-enrollment-prioritization-of-populations",
    "EQUAL ACCESS:AFFORDABILITY": "equal-access-affordability",
    "EQUAL ACCESS:PAYMENT PRACTICES": "equal-access-payment-practices",
    "EQUAL ACCESS:PAYMENT RATES": "equal-access-payment-rates",
    "EQUAL ACCESS:PROVIDER OPTIONS FOR PARENTS": "equal-access-provider-options-for-parents",
    "EQUAL ACCESS:SUPPLY BUILDING STRATEGIES": "equal-access-supply-building-strategies",
    "HEALTH AND SAFETY:ADMINISTRATION OF MEDICATION": "health-and-safety-administration-of-medication",
    "HEALTH AND SAFETY:BUILDING AND PHYSICAL PREMISES SAFETY": "health-and-safety-building-and-physical-premises-safety",
    "HEALTH AND SAFETY:CHILD DEVELOPMENT": "health-and-safety-child-development",
    "HEALTH AND SAFETY:EMERGENCY PREPAREDNESS AND RESPONSE PLANNING": "health-and-safety-emergency-preparedness-and-response-planning",
    "HEALTH AND SAFETY:FIRE STANDARDS": "health-and-safety-fire-standards",
    "HEALTH AND SAFETY:HANDLING AND STORAGE OF HAZARDOUS MATERIALS AND": "health-and-safety-handling-and-storage-of-hazardous-materials-and-disposal-of-biocontaminants",
    "HEALTH AND SAFETY:IDENTIFICATION AND REPORTING OF CHILD ABUSE": "health-and-safety-identification-and-reporting-of-child-abuse",
    "HEALTH AND SAFETY:INSPECTION OF IN-HOME CARE": "health-and-safety-inspection-of-in-home-care",
    "HEALTH AND SAFETY:INSPECTORS": "health-and-safety-inspectors",
    "HEALTH AND SAFETY:ONGOING TRAINING": "health-and-safety-ongoing-training",
    "HEALTH AND SAFETY:PEDIATRIC FIRST AID AND PEDIATRIC CPR": "health-and-safety-pediatric-first-aid-and-pediatric-cpr",
    "HEALTH AND SAFETY:POSTING INSPECTION REPORTS": "health-and-safety-posting-inspection-reports",
    "HEALTH AND SAFETY:PRECAUTIONS IN TRANSPORTING CHILDREN": "health-and-safety-precautions-in-transporting-children",
    "HEALTH AND SAFETY:PREVENTION AND CONTROL OF INFECTIOUS DISEASES": "health-and-safety-prevention-and-control-of-infectious-diseases",
    "HEALTH AND SAFETY:PREVENTION AND RESPONSE TO EMERGENCIES FROM FOOD": "health-and-safety-prevention-and-response-to-emergencies-from-food-and-allergic-reactions",
    "HEALTH AND SAFETY:PREVENTION OF SHAKEN BABY SYNDROME, ABUSIVE HEAD": "health-and-safety-prevention-of-shaken-baby-syndrome-abusive-head-trauma-and-child-maltreatment",
    "HEALTH AND SAFETY:RATIOS AND GROUP SIZE FOR CCDF PROVIDERS": "health-and-safety-ratios-and-group-size-for-ccdf-providers",
    "HEALTH AND SAFETY:RELATIVE EXEMPTIONS": "health-and-safety-relative-exemptions",
    "HEALTH AND SAFETY:SUDDEN INFANT DEATH SYNDROME AND SAFE SLEEP": "health-and-safety-sudden-infant-death-syndrome-and-safe-sleep",
    "LEAD AGENCY RESPONSIBILITIES:PROGRAM ADMINISTRATION, PLAN DEVELOPMENT,": "lead-agency-responsibilities-program-administration-plan-development-and-program-funding-coordination",
    "PROGRAM INTEGRITY:EFFECTIVE FISCAL MANAGEMENT PRACTICES": "program-integrity-effective-fiscal-management-practices",
    "PROGRAM INTEGRITY:EFFECTIVE INTERNAL CONTROLS": "program-integrity-effective-internal-controls",
    "PROGRAM INTEGRITY:FRAUD INVESTIGATION, PAYMENT RECOVERY, AND": "program-integrity-fraud-investigation-payment-recovery-and-sanctions",
    "WORKFORCE:PROFESSIONAL DEVELOPMENT": "workforce-professional-development",
}
APPENDIX_EXTRACTION = {
    "segmentation": "labeled_sections",
    # One finding per all-caps "AREA:TOPIC" line; wrapped headings continue on the next
    # all-caps line ("TRAUMA, AND CHILD MALTREATMENT", "(PROVISIONAL HIRE)").
    "section_heading_pattern": r"^(?P<label>[A-Z][A-Z0-9 ,&/()'’-]*:[A-Z][A-Z0-9 ,&/()'’-]*)$",
    "heading_continuation_pattern": r"^(?P<heading>[A-Z(][A-Z0-9 ,&/()'’-]*)$",
    "section_label_replacements": APPENDIX_FINDING_SLUGS,
    "start_after_pattern": r"^Plan Status: .*$",
}

# Separately posted FFY 2025-2027 amendments (consolidated CARS prints unless noted), read from
# the Lead Agency pages on 2026-09-13. MI posts Amendment 1 and 2 but its taken plan already is the
# Amendment 2 print (2026-09-10 run); MO's amendments sit behind the blocked dese.mo.gov media path.
# (label, url, version text, approved-as-of date, extra)
AMENDMENTS: dict[str, dict] = {
    "ca": {"index": "https://www.cdss.ca.gov/inforesources/child-care-and-development/fund-state-plan", "docs": [
        ("amendment-1", "https://www.cdss.ca.gov/Portals/9/CCDD/2025-27 CCDF State Plan – Amendments 1.pdf", "Amendment 1", None,
         {"extraction": CA_EXTRACTION, "note": "state Word export (CA_EXTRACTION); the print carries no CARS Plan Status line"})]},
    "dc": {"index": "https://osse.dc.gov/publication/dc-child-care-and-development-fund", "docs": [
        ("amendment-1-approval-letter", "https://osse.dc.gov/sites/default/files/dc/sites/osse/publication/attachments/DC%20FFY%202025-2027%20CCDF%20Plan%20Amendment%201%20Approval%20Letter.pdf", "Amendment 1 approval letter", "2024-10-01", {"letter": True}),
        ("amendment-2-approval-letter", "https://osse.dc.gov/sites/default/files/dc/sites/osse/publication/attachments/DC%20FFY%202025-2027%20CCDF%20Plan%20Amendment%202%20Approval%20Letter_0.pdf", "Amendment 2 approval letter", "2026-05-28", {"letter": True})]},
    "ma": {"index": "https://www.mass.gov/lists/child-care-and-development-fund-ccdf-state-plans", "impersonation": True, "docs": [
        ("amendment-1", "https://www.mass.gov/doc/ma-eec-ccdf-state-plan-ffy-2025-2027-amend-1/download", "Amendment 1", "2026-03-02", {}),
        ("amendment-2", "https://www.mass.gov/doc/ma-eec-ccdf-state-plan-ffy-2025-2027-amend-2/download", "Amendment 2", "2026-04-27", {})]},
    "me": {"index": "https://www.maine.gov/dhhs/ocfs/provider-resources/child-care-subsidy-information-for-providers", "docs": [
        ("amendment-1", "https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/inline-files/ACF-118%20CCDF%20FFY%202025-2027%20For%20Maine_Amendment%201.pdf", "Amendment 1", "2025-05-27", {}),
        ("amendment-2", "https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/inline-files/ACF-118%20CCDF%20FFY%202025-2027%20For%20Maine_Amendment%202.pdf", "Amendment 2", "2025-08-18", {}),
        ("amendment-3", "https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/inline-files/ACF-118%20CCDF%20FFY%202025-2027%20For%20Maine_Amendment%203.pdf", "Amendment 3", "2025-12-18", {})],
        "not_taken": "Amendment #4 (6.26.26) link answers HTTP 200 application/pdf with a 0-byte body for plain and browser clients (2026-09-13); not taken"},
    "nc": {"index": "https://ncchildcare.ncdhhs.gov/Services/Child-Care-Development-Fund-CCDF", "docs": [
        ("amendment-2", "https://ncchildcare.ncdhhs.gov/Portals/0/documents/pdf/A/ACF-118_CCDF_FFY_2025-2027_For_North_Carolina.pdf?ver=qMH8KP5I8Z-D2B1zTmbO-w%3d", "Amendment 2", "2026-03-12",
         {"note": "the page's 'with Amendment 1' and 'with Amendment 2' links resolve to the same file (byte-identical, Version: Amendment 2)"})]},
    "nd": {"index": "https://www.hhs.nd.gov/cfs/early-childhood-services/child-care-development-fund", "docs": [
        ("amendment-1", "https://www.hhs.nd.gov/sites/default/files/documents/website-archive/human-services/2025-2027-ccdfstateplan-amendment1-archived.pdf", "Amendment 1", "2025-08-12", {}),
        ("amendment-2", "https://www.hhs.nd.gov/sites/default/files/documents/website-archive/human-services/2025-2027-ccdfstateplan-amendment2-archived.pdf", "Amendment 2", "2026-04-10", {})]},
    "oh": {"index": "https://childrenandyouth.ohio.gov/for-providers/resources/child-care-and-development-fund-state-plan", "docs": [
        ("amendment-1", "https://dam.assets.ohio.gov/image/upload/v1720530796/childrenandyouth.ohio.gov/For%20Providers/CCDF/CCDF_FFY_2025-2027_For_Ohio.pdf", "Amendment 1", "2025-12-18", {}),
        ("amendment-2", "https://dam.assets.ohio.gov/image/upload/childrenandyouth.ohio.gov/For%20Partners%20and%20Providers/CCDF/Amendment%20Approvals/State_Plan_FFY_2025-2027_Amendment_2.pdf", "Amendment 2", "2026-07-16", {})]},
    "or": {"index": "https://www.oregon.gov/delc/about-us/pages/state-plans.aspx", "docs": [
        ("amendment-1", "https://www.oregon.gov/delc/about-us/Documents/ACF-118%20CCDF%20FFY%202025-2027%20For%20Oregon%20Amendment%201.pdf", "Amendment 1", "2025-11-14", {})]},
    "sd": {"index": "https://dss.sd.gov/childcare/stateplan/default.aspx", "docs": [
        ("amendment-1", "https://dss.sd.gov/docs/childcare/state_plan/2025-2027/Amendment_1.pdf", "Amendment 1", "2025-07-09", {}),
        ("amendment-2", "https://dss.sd.gov/docs/childcare/state_plan/2025-2027/Amendment_2.pdf", "Amendment 2", "2026-02-05", {}),
        ("amendment-3", "https://dss.sd.gov/docs/childcare/state_plan/2025-2027/Amendment_3.pdf", "Amendment 3", "2026-05-29", {})]},
    "vt": {"index": "https://dcf.vermont.gov/CDD/CCDF", "docs": [
        ("amendment-1-approval-letter", "https://outside.vermont.gov/dept/DCF/Shared%20Documents/CDD/Reports/CCDF-Plans/CCDF-Plan-2025-2027-Amendment-1-Approval-Letter.pdf", "Amendment 1 approval letter", "2024-10-07", {"letter": True})]},
    "wa": {"index": "https://www.dcyf.wa.gov/about/government-affairs/ccdf", "docs": [
        ("amendment-1", "https://www.dcyf.wa.gov/sites/default/files/pdf/2025-2027-CCDF-Amend1.pdf", "Amendment 1", "2026-05-29", {})]},
}

# Current-year payment rate and copayment schedules posted by the Lead Agency (ccdf-s30). Of the
# 17 publisher pages the 2026-09-10 run notes flagged, 4 post schedules (ME, ID, TN, SC); the other 13
# post market rate survey or narrow cost analysis reports only (the basis for rates, not the
# schedule) and are not taken. NC's Subsidy Services page (one hop from its CCDF page) posts the
# subsidized child care market rate tables and is added.
# (slug, url, title, effective date, source_format, extra)
RATE_SCHEDULES: dict[str, dict] = {
    "id": {"index": "https://healthandwelfare.idaho.gov/providers/child-care-providers/child-care-resources", "agency": "Idaho Department of Health and Welfare, Idaho Child Care Program (ICCP)", "docs": [
        ("iccp-copay-chart-2025-10-01", "https://publicdocuments.dhw.idaho.gov/WebLink/ElectronicFile.aspx?docid=4671&dbid=0&repo=PUBLIC-DOCUMENTS", "Idaho Child Care Copay Chart, effective October 1, 2025", "2025-10-01", "pdf", {"note": "Laserfiche WebLink DocView id=4671 served through the repository's ElectronicFile endpoint"}),
        ("iccp-local-market-rates-2025-07-01", "https://publicdocuments.dhw.idaho.gov/WebLink/ElectronicFile.aspx?docid=19508&dbid=0&repo=PUBLIC-DOCUMENTS", "Idaho Child Care Program Local Market Rates, effective July 1, 2025", "2025-07-01", "pdf", {"note": "Laserfiche WebLink DocView id=19508"})]},
    "me": {"index": "https://www.maine.gov/dhhs/ocfs/provider-resources/child-care-subsidy-information-for-providers", "agency": "Maine DHHS Office of Child and Family Services, Child Care Affordability Program (CCAP)", "docs": [
        ("child-care-market-rates-2025-05-19", "https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/inline-files/5.19.25%20Child%20Care%20Market%20Rates.pdf", "Maine Child Care Market Rates (maximum rates by county and setting), May 19, 2025", "2025-05-19", "pdf", {}),
        ("ccap-parent-fee-guide-fy26", "https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/inline-files/CCAP%20Parent%20Fee%20Guide%20%28FY26%29.pdf", "CCAP Parent Fee Guide (FY26), effective April 18, 2026", "2026-04-18", "pdf", {}),
        ("ccap-income-guidelines-2026-04-18", "https://www.maine.gov/dhhs/sites/maine.gov.dhhs/files/inline-files/4.18.26%20125%20CCAP%20income%20guidelines.docx", "CCAP Current Income Guidelines (125% SMI), April 18, 2026", "2026-04-18", "docx", {"note": "posted as a Word document; the page labels the link (PDF)"})]},
    "nc": {"index": "https://ncchildcare.ncdhhs.gov/Home/DCDEE-Sections/Subsidy-Services/Market-Rates", "agency": "North Carolina DHHS Division of Child Development and Early Education, Subsidized Child Care Assistance", "docs": [
        ("subsidized-market-rates-centers-2023-10-01", "https://ncchildcare.ncdhhs.gov/Portals/0/documents/pdf/M/Market_Rates_Centers_Eff_10-1.pdf?ver=9w52alSPhmrmo0N9gGVMEw%3d%3d", "Subsidized Child Care Market Rates for Child Care Centers, effective October 1, 2023 (current)", "2023-10-01", "pdf", {}),
        ("subsidized-market-rates-homes-2023-10-01", "https://ncchildcare.ncdhhs.gov/Portals/0/documents/pdf/M/Mkt_Rates_Homes_eff_10-1.pdf?ver=baC5Yg7ZMrQ5fck2y9CcvA%3d%3d", "Subsidized Child Care Market Rates for Family Child Care Homes, effective October 1, 2023 (current)", "2023-10-01", "pdf", {}),
        ("subsidized-market-rates-centers-2026-10-01", "https://ncchildcare.ncdhhs.gov/Portals/0/documents/pdf/S/SCCA_Centers_Market_Rates_Eff__10-01-26_Revised_8-18-26.pdf?ver=4UnzSmTrx2JM-mBPjTDgtQ%3d%3d", "Subsidized Child Care Market Rates for Child Care Centers, effective October 1, 2026 (revised August 18, 2026)", "2026-10-01", "pdf", {}),
        ("subsidized-market-rates-homes-2026-10-01", "https://ncchildcare.ncdhhs.gov/Portals/0/documents/pdf/S/SCCA_Homes_Market_Rates_Eff__10-01-26_Revised_8-18-26.pdf?ver=XOzbwZaQgjWdrte2IHJd3w%3d%3d", "Subsidized Child Care Market Rates for Family Child Care Homes, effective October 1, 2026 (revised August 18, 2026)", "2026-10-01", "pdf", {})]},
    "sc": {"index": "https://scchildcare.org/resources/", "agency": "South Carolina Department of Social Services, SC Child Care Scholarship Program", "docs": [
        ("scholarship-fee-scale-2025-2026", "https://scchildcare.org/media/ih2mrjw5/fee-scale-2025-2026.pdf", "SC Child Care Scholarship Program Fee Scale, October 1, 2025 - September 30, 2026", "2025-10-01", "pdf", {}),
        ("scholarship-maximum-payments-ffy2026", "https://scchildcare.org/media/gpok20jb/maxrates.pdf", "SC Child Care Scholarship Maximum Payments Allowed, October 1, 2025 - September 30, 2026", "2025-10-01", "pdf", {"note": "the page labels it FFY 2025; the document covers 10/1/2025-9/30/2026"}),
        ("child-care-income-standards-2025-2026", "https://scchildcare.org/media/pskhwthx/income-guidelines-2025-2026.pdf", "Child Care Income Standards, 2025-2026", "2025-10-01", "pdf", {})]},
    "tn": {"index": "https://www.tn.gov/humanservices/information-and-resources/tdhs-reports-and-information.html", "agency": "Tennessee Department of Human Services, Child Care Certificate Program", "docs": [
        ("income-eligibility-limits-and-copay-fees-2025-10-01", "https://www.tn.gov/content/dam/tn/human-services/documents/Income%20Eligibility%20Limits%20and%20CoPay%20Chart%2010.1.25.pdf", "Child Care Certificate Program Income Eligibility Limits and Parent Co-Pay Fees, effective October 1, 2025", "2025-10-01", "pdf", {}),
        ("provider-reimbursement-rates-2026-01-01", "https://www.tn.gov/content/dam/tn/human-services/documents/Reimbursement_Rate_Chart_1.1.26.pdf", "Child Care Certificate Program Provider Weekly Reimbursement Rates including QRIS Scorecard Bonus Payments, effective January 1, 2026", "2026-01-01", "pdf", {})]},
}
# The 12 other run-note pages list market rate survey / narrow cost analysis reports only.
RATE_PAGES_REPORTS_ONLY = {
    "ky": "market rate surveys (2017, 2020, 2023) on the DCC page; no rate or copay schedule",
    "ut": "2021 and 2024 Child Care Market Rate Studies on the OCC Plans and Reports page; no schedule",
    "mn": "dcyf.mn.gov page (impersonated) lists the plan and the QPR only; no schedule",
    "nj": "childcarenj.gov home lists CCAP application pages only; the 2017-18 and 2021-22 MRS reports the run note recorded were not on the page read 2026-09-13; no schedule",
    "co": "2021-22 Colorado Market Rate Survey Report (Google Drive) on the CDEC State Plans page; no schedule",
    "ct": "2024 Market Rate Survey and Methodology Report, 2022 MRS and analysis on the OEC CCDF page; no schedule",
    "la": "2017, 2020, 2023 Louisiana Child Care Market Rate Surveys on the LDOE policy guidance page; no schedule",
    "or": "2022 alternate rate-setting structure legislative report on the DELC State Plans page; no schedule",
    "va": "the Virginia child care plan page lists the plan only (AkamaiGHost 403 to plain clients); no schedule",
    "ri": "the DHS State Plans page lists CCDF plans and amendments only; no schedule",
    "pa": "the DHS Early Learning and Child Care resources page lists the plan; the 2025 MRS report the run note recorded is a survey, not a schedule",
    "ms": "2021/2024 market rate surveys and the 2024 Narrow Cost Analysis on the ECCD Reports and Archives page; no schedule",
    "vt": "Child Care Market Rate Survey 2024 on the CDD CCDF page; no schedule",
}


# Wave 5 (2026-09-15, needs-closure-2026-09-14 ccdf-s30): the 13 EXTRACTABLE rate-schedule cells were re-read
# one hop past the Lead Agency index page. Four states post the operative schedules (MS, UT, VT, WI: WI was a
# REVIEW cell); the other ten pages and their program sub-pages still post only survey reports or no schedule.
WAVE5_AS_OF = "2026-09-15"
RATE_SCHEDULES_WAVE5: dict[str, dict] = {
    "ms": {"index": "https://www.mdhs.ms.gov/eccd/parents/pay/", "agency": "Mississippi Department of Human Services, Division of Early Childhood Care and Development (Child Care Payment Program)", "docs": [
        ("ccpp-copayment-fee-scale-2021-11-01", "https://www.mdhs.ms.gov/wp-content/uploads/2021/11/Copay-Table-Update-11_01_21.pdf", "Child Care Payment Program Family Co-Pay Fee Scale (Table 1), effective November 1, 2021", "2021-11-01", "pdf", {"note": "linked as 'Co-payment Fee Scale' from the ECCD Child Care Co-Payments page (one hop from the Reports and Archives index); the current schedule the page presents"})]},
    "ut": {"index": "https://jobs.utah.gov/occ/provider/subsidy.html", "agency": "Utah Department of Workforce Services, Office of Child Care", "docs": [
        ("income-eligibility-and-copayments-2025-10-01", "https://jobs.utah.gov/occ/provider/table1025.pdf", "Child Care Income Eligibility and Co-Payment Table (Table 4), effective October 1, 2025", "2025-10-01", "pdf", {}),
        ("income-eligibility-and-copayments-2026-10-01", "https://jobs.utah.gov/occ/provider/table1026.pdf", "Child Care Income Eligibility and Co-Payment Table (Table 4), effective October 1, 2026", "2026-10-01", "pdf", {"note": "posted 2026-08-28 as the forthcoming table"}),
        ("maximum-monthly-subsidy-payments-2024-10-01", "https://jobs.utah.gov/occ/provider/table30824.pdf", "Maximum Monthly Child Care Payments Based on Monthly Local Market Rates (Table 3), effective October 1, 2024", "2024-10-01", "pdf", {})]},
    "vt": {"index": "https://dcf.vermont.gov/cdd/providers/care/ccfap", "agency": "Vermont Department for Children and Families, Child Development Division (CCFAP)", "docs": [
        ("ccfap-state-rates-2025-07-13", "https://outside.vermont.gov/dept/DCF/Policies%20Procedures%20Guidance/CDD-Guidance-CCFAP-Capped-Rates.pdf", "Child Care Financial Assistance State Rates, effective July 13, 2025", "2025-07-13", "pdf", {"note": "linked as 'Revised State Rates' from the CCFAP For Providers page"}),
        ("ccfap-income-guidelines-2025-03-23", "https://outside.vermont.gov/dept/DCF/Policies%20Procedures%20Guidance/CCFAP-Income-Guidelines.pdf", "Child Care Financial Assistance Income Guidelines (family share by income and household size), effective March 23, 2025", "2025-03-23", "pdf", {"note": "linked from the CCFAP benefits page https://dcf.vermont.gov/benefits/ccfap"})]},
    "wi": {"index": "https://dcf.wisconsin.gov/wishares/maxrates", "agency": "Wisconsin Department of Children and Families (Wisconsin Shares Child Care Subsidy)", "docs": [
        ("wisconsin-shares-maximum-rates-2025-10-01", "https://dcf.wisconsin.gov/files/wishares/pdf/max-rates-statewide.pdf", "2025 Wisconsin Shares Child Care Subsidy County and Tribal Maximum Rates, effective October 1, 2025", "2025-10-01", "pdf", {}),
        ("wisconsin-shares-copayment-schedule-2026-02-01", "https://dcf.wisconsin.gov/files/wishares/pdf/wishares-copay-schedule.pdf", "Wisconsin Shares Copayment Schedule, effective February 1, 2026", "2026-02-01", "pdf", {})]},
}
RATE_PAGES_REVIEWED_WAVE5 = {
    "co": "cdec.colorado.gov/resources/state-plans answers HTTP 403 (CloudFront 'request could not be satisfied') to the plain client, the block the 2026-09-10 retry note recorded; no impersonation is documented for the host",
    "ct": "the OEC CCDF page lists the 2024/2022/2018 market rate survey reports and the Care 4 Kids overview page lists no rate or fee document; no schedule",
    "ky": "the DCC page lists the KICCS provider portal and market rate surveys; no rate or copay schedule linked",
    "la": "the LDOE policy guidance page lists the 2017/2020/2023 market rate surveys; the CCAP Providers page links the 2018 CCAP Provider Guide only; no schedule",
    "mn": "dcyf.mn.gov/child-care-and-development-fund answered the plain client (HTTP 200) but lists the plan and QPR only; no rate or copay schedule linked",
    "nj": "childcarenj.gov answers HTTP 403 (Cloudflare 'Attention Required') to the plain client, the block the 2026-09-10 retry note recorded",
    "or": "the DELC State Plans page lists the 2022 alternate rate-setting report and the advisory-committee application only; no ERDC rate or copay schedule linked",
    "pa": "the DHS Early Learning and Child Care page and its Child Care Works page link the 2025 MRS reports, the application and the eligibility regulations; no maximum child care allowance or copay schedule linked",
    "ri": "the DHS State Plans page lists CCDF plans, amendments and the SSI/overpayment pages only; no schedule",
    "va": "www.childcare.virginia.gov answered HTTP 503 to the plain client on 2026-09-15 (AkamaiGHost 403 on 2026-09-10); not re-probed with impersonation",
}


def _followup_metadata(jur: str, *, subtype: str, index: str, discovered: str) -> dict:
    return {
        "primary_source": True,
        "source_authority": AUTHORITY,
        "document_subtype": subtype,
        "program": "CCDF",
        "form": "ACF-118",
        "fiscal_years": FY,
        "plan_period": "2024-10-01 to 2027-09-30",
        "central_index_url": INDEX,
        "publisher_index_url": index,
        "source_discovery_group": f"{jur}/policy/ccdf",
        "discovered_via": discovered,
    }


def attach_family(queue: dict, jurisdiction: str, entry: dict) -> None:
    """Record a follow-up family on the jurisdiction's existing plan row (one row per jurisdiction)."""
    rows = [s for s in queue["states"] if s["jurisdiction"] == jurisdiction
            and (s.get("target_scope") or {}).get("document_class") == "policy"]
    if not rows:
        raise SystemExit(f"{jurisdiction}: no plan row in the queue")
    row = rows[0]
    families = [f for f in row.get("additional_families", []) if f.get("family") != entry["family"]]
    families.append(entry)
    row["additional_families"] = families


def build_appendices(queue: dict, appendix_urls: dict[str, str]) -> int:
    written = 0
    for code in STATES_51:
        jur = f"us-{code}"
        name = next(n for n, c in CODES.items() if c == code)
        url = appendix_urls[code]
        doc = {
            "source_id": f"{jur}-acf-ccdf-plan-fy{FY}-appendix-1",
            "jurisdiction": jur,
            "document_class": "policy",
            "title": f"{name} CCDF Plan FFY {FY}, Appendix 1: Lead Agency Implementation Plan",
            "source_url": url,
            "source_format": "pdf",
            "source_as_of": FOLLOWUP_AS_OF,
            "expression_date": EXPRESSION_DATE,
            "citation_path": f"{jur}/policy/acf/ccdf-plan/fy{FY}-appendix-1",
            # acf.gov answers non-browser User-Agents with HTTP 202 and an empty body.
            "request": {"browser_user_agent": True},
            "extraction": APPENDIX_EXTRACTION,
            "metadata": _followup_metadata(jur, subtype="state_plan_appendix_pdf", index=INDEX,
                                           discovered=f"manual-review:ccdf-agent-queue additional_families; index {INDEX}"),
        }
        doc["metadata"]["appendix"] = "Appendix 1: Lead Agency Implementation Plan for federal non-compliances (ACF-hosted accepted copy)"
        doc["metadata"]["closure_elements"] = ["ccdf-s27"]
        manifest = {"version": APPENDIX_VERSION, "documents": [doc]}
        stem = f"{jur}-ccdf-state-plan-appendix-fy{FY}"
        (ROOT / "manifests" / f"{stem}.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120))
        written += 1
        attach_family(queue, jur, {
            "family": "ccdf_plan_appendix_1",
            "queue_status": "agent_ready",
            "index_url": INDEX,
            "primary_source_url": url,
            "target_manifest": f"manifests/{stem}.yaml",
            "target_scope": {"jurisdiction": jur, "document_class": "policy", "version": APPENDIX_VERSION},
            "taken_count": 1,
            "notes": f"ACF-hosted Appendix 1 (Lead Agency implementation plan for federal non-compliances) listed on the FY 2025-2027 index; taken {FOLLOWUP_AS_OF} (closure ccdf-s27). One provision per finding heading plus the document root.",
        })
    return written


def build_amendments(queue: dict) -> int:
    written = 0
    for code, spec in AMENDMENTS.items():
        jur = f"us-{code}"
        name = next(n for n, c in CODES.items() if c == code)
        docs = []
        for label, url, version_text, approved, extra in spec["docs"]:
            letter = bool(extra.get("letter"))
            doc = {
                "source_id": f"{jur}-acf-ccdf-plan-fy{FY}-{label}",
                "jurisdiction": jur,
                "document_class": "policy",
                "title": f"{name} CCDF Plan FFY {FY}, {version_text}",
                "source_url": url,
                "source_format": "pdf",
                "source_as_of": FOLLOWUP_AS_OF,
                "expression_date": approved or EXPRESSION_DATE,
                "citation_path": f"{jur}/policy/acf/ccdf-plan/fy{FY}-{label}",
            }
            if spec.get("impersonation"):
                doc["request"] = {"browser_impersonation": True}
            doc["extraction"] = {"segmentation": "single_block"} if letter else extra.get("extraction", CARS_EXTRACTION)
            doc["metadata"] = _followup_metadata(jur, subtype="amendment_approval_letter_pdf" if letter else "state_plan_amendment_pdf",
                                                 index=spec["index"], discovered=f"manual-review:ccdf-agent-queue additional_families; index {spec['index']}")
            doc["metadata"]["plan_version"] = version_text
            doc["metadata"]["plan_status"] = (f"ACF approval letter effective {approved}" if letter
                                              else f"Approved as of {approved}" if approved else "Approved (no CARS Plan Status line in the state export)")
            if extra.get("note"):
                doc["metadata"]["source_note"] = extra["note"]
            doc["metadata"]["closure_elements"] = ["ccdf-s28"]
            docs.append(doc)
        manifest = {"version": AMENDMENT_VERSION, "documents": docs}
        stem = f"{jur}-ccdf-state-plan-amendments-fy{FY}"
        (ROOT / "manifests" / f"{stem}.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120))
        written += 1
        note = (f"Separately posted FFY {FY} amendments taken {FOLLOWUP_AS_OF} (closure ccdf-s28): "
                + "; ".join(v for _l, _u, v, _a, _e in spec["docs"]) + ".")
        if spec.get("not_taken"):
            note += " " + spec["not_taken"] + "."
        attach_family(queue, jur, {
            "family": "ccdf_plan_amendments",
            "queue_status": "agent_ready",
            "index_url": spec["index"],
            "primary_source_urls": [u for _l, u, _v, _a, _e in spec["docs"]],
            "target_manifest": f"manifests/{stem}.yaml",
            "target_scope": {"jurisdiction": jur, "document_class": "policy", "version": AMENDMENT_VERSION},
            "taken_count": len(docs),
            "notes": note,
        })
    return written


def build_rate_schedules(queue: dict, *, as_of: str = FOLLOWUP_AS_OF) -> int:
    specs = RATE_SCHEDULES if as_of == FOLLOWUP_AS_OF else RATE_SCHEDULES_WAVE5
    reviewed = RATE_PAGES_REPORTS_ONLY if as_of == FOLLOWUP_AS_OF else RATE_PAGES_REVIEWED_WAVE5
    rate_version = f"{as_of}-ccdf-rate-schedules"
    written = 0
    for code, spec in specs.items():
        jur = f"us-{code}"
        name = next(n for n, c in CODES.items() if c == code)
        docs = []
        for slug, url, title, effective, fmt, extra in spec["docs"]:
            doc = {
                "source_id": f"{jur}-ccdf-rate-schedule-{slug}",
                "jurisdiction": jur,
                "document_class": "policy",
                "title": f"{name}: {title}",
                "source_url": url,
                "source_format": fmt,
                "source_as_of": as_of,
                "expression_date": effective,
                "citation_path": f"{jur}/policy/ccdf/rate-schedules/{slug}",
            }
            if fmt == "pdf":
                doc["extraction"] = {"segmentation": "single_block"}
            doc["metadata"] = {
                "primary_source": True,
                "source_authority": spec["agency"],
                "document_subtype": "rate_or_copay_schedule",
                "program": "CCDF",
                "publisher_index_url": spec["index"],
                "source_discovery_group": f"{jur}/policy/ccdf",
                "discovered_via": f"manual-review:ccdf-agent-queue additional_families; index {spec['index']}",
                "closure_elements": ["ccdf-s30"],
            }
            if extra.get("note"):
                doc["metadata"]["source_note"] = extra["note"]
            docs.append(doc)
        manifest = {"version": rate_version, "documents": docs}
        stem = f"{jur}-ccdf-rate-schedules"
        (ROOT / "manifests" / f"{stem}.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120))
        written += 1
        attach_family(queue, jur, {
            "family": "ccdf_rate_and_copay_schedules",
            "queue_status": "agent_ready",
            "index_url": spec["index"],
            "primary_source_urls": [u for _s, u, _t, _e, _f, _x in spec["docs"]],
            "target_manifest": f"manifests/{stem}.yaml",
            "target_scope": {"jurisdiction": jur, "document_class": "policy", "version": rate_version},
            "taken_count": len(docs),
            "notes": f"Current-year rate and copay schedules posted by the Lead Agency, taken {as_of} (closure ccdf-s30): " + "; ".join(t for _s, _u, t, _e, _f, _x in spec["docs"]) + ".",
        })
    for code, reason in reviewed.items():
        attach_family(queue, f"us-{code}", {
            "family": "ccdf_rate_and_copay_schedules",
            "queue_status": "needs_review",
            "target_manifest": None,
            "taken_count": 0,
            "notes": f"Reviewed {as_of}: {reason}. Market rate survey and cost analysis reports are the basis for rates, not the operative schedule, and were not taken.",
        })
    return written


def run_family(family: str, *, as_of: str = FOLLOWUP_AS_OF) -> int:
    queue_path = ROOT / "manifests" / "ccdf-agent-queue.yaml"
    queue = yaml.safe_load(queue_path.read_text())
    if family == "appendices":
        rows = fetch_index()
        urls = {r["code"]: r["appendix_url"] for r in rows if r["appendix_url"]}
        missing = [c for c in STATES_51 if c not in urls]
        if missing:
            print(f"index lists no Appendix for {missing}", file=sys.stderr)
            return 1
        written = build_appendices(queue, urls)
    elif family == "amendments":
        written = build_amendments(queue)
    else:
        written = build_rate_schedules(queue, as_of=as_of)
    queue_path.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    print(f"{family}: wrote {written} manifests; queue rows annotated under additional_families")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="comma-separated jurisdiction codes (as,mp,...) whose rows are refreshed from "
                        "RESOLUTIONS without fetching the ACF index (a newly agent_ready row also gets its manifest); "
                        "every other row and manifest is left untouched")
    parser.add_argument("--family", choices=["appendices", "amendments", "rate-schedules"],
                        help="2026-09-13 follow-up: build that family's manifests and annotate the existing "
                             "queue rows (additional_families) instead of rebuilding the plan rows")
    parser.add_argument("--as-of", default=FOLLOWUP_AS_OF, choices=[FOLLOWUP_AS_OF, WAVE5_AS_OF],
                        help="rate-schedules only: which pass to build (2026-09-13 follow-up or 2026-09-15 wave 5)")
    args = parser.parse_args()
    if args.family:
        return run_family(args.family, as_of=args.as_of)
    if args.only:
        print(f"queue {refresh_rows_only(args.only.split(','))}")
        return 0
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
            row.update(ready_row_fields(code, name, res, r["appendix_url"]))
            written += 1
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
