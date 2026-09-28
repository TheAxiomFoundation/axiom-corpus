# TANF state policy manuals, batch 4 (retry from a US network)

Date: 2026-09-10
Program: TANF (board Year 1 list; `manifests/tanf-agent-queue.yaml`)
Branch: `discovery/ingest-tanf` (worktree, sparse checkout without `data/corpus`; artifacts written to the shared corpus root of the main checkout, `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`, where `data/` is gitignored)

started_at: 2026-09-10T21:33:54Z (first command of this session)
finished_at: 2026-09-10T21:59:39Z (tests re-run and commit follow within the minute)
agent wall time: about 28 min (21:33:54Z to 21:59Z; network waits under 1 min in total - every answering host replied in under 3 s)

## Batch rule (reviewer judgment 1)

Batch 4 is not a new slice of the 51: it is the retry the batch 2 and 3 notes asked for, run while the controller's
network exits from a US address. Work order: every `blocked_primary_source` row (NY, OR, SC, KY, NE, OH, TN, VT) and the
NM `needs_review` row, one plain request plus one curl-cffi chrome impersonation attempt each with 20 s timeouts; where
the publisher answers, confirm the manual or rule on its own index, inventory it, extract, verify, move the row to
`agent_ready`; where it still fails, append "retried <timestamp> from US network, same failure". Batch 4 =
**NY, OR, SC, KY, NE, OH, TN, VT, NM** (9 rows). No earlier state's manifest was regenerated (`--only` per state; git
shows only the eight new manifest files, the script, the queue and this note).

## Probe (2026-09-10T21:34:43Z to 21:35:28Z)

