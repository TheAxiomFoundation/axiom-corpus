# California LegInfo concurrent versions: WIC 11450 and three other sections

This run adds the scope
`us-ca/statute/2026-09-26-ca-leginfo-concurrent-versions-us-ca-sections-wic-11450--all-wic-11451.5--all-rtc-17552.3--all-rtc-17563.5--all`.
It carries every version that California's Legislative Counsel site (LegInfo)
listed on 2026-09-26 for the four multi-version code sections the corpus
carries. Each version is a row at its own same-number variant path, for example
`us-ca/statute/wic/11450--operative-2024-07-01`. The run also extends the
`california-code-sections` adapter so that a section spec can select concurrent
versions (`WIC:11450@all`).

No merged scope changes and no release selector is added. Nothing is
published, loaded or activated.

## Why

The 2026-09-25 audit of the July recovery scope (branch
`fix/us-ca-recovery-chrome-audit`, unmerged) found that LegInfo lists two
versions of WIC 11450 while the corpus carries one:

- `us-ca/statute/2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452-wic-11452.018`
  holds version 1 (as amended by Stats. 2024, Ch. 798, Sec. 1) at
  `us-ca/statute/wic/11450`.
- Version 1's history note points to a "later operative version". Its (p) makes
  version 1 inoperative on the later of two dates: July 1, 2024, or the date the
  department notifies the Legislature that the Statewide Automated Welfare System
  can implement the later version. The later version's (n) makes it operative on
  that same date.
- No scope carried the later version's text.

## What LegInfo lists

For a multi-version section, `codes_displaySection.xhtml` answers with a
"selectFromMultiples" picker, a JSF form, instead of the section. Each link on
the picker posts three fields:

- `op_statues`, `op_chapter` and `op_section`: the year, chapter and section of
  the act that last added or amended that version;
- the version page repeats them in its `printPopup()` script.

The survey on 2026-09-26 was read-only. It sent one GET, without following
redirects, for each of the 1,037 sections that us-ca statute scopes carry from
LegInfo section pages. 1,033 answered with the section. Four answered with a
302 to the picker:

| Section | Carrier of the plain path | LegInfo's versions, in picker order | Plain path holds |
| --- | --- | --- | --- |
| WIC 11450 | CalWORKs 2026-06-25 | Stats. 2024 Ch. 798 Sec. 1; Stats. 2026 Ch. 310 Sec. 2 | the first |
| WIC 11451.5 | CalWORKs 2026-06-25 | Stats. 2019 Ch. 27 Sec. 59; Stats. 2022 Ch. 588 Sec. 5; Stats. 2022 Ch. 588 Sec. 6 | the third |
| R&TC 17552.3 | income tax chapter 2026-09-14 | Stats. 2002 Ch. 34 Sec. 22; Stats. 2002 Ch. 35 Sec. 22 | the first |
| R&TC 17563.5 | income tax chapter 2026-09-14 | Stats. 2002 Ch. 34 Sec. 24; Stats. 2002 Ch. 35 Sec. 24 | the second |

"Plain path holds" is read from each carrier's retained page: its
`printPopup()` triple and its `sectionuid`.

### Why the adapter kept one version, and which one varies

`_resolve_california_multiple_section_html` (`src/axiom_corpus/corpus/states.py`)
reads the picker's form fields once. It then posts every link with those same
fields and keeps the last response that holds a `single_law_section`.

LegInfo accepts one post per form view state. In the same session, a second
post with that view state gets the picker back. This was observed live on
2026-09-25 and again on 2026-09-26, and
`test_an_unselected_spec_keeps_the_legacy_picker_behaviour` reproduces it. The
resolver therefore keeps whichever post happens to succeed:

- in a fresh session with two links, the first, as for WIC 11450;
- in one 2026-09-14 run, the first link for R&TC 17552.3 and the second for
  R&TC 17563.5.

So the version at the plain path of a multi-version section depends on the
session. This corrects the audit note's statement that a run in which both posts
succeed would keep version 2. With one shared view state, both posts cannot
succeed.

### WIC 11450 was amended overnight

On 2026-09-25 the picker's second link was Stats. 2024, Ch. 798, Sec. 2. On
2026-09-26 it is Stats. 2026, Ch. 310, Sec. 2 (AB 2765, effective September 18,
2026).

