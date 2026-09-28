# WIC: state policy manuals, batch 2 (NJ, VA, WA, AZ, TN, MA, IN, MD, MO, WI)

Date: 2026-09-10
Program: WIC (board Year 1 list; `manifests/wic-agent-queue.yaml`)
Branch: `discovery/ingest-wic`
Previous run: `docs/ingest-runs/2026-09-10-wic-fns-guidance-and-state-manuals.md` (batch 1)

Timing: started_at 2026-09-10T18:33:33Z, finished_at 2026-09-10T19:02:17Z (agent wall time 1724 seconds, about
29 minutes, measured just before the commit that carries this note). Extraction wall time per jurisdiction
(final, complete runs):

| scope | started | elapsed_seconds | documents | provisions |
|---|---|---|---|---|
| us-md / manual | 2026-09-10T18:53:42Z | 77 | 8 | 16 |
| us-nj / manual | 2026-09-10T18:53:45Z | 5 | 9 | 18 |
| us-wa / manual | 2026-09-10T18:53:49Z | 24 | 33 | 66 |
| us-va / manual | 2026-09-10T18:57:06Z | 29 | 147 | 294 |

Totals: 4 scopes, 197 documents, 394 provisions (one root plus one body provision per document), coverage
`complete: true` for every scope, 0 missing, 0 extra, 0 duplicate citation paths (checked directly in each
provisions JSONL, not only via the coverage report), and no new citation path exists in any other provisions
JSONL under `data/corpus/provisions/<jurisdiction>/` (checked against every other scope of each state before
extraction). Smoke runs before the full runs: NJ and WA (`--limit 2`, plain client) into a scratch base, both
complete. Jurisdictions attempted 10 (NJ, VA, WA, AZ, TN, MA, IN, MD, MO, WI); extracted 4 (VA, WA, MD, NJ;
NJ is a flagged partial); blocked 6 (AZ, TN, MO, MA, IN, WI; reasons below). Batch-1 blocked rows NY, FL, IL,
OH were re-checked once (below).

Conventions unchanged from batch 1: document_class `manual`, version `2026-09-10-wic-state-policy-manual`, one
document per policy/chapter PDF listed on the agency's own manual index, citation path
`us-xx/manual/<agency>/wic/<section label>`, `single_block` extraction, expression date = CLI value 2026-09-10.

## Selection

The next ten states by population after batch 1's ten: NJ, VA, WA, AZ, TN, MA, IN, MD, MO, WI. Every state has a
queue row; extracted rows are `agent_ready`, blocked rows are `blocked_primary_source` with the exact failure.

## Extracted

| state | index_url | index families (count) | taken |
|---|---|---|---|
| VA | https://www.vdh.virginia.gov/wic/wic-policy-and-procedures-manual/ | policy PDFs 146 (functional areas I-VIII and XII); overview 1; printed TOC 1; forms (IX) 39; appendices (X) 12; glossary (XI) 1; one file linked twice 1 | 147 (146 policies + overview) |
| WA | https://doh.wa.gov/public-health-provider-resources/public-health-system-resources-and-services/local-health-resources-and-tools/wic/policy-procedures | chapter PDFs 31 (Volume 1: 23 of chapters 1-25, chapters 4 and 13 vacant; Volume 2: 8); chapter-section "Required Guidance" PDFs 2; revision tables / notices of revision 25; policy-revision PDF 1; post-PHE guidance PDFs 27; required-local-agency-policies list 1; staff tools, forms and other files (PDF/DOCX/XLSX) 47 | 33 (chapters + the two chapter-section PDFs) |
| MD | https://health.maryland.gov/phpa/wic/Pages/wic-policy.aspx | chapter PDFs 8 (each a compiled chapter of numbered policies: Outreach, Certification, Food Packages, Food Delivery, Nutrition Education, Financial, Local Agency Operations & Management, Farmer's Market) | 8 |
| NJ | https://www.nj.gov/health/fhs/wic/vendors/policies.shtml | vendor-management P&P PDFs 9 (P&P 1.31-1.50); other PDF 1 (privacy notice) | 9 (partial manual, see judgments) |

Access notes per publisher: vdh.virginia.gov, doh.wa.gov, health.maryland.gov and nj.gov all serve the index and
PDFs to the plain client with a browser User-Agent; no impersonation, range backend or CA-bundle extension was
needed for any batch-2 publisher. MD and NJ PDF hrefs contain literal spaces (NJ also double spaces) and are
percent-encoded by the generator, as PA's were in batch 1. `REQUESTS_CA_BUNDLE` still pointed at
`data/certs/wic-state-ca-bundle.pem` (certifi + the two batch-1 intermediates, rebuilt by the generator) for every
run; no new intermediate was needed and verification was never disabled.