| host | plain requests | curl-cffi chrome | outcome |
|---|---|---|---|
| otda.ny.gov (TASB.pdf) | RemoteDisconnected (server closed without response) | HTTP 200 text/html 7.6 KB bot-challenge page (`window["bobcmn"]`/TSPD) | still blocked |
| ch461rules.odhs.oregon.gov | 200 | 200 | answers (self-described unofficial; see OR) |
| secure.sos.state.or.us (OARD) | 200 (2.8 s) | not needed | answers - official OAR |
| dss.sc.gov manuals page | 200 | 200 | answers |
| www.chfs.ky.gov opmanual.aspx | 404 | 404 | host answers; the lead index moved (see KY) |
| rules.nebraska.gov | SSLError (leaf-only chain) -> 200 with the stored DigiCert intermediate | CertificateVerifyError (curl-cffi has no bundle override) | answers with the repaired chain |
| dhhs.ne.gov/Pages/ADC.aspx | 404 | 404 | host answers (page gone); not needed |
| emanuals.jfs.ohio.gov CAM | SSLError after 12 s (handshake dropped) | `curl: (35) TLS connect error` after 14 s | still blocked (TLS ClientHello rejected; http:// "Empty reply from server") |
| codes.ohio.gov 5101:1 | 200 | 200 | answers |
| www.tn.gov Families First page | 200 | 200 | answers |
| dcf.vermont.gov current rules | 200 | 200 | answers |
| outside.vermont.gov 2200-Reach-Up.pdf | 200 application/pdf 840,668 B | 200 | answers (no F5 rejection) |
| www.srca.nm.gov chapter 102 page | 200 | 200 | answers (widget index unchanged; see NM) |

## Results

| jurisdiction | status | document_class | documents taken / on index | provisions | elapsed s |
|---|---|---|---|---|---|
| us-ny | blocked_primary_source (retried, same failure) | manual | 0 / 1 | 0 | - |
| us-or | extracted (OAR adapter) | regulation | 541 rules in 28 divisions / 541 | 571 | 26 |
| us-sc | extracted | manual | 1 / 27 PDFs on the manuals page | 408 | 6 |
| us-ky | extracted | manual | 2 / 12 Operation Manual volumes | 337 | 4 |
| us-ne | extracted | regulation | 5 / 5 chapters of 468 NAC | 342 | 4 |
| us-oh | extracted (OAC adapter; CAM still blocked) | regulation | 63 rules in 5 chapters / 63 | 70 | 3 |
| us-tn | extracted | manual | 19 / 106 PDFs on the publications page (19 in the Families First section) | 118 | 7 |
| us-vt | extracted | regulation | 6 / 14 rule PDFs | 197 | 6 |
| us-nm | extracted (needs_review resolved) | regulation | 17 / 85 SRCA part links on the HCA ISD page (17 in 8.102) | 254 | 5 |

Retried 9, extracted 8, still blocked 1 (NY). Provision total: **2,297 rows across 8 scopes**, every scope
`complete: true`, 0 missing, 0 extra, 0 duplicate citation paths. Uniqueness was re-checked directly on each provisions
JSONL, and every new `citation_path` was checked against every other provisions JSONL under
`data/corpus/provisions/<jurisdiction>/` (SC 9 files, KY 8, TN 9, VT 6, NM 7, NE 5, OR 8, OH 6): 0 collisions in seven
scopes; in us-oh the single shared path is the OAC adapter's collection root `us-oh/regulation`, which the two other
OAC-adapter scopes (`2026-07-16-agency-5101-4`, the 5122-36 SSI scope) also carry by design - recorded, not skipped
(reviewer judgment 8).

Versions: `2026-09-10-tanf-state-policy-manual` for the six `extract-official-documents` scopes; the two adapter scopes
carry the adapter's scoped run id, `2026-09-10-tanf-state-policy-manual-chapter-461` (OR) and
`2026-09-10-tanf-state-policy-manual-agency-5101-1` (OH), because `oregon_admin_rules_run_id` / `ohio_admin_code_run_id`
append the filter to the version and no existing function was changed. document_class `manual` for the SC, KY, TN
agency manuals; `regulation` for VT (DCF-adopted rules), NM (NMAC 8.102), NE (468 NAC), OR (OAR 461), OH (OAC 5101:1).

Artifacts (unsigned, uncommitted, awaiting controller), per scope:

- `data/corpus/sources/<jur>/<class>/<version>/...` (official-documents scopes under `official-documents/`; OR/OH under the adapters' layouts)
- `data/corpus/inventory/<jur>/<class>/<version>.json`
- `data/corpus/provisions/<jur>/<class>/<version>.jsonl`
- `data/corpus/coverage/<jur>/<class>/<version>.json`

## Index inventories

**New York (us-ny) - still blocked.** Same publisher behaviour as batches 1 and 2: the plain GET of
https://otda.ny.gov/programs/temporary-assistance/TASB.pdf is closed by the server without a response; the chrome
impersonation GET returns HTTP 200 text/html 7,559 bytes, a JavaScript bot-challenge shell (`window["bobcmn"]`, TSPD
cookie logic), not the PDF. Row note appended: "Retried 2026-09-10T21:34Z from a US network (batch 4: ...), same
failure." No workaround. The 2024-2026 TANF State Plan (policy) and the Employment Policy Manual remain the NY TANF
documents in the corpus.

**Oregon (us-or, regulation, OAR adapter).** Both oregon.gov hosts resolve from this network. The lead list's ODHS
site https://ch461rules.odhs.oregon.gov/ answers but states "This website displays unofficial administrative rules ...
For official administrative rules, please visit the Secretary of State", linking the OARD chapter listing
https://secure.sos.state.or.us/oard/displayChapterRules.action?selectedChapter=90 - the index used. Family: chapter
461 (Department of Human Services, Self-Sufficiency Programs) = 28 divisions, 541 current rules (division list on the
queue row: 1 general definitions and rulemaking, 25 hearings, 101-198 program rules incl. 191 TEFAP, 192 Oregon Hunger
Response Fund, 194 tax infrastructure grants, 196 Summer EBT, 197/198 youth homelessness grants). Taken: the whole
chapter through the existing `extract-oregon-administrative-rules --only-chapter 461` adapter (1 collection row, 1
chapter, 28 division rows, 541 rule rows; citation paths `us-or/regulation/chapter-461/division-<n>/rule-461-<ddd>-<dddd>`),
30 source files, coverage 571/571. Chapter 461 is the combined rulebook for every ODHS self-sufficiency program, so it
was taken whole like the combined manuals of batches 1-3 (NH FAM, PA cash handbook, MI Bridges) rather than as a
hand-picked division set. The manifest `manifests/us-or-tanf-state-policy-manual.yaml` is a one-document descriptor
(like `manifests/us-oh-snap-rules.yaml` for the OAC adapter) recording the index, counts and the adapter command; it is
not an `extract-official-documents` input. expression_date 2026-09-10 (`--source-as-of`/`--expression-date` passed
explicitly because the adapter otherwise uses the version string as a date).

**South Carolina (us-sc, manual).** Index: DSS manuals page https://dss.sc.gov/about/data-and-resources/manuals/, 27
PDF links (APS policies, "Economic Services Policy and Procedure Manuals": SNAP manual volume 71 - the corpus holds the
us-sc SNAP manual scope -, the TANF Policy Manual, the SNAP/TANF Benefit Integrity manual; DSNAP, Refugee Resettlement,
SC Voucher, child welfare documents). Taken: the TANF Policy Manual, now **volume 67**
(`/media/bxwc1jdj/tanf-policy-manual-volume-67-final.pdf`, 407 pages, HTTP Last-Modified 2026-07-31 = expression_date),
page-level (`us-sc/manual/dss/tanf-policy-manual` and `.../page-N`, mirroring `us-sc/manual/dss/snap-policy-manual`).
The lead list's volume 65 URL still serves the superseded volume (Last-Modified 2025-01-13); not taken. Plain clients
answer, no impersonation flag.

**Kentucky (us-ky, manual).** The lead index https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/opmanual.aspx is HTTP
404 (the K-TAP program page moved to `/agencies/dcbs/dfs/fssb/Pages/ktap.aspx`, which links the Policy Development
Branch, not the manuals). The Division of Family Support page https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx
(the landing page of the ingested SNAP volumes II/IIA) lists the 12 Operation Manual volumes: I General Administration,
II SNAP, IIA SNAP work requirements, III KTAP, IIIA KWP, IV Vacant, IVA Non-MAGI Medicaid, IVB MAGI Medicaid/APTC/QHP,
V State Supplementation, VIII CCAP, IX OMTL cover letters, X Policy Updates. Taken: **Volume III - Kentucky Transitional
Assistance Program (KTAP)** (226 pages, OMTL-692, "R. 5/1/26", HTTP Last-Modified 2026-07-10) and **Volume IIIA -
Kentucky Works Program (KWP)** (109 pages, OMTL-628, "R. 8/1/23", Last-Modified 2025-10-31), page-level
(`us-ky/manual/dcbs/dfs/volume-iii-ktap`, `.../volume-iiia-kwp`, mirroring `.../volume-ii-snap`). expression_date =
HTTP Last-Modified per file (batch-2 rule); the manuals' own revision marks are in metadata. The batch-2 Azure Front
Door 403 did not recur; plain clients answer with the extractor's default user agent.

**Nebraska (us-ne, regulation).** rules.nebraska.gov is a client-rendered React app ("You need to enable JavaScript")
whose data comes from `https://rules.nebraska.gov/api/...` - the same API the ingested 475 NAC SNAP scope used
(`api/title/GetByAgencyId/37`, `api/chapter/GetByTitleId/<id>`, `api/fileStorage/GetAsByteArray/chapter-pdfs/<blob>`).
The host still serves only its leaf certificate; the DigiCert public intermediate stored in batch 2
(`data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem`) was concatenated with certifi's bundle into a scratch file
and passed as `REQUESTS_CA_BUNDLE` to the generator and the extractor (the generator refuses to run the NE builder
without it); verification was never disabled and no `verify_tls: false` is in the manifest (the SNAP manifest carried
one). Family: DHHS (agency 37) has 45 titles; title 468 Aid to Dependent Children (id 223) has 5 chapters, all
effective 2022-08-29: 1 General Background, 2 Eligibility Requirements, 3 Calculation of ADC Benefits, 4 Employment
First Self-Sufficiency Program (EF), 5 Emergency Assistance to Needy Families with Children (EA). Taken: all 5 as the
publisher's chapter PDF blobs (`468 NAC <n> (08-29-2022).pdf`; the API has no signed `officialPdfBlobName` for this
title, unlike 475 NAC), `labeled_sections` with the 475 NAC scope's heading and continuation patterns and
`normalize_parenthetical_label_components` (no `drop_lines`: these blobs have no attorney-general/governor signature
page). 337 section rows (`us-ne/regulation/title-468/chapter-<n>/<label>`), every label numeric. expression_date = the
API's chapter `effectiveDate` (the PDF endpoint sends no Last-Modified). Landing page
https://rules.nebraska.gov/rules?agencyId=37&titleId=223. The batch-2 Azure gateway 403 did not recur.

**Ohio (us-oh, regulation, OAC adapter; CAM still blocked).** The ODJFS eManuals host now accepts the TCP connection
but drops the TLS handshake for every client tried (plain requests `SSLError` after 12 s, curl-cffi chrome `curl: (35)
TLS connect error`, curl `SSL_ERROR_SYSCALL` on the ClientHello, TLS 1.2-only the same; `http://` returns an empty
reply), so the Cash Assistance Manual is still unreachable - recorded on the row with the retry timestamp. codes.ohio.gov
(Legislative Service Commission, the host of the ingested OAC 5101:4 SNAP scope) answers: agency 5101:1 "Division of
Public Assistance" https://codes.ohio.gov/ohio-administrative-code/5101:1 lists 5 chapters - 5101:1-1 General
Provisions, 5101:1-2 Application Process; Verification, 5101:1-3 Ohio Works First, 5101:1-23 Income, 5101:1-24
Prevention, Retention, and Contingency (PRC) - with 63 rules. Taken: the whole agency division through the existing
`extract-ohio-administrative-code --only-agency 5101:1` adapter (1 collection, 1 agency, 5 chapter, 63 rule rows;
`us-oh/regulation/agency-5101-1/chapter-5101-1-<n>/rule-5101-1-<n>-<nn>`), 7 source files, coverage 70/70, exactly as the
SNAP scope took 5101:4 instead of the eManuals Food Assistance manual. The OAC rules are the adopted text the CAM
reproduces; the row's document_class changed from `manual` to `regulation`. Descriptor manifest as for OR.

**Tennessee (us-tn, manual).** Index: DHS publications page
https://www.tn.gov/humanservices/information-and-resources/dhs-publications.html (the landing page of the ingested SNAP
policy scope), 106 PDF links. The "Families First (TANF)" section lists 19 policies of the 23 series: 23.01
Application Process, 23.02 Assistance Units, 23.03 Technical Eligibility, 23.04 Resource Eligibility, 23.05 Income
Eligibility, 23.06 Drug Testing, 23.07 Personal Responsibility Plans, 23.11 Child Support Cooperation, 23.12 EBT
Location Restrictions, 23.13 Work and/or Educational Activity, 23.14 Time Limits, 23.16 Marriage During Receipt of
Assistance, 23.17 Verification and Documentation, 23.18 Authorization and Case Management, 23.19 Overpayments and
Underpayments, 23.21 Family Focused Solutions, 23.22 Child Care, 23.23 Diversion Payments, 23.24 Work Incentive
Payments (23.08-23.10, 23.15, 23.20 are not published; the section notes that links to forms are internal). Taken: all
19, page-level (`us-tn/manual/dhs/families-first/23-NN`, mirroring `us-tn/manual/dhs/snap/24-NN`), 99 pages; expression_date
= HTTP Last-Modified per file (17 files 2026-04-24, 23.12 2026-07-31, 23.16 2026-08-10). The batch-3 read timeout did
not recur (one transient connection failure with the extractor's default user agent at 21:47Z succeeded on retry and
during extraction; no request flag).

