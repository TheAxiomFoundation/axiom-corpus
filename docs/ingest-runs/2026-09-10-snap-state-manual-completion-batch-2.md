# SNAP state policy manuals, completion batch 2 (axiom-corpus#680)

Date: 2026-09-10
Program: SNAP (`manifests/state-snap-manual-agent-queue.yaml`, 51 rows, unchanged; this pass is
tracked in `manifests/snap-completion-agent-queue.yaml`, batch-1 rows unchanged except the KY and NY
retries)
Issue: https://github.com/TheAxiomFoundation/axiom-corpus/issues/680 ("SNAP discovery missed
~24 states")
Agent: one session from a US network. started_at 2026-09-10T21:34:31Z, finished_at
2026-09-10T22:06:55Z, wall time 32m 24s. Per-state extraction seconds (timer around
`extract-official-documents`): KY 3 s (22:00:06Z-22:00:09Z), WY 5 s (22:00:12Z-22:00:17Z), ND 3 s
(22:00:19Z-22:00:22Z); artifact timestamps agree (first source file to coverage file: KY 22:00:08-22:00:09,
WY 22:00:15-22:00:17, ND 22:00:21-22:00:22).
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. No existing
function was modified: the only code change is additive in
`scripts/build_snap_state_manual_completion_manifests.py` (three new live builders `build_ky`,
`build_wy`, `build_nd`, one helper `_pdf_revision_facts`, one helper `slug_full`, the batch-2 static
rows and batch-aware row notes in `main()`). No new adapter: extraction is
`uv run axiom-corpus-ingest extract-official-documents`.

## Selection rule (reviewer judgment)

Step 1: retry the two publishers blocked in batch 1 once each, one plain Axiom request and one
curl-cffi chrome120 browser-impersonation request, 20 s timeouts. KY answered (HTTP 200 to both) and
was completed; NY is still bot-challenged and stays `blocked_primary_source`.

Step 2: the issue's remaining discovery-gap states in its order, NE, WY, AZ, AR, IA, HI, NM, VT, NV,
ND. AZ blocked on its first probe, so ID (first replacement candidate) was taken in its place.
Attempted: 10 (NE, WY, AR, IA, HI, NM, VT, NV, ND, ID) plus the KY and NY retries; publishers
probed: 13 of the cap of 16. Extracted: KY, WY, ND (3). Index confirmed complete, nothing to take:
NE, AR, IA, HI, NM, VT, NV, ID (8). Blocked: AZ, NY (2).

The same constraints as batch 1: released SNAP scopes are immutable, so every document missing from
the corpus goes into a new scope per state, version `2026-09-10-snap-state-manual-completion`,
`document_class` per the state's existing convention, manifest
`manifests/us-xx-snap-manual-completion.yaml`, citation paths under the state's existing convention.
Every candidate citation path was checked against every provisions JSONL under
`/Users/pavelmakarchuk/axiom-corpus/data/corpus/provisions/<jurisdiction>/` (all document classes, all
versions) by the generator (`citation_path_already_in_corpus`, none occurred) and again independently
on the JSONL after extraction (0 collisions). Every document was confirmed on the publisher's own
index, fetched live; no mirrors, archives, compiled lists or PolicyEngine files. TLS verification was
never disabled: the one broken chain (rules.nebraska.gov) was fixed with the publisher's public
intermediate under `data/certs/` and `REQUESTS_CA_BUNDLE` (below).

A recurring finding of this batch: many released SNAP scopes are already superseded by newer
editions on the publisher (KY Volumes II and IIA, NE chapters 2 and 3, AR manual and appendices, NV six
chapters, WY Table II, ND 64 topics plus landing and TOC). Their citation paths exist, so a completion
scope cannot carry them; each needs a superseding scope, recorded in the queue row and below, not
re-taken here.

## Retries

**us-ky** — https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx: plain request HTTP 200
(56,233 bytes, 1.6 s), impersonation HTTP 200 (58,132 bytes). Batch 1 had HTTP 403 to both from the
first network. Completed below.

**us-ny** — https://otda.ny.gov/programs/snap/: plain request closed without a response
(`requests.ConnectionError: RemoteDisconnected('Remote end closed connection without response')`,
0.7 s); impersonation HTTP 200 carrying a 7,562-byte F5/TSPD JavaScript bot-challenge page (batch 1:
connection reset, then a 5,609-byte challenge page). No index inventory possible; no workaround.

