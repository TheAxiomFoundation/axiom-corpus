# SNAP child support elections: cited state primary sources

Date: 2026-09-28. Branch `ingest/snap-child-support-cited-sources-2`, cut from
`origin/main` 32d1f9528dc44269cad078b3818a47a51cc06b91. The work was drafted on
2026-09-27 in `ingest/snap-child-support-cited-sources` (never committed), reviewed,
corrected and re-extracted here; "Review and corrections" below lists what changed.

## Purpose

Retain the official state sources behind each state's election under 7 CFR 273.9 for
legally obligated child support paid to a nonhousehold member, and its history from
2010. Under 273.9(c)(17) the payments are an income exclusion; "at its option, the
State agency may allow households a deduction ... in accordance with paragraph (d)(5)
... rather than an income exclusion" (both in scope
`us/regulation/2026-07-15-title-7-part-273`, row `us/regulation/7/273/9`). The
discovery checklist was the state primary sources that the policyengine-us parameter
`gov/usda/snap/income/deductions/child_support.yaml` and PR #9622 cite and the corpus
lacked, after axiom-corpus #736 took CA, IL, VA, DE and MA. Those citations are leads,
not source text. Every source here was fetched live from its official publisher. No
USDA SNAP State Options Report, archive capture or secondary copy was used (decision
d325; AGENTS.md).

## Scopes

Fifteen scopes, fourteen from `extract-official-documents` manifests and one from the
Maryland COMAR adapter. Retained files sit under
`data/corpus/sources/<scope>/official-documents/` (Maryland:
`.../maryland-comar-xml/`). Coverage is complete for every scope, with no missing,
extra or duplicate rows.

