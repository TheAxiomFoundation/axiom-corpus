# WIC: state policy manuals, batch 3 (CO, MN, SC, AL, LA, KY, OR, OK, CT, UT; replacements IA, NV, AR, MS, KS, NM)

Date: 2026-09-10
Program: WIC (board Year 1 list; `manifests/wic-agent-queue.yaml`)
Branch: `discovery/ingest-wic`
Previous runs: `docs/ingest-runs/2026-09-10-wic-fns-guidance-and-state-manuals.md` (batch 1),
`docs/ingest-runs/2026-09-10-wic-state-manuals-batch-2.md` (batch 2)

Timing: two agent sessions. The first started_at 2026-09-10T19:20:56Z, probed all sixteen publishers, generated the five
manifests, ran the extractions (19:38Z-19:44Z) and drafted this note, and was killed before committing (its last file
write was 19:46Z, so roughly 19:20Z-19:46Z, about 26 minutes, with no finished_at of its own). The continuation
started_at 2026-09-10T20:43:22Z, finished_at 2026-09-10T20:53:44Z (continuation wall time 622 seconds, about
10 minutes, measured just before the commit that carries this note); it verified the five scopes, fixed
one image-only Iowa PDF (judgment 12), completed the queue check and this note, and committed. Extraction wall time
per jurisdiction (final, complete runs; the first five ran concurrently, the Iowa rerun alone):

| scope | started | elapsed_seconds | documents | provisions |
|---|---|---|---|---|
| us-co / manual | 2026-09-10T19:38:51Z | 280 | 110 | 220 |
| us-mn / manual | 2026-09-10T19:38:55Z | 23 | 83 | 166 |
| us-ct / manual | 2026-09-10T19:38:58Z | 105 | 118 | 236 |
| us-ut / manual | 2026-09-10T19:39:02Z | 32 | 107 | 214 |
| us-ia / manual | 2026-09-10T20:49:13Z | 112 | 169 | 338 (rerun with OCR for one scanned PDF; the first run at 19:39:06Z, 111 s, wrote 337 and was superseded) |