**Vermont (us-vt, regulation).** Index: DCF ESD Current Rules page https://dcf.vermont.gov/esd/laws-rules/current, 14
rule PDFs on outside.vermont.gov (the 12 numbered files inventoried in batch 3 plus the Emergency Housing FY26 rules
and the renumbering bulletin) and the 3SquaresVT manual link. Taken: the six TANF-family files 2000 All Programs, 2100
Reach First, 2200 Reach Up, 2300 Reach Up Services, 2400 Post Secondary Education, 2500 Reach Ahead, page-level
(`us-vt/regulation/dcf/esd-rules/<nnnn>`), 191 pages; expression_date = HTTP Last-Modified per file (2000 and 2500
2022-05-19, 2100 2024-08-30, 2300/2400 2024-08-21, 2200 2026-06-30). Not taken: 2600-3100 (GA, AABD-EP, EA, fuel,
refugee cash) and the two other documents. The F5 gateway served every file with HTTP 200 application/pdf.

**New Mexico (us-nm, regulation) - needs_review resolved.** The batch-2 question was whether to accept the SRCA
RealFile vendor widget as the index or find an agency-published parts index. The Health Care Authority Income Support
Division page https://www.hca.nm.gov/lookingforinformation/income-support-division-1/ - the `source_index_url` the
ingested us-nm SNAP regulations scope already uses - lists 85 SRCA part files by chapter (8.100 x10, 8.102 x17, 8.106
x17, 8.119 x7, 8.139 x17, 8.150 x17). Family: chapter 102 Cash Assistance Programs, 17 parts (100, 110, 120, 230, 400,
410, 420, 460, 461, 462, 500, 501, 510, 520, 610, 611, 620). Taken: all 17 from the publisher's part files
(`https://www.srca.nm.gov/parts/title08/08.102.<nnnn>.html`, all HTTP Last-Modified 2025-04-21 = expression_date),
`labeled_sections` with the SNAP scope's per-part heading pattern (`8.\s*102.\s*<part>.\s*N`), 237 section rows
(`us-nm/regulation/nmac/8/102/<part>/8.102.<part>.<n>`); titles from each part's "PART nnn ..." heading. Not taken:
8.100 (general provisions) and 8.139 (SNAP), both in the corpus; 8.106 GA, 8.119 LIHEAP, 8.150 child care. The SRCA
chapter page still lists only reserved part ranges; no vendor API and no probe-by-number was used.

