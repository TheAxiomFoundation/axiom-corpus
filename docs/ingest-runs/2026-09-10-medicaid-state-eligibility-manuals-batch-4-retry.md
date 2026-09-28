# Medicaid state eligibility manuals, batch 4 (retry of blocked publishers from a US network)

Date: 2026-09-10
Program: Medicaid (board Year 1 list; `manifests/medicaid-agent-queue.yaml`)
Agent: one session. started_at 2026-09-10T21:33:43Z, finished_at 2026-09-10T22:22:05Z, wall time 0h 48m 22s. The controller's network
exits from a US address for this run; every host that blocked batches 1-3 was retried while the route held.
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. No function in `src/axiom_corpus`
was modified and no adapter was added. The only code change is to the batch-1/2/3 generator
`scripts/build_medicaid_state_eligibility_manual_manifests.py`: ten new `build_xx()` functions (OH, TN, LA, KY, UT, SC,
NM, KS, AZ, MT), a `document4()` wrapper (batch-4 provenance string), `fetch_impersonated()` (curl-cffi chrome120, TLS
verification on, used only after the plain request failed) and `_robohelp_topics()` (the MN/PA RoboHelp TOC walk, now
shared by UT, KS and AZ), batch-4 static rows (OR, NE, NH, HI, ME), the CA/AL retry-note appender and `--batch 4` in `main()`.
Batch-1, -2 and -3 builders and rows are untouched (`--batch 4 --only ...` was used for every regeneration).

## Retry (reviewer judgment)

All thirteen `blocked_primary_source` rows were retried at 2026-09-10T21:35Z: one plain request (Axiom user agent) plus
one curl-cffi chrome120 browser-impersonation request per recorded URL, 20 s timeouts. Outcome by host:

| Row | Recorded URL (batch 1-3) | Plain | chrome120 | Result |
| --- | --- | --- | --- | --- |
| us-ca | dhcs.ca.gov MEPM index | 200, 850 B Incapsula iframe | 200, 846 B same | still blocked |
| us-oh | codes.ohio.gov OAC 5160:1 | 200 | 200 | extracted (96 rules) |
| us-oh | medicaid.ohio.gov MEPL index | 404 | 404 | MEPL family still unreachable |
| us-az | azahcccs.gov /Resources/EligibilityPolicy/ | 200 soft-404 page | same | manual found at epm.azahcccs.gov; extracted |
| us-tn | tn.gov TennCare eligibility policy | 200 | 200 | extracted |
| us-sc | scdhhs.gov batch-3 path | 404 (site 404 page) | same | manual found at /providers/manuals/...; extracted |
| us-al | medicaid.alabama.gov | SSL error 0.4 s (no cert) | curl 28 at 20 s | still blocked |
| us-la | ldh.la.gov eligibility manual | 403 cloudflare | 200 | extracted with browser_impersonation |
| us-ky | chfs.ky.gov batch-3 path | 404 | 404 | manual found on the DFS page; extracted |
| us-or | oregon.gov ODHS eligibility page | 404 | 404 | host answers; rules are OARD 410-200 (needs_review) |
| us-ut | oepmanuals.dhhs.utah.gov | 200 | 200 | extracted |
| us-ks | kancare.ks.gov batch-3 path | 404 | 404 | manuals found under /data-policy/policy/eligibility/manuals; extracted |
| us-nm | hca.nm.gov batch-3 path | 404 | 404 | manual found on the MAD page; extracted from srca.nm.gov |
| us-ne | dhhs.ne.gov batch-3 path | 404 | 404 | host answers; Title 477 on rules.nebraska.gov (needs_review) |

Where the recorded path was a 404 the publisher's site was searched (site navigation, sitemap.xml, the agency's own
pages) for the manual's current index; nothing was ingested by guessing document URLs. Hosts retried: 13 (14 URLs).
Newly extracted: OH, AZ, TN, SC, LA, KY, UT, KS, NM (9). Still blocked: CA, AL (2). Reachable but not ingested: OR, NE
(2, `needs_review`). At 43 minutes of wall time the retry part was complete, so the not-yet-attempted list was started by
population: HI, NH, ME and MT were probed (22:20Z); MT's CMA Policy Manual index was found and extracted; NH (host answers
only to browser impersonation; manual located at /mam_htm/newmam.htm), HI (no manual; HAR chapters on the DHS rules site)
and ME (Chapter 332 publication not located) are recorded `needs_review` with the located pages. New states attempted: 4
probed, 1 extracted.

