# SSI state-administered supplements, batch 3 (the remaining rows)

Date: 2026-09-11
Program: SSI, optional state supplementary payments administered by the states (queue
`manifests/ssi-agent-queue.yaml`; the five `needs_review` rows and the OK `blocked_primary_source` row left by
`docs/ingest-runs/2026-09-10-ssi-state-supplements-batch-2.md`, plus the six states that had no row at all).
Agent: two sessions on a controller whose network exits from a US address. The first probed WI, AK and WY
(2026-09-11T09:20-09:22Z; three index pages and three empty probe files left in the worktree root, moved out and
re-fetched) and was killed before writing anything else. This continuation: started_at 2026-09-11T09:35:34Z,
finished_at 2026-09-11T10:48:23Z, wall time 1h 12m 49s (probes and index inventories 09:36-10:15Z, generator runs
10:16Z, 10:29Z, 10:33Z and 10:4xZ after three inventory fixes, the five extractions 10:34:42-10:40:17Z, verification,
tests, this note, commit).
Impact analysis: not run; the GitNexus MCP tools were unavailable. No function in `src/axiom_corpus` was
modified and no adapter was added. The only code change is the batch-3 extension of the generator
`scripts/build_ssi_state_supplement_manifests.py` (a shared RoboHelp 2022 TOC walker, builders for AK, WI, MO, SD,
OK, static `done` rows for the six no-supplement states, the WY block, `--batch 3`, now the default; batch-1 and
batch-2 states are never regenerated), `ruff`-clean.

## Re-probe of OK and the leads from batch 2 (one plain request, one chrome120 impersonation, 20 s timeouts)

- **us-ok** — https://oklahoma.gov/okdhs/library/policy/current/oac-340/chapter-15.html now answers HTTP 301 to
  https://rules.ok.gov/home (the whole OKDHS policy library redirects there). rules.ok.gov/home: Cloudflare HTTP 403
  (5,316-byte "Just a moment..." page) to the plain client; chrome120 impersonation HTTP 200 (1,551-byte JavaScript
  application shell, no rule text) on the first request and HTTP 403 (5,906 bytes) on the second. The publication's
  own segments API, `prod-ok-rules-api.tecuity.com` (the `download_url` of the corpus's 2026-07-21 `us-ok/regulation`
  SNAP rules scope, `manifests/us-ok-snap-rules.yaml`), answers HTTP 200 to the plain client for
  `GetSegmentsByChapterNum?titleNum=340&chapterNum=15` (47,193 bytes) and `GetSegmentsByTitleNum?titleNum=340`
  (12,920,396 bytes, 32 s). Inventoried and extracted from the API (below); the row leaves `blocked_primary_source`.
- **us-wi** — the batch-2 lead "DHS 2 Wis. Adm. Code" is wrong: docs.legis.wisconsin.gov/code/admin_code/dhs/001/2
  is "Recoupment of Benefit Overpayments" and the DHS chapter index (Chs. DHS 1-19, 30-100, 101-109, 110-199,
  250-) has no state-SSI chapter. The DHS SSI program's Forms and Publications page lists the agency's three SSI
  handbooks on emhandbooks.wisconsin.gov (HTTP 200 plain). Extracted (below).
- **us-ak** — http://dpaweb.hss.state.ak.us/manuals/apa/apa.htm HTTP 200 (33,512 bytes, RoboHelp 2022) to the plain
  client; the https port does not answer (connect timeout 20 s). Extracted over http (below), as the SNAP manual scope.
- **us-mo** — dssmanuals.mo.gov answered HTTP 200 (the first probe at 09:4xZ timed out at the TCP level, 000 after 9.9 s;
  the second and every later request answered). The site search for "Supplemental Nursing Care" surfaces the SNC
  Manual, which the home-page manual list omits; the SAB and Blind Pension manuals exist at the same kind of path.
  Extracted (below).
- **us-sd** — sdlegislature.gov/Rules/Administrative/67:12:14 HTTP 200 (5,982-byte JavaScript shell) plain; the LRC
  rules API `api/Rules/67:12` (2,256,882 bytes) and `api/Rules/67:12:14` (25,909 bytes) HTTP 200 plain. Extracted.
- **us-wy** — dfs.wyo.gov HTTP 200 plain (assistance-programs, cash-assistance, policy-manuals pages inventoried: no
  SSI supplement family). The Department of Health's Eligibility Operations Manual ecom.wyo.gov HTTP 200 plain, section
  M1804 State Supplemental Payments HTTP 200 (248,711 bytes) but its content is a script-rendered Google Drive viewer
  embed (below). Blocked.

## Batch selection (reviewer judgment)

