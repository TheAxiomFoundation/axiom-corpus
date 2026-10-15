# Content check v2: figures, reviewed-empty rows, the navigation threshold (2026-10-13)

The [hollow-root audit](2026-10-13-hollow-document-root-audit.md) (axiom-corpus#853)
classified the 188 `hollow_document_root` findings of content-check-v1 (#847) and
listed, in "What the check misses and over-counts", what the check gets wrong. This
note records the measurements behind content-check-v2, which acts on three of them,
and scopes the fourth as a [design note](../source-coverage-check.md). The rules are
in the [release gate policy](../release-gate-policy.md#version-2-2026-10-13).

Nothing was published, loaded or activated, and no scope was edited. Only
`manifests/release-content-baseline.json` was rebuilt, and
`manifests/reviewed-empty-nodes.yaml` was added.

## Method

The variant table, figure census and near-threshold measurements below are
**unpublished prototype evidence**. Their measuring scripts, exact options and raw
outputs were not published with this checkout, so those measurements cannot be
reproduced from repository artifacts alone.

Every locked scope with provisions and an inventory (2,390) was fetched at #847's
head `88c1435a5`. A measuring script re-implements v1's per-row quantities
(navigation coverage, residual words, words with a letter, tokens with a digit,
heading repeats, prefix verdict) once per row and evaluates each candidate rule
from them. Its v1 rule reproduces the v1 baseline exactly in all 2,390 scopes.
Each variant's findings were compared, finding by finding, with v1's.

| Variant | `navigation_body` | `hollow_document_root` | Added | Removed |
| --- | ---: | ---: | ---: | ---: |
| v1 | 1,198 | 188 | | |
| Every token with a digit is text | 1,198 | 183 | 0 | 5 |
| ... and digit tokens count in the navigation residual | 1,197 | 182 | 0 | 7 |
| Navigation threshold 0.69 | 1,206 | 189 | 9 | 0 |
| Navigation threshold 0.65 | 1,284 | 190 | 88 | 0 |
| Navigation threshold 0.6 | 1,357 | 194 | 165 | 0 |
| Roots only: a row is text for its root below 0.69 | 1,198 | 189 | 1 | 0 |
| Roots only, below 0.65 | 1,198 | 190 | 2 | 0 |
| Roots only, below 0.6 | 1,198 | 194 | 6 | 0 |

`navigation_prefixed_body` (102) and `version_picker_source` (1) did not change in
any variant.

## Figures

The audit's one check false positive is IL CSMM item 67224, the minimum monthly SNAP
benefit, whose only block is 27 dates and amounts (`04/09 - 10/13 ... $16 $15 ...`).

Counting every token with a digit as text removes five findings: item 67224 and the
four CMS scanned attachments IN-12-014, OH-12-004, OH-12-006 and OH-13-001, whose
pages read as a date stamp (`1/4/13`, `9/4/13`, `3/4/13`, `05/22/13`). The audit
classified those four as extractor defects (#854 reads them by OCR), so that rule
would hide real losses. Also counting digit tokens in the navigation residual hides a
CMS index page (`us-ny/.../spa-index/p05`), whose block of "Approval Document" links
crosses the 25-word residual with two dates.

The 1,381 locked rows with a digit and no letter, by the number of figure tokens
(numbers, dates, amounts, rates, ranges) they hold:

| Figures | Rows | Garbled glyph pages | Tables under v2 | What they are |
| ---: | ---: | ---: | ---: | --- |
| 0 | 28 | 19 | 0 | garbled pages, list markers and other marks |
| 1 | 1,135 | 13 | 0 | tariff item numbers, page numbers, date stamps |
| 2 | 73 | 9 | 0 | pairs of stamp dates, a pair of incomes |
| 3 to 4 | 23 | 6 | 0 | stamps with SPA numbers, IRS code lists, a sample card number |
| 5 to 12 | 98 | 77 | 21 | garbled pages (under 15% figures); IRS code lists, year lists, revenue projections, a table row |
| 25 and more | 24 | 0 | 24 | benefit, rate, income, proration and ZIP code tables; tariff code annexes |

v2 counts a letterless body as text when at least 5 of its tokens are figures and
figures are at least half its tokens. A list marker (`(1)`, `[12]`, `3.`) is not a
figure, so a body that kept only its paragraph numbers is not text; no locked row has
that shape today. 45 rows qualify, all tables or lists of figures, none garbled. In
the baseline the rule removes item 67224 and no other finding; the four attachments
stay hollow. The unpublished census was made with the shipped `is_figure` and
`is_figure_table`.

## Reviewed-empty rows

`manifests/reviewed-empty-nodes.yaml` lists the 72 rows the audit classified
`expected_empty`, in 13 scopes, generated from the audit's CSV: 45 `index`, 10
`reserved`, 6 `empty_in_source`, 4 `deleted`, 3 `table_of_contents`, 2
`cross_reference`, 2 `repealed`. Each row's note is the audit's cause and, for
Illinois (whose scope retains no per-item page), the basis of the review: the live
IDHS page fetched 2026-10-13. `tests/test_release_policy_repository.py` checks that
the rows citing the audit are exactly its `expected_empty` rows.

## The navigation threshold

ME 36 §5219-SS in `us-me/statute/2026-07-13-recovery` lost its text; its one block is
the page's menu at 69.2% navigation, because two of its links, "§5219-SS PDF" and
"Ch. 822 Contents", are less than 75% letters and so are not navigation strings.

The rows the lower thresholds add, with their share:

- 0.69 to 0.70 (8 rows): Washington and Texas lists of rule links (0.699), a Vermont
  list of credits (0.698), an Iowa "For more information see ..." pointer (0.694),
  the Maine menu (0.692), a UK guidance sentence on National Insurance rates "from 6
  April 2026" (0.692), and a heading of the Israeli National Insurance Law (0.691).
- 0.65 to 0.69 (78 more): 28 Pennsylvania "Click on a link to see the chart for that
  month" blocks, Minnesota statute breadcrumbs, Connecticut repeal notices
  ("Repealed February 10, 2004. Return to Table of Contents", 0.660), Minnesota
  manual prose whose terms are links (0.656), Arizona and Texas "see the following"
  lists, a Belgian minimum-wage page's validity line.

The roots-only bar adds the Maine root at 0.69 and 0.65, and at 0.65 also a
Wisconsin W-2 appendix whose only block says "Use the following link to access the
Bureau of Refugee Programs policy manual" (a missing source, by the audit's
taxonomy). At 0.6 it adds an Alaska "J. Reserved" item, a New Hampshire FAM section
with prose (0.616), a Washington table of contents and an Idaho SPA index page.

v2 keeps 0.7. Text sits on both sides of every bar between 0.6 and 0.7, so lowering
it trades real text for the one miss, whose scope #847 already withdraws; and
`navigation_body` also decides which blocks the HTML extractor may drop (#852).
`test_the_maine_menu_under_the_navigation_bar_is_left_to_the_withdrawal` pins the
measurement and the withdrawal.

## Baseline

Rebuilt with `axiom-corpus-ingest content-check --all --update-baseline --workers 4`
under content-check-v2. Against the v1 baseline at `88c1435a5`: no digest changed,
no finding was added, and 73 were removed (item 67224 and the 72 reviewed rows).
Findings: 1,416 in 181 scopes (v1: 1,489 in 182); the New Mexico SNAP regulations
scope, whose two findings were its repealed parts, is now clean. The 115
`hollow_document_root` findings left are the audit's 103 extractor defects and 12
missing or placeholder sources.

## Evidence availability

The unpublished prototype measurements above are retained as historical design
context. The [source-coverage design note](../source-coverage-check.md) identifies
its prototype measurements with the same limitation. Publish the measuring
scripts, deterministic input selection, options and raw outputs before treating
either set of measurements as independently reproducible evidence. The baseline
command above uses the repository CLI; it does not reproduce the prototype's
variant table or census.