Family per state: the state Medicaid agency's eligibility policy manual (MAGI and non-MAGI eligibility, income,
resources, household composition, LTSS financial eligibility), confirmed from the agency's own index page;
transmittals, prior editions, obsolete topics, provider manuals, training material and forms on the same index are
separate families, inventoried but not taken. Where a state codifies its eligibility manual as administrative rules
(OH OAC 5160:1, NM NMAC 8.2xx) the rules are taken as `manual` (the MA/CO/NJ/OK precedent; the controller may prefer
`regulation`).

Scope: document_class `manual`, version `2026-09-10-medicaid-state-eligibility-manual`, citation paths
`us-xx/manual/<agency>/medicaid/<section>`, `source_as_of` and `expression_date` 2026-09-10 (current manual trees as
fetched; the manifests were generated before local midnight so they carry 2026-09-10; effective dates printed inside the
documents were not parsed; same judgment as batches 1-3).

Extraction: `uv run axiom-corpus-ingest extract-official-documents`, no new adapter, all artifacts under the main
checkout's `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus` (this worktree is sparse). PDFs use the extractor's
page granularity with `ocr: true`; HTML pages use `html_content_selector` per publisher (RoboHelp outputs: `body` minus
the `#rh-topic-header` chrome); the SC Word files use the extractor's existing `docx` path. TLS verification was never
disabled. Two publishers serve incomplete chains: img1.scdhhs.gov (SC MPPM host) omits the GoDaddy "Go Daddy Secure
Certificate Authority - G2" intermediate and rules.nebraska.gov omits "DigiCert Global G2 TLS RSA SHA256 2020 CA1"; both
public intermediates were fetched from the CAs' repositories (certs.godaddy.com, cacerts.digicert.com) and stored as
`data/certs/godaddy-secure-certificate-authority-g2.pem` and `data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem`,
concatenated with certifi into `data/certs/medicaid-manuals-ca-bundle.pem` (the LIHEAP precedent); the generator and the
extractor were run with `REQUESTS_CA_BUNDLE` pointing at that bundle (needed for SC only; NE was not extracted). ldh.la.gov
(LA) answers 403 to every plain client and 200 to browser impersonation, so the LA manifest sets the extractor's existing
`browser_impersonation` / `browser_impersonation_direct` request options (the Revenu Quebec precedent in
`manifests/ca-rulespec-2026-07-21-official-dependencies.yaml`). Coverage is `complete: true` with 0 missing, 0 extra and 0
duplicate citation paths for every extracted scope; `citation_path` uniqueness within each provisions JSONL and absence
from every other provisions JSONL under `data/corpus/provisions/<jurisdiction>/` (all document classes) were verified
independently with a counter script, and every manifest document path was checked against the JSONL document rows.
One transient collision (LA) is documented below; the final artifacts have none.

## Per-jurisdiction results

| Jurisdiction | Index | Documents taken | Provisions (JSONL rows) | Extraction seconds |
| --- | --- | ---: | ---: | ---: |
| us-oh | OAC 5160:1 chapter tree on codes.ohio.gov | 96 | 192 | 88 |
| us-tn | TennCare Eligibility Policy: three manual pages (AEM table feeds) | 88 | 743 | 36 |
| us-ky | DCBS Division of Family Support page (Operation Manual volumes) | 2 | 502 | 4 |
| us-sc | SCDHHS MPPM page -> img1.scdhhs.gov/mppm/ | 18 | 68 | 7 |
| us-az | AHCCCS Eligibility Policy Manual (epm.azahcccs.gov RoboHelp TOC) | 743 | 4,712 | 159 |
| us-ut | DHHS Medicaid Policy Manual (oepmanuals RoboHelp TOC) | 639 | 1,971 | 238 |
| us-nm | HCA Medical Assistance Division page (NMAC 8.2xx parts, srca.nm.gov) | 90 | 180 | 18 |
| us-ks | KDHE eligibility policy manuals page: KFMAM chapters + MKEESM July 2026 | 117 | 749 | 25 (first run); 24 (re-run) |
| us-la | LDH Medicaid Eligibility Manual page | 99 | 891 | 71 (first run); 63 (second, 95 documents); 65 (third, 99) |
| us-mt | DPHHS HCSD Combined Medicaid Assistance (CMA) Policy Manual page | 125 | 486 | 45 |

