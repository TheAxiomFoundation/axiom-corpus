# WIC: state policy manuals, batch 5 (the last five jurisdictions: DC extracted; AK, ND, VT, WY not published; AZ, DE re-checked)

Date: 2026-09-10 (probes and extraction), 2026-09-11 (verification, note, commit)
Program: WIC (board Year 1 list; `manifests/wic-agent-queue.yaml`)
Branch: `discovery/ingest-wic`
Previous runs: `docs/ingest-runs/2026-09-10-wic-fns-guidance-and-state-manuals.md` (batch 1),
`docs/ingest-runs/2026-09-10-wic-state-manuals-batch-2.md` (batch 2),
`docs/ingest-runs/2026-09-10-wic-state-manuals-batch-3.md` (batch 3),
`docs/ingest-runs/2026-09-10-wic-state-manuals-batch-4-retry.md` (batch 4)

Timing: two agent sessions. The first started with the probes of the five publishers at 2026-09-10T22:58Z (the
timestamp it wrote into the generator's `BLOCKED` entries), re-checked AZ and DE at 23:00Z, wrote `build_dc` and the
four `BLOCKED` entries, generated `manifests/us-dc-wic-policy-manual.yaml` and the five queue rows, ran the DC extraction
(artifact mtimes: first source PDF written 23:08:59Z, inventory/provisions/coverage written 23:09:33Z) and was killed
before writing this note or committing (no finished_at of its own; roughly 22:58Z-23:10Z, about 12 minutes). The
continuation started_at 2026-09-11T09:35:22Z, finished_at 2026-09-11T09:58:12Z (continuation wall time 1370 seconds, about
23 minutes, measured just before the commit that carries this note); it inspected the uncommitted diff, confirmed
every finding with one plain request per publisher, regenerated the manifest and queue rows (byte-identical to what the
first session left), verified the DC scope independently of the coverage report, attempted and abandoned a timed
re-extraction (judgment 6), ran lint and tests, wrote this note and committed. The network exited from a US address in
both sessions. Extraction wall time per jurisdiction (final, complete run):

| scope | started | elapsed_seconds | documents | provisions |
|---|---|---|---|---|
| us-dc / manual | 2026-09-10T23:08Z (first session) | about 34 (derived from artifact mtimes, 23:08:59Z first PDF to 23:09:33Z coverage; the continuation's timed re-run was abandoned after 11 minutes and 9 files, see judgment 6) | 92 | 184 |

Totals: 1 scope, 92 documents, 184 provisions (one root plus one body provision per document), coverage
`complete: true`, 0 missing, 0 extra, 0 duplicate citation paths. The scope was checked independently of the coverage
report by a script over the provisions JSONL, the inventory, the source files and the manifest (run 2026-09-11T09:54Z):
every manifest citation path has exactly one level-1 root row and exactly one level-2 body row (`<path>/document-1`)
under it, no path repeats, every body row has non-empty text (smallest 1,028 characters, largest 25,051), every root
row's `source_url` equals its manifest document's URL, every row's `source_path` lies under
`sources/us-dc/manual/2026-09-10-wic-state-policy-manual/` and is an inventory item, all 184 inventory items are
provision rows, the 92 files on disk are exactly the 92 inventory source paths (no extra, no symlink) and every file's
SHA-256 matches its inventory hash; and no citation path of the scope exists in any of the 9 other provisions JSONL
files under `data/corpus/provisions/us-dc/` (form 1, manual 3: `2026-07-17-dc-snap-manual`,
`2026-07-19-dc-child-care-subsidy`, `2026-09-10-tanf-state-policy-manual`; policy 2; statute 3). No smoke run was made
for DC: its files are plain PDF downloads from the program site's CDN on the same extractor path as batch 4's RI/ME/WV
(batch-4 convention), and the first full run was complete.

Conventions unchanged from batches 1-4: document_class `manual`, version `2026-09-10-wic-state-policy-manual`, one
document per policy PDF listed on the agency's own manual index, citation path `us-xx/manual/<agency>/wic/<section
label>`, `single_block` extraction, expression date = CLI value 2026-09-10, and
`REQUESTS_CA_BUNDLE=data/certs/wic-state-ca-bundle.pem` (certifi plus the two batch-1 intermediates, rebuilt by the
generator; gitignored under `data/`). No new intermediate was needed (`data/certs/` is unchanged) and TLS verification
was never disabled (Delaware's chain failure, below, was left as a failure). One convention differs for DC:
`source_as_of` is `2026-09-11` in the manifest and therefore in every provision row (judgment 5).

## Part 1: the five jurisdictions without a queue row (AK, DC, ND, VT, WY)

Each WIC program page was fetched once with the plain client and a browser User-Agent (20 s timeout) at
2026-09-10T22:58Z; all five answered HTTP 200, so no impersonation was spent. The linked sub-pages were then read where
a local-agency, policy or manual page could be expected. The continuation re-read each recorded index URL once at
2026-09-11T09:38Z (plain client, 20 s): same status, same finding for every row.

| jurisdiction | agency page | finding | outcome |
|---|---|---|---|
| DC | dchealth.dc.gov WIC service page links the DC Health WIC State Agency's program site dcwic.org (three links; confirmed 09:54Z); its public 'Policies, Forms, & Tools' page lists one PDF per numbered policy in ten chapter dropdowns | manual index found | extracted (92) |
| AK | health.alaska.gov WIC page (legacy dpa/Pages/nutri/wic URL redirects to it) links applications, vendor newsletters, Vendor Forms, Approved Foods, Clinics by Region, Farmers Market and Vendor Management; Vendor Management links only the learn.dhss.alaska.gov login; Nutrition topic page lists none; legacy manual.aspx / policy.aspx and one guessed path answer 404 | no policy manual or local-agency section published | blocked_primary_source (not published) |
| ND | hhs.nd.gov WIC page (via www.hhs.nd.gov/wic; three legacy health/... paths 404) and twelve sub-pages are participant- and store-facing; eWIC for Stores links one PDF (approved infant formula suppliers); site search for 'WIC policy manual' returns only those pages | no manual or local-agency section | blocked_primary_source (not published) |
| VT | healthvermont.gov WIC section: fourteen sub-pages, none a policy or local-agency page; Plans & Reports links the '2025 State Plan Goals and Objectives' PDF (state-plan family, MT precedent) and data reports; Information for Grocers links the Grocer Handbook and vendor forms (vendor family) | no manual published | blocked_primary_source (not published) |
| WY | health.wyo.gov WIC page and thirteen sub-pages list no manual or local-agency section; Vendor Services links a 'Vendor Manual', stocking requirements and a price survey as Google Docs (vendor family); site search returns only the program page | no program policy manual published | blocked_primary_source (not published) |

## Part 2: re-check of the two batch-4 access blocks (AZ, DE)

Once each at 2026-09-10T23:00Z (one plain request and one `curl_cffi` chrome120 impersonation), recorded in the
generator's `RETRIED` table and appended to the queue rows' `notes`; the continuation confirmed each with one plain
request at 09:39Z and spent no further impersonation.

| state | batch-4 failure | re-check | outcome |
|---|---|---|---|
| AZ | relocated Local Agencies page (prevention/azwic/agencies/index.php) links 'WIC Manuals' to `#manuals`, which the served page does not contain | 23:00Z: same page (80,005 bytes) to the plain client and to the impersonation, still no element with id `manuals`. 09:39Z plain: HTTP 200, 79,014 bytes (content drift), the 'WIC Manuals' link still `href="#manuals"`, still no `id="manuals"` or `name="manuals"` | still blocked: no manual index as served; browser check remains a controller item |
| DE | www.dhss.delaware.gov 403 to the plain client; impersonation fails TLS (self-signed certificate in chain) | 23:00Z: HTTP 403 'Web App - Unavailable' (1,892 bytes) to the plain client; impersonation still curl 60 self-signed certificate in certificate chain, not disabled. 09:39Z plain: the recorded index URL (dhss/dph/chs/wichome.html) and dhss/dph/chca/dphwichom01.html both 403, 1,892 bytes, title 'Web App - Unavailable' | same failure; recorded, not fixed |

## Extracted

| state | index_url | index families (count) | taken |
|---|---|---|---|
| DC | https://www.dcwic.org/policies-forms ('Policy and Procedures' tab) | policy PDFs 92 in ten chapter dropdowns (2 Nutrition Services, 3 MIS, 4 Organization and Management, 5 Nutrition Services Administration, 7 Caseload Management, 8 Certification and Eligibility, 9 Food Delivery, 10 Monitoring and Audits, 11 Civil Rights, 12 Administrative Procedures; no chapter 1 or 6 is listed); lettered policy attachments ('N.NNNA Title': forms, guides, workbooks) 57; clinical manuals above the tabs (Anthropometrics, Laboratory) 2; style guides above the tabs 2; other tabs: Admin Forms 22, Assessment Tools 8, Substance Use Resources 5, Teletask Messaging Guides 4 (index_document_count 192); annotations: one repeated link to the same file (12.008A links the 12.008 PDF; `duplicate_link_same_file`), no duplicate policy number | 92 |

Access notes: dcwic.org serves the index page to the plain client with a browser User-Agent; the PDFs are served from the
site's Webflow CDN (cdn.prod.website-files.com), which served all 92 files in about 34 s on 2026-09-10T23:09Z and about
one file per 80 s on 2026-09-11T09:41Z-09:52Z (judgment 6). No impersonation, range backend or CA-bundle extension was
needed. The 'LA Staff Portal' on dcwic.org is password-protected and was not entered.

DC labels: the policy number from the link text (`2.001 State Agency Nutrition Services Plan` ->
`us-dc/manual/dchealth/wic/2.001`); the policy title follows the number in the link text and is kept in the document
title together with the chapter number and title (`DC WIC Policy & Procedure Manual, Chapter 8 Certification and
Eligibility: Policy 8.004 ...`). Chapter number, chapter title, link text, the program site and the agency page that
links it are recorded per document. The link text `11.00lB Civil Rights Complaint Form` (letter l for 1) is matched by
the regex as an attachment of 11.001 and not taken.

## Blocked (nothing downloaded; no mirrors, reposts, proxies or archived copies used)

Not published on the publisher's site: AK, ND, VT (State Plan and Grocer Handbook only), WY (vendor manual as a Google
Doc only). Access blocks re-checked and unchanged: AZ (manuals anchor absent from the served page), DE (403; TLS chain
to the impersonation). The exact failure per row is in `BLOCKED` / `RETRIED` in the generator and in the queue row
`notes`. After this batch every one of the 51 jurisdictions (50 states plus DC) has a queue row; see the closing table.

## Artifacts (unsigned, uncommitted, awaiting controller)

In the main checkout's corpus root (`/Users/pavelmakarchuk/axiom-corpus/data/corpus`, where batches 1-4's artifacts
are; this worktree is sparse and excludes `data/corpus`):

