# Wave 8 state-tax regulations: the five income-tax regulation rows the 2026-09-14 run could not extract

Date: 2026-10-20 (work ran 14:48 to 15:40 EDT; wall time about 52 minutes).
Work order: the five `us-xx/regulation` rows of `manifests/tax-agent-queue.yaml` that the 2026-09-14 state
income-tax regulation run (`docs/ingest-runs/2026-09-14-state-tax-regulations.md`, needs-closure gap R01) left
`blocked_primary_source` (us-ar, us-dc, us-nj) or `needs_review` (us-de, us-ut). Four publishers now serve a body
with content; one moved.
Worktree `~/axiom-corpus-worktrees/w8-state-tax-regs`, branch `discovery/ingest-w8-state-tax-regs` cut from `main`
(393127f8b). Every extraction wrote to the main checkout's corpus root
(`--base data/corpus` of the main checkout) with `--source-as-of 2026-10-20`. The artifacts there are
unsigned and uncommitted: 3 new scopes, 344 rows, 619,200 characters of body text, 8.4 MB of sources, 159 source
files. Nothing under `manifests/releases/` or `manifests/program-bundles/` was touched; no signing, selector,
Supabase, R2 or `corpus push` step ran.
Disk: 3.0 TiB free at the start and at the end.
Impact analysis: not run (the GitNexus MCP tools were not available). No library function under `src/` changed: the
work is one new generator script, three manifests, five queue rows, one changelog fragment and this note.

Result: **3 of 5 rows extracted and moved to `agent_ready`** (us-ar, us-dc, us-ut), all coverage `complete: true`,
0 missing, 0 extra, 0 duplicate citation paths. **us-de stays `needs_review`** (re-confirmed absent at the
publisher, now proved at the deep endpoint). **us-nj stays `blocked_primary_source`** (the N.J.A.C. is still
published online by LexisNexis alone).

## Version

Scope version `2026-10-20-income-tax-regulations`, manifests `manifests/us-<st>-income-tax-regulations.yaml`.
The controller's brief suggested `2026-10-20-w8-state-tax-regulations`, but the existing family convention
dictates otherwise: these five rows are the open remainder of the one 2026-09-14 income-tax regulation family
(same closure gap R01, same `document_class`, same queue rows), whose 37 extracted scopes all carry
`<run-date>-income-tax-regulations` with an optional descriptive suffix and whose manifests are all named
`manifests/us-<st>-income-tax-regulations.yaml`. The `w<N>` infix belongs to the separate program-bundle gap waves
(`2026-10-06-w6-income-tax-forms-ok`, `2026-10-12-w7-income-tax-statute-va`), which this work order is not.
Only the run date changes, so the new scopes sit beside their 37 siblings and no sibling version is reused.

Document class is `regulation` for all three scopes: each document is codified administrative-code text published
by the jurisdiction's own code publisher, and each jurisdiction's existing citation convention is a regulation
convention (`us-dc/regulation/dcmr/...` from wave 7, `us-ut/regulation/admin-rules/...` from the July FEP and
wave-6 scopes, and the 2026-09-14 family's `us-pa/regulation/title-61/chapter-101/section-101-6` shape, which
Arkansas follows).

## Duplicate-work check