## Code changes

- `scripts/build_tanf_state_policy_manual_manifests.py` (existing generator, extended rather than a new script):
  `BATCH_4`, `BATCH_LABEL` extended ("Batch 4 (retry)"), helpers `plain_fetch` (plain `requests`, honours
  `REQUESTS_CA_BUNDLE`) and `heading_case`, builders `build_sc`, `build_ky`, `build_tn`, `build_vt`, `build_nm`, `build_ne`
  and the descriptor builders `build_or`, `build_oh`; `BUILDERS` wiring; `BLOCKED` reduced to NY with the batch-4 retry
  sentence appended; `NEEDS_REVIEW` emptied (NM now builds); `main()` takes the row's `target_scope.version` from the
  builder result when present (adapter run ids). Two generation passes fixed a case-sensitive KY volume filter (missed
  `omvolviii.pdf`), a rule-link regex in `build_oh` that missed decimal rule numbers, and trailing periods in two
  inventory strings; manifests were byte-identical across the passes.
- No changes under `src/` or `tests/`: the OR and OH scopes use the existing OAR/OAC adapters unchanged; NE reuses the
  existing `labeled_sections` mode; the batch-1 DOCX mode was not needed.
- `data/certs/`: no addition (the DigiCert intermediate from batch 2 was reused for rules.nebraska.gov; the concatenated
  bundle lives only in the scratch directory and is not committed).
