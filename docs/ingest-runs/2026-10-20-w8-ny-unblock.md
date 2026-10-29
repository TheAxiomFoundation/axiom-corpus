# Wave 8, group `ny`: newly reachable New York sources (TANF, SSI, Medicaid)

Date: 2026-10-20 (UTC timestamps below).
Task: re-probe the four New York rows that have been blocked since 2026-09-10 and ingest what is now reachable, in this
order: (1) TANF `us-ny`, the OTDA Temporary Assistance Source Book; (2) SSI `us-ny`, the OTDA State Supplement Program
documents; (3) Medicaid `us-ny`, the NY State of Health income-levels chart.
Queue rows: `manifests/tanf-agent-queue.yaml` (`us-ny`), `manifests/ssi-agent-queue.yaml` (`us-ny`),
`manifests/medicaid-agent-queue.yaml` (`us-ny`, family `w6_bundle_gap`).
Index inventory script: `scripts/inventory_nysoh_assistor_toolkit.py`.

**Headline: the probe this run was given did not reproduce on `otda.ny.gov`.** Two of the three targets stay blocked.
The one target that is genuinely reachable (`info.nystateofhealth.ny.gov`) was never a fingerprint block at all: it is a
User-Agent block that the extractor's own built-in browser User-Agent fallback already passes.

## Worktree, branch, timing, disk

- Worktree `~/axiom-corpus-worktrees/w8-ny`, branch `discovery/ingest-w8-ny` cut from `main` 393127f8b. `uv sync --extra
  dev` was needed: the worktree's `.venv` held no dev extras, so `uv run pytest` had been resolving Anaconda's pytest.
- Every extraction wrote to the main checkout's corpus root (`--base <axiom-corpus checkout>/data/corpus`).
  Artifacts are unsigned and uncommitted; `data/corpus` is not tracked in that checkout. Nothing was signed, locked,
  pushed to R2 or loaded to Supabase. `manifests/releases/` and `manifests/program-bundles/` are untouched. Only
  read-only git commands ran in `~/axiom-corpus`.
- Timing: started 2026-10-20T18:52:05Z; duplicate-work check and baseline tests to 19:00Z; publisher probes
  18:58-19:06Z; index inventory 19:06-19:08Z; Medicaid extraction 19:08:34Z, **5 s** wall for all three documents;
  checks, queue rows and this note to 19:40Z. TANF extraction seconds: 0 (blocked, nothing fetched). SSI extraction
  seconds: 0 (blocked, nothing fetched). Finished 2026-10-20T19:45Z; wall time about 53 minutes.
- Impact analysis: not run. The GitNexus MCP tools are not available in this session. No library function under `src/`
  was changed.

## Duplicate-work check (repo rule, before any edit)

- `gh search issues "New York OTDA" --repo TheAxiomFoundation/axiom-corpus`: no results.
- `gh search prs "otda" --repo TheAxiomFoundation/axiom-corpus --state open`: no results.
- `gh pr list --state open`: 30 open PRs; each one's file list was checked against
  `manifests/{tanf,ssi,medicaid}-agent-queue.yaml`. Only **#830** touches one of them (`ssi-agent-queue.yaml`), and its
  diff changes the *federal* eCFR row (20 CFR 416 Appendix to Subpart K), not the `us-ny` row. #773 is NYC
  Administrative Code income tax, not a benefit queue. No row of this run is covered by an open PR, so no row was
  skipped for duplication.
- Two open PRs are relevant as constraints, not duplicates: #897 and #899 refuse local machine paths in signed ingest
  manifests. This run's manifest names no `local_path` and the provisions carry no `file:` URL or `/Users/` path
  (checked).

## Publisher access (2026-10-20, re-verified before use; TLS verification never disabled)

The probe results handed to this run claimed that `otda.ny.gov` "answers 200 to a curl_cffi chrome120 fingerprint".
That is true of the status line and false of the body.