- **What AB 2765 changed.** It amended only the later version, and there only
  (e): the recurring special needs allowance rises from ten dollars ($10) to
  fifteen dollars ($15) per eligible recipient.
- **Version 1 is not amended.** Its text is unchanged. Only its history note's
  pointer moved, and it now reads "See later operative version, as amended by
  Sec. 2 of Stats. 2026, Ch. 310."
- **Identity moved with the amendment.** The later version's LegInfo
  `sectionuid` changed as well, from `id_921fd5be-…` to `id_cc57e543-…`.
  Neither the op triple nor the `sectionuid` identifies a version across an
  amendment.
- **The operative clause did not move.** It still reads "Conditionally operative
  on or after July 1, 2024, by its own provisions."

## Design

### One row per version, at a same-number variant path

Each concurrent version is a row at `<section>--<slug>`. This is
`citation_segment.variant_segment`, the separator the New Mexico, Vermont,
Delaware, New Jersey and Alabama statute adapters already use. Released cuts
already carry such rows, for example:

- `us-nm/statute/7-1-6.21--effective-2027-07-01`;
- `us-al/statute/40-21-123--code-28957`, Alabama's version "effective upon
  ratification".

The variant is a sibling of the section, not a child, for three reasons:

- `schema/citation-path.v1.json` accepts it.
- axiom-encode's resolver takes a row's descendants to be the paths under
  `<path>/` (`_read_descendant_records`). It finds ancestors by splitting on `/`
  (`_parent_citation_paths`).
- So `us-ca/statute/wic/11450--operative-2024-07-01/a/1/A` falls back to its own
  version's row, never to version 1's. A child-shaped path such as `11450/v2`
  would read as a subdivision of version 1.

### The slug comes from the version's own history note

`california_versions.leginfo_variant_slug` applies the first rule that matches:

1. `operative-YYYY-MM-DD` if the note says the version is (conditionally)
   operative on, or on or after, a date;
2. `inoperative-YYYY-MM-DD` if it becomes (conditionally) inoperative on, or on
   or after, a date;
3. `repealed-YYYY-MM-DD` if it is repealed on, on or after, or as of a date;
4. otherwise `stats-<year>[-ch-<chapter>][-sec-<section>]`, the op triple with
   LegInfo's own abbreviations. Empty fields are left out, as with Prop. 63's
   `stats-2004-sec-12`.

Why this order:

- **Dated clauses before the triple.** A dated clause names what the version is
  for, and that outlived AB 2765 where the op triple did not.
- **The start date before the end date.** A version's operative date is fixed
  when the version is created. End dates are added to it, and moved, when a
  later version follows: WIC 11451.5's middle version was "conditionally
  operative June 1, 2020" before it also became "conditionally inoperative on or
  after October 1, 2024". Taking the end date first would re-key WIC 11450's
  later version the next time a version after it is enacted.
- **Two versions of one section with the same slug raise an error** instead of
  guessing.
- **A note naming an impossible date raises** with that cause.

The rows:

| Row | Slug basis in the note |
| --- | --- |
| `wic/11450--operative-2021-07-01` | "Section conditionally operative July 1, 2021, or later date" (also "conditionally inoperative on or after July 1, 2024") |
| `wic/11450--operative-2024-07-01` | "Conditionally operative on or after July 1, 2024" |
| `wic/11451.5--repealed-2020-06-01` | "Repealed on or after June 1, 2020" (no operative clause) |
| `wic/11451.5--operative-2020-06-01` | "Section conditionally operative June 1, 2020, or after" (also "conditionally inoperative on or after October 1, 2024") |
| `wic/11451.5--operative-2024-10-01` | "Conditionally operative on or after October 1, 2024" |
| `rtc/17552.3--stats-2002-ch-34-sec-22` | no dated clause; "Added by Stats. 2002, Ch. 34, Sec. 22" |
| `rtc/17552.3--stats-2002-ch-35-sec-22` | no dated clause; "Added by Stats. 2002, Ch. 35, Sec. 22" |
| `rtc/17563.5--stats-2002-ch-34-sec-24` | no dated clause; "Added by Stats. 2002, Ch. 34, Sec. 24" |
| `rtc/17563.5--stats-2002-ch-35-sec-24` | no dated clause; "Added by Stats. 2002, Ch. 35, Sec. 24" |

