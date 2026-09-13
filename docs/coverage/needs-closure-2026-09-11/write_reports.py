#!/usr/bin/env python3
"""Derive <program>.md and README.md from the matrices and schemas written by
build_ssi_liheap_medicare_matrices.py. Every table here is computed from the CSVs; the
narrative sections (method, closers, uncertainties) are written by the analyst."""
import csv
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
STATUSES = ["PRESENT", "EXTRACTABLE", "ABSENT", "OUTREACH", "REVIEW"]
ORDER = {"PRESENT": 0, "REVIEW": 1, "EXTRACTABLE": 2, "OUTREACH": 3, "ABSENT": 4}


def load(prog):
    rows = list(csv.DictReader((HERE / f"{prog}-matrix.csv").open()))
    schema = yaml.safe_load((HERE / f"{prog}-schema.yaml").open())
    names = {e["id"]: e["name"] for e in schema["elements"]}
    return rows, schema, names


def table(header, body):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " if i == 0 else " ---: " for i in range(len(header))) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in body]
    return "\n".join(out)


def federal_rollup(rows, schema):
    fam = defaultdict(Counter)
    for e in schema["elements"]:
        if e["level"] != "federal":
            continue
        st = next(r["status"] for r in rows if r["jurisdiction"] == "us" and r["element"] == e["id"])
        fam[e["family"]][st] += 1
    body = [[f, sum(c.values())] + [c.get(s, 0) for s in STATUSES] for f, c in fam.items()]
    return table(["federal family", "elements"] + STATUSES, body)


def state_rollup(rows):
    per = defaultdict(Counter)
    for r in rows:
        if r["level"] == "state" and r["jurisdiction"] != "us":
            per[r["jurisdiction"]][r["status"]] += 1
    body = []
    for j in sorted(per):
        c = per[j]
        n = sum(c.values())
        gaps = c.get("REVIEW", 0) + c.get("EXTRACTABLE", 0) + c.get("OUTREACH", 0)
        body.append([j, n] + [c.get(s, 0) for s in STATUSES] + ["closed" if gaps == 0 else f"{gaps} open"])
    return table(["jurisdiction", "state elements"] + STATUSES + ["closure"], body)


def gaps(rows, names):
    g = defaultdict(list)
    for r in rows:
        if r["jurisdiction"] != "us" and r["level"] == "state" and r["status"] in ("EXTRACTABLE", "OUTREACH", "REVIEW"):
            g[(r["element"], r["status"])].append(r["jurisdiction"][3:])
    items = sorted(g.items(), key=lambda kv: -len(kv[1]))
    body = [[e, names[e][:90], s, len(js), " ".join(sorted(js))] for (e, s), js in items]
    return table(["element", "name", "status", "states", "which"], body), items


def cell_counts(rows):
    c = Counter(r["status"] for r in rows)
    return table(["status"] + STATUSES + ["total"], [["cells"] + [c.get(s, 0) for s in STATUSES] + [len(rows)]])


def pe_section(schema):
    pc = schema["policyengine_cross_check"]
    lines = [f"PolicyEngine-US models {pc['modeled_count']} of {schema['element_count']} elements in full, {pc['partial_count']} in part, and {pc['not_modeled_count']} not at all. The schema YAML lists every element; the ones PolicyEngine lacks entirely are:", ""]
    lines += [f"- {x}" for x in pc["not_modeled"]]
    lines += ["", "Modeled only in part:", ""] + [f"- {x}" for x in pc["partial"]]
    rc = schema["rulespec_cross_check"]
    lines += ["", f"rulespec-us encodes {len(rc['encoded'])} of the elements (paths in the schema's `rulespec_cross_check`)."]
    return "\n".join(lines)


NARRATIVE = {}