- `data/corpus/sources/us-dc/manual/2026-09-10-wic-state-policy-manual/official-documents/*.pdf` (92 files)
- `data/corpus/{inventory,provisions,coverage}/us-dc/manual/2026-09-10-wic-state-policy-manual.{json,jsonl,json}`

Rebuild (`--only` limits the generator to these rows; the BLOCKED loop runs after the builders, so a jurisdiction must be
removed from `BLOCKED` before its builder's row can stay `agent_ready`; none of the batch-5 rows is in both tables, so
one pass is enough, and the pass run by the continuation reproduced the manifest and queue byte for byte):

```bash
uv run python scripts/build_wic_manifests.py --only us-dc,us-ak,us-nd,us-vt,us-wy,us-az,us-de
export REQUESTS_CA_BUNDLE=$PWD/data/certs/wic-state-ca-bundle.pem
uv run axiom-corpus-ingest extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --version 2026-09-10-wic-state-policy-manual --manifest manifests/us-dc-wic-policy-manual.yaml \
  --source-as-of 2026-09-10 --expression-date 2026-09-10
```

Lint: `uv run ruff check scripts/build_wic_manifests.py` is clean (run 2026-09-11T09:40Z, after the last generator
edit; the continuation made no generator edit).

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"` in this
sparse worktree: 255 passed, 2 skipped, 10 failed in 47.0 s (run 2026-09-11T09:50:54Z-09:51:43Z). The ten failures are
the known pre-existing FileNotFoundError / same-file assertions on `data/corpus/...` fixtures absent from this sparse
checkout (BE rulespec promotion, NY TANF compatibility x2, BE source promotion, and the AK/CT/MI/MT/ND/NY SNAP manual
tests), identical to batches 1-4; none touch WIC code or manifests. No adapter code was added: dcwic.org works with the
existing `extract-official-documents` options, so no new tests.