## Per-jurisdiction results

| Jurisdiction | Index | Found | Taken | Provisions | Extraction seconds | Status |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| us-ky | DCBS DFS Operation Manual volumes (DFS page) | 23 | 1 | 257 | 3 | agent_ready (extracted) |
| us-ny | OTDA SNAP program page | - | 0 | - | - | blocked_primary_source (retry failed) |
| us-ne | Nebraska Rules, Title 475 NAC | 5 | 0 | - | - | done (index complete; ch. 2-3 revised) |
| us-wy | DFS SNAP and POWER Policy Manual | 15 | 4 | 8 | 5 | agent_ready (extracted) |
| us-az | DES FAA policy manual host | - | 0 | - | - | blocked_primary_source |
| us-ar | DHS DCO SNAP pages + media library | 13 | 0 | - | - | done (index complete; manual revised) |
| us-ia | HHS Employees' Manual TOC | 13 | 0 | - | - | done (index complete) |
| us-hi | DHS Administrative Rules for Programs | 140 | 0 | - | - | done (index complete) |
| us-nm | HCA ISD page / SRCA NMAC Title 8 | 102 | 0 | - | - | done (index complete) |
| us-vt | 3SquaresVT RoboHelp TOC | 32 | 0 | - | - | done (index complete) |
| us-nv | DWSS Eligibility & Payments Manual page | 139 | 0 | - | - | done (index complete; 6 chapters revised) |
| us-nd | HHS SNAP Policy Manual TOC + Release Log | 160 | 4 | 60 | 3 | agent_ready (extracted) |
| us-id | OARC Current Rules document list (AZ replacement) | 369 | 0 | - | - | done (index complete) |

Total: 9 documents, 325 provisions across 3 new scopes. Found/taken per family are in the queue rows
(`index_document_count`, `taken_count`, `index_families`); families are disjoint, so `found` sums
to `index_document_count`.

Coverage for the three extracted scopes is `complete: true` with 0 missing, 0 extra and 0
duplicate citation paths (`duplicate_provision_citations` and `duplicate_source_citations` empty).
Verified independently on the JSONL: KY 257 rows, 257 distinct `citation_path`, the manifest root
present, 0 collisions against the other nine provisions files under `provisions/us-ky/`; WY 8 rows,
8 distinct, 4/4 roots, 0 collisions against six files; ND 60 rows, 60 distinct, 4/4 roots, 0
collisions against seven files. Every inventory item names a regular, non-symlink file under
`sources/<jur>/manual/2026-09-10-snap-state-manual-completion/` whose SHA-256 matches (0 bad
references); no source file under 3 KB (no challenge or error pages retained); no empty text blocks.

### Index inventories and diagnoses

**us-ky** — https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx, the released scope's
`manual_landing_page`. It lists 12 Operation Manual volume PDFs and 11 SNAP application forms (23
documents): Volume I General Administration, II SNAP, IIA SNAP Work Requirements, III KTAP, IIIA
KWP, IV (vacant), IVA non-MAGI Medicaid, IVB MAGI Medicaid/APTC, V State Supplementation, VIII CCAP,
IX OMTL cover letters, X Policy Updates. The released scope `us-ky/manual/2026-07-17-ky-snap-manual`
holds Volumes II and IIA (400 provisions). Both are revised on the publisher: Volume II is now
OMTL-704, table of contents "R. 8/1/26", 349 pages, SHA-256 c9789d01... (released 7ef887da...,
OMTL-701, R. 7/1/26); Volume IIA is 54 pages, SHA-256 cb5088b1... (released a1a7f8d1...); their
citation paths exist, so a superseding KY scope is needed. Volume I (General Administration: case
processing, case records, documentation, confidentiality, civil rights, hearings and the other
procedures that apply to every Family Support program including SNAP; 256 pages, latest section
revision R. 8/1/26, latest OMTL 703, TOC R. 1/15/25) is SNAP-governing and absent from the corpus:
taken as `us-ky/manual/dcbs/dfs/volume-i-general-administration` (KY convention
`us-ky/manual/dcbs/dfs/<volume>`, `document_class: manual`), `expression_date` 2026-08-01 (the latest
section revision, as the released rows use `manual_revision_date`). Families (23 found, 1 taken):
SNAP volumes already in the released scope, revised 2/0; general-administration volume 1/1; other
program volumes 7/0; OMTL cover-letter and policy-update volumes 2/0 (transmittal history, no SNAP
policy text per the released queue row); SNAP application forms 11/0. The SNAP E&T page linked from
the index carries the Kentucky SNAP E&T State Plan 2026 PDF and E&T provider guides (state-plan and
provider families, not taken). The plain Axiom request answers, so the manifest carries no request
option (the released rows use `browser_user_agent: true`). Extraction: 1 document, 257 provisions
(1 root + 256 page provisions), 3 s.