Totals: 5 scopes, 587 documents, 1,174 provisions (one root plus one body provision per document), coverage
`complete: true` for every scope, 0 missing, 0 extra, 0 duplicate citation paths (checked directly in each provisions
JSONL against its manifest, not only via the coverage report, and re-checked independently by the continuation: every
manifest citation path has exactly one root row, every document has exactly one body row under its path, no path
repeats, every body row has non-empty text, every inventory item's citation path is a provision row and every root
item's `source_url` and `source_path` match its manifest document), and no new citation path exists in any other
provisions JSONL under `data/corpus/provisions/<jurisdiction>/` (checked before extraction against the manifests and
again after extraction against the JSONL, 15/8/7/6/10 other files for CO/MN/CT/UT/IA; the existing
`us-co/manual/hcpf/medicaid`, `us-mn/manual/dhs/combined-manual`, `us-ct/manual/dss/snap`, `us-ut/manual/recovery` and
`us-ia/manual/hhs/em` scopes share a jurisdiction but no path). The first Iowa run had 337 provisions because one
scanned PDF yielded no body row; the rerun with OCR (judgment 12) has 338. Smoke runs before the full runs: CO (`--limit 2`, the Google Drive download path)
and IA (`--limit 2`, extension-less Drupal media URLs) into a scratch base, both complete.

Publishers probed 16 (the cap): the ten selected states CO, MN, SC, AL, LA, KY, OR, OK, CT, UT and all six replacements
IA, NV, AR, MS, KS, NM, in order. Extracted 5 (CO, MN, CT, UT, IA). Blocked 11: six access blocks on the first probe
(SC, LA, KY, AR, KS: HTTP 403 to the plain client and to one browser-impersonation attempt, 20 s timeouts; OR: the
publisher's host does not resolve) and five publishers that do not post the manual on their own site (AL, OK, MS, NM;
NV's manual page is password-protected). The sixteen-probe cap was reached with five extractable states, so fewer than
ten states were attempted for extraction; the remaining states are listed at the end.

Conventions unchanged from batches 1 and 2: document_class `manual`, version `2026-09-10-wic-state-policy-manual`, one
document per policy/chapter PDF listed on the agency's own manual index, citation path
`us-xx/manual/<agency>/wic/<section label>`, `single_block` extraction, expression date = CLI value 2026-09-10, and
`REQUESTS_CA_BUNDLE=data/certs/wic-state-ca-bundle.pem` (certifi plus the two batch-1 intermediates, rebuilt by the
generator from the three committed `data/certs/*.pem` intermediates; the bundle itself is gitignored under `data/`, so
`git status` shows no cert change) for every run. No new intermediate was needed and TLS verification
was never disabled.

## Selection

The next ten states by population after batch 2: CO, MN, SC, AL, LA, KY, OR, OK, CT, UT. A state whose publisher
blocked the first probe (plain request plus one `curl_cffi` chrome124 impersonation, 20 s timeouts) or does not publish
the manual was replaced, in order, by IA, NV, AR, MS, KS, NM. The first probe of each publisher was its WIC program page
(or the manual index where one was already known) and, for a 403, the site root. Every probed state has a queue row;
extracted rows are `agent_ready`, blocked rows are `blocked_primary_source` with the exact failure.

## Extracted

| state | index_url | index families (count) | taken |
|---|---|---|---|
| CO | https://www.coloradowic.gov/policies-procedures/manuals/wic-policy-manual | policy PDFs on the agency's Google Drive 110 (Sections 1-11; Section 6 Food Funds lists none); compiled FY26 manual 1 (one Drive file linked 12 times: "View FY26 Compiled Policies and Procedures" and "Open Section N to view content") | 110 |
| MN | https://www.health.state.mn.us/people/wic/localagency/mom.html | chapter section PDFs 83 (chapters 1-9); "- all" compilations of 5.2 and 5.3: 2; draft section 7.10: 1; exhibit PDFs 46; exhibit Word files 17; draft exhibit 7-D: 1; links repeated under a second chapter 4 | 83 |
| CT | https://portal.ct.gov/dph/wic/ct-wic-state-plan (links nine "State Plan Policies - WIC NNN" pages: 100, 101, 102, 104, 105, 106, 200, 300, 400, and two singleton policies) | policy PDFs 115; 300-02 addenda 3; series tables of contents 9; numbered attachments (forms, tools, guidance, schedules under a policy number) 42 PDF + 7 Word; unnumbered forms, brochures, translations and guidance 30; State Plan Section 1 (program operations plan, BFPC implementation plan) 2 | 118 (policies + addenda) |
| UT | https://wic.utah.gov/about/wic-policies/ | policy PDFs 107 (functional areas I-XI and an Appendix of definitions; VI Food Funds Management lists none). Separate page, counted only: FY 2027 state plan "Section II: Local Agency Policy and Procedure Manual" draft, 110 PDFs | 107 |
| IA | https://hhs.iowa.gov/wic-portal/policies | policy PDFs 147; procedure PDFs 21; definitions 1; forms and booklets (PDF, incl. 37 translations of the Rights and Responsibilities form) 63; Word files 2; one form linked twice 1 | 169 (policies, procedures, definitions) |

Access notes per publisher: coloradowic.gov, health.state.mn.us, portal.ct.gov, wic.utah.gov and hhs.iowa.gov all serve
the index pages to the plain client with a browser User-Agent; no impersonation, range backend or CA-bundle extension was
needed. Colorado's policy files are served from drive.google.com (below). Iowa's files are Drupal media downloads
(`/media/<id>/download?inline`) without a file extension; `source_format: pdf` is declared in the manifest and the
extractor names the snapshot by `source_id`.

CO labels: slug of the index link text (the index prints no policy numbers), e.g.
`us-co/manual/cdphe/wic/determining-income-eligibility`, `.../food-packages-infants`; Section 4 links "Nutrition
Education Plan" twice to two different files (second labeled `nutrition-education-plan-2`). Each document records its
index section and Drive file id.

MN labels: the section number from the file name (`sctn5_2_4.pdf` -> `5.2.4`), which never disagreed with the link-text
number; e.g. `us-mn/manual/mdh/wic/5.2.4` (Income), `.../1.13` (Fair Hearing Procedure). Chapter titles come from the
page's chapter drawers (1 Administration, 2 Financial Management, 3 Caseload Management, 4 Local Agency Management and
Staffing, 5 Certification, 6 Nutrition Education, 7 Food Package, 8 WIC Cards, 9 Information System Operations).

CT labels: the policy number `NNN-NN` (`us-ct/manual/dph/wic/200-06`, Income Eligibility Policy), plus
`300-02-addendum-i`, `-ii`, `-iii` for the maximum-monthly-allowance addenda; the singletons linked only from the state
plan page are `103-01` (Dual Participation) and `108-01` (Inventory Control Procedures). Each document records its series
page as `index_url` and the state plan page as `state_plan_index_url`.

UT labels: slug of the link text (`us-ut/manual/dhhs/wic/income-guidelines`, `.../adjunct-eligibility`); the file
names carry WordPress upload counters (`Income-Guidelines-18.pdf`) that change on re-upload, so they are not used.

IA labels: slug of the link text including the policy number where the index prints one
(`us-ia/manual/hhs/wic/450.05-food-selection-criteria`, `.../income-determination`); "450.40 Sanctions" and "450.60 Dual
Participation" are each two different files (Vendor Management and Program Integrity), the second labeled `-2`.

## Blocked (nothing downloaded; no mirrors, reposts, proxies or archived copies used)

Access blocks on the first probe (plain client with browser User-Agent, then one `curl_cffi` chrome124 impersonation;
20 s timeouts):

- SC (dph.sc.gov): HTTP 403 (CloudFront) for the WIC program page and the site root. No manual index could be read.
- LA (ldh.la.gov): HTTP 403 (Cloudflare) for the WIC page and the site root. A chapter of the Louisiana WIC Policy &
  Procedure Manual demonstrably exists on the host (`assets/docs/LegisReports/Act542/WIC_Chapter11.pdf`).
- KY (www.chfs.ky.gov): HTTP 403 for the WIC page and the site root. The WIC and Nutrition Manual policy groups 200-800
  demonstrably exist on the host under `agencies/dph/dmch/nsb/wnm/`.
- OR (www.oregon.gov): the host does not resolve. The system resolver, 1.1.1.1 and 8.8.8.8 all answer SERVFAIL for
  `www.oregon.gov` (checked 19:23Z, 19:27Z, 19:34Z and again at 20:44Z by the continuation), while other hosts resolve, so the plain and
  impersonation probes fail before any HTTP request. The Oregon WIC Policy and Procedure Manual is published at
  `OHA/PH/HEALTHYPEOPLEFAMILIES/WIC/Pages/wicpolicy.aspx` with one PDF per policy (`Documents/ppm/<number>.pdf`), so
  this is a publisher-side DNS outage, not a publication gap.
- AR (healthy.arkansas.gov): HTTP 403 (Cloudflare) for the WIC page. Replacement state.
- KS (www.kdhe.ks.gov): HTTP 403 (Cloudflare) for the WIC program page and the site root. The Kansas WIC Policy &
  Procedures Manual policies demonstrably exist on the host (`DocumentCenter/View/<id>/<POLICY>-PDF`). Replacement state.

Manual not posted on the publisher's own site:

- AL (alabamapublichealth.gov): the WIC Procedure Manual is cited by the agency's own formulary ("Procedure Manual 5.3")
  but the WIC home, Health Care Providers and Health Provider Standards pages link only the formulary, prescription forms,
  a certification-process handout, two stand-alone policy PDFs (IID policy, informal resolution process) and the FY2027
  state-plan public notice; no page lists the manual.
- OK (oklahoma.gov): the WIC program page and its Health Partners, WIC Forms, Formula Information, Health & Nutrition and
  Caseload Data subpages link only the formulary, income guidelines, clinic list, assessment forms and formula documents.
- NV (nevadawic.org): the agency's Staff > Policy and Procedures page, which carries the Nevada WIC Policy & Procedure
  Manual, is password-protected ("This content is password-protected. To view it, please enter the password below.");
  individual policy PDFs exist under `wp-content/uploads` but no public index lists them. Replacement state.
- MS (msdh.ms.gov): the WIC Local Agencies page says sites must operate under the MSDH WIC Policy and Procedure Manual
  but links only the local-agency application and site-requirements PDFs; the WIC program pages link no manual.
  Replacement state.
- NM (nmwic.org): the NM WIC Policies & Procedures page lists the manual's series headings (100 Introduction through
  1400 Vendor Management, Appendices, Peer Counselor Policies) but links no documents under them; the only links in that
  section point at the department intranet (`http://chilenet/...`). Replacement state.

