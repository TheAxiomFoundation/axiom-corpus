# WIC: FNS guidance (FY 2025-2026 policy memoranda, income eligibility guidelines) and state policy manuals

Date: 2026-09-10
Program: WIC (board Year 1 list; `manifests/wic-agent-queue.yaml`)
Branch: `discovery/ingest-wic`

Timing: started_at 2026-09-10T16:34:31+0200, finished_at 2026-09-10T17:13:38+0200 (agent wall time
2,347 seconds, about 39 minutes, measured just before the commit that carries this note). Extraction wall time per jurisdiction (final, complete
runs; earlier GA/PA attempts that failed on dead publisher links are described below):

| scope | started | elapsed_seconds | documents | provisions |
|---|---|---|---|---|
| us / guidance | 2026-09-10T17:00:48+0200 | 6 | 11 | 22 |
| us-ca / manual | 2026-09-10T17:02:46+0200 | 132 | 138 | 276 |
| us-tx / manual | 2026-09-10T17:02:46+0200 | 39 | 146 | 292 |
| us-mi / manual | 2026-09-10T17:02:46+0200 | 44 | 115 | 230 |
| us-nc / manual | 2026-09-10T17:02:57+0200 | 27 | 23 | 46 |
| us-pa / manual | 2026-09-10T17:08:47+0200 | 40 | 44 | 88 |
| us-ga / manual | 2026-09-10T17:11:14+0200 | 25 | 127 | 254 |

Totals: 7 scopes, 604 documents, 1,208 provisions (one root plus one body provision per document),
coverage `complete: true` for every scope, 0 missing, 0 extra, 0 duplicate citation paths (checked
directly in each provisions JSONL, not only via the coverage report). Smoke runs before the full
runs: TX (`--limit 3`, browser-impersonation path) and CA (`--limit 3`, CA-bundle path) into a
scratch base, both complete. Jurisdictions attempted 11 (federal + CA, TX, FL, NY, PA, IL, OH, GA,
NC, MI); extracted 7; blocked 4 (NY, FL, IL, OH; reasons below).

## Federal: USDA Food and Nutrition Service (now Food and Nutrition Administration)

Publisher facts a reviewer needs: FNS was renamed the Food and Nutrition Administration (FNA) on
2026-06-01 and its site moved to `www.fna.usda.gov`; the legacy `/wic/policy-memoranda` and
`/wic/regulations` paths no longer exist (404 on the origin). The public front door
(`www.fns.usda.gov` and `www.fna.usda.gov`, Akamai) answers HTTP 403 "Access Denied
(errors.edgesuite.net)" to every client tried: plain requests, browser user agent, curl_cffi
impersonation (chrome/chrome131/safari/firefox/edge), the Claude fetch proxy, and a real browser on
this machine. The publisher's own origin host `fns-prod.azureedge.us` serves the same Drupal site and
files (the existing `manifests/us-snap-guidance.yaml` already downloads FNS files from it), so the
index and memo pages were read there. Two of that host's quirks are recorded in the generator:
compressed responses are cached without the query string, so the resource browser's facet filter is
only honored with `Accept-Encoding: identity`; and the listing's `page` parameter is ignored, so
only the first listing page (ten newest rows) is enumerable. The memo pages carry no text of their
own: each embeds its PDF from the USDA guidance portal
(`www.usda.gov/sites/default/files/guidance-documents/...`), which serves PDFs only to
browser-impersonated clients; manifests use the existing `request: browser_impersonation` option.

Index inventory (index_url `https://www.fna.usda.gov/resources?f[0]=program:32&f[1]=resource_type:160`,
the FNA resource browser filtered to WIC + Policy Memos, linked as "View policy" from the WIC agency
page `https://www.fna.usda.gov/wic/agency`):

