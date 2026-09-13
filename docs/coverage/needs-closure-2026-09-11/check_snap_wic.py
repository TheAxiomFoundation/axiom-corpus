#!/usr/bin/env python3
"""Needs-driven closure check for SNAP and WIC over the 50 states plus DC (2026-09-11 pass).

Re-run (read-only over data/corpus; writes only into --out):

    python3 docs/coverage/needs-closure-2026-09-11/check_snap_wic.py \
        --corpus /Users/pavelmakarchuk/axiom-corpus/data/corpus \
        --selector docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json \
        --queues manifests \
        --rulespec /Users/pavelmakarchuk/rulespec-us \
        --out docs/coverage/needs-closure-2026-09-11

Outputs per program: <program>-schema.yaml, <program>-matrix.csv, <program>-summary.json and a
<program>-hits.jsonl (every PRESENT match with its snippet, for spot checks).

The schema is law-derived: every 7 USC ch. 51 section (plus the rule-carrying subsections of 2012,
2014, 2015, 2017, 2020 and 2025(h)), every 7 CFR 271-285 section (from the eCFR structure API,
`cfr_structure.py`) plus paragraph-level elements of 7 CFR 273, every 7 CFR 246 section plus the
participant-facing paragraphs of 246.7, 246.10 and 246.12, 42 USC 1786 subsection by subsection,
the FNS/FNA guidance families, and the state rulebook families (manual/regulation text, annual
tables and transmittals, state plans, state statute). PolicyEngine and rulespec-us are recorded per
element as cross-check flags only (pe_modeled, rulespec_scoped); neither defines the bar.

Status vocabulary (one row per jurisdiction x element):
  PRESENT      a provision body in a selected scope carries the element (scope_version,
               citation_path and a matched snippet are cited in evidence_note)
  INHERITED    federal-level element; the state row inherits the `us` row's status (recorded once)
  EXTRACTABLE  the publisher lists the carrying family and it was not taken (family and index named)
  ABSENT       the publisher posts nothing carrying it (evidence_note says what was checked)
  OUTREACH     the queue row records a publisher block
  REVIEW       could not be determined from corpus + queue evidence
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfr_structure import CFR_STRUCTURE  # noqa: E402

STATES = [
    "us-al", "us-ak", "us-az", "us-ar", "us-ca", "us-co", "us-ct", "us-de", "us-dc", "us-fl",
    "us-ga", "us-hi", "us-id", "us-il", "us-in", "us-ia", "us-ks", "us-ky", "us-la", "us-me",
    "us-md", "us-ma", "us-mi", "us-mn", "us-ms", "us-mo", "us-mt", "us-ne", "us-nv", "us-nh",
    "us-nj", "us-nm", "us-ny", "us-nc", "us-nd", "us-oh", "us-ok", "us-or", "us-pa", "us-ri",
    "us-sc", "us-sd", "us-tn", "us-tx", "us-ut", "us-vt", "us-va", "us-wa", "us-wv", "us-wi",
    "us-wy",
]
JURISDICTIONS = ["us"] + STATES

# SNAP superseding scopes on disk (docs/ingest-runs/2026-09-11-snap-superseding-scopes-batch-{1,2}.md
# on branches discovery/ingest-snap-superseding-{1,2}); treated as replacing their released versions.
SUPERSEDING = {
    "us-ar": ("manual", "2026-09-11-ar-snap-manual-supersede", "2026-07-16-ar-snap-manual"),
    "us-ga": ("manual", "2026-09-11-ga-snap-manual-supersede", "2026-05-27-ga-snap-manual-r2026-07-15-self-contained"),
    "us-ky": ("manual", "2026-09-11-ky-snap-manual-supersede", "2026-07-17-ky-snap-manual"),
    "us-me": ("regulation", "2026-09-11-me-snap-manual-supersede", "2026-07-17-me-snap-rules"),
    "us-mi": ("manual", "2026-09-11-mi-snap-manual-supersede", "2026-07-17-mi-bridges-manual"),
    "us-nc": ("manual", "2026-09-11-nc-snap-manual-supersede", "2026-05-27-nc-fns-manuals-r2026-07-15-self-contained"),
    "us-nd": ("manual", "2026-09-11-nd-snap-manual-supersede", "2026-07-21-nd-snap-manual"),
    "us-ne": ("regulation", "2026-09-11-ne-snap-manual-supersede", "2026-07-17-ne-snap-rules"),
    "us-nv": ("manual", "2026-09-11-nv-snap-manual-supersede", "2026-05-27-nv-eligibility-payments-manual-r2026-07-15-self-contained"),
    "us-ok": ("policy", "2026-09-11-ok-snap-manual-supersede", "2026-07-21-ok-snap-policy"),
    "us-tn": ("manual", "2026-09-11-tn-snap-manual-supersede", "2026-05-27-tn-snap-policies-r2026-07-15-self-contained"),
    "us-wy": ("manual", "2026-09-11-wy-snap-manual-supersede", "2026-05-27-wy-manuals-r2026-07-15-self-contained"),
}

# Which selected state scopes are the SNAP rulebook (manual / regulation / policy / SNAP guidance).
SNAP_SCOPE_RE = re.compile(
    r"snap|calfresh|foodshare|3squares|fns-manuals|bridges|keesm|combined-manual|cash-snap|"
    r"eligibility-payments|programs-eligibility-notebook|eaz-manual|income-maintenance|"
    r"tx-manuals|ut-manuals|wy-manuals|poe-manual|ess-manual|he-w-700|388-4|dta-regulations|"
    r"fia-snap|bbce|acin|10-ccr-2506|agency-5101-4|co-snap|ok-snap|food-stamp|faa5|faa6|"
    r"^2026-05-29|ma-dta-snap-cola|healthy-choices|hi-snap",
    re.I,
)
OTHER_PROGRAM_RE = re.compile(r"medicaid|chip|ccdf|tanf|ssi-state|wic|tax|pit-|income-tax|liheap|tafdc|capi|calworks", re.I)


def load_selector(path):
    d = json.load(open(path))
    return [(s["jurisdiction"], s["document_class"], s["version"]) for s in d["scopes"]]


def effective_scopes(selector):
    eff = []
    for j, dc, v in selector:
        if j not in JURISDICTIONS:
            continue
        if j in SUPERSEDING and v == SUPERSEDING[j][2]:
            continue
        eff.append((j, dc, v))
    for j, (dc, v, _old) in SUPERSEDING.items():
        eff.append((j, dc, v))
    return eff


def snap_scopes_for(j, eff):
    out = []
    for jj, dc, v in eff:
        if jj != j:
            continue
        if j == "us":
            if dc == "statute" and "title-7-consolidated" in v:
                out.append((dc, v))
            elif dc == "regulation" and ("7-cfr-273" in v or "title-7-part-275" in v or v == "2026-07-13-recovery-r2026-07-17-dedup"):
                out.append((dc, v))
            elif dc == "guidance" and ("snap" in v or v == "2026-07-13-recovery"):
                out.append((dc, v))
            continue
        if dc not in ("manual", "regulation", "policy", "guidance"):
            continue
        if dc == "policy" and v == "2026-09-10":  # LIHEAP state plans
            continue
        if OTHER_PROGRAM_RE.search(v):
            continue
        if SNAP_SCOPE_RE.search(v):
            out.append((dc, v))
        elif dc == "manual" and v.startswith("2026-07-13-recovery"):
            out.append((dc, v))  # page captures of the released SNAP manual scopes
        elif dc == "regulation" and v.startswith("2026-07-13-recovery") and j not in ("us-nj", "us-mt", "us-co"):
            out.append((dc, v))  # us-nj recovery = NJAC 10:90 (WFNJ); us-mt = ARM 37.78; us-co = consolidated TANF
    return sorted(set(out))


def wic_scopes_for(j, eff):
    out = []
    for jj, dc, v in eff:
        if jj != j:
            continue
        if j == "us" and ((dc == "guidance" and "wic" in v) or (dc == "regulation" and v == "2026-07-13-recovery-r2026-07-17-dedup")):
            out.append((dc, v))
        elif j != "us" and "wic-state-policy-manual" in v:
            out.append((dc, v))
    return sorted(set(out))


def load_rows(corpus: Path, j, dc, v):
    p = corpus / "provisions" / j / dc / f"{v}.jsonl"
    if not p.exists():
        return []
    with open(p) as fh:
        return [json.loads(line) for line in fh]


# ---------------------------------------------------------------------------
# Federal statute elements (7 USC ch. 51). Sections plus rule-carrying subsections.
# ---------------------------------------------------------------------------
USC7_SECTIONS = [
    ("2011", "Congressional declaration of policy"), ("2012", "Definitions"),
    ("2012a", "Publicly operated community health centers"),
    ("2013", "Establishment of supplemental nutrition assistance program"),
    ("2014", "Eligible households"), ("2014a", "Notice of change in State of residence of certified household"),
    ("2015", "Eligibility disqualifications"), ("2016", "Issuance and use of program benefits"),
    ("2016a", "EBT benefit fraud prevention"), ("2017", "Value of allotment"),
    ("2018", "Approval of retail food stores and wholesale food concerns"),
    ("2019", "Redemption of program benefits"), ("2020", "Administration"),
    ("2021", "Civil penalties and disqualification of retail food stores and wholesale food concerns"),
    ("2022", "Disposition of claims"), ("2023", "Administrative and judicial review; restoration of rights"),
    ("2024", "Violations and enforcement"), ("2025", "Administrative cost-sharing and quality control"),
    ("2026", "Research, demonstration, and evaluations"), ("2026a", "Healthy fluid milk incentives projects"),
    ("2027", "Appropriations and allotments"), ("2028", "Consolidated block grants for Puerto Rico and American Samoa"),
    ("2029", "Workfare"), ("2031", "Minnesota Family Investment Project"),
    ("2032", "Automated data processing and information retrieval systems"),
    ("2034", "Assistance for community food projects"), ("2035", "Simplified supplemental nutrition assistance program"),
    ("2036", "Availability of commodities for emergency food assistance program"),
    ("2036a", "Nutrition education and obesity prevention grant program"),
    ("2036b", "Retail food store and recipient trafficking"),
    ("2036c", "Annual State report on verification of SNAP participation"),
    ("2036d", "Pilot projects to encourage the use of public-private partnerships committed to addressing food insecurity"),
]
# 7 USC 2030 and 2033 are repealed (container rows only) and are noted in the schema, not elements.

# (section, subsection, heading, level, pe_modeled)
USC7_SUBSECTIONS = [
    ("2012", "j", "Definition of elderly or disabled member (age 60; SSI, SSDI, VA, RR disability)", "federal_only", "yes (has_snap_elderly_disabled_member)"),
    ("2012", "k", "Definition of food; State restaurant meals option for elderly, disabled, homeless", "federal_with_state_option", "no"),
    ("2012", "m", "Definition of household; purchase-and-prepare; separate households (m)(4) state option for institution residents", "federal_only", "partial (snap_unit)"),
    ("2012", "o", "Definition of retail food store", "federal_only", "no"),
    ("2012", "r", "Definition of State agency", "federal_only", "no"),
    ("2012", "u", "Thrifty Food Plan: definition, re-evaluation limits and regional adjustments (AK/HI/GU/VI)", "federal_only", "yes (max_allotment by region; uprating)"),
    ("2014", "a", "Income and resources as substantial limiting factors; categorical eligibility for TANF/SSI/GA households", "federal_with_state_option", "yes (categorical_eligibility)"),
    ("2014", "b", "Eligibility standards; uniform national standards", "federal_only", "no"),
    ("2014", "c", "Gross income standard: 130 percent of poverty; elderly/disabled exemption", "federal_only", "yes (income/limit/gross)"),
    ("2014", "d", "Exclusions from income (every enumerated exclusion; child support pass-through, education, (d)(7) child earned income under 18)", "federal_with_state_option", "partial (income/sources; child_income_exclusion_age)"),
    ("2014", "e", "Deductions from income: standard (e)(1), earned income 20% (e)(2), dependent care (e)(3), homeless shelter (e)(4)?, medical (e)(5), shelter cap and SUA (e)(6), child support (e)(4)", "federal_with_state_option", "yes (income/deductions/*)"),
    ("2014", "f", "Calculation of household income; prospective or retrospective accounting; simplified reporting", "federal_with_state_option", "no"),
    ("2014", "g", "Allowable financial resources: $2,000/$3,000 base (indexed), vehicle rules, TANF/Medicaid substitution, state option", "federal_with_state_option", "partial (asset_test/limit; vehicles not modeled)"),
    ("2014", "h", "Temporary emergency (disaster) standards of eligibility", "federal_only", "no"),
    ("2014", "i", "Attribution of income and resources of sponsors to sponsored aliens (deeming)", "federal_only", "no"),
    ("2014", "j", "Resource exemption for otherwise exempt (categorically eligible) households", "federal_only", "partial (categorical_eligibility)"),
    ("2014", "k", "Assistance to third parties (vendor payments) counted or excluded", "federal_only", "no"),
    ("2014", "l", "Earnings of on-the-job training participants under 19", "federal_only", "no"),
    ("2014", "m", "Simplified calculation of income for the self-employed (state option)", "federal_with_state_option", "yes (deductions/self_employment)"),
    ("2014", "n", "State options to simplify determination of child support payments", "federal_with_state_option", "partial (deductions/child_support)"),
    ("2015", "a", "Additional conditions rendering individuals ineligible", "federal_only", "no"),
    ("2015", "b", "Fraud and misrepresentation: IPV disqualification periods 12 months / 24 months / permanent", "federal_only", "no"),
    ("2015", "c", "Refusal to provide necessary information; SSN", "federal_only", "no"),
    ("2015", "d", "Conditions of participation: work registration, exemptions (age, child under 6, etc.), sanctions, E&T, voluntary quit", "federal_with_state_option", "partial (work_requirements/general)"),
    ("2015", "e", "Students: ineligibility of higher-education students and exceptions", "federal_only", "yes (student/*)"),
    ("2015", "f", "Aliens: eligible non-citizen categories (as amended by P.L. 119-21)", "federal_only", "yes (eligible_immigration_statuses)"),
    ("2015", "g", "Residents of States providing SSI state supplementary payments (cash-out)", "federal_with_state_option", "no"),
    ("2015", "h", "Transfer of assets to qualify", "federal_only", "no"),
    ("2015", "i", "Comparable treatment for disqualification under other programs", "federal_with_state_option", "no"),
    ("2015", "j", "Disqualification for receipt of multiple benefits", "federal_only", "no"),
    ("2015", "k", "Disqualification of fleeing felons and probation/parole violators", "federal_only", "no"),
    ("2015", "l", "Custodial parent cooperation with child support agency (state option)", "federal_with_state_option", "no"),
    ("2015", "m", "Noncustodial parent cooperation with child support agency (state option)", "federal_with_state_option", "no"),
    ("2015", "n", "Disqualification for child support arrears (state option)", "federal_with_state_option", "no"),
    ("2015", "o", "Work requirement (ABAWD): 3 months in 36; age range (18-64 after P.L. 119-21); exceptions; waivers at 10% unemployment; discretionary exemptions; good-faith AK/HI", "federal_with_state_option", "yes (work_requirements/abawd/*)"),
    ("2015", "p", "Disqualification for destroying food to obtain cash", "federal_only", "no"),
    ("2015", "q", "Disqualification for sale of food purchased with benefits", "federal_only", "no"),
    ("2015", "r", "Disqualification for certain convicted felons (murder, sexual assault)", "federal_only", "no"),
    ("2015", "s", "Ineligibility due to substantial lottery or gambling winnings", "federal_only", "no"),
    ("2017", "a", "Allotment calculation: TFP cost less 30 percent of net income; minimum benefit 8 percent of TFP for 1-2 person households", "federal_only", "yes (max_allotment, min_allotment, expected_contribution)"),
    ("2017", "b", "Benefits not deemed income or resources", "federal_only", "no"),
    ("2017", "c", "First month benefits prorated; $10 minimum initial allotment", "federal_only", "partial (proration)"),
    ("2017", "d", "Reduction of public assistance benefits does not increase SNAP", "federal_only", "no"),
    ("2017", "e", "Allotments for residents of drug and alcohol treatment centers", "federal_only", "no"),
    ("2017", "f", "Alternative procedures for residents of group facilities", "federal_only", "no"),
    ("2020", "e", "Requisites of State plan of operation: application processing, expedited service, interviews, certification periods, verification, hearings, SUA and other elections", "federal_with_state_option", "no"),
    ("2020", "i", "Application and denial procedures; combined application projects", "federal_with_state_option", "no"),
    ("2020", "s", "Transitional benefits option (state election)", "federal_with_state_option", "no"),
    ("2025", "h", "Funding of employment and training programs; E&T state plan", "federal_with_state_option", "no"),
]

# ---------------------------------------------------------------------------
# 7 CFR 273 paragraph-level elements (checked by keyword over the section body, because the
# selected 273 scopes are section-granular). (id_suffix, section, label, level, regex, pe)
# ---------------------------------------------------------------------------
CFR273_PARAGRAPHS = [
    ("1a", "273.1", "273.1(a) Household definition (purchase and prepare together)", "federal_only", r"purchase food and prepare meals|purchases? food and prepares?", "partial (snap_unit)"),
    ("1b", "273.1", "273.1(b) Special household requirements (spouses, children under 22, boarders, institutions)", "federal_only", r"\bboarder|under 22 years|children under 22", "partial (snap_unit)"),
    ("2e", "273.2", "273.2(e) Interview requirements and telephone-interview waiver", "federal_with_state_option", r"telephone interview|face-to-face interview", "no"),
    ("2f", "273.2", "273.2(f) Verification requirements (mandatory and optional)", "federal_with_state_option", r"verif(y|ication) (of|prior to certification)", "no"),
    ("2g", "273.2", "273.2(g) Normal processing standard (30 days)", "federal_only", r"30 days following the date the application was filed|within 30 days", "no"),
    ("2i", "273.2", "273.2(i) Expedited service (7-day standard; $150 gross income / $100 liquid resources test)", "federal_only", r"expedited service|\$150 in monthly gross income", "no"),
    ("2j", "273.2", "273.2(j) Categorical eligibility including broad-based categorical eligibility (state option)", "federal_with_state_option", r"categorically eligible|categorical eligibility", "yes (categorical_eligibility)"),
    ("2k", "273.2", "273.2(k) Joint processing with public assistance (PA/GA) applications", "federal_only", r"joint (PA|processing|application)", "no"),
    ("2o", "273.2", "273.2(o) Attestation of disqualified-felon status by applicants (P.L. 113-79 sec. 4008)", "federal_only", r"attest.{0,120}(felon|convicted)", "no"),
    ("4a", "273.4", "273.4(a) Eligible non-citizens: qualified alien categories and waiting periods", "federal_only", r"qualified alien|lawfully admitted for permanent residence", "yes (eligible_immigration_statuses)"),
    ("4c", "273.4", "273.4(c) Sponsored aliens: deeming of sponsor income and resources", "federal_only", r"sponsor.{0,40}(deem|income)", "no"),
    ("5b", "273.5", "273.5(b) Student eligibility exemptions (20 hours work, work study, parents, E&T/TANF/state programs)", "federal_with_state_option", r"20 hours|work.study", "yes (student/*)"),
    ("7a", "273.7", "273.7(a) Work registration requirement and age range (16-59 pre-OBBBA; as amended)", "federal_only", r"work registration|register for work", "partial (work_requirements/general)"),
    ("7b", "273.7", "273.7(b) Exemptions from work registration (age, child under 6, disability, students, 30 hours)", "federal_only", r"exempt from work registration|exemptions? from the work requirement|30 hours", "partial (work_requirements/general)"),
    ("7c", "273.7", "273.7(c) E&T program requirements and (e) components; State E&T plan", "federal_with_state_option", r"employment and training program|E&T plan|E&T component", "no"),
    ("7d", "273.7", "273.7(d) E&T participant reimbursement and support services (transportation, dependent care)", "federal_with_state_option", r"participant reimbursement|reimburs.{0,80}dependent care|transportation", "no"),
    ("7f", "273.7", "273.7(f) Failure to comply: sanction periods (1, 3, 6 months; state option up to 6)", "federal_with_state_option", r"(one|1) month.{0,120}(three|3) months.{0,200}(six|6) months|minimum (disqualification|sanction) period", "no"),
    ("7j", "273.7", "273.7(j) Voluntary quit and reduction of work effort", "federal_only", r"voluntar(y|ily) quit|reduc(e|ing|tion of) (work|hours)", "no"),
    ("8b", "273.8", "273.8(b) Resource limits ($2,000 / $3,000 elderly-disabled, indexed)", "federal_only", r"\$2,?000|\$3,?000|resource limit", "yes (asset_test/limit)"),
    ("8e", "273.8", "273.8(e) Excluded resources (home, retirement, education accounts, etc.)", "federal_only", r"exclusions from resources|excluded (from )?resources|shall be excluded", "no"),
    ("8f", "273.8", "273.8(f) Vehicle treatment (fair market value / equity tests; TANF vehicle rule substitution)", "federal_with_state_option", r"fair market value|licensed vehicle", "no"),
    ("9a", "273.9", "273.9(a) Income eligibility standards: net 100% FPL, gross 130% FPL, 165% for elderly/disabled separate households", "federal_only", r"130 percent|165 percent", "yes (income/limit)"),
    ("9b", "273.9", "273.9(b) Definition of earned and unearned income", "federal_only", r"earned income shall include|unearned income shall include", "yes (income/sources)"),
    ("9c", "273.9", "273.9(c) Income exclusions (all enumerated); (c)(17) child support exclusion option", "federal_with_state_option", r"income exclusions|shall be excluded from (household )?income|excluded from income", "partial (income/sources)"),
    ("9d1", "273.9", "273.9(d)(1) Standard deduction (8.31% of net income standard, floor/ceiling by area)", "federal_only", r"standard deduction", "yes (deductions/standard)"),
    ("9d2", "273.9", "273.9(d)(2) Earned income deduction (20 percent)", "federal_only", r"earned income deduction", "yes (deductions/earned_income)"),
    ("9d3", "273.9", "273.9(d)(3) Excess medical deduction ($35 threshold, elderly/disabled); standard medical deduction demonstrations", "federal_with_state_option", r"excess medical deduction|\$35 per month", "yes (excess_medical_expense)"),
    ("9d4", "273.9", "273.9(d)(4) Dependent care deduction (uncapped)", "federal_only", r"dependent care deduction|dependent care", "yes (dependent_care)"),
    ("9d5", "273.9", "273.9(d)(5) Child support deduction (legally obligated payments); exclusion alternative", "federal_with_state_option", r"child support (deduction|payments)", "yes (deductions/child_support)"),
    ("9d6i", "273.9", "273.9(d)(6)(i) Homeless shelter deduction (state option; $143 indexed)", "federal_with_state_option", r"homeless shelter deduction", "yes (excess_shelter_expense/homeless)"),
    ("9d6ii", "273.9", "273.9(d)(6)(ii) Excess shelter deduction: 50 percent of income after other deductions; cap except elderly/disabled", "federal_only", r"excess shelter deduction", "yes (excess_shelter_expense/cap, income_share_disregard)"),
    ("9d6iii", "273.9", "273.9(d)(6)(iii) Standard utility allowances: HCSUA, LUA, telephone; mandatory SUA state option; LIHEAP heat-and-eat threshold", "federal_with_state_option", r"standard utility allowance", "yes (deductions/utility/*)"),
    ("10a", "273.10", "273.10(a) Month of application: proration of the initial month's benefit", "federal_only", r"prorat", "partial (proration)"),
    ("10c", "273.10", "273.10(c) Determining income: prospective budgeting, anticipating income, averaging", "federal_only", r"anticipat(ed|ing) income|prospective(ly)?", "no"),
    ("10d", "273.10", "273.10(d) Determining deductions: anticipated expenses, averaging, billed vs paid", "federal_only", r"anticipated expenses|deductible expenses", "no"),
    ("10e1", "273.10", "273.10(e)(1) Net income computation steps", "federal_only", r"net monthly income", "yes (snap_net_income)"),
    ("10e2", "273.10", "273.10(e)(2) Benefit computation: 30 percent of net income; minimum benefit 8 percent of TFP; $1-$4 rounding", "federal_only", r"30 percent|minimum benefit|8 percent", "yes (expected_contribution, min_allotment)"),
    ("10f", "273.10", "273.10(f) Certification periods (up to 12 months; 24 months elderly/disabled; 36 months ESAP)", "federal_with_state_option", r"certification period", "no"),
    ("11a", "273.11", "273.11(a) Self-employment income: annualizing, costs of producing income, standard percentage option", "federal_with_state_option", r"self-employment", "yes (deductions/self_employment)"),
    ("11b", "273.11", "273.11(b) Boarders; (d) treatment centers; (e) group living arrangements; (f) shelters for battered women", "federal_only", r"boarder|group living arrangement", "no"),
    ("11c", "273.11", "273.11(c) Treatment of income and resources of ineligible/disqualified members (all vs prorated share; state option for ineligible aliens)", "federal_with_state_option", r"pro rata share|prorated share|ineligible alien", "yes (ineligible_members/*)"),
    ("11k", "273.11", "273.11(k) Reduction of benefits for failure to comply with other program requirements (comparable disqualification); (m) drug felony disqualification opt-out", "federal_with_state_option", r"comparable (disqualification|penalt)|convicted.{0,60}(felony|controlled substance)", "no"),
    ("12a", "273.12", "273.12(a) Reporting requirements: change reporting (10 days, $100/125 earned), simplified reporting, 130% threshold", "federal_with_state_option", r"simplified reporting|within 10 days", "no"),
    ("12c", "273.12", "273.12(c) State agency action on changes; (e) mass changes (COLA)", "federal_only", r"mass change", "no"),
    ("13a", "273.13", "273.13(a) Notice of adverse action timing (10 days) and content", "federal_only", r"10 days|adverse action", "no"),
    ("14b", "273.14", "273.14(b) Recertification process, application, interview, notice of expiration", "federal_only", r"notice of expiration|recertification", "no"),
    ("15", "273.15", "273.15 Fair hearings: request period (90 days), timeliness, continuation of benefits", "federal_only", r"90 days|fair hearing", "no"),
    ("16", "273.16", "273.16 IPV disqualification: 12 months, 24 months, permanent; administrative disqualification hearings", "federal_only", r"twelve months|12 months|permanent(ly)?", "no"),
    ("18", "273.18", "273.18 Claims against households: IHE, IPV, AE claims; 20/10 percent allotment reduction; compromise", "federal_only", r"inadvertent household error|allotment reduction|20 percent", "no"),
    ("21", "273.21", "273.21 Monthly reporting and retrospective budgeting (state option)", "federal_with_state_option", r"retrospective budgeting|monthly report", "no"),
    ("24a", "273.24", "273.24(a)-(b) ABAWD time limit: 3 countable months in 36; qualifying work 80 hours; exceptions (age, disability, dependents, pregnancy, homeless, veterans, foster youth)", "federal_only", r"80 hours|three countable months|3 countable months", "yes (work_requirements/abawd)"),
    ("24e", "273.24", "273.24(e) Regaining eligibility after the time limit", "federal_only", r"regain", "no"),
    ("24f", "273.24", "273.24(f) Waivers of the time limit for areas with high unemployment (10 percent) or insufficient jobs", "federal_with_state_option", r"waiver|unemployment rate", "yes (abawd/waived_states, waived_counties)"),
    ("24g", "273.24", "273.24(g) Discretionary (percentage) exemptions and carryover", "federal_with_state_option", r"exemptions? (which|that) may be used|percentage|15 percent|12 percent|8 percent", "yes (abawd/discretionary_exemption_rate)"),
    ("26", "273.26", "273.26-273.32 Transitional benefits alternative (state option; 5-month TBA)", "federal_with_state_option", r"transitional benefit", "no"),
]

# 7 CFR 246 paragraph-level elements checked by citation path (paragraph rows exist in the scope).
CFR246_PARAGRAPHS = [
    ("7b", "us/regulation/7/246/7/b", "246.7(b) Residency and physical presence; migrant, homeless and Indian reservation provisions", "federal_with_state_option", "no"),
    ("7c", "us/regulation/7/246/7/c", "246.7(c) Eligibility criteria: categorical (pregnant, breastfeeding, postpartum, infants, children under 5), income, nutritional risk; certification procedures", "federal_only", "yes (wic_category, meets_wic_categorical_eligibility)"),
    ("7d1", "us/regulation/7/246/7/d/1", "246.7(d)(1) Income eligibility standard: at or below 185 percent of poverty; state may set lower (not below 100 percent) or use state health/Medicaid standard", "federal_with_state_option", "yes (wic_income_limit, wic_fpg)"),
    ("7d2", "us/regulation/7/246/7/d/2", "246.7(d)(2) Income determination: family size, current vs annual income, exclusions (d)(2)(iv), adjunctive/automatic eligibility (d)(2)(vi) via Medicaid, SNAP, TANF", "federal_with_state_option", "partial (meets_wic_income_test; adjunctive via program receipt)"),
    ("7e", "us/regulation/7/246/7/e", "246.7(e) Nutritional risk: criteria, anthropometric and bloodwork requirements, who determines", "federal_with_state_option", "partial (is_wic_at_nutritional_risk)"),
    ("7f", "us/regulation/7/246/7/f", "246.7(f) Processing standards: 10 days (20 in remote areas), priority for pregnant women and infants", "federal_only", "no"),
    ("7g", "us/regulation/7/246/7/g", "246.7(g) Certification periods by category (pregnancy, 6/12 months infants, 12 months breastfeeding, up to 12 months children)", "federal_with_state_option", "no"),
    ("7h", "us/regulation/7/246/7/h", "246.7(h) Priority system for caseload limits (priorities I-VII)", "federal_with_state_option", "no"),
    ("7i", "us/regulation/7/246/7/i", "246.7(i) Participant rights and responsibilities; notice of ineligibility", "federal_only", "no"),
    ("7j", "us/regulation/7/246/7/j", "246.7(j) Notification of ineligibility, termination, expiration; disqualification notice", "federal_only", "no"),
    ("7k", "us/regulation/7/246/7/k", "246.7(k) Dual participation prohibition and claims", "federal_only", "no"),
    ("7l", "us/regulation/7/246/7/l", "246.7(l) Transfer of certification (VOC) between agencies", "federal_only", "no"),
    ("7m", "us/regulation/7/246/7/m", "246.7(m) Certification of participants in institutions and homeless facilities", "federal_only", "no"),
    ("7n", "us/regulation/7/246/7/n", "246.7(n) Remote and other certification flexibilities (physical presence exceptions)", "federal_with_state_option", "no"),
    ("10b", "us/regulation/7/246/10", "246.10(b) General food package requirements; state food lists; (b)(1)(i) state authorized foods", "federal_with_state_option", "no", r"State agencies must (identify|authorize)|authorized supplemental foods|food list"),
    ("10c", "us/regulation/7/246/10", "246.10(c) Food package tailoring, substitutions and infant formula issuance", "federal_with_state_option", "partial (wic_food_package)", r"tailor|substitut"),
    ("10d", "us/regulation/7/246/10", "246.10(d) Medical documentation for exempt formula and WIC-eligible nutritionals", "federal_only", "no", r"medical documentation"),
    ("10e", "us/regulation/7/246/10", "246.10(e) Food packages I-VII: maximum monthly allowances by category, cash-value benefit amounts and inflation adjustment", "federal_only", "partial (wic/value by package, cvb/current)", r"maximum monthly allowance|Food Package (I|II|III|IV|V|VI|VII)\b"),
    ("12a", "us/regulation/7/246/12", "246.12(a)-(f) Food delivery systems, benefit issuance, EBT requirements", "federal_with_state_option", "no", r"food delivery system|electronic benefit transfer|EBT"),
    ("12g", "us/regulation/7/246/12", "246.12(g)-(l) Vendor authorization, selection criteria, agreements, training, monitoring, sanctions", "federal_with_state_option", "no", r"vendor (authorization|selection|agreement|sanction)"),
    ("12u", "us/regulation/7/246/12", "246.12(u) Participant violations, sanctions and disqualification; claims", "federal_with_state_option", "no", r"participant violation|disqualif.{0,60}participant"),
    ("4a", "us/regulation/7/246/4", "246.4(a) State plan contents (annual; local agency plan, certification procedures, food list, priority, income guidelines)", "federal_with_state_option", "no", r"State Plan|state plan"),
    ("2", "us/regulation/7/246/2", "246.2 Definitions (breastfeeding woman, infant, child, postpartum, pregnant, family, income, nutritional risk, etc.)", "federal_only", "partial (wic_category definitions)"),
    ("9", "us/regulation/7/246/9", "246.9 Fair hearing procedures for participants (request period, decision within 45 days)", "federal_only", "no"),
    ("11", "us/regulation/7/246/11", "246.11 Nutrition education: two contacts per certification, breastfeeding promotion", "federal_only", "no"),
    ("16a", "us/regulation/7/246/16a", "246.16a Infant formula rebate contracts and cost containment", "federal_only", "no"),
]

USC1786 = [
    ("a", "Congressional findings and declaration of purpose", "federal_only", "no"),
    ("b", "Definitions (breastfeeding, infant, child, postpartum, pregnant, nutritional risk, low-income)", "federal_only", "partial (definitions used by wic_category)"),
    ("c", "Grants-in-aid; eligibility of local agencies; regulations", "federal_only", "no"),
    ("d", "Eligible participants: categories, income at or below 185 percent of poverty, adjunctive eligibility, nutritional risk, certification periods, physical presence", "federal_with_state_option", "partial (categories, 185 percent, nutritional risk flag)"),
    ("e", "Nutrition education and drug abuse education", "federal_only", "no"),
    ("f", "Plan of operation and administration by State agency; state plan contents; food package options", "federal_with_state_option", "no"),
    ("g", "Authorization of appropriations", "federal_only", "no"),
    ("h", "Funds for nutrition services and administration; infant formula rebates; minimum income guidelines; vendor cost containment", "federal_only", "no"),
    ("i", "Division of funds formula; reallocation", "federal_only", "no"),
    ("j", "Program services at community and migrant health centers", "federal_only", "no"),
    ("k", "National Advisory Council on Maternal, Infant, and Fetal Nutrition", "federal_only", "no"),
    ("l", "Donation of foods by Secretary", "federal_only", "no"),
    ("m", "Farmers' market nutrition program (FMNP): eligibility, benefit levels, state match", "federal_with_state_option", "no"),
    ("n", "Disqualification of vendors disqualified under SNAP", "federal_only", "no"),
    ("o", "Disqualification of vendors convicted of trafficking or illegal sales", "federal_only", "no"),
    ("p", "Criminal forfeiture", "federal_only", "no"),
    ("q", "Technical assistance to Secretary of Defense", "federal_only", "no"),
    ("r", "Emergencies and disasters", "federal_only", "no"),
    ("s", "Supply chain disruptions (infant formula flexibilities)", "federal_only", "no"),
]

# Federal guidance families. (id, label, level, regex over selected federal guidance bodies, pe, publisher index if untaken)
SNAP_FED_GUIDANCE = [
    ("snap_g01", "FY 2026 COLA memo: maximum allotments by household size and region (48 states/DC, AK urban/rural 1/rural 2, HI, GU, VI)", r"Maximum Monthly Allotment", "yes (max_allotment)", None),
    ("snap_g02", "FY 2026 COLA memo: standard deductions by household size and region", r"Standard Deductions", "yes (deductions/standard)", None),
    ("snap_g03", "FY 2026 COLA memo: maximum excess shelter deduction by region", r"Maximum Excess Shelter Deduction", "yes (excess_shelter_expense/cap)", None),
    ("snap_g04", "FY 2026 COLA memo: homeless shelter deduction amount", r"Homeless Shelter Deduction", "yes (excess_shelter_expense/homeless/deduction)", None),
    ("snap_g05", "FY 2026 COLA memo: maximum asset limits ($4,500 elderly/disabled; $3,000 other)", r"Maximum Asset Limits", "yes (asset_test/limit)", None),
    ("snap_g06", "FY 2026 income eligibility standards: net (100% FPL) by size and region", r"Net Monthly Income Limit", "yes (income/limit/net)", None),
    ("snap_g07", "FY 2026 income eligibility standards: gross (130% FPL) by size and region", r"Gross Monthly Income Limit \(130", "yes (income/limit/gross)", None),
    ("snap_g08", "FY 2026 income eligibility standards: 165% FPL elderly/disabled separate-household test", r"165% of Federal Poverty Level|165 percent", "no (165% separate-household test not modeled)", None),
    ("snap_g09", "FY 2026 minimum benefit amount (8 percent of TFP for 1-2 person households, by region)", r"minimum (benefit|allotment).{0,80}\$\s?\d", "yes (min_allotment/rate)", "FNS COLA memo 'FY 2026 Cost-of-Living Adjustments' (the full memo carries the minimum benefit; the corpus holds only the two-page allotments/deductions and income-standards tables), fns.usda.gov/snap/allotment/cola (origin fns-prod.azureedge.us)"),
    ("snap_g10", "FNS annual table of state standard utility allowances (HCSUA, LUA, telephone) by state", r"standard utility allowance.{0,600}(Alabama|Alaska|Arizona)", "yes (deductions/utility/* by state)", "FNS SUA page fns.usda.gov/snap/eligibility/deduction/standard-utility-allowances (annual state table); also FY2024 SNAP QC Technical Documentation Table F.7 held on disk but not selected (us/guidance/2026-07-08-snap-qc-fy2024-technical-documentation)"),
    ("snap_g11", "FNS ABAWD time-limit waiver status list by state and area", r"(waiver|waived).{0,200}able.bodied|ABAWD.{0,200}waiver.{0,200}(state|area|county)", "yes (abawd/waived_states, waived_counties)", "FNS ABAWD waivers page fns.usda.gov/snap/abawd/waivers (per-state approval letters and status table)"),
    ("snap_g12", "FNS broad-based categorical eligibility state chart (gross income and asset thresholds elected)", r"broad.based categorical.{0,600}(Alabama|Alaska|Arizona)", "partial (categorical_eligibility; BBCE thresholds not state-specific)", "FNS BBCE chart fns.usda.gov/snap/broad-based-categorical-eligibility"),
    ("snap_g13", "OBBBA (P.L. 119-21) ABAWD exceptions implementation memo", r"One Big Beautiful Bill.{0,400}(ABAWD|able-bodied)", "yes (abawd age thresholds, hr1_in_effect)", None),
    ("snap_g14", "OBBBA alien eligibility implementation memo", r"One Big Beautiful Bill.{0,400}(alien|non-?citizen)", "yes (eligible_immigration_statuses)", None),
    ("snap_g15", "Other OBBBA implementation memos: SUA/LIHEAP heat-and-eat limit to elderly/disabled, internet excluded from SUA, TFP re-evaluation limits, work requirement age 65 and parents of children 14+, state cost share", r"internet.{0,200}(utility|SUA)|heat.and.eat|cost.shar(e|ing).{0,200}(payment error|state)", "partial (SUA and work-requirement age changes modeled; cost share n/a)", "FNS OBBBA implementation memo series fna.usda.gov/snap/obbb (front door 403; origin host serves)"),
    ("snap_g16", "FNS State Options Report (elections by state: BBCE, SUA, simplified reporting, TBA, child support, vehicles, etc.)", r"State Options Report", "n/a", "FNS SNAP State Options Report (fns.usda.gov/snap/waivers/state-options-report); queue policy lists State Options Reports as a forbidden source for state rules, so it is a cross-check only"),
]
WIC_FED_GUIDANCE = [
    ("wic_g01", "WIC income eligibility guidelines 2026-2027 (185% of poverty by family size, Federal Register notice)", r"185 percent.{0,300}poverty|Income Eligibility Guidelines", "yes (wic_income_limit, wic_fpg)", None),
    ("wic_g02", "FY 2026 cash-value voucher/benefit amounts memo (#2026-2)", r"Cash-Value (Voucher|Benefit)", "yes (cvb/current)", None),
    ("wic_g03", "Food package revisions implementation memo (#2025-5) and P.L. 119-37 fluid milk temporary increase (#2026-1)", r"Food Package|Fluid Milk", "partial (wic/value by package; milk allowance not modeled)", None),
    ("wic_g04", "FNS WIC nutrition risk criteria allowed list (Guidance Documents family)", r"nutrition risk criteria.{0,300}(allowed|list|code|justification)", "partial (is_wic_at_nutritional_risk flag only)", "FNA resource browser, WIC Guidance Documents family (195 documents; none taken), fna.usda.gov/resources?f[0]=program:32"),
    ("wic_g05", "Standing WIC policy memoranda issued before FY 2025 (143 of the 154-memo family, e.g. income determination, adjunctive eligibility, certification periods)", r"^WIC Policy Memorandum #(19\d\d|200\d|201\d|202[0-4])-\d+", "no", "FNA resource browser, WIC Policy Memos family (154; 11 FY2025-2026 memos taken)"),
    ("wic_g06", "WIC Federal Register notices and final rules family other than the income guidelines (food package final rule 2024, EBT, vendor cost containment)", r"Federal Register|\d+ FR \d+|final rule", "no", "FNA resource browser, WIC Federal Register Notices family (70; none taken; the two income-guideline notices are wic_g01)"),
    ("wic_g07", "WIC infant formula rebate and cost-containment guidance (state contract requirements)", r"infant formula.{0,120}(rebate|cost containment|contract)", "no", "FNA WIC infant formula guidance (Guidance Documents family)"),
    ("wic_g08", "FNS WIC State Plan guidance and template (annual state plan submission requirements)", r"State Plan (Guidance|Template|Submission)", "no", "FNA WIC State Plan guidance (Guidance Documents family)"),
]

# ---------------------------------------------------------------------------
# State-level elements. (id, label, authority, family, mandatory, regex, pe, rulespec)
# family: state_manual_or_regulation | state_table_or_transmittal | state_plan | state_statute
# mandatory=True: every state must carry it (state-set value or restatement); False: an optional
# election whose absence from a complete rulebook means it is not elected.
# ---------------------------------------------------------------------------
SNAP_STATE_ELEMENTS = [
    ("snap_s01", "BBCE / expanded categorical eligibility election (TANF-funded non-cash benefit conferring eligibility)", "273.2(j)(2)", "state_manual_or_regulation", False,
     r"broad.based categorical|expanded categorical|modified categorical|\bBBCE\b|\bECE\b households|categorical eligibility is expanded|categorical(ly)? eligib[^.]{0,200}\b(200|185|165|160|150)\s?(%|percent)|\b(200|185|165|160|150)\s?(%|percent)[^.]{0,200}categorical(ly)? eligib|categorical eligibility income standard|information and referral[^.]{0,120}(TANF|categorical)|(TANF|MOE)[- ]funded[^.]{0,160}(categorical|service|brochure)|healthy (and stable )?marriage[^.]{0,160}categorical|(authorized to receive|receipt of|receives?)[^.]{0,120}(TANF|MFIP|FIP|ADC|TCA|CalWORKs|W-2|FEP|Families First|Work First|Ohio Works|POWER|KTAP|TEA|JOBS|TAFDC|TANF-MOE)[^.]{0,150}(non.?cash|informational (brochure|pamphlet|notice)|pamphlet|brochure|WSP|supportive service|Support For You)", "partial (categorical_eligibility lists TANF non-cash; thresholds not per state)", "us-ca (modified-categorical-eligibility), us-az"),
    ("snap_s02", "BBCE gross income threshold elected (130/165/185/200 percent of poverty)", "273.2(j)(2)(ii)", "state_manual_or_regulation", False,
     r"(categorical(ly)?|BBCE|expanded)[^.]{0,300}\b(200|185|165|160|150)\s?(%|percent)|\b(200|185|165|160|150)\s?(%|percent)[^.]{0,200}(categorical|BBCE)", "no (PE applies the federal 130/100 tests plus a generic categorical flag)", "us-ca (modified-categorical-eligibility)"),
    ("snap_s03", "BBCE asset test waived or elected asset limit", "273.2(j)(2)(ii)", "state_manual_or_regulation", False,
     r"(categorical(ly)?|BBCE|expanded|\bECE\b)[^.]{0,300}(resource|asset)s? (test|limit)s?[^.]{0,120}(not apply|waive|no |exempt|does not|not subject)|(no|without an?|not subject to|exempt from) (the )?(resource|asset)s? (test|limit)s?[^.]{0,200}(categorical|BBCE|\bECE\b)|(resource|asset)s? (test|limit)s?[^.]{0,120}(do(es)? not apply|waived|not applicable)[^.]{0,200}(categorical|BBCE)", "no", "no"),
    ("snap_s04", "Heating/cooling standard utility allowance (HCSUA) amount", "273.9(d)(6)(iii)", "state_manual_or_regulation", True,
     r"(heating|cooling|standard) utility (allowance|standard)[^.]{0,200}\$\s?\d{2,4}|\bHCSUA\b[^.]{0,200}\$\s?\d{2,4}|\bSUA\b[^.]{0,200}\$\s?\d{2,4}|\$\s?\d{2,4}[^.]{0,120}(heating|cooling|standard) utility", "yes (deductions/utility/standard by state)", "us-ca (standard-utility-allowance)"),
    ("snap_s05", "Limited/basic (non-heating) utility allowance amount", "273.9(d)(6)(iii)", "state_manual_or_regulation", True,
     r"(limited|basic|non.heating|nonheating) utility (allowance|standard)|\bLUA\b|\bBUA\b|\bNHSUA\b|non.heating standard", "yes (deductions/utility/limited by state)", "no"),
    ("snap_s06", "Telephone / single-utility standard amount", "273.9(d)(6)(iii)", "state_manual_or_regulation", True,
     r"telephone (standard|allowance|utility)|phone (standard|allowance)|single utility (allowance|standard)|\bTUA\b|one.utility standard", "yes (deductions/utility/single/phone)", "no"),
    ("snap_s07", "Mandatory SUA election (standards used in place of actual utility costs)", "273.9(d)(6)(iii)(E)", "state_manual_or_regulation", False,
     r"mandatory (standard )?utility|(SUA|HCSUA|standard utility allowance|utility (allowance|standard))s? (is|are) mandatory|must use the (standard utility|SUA|HCSUA|utility (standard|allowance))|(SUA|HCSUA|utility (allowance|standard))s?[^.]{0,80}(in lieu of|instead of|rather than) actual utility|cannot (use|claim) actual utility", "yes (utility/always_standard)", "no"),
    ("snap_s08", "LIHEAP nominal-payment (heat-and-eat) SUA entitlement and post-OBBBA limitation", "273.9(d)(6)(iii)(C)", "state_manual_or_regulation", False,
     r"(LIHEAP|LIEAP|\bHEAP\b|\bLEAP\b|energy assistance)[^.]{0,200}(SUA|HCSUA|standard utility|heating|utility (standard|allowance))|heat.and.eat|\$20(\.01)?[^.]{0,80}(energy|LIHEAP)", "no", "no"),
    ("snap_s09", "Homeless shelter deduction election and amount", "273.9(d)(6)(i)", "state_manual_or_regulation", False,
     r"homeless (household )?(shelter|standard) (deduction|allowance)|homeless[^.]{0,120}shelter (deduction|standard)", "yes (excess_shelter_expense/homeless)", "no"),
    ("snap_s10", "Standard medical deduction (demonstration) amount and threshold", "273.9(d)(3), 7 USC 2026(b)", "state_manual_or_regulation", False,
     r"standard medical (deduction|expense deduction|expense \(SME\)|expense standard|allowance)|\bSMD\b|\bSMED\b", "no (PE uses the federal $35 excess-medical rule)", "no"),
    ("snap_s11", "Excess medical deduction as applied ($35 threshold; elderly/disabled)", "273.9(d)(3)", "state_manual_or_regulation", True,
     r"medical (expense|deduction|cost)s?[^.]{0,120}(\$\s?35|excess|exceed|over \$)", "yes (excess_medical_expense)", "us (273/9)"),
    ("snap_s12", "Child support: deduction vs income exclusion election", "273.9(c)(17), 273.9(d)(5)", "state_manual_or_regulation", True,
     r"child support[^.]{0,120}(deduction|exclu|disregard)", "yes (deductions/child_support)", "no"),
    ("snap_s13", "Dependent care deduction (uncapped) as applied", "273.9(d)(4)", "state_manual_or_regulation", True,
     r"dependent care (deduction|expense|cost)|child care (deduction|expense)s?[^.]{0,80}(deduct|allow)", "yes (dependent_care)", "us (273/9)"),
    ("snap_s14", "Earned income deduction (20 percent) as applied", "273.9(d)(2)", "state_manual_or_regulation", True,
     r"earned income (deduction|disregard)[^.]{0,80}(20|twenty)\s?(%|percent)|(20|twenty)\s?(%|percent)[^.]{0,60}earned income", "yes (deductions/earned_income)", "us (273/9)"),
    ("snap_s15", "Standard deduction amount by household size (state's applied table)", "273.9(d)(1)", "state_table_or_transmittal", True,
     r"standard deduction[^.]{0,160}\$\s?\d{3}\b", "yes (deductions/standard)", "us (fy-2026-cola/deductions)"),
    ("snap_s16", "Excess shelter deduction cap amount (state's applied table)", "273.9(d)(6)(ii)", "state_table_or_transmittal", True,
     r"(maximum|cap(ped)?|limit(ed)?)[^.]{0,60}(excess )?shelter (deduction|expense|cost)s?[^.]{0,120}\$\s?\d{3}|(excess )?shelter (deduction|expense|cost)s?[^.]{0,80}(cap|maximum|limit)[^.]{0,120}\$\s?\d{3}|\$\s?\d{3}[^.]{0,60}(shelter (cap|maximum)|maximum (excess )?shelter)|shelter (cap|maximum)[^.]{0,60}\$\s?\d{3}", "yes (excess_shelter_expense/cap)", "us (fy-2026-cola/deductions)"),
    ("snap_s17", "Gross and net income limits by household size (state's applied table)", "273.9(a), 273.10(e)", "state_table_or_transmittal", True,
     r"(gross|net) (monthly )?income (limit|standard|test|eligibility)s?[^.]{0,300}\$\s?\d{3}|income eligibility standards?[^.]{0,200}\$\s?\d{3}|130\s?(%|percent)[^.]{0,200}\$\s?\d{3}|maximum gross (monthly )?income[^.]{0,120}\$\s?\d{3}", "yes (income/limit + FPG)", "us (income-eligibility-standards)"),
    ("snap_s18", "Maximum allotment by household size (state's applied table)", "273.10(e)(2)(ii)", "state_table_or_transmittal", True,
     r"maximum (monthly )?(allotment|benefit)s?[^.]{0,200}\$\s?\d{3}|thrifty food plan[^.]{0,120}\$\s?\d{3}|(allotment|basis of issuance|benefit issuance) (table|chart|schedule)s?|basis of (coupon|EBT) issuance", "yes (max_allotment)", "us (maximum-allotments)"),
    ("snap_s19", "Minimum benefit and initial-month proration as applied", "273.10(a)(1)(ii), 273.10(e)(2)(ii)(C)", "state_manual_or_regulation", True,
     r"prorat[^.]{0,120}(initial|first) month|initial month[^.]{0,120}prorat|minimum (benefit|allotment)[^.]{0,120}\$\s?\d", "yes (min_allotment, proration)", "us (273/10)"),
    ("snap_s20", "Current-FY change transmittal / COLA notice carrying the state's applied FY 2026 amounts", "273.9(d), 273.10(e)", "state_table_or_transmittal", True,
     r"(October 1, 2025|FY ?2026|fiscal year 2026|FFY ?2026|10/1/(20)?25|10/01/(20)?25|effective (October|Oct\.?) (1, )?2025)[^.]{0,300}(allotment|income (limit|standard)|standard deduction|utility|shelter)|(allotment|income (limit|standard)|standard deduction|utility allowance|shelter cap)[^.]{0,300}(October 1, 2025|FY ?2026|fiscal year 2026|FFY ?2026|10/1/(20)?25|10/01/(20)?25)", "n/a (PE carries FY amounts federally)", "no"),
    ("snap_s21", "Resource limit as applied ($3,000 / $4,500) and countable resources", "273.8(b)", "state_manual_or_regulation", True,
     r"resource (limit|standard|maximum)s?[^.]{0,120}\$\s?\d|asset limit[^.]{0,120}\$\s?\d|countable resources?[^.]{0,80}\$\s?\d|\$\s?[34],[05]00[^.]{0,80}(resource|asset)", "partial (asset_test/limit)", "us (273/8)"),
    ("snap_s22", "Vehicle exclusion policy (federal FMV/equity tests or TANF vehicle-rule substitution)", "273.8(f)", "state_manual_or_regulation", True,
     r"vehicle[^.]{0,150}(exclu|fair market|equity|countable|resource)|(licensed|motor) vehicle", "no", "no"),
    ("snap_s23", "Simplified reporting election and periodic report requirements", "273.12(a)(5)", "state_manual_or_regulation", True,
     r"simplified report|semi.annual report|periodic report|six.month report|interim report|\bSR\b household", "no", "no"),
    ("snap_s24", "Certification period lengths by household type (state-set within 273.10(f))", "273.10(f)", "state_manual_or_regulation", True,
     r"certification period[^.]{0,200}\b(6|12|24|36|six|twelve|twenty.four)\b[^.]{0,20}months?|\b(6|12|24|36|six|twelve|twenty.four)\b.month certification", "no", "no"),
    ("snap_s25", "Change reporting thresholds and timeframes (10 days; 130 percent gross; ABAWD hours)", "273.12(a)", "state_manual_or_regulation", True,
     r"report[^.]{0,120}change[^.]{0,200}(10 days|ten days|130 percent|130%|gross (monthly )?income)|change[^.]{0,80}within (10|ten) (calendar )?days", "no", "no"),
    ("snap_s26", "ABAWD time limit as applied: countable months, qualifying activities, exceptions (post-OBBBA age range)", "273.24(a)-(c)", "state_manual_or_regulation", True,
     r"able.bodied|\bABAWD|time.limit[^.]{0,120}(countable|36.month|three months|3 months)", "yes (abawd/*)", "us (273/24)"),
    ("snap_s27", "ABAWD waived areas in effect and discretionary (percentage) exemption policy", "273.24(f),(g)", "state_manual_or_regulation", True,
     r"(ABAWD|time.limit|work requirement)[^.]{0,200}(waiver|waived|exempt(ion)? (area|county|counties))|discretionary exemption|percentage exemption|15 percent exemption|(waived|waiver) (area|count(y|ies)|region)", "yes (abawd/waived_states, waived_counties, discretionary_exemption_rate)", "no"),
    ("snap_s28", "Work registration exemptions and sanction durations for noncompliance (state-set within 273.7(f))", "273.7(a),(b),(f)", "state_manual_or_regulation", True,
     r"work registration|register(ed)? for work|work requirement[^.]{0,100}(sanction|disqualif|penalt)|failure to comply[^.]{0,80}work", "partial (general work requirements; sanctions not modeled)", "us (273/7)"),
    ("snap_s29", "Voluntary quit and reduction of work effort policy", "273.7(j)", "state_manual_or_regulation", True,
     r"voluntar(y|ily) quit|reduc(e|ed|ing|tion of) (work|hours)[^.]{0,80}(sanction|disqualif|good cause|penalt)", "no", "no"),
    ("snap_s30", "E&T program design: mandatory vs voluntary, components, participant reimbursements", "273.7(e)", "state_manual_or_regulation", True,
     r"employment (and|&) training|\bE&T\b|\bE ?& ?T\b|SNAP E ?& ?T|\bSNAP ?ET\b", "partial (work program participation)", "no"),
    ("snap_s31", "SNAP E&T State Plan (annual, filed with FNS)", "273.7(c)", "state_plan", True, None, "no", "no"),
    ("snap_s32", "State Plan of Operation (272.2) with elected options attachments", "272.2", "state_plan", True, None, "no", "no"),
    ("snap_s33", "Transitional benefits alternative (TBA) election and period", "273.26-273.32", "state_manual_or_regulation", False,
     r"transitional benefits? (alternative|assistance|period|reporting|option)|\bTBA\b|transitional (SNAP|food|CalFresh|FoodShare|food stamp)|\bTSNAP\b|\bTFA\b", "no", "no"),
    ("snap_s34", "Student eligibility as applied, including state/local E&T programs that qualify students", "273.5(b)", "state_manual_or_regulation", True,
     r"student[^.]{0,250}(higher education|institution of higher|college|post.secondary)|ineligible student|higher education[^.]{0,120}student", "partial (student/*)", "us (273/5)"),
    ("snap_s35", "Non-citizen eligibility as applied (federal categories restated; OBBBA changes; sponsor deeming)", "273.4", "state_manual_or_regulation", True,
     r"(alien|non.?citizen|immigrant|immigration status|qualified alien|lawful permanent resident|LPR)s?[^.]{0,200}eligib|sponsor[^.]{0,80}deem", "yes (eligible_immigration_statuses)", "us (273/4)"),
    ("snap_s36", "Income and deductions of ineligible non-citizen members: all vs prorated share (state option)", "273.11(c)(3)", "state_manual_or_regulation", True,
     r"(ineligible|disqualified|excluded) (alien|non.?citizen|immigrant|household member|member|individual)s?[^.]{0,300}(income|resource)s?[^.]{0,200}(prorat|count|all)|prorat[^.]{0,200}(alien|non.?citizen|immigrant|ineligible|disqualified)|(alien|non.?citizen|immigrant)s?[^.]{0,200}prorat", "yes (ineligible_members/*)", "no"),
    ("snap_s37", "State-funded food assistance for non-citizens ineligible under federal rules (if any)", "state statute", "state_statute", False,
     r"state.funded[^.]{0,200}(non.?citizen|immigrant|alien|legal permanent|CFAP|\bFAP\b)|(non.?citizen|immigrant|alien)s?[^.]{0,200}state.funded (food|nutrition|snap|benefit|supplemental)|California Food Assistance Program|\bCFAP\b|Food Assistance Program for Legal Immigrants|Minnesota Food Assistance Program|\bMFAP\b|State Funded Supplemental Nutrition Assistance|\bSFSNAP\b|State Food Assistance Program|state.funded (food|SNAP|nutrition)[^.]{0,120}(immigrant|non.?citizen|alien)", "partial (ca_snap_immigration_status_eligible only)", "no"),
    ("snap_s38", "Drug-felony disqualification: state opt-out or modification (21 USC 862a)", "21 USC 862a, 273.11(m)", "state_manual_or_regulation", False,
     r"(drug|controlled substance)[^.]{0,100}(felony|conviction|felon)[^.]{0,250}(disqualif|eligib|ineligib)", "no", "no"),
    ("snap_s39", "Combined application project / elderly simplified application project", "7 USC 2020(i), 273.2(o)", "state_manual_or_regulation", False,
     r"combined application project|\bCAP\b[^.]{0,80}\bSSI\b|elderly simplified application|\bESAP\b|\bSCAP\b|\bNYSCAP\b|\bMSCAP\b|\bSSI CAP\b", "no", "no"),
    ("snap_s40", "Restaurant meals program election", "7 USC 2012(k), 274.7", "state_manual_or_regulation", False,
     r"restaurant meals? program|\bRMP\b|restaurant meals?[^.]{0,120}(elderly|disabled|homeless)", "no", "no"),
    ("snap_s41", "Interview mode (telephone/on-demand) and interview waiver policy", "273.2(e)", "state_manual_or_regulation", True,
     r"(telephone|phone|video) interview|waive[^.]{0,40}interview|on.demand interview|interview[^.]{0,80}(waived|by telephone)", "no", "no"),
    ("snap_s42", "Expedited service criteria and timeframe as applied", "273.2(i)", "state_manual_or_regulation", True,
     r"expedited (service|benefit|processing|issuance|snap|calfresh|foodshare)|\$150[^.]{0,120}(gross|liquid)", "no", "no"),
    ("snap_s43", "Verification standards: mandatory items, acceptable documents, questionable information", "273.2(f)", "state_manual_or_regulation", True,
     r"verif(y|ication)[^.]{0,150}(identity|residency|income|questionable|mandatory|required)", "no", "no"),
    ("snap_s44", "Fair hearing procedures and timeframes", "273.15", "state_manual_or_regulation", True,
     r"fair hearing|administrative hearing|state hearing|hearing request", "no", "no"),
    ("snap_s45", "IPV disqualification periods and administrative disqualification hearings", "273.16", "state_manual_or_regulation", True,
     r"intentional program violation|\bIPV\b|administrative disqualification hearing|\bADH\b", "no", "no"),
    ("snap_s46", "Claims and overpayment recovery (IHE/AE/IPV; allotment reduction; compromise)", "273.18", "state_manual_or_regulation", True,
     r"overpayment|claim[^.]{0,60}(establish|collect|recover|recoup)|inadvertent household error|agency error claim", "no", "no"),
    ("snap_s47", "Household composition and separate-household rules as applied", "273.1", "state_manual_or_regulation", True,
     r"household (composition|definition|concept|member)|purchase and prepare|purchases? and prepares?|\bboarder", "partial (snap_unit)", "us-ca 63-402"),
    ("snap_s48", "Residency requirement as applied", "273.3", "state_manual_or_regulation", True,
     r"residen(cy|t)[^.]{0,80}(requirement|of the state|in the state|in the county|in the project area)|reside in the state", "no", "us (273/3)"),
    ("snap_s49", "Social security number requirement as applied", "273.6", "state_manual_or_regulation", True,
     r"social security number|\bSSN\b", "no", "us (273/6)"),
    ("snap_s50", "Self-employment income: expense method (actual vs standard percentage)", "273.11(a)", "state_manual_or_regulation", True,
     r"self.employ(ment|ed)[^.]{0,250}(expense|deduction|percent|%|cost of (doing|producing))", "yes (deductions/self_employment)", "no"),
    ("snap_s51", "Elderly/disabled definition (age 60; disability sources) as applied", "271.2, 273.9(d)(3)", "state_manual_or_regulation", True,
     r"(elderly|disabled)[^.]{0,150}\b(60|sixty)\b[^.]{0,40}(age|older|years)|age 60 or older|60 years of age or older|\b60 (years )?(of age )?(or|and) older", "yes (has_snap_elderly_disabled_member)", "no"),
    ("snap_s52", "Categorical eligibility (TANF/SSI/GA recipients) as applied by the state", "273.2(j)(1)", "state_manual_or_regulation", True,
     r"categorical(ly)? eligib", "yes (categorical_eligibility)", "us (273/2/j)"),
    ("snap_s53", "State-funded minimum benefit supplement (NJ, MD, DC and others; if any)", "state statute", "state_statute", False,
     r"(state|district|locally)[- ]funded[^.]{0,120}(minimum (benefit|allotment)|minimum brings|SNAP supplement|supplemental (SNAP|food)|Any size \$)|minimum state supplement|\bMSS\b benefits|state (snap )?supplement[^.]{0,150}(allotment is less|minimum|\$\s?\d)|(minimum (benefit|allotment))[^.]{0,120}(state|district)[- ]funded|federally funded SNAP benefit is less than", "yes for NJ, MD, DC (gov/states/*/snap/min_allotment)", "no"),
    ("snap_s54", "Income exclusions as applied (federal list restated; state-specific exclusions)", "273.9(c)", "state_manual_or_regulation", True,
     r"(excluded|exempt) income|income exclusions?|not counted as income|disregarded income", "partial (income/sources)", "no"),
    ("snap_s55", "Prospective budgeting / income anticipation and conversion factors (4.3 / 4.33 / 2.15)", "273.10(c)", "state_manual_or_regulation", True,
     r"4\.3\b|4\.33\b|2\.15\b|prospective(ly)? budget|anticipat(ed|ing) income", "no", "no"),
    ("snap_s56", "Notice of adverse action / advance notice period as applied", "273.13", "state_manual_or_regulation", True,
     r"adverse action|advance notice|timely notice", "no", "no"),
    ("snap_s57", "Recertification and notice of expiration process as applied", "273.14", "state_manual_or_regulation", True,
     r"recertif|notice of expiration|redetermination", "no", "no"),
    ("snap_s58", "Treatment center / group living / shelter resident rules as applied", "273.11(e),(f), 7 USC 2017(e),(f)", "state_manual_or_regulation", True,
     r"(drug|alcohol)[^.]{0,60}treatment (center|facilit)|group living arrangement|shelter for battered", "no", "no"),
    ("snap_s59", "SSI cash-out / SSI recipients' treatment (CA CalFresh expansion, state supplement states)", "273.20, 7 USC 2015(g)", "state_manual_or_regulation", False,
     r"cash.out (state|project|program|payments)|SSI recipients? (in|from) (a )?[^.]{0,20}cash.out|SSI/SSP recipients?[^.]{0,80}(eligible|ineligible)|SSI recipients? (are|is|shall be) (eligible|ineligible)", "no", "no"),
    ("snap_s60", "Fleeing felon / parole violator disqualification as applied", "273.11(n)", "state_manual_or_regulation", True,
     r"fleeing felon|probation or parole|parole violat", "no", "no"),
    ("snap_s61", "Lottery/gambling winnings disqualification threshold as applied", "273.11(r), 272.17", "state_manual_or_regulation", True,
     r"lottery|gambling", "no", "no"),
]

WIC_STATE_ELEMENTS = [
    ("wic_s01", "State income eligibility standard (185 percent or lower) and current income guidelines table", "246.7(d)(1)", "state_manual_or_regulation", True,
     r"185\s?(%|percent)|income (eligibility )?guidelines|income (standard|limit|scale)", "yes (wic_income_limit)", "no"),
    ("wic_s02", "Income determination method: family size, current vs annual income, self-employment, in-kind", "246.7(d)(2)(i)-(iv)", "state_manual_or_regulation", True,
     r"(current|annual|gross) income[^.]{0,120}(determin|calculat|used|average)|self.employ|family size|economic unit", "partial (wic_countable_income)", "no"),
    ("wic_s03", "Adjunctive / automatic income eligibility programs recognised (Medicaid, SNAP, TANF, others)", "246.7(d)(2)(vi)", "state_manual_or_regulation", True,
     r"adjunct(ive)?(ly)? (income )?eligib|automatic(ally)? income.eligib|(Medicaid|SNAP|TANF|Food Stamp|Medi-Cal|MassHealth|CalFresh)[^.]{0,120}(adjunct|automatic(ally)? (income )?eligib)", "partial (meets_wic_income_test uses program receipt)", "no"),
    ("wic_s04", "Categorical eligibility definitions (pregnant, breastfeeding to 1 year, postpartum 6 months, infant, child to age 5)", "246.2, 246.7(c)", "state_manual_or_regulation", True,
     r"(pregnant|breastfeeding|postpartum|infant|child)[^.]{0,80}(categor|eligib)|categorical(ly)? eligib", "yes (wic_category)", "no"),
    ("wic_s05", "Nutritional risk criteria in use and who may determine risk (CPA)", "246.7(e)", "state_manual_or_regulation", True,
     r"nutrition(al)? risk", "partial (is_wic_at_nutritional_risk)", "no"),
    ("wic_s06", "Anthropometric and hematological (bloodwork) requirements and deferral", "246.7(e)(1)(ii)", "state_manual_or_regulation", True,
     r"hemoglobin|hematocrit|anthropometric|bloodwork|blood work|height and weight", "no", "no"),
    ("wic_s07", "Certification periods by category", "246.7(g)", "state_manual_or_regulation", True,
     r"certification period", "no", "no"),
    ("wic_s08", "Residency and physical presence requirements (and exceptions)", "246.7(b), 246.7(c)(2)(iii)", "state_manual_or_regulation", True,
     r"residen(cy|t)[^.]{0,120}(requirement|state|local agency|service area)|physical(ly)? presen", "no", "no"),
    ("wic_s09", "Identity, residency and income documentation and verification", "246.7(c)(2)", "state_manual_or_regulation", True,
     r"proof of (income|identity|residen)|verif(y|ication)[^.]{0,80}(income|identity|residen)|documentation of (income|identity)", "no", "no"),
    ("wic_s10", "Presumptive / temporary certification of pregnant women pending income or risk documentation", "246.7(e)(1)(iii)?, 246.7(c)(2)(ii)", "state_manual_or_regulation", True,
     r"temporar(y|ily) certif|30.day (temporary )?certification|provisional certification|short certification|shortened[^.]{0,30}certification|presumptive(ly)? (eligib|certif)[^.]{0,80}(pregnan|WIC certification)", "no", "no"),
    ("wic_s11", "Priority system and waiting list management", "246.7(h)", "state_manual_or_regulation", True,
     r"priority (system|level|I\b|1\b)|waiting list", "no", "no"),
    ("wic_s12", "Processing standards (10/20 days) and appointment scheduling", "246.7(f)", "state_manual_or_regulation", True,
     r"processing standard|(10|20|ten|twenty) (calendar |business )?days[^.]{0,80}(appointment|certif|notif)", "no", "no"),
    ("wic_s13", "Food packages and tailoring (state maximum monthly allowances)", "246.10(b),(c),(e)", "state_manual_or_regulation", True,
     r"food package", "partial (wic/value by package)", "no"),
    ("wic_s14", "Cash-value benefit amounts as issued", "246.10(e)(9),(12)", "state_manual_or_regulation", True,
     r"cash.value (benefit|voucher)|\bCVB\b|\bCVV\b", "yes (cvb/current)", "no"),
    ("wic_s15", "State-approved food list / authorized foods", "246.10(b)(1)(i)", "state_manual_or_regulation", True,
     r"(approved|authorized|allowed) food (list|guide|card)|WIC.approved food|food list|authorized foods", "no", "no"),
    ("wic_s16", "Medical documentation and special/exempt infant formula issuance", "246.10(d),(e)(3)", "state_manual_or_regulation", True,
     r"medical documentation|exempt infant formula|special formula|WIC.eligible nutritionals|medical (necessity|prescription)", "no", "no"),
    ("wic_s17", "Breastfeeding categories (fully/partially/some) and food package assignment", "246.2, 246.10(e)(1)", "state_manual_or_regulation", True,
     r"(fully|partially|exclusively|mostly|some) breastfe|breastfeeding (peer|promotion|support)", "yes (is_wic_fully_breastfeeding, wic_infant_feeding_category)", "no"),
    ("wic_s18", "Dual participation and transfer of certification (VOC)", "246.7(k),(l)", "state_manual_or_regulation", True,
     r"dual participation|verification of certification|\bVOC\b|transfer[^.]{0,80}(certification|participant)", "no", "no"),
    ("wic_s19", "Participant violations, sanctions, disqualification and claims", "246.12(u)", "state_manual_or_regulation", True,
     r"(participant|program) (violation|abuse|sanction|disqualif|fraud)|claims against participants", "no", "no"),
    ("wic_s20", "Notice of ineligibility, termination and expiration", "246.7(j)", "state_manual_or_regulation", True,
     r"notice of (ineligibility|termination|expiration)|notif(y|ication)[^.]{0,80}(ineligib|terminat)", "no", "no"),
    ("wic_s21", "Fair hearing procedures for participants", "246.9", "state_manual_or_regulation", True,
     r"fair hearing", "no", "no"),
    ("wic_s22", "Nutrition education contacts and breastfeeding promotion", "246.11", "state_manual_or_regulation", True,
     r"nutrition education", "no", "no"),
    ("wic_s23", "Vendor authorization, management and sanctions", "246.12(g)-(l)", "state_manual_or_regulation", True,
     r"vendor (authorization|selection|management|agreement|sanction|monitoring)|authorized vendor", "no", "no"),
    ("wic_s24", "Benefit issuance / eWIC / food instrument rules", "246.12(a)-(f)", "state_manual_or_regulation", True,
     r"\beWIC\b|\bEBT\b|benefit issuance|food instrument|cash.value voucher", "no", "no"),
    ("wic_s25", "Local agency selection, agreements and monitoring", "246.5, 246.6, 246.19", "state_manual_or_regulation", True,
     r"local agenc[^.]{0,100}(select|agreement|contract|monitor|review)", "no", "no"),
    ("wic_s26", "Migrant, homeless and institutional participant provisions", "246.7(b)(1)(i), 246.7(c)(2)(iv), 246.7(m)", "state_manual_or_regulation", True,
     r"migrant|homeless|institution[^.]{0,80}(participant|resident)", "no", "no"),
    ("wic_s27", "Farmers' market nutrition program / farm direct", "246.12(v), 42 USC 1786(m)", "state_manual_or_regulation", False,
     r"farmers.? market|farm direct", "no", "no"),
    ("wic_s28", "Civil rights and nondiscrimination procedures", "246.8", "state_manual_or_regulation", True,
     r"civil rights|nondiscrimination", "no", "no"),
    ("wic_s29", "Caseload management and participant scheduling", "246.7(f), 246.7(h)", "state_manual_or_regulation", True,
     r"caseload", "no", "no"),
    ("wic_s30", "WIC State Plan filed with FNS (246.4)", "246.4", "state_plan", True, None, "no", "no"),
    ("wic_s31", "State WIC administrative rule chapter (if the state codifies WIC)", "state regulation", "state_regulation", False, None, "no", "no"),
]

# ---------------------------------------------------------------------------
# Reviewer facts from the run notes and queues that the queue rows carry only in prose.
# ---------------------------------------------------------------------------
SNAP_BLOCKED = {
    "us-az": "DES FAA policy manual host dbmefaapolicy.azdes.gov answers HTTP 403 / F5 TSPD bot challenge (2026-09-10, re-probed 2026-09-11); released scope is a thin archived-snapshot capture (7 + 143 provisions)",
    "us-ny": "OTDA host otda.ny.gov bot-challenged (batches 1-3, re-probed 2026-09-11); released scopes hold the SNAP Source Book (22 rows), Employment Policy Manual and 18 NYCRR 385/387",
    "us-oh": "ODJFS eManuals Food Assistance manual host does not answer (2026-09-11); OAC 5101:4 complete (82/82 rules) in corpus",
}
# transmittal / table families the publisher lists (completion queue index_families and run notes), not taken
SNAP_TRANSMITTAL_FAMILY = {
    "us-ga": "manual_transmittal_cover_letter_pdf 87 (MT 1-87; MT 87 dated 2026-06-01), https://pamms.dhs.ga.gov/dfcs/snap/",
    "us-nv": "ep_manual_transmittal_letter_pdf 86 (2010-July 2026), https://dwss.nv.gov/Home/Features/eligibility/eligibility-n-payment-info-manual/",
    "us-nc": "fns_administrative_letter_document 367 + fns_change_notice_document 312 (2022-2026), https://policies.ncdhhs.gov/divisional-n-z/social-services/food-and-nutrition-services/fns-policies-manuals/",
    "us-mi": "bpb_policy_bulletin_pdf 422 + rft_reference_table_pdf 22 (7 in scope) + rfs_reference_schedule_pdf 8 (2 in scope), MDHHS Bridges manuals (BEM/BAM/RFT/RFS TOCs)",
    "us-fl": "ess_summary_of_changes_quarterly_pdf 28, https://www.myflfamilies.com/services/public-assistance/additional-resources-and-services/ess-program-manual",
    "us-nd": "release_update_pdf 15 (2 taken, 12 pre-baseline), https://www.nd.gov/dhs/policymanuals/SNAP/Content/Home%202.htm release log",
    "us-ky": "omtl_cover_letter_and_policy_update_volume_pdf 2 (Volumes IX and X transmittal history), https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx",
    "us-wy": "cm_updates_change_log_html 1, https://dfs.wyo.gov/about/policy-manuals/snap-and-power-policy-manual/ (CM Updates)",
    "us-nh": "service_release_html_cited_by_topics 109, https://www.dhhs.nh.gov/fsm_htm/newfsm.htm (Service Releases)",
    "us-ma": "MA DTA Online Guide (follow-on family named in completion batch 1), https://www.mass.gov/lists/department-of-transitional-assistance-regulations; DTA COLA guidance already in scope",
    "us-ny": "OTDA ADM/INF/GIS policy directives (follow-on family named in completion batches 1-3; host bot-challenged)",
    "us-ca": "CDSS All County Letters / ACINs for CalFresh COLA (only ACIN I-46-25 and the BBCE ACLs are in scope), https://www.cdss.ca.gov/inforesources/letters-regulations",
}
SNAP_ET_PLAN_PUBLISHER = {
    "us-ar": "snap_et_state_plan_pdf 2 (FFY25/FY26 SNAP E&T State Plans) on the DHS DCO SNAP page",
    "us-ky": "Kentucky SNAP E&T State Plan 2026 PDF on the CHFS DFS index (completion batch 2)",
}
SNAP_STATE_PLAN_ATTACHMENT_PUBLISHER = {
    "us-nm": "isd_state_verification_plan_pdf 1 (ISD State Verification Plan, a 272.2 attachment) on https://www.hca.nm.gov/lookingforinformation/income-support-division-1/",
}

WIC_BLOCK_CLASS = {
    # OUTREACH: publisher blocks (bot wall, 403, TLS, DNS, login, password) per manifests/wic-agent-queue.yaml
    "us-ar": "OUTREACH", "us-az": "OUTREACH", "us-de": "OUTREACH", "us-nh": "OUTREACH", "us-ks": "OUTREACH",
    "us-ma": "OUTREACH", "us-il": "OUTREACH", "us-mo": "OUTREACH", "us-nm": "OUTREACH", "us-nv": "OUTREACH",
    # ABSENT: publisher posts no manual (index read, nothing listed)
    "us-ak": "ABSENT", "us-al": "ABSENT", "us-fl": "ABSENT", "us-hi": "ABSENT", "us-id": "ABSENT", "us-in": "ABSENT",
    "us-la": "ABSENT", "us-ms": "ABSENT", "us-mt": "ABSENT", "us-nd": "ABSENT", "us-ne": "ABSENT",
    "us-ny": "ABSENT", "us-oh": "ABSENT", "us-ok": "ABSENT", "us-sc": "ABSENT", "us-sd": "ABSENT", "us-tn": "ABSENT",
    "us-vt": "ABSENT", "us-wi": "ABSENT", "us-wy": "ABSENT",
}
WIC_STATE_PLAN_PUBLISHER = {
    "us-mt": "2026 Montana WIC State Plan page (dphhs.mt.gov/ecfsd/wic/wicstateplan; attachments under assets/ecfsd/WIC/StatePlan/)",
    "us-vt": "2025 State Plan Goals and Objectives PDF (healthvermont.gov WIC Plans & Reports)",
    "us-wi": "FY2025 state-plan sections (dhs.wisconsin.gov wic/certification-eligibility-coordination.pdf, wic/caseload-management.pdf)",
    "us-ut": "FY2027 state plan Section II draft (110 PDFs on a separate wic.utah.gov page)",
    "us-wv": "state_plan_page 2 (FY 2025, FY 2024) on the dhhr.wv.gov policy index",
    "us-ct": "state_plan_section_1_pdf 2 on the portal.ct.gov State Plan Policies pages",
    "us-ma": "FFY 2027 WIC state plan page on mass.gov (host 403 to non-browser clients)",
    "us-al": "FY2027 state-plan public notice only (alabamapublichealth.gov)",
}
WIC_STATE_RULE_PUBLISHER = {"us-tn": "WIC state rule 1200-15-02 linked from tn.gov/health/wic.html (batch 4 retry)"}
WIC_PARTIAL = {"us-nj": "only the vendor-management functional area (P&P 1.31-1.50) of the manual is published; certification chapters are not posted"}
# Snippet-window exclusions for elements whose keywords collide with a neighbouring rule.
EXCLUDE = {
    "snap_s15": r"homeless|earned income|twenty per ?cent|20 percent",
    "snap_s10": r"Medicare Drug discount",
    "snap_s53": r"emergency (allotment|supplement)|SSI State Supplement|state supplementary payment|SSP\b|Medicaid|AABD|TANF|GA\b",
    "wic_s03": r"adjunctive therap",
}
# Guidance elements decided on document headings (a body mention of an older memo or a final rule is not the document).
HEADING_CHECK = {"wic_g05": None, "wic_g06": r"Income Eligibility Guidelines"}
# FY 2026 figures must not be satisfied by the FY 2024 COLA memo held in the corpus.
FY2026_ONLY = {"snap_g01", "snap_g02", "snap_g03", "snap_g04", "snap_g05", "snap_g06", "snap_g07", "snap_g08", "snap_g09"}
SNAP_ET_PLAN_HEADING = re.compile(r"E&T State Plan|Employment (and|&) Training (State )?Plan|Workfare (Program )?State Plan", re.I)
SNAP_PLAN_OF_OPERATION_HEADING = re.compile(r"State Plan of Operation", re.I)

WIC_NOT_TAKEN_FAMILY = {
    "us-mn": "exhibit PDFs 46 not taken (5-A income guidelines, 5-T risk criteria, 5-U priority system, 6-A high-risk criteria carry parameter content)",
    "us-ct": "numbered attachments 49 and unnumbered guidance 30 not taken (incl. the 2025-2026 income eligibility guidelines sheet)",
    "us-ga": "11 policies on the index answer 404/403 on the publisher (incl. eligibility criteria, physical presence, notice of ineligibility, fair hearing)",
    "us-wa": "27 post-PHE guidance PDFs and 25 revision tables not taken",
    "us-va": "appendices 12 and glossary not taken",
    "us-me": "appendix files 79 not taken",
    "us-wv": "attachment PDFs 117 not taken",
    "us-dc": "57 lettered attachments and 2 clinical manuals not taken",
    "us-or": "23 WIC Policy Update release notes not taken",
    "us-ky": "Summary of Policy Changes FY 25 not taken",
    "us-ri": "73 other PDFs on the program page (forms, food lists) not taken",
}


def best_hit(rows, regex, exclude=None):
    """Strongest match: the row with the most matches (ties: longer body), so on-topic policies beat passing
    mentions. `exclude` is a regex that disqualifies a match when it appears in the +-200 char window."""
    rx = re.compile(regex, re.I | re.S)
    ex = re.compile(exclude, re.I | re.S) if exclude else None
    best = None
    for r in rows:
        b = r.get("body") or ""
        if not b:
            continue
        ms = [m for m in rx.finditer(b)]
        if ex:
            ms = [m for m in ms if not ex.search(b[max(0, m.start() - 200):m.end() + 200])]
        if not ms:
            continue
        m = ms[0]
        score = (min(len(ms), 50), min(len(b), 20000))
        if best is None or score > best[0]:
            s0 = max(0, m.start() - 60)
            snippet = re.sub(r"\s+", " ", b[s0:m.end() + 80]).strip()
            best = (score, r, snippet)
    if best is None:
        return None, None
    return best[1], best[2]


def rulespec_index(root: Path):
    """Set of rulespec-us source paths that exist as encodings (us/statutes/7/..., us/regulations/7-cfr/...)."""
    idx = set()
    for base in ("us/statutes/7", "us/regulations/7-cfr", "us/policies/usda"):
        p = root / base
        if not p.exists():
            continue
        for f in p.rglob("*.yaml"):
            if f.name.endswith(".test.yaml"):
                continue
            rel = f.relative_to(root).with_suffix("")
            idx.add(str(rel))
    cited = set()
    for f in root.glob("programs/*/snap/*.yaml"):
        d = yaml.safe_load(open(f)) or {}
        for k in ("federal", "state"):
            for c in (d.get("scope") or {}).get(k, []) or []:
                cited.add((f.parent.parent.name, c))
    return idx, cited


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, type=Path)
    ap.add_argument("--selector", required=True, type=Path)
    ap.add_argument("--queues", required=True, type=Path)
    ap.add_argument("--rulespec", type=Path, default=None)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    selector = load_selector(args.selector)
    eff = effective_scopes(selector)
    cq = {r["jurisdiction"]: r for r in yaml.safe_load(open(args.queues / "snap-completion-agent-queue.yaml"))["states"]}
    wq = {r["jurisdiction"]: r for r in yaml.safe_load(open(args.queues / "wic-agent-queue.yaml"))["states"]}
    sq = {r["jurisdiction"]: r for r in yaml.safe_load(open(args.queues / "state-snap-manual-agent-queue.yaml"))["states"]}
    rs_idx, rs_cited = rulespec_index(args.rulespec) if args.rulespec else (set(), set())

    scope_rows = {}

    def rows_for(scopes, j):
        out = []
        for dc, v in scopes:
            key = (j, dc, v)
            if key not in scope_rows:
                scope_rows[key] = load_rows(args.corpus, j, dc, v)
            out.extend(scope_rows[key])
        return out

    snap_scopes = {j: snap_scopes_for(j, eff) for j in JURISDICTIONS}
    wic_scopes = {j: wic_scopes_for(j, eff) for j in JURISDICTIONS}

    def rs_flag(kind, sec, sub=None):
        """rulespec-us cross-check: an encoding file exists, or a state program spec cites the path."""
        if kind == "usc":
            path = f"us/statutes/7/{sec}" + (f"/{sub}" if sub else "")
            cite = f"statutes/7/{sec}" + (f"/{sub}" if sub else "")
        else:
            part, s = sec.split(".")
            path = f"us/regulations/7-cfr/{part}/{s}"
            cite = f"regulations/7-cfr/{part}/{s}"
        enc = any(p == path or p.startswith(path + "/") for p in rs_idx)
        citers = sorted({j for j, c in rs_cited if c == cite or c.startswith(cite + "/")})
        if enc and citers:
            return f"yes (encoded; cited by {', '.join(citers)})"
        if enc:
            return "yes (encoded)"
        if citers:
            return f"cited by {', '.join(citers)} (no encoding file)"
        return "no"

    # ---------------- build element lists
    def cfr_section_elements(parts, program):
        els = []
        for part in parts:
            label, secs = CFR_STRUCTURE[part]
            for sec, heading, res in secs:
                if res:
                    continue
                p, s = sec.split(".")
                pe = CFR_SECTION_PE.get(sec, "no")
                els.append({
                    "id": f"{program}_cfr_{sec.replace('.', '_')}", "label": f"7 CFR {sec} {heading}", "level": "federal_regulation",
                    "family": "federal_regulation", "authority": f"7 CFR {sec}", "citation_path": f"us/regulation/7/{p}/{s}",
                    "pe_modeled": pe, "rulespec_scoped": rs_flag("cfr", sec), "check": "citation_path row with body (or paragraph children with bodies)",
                })
        return els

    snap_elements = []
    for sec, heading in USC7_SECTIONS:
        snap_elements.append({"id": f"snap_usc_{sec}", "label": f"7 USC {sec} {heading}", "level": "federal_statute", "family": "federal_statute",
                              "authority": f"7 USC {sec}", "citation_path": f"us/statute/7/{sec}", "pe_modeled": USC7_SECTION_PE.get(sec, "no"),
                              "rulespec_scoped": rs_flag("usc", sec), "check": "citation_path row with body"})
    for sec, sub, heading, level, pe in USC7_SUBSECTIONS:
        snap_elements.append({"id": f"snap_usc_{sec}_{sub}", "label": f"7 USC {sec}({sub}) {heading}", "level": level, "family": "federal_statute",
                              "authority": f"7 USC {sec}({sub})", "citation_path": f"us/statute/7/{sec}/{sub}", "pe_modeled": pe,
                              "rulespec_scoped": rs_flag("usc", sec, sub), "check": "citation_path row with body"})
    snap_elements += cfr_section_elements([str(p) for p in range(271, 286)], "snap")
    for suf, sec, label, level, rx, pe in CFR273_PARAGRAPHS:
        p, s = sec.split(".")
        snap_elements.append({"id": f"snap_cfr_{sec.replace('.', '_')}_{suf}", "label": f"7 CFR {label}", "level": level, "family": "federal_regulation",
                              "authority": f"7 CFR {label.split(' ')[0]}", "citation_path": f"us/regulation/7/{p}/{s}", "regex": rx, "pe_modeled": pe,
                              "rulespec_scoped": rs_flag("cfr", sec), "check": "regex over the section body (selected 273 scopes are section-granular)"})
    for eid, label, rx, pe, idx in SNAP_FED_GUIDANCE:
        snap_elements.append({"id": eid, "label": label, "level": "federal_guidance", "family": "fns_guidance", "authority": "FNS/FNA guidance",
                              "regex": rx, "pe_modeled": pe, "rulespec_scoped": "yes (fy-2026-cola policies)" if eid in ("snap_g01", "snap_g02", "snap_g03", "snap_g06", "snap_g07") else "no",
                              "publisher_index": idx, "check": "regex over selected federal guidance bodies"})
    for eid, label, root, fam, mand, rx, pe, rs in SNAP_STATE_ELEMENTS:
        snap_elements.append({"id": eid, "label": label, "level": "state", "family": fam, "authority": root, "mandatory": mand, "regex": rx,
                              "pe_modeled": pe, "rulespec_scoped": rs, "check": "regex over the jurisdiction's selected SNAP scope bodies" if rx else "queue row / run-note inventory (no corpus family exists)"})

    wic_elements = []
    for sub, heading, level, pe in USC1786:
        wic_elements.append({"id": f"wic_usc_1786_{sub}", "label": f"42 USC 1786({sub}) {heading}", "level": level, "family": "federal_statute",
                             "authority": f"42 USC 1786({sub})", "citation_path": f"us/statute/42/1786/{sub}", "pe_modeled": pe, "rulespec_scoped": "no",
                             "check": "citation_path row with body"})
    wic_elements += cfr_section_elements(["246"], "wic")
    for row in CFR246_PARAGRAPHS:
        suf, cp, label, level, pe = row[:5]
        rx = row[5] if len(row) > 5 else None
        el = {"id": f"wic_cfr_246_{suf}", "label": f"7 CFR {label}", "level": level, "family": "federal_regulation",
              "authority": f"7 CFR {label.split(' ')[0]}", "citation_path": cp, "pe_modeled": pe,
              "rulespec_scoped": rs_flag("cfr", "246." + cp.split("/")[4]),
              "check": "citation_path row with body (or paragraph children with bodies)"}
        if rx:
            el["regex"] = rx
            el["check"] = "regex over the section body (246.4, 246.10 and 246.12 have no paragraph rows in the scope)"
        wic_elements.append(el)
    for eid, label, rx, pe, idx in WIC_FED_GUIDANCE:
        wic_elements.append({"id": eid, "label": label, "level": "federal_guidance", "family": "fns_guidance", "authority": "FNS/FNA guidance",
                             "regex": rx, "pe_modeled": pe, "rulespec_scoped": "no", "publisher_index": idx, "check": "regex over selected federal guidance bodies"})
    for eid, label, root, fam, mand, rx, pe, rs in WIC_STATE_ELEMENTS:
        wic_elements.append({"id": eid, "label": label, "level": "state", "family": fam, "authority": root, "mandatory": mand, "regex": rx,
                             "pe_modeled": pe, "rulespec_scoped": rs, "check": "regex over the jurisdiction's selected WIC scope bodies" if rx else "queue row / run-note inventory (no corpus family exists)"})

    # ---------------- federal checks
    def federal_check(el, rows):
        if "citation_path" in el and not el.get("regex"):
            cp = el["citation_path"]
            for r in rows:
                if r["citation_path"] == cp and (r.get("body") or "").strip():
                    return "PRESENT", r["version"], cp, f"section row present in {r['version']}, body {len(r['body'])} chars"
            kids = [r for r in rows if r["citation_path"].startswith(cp + "/") and (r.get("body") or "").strip()]
            if kids:
                return "PRESENT", kids[0]["version"], kids[0]["citation_path"], f"{len(kids)} child rows with bodies under {cp} in {kids[0]['version']}"
            return None, None, None, None
        if "citation_path" in el and el.get("regex"):
            cp = el["citation_path"]
            secs = [r for r in rows if r["citation_path"] == cp and (r.get("body") or "").strip()]
            if not secs:
                return None, None, None, f"section row {cp} absent"
            r, snip = best_hit(secs, el["regex"])
            if r:
                return "PRESENT", r["version"], cp, f"regex {el['regex']!r} matched in the {cp} body ({r['version']}): {snip[:200]}"
            return "REVIEW", secs[0]["version"], cp, f"section {cp} present ({len(secs[0]['body'])} chars) but regex {el['regex']!r} did not match; paragraph not verified"
        grows = [r for r in rows if r.get("document_class") == "guidance"]
        if el["id"] in HEADING_CHECK:
            exc = HEADING_CHECK[el["id"]]
            docs = [r for r in grows if r.get("kind") == "document" and r.get("level", 1) <= 1 and re.search(el["regex"], r.get("heading") or "", re.I)
                    and not (exc and re.search(exc, r.get("heading") or "", re.I))]
            if docs:
                return "PRESENT", docs[0]["version"], docs[0]["citation_path"], f"{len(docs)} document heading(s) match {el['regex']!r}: {docs[0].get('heading')!r}"
            held = [r.get("heading") for r in grows if r.get("kind") == "document" and r.get("level", 1) <= 1][:12]
            return None, None, None, f"no document heading matches {el['regex']!r} (excluding {exc!r}); guidance documents held: {held}"
        if el["id"] in FY2026_ONLY:
            grows = [r for r in grows if "fy2024" not in r["version"]]
        r, snip = best_hit(grows, el["regex"])
        if r:
            return "PRESENT", r["version"], r["citation_path"], f"regex {el['regex']!r} matched in {r['citation_path']} ({r['version']}): {snip[:200]}"
        return None, None, None, None

    def federal_gap(program, el):
        if el["family"] == "federal_statute":
            if program == "wic":
                return "EXTRACTABLE", "", "", "42 USC 1786 is in no selected scope (no us/statute/42/1786 row in any corpus JSONL); uscode.house.gov serves it and the corpus already holds 7 USC ch. 51 and 42 USC titles from the same publisher (us/statute/2026-07-19-rulespec-title-42-consolidated)"
            return "REVIEW", "", "", "row absent from us/statute/2026-07-22-rulespec-title-7-consolidated"
        if el["family"] == "federal_regulation":
            return "EXTRACTABLE", "", "", "part in no selected scope (selected federal scopes hold 7 CFR 246, 247, 273 and 275 only); eCFR title 7 chapter II subchapter C lists it (structure API read 2026-09-12); same extractor as us/regulation/2026-06-15-title-7-part-275"
        idx = el.get("publisher_index")
        if idx:
            st = "REVIEW" if el["id"] == "snap_g16" else "EXTRACTABLE"
            return st, "", "", f"no selected federal scope carries it (regex {el['regex']!r} over {len([1 for k in scope_rows if k[0]=='us'])} federal scopes); publisher lists it: {idx}"
        return "REVIEW", "", "", f"no selected federal scope matched regex {el['regex']!r}; publisher index not inventoried for this family"

    hits = {"snap": [], "wic": []}

    def write(program, elements, scopes, state_rule):
        matrix = []
        us_rows = rows_for(scopes["us"], "us")
        us_status = {}
        for el in elements:
            if el["level"] == "state":
                continue
            st, ver, cp, note = federal_check(el, us_rows)
            if st is None:
                st, ver, cp, note = federal_gap(program, el)
            us_status[el["id"]] = (st, ver, cp, note)
            if st == "PRESENT":
                hits[program].append({"jurisdiction": "us", "element": el["id"], "citation_path": cp, "version": ver, "note": note})
            matrix.append(["us", el["id"], el["level"], el["family"], st, ver or "", cp or "", el["pe_modeled"], note])
        for j in STATES:
            jrows = rows_for(scopes[j], j)
            for el in elements:
                if el["level"] != "state":
                    st, ver, cp, note = us_status[el["id"]]
                    matrix.append([j, el["id"], el["level"], el["family"], "INHERITED", ver or "", cp or "", el["pe_modeled"], f"federal-level element; the us row is {st}"])
                    continue
                if el.get("regex"):
                    r, snip = best_hit(jrows, el["regex"], EXCLUDE.get(el["id"]))
                    if r:
                        note = f"regex matched in {r['citation_path']} ({r['version']}): {snip[:220]}"
                        hits[program].append({"jurisdiction": j, "element": el["id"], "citation_path": r["citation_path"], "version": r["version"], "note": note})
                        matrix.append([j, el["id"], "state", el["family"], "PRESENT", r["version"], r["citation_path"], el["pe_modeled"], note])
                        continue
                st, ver, cp, note = state_rule(j, el, scopes[j], len(jrows))
                matrix.append([j, el["id"], "state", el["family"], st, ver, cp, el["pe_modeled"], note])
        return matrix

    # ---------------- SNAP state gap rule
    def snap_state_rule(j, el, jscopes, nrows):
        fam = el["family"]
        row = cq.get(j)
        blocked = j in SNAP_BLOCKED
        inventoried = bool(row and row.get("index_families"))
        checked = f"searched {nrows} provisions of {len(jscopes)} SNAP scope(s) {[v for _, v in jscopes]} for regex {el.get('regex')!r}: no match" if el.get("regex") else ""
        if el["id"] == "snap_s31":
            docs = [r for r in rows_for(jscopes, j) if r["kind"] in ("document", "section") and SNAP_ET_PLAN_HEADING.search(r.get("heading") or "")]
            if docs:
                d = docs[0]
                kids = [r for r in rows_for(jscopes, j) if r["citation_path"].startswith(d["citation_path"]) and (r.get("body") or "").strip()]
                return "PRESENT", d["version"], d["citation_path"], f"document heading {d.get('heading')!r} with {len(kids)} body rows"
            pub = SNAP_ET_PLAN_PUBLISHER.get(j)
            return "EXTRACTABLE", "", "", (f"state publisher lists it: {pub}. " if pub else "") + "FNS posts every state's SNAP E&T State Plan (fns.usda.gov/snap/et/plans; FNA front door 403, origin host fns-prod.azureedge.us serves). No corpus scope carries an E&T plan."
        if el["id"] == "snap_s32":
            secs = [r for r in rows_for(jscopes, j) if SNAP_PLAN_OF_OPERATION_HEADING.search(r.get("heading") or "")]
            if secs:
                return "REVIEW", secs[0]["version"], secs[0]["citation_path"], f"manual section {secs[0].get('heading')!r} describes the state plan of operation; the plan itself and its option attachments are not in the corpus and FNS does not post them"
            if j in SNAP_STATE_PLAN_ATTACHMENT_PUBLISHER:
                return "EXTRACTABLE", "", "", f"publisher lists a 272.2 plan attachment, not taken: {SNAP_STATE_PLAN_ATTACHMENT_PUBLISHER[j]}"
            if blocked:
                return "OUTREACH", "", "", f"publisher index unreadable: {SNAP_BLOCKED[j]}; plan of operation not inventoried"
            if inventoried:
                fams = ", ".join(f"{k} {v.get('found')}" for k, v in row["index_families"].items())
                return "ABSENT", "", "", f"publisher SNAP index inventoried family-by-family in the #680 completion pass ({row['index_url']}): {fams}; no 272.2 plan of operation listed. FNS does not post state plans of operation"
            return "REVIEW", "", "", "publisher index not inventoried family-by-family (state not in the #680 completion queue; original 2026-05/07 discovery recorded the manual only); 272.2 plans are not routinely published and FNS does not post them"
        if blocked:
            return "OUTREACH", "", "", f"{checked}; {SNAP_BLOCKED[j]}"
        fed_note = " The FY 2026 federal value is PRESENT at the federal level (snap_g01-g09), so the encoder is not blocked on the figure; the state's own applied table was not found." if fam == "state_table_or_transmittal" else ""
        if el.get("mandatory"):
            if j in SNAP_TRANSMITTAL_FAMILY:
                return "EXTRACTABLE", "", "", f"{checked}; publisher lists an untaken table/transmittal/directive family that may carry it: {SNAP_TRANSMITTAL_FAMILY[j]}.{fed_note}"
            if inventoried:
                return "REVIEW", "", "", f"{checked}; manual index recorded complete family-by-family, no untaken policy family listed; the regex may miss the state's wording or the value lives in a chart, so a reader must confirm.{fed_note}"
            return "REVIEW", "", "", f"{checked}; publisher index not inventoried family-by-family (state not in the #680 completion queue).{fed_note}"
        complete = (row and row.get("queue_status") in ("done", "agent_ready")) or (sq.get(j, {}).get("queue_status") == "published_current")
        if inventoried:
            fams = ", ".join(f"{k} {v.get('found')}" for k, v in row["index_families"].items())
            return "ABSENT", "", "", f"{checked}; publisher index inventoried family-by-family ({row['index_url']}: {fams}) and no rulebook text carries this optional election (not elected, or elected only in an untaken transmittal)"
        if complete:
            return "REVIEW", "", "", f"{checked}; rulebook recorded published_current in the 2026-05/07 discovery but the publisher index was not inventoried family-by-family, so absence of the election cannot be confirmed"
        return "REVIEW", "", "", checked

    # ---------------- WIC state gap rule
    def wic_state_rule(j, el, jscopes, nrows):
        row = wq.get(j, {})
        cls = WIC_BLOCK_CLASS.get(j)
        checked = f"searched {nrows} provisions of {[v for _, v in jscopes]} for regex {el.get('regex')!r}: no match" if el.get("regex") and jscopes else ""
        inv = row.get("index_inventory") or {}
        invs = ", ".join(f"{k} {v}" for k, v in inv.items() if not isinstance(v, list)) if inv else ""
        if el["id"] == "wic_s30":
            if j in WIC_STATE_PLAN_PUBLISHER:
                return "EXTRACTABLE", "", "", f"publisher posts the state plan family, not taken: {WIC_STATE_PLAN_PUBLISHER[j]}"
            if cls == "OUTREACH":
                return "OUTREACH", "", "", f"publisher blocked ({row.get('index_url')}): {str(row.get('notes', ''))[:220]}"
            return "REVIEW", "", "", f"state plan family not inventoried by the WIC queue (manual family only; index {row.get('index_url')}); FNS does not post state plans"
        if el["id"] == "wic_s31":
            if j in WIC_STATE_RULE_PUBLISHER:
                return "EXTRACTABLE", "", "", f"publisher lists it, not taken: {WIC_STATE_RULE_PUBLISHER[j]}"
            return "REVIEW", "", "", "state administrative-code WIC chapter not inventoried by the WIC queue (manual family only); whether the state codifies WIC is unverified"
        if not jscopes:
            if cls == "OUTREACH":
                return "OUTREACH", "", "", f"no WIC scope; publisher block recorded in the queue ({row.get('index_url')}): {str(row.get('notes', ''))[:260]}"
            if cls == "ABSENT":
                return "ABSENT", "", "", f"no WIC scope; publisher posts no policy manual ({row.get('index_url')}): {str(row.get('notes', ''))[:260]}"
            return "REVIEW", "", "", "no WIC scope and no queue classification"
        if j in WIC_PARTIAL and el["id"] not in ("wic_s23",):
            return "ABSENT", "", "", f"{checked}; {WIC_PARTIAL[j]} ({row.get('index_url')})"
        untaken = WIC_NOT_TAKEN_FAMILY.get(j)
        if el.get("mandatory"):
            if untaken:
                return "EXTRACTABLE", "", "", f"{checked}; publisher index ({row.get('index_url')}: {invs}) lists untaken items that may carry it: {untaken}"
            return "REVIEW", "", "", f"{checked}; manual index ({row.get('index_url')}: {invs}) recorded complete; the regex may miss the state's wording"
        return "ABSENT", "", "", f"{checked}; manual index ({row.get('index_url')}: {invs}) recorded complete and no policy text carries this optional provision"

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for program, elements, scopes, rule in (("snap", snap_elements, snap_scopes, snap_state_rule), ("wic", wic_elements, wic_scopes, wic_state_rule)):
        matrix = write(program, elements, scopes, rule)
        with open(out / f"{program}-matrix.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["jurisdiction", "element", "level", "family", "status", "scope_version", "citation_path", "pe_modeled", "evidence_note"])
            w.writerows(matrix)
        with open(out / f"{program}-hits.jsonl", "w") as fh:
            for h in hits[program]:
                fh.write(json.dumps(h) + "\n")
        pe_gap = [e for e in elements if str(e["pe_modeled"]).startswith("no")]
        schema = {
            "program": program, "generated": started, "generator": "docs/coverage/needs-closure-2026-09-11/check_snap_wic.py",
            "element_count": len(elements),
            "levels": {"federal_statute": "set by Congress; inherited by every state", "federal_regulation": "set by USDA; inherited; sections carrying a state option are marked federal_with_state_option and have state-level children",
                       "federal_guidance": "FNS/FNA annual tables and memos; inherited", "state": "state-set value or state election, carried by the state's own rulebook family"},
            "families": ["federal_statute", "federal_regulation", "fns_guidance", "state_manual_or_regulation", "state_table_or_transmittal", "state_plan", "state_statute", "state_regulation"],
            "notes": SCHEMA_NOTES[program],
            "policyengine_cross_check": {"elements_pe_does_not_model": len(pe_gap), "ids": [e["id"] for e in pe_gap]},
            "elements": elements,
        }
        with open(out / f"{program}-schema.yaml", "w") as fh:
            yaml.safe_dump(schema, fh, sort_keys=False, width=200, allow_unicode=True)
        counts = Counter(r[4] for r in matrix)
        by_j = defaultdict(Counter)
        by_el = defaultdict(Counter)
        for r in matrix:
            by_j[r[0]][r[4]] += 1
            by_el[r[1]][r[4]] += 1
        results[program] = {"elements": len(elements), "cells": len(matrix), "status_counts": dict(counts),
                            "by_jurisdiction": {j: dict(c) for j, c in by_j.items()}, "by_element": {e: dict(c) for e, c in by_el.items()},
                            "scopes": {j: [f"{dc}/{v}" for dc, v in scopes[j]] for j in JURISDICTIONS},
                            "pe_not_modeled": len(pe_gap)}
    results["timing"] = {"started": started, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "elapsed_seconds": round(time.time() - t0, 1),
                         "scopes_loaded": len(scope_rows), "rows_loaded": sum(len(v) for v in scope_rows.values())}
    json.dump(results, open(out / "summary.json", "w"), indent=1)
    print(json.dumps({k: (v["status_counts"] if isinstance(v, dict) and "status_counts" in v else v) for k, v in results.items()}, indent=1))


USC7_SECTION_PE = {"2012": "partial (definitions: elderly/disabled, household via snap_unit, TFP)", "2014": "partial (a,c,d,e,g,m,n: categorical eligibility, income tests, exclusions, deductions, resources)",
                   "2015": "partial (d,e,f,o: work requirements, students, immigrants, ABAWD; not IPV/quit/felony detail)", "2017": "partial (a,c: allotment, minimum benefit, proration)"}
CFR_SECTION_PE = {
    "273.1": "partial (snap_unit / household concept)", "273.2": "partial (j: categorical eligibility incl. BBCE)",
    "273.4": "partial (eligible_immigration_statuses, ineligible-member proration)",
    "273.5": "partial (student rules)", "273.7": "partial (general work requirements, E&T hours)",
    "273.8": "partial (asset limit; vehicle rules not modeled)", "273.9": "partial (income sources, standard/earned/medical/shelter/utility/child-support deductions)",
    "273.10": "partial (gross/net tests, max/min allotment, proration)", "273.11": "partial (ineligible member income counting, self-employment)",
    "273.24": "partial (ABAWD time limit, waived areas, discretionary exemptions)",
    "246.2": "partial (definitions used by wic_category)", "246.7": "partial (categorical, income 185% FPG, nutritional risk flag)",
    "246.10": "partial (food package value, CVB amounts)",
}
SCHEMA_NOTES = {
    "snap": [
        "Federal statute elements are every section of 7 USC ch. 51 (2011-2036d; 2030 and 2033 are repealed container rows) plus every subsection of 2012, 2014, 2015 and 2017 and the state-plan subsections 2020(e),(i),(s) and 2025(h); 2012 subsections a-i, l, n-q, s-t, v are definitional and folded into the 2012 section element.",
        "Federal regulation elements are every non-reserved section of 7 CFR 271-285 as listed by the eCFR structure API (current edition, read 2026-09-12) plus 54 paragraph-level elements of 7 CFR 273. The selected 273 scopes are section-granular (273.2 is one 154 KB body), so paragraph elements are verified by keyword over the section body, not by citation path; 7 CFR 246 is paragraph-granular in its scope.",
        "Schema uncertainty: the paragraph-level split of 273 is a reviewer's reading of the section headings, not an exhaustive paragraph list; 273.2 (application processing) and 273.7 (work provisions) each carry more distinct facts than the elements enumerated here.",
        "Federal guidance elements: the FY 2026 COLA tables and income standards are read from the two-page FNS tables held in the corpus (the 165% table is on page 2 of the income standards); the full COLA memo, which carries the minimum benefit, is a separate document. The FY 2024 COLA memo in the corpus is excluded from the FY 2026 checks. The State Options Report is listed as a cross-check only because the queue policy forbids it as a source.",
        "State elements: 61 elements grouped by carrying family. 'mandatory' means every state's rulebook must carry the fact (a restatement or a state-set value); optional elections (BBCE, homeless deduction, SMD, TBA, CAP/ESAP, RMP, drug-felony opt-out, state-funded supplements) are ABSENT when a fully inventoried rulebook carries no text for them.",
        "Regex evidence is a keyword search of provision bodies; a PRESENT hit cites the provision that matched and a snippet. A hit shows the rulebook text carries the fact, not that the encoder can read the exact value from that row (single-block manuals such as KY, RI put a whole volume in one provision).",
        "Table elements (snap_s15-s18, s20) ask for the state's own applied FY 2026 table; the federal FY 2026 value is present at the federal level, so an ABSENT/EXTRACTABLE there is a provenance gap, not a missing fact.",
    ],
    "wic": [
        "Federal statute elements are the 19 subsections of 42 USC 1786 (a)-(s); the section is in no corpus scope, so every one is EXTRACTABLE from uscode.house.gov.",
        "Federal regulation elements are the 30 sections of 7 CFR 246 plus 25 participant-facing paragraph elements (246.7, 246.10, 246.12, 246.4, 246.9, 246.11, 246.16a). The scope us/regulation/2026-07-13-recovery-r2026-07-17-dedup is paragraph-granular only for 246.7 (231 paragraph rows); 246.4, 246.10 and 246.12 are single section bodies, so their paragraph elements are checked by keyword over the section body.",
        "Schema uncertainty: 246.10(e) food packages I-VII are one element although each package's maximum monthly allowance is a distinct fact; 246.12 vendor management (g)-(l) is one element although it carries dozens of facts an encoder of vendor rules would need. The bar for a household-facing WIC encoding is 246.7 + 246.10 + the state's income guidelines and food list; vendor and local-agency elements are recorded for completeness.",
        "State elements: 31, of which 29 are checked by regex over the state's WIC policy manual scope (single_block per policy PDF, so a match cites the policy). Only 21 states have a manual scope; the other 30 inherit the queue's classification (OUTREACH for the 10 access/login blocks, ABSENT for the 20 publishers that post no manual).",
        "wic_s30 (state plan) and wic_s31 (state rule chapter) have no corpus family anywhere; the queue inventoried the manual family only, so most rows are REVIEW rather than ABSENT.",
        "PolicyEngine models WIC as eligibility (category, 185% income test, nutritional risk flag) plus a food-package value and the CVB; everything about certification, documentation, priority, sanctions, vendors, nutrition education and issuance is beyond it.",
    ],
}


if __name__ == "__main__":
    main()
