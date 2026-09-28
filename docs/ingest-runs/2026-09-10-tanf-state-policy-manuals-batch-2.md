# TANF state policy manuals, batch 2

Date: 2026-09-10
Program: TANF (board Year 1 list; `manifests/tanf-agent-queue.yaml`)
Branch: `discovery/ingest-tanf` (worktree, sparse checkout without `data/corpus`; artifacts written to the shared corpus root of the main checkout, `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`)

started_at: 2026-09-10T20:33:00+0200 (first command; the shell timer started 20:34:44)
finished_at: 2026-09-10T21:33:21+0200 (commit)
agent wall time: about 60 min (20:33 to 21:33; NH extraction alone 941 s)

## Batch rule (reviewer judgment 1)

Batch 1's rule is kept: queue rows in queue order; a state whose current TANF cash assistance policy
manual, or the adopted rule the state itself publishes as its primary policy document, is already in
the corpus is `done` and does not count. The work order for batch 2 was: the four rows batch 1 deferred
(PA, SC, SD, VA), then `needs_review` rows with a state-published manual or rule (none: the only other
`needs_review` row was the federal row), then the next queue-order states until ten jurisdictions were
attempted. The queue had no further state rows, so the batch was extended with states that are not on
the policyengine-us lead list, in alphabetical order, skipping states whose TANF policy document is
already in the corpus. Those skipped states were added to the queue as `done` rows so the queue records
why they were not attempted: AK (7 AAC 45 + ATAP standards), AR (TEA), CT (UPM), IA (441 IAC), MA
(106 CMR 701-707), MD (COMAR 07.03.03 + guidance), MI (Bridges Eligibility Manual, combined), MN
(Combined Manual), NJ (N.J.A.C. 10:90, page-level recovery scope only), UT (R986), WV (Income
Maintenance Manual, combined), WY (SNAP and POWER manual, combined). Combined manuals count, as in
batch 1.

Batch 2 = **PA, SC, SD, VA, ID, KY, LA, NE, NH, NM**. Blocked publishers count as attempted; NM was
attempted but is `needs_review` (see below), not blocked.

## Results

| jurisdiction | status | document_class | documents taken / on index | provisions | elapsed s |
|---|---|---|---|---|---|
| us-pa | extracted | manual | 365 / 365 topic pages (543 TOC entries) | 1283 | 61 |
| us-sc | blocked_primary_source | manual | 0 / unknown | 0 | - |
| us-sd | extracted | regulation | 153 / 181 API records | 306 | 27 |
| us-va | extracted | manual | 10 / 12 | 554 | 7 |
| us-id | extracted | regulation | 1 / 371 (21 in IDAPA 16) | 19 | 3 |
| us-ky | blocked_primary_source | manual | 0 / unknown | 0 | - |
| us-la | extracted | manual | 292 / 3809 listing (781 in the EI manual) | 1346 | 200 |
| us-ne | blocked_primary_source | regulation | 0 / unknown | 0 | - |
| us-nh | extracted | manual | 715 / 715 | 1430 | 941 |
| us-nm | needs_review (attempted, not extracted) | regulation | 0 / unknown | 0 | - |

Attempted 10, extracted 6, blocked 3 (SC, KY, NE), needs_review 1 (NM). Newly marked done without
extraction: 12 (AK, AR, CT, IA, MA, MD, MI, MN, NJ, UT, WV, WY). NY and OR retried once each, still
blocked (below).

Provision total: 4,938 rows across 6 scopes, every scope `complete: true`, 0 missing, 0 extra,
0 duplicate citation paths. Uniqueness was re-checked directly on each provisions JSONL, and every new
`citation_path` was checked against every other provisions JSONL under
`data/corpus/provisions/<jurisdiction>/` (0 cross-scope collisions in all six). Version for every scope:
`2026-09-10-tanf-state-policy-manual`; document_class `manual` for agency manuals (PA, VA, LA, NH) and
`regulation` where the state's primary policy document is an adopted rule it publishes itself (SD ARSD
67:10, ID IDAPA 16.03.08).

Artifacts (unsigned, uncommitted, awaiting controller), per scope:

- `data/corpus/sources/<jur>/<class>/2026-09-10-tanf-state-policy-manual/official-documents/...`
- `data/corpus/inventory/<jur>/<class>/2026-09-10-tanf-state-policy-manual.json`
- `data/corpus/provisions/<jur>/<class>/2026-09-10-tanf-state-policy-manual.jsonl`
- `data/corpus/coverage/<jur>/<class>/2026-09-10-tanf-state-policy-manual.json`

## Index inventories

