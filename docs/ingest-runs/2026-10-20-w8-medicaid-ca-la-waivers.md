# Wave 8 Medicaid reprobe: the California CCR section, the Louisiana eligibility manual and the six section 1115 rows

Date: 2026-10-20 (UTC).
Work order: the `family: w6_bundle_gap` us-ca and us-la rows and the six `family: cms_1115_stc` `needs_review` rows of
`manifests/medicaid-agent-queue.yaml` (`docs/coverage/program-bundle-gaps-2026-10-06/wave6/health.csv`, branch
`analysis/program-bundle-gaps-2026-10-06`; the 1115 rows come from the wave-5 closure,
`docs/ingest-runs/2026-09-15-medicaid-chip.md`).
Branch `discovery/ingest-w8-medicaid` cut from `main` 393127f8b in the sparse worktree `~/axiom-corpus-worktrees/w8-medicaid`
(`data/corpus/` excluded, never symlinked); the extraction wrote to the main checkout's corpus root
(`--base <main checkout>/data/corpus`), artifacts uncommitted and unsigned.
Timing: started 2026-10-20T18:51:58Z, finished 2026-10-20T19:32Z, about 40 minutes of agent time. Duplicate-work check and
history reading to 18:54Z, publisher probes 18:54Z-19:05Z, the medicaid.gov demonstration pass 19:05Z-19:12Z, generator and
extraction 19:12Z-19:15Z, verification 19:15Z-19:20Z, first draft of this note to 19:28Z, then a controller correction on
probe method (judge a host on its response body, and test the extractor's own browser-user-agent retry before adding a
`request` option) and the re-verification, test baseline and note rewrite it required, 19:28Z-19:32Z. Per-target extraction
seconds: us-ca CCR 7 s; us-ca ACWDL, us-la and the six 1115 rows, no extraction (nothing takeable).
Impact analysis: not run (the GitNexus MCP tools are not available in this session). No library function under `src/` was
modified; the only code change is one new generator.
Duplicate-work check (before any edit): `gh search prs "medicaid" --repo TheAxiomFoundation/axiom-corpus --state open
--limit 20` returned four PRs (819, 867, 899, 812), `gh search issues "1115 waiver" --state open` returned none, and the
file lists of all 33 open PRs name no `manifests/medicaid-agent-queue.yaml` change. PR 899 touches four older Medicaid run
notes, but only to scrub local machine paths; it covers none of these rows. No row was skipped for duplicate work.

Outputs: this note; one new generator; one new manifest; nine updated queue rows. Nothing under `data/corpus/` is committed.

## Result

| Target | Row | Index found | Taken | Outcome |
| --- | --- | ---: | ---: | --- |
| CCR section on the official CCR publisher | us-ca `w6_bundle_gap` (govt.westlaw.com) | 12 sections in the Article 2 table of contents | 1 | EXTRACTED `us-ca/regulation/2026-10-20-w8-medicaid-ccr-section` |
| DHCS All County Welfare Directors Letters index | us-ca `w6_bundle_gap` (dhcs.ca.gov) | 93 pages named by the publisher's sitemap, no body served | 0 | BLOCKED (unchanged), 6 work-order rows |
| Louisiana Medicaid eligibility document | us-la `w6_bundle_gap` (ldh.la.gov) | 99 documents on the LDH eligibility-manual index | 0 new | ALREADY-HELD in a signed release |
| Section 1115 demonstration list | us-ak, us-id, us-nd, us-ne, us-nv, us-sc `cms_1115_stc` | 7, 13, 11, 12, 15, 16 listings | 0 | ABSENT re-verified; publisher answers, posts nothing takeable |

The one new scope reports coverage `complete: true`, 0 missing, 0 extra, 0 duplicate provision citations and 0 duplicate
source citations.

Final `status_counts`: `needs_review: 7, agent_ready: 194, blocked_primary_source: 9, done: 6` (216 rows). Before this run:
`needs_review: 7, agent_ready: 192, blocked_primary_source: 11, done: 6`. The two moves are the us-ca CCR row and the us-la
row leaving `blocked_primary_source` for `agent_ready`; the six 1115 rows stay `needs_review`, the us-ca ACWDL row stays
`blocked_primary_source`.

## Publisher access (2026-10-20T18:54Z to 19:40Z, TLS verified against certifi, nothing added to `data/certs/`, `REQUESTS_CA_BUNDLE` untouched)

