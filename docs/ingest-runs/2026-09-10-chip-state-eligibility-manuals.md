# CHIP state eligibility manuals, handbook chapters and adopted rules

Date: 2026-09-10
Program: CHIP (board Year 1 list; `manifests/chip-agent-queue.yaml`)
Branch: `discovery/ingest-chip`

Timing: started_at 2026-09-10T16:35:04+0200, finished_at 2026-09-10T17:08:27+0200, agent wall time 33 min 23 s.
GitNexus impact analysis was not run: the GitNexus MCP tools were not available in this
session. No existing function was modified; the only code added is the generator script
`scripts/build_chip_state_eligibility_manifests.py` (manifest/queue writer, no adapter).

Source family: the state agency's own CHIP eligibility manual, handbook chapter, or adopted
eligibility rule for the separate CHIP program (or the combined Medicaid eligibility manual
chapters that govern CHIP). Each source was confirmed from the publisher's own index page,
never from the lead list. Scope: document_class `manual` (or `regulation` where the primary
document is an adopted rule), version `2026-09-10-chip-state-eligibility-manual`, citation
paths `us-xx/manual/<agency>/chip/<section>` (regulation scopes follow the jurisdiction's
existing regulation citation convention).

## Result

| Jurisdiction | Status | Scope | Provisions | Extract s |
|---|---|---|---|---|
| us | done (already in corpus) | - | - | - |
| us-al | agent_ready | us-al/manual | 6 | 3 |
| us-ct | agent_ready | us-ct/manual | 4 | 4 |
| us-de | agent_ready | us-de/regulation | 4 | 2 |
| us-fl | blocked_primary_source | - | - | - |
| us-ga | agent_ready | us-ga/manual | 8 | 2 |
| us-ia | agent_ready | us-ia/manual | 94 | 2 |
| us-id | agent_ready | us-id/regulation | 75 | 4 |
| us-il | done (already in corpus) | - | - | - |
| us-in | agent_ready | us-in/manual | 76 | 7 |
| us-ks | blocked_primary_source | - | - | - |
| us-la | blocked_primary_source | - | - | - |
| us-ma | agent_ready | us-ma/regulation | 23 | 2 |
| us-mi | done (already in corpus) | - | - | - |
| us-mo | agent_ready | us-mo/manual | 13 | 3 |
| us-ny | agent_ready | us-ny/manual | 2 | 1 |
| us-tx | agent_ready | us-tx/manual | 82 | 1 |
| us-wi | blocked_primary_source | - | - | - |

Attempted 18/18 rows; extracted 11 jurisdictions (17 documents, 387 provisions); blocked 4;
done-already 3. Coverage `complete: true` for every extracted scope, 0 missing, 0 extra,
0 duplicate citation paths (duplicates re-verified directly on the provision JSONL).
Smoke runs (scratch base): GA (8 provisions), TX (first pass 162 provisions with two duplicate
labels d-210/d-1060, fixed by restricting the pattern to the export's comma-form page
headings; second pass 82 provisions, 0 duplicates). Extract seconds are wall seconds of the
final `extract-official-documents` command per jurisdiction (MA and CT were re-run once
after a pattern / source swap: first runs 3 s and 3 s).

Artifacts (unsigned, uncommitted, awaiting controller; `data/corpus` lives in the main
checkout):

- `data/corpus/sources/us-xx/<class>/2026-09-10-chip-state-eligibility-manual/official-documents/*`
- `data/corpus/inventory/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.json`
- `data/corpus/provisions/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.jsonl`
- `data/corpus/coverage/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.json`

TLS: no verification was disabled and no intermediate had to be added (`data/certs` unchanged).
Hosts that 403 plain clients (mass.gov, portal.ct.gov, alabamapublichealth.gov, pamms,
health.ny.gov, dssmanuals.mo.gov, fhb.hhs.texas.gov) use the existing manifest
`request: browser_impersonation: true` fallback.

