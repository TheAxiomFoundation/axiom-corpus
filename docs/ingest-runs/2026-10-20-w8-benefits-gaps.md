# Wave 8, group `benefits`: WIC Kansas, CHIP Montana and Wyoming, SSI Wyoming and the four territories

Date: 2026-10-20 (America/New_York).
Assignment: the newly reachable benefit-program sources of three programs — WIC `us-ks`, CHIP `us-wy` and `us-mt`,
SSI `us-wy` plus the four territory rows (`us-as`, `us-gu`, `us-pr`, `us-vi`).
Queues: `manifests/wic-agent-queue.yaml`, `manifests/chip-agent-queue.yaml`, `manifests/ssi-agent-queue.yaml`.
Generator: `scripts/update_w8_benefits_queue_rows.py` (every queue-row change of this run; idempotent, text-level, so
every row this run did not touch stays byte-identical).

## Worktree, branch, timing, disk

- Worktree `~/axiom-corpus-worktrees/w8-benefits`, branch `discovery/ingest-w8-benefits` cut from `main` 393127f8b.
  The one extraction wrote to the main checkout's corpus root (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`),
  `--source-as-of 2026-10-20 --expression-date 2026-10-20`; artifacts are unsigned and uncommitted. Nothing was
  signed, locked, pushed to R2 or loaded to Supabase; `manifests/releases/` and `manifests/program-bundles/` are
  untouched. In `~/axiom-corpus` only read-only git commands were run.
- Timing: `started_at` **2026-10-20T18:51:59Z**, `finished_at` **2026-10-20T19:17:33Z**, wall time **25 min 34 s**.
  Measured durations inside that window: Montana ARM 37.79 smoke run (3 rules) 12 s; **Montana ARM 37.79 full
  extraction 12 s** — the only target that produced an extraction, so that is the whole of the per-target extraction
  time; control run with `--include-not-effective` 12 s; baseline test run 151 s; end-of-run test run 77 s. Order of
  work: duplicate-work check, then the runbook and queue rows, then the baseline tests (two false starts — `uv sync`
  was needed in this worktree, then the locked-corpus gate sent the run to the documented
  `AXIOM_CORPUS_PARTIAL_TESTS=1` mode), then the publisher probes, the Montana extraction, the Wyoming and POMS
  verification, and last the queue rows, this note and the end-of-run tests.
- Disk: `df -h /` 3.0 TiB free before and after; the new scope adds 1.3 MB.
- Impact analysis: not run — **the GitNexus MCP tools are not available in this session**. No library function under
  `src/` was changed; the Montana adapter was only invoked.

## Duplicate-work check (repo rule, before any edit)