Every host below was judged on its response body, never on its status line, and the plain path was tried first on each
one because most hosts need nothing. The method, after two controller corrections during the run:

- A 200 counts as unreachable where the body is a challenge or a stub. One of these hosts serves a challenge with 200 as
  readily as with 403.
- A body from roughly 5 KB upward is a candidate challenge (measured Cloudflare challenge bodies run 5,490 to 6,350
  bytes here and elsewhere), and a body under about 3 KB is a candidate stub or redirect shell. Both are candidates only:
  the decision is made by reading the body.
- Decided by these markers: `Attention Required! | Cloudflare`, `Just a moment...`, `bobcmn`, `cf_chl_opt`, `chk_jschl`,
  `Checking your browser`, Incapsula, Radware, TSPD, captcha. `challenge-platform` is **not** used: Cloudflare injects
  that telemetry script into genuine pages, so it is a false positive.
- A pass also requires the publisher's own page furniture: a real `<title>` and real navigation entries, not only an
  absence of markers.
- The small-body rule is not applied to an API response. No JSON endpoint was used in this run; the six medicaid.gov
  inventories were taken from the HTML list pages, 128 to 196 KB each.
- The extractor's ladder is the corpus user agent first, then the browser-user-agent retry `_download_document` already
  performs on a 403 (`OFFICIAL_DOCUMENT_BROWSER_USER_AGENT`, Chrome/124.0), and only then a curl_cffi fingerprint. That
  second rung cannot clear a Cloudflare challenge by design, and `src/axiom_corpus/corpus/documents.py` says why near
  lines 473-475: a Chrome user agent on a non-Chrome TLS fingerprint is itself a bot signal. It was still tried on every
  host, and on `ldh.la.gov` it was enough.

- `govt.westlaw.com/calregs`: fingerprint-blocked, and impersonation is genuinely required. The corpus user agent is
  answered a Cloudflare "Just a moment. Enable JavaScript and cookies to continue" body (HTTP 403, 6,158 bytes), and the
  extractor's own browser-user-agent retry is answered the same challenge body (HTTP 403, 6,350 bytes), with and without
  the `bhCookieSess`/`bhCookiePerm` cookies the 2026-09-14 CCR scope uses. So the user-agent fallback alone is not enough
  here. A curl_cffi `chrome120` fingerprint is served the pages themselves: the CCR index HTTP 200 (14,573 bytes, the
  title list), the Title 10 browse page 23,002 bytes, Chapter 5.6 7,182 bytes, Article 2 listing its 12 sections, and the
  § 2699.200 document 23,188 bytes with an `#co_document` body. That body was read, not assumed: it holds the section's
  regulatory text from "(a) All eligibility requirements contained herein shall be applied without regard to race,
  creed, colour..." through the authority and reference note (Insurance Code section 12696.05) and 20 numbered history
  entries to "End of Document", 8,201 characters once extracted. It is CCR text, not a challenge and not a search shell.
  No challenge was solved and no CAPTCHA was answered. The `/calregs/Search/Results?...` address the queue row carries
  does answer a "Please click here to continue" interstitial even to `chrome120` (HTTP 200, 4,281 bytes, no content), so
  the section was reached down the publisher's own browse table of contents instead. The retained artifact was then
  checked against the marker list after extraction: 23,035 characters, zero challenge markers (and no
  `challenge-platform` either), title "View Document - California Code of Regulations", the publisher's own Home,
  Updates, Search, Help and Table of Contents navigation, an `#co_document` body, and the strings `10 CCR § 2699.200`,
  "Barclays Official California Code of Regulations", "Access for Infants and Mothers", "Insurance Code" and "End of
  Document". For the avoidance of doubt about an earlier 8.4 KB figure: the page body is 23,188 bytes and 8,756
  characters of text; 8,201 is the character count of the extracted provision rows, not a response size.
