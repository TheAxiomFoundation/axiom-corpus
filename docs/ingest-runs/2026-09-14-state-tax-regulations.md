# State income-tax regulations: 42 income-tax jurisdictions (closure gap R01)

Date: 2026-09-14
Work order: needs-closure gap R01 of `docs/coverage/needs-closure-2026-09-11/tax.md` ("no state's
income-tax regulations are selected anywhere: 42 of 42 income-tax states"). One `us-xx/regulation`
scope per jurisdiction, version `2026-09-14-income-tax-regulations` (dedicated adapters append their
run-id suffix), document class `regulation`, `--source-as-of 2026-09-14`, expression date the
publisher's stated currency date where printed and otherwise 2026-09-14.
Branch `discovery/ingest-state-tax-regulations` in the sparse worktree
`~/axiom-corpus-worktrees/tax-regs` (`data/corpus/` excluded, never symlinked; reset to `origin/main`
5c2505ec6 after the first session died on an API limit, its two extracted scopes kept). Every
extraction wrote to the main checkout's corpus root (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`);
artifacts are unsigned and uncommitted there. Timing: publisher probes 2026-09-13 21:30 to 2026-09-14
02:30 EDT (two networks: the laptop's Wi-Fi flapped once mid-run, nothing was lost); extractions
2026-09-14 02:30 to 09:40 EDT, per-scope seconds below. Disk: 32 GB free at start, never near the
5 GB stop line (the 37 source directories total about 420 MB, the Hawaii and Georgia PDFs 67 MB and
13 MB of that). Impact analysis: GitNexus MCP tools were not available; every changed library
function's callers were read directly (listed under Code changes).

Result: **37 of 42 jurisdictions extracted, all coverage `complete: true`, 0 missing, 0 extra,
0 duplicate citation paths** (7,349 provision rows). Five jurisdictions are not extracted: DC, NJ
and AR because the official publisher serves no stable document (postback-only, vendor-only, or
browser-rendered only), DE because the Administrative Code has no income-tax title, UT because the
publisher's JavaScript application's file ids could not be discovered without a browser. Three
scopes (MD, OH, OR) carry adapter root-container rows already carried by released scopes and need
consolidation by the controller; the draft selector validates with exactly those three errors.

## Method

Every jurisdiction was probed once with the extractor's own plain client (the
`OFFICIAL_DOCUMENT_USER_AGENT` `requests` session, certifi plus `data/certs/`) against the state's
administrative-code publisher or revenue department; browser impersonation (`curl_cffi` chrome120)
was tried only where the plain probe met a challenge page. No mirror, proxy, archived copy, Cornell,
Justia, Casetext or LexisNexis page was used; `verify_tls` was never disabled. Manifests are built by
`scripts/build_us_state_income_tax_regulation_manifests.py` (static specifications for one-file-per-
chapter publishers; live discovery against the publisher's index for one-file-per-section publishers
and JSON APIs; `--cache-dir` makes a rebuild offline). Two families:

- **Dedicated adapters** (existing code): Illinois (`extract-illinois-admin-code`, new
  `--only-part`), Maryland (`extract-maryland-comar`), Montana (`extract-montana-admin-rules`),
  New York (`extract-nycrr-parts`), Ohio (`extract-ohio-administrative-code`), Oregon
  (`extract-oregon-administrative-rules`), Pennsylvania and Virginia (`extract-pennsylvania-code`,
  `extract-virginia-vac`, comma-separated `--only-chapter`). Each has a pointer manifest
  `manifests/us-xx-income-tax-regulations.yaml` recording the command actually run.
- **Manifest-driven official documents** (`extract-official-documents`) for the other 29:
  `labeled_sections` on the publisher's section labels (PDF, HTML, DOCX), `records` for the
  Oklahoma JSON API, one file per rule where the publisher prints tables of contents that repeat
  every heading (Alabama, North Carolina, Kentucky, Kansas, California, Massachusetts, Rhode Island,
  Maine, Minnesota, New Mexico, Iowa, North Dakota, Wisconsin, Vermont, West Virginia).

## Publisher access (2026-09-13/14)

| Host | Plain client | Notes |
| --- | --- | --- |
| admincode.legislature.state.al.us | 200 | JavaScript app over persisted GraphQL; `/api/chapter/810-3-<n>` and `/api/rule/<id>` serve PDFs |
| apps.azsos.gov | 403 Cloudflare | PDF served to browser impersonation (`browser_impersonation: true`) |
| govt.westlaw.com (calregs, nycrr) | 200 | cookie-bearing sessions get a browser-check interstitial after the first page; NYCRR adapter's bh cookies / `fresh_session` |
| sos.state.co.us CCR | 200 | rule PDF via GenerateRulePdf |
| eregulations.ct.gov | 200 | F5/TSPD markers in the page, full content served |
| dcregs.dc.gov | 200 | rule text only through ASP.NET `__doPostBack` (durable; same as 2026-09-13 re-probe) |
| regulations.delaware.gov API | 200 | title list has no income-tax title |
| rules.sos.ga.gov | 200 | rule pages are JS-rendered (session POST); Department 560 PDF download serves |
| files.hawaii.gov, tax.hawaii.gov | 200 | DOTAX HAR compilation PDF |
| legis.iowa.gov, adminrules.idaho.gov, ndlegis.gov, docs.legis.wisconsin.gov, revisor.mn.gov, scstatehouse.gov, sos.mo.gov, sos.ms.gov, doa.la.gov, maine.gov, mass.gov, apps.legislature.ky.gov, revenue.nebraska.gov, srca.nm.gov, rules.sos.ri.gov, tax.vermont.gov, ars.apps.lara.state.mi.us, apps.sos.wv.gov, secure.sos.state.or.us, rules.mt.gov, codes.ohio.gov, pacodeandbulletin.gov, law.lis.virginia.gov | 200 | content to the plain client (revisor.mn.gov rate-limits bursts with 429; mass.gov regulation pages fetched with impersonation as the July DTA runs) |
| ftp.ilga.gov (JCAR) | TLS chain incomplete | leaf issued by Sectigo Public Server Authentication CA OV R40 without the intermediate; intermediate fetched from the leaf's AIA URL and committed as `data/certs/sectigo-public-server-authentication-ca-ov-r40.pem` (`REQUESTS_CA_BUNDLE`) |
| iar.iga.in.gov + drxya2s1hkmtl.cloudfront.net/api | 200 / 403 | the General Assembly's own API distribution (referenced from the site bundle) answers the plain client 403 and browser impersonation with the article JSON |
| rules.ks.gov API | 200 | policy-library-public collections/sections/policies (same vendor as rules.mt.gov) |
| rules.ok.gov API (tecuity) | 200 | GetSegmentsByChapterNum served plainly today |
| rules.nebraska.gov | SSLCertVerificationError | department copy used instead |
| codeofarrules.arkansas.gov | 200 shell | rule text browser-rendered only; tree endpoints empty below title; curl_cffi chain failure |
| nj.gov/oal | 200 | N.J.A.C. text only via LexisNexis |
| adminrules.utah.gov | 200 shell | public API argument shapes undiscoverable without the browser |
| github.com maryland-dsd/law-xml-codified | 200 | COMAR XML publication 2026-09-11 |

## Per-jurisdiction results

Seconds are wall-clock extraction time; "rows" is every provision row in the scope (documents,
containers and their children); coverage was `complete: true` with 0 missing / 0 extra / 0 duplicate
citation paths for every scope listed.

| Jurisdiction | Publisher and document | Method | s | Docs | Section rows | Rows | Largest body |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| us-al | LSA Administrative Code, chapter 810-3 rules (80 chapters, 268 rules) | official-documents, one rule PDF each, page rows | 48 | 268 | 504 pages | 772 | 2,947 |
| us-az | SOS A.A.C. 15-2 chapter PDF | labeled_sections (bold R15-2X-NNN), impersonation | 3 | 1 | 105 | 106 | 11,372 |
| us-ca | OAL CCR 18 div. 3 ch. 2.5, 53 live sections of 448 listed | one Westlaw document each, `html_text_selector`, `fresh_session` | 129 | 53 | 158 blocks | 211 | 35,361 |
| us-co | SOS 1 CCR 201-2 rule PDF | labeled_sections (bold Rule 39-22-...) | 6 | 1 | 105 | 106 | 101,824 |
| us-ct | eRegulations Title 12 "INCOME TAX" subject matter (HTML) | labeled_sections, TOC dropped | 2 | 1 | 186 | 187 | 20,444 |
| us-ga | SOS Department 560 PDF, chapter 560-7 window (pp. 389-822) | labeled_sections | 24 | 1 | 129 | 130 | 95,924 |
| us-hi | DOTAX HAR 18-235 compilation PDF (pp. 7-158) | label-only bold headings | 13 | 1 | 137 | 138 | 51,523 |
| us-ia | LSA IAC 701 chapters 300-308 PDFs | labeled_sections | 8 | 9 | 209 | 218 | 41,093 |
| us-id | OARC IDAPA 35.01.01 PDF | label-only headings | 6 | 1 | 176 | 177 | 29,196 |
| us-il | JCAR 86 Ill. Adm. Code Part 100 | `extract-illinois-admin-code --only-title 86 --only-part 100` | 10 | 1 part | 195 | 200 | 55,387 |
| us-in | IAR 45 IAC 3.1 article JSON | json_html_field + `html_text_selector`, impersonation | 3 | 1 | 171 | 172 | 26,850 |
| us-ks | SOS rules.ks.gov K.A.R. 92-12 (71 effective of 130) | one accessible-HTML document each | 13 | 71 | 71 blocks | 142 | 8,449 |
| us-ky | LRC 103 KAR ch. 15/17/18/19 (24 current of 70) | one regulation PDF each, Section rows | 3 | 24 | 106 | 130 | 4,938 |
| us-la | OSR LAC 61:I chapter 13 (Title 61 vol. 1 DOCX) | labeled_sections between chapter headings | 2 | 1 | 11 | 12 | 11,397 |
| us-ma | DOR 830 CMR 62/62B (17 regulations of 32 entries) | one regulation page each, numbered subsections | 45 | 17 | 126 + 19 blocks | 162 | 32,996 |
| us-md | DSD COMAR 03.04 (publication 2026-09-11) | `extract-maryland-comar --only-title 03 --only-subtitle 04` | (agent 1) | 15 chapters | 91 regulations | 109 | 24,733 |
| us-me | MRS rules 803-825 individual family (7 of 38) | one rule PDF each, bold .NN headings | 4 | 7 | 64 | 71 | 16,247 |
| us-mi | OAHR ARS R 206.1-206.33 rule set PDF | labeled_sections | 1 | 1 | 32 | 33 | 6,365 |
| us-mn | Revisor Minnesota Rules 8001/8002/8007/8038/8050/8092/8093 (7 of 43) | full-chapter HTML, labeled_sections | 2 | 7 | 20 | 27 | 18,656 |
| us-mo | SOS 12 CSR 10-2 chapter PDF | labeled_sections from page 4 | 5 | 1 | 61 | 62 | 74,549 |
| us-ms | SOS Admin. Code Title 35 Part III PDF | chapter-level labeled_sections | 2 | 1 | 95 | 96 | 327,617 |
| us-mt | SOS ARM 42.15 | `extract-montana-admin-rules --only-title 42 --only-section 42.15` | 9 | 9 subchapters | 50 rules | 62 | 4,826 |
| us-nc | OAH 17 NCAC 06 (218 rule PDFs) | one rule PDF each, page rows | 27 | 218 | 219 pages | 437 | 4,943 |
| us-nd | Legislative Council NDAC 81-03 individual chapters (7 of 25) | labeled_sections | 2 | 7 | 43 | 50 | 6,471 |
| us-ne | DOR Regulations Chapter 22 (HTML) | labeled_sections (REG-22-NNN) | 1 | 1 | 15 | 16 | 21,899 |
| us-nm | SRCA 3.3 NMAC parts (20 of 21) | labeled_sections | 2 | 20 | 269 | 289 | 21,487 |
| us-ny | DOS 20 NYCRR ch. II subch. A (44 current parts of 82) | `extract-nycrr-parts` | 471 | 44 parts, 46 documents | 228 sections + nested | 2,015 | 108,526 |
| us-oh | codes.ohio.gov OAC 5703-7 | `extract-ohio-administrative-code --only-agency 5703 --only-chapter 5703-7` | (agent 1) | 1 chapter | 14 rules | 17 | 5,999 |
| us-ok | OAR rules API OAC 710:50 | `records` (revoked/reserved excluded) | 2 | 1 | 172 + 2 appendices | 175 | 15,695 |
| us-or | OARD OAR 150-316 | `extract-oregon-administrative-rules --only-chapter 150 --only-division 316` | 10 | 1 division | 145 rules | 148 | 23,942 |
| us-pa | LRB 61 Pa. Code chapters 101-125 | `extract-pennsylvania-code --only-title 61 --only-chapter 101,...,125` | 2 | 13 chapters | 166 | 181 | 49,724 |
| us-ri | DOS 280-RICR-20-55 parts (13 of 15) | one part PDF each, labeled_sections | 4 | 13 | 100 | 113 | 7,978 |
| us-sc | LSA Code of Regulations Chapter 117 PDF | labeled_sections | 3 | 1 | 290 | 291 | 85,648 |
| us-va | Virginia Law Portal 23VAC10-110 and 10-140 | `extract-virginia-vac --only-title 23 --only-agency 10 --only-chapter 110,140` | 11 | 2 chapters | 72 | 77 | 9,514 |
| us-vt | Department of Taxes regulations 1.5811(21)(B)(ii), 1.5811(11)(A)(i) | page rows | 3 | 2 | 12 pages | 14 | 3,061 |
| us-wi | LRB Tax 2 and Tax 3 PDFs | labeled_sections | 5 | 2 | 64 | 66 | 112,676 |
| us-wv | SOS CSR 110-21, 21A, 21B, 21C, 21G, 21H | `ocr: true`, page rows | 63 | 6 | 49 pages | 55 | 4,124 |

Not extracted (queue rows record the evidence):

| Jurisdiction | Status | Evidence |
| --- | --- | --- |
| us-dc | blocked_primary_source | dcregs.dc.gov RuleList for 9-1 (HTTP 200, 196 KB, plain and impersonated) lists 22 sections whose text and files open only through `__doPostBack`; no GET URL |
| us-nj | blocked_primary_source | OAL public-access page (HTTP 200): the N.J.A.C. is published online only by LexisNexis; nj.gov posts no N.J.A.C. 18:35 text |
| us-de | needs_review (absent) | `api/AdminCode/titles` (HTTP 200) lists titles 1-29 with no revenue/finance title; the Division of Revenue issues Technical Information Memoranda, not codified regulations |
| us-ar | blocked_primary_source | codeofarrules.arkansas.gov (official since 2025-01-01) returns the page shell for `/Rules/Rule?levelType=PART&id=26-33-261-941-0-0` (HTTP 200, 13 KB, no text); tree endpoints return `[]` below title; DFA's rules page (HTTP 520 on the first probe, 200 later) links no income-tax rule PDF |
| us-ut | needs_review | adminrules.utah.gov JavaScript app; `/api/public/rule/{a}/{b}/{c}`, `ruleversioninfo/{id}`, `searchRuleDataTotal/{q}/{page}` answer 400/204/empty rule lists for every argument shape tried; the current-file uuid the July R986 manifest carried is only exposed in the browser |

## Collisions and consolidation

Every new scope's citation paths were compared with every scope of the same jurisdiction in
`manifests/releases/us-rulespec-2026-09-13-federal-and-plans-union.json` and with every other scope
on disk for that jurisdiction (script in the run's scratch, result also visible in
`validate-release` on the draft selector):

| Scope | Shared rows | With | Resolution |
| --- | --- | --- | --- |
| `us-md/regulation/2026-09-14-income-tax-regulations-publication-2026-09-11-title-03-subtitle-04` | `us-md/regulation` (1 root collection row) | released `2026-09-10-ssi-state-supplement-...-chapters-06-07`, and the pending TCA and chapter-06/07 scopes | adapter emits the root by design (no suppression option); **needs consolidation by the controller** (`scripts/consolidate_release_scopes.py`, as the 2026-09-11 Ohio/Maryland pass). Title-03 and subtitle-04 rows are unique. |
| `us-oh/regulation/2026-09-14-income-tax-regulations-agency-5703-chapter-5703-7` | `us-oh/regulation` (1) | released `2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated` | same; agency-5703 and chapter rows are unique |
| `us-or/regulation/2026-09-14-income-tax-regulations-chapter-150-division-316` | `us-or/regulation` (1) | released `2026-09-10-tanf-state-policy-manual-chapter-461` | same; chapter-150 and division rows are unique |

All 34 other scopes share no citation path with any released or on-disk scope. Colorado's
official-documents scope carries no `us-co/regulation` root; Pennsylvania, Virginia, Illinois and
Montana emit adapter roots, but no released scope of those jurisdictions carries them.

## Decisions

- Whole-chapter bodies are split into section rows everywhere the publisher prints section labels;
  where the publisher prints one file per rule (AL, NC, KY, KS, CA, MA, ME, RI) the rule is the row
  (page or block children). Mississippi's Part III is published with chapter-level numbering
  (35.III.<subpart>.<chapter>) and section numbers that repeat across chapters; the 95 chapter rows
  stand, with the individual income chapter 35.III.12.01 as one 327 kB row (recorded; a second pass
  with page windows can split it).
- Repealed and revoked numbers are taken where the publisher prints them as rule text ("Repealed."
  stubs in GA, AZ, CO) and excluded where the publisher lists them without text (KS revoked, OK
  revoked/reserved, NY repealed parts, CA repealed/renumbered stubs, MN fully repealed chapters, NM
  expired part 31, KY expired/withdrawn regulations).
- Scope boundaries: individual income tax chapters plus withholding where it is inside the same
  income-tax chapter or agency family (IA 307, ND 81-03-03.x, NY parts 171-178, VA 10-140, ME 803);
  corporate chapters were left out (IA none, ND 81-03-05.x, KY 103 KAR 16, MN 8003/8017-8035, ME
  801/808/810). Oregon divisions 314 and 315 and Colorado 1 CCR 201-1 (procedure) are follow-ups.
- The Colorado CCR adapter was not used: its section parser (built for the 9/10 CCR volume format)
  discovers 1 CCR 201-2 but yields no provisions for `Rule 39-22-xxx` headings; the official-
  documents extractor reads the same publisher PDF.
- The Alabama and Kentucky HTML pages print provision text in `span`/`div` containers the extractor
  did not read; Kentucky uses the LRC's per-regulation PDFs, Alabama the LSA's per-rule PDFs.
  Indiana's article HTML has the same shape and is the reason for the new `html_text_selector`
  option (also used for the Westlaw CCR pages).
- Agent 1's Maryland session also wrote an unrelated consolidated artifact
  `us-md/regulation/2026-09-10-ssi-state-supplement-...-r2026-09-14-chapter-03-consolidated` (58
  rows) to the shared base; it is not part of this work order and is not in the selector draft.

## Code changes

Library changes (callers read directly; GitNexus was unavailable):

- `illinois_admin_code.py` + `cli.py`: `--only-part` filter (`_normal_part_numbers`,
  `_entry_part_number`; callers: `extract_illinois_admin_code`, `_cmd_extract_illinois_admin_code`).
- `pennsylvania_code.py`, `virginia_vac.py`: `_matches_selector` accepts comma-separated chapter
  selectors (callers: the two `extract_*` functions); the VA run id tokenizes the comma.
- `nycrr.py::_part_child_citation_path`: repealed ranges ("s 101.5 -- 101.7 (Repealed)") get a range
  citation (`101/5-7`); the nested-provision loop in `extract_nycrr_parts` skips a second nested
  paragraph whose path was already emitted (Westlaw prints alpha "(i)" and roman "(i)" alike; the
  section row keeps the full text). Only caller: `extract_nycrr_parts`.
- `documents.py`: `_request_headers_from_config` adds a `Cookie` header from `request.cookies`
  (caller: `_download_document`); `_download_document` honours `request.fresh_session`;
  `_html_text_nodes` backs the default and labeled HTML block loops and honours
  `extraction.html_text_selector` (callers: `_extract_html_blocks`,
  `_extract_labeled_html_section_blocks`). Default behaviour is unchanged when the options are absent.
- `data/certs/sectigo-public-server-authentication-ca-ov-r40.pem` (publisher intermediate for
  ftp.ilga.gov, from the leaf's AIA URL), added with `git add -f`.
- Tests: `tests/test_income_tax_regulation_request_options.py` (cookies header, NYCRR range path,
  `html_text_selector`), plus agent 1's tests for the IL/PA/VA filters.

## Verification

- `uv run ruff check .`: passes.
- `uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or official_documents
  or discovery or tax or regulation"`: 539 passed, 2 skipped, 25 failed. Every failure reads other
  scopes' `data/corpus` artifacts the sparse checkout does not contain (`FileNotFoundError` on AK,
  CT, MI, MT, ND, NY SNAP manuals, NM and NY SNAP regulations, NY TANF, NC statute, MA DTA, BE, IL,
  AM, NZ scopes; `test_sc_act110_successor` KeyError and `test_rulespec_be_source_promotion` assert
  on the same missing artifacts). None touches the changed modules' new behaviour; the four new tests
  and the IL/PA/VA adapter tests pass.
- Coverage: every scope `complete: true`, 0 missing, 0 extra, 0 duplicates; every document row has
  child rows (sections, pages or blocks); no body above 200k characters except Mississippi's
  35.III.12.01 (327,617, recorded above).
- Source files: every inventory item names a regular file under its own
  `sources/<jur>/regulation/<version>/` tree; stale files from earlier pattern passes were removed
  so the trees hold only inventoried files (adapter-native index files aside).
- Queue rows: 42 new rows in `manifests/tax-agent-queue.yaml` (37 `done`, 3
  `blocked_primary_source`, 2 `needs_review`), each verified against the coverage JSON and manifest
  on disk (version, `taken_count` = manifest documents/parts); `status_counts` updated.
- `validate-release --ignore-r2-missing` on `docs/ingest-runs/2026-09-14-state-tax-regulations.selector.json`
  (the 2026-09-13 federal-and-plans union plus the 37 scopes, 798 scopes): `ok: false` with exactly
  3 `duplicate_release_citation` errors (the MD/OH/OR root rows above) and the 546 pre-existing
  warnings.

## Controller

Selector additions (artifacts unsigned, on the controller's disk under
`/Users/pavelmakarchuk/axiom-corpus/data/corpus`, not committed). The three starred scopes need
their root row consolidated with the released scope before the cut.

| jurisdiction | document_class | version |
| --- | --- | --- |
| us-al | regulation | 2026-09-14-income-tax-regulations |
| us-az | regulation | 2026-09-14-income-tax-regulations |
| us-ca | regulation | 2026-09-14-income-tax-regulations |
| us-co | regulation | 2026-09-14-income-tax-regulations |
| us-ct | regulation | 2026-09-14-income-tax-regulations |
| us-ga | regulation | 2026-09-14-income-tax-regulations |
| us-hi | regulation | 2026-09-14-income-tax-regulations |
| us-ia | regulation | 2026-09-14-income-tax-regulations |
| us-id | regulation | 2026-09-14-income-tax-regulations |
| us-il | regulation | 2026-09-14-income-tax-regulations-title-086-part-00100 |
| us-in | regulation | 2026-09-14-income-tax-regulations |
| us-ks | regulation | 2026-09-14-income-tax-regulations |
| us-ky | regulation | 2026-09-14-income-tax-regulations |
| us-la | regulation | 2026-09-14-income-tax-regulations |
| us-ma | regulation | 2026-09-14-income-tax-regulations |
| us-md * | regulation | 2026-09-14-income-tax-regulations-publication-2026-09-11-title-03-subtitle-04 |
| us-me | regulation | 2026-09-14-income-tax-regulations |
| us-mi | regulation | 2026-09-14-income-tax-regulations |
| us-mn | regulation | 2026-09-14-income-tax-regulations |
| us-mo | regulation | 2026-09-14-income-tax-regulations |
| us-ms | regulation | 2026-09-14-income-tax-regulations |
| us-mt | regulation | 2026-09-14-income-tax-regulations-title-42-section-42-15 |
| us-nc | regulation | 2026-09-14-income-tax-regulations |
| us-nd | regulation | 2026-09-14-income-tax-regulations |
| us-ne | regulation | 2026-09-14-income-tax-regulations |
| us-nm | regulation | 2026-09-14-income-tax-regulations |
| us-ny | regulation | 2026-09-14-income-tax-regulations |
| us-oh * | regulation | 2026-09-14-income-tax-regulations-agency-5703-chapter-5703-7 |
| us-ok | regulation | 2026-09-14-income-tax-regulations |
| us-or * | regulation | 2026-09-14-income-tax-regulations-chapter-150-division-316 |
| us-pa | regulation | 2026-09-14-income-tax-regulations-title-61-chapter-101-103-105-107-109-111-113-115-117-119-121-123-125 |
| us-ri | regulation | 2026-09-14-income-tax-regulations |
| us-sc | regulation | 2026-09-14-income-tax-regulations |
| us-va | regulation | 2026-09-14-income-tax-regulations-title-23-agency-10-chapter-110-140 |
| us-vt | regulation | 2026-09-14-income-tax-regulations |
| us-wi | regulation | 2026-09-14-income-tax-regulations |
| us-wv | regulation | 2026-09-14-income-tax-regulations |

Consolidation commands (mirror of the 2026-09-11 pass; the released scope stays untouched and the
selector swaps it for the successor):

```bash
uv run python scripts/consolidate_release_scopes.py --base data/corpus \
  --jurisdiction us-md --document-class regulation \
  --source-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07 \
  --source-version 2026-09-14-income-tax-regulations-publication-2026-09-11-title-03-subtitle-04 \
  --target-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-09-14-title-03-subtitle-04-consolidated
uv run python scripts/consolidate_release_scopes.py --base data/corpus \
  --jurisdiction us-oh --document-class regulation \
  --source-version 2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-consolidated \
  --source-version 2026-09-14-income-tax-regulations-agency-5703-chapter-5703-7 \
  --target-version 2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-r2026-09-14-5703-7-consolidated
uv run python scripts/consolidate_release_scopes.py --base data/corpus \
  --jurisdiction us-or --document-class regulation \
  --source-version 2026-09-10-tanf-state-policy-manual-chapter-461 \
  --source-version 2026-09-14-income-tax-regulations-chapter-150-division-316 \
  --target-version 2026-09-10-tanf-state-policy-manual-chapter-461-r2026-09-14-150-316-consolidated
```

Rebuild (manifests, then the 29 official-documents scopes, then the adapters):

```bash
uv run python scripts/build_us_state_income_tax_regulation_manifests.py --cache-dir /tmp/tax-reg-cache
for st in al az ca co ct ga hi ia id in ks ky la ma me mi mn mo ms nc nd ne nm ok ri sc vt wi wv; do
  s=$(date +%s); uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-14-income-tax-regulations --manifest manifests/us-$st-income-tax-regulations.yaml \
    --source-as-of 2026-09-14 --expression-date 2026-09-14
  echo "elapsed_seconds=$(( $(date +%s) - s )) scope=us-$st/regulation/2026-09-14-income-tax-regulations"
done
V=2026-09-14-income-tax-regulations; A="--base data/corpus --version $V --source-as-of 2026-09-14 --expression-date 2026-09-14"
REQUESTS_CA_BUNDLE=<certifi bundle + data/certs/sectigo-public-server-authentication-ca-ov-r40.pem> \
  uv run axiom-corpus-ingest extract-illinois-admin-code $A --only-title 86 --only-part 100 --workers 4
uv run axiom-corpus-ingest extract-maryland-comar $A --only-title 03 --only-subtitle 04 --publication-branch publication/2026-09-11.2026-09-11
uv run axiom-corpus-ingest extract-montana-admin-rules $A --only-title 42 --only-section 42.15
uv run axiom-corpus-ingest extract-nycrr-parts $A --manifest manifests/us-ny-income-tax-regulations.yaml
uv run axiom-corpus-ingest extract-ohio-administrative-code $A --only-agency 5703 --only-chapter 5703-7
uv run axiom-corpus-ingest extract-oregon-administrative-rules $A --only-chapter 150 --only-division 316
uv run axiom-corpus-ingest extract-pennsylvania-code $A --only-title 61 --only-chapter 101,103,105,107,109,111,113,115,117,119,121,123,125 --workers 4
uv run axiom-corpus-ingest extract-virginia-vac $A --only-title 23 --only-agency 10 --only-chapter 110,140 --workers 4
uv run axiom-corpus-ingest validate-release --base data/corpus \
  --release docs/ingest-runs/2026-09-14-state-tax-regulations.selector.json --ignore-r2-missing --max-issues 50
```

Remaining steps are the controller's: consolidate MD/OH/OR, `sign-ingest-manifest` for the 37
scopes, merge into the next union selector, re-validate, sign, publish, activate. Follow-ups for a
later work order: Utah (browser session to capture the R865-9I file id), Oregon divisions 314/315,
Colorado 1 CCR 201-1, a page-windowed split of Mississippi 35.III.12.01, and the 2026-09-13
re-probe list for DC, NJ and AR if their publishers change.