**us-ne** — https://rules.nebraska.gov/rules?agencyId=37&titleId=230. The site is a React app; its
data is the same-origin API (`/api/title/GetByAgencyId/37`, `/api/chapter/GetByTitleId/230`), which
is the publisher's own index. Title 475 "Supplemental Nutrition Assistance Program" has five chapters:
1 General Provisions (effective 2025-12-24), 2 Household Processing (2026-07-28), 3 Eligibility
(2026-07-28), 4 Benefits (2024-09-17), 5 EBT Card Issuance and Accountability (2020-07-04). All five
are in `manifests/us-ne-snap-rules.yaml` and `us-ne/regulation/2026-07-17-ne-snap-rules` (742
provisions, coverage complete); chapters 2 and 3 are new editions (the released files are the
09-17-2024 editions), so a superseding NE rules scope is needed; nothing new to take. TLS:
rules.nebraska.gov serves `*.nebraska.gov` without its intermediate (openssl verify return code 21,
"unable to verify the first certificate"; plain requests and curl-cffi both fail with "unable to get
local issuer certificate"). The released manifest works around this with `request.verify_tls: false`.
This run fetched with verification on: the publisher's public intermediate "DigiCert Global G2 TLS
RSA SHA256 2020 CA1" (issuer DigiCert Global Root G2, SHA-256 fingerprint C8:02:5F:9F:...:25:A9,
downloaded from cacerts.digicert.com) is added as
`data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem`, and `REQUESTS_CA_BUNDLE` = certifi +
that file (force-added; `data/` is gitignored, as the existing Entrust bundle was). The superseding
scope should use that bundle instead of `verify_tls: false`.

**us-wy** — https://dfs.wyo.gov/about/policy-manuals/snap-and-power-policy-manual/. Existing WY
convention: `manifests/us-wy-manuals.yaml`, `document_class: manual`,
`us-wy/manual/dfs/snap-power-policy-manual[/<slug>]`; the released scope
`us-wy/manual/2026-05-27-wy-manuals-r2026-07-15-self-contained` holds the main manual page (sections
100-1400, one text block), the 900 and 1100 accordion "extended menu" pages (embedded in the main
page, not linked from it) and Table II POWER Income Limits: 4 documents, 9 provisions. The manual's
sub-navigation lists EDI (case-file imaging guidance), Glossary, Codes, Notices, CM Updates, Policy
Clarifications, Resources and Tables; Tables links Table I SNAP Income Limits and Table II; the manual
text links a Medical Handbook and a page "Purchasing and preparing food separately and pass-through
rent/mortgage monies 7/21/14". Families (15 found, 4 taken): main page already in the released scope
1/0; extended-menu accordions already in the released scope 2/0; glossary 1/1 (13,600 words of manual
definitions, as the TX glossary); policy clarifications 1/1 (Q&A policy interpretations); Table I SNAP
income limits 1/1 (the FFY2027 gross/net standards and allotments; not in the released scope, which
took Table II only); purchasing-and-preparing-food-separately policy page 1/1; Table II already in the
released scope 1/0 (now the July 2026-June 2027 POWER standards, so revised: superseding scope); CM
Updates 1/0 (change log, the change-summary family); EDI guidance 1/0, Codes 1/0, Notices 1/0,
Resources 1/0 (system, code and form catalogues, no eligibility policy); Tables landing 1/0; Medical
Handbook 1/0 (Medicaid). Extraction selector `.entry-content` (the WordPress article body; the
released rows have no selector and yield one block per page): 4 documents, 8 provisions (4 roots + 4
blocks), 5 s. `expression_date` = fetch date, as the released rows.

**us-az** — blocked, below.