## Artifacts (unsigned, uncommitted, awaiting controller)

In the main checkout's corpus root (`/Users/pavelmakarchuk/axiom-corpus/data/corpus`, where batches 1 and 2's artifacts
are; this worktree is sparse and excludes `data/corpus`):

- `data/corpus/sources/us-xx/manual/2026-09-10-wic-state-policy-manual/official-documents/*.pdf`
- `data/corpus/{inventory,provisions,coverage}/us-xx/manual/2026-09-10-wic-state-policy-manual.{json,jsonl,json}`
  for xx in co, mn, ct, ut, ia.

Rebuild (`--only` limits the generator to these rows so batch-1 and batch-2 manifests are not regenerated; the Iowa
manifest sets `extraction.ocr: true` on `450.70-snap-wic-mou` from the generator's `IA_IMAGE_ONLY_PDFS` table, and
extraction of that document needs `tesseract` on PATH, 5.5.3 here):

```bash
uv run python scripts/build_wic_manifests.py --only us-co,us-mn,us-ct,us-ut,us-ia,us-sc,us-al,us-la,us-ky,us-or,us-ok,us-nv,us-ar,us-ms,us-ks,us-nm
export REQUESTS_CA_BUNDLE=$PWD/data/certs/wic-state-ca-bundle.pem
for st in co mn ct ut ia; do
  uv run axiom-corpus-ingest extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-wic-state-policy-manual --manifest manifests/us-$st-wic-policy-manual.yaml \
    --source-as-of 2026-09-10 --expression-date 2026-09-10
done
```