Rebuild:

```bash
uv run python scripts/build_chip_state_eligibility_manifests.py
for m in manifests/us-*-chip-state-eligibility-manual.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-10-chip-state-eligibility-manual --manifest $m --source-as-of 2026-09-10
done
```

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped. All 10 failures are `FileNotFoundError` on `data/corpus`
artifacts (be statute promotion inputs, us-ny TANF/SNAP, us-ak/us-ct/us-mi/us-mt/us-nd SNAP
manual inventories) that are absent from this sparse worktree; none touch CHIP files.

## Federal row (`us`)

Index: https://www.medicaid.gov/chip (403 to plain clients; read through browser
impersonation), 15 sections: State Program Information, CHIP State Plan Amendments,
Benefits, CCTAG, Cost Sharing, Eligibility & Enrollment (Waiting Periods, Continuous
Eligibility, Enrollment Strategies, Substitution Strategies), Financing, Managed Care,
Quality & Performance, Reports & Evaluations, Guidance & Regulations. Already in the corpus:
CMS CHIP SPAs and the children coverage map (`us/policy`), the Medicaid/CHIP/BHP eligibility
levels table (`us/form`), Title XXI (`us/statute`, run note 2026-06-26), and 42 CFR part 457
(171 provisions, subparts A-L, in `us/regulation` version
`2026-07-13-recovery-r2026-07-17-dedup`, coverage complete). Nothing federal and primary
remains on the index that is not an explanatory page or a broad SHO/CIB guidance family;
nothing taken, row marked `done`.

## Per-jurisdiction index inventories

- **us-al** ADPH ALL Kids index https://www.alabamapublichealth.gov/allkids/index.html: 17
  program pages (home, income guidelines, pay premium, benefits booklet, standards of care,
  how to apply, apply, enrolled families, order materials, FAQ, Spanish, enrollment data,
  links, research, reports, other insurance, about). Taken 2: Income Guidelines (effective
  2/1/2026) and Premiums and Copays. Not found: an ALL Kids eligibility manual, and the
  Alabama Administrative Code chapter for ALL Kids (LSA admincode chapter API: 420-10-1 is
  newborn screening, 420-10-2 is WIC, 420-10-3..7 404; no chapter-list API; ADPH's own
  Laws and Regulations page does not list ALL Kids).
- **us-ct** DSS healthcare-coverage index
  https://portal.ct.gov/dss/find-benefits-and-support/healthcare-coverage: 9 HUSKY
  documents (prescreener, how to qualify, member/provider info, benefits overview, advisory
  committee, HUSKY Health landing, non-citizen children coverage, H.R.1 changes). Taken 2:
  DSS knowledge-base article "What is HUSKY B?" and the March 1, 2026 HUSKY Health monthly
  income chart PDF. Not taken: the Uniform Policy Manual (129 list pages of .doc/.docx; no
  HUSKY B chapter in the UPM0/UPM2/UPM8 listings), the 2020 huskymonthlyincomechart.pdf, and
  the eRegulations DSS document surfaced by search (provider participation, 17b-262-523 ff.).
- **us-de** Delaware Administrative Code Title 16 (regulations.delaware.gov AdminCode title
  API): one CHIP regulation, DSSM 18000 Delaware Healthy Children Program (regulationId
  1054, pdfId b78ac36e-3af7-4d1a-9503-16927de57397). Taken 1 (3-page PDF, page-level like the
  existing us-de-dssm-13000 scope). dhss.delaware.gov presents a self-signed certificate in
  its chain and was not used.
- **us-fl** floridakidcare.org (Florida Healthy Kids Corporation): 14 consumer pages; no
  manual or rule. AHCA https://ahca.myflorida.com/medicaid/florida-kidcare: HTTP 403
  Cloudflare "Attention Required!" to plain, curl and chrome120 clients. Blocked, 0 taken.