NARRATIVE["ssi"] = dict(
    title="SSI (federal SSI and state supplements)",
    method="""The schema follows the law's own structure, in order of authority: one element per section of
42 U.S.C. 1381 to 1383f (20 sections), one per subpart of 20 CFR 416 (22 subparts, A to V, plus the
Subpart K appendix), one per POMS SI subchapter as listed on SSA's own part SI chapter list on
2026-09-10 (every subchapter, taken or not), three annual-figure families (the COLA notice with the
federal benefit rate, the student earned income exclusion and the SGA amounts), and six state-level
elements for the supplement: whether the state runs an optional program and who administers it
(SI 01415.010), the state authority, the eligibility categories and living arrangements, the payment
amounts, the state income and resource methodology, and, for federally administered programs, SSA's
living-arrangement codes and payment levels (SI 01415.058). A POMS subchapter is treated as one
element because the encoder reads the subchapter as a unit; the schema file records the number of
sections behind each. Statute elements are whole sections; the held scope carries subsection rows.

Selected scopes read: `us/statute/2026-06-20-ssi-title-xvi-...` (226 rows, 1381 to 1382j),
`us/regulation/2026-09-11-title-20-part-416` (622 rows, complete), `us/manual/2026-09-10-ssi-poms-si`
(11,028 rows, 23 subchapters), `us/guidance/2026-07-05-ssa-cola-2026`,
`us/guidance/2026-05-17-ssa-automatic-determinations-2026`, and the state-supplement scopes named in
`manifests/ssi-agent-queue.yaml` (27 extracted, 22 done by pointer to older scopes). For every state
the cited row was opened and its heading and body checked; the paths are in the CSV. Status rules are
the brief's: PRESENT only with a selected scope and a citation path whose body carries the fact
(`verify_matrices.py` re-opens every PRESENT cell and checks selector membership); EXTRACTABLE when the
publisher lists the family and the queue or run note shows it was not taken; ABSENT with an `n/a`
note where the law gives the jurisdiction nothing to set; OUTREACH for the two publisher blocks;
REVIEW where the scope is present but the row that would carry the fact could not be identified or
carries the method without the figure.""",
    closers=OrderedDict([
        ("SSI-F-USC", "42 U.S.C. 1383 to 1383f (procedures, overpayments, representative payees, penalties, Medicaid eligibility of SSI recipients, outreach): eight sections, same publisher and adapter as the held Title XVI scope (uscode.house.gov USLM); one `extract-uscode` run with the section list widened."),
        ("SSI-F-POMS", "POMS part SI: 56 subchapters listed by SSA and not taken (SI 006 application process, SI 00530 fugitive felons, SI 00870 PASS, SI 01150 transfers and trusts, SI 012 grandfathered provisions, SI 017 Medicaid, SI 018 SNAP, SI 020 payments except 02001/02005, SI 021 to 023 underpayments, overpayments, posteligibility, SI 029, SI 040 appeals). Widen `TAKEN_SUBCHAPTERS` in `scripts/build_ssi_poms_si_manifests.py`; the extractor and index are proven."),
        ("SSI-F-CFR416-APPK", "20 CFR 416 Subpart K appendix: extend the eCFR adapter's `_appendix_citation_from_identifier` to subpart-scoped appendices and re-take with `--include-appendices` (run note 2026-09-11-federal-cfr-followon-parts)."),
        ("SSI-ST-2", "State enabling statutes for 24 state-administered or shared programs (for example AS 47.25, Conn. Gen. Stat. 17b-600, D.C. Code 4-205, 305 ILCS 5/3, Minn. Stat. 256D, RSMo 208, G.S. 108A, RSA 167, Wis. Stat. 49.77): a state-statute family through the existing state-code adapters. rulespec-us already encodes Conn. Gen. Stat. 17b-600 and D.C. Code 4-205.49 from text that is not in the selected corpus, so these two are the first to take."),
        ("SSI-ST-4", "Payment standards that the rule text delegates to a chart or notice: OKDHS Appendix C-1 (OK), the DTA SSP standards chart behind 106 CMR 327.330 (MA), AAM 601 Table A (NH, a table image the HTML extractor dropped), the OhioMHAS RSS payment notice (OH), MPPM 103 net income limits (SC), the DARS AG rate broadcast (VA), the 469 NAC standard-of-need table (NE), the department-approved rate (SD), a current KHPA/KDHE SSPP amount (KS), and the DHS MSA revised sections 01/2026 (MN: already on disk as `us-mn/manual/2026-06-27-mn-dhs-msa-revised-sections-2026-01`, only unselected). Ten states; each is one small document."),
        ("SSI-ST-5", "State income and resource methodology where the program has its own: AK, AL (page not located), ID, IL, MA, MO, NC, NE, NM, OK, SC, KY, CO, CT, FL, ME are PRESENT; VA and SD need the rule page identified; the F/S states (DC, DE, IA, MI, PA, RI) need the state-administered part inventoried (the queue covered only the SSA-administered part)."),
        ("SSI-ST-OR", "Oregon: OAR chapter 461 (OSIP eligibility 461-135, payment standard 461-155-0250, income deductions 461-160) on the Secretary of State OARD, which answered HTTP 200 on 2026-09-10; the OPEN notebook cites the rules by number only."),
        ("OUTREACH", "New York (otda.ny.gov JavaScript challenge) and Wyoming (ecom.wyo.gov Google-Sites embed): agency contact for a document copy, or a browser-rendered fetch under a recorded exception."),
    ]),
    uncertain="""Whether a POMS subchapter is the right grain (an encoder may want section-level elements for
SI 00830 with 183 sections); whether the mandatory pass-along supplement deserves its own state element
(it is folded into SSI-ST-1); the reading that a flat institutional add-on (GA, IN, LA, TX, UT, WA, WI)
has no state income methodology (SSI-ST-5 marked n/a) is the analyst's; and for the F/S states the
state-administered part of the program is outside what the queue inventoried, so SSI-ST-5 is REVIEW
rather than ABSENT.""",
)

