# California statute recovery rows: audit and supersession

`us-ca/statute/2026-07-13-recovery` (33 rows, 11 retained LegInfo pages) came
from the July US source recovery. It was added in ed8464a37 (2026-07-15) and
merged by #344 (a9d5ec29f, 2026-07-16); its manifest was re-signed in 66706c527
(2026-07-21). It was built by `scripts/recover_ingest_batch.py`,
not by the `california-code-sections` adapter, and its rows have
`source_format: html`. A reviewer found that its WIC 11450 rows hold no statute
text. This run audits every row and every retained page, finds where the text
is carried faithfully, and decides whether to build a successor scope.

The merged scope is unchanged. Nothing is fetched, published, loaded or
activated, and no tracked selector is added or edited.

**Decision: no successor scope.** The R&TC text the scope holds is already
carried, with identical text, by the 2026-09-14 income tax chapter scope, at the
same section paths and as proper `section` rows. The WIC page's retained bytes
hold no statute text, so no successor built from them can carry WIC 11450.
The wave4 cuts already leave the scope out. Every later cut should do the same,
replacing it as described in
[How later cuts supersede the scope](#how-later-cuts-supersede-the-scope).

## How the rows were made

The rows are exactly what `_generic` in `scripts/recover_ingest_batch.py` makes of
each retained page. `_generic` calls the shared document-block extractor
(`axiom_corpus.corpus.documents._extract_blocks` and `_provision_records`).
Replaying it on the 11 retained pages reproduces all 33 provision rows and all
33 inventory items field for field
(`test_the_generic_document_extractor_reproduces_the_committed_scope`). Each
page becomes:

- a `document` root at the single citation the recovery plan declared, with
  no body and `citation_label`/`heading` set to the source id with spaces
  (`us ca code rtc p8`);
- `block-1`, headed `Code Section`: the page header, i.e. LegInfo's menu
  (`skip to content`, `home`, `accessibility`, `FAQ`, `feedback`, `sitemap`,
  `login`, …) and the breadcrumb, which ends in the page heading (`Code Section`,
  or `Welfare and Institutions Code - WIC`);
- `block-2`: on an R&TC page, headed with the printed number (`17014.`) and
  holding the section text without its history note; on the WIC page, headed
  `Code Section` and holding the picker's two history lines.

The shared extractor always builds a document root with a heading and no body
(`_provision_records`, `src/axiom_corpus/corpus/documents.py:3683-3708`). The
defect is where the recovery put that root: at the section's own citation path,
so the section path resolves to an empty row. `_generic` also accepted the WIC
picker. Its only check tied to the declared citation is that the target's last
path segment occurs in the page text (`recover_ingest_batch.py:650`). For
`us-ca/statute/wic/11450/a/1/A` that segment is `A`.

The copy of the recovery plan the script reads (`us-source-recovery-plan.json`
at the repository root) is untracked. Revision 3 of the plan is tracked at
`origin/recovery/us-source-map:manifests/migrations/us-source-recovery-plan.json`.
Each `us-ca-code-*` entry there has parser `state-statutes:california`,
`proposed_version` `2026-07-13-recovery` and exactly one target; the WIC target
is `us-ca/statute/wic/11450/a/1/A`. With that parser and one declared target,
today's dispatch in `_parse` sends a page to `_targeted_state_html`, not
`_generic`. That function returns one `section` row
whose body is the page's whole visible text, menu included. Rerunning the
recovery script therefore cannot give clean rows either. A replacement has to
come from the `california-code-sections` adapter, which reads only the
`single_law_section` container.

### Why the recovery report counted these rows as recovered

`recovered-coverage-report.json` marks every one of the 11 pages as
`"parsed": false`, `"rows": 0`, with the issue "official source snapshot is not
present in recovered-fetched". Yet it counts each page's citation as `1/1`
resolved, by method `exact-cross-scope`. The final reconciliation in
`scripts/recover_ingest_batch.py` is global by design (lines 1250-1260). It
indexes the citation paths of every provisions file under `data/corpus`
(`_all_ingested_citation_paths`, lines 130-144), including this scope's own
rows. A target counts as resolved when its path appears anywhere
(`_resolve_across_ingested_scopes`, lines 147-152). The check matches on path
alone and never reads a body, so this scope's empty roots satisfied its own
targets.

## Audit

```bash
uv run --extra dev python scripts/audit_us_ca_statute_recovery_rows.py --base data/corpus --output docs/ingest-runs/2026-09-25-us-ca-statute-recovery-audit.json
```

The script types each retained page and gives each row one verdict. It uses the
adapter's own LegInfo helpers (`_california_html_section_body`,
`_california_html_history`) as the reference extraction.
[`2026-09-25-us-ca-statute-recovery-audit.json`](2026-09-25-us-ca-statute-recovery-audit.json)
holds the per-page and per-row results. During this run two further audits,
which are not committed, reached the same verdicts on all 33 rows and all 11
pages: one parsed the HTML from scratch with lxml, the other ran the adapter's
parsing functions.