**Pennsylvania (us-pa, manual).** Index: OIM Cash Assistance Handbook,
http://services.dpw.state.pa.us/oimpolicymanuals/cash/index.htm (Adobe RoboHelp; TOC data in
`whxdata/toc.js` and `toc*.js`, the same layout as the ingested SNAP handbook). One family: 543 TOC
entries resolving to 365 topic pages (chapters 100 Operations Memoranda/Policy Clarifications, 103
through 192 with their appendices; the other 178 entries are in-page anchors of those pages). Taken:
all 365. Not on the TOC and not taken: glossary pop-ups under `_Popups/`. Citation path
`us-pa/manual/dhs/cash/<dir>-<file>` (e.g. `.../160-income-deductions-160-2-tanf-earned-income-deductions`),
mirroring the SNAP handbook's `us-pa/manual/dhs/snap/...`; expression_date = each page's HTTP
Last-Modified (352 pages 2026-08-27, 8 pages without the header fall back to 2026-09-10, 5 older);
`html_drop_selectors` `.topic-header`, `.topic-header-shadow`. One file name contains an en dash
(`113_1_General_Policy_–_TANF.htm`); the TOC JS only escapes quotes, so the generator no longer
unicode-unescapes it (first run failed on that URL; fixed and rerun).

**South Carolina (us-sc) - blocked.** SC DSS TANF Policy Manual Volume 65,
https://dss.sc.gov/media/ojqddxsk/tanf-policy-manual-volume-65.pdf (manuals page
https://dss.sc.gov/about/data-and-resources/manuals/, the host of the ingested SNAP manual volume 69).
dss.sc.gov resolves (167.7.60.200) but every TCP connection to :443 and :80 timed out - curl
"Connection timed out after 12002 milliseconds", Python requests ConnectTimeout, curl-cffi chrome
impersonation "Connection timed out after 30001 milliseconds" - at 20:35, 20:39 and 20:52 +02:00. No
index could be inventoried, no workaround. Retry from another network (the SNAP manual was fetched from
this host in May).

**South Dakota (us-sd, regulation).** Index: Legislative Research Council administrative rules,
https://sdlegislature.gov/Rules/Administrative/67:10 (a Vue app; the data comes from
`https://sdlegislature.gov/api/Rules/<rule number>`, one JSON per rule with an `Html` body and a
`Next` pointer). Family: walking `Next` from 67:10 until 67:11 returns 181 records: 1 article (type B,
Temporary Assistance to Needy Families), 10 chapters (type C, 67:10:01 General provisions through
67:10:10 Notice requirements) and 170 sections (type D). Taken: the 153 sections whose catchline is
not Repealed/Transferred, one document each (`source_url` the human rule page, `download_url` the API
JSON, `json_html_field: Html`). Not taken: the article and chapter records (tables of contents) and 17
repealed/transferred sections (67:10:01:13, 67:10:03:22, 67:10:04:18, 67:10:04:19, 67:10:05:04,
67:10:05:06, 67:10:05:10, 67:10:05:15, 67:10:05:16, 67:10:06:04, 67:10:06:09, 67:10:06:10,
67:10:06:14, 67:10:06:15, 67:10:06:17, 67:10:06:20, 67:10:10:05). Citation path
`us-sd/regulation/arsd/67/10/<chapter>/<section>`; each rule yields a root row and one block
(`.../block-1`). expression_date = 2026-09-10 (the API carries no date; each rule's source note is in
its text). The DSS TANF pages link to these rules; South Dakota has no separate DSS TANF manual (the
DSS SNAP manual is a different program).

**Virginia (us-va, manual).** Index: VDSS TANF Manual page, https://www.dss.virginia.gov/relief/tanf/tanf-manual/.
Family: 12 PDFs - Contents (table of contents), Full Manual (`Combined-Full-Manual-07-24_1.pdf`) and
10 chapter files (Chapter 100 General Information through Chapter 1000 VIEW Employment Services). Taken:
the 10 chapter files, page-level (`us-va/manual/dss/tanf/chapter-300/page-N`), like the VA SNAP manual
scope; the Full Manual duplicates the chapters and the Contents file is a TOC. All files carry HTTP
Last-Modified 2026-04-21 (used as expression_date); each page's running head carries its own transmittal
date (e.g. 10/23). Browser impersonation on (plain fetch tried first).