| scope | citation paths | retained source | official URL | bytes | SHA-256 | rows |
|---|---|---|---|---:|---|---:|
| `us-ar/manual/2026-09-28-ar-snap-manual-2020-02-01` | `us-ar/manual/dhs/snap-policy-manual/vintage/2020-02-01` + `/page-1` to `/page-1057` | `ar-dhs-snap-manual-2020-02-01.pdf` | <https://humanservices.arkansas.gov/wp-content/uploads/Complete_SNAP_Manual.pdf> | 10,016,438 | `8dc2bfbcd8a46e485adb3fdd9631b6d80228c963f99a3d057b16be24fcd6c309` | 1058 |
| `us-co/regulation/2026-09-28-co-10-ccr-2506-1-2009-07-01` | `us-co/regulation/10-ccr-2506-1/vintage/2009-07-01` + `/page-1` to `/page-236` | `co-10-ccr-2506-1-2009-07-01.pdf` | <https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=3031&fileName=10%20CCR%202506-1> | 1,742,000 | `702e55452624351ee1027502637369a3a65cfa0317d9d27378420894abbfeeaf` | 237 |
| `us-hi/regulation/2026-09-28-hi-har-17-676-2012-01-06` | `us-hi/regulation/har/17/676/vintage/2012-01-06` + `/page-1` to `/page-73` | `hi-dhs-har-17-676-2012-01-06.pdf` | <https://humanservices.hawaii.gov/wp-content/uploads/2014/01/17-676.pdf> | 175,324 | `9ed9a56f7f4e5fdf03cece5fa221e7900662b562beec3642329726093c88986f` | 74 |
| `us-la/regulation/2026-09-28-la-lac-title-67-part-iii-compilation-2026-08` | `us-la/regulation/lac/67/iii` + 311 section rows | `la-osr-lac-67-iii.docx` | <https://www.doa.la.gov/media/oq1j3hys/67.docx> | 1,081,819 | `929dea17d238ba30424bd0f4c631e69ae8b933e550e3a5b6940fd63a15d1c28f` | 312 |
| `us-la/rulemaking/2026-09-28-la-register-2003-04-20-vol-29-no-4` | `us-la/rulemaking/louisiana-register/2003-04-20/vol-29-no-4` + `/page-1` to `/page-145` | `la-register-2003-04-20-vol-29-no-4.pdf` | <https://www.doa.la.gov/media/m23b1mhf/0304.pdf> | 2,415,464 | `3c853f00686b5be1aee4cef3940936bec06cd8db056f63f778f0aa776753fd9f` | 146 |
| `us-mo/guidance/2026-09-28-mo-dss-im-34-2013` | `us-mo/guidance/dss/im-2013-34` + `/block-1` to `/block-8` | `mo-dss-im-34-2013.html` | <https://dssmanuals.mo.gov/wp-content/themes/mogovwp_dssmanuals/public/memos/memos_13/im34_13.html> | 16,758 | `8b7379beb096fcc1adc258569dd374cb1acb483c68a9d5bc01da84a449b1bd51` | 9 |
| `us-mo/guidance/2026-09-28-mo-dss-im-39-2003` | `us-mo/guidance/dss/im-2003-39` + `/block-1` | `mo-dss-im-39-2003.html` | <https://dssmanuals.mo.gov/wp-content/themes/mogovwp_dssmanuals/public/memos/memos_03/im39_03.html> | 24,250 | `8709c83799a3ae48a25f6506dde7a2c37b8f73e574cfbfcc872f2637660d4b30` | 2 |
| `us-nc/guidance/2026-09-28-nc-dss-es-al-6-2005` | `us-nc/guidance/dss/administrative-letters/economic-services/2005/6` + `/page-1` to `/page-2` | `nc-dss-es-al-6-2005.pdf` | <https://policies.ncdhhs.gov/wp-content/uploads/es_al-6-2005.pdf> | 72,241 | `ab742e6d7a4f7792b7641af357bd9f3b41d4089704bcb0cf0914ec5f483a48d4` | 3 |
| `us-nj/statute/2026-09-28-nj-pl-2013-c45` | `us-nj/statute/session-laws/2013/c45` + `/block-1` | `nj-pl-2013-c45.html` | <https://pub.njleg.gov/bills/2012/PL13/45_.HTM> | 44,422 | `7446947a23370100dc106ba8b948222b2e7479ff3d2518f6d282344de24aa360` | 2 |
| `us-nj/rulemaking/2026-09-28-nj-prn-2016-017` | `us-nj/rulemaking/new-jersey-register/2016-05-02/prn-2016-017` + `/page-1` to `/page-20` | `nj-prn-2016-017.pdf` | <https://www.nj.gov/humanservices/notices/documents/rule-proposals/(F)%20PRN%202016-017%20(DHS-DFD%2010_87-1.11).pdf> | 65,025 | `64f265bc860a1f675099484f7ab1d2abf8c7e7c933c6d0f6626d99e0da5c893f` | 21 |
| `us-ri/regulation/2026-09-28-ri-218-820-snap-rules-2014-10-01` | `us-ri/regulation/218-820/vintage/2014-10-01` + `/page-1` to `/page-311` | `ri-218-820-snap-rules-2014-10-01.pdf` | <https://risos-apa-production-public.s3.amazonaws.com/DHS/7907.pdf> | 1,282,467 | `23027ddc2d875cc3057d844c70c0963ddbd17f302f47a6f6097bee488aec7912` | 314 |
|  | `us-ri/regulation/218-820/vintage/2014-10-01/filing-record` + `/block-1` | `ri-218-820-snap-rules-2014-10-01-filing-record.html` | <https://rules.sos.ri.gov/Regulations/part/218-XXX-XX-820?reg_id=7907> | 230,012 | `0437731a2b21e71e6cf470605359faf097439c9c4be9e3aeef3626c059a8ee47` |  |
| `us-vt/rulemaking/2026-09-28-vt-dcf-b18-06f` | `us-vt/rulemaking/dcf/2018-12-10/b18-06f` + `/page-1` to `/page-3` | `vt-dcf-b18-06f.pdf` | <https://outside.vermont.gov/dept/DCF/Shared%20Documents/ESD/Rules-Adopted/B18-06F.pdf> | 152,199 | `5c7d74027d356c28b93b6bbaa46ef43875c0e721f8444e26058bc33d0d8b3812` | 4 |
| `us-wa/rulemaking/2026-09-28-wa-wsr-09-15-085` | `us-wa/rulemaking/washington-state-register/2009-07-14/wsr-09-15-085` + `/block-1` | `wa-wsr-09-15-085.html` | <https://lawfilesext.leg.wa.gov/law/wsr/2009/15/09-15-085.htm> | 9,981 | `d5cb51c135bc2eafc27d7e7a21598f421e1247697dd74f14b613db97a0af8e07` | 2 |
| `us-wa/rulemaking/2026-09-28-wa-wsr-09-16-095` | `us-wa/rulemaking/washington-state-register/2009-08-04/wsr-09-16-095` + `/block-1` | `wa-wsr-09-16-095.html` | <https://lawfilesext.leg.wa.gov/law/wsr/2009/16/09-16-095.htm> | 3,538 | `45b16e4ba01a47f9a29abef748975f8584abff0057b9922f9966e2a28596f477` | 2 |
| `us-md/regulation/2026-09-28-md-snap-comar-publication-2026-09-27-title-07-subtitle-03-chapter-17` | `us-md/regulation/title-07/subtitle-03/chapter-17` + 62 section rows | `17.xml` | <https://github.com/maryland-dsd/law-xml-codified/blob/publication%2F2026-09-27.2026-09-27/us/md/exec/comar/07/03/17.xml> | 297,690 | `a6d536234e1f27d49988b4faec211d94b51d3d8dba485df216689e44cd8e1df7` | 66 |
|  | `us-md/regulation/title-07/subtitle-03` (1 row) | `index.xml` | <https://github.com/maryland-dsd/law-xml-codified/blob/publication%2F2026-09-27.2026-09-27/us/md/exec/comar/07/03/index.xml> | 1,380 | `45c4f854e5a67360ea3e671a37545a921d4900af57697559221f1ab1aaf7e4ca` |  |
|  | `us-md/regulation/title-07` (1 row) | `index.xml` | <https://github.com/maryland-dsd/law-xml-codified/blob/publication%2F2026-09-27.2026-09-27/us/md/exec/comar/07/index.xml> | 877 | `b5d39d14ee78375c6e3e24aab65c8da4a1ec5722d3c73ddcbbfd5af7af88fde0` |  |
|  | `us-md/regulation` (1 row) | `index.xml` | <https://regs.maryland.gov> | 3,517 | `abac0a7a27697fedbb4a642dc44741dbc6b3738938f25ff62e07282d88a526a4` |  |