| check | result |
| --- | --- |
| `gh search prs "wic" --repo TheAxiomFoundation/axiom-corpus --state open --limit 20` | 5 hits (#860, #752, #772, #770, #729); all California LegInfo, Title 52 or HTS work, none a WIC source row |
| `gh search prs "chip" --repo TheAxiomFoundation/axiom-corpus --state open --limit 20` | 3 hits (#636, #867, #841); federal proposal-security sources, a PyMuPDF measurement and an eCFR group-part fix, none a CHIP row |
| `gh search issues "state supplement" --repo TheAxiomFoundation/axiom-corpus --state open` | 1 hit, #139 "Support SSA publication downloads blocked with 403"; unrelated to the SI 01415 question answered here |
| `gh pr list --state open --json number,title,files` (60 open PRs, filtered on the three queue paths) | one PR touches a target file: **#830** edits `manifests/ssi-agent-queue.yaml`, but only the federal 20 CFR 416 row (`appendix_subpart_k_scope`, `2026-10-12-with-appendices-title-20-part-416`). It touches none of the five SSI rows of this run. No PR touches `wic-agent-queue.yaml` or `chip-agent-queue.yaml` |

No row was skipped for duplicate work. #830 and this branch edit disjoint regions of the SSI queue; the controller
should merge them in either order and recheck `status_counts`, which both runs recompute from every row.

## Results by row

| program | row | before | after | outcome |
| --- | --- | --- | --- | --- |
| WIC | `us-ks` | blocked_primary_source | blocked_primary_source | **still blocked**: the manual is on no KDHE static index; the only list endpoint is robots-disallowed |
| CHIP | `us-mt` | blocked_primary_source | **done** | **extracted**: ARM 37.79 (HMK), 30 rules, 39 provision rows |
| CHIP | `us-wy` | blocked_primary_source | **done** | **already held**: M1803 Kid Care CHIP is in a locked scope; no new extraction |
| SSI | `us-wy` | blocked_primary_source | **done** | **already held**: M1804 State Supplemental Payments is in the same locked scope |
| SSI | `us-as` | blocked_primary_source | **done** | **done by POMS finding**: no supplement at all |
| SSI | `us-gu` | blocked_primary_source | **done** | **done by POMS finding**: no supplement at all |
| SSI | `us-pr` | blocked_primary_source | **done** | **done by POMS finding**: no supplement at all |
| SSI | `us-vi` | blocked_primary_source | **done** | **done by POMS finding**: no supplement at all |

Seven of eight rows leave `blocked_primary_source`. One extraction, one new scope.

## Scopes

| jurisdiction | class | version | index | taken | rows | body chars | source MB | s |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| us-mt | regulation | `2026-10-20-w8-chip-hmk-title-37-section-37-79` | 42 | 30 | 39 | 50,898 | 1.08 (69 files) | 12 |

Version string: `2026-10-20-w8-chip-hmk` was passed, of the required form `2026-10-20-w8-<program>-<family>`
(program `chip`, family `hmk`, Montana's own name for the program — the chapter is titled "HEALTHY MONTANA KIDS
(HMK)"). The Montana adapter appends its selection, as it did for the committed `2026-09-14-income-tax-regulations`
scope, so the scope version on disk is `2026-10-20-w8-chip-hmk-title-37-section-37-79`. No other target produced a
scope, so no other version string was needed.

## Publisher access (2026-10-20)

Every probe used TLS verification (never disabled) and no mirror, repost, proxy or archived copy.

**Reachability was judged by body content, never by the status line.** Every body was saved and read — parsed for
title, page furniture, document links and policy text — before any entry was written. A status-only reading would
have been wrong twice here, in both directions: `www.kdhe.ks.gov` serves HTTP **403 with a Cloudflare challenge
body** to the extractor's own clients, and `rules.mt.gov` serves HTTP **200 with an 894-byte application shell**.

Each saved body was also scanned for challenge and stub signatures (`bobcmn`, "Please enable JavaScript", "Just a
moment", `cf-challenge`, `cf_chl_opt`, `/cdn-cgi/l/chk_jschl`, "Checking your browser", "Verifying you are human",
Incapsula, Radware, TSPD, captcha) and against the size bands:

- **No** body of this run fell in the 6-8 KB probable-challenge band. The KDHE challenge bodies this run did receive
  are smaller — **5,490 and 5,893 bytes** — so that band is worth widening to about 5 KB.
- One body under 3 KB: `rules.mt.gov` at **894 bytes**, read as the Esper single-page-application shell and **not
  relied on**. The Montana collections API also answers under 3 KB (1,324 bytes) but is real parsed JSON, not a
  stub, so the small-body band should not be applied to an API response.
- The five large KDHE bodies match `challenge-platform`, which is **not** a challenge: it is Cloudflare's passive
  `/cdn-cgi/challenge-platform/scripts/jsd/main.js` telemetry include, which Cloudflare injects into genuine pages.
  Those bodies carry real KDHE furniture (9-14 `navMainItem` nav entries, titles such as "Policy & Information
  Updates | KDHE, KS") and yielded 583 real document links, and a scan for the markers that do mean an interstitial
  (`cf-challenge`, `cf_chl_opt`, `chk_jschl`, "Checking your browser", "Verifying you are human") matched **0**.

**Which hosts need browser impersonation — tested, not assumed.** A 403 to the Axiom user agent is not by itself
proof of a fingerprint block, because the extractor already retries a 403, 404 or 406 with its own browser user
agent (`_BROWSER_FALLBACK_STATUSES`). That fallback was tested on the same plain `requests` path the extractor uses:

| host | plain Axiom UA | extractor's own browser-UA fallback | curl_cffi `chrome120` |
| --- | --- | --- | --- |
| `www.kdhe.ks.gov` /1149, /903, /1206 | **403**, 5,490-5,893 B, title "Attention Required! \| Cloudflare" / "Just a moment..." | **403**, 5,490 B, same challenge body | **200** with content |
| `ecom.wyo.gov` M1803, M1804 | **200**, 230,051 / 233,949 B, full policy text | not needed | 200, same content |
| `secure.ssa.gov` SI 01415.010 | **200**, 79,638 B, 53 table rows | not needed | 200, same content |
| `rules.mt.gov/api/.../collections` | **200**, 1,324 B, valid JSON | not needed | 200, same content |
| `rules.wyo.gov/Search.aspx?mode=1&AgencyId=48` | **200**, 33,505 B | not needed | 200, same content |

The extractor's built-in browser-UA fallback is therefore **not** enough for KDHE: a Chrome user agent on a
non-Chrome TLS fingerprint is itself a bot signal, exactly as `src/axiom_corpus/corpus/documents.py` documents, and
only the matching `chrome120` TLS profile (`request.browser_impersonation`) clears it. **Only KDHE needs
impersonation**, and even there it clears the gate without yielding the manual. Every finding that actually resolved
a row this run — the Wyoming policy text, the POMS state table and the Montana rule text — was reproduced on the
**plain** extractor path, so **no row of this run depends on impersonation**.

| host | client | status | bytes | finding |
| --- | --- | --- | ---: | --- |
| `www.kdhe.ks.gov/1149/...` | chrome120 | 200 | 124,981 | redirects to `/1149/For-Local-WIC-Agencies`; real page (nav, 11 document links). The plain client and the extractor's browser-UA fallback both get 403 with a Cloudflare challenge body, so only `browser_impersonation` clears the gate |
| `www.kdhe.ks.gov/DocumentCenter/Index/903` | chrome120 | 200 | 103,708 | CivicEngage React shell, `window.folderName` "Policy & Procedure Manual", `window.parentId` 898; **0** `DocumentCenter/View` links |
| `www.kdhe.ks.gov/DocumentCenter/Index/898` | chrome120 | 200 | 103,712 | same shell, "Information for WIC Local Agencies"; 0 document links |
| `www.kdhe.ks.gov/robots.txt` | chrome120 | 200 | 857 | `Disallow: /admin` — the admin-area AJAX binding endpoint that holds the document list is robots-disallowed |
| `www.kdhe.ks.gov/sitemap.xml` | chrome120 | 200 | 234,656 | page URLs and one `/DocumentCenter` home entry; **no document URLs** |
| `rules.mt.gov/gateway/ChapterHome.asp?Chapter=37.79` | chrome120 | 200 | 894 | redirects to `https://rules.mt.gov`; Esper `policy-library-public` SPA shell, no rule text (its bundle names `app.public.staging.esper.com`) |
| `rules.mt.gov/robots.txt` | chrome120 | 200 | 25 | `User-agent: *` / `Disallow:` (nothing disallowed) |
| `rules.mt.gov/api/policy-library-public/collections` | plain Axiom UA and adapter | 200 | 1,324 | the publisher's own index the committed Montana adapter reads; valid JSON, and the collection's own `allowedActions` are `VIEW`, `CAN_VIEW_HISTORICAL_VERSIONS`, `VIEW_NOT_EFFECTIVE`, `DOWNLOAD_SECTIONS`, `DOWNLOAD_COLLECTIONS` — the publisher declares downloading permitted. ARM 37.79 resolves to 6 subchapters and 42 rules |
| `rules.wyo.gov/Search.aspx?mode=1&AgencyId=48` | chrome120 | 200 | 33,580 | agency and program lists empty in the served HTML; filled by `AjaxHandler.ashx?handler=...` |
| `rules.wyo.gov/js/wyScripts.js` | chrome120 | 200 | 38,996 | names the undocumented endpoint set: `GetAllAgencies`, `GetAgencies`, `GetAgencyPrograms`, `Search`, `Search_GetProgramRules`, `GetRuleVersionHTML`, `GetRuleVersionHistory` |
| `rules.wyo.gov/Report.aspx?token=<...>` | chrome120 | 200 | 27,811 | the one GET-addressable document path; needs an application-minted token. The token on `Agencies.aspx` returns a 3-page "Agency Listing" PDF |
| `ecom.wyo.gov/.../m1804-state-supplemental-payments` | plain Axiom UA | 200 | 233,949 | **body read: now serves the policy text** in `div.UtePc` (3,484 chars, the whole M1804 section); 128 navigation sections in the served HTML. No challenge or stub signature |
| `ecom.wyo.gov/.../m1803-kid-care-chip` | plain Axiom UA | 200 | 230,051 | same: `div.UtePc` carries the whole Kid Care CHIP eligibility section (2,767 chars) |
| `secure.ssa.gov/poms.nsf/lnx/0501415010` | plain Axiom UA | 200 | 79,638 | SI 01415.010; body parsed to 53 table rows, 51 of them jurisdictions |
| `secure.ssa.gov/apps10/poms.nsf/subchapterlist!openview&restricttocategory=05014` | chrome120 | 200 | 32,721 | the SI 014 chapter list; body parsed to 32 SI 01415 sections. The first category code tried answered 200 with a body reading "No documents found" — a status-only reading would have recorded a working index |

No publisher needed a certificate: `data/certs/` is untouched and `REQUESTS_CA_BUNDLE` was not set. No TLS
verification was disabled anywhere.

## WIC `us-ks` — still blocked (index found 583, manual chapters taken 0)

The 2026-09-10 and 2026-09-13 probes recorded a Cloudflare 403 and then an empty shell. On 2026-10-20 the 403 is
cleared by the `chrome120` TLS profile, so an access gate is no longer the whole story — but the manual is still not
on an index KDHE serves. The gate itself is narrower than the queue recorded, and narrower than a status-only probe
suggests: the plain extractor client **and** the extractor's own browser-user-agent fallback both still get 403 with
a Cloudflare challenge body (5,490-5,893 bytes), so a future assignment on this host needs
`request: browser_impersonation`, not the built-in fallback.

1. `/1149/For-Local-WIC-Agencies` links the Policy & Procedure Manual to `DocumentCenter/Index/903`.
2. Folders 903 and 898 both answer 200 as the CivicEngage React shell with **zero** `DocumentCenter/View` links. The
   document list comes only from the admin-area `Document_AjaxBinding` endpoint, and `robots.txt` carries
   `Disallow: /admin`. **The endpoint was not requested.** That is a publisher instruction, not a technical wall.
3. `sitemap.xml` lists page URLs only — one `/DocumentCenter` home entry and no document URLs.
4. Every one of the **31** WIC, nutrition and policy pages in that sitemap was read (1 answered 403 under the sweep's
   own rate, the rest 200). Together they link **583 distinct** `DocumentCenter/View` documents, and a scan for
   manual-chapter naming (`ADM`, `CRT`, `CER`, `NSE`, `NUT`, `FIS`, `VEN`, `BF`, `GEN`, `OPS`, `MIS`, `FD`, `ELG`
   followed by a number) matched **0** of them.

Same finding on three dates. The row stays `blocked_primary_source` with `source_kind`
`official_state_agency_manual_no_static_index`, which names the real obstacle; `index_url` now points at folder 903,
the index that is actually empty, instead of the landing page that is not.

**New pointer, not taken.** `/1206/Policy-Information-Updates` **is** a KDHE-own static index: it lists **63** WIC
documents as plain `DocumentCenter/View` links — Policy Memos (P-Memo) FFY 2021 through FFY 2025 and the monthly KS
WIC Update slides and supplements, under year and FFY headings. This is a guidance family, not this row's manual
target, so it was left for a controller assignment and is recorded in `index_families`.

## CHIP `us-mt` — extracted (index 42, taken 30)

The queue recorded Montana blocked because the ARM gateway serves an Esper SPA shell. That is still true of the
gateway URL, and the brief's instruction was to record the row blocked rather than emulate an undocumented vendor
API. **The row is not blocked, and nothing was emulated**: this repository already ships a reviewed Montana adapter,
`extract-montana-admin-rules`, which reads `rules.mt.gov/api/policy-library-public/collections` and is the committed
route behind `us-mt/regulation/2026-09-14-income-tax-regulations-title-42-section-42-15` and the wave-6 ARM 37.78 and
37.80 scopes. Invoking the repo's own adapter is not new emulation, and no library function was changed.

ARM chapter 37.79 is titled "HEALTHY MONTANA KIDS (HMK)" — Montana's separate CHIP. Inventory by family:

| family | found | taken |
| --- | ---: | ---: |
| subchapter 37.79.1 General Provisions | 11 | 11 |
| subchapter 37.79.2 Eligibility | 6 | 5 |
| subchapter 37.79.3 Benefits | 15 | 5 |
| subchapter 37.79.5 Enrollment Provisions | 4 | 3 |
| subchapter 37.79.6 Services and Provider Requirements | 5 | 5 |
| subchapter 37.79.8 Hearing and Appeal Procedures | 1 | 1 |
| total | **42** | **30** |

The 12 not taken are repealed or otherwise not-effective ARM entries, which the adapter excludes unless
`--include-not-effective` is passed; a control run with that flag returned 42 rules and 51 provision rows and
confirmed the 42/30 split. The 30 taken rules are the chapter's current text.

## CHIP `us-wy` and SSI `us-wy` — already held, no new extraction

Both rows named a publisher that does not serve an index. `rules.wyo.gov` is now characterised exactly: its agency
list, its search and its rule text all come from `AjaxHandler.ashx?handler=...`, an undocumented vendor endpoint set,
and its one GET-addressable document path needs a token the application mints. **Not emulated** — and unlike Montana
this repository ships no Wyoming rules adapter, so there was no sanctioned route to use.

The documents exist elsewhere, published by the agency that writes them. The Wyoming Department of Health's
Eligibility Online Manual at `ecom.wyo.gov` now serves its policy text in the HTML (`div.UtePc`); the 2026-09-11
finding of a script-rendered Google Drive embed with no document URL is **obsolete**. Its navigation lists **128**
sections today against the 107 the queue recorded.

The decisive finding is that the corpus **already holds both sections**. The Medicaid queue took the whole EOM on
2026-09-15 as the locked scope `us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure`
(`manifests/us-wy-medicaid-eligibility-manual.yaml`, 121 documents, 458 provision rows, 124 locked files) with the
same `div.UtePc` selector derived independently here:

| row | citation path | block rows | body chars |
| --- | --- | ---: | ---: |
| CHIP | `us-wy/manual/wdh/medicaid/m1800-other-programs-m1803-kid-care-chip` | 4 | 2,556 |
| SSI | `us-wy/manual/wdh/medicaid/m1800-other-programs-m1804-state-supplemental-payments` | 4 | 3,254 |

Re-extraction was **refused**: it would have produced duplicate citation paths for text the corpus already serves.
Both rows are recorded `done` with `source_kind` `official_state_agency_manual_already_held` and a pointer to that
scope, the shape the SSI queue already uses for rows whose governing text sits in another family.

The held text was verified against the live pages on 2026-10-20: the corpus text is a **strict subset** of what the
publisher serves today — every corpus token is on the page, so nothing is stale.

**Finding for the controller (not this run's scope).** Two live tokens per section are absent from the corpus: the
field labels (`Purpose:`, `Reference:`, `Clarifying Information:`, `Worker Responsibilities:`) and, substantively,
the **Purpose sentence**. M1804's "This section will assist in showing the SDX process of how the State Supplemental
Payment is issued." and M1803's "This section will assist in determining Kid Care CHIP eligibility for children ages
0-18 years." are in neither scope's four block rows, which begin at "Current Policy Effective Date:". The policy
substance (the numbered POL requirements, the references, the clarifying information and the worker responsibilities)
is complete. This is a fidelity gap in the 2026-09-15 Medicaid scope, not something these rows introduced, and it is
worth a successor build of that scope rather than a change here.

## SSI `us-as`, `us-gu`, `us-pr`, `us-vi` — done by POMS finding

All four rows named the POMS subchapter list. The question the brief set was whether each territory pays an optional
state supplement at all. POMS SI 01415 answers it on SSA's own index:

- The SI 014 chapter list (`restricttocategory=05014`) lists **32** SI 01415 sections — SI 01415.000, .001, .010,
  .024 and .031 through .058 — and **names no territory**. A case-insensitive scan of that list for `samoa`, `guam`,
  `puerto`, `virgin islands` and `mariana` matched nothing.
- The SI 01415.010 state table ("Administration of State Supplementary Programs", fetched 2026-10-20) carries
  exactly **51 jurisdiction rows**: the 50 States and the District of Columbia. There is **no American Samoa, Guam,
  Puerto Rico, Virgin Islands or Northern Mariana Islands row**. (The only table rows matching "Virgin" are
  "Virginia" and "West Virginia".)

So none of the four pays a supplement, optional or mandatory, and no territory publishes a supplement document to
ingest. With 42 U.S.C. 1382c(e) and POMS SI 00501.410 / SI 00501.415, which the rows already cited for the title XVI
definition of the United States, the rows are settled. Each is recorded `done` with `source_kind`
`ssa_poms_section`, `administration: N` and a pointer to `us/manual/ssa/poms/si/01415.010` in the held scope
`us/manual/2026-09-10-ssi-poms-si` (`manifests/us-ssa-poms-si-2026-09-10.yaml`) — the resolution the `us-mp` row
already uses. `program_applicability: not_applicable` is kept, and the notes' stand-in clause ("recorded as
blocked_primary_source because the queue schema has no not-applicable status") is dropped, since the status is no
longer a stand-in. Nothing was fetched into the corpus for these rows.

## Reviewer judgments

1. **Montana: ran the repo's adapter instead of recording a block.** The brief said to record the row blocked if the
   text is only reachable through an undocumented vendor API, rather than emulate the application. The adapter that
   reads that API is already committed and already has merged scopes behind it, so using it is the sanctioned route
   and not new emulation. Recording a block would have been wrong. No library function was changed.
2. **Wyoming: did not emulate `AjaxHandler.ashx`.** The same reasoning cuts the other way: no Wyoming adapter exists,
   so the brief's rule applies in full. The rows were resolved from the agency's own manual instead.
3. **Wyoming: refused to re-extract held text.** The brief asked for the manual to be taken if the page now serves
   text. It does, and the corpus already holds it. Taking it again would have duplicated citation paths, which the
   brief's own uniqueness rule forbids, so the rows point at the held scope.
4. **Wyoming: did not take the other 127 EOM sections.** The brief's "take the manual" is read as the row's target —
   the SSP section for SSI, the Kid Care CHIP section for CHIP. The other sections are other-program families
   (Medicaid, MSP, family and children's programs) owned by other queues, and the whole manual is held already.
5. **Kansas: did not request the robots-disallowed endpoint.** `Disallow: /admin` covers the one endpoint that would
   list the manual. The row stays blocked on that ground, which is firmer than the 2026-09-10 Cloudflare finding.
6. **Kansas: did not ingest the policy-memoranda index.** 63 documents are genuinely reachable on a KDHE static
   index, but they are a guidance family, not this row's `document_class: manual` target. Recorded as a pointer.
7. **Territories: flipped to `done` rather than leaving `blocked_primary_source`.** The brief and the `us-mp`
   precedent both call for `done` once POMS settles the question, and `program_applicability: not_applicable` already
   carries the not-applicable fact.
8. **Did not use `extract-official-documents` for Montana.** The brief named that command, but the Montana chapter has
   no per-rule fetchable document URL; the ARM adapter is the repo's route for ARM and emits the same artifact set
   (sources, inventory, provisions, coverage).
9. **`index_document_count` counts rules, not provision rows.** 42 for Montana, matching the queue's convention of
   counting documents an index lists rather than extracted rows. 128 for the Wyoming rows is the EOM navigation count.
10. **Judged every host by body content, not by its status line**, and kept each body for the scan recorded above.
    That mattered in both directions here: KDHE's 403 bodies are Cloudflare challenges rather than plain denials, and
    `rules.mt.gov`'s 200 is an 894-byte shell. It also caught a probe of my own — the first POMS category code I
    tried answered HTTP 200 with a body reading "No documents found", which a status-only reading would have recorded
    as a working index; the correct code (`05014`) was found by reading that body.
11. **Treated `challenge-platform` as inconclusive, not as a challenge.** Cloudflare injects that telemetry script
    into genuine pages, so the five large KDHE bodies were cleared by their own furniture, titles and 583 extracted
    document links plus a zero match on the markers that do mean an interstitial. Reporting them as challenges would
    have been a false negative on a reachable host.
12. **Tested the extractor's own 403 fallback instead of assuming a fingerprint block.** A 403 to the Axiom user
    agent is not proof of one. On KDHE the fallback is genuinely insufficient (403 with a challenge body either way),
    so `request.browser_impersonation` is the documented route — but the test also showed that **no row resolved in
    this run needs it**: Wyoming's policy text, the POMS table and the Montana rule text all come back on the plain
    extractor path, which is the stronger basis for the rows and avoids an unnecessary manifest option.

## Checks

- Coverage of the new scope: `complete: true`, `missing_from_provisions: []`, `extra_provisions: []`,
  `duplicate_provision_citations: []`, `duplicate_source_citations: []`, `matched_count` 39 = `provision_count` 39 =
  `source_count` 39, `error_count` 0.
- Uniqueness on the provisions JSONL itself: 39 rows, 39 distinct citation paths.
- Uniqueness against **every other** provisions JSONL under `data/corpus/provisions/us-mt/` (11 files): the only
  shared paths are the two ancestors `us-mt/regulation` (collection) and `us-mt/regulation/title-37` (title), which
  the committed ARM 37.78, 37.80 and 42.15 scopes already share with each other. No chapter-, subchapter- or
  rule-level path collides, and **no ARM 37.79 path exists in any other scope**, so nothing was skipped.
- Body text: all **30** rule rows have non-empty bodies (50,898 body characters in total). The 9 empty bodies are the
  container rows (1 collection, 1 title, 1 chapter, 6 subchapters), as in every committed ARM and EOM scope. No
  document is image-only, so no `ocr: true` was needed.
- `content-check us-mt/regulation/2026-10-20-w8-chip-hmk-title-37-section-37-79`: "no locked scope ... matches" — the
  command reads locked scopes only, and these artifacts are deliberately unsigned and unlocked. The controller should
  run it after locking.
- `status_counts` reconciled from every row of all three queues: WIC 23 + 35 = 58 rows; CHIP 93 + 8 + 16 = 117 rows;
  SSI 30 + 1 + 28 = 59 rows.
- Queue diff confined to the 8 intended rows: a row-by-row comparison against `HEAD` shows exactly `us-ks` in WIC,
  `us-mt` and `us-wy` in CHIP and `us-as`, `us-gu`, `us-pr`, `us-vi`, `us-wy` in SSI changed; row counts unchanged;
  all three files still parse. A second run of the generator is byte-identical.
- `uv run ruff check scripts/update_w8_benefits_queue_rows.py`: "All checks passed!".
- Tests, before the first edit and again at the end:
  `AXIOM_CORPUS_PARTIAL_TESTS=1 uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`.
  Baseline **18 failed, 341 passed, 2 skipped** (151 s); end of run **18 failed, 341 passed, 2 skipped**. The same 18
  failures, every one a missing `data/corpus` artifact of another scope this partial checkout does not hold (Armenia
  ARLIS, BE promotion, Wisconsin pit-west replay, Israel OpenLaw, SC act 110 successor, AK/CT/MI/MT/ND/NY SNAP
  manuals, SNAP child-support CA/DE), the known set of the wave-6 and wave-7 notes. **No new failure.** The run
  without `AXIOM_CORPUS_PARTIAL_TESTS=1` stops at the locked-corpus gate (68,059 locked files absent) before
  collecting, which is why the documented partial mode is used for both ends. **`uv sync --extra dev` is
  required in this worktree first**: without it `uv run pytest` silently resolved a different pytest (an
  Anaconda one) and died with `ModuleNotFoundError: No module named 'axiom_corpus'` in `pytest_configure`,
  before collecting a single test — and it exits 0, so a piped run looks like a pass. The two runs compared
  here are **sorted `FAILED` lists**, not counts: `comm` over the two sorted lists reports no line on either
  side, so the sets are identical and not merely equal in size.
- `changelog.d/w8-benefits.added.md` added.

## Controller

- Selector addition: `us-mt/regulation/2026-10-20-w8-chip-hmk-title-37-section-37-79` (unsigned, uncommitted, on the
  controller's disk).
- Shared containers: the new scope emits `us-mt/regulation` and `us-mt/regulation/title-37`, which the ARM 37.78,
  37.80 and 42.15 scopes also emit. Fold as the earlier ARM consolidations did — the wave-6 consolidated scope
  `...-r2026-10-07-w6-37-78-37-80-sans-420-consolidated` is the precedent, and ARM 37.79 is the chapter between the
  two it already carries.
- No new release selector, no signing, no push, no Supabase load.
- Open follow-ups: (a) the dropped Purpose paragraph in the 2026-09-15 Wyoming EOM scope, worth a successor build;
  (b) the 63 KDHE WIC policy memoranda on `/1206/Policy-Information-Updates`, a guidance-family assignment;
  (c) PR #830 also edits `ssi-agent-queue.yaml` in a disjoint region — recheck `status_counts` after both merge.

## Rebuild

```bash
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
uv run --extra dev axiom-corpus-ingest extract-montana-admin-rules --base $B \
  --version 2026-10-20-w8-chip-hmk --only-title 37 --only-section 37.79 \
  --source-as-of 2026-10-20 --expression-date 2026-10-20 --workers 4
uv run --extra dev python scripts/update_w8_benefits_queue_rows.py
```
