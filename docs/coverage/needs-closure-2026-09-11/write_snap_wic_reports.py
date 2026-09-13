#!/usr/bin/env python3
"""Write snap.md and wic.md from the matrices, schemas and summary.json produced by check_snap_wic.py.

    python3 docs/coverage/needs-closure-2026-09-11/write_snap_wic_reports.py \
        --dir docs/coverage/needs-closure-2026-09-11

The tables are computed from the CSVs; the narrative sections are authored here so that a re-run
of the check regenerates the numbers without losing the reading.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

import yaml

STATUSES = ["PRESENT", "EXTRACTABLE", "ABSENT", "OUTREACH", "REVIEW"]


def load(d: Path, program: str):
    rows = list(csv.DictReader(open(d / f"{program}-matrix.csv")))
    schema = yaml.safe_load(open(d / f"{program}-schema.yaml"))
    summary = json.load(open(d / "summary.json"))
    return rows, schema, summary


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" if i == 0 else "---:" if isinstance(rows[0][i], int) else "---" for i in range(len(header))) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def status_counts(rows, pred):
    c = Counter(r["status"] for r in rows if pred(r))
    return [c.get(s, 0) for s in STATUSES]


def federal_family_rollup(rows, schema):
    fam_of = {e["id"]: e["family"] for e in schema["elements"]}
    label = {"federal_statute": "statute", "federal_regulation": "regulation (eCFR)", "fns_guidance": "FNS/FNA guidance"}
    out = []
    for fam in ("federal_statute", "federal_regulation", "fns_guidance"):
        us = [r for r in rows if r["jurisdiction"] == "us" and fam_of[r["element"]] == fam]
        out.append([label[fam], len(us)] + status_counts(us, lambda r: True))
    return out


def per_jurisdiction(rows):
    out = []
    byj = defaultdict(list)
    for r in rows:
        if r["level"] == "state":
            byj[r["jurisdiction"]].append(r)
    for j, rs in byj.items():
        c = status_counts(rs, lambda r: True)
        open_ = len(rs) - c[0] - c[2]  # not PRESENT and not ABSENT
        out.append([j, len(rs)] + c + [f"{open_} open" if open_ else "closed"])
    return out


def top_gaps(rows, schema, n=12):
    lab = {e["id"]: e for e in schema["elements"]}
    byel = defaultdict(Counter)
    for r in rows:
        if r["level"] == "state":
            byel[r["element"]][r["status"]] += 1
    scored = []
    for e, c in byel.items():
        gap = sum(v for k, v in c.items() if k != "PRESENT")
        scored.append((gap, e, c))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out = []
    for gap, e, c in scored[:n]:
        el = lab[e]
        out.append([e, el["label"][:95], el["family"], gap, c.get("EXTRACTABLE", 0), c.get("ABSENT", 0), c.get("OUTREACH", 0), c.get("REVIEW", 0)])
    return out


def pe_gap_list(schema):
    out = defaultdict(list)
    for e in schema["elements"]:
        if str(e["pe_modeled"]).startswith("no"):
            out[e["level"]].append(e)
    return out


SNAP_NARRATIVE = {
    "method": """The schema follows the law's own structure, in order of authority. (1) Federal statute: every
section of 7 U.S.C. chapter 51 (2011 to 2036d; 2030 and 2033 are repealed container rows and are
noted, not counted) and every subsection of the four household-facing sections 2012 (definitions),
2014 (eligible households), 2015 (disqualifications) and 2017 (allotment), plus the state-plan
subsections 2020(e), (i), (s) and the E&T funding subsection 2025(h). (2) Federal regulation: every
non-reserved section of 7 CFR 271 to 285 as listed by the eCFR structure API (current edition, read
2026-09-12; `cfr_structure.py`), plus 54 paragraph-level elements of 7 CFR 273 (household concept,
application processing, non-citizens, students, work provisions, resources, income and deductions,
benefit computation, special households, reporting, notices, recertification, hearings, IPV, claims,
MRRB, ABAWD, TBA). Sections carrying a state option are marked `federal_with_state_option` and have
state-level children. (3) FNS/FNA guidance: the FY 2026 COLA tables and income standards (nine
figures), the annual state SUA table, the ABAWD waiver list, the BBCE chart, the two OBBBA
implementation memos in the corpus and the rest of that series, and the State Options Report as a
cross-check. (4) State rulebook: 61 elements a state's manual, regulation, annual table or
transmittal, state plan or statute must carry, each a fact an encoder reads (an amount, a threshold,
an election, a period, a disqualification rule), grouped by the family that carries it.