Maryland's scope also retains the publication's `index.xml` files for the collection,
title and subtitle and the license file `license.md`.

## Scope details

Each subsection gives the printed date that sets `expression_date` and the sentence
that bears on child support treatment, with its row. The tests
(`tests/test_us_snap_child_support_cited_*.py`) pin every quoted sentence in its row.

### Colorado: 10 CCR 2506-1, version effective July 1, 2009

Rule version 3031 of the Code of Colorado Regulations, Rule Manual Volume 4B Food
Stamps. The final editor's history (page 236) prints "Rule Sections SB&P, 4010.11,
4230 eff. 07/01/2009." B-4223.6 (`.../vintage/2009-07-01/page-127`), headed "DEDUCTION
FOR LEGALLY OBLIGATED CHILD SUPPORT PAID TO NONHOUSEHOLD MEMBERS": "The child support
deduction will be made from the household's total countable gross income. The
deduction will be made prior to any gross income test to determine eligibility." In
mechanics this is an exclusion before the gross test, although the rule calls it a
deduction. The Secretary of State's rule-history table lists this version as adopted
05/01/2009 (eDocket 2009-00185) and the next as effective 03/02/2010; those facts are in
`metadata.rule_history_note`, labeled as coming from a page this scope does not retain
(see "Not ingested").

### Louisiana: LAC 67:III (August 2026 compilation) and the April 2003 Register

`us-la/regulation/2026-09-28-la-lac-title-67-part-iii-compilation-2026-08` takes all 311
sections of Part III from the Office of the State Register's Title 67 DOCX, whose footer
prints "Louisiana Administrative Code August 2026". `expression_date` 2026-08-01 encodes
that month (`expression_date_precision: month`). §1980
(`us-la/regulation/lac/67/iii/1980`): "legally obligated child support payments to
non-household members are excluded when determining eligibility based on gross income
standards;". §1981 (`.../iii/1981`): "Legally obligated child support payments to, or
for, an individual living outside of the household must be included in the deductions
from the total monthly income when a budget for SNAP eligibility is determined." So the
payments are excluded for the gross test and deducted in the net budget. §1980's history
prints "LR 29:607 (April 2003)".

`us-la/rulemaking/2026-09-28-la-register-2003-04-20-vol-29-no-4` retains that whole
Register issue as page rows. The rule "Food Stamp Program—2002 Farm Bill (LAC 67:III.1917,
1932, 1949, 1953, 1961, 1965, 1966, 1980, 1983 and 2013)", document 0304#065, runs from
printed page 605 to 607 (PDF pages 94-96). Page 607 (`.../vol-29-no-4/page-96`) adds
§1980.C: "Legally obligated child support payments to non- household members are
excluded when determining eligibility based on gross income standards." Page footers
print "Louisiana Register Vol. 29, No. 04 April 20, 2003". The issue-level metadata
describes the issue; the rule's fields sit under `metadata.relevant_rule`, so the other
agencies' pages are not tagged SNAP.

### Missouri: IM-39 (2003) and IM-34 (2013)

IM-39 (`us-mo/guidance/dss/im-2003-39/block-1`), dated 03/04/03: "Effective for any
budget completed March 10, 2003, and after, exclude (deduct) the child support expense
from the gross income prior to the gross eligibility (130% of Federal Poverty Level -
FPL) test." Its net-income steps subtract the 20% earned income deduction before child
support. IM-34 (`us-mo/guidance/dss/im-2013-34`), dated 03/15/13 and "in effect March 18,
2013", changes the allocation for ineligible or disqualified members (block 4): "When
prorating ineligible or disqualified members' income, all obligated child support paid
by eligible and/or ineligible EU members is excluded from the household's gross
income." It replaces IM-39's ineligible-member steps and revises manual sections
1115.035.20.05, 1115.070.00 and 1115.071.00, whose released rows are listed in
`metadata.manual_sections_revised`.