GitNexus impact analysis was not run: the GitNexus MCP tools were unavailable in both sessions. No existing function
was modified; in `scripts/build_wic_manifests.py` the additions are `build_dc`, four `BLOCKED` entries (AK, ND, VT, WY),
two `RETRIED` entries (AZ, DE), five `STATE_NAMES` entries, `BATCH_NOTE[6]`, five `BATCH` entries, one `STATE_BUILDERS`
entry and one paragraph of the module docstring.

## Reviewer judgments

1. Continuation: the first session's uncommitted diff (generator, queue, DC manifest) and its corpus artifacts were
   inspected rather than redone. The generator pass `--only us-dc,us-ak,us-nd,us-vt,us-wy,us-az,us-de` run by the
   continuation reproduced the manifest and the queue byte for byte, every publisher finding was confirmed with one
   plain request, and the DC artifacts passed the independent check above, so everything on disk was kept.
2. DC's index is on dcwic.org, not on dchealth.dc.gov. It is taken as the agency's own index because the DC Health WIC
   service page links dcwic.org as the program's site and the site identifies itself as DC Health WIC (headquarters
   address and info.wic@dc.gov in its footer); the agency label in the citation path is `dchealth`.
3. DC takes the 92 numbered policies and not the 57 lettered attachments (forms, guides, workbooks; WV precedent), the
   two clinical manuals (Anthropometrics, Laboratory), the two style guides or the four other tabs' files. A reviewer
   who wants the clinical manuals should add them as two documents; they are not policies of the manual.