Selected scopes are those of `docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json`
with the twelve SNAP superseding scopes on disk (`2026-09-11-<st>-snap-manual-supersede` for AR, GA,
KY, ME, MI, NC, ND, NE, NV, OK, TN, WY) replacing their released versions. A state's SNAP rulebook is
its manual, regulation, policy and SNAP guidance scopes (the list per state is in `summary.json`
under `scopes`; other-program scopes such as Medicaid, TANF, WIC, LIHEAP and tax are excluded by
name). Federal statute and paragraph-granular regulation elements are checked by citation path: the
row must exist with a non-empty body. The selected 7 CFR 273 scopes are section-granular (273.2 is
one 154 KB body), so 273 paragraph elements are checked by a keyword regex over the section body;
guidance elements by regex over the selected federal guidance bodies; state elements by regex over
every provision body of the state's SNAP scopes, taking the provision with the most matches as the
citation (a longer body breaks ties). Every regex is recorded per element in `snap-schema.yaml`, and
every PRESENT match with its snippet is in `snap-hits.jsonl`; a reviewer can open the cited row.

Status rules: PRESENT only when a provision body in a selected scope carries the element (cited with
scope version, citation path and snippet). EXTRACTABLE when the completion queue row or a run note
records that the publisher lists the carrying family and it was not taken (the family and index are
named). ABSENT when the publisher's index was inventoried family-by-family in the #680 completion
pass and no listed family or rulebook text carries the fact (for optional elections this reads as
"not elected"). OUTREACH for the three publisher blocks the queue records (AZ DES FAA host, NY OTDA,
OH eManuals). REVIEW when the regex found nothing and the publisher index was not inventoried
family-by-family (the 23 states outside the completion queue), or when a 273 paragraph regex failed
inside a present section. Federal-level elements are decided once at the `us` row and inherited
(`INHERITED`) by the 51 states, so each state row carries the federal status in its note rather than
repeating the evidence.""",
    "gaps": """**Federal.** 7 CFR 271, 272, 274 and 276 to 285 (126 non-reserved sections) are in no selected
scope: the federal SNAP regulation in the corpus is 273 (complete across two scopes) and 275 only.
271.2 (definitions, including elderly or disabled member), 272.2 (state plan of operation), 272.8
(IEVS), 272.17 (lottery), 274.7 (benefit redemption, restaurant meals), 277 (administrative cost
sharing) and 278 (retailers) are the rule-carrying parts an encoder reads; 283 (QC appeals, 32
sections) and 279 are procedural. All are EXTRACTABLE from eCFR with the extractor that produced
`us/regulation/2026-06-15-title-7-part-275`. 42 U.S.C. chapter 51 is complete section by section and
subsection by subsection in `us/statute/2026-07-22-rulespec-title-7-consolidated`. Of the guidance
families, the FY 2026 allotment, deduction, asset and income tables are present; the FNS state SUA
table, the ABAWD waiver list, the BBCE chart and the remaining OBBBA memos are EXTRACTABLE from the
FNS/FNA origin host; the full COLA memo (minimum benefit figure) is EXTRACTABLE; the State Options
Report is REVIEW because the queue policy forbids it as a source for state rules.

