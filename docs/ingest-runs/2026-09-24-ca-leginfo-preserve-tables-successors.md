# California LegInfo section scopes re-extracted with --preserve-tables

`extract-california-code-sections` builds each section body from a LegInfo page's
`<p>` and `<i>` blocks. By default it keeps only the first copy of any block whose
text repeats an earlier one, so a merged scope loses repeated table cells,
repeated row labels and repeated statutory paragraphs. #733 added
`--preserve-tables`: each table row becomes one `cell | cell` line, a table that
LegInfo wraps in a paragraph is emitted once (212eedce6), and no block is dropped
for repeating earlier text.
The option is off by default, so every scope extracted before it keeps the loss.

This run measures that loss in every merged scope the adapter built, re-extracts
the affected scopes from their retained bytes under new versions, and records how
the new versions supersede the old ones in release selectors. Nothing is fetched
from LegInfo, no merged version changes, and nothing is published, loaded or
activated.

## Inventory and measurement

`scripts/audit_california_leginfo_table_loss.py` walks every us-ca provisions file
whose rows have `source_format: california-leginfo-section-html` and re-extracts
each retained page both ways. It compares each body with the section's visible
text, meaning the section `div` without its `h6` number heading, as a multiset of
words with the `|` separators removed. This check does not depend on the
extracted body; it reuses only the extractor's locator for the section `div`.
`docs/ingest-runs/2026-09-24-ca-leginfo-preserve-tables-audit.json`
holds the per-section results, including every block the default mode dropped.

```bash
uv run --extra dev python scripts/audit_california_leginfo_table_loss.py \
  --base data/corpus \
  --output docs/ingest-runs/2026-09-24-ca-leginfo-preserve-tables-audit.json
```

The adapter built six merged us-ca statute scopes. In the five scopes built
before #733, the default mode reproduces every committed body exactly. In all
six, the table-preserving body of every page holds exactly the words of the
section's visible text:

| Scope (`us-ca/statute/…`) | Sections | With tables | Bodies a `--preserve-tables` re-extraction changes | Blocks dropped (in tables / outside) | Visible words the committed bodies lack |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452-wic-11452.018` | 5 | 2 | 2 | 0 / 1 | 138 |
| `2026-06-27-ca-ssi-ssp-wic-12200-us-ca-sections-wic-12200` | 1 | 0 | 0 | 0 / 0 | 0 |
| `2026-07-06-ca-rtc-pit-core-us-ca-sections-rtc-17041-rtc-17043-rtc-17045-rtc-17052-rtc-17054-rtc-17073.5` | 6 | 2 | 2 | 53 / 1 | 69 |
| `2026-07-28-ca-cdss-calfresh-bbce-authority-us-ca-sections-wic-18901.3-wic-18901.5` | 2 | 0 | 0 | 0 / 0 | 0 |
| `2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7` | 1,029 | 5 | 14 | 68 / 17 | 385 |
| `2026-09-23-ca-rtc-sb-1435-us-ca-sections-rtc-17024.5-rtc-17052` | 2 | 2 | 0 | — | 0 |

The SB 1435 scope was extracted with `--preserve-tables` and the wrapped-table
fix, so it already carries the full text. Its row compares its committed bodies;
the audit JSON's default-against-preserved fields for it read 2 changed bodies,
50 / 0 dropped blocks and 21 missing words, which is what a default-mode
extraction would have lost. The 06-27 and 07-28 scopes have no
tables and no repeated blocks, so their bodies are identical in both modes and
they need no successor. `us-ca/statute/2026-07-13-recovery` was built by a
different adapter (`source_format: html`), and `--preserve-tables` does not apply
to it. Its only `<table>` is LegInfo's version picker on a "select from multiples"
page, not statute text.

The 18 section records whose bodies change, and what the default mode left out:

| Scope | Section | Tables | Blocks dropped (in tables / outside) | Visible words lacking | Lines, default → preserved |
| --- | --- | ---: | ---: | ---: | ---: |
| 06-25 | WIC 11450 | 1 | 0 / 1 | 138 | 90 → 80 |
| 06-25 | WIC 11452 | 1 | 0 / 0 | 0 | 37 → 26 |
| 07-06 | R&TC 17041 | 2 | 3 / 1 | 48 | 57 → 39 |
| 07-06 | R&TC 17052 | 8 | 50 / 0 | 21 | 84 → 100 |
| 09-14 | R&TC 17024.5 | 1 | 0 / 0 | 0 | 111 → 93 |
| 09-14 | R&TC 17041 | 2 | 3 / 1 | 48 | 57 → 39 |
| 09-14 | R&TC 17052 | 8 | 50 / 0 | 21 | 84 → 100 |
| 09-14 | R&TC 17052.6 | 2 | 7 / 0 | 33 | 27 → 24 |
| 09-14 | R&TC 17053.5 | 0 | 0 / 3 | 55 | 42 → 45 |
| 09-14 | R&TC 17053.73 | 0 | 0 / 2 | 39 | 136 → 138 |
| 09-14 | R&TC 17276 | 0 | 0 / 1 | 33 | 66 → 67 |
| 09-14 | R&TC 17955 | 0 | 0 / 1 | 25 | 24 → 25 |
| 09-14 | R&TC 18628 | 0 | 0 / 3 | 31 | 19 → 22 |
| 09-14 | R&TC 18648 | 0 | 0 / 2 | 18 | 17 → 19 |
| 09-14 | R&TC 18662 | 0 | 0 / 1 | 36 | 62 → 63 |
| 09-14 | R&TC 19025 | 1 | 8 / 0 | 8 | 25 → 12 |
| 09-14 | R&TC 19141.5 | 0 | 0 / 2 | 32 | 24 → 26 |
| 09-14 | R&TC 19183 | 0 | 0 / 1 | 6 | 24 → 25 |

R&TC 17052's 50 in-table blocks include 40 cells of the six (m) to (o) tables
that LegInfo wraps in a paragraph. The default body keeps those tables' words in
the wrapper's flattened line, so only the 10 blocks from the (b)(1) and (b)(2)
tables lose text: the 21 missing words. The same 40 blocks are counted in the
PIT core and chapter totals.

- **Tables.** Outside a wrapping paragraph, the default mode printed one cell
  per line and dropped any cell that repeated earlier text. R&TC 17041 lost the
  second rate table's header row and its `1% of the taxable income` cell. R&TC
  17052(b) lost the phaseout column of both EITC tables, and the second table's
  stub header and first two row labels: the row now read as
  `No qualifying children | $3,290 | $3,290` survived as one `$3,290`. R&TC
  17052.6 lost the second table's header, its AGI labels and its `0%` row. R&TC 19025's estimated-tax
  table lost its repeated `__`, `0`, `30` and `40` cells, so its columns could
  not be read. The WIC 11450 and 11452 tables and the R&TC 17024.5
  specified-date table lost no word, but each of their rows now reads as one
  line (`10 or more ........................ | 1,403`).
- **Repeated paragraphs.** The dedup also dropped whole statutory paragraphs that
  repeat, word for word, one given earlier for a parallel case. The R&TC
  17053.5(a)(1)(B) renter's credit lost its clause for taxable years beginning on
  or after January 1, 2026, including `(I) Two hundred fifty dollars ($250) …`
  and `(II) Five hundred dollars ($500) …`, which repeat (a)(1)(A)'s clause.
  R&TC 18628 lost (f)(1) to (3), which repeat (e)(1) to (3). WIC 11450 lost the
  second (ib) paragraph (138 words), and R&TC 17041 lost (c)(2). The others are
  17053.73, 17276(C), 17955(B), 18648(A)-(B), 18662's quoted form statement,
  19141.5(A)-(B) and 19183(A). In the retained HTML each is a separate `<p>` in
  its own subdivision, not a rendering artifact.
- **Limits of the row format.** `--preserve-tables` drops empty cells and does
  not expand `colspan`. In R&TC 17024.5, LegInfo wraps each taxable-year label
  over two or three table rows, so the date sits only on the label's last line
  (`31, 1983 ........................ | January 15, 1983`). In R&TC 19025, the
  two-row header splits the stub label, and the `colspan=4` caption reads as one
  cell. No text is lost in either case.

## Successor scopes

The successor versions are `<original version>-r2026-09-24-preserve-tables`:

| Original (`us-ca/statute/…`) | Successor | Capture date | Parent handling |
| --- | --- | --- | --- |
| `2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452-wic-11452.018` | `…-wic-11452.018-r2026-09-24-preserve-tables` | 2026-06-25 | parents nulled |
| `2026-07-06-ca-rtc-pit-core-us-ca-sections-rtc-17041-rtc-17043-rtc-17045-rtc-17052-rtc-17054-rtc-17073.5` | `…-rtc-17073.5-r2026-09-24-preserve-tables` | 2026-07-06 | parents nulled |
| `2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7` | `…-4e26e6efabc3f0c7-r2026-09-24-preserve-tables` | 2026-09-14 | `self_contain_usc_scope.py` |

The revision marker is appended to the original version, as for the committed
`-rYYYY-MM-DD-` successors such as `…-r2026-07-24-immutable`. Rerunning the adapter with a new `--version` prefix
would put the marker before the adapter's `-us-ca-sections-…` suffix. Those names
sort before their originals (`r` < `u`), and the release gate's
`scope_monotonicity` check, which orders versions by date and then by string,
would then report the swap as a regression.

```bash
uv run --extra dev python scripts/repro/us_ca_leginfo_preserve_tables_successors.py --base data/corpus
```

For each original, `scripts/repro/us_ca_leginfo_preserve_tables_successors.py`
does the following:

1. It reads the section list in the original inventory's order and checks each
   retained page against its inventory SHA-256. It also checks that each page
   has LegInfo's `single_law_section`, because the adapter fetches the page again
   when a cached copy lacks it. The order reproduces the original run id,
   including the chapter's `4e26e6efabc3f0c7` hash.
2. It copies the retained pages into a temporary download cache laid out as
   `california-leginfo-sections/<LAW>-<section>.html` and runs
   `extract_california_code_sections` into a scratch base. It uses the original
   `--version` prefix, `--source-as-of` and `--expression-date`, plus
   `--download-dir <cache> --delay-seconds 0 --preserve-tables`. It then checks
   that every source the adapter wrote is byte-identical to the retained page,
   so nothing came from LegInfo. For the chapter, this is the TY2026 run's
   command (`docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md`) with the
   same `manifests/us-ca-rtc-part-10-10.2-sections.args`, pointed at the cache.
3. It detaches the out-of-scope `us-ca/statute/<law>` parent the way the original
   was detached:
   - The 2026-06-25 and 2026-07-06 scopes had `parent_citation_path` and
     `parent_id` nulled, with no other change, by the 2026-07-15 release
     provenance repair (de4c33abb).
   - The 2026-09-14 chapter scope went through `scripts/self_contain_usc_scope.py`,
     which also records `metadata.detached_parent_citation_path` and
     `metadata.self_contained_root`.
4. It writes the scope under the successor version. Only each row's `version`,
   each source path and the coverage report's `version` change.

Each successor matches its original except where the table-preserving body
differs:

- **Provisions.** Citation paths, order, ids (path-only, as the adapter emits),
  metadata, capture dates and parent handling are unchanged. Every row differs
  from the original only in `version`, `source_path` and, for the 18 section
  records above, `body`.
- **No lost words.** No successor body lacks a word its original body had.
- **Visible text.** Every successor body holds exactly the words of its page's
  visible text.
- **Sources.** The retained pages are byte-identical copies: 5, 6 and 1,029
  files. The 1,029 chapter pages total 171 MB (163 MiB). Git stores each blob
  once, so the repository gains tree entries rather than a second copy, though a
  checkout writes both copies to disk. Each successor source directory gets a `**/*.html binary` line in
  `.gitattributes`, as the 07-28 and SB 1435 scopes do, because retained LegInfo
  HTML has trailing whitespace.
- **Inventory and coverage.** Inventory items differ only in `source_path`. The
  coverage reports differ only in `version` and are complete (5/5, 6/6 and
  1,029/1,029 matched).

`tests/test_us_ca_leginfo_preserve_tables_successors.py` checks the provisions,
sources, inventory and coverage claims above. It rebuilds the WIC and PIT core
successors offline, with the network blocked, byte for byte. For the chapter it
checks the 1,029 bodies in chunks of 150 against a fresh re-extraction and
against the visible text, and replays the parent detachment on the committed
rows. It also re-runs the audit for every scope in the audit JSON.

## How the successors supersede the originals

Tracked selectors under `manifests/releases/` are immutable, so no selector is
edited. The originals are selected as follows:

- **WIC scope:** 33 tracked selectors, including the two newest US cuts,
  `us-rulespec-2026-09-14-wave4-union` and `us-rulespec-2026-09-14-wave4-r2-union`.
- **PIT core scope:** 31 tracked selectors, the newest being the three 2026-09-13
  unions. The wave4 cuts replaced it with the chapter scope.
- **Chapter scope:** the two wave4 cuts only.

On the production side, as the workflow runs show:

- **wave4-union** was serving on 2026-09-14. The activation preview in Activate
  named corpus release run 34901357262 (21:57Z) found it already current for all
  287 of its (jurisdiction, document class) pairs. The serving WIC and chapter
  scopes are therefore the originals.
- **wave4-r2-union** was published by Publish named corpus release run
  34909195701 (workflow_dispatch, content_sha256 `528f596a…`). No activation
  workflow run has targeted it; none has run since 2026-09-14.

The successor cut is the draft selector
`docs/ingest-runs/2026-09-24-ca-leginfo-preserve-tables.selector.json`
(`us-rulespec-2026-09-24-ca-preserve-tables`). It is `us-rulespec-2026-09-14-wave4-r2-union`
with two scopes replaced in place: the WIC original by its successor and the
chapter original by its successor. The other 1,040 scopes, the quality profile
and the sort order are unchanged. It is a draft, not a tracked selector, because
`publish.yml` publishes any selector added under `manifests/releases/` when it
reaches main.

To cut it, a release branch copies it to
`manifests/releases/us-rulespec-2026-09-24-ca-preserve-tables.json`, runs
`axiom-corpus-ingest validate-release --base data/corpus --release <that file>
--ignore-r2-missing` and commits it. That is step 4 of
`scripts/sign_release_scopes.sh`, run by hand: all three successors' ingest
manifests are signed in this PR, and with nothing left to sign the script's
step 3 `git commit` exits non-zero and stops it first.

Other cuts are in flight. Draft PR #729 (`us-rulespec-2026-09-22-hts-full-schedule-union`)
also succeeds wave4-r2 and selects the WIC and chapter originals. Draft PR #740
(`us-rulespec-2026-09-24-irs-sales-tax-tables-union`) succeeds
`us-rulespec-2026-08-23-canada-338-suspension-union` and selects the WIC and PIT
core originals. `docs/ingest-runs/2026-09-23-tax-statute-policybench.selector.json`
is a further draft. The rule is the same for all of them: whichever cut lands
first, replace each selected original with its successor in that cut, rather
than cutting this wave4-r2-based draft over it and dropping its other additions
from serving. `validate-release` on the full draft (1,042 scopes) and on
`us-rulespec-2026-09-14-wave4-r2-union` gives the same result, the same 0 errors
and 546 warnings, so the replacements add no issue.

Three limits apply to every cut:

- **Never select an original with its successor.** They share every citation
  path, so each pair gives one `duplicate_release_citation` error per path. Do
  not resolve that with `scripts/deduplicate_release_selector.py`: given the
  original as canonical and the successor as an addition, it deletes the
  successor's colliding provisions and inventory items.
- **The PIT core successor goes only where the PIT core original was.** It
  shares R&TC 17041, 17043, 17045, 17052, 17054 and 17073.5 with the chapter
  successor (six duplicate citations), so this draft leaves it out. A cut that
  selects the PIT core original instead of the chapter scope, as #740 does,
  swaps in the PIT core successor. The `us-ca/form/2026-07-23-ca-2026-form-540-es`
  records also name the PIT core original in `statutory_corpus_version`.
- **The SB 1435 scope stays unselected.** It shares R&TC 17024.5 and 17052 with
  the chapter successor (two duplicate citations). The chapter successor
  re-extracts the 2026-09-14 capture, so its 17024.5, 17052 and the 28 other
  sections SB 1435 amends, repeals, or repeals and adds still hold their
  pre-SB 1435 text. Serving the
  amended text still needs a chapter capture taken after SB 1435, as the SB 1435
  run note says.

Statutory pointers in merged form scopes are not changed:

- The FTB 3514 booklet's `statutory_corpus_version` names the chapter original.
- The 540-ES records' `statutory_corpus_version` names the PIT core original.

Both originals stay in the corpus, and the pointers still identify the capture
the forms were checked against. The successor of each carries the same capture
with the full text.

## Checks

Each check below ran on `origin/main` at 233dcac58 (#733 merged) with this
branch's changes:

- `uv run --extra dev ruff check .` and `ruff format --check` on the new
  scripts and test passed.
- `uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports`
  found no issues, and neither did `mypy --explicit-package-bases` on the two
  new scripts and the new test module.
- `uv run --extra dev python -m pytest -q --timeout=60` gave 4,716 passed and
  103 skipped, with 208 integration tests deselected by the default marker
  filter. That includes
  `tests/test_us_ca_leginfo_preserve_tables_successors.py`,
  `tests/test_us_ca_rtc_sb_1435_sections.py` and
  `tests/test_us_ca_2025_ftb_3514_booklet.py`.
- `uv run --extra dev towncrier build --draft --version 0.0.0` renders the
  fragment.
- `python scripts/validate_citation_paths.py` passed (`RESULT: OK`).
- `axiom-corpus-ingest coverage --write` for each successor rewrote its coverage
  report byte-identically.
- `axiom-corpus-ingest validate-release --base data/corpus --release <draft
  selector>`: 1,042
  scopes, `ok`, 0 errors and 546 warnings. The same command on
  `us-rulespec-2026-09-14-wave4-r2-union` gives the same 546 warnings, and none
  of them is on a us-ca statute scope.
- The successors were first built on #733's pre-fix head (9cb91d1ec) with an
  independently written fix for the wrapped-table duplication. Before that build
  was discarded, it agreed byte for byte on all 1,049 files with the build on
  main (233dcac58, which includes 212eedce6).

## Signing

The successors' sources, inventories, provisions and coverage reports (added
with `git add -f`, because `data/` is ignored) are committed first, together with
this note in its final form. Each successor's ingest manifest is then signed from
a clean checkout of that commit:

```bash
AXIOM_CORPUS_INGEST_PRIVATE_KEY=... uv run --extra dev axiom-corpus-ingest sign-ingest-manifest \
  --jurisdiction us-ca --document-class statute --version <successor version> \
  --command "uv run --extra dev python scripts/repro/us_ca_leginfo_preserve_tables_successors.py --base data/corpus (run note: docs/ingest-runs/2026-09-24-ca-leginfo-preserve-tables-successors.md)" \
  --reasoning-log docs/ingest-runs/2026-09-24-ca-leginfo-preserve-tables-successors.md
```

The three manifests are at
`.axiom/ingest-manifests/us-ca/statute/<successor version>.json`. Each covers its
scope's sources, inventory, provisions and coverage report, with this note as
the reasoning log. `axiom-corpus-ingest guard-ingested`, with the repository's
`AXIOM_CORPUS_INGEST_PUBLIC_KEY`, checks them against the committed artifacts.
The private key is read into the environment of the signing command only and
is not written to any file.

This note is the reasoning log of all three manifests, so any later edit to it
requires re-signing all three. The signed commit must stay an ancestor of the
guarded head, so update this branch from main by merging, not rebasing.