4. DC's index lists no chapter 1 or 6; the labels are the publisher's policy numbers, so the gaps are preserved rather
   than renumbered. 12.008A links the 12.008 file a second time and is skipped (`duplicate_link_same_file`, MN/WV
   precedent).
5. DC `source_as_of` is `2026-09-11`, not the batches 1-4 value `2026-09-10`: the generator stamps the local date of the
   index read (`SOURCE_AS_OF = date.today()`), and the first session read the index at 22:58Z on 2026-09-10, which was
   00:58 local on 2026-09-11; the extractor lets the manifest value override the CLI `--source-as-of 2026-09-10`, so
   all 184 rows carry `2026-09-11`. It was left as generated (hand-editing a generated manifest would be reverted by the
   next generator run, and the date is the true local fetch date); `expression_date` is the CLI value 2026-09-10 as in
   every batch. A reviewer who wants uniform dates can regenerate and re-extract on a day of their choosing.
6. The continuation started a timed re-extraction of DC at 09:40:47Z to own the per-state seconds; the Webflow CDN
   served about one 170 KB file per 80 s (a 20 s `curl` of one PDF received 11-19 KB), so after 11 minutes and 9 files
   (2.001-2.009, each byte-identical to its inventory hash) the run was stopped. The extractor writes inventory,
   provisions and coverage only at the end, so the first session's artifacts (mtimes 23:09:33Z) were untouched; all 92
   source files were re-hashed against the inventory afterwards and match. The slow-down was not worked around (no
   parallelism, proxy or mirror); the elapsed time in the table is derived from the first run's artifact mtimes.