**Idaho (us-id, regulation).** Index: Office of the Administrative Rules Coordinator current rules,
https://adminrules.idaho.gov/current-rules/ (WordPress; the list is served by
`POST /wp-json/dfm-document-display/fetch-documents` with `{"azurePayload": {"documentType":
"currentRules"}}` and the page's `X-WP-Nonce`). Family: 371 current rule chapters, 21 under IDAPA 16
(Health and Welfare). Taken: IDAPA 16.03.08 Federal Welfare Programs (the TAFI rule; 6 pages, HTTP
Last-Modified 2026-07-07, effective marks (7-1-26) so expression_date 2026-07-01), `numbered_sections`
like the ingested 16.03.05 AABD scope; citation path `us-id/regulation/idapa/16/03/08/<section>`. Reserved
ranges (`002. – 099. (RESERVED)` etc.) and the part labels `TANF PROGRAM`/`LIHEAP` are dropped: left in,
the numbered-sections reader treated the all-caps heading of section 111 as a continuation of the
reserved heading (first run: 22 rows with 111 folded into 105-110; rerun: 19 rows, 18 sections plus root).
Not taken: 16.03.04 and 16.03.05 (already in the corpus) and the other title 16 chapters. IDHW's TAFI
program page (`/services-programs/financial-assistance/about-tafi`) links no manual; the adopted rule is
the state's published policy document. adminrules.idaho.gov rejects curl-cffi's chrome TLS profile
("unable to get local issuer certificate") but verifies with plain requests/certifi, so the generator
uses plain requests for this host and the manifest has no impersonation flag.

**Kentucky (us-ky) - blocked.** CHFS DCBS Operation Manual index (Volume IIIA K-TAP),
https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/opmanual.aspx. Plain requests and curl-cffi chrome
impersonation both get HTTP 403 text/html 1,484 bytes "Service unavailable - The request is blocked."
with an `x-azure-ref` header (Azure Front Door WAF). No index could be inventoried, no workaround.

**Louisiana (us-la, manual).** DCFS publishes its policies through its PowerDMS public document
directory, https://public.powerdms.com/LADCFS/tree (linked from dcfs.louisiana.gov as "Policies
Listing"; listing JSON at `https://public.powerdms.com/LADCFS/documents`, each document served as a PDF
at its `publicUrl`). Listing: 3,809 public documents; the Economic Independence (EI) folder holds 1,248
in 7 families: 4. Economic Independence manual 781, 7. Administrative Procedures Manual 184, 16. Fraud
and Recovery Manual 135, 14. Safety Policy Manual 102, 3. EBT Handbook 36, 2. SIEVS Manual 9, Louisiana
TANF Work Verification Plan 1. The EI manual (combined FITAP/KCSP/SNAP/STEP) by part: Y forms and
instructions 435, C case processing 98, B eligibility factors 87, O DSNAP 35, F case maintenance 31, P
STEP 29, K LaCAP 19, E special households 18, S simplified reporting 15, J charts 7, M KCSP 4, G
nondiscrimination 2, N child abuse reporting 1. Taken: the 292 policy documents in parts B, C, E, F,
G, J, M, N, P, S, page-level (`us-la/manual/dcfs/ei/<document-name slug>/page-N`, e.g.
`.../b-1730-fitap-60-month-time-limit`). Not taken: Y (forms), O and K (SNAP-only programs) and the other
EI families. PowerDMS sends no Last-Modified (expression_date 2026-09-10); the effective date is printed
in each document's header block. Browser impersonation on.

