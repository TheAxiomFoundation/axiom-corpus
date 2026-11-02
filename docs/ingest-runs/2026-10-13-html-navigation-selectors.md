# HTML navigation selectors: Washington EA-Z tab links and Texas "Related Policy" lists

Date: 2026-10-13. Branch `fix/html-drop-selectors-wa-tx`, stacked on #852
(`fix/html-navigation-blocks`, 57cd05e01). #852's navigation-block filter keeps,
on purpose, two publisher-specific kinds of page navigation that its general rule
cannot tell from text: a lone link (it can be a section's whole text) and a link
list whose section codes sit outside the links. They were the largest remainders
of the release content check's `navigation_body` rows: 179 Washington DSHS EA-Z
tab links and 225 Texas HHS handbook "Related Policy" lists
([#852's run note](2026-10-13-html-navigation-blocks.md#why-828-flagged-rows-remain)).
This change names them in their manifests so future ingests stop writing them as
provision rows.

Every locked scope is unchanged. Nothing was fetched from publishers, published,
loaded or activated; the measurement re-extracts the bytes the scopes' locks pin
into scratch output outside `data/corpus`.

## Why not `html_drop_selectors`

`html_drop_selectors` remove elements before the heading walk numbers the page's
`block-N` blocks. Both kinds of navigation here are whole blocks in the middle of
their pages (a tab link under a WAC heading, a "Related Policy" heading over its
list), so a drop selector empties the block and every block after it on the page
moves up one ordinal: 3,575 kept rows of the four scopes follow a dropped block on
their page. For Texas it is worse: a selector can remove the heading and the
first paragraph after it but not every paragraph up to the next heading, so the
rest of a list would join the block before it and change that block's body. So
the extractor gains two keys that drop whole positional blocks instead, with the
ordinal used up as #852's filter does (`documents._DeclaredNavigation`, rule in
[release-gate-policy.md](../release-gate-policy.md#declared-navigation)):

- `html_navigation_selectors` match navigation elements. A block whose every
  string lies inside a matched element is dropped; a block with any other text
  keeps its whole body.
- `html_navigation_heading_selectors` match headings. The block a matched
  heading starts is dropped.

Matched elements stay in the tree, so the walk sees the headings and block
boundaries an unfiltered extraction sees. The declarations are independent of
#852's filter: `html_keep_navigation_blocks: true` keeps the blocks the filter
would drop and still drops the declared ones, so a manifest can keep a link list
the filter misjudges and still name its real chrome. A manifest whose pages have
no positional blocks (declared sections, JSON records or source-only JSON, a JSON
field read as one block, a PDF or other non-HTML source) cannot declare
navigation: the extractor raises instead of ignoring the key.

## The selectors

### Washington DSHS EA-Z (`manifests/us-wa-eaz-manual.yaml`, all 200 pages)

Under each WAC heading, a page lists jump links to the "Clarifying Information"
and "Worker Responsibilities" sections further down, one list item per WAC:

```html
<h3><a href="...cite=388-404-0005">WAC 388-404-0005</a> How does a child's age ...?</h3>
<ul><li><h4><a href="#388-404-0005">Clarifying Information and Worker Responsibilities</a></h4></li></ul>
```

Of the 179 flagged rows, 152 are one such link (under an `h4`, or directly in the
item; 2 use the page's absolute URL with a fragment) and 26 are two links joined by
a bare "and" (`<a>Clarifying Information</a> and <a>Worker Responsibilities</a>`,
in the item itself or in an `h4`, `p`, `strong` or `span` inside it). The "and"
is text no link holds, so the selectors name the links and the element that joins
two of them:

```yaml
html_navigation_selectors:
- 'ul > li a[href*="#"]:-soup-contains("Clarifying Information", "Worker Responsibilities")'
- 'ul > li:has(> a[href*="#"]:-soup-contains("Clarifying Information")):has(> a[href*="#"]:-soup-contains("Worker Responsibilities"))'
- 'ul > li :has(> a[href*="#"]:-soup-contains("Clarifying Information")):has(> a[href*="#"]:-soup-contains("Worker Responsibilities"))'
```

On the 200 retained pages they match 222 links, 11 list items and 97 inner
elements, every one of them only label text ("Clarifying Information", "Worker
Responsibilities", "Clarifying Information and Worker Responsibilities").
Matching the list item that holds such a link (`ul > li:has(...)`) would be
simpler but is wrong: it also matches an item of prose ("Barcode generated a
tickle for any AU eligible for Basic Food starting April. See Worker
Responsibilities ...").

One flagged row stays: an item that reads "Clarifying Information" with no link
(the emergency food supplements page). CSS can match it only by substring, which
also matches prose items, so it is left for the check to report.

### Texas HHS handbooks (Texas Works, MEPD, C-120)

`manifests/us-tx-snap-manual-completion.yaml` (283 Texas Works pages),
`us-tx-medicaid-eligibility-manual.yaml` (712 MEPD and Texas Works pages),
`us-tx-twh-c120-snap-deduction-amounts.yaml` (the C-120 page, a Wayback capture)
and the two builders that write the first two
(`TX_RELATED_POLICY_HEADING`). Sections end with a "Related Policy" heading over
one or more paragraphs of cross-references, titles and codes linked or not:

```html
<h3>Related Policy</h3>
<p>Social Security Numbers (SSNs), <a href="...a-140-expedited-service">A-144.1</a></p>
<p>Postponed Verification Procedures, <a href="...">A-145.1</a></p>
```

CSS cannot select "the paragraphs up to the next heading", so the selector names
the heading:

```yaml
html_navigation_heading_selectors:
- ':is(h2, h3, h4, h5, h6):-soup-contains("Related"):-soup-contains("Polic"):not(:-soup-contains("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"))'
```

The words are matched apart because two headings join them with a no-break space
(`Related&nbsp;Policy` in MEPD's copy of A-1320, `Related &nbsp;Policy` in
B-540), and a heading with a digit is never matched, because every section heading
carries its number ("A-1131.2 Good Cause Related to ..."). On the 996 retained
pages it matches 896 headings, all "Related Policy", "Related Policy:" or
"Related Policies"; the 24 numbered section headings that contain "Related" are
not matched.

## Measurement: re-extracting the four scopes

`scripts/measure_html_navigation_blocks.py` (#852's, extended here) matches each
retained source to its manifest entry and extracts it from the locked bytes: with
`html_keep_navigation_blocks: true` and the declarations left out (which must
reproduce the locked rows byte for byte), with the manifest's extraction, and, for a manifest that declares
navigation, once more without the declaration, which tells the rows the
declaration drops (`by: declared`) from the rows #852's filter drops
(`by: filter`).

| Scope | Documents reproduced | Rows | Filter drops | Declared drops | Rows after | `navigation_body` |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `us-wa/manual/2026-07-21-wa-eaz-manual` | 200 / 200 | 1,265 | 7 | 178 | 1,080 | 194 → 9 |
| `us-tx/manual/2026-09-10-snap-state-manual-completion` | 283 / 283 | 4,392 | 43 | 393 | 3,956 | 163 → 3 |
| `us-tx/manual/2026-09-10-medicaid-state-eligibility-manual` | 712 / 712 | 5,026 | 37 | 420 | 4,569 | 145 → 2 |
| `us-tx/manual/2026-07-13-tx-twh-c120` | 1 / 1 | 12 | 0 | 3 | 9 | 2 → 0 |
| **Total** | **1,196** | **10,695** | **87** | **994** | **9,614** | **504 → 14** |

The filter's 87 drops are #852's, unchanged; #852 alone leaves 417
`navigation_body` rows in these scopes.

- **(a) The targeted rows go.** 178 of the 179 Washington tab-link rows (the
  unlinked label stays) and all 225 Texas "Related Policy" rows (117, 106 and 2).
  #852's two reviews labeled every one of the 403 navigation.
- **(b) No other row changes.** The script compares every kept row with its
  locked row field by field: none differs in anything but `metadata.block_count`,
  which moves on 5,900 rows of pages that lose a block, and no document's kept
  rows change order. 3,575 of the kept rows follow a declared drop on their
  page; their paths hold because the dropped ordinals are used up.
- **Nothing else moves.** The other 144 scopes of #852's measurement, whose
  manifests declare nothing, re-extracted at 2b0088980 give successor rows byte
  for byte equal to #852's final run. At 2b0088980 the full test suite has
  5,525 passed, 106 skipped and 1 failed:
  `test_streaming_validation.py::test_validate_release_matches_full_record_validation`,
  a Hypothesis example (a provision whose `source_path` is the integer 7) that
  fails the same way on #852's head 57cd05e01. It is #847's, fixed on #847 at
  e934e4d6c, which #852 has not merged yet.
- **(c) No new findings.** The release content check's scanner finds no new
  finding of any kind in any successor, and `content-check --check-baseline` over
  the four locked scopes reports no baseline difference.
- **Citations.** No row the declarations drop is cited by a RuleSpec repository
  (every local `rulespec-*` clone, at origin/main). The two Texas `block-N` rows
  `rulespec-us` cites are in the older Texas manuals scope, which this change does
  not touch.

### What the Texas heading drops beyond the flagged rows

The heading drops every "Related Policy" list, not only those the check flags:
591 more rows (276, 314 and 1; 378 distinct bodies), lists whose titles or codes
sit outside the links, so link text does not cover 70% of them. A review lane
(Opus 5.5 through Subfleet, while the Codex lanes were held) told to defend the
corpus text, calling anything that could be the section's own substance CONTENT,
labeled all 378 bodies NAV: no CONTENT, no MIXED. A split of every dropped body
into title-and-code items finds only pointers (section titles with codes, guide
and form names, "Glossary, Combat Pay and Combat Zone").

The cost: 37 sentences in 32 kept rows send the reader to "related policy"
("Follow related policy.", "See related policy for dates Medicaid eligibility
begins.", "refer to related policy to disqualify ..."), and 23 of those rows are
followed on their page by a list this change drops. In a successor those pointers
no longer resolve within the scope's rows. Most of the sections the lists name
are themselves in the corpus (some entries name a guide or form, such as "The
Texas Works Documentation Guide (PDF)"), and the retained page keeps the list, but the link from
the instruction to its target section is gone. Whether a cross-reference list
that a section's text points to counts as the section's text is a judgment call,
and it goes with the merge decision.

### What the check still reports

- Washington, 9 rows: the unlinked "Clarifying Information" label and eight lone
  pointers or link lists of the pages' own ("See Diversion Cash Assistance (DCA)",
  "Cash and Medical Decision Tree", an ADA resources list). #852's reviews call six
  of them content.
- Texas, 5 rows: "See A-140, Expedited Service" and "Exempt personal
  possessions" under program headings (in both scopes) and a county list under
  "All Programs"; both reviews call all five content.

## Reproduce

```bash
uv run axiom-corpus-ingest corpus fetch us-wa/manual/2026-07-21-wa-eaz-manual \
  us-tx/manual/2026-09-10-snap-state-manual-completion \
  us-tx/manual/2026-09-10-medicaid-state-eligibility-manual \
  us-tx/manual/2026-07-13-tx-twh-c120
uv run python scripts/measure_html_navigation_blocks.py --out <scratch dir> <the four scopes>
uv run axiom-corpus-ingest content-check <the four scopes> --check-baseline
```

The four scopes take about 100 seconds. `tests/test_html_navigation_selectors.py` pins
the mechanism (examples, and a Hypothesis property: the kept blocks are every block
minus the declared ones, ordinals unchanged), each selector on retained pages, and
the manifests against the builders; `tests/test_us_wa_eaz_manual.py` re-extracts
all 200 Washington pages.

## Follow-ups

- Successor ingests of the four scopes are separate signed ingests, and selecting
  one in place of a locked scope is a release decision.
- 74 kept Texas rows carry a "Related Policy" list inside a content block, under a
  bold paragraph rather than a heading (`<p><strong>Related Policy</strong></p>`).
  Dropping those would change the bodies of content rows; they are left.
- `manifests/us-tx-manuals.yaml` (11 Texas Works pages from May 2026) is not given
  the selector: its locked scopes were made by `scripts/recover_ingest_batch.py`,
  so the measurement cannot reproduce them from the manifest. A successor ingest
  of those pages can add it with its own measurement.