Lint: `uv run ruff check scripts/build_wic_manifests.py` is clean (re-run by the continuation after its edit).

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"` in this
sparse worktree: 255 passed, 2 skipped, 10 failed (same result when re-run by the continuation). All ten failures are the known pre-existing FileNotFoundError /
same-file assertions on `data/corpus/...` fixtures absent from this sparse checkout (BE rulespec promotion, NY TANF
compatibility x2, BE source promotion, and the AK/CT/MI/MT/ND/NY SNAP manual tests), identical to batches 1 and 2; none
touch WIC code or manifests. No adapter code was added: every batch-3 publisher works with the existing
`extract-official-documents` options, including the existing `google_drive_download_url` path (already covered by
`tests/test_corpus_documents.py`), so no new tests.

GitNexus impact analysis was not run: the GitNexus MCP tools were unavailable in this session. No existing function was
modified; in `scripts/build_wic_manifests.py` the additions are `slug`, `build_co`, `build_mn`, `build_ct`, `build_ut`,
`build_ia`, the `CT_SERIES` and `IA_IMAGE_ONLY_PDFS` constants, new entries in the `BLOCKED`, `STATE_NAMES`, `BATCH_NOTE`, `BATCH`,
`INDEX_ANNOTATION_KEYS` and `STATE_BUILDERS` data tables, and the module docstring.

## Reviewer judgments

1. Colorado's policies are hosted on the agency's Google Drive. coloradowic.gov (the CDPHE WIC site) is the publisher's
   own index: it lists every FY26 policy by section, but each link is a `drive.google.com/file/d/<id>/view` share of the
   agency's own Drive, and nothing of the current manual is served from coloradowic.gov itself (older compilations under
   `/sites/default/files/` are FY2018-FY2021). The extractor already has a first-class path for exactly this
   (`google_drive_download_url`, used by `manifests/us-co-snap-primary-policy.yaml` for CDHS state plans), so the Drive
   files linked from the publisher's index were treated as the publisher's posting, not a mirror. Manifest `source_url`
   values are the Drive share URLs as linked; the extractor converts them to direct downloads. A reviewer who reads "on its
   own site" strictly may prefer to mark CO blocked; the queue row and manifest make the hosting explicit
   (`google_drive_file_id`, `access_note`).
2. CO scope: the 110 section policies are taken; the compiled FY26 manual (one Drive file, the same content) is not
   (TX/NC precedent). The two different "Nutrition Education Plan" files are both taken; a reviewer should decide which
   is current. Section 6 (Food Funds) lists no policies.
3. MN scope: the 83 chapter sections are taken. Not taken: the two "- all" compilations (5.2, 5.3; duplicates of their
   subsections), the draft replacement of 7.10 and the draft exhibit 7-D (a final 7.10 and 7-D are published), and the 63
   exhibits (forms, sample letters, tables, checklists). Exhibits 5-A (income guidelines), 5-T (risk criteria), 5-U
   (priority system) and 6-A (high-risk criteria) carry parameter-like content an encoder may want; a later revision could
   take the exhibit PDFs as `exhibit` documents. The MOM's own table-of-contents page (`program/mom/toc.html`) answers 403;
   the `mom.html` page is the index.