Three extraction streams ran concurrently (A: OH, TN, KY, SC; B: UT, NM; C: AZ, KS, LA), so the seconds are wall
seconds under shared network and CPU. KS was extracted twice (the first run's KFMAM selector kept the left navigation) and LA
three times (the first run collided with the CHIP scope, the second skipped the four colliding sections, the third took
them again once the CHIP session had withdrawn its copy; below); superseded artifacts were deleted before each rebuild, so
no stale source files remain.

Total: 2,017 documents, 10,494 provisions across 10 scopes. Index documents found versus taken are in the queue
rows (`index_document_count`, `taken_count`, `index_families`).

### Index inventories (every document family on the publisher index; taken counts)

**us-oh** — https://codes.ohio.gov/ohio-administrative-code/5160:1
Ohio's eligibility manual is OAC 5160:1 (Medicaid eligibility rules of the Ohio Department of Medicaid, published by the
Legislative Service Commission on codes.ohio.gov, the publisher of the existing OH SNAP rules scope). Chapter landing
pages 5160:1-1 General Principles, 1-2 Application Procedures, 1-3 Aged Blind and Disabled, 1-4 Families and Children,
1-5 Special Covered Groups, 1-6 Long-Term Care: 6 found / 0 taken (link lists). Rule pages: 96 found / 96 taken (5, 16,
36, 6, 11, 22 per chapter). 102 found, 96 taken. Selector `section.laws-body` (the rule text; the header, history and
"laws-section-info" boxes are not taken). Citation paths `us-oh/manual/odm/medicaid/5160-1-3-02-1` (rule number, colon
and dots as dashes). The ODM Medicaid Eligibility Procedure Letters (medicaid.ohio.gov) still answer HTTP 404 (5,279-byte
AmazonS3 page) to both requests for the index, the site root and path variants, so the MEPL family remains a follow-on;
batch 2 saw one chrome120 200 for that index, not reproduced here.

**us-tn** — https://www.tn.gov/tenncare/policy-guidelines/eligibility-policy.html
Division of TennCare Eligibility Policy. Manual landing pages (Administrative Manual, Aged, Blind and Disabled Manual,
Families and Children Manual): 3 found / 0 taken; each carries an AEM data table whose JSON feed
(`.../_jcr_content/content/tn_complex_datatable*.tablejson.json`) lists Section / Chapter (PDF link) / Policy Number.
Chapter PDFs: 11 + 38 + 39 = 88 found / 88 taken. "Division of TennCare Eligibility Policy Consolidated" PDF (the same
chapters in one file): 1 / 0. 92 found, 88 taken. Citation paths `us-tn/manual/tenncare/medicaid/abd-115-005`,
`.../admin-200-005`, `.../fc-015-005` (manual prefix plus policy number).

**us-ky** — https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx
DCBS Division of Family Support Operation Manual (the batch-3 `opm.aspx` path is gone; the volumes are listed on the
division page). Volume IVA Non-MAGI Medicaid (MA) and Volume IVB MAGI Medicaid, APTC/CSR and QHP: 2 found / 2 taken
(1.55 MB and 0.66 MB PDFs, 502 pages together). Other volumes (I General Administration, II and IIA SNAP, III KTAP,
IIIA Kentucky Works, IV vacant, V State Supplementation, VIII CCAP, IX OMTL cover letters, X policy updates): 10 / 0.
12 found, 2 taken. Citation paths `us-ky/manual/dcbs/medicaid/volume-iva`. The KY SNAP scope already holds Volume II.