- **us-ga** DFCS Medicaid Policy Manual index https://pamms.dhs.ga.gov/dfcs/medicaid/: 241
  numbered sections. Taken 1: 2194 PeachCare for Kids (MT 79, effective May 2026). Not
  taken: the Family Medicaid sections it cross-references (2160, 2182, 2215, 2610, 2650,
  Appendix A2).
- **us-ia** Iowa HHS Income Maintenance manuals index
  https://hhs.iowa.gov/about/policy-manuals/income-maintenance: 58 Employees' Manual
  chapter/appendix PDFs (Titles 1, 4, 5, 6, 8, 13, 23, 24 plus omnibus files). Taken 1: 5-E
  Healthy and Well Kids in Iowa (hawk-i), 93 pages, page-level. Not taken: Title 8 Medicaid
  chapters.
- **us-id** IDHW CHIP page (2 policy links: income guidelines node/623, notices and proposed
  rules) -> adopted rule IDAPA 16.03.01 Eligibility for Health Care Assistance for Families
  and Children at https://adminrules.idaho.gov/rules/current/16/160301.pdf (Office of the
  Administrative Rules Coordinator; redirects to files.dfm.idaho.gov; the "Current Rules"
  listing page is script-rendered, so its document count could not be read). Taken 1,
  numbered sections (same shape as us-id-aabd-rules.yaml).
- **us-il** HFS All Kids index https://hfs.illinois.gov/medicalprograms/allkids.html: 14
  program pages, no policy manual link. Done by pointer to the IDHS Cash, SNAP and Medical
  Manual already in the corpus (12,450 provisions, `us-il/manual/dhs/csmm/*`).