4. CT structure: Connecticut publishes its manual as "State Plan Policies" series pages. On each page the first PDF under
   a policy number is the policy and later files under the same number are attachments (sample job descriptions,
   monitoring tools, checklists, forms, FAQs, schedules); that first-PDF rule was checked by eye against every series
   page. The three 300-02 addenda (maximum monthly allowances for infants, women and children; juice benefits) are taken as
   their own documents because they carry the food-package amounts. Not taken: series tables of contents (9), numbered
   attachments (49), unnumbered forms, brochures, translations and guidance (30, including the 2025-2026 income eligibility
   guidelines sheet and the Nutrition Services Documentation guidance), and the State Plan Section 1 documents (a different
   family). Series 103 and 108 exist only as the singleton policies 103-01 and 108-01 on the state plan page; no 107 or
   500+ series is published.
5. UT: the "WIC policies" page is the current manual and is taken. The FY 2027 state plan's "Section II: Local Agency
   Policy and Procedure Manual" draft page (110 PDFs, including two policies and a "No policies" placeholder the current
   page lacks) is a proposed version and is counted, not taken; when Utah promotes it, the manifest should be rebuilt
   from whichever page the agency then calls current. Functional area VI lists no policies.
6. IA: policies and procedures are taken (the manual's own PROCEDURES headings are part of the Policy and Procedure
   Manual); forms, booklets (the vendor agreement and handbook), Word files and the 37 translations of the Rights and
   Responsibilities form are not. The 450.40 and 450.60 pairs are two files each and both are taken.
7. Label conventions: CO, UT and IA labels are slugs of the index link text because those indexes print no (or only
   some) policy numbers; CT and MN labels are the publishers' own numbers. Slug labels will change if the agency renames
   a policy.
8. Blocked publishers were not worked around (SC, LA, KY, AR, KS 403s; OR DNS; AL, OK, MS, NM not published; NV password).
   For LA, KY and KS the manual demonstrably exists on the publisher's host and for OR it is published on a host that did
   not resolve during the run; those four are the first retries. AZ and TN (batch 2) remain the other known access blocks.
9. Probe budget: each blocked publisher received exactly the first probe the work order allows (one plain request and one
   impersonation per URL, two URLs for the 403 cases: the WIC page and the site root); Oregon's DNS was re-checked four
   times over the run because a resolver failure can be transient. None of the batch-1 or batch-2 blocked rows were
   re-checked in this batch.
10. Expression dates are the CLI value 2026-09-10 for every document (batch-1 convention), although CT policies print
    revision dates in their titles and MN sections print revision months.
11. NV is recorded as not published rather than as an access block: the agency site serves the page but gates the manual
    behind a password, which is a publication choice, not a front-door block.
12. IA `450.70 SNAP WIC MOU` (the FNS/WIC state agency information-sharing MOU posted under Vendor and Farmer Management)
    is a three-page scan (one JPEG per page, no text layer; `pdftotext` returns nothing). The first extraction wrote its
    root row with `block_count: 0` and no body row, which the coverage report does not flag because coverage compares
    inventory items to rows. The continuation set the extractor's existing per-document `ocr` fallback (tesseract runs
    only on pages without text; the option used by the Belgian family-benefit scope) on that one document and re-ran
    the Iowa scope; its body is now 6,191 characters of OCR text and may carry recognition errors, so an encoder should
    read the PDF for exact figures. No other batch-3 document lacked text. The Iowa index was unchanged when the
    manifest was regenerated at 20:49Z (169 documents, identical apart from the two OCR lines).
13. Continuation scope: the first agent's manifests, queue rows and extractions were verified, not redone; only the
    Iowa manifest and queue row were regenerated (`--only us-ia`) and only the Iowa scope re-extracted. No further
    publisher was probed because the sixteen-probe cap was already reached; five of the sixteen were extractable, so
    this batch attempts five states, not ten.

Remaining (controller): `sign-ingest-manifest` per scope, immutable release selector, `publish_corpus.py --dry-run`,
then publish and activate. States still not attempted for WIC manuals after three batches: NE, WV, ID, HI, NH, ME, MT,
RI, DE, SD, ND, AK, DC, VT, WY (plus the territories). Retry first: OR (when www.oregon.gov resolves), then LA, KY, KS,
AZ, TN if their front doors stop blocking non-browser clients; NY, FL, IL, OH, MA, IN, WI, MO, AL, OK, MS, NM, NV, SC, AR
if their agencies publish an index.
