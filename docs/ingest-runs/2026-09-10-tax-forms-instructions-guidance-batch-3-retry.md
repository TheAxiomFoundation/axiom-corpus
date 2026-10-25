# Tax forms, instructions, and guidance: batch 3, US-network retry of CO, IN and UT

Date: 2026-09-10
Program: TAX (board Year 1 list; `manifests/tax-agent-queue.yaml`)
Branch: `discovery/ingest-tax`

Timing: started_at 2026-09-10T21:34:22Z, finished_at 2026-09-10T21:46:42Z, agent wall time 0h 12m 20s (740 s).
The CLI prints no timing; every extraction was wrapped in
`s=$(date +%s); ...; echo $(( $(date +%s) - s ))`. The controller's network exited
from a US address for this run; batches 1 and 2 ran from a European exit.

GitNexus impact analysis was not run: the GitNexus MCP tools were unavailable in
this session. No existing function in `src/` was modified and no new adapter was
needed; the three scopes ran through the existing `extract-official-documents`
extractor (`single_block` PDFs; the extractor's existing
`request.browser_impersonation` path for Colorado). The only code change is to
the generator `scripts/build_tax_forms_manifests.py`: the CO, IN and UT
`blocked` entries became document rows (`retry_batch: 3`, keeping their
batch-1/2 membership so every batch-1 and batch-2 queue row and manifest is
byte-identical after regeneration), a `US_NETWORK_RETRY` stamp, a `BATCH_3`
tuple and note, and `batch_note` reading `retry_batch` first.
`uv run ruff check scripts/build_tax_forms_manifests.py` passes.

## Federal (`us`)

No change. The `us/form` and `us/guidance` scopes from batch 1 were not re-run.

## States, batch 3 (retry)

Batch rule (reviewer judgment): batch 3 is exactly the three
`blocked_primary_source` rows left by batches 1 and 2 (CO, IN from batch 1; UT
from batch 2), retried because the controller's route now exits from a US
address. No `done` or `agent_ready` row was reopened. Each host got one plain
request with the corpus user agent and one curl_cffi chrome120 impersonation,
20 s timeouts, at 2026-09-10T21:35:30Z, before any extraction.

All documents: document_class `form`, citation path
`us-xx/form/<agency>/ty2025/<form-id>`, version
`2026-09-10-tax-state-forms-ty2025`, PDF `single_block` (root + `document-1`),
`source_as_of` 2026-09-10, `expression_date` 2025-01-01, as in batches 1 and 2.

| state | index_url | index docs | taken | provisions | seconds | status |
|---|---|---|---|---|---|---|
| us-co | https://tax.colorado.gov/2025-individual-income-tax-forms | 45 DR-form landing pages (Main Returns 5, Tax & Voluntary Schedules 5, Payment Forms 8, Credit/Subtraction/Deduction 27) | 2: DR 0104 (2025, 8 pp, rev. 10/03/25), DR 0104 Book (2025 filing guide, 88 pp, rev. 10/29/25) | 4 | 4 | agent_ready |
| us-in | https://www.in.gov/dor/tax-forms/individual/current/ | 54 unique Download.aspx links (58 listed; full-year residents 14, part-year/nonresidents 15, other 31) | 2: 2025 IT-40 Form (State Form 154, R24 / 9-25), 2025 IT-40 Booklet (SP 265, 12-25, 56 pp) | 4 | 3 | agent_ready |
| us-ut | https://tax.utah.gov/forms-pubs/ | 517 unique PDF links (618 table rows; 231 current; Individual Income 103, 21 current) | 2: TC-40 Basic (2025 return, 3 pp), TC-40 Instructions (2025 booklet, 34 pp) | 4 | 2 | agent_ready |

Per-index families (every family seen, counts, taken) are in each queue row's
`index_families` list and `notes`, and in `STATES[...]["index_families"]` /
`["inventory"]` of the generator.

Retry results, with the exact responses (2026-09-10T21:35:30Z):