7. AK, ND, VT and WY are publication gaps, not access blocks: every page answered 200 and none lists a policy manual or
   a local-agency section. VT's State Plan is the state-plan family (MT/MA/UT precedent) and WY's vendor manual the
   vendor family; neither was taken.
8. AZ and DE were re-checked once by the first session (plain plus one impersonation each, 23:00Z) and confirmed by the
   continuation with one plain request each; the `RETRIED` text keeps the 23:00Z stamp. The AZ page shrank from 80,005
   to 79,014 bytes between the two reads and still has no `manuals` element; DE's 403 body is unchanged (1,892 bytes).
   Neither block was worked around and TLS verification was not disabled.
9. Probe budget: one program page per jurisdiction plus linked sub-pages; AK received three legacy/guessed URL attempts
   (all 404) and ND three legacy paths (all 404) because their sites had moved; DE received one extra plain request in
   the continuation (the chca/dphwichom01.html page, also 403).
10. Expression dates are the CLI value 2026-09-10 for every document (batch-1 convention).

Remaining (controller): `sign-ingest-manifest` for `us-dc/manual/2026-09-10-wic-state-policy-manual`, immutable release
selector, `publish_corpus.py --dry-run`, then publish and activate. Every jurisdiction now has a row; the territories
were never in scope. Retry first: AZ (browser check of the agencies page), KS (Document Center listing or challenge),
AR, MA, NH, DE (front doors), IL (DNS); the not-published rows if their agencies post an index.

## Status after five batches: all 51 jurisdictions

Queue `status_counts`: agent_ready 22 (federal guidance plus 21 state manual scopes, 1,820 documents, 3,640 provisions,
every coverage report `complete: true`), blocked_primary_source 30. Documents/provisions are the corpus counts for
`2026-09-10-wic-state-policy-manual`; "taken/index" is `taken_count`/`index_document_count` from the queue.