NARRATIVE["liheap"] = dict(
    title="LIHEAP (federal block grant and the FY2026 state plans)",
    method="""The schema follows 42 U.S.C. 8621 to 8630 (ten sections), 45 CFR 96 subpart H (96.80 to 96.89), the
three federal figures a plan encoder needs every year (HHS poverty guidelines, the ACF state median
income table, the model plan instructions), and the FY2026 Detailed Model Plan section by section: the
plan is the state rulebook, so its sections 1 to 17 map to 17 state elements (program components and
dates; funding allocation; categorical eligibility; the SNAP nominal payment; countable income and
household definition; the heating threshold, extra rules and priority groups, benefit variables and
min/max; the benefit matrix attachment; cooling; crisis definitions, response times and benefit levels;
weatherization; outreach and agency designation; hearings; Assurance 16 and performance measures;
monitoring), plus one element for the state policy/operations manual that the clearinghouse index lists
beside each plan and that carries the application procedures and vendor rules the plan only summarises.

Every plan body was opened by regular expression on the extracted text of sections 1, 2, 3 and 4
(`us-xx/policy/acf/liheap-plan/fy2026/N`, 51 scopes of 21 rows): dates of operation, the 2.1 and 4.1
thresholds (`HHS Poverty Guidelines 150.00%`, `State Median Income 60.00%`), the 2.6 minimum and maximum
benefit, the 1.7b nominal amount, the 4.x response hours and the crisis dollar figures. The parsed
values are in the evidence notes so a reader can check them against the plan.""",
    closers=OrderedDict([
        ("LIHEAP-F-USC", "42 U.S.C. chapter 94 subchapter II: no section is in any statute scope (128 files checked). One uscode.house.gov USLM run over title 42 sections 8621 to 8630; the federal queue row (`needs_review`) already lists the ACF statute-and-regulations page as the lead."),
        ("LIHEAP-F-CFR96", "45 CFR 96 subpart H: `extract-ecfr --only-title 45 --only-part 96` (the adapter's compression fix from 2026-09-11 is required); subpart H is ten sections."),
        ("LIHEAP-F-ANN", "HHS poverty guidelines (Federal Register notice) and the ACF LIHEAP-IM state median income table: one `guidance` document each per year from aspe.hhs.gov and the OCS policy-guidance index."),
        ("LIHEAP-ST-05", "Countable income and household definition (51 states REVIEW): the plan records gross/net and the income types as check boxes; the PDF text layer prints both `Yes No` labels with no state. Re-extract the plans reading the AcroForm field values (the OLDC form is a fillable PDF) or take the state policy manual, which states the rule in prose. The same fix closes LIHEAP-ST-03 (30 states) and firms up ST-07/08."),
        ("LIHEAP-ST-09", "Benefit matrix: a plan attachment that the clearinghouse PDF does not include (the extracted text ends at the 'Plan Attachments' list). 37 states have a policy manual on the clearinghouse index that carries the matrix; 13 have none listed and need their agency site inventoried (CA, DC, ID, IL, MA, NC, NM, OK, RI, SC, TX, WA, WY)."),
        ("LIHEAP-ST-18", "State LIHEAP policy or operations manual: the clearinghouse 'State LIHEAP Policy Manuals' links read on 2026-09-11 give 37 documents (PDF, HTML manuals, one adopted rule chapter each for CO, ME, MS); KS (KEESM 13000) and WV (Income Maintenance Manual chapter 26) are already in selected scopes; NY's manual is behind the OTDA block."),
        ("OUTREACH", "New York: otda.ny.gov JavaScript challenge (SSI batch 1, TANF/SNAP queues); the FY2026 plan itself came from the ACF clearinghouse and is PRESENT."),
    ]),
    uncertain="""The check-box problem is the main one: PRESENT for ST-01/07/08/11/12 rests on the narrative
fields and parsed figures, not on the yes/no answers (asset test, renters, subsidized housing, priority
groups), so an encoder must still read the PDF for those. Sections 18 to 20 (certifications, assurances)
are not elements. Whether the plan or the policy manual is the rulebook for benefit determination
differs by state: where the plan says 'see attached matrix' the manual is the only carrier. Tribal and
territory plans (AS, GU, MP, PR extracted) are outside the 50+DC matrix.""",
)