**State plans (51 states each).** No SNAP E&T State Plan is in the corpus except Colorado's
(`us-co/policy/co-cdhs-snap-et-state-plan-ffy2026`), although FNS posts every state's plan and two
state indexes list theirs (AR, KY): 50 EXTRACTABLE. The 272.2 State Plan of Operation and its option
attachments are in no scope for any state; FNS does not post them, 24 inventoried publishers list
none (ABSENT), New Mexico lists a verification-plan attachment (EXTRACTABLE), and the rest are REVIEW.
These two families are the largest shared gap and the one the corpus cannot close from the manuals.

**Applied FY 2026 tables and transmittals.** The state's own applied table of standard deductions,
shelter caps, income limits and maximum allotments, and the transmittal that put the FY 2026 figures
into effect, were found in the rulebook text of 26 to 36 states; the federal figures are PRESENT for
everyone, so this is a provenance gap (which document the encoder cites for the state's applied
value), not a missing fact. Where the publisher lists a transmittal or table family that was not
taken (GA MT cover letters, NC change notices, MI policy bulletins and RFT tables, NV transmittals, FL
summaries of changes, ND release PDFs, NH service releases, KY OMTL volumes, AR media-library
editions, MA DTA Online Guide, CA ACLs) the cell is EXTRACTABLE; elsewhere REVIEW.

**Optional elections.** BBCE, its threshold and asset waiver, mandatory SUA, the standard medical
deduction, TBA, CAP/ESAP, restaurant meals, drug-felony modification, state-funded non-citizen food
assistance and state-funded minimum supplements are elections; a fully inventoried rulebook with no
text for them is ABSENT (not elected). Where the inventory was not family-by-family the cell is REVIEW.

**Blocked publishers.** Arizona (DES FAA manual host, F5 challenge; the released scope is a thin
archived-snapshot capture), New York (OTDA host bot-challenged; the SNAP Source Book scope carries 22
rows) and Ohio (eManuals Food Assistance manual host does not answer; OAC 5101:4 is complete) carry
OUTREACH for every element the regex did not find.""",
    "closers": """- 7 CFR 271-285: one eCFR extraction per part with the existing `extract-official-documents`
  path used for part 275 (126 sections; the whole title-7 subchapter C is about 2 MB of XML). Closes
  126 federal cells and, by inheritance, their 51 state rows each.
- FNS annual tables (SUA by state, ABAWD waiver status, BBCE chart, full COLA memo, remaining OBBBA
  memos): one guidance manifest against the FNA origin host `fns-prod.azureedge.us`, the host the
  existing `manifests/us-snap-guidance.yaml` already uses. Closes 5 federal cells; the SUA table alone
  gives every state's HCSUA/LUA/telephone figures an FNS citation.
- SNAP E&T State Plans: FNS posts all 51 on one index (`fns.usda.gov/snap/et/plans`, origin host);
  one manifest, one scope per state or one federal scope with 51 documents. Closes 50 cells.
- State transmittal and table families already inventoried (GA, NC, MI, NV, FL, ND, NH, KY, AR, MA,
  CA): per-state completion scopes from the recorded index families; these carry the applied FY 2026
  figures and the revision history the manuals cite. Closes most of the 15 to 25 non-PRESENT cells per
  table element (snap_s15 to s18, s20) and gives the transmittal element its own family.
- 272.2 State Plans of Operation: not published by FNS or by 24 inventoried states; outreach to state
  agencies (or a FOIA-style request to FNS regional offices) is the only route. Record as a standing
  gap rather than a queue item.
- AZ, NY, OH: outreach for an official export (AZ DES FAA manual, NY OTDA SNAP Source Book and policy
  directives, OH eManuals Food Assistance manual). Each closes 9 to 24 state cells.
- REVIEW cells in the 23 states outside the #680 completion queue: a family-by-family inventory of
  each publisher's SNAP index (the completion pass method) turns REVIEW into ABSENT or EXTRACTABLE
  without new extraction; the same pass can re-probe the regex misses for mandatory elements.""",
}

WIC_NARRATIVE = {
    "method": """The schema follows the law's own structure. (1) Federal statute: the 19 subsections of 42 U.S.C.