**us-ar** — https://humanservices.arkansas.gov/divisions-shared-services/county-operations/supplemental-nutrition-assistance-snap/
and its sub-pages (nutrition waiver, waiver FAQ, SNAP Requirement to Work & Time Limit Rules, SNAP
Overview and How to Apply, SNAP E&T). They link the three policy HTML pages and the FY2026 Quick
Reference chart already in `manifests/us-ar-snap-manual.yaml` (`us-ar/manual/2026-07-16-ar-snap-manual`,
810 provisions). No DHS web page links the SNAP Certification Manual PDF (the released row's
`discovered_via: official-policy-index:arkansas-dhs-dco-policies` page no longer exists; the sitemap
has no DCO policy page). The publisher's own media library (`/wp-json/wp/v2/media?search=SNAP`, the
site's WordPress API) lists SNAP-Policy-Manual-11.21.2025, -03.01.2026, -04.02.2026 (the released
edition, still HTTP 200) and -07.01.2026 (uploaded 2026-07-22), SNAP-Appendices-04.02.2026 and
-07.30.2026; the released appendices URL SNAP-Appendices-05.15.2026.pdf answers HTTP 404. Families (13
found, 0 taken): program-page policy HTML 3/0 (in corpus); quick reference chart 1/0 (in corpus);
policy manual PDFs in the media library 4/0 (1 in corpus, 1 revised edition); appendices PDFs 2/0 (1
revised edition; the released file is gone); SNAP-Employment-and-Training-7.24.26.pdf 1/0 (the E&T
provider contact list, a directory); SNAP E&T State Plans FFY25/FY26 2/0 (state-plan family). The July
2026 manual and appendices are new editions of `us-ar/manual/dhs/snap-policy-manual` and
`snap-manual-appendices`, so a superseding AR scope is needed; nothing new to take.

**us-ia** — https://hhs.iowa.gov/media/4035/download?inline (Employees' Manual table of contents,
revised March 3, 2023). Title 7 SNAP = chapters A Administration, B Application Processing, C
Nonfinancial Eligibility, D Resources, E Income, F Budgeting, G Case Maintenance, H Adjustments, I
Specific Households and Participants, J Intentional Program Violation, M SNAP Employment and Training,
plus an "All SNAP Chapters" omnibus. Families (13 found, 0 taken): Title 7 chapter PDFs 11/0 (all in
`manifests/us-ia-snap-manual.yaml` and `us-ia/manual/2026-07-17-ia-snap-manual`, 443 provisions); TOC
PDF 1/0 (in corpus); omnibus 1/0 (the same text in one file, excluded by the released row). All 12
released files are byte-identical to the publisher's today (SHA-256 against the released inventory).

**us-hi** — https://humanservices.hawaii.gov/admin-rules-2/admin-rules-for-programs/: 140 HAR Title 17
chapter PDFs. Families (140 found, 0 taken): Subtitle 6 SNAP-governing chapters 20/0 (600 Overview,
601 Confidentiality, 602.1 Hearings, 603, 604.1 Fraud, 605, 606, 610 Food Stamp Program
Administration, 647-650, 655, 663, 675 Assets, 676 Income, 680, 681, 683, 684.1; all in
`manifests/us-hi-snap-rules.yaml` and the released scope, 594 provisions; every file's Last-Modified is
2018-2022, so none is revised); other Subtitle 6 chapters 11/0 (653 child support and third-party
liability, 654 no-fault insurance, 656.1 TANF, 658 AABD financial assistance, 659 General Assistance,
661 refugee/repatriate/SLIAG, 678 financial assistance standards, 685.4 replacement of stolen
financial-assistance and child-care benefits, 686.1 Summer EBT (outside SNAP, as ME SUN Bucks), 687
Hawaii Emergency Food Assistance Program, 17-602.1 duplicate link); other subtitles 108/0; one dead
link 1/0 (17-602.1 at files.hawaii.gov, HTTP 404).

