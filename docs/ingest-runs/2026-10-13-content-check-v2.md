# Content check v2: figures, reviewed-empty rows, the navigation threshold (2026-10-13)

Re-measured **2026-10-20 at `761cf682d`**, after merging main `e019e4456`
into #861. This refreshes the original 2026-10-13 measurement recorded at
`5838d7d37`; historical comparisons below explicitly name their baseline.
The [hollow-root audit](2026-10-13-hollow-document-root-audit.md) (#853)
classified the 188 v1 hollow roots. The rules are in the
[release gate policy](../release-gate-policy.md#version-2-2026-10-13).

No corpus bytes, release selectors or reviewed-empty entries changed. Nothing was
published, loaded, signed or activated. The baseline was regenerated and the
measurement documentation refreshed.

## Method

All 63,859 locked files across 2,433 locks were materialized and hash-verified.
Every locked scope with provisions and an inventory was scanned: **2,390 → 2,425**.
The combined code checks letters and figure-table counts and shares over the whole
body; navigation and prefix matching still use at most 1,200 tokens. The census
also uses the whole body, unlike the original capped prototype.

The candidate script evaluates navigation coverage, residual words, heading
repetition and prefix verdict once per row. Its primary v2 result reproduces the
CLI baseline's findings and reviewed-empty paths exactly in all 2,425 scopes.
For current-input comparisons, “v1-style” means the combined code with figures and
reviewed-empty exemptions disabled, retaining whole-body letter detection. This
is not a replay of the old capped implementation. Candidate additions/removals
below compare with that current-input v1-style result; each cell is
**original 2026-10-13 → fresh 2026-10-20**.

| Variant | `navigation_body` | `hollow_document_root` | Added | Removed |
| --- | ---: | ---: | ---: | ---: |
| v1-style | 1,198 → 1,199 | 188 → 188 | 0 → 0 | 0 → 0 |
| Every token with a digit is text | 1,198 → 1,199 | 183 → 183 | 0 → 0 | 5 → 5 |
| ... and digit tokens count in the navigation residual | 1,197 → 1,198 | 182 → 182 | 0 → 0 | 7 → 7 |
| Navigation threshold 0.69 | 1,206 → 1,208 | 189 → 189 | 9 → 10 | 0 → 0 |
| Navigation threshold 0.65 | 1,284 → 1,286 | 190 → 190 | 88 → 89 | 0 → 0 |
| Navigation threshold 0.6 | 1,357 → 1,359 | 194 → 194 | 165 → 166 | 0 → 0 |
| Roots only: a row is text for its root below 0.69 | 1,198 → 1,199 | 189 → 189 | 1 → 1 | 0 → 0 |
| Roots only, below 0.65 | 1,198 → 1,199 | 190 → 190 | 2 → 2 | 0 → 0 |
| Roots only, below 0.6 | 1,198 → 1,199 | 194 → 194 | 6 → 6 | 0 → 0 |

`navigation_prefixed_body` (102 → 102) and `version_picker_source` (1 → 1)
do not change in any variant. The residual experiment keeps the shipped
letter-based prefix rule, as the original prototype implementation did.

## Figures

The audit's one check false positive remains IL CSMM item 67224, the minimum
monthly SNAP benefit, whose only block is 27 dates and amounts (27 → 27).

Counting every token with a digit as text removes five findings (5 → 5): item
67224 and the four CMS scanned attachments IN-12-014, OH-12-004, OH-12-006 and
OH-13-001 (4 → 4), whose pages read as a date stamp. The audit classified the
four as extractor defects (#854 reads them by OCR), so that rule would hide real
losses. Also counting digit tokens in the navigation residual hides a CMS index
page (`us-ny/.../spa-index/p05`), whose “Approval Document” links cross the
25-word residual with two dates.

The locked rows with a digit and no letter changed **1,381 → 1,384**. The three
new rows are one-date blocks in the Illinois w7 manual: items 112906, 149890 and
161600. By number of figure tokens (numbers, dates, amounts, rates, ranges):

| Figures | Rows | Garbled glyph pages | Tables under v2 | What they are |
| ---: | ---: | ---: | ---: | --- |
| 0 | 28 → 28 | 19 → 19 | 0 → 0 | garbled pages, list markers and other marks |
| 1 | 1,135 → 1,138 | 13 → 13 | 0 → 0 | tariff item numbers, page numbers, date stamps |
| 2 | 73 → 73 | 9 → 9 | 0 → 0 | pairs of stamp dates, a pair of incomes |
| 3 to 4 | 23 → 23 | 6 → 6 | 0 → 0 | stamps with SPA numbers, IRS code lists, a sample card number |
| 5 to 12 | 98 → 98 | 77 → 77 | 21 → 21 | garbled pages; IRS code lists, year lists, revenue projections, a table row |
| 13 to 24 | 0 → 0 | 0 → 0 | 0 → 0 | none |
| 25 and more | 24 → 24 | 0 → 0 | 24 → 24 | benefit, rate, income, proration and ZIP code tables; tariff code annexes |

“Garbled” uses the original census's control-character detector
(`U+0000–0008`, `000B–000C`, `000E–001F`, `007F`). Its maximum figure share is
1/7 (14.29%), still under 15% of tokens. This detector is not a new source audit.

V2 counts a letterless body as text when at least 5 tokens are figures and figures
are at least half of all body tokens. List markers (`(1)`, `[12]`, `3.`) are not
figures; bodies consisting only of such markers remain absent (0 → 0).
Qualifying rows remain **45 → 45**, with **0 → 0** garbled figure tables. The
figure rule removes **1 → 1** finding, item 67224, and no other finding; all four
attachments remain hollow. The fresh census uses the shipped `is_figure` and
`is_figure_table` over full bodies.

## Reviewed-empty rows

`manifests/reviewed-empty-nodes.yaml` still lists **72 → 72** rows in
**13 → 13** scopes, matching the audit's `expected_empty` rows:
`index` 45 → 45, `reserved` 10 → 10, `empty_in_source` 6 → 6,
`deleted` 4 → 4, `table_of_contents` 3 → 3, `cross_reference` 2 → 2,
`repealed` 2 → 2. All 72 are matched hollow roots; stale listed rows: 0.
The Illinois review basis remains the live IDHS pages fetched 2026-10-13, because
that scope retains no per-item pages. This run did not repeat that source review.

## The navigation threshold

ME 36 §5219-SS in `us-me/statute/2026-07-13-recovery` remains a missed text loss:
its menu is 69.2% navigation (69.2% → 69.2%). “§5219-SS PDF” and “Ch. 822
Contents” are under 75% letters and therefore are not navigation strings.

The threshold experiment was also run with the full v2 rule and all reviewed
exemptions. The old columns are the original v1 experiment; the new columns
are additional findings relative to the combined v2 rule at 0.7:

| Change | Added `navigation_body`, old → new | Added hollow roots, old → new |
| --- | ---: | ---: |
| threshold 0.69 | 8 → 9 | 1 → 1 |
| threshold 0.65 | 86 → 87 | 2 → 2 |
| threshold 0.6 | 159 → 160 | 6 → 6 |
| root-only bar at 0.69 | 0 → 0 | 1 → 1 |
| root-only bar at 0.65 | 0 → 0 | 2 → 2 |
| root-only bar at 0.6 | 0 → 0 | 6 → 6 |

The 0.69–0.70 band changed **8 → 9** rows. The additional row is a second scope's
copy of the Israeli National Insurance Law heading, in
`il/statute/2026-09-29-il-taxben-contributions` (0.691). The band still includes
Washington and Texas rule-link lists (0.699), Vermont credits (0.698), the Iowa
pointer (0.694), the Maine menu (0.692), and the UK guidance sentence announcing
National Insurance rates “from 6 April 2026” (0.692).

The 0.65–0.69 band stays **78 → 78** more rows, including 28 Pennsylvania chart
links (28 → 28), Minnesota breadcrumbs, Connecticut repeal notices (0.660),
Minnesota prose with linked terms (0.656), Arizona/Texas pointers and a Belgian
validity line. The 0.6–0.65 band stays **73 → 73** rows. These displayed shares
remain unchanged to three decimals.

Roots-only changes still add the Maine root at 0.69; at 0.65 they also add the
Wisconsin W-2 refugee-policy pointer. At 0.6 they additionally add an Alaska
“J. Reserved” item, New Hampshire FAM prose (0.616 → 0.616), a Washington table
of contents and an Idaho SPA index. Reviewed exemptions are applied throughout.

V2 keeps 0.7. The band still contains prose, and `navigation_body` also decides
which HTML blocks the extractor may drop (#852). The Maine scope is already
withdrawn. Its chapter successor still carries **5,280 → 5,280** characters of
§5219-SS; partial-loss analysis belongs to the source-coverage design note.
`test_the_maine_menu_under_the_navigation_bar_is_left_to_the_withdrawal` pins the
menu measurement and withdrawal.

## Baseline

Rebuilt on the combined code with:

```bash
uv run --extra dev axiom-corpus-ingest content-check --all --update-baseline --workers 4
```

Findings changed **1,416 → 1,417**, affected scopes **181 → 182**, and scanned
scopes **2,390 → 2,425**. Counts by code are navigation **1,198 → 1,199**, prefixes
**102 → 102**, hollow roots **115 → 115**, and picker sources **1 → 1**.
Selected affected scopes remain **176 → 176** across all tracked selectors and
**151 → 151** in `us-rulespec-2026-10-12-w5-benefits-union`.

Against #847's original v1 baseline at `88c1435a5`: shared provision/inventory
digest changes **0 → 0**, findings added **0 → 1**, findings removed **73 → 73**.
The added finding is `navigation_body` at
`us/manual/ssa/poms/rs/02510.030/block-4`, in the added OASDI POMS RS scope.
There are 35 additional baseline scopes, 34 clean. Against main `e019e4456`:
zero shared digest changes, zero findings added and 73 removed. The main baseline
has 2,391 entries; the fresh scan adds its 34 missing clean scopes. The merged v2
baseline at `761cf682d` likewise gains exactly those 34 clean entries, with every
existing entry unchanged.

On current inputs, v1-style finds **1,489 → 1,490** findings in **182 → 183** scopes;
v2 removes only item 67224 and the 72 reviewed rows. The New Mexico SNAP
regulations scope remains clean. The **115 → 115** remaining hollow roots still
match the audit's **103 → 103** extractor defects and **12 → 12** missing or
placeholder sources. Audit classifications stay **188 → 188** total, including
**72 → 72** expected-empty rows and **1 → 1** false positive.

## Source-coverage and CMS context

The source-coverage prototype was also re-run on 2026-10-20, using exactly the
15 scopes in the union of its two retained 2026-10-13 output files. It compares
casefolded word-token multisets from extracted bodies plus headings against each
retained HTML source after the shipped invisible/navigation XPath elements are
dropped. Median means the sorted four-decimal ratios at index `n // 2`, matching
the original prototype. All **4,718 → 4,718** per-source rows reproduce exactly:

| Scope family (original selection) | HTML sources, old → new | Median, old → new |
| --- | ---: | ---: |
| CA recovery | 11 → 11 | 0.4865 → 0.4865 |
| CA chapter successor | 1,029 → 1,029 | 0.6096 → 0.6096 |
| CT Medicaid plan | 6 → 6 | 0.0937 → 0.0937 |
| MD TCA statutes | 2 → 2 | 0.0324 → 0.0324 |
| ME recovery | 6 → 6 | 0.0315 → 0.0315 |
| ME chapter successor | 1,777 → 1,777 | 0.1489 → 0.1489 |
| NC TY2026 core | 1 → 1 | 0.0234 → 0.0234 |
| NH TANF manual | 715 → 715 | 1.0000 → 1.0000 |
| NY income-tax regulations | 318 → 318 | 0.3352 → 0.3352 |
| NY recovery | 11 → 11 | 0.9332 → 0.9332 |
| PA SNAP handbook | 297 → 297 | 1.0000 → 1.0000 |
| VA chapter | 307 → 307 | 0.5687 → 0.5687 |
| VA w6 statute | 2 → 2 | 0.9027 → 0.9027 |
| WA EA-Z manual | 200 → 200 | 0.9604 → 0.9604 |
| CMS FCEP | 36 → 36 | 0.0187 → 0.0187 |

The ME chapter count below 0.5 remains **1,330 → 1,330** of **1,777 → 1,777**
HTML pages. Its §656 source remains **1,446 → 1,446** visible words; five tokens
are retained by this body-plus-heading comparison (coverage 0.0035). This is a
whole-page prototype, not a proposed release gate. The earlier informal ranges
“0.01–0.09” for losses and “0.1–0.6” for VA/CA pages were recorded on 2026-10-13
at `5838d7d37` without a defined aggregate statistic; the explicit fresh medians
above replace those phrases in the PR body. The design note itself remains the
historical proposal.

The CMS markup sweep matched 195 locked state-plan provisions files, containing
240 index pages in 102 scopes. All **240 → 240** original raw page rows match.
A “bare summary cell” is a nonempty `margin-bottom-3` div with no descendant
`p`, inside a CMS accordion card. It is a markup proxy for the extraction loss,
not a new semantic review of whether that text appears elsewhere.

The original **12,911 → 12,911** count is correct only for pages without
`hollow_document_root` or `navigation_body` findings: **222 → 222** pages,
**218 → 218** with bare summary cells. It includes **12** pages flagged only by
`navigation_prefixed_body`, holding **1,078** such cells. If “unflagged” means no
content finding of any code, the claimed count changes **12,911 → 11,833**:
**210** pages, **206** with bare summary cells. The difference is the definition
of unflagged, not changed corpus bytes or changed source markup.

## Evidence availability

The fresh variant and census script and raw JSON accompany the merge handoff;
they are not tracked repository artifacts. The script checks exact agreement
with the CLI baseline for every scope and reviewed path. Its sha256 is
`243e8019573d4c1ef3b16b5251b05da6f0976b2fbec90afd163d5b1c4335c8cf`;
the rebuilt baseline's sha256 is
`ed4fe1210819f80ceeb0372d7faba59316099b51ab12b3107c822d56fe9f371e`.
The CLI command reproduces the shipped baseline, not the candidate variant table
or census by itself.

The source-coverage and CMS script and its exact input selection/raw outputs
also accompany the handoff; its sha256 is
`651f852504402a38a2e48d7b0eb9bc8554484d40263d5bd1c2653d711058a2a4`.
The [source-coverage design note](../source-coverage-check.md) remains the
2026-10-13 proposal, while the fresh comparisons are recorded above.
