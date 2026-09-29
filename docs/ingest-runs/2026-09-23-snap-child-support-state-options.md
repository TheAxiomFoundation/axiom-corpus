# SNAP child support exclusion/deduction state option: state sources

Date: 2026-09-23 (America/New_York; the fetches ran 2026-09-24 02:58-02:59 UTC).
Branch `ingest-snap-state-options`, cut from `origin/main` 942e138e7. On
2026-09-24 an adversarial review found three extraction defects in the
California and Delaware PDFs; the fixes, merges of `origin/main` 376cd894d and
233dcac58 and the regenerated CA and DE artifacts are described under "Review
fixes (2026-09-24)".

Purpose: an Axiom encoding of SNAP's child support option needs the governing
text in the corpus. 7 CFR 273.9(c)(17) excludes legally obligated child support
paid to or for a nonhousehold member from income, and lets the state agency
deduct it under 7 CFR 273.9(d)(5) instead. policyengine-us had each state's
election inverted (policyengine-us PR #9586, parameter
`gov.usda.snap.income.deductions.child_support`), and that error reached a
PolicyBench reference. This run checked every state source that PR cites,
confirmed the ones the corpus already holds, and ingested the rest.

No publication, R2 upload, Supabase load, release or activation step was run.

## Already in the corpus (confirmed, not re-taken)

Each row below was read from the committed provisions file, and the child
support text was found in its body. "Selected" means the scope is in
`manifests/releases/us-rulespec-2026-09-14-wave4-r2-union.json`.

| source | citation path | scope (selected) | expression date | where the rule is |
|---|---|---|---|---|
| 7 CFR 273.9 | `us/regulation/7/273/9` | `us/regulation/2026-05-10-snap-7-cfr-273-r2026-07-15-self-contained` (selected); also `2026-07-15-title-7-part-273` (2026-07-09) | 2026-04-29 | (c)(17) and (d)(5) are in the section body; the anchor layer (`data/corpus/anchors/us/regulation/2026-05-10-snap-7-cfr-273.jsonl`) has `us/regulation/7/273/9/d/5` but no `.../c/17` anchor |
| CA MPP 63-502.2(p) | `us-ca/regulation/cdss-mpp/division-63/fsman05/block-4` | `us-ca/regulation/2026-07-17-ca-cdss-mpp-calfresh` (selected) | 2008-07-01 | block heading "63-502 INCOME, EXCLUSIONS AND DEDUCTIONS"; paragraph (p) |
| CO 10 CCR 2506-1 section 4.407.5 | `us-co/regulation/10-ccr-2506-1/4.407.5` | `us-co/regulation/2026-07-16-10-ccr-2506-1` (selected) | 2026-07-16 | "Child Support Expense Exclusion", paragraph A |
| DE DSSM 9059 | `us-de/regulation/title-16/9000-food-stamp-program/9059` | `us-de/regulation/2026-07-17-de-snap-rules` (selected) | 2025-12-01 | item 26, "Child Support Payments"; source is regulations.delaware.gov, not the Cornell LII copy PR #9586 links |
| IL PM 13-01-07 | `us-il/manual/dhs/csmm/16161` | `us-il/manual/2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained` (selected) | 2026-05-27 | "Child Support Income Exclusion", the text as corrected by MR #23.22 |
| MA 106 CMR 363.230(O) | `us-ma/regulation/106-cmr/363/230` | `us-ma/regulation/2026-07-24-ma-dta-regulations-snap-current-union` (selected) | 2024-05-01 | paragraph (O); source is mass.gov, not the Cornell LII copy PR #9586 links |
| MI BEM 500 | `us-mi/manual/mdhhs/bridges/bem/500` | `us-mi/manual/2026-09-11-mi-snap-manual-supersede` (selected) | 2026-04-01 (BPB 2026-007) | pages 5 and 14 |
| MI BEM 554 | `us-mi/manual/mdhhs/bridges/bem/554` | same (selected) | 2026-08-01 (BPB 2026-020) | pages 1, 2, 5, 6 ("CHILD SUPPORT EXPENSES"), 7 and 30 |
| MI BEM 556 | `us-mi/manual/mdhhs/bridges/bem/556` | same (selected); also `2026-07-17-mi-bridges-manual` | 2025-11-01 (BPB 2025-028) | pages 4-5, line 20 "Enter monthly child support expenses" |
| OR OAR 461-140-0266 | `us-or/regulation/chapter-461/division-140/rule-461-140-0266` | `us-or/regulation/2026-09-10-tanf-state-policy-manual-chapter-461-r2026-09-14-150-316-consolidated` (selected); also `2026-09-10-tanf-state-policy-manual-chapter-461` | 2026-09-10 | "Effective January 19, 2023, in the SNAP program ..."; source is the Secretary of State OARD page, not the ODHS PDF PR #9586 links |
| IA Employees' Manual 7-E and 7-F | `us-ia/manual/hhs/em/7-e`, `us-ia/manual/hhs/em/7-f` | `us-ia/manual/2026-07-17-ia-snap-manual` (selected) | 2026-02-13 | 7-F page 17, step 6 "Child support payment deduction" (net income) |
| MO SNAP Manual 1115.035.20 | `us-mo/manual/dss/snap/1115-000-00/1115-035-00/1115-035-20` | `us-mo/manual/2026-05-27-mo-snap-manual-r2026-07-15-self-contained` (selected) | 2026-05-27 | "Child Support Exclusion"; the main text is in `.../1115-035-20/block-1`, and the special cases (ineligible or disqualified members, and payers whose own income is excluded) are in the child rows `.../1115-035-20-NN/block-1` |