**us-nm** — https://www.hca.nm.gov/lookingforinformation/income-support-division-1/ links the NMAC
parts on the State Records Center (srca.nm.gov): 8.100 (10 parts), 8.102 TANF/NMW (17), 8.106 GA (18),
8.119 refugee (7), 8.139 Food Stamp Program (17), 8.150 LIHEAP (17), plus the State Verification Plan
PDF. The SRCA Title 8 chapter page marks every other 8.139 part number RESERVED (1-99, 101-109,
111-119, 121-399, 401-409, 411-419, 421-499, 505-509, 511-519, 521-526, 528-609, 611-639, 641-646,
648-649), which leaves 18 active parts: the 17 on the HCA page plus 8.139.640 (in the released scope).
Families (102 found, 0 taken): 8.139 parts 18/0 and 8.100 parts 10/0 (all 28 in
`manifests/us-nm-snap-regulations.yaml` and `us-nm/regulation/2026-07-17-nm-snap-regulations`, 388
provisions; all 28 SRCA files byte-identical to the released inventory); other ISD program parts 73/0;
verification plan 1/0.

**us-vt** — https://www.ahsnet.ahs.state.vt.us/Public/3sVT/ (RoboHelp). The TOC
(`whxdata/toc.new.js` plus `toc<N>.new.js` per book) has 32 books and 252 entries; the entries are
in-page anchors that resolve to 32 distinct topic files, all in `manifests/us-vt-3squaresvt-manual.yaml`
and `us-vt/manual/2026-07-21-vt-3squaresvt-manual` (911 provisions), and all 32 files are
byte-identical to the released inventory. Families: TOC books 32 (structure), TOC entries 252
(structure), chapter topics 32/0; `index_document_count` 32.

**us-nv** — https://dwss.nv.gov/Home/Features/eligibility/eligibility-n-payment-info-manual/: 139
PDF links. Families (139 found, 0 taken): chapter and reference PDFs 51/0 (A-D, F, R, TOC, glossary,
index; all 51 citation paths in `manifests/us-nv-eligibility-payments-manual.yaml` and the released
scope, 821 provisions); manual transmittal letters 2010-July 2026 86/0 (the change-summary family, as
FL Summary of Changes and NH Service Releases); two off-site state web-standards PDFs 2/0. Six chapters
are now served as new files and their released URLs are gone from the index: A-100 Application
Processing, A-200 Verification and Documentation, A-700 Income, A-1800 Case Disposition, B-400 Special
Households, B-900 Program Violations/Sanctions (revised by the April-July 2026 transmittals); their
citation paths exist, so a superseding NV scope is needed. Nothing new to take.

**us-nd** — https://www.nd.gov/dhs/policymanuals/SNAP/Content/Home%202.htm (MadCap Flare). The TOC
`Data/Tocs/Online_Chunk0.js` lists 67 entries (the Home page plus 66 topics); the Release Log lists
15 release-update PDFs (25.2-26.7). The released scope `us-nd/manual/2026-07-21-nd-snap-manual`
(Release 26.5) holds the landing page, the TOC, the 26.5 PDF and 64 topics. Since then Release 26.6
(effective 2026-08-13) and 26.7 (effective 2026-10-01, published ahead of its effective date) landed:
two new topics, "SNAP Application and Review Processing" (1,010 words) and "Acting on SNAP Changes"
(2,303 words), and the two release PDFs. Families (160 found, 4 taken): TOC topics 66/2 (64 already
in the released scope, counted separately); landing and TOC already in the released scope 2/0;
release-update PDFs 15/2 (1 already in the released scope; 12 older than the released baseline, the
change-history family, not taken). Citation paths follow the released conventions
`us-nd/manual/hhs/snap/<slug of the /dhs/policymanuals/SNAP/Content/... path>-htm` (untruncated) and
`us-nd/manual/hhs/snap/updates/release-26-6`, `release-26-7`; selector `#mc-main-content` as the
released topics. `expression_date`: fetch date for the topics (they carry no date), release effective
date for the PDFs (as the released 26.5 row). 66 of the 67 released files differ byte-wise from the
publisher's today (only the Release 26.5 PDF is identical), consistent with two releases since 26.5, so the
released topics need a superseding scope. Extraction: 4 documents, 60 provisions (4 roots + 33 topic text
blocks (23 and 10) + 23 release-PDF page provisions), 3 s.

