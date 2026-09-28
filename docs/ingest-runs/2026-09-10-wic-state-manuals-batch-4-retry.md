# WIC: state policy manuals, batch 4 (retry from a US network: OR, KY extracted; AZ, TN, SC, LA, KS, AR, MA, IL still blocked; then WV, ME, RI extracted; NE, ID, HI, NH, MT, DE, SD blocked)

Date: 2026-09-10
Program: WIC (board Year 1 list; `manifests/wic-agent-queue.yaml`)
Branch: `discovery/ingest-wic`
Previous runs: `docs/ingest-runs/2026-09-10-wic-fns-guidance-and-state-manuals.md` (batch 1),
`docs/ingest-runs/2026-09-10-wic-state-manuals-batch-2.md` (batch 2),
`docs/ingest-runs/2026-09-10-wic-state-manuals-batch-3.md` (batch 3)

Timing: one agent session, started_at 2026-09-10T21:33:13Z, finished_at 2026-09-10T21:56:02Z (wall time 1369 seconds,
about 23 minutes, measured just before the commit that carries this note). The controller's network exited
from a US address for this run, which is why hosts that answered 403 or did not resolve in batches 2 and 3 were retried.
Extraction wall time per jurisdiction (final, complete runs):

| scope | started | elapsed_seconds | documents | provisions |
|---|---|---|---|---|
| us-ky / manual | 2026-09-10T21:42:45Z | 12 | 10 | 20 |
| us-or / manual | 2026-09-10T21:43:47Z | 24 | 88 | 176 |
| us-wv / manual | 2026-09-10T21:52:35Z | 30 | 140 | 280 (rerun after judgment 8; the first run at 21:51:05Z, 31 s, wrote 141 documents / 282 rows and was superseded) |
| us-me / manual | 2026-09-10T21:51:06Z | 25 | 111 | 222 |
| us-ri / manual | 2026-09-10T21:51:05Z | 3 | 2 | 4 |

Totals: 5 scopes, 351 documents, 702 provisions (one root plus one body provision per document), coverage
`complete: true` for every scope, 0 missing, 0 extra, 0 duplicate citation paths. Each scope was checked independently
of the coverage report by a script over the provisions JSONL and the manifest: every manifest citation path has exactly
one root row and exactly one body row under it, no path repeats, every body row has non-empty text (smallest body 379
characters, WV), every inventory item's citation path is a provision row, every root row's `source_url` matches its
manifest document and its `source_path` lies under `sources/<jurisdiction>/manual/<version>/`; and no new citation path
exists in any other provisions JSONL under `data/corpus/provisions/<jurisdiction>/` (6/6/6/9/9 other files for
KY/OR/WV/ME/RI; the existing `us-ky/manual/2026-07-17-ky-snap-manual`, `us-or/manual/2026-07-16-or-programs-eligibility-notebook`
and `us-wv/manual/*` scopes share a jurisdiction but no path). Smoke run before the full runs: OR (`--limit 2`) into a
scratch base, complete; the other four scopes are plain PDF downloads on the same extractor path and were run directly.

