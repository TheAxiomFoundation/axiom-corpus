#!/usr/bin/env python3
# ruff: noqa: E501
"""Wave 8, group `benefits`: record the 2026-10-20 findings on the WIC, CHIP and SSI queue rows.

    uv run python scripts/update_w8_benefits_queue_rows.py

Seven rows are rewritten in place (run note docs/ingest-runs/2026-10-20-w8-benefits-gaps.md):

* `wic-agent-queue.yaml` us-ks stays `blocked_primary_source` with the third-date finding: the
  KDHE Document Center folder that holds the Policy & Procedure Manual serves no document list,
  and the only list endpoint is robots-disallowed.
* `chip-agent-queue.yaml` us-mt becomes `done` on the ARM 37.79 scope taken with this
  repository's committed Montana adapter, and us-wy becomes `done` on the Kid Care CHIP section
  of the Wyoming EOM, which the corpus already holds.
* `ssi-agent-queue.yaml` us-wy becomes `done` on the State Supplemental Payments section of the
  same held Wyoming scope, and us-as, us-gu, us-pr and us-vi become `done` on the POMS SI 01415
  finding, the resolution the us-mp row already uses.

Each row is re-dumped as text in place so the rest of every queue stays byte-identical (other
agents edit the same files); `status_counts` is recomputed from every row. A rerun is idempotent.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
RUN_NOTE = "docs/ingest-runs/2026-10-20-w8-benefits-gaps.md"
MARK = "2026-10-20 (w8 benefits run"

WY_EOM_SCOPE = {
    "jurisdiction": "us-wy",
    "document_class": "manual",
    "version": "2026-09-15-medicaid-eligibility-manual-closure",
}
WY_EOM_MANIFEST = "manifests/us-wy-medicaid-eligibility-manual.yaml"
POMS_MANIFEST = "manifests/us-ssa-poms-si-2026-09-10.yaml"
POMS_SCOPE = {"jurisdiction": "us", "document_class": "manual", "version": "2026-09-10-ssi-poms-si"}
SI_01415_INDEX = "https://secure.ssa.gov/apps10/poms.nsf/subchapterlist!openview&restricttocategory=05014"

KS_NOTE = (
    "Re-probed 2026-10-20 (w8 benefits run, " + RUN_NOTE + ") with curl_cffi chrome120 browser impersonation, the "
    "route the official-document fetcher offers as request.browser_impersonation: www.kdhe.ks.gov answers HTTP 200 to "
    "that client (/1149/Information-for-WIC-Local-Agencies redirects to /1149/For-Local-WIC-Agencies, 124,981 bytes of "
    "real page). Every response was judged by its body, not its status line. The access gate is narrower than the "
    "queue recorded but still needs that profile: the plain extractor client and the extractor's own "
    "browser-user-agent fallback (the 403/404/406 retry) both answer HTTP 403 with a Cloudflare challenge body of "
    "5,490 to 5,893 bytes (titles 'Attention Required! | Cloudflare' and 'Just a moment...'), because a Chrome user "
    "agent on a non-Chrome TLS fingerprint is itself a bot signal; a future assignment on this host must set "
    "request.browser_impersonation and must not rely on the built-in fallback. The gate is not why the row stays "
    "blocked. The block is the index: "
    "DocumentCenter/Index/903 (window.folderName 'Policy & Procedure Manual', window.parentId 898 'Information for WIC "
    "Local Agencies') answers HTTP 200 (103,708 bytes) as the CivicEngage React shell with zero DocumentCenter/View "
    "links, and folder 898 likewise; the document list comes only from the admin-area AJAX binding endpoint, which "
    "www.kdhe.ks.gov/robots.txt disallows (Disallow: /admin), so it was not requested. www.kdhe.ks.gov/sitemap.xml "
    "(234,656 bytes) lists page URLs and one /DocumentCenter home entry and no document URLs. Every one of the 31 WIC, "
    "nutrition and policy pages in that sitemap was read: 583 distinct DocumentCenter/View documents in total and not "
    "one manual-chapter document. Same finding on three dates (2026-09-10, 2026-09-13, 2026-10-20): the Policy & "
    "Procedure Manual is on no KDHE static index, and nothing was taken. New pointer for a future assignment: "
    "/1206/Policy-Information-Updates is a KDHE-own static index listing 63 WIC documents (Policy Memos P-Memo FFY 2021 "
    "to FFY 2025 and the monthly KS WIC Update slides and supplements) as plain DocumentCenter/View links; that is a "
    "guidance family, not this row's manual target, and it was not taken."
)
KS_FAMILIES = (
    "Policy & Procedure Manual (DocumentCenter folder 903): 0 found / 0 taken (React shell, no document list; the "
    "admin-area binding endpoint is robots-disallowed). Sitemap sweep 2026-10-20 of all 31 WIC, nutrition and policy "
    "pages: 583 DocumentCenter/View documents found / 0 taken, 0 of them manual chapters. Policy memoranda "
    "(/1206/Policy-Information-Updates, KDHE-own static index): 63 found / 0 taken (guidance family, out of this row's "
    "manual scope)."
)

MT_NOTE = (
    "Resolved 2026-10-20 (w8 benefits run, " + RUN_NOTE + "): not blocked. The gateway URL "
    "rules.mt.gov/gateway/ChapterHome.asp?Chapter=37.79 still redirects to https://rules.mt.gov (HTTP 200, 894 bytes) "
    "and serves only the Esper policy-library-public single-page-application shell, whose bundle names "
    "app.public.staging.esper.com; that URL carries no rule text and was not emulated. The chapter is taken instead "
    "with this repository's committed Montana adapter (extract-montana-admin-rules), which reads the publisher's own "
    "policy-library-public index at https://rules.mt.gov/api/policy-library-public/collections and is already the "
    "committed route for ARM title 42 chapter 42.15 and for ARM 37.78 and 37.80. ARM chapter 37.79 HEALTHY MONTANA "
    "KIDS (HMK): the index lists 42 rules in 6 subchapters; the 30 currently effective rules were taken as "
    "us-mt/regulation/2026-10-20-w8-chip-hmk-title-37-section-37-79 (39 provision rows: 30 rule rows plus 9 container "
    "rows), coverage complete with 0 missing, 0 extra and 0 duplicate citation paths and every rule body non-empty; the "
    "12 repealed or otherwise not-effective entries were inventoried and not taken. The scope's citation paths collide "
    "with no other us-mt provisions scope except the two shared ancestors us-mt/regulation and "
    "us-mt/regulation/title-37, which every committed ARM scope shares. TLS verified; no mirror, repost, proxy or "
    "archived copy. Artifacts are unsigned and uncommitted; the controller signs and selects."
)
MT_FAMILIES = {
    "subchapter_37-79-1 General Provisions": {"found": 11, "taken": 11},
    "subchapter_37-79-2 Eligibility": {"found": 6, "taken": 5},
    "subchapter_37-79-3 Benefits": {"found": 15, "taken": 5},
    "subchapter_37-79-5 Enrollment Provisions": {"found": 4, "taken": 3},
    "subchapter_37-79-6 Services and Provider Requirements": {"found": 5, "taken": 5},
    "subchapter_37-79-8 Hearing and Appeal Procedures": {"found": 1, "taken": 1},
}

WY_RULES_FINDING = (
    "rules.wyo.gov is confirmed unusable as an index: Search.aspx?mode=1&AgencyId=48 answers HTTP 200 (33,580 bytes) "
    "but its agency and program lists and its rule text come from an undocumented vendor endpoint set "
    "(AjaxHandler.ashx?handler=GetAllAgencies / GetAgencies / GetAgencyPrograms / Search / Search_GetProgramRules / "
    "GetRuleVersionHTML / GetRuleVersionHistory), and the one GET-addressable document path, "
    "Report.aspx?token=<server-minted token>, needs a token the application mints (the token on Agencies.aspx returns a "
    "3-page 'Agency Listing' PDF, 27,811 bytes). Not emulated."
)
WY_EOM_FINDING = (
    "The Wyoming Department of Health publishes the governing text itself in the Eligibility Online Manual at "
    "ecom.wyo.gov, whose navigation now carries 128 sections in the served HTML (107 at the 2026-09-11 probe), and the "
    "2026-09-11 finding of a script-rendered Google Drive embed with no document URL is obsolete: the body served to "
    "the plain extractor client (HTTP 200, 233,949 bytes, no challenge or stub signature) carries the policy text in "
    "div.UtePc, so no browser impersonation is needed here."
)
WY_HELD = (
    "Re-extraction was refused because it would duplicate those citation paths. Verified 2026-10-20 against the live "
    "page: the corpus text is a strict subset of the text served today, the only live tokens absent from the corpus "
    "being the section labels and the Purpose sentence (recorded as a finding in the run note). Nothing new was "
    "fetched into the corpus."
)

WY_CHIP_NOTE = (
    "Resolved 2026-10-20 (w8 benefits run, " + RUN_NOTE + "): not blocked, and no new extraction was needed. "
    + WY_RULES_FINDING
    + " "
    + WY_EOM_FINDING
    + " Section M1803 Kid Care CHIP is already in the corpus as "
    "us-wy/manual/wdh/medicaid/m1800-other-programs-m1803-kid-care-chip in the locked scope "
    "us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure (" + WY_EOM_MANIFEST + ", 121 documents), with four "
    "non-empty block rows carrying the POL M1803 eligibility requirements, the 42 CFR 435.229 and Social Security Act "
    "references, the clarifying information and the worker responsibilities. " + WY_HELD
)
WY_CHIP_FAMILIES = (
    "Wyoming Department of Health EOM sections (ecom.wyo.gov navigation, 2026-10-20): 128 found / 1 taken (M1803 Kid "
    "Care CHIP, already held in us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure); the other 127 sections "
    "are other-program families and out of this row's scope. Secretary of State rules site (rules.wyo.gov agency 048): "
    "0 found / 0 taken, no publisher-served index."
)

WY_SSI_NOTE = (
    "Resolved 2026-10-20 (w8 benefits run, " + RUN_NOTE + "): not blocked, and no new extraction was needed. "
    + WY_EOM_FINDING
    + " Section M1804 State Supplemental Payments is already in the corpus as "
    "us-wy/manual/wdh/medicaid/m1800-other-programs-m1804-state-supplemental-payments in the locked scope "
    "us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure (" + WY_EOM_MANIFEST + ", 121 documents), with four "
    "non-empty block rows carrying the POL M1804 policy (the $20.00 monthly supplement, the sole-SSI-income and "
    "Wyoming-residence criteria), the 20 CFR 416.2001, W.S. 42-2-103 and Senate Enrolled Act 43 (SF002) references, the "
    "clarifying information and the worker responsibilities including the SDX living-arrangement and record-identification "
    "code tables. " + WY_HELD + " " + WY_RULES_FINDING + " The SSA regional description stays in the federal family at "
    "us/manual/ssa/poms/si/01415.010 (Wyoming row S/S)."
)
WY_SSI_FAMILIES = (
    "Wyoming Department of Health EOM sections (ecom.wyo.gov navigation, 2026-10-20): 128 found / 1 taken (M1804 State "
    "Supplemental Payments, already held in us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure); the other 127 "
    "sections are other-program families and out of this row's scope. DFS index: no SSI supplement family."
)

TERRITORY_ADMIN = {
    "us-as": "American Samoa operates no adult assistance program under titles I, X, XIV or XVI",
    "us-gu": "Guam administers Old Age Assistance, Aid to the Blind and Aid to the Permanently and Totally Disabled through DPHSS under titles I, X and XIV",
    "us-pr": "Puerto Rico administers Aid to the Aged, Blind and Disabled under titles I, X and XIV",
    "us-vi": "the Virgin Islands Department of Human Services administers Old Age Assistance, Aid to the Blind and Aid to the Disabled under titles I, X and XIV",
}


def territory_note(jurisdiction: str) -> str:
    return (
        "Done 2026-10-20 (w8 benefits run, " + RUN_NOTE + "): confirmed on the publisher's own index that the "
        "jurisdiction pays no state supplement at all, optional or mandatory. The POMS SI 014 chapter list ("
        + SI_01415_INDEX + ") lists 32 SI 01415 sections and names no territory, and the SI 01415.010 state table "
        "(fetched 2026-10-20, HTTP 200, 79,638 bytes) carries exactly 51 jurisdiction rows, the 50 States and the "
        "District of Columbia, with no American Samoa, Guam, Puerto Rico, Virgin Islands or Northern Mariana Islands "
        "row. With 42 U.S.C. 1382c(e) and POMS SI 00501.410 / SI 00501.415 that settles the row: there is no optional "
        "state supplement and no territory supplement document to ingest ("
        + TERRITORY_ADMIN[jurisdiction]
        + ", a separate family). Recorded done with that POMS finding and a pointer to us/manual/ssa/poms/si/01415.010 "
        "(version 2026-09-10-ssi-poms-si), the resolution the us-mp row already uses. Nothing was fetched."
    )


def territory_families(jurisdiction: str) -> str:
    return (
        "POMS SI 01415.010 Administration of State Supplementary Programs (state table): 1 found / 1 taken in the "
        "federal family; the table carries no " + {"us-as": "American Samoa", "us-gu": "Guam", "us-pr": "Puerto Rico", "us-vi": "Virgin Islands"}[jurisdiction]
        + " row and SI 01415 holds no territory-specific section; POMS SI 00501.410 / SI 00501.415 keep the "
        "jurisdiction outside the title XVI definition of the United States; no territory document family exists"
    )


def _row_span(lines: list[str], jurisdiction: str, *, without_family: bool = False) -> tuple[int, int]:
    """Line span [start, end) of a `states:` row, by jurisdiction."""
    starts = [i for i, line in enumerate(lines) if line == f"- jurisdiction: {jurisdiction}"]
    if not starts:
        raise SystemExit(f"row not found: {jurisdiction}")
    spans = []
    for start in starts:
        end = start + 1
        while end < len(lines) and not lines[end].startswith("- ") and not (
            lines[end] and not lines[end][0].isspace() and lines[end].endswith(":")
        ):
            end += 1
        spans.append((start, end))
    if without_family:
        spans = [s for s in spans if not any(line.startswith("  family:") for line in lines[s[0]:s[1]])]
    if len(spans) != 1:
        raise SystemExit(f"row is not unique: {jurisdiction} ({len(spans)} candidates)")
    return spans[0]


def _render(row: dict) -> list[str]:
    text = yaml.safe_dump(row, sort_keys=False, width=120, allow_unicode=True)
    out = []
    for index, line in enumerate(text.rstrip("\n").split("\n")):
        out.append(("- " + line) if index == 0 else ("  " + line))
    return out


# The four territory rows were written while the queue schema had no not-applicable status, so their
# notes open by explaining the blocked_primary_source stand-in. They are `done` now, and
# `program_applicability: not_applicable` carries that fact, so the stand-in clause is dropped.
STALE_STATUS_CLAUSE = re.compile(
    r"^Not applicable \(recorded as blocked_primary_source because the queue schema has no not-applicable status\): "
)


def _apply(path: Path, jurisdiction: str, updates: dict, note: str, *, without_family: bool = False) -> None:
    lines = path.read_text().split("\n")
    start, end = _row_span(lines, jurisdiction, without_family=without_family)
    block = "\n".join(line[2:] if line.startswith("- ") else line[2:] for line in lines[start:end] if line)
    row = yaml.safe_load(block)
    row.update(updates)
    existing = STALE_STATUS_CLAUSE.sub("Not applicable: ", str(row.get("notes") or ""))
    if MARK in existing:
        # A rerun replaces this run's own sentences; `MARK` starts mid-sentence, so cut back to the
        # end of the sentence before it and keep that sentence's full stop.
        kept = existing[: existing.index(MARK)].rsplit(". ", 1)[0].rstrip()
        existing = (kept + ".") if kept else ""
    row["notes"] = (existing.rstrip() + " " + note).strip() if existing else note
    row["run_note"] = RUN_NOTE
    path.write_text("\n".join(lines[:start] + _render(row) + lines[end:]))


def _reconcile(path: Path) -> dict[str, int]:
    text = path.read_text()
    data = yaml.safe_load(text)
    counts = Counter(row.get("queue_status") for row in data.get("states", []))
    ordered = {key: counts[key] for key in sorted(counts)}
    block = "status_counts:\n" + "".join(f"  {key}: {value}\n" for key, value in ordered.items())
    text = re.sub(r"^status_counts:\n(?:  .*\n)+", block, text, count=1, flags=re.M)
    path.write_text(text)
    yaml.safe_load(text)
    return ordered


def main() -> int:
    wic = REPO / "manifests/wic-agent-queue.yaml"
    chip = REPO / "manifests/chip-agent-queue.yaml"
    ssi = REPO / "manifests/ssi-agent-queue.yaml"

    _apply(
        wic,
        "us-ks",
        {
            "queue_status": "blocked_primary_source",
            "source_kind": "official_state_agency_manual_no_static_index",
            "primary_source_url": "https://www.kdhe.ks.gov/1149/For-Local-WIC-Agencies",
            "index_url": "https://www.kdhe.ks.gov/DocumentCenter/Index/903",
            "index_document_count": 0,
            "taken_count": 0,
            "index_families": KS_FAMILIES,
        },
        KS_NOTE,
    )

    _apply(
        chip,
        "us-mt",
        {
            "queue_status": "done",
            "source_kind": "official_state_administrative_rules",
            "primary_source_url": "https://rules.mt.gov/",
            "target_manifest": None,
            "target_scope": {
                "jurisdiction": "us-mt",
                "document_class": "regulation",
                "version": "2026-10-20-w8-chip-hmk-title-37-section-37-79",
            },
            "index_url": "https://rules.mt.gov/api/policy-library-public/collections",
            "index_document_count": 42,
            "taken_count": 30,
            "index_families": MT_FAMILIES,
        },
        MT_NOTE,
        without_family=True,
    )

    _apply(
        chip,
        "us-wy",
        {
            "queue_status": "done",
            "source_kind": "official_state_agency_manual_already_held",
            "primary_source_url": "https://ecom.wyo.gov/m1800-other-programs/m1803-kid-care-chip",
            "target_manifest": WY_EOM_MANIFEST,
            "target_scope": dict(WY_EOM_SCOPE),
            "index_url": "https://ecom.wyo.gov/",
            "index_document_count": 128,
            "taken_count": 1,
            "index_families": WY_CHIP_FAMILIES,
        },
        WY_CHIP_NOTE,
        without_family=True,
    )

    _apply(
        ssi,
        "us-wy",
        {
            "queue_status": "done",
            "source_kind": "official_state_agency_manual_already_held",
            "primary_source_url": "https://ecom.wyo.gov/m1800-other-programs/m1804-state-supplemental-payments",
            "target_manifest": WY_EOM_MANIFEST,
            "target_scope": dict(WY_EOM_SCOPE),
            "index_url": "https://ecom.wyo.gov/",
            "index_document_count": 128,
            "taken_count": 1,
            "index_families": WY_SSI_FAMILIES,
        },
        WY_SSI_NOTE,
    )

    for jurisdiction in ("us-as", "us-gu", "us-pr", "us-vi"):
        _apply(
            ssi,
            jurisdiction,
            {
                "queue_status": "done",
                "source_kind": "ssa_poms_section",
                "target_manifest": POMS_MANIFEST,
                "target_scope": dict(POMS_SCOPE),
                "index_url": SI_01415_INDEX,
                "index_document_count": 1,
                "taken_count": 1,
                "index_families": territory_families(jurisdiction),
                "administration": "N",
            },
            territory_note(jurisdiction),
        )

    for path in (wic, chip, ssi):
        print(f"{path.relative_to(REPO)}: status_counts {_reconcile(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