| jurisdiction | status | batch | result |
|---|---|---|---|
| us-ak | blocked_primary_source | 5 | not published on health.alaska.gov |
| us-al | blocked_primary_source | 3 | not published (Procedure Manual cited by the formulary, not posted) |
| us-ar | blocked_primary_source | 3 | access: HTTP 403 (Cloudflare); retried batch 4, same |
| us-az | blocked_primary_source | 2 | reachable since batch 4; 'WIC Manuals' anchor absent from the served page; re-checked batch 5, same |
| us-ca | agent_ready | 1 | extracted 138/147; 138 documents, 276 provisions |
| us-co | agent_ready | 3 | extracted 110/111; 110 documents, 220 provisions |
| us-ct | agent_ready | 3 | extracted 118/208; 118 documents, 236 provisions |
| us-dc | agent_ready | 5 | extracted 92/192; 92 documents, 184 provisions |
| us-de | blocked_primary_source | 4 | access: HTTP 403; impersonation fails TLS (self-signed chain); re-checked batch 5, same |
| us-fl | blocked_primary_source | 1 | not published (DHM 150-24 not on floridahealth.gov) |
| us-ga | agent_ready | 1 | extracted 127/150; 127 documents, 254 provisions |
| us-hi | blocked_primary_source | 4 | not published on health.hawaii.gov |
| us-ia | agent_ready | 3 | extracted 169/234; 169 documents, 338 provisions |
| us-id | blocked_primary_source | 4 | not published on healthandwelfare.idaho.gov |
| us-il | blocked_primary_source | 1 | manual page redirects to Page Not Found; host did not resolve in batch 4 |
| us-in | blocked_primary_source | 2 | not published on in.gov |
| us-ks | blocked_primary_source | 3 | Document Center is a React shell fed by an admin endpoint; Cloudflare challenge |
| us-ky | agent_ready | 3 | extracted 10/13 (batch 4 retry); 10 documents, 20 provisions |
| us-la | blocked_primary_source | 3 | reachable since batch 4; manual not published |
| us-ma | blocked_primary_source | 2 | access: HTTP 403; retried batch 4, same |
| us-md | agent_ready | 2 | extracted 8/8; 8 documents, 16 provisions |
| us-me | agent_ready | 4 | extracted 111/193; 111 documents, 222 provisions |
| us-mi | agent_ready | 1 | extracted 115/127; 115 documents, 230 provisions |
| us-mn | agent_ready | 3 | extracted 83/150; 83 documents, 166 provisions |
| us-mo | blocked_primary_source | 2 | manual behind the Local Agency Portal login |
| us-ms | blocked_primary_source | 3 | not published on msdh.ms.gov |
| us-mt | blocked_primary_source | 4 | policies published only as the 2026 WIC State Plan (state-plan family) |
| us-nc | agent_ready | 1 | extracted 23/24; 23 documents, 46 provisions |
| us-nd | blocked_primary_source | 5 | not published on hhs.nd.gov |
| us-ne | blocked_primary_source | 4 | not published on dhhs.ne.gov |
| us-nh | blocked_primary_source | 4 | access: HTTP 403 (impersonation 404, page moved) |
| us-nj | agent_ready | 2 | extracted 9/10 (partial: vendor-management area only); 9 documents, 18 provisions |
| us-nm | blocked_primary_source | 3 | policies page links only the intranet |
| us-nv | blocked_primary_source | 3 | manual page password-protected |
| us-ny | blocked_primary_source | 1 | not published on health.ny.gov |
| us-oh | blocked_primary_source | 1 | not published (Local Staff and program pages 404) |
| us-ok | blocked_primary_source | 3 | not published on oklahoma.gov |
| us-or | agent_ready | 3 | extracted 88/111 (batch 4 retry); 88 documents, 176 provisions |
| us-pa | agent_ready | 1 | extracted 44/56; 44 documents, 88 provisions |
| us-ri | agent_ready | 4 | extracted 2/75 (compiled Procedures Manual, Vendor Policies); 2 documents, 4 provisions |
| us-sc | blocked_primary_source | 3 | reachable since batch 4; manual not published |
| us-sd | blocked_primary_source | 4 | not published on doh.sd.gov |
| us-tn | blocked_primary_source | 2 | reachable since batch 4; manual policies exist under content/dam but no page indexes them |
| us-tx | agent_ready | 1 | extracted 146/147; 146 documents, 292 provisions |
| us-ut | agent_ready | 3 | extracted 107/107; 107 documents, 214 provisions |
| us-va | agent_ready | 2 | extracted 147/200; 147 documents, 294 provisions |
| us-vt | blocked_primary_source | 5 | not published on healthvermont.gov (State Plan and Grocer Handbook only) |
| us-wa | agent_ready | 2 | extracted 33/134; 33 documents, 66 provisions |
| us-wi | blocked_primary_source | 2 | not published on dhs.wisconsin.gov |
| us-wv | agent_ready | 4 | extracted 140/272; 140 documents, 280 provisions |
| us-wy | blocked_primary_source | 5 | not published on health.wyo.gov (vendor manual as a Google Doc only) |

Tally: 51 rows; 21 extracted (agent_ready), 30 blocked_primary_source, of which 7 are access blocks (AR, AZ as served,
DE, IL, KS, MA, NH), 3 are manuals behind a login or password (MO, NM, NV) and 20 are publishers that do not post the
manual (AK, AL, FL, HI, ID, IN, LA, MS, MT, ND, NE, NY, OH, OK, SC, SD, TN, VT, WI, WY).
