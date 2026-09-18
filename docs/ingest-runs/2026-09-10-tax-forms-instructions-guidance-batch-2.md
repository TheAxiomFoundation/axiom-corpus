# Tax forms, instructions, and guidance: states batch 2 (NH onward) and CO/IN retries

Date: 2026-09-10
Program: TAX (board Year 1 list; `manifests/tax-agent-queue.yaml`)
Branch: `discovery/ingest-tax`

Timing: started_at 2026-09-10T18:33:23Z, finished_at 2026-09-10T18:55:18Z, agent wall time 0h 21m 55s
(1315 s). The CLI prints no timing; every extraction was wrapped in
`s=$(date +%s); ...; echo $(( $(date +%s) - s ))`. A previous attempt at this batch
stalled before doing anything; this run started from the clean batch-1 tree.

GitNexus impact analysis was not run: the GitNexus MCP tools were unavailable in
this session. No existing function in `src/` was modified and no new adapter was
needed; every scope ran through the existing `extract-official-documents`
extractor (`single_block` PDFs, `html_content_selector` HTML, and the extractor's
existing `request.browser_impersonation` path for one publisher). The only code
change is to the batch-1 generator `scripts/build_tax_forms_manifests.py`
(batch-2 tables; dict rows for HTML documents; a per-state `document_class`,
`request`, `index_families` and `retries`; an impersonation-aware `--verify`
probe). Regenerating with it leaves every batch-1 manifest byte-identical.
`uv run ruff check scripts/build_tax_forms_manifests.py` passes; the 8 pre-existing
findings `ruff check scripts/` reports are in `build_liheap_state_plan_manifests.py`
and `draft_program_work_orders.py` and were left alone.

## Federal (`us`)

No change. The `us/form` and `us/guidance` scopes from batch 1 were not re-run.

## States, batch 2

