# New York Tax Law line structure and Form IT-214 (TY2025)

Date: 2026-09-23
Branch `ingest-pb-ny-606-it214`, cut from `origin/main` (942e138e7).
Purpose: PolicyBench root cause r09 (New York real property tax credit renter cap, and the
2025 flat credit tables). The encodings need N.Y. Tax Law § 606(e), (e)(7) and (e)(7)(D) and the
official 2025 Form IT-214 tables.

## Problem

Both New York statute scopes that carry § 606 hold a body with no structural line breaks:

- `us-ny/statute/2026-07-06-ny-tax-article22-core-us-ny-sections-tax-601-tax-606-tax-614-tax-615-tax-616`
  (OpenLegislation API JSON): the API string escapes each line break as the two characters `\n`,
  and `_api_document_text` kept them, so the 418,902-character § 606 body is one line.
- `us-ny/statute/2026-09-14-income-tax-chapter` (Senate HTML through `extract-official-documents`):
  the generic HTML extractor read `div.nys-openleg-result-text` with whitespace collapsed, so each
  section is one line in a `block-1` row under a bodiless document root.

## Code change

`src/axiom_corpus/corpus/state_adapters/new_york.py`:

- `normalize_new_york_openleg_text` turns the OpenLegislation fixed-width text into one line per
  paragraph the publisher starts on its own line (a line indented by exactly two spaces starts a
  line; hard-wrapped continuation lines join with one space and prose justification spaces
  collapse). A label the publisher prints inline after a heading or its parent label, such as
  § 606(e)(1), (e)(2)(A) and (e)(3)(A), stays on that line (see "Known limits"). It keeps table
  lines (deeper indent, or a run of three or more spaces) exactly as published; the line after a
  table line starts its own line. Two narrower rules keep table headers and version-marked rows
  apart from the prose above them: a margin line directly above a table line starts its own line
  when the prose before it ends with a colon and the line does not begin with `(` (so the header
  "If the taxpayer's federal adjusted gross" of § 606(e)(3)(B) no longer joins "shall be:"), and a
  line beginning with `*` (OpenLegislation's multiple-version marker) starts its own line. The
  whitespace-separated word sequence is unchanged.
- `_api_document_text` decodes the escaped `\n` before normalizing (API and sections extractors).
- `new_york_openleg_html_text` rebuilds the OpenLegislation layout from a Senate page: `<br />` is a
  line break and an empty line (`<br /><br />`, the page's rendering of a paragraph indent) becomes a
  line break plus the two-space indent. `_page_body` uses it when the text node carries `<br />`,
  otherwise keeps its earlier behaviour. On the retained pages the rebuilt layout equals the retained
  API text byte for byte for §§ 601, 614, 615 and 616 (same revisions; § 606 was revised on
  2026-09-04 between the two captures).

GitNexus impact analysis could not run (its index reports a storage-version mismatch: database file
version 42, build storage version 40). Callers were checked by hand: `_api_document_text` is called
by `extract_new_york_openleg_api` and `extract_new_york_openleg_sections`; `_page_body` only by
`parse_new_york_law_page` (`extract_new_york_consolidated_laws`); `extract-state-statutes` dispatches
both the consolidated-laws and the OpenLegislation API adapters. Only New York statute extraction is
affected. No released artifact is rewritten.

Cross-check of the two paths: the July API text of § 606 (revision active 2026-06-05) and the
September Senate page of § 606 (revision 2026-09-04) normalize to the same 138 lines for subsection
(e); across the whole section the two differ only where the 2026-09-04 revision runs `(1)` in after
the (c) and (i) headings. On all 93 retained pages and the five retained July API bodies the
normalized word sequence equals the source's. The two narrower rules change exactly seven lines
across the 93 bodies (§ 601(a)(9) table header; the four § 606(e)(3) table headers; two
`* (xxxiii)`/`* (xxxv)` rows of the § 606(i) table) and nothing else. No line in the 93 successor
bodies starts with a wrapped cross-reference such as `(c) of section`: every label-headed line that
does not come from a two-space-indented source line either follows a table or is itself a table row.
Of the 1,491 lines kept verbatim as table lines, the 321 without a digit, `$`, rule, "percent" or
"is:" (208 distinct) were reviewed by eye: each is a row, header or column continuation of a
published multi-column table (§ 601 recapture tables, § 606(a), (c), (e), (i) and § 612 tables).

## Successor statute scope

`scripts/repro/us_ny_tax_article_22_line_structure.py` rebuilds
`us-ny/statute/2026-09-14-income-tax-chapter-r2026-09-23-line-structure` from the 93 retained
Senate pages of `2026-09-14-income-tax-chapter` (no publisher traffic): each page's SHA-256 is
checked against the released inventory, the bytes are copied to
`new-york-senate-html/TAX/<section>.html`, the page is parsed with `parse_new_york_law_page`, and
every body is checked to carry the released word sequence. One `section` row per section with the
body on the section row (the shape of the July API and recovery NY scopes); the 93 `/block-1`
rows of the released scope are not carried. `source_as_of` and `expression_date` stay 2026-09-14.
Coverage: 93 / 93, complete.

Row labels follow the New York adapter, not the generic extractor: the released row for § 606 has
`citation_label` and `heading` "N.Y. Tax Law § 606. Credits against tax"; the successor row has
`citation_label` and `legal_identifier` "N.Y. TAX Law § 606" and `heading` "Credits against tax",
the adapter's `N.Y. {law_id} Law § {section}` form that the July API scope already carries. Citation
paths and row ids are unchanged; only the display label changes. Mapping law IDs to their title-case
names would change every New York adapter scope, so it is left for a separate change.

Controller swap: select `us-ny/statute/2026-09-14-income-tax-chapter-r2026-09-23-line-structure`
in place of `us-ny/statute/2026-09-14-income-tax-chapter` (never both: they share the 93 section
paths). A scratch what-if selector of the 16 `us-ny` scopes of `us-rulespec-2026-09-14-wave4-r2-union`
with this swap and the IT-214 scope added (17 scopes) has 7,514 rows, all distinct paths; keeping both statute
scopes would duplicate 93 paths (`duplicate_release_citation` under the release's
`complete-expression-dates-v1` profile).

The July core scope is out of the latest selectors (`us-rulespec-2026-09-14-wave4-union` and
`-wave4-r2-union` carry `2026-09-14-income-tax-chapter` instead; the newest selectors that carry the
July scope are the 2026-09-13 unions, such as `us-rulespec-2026-09-13-followup-union`) and is not
re-emitted: its five sections are a subset of the September successor's paths, so the two could
never be selected together, and the § 606 word sequence is identical in both revisions (65,236
words; § 606(e) is the same 138 lines). If a July successor is ever wanted, the fixed adapter re-emits it
offline from the retained JSON. The sections extractor appends
`-us-ny-sections-tax-601-tax-606-tax-614-tax-615-tax-616` to `--version`, so this command writes
`2026-07-06-ny-tax-article22-core-r2026-09-23-line-structure-us-ny-sections-tax-601-tax-606-tax-614-tax-615-tax-616`
(checked in a scratch base: five section rows, no escaped `\n`, source bytes identical to the
retained JSON, § 606(e)(7)(D) on its own line, coverage 5 / 5):

```bash
uv run axiom-corpus-ingest extract-new-york-openleg-sections --base data/corpus \
  --version 2026-07-06-ny-tax-article22-core-r2026-09-23-line-structure \
  --source-dir data/corpus/sources/us-ny/statute/2026-07-06-ny-tax-article22-core-us-ny-sections-tax-601-tax-606-tax-614-tax-615-tax-616 \
  --section TAX:601 --section TAX:606 --section TAX:614 --section TAX:615 --section TAX:616 \
  --source-as-of 2026-07-06 --expression-date 2026-07-06
```

## Resolving § 606(e)(7)(D)

New York OpenLegislation asserts sections, so the corpus row is the section
`us-ny/statute/TAX/606`; `/e`, `/e/7` and `/e/7/D` are slices of its body. A line-anchored label walk
(the first line starting `(e) `, then `(7) ` inside it, then `(D) ` inside that, each ending at the next
sibling label) finds nothing in either released body (0 line breaks) and, in the successor body,
returns `[84639:114480]` for (e), `[106734:108041]` for (e)(7) and, for (e)(7)(D), exactly "(D) To a
tenant if the adjusted rent for the residence exceeds four hundred fifty dollars per month on
average." `tests/test_us_ny_tax_article_22_line_structure.py` pins that walk.

Known limits:

- The label walk above is this repository's check. The encoder's own slicer (the code in
  `axiom-encode` that raised `CorpusSourceSliceError`) was not run against the successor body in this
  change; confirm `/e`, `/e/7` and `/e/7/D` with it before re-pointing an encoding.
- The corpus anchor generator (`generate_anchors_for_provision`, behind `generate-anchors`) builds
  anchors for 80 of the 93 successor sections and raises `duplicate anchor citation paths` for 13,
  § 606 among them. For § 606 its outline parse starts at `(2)`: `(a)` and `(1)` run in after the
  section heading (`§ 606. Credits against tax. (a) Investment tax credit (ITC). (1) ...`), other
  labels run in after their parent (`(3) Determination of credit. (A) ...`), and the section has
  hyphenated (`(e-1)`) and doubled (`(aa)`) subsections. That is a property of `anchors.py`,
  unchanged here; no anchors are emitted for this scope.
- Label-like tokens can open a table row: the § 606(i) credit table prints wrapped
  cross-references such as `(aa)`, `(ee)`, `(ff)`, `(jj)`, `(vvv)`, `(j-1)` and `(n-2)` at the start
  of a column-1 line. Those lines keep their published column gap (a run of three or more spaces),
  which prose lines never have after normalization, so a label walk that skips such lines (or bounds
  each search by the parent's sibling labels, as for (e)) is not misled. A bare walk for
  `us-ny/statute/TAX/606/aa` from the top of the section would hit the table row first.
- The official text prints § 606(e)(1)(C) as `(c) "Household gross income" means ...` (lower-case
  label, both revisions); the corpus keeps the publisher's text, so a case-sensitive walk for
  `/e/1/C` finds nothing.
- Runs of labels printed on one line stay on one line (for example § 606(e)(3)(B)(i) runs in after
  `(B) For taxable years beginning on or after January first, two thousand twenty-five,`), so
  `/e/3/B` resolves by a line walk but `/e/3/B/i` needs an in-line label search.
- A two-column table row whose columns are separated by only two spaces (for example
  `(xxiv) Security training tax credit  Amount of credit ...` in § 606(i)) is read as prose and its
  gap collapses to one space; its words and order are unchanged.

## Form IT-214 (TY2025)

`manifests/us-ny-it-214-real-property-tax-credit-ty2025.yaml`, version
`2026-09-23-ny-it-214-ty2025`, the state TY2025 forms pattern (`single_block` PDFs,
`us-ny/form/tax/ty2025/<form>`, expression date 2025-01-01, as `us-ny/form/tax/ty2026/it-2105-i`):

| citation path | source URL | SHA-256 |
|---|---|---|
| `us-ny/form/tax/ty2025/it-214` | https://www.tax.ny.gov/pdf/current_forms/it/it214_fill_in.pdf | `38708017127e49e7dedf4196cd8f25cf263fbda591ea1fcc2f604779c6aba2be` |
| `us-ny/form/tax/ty2025/it-214-i` | https://www.tax.ny.gov/pdf/current_forms/it/it214i.pdf | `e8cc5a14cb3c464ac3fd82fdf62c2684bd11ae95177f7f6495b01b5bc62881f8` |

Retrieved 2026-09-23 (about 16:04Z) with the corpus client. Re-fetched with curl at 17:03Z and again
at 18:04Z: HTTP 200, same SHA-256 and byte length for both (502,663 and 313,517), `Last-Modified`
17 Nov 2025; the
PDF titles read "... Tax Year 2025" and each has three pages.
https://www.tax.ny.gov/forms/income_credit_forms.htm lists "IT-214 (Fill-in)" (through
`/pit/ads/efile_addit214-2d.htm`, which links `it214_fill_in.pdf` and `it214_fill_in_2d.pdf`) and "IT-214-I (Instructions)" (`it214i.pdf`). Re-running
`axiom-corpus-ingest extract-official-documents --base <scratch> --version 2026-09-23-ny-it-214-ty2025
--manifest manifests/us-ny-it-214-real-property-tax-credit-ty2025.yaml` (a fresh download) reproduces
the source bytes, inventory, provisions and coverage byte for byte. The form body carries Table 1
(line 9 rates, 0.035 to 0.065), Table A (age 65 or older, $375 to $150) and Table B (under 65, $75
to $50) with every cell in row order, matching the rate table of § 606(e)(1)(A)(ii) and the credit
tables of § 606(e)(3)(B)(i) and (ii); the instructions carry the $450 average monthly rent test of
§ 606(e)(7)(D).
Coverage: 4 / 4, complete.

## Checks

- `uv run --extra dev ruff check .`: all checks passed. `uv run --extra dev mypy
  src/axiom_corpus/corpus --ignore-missing-imports`: no issues in 93 source files.
- `uv run --extra dev python -m pytest -q tests/test_corpus_new_york.py
  tests/test_us_ny_tax_article_22_line_structure.py tests/test_us_ny_it214_ty2025.py`: 30 passed.
  Neighbouring suites (`-m "not integration and not slow"`): `tests/test_corpus_nyc_admin_code.py
  tests/test_corpus_nycrr.py tests/test_us_ny_snap_manuals.py tests/test_us_ny_snap_regulations.py
  tests/test_corpus_state_statute_completion.py tests/test_citations.py
  tests/test_citation_path_grammar.py tests/test_idaho_statute_successor.py`: 138 passed;
  `tests/test_corpus_documents.py tests/test_corpus_release_quality.py
  tests/test_corpus_rulespec_paths.py`: 146 passed; `tests/test_ny_converter.py
  tests/test_build_ny_tanf_compatibility_scope.py`: 30 passed, 4 deselected. Line coverage of the new
  adapter code (`normalize_new_york_openleg_text`, `_openleg_table_line`,
  `new_york_openleg_html_text` and the two changed call sites) from `tests/test_corpus_new_york.py`
  alone: every new line executed.
- `axiom-corpus-ingest coverage ... --write` for both scopes: complete (93 / 93 and 4 / 4), coverage
  files unchanged by the rewrite.
- `scripts/validate_citation_paths.py` over the whole `data/corpus/provisions` tree (576,838 records,
  425,671 unique paths): OK, every irregular-family count equal to its ratchet baseline.
- `axiom-corpus-ingest validate-release` on scratch selectors under `complete-expression-dates-v1`:
  the two new scopes alone, 0 issues; the 16 `us-ny` scopes of `us-rulespec-2026-09-14-wave4-r2-union`
  with the statute swap and the IT-214 scope added (17 scopes), 0 issues (7,514 rows, all paths distinct); the
  same plus the released `2026-09-14-income-tax-chapter`, 93 `duplicate_release_citation` errors, as
  expected.
- `scripts/repro/us_ny_tax_article_22_line_structure.py --base <scratch>` reproduces the successor
  inventory, provisions, coverage and all 93 source files byte for byte.
- `towncrier check --compare-with origin/main` after the content commit: both fragments found; both
  render in `towncrier build --draft --version 0.0.0` (the CI command).
- Not run: the whole-repository pytest suite (machine load) and `publish_corpus.py --dry-run` (it only
  accepts a tracked selector under `manifests/releases/`, and this change adds none).
- Signing: the new scope artifacts sit under the ignored `data/` tree and were added with
  `git add -f`. After the content commit (`c0c44ea6`), both scopes were signed over that clean
  commit with the commands below and the two manifests under `.axiom/ingest-manifests/us-ny/` were
  committed separately (96 applied files for the statute scope, 5 for the form scope);
  `axiom-corpus-ingest guard-ingested --base-ref origin/main` then verifies them.

```bash
AXIOM_CORPUS_INGEST_PRIVATE_KEY=... uv run --extra dev axiom-corpus-ingest sign-ingest-manifest \
  --repo . --base data/corpus --jurisdiction us-ny --document-class statute \
  --version 2026-09-14-income-tax-chapter-r2026-09-23-line-structure \
  --command "uv run --extra dev python scripts/repro/us_ny_tax_article_22_line_structure.py --base data/corpus --source-base data/corpus (run note: docs/ingest-runs/2026-09-23-ny-tax-606-line-structure-it214.md)"
AXIOM_CORPUS_INGEST_PRIVATE_KEY=... uv run --extra dev axiom-corpus-ingest sign-ingest-manifest \
  --repo . --base data/corpus --jurisdiction us-ny --document-class form --version 2026-09-23-ny-it-214-ty2025 \
  --command "axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-09-23-ny-it-214-ty2025 --manifest manifests/us-ny-it-214-real-property-tax-credit-ty2025.yaml (run note: docs/ingest-runs/2026-09-23-ny-tax-606-line-structure-it214.md)"
```