- Colorado: `tax.colorado.gov` forms index, HTTP 403 CloudFront "ERROR: The
  request could not be satisfied" to the plain request with the corpus user
  agent; HTTP 200 (nginx) to chrome120 impersonation. The DR 0104 landing pages
  and the 2025 PDFs behave the same way (plain 403, impersonated 200,
  `application/pdf`). The batch-1 guess `DR0104_Book_2025.pdf` is 404; the
  publisher's 2025 files are `Book104_2025.pdf` and `DR0104_2025.pdf`, linked
  from `/DR0104Booklet` and `/DR0104`. Served by the publisher's own host with
  TLS verified, so the manifest sets the extractor's existing
  `request: {browser_user_agent, browser_impersonation, browser_impersonation_direct}`
  (NH precedent, `manifests/us-ma-2026-surtax-guidance.yaml`). Not a workaround
  of a geo block: the plain request is what CloudFront refuses now.
- Indiana: the in.gov DOR index serves plainly (200) as before; `forms.in.gov/
  Download.aspx?id=16914` and `id=16915` now answer HTTP 200 `application/pdf`
  (Cloudflare) to both the plain and the impersonated request, where every mode
  got the Cloudflare "Sorry, you have been blocked" 403 from Europe. No
  `request` keys configured. The host names files by content-disposition
  (`IT-40 (9-25) Fillable.pdf`, `IT-40 Instructions (12-25).pdf`); the index page
  is recorded as `source_url`, the Download.aspx URL as `download_url`.
- Utah: `tax.utah.gov/forms` answers 301 to `/forms-pubs/`, which serves HTTP 200
  to the plain request (Cloudflare, no challenge) and HTTP 403 (Cloudflare
  challenge) to chrome120 impersonation, so no `browser_impersonation` is
  configured (the DC pattern from batch 1). `tax.utah.gov/forms/current/tc-40.pdf`
  answers 301 to `https://files.tax.utah.gov/tax/forms/current/tc-40.pdf`, and the
  file host serves the PDFs (S3, 200) in both modes. Batch 2 probed
  `files.tax.utah.gov/forms/current/...` (no `/tax/` segment), which is a real
  404 on that host; the index links `/tax/forms/<year or current>/`. The
  batch-2 note's "Cloudflare challenge in all three modes" is therefore not
  reproducible from this network for the plain request; whether the earlier
  challenge was geographic or transient is not determinable from here.

No host stayed blocked; no "retried ..., same failure" note was appended.

## Access notes

- TLS: no chain problems; no bundle added under `data/certs/`; verification never
  disabled; no proxy or mirror used.
- Colorado DOR: chrome120 TLS impersonation of the publisher's own host, as above.
  The DR 0104 Booklet landing page's descriptive text still lists the 2024
  contents while linking the 2025 PDF (publisher text lag; the 2025 PDF's own
  cover reads "2025 104 BOOK").
- Indiana DOR: index inventory counted from the three tables under
  `#content_container_744163`; IN-DEP, IN-DEP-A and IN-W appear in both the
  resident and the nonresident table and ES-40 twice, hence 58 listed / 54 unique.
- Utah STC: the index is one 618-row table (Number, Name, Tax Type, Item Type,
  Status, Tax Year, ...); counts by Tax Type and Status come from that table.

## Counts

Scopes: 3 (us-co, us-in, us-ut form). Documents: 6. Provisions: 12 = CO 4 + IN 4
+ UT 4 (per state: two document roots plus two body-bearing `document-1` rows;
body lengths CO 10,923 / 179,708, IN 5,434 / 289,788, UT 2,686 / 149,570 chars).
Coverage `complete: true` for every scope, 0 missing, 0 extra, 0 duplicate
provision or source citations; citation paths verified unique per provisions
file by an independent script and equal to the inventory set; no new
citation_path exists in any other provisions JSONL under
`data/corpus/provisions/<jurisdiction>/` (16 files checked for us-co, 9 for
us-in, 7 for us-ut, all classes); every inventory item names a non-symlink
regular file under `sources/<jurisdiction>/form/<version>/` whose SHA-256
matches, and every provision's source path is in the inventory. Index documents
found versus taken: 45/2 (CO), 54/2 (IN), 517/2 (UT).