Batch rule (reviewer judgment): batch 1 left seven `needs_review` states (NH, NJ,
NM, OK, UT, VT, WA). The work order asked for "the next ten ... starting at NH";
the queue holds only these seven, so batch 2 is all of them and no `done` row
(including the seven whose `target_scope.version` is null: MD, MO, ND, OH, SC,
VA, WV) was reopened. UT is counted although it ended blocked (the block is the
publisher's). After this run the queue has no `needs_review` rows.

Form scopes: document_class `form`, citation path
`us-xx/form/<agency>/ty2025/<form-id>`, version
`2026-09-10-tax-state-forms-ty2025`, PDF `single_block` (root + `document-1`),
`source_as_of` 2026-09-10, `expression_date` 2025-01-01, as in batch 1.

Guidance scopes (new in batch 2, reviewer judgment 2): two states publish no
TY2025 resident individual income tax return at all. Following the
zero-liability precedents (FL/NV/SD/TN/TX/WY/AK hold statute or guidance, not a
return), they were given document_class `guidance`, citation path
`us-xx/guidance/<agency>/<id>` (the `us/guidance/irs/<id>` shape), version
`2026-09-10-tax-state-guidance-ty2025`, same dates, manifest
`us-xx-individual-income-tax-guidance-ty2025.yaml`.

| state | index_url | index docs | taken | provisions | seconds | status |
|---|---|---|---|---|---|---|
| us-nh | https://www.revenue.nh.gov/resource-center/current-year-forms-and-instructions | 232 unique PDFs (238 links) | 1 (guidance): TIR 2025-001, I&D tax repealed 2025-01-01 | 2 | 1 | agent_ready |
| us-nj | https://www.nj.gov/treasury/taxation/prntgit.shtml | 63 unique PDFs (89 table rows) | 2: NJ-1040, NJ-1040 instructions | 4 | 5 | agent_ready |
| us-nm | https://www.tax.newmexico.gov/individuals/online-services-overview/personal-income-tax-forms/ | 32 files + 2 subfolders (RealFile folder "Personal Income Tax (PIT)") | 3: 2025 PIT-1, PIT-1 instructions, 2025 Tax Look Up Table | 6 | 7 | agent_ready |
| us-ok | https://oklahoma.gov/tax/forms.html (metadata CSV New-MetaData-CSV-8-1-26.csv) | 26 rows Income Tax / Individuals / Current (1,649 rows total) | 1: 2025 Form 511 resident packet (form + instructions + 538-S + tax table) | 2 | 3 | agent_ready |
| us-ut | https://tax.utah.gov/forms | n/a | 0 | 0 | n/a | blocked_primary_source |
| us-vt | https://tax.vermont.gov/personal-income-tax | 35 unique PDFs | 3: IN-111, IN-111 instructions, Tax Year 2025 Vermont Tax Rate Schedules | 6 | 4 | agent_ready |
| us-wa | https://dor.wa.gov/taxes-rates/other-taxes/capital-gains-tax (no income tax forms exist) | 8 documents linked (4 interim statements, 2 special notices, 2 PDFs) | 3 (guidance, HTML): DOR Income tax page, Capital gains tax page, Special Notice on TY2025 tiered rates | 22 | 1 | agent_ready |

Per-index families (every family seen, counts, taken) are in each queue row's
new `index_families` list and `notes`, and in `STATES[...]["index_families"]` /
`["inventory"]` of the generator. Batch-1 rows keep their families in `notes`
only (unchanged).

Blocked, with the exact failure:

- Utah: `tax.utah.gov` answers HTTP 403 with a Cloudflare JavaScript challenge
  ("Just a moment... Enable JavaScript and cookies to continue", header
  `cf-mitigated: challenge`) for the forms index and the TC-40 PDF paths
  (`/forms/current/tc-40.pdf`, `tc-40inst.pdf`) with the corpus user agent, a
  Chrome user agent, and curl_cffi chrome120 impersonation. The commission's
  file host `files.tax.utah.gov`, which its own `incometax.utah.gov` instruction
  site links for `tc-40.pdf`, `tc-40inst.pdf`, `tc-40-fullpacket.pdf` and
  `tc-40a.pdf`, answers HTTP 404 (S3 "Page Not Found") for every path and the
  root in all three modes. Not worked around. `incometax.utah.gov` (HTML TC-40
  instructions) serves to the corpus user agent and is left for the reviewer as
  a possible instructions-only source; it was not taken because the resident
  return itself is unreachable.

Retries of the batch-1 blocks (one plain request and one chrome120 impersonation
each, 20 s timeouts, 2026-09-10T18:35:21Z, under two minutes total):

- Colorado: `tax.colorado.gov` forms index and `DR0104_Book_2025.pdf` path, HTTP
  403 CloudFront "ERROR: The request could not be satisfied" in both modes. Same
  failure; row note appended "retried 2026-09-10T18:35:21Z, same failure".
- Indiana: the in.gov DOR index serves (200) in both modes; `forms.in.gov/
  Download.aspx?id=15904` and `forms.in.gov/` answer HTTP 403 Cloudflare
  "Sorry, you have been blocked" in both modes. Same failure; row note appended
  "retried 2026-09-10T18:35:21Z, same failure".

## Access notes

- TLS: no chain problems; no bundle added under `data/certs/`; verification never
  disabled.
- New Hampshire DRA (`revenue.nh.gov`): HTTP 403 to plain requests with the
  corpus user agent and with a Chrome user agent; serves to a chrome120 TLS
  fingerprint. The NH manifest sets the extractor's existing
  `request: {browser_user_agent, browser_impersonation, browser_impersonation_direct}`
  (precedent `manifests/us-ma-2026-surtax-guidance.yaml`). This is the
  publisher's own host, fetched with TLS verified; no mirror or proxy.
- New Mexico TRD: the Personal Income Tax Forms page is a RealFile widget
  (`rf-tables.js`, account `34821a9573ca43e7b06dfad20f5183fd`, folder
  `288c2306-33d5-4471-b79b-73d07aaea840`). The inventory is the widget's own
  `GET .../prod/GetWidgetFiles?accountGUID=..&folderId=..&rootFolderId=..` listing
  (32 files, 2 subfolders); downloads are the URLs the widget emits,
  `https://klvg4oyd4j.execute-api.us-west-2.amazonaws.com/prod/PublicFiles/<account>/<fileId>/<name>`.
  The documents record the TRD page as `source_url` and that URL as
  `download_url`, like the DE/MT file-host precedents.
- Oklahoma Tax Commission: `oklahoma.gov/tax/forms.html` is rendered from the
  commission's metadata CSV (`data-csv-table-api`); the CSV was used as the index
  inventory. PDFs are on `oklahoma.gov` itself.
- Vermont: `/individuals/personal-income-tax` redirects to `/personal-income-tax`;
  `/individuals/personal-income-tax/forms-and-instructions` is 404. The index
  labels `VermontTaxTables-2025.pdf` "Tax Year 2024 Vermont Tax Tables" (publisher
  label mismatch; not taken).
- Washington DOR pages: Drupal, body selected with `main .field--name-body`
  (exactly one match per page); the default HTML segmentation yields one
  provision per heading (`block-N`).
- Utah: see Blocked.

## Counts

Scopes: 6 (us-nj, us-nm, us-ok, us-vt form; us-nh, us-wa guidance). Documents:
13. Provisions: 42 = NJ 4 + NM 6 + OK 2 + VT 6 + NH 2 + WA 22. Coverage
`complete: true` for every scope, 0 missing, 0 extra; citation paths verified
unique per provisions file by an independent script, and no new citation_path
exists in any other provisions JSONL under `data/corpus/provisions/<jurisdiction>/`
(all classes checked for each of the six jurisdictions); every inventory item's
SHA-256 matches its non-symlink source file. Index documents found versus taken:
232/1 (NH), 63/2 (NJ), 32/3 (NM), 26/1 (OK), 35/3 (VT), 8/3 (WA), UT n/a.

Extraction seconds: NJ 5, NM 7, OK 3, VT 4, NH 1, WA 1. Smoke runs (scratch
base): VT 5 s, NH 1 s. `--verify` probe of all 56 manifest documents (batch 1 +
2): 0 failures, 22 s.

Artifacts (unsigned, awaiting controller; not committed; written to the main
checkout's corpus root because this worktree is sparse):

- `data/corpus/sources/us-xx/form/2026-09-10-tax-state-forms-ty2025/official-documents/*`
- `data/corpus/{inventory,provisions,coverage}/us-xx/form/2026-09-10-tax-state-forms-ty2025.*`
  for xx in nj, nm, ok, vt
- `data/corpus/sources/us-xx/guidance/2026-09-10-tax-state-guidance-ty2025/official-documents/*`
- `data/corpus/{inventory,provisions,coverage}/us-xx/guidance/2026-09-10-tax-state-guidance-ty2025.*`
  for xx in nh, wa

Rebuild:

```bash
uv run python scripts/build_tax_forms_manifests.py --verify   # probe every URL
AXIOM_CORPUS_BASE=/Users/pavelmakarchuk/axiom-corpus/data/corpus uv run python scripts/build_tax_forms_manifests.py
BASE=/Users/pavelmakarchuk/axiom-corpus/data/corpus
for j in nj nm ok vt; do
  uv run axiom-corpus-ingest extract-official-documents --base $BASE \
    --version 2026-09-10-tax-state-forms-ty2025 --manifest manifests/us-$j-individual-income-tax-forms-ty2025.yaml
done
for j in nh wa; do
  uv run axiom-corpus-ingest extract-official-documents --base $BASE \
    --version 2026-09-10-tax-state-guidance-ty2025 --manifest manifests/us-$j-individual-income-tax-guidance-ty2025.yaml
done
```

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
in the sparse worktree: 255 passed, 10 failed, 2 skipped (64 s). The 10 failures
are the known sparse-checkout `FileNotFoundError`s (BE rulespec promotion, NY
TANF compatibility x2, BE source promotion, AK/CT/MI/MT/ND/NY SNAP manual tests),
identical to batch 1. No test references the files added here.

## Reviewer judgments

1. Batch membership: seven states, not ten; no `done` row reopened (above). UT
   counted in the batch though blocked.
2. NH and WA as guidance scopes. NH: the DRA's TY2025 index lists no Interest
   and Dividends (DP-10) family and TIR 2025-001 states "2025 I&D Tax forms will
   not be available"; the TIR was taken. WA: the DOR states "Washington does not
   currently have an individual income tax" and announces the 9.9% tax on AGI
   over $1 million from 2028 (SB 6346, first returns 2029); the capital gains
   excise tax on individuals (7% to $1,000,000 and 9.9% above from tax year 2025)
   is filed only through My DOR, so the three DOR HTML pages were taken and the
   2023 return-instructions PDF (pre-tiered-rates) was not. A reviewer may
   prefer to hold these two under `done`-style rows instead of new scopes.
3. NM downloads come from the TRD's RealFile host on AWS API Gateway, the only
   URLs the publisher's index emits (treated like `revenuefiles.delaware.gov`).
   The 2025 Tax Look Up Table was taken as the separately listed computation
   document (DE/AL tax-table precedent); the combined 2025 PIT Packet and the
   PIT-RC rebate schedule were not.
4. OK publishes the resident return only inside the 511 packet (form,
   instructions, 538-S, tax table), so taken_count is 1 with subtype
   `forms_and_instructions_packet`.
5. VT: rate schedules taken, tax tables and the combined booklet not (AR
   precedent: computation sheet over lookup table; booklet duplicates IN-111 and
   its instructions).
6. NJ: rate schedules and tax table are inside the 70-page instruction booklet;
   nothing separate is listed.
7. NH requires browser TLS impersonation through the extractor's existing
   `request` keys; batch 1 deliberately did not configure this for DC because DC
   served plainly. Here plain requests are refused, the host is the publisher's,
   and TLS stays verified, so it was used rather than marking NH blocked.
8. UT: `incometax.utah.gov` HTML instructions were not taken as a partial scope;
   the row is blocked on the unreachable resident return.
9. Queue rows gained an `index_families` list for batch-2 states only; the
   generator leaves batch-1 rows and manifests unchanged.
10. The `_verify` helper now imports `curl_cffi` lazily for impersonated rows and
    treats any probe exception as a failure.

Remaining (controller): `sign-ingest-manifest` per scope, immutable release
selector, `publish_corpus.py --dry-run`, then publish and activate. The TAX state
queue is exhausted; CO, IN and UT stay `blocked_primary_source` pending access
from a US network or a publisher export.