### New Jersey: P.L. 2013, c.45 and PRN 2016-017

P.L. 2013, c.45 section 10, codified as N.J.S.A. 44:10-104
(`us-nj/statute/session-laws/2013/c45/block-1`): the department and county welfare
agencies "shall exclude from a household’s income all legally-obligated or
court-ordered child support payments paid by a household member to, or on behalf of, a
non-household member ... for the purpose of determining whether a household meets
applicable gross and net SNAP income eligibility standards." The act prints "Approved
April 15, 2013." Section 11 makes it effective "on the first day of the seventh month
next following the date of enactment", which is November 1, 2013
(`effective_date_computed`, labeled as computed).

PRN 2016-017 is DHS's own copy of the proposal published as 48 N.J.R. 695(a) and adopted
as R.2017 d.022, effective February 6, 2017. Both citations come from the history notes of
the amended rules in the released scope `us-nj/regulation/2026-07-17-nj-snap-rules`; the
copy prints only an unlabeled "48 NJR 5(1)". Page 3: "legally obligated child support
paid by a household member will now be considered as an income exclusion, which will
result in this income being eliminated from consideration prior to the household’s gross
income test." Pages 9-20 mark additions and deletions (see "Extraction options"). Pages
10-11 add N.J.A.C. 10:87-5.9(a)20, `{+20. All legally obligated or court-ordered child
support payments ...+}`. Pages 11-12 delete the child support deduction, 10:87-5.10(a)4v
and (a)5, as one `[-...-]` run across the page break.

### North Carolina: Administrative Letter Economic Services No. 6-2005

`us-nc/guidance/dss/administrative-letters/economic-services/2005/6`, dated June 29, 2005,
effective July 1, 2005 (page 1): "Treatment of Legally Obligated Child Support (LSO) paid
by members of the Food Stamp Unit was changed to an income exclusion rather than an
income deduction beginning January 1, 2005." It also says: "FSIS also uses Field 80N to
calculate the LSO amount paid as an income deduction once the gross income test has
been performed." It replaces Administrative Letter No. 11-2004 (December 16, 2004). The
retained PDF is the publisher's 2016 electronic copy (`file_note`).

### Rhode Island: 218-820, emergency amendment effective October 1, 2014

The Secretary of State's filing 7907 of the pre-RICR SNAP rules, Sections 1000-1083
(218-820). The PDF prints only "October 2014". The scope also retains the Secretary of
State's filing record (`.../vintage/2014-10-01/filing-record/block-1`), which prints
"EMERGENCY RULE", "Effective 10/01/2014 to 01/29/2015", the part's later filings
("Amendment - effective from 12/15/2014 to 03/17/2015") and "Repeal - effective from
10/09/2017", when 218-RICR-20-00-1 replaced it. 1008.20.22 REV:05/2005 (page 136): "Legally
obligated child support payments made by a household member to or for a nonhousehold
member are an income exclusion." 1010.20 REV:05/2005 (page 145): child support paid is
"not deductions but ... instead income exclusions". The older 1038.19 REV:09/2000 (page
288) is still headed "CHILD SUPPORT DEDUCTION"; the inconsistency is the source's own.

### Washington: WSR 09-15-085 and WSR 09-16-095

