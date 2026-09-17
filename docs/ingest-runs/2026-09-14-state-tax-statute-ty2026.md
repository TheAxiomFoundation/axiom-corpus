# State income-tax statute chapters (18 partial states) and TY2026 indexed amounts (30 states)

Date: 2026-09-14
Work order: top gaps 2 (F06, TY2026 indexed amounts: 30 states REVIEW) and 3 (partial income-tax
chapters: 18 states) of the needs-driven closure check for individual income tax
(`docs/coverage/needs-closure-2026-09-11/tax.md`, `tax-schema.yaml`, `tax-matrix.csv`).
Branch `discovery/ingest-state-tax-statute-ty2026` cut from `origin/main` (5c2505ec6) in the sparse
worktree `~/axiom-corpus-worktrees/tax-statute` (`data/corpus/` excluded, never symlinked); every
extraction wrote to the main checkout's corpus root (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`)
with `--source-as-of 2026-09-14`. Research of the 30 revenue-department indexes ran on 2026-09-13
(three parallel read-only probes, curl with the corpus user agent, every URL fetched and read);
extractions ran 2026-09-13T21:24-04:00 to 2026-09-14T00:10-04:00; per-scope seconds are in the tables.
Disk: 33 GB free at start, 29 GB at the end (statute sources 454 MB, amounts sources 13 MB; the stop
line of 5 GB was never approached).
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. Two library
functions changed, both additively (see Code changes); everything else is manifests, the two
generator scripts, the queue rows and this note.

## Publisher access (2026-09-13/14)

- Statute publishers served the plain corpus client: ALISON GraphQL (AL), azleg.gov (AZ, no WAF
  block this run), delcode.delaware.gov (DE), legislature.idaho.gov (ID, slow: 429 s for 164
  rows), apps.legislature.ky.gov (KY; the chapter listing is `chapter.aspx?id=37674`, one PDF per
  section from `statute.aspx?id=N`), mgaleg.maryland.gov (MD, no WAF block this run),
  legislature.maine.gov (ME), revisor.mn.gov (MN), nebraskalegislature.gov (NE), codes.ohio.gov (OH),
  le.utah.gov (UT), law.lis.virginia.gov (VA), leginfo.legislature.ca.gov (CA, no WAF block this run:
  1,029 section pages at 0.3 s spacing, 547 s).
- `www.cga.ct.gov` (CT) and `www.legislature.mi.gov` (MI) serve TLS chains without their
  intermediates (Go Daddy Secure Certificate Authority G2; DigiCert Global G2 TLS RSA SHA256 2020
  CA1). Both intermediates were already under `data/certs/`; `data/certs/state-tax-statute-ca-bundle.pem`
  (certifi plus the two, `git add -f`) was passed as `REQUESTS_CA_BUNDLE` for every adapter run.
  Verification was never disabled.
- `www.nysenate.gov` (NY Tax Law) answers HTTP 403 to the plain corpus client and serves the page to
  a Chrome TLS fingerprint; the OpenLegislation JSON API the July core scope used needs an API key
  that is not available in this environment (HTTP 401). The manifest carries
  `browser_impersonation: chrome120` (curl_cffi, TLS verified).
- Revenue departments: `tax.colorado.gov` (CloudFront) and `tax.ohio.gov` answer the corpus client
  with 403 (Ohio as a 404 whose body is a "403 Error Page") and serve a Chrome user agent; the two
  manifests carry the browser fallback. `dor.georgia.gov`, `dor.mo.gov`, `tax.ny.gov` and
  `mgaleg.maryland.gov` served the corpus client this run (no WAF block observed).
- Blocked: `otr.cfo.dc.gov` (DC) answers "Access denied | otr" (HTTP 403) to both user agents on
  every page path; `marylandtaxes.gov` (MD Comptroller) redirects to a ServiceNow knowledge base whose
  pages are JavaScript shells (HTTP 200, no text or document links; KB API 401) and whose legacy PDF
  paths 404; the Arkansas and Mississippi Codes are published only through LexisNexis behind the
  robot check (probed once each). Not worked around.
- No mirror, repost, proxy or archived copy was used; no CAPTCHA was attempted; no OCR was needed
  (every PDF taken has a text layer; body lengths below).

## Family 1: whole income-tax chapter statute scopes (18 states)