1786 (a) to (s), section 17 of the Child Nutrition Act, each a distinct rule-carrying unit (eligibility
in (d), state plan in (f), funds and rebates in (h), FMNP in (m), vendor disqualification in (n)-(o)).
(2) Federal regulation: the 30 sections of 7 CFR 246 as listed by the eCFR structure API (current
edition, read 2026-09-12) plus 25 participant-facing paragraph elements of 246.7 (residency,
categories, income standard and determination, adjunctive eligibility, nutritional risk, processing
standards, certification periods, priority, rights, notices, dual participation, VOC, institutions,
remote certification), 246.10 (food lists, tailoring, medical documentation, food packages I to VII
and CVB), 246.12 (issuance, vendors, participant sanctions), 246.4(a), 246.2, 246.9, 246.11 and
246.16a. (3) FNS/FNA guidance: the income eligibility guidelines, the CVB memo, the food package
memos, the nutrition-risk criteria list, the pre-FY 2025 memo family, the Federal Register notice
family, infant formula rebate guidance and state-plan guidance. (4) State rulebook: 31 elements the
state's WIC policy manual, state plan or administrative rule must carry (income standard and
guidelines table, income determination, adjunctive programs, categories, nutritional risk, bloodwork,
certification periods, residency and physical presence, documentation, temporary certification,
priority, processing standards, food packages and CVB, food list, medical documentation,
breastfeeding categories, dual participation and VOC, participant sanctions, notices, fair hearings,
nutrition education, vendors, issuance, local agencies, migrant and homeless, FMNP, civil rights,
caseload, state plan, state rule chapter).

Selected scopes: `us/guidance/2026-09-10-wic-fns-guidance` (11 documents) and the paragraph-granular
7 CFR 246 in `us/regulation/2026-07-13-recovery-r2026-07-17-dedup` at the federal level; the 21 state
scopes `us-xx/manual/2026-09-10-wic-state-policy-manual` (one root plus one body provision per policy
PDF). Federal statute and 246.7 paragraph elements are checked by citation path; 246.4, 246.10 and
246.12 have no paragraph rows, so their paragraph elements are checked by keyword regex over the
section body; guidance by regex over the selected guidance bodies; state elements by regex over every
policy body of the state's WIC scope, taking the policy with the most matches. Every regex is in
`wic-schema.yaml`; every PRESENT match with its snippet is in `wic-hits.jsonl`.

Status rules: PRESENT only with a cited provision body. EXTRACTABLE when the queue row or run note
names an untaken family that carries it (state plans on MT, VT, WI, UT, WV, CT, MA and AL sites;
Tennessee's WIC rule 1200-15-02; Minnesota's exhibits, Connecticut's attachments and the other
not-taken index items where a mandatory element was not found). ABSENT for the 20 publishers that
post no manual (queue `blocked_primary_source`, not published) and for optional elements a complete
manual does not carry. OUTREACH for the 10 publishers that block or gate the manual (AR, AZ as served,
DE, IL, KS, MA, NH access blocks; MO, NM, NV login or password). REVIEW where no family was
inventoried (state plans and state rule chapters for most states) or a mandatory regex found nothing
in a complete manual. Federal elements are decided at the `us` row and inherited.""",
    "gaps": """**Federal statute.** 42 U.S.C. 1786 is in no corpus scope in any form: no `us/statute/42/1786` row
exists in any JSONL under `provisions/us/statute/` (the four files that mention "1786" cite it from
other sections). All 19 subsections are EXTRACTABLE from uscode.house.gov, the publisher of the
title 7 and title 42 statute scopes the corpus already holds.