- `www.dhcs.ca.gov`: still fully blocked, on the body. Every HTML address answers an Imperva/Incapsula
  `_Incapsula_Resource` challenge stub and no page content: HTTP 200 with 212 bytes to the extractor's
  browser-user-agent fallback (the brief's figure, reproduced exactly), 840-955 bytes to the corpus user agent and to
  `chrome120`. That holds for the site root, the ACWDL index, the "Program descriptions by FPL (Enclosure 3)" page the row
  names, the WordPress REST path, and the same addresses on `dhcs.ca.gov` without `www`. The publisher's sitemaps do
  answer with real XML (`robots.txt` 249 bytes, `sitemap.xml` 1,036 bytes, `page-sitemap{,2,3,4}.xml`, 1,001 pages on the
  first alone) and list the ACWDL index plus 92 year pages and an `acwdl-master-index` page, which proves the pages exist
  but carries no letter text.
- `ldh.la.gov`: answers again, and the block is on the user agent only, so no `request` option is needed. The corpus user
  agent is answered a 118-byte "403 Forbidden" body; the extractor's own browser-user-agent retry is served the real
  pages, HTTP 200 with the eligibility-manual index at 189,146 bytes (title "Medicaid Eligibility Manual | Louisiana
  Department of Health", 99 policy PDFs linked) and `H-3040m.pdf` at 29,941 bytes of `application/pdf`. The index diff
  against the held manifest was then re-run on that browser-user-agent body and is still zero in both directions. The 99
  policy PDFs are at `/assets/medicaid/MedicaidEligibilityPolicy/<id>.pdf`.
- `www.medicaid.gov`: answers the plain corpus client. The Approved-filter demonstration list for all six states and
  eighteen demonstration pages read HTTP 200 (128-196 KB each). A burst of six list requests drew an Akamai "Access
  Denied" HTTP 403 (459 bytes); a paced retry at about 9-12 s between requests cleared it and every later request
  answered. No impersonation was used on this host.
- `oal.ca.gov`: HTTP 200 to `chrome120` (the CCR publications page 153,246 bytes). Read to settle the Westlaw judgment
  below, not taken.
- `info.nystateofhealth.ny.gov` (the us-ny row): not touched. Another agent owns the New York rows.
- No mirror, repost, proxy or archived copy was fetched or taken. No TLS verification was disabled. No PolicyEngine file or
  compiled list was used as a source. No credential or secret was written to any file.

## Reviewer judgment 1: govt.westlaw.com is California's own publication channel for the CCR

The row's host is a vendor host, so the question had to be settled before anything was taken. It is the state's own
channel, and the row was worked rather than left blocked:

- Government Code section 11344 makes the Office of Administrative Law responsible for the official compilation, printing
  and publication of state regulations in the California Code of Regulations.
- OAL's own publications page, `https://oal.ca.gov/publications/ccr/`, links
  `govt.westlaw.com/calregs/Index?transitionType=Default&contextData=(sc.Default)` three times: as "Online", as
  "California Code of Regulations", and as "this site provided here" inside OAL's caution that OAL "cannot verify the
  authenticity of regulations downloaded from websites other than this site". OAL therefore names that host as the one
  online CCR whose text it vouches for, and updates it weekly.
- The document itself prints "Barclays Official California Code of Regulations" and the OAL hierarchy (Title 10.
  Investment / Chapter 5.6. Access for Infants and Mothers Program / Article 2. Eligibility, Application, and Enrollment).
- The repository already acts on this reading: `manifests/us-ca-income-tax-regulations.yaml` (version 2026-09-14, 211
  provision rows in `us-ca/regulation/18-ccr/...`) takes CCR sections from the same `/calregs/Document/` endpoint. This run
  follows that precedent rather than creating a second convention.

So the host is not a mirror of someone else's publication; it is the publication. Had OAL named a different site, or named
no site, the row would have stayed blocked with that reasoning instead.

## Reviewer judgment 2: the access method, flagged for the controller

The 2026-09-14 CCR scope reached the same endpoint with `request: fresh_session: true` plus the two Barclays cookies. That
no longer works: on 2026-10-20 Cloudflare answers a browser-check interstitial body on every path, cookies or not, to the
corpus user agent and to the extractor's own browser-user-agent retry alike, so the cheap fallback was tested first and
ruled out rather than assumed. That outcome is the expected one for a Cloudflare host, for the reason
`src/axiom_corpus/corpus/documents.py` gives near lines 473-475. Only a browser TLS fingerprint is served the document.
The new rows therefore carry `request: browser_impersonation: true, browser_impersonation_direct: true`
(curl_cffi `chrome120`, `verify=True`), the same pair the 2026-10-06 run records, which is the mechanism the repository
already uses for `hcpf.colorado.gov`,
`www.michigan.gov` and `www.medicaid.gov`, gated on a run note documenting it. This note is that documentation, and the
change from 2026-09-14 is recorded here deliberately: the controller may prefer to treat a publisher that will only answer
a browser fingerprint as blocked, and can overrule this row on that basis. Nothing else in the run depends on it.

## Reviewer judgment 3: the queue row names a Title 10 section, not a Title 22 section

The brief describes this row as "California Code of Regulations title 22 Medicaid sections". The row itself does not: its
`primary_source_url` is `.../Search/Results?t_querytext=2699.200&t_Method=tnc`, `blocked_count` is 1, and the 2026-10-06
note names "10 CCR 2699.200 (MCAP basis of eligibility)". The live CCR confirms the row: § 2699.200 "Basis of Eligibility"
sits in Title 10, Chapter 5.6 (Access for Infants and Mothers Program), Article 2, which the Medi-Cal Access Program
continues; Title 10 Chapter 5.8's sections run 2699.66xx. The row was worked as written. No Title 22 Medicaid section is
named by any Medicaid queue row, so none was taken; if the controller wants Title 22 Division 3 Medi-Cal sections, that is
a new work-order row, not this one.

## Reviewer judgment 4: the Louisiana row resolves to already-held, not to a new take

FAQ category 19 is the LaCHIP Affordable Plan question set. A FAQ page is not a policy document, and the eligibility
document that LDH's own index lists as current for that program is "H - 3040 LaCHIP Affordable Plan". That document, and
every other document the index lists, is already held: the live index lists 99 policy PDFs, and
`manifests/us-la-medicaid-eligibility-manual.yaml` (version `2026-09-10-medicaid-state-eligibility-manual`) holds 99
documents at byte-identical URLs. The diff is zero in both directions: 0 in the index and not held, 0 held and not in the
index, including `H-3040m.pdf` at `us-la/manual/ldh/medicaid/h-3040`. The diff was computed twice, the second time on the
body the extractor's own browser-user-agent retry is served, with the same result both times. That version appears in five
signed release
selectors, so it is immutable; it was not touched, and no duplicate scope was created. The row therefore keeps the
existing eligibility-manual version, as the brief directs for a row in that family, and moves to `agent_ready` with the
index inventory recorded.

## Reviewer judgment 5: the six section 1115 rows stay ABSENT, and the family stays separate

`cms_1115_stc` is a separate document family from the state eligibility manual: a different publisher (CMS, not the state
agency), a different document class (`policy`, not `manual`), and a different citation root (`us-xx/policy/cms/1115-stc`).
Its existing version `2026-09-15-medicaid-1115-stc` appears in two signed release selectors, so had anything been takeable
tonight it would have needed its own new version `2026-10-20-w8-medicaid-1115-stc`. Nothing was takeable, so no version was
cut and no manifest was written.

The list answers, and it answered in September too; what has not changed is the underlying fact. Each state's Approved-filter
list was inventoried and every eligibility-plausible listing was opened and read for its printed `Status` and waiver dates:

| Jurisdiction | Listings | Eligibility-bearing approved demonstration | What the publisher's own pages say |
| --- | ---: | --- | --- |
| us-ak | 7 | none | Alaska Behavioral Health Reform: Status Approved, 11/21/2018 to 12/31/2028, SUD/SMI service authority; newest postings a Technical Correction Approval 03/27/2026 and a Demonstration Approval - Evaluation Design 12/09/2025. The other six listings are 1915(c) waivers |
| us-id | 13 | none | Behavioral Health Transformation, Family Planning Referrals and Medicaid Reform Waiver all Status Pending; Childless Adults expired 09/30/2014; Children's Access Card expired 09/30/2013; Dental Smiles (ID-03), ID-02, ID-04 and ID.0004.R01.01 are 1915(b) |
| us-nd | 11 | none | the only 1115 listing, Managed Care Risk Mitigation COVID-19 PHE, Status Expired 05/11/2023; ND-0004.R05.00 (Approved 06/07/2024 to 06/30/2026) and ND-04 are 1915(b) |
| us-ne | 12 | none | Heritage Health Adult 1115 Status Terminated, expiration 09/02/2021, with the CMS approval to terminate posted; the SUD demonstration is service authority; Heritage Health (NE-0003, Approved to 09/30/2027) and NE-0004.R00.00 are 1915(b) |
| us-nv | 15 | none | Healthy Futures Status Pending (application 07/20/2026, CMS completeness letter 08/03/2026, no approval document); Comprehensive Care Waiver Status Expired 06/30/2018; reentry, OUD/SUD, CCBHC, dental and youth behavioural-health demonstrations are service authority |
| us-sc | 16 | none | Healthy Connections Works and Palmetto Pathways to Independence both Status Withdrawn (2019 approvals, withdrawn 2021); the 2025 Palmetto Pathways and Transitioning to Preconception Care listings Status Pending; the Enhanced Prenatal and Postpartum Home Visitation Pilot expired 03/31/2023 |

Two states do hold a current approved section 1115 demonstration whose pages serve approval documents: Alaska Behavioral
Health Reform (to 12/31/2028) and, on a pending extension, Idaho Behavioral Health Transformation. Both are
behavioural-health demonstrations. The wave-5 family rule, which the generator holds and
`docs/ingest-runs/2026-09-15-medicaid-chip.md` records, excludes SUD/SMI, reentry, CCBHC and payment demonstrations as
service authority rather than eligibility terms, and taking them would neither clear M-ST-1315 nor leave the family's
selection rule intact. They were not taken, and this is flagged as a scope question for the controller: if
service-authority 1115 approvals are wanted, they belong in their own family, not in `cms_1115_stc`.

The withdrawn South Carolina pages do serve "CMS Approval" PDFs from 12/12/2019. They were not taken either: a withdrawn
demonstration's approval is not current terms.

## The extracted scope

`scripts/build_medicaid_ca_ccr_section_manifests.py` (new) holds the selection as a table (title number, section, the
heading the table of contents prints, what the bundle row needs it for), reads the publisher's own Article 2 table of
contents at build time, and fails the build if a selected section is no longer listed or is listed under a different
heading. It writes `manifests/us-ca-medicaid-ccr-sections.yaml` (document class `regulation`, citation path
`us-ca/regulation/10-ccr/<section>`, content selector `#co_document` and the text selector the committed 18 CCR scope
uses), updates the us-ca `govt.westlaw.com` queue row, and records the eight other reprobed rows. Its fetch helper
enforces the body rule in code rather than leaving it to the operator: a 200 whose body carries any challenge marker, or
which lacks the publisher's own page furniture, fails the build, so a future silent challenge cannot be mistaken for an
empty table of contents.

| Jurisdiction | Version | Documents | Rows | Chars | Seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| us-ca | `2026-10-20-w8-medicaid-ccr-section` | 1 | 4 | 8,201 | 7 |

Version string: a new family, so `2026-10-20-w8-medicaid-ccr-section` on the brief's `2026-10-20-w8-medicaid-<family>`
pattern. It is not the eligibility-manual family (different publisher, class and citation root), and it is not the 18 CCR
income-tax scope's `2026-09-14`, which is a released and therefore immutable version of a different programme's selection.

Verification:

- Coverage `complete: true`, `matched_count: 4`, `missing_from_provisions: []`, `extra_provisions: []`,
  `duplicate_provision_citations: []`, `duplicate_source_citations: []`.
- Uniqueness on the provisions JSONL itself: 4 rows, 4 distinct citation paths, no internal duplicate.
- Uniqueness against every other provisions JSONL under `data/corpus/provisions/us-ca/`: the 28 locked files the scope
  check needed were fetched first (`corpus fetch --path data/corpus/provisions/us-ca`; two unrelated
  `2026-09-13-*-r2026-10-13-hollow-roots.jsonl` files could not be obtained from any source, a pre-existing condition that
  does not touch `us-ca/regulation/10-ccr`), then all 48 other files, 25,784 rows, were scanned: zero collisions. The only
  other CCR scope is `18-ccr` (211 rows, `2026-09-14-income-tax-regulations.jsonl`), a disjoint title. No scope was skipped
  for a collision.
- Body text: the three block rows carry 164, 3,418 and 4,619 characters, 8,201 in total, which matches the section text the
  publisher serves. The one empty body is the `kind: document` root, as in every other official-documents scope. No page is
  image-only, so no row needs `ocr: true` and none was set.
- Source references: the inventory's four items all name the same regular, non-symlink file
  `sources/us-ca/regulation/2026-10-20-w8-medicaid-ccr-section/official-documents/ca-ccr-10-2699.200.html` (23,188 bytes)
  inside the exact scope boundary, with a matching SHA-256; every provision cites that inventory path.
- No manifest, queue row, note or generator holds a local machine path (the guard PRs 897 and 899 add).

One cosmetic effect of the queue rewrite is worth naming for the reviewer. Every queue generator in `scripts/`, this one
included, writes the file with `yaml.safe_dump(..., sort_keys=False, allow_unicode=True, width=120)`. The file was last
written by `scripts/append_w6_health_queue_rows.py`, which leaves long `notes` strings on one line, so this run re-wraps
those strings to 120 columns across the wave-6 rows it did not otherwise touch. The content of those rows is byte-identical
after unwrapping; only the line breaks move, and the next run of any other queue generator would do the same.

## What stays open, and why

- BLOCKED (6 work-order rows, us-ca): the DHCS ACWDL index and the five other `www.dhcs.ca.gov` HTML documents (ACWDL
  23-03, ACWDL 25-14, Program descriptions by FPL Enclosure 3, the non-MAGI asset-limit page, the Former Foster Youth page,
  the Working Disabled Program page). Imperva/Incapsula answers every HTML address a challenge stub to every client tried.
  The 2026-10-06 run found wp-content copies for three other documents; none exists for these. OUTREACH to DHCS for a
  text export or an unchallenged path, unchanged.
- ABSENT (6 states): M-ST-1315 for AK ID ND NE NV SC. The publisher answers and posts no current approved eligibility
  demonstration; the rows stay `needs_review` with tonight's evidence.
- Controller scope question: behavioural-health 1115 approvals for AK and ID, and the New York row, which another agent
  owns.
- SKIPPED for duplicate work: none.

## Code changes

- `scripts/build_medicaid_ca_ccr_section_manifests.py` (new). `uv run ruff check` passes.
- No library function under `src/` was modified. The GitNexus MCP tools are unavailable in this session, so no impact
  analysis was run.

## Tests

`uv sync --extra dev` first, so `uv run pytest` is the worktree's own pytest and not another one on the path, then
`AXIOM_CORPUS_PARTIAL_TESTS=1 uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or
discovery"`. The partial-tests flag is needed because the worktree is sparse: without it the run exits on 68,059 locked
corpus files that are not in this checkout, and without the dev extra it cannot import `axiom_corpus` at all.

- Baseline: 18 failed, 341 passed, 2 skipped, 7,241 deselected. Measured twice: once before the first edit, and again on
  a clean tree (`git stash push --include-untracked` at 393127f8b, then `git stash pop`) so that the whole `FAILED` list
  could be captured instead of a truncated tail.
- Trap met and avoided: the first baseline attempt, run as `uv run pytest` without the dev extra, resolved a different
  pytest that cannot import `axiom_corpus`. It raised `INTERNALERROR ModuleNotFoundError` in `pytest_configure` and still
  exited 0, so a piped run reads as a pass. The second attempt, with the extra but without
  `AXIOM_CORPUS_PARTIAL_TESTS=1`, exited 0 again on `Exit: 68059 locked corpus file(s) are not in this checkout`. Neither
  ran a test. Only the third invocation, and the final runs after `uv sync --extra dev`, are real.
- After: 18 failed, 341 passed, 2 skipped, 7,241 deselected.
- The two `FAILED` lists were compared sorted, line by line, not by count: they are identical. No failure in this run is
  this run's.

The 18 are retained-artifact and locked-corpus tests for unrelated scopes: Armenia ARLIS, two Belgian rulespec promotion
tests, two New York TANF compatibility-scope tests, Wisconsin PIT, Israel OpenLaw, SC Act 110, the AK, CT, MI, MT, ND and
NY SNAP manuals, and four SNAP child-support source tests. They fail because the locked corpus files they replay are
absent from this sparse checkout. None of them reads anything this run changed.

## Rebuild

```bash
cd ~/axiom-corpus-worktrees/w8-medicaid
B=<main checkout>/data/corpus
uv run python scripts/build_medicaid_ca_ccr_section_manifests.py
uv run axiom-corpus-ingest extract-official-documents --base $B \
  --manifest manifests/us-ca-medicaid-ccr-sections.yaml \
  --version 2026-10-20-w8-medicaid-ccr-section --source-as-of 2026-10-20
```

Remaining controller steps: `sign-ingest-manifest` for `us-ca/regulation/2026-10-20-w8-medicaid-ccr-section`, selector,
`validate-release`, publication and activation. Nothing in this run was pushed, signed or published.
