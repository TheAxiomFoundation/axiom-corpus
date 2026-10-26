# Tax forms, instructions, and guidance: IRS TY2025 core and states batch 1

Date: 2026-09-10
Program: TAX (board Year 1 list; `manifests/tax-agent-queue.yaml`)
Branch: `discovery/ingest-tax`

Timing: started_at 2026-09-10T16:36:36+0200, finished_at 2026-09-10T16:59:21+0200, agent wall
time 0h 22m 45s (1365 s). The CLI prints no timing; every extraction was wrapped in
`s=$(date +%s); ...; echo $(( $(date +%s) - s ))`.

GitNexus impact analysis was not run: the GitNexus MCP tools were unavailable in
this session. No existing function was modified; the only code added is the
generator script `scripts/build_tax_forms_manifests.py`. No new adapter was
needed; everything ran through the existing `extract-official-documents`
extractor with `single_block` (PDF) and `html_content_selector` (HTML) config.

## Federal (`us`)

Publisher: Internal Revenue Service.

Index inventory:

- https://www.irs.gov/forms-instructions (Forms & Instructions): 35 products
  listed as popular forms/instructions: Form 1040 + instructions, Schedules 1,
  1-A, 2, 3, the 1040 tax table (p1040), 1040-SR, W-4, 1040-ES, W-9 + instr.,
  4506-T, 4506, 2848, 941 + instr., W-2, W-2/W-3 instr., 9465 + instr., SS-4 +
  instr., W-7 / W-7(SP) + instr., 4547 + instr.; plus links to accessible/eBook/
  prior-year/browser-friendly listings.
- https://www.irs.gov/forms-pubs/about-form-1040 (Form 1040 page): Form 1040,
  1040-SR, instructions (HTML and print PDF), Schedules 1, 1-A, 2, 3, "Changes
  to the 2025 Instructions for Form 1040", 1040 tax and EIC tables (HTML), and
  related-product links (Pub 17, 1040-ES, 1040-V, 1040-X, 2106, 2210, 2441, 2848,
  3903, ...).
- https://www.irs.gov/forms-pubs/schedules-for-form-1040: 14 schedules (1, 1-A,
  2, 3, A, B, C, D, E, EIC, F, H, J, R, SE, 8812).
- https://www.irs.gov/internal-revenue-bulletins: 2026 issues 2026-01 through
  2026-37 (37 issues); scanned issue pages 2026-01..05, 20..26, 30..37 for
  inflation-adjustment items.

Taken, family `irs-individual-income-tax-forms-ty2025`, document_class `form`,
citation path `us/form/irs/ty2025/<irs-product-id>`, version
`2026-09-10-tax-irs-forms-ty2025` (19 documents, 1,087 provisions):

| product | source | provisions |
|---|---|---|
| f1040, f1040s1, f1040s2, f1040s3, f1040sa, f1040sb, f1040sd, f1040sei, f1040s8, f8962, f1040sse | `/pub/irs-pdf/<id>.pdf`, single_block | 2 each (root + `document-1`) |
| i1040gi | https://www.irs.gov/instructions/i1040gi (HTML) | 305 |
| i1040sca | https://www.irs.gov/instructions/i1040sca | 54 |
| i1040sb | https://www.irs.gov/instructions/i1040sb | 18 |
| i1040sd | https://www.irs.gov/instructions/i1040sd | 75 |
| i1040s8 | https://www.irs.gov/instructions/i1040s8 | 33 |
| i8962 | https://www.irs.gov/instructions/i8962 | 96 |
| i1040sse | https://www.irs.gov/instructions/i1040sse | 35 |
| p17 | https://www.irs.gov/publications/p17 | 449 |

Instructions and Publication 17 were taken from the irs.gov HTML editions
(`html_content_selector: .book`), which the extractor splits into one provision
per heading (`block-N`, heading preserved); the print PDF URL is recorded in
each document's `print_version_pdf` metadata. Schedule EIC has no separate
instructions (they live in the Form 1040 instructions). Schedules 1/2/3
instructions are likewise inside i1040gi. Not taken from the index: 1040-SR,
Schedule 1-A, the standalone tax-table PDF (p1040; the table is in i1040gi
`block-152`, EIC table `block-116`), 1040-ES, W-4, and the non-1040 families.