**Federal regulation and guidance.** 7 CFR 246 is complete (30 sections, 231 paragraph rows under
246.7) as captured on 2026-07-13, so the 2024 food package final rule text is in force in the scope.
The 2026-2027 and 2025-2026 income eligibility guidelines, the FY 2026 CVB memo, the food package
flexibilities memo (#2025-5) and the fluid-milk increase memo (#2026-1) are PRESENT. The nutrition
risk criteria list, the 143 standing pre-FY 2025 policy memoranda, the 70 Federal Register notices,
infant formula rebate guidance and state plan guidance are EXTRACTABLE from the FNA resource browser
(the queue row inventoried the families; none taken).

**States without a manual in the corpus (30).** Twenty publishers post no WIC policy manual on their
own site (AK, AL, FL, HI, ID, IN, LA, MS, MT, ND, NE, NY, OH, OK, SC, SD, TN, VT, WI, WY): every
manual-carried element is ABSENT for them with the queue's finding as evidence. Ten publishers block
or gate it (AR, AZ, DE, IL, KS, MA, NH; MO, NM, NV): OUTREACH. For these 30 states the only corpus
route to the state's income guidelines, food list and certification rules is the state plan (posted
by MT, VT, WI, AL as a notice) or the state administrative rule (TN 1200-15-02), both EXTRACTABLE
where the queue saw them and REVIEW elsewhere.