**us-id** (replacement for AZ) — https://adminrules.idaho.gov/current-rules/. The Current Rules page
renders its list from the site's own REST endpoint (`/wp-json/dfm-document-display/fetch-documents`,
`documentType: currentRules`, called with the page's nonce exactly as the page's script does; the
legacy directory URL `/rules/current/16/` answers HTTP 404, and curl-cffi impersonation of this host
fails on the local CA store while plain requests verify fine). It lists 369 current rule chapters, 21
in IDAPA Title 16 (Department of Health and Welfare). Families (369 found, 0 taken): 16.03.04 "Idaho
Food Stamp Program" 1/0 (in `manifests/us-id-snap-rules.yaml` and the released scope
`us-id/regulation/2026-05-27-id-food-stamp-rules-r2026-07-15-self-contained`; the live PDF, 70 pages,
Last-Modified 2026-07-01, is byte-identical to the released inventory, SHA-256 1d542968...); other
Title 16 chapters 20/0 (16.03.01 health-care eligibility, 16.03.05 AABD, 16.03.08 Federal Welfare
Programs (cash assistance), 16.03.19-26 provider and Medicaid rules, 16.02, 16.04-16.06); other
agencies 348/0. DHW publishes no separate public SNAP manual; #680's 70 "captured" is the section count
of the one chapter.

### Blocked publishers (no workaround attempted)

**us-ny** — see Retries.

**us-az** — https://dbmefaapolicy.azdes.gov/FAA5.html (the DES FAA policy manual host, the released
row's `primary_source_url` host): HTTP 403 with a 5,675-byte page to the plain Axiom request and HTTP
403 with a 5,995-byte F5/TSPD JavaScript bot-challenge page to curl-cffi chrome120 impersonation (20 s
timeouts). The released scope was built from archived snapshots (`download_url` on web.archive.org),
which this run's rules exclude for new documents. ID was taken as the replacement.

## Artifacts (unsigned, uncommitted; `data/` is gitignored in the main checkout)

- `data/corpus/sources/us-xx/manual/2026-09-10-snap-state-manual-completion/official-documents/*`
- `data/corpus/inventory/us-xx/manual/2026-09-10-snap-state-manual-completion.json`
- `data/corpus/provisions/us-xx/manual/2026-09-10-snap-state-manual-completion.jsonl`
- `data/corpus/coverage/us-xx/manual/2026-09-10-snap-state-manual-completion.json`

for xx in ky, wy, nd, under `/Users/pavelmakarchuk/axiom-corpus/data/corpus` (alongside the batch-1 tx
and nh artifacts).

Rebuild (batch-1 manifests are never regenerated; `--only` restricts the live builders):

```bash
uv run python scripts/build_snap_state_manual_completion_manifests.py \
  --corpus-base /Users/pavelmakarchuk/axiom-corpus/data/corpus --only us-ky --only us-wy --only us-nd
for j in ky wy nd; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-snap-state-manual-completion \
    --manifest manifests/us-$j-snap-manual-completion.yaml
done
```

`source_as_of` is 2026-09-10 for every document; `expression_date` is per document (KY 2026-08-01,
WY 2026-09-10, ND topics 2026-09-10, ND releases 2026-08-13 and 2026-10-01).

Ruff: `uv run ruff check scripts/build_snap_state_manual_completion_manifests.py` -> all checks passed.

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped (4,275 deselected). The 10 failures are exactly the known
sparse-worktree failures (BE rulespec promotion, NY TANF compatibility x2, BE source promotion,
AK/CT/MI/MT/ND/NY SNAP manual tests), all opening `data/corpus` artifacts this worktree does not check
out. No test reads the new manifests, the completion queue or the generator.

## Reviewer judgments (all of them)

1. Retry rule: KY and NY once each, one plain request and one browser-impersonation request, 20 s
   timeouts; KY completed because it answered, NY left blocked with the exact failure.
2. Order and replacement: NE, WY, AZ, AR, IA, HI, NM, VT, NV, ND in the issue's order; AZ blocked on its
   first probe and ID (first replacement candidate) took its slot; 10 attempted, 13 publishers probed.
3. Revised editions of documents already in a released scope are never re-taken in a completion scope
   (their citation paths exist and a release rejects duplicates): KY Volumes II and IIA, NE chapters 2
   and 3, AR manual and appendices, NV six chapters, WY Table II, ND landing/TOC/64 topics. Each is
   recorded for a superseding scope in the queue row.