Extraction seconds: CO 4, IN 3, UT 2. Pre-extraction probes: eight URLs in both
modes, under one minute. `--verify` probe of all 62 manifest documents (batches
1-3): 0 failures, 25 s.

Artifacts (unsigned, awaiting controller; not committed; written to the main
checkout's corpus root because this worktree is sparse):

- `data/corpus/sources/us-xx/form/2026-09-10-tax-state-forms-ty2025/official-documents/*`
- `data/corpus/{inventory,provisions,coverage}/us-xx/form/2026-09-10-tax-state-forms-ty2025.*`
  for xx in co, in, ut

Rebuild:

```bash
uv run python scripts/build_tax_forms_manifests.py --verify   # probe every URL
AXIOM_CORPUS_BASE=/Users/pavelmakarchuk/axiom-corpus/data/corpus uv run python scripts/build_tax_forms_manifests.py
BASE=/Users/pavelmakarchuk/axiom-corpus/data/corpus
for j in co in ut; do
  uv run axiom-corpus-ingest extract-official-documents --base $BASE \
    --version 2026-09-10-tax-state-forms-ty2025 --manifest manifests/us-$j-individual-income-tax-forms-ty2025.yaml
done
```

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
in the sparse worktree: 255 passed, 10 failed, 2 skipped (41 s). The 10 failures
are the known sparse-checkout `FileNotFoundError`s (BE rulespec promotion, NY
TANF compatibility x2, BE source promotion, AK/CT/MI/MT/ND/NY SNAP manual tests),
identical to batches 1 and 2. No test references the files added here.

## Reviewer judgments

1. Batch membership: the three blocked rows only; nothing reopened. Batch-1/2
   rows and manifests unchanged (verified by regenerating: only the three new
   manifests, the three queue rows and `status_counts` differ).
2. Estimated-tax documents not taken: DR 0104EP (2025) and ES-40 both carry an
   estimated-tax worksheet, and the work order's "estimated-tax computation
   document where the publisher lists one" could be read to include them.
   Colorado lists DR 0104EP under Payment Forms and Indiana lists ES-40 as a
   payment voucher; batch 2 left the equivalent NJ-1040-ES, NM PIT-ES and VT
   IN-114 untaken, so the same line is held here for consistency. A reviewer who
   reads the rule the other way can add both rows to the generator; no other
   state in the queue took an estimated voucher. Utah's TC-546 is a coupon only.
3. No separate rate schedule exists for any of the three (flat-rate states; the
   rate is stated in each booklet: Colorado 4.4% in the DR 0104 Book line-13
   instructions), so taken_count is 2 each (DC/IA/ID/MS/MT precedent).
4. Schedules the return requires (Indiana Schedules 3, 7 and CT-40; Utah TC-40A/
   TC-40W; Colorado DR 0104AD/CR/CH) were not taken, as in DC/MS/MT; Utah's
   `tc-40full` (return plus schedules), Mini Packet and Full Packet are
   compilations without instructions and were not taken (VT booklet precedent).
5. Colorado uses browser TLS impersonation through the extractor's existing
   `request` keys because plain requests are refused by the publisher's own edge
   from this network too (not only geographically); TLS stays verified.
6. Utah's index_url is the redirect target `/forms-pubs/` (the URL the publisher
   serves), not the `/forms` alias the batch-2 row carried; Colorado's index_url
   is the TY2025 forms page reached from the 2025 tab of the landing page the
   batch-1 row carried, because that page is the publisher's TY2025 inventory.
7. Indiana's `source_url` is the index page and `download_url` the opaque
   Download.aspx id, like the NM RealFile and DE file-host precedents; the existing
   `us-in/guidance` source-hold scope (2026-07-24) that records the portal listing
   was left untouched.
8. The UT batch-2 block note is corrected rather than appended: part of it (the
   file-host 404s) was a wrong path on the agent's side, recorded above.

Remaining (controller): `sign-ingest-manifest` per scope, immutable release
selector, `publish_corpus.py --dry-run`, then publish and activate. The TAX state
queue has no blocked rows left.