Michigan vintage check. On 2026-09-23 the live BEM 500, 554 and 556 PDFs at
`https://mdhhs-pres-prod.michigan.gov/OLMWeb/ex/BP/Public/BEM/{500,554,556}.pdf`
printed BPB 2026-007 (4-1-2026), BPB 2026-020 (8-1-2026) and BPB 2025-028
(11-1-2025), the same bulletins as the selected `2026-09-11-mi-snap-manual-supersede`
rows. No Michigan re-take is needed.

## New scopes

Every source was fetched by `extract-official-documents` with the corpus user
agent, straight from the official publisher. An independent `curl` download
(02:54-02:56 UTC) of the CA and DE PDFs, the IL and MA pages and
22VAC40-601-70 had the same SHA-256 as the retained file in each case. The IL
page's bytes depend on the User-Agent: the corpus user agent
(`OFFICIAL_DOCUMENT_USER_AGENT` in `src/axiom_corpus/corpus/documents.py`) and
curl's default both get the retained 18,059 bytes, but a browser User-Agent gets
18,134 bytes, because the page then wraps its ASP.NET hidden fields in
`<div class="aspNetHidden">`. A re-check on 2026-09-24 at 03:49 UTC with
`OFFICIAL_DOCUMENT_USER_AGENT` matched the retained SHA-256. A second
run of all five manifests into a scratch base at 02:59:36 UTC wrote
byte-identical sources, inventory, provisions and coverage. At 03:12 UTC the IL
and MA scopes were extracted again after a wording fix to their manifests'
`authority_role` metadata; their source bytes were unchanged and only that
metadata field changed in their rows.

