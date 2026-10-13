# Design note: a source-coverage check for partial text loss

Status: proposal (2026-10-13). No code. It follows the
[hollow-root audit](ingest-runs/2026-10-13-hollow-document-root-audit.md), which
found losses that the release content check
([release gate policy](release-gate-policy.md#content-check)) cannot see, and the
measurements in the [content-check v2 run note](ingest-runs/2026-10-13-content-check-v2.md).

## The gap

The content check reads rows: it flags a row made of page navigation, a row that
opens with chrome, and a `document` root with no text below it. A scope that keeps
some of a page's text and drops the rest passes, because something with text is
left. The audit found:

- 12,911 CMS SPA summaries lost on 218 index pages the check does not flag (every
  date on all 240 pages), and the state, dates and topics of 16 FCEP summaries;
- scanned state-plan pages read as a date stamp or typed overlay (1,021 pages
  are candidates);
- prose dropped beside a kept table (ME §5111), history notes dropped beside
  menu children (10 CA R&TC roots), inline text omitted in WA EA-Z and the NH FAM;
- ME 36 §5219-SS, whose only block is a menu just under the navigation
  threshold (v2 keeps that threshold; see the run note).

## The measure

For each source document, the **coverage** is the share of the words a reader sees
in the part of the source the extractor reads that also appear in the text it
extracted from that source (the bodies and headings of every row that cites it).
Words are counted as a multiset of casefolded tokens with a letter or a digit, so
a phrase that appears once in the source and once in a row counts once, and a
repeated phrase must be kept as often as it appears.

## What a prototype shows

`source_coverage_prototype.py` (in the evidence folder of the run note) applies
the measure to whole HTML pages, with scripts, styles and the content check's
navigation elements removed, for a handful of scopes:

| Scope | HTML sources | Median | 10th percentile | Under 0.5 | What the low pages lose |
| --- | ---: | ---: | ---: | ---: | --- |
| `us-pa/manual/2026-07-21-pa-snap-handbook` | 297 | 1.00 | 1.00 | 0 | nothing |
| `us-nh/manual/2026-09-10-tanf-state-policy-manual` | 715 | 1.00 | 0.99 | 9 | |
| `us-wa/manual/2026-07-21-wa-eaz-manual` | 200 | 0.96 | 0.67 | 6 | |
| `us-ny/statute/2026-07-13-recovery` | 11 | 0.93 | 0.92 | 0 | nothing (the chrome is kept, not the text lost) |
| `us-ca/statute/…-income-tax-chapter-…-r2026-09-24-preserve-tables` | 1,029 | 0.61 | 0.34 | 347 | breadcrumbs and the search box; history notes |
| `us-va/statute/2026-09-14-income-tax-chapter` | 307 | 0.57 | 0.09 | 127 | the site's report builder and search box |
| `us-me/statute/2026-09-14-income-tax-chapter-us-me-title-36` | 1,777 | 0.15 | 0.03 | 1,330 | lettered paragraphs: §656 keeps "1. Real estate." (15 characters) of a 1,446-word page |
| `us-ny/regulation/2026-09-14-income-tax-regulations` | 318 | 0.34 | 0.01 | 197 | Westlaw chrome; the Part notes #854 restores |
| `us-ct/policy/2026-09-13-medicaid-state-plan` | 6 | 0.09 | 0.03 | 6 | SPA summaries, dates and topics |
| `us/policy/2026-07-05-cms-chip-fcep-spa` | 36 | 0.02 | 0.01 | 36 | SPA summaries; the site's search and filter form |
| `us-md/statute/2026-07-03-md-tca-statutes` | 2 | 0.03 | 0.02 | 2 | the whole statute |
| `us-me/statute/2026-07-13-recovery` | 6 | 0.03 | 0.01 | 6 | the whole section |

Two lessons:

1. **The measure finds real partial loss the content check misses.** The Maine
   chapter scope, which replaces the withdrawn recovery scope and which
   rulespec-us cites, has no content finding, yet its section rows keep only the
   numbered subsection heads on many pages (spot checks of §§176-A, 656 and
   5122). That is the lettered-paragraph loss the 2026-09-27 sibling audit
   recorded and #754 repairs; the measure shows its size. §5219-SS there is at
   0.71: its section heading, its history notes and the paragraph that reduces
   the credit for tax years beginning before 2025 are missing.
2. **The whole page is the wrong denominator.** Chrome outside `nav`, `header`,
   `footer` and links (breadcrumb text, search forms, a report builder, site
   footers in `div`s) pulls well-extracted Virginia and California pages down to
   0.1 to 0.6, and the FCEP pages count the site's search form among their
   losses. A check on whole pages would either flag most statute scopes or miss
   real loss.

## Proposal

1. **Measure at extraction, over the extractor's own region.** Each extractor
   already knows what it reads: the manifest's `html_text_selector` and drop
   selectors, the PDF page window and its start and stop markers, the DOCX
   labeled-sections range, the navigation blocks it drops on purpose
   (`is_navigation_block`, axiom-corpus#852) and the declared navigation of
   #857. At the end of each source document it counts the region's words and the
   extracted words and writes, per source, `region_words`, `kept_words`,
   `deliberately_dropped_words` and the ten longest missing runs into the scope's
   coverage report. A release-time check cannot rebuild those regions for 2,390
   scopes made by dozens of adapters; the extractor can record them for free.
2. **Report first, gate later.** Add a `low_source_coverage` finding, computed
   from the recorded figures, to the content check only after a release of
   report-only figures has been reviewed per family. Start with a conservative
   bar (coverage under 0.5 of a region of at least 50 words) and list deliberate
   gaps with reasons, the way the reviewed-empty list does for empty rows:
   `segmentation: source_only`, tables kept elsewhere, appendices out of scope.
3. **PDFs.** Count the text layer (and OCR text where OCR ran) of the page window.
   A page whose images cover at least 90% of it and whose layer has fewer than 30
   words with a letter (the #854 OCR rule) is "unread" unless OCR ran, which
   catches the stamp-only scans directly.
4. **Normalization.** NFKC, casefold, soft hyphens and line-end hyphenation
   joined, ligatures expanded, and tokens with a letter or digit only, so a
   whitespace or punctuation change never reads as loss. The ten longest missing
   runs, not a share alone, are what a reviewer reads.
5. **Existing scopes.** Locked coverage reports cannot change, so measure them
   once offline (whole pages for HTML where no selector applies, the manifest's
   selector where one does) to rank successor work. The prototype's numbers
   above already rank the Maine chapter scope near the top.

## Open questions

- Repeated boilerplate across a scope's pages (a disclaimer kept once) inflates
  loss on every page but the first; count per scope as well as per source?
- Sources split into many rows (a manual's table of contents feeding hundreds
  of rows, as in the Illinois manual, whose rows all name one snapshot): the
  measure needs each row's true source, which that scope does not record.
- JSON and XML sources (CT's JSON table of contents, eCFR XML) need their own
  visible-text rules.