| URL | Plain client (Axiom UA) | Plain client (browser UA) | curl-cffi chrome120 |
| --- | --- | --- | --- |
| `https://otda.ny.gov/programs/temporary-assistance/` | reset / 200 challenge | 200 challenge, 6,647 B | 200 **challenge**, 6,647 B |
| `https://otda.ny.gov/programs/temporary-assistance/TASB.pdf` | 200 challenge, 6,650 B | 200 challenge | 200 **challenge**, 6,650 B |
| `https://otda.ny.gov/programs/ssp/` | connection reset by peer | reset | 200 **challenge**, 6,650 B |
| `https://info.nystateofhealth.ny.gov/` | **403**, 919 B (CloudFront) | **200**, 86,414 B | 200, 86,414 B |
| `https://info.nystateofhealth.ny.gov/AssistorToolKit` | **403**, 919 B | **200**, 84,422 B | 200 |
| the three income-levels PDFs | **403**, 919 B | **200**, `application/pdf` | 200 |

- `otda.ny.gov` serves an F5/Shape TSPD JavaScript challenge: `window["bobcmn"] = ...` plus "Please enable JavaScript to
  view the page content. Your support ID is ...". Every Chromium, Edge and Firefox impersonation profile available in
  curl-cffi 0.15.0 returns that same page (chrome, chrome110, chrome120, chrome124, chrome131, chrome133a, edge101,
  firefox135: HTTP 200, 7,272-7,278 B, all challenge); `safari18_0` is reset by the peer. The challenge is bot
  detection. It was **not** solved, and no cookie replay, headless browser, mirror, repost, proxy or archived copy was
  used. Nothing was taken from `otda.ny.gov`.
- `info.nystateofhealth.ny.gov`: the 2026-10-06 wave-6 "CloudFront 403" is a **User-Agent block**, not a challenge. The
  host answers 403 (919 bytes) to the extractor's own `Axiom/1.0 (Legal Archive; ...)` User-Agent and 200 to the
  extractor's built-in `OFFICIAL_DOCUMENT_BROWSER_USER_AGENT` fallback, which `_needs_browser_fallback` already triggers
  on a 403. So the manifest needs **no** `request` option at all; `browser_impersonation` would have worked too and
  stays available if the host tightens.
- No CAPTCHA was bypassed, no TLS verification disabled, nothing added to `data/certs/`, no `REQUESTS_CA_BUNDLE`
  override needed (no broken chain seen).

## Target 1: TANF `us-ny` - BLOCKED (not taken)

Recorded primary source: `https://otda.ny.gov/programs/temporary-assistance/TASB.pdf` (OTDA Temporary Assistance Source
Book). Exact failure: the publisher's own index `https://otda.ny.gov/programs/temporary-assistance/` and the PDF itself
both return **HTTP 200 with a 6.6-7.3 KB F5/Shape TSPD JavaScript bot-challenge body and no page content**, to the plain
client and to all eight non-Safari impersonation profiles; Safari profiles are reset by the peer.