NARRATIVE["medicare"] = dict(
    title="Medicare (federal Parts A, B, D and the state Medicare Savings Programs)",
    method="""The schema takes the eligibility, enrollment, premium and cost-sharing sections of 42 U.S.C.
subchapter XVIII (426, 426-1, 1395c to 1395e, 1395i-2, 1395i-2a, 1395k, 1395l, 1395o to 1395s, 1395v,
1395w-21, 1395w-22, 1395w-101, 1395w-102, 1395w-113, 1395w-114) plus the Medicaid sections that define
the MSP groups (1396a(a)(10)(E), 1396d(p), 1396u-3); 42 CFR 406, 407, 408 and the three 423 subparts that
carry Part D eligibility, premiums and the low-income subsidy; 42 CFR 435 as used by MSP determinations;
one element per chapter of IOM Pub 100-01 and 100-24 and one per publication for 100-02 and 100-04;
the four IOM publications that carry Part D, Part C, NCD and MSP material and were not taken; six POMS
HI subchapters; the four annual CMS figure families; the cms.gov eligibility page; and seven state
elements: MSP coverage groups, income standards, resource test, income methodology, buy-in coverage
group (from Pub 100-24), QMB cost-sharing payment policy, and the current-year standards chart.

State MSP rules were searched in the selected Medicaid eligibility scope of each state (41 from the
2026-09-10 Medicaid run, FL/ID/IL/MI/WV/WY/OR by pointer). The scan is keyword-based but strict: a row
counts for MED-ST-1 only if an MSP group name (QMB, SLMB, QI, QDWI, Medicare Savings Program, buy-in) is
in its heading or appears three or more times in its body, after dropping tables of contents,
glossaries, change logs, bulletins and Q&A pages; MED-ST-2/3/4/6/7 require the qualifying text (an
FPL percentage, a resource limit or no-resource-test statement, a disregard, a cost-sharing statement,
a 2025/2026-dated dollar figure) within 250 characters of the group term, and the matched sentence is
written into the evidence note so the reader can judge it without opening the row. Every state-level
PRESENT snippet was then read by the analyst; eight cells where the first hit was wrong (LA and UT income
rows, IL/MS/RI non-MSP disregards, NC's Medicaid deductible, MI's code table) or a better carrier existed
(IN disregards) are corrected through the `MED_OVERRIDE` table in the builder, so the correction is
reproducible.""",
    closers=OrderedDict([
        ("MED-F-USC", "42 U.S.C. subchapter XVIII: only 426 is held. Seventeen sections from uscode.house.gov (same USLM adapter as the held Title 42 scopes) close the statute layer; 1396u-3 (QI) rides along."),
        ("MED-F-CFR", "42 CFR 406, 407, 408 and 423 subparts B, D, P: none is in the corpus. Four `extract-ecfr` runs (423 is a large part; the subpart filter or a whole-part take both work)."),
        ("MED-F-IOM", "IOM Pub 100-18 (Prescription Drug Benefit Manual, whole-manual PDF: needs a heading proof for the single file), Pub 100-16 (Managed Care, 15 chapters), Pub 100-03 and 100-05: the chapter-PDF generator transfers; each publication must be proven separately as the 100-02/100-04 run did."),
        ("MED-F-POMS", "POMS part HI (chapter list category 06): the SI extractor and index parser apply unchanged; HI 00801/00805/00815/01001/01101/03001 are the six subchapters an encoder needs."),
        ("MED-F-ANN", "Annual Part A/B premium and deductible notices (CMS-8xxx-N in the Federal Register), the Part D parameters announcement, the LIS/MSP resource memo and the HHS poverty guidelines: one `guidance` document per year each."),
        ("MED-ST-7", "Current-year MSP standards chart (26 states REVIEW): the manual states the percentages but the dollar table is a separate annual standards document (for example CT program standards, KY MS 4455 scale, MO Appendix J is held but undated for MSP, NH MAM 601 tables). Take the standards document as a `guidance` scope per state per year."),
        ("MED-ST-2/3", "GA, ID, MN, OH state the income limit by reference (to 1396d(p) or a 'QMB income limit'); AZ, DC, DE, HI, NJ, SD, VT do not state the resource rule near the group term. These need a reader to open the coverage-group rule, or the standards chart above."),
        ("OUTREACH/REVIEW", "AL (medicaid.alabama.gov TLS timeout), CA (DHCS Imperva 403), NE (rules.nebraska.gov 403 on 2026-09-11): agency outreach. OR: OAR 461 / 410-200-0435 region on OARD (HTTP 200). WY: EOM on Google Sites needs a rendering fetch."),
    ]),
    uncertain="""Subchapter XVIII was reduced to household-facing sections; payment-system sections (1395ww and
similar) are out of scope. Part C is represented by two statute sections and Pub 100-16 only. The state
scan finds the carrier row and quotes it, but PRESENT for MED-ST-3 often means the manual states that
a resource test exists (or does not) with the figure elsewhere; MED-ST-7 PRESENT means a dated dollar
figure sits next to a group term, which a few pages satisfy with a related figure (NC MA-3315 quotes the
2026 IRMAA threshold). State MSP expansions above the federal floor (CT 211% FPL, DC 300%, ME 185%,
MA 210%, VT 202%, WA 110% QMB) are visible in the evidence and are exactly the state-set values
PolicyEngine's single federal parameter set does not carry.""",
)