Guidance, document_class `guidance`, `us/guidance/irs/<id>`, version
`2026-09-10-tax-irs-guidance` (3 documents, 16 provisions, page-per-provision
like the existing `us-irs-guidance.yaml` scope):

- Notice 2026-10, 2026 Standard Mileage Rates (IRB 2026-04, 2026-01-20, page 378).
- Rev. Proc. 2026-24, 2027 HSA inflation adjusted amounts (IRB 2026-25, 2026-06-15).
- Rev. Proc. 2026-26, section 36B applicable percentage table and required
  contribution percentage for 2027 (IRB 2026-31, 2026-07-27).

Already in `manifests/us-irs-guidance.yaml` and skipped: Rev. Proc. 2025-25,
Rev. Proc. 2025-32 (tax year 2026 items), Notice 2025-67. The Rev. Proc. setting
tax year 2027 items had not been published by 2026-09-10 (last issue scanned
2026-37).

## States, batch 1

Batch rule (reviewer judgment): walk the queue in order; a state whose
current-year resident individual income tax material is on the work order's
"do not duplicate" list is `done` and does not count; batch 1 is the first ten
remaining states. Result: AL, AR, CO, DC, DE, IA, ID, IN, MS, MT. CO and IN are
counted in the ten although they ended blocked (they need a new extraction; the
block is the publisher's, not a prior ingest).

All state documents: document_class `form`, citation path
`us-xx/form/<agency>/ty2025/<form-id>`, version
`2026-09-10-tax-state-forms-ty2025`, PDF `single_block` (root + `document-1`),
`source_as_of` 2026-09-10, `expression_date` 2025-01-01.

| state | index_url | index docs | taken | provisions | seconds | status |
|---|---|---|---|---|---|---|
| us-al | https://www.revenue.alabama.gov/forms/?jsf=jet-data-table:form-table&tax=individual-income-tax | 26 rows (search "40": 15 TY2025 + 10 TY2024) | 4: Form 40, Form 40 Booklet (instructions), Form 40 Tax Table, Standard Deduction Chart 40 | 8 | 2 | agent_ready |
| us-ar | https://www.dfa.arkansas.gov/office/taxes/income-tax-administration/individual-income-tax/forms/2025-tax-forms/ | 49 PDFs | 3: AR1000F, AR1000F/NR Instructions, Tax Brackets 2025 | 6 | 1 | agent_ready |
| us-co | https://tax.colorado.gov/individual-income-tax-forms | n/a | 0 | 0 | n/a | blocked_primary_source |
| us-dc | https://otr.cfo.dc.gov/page/individual-income-tax-forms-0 | 230 node links (2018-2025; 6 per year) | 2: 2025 D-40 Booklet, 2025 D-40 | 4 | 3 | agent_ready |
| us-de | https://revenue.delaware.gov/personal-income-tax-forms/ | 63 PDFs | 3: PIT-RES, PIT-RES Instructions, 2025 Income Tax Table | 6 | 6 | agent_ready |
| us-ia | https://revenue.iowa.gov/forms/common-forms/individual-income-tax | 15 media links + 47 expanded-instruction pages | 2: 2025 IA 1040, 2025 IA 1040 Expanded Instructions (printable PDF) | 4 | 1 | agent_ready |
| us-id | https://tax.idaho.gov/forms/ | 200 PDFs (589 links) | 3: Form 40, Individual Income Tax Instructions (EIN00046 rev. 2026-03-02), Form 39R | 6 | 7 | agent_ready |
| us-in | https://www.in.gov/dor/tax-forms/individual/current/ | 62 form links | 0 | 0 | n/a | blocked_primary_source |
| us-ms | https://www.dor.ms.gov/forms-resources/form-search?division=individual_forms | 26 PDFs | 2: Form 80-105, Form 80-100 Instructions | 4 | 4 | agent_ready |
| us-mt | https://revenue.mt.gov/forms/ (publication pages) | 20 + 7 PDFs | 2: 2025 Form 2, 2025 Form 2 Instructions | 4 | 11 | agent_ready |

Per-index families (every family seen, counts, taken) are recorded verbatim in
each queue row's `notes` and in `STATES[...]["inventory"]` of the generator.

Blocked, with the exact failure:

- Colorado: `tax.colorado.gov` answers HTTP 403 "ERROR: The request could not
  be satisfied ... The Amazon CloudFront distribution is configured to block
  access from your country" for the site root, the forms index, and the DR 0104
  Book PDF path, with the corpus user agent, a Chrome user agent, and curl_cffi
  chrome120 impersonation. Not worked around.
- Indiana: the in.gov DOR index renders, but every download is
  `forms.in.gov/Download.aspx?id=...`, which answers HTTP 403 with a Cloudflare
  "Sorry, you have been blocked ... You are unable to access in.gov" page for all
  three request modes (HEAD and GET); `forms.in.gov/` root also 403s. No
  in.gov-hosted copy of the IT-40 booklet was found. Not worked around.

Done already (34 rows marked `done`, not re-ingested, not counted): AK, AZ, CA,
CT, FL, GA, HI, IL, KS, KY, LA, MA, MD, ME, MI, MN, MO, NC, ND, NE, NV, NY, OH,
OR, PA, RI, SC, SD, TN, TX, VA, WI, WV, WY. Each row carries the prior
`target_manifest`; `target_scope.version` comes from the prior run note or a
local coverage artifact, and `document_class` from the coverage directory that
holds that version.

Remaining for later batches (`needs_review`): NH, NJ, NM, OK, UT, VT, WA.

## Access notes

- TLS: no chain problems; no bundle needed; verification never disabled.
- DC OTR: the index and PDFs serve to the corpus user agent; a Chrome user agent
  or chrome120 impersonation gets a Cloudflare "Access denied" page, so no
  `browser_impersonation` is configured for DC.
- Montana: `revenue.mt.gov/forms/` serves a page titled "404 Error Page" whose
  body is the live forms repository; the Form 2 PDFs are linked from its
  publication pages (`revenue.mt.gov/files/...` and `revenuefiles.mt.gov/...`).
- Mississippi file names contain spaces (`80105258%201.pdf`); fetched as-is.

## Counts

Scopes: 10 (us/form, us/guidance, and 8 state form scopes). Documents: 43.
Provisions: 1,145 = 1,087 (us/form) + 16 (us/guidance) + 42 (states: AL 8,
AR 6, DC 4, DE 6, IA 4, ID 6, MS 4, MT 4). Coverage `complete: true` for every
scope, 0 missing, 0 extra; citation paths verified unique per provisions file.

Extraction seconds: us/form 10, us/guidance 2 (re-run after the mileage-notice
correction, first run also 2), AL 2, AR 1, DC 3, DE 6, IA 1, ID 7, MS 4, MT 11.
Smoke runs (scratch base): IRS f1040 + i1040s8, 2 s; MS, 5 s.

Artifacts (unsigned, awaiting controller; not committed):

- `data/corpus/sources/us/form/2026-09-10-tax-irs-forms-ty2025/official-documents/*`
- `data/corpus/{inventory,provisions,coverage}/us/form/2026-09-10-tax-irs-forms-ty2025.*`
- `data/corpus/sources/us/guidance/2026-09-10-tax-irs-guidance/official-documents/*`
- `data/corpus/{inventory,provisions,coverage}/us/guidance/2026-09-10-tax-irs-guidance.*`
- `data/corpus/sources/us-xx/form/2026-09-10-tax-state-forms-ty2025/official-documents/*`
- `data/corpus/{inventory,provisions,coverage}/us-xx/form/2026-09-10-tax-state-forms-ty2025.*`
  for xx in al, ar, dc, de, ia, id, ms, mt

Rebuild:

```bash
uv run python scripts/build_tax_forms_manifests.py --verify   # probe every URL
AXIOM_CORPUS_BASE=data/corpus uv run python scripts/build_tax_forms_manifests.py
uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-10-tax-irs-forms-ty2025 --manifest manifests/us-irs-individual-income-tax-forms-ty2025.yaml
uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-10-tax-irs-guidance --manifest manifests/us-irs-guidance-2026-inflation-adjustments.yaml
for j in al ar dc de ia id ms mt; do
  uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-10-tax-state-forms-ty2025 --manifest manifests/us-$j-individual-income-tax-forms-ty2025.yaml
done
```

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
in the sparse worktree: 255 passed, 10 failed, 2 skipped. All 10 failures are
`FileNotFoundError` on `data/corpus/...` inputs (BE rulespec promotion, NY TANF
scope, AK/CT/MI/MT/ND/NY SNAP manual tests), which are absent from this sparse
checkout; the same 10 tests pass in the main checkout (13 passed with
`-p no:cacheprovider`). No test references the files added here.

## Reviewer judgments

1. Batch rule and membership (above); CO and IN counted in the ten despite
   ending blocked.
2. The "done" list follows the work order literally: AZ (140ES booklet), CA
   (540-ES), KS (K-40ES), LA (IT-540ES), MA (Form 1-ES), NE (1040N-ES), OR
   (OR-ESTIMATE), WI (Form 1-ES) hold estimated-tax material, and the
   zero-liability states hold statutes/guidance, not a TY2025 resident return +
   instructions; they are marked done and not re-ingested. MD, MO, ND, OH, SC,
   VA, WV have a forms manifest but no local coverage artifact and no release
   selector naming a form version, so their `target_scope.version` is null.
3. IRS instructions and Publication 17 were taken as irs.gov HTML (headed
   sections, one provision per heading) instead of the print PDFs; the PDF URL is
   in metadata. Per-heading provisions use the extractor's `block-N` suffixes.
4. State forms and instruction booklets are one body-bearing `document-1`
   provision each (`single_block`), matching the GA IT-511, AZ 140ES, and CA
   540-ES precedents; no per-section splitting of state booklets was attempted.
5. Per-state "rate schedule or estimated tax instructions" reading: taken where
   the publisher lists a separate TY2025 computation document (AL tax table +
   standard deduction chart, AR tax brackets, DE tax table); not taken where the
   rate schedule is inside the booklet (DC, IA, ID, MS, MT). The DC 2026 D-40ES
   booklet is a TY2026 product and was left out. AR tax tables (lookup) were
   left out in favor of the brackets sheet.
6. Iowa publishes its instructions as 47 HTML line pages plus the department's
   own printable "2025 IA 1040 Expanded Instructions" PDF; the PDF was taken as
   the instruction booklet. `manifests/us-ia-revenue-tax-guidance.yaml` (two of
   those HTML pages, guidance class) was left untouched.
7. Idaho: `manifests/us-id-tax-forms.yaml` (older source-discovery seed, never
   extracted) was left untouched; the TY2025 instructions revision
   (EIN00046_03-02-2026) is new.
8. Alabama's index is a client-filtered JetEngine table; the counts recorded are
   the rows the server rendered for the individual-income-tax filter and the
   "40" search, not a server-side total.
9. Guidance selection: only inflation-adjustment items affecting individual
   returns (mileage, HSA, section 36B percentages); section 45Q/43/613A factors,
   LIHTC percentages and Saver's Match notices in the scanned issues were not
   taken. First generation of the guidance manifest mis-identified Notice 2026-8
   (group exemption letters) as the mileage notice from the IRB highlight list;
   corrected to Notice 2026-10 after reading the PDF, the stale source file was
   removed, and the scope was re-extracted (final count 16 provisions).

Remaining (controller): `sign-ingest-manifest` per scope, immutable release
selector, `publish_corpus.py --dry-run`, then publish and activate. States batch
2 starts at NH.