**us-sc** — https://www.scdhhs.gov/providers/manuals/sc-medicaid-policy-and-procedures-manual (redirects to
https://img1.scdhhs.gov/mppm/)
SCDHHS Medicaid Policy and Procedures Manual (MPPM), Word files: Section 100 General Information, 200 MAGI Related
Programs, 300 Non-MAGI (SSI) Related Programs, 800 Office of Civil Rights and Privacy, Chapters 401-406 (SSI strict
income and resource policy, OSS, Pass-Along, retroactive Medicaid for SSI recipients, essential spouse), 501-504 (BCCP,
Title IV-E, RAP, TB), 601 Presumptive Eligibility, 701-703 (presumptive disability, PHE unwinding, disability
determination): 18 found / 18 taken. MIAP Manual (.docx, a separate manual): 1 / 0. Staff training portals, OnBase job
aids, eligibility workbooks, CGIS/EEMS guides (SharePoint, not public) and the medsweb forms listing: 9 / 0. 28 found, 18
taken. Citation paths `us-sc/manual/scdhhs/medicaid/section-100`, `.../chapter-401`. The docx path yields whole-document
blocks for most files (Section 100 is one 709 K-character block; Section 300 eight blocks), the CT precedent; the full text
is captured.

**us-az** — https://epm.azahcccs.gov/EligibilityPolicyManual/index.html
AHCCCS Eligibility Policy Manual (RoboHelp), linked from the AHCCCS applicant pages; the batch-2 path
`/Resources/EligibilityPolicy/` now answers a soft 404 ("Page/Document not found", HTTP 200). TOC books: Home,
Introduction, Policy, Examples, PAS Appendix-EPD, PAS Appendix-DD, News Flash, Revisions. Unique topic pages: 743 found /
743 taken (all books; examples and the PAS appendices are parts of the manual). TOC entries that repeat a topic already
listed under another book: 1,632 / 0. 2,375 TOC entries, 743 documents taken. Citation paths
`us-az/manual/ahcccs/medicaid/<topic path slug>`. The AZ DES FAA manuals already in the corpus are the SNAP/cash manuals.