Method. Where the state's source-first adapter has a chapter (or article) filter the chapter was
taken through `extract-state-statutes` from `manifests/state-income-tax-chapters-2026-09-14.yaml`
(CT 12/229, DE 30/11, ID 63/30, MI 206, MN 290, AZ title 43 which is the income-tax title); where
the adapter filters at title grain only, the enclosing taxation title was taken (AL 40, MD
Tax-General, ME 36, NE 77, OH 57, UT 59), which is a superset of the chapter and keeps the coverage
check against the publisher's index meaningful. The adapters append a scope suffix to the version
prefix `2026-09-14-income-tax-chapter` (the same convention as the July `-pit-central-us-mt-title-15`
scopes). Four states have no chapter-capable adapter and were taken one section per document by
`scripts/build_state_tax_statute_ty2026_manifests.py --family statute`, which reads the legislature's
own index live: KY (195 section PDFs, `single_block`, citation path `us-ky/statute/krs/141.NNN`,
the convention of the July KY scope so its `.../document-1` citations still resolve), VA (307 LIS
section pages, `article#vacode section.body`), NY (93 section pages listed on the six article 22
part pages, `div.nys-openleg-result-text`, `us-ny/statute/TAX/NNN`) and CA (RTC Parts 10 and 10.2,
1,032 section numbers read from the 88 chapter/article text pages, 1,029 unique, run through
`extract-california-code-sections`; the extractor emits section rows whose parent is the omitted
`us-ca/statute/rtc` container, so `scripts/self_contain_usc_scope.py` detached those parents the way
the July core scope was self-contained). Every scope reports `complete: true`, 0 missing, 0 extra,
0 duplicate citations; no section row has an empty body except the publisher's own repealed,
transferred or "Unconstitutional" placeholders (NE 801 of 2,741, MI 56 of 307, DE 5 of 88; KY's 43
repealed sections carry the LRC "Repealed" note as their body). Section rows are one row per
section (adapters) or root plus one body row (`document-1` / `block-1`, official-documents
extractor); nothing is a whole-chapter dump, and the largest single-section bodies are NY 606
(402 K characters, the credits section), MD 10-105 rate section (111 K) and UT (96 K).

Not taken: AR and MS (Lexis-only publishers, blocked; the released Act 2 of 2026 and HB 1 scopes
stay).

| st | chapter taken | scope version(s) (`2026-09-14-income-tax-chapter` + suffix) | rows | sections | complete | s |
|---|---|---|---:|---:|---|---:|
| al | Code of Alabama Title 40, Chapter 18 (whole Title 40 taken) | -us-al-title-40 | 2,265 | 2,062 | yes | 56 |
| az | Arizona Revised Statutes Title 43 (Taxation of Income) | -us-az-title-43 | 335 | 265 | yes | 42 |
| ca | California Revenue and Taxation Code Division 2, Parts 10 and 10.2 (Personal Income Tax; Administration) | -us-ca-sections-4e26e6efabc3f0c7 | 1,029 | 1,029 | yes | 547 |
| ct | Connecticut General Statutes Title 12, Chapter 229 (Income Tax), with the title 17b companion | -title-12-chapter-229; -title-17b | 797 | 773 | yes | 4 + 4 |
| de | Delaware Code Title 30, Chapter 11 (Personal Income Tax) | -us-de-title-30-chapter-11 | 103 | 88 | yes | 6 |
| id | Idaho Statutes Title 63, Chapter 30 (Income Tax) | -us-id-title-63-chapter-30 | 164 | 162 | yes | 429 |
| ky | Kentucky Revised Statutes Chapter 141 (Income Taxes) | (none) | 390 | 195 | yes | 10 |
| md | Maryland Code, Tax-General Article, Title 10 (Income Tax) (whole article taken) | -us-md-article-gtg | 744 | 729 | yes | 43 |
| me | Maine Revised Statutes Title 36, Part 8 (Income Taxes) (whole Title 36 taken) | -us-me-title-36 | 1,933 | 1,776 | yes | 220 + 9 (re-run) |
| mi | Michigan Compiled Laws Chapter 206 (Income Tax Act of 1967) | -us-mi-chapter-206 | 308 | 307 | yes | 4 |
| mn | Minnesota Statutes Chapter 290 (Income and Franchise Taxes), with companions 142G and 256P | -us-mn-title-290; -us-mn-title-142g; -us-mn-title-256p | 312 | 306 | yes | 12 + 9 + 9 |
| ne | Nebraska Revised Statutes Chapter 77, Article 27 (Income Tax) (whole Chapter 77 taken) | -us-ne-title-77 | 2,742 | 2,741 | yes | 6 |
| ny | New York Tax Law Article 22 (Personal Income Tax) | (none) | 186 | 93 | yes | 78 |
| oh | Ohio Revised Code Chapter 5747 (Income Tax) (whole Title 57 taken) | -us-oh-title-57 | 1,385 | 1,351 | yes | 28 |
| ut | Utah Code Title 59, Chapter 10 (Individual Income Tax Act) (whole Title 59 taken) | -title-59 | 1,226 | 1,082 | yes | 78 |
| va | Code of Virginia Title 58.1, Chapter 3 (Income Tax) | (none) | 614 | 307 | yes | 105 |