All remaining rows, no population ordering needed: (1) the six states with no row, AR, AZ, MS, ND, TN, WV, which
POMS SI 01415.010 lists with Optional = N; (2) the five `needs_review` rows MO, WI, SD, AK, WY; (3) OK re-probed once.
Probed: 12. Attempted: 12. Extracted: 5 (AK, WI, MO, SD, OK). Done by POMS finding: 6 (AR, AZ, MS, ND, TN, WV).
Blocked: 1 (WY). After this batch every one of the 51 jurisdictions (50 states and DC) has a resolved row: 52 rows
including the federal POMS SI row; `needs_review` is empty.

Family per state, as in batches 1 and 2: the state agency's own governing document for the optional supplement
(eligibility, payment standards, living arrangements), confirmed from the publisher's own index: the adopted rule
where the state publishes the rule itself as the program's governing text (SD, OK), the agency manual where the manual
is the governing text (AK, WI, MO). No compiled list (SSA's "State Assistance Programs for SSI Recipients",
PolicyEngine files) was used as a source; web search was used only to identify each state's own publisher and
program name, and every document was taken from that publisher's index. The POMS SI 01415.010 state table already
in the corpus (version `2026-09-10-ssi-poms-si`) was read to confirm the six no-supplement states (Arizona S/N,
Arkansas F/N, Mississippi F/N, North Dakota NR/N, Tennessee F/N, West Virginia N/N).