VA labels: each Virginia policy prints its number on page one ("Policy: CRT 05.2"); several newer files are named
by title only (e.g. `Breastfeeding-Promotion-and-Support.pdf`, BF 01.0), so the generator downloads each policy
PDF once and labels it from the page-one number, falling back to the filename code. Headers and filenames never
disagreed. One policy, "Remote WIC Services" (functional area XII), prints no policy number and is labeled by
title (`remote-wic-services`). Labels are lowercased in the citation path (`us-va/manual/vdh/wic/crt-05.2`,
`.../ned-02.1`, `.../ep-1.0`, `.../overview`).

WA labels: `volume-1-chapter-N`, `volume-2-chapter-N`, and `volume-1-chapter-25-section-4` /
`volume-2-chapter-1-section-3` for the two chapter-section "Required Guidance" PDFs the index lists under their
chapters. Volume 2 Chapter 3 is published as "Draft Chapter 3" (metadata `working_draft: true`); Volume 2
Chapter 7's link text is "Record Retention" without a chapter prefix, so labels come from the h3 chapter headings
that structure the page, not from link text.

MD labels: `chapter-1` .. `chapter-8`. The chapter files are large compilations (Chapter 2 Certification is 424
pages, about 750 KB of text in one body provision).

NJ labels: `1.31`, `1.32`, `1.33`, `1.34`, `1.35`, `1.38`, `1.45`, `1.47`, `1.50` (the manual's own P&P numbers;
functional area I, Vendor).

## Blocked (nothing downloaded; no mirrors, reposts, proxies or archived copies used)

- AZ (azdhs.gov): the Arizona WIC Policy and Procedure Manual chapters exist as PDFs under
  `azdhs.gov/documents/prevention/azwic/manuals/policy/`, but azdhs.gov answers every request for the
  local-agencies index page and for the chapter PDFs with a Cloudflare "Attention Required!" HTTP 403: plain
  requests, browser user agent, curl with browser headers, curl_cffi impersonation (chrome120/124/131, safari17,
  firefox133, edge101, android chrome) and the Claude fetch proxy.
- TN (tn.gov): individual policies of the WIC Policy & Procedures Manual are hosted on tn.gov
  (`content/dam/tn/health/program-areas/wic/FY2022-ADM-01-03-02-Access-to-WIC-Services.pdf`), but www.tn.gov
  answers HTTP 403 (`awselb/2.0`) or times out for every client tried (plain requests, browser UA, curl with browser
  headers, curl_cffi chrome120/124/131, safari17, firefox133, edge101, android chrome, the Claude fetch proxy), so
  neither the WIC pages nor a manual index could be read from the publisher.
- MO (health.mo.gov): the WIC Operations Manual (WOM) is published only behind the WIC Local Agency Portal login;
  the manual index and every section URL redirect to `health.mo.gov/topic/781/login`, and the public WIC pages link
  no manual.
- MA (mass.gov): the Massachusetts WIC Program Manual (PM) is named in the FFY 2027 WIC state plan as the document
  the state office updates, but it is not published: the WIC organization page, the providers page and the
  state-plan page link no manual (the state plans are a different document family). mass.gov also answers 403 to
  non-browser clients.
- IN (in.gov): the Indiana WIC Policy and Procedure Manual is not published; the WIC Staff page links only the
  Indiana WIC Disaster Plan, and the WIC home, eligibility and vendor pages link only the vendor manual and
  participant material.
- WI (dhs.wisconsin.gov): the Wisconsin WIC Policy and Procedure Manual is not published; the WIC home, Providers
  and Professionals and local-project pages link no manual, candidate `/wic/ppm*` and `/wic/local-agency*` paths
  answer 404, and the only policy-like PDFs on the host (`wic/certification-eligibility-coordination.pdf`,
  `wic/caseload-management.pdf`) are FY 2025 state-plan sections, not a manual index.

## Batch-1 blocked rows, re-checked once (about three minutes total)

Each agency page was fetched once more at 2026-09-10T18:47Z and searched for manual/policy/procedure links; the
queue row note now ends "re-checked 2026-09-10T18:47Z, still not published."

- NY: `health.ny.gov/prevention/nutrition/wic/` still links no manual.
- FL: `floridahealth.gov/individual-family-health/womens-health/wic/` still links no manual.
- IL: `dhs.state.il.us/page.aspx?item=36418` still redirects to "Page Not Found" (item=27893).
- OH: `odh.ohio.gov/know-our-programs/Women-Infants-Children/Local-Staff` still links no manual.

## Artifacts (unsigned, uncommitted, awaiting controller)

In the main checkout's corpus root (`/Users/pavelmakarchuk/axiom-corpus/data/corpus`, where batch 1's artifacts are;
this worktree is sparse and excludes `data/corpus`):

- `data/corpus/sources/us-xx/manual/2026-09-10-wic-state-policy-manual/official-documents/*.pdf`
- `data/corpus/{inventory,provisions,coverage}/us-xx/manual/2026-09-10-wic-state-policy-manual.{json,jsonl,json}`
  for xx in va, wa, md, nj.