def write_program(prog):
    rows, schema, names = load(prog)
    n = NARRATIVE[prog]
    gtable, gitems = gaps(rows, names)
    fed = Counter(r["status"] for r in rows if r["jurisdiction"] == "us")
    st = Counter(r["status"] for r in rows if r["level"] == "state" and r["jurisdiction"] != "us")
    n_fed = sum(1 for e in schema["elements"] if e["level"] == "federal")
    n_st = schema["element_count"] - n_fed
    out = [f"# {n['title']}: needs-driven closure check", "",
           f"Corpus as selected on 2026-09-11 (draft union selector plus the three 2026-09-11 federal scopes); checked 2026-09-12. "
           f"Schema: `{prog}-schema.yaml` ({schema['element_count']} elements: {n_fed} federal, {n_st} state). Matrix: `{prog}-matrix.csv` "
           f"({len(rows)} cells = 52 jurisdictions x {schema['element_count']} elements, one row each). Builder: `build_ssi_liheap_medicare_matrices.py`; "
           f"verifier: `verify_matrices.py` (re-opens every PRESENT cell: 0 failures).", "",
           "## Method", "", n["method"], "",
           "## Cells by status", "", cell_counts(rows), "",
           f"Federal elements are checked once and inherited by the 51 states (`evidence_note` = `inherited from federal`); the federal row alone: "
           + ", ".join(f"{s} {fed.get(s, 0)}" for s in STATUSES if fed.get(s)) + ". State-level cells (51 x " + str(n_st) + "): "
           + ", ".join(f"{s} {st.get(s, 0)}" for s in STATUSES if st.get(s)) + ".", "",
           "## Federal roll-up by document family", "", federal_rollup(rows, schema), "",
           "## Per-jurisdiction roll-up (state-level elements)", "", state_rollup(rows), "",
           "## Top gaps by how many states share them", "", gtable, "",
           "## What would close each class", ""]
    for k, v in n["closers"].items():
        out.append(f"- **{k}**: {v}")
    out += ["", "## Elements beyond PolicyEngine", "", pe_section(schema), "",
            "## Where the schema is uncertain", "", n["uncertain"], "",
            "## Searches run and timing", "",
            "- Statute scopes: every `us/statute/*.jsonl` (128 files) scanned for citation paths under 42/1383*, 42/1395*, 42/1396a, 42/1396d, 42/1396u-3, 42/862[1-9], 42/8630; regulation scopes for 42/406, 42/407, 42/408, 42/423, 45/96; the selector JSON for scope membership.",
            "- POMS, IOM and eCFR inventories: the run notes' index tables (2026-09-10-ssi-poms-si, 2026-09-10-medicare-cms-iom-100-01/-100-24, 2026-09-11-medicare-cms-iom-100-02-100-04, 2026-09-11-federal-cfr-followon-parts).",
            "- State rows: the queue rows in `manifests/*-agent-queue.yaml`, then targeted body searches in each selected scope (regular expressions over heading and body; the cited row's body was opened for every PRESENT cell and re-opened by `verify_matrices.py`).",
            "- PolicyEngine: `policyengine_us/parameters/gov/{ssa/ssi,hhs/liheap,hhs/medicare}` and `gov/states/*` walked 2026-09-11/12; rulespec-us and rulespec-us-{ca,co,ny} grepped for the statute, POMS, CMS and state program paths on 2026-09-12.",
            "- Timing: a first attempt on 2026-09-11 (18:05 to 18:13 EDT) drafted the builder and stopped; this run 2026-09-12 08:37 to about 09:20 EDT, including three build-verify cycles (each build about 60 s, each verify about 60 s) and the manual re-grading of the state rows after reading the evidence dumps.",
            ""]
    (HERE / f"{prog}.md").write_text("\n".join(out))
    return schema["element_count"], len(rows), Counter(r["status"] for r in rows), gitems[:5], schema["policyengine_cross_check"]["not_modeled_count"]


