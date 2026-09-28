# Territories: the ten board Year 1 programs in PR, GU, VI, AS and MP

Date: 2026-09-11
Programs: LIHEAP, Medicaid, CCDF, CHIP, SSI, TANF, WIC, tax, SNAP (NAP/ASNAP/NAP-CNMI where the
territory runs a block grant instead of SNAP), Medicare
Jurisdictions: Puerto Rico (us-pr), Guam (us-gu), U.S. Virgin Islands (us-vi), American Samoa
(us-as), Northern Mariana Islands (us-mp)
Branch: `discovery/ingest-territories` (sparse worktree `~/axiom-corpus-worktrees/territories`,
cut from `origin/discovery/program-ingestion-union` because `origin/main` did not yet carry the
2026-09-11 hand-off; artifacts written to the main checkout's `data/corpus`).
Agent: started_at 2026-09-11T21:00Z, finished_at 2026-09-11T21:50Z, wall time 50 min.
Network: US exit (Charter Communications, New York; ipinfo checked before the first probe), so
every block below is publisher-side, not geo-restriction.
Impact analysis: not run; the GitNexus MCP tools were not available in this session. No function
in `src/axiom_corpus` was modified and no adapter was added; the only code changes are the
territory tables and territory-only modes added to the ten program generators (see Code).

Discovery first, extraction second: every cell below was resolved from the publisher's own
index (territory agency, or the federal agency's territory page where it hosts the territory's
own submitted plan). No republication, mirror, proxy or archived copy was used; no TLS
verification was disabled; nothing was worked around.

## Outcome matrix

extracted = new scope in the corpus; pointer = `done`, governing text already in the corpus;
blocked = `blocked_primary_source` (exact failure in the queue row); needs_review = publisher
reachable, no extractable primary document; n/a = program does not operate in the territory
(recorded as `blocked_primary_source` with `program_applicability: not_applicable`, because no
queue schema has a not-applicable status).

| Program | us-pr | us-gu | us-vi | us-as | us-mp |
| --- | --- | --- | --- | --- | --- |
| LIHEAP | extracted (2026-09-10) | extracted (2026-09-10) | blocked: no plan published | extracted (2026-09-10) | extracted (2026-09-10) |
| Medicaid | blocked: no manual | blocked: no manual (2019 PDFs 404) | blocked: no manual | blocked: no DNS record | blocked: no manual |
| CCDF | needs_review: draft plan only (unchanged) | extracted (2026-09-10) | needs_review: FFY 2022-2024 plan only (unchanged) | blocked: TLS self-signed, expired (unchanged) | blocked: HTTP 403 (unchanged) |
| CHIP | blocked: M-CHIP, no separate document | blocked: M-CHIP | blocked: M-CHIP | blocked: M-CHIP (publisher unreachable) | blocked: M-CHIP |
| SSI | n/a (42 U.S.C. 1382c(e)) | n/a | n/a | n/a | pointer: SSI applies, no supplement (POMS SI 00501.410) |
| TANF | extracted: Reglamento 7653 | extracted: FY 2024-2026 state plan | blocked: no manual or plan | n/a: no TANF program operated | n/a (42 U.S.C. 619(5)) |
| WIC | blocked: no manual | blocked: no manual | blocked: no manual | blocked: no manual | blocked: no manual |
| tax | extracted: 2025 Form 482 + instructions (ES, EN) | extracted: 2025 Form 1040 Guam, 1040-SR Guam | pointer: BIR index links the IRS Form 1040 | needs_review: Form 390 only as Excel workbook | extracted: 2025 Form 1040CM, 1040NMI, Schedules 1CM/ETC/WSD |
| SNAP | extracted: NAP Reglamento 8684 | blocked: SNAP, no manual or plan link | blocked: SNAP, no manual or plan | blocked: ASNAP, publisher posts nothing | extracted: FFY 2025 NAP block-grant MOU |
| Medicare | pointer (Pub 100-01) | pointer | pointer | pointer | pointer |

Totals over the 50 cells: extracted 13 (7 new scopes in this pass, 6 from the 2026-09-10
LIHEAP and CCDF runs), pointer 7, blocked 22, needs_review 4, not applicable 6 (counted inside
blocked in the queue files: the queue tallies are blocked 28, needs_review 4, done 7,
agent_ready 13).

## New scopes (this pass)

Every scope: coverage `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths; the
draft selector (union selector + these seven scopes) deep-validates with `ok: true`, 0 errors
(see Verification). Extraction seconds are wall seconds of the `extract-official-documents`
command, wrapped with `date +%s` (the CLI prints no timing).

| Scope | Manifest | Documents | Provisions | Seconds | Notes |
| --- | --- | ---: | ---: | ---: | --- |
| `us-pr/form/2026-09-11-tax-territory-forms-ty2025` | `manifests/us-pr-individual-income-tax-forms-ty2025.yaml` | 4 | 8 | 14 | Formulario 482 and Form 482.0 (informative prints) plus both instructions booklets; single_block, bodies 292-589 KB |
| `us-gu/form/2026-09-11-tax-territory-forms-ty2025` | `manifests/us-gu-individual-income-tax-forms-ty2025.yaml` | 2 | 4 | 4 | 2025 Form 1040 Guam and 1040-SR Guam (DRT prints); single_block |
| `us-mp/form/2026-09-11-tax-territory-forms-ty2025` | `manifests/us-mp-individual-income-tax-forms-ty2025.yaml` | 5 | 10 | 4 | 2025 Form 1040CM, 1040NMI, Schedules 1CM, ETC, WSD; single_block |
| `us-pr/regulation/2026-09-11-tanf-territory-regulation` | `manifests/us-pr-tanf-state-policy-manual.yaml` | 1 | 117 | 169 | Reglamento 7653 (TANF eligibility certification rules), scanned, stored rotated; page OCR with `ocr_psm: 1` |
| `us-gu/policy/2026-09-11-tanf-territory-state-plan` | `manifests/us-gu-tanf-state-policy-manual.yaml` | 1 | 34 | 47 | FY 2024-2026 TANF State Plan renewal, final certified; scanned, page OCR |
| `us-pr/regulation/2026-09-11-snap-nap-regulation` | `manifests/us-pr-nap-eligibility-regulation.yaml` | 1 | 128 | 128 | Reglamento 8684 (NAP eligibility rules, 2015-12-28), scanned, page OCR |
| `us-mp/policy/2026-09-11-snap-nap-mou` | `manifests/us-mp-nap-mou-fy2025.yaml` | 1 | 22 | 33 | FFY 2025 NAP block-grant MOU (CNMI DCCA / USDA FNS, version 6, signed 2024-12-03); scanned, page OCR |

Total: 15 documents, 323 provisions across 7 scopes. Citation paths:
`us-xx/form/<agency>/ty2025/<form-id>` (tax, the state convention),
`us-pr/regulation/adsef/reglamento-<n>` (the two ADSEF regulations),
`us-gu/policy/acf/tanf-plan/fy2024-2026` and `us-mp/policy/fns/nap-mou/fy2025` (the plan-family
convention of the LIHEAP and CCDF territory scopes). None collides with the existing `us-pr`,
`us-gu` and `us-mp` scopes (`.../acf/liheap-plan/fy2026`, `.../acf/ccdf-plan/fy2025-2027`).

OCR: the four scanned documents are image-only PDFs; the extractor's Tesseract page OCR ran
with the only installed traineddata (`eng`), so Spanish diacritics in the two Puerto Rico
regulations are approximate (recorded in each manifest's `ocr_note`; see Decisions). Reglamento
7653 is stored with `/Rotate 270` on every page and the rasterized pages come out sideways, so
its manifest sets `ocr_psm: 1` (Tesseract automatic page segmentation with orientation
detection), which was verified on pages 1, 3, 4 and 5 before the run.

TLS: no verification was disabled and no new intermediate was needed for any extracted host.
`medicaid.pr.gov` (reviewed, nothing extracted) omits its DigiCert Global G2 TLS RSA SHA256
2020 CA1 intermediate; the copy already committed under `data/certs/` completed the chain for
the review (certifi + intermediate via `REQUESTS_CA_BUNDLE`). `www.dhss.as` presents a
self-signed, expired certificate (CN=cmaster70) and stays blocked.

## Per-territory publisher findings

The queue row of every program carries the exact finding (`index_url`,
`index_document_count`, families, `notes`); this section is the reviewer summary.

### Puerto Rico (us-pr)

- LIHEAP: unchanged from 2026-09-10 (FY 2026 plan on the ACF LIHEAP Clearinghouse territory table).
- Medicaid: Programa Medicaid (Departamento de Salud, medicaid.pr.gov, chain completed as above):
  the applicant page lists required documents and a pre-screening calculator
  (prod-ua.preeservices.com), the Guias page holds 138 provider-enrollment files (69 checklists,
  25 PRV/AP/CLM policies, 36 communications, 8 forms); no eligibility manual or reglamento.
  salud.pr.gov/CMS/85 and ASES (Plan Vital) carry no eligibility rules. Blocked (not published).
- CCDF: re-read; ACUDEN's documents page (84 file links) still lists only the draft
  2025-2027 plan, its hearing and fee-scale attachments, the 2026-27 proposal forms and the
  adopted Reglamento del Programa Child Care (Num. 8687 de 2016), a separate regulation family.
  Still needs_review.
- CHIP: Medicaid-expansion CHIP; no separate document. Blocked with the Medicaid finding.
- SSI: outside title XVI, 42 U.S.C. 1382c(e) (in the corpus as `us/statute/42/1382c/e`);
  Puerto Rico runs AABD under titles I, X, XIV instead (separate family). Not applicable.
- TANF: ADSEF's Reglamentos page (serviciosenlinea.adsef.pr.gov/sobre-adsef/reglamento; 16
  PDFs: 2 regulations, 3 program state plans, 8 forms, 3 notices) lists Reglamento 7653, the
  TANF eligibility certification rules. Extracted. ADSEF's 2024 transition memorandum says a
  revised TANF regulation is in final review; 7653 is what the publisher posts.
- WIC: wic.pr.gov is a single-page Angular application whose server response has no document
  links; salud.pr.gov lists no manual. Blocked (not published).
- Tax: Hacienda's 2025 individual return page links six PDFs (Spanish and English informative
  prints of Formulario 482 / Form 482.0, both instructions booklets, both Schedule CT prints).
  Four taken. The return itself must be e-filed; the prints are the official form.
- SNAP: NAP block grant (7 U.S.C. 2028). The eligibility rule is Reglamento 8684 (2015-12-28)
  on the same ADSEF Reglamentos page. Extracted. The signed 2023 NAP State Plan of Operations
  (86 scanned pages, same page) and the FNA-hosted FY 2026 NAP SPO approval letter
  (fns-prod.azureedge.us/nap/pr/state-plan-operations; the letter only, no plan attachment)
  are the plan family, recorded and not taken. adsef.pr.gov itself times out on TCP; the
  agency's live site is serviciosenlinea.adsef.pr.gov, which answers a cookie-keeping browser
  session and sometimes loops redirects for a session-less client (the generator uses a session).
- Medicare: federal; pointer to Pub 100-01 (chapter 2, 40.2 carries the Puerto Rico SMI
  automatic-enrollment exception).

### Guam (us-gu)

- LIHEAP and CCDF: unchanged from 2026-09-10 (both extracted).
- Medicaid: DPHSS's Medicare/Medicaid services page and the BHCFA bureau page are text-only;
  the 2019 Guam Medicaid State Plan and Handbook PDFs answer 404. Blocked (not published).
- CHIP: Medicaid-expansion; blocked with the Medicaid finding.
- SSI: not applicable (42 U.S.C. 1382c(e)); Guam runs OAA/AB/APTD through DPHSS BES.
- TANF: DPHSS Bureau of Economic Security page (6 PDFs) lists the FY 2024-2026 TANF State
  Plan renewal (final certified, cover letters December 2023). Extracted (policy).
- WIC: DPHSS WIC pages are text-only (0 PDFs); the only WIC file on the host is the 2024-2025
  income guidelines in the retired wp-content path. Blocked (not published).
- Tax: DRT Forms & Publications page (59 PDFs) carries Guam prints of Form 1040 and 1040-SR
  for 2019-2025; no Guam instructions booklet (DRT refers taxpayers to the IRS instructions,
  in the corpus as `us/form/irs/ty2025/i1040gi`). Two taken.
- SNAP: Guam runs SNAP; the BES page's "FY26 SNAP State Plan" entry has no link (the anchor is
  commented out in the page source) and the SNAP services page is text-only; the FY26 SNAP E&T
  plan is a separate family. Blocked (not published).
- Medicare: pointer.

### Virgin Islands (us-vi)

- LIHEAP: not on the Clearinghouse territory table (AS, GU, MP, PR only; the VI file paths 404);
  DHS Division of Family Assistance posts only the ECAP checklist and intake form. Blocked.
- Medicaid: DHS Office of Medicaid page lists nine application forms and the Providers General
  Information Manual (provider family, 2026-01-21); no eligibility manual or state plan. Blocked.
- CCDF: re-read; the Office of Child Care & Regulatory Services page (36 PDFs) still lists the
  FFY 2022-2024 plan, the 2019 policy memoranda, the subsidy rules and the 2022 market rate
  survey. Still needs_review.
- CHIP: Medicaid-expansion; blocked with the Medicaid finding.
- SSI: not applicable (42 U.S.C. 1382c(e)); DHS runs OAA/AB/AD.
- TANF: the DFA page (24 PDFs) has one TANF brochure and no manual, rule or plan. Blocked.
- WIC: DOH's More WIC Information page lists nine participant PDFs; the FY 2027 WIC State Plan
  is open for comment (state-plan family). Blocked (not published).
- Tax: the BIR Forms page is an application whose listing comes from the publisher's own
  `/api/form/find` endpoint (131 entries); every "1040 U.S. Individual Income Tax Return" entry
  links the IRS PDF (2025: irs.gov/pub/irs-prior/f1040--2025.pdf) and BIR posts no return or
  instructions of its own (its TY2025 product is Form 1040 INFO, a residents' attachment).
  Done by pointer to `us/form/irs/ty2025/f1040` and `i1040gi`.
- SNAP: the Virgin Islands runs SNAP; the DFA page has application packets, the FY 2026
  income-limits chart and simplified-reporting notice, the SNAP E&T plan and handbook, ABAWD
  flyers and waivers, but no manual or plan of operation (the "Plan for Operations Management"
  file is the FY 2025 Summer EBT iPOM). Blocked (not published).
- Medicare: pointer.

### American Samoa (us-as)

- LIHEAP: unchanged from 2026-09-10 (extracted).
- Medicaid: medicaid.as.gov has no DNS A record (zone delegated to ns3-5.linode.com; NOERROR,
  empty answer, also from 8.8.8.8). Blocked (unreachable).
- CCDF: www.dhss.as still presents the self-signed, expired CN=cmaster70 certificate (verify
  return code 10; curl 60 plain and curl_cffi chrome120); the plain-HTTP site answers but its
  Child Care, ASNAP and ASWIC entries are `coming.html` placeholders. Still blocked.
- CHIP: Medicaid-expansion; blocked (publisher unreachable).
- SSI: not applicable (42 U.S.C. 1382c(e)); American Samoa runs no adult assistance program.
- TANF: eligible under 42 U.S.C. 619(5) but has never operated TANF (ACF's TANF jurisdictions
  are the states, DC, Guam, Puerto Rico and the Virgin Islands); DHSS lists no TANF program.
  Not applicable.
- WIC: aswic.com (the address FNA's WIC contact page gives for the agency) carries program and
  clinic information and the USDA complaint form; dhss.as ASWIC is a placeholder. Blocked.
- Tax: the ASG Tax Office page (15 files) posts the 2025 Form 390 A.S. Individual Income Tax
  Return only as an Excel workbook of form sheets (390, Sch. T8812, 8812(2001), Sch. TEITC,
  Sch A & B, Sch. C, 390X, 390A, Direct Deposit) and reposts the IRS 2000 tax table and
  instructions (the territory applies the IRC as of 2000-12-31). The official-documents xlsx
  path is a header-row table reader and would not represent a form layout. needs_review.
- SNAP: ASNAP block grant; DHSS posts nothing (placeholders; https blocked by its certificate);
  FNA hosts only the FY 2025 NAP summary factsheet. Blocked.
- Medicare: pointer.

### Northern Mariana Islands (us-mp)

- LIHEAP: unchanged from 2026-09-10 (extracted).
- Medicaid: the Commonwealth Medicaid Agency site (cnmimedicaid.org, Google Sites) links two
  application packets and an FAQ on Google Drive, lists required documents and describes income
  limits only as FBR percentages; its SPA page links a Google Sheet and the medicaid.gov SPA
  index; medicaid.cnmi.mp does not answer. Blocked (not published).
- CCDF: www.childcare.gov.mp still answers HTTP 403 (nginx/1.29.8) to the plain browser UA and
  curl_cffi chrome120; www.dcca.gov.mp answers the same 403. Still blocked.
- CHIP: Medicaid-expansion; blocked with the Medicaid finding.
- SSI: applies (Covenant section 502(a)(1); POMS SI 00501.410 and SI 00501.415, in the corpus,
  define the United States for SSI as the 50 States, DC and the NMI). POMS SI 01415.010's state
  table has no NMI row and the CNMI sites list no supplement. Done by pointer.
- TANF: not a State under 42 U.S.C. 619(5). Not applicable.
- WIC: CHCC's CNMI WIC page lists forms, the food list booklet and two NWA handouts (7 PDFs);
  no manual. Blocked (not published).
- Tax: the Department of Finance Forms page (170 file links) carries the 2025 Revenue and
  Taxation block: Form 1040CM (the NMTIT return), Form 1040NMI (wage and salary tax return),
  the nonresident and amended returns, Schedules 1CM, ETC and WSD, and links the IRS Schedules
  8812/EIC and the IRS 1040 instructions for the mirrored code; the last posted 1040CM
  instructions booklet is tax year 2020 (prior-year page); "Publication IOC 2025" is the
  W-2CM code reference, not instructions. Five taken.
- SNAP: NAP-CNMI. cnminap.gov.mp (DCCA) lists the signed FFY 2025 NAP block-grant MOU with USDA
  FNS (funding, benefit levels, financial and nonfinancial eligibility criteria), the 2026 DNAP
  application and checklist and a Summer EBT waiver; the Application Center lists 23 forms,
  the 2021 program guide (self-screening leaflet) and the 2025 applicant orientation paper.
  The MOU is the governing document and was extracted (policy). No FFY 2026 MOU is posted.
- Medicare: pointer.

## Code

No generated queue was hand-edited. Each program generator got a territory table and a mode
that touches only territory rows, the same way the state batches were added:

| Generator | Addition | Invocation |
| --- | --- | --- |
| `scripts/build_liheap_state_plan_manifests.py` | `TERRITORY_ROWS_NOT_ON_INDEX` (VI) | `--territories [--only us-vi]` |
| `scripts/build_ccdf_state_plan_manifests.py` | 2026-09-11 retry findings appended to the AS, MP, PR, VI `RESOLUTIONS`; `refresh_rows_only` | `--only as,mp,pr,vi` |
| `scripts/build_medicaid_state_eligibility_manual_manifests.py` | batch 6 (`STATIC_ROWS_BATCH6`) | `--batch 6 [--only us-xx]` |
| `scripts/build_chip_state_eligibility_manifests.py` | `NEW_ROW_NAMES_TERRITORIES`, `territory_chip_row` | `[--only us-xx,...]` |
| `scripts/build_ssi_state_supplement_manifests.py` | batch 4 (`update_queue_batch4`) | `--batch 4 [--only PR,GU,...]` |
| `scripts/build_tanf_state_policy_manual_manifests.py` | `build_gu`, `build_pr` (live index fetch), `NOT_PUBLISHED`, `NOT_APPLICABLE`, `BATCH_5` | `--only us-gu --only us-pr --only us-vi --only us-as --only us-mp` |
| `scripts/build_wic_manifests.py` | `TERRITORY_BLOCKED` (batch 7) | `--only us-pr,us-gu,us-vi,us-as,us-mp` |
| `scripts/build_tax_forms_manifests.py` | `STATES` entries for PR, GU, MP (batch 4, own version and source date), `TERRITORY_POINTER_ROWS` (VI, AS) | `--only us-pr,us-gu,us-vi,us-as,us-mp` |
| `scripts/build_snap_state_manual_completion_manifests.py` | `build_pr_nap`, `build_mp_nap` (live index fetch), `STATIC_ROWS_TERRITORIES` | `--only us-pr --only us-mp --only us-gu --only us-vi --only us-as --corpus-base <corpus>` |
| `scripts/build_cms_iom_100_01_manifests.py` | `TERRITORY_POINTERS` | `--territory-rows [--only us-xx]` |

Regenerating a state batch was never needed: the CHIP and tax generators rewrite every
manifest from their static tables and the result was byte-identical (`git status` showed only
the queue files and the new territory manifests).

Commit replay: the queue files were reset to HEAD and the generators re-run territory by
territory so each territory has its own commit. Re-running the SNAP NAP builders after their own
extraction made the corpus collision scan count the scopes' own citation paths (emptying the
CNMI manifest in the first MP commit); `corpus_citation_paths` now takes `exclude_version`, the
ADSEF and cnminap index fetches retry transient redirect loops, and a follow-up commit restores
the PR and MP SNAP rows and the CNMI manifest.

## Commands

```bash
# queue rows (all programs) and the seven territory manifests
uv run python scripts/build_liheap_state_plan_manifests.py --territories
uv run python scripts/build_ccdf_state_plan_manifests.py --only as,mp,pr,vi
uv run python scripts/build_medicaid_state_eligibility_manual_manifests.py --batch 6
uv run python scripts/build_chip_state_eligibility_manifests.py --only us-pr,us-gu,us-vi,us-as,us-mp
uv run python scripts/build_ssi_state_supplement_manifests.py --batch 4
uv run python scripts/build_wic_manifests.py --only us-pr,us-gu,us-vi,us-as,us-mp
uv run python scripts/build_cms_iom_100_01_manifests.py --territory-rows
uv run python scripts/build_tax_forms_manifests.py --only us-pr,us-gu,us-vi,us-as,us-mp
uv run python scripts/build_tanf_state_policy_manual_manifests.py --only us-gu --only us-pr --only us-vi --only us-as --only us-mp
uv run python scripts/build_snap_state_manual_completion_manifests.py --only us-pr --only us-mp --only us-gu --only us-vi --only us-as \
  --corpus-base /Users/pavelmakarchuk/axiom-corpus/data/corpus

# extraction (base = the main checkout's corpus root; df -h / checked before each run, 8.5 GB free)
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
for j in pr gu mp; do
  uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-11-tax-territory-forms-ty2025 \
    --manifest manifests/us-$j-individual-income-tax-forms-ty2025.yaml --source-as-of 2026-09-11
done
uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-11-tanf-territory-regulation \
  --manifest manifests/us-pr-tanf-state-policy-manual.yaml --source-as-of 2026-09-11
uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-11-tanf-territory-state-plan \
  --manifest manifests/us-gu-tanf-state-policy-manual.yaml --source-as-of 2026-09-11
uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-11-snap-nap-regulation \
  --manifest manifests/us-pr-nap-eligibility-regulation.yaml --source-as-of 2026-09-11
uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-11-snap-nap-mou \
  --manifest manifests/us-mp-nap-mou-fy2025.yaml --source-as-of 2026-09-11

# release deep validation on a draft selector (union selector + the seven scopes), scratch directory
uv run axiom-corpus-ingest validate-release --base $B --release <scratch>/territories-draft.selector.json \
  --ignore-r2-missing --max-issues 50
```

Artifacts (unsigned, uncommitted, under the main checkout's `data/corpus`; `data/corpus` is not
checked out in this worktree and nothing under it was committed):

- `data/corpus/sources/<jur>/<class>/<version>/official-documents/*`
- `data/corpus/inventory/<jur>/<class>/<version>.json`
- `data/corpus/provisions/<jur>/<class>/<version>.jsonl`
- `data/corpus/coverage/<jur>/<class>/<version>.json`

## Verification

Coverage per scope: `complete: true`, 0 missing, 0 extra for all seven (tax scopes: one root plus one
`document-1` body per document, bodies 2-589 KB; OCR scopes: one root plus one `page-N` body per page,
median body 1.4-2.7 KB, the only bodies under 200 characters are two cover/signature pages of
Reglamento 7653 and the MOU's signature page). Citation-path uniqueness inside each provisions
JSONL and absence from every other provisions file of the same jurisdiction were checked by the
SNAP generator's `--corpus-base` collision scan (0 collisions) and by the release validation below.

Release deep validation, draft selector = the union selector
(`us-rulespec-2026-09-11-program-ingestion-union`, 536 scopes) plus the seven territory scopes
(543 scopes), run from the worktree against the main checkout's corpus:
`ok: true`, `error_count: 0`, `warning_count: 546` (37 s). The 546 warnings are the ones the
2026-09-11 consolidation note already lists (541 `missing_parent_id` in the released
`us-ca/regulation/2026-07-13-recovery` scope and the 5 advisory `unsectioned_document_body`
warnings); none concerns a territory scope. No `duplicate_release_citation` was raised, so the new
citation paths collide with nothing in the release.

## Tests

`uv run ruff check scripts`: all checks passed.

`uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
in the sparse worktree: 286 passed, 12 failed, 2 skipped (48 s). All 12 failures open `data/corpus` artifacts of other
scopes that the sparse worktree does not check out (`FileNotFoundError` under `data/corpus/...`):
the ten the gotchas note lists (`test_be_rulespec_2026_08_23_promotion`, the two
`test_build_ny_tanf_compatibility_scope` tests, `test_rulespec_be_source_promotion`, and the
AK, CT, MI, MT, ND, NY SNAP manual tests) plus `test_armenia_arlis` and `test_israel_openlaw`,
which fail the same way; none touches a territory file, and the consolidation note records that
the selection passes in a full checkout.

## Controller section

Selector additions (append to
`docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json` or its
successor; the draft used for validation is the union selector plus exactly these seven):

```json
{"jurisdiction": "us-pr", "document_class": "form", "version": "2026-09-11-tax-territory-forms-ty2025"}
{"jurisdiction": "us-gu", "document_class": "form", "version": "2026-09-11-tax-territory-forms-ty2025"}
{"jurisdiction": "us-mp", "document_class": "form", "version": "2026-09-11-tax-territory-forms-ty2025"}
{"jurisdiction": "us-pr", "document_class": "regulation", "version": "2026-09-11-tanf-territory-regulation"}
{"jurisdiction": "us-gu", "document_class": "policy", "version": "2026-09-11-tanf-territory-state-plan"}
{"jurisdiction": "us-pr", "document_class": "regulation", "version": "2026-09-11-snap-nap-regulation"}
{"jurisdiction": "us-mp", "document_class": "policy", "version": "2026-09-11-snap-nap-mou"}
```

Decisions for the reviewer:

1. OCR language. Only Tesseract's `eng` traineddata is installed on the controller machine, so
   the two Puerto Rico regulations (Spanish) were OCR'd with the English model; the text is
   legible but diacritics are approximate. Installing `spa` (`brew install tesseract-lang`) and
   re-extracting both scopes with `ocr_language: spa` would improve fidelity; the manifests
   record the note.
2. Reglamento 7653 currency and expression date. ADSEF's own Reglamentos page posts 7653 as the
   TANF regulation while its 2024 transition memorandum says a revised regulation is in final
   review; the promulgation date sits on a scanned cover the OCR did not read, so
   `expression_date` is the fetch date (the MA/VA precedent). Confirm or replace when ADSEF
   posts the revision.
3. Not-applicable status. SSI (PR, GU, VI, AS) and TANF (AS, MP) rows are
   `blocked_primary_source` with `program_applicability: not_applicable` because no queue schema
   has a not-applicable status; a schema value would make the tallies cleaner.
4. American Samoa tax: extract the 2025 Form 390 workbook through a form-workbook path (one
   provision per sheet) or wait for a PDF print; needs_review as recorded.
5. Puerto Rico NAP plan family: the signed 2023 NAP State Plan of Operations (ADSEF, 86 scanned
   pages) and the FNA-hosted FY 2026 approval letter were recorded, not taken; a later plan-family
   run can add them under `us-pr/policy` without colliding with the regulation scope.
6. CNMI NAP MOU is the FFY 2025 agreement (the latest the publisher posts); an FFY 2026 MOU, once
   posted, would be a superseding scope.
7. Virgin Islands tax: BIR's own TY2025 Form 1040 INFO (residents' attachment) was recorded, not
   taken; take it if territory-specific attachments are wanted.
8. The medicaid.pr.gov chain completion used the already committed DigiCert G2 intermediate; no
   cert was added in this pass.