- GitNexus MCP tools were unavailable in this session, so no impact analysis was run; no existing function outside the
  generator script was modified.
- `uv run ruff check scripts/build_tanf_state_policy_manual_manifests.py`: all checks passed.

## Reviewer judgments

1. Batch rule: batch 4 is the retry of the nine blocked/needs-review rows only; no new jurisdictions, no regeneration of
   earlier states.
2. Blocked count after the retry: NY only (bot challenge, a deliberate publisher block; keep `blocked_primary_source`
   until OTDA offers a non-browser path). The OH eManuals host is also still blocked (TLS handshake dropped), but Ohio
   is `agent_ready` on the OAC 5101:1 scope (judgment 4).
3. Oregon: the official OARD (Secretary of State) is the index, not the ODHS mirror that calls itself unofficial; the
   whole combined chapter 461 was taken through the existing adapter (division filter rejected: nearly every division
   applies to TANF, and combined manuals were taken whole in batches 1-3), so the scope includes the non-TANF divisions
   191, 192, 194, 196-198 the way WI's chapter 18 and NH's medical/child-care chapters were included.
4. Ohio: with the CAM unreachable, OAC 5101:1 on codes.ohio.gov is the adopted rule text the CAM reproduces and the
   same publisher/adapter the SNAP scope used for 5101:4; document_class `regulation`. The CAM (transmittal letters and
   procedural text) remains a possible later `manual` scope once the eManuals host accepts a TLS client.