Conventions unchanged from batches 1-3: document_class `manual`, version `2026-09-10-wic-state-policy-manual`, one
document per policy/chapter PDF listed on the agency's own manual index, citation path
`us-xx/manual/<agency>/wic/<section label>`, `single_block` extraction, expression date = CLI value 2026-09-10, and
`REQUESTS_CA_BUNDLE=data/certs/wic-state-ca-bundle.pem` (certifi plus the two batch-1 intermediates, rebuilt by the
generator; gitignored under `data/`) for every run. No new intermediate was needed (`data/certs/` is unchanged) and TLS
verification was never disabled (Delaware's chain failure, below, was left as a failure).

## Part 1: retry of every blocked row

At 2026-09-10T21:34Z every `blocked_primary_source` row's index URL (the URL recorded in the queue) was fetched once
with the plain client and a browser User-Agent, 20 s timeout, from the US network. Rows whose host now answered were
followed to their manual index where one exists; one `curl_cffi` impersonation was spent only where the plain client's
answer needed disambiguation (AZ, NH, DE).

| state | batch-2/3 failure | retry result | outcome |
|---|---|---|---|
| OR | www.oregon.gov SERVFAIL at every resolver | resolves; wicpolicy.aspx index 200 | extracted (88) |
| KY | 403 for WIC page and site root | WIC page 200; 'WIC and Nutrition Manual' heading lists 10 policy-group PDFs | extracted (10) |
| AZ | Cloudflare 403 to every client | 200, but the batch-2 Local Agencies URL is a soft 404 and the relocated page (agencies/index.php) has a 'WIC Manuals' sidebar link to an in-page anchor the served page does not contain (same 80,005-byte page to the plain client and to one impersonation); candidate manuals sub-pages are the same soft 404; the manuals/policy directory answers 403 | still blocked: no manual index published as served |
| TN | 403 (awselb) or timeout | host answers (2 of 6 requests still failed with a TLS EOF); the batch-2 WIC URL is 404; the relocated page health/wic.html links participant, vendor and nutrition material, the WIC rule 1200-15-02 and the vendor Food Package Policy, no manual index; a manual policy PDF known from batch 2 still answers 200 to HEAD | still blocked: manual not indexed |
| SC | 403 (CloudFront) | 200; WIC program page and its WIC Resources, Healthcare Providers & Formulas and South Carolina WIC subpages link no manual; apps.dhec.sc.gov/Health/WIC is a participant sign-in portal | still blocked: manual not published |
| LA | 403 (Cloudflare) | 200; Bureau of Nutrition Services WIC page, LDH Forms & Policies page and louisianawic.org (participant, vendor, medical-provider pages) link no manual | still blocked: manual not published |
| KS | 403 (Cloudflare) | 200; the For Local WIC Agencies page links the Policy & Procedure Manual folder (DocumentCenter/Index/903), which is an empty React shell (`window.folderId = "903"`) whose documents are fetched from an admin-area endpoint (`/Admin/DocumentCenter/.../Document_AjaxBinding`); that endpoint returned the site HTML to the plain client and, on the fifth request, a Cloudflare 'Just a moment' HTTP 429 challenge, at which point probing stopped | still blocked: no static index; challenge not worked around |
| AR | 403 (Cloudflare) | 403 for the WIC page and the site root | same failure |
| MA | 403 | 403 for the WIC organization page | same failure |
| IL | page-not-found redirect (batch 1) | www.dhs.state.il.us does not resolve (NameResolutionError, twice) | could not be re-read |
| NY, FL, IN, WI, AL, OK, MS | manual not published | pages reachable, still no manual link (re-read 21:38Z) | same |
| OH | manual not published | the Local Staff page and the program page both answer 404 | same |
| MO | manual behind portal login | still redirects to health.mo.gov/topic/781/login | same |
| NV | manual page password-protected | still password-protected | same |
| NM | policy page links only the intranet | still only intranet (chilenet) links | same |

Queue rows: OR and KY moved to `agent_ready`; AZ, TN, SC, LA and KS keep `blocked_primary_source` with the failure text
replaced by the retry finding; AR, MA and IL carry "retried 2026-09-10T21:34Z from US network, same failure" (IL: did
not resolve); the eleven not-published rows carry a "re-probed 2026-09-10T21:38Z from US network" stamp (generator
tables `RETRIED`).

## Part 2: next states by population (wall time was under 45 minutes)

Ten more states were attempted, in population order: NE, WV, ID, HI, NH, ME, MT, RI, DE, SD (first probe of each WIC
program page at 21:46:49Z, then the linked local-agency/policy page). Extracted 3 (WV, ME, RI). Blocked 7: NH and DE
answer 403 to the plain client for the WIC page and the site root (NH's WIC URL answers 404 to one impersonation, so the
page has also moved; DE's one impersonation fails TLS verification with a self-signed certificate in the chain, which was
not disabled); NE, ID, HI and SD publish no manual on their sites; MT publishes its program policies only as the 2026
WIC State Plan (state-plan family).

## Extracted

| state | index_url | index families (count) | taken |
|---|---|---|---|
| OR | https://www.oregon.gov/OHA/PH/HEALTHYPEOPLEFAMILIES/WIC/Pages/wicpolicy.aspx | policy PDFs 88 under 'Sec NNN' headings 100-1100 (400 and 500 are both 'Local Operations'); WIC Policy Update release notes 23 (2018-2026) | 88 |
| KY | https://www.chfs.ky.gov/agencies/dph/dmch/nsb/Pages/wic.aspx ('WIC and Nutrition Manual' heading) | policy-group PDFs 10 (100-900 plus 800B Farmers Market); Summary of Policy Changes FY 25: 1; other PDFs under the heading (Medical Necessity Forms, Referral Form) 2 | 10 |
| WV | https://dhhr.wv.gov/WIC/policyprocedure/Pages/Default.aspx (links eleven chapter pages 1.0-11.0) | policy PDFs 140 (after dropping one repeated link to the same 3.16 file); attachment PDFs 117; chapter index tables / policy indexes 11 (one 'Index Table' plus ten 'Chapter N Policy Index' / 'Table of Contents' files and two text-less links on 2.0); state plan pages 2 (FY 2025, FY 2024); participant agreement PDFs 2 (English, Spanish) | 140 |
| ME | https://www.maine.gov/dhhs/mecdc/healthy-living/wic/wic-administration-and-policies/wic-policies | policy PDFs 111 in thirteen series (BFPC 7, BF 8, CM 4, CE 6, CR 7, FM 18, FMNP 8, FD 5, IS 5, MA 2, NS 6, OM 21, VM 14); appendix files 79; other 3 ('OM 1A WIC State Agency Organization', 'VM-Appendix-2-C Vendor Training Guide', one alternate-format 'Word' link) | 111 |
| RI | https://health.ri.gov/programs/wic/ | 'WIC Procedures Manual' compiled PDF 1; 'WIC Vendor Policies' PDF 1; other PDFs on the program page (forms, food lists, brochures, translations) 73 | 2 |

Access notes: oregon.gov, chfs.ky.gov, dhhr.wv.gov, maine.gov and health.ri.gov all serve the index pages and PDFs to the
plain client with a browser User-Agent; no impersonation, range backend or CA-bundle extension was needed.

OR labels: the policy number from the file name (`ppm/610.pdf` -> `us-or/manual/oha/wic/610`), which is also the link
text; the policy title is the text following the link. Section number and title are recorded per document.

KY labels: the policy-group number (`us-ky/manual/chfs/wic/200`, Certification; `.../800b`, Farmers Market). Each
document is a whole policy group (21-200 pages), the publisher's unit.

WV labels: the policy number from the link text (`us-wv/manual/dhhr/wic/2.03`), with the chapter page as `index_url`
and the Policy/Procedure page as `policy_index_url`. File names carry `.docx.pdf` and `(2)` suffixes and are not used.

ME labels: the series code and number (`us-me/manual/mecdc/wic/ce-2`, Income Eligibility Determination and
Documentation). Revision dates printed in some link texts (`CE-1 Eligibility Application 10.2024`) are kept in the
title, not the label.

RI labels: `procedures-manual` and `vendor-policies` (slugs of the two link texts).

## Blocked (nothing downloaded; no mirrors, reposts, proxies or archived copies used)

Access blocks after the retry: AR (403 Cloudflare), MA (403), IL (host does not resolve), NH (403; one impersonation
404), DE (403; one impersonation fails TLS: self-signed certificate in chain), KS (index is a React shell fed by an
admin-area endpoint that returns HTML and then a Cloudflare challenge to non-browser clients). Not published on the
publisher's site (or not indexed): AZ, TN, SC, LA (all newly reachable), NE, ID, HI, SD, MT (State Plan only), and the
unchanged NY, FL, IL, OH, MO, IN, WI, AL, OK, MS, NM, NV rows. The exact failure per row is in `BLOCKED` /
`RETRIED` in the generator and in the queue row `notes`.

## Artifacts (unsigned, uncommitted, awaiting controller)

In the main checkout's corpus root (`/Users/pavelmakarchuk/axiom-corpus/data/corpus`, where batches 1-3's artifacts are;
this worktree is sparse and excludes `data/corpus`):