The slug is a label taken from LegInfo's note and says nothing about whether a
condition has occurred. Which WIC 11450 version governs on a given day turns on
the department's notification date, which the corpus does not record. The rows
therefore carry no `status`. `metadata.leginfo_note_clauses` records each dated
clause the note names, with its date and whether the note calls it conditional,
e.g. `{"operative": {"date": "2024-07-01", "conditional": true}}`, and nothing
more.

### Every version gets a variant path, and the plain path keeps its carrier's version

New Mexico and New Jersey keep the first printed version at the plain path and
suffix only the others. Their publishers print the versions in a fixed order in
one document. Here the version at the plain path is whatever its carrier's
capture session produced (see above). So every version gets a variant path, and
the plain path keeps the version its carrier captured.

- **Existing citations keep resolving as before.** rulespec-us cites
  `us-ca/statute/wic/11450`, and its draft PR #1365 re-points a module to it.
  That path keeps resolving to version 1.
- **Every version has an explicit path.** That path does not depend on how a
  capture happened to go.
- **A version's text can sit at two paths.** In a cut that selects both scopes,
  the plain row is an earlier capture of one of the versions. This is intended.
  Release validation keys uniqueness on `citation_path` alone
  (`duplicate_release_citation`,
  `src/axiom_corpus/corpus/release_quality.py:233-245`).

Which version each plain path holds differs by section, so this table records
it. `test_every_us_ca_plain_row_of_these_sections_is_one_of_these_versions`
checks it over every us-ca statute scope, by `sectionuid`, op triple and text:

| Plain path | Carrier | Same version as |
| --- | --- | --- |
| `us-ca/statute/wic/11450` | CalWORKs 2026-06-25 | `--operative-2021-07-01` (the earlier version) |
| `us-ca/statute/wic/11451.5` | CalWORKs 2026-06-25 | `--operative-2024-10-01` (the latest version) |
| `us-ca/statute/rtc/17552.3` | income tax chapter 2026-09-14 | `--stats-2002-ch-34-sec-22` |
| `us-ca/statute/rtc/17563.5` | income tax chapter 2026-09-14 | `--stats-2002-ch-35-sec-24` |

The plain rows differ from their variants only in the history note. CalWORKs'
WIC 11450 note still points to "Stats. 2024, Ch. 798", where LegInfo now prints
"Stats. 2026, Ch. 310".

### Alternatives not taken

| Alternative | Why not |
| --- | --- |
| Version 2 at `us-ca/statute/wic/11450` in a new scope | One `duplicate_release_citation` against CalWORKs, or #742's successor, in any cut that keeps them. It would also silently change what rulespec-us's citation resolves to. |
| A CalWORKs successor carrying the plain rows plus the versions | It must replace CalWORKs and #742's successor in every cut, it covers only two of the four sections, and the plain path would still depend on the session. |
| A child path (`11450/version-2`) | axiom-encode reads it as a subdivision of version 1, both for descendant composition and for ancestor slicing. |
| An `@` suffix (Nevada, Texas and Colorado adapters) | `schema/citation-path.v1.json` rejects `@`. |
| Select one version by date (NC `version_aware_splitter`) | It needs the applicable date, and the notification date is not recorded. |
| A version segment before the section (German `fassung-YYYY-MM-DD/<section>`) | It needs validity dates, and it exists only in hand-written manifests. |
| Slug from the op triple (`--stats-2024-ch-798-sec-2`) | It moved overnight with AB 2765. It is kept as the fallback for notes without a dated clause. |
| Picker ordinal (`--variant-2`) | All four pickers list their versions in ascending triple order. If LegInfo sorts that way, amending an earlier version reorders them. |

### Row contents

Each row is a `section` row built from its own retained page, with the fields
the adapter already writes, plus:

- **Identity fields.** `metadata.op_statues`, `op_chapter` and `op_section` hold
  the page's own triple. Unselected rows still write null there.
  `metadata.variant`, `metadata.canonical_citation_path` (the plain path) and
  the identifier `california:variant` follow the New Mexico and New Jersey
  convention. `metadata.variant_citation_paths` lists every version of the
  section that the scope carries.
