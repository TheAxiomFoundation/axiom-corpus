#!/usr/bin/env python3
"""Needs-driven closure check for SSI, LIHEAP and Medicare (2026-09-11).

Single source of truth for the three law-derived needs schemas and the
jurisdiction x element matrices under docs/coverage/needs-closure-2026-09-11/.

Reads corpus artifacts read-only from --base (default: the main checkout's
data/corpus). Writes <program>-schema.yaml and <program>-matrix.csv next to
this script and prints the roll-ups used in <program>.md.

Status vocabulary (from the brief): PRESENT (a provision in a selected scope
carries the element; cite scope version + citation_path, body opened),
EXTRACTABLE (publisher lists the carrying family, not taken), ABSENT (publisher
posts nothing carrying it; "n/a" when the element does not apply), OUTREACH
(queue records a publisher block), REVIEW (cannot tell).

Federal-only elements are checked once at the federal level; the state rows
inherit the federal status with evidence_note "inherited from federal".
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, OrderedDict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent

STATES = [
    "ak", "al", "ar", "az", "ca", "co", "ct", "dc", "de", "fl", "ga", "hi", "ia", "id",
    "il", "in", "ks", "ky", "la", "ma", "md", "me", "mi", "mn", "mo", "ms", "mt", "nc",
    "nd", "ne", "nh", "nj", "nm", "nv", "ny", "oh", "ok", "or", "pa", "ri", "sc", "sd",
    "tn", "tx", "ut", "va", "vt", "wa", "wi", "wv", "wy",
]
JURS = ["us"] + [f"us-{s}" for s in STATES]

# Selected scopes (docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json
# plus the three 2026-09-11 federal scopes named in the brief).
SEL = {
    "ssi_statute": "2026-06-20-ssi-title-xvi-title-42-r2026-07-15-self-contained-r2026-07-17-dedup",
    "cfr416": "2026-09-11-title-20-part-416",
    "poms": "2026-09-10-ssi-poms-si",
    "cola": "2026-07-05-ssa-cola-2026",
    "autodet": "2026-05-17-ssa-automatic-determinations-2026",
    "dc_ossp": "2026-07-03-dc-ossp-ssa-poms",
    "m426": "2026-06-23-medicare-426-title-42-r2026-07-15-self-contained-r2026-07-17-dedup",
    "medicaid_statute": "2026-06-26-medicaid-title-42-r2026-07-15-self-contained-r2026-07-15-self-contained-r2026-07-17-dedup",
    "cfr435": "2026-06-25-title-42-part-435",
    "iom0101": "2026-09-10-medicare-cms-iom-100-01",
    "iom0124": "2026-09-10-medicare-cms-iom-100-24",
    "iom0102": "2026-09-11-medicare-cms-iom-100-02",
    "iom0104": "2026-09-11-medicare-cms-iom-100-04",
    "cms_ab": "2026-03-10-cms-original-medicare-part-a-b",
}

CORPUS_ROWS: dict[str, list[dict]] = {}


def rows(base: Path, rel: str) -> list[dict]:
    if rel not in CORPUS_ROWS:
        p = base / "provisions" / f"{rel}.jsonl"
        CORPUS_ROWS[rel] = [json.loads(l) for l in p.open()] if p.exists() else []
    return CORPUS_ROWS[rel]


def find(base: Path, rel: str, cp_regex: str | None = None, body_regex: str | None = None):
    """First row whose citation_path matches cp_regex and whose heading+body matches body_regex."""
    crx = re.compile(cp_regex) if cp_regex else None
    brx = re.compile(body_regex, re.I | re.S) if body_regex else None
    for d in rows(base, rel):
        if crx and not crx.search(d["citation_path"]):
            continue
        t = (d.get("heading") or "") + " " + (d.get("body") or "")
        if brx and not brx.search(t):
            continue
        if not (d.get("body") or "").strip() and brx:
            continue
        return d
    return None


def count(base: Path, rel: str, body_regex: str) -> int:
    brx = re.compile(body_regex, re.I | re.S)
    return sum(1 for d in rows(base, rel) if brx.search((d.get("heading") or "") + " " + (d.get("body") or "")))


# ----------------------------------------------------------------------------
# element containers
# ----------------------------------------------------------------------------

RULESPEC = {  # rulespec-us (and rulespec-us-{ca,co,ny}) files walked 2026-09-12; value = encoding paths, "no" = none found
    "SSI-F-USC-1382": "rulespec-us us/statutes/42/1382/{a/1,a/2,a/3,b,e/1}",
    "SSI-F-USC-1382a": "rulespec-us us/statutes/42/1382a/{b/2,b/4}",
    "SSI-F-USC-1382b": "rulespec-us us/statutes/42/1382b/a",
    "SSI-F-USC-1382c": "rulespec-us us/statutes/42/1382c/{a/1,a/2}",
    "SSI-F-USC-1382f": "rulespec-us us/statutes/42/1382f/{a,c}",
    "SSI-F-ANN-FBR": "rulespec-us us/policies/ssa/cola/2026",
    "SSI-F-ANN-SGA": "rulespec-us us/policies/ssa/substantial-gainful-activity/2026",
    "SSI-ST-2": "rulespec-us us-ct/statutes/17b-600, us-dc/statutes/4/4-205/49 (statutes whose text is not in the selected corpus)",
    "SSI-ST-3": "rulespec-us us-ct/policies/dss/upm/{4005-10,4520-10,4520-20,5045-10,5050-13,5520-10,6005}, us-co/regulations/9-ccr-2503-5/{3.531,3.546,3.549,3.570.11}, us-ga/policies/dfcs/medicaid/2578",
    "SSI-ST-4": "rulespec-us us-ak/policies/dpa/apa/standards/2026/state-supplement-payment-standard, us-al/policies/dhr/ssp/state-supplement-payment-standard, us-co/regulations/9-ccr-2503-5/3.532, us-ct/policies/dss/program-standards/2026-01-01/*, us-id/regulations/idapa/16/03/05/514, us-mn/policies/dhs/combined-manual/0020-21/msa-assistance-standards-2026, us-ga/policies/dfcs/medicaid/2578",
    "SSI-ST-5": "rulespec-us us-co/regulations/9-ccr-2503-5/3.533, us-ct/policies/dss/upm/{5030-10,5030-15}",
    "SSI-ST-6": "rulespec-us us/policies/ssa/poms/si-01415-058/2026/federally-administered-optional-supplement-common, us-dc/policies/ssa/poms/si-01415-058/2026/*, us-de/policies/ssa/poms/si-01415-058/2026/*",
    "MED-F-USC-426": "rulespec-us us/statutes/42/426/{a,a/1,a/2,b,b/1,b/2,c,d,e,f,h,h/1}",
    "MED-F-USC-1396a": "rulespec-us us/statutes/42/1396a/{a/10,e,e/14,f,l,m,xx}",
    "MED-F-USC-1396d": "rulespec-us us/statutes/42/1396d/{a/i,n} (1396d(p) QMB standards not encoded)",
    "MED-F-CFR-435-MSP": "rulespec-us us/regulations/42-cfr/435/{121,601/d/1,...}",
    "MED-F-GUID-CMS-AB": "rulespec-us us/policies/cms/original-medicare-part-a-b",
    "MED-ST-1": "rulespec-us us-ct/policies/dss/upm/{4005-10,5030-15} (MSP mentions only)",
}


def elem(eid, name, level, family, sets, pe, sources, note=""):
    return OrderedDict(
        id=eid, name=name, level=level, family=family, set_by=sets, pe_modeled=pe,
        rulespec_encoded=RULESPEC.get(eid, "no"), derived_from=sources, note=note,
    )


class Matrix:
    def __init__(self):
        self.rows: list[dict] = []

    def add(self, jur, element, level, family, status, scope="", cp="", note="", pe="no"):
        assert status in {"PRESENT", "EXTRACTABLE", "ABSENT", "OUTREACH", "REVIEW"}, status
        if status == "PRESENT":
            assert scope and cp, (jur, element)
        self.rows.append(OrderedDict(
            jurisdiction=jur, element=element, level=level, family=family, status=status,
            scope_version=scope, citation_path=cp, pe_modeled=pe, evidence_note=note,
        ))

    def federal(self, element, level, family, status, scope="", cp="", note="", pe="no"):
        self.add("us", element, level, family, status, scope, cp, note, pe)
        for s in STATES:
            self.add(f"us-{s}", element, level, family, status, scope, cp,
                     "inherited from federal", pe)

    def write(self, path: Path):
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(self.rows[0].keys()))
            w.writeheader()
            w.writerows(self.rows)

    def check(self, n_elements):
        per = Counter(r["jurisdiction"] for r in self.rows)
        assert set(per) == set(JURS), set(JURS) ^ set(per)
        assert all(v == n_elements for v in per.values()), per
        pairs = Counter((r["jurisdiction"], r["element"]) for r in self.rows)
        assert max(pairs.values()) == 1




def finish(m: "Matrix", schema):
    """Every jurisdiction x element has exactly one row: the federal jurisdiction gets an
    explicit n/a row for each state-set element (no federal carrier exists for it)."""
    have = {(r["jurisdiction"], r["element"]) for r in m.rows}
    for e in schema:
        if ("us", e["id"]) not in have:
            m.add("us", e["id"], e["level"], "n/a", "ABSENT", note="n/a: state-set element; no federal carrier", pe=e["pe_modeled"])
    m.check(len(schema))

# ----------------------------------------------------------------------------
# SSI
# ----------------------------------------------------------------------------

POMS_SI = [  # (subchapter, title, sections listed, taken)
    ("00500", "Eligibility (chapter TOC)", 1, False), ("00501", "Eligibility Under the SSI Provisions", 32, True),
    ("00502", "SSI Alien Eligibility", 46, True), ("00510", "Requirement to File for Other Program Benefits", 9, False),
    ("00515", "SSA Access to Financial Institutions (AFI)", 5, False), ("00520", "Institutionalization", 38, True),
    ("00529", "No Social Security Benefits for Prisoners Title XVI", 1, False),
    ("00530", "Fugitive Felons and Parole and Probation Violators", 41, False),
    ("00600", "The SSI Application Process (chapter TOC)", 1, False),
    ("00601", "General Applications and Interviewing Policy", 15, False),
    ("00602", "Abbreviated Application Process for Clear Technical Denials", 7, False),
    ("00603", "The SSI Disability/Blindness Initial Claims Process", 17, False),
    ("00604", "Completion of Form SSA-8000-BK", 80, False), ("00605", "Use and Completion of Form SSA-8001-BK", 13, False),
    ("00800", "Income (chapter TOC)", 1, False), ("00810", "General - Income Rules for the SSI Program", 27, True),
    ("00815", "What Is Not Income", 24, True), ("00820", "Earned Income", 44, True), ("00830", "Unearned Income", 183, True),
    ("00832", "Unearned Income Anderson Case", 7, False),
    ("00835", "Living Arrangements and In-Kind Support and Maintenance", 67, True),
    ("00870", "Plans to Achieve Self-Support (PASS)", 20, False),
    ("01100", "Resources (chapter TOC)", 1, False), ("01110", "Resources, General", 28, True),
    ("01120", "Identifying Resources", 63, True), ("01130", "Resources Exclusions", 86, True),
    ("01140", "Types of Countable Resources", 37, True), ("01150", "Other Resources Provisions (transfers, trusts)", 37, False),
    ("01200", "Grandfathered Income and Resource Provisions (chapter TOC)", 1, False),
    ("01210", "Special Blind Income Provision", 37, False), ("01220", "Special Resource Provision", 14, False),
    ("01300", "Deeming (chapter TOC)", 1, False), ("01310", "Deeming, General", 53, True),
    ("01320", "Deeming of Income", 55, True), ("01330", "Deeming of Resources", 22, True),
    ("01400", "State Supplementary Payments (chapter TOC)", 1, True),
    ("01401", "Introduction to State Supplementation", 4, True),
    ("01403", "Pass Along of Federal SSI COLA Increases", 3, True),
    ("01405", "Federal and State Administrative Considerations", 2, True),
    ("01410", "Federal Administration of State Supplementary Payments", 9, True),
    ("01415", "Elements of State Supplementary Payments (state tables, payment levels)", 65, True),
    ("01700", "Medicaid Eligibility (chapter TOC)", 1, False), ("01715", "Medicaid and the SSI Program", 6, False),
    ("01730", "SSA Determinations of Medicaid Eligibility (1634 states)", 38, False),
    ("01800", "SNAP (chapter TOC)", 1, False), ("01801", "Supplemental Nutrition Assistance Program", 34, False),
    ("02000", "Benefits and Payments (chapter TOC)", 1, False), ("02001", "Computation of Benefits - Introduction", 5, True),
    ("02002", "Monitoring State Accounting for IAR Payments", 6, False), ("02003", "Interim Assistance Payments", 45, False),
    ("02004", "Direct Field Office Payments", 8, False), ("02005", "Computation of Benefits - SSI", 21, True),
    ("02006", "Windfall Offset and Effect on Title XVI Payments", 15, False),
    ("02007", "SSI Interim Benefits Payments", 5, False), ("02009", "Computation of Payments for Months Prior to April 1982", 16, False),
    ("02100", "Underpayments (chapter TOC)", 1, False), ("02101", "Title XVI Underpayments", 14, False),
    ("02200", "Overpayments (chapter TOC)", 1, False), ("02201", "SSI Overpayments - Overview", 10, False),
    ("02205", "SSI Overpayments - Sponsor/Alien Cases", 3, False), ("02220", "Recovery Procedures for SSI Overpayments", 40, False),
    ("02300", "Posteligibility Events (chapter TOC)", 1, False), ("02301", "Posteligibility Changes", 30, False),
    ("02302", "Continuing Benefits Under Sections 1619(a) and 1619(b)", 17, False),
    ("02305", "Redeterminations of Eligibility and/or Payment Amount", 73, False),
    ("02306", "Miscellaneous Posteligibility Issues", 5, False), ("02309", "Critical Birthday and Insured Status Diaries", 8, False),
    ("02310", "SSI Interfaces", 31, False), ("02900", "State Financial Management (chapter TOC)", 1, False),
    ("02901", "SSI Administrative Costs", 5, False), ("04000", "Administrative Review, Appeals and Finality (chapter TOC)", 1, False),
    ("04005", "Administrative Review (Appeals) Process - SSI", 7, False), ("04010", "Initial Determinations - SSI", 3, False),
    ("04020", "Reconsideration - SSI", 7, False), ("04030", "ALJ Hearings - SSI", 9, False),
    ("04040", "Appeals Council Review - SSI", 7, False), ("04050", "Litigation - SSI", 6, False),
    ("04060", "Expedited Appeals Process - SSI", 2, False), ("04070", "Administrative Finality - SSI", 11, False),
]
POMS_PE = {"00501": "partial", "00502": "partial", "00520": "partial", "00810": "partial", "00815": "partial",
           "00820": "partial", "00830": "partial", "00835": "partial", "01110": "partial", "01120": "partial",
           "01130": "partial", "01140": "partial", "01310": "yes", "01320": "yes", "01330": "partial",
           "01415": "partial", "02005": "partial", "02302": "no"}

SSI_STATUTE = [  # (section, title, pe)
    ("1381", "Statement of purpose", "no"), ("1381a", "Basic entitlement to benefits", "no"),
    ("1382", "Eligibility for benefits: income and resource limits, benefit amounts, couples, institutions, absence", "yes"),
    ("1382a", "Income: definition, earned/unearned, exclusions", "yes"),
    ("1382b", "Resources: definition, exclusions, transfers, trusts", "partial"),
    ("1382c", "Definitions: aged, blind, disabled, child, marriage, eligible spouse", "partial"),
    ("1382d", "Rehabilitation services for blind and disabled individuals", "no"),
    ("1382e", "Supplementary assistance by States (optional and mandatory supplementation, administration, pass-along)", "partial"),
    ("1382f", "Cost-of-living adjustments in benefits", "yes"),
    ("1382g", "Payments to institutions and residents (institutional rate)", "partial"),
    ("1382h", "Continuing benefits and Medicaid for working recipients (1619(a)/(b))", "no"),
    ("1382i", "Medical and social services for certain handicapped persons", "no"),
    ("1382j", "Attribution of sponsor's income and resources to aliens", "no"),
    ("1383", "Procedure for payment of benefits: applications, representative payees, overpayments, redeterminations, PASS", "no"),
    ("1383a", "Penalties for fraud", "no"), ("1383b", "Administration", "no"),
    ("1383c", "Eligibility for medical assistance of aged, blind, or disabled individuals (Medicaid link)", "no"),
    ("1383d", "Outreach program for children", "no"), ("1383e", "Annual report on program", "no"),
    ("1383f", "Report on SSI eligibility / recipient counts", "no"),
]
CFR416 = [  # subpart letter, title, pe
    ("A", "Introduction, General Provisions and Definitions", "no"), ("B", "Eligibility", "partial"),
    ("C", "Filing of Applications", "no"), ("D", "Amount of Benefits", "yes"),
    ("E", "Payment of Benefits, Overpayments, and Underpayments", "no"), ("F", "Representative Payment", "no"),
    ("G", "Reports Required", "no"), ("H", "Determination of Age", "no"), ("I", "Determining Disability and Blindness", "no"),
    ("J", "Determinations of Disability (state agency process)", "no"), ("K", "Income (exclusions, ISM, deeming)", "yes"),
    ("L", "Resources and Exclusions", "partial"), ("M", "Suspensions and Terminations", "no"),
    ("N", "Determinations, Administrative Review Process, and Reopening", "no"), ("O", "Representation of Parties", "no"),
    ("P", "Residence and Citizenship", "partial"), ("Q", "Referral to Other Agencies", "no"),
    ("R", "Relationship (marriage, parent-child)", "partial"), ("S", "Interim Assistance Provisions", "no"),
    ("T", "State Supplementation Provisions; Agreement; Payments", "partial"),
    ("U", "Medicaid Eligibility Determinations", "no"), ("V", "Payments for Vocational Rehabilitation Services", "no"),
]

# State-level SSI supplement data (from manifests/ssi-agent-queue.yaml, the three
# 2026-09-10 state-supplement run notes, POMS SI 01415.010, and the provision
# bodies opened in this analysis).
POMS = SEL["poms"]
P058 = "us/manual/ssa/poms/si/01415.058/block-"
SSI_STATES = {
    # admin, class, authority(status, scope, cp, note), elig(status,scope,cp,note), amounts(...), income_rules(...), fed_levels(...)
    "ak": dict(admin="S", authority=("REVIEW", "", "", "AS 47.25.430-.615 (APA statute) not inventoried; the queue took the DPA APA Manual only"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ak/manual/dpa/apa/400-400-1-an-overview-of-the-adult-public-assistance-program/block-1", "DPA Adult Public Assistance Manual 400-1 overview (4,942 chars; 660 rows, sections 400-482); eligibility categories and living arrangements in the 400s-470s topics"),
               amounts=("PRESENT", "2026-06-30-ak-apa-standards-ak-dpa-apa-standards-2026", "us-ak/guidance/dpa/apa/standards/2026/page-1", "APA payment standards 2026 ($977 need standard on page 1); manual section 470s carry the standards text"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ak/manual/dpa/apa/440-440-4-determining-the-household-s-monthly-income/block-1", "APA 440-4 Determining eligibility and benefit level (28,534 chars); income 440-443, resources 430-433 (430-2 resource limits)")),
    "al": dict(admin="S", authority=("PRESENT", "2026-06-30-al-admin-code-660-2-4", "us-al/regulation/alabama-administrative-code/660/2/4", "Alabama Administrative Code chapter 660-2-4 Optional Supplementation (62 page rows)"),
               elig=("PRESENT", "2026-06-30-al-admin-code-660-2-4", "us-al/regulation/alabama-administrative-code/660/2/4/page-2", "page 2 (660-2-4-.01 General): optional supplementation is paid to SSI recipients not on assistance in December 1973; page 4: ineligibility for SSI means ineligibility for supplementation"),
               amounts=("PRESENT", "2026-06-30-al-admin-code-660-2-4", "us-al/regulation/alabama-administrative-code/660/2/4/page-24", "page 24 payment table (nursing care supplement $60, personal care supplements); page granularity, supplement dated 3/31/95"),
               income=("REVIEW", "2026-06-30-al-admin-code-660-2-4", "us-al/regulation/alabama-administrative-code/660/2/4/page-10", "chapter present at page granularity (62 pages, supplement dated 3/31/95) but the budgeting page was not individually located; open pages 10-24")),
    "ar": dict(admin="N"), "az": dict(admin="N"), "ms": dict(admin="N"), "nd": dict(admin="N"), "tn": dict(admin="N"), "wv": dict(admin="N"),
    "ca": dict(admin="F", authority=("PRESENT", "2026-06-27-ca-ssi-ssp-wic-12200-us-ca-sections-wic-12200", "us-ca/statute/wic/12200", "Welf. & Inst. Code 12200 (SSP payment standards statute, 2,917 chars)"),
               fed=(f"{P058}2", "California living-arrangement definitions (block-2) and payment levels (blocks 4-5); regional SI SF01415.100-.190")),
    "co": dict(admin="S", authority=("PRESENT", "2026-06-19-co-oap-9-ccr-2503-5-r2026-07-15-self-contained", "us-co/regulation/9-ccr-2503-5/3.530", "9 CCR 2503-5 Adult Financial: 3.530 OAP, 3.540 AND-SO"),
               elig=("PRESENT", "2026-06-19-co-oap-9-ccr-2503-5-r2026-07-15-self-contained", "us-co/regulation/9-ccr-2503-5/3.540.1", "OAP and AND-SO definitions and eligibility (3.530.1, 3.540.1)"),
               amounts=("PRESENT", "2026-06-19-co-oap-9-ccr-2503-5-r2026-07-15-self-contained", "us-co/regulation/9-ccr-2503-5/3.530", "OAP grant standard $1,032 effective 2026-01-01; PNA $79 in 3.532"),
               income=("PRESENT", "2026-06-19-co-oap-9-ccr-2503-5-r2026-07-15-self-contained", "us-co/regulation/9-ccr-2503-5/3.533", "3.533 income disregards ($65 + half)")),
    "ct": dict(admin="S", authority=("REVIEW", "", "", "Conn. Gen. Stat. 17b-600 et seq. not inventoried; DSS UPM sections are the operating rule"),
               elig=("PRESENT", "2026-07-02-ct-ssp-upm-and-standards", "us-ct/policy/dss/upm/4005.05/block-1", "UPM 4005.05 general principles, 4520.10 rated housing, 4520.20 LTC facilities"),
               amounts=("PRESENT", "2026-07-02-ct-ssp-upm-and-standards", "us-ct/policy/dss/program-standards/2026-01-01/page-1", "DSS program standards chart effective 2026-01-01 (page 1: SSP standards, $1,600 asset limit, disregards); UPM 4520.10 rated housing rates ($130.40 New Horizons)"),
               income=("PRESENT", "2026-07-02-ct-ssp-upm-and-standards", "us-ct/policy/dss/upm/5030.10/block-1", "UPM 5030.10 earned income disregard, 5030.15 unearned income disregard, 4005.10 asset limits")),
    "dc": dict(admin="F/S", authority=("REVIEW", "", "", "DC Code 4-205.05 et seq. / DCMR not inventoried for the state-administered part"),
               fed=(f"{P058}10", "DC living-arrangement definitions (block-10) and payment levels (blocks 12-13); SI PHI01415.009; also us/guidance/ssa/poms/si-01415-058/2026 (dc-ossp scope)"),
               fs_note="F/S: the state-administered part (DHCF OSSP for adult foster care, DC Code 4-205.05) is not covered by the queue"),
    "de": dict(admin="F/S", authority=("REVIEW", "", "", "us-de/regulation/2026-07-03-de-dssm-13000 (DSSM 13000, 25 page rows) is on disk but not in the draft selector; Del. Code title 31 not inventoried"),
               fed=(f"{P058}6", "Delaware living-arrangement definitions (block-6) and payment levels (blocks 8-9); SI PHI01415.008; also us-de/guidance/2026-07-03-de-ssi-state-supplement-poms"),
               fs_note="F/S: the state-administered part is not covered by the queue"),
    "fl": dict(admin="S", authority=("PRESENT", "2026-09-10-ssi-state-supplement", "us-fl/regulation/fac/65a-2/033", "FAC chapter 65A-2 Optional State Supplementation (8 rules)"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-fl/regulation/fac/65a-2/033", "65A-2.033 OSS eligibility and living arrangements (ALF, AFCH, MHRTF)"),
               amounts=("PRESENT", "2026-09-10-ssi-state-supplement", "us-fl/regulation/fac/65a-2/036/block-1", "65A-2.036 OSS base provider rates ($1,152.00) and personal needs allowance ($160.00); 65A-2.033 OSS income standard $609.40"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-fl/regulation/fac/65a-2/033/block-1", "income/PNA budgeting in 65A-2.033")),
    "ga": dict(admin="S", authority=("REVIEW", "", "", "O.C.G.A. 49-4-3 not inventoried; DFCS manual sections are the operating text"),
               elig=("PRESENT", "2026-07-13-recovery-r2026-07-17-dedup", "us-ga/manual/dfcs/medicaid/2578/block-3", "Medicaid Policy Manual 2578 SSI Recipients (nursing-home supplement) and 2136 institutionalized hospice (medicaid scope)"),
               amounts=("PRESENT", "2026-07-13-recovery-r2026-07-17-dedup", "us-ga/manual/dfcs/medicaid/2578/block-3", "2578 Basic Considerations: SSI reduced to $30 in NH plus state supplement table by effective date"),
               income=("ABSENT", "", "", "n/a: Georgia's supplement is a flat institutional add-on for SSI recipients; SSI income rules apply")),
    "hi": dict(admin="F", authority=("REVIEW", "", "", "HRS 346-53 not inventoried"),
               fed=(f"{P058}14", "Hawaii living-arrangement definitions (block-14) and payment levels (blocks 16-17); SI SF01415.200-.220")),
    "ia": dict(admin="F/S", authority=("REVIEW", "", "", "Iowa Code 249 / 441 IAC 51-52 not inventoried"),
               fed=(f"{P058}18", "Iowa living-arrangement definitions (block-18) and payment levels (blocks 20-21)"),
               fs_note="F/S: the state-administered part (441 IAC chapter 52, in-home health related care) is not covered by the queue"),
    "id": dict(admin="S", authority=("PRESENT", "2026-07-04-id-aabd-rules", "us-id/regulation/idapa/16/03/05", "IDAPA 16.03.05 Eligibility for AABD (286 section rows)"),
               elig=("PRESENT", "2026-07-04-id-aabd-rules", "us-id/regulation/idapa/16/03/05/156", "156 AABD for the blind or disabled; 107-109 institutional status; 513 RALF/CFH living arrangements (286 section rows)"),
               amounts=("PRESENT", "2026-07-04-id-aabd-rules", "us-id/regulation/idapa/16/03/05/514", "514 AABD cash payments (maximum payments by living arrangement; $18 essential-person case); 501 basic allowance $545/month; 502 special needs allowances"),
               income=("PRESENT", "2026-07-04-id-aabd-rules", "us-id/regulation/idapa/16/03/05/201", "201 resource limit $2,000/$3,000; income sections 300s")),
    "il": dict(admin="S", authority=("REVIEW", "", "", "305 ILCS 5/3 (AABD article) not inventoried; the IDHS manual is the operating text"),
               elig=("PRESENT", "2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained", "us-il/manual/dhs/csmm/15910", "PM 11-01-00 AABD Cash Assistance Standard; PM I-03-03 Adult Programs"),
               amounts=("PRESENT", "2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained", "us-il/manual/dhs/csmm/15911/block-1", "WAG 11-01-00 AABD standard; WAG 25 attachments (12661) carry the area/allowance tables"),
               income=("PRESENT", "2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained", "us-il/manual/dhs/csmm/15967/block-1", "PM/WAG 11-02-03 using the standard; income disregards in PM 08")),
    "in": dict(admin="S", authority=("REVIEW", "", "", "IC 12-10-6 not inventoried"),
               elig=("PRESENT", "2026-07-04-in-ssp-sapn", "us-in/manual/fssa/medicaid-policy-manual/chapter-5000/5005.00.00", "IHCPPM chapter 5000 SAPN eligibility"),
               amounts=("PRESENT", "2026-07-04-in-ssp-sapn", "us-in/manual/fssa/medicaid-policy-manual/chapter-5000/5005.05.00", "5005.05.00 benefit calculation"),
               income=("ABSENT", "", "", "n/a: SAPN is a personal-needs add-on for RCAP residents; SSI income rules apply")),
    "ks": dict(admin="S", authority=("REVIEW", "", "", "us-ks/statute/2026-07-04-ks-sspp-statute (K.S.A. 39-972) is on disk but not in the draft selector"),
               elig=("PRESENT", "2026-07-04-ks-sspp-guidance", "us-ks/guidance/khpa/policy-memo/2007-05-01/state-supplemental-payment-program/page-2", "page 2: SSPP eligibility follows SSI receipt and the institutional living arrangement (KHPA policy memo 2007-05-01; currency not confirmed)"),
               amounts=("REVIEW", "2026-07-04-ks-sspp-guidance", "us-ks/guidance/khpa/policy-memo/2007-05-01/state-supplemental-payment-program/page-2", "the 2007 memo describes the SSPP design and payment; no current-year amount is in the corpus (K.S.A. 39-972 scope is on disk, unselected)"),
               income=("ABSENT", "", "", "n/a: flat institutional/personal-needs supplement; SSI rules apply")),
    "ky": dict(admin="S", authority=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ky/regulation/kar/921/002/015", "921 KAR 2:015 Supplemental programs for persons who are aged, blind, or have a disability"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ky/regulation/kar/921/002/015/block-1", "PCH/FCH/caretaker categories in 921 KAR 2:015"),
               amounts=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ky/regulation/kar/921/002/015/block-1", "payment standard amounts ($965 etc.) in the regulation text"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ky/regulation/kar/921/002/015/block-1", "income and resource rules in the same regulation")),
    "la": dict(admin="S", authority=("REVIEW", "", "", "La. R.S. 46:1 et seq. not inventoried; LDH manual J-0000 is the operating text"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-la/manual/ldh/medicaid-eligibility/j-0000/page-2", "J-300 Optional State Supplement payment: state-funded payment of up to $15.00 to certain LTC beneficiaries (page granularity)"),
               amounts=("PRESENT", "2026-09-10-ssi-state-supplement", "us-la/manual/ldh/medicaid-eligibility/j-0000/page-2", "J-300: OSS is up to $15.00 per month (Reissued July 21, 2025)"),
               income=("ABSENT", "", "", "n/a: flat $15 institutional supplement to SSI-eligible LTC beneficiaries; SSI rules apply")),
    "ma": dict(admin="S", authority=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ma/regulation/106-cmr/327/327.100", "106 CMR 327.000 Eligibility Requirements for SSP (24 sections)"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ma/regulation/106-cmr/327/327.220", "327.220 State Living Arrangements A-G"),
               amounts=("REVIEW", "2026-09-10-ssi-state-supplement", "us-ma/regulation/106-cmr/327/327.330", "327.330 Payment Standards names the method but the dollar table is in a DTA standards chart not taken; POMS SI BOS01415.930 (federal scope) carries older optional-payment text"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ma/regulation/106-cmr/327/327.100", "income and asset rules in 106 CMR 327")),
    "md": dict(admin="S", authority=("PRESENT", "2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07", "us-md/regulation/title-07/subtitle-03/chapter-07", "COMAR 07.03.06 Mandatory State Supplement and 07.03.07 Public Assistance to Adults"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07", "us-md/regulation/title-07/subtitle-03/chapter-07/regulation-04", "PAA eligibility (assisted living, group homes)"),
               amounts=("PRESENT", "2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07", "us-md/regulation/title-07/subtitle-03/chapter-07/regulation-04", "PAA grant computation with dollar figures ($82 PNA)"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07", "us-md/regulation/title-07/subtitle-03/chapter-07/regulation-04", "income/resource treatment in 07.03.07")),
    "me": dict(admin="S", authority=("PRESENT", "2026-09-10-ssi-state-supplement", "us-me/regulation/dhhs/ofi/chapter-332/part-11/section-1", "10-144 CMR ch. 332 Part 11 State Supplement"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-me/regulation/dhhs/ofi/chapter-332/part-11/section-5", "Part 11 section 5 Types of living arrangements (living alone/with others, flat-rate boarding home, adult foster home, cost-reimbursed boarding home)"),
               amounts=("PRESENT", "2026-09-10-ssi-state-supplement", "us-me/regulation/dhhs/ofi/chapter-332/part-11/section-5", "section 5: $10.00 individual / $7.50 per member of a couple living alone or with others; boarding-home amounts by arrangement; POMS SI BOS01415.010/.910 in the federal scope"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-me/regulation/dhhs/ofi/chapter-332/part-11/section-2", "section 2: countable income per Part 7 section 2; payment = SSI maximum plus supplement minus countable income")),
    "mi": dict(admin="F/S", authority=("REVIEW", "", "", "MCL 400.1 et seq. not inventoried"),
               fed=(f"{P058}22", "Michigan living-arrangement definitions (block-22) and payment levels (blocks 24-25); SI CHI01415.001"),
               fs_note="F/S: the state-administered part is not covered by the queue"),
    "mn": dict(admin="S", authority=("REVIEW", "", "", "Minn. Stat. 256D.33-.54 (MSA) not inventoried; DHS Combined Manual is the operating text"),
               elig=("PRESENT", "2026-05-27-mn-combined-manual-r2026-07-15-self-contained", "us-mn/manual/dhs/combined-manual/current/page-913", "0020.21 MSA Assistance Standards: living-arrangement rules (page 914 of the PDF; issue 09/2020)"),
               amounts=("REVIEW", "2026-05-27-mn-combined-manual-r2026-07-15-self-contained", "us-mn/manual/dhs/combined-manual/current/page-914", "page 915 of the PDF prints the $614.66 living-with-others MSA standard from the 09/2020 issue (stale); the 01/2026 revised MSA sections (us-mn/manual/2026-06-27-mn-dhs-msa-revised-sections-2026-01) are on disk but not selected"),
               income=("PRESENT", "2026-05-27-mn-combined-manual-r2026-07-15-self-contained", "us-mn/manual/dhs/combined-manual/current/page-949", "MSA budgeting steps (page 950): subtract countable income from the 0020.21 standard plus special needs (0023)")),
    "mo": dict(admin="S", authority=("REVIEW", "", "", "RSMo 208.030 (SAB) / 208.030-.040 (SNC) not inventoried; 13 CSR 40-2 has no SNC/SAB rule (queue)"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-mo/manual/dss/snc/0605-000-00/block-1", "SNC 0605.000.00 Eligibility: persons 21+ in a licensed RCF/ALF/ICF/SNF; SAB Manual 0400-0440 in the same scope"),
               amounts=("PRESENT", "2026-09-10-ssi-state-supplement", "us-mo/manual/dss/snc/0615-000-00/0615-005-00/block-1", "SNC 0615.005.00 Maximum Grants by licensed facility type"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-mo/manual/dss/snc/0610-000-00/0610-005-00/block-1", "SNC/SAB income and resource limits in the manuals")),
    "mt": dict(admin="F", authority=("REVIEW", "", "", "MCA 53-2 not inventoried"),
               fed=(f"{P058}26", "Montana living-arrangement definitions (block-26) and payment levels (blocks 28-29); SI DEN01415.010")),
    "nc": dict(admin="S", authority=("REVIEW", "", "", "G.S. 108A-40 et seq. not inventoried; NCDHHS SA manuals are the operating text"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-nc/manual/dss/special-assistance/manual/page-6", "State/County Special Assistance manual (368 pages) and SA In-Home manual"),
               amounts=("PRESENT", "2026-09-10-ssi-state-supplement", "us-nc/manual/dss/special-assistance/manual/page-219", "SA rate and FBR chart: 2026 basic rate $1,397, basic maintenance $1,467, enhanced $1,792, enhanced maintenance $1,862; FBR $994"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-nc/manual/dss/special-assistance/manual/page-165", "countable income rules (pages 165-166); resource exclusions pages 113-116 ($1,500 burial exclusion)")),
    "ne": dict(admin="S", authority=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ne/regulation/title-469/chapter-2/001", "469 NAC chapters 1-4 (AABD payment program); 2-001 Eligibility"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ne/regulation/title-469/chapter-2/001", "469 NAC 2-001 Eligibility (application, citizenship, ... ); 2-010.01(B)(vi)(3)(a) SSI referral"),
               amounts=("REVIEW", "2026-09-10-ssi-state-supplement", "us-ne/regulation/title-469/chapter-3/003.01.b", "469 NAC 3-003.01(B) defines the AABD/SDP standard of need by living arrangement; the dollar table was not found in the chapter text"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ne/regulation/title-469/chapter-2/010.01.b.xi", "2-010.01(B)(xi) computation of income and disregards ($20 general disregard; (xi)(2) earned income disregards)")),
    "nh": dict(admin="S", authority=("REVIEW", "", "", "RSA 167 / He-W 600 rules not inventoried; DHHS Adult Assistance Manual is the operating text"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-nh/manual/dhhs/aam/203-categorical-requirements-aam/block-1", "AAM 203 Categorical requirements (OAA, ANB, APTD); 227 assistance group composition; 515 topic pages"),
               amounts=("REVIEW", "2026-09-10-ssi-state-supplement", "us-nh/manual/dhhs/aam/601-table-a-income-limits-aam/block-1", "AAM 601 Table A Income Limits (standards of need) extracted as a 60-character stub (table not captured); 617 Grant Determination gives the method only"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-nh/manual/dhhs/aam/603-01-earned-income-disregard-aam/block-1", "AAM 603.01 earned income disregard ($65 rule), 603.05 adult standard disregard, 613 computing eligibility")),
    "nj": dict(admin="F", authority=("REVIEW", "", "", "N.J.S.A. 44:7-85 et seq. not inventoried"),
               fed=(f"{P058}34", "New Jersey living-arrangement definitions (block-34) and payment levels (blocks 36-37); SI NY01415.025")),
    "nm": dict(admin="S", authority=("PRESENT", "2026-09-10-ssi-state-supplement", "us-nm/regulation/nmac/8/106/100/8.106.100.7", "8.106 NMAC State Funded Assistance Programs (17 parts)"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-nm/regulation/nmac/8/106/400/8.106.400.11", "8.106.400.11 Living arrangement: the ARSCH supplement requires residence in a licensed adult residential shelter care facility; 8.106.400.10 benefit group"),
               amounts=("PRESENT", "2026-09-10-ssi-state-supplement", "us-nm/regulation/nmac/8/106/500/8.106.500.10", "8.106.500.10 Payments to adults in residential care: $100 per month to an SSI recipient in a licensed shelter care home (Rp 3/1/2025)"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-nm/regulation/nmac/8/106/520/8.106.520.12", "8.106.520 income rules (520.9 exempt income, 520.12 earned income deductions) govern GA; the ARSCH supplement is a flat $100 to SSI recipients")),
    "nv": dict(admin="F", authority=("REVIEW", "", "", "NRS 422 not inventoried"),
               fed=(f"{P058}30", "Nevada living-arrangement definitions (block-30) and payment levels (blocks 32-33); SI SF01415.300")),
    "ny": dict(admin="S", blocked="otda.ny.gov JavaScript challenge (plain client connection reset; chrome120 impersonation returns a challenge page); retried from a US network 2026-09-10",
               fed_partial=("us/manual/ssa/poms/si/ny01415.026", "SI NY01415.026 New York Payments (regional description, 06/2006)")),
    "oh": dict(admin="S", authority=("PRESENT", "2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated", "us-oh/regulation/agency-5122/chapter-5122-36/rule-5122-36-01", "OAC chapter 5122-36 Residential State Supplement (5 rules)"),
               elig=("PRESENT", "2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated", "us-oh/regulation/agency-5122/chapter-5122-36/rule-5122-36-02", "5122-36-02 RSS non-financial eligibility; -04 living arrangements"),
               amounts=("REVIEW", "2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated", "us-oh/regulation/agency-5122/chapter-5122-36/rule-5122-36-05", "5122-36-05 sets the payment determination; the RSS payment level itself is set by OhioMHAS notice, not in the rule text"),
               income=("PRESENT", "2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated", "us-oh/regulation/agency-5122/chapter-5122-36/rule-5122-36-05", "financial determination by CDJFS under 5122-36-05 / 5160:1-3")),
    "ok": dict(admin="S", authority=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ok/regulation/oac/340/15/340-15-1-1", "OAC 340:15 State Supplemental Payment"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ok/regulation/oac/340/15/340-15-1-1", "340:15-1-1 purpose; -1-2 definitions"),
               amounts=("REVIEW", "2026-09-10-ssi-state-supplement", "us-ok/regulation/oac/340/15/340-15-1-5", "340:15-1-5: payment based on the SSP need standard in OKDHS Appendix C-1 Schedule VIII.A; Appendix C-1 not taken"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-ok/regulation/oac/340/15/340-15-1-2", "340:15-1-2 income exclusions ($20, $65 + half)")),
    "or": dict(admin="S", authority=("EXTRACTABLE", "", "", "OAR chapter 461 (OSIP, secure.sos.state.or.us, HTTP 200 on 2026-09-10) is the adopted-rule family, not taken"),
               elig=("REVIEW", "2026-07-16-or-programs-eligibility-notebook", "us-or/manual/odhs/open/page-33", "OPEN page 33: OSIPM-eligible individuals can receive OSIP cash special-needs payments; the OSIP eligibility rules (OAR 461-135) are cited by number only and not taken"),
               amounts=("EXTRACTABLE", "", "", "OAR 461-155-0250 Income and Payment Standard (cited on OPEN page 510) is on the Secretary of State OARD (HTTP 200 on 2026-09-10) and not taken"),
               income=("EXTRACTABLE", "", "", "OAR 461-160-0550 income deductions and 461-160-0780 adjusted income (cited on OPEN pages 269 and 510) not taken")),
    "pa": dict(admin="F/S", authority=("REVIEW", "", "", "62 P.S. 432.4 / 55 Pa. Code 297 not inventoried"),
               fed=(f"{P058}38", "Pennsylvania living-arrangement definitions (block-38) and payment levels (blocks 40-41); SI PHI01415.010"),
               fs_note="F/S: the state-administered part (domiciliary care, 55 Pa. Code 297) is not covered by the queue"),
    "ri": dict(admin="F/S", authority=("REVIEW", "", "", "R.I. Gen. Laws 40-6-27 not inventoried"),
               fed=(f"{P058}42", "Rhode Island living-arrangement definitions (block-42) and coding/levels (block-43); SI BOS01415.012 and .950"),
               fs_note="F/S: the state-administered part is not covered by the queue"),
    "sc": dict(admin="S", authority=("REVIEW", "", "", "S.C. Code 43-5-10 et seq. not inventoried; SCDHHS MPPM chapter 403 is the operating text"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-sc/manual/scdhhs/mppm/chapter-403/403.02", "403.02 Categorical eligibility (aged 65+, blind, disabled per SSI); 403.01 introduction (CRCF residents); sections 403.01-403.12"),
               amounts=("REVIEW", "2026-09-10-ssi-state-supplement", "us-sc/manual/scdhhs/mppm/chapter-403/403.05.03B", "403.05.03B: payment = net income limit (NIL) minus countable income; the NIL dollar figure sits in the MPPM 103 standards, not in chapter 403"),
               income=("PRESENT", "2026-09-10-ssi-state-supplement", "us-sc/manual/scdhhs/mppm/chapter-403/403.05.02", "403.05.02 OSS income considerations (ISM not counted); 403.06 resource criteria ($2,000)")),
    "sd": dict(admin="S", authority=("PRESENT", "2026-09-10-ssi-state-supplement", "us-sd/regulation/arsd/67/12/14/01", "ARSD 67:12:14 Optional State Supplemental Program (11 sections)"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-sd/regulation/arsd/67/12/14/02", "67:12:14:02 eligibility requirements (SSI recipient, adult 18+, resident, independent living arrangement)"),
               amounts=("REVIEW", "2026-09-10-ssi-state-supplement", "us-sd/regulation/arsd/67/12/14/04", "67:12:14:04 pays 'at a rate approved by the department'; no dollar figure in the rule; POMS SI DEN01415.011 (federal scope) describes the program"),
               income=("REVIEW", "2026-09-10-ssi-state-supplement", "us-sd/regulation/arsd/67/12/14/01", "no income/resource text found in the chapter beyond definitions")),
    "tx": dict(admin="S", authority=("REVIEW", "", "", "Tex. Hum. Res. Code 32 not inventoried; HHSC MEPD H-6000 is the operating text"),
               elig=("PRESENT", "2026-09-10-medicaid-state-eligibility-manual", "us-tx/manual/hhsc/medicaid/mepd-h-6000/block-1", "H-6000 Co-Payment for SSI Cases (institutionalized SSI recipients)"),
               amounts=("PRESENT", "2026-09-10-medicaid-state-eligibility-manual", "us-tx/manual/hhsc/medicaid/mepd-h-6000/block-1", "$30 reduced SSI standard supplemented to a $75 PNA (H-6000); Appendix XXXI budget chart"),
               income=("ABSENT", "", "", "n/a: institutional-only supplement; SSI rules apply")),
    "ut": dict(admin="S", authority=("EXTRACTABLE", "", "", "Utah Admin. Code R414-306-6 (adminrules.utah.gov) named in the queue and not taken"),
               elig=("PRESENT", "2026-05-27-ut-manuals-r2026-07-15-self-contained", "us-ut/manual/dws/eligibility-manual/200-program-eligibility-requirements-205-10-state-supplemental-payments-to-ssi-recipients-general-in/block-2", "DWS Eligibility Manual 205-10"),
               amounts=("PRESENT", "2026-05-27-ut-manuals-r2026-07-15-self-contained", "us-ut/manual/dws/eligibility-manual/200-program-eligibility-requirements-205-10-state-supplemental-payments-to-ssi-recipients-general-in/block-2", "rates effective 2026-01-01 ($3.91 single, $12.19/$5.75 couples)"),
               income=("ABSENT", "", "", "n/a: flat supplement to SSI recipients; SSI rules apply")),
    "va": dict(admin="S", authority=("EXTRACTABLE", "", "", "22VAC30-80 Auxiliary Grants Program (law.lis.virginia.gov, 12 sections) inventoried and not taken"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-va/manual/dars/auxiliary-grant/chapter-c/page-9", "chapter C page 9: AG covered groups (aged, blind, disabled); chapter D SSI recipients' eligibility"),
               amounts=("REVIEW", "2026-09-10-ssi-state-supplement", "us-va/manual/dars/auxiliary-grant/chapter-k/page-13", "chapter K page 13: the AG rate is set by an annual DARS rate broadcast (Fusion), not printed in the manual; chapter J page 6 shows the $82 personal needs allowance"),
               income=("REVIEW", "2026-09-10-ssi-state-supplement", "us-va/manual/dars/auxiliary-grant/chapter-g/page-13", "chapters A-L present at page granularity; the income and resource rule pages were not individually verified (chapter G resource transfers, chapter E resources)")),
    "vt": dict(admin="F", authority=("REVIEW", "", "", "33 V.S.A. 1301 et seq. not inventoried"),
               fed=(f"{P058}44", "Vermont living-arrangement definitions (block-44) and payment levels (blocks 46-47); SI BOS01415.013 and .970")),
    "wa": dict(admin="S", authority=("PRESENT", "2026-07-01-388-474-r2026-07-15-self-contained-r2026-07-17-dedup", "us-wa/regulation/388/388-474/388-474-0012", "WAC 388-474 (SSI state supplemental payment)"),
               elig=("PRESENT", "2026-07-01-388-474-r2026-07-15-self-contained-r2026-07-17-dedup", "us-wa/regulation/388/388-474/388-474-0012", "388-474-0012 who can get SSP"),
               amounts=("PRESENT", "2026-06-25-388-478-r2026-07-15-self-contained-r2026-07-17-dedup", "us-wa/regulation/388/388-478/388-478-0055", "WAC 388-478-0055 how much SSP; -0057 adjustments"),
               income=("ABSENT", "", "", "n/a: SSP paid to SSI recipients in named categories; SSI rules apply")),
    "wi": dict(admin="S", authority=("EXTRACTABLE", "", "", "Wis. Stat. 49.77 (docs.legis.wisconsin.gov) is the authority; no admin-rule chapter exists (queue); statute not taken"),
               elig=("PRESENT", "2026-09-10-ssi-state-supplement", "us-wi/manual/dhs/ssi/ssi-admin/4-1/block-8", "SSI Administration Handbook (P-23129) and SSI-E Handbook (P-20679)"),
               amounts=("PRESENT", "2026-09-10-ssi-state-supplement", "us-wi/manual/dhs/ssi/ssi-admin/4-1/block-8", "state supplement and SSI-E amounts in the handbooks (Release 26-01)"),
               income=("ABSENT", "", "", "n/a: supplement follows SSI eligibility; SSI rules apply")),
    "wy": dict(admin="S", blocked="ecom.wyo.gov EOM M1804 is a script-rendered Google Drive embed with no addressable document URL (batch 3)",
               fed_partial=("us/manual/ssa/poms/si/den01415.013", "SI DEN01415.013 Supplementary Payments In Wyoming (regional description)")),
}
P058_PAY = {"ca": 4, "de": 8, "dc": 12, "hi": 16, "ia": 20, "mi": 24, "mt": 28, "nv": 32, "nj": 36, "pa": 40, "ri": 43, "vt": 46}
PE_SSI_STATES = {"ak", "al", "ca", "co", "ct", "dc", "de", "ga", "id", "il", "in", "ks", "ky", "ma", "me", "mi", "mn", "mo", "ne", "nm", "sc", "tx", "wa"}


def build_ssi(base: Path):
    schema = []
    m = Matrix()
    scope_st = SEL["ssi_statute"]
    held = {d["citation_path"] for d in rows(base, f"us/statute/{scope_st}")}
    # statute
    for sec, title, pe in SSI_STATUTE:
        eid = f"SSI-F-USC-{sec}"
        schema.append(elem(eid, f"42 U.S.C. {sec}: {title}", "federal", "statute (US Code Title 42 ch. 7 subch. XVI)", "Congress", pe,
                           ["42 U.S.C. 1381-1383f"], ""))
        cp = f"us/statute/42/{sec}"
        if cp in held:
            n = sum(1 for d in rows(base, f"us/statute/{scope_st}") if d["citation_path"].startswith(cp + "/") or d["citation_path"] == cp)
            m.federal(eid, "federal", "statute", "PRESENT", scope_st, cp, f"{n} rows in the Title XVI scope; subsection bodies opened (e.g. 1382/a/1)", pe)
        else:
            m.federal(eid, "federal", "statute", "EXTRACTABLE", "", "", "uscode.house.gov Title 42 ch. 7 subch. XVI (same publisher as the held 2026-06-20 Title XVI scope, which stops at 1382j)", pe)
    # regulation
    for letter, title, pe in CFR416:
        eid = f"SSI-F-CFR416-{letter}"
        schema.append(elem(eid, f"20 CFR 416 Subpart {letter}: {title}", "federal", "regulation (eCFR)", "SSA", pe, ["20 CFR part 416"], ""))
        secs = [r for r in rows(base, f"us/regulation/{SEL['cfr416']}") if r.get("kind") == "section" and (r.get("metadata") or {}).get("subpart") == letter and (r.get("body") or "").strip()]
        assert secs, letter
        m.federal(eid, "federal", "regulation", "PRESENT", SEL["cfr416"], secs[0]["citation_path"], f"subpart {letter}: {len(secs)} sections with non-empty bodies in the 2026-09-11 complete eCFR scope (cited: first section; container row us/regulation/20/416/subpart-{letter} has no body by design)", pe)
    eid = "SSI-F-CFR416-APPK"
    schema.append(elem(eid, "20 CFR 416 Appendix to Subpart K (income excluded under other federal laws)", "federal", "regulation (eCFR)", "SSA", "no", ["20 CFR part 416"], "run note 2026-09-11-federal-cfr-followon-parts: appendix not taken (adapter accepts part-scoped appendices only)"))
    m.federal(eid, "federal", "regulation", "EXTRACTABLE", "", "", "eCFR structure lists 'Appendix to Subpart K of Part 416'; not taken (adapter limitation, run note 2026-09-11)")
    # POMS
    for sub, title, n, taken in POMS_SI:
        eid = f"SSI-F-POMS-SI-{sub}"
        pe = POMS_PE.get(sub, "no")
        schema.append(elem(eid, f"POMS SI {sub}: {title}", "federal", "agency manual (SSA POMS part SI)", "SSA", pe, ["POMS SI chapter list"], f"{n} sections listed on the subchapter index"))
        if taken:
            d = find(base, f"us/manual/{SEL['poms']}", rf"^us/manual/ssa/poms/si/{sub}\.\d{{3}}/block-1$", r".{200,}")
            cp = d["citation_path"] if d else f"us/manual/ssa/poms/si/{sub}.001"
            m.federal(eid, "federal", "manual", "PRESENT", SEL["poms"], cp, f"{n}/{n} sections taken incl. regional; block bodies opened", pe)
        else:
            ch = sub[:3]
            m.federal(eid, "federal", "manual", "EXTRACTABLE", "", "", f"listed on https://secure.ssa.gov/apps10/poms.nsf/subchapterlist!openview&restricttocategory=05{ch} ({n} sections); not taken (run note 2026-09-10-ssi-poms-si, judgment 1)", pe)
    # annual figures
    ann = [
        ("SSI-F-ANN-FBR", "SSI federal benefit rate and essential-person amount for the current year (COLA notice)", "yes", f"us/guidance/{SEL['cola']}", "federal-register/block-1", r"SSI\)? monthly payment amounts for 2026", "$994 individual / $1,491 couple / $498 essential person for 2026 in 90 FR 49047"),
        ("SSI-F-ANN-SEIE", "Student earned income exclusion amounts for the current year", "yes", f"us/guidance/{SEL['cola']}", "federal-register/block-1", r"student earned income exclusion", "$2,410/month, $9,730/year for 2026"),
        ("SSI-F-ANN-SGA", "Substantial gainful activity amounts for the current year", "partial", f"us/guidance/{SEL['autodet']}", "substantial-gainful-activity/2026/block-1", r"substantial gainful", "SSA automatic determinations 2026"),
    ]
    for eid, name, pe, rel, cpsuffix, rx, note in ann:
        schema.append(elem(eid, name, "federal", "annual notice (Federal Register / SSA OACT)", "SSA", pe, ["42 U.S.C. 1382f", "20 CFR 416.405-416.415"], ""))
        d = find(base, rel, None, rx)
        assert d, eid
        m.federal(eid, "federal", "annual notice", "PRESENT", rel.split("/")[-1], d["citation_path"], note, pe)
    # state elements
    st_elems = [
        ("SSI-ST-1", "State supplementation program existence and administration (mandatory/optional; federal, state or shared administration)", "POMS SI 01415.010 state table; 20 CFR 416 subpart T", "partial"),
        ("SSI-ST-2", "State authority establishing the supplement (statute or adopted rule)", "state statute or regulation", "no"),
        ("SSI-ST-3", "State eligibility categories and living-arrangement definitions for the supplement", "state regulation/manual, or POMS SI 01415.058 for federally administered programs", "partial"),
        ("SSI-ST-4", "State supplement payment standards / amounts by living arrangement (current year)", "state regulation/manual/standards table, or POMS SI 01415.058", "partial"),
        ("SSI-ST-5", "State income and resource methodology for a state-administered supplement (disregards, limits)", "state regulation/manual", "partial"),
        ("SSI-ST-6", "Federally administered optional supplement: SSA living-arrangement codes and payment levels", "POMS SI 01415.058 state subsection and regional SI xx01415 sections", "partial"),
    ]
    for eid, name, fam, pe in st_elems:
        schema.append(elem(eid, name, "state", fam, "state legislature/agency (SSA publishes the federally administered levels)", pe, ["42 U.S.C. 1382e", "20 CFR 416 subpart T", "POMS SI 014"], ""))
    t010 = "us/manual/ssa/poms/si/01415.010/block-1"
    for s in STATES:
        info = SSI_STATES[s]
        j = f"us-{s}"
        adm = info["admin"]
        pe_s = "partial" if s in PE_SSI_STATES else "no"
        m.add(j, "SSI-ST-1", "state", "manual (POMS)", "PRESENT", SEL["poms"], t010, f"SI 01415.010 state table row: Optional = {adm}; table body opened", pe_s)
        if adm == "N":
            for e in ("SSI-ST-2", "SSI-ST-3", "SSI-ST-4", "SSI-ST-5", "SSI-ST-6"):
                m.add(j, e, "state", "n/a", "ABSENT", "", "", "n/a: no optional state supplement (POMS SI 01415.010 Optional = N); mandatory supplement, if any, is federally computed", "no")
            continue
        if "blocked" in info:
            cp, note = info["fed_partial"]
            m.add(j, "SSI-ST-2", "state", "state statute/regulation", "OUTREACH", "", "", info["blocked"], pe_s)
            m.add(j, "SSI-ST-3", "state", "state manual", "OUTREACH", "", "", info["blocked"] + f"; discovery material only: {note}", pe_s)
            m.add(j, "SSI-ST-4", "state", "state manual", "OUTREACH", "", "", info["blocked"] + f"; {note} ({cp}) is a dated regional description, not the state's current table", pe_s)
            m.add(j, "SSI-ST-5", "state", "state manual", "OUTREACH", "", "", info["blocked"], pe_s)
            m.add(j, "SSI-ST-6", "state", "n/a", "ABSENT", "", "", "n/a: state-administered program", "no")
            continue
        st, sc, cp, note = info["authority"]
        m.add(j, "SSI-ST-2", "state", "state statute/regulation", st, sc, cp, note, pe_s)
        if "fed" in info:
            cp, note = info["fed"]
            fs = info.get("fs_note", "")
            m.add(j, "SSI-ST-3", "state", "manual (POMS)", "PRESENT", SEL["poms"], cp, note + ("; " + fs if fs else ""), pe_s)
            paycp = f"us/manual/ssa/poms/si/01415.058/block-{P058_PAY[s]}"
            m.add(j, "SSI-ST-4", "state", "manual (POMS)", "PRESENT", SEL["poms"], paycp, "January 2026 recipient payment levels by living-arrangement code (SI 01415.058, TN 95; couple levels in the next block); " + (fs if fs else "SSA-administered"), pe_s)
            if fs:
                m.add(j, "SSI-ST-5", "state", "state regulation/manual", "REVIEW", "", "", fs + "; SSA rules apply to the federally administered part", pe_s)
            else:
                m.add(j, "SSI-ST-5", "state", "n/a", "ABSENT", "", "", "n/a: federally administered; SSI income/resource rules apply (20 CFR 416 subparts K-L)", "no")
            m.add(j, "SSI-ST-6", "state", "manual (POMS)", "PRESENT", SEL["poms"], cp, note, pe_s)
            continue
        for e, key in (("SSI-ST-3", "elig"), ("SSI-ST-4", "amounts"), ("SSI-ST-5", "income")):
            st, sc, cp, note = info[key]
            fam = "n/a" if st == "ABSENT" else "state regulation/manual"
            m.add(j, e, "state", fam, st, sc, cp, note, pe_s)
        m.add(j, "SSI-ST-6", "state", "n/a", "ABSENT", "", "", "n/a: state-administered program (not in SI 01415.058A)", "no")
    finish(m, schema)
    return schema, m


# ----------------------------------------------------------------------------
# LIHEAP
# ----------------------------------------------------------------------------

LIHEAP_STATUTE = [
    ("8621", "Findings and purpose"), ("8622", "Definitions (home energy, household, State, poverty level, SMI)"),
    ("8623", "Authorization of appropriations; leveraging and REACH set-asides"),
    ("8624", "Applications and requirements: allotment uses, the 16 assurances incl. income eligibility ceiling (150% poverty / 60% SMI, floor 110% poverty), outreach, priority to highest need, hearings, plan contents (2605(c))"),
    ("8625", "Administration (Secretary's duties)"), ("8626", "Payments to States; carryover limits"),
    ("8627", "Withholding of funds"), ("8628", "Technical assistance and training"),
    ("8629", "Reports, data collection and evaluation"), ("8630", "Incentive program for leveraging non-federal resources"),
]
LIHEAP_CFR = [
    ("96.80", "Scope of subpart H"), ("96.81", "Carryover and reallotment"), ("96.82", "Required report on households assisted"),
    ("96.83", "Increase in maximum amount that may be used for weatherization"), ("96.84", "Miscellaneous (income eligibility definitions, nominal payments, categorical eligibility)"),
    ("96.85", "Income eligibility (poverty guidelines and SMI; household definition)"), ("96.86", "Exemption from requirement for additional outreach and intake services"),
    ("96.87", "Leveraging incentive program"), ("96.88", "Administrative costs"), ("96.89", "Exemptions from requirements in the Human Services Reauthorization Act of 1994"),
]
LIHEAP_MANUALS = {  # clearinghouse "State LIHEAP Policy Manuals" links read 2026-09-11 (liheapch.acf.gov/stateplans.htm)
    "al": "https://adeca.alabama.gov/wp-content/uploads/LIHEAP-Manual.pdf", "ak": "http://dpaweb.hss.state.ak.us/manuals/HAP/hap.htm",
    "az": "https://des.az.gov/sites/default/files/dl/CCSD-LIHEAP-Policy.pdf", "ar": "https://liheapch.acf.gov/sites/default/files/webfiles/docs/2026/manuals/AR_Manual_2026.pdf",
    "co": "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=7308&fileName=9%20CCR%202503-7", "ct": "https://portal.ct.gov/-/media/departments-and-agencies/dss/winter-heating-assistance/as-appoved-ffy-2025-liheap-allocation-plan.pdf",
    "de": "https://bidcondocs.delaware.gov/HSS/HSS_15027Liheap_MAN.pdf", "fl": "https://liheapch.acf.gov/sites/default/files/webfiles/docs/2023/manuals/FL_PolicyManual_2023.pdf",
    "ga": "https://liheapch.acf.gov/sites/default/files/webfiles/docs/2023/manuals/GA_PolicyManual_2023.pdf", "hi": "https://humanservices.hawaii.gov/wp-content/uploads/2019/07/Policies-and-Procedures-2020.pdf",
    "in": "https://www.in.gov/ihcda/files/Indiana-LIHEAP-Intake-and-Operations-Program-Manual-PY2024-version-1.0.pdf", "ia": "https://hhs.iowa.gov/media/2702/download?inline=",
    "ks": "https://content.dcf.ks.gov/EES/KEESM/Keesm.htm", "ky": "https://www.kyhousing.org/Partners/Developers/Single-Family/Weatherization-Assistance/Documents/2022%20Kentucky%20Health%20and%20Safety%20Plan.pdf",
    "la": "https://www.lhc.la.gov/hubfs/Document%20Libraries/Energy%20Assistance/Louisiana%20LIHEAP%20Service%20Delivery%20Guide%20-%20REVISED%20February%201%2c%202022.pdf",
    "me": "https://www.mainehousing.org/docs/default-source/msha-rules/ch24-home-energy-assistance-program-rule.pdf", "md": "https://dhs.maryland.gov/documents/OHEP/2021%20Operations%20Manual%20Final.pdf",
    "mi": "https://www.michigan.gov/mpsc/-/media/Project/Websites/mpsc/consumer/meap/2024/2024_MEAP_Policy_Manual.pdf", "mn": "https://mn.gov/commerce-stat/pdfs/eap/providers/2024/FINAL-FFY24-EAP-Policy-Manual.pdf",
    "ms": "https://www.sos.ms.gov/adminsearch/ACCode/00000693c.pdf", "mo": "https://mydss.mo.gov/media/pdf/liheap-manual", "mt": "https://dphhs.mt.gov/assets/hcsd/liheap/LIHEAPmanual.pdf",
    "ne": "https://dhhs.ne.gov/Guidance%20Docs/Low%20Income%20Home%20Energy%20Assistance%20Program%20(LIHEAP)%20Guidance%20Document.pdf", "nv": "https://dwss.nv.gov/uploadedFiles/dwssnvgov/content/Energy/FY%202024%20EAP%20Manual.pdf",
    "nh": "https://www.energy.nh.gov/sites/g/files/ehbemt551/files/inline-documents/sonh/fuel-assistance-program-procedures-manual.pdf", "nj": "https://www.nj.gov/dca/dhcr/offices/docs/FY2026%20LIHEAP%20Handbook%20.pdf",
    "ny": "http://otda.ny.gov/programs/heap/HEAP-manual.pdf", "nd": "https://www.nd.gov/dhs/policymanuals/415/MLs/ML%203750%2010.1.2023.%20Full.pdf",
    "oh": "https://irp.cdn-website.com/aa88b0b1/files/uploaded/2022-24%20ATTACHMENT%202022-2023%20EAP%20Guidelines%20%281%29.pdf", "or": "https://www.oregon.gov/ohcs/energy-weatherization/Documents/2022-Energy-Assistance-Manual.pdf",
    "pa": "http://services.dpw.state.pa.us/oimpolicymanuals/liheap/index.htm", "sd": "https://liheapch.acf.gov/sites/default/files/webfiles/docs/SD_Policy-and-Procedures-Manual2018.pdf",
    "tn": "https://thda.org/pdf/LIHEAP-Policy-Manual.pdf", "ut": "https://jobs.utah.gov/housing/scso/seal/documents/heatpolicymanual.pdf",
    "vt": "https://dcf.vermont.gov/esd/laws-rules/proposed/P2900 (Heating) and P3100 (Crisis)", "va": "https://www.dss.virginia.gov/files/division/bp/ea/intro_page/manual/Complete_Manual.pdf",
    "wv": "http://www.wvdhhr.org/bcf/policy/imm/new_manual/immanual/manual_pdf_files/chapter_26/ch26_2.pdf", "wi": "https://energyandhousing.wi.gov/PublishingImages/Pages/AgencyResources/energy-assistance/Program%20Year%202024%20WHEAP%20Manual%20April.pdf",
}
LIHEAP_NY_BLOCK = "otda.ny.gov answers plain clients with a connection reset and impersonated clients with a JavaScript challenge (SSI batch 1 and TANF/SNAP queues, 2026-09-10)"


def build_liheap(base: Path):
    schema = []
    m = Matrix()
    for sec, title in LIHEAP_STATUTE:
        eid = f"LIHEAP-F-USC-{sec}"
        pe = "partial" if sec == "8624" else "no"
        schema.append(elem(eid, f"42 U.S.C. {sec}: {title}", "federal", "statute (US Code Title 42 ch. 94 subch. II)", "Congress", pe, ["42 U.S.C. 8621-8630"], ""))
        m.federal(eid, "federal", "statute", "EXTRACTABLE", "", "", "no Title 42 ch. 94 section in any us/statute scope (checked all 128 files); publisher uscode.house.gov, also linked from https://acf.gov/ocs/law-regulation/liheap-statute-and-regulations (queue lead, needs_review row)", pe)
    for sec, title in LIHEAP_CFR:
        eid = f"LIHEAP-F-CFR96-{sec.replace('.', '-')}"
        pe = "partial" if sec in ("96.85",) else "no"
        schema.append(elem(eid, f"45 CFR {sec}: {title}", "federal", "regulation (eCFR, 45 CFR 96 subpart H)", "HHS/ACF", pe, ["45 CFR 96 subpart H"], ""))
        m.federal(eid, "federal", "regulation", "EXTRACTABLE", "", "", "no us/regulation/45/96 path in the corpus; eCFR Versioner API (same publisher as the 2026-09-11 part 98/436/416 scopes; adapter now sends Accept-Encoding)", pe)
    ann = [
        ("LIHEAP-F-ANN-POVERTY", "HHS poverty guidelines for the program year (income ceiling basis)", "annual notice (Federal Register, HHS/ASPE)", "yes", "no HHS poverty guidelines notice in us/guidance (only references inside other documents); Federal Register / aspe.hhs.gov"),
        ("LIHEAP-F-ANN-SMI", "State median income estimates for LIHEAP (ACF LIHEAP-IM annual SMI table)", "annual guidance (ACF OCS LIHEAP Information Memorandum)", "yes", "no SMI table in the corpus; ACF posts the annual LIHEAP IM on the OCS policy-guidance index"),
        ("LIHEAP-F-GUID-MODELPLAN", "LIHEAP Model Plan (OMB form) and ACF instructions; LIHEAP Action Transmittals / Information Memoranda", "agency guidance (ACF OCS)", "no", "not in the corpus; ACF OCS LIHEAP policy-guidance index"),
    ]
    for eid, name, fam, pe, note in ann:
        schema.append(elem(eid, name, "federal", fam, "HHS", pe, ["42 U.S.C. 8624(b)(2)", "45 CFR 96.85"], ""))
        m.federal(eid, "federal", fam.split(" (")[0], "EXTRACTABLE", "", "", note, pe)

    st_elems = [
        ("LIHEAP-ST-01", "Program components operated and dates of operation (plan section 1.1)", "state plan", "partial"),
        ("LIHEAP-ST-02", "Funding allocation by component, carryover, admin and Assurance 16 shares (1.2-1.3)", "state plan", "no"),
        ("LIHEAP-ST-03", "Categorical eligibility policy and automatic enrollment (1.4-1.6)", "state plan (yes/no boxes) + policy manual", "partial"),
        ("LIHEAP-ST-04", "SNAP nominal payment policy and amount (1.7)", "state plan", "no"),
        ("LIHEAP-ST-05", "Countable income (gross/net, income types) and household definition (1.8-1.12)", "state plan (check boxes) + policy manual", "partial"),
        ("LIHEAP-ST-06", "Heating: income eligibility threshold by household size (2.1)", "state plan", "partial"),
        ("LIHEAP-ST-07", "Heating: additional eligibility rules and priority for vulnerable households (2.2-2.4)", "state plan", "no"),
        ("LIHEAP-ST-08", "Heating: benefit determination variables, minimum and maximum benefit (2.5-2.6)", "state plan", "partial"),
        ("LIHEAP-ST-09", "Heating/cooling benefit matrix (plan attachment)", "plan attachment / state policy manual", "partial"),
        ("LIHEAP-ST-10", "Cooling: threshold, eligibility, benefit levels (section 3)", "state plan", "no"),
        ("LIHEAP-ST-11", "Crisis: threshold, crisis definition, life-threatening definition, response times (4.1-4.5)", "state plan", "partial"),
        ("LIHEAP-ST-12", "Crisis: additional eligibility and benefit levels / maximum crisis benefit (4.6-4.x)", "state plan", "partial"),
        ("LIHEAP-ST-13", "Weatherization component rules (section 5)", "state plan", "no"),
        ("LIHEAP-ST-14", "Outreach, coordination, agency designation, energy-supplier agreements (6-9)", "state plan", "no"),
        ("LIHEAP-ST-15", "Fair hearings (12)", "state plan", "no"),
        ("LIHEAP-ST-16", "Assurance 16 services, leveraging, training, performance measures (13-16)", "state plan", "no"),
        ("LIHEAP-ST-17", "Monitoring, audit and program integrity (10, 17)", "state plan", "no"),
        ("LIHEAP-ST-18", "State LIHEAP policy/operations manual (application procedures, matrices, vendor rules)", "state policy manual or adopted rule", "partial"),
    ]
    for eid, name, fam, pe in st_elems:
        schema.append(elem(eid, name, "state", fam, "state grantee (plan approved by HHS)", pe, ["42 U.S.C. 8624(b)-(c)", "LIHEAP Detailed Model Plan sections 1-20"], ""))
    thr = re.compile(r"(HHS Poverty Guidelines|State Median Income)\s*(\d{2,3}\.\d\d)\s*%", re.I)
    mm = re.compile(r"Minimum Benefit\s*\$?\s*([\d,\.]+)\s*Maximum Benefit\s*\$?\s*([\d,\.]+)", re.I)
    hrs = re.compile(r"(\d{1,3})\s*Hours", re.I)
    nom = re.compile(r"Amount of Nominal Assistance:\s*\$\s*([\d\.]+)", re.I)
    pe_states = {"dc", "il", "ma", "tx"}
    for s in STATES:
        j = f"us-{s}"
        scope = "2026-09-10"
        secs = {}
        for d in rows(base, f"{j}/policy/{scope}"):
            secs[d["citation_path"].split("/")[-1]] = d
        root = f"{j}/policy/acf/liheap-plan/fy2026"
        def cp(n):
            return f"{root}/{n}"
        def body(n):
            return (secs[str(n)].get("body") or "") if str(n) in secs else ""
        pe_s = "partial" if s in pe_states else "no"
        s1, s2, s3, s4 = body(1), body(2), body(3), body(4)
        heat = bool(re.search(r"Heating assistance\s+\d{2}/\d{2}/\d{4}", s1))
        cool = bool(re.search(r"Cooling assistance\s+\d{2}/\d{2}/\d{4}", s1))
        m.add(j, "LIHEAP-ST-01", "state", "state plan", "PRESENT", scope, cp(1), f"section 1.1 dates of operation opened (heating={'yes' if heat else 'no'}, cooling={'yes' if cool else 'no'})", pe_s)
        m.add(j, "LIHEAP-ST-02", "state", "state plan", "PRESENT", scope, cp(1), "section 1.2 allocation percentages in body", "no")
        cat = re.search(r"1\.4a\..*?Please explain.*?application process\.\s*(.*?)\s*1\.5 Do you automatically", s1, re.S)
        cat_txt = cat.group(1).strip() if cat else ""
        if len(cat_txt) > 40:
            m.add(j, "LIHEAP-ST-03", "state", "state plan", "PRESENT", scope, cp(1), f"1.4a definition text present ({len(cat_txt)} chars); the yes/no boxes of 1.4-1.6 are not captured in the extracted text (no checkbox glyphs)", pe_s)
        else:
            m.add(j, "LIHEAP-ST-03", "state", "state plan", "REVIEW", scope, cp(1), "1.4-1.6 are yes/no boxes; the extractor keeps no checkbox state and 1.4a carries no description, so the policy cannot be read from the body", pe_s)
        n = nom.search(s1)
        m.add(j, "LIHEAP-ST-04", "state", "state plan", "PRESENT", scope, cp(1), f"1.7b nominal assistance amount ${n.group(1) if n else '?'} in body" if n else "1.7 text present", "no")
        m.add(j, "LIHEAP-ST-05", "state", "state plan", "REVIEW", scope, cp(1), "1.8 (gross/net) and 1.9 (income types) are check boxes; checkbox state is not captured in the extracted text; narrative in 1.10-1.12 present", pe_s)
        th = thr.findall(s2)
        if heat and th:
            m.add(j, "LIHEAP-ST-06", "state", "state plan", "PRESENT", scope, cp(2), "2.1: " + "; ".join(f"{a} {b}%" for a, b in th[:3]), pe_s)
        elif not heat:
            m.add(j, "LIHEAP-ST-06", "state", "n/a", "ABSENT", "", "", "n/a: no heating component operated (section 1.1)", "no")
        else:
            m.add(j, "LIHEAP-ST-06", "state", "state plan", "REVIEW", scope, cp(2), "2.1 threshold not parseable from body", pe_s)
        pm = re.search(r"Older Adults \(60 years or older\)\? Yes No If yes, describe:\s*(.*?)Individuals with a disability", s2, re.S)
        pdesc = pm.group(1).strip() if pm else ""
        expl = re.search(r'Explanations of policies for each "yes" checked above:\s*(.*?)\s*Determination of Benefits', s2, re.S)
        edesc = expl.group(1).strip() if expl else ""
        p24 = re.search(r"2\.4 Describe how you prioritize.*?etc\.\s*(.*?)\s*2\.5 Check the variables", s2, re.S)
        d24 = p24.group(1).strip() if p24 else ""
        if not heat:
            m.add(j, "LIHEAP-ST-07", "state", "n/a", "ABSENT", "", "", "n/a: no heating component", "no")
        elif len(pdesc) + len(edesc) + len(d24) > 60:
            m.add(j, "LIHEAP-ST-07", "state", "state plan", "PRESENT", scope, cp(2), f"2.3/2.4 priority narrative present ({len(pdesc)+len(edesc)+len(d24)} chars); yes/no boxes not captured", "no")
        else:
            m.add(j, "LIHEAP-ST-07", "state", "state plan", "REVIEW", scope, cp(2), "2.2-2.4 are yes/no boxes with no narrative in the body; checkbox state not captured", "no")
        mx = mm.search(s2)
        if not heat:
            m.add(j, "LIHEAP-ST-08", "state", "n/a", "ABSENT", "", "", "n/a: no heating component", "no")
        elif mx:
            m.add(j, "LIHEAP-ST-08", "state", "state plan", "PRESENT", scope, cp(2), f"2.6 minimum ${mx.group(1)} / maximum ${mx.group(2)}; 2.5 variables are check boxes (state not captured) but narrative present", pe_s)
        else:
            m.add(j, "LIHEAP-ST-08", "state", "state plan", "REVIEW", scope, cp(2), "2.6 min/max not parseable", pe_s)
        # matrix attachment
        if s == "ks":
            pass
        elif s in LIHEAP_MANUALS:
            m.add(j, "LIHEAP-ST-09", "state", "plan attachment / policy manual", "EXTRACTABLE", "", "", f"the extracted plan ends at the 'Plan Attachments' list (matrix is an attachment, not in the PDF); clearinghouse lists a state policy manual: {LIHEAP_MANUALS[s]}", pe_s)
        else:
            m.add(j, "LIHEAP-ST-09", "state", "plan attachment / policy manual", "REVIEW", "", "", "matrix is a plan attachment not in the extracted PDF; the clearinghouse index lists no policy manual for this state; state agency site not inventoried", pe_s)
        if cool:
            th3 = thr.findall(s3); mx3 = mm.search(s3)
            m.add(j, "LIHEAP-ST-10", "state", "state plan", "PRESENT", scope, cp(3), f"3.1 threshold {'; '.join(f'{a} {b}%' for a, b in th3[:2]) if th3 else 'n/p'}; min/max {mx3.group(1)+'/'+mx3.group(2) if mx3 else 'n/p'}", "no")
        else:
            m.add(j, "LIHEAP-ST-10", "state", "n/a", "ABSENT", "", "", "n/a: no cooling component operated (section 1.1)", "no")
        h = hrs.findall(s4); th4 = thr.findall(s4)
        m.add(j, "LIHEAP-ST-11", "state", "state plan", "PRESENT", scope, cp(4), f"4.1 threshold {'; '.join(f'{a} {b}%' for a, b in th4[:2]) if th4 else 'n/p'}; 4.2-4.3 definitions; response hours {','.join(h[:2])}", pe_s)
        mx4 = mm.search(s4)
        cb = re.search(r"maximum (crisis )?(benefit|payment|amount)[^.]{0,120}\$\s?[\d,]+|\$\s?[\d,]{3,}", s4, re.I)
        if mx4 or cb:
            m.add(j, "LIHEAP-ST-12", "state", "state plan", "PRESENT", scope, cp(4), f"crisis benefit figures in section 4 ({'min/max '+mx4.group(1)+'/'+mx4.group(2) if mx4 else cb.group(0)[:60]})", pe_s)
        else:
            m.add(j, "LIHEAP-ST-12", "state", "state plan", "REVIEW", scope, cp(4), "no crisis benefit dollar figure found in section 4 body; yes/no boxes not captured", pe_s)
        m.add(j, "LIHEAP-ST-13", "state", "state plan", "PRESENT", scope, cp(5), f"section 5 body {len(body(5))} chars", "no")
        m.add(j, "LIHEAP-ST-14", "state", "state plan", "PRESENT", scope, cp(6), "sections 6-9 bodies present", "no")
        m.add(j, "LIHEAP-ST-15", "state", "state plan", "PRESENT", scope, cp(12), f"section 12 body {len(body(12))} chars", "no")
        m.add(j, "LIHEAP-ST-16", "state", "state plan", "PRESENT", scope, cp(13), "sections 13-16 bodies present", "no")
        m.add(j, "LIHEAP-ST-17", "state", "state plan", "PRESENT", scope, cp(17), "sections 10 and 17 bodies present", "no")
        if s == "ks":
            m.add(j, "LIHEAP-ST-09", "state", "state policy manual", "PRESENT", "2026-05-27-ks-keesm-r2026-07-15-self-contained", "us-ks/manual/dcf/keesm/keesm13000", "KEESM 13000 Low Income Energy Assistance Program (LIEAP) is in the selected KEESM scope; the clearinghouse manual link points at KEESM", pe_s)
            m.add(j, "LIHEAP-ST-18", "state", "state policy manual", "PRESENT", "2026-05-27-ks-keesm-r2026-07-15-self-contained", "us-ks/manual/dcf/keesm/keesm13000", "KEESM 13000 LIEAP (clearinghouse manual link = KEESM)", pe_s)
        elif s == "wv":
            d = find(base, "us-wv/manual/2026-07-21-wv-income-maintenance-manual", None, r"LIEAP")
            m.add(j, "LIHEAP-ST-18", "state", "state policy manual", "PRESENT", "2026-07-21-wv-income-maintenance-manual", d["citation_path"], "WV Income Maintenance Manual (integrated PDF, page granularity) carries the LIEAP chapter the clearinghouse links (chapter 26); 133 page rows mention LIEAP", pe_s)
        elif s == "ny":
            m.add(j, "LIHEAP-ST-18", "state", "state policy manual", "OUTREACH", "", "", f"clearinghouse links {LIHEAP_MANUALS['ny']}; {LIHEAP_NY_BLOCK}", pe_s)
        elif s in LIHEAP_MANUALS:
            m.add(j, "LIHEAP-ST-18", "state", "state policy manual", "EXTRACTABLE", "", "", f"clearinghouse 'State LIHEAP Policy Manuals' link (read 2026-09-11): {LIHEAP_MANUALS[s]}; not taken (run note: manuals are a separate family)", pe_s)
        else:
            m.add(j, "LIHEAP-ST-18", "state", "state policy manual", "REVIEW", "", "", "clearinghouse index lists no policy manual for this state; state agency site not inventoried in the queue", pe_s)
    finish(m, schema)
    return schema, m


# ----------------------------------------------------------------------------
# Medicare
# ----------------------------------------------------------------------------

MEDICARE_STATUTE = [
    ("426", "Entitlement to hospital insurance benefits (age 65, disability 24-month wait)", "yes", "m426"),
    ("426-1", "End stage renal disease program entitlement", "no", None),
    ("1395c", "Description of Part A program", "no", None), ("1395d", "Scope of Part A benefits (inpatient, SNF, home health, hospice)", "no", None),
    ("1395e", "Part A deductibles and coinsurance", "yes", None),
    ("1395i-2", "Voluntary Part A enrollment and premium (incl. reduced premium at 30-39 quarters)", "yes", None),
    ("1395i-2a", "Part A for qualified disabled and working individuals (QDWI premium)", "no", None),
    ("1395k", "Scope of Part B benefits", "no", None), ("1395l", "Part B payment: deductible, coinsurance", "partial", None),
    ("1395o", "Part B eligibility", "yes", None), ("1395p", "Part B enrollment periods (IEP, GEP, SEPs)", "no", None),
    ("1395q", "Part B coverage period", "no", None),
    ("1395r", "Part B premiums, hold-harmless, late enrollment penalty, income-related adjustment (IRMAA)", "yes", None),
    ("1395s", "Payment of Part B premiums", "no", None), ("1395v", "State buy-in agreements", "no", None),
    ("1395w-21", "Part C eligibility, election and enrollment", "no", None), ("1395w-22", "Part C benefits and beneficiary protections", "no", None),
    ("1395w-101", "Part D eligibility, enrollment and information", "no", None),
    ("1395w-102", "Part D prescription drug benefit (deductible, cost-sharing, out-of-pocket cap)", "no", None),
    ("1395w-113", "Part D premiums, late enrollment penalty, income-related adjustment", "yes", None),
    ("1395w-114", "Part D premium and cost-sharing subsidies for low-income individuals (LIS / Extra Help)", "no", None),
    ("1396a", "State plan requirements incl. 1396a(a)(10)(E) mandatory MSP groups (QMB, SLMB, QI, QDWI)", "yes", "medicaid_statute"),
    ("1396d", "Definitions incl. 1396d(p) QMB income/resource standards and Medicare cost-sharing, 1396d(s) QDWI", "yes", "medicaid_statute"),
    ("1396u-3", "Qualifying individuals (QI) program and federal allotments", "partial", None),
]
MEDICARE_CFR = [
    ("406", "42 CFR 406: Hospital insurance eligibility and entitlement (subparts A-D)", "partial"),
    ("407", "42 CFR 407: Supplementary medical insurance enrollment and entitlement (subparts A-D incl. state buy-in)", "partial"),
    ("408", "42 CFR 408: Premiums for SMI (subparts A-H: amounts, IRMAA, late enrollment, collection, state payment)", "yes"),
    ("423-B", "42 CFR 423 subpart B: Part D eligibility, enrollment and disenrollment", "no"),
    ("423-D", "42 CFR 423 subpart D: Part D premiums, cost-sharing, IRMAA (423.286)", "partial"),
    ("423-P", "42 CFR 423 subpart P: premium and cost-sharing subsidies for low-income individuals", "no"),
]
IOM = [
    ("100-01-1", "IOM Pub 100-01 ch.1: General program benefits and administration", "iom0101", "chapter-1", "no"),
    ("100-01-2", "IOM Pub 100-01 ch.2: Hospital insurance and SMI entitlement, enrollment periods, state buy-in", "iom0101", "chapter-2", "partial"),
    ("100-01-3", "IOM Pub 100-01 ch.3: Deductibles, coinsurance amounts and payment limitations (Part B premium 20.6)", "iom0101", "chapter-3", "partial"),
    ("100-01-4", "IOM Pub 100-01 ch.4: Physician certification and recertification", "iom0101", "chapter-4", "no"),
    ("100-01-5", "IOM Pub 100-01 ch.5: Definitions", "iom0101", "chapter-5", "no"),
    ("100-01-6", "IOM Pub 100-01 ch.6: Disclosure of information", "iom0101", "chapter-6", "no"),
    ("100-01-7", "IOM Pub 100-01 ch.7: Contractor responsibilities", "iom0101", "chapter-7", "no"),
    ("100-24-1", "IOM Pub 100-24 ch.1: State payment of Medicare premiums, program overview and policy (buy-in groups, QMB Part A)", "iom0124", "chapter-1", "partial"),
    ("100-24-2", "IOM Pub 100-24 ch.2: Data exchange processes", "iom0124", "chapter-2", "no"),
    ("100-24-3", "IOM Pub 100-24 ch.3: Data exchange", "iom0124", "chapter-3", "no"),
    ("100-24-4", "IOM Pub 100-24 ch.4: Code descriptions", "iom0124", "chapter-4", "no"),
    ("100-24-5", "IOM Pub 100-24 ch.5: Premium billing", "iom0124", "chapter-5", "no"),
    ("100-24-6", "IOM Pub 100-24 ch.6: Problem cases and resources", "iom0124", "chapter-6", "no"),
    ("100-02", "IOM Pub 100-02 Medicare Benefit Policy Manual (17 chapters: covered services, durations, exclusions)", "iom0102", "chapter-1", "no"),
    ("100-04", "IOM Pub 100-04 Medicare Claims Processing Manual (39 chapters incl. ch.30 financial liability, ch.28 Medigap/Medicaid coordination)", "iom0104", "chapter-1", "no"),
]
IOM_NOT_TAKEN = [
    ("100-18", "IOM Pub 100-18 Medicare Prescription Drug Benefit Manual (Part D eligibility, enrollment, LIS)", "whole_manual_download_only on the IOM index (queue index_inventory); not taken"),
    ("100-16", "IOM Pub 100-16 Medicare Managed Care Manual (Part C eligibility, enrollment, benefits)", "15 chapters listed on the IOM index; not taken"),
    ("100-03", "IOM Pub 100-03 National Coverage Determinations Manual", "4 chapters listed on the IOM index; not taken"),
    ("100-05", "IOM Pub 100-05 Medicare Secondary Payer Manual", "8 chapters listed on the IOM index; not taken"),
]
POMS_HI = [
    ("HI-00801", "POMS HI 00801: Hospital insurance entitlement (age, disability, ESRD)"),
    ("HI-00805", "POMS HI 00805: Supplementary medical insurance enrollment"),
    ("HI-00815", "POMS HI 00815: State buy-in"),
    ("HI-01001", "POMS HI 01001: Premium billing and collection (Part A/B premiums, penalties)"),
    ("HI-01101", "POMS HI 01101: Income-related monthly adjustment amount (Part B and D)"),
    ("HI-03001", "POMS HI 03001-03050: Medicare Part D Extra Help (LIS) eligibility, income and resources"),
]
MED_STATES_FIRST = {"us-mn": "manual/2026-09-10-medicaid-state-eligibility-manual"}
MED_SCOPES = {
    "ak": "manual/2026-09-10-medicaid-state-eligibility-manual", "ar": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "az": "manual/2026-09-10-medicaid-state-eligibility-manual", "co": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "ct": "manual/2026-09-10-medicaid-state-eligibility-manual", "dc": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "de": "manual/2026-09-10-medicaid-state-eligibility-manual", "fl": "manual/2026-05-27-fl-ess-manual-r2026-07-15-self-contained",
    "ga": "manual/2026-09-10-medicaid-state-eligibility-manual", "hi": "regulation/2026-09-10-medicaid-state-eligibility-manual",
    "ia": "manual/2026-09-10-medicaid-state-eligibility-manual", "id": "regulation/2026-07-04-id-aabd-rules",
    "il": "manual/2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained", "in": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "ks": "manual/2026-09-10-medicaid-state-eligibility-manual", "ky": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "la": "manual/2026-09-10-medicaid-state-eligibility-manual", "ma": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "md": "manual/2026-09-10-medicaid-state-eligibility-manual", "me": "regulation/2026-09-10-medicaid-state-eligibility-manual",
    "mi": "manual/2026-07-17-mi-bridges-manual", "mn": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "mo": "manual/2026-09-10-medicaid-state-eligibility-manual", "ms": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "mt": "manual/2026-09-10-medicaid-state-eligibility-manual", "nc": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "nd": "manual/2026-09-10-medicaid-state-eligibility-manual", "nh": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "nj": "manual/2026-09-10-medicaid-state-eligibility-manual", "nm": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "nv": "manual/2026-09-10-medicaid-state-eligibility-manual", "ny": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "oh": "manual/2026-09-10-medicaid-state-eligibility-manual", "ok": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "or": "regulation/2026-09-10-chip-state-eligibility-manual", "pa": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "ri": "manual/2026-09-10-medicaid-state-eligibility-manual", "sc": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "sd": "manual/2026-09-10-medicaid-state-eligibility-manual", "tn": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "tx": "manual/2026-09-10-medicaid-state-eligibility-manual", "ut": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "va": "manual/2026-09-10-medicaid-state-eligibility-manual", "vt": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "wa": "manual/2026-09-10-medicaid-state-eligibility-manual", "wi": "manual/2026-09-10-medicaid-state-eligibility-manual",
    "wv": "manual/2026-07-21-wv-income-maintenance-manual", "wy": "manual/2026-05-27-wy-manuals-r2026-07-15-self-contained",
}
MED_BLOCKED = {
    "al": "medicaid.alabama.gov does not answer TCP / times out to plain and impersonated clients (Medicaid queue, retried from a US network 2026-09-10); no Medicaid eligibility manual scope selected",
    "ca": "DHCS Medi-Cal Eligibility Procedures Manual index answers HTTP 403 (Imperva) to every client profile (Medicaid queue, retried 2026-09-10); no Medicaid eligibility manual scope selected",
    "ne": "rules.nebraska.gov chapter API for 477 NAC (Medicaid eligibility) blocked on 2026-09-11 (Medicaid queue batch 5); no Medicaid eligibility scope selected",
}
MED_REVIEW = {
    "wy": "Medicaid queue needs_review: the WDH Eligibility Online Manual (ecom.wyo.gov, Google Sites) was inventoried (107 policy pages, 17 tables) but not extracted; the selected WY scope is the SNAP/POWER manual, which has no MSP text",
    "or": "the selected Oregon scope is OAR 410-200 (CHIP/Medicaid MAGI rules, 41 rules) which carries no MSP standard; Oregon's MSP rules sit in OAR chapter 461 / 410-200-0435-0440 region, not taken (OARD, HTTP 200 on 2026-09-10)",
}
MED_OVERRIDE = {  # hand-reviewed cells (2026-09-12): the keyword scan's first hit was wrong or a better carrier row was read
    ("la", "MED-ST-2"): ("PRESENT", "us-la/manual/ldh/medicaid/h-1100/page-1", "hand-reviewed: H-1100 QMB requirements: entitled to or enrolled in Part A; income less than or equal to 100 percent of FPL (the scan's first hit on H-100 p.2 quoted the neighbouring FOA 300% sentence); Z-200 pp.1-7 restate QMB 100% / SLMB 100-120% FPIG"),
    ("ut", "MED-ST-2"): ("PRESENT", "us-ut/manual/dhhs/medicaid/300-medicaid-programs-320-1-eligibility-for-medicare-cost-sharing/block-2", "hand-reviewed: 320-1 Eligibility for Medicare Cost-Sharing: QMB 100% FPL, SLMB 120% FPL, QI-1 135% FPL, QDWI 200% FPL, no spenddown (the scan's first hit was 435-3 retroactive-period income)"),
    ("in", "MED-ST-4"): ("PRESENT", "us-in/manual/fssa/medicaid/ihcppm-chapter-1600/page-8", "hand-reviewed: IHCPPM 1600 p.8 table: MA L (QMB) $20 general income disregard, $65 + one-half earned income disregard (the scan's first hit described MAGI categories)"),
    ("il", "MED-ST-4"): ("REVIEW", "", "hand-reviewed: the scan's hit (PM 15000 Partnership asset-protection disregard) is not an MSP disregard; the manual index lists PM 06-12-01-c Income Exemption, which should be opened"),
    ("ms", "MED-ST-4"): ("REVIEW", "", "hand-reviewed: the scan's hit is the Disabled Adult Child disregard example (ch. 400 p.20), not an MSP disregard; the MSP budgeting page should be opened"),
    ("ri", "MED-ST-4"): ("REVIEW", "", "hand-reviewed: the scan's hit is the LTSS/MAGI 5% disregard table (210-RICR-40-00-3 p.8), not an MSP disregard"),
    ("nc", "MED-ST-6"): ("REVIEW", "", "hand-reviewed: the scan's hit ('pend to meet a deductible', MA-2160 p.5) is the Medicaid deductible, not Medicare cost-sharing; MA-2130 QMB benefits should be opened"),
    ("mi", "MED-ST-6"): ("REVIEW", "", "hand-reviewed: the scan's hit is the BEM 101 program-code table; BEM 165 (MSP) should be opened for the cost-sharing payment statement"),
}
MSP_GROUP_RX = r"qualified medicare beneficiar|\bQMB\b|specified low[- ]income medicare|\bSLMB\b|qualifying individual|\bQI-?1\b|\bQI\b|medicare savings program|\bMSP\b|qualified disabled (and )?working|\bQDWI\b|medicare (premium|cost[- ]sharing) (assistance|payment|program)|medicare buy[- ]in|SSI buy-in"
MSP_RX = r"qualified medicare beneficiar|\bQMB\b|specified low[- ]income medicare|\bSLMB\b|qualifying individual|\bQI-?1\b|medicare savings program|qualified disabled (and )?working|\bQDWI\b|medicare cost[- ]sharing|medicare premium (assistance|payment)"
NUM_RX = r"(one hundred|hundred (and )?(ten|twenty|thirty[- ]five)|1\d\d\s?(%|percent|per cent)|100\s?(%|percent|per cent)|\$\s?\d[\d,]{2,})"


def build_medicare(base: Path):
    schema = []
    m = Matrix()
    for sec, title, pe, key in MEDICARE_STATUTE:
        eid = f"MED-F-USC-{sec}"
        fam = "statute (US Code Title 42 ch. 7 subch. XVIII / XIX)"
        schema.append(elem(eid, f"42 U.S.C. {sec}: {title}", "federal", fam, "Congress", pe, ["42 U.S.C. 1395 et seq.", "42 U.S.C. 1396a, 1396d, 1396u-3"], ""))
        if key:
            scope = SEL[key]
            cp = f"us/statute/42/{sec}"
            n = sum(1 for d in rows(base, f"us/statute/{scope}") if d["citation_path"] == cp or d["citation_path"].startswith(cp + "/"))
            sub = {"1396a": "us/statute/42/1396a/a/10", "1396d": "us/statute/42/1396d/p"}.get(sec)
            if sub and not any(d["citation_path"] == sub for d in rows(base, f"us/statute/{scope}")):
                sub = None
            m.federal(eid, "federal", "statute", "PRESENT", scope, sub or cp, f"{n} rows; bodies opened" + (f"; MSP subsection at {sub}" if sub else ""), pe)
        else:
            m.federal(eid, "federal", "statute", "EXTRACTABLE", "", "", "no us/statute/42/1395* path in any statute scope (128 files checked; subchapter XVIII absent apart from 426); uscode.house.gov (publisher of the held Title 42 scopes)", pe)
    for code, title, pe in MEDICARE_CFR:
        eid = f"MED-F-CFR-{code}"
        schema.append(elem(eid, title, "federal", "regulation (eCFR)", "CMS", pe, ["42 CFR 406, 407, 408, 423"], ""))
        m.federal(eid, "federal", "regulation", "EXTRACTABLE", "", "", "no us/regulation/42/406|407|408|423 path in the corpus; eCFR Versioner API (adapter fixed 2026-09-11 for the compression requirement)", pe)
    eid = "MED-F-CFR-435-MSP"
    schema.append(elem(eid, "42 CFR 435 provisions used by MSP determinations (435.4 definitions, 435.601/435.725 financial methodologies, 435.914-.916 redeterminations)", "federal", "regulation (eCFR)", "CMS", "partial", ["42 CFR 435"], "part 435 is selected in full"))
    d = find(base, f"us/regulation/{SEL['cfr435']}", r"^us/regulation/42/435/4$")
    m.federal(eid, "federal", "regulation", "PRESENT", SEL["cfr435"], d["citation_path"], "part 435 complete (168 provisions); 435.4 body mentions the low-income subsidy; no MSP-specific eligibility group section exists in part 435", "partial")
    for code, title, key, ch, pe in IOM:
        eid = f"MED-F-IOM-{code}"
        schema.append(elem(eid, title, "federal", "agency manual (CMS IOM)", "CMS", pe, ["CMS Internet-Only Manuals index"], ""))
        scope = SEL[key]
        pub = code.split("-")[0] + "-" + code.split("-")[1]
        d = find(base, f"us/manual/{scope}", rf"^us/manual/cms/iom/{pub}/{ch}/[^/]+$", r".{300,}")
        nsec = sum(1 for r in rows(base, f"us/manual/{scope}") if r["citation_path"].startswith(f"us/manual/cms/iom/{pub}/{ch}/")) if code.count("-") == 2 else len(rows(base, f"us/manual/{scope}"))
        m.federal(eid, "federal", "manual", "PRESENT", scope, d["citation_path"], f"{nsec} section rows{' in the chapter' if code.count('-') == 2 else ' across the publication'}; section bodies opened", pe)
    for code, title, note in IOM_NOT_TAKEN:
        eid = f"MED-F-IOM-{code}"
        schema.append(elem(eid, title, "federal", "agency manual (CMS IOM)", "CMS", "no", ["CMS Internet-Only Manuals index"], ""))
        m.federal(eid, "federal", "manual", "EXTRACTABLE", "", "", f"https://www.cms.gov/medicare/regulations-guidance/manuals/internet-only-manuals-ioms: {note}", "no")
    for code, title in POMS_HI:
        eid = f"MED-F-POMS-{code}"
        pe = "partial" if code in ("HI-01101",) else "no"
        schema.append(elem(eid, title, "federal", "agency manual (SSA POMS part HI)", "SSA", pe, ["POMS HI chapter list"], ""))
        m.federal(eid, "federal", "manual", "EXTRACTABLE", "", "", "POMS part HI is listed at https://secure.ssa.gov/poms.nsf/chapterlist!openview&restricttocategory=06 (same publisher/extractor as the SI scope); no POMS HI section in the corpus", pe)
    ann = [
        ("MED-F-ANN-AB", "Annual Part A premium, Part A deductible/coinsurance, Part B premium/deductible and IRMAA brackets (CMS Federal Register notices / fact sheet)", "yes", "EXTRACTABLE", "", "", "no 2026 Part A/B premium notice in the corpus (grep 'Part B premium' + 2026 across us/*); CMS newsroom fact sheets are on the lead list as needs_review; Federal Register notices (CMS-8xxx-N) are the primary family"),
        ("MED-F-ANN-D", "Annual Part D base beneficiary premium, IRMAA and standard benefit parameters (CMS annual release)", "partial", "EXTRACTABLE", "", "", "not in the corpus; CMS Part D annual parameters announcement"),
        ("MED-F-ANN-LIS", "Annual Part D LIS resource limits and MSP resource standards (CMS annual LIS/MSP resource memo)", "partial", "EXTRACTABLE", "", "", "not in the corpus (PE cites SMD 10-003 and POMS SI 01715.010, neither held); CMS releases the figures annually"),
        ("MED-F-ANN-POVERTY", "HHS poverty guidelines (MSP income standards basis)", "yes", "EXTRACTABLE", "", "", "no poverty guidelines notice in the corpus; Federal Register / aspe.hhs.gov"),
    ]
    for eid, name, pe, st, sc, cp, note in ann:
        schema.append(elem(eid, name, "federal", "annual notice (Federal Register / CMS)", "CMS/HHS", pe, ["42 U.S.C. 1395e, 1395i-2, 1395r, 1395w-113, 1395w-114, 1396d(p)"], ""))
        m.federal(eid, "federal", "annual notice", st, sc, cp, note, pe)
    eid = "MED-F-GUID-CMS-AB"
    schema.append(elem(eid, "CMS 'Original Medicare (Part A and B) Eligibility and Enrollment' guidance page (IEP/GEP/SEP, premiums, IRMAA, LEP)", "federal", "agency guidance (cms.gov)", "CMS", "yes", ["cms.gov"], "encoded in rulespec-us us/policies/cms/original-medicare-part-a-b.yaml"))
    m.federal(eid, "federal", "guidance", "PRESENT", SEL["cms_ab"], "us/guidance/cms/original-medicare-part-a-b/block-11", "31 blocks; IEP, GEP, SEP, IRMAA (block-26), LEP (blocks 27-28) bodies opened", "yes")

    st_elems = [
        ("MED-ST-1", "MSP coverage groups defined in the state Medicaid rule/manual (QMB, SLMB, QI, QDWI)", "state Medicaid regulation or eligibility manual", "yes"),
        ("MED-ST-2", "MSP income standards (percent of FPL, state options above the federal floor)", "state Medicaid regulation/manual", "yes"),
        ("MED-ST-3", "MSP resource test (whether applied; limits)", "state Medicaid regulation/manual", "yes"),
        ("MED-ST-4", "MSP income methodology and state disregards ($20 general disregard, SSI methodology, state-specific disregards)", "state Medicaid regulation/manual", "partial"),
        ("MED-ST-5", "State buy-in coverage groups (Part B / Part A buy-in status per state)", "CMS IOM Pub 100-24 ch.1 (1.6-1.7) and state buy-in agreement", "no"),
        ("MED-ST-6", "State payment of Medicare cost-sharing for QMBs / balance-billing protection (state plan option)", "state Medicaid regulation/manual", "partial"),
        ("MED-ST-7", "Current-year MSP income/resource figures table (state standards chart)", "state Medicaid manual table or annual notice", "partial"),
    ]
    for eid, name, fam, pe in st_elems:
        schema.append(elem(eid, name, "state", fam, "state Medicaid agency (federal floor in 42 U.S.C. 1396d(p), 1396a(a)(10)(E))", pe, ["42 U.S.C. 1396a(a)(10)(E)", "42 U.S.C. 1396d(p)", "CMS IOM Pub 100-24"], ""))
    d16 = find(base, f"us/manual/{SEL['iom0124']}", r"^us/manual/cms/iom/100-24/chapter-1/1\.6$")
    GROUP = re.compile(MSP_GROUP_RX, re.I)
    SKIP_HEAD = re.compile(r"table of contents|contents|glossary|acronym|abbreviation|index|policy bulletin|\blog\b|transmittal|what's new|questions and answers|q ?& ?a|faq|covid|unwinding", re.I)
    CHANGELOG = re.compile(r"\b(Updated|Replaced?|Revised|Added|Removed|Deleted|Clarified)\b")
    QUAL = {
        "MED-ST-2": re.compile(r"\d{2,3}\s?(%|percent)\s?(of )?(the )?(federal poverty|FPL|FPIG|poverty)|(federal poverty|FPL|poverty (level|line|guideline))[^.]{0,80}\d{2,3}\s?(%|percent)|(poverty line|poverty level)[^.]{0,60}(family size|applicable)|income (limit|standard)s?[^.]{0,60}\$\s?\d", re.I),
        "MED-ST-3": re.compile(r"resource (limit|standard|test|maximum)|asset (limit|test|maximum|standard)|countable (resources|assets)[^.]{0,80}(exceed|limit|\$)|no (resource|asset) (test|limit)|resources[^.]{0,40}(three times|twice|\$\s?\d)|may have assets", re.I),
        "MED-ST-4": re.compile(r"disregard|SSI[- ](methodolog|related)|\$20\b|general (income )?exclusion|\$65\b", re.I),
        "MED-ST-6": re.compile(r"coinsurance|deductible|cost[- ]sharing|balance bill|crossover", re.I),
        "MED-ST-7": re.compile(r"(2025|2026)[^.]{0,160}\$\s?\d|\$\s?\d[^.]{0,160}(2025|2026)", re.I | re.S),
    }
    LABEL = {"MED-ST-2": "an FPL-percent or dollar income standard", "MED-ST-3": "a resource/asset limit or no-resource-test statement",
             "MED-ST-4": "a disregard or SSI-methodology statement", "MED-ST-6": "a coinsurance/deductible/cost-sharing payment statement",
             "MED-ST-7": "a 2025/2026-dated dollar figure"}
    PEQ = {"MED-ST-2": "yes", "MED-ST-3": "yes", "MED-ST-4": "partial", "MED-ST-6": "partial", "MED-ST-7": "partial"}
    for s in STATES:
        j = f"us-{s}"
        m.add(j, "MED-ST-5", "state", "manual (CMS IOM)", "PRESENT", SEL["iom0124"], d16["citation_path"], "Pub 100-24 ch.1 1.6 'Part B Buy-in Coverage Groups in the 50 States and DC' and 1.7 QMB Part A payment (federal family, state-by-state text; body opened)", "no")
        if s in MED_BLOCKED:
            for e in ("MED-ST-1", "MED-ST-2", "MED-ST-3", "MED-ST-4", "MED-ST-6", "MED-ST-7"):
                m.add(j, e, "state", "state Medicaid regulation/manual", "OUTREACH", "", "", MED_BLOCKED[s], "yes" if e in ("MED-ST-1", "MED-ST-2", "MED-ST-3") else "partial")
            continue
        if s in MED_REVIEW:
            for e in ("MED-ST-1", "MED-ST-2", "MED-ST-3", "MED-ST-4", "MED-ST-6", "MED-ST-7"):
                m.add(j, e, "state", "state Medicaid regulation/manual", "REVIEW", "", "", MED_REVIEW[s], "yes" if e in ("MED-ST-1", "MED-ST-2", "MED-ST-3") else "partial")
            continue
        rel = f"{j}/{MED_SCOPES[s]}"
        scope = MED_SCOPES[s].split("/")[-1]
        cands = []  # (heading names an MSP group, group mentions, row, text, matches)
        for d in rows(base, rel):
            body = d.get("body") or ""
            head = d.get("heading") or ""
            if not body.strip() or SKIP_HEAD.search(head) or re.search(r"table-of-contents|/toc|glossary|/updates/|transmittal", d["citation_path"]):
                continue
            if len(re.findall(r"\.{6,}", body)) >= 3:  # leader dots: a table-of-contents page
                continue
            if len(CHANGELOG.findall(body)) >= 8 and len(re.findall(r"\d{1,2}/\d{1,2}/\d{2,4}", body)) >= 8:  # manual change log
                continue
            if re.search(r"qna|q-and-a|faq|covid|unwinding", d["citation_path"]):
                continue
            t = head + " " + body
            gm = list(GROUP.finditer(t))
            if not gm:
                continue
            cands.append((bool(GROUP.search(head)), len(gm), d, t, gm))
        cands.sort(key=lambda c: (not c[0], -c[1]))
        st1 = [c for c in cands if (c[0] and len(c[2].get("body") or "") >= 200) or c[1] >= 3]
        if not st1:
            for e in ("MED-ST-1", "MED-ST-2", "MED-ST-3", "MED-ST-4", "MED-ST-6", "MED-ST-7"):
                m.add(j, e, "state", "state Medicaid regulation/manual", "REVIEW", scope, "", f"no row of the selected scope {rel} names an MSP group (QMB/SLMB/QI/QDWI/MSP) in its heading or three times in its body", "partial")
            continue
        hm0, n0, d0, _, _ = st1[0]
        m.add(j, "MED-ST-1", "state", "state Medicaid regulation/manual", "PRESENT", scope, d0["citation_path"], f"{len(st1)} rows name an MSP group in the heading or 3+ times in the body (TOC/glossary rows excluded); cited row {(d0.get('heading') or '')[:70]!r}, {n0} mentions, body opened", "yes")
        for e in ("MED-ST-2", "MED-ST-3", "MED-ST-4", "MED-ST-6", "MED-ST-7"):
            hit = None
            for hm, n, d, t, gm in cands:
                if e == "MED-ST-7" and not (hm or n >= 2):
                    continue
                for g in gm:
                    lo = max(0, g.start() - (150 if e != "MED-ST-7" else 100))
                    ctx = t[lo: g.end() + (250 if e != "MED-ST-7" else 160)]
                    gpos = g.start() - lo
                    qs = list(QUAL[e].finditer(ctx))
                    if qs:
                        q = min(qs, key=lambda q_: min(abs(q_.start() - gpos), abs(q_.end() - gpos)))  # the qualifier nearest the group term
                        snippet = " ".join(ctx[max(0, q.start() - 90): q.end() + 90].split())
                        hit = (d, snippet)
                        break
                if hit:
                    break
            if hit:
                d, snippet = hit
                m.add(j, e, "state", "state Medicaid regulation/manual", "PRESENT", scope, d["citation_path"], f"{LABEL[e]} within {'160' if e == 'MED-ST-7' else '250'} chars of an MSP group term in {(d.get('heading') or '')[:50]!r}: \"...{snippet}...\"", PEQ[e])
            else:
                m.add(j, e, "state", "state Medicaid regulation/manual", "REVIEW", scope, "", f"{len(cands)} MSP rows in the scope but none carries {LABEL[e]} near the group term; the figure may sit in a standards chart or appendix outside this scope", PEQ[e])
    for (s_, e_), (st_, cp_, note_) in MED_OVERRIDE.items():
        for r in m.rows:
            if r["jurisdiction"] == f"us-{s_}" and r["element"] == e_:
                r["status"], r["citation_path"], r["evidence_note"] = st_, cp_, note_
                r["scope_version"] = MED_SCOPES[s_].split("/")[-1]
    finish(m, schema)
    return schema, m


# ----------------------------------------------------------------------------

def dump_schema(program, title, schema, path: Path, sources_note, uncertainties):
    doc = OrderedDict(
        program=program, title=title, date="2026-09-11",
        method=("Law-derived: one element per statute section, CFR subpart/section, POMS/IOM subchapter or chapter, "
                "annual notice family, and state plan section / state rule family. PolicyEngine-US (policyengine_us/parameters and variables, "
                "walked 2026-09-11) and rulespec-us are cross-checks only: pe_modeled = yes/partial/no per element."),
        sources=sources_note, uncertainties=uncertainties,
        element_count=len(schema),
        policyengine_cross_check=OrderedDict(
            note="Elements the law has that PolicyEngine-US does not model (pe_modeled = no) and models only in part (partial). PolicyEngine is a cross-check, not the bar.",
            not_modeled_count=sum(1 for e in schema if e["pe_modeled"] == "no"),
            partial_count=sum(1 for e in schema if e["pe_modeled"] == "partial"),
            modeled_count=sum(1 for e in schema if e["pe_modeled"] == "yes"),
            not_modeled=[f"{e['id']}: {e['name']}" for e in schema if e["pe_modeled"] == "no"],
            partial=[f"{e['id']}: {e['name']}" for e in schema if e["pe_modeled"] == "partial"],
        ),
        rulespec_cross_check=OrderedDict(
            note="Elements with a RuleSpec encoding in rulespec-us (or rulespec-us-ca/co/ny); every other element has none.",
            encoded=[f"{e['id']}: {e['rulespec_encoded']}" for e in schema if e["rulespec_encoded"] != "no"],
        ),
        elements=[dict(e) for e in schema],
    )
    def _plain(o):
        if isinstance(o, dict):
            return {k: _plain(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_plain(v) for v in o]
        return o
    path.write_text(yaml.safe_dump(_plain(doc), sort_keys=False, allow_unicode=True, width=140))


def rollup(m: Matrix):
    by_status = Counter(r["status"] for r in m.rows)
    fed = Counter(r["status"] for r in m.rows if r["jurisdiction"] == "us")
    st_only = [r for r in m.rows if r["jurisdiction"] != "us" and r["level"] == "state"]
    st_status = Counter(r["status"] for r in st_only)
    per_jur = {}
    for r in st_only:
        per_jur.setdefault(r["jurisdiction"], Counter())[r["status"]] += 1
    gaps = Counter()
    for r in m.rows:
        if r["jurisdiction"] != "us" and r["status"] in ("EXTRACTABLE", "OUTREACH", "REVIEW") and r["evidence_note"] != "inherited from federal":
            gaps[(r["element"], r["status"])] += 1
    return by_status, fed, st_status, per_jur, gaps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="/Users/pavelmakarchuk/axiom-corpus/data/corpus")
    a = ap.parse_args()
    base = Path(a.base)
    builds = [
        ("ssi", "SSI (federal SSI and state supplements)", build_ssi,
         ["42 U.S.C. 1381-1383f (uscode.house.gov structure)", "20 CFR 416 subparts A-V (eCFR structure 2026-09-09)",
          "POMS part SI chapter/subchapter list (run note 2026-09-10-ssi-poms-si)", "POMS SI 01415.010 state table and SI 01415.058",
          "manifests/ssi-agent-queue.yaml and the three state-supplement run notes",
          "cross-check: policyengine_us/parameters/gov/ssa/ssi (25 leaves) and gov/states/*/{ssp,aabd,msa,oap,ossp,sspp,state_supplement,ssi_supplement} (23 states); rulespec-us us/statutes/42/1382*, us/policies/ssa/poms/si-01415-058, state SSP policies (AK, AL, KS, MN, DC, DE)"],
         ["Statute elements are whole sections; an encoder may need subsection-level granularity (the held scope has it).",
          "POMS regional (BOS/CHI/...) sections are folded into their national subchapter element.",
          "State element SSI-ST-5 is marked n/a where the supplement is a flat add-on that follows SSI eligibility; that reading is the analyst's, not the queue's.",
          "Mandatory (pass-along) supplements are folded into SSI-ST-1 because SSA computes them for federally administered states; states with state-administered mandatory programs (AK, AZ, CO, ...) may need a separate element."]),
        ("liheap", "LIHEAP (federal block grant and state FY2026 plans)", build_liheap,
         ["42 U.S.C. 8621-8630", "45 CFR 96 subpart H (96.80-96.89)", "LIHEAP Detailed Model Plan sections 1-20 (structure read from the extracted plans)",
          "ACF LIHEAP Clearinghouse index https://liheapch.acf.gov/stateplans.htm read 2026-09-11 (plans, policy manuals, delegation letters)",
          "manifests/liheap-agent-queue.yaml and run note 2026-09-10-liheap-state-plans-fy2026",
          "cross-check: policyengine_us gov/hhs/liheap (1 leaf: smi_limit) and gov/states/{dc,il,ma}/.../liheap, gov/states/tx/tdhca/ceap; rulespec-us has no LIHEAP encoding"],
         ["The plan's yes/no check boxes (categorical eligibility, asset test, priority groups, gross/net income, income types) are not captured by the PDF text extraction; those elements are REVIEW unless the narrative fields carry the answer.",
          "Benefit matrices and the policy manual are plan attachments that the clearinghouse PDF does not include; the matrix element is EXTRACTABLE only via the state manual link.",
          "Sections 18-20 (certifications) are not elements; Section 20 also absorbs the assurances page.",
          "Tribal and territory plans (AS, GU, MP, PR extracted) are outside the 50+DC matrix."]),
        ("medicare", "Medicare (federal Parts A, B, D and state Medicare Savings Programs)", build_medicare,
         ["42 U.S.C. 426, 1395c-1395w-114 (subchapter XVIII eligibility, premium and cost-sharing sections)", "42 U.S.C. 1396a(a)(10)(E), 1396d(p), 1396u-3",
          "42 CFR 406, 407, 408, 423 (subparts B, D, P), 435", "CMS IOM index (25 publications) and the four held publications",
          "POMS part HI chapter list", "manifests/medicare-agent-queue.yaml, run notes 2026-09-10-medicare-cms-iom-100-01/-100-24, 2026-09-11-medicare-cms-iom-100-02-100-04",
          "state MSP rules: the selected Medicaid eligibility scopes (manifests/medicaid-agent-queue.yaml)",
          "cross-check: policyengine_us gov/hhs/medicare (26 leaves incl. savings_programs) and variables; rulespec-us us/policies/cms/original-medicare-part-a-b.yaml, us/statutes/42/426, 42/1396a"],
         ["Subchapter XVIII was reduced to the eligibility/premium/cost-sharing sections; payment-system sections (1395ww etc.) are out of scope for a household encoding.",
          "Part C (Medicare Advantage) is represented by two statute sections and Pub 100-16 only.",
          "The state MSP scan is keyword-based over the selected Medicaid scopes; PRESENT for MED-ST-2/3/4/6/7 means a row was found with the term near the relevant text, not that the row was read end to end.",
          "States that set MSP standards in an annual standards chart outside the manual (many) will show MED-ST-7 as REVIEW even when the manual is complete."]),
    ]
    for prog, title, fn, sources, unc in builds:
        schema, m = fn(base)
        dump_schema(prog, title, schema, HERE / f"{prog}-schema.yaml", sources, unc)
        m.write(HERE / f"{prog}-matrix.csv")
        by_status, fed, st_status, per_jur, gaps = rollup(m)
        print(f"\n=== {prog}: {len(schema)} elements, {len(m.rows)} cells ===")
        print("all cells:", dict(by_status))
        print("federal row (us):", dict(fed))
        print("state-level cells:", dict(st_status))
        print("per-jurisdiction state-level:")
        for j in sorted(per_jur):
            print("  ", j, dict(per_jur[j]))
        print("top gaps (element,status): count")
        for (e, s), n in gaps.most_common(25):
            print("  ", e, s, n)


if __name__ == "__main__":
    main()