WSR 09-15-085 (`us-wa/rulemaking/washington-state-register/2009-07-14/wsr-09-15-085/block-1`),
filed July 14, 2009, amends WAC 388-450-0015. Its Purpose statement: "The department is
exercising an option from the 2002 farm bill to treat child support payments made to
someone outside of the home as an income exclusion prior to administering the gross
income test." The operative text adds, after "Some examples of income we do not count
are:", `(n) {+For Basic Food Only: The total monthly amount of all legally obligated
current or back child support payments paid by the assistance unit to someone outside of
the assistance unit for:+}`. WSR 09-16-095, filed August 4, 2009: "the department wishes to
change the effective date for WSR 09-15-085 to November 15, 2009", so that a companion
change to WAC 388-450-0185 could take effect with it.

### Maryland: COMAR 07.03.17

`us-md/regulation/2026-09-28-md-snap-comar-publication-2026-09-27-title-07-subtitle-03-chapter-17`,
from the Division of State Documents' official bulk publication `law-xml-codified`,
branch `publication/2026-09-27.2026-09-27`. It has all 62 regulations as children of the
chapter row, with `legal_identifier` (`COMAR 07.03.17.35`), and keeps tables row by row.
.35A (`.../chapter-17/regulation-35`): "A household member who has verification of having
made legally obligated child support payments to or for an individual living outside the
household is allowed a deduction." .43G: "Subtract payments for child support for an
individual living outside the home as set forth in Regulation .35 of this chapter;". .42B:
a household without an elderly or disabled member "shall meet both the gross and net
income eligibility standards". The excluded-income list in .30 names child support
received, not paid. As in the released MD COMAR scopes, `source_as_of` and
`expression_date` are the publication's build date, 2026-09-27.

### Arkansas: SNAP Certification Manual, as revised through February 1, 2020

`Complete_SNAP_Manual.pdf`, 1,057 pages: manual transmittals, policy directives, the
manual and appendices. It prints no compilation-wide date. Its latest section revision
stamp is "SNAP Manual 02/01/20", on 53 section headings from page 358, which sets the
vintage. 6550 SNAP Manual 06/01/98 (page 642): "A deduction will be allowed for legally
obligated child support payments made by a household member to an individual who is
not a household member." 7524 (pages 687-688): "Except for the farm loss deduction
explained in SNAP 5670, no deductions will be allowed in the calculation of total gross
income." 6100 (page 615): "Deductions are applied after the gross income has been
calculated." The 7610 worksheet (page 692) enters child support on line 11, while its
printed line 12 totals "lines 7-10"; the metadata records the discrepancy.

### Hawaii: HAR chapter 17-676, as amended through January 6, 2012

DHS's January 2014 posting of chapter 17-676 (Income). Section histories print "comp
11/09/06", and the latest printed action is "§17-676-55 REPEALED. [R 1/06/12]" (page 38),
which sets the vintage. 17-676-56(f) (page 38): "Subtract the legally obligated child
support payments that are paid by a household member." 17-676-72(6) (page 48) allows the
deduction for payments to or for a nonhousehold member, including arrearages. Every
page's text is identical to the page rows of the released scope
`us-hi/regulation/2026-05-27-hi-snap-rules-r2026-07-15-self-contained`, taken from DHS's
2019 posting. This scope's value is the dating: the same text was posted by January 2014.

### Vermont: Bulletin No. 18-06F

`us-vt/rulemaking/dcf/2018-12-10/b18-06f`, dated December 10, 2018, announces the final
proposed rule repealing the 3SquaresVT rules. Page 1: "Current program options and
waivers will be maintained (subject to approval by the federal Food and Nutrition
Service)." The cover prints "CHANGES ADOPTED EFFECTIVE January 1, 2019". Page 2 calls that
date "anticipated" and "subject to change", and pages 2-3 say the state options live in
the 3SquaresVT Program Manual. The bulletin does not state the child support election.
Page 1 is a scanned cover whose text layer misreads it ("EFFECTNE January 1. 2019");
`metadata.ocr_note` lists each misreading, checked against a rendering of the page.

## Conventions

- **Classes and paths.** Codified or compiled rules use `regulation`, agency manuals
  `manual`, agency letters and memoranda `guidance`, and registers and rule bulletins
  `rulemaking`. The enacted session law uses `statute` under a session-law family
  distinct from codified N.J.S.A. paths, like the released GA and CO session laws.
  Louisiana section rows sit directly under the Part (`lac/67/iii/<section>`), matching
  "LAC 67:III.<section>". The Washington register paths carry the printed filing date,
  because WSR HTML prints no issue date.
- **Historical vintages.** The Colorado, Rhode Island, Arkansas and Hawaii scopes are
  historical vintages of rules or manuals the corpus holds in current form. Each takes
  its family path plus `/vintage/<date>`; `source_as_of` and `expression_date` are that
  date; and `metadata.vintage_date_basis` names the printed date used. That is the
  version's printed effective date (Colorado), the publisher's filing record, retained in
  the scope (Rhode Island), or the latest printed revision or amendment (Arkansas,
  Hawaii). File timestamps are recorded but not used. `docs/corpus-pipeline.md`
  ("Historical vintages of state documents") now documents the convention. The draft had
  used file creation dates for Arkansas and Hawaii; the printed dates replace them.
- **Other dates.** Letters, memoranda, registers, bulletins and the session law keep the
  retrieval date, 2026-09-28, as `source_as_of`, as #736 did, and their printed date as
  `expression_date`, with its kind stated in `expression_date_note`.

## Extraction options

The new options are opt-in `extraction` keys in `src/axiom_corpus/corpus/documents.py`,
documented in `docs/corpus-pipeline.md` ("Amended rule text in PDFs and HTML"):

- PDF `amendment_markup` gains `inserted_style: bold`, `deleted_style: brackets` and
  `unmarked_line_patterns` for the New Jersey convention: bold additions, bracketed
  deletions, and running page numbers left unmarked. Bracketed deletions become `[-...-]`
  runs, and a run crossing a page break is flagged on both rows. Of 23 deletion runs on
  pages 9-20, two cross a page break (11 to 12 and 18 to 19). Removing the delimiters from
  each page gives its plain text without the brackets.
- HTML `html_amendment_markup` keeps the source's spacing and paragraphs. Text and
  paragraph structure come from the default lxml parse, and each character's amendment
  status comes from an html.parser parse of the same source, aligned character by
  character. lxml alone would end WSR 09-15-085's underlined insertion at the first
  `<p>`; html.parser alone would end paragraphs at mismatched inline end tags. The two
  parses must agree on the non-space text, or extraction fails. WSR 09-15-085 reads
  `(([-and-]))` as printed, with 42 paragraphs. `html_encoding` decodes strictly without
  changing the parser.
- DOCX `docx_symbol_map` writes Word `<w:sym>` glyphs, which default extraction skips.
  Title 67 stores 290 definition dashes as Symbol-font `F0BE`; mapped to U+2015, the
  character the same compilation types for that construction, §307 reads "d. SNAP―90
  days." instead of "SNAP90 days".

Default extraction is unchanged. Two differential runs (under "Verification") extracted
existing retained documents with `origin/main`'s `documents.py` and the branch's.
GitNexus impact analysis could not run: the local index files are a newer storage
version than the tool reads. Every changed function is private to `documents.py`, and
its call sites were checked by search.

## Already in the corpus and confirmed

- Pennsylvania: the released `us-pa/manual/2026-07-21-pa-snap-handbook` has SNAP Handbook
  560.61, "A household is eligible for a child support deduction from net income before
  calculation of the shelter deduction if all of the following conditions are met:"
  (`us-pa/manual/dhs/snap/560-income-deductions-560-6-child-support-deduction/block-1`),
  and twelve Appendix A blocks that each list "Child Support 7 CFR § 273.9(d)(5)". The
  live Appendix A was not re-ingested.
- 7 CFR 273.9 is in `us/regulation/2026-07-15-title-7-part-273`, with (c)(17), (d)(5) and
  the (d)(2) rule that excluded child support earnings still count toward the earned
  income deduction.
- #736's CA ACL 06-31, IL MR 23.22, VA 22VAC40-601, DE 13 DE Reg. 1550 and MA DTA Policy
  Online.

## Not ingested

- Vermont's 3SquaresVT rules compilation,
  <https://dcf.vermont.gov/sites/dcf/files/ESD/Rules/2018/271-3Squares.pdf>: HTTP 404 on
  2026-09-28 17:11 UTC with both a browser and the corpus User-Agent. No live official
  replacement was found; B18-06F is included instead.
- Colorado's CCR rule-history page for 10 CCR 2506-1
  (<https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2818>): two
  requests a second apart returned different sets of history rows, so neither its bytes
  nor its text is reproducible. The two rows cited above appeared in both.
- Missouri IM-111 (October 22, 2004), which the released Missouri manual's revision
  histories list for the child support exclusion sections; the primary-source research
  on Missouri did not depend on it.
- The WAC 388-450-0185 companion order that WSR 09-16-095 waited for, and New Jersey's
  adoption notice 49 N.J.R. 267(a).
- Archive-only captures that the parameter or PR #9622 cite: Iowa General Letter 7-F-81,
  the 106 CMR 363 Rev. 7/2009 capture, Maryland FSP manual captures, the Pennsylvania
  2009 and 2011 handbook captures, the Vermont rules and procedures captures, the
  Arkansas FSC 2010 captures and the Hawaii 2010 capture. The corpus does not ingest
  archived copies.
- USDA FNS SNAP State Options Reports (decision d325) and secondary copies such as
  Cornell LII or Justia.

## Review and corrections

An adversarial review of the uncommitted draft (eight read-only reviewers, one per scope
group plus one for the code) found defects, and each was checked against the retained
bytes before it was fixed:

- **Maryland.** The draft scraped DSD's HTML regulation pages, which print "Please do not
  scrape. Instead, bulk download", and flattened the .45 income-standard tables. The
  scope was rebuilt with `extract-maryland-comar` from DSD's `law-xml-codified`
  publication, as every released MD COMAR scope is. All 62 regulation bodies match the
  draft word for word; tables now keep their rows, and regulations are children of the
  chapter. The draft's generator script and its misattributed pre-2000 history notes are
  gone.
- **New Jersey PRN.** "48 NJR 5(1)" is not a Register citation; the scope now cites 48
  N.J.R. 695(a). Bold mode had written deleted text as ordinary text with `deleted_runs:
  0`, including the deleted child support deduction; `deleted_style: brackets` fixes that.
- **Dates.** Missouri, North Carolina, Washington and New Jersey had set `source_as_of`
  to the document's own date; it is now the retrieval date. Arkansas and Hawaii had used
  file creation dates; they now use printed dates (above). The Louisiana Register note
  cited a cover the PDF lacks. Rhode Island's day-level effective date now rests on the
  retained filing record.
- **Rhode Island path.** `dhs/snap-rules/...` matched no RI neighbour. The path is now
  keyed to the Secretary of State's own identifier, `218-820`.
- **Hawaii.** The scope's text duplicates the released 2019 posting. That is now
  disclosed, and the draft's claim that the chapter prints no compilation date is
  corrected.
- **Metadata claims.** The Arkansas, Hawaii, Rhode Island, Missouri, North Carolina,
  Vermont, Washington and Louisiana descriptions were reworded to what the text prints,
  and every such sentence is pinned in a test. Examples: 7610's line 12, Hawaii's
  (g)/(j)(1) cross-references, and B18-06F's "proposed" checkbox and "anticipated"
  effective date.
- **Extraction.** IM-39 dropped its site navigation. IM-34 gained its header (division,
  addressee, subject, manual revision). The Louisiana definition dashes are restored.
  WSR 09-15-085 keeps its paragraphs and printed spacing. Cosmetic artifacts of default
  extraction are disclosed in each scope's `extraction_note` rather than changed:
  Colorado's paragraph-free pages, line-end hyphen joins in CO, RI and NC, run-in RI
  headings, WordPerfect glyphs in the Louisiana Register, the §1507/§2305 editor's notes
  and Arkansas's private-use bullets.
- **Code.** The review asked that the new options fail closed, get tests and have their
  behaviour documented. `html_encoding` had silently switched the HTML parser; it now
  only decodes, strictly. Every new error branch has a test, and three seeded property
  tests cover the markup invariants, 3,000 cases each. Hypothesis is not a repository
  dependency, and adding it re-resolves `uv.lock`, moving the `verify` extra's
  policyengine-us from 1.634 to 2.15, so the seeded tests stand in until a separate change
  adds it.

### Second review (pull request #763)

An independent adversarial review of the pull request (subfleet `review`, standard
tier) reproduced two major and two minor defects in the new options. Each was
reproduced here before it was fixed, and each now has a regression test.

- **HTML word and paragraph boundaries.** A boundary was written only on entering a
  block element, so text after a closing `</div>` ran into the block, and table cells
  ran together (`1{+200+}` strips to `1200`). The check compared non-space characters
  only, so it could not see this. Block elements now end paragraphs, and cells and
  `<br>` separate words.
- **CDATA.** html.parser keeps CDATA that the default lxml parse drops, and the check's
  reference used the same html.parser tree. The resulting design takes text from lxml
  and only amendment status from html.parser, with the two aligned and required to
  agree. It also fixes a regression the first boundary fix caused: html.parser closes an
  open `<p>` at a mismatched `</b>` or `</u>`, which split WSR 09-15-085's "(o)" from its
  text. WSR 09-15-085's rows are unchanged from the first commit.
- **PDF precedence.** `unmarked_line_patterns` now applies before any character is
  classified, so a struck page number no longer fails bracket mode. Bold mode now
  ignores drawn underlines when checking conflicts, so a struck, underlined character
  is deleted rather than refused.
- **Rhode Island.** The page-offset note now applies only from PDF page 17; pages 1-16
  are the cover and contents.

The HTML property test now checks against the generator's own words and paragraphs,
1,000 generated documents, rather than comparing non-space characters.

## Citation-path ratchet and retention

The new rows add 13 `block-N` paths (IM-39 1, IM-34 8, P.L. c.45 1, the two WSR orders 2,
the RI filing record 1) and 1,847 `page-N` paths (AR 1,057, CO 236, RI 311, the LA
Register 145, HI 73, NJ PRN 20, VT 3, NC 2). Recounted on this tree,
`schema/citation-path.v1.json` sets `block_n` to 75,929 and `page_n` to 152,501; no
other family moves. With these baselines `scripts/validate_citation_paths.py` passes over
588,825 records (437,411 unique paths). Any branch that merges later must recount on the
merged tree rather than take either side of a conflict.

`.gitattributes` marks each new scope's retained HTML, and Maryland's XML and license
file, binary. PDF and DOCX retention follow the existing rules. Only the fifteen scopes'
`sources/`, `inventory/`, `provisions/` and `coverage/` paths are force-added from the
ignored `data/` tree.

## Commands

```bash
export UV_PYTHON=/opt/homebrew/bin/python3.14   # standard CPython 3.14, as CI
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-ar-snap-manual-2020-02-01 --manifest manifests/us-ar-snap-manual-2020-02-01.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-co-10-ccr-2506-1-2009-07-01 --manifest manifests/us-co-10-ccr-2506-1-2009-07-01.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-hi-har-17-676-2012-01-06 --manifest manifests/us-hi-har-17-676-2012-01-06.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-la-lac-title-67-part-iii-compilation-2026-08 --manifest manifests/us-la-lac-title-67-part-iii.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-la-register-2003-04-20-vol-29-no-4 --manifest manifests/us-la-register-2003-04-20-vol-29-no-4.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-mo-dss-im-34-2013 --manifest manifests/us-mo-dss-im-34-2013.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-mo-dss-im-39-2003 --manifest manifests/us-mo-dss-im-39-2003.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-nc-dss-es-al-6-2005 --manifest manifests/us-nc-dss-es-al-6-2005.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-nj-pl-2013-c45 --manifest manifests/us-nj-pl-2013-c45.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-nj-prn-2016-017 --manifest manifests/us-nj-prn-2016-017.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-ri-218-820-snap-rules-2014-10-01 --manifest manifests/us-ri-218-820-snap-rules-2014-10-01.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-vt-dcf-b18-06f --manifest manifests/us-vt-dcf-b18-06f.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-wa-wsr-09-15-085 --manifest manifests/us-wa-wsr-09-15-085.yaml
uv run --extra dev axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-28-wa-wsr-09-16-095 --manifest manifests/us-wa-wsr-09-16-095.yaml
uv run --extra dev axiom-corpus-ingest extract-maryland-comar --base data/corpus --version 2026-09-28-md-snap-comar \
  --publication-branch publication/2026-09-27.2026-09-27 --only-title 07 --only-subtitle 03 --only-chapter 17