- **`metadata.leginfo_version_label`**, e.g. "Stats. 2026, Ch. 310, Sec. 2".
  `citation_label` and `legal_identifier` stay "Cal. WIC Code § 11450", as in
  New Mexico.
- **`metadata.leginfo_note_clauses`**, the note's dated clauses, and
  **`metadata.leginfo_version_count`**, the number of versions LegInfo offered
  (1 when LegInfo served the section directly).
- **`metadata.leginfo_picker`**: the retained picker's `source_path` and
  `sha256`, this version's index, and every version the picker offered with its
  link text. The link text keeps LegInfo's amendment lineage ("Amended (as
  amended by Stats. 2024, Ch. 798, Sec. 2) by Stats. 2026, Ch. 310, Sec. 2"). The
  picker is a supporting source file, not an inventory item. `publish_corpus.py`
  takes every file under a scope's source prefix
  (`scripts/publish_corpus.py:681-690`), so it is published with the scope.
- **`metadata.leginfo_retrieval`**: the exact form post that retrieved the page,
  without its per-request view state.
- **`source_url`**: LegInfo's GET-addressable print page for the version
  (`printCodeSectionWindow.xhtml?…&op_statues=…&op_chapter=…&op_section=…`).
  The display URL answers with the picker. The retained bytes are the posted
  display page, which carries the `sectionuid`. On 2026-09-27 each of the nine
  print URLs served the same text as its retained page (one GET each, extracted
  with `--preserve-tables`). A later amendment re-keys a version's triple, so an
  older print URL can stop resolving.

## Adapter change

`extract-california-code-sections` (`extract_california_code_sections`,
`_load_california_section_versions`, `_california_version_section` in
`states.py`; the new module `california_versions.py`):

- **Selectors.** `--section WIC:11450@all` selects every version the picker
  offers. `--section WIC:11450@<slug>` selects one. The scope version gets the
  selector (`wic-11450--all`).
- **Fetching.** Every version is fetched, whatever the selector. Each gets its
  own GET of the picker, and the picker's version list must not change between
  GETs. Then one POST of that link goes out with that GET's form fields.
  A response counts only when it is a section page whose `printPopup()`
  triple is the link's.
- **Failure.** A failed post is retried up to `--request-attempts` times, each
  time after a fresh GET, because any post spends the view state. Any other
  failure raises `CaliforniaVersionError`, and nothing is written for that run.
  The failures are:
  - a request that still fails;
  - a changed picker;
  - a wrong or missing version;
  - a shared slug;
  - a note with an impossible date;
  - an unknown selector;
  - a section requested more than once when any request has a selector.
- **Offline rerun.** With `--download-dir`, the picker and every version page
  are cached under their slugs. A cache holding the picker and one page per
  version reruns with no request at all, and the scope's retained sources form
  such a cache. Without the picker the section is refetched. Two cached pages of
  one version raise.
- **Unselected specs are unchanged.** `test_unselected_specs_still_reproduce_committed_scopes_offline`
  re-extracts the CalWORKs scope and the SB 1435 scope from their retained
  bytes, with the network blocked. Their committed sources, inventory and
  coverage come out byte for byte, and their rows come out apart from the
  parent detachment applied after extraction.
- **Signatures.** Callers that pass 2-tuples keep working, including #742's
  repro script:
  - `_california_sections_run_id(version, specs)` gives the historical id;
  - `_california_section_html_relative_name(law_code, section)` gives the
    historical name.

## Generation

The scope was extracted on 2026-09-26 (13:41:06Z to 13:41:50Z):

```bash
uv run --extra dev axiom-corpus-ingest extract-california-code-sections \
  --base data/corpus \
  --version 2026-09-26-ca-leginfo-concurrent-versions \
  --source-as-of 2026-09-26 \
  --expression-date 2026-09-26 \
  --section 'WIC:11450@all' \
  --section 'WIC:11451.5@all' \
  --section 'RTC:17552.3@all' \
  --section 'RTC:17563.5@all' \
  --delay-seconds 1 \
  --download-dir <download cache; a copy of this scope's retained sources reproduces the run offline> \
  --preserve-tables

uv run --extra dev python scripts/self_contain_usc_scope.py \
  --base data/corpus \
  --jurisdiction us-ca \
  --document-class statute \
  --version 2026-09-26-ca-leginfo-concurrent-versions-us-ca-sections-wic-11450--all-wic-11451.5--all-rtc-17552.3--all-rtc-17563.5--all
```