| scope | citation path(s) | retained source | official URL | bytes | SHA-256 | rows |
|---|---|---|---|---:|---|---:|
| `us-ca/guidance/2026-09-23-ca-cdss-acl-06-31` | `us-ca/guidance/cdss/acl-2006-06-31` + `/page-1` to `/page-31` | `ca-cdss-acl-2006-06-31.pdf` | <https://www.cdss.ca.gov/lettersnotices/entres/getinfo/acl06/pdf/06-31.pdf> | 412,441 | `4def0ef51b035bc87c1789e508a4a04a2046ab42e1f38c1775c8ec2e9146b8f2` | 32 |
| `us-il/manual/2026-09-23-il-dhs-mr-23-22` | `us-il/manual/dhs/csmm/149614` + `/block-1` to `/block-10` | `il-dhs-csmm-149614.html` | <https://www.dhs.state.il.us/page.aspx?item=149614> | 18,059 | `a1711213ea9b163269e1f3ffb6eb02b00c8d5518b51d406e51646633ac2f9d40` | 11 |
| `us-va/regulation/2026-09-23-va-22vac40-601-snap` | `us-va/regulation/22vac40-601/{10,20,30,40,50,60,70}` + one `/block-1` each | `us-va-regulation-22vac40-601-10.html` | <https://law.lis.virginia.gov/admincode/title22/agency40/chapter601/section10/> | 32,704 | `2794f0d2a6558b59220c16bd3221f2b82dfb04c1fa0666d955f068ab04bf475a` | 14 |
| | | `us-va-regulation-22vac40-601-20.html` | <https://law.lis.virginia.gov/admincode/title22/agency40/chapter601/section20/> | 28,238 | `b240edc33cb2d746d8042501ad263ac88d4fdbbffb56d5883448468660369b81` | |
| | | `us-va-regulation-22vac40-601-30.html` | <https://law.lis.virginia.gov/admincode/title22/agency40/chapter601/section30/> | 28,273 | `216a023de639c6e88965f47ba53a05431eb5864ff2a6aefba96291d468707a94` | |
| | | `us-va-regulation-22vac40-601-40.html` | <https://law.lis.virginia.gov/admincode/title22/agency40/chapter601/section40/> | 40,872 | `e9fd131d26cedbdb71f6a74e2468d9530d6673b0aeb6d047d5f3662d03a904f8` | |
| | | `us-va-regulation-22vac40-601-50.html` | <https://law.lis.virginia.gov/admincode/title22/agency40/chapter601/section50/> | 27,680 | `efac59d77ada71b99d8d200be5488f6e65b9ca5655953e58dd3d69aa62bf4acc` | |
| | | `us-va-regulation-22vac40-601-60.html` | <https://law.lis.virginia.gov/admincode/title22/agency40/chapter601/section60/> | 28,635 | `088b3095949e3daa71de85653a7bcfdaeeccbbadd0116f1fbd8386c85b25dcdb` | |
| | | `us-va-regulation-22vac40-601-70.html` | <https://law.lis.virginia.gov/admincode/title22/agency40/chapter601/section70/> | 28,156 | `725fd2a4294d44331067d9306f5547200a44366f08c6f36f6582cc43dd5cf72f` | |
| `us-de/rulemaking/2026-09-23-de-register-13-de-reg-1550` | `us-de/rulemaking/delaware-register/2010-06-01/13-de-reg-1550` + `/page-1` to `/page-23` | `de-register-13-de-reg-1550.pdf` | <https://archive.regulations.delaware.gov/register/june2010/final/13%20DE%20Reg%201550%2006-01-10.pdf> | 244,442 | `d926537b3b6563fb0b518a13d7283e801a5f6058269cbbc81c2e44ee0d348af5` | 24 |
| `us-ma/guidance/2026-09-23-ma-dta-policy-online-snap-child-support` | `us-ma/guidance/dta/policy-online/snap/child-support-expenses-deduction` + `/block-1` to `/block-6` | `ma-dta-policy-online-snap-child-support-expenses-deduction.html` | <https://eohhs.ehs.state.ma.us/DTA/PolicyOnline/BEACON5/%21SSL%21/WebHelp/SNAP/ExpensesDeductions/Ex_CSExpDed.htm> | 24,214 | `df44456eac9ce03fdd29a79007b37012af9db3c85cf7486ca291c8d5f455bef4` | 7 |

Retained paths are under `data/corpus/sources/<scope>/official-documents/`.
Coverage is complete for all five scopes: 32/32, 11/11, 14/14, 24/24 and 7/7,
with no missing, extra or duplicate rows. Both PDFs have embedded text on every
page (31 and 23 pages), so every page row has a body. The CA and DE rows are
extracted with the manifest `extraction` settings described in their sections
below; the row counts, citation paths and retained PDFs did not change when
they were added.