Companion scopes. The released `2026-07-13-recovery` scopes of CT and MN mix income-tax sections
with public-assistance sections that rulespec-us cites (CGS 17b-104, 17b-112, 17b-600; Minn. Stat.
142G.16, 142G.17, 256P.03). Swapping the recovery scope out for the chapter would drop them, so the
chapters holding them were taken from the same publishers at the same grain: CT Title 17b whole
(722 rows; two chapter-level scopes of one title would both carry the `us-ct/statute/title-17b`
container row, which the validator rejects as a duplicate citation) and MN chapters 142G and 256P.
The MN chapter tokens are lettered, and `state_run_id` uppercased them into the version string,
which the release selector rejects; the run id now lowercases the chapter token (Code changes).

### Superseding swaps and cited-path checks

Released scopes are immutable; the swaps below are what the controller applies to the selector.
"Colliding paths" are citation paths present in both the released scope and the new scope (a
selector cannot carry a path twice). "Dangling" are paths cited by rulespec-us (commit c8951033,
`~/rulespec-us/us-xx`) that exist in neither the new scope nor a kept scope: all of them are
sub-section rows of the recovery scopes (`block-N`, `/10`-style subsection splits, the CA
`wic/11450/a/1/A` paragraph) whose section root is in the new scope; the rules repository re-points
them to the section root (with anchors for the paragraph) as a follow-up. KY's `us-ky/statute/11/...`
citations and NY's `NYC/...` citations sit in kept scopes (KY recovery, NYC admin code), which do not
collide. The MD human-services and CT supplement/12-700-a-10 scopes are kept.

| st | released scope(s) swapped out | colliding paths | paths of the released scope not in the new scope | rulespec-us cited: total / in new scope / in a kept scope / dangling |
|---|---|---:|---|---|
| al | `2026-07-13-recovery` | 3 | none | 3 / 3 / 0 (-) / none |
| az | `2026-07-13-recovery` | 7 | 7 (2026-07-13-recovery...) | 7 / 7 / 0 (-) / none |
| ca | `2026-07-06-ca-rtc-pit-core-us-ca-sections-rtc-17041-rtc-17043-rtc-17045-rtc-17052-rtc-17054-rtc-17073.5`; `2026-07-13-recovery` | 16 | none; 23 (2026-07-13-recovery...) | 24 / 16 / 7 (`wic/11450.12`, `wic/11451.5`, `wic/11452`, `wic/11452.018`, `wic/12200`, `wic/18901.3`, `wic/18901.5`) / `wic/11450/a/1/A` |
| ct | `2026-07-13-recovery` | 6 | 9 (2026-07-13-recovery...) | 11 / 6 / 3 (`12-700-a-10/operative-text`, `2026-supplement/12-704e`, `2026-supplement/12-704e/earned-income-tax-credit`) / `12-700/block-1`, `12-704i/block-1` |
| de | `2026-07-13-recovery` | 6 | none | 6 / 6 / 0 (-) / none |
| id | `2026-07-31-id-title-63-chapter-30-successor` | 7 | none | 5 / 5 / 0 (-) / none |
| ky | `2026-07-22-individual-income-tax` | 4 | none | 5 / 2 / 3 (`11/141.020`, `11/141.067`, `11/141.069`) / none |
| md | `2026-07-13-recovery-r2026-07-24-immutable` | 2 | `gtg/10-105/block-1`, `gtg/10-211/block-1` | 4 / 2 / 2 (`human-services/5-312/temporary-cash-assistance`, `human-services/5-316/fip-funding`) / none |
| me | `2026-07-13-recovery` | 6 | 7 (2026-07-13-recovery...) | 7 / 6 / 0 (-) / `36/5111/block-2` |
| mi | `2026-07-13-recovery` | 1 | 14 (2026-07-13-recovery...) | 11 / 1 / 0 (-) / `206.30/10`, `206.30/11`, `206.30/12`, `206.30/2`, `206.30/3`, `206.30/7`, `206.30/8`, `206.51/1`, `206.51/10`, `206.51/6` |
| mn | `2026-07-13-recovery` | 5 | 120 (2026-07-13-recovery...) | 10 / 8 / 0 (-) / `290.06/block-12`, `290.06/block-13` |
| ne | `2026-07-13-recovery` | 3 | 10 (2026-07-13-recovery...) | 3 / 3 / 0 (-) / none |
| ny | `2026-07-06-ny-tax-article22-core-us-ny-sections-tax-601-tax-606-tax-614-tax-615-tax-616`; `2026-07-13-recovery` | 16 | none; none | 17 / 14 / 3 (`NYC/11-1701`, `NYC/11-1704.1`, `NYC/11-1706`) / none |
| oh | `2026-07-13-recovery` | 4 | 8 (2026-07-13-recovery...) | 3 / 3 / 0 (-) / none |
| ut | `2026-07-13-recovery` | 3 | none | 3 / 3 / 0 (-) / none |
| va | `2026-07-13-recovery` | 8 | none | 4 / 4 / 0 (-) / none |