4. KY: Volume I General Administration is SNAP-governing (it governs case processing for every Family
   Support program including SNAP) and is taken; Volumes III-VIII are other programs; IX and X are
   transmittal history (the released queue row's finding); the SNAP applications and the SNAP E&T State
   Plan 2026 are separate families. `expression_date` 2026-08-01 = the latest "R." section revision
   in the volume, the released KY rows' `manual_revision_date` convention. No `browser_user_agent`
   option because the plain request answers.
5. WY: Glossary, Policy Clarifications, Table I SNAP Income Limits and the purchasing-and-preparing
   page are SNAP-governing manual text and taken; CM Updates is the change-summary family; EDI, Codes,
   Notices and Resources are system/form catalogues; the Tables page is a landing page; the Medical
   Handbook is Medicaid. Selector `.entry-content`; `expression_date` = fetch date as the released rows.
6. ND: the two topics and the 26.6 and 26.7 release PDFs added since Release 26.5 are taken; the 12
   release PDFs older than the released baseline are the change-history family, not taken; topic
   `expression_date` = fetch date (no date on the page), release `expression_date` = effective date
   (26.7's 2026-10-01 is in the future; the publisher has already posted it). The Home page in the TOC
   is the released landing page (`navigation/landing`) and is not a topic.
7. NE: the TLS chain is fixed with the publisher's public DigiCert intermediate under `data/certs/`
   and `REQUESTS_CA_BUNDLE`; the released manifest's `request.verify_tls: false` is flagged for the
   superseding scope. The same-origin `/api` the React app calls is the publisher's own index.
8. AR: no DHS web page links the SNAP Certification Manual any more; the site's own WordPress media
   API is used as the publisher's index of manual editions. The E&T provider contact list and the SNAP
   E&T State Plans are not the manual.
9. HI: Subtitle 6 chapters 653, 654, 656.1, 658, 659, 661, 678, 685.4, 686.1 (Summer EBT) and 687
   (HEFAP) are not SNAP; the 20 released chapters are the complete SNAP set; revision status from
   Last-Modified headers because the released scope is a self-contained release object without
   per-file hashes.
10. NM: the SRCA reserved-part ranges establish the 18 active 8.139 parts; the HCA page omits
    8.139.640, which the released scope already holds.
11. NV: the 86 manual transmittal letters are the change-summary family; the six re-issued chapter
    files are revised editions.
12. IA: the Title 7 omnibus PDF is a duplicate of the eleven chapters (as the released row decided).
13. VT: 252 TOC entries collapse to 32 topic files; the TOC entries are anchors, not documents.
14. ID: SNAP policy in Idaho is IDAPA 16.03.04 only; the document list was fetched through the
    publisher's own REST endpoint with the page's nonce, the request the page itself makes, not a
    workaround; the released PDF is unchanged.
15. AZ: blocked; the released scope's archived-snapshot method is not used for new documents.
16. Generator: the batch-1 KY and NY static rows are superseded (KY by the live builder, NY by the
    batch-2 retry row); `slug()` is left as batch 1 wrote it and a separate `slug_full()` serves the
    untruncated ND convention; families are disjoint so `found` sums to `index_document_count`.
17. Timing measured with `date` stamps around each extraction; artifact timestamps agree.

## Remaining from #680

Discovery-gap states not yet attempted (in #680's order): NC, OH, MT, OK, GA, TN, MI (7; TN and MI
borderline, re-check against the publisher rather than the threshold). Blocked and needing another
route or an official export: NY (OTDA, TSPD challenge), AZ (DES FAA host, TSPD challenge). Superseding
scopes needed for revised editions found today: KY Volumes II and IIA (OMTL-704), NE Title 475
chapters 2 and 3 (2026-07-28), AR SNAP Certification Manual 07.01.2026 and Appendices 07.30.2026, NV
A-100, A-200, A-700, A-1800, B-400, B-900, WY Table II (July 2026), ND Release 26.7 topic text and
landing/TOC; plus ME Ch. 609 from batch 1. Follow-on families: KY SNAP E&T State Plan 2026; AR SNAP
E&T State Plans; WY CM Updates; NV transmittal letters; ND pre-26.5 release PDFs; MA DTA Online Guide;
NH Service Releases; OTDA ADM/INF/GIS directives; FL quarterly Summary of Changes. Controller steps
after review: `sign-ingest-manifest` per scope, an immutable release selector, `publish_corpus.py
--dry-run`, then publication and activation; only then do the new KY, WY and ND documents (and the
batch-1 TX and NH documents) reach the encoding dashboard.