**us-ut** — https://oepmanuals.dhhs.utah.gov/
DHHS Medicaid Policy Manual (RoboHelp 2022; the batch-3 probe's S3 AccessDenied is gone from this network). TOC books:
What's New, Welcome, 100 General Provisions, 200 Basic Rules, 300 Medicaid Programs, 400 Income and Household
Requirements, 500 Assets, 600 Program Benefits, 700 Eligibility Determination and Review, 800 Records and Case
Management, 900 PCN, 1000 UPP, Tables, Resources, Glossary, QnA, Continued Medicaid Unwinding Flexibilities: 639 topics
found / 639 taken. Obsolete book (prior versions of every section, `Obsolete/...`): 1,807 / 0. 2,446 found, 639 taken.
Citation paths `us-ut/manual/dhhs/medicaid/400-income-and-household-requirments-461-5-spenddown-with-medical-bills`
(the publisher's topic path, misspelling included). The DWS eligibility manual scope already in the corpus
(`us-ut-manuals.yaml`) is the FEP/SNAP manual.

**us-nm** — https://www.hca.nm.gov/lookingforinformation/medical-assistance-division-1/
Health Care Authority Medical Assistance Division page (the batch-3 path is gone). Its "NM Administrative Code (NMAC)
Rule Number / Category / Program" table lists the Medical Assistance Program Manual's eligibility chapters as NMAC parts
8.200-8.299 (90 parts: 8.200 general recipient policies 7, categories 8.201-8.299 3 each, 8.281 and 8.291 4 each) with PDF
copies on a vendor host (prod-rf-lambda.rtssaas.com). Each part was fetched instead from the official NMAC compilation
publisher's part page (https://www.srca.nm.gov/parts/title08/08.291.0400.html, HEAD-checked 200 for all 90), the same
source the us-nm SNAP regulation scope uses; 90 found / 90 taken; other NMAC parts on the page: 0. Citation paths
`us-nm/manual/hca/medicaid/8-291-400`. Selector `.WordSection1, .Section1` (the SNAP precedent), one block per part.

**us-ks** — https://www.kancare.ks.gov/data-policy/policy/eligibility/manuals
KDHE Division of Health Care Finance eligibility policy manuals page (the batch-3 path is gone). Current KFMAM (Kansas
Family Medical Assistance Manual, khap2.kdhe.state.ks.us/kfmam/, database-driven): the table of contents lists chapters
01000-08000 as `main.asp?tier1=NN000` pages, 8 found / 8 taken (selector `#content` minus the left navigation and search
boxes; the "Full Manual" page is the same text in one file, not taken as a separate document). Current MKEESM (Medical
KEESM, Elderly and Disabled, July 2026 edition, khap.kdhe.ks.gov RoboHelp): books 1000 Administration to 11000 Incorrect
Coverage, 109 topics found / 109 taken. Prior MKEESM editions (January 2018 to April 2026): 47 / 0. 164 found, 117 taken.
Citation paths `us-ks/manual/kdhe/medicaid/kfmam-01000`, `.../mkeesm-2000-2100-2110-...`. The KEESM scope already in the
corpus is the DCF cash and food manual.

**us-la** — https://ldh.la.gov/page/medicaid-eligibility-manual
LDH Medicaid Eligibility Manual, one PDF per section: Preface, A-100/A-200 (acronyms, definitions), B, C, E, F, G
(introduction, medical services, category, medical programs, application processing), H-100 to H-3900 (programs, 38),
I-100 to I-2100 (eligibility factors, 25), J to X (one each), Z-100 to Z-2500 (appendices, 17): 99 found / 99 taken.
Citation paths `us-la/manual/ldh/medicaid/h-1020`. Collision history: the first extraction (22:04Z) collided on four
paths (H-3030 LaCHIP, H-3040 LaCHIP Affordable Plan, H-3050 LaCHIP Phase IV, Z-2500 Premium Program Income Limits) with
today's CHIP scope (`us-la/manual`, version `2026-09-10-chip-state-eligibility-manual`), so the manifest was rebuilt without
them (95 documents, extracted 22:11Z). The concurrent CHIP session then deleted its LA extraction and rewrote its LA queue
row as `done` by pointer to this scope (chip-agent-queue.yaml: "a CHIP extraction of the four made in this run collided
with them and was deleted ... Nothing separate to add"), so the four sections belong here: the skip was reverted, the
95-document artifacts deleted and the full 99-document manifest extracted (22:14Z); the final collision check finds 0.

**us-mt** — https://dphhs.mt.gov/hcsd/Manuals/CMAPolicyManual
DPHHS Human and Community Services Division Combined Medicaid Assistance (CMA) Policy Manual (not-yet-attempted state,
probed and taken in this run). Section PDFs under /assets/hcsd/mamanual/ and /assets/hcsd/fmamanual/, each listed twice
(section number and title links): 0-1 Table of Contents, 0-3 Introduction, 0-4 Acronyms and Glossary, CMA 001/002 resource
and medically-needy limits, ACA FMA 003-007 (MAGI groups), ABD 008-009 and the CMA/FMA/ABD numbered sections through
CMA 1509 (case file retention): 125 found / 125 taken. Other PDFs linked from the page template (interpreter list, privacy
notice, other programs' manuals): 12 / 0. 137 found, 125 taken. Citation paths `us-mt/manual/dphhs/medicaid/aca003`,
`.../cma0-3july012016` (the publisher's file stems). The MT SNAP and TANF manual scopes already in the corpus are separate
manuals.

### New states probed, not extracted (needs_review)

- **us-nh** — dhhs.nh.gov answers HTTP 403 "Access Denied" to every plain request and HTTP 200 to chrome120
  impersonation; the Medicaid page links the "NH DHHS Online Medical Assistance Manual" (/mam_htm/newmam.htm). Index
  found, not inventoried or extracted within this run (needs the browser-impersonation request option, as LA).
- **us-hi** — medquest.hawaii.gov publishes no eligibility manual; its Rules and Policies page links the Hawaii
  Administrative Rules on humanservices.hawaii.gov (Med-QUEST eligibility is HAR Title 17, 1700-1740 series) and the
  annual MAGI income standards charts (7 PDFs). Not inventoried or extracted.
- **us-me** — the OFI Policies/Rules page carries no direct link to the MaineCare Eligibility Manual (10-144 CMR Chapter
  332); the guessed policy-manuals and SOS chapter-list paths are 404. Index not located.

### Still blocked (retried from the US network, same failure)

- **us-ca** — the DHCS MEPM index now answers HTTP 200 to both requests, but the 848-byte body is only the
  Imperva/Incapsula "Request unsuccessful" challenge iframe (incident id 491000040177845619-389699386573783349); no
  manual content, no index inventory. No workaround attempted.
- **us-al** — medicaid.alabama.gov now accepts TCP, but the TLS handshake never completes: curl and curl-cffi chrome120
  time out after the Client Hello (curl 28 at 20 s); python requests gets an SSL EOF / "unable to get local issuer
  certificate" within 0.4 s, i.e. no server certificate is delivered (openssl s_client shows no certificate chain).
  Not a chain-repair case. No workaround attempted.

### Reachable, not ingested (needs_review)

- **us-or** — oregon.gov resolves and answers, but the ODHS eligibility page recorded in batch 3 is 404 and no OHA page
  carries an OHP eligibility manual; the OHP eligibility rules are OAR chapter 410 division 200 on the Secretary of
  State OARD (HTTP 200, JavaScript application), which the existing `extract-oregon-admin-rules` adapter already targets
  as document_class `regulation`. Reviewer judgment: not duplicated through the manual-class official-documents path;
  the controller should run that adapter for division 410-200 or decide the class.
- **us-ne** — dhhs.ne.gov answers; the "Title 477 Medicaid Eligibility" page points to the Title 477 chapter listing on
  rules.nebraska.gov (JavaScript application; TLS chain fixed with the DigiCert intermediate) and to a Title 477
  Appendix page with 47 appendix PDFs (477-000-002 to 477-000-061). The chapter PDFs are served through the SOS site's
  API (the us-ne SNAP regulation scope used `rules.nebraska.gov/api/fileStorage/GetAsByteArray/chapter-pdfs/...` with
  `verify_tls: false`, which this batch does not repeat); the API listing for Title 477 was not located within this run,
  so nothing was taken. Follow-on: enumerate the chapters through the SOS API with the bundle, then take chapters plus
  the 47 appendices.

## Artifacts (unsigned, uncommitted, awaiting controller)

- `data/corpus/sources/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual/official-documents/*`
- `data/corpus/inventory/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.json`
- `data/corpus/provisions/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.jsonl`
- `data/corpus/coverage/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.json`

for xx in oh, tn, ky, sc, az, ut, nm, ks, la, mt, under `/Users/pavelmakarchuk/axiom-corpus/data/corpus` (main checkout),
alongside the batch-1 to batch-3 artifacts. Other sessions (CHIP, SSI and others) write to the same base concurrently;
nothing outside these ten scopes was touched by this session.

Rebuild:

```bash
export REQUESTS_CA_BUNDLE=$PWD/data/certs/medicaid-manuals-ca-bundle.pem
uv run python scripts/build_medicaid_state_eligibility_manual_manifests.py --batch 4
for j in oh tn ky sc az ut nm ks la mt; do
  uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-10-medicaid-state-eligibility-manual \
    --manifest manifests/us-$j-medicaid-eligibility-manual.yaml \
    --source-as-of 2026-09-10 --expression-date 2026-09-10
done
```

Lint: `uv run ruff check scripts/build_medicaid_state_eligibility_manual_manifests.py` is clean. `uv run ruff check scripts/`
still reports the 8 pre-existing findings in two unrelated scripts noted in batches 2 and 3; left alone.

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped (31 s; run after the last generator change). The 10 failures are exactly the expected pre-existing data-dependent tests of this sparse worktree
(`test_be_rulespec_2026_08_23_promotion`, `test_build_ny_tanf_compatibility_scope` x2, `test_rulespec_be_source_promotion`,
`test_us_ak/ct/mi/mt/nd/ny_snap_manual`); none touches the Medicaid manifests or the generator, and no other test failed.

## Reviewer judgments (all of them)

1. Retry protocol: every blocked row got exactly one plain and one chrome120 request at the recorded URL; where the
   recorded path was a 404 on an answering host the manual's current index was located through the publisher's own
   navigation or sitemap, never by guessing document URLs; CA and AL keep `blocked_primary_source` with the retry
   appended; OR and NE become `needs_review` because the hosts answer but the manual is served by a rules publisher
   (OARD, rules.nebraska.gov) that this batch did not ingest.
2. TLS chains: the two incomplete chains (img1.scdhhs.gov, rules.nebraska.gov) were repaired with the CAs' public
   intermediates under `data/certs/` and `REQUESTS_CA_BUNDLE`; verification was never disabled, and the NE SNAP scope's
   `verify_tls: false` precedent was deliberately not repeated.
3. LA: taken with the extractor's existing browser-impersonation request option because the publisher answers 200 to a
   browser client and 403 to plain clients (no interstitial to solve); the four LaCHIP sections are taken here because the
   CHIP session withdrew its colliding copy and points its LA row at this scope (a skip-then-revert during the run; the
   final state has no collision).
4. OH: OAC 5160:1 rule pages are the eligibility manual (the OK/MA/CO/NJ codified-rules-as-`manual` judgment); the MEPL
   family stays unreachable (404 from medicaid.ohio.gov) and is recorded as a follow-on; chapter landing pages not taken.
5. NM: the HCA page lists the NMAC parts with vendor-hosted PDF copies; each part is fetched from the official NMAC
   compilation (srca.nm.gov), the SNAP-scope precedent, under `manual` paths (no collision with the `regulation` paths of
   the SNAP scope); only the 8.2xx eligibility chapters are the manual.
6. AZ: all TOC books (Introduction, Policy, Examples, PAS appendices, News Flash, Revisions) are taken as one manual; TOC
   repeats of an already-listed topic are inventoried (1,632) but count once.
7. UT: the Obsolete book (1,807 prior-version topics) is a prior-release family, not taken; What's New, Welcome, Tables,
   Resources, Glossary and QnA are taken as parts of the manual.
8. KS: both current manuals (KFMAM chapter pages and the July 2026 MKEESM) are one scope; the 47 prior MKEESM editions are
   not taken; the KFMAM "Full Manual" page is the same text and is not taken as a separate document.
9. KY: Volumes IVA and IVB only; Volume I (general administration across programs) is a separate family.
10. SC: the 18 MPPM section/chapter Word files only; the MIAP manual and the non-public SharePoint material are not taken;
    whole-document docx blocks accepted (CT precedent).
11. TN: the 88 chapter PDFs from the three manuals' table feeds; the consolidated PDF (same chapters in one file) is not
    taken.
12. PDF manuals at page granularity with OCR fallback; `expression_date` = fetch date (as batches 1-3).
13. Three concurrent extraction streams, so per-state seconds are shared-resource wall times; KS and LA rebuilt once each
    after the first run (selector fix, collision skip) with the first artifacts deleted.
14. New states: the retry finished under 60 minutes, so HI, NH, ME and MT were probed in population order; MT was taken
    from its CMA Policy Manual index (all 125 section PDFs, template PDFs not taken); NH, HI and ME are recorded
    `needs_review` with the pages located rather than extracted by guessing, and no further state was pulled.
15. `ruff` findings in two unrelated scripts under `scripts/` left unfixed (as batches 2 and 3).

## Remaining for later batches

Still blocked: CA (Incapsula), AL (TLS handshake). Reachable, needs a controller decision or a small follow-on: OR (OAR
410-200 through the existing OARD adapter, or as manual), NE (Title 477 chapters through the SOS API plus the 47 appendix
PDFs). Probed, needs a small follow-on: NH (MAM with browser impersonation), HI (HAR chapters), ME (Chapter 332 publication).
Not yet attempted (by population): RI, DE, SD, ND, AK, DC, VT, WY, plus the territories.
Follow-on families: OH MEPLs (medicaid.ohio.gov 404); SC MIAP manual; KS prior MKEESM editions; UT obsolete topics; TN consolidated PDF; the batch-1 to batch-3
lists. Controller steps after review: decide `manual` vs `regulation` for OH and NM (and OK, MA, CO, NJ),
`sign-ingest-manifest` per scope, immutable release selector, `publish_corpus.py --dry-run`, then publication and
activation.