Scope: version `2026-09-10-ssi-state-supplement` for all five manifest scopes; `document_class` by the document's
nature (`manual` for AK, WI, MO; `regulation` for SD, OK) with each jurisdiction's existing citation conventions
(`us-ak/manual/dpa/<manual>/<topic>` and `navigation/toc-<key>` of the SNAP manual scope; `us-mo/manual/dss/<manual>/
<section path>` of the MHABD Medicaid scope; `us-sd/regulation/arsd/67/12/14/<section>` of the CHIP and TANF scopes;
`us-ok/regulation/oac/340/15/<section>` of the SNAP rules scope; `us-wi/manual/dhs/ssi/<handbook>/<topic>`, a new
DHS group beside the MEH PDF scope `us-wi/manual/dhs/medicaid/...`); `source_as_of` 2026-09-11 (the fetch date);
`expression_date` the date the publisher prints where there is one (WI: both handbooks print "Release 26-01 May 1,
2026"; SD: 1993-12-31, the latest "effective" date in the chapter's SDR source notes) and otherwise the fetch date
(AK topics carry manual-change transmittal references, latest Memo MC #76 (09/26); MO sections print their own IM memo
dates; the OK API carries no effective dates for chapter 15).

Extraction: `uv run axiom-corpus-ingest extract-official-documents` for the five manifests; artifacts under the
main checkout's `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus` (this worktree is sparse). TLS verification
was never disabled; no certificate was needed (no publisher in this batch serves an incomplete chain; AK is plain
http, the publisher's only working scheme). No `browser_impersonation` was needed for any extracted document (all
five publishers answer the plain client); impersonation was used only for the OK and MO probes recorded above. No
proxy, mirror or third-party copy was used anywhere. Coverage is `complete: true` with 0 missing, 0 extra and 0
duplicate citation paths for all five scopes; `citation_path` uniqueness within each provisions JSONL, every
inventory source reference (regular file under the scope's own `sources/` boundary, no symlinks, SHA-256 matching),
every provision's `source_path` present in its inventory, and absence from every other provisions JSONL under
`data/corpus/provisions/<jurisdiction>/` (all document classes, including today's Medicaid, CHIP, TANF, CCDF, WIC and
SNAP scopes) were verified independently with a counter script (`verify_scopes.py`, scratch): 0 in-file
duplicates, 0 collisions, 0 source-reference problems. The regenerated manifests were checked against the
provisions (same `source_url` sets; every manifest `citation_path` is a root row; no root row outside the manifest).

## Per-jurisdiction results

| Jurisdiction | Program | Index | document_class | Documents taken | Provisions | Extraction seconds |
| --- | --- | --- | --- | ---: | ---: | ---: |
| us-ak | Adult Public Assistance (APA) | DPA APA Manual RoboHelp TOC (dpaweb.hss.state.ak.us) | manual | 330 (225 topics + 105 TOC snapshots) | 660 | 334.8 (10:34:42-10:40:17Z) |
| us-wi | State SSI Supplement, SSI-E | DHS SSI Forms and Publications page -> emhandbooks.wisconsin.gov | manual | 13 (5 + 8 topics) | 151 | 16.7 (10:35:07Z) |
| us-mo | Supplemental Nursing Care (SNC), Supplemental Aid to the Blind (SAB) | dssmanuals.mo.gov index and WordPress sitemap | manual | 89 (35 + 54 sections) | 182 | 145.5 (10:35:24-10:37:49Z) |
| us-sd | Optional State Supplemental Program | LRC rules API, ARSD Article 67:12 | regulation | 1 chapter (11 sections) | 12 | 5.1 (10:37:49Z) |
| us-ok | State Supplemental Payment (SSP) | OAR rules.ok.gov segments API, OAC Title 340 | regulation | 1 chapter (6 sections in force, 2 revoked excluded) | 7 | 4.7 (10:37:55Z) |

Total: 434 documents, 1,012 provisions (1,042,477 body characters) across 5 scopes in 5 jurisdictions. Index
documents found versus taken are in the queue rows (`index_document_count`, `taken_count`, `index_families`):
found 586 across the five inventoried indexes (AK 330, WI 66, MO 139, SD 21, OK 30), taken 434.

### Index inventories (every document family on the publisher index; taken counts)

**us-ak** — http://dpaweb.hss.state.ak.us/manuals/apa/whxdata/toc.new.js (landing http://dpaweb.hss.state.ak.us/manuals/apa/apa.htm)
Alaska Adult Public Assistance Manual (Department of Health, Division of Public Assistance; title page "July 1999",
current through Memo MC #76 (09/26)), RoboHelp 2022 table of contents walked to closure: 105 TOC files, 561 TOC
entries of which 336 are same-page anchors, 225 distinct topic pages. Policy topics (400 General Information, 410
Application Process, 420 Development of Income, 421 Citizenship and Alien Status, 422 SSN, 423 Alaska Residency, 424
Age, 425 Blindness/Disability, 426 Interim Assistance, 430-433 Resources, 440-443 Income, 450 Living Arrangements, 451
Eligibility Determinations, 452 Payments, 460 Financial Responsibility and Deeming, 470 Institutions, 480 Case
Maintenance, 481 Notices, 482 Claims, Addendum): 147 found / 147 taken. Transmittal and manual-change memo pages
(Title Page, Memo MC #76, previous transmittals MC #1-#75 and the 1999 edition memo): 78 / 78 (the SNAP manual scope
took its transmittals too). TOC files snapshotted as `navigation/toc-<key>` rows (source_format javascript, the SNAP
scope's `manual_toc_snapshot` rows): 105 / 105. 330 found, 330 taken. Citation `us-ak/manual/dpa/apa/<topic-slug>`
(+ `/block-1`), e.g. `us-ak/manual/dpa/apa/450-450-living-arrangements`; 660 rows (330 documents + 330 blocks; 2
blocks under 60 characters). The topic header, header shadow, RoboHelp glossary pop-ups (`.expanding-content`) and
the transmittal-link table are dropped, as in the SNAP manifest. The corpus's `us-ak/guidance/dpa/apa/standards/2026`
(APA standards PDF, 2026-06-30) is the payment-standard table, a different class; no collision.

**us-wi** — https://www.dhs.wisconsin.gov/ssi/publications.htm (DHS SSI program "Forms and Publications"; program
index https://www.dhs.wisconsin.gov/ssi/index.htm)
Handbooks (emhandbooks.wisconsin.gov, RoboHelp 2022): **SSI Administration Handbook, P-23129** (1.1 Introduction, 2.1
Federal and State SSI Recipients, 3.1 State-Only SSI Recipients, 4.1 SSI Payment Levels, 4.2 Forms and Pubs): 5 / 5;
**SSI-E Handbook, P-20679** (1.1 Introduction, 2.1 SSI-E for People in Substitute Care, 3.1 SSI-E for People in Natural
Residential Settings, 4.1 SSI-E and Other Benefits, 5.1 Appeals and Complaints, 6.1 SSI-E Payment Rates, 6.2
Grandfathered Facilities, 6.3 SSI Forms): 8 / 8; SSI Caretaker Supplement (CTS) Policy Handbook, P-23131 (27 topics;
Release 26-01 August 12, 2026): 27 / 0. DHS SSI program web pages (index, apply, benefits, caretaker, eligibility,
forms & publications, glossary, SSI-E, links): 9 / 0. Forms (F-20817, F-20817A, F-22565, F-22564, F-10126, F-22571,
F-20818, F-02340, F-20812 ...): 10 / 0. Interim-assistance reimbursement letter templates (Word): 3 / 0. Fact sheets
and publications (P-23110, P-23128, P-23043, P-02176): 4 / 0. 66 found, 13 taken. Both taken handbooks print "Release
26-01 May 1, 2026" on every topic. Citation `us-wi/manual/dhs/ssi/ssi-admin/<topic>` and `us-wi/manual/dhs/ssi/ssi-e/
<topic>` (e.g. `.../ssi-admin/4-1` + `/block-N`); 151 rows (13 documents, 138 blocks; block-1 of each topic is the
"State of Wisconsin Department of Health Services Release 26-01 May 1, 2026 / View History" banner, 88 characters,
kept as page content). The 4.1 payment table (federal $994.00 + state $92.16 for an eligible individual living
independently, effective May 1, 2026) is in `.../ssi-admin/4-1`.

**us-mo** — https://dssmanuals.mo.gov/ (DSS Manuals site; pages enumerated from
https://dssmanuals.mo.gov/wp-sitemap-posts-page-1.xml and -2.xml, 3,411 URLs, the MHABD scope's method)
**Supplemental Nursing Care (SNC) Manual** (0600 SNC, 0605 Eligibility, 0610 Financial Need, 0615 Payment and Amount
of Grant, 0620 Medicaid Coverage, 0625 Prompt Disposition, 0630 Annual Renewals and Change in Circumstance, 0635
Location of SNC Case Records, with subsections): 35 / 35. **Supplemental Aid to the Blind (SAB) Manual** (0400 SAB,
0405 Eligibility Requirements, 0410 Determining Need, 0415 Payment and Amount of Grant, 0420 Medicaid Eligibility,
0425 Application Processing, 0430 Annual Renewals and Change in Circumstance, 0435 Referral to Rehabilitation
Services for the Blind, 0440 Location of SAB Case Records, with subsections): 54 / 54. Blind Pension Manual (0500-0530
and Appendix A; 0505.000.00 Eligibility Requirements is password-protected): 42 / 0. Other DSS manuals on the site
index (Children's Services, Family MO HealthNet (MAGI), Food Stamps, Forms, Independent Living Rehabilitation, MHABD,
Prevention of Blindness, Temporary Assistance; Child Welfare, VR and OBS are linked at deeper paths): 8 / 0. 139
found, 89 taken. Citation `us-mo/manual/dss/snc/0605-000-00/0605-005-00` and `us-mo/manual/dss/sab/0405-000-00/...`
(+ `/block-N`), `.entry-content` selector; 182 rows (89 documents, 93 blocks).

**us-sd** — https://sdlegislature.gov/api/Rules/67:12 (LRC rules API, ARSD Article 67:12 Assistance Payments;
landing https://sdlegislature.gov/Rules/Administrative/67:12:14)
Article 67:12 chapters: in force 8 (67:12:01 Assistance applications and eligibility, 02 Notice to applicants and
recipients, 04 Limitations on real property, 05 Limitations on personal property, 06 Budgeting, 12 Dependent children
foster care, 13 Repatriate program, **14 Optional state supplemental program**): 8 / 1; repealed or transferred 13
(03, 07-11, 15-21): 13 / 0. 21 found, 1 taken. Chapter 67:12:14 sections 01 Definitions, 02 Eligibility requirements
for optional state program, 03 Termination of optional supplemental payment, 04 Payment of the optional supplement,
05 Death of recipient, 06 Notice of eligibility, 07 Notice of termination, 08 Determination of eligibility for
retroactive payments, 09 Payment of retroactive benefits, 10 Social security "pass-on" increases, 11 Suspension of
optional supplemental payment during SSI appeal; sources 5 SDR 6 (effective 1978-08-06) to 20 SDR 92 (effective
1993-12-31). Citation `us-sd/regulation/arsd/67/12/14` + `/NN`, the CHIP 67:46 convention (JSON `Html` field, labeled
sections); 12 rows.

**us-ok** — https://prod-ok-rules-api.tecuity.com/GetSegmentsByTitleNum?titleNum=340 (the rules.ok.gov
publication's segments API; landing https://rules.ok.gov/home)
OAC Title 340 (Department of Human Services) chapters: current 17 (1 Function and Structure, 2 Administrative
Components, 5 Adult Protective Services, 10 TANF, **15 State Supplemental Payment / Children and Youth with Special
Health Care Needs**, 20 LIHEAP, 25 Child Support Services, 40 Child Care Subsidy, 50 SNAP (already in the corpus),
60 Refugee Resettlement, 61 Repatriation, 65 Public Assistance Procedures, 70 Social Services, 75 Child Welfare
Services, 100 Developmental Disabilities Services, 105 Aging Services, 110 Licensing Services): 17 / 1; revoked 13
(30, 35, 45, 55, 78, 80, 85, 90, 95, 115, 120, 125, 130): 13 / 0. 30 found, 1 taken. Chapter 15 segments: Subchapter 1
State Supplemental Payment (340:15-1-1 Purpose and legal basis, -2 Definitions, -3 Legal basis [revoked], -4 SSP plan,
-5 State Supplemental Payment, -6 Special requirements, -7 Non-conditioning of assistance payments [revoked]) and
Subchapter 3 Children and Youth with Special Health Care Needs (340:15-3-1 Eligibility and available services), the
API's chapter description being the CYSHCN title. Citation `us-ok/regulation/oac/340/15` + `/340-15-1-N`, the SNAP
rules scope's records convention (revoked and reserved segments excluded; subchapter headings carried in section
metadata, as in that scope); 7 rows.

### No optional state supplement (done by the POMS finding; nothing fetched)

POMS SI 01415.010 "Administration of State Supplementary Programs" (state table, in the corpus as
`us/manual/ssa/poms/si/01415.010/block-1`, version `2026-09-10-ssi-poms-si`) lists six states with Optional = N:
**Arizona** (Mandatory S), **Arkansas** (F), **Mississippi** (F), **North Dakota** (NR), **Tennessee** (F), **West
Virginia** (N). No state agency document exists to inventory for an optional supplement; each gets a `done` row
(`source_kind: ssa_poms_section`, `administration: N`) pointing at the POMS row and the federal manifest. No regional
POMS section exists for these states in the SI 01415 family (the regional sections are BOS, CHI, DAL, DEN (Montana),
NY, PHI (Pennsylvania), SEA, SF).

### Blocked publishers (no workaround attempted)

- **us-wy** — https://ecom.wyo.gov/m1800-other-programs/m1804-state-supplemental-payments. Wyoming's State
  Supplemental Payments are administered by the Department of Health (Division of Healthcare Financing); the agency's
  governing text is Eligibility Operations Manual section M1804 on ecom.wyo.gov (Google Sites; the EOM navigation lists
  107 sections from M100 Purpose to M1900 Hearings, M1804 the one SSP section; M1800 Other Programs also holds M1803
  Kid Care CHIP, M1805-M1811). The page answers HTTP 200 (248,711 bytes) to the plain client, but `div[role=main]`
  carries only the title: the content is a Google Drive viewer embed rendered by script
  (`embeds.googleusercontent.com/embeds/.../inner-frame-minified.html`, `data-embedded-items-count="1"`) and the HTML
  carries no document URL, file id or `docs.google.com`/`drive.google.com/file` reference, so the document is not
  addressable from the publisher's page (the extractor's Google Drive support needs a file URL). DFS (dfs.wyo.gov)
  lists no SSI supplement family (Cash Assistance = POWER: eligibility, income and resource requirements, monthly
  benefit amounts, work program; policy manuals: APS, Child Support, SNAP/POWER (in the corpus), Foster Care). The
  Secretary of State's rules.wyo.gov (ASP.NET search application, HTTP 200) was not searched for a Department of
  Health SSP rule chapter. No index document taken; the row carries the EOM index count (107 / 0).
- **us-ny** — unchanged from batch 2 (JavaScript challenge); not re-probed in this batch.

Queue rows: the five extracted states carry `index_url`, `index_document_count`, `taken_count` and `index_families`
with the counts above; the six no-supplement rows are new (alphabetical position, `target_scope` the federal scope
alias, `index_document_count: 1`, `taken_count: 1` for the POMS row already in the federal family); the WY row carries
the M1804 URL as `primary_source_url`, the EOM root as `index_url` and the failure in `notes`; the OK row moves from
`blocked_primary_source` to `agent_ready` with the re-probe record in `notes`. `status_counts`: agent_ready 28 (23 +
AK, WI, MO, SD, OK), done 22 (16 + AR, AZ, MS, ND, TN, WV), blocked_primary_source 2 (NY, WY), needs_review 0; 52 rows
(51 jurisdictions + federal), reconciled against the rows by script. Top-level `queue_status` stays `in_progress`
(two blocked rows; signing, release selectors and publication are controller steps).

## Artifacts (unsigned, uncommitted, awaiting controller)

- `data/corpus/sources/us-xx/<class>/2026-09-10-ssi-state-supplement/official-documents/*`
- `data/corpus/inventory/us-xx/<class>/2026-09-10-ssi-state-supplement.json`
- `data/corpus/provisions/us-xx/<class>/2026-09-10-ssi-state-supplement.jsonl`
- `data/corpus/coverage/us-xx/<class>/2026-09-10-ssi-state-supplement.json`

for us-ak/manual, us-wi/manual, us-mo/manual, us-sd/regulation, us-ok/regulation, all under
`/Users/pavelmakarchuk/axiom-corpus/data/corpus` (main checkout). No certificate was added this batch.

Rebuild (the generator caches index pages and API responses under `~/.axiom/ssi-state-supplement-cache`; the
extractor re-fetches every document; no CA bundle and no `browser_impersonation` needed):

```bash
uv run python scripts/build_ssi_state_supplement_manifests.py --print-index   # batch 3 (default)
for s in ak wi mo sd ok; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-ssi-state-supplement \
    --manifest manifests/us-$s-ssi-state-supplement.yaml
done
```

Lint: `uv run ruff check scripts/build_ssi_state_supplement_manifests.py` clean.

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped (46.0 s). The ten failures are the known sparse-worktree data-dependent tests
(`test_be_rulespec_2026_08_23_promotion`, `test_build_ny_tanf_compatibility_scope` x2,
`test_rulespec_be_source_promotion`, `test_us_ak/ct/mi/mt/nd/ny_snap_manual`), identical to batches 1 and 2; none
touches the SSI manifests or the generator. No adapter was added, so no new tests.

## Reviewer judgments (all of them)

1. Batch = every remaining row, no population ordering: the six states with no row, the five `needs_review` rows
   and one OK re-probe. Twelve probed, twelve attempted; every one of the 51 jurisdictions now has a resolved row.
2. No-supplement rule: a state that POMS SI 01415.010 lists with Optional = N pays no optional supplement, so there is
   no state document to inventory; the row is `done` with the POMS pointer (AR, AZ, MS, ND, TN, WV). The POMS table
   was read from the corpus's own POMS scope, not from SSA's compiled "State Assistance Programs" publication. The
   mandatory-column value is recorded in each note; the federally administered mandatory supplements (AR, MS, TN) need
   no separate state extraction either.
3. OK: taken from the rules.ok.gov publication's own segments API (prod-ok-rules-api.tecuity.com). Judged not a
   workaround of the publisher: the API is the Secretary of State's own data service behind rules.ok.gov (the site is a
   JavaScript front end to it), it answers the plain client with no fingerprint or challenge, it is already the
   corpus's `download_url` for the 2026-07-21 OK SNAP rules scope, and no proxy, mirror or third-party copy is
   involved. The Cloudflare block on the HTML front end (plain 403; impersonation 200 shell then 403) is recorded in the
   row, and the row moves from `blocked_primary_source` to `agent_ready`. `document_class` `regulation`; whole chapter
   15 taken (Subchapter 3 CYSHCN belongs to the same chapter; revoked 340:15-1-3 and -7 excluded by the SNAP scope's
   status filter); `expression_date` = fetch date (the API carries no effective dates for these segments).
4. SD: `document_class` `regulation`; ARSD 67:12:14 is the adopted Optional State Supplemental Program rule, taken
   from the LRC rules API exactly as the CHIP (67:46) and TANF (67:10) scopes (JSON `Html`, labeled sections,
   `us-sd/regulation/arsd/67/12/14/NN`). `expression_date` 1993-12-31, the latest "effective" date in the chapter's SDR
   source notes. Repealed and transferred chapters in the article are inventoried, not taken.
5. AK: `document_class` `manual`; the Adult Public Assistance Manual is the governing text of APA (Alaska's state
   supplement), taken in full (225 topic pages including the 78 transmittal and manual-change memo pages, plus 105 TOC
   snapshots) mirroring the SNAP manual scope's structure and drop selectors; `expression_date` = fetch date (the
   manual's title page prints July 1999 and topics carry MC transmittal references). The TOC's 336 same-page anchors
   are deduplicated to their pages (a first generator run with a 400-page sanity threshold failed on this; the
   threshold is 200 and the count is recorded in a comment). The http scheme is the publisher's only working one.
6. WI: `document_class` `manual`; the governing text of the state SSI payment is the DHS SSI Administration Handbook
   (P-23129), taken with the SSI-E Handbook (P-20679; the Exceptional Expense Supplement is a component of the state SSI
   payment), both from the DHS handbook host emhandbooks.wisconsin.gov, listed on the DHS SSI program's own Forms and
   Publications page (the index of record). The Caretaker Supplement handbook (P-23131) is a TANF-funded cash benefit to
   SSI parents under Wis. Stat. 49.775, not an optional SSI supplement under section 1616; recorded as a separate
   family, not taken, for the controller. Wisconsin has no administrative-rule chapter for the payment (batch-2 lead
   corrected). `expression_date` 2026-05-01 (Release 26-01). The release banner block is kept as page content.
7. MO: `document_class` `manual`; the SNC and SAB manuals are FSD's governing text for Missouri's two state-administered
   supplements (SNC for SSI-eligible residents of licensed residential care, assisted living and nursing facilities
   without vendor payments; SAB for blind persons), enumerated from the publisher's sitemap as the MHABD scope was.
   The Blind Pension Manual is a state-only pension for blind persons not eligible for SAB (not an SSI supplement) and
   its eligibility section is password-protected: separate family, not taken. 13 CSR 40-2 (the Secretary of State's
   FSD chapter) was inventoried from its PDF table of contents and has no SNC/SAB-specific rule; the MHABD scope names
   SNC on 22 rows but carries no SNC/SAB eligibility text, so this is not a pointer case. `expression_date` = fetch date.
8. WY: `blocked_primary_source` because the governing document (EOM M1804) is served only inside a script-rendered
   Drive embed with no addressable URL; the page is not fetched in any other way (no headless browser, no guessing of
   Drive ids). The EOM navigation is inventoried (107 / 0) so the row has an index record. rules.wyo.gov (Department of
   Health rule chapters) is named as a lead for the controller, not searched.
9. No `browser_impersonation`, no CA bundle and no adapter were needed; TLS verification was never disabled; no
   PolicyEngine file or compiled list was read; no secrets in any file (manifests carry only public publisher URLs).
10. The batch-2 judgment 12 issue stands: release deep validation flags the OAC and COMAR adapters' shared container rows
    (`us-oh/regulation`; `us-md/regulation`, `.../title-07`, `.../title-07/subtitle-03`) as duplicate citations across
    scopes. No further OH or MD adapter scope was built in this batch; the controller must resolve the container-row
    overlap (adapter change or selector composition) before the OH and MD scopes can be published.
11. Extraction seconds are wall times of the `extract-official-documents` commands, timed with `/usr/bin/time -p` and
    start/finish timestamps.
12. GitNexus impact analysis could not be run (tools unavailable); no existing function was modified.

## Remaining

- Blocked: NY (JavaScript challenge; not re-probed this batch), WY (script-rendered Drive embed). Retry from another
  network or obtain the documents from the agencies; for WY also consider a Department of Health rule chapter on
  rules.wyo.gov as the adopted-rule alternative. Do not work around.
- Follow-on families not taken: WI Caretaker Supplement handbook (P-23131) and the DHS SSI fact sheets; MO Blind Pension
  Manual; OK CYSHCN is included in chapter 15 (note for encoders); the batch-1 and batch-2 items (SC OSS Services
  provider manual, LA Z appendices, OR OAR 461, UT R414-306-6, ME Ch. 332 appendices, VA 22VAC30-80).
- Controller: review the `document_class` choices in judgments 3-7 and the OK API judgment 3; resolve the OH/MD
  container-row overlap (judgment 10); `sign-ingest-manifest` for the five manifest scopes; immutable release selector
  for the batch-1, batch-2 and batch-3 scopes; `publish_corpus.py --dry-run`; then publication and activation.

## Closing status, all 51 jurisdictions and the federal row (queue `manifests/ssi-agent-queue.yaml`)

| Jurisdiction | Status | Resolution (scope or blocked URL) |
| --- | --- | --- |
| us | agent_ready | us/manual/2026-09-10-ssi-poms-si (POMS SI family) |
| us-ak | agent_ready | us-ak/manual/2026-09-10-ssi-state-supplement (batch 3) |
| us-al | done | us-al/regulation/2026-06-30-al-admin-code-660-2-4 (pointer) |
| us-ar | done | no optional supplement; us/manual/ssa/poms/si/01415.010 (batch 3) |
| us-az | done | no optional supplement; us/manual/ssa/poms/si/01415.010 (batch 3) |
| us-ca | done | us-ca/guidance/2026-06-27-ca-dor-ssi-ssp-newsletter |
| us-co | done | us-co/regulation/2026-06-19-co-oap-9-ccr-2503-5 (pointer) |
| us-ct | done | us-ct/policy/2026-07-02-ct-ssp-upm-and-standards |
| us-dc | done | us/guidance/2026-07-03-dc-ossp-ssa-poms |
| us-de | done | us-de/guidance/2026-07-03-de-ssi-state-supplement-poms |
| us-fl | agent_ready | us-fl/regulation/2026-09-10-ssi-state-supplement (batch 1) |
| us-ga | done | us-ga/manual/2026-06-24-ga-ssp |
| us-hi | agent_ready | federally administered; us/manual/2026-09-10-ssi-poms-si |
| us-ia | agent_ready | federally administered; us/manual/2026-09-10-ssi-poms-si |
| us-id | done | us-id/regulation/2026-07-04-id-aabd-rules (pointer) |
| us-il | done | us-il/manual/2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained (pointer) |
| us-in | done | us-in/manual/2026-07-04-in-ssp-sapn |
| us-ks | done | us-ks/guidance/2026-07-04-ks-sspp-guidance |
| us-ky | agent_ready | us-ky/regulation/2026-09-10-ssi-state-supplement (batch 2) |
| us-la | agent_ready | us-la/manual/2026-09-10-ssi-state-supplement (batch 2) |
| us-ma | agent_ready | us-ma/regulation/2026-09-10-ssi-state-supplement (batch 1) |
| us-md | agent_ready | us-md/regulation/2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapter-07 and -06 (batch 2, adapter) |
| us-me | agent_ready | us-me/regulation/2026-09-10-ssi-state-supplement (batch 2) |
| us-mi | agent_ready | federally administered; us/manual/2026-09-10-ssi-poms-si |
| us-mn | done | us-mn/manual/2026-05-27-mn-combined-manual-r2026-07-15-self-contained (pointer) |
| us-mo | agent_ready | us-mo/manual/2026-09-10-ssi-state-supplement (batch 3) |
| us-ms | done | no optional supplement; us/manual/ssa/poms/si/01415.010 (batch 3) |
| us-mt | agent_ready | federally administered; us/manual/2026-09-10-ssi-poms-si |
| us-nc | agent_ready | us-nc/manual/2026-09-10-ssi-state-supplement (batch 1) |
| us-nd | done | no optional supplement; us/manual/ssa/poms/si/01415.010 (batch 3) |
| us-ne | agent_ready | us-ne/regulation/2026-09-10-ssi-state-supplement (batch 2) |
| us-nh | agent_ready | us-nh/manual/2026-09-10-ssi-state-supplement (batch 2) |
| us-nj | agent_ready | federally administered; us/manual/2026-09-10-ssi-poms-si |
| us-nm | agent_ready | us-nm/regulation/2026-09-10-ssi-state-supplement (batch 2) |
| us-nv | agent_ready | federally administered; us/manual/2026-09-10-ssi-poms-si |
| us-ny | blocked_primary_source | https://otda.ny.gov/programs/ssp/ (JavaScript challenge; batches 1-2) |
| us-oh | agent_ready | us-oh/regulation/2026-09-10-ssi-state-supplement-agency-5122-chapter-5122-36 (batch 2, adapter) |
| us-ok | agent_ready | us-ok/regulation/2026-09-10-ssi-state-supplement (batch 3; API after the HTML front end blocked) |
| us-or | done | us-or/manual/2026-07-16-or-programs-eligibility-notebook (pointer) |
| us-pa | agent_ready | federally administered; us/manual/2026-09-10-ssi-poms-si |
| us-ri | agent_ready | federally administered; us/manual/2026-09-10-ssi-poms-si |
| us-sc | agent_ready | us-sc/manual/2026-09-10-ssi-state-supplement (batch 2) |
| us-sd | agent_ready | us-sd/regulation/2026-09-10-ssi-state-supplement (batch 3) |
| us-tn | done | no optional supplement; us/manual/ssa/poms/si/01415.010 (batch 3) |
| us-tx | done | us-tx/manual/2026-09-10-medicaid-state-eligibility-manual (pointer) |
| us-ut | done | us-ut/manual/2026-05-27-ut-manuals-r2026-07-15-self-contained (pointer) |
| us-va | agent_ready | us-va/manual/2026-09-10-ssi-state-supplement (batch 1) |
| us-vt | agent_ready | federally administered; us/manual/2026-09-10-ssi-poms-si |
| us-wa | done | us-wa/regulation/2026-07-01-388-474 (pointer) |
| us-wi | agent_ready | us-wi/manual/2026-09-10-ssi-state-supplement (batch 3) |
| us-wv | done | no optional supplement; us/manual/ssa/poms/si/01415.010 (batch 3) |
| us-wy | blocked_primary_source | https://ecom.wyo.gov/m1800-other-programs/m1804-state-supplemental-payments (script-rendered embed; batch 3) |

Tally: 52 rows; agent_ready 28 (18 state rows with a 2026-09-10 state-supplement scope: 16 manifest scopes across the
three batches and the OH and MD adapter scopes; the federal POMS SI row; 9 federally administered states resolved
inside the POMS family: HI, IA, MI, MT, NJ, NV, PA, RI, VT), done 22 (16 rows resolved by earlier runs or by pointer;
6 no-supplement states), blocked_primary_source 2 (NY, WY), needs_review 0.