### Retained pages

All 11 files hash to the SHA-256 in their provenance sidecar and in the signed
ingest manifest's `applied_files`. All 11 sidecars carry the same `fetched_at`,
`2026-07-14T01:42:23Z`. The manifest itself verifies: `verify_ingest_manifest`,
with the repository's `AXIOM_CORPUS_INGEST_PUBLIC_KEY`, reports no issue. The
manifest faithfully attests to defective content. Its coverage summary reads
complete, 33 of 33 matched, because coverage compares inventory citation paths
with provision citation paths and never reads a body
(`compare_provision_coverage`, `src/axiom_corpus/corpus/coverage.py:60-82`).

| Retained file (`official-documents/…`) | LegInfo URL `sectionNum` | Page type | Printed section and history note |
| --- | --- | --- | --- |
| `us-ca-code-rtc` | RTC `17014.` | `single_law_section` | 17014. (Amended by Stats. 1994, Ch. 1243, Sec. 4. …) |
| `us-ca-code-rtc-p2` | RTC `17016.` | `single_law_section` | 17016. (Repealed and added by Stats. 1955, Ch. 939.) |
| `us-ca-code-rtc-p3` | RTC `17017.` | `single_law_section` | 17017. (Amended by Stats. 1961, Ch. 537.) |
| `us-ca-code-rtc-p4` | RTC `17029.` | `single_law_section` | 17029. (Amended by Stats. 1991, Ch. 117, Sec. 9. …) |
| `us-ca-code-rtc-p5` | RTC `17034.` | `single_law_section` | 17034. (Amended (as amended by Stats. 1993, Ch. 31) by Stats. 1993, Ch. 877, …) |
| `us-ca-code-rtc-p6` | RTC `17038.` | `single_law_section` | 17038. (Amended by Stats. 1983, Ch. 323, Sec. 82.5. …) |
| `us-ca-code-rtc-p7` | RTC `17053.6.` | `single_law_section` | 17053.6. (Amended by Stats. 1991, Ch. 472, Sec. 6. …) |
| `us-ca-code-rtc-p8` | RTC `17054.7.` | `single_law_section` | 17054.7. (Amended by Stats. 1993, Ch. 877, Sec. 12. …) |
| `us-ca-code-rtc-p9` | RTC `17061.` | `single_law_section` | 17061. (Amended by Stats. 1977, Ch. 1252.) |
| `us-ca-code-rtc-p10` | RTC `17062.1.` | `single_law_section` | 17062.1. (Added by Stats. 2025, Ch. 231, Sec. 6. (SB 711) …) |
| `us-ca-code-wic` | WIC `11450.` | `selectFromMultiples` | none: a version picker (title `Law section`) |

The WIC page is LegInfo's "Found multiple results … Please Select from the List
below" form (`form#selectFromMultiples`). It has no `single_law_section` and no
section text. It offers two versions of WIC 11450, each as a link that posts
`op_statues`/`op_chapter`/`op_section` back to LegInfo:

1. `2024`/`798`/`1`: "(Amended (as amended by Stats. 2022, Ch. 715, Sec. 2) by
   Stats. 2024, Ch. 798, Sec. 1.)"
2. `2024`/`798`/`2`: "(Amended (as added by Stats. 2022, Ch. 715, Sec. 3) by
   Stats. 2024, Ch. 798, Sec. 2.)"