**States with a manual (21).** The 29 manual-carried elements are PRESENT in nearly every state
with a manual; the exceptions are New Jersey (only the vendor-management functional area is
published, so 18 of 29 are ABSENT by the publisher's own choice) and a handful of REVIEW/EXTRACTABLE
cells where a mandatory element was not found and the queue lists untaken items that may carry it
(MN exhibits, CT attachments, RI's compiled manual, KY's policy-group PDFs, ME appendices).

**State plan and state rule (all 51).** No WIC state plan (246.4) is in the corpus for any state, and
no state administrative-code WIC chapter; the WIC queue inventoried the manual family only. These are
the two shared gaps that a manual cannot close: the state plan is where the income standard,
priority system, food list and certification procedures are filed with FNS every year.""",
    "closers": """- 42 U.S.C. 1786: one uscode.house.gov extraction (section 17 of the Child Nutrition Act) with the
  extractor that built `us/statute/2026-07-22-rulespec-title-7-consolidated`. Closes 19 federal cells.
- FNA guidance families: one manifest against the FNA resource browser on the origin host for the
  nutrition risk criteria list, the pre-FY 2025 memoranda, the Federal Register notices, rebate and
  state-plan guidance (the batch-1 run note records the facet counts: 195, 154, 70). Closes 5 federal
  cells.
- WIC state plans: FNS does not post them; eight states post theirs (MT, VT, WI, UT, WV, CT, MA, AL
  notice). A state-plan family manifest for those eight closes 8 cells and, for MT and VT, is the only
  published policy text. The other 43 need outreach or a FOIA-style request to FNS regional offices.
- State WIC rule chapters: a state-register inventory (the tax and SSI passes' method) for the states
  that codify WIC (TN 1200-15-02 is the one the queue saw); unverified elsewhere.
- Blocked publishers (AR, AZ, DE, IL, KS, MA, NH, MO, NM, NV): outreach for an official export; the
  batch-4 note names AZ (browser check of the agencies page) and KS (Document Center listing) as the
  first retries. Each closes 29 cells.
- Publishers that post no manual (20): nothing to extract; the gap is real and should be recorded as
  such against the program's closure, with the state plan as the fallback family.
- Untaken index items in states with a manual (MN exhibits 5-A/5-T/5-U/6-A, CT income guidelines
  sheet and attachments, ME appendices, WV attachments, DC clinical manuals, OR policy updates): small
  completion scopes from the recorded index families.""",
}


def write(program, d: Path, narrative):
    rows, schema, summary = load(d, program)
    s = summary[program]
    n_el = s["elements"]
    n_state_el = sum(1 for e in schema["elements"] if e["level"] == "state")
    n_fed_el = n_el - n_state_el
    c = s["status_counts"]
    us_rows = [r for r in rows if r["jurisdiction"] == "us"]
    st_rows = [r for r in rows if r["level"] == "state"]
    us_c = status_counts(us_rows, lambda r: True)
    st_c = status_counts(st_rows, lambda r: True)
    pe = pe_gap_list(schema)
    pe_n = sum(len(v) for v in pe.values())
    name = "SNAP" if program == "snap" else "WIC"
    t = summary["timing"]

    lines = []
    lines.append(f"# {name}: needs-driven closure check (2026-09-11 corpus)\n")
    lines.append(f"Corpus as selected on 2026-09-11 (draft union selector plus the twelve SNAP superseding scopes on disk); checked {t['finished'][:10]}. "
                 f"Schema: `{program}-schema.yaml` ({n_el} elements: {n_fed_el} federal, {n_state_el} state). "
                 f"Matrix: `{program}-matrix.csv` ({s['cells']} cells = 52 jurisdictions x {n_el} elements, one row each). "
                 f"Builder: `check_snap_wic.py` (read-only over `data/corpus`; {t['elapsed_seconds']} s, {t['scopes_loaded']} scopes and {t['rows_loaded']} provision rows loaded for both programs); "
                 f"PRESENT evidence: `{program}-hits.jsonl`.\n")
    lines.append("## Method\n")
    lines.append(narrative["method"] + "\n")
    lines.append("## Cells by status\n")
    lines.append(table(["status"] + STATUSES + ["INHERITED", "total"], [["cells"] + [c.get(x, 0) for x in STATUSES] + [c.get("INHERITED", 0), s["cells"]]]) + "\n")
    lines.append(f"Federal elements are checked once at the `us` row and inherited by the 51 states (`INHERITED`, {c.get('INHERITED', 0)} cells whose note names the federal status). "
                 f"The federal row alone ({n_fed_el} elements): PRESENT {us_c[0]}, EXTRACTABLE {us_c[1]}, ABSENT {us_c[2]}, OUTREACH {us_c[3]}, REVIEW {us_c[4]}. "
                 f"State-level cells (51 x {n_state_el} = {len(st_rows)}): PRESENT {st_c[0]}, EXTRACTABLE {st_c[1]}, ABSENT {st_c[2]}, OUTREACH {st_c[3]}, REVIEW {st_c[4]}.\n")
    lines.append("## Federal roll-up by document family\n")
    lines.append(table(["federal family", "elements"] + STATUSES, federal_family_rollup(rows, schema)) + "\n")
    fed_gaps = [r for r in us_rows if r["status"] != "PRESENT"]
    grouped = defaultdict(list)
    for r in fed_gaps:
        if r["family"] == "federal_regulation" and r["evidence_note"].startswith("part in no"):
            key = "cfr-parts"
        elif r["element"].startswith("wic_usc_1786"):
            key = "usc-1786"
        else:
            key = r["element"]
        grouped[key].append(r)
    lines.append("Federal cells not PRESENT:\n")
    for key, rs in grouped.items():
        if key == "cfr-parts":
            parts = sorted({r["element"].split("_")[2] for r in rs})
            lines.append(f"- {len(rs)} elements {rs[0]['status']}: 7 CFR parts {', '.join(parts)} ({rs[0]['evidence_note'][:220]})")
        elif key == "usc-1786":
            lines.append(f"- {len(rs)} elements {rs[0]['status']}: 42 U.S.C. 1786(a) to (s) ({rs[0]['evidence_note'][:260]})")
        else:
            r = rs[0]
            lines.append(f"- `{r['element']}` {r['status']}: {r['evidence_note'][:260]}")
    lines.append("")
    lines.append("## Per-jurisdiction roll-up (state-level elements)\n")
    lines.append(table(["jurisdiction", "state elements"] + STATUSES + ["closure"], per_jurisdiction(rows)) + "\n")
    lines.append("`closure` counts cells that are neither PRESENT nor ABSENT (EXTRACTABLE, OUTREACH and REVIEW): what still needs an action or a decision. "
                 "ABSENT cells are closed in the sense that the publisher posts nothing; for optional elections they read as \"not elected\".\n")
    lines.append("## Top gaps by how many states share them\n")
    lines.append(table(["element", "label", "family", "states not PRESENT", "EXTRACTABLE", "ABSENT", "OUTREACH", "REVIEW"], top_gaps(rows, schema)) + "\n")
    lines.append("## What the gaps are\n")
    lines.append(narrative["gaps"] + "\n")
    lines.append("## What would close each class of gap\n")
    lines.append(narrative["closers"] + "\n")
    lines.append("## Elements beyond PolicyEngine\n")
    lines.append(f"PolicyEngine models {n_el - pe_n} of the {n_el} elements at least partially (`pe_modeled` yes or partial) and none of the other {pe_n}. "
                 "The law has these and PolicyEngine does not (grouped by level):\n")
    for level in ("federal_statute", "federal_only", "federal_with_state_option", "federal_regulation", "federal_guidance", "state"):
        els = pe.get(level, [])
        if not els:
            continue
        lines.append(f"- **{level}** ({len(els)}): " + "; ".join(f"`{e['id']}` {e['label'][:70]}" for e in els[:40]) + (" ..." if len(els) > 40 else ""))
    lines.append("")
    lines.append("`pe_modeled` is recorded per element in the schema and per row in the matrix; `rulespec_scoped` records whether rulespec-us encodes the source or a state program spec cites it (federal elements are computed from the rulespec-us file tree and the `programs/*/snap` scope lists).\n")
    lines.append("## Schema notes and uncertainty\n")
    for n in schema["notes"]:
        lines.append(f"- {n}")
    lines.append("")
    lines.append("## Timing and searches\n")
    lines.append(f"- Check run started {t['started']}, finished {t['finished']} ({t['elapsed_seconds']} s for SNAP and WIC together); {t['scopes_loaded']} scope files and {t['rows_loaded']} provision rows read from `data/corpus/provisions`.")
    lines.append("- Searches: for every element with a `regex` in the schema, that regex was run (case-insensitive, dot matches newline) over every provision body of the jurisdiction's selected scopes listed in `summary.json` under `scopes`; citation-path elements were looked up by exact path (then by children with bodies). The eCFR structure was read once from `https://www.ecfr.gov/api/versioner/v1/structure/current/title-7.json` (5.3 MB) and the parts 246 and 271-285 section lists embedded in `cfr_structure.py`.")
    lines.append("- Queue evidence: `manifests/snap-completion-agent-queue.yaml` (index_families, queue_status, index_url per state), `manifests/state-snap-manual-agent-queue.yaml`, `manifests/wic-agent-queue.yaml` (queue_status, index_inventory, notes), plus the reviewer facts transcribed from the 2026-09-10/11 run notes into the script's tables (`SNAP_BLOCKED`, `SNAP_TRANSMITTAL_FAMILY`, `SNAP_ET_PLAN_PUBLISHER`, `WIC_BLOCK_CLASS`, `WIC_STATE_PLAN_PUBLISHER`, `WIC_NOT_TAKEN_FAMILY`).")
    lines.append("- Spot checks: the PRESENT snippets of every optional-election element and every table element were read for false positives after each run; regexes were tightened three times (BBCE, mandatory SUA, LIHEAP heat-and-eat, standard medical deduction, table elements, TBA, state-funded programs, restaurant meals, state minimum supplements, SSI cash-out; WIC adjunctive eligibility and temporary certification) and a per-element exclusion window added. Residual false positives are possible for elements whose wording varies by state; the cited row is always given so a reader can check.")
    lines.append("")
    (d / f"{program}.md").write_text("\n".join(lines))
    return {"elements": n_el, "cells": s["cells"], "status": c, "pe_not_modeled": pe_n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, type=Path)
    a = ap.parse_args()
    out = {}
    out["snap"] = write("snap", a.dir, SNAP_NARRATIVE)
    out["wic"] = write("wic", a.dir, WIC_NARRATIVE)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