- **us-in** IHCPPM index
  https://www.in.gov/fssa/ompp/forms-documents-and-tools/medicaid-eligibility-policy-manual/:
  24 chapter PDFs plus all-chapters PDF and transmittals. Taken 2: Chapter 1600 Categories of
  Assistance (CHIP = 1620.72 Children's Health Plan / Hoosier Healthwise Package C) and
  Chapter 3000 Eligibility Standards. Chapter 5000 is already in the corpus (us-in-ssp-sapn).
- **us-ks** https://www.kancare.ks.gov/policies-and-reports/eligibility-policy (KFMAM):
  HTTP 403 "Access Denied" for the index, the KFMAM page and the site root, to plain, curl and
  chrome120 clients; www.kdhe.ks.gov also 403. Blocked, 0 taken. The existing us-ks KEESM
  scope is SNAP/TANF and has no CHIP chapter.
- **us-la** https://ldh.la.gov/page/medicaid-eligibility-manual: HTTP 403 Cloudflare
  "Attention Required!" for the page and the site root, to plain, curl and chrome120 clients.
  Blocked, 0 taken.
- **us-ma** Mass.gov 130 CMR member regulations (https://www.mass.gov/law-library/130-cmr):
  taken 2, the official PDF downloads of 130 CMR 505.000 Coverage Types (E.L. 254, rev.
  2026-02-13; 8 sections) and 130 CMR 506.000 Financial Requirements (E.L. 250, rev.
  2026-01-30; 13 sections). The lead list's law.cornell.edu mirror was not used.
- **us-mi** Bridges Eligibility Manual TOC (BEM 000, 196 documents in the existing
  us-mi-bridges-manual.yaml). Done by pointer: BEM 130 MICHILD and BEM 131 Healthy Kids are
  already ingested (`us-mi/manual/mdhhs/bridges/bem/130`, three page provisions).
- **us-mo** Family MO HealthNet (MAGI) Manual index
  https://dssmanuals.mo.gov/family-mo-healthnet-magi/: 17 numbered sections (1800-1890) and
  11 appendices. The CHIP section 1840.000.00 is password-protected on the publisher's site,
  as are the other numbered sections. Taken 2: Appendix A (MAGI income limits with 5% FPL and
  CHIP premium amounts, 7/1/2026-3/31/2027) and Appendix E (CHIP Premium Chart effective
  7/1/2026), page-level.
- **us-ny** NYSDOH Child Health Plus index
  https://www.health.ny.gov/health_care/child_health_plus/: 8 program pages. Taken 1:
  Eligibility and Cost (2026 FPL tables effective 2/17/2026). NYSDOH publishes no CHPlus
  eligibility manual; 10 NYCRR is vendor-hosted.
- **us-tx** Texas Works Handbook Part D index
  https://fhb.hhs.texas.gov/handbooks/texas-works-handbook/part-d-childrens-health-insurance-program:
  23 top-level sections D-100 to D-2400 (www.hhs.texas.gov handbook URLs now 301 to
  fhb.hhs.texas.gov). Taken 1: the publisher's printer-friendly export of Part D
  (https://fhb.hhs.texas.gov/book/export/html/75506, one HTML document), split into 81
  handbook pages by the export's comma-form headings "D-NNN, Title".
- **us-wi** https://www.emhandbooks.wisconsin.gov/bcplus/bcplus.htm (BadgerCare Plus
  Eligibility Handbook): host 165.189.157.19 did not accept TCP connections on 443 or 80
  during the run (curl (28) connection timeout on four attempts between 16:45 and 17:02
  local; WebFetch ECONNREFUSED); www.dhs.wisconsin.gov answered normally. Blocked, 0 taken.
  The same host served the FoodShare handbook in July 2026, so this may be transient.

## Reviewer judgments

1. **Agency eligibility pages as `manual` (AL, CT, NY).** These states publish no CHIP
   eligibility manual and their adopted rule was not reachable on an official host, so the
   agency's own eligibility/premium pages were taken under document_class `manual` with
   document_subtype `agency_eligibility_policy_page` / `agency_income_standards_chart_pdf`.
   A reviewer may prefer a different class or to drop them.
2. **Georgia citation path** follows the work order (`us-ga/manual/dfcs/chip/2194`) rather
   than the existing `us-ga/manual/dfcs/medicaid/NNNN` convention of us-ga-ssp-manual.yaml.
3. **Texas granularity.** The export repeats some subsection headings (D-210, D-1060) and the
   HTML labeled extractor cannot merge repeats without changing existing code, so sections
   are the export's comma-form page headings only; subsection headings such as D-121 or
   D—231.1 remain inside the page bodies. 24 provisions are container pages with empty bodies
   (D-100, D-200, ... which only list subpages). The existing us-tx-manuals.yaml scope still
   carries D-1820 under `us-tx/manual/hhs/texas-works-handbook/d-1820-enrollment-fees`; it
   is superseded in content but was not removed.
4. **Indiana chapter selection.** Only 1600 and 3000 were taken; 2800 Income and 3400
   Budgeting also apply to CHIP.
5. **Iowa** 5-E carries a 2010 revision date on the publisher's current index; 441 IAC
   chapter 86 (Iowa Legislature) is a candidate follow-up.
6. **Missouri** manual section 1840.000.00 is password-protected; only the public appendices
   were taken (no workaround attempted). Reviewer may want the row as partially blocked.
7. **Michigan/Illinois done-by-pointer.** MI: the BEM 130 document root record has an empty
   body (text is on its three page children). IL: All Kids is governed by the ingested IDHS
   combined manual; no separate CHIP manual exists.
8. **Delaware, Idaho, Massachusetts as `regulation`** with the jurisdictions' existing
   regulation citation conventions instead of the `manual/.../chip/` path.
9. **Serving overlap.** Every new `manual` scope shares its `(jurisdiction, manual)` pair
   with an existing SNAP/other manual scope; the controller must include both versions in
   the release membership when activating.
10. **Wisconsin** should be retried before the block is treated as durable.

Remaining (controller): `sign-ingest-manifest` per scope, immutable release selector,
`publish_corpus.py --dry-run` then publish (Supabase, R2). Not done here: push, sign,
publish, Supabase load.
