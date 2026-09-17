# SSI state-administered supplements, batch 1

Date: 2026-09-10
Program: SSI, optional state supplementary payments administered by the states (queue
`manifests/ssi-agent-queue.yaml`, the 29 `needs_review` rows left by
`docs/ingest-runs/2026-09-10-ssi-poms-si.md`).
Agent: two sessions. The first ran roughly 2026-09-10T19:40Z to 20:40Z (probes, generator, the four
extractions at 19:44Z, pointer and blocked rows) and was killed before committing. This continuation
picked up from the working tree: started_at 2026-09-10T20:43:38Z, finished_at 2026-09-10T20:54:36Z, wall time 0h 10m 58s
(verification, the Massachusetts re-extraction below, queue-row fields, this note, commit).
Impact analysis: not run; the GitNexus MCP tools were unavailable in both sessions. No function in
`src/axiom_corpus` was modified and no adapter was added. The only code is the new generator
`scripts/build_ssi_state_supplement_manifests.py` (builders for FL, MA, NC, VA; static pointer and
blocked rows; queue update), `ruff`-clean.

## Batch selection (reviewer judgment)

The 29 `needs_review` rows ranked by population (Census Vintage 2024 estimates; CO 5.96M ranks above
MN 5.79M): TX, FL, NY, IL, OH, NC, VA, WA, MA, CO | MN, SC, AL, LA, KY, OR, OK, UT, NE, NM, ID, NH, ME,
MD, MO, WI, SD, AK, WY. The first ten were attempted; when a publisher blocked on its first probe the
next state in population order replaced it (at most six replacements allowed). NY blocked and was
replaced by MN; OH blocked and was replaced by SC, which itself blocked and was replaced by AL.
Probed: 13 (TX, FL, NY, IL, OH, NC, VA, WA, MA, CO, MN, SC, AL). Attempted: 10 (TX, FL, IL, NC, VA,
WA, MA, CO, MN, AL). Extracted: 4 (FL, MA, NC, VA). Done by pointer: 6 (TX, IL, WA, CO, MN, AL).
Blocked: 3 (NY, OH, SC).