Consequence: the Source Book could not be confirmed on OTDA's own index, the index could not be inventoried, and no
companion policy document could be identified. `index_document_count` stays 1 (the row's own count, unverifiable),
`taken_count` 0, `queue_status` `blocked_primary_source`. The row's note now records the 2026-10-20 re-probe and the
explicit warning that an HTTP 200 on this host is not content.

Already held, unchanged by this run: the 2024-2026 TANF State Plan (`us-ny-tanf-state-plan`) and the Employment Policy
Manual (`2026-07-17-ny-snap-manuals`).

## Target 2: SSI `us-ny` - BLOCKED (not taken)

Recorded primary source: `https://otda.ny.gov/programs/ssp/` (OTDA State Supplement Program). Exact failure: the plain
client is **reset by the peer**; curl-cffi chrome120 returns **HTTP 200 with the same 6.6 KB TSPD JavaScript challenge
body**. No payment-standard or eligibility document exists to confirm without that index, so none was taken.
`index_document_count` stays `null`, `taken_count` 0, `queue_status` `blocked_primary_source`.

Already held, unchanged: the SSA regional description in the federal family,
`us/manual/ssa/poms/si/ny01415.026`.

## Target 3: Medicaid `us-ny` - TAKEN

### The publisher's own index

The row names `https://info.nystateofhealth.ny.gov/sites/default/files/2026 Income Levels_for Medicaid, CHPlus & EP.pdf`.
Finding the index that lists it took three dead ends, recorded here because they will recur on this publisher:

1. `/resources` (the marketplace's resources library) **is** server-rendered (`<article class="node
   node--type-resource ...>` teasers, 10 per page, `?page=N`), and its `resource_type` facets work server-side. Its
   items are node aliases; **none of the facets lists these PDFs**. Crawled in full: `resource_type:80` Materials
   (English) 40 items, `resource_type:5` Policies 43 items, `resource_type:90` Estimate Financial Help 1 item.
2. `/search?search=...` ignores the query server-side ("You must have JavaScript enabled to use this form"); its facet
   counts are identical for every query, so the result list is JavaScript-only.
3. The Drupal sitemap (`/sitemap.xml`, 2 pages, 3,657 URLs) holds pages and news only: **0** `/resource/` URLs and no
   income-levels URL. `/jsonapi` is 404.

The index that does list the document is the **Assistor Tool Kit** page,
`https://info.nystateofhealth.ny.gov/AssistorToolKit`, which prints the row's PDF under the label "2026 FPL Medicaid,
Child Health Plus, Essential Plan". Inventory (reproduce with `uv run --extra dev python
scripts/inventory_nysoh_assistor_toolkit.py`): **91 links in the main region, 61 document links**, in six families:

| Index family | Found | Taken |
| --- | ---: | ---: |
| `eligibility_income_chart_pdf` | 3 | **3** |
| `assistor_newsletter_pdf` | 45 | 0 |
| `identity_form_or_instruction_pdf` | 9 | 0 |
| `account_instruction_pdf` | 2 | 0 |
| `assistor_training_memo_pdf` | 1 | 0 |
| `qhp_benefit_attachment_pdf` | 1 | 0 |
| **Total** | **61** | **3** |

The income-chart family is the row's family and all three of its documents are current for the 2026 coverage year (each
one's HTTP `Last-Modified` is 2026-02-24): the named Medicaid/CHPlus/EP chart, the 2026 Child Health Plus Desk Aid and
the 2025 income levels that govern the 2026 qualified-health-plan year. All three were taken. The other 58 document
links were inventoried and not taken: assistor newsletters, identity forms (DOH-5088/5090/5091), account and
identity-proofing instructions, one HRA training memo and the QHP essential-health-benefits attachment are not
eligibility standards and none is named by the bundle-gap row.

### Scope and command

Manifest `manifests/us-ny-medicaid-income-levels-2026.yaml`, modelled on `manifests/us-ny-msp-income-standards-2026.yaml`
(the NY income-standards precedent): `document_class: guidance` for charts, per the wave-6 health convention, and
`us-ny/guidance/<agency>/...` citation paths with `nysoh` as the agency segment.

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base <axiom-corpus checkout>/data/corpus \
  --version 2026-10-20-w8-ny-medicaid \
  --manifest manifests/us-ny-medicaid-income-levels-2026.yaml
```

Version string: `2026-10-20-w8-ny-medicaid`, the wave-tagged form this task set. It matches the wave convention already
in the tree (`2026-10-06-w6-health-guidance-ny`, `2026-10-06-w6-benefits-guidance-ny`) and does not collide with the NY
guidance scopes already locked (`2026-09-14-msp-income-standards`, `2026-10-06-w6-benefits-guidance-ny`,
`2026-10-06-w6-income-tax-guidance-ny`).

Scope `us-ny/guidance/2026-10-20-w8-ny-medicaid`: 3 documents, 3 source files, 6 provisions (3 document roots, 3
`page-1` rows), 5 s.

| Citation path | Document | Body chars |
| --- | --- | ---: |
| `us-ny/guidance/nysoh/income-levels/2026-medicaid-child-health-plus-essential-plan` | 2026 Income Levels for Medicaid, Child Health Plus and Essential Plan | 0 (root) |
| `.../2026-medicaid-child-health-plus-essential-plan/page-1` | same, p.1 | 3,542 |
| `us-ny/guidance/nysoh/income-levels/2026-child-health-plus-desk-aid` | 2026 Child Health Plus Desk Aid | 0 (root) |
| `.../2026-child-health-plus-desk-aid/page-1` | same, p.1 | 1,313 |
| `us-ny/guidance/nysoh/income-levels/2026-plan-year-qualified-health-plans` | 2025 Income Levels for Qualified Health Plans, 2026 Plan Year | 0 (root) |
| `.../2026-plan-year-qualified-health-plans/page-1` | same, p.1 | 1,796 |

### Artifacts (uncommitted, unsigned, in the main checkout's corpus root)

| sha256 (first 16) | Bytes | Path under `data/corpus/` |
| --- | ---: | --- |
| `351c1af99e058800` | 325 | `coverage/us-ny/guidance/2026-10-20-w8-ny-medicaid.json` |
| `0bd542a5a3d62fe7` | 12,109 | `inventory/us-ny/guidance/2026-10-20-w8-ny-medicaid.json` |
| `0f8f59b9512373a6` | 20,307 | `provisions/us-ny/guidance/2026-10-20-w8-ny-medicaid.jsonl` |
| `56a4451f671d748b` | 199,023 | `sources/.../official-documents/us-ny-nysoh-income-levels-medicaid-chplus-ep-2026.pdf` |
| `adc190fe12736d0f` | 184,797 | `sources/.../official-documents/us-ny-nysoh-child-health-plus-desk-aid-2026.pdf` |
| `5d59a3c4f57ee862` | 161,759 | `sources/.../official-documents/us-ny-nysoh-income-levels-qhp-2026-plan-year.pdf` |

Each retained PDF's sha256 equals the live download's, fetched independently before extraction.

## Reviewer judgments

1. **The handed probe is wrong for `otda.ny.gov`, and the error is the status code.** chrome120 does return HTTP 200,
   but the body is the TSPD challenge, byte-for-byte the same failure the 2026-09-10 and 2026-09-13 notes record. The
   2026-09-10 note had already classified this correctly; this run reproduced it across eight profiles. TANF and SSI stay
   `blocked_primary_source`. Treat "200" on this host as no evidence of access.
2. **The OTDA block was not worked around.** The challenge is bot detection. Solving it (cookie replay, a JS runtime, a
   headless browser) is out of bounds, and no mirror, repost, proxy or archived copy was substituted. `law.cornell.edu`
   NYCRR pages already in the TANF row stay `excluded_secondary`; nothing was read from them.
3. **`info.nystateofhealth.ny.gov` never needed an impersonation fingerprint.** The wave-6 note recorded "CloudFront
   403, no documented fallback" and sent the row to OUTREACH. The 403 keys on the Axiom User-Agent; the extractor's own
   browser-UA fallback, which it already applies to a 403, answers 200. So no `request` option was added. This also
   means the row was reachable before today by the extractor's standard path, and the wave-6 block was a mis-diagnosis,
   not a publisher change.
4. **The Assistor Tool Kit is the right index, and the resources library is not.** The library is the site's nominal
   document index and it does not list these PDFs in any facet; the Tool Kit page prints the row's document by name. The
   note records the three dead ends so the next pass does not repeat them.
5. **Three documents taken, not one.** The task's "any current companion the publisher's index lists" is read as the
   index's own income-chart family. All three carry 2026-plan-year income standards and the same 2026-02-24
   `Last-Modified`. The QHP chart is marketplace, not Medicaid; it is taken because the index groups it with the
   Medicaid/CHPlus/EP chart as a current income standard, and its `metadata.program` says `ACA_MARKETPLACE`, so a later
   consumer can separate it.
6. **Index labels differ from document titles, and both are recorded.** The index prints "2026 FPL Medicaid, Child
   Health Plus, Essential Plan"; the PDF's own first line is "2026 Income Levels for Medicaid, Child Health Plus and
   Essential Plan". The manifest uses the document's printed title as `title` and keeps the index's wording in
   `metadata.index_label_as_printed`.
7. **The index's own URL encoding was used.** The queue row spells the PDF with a literal `,` and `&`; the index links
   it percent-encoded (`%2C`, `%26`). Both resolve to the same bytes; the manifest records the index's spelling and the
   queue row keeps its own, so the bundle generator's URL join still matches.
8. **Empty document-root bodies are correct here, not a `hollow_document_root` finding.** Each root has a `page-1`
   child that carries text, which is exactly the condition the 2026-10-13 hollow-root audit exempts.
   `ScopeContentScanner` over the new scope returns **0 findings**.
9. **The cross-scope uniqueness check is complete for 32 of 36 locked `us-ny` provisions files.** `corpus fetch --path
   data/corpus/provisions/us-ny` obtained 32; four `-r2026-10-13-hollow-roots` successor scopes
   (chip-state-plan, medicaid-state-plan, ny-snap-regulations, income-tax-regulations) report "no source holds it" -
   their bytes are in neither R2 nor the cache. Each is a successor of a base scope that *was* fetched and, by the
   hollow-root successors' construction, differs from it only in document-root rows, so it introduces no citation path
   the base scope lacks. No `us-ny/guidance/nysoh` path and no `income-level` path exists anywhere in the 8,697 paths
   checked.
10. **`expression_date` is 2026-01-01 for all three, not the file date.** The charts print 2026 coverage-year levels
    and carry no effective date of their own; the 2026-02-24 `Last-Modified` is recorded in
    `metadata.expression_date_note` instead. The QHP chart's `2025` names the FPL year, not its own year, and its note
    says so.
11. **The Medicaid row keeps its `work_order` and gains an inventory.** `blocked_count` drops 1 to 0, `queue_status`
    becomes `agent_ready`, and `run_note` now points at this note rather than the wave-6 health note.

## Queue rows and `status_counts`

- `manifests/medicaid-agent-queue.yaml`, `us-ny` family `w6_bundle_gap`: `blocked_primary_source` to `agent_ready`,
  `blocked_count` 1 to 0, plus `target_manifest`, `target_scope`, `index_url`, `index_document_count: 61`,
  `taken_count: 3`, `index_families` (the six families above) and a new note. `status_counts`: `agent_ready` 192 to
  **193**, `blocked_primary_source` 11 to **10**.
- `manifests/tanf-agent-queue.yaml`, `us-ny`: `queue_status` unchanged (`blocked_primary_source`); note extended with
  the 2026-10-20 re-probe; `index_families` added ("no index inventory possible"). `status_counts` unchanged.
- `manifests/ssi-agent-queue.yaml`, `us-ny`: `queue_status` unchanged (`blocked_primary_source`); note extended with the
  2026-10-20 re-probe; `index_families` wording sharpened to name the challenge. `status_counts` unchanged.
- All three files reconcile: a `yaml.safe_load` count of `queue_status` over `states` equals the declared
  `status_counts` (tanf 1/36/23/4 of 64 rows; ssi 30/23/6 of 59; medicaid 7/193/10/6 of 216).

## Checks

- Coverage `data/corpus/coverage/us-ny/guidance/2026-10-20-w8-ny-medicaid.json`: `complete: true`, `matched_count: 6`,
  `missing_from_provisions: 0`, `extra_provisions: 0`, `duplicate_provision_citations: 0`,
  `duplicate_source_citations: 0`.
- Citation-path uniqueness read directly off the provisions JSONL: 6 rows, 6 distinct `citation_path` values, no
  duplicate.
- Cross-scope: the 6 new paths intersected against every other `us-ny` provisions file on disk (32 files, 8,697 paths):
  **no collision**. Nothing had to be skipped. See judgment 9 for the four unobtainable successor scopes.
- `uv run --extra dev python scripts/validate_citation_paths.py --provisions <tree of the new file>`: 6 records, 6
  unique paths, `RESULT: OK`; new irregular segments 3 `page-N` (within baseline).
- Body text: every `page-1` row is non-empty (3,542 / 1,313 / 1,796 chars) and no PDF is image-only (PyMuPDF reports 0
  images and a full text layer on each of the three single-page PDFs), so **no `ocr: true` was needed**. Each document
  root is empty by design (judgment 8).
- `ScopeContentScanner` over the new scope: 0 findings, no `hollow_document_root`.
- No leaked local path: no `file:` URL and no `/Users/` string in the inventory or provisions; `metadata.download_url`
  is the official URL (PR #897/#899 constraint).
- `uv run ruff check scripts/inventory_nysoh_assistor_toolkit.py`: clean (`ruff format` applied).
- Tests, before any edit and again at the end:
  `AXIOM_CORPUS_PARTIAL_TESTS=1 uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents
  or discovery"`. Baseline (before the first edit) **18 failed, 341 passed, 2 skipped, 7,241 deselected**; final
  **18 failed, 341 passed, 2 skipped, 7,241 deselected**. The two `FAILED` lists are byte-identical (`diff` of the
  sorted lists is empty), so this run adds **no new failure**. The 18 are the known partial-tree set of the wave-6 and
  wave-7 notes (MT/ND/NY/AK/CT/MI SNAP manuals, SNAP child-support CA/DE, Armenia, BE, Wisconsin, Israel, SC): each
  reads a `data/corpus` artifact this worktree does not hold.
- `changelog.d/w8-ny-unblock.added.md` added.

## Rebuild

```bash
B=<axiom-corpus checkout>/data/corpus
uv run --extra dev python scripts/inventory_nysoh_assistor_toolkit.py          # the index inventory above
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base $B \
  --version 2026-10-20-w8-ny-medicaid \
  --manifest manifests/us-ny-medicaid-income-levels-2026.yaml
uv run --extra dev axiom-corpus-ingest coverage \
  --base $B \
  --source-inventory $B/inventory/us-ny/guidance/2026-10-20-w8-ny-medicaid.json \
  --provisions $B/provisions/us-ny/guidance/2026-10-20-w8-ny-medicaid.jsonl \
  --jurisdiction us-ny --document-class guidance --version 2026-10-20-w8-ny-medicaid --write
```

## Remaining work for New York

1. **TANF `us-ny` (OTDA Temporary Assistance Source Book): OUTREACH.** Three dates, two networks, nine client profiles,
   the same F5/Shape challenge. An engineering fix is not the right next step; ask OTDA for the Source Book, or for an
   address outside the TSPD-protected path, as the New York SNAP manuals were obtained.
2. **SSI `us-ny` (OTDA State Supplement Program): OUTREACH**, same host, same challenge. The SSP payment standards and
   eligibility rules have no confirmed official address until OTDA answers.
3. The `program_bundle_gaps_w6` sub-family on the TANF row (`additional_families`) stays
   `blocked_primary_source` for the same reason.
4. **Four `us-ny` `-r2026-10-13-hollow-roots` successor scopes have no obtainable bytes** (judgment 9). This is not a NY
   source problem but it does block a byte-exact `us-ny` uniqueness sweep; whoever owns the hollow-root successors
   should publish or re-create them.
5. The new scope is unsigned and unlocked, and no release selector names it. The controller decides whether
   `us-ny/guidance/2026-10-20-w8-ny-medicaid` enters the next named selector.
6. `info.nystateofhealth.ny.gov` is now known-reachable through the extractor's standard browser-UA fallback. Other
   wave-6 health rows that were sent to OUTREACH on the same "CloudFront 403" diagnosis should be re-checked the same
   way, with the body read, not the status code.
