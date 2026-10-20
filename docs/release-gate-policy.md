# Release gate policy: withdrawn scopes and the content check

`validate_release` (`src/axiom_corpus/corpus/release_quality.py`) checks each
selected scope's artifacts: inventory, provisions, sources, coverage, dates and
citation uniqueness. Those checks read paths and digests, never what a body
says. The July 2026 US source recovery merged scopes that passed every one of
them while holding no legal text: empty `document` roots at statute section
paths, LegInfo menus, a version picker in place of WIC 11450, and landing pages
in place of manuals ([us-ca audit](ingest-runs/2026-09-25-us-ca-statute-recovery-audit.md),
[sibling audit](ingest-runs/2026-09-27-recovery-sibling-scopes-audit.md)).

The gate now also reads tracked files from the repository
(`ReleaseGatePolicy`, `src/axiom_corpus/corpus/release_policy.py`):

| File | Holds | A release fails when |
| --- | --- | --- |
| `manifests/withdrawn-scopes.yaml` | scopes no new cut may select | it selects one and is not a selector the scope's entry allows |
| `manifests/release-content-baseline.json` | every locked scope's known content findings, pinned to its bytes | a selected scope has a content finding and the baseline has no entry for the scope's exact bytes |
| `manifests/reviewed-empty-nodes.yaml` | document rows that review found correctly empty, with reasons | never by itself: a listed row is not a `hollow_document_root` finding ([Reviewed-empty rows](#reviewed-empty-rows)) |

Local validation (`axiom-corpus-ingest validate-release`), the
`Validate named release selectors` CI job and `scripts/publish_corpus.py`
(dry run, preflight and post-readback) call `validate_release` or its batched
counterpart `validate_releases`, so all three enforce both files.
`publish_corpus.py` reads the policy from the checkout it
publishes; `validate-release` reads it from the checkout holding `--base`, and
says on stderr when `--base` is in no checkout, in which case no file
applies. In a checkout that keeps corpus locks, the first two files are required: a
missing one fails validation and publication. The reviewed-empty list is
optional: without it no hollow root is exempt, which can only add findings. `tests/test_release_policy_repository.py`, in the required
`test (3.14)` job, fails any tracked selector that selects a withdrawn scope
without an allowance, so a non-compliant cut cannot merge either.

## Notices

Known, accepted conditions are reported as `notices`, not issues:

- `withdrawn_scope_grandfathered`: an allowed selector keeps a withdrawn scope.
- `baselined_content_findings`: a scope carries findings the baseline records.
- `reviewed_empty_document_roots`: a scope has document rows that review found
  correctly empty (`manifests/reviewed-empty-nodes.yaml`).

Notices never count as errors or warnings, so they change neither `ok` nor the
`error_count` and `warning_count` that a signed release object attests
(`publish_corpus._validation_attestation`). `to_mapping()` adds `notice_count`
and `notices` only when there are any; a report without them is exactly what it
was before. Every tracked selector therefore validates as before, apart from
its notices.

## Withdrawn scopes

Each entry of `manifests/withdrawn-scopes.yaml` names a scope and records:

- `withdrawn_on` and `decision`: when and by which release decision;
- `listed_on`: the day the entry was written (2026-10-13 for every current
  entry);
- `reason` and `run_note`: why, and the audit that shows it;
- `replace_with`: scopes a new cut selects in its place, or `carried_by`: scopes
  that already carry its text, so it is simply dropped;
- `grandfathered_selectors`: every tracked selector that reached `main` before
  the entry did and selects the scope. Tracked selectors are immutable, so they
  keep it. Some were cut after the decision but before the gate existed;
- `exceptions`: a selector that reaches `main` after the entry and keeps the
  scope on purpose, with a `reason`.

Every allowance is pinned to the selector's digest
(`axiom_corpus.release.manifest.selector_sha256`) under `selector_digests`, so
it holds only for that exact selector: an edited selector with the same name
loses it. A release that selects a withdrawn scope without an allowance fails
with `withdrawn_scope_selected`, naming the reason, the decision, the scopes to
select instead and the run note.

`test_grandfathered_selectors_predate_the_listing_and_later_ones_are_exceptions`
reads `origin/main`'s first-parent history: a grandfathered selector must have
been on `main`, at its pinned digest, before its entry reached `main` (a merged
pull request's merge commit). Order decides, not dates, so a selector merged
earlier on the day an entry is written is still grandfathered. Every version of
the registry on `main` is parsed as YAML, so an entry counts however it is
spelled. While an entry is pending (on a branch, or in pull-request CI), any
selector already on `main` at its pinned digest may be grandfathered, but not
one the same branch adds or changes; a selector deleted and recreated with other
contents has a digest that was never on `main` in time. The test needs main's
whole history: it fails in a shallow clone, or without `origin/main`, and a
registry or selector version it cannot read fails it rather than counting as
deleted. Where main's ref has another name, set `AXIOM_CORPUS_MAIN_REF` to it;
it must name main, never a branch. A stale `origin/main` can read a recently
merged entry as pending, so run `git fetch origin main` first (CI always
fetches it).
`test_no_entry_is_listed_in_the_future` keeps `listed_on` no later than the
current commit.

The 19 entries:

| Decision | Scopes | A new cut |
| --- | --- | --- |
| 2026-09-27, with #748 | `us-ca/statute/2026-07-13-recovery`; PIT core `2026-07-06-ca-rtc-pit-core-…` | selects the income tax chapter scope's `-r2026-09-24-preserve-tables` successor |
| 2026-10-03, with #757 | NY, ME, MN, UT, MI statute recovery scopes; NY article 22 core | selects the 2026-09-14 chapter scopes |
| 2026-10-03, with #757 | `us-co/regulation/2026-07-13-recovery` | selects its `-r2026-09-11-tanf-consolidated` successor |
| 2026-10-03, with #757 | FL, SC, TN regulation and IL, IN, SC, UT manual recovery scopes (landing and index pages) | drops them; the release scopes they re-fetched carry the text |
| #757 audit | `us-id/statute/2026-07-13-recovery` (no key line selects it) | selects the 2026-09-14 Title 63 chapter 30 scope |
| 2026-10-11, with #760 | `us-sc/statute/2026-07-13-recovery`; Act 110 `2026-07-24-sc-act110-…` | selects the 2026-09-27 successor that carries §12-6-520 |

The audits keep `us/guidance/2026-07-13-recovery` (the only selected carrier of
five cited ED and IRS paths) and the CO consolidated scope, and
`us-mt/regulation/2026-07-13-recovery` stays until its successor (#761) merges;
none of the three is listed. Six cuts made after the 2026-10-03 decision still
select withdrawn scopes. The 2026-10-07, 2026-10-11 and 2026-10-12 unions keep
the landing scopes and the SC statute scope. `us-rulespec-2026-10-13-snap-fy2026-memo-source-corrected`
(#848), an additive successor of the obbb-alien-snap pin, drops the CA scopes
but keeps 16: the CO regulation, landing, ME, MI, MN, NY, UT and SC statute
recovery scopes, NY article 22 core and SC Act 110. The Arizona DES ECE dated
selector (#799), merged on 2026-10-14, keeps the same 16; the w7 bundle-gaps union
(#856) keeps the seven landing scopes and both SC statute scopes, nine in all.
All six reached `main` before the gate, so they are grandfathered like every
earlier selector; the next cut in each line must take the swap. Their notice says the selector chose the
scope before the gate listed it.

### Withdrawing a scope

1. Record the audit and decision in a run note.
2. Add the entry, sorted by jurisdiction, document class and version, with
   `listed_on` set to the day you write it. List under `grandfathered_selectors`
   every tracked selector on `main` that selects the scope, and add each one's
   digest to `selector_digests`; if one lands before your entry merges, add it
   too. A selector that reaches `main` after the entry goes under `exceptions`,
   with a reason. The failure message
   of `test_no_tracked_selector_selects_a_withdrawn_scope_without_an_allowance`
   prints the digest of every selector it finds.
3. Run `uv run --extra dev python -m pytest -q tests/test_release_policy_repository.py`.

A cut that must keep a withdrawn scope adds an `exceptions` entry with its
reason; that is a release decision and is reviewed as one.

## Content check

`axiom_corpus.corpus.content_quality` reads a scope's provisions and its
retained HTML sources (XHTML included; other XML, such as Akoma Ntoso, is not
HTML). A page's navigation text is the text of its links (`a` with an `href`),
`option` and `button` elements, its `nav`, any `header` or `footer` outside an
`article`, `main` or `section`, and elements with a navigation, banner or
contentinfo role, keeping only strings that are at least 75% letters, so a
citation link such as `1990 c 604 art 2 s 21` is never navigation. Strings match
a body as whole word runs, longest first. Findings:

| Code | Rule |
| --- | --- |
| `navigation_body` | navigation strings cover at least 70% of the body's characters with at most 25 words left over, and the body is not just the row's heading, alone or after its citation label (compared without case or punctuation) |
| `navigation_prefixed_body` | at least 80 words, with a skip link or JavaScript notice in the first 60, or a first 60 words that are at least 40% navigation and open with at least 8 navigation words; the rest is less than half navigation |
| `hollow_document_root` | a bodyless `document` row with no row below it that carries text (a word with a letter or a table of figures, not navigation, not from a version picker); a bodyless document with nothing below it at all is hollow too; a row on the reviewed-empty list is not a finding |
| `version_picker_source` | an HTML source with LegInfo's `form#selectFromMultiples` and no `#single_law_section`, the shape the California adapter resolves (`states._resolve_california_multiple_section_html`) |

A body with no word with a letter is text when it is a table of figures: at
least 5 of its tokens are figures (numbers, dates, amounts, rates and ranges,
such as `$1,014.00`, `.9666`, `10/19--` or `($450,000)`), and figures are at
least half of its tokens. A list marker of one to three digits (`(1)`, `[12]`,
`3.`, `(4).`) is not a figure: a body that kept only its paragraph numbers has
lost its text. Four or more digits in brackets, such as `(1234)`, read as a figure,
because they cannot be told apart from an amount; a body of nothing but such
numbers therefore passes as a table of figures. The rule decides
only whether a row carries text. In the navigation rules a figure is a token
like any other: it counts in the coverage share, a navigation string that holds
one ("Appendix 1") covers it, and outside any navigation string it has no
letter, so it is neither a left-over word nor the end of an opening run.

`CONTENT_CHECK_VERSION` (`content-check-v2`) names these rules. Version 1
counted only words with a letter as text; see [Version 2](#version-2-2026-10-13).

### How the rules were set

The two audits classify all 789 rows of the 19 July recovery scopes against
their retained sources. On them:

- **No row with text is flagged.** None of the 618 rows the audits found to
  carry text (`legal_text`, `document_page_text`, `document_section_text`,
  `section_text_without_history`) is flagged.
- **Flagged:** all 11 LegInfo menu blocks and the WIC picker page; the WIC root,
  whose only rows below it are the menu and the picker's history lines; 36 of 47
  site-chrome blocks; 6 of 23 landing-page blocks; 10 of 40 empty sibling roots;
  and 12 of 16 chrome-wrapped section pages (all 11 NY rows and MT).
- **Missed:** the Minnesota breadcrumbs and version lists, whose links are
  mostly numbers; one Maine menu at 69% coverage; prose landing pages; the Utah
  and Michigan pages whose chrome is not a link menu; history-note footers;
  alias copies; and roots that do have text below them.

`test_the_content_check_agrees_with_the_audit` pins this table for the sibling
scopes. In a withdrawn scope the registry stops every missed row. Two retained
scopes keep missed rows that pass the gate: `us/guidance/2026-07-13-recovery`
(seven empty roots, three prose landing pages and three alias copies) and
`us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated` (four
empty roots and one prose landing page). Seven of the eleven empty roots have
text-bearing rows below them; the other four have only a landing page below them.
The four landing pages and three alias copies are tolerated.

Two rules were measured and dropped:

- **"A bodyless `document` root at a section-depth path."** The locked scopes
  hold 38,783 bodyless `document` roots, 1,708 of them in statute scopes. Most
  are the shared extractor's normal shape: the wave4 chapter scopes that replace
  the recovery scopes keep each section's text in a child block (307 roots in the
  Virginia chapter scope, 195 in Kentucky, 98 in North Carolina, 93 in New York).
  The check flags a root only when nothing below it carries text.
- **Landing pages by link density.** The share of a page's visible text inside
  links does not separate landing pages (0.007 to 0.945 on the 12 the sibling
  audit identified) from statute pages with large menus (up to 0.753). A landing
  page is caught when its blocks are navigation, or its root has none with text.

**Original scan snapshot (recorded 2026-10-13 at `be6f6da81`).** The following
table and interpretation describe that scan, not the current corpus. Across
the 2,390 locked scopes then holding provisions and an inventory, the check
reported 1,489 findings in 182 scopes:

| Class | Scopes | `navigation_body` | `navigation_prefixed_body` | `hollow_document_root` | `version_picker_source` |
| --- | ---: | ---: | ---: | ---: | ---: |
| manual | 43 | 734 | 4 | 78 | |
| guidance | 57 | 207 | 9 | | |
| policy | 47 | 94 | 69 | 44 | |
| statute | 22 | 119 | 19 | 12 | 1 |
| regulation | 11 | 41 | 1 | 54 | |
| form | 2 | 3 | | | |

Most were site menus, language pickers, "Authenticate / PDF" and "View In PDF"
blocks, and related-link lists in scopes ingested from agency web pages,
including the 2026-10-06 w6 scopes. 56 of the 69 policy prefixes were Canadian
government pages (Canada.ca, CRA, Revenu Québec) that opened with skip links.
At that snapshot, 177 of the 182 scopes were selected by a tracked selector,
and the then-newest union (`us-rulespec-2026-10-12-w5-benefits-union`) selected
152 of them.

### Version 2 (2026-10-13)

Re-measured on 2026-10-20 at combined-code commit `761cf682d`: 1,417 findings
in 182 of the 2,425 locked scopes with provisions and an inventory, plus 72
reviewed-empty roots (`content-check-v2`). The earlier 2026-10-13 measurement,
recorded at `5838d7d37`, reported 1,416 findings in 181 of 2,390 scopes. On the
current inputs, the v1 comparison (whole-body letter detection, with figure
tables and reviewed exemptions disabled) finds 1,490 findings in 183 scopes.

Rebuilding adds 34 clean scope entries to the merge's baseline at `761cf682d`,
with findings unchanged. Against main's v1 baseline at `e019e4456`, no finding
is added and 73 are removed. Against #847's historical v1 baseline at
`88c1435a5`, the baseline adds 35 scope entries, adds one finding from the OASDI
POMS RS scope and removes 73. Neither comparison changes a shared scope's
provisions or inventory digest.

| Class | Scopes | `navigation_body` | `navigation_prefixed_body` | `hollow_document_root` | `version_picker_source` |
| --- | ---: | ---: | ---: | ---: | ---: |
| manual | 44 | 735 | 4 | 10 | |
| guidance | 57 | 207 | 9 | | |
| policy | 47 | 94 | 69 | 44 | |
| statute | 22 | 119 | 19 | 12 | 1 |
| regulation | 10 | 41 | 1 | 49 | |
| form | 2 | 3 | | | |

Of the 182 scopes with findings, 176 are selected by at least one tracked
selector. The named union `us-rulespec-2026-10-12-w5-benefits-union` selects
151 of them.

The [hollow-root audit](ingest-runs/2026-10-13-hollow-document-root-audit.md)
classified all 188 historical v1 `hollow_document_root` findings against their
sources:
103 extractor defects, 12 missing or placeholder sources, 72 correctly empty
nodes and one check false positive. Version 2 acts on its section "What the check
misses and over-counts". The combined-code measurements and comparisons with
v1 are in the [run note](ingest-runs/2026-10-13-content-check-v2.md):

- **Tables of figures are text.** The false positive was IL CSMM item 67224, the
  minimum monthly SNAP benefit, whose only block is dates and amounts. Counting
  every token with a digit as text would also clear four CMS scanned attachments
  (IN-12-014, OH-12-004, OH-12-006, OH-13-001), whose pages read as a date stamp
  such as `9/4/13`: real text losses. Of the 1,384 locked rows whose whole body
  has a digit and no letter, date stamps, page numbers and stamps with SPA
  numbers hold one to four figures, and pages whose font maps glyphs to control characters hold
  stray digits, at most 14.3% of their tokens. The rule makes 45 rows text, all
  tables or lists of figures (benefit and rate tables, IRS code lists, tariff
  code annexes, ZIP code lists, revenue projections) and none of them garbled.
  Figure counts and their share use the whole body; navigation matching still
  reads at most 1,200 tokens. No locked row consists only of list markers.
  Rows of up to four figures stay what they were in v1, a few real values among
  them (a DC page with two incomes), but no root has such a row as its only
  text. The rule clears item 67224 and no other finding.
- **Reviewed-empty rows are listed with their reasons.** The 72 correctly empty rows
  in 13 scopes are in `manifests/reviewed-empty-nodes.yaml`: 45 `index`, 10
  `reserved`, 6 `empty_in_source`, 4 `deleted`, 3 `table_of_contents`, 2
  `cross_reference` and 2 `repealed`. Each has its reason, so the baseline
  no longer records them as findings. The 115 `hollow_document_root` findings
  left are the audit's 103 extractor defects and 12 missing sources.
- **The navigation threshold stays at 0.7.** ME 36 §5219-SS lost all its text
  in `us-me/statute/2026-07-13-recovery`, but its menu block is 69.2%
  navigation (its "§5219-SS PDF" and "Ch. 822 Contents" links are under 75%
  letters, so they are not navigation strings), so neither the block nor its
  root is flagged. Lowering the threshold under the combined Version 2 rules
  adds the following findings:

  | Navigation threshold | Additional `navigation_body` | Additional hollow roots |
  | --- | ---: | ---: |
  | 0.69 | 9 | 1 |
  | 0.65 | 87 | 2 |
  | 0.6 | 160 | 6 |

  The band holds text: a UK sentence announcing new National Insurance rates
  from 6 April 2026 (0.692), a heading of the Israeli National Insurance Law
  (0.691), Connecticut repeal notices beside a "Return to Table of Contents"
  link (0.660) and Minnesota manual prose whose terms are links (0.656). A bar
  for hollow roots only (a row counts as text for its root only below 0.65)
  adds two hollow roots, §5219-SS and one Wisconsin pointer page, but
  it would call those same prose and repeal-notice rows empty whenever they are
  a root's only text. The scope is withdrawn, so no new cut selects the miss; the
  2026-09-14 chapter scope that replaces it carries 5,280 characters of
  §5219-SS. The earlier audit identified missing history notes and one paragraph
  there, a partial loss described in the design note below.
  `navigation_body` also decides which blocks the HTML extractor may drop
  (axiom-corpus#852), a second reason not to lower it.
- **Partial loss is not a content-check finding.** The audit's partial losses
  include CMS SPA summaries on unflagged index pages, scanned pages read as a
  stamp and prose dropped beside a kept table. Re-measured on 2026-10-20,
  11,833 bare summary cells occur on 206 of the 210 CMS index pages with no
  content findings. The earlier count of 12,911 is also reproduced, on 218 of
  222 pages, when only `hollow_document_root` and `navigation_body` findings
  exclude a page: that definition includes 12 additional pages with
  `navigation_prefixed_body` findings and their 1,078 bare summary cells. Bare
  cells are the markup proxy for summaries the extractor dropped. These losses
  leave text below the root. Catching them takes a comparison of a source's
  visible text with the text extracted from it:
  [design note](source-coverage-check.md). The source-coverage prototype was
  also re-run on 2026-10-20 over the same 15 scopes; every per-source result
  matched the earlier measurement ([run note](ingest-runs/2026-10-13-content-check-v2.md)).

### Reviewed-empty rows

`manifests/reviewed-empty-nodes.yaml` lists, per scope, the `document` rows that
review found correctly empty, with the run note that records the review. Each
row has a `reason`:

| Reason | The official node |
| --- | --- |
| `table_of_contents` | is the source's table of contents |
| `index` | only lists links to separate documents: its sub-items, each its own row in the scope, or documents the scope leaves out on purpose (an archive of superseded memos, desk aids outside the manual) |
| `cross_reference` | is a "see" or relocation stub whose target is elsewhere |
| `reserved` | is a reserved item |
| `deleted` | is a deleted item: only a deletion marker is left |
| `repealed` | is a repealed part: only its repeal notice and history are left |
| `empty_in_source` | has an empty content area in the official source |

and a `note` that says what the reviewer saw and where (the retained source, or
for Illinois, whose scope retains no per-item page, the live page). The test is
whose text is missing. A node whose own content is a document the scope does
not retain is a missing source, not an empty node, and stays a finding: a
manual section whose text is a linked PDF hard card, a Glossary whose entries
are sub-pages that were not ingested. A node that only indexes separate
documents has no text of its own, whether the scope holds those documents or
leaves them out on purpose; if they should be in the corpus, that is a coverage
gap of the scope, recorded in its run note, not an empty row. The audit drew
this line; two listed rows index documents outside their scope (North Dakota's
archived memos, Washington's desk aids).

A withdrawn scope may be listed. Validation never content-checks a withdrawn
scope, so its entry only keeps the baseline and the CI check in step with the
audit.

The list never changes what a row is: it removes only `hollow_document_root`
findings at the listed paths. A listed root's blocks are still checked (a menu
block below a reviewed table of contents is still `navigation_body`), and
`ScopeContentScanner.text_paths`, which recovery reconciliation reads, still
counts a reviewed root as carrying no text. In `validate_release`, a scope's
listed rows that are hollow become one `reviewed_empty_document_roots` notice,
for a scope checked by scan and by baseline alike.

The baseline records the hollow roots its scan exempted in `reviewed_empty`.
Validation reuses that scan only while all those roots remain on the list;
removing a listed root, including by removing the optional file, forces a fresh
scan so the root becomes a finding again. Baseline entries without exemptions
omit the field.

`content-check --check-baseline` scans with the list and fails when a listed
scope is not locked or a listed row is not a hollow root of its scope, so a row
that gains text (a successor extraction, a fixed extractor) or a mistyped path
cannot stay listed. Adding a row removes its finding, so the list and the
baseline change in the same commit:

1. Read the row's source (and its descendants) and record the review in a run
   note.
2. Add the row under its scope, sorted, with `reason`, `note` and the run note.
3. Run `uv run axiom-corpus-ingest content-check <scope> --update-baseline`, then
   `uv run --extra dev python -m pytest -q tests/test_release_policy_repository.py`.

A successor scope is a new version: it does not inherit its predecessor's
entries, and its empty rows are reviewed again.

### The baseline

Because so many selected scopes carry findings, grandfathering *selectors* for
the content check would fail the next cut of every line. The baseline instead
records, for every locked scope, its findings (often none), pinned to the sha256
of its provisions and inventory files. The inventory pins each source file's
sha256, and validation checks the sources against it, so the two digests pin
every byte the check reads. In `validate_release`:

- a withdrawn scope is not content-checked (the withdrawal decides it);
- a scope whose digests match its entry and whose applied empty-root exemptions
  remain listed is not read again, and its recorded findings become one
  `baselined_content_findings` notice;
- any other scope is scanned as its provisions stream for validation, and each
  finding is an error (`navigation_body`, `navigation_prefixed_body`,
  `hollow_document_root`, `version_picker_source`), recorded or not: a scope
  whose provisions or inventory are rewritten must have its entry updated
  (`--update-baseline <scope>`). An entry for other bytes or removed empty-root
  exemptions also gives a `content_baseline_mismatch` warning, and a baseline
  made by other check rules a single `content_baseline_stale` warning;
- either way, rows on the reviewed-empty list are not findings, and the baseline
  is built with the list (`--update-baseline` reads it).

So existing scopes stay selectable, and a new scope with chrome, a hollow root
or a picker fails the release that selects it until its extraction is fixed or
its findings are recorded on purpose. A clean new scope needs no entry.

### The extractor drops navigation blocks

The official-document HTML extractor (`documents._extract_html_blocks`) asks
`content_quality.is_navigation_block` of every positional block it makes: the
heading walk's `block-N` blocks, a WebWorks page's blocks, and the whole-root
fallback. The helper is the `navigation_body` rule above, read against the same
navigation strings of the same retained bytes, with four more conditions so
that a dropped block is a list of the page's link labels and nothing else:

- every token lies in a navigation string or is only link separators (`|`,
  `>`, `»`, `•` ...), so a status line, a pointer, a figure beside a linked label
  or a table mark (✓, ✗, a dash) keeps its block;
- the body is at least two navigation strings
  (`NAVIGATION_BLOCK_MIN_STRINGS`): a lone link can be a section's whole text;
- no matched string is longer than 12 words
  (`NAVIGATION_BLOCK_MAX_STRING_WORDS`): long link text can be prose;
- no matched string ends a sentence (a final period or exclamation mark): a
  label names a page, a sentence inside a link can be a definition.

A body longer than the 1,200 words the check reads, or one that repeats its
heading, is never dropped. A dropped block's ordinal is used up, so the blocks
after it keep the citation paths an unfiltered extraction gives them; encodings
that cite `block-N` paths resolve the same way in a successor scope. The filter
drops nothing from a page whose manifest declares its sections
(`labeled_sections`, `anchor_range`), from HTML read out of a JSON field, which
the check cannot see, or from a page `scripts/recover_ingest_batch.py`
re-encodes before extracting. `html_keep_navigation_blocks: true` in a
manifest's `extraction` keeps every block the filter would drop.

So every block this filter drops is a row the check would flag, and the check
still reports the flagged rows the extractor keeps. Existing scopes do not
change: a successor is a separate, signed ingest. The calibration, a measurement
over the 148 scopes with `navigation_body` rows, and the scope families that
would gain from successors are in
[the run note](ingest-runs/2026-10-13-html-navigation-blocks.md);
`scripts/measure_html_navigation_blocks.py` repeats the measurement.

#### Declared navigation

A manifest can also name a publisher's navigation, for chrome the filter keeps
on purpose (a lone tab link, a link list with unlinked section codes):

- `html_navigation_selectors` match navigation elements; a positional block
  whose every string lies inside a matched element is dropped. A block with
  any other text keeps its whole body.
- `html_navigation_heading_selectors` match headings; the positional block a
  matched heading starts is dropped.

Matched elements stay in the tree, so headings and block boundaries are those of
an unfiltered extraction, and a dropped block's ordinal is used up as above.
`html_drop_selectors` cannot stand in for them on positional pages: they remove
elements before the blocks are numbered, so every block after one they empty is
renumbered. The declarations are independent of the filter: they apply to HTML
read out of a JSON field too, and `html_keep_navigation_blocks: true` keeps the
filter's blocks while still dropping the declared ones. A manifest whose pages
have no positional blocks (declared sections, JSON records or source-only JSON,
a JSON field read as one block, a source that is not HTML or JSON) cannot
declare navigation; the extractor raises. A declared block is
dropped whether or not the check would flag it, so a manifest that declares
navigation is measured before its successor is ingested
(`scripts/measure_html_navigation_blocks.py` reports declared drops apart from
the filter's). The Washington DSHS EA-Z and Texas HHS handbook manifests declare
theirs ([run note](ingest-runs/2026-10-13-html-navigation-selectors.md)).

### Commands

```bash
# Findings of some scopes (positional: <jurisdiction>[/<class>[/<version>]])
uv run axiom-corpus-ingest content-check us-ca/statute/2026-07-13-recovery

# Check the whole baseline against fresh scans (CI runs this in the test job)
uv run axiom-corpus-ingest content-check --all --check-baseline --workers 4

# Record a scope's findings on purpose, or rebuild the baseline after a rule change
uv run axiom-corpus-ingest content-check us-xx/statute/<version> --update-baseline
uv run axiom-corpus-ingest content-check --all --update-baseline --workers 4
```

A named scope that matches no locked scope with provisions and inventory is an
error (exit 2), so a mistyped scope cannot pass as a clean check of nothing.
A full check parses about 1.9 GB of HTML and reads 2.5 GB of provisions. Earlier
measurements took about 90 seconds on four workers locally and about three
minutes on the CI runner. CI runs the check on three workers after its
four-worker pytest run, including when tests fail; the two checks run
sequentially within the runner's four cores. Raising `CONTENT_CHECK_VERSION`
requires rebuilding the baseline in the same change: validation ignores a baseline made by other
rules, and CI's check fails on it.

## Recovery reconciliation

`scripts/recover_ingest_batch.py` decides which planned citations a batch
recovered. It used to match paths only, over every provisions file, the batch's
own scope included, so the us-ca scope's empty roots resolved their own
targets. It now:

- fetches the locked sources as well as the provisions (about 1.9 GB of
  sources in a full checkout; clones from the shared cache on APFS), then
  indexes, per
  citation path, the scopes in which the row at that path carries text by the
  rules above (`ScopeContentScanner.text_paths`);
- counts a document's own planned scope only when the document's recorded
  result is parsed, so leftover rows cannot vouch for themselves. A run whose
  snapshot for a document has left `recovered-fetched` carries that document's
  earlier parse forward unchanged, and a run limited to one document
  (`AXIOM_RECOVERY_ONLY_DOCUMENT_ID`) carries every other document's earlier
  result forward, parse failures and their provenance errors included. A
  reparse that fails records an unparsed result, and its targets then resolve
  only through other scopes, in this run and every later one alike;
- reads bodies in the per-document check as well;
- counts, for each remaining class in the summary, the class's unresolved
  citations, not every target of a partly resolved document.

On the retained us-ca pages, the ten R&TC targets resolve, as
`exact-cross-scope`, to the income tax chapter scope that carries their text,
and WIC 11450(a)(1)(A) resolves to nothing
(`tests/test_recover_ingest_reconciliation.py`).