Family per state: the state agency's own governing document for the optional supplement (eligibility,
payment standards, living arrangements), confirmed from the publisher's own index page: the adopted rule
where the state publishes the rule itself as the program's governing text (FL, MA), the agency program
manual where the manual is the governing text (NC, VA). Change notices, administrative letters,
transmittals, forms and provider documents on the same index are separate families, inventoried and not
taken. Where the state's supplement rules already live in a scope in the corpus, the row is `done`
with a pointer to that scope and nothing is re-fetched. No compiled list (SSA's "State Assistance
Programs for SSI Recipients", PolicyEngine files) was used as a source; the lead list was not consulted.

Scope: version `2026-09-10-ssi-state-supplement`; `document_class` by the document's nature
(`regulation` for FL and MA, `manual` for NC and VA) with each jurisdiction's existing citation
conventions; `source_as_of` 2026-09-10; `expression_date` is the date the publisher prints where
there is one (FL per-rule effective date, NC revision date) and otherwise the fetch date (MA, VA).

Extraction: `uv run axiom-corpus-ingest extract-official-documents`, no new adapter, artifacts under
the main checkout's `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus` (this worktree is
sparse). FL rule text is the publisher's `.doc` download per rule (`download_url`); MA is one PDF via
`download_url` segmented into `labeled_sections`; NC and VA are PDFs at page granularity with
`ocr: true`. TLS verification was never disabled and no publisher needed a certificate bundle (no
`data/certs` change). One browser-impersonation attempt (curl-cffi chrome120, 20 s timeout) was made
only to characterise the three blocked publishers; nothing was fetched that way and no manifest uses
`browser_impersonation`. Coverage is `complete: true` with 0 missing, 0 extra and 0 duplicate
citation paths for all four scopes; `citation_path` uniqueness within each provisions JSONL and
absence from every other provisions JSONL under `data/corpus/provisions/<jurisdiction>/` (all document
classes, including today's Medicaid and CHIP scopes) were verified independently with a counter script
in this continuation (0 in-file duplicates, 0 cross-scope collisions). The regenerated manifests were
also checked against the inventories (same `source_url` sets; every manifest `citation_path` is a
root row).

## Per-jurisdiction results

| Jurisdiction | Program | Index | document_class | Documents taken | Provisions | Extraction seconds |
| --- | --- | --- | --- | ---: | ---: | ---: |
| us-fl | Optional State Supplementation (OSS) | FAC chapter 65A-2 on flrules.org | regulation | 8 | 16 | 5 (19:44:04-19:44:09Z) |
| us-ma | State Supplement Program (SSP) | 106 CMR law library, mass.gov | regulation | 1 | 25 | 1 (19:44:25Z); re-extracted 20:51:38Z, 1.5 s |
| us-nc | State/County Special Assistance (SA, SA In-Home) | NCDHHS Policies and Manuals, Special Assistance | manual | 2 | 418 | 2 (19:44:29-19:44:31Z) |
| us-va | Auxiliary Grant (AG) | DARS Auxiliary Grant, for providers | manual | 12 | 574 | 5 (19:44:35-19:44:40Z) |

Total: 23 documents, 1,033 provisions across 4 scopes. Extraction seconds for the first session's runs
are lower bounds recovered from artifact mtimes (first source file written to coverage written; the
first download itself is not included) because that session's log was lost; the MA re-extraction was
timed directly. Index documents found versus taken are in the queue rows (`index_document_count`,
`taken_count`, `index_families`): found 158 across the four extracted indexes, taken 23.

### Index inventories (every document family on the publisher index; taken counts)

**us-fl** — https://flrules.org/gateway/ChapterHome.asp?Chapter=65A-2
FAC chapter 65A-2 "Optional State Supplementation" (DCF rule, published by the Department of State's
Florida Administrative Code site): 65A-2.022 Rights and Responsibilities (eff. 2021-10-26), .023
Application and Determination of Eligibility (2021-10-26), .024 Determination of Continued Eligibility
(2001-12-16), .031 Advance Notice (2001-12-16), .032 OSS Eligibility Criteria (2021-10-26), .033 OSS
Coverage Groups (2002-05-14), .035 Income Calculation (2001-12-16), .036 OSS Base Provider Rates and
Program Standards (2025-06-24): 8 found / 8 taken. The RuleNo page is the publisher's rule record;
the rule text is its `.doc` (readFile.asp) taken as `download_url`. Citation paths
`us-fl/regulation/fac/65a-2/022` … `/036` (the FAC 65A-1 SNAP scope's convention); 16 rows (each
rule plus one text block). DCF's own site has no OSS page (guessed paths 404) and the ESS Program
Policy Manual scope carries no OSS text.

**us-ma** — https://www.mass.gov/law-library/106-cmr
DTA regulations listed: SSP 327.000 Eligibility Requirements for State Supplement Program: 1 found / 1
taken; Fair hearing rules 343: 1 / 0; SNAP 360-367: 8 / 0; TCAP/TAFDC/EAEDC 701-708: 8 / 0. 18 found,
1 taken. The regulation page
(`/regulations/106-CMR-32700-eligibility-requirements-for-state-supplement-program-ssp`) carries only
the official PDF, taken as `download_url` (6 pages, PDF modification date 2019-05-06, "Mass. Register
#1390 5/3/19" printed in 327.110). Sections 327.010, .100, .110, .120, .130, .140, .150, .160, .200,
.210, .220, .230, .300, .310, .320, .330, .340, .350, .360, .370, .380, .390, .400, .410 (24; the
page-1 table of contents misprints 327.160 as 322.160). Citation paths
`us-ma/regulation/106-cmr/327` and `us-ma/regulation/106-cmr/327/327.010` … `/327.410` (the 106 CMR
convention of the DTA regulation scopes; no other us-ma scope carries 106 CMR 327). mass.gov answered
HTTP 200 to a paced plain client (3 s pauses) in both sessions; the earlier federal run's 403 was not
seen. Re-extraction in this continuation: the first session's manifest used `start_page: 2` to skip
the page-1 table of contents, which also dropped 327.010 Authority, 327.100 Overview and 327.110
Definitions, whose text begins on page 1 after the TOC (the scope had 22 rows and coverage was
"complete" only because those sections were never in the source list). The manifest now uses
`start_page: 1` with `start_after_pattern` anchored on the last TOC line (`327.410: Recovery of
Overpayments`), both existing extractor options; smoke-run into a scratch base (25 rows, no
duplicates), then re-extracted into the corpus base: 25 rows, complete.

**us-nc** — https://policies.ncdhhs.gov/divisional-n-z/social-services/special-assistance/special-assistance/
Program manuals: State/County Special Assistance Manual (Rev. June 2026, 368 pages) and Special
Assistance In-Home Program Manual (Rev. June 2026, 48 pages): 2 found / 2 taken. Change notices
(CHANGE NO. …, EFS-SA-CN, SAIH Case Management Manual changes): 50 / 0; administrative letters: 33 / 0;
forms and notices: 23 / 0; EIS system documents: 3 / 0. 111 found, 2 taken. Each document page carries
only the PDF (`wp-content/uploads/...Rev-June-2026.pdf`), taken as `download_url`. Citation paths
`us-nc/manual/dss/special-assistance/manual` (+ `/page-N`) and `.../in-home-manual` (+ `/page-N`);
418 rows. `expression_date` 2026-06-01, the printed revision date.

**us-va** — https://dars.virginia.gov/benefits/auxiliary-grant/for-providers/
Auxiliary Grant Program Manual chapters A Introduction, B Application Processing, C Non-Financial
Requirements, D SSI Recipients' Eligibility, E Non SSI Resource Eligibility, F Non SSI Conditional
Benefits, G Non SSI Resource Transfers, H Non SSI Income Exclusions, I Non SSI Income Sources, J Grant
Computation & Issuance, K Supportive Housing, L Administrative Issues: 12 found / 12 taken (page counts
14, 50, 55, 16, 157, 27, 45, 35, 116, 14, 14, 19). Manual transmittal DARS-APSD-18: 1 / 0. Provider
manuals, agreements, certification and forms: 8 / 0. 21 found, 12 taken. The chapters are served by
the agency document repository www.dsa.virginia.gov (the index links www.vadsa.org, which redirects
there; recorded as `hosting_authority`); `source_url` is the canonical repository URL, the index
link is kept as `index_link_url`. The adopted rule 22VAC30-80 Auxiliary Grants Program on Virginia LIS
(https://law.lis.virginia.gov/admincode/title22/agency30/chapter80/, 12 sections incl. FORMS) is the
alternative family, inventoried on its own index and not taken. Citation paths
`us-va/manual/dars/auxiliary-grant/chapter-a` … `chapter-l` (+ `/page-N`); 574 rows.
`expression_date` fetch date; each chapter prints its own revision month on the cover.

### Already in corpus (done, pointers; nothing re-fetched)

- **us-tx** — Texas supplements only institutionalized SSI recipients: HHSC MEPD Handbook H-6000
  "Co-Payment for SSI Cases" (Revision 26-1, effective 2026-03-01: HHSC adds $45 to the $30 reduced SSI
  payment standard so the recipient keeps a $75 personal needs allowance). H-6000, Appendix VIII and
  Appendix XXXI are in today's Medicaid eligibility-manual scope (`us-tx/manual/hhsc/medicaid/mepd-h-6000`,
  `mepd-appendix-viii`, `mepd-appendix-xxxi`; manifest on branch `discovery/ingest-medicaid`, version
  `2026-09-10-medicaid-state-eligibility-manual`). Index fhb.hhs.texas.gov MEPD handbook, HTTP 200 to a
  plain client (the hhs.texas.gov alias that answered 403 in the federal run redirects there).
- **us-il** — AABD Cash is governed by the IDHS Cash, SNAP and Medical Policy Manual / WAG, in the corpus
  in full (`us-il/manual`, version `2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained`,
  12,450 rows; AABD sections PM I-02-02, PM I-03-03, PM/WAG 11-01-00, 11-02-03, WAG 03-03-02, WAG 25-03-03,
  PM 22-05-01; 493 rows mention AABD).
- **us-wa** — SSI State Supplemental Payment: WAC chapter 388-474 (388-474-0001, -0010, -0012, -0020) in
  the corpus in full as `us-wa/regulation/388/388-474/...` (version `2026-07-01-388-474`, adapter scope,
  no manifest, selected in `manifests/releases/us-rulespec-2026-07-17.json`). The DSHS EA-Z manual scope
  carries no SSP page.
- **us-co** — Old Age Pension and Aid to the Needy Disabled - State Only under Adult Financial rule 9 CCR
  2503-5 (3.500-3.587 incl. 3.530 OAP and 3.540 AND-SO), in the corpus in full as
  `us-co/regulation/9-ccr-2503-5/...` (version `2026-06-19-co-oap-9-ccr-2503-5`, 92 rows, adapter scope).
- **us-mn** (replacement 1) — Minnesota Supplemental Aid: DHS Combined Manual (`us-mn/manual`, version
  `2026-05-27-mn-combined-manual-r2026-07-15-self-contained`, 1,354 rows; 523 pages mention MSA incl.
  0020.21 MSA Assistance Standards) plus the MSA revised sections issued 01/2026
  (`2026-06-27-mn-dhs-msa-revised-sections-2026-01`). The corpus copies came from dhs.state.mn.us; mn.gov/dhs
  answers a Radware challenge to a plain client.
- **us-al** (replacement 3) — Alabama Administrative Code chapter 660-2-4 "Optional Supplementation"
  (DHR), in the corpus as `us-al/regulation` version `2026-06-30-al-admin-code-660-2-4` (62 rows, page
  granularity). dhr.alabama.gov HTTP 200 to a plain client; medicaid.alabama.gov no TCP answer.

### Blocked publishers (no workaround attempted)

- **us-ny** — https://otda.ny.gov/programs/ssp/ (OTDA State Supplement Program). Plain client: TCP
  connection reset by peer, site root too. curl-cffi chrome120 impersonation (20 s timeout): HTTP 200 but
  a 5,615-byte JavaScript challenge ("Please enable JavaScript to view the page content. Your support ID
  is ...") with no page content. No index inventory possible. SSA's regional description stays in the
  federal family (`us/manual/ssa/poms/si/ny01415.026`).
- **us-oh** — https://codes.ohio.gov/ohio-administrative-code/chapter-5122-36 (Residential State
  Supplement, OAC 5122-36, Department of Behavioral Health, formerly OhioMHAS). codes.ohio.gov: connect
  timeout at 20 s for the plain client and for chrome120 impersonation (as in today's Medicaid batches).
  mha.ohio.gov redirects to dbh.ohio.gov, which answers HTTP 404 (5,264-byte error shell) to every plain
  request and, impersonated, HTTP 200 generic "Community" pages without the RSS program text or rule
  documents; its Rules & Regulations page carries no 5122-36 links. No index inventory possible.
- **us-sc** (replacement 2) — https://www.scdhhs.gov/resources/mppm (Optional State Supplementation,
  SCDHHS Medicaid Policy and Procedures Manual). HTTP 403 (919-byte body) to the plain client for the
  site root and the MPPM page, and HTTP 403 (919 bytes) to chrome120 impersonation. No index inventory
  possible.

Queue rows for all thirteen probed states carry `index_url`, `index_document_count`, `taken_count`
and `index_families`: extracted rows with the counts above; pointer rows with the pointed-to scope's
index URL, `index_document_count: null` (the existing scope's index was not re-inventoried),
`taken_count: 0` and an `index_families` string naming the scope; blocked rows with the probed URL as
`index_url` (the Medicaid queue convention), `index_document_count: null`, `taken_count: 0` and
`index_families` "no index inventory possible". `status_counts`: agent_ready 14 (10 + FL, MA, NC,
VA), needs_review 16 (29 - 13), done 13 (7 + 6 pointers), blocked_primary_source 3; 46 rows, reconciled
against the rows by script. Top-level `queue_status` stays `in_progress`.

## Artifacts (unsigned, uncommitted, awaiting controller)

- `data/corpus/sources/us-xx/<class>/2026-09-10-ssi-state-supplement/official-documents/*`
- `data/corpus/inventory/us-xx/<class>/2026-09-10-ssi-state-supplement.json`
- `data/corpus/provisions/us-xx/<class>/2026-09-10-ssi-state-supplement.jsonl`
- `data/corpus/coverage/us-xx/<class>/2026-09-10-ssi-state-supplement.json`

for us-fl/regulation, us-ma/regulation, us-nc/manual, us-va/manual under
`/Users/pavelmakarchuk/axiom-corpus/data/corpus` (main checkout).

Rebuild (the generator caches index pages under `~/.axiom/ssi-state-supplement-cache`; the extractor
re-fetches every document):

```bash
uv run python scripts/build_ssi_state_supplement_manifests.py --print-index
for s in fl ma nc va; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-ssi-state-supplement \
    --manifest manifests/us-$s-ssi-state-supplement.yaml
done
```

Lint: `uv run ruff check scripts/build_ssi_state_supplement_manifests.py` clean.

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped (39 s), run before and after the MA change with the same result. The
ten failures are the known sparse-worktree data-dependent tests (`test_be_rulespec_2026_08_23_promotion`,
`test_build_ny_tanf_compatibility_scope` x2, `test_rulespec_be_source_promotion`,
`test_us_ak/ct/mi/mt/nd/ny_snap_manual`); none touches the SSI manifests or the generator. No adapter
was added, so no new tests.

## Reviewer judgments (all of them)

1. Batch = the ten largest `needs_review` states by Census Vintage 2024 population (CO ranked above
   MN), replacements in the same order only after a publisher blocked on its first probe: NY -> MN,
   OH -> SC -> AL. Thirteen probed, ten attempted, within the sixteen-probe cap.
2. A state whose supplement rules already live in a corpus scope is `done` by pointer and counts as
   attempted (TX, IL, WA, CO, MN, AL); nothing was re-fetched for them and no new scope was cut.
3. FL: `document_class` `regulation`. The governing text is DCF's adopted rule FAC 65A-2, published by
   the Department of State (flrules.org); DCF has no OSS manual page. Citation `us-fl/regulation/fac/65a-2/<section>`
   follows the existing FAC 65A-1 scope. The rule `.doc` is taken as `download_url`; `expression_date`
   is each rule's printed effective date.
4. MA: `document_class` `regulation`. 106 CMR 327.000 is DTA's adopted regulation and the program's
   only governing text; citation `us-ma/regulation/106-cmr/327/<section>` follows the DTA 106 CMR
   scopes. Section granularity via `labeled_sections`; the other 17 chapters on the 106 CMR index are not
   taken; `expression_date` = fetch date (the page prints no effective date).
5. MA re-extraction (this continuation): `start_page: 2` had silently dropped 327.010-327.110; replaced
   by `start_after_pattern` on the last TOC line, smoke-run in a scratch base, then re-extracted (22 ->
   25 rows). Recorded here rather than left for a later pass because coverage could not detect it.
6. NC: `document_class` `manual`. The two DSS program manuals are the governing text of State/County
   Special Assistance; change notices, administrative letters, forms and EIS documents on the same index are
   separate families, not taken. Page granularity; `expression_date` 2026-06-01, the printed revision date.
7. VA: `document_class` `manual`. The DARS Auxiliary Grant Program Manual (12 chapters) is taken as
   the agency's governing document; the adopted rule 22VAC30-80 on Virginia LIS is inventoried as the
   alternative family and not taken (a later pass may add it as `us-va/regulation`). The chapters are
   fetched from the agency repository host www.dsa.virginia.gov that the DARS index links (via
   www.vadsa.org), recorded as `hosting_authority`; transmittal and provider documents not taken;
   `expression_date` = fetch date.
8. TX pointer: `document_class` `manual` (MEPD handbook H-6000 in the Medicaid scope). Texas's
   supplement is limited to the $45 institutional add-on; no separate document exists on the HHSC index.
9. IL pointer: `manual` (IDHS PM/WAG scope carries AABD Cash). MN pointer: `manual` (Combined
   Manual + MSA revised sections). WA pointer: `regulation` (WAC 388-474). CO pointer: `regulation`
   (9 CCR 2503-5). AL pointer: `regulation` (Ala. Admin. Code 660-2-4).
10. NY, OH, SC recorded `blocked_primary_source` with the exact failures after one plain request and
    one chrome120 impersonation attempt each; no proxies, mirrors or third-party copies. OH's blocked
    publisher is the same codes.ohio.gov host blocked in today's Medicaid batches.
11. Queue-row fields for pointer and blocked rows (this continuation): pointer rows get `taken_count: 0`
    and an `index_families` pointer string with `index_document_count: null`; blocked rows carry the
    probed URL as `index_url` and an `index_families` placeholder, following the Medicaid queue.
12. Extraction seconds for the first session are recovered from artifact mtimes (lower bounds) because
    that session's console output was lost with the session.
13. TLS verification was never disabled; no certificate bundle was needed; no PolicyEngine file or
    compiled list was read; no secrets in any file (manifests carry only public publisher file ids).
14. No adapter and no library change; GitNexus impact analysis could not be run (tools unavailable).

## Remaining

- `needs_review` rows still open (16, population order): LA, KY, OR, OK, UT, NE, NM, ID, NH, ME, MD,
  MO, WI, SD, AK, WY (WI's index https://www.dhs.wisconsin.gov/ssi/index.htm was confirmed HTTP 200 in
  the federal run). Batch 2 = the next ten by population with the same rule.
- Blocked (NY, OH, SC): retry from another network or obtain an official export; do not work around.
- Follow-on families not taken: NC change notices and administrative letters; VA 22VAC30-80 (as a
  `regulation` scope) and transmittal DARS-APSD-18; MA 106 CMR 343 fair-hearing rules (SNAP and TAFDC
  chapters belong to other programs); FL DCF program materials if DCF publishes any.
- Controller: review the `document_class` choices in judgments 3-9, `sign-ingest-manifest` for the
  four scopes, immutable release selector, `publish_corpus.py --dry-run`, then publication and activation.
