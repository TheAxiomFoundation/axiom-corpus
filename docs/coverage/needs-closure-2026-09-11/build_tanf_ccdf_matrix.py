#!/usr/bin/env python3
"""Needs-driven closure check for TANF and CCDF (2026-09-11).

Builds the law-derived needs schema (``<program>-schema.yaml``) and the
jurisdiction x element matrix (``<program>-matrix.csv``) for TANF and CCDF
over the federal level plus the 50 states and DC, and a ``summary.json``
with the roll-ups the ``<program>.md`` reports quote.

Read-only with respect to ``data/corpus``. Inputs:

* the draft union selector (``docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json``)
  plus ``us/regulation/2026-09-11-title-45-part-98`` (the selected scopes);
* the eCFR title-45 structure snapshot retained with the part 98 scope (every
  live section of 45 CFR 260-265 and 98);
* provision bodies under ``data/corpus/provisions`` for the selected scopes
  (and, for four TANF states, on-disk scopes that are not selected);
* the TANF and CCDF agent queues and run notes (publisher inventories, blocks),
  transcribed into the constant tables below with the row or note they come from.

Status rules (per cell):

* PRESENT only when a provision body in a *selected* scope carries the element:
  the element's strong pattern matches the provision heading, or matches the
  body at least twice. A single body mention is not enough and is reported as
  REVIEW with the candidate path in the note. The matched scope, citation_path
  and a snippet are recorded.
* EXTRACTABLE when the queue row or run note shows the publisher lists the
  carrying document and it was not taken (or was taken but is not selected).
* ABSENT when the publisher posts nothing carrying it.
* OUTREACH when the queue row records a publisher block.
* REVIEW otherwise (including "not located by pattern in a whole-rulebook scope").

Usage: python3 build_tanf_ccdf_matrix.py --base /path/to/data/corpus --repo <worktree> --out <this dir>
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import yaml

STATES = [
    "ak", "al", "ar", "az", "ca", "co", "ct", "dc", "de", "fl", "ga", "hi", "ia", "id", "il", "in",
    "ks", "ky", "la", "ma", "md", "me", "mi", "mn", "mo", "ms", "mt", "nc", "nd", "ne", "nh", "nj",
    "nm", "nv", "ny", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "va", "vt", "wa",
    "wi", "wv", "wy",
]
JURS = ["us"] + [f"us-{s}" for s in STATES]

SELECTOR = "docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json"
PART98 = ("us", "regulation", "2026-09-11-title-45-part-98")
CSV_COLUMNS = ["jurisdiction", "element", "level", "family", "status", "scope_version", "citation_path", "pe_modeled", "evidence_note"]

# --------------------------------------------------------------------------------------
# TANF: state-level rule elements (law-derived; see the schema notes for the derivation).
# Each entry: id, name, law, families, facts (what an encoder reads), patterns (strong / weak),
# unique (True = TANF-specific vocabulary, no program-alias gate needed in combined manuals), pe.
# --------------------------------------------------------------------------------------
TANF_STATE_ELEMENTS = [
    dict(id="tanf-s01", name="Assistance unit composition (who must be included; mandatory and optional members)",
         law="42 U.S.C. 608(a)(1) (minor child requirement), 602(a)(1)(A)(i); 45 CFR 260.30 (family); state rulebook",
         families="state regulation/manual (assistance unit chapter); state TANF plan",
         facts=["mandatory members (parents, minor siblings and half-siblings living together)", "optional members (e.g. stepparents, other relatives)",
                "members excluded from the unit (SSI recipients, ineligible immigrants, sanctioned adults) and whether their income counts",
                "pregnant woman with no other child: eligibility and month of eligibility", "one unit per household / multiple units in a home"],
         strong=r"assistance unit|filing unit|assistance group|need group|standard filing unit|budget(?:ary)? (?:unit|group)|mandatory (?:\w+ )?(?:household|assistance unit|filing unit) members|who must be included|family composition|household (?:unit|composition)|must include",
         weak=r"household members|family members",
         unique=True, pe="partial (PE: household/spm_unit roles, max_unit_size caps; no unit-composition rules)"),
    dict(id="tanf-s02", name="Dependent child age limit and student extension",
         law="42 U.S.C. 608(a)(1), 619(2) (minor child); state rulebook",
         families="state regulation/manual; state TANF plan",
         facts=["age limit for a dependent child (under 18)", "extension to age 18 (or 19) for a full-time secondary/vocational student", "expected-to-graduate rule and month the child ages out"],
         strong=r"(?:minor|dependent|eligible) child(?:ren)?[^.]{0,80}under (?:the )?age (?:of )?(?:18|19|eighteen|nineteen)|(?:minor|dependent|eligible) child(?:ren)?[^.]{0,80}(?:has|have|had) not (?:attained|reached) (?:age |the age of )?(?:18|19|eighteen)|(?:age|aged) (?:18|19|eighteen)[^.]{0,80}(?:full[- ]time student|secondary school|high school|expected to (?:graduate|complete))|under (?:the )?age (?:of )?(?:18|eighteen)[^.]{0,120}(?:full[- ]time student|secondary school|high school|graduat)",
         weak=r"full[- ]time student|secondary school",
         unique=False, pe="yes (age_limit / minor_child / student_dependent parameters in gov/hhs/tanf and many states)"),
    dict(id="tanf-s03", name="Relationship to caretaker relative and living-with requirement",
         law="42 U.S.C. 602(a)(1)(A) (needy families), 608(a)(1); state rulebook",
         families="state regulation/manual",
         facts=["degrees of relationship that qualify a caretaker relative (blood, marriage, adoption; fifth degree etc.)", "child must live in the home of the relative", "legal guardians / non-relative caretakers accepted or not"],
         strong=r"specified relative|caretaker relative|degree of relationship|relative caretaker|within the (?:fifth|5th) degree|blood,? marriage,? or adoption|relationship (?:requirement|to the child)",
         weak=r"living with|relative",
         unique=True, pe="no"),
    dict(id="tanf-s04", name="Citizenship and immigrant eligibility (qualified alien, five-year bar, state option)",
         law="8 U.S.C. 1612-1613 (PRWORA title IV), 42 U.S.C. 608(f); state option",
         families="state regulation/manual; state TANF plan",
         facts=["qualified-immigrant categories eligible", "five-year bar applied or waived (state option) and exempt classes (refugees, asylees, veterans)", "state-funded assistance for barred immigrants", "sponsor deeming rules"],
         strong=r"qualified (?:alien|non-?citizen|immigrant)|five[- ]year bar|5[- ]year bar|lawful(?:ly admitted)? permanent resident|refugee|asylee|sponsor(?:ed|'s) (?:alien|non-?citizen|income)|PRWORA",
         weak=r"citizenship|immigration status|non-?citizen",
         unique=False, pe="partial (gov/hhs/tanf/bar_exempt_immigration_statuses, five_year_bar_years; CA, IL, MT status lists)"),
    dict(id="tanf-s05", name="Need standard (standard of need) by family size and region",
         law="42 U.S.C. 602(a)(1)(B)(i) (objective criteria for need); state rulebook",
         families="state regulation/manual; payment/need standard tables",
         facts=["need standard amount by assistance-unit size", "regional / shelter / county-group variants", "increment for each additional member beyond the table"],
         strong=r"standard of need|need standards?|standards? of assistance|basic standard of adequate care|budgetary needs?|monthly income standards|need level",
         weak=r"needs? standard",
         unique=True, pe="yes (need_standard / standard_of_need in most state trees)"),
    dict(id="tanf-s06", name="Payment standard / maximum grant by family size and region",
         law="42 U.S.C. 602(a)(1)(B)(i); state rulebook",
         families="state regulation/manual; payment standard tables and transmittals",
         facts=["maximum grant / payment standard by unit size", "regional or county-group tables", "adult-included vs child-only tables", "ratable reduction or percentage-of-need factor", "effective date of the current table"],
         strong=r"payment standards?|maximum (?:aid )?payment|payment levels?|maximum (?:monthly )?benefit|grant standard|maximum grant|family maximum|payment amounts?|maximum (?:monthly )?(?:grant|allowance|assistance)|amount of assistance|transitional standard|family wage level",
         weak=r"benefit amount",
         unique=True, pe="yes (payment_standard / maximum_benefit / grant_standard in most state trees)"),
    dict(id="tanf-s07", name="Income eligibility tests for applicants and recipients (gross/net limits)",
         law="42 U.S.C. 602(a)(1)(B)(i); state rulebook",
         families="state regulation/manual",
         facts=["applicant gross income test threshold (e.g. 185% of need, 100% of standard)", "recipient / ongoing income test", "net income test against the payment standard", "prospective vs retrospective budgeting period"],
         strong=r"gross income (?:test|limit|ceiling|eligibility|standard)|185\s?(?:%|percent)|net income (?:test|eligibility)|income (?:eligibility )?(?:test|limit|ceiling|standard)s?|(?:applicant|recipient) (?:income )?test|financial eligibility (?:determination|test)|100 percent (?:of the )?(?:income )?standard",
         weak=r"income limit",
         unique=False, pe="yes (gross_income_limit / fpg_limit / income_limit parameters)"),
    dict(id="tanf-s08", name="Earned income disregards (applicant and recipient; flat and percentage)",
         law="42 U.S.C. 602(a)(1)(B)(i); state rulebook",
         families="state regulation/manual",
         facts=["applicant disregard (flat and/or percentage)", "recipient disregard and any time limit on it", "work expense / standard employment deduction", "order of application"],
         strong=r"earned income disregards?|work incentive (?:disregard|deduction|payment)|\$30 (?:and|plus) (?:one[- ]third|1/3)|standard work (?:expense|deduction)|earned income deductions?|earned income (?:exclusion|exemption)|(?:disregard|deduct)(?:ed|ing)? .{0,40}(?:percent|%) of (?:the )?(?:gross )?earned income|work expense (?:deduction|disregard|allowance)",
         weak=r"disregard",
         unique=True, pe="yes (earned_income_disregard / work_expense parameters in most state trees)"),
    dict(id="tanf-s09", name="Child support assignment, cooperation, pass-through and disregard",
         law="42 U.S.C. 608(a)(2), 608(a)(3), 657(a); 45 CFR 264.30-264.31; state option on pass-through",
         families="state regulation/manual; state TANF plan",
         facts=["assignment of support rights as a condition of aid", "cooperation with IV-D and good-cause exceptions", "sanction for non-cooperation (at least 25% or case closure)", "pass-through amount and disregard amount"],
         strong=r"child support (?:cooperation|enforcement|pass[- ]?through|disregard|assignment|referral|services)|assignment of (?:support )?rights|IV-?D|good cause (?:for )?(?:not )?cooperat|paternity",
         weak=r"child support",
         unique=True, pe="partial (child_support deduction/disregard/passthrough in AK, CT, DC, DE, ME, MN, NJ, NM, OR, RI, TX, WV; no cooperation sanction)"),
    dict(id="tanf-s10", name="Dependent care and work-related expense deductions",
         law="state rulebook (42 U.S.C. 602(a)(1)(B)(i))",
         families="state regulation/manual",
         facts=["dependent care deduction caps by child age and hours worked", "work-related expense allowance", "whether the deduction applies to applicants, recipients or both"],
         strong=r"dependent care (?:deduction|disregard|expense|allowance)|child care (?:deduction|disregard|expense|allowance|costs? (?:deduction|disregard))|work[- ]related expenses?|day care (?:deduction|expense)",
         weak=r"dependent care|child care",
         unique=False, pe="yes (dependent_care / child_care / work_expense deductions in many state trees)"),
    dict(id="tanf-s11", name="Resource (asset) limit and countable/excluded resources",
         law="state rulebook (42 U.S.C. 602(a)(1)(B)(i)); 45 CFR 263.20-263.23 (IDAs excluded)",
         families="state regulation/manual",
         facts=["resource limit amount (applicant / recipient; with or without an elderly member)", "countable resources", "excluded resources (home, IDAs, retirement, burial)", "restricted accounts and savings exclusions"],
         strong=r"resource limit|asset limit|resources? (?:may|shall|must|can ?not|cannot|do(?:es)? not) (?:not )?exceed|assets? (?:may|shall|must|cannot) (?:not )?exceed|countable resources|resource (?:eligibility|test|standard)|\$\d[\d,]* (?:in |of )?(?:countable |liquid )?(?:resources|assets)",
         weak=r"resources|assets",
         unique=False, pe="yes (resource_limit / asset_limit / resources parameters in most state trees)"),
    dict(id="tanf-s12", name="Vehicle exclusion / equity limit",
         law="state rulebook",
         families="state regulation/manual",
         facts=["number of vehicles excluded (one / one per adult / all)", "equity or fair-market-value limit for counted vehicles", "vehicles excluded for work, disability or income production"],
         strong=r"(?:one|1|first) (?:motor )?vehicle|vehicles? (?:is|are|shall be) (?:excluded|exempt|disregarded)|equity value of (?:the |a |each |one )?(?:motor )?vehicle|fair market value of (?:the |a |each |one )?(?:motor )?vehicle|vehicle (?:exclusion|exemption|equity)|motor vehicles?",
         weak=r"vehicle|automobile",
         unique=False, pe="partial (vehicle limits in CA, IN, TX, WI, gov/hhs/tanf/non_cash tx_vehicle_exemption)"),
    dict(id="tanf-s13", name="Benefit computation (deficit, proration, rounding, minimum grant)",
         law="state rulebook",
         families="state regulation/manual",
         facts=["grant = payment standard minus countable income (or ratable reduction of the deficit)", "proration of the first month", "rounding rule", "minimum grant / no payment under $10", "budgeting method (prospective, retrospective, semi-annual)"],
         strong=r"deficit|prorat(?:e|ed|ion)|minimum (?:grant|payment|benefit)|benefit (?:calculation|computation)|grant (?:computation|calculation|amount is)|computing the (?:grant|benefit|payment)|budgeting (?:method|procedure)|payments? in whole dollars|rounded (?:down|up|to the nearest)",
         weak=r"benefit amount|calculat",
         unique=False, pe="yes (benefit formulas in state variables; minimum_payment / minimum_benefit parameters)"),
    dict(id="tanf-s14", name="Lifetime time limit (60 months or shorter) and hardship extensions/exemptions",
         law="42 U.S.C. 608(a)(7) (60-month limit, 20% hardship); 45 CFR 264.1-264.3; state option for shorter limits",
         families="state regulation/manual; state TANF plan",
         facts=["lifetime limit in months (60 or a shorter state limit)", "months that do not count (child-only, minor parent, months on tribal TANF, months in Indian country)", "hardship extension criteria and caseload cap", "clock-stopping while working / in a waiver", "intermediate limits (e.g. 24 in 60)"],
         strong=r"(?:60|sixty)[- ]month (?:limit|lifetime|time|maximum|clock|period)|five[- ]year (?:limit|lifetime|time)|lifetime (?:limit|maximum)|time[- ]limits? (?:for|on|of) (?:assistance|TANF|cash|benefits|adults|the receipt)|hardship (?:exemption|extension|exception)|(?:24|36|48)[- ]month (?:limit|time|maximum|clock)|months? (?:of assistance )?count(?:ed|s|ing)? toward|countable months|time[- ]limited (?:assistance|benefits|cash)",
         weak=r"time limit",
         unique=True, pe="no (PolicyEngine has no TANF time-limit parameters)"),
    dict(id="tanf-s15", name="Work requirements: participation hours, exemptions, work-eligible individuals",
         law="42 U.S.C. 607(c)-(d), 602(a)(1)(A)(ii); 45 CFR 261.10-261.16, 261.30-261.35; state rulebook",
         families="state regulation/manual; state TANF plan; Work Verification Plan",
         facts=["required hours per week by household type (20/30/35/55)", "exemptions (caring for a child under age X, disability, caretaker of a disabled member, age)", "work-eligible individual definition", "deadline to engage in work (e.g. within 24 months)"],
         strong=r"work (?:requirements?|participation|activit(?:y|ies))|(?:20|30|35|55) hours (?:per|a|each) week|work[- ]eligible (?:individual|adult)|exempt(?:ion|ed)? from (?:the )?(?:work|participation|employment)(?: requirement)?|welfare[- ]to[- ]work|employment (?:and training )?(?:program|services) (?:requirement|participation)|hours of participation|mandatory (?:work )?participant|participation (?:requirement|hours)",
         weak=r"work program|employment program",
         unique=True, pe="partial (work hours in DC, MT, TX CCDF trees; federal variable meets_tanf_work_requirements; no exemptions)"),
    dict(id="tanf-s16", name="Countable work activities (core and non-core) and limits on education/job search",
         law="42 U.S.C. 607(d); 45 CFR 261.30-261.34; state rulebook",
         families="state regulation/manual; Work Verification Plan",
         facts=["core and non-core activity lists as the state defines them", "vocational education 12-month cap", "job search / job readiness 6-week (4 consecutive) cap", "hours caps on education for teen parents"],
         strong=r"unsubsidized employment|subsidized (?:private|public)[- ]sector employment|community service program|vocational educational training|core (?:activities|hours)|non-?core (?:activities|hours)|job search (?:and|or) job readiness|on[- ]the[- ]job training|work experience (?:program|activity|placement)",
         weak=r"work activit",
         unique=True, pe="no"),
    dict(id="tanf-s17", name="Sanctions for work non-compliance (pro-rata or full-family, duration, cure) and good cause",
         law="42 U.S.C. 607(e), 608(a)(2); 45 CFR 261.14-261.16; state rulebook",
         families="state regulation/manual; state TANF plan",
         facts=["first / second / third sanction amount (adult portion, percentage, full family)", "sanction duration and cure (compliance) period", "good cause reasons", "conciliation before sanction"],
         strong=r"sanction|full[- ]family (?:sanction|penalty|closure)|refus(?:al|es|ed|ing) to (?:participate|comply|work|engage|cooperate)|penalt(?:y|ies) for (?:non-?compliance|failure to)|non-?compliance with (?:work|participation|employment)",
         weak=r"good cause|non-?compliance",
         unique=True, pe="partial (DC work_requirement/sanction/rate only)"),
    dict(id="tanf-s18", name="Child-care exception to work sanctions for single parents of children under six",
         law="42 U.S.C. 607(e)(2); 45 CFR 261.15, 261.56-261.57; definitions set in the CCDF plan (45 CFR 98.16(v))",
         families="state regulation/manual; CCDF state plan 2.2.9",
         facts=["no sanction of a single parent of a child under six who cannot obtain child care", "definitions of appropriate, affordable and reasonable-distance child care", "how the parent documents unavailability"],
         strong=r"(?:child|children) under (?:the age of )?(?:six|6)[^.]{0,120}(?:child ?care|childcare)|(?:child ?care|childcare)[^.]{0,120}(?:child|children) under (?:the age of )?(?:six|6)|(?:appropriate|affordable|suitable) child care (?:is|was) (?:not|un)available|inability to obtain (?:needed |appropriate )?child care",
         weak=r"unavailab(?:le|ility) of child care|lack of child care",
         unique=True, pe="no"),
    dict(id="tanf-s19", name="Individual responsibility plan / assessment (state design)",
         law="42 U.S.C. 608(b); 45 CFR 261.11-261.13; state rulebook",
         families="state regulation/manual",
         facts=["assessment of skills and employability (timing)", "individual responsibility / personal responsibility plan as a condition of aid", "plan contents and modification", "penalty for refusing to sign"],
         strong=r"individual responsibility plan|personal responsibility (?:plan|agreement|contract)|self[- ]sufficiency (?:plan|agreement|contract)|employability (?:development )?plan|family (?:investment|success|employment|self[- ]sufficiency) (?:plan|agreement|contract)|employment (?:development )?plan|mutual (?:responsibility )?agreement|responsibility agreement|family (?:development )?plan|job plan|case plan|work plan|assessment (?:of|and) (?:skills|employability|work)|employability assessment",
         weak=r"\bIRP\b|\bPRP\b|\bFIA\b",
         unique=True, pe="no"),
    dict(id="tanf-s20", name="Minor (teen) parent rules: school attendance and adult-supervised living arrangement",
         law="42 U.S.C. 608(a)(4)-(5); state rulebook",
         families="state regulation/manual",
         facts=["minor parent must live with a parent or in an adult-supervised setting (exceptions)", "school attendance / diploma requirement for a minor parent", "who is the payee for a minor parent's grant"],
         strong=r"minor parent|teen(?:age)? parent|adult[- ]supervised (?:setting|living|arrangement)|unmarried (?:minor|teen)|under (?:age )?18[^.]{0,60}(?:parent|pregnant)[^.]{0,80}(?:school|live|reside)",
         weak=r"school attendance|living arrangement",
         unique=True, pe="partial (MA teen_parent age/fpg_limit; AZ teen_parent_age_limit CCAP)"),
    dict(id="tanf-s21", name="Diversion / one-time non-recurrent short-term benefits (state design)",
         law="45 CFR 260.31(b)(1) (non-assistance); state option",
         families="state regulation/manual; state TANF plan",
         facts=["diversion payment amount (e.g. N months of the grant)", "eligibility conditions", "period of ineligibility for ongoing aid after diversion", "repayment / frequency limits"],
         strong=r"diversion (?:assistance|payment|program|cash|benefit|grant|option)|diversionary|grant diversion|(?:one[- ]time|lump[- ]sum) (?:diversion|cash assistance|TANF|payment in lieu of)|prevention, retention,? and contingency|non-?recurr(?:ent|ing) short[- ]term|applicant job search|reach first|short[- ]term (?:cash )?assistance program|work diversion",
         weak=r"emergency assistance",
         unique=True, pe="no"),
    dict(id="tanf-s22", name="Child-only cases and non-needy / ineligible caretaker relatives (incl. kinship payments)",
         law="state rulebook (42 U.S.C. 608(a)(7)(A) exempts child-only from the time limit)",
         families="state regulation/manual",
         facts=["child-only case definition (non-needy caretaker, SSI parent, ineligible immigrant parent, sanctioned parent)", "payment standard for child-only units", "whether the caretaker's income is counted", "kinship / relative caregiver payment variants"],
         strong=r"child[- ]only|non-?needy (?:caretaker|relative|payee)|ineligible (?:parent|caretaker|adult)|kinship (?:care|caregiver|payment|subsidy|guardian)|payee[- ]only|excluded (?:parent|adult|caretaker)|SSI (?:parent|recipient)[^.]{0,60}(?:excluded|not included|removed)",
         weak=r"caretaker",
         unique=True, pe="partial (IL child_only payment level; TX non_caretaker standards)"),
    dict(id="tanf-s23", name="State residency and temporary absence",
         law="state rulebook (42 U.S.C. 602(a)(1)(A)(i))",
         families="state regulation/manual",
         facts=["residency and intent-to-remain requirement", "temporary absence of a child or caretaker (days allowed)", "out-of-state absence rules"],
         strong=r"resid(?:ent|ency|e|es|ing) (?:of|in) (?:the )?(?:state|commonwealth|district)|state resident|residen(?:cy|t) requirement|temporar(?:y|ily) absen(?:t|ce)|out[- ]of[- ]state",
         weak=r"residen",
         unique=False, pe="no"),
    dict(id="tanf-s24", name="Family Violence Option: screening, good-cause waivers of requirements",
         law="42 U.S.C. 602(a)(7); 45 CFR 260.50-260.59; state option",
         families="state regulation/manual; state TANF plan",
         facts=["FVO elected", "screening and referral", "waivers of time limit, work, child-support cooperation and residency for victims", "waiver duration and re-evaluation"],
         strong=r"family violence option|family violence (?:waiver|indicator|exemption)|domestic violence (?:waiver|exemption|option|screening|victim)|good cause (?:domestic|family) violence|victims? of (?:domestic|family) violence|(?:domestic|family) violence[^.]{0,80}(?:waiv|exempt|good cause)",
         weak=r"domestic violence|family violence",
         unique=True, pe="no"),
    dict(id="tanf-s25", name="Application, verification, redetermination and change reporting (procedural rules, effective dates)",
         law="42 U.S.C. 602(a)(1)(B)(iii) (fair and equitable treatment); 45 CFR 264.10 (IEVS); state rulebook",
         families="state regulation/manual",
         facts=["application date and processing deadline (30/45 days)", "interview and verification requirements", "redetermination frequency", "change-reporting threshold and deadline", "effective date of a change in benefits"],
         strong=r"redetermination|eligibility (?:review|period)|application (?:process|processing|date|form|interview)|change reporting|report(?:ing)? (?:of )?changes|verification (?:requirements?|of (?:income|eligibility|information))|effective date (?:of|for) (?:eligibility|benefits|assistance|the grant)|recertification|periodic review|IEVS|income and eligibility verification",
         weak=r"application|verification",
         unique=False, pe="no"),
    dict(id="tanf-s26", name="Notices and fair hearings / appeals",
         law="42 U.S.C. 602(a)(1)(B)(iii); state rulebook",
         families="state regulation/manual",
         facts=["adequate / timely notice period (10 days)", "hearing request deadline", "continuation of benefits pending hearing", "hearing decision timeline"],
         strong=r"fair hearing|administrative hearing|adequate (?:and timely )?notice|advance notice|notice of (?:adverse )?action|10[- ]day (?:advance )?notice|right to (?:a |an )?(?:fair |administrative )?hearing|appeal rights|hearing (?:rights|request)|timely notice",
         weak=r"hearing|appeal",
         unique=False, pe="no"),
    dict(id="tanf-s27", name="Overpayments, underpayments, recovery and intentional program violations",
         law="45 CFR 263.11 (misuse); state rulebook",
         families="state regulation/manual",
         facts=["overpayment recovery method and monthly recoupment percentage", "underpayment correction", "IPV disqualification periods (12 / 24 months / permanent)", "administrative disqualification hearing"],
         strong=r"overpayments?|recoupment|underpayments?|restitution|recover(?:y|ed|ing) (?:of |from )?(?:the )?(?:benefit|grant|assistance|overpaid)|intentional program violation|\bIPV\b|benefit recovery|claims? (?:establishment|collection)",
         weak=r"fraud|recovery",
         unique=False, pe="no"),
    dict(id="tanf-s28", name="Disqualifications: fugitive felons, drug-felony option, fraud/misrepresentation of residence",
         law="42 U.S.C. 608(a)(9) (fugitive felons), 608(a)(8) (10-year fraud bar); 21 U.S.C. 862a (drug felony, state opt-out/modify)",
         families="state regulation/manual; state TANF plan",
         facts=["fugitive felon and probation/parole violator bar", "drug-felony disqualification as adopted, opted out of or modified (treatment, testing)", "ten-year bar for fraudulent misrepresentation of residence"],
         strong=r"fleeing felon|fugitive felon|fleeing (?:to avoid|prosecution)|drug[- ]related felony|felony (?:drug|controlled substance)|controlled substance[^.]{0,60}(?:felony|conviction)|convicted[^.]{0,80}(?:felony|drug)|probation or parole violat|parole or probation violat|misrepresent(?:ed|ing|ation of) (?:their |his or her )?(?:place of )?residence|fraudulent(?:ly)? (?:misrepresent|receiv)",
         weak=r"felon|conviction",
         unique=True, pe="no"),
    dict(id="tanf-s29", name="EBT access restrictions (liquor stores, casinos, adult entertainment)",
         law="42 U.S.C. 608(a)(12); 45 CFR 264.60-264.61; state implementation",
         families="state regulation/manual; state TANF plan",
         facts=["prohibited locations and transaction types", "state penalties for misuse", "replacement card fees where charged"],
         strong=r"liquor stores?|casinos?|gambling (?:establishment|casino|facilit)|gaming (?:establishment|casino|facilit)|strip clubs?|adult[- ]oriented|adult entertainment|prohibited (?:location|establishment)|electronic benefit transfer[^.]{0,150}(?:liquor|casino|gaming|adult)|EBT[^.]{0,150}(?:liquor|casino|gaming|adult)",
         weak=r"EBT|electronic benefit transfer",
         unique=True, pe="no"),
    dict(id="tanf-s30", name="Transitional and supportive services (transitional child care, transportation, work supports, work incentive payments)",
         law="state design (45 CFR 260.31(b) non-assistance); state TANF plan",
         families="state regulation/manual; state TANF plan",
         facts=["transitional child care / benefits duration after case closure", "transportation and work-related allowances (amounts)", "work incentive / retention payments", "post-employment services"],
         strong=r"transitional (?:child ?care|benefits?|assistance|support|services|medicaid|medical)|supportive services|post[- ]employment (?:services|support)|job retention|work incentive payment|transportation (?:assistance|allowance|reimbursement|expenses?)|work[- ]related (?:supportive )?services|reach ahead|extended (?:child ?care|benefits)",
         weak=r"transportation|child care assistance",
         unique=True, pe="no"),
    dict(id="tanf-s31", name="Unearned income treatment, exclusions, deeming (stepparent, sponsor), lump sums",
         law="state rulebook (42 U.S.C. 602(a)(1)(B)(i))",
         families="state regulation/manual",
         facts=["counted unearned income", "excluded income list", "stepparent / grandparent deeming formula", "sponsor deeming", "lump-sum treatment (period of ineligibility or resource)"],
         strong=r"unearned income|excluded income|income exclusions?|income (?:is|shall be|that is|which is) (?:excluded|disregarded|not counted|exempt)|deem(?:ed|ing) (?:income|of)|stepparent(?:'s)? income|lump[- ]sum (?:income|payment)|countable (?:unearned )?income|sponsor(?:'s)? income",
         weak=r"income",
         unique=False, pe="yes (income sources: earned/unearned lists in gov/hhs/tanf/cash/income and many state trees)"),
    dict(id="tanf-s32", name="State TANF plan (42 U.S.C. 602(a)) as a certified document",
         law="42 U.S.C. 602(a) (state plan contents, certification, public comment, 3-year renewal); 45 CFR 260.40",
         families="state TANF plan (state-published; ACF OFA posts no consolidated index)",
         facts=["outline of the program and its eligibility criteria (602(a)(1)(A)-(B))", "the state's stated time-limit, work, sanction, FVO and diversion policies", "certifications and the plan period"],
         strong=r"^(?:.*\b)?(?:TANF|Temporary Assistance (?:for|to) Needy Families)\b.{0,60}\bState Plan\b|\bState Plan\b.{0,40}\b(?:TANF|Temporary Assistance)|title IV-?A state plan",
         weak=r"state plan",
         unique=True, pe="no (PE cites some plans as references only)", doc_element=True),
]

# Which selected scopes per jurisdiction carry TANF text (searched for PRESENT). All are in the union selector
# (checked 2026-09-12 against the selector JSON).
TANF_SCOPES = {
    "us-ak": [("regulation", "2026-07-01-ak-atap-regulations"), ("guidance", "2026-07-01-ak-atap-standards")],
    "us-al": [("policy", "2026-07-02-al-tanf-official-documents"), ("regulation", "2026-07-02-al-admin-code-660-2-2")],
    "us-ar": [("policy", "2026-07-02-ar-tea-official-documents")],
    "us-az": [("manual", "2025-10-30-az-des-faa5-manual-r2026-07-15-self-contained"), ("manual", "2026-07-17-faa5-recovery")],
    "us-ca": [("regulation", "2026-09-10-tanf-state-policy-manual"), ("guidance", "2026-06-24-ca-cdss-calworks-acl"),
              ("statute", "2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452-wic-11452.018")],
    "us-co": [("regulation", "2026-07-13-recovery-r2026-09-11-tanf-consolidated")],
    "us-ct": [("policy", "2026-07-02-ct-ssp-upm-and-standards")],
    "us-dc": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-de": [("regulation", "2026-07-03-de-tanf-rules")],
    "us-fl": [("manual", "2026-05-27-fl-ess-manual-r2026-07-15-self-contained")],
    "us-ga": [("manual", "2026-06-25-ga-tanf"), ("guidance", "2026-06-25-ga-tanf")],
    "us-hi": [],
    "us-ia": [("regulation", "2026-07-03-ia-fip-admin-rules")],
    "us-id": [("regulation", "2026-09-10-tanf-state-policy-manual")],
    "us-il": [("manual", "2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained")],
    "us-in": [("manual", "2026-05-27-in-snap-manual-r2026-07-15-self-contained")],
    "us-ks": [("manual", "2026-05-27-ks-keesm-r2026-07-15-self-contained")],
    "us-ky": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-la": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-ma": [("regulation", "2026-06-27-ma-tafdc-regulations")],
    "us-md": [("guidance", "2026-07-05-md-tca-2026-guidance")],
    "us-me": [("regulation", "2026-07-03-me-tanf-rule-125a")],
    "us-mi": [("manual", "2026-07-17-mi-bridges-manual")],
    "us-mn": [("manual", "2026-05-27-mn-combined-manual-r2026-07-15-self-contained")],
    "us-mo": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-ms": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-mt": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-nc": [],
    "us-nd": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-ne": [("regulation", "2026-09-10-tanf-state-policy-manual")],
    "us-nh": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-nj": [("regulation", "2026-07-13-recovery")],
    "us-nm": [("regulation", "2026-09-10-tanf-state-policy-manual")],
    "us-nv": [("manual", "2026-05-27-nv-eligibility-payments-manual-r2026-07-15-self-contained")],
    "us-ny": [("policy", "2026-08-09-ny-tanf-official-source-recovery-with-aliases")],
    "us-oh": [("regulation", "2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated")],
    "us-ok": [("regulation", "2026-09-10-tanf-state-policy-manual")],
    "us-or": [("regulation", "2026-09-10-tanf-state-policy-manual-chapter-461")],
    "us-pa": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-ri": [("regulation", "2026-09-10-tanf-state-policy-manual")],
    "us-sc": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-sd": [("regulation", "2026-09-10-tanf-state-policy-manual")],
    "us-tn": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-tx": [("manual", "2026-05-27-tx-manuals-r2026-07-15-self-contained")],
    "us-ut": [("regulation", "2026-07-02-ut-fep-official-documents"), ("manual", "2026-05-27-ut-manuals-r2026-07-15-self-contained")],
    "us-va": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-vt": [("regulation", "2026-09-10-tanf-state-policy-manual")],
    "us-wa": [("manual", "2026-07-21-wa-eaz-manual"), ("regulation", "2026-06-25-388-450-r2026-07-15-self-contained"),
              ("regulation", "2026-06-25-388-478-r2026-07-15-self-contained-r2026-07-17-dedup"),
              ("regulation", "2026-07-01-388-474-r2026-07-15-self-contained-r2026-07-17-dedup")],
    "us-wi": [("manual", "2026-09-10-tanf-state-policy-manual")],
    "us-wv": [("manual", "2026-07-21-wv-income-maintenance-manual")],
    "us-wy": [("manual", "2026-05-27-wy-manuals-r2026-07-15-self-contained")],
}

# Scopes on disk but NOT selected by the union selector (the TANF queue marks the state "done" by pointer to them;
# they were in the July foundation releases and are not in the 2026-08-23 or 2026-09-11 union selectors).
TANF_UNSELECTED = {
    "us-hi": [("regulation", "2026-07-03-hi-tanf-admin-rules")],
    "us-me": [("regulation", "2026-07-03-me-tanf-regulation")],
    "us-md": [("regulation", "2026-07-03-md-tca-comar-publication-2026-06-29-title-07-subtitle-03-chapter-03")],
    "us-nc": [("manual", "2026-07-03-nc-work-first-manual")],
}
TANF_UNSELECTED_NOTE = {
    "us-hi": "HAR 17-656/17-676/17-678 scope us-hi/regulation/2026-07-03-hi-tanf-admin-rules exists on disk (July foundation releases) but is not in the 2026-09-11 union selector; re-select or supersede",
    "us-me": "10-144 CMR ch. 331 scope us-me/regulation/2026-07-03-me-tanf-regulation exists on disk (July foundation releases) but is not in the union selector; only the Rule 125A chart is selected",
    "us-md": "COMAR 07.03.03 scope us-md/regulation/2026-07-03-md-tca-comar-... exists on disk (July foundation releases) but is not in the union selector; only IM 26-13 (benefit schedule) is selected",
    "us-nc": "Work First Manual: only section 114 (Income and Budgeting, 18 rows) was ever ingested (us-nc/manual/2026-07-03-nc-work-first-manual, unselected); the other WF sections are posted at policies.ncdhhs.gov (queue row: follow-up)",
}

# Combined manuals: a matching row must also mention the program (alias gate) unless the element is TANF-unique.
# ID (IDAPA 16.03.08 TANF+LIHEAP: LIHEAP sections carry LIHEAP in the heading and are dropped by NEG_HEADING),
# KY (KTAP + KWP volumes) and VT (Reach Up family rules) are TANF-only scopes and are NOT gated.
COMBINED = {"us-fl", "us-il", "us-in", "us-ks", "us-mi", "us-mn", "us-nv", "us-tx", "us-ut", "us-wa", "us-wv", "us-wy",
            "us-nh", "us-or", "us-la", "us-oh", "us-az", "us-ct"}
TANF_ALIASES = {
    "us-fl": r"\bTCA\b|temporary cash assistance", "us-il": r"\bTANF\b|cash assistance", "us-in": r"\bTANF\b",
    "us-ks": r"\bTANF\b|cash assistance", "us-mi": r"\bFIP\b|family independence program", "us-mn": r"\bMFIP\b",
    "us-nv": r"\bTANF\b", "us-tx": r"\bTANF\b", "us-ut": r"\bFEP\b|family employment program",
    "us-wa": r"\bTANF\b|\bWorkFirst\b|temporary assistance", "us-wv": r"WV WORKS|\bTANF\b", "us-wy": r"\bPOWER\b",
    "us-nh": r"\bFANF\b|\bNHEP\b|financial assistance to needy families", "us-or": r"\bTANF\b|\bJOBS\b",
    "us-la": r"\bFITAP\b|\bKCSP\b|\bSTEP\b|\bTANF\b", "us-oh": r"Ohio Works First|\bOWF\b|\bTANF\b",
    "us-az": r"\bCA\b|cash assistance|\bTANF\b", "us-ct": r"\bTFA\b|temporary family assistance",
}

# Default status when an element is not found for a jurisdiction (queue- or inspection-derived evidence).
TANF_DEFAULT_MISSING = {
    "us-ny": ("OUTREACH", "OTDA Temporary Assistance Source Book (TASB.pdf) blocked by an F5/TSPD JavaScript bot wall (queue row, retried 3x incl. US network); only the 2024-2026 TANF State Plan is selected; 18 NYCRR parts 350-397 were not inventoried by the queue"),
    "us-ga": ("EXTRACTABLE", "Georgia TANF Policy Manual: only sections 1525, 1605, 1615 and Appendix A are in the corpus (47 block rows); the full manual is posted at pamms.dhs.ga.gov/dfcs/tanf/ (queue 'done' by pointer to a 4-section slice)"),
    "us-ct": ("EXTRACTABLE", "CT DSS Uniform Policy Manual: 13 UPM sections plus the 2026 standards chart are in the corpus (28 rows); the full UPM (TFA chapters 1000-8000) is posted by DSS (queue 'done' by pointer to a slice)"),
    "us-az": ("EXTRACTABLE", "AZ DES FAA policy manual: 7 topic pages plus the 143-row FAA5 recovery scope are in the corpus; the manual (dbmefaapolicy.azdes.gov, FAA1-FAA6) is posted whole (queue 'done' by pointer to a slice)"),
    "us-de": ("EXTRACTABLE", "Delaware selected scope us-de/regulation/2026-07-03-de-tanf-rules holds DSSM section 4000 (Financial Responsibility, 41 rows) only; the DSSM 3000 series (TANF program rules: time limits, contract of mutual responsibility, work, sanctions, teen parents, diversion) is posted by the same publisher (regulations.delaware.gov, Title 16) and was not taken (the queue row's 'DSSM 3000 already ingested' names the wrong section)"),
}
# Per-jurisdiction rulebook notes appended to REVIEW cells (from reading the scope shapes 2026-09-12).
TANF_JUR_NOTES = {
    "us-id": "IDAPA 16.03.08 (2026 zero-based rewrite; 18 sections 100-115 TANF, 200-205 LIHEAP) is a skeleton naming eligibility, household members, cooperation, IRP, sanctions and overpayments but carrying no need/payment standards, income limits, disregards, resource limits, time limits or work-hour rules; the IDHW TAFI page links no manual (queue row); the TAFI State Plan, where Idaho reports those values, was not inventoried",
    "us-wy": "Wyoming SNAP and POWER manual scope is 3 document-level blocks (11K-84K chars) plus the POWER income-limit table; matches cite a whole block and POWER chapters are not separable; re-extract at chapter granularity",
    "us-ak": "7 AAC 45 has 127 rows (28 repealed stubs) and the 2026 ATAP standards carry the need/maximum payment tables; DPA's ATAP policy manual was not inventoried by the queue (row done by pointer to the regulation)",
    "us-al": "Alabama rule 660-2-2 (45 pages, page-level), the 2024 TANF State Plan and Payment Manual Appendix N sec. 2 are the selected documents; DHR posts no separate TANF manual (queue row)",
    "us-nj": "N.J.A.C. 10:90 is in the corpus as a 558-page page-level recovery scope; page rows carry no section headings, so heading matches are impossible and body matches cite a page",
    "us-md": "only IM 26-13 (4 rows: the 2026 TCA benefit schedule) is selected",
    "us-me": "only the Rule 125A chart (2 rows) is selected",
}

# --------------------------------------------------------------------------------------
# CCDF: state-level rule elements carried by the ACF-118 plan (section in parentheses),
# the state's own subsidy rulebook, and rate/copay schedules.
# --------------------------------------------------------------------------------------
CCDF_STATE_ELEMENTS = [
    dict(id="ccdf-s01", name="Lead Agency and policy-setting authority (statewide vs local variation)", law="42 U.S.C. 9858b (Lead Agency); 45 CFR 98.10-98.11, 98.16(a),(d)", plan=["1.1", "1.2"], pat=r"Lead Agency", families="CCDF state plan 1.1-1.2",
         facts=["Lead Agency identity", "whether eligibility, copays or rates vary by locality (1.2)"], pe="no"),
    dict(id="ccdf-s02", name="Child age limit (under 13; optional to 19 if incapable of self-care/under court supervision)", law="45 CFR 98.20(a)(1); 98.16(g)(2)", plan=["2.2"], pat=r"age of children served|through age 12|under (?:age )?13|younger than (?:age )?13|age 13", families="CCDF state plan 2.2.1; state rulebook",
         facts=["age limit for a child (13)", "extended age limit (up to 19) for children incapable of self-care or under court supervision"], pe="yes (age_limit / child_age_limit in gov/hhs/ccdf and 37 state trees)"),
    dict(id="ccdf-s03", name="Reason for care: definitions of working, job training/education, job search; minimum activity hours", law="45 CFR 98.20(a)(3), 98.16(g)(3),(4),(6); state option", plan=["2.2"], pat=r"reason for care|job search|minimum (?:number of )?hours|hours (?:per|a) week", families="CCDF state plan 2.2.2; state rulebook",
         facts=["definition of working (incl. self-employment, hours)", "definition of job training / education", "job search allowed at initial eligibility and its duration", "minimum weekly hours where set"], pe="partial (activity hours in AL, IA, KS, KY, LA, MA, MN, MT, NJ, OK, RI, SC, SD, TN, TX, UT, VA, WV)"),
    dict(id="ccdf-s04", name="Initial income eligibility limit (share of SMI or FPL by family size)", law="45 CFR 98.20(a)(2)(i), 98.21(b); 98.16(i)(5)", plan=["2.2"], pat=r"Initial eligibility: income limits|income (?:eligibility )?limits?|percent(?:age)? of (?:the )?(?:State Median Income|SMI|federal poverty|FPL)", families="CCDF state plan 2.2.3-2.2.4; state rulebook; annual income limit tables",
         facts=["initial income limit as % SMI or % FPL by family size", "SMI year / table in use", "local variation"], pe="yes (income_limit_smi / smi_rate / fpl_rate parameters)"),
    dict(id="ccdf-s05", name="Graduated phase-out / exit threshold at redetermination (second tier up to 85% SMI)", law="45 CFR 98.21(b); 98.16(h)(2)", plan=["2.5"], pat=r"graduated phase-?out|second tier|85\s?(?:%|percent)", families="CCDF state plan 2.5.5; state rulebook",
         facts=["exit / redetermination income threshold (% SMI)", "phase-out design (second tier, sliding fee steps)"], pe="yes where modeled (exit/redetermination SMI rates in CO, DC, IL, IN, MA, MD, MI, MN, MO, ND, NE, NJ, NM, OH, TN, VA, WY)"),
    dict(id="ccdf-s06", name="Family asset limit ($1,000,000 certification)", law="45 CFR 98.20(a)(2)(ii)", plan=["2.2"], pat=r"asset limit|\$1,000,000|1 million|million", families="CCDF state plan 2.2.6",
         facts=["family assets must not exceed $1,000,000 (self-certification method)"], pe="partial (gov/hhs/ccdf/asset_limit; DC, IA, IN, MA, TX)"),
    dict(id="ccdf-s07", name="Countable income definition and treatment of irregular fluctuations in earnings", law="45 CFR 98.21(c); 98.16(h)(3)", plan=["2.2"], pat=r"irregular fluctuation|countable income|define(?:s|d)? (?:family )?income|gross income|income (?:definition|calculation|is defined|includes)", families="CCDF state plan 2.2.5; state rulebook",
         facts=["countable income sources and exclusions", "income averaging / treatment of irregular earnings", "family size definition"], pe="yes (countable_income/sources lists in most state trees)"),
    dict(id="ccdf-s08", name="Additional state eligibility criteria and residency (98.20(b))", law="45 CFR 98.20(b); 98.16(i)(5)", plan=["2.2"], pat=r"Additional eligibility criteria|additional (?:eligibility )?(?:criteria|conditions|rules)|resid", families="CCDF state plan 2.2.7; state rulebook",
         facts=["residency requirement", "immigration status of the child (qualified alien test)", "other state conditions (cooperation with child support etc.)"], pe="partial (immigration status lists in DC, IL, MA, NH, NM)"),
    dict(id="ccdf-s09", name="Protective services and foster care eligibility (waiver of income/activity requirements)", law="45 CFR 98.20(a)(3)(ii); 98.16(g)(7)", plan=["2.2", "2.3"], pat=r"protective services|foster care", families="CCDF state plan 2.2 / 2.3",
         facts=["definition of protective services (sub-populations)", "income and activity waivers for those children", "respite care"], pe="no"),
    dict(id="ccdf-s10", name="Priority groups and definition of very low income; homeless enrollment grace period", law="45 CFR 98.46, 98.51; 98.16(g)(8)", plan=["2.3"], pat=r"priorit|very low income|homeless", families="CCDF state plan 2.3.1-2.3.3",
         facts=["very-low-income definition", "priority populations and how priority is given (waitlist, higher limits)", "homeless grace period for documentation (days)"], pe="no"),
    dict(id="ccdf-s11", name="Minimum 12-month eligibility period and temporary changes", law="45 CFR 98.21(a); 98.16(h)(1)", plan=["2.5"], pat=r"12[- ]month|twelve[- ]month|temporary change", families="CCDF state plan 2.5.2; state rulebook",
         facts=["12-month eligibility period", "temporary changes that do not end eligibility (list)", "longer periods where used"], pe="no"),
    dict(id="ccdf-s12", name="Job search and continued assistance after loss of activity (minimum three months)", law="45 CFR 98.21(a)(2); 98.16(h)", plan=["2.5"], pat=r"job search|three months|3 months|loss of (?:work|employment)", families="CCDF state plan 2.5.3; state rulebook",
         facts=["continued assistance period after loss of work/activity (at least 3 months)", "job search period at redetermination"], pe="no"),
    dict(id="ccdf-s13", name="Change reporting requirements during the eligibility period", law="45 CFR 98.21(h); 98.16(h)(8)", plan=["2.5"], pat=r"report(?:ing)? changes|changes? in (?:circumstances|income)", families="CCDF state plan 2.5.4; state rulebook",
         facts=["changes families must report (income over 85% SMI, loss of residency, cessation of activity beyond 3 months)", "reporting deadline"], pe="no"),
    dict(id="ccdf-s14", name="Presumptive eligibility (optional, up to three months)", law="45 CFR 98.21(e); 98.16(h)(5)", plan=["2.1", "2.5"], pat=r"presumptive", families="CCDF state plan 2.1 / 2.5",
         facts=["presumptive eligibility adopted", "period (up to 3 months) and conditions"], pe="no"),
    dict(id="ccdf-s15", name="Family co-payment cap (7% of income) and sliding fee scale by income and family size", law="45 CFR 98.45(l); 98.16(k)", plan=["3.1"], pat=r"7\s?(?:%|percent)|sliding[- ]fee scale|co-?payment", families="CCDF state plan 3.1.1-3.1.2 (fee table); state copay schedule",
         facts=["maximum copay as % of gross income (7)", "sliding fee scale table: income bands x family size -> copay", "statewide or local scales"], pe="yes (copay / sliding_fee / family_share parameters in most state trees)"),
    dict(id="ccdf-s16", name="Co-payment calculation method (per child / per family, dollar vs percent)", law="45 CFR 98.45(l)(2); 98.16(k)", plan=["3.2"], pat=r"contribution|co-?payment|fee is", families="CCDF state plan 3.2.1; state rulebook",
         facts=["copay assessed per family or per child (discount for additional children)", "flat dollar vs percent of income", "part-time adjustments"], pe="yes where modeled (copay per-child/per-family rules in DC, KY, MA, MO, NJ, TX, VA, WV)"),
    dict(id="ccdf-s17", name="Co-payment waiver criteria (income at/below 150% FPL, protective services, homelessness, disability, Head Start)", law="45 CFR 98.45(l)(4); 98.16(k)", plan=["3.3"], pat=r"waiv", families="CCDF state plan 3.3.1; state rulebook",
         facts=["income threshold below which copay is waived", "categorical waivers (protective services, homeless, disability, Head Start enrollment)"], pe="partial (copay waiver thresholds in CA, ND, NM, OH, SC, TN)"),
    dict(id="ccdf-s18", name="Provider options, parental choice, certificates vs grants/contracts, in-home care limits", law="45 CFR 98.30, 98.16(i)(2), 98.16(q); 42 U.S.C. 9858c(c)(2)(A)", plan=["4.1"], pat=r"in-home|relative|certificate|contract|grant|parent choice|parental choice", families="CCDF state plan 4.1.1",
         facts=["provider types payable (center, family, in-home, relative)", "limits on in-home care", "certificates vs contracts/grants"], pe="partial (provider-type rate categories only)"),
    dict(id="ccdf-s19", name="Market rate survey or alternative methodology and narrow cost analysis (basis for rates)", law="45 CFR 98.45(c)-(f); 98.16(r)", plan=["4.2"], pat=r"market rate survey|alternative methodology|narrow cost analysis|cost estimation", families="CCDF state plan 4.2; MRS/cost reports (state-published, not taken)",
         facts=["MRS year and percentile targeted", "alternative methodology (cost model) where used", "narrow cost analysis results"], pe="no"),
    dict(id="ccdf-s20", name="Base payment rates by provider type, age of child and region", law="45 CFR 98.45(a),(f)(2); 98.16(r)", plan=["4.3"], pat=r"base payment rates?|payment rates?", families="CCDF state plan 4.3.1-4.3.2 (rate tables as of plan date); state rate schedule",
         facts=["rate table: provider type x age group x region (x unit: hour/day/week/month)", "rate unit definitions (full-time / part-time hours)", "effective date"], pe="yes (rates / reimbursement_rates / market_rate parameters in most state trees)"),
    dict(id="ccdf-s21", name="Tiered, differential and add-on rates (quality, special needs, non-traditional hours, infants)", law="45 CFR 98.45(k); 98.16(r),(x)", plan=["4.3"], pat=r"tiered|differential|add-?ons?", families="CCDF state plan 4.3.3; state rate schedule",
         facts=["quality-tier multipliers or bonuses", "special-needs add-on", "non-traditional hours add-on", "infant/toddler differential"], pe="partial (quality/special-needs multipliers in AK, AZ, IN, ND, OH, SC, SD, TN, TX, WV)"),
    dict(id="ccdf-s22", name="Payment practices: enrollment-based payment, absence policy, timeliness, registration fees", law="45 CFR 98.45(m); 98.16(cc)", plan=["4.4"], pat=r"enrollment|absence|prospective|21 (?:calendar )?days|registration fee", families="CCDF state plan 4.4.1-4.4.3; state rulebook",
         facts=["payment on enrollment vs attendance", "paid absence days", "registration / mandatory fees paid", "payment timeliness (21 days)"], pe="no"),
    dict(id="ccdf-s23", name="Provider standards: licensing, ratios/group size, health and safety, background checks, relative exemptions", law="45 CFR 98.40-98.44; 98.16(l)-(p),(u)", plan=["5.1", "5.2", "5.3", "5.7", "5.8"], pat=r"licens|health and safety|background check|ratio", families="CCDF state plan section 5; state licensing rules (not in scope of this check)",
         facts=["licensing thresholds and exemptions", "ratios and group sizes by age", "health and safety topics and training hours", "background check components", "relative-provider exemptions"], pe="no"),
    dict(id="ccdf-s24", name="Exception to TANF work penalties for single parents of children under six (definitions of appropriate/affordable/reasonable-distance child care)", law="42 U.S.C. 607(e)(2); 45 CFR 98.16(v), 98.33(f)", plan=["2.2"], pat=r"Exception to TANF work requirements|under (?:age )?six|under (?:age )?6", families="CCDF state plan 2.2.9",
         facts=["definitions of appropriate child care, reasonable distance, unsuitability of informal care, affordable arrangements", "how the exception is communicated"], pe="no"),
    dict(id="ccdf-s25", name="Program integrity: fraud investigation, recovery of misspent funds, client and provider sanctions", law="45 CFR 98.68; 98.16(dd)", plan=["10.2"], pat=r"fraud|recover|sanction", families="CCDF state plan 10.1-10.2; state rulebook",
         facts=["overpayment recovery from families and providers", "sanctions and disqualification periods", "IPV definition"], pe="no"),
    dict(id="ccdf-s26", name="CCDF state plan FFY 2025-2027 (ACF-118) as the certified/approved document", law="42 U.S.C. 9858c; 45 CFR 98.13-98.18", plan=["root"], pat=None, families="CCDF state plan (Lead Agency publication reached via the ACF index)",
         facts=["the plan document itself (10 sections, 41 subsections), its plan status (certified/approved) and period"], pe="no", doc_element=True),
    dict(id="ccdf-s27", name="Plan Appendix 1: Lead Agency implementation plan for federal non-compliances (waived requirements)", law="45 CFR 98.18(b), 98.16 (Appendix 1 template)", plan=[], pat=None, families="ACF-hosted Appendix PDF on the FY 2025-2027 index (51 listed, 0 taken)",
         facts=["which federal requirements the state is not yet meeting and the corrective plan/dates"], pe="no", doc_element=True),
    dict(id="ccdf-s28", name="Plan amendments approved after the initial plan (consolidated amended plans)", law="45 CFR 98.18(b)", plan=[], pat=None, families="amended plans posted on Lead Agency pages (inventoried, not taken except where the only posted version)",
         facts=["amended values (income limits, copays, rates) and their approval dates"], pe="no", doc_element=True),
    dict(id="ccdf-s29", name="State CCDF subsidy rulebook (state regulation or policy manual operationalizing eligibility, copays and rates)", law="45 CFR 98.3 (state law), 98.16(i)(5); state law", plan=[], pat=None, families="state regulation/manual for the subsidy program (CCAP/CCS/ERDC/Wisconsin Shares etc.)",
         facts=["the operative eligibility, copay, authorization-hours and payment rules the plan summarizes"], pe="yes (PolicyEngine state child-care trees cite these manuals)", doc_element=True),
    dict(id="ccdf-s30", name="Current-year payment rate schedule and copay schedule updates (rate sheets, transmittals) after the plan snapshot", law="45 CFR 98.45(f)(2) (rates follow the latest MRS; re-evaluated at least every 3 years)", plan=[], pat=None, families="state rate schedules / MRS sheets / transmittals (state-published)",
         facts=["current rate table and copay table with effective dates"], pe="yes (PE parameters carry dated rate values)", doc_element=True),
]

# Explicit carriers of a state's own child-care subsidy rulebook inside selected scopes (verified by heading walk
# 2026-09-11 and re-checked 2026-09-12 with a heading scan of every selected TANF/combined scope; the other combined
# manuals carry no subsidy chapter).
CCDF_RULEBOOK_ALLOW = {
    "us-az": [("regulation", "2026-06-25-az-aac-title-6-chapter-5-article-49", r"article-49/R6-5-49"), ("manual", "2026-06-25-az-ccap", r"des/ccap/")],
    "us-ga": [("manual", "2026-06-25-ga-caps", r"caps/policy-manual|caps/appendix")],
    "us-co": [("regulation", "2026-07-13-recovery-r2026-09-11-tanf-consolidated", r"8-ccr-1403-1/")],
    "us-mi": [("manual", "2026-07-17-mi-bridges-manual", r"bridges/bem/(?:205|525|70[2-9]|71[0-9])")],
    "us-ks": [("manual", "2026-05-27-ks-keesm-r2026-07-15-self-contained", r"keesm/keesm(?:28[0-9]{2}|10[0-9]{3}|44[0-9]{2}|7[0-9]{3})")],
    "us-ut": [("manual", "2026-05-27-ut-manuals-r2026-07-15-self-contained", r"child-care|escc")],
    "us-il": [("manual", "2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained", r"csmm/1427[6-9]|csmm/143[0-9]{2}")],
    "us-nh": [("manual", "2026-09-10-tanf-state-policy-manual", r"dhhs/fam/9[0-9]{2}")],
}
CCDF_RULEBOOK_STRONG = re.compile(
    r"child care (?:assistance|subsidy|scholarship|payment assistance|certificate program)|\bCCAP\b|\bERDC\b|Wisconsin Shares|"
    r"child development and care|\bCDC\b program|child care and development fund|\bCCDF\b|\bCAPS\b|Child Care Services program|"
    r"childcare (?:assistance|subsidy)|co-?payment[^.]{0,80}child care|child care[^.]{0,80}(?:co-?payment|sliding fee|provider payment rate)",
    re.I)

# Queue-derived defaults for CCDF document elements (s27-s30) and blocked/absent plans (ccdf-agent-queue.yaml rows,
# run notes 2026-09-10-ccdf-state-plans-fy2025-2027{,-retry,-retry-2}.md).
CCDF_PLAN_BLOCKED = {
    "us-az": "HTTP 403 cloudflare from the AZ DES plan page (plain and impersonated; retried 3x incl. US network)",
    "us-ga": "connection reset by www.decal.ga.gov (retried 3x incl. US network)",
    "us-md": "HTTP 403 'Access denied' on earlychildhood.marylandpublicschools.org/2025-2027-ccdf-plan (retried 3x)",
    "us-mo": "dese.mo.gov serves a Drupal antibot/Incapsula form instead of the plan PDF (retried 3x)",
    "us-ny": "ocfs.ny.gov F5/Shape TSPD JavaScript challenge instead of the index (retried 3x)",
    "us-tx": "HTTP 403 CloudFront / HTTP 202 AWS WAF challenge from the TWC plan page (retried 3x)",
}
CCDF_PLAN_NOT_TAKEN = {
    "us-ak": ("REVIEW", "publisher posts only the 2024-05-24 draft '2025-2027 CCDF State Plan 052424.pdf' on the Online Public Notice (no approved or certified plan posted); reviewer decision whether a draft counts"),
    "us-in": ("EXTRACTABLE", "publisher posts the certified 2024-06-30 submission (399 pages, non-CARS layout with attached state rules; the CARS section pattern matched 5 labels so it was not extracted); an adapter/pattern change would take it"),
}
CCDF_AMENDMENTS = {
    "PRESENT_AS_AMENDED": {"us-ar": "Amendment 2 (approved 2026-05-13) is the taken plan", "us-ia": "Amendment 1 (approved 2026-03-26) is the taken plan", "us-mi": "Amendment 2 (approved 2026-03-12) is the taken plan", "us-mn": "Amendment 3 (approved 2026-08-11) is the taken plan", "us-la": "Amendment 1 (approved 2025-03-26) is the taken plan"},
    "EXTRACTABLE": {"us-ca": "Amendment #1 posted separately, not taken", "us-dc": "amendment 1 and 2 approval letters posted separately", "us-ma": "amendment 1 and 2 consolidated plans posted separately", "us-nc": "Amendment 2 consolidated plan posted separately", "us-nd": "Amendment 1 and 2 posted separately", "us-oh": "amendments 1 and 2 posted separately", "us-sd": "Amendments 1-3 consolidated plans posted separately", "us-wa": "Amendment 1 posted separately", "us-me": "Amendments #1-#4 posted separately (latest 2026-06-26)", "us-or": "Amendment 1 with approval letter posted separately", "us-vt": "Amendment 1 approval letter posted separately", "us-mo": "landing page lists Amendment #1 and 'Current' Amendment #2 behind the blocked media path"},
}
CCDF_APPENDIX_STATE_COPY = {"us-ky", "us-me", "us-mi", "us-ms", "us-nc", "us-nd", "us-or", "us-tn", "us-ut"}
CCDF_RATE_SHEETS = {
    "us-me": "market rate sheets 2018/2021/2024/2025 and MRS reports listed on the OCFS page, not taken",
    "us-id": "ICCP copay chart and local market rates listed on the IDHW page, not taken",
    "us-ky": "market rate surveys 2017/2020/2023 listed, not taken",
    "us-tn": "income eligibility limits and co-pay table, state rate and QRIS bonus table, market rate surveys 2022-23 to 2024-25 listed on the TDHS page, not taken",
    "us-ut": "market rate studies 2021, 2024 listed, not taken",
    "us-mn": "market rate survey reports listed, not taken",
    "us-nj": "market rate survey reports (2017-18, 2021-22) listed, not taken",
    "us-co": "2024 Market Rate Survey and Narrow Cost Analysis listed, not taken",
    "us-ct": "2024 MRS and narrow cost analysis listed, not taken",
    "us-la": "MRS reports 2017/2020/2023 listed, not taken",
    "us-or": "2024 narrow cost analysis and alternate rate-setting report listed, not taken",
    "us-sc": "Child Care Scholarship fee scales, maximum payments and income standards (about 17 documents) listed on scchildcare.org, not taken",
    "us-va": "2020 market rate survey and alternative rate methodology report listed, not taken",
    "us-ri": "child care market rate survey 2024 listed, not taken",
    "us-pa": "2025 Child Care Market Rate Survey report and summary listed, not taken",
    "us-ms": "market rate surveys 2021/2024 and Narrow Cost Analysis 2024 listed, not taken",
    "us-vt": "Child Care Market Rate Survey 2024 listed, not taken",
    "us-ga": "CAPS Appendix C reimbursement rates and Appendix D family fee chart are in the selected CAPS scope (June 2026)",
    "us-az": "CCAP income/fee schedule FFY2026 is encoded in rulespec-us (us-az/policies/des/ccap/income-fee-schedule-ffy2026), source in the selected AZ CCAP scope",
}
CCDF_RULEBOOK_LISTED = {
    "us-in": "IN FSSA CCDF Policy Manual (in.gov/fssa/carefinder/files/CCDF-Policy-Manual.pdf, HTTP 200, 4.4 MB) and Provider Manual answer but were not extracted (queue row 2026-09-10-ccdf-in-policy-manual, needs_review)",
    "us-ky": "KY Operation Manual Vol. VIII Child Care Assistance Program (CCAP) listed on the DFS volume index, not taken (TANF queue row)",
    "us-nm": "8.150 NMAC child care parts (17) listed on the HCA ISD SRCA index, not taken (TANF queue row)",
    "us-ri": "218-RICR-20-00-4 Child Care Assistance Program rules (and Part 13) listed on the RICR chapter page, not taken (TANF queue row)",
    "us-sc": "SC Voucher manual (DSS manuals page) and Child Care Scholarship policy manuals vol. 36-39 (scchildcare.org) listed, not taken",
    "us-tn": "child care policies listed on the TDHS publications page, not taken (TANF queue row)",
    "us-id": "IDAPA 16.06.12 Idaho Child Care Program rules on the OARC current-rules index (371 chapters), not taken",
    "us-ne": "Title 392 Child Care Subsidy on rules.nebraska.gov (45 DHHS titles), not taken",
    "us-oh": "OAC 5101:2-16 publicly funded child care on codes.ohio.gov, not taken (only 5101:1 and 5101:4 taken)",
    "us-ok": "OAC 340:40 child care subsidy on rules.ok.gov, not taken",
    "us-sd": "ARSD 67:47 child care assistance on sdlegislature.gov/Rules, not taken",
    "us-or": "ERDC rules moved to OAR chapter 414 (Department of Early Learning and Care) on the same OARD publisher; the selected chapter 461 scope carries no ERDC-specific rule, not taken",
    "us-wi": "Wisconsin Shares Child Care Subsidy Policy Manual is a separate DCF manual (the W-2 manual only references Wisconsin Shares participation); not inventoried by the queue",
    "us-vt": "Vermont CCFAP rules (CDD) are separate from the ESD rules taken; the DCF CDD page was inventoried for the plan only",
    "us-me": "CCAP rules (10-148 CMR ch. 6), income guidelines and memos (18 documents) listed on the OCFS page, not taken",
}

# --------------------------------------------------------------------------------------
# Federal statute elements (section-level where the numbering is certain).
# --------------------------------------------------------------------------------------
TANF_STATUTE = [
    ("42 U.S.C. 601", "Purpose of Title IV-A; no individual entitlement"),
    ("42 U.S.C. 602", "Eligible States; State plan contents (602(a)(1)-(7)), certifications, public comment, 3-year renewal"),
    ("42 U.S.C. 603", "Grants to States (family assistance grant, contingency fund, healthy marriage/fatherhood, emergency funds)"),
    ("42 U.S.C. 604", "Use of grants (purposes, carry-over, transfers to CCDF/SSBG, administrative cap, IDAs, EBT restrictions 604(h))"),
    ("42 U.S.C. 605", "Administrative provisions (quarterly payments, computable amounts)"),
    ("42 U.S.C. 606", "Federal loans for State welfare programs"),
    ("42 U.S.C. 607", "Mandatory work requirements: participation rates, hours, work activities (607(d)), penalties against individuals (607(e)), child-care exception"),
    ("42 U.S.C. 608", "Prohibitions and requirements: minor child, IV-D cooperation, 60-month limit, teen parents, fugitive felons, fraud bar, aliens (608(f)), EBT (608(a)(12))"),
    ("42 U.S.C. 609", "Penalties against States"),
    ("42 U.S.C. 610", "Appeal of adverse decision"),
    ("42 U.S.C. 611", "Data collection and reporting"),
    ("42 U.S.C. 611a", "State required to provide certain information"),
    ("42 U.S.C. 612", "Direct funding and administration by Indian tribes"),
    ("42 U.S.C. 613", "Research, evaluations, and national studies"),
    ("42 U.S.C. 614", "Study by the Census Bureau"),
    ("42 U.S.C. 615", "Waivers"),
    ("42 U.S.C. 616", "Administration (Office of Family Assistance)"),
    ("42 U.S.C. 617", "Limitation on Federal authority"),
    ("42 U.S.C. 618", "Funding for child care (CCDF mandatory and matching funds)"),
    ("42 U.S.C. 619", "Definitions (adult, minor child, fiscal year, Indian, State)"),
]
CCDF_STATUTE = [
    ("42 U.S.C. 9857-9857a", "CCDBG Act short title and goals (sec. 658A)"),
    ("42 U.S.C. 9858", "Authorization of appropriations (sec. 658B)"),
    ("42 U.S.C. 9858a", "Lead agency designation (sec. 658D)"),
    ("42 U.S.C. 9858c", "Application and plan (sec. 658E): plan contents incl. eligibility (658E(c)(2)), sliding fee scale, payment rates, health and safety, 12-month eligibility, priority, consumer education"),
    ("42 U.S.C. 9858d-9858m", "Sections 658F-658O: limitations on State allotments, activities to improve quality (658G), background checks (658H), administration and enforcement (658I), payments, annual report and audits, Secretary's report, hotline, allotments (658O)"),
    ("42 U.S.C. 9858n", "Definitions (sec. 658P): child care certificate, eligible child, family child care provider, State median income, etc."),
    ("42 U.S.C. 9858o-9858r", "Sections 658Q-658T: severability, parental rights and responsibilities, miscellaneous, limitation"),
]

CFR_STATE_OPTION = {  # CFR sections that set or bound state-level elements (schema cross-reference)
    "260.30": ["tanf-s01", "tanf-s02"], "260.31": ["tanf-s21", "tanf-s30"], "260.50": ["tanf-s24"], "260.51": ["tanf-s24"], "260.52": ["tanf-s24"],
    "260.54": ["tanf-s24"], "260.55": ["tanf-s24"], "261.10": ["tanf-s15"], "261.11": ["tanf-s19"], "261.12": ["tanf-s19"], "261.13": ["tanf-s19"],
    "261.14": ["tanf-s17"], "261.15": ["tanf-s18"], "261.16": ["tanf-s17"], "261.30": ["tanf-s16"], "261.31": ["tanf-s15"], "261.32": ["tanf-s15"],
    "261.33": ["tanf-s16"], "261.34": ["tanf-s16"], "261.35": ["tanf-s15"], "261.56": ["tanf-s18"], "261.57": ["tanf-s18"], "263.20": ["tanf-s11"],
    "263.21": ["tanf-s11"], "263.22": ["tanf-s11"], "263.23": ["tanf-s11"], "264.1": ["tanf-s14"], "264.2": ["tanf-s14"], "264.3": ["tanf-s14"],
    "264.10": ["tanf-s25"], "264.30": ["tanf-s09"], "264.31": ["tanf-s09"], "264.60": ["tanf-s29"], "264.61": ["tanf-s29"],
    "98.2": ["ccdf-s02", "ccdf-s07"], "98.3": ["ccdf-s29"], "98.16": ["ccdf-s26"], "98.18": ["ccdf-s28"], "98.20": ["ccdf-s02", "ccdf-s03", "ccdf-s04", "ccdf-s06", "ccdf-s08", "ccdf-s09"],
    "98.21": ["ccdf-s05", "ccdf-s07", "ccdf-s11", "ccdf-s12", "ccdf-s13", "ccdf-s14"], "98.30": ["ccdf-s18"], "98.33": ["ccdf-s24"], "98.40": ["ccdf-s23"],
    "98.41": ["ccdf-s23"], "98.42": ["ccdf-s23"], "98.43": ["ccdf-s23"], "98.45": ["ccdf-s15", "ccdf-s16", "ccdf-s17", "ccdf-s19", "ccdf-s20", "ccdf-s21", "ccdf-s22", "ccdf-s30"],
    "98.46": ["ccdf-s10"], "98.51": ["ccdf-s10"], "98.68": ["ccdf-s25"],
}


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------
_ROWS_CACHE: dict[tuple, list | None] = {}


def load_rows(base: Path, jur: str, dc: str, ver: str):
    key = (jur, dc, ver)
    if key not in _ROWS_CACHE:
        p = base / "provisions" / jur / dc / f"{ver}.jsonl"
        _ROWS_CACHE[key] = [json.loads(line) for line in p.open()] if p.exists() else None
    return _ROWS_CACHE[key]


def snippet(text: str, m: re.Match, width: int = 70) -> str:
    s = max(0, m.start() - width)
    e = min(len(text), m.end() + width)
    return re.sub(r"\s+", " ", text[s:e]).strip()


def cfr_sections(structure_path: Path, parts: set[str]):
    s = json.load(structure_path.open())
    out = []

    def walk(n):
        if n.get("type") == "part" and n.get("identifier") in parts:
            def w2(m):
                if m.get("type") == "section" and not m.get("reserved"):
                    out.append((n["identifier"], m["identifier"], m.get("label_description", "")))
                for c in m.get("children", []):
                    w2(c)
            for c in n.get("children", []):
                w2(c)
            return
        for c in n.get("children", []):
            walk(c)
    walk(s)
    return out


NEG_HEADING = re.compile(r"\b(SNAP|Food Stamps?|FoodShare|Basic Food|3SquaresVT|Food Assistance|Medicaid|MAGI|CHIP|LIHEAP|ABAWD|General Assistance|Refugee|AABD|SSI|Medical|BFET|E&T|Summer EBT|SEBT)\b", re.I)
TANF_WORDS = re.compile(r"\bTANF\b|temporary assistance|cash assistance", re.I)


def search_scopes(base, jur, scopes, element, alias_re):
    """Best match for an element: (score, strong, row, scope_version, evidence, hits, heading_matched).

    strong is True when the heading matched or the body matched at least twice.
    """
    strong = re.compile(element["strong"], re.I | re.M)
    weak = re.compile(element["weak"], re.I) if element.get("weak") else None
    best = None
    for dc, ver in scopes:
        rows = load_rows(base, jur, dc, ver)
        if rows is None:
            continue
        for r in rows:
            heading = r.get("heading") or ""
            body = r.get("body") or ""
            if not body:
                continue
            text = heading + "\n" + body
            m_head = strong.search(heading)
            m_body = strong.search(body)
            if not (m_head or m_body):
                continue
            if NEG_HEADING.search(heading) and not (alias_re and alias_re.search(heading)) and not TANF_WORDS.search(heading):
                continue
            if alias_re and not (alias_re.search(text) or TANF_WORDS.search(text)):
                continue
            hits = len(strong.findall(body))
            is_strong = bool(m_head) or hits >= 2
            score = (2 if m_head else 0) + min(hits, 20) / 20 + (0.5 if weak and weak.search(body) else 0) + (1 if is_strong else 0)
            if best is None or score > best[0]:
                m = m_head or m_body
                best = (score, is_strong, r, f"{jur}/{dc}/{ver}", snippet(heading if m_head else body, m), hits, bool(m_head))
    return best


def state_plan_scan(base: Path, jur: str, selected: set):
    """Find a TANF state plan document anywhere on disk for the jurisdiction; returns (selected?, scope, row)."""
    found = []
    for p in glob.glob(str(base / "provisions" / jur / "*" / "*.jsonl")):
        dc = Path(p).parent.name
        ver = Path(p).stem
        for r in load_rows(base, jur, dc, ver) or []:
            cp = r["citation_path"]
            if "state-plan" not in cp:
                continue
            head = r.get("heading") or ""
            if re.search(r"tanf", cp, re.I) or re.search(r"\bTANF\b|Temporary Assistance", head):
                if not (r.get("body") or ""):  # document root row
                    found.append(((jur, dc, ver) in selected, f"{jur}/{dc}/{ver}", r))
                    break
    found.sort(key=lambda t: not t[0])
    return found[0] if found else None


# --------------------------------------------------------------------------------------
def build_tanf(base: Path, selector_scopes, out: Path, structure: Path):
    t0 = time.time()
    cfr = cfr_sections(structure, {"260", "261", "262", "263", "264", "265"})
    schema = {
        "program": "tanf",
        "title": "TANF (Temporary Assistance for Needy Families) needs schema, law-derived",
        "date": "2026-09-11",
        "method": (
            "Elements are enumerated from the program's own legal structure: (1) 42 U.S.C. 601-619 section by section; "
            "(2) every live section of 45 CFR 260-265 (from the eCFR title-45 structure snapshot of 2026-09-09 retained with the "
            f"part 98 scope; {len(cfr)} sections); (3) the state rulebook structure observed in the selected state scopes "
            "(chapter tables of contents of MT, ND, VA, TN, PA, WI, MS, CA, CO, DE, IA, NE, NM, OK, SD, VT, ID and the combined "
            "manuals) plus the state plan requirements of 42 U.S.C. 602(a). State-level elements are the rule elements a "
            "state must set (state option or state-set value); each carries a 'facts' list naming what an encoder reads. "
            "PolicyEngine's gov/hhs/tanf and gov/states/*/…/tanf trees and the rulespec-us programs/us-*/tanf wrappers "
            "are a cross-check only (pe_modeled field)."
        ),
        "levels": {"federal": "set by statute/regulation, inherited by every state; checked once at jurisdiction us",
                   "federal_with_state_option": "federal rule that a state elects or parameterizes; checked per state",
                   "state": "set entirely by the state; checked per state"},
        "federal_statute_elements": [
            {"id": f"tanf-f-usc-{c.split()[-1]}", "citation": c, "name": n, "level": "federal" + (" (state option)" if c.split()[-1] in ("602", "607", "608") else ""),
             "family": "federal statute (uscode.house.gov, title 42 chapter 7 subchapter IV part A)",
             "corpus_family_status": "absent from every us/statute scope (citation_path scan of data/corpus/provisions/us/statute for us/statute/42/601-619, 2026-09-12: 0 rows)",
             "pe_modeled": "partial (PE cites 607/608 for work requirement and immigrant variables)" if c.split()[-1] in ("607", "608") else "no"}
            for c, n in TANF_STATUTE
        ],
        "federal_regulation_elements": [
            {"id": f"tanf-f-cfr-{sec}", "citation": f"45 CFR {sec}", "part": part, "name": desc,
             "level": "federal (state option)" if sec in CFR_STATE_OPTION else "federal",
             "sets_state_elements": CFR_STATE_OPTION.get(sec, []),
             "family": "federal regulation (eCFR Versioner API; extract-ecfr --only-title 45 --only-part 260..265)",
             "corpus_family_status": "not in the corpus (queue federal row 2026-09-10; data/corpus/provisions/us/regulation has title-45 parts 98 and 1302 only)",
             "pe_modeled": "no"}
            for part, sec, desc in cfr
        ],
        "federal_guidance_elements": [
            {"id": "tanf-f-acf-guidance", "citation": "ACF OFA TANF Program Instructions and Policy Announcements (TANF-ACF-PI/PA series)", "name": "ACF program guidance (e.g. work verification plan instructions, FVO, data reporting)",
             "level": "federal", "family": "ACF guidance (acf.gov/ofa resource library)", "corpus_family_status": "not in the corpus; the acf.gov resource library answered a non-browser client with an HTTP 202 challenge on 2026-09-10 (queue federal row)", "pe_modeled": "no"},
        ],
        "state_elements": [
            {"id": e["id"], "name": e["name"], "level": "state" if "608" not in e["law"] and "607" not in e["law"] and "45 CFR" not in e["law"] else "federal_with_state_option",
             "law_basis": e["law"], "carrying_families": e["families"], "facts": e["facts"], "evidence_patterns": {"strong": e["strong"], "weak": e.get("weak")},
             "pe_modeled": e["pe"], "document_element": bool(e.get("doc_element"))}
            for e in TANF_STATE_ELEMENTS
        ],
        "policyengine_cross_check": {
            "source": "policyengine-us parameters gov/hhs/tanf (20 files: age_limit student/non_student, income sources, non_cash gross/net income limits and asset limit, five_year_bar_years, bar_exempt_immigration_statuses) and gov/states/<st>/<agency>/<program> for 46 state TANF trees (walked 2026-09-12)",
            "elements_the_law_has_that_pe_lacks": [e["id"] for e in TANF_STATE_ELEMENTS if e["pe"].startswith("no")],
            "elements_pe_models_partially": [e["id"] for e in TANF_STATE_ELEMENTS if e["pe"].startswith("partial")],
            "rulespec_us_note": "programs/us-*/tanf/fy-2026.yaml wrappers (15 states: AK, AL, AR, AZ, CA, CO, CT, DE, GA, IN, KS, ME, NY, TX, UT) all carry acknowledged_incomplete for the eligibility/benefit judgments; the encoded slices are payment/need standards, disregards, income tests and resource limits (tanf-s05..s08, s11, s13), i.e. the same subset PolicyEngine models.",
        },
        "schema_uncertainties": [
            "Section-level elements for 42 U.S.C. 601-619 are enumerated from the compiler's knowledge of the title (the text is not in the corpus); headings should be re-checked against the ingested text once extracted.",
            "State-level elements are a normalized cross-state list; individual states split or merge them (e.g. WI W-2 placements replace need/payment standards; MN MFIP has a food portion). One state element can map to several rulebook chapters, and the 'facts' lists are indicative, not exhaustive.",
            "Procedural elements (tanf-s25, s26, s27) are broad; a PRESENT there says the rulebook has the chapter, not that every fact is carried.",
            "The evidence search is pattern-based on provision bodies; PRESENT means a heading match or at least two body matches were found and cited, not that a human read every state's chapter. A random sample of PRESENT cells was read by hand (see tanf.md).",
            "Whether a state 'sets' an optional element (diversion, drug-felony modification, EBT penalties) cannot be told from absence; REVIEW is used, not ABSENT, unless the queue records the publisher posts nothing.",
        ],
    }
    (out / "tanf-schema.yaml").write_text(yaml.safe_dump(schema, sort_keys=False, allow_unicode=True, width=140))

    rows = []
    # federal cells (one row each; inherited by the 51 jurisdictions)
    for c, n in TANF_STATUTE:
        rows.append(["us", f"tanf-f-usc-{c.split()[-1]}", "federal", "federal statute", "EXTRACTABLE", "", "", "no" if c.split()[-1] not in ("607", "608") else "partial",
                     f"{c} {n}: not in any us/statute scope; uscode.house.gov publishes title 42 (the corpus already takes USC titles from it); inherited by all 51 jurisdictions"])
    for part, sec, desc in cfr:
        rows.append(["us", f"tanf-f-cfr-{sec}", "federal" + (" (state option)" if sec in CFR_STATE_OPTION else ""), "federal regulation", "EXTRACTABLE", "", "", "no",
                     f"45 CFR {sec} ({desc}): parts 260-265 not in the corpus; eCFR Versioner API serves title 45 (extract-ecfr, adapter fixed 2026-09-11 for gzip); inherited by all 51 jurisdictions"])
    rows.append(["us", "tanf-f-acf-guidance", "federal", "ACF guidance", "REVIEW", "", "", "no",
                 "no ACF OFA guidance scope in the corpus; acf.gov resource library answered HTTP 202 challenge to a non-browser client (queue federal row); a browser UA fetched the OCC plan index, so a retry with a browser UA is the next step"])

    level_of = {e["id"]: s["level"] for e, s in zip(TANF_STATE_ELEMENTS, schema["state_elements"])}
    per_jur = defaultdict(Counter)
    qa_pool = []
    for jur in JURS[1:]:
        alias_re = re.compile(TANF_ALIASES[jur], re.I) if jur in COMBINED else None
        scopes = TANF_SCOPES.get(jur, [])
        jnote = TANF_JUR_NOTES.get(jur)
        for e in TANF_STATE_ELEMENTS:
            pe = e["pe"].split(" ")[0]
            fam = e["families"].split(";")[0]
            lvl = level_of[e["id"]]

            def emit(status, sv="", cp="", note=""):
                rows.append([jur, e["id"], lvl, fam, status, sv, cp, pe, note])
                per_jur[jur][status] += 1

            if e.get("doc_element"):  # tanf-s32 state plan
                hit = state_plan_scan(base, jur, selector_scopes)
                if hit and hit[0]:
                    emit("PRESENT", hit[1], hit[2]["citation_path"], f"heading='{(hit[2].get('heading') or '')[:80]}' (state-plan document root in a selected scope)")
                elif hit:
                    emit("EXTRACTABLE", "", "", f"state plan document exists on disk in unselected scope {hit[1]} ({hit[2]['citation_path']}); re-select")
                elif jur == "us-mt":
                    emit("EXTRACTABLE", "", "", "MT DPHHS TANF manual page lists the TANF State Plan 1/2024-12/2026 PDF (state-plan family, not taken; batch-1 run note)")
                else:
                    emit("REVIEW", "", "", "state-published TANF plan not in the corpus and not inventoried: the TANF queue's document family is tanf_policy_sources (manuals and adopted rules), and ACF OFA posts no consolidated plan index (acf.gov/ofa/programs/tanf/state-plans is 404, queue federal row); each state's posting must be checked")
                continue

            best = search_scopes(base, jur, scopes, e, alias_re)
            if best and best[1]:
                _, _, r, sv, ev, hits, m_head = best
                emit("PRESENT", sv, r["citation_path"], f"heading='{(r.get('heading') or '')[:80]}' | {'heading match' if m_head else f'{hits} body matches'} | {ev[:200]}")
                qa_pool.append((jur, e["id"], sv, r["citation_path"], (r.get("heading") or "")[:80], ev[:200]))
                continue
            weak_note = ""
            if best:
                _, _, r, sv, ev, hits, _ = best
                weak_note = f"single body mention only at {sv} {r['citation_path']} ('{ev[:120]}'), not enough for PRESENT; "
            # fallback: unselected on-disk scope
            fb = search_scopes(base, jur, TANF_UNSELECTED.get(jur, []), e, None)
            if fb and fb[1]:
                _, _, r, sv, ev, hits, _ = fb
                emit("EXTRACTABLE", "", "", f"found in unselected on-disk scope {sv} at {r['citation_path']} ('{ev[:120]}'); {TANF_UNSELECTED_NOTE[jur]}")
                continue
            if jur in TANF_UNSELECTED:
                emit("REVIEW", "", "", weak_note + f"not located by pattern in the selected scope(s) nor in the unselected on-disk scope; {TANF_UNSELECTED_NOTE[jur]}")
                continue
            if jur in TANF_DEFAULT_MISSING:
                st, note = TANF_DEFAULT_MISSING[jur]
                emit(st, "", "", weak_note + note)
            else:
                scope_desc = ", ".join(f"{dc}/{v}" for dc, v in scopes)
                emit("REVIEW", "", "", weak_note + f"no body in the selected scope(s) [{scope_desc}] matched the evidence patterns with a heading match or 2+ body matches; the scope is the publisher's whole rulebook per the queue row, so either the element lives under other vocabulary or the state does not set it" + (f"; {jnote}" if jnote else ""))

    with (out / "tanf-matrix.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        w.writerows(rows)
    return rows, per_jur, time.time() - t0, len(cfr), qa_pool


def build_ccdf(base: Path, selector_scopes, out: Path, structure: Path):
    t0 = time.time()
    cfr = cfr_sections(structure, {"98"})
    p98 = load_rows(base, *PART98)
    p98_by_sec = {r["citation_path"].split("/")[-1]: r for r in p98 if re.match(r"^\d", r["citation_path"].split("/")[-1])}
    schema = {
        "program": "ccdf",
        "title": "CCDF (Child Care and Development Fund) needs schema, law-derived",
        "date": "2026-09-11",
        "method": (
            "Elements are enumerated from (1) the CCDBG Act, 42 U.S.C. 9857-9858r (section groups; text not in the corpus); "
            f"(2) every live section of 45 CFR 98 ({len(cfr)} sections, eCFR structure 2026-09-09, scope us/regulation/2026-09-11-title-45-part-98); "
            "(3) the ACF-118 FFY 2025-2027 plan preprint structure (10 sections, 41 subsections, numbered questions such as 2.2.1-2.2.9, "
            "3.1.1-3.3.1, 4.3.1-4.4.3, read from the Oklahoma plan bodies) and the state rulebooks and rate/copay schedules the run notes inventoried. "
            "State-level elements are the values and options 45 CFR 98.16 requires a Lead Agency to set in its plan; each carries a 'facts' list. "
            "PolicyEngine's gov/hhs/ccdf and 37 state child-care trees are a cross-check only (pe_modeled)."
        ),
        "levels": {"federal": "set by statute/regulation, inherited by every state; checked once at jurisdiction us",
                   "federal_with_state_option": "federal rule the Lead Agency elects or parameterizes in its plan; checked per state",
                   "state": "set entirely by the state; checked per state"},
        "federal_statute_elements": [
            {"id": f"ccdf-f-usc-{i+1}", "citation": c, "name": n, "level": "federal (state option)" if "9858c" in c else "federal",
             "family": "federal statute (uscode.house.gov, title 42 chapter 105 subchapter II-B)",
             "corpus_family_status": "absent: no us/statute scope carries us/statute/42/9857-9858r (queue federal row; citation_path scan 2026-09-12: 0 rows)", "pe_modeled": "no"}
            for i, (c, n) in enumerate(CCDF_STATUTE)
        ],
        "federal_regulation_elements": [
            {"id": f"ccdf-f-cfr-{sec}", "citation": f"45 CFR {sec}", "name": desc,
             "level": "federal (state option)" if sec in CFR_STATE_OPTION else "federal",
             "sets_state_elements": CFR_STATE_OPTION.get(sec, []),
             "family": "federal regulation (eCFR)", "corpus_family_status": "present: us/regulation/2026-09-11-title-45-part-98 (taken 2026-09-11, 73 rows, complete coverage)", "pe_modeled": "no"}
            for _, sec, desc in cfr
        ],
        "federal_guidance_elements": [
            {"id": "ccdf-f-acf-guidance", "citation": "ACF OCC Program Instructions / Information Memoranda (CCDF-ACF-PI/IM series), FFY 2025-2027 Plan preprint and instructions", "name": "ACF OCC guidance incl. the ACF-118 preprint and instructions", "level": "federal", "family": "ACF guidance (acf.gov/occ)", "corpus_family_status": "not in the corpus (the FY 2025-2027 index page lists no preprint/instructions; queue federal row)", "pe_modeled": "no"},
        ],
        "state_elements": [
            {"id": e["id"], "name": e["name"], "level": "federal_with_state_option" if "45 CFR" in e["law"] else "state", "law_basis": e["law"],
             "carrying_families": e["families"], "plan_sections": e["plan"], "facts": e["facts"], "evidence_pattern": e["pat"], "pe_modeled": e["pe"], "document_element": bool(e.get("doc_element"))}
            for e in CCDF_STATE_ELEMENTS
        ],
        "policyengine_cross_check": {
            "source": "policyengine-us gov/hhs/ccdf (age_limit, amount, asset_limit, copay_percent, county_cluster, income_limit_smi) and 37 state child-care trees (ak al az ca co dc hi il in ks ky la ma md me mi mn mo mt nd ne nh nj nm oh ok or ri sc tn tx ut va wi wv wy; walked 2026-09-12)",
            "elements_the_law_has_that_pe_lacks": [e["id"] for e in CCDF_STATE_ELEMENTS if e["pe"].startswith("no")],
            "elements_pe_models_partially": [e["id"] for e in CCDF_STATE_ELEMENTS if e["pe"].startswith("partial")],
            "rulespec_us_note": "rulespec-us has no CCDF program wrappers; the only CCDF policies are us-az/policies/des/ccap/income-fee-schedule-ffy2026 and us-az/regulations/aac/title-6/chapter-5/article-49/R6-5-4912, R6-5-4915 (grep 2026-09-12).",
        },
        "schema_uncertainties": [
            "Exact section letters of 42 U.S.C. 9858d-9858m and 9858o-9858r are grouped, not enumerated one by one, because the statute text is not in the corpus; take the title before treating the statute rows as section-complete.",
            "Plan-carried elements are PRESENT when the plan subsection body carries the element's vocabulary; the plan reports values as of 2024-10-01 (or the taken amendment), so current-year copay and rate schedules are a separate element (ccdf-s30).",
            "Provider standards (ccdf-s23) are summarized by the plan; the state licensing code itself is out of scope of this check.",
            "The plan is a certified description of policy; whether an encoder may cite it in place of the state rule is a rules-repo decision, so ccdf-s29 (the state rulebook) is tracked separately.",
        ],
    }
    (out / "ccdf-schema.yaml").write_text(yaml.safe_dump(schema, sort_keys=False, allow_unicode=True, width=140))

    rows = []
    for i, (c, n) in enumerate(CCDF_STATUTE):
        rows.append(["us", f"ccdf-f-usc-{i+1}", "federal", "federal statute", "EXTRACTABLE", "", "", "no", f"{c} {n}: not in any us/statute scope; uscode.house.gov publishes title 42; inherited by all 51 jurisdictions"])
    for _, sec, desc in cfr:
        r = p98_by_sec.get(sec.split(".")[-1])  # structure identifier 98.20 -> path segment 20
        if r and (r.get("body") or "").strip():
            rows.append(["us", f"ccdf-f-cfr-{sec}", "federal" + (" (state option)" if sec in CFR_STATE_OPTION else ""), "federal regulation", "PRESENT", "us/regulation/2026-09-11-title-45-part-98", r["citation_path"], "no", f"body {len(r['body'])} chars: '{re.sub(chr(10), ' ', r['body'][:90])}'; inherited by all 51 jurisdictions"])
        else:
            rows.append(["us", f"ccdf-f-cfr-{sec}", "federal", "federal regulation", "REVIEW", "", "", "no", "section listed in the eCFR structure but no non-empty body found in the part 98 scope"])
    rows.append(["us", "ccdf-f-acf-guidance", "federal", "ACF guidance", "REVIEW", "", "", "no", "no ACF OCC guidance or preprint scope in the corpus; the FY 2025-2027 index lists no preprint; the OCC CCDF-ACF-PI series has not been inventoried"])

    level_of = {e["id"]: s["level"] for e, s in zip(CCDF_STATE_ELEMENTS, schema["state_elements"])}
    per_jur = defaultdict(Counter)
    plan_ver = "2026-09-10-ccdf-plan-fy2025-2027"
    for jur in JURS[1:]:
        plan = load_rows(base, jur, "policy", plan_ver) if (jur, "policy", plan_ver) in selector_scopes else None
        by_sec = {r["citation_path"].split("/")[-1]: r for r in plan} if plan else {}
        for e in CCDF_STATE_ELEMENTS:
            pe = e["pe"].split(" ")[0]
            fam = e["families"].split(";")[0]
            lvl = level_of[e["id"]]
            status = note = sv = cp = ""
            if e["id"] == "ccdf-s26" and jur == "us-ga":
                status, sv, cp = "PRESENT", "us-ga/manual/2026-06-25-ga-caps", "us-ga/manual/decal/caps/ccdf-state-plan-2025-2027"
                note = "Georgia CCDF State Plan FFY 2025-2027, 389 page-level rows inside the CAPS manual scope (June 2026 ingest); the 2026-09-10 run's decal.ga.gov block is therefore not a coverage gap for the plan document"
            elif e["id"] == "ccdf-s26":
                if plan:
                    root = plan[0]
                    status, sv, cp = "PRESENT", f"{jur}/policy/{plan_ver}", root["citation_path"]
                    note = f"plan root + 41 subsections; plan status: {root.get('metadata', {}).get('plan_status', 'see queue row')}"
                elif jur in CCDF_PLAN_BLOCKED:
                    status, note = "OUTREACH", CCDF_PLAN_BLOCKED[jur]
                elif jur in CCDF_PLAN_NOT_TAKEN:
                    status, note = CCDF_PLAN_NOT_TAKEN[jur]
                else:
                    status, note = "REVIEW", "no plan scope selected and no queue evidence"
            elif e["id"] == "ccdf-s27":
                status, note = "EXTRACTABLE", "ACF-hosted Appendix 1 PDF listed on acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027 for all 50 states + DC (51 listed, 0 taken; run note 'Appendix family not taken')" + ("; state also posts its own copy" if jur in CCDF_APPENDIX_STATE_COPY else "")
            elif e["id"] == "ccdf-s28":
                if jur in CCDF_AMENDMENTS["PRESENT_AS_AMENDED"] and plan:
                    status, sv, cp, note = "PRESENT", f"{jur}/policy/{plan_ver}", plan[0]["citation_path"], CCDF_AMENDMENTS["PRESENT_AS_AMENDED"][jur]
                elif jur in CCDF_AMENDMENTS["EXTRACTABLE"] and jur not in CCDF_PLAN_BLOCKED:
                    status, note = "EXTRACTABLE", CCDF_AMENDMENTS["EXTRACTABLE"][jur] + " (Lead Agency page, queue row)"
                elif jur in CCDF_PLAN_BLOCKED:
                    status, note = "OUTREACH", "Lead Agency site blocked (" + CCDF_PLAN_BLOCKED[jur].split(" (")[0] + ")" + ("; " + CCDF_AMENDMENTS["EXTRACTABLE"][jur] if jur in CCDF_AMENDMENTS["EXTRACTABLE"] else "")
                else:
                    status, note = "REVIEW", "queue row records no amendment on the Lead Agency page; whether an amendment has since been approved is unverified"
            elif e["id"] == "ccdf-s29":
                best = None
                for dc, ver, prefix in CCDF_RULEBOOK_ALLOW.get(jur, []):
                    for r in (load_rows(base, jur, dc, ver) or []):
                        body = r.get("body") or ""
                        if not body or not re.search(prefix, r["citation_path"]):
                            continue
                        hits = len(CCDF_RULEBOOK_STRONG.findall(body))
                        if hits and (best is None or hits > best[0]):
                            best = (hits, r, f"{jur}/{dc}/{ver}", snippet(body, CCDF_RULEBOOK_STRONG.search(body)))
                if best:
                    _, r, sv, ev = best
                    status, cp, note = "PRESENT", r["citation_path"], f"heading='{(r.get('heading') or '')[:80]}' | {best[0]} body matches | {ev[:200]}"
                elif jur in CCDF_RULEBOOK_LISTED:
                    status, note = "EXTRACTABLE", CCDF_RULEBOOK_LISTED[jur]
                elif jur in CCDF_PLAN_BLOCKED and jur not in ("us-ga", "us-az"):
                    status, note = "OUTREACH", "Lead Agency site blocked (" + CCDF_PLAN_BLOCKED[jur].split(" (")[0] + "); the state subsidy rulebook was not inventoried"
                else:
                    status, note = "REVIEW", "no selected scope carries the state's child-care subsidy rulebook (heading scan of the selected TANF/combined scope 2026-09-12 found no subsidy chapter) and no queue row inventoried it"
            elif e["id"] == "ccdf-s30":
                if jur in CCDF_RATE_SHEETS and jur in ("us-ga", "us-az"):
                    status, note = "REVIEW", CCDF_RATE_SHEETS[jur] + "; whether it is the current-year schedule is unverified"
                elif jur in CCDF_RATE_SHEETS:
                    status, note = "EXTRACTABLE", CCDF_RATE_SHEETS[jur] + " (run-note inventory)"
                elif jur in CCDF_PLAN_BLOCKED:
                    status, note = "OUTREACH", "Lead Agency site blocked (" + CCDF_PLAN_BLOCKED[jur].split(" (")[0] + ")"
                else:
                    status, note = "REVIEW", "current rate/copay schedule family not inventoried for this state; the plan carries the values as of its submission only"
            else:
                if jur == "us-ga" and not plan:
                    ga = [r for r in (load_rows(base, "us-ga", "manual", "2026-06-25-ga-caps") or []) if "ccdf-state-plan-2025-2027" in r["citation_path"] and r.get("body")]
                    labels = [re.escape(sec) for sec in e["plan"] if sec != "root"]
                    found = None
                    for r in ga:
                        if labels and not re.search(r"(?m)^\s*(?:" + "|".join(labels) + r")(?:\.\d+)?\s", r["body"]):
                            continue
                        m = re.search(e["pat"], r["body"], re.I) if e["pat"] else None
                        if m:
                            found = (r, m)
                            break
                    if found:
                        r, m = found
                        status, sv, cp = "PRESENT", "us-ga/manual/2026-06-25-ga-caps", r["citation_path"]
                        note = f"GA plan is page-level inside the CAPS scope; page carries the section label and pattern | {snippet(r['body'], m)[:160]}"
                    else:
                        status, note = "REVIEW", "GA plan pages (CAPS scope) did not match the section label + pattern; read the pages"
                elif plan:
                    found = None
                    for s in e["plan"]:
                        r = by_sec.get(s)
                        if not r:
                            continue
                        m = re.search(e["pat"], r.get("body") or "", re.I)
                        if m:
                            found = (r, m)
                            break
                    if found:
                        r, m = found
                        status, sv, cp = "PRESENT", f"{jur}/policy/{plan_ver}", r["citation_path"]
                        note = f"plan section '{r.get('heading','')[:60]}' | {snippet(r['body'], m)[:200]}"
                    else:
                        status, note = "REVIEW", f"plan sections {e['plan']} present but the evidence pattern did not match; read the section"
                elif jur in CCDF_PLAN_BLOCKED:
                    status, note = "OUTREACH", CCDF_PLAN_BLOCKED[jur]
                elif jur in CCDF_PLAN_NOT_TAKEN:
                    status, note = CCDF_PLAN_NOT_TAKEN[jur]
                    if status == "EXTRACTABLE":
                        note = "carried by the certified plan the publisher posts; " + note
                else:
                    status, note = "REVIEW", "no plan scope"
            rows.append([jur, e["id"], lvl, fam, status, sv, cp, pe, note])
            per_jur[jur][status] += 1

    with (out / "ccdf-matrix.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        w.writerows(rows)
    return rows, per_jur, time.time() - t0, len(cfr), []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    base = Path(a.base)
    repo = Path(a.repo)
    out = Path(a.out)
    sel = json.load((repo / SELECTOR).open())["scopes"]
    selector_scopes = {(s["jurisdiction"], s["document_class"], s["version"]) for s in sel} | {PART98}
    structure = base / "sources/us/regulation/2026-09-11-title-45-part-98/ecfr/title-45.structure.json"
    summary = {}
    for name, fn, elements in (("tanf", build_tanf, TANF_STATE_ELEMENTS), ("ccdf", build_ccdf, CCDF_STATE_ELEMENTS)):
        rows, per_jur, secs, ncfr, qa_pool = fn(base, selector_scopes, out, structure)
        c = Counter(r[4] for r in rows)
        fam_of = {e["id"]: e["families"].split(";")[0] for e in elements}
        gaps = defaultdict(Counter)
        fam_gaps = defaultdict(Counter)
        elem_present = Counter()
        for r in rows:
            if r[0] == "us":
                continue
            if r[4] == "PRESENT":
                elem_present[r[1]] += 1
            else:
                gaps[r[1]][r[4]] += 1
                fam_gaps[fam_of[r[1]]][r[4]] += 1
        summary[name] = {
            "rows": len(rows), "elements": len({r[1] for r in rows}), "state_elements": len(elements),
            "federal_elements": len({r[1] for r in rows if r[0] == "us"}),
            "status_counts": dict(c), "cfr_sections": ncfr, "seconds": round(secs, 1),
            "per_jurisdiction": {j: dict(v) for j, v in per_jur.items()},
            "element_present": dict(elem_present),
            "element_gaps": {k: dict(v) for k, v in sorted(gaps.items(), key=lambda kv: -sum(kv[1].values()))},
            "family_gaps": {k: dict(v) for k, v in sorted(fam_gaps.items(), key=lambda kv: -sum(kv[1].values()))},
            "qa_pool_size": len(qa_pool),
        }
        if qa_pool:
            (out / f"{name}-present-cells.tsv").write_text("\n".join("\t".join(x) for x in qa_pool) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("per_jurisdiction", "element_gaps", "family_gaps", "element_present")} for k, v in summary.items()}, indent=1))


if __name__ == "__main__":
    main()