Rebuild (the generator's new `--only` flag limits a run to selected queue rows so batch-1 manifests are not
regenerated; without it every row is rebuilt):

```bash
uv run python scripts/build_wic_manifests.py --only us-va,us-wa,us-md,us-nj,us-az,us-tn,us-mo,us-ma,us-in,us-wi,us-ny,us-fl,us-il,us-oh
export REQUESTS_CA_BUNDLE=$PWD/data/certs/wic-state-ca-bundle.pem
for st in va wa md nj; do
  uv run axiom-corpus-ingest extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-wic-state-policy-manual --manifest manifests/us-$st-wic-policy-manual.yaml \
    --source-as-of 2026-09-10 --expression-date 2026-09-10
done
```

Lint: `uv run ruff check scripts/` is clean. It fixed the batch-1 F841 (unused `agency` in
`build_wic_manifests.main`) and the pre-existing findings ruff reported in `scripts/` (an unused import in
`build_liheap_state_plan_manifests.py`; unused import, import order and one-line compound statements in
`draft_program_work_orders.py`); no behavior change in either.

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
in this sparse worktree: 255 passed, 2 skipped, 10 failed. All ten failures are the known pre-existing
FileNotFoundError / same-file assertions on `data/corpus/...` fixtures absent from this sparse checkout (BE rulespec
promotion, NY TANF compatibility x2, BE source promotion, and the AK/CT/MI/MT/ND/NY SNAP manual tests), identical to
batch 1; none touch WIC code or manifests. No adapter code was added (every batch-2 publisher works with the existing
`extract-official-documents` options), so no new tests.

GitNexus impact analysis was not run: the GitNexus MCP tools were unavailable in this session. No existing
function outside `scripts/build_wic_manifests.py` was modified; in that script `main` gained the `--only`
argument and the batch-2 rows, and four builders (`build_va`, `build_wa`, `build_md`, `build_nj`) plus
`pdf_header_policy_code` were added.

## Reviewer judgments

1. NJ partial manual. nj.gov publishes only functional area I (vendor management, P&P 1.31-1.50) of the "WIC
   Services Policy and Procedure Manual", on the agency's Vendor Policies and Procedures page, and says some
   policies are redacted. The nine published policies are taken from the publisher's own index under
   `us-nj/manual/doh/wic/<P&P number>`; the row is `agent_ready` with the note "Partial: only the
   vendor-management functional area of the manual is published." A reviewer may prefer to treat NJ as
   blocked for encoding purposes; nothing here stands in for the unpublished certification chapters.
2. VA scope. Functional areas I-VIII (policies) and XII (emergency-procedure policies EP 1.0-4.0 and Remote WIC
   Services) plus the manual Overview are taken. Not taken: IX Forms (39), X Appendices (12, a mix of forms,
   letters and regulation reprints), XI Glossary (1), the printed TOC, and the "Nutrition Services" link in XII,
   which points at the WIC-395 form. FDS-02.2.4 is linked twice ("Food Package V - Pregnant and Providing" and
   "Mostly Breast Milk"); the one file is taken once.
3. VA labels from page-one policy numbers rather than the index (the index has no numbers), with filename codes
   as fallback; the two never disagreed. "Remote WIC Services" is labeled by title because it prints no number.
4. WA scope. Chapter PDFs of both volumes plus the two chapter-section "Required Guidance" PDFs are taken. Not
   taken: tables of revisions (25), the "Certifying Participants after Delivery" policy-revision PDF, the 27
   post-public-health-emergency guidance PDFs (remote certification, remote benefit issuance, mailed-card letters in
   eleven languages, post-PHE separation-of-duties review, etc.), the required-local-agency-policies list, and
   staff tools/forms. A reviewer may want the post-PHE remote-services policies taken as a later revision.
5. WA Volume 2 Chapter 3 is the publisher's "Draft Chapter 3" (metadata `working_draft: true`), taken because it
   is the only version the index offers (cf. TX in batch 1).
6. MD chapters are compilations (up to 424 pages in one body provision); a later revision could split them by the
   numbered policies in each chapter's table of contents.
7. Blocked publishers were not worked around (AZ Cloudflare, TN WAF, MO login, MA/IN/WI not published). For AZ and
   TN the manual demonstrably exists on the publisher's host; both are access blocks, not publication gaps, and
   would be the first retries if the publishers' front doors change.
8. Expression dates are the CLI value 2026-09-10 for every document (batch-1 convention), although VA policies
   print effective dates and WA chapters print revision dates.
9. Re-check budget: the four batch-1 blocked agencies were re-fetched once each (one page each, about three
   minutes in total), not re-researched.

Remaining (controller): `sign-ingest-manifest` per scope, immutable release selector,
`publish_corpus.py --dry-run`, then publish and activate. Third state batch: the remaining states; retry AZ and
TN if their front doors stop blocking non-browser clients, and NY/FL/IL/OH/MA/IN/WI/MO if their agencies
publish an index.