When the adapter fetches a picker page it posts those links
(`_resolve_california_multiple_section_html`,
`src/axiom_corpus/corpus/states.py:5368-5412`). `extract-california-code-sections`
then rejects any page that still lacks `single_law_section`
(`states.py:2415-2417`). The recovery extractor did neither.

### Rows

| Verdict | Rows | Citation paths |
| --- | ---: | --- |
| `empty_document_root` | 11 | `us-ca/statute/rtc/{17014, 17016, 17017, 17029, 17034, 17038, 17053.6, 17054.7, 17061, 17062.1}` and `us-ca/statute/wic/11450/a/1/A` |
| `leginfo_page_chrome` | 11 | `<each root>/block-1` |
| `picker_history_notes_only` | 1 | `us-ca/statute/wic/11450/a/1/A/block-2` |
| `section_text_without_history` | 10 | `us-ca/statute/rtc/<section>/block-2` for the ten R&TC sections |

So 23 of the 33 rows hold no section text:

- **Every root is empty.** That includes each row at a real section path such as
  `us-ca/statute/rtc/17014`. A row-level reader (the stored row,
  `corpus.current_provisions`) gets an empty body headed with the source id
  (`us ca code rtc`). The text sits one level down, at a synthetic `block-2`
  path. axiom-encode composes a body for the root from `block-1` and `block-2`,
  menu first (see
  [What resolves against these rows downstream](#what-resolves-against-these-rows-downstream)).
- **Every `block-1` is page chrome.** The audit accepts a body as chrome only
  when all three hold:
  - its lines are exactly LegInfo's 15-line menu followed by the entries of the
    page's own `#breadcrumbs` list (`California Law >>`, `>>`, then the page
    title);
  - each menu line appears in the page outside the statute container;
  - no line is a line of the section text.

  `test_classifier_refuses_altered_rows` checks that the verdicts are strict.
  Each of these mutations makes a row `unclassified`: a dropped paragraph, a
  changed breadcrumb, truncated chrome, and swapped or truncated picker notes.
- **The WIC rows carry nothing from WIC 11450.** The root
  `us-ca/statute/wic/11450/a/1/A` names subparagraph (a)(1)(A), but the row
  stands for the whole picker page and its body is empty. `block-1` is chrome
  whose breadcrumb ends in `Welfare and Institutions Code - WIC`. `block-2` is
  the two picker history lines above, joined into one paragraph.

The ten R&TC `block-2` bodies are faithful. Each equals, whitespace-normalized,
the adapter's default body of the same retained page less its last line, the
history note. The row's `heading` holds the printed number (`17014.`). Neither
the history note nor the division/part/chapter headings appear in the body.

## Where the text is carried

| Recovery section | Carried by | Row | Same text |
| --- | --- | --- | --- |
| R&TC 17014, 17016, 17017, 17029, 17034, 17038, 17053.6, 17054.7, 17061, 17062.1 | `us-ca/statute/2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7` | `us-ca/statute/rtc/<section>`, `kind: section`, captured 2026-09-14 | yes: each body equals, whitespace-normalized, the adapter's body of the recovery's own 2026-07-14 page, history note included |
| WIC 11450 | `us-ca/statute/2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452-wic-11452.018` | `us-ca/statute/wic/11450`, `kind: section`, captured 2026-06-25 | not comparable: the recovery page has no text. The CalWORKs row is version 1 of the picker (below) |

None of the ten R&TC sections changed between the two captures. The chapter
scope's rows hold the full text and the history note under the section path
itself. #742 (open) adds `--preserve-tables` successors of three scopes: both
reference scopes and the PIT core scope. None of these ten sections has a table
or a dropped repeated block, so the chapter successor's bodies for them match
the chapter scope's.

On `origin/main` (b5b637167), no us-ca scope other than these three carries
any of the eleven section paths or any of their descendants. The recovery
scope is the only one with `us-ca/statute/wic/11450/a/1/A` or any `block-N` path
under these sections.

### WIC 11450 has two current versions; the corpus carries one

The premise that WIC 11450 "is already carried faithfully" by the CalWORKs scope
holds for one of the two versions LegInfo lists, not for the section as a whole:

- The CalWORKs row is version 1, amended by Stats. 2024, Ch. 798, **Sec. 1**. Its
  LegInfo history reads: "Section conditionally operative July 1, 2021, or later
  date, as prescribed by its own provisions. Conditionally inoperative on or
  after July 1, 2024, by its own provisions. Repealed conditionally by its own
  provisions. See later operative version, as amended by Sec. 2 of Stats. 2024,
  Ch. 798." Its subdivision (p) makes it inoperative "on July 1, 2024, or on the
  date the department notifies the Legislature that the Statewide Automated
  Welfare System can perform the necessary automation to implement Section 11450,
  as added by Section 3 of the act that added this subdivision, whichever date is
  later".
- Version 2, the "later operative version" (Stats. 2022, Ch. 715, Sec. 3, amended
  by Stats. 2024, Ch. 798, **Sec. 2**), is carried by no us-ca scope. Its text
  is not in the corpus: the recovery's `block-2` and the CalWORKs row's history
  and (p) only name it.
- Which version governs on a given date turns on the date of that CDSS
  notification. The corpus does not record that date.
- A read-only fetch of LegInfo's WIC Article 6 text on 2026-09-25 prints both
  versions. It is not retained in the corpus. Word by word:
  - **Same text.** (a)(1)(A) and its maximum-aid table are identical in both.
  - **Version 2 differs only in these places.** It drops "commencing October 1,
    2023," from the perinatal home-visiting clause. It extends the notice-to-quit
    homelessness test with "or any notice that could lead to an eviction,
    regardless of the circumstances cited in the notice". It widens the
    domestic-violence clause ("including, but not limited to, a parent or child
    with whom they were living") and drops the October 1, 2023 start date from
    the case-plan condition, keeping the condition itself. Its (n) makes it operative on July 1, 2024 (or the
    notification date) instead of July 1, 2021. It has no (o) or (p).
- **The carried version also lost a paragraph.** The CalWORKs row was extracted
  in the adapter's default mode, which dropped the second, word-identical
  `(ib)` paragraph (138 words). #742's `--preserve-tables` successor restores it,
  and is still version 1.
- When the adapter meets a picker, it keeps the last offered version whose post
  returns a `single_law_section` (`states.py:5391-5412`). The retained
  2026-07-14 picker lists version 1 first, so a run on that picker in which both
  posts succeed would keep version 2. The CalWORKs page fetched 2026-06-25 is
  version 1. What LegInfo returned that day is not retained: a picker in another
  order, a failed post, or version 1 served directly.

A recovery successor cannot close this gap: its WIC bytes are the picker. It is
recorded under [Follow-ups](#follow-ups) as a separate ingest.

## What resolves against these rows downstream

rulespec-us cites eleven of the recovery paths, all at their roots:

- The ten R&TC modules (`us-ca/statutes/rtc/17014.yaml` … `17053/6.yaml` …
  `17062/1.yaml`) each cite their section root, `us-ca/statute/rtc/<section>`.
- `us-ca/policies/cdss/calworks/monthly-aid-payment.yaml` cites
  `us-ca/statute/wic/11450/a/1/A`, in `source_verification` and in eight proof
  atoms for (a)(1)(A) and its `$326` … `1,403` maximum-aid table.

No `block-N` path is cited by code. Two rows of
`docs/coverage/needs-closure-2026-09-11/tax-matrix.csv` (lines 335 and 360) use
`rtc/17062.1/block-2` and `rtc/17054.7/block-2` as evidence. The wave4
consolidation note lists all 22 block paths among the paths it dropped.

rulespec-us validates against the release its `.axiom/toolchain.toml` pins,
`us-rulespec-2026-08-08-obbb-alien-snap`, which selects this scope. axiom-encode
resolves a citation in `corpus_resolver.py` (`resolve_local_corpus_source`):

- The exact path is tried first. Ancestors are tried only when no active exact
  row exists (`_citation_lookup_groups`, `_parent_citation_paths`).
- A row with a null body gets a body composed from its descendants.
- An ancestor hit is sliced to the requested fragment.

Under the current pin:

- **WIC.** The empty root at `us-ca/statute/wic/11450/a/1/A` wins the exact
  lookup. Its body is composed from `block-1` (the menu) and `block-2` (the two
  picker history lines). None of the module's eight proof excerpts occurs in
  those two bodies. The module passes only under its waiver in
  rulespec-us `known-validation-gaps.yaml` (rulespec-us#782, expires
  2026-12-21).
- **R&TC.** Each root's body is composed from the chrome block and the text
  block, so the section text is present, preceded by the menu.

Once a cut supersedes the scope as described below:

- **WIC.** The exact lookup misses and the resolver falls back to
  `us-ca/statute/wic/11450` in the CalWORKs scope, sliced to (a)(1)(A). Three of
  the eight excerpts occur verbatim in the CalWORKs row. The other five do not
  occur verbatim in it. They use `...` elisions, a reformatted table line
  (`Maximum aid: 1 $326; 2 $535; …`) or a straight apostrophe. Those five are a
  rulespec-us repair either way. A changed issue list also changes the waiver's
  fingerprint.
- **R&TC.** Each path resolves to the chapter scope's section row.
- **Why the chapter scope has to come in.** Dropping the recovery scope without
  adding the chapter scope would leave the ten R&TC paths with no carrier.

After supersession the WIC path is therefore not dangling for validation: it
resolves by ancestor slice to real text. axiom-encode's migration inventory
still reports any ancestor-slice resolution as a `parent-slice-dependency`
failure (`src/axiom_encode/cli.py`, in the migration-inventory loop). rulespec-us
draft PR #1365 re-points the citation to `us-ca/statute/wic/11450`, which clears
that failure too.

## Why no successor scope

1. **No text would be recovered.** The ten text-bearing rows duplicate text the
   chapter scope already carries at the proper section paths, in a newer capture
   and with the history notes. The other 23 rows carry nothing a successor could
   keep.
2. **A successor could never share a release with the chapter scope.** The
   recovery scope and the chapter scope share the ten R&TC section paths. One
   release with both gives exactly ten `duplicate_release_citation` errors
   (`test_the_recovery_scope_cannot_join_a_release_with_the_chapter_scope`). A
   successor holding the same ten sections would collide the same way, so no
   wave4-line cut could select it. Its only use would be a one-for-one swap in
   the canada-338 line, which keeps PIT core. There it would give rulespec-us
   the same text the chapter scope gives. A re-extraction of the retained July
   pages is the adapter body of those pages, and that body equals the chapter
   scope's body for all ten sections. It would add a signed scope and gain
   nothing.
3. **WIC 11450 cannot come from these bytes.** The adapter cannot use the
   retained picker page. It ignores a cached page without `single_law_section`
   and refetches from LegInfo (`states.py:5338-5342`). Carrying WIC 11450 version 2, or both versions, needs a new
   LegInfo capture and a rule for two concurrent versions at one citation path.
   That is a new ingest, not a successor of this scope.
4. **The recovery-only paths carry no text.** `us-ca/statute/wic/11450/a/1/A` is
   an empty row, and the `block-N` paths are artifacts of the block extractor.
   Serving them preserves no statute text.

## How later cuts supersede the scope

Tracked selectors under `manifests/releases/` are immutable. `publish.yml` runs
on every push to `main` that changes `manifests/releases/*.json`
(`.github/workflows/publish.yml:7-11`), so adding a selector is a release
decision. This run adds none. It records the rule for the next cut in each line.

**Where the scope is selected.** 32 tracked selectors select it:

- the 23 July cuts, from `us-rulespec-2026-07-13` through
  `us-rulespec-2026-07-31-idaho-statutes-current`, including
  `us-rulespec-ny-snap-2026-07-17` and `us-rulespec-snap-2026-07-21`;
- the August cuts `us-rulespec-2026-08-03-ecps-pit-tariff-union`,
  `-08-08-obbb-alien-snap`, `-08-09-cutover-surface-union` and
  `-08-23-canada-338-suspension-union`;
- the four September unions through `us-rulespec-2026-09-13-followup-union`;
- `us-rulespec-2026-09-24-snap-fy2027-cola` (#747, merged 2026-09-25), the
  successor of `obbb-alien-snap` that adds the SNAP FY 2027 COLA memorandum.

`us-rulespec-2026-09-14-wave4-union` and `us-rulespec-2026-09-14-wave4-r2-union`
do not select it.

**The wave4 line has already superseded it.** The wave4 consolidation
([2026-09-14-wave4-release-consolidation.md](2026-09-14-wave4-release-consolidation.md))
removed this scope and the PIT core scope and selected the chapter scope in their
place. Its "Dangling rulespec-us citations" section lists
`us-ca/statute/wic/11450/a/1/A` and leaves the re-point to rulespec-us. For
axiom-encode the path is not dangling: it resolves by ancestor slice
([above](#what-resolves-against-these-rows-downstream)). In both
wave4 selectors the us-ca statute scopes are the CalWORKs, SSI/SSP, CalFresh BBCE
and chapter scopes
(`test_the_newest_tracked_cuts_already_swap_the_recovery_scope_for_the_chapter`).
PR #742's draft replaces two of those with their `--preserve-tables` successors.

**Two older lines still carry it,** both built for rulespec-us's pin:

- **The obbb-alien-snap line.** rulespec-us pins
  `us-rulespec-2026-08-08-obbb-alien-snap` (`.axiom/toolchain.toml` on its
  `main`). #747 cut its successor, `us-rulespec-2026-09-24-snap-fy2027-cola`,
  unchanged in us-ca.
- **The canada-338 line.** rulespec-us#1389 (open) stages a re-pin to
  `us-rulespec-2026-08-23-canada-338-suspension-union`. Draft PRs #740
  (`us-rulespec-2026-09-24-irs-sales-tax-tables-union`) and #746
  (`us-rulespec-2026-09-24-al-ty2025-income-tax-union`) extend that union.

All of these select this scope and the PIT core scope, and not the chapter
scope. In them the recovery scope is the only carrier of the ten R&TC section
paths, so dropping it alone would drop those sections. The next cut in either
line should therefore:

1. remove `us-ca/statute/2026-07-13-recovery` and
   `us-ca/statute/2026-07-06-ca-rtc-pit-core-us-ca-sections-rtc-17041-rtc-17043-rtc-17045-rtc-17052-rtc-17054-rtc-17073.5`;
2. add `us-ca/statute/2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7`,
   or its #742 successor if #742 has merged. The chapter scope carries all six
   PIT core sections with byte-identical bodies, which is why PIT core leaves
   with the recovery scope. It also carries all ten recovery sections;
3. if #742 has merged, also replace the CalWORKs original with its #742
   successor, as #742 prescribes for every cut.

**This changes #742's rule for the #740 line.** #742's run note says a cut that
keeps the PIT core original instead of the chapter scope, "as #740 does", swaps
in the PIT core successor. That rule predates this audit and assumes the line
keeps the recovery scope. Here the line drops the recovery scope, so it must add
the chapter scope, so it drops PIT core. That holds for the original and for
#742's PIT core successor alike: either one would give six
`duplicate_release_citation` errors against the chapter scope. #742's PIT core
successor then has no planned cut. It stays correct and signed for any cut that
keeps PIT core, which after this audit means one that also keeps the recovery
scope.

After the swap, two rows of `us-ca/form/2026-07-23-ca-2026-form-540-es` still
name the PIT core version in `metadata.statutory_corpus_version`, a scope the
release no longer selects. Nothing in axiom-corpus `src/` or `scripts/` reads
that field. Both wave4 selectors are in the same state, and the pointer still
identifies the 2026-07-06 capture the form was checked against.

Applied to the canada-338 union's us-ca statute scopes, that swap passes
`validate_release` with strict warnings and 0 issues
(`test_the_same_swap_validates_on_the_canada_338_line`); the obbb-alien-snap line
selects the same us-ca statute scopes. Every PIT core path is
also a chapter-scope path. Two runs over the whole union, one as it stands and
one with the swap applied, give the same result: `ok`, with the union's 541
`missing_parent_id` warnings. Those all belong to
`us-ca/regulation/2026-07-13-recovery`, and the swap adds no issue. This is the
same swap the wave4 consolidation made. For rulespec-us, a cut with this swap changes what
the ten R&TC modules and the CalWORKs module resolve to. The ten R&TC modules
get the chapter scope's rows; the CalWORKs module gets the ancestor slice of
`wic/11450`. A re-pin to such a cut therefore re-fingerprints the CalWORKs
module's waiver.

**Enforcement.** `test_no_new_tracked_selector_selects_the_recovery_scope`
freezes the 32 selectors above. It fails if any other tracked selector selects
this scope, and names the swap to make. `test (3.14)` is a required check on
`main`, so the rule gates merges. It covers tracked selectors only: ten older
draft selectors under `docs/ingest-runs/` still select the scope, and a cut
copied from one of them fails when it becomes tracked. It is an interim guard;
follow-up 3 is the durable one. #740 and #746, as drafted, would fail it
once they are updated from a `main` that has this test. Each needs the swap
above before it is cut.

**Rules for every cut:**

- **Never select the recovery scope with the chapter scope or its successor.**
  The ten shared paths fail the release gate. Do not resolve that with
  `scripts/deduplicate_release_selector.py`. It removes the added scope's
  colliding provisions and inventory items. With the recovery scope as
  canonical, it would delete the chapter scope's ten good rows and keep the
  empty roots.
- **Activation is per `(jurisdiction, document_class)`, last activation wins.**
  `corpus.activate_corpus_release` upserts `corpus.active_scope_pointer` for each
  pair the release carries and logs the takeover in
  `corpus.scope_activation_history`
  (`supabase/migrations/20260719043000_profiled_release_activation.sql:254-303`).
  Activating any release that selects the recovery scope therefore points
  `us-ca/statute` back at it, and at the PIT core scope, even after a wave4-line
  release. That includes the canada-338 union rulespec-us#1389 is moving to.
  - **The workflow gate catches this.** The `activate-release.yml` workflow runs
    `scripts/check_release_gate.py`. Its `scope_monotonicity` check
    (`check_release_gate.py:310-322`) reports a regression when a pair's newest
    incoming version sorts before the active one. For `us-ca/statute` that is
    `2026-07-28-…` in the canada-338 line against `2026-09-14-…` in wave4. The
    check can be overridden only with the `allow_regression` input.
  - **The direct path does not.** `scripts/activate_release.py` does not run the
    gate. Its `--dry-run` still names the takeover.
- **The release gate does not catch these rows.** `validate_release` passes the
  scope alone with 0 issues under strict warnings
  (`test_release_validation_does_not_see_the_defects`). Its only empty-text
  check warns when a row has neither body nor heading
  (`src/axiom_corpus/corpus/release_quality.py:759-765`). Every empty root here
  has a heading. Only this audit and its tests record the defects.

## Follow-ups

These are recorded, not done here:

1. **rulespec-us CalWORKs module.** `monthly-aid-payment.yaml` cites a path that
   today resolves to page chrome, and its eight proof failures are waived. After
   supersession three excerpts occur verbatim in the text the path resolves to. The module's
   remaining excerpt repairs, and the re-point in draft PR #1365, belong to
   rulespec-us. Two more points belong there too:
   - **Which version.** The module should say which WIC 11450 version it
     encodes. Per LegInfo on 2026-09-25, (a)(1)(A) and its table read the same
     in both versions.
   - **Which pin.** Its current pin (`obbb-alien-snap`) and the pin
     rulespec-us#1389 stages (the canada-338 union) both select this scope.
2. **WIC 11450 version 2.** Capture the "later operative version" (Stats. 2024,
   Ch. 798, Sec. 2) and decide how the corpus carries two concurrent LegInfo
   versions at one citation path. The adapter keeps one version per path today.
3. **Release gate.** Two changes would stop `validate_release` passing scopes
   like this one:
   - a content check that fails bodies which are site navigation, empty
     `document` roots at section paths, and version-picker sources;
   - a data-driven list of withdrawn scopes, each mapped to its replacement,
     that `validate_release` errors on. Local validation, the selector CI and
     `publish_corpus.py` would then all enforce the rule, for this scope and for
     the sibling recovery scopes below. That list would replace this note's
     single-scope test.
4. **Recovery accounting.** Make the recovery reconciliation read bodies, and
   stop it from counting a scope's own rows, before the recovery script is used
   again.
5. **Sibling recovery scopes.** A read-only sweep, run during this audit and not
   committed, covered all 70 `2026-07-13-recovery*` provisions files (8,741
   rows). It matched chrome by whole-line menu terms, and each hit was then
   read. The LegInfo picker
   exists only in this scope, and no other us-ca scope has LegInfo chrome.
   The same family of defects appears elsewhere in the July batch:

   | Scope | What the sweep found |
   | --- | --- |
   | `us-ny/statute/2026-07-13-recovery` | all 11 section rows start with page chrome before the law text |
   | `us-id/statute/2026-07-13-recovery` | all 5 documents hollow; `block-1` is the legislature menu |
   | `us-me/statute/2026-07-13-recovery` | 6 navigation blocks; 5 of 6 documents hollow |
   | `us-mn/statute/2026-07-13-recovery` | 5 chrome blocks |
   | `us-ut/statute/2026-07-13-recovery` | all 3 section rows start with page chrome |
   | `us-sc/statute/2026-07-13-recovery` | `12-6-520` has navigation and 12-6-510's table, not 12-6-520 |
   | `us-mi/statute/2026-07-13-recovery`, `us-mt/regulation/2026-07-13-recovery` | one row each with a chrome prefix |
   | `us-co/regulation/2026-07-13-recovery` (and its `-r2026-09-11-tanf-consolidated` successor), `us-fl/regulation/…`, `us-sc/regulation/…`, `us-tn/regulation/…`, `us-il/manual/…-r2026-07-17-dedup`, `us-in/manual/…`, `us-sc/manual/…`, `us-ut/manual/…`, `us/guidance/…` | a retained source that is a landing, index or table-of-contents page |

   Several of these were swapped out by the wave4 consolidation. Each still
   needs its own audit against the cuts that select it.
6. **Stale references.**
   - `docs/coverage/needs-closure-2026-09-11/tax-matrix.csv` lines 335 and 360
     cite `block-2` paths of this scope.
   - The `supersedes` entry in `manifests/tax-agent-queue.yaml` (and
     `scripts/state_tax_ty2026_amounts.py:673`) holds for the R&TC half only,
     because the chapter scope does not carry the WIC path.

## Checks

Run on `origin/main` b5b637167 with this branch's files:

- **The audit.** The command above rewrote the committed audit JSON
  byte-identically. `uv run --extra dev python -m pytest -q
  tests/test_us_ca_statute_recovery_audit.py`: 18 passed.
- **The full suite.** `uv run --extra dev python -m pytest -q`: 4,759 passed,
  105 skipped and 208 integration tests deselected, run on cf46a725b (before
  #747). On b5b637167 a rerun reached 94% with no failure before it was
  interrupted. This module and #747's new test pass there (21 passed). CI's
  required `test (3.14)` runs the full suite on this branch.
- **Lint.** `uv run --extra dev ruff check .` and `ruff format --check` on the
  new script and test passed.
- **Types.** `uv run --extra dev mypy src/axiom_corpus/corpus
  --ignore-missing-imports` found no issues, and neither did `mypy
  --explicit-package-bases --follow-imports=silent` on the new script and test.
  Without `--follow-imports=silent`, mypy also reports the existing `no-redef`
  at `scripts/recover_ingest_batch.py:40`, which the test imports; `main` has
  the same error.
- **Changelog.** `uv run --extra dev towncrier build --draft --version 0.0.0`
  renders the fragment.
- **Release validation.** `validate_release` gives:
  - the recovery scope alone, strict warnings: 0 issues;
  - the recovery scope with the chapter scope: exactly the ten
    `duplicate_release_citation` errors;
  - the canada-338 union's us-ca statute scopes with the swap, strict warnings:
    0 issues;
  - the whole canada-338 union, as it stands and with the swap: `ok` with the
    same 541 `missing_parent_id` warnings.
- **The merged manifest.** `verify_ingest_manifest` on the merged ingest
  manifest, with the repository's public key: no issues.
- **Ingest guard.** `axiom-corpus-ingest guard-ingested --base-ref origin/main
  --head-ref HEAD`, with `AXIOM_CORPUS_INGEST_PUBLIC_KEY` from the repository's
  Actions variable: "No protected corpus artifact changes." `towncrier check
  --compare-with origin/main` finds the fragment.

## Signing

No scope is added, so there is no ingest manifest to sign. This note is not the
reasoning log of any manifest. The branch touches no protected corpus artifact
and no ingest manifest.