5. Adapter run ids (`...-chapter-461`, `...-agency-5101-1`) deviate from the shared version string; accepted rather than
   changing adapter functions. The two manifests are descriptors (the us-oh-snap-rules precedent), not extraction inputs.
6. New Mexico: the agency-published HCA/ISD parts index (the SNAP scope's precedent) is the index; the vendor widget
   is not used. Only chapter 102 taken; the shared 8.100 general parts are already in the corpus under the SNAP scope.
7. Nebraska: chapter PDF blobs with `labeled_sections` (the 475 NAC patterns, no signature drop lines) rather than the
   API's `chapterHtml`, matching the SNAP scope's source choice; expression_date = API effectiveDate.
8. us-oh collision: the OAC adapter's collection root row `us-oh/regulation` is shared with the two other OAC-adapter
   scopes by design (identical row content); recorded for the controller, scope not skipped. No other collision in any
   of the eight scopes.
9. Kentucky: Volume IIIA (KWP) taken alongside Volume III (KTAP) because KWP is the KTAP work component (as VA's VIEW
   chapters were taken); the lead index URL is dead and the DFS page is the publisher's volume list.
10. South Carolina: the current volume 67 taken from the manuals page, not the lead list's superseded volume 65 URL.
11. Tennessee: the whole 23 series taken (incl. 23.21 Family Focused Solutions and 23.22 Child Care, listed in the
    Families First section); the 24-series SNAP policies were not re-taken.
12. Vermont: 2000 All Programs taken with 2100-2500 (it carries the general rules the Reach Up rules rely on); the
    other ESD programs' rules not taken.
13. expression_date choices: HTTP Last-Modified for SC, KY, TN, VT, NM files; NE the API's chapter effective date;
    OR/OH the run date (adapters take a single expression date; each rule's own history/effective text is in its body).
14. Tests: the focused subset passes except the 10 known sparse-worktree failures (below).

## Timing

Probes 21:34:43-21:35:28Z (45 s for 12 hosts, two clients each). Discovery of the moved KY index, the NE API, the OH
TLS failure and the NM index 21:36-21:48Z. Manifest generation (all eight states in one run, live indexes: TN 19 HEADs,
NM 17 GETs, KY 2 downloads, OH 6 pages, OR 1 page, NE 2 API calls) 21:52:21-21:53:00Z (39 s); OH regenerated alone
after the regex fix (about 5 s); KY/NM/OH regenerated after the punctuation and volume-filter fix (about 15 s).
Per-jurisdiction extraction seconds (full runs, shared corpus root, the six official-documents scopes in parallel
starting 21:53:22Z): SC 6, KY 4, TN 7, VT 6, NM 5, NE 4; adapters starting 21:53:32Z: OR 26 (28 division pages, 4
workers), OH 3. Tests 40 s (21:55:15-21:55:57Z).

## Tests

`uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 256 passed, 10 failed, 2 skipped in the worktree (39.7 s). The 10 failures are the expected `FileNotFoundError`s
on `data/corpus/...` artifacts absent from this sparse checkout: test_be_rulespec_2026_08_23_promotion,
test_build_ny_tanf_compatibility_scope (2), test_rulespec_be_source_promotion, test_us_ak_snap_manual,
test_us_ct_snap_manual, test_us_mi_snap_manual, test_us_mt_snap_manual, test_us_nd_snap_manual, test_us_ny_snap_manuals.
No other failure.

## Rebuild

```bash
# rules.nebraska.gov only needs the repaired chain; harmless for the other hosts
export REQUESTS_CA_BUNDLE=$(mktemp); cat "$(uv run python -c 'import certifi;print(certifi.where())')" data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem > "$REQUESTS_CA_BUNDLE"
uv run python scripts/build_tanf_state_policy_manual_manifests.py \
  --only us-sc --only us-ky --only us-tn --only us-vt --only us-nm --only us-ne --only us-or --only us-oh   # fetches every index live (about 40 s)
for st in sc ky tn vt nm ne; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base data/corpus --version 2026-09-10-tanf-state-policy-manual \
    --manifest manifests/us-$st-tanf-state-policy-manual.yaml
done
uv run axiom-corpus-ingest extract-oregon-administrative-rules --base data/corpus \
  --version 2026-09-10-tanf-state-policy-manual --only-chapter 461 \
  --source-as-of 2026-09-10 --expression-date 2026-09-10 --download-dir <cache> --workers 4
uv run axiom-corpus-ingest extract-ohio-administrative-code --base data/corpus \
  --version 2026-09-10-tanf-state-policy-manual --only-agency 5101:1 \
  --source-as-of 2026-09-10 --expression-date 2026-09-10 --download-dir <cache>
```

No credentials read or written. TLS verification was never disabled.

## Remaining

Blocked publisher: NY (OTDA bot challenge on TASB.pdf; no non-browser path found). Ohio's Cash Assistance Manual host
(emanuals.jfs.ohio.gov) still rejects TLS clients; the OAC 5101:1 scope stands in. Federal: 45 CFR 260-265 via
`extract-ecfr`, and the ACF OFA state plan index (unchanged; the federal row stays `needs_review`). Known batch-1 issue
left alone per the work order: the us-co scope's sections 3.606.1, 3.606.2, 3.606.6 share citation paths with
`us-co/regulation/2026-07-13-recovery`. Controller: `sign-ingest-manifest` per scope (24 agent_ready scopes now,
including the two adapter-driven ones), immutable release selector, `publish_corpus.py --dry-run`, publish; decide the
shared `us-oh/regulation` root row across the three OAC scopes at selector time.

## Closing table: all 51 jurisdictions and their final queue status

Tally (50 states + DC): done 26, agent_ready 24, blocked_primary_source 1, needs_review 0. The federal row (`us`) is
`needs_review`, so the queue's `status_counts` are done 26, agent_ready 24, blocked_primary_source 1, needs_review 1
(52 rows).

| jurisdiction | name | queue_status | document_class | target_manifest |
|---|---|---|---|---|
| us-ak | Alaska | done | regulation | manifests/us-ak-atap-regulations.yaml |
| us-al | Alabama | done | policy | manifests/us-al-tanf-official-documents.yaml |
| us-ar | Arkansas | done | policy | manifests/us-ar-tea-official-documents.yaml |
| us-az | Arizona | done | manual | manifests/us-az-des-faa5-manual.yaml |
| us-ca | California | agent_ready | regulation | manifests/us-ca-tanf-state-policy-manual.yaml |
| us-co | Colorado | agent_ready | regulation | manifests/us-co-tanf-state-policy-manual.yaml |
| us-ct | Connecticut | done | policy | manifests/us-ct-ssp-official-documents.yaml |
| us-dc | District of Columbia | agent_ready | manual | manifests/us-dc-tanf-state-policy-manual.yaml |
| us-de | Delaware | done | regulation | manifests/us-de-tanf-rules.yaml |
| us-fl | Florida | done | manual | manifests/us-fl-ess-manual.yaml |
| us-ga | Georgia | done | manual | manifests/us-ga-tanf-manual.yaml |
| us-hi | Hawaii | done | regulation | manifests/us-hi-tanf-admin-rules.yaml |
| us-ia | Iowa | done | regulation | manifests/us-ia-fip-admin-rules.yaml |
| us-id | Idaho | agent_ready | regulation | manifests/us-id-tanf-state-policy-manual.yaml |
| us-il | Illinois | done | manual | manifests/us-il-snap-manual.yaml |
| us-in | Indiana | done | manual | manifests/us-in-snap-manual.yaml |
| us-ks | Kansas | done | manual | manifests/us-ks-keesm.yaml |
| us-ky | Kentucky | agent_ready | manual | manifests/us-ky-tanf-state-policy-manual.yaml |
| us-la | Louisiana | agent_ready | manual | manifests/us-la-tanf-state-policy-manual.yaml |
| us-ma | Massachusetts | done | regulation | manifests/us-ma-tafdc-regulations.yaml |
| us-md | Maryland | done | regulation | manifests/us-md-tca-guidance-official-documents.yaml |
| us-me | Maine | done | regulation | manifests/us-me-tanf-regulation-official-documents.yaml |
| us-mi | Michigan | done | manual | manifests/us-mi-bridges-manual.yaml |
| us-mn | Minnesota | done | manual | manifests/us-mn-combined-manual.yaml |
| us-mo | Missouri | agent_ready | manual | manifests/us-mo-tanf-state-policy-manual.yaml |
| us-ms | Mississippi | agent_ready | manual | manifests/us-ms-tanf-state-policy-manual.yaml |
| us-mt | Montana | agent_ready | manual | manifests/us-mt-tanf-state-policy-manual.yaml |
| us-nc | North Carolina | done | manual | manifests/us-nc-work-first-manual-official-documents.yaml |
| us-nd | North Dakota | agent_ready | manual | manifests/us-nd-tanf-state-policy-manual.yaml |
| us-ne | Nebraska | agent_ready | regulation | manifests/us-ne-tanf-state-policy-manual.yaml |
| us-nh | New Hampshire | agent_ready | manual | manifests/us-nh-tanf-state-policy-manual.yaml |
| us-nj | New Jersey | done | regulation | manifests/us-nj-wfnj-rules.yaml |
| us-nm | New Mexico | agent_ready | regulation | manifests/us-nm-tanf-state-policy-manual.yaml |
| us-nv | Nevada | done | manual | manifests/us-nv-eligibility-payments-manual.yaml |
| us-ny | New York | blocked_primary_source | manual | manifests/us-ny-tanf-state-policy-manual.yaml |
| us-oh | Ohio | agent_ready | regulation | manifests/us-oh-tanf-state-policy-manual.yaml |
| us-ok | Oklahoma | agent_ready | regulation | manifests/us-ok-tanf-state-policy-manual.yaml |
| us-or | Oregon | agent_ready | regulation | manifests/us-or-tanf-state-policy-manual.yaml |
| us-pa | Pennsylvania | agent_ready | manual | manifests/us-pa-tanf-state-policy-manual.yaml |
| us-ri | Rhode Island | agent_ready | regulation | manifests/us-ri-tanf-state-policy-manual.yaml |
| us-sc | South Carolina | agent_ready | manual | manifests/us-sc-tanf-state-policy-manual.yaml |
| us-sd | South Dakota | agent_ready | regulation | manifests/us-sd-tanf-state-policy-manual.yaml |
| us-tn | Tennessee | agent_ready | manual | manifests/us-tn-tanf-state-policy-manual.yaml |
| us-tx | Texas | done | manual | manifests/us-tx-manuals.yaml |
| us-ut | Utah | done | regulation | manifests/us-ut-fep-official-documents.yaml |
| us-va | Virginia | agent_ready | manual | manifests/us-va-tanf-state-policy-manual.yaml |
| us-vt | Vermont | agent_ready | regulation | manifests/us-vt-tanf-state-policy-manual.yaml |
| us-wa | Washington | done | manual | manifests/us-wa-eaz-manual.yaml |
| us-wi | Wisconsin | agent_ready | manual | manifests/us-wi-tanf-state-policy-manual.yaml |
| us-wv | West Virginia | done | manual | manifests/us-wv-manuals.yaml |
| us-wy | Wyoming | done | manual | manifests/us-wy-manuals.yaml |

The `target_manifest` of the NY row is the path the builder will write once OTDA is reachable; that file does not
exist yet. The OR and OH manifests exist as descriptors; their `target_scope.version` values are the adapter run ids.