```

## Verification

- **Tests.** The focused tests pass:
  - the new and updated `tests/test_us_snap_child_support_cited_*.py`;
  - `tests/test_corpus_documents_amendment_styles.py`, which covers the new options,
    each error branch, the second review's cases and the seeded property tests;
  - #736's `tests/test_us_snap_child_support_state_sources.py`, which re-extracts the CA
    and DE PDFs, and `tests/test_corpus_documents_pdf_amendment_markup.py`;
  - `tests/test_ingest_manifest_provenance.py` and `tests/test_citation_path_grammar.py`.

  Also run: `uv run --extra dev ruff check .`,
  `uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports`,
  `uv run --extra dev towncrier check`, and `scripts/validate_citation_paths.py` (see
  "Citation-path ratchet").
- **Reproducibility.** The commands above were run twice, into `data/corpus` and into a
  scratch base (2026-09-28, 16:59-17:00 and 17:11 UTC). Every retained source except
  Missouri's two memos was also byte-identical to the draft's 2026-09-27 download (the RI
  filing record is new). 13 scopes wrote
  byte-identical sources, inventory, provisions and coverage. The two Missouri memos
  wrote identical provisions and coverage; their HTML differs between fetches only in
  per-request Dynatrace (`rpid`) and Incapsula (`cb`) script tokens, recorded in
  `source_bytes_note`.
- **Default extraction unchanged.** Differential runs extracted existing retained
  documents with `origin/main`'s `documents.py` and the branch's, covering every
  combination of extraction keys the manifests use (92 after merging `origin/main`
  c65b2ca15) and excluding OCR scopes and PDFs over 6 MB. The final code, after the
  second review's fixes, gave identical blocks on 765 documents (445 HTML, 320 PDF;
  11,175 blocks). The first review's independent differential of the draft covered
  14,588 released sources, and the second review's covered 27 documents (PDF, HTML and
  DOCX, including the CA/DE markup scopes and a labeled-sections DOCX); both were also
  identical.
- **Citation-path collisions.** Every new citation path was checked against every
  tracked provisions file of its jurisdiction (231 files). There are no collisions,
  except that Maryland's scope carries the adapter's three shared containers
  (`us-md/regulation`, `.../title-07`, `.../title-07/subtitle-03`), as every MD COMAR
  adapter scope does.
- **Release validation.** A local draft selector checks that the scopes are releasable.
  It takes the 200 scopes of the touched jurisdictions in
  `us-rulespec-2026-09-14-wave4-r2-union`, plus the fourteen official-documents scopes.
  Maryland's chapter 17 was consolidated with the selected MD regulation scope, as a
  release cut would:
  `scripts/consolidate_release_scopes.py ... --source-version <selected> --source-version 2026-09-28-md-snap-comar-...-chapter-17`,
  giving 166 + 66 − 3 shared containers = 229 rows, complete. The selector passes
  `validate-release` with 0 errors and one warning, `unsectioned_document_body` on
  `us-md/manual/2026-09-10-wic-state-policy-manual`, the same one the baseline gives
  without the new scopes. The consolidated scope is not committed. Selecting Maryland in
  a release needs that consolidation, as for the other MD COMAR adapter scopes.
- **Signing.** Each scope's signed ingest manifest under `.axiom/ingest-manifests/`
  attests this note by SHA-256 as its reasoning log, with its command above. The
  manifests are signed from the clean commit that contains this note's final text, so
  the note does not record the `guard-ingested` result; the pull request does.