- `data/corpus/sources/us-xx/manual/2026-09-10-wic-state-policy-manual/official-documents/*.pdf`
- `data/corpus/{inventory,provisions,coverage}/us-xx/manual/2026-09-10-wic-state-policy-manual.{json,jsonl,json}`
  for xx in ky, or, wv, me, ri. The stale `us-wv-wic-manual-3.16-2.pdf` from the superseded first WV run was removed
  (judgment 8); the rerun's inventory and provisions never referenced it.

Rebuild (`--only` limits the generator to these rows; the BLOCKED loop runs after the builders, so a jurisdiction must be
removed from `BLOCKED` before its builder's row can stay `agent_ready`, which is why OR and KY were regenerated twice):

```bash
uv run python scripts/build_wic_manifests.py --only us-or,us-ky,us-wv,us-me,us-ri
uv run python scripts/build_wic_manifests.py --only us-az,us-tn,us-sc,us-la,us-ks,us-ar,us-ma,us-il,us-oh,us-mo,us-nv,us-nm,us-ny,us-fl,us-in,us-wi,us-al,us-ok,us-ms,us-ne,us-id,us-hi,us-nh,us-mt,us-de,us-sd
export REQUESTS_CA_BUNDLE=$PWD/data/certs/wic-state-ca-bundle.pem
for st in ky or wv me ri; do
  uv run axiom-corpus-ingest extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-wic-state-policy-manual --manifest manifests/us-$st-wic-policy-manual.yaml \
    --source-as-of 2026-09-10 --expression-date 2026-09-10
done
```

Lint: `uv run ruff check scripts/build_wic_manifests.py` is clean.

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"` in this
sparse worktree: 255 passed, 2 skipped, 10 failed in 41.9 s (run at 21:53:36Z-21:54:18Z, after every generator edit). The ten failures are the known pre-existing FileNotFoundError / same-file assertions on
`data/corpus/...` fixtures absent from this sparse checkout (BE rulespec promotion, NY TANF compatibility x2, BE source
promotion, and the AK/CT/MI/MT/ND/NY SNAP manual tests), identical to batches 1-3; none touch WIC code or manifests. No
adapter code was added: every batch-4 publisher works with the existing `extract-official-documents` options, so no new
tests.

GitNexus impact analysis was not run: the GitNexus MCP tools were unavailable in this session. No existing function was
modified; in `scripts/build_wic_manifests.py` the additions are `build_or`, `build_ky`, `build_wv`, `build_me`,
`build_ri`, the `RETRIED` table, new entries in the `BLOCKED`, `STATE_NAMES`, `BATCH_NOTE`, `BATCH`,
`INDEX_ANNOTATION_KEYS` and `STATE_BUILDERS` data tables, one appended line in `main` that adds the `RETRIED` stamp to a
blocked row's notes (the `recheck` string), and the module docstring. The `BLOCKED` entries for OR
and KY were removed because those states are now built.

## Reviewer judgments

1. Retry scope: every blocked row was retried exactly once with the plain client; impersonation was spent once each on
   AZ (to show the stripped page is served to browsers too), NH (403 vs moved page) and DE (TLS chain). KS received
   six requests in total (index shell, bundle, three admin-endpoint probes, one JS asset) before Cloudflare challenged;
   the challenge was not worked around and no further KS request was made.
2. KY takes each policy group as one document because that is the publisher's unit (one PDF per group, 21-200 pages);
   an encoder wanting per-policy granularity would need to split the PDFs, which `single_block` does not do. The
   'Summary of Policy Changes FY 25' and the 'LHD Administrative Reference' under the neighbouring 'For Local Health
   Department Staff' heading are not taken.
3. OR takes the 88 policies and not the 23 'WIC Policy Update' release notes, which are change memos (a different
   family, comparable to FNS policy memoranda); the policy PDFs are the current text.
4. AZ is re-classified from access block to publication gap as served: the site now answers, but the page that should
   carry the manuals section does not contain it. A reviewer with a browser should check whether azdhs.gov renders that
   section client-side from a source this agent could not see; if so AZ becomes extractable.
5. TN, SC and LA are re-classified from access block to not published/indexed; for TN the manual policies demonstrably
   exist under content/dam but no page lists them, so a reviewer may ask the agency for the index.
6. WV: policies are 'N.NN Title' PDFs; files whose link text contains 'Attachment' (117) are attachments and are not
   taken, nor are the chapter index tables. The rule 'number prefix matches the chapter' put ten policy-index files and
   two text-less links in `other_chapter_page_file` (inventoried, not taken). Some WV policies are served from
   `/WIC/Documents/` or `/WIC/foods/Documents/` rather than `/WIC/policyprocedure/Documents/`; they are taken as linked.
7. ME: policies are series-coded PDFs; 'Appendix ...' files (79) are not taken. 'OM 1A WIC State Agency Organization'
   (no hyphen, a chart) and 'VM-Appendix-2-C Vendor Training Guide' were left in `other_file` as appendix-like; a
   reviewer may want OM 1A. Several ME link texts carry revision months (10.2024, 1.2026); the CLI expression date
   2026-09-10 was kept (batch-1 convention).
8. WV 3.16 'Special Formula Distribution System' is linked twice on the 3.0 chapter page to the same file; the first
   generator run labelled the second link `3.16-2` and the first extraction took both. The generator now skips a
   repeated URL (`duplicate_link_same_file`, MN precedent), the manifest was regenerated (140) and WV re-extracted; the
   stale `3.16-2` source PDF from the first run was deleted from the corpus sources directory.
9. RI publishes the manual as one compiled PDF (the 'WIC Procedures Manual', 384,628 characters in one body row) plus
   the 'WIC Vendor Policies' PDF; both are taken as single documents because no per-policy index exists (unlike the
   TX/NC compiled files, which duplicated per-section PDFs). An encoder will need to locate sections inside the body
   text. The other 73 PDFs on the program page are forms, food lists, brochures and translations.
10. MT is recorded as not published rather than extracted: its 'State Plan Program Policies' link is the 2026 WIC State
    Plan, which batches 1-3 treated as a different document family (MA, UT precedent). A reviewer who wants Montana's
    policies should open a state-plan family for it.
11. Expression dates are the CLI value 2026-09-10 for every document (batch-1 convention).
12. Probe budget for the new states: one WIC program page and, where linked, one local-agency/policy page each (WV: the
    eleven chapter pages, which are the index); ID received five URL attempts because its WIC pages had moved; NH and DE
    received the site root as the second probe (403 pattern) and one impersonation each.

Remaining (controller): `sign-ingest-manifest` per scope, immutable release selector, `publish_corpus.py --dry-run`,
then publish and activate. States still not attempted for WIC manuals after four batches: ND, AK, DC, VT, WY (plus the
territories). Retry first: KS (if the Document Center gains a static listing or the challenge lifts for a browser
session), AZ (browser check of the agencies page), AR, MA, NH, DE (front doors), IL (DNS); NY, FL, OH, MA, IN, WI, MO,
AL, OK, MS, NM, NV, SC, LA, TN, NE, ID, HI, SD, MT if their agencies publish an index.
