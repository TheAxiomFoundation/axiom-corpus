# Source coverage of the locked HTML scopes (2026-10-13)

The [source-coverage design note](../source-coverage-check.md) proposes measuring, for
each source document, how much of the text an extractor read reached its rows. Its
first step is built (axiom-corpus#863): the official-document extractor now records the
figures for every scope it builds. Locked scopes cannot change, so this note measures
the ones that exist, once and offline, to rank successor work. It covers retained HTML
sources only.

Nothing was published, loaded or activated. No scope was edited, and nothing was fetched
into or written under `data/corpus`.

The per-scope ranking is
[`2026-10-13-source-coverage-ranking.csv`](2026-10-13-source-coverage-ranking.csv)
(711 rows: region, sources, median, 10th percentile and minimum coverage, sources under
the review bar, words missing, whether the scope is withdrawn, and the release
selectors that select it).

## Method

`scripts/measure_source_coverage.py --all`, at `272b8d543`, read every locked scope's
rows and retained HTML sources from the local corpus cache.

- 2,398 scopes are locked. 746 hold a source that may be an HTML page. In 711 of
  them a row cites at least one HTML page: 33,525 pages in all. In the other 35 no
  row cites an HTML page: the HTML-like files are cited by no row, or are not HTML.
- A page's **region** is what the extractor reads from it, chosen in this order:
  the manifest the scope's signed ingest manifest names; else the settings that every
  manifest listing the same source id agrees on; else the whole page, without scripts,
  styles and the content check's navigation elements. Manifests are read as they are
  in the checkout today.
- The **kept** words are those of the heading and body of every row citing the page.
  Coverage is kept words over region words, counted as a multiset
  (`axiom_corpus.corpus.source_coverage`).
- The **review bar** is the one the design note proposes: coverage under 0.5 of a
  region of at least 50 words. "With body text" counts the pages under the bar whose
  rows carry a body: a page whose rows hold headings only is a container or an empty
  document, not a partial loss.

Two full runs, before and after a change to how missing runs are cut, gave identical
per-scope figures.

| Region read as | Scopes | Pages | Coverage of 0.99 or more | Under the bar | With body text |
| --- | ---: | ---: | ---: | ---: | ---: |
| The manifest the scope's ingest names | 158 | 10,284 | 89.1% | 23 | 21 |
| A manifest matched by source id | 340 | 5,571 | 84.0% | 255 | 255 |
| The whole page | 216 | 17,670 | 10.9% | 3,411 | 3,000 |

Three scopes hold pages of both of the last two kinds. The pages hold 43.0 million
region words, of which 7.75 million are missing from the rows.

## Scopes read through a manifest

Of the 495 scopes read only through manifests, 374 have no page under the bar. The 121
that do, most first:

| Scope | HTML pages | Median | 10th percentile | Under the bar | With body text | Selectors |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| The 2026-09-13 CMS state-plan scopes (101 with a page under the bar) | 239 | | | 231 | 231 | |
| `us/policy/2026-07-05-cms-chip-fcep-spa` | 36 | 0.24 | 0.06 | 10 | 10 | 44 |
| `us-wa/rulemaking/2026-10-06-w6-benefits-rulemaking-wa` | 9 | 0.91 | 0.05 | 4 | 4 | 3 |
| `us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure` | 121 | 1.00 | 0.79 | 4 | 4 | 1 |
| `us-wa/rulemaking/2026-10-06-w6-tanf-ccdf-rulemaking-wa` | 5 | 0.34 | 0.04 | 3 | 3 | 3 |
| `us/manual/2026-09-10-ssi-poms-si` | 915 | 1.00 | 0.97 | 3 | 3 | 9 |
| `us-ky/regulation/2026-10-06-w6-tanf-ccdf-rules-ky` | 2 | 0.01 | 0.01 | 2 | 2 | 3 |
| `us-md/statute/2026-07-03-md-tca-statutes` | 2 | 0.02 | 0.02 | 2 | 2 | 13 |
| `be/guidance/2026-07-02-be-cnt-minimum-wage` | 2 | 0.44 | 0.43 | 2 | 2 | none |
| `us-nm/regulation/2026-07-17-nm-snap-regulations` | 28 | 0.99 | 0.90 | 2 | 0 | 19 |
| `us-wa/manual/2026-07-21-wa-eaz-manual` | 200 | 0.99 | 0.62 | 2 | 2 | 19 |
| `us-ut/manual/2026-09-10-chip-state-eligibility-manual` | 206 | 1.00 | 1.00 | 2 | 2 | 9 |
| `us-ut/manual/2026-09-10-medicaid-state-eligibility-manual` | 639 | 1.00 | 1.00 | 2 | 2 | 9 |
| `us/manual/2026-09-13-ssi-poms-si-remainder` | 778 | 1.00 | 0.98 | 2 | 2 | 7 |
| `us-ok/policy/2026-10-06-w6-tanf-ccdf-policy-ok` | 1 | 0.40 | 0.40 | 1 | 1 | 3 |
| `us-nm/guidance/2026-10-06-w6-income-tax-guidance-nm` | 1 | 0.50 | 0.50 | 1 | 1 | 3 |
| `us-ne/policy/2026-10-06-w6-tanf-ccdf-docs-ne` | 2 | 0.60 | 0.48 | 1 | 1 | 3 |
| `us-de/guidance/2026-10-06-w6-income-tax-guidance-de` | 4 | 0.84 | 0.31 | 1 | 1 | 3 |
| `us-il/guidance/2026-10-06-w6-income-tax-guidance-il` | 4 | 0.92 | 0.19 | 1 | 1 | 3 |
| `us/guidance/2026-10-06-w6-federal-cms-guidance` | 14 | 0.98 | 0.56 | 1 | 1 | 3 |
| `us/manual/2026-09-13-medicare-poms-hi` | 922 | 1.00 | 0.99 | 1 | 1 | 7 |

What the pages under the bar lose, from their longest missing runs:

- **CMS state plans.** 231 of the 240 SPA index pages (median coverage 0.15) are
  missing their summaries, dates and topics: on `us-ct/…/spa-index-p04`, 503 of 4,584
  words are kept. The hollow-root audit found this loss; #854 gave the manifests a
  per-SPA selector, and the locked scopes predate it. (Their ingest manifests record
  no `--manifest` argument, so the pages are matched by source id.)
- **CMS CHIP FCEP summaries.** The 36 summary cards hold 22 to 148 words, and the rows
  keep a median of 6.5 of them. The 10 under the bar keep 4% to 9% of a card: the
  summary is lost. The other 14 cards of 50 words or more keep 69% to 87%: the
  summary is there and the state, dates and topics are not.
- **Washington State Register filings** (two wave 6 scopes, 7 of 14 pages). A filing
  prints its rule text in `div` and `span` elements beside its tables, and the rows
  keep the tables: WSR 23-14-065 keeps 61 of 1,267 words, WSR 24-11-019 193 of 5,027.
  Not in the hollow-root audit.
- **Kentucky 921 KAR 2:016** (both renditions). The page prints each paragraph's
  label ("(a)", "1.") as an `h2` and its text in `span` elements, which the default
  walk does not read as body text; the rows hold only the regulation's tables.
  88 of 7,504 and 205 of 15,463 words are kept. Not in the hollow-root audit.
- **Maryland TCA statutes.** The two pages keep their menus and lose the statute (the
  audit's finding; #854 fixed the manifest).
- **Utah CHIP and Medicaid manuals.** Four pages lose paragraphs and numbered lists:
  CHIP section 419-5 keeps 13 of 371 words (its "General Information" is missing).
- **Washington EA-Z manual.** Two pages lose their "EXAMPLE" blocks; across the 200
  pages the 10th percentile is 0.62.
- **SSA POMS** (three scopes, six pages). Exhibit letters, address lists and query
  screens: SI ATL01120.202 keeps 32 of 206 words.
- **Wyoming manual.** Four chapter pages lose the lists of their sections.
- **Single pages.** The Oklahoma standards page loses the paragraphs between its
  tables (889 of 2,225 words kept); an Illinois press release keeps 288 of 1,527;
  the healthcare.gov CHIP page 147 of 558; the New Mexico 529 page 199 of 399; the two
  Belgian minimum-wage pages lose the text under their update line (197 and 165
  words).
- **Not a loss.** New Mexico 8.139.640 and 8.139.650 are repealed parts whose rows are
  headings (the scope is in the reviewed-empty list). The Delaware news page and the
  Nebraska TANF page count site chrome inside the content root: a news feed, share
  widgets.

## Scopes read as whole pages

Of the 213 scopes read only as whole pages, 113 have no page under the bar. The 20
with the most:

| Scope | HTML pages | Median | 10th percentile | Under the bar | With body text | Selectors |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `us-me/statute/2026-09-14-income-tax-chapter-us-me-title-36` | 1,777 | 0.15 | 0.02 | 1,348 | 1,347 | 6 |
| `us-mt/statute/2026-07-16-pit-central-us-mt-title-15` | 2,392 | 0.36 | 0.16 | 660 | 660 | 31 |
| `us-ca/statute/2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7` | 1,029 | 0.60 | 0.33 | 359 | 359 | 2 |
| `us-ca/statute/2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7-r2026-09-24-preserve-tables` | 1,029 | 0.60 | 0.33 | 359 | 359 | 5 |
| `us-ny/regulation/2026-09-14-income-tax-regulations` | 318 | 0.31 | 0.02 | 192 | 65 | 5 |
| `us-ut/statute/2026-09-14-income-tax-chapter-title-59` | 144 | 0.05 | 0.01 | 104 | 0 | 6 |
| `us-ks/statute/2026-07-16-pit-west-us-ks-chapter-79-article-32` | 444 | 0.68 | 0.02 | 82 | 35 | 31 |
| `us-id/statute/2026-09-14-income-tax-chapter-us-id-title-63-chapter-30` | 164 | 0.75 | 0.32 | 37 | 35 | 5 |
| `us-ma/statute/2026-09-23-ma-mgl-chapter-62-us-ma-part-i-title-ix-chapter-62-sections-2-r2026-10-07-chapter-62-without-recovery-sections-consolidated` | 58 | 0.04 | 0.04 | 34 | 2 | 3 |
| `us-md/statute/2026-09-14-income-tax-chapter-us-md-article-gtg` | 729 | 0.80 | 0.50 | 28 | 28 | 5 |
| `us-ct/statute/2026-09-14-income-tax-chapter-title-17b` | 30 | 0.53 | 0.30 | 12 | 10 | 5 |
| `us-la/statute/2026-07-16-pit-central-us-la-title-47` | 2,660 | 0.91 | 0.70 | 12 | 12 | 8 |
| `us-la/statute/2026-07-22-la-title-47-official-current-us-la-title-47` | 2,664 | 0.91 | 0.70 | 12 | 12 | 23 |
| `us-ny/regulation/2026-07-17-ny-snap-regulations` | 44 | 0.92 | 0.12 | 9 | 3 | 36 |
| `us-hi/statute/2026-07-16-pit-east-us-hi-volume-04-chapter-235-r2026-10-07-chapter-346-consolidated` | 423 | 0.91 | 0.11 | 8 | 3 | 3 |
| `us-ri/statute/2026-07-16-pit-west-us-ri-chapter-44-30` | 100 | 0.81 | 0.17 | 7 | 1 | 31 |
| `us-me/statute/2026-07-13-recovery` | 6 | 0.03 | 0.01 | 6 | 6 | withdrawn |
| `us-id/statute/2026-07-13-recovery` | 5 | 0.04 | 0.02 | 5 | 5 | withdrawn |
| `us-ca/statute/2026-07-13-recovery` | 11 | 0.49 | 0.34 | 5 | 5 | withdrawn |
| `us-hi/statute/2026-07-03-hi-hrs-us-hi-chapter-346` | 267 | 0.92 | 0.12 | 5 | 2 | 2 |

What they lose, from their longest missing runs:

- **Maine Title 36** is the one large partial loss. Its rows keep the numbered
  subsection heads and lose the lettered paragraphs: §656 keeps 5 of 1,455 words, and
  across the scope 372,653 of 579,623 region words are missing. Open PR #754 addresses
  it; the scope is in six selectors.
- **Montana Title 15.** The rows do not hold the history note that closes each section
  ("History: En. Sec. 5, Ch. 181, L. 1933; …"): 1,635 of the 2,392 pages have a
  missing run that starts with it. On a short or repealed section the note is most of
  the page (15-30-2110 keeps 13 of 560 words).
- **California R&TC** (both renditions). Every page under the bar opens with a missing
  run of LegInfo's search form and breadcrumbs (a median of 77 words). The median
  page of the scope is missing 96 words in all and the 90th percentile 101, so what
  puts a page under the bar is how short its section is. The history note that closes
  a section ("Repealed and added by Stats. 1955, Ch. 939.") is among the missing
  words.
- **New York income tax regulations.** 127 of the 192 pages have heading-only rows;
  those read are Part "Notes" pages (#854 restores the notes) and repealed sections.
  On the other 65, the pages read are missing Westlaw's header and currency notice.
- **Utah Title 59.** All 104 have heading-only rows; those read are part pages that
  list their sections' catchlines. Containers, not a loss.
- **Kansas chapter 79.** The chapter index (5,531 words, a heading-only row), and the
  history notes and case annotations of short sections.
- **Idaho Title 63, chapter 30.** The site banner and the history line of short
  sections, and a 292-word second rendition of 63-3022E (the audit's finding; open
  PR #823).
- **Massachusetts chapter 62.** Part, title and chapter pages with heading-only rows,
  and the Legislature site's search and registration forms.
- **Maryland Tax-General.** Site chrome only: the 28 pages are sections of 50 to 57
  region words, and the longest missing run on each is the site's search notice.
- **Connecticut Title 17b.** The titles index (977 words), and the history notes and
  annotations that follow each section.
- **Louisiana Title 47.** The source notes of short sections ("Acts 2008, No. 819, §1,
  eff. Jan. 1, 2008; …").

## What the measure cannot yet tell apart

- **Chrome in whole pages.** Only 10.9% of whole pages reach 0.99, against 84% to 89%
  of pages read through a manifest. Search forms, banners and currency notices outside
  navigation elements are counted as text, so a short section scores low on a page
  with a hundred words of chrome. The share of a whole-page scope means little without
  its missing runs; a region per adapter would fix it.
- **Container pages.** 411 of the 3,411 whole pages under the bar have heading-only
  rows. They are the content check's subject (hollow roots, reviewed-empty rows), not
  partial losses.
- **History and source notes.** The Montana, California, Kansas, Idaho, Connecticut and
  Louisiana rows omit them. Whether that is a loss or a deliberate gap is a decision
  per adapter, and the proposed list of deliberate gaps would record it.
- **One snapshot for many rows.** Every row of the Illinois manual cites the manual's
  table of contents, so its 7-word region is covered by 12,450 rows. The measure needs
  each row's true source.
- **Section numbers.** An HTML `labeled_sections` row keeps its number in its citation
  path, not its heading or body, so the number counts as missing.

## Next

1. Successors, by what is lost and what selects it: Maine Title 36 (after #754); the
   CMS state-plan and FCEP scopes and the Maryland TCA scope (their manifests are
   fixed); the Washington State Register and Kentucky 921 KAR 2:016 pages, which need
   an extraction fix first.
2. Decide per statute adapter whether history and source notes belong in the rows.
3. Give the statute adapters a region, so their figures can be recorded at extraction
   like the official-document extractor's and whole pages are not needed.
4. Review a release of recorded figures before adding the `low_source_coverage`
   finding (design note, proposal 2).

## Reproduce

The outputs are kept outside the repository, in
`~/reviews/axiom-corpus-source-coverage-2026-10-13/` (see its `README.md`):
`out/source-coverage-run3.json` (every page's figures and five longest missing runs),
`out/source-coverage-run3-scopes.csv` (the ranking committed here),
`scripts/show_scope.py` (prints a scope's pages under the bar with their runs) and
`scripts/run_note_tables.py` (the tables above).

```bash
uv run python scripts/measure_source_coverage.py --all --workers 4 \
  --output out/source-coverage.json --csv out/source-coverage-scopes.csv
```