### California: CDSS ACL 06-31

`manifests/us-ca-cdss-acl-06-31.yaml`. The letter is dated August 16, 2006
(`expression_date`) and takes effect October 1, 2006 (`metadata.effective_date`).
Page 2: legally obligated child support paid to a nonhousehold member is "now
treated as income exclusions rather than deductions per MPP 63-502.2(p)", taken
before the gross income test. Page 8 carries the amended text of
MPP 63-502.2(p). Citation path and document class follow the released CDSS
letters (`us-ca/guidance/cdss/acl-2014-14-56` and siblings). The URL is the one
the CDSS 2006 All County Letters index links; the legacy
`https://www.cdss.ca.gov/getinfo/acl06/pdf/06-31.pdf` path that PR #9586 cites
served the same bytes (same SHA-256) and is recorded as
`metadata.alternate_source_url`.

Extraction settings (manifest `extraction`):

- `ignore_actual_text: true`. The PDF is tagged, and two structure elements
  carry an empty `/ActualText`: the one holding the page-1 "Changes include:"
  paragraph (MCIDs 53 and 54) and one on page 15 holding the struck MPP
  63-503.311(g) and the relettered "(hg) (Continued)" and "(ih) (Continued)"
  after it (MCIDs 70-74). MuPDF substitutes the empty replacement text for the
  visible glyphs, so the first extraction dropped both passages (883
  characters on page 1). With the flag, extraction reads the glyphs. Only
  pages 1 and 15 change; every other page's text is byte-identical.