def write_readme(summary):
    p = HERE / "README.md"
    existing = p.read_text() if p.exists() else ""
    lines = []
    if "needs-closure-2026-09-11" not in existing:
        lines += ["# Needs-driven closure check, 2026-09-11 corpus", "",
                  "Per program: `<program>-schema.yaml` (the law-derived needs schema), `<program>-matrix.csv` (one row per jurisdiction x element: "
                  "jurisdiction, element, level, family, status, scope_version, citation_path, pe_modeled, evidence_note) and `<program>.md` (method, roll-ups, gaps, closers, elements beyond PolicyEngine).", ""]
    else:
        lines.append(existing.rstrip() + "\n")
    lines += ["## SSI, LIHEAP, Medicare (branch analysis/needs-closure-ssi-liheap-medicare)", "",
              table(["program", "elements", "cells", "PRESENT", "EXTRACTABLE", "ABSENT", "OUTREACH", "REVIEW", "PE does not model"],
                    [[prog, n_el, n_cells] + [c.get(s, 0) for s in STATUSES] + [pe_no] for prog, (n_el, n_cells, c, _, pe_no) in summary.items()]),
              "", "Built by `build_ssi_liheap_medicare_matrices.py` (reads `data/corpus` read-only), checked by `verify_matrices.py`, reports by `write_reports.py`.", ""]
    p.write_text("\n".join(lines))


if __name__ == "__main__":
    summary = OrderedDict()
    for prog in ("ssi", "liheap", "medicare"):
        summary[prog] = write_program(prog)
        n_el, n_cells, c, top, pe_no = summary[prog]
        print(prog, n_el, n_cells, dict(c), "PE-no", pe_no)
        for (e, s), js in top:
            print("   ", e, s, len(js))
    write_readme(summary)
