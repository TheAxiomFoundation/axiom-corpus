"""Build one corpus manifest per jurisdiction for the state CHIP eligibility policy family
(state agency CHIP eligibility manual / handbook chapter / adopted eligibility rule), and
update the CHIP agent queue (manifests/chip-agent-queue.yaml).

Every source below was confirmed by the agent from the publisher's own index page on
2026-09-10 (see docs/ingest-runs/2026-09-10-chip-state-eligibility-manuals.md for the index
inventories). Blocked publishers and jurisdictions already covered by existing corpus scopes
are recorded on the queue rows only; no manifest is written for them.

    uv run python scripts/build_chip_state_eligibility_manifests.py
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "manifests" / "chip-agent-queue.yaml"
SOURCE_AS_OF = "2026-09-10"
VERSION = "2026-09-10-chip-state-eligibility-manual"
DISCOVERED_VIA = "manual-review:chip-agent-queue; publisher index confirmed by agent 2026-09-10"


def doc(
    jur: str,
    source_id: str,
    title: str,
    url: str,
    citation_path: str,
    fmt: str,
    expression_date: str,
    *,
    document_class: str = "manual",
    subtype: str,
    authority: str,
    extraction: dict | None = None,
    request: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    d: dict = {
        "source_id": source_id,
        "jurisdiction": jur,
        "document_class": document_class,
        "title": title,
        "source_url": url,
        "source_format": fmt,
        "source_as_of": SOURCE_AS_OF,
        "expression_date": expression_date,
        "citation_path": citation_path,
    }
    if request:
        d["request"] = request
    if extraction:
        d["extraction"] = extraction
    d["metadata"] = {
        "primary_source": True,
        "source_authority": authority,
        "document_subtype": subtype,
        "program": "CHIP",
        "source_discovery_group": f"{jur}/{document_class}/chip",
        "discovered_via": DISCOVERED_VIA,
        **(metadata or {}),
    }
    return d


IMPERSONATE = {"browser_impersonation": True}
PAGES = {"page_citation_prefix": "page"}

# --- confirmed jurisdictions -----------------------------------------------------------

CONFIRMED: dict[str, dict] = {
    "us-al": {
        "name": "Alabama",
        "document_class": "manual",
        "source_kind": "official_agency_eligibility_pages",
        "index_url": "https://www.alabamapublichealth.gov/allkids/index.html",
        "index_document_count": 17,
        "primary_source_url": "https://www.alabamapublichealth.gov/allkids/income.html",
        "notes": (
            "ADPH ALL Kids program index (17 program pages: home, income guidelines, pay premium, "
            "benefits booklet, standards of care, how to apply, apply, enrolled families, order "
            "materials, FAQ, Spanish, enrollment data, links, research, reports, other insurance, "
            "about). Taken: the agency's own eligibility policy pages (Income Guidelines effective "
            "2/1/2026; Premiums and Copays). ADPH publishes no ALL Kids eligibility manual; the "
            "Alabama Administrative Code chapter for ALL Kids could not be located on the LSA "
            "admincode site (chapter API 420-10-1 is newborn screening, 420-10-2 is WIC, "
            "420-10-3..7 return 404; no chapter-list API). Reviewer judgment: agency eligibility "
            "pages recorded under document_class manual with document_subtype "
            "agency_eligibility_policy_page."
        ),
        "documents": [
            doc(
                "us-al", "al-adph-allkids-income-guidelines",
                "ADPH ALL Kids: Income Guidelines (effective 2/1/2026)",
                "https://www.alabamapublichealth.gov/allkids/income.html",
                "us-al/manual/adph/chip/income-guidelines", "html", "2026-02-01",
                subtype="agency_eligibility_policy_page",
                authority="Alabama Department of Public Health, ALL Kids",
                request=IMPERSONATE,
                extraction={"html_content_selector": "div.col-sidebar-content"},
                metadata={"state_program": "ALL Kids"},
            ),
            doc(
                "us-al", "al-adph-allkids-premiums-and-copays",
                "ADPH ALL Kids: Premiums and Copays",
                "https://www.alabamapublichealth.gov/allkids/premiums-and-copays.html",
                "us-al/manual/adph/chip/premiums-and-copays", "html", "2026-01-01",
                subtype="agency_eligibility_policy_page",
                authority="Alabama Department of Public Health, ALL Kids",
                request=IMPERSONATE,
                extraction={"html_content_selector": "div.col-sidebar-content"},
                metadata={"state_program": "ALL Kids"},
            ),
        ],
    },
    "us-ct": {
        "name": "Connecticut",
        "document_class": "manual",
        "source_kind": "official_agency_eligibility_pages",
        "index_url": "https://portal.ct.gov/dss/find-benefits-and-support/healthcare-coverage",
        "index_document_count": 9,
        "primary_source_url": "https://portal.ct.gov/dss/knowledge-base/articles/healthcare-coverage/husky-b",
        "notes": (
            "DSS healthcare-coverage index: 9 HUSKY documents (prescreener, how to qualify, member "
            "info, provider info, benefits overview, advisory committee, HUSKY Health landing, "
            "non-citizen children coverage, H.R.1 changes). Taken: DSS knowledge-base article "
            "'HUSKY B' (the agency's CHIP eligibility statement) and the March 1, 2026 HUSKY Health "
            "monthly income chart PDF attached to the DSS 'HUSKY Health Income Charts' article "
            "(the article itself is a 161-character stub). The DSS Uniform Policy Manual "
            "(https://portal.ct.gov/dss/lists/uniform-policy-manual, 129 list pages of .doc/.docx "
            "sections) has no HUSKY B chapter in UPM0/UPM2/UPM8 listings; the linked "
            "huskymonthlyincomechart.pdf is dated March 2020 and was not taken. Reviewer judgment: "
            "agency pages recorded as document_class manual, subtype agency_eligibility_policy_page."
        ),
        "documents": [
            doc(
                "us-ct", "ct-dss-husky-b-article",
                "Connecticut DSS: What is HUSKY B? (Children's Health Insurance Program)",
                "https://portal.ct.gov/dss/knowledge-base/articles/healthcare-coverage/husky-b",
                "us-ct/manual/dss/chip/husky-b", "html", "2025-06-13",
                subtype="agency_eligibility_policy_page",
                authority="Connecticut Department of Social Services",
                request=IMPERSONATE,
                extraction={"html_content_selector": "div.article-body"},
                metadata={"state_program": "HUSKY B"},
            ),
            doc(
                "us-ct", "ct-dss-husky-monthly-income-chart-2026",
                "Connecticut DSS: HUSKY Health Monthly Income Chart, March 1, 2026",
                "https://portal.ct.gov/dss/-/media/departments-and-agencies/dss/fact-sheets-and-issue-briefs/fact-sheets/husky-income-charts/husky-health-monthly-income-chart-march-1-2026.pdf?rev=eafe894baf074727b4ace4651ae19df7&hash=630A05F5CEF1DF1D2C753B40745E36A1",
                "us-ct/manual/dss/chip/husky-monthly-income-chart-2026", "pdf", "2026-03-01",
                subtype="agency_income_standards_chart_pdf",
                authority="Connecticut Department of Social Services",
                request=IMPERSONATE,
                extraction=PAGES,
                metadata={"state_program": "HUSKY B",
                          "chart_article": "https://portal.ct.gov/dss/knowledge-base/articles/fact-sheets-and-brochures-articles/income-tables-articles/husky-income-charts"},
            ),
        ],
    },
    "us-de": {
        "name": "Delaware",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_pdf",
        "index_url": "https://regulations.delaware.gov/AdminCode/title16",
        "index_document_count": 1,
        "primary_source_url": "https://regulations.delaware.gov/api/AdminCode/title16/18000/b78ac36e-3af7-4d1a-9503-16927de57397",
        "notes": (
            "Delaware Administrative Code Title 16, DSS Division of Social Services Manual: the "
            "AdminCode title API lists one CHIP regulation, '18000 Delaware Healthy Children "
            "Program' (regulationId 1054, pdfId b78ac36e-...). Taken. Same publisher/API as the "
            "existing us-de-dssm-13000 manifest; dhss.delaware.gov itself presents a self-signed "
            "certificate in its chain and was not used."
        ),
        "documents": [
            doc(
                "us-de", "de-dhss-dssm-18000",
                "Delaware Administrative Code Title 16 DSSM 18000: Delaware Healthy Children Program",
                "https://regulations.delaware.gov/api/AdminCode/title16/18000/b78ac36e-3af7-4d1a-9503-16927de57397",
                "us-de/regulation/admin-code/title16/dssm/18000", "pdf", SOURCE_AS_OF,
                document_class="regulation",
                subtype="administrative_code_pdf",
                authority="Delaware Department of Health and Social Services, Division of Social Services",
                extraction=PAGES,
                metadata={"state_program": "Delaware Healthy Children Program", "title_number": "16", "chapter": "18000",
                          "regulation_page": "https://regulations.delaware.gov/AdminCode/title16/18000"},
            ),
        ],
    },
    "us-ga": {
        "name": "Georgia",
        "document_class": "manual",
        "source_kind": "official_html_manual_section",
        "index_url": "https://pamms.dhs.ga.gov/dfcs/medicaid/",
        "index_document_count": 241,
        "primary_source_url": "https://pamms.dhs.ga.gov/dfcs/medicaid/2194/",
        "notes": (
            "Georgia DFCS Medicaid Policy Manual (PAMMS): 241 numbered sections; the CHIP class of "
            "assistance is one section, '2194 PeachCare for Kids' (MT 79, effective May 2026). Taken. "
            "General Family Medicaid sections it cross-references (2160, 2182, 2215, 2610, 2650, "
            "Appendix A2) are Medicaid manual sections and were not taken. Reviewer judgment: "
            "citation path follows the work order (us-ga/manual/dfcs/chip/2194) rather than the "
            "existing us-ga/manual/dfcs/medicaid/NNNN convention used by us-ga-ssp-manual.yaml."
        ),
        "documents": [
            doc(
                "us-ga", "ga-dfcs-medicaid-2194-peachcare-for-kids",
                "Georgia Medicaid Policy Manual: 2194 PeachCare for Kids",
                "https://pamms.dhs.ga.gov/dfcs/medicaid/2194/",
                "us-ga/manual/dfcs/chip/2194", "html", "2026-05-01",
                subtype="policy_manual_section",
                authority="Georgia Department of Human Services, Division of Family and Children Services",
                request=IMPERSONATE,
                extraction={"html_content_selector": "article.doc"},
                metadata={"state_program": "PeachCare for Kids", "manual_transmittal": "MT 79",
                          "manual_landing_page": "https://pamms.dhs.ga.gov/dfcs/medicaid/"},
            ),
        ],
    },
    "us-ia": {
        "name": "Iowa",
        "document_class": "manual",
        "source_kind": "official_pdf_manual_chapter",
        "index_url": "https://hhs.iowa.gov/about/policy-manuals/income-maintenance",
        "index_document_count": 58,
        "primary_source_url": "https://hhs.iowa.gov/media/3983/download?inline",
        "notes": (
            "Iowa HHS Income Maintenance policy manuals index (58 Employees' Manual chapter/appendix "
            "PDFs across Titles 1, 4, 5, 6, 8, 13, 23, 24). The CHIP chapter is Title 5 Chapter E "
            "'Healthy and Well Kids in Iowa (hawk-i)' (93 pages, revised 2010-08-20 per its own TOC). "
            "Taken, page-level provisions. Title 8 Medicaid chapters were not taken. Reviewer "
            "judgment: the chapter's own revision date (2010) is old; Iowa's hawk-i rule 441 IAC "
            "chapter 86 (published by the Iowa Legislature) is a candidate follow-up."
        ),
        "documents": [
            doc(
                "us-ia", "ia-hhs-employees-manual-5-e-hawki",
                "Iowa HHS Employees' Manual Title 5 Chapter E: Healthy and Well Kids in Iowa (hawk-i)",
                "https://hhs.iowa.gov/media/3983/download?inline",
                "us-ia/manual/hhs/chip/employees-manual-5-e", "pdf", "2010-08-20",
                subtype="policy_manual_chapter_pdf",
                authority="Iowa Department of Health and Human Services",
                extraction=PAGES,
                metadata={"state_program": "hawk-i", "manual_title": "5", "manual_chapter": "E"},
            ),
        ],
    },
    "us-id": {
        "name": "Idaho",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_pdf",
        "index_url": "https://healthandwelfare.idaho.gov/services-programs/medicaid-health/childrens-health-insurance-program-chip",
        "index_document_count": 2,
        "primary_source_url": "https://adminrules.idaho.gov/rules/current/16/160301.pdf",
        "notes": (
            "IDHW CHIP program page links two policy documents: income guidelines (node/623) and "
            "'Notices and Proposed Rules'. The adopted eligibility rule is IDAPA 16.03.01 "
            "'Eligibility for Health Care Assistance for Families and Children' (Title XIX and XXI), "
            "served by the Office of the Administrative Rules Coordinator at "
            "adminrules.idaho.gov/rules/current/16/160301.pdf (redirects to files.dfm.idaho.gov; "
            "the Current Rules listing page itself is script-rendered). Taken, numbered sections, "
            "same shape as the existing us-id-aabd-rules.yaml (IDAPA 16.03.05)."
        ),
        "documents": [
            doc(
                "us-id", "id-dhw-idapa-16-03-01",
                "IDAPA 16.03.01 Eligibility for Health Care Assistance for Families and Children",
                "https://adminrules.idaho.gov/rules/current/16/160301.pdf",
                "us-id/regulation/idapa/16/03/01", "pdf", "2026-07-01",
                document_class="regulation",
                subtype="administrative_rules",
                authority="Idaho Department of Health and Welfare",
                extraction={
                    "segmentation": "numbered_sections",
                    "start_page": 5,
                    "sort_text": True,
                    "drop_lines": [
                        "IDAHO ADMINISTRATIVE CODE",
                        "Department of Health and Welfare",
                        "16.03.01 – ELIGIBILITY FOR HEALTH CARE ASSISTANCE FOR FAMILIES AND CHILDREN",
                    ],
                    "drop_line_patterns": [
                        r"^Section [0-9]+\s+Page [0-9]+.*$",
                        r"^Section [0-9]+$",
                        r"^Page [0-9]+$",
                        r"^IDAHO ADMINISTRATIVE CODE IDAPA 16\.03\.01.*$",
                        r"^Department of Health and Welfare Families (and|&) Children$",
                    ],
                },
                metadata={"idapa_chapter": "16.03.01", "state_program": "Idaho CHIP"},
            ),
        ],
    },
    "us-in": {
        "name": "Indiana",
        "document_class": "manual",
        "source_kind": "official_pdf_manual_chapter",
        "index_url": "https://www.in.gov/fssa/ompp/forms-documents-and-tools/medicaid-eligibility-policy-manual/",
        "index_document_count": 24,
        "primary_source_url": "https://www.in.gov/dA/4fd9875d6b/Medicaid_PM_1600.pdf?language_id=1",
        "notes": (
            "Indiana Health Coverage Program Policy Manual (IHCPPM) index: 24 chapter PDFs plus an "
            "all-chapters PDF and transmittals. Indiana runs a combined manual; CHIP is Hoosier "
            "Healthwise Package C / 'Children's Health Plan (MED 3)'. Taken: Chapter 1600 Categories "
            "of Assistance (defines the CHIP category, section 1620.72) and Chapter 3000 Eligibility "
            "Standards (income standards). Chapter 5000 is already in the corpus (us-in-ssp-sapn). "
            "Reviewer judgment: chapters 2800 Income and 3400 Budgeting also apply to CHIP but were "
            "not taken."
        ),
        "documents": [
            doc(
                "us-in", "in-fssa-ihcppm-chapter-1600",
                "Indiana Health Coverage Program Policy Manual Chapter 1600: Categories of Assistance",
                "https://www.in.gov/dA/4fd9875d6b/Medicaid_PM_1600.pdf?language_id=1",
                "us-in/manual/fssa/chip/ihcppm-chapter-1600", "pdf", "2026-06-19",
                subtype="medicaid_policy_manual",
                authority="Indiana Family and Social Services Administration, Office of Medicaid Policy and Planning",
                extraction={
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": r"^(?P<label>[0-9]{4}\.[0-9]{2}\.[0-9]{2})(?:\s+(?P<heading>[A-Z][A-Z0-9 /()&',-]+))?\s*$",
                    "label_only_heading_pattern": r"^[A-Z][A-Z0-9 /()&',-]+\s*$",
                    "start_page": 3,
                    "drop_line_patterns": [
                        r"^\s*Indiana Health Coverage Program Policy Manual\s*$",
                        r"^\s*Chapter 1600\s*$",
                        r"^\s*[0-9]+\s*$",
                    ],
                },
                metadata={"state_program": "Hoosier Healthwise Package C", "manual_chapter": "1600"},
            ),
            doc(
                "us-in", "in-fssa-ihcppm-chapter-3000",
                "Indiana Health Coverage Program Policy Manual Chapter 3000: Eligibility Standards",
                "https://www.in.gov/dA/a7e1fb7d7d/Medicaid_PM_3000.pdf?language_id=1",
                "us-in/manual/fssa/chip/ihcppm-chapter-3000", "pdf", "2026-09-03",
                subtype="medicaid_policy_manual",
                authority="Indiana Family and Social Services Administration, Office of Medicaid Policy and Planning",
                extraction={
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": r"^(?P<label>[0-9]{4}\.[0-9]{2}\.[0-9]{2})(?:\s+(?P<heading>[A-Z][A-Z0-9 /()&',-]+))?\s*$",
                    "label_only_heading_pattern": r"^[A-Z][A-Z0-9 /()&',-]+\s*$",
                    "start_page": 3,
                    "drop_line_patterns": [
                        r"^\s*Indiana Health Coverage Program Policy Manual\s*$",
                        r"^\s*Chapter 3000\s*$",
                        r"^\s*[0-9]+\s*$",
                    ],
                },
                metadata={"state_program": "Hoosier Healthwise Package C", "manual_chapter": "3000"},
            ),
        ],
    },
    "us-ma": {
        "name": "Massachusetts",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_pdf",
        "index_url": "https://www.mass.gov/law-library/130-cmr",
        "index_document_count": 2,
        "primary_source_url": "https://www.mass.gov/doc/130-cmr-505000-masshealth-coverage-types-5/download",
        "notes": (
            "MassHealth eligibility regulations on Mass.gov (130 CMR 501-522 member regulations). "
            "CHIP in Massachusetts is MassHealth Family Assistance / CommonHealth for children, "
            "governed by 130 CMR 505.000 Coverage Types (Trans. E.L. 254, rev. 2026-02-13) and "
            "130 CMR 506.000 Financial Requirements (E.L. 250, rev. 2026-01-30). Both taken from "
            "the regulation pages' official PDF downloads. The lead list's law.cornell.edu mirror "
            "of 130 CMR 506.011 was not used."
        ),
        "documents": [
            doc(
                "us-ma", "ma-eohhs-130-cmr-505",
                "130 CMR 505.000: MassHealth: Coverage Types",
                "https://www.mass.gov/doc/130-cmr-505000-masshealth-coverage-types-5/download",
                "us-ma/regulation/130-cmr/505", "pdf", "2026-02-13",
                document_class="regulation",
                subtype="administrative_regulation",
                authority="Massachusetts Executive Office of Health and Human Services, MassHealth",
                request=IMPERSONATE,
                extraction={
                    "segmentation": "labeled_sections",
                    "start_page": 2,
                    "section_heading_pattern": r"^505\.(?P<section>\d{3}):\s+(?P<heading>[^,]+|Medicare Savings Program \(MSP, also called Buy-in\))$",
                    "section_label_template": "{section}",
                    "drop_line_patterns": [
                        r"^130 CMR:\s+DIVISION OF MEDICAL ASSISTANCE$",
                        r"^Trans\. by E\.L\.",
                        r"^Rev\.",
                        r"^130 CMR 505\.000:",
                        r"^\d+$",
                    ],
                },
                metadata={"legal_identifier": "130 CMR 505.000",
                          "regulation_page": "https://www.mass.gov/regulations/130-CMR-505000-masshealth-coverage-types"},
            ),
            doc(
                "us-ma", "ma-eohhs-130-cmr-506",
                "130 CMR 506.000: MassHealth: Financial Requirements",
                "https://www.mass.gov/doc/130-cmr-506000-masshealth-financial-requirements-4/download",
                "us-ma/regulation/130-cmr/506", "pdf", "2026-01-30",
                document_class="regulation",
                subtype="administrative_regulation",
                authority="Massachusetts Executive Office of Health and Human Services, MassHealth",
                request=IMPERSONATE,
                extraction={
                    "segmentation": "labeled_sections",
                    "start_page": 2,
                    "section_heading_pattern": r"^506\.(?P<section>\d{3}):\s+(?P<heading>[^,]+)$",
                    "section_label_template": "{section}",
                    "drop_line_patterns": [
                        r"^130 CMR:\s+DIVISION OF MEDICAL ASSISTANCE$",
                        r"^Trans\. by E\.L\.",
                        r"^Rev\.",
                        r"^130 CMR 506\.000:",
                        r"^\d+$",
                    ],
                },
                metadata={"legal_identifier": "130 CMR 506.000",
                          "regulation_page": "https://www.mass.gov/regulations/130-CMR-506000-masshealth-financial-requirements"},
            ),
        ],
    },
    "us-mo": {
        "name": "Missouri",
        "document_class": "manual",
        "source_kind": "official_pdf_manual_appendix",
        "index_url": "https://dssmanuals.mo.gov/family-mo-healthnet-magi/",
        "index_document_count": 28,
        "primary_source_url": "https://dssmanuals.mo.gov/wp-content/uploads/2019/05/appendix-e.pdf",
        "notes": (
            "Missouri DSS Family MO HealthNet (MAGI) Manual index: 17 numbered sections "
            "(1800-1890) and 11 appendices. The CHIP section 1840.000.00 'MO HealthNet Children's "
            "Health Insurance Program (CHIP)' is password-protected on the publisher's site "
            "('This content is password-protected'), as are the other numbered sections. Taken: the "
            "two public CHIP appendices, Appendix A (MAGI income limits with 5% FPL and CHIP "
            "premium amounts, 7/1/2026-3/31/2027) and Appendix E (MO HealthNet for Kids CHIP "
            "Premium Chart effective 7/1/2026). Reviewer judgment: the manual section itself "
            "remains unavailable without publisher credentials; no workaround attempted."
        ),
        "documents": [
            doc(
                "us-mo", "mo-dss-magi-appendix-a",
                "Missouri Family MO HealthNet (MAGI) Manual Appendix A: MAGI Income With 5% of FPL Included and CHIP Premium Amounts",
                "https://dssmanuals.mo.gov/wp-content/uploads/2019/03/MAGIappendix-a.pdf",
                "us-mo/manual/dss/chip/magi-appendix-a", "pdf", "2026-07-01",
                subtype="policy_manual_appendix_pdf",
                authority="Missouri Department of Social Services, Family Support Division",
                request=IMPERSONATE,
                extraction=PAGES,
                metadata={"state_program": "MO HealthNet for Kids (CHIP)"},
            ),
            doc(
                "us-mo", "mo-dss-magi-appendix-e",
                "Missouri Family MO HealthNet (MAGI) Manual Appendix E: MO HealthNet for Kids CHIP Premium Chart",
                "https://dssmanuals.mo.gov/wp-content/uploads/2019/05/appendix-e.pdf",
                "us-mo/manual/dss/chip/magi-appendix-e", "pdf", "2026-07-01",
                subtype="policy_manual_appendix_pdf",
                authority="Missouri Department of Social Services, Family Support Division",
                request=IMPERSONATE,
                extraction=PAGES,
                metadata={"state_program": "MO HealthNet for Kids (CHIP)"},
            ),
        ],
    },
    "us-ny": {
        "name": "New York",
        "document_class": "manual",
        "source_kind": "official_agency_eligibility_pages",
        "index_url": "https://www.health.ny.gov/health_care/child_health_plus/",
        "index_document_count": 8,
        "primary_source_url": "https://www.health.ny.gov/health_care/child_health_plus/eligibility_and_cost.htm",
        "notes": (
            "NYSDOH Child Health Plus index: 8 program pages (eligibility and cost, benefits, where to "
            "go for care, health plans, how to apply, helpful links, contact, Spanish). Taken: "
            "'Eligibility and Cost' (the Department's published CHPlus eligibility and premium table, "
            "2026 FPL effective 2/17/2026). NYSDOH publishes no CHPlus eligibility manual and 10 NYCRR "
            "is vendor-hosted. Reviewer judgment: agency page recorded as document_class manual, "
            "subtype agency_eligibility_policy_page."
        ),
        "documents": [
            doc(
                "us-ny", "ny-doh-child-health-plus-eligibility-and-cost",
                "New York State Department of Health: Child Health Plus Eligibility and Cost",
                "https://www.health.ny.gov/health_care/child_health_plus/eligibility_and_cost.htm",
                "us-ny/manual/doh/chip/child-health-plus-eligibility-and-cost", "html", "2026-02-17",
                subtype="agency_eligibility_policy_page",
                authority="New York State Department of Health",
                request=IMPERSONATE,
                extraction={"html_content_selector": "#content"},
                metadata={"state_program": "Child Health Plus"},
            ),
        ],
    },
    "us-tx": {
        "name": "Texas",
        "document_class": "manual",
        "source_kind": "official_html_handbook_part",
        "index_url": "https://fhb.hhs.texas.gov/handbooks/texas-works-handbook/part-d-childrens-health-insurance-program",
        "index_document_count": 23,
        "primary_source_url": "https://fhb.hhs.texas.gov/book/export/html/75506",
        "notes": (
            "Texas Works Handbook (HHSC Forms and Handbooks site; www.hhs.texas.gov URLs now 301 to "
            "fhb.hhs.texas.gov). Part D Children's Health Insurance Program lists 23 top-level "
            "sections D-100 to D-2400 (each with subsections). Taken as the publisher's own "
            "printer-friendly export of Part D (one HTML document; sections are the export's "
            "comma-form page headings 'D-NNN, Title', one per handbook page, with the "
            "un-comma'd subsection headings such as D-121 or D—231.1 kept inside the page body "
            "because the export repeats some of them and the HTML extractor cannot merge repeats). The "
            "existing us-tx-manuals.yaml scope already holds D-1820 Enrollment Fees under "
            "us-tx/manual/hhs/texas-works-handbook/d-1820-enrollment-fees; it is superseded in "
            "content but not removed. Reviewer judgment: the D-210 heading is repeated in the export "
            "and is merged by drop_repeated_section_headings."
        ),
        "documents": [
            doc(
                "us-tx", "tx-hhsc-texas-works-handbook-part-d",
                "Texas Works Handbook Part D: Children's Health Insurance Program",
                "https://fhb.hhs.texas.gov/book/export/html/75506",
                "us-tx/manual/hhs/chip/texas-works-handbook-part-d", "html", SOURCE_AS_OF,
                subtype="policy_handbook_part",
                authority="Texas Health and Human Services Commission",
                request=IMPERSONATE,
                extraction={
                    "html_content_selector": "body",
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": r"^D-(?P<num>\d{3,4}),\s+(?P<heading>\S.*)$",
                    "section_label_template": "d-{num}",
                },
                metadata={"state_program": "Texas CHIP and CHIP Perinatal",
                          "part_landing_page": "https://fhb.hhs.texas.gov/handbooks/texas-works-handbook/part-d-childrens-health-insurance-program"},
            ),
        ],
    },
}

# --- blocked publishers ---------------------------------------------------------------

BLOCKED: dict[str, dict] = {
    "us-fl": {
        "name": "Florida",
        "index_url": "https://www.floridakidcare.org/",
        "index_document_count": 14,
        "primary_source_url": "https://ahca.myflorida.com/medicaid/florida-kidcare",
        "notes": (
            "Blocked. The Title XXI agency page https://ahca.myflorida.com/medicaid/florida-kidcare "
            "returns HTTP 403 (Cloudflare 'Attention Required!') to a plain client, to a curl "
            "client and to the chrome120 browser-impersonation client. floridakidcare.org "
            "(Florida Healthy Kids Corporation; 14 consumer pages: about, benefits, cost, cost "
            "calculator, plan information, renew, requirements, FAQs, board, media, partner "
            "resources, notices, required reporting, contact) publishes no eligibility manual or "
            "adopted rule; the DCF ESS manual already in the corpus (us-fl/manual) has no KidCare "
            "chapter. Candidate follow-up: s. 409.814 F.S. from the Florida Legislature."
        ),
    },
    "us-ks": {
        "name": "Kansas",
        "index_url": "https://www.kancare.ks.gov/policies-and-reports/eligibility-policy",
        "index_document_count": None,
        "primary_source_url": "https://www.kancare.ks.gov/policies-and-reports/eligibility-policy",
        "notes": (
            "Blocked. The Kansas Family Medical Assistance Manual (KFMAM) publisher "
            "www.kancare.ks.gov returns HTTP 403 'Access Denied' for the eligibility-policy index, "
            "the KFMAM page and the site root, to plain, curl and chrome120-impersonated clients; "
            "www.kdhe.ks.gov also returns 403. The existing us-ks KEESM scope (DCF) is SNAP/TANF and "
            "has no CHIP chapter."
        ),
    },
    "us-la": {
        "name": "Louisiana",
        "index_url": "https://ldh.la.gov/page/medicaid-eligibility-manual",
        "index_document_count": None,
        "primary_source_url": "https://ldh.la.gov/page/medicaid-eligibility-manual",
        "notes": (
            "Blocked. ldh.la.gov (Louisiana Medicaid Eligibility Manual, LaCHIP) returns HTTP 403 "
            "(Cloudflare 'Attention Required!') for the manual page and the site root, to plain, "
            "curl and chrome120-impersonated clients. The existing us-la SNAP manual came from "
            "public.powerdms.com (DCFS), which does not host the LDH Medicaid manual."
        ),
    },
    "us-wi": {
        "name": "Wisconsin",
        "index_url": "https://www.emhandbooks.wisconsin.gov/bcplus/bcplus.htm",
        "index_document_count": None,
        "primary_source_url": "https://www.emhandbooks.wisconsin.gov/bcplus/bcplus.htm",
        "notes": (
            "Blocked. The BadgerCare Plus Eligibility Handbook host www.emhandbooks.wisconsin.gov "
            "(165.189.157.19) did not accept TCP connections on 443 or 80 during this run "
            "(curl: (28) connection timeout after 20-60 s on three attempts; WebFetch "
            "ECONNREFUSED); www.dhs.wisconsin.gov answered normally. The same host served the "
            "FoodShare handbook for us-wi-foodshare-manual.yaml in July 2026, so this may be "
            "transient; retry before treating as a durable block."
        ),
    },
}

# --- jurisdictions already covered by existing corpus scopes ------------------------------

DONE: dict[str, dict] = {
    "us": {
        "name": "Federal",
        "index_url": "https://www.medicaid.gov/chip",
        "index_document_count": 15,
        "target_manifest": "manifests/us-cms-chip-fcep-spa-official-documents.yaml; manifests/us-cms-chip-children-coverage-map-official-documents.yaml; manifests/us-medicaid-chip-eligibility-levels.yaml",
        "target_scope": {"jurisdiction": "us", "document_class": "regulation", "version": "2026-07-13-recovery-r2026-07-17-dedup"},
        "notes": (
            "Done; nothing re-ingested. CMS CHIP index (15 sections: state program information, CHIP "
            "SPAs, benefits, CCTAG, cost sharing, eligibility & enrollment with waiting periods / "
            "continuous eligibility / enrollment strategies / substitution strategies, financing, "
            "managed care, quality, reports & evaluations, guidance & regulations). Already in the "
            "corpus: CHIP SPAs and children coverage map (us/policy), the Medicaid/CHIP/BHP "
            "eligibility levels table (us/form), Title XXI (us/statute, docs/ingest-runs/"
            "2026-06-26-chip-title-xxi.md), and 42 CFR part 457 (171 provisions, subparts A-L, in "
            "us/regulation version 2026-07-13-recovery-r2026-07-17-dedup, coverage complete). The "
            "remaining CMS index sections are explanatory web pages or SHO/CIB guidance families, "
            "not a primary CHIP policy document; none taken."
        ),
    },
    "us-il": {
        "name": "Illinois",
        "index_url": "https://hfs.illinois.gov/medicalprograms/allkids.html",
        "index_document_count": 14,
        "target_manifest": "manifests/us-il-snap-manual.yaml",
        "target_scope": {"jurisdiction": "us-il", "document_class": "manual", "version": "2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained"},
        "notes": (
            "Done by pointer (reviewer judgment). HFS All Kids index (14 program pages) links no "
            "policy manual; All Kids (Medicaid and CHIP) eligibility is governed by the IDHS Cash, "
            "SNAP and Medical Manual, which is already ingested in full (12,450 provisions at "
            "us-il/manual/dhs/csmm/*, including PM 04-02 Family Health Plans cases, PM 15-06-01-d "
            "All Kids Assist Standard, PM 06-24-07 Premiums and Co-Pays, WAG 06-08-14 All Kids Forms). "
            "No separate CHIP manual exists to add."
        ),
    },
    "us-mi": {
        "name": "Michigan",
        "index_url": "https://mdhhs-pres-prod.michigan.gov/OLMWeb/ex/BP/Public/BEM/000.pdf",
        "index_document_count": 196,
        "target_manifest": "manifests/us-mi-bridges-manual.yaml",
        "target_scope": {"jurisdiction": "us-mi", "document_class": "manual", "version": "2026-07-17-mi-bridges-manual"},
        "notes": (
            "Done by pointer (reviewer judgment). MIChild (Michigan CHIP) eligibility is BEM 130 "
            "MICHILD (BPB 2024-001) and BEM 131 Healthy Kids of the Bridges Eligibility Manual, both "
            "already ingested in us-mi-bridges-manual.yaml (us-mi/manual/mdhhs/bridges/bem/130 with "
            "three page provisions; the document root record has an empty body, text is on the "
            "page children). Not duplicated."
        ),
    },
}



# --- batch 2 (2026-09-10): next ten states by population, plus pulls ----------------------
#
# Batch 2 took the ten most populous states not yet in the queue (CA, PA, OH, NC, NJ, VA, WA,
# AZ, TN, MD). NC, NJ and VA were already covered by the combined Medicaid eligibility manuals
# ingested by the parallel Medicaid run (same corpus root), so CO, MN and SC were pulled next.
# See docs/ingest-runs/2026-09-10-chip-state-eligibility-manuals-batch-2.md.

BATCH2_DISCOVERED_VIA = (
    "manual-review:chip-agent-queue batch 2; publisher index confirmed by agent 2026-09-10"
)
RETRIED_AT = "2026-09-10T18:39Z"
# Batch-1 blocked rows, retried once (one plain request, one chrome120 request, 25 s timeouts).
RETRY_NOTES: dict[str, str] = {
    "us-fl": f"retried {RETRIED_AT}, same failure (HTTP 403 Cloudflare 'Attention Required!' plain and chrome120).",
    "us-ks": f"retried {RETRIED_AT}, same failure (HTTP 403 'Access Denied' plain and chrome120).",
    "us-la": f"retried {RETRIED_AT}, same failure (HTTP 403 Cloudflare 'Attention Required!' plain and chrome120).",
    "us-wi": f"retried {RETRIED_AT}, same failure (TCP connect timeout after 25 s on 443, plain and chrome120).",
}

NEW_ROW_NAMES: dict[str, str] = {
    "us-az": "Arizona", "us-ca": "California", "us-co": "Colorado", "us-md": "Maryland",
    "us-mn": "Minnesota", "us-nc": "North Carolina", "us-nj": "New Jersey", "us-oh": "Ohio",
    "us-pa": "Pennsylvania", "us-sc": "South Carolina", "us-tn": "Tennessee", "us-va": "Virginia",
    "us-wa": "Washington",
}

NEVER_CONTINUE = "(?!)"  # heading_continuation_pattern that never matches: headings are one line

MD_COMAR_10_09_11_SECTIONS: dict[str, str] = {
    "01": "Purpose and Scope",
    "02": "Definitions",
    "03": "Coverage Groups",
    "04": "Application",
    "05": "Application: Additional Requirements",
    "06": "Nonfinancial Eligibility Requirements",
    "07": "Consideration of Household Income",
    "08": "Consideration of Family Income: Earned and Unearned Income (Repealed)",
    "09": "Consideration of Family Income: Income Disregards (Repealed)",
    "10": "Determining Financial Eligibility",
    "11": "Certification Periods",
    "12": "Covered Services",
    "13": "Post-Eligibility Requirements",
    "14": "Hearings",
    "15": "Fraud and Abuse",
    "16": "Adjustments and Recoveries",
    "17": "Interpretive Regulation",
}


def _md_comar_doc(num: str, title: str) -> dict:
    d = doc(
        "us-md", f"md-mdh-comar-10-09-11-{num}",
        f"COMAR 10.09.11.{num} {title}",
        f"https://regs.maryland.gov/us/md/exec/comar/10.09.11.{num}",
        f"us-md/regulation/title-10/subtitle-09/chapter-11/regulation-{num}", "html", "2026-04-13",
        document_class="regulation",
        subtype="administrative_regulation_section",
        authority="Maryland Department of Health (COMAR Title 10), published by the Maryland Division of State Documents",
        extraction={"html_content_selector": "article.content"},
        metadata={"legal_identifier": f"COMAR 10.09.11.{num}", "state_program": "Maryland Children's Health Program",
                  "chapter_page": "https://regs.maryland.gov/us/md/exec/comar/10.09.11",
                  "repealed": title.endswith("(Repealed)")},
    )
    d["metadata"]["discovered_via"] = BATCH2_DISCOVERED_VIA
    return d


CONFIRMED_BATCH2: dict[str, dict] = {
    "us-pa": {
        "name": "Pennsylvania",
        "document_class": "manual",
        "source_kind": "official_pdf_policy_handbook",
        "index_url": "https://www.pa.gov/agencies/dhs/resources/chip/chip-resources",
        "index_document_count": 16,
        "index_families": {"agency_policy_handbook_pdf": 2, "chip_state_plan_pdf": 1,
                           "privacy_notice_pdf": 1, "program_web_page": 12},
        "primary_source_url": "https://www.pa.gov/content/dam/copapwp-pagov/en/dhs/documents/chip/eligibility-and-benefits/documents/chip-enrollment-and-benefits-handbook.pdf",
        "notes": (
            "PA DHS CHIP Resources index: 16 documents (2 agency policy handbooks: CHIP Enrollment "
            "and Benefits Handbook released 2026-01-01, CHIP Procedures Handbook January 2026; the "
            "CHIP State Plan PDF (September 2026); the CHIP privacy notice; 12 CHIP program web pages). "
            "Taken 1: the Enrollment and Benefits Handbook (Part 1 eligibility, enrollment and cost "
            "sharing; Part 2 benefits), chapter-level sections. Not taken: the Procedures Handbook "
            "(148 pages of MCO operating procedures: COMPASS, quality management, marketing, "
            "administration), the state plan (state-plan family; CMS CHIP SPAs are already in the "
            "corpus), the privacy notice. The Medicaid run's MA Eligibility Handbook section 309.6 "
            "(us-pa/manual/dhs/medicaid/309-...) only refers applicants to CHIP. Reviewer judgments: "
            "sections are chapters because the publisher's subsection labels repeat (2.1 appears three "
            "times), and the glossary (page 5) precedes the first chapter and is not captured."
        ),
        "documents": [
            doc(
                "us-pa", "pa-dhs-chip-enrollment-and-benefits-handbook",
                "Pennsylvania DHS Children's Health Insurance Program (CHIP) Enrollment and Benefits Handbook",
                "https://www.pa.gov/content/dam/copapwp-pagov/en/dhs/documents/chip/eligibility-and-benefits/documents/chip-enrollment-and-benefits-handbook.pdf",
                "us-pa/manual/dhs/chip/enrollment-and-benefits-handbook", "pdf", "2026-01-01",
                subtype="policy_handbook_pdf",
                authority="Pennsylvania Department of Human Services",
                extraction={
                    "segmentation": "labeled_sections",
                    "start_page": 6,
                    "section_heading_pattern": r"^CHAPTER (?P<num>\d+):\s+(?P<heading>[A-Z].*?)\s*$",
                    "section_label_template": "chapter-{num}",
                    "heading_continuation_pattern": NEVER_CONTINUE,
                    "drop_line_patterns": [r"^\s*Released January 1, 2026\s*$", r"^\s*\d{1,2}\s*$"],
                },
                metadata={"state_program": "Pennsylvania CHIP", "released": "2026-01-01"},
            ),
        ],
    },
    "us-wa": {
        "name": "Washington",
        "document_class": "manual",
        "source_kind": "official_html_manual_chapter",
        "index_url": "https://www.hca.wa.gov/free-or-low-cost-health-care/i-help-others-apply-and-access-apple-health/modified-adjusted-gross-income-magi-based-programs-manual",
        "index_document_count": 16,
        "index_families": {"magi_program_chapter": 9, "magi_financial_eligibility_chapter": 3,
                           "magi_client_notice_chapter": 4},
        "primary_source_url": "https://www.hca.wa.gov/free-or-low-cost-health-care/i-help-others-apply-and-access-apple-health/apple-health-kids-and-without-premiums",
        "notes": (
            "Washington HCA Apple Health Eligibility Manual, MAGI-based programs manual index: 16 "
            "chapters (9 program chapters, 3 financial-eligibility chapters, 4 client-notice chapters). "
            "CHIP in Washington is premium-based Apple Health for Kids; taken 1: 'Apple Health for "
            "Kids, with and without premiums' (revised 2026-04-01), which carries WAC 182-505-0210, "
            "182-505-0215 and 182-505-0225 with HCA clarifying information, sectioned by WAC. The "
            "accordion title copies of each WAC heading are dropped (dl.ckeditor-accordion > dt) so "
            "each WAC appears once. Not taken: Household composition, Income (parts 1-2) and the "
            "other program chapters (Medicaid)."
        ),
        "documents": [
            doc(
                "us-wa", "wa-hca-apple-health-for-kids",
                "Washington Apple Health Eligibility Manual: Apple Health for Kids, with and without premiums",
                "https://www.hca.wa.gov/free-or-low-cost-health-care/i-help-others-apply-and-access-apple-health/apple-health-kids-and-without-premiums",
                "us-wa/manual/hca/chip/apple-health-for-kids", "html", "2026-04-01",
                subtype="eligibility_manual_chapter",
                authority="Washington State Health Care Authority",
                extraction={
                    "html_content_selector": "div.region-content",
                    "html_drop_selectors": ["dl.ckeditor-accordion > dt"],
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": r"^(?P<heading>WAC (?P<num>182-505-\d{4})\s+\S.*)$",
                    "section_label_template": "wac-{num}",
                },
                metadata={"state_program": "Apple Health for Kids with premiums (CHIP)",
                          "wac_sections": ["182-505-0210", "182-505-0215", "182-505-0225"]},
            ),
        ],
    },
    "us-tn": {
        "name": "Tennessee",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_pdf",
        "index_url": "https://publications.tnsosfiles.com/rules/1200/1200-13/1200-13.htm",
        "index_document_count": 22,
        "index_families": {"tenncare_rule_chapter_pdf": 22},
        "primary_source_url": "https://publications.tnsosfiles.com/rules/1200/1200-13/1200-13-21.20250202.pdf",
        "notes": (
            "Tennessee Secretary of State, Division of Publications, effective rules index for "
            "Chapter 1200-13 (Division of TennCare): 22 rule chapters 1200-13-01 through 1200-13-22. "
            "Taken 1: 1200-13-21 CoverKids (Tennessee's separate CHIP), February 2025 revision, rules "
            ".01-.10. Not taken: 1200-13-20 TennCare Eligibility (Medicaid) and the other chapters. "
            "tn.gov (TennCare eligibility policy page) returns HTTP 403 to plain and chrome120 clients; "
            "publications.tnsosfiles.com returns 403 to a plain client and 200 with browser "
            "impersonation. Citation path follows the existing us-tn/regulation/1240-01/02/01 "
            "convention (chapter 1200-13 / rule chapter 21 / rule NN)."
        ),
        "documents": [
            doc(
                "us-tn", "tn-tenncare-rules-1200-13-21-coverkids",
                "Rules of the Tennessee Department of Finance and Administration, Division of TennCare, Chapter 1200-13-21 CoverKids",
                "https://publications.tnsosfiles.com/rules/1200/1200-13/1200-13-21.20250202.pdf",
                "us-tn/regulation/1200-13/21", "pdf", "2025-02-02",
                document_class="regulation",
                subtype="administrative_rules_chapter",
                authority="Tennessee Department of Finance and Administration, Division of TennCare",
                request=IMPERSONATE,
                extraction={
                    "segmentation": "labeled_sections",
                    "section_heading_pattern": r"^1200-13-21-\.(?P<num>\d{2})\s+(?P<heading>[A-Z][A-Z0-9 ,'&/()-]*?)\.(?:\s+(?P<body>\S.*))?\s*$",
                    "section_label_template": "{num}",
                    "heading_continuation_pattern": NEVER_CONTINUE,
                    "drop_lines": ["COVERKIDS", "CHAPTER 1200-13-21"],
                    "drop_line_patterns": [
                        r"^\(Rule 1200-13-21-\.\d{2}, continued\)\s*$",
                        r"^[A-Z][a-z]+, \d{4}(?: \(Revised\))?\s*$",
                        r"^\d{1,2}\s*$",
                    ],
                },
                metadata={"state_program": "CoverKids", "rule_chapter": "1200-13-21",
                          "sos_revision": "February, 2025 (Revised)"},
            ),
        ],
    },
    "us-md": {
        "name": "Maryland",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_html",
        "index_url": "https://regs.maryland.gov/us/md/exec/comar/10.09.11",
        "index_document_count": 17,
        "index_families": {"comar_regulation_section_html_in_force": 15,
                           "comar_regulation_section_html_repealed": 2},
        "primary_source_url": "https://regs.maryland.gov/us/md/exec/comar/10.09.11",
        "notes": (
            "COMAR 10.09.11 Maryland Children's Health Program (MCHP, Maryland's CHIP), chapter page "
            "on the Division of State Documents' COMAR site regs.maryland.gov (dsd.maryland.gov "
            "redirects there with HTTP 301; the site is operated for DSD by Open Law Library and "
            "states State of Maryland copyright). 17 regulation sections .01-.17, two repealed (.08, "
            ".09); all 17 taken as one HTML document each, citation paths following the existing "
            "us-md/regulation/title-07/subtitle-03/chapter-03/regulation-NN convention. Chapter "
            "revised 2014-01-06; latest amendment .11D effective 2026-04-13 (used as expression_date "
            "for all sections). Reviewer judgments: the site asks visitors to use its bulk HTML/XML "
            "downloads (GitHub maryland-dsd) instead of scraping; 17 page fetches were made directly. "
            "The Maryland Medical Assistance eligibility manual was not located on mdh.maryland.gov."
        ),
        "documents": [_md_comar_doc(num, title) for num, title in MD_COMAR_10_09_11_SECTIONS.items()],
    },
    "us-co": {
        "name": "Colorado",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_pdf",
        "index_url": "https://www.sos.state.co.us/CCR/NumericalCCRDocList.do?deptID=7&agencyID=69",
        "index_document_count": 22,
        "index_families": {"ccr_rule_document_chp_plus": 1, "ccr_rule_document_medical_assistance": 21},
        "primary_source_url": "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=12479&fileName=10%20CCR%202505-3",
        "notes": (
            "Colorado Secretary of State, Code of Colorado Regulations, HCPF Medical Services Board "
            "rule list: 22 CCR documents (10 CCR 2505-3 and 21 parts of 10 CCR 2505-10 Medical "
            "Assistance). Taken 1: 10 CCR 2505-3, the Children's Basic Health Plan (Child Health Plan "
            "Plus) rule, current version effective 2026-04-14 (ruleVersionId 12479; rule info page "
            "DisplayRule.do?action=ruleinfo&ruleId=2816), sectioned by the rule's numbered sections "
            "50-610 (the SOS listing titles it 'Financial Management of the Children's Basic Health "
            "Plan'; the text covers eligibility, benefits, cost sharing, enrollment, financial "
            "management and appeals). Sections 210 and 510 have no title line; their first sentence "
            "serves as heading. hcpf.colorado.gov returns HTTP 403 (CloudFront) and was not used. "
            "Citation path follows the existing us-co/regulation/10-ccr-2506-1 convention."
        ),
        "documents": [
            doc(
                "us-co", "co-hcpf-10-ccr-2505-3",
                "10 CCR 2505-3 Financial Management of the Children's Basic Health Plan (Child Health Plan Plus rules)",
                "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=12479&fileName=10%20CCR%202505-3",
                "us-co/regulation/10-ccr-2505-3", "pdf", "2026-04-14",
                document_class="regulation",
                subtype="code_of_colorado_regulations_rule",
                authority="Colorado Department of Health Care Policy and Financing, Medical Services Board",
                extraction={
                    "segmentation": "labeled_sections",
                    "section_label_pattern": r"^(?P<label>50|[1-6][0-9]0)\s*$",
                    "label_only_heading_pattern": r"^\S.*$",
                    "heading_continuation_pattern": NEVER_CONTINUE,
                    "drop_lines": [
                        "CODE OF COLORADO REGULATIONS",
                        "10 CCR 2505-3",
                        "Medical Services Board",
                        "DEPARTMENT OF HEALTH CARE POLICY AND FINANCING",
                    ],
                    "drop_line_patterns": [r"^(?:[1-9]|[1-4][0-9])\s*$"],
                },
                metadata={"state_program": "Child Health Plan Plus (CHP+)", "ccr_series": "10 CCR 2505-3",
                          "rule_version_id": "12479", "effective_date": "2026-04-14",
                          "rule_info_url": "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2816&deptID=7&agencyID=69"},
            ),
        ],
    },
    "us-mn": {
        "name": "Minnesota",
        "document_class": "manual",
        "source_kind": "official_html_manual_section",
        "index_url": "https://hcopub.dhs.state.mn.us/epm/2_2.htm",
        "index_document_count": 23,
        "index_families": {"epm_ma_fca_topic": 23},
        "primary_source_url": "https://hcopub.dhs.state.mn.us/epm/2_2_3_3.htm",
        "notes": (
            "Minnesota DHS Health Care Programs Eligibility Policy Manual (EPM), chapter 2.2 Medical "
            "Assistance for Families with Children and Adults (MA-FCA) index: 23 topic pages (general "
            "requirements, non-financial eligibility, financial eligibility, post-eligibility). "
            "Minnesota's CHIP is Medicaid-expansion CHIP (Title XXI-funded MA for infants 275-283% "
            "FPG and pregnant people; MinnesotaCare is a Basic Health Program, not CHIP), so there is "
            "no separate CHIP manual. Taken 2: 2.2.2.1 MA-FCA Bases of Eligibility (published "
            "2026-06-03) and 2.2.3.3 MA-FCA Income Limit (published 2018-12-01; names the CHIP-funded "
            "infant band). The RoboHelp topic body (#rh-topic) is taken as blocks. Reviewer judgment: "
            "the remaining MA-FCA topics (household composition, income methodology) also apply."
        ),
        "documents": [
            doc(
                "us-mn", "mn-dhs-epm-2-2-2-1",
                "Minnesota EPM 2.2.2.1 MA-FCA Bases of Eligibility",
                "https://hcopub.dhs.state.mn.us/epm/2_2_2_1.htm",
                "us-mn/manual/dhs/chip/epm-2-2-2-1", "html", "2026-06-03",
                subtype="eligibility_policy_manual_topic",
                authority="Minnesota Department of Human Services",
                extraction={"html_content_selector": "#rh-topic"},
                metadata={"state_program": "Medical Assistance for Families with Children and Adults (CHIP-funded infants and pregnant people)",
                          "epm_section": "2.2.2.1"},
            ),
            doc(
                "us-mn", "mn-dhs-epm-2-2-3-3",
                "Minnesota EPM 2.2.3.3 MA-FCA Income Limit",
                "https://hcopub.dhs.state.mn.us/epm/2_2_3_3.htm",
                "us-mn/manual/dhs/chip/epm-2-2-3-3", "html", "2018-12-01",
                subtype="eligibility_policy_manual_topic",
                authority="Minnesota Department of Human Services",
                extraction={"html_content_selector": "#rh-topic"},
                metadata={"state_program": "Medical Assistance for Families with Children and Adults (CHIP-funded infants and pregnant people)",
                          "epm_section": "2.2.3.3"},
            ),
        ],
    },
}
for _spec in CONFIRMED_BATCH2.values():
    for _d in _spec["documents"]:
        _d["metadata"]["discovered_via"] = BATCH2_DISCOVERED_VIA

BLOCKED_BATCH2: dict[str, dict] = {
    "us-ca": {
        "name": "California",
        "index_url": "https://www.dhcs.ca.gov/services/medi-cal/eligibility/Pages/MEPM.aspx",
        "index_document_count": None,
        "primary_source_url": "https://www.dhcs.ca.gov/services/medi-cal/eligibility/Pages/MEPM.aspx",
        "notes": (
            "Blocked. California's CHIP is Title XXI-funded Medi-Cal for children (Optional Targeted "
            "Low-Income Children) plus MCAP and county CCHIP; the eligibility manual is the DHCS "
            "Medi-Cal Eligibility Procedures Manual. www.dhcs.ca.gov returns HTTP 403 with an empty "
            "772-byte body for the MEPM index and for the site root, to a plain client, the WebFetch "
            "client and the chrome120 browser-impersonation client. 22 CCR is vendor-hosted (Westlaw) "
            "and was not used. No existing us-ca scope carries Medi-Cal or CHIP eligibility text. 0 taken."
        ),
    },
    "us-oh": {
        "name": "Ohio",
        "index_url": "https://codes.ohio.gov/ohio-administrative-code/chapter-5160:1-4",
        "index_document_count": None,
        "primary_source_url": "https://codes.ohio.gov/ohio-administrative-code/chapter-5160:1-4",
        "notes": (
            "Blocked. Ohio's CHIP is Medicaid-expansion CHIP whose eligibility rules are the adopted "
            "rules in OAC Chapter 5160:1-4 (MAGI-based Medicaid: children, families and adults) "
            "published by the Legislative Service Commission at codes.ohio.gov. codes.ohio.gov did "
            "not accept TCP connections on 443 during this run (requests ConnectTimeout after 25 s "
            "plain; curl (28) connection timed out after 25 s with chrome120 impersonation; WebFetch "
            "ECONNREFUSED 198.234.74.32:443), and emanuals.jfs.ohio.gov timed out the same way. "
            "medicaid.ohio.gov answered (HTTP 200) but publishes no eligibility manual, only consumer "
            "coverage pages and managed-care policy. codes.ohio.gov served us-oh-snap-rules.yaml "
            "(OAC 5101:4) in July 2026, so this is probably transient; retry before treating the "
            "block as durable. 0 taken."
        ),
    },
    "us-az": {
        "name": "Arizona",
        "index_url": "https://epm.azahcccs.gov/",
        "index_document_count": None,
        "primary_source_url": "https://epm.azahcccs.gov/",
        "notes": (
            "Blocked. AHCCCS publishes the Medical Assistance Eligibility Policy Manual (KidsCare is "
            "its chapter 408) at epm.azahcccs.gov; that host, www.azahcccs.gov (AMPM index, program "
            "pages) and the site root all return HTTP 403 Forbidden to plain, WebFetch and chrome120 "
            "clients. The adopted KidsCare rule A.A.C. Title 9 Chapter 31 at the Arizona Secretary of "
            "State (apps.azsos.gov/public_services/Title_09/9-31.pdf) returns a Cloudflare JavaScript "
            "challenge ('Just a moment...', HTTP 403). 0 taken."
        ),
    },
    "us-sc": {
        "name": "South Carolina",
        "index_url": "https://img1.scdhhs.gov/mppm/",
        "index_document_count": None,
        "primary_source_url": "https://img1.scdhhs.gov/mppm/",
        "notes": (
            "Blocked. South Carolina's CHIP (Partners for Healthy Children) is Medicaid-expansion CHIP "
            "governed by the SCDHHS Medicaid Policy and Procedures Manual (MPPM; Chapter 204 Healthy "
            "Connections Plans for Children), published at img1.scdhhs.gov/mppm/ and "
            "www1.scdhhs.gov/mppm/. Both hosts present their leaf certificate without the issuing "
            "intermediate (Go Daddy Secure Certificate Authority - G2); the chain was repaired with the "
            "publisher's public intermediate fetched from the leaf's AIA URL "
            "(data/certs/godaddy-secure-certificate-authority-g2.pem) via REQUESTS_CA_BUNDLE, TLS "
            "verification never disabled. With the chain verified, both hosts return HTTP 403 'Error "
            "Page' to plain and chrome120 clients, and www.scdhhs.gov (CloudFront) returns HTTP 403 "
            "'The request could not be satisfied' for its policy index pages. 0 taken."
        ),
    },
}

MEDICAID_RUN_VERSION = "2026-09-10-medicaid-state-eligibility-manual"
MEDICAID_RUN_NOTE = (
    "Manifest lives on the parallel Medicaid branch (discovery/ingest-medicaid); artifacts share "
    "data/corpus in the main checkout."
)

DONE_BATCH2: dict[str, dict] = {
    "us-nc": {
        "name": "North Carolina",
        "index_url": "https://policies.ncdhhs.gov/divisional/health-benefits-nc-medicaid/family-and-childrens-medicaid/",
        "index_document_count": 64,
        "target_manifest": f"discovery/ingest-medicaid: us-nc/manual {MEDICAID_RUN_VERSION}",
        "target_scope": {"jurisdiction": "us-nc", "document_class": "manual", "version": MEDICAID_RUN_VERSION},
        "pointer": "us-nc/manual/dhb/medicaid/ma-3xxx (Family and Children's Medicaid manual, 64 documents incl. fcm table of contents)",
        "notes": (
            "Done by pointer (reviewer judgment). NC Health Choice, the separate CHIP, was folded into "
            "NC Medicaid on 2023-04-01; CHIP-funded children are determined under the Family and "
            "Children's Medicaid manual (MA-3xxx), which the parallel Medicaid run ingested in full on "
            "2026-09-10 (64 F&C documents at us-nc/manual/dhb/medicaid/ma-3100 ... ma-3570 plus the "
            "fcm table of contents, version " + MEDICAID_RUN_VERSION + "). " + MEDICAID_RUN_NOTE +
            " policies.ncdhhs.gov returns HTTP 403 to the WebFetch client; the index count is the "
            "Medicaid run's inventory. Nothing separate to add."
        ),
    },
    "us-nj": {
        "name": "New Jersey",
        "index_url": "https://www.nj.gov/humanservices/notices/documents/rules-and-regulations/",
        "index_document_count": 6,
        "target_manifest": f"discovery/ingest-medicaid: us-nj/manual {MEDICAID_RUN_VERSION}",
        "target_scope": {"jurisdiction": "us-nj", "document_class": "manual", "version": MEDICAID_RUN_VERSION},
        "pointer": "us-nj/manual/dhs/medicaid/njac-10-79 (N.J.A.C. 10:79 NJ FamilyCare-Children's Program, 115 page provisions)",
        "notes": (
            "Done by pointer (reviewer judgment). New Jersey's CHIP eligibility rule is N.J.A.C. 10:79 "
            "NJ FamilyCare-Children's Program (DHS/DMAHS rules-and-regulations PDF set: 10:69, 10:70, "
            "10:71, 10:72, 10:78, 10:79), already ingested by the parallel Medicaid run on 2026-09-10 "
            "at us-nj/manual/dhs/medicaid/njac-10-79 (115 page provisions, version "
            + MEDICAID_RUN_VERSION + "). " + MEDICAID_RUN_NOTE + " The HTML index page for that PDF "
            "folder was not re-located in this run (three candidate DHS URLs returned 404); the "
            "folder listing count is the Medicaid run's inventory. Nothing separate to add."
        ),
    },
    "us-va": {
        "name": "Virginia",
        "index_url": "https://www.dmas.virginia.gov/for-providers/eligibility-manual/",
        "index_document_count": 21,
        "target_manifest": f"discovery/ingest-medicaid: us-va/manual {MEDICAID_RUN_VERSION}",
        "target_scope": {"jurisdiction": "us-va", "document_class": "manual", "version": MEDICAID_RUN_VERSION},
        "pointer": "us-va/manual/dmas/medicaid/m21 (Chapter M21 FAMIS, 22 provisions; also m22 FAMIS MOMS, m23 FAMIS Prenatal)",
        "notes": (
            "Done by pointer (reviewer judgment). Virginia's CHIP (FAMIS) eligibility is Chapter M21 "
            "FAMIS of the DMAS Virginia Medical Assistance Eligibility Manual, with M22 FAMIS MOMS and "
            "M23 FAMIS Prenatal Coverage; all three were ingested by the parallel Medicaid run on "
            "2026-09-10 (21 manual chapters, us-va/manual/dmas/medicaid/m21 has 22 provisions, version "
            + MEDICAID_RUN_VERSION + "). " + MEDICAID_RUN_NOTE + " Nothing separate to add."
        ),
    },
}


# --- batch 3 (docs/ingest-runs/2026-09-10-chip-state-eligibility-manuals-batch-3.md) -----------
# Next ten states by population not in the queue (KY, OR, OK, UT, NV, AR, MS, NM, NE, WV) with
# replacements HI, NH, ME, MT, RI, SD. AR and WV are already covered by combined manuals in the
# corpus; OR, NE, HI, NH, UT and MT publishers blocked on the first probe (see BLOCKED_BATCH3).

BATCH3_DISCOVERED_VIA = (
    "manual-review:chip-agent-queue batch 3; publisher index confirmed by agent 2026-09-10"
)

NEW_ROW_NAMES_BATCH3: dict[str, str] = {
    "us-ar": "Arkansas", "us-hi": "Hawaii", "us-ky": "Kentucky", "us-me": "Maine",
    "us-ms": "Mississippi", "us-mt": "Montana", "us-ne": "Nebraska", "us-nh": "New Hampshire",
    "us-nm": "New Mexico", "us-nv": "Nevada", "us-ok": "Oklahoma", "us-or": "Oregon",
    "us-ri": "Rhode Island", "us-sd": "South Dakota", "us-ut": "Utah", "us-wv": "West Virginia",
}

OK_OHCA_SUBCHAPTER_6_INDEX = (
    "https://oklahoma.gov/ohca/policies-and-rules/xpolicy/"
    "medical-assistance-for-adults-and-children-eligibility/"
    "soonercare-for-pregnant-women-and-families-with-children.html"
)
OK_RULES_API_317_35 = (
    "https://prod-ok-rules-api.tecuity.com/GetSegmentsByChapterNum?titleNum=317&chapterNum=35"
)
OK_RECORD_METADATA_FIELDS = [
    "id", "parentId", "name", "titleNum", "chapterNum", "subChapterNum", "partNum", "sectionNum",
    "appendixNum", "description", "statusName", "segmentStatusId", "segmentTypeId", "recordStatus",
    "effectiveDate", "filingId", "hasEmergency", "segmentNotes",
]


MS_EPM_HEADING = r"^\s*(?P<num>{ch}\.\d{{2}}(?:\.\d{{2}}[A-Z]?)?)\s+(?P<heading>[A-Z][A-Z0-9 ,\-–’'()/&:.]+?)\s*$"
MS_EPM_LABEL = r"^\s*(?P<num>{ch}\.\d{{2}}(?:\.\d{{2}}[A-Z]?)?)\s*$"
MS_EPM_LABEL_HEADING = r"^\s*[A-Z][A-Z0-9 ,\-–’'()/&:.]+\s*$"
MS_EPM_DROP = [
    r"^\s*MISSISSIPPI DIVISION OF MEDICAID\s*$",
    r"^\s*Eligibility Policy and Procedures Manual\s*$",
    r"^\s*CHAPTER \d{3} – .*$",
    r"^\s*P\s?a\s?g\s?e\s*\|\s*\d+\s*$",
    r"^\s*Effective Month:.*$",
]


def _ms_chapter_extraction(chapter: str, start_page: int) -> dict:
    return {
        "segmentation": "labeled_sections",
        "start_page": start_page,
        "section_heading_pattern": MS_EPM_HEADING.format(ch=chapter),
        "section_label_pattern": MS_EPM_LABEL.format(ch=chapter),
        "label_only_heading_pattern": MS_EPM_LABEL_HEADING,
        "label_only_requires_heading": True,
        "section_label_template": "{num}",
        "heading_continuation_pattern": NEVER_CONTINUE,
        "drop_line_patterns": MS_EPM_DROP,
    }


NM_8_291_HEADING = (
    r"^(?P<label>8\s*\.\s*291\s*\.\s*{part}\s*\.\s*(?P<num>\d+(?:\s*-\s*\d+)?))\s+(?P<heading>[A-Z][^:]{{0,180}}:|\[RESERVED\]|"
    r"[A-Z][A-Z0-9 /()\[\]\-–—,'&]{{0,180}})(?:\s+(?P<body>.*))?$"
)


def _nm_part_doc(part: str, title: str, expression_date: str) -> dict:
    d = doc(
        "us-nm", f"nm-srca-nmac-8-291-{part}",
        f"8.291.{part} NMAC {title}",
        f"https://www.srca.nm.gov/parts/title08/08.291.0{part}.html",
        f"us-nm/regulation/nmac/8/291/{part}", "html", expression_date,
        document_class="regulation",
        subtype="administrative_code",
        authority="New Mexico State Records Center and Archives",
        extraction={
            "html_content_selector": ".WordSection1, .Section1",
            "segmentation": "labeled_sections",
            "section_heading_pattern": NM_8_291_HEADING.format(part=part),
            "section_label_template": f"8.291.{part}.{{num}}",
            "normalize_label_internal_whitespace": True,
        },
        metadata={
            "issuing_agency": "New Mexico Health Care Authority",
            "legal_identifier": f"8.291.{part} NMAC",
            "nmac_title": "8", "nmac_chapter": "291", "nmac_part": part,
            "nmac_title_index_url": "https://www.srca.nm.gov/nmac-home/nmac-titles/title-8-social-services/",
            "state_program": "Medicaid eligibility - affordable care (MAGI children incl. Title XXI-funded)",
        },
    )
    d["metadata"]["discovered_via"] = BATCH3_DISCOVERED_VIA
    return d


def _sd_chapter_doc(chapter: str, title: str, expression_date: str) -> dict:
    d = doc(
        "us-sd", f"sd-lrc-arsd-67-46-{chapter}",
        f"ARSD Chapter 67:46:{chapter} {title}",
        f"https://sdlegislature.gov/api/Rules/67:46:{chapter}",
        f"us-sd/regulation/arsd/67/46/{chapter}", "json", expression_date,
        document_class="regulation",
        subtype="administrative_rule_chapter",
        authority="South Dakota Department of Social Services (ARSD Article 67:46), published by the South Dakota Legislative Research Council",
        extraction={
            "json_html_field": "Html",
            "segmentation": "labeled_sections",
            "section_heading_pattern": rf"^67:46:{chapter}:(?P<num>\d{{2}})\s*\.\s+(?P<heading>[^.]+\.)\s*(?P<body>.*)$",
            "section_label_template": "{num}",
        },
        metadata={
            "legal_identifier": f"ARSD 67:46:{chapter}",
            "landing_page": f"https://sdlegislature.gov/Rules/Administrative/67:46:{chapter}",
            "article_index": "https://sdlegislature.gov/api/Rules/67:46",
        },
    )
    d["metadata"]["discovered_via"] = BATCH3_DISCOVERED_VIA
    return d


CONFIRMED_BATCH3: dict[str, dict] = {
    "us-ky": {
        "name": "Kentucky",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_html",
        "index_url": "https://apps.legislature.ky.gov/law/kar/titles/907/004/",
        "index_document_count": 2,
        "index_families": {"kar_regulation_html": 2},
        "primary_source_url": "https://apps.legislature.ky.gov/law/kar/titles/907/004/020/",
        "notes": (
            "Kentucky Legislative Research Commission index for 907 KAR Chapter 4 (Kentucky Children's "
            "Health Insurance Program): 2 regulations, 907 KAR 4:020 KCHIP Medicaid Expansion and 907 KAR "
            "4:030 KCHIP Phase III (separate CHIP), both last amended effective 2023-01-12 per their "
            "HISTORY lines. Taken 2, one HTML document each (div.regulation-content), whole regulation "
            "as one provision because the LRC page marks each section and paragraph as an h2 with the "
            "text in spans. The DCBS Operations Manual Volume IVA (Medicaid) at chfs.ky.gov was not "
            "located on a public index in this run."
        ),
        "documents": [
            doc(
                "us-ky", f"ky-lrc-907-kar-4-{num}",
                f"907 KAR 4:{num}. {title}",
                f"https://apps.legislature.ky.gov/law/kar/titles/907/004/{num}/",
                f"us-ky/regulation/kar/907/004/{num}", "html", "2023-01-12",
                document_class="regulation",
                subtype="administrative_regulation",
                authority="Kentucky Cabinet for Health and Family Services, Department for Medicaid Services (907 KAR), published by the Legislative Research Commission",
                extraction={"html_content_selector": "div.regulation-content"},
                metadata={"legal_identifier": f"907 KAR 4:{num}", "state_program": "KCHIP",
                          "history_effective": "2023-01-12"},
            )
            for num, title in (
                ("020", "Kentucky Children's Health Insurance Program Medicaid Expansion Title XXI of the Social Security Act"),
                ("030", "Kentucky Children's Health Insurance Program Phase III Title XXI of the Social Security Act"),
            )
        ],
    },
    "us-ok": {
        "name": "Oklahoma",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_json_records",
        "index_url": OK_RULES_API_317_35,
        "index_document_count": 397,
        "index_families": {"oac_section": 350, "oac_part": 29, "oac_subchapter": 17, "oac_chapter": 1},
        "primary_source_url": "https://rules.ok.gov/home",
        "notes": (
            "Oklahoma Secretary of State Office of Administrative Rules (rules.ok.gov, the official OAC "
            "publisher; same segments API as us-ok-snap-rules.yaml) chapter listing for OAC 317:35 "
            "Medical Assistance for Adults and Children - Eligibility: 397 segments (350 sections, 29 "
            "parts, 17 subchapters, the chapter; statuses 292 in force, 82 Revoked, 17 Terminated, 4 "
            "Reserved, 2 AmendedAndRenumbered). Oklahoma's CHIP is Medicaid-expansion SoonerCare for "
            "children, governed by Subchapter 6 SoonerCare for Pregnant Women and Families with Children. "
            "Taken 1 document, the chapter JSON filtered to the 29 Subchapter 6 sections (label prefix "
            "317:35-6-; Revoked and Reserved excluded; 62 and 62.1, AmendedAndRenumbered, carry no text in "
            "the API and yield no provision, so 27 section provisions result). The OHCA "
            "policy site lists the same 29 sections but states its copies are unofficial, so it is "
            "recorded only as the agency index. The API returns HTTP 403 to the plain client and is read "
            "through the manifest browser_impersonation fallback. Not taken: subchapters 5, 10, 22."
        ),
        "documents": [
            doc(
                "us-ok", "ok-oac-317-35-6-soonercare-children-families",
                "Oklahoma Administrative Code Title 317 Chapter 35 Subchapter 6 SoonerCare for Pregnant Women and Families with Children",
                "https://rules.ok.gov/home",
                "us-ok/regulation/oac/317/35", "json", SOURCE_AS_OF,
                document_class="regulation",
                subtype="administrative_code_subchapter",
                authority="Oklahoma Health Care Authority (OAC Title 317), published by the Oklahoma Secretary of State Office of Administrative Rules",
                request=IMPERSONATE,
                extraction={
                    "segmentation": "records",
                    "json_record_text_field": "text",
                    "json_record_text_is_html": True,
                    "json_record_label_field": "sectionNum",
                    "json_record_heading_field": "description",
                    "json_record_kind_field": "name",
                    "json_record_status_field": "statusName",
                    "json_record_exclude_statuses": ["Revoked", "Reserved"],
                    "json_record_include_label_prefixes": ["317:35-6-"],
                    "json_record_metadata_fields": OK_RECORD_METADATA_FIELDS,
                },
                metadata={
                    "official_publisher": "Oklahoma Secretary of State Office of Administrative Rules",
                    "rules_landing_page": "https://rules.ok.gov/home",
                    "rules_api_url": OK_RULES_API_317_35,
                    "agency_policy_site_index": OK_OHCA_SUBCHAPTER_6_INDEX,
                    "legal_identifier": "OAC 317:35-6",
                    "state_program": "SoonerCare (Medicaid-expansion CHIP for children)",
                    "expression_date_note": "chapter compilation as served on source_as_of; per-section effectiveDate kept in record metadata",
                },
            ),
        ],
    },
    "us-nv": {
        "name": "Nevada",
        "document_class": "manual",
        "source_kind": "official_pdf_manual_chapter",
        "index_url": "https://dwss.nv.gov/programs/medical/medical-assistance-manual/",
        "index_document_count": 93,
        "index_families": {"mam_chapter_pdf": 23, "mam_appendix_pdf": 9, "mam_full_manual_pdf": 1,
                           "mam_table_of_contents_pdf": 1, "manual_transmittal_letter_pdf": 59},
        "primary_source_url": "https://dwss.nv.gov/uploadedFiles/dwssnvgov/content/Medical/B-100%20MAGI%20Medical%20Categories%20Mar%2017.pdf",
        "notes": (
            "Nevada DWSS Medical Assistance Manual index: 93 documents (23 chapter PDFs A-100 to H-200, "
            "9 appendices, the full manual, the table of contents, 59 manual transmittal letters). "
            "Nevada Check Up (the separate CHIP) is determined under the MAM: section B-120.2 Nevada "
            "Check Up in chapter B-100 MAGI Medical Categories (March 2017) and Appendix A MAGI Income "
            "Charts (November 2024). Taken 2, page-level (the running page header repeats the section "
            "label, so labeled sections would collide). Not taken: E-100 MAGI Budget Methodology, the "
            "2014 'Nevada Check Up Manual revised sections' PDF linked from the Nevada Check Up page."
        ),
        "documents": [
            doc(
                "us-nv", "nv-dwss-mam-b-100",
                "Nevada DWSS Medical Assistance Manual B-100 Modified Adjusted Gross Income (MAGI) Medical Categories",
                "https://dwss.nv.gov/uploadedFiles/dwssnvgov/content/Medical/B-100%20MAGI%20Medical%20Categories%20Mar%2017.pdf",
                "us-nv/manual/dwss/chip/mam-b-100", "pdf", "2017-03-01",
                subtype="eligibility_manual_chapter_pdf",
                authority="Nevada Division of Welfare and Supportive Services",
                extraction=PAGES,
                metadata={"state_program": "Nevada Check Up", "manual_section": "B-100",
                          "chip_section": "B-120.2"},
            ),
            doc(
                "us-nv", "nv-dwss-mam-appendix-a",
                "Nevada DWSS Medical Assistance Manual Appendix A MAGI Income Charts",
                "https://dwss.nv.gov/uploadedFiles/dwssnvgov/content/Medical/Appendix%20A%20MAGI%20Income%20Charts%20ADA%20Nov%20-%2024.pdf",
                "us-nv/manual/dwss/chip/mam-appendix-a", "pdf", "2024-11-01",
                subtype="income_standards_chart_pdf",
                authority="Nevada Division of Welfare and Supportive Services",
                extraction=PAGES,
                metadata={"state_program": "Nevada Check Up", "manual_section": "Appendix A"},
            ),
        ],
    },
    "us-ms": {
        "name": "Mississippi",
        "document_class": "manual",
        "source_kind": "official_pdf_manual_chapter",
        "index_url": "https://medicaid.ms.gov/medicaid-coverage/eligibility-policy/",
        "index_document_count": 27,
        "index_families": {"eligibility_manual_chapter_pdf": 7, "eligibility_manual_appendix_pdf": 20},
        "primary_source_url": "https://medicaid.ms.gov/wp-content/uploads/2025/09/Chapter-101-Coverage-Groups-and-Processing-Applications-and-Reviews-revised-September2025.pdf",
        "notes": (
            "Mississippi Division of Medicaid Eligibility Policy and Procedures Manual index: 7 chapter "
            "PDFs (100, 101, 102, 200, 300, 400, 500) and 20 appendices. Mississippi's separate CHIP "
            "(COE-099) is determined under this manual. Taken 3: Chapter 101 Coverage Groups and "
            "Processing Applications and Reviews (revised September 2025; CHIP coverage group, 101.10.02 "
            "beginning dates of CHIP eligibility), Chapter 400 ABD and MAGI Eligibility Criteria and "
            "Budgeting (revised July 2025; 400.18-400.19 children and CHIP), labeled sections from the "
            "chapter's own numbering after the table of contents; Appendix A-3 MAGI Income Limits chart "
            "(uploaded March 2026), page-level. Not taken: chapters 100, 102, 200, 300, 500 and the "
            "other appendices."
        ),
        "documents": [
            doc(
                "us-ms", "ms-dom-epm-chapter-101",
                "Mississippi Division of Medicaid Eligibility Policy and Procedures Manual Chapter 101 Coverage Groups and Processing Applications and Reviews",
                "https://medicaid.ms.gov/wp-content/uploads/2025/09/Chapter-101-Coverage-Groups-and-Processing-Applications-and-Reviews-revised-September2025.pdf",
                "us-ms/manual/dom/chip/epm-chapter-101", "pdf", "2025-09-01",
                subtype="eligibility_manual_chapter_pdf",
                authority="Mississippi Division of Medicaid",
                extraction=_ms_chapter_extraction("101", 6),
                metadata={"state_program": "Mississippi CHIP (COE-099)", "manual_chapter": "101",
                          "revised": "September 2025"},
            ),
            doc(
                "us-ms", "ms-dom-epm-chapter-400",
                "Mississippi Division of Medicaid Eligibility Policy and Procedures Manual Chapter 400 ABD and MAGI Eligibility Criteria and Budgeting",
                "https://medicaid.ms.gov/wp-content/uploads/2025/07/Chapter-400-ABD-and-MAGI-Eligibility-Criteria-and-Budgeting.-Revised-July-2025v2.pdf",
                "us-ms/manual/dom/chip/epm-chapter-400", "pdf", "2025-07-01",
                subtype="eligibility_manual_chapter_pdf",
                authority="Mississippi Division of Medicaid",
                extraction=_ms_chapter_extraction("400", 4),
                metadata={"state_program": "Mississippi CHIP (COE-099)", "manual_chapter": "400",
                          "revised": "July 2025"},
            ),
            doc(
                "us-ms", "ms-dom-epm-appendix-a-3",
                "Mississippi Division of Medicaid Eligibility Policy and Procedures Manual Appendix A-3 Modified Adjusted Gross Income (MAGI) Limits Chart",
                "https://medicaid.ms.gov/wp-content/uploads/2026/03/Appendix-A-3-MAGI-Income-Limits.-2014-to-present.pdf",
                "us-ms/manual/dom/chip/epm-appendix-a-3", "pdf", "2026-03-01",
                subtype="income_standards_chart_pdf",
                authority="Mississippi Division of Medicaid",
                extraction=PAGES,
                metadata={"state_program": "Mississippi CHIP (COE-099)", "manual_appendix": "A-3",
                          "expression_date_note": "publisher upload month (2026/03); the chart carries no cover date"},
            ),
        ],
    },
    "us-nm": {
        "name": "New Mexico",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_html",
        "index_url": "https://www.srca.nm.gov/nmac-home/nmac-titles/title-8-social-services/",
        "index_document_count": 4,
        "index_families": {"nmac_part_html_in_force": 4},
        "primary_source_url": "https://www.srca.nm.gov/parts/title08/08.291.0400.html",
        "notes": (
            "New Mexico State Records Center and Archives NMAC Title 8 index, Chapter 291 Medicaid "
            "Eligibility - Affordable Care (the chapter link redirects to the title page, whose chapter "
            "291 entry lists only reserved ranges; parts 400, 410, 420, 430 were confirmed by fetching, "
            "440+ return 404). New Mexico's CHIP is Medicaid-expansion coverage determined under these "
            "MAGI rules. Taken 4: 8.291.400 Eligibility Requirements (amended through 2024-09-01), "
            "8.291.410 General Recipient Requirements (2024-07-01), 8.291.420 Recipient Rights and "
            "Responsibilities (2024-07-01), 8.291.430 Financial Responsibility Requirements (2025-04-01), "
            "labeled sections with the same pattern as us-nm-snap-regulations.yaml; expression_date is "
            "the latest history date in each part."
        ),
        "documents": [
            _nm_part_doc("400", "Eligibility Requirements", "2024-09-01"),
            _nm_part_doc("410", "General Recipient Requirements", "2024-07-01"),
            _nm_part_doc("420", "Recipient Rights and Responsibilities", "2024-07-01"),
            _nm_part_doc("430", "Financial Responsibility Requirements", "2025-04-01"),
        ],
    },
    "us-me": {
        "name": "Maine",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_docx",
        "index_url": "https://www.maine.gov/sos/cec/rules/10/ch332.htm",
        "index_document_count": 6,
        "index_families": {"rule_chapter_docx": 2, "rule_chapter_doc": 3, "rule_appendices_docx": 1},
        "primary_source_url": "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/144c332-2025-101%20NSC.docx",
        "notes": (
            "Maine Secretary of State APA Office page for 10-144 C.M.R. Chapter 332 MaineCare Eligibility "
            "Manual: 6 documents (Chapter 332 Word, its appendices and charts, Chapters 333-336). Part 5 "
            "Children's Health Insurance Program (CHIP, formerly CubCare) of Chapter 332 is Maine's CHIP "
            "eligibility rule; last updated (effective) 2025-04-29, filing 2025-101. Taken 1 document, "
            "Part 5 only (start after the body 'PART 5' heading, stop at 'PART 6'; 10 sections). Not "
            "taken: the other 11 parts of Chapter 332, the appendices, Chapters 333-336."
        ),
        "documents": [
            doc(
                "us-me", "me-ofi-mainecare-eligibility-manual-chapter-332-part-5",
                "Maine 10-144 C.M.R. Chapter 332 MaineCare Eligibility Manual, Part 5: Children's Health Insurance Program (CHIP)",
                "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/144c332-2025-101%20NSC.docx",
                "us-me/regulation/dhhs/ofi/chapter-332/part-5", "docx", "2025-04-29",
                document_class="regulation",
                subtype="administrative_rules_part",
                authority="Maine Department of Health and Human Services Office for Family Independence",
                extraction={
                    "segmentation": "labeled_sections",
                    "start_after_pattern": r"^PART 5$",
                    "stop_text_pattern": r"^PART 6$",
                    "section_heading_pattern": r"^SECTION (?P<num>\d+):\s*(?P<heading>.+)$",
                    "section_label_template": "section-{num}",
                },
                metadata={"publication_authority": "Maine Secretary of State Administrative Procedure Act Office",
                          "rule_chapter": "10-144 C.M.R. Chapter 332", "rule_part": "5",
                          "rule_filing": "2025-101", "state_program": "Maine CHIP (formerly CubCare)"},
            ),
        ],
    },
    "us-ri": {
        "name": "Rhode Island",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_pdf",
        "index_url": "https://rules.sos.ri.gov/Organizations/SubChapter/210-30-00",
        "index_document_count": 4,
        "index_families": {"ricr_part_active": 4},
        "primary_source_url": "https://rules.sos.ri.gov/regulations/Part/210-30-00-1",
        "notes": (
            "Rhode Island Code of Regulations (Department of State) Title 210 EOHHS, Chapter 30 Medicaid "
            "for Children, Families and ACA Adults (4 subchapters: 00 Affordable Coverage Groups, 05, 10, "
            "15); Subchapter 00 lists 4 active parts (1, 3, 4, 5). RIte Care children including the "
            "CHIP-funded group are determined under these parts. Taken 2: 210-RICR-30-00-1 Medicaid "
            "Affordable Care Coverage Groups Overview and Eligibility Pathways (effective 2025-08-17) and "
            "210-RICR-30-00-5 Medicaid MAGI Financial Eligibility Determinations and Verification "
            "(effective 2025-08-28), the 'Download Regulation' PDFs, page-level like us-ri-snap-rules.yaml. "
            "Not taken: parts 3 (application and renewal) and 4 (hospital presumptive eligibility)."
        ),
        "documents": [
            doc(
                "us-ri", "ri-eohhs-210-ricr-30-00-1",
                "210-RICR-30-00-1 Medicaid Affordable Care Coverage Groups Overview and Eligibility Pathways",
                "https://rules.sos.ri.gov/regulations/Part/210-30-00-1",
                "us-ri/regulation/210-ricr/30/00/1", "pdf", "2025-08-17",
                document_class="regulation",
                subtype="administrative_regulation",
                authority="Rhode Island Executive Office of Health and Human Services",
                extraction=PAGES,
                metadata={"official_publisher": "Rhode Island Department of State",
                          "legal_identifier": "210-RICR-30-00-1", "regulation_effective_date": "2025-08-17",
                          "download_url_note": "Download Regulation PDF REG_13314_20250728104245127.pdf"},
            ),
            doc(
                "us-ri", "ri-eohhs-210-ricr-30-00-5",
                "210-RICR-30-00-5 Medicaid MAGI Financial Eligibility Determinations and Verification",
                "https://rules.sos.ri.gov/regulations/Part/210-30-00-5",
                "us-ri/regulation/210-ricr/30/00/5", "pdf", "2025-08-28",
                document_class="regulation",
                subtype="administrative_regulation",
                authority="Rhode Island Executive Office of Health and Human Services",
                extraction=PAGES,
                metadata={"official_publisher": "Rhode Island Department of State",
                          "legal_identifier": "210-RICR-30-00-5", "regulation_effective_date": "2025-08-28",
                          "download_url_note": "Download Regulation PDF REG_13331_20250808145837454.pdf"},
            ),
        ],
    },
    "us-sd": {
        "name": "South Dakota",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_json_html",
        "index_url": "https://sdlegislature.gov/api/Rules/67:46",
        "index_document_count": 13,
        "index_families": {"arsd_chapter": 13},
        "primary_source_url": "https://sdlegislature.gov/api/Rules/67:46:14",
        "notes": (
            "South Dakota Legislature ARSD Article 67:46 Eligibility for Medical Services (13 chapters, "
            "read from the Legislative Research Council's rules API because sdlegislature.gov/Rules/"
            "Administrative/67:46 is script-rendered). Taken 2: Chapter 67:46:14 Nonmedicaid Children's "
            "Health Insurance Program (the separate CHIP rule; latest effective 2024-11-11) and Chapter "
            "67:46:12 MAGI Medicaid Eligibility Standards (Medicaid-expansion children; 2023-07-03), one "
            "JSON document each (Html field), sections split on the body headings '67:46:14:NN.'; the "
            "chapter's table-of-contents lines have no period after the number and are not sections."
        ),
        "documents": [
            _sd_chapter_doc("14", "Nonmedicaid Children's Health Insurance Program", "2024-11-11"),
            _sd_chapter_doc("12", "Modified Adjusted Gross Income (MAGI) Medicaid Eligibility Standards", "2023-07-03"),
        ],
    },
}
for _spec in CONFIRMED_BATCH3.values():
    for _d in _spec["documents"]:
        _d["metadata"]["discovered_via"] = BATCH3_DISCOVERED_VIA
CONFIRMED_BATCH3["us-ok"]["documents"][0]["download_url"] = OK_RULES_API_317_35
CONFIRMED_BATCH3["us-ri"]["documents"][0]["download_url"] = (
    "https://risos-apa-production-public.s3.amazonaws.com/EOHHS/REG_13314_20250728104245127.pdf"
)
CONFIRMED_BATCH3["us-ri"]["documents"][1]["download_url"] = (
    "https://risos-apa-production-public.s3.amazonaws.com/EOHHS/REG_13331_20250808145837454.pdf"
)

BLOCKED_BATCH3: dict[str, dict] = {
    "us-or": {
        "name": "Oregon",
        "index_url": "https://secure.sos.state.or.us/oard/displayChapterRules.action?selectedChapter=94",
        "index_document_count": None,
        "primary_source_url": "https://secure.sos.state.or.us/oard/displayChapterRules.action?selectedChapter=94",
        "notes": (
            "Blocked. Oregon's CHIP is Medicaid-expansion Oregon Health Plan coverage governed by OAR "
            "chapter 410 division 200 (OHA Health Systems Division, published by the Secretary of State's "
            "OARD). On 2026-09-10 the oregon.gov DNS zone did not resolve: secure.sos.state.or.us and "
            "www.oregon.gov returned SERVFAIL from the authoritative servers (dig @1.1.1.1 and @8.8.8.8, "
            "NS lookup for oregon.gov SERVFAIL), so both the plain and chrome120 probes failed with name "
            "resolution errors after 20 s. Probably transient; retry before treating as durable. 0 taken."
        ),
    },
    "us-ne": {
        "name": "Nebraska",
        "index_url": "https://rules.nebraska.gov/rules?agencyId=41",
        "index_document_count": None,
        "primary_source_url": "https://dhhs.ne.gov/Pages/Medicaid-Regulations.aspx",
        "notes": (
            "Blocked. Nebraska's CHIP is Medicaid-expansion coverage under 477 NAC (DHHS Medicaid "
            "eligibility regulations). dhhs.ne.gov did not accept TCP connections on 443 (ConnectTimeout "
            "20 s plain; curl (28) 20 s chrome120). The Secretary of State's Nebraska Administrative "
            "Code site rules.nebraska.gov serves its leaf certificate without the DigiCert Global G2 TLS "
            "RSA SHA256 2020 CA1 intermediate; with the already-committed data/certs/"
            "digicert-global-g2-tls-rsa-sha256-2020-ca1.pem in REQUESTS_CA_BUNDLE the chain verifies, "
            "after which the site root and the agency listing return HTTP 403 to plain and chrome120 "
            "clients. TLS verification was never disabled. 0 taken."
        ),
    },
    "us-hi": {
        "name": "Hawaii",
        "index_url": "https://medquest.hawaii.gov/en/plans-providers/har.html",
        "index_document_count": None,
        "primary_source_url": "https://medquest.hawaii.gov/en/plans-providers/har.html",
        "notes": (
            "Blocked. Hawaii's CHIP is Medicaid-expansion QUEST coverage governed by Med-QUEST Division "
            "administrative rules (HAR Title 17); medquest.hawaii.gov returned HTTP 522 (Cloudflare origin "
            "timeout, empty body, ~20 s) to plain and chrome120 clients. 0 taken."
        ),
    },
    "us-nh": {
        "name": "New Hampshire",
        "index_url": "https://www.gencourt.state.nh.us/rules/state_agencies/he-w800.html",
        "index_document_count": None,
        "primary_source_url": "https://www.gencourt.state.nh.us/rules/state_agencies/he-w800.html",
        "notes": (
            "Blocked. New Hampshire's CHIP eligibility rules are DHHS He-W 800 (medical assistance) "
            "published by the Office of Legislative Services at gencourt.state.nh.us: HTTP 403 'Error 403' "
            "to the plain client; the chrome120 request was closed abruptly (curl 56). 0 taken."
        ),
    },
    "us-ut": {
        "name": "Utah",
        "index_url": "https://oepmanuals-chip.dhhs.utah.gov/Welcome_page.htm",
        "index_document_count": None,
        "primary_source_url": "https://oepmanuals-chip.dhhs.utah.gov/Welcome_page.htm",
        "notes": (
            "Blocked. Utah DHHS Office of Eligibility Policy publishes a separate CHIP eligibility policy "
            "manual at oepmanuals-chip.dhhs.utah.gov (effective 2024-05-01); the host returns HTTP 403 "
            "AccessDenied (111-byte XML) to plain and chrome120 clients for the welcome page and the site "
            "root. The former Medicaid eligibility manual hosts medicaidpolicy.utah.gov and "
            "bepmanuals.health.utah.gov are NXDOMAIN. The adopted rule R382-10 lives only in the Office of "
            "Administrative Rules eRules single-page app (adminrules.utah.gov; plain client 404, no public "
            "rule endpoint found in its bundle), and medicaid.utah.gov publishes no eligibility manual. "
            "The existing us-ut/manual DWS Eligibility Manual scope has no CHIP chapter. 0 taken."
        ),
    },
    "us-mt": {
        "name": "Montana",
        "index_url": "https://rules.mt.gov/gateway/ChapterHome.asp?Chapter=37%2E79",
        "index_document_count": None,
        "primary_source_url": "https://rules.mt.gov/gateway/ChapterHome.asp?Chapter=37%2E79",
        "notes": (
            "Blocked. Montana's CHIP (Healthy Montana Kids) eligibility rule is ARM 37.79, published by "
            "the Secretary of State at rules.mt.gov. The site (plain client HTTP 200) is now the Esper "
            "'policy-library-public' single-page application: the HTML shell carries no rule text, its "
            "search API returns HTTP 403 AccessDenied to the plain client and the HTML shell to the "
            "chrome120 client, and no document endpoint is discoverable. dphhs.mt.gov/hmk answers (HTTP "
            "200) but publishes only the member guide and evidence of coverage, not an eligibility "
            "manual or rule. 0 taken."
        ),
    },
}

DONE_BATCH3: dict[str, dict] = {
    "us-ar": {
        "name": "Arkansas",
        "index_url": "https://humanservices.arkansas.gov/divisions-shared-services/county-operations/policy/",
        "index_document_count": 1,
        "target_manifest": f"discovery/ingest-medicaid: us-ar/manual {MEDICAID_RUN_VERSION}",
        "target_scope": {"jurisdiction": "us-ar", "document_class": "manual", "version": MEDICAID_RUN_VERSION},
        "pointer": "us-ar/manual/dco/medicaid/policy-manual (DCO Medical Services Policy Manual, 563 page provisions; ARKids First-B is determined under it)",
        "notes": (
            "Done by pointer (reviewer judgment). Arkansas's separate CHIP, ARKids First-B, is determined "
            "under the DHS Division of County Operations Medical Services Policy Manual (MS-Policy-9.26-"
            "New.pdf), which the parallel Medicaid run ingested in full on 2026-09-10 (563 page provisions "
            "at us-ar/manual/dco/medicaid/policy-manual, version " + MEDICAID_RUN_VERSION + "); the text "
            "names ARKids A and ARKids B throughout. " + MEDICAID_RUN_NOTE + " Nothing separate to add."
        ),
    },
    "us-wv": {
        "name": "West Virginia",
        "index_url": "https://bfa.wv.gov/income-maintenance-manual",
        "index_document_count": 1,
        "target_manifest": "manifests/us-wv-manuals.yaml",
        "target_scope": {"jurisdiction": "us-wv", "document_class": "manual", "version": "2026-07-21-wv-income-maintenance-manual"},
        "pointer": "us-wv/manual/bfa/income-maintenance-manual (Income Maintenance Manual effective 2026-07-01, 2276 page provisions; WVCHIP eligibility chapters included)",
        "notes": (
            "Done by pointer (reviewer judgment). West Virginia CHIP (WVCHIP) eligibility is determined "
            "under the Bureau for Family Assistance Income Maintenance Manual, already in the corpus as "
            "us-wv-manuals.yaml (single combined PDF effective 2026-07-01, 2276 page-level provisions, "
            "version 2026-07-21-wv-income-maintenance-manual); the WVCHIP provisions (MAGI Medicaid/WVCHIP "
            "chapters) are inside it. The former dhhr.wv.gov manual index returns 404; the current landing "
            "page is bfa.wv.gov/income-maintenance-manual. Nothing separate to add."
        ),
    },
}



# --- batch 4, retry from a US network (docs/ingest-runs/2026-09-10-chip-state-eligibility-manuals-batch-4-retry.md)
# Every blocked_primary_source row (FL, KS, LA, WI, CA, OH, AZ, SC, OR, NE, HI, NH, UT, MT) was
# retried once plain and once chrome120 (20 s timeouts) from a US exit; the publishers that
# answered were inventoried and extracted here, and the five never-queued jurisdictions (AK, DC,
# ND, VT, WY) were probed. CA, MT and FL still block; DC and WY publish rule text only behind
# ASP.NET postbacks; WI, LA, OH, SC, KS and AZ are covered by the parallel Medicaid run's scopes
# (discovery/ingest-medicaid, same corpus root) and are done by pointer.

BATCH4_DISCOVERED_VIA = (
    "manual-review:chip-agent-queue batch 4 (US-network retry); publisher index confirmed by agent 2026-09-10"
)
RETRIED_AT_BATCH4 = "2026-09-10T21:35Z"

NEW_ROW_NAMES_BATCH4: dict[str, str] = {
    "us-ak": "Alaska",
    "us-dc": "District of Columbia",
    "us-nd": "North Dakota",
    "us-vt": "Vermont",
    "us-wy": "Wyoming",
}

# Still-blocked rows: appended to the existing note (same shape as RETRY_NOTES).
RETRY_NOTES_BATCH4: dict[str, str] = {
    "us-ca": (
        f"retried {RETRIED_AT_BATCH4} from US network, same failure (HTTP 200 with an Incapsula "
        "'Request unsuccessful' JavaScript-challenge iframe, 843-byte body, plain and chrome120; no "
        "MEPM index reachable)."
    ),
    "us-mt": (
        f"retried {RETRIED_AT_BATCH4} from US network, same failure (rules.mt.gov now answers HTTP 405 "
        "with a 'Human Verification' CAPTCHA page requiring JavaScript, plain and chrome120)."
    ),
    "us-fl": (
        f"retried {RETRIED_AT_BATCH4} from US network, different failure (ahca.myflorida.com now answers; "
        "the Florida KidCare page returns HTTP 404 'WebContentNotFound' at /medicaid/florida-kidcare, "
        "/medicaid/florida-kidcare.html and under medicaid-policy-quality-and-operations; the Medicaid and "
        "Medicaid Policy, Quality and Operations pages carry no KidCare or Title XXI eligibility manual or "
        "rule link). No eligibility manual located; still blocked_primary_source."
    ),
}

UT_CHIP_BASE = "https://oepmanuals-chip.dhhs.utah.gov/"
AK_MAGI_BASE = "http://dpaweb.hss.state.ak.us/manuals/MAGI2/"
ND_ACA_BASE = "https://www.nd.gov/dhs/policymanuals/51003/Content/"
ROBOHELP_TOPIC_EXTRACTION = {
    "html_content_selector": "body",
    "html_drop_selectors": ["div.topic-header", "div.topic-header-shadow"],
}
OR_OAR_DIVISION_EXTRACTION = {
    "html_content_selector": "#content",
    "segmentation": "labeled_sections",
    "section_heading_pattern": r"^(?P<label>410-200-\d{4})\s+(?P<heading>[A-Z].*?)\.?$",
}
NE_477_EXTRACTION = {
    "segmentation": "labeled_sections",
    "normalize_parenthetical_label_components": True,
    "section_heading_pattern": (
        r"^(?P<label>0\d{2}(?:\.\d{1,2})?(?:\([A-Za-z0-9]+\))*)\.?\s+"
        r"(?P<heading>[A-Z][A-Z0-9 ’'&,/()\-–‑§]+?(?:\.(?=\s|$)|$))(?:\s+(?P<body>.*))?$"
    ),
    "heading_continuation_pattern": (
        r"^(?P<heading>[A-Z][A-Z0-9 ’'&,/()\-–‑§$]+?(?:\.(?=\s|$)|$))(?:\s+(?P<body>.*))?$"
    ),
}
NH_HE_W_EXTRACTION = {
    "html_content_selector": ".WordSection1",
    "segmentation": "labeled_sections",
    "section_heading_pattern": (
        r"^(?P<prefix>He-W)\s+(?P<part>\d+)\s*\.\s*(?P<section>\d+)\s*(?:[-–]\s*)?"
        r"(?P<heading>.*?)(?:\s+\.\s+(?P<body>.+))?\.?$"
    ),
    "section_label_template": "{prefix} {part}.{section}",
    "stop_text_pattern": "^APPENDIX A",
}
VT_HBEE_DROP = [
    r"^\s*Agency of Human Services\s*$",
    r"^\s*Health Benefits Eligibility and Enrollment\s*$",
    r"^\s*(?:Eligibility Standards|Financial Methodologies)\s*$",
    r"^\s*Part \d – Page \d+ \(Sec\.[^)]*\)\s*$",
]
VT_HBEE_EXTRACTION = {
    "segmentation": "labeled_sections",
    "start_page": 3,
    "section_heading_pattern": r"^\s*(?P<label>\d{1,2}\.\d\d)\s+(?P<heading>[A-Z].*?)\s*\(\d\d/\d\d/\d{4}, GCR [\d-]+\)\s*$",
    "section_label_template": "{label}",
    "heading_continuation_pattern": NEVER_CONTINUE,
    "drop_line_patterns": VT_HBEE_DROP,
}


def _topic_slug(path: str) -> str:

    stem = path.rsplit("/", 1)[-1]
    stem = stem[:-4] if stem.lower().endswith(".htm") else stem
    return re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()


def _ut_topic_doc(path: str, name: str) -> dict:
    slug = _topic_slug(path)
    return doc(
        "us-ut", f"ut-dhhs-chip-{slug}", name, UT_CHIP_BASE + path,
        f"us-ut/manual/dhhs/chip/{slug}", "html", SOURCE_AS_OF,
        subtype="agency_eligibility_manual_topic",
        authority="Utah Department of Health and Human Services, Office of Eligibility Policy (CHIP Policy Manual)",
        extraction=ROBOHELP_TOPIC_EXTRACTION,
        metadata={"manual_section": name.split(" ", 1)[0], "manual_effective_date": "2024-05-01",
                  "discovered_via": BATCH4_DISCOVERED_VIA},
    )


def _ak_topic_doc(path: str, name: str) -> dict:
    slug = _topic_slug(path)
    return doc(
        "us-ak", f"ak-dpa-magi-{slug}", name, AK_MAGI_BASE + path,
        f"us-ak/manual/dpa/magi-medicaid/{slug}", "html", SOURCE_AS_OF,
        subtype="agency_eligibility_manual_topic",
        authority="Alaska Department of Health, Division of Public Assistance (MAGI Medicaid Eligibility Manual)",
        extraction=ROBOHELP_TOPIC_EXTRACTION,
        metadata={"state_program": "Denali KidCare", "discovered_via": BATCH4_DISCOVERED_VIA},
    )


def _nd_topic_doc(filename: str, name: str) -> dict:
    num = filename[:-4]
    return doc(
        "us-nd", f"nd-hhs-{num}", name, ND_ACA_BASE + filename,
        f"us-nd/manual/hhs/aca-medicaid/{num}", "html", "2026-05-15",
        subtype="agency_eligibility_manual_topic",
        authority="North Dakota Health and Human Services, Medical Services Division (Service Chapter 510-03 ACA Medicaid)",
        extraction={"html_content_selector": "#mc-main-content"},
        metadata={"service_chapter_section": num, "manual_release": "26.3 (published 2026-05-15)",
                  "state_program": "Healthy Steps (Medicaid-expansion CHIP)", "discovered_via": BATCH4_DISCOVERED_VIA},
    )


UT_CHIP_TOPICS: tuple[tuple[str, str], ...] = (
    ('100_General_Provisions/100_General_Provisions.htm', '100 General Provisions'),
    ('100_General_Provisions/101_Enrollee_Rights.htm', '101 Enrollee Rights'),
    ('100_General_Provisions/102_Enrollee_Responsibilities.htm', '102 Enrollee Responsibilities'),
    ('100_General_Provisions/102-1_Completion_of_an_Application.htm', '102-1 Completion of an Application'),
    ('100_General_Provisions/102-2_Verification.htm', '102-2 Verification'),
    ('100_General_Provisions/102-3_Report_Changes.htm', '102-3 Report Changes'),
    ('100_General_Provisions/102-5_Cooperate_with_Quality_Reviews.htm', '102-5 Cooperate with Quality Reviews'),
    ('100_General_Provisions/103_Worker_Responsibilities.htm', '103 Worker Responsibilities'),
    ('100_General_Provisions/103-1_Prohibited_Action.htm', '103-1 Prohibited Action'),
    ('100_General_Provisions/104_Authority_of_the_Office_Director.htm', '104 Authority of the Office Director'),
    ('100_General_Provisions/110_Safeguarding_Information.htm', '110 Safeguarding Information'),
    ('100_General_Provisions/110-1_Safeguards_of_Income_Match_Data.htm', '110-1 Safeguards of Income Match Data'),
    ('100_General_Provisions/101-2_Special_Safeguards_for_IRS_Income_Match_Data.htm', '110-2 Special Safeguards for IRS Income Match Data'),
    ('100_General_Provisions/101-3_Who_May_Have_Access_to_Income_Match_Records.htm', '110-3 Who May Have Access to Income Match Records'),
    ('100_General_Provisions/111_Confidential_Information.htm', '111 Confidential Information'),
    ('100_General_Provisions/111-1_Releasing_Information_to_the_Enrollee.htm', '111-1 Releasing Information to the Enrollee'),
    ('100_General_Provisions/111-2_Use_of_Confidential_Information.htm', '111-2 Use of Confidential Information'),
    ('100_General_Provisions/111-3_Releasing_Information_to_Others.htm', '111-3 Releasing Information to Others'),
    ('100_General_Provisions/120_Complaints.htm', '120 Complaints'),
    ('100_General_Provisions/120-1_Agency_Conferences.htm', '120-1 Agency Conferences'),
    ('100_General_Provisions/120-2_Fair_Hearings.htm', '120-2 Fair Hearings'),
    ('100_General_Provisions/120-3_Fair_Hearing_Requests.htm', '120-3 Fair Hearing Requests'),
    ('100_General_Provisions/120-4_The_Hearing.htm', '120-4 The Hearing'),
    ('100_General_Provisions/120-5_Benefits_Pending_A_Hearing_Decision.htm', '120-5 Benefits Pending A Hearing Decision'),
    ('100_General_Provisions/120-6_What_Happens_During_a_Fair_Hearing.htm', '120-6 What Happens During a Fair Hearing'),
    ('100_General_Provisions/120-8_Fair_Hearing_Decisions.htm', '120-8 Fair Hearing Decisions'),
    ('100_General_Provisions/120-9_How_to_Appeal_A_Decision.htm', '120-9 What Records Are Kept of Hearing Decisions and Who Can See Them'),
    ('100_General_Provisions/130_HIPAA_(Health_Insurance_Portability_and_Accountability_Act_of_1996).htm', '130 HIPAA (Health Insurance Portability and Accountability Act of 1996)'),
    ('200_Program_Standards/200_Program_Standards.htm', '200 Program Standards'),
    ('200_Program_Standards/201_Medicaid_Eligibility.htm', '201 Medicaid Eligibility'),
    ('200_Program_Standards/201-1_Screening_for_Medicaid_Eligibility.htm', '201-1 Screening for Medicaid Eligibility'),
    ('200_Program_Standards/202_Citizenship_and_Non-Citizen_Status_Requirements.htm', '202 Citizenship and Non-Citizen Status Requirements'),
    ('200_Program_Standards/202-1_U.S._Citizens.htm', '202-1 U.S. Citizens'),
    ('200_Program_Standards/202-2_Qulaified_Non-Citizen.htm', '202-2 Qualified Non-Citizen'),
    ('200_Program_Standards/202-2.1_Lawfully_Present_Children.htm', '202-2.1 Lawfully Present Children'),
    ('200_Program_Standards/202-3_Verification_of_Non-Citizen_Status.htm', '202-3 Verification of Non-Citizen Status'),
    ('200_Program_Standards/202-4_Sponsored_Non-Citizens.htm', '202-4 Sponsored Non-Citizens'),
    ('200_Program_Standards/203_Utah_Residence.htm', '203 Utah Residence'),
    ('200_Program_Standards/203-1_Determining_Residency.htm', '203-1 Determining Residency'),
    ('200_Program_Standards/203-2_Who_is_Capable_of_Expressing_Intent_.htm', '203-2 Who is Capable of Expressing Intent?'),
    ('200_Program_Standards/203-4_Determining_Residency_for_Individuals_Under_21.htm', '203-4 Determining Residency for Individuals Under 21'),
    ('200_Program_Standards/203-5_Factors_Indicating_No_Intent_to_Reside_in_Utah.htm', '203-5 Factors Indicating No Intent to Reside in Utah'),
    ('200_Program_Standards/203-6_Moving_From_State_to_State.htm', '203-6 Moving From State to State'),
    ('200_Program_Standards/204_Residents_of_Institutions.htm', '204 Residents of Institutions'),
    ('200_Program_Standards/204-1_What_is_an_Institution_.htm', '204-1 What is an Institution?'),
    ('200_Program_Standards/204-2_What_is_a_Public_Non-Medical_Institution_.htm', '204-2 What is a Public Non-Medical Institution?'),
    ('200_Program_Standards/204-3_Who_is_a_Resident_of_a_Household_.htm', '204-3 Who is a “Resident” of a Household?'),
    ('200_Program_Standards/204-4_Who_is_a_Resident_of_an_Institution_.htm', '204-4 Who is a “Resident” of an Institution?'),
    ('200_Program_Standards/210_Age_of_a_Child.htm', '210 Age of a Child'),
    ('200_Program_Standards/211_Social_Security_Numbers_(SSN).htm', '211 Social Security Numbers (SSN)'),
    ('200_Program_Standards/211-1_Verifying_Social_Security_Numbers.htm', '211-1 Verifying Social Security Numbers'),
    ('200_Program_Standards/211-2_Applying_for_a_Social_Security_Number.htm', '211-2 Applying for a Social Security Number'),
    ('200_Program_Standards/211-3_Who_Does_Not_Have_to_Provide_a_Social_Security_Number.htm', '211-3 Who Does Not Have to Provide a Social Security Number'),
    ('200_Program_Standards/211-4_Good_Cause_for_Not_Applying_For_the_SSN_Card.htm', '211-4 Good Cause for Not Applying For the SSN Card'),
    ('200_Program_Standards/215_Relationship.htm', '215 Relationship'),
    ('200_Program_Standards/215-1_Parent.htm', '215-1 Parent'),
    ('200_Program_Standards/215-3_When_Unrelated_Adults_Live_in_the_Home..htm', '215-3 When Unrelated Adults Live in the Home.'),
    ('200_Program_Standards/220_Health_Insurance_Coverage.htm', '220 Health Insurance'),
    ('200_Program_Standards/220-1_Definitions.htm', '220-1 Definitions'),
    ('200_Program_Standards/220-2_Coverage_Under_a_Health_Insurance_Plan.htm', '220-2 Coverage Under a Health Insurance Plan'),
    ('200_Program_Standards/220-3_Coverage_Only_Under_a_Limited_Coverage_Plan.htm', '220-3 Coverage Only Under a Limited Coverage Plan'),
    ('200_Program_Standards/220-4_Access_to_Employer-Sponsored_Health_Insurance.htm', '220-4 Access to Employer-Sponsored Health Insurance'),
    ('200_Program_Standards/220-5_Health_Insurance_Coverage_through_a_Non-Custodial_Parent.htm', '220-5 Health Insurance Coverage through a Non-Custodial Parent'),
    ('200_Program_Standards/220-6_Coverage_or_Access_to_Coverage_Under_a_State_Employees_Group_Health_Plan.htm', '220-6 Coverage or Access to Coverage Under a State Employee’s Group Health Plan'),
    ('200_Program_Standards/220-7_Coverage_Under_Indian_Health_Services.htm', '220-7 Coverage Under Indian Health Services'),
    ('200_Program_Standards/220-8_Termination_of_Health_Insurance_Coverage.htm', '220-8 Termination of Health Insurance Coverage'),
    ('200_Program_Standards/220-9_Coordination_With_the_Federally_Facilitated_Marketplace_(FFM).htm', '220-9 Coordination With the Federally Facilitated Marketplace (FFM)'),
    ('200_Program_Standards/222_Pregnancy_and_Postpartum.htm', '222 Pregnancy and Postpartum'),
    ('200_Program_Standards/222-1_Deemed_Newborn.htm', '222-1 Deemed Newborn'),
    ('200_Program_Standards/245_Child_Support_Services.htm', '245 Child Support Services'),
    ('400_Income_Standards_and_Household_Composition/400_Income_Standards_and_Household_Composition.htm', '400 Income Standards and Household Composition'),
    ('400_Income_Standards_and_Household_Composition/400-1_Joint_Custody_and_Temporary_Absence.htm', '400-1 Joint Custody and Temporary Absence'),
    ('400_Income_Standards_and_Household_Composition/401_MAGI_Household_Composition.htm', '401 MAGI Household Composition'),
    ('400_Income_Standards_and_Household_Composition/401-1_The_MAGI_Household.htm', '401-1 The MAGI Household'),
    ('400_Income_Standards_and_Household_Composition/401-2_Tax_Filer_s_MAGI_Household.htm', "401-2 Tax Filer's MAGI Household"),
    ('400_Income_Standards_and_Household_Composition/401-3_Non-Tax_Filer’s_MAGI_Household.htm', '401-3 Non-Tax Filer’s MAGI Household'),
    ('400_Income_Standards_and_Household_Composition/413_Introduction_to_Types_of_Income.htm', '413 Introduction to Types of Income'),
    ('400_Income_Standards_and_Household_Composition/413-1_What_is_Income_.htm', '413-1 What is Income?'),
    ('400_Income_Standards_and_Household_Composition/413-4_Ownership_of_Income.htm', '413-4 Ownership of Income'),
    ('400_Income_Standards_and_Household_Composition/413-5_Deposits_to_Joint_Checking_and__or_Savings_Accounts.htm', '413-5 Deposits to Joint Checking and/ or Savings Accounts'),
    ('400_Income_Standards_and_Household_Composition/413-6_What_is_Not_Income_.htm', '413-6 What is Not Income?'),
    ('400_Income_Standards_and_Household_Composition/415_Unearned_Income.htm', '415 Unearned Income'),
    ('400_Income_Standards_and_Household_Composition/415-1_Examples_of_Unearned_Income.htm', '415-1 Examples of Unearned Income'),
    ('400_Income_Standards_and_Household_Composition/415-2_Veterans_Administration_Benefits.htm', '415-2 Veterans Administration Benefits'),
    ('400_Income_Standards_and_Household_Composition/415-3_When_the_Entitlement_Amount_Differs_from_the_Payment_Amount.htm', '415-3 When the Entitlement Amount Differs from the Payment Amount'),
    ('400_Income_Standards_and_Household_Composition/415-4_Income_from_Rental_Property.htm', '415-4 Income from Rental Property'),
    ('400_Income_Standards_and_Household_Composition/415-5_Child_Support_Payments.htm', '415-5 Child Support Payments'),
    ('400_Income_Standards_and_Household_Composition/415-6_Educational_Assistance.htm', '415-6 Educational Assistance'),
    ('400_Income_Standards_and_Household_Composition/415-7_Certain_Interest_or_Dividend_Income,_Irregular_and_Infrequent_Income.htm', '415-7 Certain Interest or Dividend Income, Irregular and Infrequent Income'),
    ('400_Income_Standards_and_Household_Composition/415-8_Sales_Contracts.htm', '415-8 Sales Contracts'),
    ('400_Income_Standards_and_Household_Composition/415-9_Payments_to_Replace_or_Repair_Lost,_Stolen,_or_Damaged_Property.htm', '415-9 Payments to Replace or Repair Lost, Stolen, or Damaged Property'),
    ('400_Income_Standards_and_Household_Composition/415-12_Personal_Injury_and_TPL_Settlements.htm', '415-12 Personal Injury and TPL Settlements'),
    ('400_Income_Standards_and_Household_Composition/415-13_Countable_Payments_to_American_Indians_Alaska_Natives.htm', '415-13 Countable Payments to American Indians/Alaska Natives'),
    ('400_Income_Standards_and_Household_Composition/417_Unearned_Income_Exclusions.htm', '417 Unearned Income Exclusions'),
    ('400_Income_Standards_and_Household_Composition/417-1_Rental_Subsidies_and_Relocation_Assistance.htm', '417-1 Rental Subsidies and Relocation Assistance'),
    ('400_Income_Standards_and_Household_Composition/417-2_Trust_Funds.htm', '417-2 Trust Funds'),
    ('400_Income_Standards_and_Household_Composition/417-3_Tax_Refunds_and_Tax_Credits.htm', '417-3 Tax Refunds and Tax Credits'),
    ('400_Income_Standards_and_Household_Composition/417-4_Transportation_Tickets_for_Domestic_Travel.htm', '417-4 Transportation Tickets for Domestic Travel'),
    ('400_Income_Standards_and_Household_Composition/417-6_Death_Benefits.htm', '417-6 Death Benefits'),
    ('400_Income_Standards_and_Household_Composition/417-7_Credit_Life_and_Credit_Disability_Insurance_Benefits.htm', '417-7 Credit Life and Credit Disability Insurance Benefits'),
    ('400_Income_Standards_and_Household_Composition/417-8_Payments_under_the_National_Flood_Insurance_Program.htm', '417-8 Payments under the National Flood Insurance Program'),
    ('400_Income_Standards_and_Household_Composition/417-9_Payments_for_Clinical_Trial_Participation.htm', '417-9 Payments for Clinical Trial Participation'),
    ('400_Income_Standards_and_Household_Composition/417-10_Income_Excluded_Under_a_PASS_Plan.htm', '417-10 Income Excluded Under a PASS Plan'),
    ('400_Income_Standards_and_Household_Composition/417-11_Home_Produce_for_Consumption.htm', '417-11 Home Produce for Consumption'),
    ('400_Income_Standards_and_Household_Composition/417-12_Proceeds_from_a_Bona_Fide_Loan.htm', '417-12 Proceeds from a Bona Fide Loan'),
    ('400_Income_Standards_and_Household_Composition/417-14_Payments_to_American_Indians_Alaska_Natives.htm', '417-14 Payments to American Indians/Alaska Natives'),
    ('400_Income_Standards_and_Household_Composition/417-15_Gifts_Made_to_a_Child_with_a_Life-Threatening_Disease_by_Non-profit_Organizations.htm', '417-15 Gifts Made to a Child with a Life-Threatening Disease by Non-profit Organizations'),
    ('400_Income_Standards_and_Household_Composition/417-16_Income_from_Assets.htm', '417-16 Income from Assets'),
    ('400_Income_Standards_and_Household_Composition/417-17_Public_Assistance_Exclusions.htm', '417-17 Public Assistance Exclusions'),
    ('400_Income_Standards_and_Household_Composition/417-18_Employment_and_Volunteer_Program_Payments.htm', '417-18 Employment and Volunteer Program Payments'),
    ('400_Income_Standards_and_Household_Composition/417-19_Reparations_Payments.htm', '417-19 Reparations Payments'),
    ('400_Income_Standards_and_Household_Composition/417-20_Settlements_Disaster_Relief_Payments.htm', '417-20 Settlements/Disaster Relief Payments'),
    ('400_Income_Standards_and_Household_Composition/417-21_COVID_19_Recovery_Rebate_Payments.htm', '417-21 COVID 19 Recovery Rebate Payments'),
    ('400_Income_Standards_and_Household_Composition/419_Earned_Income.htm', '419 Earned Income'),
    ('400_Income_Standards_and_Household_Composition/419-1_Sources_of_Earned_Income.htm', '419-1 Sources of Earned Income'),
    ('400_Income_Standards_and_Household_Composition/419-2_Income_Received_from_a_Business.htm', '419-2 Income Received from a Business'),
    ('400_Income_Standards_and_Household_Composition/419-3_Self-Employment_Income.htm', '419-3 Self-Employment Income'),
    ('400_Income_Standards_and_Household_Composition/419-4_Self-Employment_Expenses.htm', '419-4 Self-Employment Expenses'),
    ('400_Income_Standards_and_Household_Composition/419-5_Earned_Income_Exclusions.htm', '419-5 Earned Income Exclusions'),
    ('400_Income_Standards_and_Household_Composition/421_Lump_Sum_Payments.htm', '421 Lump Sum Payments'),
    ('400_Income_Standards_and_Household_Composition/425-2_Deeming_from_a_Non-Citizen’s_Sponsor.htm', '425-2 Deeming from a Non-Citizen’s Sponsor'),
    ('400_Income_Standards_and_Household_Composition/435_Budgeting_Income.htm', '435 Budgeting Income'),
    ('400_Income_Standards_and_Household_Composition/435-1_Definitions.htm', '435-1 Definitions'),
    ('400_Income_Standards_and_Household_Composition/435-2_Determine_a_Best_Estimate_of_Income.htm', '435-2 Determine a Best Estimate of Income'),
    ('400_Income_Standards_and_Household_Composition/440_Determine_Countable_Income.htm', '440 Determine Countable Income'),
    ('400_Income_Standards_and_Household_Composition/440-1_MAGI_Methodology_General_Rules.htm', '440-1 MAGI Methodology General Rules'),
    ('400_Income_Standards_and_Household_Composition/440-2_MAGI-Based_Income_Requirements.htm', '440-2 MAGI-Based Income Requirements'),
    ('400_Income_Standards_and_Household_Composition/440-3_Income_for_MAGI_Methodology.htm', '440-3 Income for MAGI Methodology'),
    ('400_Income_Standards_and_Household_Composition/440-4_Specific_Treatment_of_Income_for_MAGI-Based_Programs.htm', '440-4 Specific Treatment of Income for MAGI-Based Programs'),
    ('400_Income_Standards_and_Household_Composition/440-5_Calculating_Income_for_MAGI-Based_Programs.htm', '440-5 Calculating Income for MAGI-Based Programs'),
    ('400_Income_Standards_and_Household_Composition/440-6_Whose_Income_Counts_for_MAGI_Household_.htm', '440-6 Whose Income Counts for MAGI Household?'),
    ('600_Program_Benefits/600_Program_Benefits.htm', '600 Program Benefits'),
    ('600_Program_Benefits/601_Health_Plan_Selections_and_Education.htm', '601 Health Plan Selection and Education'),
    ('600_Program_Benefits/602_Cost_Sharing_Requirements.htm', '602 Cost Sharing Requirements'),
    ('600_Program_Benefits/603_CHIP_Member_ID_Cards.htm', '603 CHIP Member ID Cards'),
    ('600_Program_Benefits/604_Suspension_of_Benefits.htm', '604 Suspension of Benefits'),
    ('700_Eligibility_Determination_and_Redetermination/700_Eligibility_Determination_and_Redetermination.htm', '700 Eligibility Determination and Redetermination'),
    ('700_Eligibility_Determination_and_Redetermination/701_Application.htm', '701 Application'),
    ('700_Eligibility_Determination_and_Redetermination/701-1_What_is_an_Application_.htm', '701-1 What is an Application?'),
    ('700_Eligibility_Determination_and_Redetermination/701-2_Date_of_Application.htm', '701-2 Date of Application'),
    ('700_Eligibility_Determination_and_Redetermination/701-3_Effective_Dates_of_Certification.htm', '701-3 Effective Dates of Certification'),
    ('700_Eligibility_Determination_and_Redetermination/701-4_What_to_do_with_an_Application.htm', '701-4 What to do with an Application'),
    ('700_Eligibility_Determination_and_Redetermination/701-5_Eligibility_Decisions.htm', '701-5 Eligibility Decisions'),
    ('700_Eligibility_Determination_and_Redetermination/701-6_Incarcerated_Individuals_in_Jail_or_Prison.htm', '701-6 Incarcerated Individuals in Jail or Prison'),
    ('700_Eligibility_Determination_and_Redetermination/702_Re-Opening_CHIP.htm', '702 Re-Opening CHIP'),
    ('700_Eligibility_Determination_and_Redetermination/702-1_Transitions_Between_CHIP,_UPP_and_Medicaid.htm', '702-1 Transitions Between CHIP, UPP and Medicaid'),
    ('700_Eligibility_Determination_and_Redetermination/703_Certification_Period.htm', '703 Certification Period'),
    ('700_Eligibility_Determination_and_Redetermination/703-1_Length_of_the_Certification_Period.htm', '703-1 Length of the Certification Period'),
    ('700_Eligibility_Determination_and_Redetermination/704_Eligibility_Review.htm', '704 Eligibility Review'),
    ('700_Eligibility_Determination_and_Redetermination/704-1_Ex_Parte_Reviews_(Reviews_Not_requiring_Member_Participation).htm', '704-1 Ex Parte Reviews (Reviews Not requiring Member Participation)'),
    ('700_Eligibility_Determination_and_Redetermination/704-2_Reviews_Requiring_Member_Participation.htm', '704-2 Reviews Requiring Member Participation'),
    ('700_Eligibility_Determination_and_Redetermination/705_Verification.htm', '705 Verification'),
    ('700_Eligibility_Determination_and_Redetermination/705-2_What_is_Acceptable_Verification_.htm', '705-2 What is Acceptable Verification'),
    ('700_Eligibility_Determination_and_Redetermination/705-4_Verification_from_Collateral_Contacts.htm', '705-4 Verification from Collateral Contacts'),
    ('700_Eligibility_Determination_and_Redetermination/705-6_Verification_of_SSA_Benefits.htm', '705-6 Verification of SSA Benefits'),
    ('700_Eligibility_Determination_and_Redetermination/706_Income_Match.htm', '706 Income Match'),
    ('700_Eligibility_Determination_and_Redetermination/706-1_Sources_of_IEVS_Data.htm', '706-1 Sources of IEVS Data'),
    ('700_Eligibility_Determination_and_Redetermination/706-2_Special_Rules_for_Income_Matches_When_Enrollees_Apply.htm', '706-2 Special Rules for Income Matches When Enrollees Apply'),
    ('700_Eligibility_Determination_and_Redetermination/706-3_What_to_Do_With_Match_Reports.htm', '706-3 What to Do With Match Reports'),
    ('700_Eligibility_Determination_and_Redetermination/706-4_Taking_Actions_on_Responses.htm', '706-4 Taking Actions on Responses'),
    ('700_Eligibility_Determination_and_Redetermination/706-5_What_To_Do_With_An_Ineligible_Case.htm', '706-5 What To Do With An Ineligible Case'),
    ('700_Eligibility_Determination_and_Redetermination/706-6_Special_Rule_for_the_IRS_Match.htm', '706-6 Special Rule for the IRS Match'),
    ('800_Records_and_Case_Management/800_Records_and_Case_Management.htm', '800 Records and Case Management'),
    ('800_Records_and_Case_Management/801_Case_Records.htm', '801 Case Records'),
    ('800_Records_and_Case_Management/801-1_Creating_and_Maintaining_Case_Records.htm', '801-1 Creating and Maintaining Case Records'),
    ('800_Records_and_Case_Management/801-2_Removing_Old_Material_From_the_Case_Record.htm', '801-2 Removing Old Material From the Case Record'),
    ('800_Records_and_Case_Management/802_Case_Numbers_and_Member_Identification_Numbers.htm', '802 Case Numbers and Member Identification Numbers'),
    ('800_Records_and_Case_Management/803_Notification.htm', '803 Notification'),
    ('800_Records_and_Case_Management/803-2_Returned_Mail.htm', '803-2 Returned Mail'),
    ('800_Records_and_Case_Management/804_Changes.htm', '804 Changes'),
    ('800_Records_and_Case_Management/804-1_Change_of_Address.htm', '804-1 Change of Address'),
    ('800_Records_and_Case_Management/804-2_Change_in_Access_to_Health_Insurance.htm', '804-2 Change in Access to Health Insurance'),
    ('800_Records_and_Case_Management/804-3_Adding_Eligible_Children_to_Open_CHIP_Cases.htm', '804-3 Adding Eligible Children to Open CHIP Cases'),
    ('800_Records_and_Case_Management/804-4_Removing_Children_From_CHIP.htm', '804-4 Removing Children From CHIP'),
    ('800_Records_and_Case_Management/804-5_Income_Changes.htm', '804-5 Income Changes'),
    ('800_Records_and_Case_Management/805_Case_Closure.htm', '805 Case Closure'),
    ('800_Records_and_Case_Management/806_Improper_CHIP_Coverage.htm', '806 Improper CHIP Coverage'),
    ('800_Records_and_Case_Management/806-1_Causes_of_Improper_CHIP_Coverage.htm', '806-1 Causes of Improper CHIP Coverage'),
    ('800_Records_and_Case_Management/806-2_What_to_do_When_Improper_CHIP_Coverage_Occurs.htm', '806-2 What to do When Improper CHIP Coverage Occurs'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1000_State_Children_s_Health_Insurance_Program_(CHIP).htm', "1000 State Children's Health Insurance Program (CHIP)"),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1200_Program_Standards.htm', '1200 Program Standards'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1202_Citizenship_Status_Requirements.htm', '1202 Citizenship Status Requirements'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1203_Utah_Residence.htm', '1203 Utah Residence'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1203-1_Verification_of_Utah_Residence.htm', '1203-1 Verification of Utah Residence'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1211_Social_Security_Numbers.htm', '1211 Social Security Numbers'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1230_Employment_Requirement.htm', '1230 Employment Requirement'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1250_Open_Enrollment_Periods.htm', '1250 Open Enrollment Periods'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1700_Eligibility_Determination_and_Redetermination.htm', '1700 Eligibility Determination and Redetermination'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1701_Application.htm', '1701 Application'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1701-1_What_is_an_Application_.htm', '1701-1 What is an Application?'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1701-2_Date_of_Application.htm', '1701-2 Date of Application'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1701-3_Effective_Dates_of_Certification.htm', '1701-3 Effective Dates of Certification'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1701-4_What_to_do_with_an_Application.htm', '1701-4 What to do with an Application'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1702_Re-Opening_State_CHIP.htm', '1702 Re-Opening State CHIP'),
    ('1000_State_Children_s_Health_Insurance_Program_(CHIP)/1702-1_Transitions_Between_State_CHIP_and_UPP.htm', '1702-1 Transitions Between State CHIP and UPP'),
    ('Tables/Table_I_-_Income_Limits.htm', 'Table I - Income Limits'),
    ('Tables/Table_I-A_-_5__Federal_Poverty_Level_Deduction_Amount.htm', 'Table I-A - 5% Federal Poverty Level Deduction Amount'),
    ('Tables/Table_I-B_-_State_CHIP_Maximum_Out_of_Pocket.htm', 'Table I-B - State CHIP Maximum Out of Pocket'),
    ('Tables/TABLE_III_-_172_Hour_Rule.htm', 'TABLE III - 172 Hour Rule'),
    ('Tables/TABLE_IV_-_Proof_of_U.S._Citizenship_and_Identification.htm', 'TABLE IV - Proof of U.S. Citizenship and Identification'),
    ('Tables/Table_V_-_Telephone_Numbers.htm', 'Table V - Telephone Numbers'),
    ('Tables/Table_VI_-_Verification_and_Interface_Match.htm', 'Table VI - Verification and Interface Match'),
    ('Tables/Table_VII_-_Approved_Halfway_Houses.htm', 'Table VII - Approved Halfway Houses'),
    ('Tables/Table_VII-A.htm', 'Table VII-A Participating Facilities and Organizations for Pre-Release Services'),
    ('Tables/Table_VII-B_Facilities_Reporting_Data_to_CCJJ.htm', 'Table VII-B Facilities Reporting Data to CCJJ'),
    ('Tables/Table_VIII__Data_Retention.htm', 'Table VIII Data Retention'),
)

AK_MAGI_TOPICS: tuple[tuple[str, str], ...] = (
    ('magi_medicaid_eligibility_manual/magi_medicaid_eligibility_manual.htm', 'MAGI Medicaid Eligibility Manual'),
    ('800_introduction_to_medicaid/800_introduction_to_medicaid.htm', '800 Introduction to Medicaid'),
    ('800_introduction_to_medicaid/800-1_purpose.htm', '800-1 Purpose'),
    ('801_general_medicaid_provisions/a._freedom_of_choice_provisions.htm', '801 General Medicaid Provisions'),
    ('802_notices/802_notice_of_decision_required.htm', '802 Notices'),
    ('802_notices/802-1_adequate_notice.htm', '802-1 Adequate Notice'),
    ('802_notices/802-2_timely_notice_requirement.htm', '802-2 Timely Notice Requirement'),
    ('802_notices/802-3_other_notice_requirements.htm', '802-3 Other Notice Requirements'),
    ('803_fraud/a._eligibility_technician_responsibilities.htm', '803 Fraud'),
    ('804_right_to_fair_hearing/804_right_to_fair_hearing.htm', '804 Right to Fair Hearing'),
    ('805_medicaid_recipient_id_card/805_medicaid_recipient_id_card.htm', '805 Medicaid Recipient ID Card'),
    ('806_application_and_renewal_process/application_and_renewal_process.htm', '806 Application and Renewal Process'),
    ('806_application_and_renewal_process/806-1_the_application.htm', '806-1 The Application'),
    ('806_application_and_renewal_process/806-2_actions_taken_on_the_application.htm', '806-2 Actions Taken on the Application'),
    ('806_application_and_renewal_process/renewal_requirements.htm', '806- 3 Renewal Requirements'),
    ('807_non_financial_factors_of_eligibility/807_non-financial_factors.htm', '807 Non Financial Factors of Eligibility'),
    ('808_us_citizenship_and_eligible_alien_status/808_us_citizenship_and_eligibile_alien_status.htm', '808 US Citizenship and Eligible Alien Status'),
    ('809_alaska_residency/809_alaska_residency.htm', '809 Alaska Residency'),
    ('810_social_security_enumeration/810_social_security_enumeration.htm', '810 Social Security Enumeration'),
    ('811_assignment_of_rights/811_assignment_of_rights.htm', '811 Assignment of Rights'),
    ('812_medical_support_assignment/812_medical_support_assignment.htm', '812 Medical Support Assignment'),
    ('813_development_of_income/development_of_income.htm', '813 Development of Income'),
    ('814_tpl_and_recovery/814_tpl_and_recovery.htm', '814 TPL and Recovery'),
    ('815_residents_of_institutions/815_residents_of_institutions.htm', '815 Residents of Institutions'),
    ('816_magi_medicaid_categories/806_magi_medicaid_categories.htm', '816 MAGI Medicaid Categories'),
    ('817_determining_magi_medicaid_household/817_magi_medicaid_household_composition.htm', '817 Determining MAGI Medicaid Household'),
    ('818_magi_medicaid_income/818_magi_medicaid_income.htm', '818 MAGI Medicaid Income'),
    ('819_types_of_income/819_types_of_income.htm', '819 Types of Income'),
    ('820_budgeting_income/820_budgeting_income.htm', '820 Budgeting Income'),
    ('821_budgeting_self-employment_income/821_budgeting_self-employment_income.htm', '821 Budgeting Self-Employment Income'),
    ('822_resources/822_resources.htm', '822 Resources'),
    ('823_verification_and_documentation/823_verification_and_documentation.htm', '823 Verification and Documentation'),
    ('824_magi_medicaid_change_reporting_requirements/824_magi_medicaid_change_reporting_requirements.htm', '824 MAGI Medicaid Change Reporting Requirements'),
    ('825_coordination_with_the_federally_facilitated_marketplace/825_coordination_with_the_federally_facilitated_marketplace.htm', '825 Coordination With the Federally Facilitated Marketplace'),
    ('826_home_and_community_based_waiver_services/826_home_and_community_based_waiver_services.htm', '826 Home and Community Based Waiver Services'),
    ('827_retroactive_medicaid/825_retroactive_medicaid.htm', '827 Retroactive Medicaid'),
    ('828_transitional_medicaid/828_transitional_medicaid.htm', '828 Transitional Medicaid'),
    ('829_title_iv-e_foster_care_and_adoption_assistance/829_title_iv-e_foster_care_and_adoption_assistance.htm', '829 Title IV-E Foster Care and Adoption Assistance'),
    ('830_eligibility_under_adoption_assistance/830_eligibility_under_adoption_assistance.htm', '830 Eligibility Under Adoption Assistance'),
    ('831_emergency_treatment_for_aliens/831_emergency_treatment_for_aliens.htm', '831 Emergency Treatment for Aliens'),
    ('832_post_medicaid_increased_spousal_support/832_post_medicaid_increased_spousal_support.htm', '832 Post Medicaid Increased Spousal Support'),
    ('833_hospital_presumptive_eligibility/833_hosptial_presumptive_eligibility_determination.htm', '833 Hospital Presumptive Eligibility'),
    ('808_us_citizenship_and_eligible_alien_status/808-1_united_states_citizens_and_nationals.htm', '808-1 United States Citizens and Nationals'),
    ('808_us_citizenship_and_eligible_alien_status/808-2_qualified_aliens.htm', '808-2 Qualified Aliens'),
    ('808_us_citizenship_and_eligible_alien_status/808-3_native_americans_born_outside_the_united_states.htm', '808-3 Native Americans Born Outside the United States'),
    ('808_us_citizenship_and_eligible_alien_status/808-4_five_year_waiting_period.htm', '808-4 Five Year Waiting Period'),
    ('808_us_citizenship_and_eligible_alien_status/808-5_non_qualified_aliens.htm', '808-5 Non Qualified Aliens'),
    ('808_us_citizenship_and_eligible_alien_status/808-6_proof_of_united_states_citizenship_and_qualified_alien_status.htm', '808-6 Proof of United States Citizenship and Qualified Alien Status'),
    ('808_us_citizenship_and_eligible_alien_status/808-7_reasonable_opportunity_period.htm', '808-7 Reasonable Opportunity Period'),
    ('812_medical_support_assignment/812-1_informing_about_medical_support_orders.htm', '812-1 Informing About Medical Support Orders'),
    ('812_medical_support_assignment/812-2_assignment_of_medical_support_rights.htm', '812-2 Assignment of Medical Support Rights'),
    ('812_medical_support_assignment/812-3_how_a_caretaker_cooperates_with_cssd.htm', '812-3 How a Caretaker Cooperates with CSSD'),
    ('812_medical_support_assignment/812-4_failure_to_cooperate_with_cssd.htm', '812-4 Failure to Cooperate With CSSD'),
    ('812_medical_support_assignment/812-5_procedures_for_exchanging_info.htm', '812-5 Procedures For Exchanging Info'),
    ('815_residents_of_institutions/815-1_children_living_in_residential_treatment_centers_over_30_days.htm', '815-1 Hospitalized Children Receiving Treatment Over 30 Days'),
    ('816_magi_medicaid_categories/816-1_magi_category_eligibility_factors.htm', '816-1 MAGI Medicaid Category Eligibility Factors'),
    ('817_determining_magi_medicaid_household/817-1_construct_a_magi_household_for_each_applicant.htm', '817-1 Construct a MAGI Household for Each Applicant'),
    ('817_determining_magi_medicaid_household/817-2_examples_of_income_counting_for_magi_medicaid_household_compositions.htm', '817-2 Examples of Income Counting for MAGI Medicaid Household Compositions'),
    ('820_budgeting_income/820-1_estimation_the_household_s_monthly_income.htm', "820-1 Estimation The Household's Monthly Income"),
    ('820_budgeting_income/820-2_calculating_a_monthly_income_amount.htm', '820-2 Calculating a Monthly Income Amount'),
    ('820_budgeting_income/820-3_full_month_s_income.htm', "820-3 Full Month's Income"),
    ('820_budgeting_income/820-4_not_a_full_month_s_income.htm', "820-4 Not a Full Month's Income"),
    ('820_budgeting_income/820-5_irregular_income.htm', '820-5 Irregular Income'),
    ('820_budgeting_income/820-6_specialized_budgeting.htm', '820-6 Specialized Budgeting'),
)

ND_ACA_TOPICS: tuple[tuple[str, str], ...] = (
    ('510-03-05.htm', 'Definitions 510-03-05'),
    ('510-03-07-05.htm', 'General Statement 510-03-07-05'),
    ('510-03-07-10.htm', 'Purpose and Objective 510-03-07-10'),
    ('510-03-10-05.htm', 'General Information 510-03-10-05'),
    ('510-03-10-10.htm', 'Nondiscrimination in Federally Assisted Programs 510-03-10-10'),
    ('510-03-10-15.htm', 'Confidentiality 510-03-10-15'),
    ('510-03-10-20.htm', 'Assignment of Rights to Recover Medical Costs 510-03-10-20'),
    ('510-03-10-25.htm', 'Suspected Fraud 510-03-10-25'),
    ('510-03-10-30.htm', 'Liens and Recoveries 510-03-10-30'),
    ('510-03-100-05.htm', 'Family Planning Program 510-03-100-05'),
    ('510-03-100-10.htm', 'WIC Program 510-03-100-10'),
    ('510-03-100-15.htm', 'DN 143, "Your Civil Rights Brochure" 510-03-100-15'),
    ('510-03-100-20.htm', 'DN 555, "Medicaid Program Brochure" 510-03-100-20'),
    ('510-03-100-25.htm', 'DN 538, "ND Health Tracks" 510-03-100-25'),
    ('510-03-100-30.htm', 'SFN 20, “Surveillance & Utilization Review Section (SURS) Referral” 510-03-100-30'),
    ('510-03-100-35.htm', 'SFN 162, Request for Hearing 510-03-100-35'),
    ('510-03-100-40.htm', 'SFN 443, "Notice of Right to Claim \'Good Cause\'" 510-03-100-40'),
    ('510-03-100-45.htm', 'SFN 446, "Request to Claim \'Good Cause" 510-03-100-45'),
    ('510-03-100-50.htm', 'SFN 451, "Eligibility Report on Disability/Incapacity" 510-03-100-50'),
    ('510-03-100-55.htm', 'SFN 560, "Assignment of Benefits" 510-03-100-55'),
    ('510-03-100-60.htm', 'SFN 566, “Medicaid Questionnaire and Assignment” 510-03-100-60'),
    ('510-03-100-65.htm', 'SFN 691, “Affidavit of Identity For Children” 510-03-100-65'),
    ('510-03-100-70.htm', 'SFN 706, "Affidavit of Explanation why Citizenship Cannot be Supplied” 510-03-100-70'),
    ('510-03-100-75.htm', 'SFN 707, "Citizen Affidavit’ 510-03-100-75'),
    ('510-03-100-80.htm', 'SFN 817, "Health Insurance Cost-Effectiveness Review" 510-03-100-80'),
    ('510-03-100-85.htm', 'SFN 828, “Credit Form” 510-03-100-85'),
    ('510-03-100-90.htm', 'SFN 1598, “Medically Frail Questionnaire” 510-03-100-90'),
    ('510-03-105-05.htm', 'Coverage Hierarchy Order 510-03-105-05'),
    ('510-03-105-10.htm', 'Medicaid Living Arrangement Reference Hard Card 510-03-105-10'),
    ('510-03-105-15.htm', 'Lottery and Gambling Winnings Income Table 510-03-105-15'),
    ('510-03-110-20.htm', 'Medicaid Coverage for Inmates Residing in Corrections-related Supervised Community Residential Facilities 510-03-110-20'),
    ('510-03-12-05.htm', 'Cooperation - Third Party Liability 510-03-12-05'),
    ('510-03-12-10.htm', '"Good Cause" - Third Party Liability 510-03-12-10'),
    ('510-03-20-05.htm', 'General Information 510-03-20-05'),
    ('510-03-20-10.htm', 'Definitions (Cost Effective Health Insurance) 510-03-20-10'),
    ('510-03-20-15.htm', "Applicant's and Recipient's Responsibility 510-03-20-15"),
    ('510-03-20-20.htm', 'Cost-effectiveness Determination 510-03-20-20'),
    ('510-03-25-05.htm', 'Application and Review 510-03-25-05'),
    ('510-03-25-10.htm', 'Eligibility - Current and Retroactive 510-03-25-10'),
    ('510-03-25-15.htm', 'Duty to Establish Eligibility 510-03-25-15'),
    ('510-03-25-20.htm', 'Medicaid Brochures 510-03-25-20'),
    ('510-03-25-25.htm', 'Decision and Notice 510-03-25-25'),
    ('510-03-25-27.htm', 'Electronic Narratives 510-03-25-27'),
    ('510-03-25-30.htm', 'Appeals 510-03-25-30'),
    ('510-03-30-05.htm', 'Groups Covered Under ACA Medicaid 510-03-30-05'),
    ('510-03-30-10.htm', "Applicant's Choice of Category 510-03-30-10"),
    ('510-03-30-15.htm', 'Assigning Category of Eligibility 510-03-30-15'),
    ('510-03-35-05.htm', 'ACA Medicaid Household 510-03-35-05'),
    ('510-03-35-10.htm', 'Deprivation 510-03-35-10'),
    ('510-03-35-100.htm', 'Disability and Medically Frail 510-03-35-100'),
    ('510-03-35-105.htm', 'Incapacity of a Parent 510-03-35-105'),
    ('510-03-35-15.htm', 'Caretaker Relatives 510-03-35-15'),
    ('510-03-35-20.htm', 'Relative Responsibility 510-03-35-20'),
    ('510-03-35-35.htm', 'Need 510-03-35-35'),
    ('510-03-35-40.htm', 'Age and Identity 510-03-35-40'),
    ('510-03-35-45.htm', 'Citizenship and Immigration 510-03-35-45'),
    ('510-03-35-50.htm', 'American Indians Born in Canada 510-03-35-50'),
    ('510-03-35-55.htm', 'Ineligible Non- Citizens 510-03-35-55'),
    ('510-03-35-58.htm', 'Qualified Non- Citizens 510-03-35-58'),
    ('510-03-35-60.htm', 'Non-Citizens Lawfully Admitted for Permanent Residence before August 22, 1996 510-03-35-60'),
    ('510-03-35-65.htm', 'Non-Citizens Lawfully Admitted for Permanent Residence on or after August 22, 1996 510-03-35-65'),
    ('510-03-35-70.htm', 'Emergency Services for Non-Citizens 510-03-35-70'),
    ('510-03-35-80.htm', 'Social Security Numbers 510-03-35-80'),
    ('510-03-35-85.htm', 'State Residence 510-03-35-85'),
    ('510-03-35-90.htm', 'Application for Other Benefits 510-03-35-90'),
    ('510-03-35-95-05-05.htm', 'General Statement (Coverage for Inmates Receiving Inpatient Care in Certain Medical Institiutions) 510-03-35-95-05-05'),
    ('510-03-35-95-05-10.htm', 'Definitions for Coverage for Inmates Receiving Inpatient Care in Certain Medical Institutions 510-03-35-95-05-10'),
    ('510-03-35-95-05-15.htm', 'Individuals Covered (Coverage for Inmates Receiving Inpatient Care in Certain Medical Institutions) 510-03-35-95-05-15'),
    ('510-03-35-95-05-20.htm', 'Asset Considerations (Coverage for Inmates Receiving Inpatient Care in Certain Medical Institutions) 510-03-35-95-05-20'),
    ('510-03-35-95-05-25.htm', 'Income Considerations (Coverage for Inmates who are Inpatients in a Hospital Setting) 510-03-35-95-05-25'),
    ('510-03-35-95-05-30.htm', 'Income Levels (Coverage for Inmates who are Inpatients in a Hospital Setting) 510-03-35-95-05-30'),
    ('510-03-35-95-05-35.htm', 'Budgeting (Coverage for Inmates who are Inpatients in a Hospital Setting) 510-03-35-95-05-35'),
    ('510-03-35-95-10.htm', 'Coverage for Inmates Residing in Corrections-related Supervised Community Residential Facilities 510-03-35-95-10'),
    ('510-03-35-95-15.htm', 'Medicaid Eligibility for Incarcerated Individuals 510-03-35-95-15'),
    ('510-03-35-95.htm', 'Public Institutions 510-03-35-95'),
    ('510-03-35-97.htm', 'Institutions for Mental Disease (IMD) 510-03-35-97'),
    ('510-03-40-05.htm', 'Paternity 510-03-40-05'),
    ('510-03-40-10.htm', 'Medical Support 510-03-40-10'),
    ('510-03-40-15.htm', 'Cooperation - Child Support 510-03-40-15'),
    ('510-03-40-20.htm', '"Good Cause" - Child Support 510-03-40-20'),
    ('510-03-45-05.htm', 'Extended Medicaid for Pregnant Women and Newborns 510-03-45'),
    ('510-03-45-10.htm', 'Extended Medicaid for Children born to Pregnant Women 510-03-45-10'),
    ('510-03-50-05.htm', 'Transitional Medicaid Benefits 510-03-50-05'),
    ('510-03-50-10.htm', 'Extended Medicaid Benefits 510-03-50-10'),
    ('510-03-53-05.htm', 'General Statement 510-03-53-05'),
    ('510-03-53-10.htm', 'Individuals Covered 510-03-53-10'),
    ('510-03-53-15.htm', 'Continuous Eligibility Periods 510-03-53-15'),
    ('510-03-53-20.htm', 'Continuously Eligible Individuals Moving Out of the ACA Medicaid Household 510-03-53-20'),
    ('510-03-55-05.htm', 'Foster Care 510-03-55-05'),
    ('510-03-55-10.htm', 'Former Foster Care Children through Age 26 510-03-55-10-05'),
    ('510-03-55-15.htm', 'Volunteer Placement Program 510-03-55-15'),
    ('510-03-55-20.htm', 'Subsidized Guardianship Project 510-03-55-20'),
    ('510-03-60-05.htm', 'General Statement (Hospital Presumptive Eligibility (HPE) 510-03-60-05'),
    ('510-03-60-10.htm', 'Application and Review for Hospital Presumptive Eligibility (HPE) 510-03-60-10'),
    ('510-03-60-15.htm', 'Individuals Covered Under Hospital Presumptive Eligibility (HPE) 510-03-60-15'),
    ('510-03-60-20.htm', 'Eligibility Requirements for Hospital Presumptive Eligibility (HPE) 510-03-60-20'),
    ('510-03-60-25.htm', 'Budgeting for Individuals Applying for Hospital Presumptive Eligibility (HPE) 510-03-60-25'),
    ('510-03-60-30.htm', 'Hospital Presumptive Eligibility (HPE) Periods 510-03-60-30'),
    ('510-03-60-35.htm', 'Coverage under Hospital Presumptive Eligibility (HPE) 510-03-60-35'),
    ('510-03-60-40.htm', 'Three Months Prior Coverage Under Hospital Presumptive Eligibility (HPE) 510-03-60-40'),
    ('510-03-60-45.htm', 'Appealing a Hospital Presumptive Eligibility (HPE) Determination 510-03-60-45'),
    ('510-03-60-50.htm', 'Hospital Responsibility under Hospital Presumptive Eligibility (HPE) 510-03-60-50'),
    ('510-03-70-05.htm', 'General Information 510-03-70-05'),
    ('510-03-75-05.htm', 'Ownership in a Partnership or Corporation 510-03-75-05'),
    ('510-03-75-10.htm', 'Treatment of Conservation Reserve Program Property and Payments 510-03-75-10'),
    ('510-03-75-15.htm', 'Communal Colonies 510-03-75-15'),
    ('510-03-85-05.htm', 'Income Considerations 510-03-85-05'),
    ('510-03-85-10.htm', 'Determining Ownership of Income 510-03-85-10'),
    ('510-03-85-13.htm', 'ACA Income Methodologies 510-03-85-13'),
    ('510-03-85-15.htm', 'Countable Income 510-03-85-15'),
    ('510-03-85-20.htm', 'Income Conversion 510-03-85-20'),
    ('510-03-85-25.htm', 'Income Compatibility 510-03-85-25'),
    ('510-03-85-30.htm', 'Disregarded Income 510-03-85-30'),
    ('510-03-85-35.htm', 'Income Deductions 510-03-85-35'),
    ('510-03-85-40.htm', 'Income Levels 510-03-85-40'),
    ('510-03-90-05.htm', 'Definitions 510-03-90-05'),
    ('510-03-90-10.htm', '10-10-10 Rule 510-03-90-10'),
    ('510-03-90-15.htm', 'Guidelines for Anticipating Income 510-03-90-15'),
    ('510-03-90-17.htm', 'Client Share (Recipient Liability) 510-03-90-17'),
    ('510-03-90-20.htm', 'Computing Client Share (Recipient Liability) 510-03-90-20'),
    ('510-03-90-23.htm', 'Offset of Client Share (Recipient Liability) 510-03-90-23'),
    ('510-03-90-25.htm', 'Budgeting Procedures for Pregnant Women 510-03-90-25'),
    ('510-03-90-30.htm', 'Budgeting Procedures When Adding and Deleting Individuals 510-03-90-30'),
    ('510-03-90-45.htm', 'Budgeting Procedures for SSI Recipients 510-03-90-45'),
    ('510-03-90-50.htm', 'Budgeting Procedures for Medically Needy under ACA Medicaid 510-03-90-50'),
    ('510-03-90-55.htm', 'Budgeting Procedures for Continuous Eligibility for Children Under Age 19 510-03-90-55'),
    ('510-03-90-60.htm', 'Budgeting Procedures for Three Prior Months (THMP) 510-03-90-60'),
    ('510-03-90-65.htm', 'Action on Reported Changes 510-03-90-65'),
    ('510-03-95-05.htm', 'General Information 510-03-95-05'),
    ('510-03-95-20.htm', 'Refugee Medical Assistance Program 510-03-95-20'),
    ('510-03-95-40.htm', 'Special Health Services 510-03-95-40'),
    ('510-03-95-45.htm', 'Coordinated Services Program 510-03-95-45'),
    ('510-03-95-50.htm', 'North Dakota Health Tracks 510-03-95-50'),
)

CONFIRMED_BATCH4: dict[str, dict] = {
    "us-or": {
        "name": "Oregon",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_html",
        "index_url": "https://secure.sos.state.or.us/oard/displayDivisionRules.action?selectedDivision=1742",
        "index_document_count": 40,
        "index_families": {"oar_rule_in_division_200": 40},
        "primary_source_url": "https://secure.sos.state.or.us/oard/displayChapterRules.action?selectedChapter=87",
        "notes": (
            "Retried from a US network 2026-09-10T21:35Z: the oregon.gov zone resolves and the OARD answers "
            "(plain client HTTP 200; the chrome120 client receives only a 5 KB shell, so no impersonation). "
            "Batch 3's selectedChapter=94 was Oregon State Police; OAR chapter 410 (OHA Health Systems "
            "Division: Medical Assistance Programs) is selectedChapter=87 with 39 divisions, and Division 200 "
            "Eligibility for Health Systems Division Medical Programs (selectedDivision=1742) lists 40 rules "
            "410-200-0010 to 410-200-0521 with full text on one page (latest effective 2026-03-01). Oregon's "
            "CHIP is Medicaid-expansion OHP coverage under these rules. Taken 1: the division page, 40 "
            "labeled rule sections."
        ),
        "documents": [
            doc(
                "us-or", "or-oard-oar-410-division-200",
                "OAR Chapter 410 Division 200 Eligibility for Health Systems Division Medical Programs",
                "https://secure.sos.state.or.us/oard/displayDivisionRules.action?selectedDivision=1742",
                "us-or/regulation/chapter-410/division-200", "html", "2026-03-01",
                document_class="regulation",
                subtype="administrative_rule_division",
                authority="Oregon Health Authority, Health Systems Division (OAR 410), published by the Secretary of State Oregon Administrative Rules Database",
                extraction=OR_OAR_DIVISION_EXTRACTION,
                metadata={"legal_identifier": "OAR 410-200", "chapter_id": "87", "division_id": "1742",
                          "rule_count": 40, "discovered_via": BATCH4_DISCOVERED_VIA},
            )
        ],
    },
    "us-ne": {
        "name": "Nebraska",
        "document_class": "regulation",
        "source_kind": "official_filed_regulation_pdf",
        "index_url": "https://rules.nebraska.gov/api/chapter/GetByTitleId/232",
        "index_document_count": 29,
        "index_families": {"nac_477_chapter_pdf": 29},
        "primary_source_url": "https://rules.nebraska.gov/rules?agencyId=37&titleId=232",
        "notes": (
            "Retried from a US network 2026-09-10T21:35Z: dhhs.ne.gov answers (the old Medicaid-Regulations "
            "page is HTTP 404); rules.nebraska.gov (Secretary of State) answers HTTP 200 once the chain is "
            "completed with the committed DigiCert Global G2 intermediate via REQUESTS_CA_BUNDLE (TLS "
            "verification never disabled), and its chapter API (same mechanism as us-ne-snap-rules.yaml) lists "
            "Title 477 Medicaid Eligibility (titleId 232, agency 37): 29 chapters. Nebraska's CHIP (599 CHIP) is "
            "Medicaid-expansion coverage governed by 477 NAC 14-19 (MAGI-based programs). Taken 1: 477 NAC 19 "
            "Modified Adjusted Gross Income (MAGI)-Based Programs (effective 2020-07-29), 42 labeled sections. "
            "Not taken: chapters 14-18 (2018 filings using the older 15-004-style numbering) and the non-MAGI "
            "chapters."
        ),
        "documents": [
            doc(
                "us-ne", "ne-dhhs-title-477-chapter-19",
                "Nebraska Title 477 NAC Chapter 19: Modified Adjusted Gross Income (MAGI)-Based Programs",
                "https://rules.nebraska.gov/api/fileStorage/GetAsByteArray/chapter-pdfs/477%20NAC%2019%20%2807-29-2020%29.pdf",
                "us-ne/regulation/title-477/chapter-19", "pdf", "2020-07-29",
                document_class="regulation",
                subtype="official_filed_administrative_regulation_chapter",
                authority="Nebraska Department of Health and Human Services (477 NAC), filed with the Secretary of State",
                extraction=NE_477_EXTRACTION,
                metadata={"rules_landing_page": "https://rules.nebraska.gov/rules?agencyId=37&titleId=232",
                          "rules_api_url": "https://rules.nebraska.gov/api/chapter/GetByTitleId/232",
                          "agency_id": 37, "title_id": 232, "title_number": 477, "chapter_id": 1759,
                          "chapter_number": "19", "effective_date": "2020-07-29",
                          "pdf_blob_name": "477 NAC 19 (07-29-2020).pdf", "state_program": "599 CHIP",
                          "discovered_via": BATCH4_DISCOVERED_VIA},
            )
        ],
    },
    "us-hi": {
        "name": "Hawaii",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_pdf",
        "index_url": "https://humanservices.hawaii.gov/admin-rules-2/admin-rules-for-programs/",
        "index_document_count": 140,
        "index_families": {"har_title_17_med_quest_chapter_pdf_17xx": 49, "har_title_17_other_chapter_pdf": 91},
        "primary_source_url": "https://humanservices.hawaii.gov/wp-content/uploads/2016/12/HAR-17-1715-CHILDREN-GROUP-Final-10-31-16-1.pdf",
        "notes": (
            "Retried from a US network 2026-09-10T21:35Z: medquest.hawaii.gov answers (the old har.html page is "
            "HTTP 404; its Rules & Policies page links the DHS Hawaii Administrative Rules index). DHS index "
            "humanservices.hawaii.gov/admin-rules-2/admin-rules-for-programs/: 140 chapter PDFs, 49 of them "
            "Med-QUEST subtitle 12 chapters 17-1700.1 to 17-1739. Hawaii's CHIP is Medicaid-expansion QUEST "
            "coverage for the Children Group. Taken 2: HAR 17-1715 Children Group (8 pages) and HAR 17-1724.2 "
            "MAGI-Based Income Methodology (15 pages), both amended and compiled 2016-11-10 (scanned PDFs with "
            "an OCR text layer, so page-level provisions as in us-nv). Not taken: 17-1714.1 general "
            "eligibility, 17-1711.1 application processing, the income standards charts on the Med-QUEST page."
        ),
        "documents": [
            doc(
                "us-hi", f"hi-dhs-har-{cid}", f"HAR Title 17 Chapter {ch} {title}", url,
                f"us-hi/regulation/har/17/{cid.split('-', 1)[1]}", "pdf", "2016-11-10",
                document_class="regulation",
                subtype="administrative_rule_chapter",
                authority="Hawaii Department of Human Services, Med-QUEST Division (HAR Title 17 Subtitle 12)",
                extraction=PAGES,
                metadata={"legal_identifier": f"HAR 17-{ch}", "compiled": "2016-11-10", "pages": pages,
                          "discovered_via": BATCH4_DISCOVERED_VIA},
            )
            for cid, ch, title, url, pages in (
                ("17-1715", "1715", "Children Group",
                 "https://humanservices.hawaii.gov/wp-content/uploads/2016/12/HAR-17-1715-CHILDREN-GROUP-Final-10-31-16-1.pdf", 8),
                ("17-1724-2", "1724.2", "Modified Adjusted Gross Income (MAGI) Based Income Methodology",
                 "https://humanservices.hawaii.gov/wp-content/uploads/2016/12/HAR-17-1724.2-MAGI-Final-10-31-16-1.pdf", 15),
            )
        ],
    },
    "us-nh": {
        "name": "New Hampshire",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_html",
        "index_url": "https://gc.nh.gov/rules/state_agencies/he-w800.html",
        "index_document_count": 1,
        "index_families": {"he_w_chapter_html": 1},
        "primary_source_url": "https://gc.nh.gov/rules/state_agencies/he-w800.html",
        "notes": (
            "Retried from a US network 2026-09-10T21:35Z: gencourt.state.nh.us answers HTTP 200 (plain and "
            "chrome120; it now redirects to gc.nh.gov, the host us-nh-snap-rules.yaml uses). The Office of "
            "Legislative Services publishes Chapter He-W 800 Eligibility for Medical Assistance as one HTML "
            "document (33 parts, latest amendment effective 2025-10-01). New Hampshire's CHIP is "
            "Medicaid-expansion coverage governed by this chapter. Taken 1, labeled sections He-W 8xx.yy as "
            "in the He-W 700 SNAP scope (156 sections), stopping at Appendix A."
        ),
        "documents": [
            doc(
                "us-nh", "nh-gencourt-he-w-800",
                "New Hampshire Code of Administrative Rules Chapter He-W 800 Eligibility for Medical Assistance",
                "https://gc.nh.gov/rules/state_agencies/he-w800.html",
                "us-nh/regulation/he-w-800", "html", "2025-10-01",
                document_class="regulation",
                subtype="administrative_code",
                authority="New Hampshire General Court, Office of Legislative Services Administrative Rules (DHHS He-W 800)",
                extraction=NH_HE_W_EXTRACTION,
                metadata={"legal_identifier": "He-W 800", "latest_effective": "2025-10-01",
                          "discovered_via": BATCH4_DISCOVERED_VIA},
            )
        ],
    },
    "us-ut": {
        "name": "Utah",
        "document_class": "manual",
        "source_kind": "official_agency_manual_html",
        "index_url": "https://oepmanuals-chip.dhhs.utah.gov/whxdata/toc.new.js",
        "index_document_count": 909,
        "index_families": {"chip_manual_topic_html": 206, "obsolete_policy_topic_html": 697,
                           "faq_topic_html": 3, "glossary_topic_html": 1, "welcome_and_whats_new_html": 2},
        "primary_source_url": "https://oepmanuals-chip.dhhs.utah.gov/Welcome_page.htm",
        "notes": (
            "Retried from a US network 2026-09-10T21:35Z: oepmanuals-chip.dhhs.utah.gov answers HTTP 200 "
            "(plain and chrome120). The DHHS Office of Eligibility Policy CHIP Policy Manual (separate CHIP; "
            "manual effective 2024-05-01, What's New through September 2026) is a RoboHelp site whose table of "
            "contents (whxdata/toc.new.js and 63 nested toc files) lists 909 topic pages: 206 current manual "
            "topics (100 General Provisions 28, 200 Program Standards 42, 400 Income Standards and Household "
            "Composition 61, 600 Program Benefits 5, 700 Eligibility Determination and Redetermination 26, 800 "
            "Records and Case Management 17, 1000 State CHIP 16, Tables 11), 697 Obsolete topics, 3 FAQ, "
            "Glossary, Welcome, What's New. Taken 206 (every current manual topic, one HTML document each, body "
            "with the RoboHelp topic header dropped); each topic states its own Effective Date in its text, so "
            "expression_date is source_as_of."
        ),
        "documents": [_ut_topic_doc(path, name) for path, name in UT_CHIP_TOPICS],
    },
    "us-ak": {
        "name": "Alaska",
        "document_class": "manual",
        "source_kind": "official_agency_manual_html",
        "index_url": "http://dpaweb.hss.state.ak.us/manuals/MAGI2/whdata/whtdata0.htm",
        "index_document_count": 64,
        "index_families": {"magi_manual_topic_html": 64},
        "primary_source_url": "http://dpaweb.hss.state.ak.us/manuals/MAGI2/index.htm",
        "notes": (
            "Never queued before. Alaska's CHIP (Denali KidCare) is Medicaid-expansion coverage determined "
            "under the Division of Public Assistance MAGI Medicaid Eligibility Manual "
            "(dpaweb.hss.state.ak.us/manuals/MAGI2/, HTTP only, the host of us-ak-snap-manual.yaml). Its "
            "WebHelp table of contents (whdata/whtdata0-14.htm, 108 entries) lists 64 topic pages, sections "
            "800-833 (816 MAGI Medicaid Categories names Denali KidCare). Taken 64 (every topic, one HTML "
            "document each, body with the topic header dropped). The manual publishes no manual-wide date, so "
            "expression_date is source_as_of. health.alaska.gov's policy-manuals page is HTTP 404."
        ),
        "documents": [_ak_topic_doc(path, name) for path, name in AK_MAGI_TOPICS],
    },
    "us-nd": {
        "name": "North Dakota",
        "document_class": "manual",
        "source_kind": "official_agency_manual_html",
        "index_url": "https://www.nd.gov/dhs/policymanuals/51003/Data/Tocs/Master_Chunk0.js",
        "index_document_count": 141,
        "index_families": {"service_chapter_510_03_topic_html": 133, "archive_or_site_page_html": 8},
        "primary_source_url": "https://www.nd.gov/dhs/policymanuals/51003/51003.htm",
        "notes": (
            "Never queued before. North Dakota's CHIP (Healthy Steps) is Medicaid-expansion coverage "
            "determined under Service Chapter 510-03 Eligibility Factors for ACA Medicaid (the Healthy Steps "
            "manual is archived inside it), published by HHS on the state's MadCap policy-manual site "
            "(www.nd.gov/dhs/policymanuals/51003/, release 26.3 published 2026-05-15; hhs.nd.gov's own manual "
            "URLs are 404). The table of contents lists 141 entries: 133 policy topics 510-03-05 to "
            "510-03-105-15 plus 8 archive/site pages. Taken 133 (every policy topic, one HTML document each, "
            "#mc-main-content); expression_date 2026-05-15 (last published)."
        ),
        "documents": [_nd_topic_doc(filename, name) for filename, name in ND_ACA_TOPICS],
    },
    "us-vt": {
        "name": "Vermont",
        "document_class": "regulation",
        "source_kind": "official_adopted_rule_pdf",
        "index_url": "https://humanservices.vermont.gov/rules-policies/health-care-rules/health-benefits-eligibility-and-enrollment-rules-hbee",
        "index_document_count": 26,
        "index_families": {"hbee_adopted_part_pdf": 8, "hbee_combined_pdf": 1, "hbee_gcr_pdf": 1,
                           "hbee_proposed_pdf": 10, "repealed_legacy_rule_pdf": 5, "other_pdf": 1},
        "primary_source_url": "https://humanservices.vermont.gov/sites/ahsnew/files/documents/HBEE-Part-2-Eligibility-Standards.pdf",
        "notes": (
            "Never queued before. Vermont's CHIP (Dr. Dynasaur) is determined under the Agency of Human "
            "Services Health Benefits Eligibility and Enrollment (HBEE) Rules; the AHS HBEE page lists 26 "
            "PDFs (8 adopted parts, the combined rules of 2025-12-17, one ARPA GCR, 10 proposed drafts, 5 "
            "repealed legacy rules, one other). Taken 2: Part 2 Eligibility Standards (27 sections, latest "
            "GCR effective 2026-01-01) and Part 5 Financial Methodologies (26 sections, 2026-01-01), labeled "
            "sections from the first body page with the running header dropped. Not taken: parts 1, 3, 4, 6, "
            "7, 8 and the combined PDF (same text)."
        ),
        "documents": [
            doc(
                "us-vt", f"vt-ahs-hbee-part-{num}", f"Health Benefits Eligibility and Enrollment Rules, Part {num} {title}",
                f"https://humanservices.vermont.gov/sites/ahsnew/files/documents/HBEE-Part-{num}-{fname}.pdf",
                f"us-vt/regulation/ahs/hbee/part-{num}", "pdf", "2026-01-01",
                document_class="regulation",
                subtype="adopted_administrative_rule_part",
                authority="Vermont Agency of Human Services (Health Benefits Eligibility and Enrollment Rules)",
                extraction=VT_HBEE_EXTRACTION,
                metadata={"legal_identifier": f"HBEE Part {num}", "state_program": "Dr. Dynasaur",
                          "latest_gcr_effective": "2026-01-01", "discovered_via": BATCH4_DISCOVERED_VIA},
            )
            for num, title, fname in (("2", "Eligibility Standards", "Eligibility-Standards"),
                                      ("5", "Financial Methodologies", "Financial-Methodologies"))
        ],
    },
}

BLOCKED_BATCH4: dict[str, dict] = {
    "us-dc": {
        "name": "District of Columbia",
        "index_url": "https://dcregs.dc.gov/Common/DCMR/RuleList.aspx?ChapterNum=29-95",
        "index_document_count": 19,
        "primary_source_url": "https://dcregs.dc.gov/Common/DCMR/RuleList.aspx?ChapterNum=29-95",
        "notes": (
            "Blocked. DC's CHIP (DC Healthy Families) is Medicaid-expansion coverage governed by 29 DCMR "
            "Chapter 95 Medicaid Eligibility, published by the Office of Documents at dcregs.dc.gov: the chapter "
            "list (19 sections 29-9500 to 29-9599, HTTP 200) and the section pages (SectionList.aspx, "
            "RuleDetail.aspx, e.g. R0054304 effective 2024-03-08) answer, but every rule text and PDF is served "
            "only through ASP.NET __doPostBack form posts with no GET URL, which the official-documents "
            "extractor cannot fetch and this run will not emulate. dhcf.dc.gov requires JavaScript and publishes "
            "no eligibility manual. 0 taken."
        ),
    },
    "us-wy": {
        "name": "Wyoming",
        "index_url": "https://rules.wyo.gov/Search.aspx?mode=1&AgencyId=48",
        "index_document_count": None,
        "primary_source_url": "https://health.wyo.gov/healthcarefin/chip/",
        "notes": (
            "Blocked. Wyoming's separate CHIP (Kid Care CHIP) eligibility rules are Department of Health rules "
            "filed with the Secretary of State at rules.wyo.gov (agency 048): the site answers HTTP 200 but its "
            "agency listing, search and rule downloads are ASP.NET postbacks with no GET listing or file URL, so "
            "the rules cannot be confirmed from a fetchable index. health.wyo.gov/healthcarefin/chip/ (HTTP 200) "
            "publishes only member pages (Does My Child Qualify, copays, renewal, FAQ, handbooks) and no "
            "eligibility manual or rule text; the programs-and-eligibility page is 404. 0 taken."
        ),
    },
}

DONE_BATCH4: dict[str, dict] = {
    "us-la": {
        "name": "Louisiana",
        "index_url": "https://ldh.la.gov/page/medicaid-eligibility-manual",
        "index_document_count": 99,
        "target_manifest": f"discovery/ingest-medicaid: us-la/manual {MEDICAID_RUN_VERSION}",
        "target_scope": {"jurisdiction": "us-la", "document_class": "manual", "version": MEDICAID_RUN_VERSION},
        "pointer": "us-la/manual/ldh/medicaid/h-3030, h-3040, h-3050, z-2500 (LDH Medicaid Eligibility Manual, all 99 PDFs, 891 provisions)",
        "notes": (
            "Done by pointer (reviewer judgment). Retried from a US network 2026-09-10T21:35Z: ldh.la.gov "
            "answers (chrome120 HTTP 200 on the index, plain HTTP 200 on the PDFs); the LDH Medicaid "
            "Eligibility Manual index lists 99 PDFs and LaCHIP is determined under H-3030 Children Under Age "
            "19 Group - LaCHIP, H-3040 LaCHIP Affordable Plan, H-3050 LaCHIP Phase IV and Z-2500 premium "
            "program FPIG. The parallel Medicaid run ingested the whole manual (99 documents, 891 provisions) "
            "on 2026-09-10 at us-la/manual/ldh/medicaid/*, version " + MEDICAID_RUN_VERSION + ", including "
            "those four documents at the same citation paths; a CHIP extraction of the four made in this run "
            "collided with them and was deleted. " + MEDICAID_RUN_NOTE + " Nothing separate to add."
        ),
    },
    "us-oh": {
        "name": "Ohio",
        "index_url": "https://codes.ohio.gov/ohio-administrative-code/chapter-5160:1-4",
        "index_document_count": 6,
        "target_manifest": f"discovery/ingest-medicaid: us-oh/manual {MEDICAID_RUN_VERSION}",
        "target_scope": {"jurisdiction": "us-oh", "document_class": "manual", "version": MEDICAID_RUN_VERSION},
        "pointer": "us-oh/manual/odm/medicaid/5160-1-4-01 ... 5160-1-4-06 (OAC 5160:1 eligibility rules, 96 rule documents, 192 provisions)",
        "notes": (
            "Done by pointer (reviewer judgment). Retried from a US network 2026-09-10T21:35Z: codes.ohio.gov "
            "answers HTTP 200 (plain and chrome120); the LSC index for OAC Chapter 5160:1-4 MAGI-based "
            "medicaid lists 6 rules (5160:1-4-01 to -06; -01 to -03 effective 2026-06-01, -04 2024-03-01, -05 "
            "2025-10-06, -06 2024-01-01), which govern Ohio's Medicaid-expansion CHIP. The parallel Medicaid "
            "run ingested all OAC 5160:1 eligibility rules (96 documents, 192 provisions) on 2026-09-10 at "
            "us-oh/manual/odm/medicaid/5160-1-*, version " + MEDICAID_RUN_VERSION + ", including all six; a "
            "regulation-scope extraction of the six made in this run was deleted as duplicate text. "
            + MEDICAID_RUN_NOTE + " Nothing separate to add."
        ),
    },
    "us-sc": {
        "name": "South Carolina",
        "index_url": "https://img1.scdhhs.gov/mppm/",
        "index_document_count": 19,
        "target_manifest": f"discovery/ingest-medicaid: us-sc/manual {MEDICAID_RUN_VERSION}",
        "target_scope": {"jurisdiction": "us-sc", "document_class": "manual", "version": MEDICAID_RUN_VERSION},
        "pointer": "us-sc/manual/scdhhs/medicaid/section-200 (MPPM Section 200 MAGI Related Programs, chapter-level; 18 MPPM documents, 68 provisions)",
        "notes": (
            "Done by pointer (reviewer judgment). Retried from a US network 2026-09-10T21:35Z: "
            "img1.scdhhs.gov answers HTTP 200 (plain and chrome120) once the chain is completed with the "
            "committed Go Daddy G2 intermediate via REQUESTS_CA_BUNDLE (TLS verification never disabled); the "
            "MPPM index lists 19 documents and Partners for Healthy Children (Medicaid-expansion CHIP) is "
            "Chapter 204.03 of Section 200 MAGI Related Programs (latest revision 2026-08-01). The parallel "
            "Medicaid run ingested the 18 MPPM sections and chapters (68 provisions, chapter level) on "
            "2026-09-10 at us-sc/manual/scdhhs/medicaid/*, version " + MEDICAID_RUN_VERSION + ", including "
            "Section 200; a 139-section labeled extraction of Section 200 made in this run was deleted as "
            "duplicate text (a reviewer wanting section granularity can re-run it: the docx heading pattern "
            "is recorded in the batch-4 run note). " + MEDICAID_RUN_NOTE + " Nothing separate to add."
        ),
    },
    "us-ks": {
        "name": "Kansas",
        "index_url": "https://www.kancare.ks.gov/data-policy/policy/eligibility/manuals",
        "index_document_count": 30,
        "target_manifest": f"discovery/ingest-medicaid: us-ks/manual {MEDICAID_RUN_VERSION}",
        "target_scope": {"jurisdiction": "us-ks", "document_class": "manual", "version": MEDICAID_RUN_VERSION},
        "pointer": "us-ks/manual/kdhe/medicaid/kfmam-01000 ... kfmam-08000 (Kansas Family Medical Assistance Manual, 117 documents, 757 provisions)",
        "notes": (
            "Done by pointer (reviewer judgment). Retried from a US network 2026-09-10T21:35Z: "
            "www.kancare.ks.gov answers the chrome120 client (plain HTTP 403; the old eligibility-policy URL "
            "is 404) and its Policy Manuals page lists the July 2026 KFMAM (khap.kdhe.ks.gov/kfmam/, plain "
            "HTTP 200) and 29 MKEESM releases. CHIP is section 1102 and the family medical determinations "
            "throughout the KFMAM. The parallel Medicaid run ingested the KFMAM (117 documents, 757 "
            "provisions) on 2026-09-10 at us-ks/manual/kdhe/medicaid/kfmam-*, version " + MEDICAID_RUN_VERSION
            + "; a 389-section extraction of the full-manual page made in this run was deleted as duplicate "
            "text. " + MEDICAID_RUN_NOTE + " Nothing separate to add."
        ),
    },
    "us-az": {
        "name": "Arizona",
        "index_url": "https://epm.azahcccs.gov/EligibilityPolicyManual/index.html",
        "index_document_count": 743,
        "target_manifest": f"discovery/ingest-medicaid: us-az/manual {MEDICAID_RUN_VERSION}",
        "target_scope": {"jurisdiction": "us-az", "document_class": "manual", "version": MEDICAID_RUN_VERSION},
        "pointer": "us-az/manual/ahcccs/medicaid/policy-chapter-400-ahcccs-medical-assistance-programs-ma0408 (408 KidsCare; also 528 B, 1204, 1308; AHCCCS Eligibility Policy Manual, 743 documents, 4712 provisions)",
        "notes": (
            "Done by pointer (reviewer judgment). Retried from a US network 2026-09-10T21:35Z: "
            "epm.azahcccs.gov answers HTTP 200 (plain and chrome120) but its root serves only a 158-byte stub; "
            "the manual lives at /EligibilityPolicyManual/index.html, from which the parallel Medicaid run "
            "ingested the whole AHCCCS Eligibility Policy Manual (743 topic documents, 4712 provisions) on "
            "2026-09-10 at us-az/manual/ahcccs/medicaid/*, version " + MEDICAID_RUN_VERSION + ", including "
            "408 KidsCare, 528 B Premium Payment for KidsCare, 1204 KidsCare Premiums and 1308 KidsCare "
            "Application Process. " + MEDICAID_RUN_NOTE + " apps.azsos.gov (A.A.C. 9-31) still returns the "
            "Cloudflare challenge. Nothing separate to add."
        ),
    },
    "us-wi": {
        "name": "Wisconsin",
        "index_url": "https://www.emhandbooks.wisconsin.gov/bcplus/bcplus.htm",
        "index_document_count": 53,
        "target_manifest": f"discovery/ingest-medicaid: us-wi/manual {MEDICAID_RUN_VERSION}",
        "target_scope": {"jurisdiction": "us-wi", "document_class": "manual", "version": MEDICAID_RUN_VERSION},
        "pointer": "us-wi/manual/dhs/medicaid/badgercare-plus-handbook-release-26-03 (BadgerCare Plus Eligibility Handbook Release 26-03 PDF p10171-26-03, 330 page provisions; also meh-release-26-03, 503)",
        "notes": (
            "Done by pointer (reviewer judgment). Retried from a US network 2026-09-10T21:35Z: "
            "www.emhandbooks.wisconsin.gov answers HTTP 200 (plain and chrome120); the BadgerCare Plus "
            "Eligibility Handbook table of contents (whxdata/toc.new.js) lists 53 chapters in 6 books. "
            "Wisconsin's CHIP is BadgerCare Plus (Medicaid-expansion CHIP) and the same handbook, as the DHS "
            "publication PDF p10171-26-03 (Release 26-03), was ingested in full by the parallel Medicaid run "
            "on 2026-09-10 at us-wi/manual/dhs/medicaid/badgercare-plus-handbook-release-26-03 (330 page "
            "provisions, version " + MEDICAID_RUN_VERSION + "), alongside the Medicaid Eligibility Handbook "
            "p10030-26-03. " + MEDICAID_RUN_NOTE + " Nothing separate to add."
        ),
    },
}



# ---------------------------------------------------------------- territories (2026-09-11 pass)
# All five territories run Medicaid-expansion CHIP (medicaid.gov "CHIP Program by State" map), so CHIP
# eligibility lives in the Medicaid state plan and eligibility documents; none publishes a separate CHIP
# manual, handbook or rule. CMS's CHIP State Plan Amendments page (read with the existing
# browser_impersonation option: the plain client gets HTTP 403 from Akamai) hosts SPA approval packages
# and the title XXI template, not territory CHIP plans. The Medicaid finding of the same pass
# (scripts/build_medicaid_state_eligibility_manual_manifests.py --batch 6) is repeated per row.
CMS_CHIP_SPA_INDEX = "https://www.medicaid.gov/chip/state-program-information/chip-spa"
NEW_ROW_NAMES_TERRITORIES: dict[str, str] = {
    "us-pr": "Puerto Rico", "us-gu": "Guam", "us-vi": "Virgin Islands", "us-as": "American Samoa",
    "us-mp": "Northern Mariana Islands",
}
TERRITORY_MEDICAID_FINDING = {
    "us-pr": ("https://medicaid.pr.gov/CMS/5", 138,
              "the Puerto Rico Medicaid Program (medicaid.pr.gov, chain completed with the committed DigiCert G2 intermediate) "
              "publishes applicant document lists, a pre-screening calculator and 138 provider-enrollment files, no eligibility "
              "manual or reglamento; Plan Vital (ASES) pages are insurer and plan information"),
    "us-gu": ("https://dphss.guam.gov/services/medicaremedicaid", 0,
              "Guam DPHSS's Medicare/Medicaid and BHCFA pages are text-only with no document links, and the 2019 state plan "
              "and handbook PDFs answer 404"),
    "us-vi": ("https://dhs.vi.gov/office-of-medicaid/", 10,
              "the Virgin Islands DHS Office of Medicaid page lists nine application forms and the Providers General "
              "Information Manual (provider family), no eligibility manual or state plan"),
    "us-as": ("https://medicaid.as.gov/", None,
              "the American Samoa Medicaid State Agency site medicaid.as.gov has no DNS A record and cannot be reached"),
    "us-mp": ("https://www.cnmimedicaid.org/departments/eligibility-enrollment", 3,
              "the Commonwealth Medicaid Agency's Eligibility & Enrollment page links two application packets and an FAQ on "
              "Google Drive and describes income limits only as percentages of the SSI Federal Benefit Rate; its SPA page "
              "links a Google Sheet and the medicaid.gov SPA index"),
}


def territory_chip_row(jur: str) -> dict:
    index_url, count, finding = TERRITORY_MEDICAID_FINDING[jur]
    name = NEW_ROW_NAMES_TERRITORIES[jur]
    return {
        "queue_status": "blocked_primary_source",
        "source_kind": "official_medicaid_expansion_chip_no_separate_document",
        "primary_source_url": index_url,
        "target_manifest": None,
        "target_scope": {"jurisdiction": jur, "document_class": "manual", "version": None},
        "index_url": index_url,
        "index_document_count": count,
        "taken_count": 0,
        "index_families": {"separate_chip_eligibility_document": {"found": 0, "taken": 0}},
        "notes": (
            f"Blocked (2026-09-11 territories pass; first probe 2026-09-11T21:15Z from a US network). {name}'s CHIP is a "
            "Medicaid-expansion CHIP (all five territories per the medicaid.gov CHIP Program by State map), so CHIP "
            "eligibility is set in the Medicaid state plan and the Medicaid eligibility documents, and the territory "
            f"publishes no separate CHIP manual, handbook or rule. The Medicaid finding of the same pass applies: {finding}. "
            f"CMS's CHIP State Plan Amendments page ({CMS_CHIP_SPA_INDEX}) hosts SPA approval packages and the title XXI "
            "template, not territory CHIP plans. 0 taken. Nothing was worked around."
        ),
    }



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="comma-separated territory jurisdictions whose rows are (re)applied; "
                        "state rows and manifests are regenerated from the static tables either way")
    args = parser.parse_args()
    only = set(args.only.split(",")) if args.only else None
    queue = yaml.safe_load(QUEUE.read_text())
    rows = {s["jurisdiction"]: s for s in queue["states"]}
    for jur, name in {**NEW_ROW_NAMES, **NEW_ROW_NAMES_BATCH3, **NEW_ROW_NAMES_BATCH4}.items():
        rows.setdefault(jur, {"jurisdiction": jur, "name": name, "lead_counts": {},
                              "candidate_sources": []})
    for jur, name in NEW_ROW_NAMES_TERRITORIES.items():
        if only and jur not in only:
            continue
        row = rows.setdefault(jur, {"jurisdiction": jur, "name": name, "lead_counts": {}, "candidate_sources": []})
        row.update(territory_chip_row(jur))
    written: list[str] = []
    for jur, spec in {**CONFIRMED, **CONFIRMED_BATCH2, **CONFIRMED_BATCH3, **CONFIRMED_BATCH4}.items():
        stem = f"{jur}-chip-state-eligibility-manual"
        manifest = {"version": VERSION, "documents": spec["documents"]}
        (ROOT / "manifests" / f"{stem}.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120)
        )
        written.append(stem)
        row = rows[jur]
        row.update({
            "queue_status": "agent_ready",
            "source_kind": spec["source_kind"],
            "primary_source_url": spec["primary_source_url"],
            "target_manifest": f"manifests/{stem}.yaml",
            "target_scope": {"jurisdiction": jur, "document_class": spec["document_class"], "version": VERSION},
            "index_url": spec["index_url"],
            "index_document_count": spec["index_document_count"],
            "taken_count": len(spec["documents"]),
            "notes": spec["notes"],
        })
        if "index_families" in spec:
            row["index_families"] = spec["index_families"]
    for jur, spec in {**BLOCKED, **BLOCKED_BATCH2, **BLOCKED_BATCH3, **BLOCKED_BATCH4}.items():
        if jur in CONFIRMED_BATCH4 or jur in DONE_BATCH4:
            continue  # unblocked by the batch-4 US-network retry
        row = rows[jur]
        row.update({
            "queue_status": "blocked_primary_source",
            "source_kind": "official_publisher_blocked",
            "primary_source_url": spec["primary_source_url"],
            "target_manifest": None,
            "target_scope": {"jurisdiction": jur, "document_class": "manual", "version": None},
            "index_url": spec["index_url"],
            "index_document_count": spec["index_document_count"],
            "taken_count": 0,
            "notes": spec["notes"] + (f" {RETRY_NOTES[jur]}" if jur in RETRY_NOTES else "")
            + (f" {RETRY_NOTES_BATCH4[jur]}" if jur in RETRY_NOTES_BATCH4 else ""),
        })
    for jur, spec in {**DONE, **DONE_BATCH2, **DONE_BATCH3, **DONE_BATCH4}.items():
        row = rows[jur]
        row.update({
            "queue_status": "done",
            "source_kind": "already_in_corpus",
            "primary_source_url": spec["index_url"],
            "target_manifest": spec["target_manifest"],
            "target_scope": spec["target_scope"],
            "index_url": spec["index_url"],
            "index_document_count": spec["index_document_count"],
            "taken_count": 0,
            "notes": spec["notes"],
        })
        if "pointer" in spec:
            row["pointer"] = spec["pointer"]
    queue["states"] = [rows[j] for j in sorted(rows, key=lambda j: (j != "us", j))]
    queue["status_counts"] = {}
    for s in queue["states"]:
        queue["status_counts"][s["queue_status"]] = queue["status_counts"].get(s["queue_status"], 0) + 1
    queue["queue_status"] = "in_progress"
    QUEUE.write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    print(f"wrote {len(written)} manifests: {', '.join(written)}; queue {queue['status_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
