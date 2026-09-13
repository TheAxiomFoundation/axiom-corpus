#!/usr/bin/env python3
"""Needs-driven closure check for individual income tax (federal + 50 states + DC).

Reads provision bodies of the scopes named in the 2026-09-11 union selector and
emits tax-schema.yaml, tax-matrix.csv and tax-stats.json next to this file.
Read-only with respect to data/corpus.

    python3 docs/coverage/needs-closure-2026-09-11/tax-check.py \
        --corpus /Users/pavelmakarchuk/axiom-corpus/data/corpus \
        --selector docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json \
        --queue manifests/tax-agent-queue.yaml \
        --pe /Users/pavelmakarchuk/policyengine-us/policyengine_us/parameters/gov \
        --rulespec /Users/pavelmakarchuk/rulespec-us

Schema: the law's own structure. Federal elements are facts read section by
section from 26 U.S.C. subtitle A chapter 1 (subchapters A and B in full for the
individual-facing sections, individual-facing parts of D, E, F, O, P, N) plus
chapters 2, 2A, 21, 24, 61, 65, 79, the 26 CFR part 1 regulation families, the
annual revenue procedures and notices, and the IRS forms and instructions. State
elements are the facts a section-by-section reading of a state individual income
tax chapter yields, plus its regulations, annual forms, rate schedules and
bulletins. PolicyEngine (gov/irs, gov/states/<st>/tax, gov/local) and rulespec-us
are cross-checks only.

Statuses:
  PRESENT      a specific provision body in a selected scope carries the fact
               (body read by regex; the matched snippet is quoted in evidence_note)
  EXTRACTABLE  the rule exists and the publisher posts the carrying family; not taken
  ABSENT       the rule exists but the publisher posts nothing carrying it
  OUTREACH     the queue records a publisher block
  REVIEW       could not tell from corpus + queue evidence
  N/A          the jurisdiction's law has no such rule (analyst knowledge, flagged)
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

import yaml

STATES = (
    "ak al ar az ca co ct dc de fl ga hi ia id il in ks ky la ma md me mi mn mo ms "
    "mt nc nd ne nh nj nm nv ny oh ok or pa ri sc sd tn tx ut va vt wa wi wv wy"
).split()
NO_BROAD_TAX = {"ak", "fl", "nv", "nh", "sd", "tn", "tx", "wa", "wy"}
TAX_STATES = [s for s in STATES if s not in NO_BROAD_TAX]

# Citation-path filter for the individual income tax chapter of each state's code
# (whole-title scopes such as Colorado title 39, Georgia title 48, Indiana title 6,
# Louisiana title 47, Montana title 15, New Mexico chapter 7, Oklahoma title 68 and
# DC title 47 otherwise match sales, excise and corporate sections).
INCOME_TAX_CHAPTER = {
    "ak": r"^us-ak/statute/43/20", "al": r"^us-al/statute/40-18", "ar": r"^us-ar/statute/act-2-2026",
    "az": r"^us-az/statute/43-", "ca": r"^us-ca/statute/rtc/17", "co": r"^us-co/statute/39/39-22-",
    "ct": r"^us-ct/statute/(2026-supplement/)?12-7", "dc": r"^us-dc/statute/47/47-18",
    "de": r"^us-de/statute/30/11", "fl": r"^us-fl/statute/(constitution|title-xiv/chapter-220|session-laws)",
    "ga": r"^us-ga/statute/48/48-7", "hi": r"^us-hi/statute/235", "ia": r"^us-ia/statute/422",
    "id": r"^us-id/statute/63-30", "il": r"^us-il/statute/(35/5|public-act)", "in": r"^us-in/statute/6-3(\.[16])?-",
    "ks": r"^us-ks/statute/(2026/|session-2026/)?79-32", "ky": r"^us-ky/statute/(krs/141|11/141)",
    "la": r"^us-la/statute/47:(2?\d{1,2}|1\d{2}|2\d{2}|300|297\.\d+|6\d{3})(\.\d+)?$", "ma": r"^us-ma/statute/62/",
    "md": r"^us-md/statute/gtg/10", "me": r"^us-me/statute/36/5", "mi": r"^us-mi/statute/(recovery/us-mi-code-)?206",
    "mn": r"^us-mn/statute/290", "mo": r"^us-mo/statute/143", "ms": r"^us-ms/statute/27-7", "mt": r"^us-mt/statute/15-30",
    "nc": r"^us-nc/statute/(105/105-15|recovery/us-nc-code-105/block-13)", "nd": r"^us-nd/statute/57/57-38",
    "ne": r"^us-ne/statute/77/77-27", "nh": r"^us-nh/statute/(chapter-77|title-v)", "nj": r"^us-nj/statute/54a",
    "nm": r"^us-nm/statute/7-2-", "nv": r"^us-nv/statute/constitution", "ny": r"^us-ny/statute/(TAX/6|NYC)",
    "oh": r"^us-oh/statute/5747", "ok": r"^us-ok/statute/68-23", "or": r"^us-or/statute/31[56]",
    "pa": r"^us-pa/statute/act-1971-2/article-3", "ri": r"^us-ri/statute/44-30", "sc": r"^us-sc/statute/12-6",
    "sd": r"^us-sd/statute/10/43", "tn": r"^us-tn/statute/public-chapter", "tx": r"^us-tx/statute",
    "ut": r"^us-ut/statute/59-10", "va": r"^us-va/statute/58.1", "vt": r"^us-vt/statute/32-58",
    "wa": r"^us-wa/statute/82/82\.87", "wi": r"^us-wi/statute/71", "wv": r"^us-wv/statute/11-21", "wy": r"^us-wy/statute",
}

# State law facts (tax year 2025), analyst knowledge used only to separate N/A
# from EXTRACTABLE when the corpus lacks the fact. Flagged uncertain in the
# schema; a reviewer should verify each set against the state code.
K = {
    "eitc": set("ca co ct de dc hi il in ia ks la me md ma mi mn mo mt ne nj nm ny oh ok or ri sc ut vt va wa wi".split()),
    "ctc": set("az ca co ga id il me md ma mn nj nm ny ok or ut vt nc".split()),
    "cdcc": set("ar ca co de dc ga hi ia ks ky la me md mn ne nm ny oh ok or pa ri sc vt va wi wv nj mt".split()),
    "amt": set("ca co ct mn".split()),
    "no_std_ded": set("il in ma mi nj oh pa wv ct co nd sc ut".split()),
    "no_itemized": set("il in ma mi nj oh pa wv ct ut".split()),
    "no_pers_exemption": set("co nd sc mo ut la".split()),  # states with no separate personal exemption/credit
    "indexed": set("ca id me mn mo mt ne nd oh or ri sc vt wi ar ia nm ny nj il ma".split()),  # see schema note
    "cap_gains": set("ar az co hi ia id ks? ma mt nm nd ok sc vt wi wa ne mo".split()),
    "surtax": set("ca ma ny nh tn wa".split()),
    "local": set("al co de in ia ky md mi mo nj ny oh or pa wv".split()),
    "other_state_credit": set(TAX_STATES) - {"nj"} | {"nj"},
    "low_income": set("ar az dc ga hi ia ks ky md me mo nm ny oh ok pa va wi wv".split()),
    "circuit_breaker": set("az ca co ct dc hi ia il in ks ma md me mi mn mo mt nj nm ny nd oh ok or pa ri sc ut vt wi wv".split()),
    "ss_partial_tax": set("co ct mn mt nm ri ut vt wv".split()),
    "flat": set("az co ga id il in ia ky la ms mi nc pa ut".split()),
}
K["cap_gains"].discard("ks?")

# ---------------------------------------------------------------------------
# Federal schema (facts, section by section). Fields: id, label, sections (26
# U.S.C.), family, fact regex applied to the section body (None = section body
# suffices), annual checks [(scope substring, regex, label)], pe dirs, notes.
# ---------------------------------------------------------------------------
FED = [
    # subchapter A part I
    ("F001", "1(a)-(d),(i),(j): ordinary income rate schedule structure (10/12/22/24/32/35/37, OBBBA permanent)", ["1"], "federal statute", r"37\s?(%|percent)", None, ["irs/income/bracket"], ""),
    ("F002", "1(f): inflation adjustment method (C-CPI-U, base years, rounding)", ["1"], "federal statute", r"chained|C-CPI-U", None, ["irs/income/bracket"], ""),
    ("F003", "1(g): kiddie tax (net unearned income of a child taxed at parents' rate)", ["1"], "federal statute", r"unearned income", None, [], "PE: no kiddie tax"),
    ("F004", "1(h): capital gains and qualified dividend rates (0/15/20, 25 unrecaptured 1250, 28 collectibles) and breakpoints", ["1"], "federal statute", r"28 percent|collectibles", None, ["irs/capital_gains"], ""),
    ("F005", "TY2025 bracket dollar thresholds (as printed in the 2025 Form 1040 instructions tax rate schedules)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"626,350", "37% single threshold $626,350")], ["irs/income/bracket"], ""),
    ("F006", "TY2026 bracket dollar thresholds (Rev. Proc. 2025-32 sec. 3.01)", [], "revenue procedure", None, [("us/guidance/2026-05-02-irs-rev-proc-2025-32", r"640,600", "37% single threshold $640,600")], ["irs/income/bracket"], ""),
    ("F007", "3: tax table for individuals (statute) and the TY2025 tax table as printed", ["3"], "federal statute", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"2025 Tax Table", "2025 Tax Table in i1040gi block-152")], [], "PE: computes from brackets, no table"),
    ("F008", "TY2025 capital-gain rate breakpoints ($48,350 single 0% ceiling) as printed", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"48,350", "0% breakpoint $48,350")], ["irs/capital_gains"], ""),
    ("F009", "2: surviving spouse and head of household definitions", ["2"], "federal statute", r"head of a household|surviving spouse", None, ["irs/income/bracket"], "filing status"),
    # part IV credits
    ("F010", "21: child and dependent care credit (35%->20% rate, $3,000/$6,000 expense limits, earned income limit)", ["21"], "federal statute", r"3,000|6,000", None, ["irs/credits/cdcc"], ""),
    ("F011", "22: credit for the elderly and disabled ($5,000/$7,500 base amounts, 15% rate)", ["22"], "federal statute", r"5,000|7,500", None, ["irs/credits/elderly_or_disabled"], ""),
    ("F012", "23: adoption expense credit (dollar limit, phase-out, OBBBA refundable portion)", ["23"], "federal statute", None, None, [], "PE: not modeled"),
    ("F013", "24: child tax credit amount ($2,200 OBBBA), other-dependent credit $500, SSN requirement", ["24"], "federal statute", r"2,200", None, ["irs/credits/ctc"], ""),
    ("F014", "24(d): additional child tax credit refundable cap, 15% earned income formula, $2,500 threshold", ["24"], "federal statute", r"2,500", None, ["irs/credits/ctc/refundable"], ""),
    ("F015", "24(b): CTC phase-out thresholds ($200,000/$400,000) and $50 per $1,000 rate", ["24"], "federal statute", r"400,000", None, ["irs/credits/ctc/phase_out"], ""),
    ("F016", "TY2025 refundable CTC cap ($1,700) as printed in Schedule 8812 instructions", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"1,700", "refundable cap $1,700")], ["irs/credits/ctc/refundable"], ""),
    ("F017", "TY2026 refundable CTC cap (Rev. Proc. 2025-32 sec. 3.05)", [], "revenue procedure", None, [("us/guidance/2026-05-02-irs-rev-proc-2025-32", r"1,700", "refundable cap $1,700")], ["irs/credits/ctc/refundable"], ""),
    ("F018", "25A: American Opportunity credit (100%/25%, $2,500, 40% refundable, MAGI $80k-$90k) and Lifetime Learning credit (20%, $10,000)", ["25A"], "federal statute", r"80,000|2,500", None, ["irs/credits/education"], ""),
    ("F019", "25B: saver's credit rates (50/20/10) and AGI thresholds", ["25B"], "federal statute", r"50 percent", None, ["irs/credits/retirement_saving"], ""),
    ("F020", "2026 saver's credit AGI thresholds (Notice 2025-67)", [], "IRS notices", None, [("us/guidance/2026-07-23-irs-notice-2025-67", r"(?i)saver|25B", "Notice 2025-67 saver's credit item")], ["irs/credits/retirement_saving"], ""),
    ("F021", "25C: energy efficient home improvement credit (30%, $1,200/$2,000 caps, termination)", ["25C"], "federal statute", r"1,200|2,000", None, ["irs/credits/energy_efficient_home_improvement"], ""),
    ("F022", "25D: residential clean energy credit (30%, phase-down, termination)", ["25D"], "federal statute", r"30 percent", None, ["irs/credits/residential_clean_energy"], ""),
    ("F023", "25E/30D: clean vehicle credits ($4,000/$7,500, MAGI limits, termination)", ["25E", "30D"], "federal statute", r"7,500|4,000", None, ["irs/credits/clean_vehicle"], ""),
    ("F024", "25: mortgage credit certificate credit", ["25"], "federal statute", None, None, [], "PE: not modeled"),
    ("F025", "26: nonrefundable personal credit limitation and ordering", ["26"], "federal statute", None, None, [], ""),
    ("F026", "27/901/904: foreign tax credit and limitation", ["27", "901", "904"], "federal statute", None, None, [], "PE: not modeled"),
    ("F027", "32(a)-(b): EITC credit and phase-out percentages by number of children", ["32"], "federal statute", r"7\.65|34 percent|45 percent", None, ["irs/credits/eitc"], ""),
    ("F028", "32(c): EITC eligibility (qualifying child, age 25-64 childless, SSN, investment income limit, MFS)", ["32"], "federal statute", r"age 25|social security", None, ["irs/credits/eitc/eligibility"], ""),
    ("F029", "TY2025 EITC earned income amounts, maximum credits, phase-out thresholds and the EIC table as printed", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"8,046", "max credit 3+ children $8,046")], ["irs/credits/eitc"], ""),
    ("F030", "TY2026 EITC amounts (Rev. Proc. 2025-32 sec. 3.07)", [], "revenue procedure", None, [("us/guidance/2026-05-02-irs-rev-proc-2025-32", r"8,231", "max credit 3+ children $8,231")], ["irs/credits/eitc"], ""),
    ("F031", "EITC investment income limit TY2025 ($11,950) and TY2026 ($12,200)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"11,950", "TY2025 $11,950"), ("us/guidance/2026-05-02-irs-rev-proc-2025-32", r"12,200", "TY2026 $12,200")], ["irs/credits/eitc"], ""),
    ("F032", "36B: premium tax credit (applicable percentage schedule, household income bands, repayment caps)", ["36B"], "federal statute", r"applicable percentage", None, ["irs/credits/premium_tax_credit"], ""),
    ("F033", "2026 section 36B applicable percentage table (Rev. Proc. 2025-25)", [], "revenue procedure", None, [("us/guidance/2026-07-13-recovery", r"(?i)applicable percentage", "Rev. Proc. 2025-25 pages")], ["irs/credits/premium_tax_credit"], ""),
    ("F034", "2027 section 36B applicable percentage table (Rev. Proc. 2026-26)", [], "revenue procedure", None, [("us/guidance/2026-09-10-tax-irs-guidance", r"(?i)applicable percentage", "Rev. Proc. 2026-26 pages")], ["irs/credits/premium_tax_credit"], ""),
    ("F035", "31: credit for tax withheld on wages", ["31"], "federal statute", None, None, [], ""),
    ("F036", "35: health coverage tax credit (expired)", ["35"], "federal statute", None, None, [], "PE: not modeled"),
    ("F037", "53: credit for prior-year minimum tax", ["53"], "federal statute", None, None, [], "PE: not modeled"),
    # part VI AMT
    ("F038", "55: AMT rates (26/28), exemption amounts and phase-out (OBBBA), 55(d)", ["55"], "federal statute", r"26 percent", None, ["irs/income/amt"], ""),
    ("F039", "56/57/58/59: AMTI adjustments, preference items, other AMT rules", ["56", "57", "58", "59"], "federal statute", None, None, ["irs/income/amt"], ""),
    ("F040", "TY2025 AMT exemption amounts ($88,100/$137,000) as printed", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"88,100|137,000", "$88,100 / $137,000")], ["irs/income/amt/exemption"], "Form 6251 instructions not taken"),
    ("F041", "TY2026 AMT exemption amounts (Rev. Proc. 2025-32 sec. 3.11)", [], "revenue procedure", None, [("us/guidance/2026-05-02-irs-rev-proc-2025-32", r"90,100|140,200", "$90,100 / $140,200")], ["irs/income/amt/exemption"], ""),
    # subchapter B part I
    ("F042", "61: gross income definition", ["61"], "federal statute", None, None, ["irs/gross_income"], ""),
    ("F043", "62: above-the-line deductions (AGI): educator, HSA, SE tax half, SE health, IRA, student loan, alimony, moving (Armed Forces)", ["62"], "federal statute", r"adjusted gross income", None, ["irs/ald"], ""),
    ("F044", "63(c): basic standard deduction amounts ($15,750/$31,500/$23,625 OBBBA 2025) and indexing", ["63"], "federal statute", r"15,750|23,625", None, ["irs/deductions/standard"], ""),
    ("F045", "63(c)(3),(f): additional standard deduction for aged or blind", ["63"], "federal statute", r"aged|blind", None, ["irs/deductions/standard/aged_or_blind"], ""),
    ("F046", "63(c)(5): standard deduction limitation for dependents", ["63"], "federal statute", r"dependent", None, ["irs/deductions/standard/dependent"], ""),
    ("F047", "TY2025 standard deduction amounts as printed (2025 Form 1040 instructions)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"15,750", "$15,750")], ["irs/deductions/standard"], ""),
    ("F048", "TY2026 standard deduction amounts (Rev. Proc. 2025-32 sec. 3.16: $16,100/$32,200/$24,150)", [], "revenue procedure", None, [("us/guidance/2026-05-02-irs-rev-proc-2025-32", r"16,100", "$16,100")], ["irs/deductions/standard"], ""),
    ("F049", "TY2026 aged/blind additional amounts ($1,650/$2,050) (Rev. Proc. 2025-32)", [], "revenue procedure", None, [("us/guidance/2026-05-02-irs-rev-proc-2025-32", r"1,650|2,050", "$1,650 / $2,050")], ["irs/deductions/standard/aged_or_blind"], ""),
    ("F050", "67: 2-percent floor on miscellaneous itemized deductions (suspended, OBBBA permanent)", ["67"], "federal statute", None, None, ["irs/deductions/itemized/misc"], ""),
    ("F051", "68: overall limitation on itemized deductions (OBBBA 2/37 reduction from 2026)", ["68"], "federal statute", None, None, ["irs/deductions/itemized/limitation"], ""),
    # part II inclusions
    ("F052", "71/215: alimony inclusion and deduction (pre-2019 instruments)", ["71", "215"], "federal statute", None, None, ["irs/ald/alimony_expense"], ""),
    ("F053", "72: annuities and 72(t) 10% early distribution penalty", ["72"], "federal statute", None, None, [], "PE: not modeled"),
    ("F054", "85: unemployment compensation includible", ["85"], "federal statute", None, None, ["irs/unemployment_compensation"], ""),
    ("F055", "86: taxation of Social Security benefits (50%/85%, $25,000/$32,000 and $34,000/$44,000 thresholds)", ["86"], "federal statute", r"25,000|44,000", None, ["irs/social_security/taxability"], ""),
    # part III exclusions
    ("F056", "101: life insurance death benefits excluded", ["101"], "federal statute", None, None, [], ""),
    ("F057", "102: gifts and inheritances excluded", ["102"], "federal statute", None, None, [], ""),
    ("F058", "103: interest on state and local bonds excluded", ["103"], "federal statute", None, None, ["irs/gross_income"], ""),
    ("F059", "104/105/106: injury compensation, accident and health plan exclusions", ["104", "105", "106"], "federal statute", None, None, [], ""),
    ("F060", "108: discharge of indebtedness exclusions", ["108"], "federal statute", None, None, [], "PE: not modeled"),
    ("F061", "112: combat zone compensation exclusion", ["112"], "federal statute", None, None, [], ""),
    ("F062", "117: qualified scholarships exclusion", ["117"], "federal statute", None, None, [], "PE: not modeled"),
    ("F063", "121: exclusion of gain on sale of principal residence ($250,000/$500,000)", ["121"], "federal statute", None, None, [], "PE: not modeled"),
    ("F064", "125: cafeteria plans", ["125"], "federal statute", None, None, [], ""),
    ("F065", "129: dependent care assistance exclusion ($5,000; $7,500 from 2026 OBBBA)", ["129"], "federal statute", None, None, ["irs/gross_income/dependent_care_assistance_programs"], ""),
    ("F066", "132: fringe benefits exclusion", ["132"], "federal statute", None, None, [], "PE: not modeled"),
    ("F067", "135: US savings bond interest used for education", ["135"], "federal statute", None, None, [], "PE: not modeled"),
    ("F068", "137: adoption assistance exclusion", ["137"], "federal statute", None, None, [], "PE: not modeled"),
    ("F069", "139: disaster relief payments excluded", ["139"], "federal statute", None, None, [], "PE: not modeled"),
    # part V exemptions
    ("F070", "151: personal exemption amount (zero, OBBBA permanent) and 151(d)(5) senior deduction $6,000 (2025-2028)", ["151"], "federal statute", r"6,000", None, ["irs/deductions/senior_deduction", "irs/income/exemption"], ""),
    ("F071", "152: dependent definition (qualifying child, qualifying relative, tie-breaker, support)", ["152"], "federal statute", r"qualifying child", None, ["irs/dependent"], ""),
    # part VI/VII deductions
    ("F072", "162: trade or business expenses (individual-facing: SE health insurance 162(l))", ["162"], "federal statute", None, None, ["irs/ald"], ""),
    ("F073", "163(h): qualified residence interest ($750,000 limit) and mortgage insurance premiums", ["163"], "federal statute", r"750,000", None, ["irs/deductions/itemized/interest"], ""),
    ("F074", "163(h)(4): qualified passenger vehicle loan interest deduction (OBBBA, $10,000, MAGI phase-out)", ["163"], "federal statute", r"passenger vehicle|10,000", None, ["irs/deductions/auto_loan_interest"], ""),
    ("F075", "164(b)(6): SALT deduction cap ($40,000 2025, $40,400 2026, MAGI phase-down to $10,000)", ["164"], "federal statute", r"40,000|40,400", None, ["irs/deductions/itemized/salt_and_real_estate"], ""),
    ("F076", "165: casualty (federally declared disaster) and wagering loss limits (90% OBBBA)", ["165"], "federal statute", r"90 percent|wagering", None, ["irs/deductions/itemized/casualty"], ""),
    ("F077", "170: charitable contribution percentage limits, 0.5% floor (2026), non-itemizer deduction $1,000/$2,000 (2026)", ["170"], "federal statute", r"60 percent|1,000", None, ["irs/deductions/itemized/charity"], ""),
    ("F078", "172: net operating loss deduction (80% limit, carryforward)", ["172"], "federal statute", None, None, [], "PE: not modeled"),
    ("F079", "199A: qualified business income deduction (20%, thresholds, phase-in, $400 minimum OBBBA)", ["199A"], "federal statute", r"20 percent", None, ["irs/deductions/qbi"], ""),
    ("F080", "TY2026 199A threshold amounts (Rev. Proc. 2025-32 sec. 3.27)", [], "revenue procedure", None, [("us/guidance/2026-05-02-irs-rev-proc-2025-32", r"(?i)199A|qualified business income", "199A item")], ["irs/deductions/qbi/phase_out"], ""),
    ("F081", "212: expenses for production of income", ["212"], "federal statute", None, None, [], ""),
    ("F082", "213: medical expense deduction 7.5% AGI floor", ["213"], "federal statute", r"7\.5 percent", None, ["irs/deductions/itemized/medical"], ""),
    ("F083", "217: moving expenses (Armed Forces only)", ["217"], "federal statute", None, None, [], ""),
    ("F084", "219: IRA deduction limit and active-participant phase-out", ["219"], "federal statute", r"active participant", None, ["irs/gross_income/retirement_contributions"], ""),
    ("F085", "2026 IRA, 401(k), catch-up and phase-out amounts (Notice 2025-67)", [], "IRS notices", None, [("us/guidance/2026-07-23-irs-notice-2025-67", r"24,500|7,500", "401(k) $24,500 / IRA $7,500")], ["irs/gross_income/retirement_contributions/limit"], ""),
    ("F086", "221: student loan interest deduction ($2,500, MAGI phase-out)", ["221"], "federal statute", r"2,500", None, ["irs/ald/student_loan_interest"], ""),
    ("F087", "223: HSA contribution limits and eligibility", ["223"], "federal statute", None, None, [], "PE: not modeled"),
    ("F088", "2026 HSA inflation-adjusted amounts (Rev. Proc. 2025-19)", [], "revenue procedure", None, [("us/guidance/irs/rev-proc-2025-19", r"(?i)health savings", "Rev. Proc. 2025-19 document")], [], ""),
    ("F089", "2027 HSA inflation-adjusted amounts (Rev. Proc. 2026-24)", [], "revenue procedure", None, [("us/guidance/2026-09-10-tax-irs-guidance", r"(?i)health savings|HSA", "Rev. Proc. 2026-24")], [], ""),
    ("F090", "224: qualified tips deduction (OBBBA, $25,000 cap, MAGI phase-out)", ["224"], "federal statute", r"25,000", None, ["irs/deductions/tip_income"], ""),
    ("F091", "225: qualified overtime deduction (OBBBA, $12,500/$25,000 cap, MAGI phase-out)", ["225"], "federal statute", r"12,500", None, ["irs/deductions/overtime_income"], ""),
    # subchapter D/E/F/O/P
    ("F092", "401(k)/402/403(b)/457: qualified plan deferrals and taxation of distributions", ["401", "402", "403", "457"], "federal statute", None, None, ["irs/gross_income/retirement_contributions"], ""),
    ("F093", "408: traditional IRA rules; 408A Roth IRA contribution limits and MAGI phase-out", ["408", "408A"], "federal statute", None, None, [], ""),
    ("F094", "415: qualified plan contribution and benefit limits (indexed)", ["415"], "federal statute", None, None, [], ""),
    ("F095", "461(l): excess business loss limitation (indexed thresholds)", ["461"], "federal statute", None, None, [], "PE: not modeled"),
    ("F096", "469: passive activity loss rules ($25,000 rental allowance)", ["469"], "federal statute", None, None, [], "PE: not modeled"),
    ("F097", "529/529A/530: qualified tuition programs, ABLE, Coverdell", ["529", "529A", "530"], "federal statute", None, None, [], "PE: not modeled"),
    ("F098", "1001/1011-1016: amount realized and basis rules", ["1001", "1012", "1014", "1015", "1016"], "federal statute", None, None, [], "PE: not modeled"),
    ("F099", "1211/1212: capital loss limitation ($3,000) and carryover", ["1211", "1212"], "federal statute", r"3,000", None, ["irs/ald/loss/capital"], ""),
    ("F100", "1221/1222/1223: capital asset, short/long-term definitions, holding period", ["1221", "1222", "1223"], "federal statute", None, None, ["irs/capital_gains"], ""),
    ("F101", "1250/1(h)(6): unrecaptured section 1250 gain", ["1250"], "federal statute", None, None, [], "PE: not modeled"),
    ("F102", "66: community income treatment", ["66"], "federal statute", None, None, [], "PE: not modeled"),
    # chapters 2, 2A, 21, 24
    ("F103", "1401/1402: self-employment tax rates (12.4 + 2.9), 92.35% net earnings, $400 threshold", ["1401", "1402"], "federal statute", r"92\.35|400", None, ["irs/self_employment"], ""),
    ("F104", "1411: net investment income tax 3.8% and $200,000/$250,000 thresholds", ["1411"], "federal statute", r"3\.8|250,000", None, ["irs/investment/net_investment_income_tax"], ""),
    ("F105", "3101/3111/3121: FICA employee and employer rates (6.2/1.45), Additional Medicare Tax 0.9%, wages definition", ["3101", "3111", "3121"], "federal statute", r"0\.9|6\.2", None, ["irs/payroll"], ""),
    ("F106", "Social Security contribution and benefit base 2026 ($184,500)", [], "SSA automatic determinations", None, [("us/guidance/2026-05-17-ssa-automatic-determinations-2026", r"184,500", "$184,500")], ["irs/payroll/social_security"], ""),
    ("F164", "Social Security contribution and benefit base 2025 ($176,100) (SSA determination for 2025; only the 2024 and 2026 pages are selected)", [], "SSA automatic determinations", None, [("us/guidance/", r"176,100", "$176,100")], ["irs/payroll/social_security"], ""),
    ("F107", "3401/3402: wages for withholding, withholding at source, W-4", ["3401", "3402"], "federal statute", None, None, [], ""),
    ("F108", "Publication 15-T withholding tables and percentage method (2025, 2026)", [], "IRS forms and instructions", None, [("us/form/", r"(?i)publication 15-T|percentage method tables", "Pub 15-T")], [], "PE: no withholding"),
    ("F109", "3405/3406: pension withholding and backup withholding", ["3405", "3406"], "federal statute", None, None, [], ""),
    # chapters 61, 65, 68, 79
    ("F110", "6012: filing thresholds (gross income >= standard deduction; dependents)", ["6012"], "federal statute", None, None, ["irs/income/filing_requirement"], ""),
    ("F111", "6013: joint returns (election, MFS switch, deceased spouse)", ["6013"], "federal statute", None, None, [], ""),
    ("F112", "6401: refundable credits treated as overpayments", ["6401"], "federal statute", None, None, [], ""),
    ("F113", "6654: estimated tax underpayment penalty and safe harbors (90%/100%/110%)", ["6654"], "federal statute", None, None, [], "PE: not modeled"),
    ("F114", "6072/6081: return due date and extensions", ["6072", "6081"], "federal statute", None, None, [], "PE: not modeled"),
    ("F115", "7703: marital status determination; 7701(b) resident alien; 7701(a)(17) husband and wife", ["7701", "7703"], "federal statute", None, None, [], ""),
    # regulations (26 CFR part 1)
    ("F116", "26 CFR 1.1-1, 1.2-2: income tax on individuals; head of household and surviving spouse rules", [], "IRS regulation", None, None, [], "reg family"),
    ("F117", "26 CFR 1.21-1 to 1.21-4: dependent care credit regulations", [], "IRS regulation", None, None, ["irs/credits/cdcc"], ""),
    ("F118", "26 CFR 1.32-2, 1.32-3: EITC regulations", [], "IRS regulation", None, None, ["irs/credits/eitc"], ""),
    ("F119", "26 CFR 1.36B-1 to 1.36B-6: premium tax credit regulations (family glitch, affordability)", [], "IRS regulation", None, None, ["irs/credits/premium_tax_credit"], ""),
    ("F120", "26 CFR 1.61-1 to 1.63-2: gross income, AGI, taxable income, standard deduction election", [], "IRS regulation", None, None, [], ""),
    ("F121", "26 CFR 1.151-1 to 1.152-4: exemptions and dependents (support, tie-breaker)", [], "IRS regulation", None, None, ["irs/dependent"], ""),
    ("F122", "26 CFR 1.162-1 to 1.165-12: business expenses, interest tracing, taxes, losses", [], "IRS regulation", None, None, [], ""),
    ("F123", "26 CFR 1.170A-1 to 1.170A-18: charitable contributions", [], "IRS regulation", None, None, [], ""),
    ("F124", "26 CFR 1.199A-1 to 1.199A-12: QBI deduction", [], "IRS regulation", None, None, [], ""),
    ("F125", "26 CFR 1.213-1, 1.219-1, 1.221-1: medical, IRA, student loan interest", [], "IRS regulation", None, None, [], ""),
    ("F126", "26 CFR 1.401(k)-1 to 1.408A-10: qualified plans, IRAs, Roth IRAs", [], "IRS regulation", None, None, [], ""),
    ("F127", "26 CFR 1.1001-1 to 1.1016-10, 1.1211-1, 1.1212-1: basis and capital losses", [], "IRS regulation", None, None, [], ""),
    ("F128", "26 CFR 1.1401-1, 1.1402(a)-1 to 1.1402(h)-1: self-employment tax", [], "IRS regulation", None, [("us/regulation/2026-07-24-1401-coordination-repair-title-26-part-1", r"self-employment", "1.1401-1 present")], ["irs/self_employment"], ""),
    ("F129", "26 CFR 1.1411-1 to 1.1411-10: net investment income tax", [], "IRS regulation", None, None, [], ""),
    ("F130", "26 CFR 1.6012-1, 1.6013-1 to 1.6013-7, 1.6654-1: filing, joint returns, estimated tax", [], "IRS regulation", None, None, [], ""),
    ("F131", "26 CFR 31.3101-1 to 31.3402(r)-1: FICA and income tax withholding", [], "IRS regulation", None, None, [], ""),
    ("F132", "26 CFR 301.7701-18, 1.7703-1: marital status", [], "IRS regulation", None, None, [], ""),
    # revenue procedures, notices
    ("F133", "Rev. Proc. 2024-40: tax year 2025 inflation adjustments (pre-OBBBA base amounts still governing non-amended items)", [], "revenue procedure", None, [("us/guidance/irs/rev-proc-2024-40", r"(?i)inflation", "Rev. Proc. 2024-40 document")], [], ""),
    ("F134", "Rev. Proc. 2025-32: tax year 2026 inflation adjustments (all sec. 3 items)", [], "revenue procedure", None, [("us/guidance/2026-05-02-irs-rev-proc-2025-32", r"(?i)Rev\. Proc\. 2025-32|2025-32", "document present")], ["irs/income/bracket"], ""),
    ("F135", "Notice 2025-67: 2026 retirement plan and IRA limits", [], "IRS notices", None, [("us/guidance/2026-07-23-irs-notice-2025-67", r"2025-67", "document present")], ["irs/gross_income/retirement_contributions"], ""),
    ("F136", "Notice 2026-10: 2026 standard mileage rates", [], "IRS notices", None, [("us/guidance/2026-09-10-tax-irs-guidance", r"(?i)mileage", "document present")], [], ""),
    ("F137", "Revenue procedure setting tax year 2027 items (not issued as of 2026-09-10)", [], "revenue procedure", None, [("us/guidance/", r"tax year 2027 (?:inflation|adjust)", "TY2027 rev proc")], [], ""),
    ("F138", "TY2025 kiddie-tax unearned income threshold ($2,700) and TY2026 (Rev. Proc. 2025-32 sec. 3.02)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"2,700", "$2,700"), ("us/guidance/2026-05-02-irs-rev-proc-2025-32", r"1,350", "sec. 3.02: 1(g)(4)(A)(ii)(I) amount $1,350 (threshold $2,700)")], [], "PE: not modeled"),
    # forms and instructions (product family = form + instructions)
    ("F139", "Form 1040 and the 2025 Instructions for Form 1040 (line-by-line rules, worksheets)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Form 1040", "i1040gi present")], [], ""),
    ("F140", "Schedules 1, 2, 3 (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Schedule 1 \(Form 1040\)", "f1040s1 present")], [], ""),
    ("F141", "Schedule 1-A (2025): OBBBA additional deductions (tips, overtime, car loan interest, seniors) worksheet", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Schedule 1-A", "f1040s1a present")], [], ""),
    ("F142", "Schedule A and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Schedule A", "i1040sca present")], [], ""),
    ("F143", "Schedule B and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Schedule B", "i1040sb present")], [], ""),
    ("F144", "Schedule C and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Schedule C", "i1040sc")], [], ""),
    ("F145", "Schedule D and instructions (2025), incl. Qualified Dividends and Capital Gain Tax Worksheet", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Schedule D", "i1040sd present")], [], ""),
    ("F146", "Schedule E and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Schedule E", "i1040se")], [], ""),
    ("F147", "Schedule EIC (2025) and the EIC instructions/worksheets in i1040gi", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Schedule EIC", "f1040sei present")], [], ""),
    ("F148", "Schedule SE and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Schedule SE", "i1040sse present")], [], ""),
    ("F149", "Schedule 8812 and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Schedule 8812", "i1040s8 present")], [], ""),
    ("F150", "Form 8962 and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Form 8962", "i8962 present")], [], ""),
    ("F151", "Form 2441 and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Form 2441", "i2441")], [], ""),
    ("F152", "Form 8863 and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Form 8863", "i8863")], [], ""),
    ("F153", "Form 6251 and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Form 6251", "i6251")], [], ""),
    ("F154", "Forms 8959 and 8960 and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Form 8959", "i8959")], [], ""),
    ("F155", "Form 8995/8995-A and instructions (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Instructions for Form 8995", "i8995")], [], ""),
    ("F156", "Form 8880 saver's credit (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Form 8880[\s\S]{0,200}Credit for Qualified Retirement", "f8880")], [], ""),
    ("F157", "Form 1040-ES (2026) estimated tax worksheet and 2026 rate schedules", [], "IRS forms and instructions", None, [("us/form/", r"(?i)1040-ES[\s\S]{0,200}Estimated Tax Worksheet", "f1040es")], [], ""),
    ("F158", "Form W-4 (2026)", [], "IRS forms and instructions", None, [("us/form/", r"(?i)Form W-4[\s\S]{0,100}Employee.s Withholding Certificate", "fw4")], [], ""),
    ("F159", "Publication 17 (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Publication 17", "p17 present")], [], ""),
    ("F160", "Publication 501 (dependents, standard deduction, filing information) (2025)", [], "IRS forms and instructions", None, [("us/form/", r"(?i)Publication 501[\s\S]{0,100}Dependents", "p501")], [], ""),
    ("F161", "Publication 596 (EITC) (2025)", [], "IRS forms and instructions", None, [("us/form/", r"(?i)Publication 596", "p596")], [], ""),
    ("F162", "Publication 970 (education benefits) (2025)", [], "IRS forms and instructions", None, [("us/form/", r"(?i)Publication 970", "p970")], [], ""),
    ("F163", "Form 1040-SR (2025)", [], "IRS forms and instructions", None, [("us/form/2026-09-10-tax-irs-forms-ty2025", r"(?i)Form 1040-SR[\s\S]{0,80}Tax Return for Seniors", "f1040sr")], [], ""),
]

FORM_PRODUCTS = {
    "F139": ["f1040", "i1040gi"], "F140": ["f1040s1", "f1040s2", "f1040s3"], "F141": ["f1040s1a"], "F142": ["f1040sa", "i1040sca"],
    "F143": ["f1040sb", "i1040sb"], "F144": ["f1040sc", "i1040sc"], "F145": ["f1040sd", "i1040sd"], "F146": ["f1040se", "i1040se"],
    "F147": ["f1040sei"], "F148": ["f1040sse", "i1040sse"], "F149": ["f1040s8", "i1040s8"], "F150": ["f8962", "i8962"],
    "F151": ["f2441", "i2441"], "F152": ["f8863", "i8863"], "F153": ["f6251", "i6251"], "F154": ["f8959", "f8960", "i8959", "i8960"],
    "F155": ["f8995", "i8995"], "F156": ["f8880"], "F157": ["f1040es"], "F158": ["fw4"], "F159": ["p17"], "F160": ["p501"],
    "F161": ["p596"], "F162": ["p970"], "F163": ["f1040sr"],
}

# Section presence lookup is built from the corpus; the following sections are
# expected absent from every selected us/statute scope and are marked
# EXTRACTABLE with the USLM carrier.
USLM = "26 U.S.C. USLM XML release points at https://uscode.house.gov/download/releasepoints/ (the 2026-08-03 title-26 union scope was built from one) list every section"
ECFR = "eCFR title 26 chapter I (https://www.ecfr.gov/current/title-26) posts every part-1 and part-31 section; no selected us/regulation scope carries them"
IRB = "irs.gov/irb posts the Internal Revenue Bulletin issue"
IRSFORMS = "irs.gov/forms-instructions and /forms-pubs list the product (queue row us index_document_count 35; 19 taken)"

# ---------------------------------------------------------------------------
# State schema (facts). Fields: id, label, level, family, patterns, doc classes,
# pe key, known-law key (None = every income-tax state has it), applies to
# no-broad-tax states?
# ---------------------------------------------------------------------------
Q = r"[\"“”]"
S = [
    # id, label, level, family, patterns, classes, pe key, known key, applies to no-tax states, options
    ("S01", "Imposition of the individual income tax (or the constitutional/statutory bar for the nine no-tax states)", "state", "state statute",
     [r"(?i)(hereby )?(imposed|levied)[^.]{0,300}(taxable income|net income|income of every|income tax|upon every (resident )?individual|on the income)", r"(?i)(income tax|tax on (the )?(taxable |net )?income)[^.]{0,200}(hereby )?(imposed|levied)", r"(?i)imposition (and rate )?of (the )?(income )?tax",
      r"(?i)if [a-z ]{0,20}taxable income is:?[\s\S]{0,60}the tax is", r"(?i)no (state |personal |individual )*(income|net income) tax", r"(?i)(shall not|may not|never) (impose|levy|enact)[^.]{0,120}(income|net income)", r"(?i)prohibit[^.]{0,120}(personal|individual|net) income tax", r"(?i)does not( currently)? (have|impose|levy)[^.]{0,60}income tax", r"(?i)(interest and dividends tax|hall income tax|income tax)[^.]{0,120}(repealed|eliminated)", r"(?i)\[Repealed"],
     ("statute", "guidance"), "rates", None, True, {"any_class": True}),
    ("S02", "Internal Revenue Code conformity date (static or rolling) as defined in the chapter", "state conformity", "state statute",
     [r"(?i)internal revenue code[^.]{0,160}(as amended (and in effect )?(on|through|to)|in effect (on|for|as of)|as of (january|december)|means (title 26|the [^.]{0,40}code of 1986))", r"(?i)" + Q + r"internal revenue code" + Q + r" (means|shall mean)", r"(?i)internal revenue code[^.]{0,80}(january|december) \d{1,2}, (20\d\d)", r"(?i)(conform|update)[^.]{0,120}internal revenue code[^.]{0,120}(20\d\d|amendments)"],
     ("statute",) , None, None, False, {}),
    ("S03", "Resident, nonresident and part-year resident definitions (domicile, statutory residence day count)", "state", "state statute",
     [r"(?i)" + Q + r"?resident( individual)?" + Q + r"?[^.]{0,40}(means|includes|shall mean)", r"(?i)domicile[^.]{0,300}(183|one hundred eighty-three|more than (six|seven) months|permanent place of abode|two hundred)", r"(?i)part-year resident[^.]{0,60}(means|is|shall mean)", r"(?i)" + Q + r"nonresident" + Q + r"[^.]{0,40}(means|includes)"],
     ("statute",) , None, None, False, {}),
    ("S04", "Filing statuses and joint/separate return rules (married joint, separate, head of household, surviving spouse)", "state conformity", "state statute",
     [r"(?i)head of (a )?household", r"(?i)(married|husband and wife|spouses)[^.]{0,80}(joint|jointly|separate)", r"(?i)joint return", r"(?i)surviving spouse"],
     ("statute",), "rates", None, False, {}),
    ("S05", "Starting point: state gross/adjusted gross/taxable income defined from federal AGI, federal taxable income, or own gross income", "state conformity", "state statute",
     [r"(?i)federal adjusted gross income", r"(?i)federal taxable income", r"(?i)adjusted gross income[^.]{0,40}(means|shall mean|is defined|as defined)", r"(?i)taxable income[^.]{0,40}(means|shall mean|is defined)", r"(?i)gross income[^.]{0,40}(means|shall mean|includes)", r"(?i)classes of income"],
     ("statute",), "agi", None, False, {}),
    ("S06", "Rate schedule: bracket thresholds and marginal rates, or the flat rate (statute)", "state", "state statute",
     [r"(?i)(\d+(\.\d+)?|[a-z]+(-[a-z]+)?( and [a-z\-]+)?( hundredths)?( of one)?) ?(percent|per ?cent|%)[^.]{0,200}(taxable income|net income|income in excess|of the excess|over \$)", r"(?i)(taxable|net) income[^.]{0,200}(\d+(\.\d+)?) ?(percent|per ?cent|%)", r"(?i)rate of (tax )?(is|shall be)[^.]{0,80}(percent|per ?cent|%)", r"(?i)\$[\d,]+[^.]{0,60}(percent|per ?cent|%)[^.]{0,60}(excess|over)", r"(?i)\$[\d,]+-[\d,]*[\s\S]{0,160}\d+(\.\d+)?%", r"(?i)taxed at the rate of [\d.]+ ?(percent|per ?cent|%)"],
     ("statute",), "rates", None, False, {}),
    ("S07", "Bracket / deduction / exemption indexing rule (inflation adjustment method, base year, rounding)", "state", "state statute",
     [r"(?i)(bracket|rate schedule|standard deduction|personal exemption|exemption amount|dollar amounts?|threshold amounts?|income tax brackets)[^.]{0,250}(inflation|cost-of-living|consumer price index|CPI)", r"(?i)(inflation|cost-of-living|consumer price index|CPI)[^.]{0,250}(bracket|rate schedule|standard deduction|personal exemption|exemption amount|dollar amounts?|threshold amounts?)"],
     ("statute",), "rates", "indexed", False, {"reject": r"(?i)internal revenue code|section 63|section 68|151\(d\)|not adopted|commuter"}),
    ("S08", "Standard deduction amount(s) by filing status (statute)", "state", "state statute",
     [r"(?i)standard deduction[^.]{0,300}\$\s?[\d,]{3,}", r"(?i)\$\s?[\d,]{3,}[^.]{0,120}standard deduction", r"(?i)standard deduction[^.]{0,200}(percent|%)[^.]{0,80}(federal|adjusted gross)", r"(?i)standard deduction[^.]{0,200}(federal standard deduction|section 63 of the internal revenue code|allowed under section 63)"],
     ("statute",), "standard", "std", False, {}),
    ("S09", "Itemized deductions: state treatment (federal itemized with modifications, SALT/mortgage limits, own list, or none)", "state conformity", "state statute",
     [r"(?i)itemized deduction"],
     ("statute",), "itemized", "itemized", False, {}),
    ("S10", "Personal exemption amount or personal exemption credit (taxpayer and spouse)", "state", "state statute",
     [r"(?i)(personal )?exemption[^.]{0,200}\$\s?[\d,]{3,}[^.]{0,120}(taxpayer|individual|spouse|each)", r"(?i)\$\s?[\d,]{3,}[^.]{0,80}(personal exemption|exemption for the taxpayer)", r"(?i)personal exemption (amount|credit|allowance)", r"(?i)exemption[^.]{0,60}(credit|amount)[^.]{0,120}\$\s?[\d,]{2,}"],
     ("statute",), "exemptions", "pers_ex", False, {}),
    ("S11", "Dependent exemption or dependent credit amount", "state", "state statute",
     [r"(?i)(each|per|every) dependent[^.]{0,120}\$\s?[\d,]{2,}", r"(?i)\$\s?[\d,]{2,}[^.]{0,120}(each|per|every) dependent", r"(?i)dependent exemption[^.]{0,120}\$", r"(?i)dependent (tax )?credit", r"(?i)exemption[^.]{0,60}dependent"],
     ("statute",), "exemptions", "pers_ex", False, {}),
    ("S12", "Additional deduction/exemption/credit for age 65 or over and for blindness", "state", "state statute",
     [r"(?i)additional (personal )?(exemption|deduction|standard deduction|amount|credit)[^.]{0,200}(65|sixty-five|blind)", r"(?i)(65|sixty-five|blind)[^.]{0,200}additional (personal )?(exemption|deduction|standard deduction|amount|credit)", r"(?i)exemption[^.]{0,80}\$\s?[\d,]{2,}[^.]{0,200}(age (of )?65|sixty-five|blind)", r"(?i)(sixty-five|65) years of age or older[^.]{0,200}(exemption|deduction|credit)[^.]{0,120}\$"],
     ("statute",), "exemptions", None, False, {"reject": r"(?i)withholding|property tax|homestead|rent"}),
    ("S13", "Addition: interest on obligations of other states and their subdivisions", "state", "state statute",
     [r"(?i)(interest|income)[^.]{0,120}(obligations?|bonds?|securities)[^.]{0,80}(of|issued by)[^.]{0,40}(any|another|other|a) state", r"(?i)(obligations?|bonds?) of (any|another|other) state[^.]{0,160}(added|addition|includ|add)", r"(?i)(add|added|addition|include)[^.]{0,200}interest[^.]{0,160}(state|municipal|political subdivision)[^.]{0,80}(other than|except|not)", r"(?i)interest[^.]{0,100}(state|political subdivision|municipal)[^.]{0,100}(other than|except) (this state|the state|[A-Z][a-z]+)"],
     ("statute",), "additions", None, False, {}),
    ("S14", "Subtraction: interest on United States obligations", "state", "state statute",
     [r"(?i)(interest|income)[^.]{0,120}(obligations of the united states|federal (securities|obligations)|united states (government )?(securities|obligations|bonds)|u\.s\. (government )?(obligations|securities))", r"(?i)(exempt|subtract|deduct|exclud)[^.]{0,200}(obligations of the united states|federal (securities|obligations)|united states (government )?(securities|obligations|bonds))", r"(?i)(obligations of the united states|united states (government )?obligations)[^.]{0,160}(exempt|subtract|deduct|exclud|not (be )?(included|taxed))"],
     ("statute",), "subtractions", None, False, {}),
    ("S15", "Social Security benefits: full exclusion or the partial-taxation rule and its thresholds", "state", "state statute",
     [r"(?i)social security (benefits?|act)[^.]{0,300}(subtract|exempt|exclud|deduct|not (be )?(included|subject|taxed)|taxable|percent|reduc|includ)", r"(?i)(subtract|exempt|exclud|deduct)[^.]{0,200}social security", r"(?i)(title II|tier 1|section 86)[^.]{0,160}(social security|railroad)"],
     ("statute",), "retirement", None, False, {}),
    ("S16", "Pension and retirement income exclusion (amounts, age conditions, public vs private)", "state", "state statute",
     [r"(?i)(pension|retirement|annuity)[^.]{0,250}(subtract|exempt|exclud|deduct)[^.]{0,250}(\$\s?[\d,]{3,}|age|sixty|65|percent|first)", r"(?i)(subtract|exempt|exclud|deduct)[^.]{0,250}(pension|retirement (income|benefits|pay|plan|system))[^.]{0,160}(\$|age|percent|first|all)", r"(?i)retirement income[^.]{0,80}(exclusion|deduction|subtraction|credit|exempt)", r"(?i)(pension|retirement) (income|benefits?)[^.]{0,120}(exclusion|deduction|subtraction|credit|exempt)"],
     ("statute",), "retirement", None, False, {}),
    ("S17", "Military pay and military retirement subtraction", "state", "state statute",
     [r"(?i)(military|armed forces|uniformed services)[^.]{0,250}(retire|pay|compensation|service)[^.]{0,250}(subtract|exempt|exclud|deduct|not (be )?(included|taxed))", r"(?i)(subtract|exempt|exclud|deduct)[^.]{0,250}(military|armed forces|uniformed services|national guard)[^.]{0,160}(retire|pay|compensation|service|income)"],
     ("statute",), "military", None, False, {}),
    ("S18", "Capital gains: exclusion, deduction, or separate rate (where the state departs from ordinary treatment)", "state", "state statute",
     [r"(?i)(net )?(long-term )?capital gains?[^.]{0,160}(exclu|deduct|subtract|exempt|taxed at|rate of|percent|%)", r"(?i)(exclu|deduct|subtract)[^.]{0,120}(net )?capital gain"],
     ("statute",), "capital_gains", "cap_gains", True, {"reject": r"(?i)property tax|household income|homestead|stock options|high technology"}),
    ("S19", "State EITC: percentage of the federal credit or own schedule, and refundability", "state", "state statute",
     [r"(?i)earned income (tax )?credit[\s\S]{0,400}(percent|per ?cent|%)", r"(?i)(percent|per ?cent|%)[\s\S]{0,200}earned income (tax )?credit", r"(?i)(working families?|working family) (tax )?credit", r"(?i)earned income (tax )?credit[\s\S]{0,400}(refund|section 32)", r"(?i)section 32 of the (federal )?internal revenue code[\s\S]{0,300}(per ?cent|percent|%)"],
     ("statute", "guidance"), "eitc", "eitc", True, {"reject": r"(?i)shall not take into account|federal income tax deduction|notify an employee|information statement", "head_reject": r"(?i)order for claiming|order in which|general provisions|information statement"}),
    ("S20", "State EITC deviations from federal eligibility (ITIN filers, age 18-24, childless amount, non-custodial), read from the EITC section", "state", "state statute",
     [r"(?i)earned income[^.]{0,400}(individual taxpayer identification|ITIN|eighteen|18 years|age (of )?(18|19|21|24)|regardless of (age|immigration)|noncustodial|non-custodial)", r"(?i)(individual taxpayer identification number|ITIN)[^.]{0,300}earned income"],
     ("statute",), "eitc", "eitc", True, {"derive_from": "S19"}),
    ("S21", "State child tax credit / dependent credit / young child credit amount", "state", "state statute",
     [r"(?i)(child|young child|dependent|kids|child and family|empire state child|family) (income )?(tax )?credit[^.]{0,300}\$\s?[\d,]{2,}", r"(?i)\$\s?[\d,]{2,}[^.]{0,200}(child|dependent) (tax )?credit", r"(?i)(child|dependent) (tax )?credit[^.]{0,200}(percent|%)", r"(?i)child deduction[^.]{0,300}\$"],
     ("statute",), "ctc", "ctc", False, {"reject": r"(?i)dependent care|child care|day care"}),
    ("S22", "State child credit phase-out / income limit and refundability", "state", "state statute",
     [r"(?i)(child|young child|dependent|kids|child and family|empire state child|family) (income )?(tax )?credit[^.]{0,600}(phase|reduc|exceed|income limit|refund)", r"(?i)child deduction[^.]{0,400}(adjusted gross income|exceed)"],
     ("statute",), "ctc", "ctc", False, {"reject": r"(?i)dependent care|child care|day care"}),
    ("S23", "Child and dependent care credit: percentage of the federal credit or own schedule", "state", "state statute",
     [r"(?i)(dependent care|child care|household and dependent care)[^.]{0,300}(percent|%|\$)", r"(?i)(percent|%)[^.]{0,200}(dependent care|child care) (expenses|credit)"],
     ("statute",), "cdcc", "cdcc", False, {"reject": r"(?i)employer|facility|provider license"}),
    ("S24", "Credit for income taxes paid to other states (resident credit, limitation)", "state", "state statute",
     [r"(?i)tax(es)? (paid|imposed)[^.]{0,60}(another|other|any other) (state|jurisdiction)", r"(?i)credit for (income )?tax(es)? paid to", r"(?i)income tax imposed by (another|other) state", r"(?i)credit[^.]{0,120}(another|other) state[^.]{0,120}(income tax|tax on income)"],
     ("statute",) , None, None, False, {}),
    ("S25", "Low-income credit, no-tax floor, or low-income exclusion (poverty-level relief)", "state", "state statute",
     [r"(?i)low[- ]income (tax )?(credit|exclusion|exemption|comprehensive tax rebate|family tax credit|tax table|taxpayers?)", r"(?i)no tax (shall be|is) (due|imposed|payable)[^.]{0,200}(\$|dollars)", r"(?i)(no tax on (a )?taxable income|tax shall not be imposed on[\s\S]{0,120}(net income|adjusted gross income))[\s\S]{0,160}(dollars|\$)", r"(?i)(family income tax credit|family size tax credit|refundable food/excise tax credit|food/excise tax credit|sales tax relief credit|sales tax fairness credit|poverty level credit)", r"(?i)(special tax provisions for )?poverty[^.]{0,200}(credit|forgiveness|income|exempt)", r"(?i)tax forgiveness", r"(?i)credit[^.]{0,60}for low-income (taxpayers|individuals|families)"],
     ("statute",), "credits", "low_income", False, {"reject": r"(?i)housing|community|building|freeze|new markets|sustainable|business enterprise|less developed|enterprise zone|dependent care|lifted out|estimate of the number"}),
    ("S26", "Property tax circuit breaker, renter or homestead credit claimed on the income tax return", "state", "state statute",
     [r"(?i)(property tax(es)?|real estate tax|rent constituting|renter|homestead|circuit breaker)[^.]{0,100}(credit|refund|rebate|relief)[^.]{0,400}(household income|gross income|income does not exceed|exceeds \d+ per ?cent|\$[\d,]{3,})", r"(?i)credit[^.]{0,120}(property taxes? (paid|accrued)|rent constituting)"],
     ("statute",), "circuit", "circuit_breaker", False, {"reject": r"(?i)housing|solar|research|lien|apprentice|farmer|S corporation|jobs credit|manufactured dwelling|tornado|energy|allocation categor|revenue|measures affecting|armed forces and providing|agricultural"}),
    ("S27", "Other personal credits enumerated in the credits article (education, adoption, charitable, long-term care, elderly, volunteer, etc.)", "state", "state statute",
     [r"(?i)credit[^.]{0,100}(adoption|tuition|education|long-term care|elderly|senior|volunteer|charitable|scholarship|contribution|caregiver|529|college|teacher|classroom|food|grocery)"],
     ("statute",), "credits", None, False, {"reject": r"(?i)corporation|partnership interests|school repair", "head_reject": r"(?i)school repair|research|enterprise|jobs|manufactur|facility|investments in housing|family education accounts", "require_head": r"(?i)adoption|tuition|education|long-term care|elderly|senior|volunteer|charitable|scholarship|caregiver|529|college|teacher|classroom|food|grocery|sales tax (relief|fairness)|^credits?\.?$|credits against( the)? tax|income tax credits|^credits\b|^credit\b"}),
    ("S28", "State alternative minimum tax (rate, exemption, AMTI base) where enacted", "state", "state statute",
     [r"(?i)alternative minimum tax(able income)?[^.]{0,300}(percent|%|\$|exemption)"],
     ("statute",), "amt", "amt", False, {}),
    ("S29", "Surtax or special individual tax (millionaire surtax, mental health tax, capital gains excise, interest and dividends tax, high-earner tax) where enacted, incl. the year's threshold", "state", "state statute or bulletin",
     [r"(?i)(surtax|surcharge|mental health services tax|capital gains (excise )?tax|interest and dividends tax|tax on interest|additional tax)[\s\S]{0,300}(percent|%)", r"(?i)(percent|%)[^.]{0,120}(surtax|surcharge)", r"(?i)(taxable income|adjusted gross income)[^.]{0,80}(exceeds|in excess of|over)[^.]{0,40}\$\s?1,000,000", r"(?i)(interest and dividends tax|hall income tax)[^.]{0,200}(repeal|eliminat|zero)", r"(?i)long-term capital (assets|gains)[\s\S]{0,300}(percent|%)"],
     ("statute", "guidance"), "surtax", "surtax", True, {"any_class": True}),
    ("S30", "Nonresident and part-year resident sourcing and apportionment (income from sources within the state, proration)", "state", "state statute",
     [r"(?i)nonresident[^.]{0,300}(sources within|derived from|attributable to|apportion|allocat|prorat)", r"(?i)part-year resident[^.]{0,300}(prorat|apportion|allocat|portion)"],
     ("statute",) , None, None, False, {}),
    ("S31", "Employer withholding requirement and withholding tables/formula", "state", "state statute",
     [r"(?i)employer[^.]{0,120}(shall|must|required to) (deduct and )?withhold", r"(?i)withholding (tables?|formula|schedules?)", r"(?i)withhold[^.]{0,120}wages[^.]{0,200}(rate|percent|table)"],
     ("statute", "form") , None, None, False, {}),
    ("S32", "Individual estimated tax requirement, safe harbor and underpayment interest", "state", "state statute",
     [r"(?i)estimated (income )?tax[^.]{0,400}(90|100|110) ?(percent|%)", r"(?i)(declaration|payment)s? of estimated (income )?tax", r"(?i)estimated tax[^.]{0,300}(underpayment|penalty|interest)"],
     ("statute", "form") , None, None, False, {}),
    ("S33", "Filing threshold: who must file a return (income floor, exemption-based, gross income test)", "state", "state statute",
     [r"(?i)(return (shall|must) be (filed|made)|required to (file|make) a return|shall (file|make) a return)[^.]{0,400}(gross income|exceed|in excess of|\$)", r"(?i)(every|each) (resident )?individual[^.]{0,200}(gross income|net income)[^.]{0,100}(exceed|in excess of|greater than|more than)[^.]{0,80}\$", r"(?i)filing (threshold|requirement)", r"(?i)who must file[\s\S]{0,800}\$", r"(?i)(must|required to) file[^.]{0,200}(gross income|income)[^.]{0,100}(more than|exceeds|over|at least)[^.]{0,40}\$"],
     ("statute", "form"), "filing", None, False, {}),
    ("S34", "Return due date, extensions, joint return liability and innocent spouse", "state", "state statute",
     [r"(?i)(fifteenth day of the fourth month|april 15|15th day of the fourth month)", r"(?i)extension of time (to|for) (file|filing)", r"(?i)innocent spouse|jointly and severally liable"],
     ("statute", "form") , None, None, False, {}),
    ("S35", "Local income taxes (county, municipal, school district, city) authorized or imposed by the state code, where they exist", "state", "state statute",
     [r"(?i)(?<!state and )(county|municipal|city|school district)[^.]{0,20}(income|earnings|occupational (license|privilege)|wage|payroll) tax[^.]{0,300}(percent|%|rate)", r"(?i)(city of new york|yonkers)[^.]{0,200}(income tax|surcharge)", r"(?i)local income tax (rate|council|act|under this article)", r"(?i)school district (income )?surtax", r"(?i)city personal income tax"],
     ("statute",), "local", "local", False, {"reject": r"(?i)state and local income tax"}),
    ("R01", "State income tax regulations: the revenue department's administrative code chapter on the individual income tax", "state", "state regulation",
     [r"(?i)(individual |personal )?income tax[^.]{0,200}(adjusted gross income|taxable income|resident|return|deduction|credit|withholding)"],
     ("regulation",) , "carrier", None, False, {}),
    ("F01", "Tax year 2025 resident individual income tax return form", "state", "state form instructions and rate schedules",
     [r"(?i)(your first name|first name and (middle )?initial|spouse.s first name|filing status)[\s\S]{0,3000}(social security number|SSN)"],
     ("form",) , "carrier", None, True, {"form_head": r"(?i)(return|^form|packet|booklet)", "form_head_reject": r"(?i)^(instructions|.*instructions$)|estimated|worksheet|tax table|rate schedule|standard deduction chart|brackets|look up"}),
    ("F02", "Tax year 2025 resident return instruction booklet (line-by-line rules, worksheets)", "state", "state form instructions and rate schedules",
     [r"(?i)(line \d+|instructions)[\s\S]{0,4000}(line \d+)[\s\S]{0,4000}(line \d+)"],
     ("form",) , "carrier", None, True, {"form_head": r"(?i)instruction|booklet|packet|guide", "form_head_reject": r"(?i)estimated|-es\b|1-es|140es|540-es|1040n-es|740-es|or-estimate|k-40es"}),
    ("F03", "Tax year 2025 rate schedule, tax table or flat rate with the year's dollar thresholds (as printed)", "state", "state form instructions and rate schedules",
     [r"(?i)(tax rate schedules?|rate schedules?|tax tables?|tax rate tables?|rate tables?|look ?up table|tax computation)[\s\S]{0,1500}(\$\s?[\d,]{3,}|\d{2},\d{3})[\s\S]{0,300}(%|percent)", r"(?i)(\d+(\.\d+)?)\s?%[^\n]{0,80}(of (the )?(amount|excess)|over \$)[^\n]{0,60}\$?\s?[\d,]{3,}", r"(?i)(if (line|taxable income)[^\n]{0,60}is)[\s\S]{0,300}(at least|but less than|over)[\s\S]{0,300}\d{1,3},\d{3}", r"(?i)(income )?tax rate (is|of) \d+(\.\d+)?\s?(%|percent)", r"(?i)multiply[^\n]{0,80}by \d+(\.\d+)?\s?(%|percent)", r"(?i)(\d+(\.\d+)?)\s?% of (Idaho|Colorado|Utah|Indiana|Michigan|Illinois|Iowa|Kentucky|Mississippi|Georgia|Arizona|North Carolina|Pennsylvania|Louisiana) taxable income"],
     ("form",), "rates", None, False, {"year": "2025", "reject": r"(?i)capital gain|penalt|withdrawal"}),
    ("F04", "Tax year 2025 standard deduction and exemption dollar amounts as printed in the instructions", "state", "state form instructions and rate schedules",
     [r"(?i)standard deduction[^\n]{0,300}\$\s?[\d,]{3,}", r"(?i)\$\s?[\d,]{3,}[^\n]{0,150}standard deduction", r"(?i)(personal|dependent) exemption[^\n]{0,200}\$\s?[\d,]{2,}", r"(?i)exemption (amount|credit|allowance)[^\n]{0,120}\$\s?[\d,]{2,}"],
     ("form",), "standard", "std_or_ex", False, {"year": "2025"}),
    ("F05", "Tax year 2025 state EITC / child credit parameters as printed in the instructions (percentage of federal, amounts, worksheets)", "state", "state form instructions and rate schedules",
     [r"(?i)earned income (tax )?credit[\s\S]{0,600}(\d{1,3}\s?%|percent|\$\s?[\d,]{2,})", r"(?i)(child|young child|dependent|family|kids) (tax )?credit[\s\S]{0,400}(\$\s?[\d,]{2,}|\d{1,3}\s?%)", r"(?i)(working families?|working family) (tax )?credit"],
     ("form",), "eitc", "eitc_or_ctc", True, {"year": "2025"}),
    ("F06", "Tax year 2026 indexed amounts (rate schedule, standard deduction, exemptions) as published for the year (estimated-tax instructions or department bulletin)", "state", "state department bulletins",
     [r"(?i)(rate schedule|tax rate|bracket|standard deduction|exemption|inflation|indexed|tax table|rate of|rate is|surtax threshold)[\s\S]{0,600}(\$\s?[\d,]{3,}|\d+(\.\d+)?\s?%)", r"(?i)(\$\s?[\d,]{3,}|\d+(\.\d+)?\s?%)[\s\S]{0,300}(rate schedule|tax rate|bracket|standard deduction|exemption|inflation|indexed|tax table)"],
     ("form", "guidance"), "rates", None, False, {"year": "2026"}),
]

PE_KEY_DIRS = {
    "rates": ["income/rates", "income/main", "income/rate", "main", "rates"],
    "income": ["income"],
    "agi": ["income/agi", "income/base", "income/taxable_income", "income/gross_income", "income/main", "agi"],
    "additions": ["income/additions", "income/add_back", "income/adjustments", "additions"],
    "subtractions": ["income/subtractions", "income/exclusions", "income/exempt_income", "income/agi/subtractions", "subtractions", "income/deductions"],
    "military": ["income/subtractions/military", "subtractions/military", "income/subtractions/military_retirement", "subtractions/military_retirement", "income/exclusions/military"],
    "standard": ["income/deductions/standard", "deductions/standard", "income/deductions", "deductions"],
    "itemized": ["income/deductions/itemized", "deductions/itemized", "income/deductions", "deductions"],
    "exemptions": ["income/exemptions", "income/exemption", "exemptions", "income/credits/personal", "credits/personal", "income/credits/exemption", "credits/exemption", "credits/personal_exemption", "income/credits/personal_exemption"],
    "eitc": ["income/credits/eitc", "credits/eitc", "credits/earned_income", "income/credits/earned_income", "credits/wftc", "income/credits/wftc", "credits/working_families", "credits/cal_eitc", "income/credits/refundable/eitc", "credits/refundable/eitc", "wftc"],
    "ctc": ["income/credits/ctc", "credits/ctc", "credits/child", "income/credits/child", "credits/young_child", "credits/dependent", "credits/family_tax_credits", "credits/dependent_credit", "credits/child_and_dependent", "income/credits/child_and_dependent", "credits/empire_state_child", "credits/kids", "credits/child_tax_credit", "income/credits/child_tax_credit", "credits/dependent_exemption_tax_credit", "deductions/child_deduction", "income/deductions/child_deduction", "credits/dependent_care", "income/credits/family"],
    "cdcc": ["income/credits/cdcc", "credits/cdcc", "credits/child_dependent_care", "credits/dependent_care", "credits/child_care", "credits/child_and_dependent_care", "credits/household_dependent_care", "credits/cdc", "income/credits/dependent_care", "credits/child_and_dependent_care_expense", "credits/refundable/cdcc"],
    "credits": ["income/credits", "credits"],
    "circuit": ["credits/property_tax", "income/credits/property_tax", "credits/homestead", "credits/renter", "credits/rent", "income/credits/renter", "credits/circuit_breaker", "credits/refundable/property_tax", "credits/real_property_tax", "credits/homeowners", "credits/property_tax_credit", "credits/real_estate_tax", "credits/homestead_property_tax", "credits/homestead_credit", "credits/renters", "credits/property_tax_refund"],
    "amt": ["income/amt", "amt", "income/alternative_minimum_tax", "alternative_minimum_tax", "income/alternate_tax", "alternate_tax", "income/alternative_tax", "alternative_tax"],
    "capital_gains": ["income/capital_gains", "capital_gains", "gross_income/capital_gains", "subtractions/capital_gains", "deductions/capital_gains", "income/subtractions/capital_gains", "income/deductions/capital_gains", "income/gross_income/capital_gains"],
    "retirement": ["subtractions/social_security", "income/subtractions/social_security", "social_security", "income/social_security", "subtractions/pension", "income/subtractions/pension", "pension_exclusion", "income/pension_exclusion", "exemptions/retirement", "income/exemptions/retirement", "subtractions/retirement", "income/subtractions/retirement", "exclusions", "deductions/pension", "subtractions/military_retirement", "subtractions/taxable_social_security", "income/subtractions/taxable_social_security", "credits/retirement", "income/credits/retirement", "credits/ss_benefits", "subtractions/ss", "deductions/social_security", "credits/social_security", "subtractions/retirement_income", "retirement", "income/retirement"],
    "payroll": ["payroll", "income/withholding", "withholding"],
    "filing": ["income/filing_threshold", "income/filing_requirement", "filing_threshold", "filing_requirement"],
    "local": None,
    "surtax": ["income/surcharge", "surcharge", "income/high_earner_tax", "high_earner_tax", "income/millionaires_tax", "income/capital_gains", "capital_gains", "income/rates/surtax", "income/supplemental", "supplemental_tax", "income/niit", "income/additional_tax", "rates/surtax", "income/mental_health"],
}

HEAD = {
    "S01": r"imposition|imposed|tax on (individuals|residents|income|net income)|levy|levied|^tax imposed|rate", "S02": r"definition|conformity|internal revenue code|update",
    "S03": r"definition|resident", "S04": r"joint|filing status|head of household|married|spouse|husband", "S05": r"adjusted gross income|taxable income|definition|gross income|computation",
    "S06": r"rate|tax on individuals|imposition|bracket|schedule|imposed", "S07": r"inflation|index|adjust|rate", "S08": r"standard deduction|deduction", "S09": r"itemized|deduction",
    "S10": r"exemption|personal|credit", "S11": r"exemption|dependent|credit", "S12": r"exemption|aged|blind|elderly|deduction", "S13": r"addition|modification|adjustment|computation",
    "S14": r"subtraction|modification|exempt|exclu|adjustment|computation", "S15": r"social security|retirement|subtraction|modification|exclu|exempt", "S16": r"retirement|pension|annuit|subtraction|exclu|exempt",
    "S17": r"military|armed forces|subtraction|exclu|exempt|retirement", "S18": r"capital gain", "S19": r"earned income|working famil|credit", "S20": r"earned income|working famil",
    "S21": r"child|dependent|family|kids|credit", "S22": r"child|dependent|family|kids|credit", "S23": r"dependent care|child care|household|care", "S24": r"other state|another state|taxes paid|other jurisdiction|credit",
    "S25": r"low.income|poverty|forgiveness|no tax|credit|exclusion", "S26": r"property tax|renter|homestead|circuit|credit", "S27": r"credit", "S28": r"minimum tax",
    "S29": r"surtax|surcharge|capital gains|interest and dividends|supplemental|net investment|additional tax|mental health|rate", "S30": r"nonresident|part-year|source|allocat|apportion",
    "F01": r"return|form", "F02": r"instruction|booklet|packet", "F03": r"tax table|rate schedule|bracket|rate table|look up|instructions|booklet|packet", "F04": r"instruction|booklet|packet|standard deduction", "F05": r"instruction|booklet|packet", "F06": r"2026",
    "S31": r"withhold", "S32": r"estimated|declaration", "S33": r"return|filing|who must", "S34": r"return|due|filing|extension|joint|spouse", "S35": r"county|municipal|city|school district|local|occupational|earnings|yonkers|new york",
}
KIND_RANK = {"section": 0, "act": 0, "subsection": 0, "rule": 0, "document": 1, "block": 2, "page": 3}


def load_rows(corpus, j, dc, v):
    p = os.path.join(corpus, "provisions", j, dc, f"{v}.jsonl")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return [json.loads(line) for line in f]


def snippet(body, m, width=90):
    s = max(0, m.start() - width)
    e = min(len(body), m.end() + width)
    return re.sub(r"\s+", " ", body[s:e]).strip()


def best_hit(rows, patterns, head_pat=None, min_body=40, reject=None, require_head=None, head_reject=None):
    """Return (row, snippet, score) for the best body match, or None."""
    best = None
    rej = re.compile(reject) if reject else None
    reqh = re.compile(require_head) if require_head else None
    for r in rows:
        b = r.get("body") or ""
        if len(b) < min_body:
            continue
        h = (r.get("heading") or "") + " " + (r.get("citation_label") or "") + " " + b[:150]
        if reqh and not reqh.search(h.strip()):
            continue
        if head_reject and re.search(head_reject, h):
            continue
        for i, pat in enumerate(patterns):
            found = None
            for m in re.finditer(pat, b):
                sn = snippet(b, m)
                if rej and rej.search(snippet(b, m, 400)):
                    continue
                found = (m, sn)
                break
            if not found:
                continue
            m, sn = found
            score = KIND_RANK.get(r.get("kind"), 4) * 10 + i
            if head_pat and re.search(head_pat, h, re.I):
                score -= 30
            if len(b) > 200_000:
                score += 8  # whole-chapter dumps are weak evidence
            if best is None or score < best[2]:
                best = (r, sn, score)
            break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--selector", required=True)
    ap.add_argument("--queue", required=True)
    ap.add_argument("--pe", required=True)
    ap.add_argument("--rulespec", required=True)
    ap.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()
    t0 = time.time()

    sel = json.load(open(a.selector))
    queue = {r["jurisdiction"]: r for r in yaml.safe_load(open(a.queue))["states"]}

    # --- load selected US scopes (statute/regulation/form/guidance) ---
    scopes = defaultdict(list)  # jurisdiction -> [(dc, v, rows)]
    nrows = 0
    for sc in sel["scopes"]:
        j = sc["jurisdiction"]
        if not (j == "us" or j.startswith("us-")):
            continue
        if sc["document_class"] not in ("statute", "regulation", "form", "guidance"):
            continue
        rows = load_rows(a.corpus, j, sc["document_class"], sc["version"])
        if rows is None:
            print("MISSING", j, sc, file=sys.stderr)
            continue
        for r in rows:
            r["_v"] = sc["version"]
            r["_dc"] = sc["document_class"]
        scopes[j].append((sc["document_class"], sc["version"], rows))
        nrows += len(rows)
    print(f"loaded {nrows} rows from {sum(len(v) for v in scopes.values())} scopes in {time.time()-t0:.0f}s", file=sys.stderr)

    # --- PolicyEngine and rulespec trees ---
    pe_dirs = set()  # directories holding yaml plus the yaml files themselves (sans extension), e.g. irs/income/bracket
    for root, dirs, files in os.walk(a.pe):
        rel = os.path.relpath(root, a.pe)
        ys = [f for f in files if f.endswith(".yaml")]
        if ys:
            pe_dirs.add(rel)
            for f in ys:
                pe_dirs.add(os.path.join(rel, f[:-5]))
    pe_state = defaultdict(set)
    for d in pe_dirs:
        m = re.match(r"states/([a-z]{2})/tax/(.*)", d)
        if m:
            pe_state[m.group(1)].add(m.group(2))
    pe_local = {re.match(r"local/([a-z]{2})/", d).group(1) for d in pe_dirs if re.match(r"local/([a-z]{2})/[^/]+/tax", d)}

    def pe_fed(dirs):
        if not dirs:
            return "no"
        hits = [d for d in dirs if any(x == d or x.startswith(d + "/") for x in pe_dirs)]
        return "yes (%s)" % ", ".join(hits) if hits else "no"

    def pe_st(st, key):
        if key is None:
            return "no"
        if key == "carrier":
            return "n/a (document carrier; see the rule elements it carries)"
        if key == "local":
            return "yes (gov/local/%s)" % st if st in pe_local else "no"
        cands = PE_KEY_DIRS.get(key) or []
        have = pe_state.get(st, set())
        hits = sorted({c for c in cands for x in have if x == c or x.startswith(c + "/") or x.endswith("/" + c)})
        return "yes (%s)" % ", ".join(hits[:3]) if hits else "no"

    rs26 = set()
    d26 = os.path.join(a.rulespec, "us", "statutes", "26")
    for n in os.listdir(d26):
        rs26.add(n.replace(".yaml", "").replace(".test", ""))
    rs_state = defaultdict(list)
    for st in STATES:
        d = os.path.join(a.rulespec, f"us-{st}")
        for root, dirs, files in os.walk(d):
            for f in files:
                if f.endswith(".yaml") and not f.endswith(".test.yaml"):
                    rel = os.path.relpath(os.path.join(root, f), d)
                    if "/income_tax/" in rel or "/statutes/" in rel or "/tax/" in rel:
                        rs_state[st].append(rel)
    rs_income_pipeline = {st: [p for p in rs_state[st] if "income_tax" in p or ("statutes" in p and "tax" in p.lower())] for st in STATES}

    matrix = []
    schema_elements = []

    def add(jur, eid, label, level, family, status, sv, cp, note, pe, rs):
        matrix.append({"jurisdiction": jur, "element": eid, "level": level, "family": family, "status": status,
                       "scope_version": sv, "citation_path": cp, "pe_modeled": pe, "evidence_note": note,
                       "_label": label, "_rs": rs})

    # ------------------------------------------------------------------
    # Federal
    # ------------------------------------------------------------------
    us_rows = scopes["us"]
    sec_index = {}
    for dc, v, rows in us_rows:
        if dc != "statute":
            continue
        for r in rows:
            m = re.match(r"^us/statute/26/([0-9A-Za-z]+)$", r["citation_path"])
            if m and r.get("kind") == "section" and (r.get("body") or ""):
                if m.group(1) not in sec_index or len(r["body"]) > len(sec_index[m.group(1)]["body"]):
                    sec_index[m.group(1)] = r

    form_products = {r["citation_path"].split("/")[4] for dc, v, rows in us_rows if dc == "form" for r in rows if r["citation_path"].startswith("us/form/irs/ty2025/") and (r.get("body") or "")}

    def fed_guidance_hit(scope_sub, pat):
        for dc, v, rows in us_rows:
            key = f"us/{dc}/{v}"
            for r in rows:
                if scope_sub not in key and not r["citation_path"].startswith(scope_sub):
                    continue
                b = r.get("body") or ""
                m = re.search(pat, b)
                if m:
                    return r, snippet(b, m)
        return None

    for eid, label, secs, fam, fact_re, annual, pedirs, note0 in FED:
        pe = pe_fed(pedirs)
        if fam in ("IRS forms and instructions", "IRS regulation") and not pedirs:
            pe = "n/a (document carrier; see the rule elements it carries)"
        rs = "yes" if any(s in rs26 for s in secs) else "no"
        if eid in ("F006", "F017", "F030", "F041", "F048", "F049", "F080", "F134"):
            rs = "yes (rev-proc-2025-32 policy)"
        if eid in ("F020", "F085", "F135"):
            rs = "yes (notice-2025-67 policy)"
        if eid == "F033":
            rs = "yes (rev-proc-2025-25 policy)"
        schema_elements.append({"id": eid, "label": label, "level": "federal", "family": fam, "sections": secs, "pe_modeled": pe, "rulespec_encoded": rs, "applies_to": "federal (inherited by all 51 jurisdictions)", "note": note0})
        if fam == "federal statute":
            have = [s for s in secs if s in sec_index]
            miss = [s for s in secs if s not in sec_index]
            if have:
                r = sec_index[have[0]]
                if fact_re:
                    mm = None
                    for s_ in have:
                        mm = re.search(fact_re, sec_index[s_]["body"])
                        if mm:
                            r = sec_index[s_]
                            break
                    if mm:
                        add("us", eid, label, "federal", fam, "PRESENT", r["_v"], r["citation_path"], f"section body ({len(r['body'])} chars, heading '{r['heading'][:50]}', expression_date {r.get('expression_date')}) carries the fact: '{snippet(r['body'], mm, 60)}'" + (f"; sections {miss} not in any selected scope" if miss else "") + "; inherited by all states", pe, rs)
                    else:
                        add("us", eid, label, "federal", fam, "REVIEW", r["_v"], r["citation_path"], f"section body present ({len(r['body'])} chars) but the fact regex /{fact_re}/ did not match; the subsection may be paraphrased or the text may be stale", pe, rs)
                else:
                    add("us", eid, label, "federal", fam, "PRESENT", r["_v"], r["citation_path"], f"section body present ({len(r['body'])} chars, heading '{r['heading'][:50]}', expression_date {r.get('expression_date')})" + (f"; sections {miss} not in any selected scope" if miss else "") + "; inherited by all states", pe, rs)
            else:
                add("us", eid, label, "federal", fam, "EXTRACTABLE", "", "", f"26 U.S.C. {', '.join(secs)} not in any selected us/statute scope; carrying family: {USLM}", pe, rs)
        elif fam == "IRS regulation":
            if annual:
                h = fed_guidance_hit(*annual[0][:2])
                if h:
                    add("us", eid, label, "federal", fam, "PRESENT", h[0]["_v"], h[0]["citation_path"], f"regulation body present: '{h[1][:140]}'; the other sections of the family are not selected ({ECFR})", pe, rs)
                    continue
            add("us", eid, label, "federal", fam, "EXTRACTABLE", "", "", ECFR, pe, rs)
        else:
            hit = None
            notes = []
            prod = FORM_PRODUCTS.get(eid)
            if prod:
                have_p = [p for p in prod if p in form_products]
                miss_p = [p for p in prod if p not in form_products]
                if have_p:
                    pr = next(r for dc, v, rows in us_rows if dc == "form" for r in rows if r["citation_path"] == f"us/form/irs/ty2025/{have_p[0]}")
                    add("us", eid, label, "federal", fam, "PRESENT", pr["_v"], pr["citation_path"], f"product(s) {have_p} present with body text under us/form/irs/ty2025/" + (f"; {miss_p} not taken ({IRSFORMS})" if miss_p else ""), pe, rs)
                else:
                    add("us", eid, label, "federal", fam, "EXTRACTABLE", "", "", f"product(s) {prod} not in the selected us/form scope; {IRSFORMS}", pe, rs)
                continue
            for scope_sub, pat, lab in (annual or []):
                h = fed_guidance_hit(scope_sub, pat)
                if h:
                    notes.append(f"{lab}: '{h[1][:140]}' at {h[0]['citation_path']} ({h[0]['_v']})")
                    hit = hit or h
                else:
                    notes.append(f"{lab}: no match in scopes matching '{scope_sub}'")
            if hit and all("no match" not in n for n in notes):
                add("us", eid, label, "federal", fam, "PRESENT", hit[0]["_v"], hit[0]["citation_path"], "; ".join(notes), pe, rs)
            elif hit:
                add("us", eid, label, "federal", fam, "PRESENT", hit[0]["_v"], hit[0]["citation_path"], "partial: " + "; ".join(notes), pe, rs)
            else:
                if eid == "F137":
                    add("us", eid, label, "federal", fam, "ABSENT", "", "", "not yet published: the batch-1 run note scanned IRB 2026-01..2026-37 and found no TY2027 revenue procedure (normally issued in October/November)", pe, rs)
                elif eid == "F133":
                    add("us", eid, label, "federal", fam, "EXTRACTABLE", "", "", "Rev. Proc. 2024-40 (IRB 2024-45) not in any selected scope; " + IRB + "; the TY2025 amounts it set that OBBBA did not amend (e.g. EITC, AMT, 199A, kiddie tax) are otherwise only readable from the 2025 form instructions", pe, rs)
                elif eid == "F088":
                    add("us", eid, label, "federal", fam, "EXTRACTABLE", "", "", "Rev. Proc. 2025-19 (IRB 2025-23) not taken; the batch-1 run note scanned only 2026 IRB issues; " + IRB, pe, rs)
                elif eid == "F108":
                    add("us", eid, label, "federal", fam, "EXTRACTABLE", "", "", "Publication 15-T not in any selected scope; irs.gov/forms-pubs/about-publication-15-t posts it", pe, rs)
                elif fam == "IRS forms and instructions":
                    add("us", eid, label, "federal", fam, "EXTRACTABLE", "", "", "; ".join(notes) + "; " + IRSFORMS, pe, rs)
                else:
                    add("us", eid, label, "federal", fam, "REVIEW", "", "", "; ".join(notes), pe, rs)

    # ------------------------------------------------------------------
    # States
    # ------------------------------------------------------------------
    for eid, label, level, family, patterns, classes, pekey, kkey, applies_nt, opts in S:
        schema_elements.append({"id": eid, "label": label, "level": level, "family": family, "doc_classes": list(classes), "pe_key": pekey, "known_law_key": kkey, "options": {k: (v if isinstance(v, (bool, str)) else str(v)) for k, v in opts.items()}, "applies_to": "51 jurisdictions (50 states + DC)" + ("" if applies_nt else "; N/A in the nine no-broad-tax states")})

    selected_versions = {(sc["jurisdiction"], sc["document_class"], sc["version"]) for sc in sel["scopes"]}
    for st in STATES:
        j = f"us-{st}"
        q = queue.get(j, {})
        ts = q.get("target_scope") or {}
        idx = q.get("index_url") or ""
        fams = q.get("index_families") or []
        qnote = q.get("notes") or ""
        chap = re.compile(INCOME_TAX_CHAPTER.get(st, r"^$"))
        st_rows = defaultdict(list)
        stat_list = []
        for dc, v, rows in scopes.get(j, []):
            if dc == "statute":
                stat_list.append(v)
                st_rows["statute"].extend([r for r in rows if chap.match(r["citation_path"])])
            elif dc == "form":
                if re.search(r"tax|income|form-1-es|1040n|140es|540|it-511|it-540|740-es|or-estimate|n11|ny-tax", v):
                    st_rows["form"].extend(rows)
            elif dc == "guidance":
                if re.search(r"tax|income|surtax|rate|exemption|k40es|adv-2025|hb96|zero-liability|absence|hall", v):
                    st_rows["guidance"].extend(rows)
            elif dc == "regulation":
                if re.search(r"income-tax|revenue|tax-reg|-dor-|-ftb-|idor|personal-income", v):
                    st_rows["regulation"].extend(rows)
        no_tax = st in NO_BROAD_TAX
        stat_desc = ", ".join(stat_list) or "none"
        legis = "the state code publisher (legislature/revisor site; see queue candidate_sources)"
        # queue pointer on disk but not selected (TX, WY): the fix is a selector change, not a fetch
        unselected = None
        if ts.get("version") and (j, ts.get("document_class"), ts.get("version")) not in selected_versions:
            onfile = os.path.exists(os.path.join(a.corpus, "provisions", j, ts.get("document_class") or "", f"{ts.get('version')}.jsonl"))
            unselected = f"the queue row is 'done' pointing at {ts.get('document_class')}/{ts.get('version')}, which {'exists on disk' if onfile else 'is NOT on disk'} but is not in the 2026-09-11 union selector"
        s19_hit = None

        for eid, label, level, family, patterns, classes, pekey, kkey, applies_nt, opts in S:
            pe = pe_st(st, pekey)
            rs_hits = [p for p in rs_income_pipeline.get(st, []) if p.endswith(".yaml")]
            rs = "yes (%d income-tax files)" % len(rs_hits) if rs_hits else "no"
            # applicability (N/A rows)
            na = None
            if no_tax and not applies_nt:
                na = "N/A: no broad-based individual income tax; the rule does not exist in this jurisdiction"
            elif kkey == "eitc" and st not in K["eitc"] and st != "wa":
                na = "N/A: no state EITC in TY2025 law (analyst knowledge, verify)"
            elif kkey == "eitc_or_ctc" and st not in K["eitc"] and st not in K["ctc"]:
                na = "N/A: no state EITC or child credit in TY2025 law (analyst knowledge, verify)"
            elif kkey == "ctc" and st not in K["ctc"]:
                na = "N/A: no state child credit/child deduction in TY2025 law (analyst knowledge, verify)"
            elif kkey == "cdcc" and st not in K["cdcc"]:
                na = "N/A: no state child and dependent care credit in TY2025 law (analyst knowledge, verify)"
            elif kkey == "amt" and st not in K["amt"]:
                na = "N/A: no state AMT (analyst knowledge, verify)"
            elif kkey == "surtax" and st not in K["surtax"]:
                na = "N/A: no surtax or special individual income tax (analyst knowledge, verify)"
            elif kkey == "local" and st not in K["local"]:
                na = "N/A: no local income tax authorized by the state code (analyst knowledge, verify)"
            elif kkey == "std" and st in K["no_std_ded"]:
                na = "N/A: the state has no standard deduction of its own (federal taxable income start or exemption-only design) (analyst knowledge, verify)"
            elif kkey == "itemized" and st in K["no_itemized"]:
                na = "N/A: the state allows no itemized deductions (analyst knowledge, verify)"
            elif kkey == "pers_ex" and st in K["no_pers_exemption"]:
                na = "N/A: no separate personal/dependent exemption or exemption credit (federal taxable income start) (analyst knowledge, verify)"
            elif kkey == "cap_gains" and st not in K["cap_gains"]:
                na = "N/A: capital gains taxed as ordinary income with no state exclusion (analyst knowledge, verify)"
            elif kkey == "indexed" and st not in K["indexed"]:
                na = "N/A: brackets/deductions are not indexed by statute (analyst knowledge, verify)"
            elif kkey == "low_income" and st not in K["low_income"]:
                na = "N/A: no low-income credit/no-tax floor (analyst knowledge, verify)"
            elif kkey == "circuit_breaker" and st not in K["circuit_breaker"]:
                na = "N/A: no property-tax circuit breaker or renter credit on the income tax return (analyst knowledge, verify)"
            elif kkey == "std_or_ex" and st in K["no_std_ded"] and st in K["no_pers_exemption"]:
                na = "N/A: neither a standard deduction nor an exemption amount exists (federal taxable income start)"
            elif no_tax and eid in ("F01", "F02", "S20"):
                na = "N/A: no resident individual income tax return exists (no broad-based income tax)"
            if na:
                add(j, eid, label, level, family, "N/A", "", "", na, pe, rs)
                continue

            # derived element: S20 reads the same section as S19
            if opts.get("derive_from") == "S19":
                if s19_hit and s19_hit[0]["_dc"] == "statute":
                    r = s19_hit[0]
                    dev = None
                    for pat in patterns:
                        mm = re.search(pat, r["body"])
                        if mm:
                            dev = snippet(r["body"], mm, 80)
                            break
                    add(j, eid, label, level, family, "PRESENT", r["_v"], r["citation_path"], ("eligibility read from the EITC section; deviation text found: '%s'" % dev[:160]) if dev else "eligibility read from the EITC section; no deviation text (ITIN/age/childless) matched, so the state appears to follow federal eligibility (verify)", pe, rs)
                else:
                    add(j, eid, label, level, family, "EXTRACTABLE", "", "", f"the EITC section is not in any selected statute scope for this state (see S19); posted by {legis}", pe, rs)
                continue

            cand = []
            for dc in classes:
                cand.extend(st_rows.get(dc, []))
            year = opts.get("year")
            body_only_2026 = False
            if year == "2026":
                def lab26(r):
                    rem = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", r["_v"])
                    return "2026" in rem or "2026" in r["citation_path"] or "2026" in (r.get("heading") or "")
                lab = [r for r in cand if lab26(r)]
                if lab:
                    cand = sorted(lab, key=lambda r: (0 if "/2026/" in r["citation_path"] or "2026" in r["citation_path"] else 1, 0 if "2026" in (r.get("heading") or "") else 1))
                else:
                    body_only_2026 = True
                    p26 = re.compile(r"(?i)(tax(able)? years? (beginning (in|on or after January 1, ))?2026|2026 tax year|for tax year 2026|effective (for )?(tax year )?2026|in 2026)[\s\S]{0,400}(\$\s?[\d,]{3,}|\d+(\.\d+)?\s?%)")
                    cand = [r for r in cand if p26.search(r.get("body") or "")]
                    patterns = [p26.pattern]
            elif year == "2025":
                cand = [r for r in cand if "2026" not in r["citation_path"] + (r.get("heading") or "")]
            if opts.get("form_head"):
                fh = re.compile(opts["form_head"]); fr = re.compile(opts.get("form_head_reject", r"^$"))
                cand = [r for r in cand if fh.search(r.get("heading") or r.get("citation_label") or "") and not fr.search(r.get("heading") or r.get("citation_label") or "")]
                # bodies live in the document-1 child of the labelled document
                labelled = {r["citation_path"] for r in cand}
                cand = cand + [r for r in st_rows.get("form", []) if r["citation_path"].rsplit("/", 1)[0] in labelled]
            head_pat = HEAD.get(eid)
            hit = best_hit(cand, patterns, head_pat, reject=opts.get("reject"), require_head=opts.get("require_head"), head_reject=opts.get("head_reject"))
            if eid == "S19":
                s19_hit = hit

            if hit:
                r, snip, score = hit
                dc = r["_dc"]
                weak = len(r.get("body") or "") > 200_000
                note = f"{dc} body ('{(r.get('heading') or r.get('citation_label') or r['citation_path'])[:60]}', {len(r['body'])} chars): '{snip[:180]}'"
                if weak:
                    note += "; NOTE: whole-chapter dump, the fact is inside a >200k-char body (weak provenance, needs sectioning)"
                if year == "2026" and "2026" not in (r.get("body") or ""):
                    note += "; NOTE: the body itself does not state 2026, the year comes from the scope/document label"
                    if st == "mn":
                        note += "; the MN inflation-adjusted-amounts bodies carry columns labelled 2019, so the 2026 figures are NOT verifiably in the corpus (extraction defect)"
                if family == "state statute" and dc != "statute" and not opts.get("any_class"):
                    add(j, eid, label, level, family, "EXTRACTABLE", r["_v"], r["citation_path"], f"only a {dc} body carries it; the enabling statute section is not in any selected statute scope ({stat_desc}); {note}; posted by {legis}", pe, rs)
                elif st == "mn" and eid == "F06":
                    add(j, eid, label, level, family, "REVIEW", r["_v"], r["citation_path"], note, pe, rs)
                elif eid == "F06" and body_only_2026:
                    add(j, eid, label, level, family, "REVIEW", r["_v"], r["citation_path"], "no 2026-labelled document; a TY2025/undated body mentions a 2026 figure: " + note + "; verify it is a TY2026 parameter and not an estimated-tax reference", pe, rs)
                else:
                    add(j, eid, label, level, family, "PRESENT", r["_v"], r["citation_path"], note, pe, rs)
                continue

            # no hit
            if unselected and eid in ("S01", "S29"):
                add(j, eid, label, level, family, "EXTRACTABLE", "", "", unselected + "; no selected scope carries it; the fix is a selector change, not a fetch", pe, rs)
            elif family in ("state statute", "state statute or bulletin"):
                add(j, eid, label, level, family, "EXTRACTABLE", "", "", f"no selected statute body for this state carries it (selected statute scopes: {stat_desc}; income-tax chapter rows: {len(st_rows['statute'])}); the state code is posted by {legis}", pe, rs)
            elif family == "state regulation":
                add(j, eid, label, level, family, "EXTRACTABLE", "", "", "no selected regulation scope for this state is a revenue-department income tax regulation (the selected regulation scopes are benefit-program rules); the administrative code chapter is posted by the state's code publisher", pe, rs)
            elif eid in ("F01", "F02"):
                if q.get("queue_status") == "blocked_primary_source":
                    add(j, eid, label, level, family, "OUTREACH", "", "", f"queue row blocked_primary_source: {qnote[:200]}", pe, rs)
                else:
                    have = ", ".join(sorted({(r.get("heading") or r["citation_path"])[:50] for r in st_rows["form"] if r.get("kind") == "document" and r.get("heading")})) or "none"
                    add(j, eid, label, level, family, "EXTRACTABLE", "", "", f"no TY2025 resident {'return form' if eid == 'F01' else 'instruction booklet'} in any selected form scope (form documents present: {have}); queue row '{q.get('queue_status')}' points at {ts.get('document_class')}/{ts.get('version')}; publisher forms index: {idx or q.get('primary_source_url') or 'state revenue department forms page'}", pe, rs)
            elif eid == "F03":
                add(j, eid, label, level, family, "EXTRACTABLE", "", "", f"no TY2025 rate schedule/tax table/flat-rate body in the selection (form bodies: {len(st_rows['form'])}); publisher forms index {idx or q.get('primary_source_url') or 'revenue department forms page'}", pe, rs)
            elif eid == "F04":
                add(j, eid, label, level, family, "EXTRACTABLE", "", "", f"no TY2025 instruction body carrying the printed standard deduction/exemption amounts in the selection; publisher forms index {idx or q.get('primary_source_url') or 'revenue department forms page'}", pe, rs)
            elif eid == "F05":
                add(j, eid, label, level, family, "EXTRACTABLE", "", "", f"no TY2025 instruction body carrying the state EITC/child credit parameters in the selection; publisher forms index {idx or q.get('primary_source_url') or 'revenue department forms page'}", pe, rs)
            elif eid == "F06":
                m26 = re.search(r"[^.;]*2026[^.;]*", qnote + " " + " ".join(fams))
                if m26 and re.search(r"\bES\b|-ES|(?i:estimat)|2026 D-40|(?i:withholding)|1040-ES|PIT-ES|IN-114|DR 0104EP|ES-40", m26.group(0)):
                    add(j, eid, label, level, family, "EXTRACTABLE", "", "", f"no 2026-labelled body with amounts in any selected scope; the queue row records a 2026 product on the publisher's index not taken ('{m26.group(0).strip()[:110]}'); index {idx}", pe, rs)
                else:
                    add(j, eid, label, level, family, "REVIEW", "", "", "no 2026-labelled body with amounts in any selected scope and the queue row records no 2026 product; whether the department has posted TY2026 figures (most publish them in the 2026 estimated-tax or withholding instructions) was not verified", pe, rs)
            else:
                add(j, eid, label, level, family, "REVIEW", "", "", "no selected body carries it and the evidence does not settle the status", pe, rs)

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------
    out = a.out
    os.makedirs(out, exist_ok=True)
    cols = ["jurisdiction", "element", "level", "family", "status", "scope_version", "citation_path", "pe_modeled", "evidence_note"]
    with open(os.path.join(out, "tax-matrix.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols + ["element_label", "rulespec_encoded"], extrasaction="ignore")
        w.writeheader()
        for r in matrix:
            row = dict(r)
            row["element_label"] = r["_label"]
            row["rulespec_encoded"] = r["_rs"]
            w.writerow(row)

    stats = {
        "elements": len(schema_elements),
        "federal_elements": len(FED),
        "state_elements": len(S),
        "cells": len(matrix),
        "by_status": dict(Counter(r["status"] for r in matrix)),
        "by_status_federal": dict(Counter(r["status"] for r in matrix if r["jurisdiction"] == "us")),
        "by_status_state": dict(Counter(r["status"] for r in matrix if r["jurisdiction"] != "us")),
        "per_jurisdiction": {},
        "gap_by_element": {},
        "gap_by_family": {},
        "pe_not_modeled": [e["id"] + " " + e["label"] for e in schema_elements if e.get("level") == "federal" and str(e.get("pe_modeled")) == "no"],
        "seconds": round(time.time() - t0),
        "rows_loaded": nrows,
    }
    for j in ["us"] + [f"us-{s}" for s in STATES]:
        stats["per_jurisdiction"][j] = dict(Counter(r["status"] for r in matrix if r["jurisdiction"] == j))
    ge = defaultdict(Counter)
    for r in matrix:
        if r["jurisdiction"] != "us" and r["status"] in ("EXTRACTABLE", "REVIEW", "ABSENT", "OUTREACH"):
            ge[r["element"]][r["status"]] += 1
    stats["gap_by_element"] = {k: dict(v) for k, v in sorted(ge.items(), key=lambda kv: -sum(kv[1].values()))}
    gf = defaultdict(Counter)
    for r in matrix:
        if r["status"] in ("EXTRACTABLE", "REVIEW", "ABSENT", "OUTREACH"):
            gf[r["family"]][r["status"]] += 1
    stats["gap_by_family"] = {k: dict(v) for k, v in sorted(gf.items(), key=lambda kv: -sum(kv[1].values()))}
    # per-state PE coverage of state elements
    stats["pe_state_not_modeled_cells"] = sum(1 for r in matrix if r["jurisdiction"] != "us" and r["status"] != "N/A" and r["pe_modeled"] == "no")
    stats["pe_state_not_modeled_by_element"] = dict(Counter(r["element"] for r in matrix if r["jurisdiction"] != "us" and r["status"] != "N/A" and r["pe_modeled"] == "no"))
    json.dump(stats, open(os.path.join(out, "tax-stats.json"), "w"), indent=1)

    schema = {
        "title": "Needs schema: individual income tax (federal + 50 states + DC), law-derived",
        "date": "2026-09-11",
        "method": {
            "primary_source": "the law's own structure: 26 U.S.C. subtitle A chapter 1 section by section (subchapters A, B; individual-facing parts of D, E, F, N, O, P), chapters 2, 2A, 21, 24, 61, 65, 68, 79; 26 CFR part 1 and part 31 families; annual revenue procedures, notices, SSA determinations; IRS forms, schedules, instructions and publications; for each state a section-by-section template of its individual income tax chapter, its regulations, annual forms, rate schedules and department bulletins; for the nine no-broad-tax states the constitutional or statutory bar plus any wage, interest, dividend or capital-gains tax",
            "element_definition": "a fact an encoder must read (a rate, threshold, amount, definition, eligibility rule, or a whole product where the product is the carrier of many facts), not a topic",
            "federal_inheritance": "federal elements appear once (jurisdiction us) and are inherited by all 51 jurisdictions",
            "cross_checks": ["PolicyEngine-US parameters gov/irs, gov/states/<st>/tax, gov/local (column pe_modeled)", "rulespec-us us/statutes/26, us/policies/irs, us-<st>/policies/income_tax and statutes (column rulespec_encoded)"],
            "statuses": {"PRESENT": "a specific provision body in a selected scope carries it (body read by regex, snippet quoted)", "EXTRACTABLE": "the rule exists and the publisher lists the carrying family; not taken", "ABSENT": "the rule exists but the publisher posts nothing carrying it", "OUTREACH": "publisher block recorded in the queue", "REVIEW": "could not tell", "N/A": "the jurisdiction's law has no such rule (analyst knowledge; verify)"},
            "uncertainty": "the known-law sets in tax-check.py (state EITC, child credit, CDCC, AMT, surtax, local taxes, standard deduction, exemptions, capital gains, indexing, low-income relief, circuit breakers) are analyst knowledge of TY2025 law and drive the N/A rows; every N/A note says so. Regex evidence can miss a fact that is phrased differently (false EXTRACTABLE) or match a cross-reference (false PRESENT); the quoted snippet in evidence_note is the audit trail.",
        },
        "element_count": len(schema_elements),
        "elements": schema_elements,
        "known_law_sets": {k: sorted(v) for k, v in K.items()},
        "income_tax_chapter_filters": INCOME_TAX_CHAPTER,
    }
    with open(os.path.join(out, "tax-schema.yaml"), "w") as f:
        yaml.safe_dump(schema, f, sort_keys=False, allow_unicode=True, width=120)
    print(json.dumps({k: stats[k] for k in ("elements", "cells", "by_status", "by_status_federal", "by_status_state", "seconds")}, indent=1))


if __name__ == "__main__":
    main()