**Nebraska (us-ne) - blocked.** ADC policy is 468 NAC, published by the Secretary of State at
https://rules.nebraska.gov/ (www.nebraska.gov/rules-and-regs redirects there); DHHS program pages
(dhhs.ne.gov) time out on TCP connect. rules.nebraska.gov serves only its leaf certificate (issuer
DigiCert Global G2 TLS RSA SHA256 2020 CA1; openssl "unable to verify the first certificate"), so the
public intermediate was fetched from the leaf's AIA URL
(`http://cacerts.digicert.com/DigiCertGlobalG2TLSRSASHA2562020CA1-1.crt`) and stored as
`data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem` (SHA-256 fingerprint
C8:02:5F:9F:C6:5F:DF:C9:5B:3C:A8:CC:78:67:B9:A5:87:B5:27:79:73:95:79:17:46:3F:C8:13:D0:B6:25:A9);
verification was never disabled. With `REQUESTS_CA_BUNDLE` = certifi + that file the host answers plain
requests and chrome impersonation with HTTP 403 (Microsoft-Azure-Application-Gateway/v2, "403 - Access
Denied / Forbidden ... You are accessing this site from an IP Address out[side the allowed range]").
No index could be inventoried, no workaround. Retry from a US network.

**New Hampshire (us-nh, manual).** Index: DHHS Family Assistance Manual,
https://www.dhhs.nh.gov/fam_htm/newfam.htm (linked from the FANF page as "Family Assistance Policy
Manual"; RoboHelp WebHelp 5.50, TOC in `whgdata/whlstt0.htm` ... `whlstt99.htm`). Family: 100 TOC list
files with 4,019 entries resolving to 715 topic pages under `fam_htm/html/` (Introduction, 100 Case
Processing through 900 NH Child Care Scholarship, Glossary). Taken: all 715
(`us-nh/manual/dhhs/fam/<file slug>`, e.g. `.../109-01-filing-an-application-fam`). Not taken: the
linked SR (supervisory release) letters (`sr_htm/`) and the "Previous Policy" archive pages
(`famar_htm/`), separate families. expression_date = HTTP Last-Modified (2026-08-29 for every page,
the site's last republish). `html_drop_selectors` `#header`, `.no-print`, `.navBtnCusStyle`. The FAM is a
combined manual (FANF cash assistance, medical assistance categories, child care scholarship).
dhhs.nh.gov answers plain clients with an Akamai "Access Denied" 403, so browser impersonation is on
(the first extraction attempt without it failed on the first document; the manifest was patched in place
with the same `request` block the updated builder now emits, then rerun).

**New Mexico (us-nm) - attempted, needs_review.** NMAC 8.102 Cash Assistance Programs (adopted rule)
is published by the Commission of Public Records / State Records Center and Archives. The part files are
served by the publisher (`https://www.srca.nm.gov/parts/title08/08.102.0100.html` and `.pdf` answer
200), but the publisher's chapter index at
https://www.srca.nm.gov/nmac-home/nmac-titles/title-8-social-services/ is a RealFile folder widget
(`rts-realfile-folder-search` plugin, `a.rf-folder data-folder-id b5ca2d14-...`) whose listing is
loaded from the vendor's API (rf-sb-prod.rtssaas.com / AWS Lambda, with an embedded auth token); the
static page lists only the reserved part ranges. No mirror and no probe-by-number was used. Reviewer
decision: accept the vendor folder listing as the publisher's index (then inventory the non-reserved
parts 100-640 and extract the HTML parts) or find an HCA/ISD-published parts index. `index_document_count`
is null on the row.

## Retries of the batch-1 blocked rows

Both retried at 2026-09-10T20:35-20:38+02:00 with 15 s timeouts, about 35 s in total; row notes carry
"Retried ..., same failure".

- **New York**: plain `curl -I https://otda.ny.gov/programs/temporary-assistance/TASB.pdf` - "Recv failure:
  Connection reset by peer"; curl-cffi chrome and firefox GET - HTTP 200 text/html 5.5 KB JavaScript
  challenge page instead of the PDF. Same failure as batch 1.
- **Oregon**: plain curl to https://ch461rules.odhs.oregon.gov/ - "Resolving timed out after 15003
  milliseconds"; curl-cffi chrome GET of ch461rules.odhs.oregon.gov and secure.sos.state.or.us - "Could
  not resolve host"; `dig` - "connection timed out; no servers could be reached". Same failure as batch 1
  (name resolution from this network).

## Code changes

- `scripts/build_tanf_state_policy_manual_manifests.py` (existing generator, extended rather than a new
  script): builders `build_pa`, `build_va`, `build_sd`, `build_nh`, `build_la`, `build_id`; helpers `slug`,
  `last_modified`; `BATCH_2`/`BATCH_LABEL` (queue notes now say "Batch 2."), `NEW_ROWS` (queue rows for the
  states not on the lead list), 12 new `DONE` entries, `BLOCKED` entries for SC, KY, NE plus a
  `document_class` per blocked row and the NY/OR retry sentences, `NEEDS_REVIEW` for NM. The batch-1
  post-step that reset PA/SC/SD/VA to `needs_review` was removed. `--only` rebuilds a subset; a full run
  refetches every index (NH: 715 HEADs, about 8 minutes; PA: 365 HEADs).
- `data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem`: DigiCert public intermediate for
  rules.nebraska.gov (see Nebraska above).
- No changes under `src/` or `tests/`: no publisher needed a new adapter. The SD JSON-with-HTML-field
  documents use the existing `json_html_field` extraction; the batch-1 DOCX mode was not needed.
- GitNexus MCP tools were unavailable in this session, so no impact analysis was run; no existing
  function outside the generator script was modified.
- `uv run ruff check scripts/ src/ tests/` passes for the changed file. It reports 8 pre-existing findings
  in two other tracked scripts not touched by this run (`scripts/build_liheap_state_plan_manifests.py`
  unused import; `scripts/draft_program_work_orders.py` import style and one-line statements); left
  alone.

## Reviewer judgments

1. Batch rule and its extension beyond the queue (above): alphabetical order over states not on the lead
   list, 12 states marked `done` without extraction (incl. the combined-manual calls for MI, MN, WV, WY and
   the page-level recovery scope for NJ), and 18 rows added to the queue (12 done + 6 attempted).
2. Blocked publishers SC, KY, NE count as attempted; SC and NE look like geo/IP blocks and NE's DHHS site
   times out - retry from a US network before assigning adapter work. NM counts as attempted but is
   `needs_review`, not blocked: the publisher serves the files, only its index is a vendor widget.
3. `regulation` for SD (ARSD 67:10, sections as documents) and ID (IDAPA 16.03.08) with
   `us-sd/regulation/arsd/67/10/...` and `us-id/regulation/idapa/16/03/08/...`; `manual` for PA, VA, LA, NH.
4. Louisiana: the DCFS PowerDMS public directory (a vendor-hosted platform the agency itself uses and
   links as its policies listing) was accepted as the publisher's own index and file host; only the
   policy parts of the combined EI manual were taken (not forms, DSNAP, LaCAP, or the other EI families).
5. Page-level extraction for VA chapters and LA documents; topic-page HTML blocks for PA and NH;
   rule-level JSON/HTML for SD; numbered sections for ID with the reserved ranges and part labels dropped
   (the reserved ranges are otherwise empty rows and swallowed section 111).
6. Combined manuals taken whole: NH FAM (FANF + medical assistance + child care), PA Cash Assistance
   Handbook (all cash programs incl. GA and Refugee Cash); VA chapters 900-1000 (VIEW) taken as part of
   the TANF manual.
7. expression_date choices: HTTP Last-Modified for PA, VA, NH pages; 2026-09-10 (source_as_of) for SD
   rules and LA documents where the publisher sends no date; the rule's own effective marks for ID.
8. SD: 17 repealed/transferred sections and the article/chapter TOC records not taken; ID: 16.03.04 and
   16.03.05 (already in the corpus) not re-taken.
9. Tests: the focused subset passes except the 10 known sparse-worktree failures (below).

## Timing

Per-jurisdiction extraction seconds (full runs, shared corpus root): VA 7, SD 27, ID 3 (first run 2),
PA 61 (first run failed after 13 s on the en-dash URL), LA 200, NH 941 - one impersonated fetch per topic page (first run failed after 4 s
without impersonation). Manifest generation: VA, SD, ID, PA, LA, NH in one run 21:01:50-21:12:42 (SD
rule walk about 150 s; NH HEADs about 8 min); PA+ID regeneration about 2 min. NY/OR retries about 35 s.

## Tests

`uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 256 passed, 10 failed, 2 skipped in the worktree (69.9 s). The 10 failures are the expected
`FileNotFoundError`s on `data/corpus/...` artifacts absent from this sparse checkout:
test_be_rulespec_2026_08_23_promotion, test_build_ny_tanf_compatibility_scope (2),
test_rulespec_be_source_promotion, test_us_ak_snap_manual, test_us_ct_snap_manual, test_us_mi_snap_manual,
test_us_mt_snap_manual, test_us_nd_snap_manual, test_us_ny_snap_manuals. No other failure.

## Rebuild

```bash
uv run python scripts/build_tanf_state_policy_manual_manifests.py \
  --only us-va --only us-sd --only us-id --only us-pa --only us-la --only us-nh   # fetches every index live
for st in va sd id pa la nh; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base data/corpus --version 2026-09-10-tanf-state-policy-manual \
    --manifest manifests/us-$st-tanf-state-policy-manual.yaml
done
# rules.nebraska.gov only: REQUESTS_CA_BUNDLE=<certifi cacert.pem + data/certs/*.pem concatenated>
```

No credentials read or written. Extraction of the six scopes ran without `REQUESTS_CA_BUNDLE` (no chain
repair was needed for their hosts).

## Remaining

Blocked or pending publishers: SC, KY, NE (retry from a US network), NY (bot challenge), OR (DNS from
this network), NM (reviewer decision on the RealFile index). Every state on the lead list now has a
status; states still without a queue row are the alphabetical successors of the batch-2 extension (OH,
RI, TN, VT, WI). Federal: 45 CFR 260-265 via `extract-ecfr`, and the ACF OFA state plan index
(unchanged from batch 1). Known batch-1 issue left alone per the work order: the us-co scope's sections
3.606.1, 3.606.2, 3.606.6 share citation paths with `us-co/regulation/2026-07-13-recovery`. Controller:
`sign-ingest-manifest` per scope, immutable release selector, `publish_corpus.py --dry-run`, publish.