`--preserve-tables` keeps every table cell and repeated block, as the SB 1435
scope and #742's successors do. The adapter emits each row with the parent
`us-ca/statute/wic` or `us-ca/statute/rtc`, a container this scope does not
carry. The second command detaches it, as for the SB 1435 and chapter scopes.
`parent_citation_path` and `parent_id` become null, and
`metadata.detached_parent_citation_path` and `metadata.self_contained_root`
record the omitted container. Coverage is complete: 9 inventory items, 9
provisions, 9 matched.

A first attempt at 13:38Z got HTTP 503 from `codes_displaySection` for every
section, while the LegInfo home page answered 200. The adapter raised and wrote
nothing. A poll found the service back at 13:39:54Z.

After the design review (below), the slug rule changed and the scope was rebuilt
from its own retained bytes, with no LegInfo request. Each version page was
renamed to the slug the new rule gives its note, in a copy used as the download
cache, and the two commands above were rerun with every HTTP request routed to a
closed local port. The retained bytes, and so every SHA-256 below, are unchanged.
Two file names changed with their slugs: `WIC-11450--operative-2021-07-01.html`
and `WIC-11451.5--operative-2020-06-01.html`.

## Source

All pages are from <https://leginfo.legislature.ca.gov>, retrieved 2026-09-26.
Each version page was posted from its picker. Its GET-addressable print URL is
the row's `source_url`.

| Row | Version | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `us-ca/statute/wic/11450--operative-2021-07-01` | Stats. 2024, Ch. 798, Sec. 1 | 198,559 | `463f4b8189b9d5a6e52da1a704a67746d5d66957bfafb92eda53b19b2f935c4f` |
| `us-ca/statute/wic/11450--operative-2024-07-01` | Stats. 2026, Ch. 310, Sec. 2 | 197,632 | `c52c82ee68d4a616aae53b38ea329a2726a46bb2e97381f08a57e40495d644f0` |
| `us-ca/statute/wic/11451.5--repealed-2020-06-01` | Stats. 2019, Ch. 27, Sec. 59 | 166,472 | `bad86343d3f8138f0b7acc8723619a4bb029efd430b42a6750929a463fa87ac2` |
| `us-ca/statute/wic/11451.5--operative-2020-06-01` | Stats. 2022, Ch. 588, Sec. 5 | 167,774 | `660420c1f37cb5a662e650bd1d0cfcb0240d43b19969fdf590e317a26a8a2263` |
| `us-ca/statute/wic/11451.5--operative-2024-10-01` | Stats. 2022, Ch. 588, Sec. 6 | 167,181 | `0dbe70354a525921066b6f65955d64d45dbd5f7db745f55fa6dd72152c96604d` |
| `us-ca/statute/rtc/17552.3--stats-2002-ch-34-sec-22` | Stats. 2002, Ch. 34, Sec. 22 | 165,183 | `3456d22e25e54fa074e03ee495e05d5632f1951a8be2dc187a25074079298f2b` |
| `us-ca/statute/rtc/17552.3--stats-2002-ch-35-sec-22` | Stats. 2002, Ch. 35, Sec. 22 | 165,129 | `db1ffdbd9b8c2b0127d0abe677d5468b31df99d7bc2f499ff7570f5d22dec11e` |
| `us-ca/statute/rtc/17563.5--stats-2002-ch-34-sec-24` | Stats. 2002, Ch. 34, Sec. 24 | 165,180 | `84a71f529b0202b693d7a7c4c39659ac81086c96c66531b0f7ab9480a2cca9c7` |
| `us-ca/statute/rtc/17563.5--stats-2002-ch-35-sec-24` | Stats. 2002, Ch. 35, Sec. 24 | 164,972 | `b2e8081039b29f80c0b3c3181afa9ac2fcfe2e0724dccbbbda3edc1397745237` |

The pickers are retained under `california-leginfo-pickers/`:

| Picker | Bytes | SHA-256 |
| --- | ---: | --- |
| `WIC-11450.html` | 106,378 | `fdffabda5b2d0f7886fa111b6dc421a1492b7cb55f80185782959132bc29b037` |
| `WIC-11451.5.html` | 106,778 | `8fe47890762bfac98f594f3f55d020505be440bfcf0fb37e6fba5fc7daf35a47` |
| `RTC-17552.3.html` | 106,278 | `3ff2b945feb69423ec146cab558c9f1664b7cdd5366f9edbd3bccd32991daffc` |
| `RTC-17563.5.html` | 106,278 | `39d305ef3e8fd2cc630134301fb5554d9eea74380f5de33fb8abecdc6c549e45` |

LegInfo pages embed per-request view-state tokens, so the retained bytes differ
from any other fetch of the same page. The extracted text does not.

## What the rows say

**WIC 11450.** The two versions differ only in:

- (c)(1): version 2 drops "commencing October 1, 2023," from the perinatal
  home-visiting clause;
- (e): $10 against $15 (AB 2765);
- (f)(3)(B): version 2 adds "or any notice that could lead to an eviction,
  regardless of the circumstances cited in the notice";
- (f)(4)(E)(iii): version 2 adds "including, but not limited to, a parent or
  child with whom they were living", and drops the October 1, 2023 start of the
  case-plan condition;
- (n) through the end: version 1's (n) says July 1, 2021, and version 2's says
  July 1, 2024; version 1 has (o) and (p), and version 2 has neither;
- the history note.

(a)(1)(A) and its maximum-aid table ($326 for one person through $1,403 for ten
or more) are identical in both versions.

**WIC 11451.5.** There are three versions:

- Stats. 2019, Ch. 27, Sec. 59: "Repealed on or after June 1, 2020, as
  prescribed by its own provisions."
- Stats. 2022, Ch. 588, Sec. 5: conditionally operative June 1, 2020, and
  conditionally inoperative on or after October 1, 2024.
- Stats. 2022, Ch. 588, Sec. 6: conditionally operative on or after October 1,
  2024.

CalWORKs carries the third at the plain path.

**R&TC 17552.3 and 17563.5.** Stats. 2002, Chs. 34 and 35 each added these
sections, and the Ch. 34 notes say "See identical section added by Stats. 2002,
Ch. 35."

- The 17552.3 texts are identical.
- The 17563.5 texts differ in (b)(3): Ch. 34 reads "three-taxable-year" and
  Ch. 35 reads "three taxable year".

## Release boundary

The scope adds only variant paths. No other us-ca scope carries a `--` path
(`test_no_other_us_ca_scope_carries_a_variant_path`). It validates with strict
warnings and zero issues next to the us-ca statute scopes of each current line
(`test_the_scope_joins_the_newest_cuts_us_ca_statute_scopes_cleanly`):

- `us-rulespec-2026-09-24-snap-fy2027-cola`: CalWORKs, SSI/SSP, PIT core, the
  July recovery scope and CalFresh BBCE;
- `us-rulespec-2026-09-14-wave4-r2-union`: CalWORKs, SSI/SSP, CalFresh BBCE and
  the chapter scope.

#742's successors carry the same plain paths as the scopes they succeed, so the
scope works with either. A later cut adds it next to the scopes it already
selects, and removes nothing. This run adds no selector: a new
`manifests/releases/*.json` on `main` publishes.

## Downstream

- **rulespec-us.** `us-ca/policies/cdss/calworks/monthly-aid-payment.yaml`
  cites `us-ca/statute/wic/11450/a/1/A` today, and draft PR #1365 re-points it
  to `us-ca/statute/wic/11450`. Both keep resolving to version 1. The (a)(1)(A)
  text and table they quote read the same in both versions. A module that has
  to name a version can cite its variant path once a cut carries this scope.
- **AB 2765.** It changed (e) only in the later version. Whether any rulespec-us
  CalWORKs encoding depends on the special needs amount is a rulespec-us
  question, recorded as a follow-up.

## Review

An independent review ran on a Subfleet Opus lane, read-only, against
e540eb898 and the first capture (bbd5e78d9). Its verdict was approve with
changes. The findings and what this run did:

| Finding | Disposition |
| --- | --- |
| Terminating-first slugs re-key a version when it later gets an end date | Changed to operative first; the scope was rebuilt from its retained bytes |
| `status` reads as "version 1 current, version 2 pending" | Removed; `leginfo_note_clauses` records the dated clauses without judging them |
| Which version each plain path holds differs by section and is not recorded | Table under the design section; a test checks it over every us-ca statute scope |
| A section requested twice rewrites the retained picker | Refused when any of the requests has a selector |
| A cache without the picker could pass for a single-version section | The cache needs the picker; two cached pages of one version raise |
| No test reruns the new scope offline | `test_the_scope_rebuilds_offline_and_byte_identically_from_its_retained_bytes` already did; a three-version fake picker test was added |
| One failed post aborts the run; a slug error was reported as a missing version | Posts are retried after a fresh GET; the slug error is reported with its cause |
| `source_url` names a page that was never fetched | Kept, with the retrieval recorded; all nine print URLs were checked live on 2026-09-27 |
| A single-page `@all` result gives no sign of it | `leginfo_version_count` |
| The picker is not an inventory item | Documented as a supporting source file, published with the scope |

The review said a drift guard should compare a recapture's slugs with its
predecessor's. That needs a recapture, so it is listed below.

## Follow-ups

These are recorded, not done here:

1. **Unselected picker sections.** An unselected spec still lets the session
   choose the version for the plain path. Such specs should either fail closed
   on a picker or take an explicit plain-path selector. The same holds for the
   pubinfo bulk path, which keeps the first `LAW_SECTION_TBL` row per section.
2. **rulespec-us.** Check the CalWORKs encodings against AB 2765's amendment of
   WIC 11450(e) in the later version.
3. **`@` variant paths.** The Nevada, Texas and Colorado adapters still build
   `@` paths, which the citation-path grammar rejects, and Oregon and Rhode
   Island fold `@` into a single `-`. They should converge on
   `variant_segment`.
4. **Audit note.** The recovery audit note on `fix/us-ca-recovery-chrome-audit`
   (lines 230-235) should take the correction above before it merges.
5. **Drift and plain-path checks at release time.** A recapture of these
   sections should fail, or warn, when a version's slug differs from the one
   its predecessor gave the same lineage. The picker link text records the
   lineage. Release validation could also check that a plain CA row in a cut
   is the same `sectionuid` as one of the variants the cut carries. Today only
   this scope's tests check that.

## Checks

Run with this branch's files on `origin/main` b5b637167:

- **Focused tests.** 49 pass:
  - `tests/test_california_versions.py` (21): pure functions and Hypothesis
    properties;
  - `tests/test_corpus_california_section_versions.py` (19): the adapter against
    a fake LegInfo that accepts one post per view state, plus the differential
    rerun of two merged scopes;
  - `tests/test_us_ca_leginfo_concurrent_versions.py` (9): the committed scope,
    including a byte-identical offline rebuild from its retained bytes.

  With `tests/test_corpus_states.py`, 110 pass.
- **Full suite.** `uv run --extra dev python -m pytest -q` gave 4,791 passed,
  103 skipped and 208 deselected at bbd5e78d9, with the repository's ingest
  public key set. The review changes after it touch only the selected path and
  its tests; CI runs the suite on the pull request.
- **Lint and types.** `ruff check .` passes. `mypy src/axiom_corpus/corpus
  --ignore-missing-imports` finds no issues.
- **Citation paths.** `python scripts/validate_citation_paths.py` gives
  `RESULT: OK`. The nine paths use only the grammar alphabet and add to no
  irregular family.
- **Changelog.** `towncrier check --compare-with origin/main` finds the
  fragment.
- **Ingest guard.** The pull request records the result of
  `axiom-corpus-ingest guard-ingested --base-ref origin/main --head-ref HEAD`,
  run with the repository's public key after signing.

The invariants the tests execute:

- **Slugs.** For every LegInfo triple, the act slug round-trips and is
  injective. Every slug is a grammar-safe segment. A version's operative date
  names it whether or not an end date is added later.
- **Capture.** Every picker version is fetched and verified. A shared slug
  fails.
- **Reproducibility.** A complete cache reruns offline, byte for byte.
  Unselected specs reproduce merged scopes.

## Signing

The ingest manifest
`.axiom/ingest-manifests/us-ca/statute/2026-09-26-ca-leginfo-concurrent-versions-us-ca-sections-wic-11450--all-wic-11451.5--all-rtc-17552.3--all-rtc-17563.5--all.json`
is signed from a clean checkout of the commit that adds the artifacts and this
note. It attests this note as its reasoning log, so editing the note requires
re-signing.