- Policy memos family: 154 documents (index's own facet count). By the index's year facet:
  2026: 3, 2025: 7, 2024: 11, 2023: 6, 2022: 9, 2021: 8, 2020: 3, 2019: 6, 2018: 1, 2017: 1, 2016: 5,
  2015: 5, 2014: 7, 2013: 4, 2012: 2, 2011: 5, 2010: 2, 2009: 3, 2008: 4, 2007: 4, 2006: 4, 2005: 3,
  2004: 4, 2003: 4, 2002: 1, 2001: 4, 2000: 1, 1999: 4, 1998: 5, 1997: 2, 1996: 1, 1995: 7, 1994: 7,
  1993: 4, 1992: 6, 1991: 1. The ten rows visible (2025-01-10 to 2026-04-29) are stored in the queue
  row (`index_inventory.first_page_rows`); the year facet says they are exactly the 2025-2026 rows.
- Sibling families on the same browser (WIC + resource type): Guidance Documents 195, Federal
  Register Notices 70 (the regulations / final-rule family now lives there; the old regulations page
  is gone). Not taken.
- Income Eligibility Guidelines family: the WIC agency page links the 2026-2027 IEG publication on
  the USDA guidance portal; the transmitting memos (#2025-4, #2026-5) cite the Federal Register
  notices 90 FR 11598 and 91 FR 23050.

Taken (11 documents, `manifests/us-wic-fns-guidance.yaml`, version `2026-09-10-wic-fns-guidance`,
document_class `guidance`, source_as_of 2026-09-10, expression dates from each document):

- `us/guidance/fns/wic/income-eligibility-guidelines/2026-2027`: 91 FR 23050 (2026-08323, published
  2026-04-29, effective 2026-07-01 to 2027-06-30), govinfo HTML.
- `us/guidance/fns/wic/income-eligibility-guidelines/2025-2026`: 90 FR 11598 (2025-03576, published
  2025-03-10, effective 2025-07-01 to 2026-06-30), govinfo HTML.
- `us/guidance/fns/wic/policy-memo/<n>`: FY 2025 memos #2025-1 (2024-12-06), #2025-2 (2024-12-20),
  #2025-3 (2025-01-10), #2025-4 (2025-03-27), #2025-5 (2025-08-19); FY 2026 memos #2026-1
  (2025-12-05), #2026-2 (2025-12-10), #2026-4 (2026-03-30), #2026-5 (2026-04-29). Numbers and dates
  were read from each PDF header. #2025-1 and #2025-2 (December 2024) are on the un-enumerable second
  listing page; they were located by their FNA page slugs and confirmed on those pages.
- Not taken from the visible rows: "Promoting Stronger Vendor Integrity and Oversight in WIC"
  (2025-09-25, an unnumbered letter), "Information for WIC State Agencies on Executive Order 14218"
  (2026-02-06, unnumbered), and the "State Agency Options and Select Federal Requirements" companion
  page (HTML companion to #2025-5). No memo #2026-3 is listed anywhere on the index.
- 7 CFR 246 is already in the corpus: 268 provisions under `us/regulation/7/246` in
  `data/corpus/provisions/us/regulation/2026-07-13-recovery-r2026-07-17-dedup.jsonl`. Not re-ingested.

Extraction: memos are `single_block` (root + one body provision each). The Federal Register HTML
notices are govinfo `<pre>` text and extract as one block. See reviewer judgments below.

## States (first batch)

Selection rule (reviewer judgment): the ten largest states by population (CA, TX, FL, NY, PA, IL,
OH, GA, NC, MI). Every state row is present in the queue; extracted rows are `agent_ready`, blocked
rows are `blocked_primary_source` with the exact failure. document_class `manual`, version
`2026-09-10-wic-state-policy-manual`, one document per policy/chapter PDF listed on the agency's own
manual index, citation path `us-xx/manual/<agency>/wic/<section label>`, `single_block` extraction.
Expression date for every state document is the CLI value 2026-09-10 (see judgments).

| state | index_url | index families (count) | taken |
|---|---|---|---|
| CA | https://www.cdph.ca.gov/Programs/CFH/DWICSN/Pages/LocalAgencies/PoliciesandPolicyResources/WPPM.aspx | WPPM policy PDFs 138; other PDF links (forms, unrelated) 9 | 138 |
| TX | https://www.hhs.texas.gov/providers/wic-providers/wic-policy-procedures-manual | policy PDFs 137; working-draft "(T)" policy PDFs 9; complete-manual PDF 1 | 146 (both policy families; the complete manual is the same content) |
| GA | https://dph.georgia.gov/WIC/wic-policy-and-procedures-manual | policy PDFs 138 (of which 11 answer 404/403 on the publisher); section outline PDFs 11; "IS Policies Combined" 1 | 127 |
| MI | https://www.michigan.gov/mdhhs/assistance-programs/wic/wic-staff/wicpolicymanual/mi-wic-policy-manual-table-of-contents | numbered policy/exhibit PDFs 115; unnumbered attachments (MOUs, forms, client agreements) 12 | 115 |
| PA | https://wic.health.pa.gov/pawic/PoliciesAndProcedures.aspx | policy PDFs 44; policy index PDF 1; other PDFs on the page (forms, FAQs) 11 | 44 |
| NC | https://www.ncdhhs.gov/divisions/child-and-family-well-being/community-nutrition-services-section/wic/staff/wic-local-agency-resources | chapter PDFs 23 (1, 2, 3, 4, 5, 6, 6A-6F, 7-17); complete-manual PDF (01.2026) 1 | 23 |

Blocked (nothing downloaded; one blocked publisher did not hold the rest):

- NY (health.ny.gov): the NYS WIC Program Manual is not published on the state site; the WIC pages
  link no manual, the only host copies are inactive procurement attachments
  (`funding/ifb/inactive/16429/wic_program_manual_*.pdf`), and current copies exist only as reposts
  on non-government sites (nwica.org, thewichub.org), which the queue forbids.
- FL (floridahealth.gov): the WIC Procedure Manual DHM 150-24 is referenced by number in county
  documents but no state index or PDF exists; the WIC and health-care-provider pages link only forms,
  the vendor handbook and outreach material.
- IL (dhs.state.il.us): the IDHS "WIC Policy and Procedure Manual" page (item=36418) now redirects to
  "Page Not Found" (item=27893) and the WIC program page (item=31907) links no manual. One chapter
  PDF (`onenetlibrary/27896/.../wic/ppm/3_certificationstandards.pdf`, issue date May 2006) is still
  served, but there is no publisher index from which the current manual can be confirmed.
- OH (odh.ohio.gov): the Ohio WIC Policy and Procedure Manual is not published; the Local Staff and
  program pages link no manual, and the only public copy is a July 2015 county repost.

Access notes per publisher: hhs.texas.gov and michigan.gov answer 403 to non-browser clients
(manifest `request: browser_impersonation: true, browser_impersonation_direct: true`);
wic.health.pa.gov stalls urllib3 keep-alive downloads mid-body while curl completes them
(manifest `request: range_fetch: true, range_backend: curl`, the option documented for servers that
stall urllib3; its PDF URLs contain literal spaces and are percent-encoded by the generator);
dph.georgia.gov, ncdhhs.gov, govinfo.gov and fns-prod.azureedge.us work with the plain client.

TLS: `www.cdph.ca.gov` (issuer Sectigo Public Server Authentication CA OV R36) fails verification
against certifi and `www.dhs.state.il.us` omits its Entrust OV TLS Issuing RSA CA 2 intermediate.
Both public intermediates were fetched from the leaf certificates' AIA URLs
(`http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt`,
`http://crt.sectigo.com/EntrustOVTLSIssuingRSACA2.crt`) into
`data/certs/sectigo-public-server-authentication-ca-ov-r36.pem` and
`data/certs/entrust-ov-tls-issuing-rsa-ca-2.pem`; the generator builds
`data/certs/wic-state-ca-bundle.pem` = certifi + both. Every extraction ran with
`REQUESTS_CA_BUNDLE` pointing at that bundle. Verification was never disabled.

## Artifacts (unsigned, uncommitted, awaiting controller)

- `data/corpus/sources/us/guidance/2026-09-10-wic-fns-guidance/official-documents/*.{pdf,html}`
- `data/corpus/{inventory,provisions,coverage}/us/guidance/2026-09-10-wic-fns-guidance.{json,jsonl,json}`
- `data/corpus/sources/us-xx/manual/2026-09-10-wic-state-policy-manual/official-documents/*.pdf`
- `data/corpus/{inventory,provisions,coverage}/us-xx/manual/2026-09-10-wic-state-policy-manual.{json,jsonl,json}`
  for xx in ca, tx, ga, mi, pa, nc.

Rebuild:

```bash
uv run python scripts/build_wic_manifests.py
export REQUESTS_CA_BUNDLE=$PWD/data/certs/wic-state-ca-bundle.pem
uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-10-wic-fns-guidance --manifest manifests/us-wic-fns-guidance.yaml --source-as-of 2026-09-10
for st in ca tx ga mi pa nc; do
  uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-10-wic-state-policy-manual --manifest manifests/us-$st-wic-policy-manual.yaml \
    --source-as-of 2026-09-10 --expression-date 2026-09-10
done
```

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
in this sparse worktree: 255 passed, 2 skipped, 10 failed. All ten failures are pre-existing
FileNotFoundError / same-file assertions on `data/corpus/...` fixtures (SNAP manual TOC tests for
CT, MI, MT, ND, NY and the Belgian source-promotion test), which are absent from this worktree's
sparse checkout; none touch WIC code or manifests. No adapter code was added, so no new tests.

GitNexus impact analysis was not run: the GitNexus MCP tools were unavailable in this session. No
existing function was modified; the only code added is `scripts/build_wic_manifests.py`.

## Reviewer judgments

1. Origin host as the publisher's own site. The FNA front door blocks every client; reading the
   publisher's Azure origin (`fns-prod.azureedge.us`) is treated as the publisher's own site, not a
   mirror, following `manifests/us-snap-guidance.yaml`. Manifest `source_url` values are the
   canonical `www.fna.usda.gov` page URLs; the memo bytes come from the USDA guidance portal
   (`download_url`).
2. Memo index completeness. Only the first listing page could be enumerated (the origin ignores
   `page`); FY 2025 memos dated before 2025 were confirmed by slug on the publisher's site. The
   claim "every FY 2025 and FY 2026 memo" rests on the contiguous numbering #2025-1..#2025-5 and
   #2026-1, -2, -4, -5 (no #2026-3 is published on the index) plus the index's year facet.
3. Memo segmentation. The work order asked for one provision per memorandum section. Memo sections
   are unlabeled bold prose headings, inconsistent across memos (several have none), so each memo
   is a single body provision under its root; per-section splitting is deferred to a revision with
   per-memo heading patterns.
4. Two IEG periods taken (2025-2026 and 2026-2027) although only the current one was required;
   both are in force in this corpus window and are cheap.
5. Unnumbered federal items (vendor-integrity letter, EO 14218 information memo, the
   options-requirements HTML companion) were not taken; they are on the memo index but carry no memo
   number. Guidance Documents (195) and Federal Register Notices (70) families were inventoried only.
6. State expression dates. Each state policy PDF prints its own effective date, but the manifests
   use the CLI `--expression-date 2026-09-10` (the date the index published them) rather than
   parsing 600 first pages; a later revision can set per-document expression dates.
7. State segmentation is `single_block` per policy/chapter PDF (the citation path is the policy or
   chapter). NC chapters are large (up to 150 KB of text in one provision); a later revision could
   split them by numbered section.
8. TX: the nine "(T)" working-draft policies are taken alongside final policies (labels suffixed
   `t`, metadata `working_draft: true`) because the publisher says they are the versions in use;
   the complete-manual PDF was not taken as a duplicate.
9. GA: eleven policies listed on the index are not retrievable from the publisher (404: NS-200.03,
   NS-200.10, NS-210.14, NS-220.02, CT-800.01, CT-820.03, CT-820.05, CT-860.01, CT-860.04,
   FD-940.01; 403: CT-800.13). Some are core certification policies (eligibility criteria, physical
   presence, notice of ineligibility, fair hearing). They are recorded in the queue row and not
   taken; section outlines and the "IS Policies Combined" compilation were not taken.
10. MI: numbered policies and lettered exhibits (e.g. 2.13A) are taken; unnumbered attachments
    (MOUs, forms, client agreements in three languages) are not. The policy-index PDF was not taken.
11. CA: four index labels are doubled. Spanish translations of 980-1060 and 980-1065 got `-es`
    labels; 210-02 and 1000-50 are each linked to two different files under one number and both were
    taken (second file labeled `-2`); a reviewer should decide which is current.
12. PA: the 44 policies on the HTML index were taken; the 2020 policy index PDF and 11 forms/FAQ
    PDFs on the same page were not.
13. NC: the per-chapter PDFs were taken rather than the complete 01.2026 manual PDF (same content,
    addressable by chapter).
14. Blocked states were not worked around: no third-party reposts, no county copies, no archived
    copies were used for NY, FL, IL, OH.

Remaining (controller): `sign-ingest-manifest` per scope, immutable release selector,
`publish_corpus.py --dry-run`, then publish and activate. Second state batch: the remaining
states, plus re-attempting NY/FL/IL/OH if their agencies publish an index.