- `amendment_markup`, pages 7 to 23 (Attachment A, the proposed regulations).
  The attachment prints deleted text struck through and inserted text
  underlined, both as drawn rules. The rows now carry that status as
  `[-deleted-]` and `{+inserted+}` (see `docs/corpus-pipeline.md`, "Amended
  rule text in PDFs"), and each marked page's `metadata.amendment_markup`
  records the notation and its run counts. For example, page 12 now reads
  `.38 [-Child Support Deduction-]` with clauses (a) to (f) each struck, and
  page 8 reads `{+(p) Child Support payments that a household member pays to
  or for an individual living outside of the household.+}` followed by the
  inserted (1) to (6). The letter (pages 1-6) and Attachments B to D (pages
  24-31) are not marked: their underlines are emphasis ("For new
  applications:") or form layout, not amendments.
- `typographic_underlines: [Jones v. Yeutter, "Hamilton v. Lyng;"]`. In the
  MPP 63-502 and 63-503 Reference notes (pages 13 and 16) only the party names
  are underlined, not "v."; the orders date from 1988 and 1990, and the corpus's
  current MPP text (`us-ca/regulation/cdss-mpp/division-63/fsman06/block-2` and
  `fsman07/block-2`) carries both citations. They are citation typography, so
  they are written without insertion delimiters.

Checks on the marked attachment: removing the delimiters from each page gives
exactly that page's text without markup. Every horizontal rule drawn on pages
7 to 23 is accounted for by a struck or underlined character, except two
short rules on page 16 that sit under spaces (the underlined blanks for the
volume and page of "F. Supp."); spaces carry no status. No character is both
struck and underlined. Pages 9, 10, 12, 15 and 20, and parts of pages 8, 11
and 16, were compared by eye with renderings of the PDF, including
the superscripts on page 8 (`[-18th-] {+19th+}`, where the struck "th" has its
own rule) and page 11 (`October {+1st+}`).

### Illinois: IDHS Manual Release #23.22

`manifests/us-il-dhs-mr-23-22.yaml`. Released 06/30/2023 (`expression_date`).
It "corrects the policy reference to the Child Support Deduction in
PM 13-01-07" and says "Illinois implemented the income exclusion in June 2004"
(block-2). The page
is part of the Cash, SNAP, and Medical Manual (breadcrumb: Manuals > Family &
Community Services Manuals > Cash, SNAP, and Medical Manual > Manual Releases)
and is listed on the Manual Releases index (item 12448). It therefore uses the
released manual's class and path convention (`us-il/manual/dhs/csmm/<IDHS item
id>`) and its `#Main2` content selector and drop selectors. The corrected
PM 13-01-07 itself is already in the corpus (table above).

### Virginia: 22VAC40-601

`manifests/us-va-22vac40-601-snap-regulation.yaml`: all seven sections the
publisher's chapter index lists (10, 20, 30, 40, 50 [repealed], 60, 70), one
document row and one block row each. Path and class follow the released
`us-va/regulation/22vac30-80/<section>` scope (the Title 22 precedent),
including its convention that `expression_date` is the fetch date, because LIS
serves only the current text; each section's historical notes are in its body
and in `metadata.historical_notes`. 22VAC40-601-70: "Legally obligated child
support payments paid by a SNAP household member to or for a nonhousehold member
will be allowed as an exclusion from countable income for SNAP purposes",
derived from Virginia Register Volume 35, Issue 3, eff. October 31, 2018.
`extract-virginia-vac` was not used: it writes a `us-va/regulation`
collection row (as in the selected
`us-va/regulation/2026-09-14-income-tax-regulations-title-23-agency-10-chapter-110-140`
scope, which already owns that path), and a profiled release rejects a citation
path that two selected scopes both carry (`duplicate_release_citation` in
`src/axiom_corpus/corpus/release_quality.py`). LIS prints the fetch date on
every section page (9/23/2026), so a fetch on a later day will not reproduce
these source hashes.

### Delaware: 13 DE Reg. 1550

`manifests/us-de-register-13-de-reg-1550.yaml`. The Delaware Register's final
order for DSSM 9059 (DSS Final Order Regulation #10-26), published June 1, 2010
(`expression_date`). Page 2: the Division "has elected to change the treatment of
child support payments made by a FSP household member to an income exclusion
instead of a deduction", and the regulation "is adopted and shall be final
effective June 10, 2010". Page 22 carries the adopted item 26. The retained
file is the PDF that the register's HTML page links as its "Authenticated PDF
Version"; the HTML URL is in `metadata.html_version_url`.

Extraction settings (manifest `extraction`):

- `amendment_markup` from page 2. From "9059 Income Exclusions" on page 2 the
  order prints the whole of DSSM 9059: the old text struck through (to "13 DE
  Reg. 937 (01/01/10)" on page 16), then the new text underlined. The rows mark
  them `[-...-]` and `{+...+}`, so the deleted example on page 3 in which "the
  $800 is budgeted" despite $400 of court-ordered child support reads as
  deleted, and page 16 separates the struck end of the old section (items R
  and S and the "13 DE Reg. 937 (01/01/10)" history line) from the inserted
  new text. The register's closing line on page 23 ("13 DE Reg. 1550
  (06-01-10) (Final)") is not underlined and is not marked.
- `sort_blocks: true`. Pages 17 and 22 draw a shaded box ("Exceptions:" under
  item E, Educational Income; "Exception:" under item 26, Child Support
  Payments) last in the content stream, so content-order extraction placed the
  box text at the end of the page, after heading V on page 22 and in the middle
  of item H's sentence on page 17. Block sort places each box where it is
  printed. Only those two pages change order.

The PDF stays the text source: the register labels it the authenticated
version, the scope's citation paths are its pages, and the HTML page carries
the same markup. The HTML was used as an independent check instead.
`scripts/compare_pdf_amendment_markup_with_html.py` labels every word of the
HTML by its `text-decoration` (`line-through` deleted, `underline` inserted)
and every word of the marked PDF rows, and aligns the two from the first marked
word to the last. On the HTML fetched 2026-09-24 18:24:36 UTC (292,728 bytes,
SHA-256 `9f299bd1d75731a9139cd04917e2b54767bad24ffadda59dff79f2baf01011fd`, not
retained): 8,072 deleted words on both sides, 4,070 inserted words in the HTML
and 4,072 in the PDF, and no differing stretch with different labels. The 17
differing stretches are spelling or spacing only: 11 non-breaking hyphens in
the HTML ("non‑household"), and six spacing differences, four where the PDF
text breaks a word after a line-end hyphen or slash ("non- household",
"9/ 25/90,") and two where one rendering has a space the other lacks
("(viii)Reimbursements", "16.P.").
The alignment has no reordering, so the HTML also confirms where the two boxes
belong.

Class and path. A register publication is regulatory activity, not compiled
law, so it is `rulemaking` (as `docs/corpus-pipeline.md` puts the Federal
Register). The path mirrors the Federal Register family
`us/rulemaking/federal-register/<publication date>/<document>`:
`us-de/rulemaking/delaware-register/2010-06-01/13-de-reg-1550`. This is the
first `us-de/rulemaking` scope. The compiled rule it adopted is the
already-selected `us-de/regulation/title-16/9000-food-stamp-program/9059`.

### Massachusetts: DTA Policy Online, child support expenses

`manifests/us-ma-dta-policy-online-snap-child-support.yaml`. The page's "Last
Update" line reads January 5, 2023 (`expression_date`). It is DTA's
operational policy on child support expenses: legally obligated child support
is subtracted from gross income for the gross income test, then added back and
allowed as a deduction in the benefit calculation (block-2 and the worked
example in block-3). The page cites 106 CMR 364.370 for the gross income test;
the exclusion itself is codified at 106 CMR 363.230(O) (table above), which
excludes the payments "for the purpose of applying the appropriate gross income
test". Massachusetts is therefore a hybrid: it excludes the payments for the
gross income test only, and the benefit calculation deducts them. An encoding,
and the follow-up to policyengine-us PR #9586 (which sets MA to the exclusion
from 2017-01-13), should not treat MA like a state that excludes the payments
throughout. Path follows the released
`us-ma/guidance/dta/policy-online/...` DTA pages. The manifest's
`html_content_selector` (`#rh-topic > div:has(> h1)`) keeps only the topic
body; without it the first run produced a block for the mass.gov "official
website" banner and one for the site-policy footer. The "Last Update" line is
inside that selector, but it is the page's final `<h3>` with no text after it,
so the generic HTML block extractor (`_extract_html_blocks` in
`src/axiom_corpus/corpus/documents.py`) takes it as a heading and emits no
block for it. The date is carried by `expression_date`, `metadata.last_update`
and `metadata.expression_date_note`, and by the retained HTML.

## Not ingested

- **USDA FNS SNAP State Options Reports, 14th to 17th editions.** AGENTS.md
  says not to ingest secondary summaries "such as State Options Reports" unless
  explicitly directed for a separate non-canonical experiment, and every agent
  queue (for example `manifests/snap-completion-agent-queue.yaml`) lists them
  under `forbidden_sources`. `docs/ingest-runs/2026-09-13-federal-guidance-layer.md`
  kept the report (`snap_g16`) out on the same ground. The official URLs
  (all HTTP 200 on 2026-09-23) are recorded here for whoever decides otherwise:
  - 14th (options as of October 1, 2017): <https://fns-prod.azureedge.us/sites/default/files/snap/14-State-Options.pdf> (6,879,323 bytes)
  - 15th (FY 2023): <https://fns-prod.azureedge.us/sites/default/files/resource-files/snap-15th-state-options-report-october23.pdf> (1,951,320 bytes)
  - 16th (as of October 1, 2023): <https://fns-prod.azureedge.us/sites/default/files/resource-files/snap-16th-state-options-report-june24.pdf> (5,475,501 bytes)
  - 17th (October 2024): <https://fns-prod.azureedge.us/sites/default/files/resource-files/snap-stateOptionsReport-17edition-120925.pdf> (5,872,573 bytes)

  PR #9586 takes most states' values (every state without a state-rule
  comment) from these reports alone. An encoding that must not rely on the
  report reads each of those states' elections from the state SNAP manuals and
  regulations the corpus already holds; this run did not map those states.
- **Cornell LII copies** of DSSM 9059 and 106 CMR 363.230 (links in PR #9586):
  secondary. The corpus holds both rules from the official publishers (table
  above).
- **Wayback Machine captures** of the 106 CMR 363 PDF that PR #9586 uses to date
  363.230(O) to Mass Register Issue 1330 (2017-01-13): archived copies are a
  forbidden source. The corpus holds the current 106 CMR 363 (2024-05-01).
- **Missouri income maintenance memos** that the selected 1115.035.20 rows cite
  in their history lines: IM-134 (December 21, 2021), IM-54 (May 15, 2020),
  IM-34 (March 15, 2013), IM-111 (October 22, 2004) and IM-10 (February 16,
  1999). None was fetched in this run.
  - IM-54 and IM-134 are the May 2020 and December 2021 memos that PR #9586
    reports are no longer online. The DSS memo index
    (<https://dssmanuals.mo.gov/wp-content/themes/mogovwp_dssmanuals/public/memos/>)
    lists income maintenance memo years 1992 to 2018 only.
  - IM-111, IM-34 and IM-10 are online and linked from that index (HTTP 200
    with the corpus user agent on 2026-09-24):
    <https://dssmanuals.mo.gov/wp-content/themes/mogovwp_dssmanuals/public/memos/memos_04/im111_04.html>,
    <https://dssmanuals.mo.gov/wp-content/themes/mogovwp_dssmanuals/public/memos/memos_13/im34_13.html>
    and
    <https://dssmanuals.mo.gov/wp-content/themes/mogovwp_dssmanuals/public/memos/memos_99/im10_99.html>.
    IM-111 is the cover memo for Food Stamp Manual Revision #28; it lists
    1115.035.20 among the revised sections, which it says discuss "child
    support deductions". PR #9586 cites it as describing a deduction.
  - IM-34 bears on dating Missouri's election. When an ineligible or
    disqualified member's income is prorated, it says child support paid by
    EU members "is excluded from the household's gross income", and it
    refers to an earlier "child support exclusion". That suggests Missouri
    applied the exclusion by March 2013, before the 2020 or 2021 switch that
    PR #9586 infers. Whoever dates Missouri's election should read IM-34.
- **Virginia Register Volume 35, Issue 3**, the 2018 final regulation that
  added 22VAC40-601-70: not needed for the rule text; the section's
  historical note records it.

## Citation-path ratchet

The new rows add 23 `block-N` paths (IL 10, VA 7, MA 6) and 54 `page-N` paths
(CA 31, DE 23), all the default segments `extract-official-documents` gives
unsectioned HTML and PDF bodies. The review fixes changed no citation path.
After the merge of `origin/main` 376cd894d (which had raised `block_n` to
75,770 for PR #734), `schema/citation-path.v1.json` sets `block_n` to 75,793
and `page_n` to 150,647, recounted on the merged tree; no other family moves.
The later merge of 233dcac58 (PR #733) needed no change. With these baselines
`scripts/validate_citation_paths.py` passes over 581,359 records (430,064
unique paths) on the tree merged with 233dcac58. Other open ingest branches may move these
baselines too, so whichever merges later must recompute the counts on the
merged tree rather than take either side of the conflict.

## Commands

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-23-ca-cdss-acl-06-31 --manifest manifests/us-ca-cdss-acl-06-31.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-23-il-dhs-mr-23-22 --manifest manifests/us-il-dhs-mr-23-22.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-23-va-22vac40-601-snap --manifest manifests/us-va-22vac40-601-snap-regulation.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-23-de-register-13-de-reg-1550 --manifest manifests/us-de-register-13-de-reg-1550.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-23-ma-dta-policy-online-snap-child-support \
  --manifest manifests/us-ma-dta-policy-online-snap-child-support.yaml
```

The CA and DE manifests carry the extraction settings described above, so the
same commands reproduce the fixed rows. They were rerun on 2026-09-24 at
18:13:28-18:13:35 UTC: both PDFs downloaded again with the retained SHA-256,
the coverage files were unchanged, and the provisions and inventory changed
only as described under "Review fixes (2026-09-24)". A second run of both
manifests into a scratch base (18:29-18:30 UTC) wrote byte-identical sources,
inventory, provisions and coverage. The IL, VA and MA scopes were not rerun.

The artifacts sit under the ignored `data/` tree, so the ingest commit
force-adds the `sources/`, `inventory/`, `provisions/` and `coverage/` paths of
the five scopes. `.gitattributes` marks the retained HTML of the IL, VA and MA
scopes binary, as for other retained HTML; the PDFs are already covered by
`data/corpus/sources/**/*.pdf binary`.

Each scope's signed ingest manifest under `.axiom/ingest-manifests/` attests
this note by SHA-256 as its reasoning log, with the matching command above.
They are signed from the clean commit that contains this note's final text, so
this note does not record the `guard-ingested` result; the pull request does.

## Verification

- Coverage is complete for all five scopes (counts above).
- Each new citation path was checked against every provisions file of its
  jurisdiction on the tree merged with 233dcac58 (30 for us-ca, 15 us-il, 21
  us-va, 22 us-de, 31 us-ma): no collisions.
- A local draft selector (the 101 `us-ca`, `us-il`, `us-va`, `us-de` and `us-ma`
  scopes of `us-rulespec-2026-09-14-wave4-r2-union` plus the five new scopes)
  passes `validate-release` with 0 errors, rerun after the review fixes. Its 541
  warnings are all `missing_parent_id` on `us-ca/regulation/2026-07-13-recovery`,
  the same 541 the selector gives without the new scopes; none is on a new
  scope.
- Re-fetch reproducibility and byte identity with an independent download:
  see "New scopes".
- `scripts/validate_citation_paths.py`: see "Citation-path ratchet".
- Tests: `tests/test_us_snap_child_support_state_sources.py` pins each review
  finding against the committed rows and re-extracts both retained PDFs under
  their manifests' settings; `tests/test_corpus_documents_pdf_amendment_markup.py`
  covers the three extraction keys on generated PDFs;
  `tests/test_compare_pdf_amendment_markup_with_html.py` covers the HTML check.

## Review fixes (2026-09-24)

An adversarial review of PR #736 at 96f2db85c found three major defects. Each
was confirmed on the retained PDFs before it was fixed.

1. California page 1 omitted the six-item "Changes include:" paragraph,
   including the child support change and the pointer to Attachment A.
   Confirmed: the paragraph is visible in the PDF and `pdftotext` reads it, but
   PyMuPDF did not, because of the empty `/ActualText` described in the
   California section. The same cause had also dropped the struck
   63-503.311(g) ("Subtract allowable monthly child support payments ...") on
   page 15, which the review did not list. Fixed with `ignore_actual_text`.
2. Strike-through deletions read as ordinary text: California page 12 (the
   struck `.38 Child Support Deduction` and its clauses (a) to (f)) and
   Delaware page 3 (the deleted example that budgets all $800 of retirement
   income), with Delaware page 16 joining deleted and replacement text.
   Confirmed on renderings of both PDFs; the markup is drawn rules on every
   page of CA Attachment A and DE pages 2 to 23. Fixed with `amendment_markup`.
3. Delaware page 22 placed the child support exception after heading V instead
   of after item 26. Confirmed: the box is drawn last in the content stream.
   Page 17's "Exceptions:" box under item E had the same fault, which the
   review did not list. Fixed with `sort_blocks`.

The three keys are new, opt-in `extraction` settings for
`extract-official-documents` PDFs (`src/axiom_corpus/corpus/documents.py`);
without them, PDF extraction is unchanged. As a check, 116 retained PDFs from
existing scopes (sampled across every combination of `segmentation`,
`sort_text` and `text_replacements` the manifests use, OCR scopes excluded; 3,997
blocks) were extracted with the `origin/main` and the branch versions of
`documents.py`: every block was identical. For both fixed scopes, removing the
delimiters from each page gives the text the first extraction produced, except
California pages 1 and 15 (recovered text) and Delaware pages 17 and 22 (the
same words, reordered).