- `gh search prs "tax regulation" --repo TheAxiomFoundation/axiom-corpus --state open --limit 20`: 4 hits
  (#761 Montana ARM recovery successor, #746 Alabama TY2025 union, #827 HTML `pre` extractor, #547 CLML).
  None touches a state tax manifest of these five jurisdictions.
- `gh search issues "admin rules" --repo TheAxiomFoundation/axiom-corpus --state open`: no hits.
- `gh pr list --state open --json number,title,headRefName` (30 open PRs) and the same list with `files`, filtered
  on `tax-agent-queue`, `state-tax`, `us-ar`, `us-dc`, `us-de`, `us-nj`, `us-ut`: **no open PR changes
  `manifests/tax-agent-queue.yaml`.** Three open PRs touch neighbouring paths and none covers a row here:
  #899 (local-path scrub) edits `docs/ingest-runs/2026-09-14-state-tax-regulations.md` and the wave-7 state-tax
  brief prose; #763 holds us-ar and us-nj SNAP manual/rulemaking manifests; #753 holds us-dc *statute* title 47 and
  the D-40 booklets. No row was skipped for duplication.
- `gh search prs "state tax"` and `"tax-agent-queue"` additionally confirm the merged wave-6 tax PRs (#787, #788,
  #792) and the 2026-09-14 fourth-run union (#706); none holds a regulation scope for these five jurisdictions.
- Noted and not depended on: several open PRs fix the eCFR and PDF extractors (#827, #831, #832, #841, #842, #844,
  #851, #855, #862, #865, #871). Nothing here uses the eCFR adapter, and the only PDFs taken are the two Arkansas
  appendices, read by the extractor as it stands on `main`. No extractor change is required or duplicated.

## Method

Every address was fetched once with the extractor's own plain client (the `OFFICIAL_DOCUMENT_USER_AGENT`
`requests` session, certifi plus the committed `data/certs/` intermediates), one request at a time per host with
1.5 s spacing. TLS verification was never disabled and no certificate was added: the existing bundle verified all
four hosts.

**Bodies were read, not status lines.** Every retained source file was scanned for challenge and stub markers
("Attention Required! | Cloudflare", "Just a moment...", "bobcmn", "cf_chl_opt", "chk_jschl", "Checking your
browser", Incapsula, Radware, TSPD, captcha, "Please enable JavaScript", "No documents found"): **none found, in
any of the 159 files.** No retained file falls in the 5-8 KB challenge band; the smallest is 18,980 bytes. Four
bodies were rejected on content during discovery despite an HTTP 200 status line:
`codeofarrules.arkansas.gov/Rules/Rule?levelType=PART&id=...` (13.3 KB, "Object reference not set to an instance
of an object."), `adminrules.utah.gov/Code` and `/` (163 KB and 158 KB single-page-application frames with no rule
data), and the Arkansas `Home/GetRulesTreeViewData` responses below title level (`[]`, 2 bytes).

No host needed `browser_impersonation` or a browser user agent: no probe met a 403, so the plain extractor path was
used throughout and no manifest carries a `request` block. On Arkansas the plain path is also the only path, as
`curl_cffi` chrome120 still fails that host's certificate chain.

No mirror, repost, proxy, archived copy, Cornell, Justia, Casetext or LexisNexis page was used. No PolicyEngine
file or compiled list was read. No CAPTCHA was met. No secret was written to any file.

Manifests are built by the new `scripts/build_w8_state_tax_regulation_manifests.py` (`--cache-dir` makes a rebuild
offline; the 2026-09-14 generator was left untouched so its 37 historical manifests still rebuild byte-identically).

## Publisher access (2026-10-20)

| Host | Plain client | Body read | Notes |
| --- | --- | --- | --- |
| codeofarrules.arkansas.gov | 200 | rule text | **URL shape moved.** The recorded `?levelType=PART&id=26-33-261-941-0-0` answers 200 with a 13.3 KB null-reference error page. The live shape is `?levelType=section&titleID=26&chapterID=33&subChapterID=261&partID=&subPartID=&sectionID=`, whose `div#docxContent` carries the section text server-side. chrome120 still fails the certificate chain, so the plain client is the only path. |
| dcregs.dc.gov | 200, 196 KB | 85 section rows | **No longer postback-only.** Every `lnkFile` / "View text" control now prints a stable GET address beside its `__doPostBack`: `RuleList.aspx?DownloadFile=<id>` for the rule file and `SectionList.aspx?SectionNumber=<n>` for the section. |
| regulations.delaware.gov | 200 | valid JSON | `api/AdminCode/titles` is 3.4 KB **of valid JSON holding 20 complete title records**, not a stub; the deeper `POST api/AdminCode/title {regulationUrl}` endpoint named in the site bundle inventories every title. |
| www.nj.gov | 200, 28-155 KB | real pages | Pages render; their content still routes the N.J.A.C. to LexisNexis. Read, not assumed. |
| adminrules.utah.gov | 200 / 404 | rule text | **eRules relaunched v1.0.0 on 2026-10-16.** Every `/public/rule/...` and `/api/public/getfile/...` address answers 404. The new public API (`POST api/search`, `POST api/ruleVersion`, `GET api/agency`) and the rule route `/Rule/{ruleId}/{ruleTypeId}/{ruleVersionId}/undefined` serve. The new `/api/storage/<file>` download route answers HTTP 500 for every file name, including the one the rule record names. |
| rules.utah.gov | 200 | real pages | The Office's own site; its launch announcement dates the relaunch and its Code Updates page offers only monthly *changed-rules* ZIP archives, not the current code, so it was not used as a source. |

Blocked publishers: New Jersey (below).

## URLs repaired

| Row | Recorded address | Live address |
| --- | --- | --- |
| us-ut | `https://adminrules.utah.gov/public/rule/R865-9I/Current%20Rules` (404) | `https://adminrules.utah.gov/Rule/2067/51/7412/undefined` |
| us-ut `index_url` | same 404 address | `https://adminrules.utah.gov/api/search` (POST `{"searchTerm":"R865","ruleTypeId":51}`) |
| us-ar `index_url` | `https://codeofarrules.arkansas.gov/Rules/Search` (a search form, not an enumerable index) | `https://codeofarrules.arkansas.gov/Home/GetRulesSearchPartDropdown?levelType=PART&titleID=26` |
| us-de `index_url` | `https://regulations.delaware.gov/api/AdminCode/titles` | unchanged; the endpoint is correct, and `POST api/AdminCode/title` is the deeper one it leads to |

`us-ar`'s `primary_source_url` stays `https://codeofarrules.arkansas.gov/Rules/Search` (the publisher's own entry
point, still live); the dead `?levelType=PART&id=` rule shape lives only in the row's notes, where it was recorded.
The Utah trailing `/undefined` segment is required: `/Rule/2067/51/7412` without it answers 404.

## Index found versus taken

| Row | Index | Found | Taken | Left |
| --- | --- | ---: | ---: | --- |
| us-ar | Code of Arkansas Rules Title 26 Taxation part index | 67 parts | 5 parts (100-104), as 71 sections + 2 appendices | 62 parts: sales/use/excise, tobacco, severance, corporate, credits, administration |
| us-dc | DCMR Title 9 Chapter 1 rule list | 85 sections | 85 | none |
| us-de | Delaware Administrative Code title index | 20 titles / 147 units | 0 | all: no income-tax title exists |
| us-nj | OAL public-access page | 0 N.J.A.C. documents | 0 | n/a |
| us-ut | Utah Admin. Code Title R865 current rules | 14 rules | 1 (R865-9I) | 13: corporate/franchise, sales/use, fuel, severance, tobacco, fees |

### us-ar: Code of Arkansas Rules Title 26 by family (67 parts)

| family | parts |
| --- | ---: |
| tax administration and appeals | 18 |
| income tax credits and incentives | 15 |
| sales, use and excise tax | 8 |
| tobacco, beverage and other excise | 7 |
| **individual income tax** | **5** |
| income tax withholding and administration | 4 |
| corporate and pass-through income tax | 4 |
| property, severance and transfer tax | 4 |
| other taxation rules | 2 |

Parts 100-104 are Subchapter D, the individual income tax family: Part 100 Comprehensive Individual Income Tax
Rule, 101 Standard Mileage Rates, 102 Substitute and Reproduced Tax Forms, 103 Individual Income Tax Credit for
Political Contributions, 104 Treatment of Employee Contributions to Employment-Related Plans. The tree endpoints
still return `[]` below title level, so the sections were enumerated by the publisher's own PREVIOUS/NEXT chain
from the Part 100 page until it leaves `partID` 941-945: 5 part pages, 5 "Subpart 1. Generally" pages, 71 sections
and 2 appendices, 83 nodes in all. The 10 part and subpart pages carry no `div#docxContent` and no rule text, so
they are not taken. The 2 appendix pages carry no text either but link an appendix PDF through
`/Rules/AppendixDocument?appendixID=&partID=`, which is taken: Part 100 Appendix A is the 27-page INDEX of
individual income tax regulations (the old `1.26-51-xxx` numbering mapped to pages), Part 102 Appendix A the
1-page AR9101 Letter of Intent. Both have text layers, so no `ocr: true` is needed.

### us-dc: DCMR Title 9 Chapter 1 by family (85 sections)

| family | sections |
| --- | ---: |
| combined reporting and investment entities | 20 |
| withholding | 14 |
| allocation and apportionment | 8 |
| returns and filing requirements | 8 |
| reserved | 9 |
| estimated tax | 6 |
| franchise tax on corporations and unincorporated businesses | 6 |
| general provisions and exempt organizations | 4 |
| individual income tax computation, credits and modifications | 4 |
| modifications, federal adjustments and college savings | 3 |
| refunds, penalties and licenses | 3 |

The chapter now lists 85 sections, not the 22 the 2026-09-14 row recorded. All 85 are taken: the chapter is
"Income and Franchise Taxes", so by the family's scope rule (withholding and franchise material inside the same
income-tax chapter is in scope) the whole chapter is one scope. The 9 RESERVED sections are taken because the
publisher prints them as rule text ("183 RESERVED" plus its SOURCE note, 93 characters), the same treatment the
2026-09-14 run gave the GA, AZ and CO "Repealed." stubs. Files are legacy Word (`.doc`, OLE2 compound documents),
read with `segmentation: single_block`, the only segmentation the legacy DOC path accepts.

### us-ut: Utah Admin. Code Title R865 by family (14 current rules)

| family | rules |
| --- | ---: |
| sales and use tax | 3 (R865-19s, R865-21u, R865-12l) |
| severance and mineral tax | 3 (R865-16r, R865-15o, R865-14w) |
| corporate and franchise income tax | 2 (R865-3c, R865-6f) |
| fuel tax | 2 (R865-13g, R865-4d) |
| assessments and fees | 2 (R865-11q, R865-7h) |
| **individual income tax** | **1 (R865-9i)** |
| tobacco tax | 1 (R865-20t) |

R865-9I Income Tax (Tax Commission, Auditing; `ruleId` 2067, `ruleVersionId` 7412, effective 2026-01-01) is taken
as one whole-rule document. Corporate and franchise stay out of scope for the income-tax row, as in 2026-09-14.
R865-14w is mineral producers' withholding, a severance family rule, not wage withholding, so it is out of scope
too; Utah's wage-withholding sections sit inside R865-9I itself.

## Scopes

| jurisdiction | class | version | documents | rows | body chars | sources MB | s |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| us-ar | regulation | `2026-10-20-income-tax-regulations` | 73 | 172 | 294,001 | 3.2 | 100 |
| us-dc | regulation | `2026-10-20-income-tax-regulations` | 85 | 170 | 276,132 | 2.5 | 60 |
| us-ut | regulation | `2026-10-20-income-tax-regulations` | 1 | 2 | 49,067 | 2.7 | 7 |
| **total** | | 3 scopes | 159 | 344 | 619,200 | 8.4 | 167 |

MB are 10^6 bytes of source files; seconds are wall-clock per `extract-official-documents` run.
Row kinds: us-ar 73 document / 71 block / 28 appendix page; us-dc 85 document / 85 block; us-ut 1 document /
1 block.

## Decisions

- **Arkansas is taken per section, not per part.** The publisher prints one page per section with its own
  citation ("26 CAR § 100-101. Purpose"), which is the family's rule: split into section rows wherever the
  publisher prints section labels. Citation paths follow the 2026-09-14 family's Pennsylvania shape with the
  publisher segment the other two jurisdictions use:
  `us-ar/regulation/car/title-26/part-100/section-100-101`, appendices
  `us-ar/regulation/car/title-26/part-100/appendix-a`.
- **Arkansas expression date is 2026-10-19**, the "Last Updated" date the Code prints on every page. The online
  database is the official version of the Code of Arkansas Rules under Ark. Code § 25-15-218, effective
  2025-01-01, updated weekly; that statement is recorded in each document's metadata.
- **D.C. expression dates are per section.** 39 sections print a real effective date and carry it; 46 print the
  `1/1/1900` sentinel, so those carry the source-as-of date with the printed placeholder recorded in
  `effective_date_printed` and the substitution explained in `expression_date_note`. No date was invented.
- **Utah is one whole-rule row, not 32 section rows.** The rule page server-renders the publisher's own converted
  rule HTML into the DOM as Aspose absolute-positioned markup (`div.awdiv` / `span.awtext1`), which the July FEP
  R986 manifest already targeted. Read with `html_content_selector: "div[class$='_ruleHtml']"` it yields the whole
  rule, 49,067 characters, starting exactly at "R865. Tax Commission, Auditing."; the hashed CSS-module prefix
  changes per build, so the selector matches on the stable `_ruleHtml` suffix. Splitting was tried and rejected:
  because each visual line is its own `div.awdiv`, wrapped headings never form one line, and
  `segmentation: labeled_sections` with `html_text_selector: div.awdiv` recovers only 2 of the 32 `R865-9I-<n>`
  headings and 11,909 of 49,067 characters. One complete row is better than a lossy 2-row split. The 2026-09-14
  run made the same call for Mississippi's 327 kB chapter row.
- **The Utah file routes are not used.** `/api/storage/<file>` answers HTTP 500 for every file name tried,
  including the exact `htmlName` the rule-version record gives, and for a URL-encoded `uac-html/<file>` key it
  answers a JSON 404. Four argument shapes were tried and then the guessing stopped, as the 2026-09-14 Utah entry
  recommends. The rule page is the only working official address.
- **Utah's monthly changed-rules ZIPs were not used.** `rules.utah.gov/publications/code-updates/` offers only
  per-month archives of rules that changed that month, which is an edition snapshot, not the current rule.
- **Delaware's Technical Information Memoranda were not taken.** They are guidance, not codified regulations, and
  this row names regulations. Recorded as a reviewer follow-up for a `us-de/guidance` scope.

## Still blocked

**us-nj, `blocked_primary_source`.** N.J.A.C. 18:35 Gross Income Tax. Exact failure, all bodies read on
2026-10-20:

- `https://www.nj.gov/oal/rules/accessp/` answers HTTP 200 with a 29 KB page (28,983 bytes). Its only outbound
  code links are `lexisnexis.com/hottopics/njcode` and `lexisnexis.com/hottopics/njoal`, so the Office of
  Administrative Law still publishes free online access to the Administrative Code through LexisNexis alone.
- `https://www.nj.gov/oal/rules/portal/` (the OAL's own "State Agency Rulemaking Searchable Portal") answers
  HTTP 200 and points to `oalrulesproduction.dynamics365portals.us`, a rulemaking-filing portal, not codified
  N.J.A.C. text.
- `https://www.nj.gov/treasury/taxation/lawsregs.shtml` answers HTTP 200 with 48,268 bytes. Its "Statutes,
  Regulations, and Laws" block links only the OAL pages and `https://www.nj.gov/treasury/rulesamend.shtml`.
- `https://www.nj.gov/treasury/rulesamend.shtml` answers HTTP 200 with 155,267 bytes and is "Department of the
  Treasury - Proposed Rules and Amendments": a table of rulemaking notice PDFs, including ten N.J.A.C. 18:35
  entries (proposed amendments to 18:35-1.3, 4.1 and 11.3, the 18:35 readoptions of 2015 and 2022, the 18:35-12
  health-insurance rules). These are rulemaking documents, not the codified chapter.
- `https://www.nj.gov/treasury/taxation/rulesamend.shtml` answers HTTP 404.

A vendor site is not an official publisher under the source policy, so nothing was extracted. The row keeps
`taken_count: 0` and `index_document_count: 0`.

**us-de, `needs_review` (absent at the publisher).** The absence is now proved at the deep endpoint rather than
inferred from a small response: `api/AdminCode/titles` returns valid JSON with 20 complete title records, and
`POST api/AdminCode/title {regulationUrl}` inventories each one, 147 top-level regulatory units in all. The only
Department of Finance title is Title 12 Unclaimed Property and Tax Refund Offset and Intercept, 8 units (five
unclaimed-property regulations, 201 and 202 on tax refund offset and lottery intercept, 301 the voluntary
disclosure programme). The same POST endpoint answers with an empty record (null name, 0 units) for every title
number absent from the list, a hypothetical Title 30 revenue title included, so the 20-title list is the complete
index. The Delaware Administrative Code has no income-tax title. The row cannot become `agent_ready`, because
there is nothing to take, and it is not `blocked_primary_source`, because the publisher does not refuse.

## Verification

- Coverage, each of the three scopes: `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths.
- Uniqueness on the provisions JSONL: us-ar 172 rows / 172 unique paths, us-dc 170 / 170, us-ut 2 / 2.
- Uniqueness against every other provisions JSONL under `data/corpus/provisions/<jurisdiction>/`: 6 other us-ar
  scopes, 8 other us-dc scopes and 12 other us-ut scopes read in full. **No shared citation path with any of
  them**, so no collision was skipped or recorded. In particular the wave-7 `us-dc/regulation/dcmr/29-7200` and
  the Utah `admin-rules/r414/306`, `r986/700` and `r994/401` rows do not meet the new paths, and no scope carries
  a bare `us-xx/regulation` collection root that these scopes would duplicate.
- Body text: **0 empty leaf bodies** in 185 non-document rows. us-ar min 30 / median 646 / max 35,568
  (26 CAR § 100-122 Gross income generally); us-dc min 93 / median 93 / max 38,327 (9-155 College Savings
  Program); us-ut 49,067. The smallest row, `.../part-100/appendix-a/page-27`, is a footer-only page of the index
  PDF ("Income Tax Regulations Page 15") with a real text layer. Both appendix PDFs extract text, so no
  `ocr: true` is needed anywhere in this run.
- Source references: 159 inventory source files, all regular files, **0 symlinks**, every one under its own
  `sources/<jur>/regulation/2026-10-20-income-tax-regulations/` boundary with a matching SHA-256; every provision
  `source_path` is in its scope's inventory; no uninventoried file is left in any source tree.
- Challenge and stub scan over all 159 retained files: no marker, and no file in the 5-8 KB band.
- `scripts/validate_citation_paths.py --provisions <a scratch tree holding only the three new files>`:
  344 records, 344 unique paths, `RESULT: OK`; irregular families `block_n` 157 and `page_n` 28, both inside the
  existing baselines. **Note:** this script takes a directory and globs `**/*.jsonl` under it. Passing the three
  files as arguments reports "records scanned: 0" and still prints `RESULT: OK`, a vacuous pass; the run above
  used a directory.
- `uv run ruff check scripts/build_w8_state_tax_regulation_manifests.py` and `ruff format`: pass.
- Queue: three rows moved to `agent_ready`, `status_counts` reconciled against the live rows
  (`agent_ready` 25 -> 28, `blocked_primary_source` 3 -> 1, `needs_review` 3 -> 2, `done` 84, total 115).

## Tests

`uv sync --extra dev` first, then
`AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`:

- Baseline, before the first edit: **18 failed, 341 passed, 2 skipped, 7241 deselected** (162 s).
- After, at the end of the run: **18 failed, 341 passed, 2 skipped, 7241 deselected** (79 s).
- The two sorted FAILED lists are byte-identical (`diff` is empty, 18 lines each), so **no failure is new** and
  none is this branch's.

Every baseline failure is a `FileNotFoundError` on another scope's `data/corpus` artifacts that this worktree does
not hold (Armenia, BE, NY TANF, Wisconsin, Israel, SC, and the AK/CT/MI/MT/ND/NY SNAP manuals, plus the two
us-snap child-support PDF cases). None touches the official-documents code path this run exercises.

Two traps worth recording. Without `--extra dev` the venv resolves a different `pytest`, which fails to import
`axiom_corpus` with an `INTERNALERROR` and still exits 0, so a piped run looks like a pass. Without
`AXIOM_CORPUS_PARTIAL_TESTS=1` the session aborts on 68,059 locked corpus files that are not in the checkout, and
that abort also exits 0.

## Code changes

None under `src/`. New: `scripts/build_w8_state_tax_regulation_manifests.py`,
`manifests/us-ar-income-tax-regulations.yaml`, `manifests/us-dc-income-tax-regulations.yaml`,
`manifests/us-ut-income-tax-regulations.yaml`, `changelog.d/w8-state-tax-regulations.added.md`, this note.
Changed: `manifests/tax-agent-queue.yaml` (five rows and `status_counts`). No certificate was added to
`data/certs/`. The 2026-09-14 generator was not touched.

## Controller

- Select the three scopes of the Scopes table. No citation path collides with any scope on disk for those
  jurisdictions, so no consolidation is needed and no `consolidate_release_scopes.py` run is required.
- The `block_n` and `page_n` baselines in `schema/citation-path.v1.json` take their reviewed raise when the scopes
  are committed (157 `block_n`, 28 `page_n`), as for the wave-7 page-row scopes.
- `sign-ingest-manifest` for the three scopes, then merge into the next union selector and re-validate.
- us-nj needs an official publisher before it can move; us-de needs a reviewer decision on whether Division of
  Revenue Technical Information Memoranda belong in a `us-de/guidance` scope.
- The Utah relaunch broke addresses outside this run: `us-ut-fep-r986-239-official-document.yaml`,
  `us-ut-fep-official-documents.yaml`, `us-ut-ssi-state-supplement-rules.yaml`,
  `us-ut-benefits-w6-regulation.yaml`, `us-ut-tanf-ccdf-w6-regulation.yaml` and the `ssi` program bundle all
  carry `adminrules.utah.gov/public/...` or `/api/public/getfile/...` addresses that now answer 404. Their
  retained sources are unaffected, but a re-fetch or a source-drift check would fail. That is a separate work
  order.

Rebuild:

```bash
B=data/corpus   # the main checkout's corpus root
uv run python scripts/build_w8_state_tax_regulation_manifests.py --cache-dir /tmp/w8-tax-reg-cache
for st in ar dc ut; do
  s=$(date +%s)
  uv run axiom-corpus-ingest extract-official-documents --base $B \
    --version 2026-10-20-income-tax-regulations \
    --manifest manifests/us-$st-income-tax-regulations.yaml --source-as-of 2026-10-20
  echo "elapsed_seconds=$(( $(date +%s) - s )) scope=us-$st/regulation/2026-10-20-income-tax-regulations"
done
```

## Timing

Started 14:48 EDT, finished 15:40 EDT, wall time about 52 minutes. Orientation, repo rules and the
duplicate-work check 14:48-14:56; publisher probes and endpoint discovery 14:56-15:18 (Arkansas chain walk 83
requests, about 2.5 minutes; Utah API discovery the longest single piece); generator and manifests 15:18-15:25;
extractions 15:25-15:33 (DC 60 s, UT 7 s, AR 100 s, 167 s in all); checks, queue, note and commit 15:33-15:40.
Working files (probe responses, the generator cache, the validator scratch tree) are in this session's scratchpad,
not in the repository or the corpus root.