## Family 2: TY2026 indexed amounts (30 states)

Method. For each REVIEW state the revenue department's own forms index or rates page was read
(recorded as `index_url` with its count in the queue row) and the first of (1) a 2026-labelled
notice, bulletin or web page printing the indexed figures, (2) the 2026 estimated-tax instructions,
(3) a 2026 withholding publication was taken; where the department has posted no 2026-labelled
figures, the latest published year was taken and labelled with its own year (HI 2025 tables, ID
2025 rate page plus the 2026-dated withholding table, OH 2025 rates page, UT rates page). Class
follows the jurisdiction precedents: estimated-tax instructions are `form`
(`us-xx/form/<agency>/ty2026/<id>`, like the released AZ 140ES, KY 740-ES, NE 1040N-ES scopes);
notices, publications and department pages are `guidance` (`us-xx/guidance/<agency>/ty<year>/<id>`,
like the released MN, ME, MI, RI scopes). Version `2026-09-14-ty2026-indexed-amounts`; PDFs
`single_block`, pages `html_content_selector` (one block per heading). Static tables in
`scripts/state_tax_ty2026_amounts.py`; 29 manifests `manifests/us-xx-individual-income-tax-{form,guidance}-ty2026-amounts.yaml`;
27 states, 29 scopes, 33 documents, 5 to 8 s each; every scope `complete: true`, every document
body-bearing (smallest body UT 503 characters, the department's rates paragraph).

Not taken: DC (blocked), MD (publisher serves no static document), WI (the 2026 Form 1-ES
instructions are already released as `us-wi/form/2026-07-22-wi-form1-es-2026`; the check's REVIEW is
a regex miss). RI's ADV 2025-22 is likewise already released and not re-taken; the 2026 RI-1040ES
adds the printed schedule. MN's released `2026-07-22-mn-income-tax-inflation-adjusted-amounts-2026`
split the PDF table into per-bracket rows that captured the "Statutory Year" column (2019/2023); the
same PDF is re-taken here as one body together with the department's rates page, and the controller
swaps the defective scope out (no path collision; the new paths are under `.../ty2026/...`).

| st | class | document (tax year) | citation path | rows | notes |
|---|---|---|---|---:|---|
| al | form | 2026 Form 40ES Declaration of Estimated Tax Instructions (2026) | `us-al/form/ador/ty2026/form-40es-instructions` | 2 | estimated-tax thresholds only |
| al | guidance | Individual Income Tax: General Information for Individuals (rates and personal exemptions) (2026) | `us-al/guidance/ador/ty2026/individual-income-tax-filing-information` | 2 | rate schedule (2%/4%/5%); personal exemption ($1,500/$3,000) |
| ar | form | AR1000ES Individual Estimated Tax Vouchers and Instructions for Tax Year 2026 (2026) | `us-ar/form/dfa/ty2026/ar1000es-instructions` | 2 | rate schedule (0%-3.7%); standard deduction ($2,470); personal credits ($29/$58); bracket-adjustment table |
| co | form | DR 0104EP 2026 Colorado Estimated Income Tax Payment Form (2026) | `us-co/form/cdor/ty2026/dr-0104ep` | 2 | flat rate (4.4%); estimated-tax threshold |
| ct | form | Form CT-1040ES 2026 Estimated Connecticut Income Tax Payment Coupon for Individuals (2026) | `us-ct/form/drs/ty2026/ct-1040es` | 2 | Table A personal exemptions 2026; Table B rate schedule 2026; phase-out and recapture tables |
| de | form | Form PIT-EST Delaware Estimated Income Tax Voucher Instructions (2026) (2026) | `us-de/form/dor/ty2026/pit-est-instructions` | 2 | rate schedule (2.2%-6.6%); standard deduction ($3,250/$6,500); additional standard deduction ($2,500); personal credit ( |
| ga | form | 2026 500-ES Estimated Tax for Individuals and Fiduciaries (2026) | `us-ga/form/dor/ty2026/500-es` | 2 | standard deduction ($12,000/$24,000); dependent exemption ($4,000, labelled tax year 2025); retirement exclusion |
| hi | guidance | 2025 Tax Tables and Tax Rate Schedules (individual tax tables for taxable years beginning  (2025) | `us-hi/guidance/dotax/ty2025/tax-tables-and-rate-schedules` | 2 | rate schedules I-III (1.4%-11%); tax tables |
| ia | form | 2026 IA 1040ES Estimated Tax Payment Voucher Instructions (45-009) (2026) | `us-ia/form/idr/ty2026/ia-1040es-instructions` | 2 | flat rate (3.8%); low-income exemption thresholds |
| id | guidance | Individual Income Tax Rate Schedule (by year; 2025 latest) (2025) | `us-id/guidance/istc/ty2025/individual-income-tax-rate-schedule` | 42 | rate schedule by year (2025 latest: 0% to $4,811/$9,622, then 5.3%) |
| id | guidance | Table for Percentage Computation Method of Withholding (EPB00744, rev. 2026-07-23) (2026) | `us-id/guidance/istc/ty2026/epb00744-withholding-percentage-table` |  | withholding rate (5.3%); zero-bracket withholding thresholds ($16,100/$32,200) |
| mn | guidance | Inflation Adjusted Amounts for 2026 (tax year 2026 inflation-adjusted amounts) (2026) | `us-mn/guidance/department-of-revenue/ty2026/inflation-adjusted-amounts` | 7 | bracket thresholds; standard deduction; dependent exemption; aged/blind additional deduction; child credit; working fami |
| mn | guidance | Income Tax Rates and Brackets (tax year 2026) (2026) | `us-mn/guidance/department-of-revenue/ty2026/income-tax-rates-and-brackets` |  | rate schedule 2026 (5.35%/6.8%/7.85%/9.85% by filing status) |
| mo | form | MO-1040ES 2026 Declaration of Estimated Tax for Individuals (2026) | `us-mo/form/dor/ty2026/mo-1040es` | 2 | tax rate chart 2026 (2.0%-4.7%); standard deductions 2026; head-of-household/qualifying-widow additional exemption ($1,4 |
| ms | guidance | General Information: individual income tax rates for tax years 2025-2027, exemptions and s (2026) | `us-ms/guidance/dor/ty2026/general-information` | 7 | rate step by year (2026: 4% over $10,000); exemptions ($12,000/$8,000/$6,000; dependent $1,500); standard deduction ($4, |
| mt | guidance | 2026 Montana Publication 1: A Guide to Montana Tax Withholding and Estimated Payments (wor (2026) | `us-mt/guidance/mtdor/ty2026/publication-1` | 2 | 2026 and 2027 tax tables (4.7%/5.65%; 2027 5.4%); net long-term capital gains rates; worksheet ESW/ESA 2026 |
| nc | guidance | Tax Rate Schedules (current tax year rates: 3.99% for taxable years after 2025) (2026) | `us-nc/guidance/ncdor/ty2026/tax-rate-schedules` | 3 | flat rate by year (2025 4.25%; after 2025 3.99%) |
| nd | form | Form ND-1ES 2026 Estimated Individual Income Tax (SFN 28709, 12-2025) (2026) | `us-nd/form/otc/ty2026/nd-1es` | 2 | 2026 Forms ND-1 and ND-EZ tax rate schedules (1.95%/2.5% by filing status) |
| nj | form | 2026 NJ-1040-ES Instructions (Declaration of Estimated Tax) (2026) | `us-nj/form/taxation/ty2026/nj-1040-es-instructions` | 2 | personal exemptions ($1,000/$1,500/$6,000); filing thresholds |
| nm | guidance | FYI-104 New Mexico Withholding Tax, effective January 1, 2026 (2026) | `us-nm/guidance/trd/ty2026/fyi-104-withholding-tax` | 2 | withholding percentage-method tables (1.7%-5.9%); supplemental wage rate (5.9%) |
| ny | form | Instructions for Form IT-2105 Estimated Income Tax Payment Voucher for Individuals, tax ye (2026) | `us-ny/form/tax/ty2026/it-2105-i` | 2 | standard deduction table 2026; dependent exemption ($1,000); New York State rate schedules; New York City rate schedules |
| oh | guidance | Annual Tax Rates: Ohio individual income tax brackets for 2005 through 2025 (2025) | `us-oh/guidance/odt/ty2025/annual-tax-rates` | 22 | bracket schedule by year (2025 latest: 0% to $26,050, 2.75%, 3.125%) |
| ok | form | Form OW-8-ES Oklahoma Individual Estimated Tax, Tax Year 2026 Worksheet and Coupon (2026) | `us-ok/form/otc/ty2026/ow-8-es` | 2 | personal exemption ($1,000) |
| pa | form | 2026 REV-413 (I) Instructions for Estimating PA Personal Income Tax, for individuals only (2026) | `us-pa/form/department-of-revenue/ty2026/rev-413i` | 2 | flat rate (3.07%); estimated-payment income threshold ($14,000 for 2026) |
| ri | form | 2026 RI-1040ES Rhode Island Resident and Nonresident Estimated Payment Coupons (2026) | `us-ri/form/tax/ty2026/ri-1040es` | 2 | 2026 tax rate schedule (3.75%/4.75%/5.99%); standard deduction; exemption ($5,250); phase-out threshold ($261,000) |
| sc | form | SC1040ES 2026 Individual Declaration of Estimated Tax (Rev. 10/13/25) (2026) | `us-sc/form/dor/ty2026/sc1040es` | 2 | 2026 tax computation schedule (0%/3%/6%; $3,640 and $18,230 breakpoints) |
| ut | guidance | Tax Rates (Utah single rate by date range; 4.5% from January 1, 2025) (2025) | `us-ut/guidance/ustc/ty2025/tax-rates` | 2 | flat rate by date range (4.5% from 2025-01-01) |
| va | form | 2026 Form 760ES Virginia Estimated Income Tax Payment Vouchers for Individuals (Rev. 09/25 (2026) | `us-va/form/tax/ty2026/760es` | 2 | tax rate schedule (2%-5.75%); personal exemption ($930; age 65/blind $800); filing thresholds |
| va | guidance | Deductions (Virginia standard deduction amounts) (2026) | `us-va/guidance/tax/ty2026/deductions` | 21 | standard deduction ($8,750/$17,500) |
| vt | form | 2026 Form IN-114 Instructions, Individual Income Estimated Tax Payment Voucher, with 2026  (2026) | `us-vt/form/vdt/ty2026/in-114-instructions` | 2 | 2026 preliminary rate schedules X, Y-1, Y-2, Z; child care contribution rate (0.11%) |
| wv | guidance | 2026 Income Tax Rate Cut (SB 392; W. Va. Code 11-21-4j rate schedules retroactive to Janua (2026) | `us-wv/guidance/tax/ty2026/2026-income-tax-rate-cut` | 6 | 2026 rate schedule (2.11%-4.58%); 2026 married-filing-separately schedule |
| wv | guidance | IT-100.2.A Tables for Percentage Method of Withholding (March 2026) (2026) | `us-wv/guidance/tax/ty2026/it-100-2-a-withholding-tables` |  | withholding percentage-method rates; per-exemption wage reduction |

- **us-dc** (blocked_primary_source): otr.cfo.dc.gov answers HTTP 403 'Access denied | otr' (101,469-byte block page) to the corpus client and to a Chrome user agent on every page path probed on 2026-09-13; the 2026-09-10 forms run had been served on the same paths. Not worked around.
- **us-md** (blocked_primary_source): marylandtaxes.gov redirects to a ServiceNow knowledge base whose pages are JavaScript-rendered shells (HTTP 200, no article text or document links in the HTML; the KB REST API answers 401) and the legacy PDF paths (forms/current_forms/502D.pdf, 26_forms/PV.pdf, 26_forms/Withholding_Guide.pdf) redirect to 404. No 2026-labelled document is retrievable from the publisher as of 2026-09-13.
- **us-wi** (done): The 2026 Form 1-ES instructions (2026 standard deduction schedules and rate schedules) are already released as us-wi/form/2026-07-22-wi-form1-es-2026 (citation path us-wi/form/individual-income-tax/2026/1-es, same file); the closure check's REVIEW is a regex miss, not a gap. Not re-taken.
- **us-ar** statute (blocked_primary_source): The official Arkansas Code is published only through LexisNexis (arkleg.state.ar.us links to advance.lexis.com); the container answers a 3.6 KB JavaScript shell that requires the Lexis CAPTCHA/robot check before any section text (probed once 2026-09-13, same as manifests/state-statute-agent-queue.yaml). The released Act 2 of 2026 scope stays.
- **us-ms** statute (blocked_primary_source): The official Mississippi Code is published only through LexisNexis with the same CAPTCHA/robot check (probed once 2026-09-13); the released HB 1 (2025) recovery of section 27-7-5 stays.

## Data-quality findings

- Maine adapter: sections without subsections (478 of 1,776 in Title 36, e.g. 36 M.R.S. §115)
  had empty bodies because `parse_maine_section` read only `.MRSSubSection` nodes; fixed
  (fallback to the section's own `.mrs-text` paragraphs) and Title 36 re-extracted: 0 empty
  bodies. The released ME recovery scope was not affected (its five sections have subsections).
- CT chapter 229: the adapter merged the 2026 supplement (12-704e carries `source_set:
  supplement`, P.A. 25-168), so the released `2026-07-24-ct-income-tax-supplement` scope
  (`2026-supplement/12-704e`) is redundant but kept because it does not collide.
- CA: 1,032 section numbers listed on the chapter/article pages, 1,029 unique documents (three
  sections are listed under two headings); `metadata.parent_citation_path` and
  `detached_parent_citation_path` record the omitted `us-ca/statute/rtc` container.
- The five `unsectioned_document_body` and 541 `missing_parent_id` validator warnings are
  pre-existing (released WIC/IA scopes; `us-ca/regulation/2026-07-13-recovery`).

## Code changes

- `src/axiom_corpus/corpus/state_adapters/maine.py` `parse_maine_section`: additive fallback for
  sections without `.MRSSubSection` (test `test_parse_maine_section_without_subsections_keeps_body`).
  Callers: `extract_maine_revised_statutes` and the Maine tests; behaviour unchanged for sections
  with subsections.
- `src/axiom_corpus/corpus/states.py` `extract_minnesota_statutes`: the run id (scope version) uses
  the lowercased chapter token; the chapter filter itself is unchanged. Only lettered chapters are
  affected (no released MN scope has one).
- New: `scripts/build_state_tax_statute_ty2026_manifests.py`, `scripts/state_tax_ty2026_amounts.py`,
  `manifests/state-income-tax-chapters-2026-09-14.yaml`, the KY/VA/NY/CA statute manifests, the 29
  amounts manifests, `data/certs/state-tax-statute-ca-bundle.pem`.

## Tests

`uv run ruff check .`: passes. `uv run --extra dev python -m pytest -q -m "not integration and not slow"
-k "manifest or official_documents or discovery or tax or statute"` in the sparse worktree:
628 passed, 2 skipped, 20 failed, 4,211 deselected. All 20 failures read other scopes' `data/corpus`
artifacts that the sparse checkout does not contain (`FileNotFoundError` or its equivalent on the same
missing path): `test_armenia_arlis`, `test_be_rulespec_2026_08_23_promotion`,
`test_build_nc_ty2026_statutes`, `test_build_ny_tanf_compatibility_scope` (x2),
`test_idaho_statute_successor` (x2), `test_israel_openlaw`, `test_recover_ingest` (x4),
`test_rulespec_be_source_promotion`, `test_sc_act110_successor`, and the AK, CT, MI, MT, ND, NY SNAP
manual tests (the wider `-k` of this order matches more of them than the ten the earlier notes list).
None touches the two changed functions; `tests/test_corpus_maine.py` (4) and the Minnesota tests (3)
pass.

## Controller

Draft selector `docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.selector.json` =
`manifests/releases/us-rulespec-2026-09-13-federal-and-plans-union.json` (761 scopes) minus the 19
superseded scopes plus the 48 new scopes (790 scopes); `validate-release --ignore-r2-missing`:
`ok: true`, 0 errors, 546 warnings (all pre-existing). Artifacts are unsigned, on the controller's
disk under `/Users/pavelmakarchuk/axiom-corpus/data/corpus`, not committed. Remaining steps are the
controller's: `sign-ingest-manifest` per scope, merge into the next selector, re-validate, sign,
publish, activate; and the rulespec-us re-point of the dangling sub-section citations listed above.

| action | jurisdiction | document_class | version |
|---|---|---|---|
| remove | us-al | statute | 2026-07-13-recovery |
| add | us-al | statute | 2026-09-14-income-tax-chapter-us-al-title-40 |
| remove | us-az | statute | 2026-07-13-recovery |
| add | us-az | statute | 2026-09-14-income-tax-chapter-us-az-title-43 |
| remove | us-ca | statute | 2026-07-06-ca-rtc-pit-core-us-ca-sections-rtc-17041-rtc-17043-rtc-17045-rtc-17052-rtc-17054-rtc-17073.5 |
| remove | us-ca | statute | 2026-07-13-recovery |
| add | us-ca | statute | 2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7 |
| remove | us-ct | statute | 2026-07-13-recovery |
| add | us-ct | statute | 2026-09-14-income-tax-chapter-title-12-chapter-229 |
| add | us-ct | statute | 2026-09-14-income-tax-chapter-title-17b |
| remove | us-de | statute | 2026-07-13-recovery |
| add | us-de | statute | 2026-09-14-income-tax-chapter-us-de-title-30-chapter-11 |
| remove | us-id | statute | 2026-07-31-id-title-63-chapter-30-successor |
| add | us-id | statute | 2026-09-14-income-tax-chapter-us-id-title-63-chapter-30 |
| remove | us-ky | statute | 2026-07-22-individual-income-tax |
| add | us-ky | statute | 2026-09-14-income-tax-chapter |
| remove | us-md | statute | 2026-07-13-recovery-r2026-07-24-immutable |
| add | us-md | statute | 2026-09-14-income-tax-chapter-us-md-article-gtg |
| remove | us-me | statute | 2026-07-13-recovery |
| add | us-me | statute | 2026-09-14-income-tax-chapter-us-me-title-36 |
| remove | us-mi | statute | 2026-07-13-recovery |
| add | us-mi | statute | 2026-09-14-income-tax-chapter-us-mi-chapter-206 |
| remove | us-mn | statute | 2026-07-13-recovery |
| add | us-mn | statute | 2026-09-14-income-tax-chapter-us-mn-title-290 |
| add | us-mn | statute | 2026-09-14-income-tax-chapter-us-mn-title-142g |
| add | us-mn | statute | 2026-09-14-income-tax-chapter-us-mn-title-256p |
| remove | us-ne | statute | 2026-07-13-recovery |
| add | us-ne | statute | 2026-09-14-income-tax-chapter-us-ne-title-77 |
| remove | us-ny | statute | 2026-07-06-ny-tax-article22-core-us-ny-sections-tax-601-tax-606-tax-614-tax-615-tax-616 |
| remove | us-ny | statute | 2026-07-13-recovery |
| add | us-ny | statute | 2026-09-14-income-tax-chapter |
| remove | us-oh | statute | 2026-07-13-recovery |
| add | us-oh | statute | 2026-09-14-income-tax-chapter-us-oh-title-57 |
| remove | us-ut | statute | 2026-07-13-recovery |
| add | us-ut | statute | 2026-09-14-income-tax-chapter-title-59 |
| remove | us-va | statute | 2026-07-13-recovery |
| add | us-va | statute | 2026-09-14-income-tax-chapter |
| remove | us-mn | guidance | 2026-07-22-mn-income-tax-inflation-adjusted-amounts-2026 |
| add | us-al | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-al | guidance | 2026-09-14-ty2026-indexed-amounts |
| add | us-ar | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-co | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-ct | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-de | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-ga | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-hi | guidance | 2026-09-14-ty2026-indexed-amounts |
| add | us-ia | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-id | guidance | 2026-09-14-ty2026-indexed-amounts |
| add | us-mn | guidance | 2026-09-14-ty2026-indexed-amounts |
| add | us-mo | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-ms | guidance | 2026-09-14-ty2026-indexed-amounts |
| add | us-mt | guidance | 2026-09-14-ty2026-indexed-amounts |
| add | us-nc | guidance | 2026-09-14-ty2026-indexed-amounts |
| add | us-nd | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-nj | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-nm | guidance | 2026-09-14-ty2026-indexed-amounts |
| add | us-ny | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-oh | guidance | 2026-09-14-ty2026-indexed-amounts |
| add | us-ok | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-pa | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-ri | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-sc | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-ut | guidance | 2026-09-14-ty2026-indexed-amounts |
| add | us-va | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-va | guidance | 2026-09-14-ty2026-indexed-amounts |
| add | us-vt | form | 2026-09-14-ty2026-indexed-amounts |
| add | us-wv | guidance | 2026-09-14-ty2026-indexed-amounts |

Rebuild:

```bash
export REQUESTS_CA_BUNDLE=$PWD/data/certs/state-tax-statute-ca-bundle.pem
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
# adapter-driven chapters (AL, AZ, CT 229 + 17b, DE, ID, MD, ME, MI, MN 290 + 142G + 256P, NE, OH, UT)
uv run axiom-corpus-ingest extract-state-statutes --base $B --manifest manifests/state-income-tax-chapters-2026-09-14.yaml
# index-driven section manifests (KY, VA, NY) and the CA section list
uv run python scripts/build_state_tax_statute_ty2026_manifests.py --family statute
for m in us-ky-krs-chapter-141-income-taxes us-va-code-title-58.1-chapter-3-income-tax us-ny-tax-law-article-22-personal-income-tax; do
  uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-14-income-tax-chapter \
    --manifest manifests/$m.yaml --source-as-of 2026-09-14
done
uv run axiom-corpus-ingest extract-california-code-sections --base $B --version 2026-09-14-income-tax-chapter \
  --source-as-of 2026-09-14 --expression-date 2026-09-14 --delay-seconds 0.3 \
  $(cat manifests/us-ca-rtc-part-10-10.2-sections.args | tr '\n' ' ')
uv run --extra dev python scripts/self_contain_usc_scope.py --base $B --jurisdiction us-ca --document-class statute \
  --version 2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7
# TY2026 indexed amounts
uv run python scripts/build_state_tax_statute_ty2026_manifests.py --family amounts
for m in manifests/us-*-ty2026-amounts.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-14-ty2026-indexed-amounts \
    --manifest $m --source-as-of 2026-09-14
done
AXIOM_CORPUS_BASE=$B uv run python scripts/build_state_tax_statute_ty2026_manifests.py --family queue
uv run axiom-corpus-ingest validate-release --base $B \
  --release docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.selector.json --ignore-r2-missing --max-issues 50
```
